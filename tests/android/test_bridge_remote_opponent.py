"""The phone's REMOTE-OPPONENT mode, end to end, without Carcasum.

The one thing that must never happen is a remote game being read later as a
champion game: `measurement/e4_games/` is the owner-vs-CHAMPION stream, and the
Carcasum owner session's whole discriminator is chained through the anchor drawn
from it. So the tests that matter here are the LABELLING ones — and they are run
against a real finished game, not a mocked session, because the label has to
survive `_build_opponent` -> `_save_payload` -> `archive_record`.

The opponent is faked by a local HTTP server that speaks the same protocol as
`scripts/carcasum_remote/server.py` and picks the first legal action from a
replay of the `(deck_seed, actions)` pair the client sends. That fake proves
nothing about Carcasum — it proves the PHONE side: the request shape, the
stateless replay contract, retry idempotence, the archive stamp, and that a
champion game is untouched by any of it.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import android_bridge as B


# --------------------------------------------------------------------------- #
# the fake opponent                                                            #
# --------------------------------------------------------------------------- #
class _FakeCarcasum:
    """Speaks the /health + /move protocol; plays first-legal from a replay.

    Deliberately stateless in the same way the real server's ANSWER is: it
    reconstructs the position from `(deck_seed, actions)` on every request, so
    re-sending the same body must produce the same move. That is the property
    the phone's retry path leans on, and this fake is the cheapest honest way to
    assert it.
    """

    def __init__(self):
        self.requests: list[dict] = []
        self.fail_next = 0
        h = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):                            # noqa: A003, ARG002
                pass

            def _send(self, code, obj):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):                                     # noqa: N802
                self._send(200, {
                    "ok": True, "opponent_label": "carcasum_remote_5000ms",
                    "gate": {"state": "ANCHOR", "sha256": "f" * 64,
                             "probe": {"tiny_city_score": 4}},
                    "opponent": {"kind": "mcts", "budget_ms": 5000},
                    "profile": {"rules_profile": "fixed_v1", "r9_env": "1"}})

            def do_POST(self):                                    # noqa: N802
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n).decode())
                h.requests.append(body)
                if h.fail_next > 0:
                    h.fail_next -= 1
                    self._send(503, {"ok": False, "error": "transport_test"})
                    return
                self._send(200, h.answer(body))

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}"

    def answer(self, body: dict) -> dict:
        import random

        from carcassonne_ai.game_wrapper import Game

        random.seed(int(body["deck_seed"]))
        game = Game(enable_legal_moves_cache=True, fixed_start_tile=True,
                    start_row=B.GRID_RULE_START[B.GRID_RULE][0],
                    start_col=B.GRID_RULE_START[B.GRID_RULE][1],
                    draw_rule=B.DRAW_RULE, cloister_scan_fix=True)
        board = game.get_init_board()
        for a in body["actions"]:
            board, _ = game.get_next_state(board, int(a))
        if game.get_game_ended(board, 0) != 0:
            return {"ok": True, "game_over": True, "action": None}
        mask = game.get_valid_moves(board)
        legal = [i for i, v in enumerate(mask) if v]
        return {"ok": True, "action": int(legal[0]), "seat": int(board.state.current_player),
                "index": len(body["actions"]), "n_actions": len(body["actions"]) + 1,
                "game_over": False}

    def close(self):
        self.httpd.shutdown()


@pytest.fixture()
def fake():
    f = _FakeCarcasum()
    yield f
    f.close()
    B.reset()


# --------------------------------------------------------------------------- #
# the label — the whole point                                                  #
# --------------------------------------------------------------------------- #
def test_label_helpers_are_the_single_source_of_the_string():
    assert B.remote_opponent_label(5000) == "carcasum_remote_5000ms"
    assert B.remote_opponent_label(50) == "carcasum_remote_50ms"
    # Both spellings route to the remote branch: the app sends the bare kind,
    # a save/archive feeds the LABELLED one straight back in on restore.
    assert B.is_remote_opponent("carcasum_remote")
    assert B.is_remote_opponent("carcasum_remote_5000ms")
    # And the two that must never be mistaken for it.
    assert not B.is_remote_opponent("champion")
    assert not B.is_remote_opponent("tier1")


def test_a_remote_game_is_never_stamped_champion(fake):
    out = json.loads(B.new_game(json.dumps({
        "seed": 12345, "human_player": 0, "opponent": "carcasum_remote",
        "remote_url": fake.url, "remote_budget_ms": 5000, "backend": "python"})))
    assert out["ok"], out
    st = json.loads(B.get_state())
    assert st["opponent"] == "carcasum_remote_5000ms", st["opponent"]
    assert st["opponent"] != "champion"
    save = json.loads(B.save_game())
    assert save["opponent"] == "carcasum_remote_5000ms"
    assert save["remote_url"] == fake.url
    assert save["remote_budget_ms"] == 5000


def test_a_champion_game_still_stamps_champion_and_carries_no_remote_block():
    """The golden gate on the python side: the champion path is untouched."""
    out = json.loads(B.new_game(json.dumps({
        "seed": 99, "human_player": 0, "opponent": "champion",
        "sims": 8, "k_dets": 1, "backend": "python", "verify": False})))
    assert out["ok"], out
    save = json.loads(B.save_game())
    assert save["opponent"] == "champion"
    # Present-but-None, never a remote address, on every champion game.
    assert save["remote_url"] is None
    assert save["remote_budget_ms"] is None
    B.reset()


def test_remote_needs_a_url():
    err = json.loads(B.new_game(json.dumps({
        "seed": 1, "opponent": "carcasum_remote", "backend": "python"})))
    assert not err.get("ok")
    assert "remote_url" in json.dumps(err)
    B.reset()


def test_health_is_checked_at_game_start_not_three_plies_in():
    err = json.loads(B.new_game(json.dumps({
        "seed": 1, "opponent": "carcasum_remote", "backend": "python",
        "remote_url": "http://127.0.0.1:1"})))
    assert not err.get("ok"), "a dead server must fail the NEW GAME, not a later move"
    B.reset()


# --------------------------------------------------------------------------- #
# the move path                                                                #
# --------------------------------------------------------------------------- #
def test_every_request_carries_the_full_root_replay_pair(fake):
    json.loads(B.new_game(json.dumps({
        "seed": 777, "human_player": 1, "opponent": "carcasum_remote",
        "remote_url": fake.url, "backend": "python"})))
    # human_player=1 means the REMOTE seat moves first, so new_game + one ai_move
    # is enough to see a request.
    res = json.loads(B.ai_move())
    assert res["ok"], res
    assert fake.requests, "no request reached the opponent"
    req = fake.requests[0]
    assert req["deck_seed"] == 777
    assert req["human_seat"] == 1
    assert req["actions"] == []                  # first move of the game
    assert req["opponent"] == {"budget_ms": 5000}
    assert req["game_id"] == "phone-777-1"
    # The log grows and is always sent WHOLE — that is what makes a resume
    # lossless rather than a guess.
    res2 = json.loads(B.ai_move()) if not res.get("terminated") else None
    if res2 is not None and res2.get("ok"):
        assert len(fake.requests[-1]["actions"]) > 0
    B.reset()


def test_a_transport_failure_is_retried_and_the_game_survives(fake):
    json.loads(B.new_game(json.dumps({
        "seed": 4242, "human_player": 1, "opponent": "carcasum_remote",
        "remote_url": fake.url, "backend": "python"})))
    fake.fail_next = 2                            # two 503s, then success
    res = json.loads(B.ai_move())
    assert res["ok"], res
    # Three requests, all with the IDENTICAL body: a retry re-sends the same
    # (deck_seed, actions) pair, which is why it cannot corrupt the game.
    bodies = [json.dumps(r, sort_keys=True) for r in fake.requests[:3]]
    assert len(bodies) == 3
    assert len(set(bodies)) == 1, bodies
    B.reset()


def test_a_full_remote_game_archives_with_the_remote_label(fake):
    """The end-to-end shape an owner-session game will actually have."""
    json.loads(B.new_game(json.dumps({
        "seed": 31337, "human_player": 0, "opponent": "carcasum_remote",
        "remote_url": fake.url, "backend": "python"})))
    guard = 0
    while guard < 400:
        guard += 1
        st = json.loads(B.get_state())
        if st.get("terminated"):
            break
        if st["current_player"] == st["human_player"]:
            legal = st["legal"]["ids"]
            assert legal, st
            r = json.loads(B.apply_action(int(legal[0])))
            assert r["ok"], r
        else:
            r = json.loads(B.ai_move())
            assert r["ok"], r
    arc = json.loads(B.archive_record())
    assert arc["ok"], arc
    assert arc["opponent"] == "carcasum_remote_5000ms"
    assert arc["opponent_name"].startswith("Carcasum")
    assert arc["schema"] == B.ARCHIVE_SCHEMA
    # WHICH opponent binary played, straight off the server's own health block.
    assert arc["remote"]["binary_gate"] == "ANCHOR"
    assert arc["remote"]["tiny_city_probe"] == 4
    assert arc["remote"]["url"] == fake.url
    assert arc["remote"]["calls"] > 0
    # And the E4 reader-side gate agrees this is NOT an anchor game.
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    import e4_archives

    assert not e4_archives.is_anchor_eligible(arc)
    assert "carcasum_remote" in e4_archives.rejection_reason(arc)
    B.reset()
