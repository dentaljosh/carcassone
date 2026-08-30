"""`scripts/carcasum_remote/server.py` — the phone's remote-opponent daemon.

Three layers, cheapest first:

1. **The positional log contract**, with no driver at all. This is where the one
   subtle bug lives: `play_one_match` SYNTHESISES external-seat actions of its
   own (the implicit meeple pass, the redraw pass) that the phone also applies
   locally, so an action QUEUE would end up one entry out of step and silently
   play the wrong move. The session indexes by ply instead; these tests pin that,
   plus prefix divergence and retry idempotence.

2. **The R1 scoring gate**, against whatever driver is on this box — the gate
   that refuses to start against an unpatched Carcasum (a 2-tile city scoring 2
   instead of 4 is a RULES result wearing a strength result's costume).

3. **A whole game end to end**, driven through the HTTP API by
   `scripts/carcasum_remote/smoke_client.py`'s own logic, against
   `stub_driver.py` where the real binary is absent and against the real
   `carcasum_driver` where it is present. The stub proves the plumbing; only the
   real binary proves anything about Carcasum, and the test says which it ran.
"""
from __future__ import annotations

import json
import random
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "carcasum_remote"))

import server as S  # noqa: E402

REAL_DRIVER = REPO / "vendor" / "carcasum" / "build-driver" / "carcasum_driver"
STUB_DRIVER = REPO / "scripts" / "carcasum_match" / "stub_driver.py"


# --------------------------------------------------------------------------- #
# 1. the positional log contract (no driver)                                   #
# --------------------------------------------------------------------------- #
class _NoDriverSession(S._Session):
    """A session whose game thread does nothing — the protocol logic in isolation."""

    def _run(self, **kwargs):                                     # noqa: ARG002
        while not self._stop.is_set():
            time.sleep(0.01)


def _bare_session(**kw) -> _NoDriverSession:
    return _NoDriverSession(
        game_id=kw.get("game_id", "t"), deck_seed=kw.get("deck_seed", 1),
        human_seat=kw.get("human_seat", 0), binary=Path("/nonexistent"),
        opponent={}, node_labels={}, periods={}, verify_replay=False,
        max_wait_s=kw.get("max_wait_s", 0.6))


def test_the_external_action_is_read_BY_PLY_not_popped_from_a_queue():
    """The bug an action queue would have: a server-synthesised pass desyncs it.

    Sequence: the phone plays a tile (ply 0) and its own forced meeple pass
    (ply 1) and sends BOTH. The server's driver only asks for the tile — it
    applies the meeple pass itself, because Carcasum never sent `req_meeple`. A
    queue would still be holding that pass and would feed it to the NEXT request
    for a tile. Indexed by ply, the server simply reads ply 2 next.
    """
    s = _bare_session()
    try:
        s.submit([100, 101])                       # tile + the phone's forced pass
        assert s._pull_external_action() == 100    # the driver asks for the tile
        s._on_apply(100, 0, "champ_tile")
        s._on_apply(101, 0, "champ_meeple_pass_implicit")   # SERVER-synthesised
        s.submit([100, 101, 102])                  # phone's next real decision
        assert s._pull_external_action() == 102, (
            "the session replayed a stale queued action instead of reading the "
            "action at the current ply")
    finally:
        s.close()


def test_a_retry_gets_the_identical_answer_and_runs_no_second_search():
    s = _bare_session()
    try:
        s._on_apply(500, 1, "opp_tile")            # the opponent's committed move
        first = s.next_action(0)
        again = s.next_action(0)                   # the phone never saw the reply
        assert first == again
        assert first["action"] == 500
        assert first["seat"] == 1
    finally:
        s.close()


def test_a_divergent_client_log_is_a_loud_409_not_a_silent_repair():
    s = _bare_session()
    try:
        s.submit([10, 11])
        s._on_apply(10, 0, "champ_tile")
        s._on_apply(11, 0, "champ_meeple")
        with pytest.raises(S.SessionError) as e:
            s.submit([10, 99])                     # ply 1 disagrees
        assert e.value.code == "divergence"
        assert e.value.extra["ply"] == 1
    finally:
        s.close()


