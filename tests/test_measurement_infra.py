"""Contracts for scripts/measurement_infra/ (promoted from the post-search-residual pilot, CL-035).

  (A) REPLAY is lossless     — (deck_seed, actions, ply) reconstructs the exact in-play board.
  (B) SNAPSHOT == STANDALONE — snapshot-at-L child N-distribution == a fresh L-sim search, every L.
  (C) TAGGING                — top2_q_gap derived from a snapshot matches a direct tag; sane values.
  (D) FROZEN v2.9 cfg        — frozen_v29_cfg() builds and asserts the production config_hash.

Self-contained: generates a short HeuristicMCTS game inline (no committed data needed).
"""
from __future__ import annotations
import os
# frozen v2.9 leaf env — set BEFORE importing engine modules (pins the flat-leaf path)
os.environ.setdefault("CARCASSONNE_V25_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_OPP_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "0")
os.environ.setdefault("CARCASSONNE_V29_MEEPLE_CURVE", "-8,-4,-1,0,2,3,4,5")
os.environ.setdefault("CARCASSONNE_V25_MEEPLE_K", "2.0")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_CY_REPR", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")

import random
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))

import snapshot as SNAP                       # noqa: E402
import tagging as TAG                         # noqa: E402
from root_replay import replay_actions        # noqa: E402

SIMS = 30                                     # small for test speed; equivalence is sims-independent
DECK_SEED = 7_654_321
CHECK_PLY = 24


@pytest.fixture(scope="module")
def short_game():
    """Play a short HeuristicMCTS(SIMS) game; record (deck_seed, actions) + an in-play checksum."""
    cfg = SNAP.frozen_v29_cfg()
    agent = SNAP.make_heuristic_agent(SIMS, cfg, seed=0)
    random.seed(DECK_SEED)
    board = agent.game.get_init_board()
    agent.rng = random.Random(DECK_SEED ^ 0xABCDEF)
    actions, check_str = [], None
    for step in range(1, 60):
        if agent.game.get_game_ended(board, board.state.current_player) != 0.0:
            break
        agent.clear()
        a = int(agent.best_action(board))
        actions.append(a)
        board, _ = agent.game.get_next_state(board, a)
        if step == CHECK_PLY:
            check_str = agent.game.string_representation(board)
    return {"deck_seed": DECK_SEED, "actions": actions, "check_str": check_str, "cfg": cfg}


def test_replay_lossless(short_game):
    """(A) reconstruct the CHECK_PLY board purely from (deck_seed, actions) — must match in-play."""
    game, board = replay_actions(short_game["deck_seed"], short_game["actions"], CHECK_PLY)
    assert game.string_representation(board) == short_game["check_str"]


def test_snapshot_equals_standalone(short_game):
    """(B) one snapshot search == standalone searches at every level."""
    cfg = short_game["cfg"]
    levels = [10, 20, 30]
    _, board = replay_actions(short_game["deck_seed"], short_game["actions"], CHECK_PLY)
    res = SNAP.verify_equivalence(
        make_agent=lambda sims, seed: SNAP.make_heuristic_agent(sims, cfg, seed=seed),
        board=board, levels=levels, mcts_seed=123)
    for L in levels:
        assert res[L]["match"], f"snapshot != standalone at L={L}: {res[L]}"
        assert res[L]["sum_n_snap"] == res[L]["sum_n_ref"] == L


def test_tagging_consistent(short_game):
    """(C) top2_q_gap from a snapshot == a direct tag of the same search; values are sane."""
    cfg = short_game["cfg"]
    _, board = replay_actions(short_game["deck_seed"], short_game["actions"], CHECK_PLY)
    agent = SNAP.make_heuristic_agent(60, cfg, seed=0)
    agent.clear(); agent.rng = random.Random(123)
    snaps, _ = SNAP.snapshot_search(agent, board, [30, 60])
    tags = TAG.tag_from_snaps(snaps, level=30)
    assert tags["top2_q_gap"] >= 0.0
    assert 0.0 <= tags["top_share"] <= 1.0
    assert tags["n_visited"] >= 1
    # snapshot-derived tag matches stats computed directly off the same levelmap
    direct = TAG._stats({a: (n, q) for a, (n, q) in snaps[30].items()})
    assert abs(direct["top2_q_gap"] - tags["top2_q_gap"]) < 1e-9


def test_frozen_v29_cfg_hash():
    """(D) the frozen-leaf helper builds + asserts the production config_hash (no raise)."""
    cfg = SNAP.frozen_v29_cfg()
    assert cfg is not None


def test_best_action_rule(short_game):
    """best_action_from picks argmax(Q,N); ties -> lowest action id."""
    lm = {5: (10, 0.5), 9: (10, 0.5), 2: (3, 0.9)}     # 2 has highest Q -> chosen
    assert SNAP.best_action_from(lm)[0] == 2
    lm2 = {5: (10, 0.5), 9: (12, 0.5)}                 # tie Q -> higher N (9)
    assert SNAP.best_action_from(lm2)[0] == 9
    lm3 = {9: (10, 0.5), 5: (10, 0.5)}                 # tie Q and N -> lowest aid (5)
    assert SNAP.best_action_from(lm3)[0] == 5
