"""F9 / D2 — CI for the champion-vs-JCloisterZone-AI match driver.

The oracle's pytest (``test_jcz_replay_oracle.py``) guards the two engines' *rules*
agreement. This one guards the MATCH DRIVER that sits on top: the translation both
ways, the deck forcing, the divergence gate, and the archive contract.

Two rules shape this file:

* **JVM-free wherever possible.** Only the tests that genuinely need JCloisterZone are
  marked ``needs_jar`` and skipped when ``~/jcz_spike/JCloisterZone/build/Engine.jar``
  is absent (the jar is 28 MB and deliberately not vendored) — same pattern as the
  oracle's pytest.
* **Anything that touches our engine runs in a SUBPROCESS.** ``CARCASSONNE_FIX_R9`` is
  latched at ``base_deck`` import into a Rust ``OnceLock``, so the R9-on world the
  driver requires cannot be entered by a pytest process that has already imported the
  engine R9-off. A subprocess with the env exported is the only honest way to assert
  anything about it, and it is what the driver itself does.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MATCH_DIR = REPO / "scripts" / "jcz_match"
ORACLE_DIR = REPO / "scripts" / "jcz_oracle"
VENV_PY = REPO / ".venv" / "bin" / "python"
PY = str(VENV_PY if VENV_PY.exists() else sys.executable)
JAR = Path(os.environ.get(
    "JCZ_JAR", os.path.expanduser("~/jcz_spike/JCloisterZone/build/Engine.jar")))

needs_jar = pytest.mark.skipif(
    not JAR.exists(), reason=f"JCZ Engine.jar not built at {JAR} (see SPIKE_REPORT.md)")

for _p in (str(MATCH_DIR), str(ORACLE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _run_engine_script(tmp_path: Path, body: str, timeout: int = 900) -> dict:
    """Run `body` in a fresh interpreter with R9 ON, return its final JSON line.

    The script prints one JSON object as its LAST line; anything before it is noise
    (engine banners, leaf-env chatter) and is echoed on failure.
    """
    script = tmp_path / "probe.py"
    script.write_text(
        "import json, os, sys\n"
        f"sys.path[:0] = [{str(MATCH_DIR)!r}, {str(ORACLE_DIR)!r}, "
        f"{str(REPO / 'scripts')!r}, {str(REPO / 'src')!r}, {str(REPO / 'engine')!r}]\n"
        "os.environ['CARCASSONNE_FIX_R9'] = '1'\n"
        + body)
    env = dict(os.environ, CARCASSONNE_FIX_R9="1")
    proc = subprocess.run([PY, str(script)], capture_output=True, text=True,
                          timeout=timeout, cwd=REPO, env=env)
    assert proc.returncode == 0, f"probe failed:\n{proc.stdout}\n{proc.stderr}"
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    assert lines, f"probe printed nothing:\n{proc.stderr}"
    return json.loads(lines[-1])


# --------------------------------------------------------------------------- #
# 1. coordinate + rotation translation, and THE footgun                        #
# --------------------------------------------------------------------------- #
def test_rotation_is_only_ever_written_as_the_enum_string():
    """``rotation`` is an int in ``action.options`` but the enum string in a
    ``PLACE_TILE`` payload; an int silently no-ops the ply (spike A5). So the WRITE
    side must never produce an int, while the READ side must accept both."""
    from ai_engine import rotation_quarters
    from tile_map import jcz_rotation_quarters, jcz_rotation_str

    for turns in range(4):
        for rot_cw90 in range(4):
            s = jcz_rotation_str(turns, rot_cw90)
            assert isinstance(s, str) and re.fullmatch(r"R(0|90|180|270)", s), s
            q = jcz_rotation_quarters(turns, rot_cw90)
            # round trip: the string we WRITE reads back as the quarters we meant
            assert rotation_quarters(s) == q
            # …and JCZ's other two spellings of the same thing agree
            assert rotation_quarters(q * 90) == q
            assert rotation_quarters(q) == q


def test_rotation_quarters_rejects_nonsense():
    from ai_engine import rotation_quarters
    assert rotation_quarters(None) is None
    assert rotation_quarters("sideways") is None
    assert rotation_quarters(45) is None


def test_coordinates_round_trip_through_the_verified_map():
    from wingedsheep.carcassonne.objects.coordinate import Coordinate
    from tile_map import from_jcz_position, to_jcz_position

    for r0, c0 in ((18, 15), (6, 15)):
        for r in range(r0 - 3, r0 + 4):
            for c in range(c0 - 3, c0 + 4):
                pos = to_jcz_position(Coordinate(row=r, column=c), r0, c0)
                assert from_jcz_position(pos, r0, c0) == (r, c)
        # y grows DOWNWARD (north-negative) — the one sign that is easy to invert
        assert to_jcz_position(Coordinate(row=r0 - 1, column=c0), r0, c0) == [0, -1]


def test_message_kind_is_read_by_presence_not_position():
    """The Java side's exact spellings were unknown when this was written, so the
    client normalises names AND falls back to structure. Both paths are pinned."""
    from ai_engine import (COMMIT, DEPLOY_MEEPLE, PASS, PLACE_TILE, UNKNOWN,
                           message_body, message_kind, pointer_of)

    assert message_kind({"type": "PLACE_TILE"}) == PLACE_TILE
    assert message_kind({"type": "com.jcloisterzone.wsio.message.PlaceTileMessage"}) == PLACE_TILE
    assert message_kind({"className": "DeployMeepleMessage"}) == DEPLOY_MEEPLE
    assert message_kind({"type": "PASS"}) == PASS
    assert message_kind({"type": "COMMIT"}) == COMMIT
    assert message_kind({"type": "CONFIRM"}) == COMMIT
    # structural fallback: an unknown name but an unambiguous shape
    assert message_kind({"type": "Mystery", "tileId": "RFr"}) == PLACE_TILE
    assert message_kind({"type": "Mystery", "meepleId": "m1"}) == DEPLOY_MEEPLE
    assert message_kind({"type": "Mystery"}) == UNKNOWN
    assert message_kind(None) == UNKNOWN
    # payload nested vs inlined must read identically
    nested = {"type": "PLACE_TILE", "payload": {"tileId": "RFr", "rotation": "R90",
                                                "position": [1, 0]}}
    flat = {"type": "PLACE_TILE", "tileId": "RFr", "rotation": "R90", "position": [1, 0]}
    assert message_body(nested) == message_body(flat)
    ptr = {"position": [1, 0], "location": "N", "feature": "City"}
    assert pointer_of({"type": "DEPLOY_MEEPLE", "pointer": ptr}) == ptr
    assert pointer_of({"type": "DEPLOY_MEEPLE", **ptr}) == ptr


# --------------------------------------------------------------------------- #
# 2. deck forcing                                                              #
# --------------------------------------------------------------------------- #
def test_deck_forcing_length_and_multiset(tmp_path):
    """Our shuffled deck maps to a JCZ ``drawOrder`` of the right length and multiset.

    Length is the base game's 72 tiles minus the pre-placed ``fixed_v1`` start tile;
    the multiset must be the image of OUR deck under the certified 32-kind map, with
    no id outside that table (an unmapped kind would be a silent substitution)."""
    got = _run_engine_script(tmp_path, """