def test_the_client_may_be_BEHIND_without_that_being_a_divergence():
    """The ordinary lost-response case: shorter is fine, contradictory is not."""
    s = _bare_session()
    try:
        s._on_apply(10, 0, "champ_tile")
        s._on_apply(20, 1, "opp_tile")
        s.submit([10])                             # phone has not applied ply 1 yet
        assert s.next_action(1)["action"] == 20
    finally:
        s.close()


def test_waiting_on_a_move_the_client_owes_says_so_instead_of_hanging():
    s = _bare_session()
    try:
        s.submit([])
        t = threading.Thread(target=s._pull_external_action, daemon=True)
        t.start()
        time.sleep(0.15)
        with pytest.raises(S.SessionError) as e:
            s.next_action(0)
        assert e.value.code in ("needs_more_actions", "timeout")
    finally:
        s.close()


def test_a_session_id_bound_to_one_deck_cannot_be_reused_for_another():
    srv = object.__new__(S.RemoteOpponentServer)
    srv._lock = threading.Lock()
    srv._sessions = {}
    srv.session_ttl_s = 3600
    s = _bare_session(game_id="g1", deck_seed=5)
    srv._sessions["g1"] = s
    try:
        with pytest.raises(S.SessionError) as e:
            srv.get_or_create(game_id="g1", deck_seed=6, human_seat=0,
                              opponent=None, client_actions=[])
        assert e.value.code == "session_mismatch"
    finally:
        s.close()


def test_a_game_the_opponent_has_MOVED_in_cannot_be_picked_up_fresh():
    """Carcasum is not replayable — say so, do not fake a resume.

    But the discriminator is "has the OPPONENT moved", not "is the log
    non-empty": with the human on seat 0 he plays ply 0 (and possibly his
    meeple) before Carcasum is ever asked, so the first request of a brand-new
    game legitimately carries actions. Getting that wrong makes every
    human-first game unstartable, which is how this was caught.
    """
    srv = object.__new__(S.RemoteOpponentServer)
    srv._lock = threading.Lock()
    srv._sessions = {}
    srv.session_ttl_s = 3600
    with pytest.raises(S.SessionError) as e:
        # An unreplayable log fails CLOSED — counted as "the opponent has moved".
        srv.get_or_create(game_id="gone", deck_seed=1, human_seat=0,
                          opponent=None, client_actions=[-1, -2, -3])
    assert e.value.code == "session_lost"
    assert "abandoned" in str(e.value)


def test_the_opening_plies_of_a_human_first_game_are_not_a_resume():
    """A real opening log: replay it and count who owned each ply."""
    M = S.match_module()
    from carcassonne_ai import rules_profile
    from carcassonne_ai.game_wrapper import Game

    prof = rules_profile.activate(M.PROFILE)
    random.seed(4242)
    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    board = game.get_init_board()
    opening: list[int] = []
    while int(board.state.current_player) == 0:
        legal = [i for i, v in enumerate(game.get_valid_moves(board)) if v]
        board, _ = game.get_next_state(board, legal[0])
        opening.append(legal[0])
    assert opening, "seat 0 owns at least the first ply"
    assert S._count_opponent_plies(4242, opening, human_seat=0) == 0
    # And the same log read from the OTHER seat is all opponent plies.
    assert S._count_opponent_plies(4242, opening, human_seat=1) == len(opening)


def test_the_anchor_sha_is_the_binary_named_in_the_prep():
    # An IDENTITY, not a version floor. If this changes, the opponent changed and
    # `B = champion - Carcasum@5s` no longer applies to it.
    assert S.ANCHOR_SHA256 == (
        "c090847e1befa007e9b3b3031a9c880a60915e36f143aa6c3c30691599792968")
    assert S.OPPONENT_LABEL == "carcasum_remote_5000ms"


def test_a_wrong_binary_hash_refuses_to_start(tmp_path):
    fake = tmp_path / "carcasum_driver"
    fake.write_bytes(b"not the anchor binary")
    with pytest.raises(SystemExit) as e:
        S.build_gate(fake, expect_sha=S.ANCHOR_SHA256, allow_any=False)
    assert "G-BINARY FAILED" in str(e.value)


