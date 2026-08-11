"""Fast guards for the G1 lockstep fuzz driver (`scripts/rustport/lockstep_fuzz.py`).

The gate itself is 10^4 games on the laptop; this is the always-on subset that
keeps the driver honest: a handful of games must run clean in lockstep, the
wall-biased policy must actually drive play into the `board[-1]` wrap sites, and
the deck seeding must be the `root_replay` contract (so a fuzz reproducer
replays through the normal tooling).
"""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "src", REPO / "engine", REPO / "scripts" / "measurement_infra",
           REPO / "scripts" / "rustport"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

carc_rs = pytest.importorskip("carc_rs", reason="build with `maturin develop --release`")

os.environ["CARCASSONNE_WINDOW_AUDIT"] = "1"   # must precede game_wrapper import

import lockstep_fuzz as lf  # noqa: E402

from root_replay import replay_actions  # noqa: E402


def _run(idx: int, mode: str) -> dict:
    return lf.fuzz_game({"deck_seed": lf.FUZZ_SEED_BASE + idx,
                         "policy_seed": 5_000_000 + idx,
                         "mode": mode, "max_plies": 400})


@pytest.mark.parametrize("mode", ["uniform", "wall"])
def test_fuzz_games_run_clean_in_lockstep(mode):
    for idx in range(3):
        r = _run(idx, mode)
        assert r["mismatch"] is None, r["mismatch"]
        assert r["status"] in ("ok", "window_overflow"), r["status"]
        assert r["plies"] > 50
        assert r["compared"] == r["plies"] + 1


def test_fuzz_is_deterministic_given_the_two_seeds():
    a, b = _run(7, "uniform"), _run(7, "uniform")
    for k in ("plies", "terminal_scores", "status", "min_row", "max_col"):
        assert a[k] == b[k]


def test_wall_policy_reaches_the_negative_index_wrap_sites():
    """Row 0 is where the three direct `board[r][c]` sites read row -1 -> row 34.
    The start tile sits at row 6, so this is reachable; the wall policy must do
    it in every game, and must sprawl wider than the 25-wide window (which is
    what makes actions fall out of it)."""
    touched, dropped = 0, 0
    for idx in range(4):
        r = _run(idx, "wall")
        assert r["min_row"] == 0, r["min_row"]
        touched += bool(r["placements_row0"])
        dropped += r["plies_with_dropped_legal"]
    assert touched == 4
    assert dropped > 0, "wall policy never pushed a legal action out of the window"


def test_matched_error_games_are_pass_with_flag():
    """The two refusal classes the 10^4 fuzz found, pinned as regressions.

    97000006104 — every legal action falls outside the 25x25 window at ply 84
    (Python raises WindowOverflowError; Rust reports n_overflow == n_total).
    97000001314 — a tile on the LAST COLUMN makes `FarmUtil.farm_for_position`
    index `board[..][35]`, so the CPython engine itself raises IndexError at
    ply 79; Rust must refuse with the same class (its `py_index` panic).
    Both are PASS-with-flag: no state mismatch, error parity on the same ply.
    """
    r = lf.fuzz_game({"deck_seed": 97000006104, "policy_seed": 5006104,
                      "mode": "wall", "max_plies": 400})
    assert r["mismatch"] is None
    assert r["status"] == "window_overflow"
    assert r["window_overflow"]["ply"] == 84
    assert r["window_overflow"]["n_total"] == r["window_overflow"]["n_overflow"] > 0
    assert r["window_overflow"]["rust_mask_counts"] == [
        r["window_overflow"]["n_total"], r["window_overflow"]["n_overflow"]]

    r = lf.fuzz_game({"deck_seed": 97000001314, "policy_seed": 5001314,
                      "mode": "wall", "max_plies": 400})
    assert r["mismatch"] is None
    assert r["status"] == "engine_error"
    assert r["engine_error"]["ply"] == 79
    assert r["engine_error"]["error_class"] == "IndexError"
    assert "IndexError:" in r["engine_error"]["rust_error"]
    assert r["engine_error"]["last_tile"][1] == 34   # the last column


def test_seeding_matches_root_replay_contract():
    """A fuzz game's (deck_seed, actions) must replay through `root_replay`, the
    normal reproducer path — i.e. the driver's own seeding is the same one."""
    r = _run(11, "wall")
    # re-derive the action sequence by re-running (actions are only kept on flags)
    random.seed(r["deck_seed"])
    from carcassonne_ai.game_wrapper import Game
    import numpy as np

    game = Game(enable_legal_moves_cache=False)
    board = game.get_init_board()
    rng = random.Random(r["policy_seed"])
    actions = []
    while not board.state.is_terminated():
        mask = np.asarray(game.get_valid_moves(board), dtype=bool)
        off = board.offset
        tile_pass = off.size * off.size * lf.N_ROTATIONS
        a = int(lf._choose(rng, np.flatnonzero(mask).tolist(), "wall",
                           board.state.phase.value, off, tile_pass))
        actions.append(a)
        board, _ = game.get_next_state(board, a)
    assert len(actions) == r["plies"]

    _game2, board2 = replay_actions(r["deck_seed"], actions, len(actions))
    assert [int(x) for x in board2.state.scores] == r["terminal_scores"]
    ms = carc_rs.MirrorState.from_seed(str(r["deck_seed"]))
    for a in actions:
        ms.advance(int(a))
    assert list(ms.scores()) == r["terminal_scores"]