import random, collections
import match
from tile_map import load_tile_mapping
from carcassonne_ai import rules_profile
from carcassonne_ai.game_wrapper import Game

prof = rules_profile.activate("fixed_v1")
tile_map = load_tile_mapping()
random.seed(4100001)
game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
board = game.get_init_board()
st = board.state
upcoming = ([st.next_tile] if st.next_tile else []) + list(st.deck)
draw = match.draw_order_for(st, tile_map)
ours = collections.Counter(tile_map[t.description][0] for t in upcoming)
print(json.dumps({
    "n": len(draw), "n_upcoming": len(upcoming),
    "multiset_ok": collections.Counter(draw) == ours,
    "all_known": all(d in {v[0] for v in tile_map.values()} for d in draw),
    "start_tile": st.board[game.start_row][game.start_col].description,
    "r9": rules_profile.r9_env_on(),
}))
""")
    assert got["r9"] is True
    assert got["n"] == got["n_upcoming"] == 71, got     # 72 base tiles - 1 start tile
    assert got["multiset_ok"] and got["all_known"], got
    assert got["start_tile"] == "city_top_straight_road", got


@needs_jar
@pytest.mark.slow
def test_jcz_draws_our_deck_tile_for_tile(tmp_path):
    """JVM: JCZ's ACTUAL draw sequence equals the forced ``drawOrder``.

    Steps 12 plies, always taking JCZ's first offered placement, and compares the
    tile it presents against our list. This is the assertion that the whole
    'no RNG matching anywhere' claim rests on."""
    got = _run_engine_script(tmp_path, f"""