# --------------------------------------------------------------------------- #
# 2/3. against a driver                                                        #
# --------------------------------------------------------------------------- #
def _driver_param():
    if REAL_DRIVER.is_file():
        return pytest.param(REAL_DRIVER, id="real-carcasum")
    return pytest.param(
        STUB_DRIVER, id="stub-driver",
        marks=pytest.mark.xfail(
            reason="the REAL carcasum_driver is not built on this box; the stub "
                   "exercises the plumbing only and proves nothing about Carcasum",
            strict=False))


@pytest.fixture(params=[_driver_param()])
def driver(request):
    return request.param


def test_the_R1_scoring_probe_observes_a_two_tile_city_scoring_four(driver):
    """The gate that refuses an unpatched build, run live."""
    out = S.probe_tiny_city_scores_four(driver, budget_ms=20)
    assert out["tiny_city_score"] == 4
    assert out["board_size"] % 2 == 1
    assert out["start_xy"] == [out["board_size"] // 2] * 2


def _serve(srv) -> tuple[ThreadingHTTPServer, str]:
    handler = type("_H", (S._Handler,), {"srv": srv})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    host, port = httpd.server_address[:2]
    return httpd, f"http://{host}:{port}"


def test_a_whole_game_plays_through_the_http_api(driver):
    """End to end: random-legal on our side, the driver's own player on theirs.

    Asserts the three things the phone depends on — every opponent move inverts
    onto one of OUR legal actions, the finished `(deck_seed, actions)` pair
    replays to the same scores, and the server and client agree on the result.
    """
    M = S.match_module()
    from carcassonne_ai import rules_profile
    from carcassonne_ai.game_wrapper import Game

    srv = S.RemoteOpponentServer(
        binary=driver,
        opponent=dict(M.DEFAULT_OPPONENT, budget_ms=20),
        gate={"state": "TEST", "sha256": S.sha256_file(driver)},
        verify_replay=True, max_wait_s=120.0, records_dir=None)
    httpd, url = _serve(srv)
    try:
        health = json.loads(urllib.request.urlopen(url + "/health", timeout=20).read())
        assert health["ok"] and health["opponent_label"] == S.OPPONENT_LABEL

        deck_seed, human = 20260830, 0
        prof = rules_profile.activate(M.PROFILE)
        random.seed(deck_seed)
        game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
        board = game.get_init_board()
        rng = random.Random(11)
        actions: list[int] = []
        blips = 0

        while game.get_game_ended(board, 0) == 0 and len(actions) < 400:
            if int(board.state.current_player) == human:
                legal = [i for i, v in enumerate(game.get_valid_moves(board)) if v]
                a = int(rng.choice(legal))
            else:
                body = json.dumps({"game_id": "t1", "deck_seed": deck_seed,
                                   "human_seat": human,
                                   "actions": actions}).encode()
                req = urllib.request.Request(
                    url + "/move", data=body,
                    headers={"Content-Type": "application/json"}, method="POST")
                resp = json.loads(urllib.request.urlopen(req, timeout=120).read())
                if len(actions) % 7 == 0:          # a lost response, re-sent
                    req2 = urllib.request.Request(
                        url + "/move", data=body,
                        headers={"Content-Type": "application/json"}, method="POST")
                    again = json.loads(urllib.request.urlopen(req2, timeout=120).read())
                    assert again == resp, "a retry produced a different move"
                    blips += 1
                assert resp["action"] is not None, resp
                a = int(resp["action"])
                assert int(resp["seat"]) == 1 - human
                assert game.get_valid_moves(board)[a], (
                    f"the opponent's move {a} is not legal on our board")
            board, _ = game.get_next_state(board, a)
            actions.append(a)

        assert game.get_game_ended(board, 0) != 0, "the game did not terminate"
        assert blips > 0, "the idempotence probe never fired"
        rp = M.replay_actions(deck_seed, actions, M.PROFILE)
        assert rp["ok"] and rp["scores"] == list(board.state.scores)

        req = urllib.request.Request(
            url + "/end", data=json.dumps({"game_id": "t1"}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        fin = json.loads(urllib.request.urlopen(req, timeout=60).read())
        rec = fin["record"]
        assert rec is not None, fin
        assert list(rec["scores"]) == list(board.state.scores)
        assert rec["void"] is None, rec["void_detail"]
        assert not rec["real"], rec["real"]
        assert rec["replay_ok"]
    finally:
        httpd.shutdown()
