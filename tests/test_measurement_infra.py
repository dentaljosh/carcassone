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


# ---------------------------------------------------------------------------
# (E) MEEPLE-SLOT DUPLICATION CENSUS — the counting logic.
#
# Drives real base-deck tiles through the census' `dense_groups`, which is a thin
# reuse of android_bridge.feature_groups + _renumber_groups (the grouping of record).
# The contract under test: sides that open onto ONE connected on-tile feature share
# a group id (interchangeable actions); separate features never do.
# ---------------------------------------------------------------------------

sys.path.insert(0, str(REPO / "android" / "app" / "src" / "main" / "python"))
import meeple_dedup_census as MDC              # noqa: E402


def _tile(name):
    from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles
    return base_tiles[name]


def _stats_for(tile_name, sides):
    """decision_stats for a synthetic decision offering `sides` on one base-deck tile."""
    return MDC.decision_stats(MDC.dense_groups(_tile(tile_name), sides))


def test_two_opening_city_is_a_2way_duplicate():
    """`city_diagonal_top_right` has city=[[top, right]] — ONE city, two openings."""
    st = _stats_for("city_diagonal_top_right", ["top", "right"])
    assert st["n_actions"] == 2
    assert st["n_distinct_features"] == 1
    assert st["n_redundant"] == 1
    assert st["has_duplicate"] is True
    assert st["max_group_size"] == 2
    assert st["size_hist"] == {2: 1}


def test_two_separate_cities_are_not_duplicates():
    """`city_left_right` has city=[[left], [right]] — TWO cities that must stay distinct."""
    st = _stats_for("city_left_right", ["left", "right"])
    assert st["n_actions"] == 2
    assert st["n_distinct_features"] == 2
    assert st["n_redundant"] == 0
    assert st["has_duplicate"] is False
    assert st["max_group_size"] == 1
    assert st["size_hist"] == {1: 2}


def test_crossroads_four_road_stubs_stay_four_features():
    """Four (side, CENTER) connections are four dead-end roads, not one 4-way group."""
    st = _stats_for("crossroads", ["top", "right", "bottom", "left"])
    assert st["n_distinct_features"] == 4
    assert st["has_duplicate"] is False


def test_full_city_is_a_4way_duplicate():
    st = _stats_for("full_city_with_shield", ["top", "right", "bottom", "left"])
    assert st["n_distinct_features"] == 1
    assert st["n_redundant"] == 3
    assert st["max_group_size"] == 4


def test_farm_sides_of_one_field_are_duplicates():
    """`city_narrow` farms=[[top_left, top_right], [bottom_left, bottom_right]] — two fields."""
    st = _stats_for("city_narrow",
                    ["top_left", "top_right", "bottom_left", "bottom_right"])
    assert st["n_distinct_features"] == 2
    assert st["n_redundant"] == 2
    assert st["size_hist"] == {2: 2}


def test_undescribed_side_gets_a_private_group():
    """A side the tile model does not describe must never be merged with another."""
    st = _stats_for("full_city_with_shield", ["top", "right", "top_left", "bottom_left"])
    # top+right share the city; the two farm sides are undescribed -> private each.
    assert st["n_distinct_features"] == 3
    assert st["n_redundant"] == 1


def test_chose_duplicate_flag_tracks_the_taken_action():
    groups = MDC.dense_groups(_tile("city_diagonal_top_right"), ["top", "right"])
    assert MDC.decision_stats(groups, chosen_group=groups[0])["chose_duplicate"] is True
    solo = MDC.dense_groups(_tile("city_left_right"), ["left", "right"])
    assert MDC.decision_stats(solo, chosen_group=solo[0])["chose_duplicate"] is False


def test_accumulator_merge_is_additive():
    a, b = MDC._new_acc(), MDC._new_acc()
    st = _stats_for("city_diagonal_top_right", ["top", "right"])
    MDC._record(a, st, "early", passed=False, pass_legal=True)
    MDC._record(b, st, "early", passed=False, pass_legal=True)
    MDC.merge(a, b)
    assert a["decisions"] == 2 and a["decisions_with_dup"] == 2
    assert a["actions_nonpass"] == 4 and a["distinct_features"] == 2
    assert a["phase_early"]["decisions"] == 2
    assert MDC.summarize(a)["pct_actions_redundant_nonpass"] == 50.0