import random
import match
from jcz_driver import JczEngine, is_over, tile_options, wants_confirm, meeple_options
from tile_map import jcz_rotation_quarters, load_tile_mapping
from carcassonne_ai import rules_profile
from carcassonne_ai.game_wrapper import Game

prof = rules_profile.activate("fixed_v1")
tile_map = load_tile_mapping()
random.seed(4100001)
game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
st = game.get_init_board().state
draw = match.draw_order_for(st, tile_map)
start = st.board[game.start_row][game.start_col].description
sid, scw = tile_map[start]
eng = JczEngine(jar={str(JAR)!r})
seen = []
try:
    jst = eng.setup(draw, sid, jcz_rotation_quarters(0, scw) * 90)
    for _ in range(12):
        for _ in range(8):
            if is_over(jst) or tile_options(jst)[0] is not None:
                break
            if wants_confirm(jst):
                jst = eng.commit()
            elif (jst.get("action") or {{}}).get("canPass"):
                jst = eng.pass_()
            else:
                break
        tid, opts = tile_options(jst)
        if tid is None:
            break
        seen.append(tid)
        x, y, deg = sorted(opts)[0]
        jst = eng.place_tile(tid, "R%d" % deg, [x, y])
finally:
    eng.close()
print(json.dumps({{"seen": seen, "want": draw[:len(seen)]}}))
""")
    assert len(got["seen"]) >= 10, got
    assert got["seen"] == got["want"], got


# --------------------------------------------------------------------------- #
# 3. the aiMessage -> our-action inversion                                     #
# --------------------------------------------------------------------------- #
def test_inversion_round_trips_and_unmappable_is_not_an_exception(tmp_path):
    """Forward-map one of OUR legal moves into a JCZ message, invert it, get the same
    action int back — and an impossible message returns ``None`` (which the driver
    turns into ``VOID_UNMAPPABLE``) rather than raising."""
    got = _run_engine_script(tmp_path, """
import random
import match
from carcassonne_ai import action_space as A, rules_profile
from carcassonne_ai.game_wrapper import Game
from tile_map import (JCZ_EDGE_LOCATIONS, JCZ_HALF_EDGES_CW, jcz_location_for,
                      jcz_rotation_quarters, load_tile_mapping, to_jcz_position)

_EDGE_NAME = {v: k for k, v in JCZ_EDGE_LOCATIONS.items()}

prof = rules_profile.activate("fixed_v1")
tile_map = load_tile_mapping()
random.seed(4100077)
game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
board = game.get_init_board()
origin = (game.start_row, game.start_col)
W = game.window_size
rng = random.Random(7)
out = {"tile_round_trips": 0, "meeple_round_trips": 0, "tile_mismatch": [],
       "meeple_mismatch": [], "multi_slot_seen": 0}

for _ in range(40):
    if game.get_game_ended(board, 0) != 0:
        break
    st = board.state
    valid = game.get_valid_moves(board)
    legal = [i for i, v in enumerate(valid) if v]
    if st.phase.value == "tiles" and legal != [A.tile_pass_index(W)]:
        idx = rng.choice([i for i in legal if i < A.tile_action_count(W)])
        dec = game._decode_for(st, board.offset, idx)
        jcz_id, cw = tile_map[st.next_tile.description]
        msg = {"type": "PLACE_TILE", "tileId": jcz_id,
               "rotation": "R%d" % (jcz_rotation_quarters(dec.tile_rotations, cw) * 90),
               "position": to_jcz_position(dec.coordinate, *origin)}
        back, offered = match.invert_tile_message(game, board, tile_map, msg, origin)
        if back == idx:
            out["tile_round_trips"] += 1
        else:
            out["tile_mismatch"].append([idx, back, offered])
    elif st.phase.value == "meeples":
        cand = [i for i in legal if i != A.meeple_pass_index(W)]
        if cand:
            idx = rng.choice(cand)
            dec = game._decode_for(st, board.offset, idx)
            cws = dec.coordinate_with_side
            tile = st.board[cws.coordinate.row][cws.coordinate.column]
            feat, tokens = jcz_location_for(tile, cws.side)
            # ⚠️ JCZ names an edge mask by its REGISTERED CONSTANT ("NE", "_E"), never
            # by sorted letters, and a field is `.`-joined half-edges in JCZ's own
            # clockwise order. Build the fake message with the certified formatters,
            # or the test asserts against a spelling JCZ never emits.
            loc = (".".join(t for t in JCZ_HALF_EDGES_CW if t in tokens)
                   if feat == "Field" else
                   "I" if feat == "Monastery" else
                   _EDGE_NAME[frozenset(tokens)])
            msg = {"type": "DEPLOY_MEEPLE", "meepleId": "m.1", "pointer": {
                "position": to_jcz_position(cws.coordinate, *origin),
                "location": loc, "feature": feat}}
            back, offered = match.invert_meeple_message(game, board, msg)
            # OUR SLOTS ARE FINER than JCZ's: several slots can encode the same
            # deploy, so the contract is "resolves to a slot with the same JCZ key",
            # not "the identical int".
            if back is not None and jcz_location_for(
                    tile, game._decode_for(st, board.offset,
                                           back).coordinate_with_side.side) == (feat, tokens):
                out["meeple_round_trips"] += 1
                if (offered.get("n_matching_slots") or 0) > 1:
                    out["multi_slot_seen"] += 1
            else:
                out["meeple_mismatch"].append([idx, back, offered])
        else:
            idx = A.meeple_pass_index(W)
    else:
        idx = legal[0]
    board, _ = game.get_next_state(board, idx)

# an UNMAPPABLE message: a position no legal move of ours can reach
board2 = game.get_init_board()
random.seed(4100077)
board2 = game.get_init_board()
bad = {"type": "PLACE_TILE", "rotation": "R0", "position": [999, 999]}
a, offered = match.invert_tile_message(game, board2, tile_map, bad, origin)
out["unmappable_is_none"] = a is None
out["unmappable_records_our_set"] = "our_legal_images" in offered
badm = {"type": "DEPLOY_MEEPLE", "pointer": {"position": [0, 0], "location": "N",
                                             "feature": "City"}}
am, offm = match.invert_meeple_message(game, board2, badm)
out["unmappable_meeple_is_none"] = am is None
out["void_class"] = match.VOID_UNMAPPABLE
print(json.dumps(out))
""")
    assert got["tile_round_trips"] >= 8, got
    assert not got["tile_mismatch"], got["tile_mismatch"][:2]
    assert got["meeple_round_trips"] >= 3, got
    assert not got["meeple_mismatch"], got["meeple_mismatch"][:2]
    assert got["unmappable_is_none"] and got["unmappable_records_our_set"], got
    assert got["unmappable_meeple_is_none"], got
    assert got["void_class"] == "VOID_UNMAPPABLE"


# --------------------------------------------------------------------------- #
# 4. the per-ply differ actually catches something                             #
# --------------------------------------------------------------------------- #
def test_injected_partition_divergence_is_classified_REAL(monkeypatch):
    """Perturb ONE ply's partition and the differ must call it — and call it REAL.

    This is the assertion that keeps the D1 dividend honest: if the diff silently
    stopped running, every match would still produce a plausible win rate.
    """
    import match as M
    RD = M.oracle()

    ours = {"City": {frozenset({(0, 0, "N"), (1, 0, "S")})}, "Road": set(), "Field": set()}
    theirs = {"City": {frozenset({(0, 0, "N")}), frozenset({(1, 0, "S")})},
              "Road": set(), "Field": set()}
    monkeypatch.setattr(RD, "our_feature_partition", lambda *a, **k: ours)
    monkeypatch.setattr(RD, "jcz_feature_partition", lambda *a, **k: theirs)

    div = RD.Divergences()
    RD._diff_partitions(div, 7, None, (0, 0), {})
    assert div.counts["CITY_PARTITION"] == 1, dict(div.counts)
    assert "CITY_PARTITION" in RD.REAL
    assert dict(div.real()) == {"CITY_PARTITION": 1}
    # …and a REAL class is what makes the driver void the game.
    assert M.VOID_DIVERGENT == "VOID_DIVERGENT"


def test_injected_score_divergence_is_caught():
    import match as M
    RD = M.oracle()

    class _St:
        scores = [10, 4]

    div = RD.Divergences()
    RD._diff_scores(div, 3, _St(), {"players": [{"points": 10}, {"points": 5}]}, 0, [])
    assert div.counts["SCORE_RUNNING"] == 1, dict(div.counts)
    div2 = RD.Divergences()
    RD._diff_scores(div2, 3, _St(), {"players": [{"points": 10}, {"points": 4}]}, 0, [])
    assert not div2.counts


def test_a_clean_game_is_not_void_but_a_real_class_is():
    """The void rule itself: REAL -> VOID_DIVERGENT, classified-only -> scored."""
    import match as M

    clean = {"void": None, "winner": "champ", "deck_seed": 1, "champ_seat": 0,
             "margin_champ_minus_jcz": 5}
    voided = {"void": M.VOID_DIVERGENT, "deck_seed": 1, "champ_seat": 1,
              "margin_champ_minus_jcz": -3, "winner": "jcz"}
    s = M.summarize([clean, voided])
    assert s["n_scored"] == 1 and s["wins"] == 1
    assert s["voids"] == {M.VOID_DIVERGENT: 1}
    assert s["n_paired_decks"] == 0          # the void seating cannot pair


def test_summarize_pairs_the_two_seatings():
    import match as M
    recs = [
        {"void": None, "winner": "champ", "deck_seed": 11, "champ_seat": 0,
         "margin_champ_minus_jcz": 20},
        {"void": None, "winner": "jcz", "deck_seed": 11, "champ_seat": 1,
         "margin_champ_minus_jcz": -10},
    ]
    s = M.summarize(recs)
    assert s["n_scored"] == 2 and s["win_rate"] == 0.5
    assert s["n_paired_decks"] == 1 and s["paired_margin_mean"] == 5.0


def test_determinism_report_flags_a_divergent_replicate():
    import match as M
    recs = [
        {"deck_seed": 1, "champ_seat": 0, "replicate": 0, "actions": [1, 2, 3],
         "scores": [5, 4]},
        {"deck_seed": 1, "champ_seat": 0, "replicate": 1, "actions": [1, 2, 9],
         "scores": [5, 6]},
        {"deck_seed": 2, "champ_seat": 0, "replicate": 0, "actions": [4], "scores": [1, 1]},
        {"deck_seed": 2, "champ_seat": 0, "replicate": 1, "actions": [4], "scores": [1, 1]},
    ]
    rep = {(r["deck_seed"]): r for r in M.determinism_report(recs)}
    assert rep[1]["identical"] is False and rep[1]["first_diff_ply"] == 2
    assert rep[2]["identical"] is True


def test_cells_are_seat_balanced_and_resume_skips(tmp_path):
    import match as M
    cells = M.build_cells([10, 11], [0, 1], repeats=2, done=set())
    assert len(cells) == 8
    assert cells[:4] == [(10, 0, 0), (10, 1, 0), (11, 0, 0), (11, 1, 0)]
    out = tmp_path / "games.jsonl"
    out.write_text(json.dumps({"deck_seed": 10, "champ_seat": 0, "replicate": 0}) + "\n"
                   + "{not json\n")          # a torn last line from a dirty crash
    done = M.load_done(out)
    assert done == {(10, 0, 0)}
    assert (10, 0, 0) not in M.build_cells([10, 11], [0, 1], 2, done)


# --------------------------------------------------------------------------- #
# 5. the archive contract                                                      #
# --------------------------------------------------------------------------- #
def test_record_serialises_and_replays_bit_identically(tmp_path):
    """A record round-trips through JSONL and its ``(deck_seed, actions)`` replays
    bit-identically through our engine under the same profile — the ``root_replay``
    contract every downstream tool (ev_loss, the deck baseline) already assumes."""
    got = _run_engine_script(tmp_path, f"""
import random
import match
from carcassonne_ai import rules_profile
from carcassonne_ai.game_wrapper import Game

prof = rules_profile.activate("fixed_v1")
seed = 4100123
random.seed(seed)
game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
board = game.get_init_board()
rng = random.Random(99)
actions = []
while game.get_game_ended(board, 0) == 0:
    valid = game.get_valid_moves(board)
    legal = [i for i, v in enumerate(valid) if v]
    a = rng.choice(legal)
    actions.append(a)
    board, _ = game.get_next_state(board, a)
scores = list(board.state.scores)

rec = {{"schema": match.SCHEMA, "deck_seed": seed, "champ_seat": 0, "jcz_seat": 1,
       "replicate": 0, "actions": actions, "scores": scores, "void": None,
       "counts": {{}}, "real": {{}}}}
p = {str(tmp_path)!r} + "/rt.jsonl"
with open(p, "w") as fh:
    fh.write(json.dumps(rec) + "\\n")
loaded = json.loads(open(p).read().splitlines()[0])
rp = match.replay_actions(loaded["deck_seed"], loaded["actions"], "fixed_v1")
print(json.dumps({{"same_dict": loaded == json.loads(json.dumps(rec)),
                  "replay_ok": rp["ok"], "scores": scores,
                  "replay_scores": rp["scores"],
                  "n": len(actions)}}))
""")
    assert got["same_dict"], got
    assert got["replay_ok"] is True, got
    assert got["replay_scores"] == got["scores"], got
    assert got["n"] > 100, got


def test_replay_gate_rejects_a_corrupted_action_stream(tmp_path):
    """The replay check must FAIL loudly on a tampered archive, or it proves nothing."""
    got = _run_engine_script(tmp_path, """
import random, match
from carcassonne_ai import rules_profile
from carcassonne_ai.game_wrapper import Game

prof = rules_profile.activate("fixed_v1")
seed = 4100124
random.seed(seed)
game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
board = game.get_init_board()
rng = random.Random(5)
actions = []
for _ in range(20):
    legal = [i for i, v in enumerate(game.get_valid_moves(board)) if v]
    a = rng.choice(legal)
    actions.append(a)
    board, _ = game.get_next_state(board, a)
good = match.replay_actions(seed, actions, "fixed_v1")     # legal but unfinished
bad = list(actions)
bad[5] = (bad[5] + 1) % 2500
tampered = match.replay_actions(seed, bad, "fixed_v1")
print(json.dumps({"unfinished_ok": good["ok"], "tampered_ok": tampered["ok"],
                  "illegal_at": tampered["illegal_at"]}))
""")
    assert got["unfinished_ok"] is False, got     # not a terminal state -> not ok
    assert got["tampered_ok"] is False, got
    assert got["illegal_at"] is not None, got


# --------------------------------------------------------------------------- #
# 6. the AI client's launch contract                                           #
# --------------------------------------------------------------------------- #
def test_ai_engine_builds_the_classpath_launch(tmp_path, monkeypatch):
    """``java -cp <Engine.jar>:<ai classes> <main class>`` when the shim is built,
    and the plain ``-jar`` engine when it is not — checked WITHOUT starting a JVM."""
    from ai_engine import JczAiEngine

    fake_jar = tmp_path / "Engine.jar"
    fake_jar.write_bytes(b"")
    classes = tmp_path / "classes"
    classes.mkdir()

    obj = JczAiEngine.__new__(JczAiEngine)      # no JVM: exercise _launch_cmd alone
    obj.jar = fake_jar
    obj.ai_classes = classes
    obj.main_class = "com.jcloisterzone.ai.AiEngine"
    cmd = obj._launch_cmd("java")
    assert cmd[:2] == ["java", "-cp"]
    assert str(fake_jar) in cmd[2] and str(classes) in cmd[2]
    assert cmd[3] == "com.jcloisterzone.ai.AiEngine"

    obj.ai_classes = None
    assert obj._launch_cmd("java") == ["java", "-jar", str(fake_jar)]


def test_ai_directives_are_written_exactly_once_and_in_order():
    """``%ai`` is a DIRECTIVE (no reply) and must precede GAME_SETUP; ``%aimove``
    expects exactly one line back. Both are asserted against a fake pipe."""
    from ai_engine import JczAiEngine, PLACE_TILE

    sent: list[str] = []
    replies = [json.dumps({"aiMessage": {"type": "COMMIT"}, "state": {"players": []}}),
               json.dumps({"aiMessage": {"type": "PLACE_TILE", "tileId": "RFr"},
                           "state": {"players": []}})]

    obj = JczAiEngine.__new__(JczAiEngine)
    obj.ai_seats, obj.n_ai_moves = [], 0
    obj._send_raw = sent.append
    obj._recv = lambda: json.loads(replies.pop(0))

    obj.ai_seat(1)
    assert sent == ["%ai 1"] and obj.ai_seats == [1]
    msg, state, skipped = obj.ai_decision((PLACE_TILE,))
    assert sent == ["%ai 1", "%aimove", "%aimove"]
    assert msg["tileId"] == "RFr"
    assert skipped == ["COMMIT"]           # a buffered confirm is absorbed, not hidden
    assert obj.n_ai_moves == 2
