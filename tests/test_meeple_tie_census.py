"""MEEPLE-ply tie kill-census contracts — `scripts/tiletie/meeple_tie_census.py`.

Fast unit coverage only: synthetic board fixtures (hand-built 2x2 tile grids) and
at most ONE engine ply. No full-game replay, no production leaf, no census run —
the census itself is a cluster job (see the module docstring for the command).

  (A) GROUPING KEYS   — the three groupings are three DIFFERENT things, and the
                        differences are the census's whole finding:
                        board-level claimed-region (definition of record) merges
                        what the intra-tile key splits, and the afterstate repr
                        key splits what BOTH of them merge.
  (B) DENSE IDS       — undescribed slots stay private; ids are dense + ascending.
  (C) CHAIN VALUES    — `meeple_chain_values` is
                        `mine_disagreements.chain_values(..., "MEEPLE")` plus the
                        retained successor board.
  (D) GAP EMISSION    — the eps piggyback: every row carries the scalar
                        `gap = top1 - top2` (next DISTINCT value), and `gap_cdf`
                        turns those scalars into `phi(eps)`.
  (E) BLIND DISCIPLINE— no outcome field ever crosses `load_games`.
"""
from __future__ import annotations

import os

# The census does not evaluate the production leaf, but `flat_leaf` reads its env
# flags at import; pin the frozen v2.9 knobs so a stray inherited env cannot make
# a decomposition-only test depend on leaf configuration.
for _k, _v in {
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
}.items():
    os.environ.setdefault(_k, _v)

import json  # noqa: E402
import random  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
for _rel in ("scripts/tiletie", "scripts/jcz_mining", "scripts/jcz_match",
             "scripts/human_anchor"):
    _abs = str(REPO / _rel)
    if _abs not in sys.path:
        sys.path.insert(0, _abs)

import meeple_tie_census as MTC  # noqa: E402
from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai.action_space import (  # noqa: E402
    FARMER_SIDES,
    NORMAL_SIDES,
    meeple_normal_base,
    meeple_pass_index,
)
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402
from wingedsheep.carcassonne.objects.meeple_type import MeepleType  # noqa: E402
from wingedsheep.carcassonne.objects.side import Side  # noqa: E402
from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles  # noqa: E402

WINDOW = 25
NBASE = meeple_normal_base(WINDOW)
PASS_IDX = meeple_pass_index(WINDOW)


def _decomp(grid):
    """`flat_leaf.decompose` reads exactly one attribute — `state.board` — so a
    hand-built list-of-lists grid is a complete synthetic board fixture."""
    return flat_leaf.decompose(SimpleNamespace(board=grid))


def _grid(cells, size=3):
    grid = [[None] * size for _ in range(size)]
    for (r, c), tile in cells.items():
        grid[r][c] = tile
    return grid


# =========================================================================== #
# (A) GROUPING KEYS — synthetic board fixtures                                 #
# =========================================================================== #
def test_board_region_merges_two_openings_of_one_city():
    """`city_diagonal_top_right` is `city=[[TOP, RIGHT]]` — one city, two knight
    slots. Both groupings must merge them; only the repr key splits (test below)."""
    tile = base_tiles["city_diagonal_top_right"]
    d = _decomp(_grid({(1, 1): tile}))
    top = MTC.claimed_region_key(d, tile, 1, 1, MeepleType.NORMAL, Side.TOP)
    right = MTC.claimed_region_key(d, tile, 1, 1, MeepleType.NORMAL, Side.RIGHT)
    assert top is not None and top == right
    assert top[0] == "city"
    assert (MTC.intratile_region_key(tile, MeepleType.NORMAL, Side.TOP)
            == MTC.intratile_region_key(tile, MeepleType.NORMAL, Side.RIGHT))


def test_board_region_separates_two_cities_on_one_tile():
    """`city_left_right` is `city=[[LEFT], [RIGHT]]` — two cities that must stay
    distinct under every grouping."""
    tile = base_tiles["city_left_right"]
    d = _decomp(_grid({(1, 1): tile}))
    left = MTC.claimed_region_key(d, tile, 1, 1, MeepleType.NORMAL, Side.LEFT)
    right = MTC.claimed_region_key(d, tile, 1, 1, MeepleType.NORMAL, Side.RIGHT)
    assert left is not None and right is not None and left != right
    assert (MTC.intratile_region_key(tile, MeepleType.NORMAL, Side.LEFT)
            != MTC.intratile_region_key(tile, MeepleType.NORMAL, Side.RIGHT))


def test_board_region_separates_the_four_crossroads_stubs():
    """A crossroads is four `(side, CENTER)` connections — four ROADS, never one."""
    tile = base_tiles["crossroads"]
    d = _decomp(_grid({(1, 1): tile}))
    keys = [MTC.claimed_region_key(d, tile, 1, 1, MeepleType.NORMAL, s)
            for s in (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT)]
    assert all(k is not None and k[0] == "road" for k in keys)
    assert len(set(keys)) == 4


def test_cloister_center_is_its_own_one_tile_region():
    tile = base_tiles["chapel"]
    d = _decomp(_grid({(1, 1): tile}))
    assert (MTC.claimed_region_key(d, tile, 1, 1, MeepleType.NORMAL, Side.CENTER)
            == ("cloister", 1, 1))
    # ...and a CENTER on a tile with no cloister is undescribed, never a region.
    plain = base_tiles["city_left_right"]
    d2 = _decomp(_grid({(1, 1): plain}))
    assert MTC.claimed_region_key(d2, plain, 1, 1, MeepleType.NORMAL, Side.CENTER) is None


def test_undescribed_slot_is_none_under_both_key_functions():
    """`city_left_right` has no TOP feature — the census must never invent one."""
    tile = base_tiles["city_left_right"]
    d = _decomp(_grid({(1, 1): tile}))
    assert MTC.claimed_region_key(d, tile, 1, 1, MeepleType.NORMAL, Side.TOP) is None
    assert MTC.intratile_region_key(tile, MeepleType.NORMAL, Side.TOP) is None


def test_a_knight_and_a_farmer_never_share_a_key():
    """Type-different actions must never collapse, under either grouping."""
    tile = base_tiles["city_diagonal_top_right"]
    d = _decomp(_grid({(1, 1): tile}))
    knight = MTC.claimed_region_key(d, tile, 1, 1, MeepleType.NORMAL, Side.TOP)
    farmer = MTC.claimed_region_key(d, tile, 1, 1, MeepleType.FARMER, Side.BOTTOM_LEFT)
    assert knight is not None and farmer is not None and knight != farmer
    assert (MTC.intratile_region_key(tile, MeepleType.NORMAL, Side.TOP)
            != MTC.intratile_region_key(tile, MeepleType.FARMER, Side.BOTTOM_LEFT))


# --------------------------------------------------------------------------- #
# ⭐ THE DEFINITION-OF-RECORD TEST: the board key merges what the July intra-tile
# key splits. `straight_road` at (1,0) runs its road TOP<->BOTTOM, so its two
# farm connections are the LEFT field (TOP_LEFT / BOTTOM_LEFT slots) and the
# RIGHT field (TOP_RIGHT / BOTTOM_RIGHT). Put a `chapel` — one all-corner field —
# directly above it and the two fields join THROUGH that tile: one board region,
# still two intra-tile groups.
# --------------------------------------------------------------------------- #
def test_board_region_merges_farms_that_the_intratile_key_splits():
    road = base_tiles["straight_road"]
    above = base_tiles["chapel"]

    alone = _decomp(_grid({(1, 0): road}))
    tl_alone = MTC.claimed_region_key(alone, road, 1, 0, MeepleType.FARMER, Side.TOP_LEFT)
    tr_alone = MTC.claimed_region_key(alone, road, 1, 0, MeepleType.FARMER, Side.TOP_RIGHT)
    assert tl_alone != tr_alone, "the two fields are genuinely distinct on a bare board"

    joined = _decomp(_grid({(0, 0): above, (1, 0): road}))
    keys = {s: MTC.claimed_region_key(joined, road, 1, 0, MeepleType.FARMER, s)
            for s in (Side.TOP_LEFT, Side.TOP_RIGHT, Side.BOTTOM_LEFT, Side.BOTTOM_RIGHT)}
    assert len(set(keys.values())) == 1, (
        f"board-level union-find must see ONE field through the neighbour: {keys}")

    intra = {s: MTC.intratile_region_key(road, MeepleType.FARMER, s) for s in keys}
    assert len(set(intra.values())) == 2, (
        "the July intra-tile key is a LOWER BOUND and must still report two groups "
        f"here — that gap is exactly what this census quantifies: {intra}")


def test_the_three_groupings_give_three_different_counts_on_one_decision():
    """The census's headline: on one tied set, repr > intra-tile > board.

    Same fixture as above. The repr key carries `(meeple_type, row, col, side)`
    per placed meeple (`game_wrapper.string_representation`, matching
    `repr_key.rs:88-107`), so every slot is its own arm.
    """
    road = base_tiles["straight_road"]
    joined = _decomp(_grid({(0, 0): base_tiles["chapel"], (1, 0): road}))
    slots = (Side.TOP_LEFT, Side.TOP_RIGHT, Side.BOTTOM_LEFT, Side.BOTTOM_RIGHT)
    actions = [NBASE + len(NORMAL_SIDES) + FARMER_SIDES.index(s) for s in slots]

    board_keys = {a: MTC.claimed_region_key(joined, road, 1, 0, MeepleType.FARMER, s)
                  for a, s in zip(actions, slots)}
    intra_keys = {a: MTC.intratile_region_key(road, MeepleType.FARMER, s)
                  for a, s in zip(actions, slots)}
    repr_keys = {a: f"...meeple@(1,0,{s.value})..." for a, s in zip(actions, slots)}

    assert MTC.n_groups(MTC.dense_group_ids(repr_keys)) == 4     # rust builds 4 arms
    assert MTC.n_groups(MTC.dense_group_ids(intra_keys)) == 2    # July census sees 2
    assert MTC.n_groups(MTC.dense_group_ids(board_keys)) == 1    # truth: ONE region


# =========================================================================== #
# (B) DENSE IDS                                                                #
# =========================================================================== #
def test_dense_group_ids_are_dense_and_ascending():
    ids = MTC.dense_group_ids({7: ("city", 3), 5: ("road", 1), 9: ("city", 3)})
    assert ids == {5: 0, 7: 1, 9: 1}          # numbered in ascending ACTION order
    assert MTC.n_groups(ids) == 2


def test_none_keys_get_private_groups_and_never_merge():
    ids = MTC.dense_group_ids({1: None, 2: None, 3: ("city", 0), 4: ("city", 0)})
    assert MTC.n_groups(ids) == 3
    assert ids[1] != ids[2]
    assert ids[3] == ids[4]


def test_pass_key_never_collides_with_a_placement_or_another_pass_slot():
    ids = MTC.dense_group_ids({1: MTC.PASS_KEY, 2: ("farm", 0), 3: ("farm", 0)})
    assert MTC.n_groups(ids) == 2
    assert ids[1] != ids[2]


# =========================================================================== #
# (C) CHAIN VALUES — fidelity to mine_disagreements' MEEPLE branch              #
# =========================================================================== #
class _StubGame:
    """Enough of `Game` for the enumeration: a legal mask and a successor map."""

    def __init__(self, mask, successors):
        self._mask = np.asarray(mask)
        self._succ = successors

    def get_valid_moves(self, board):
        return self._mask

    def get_next_state(self, board, a):
        return self._succ[int(a)], None


def test_meeple_chain_values_matches_mine_disagreements_meeple_branch():
    import mine_disagreements as MD

    succ = {a: SimpleNamespace(state=SimpleNamespace(tag=a, current_player=1))
            for a in (2, 5, 9)}
    mask = np.zeros(12, dtype=np.int8)
    for a in succ:
        mask[a] = 1
    game = _StubGame(mask, succ)
    board = SimpleNamespace(state=SimpleNamespace(current_player=0))

    def leaf(state):
        return {2: 1.5, 5: 1.5, 9: 0.25}[state.tag]

    want = MD.chain_values(game, board, 0, leaf, "MEEPLE")
    got = MTC.meeple_chain_values(game, board, 0, leaf)
    assert [(a, v, c) for a, v, c, _s in got] == want
    assert [s for _a, _v, _c, s in got] == [succ[2], succ[5], succ[9]]
    # ...and the successor is the SAME object the value was taken from, so the
    # repr key costs no second get_next_state.
    assert got[0][3].state.tag == 2


# =========================================================================== #
# (D) GAP EMISSION — the eps piggyback                                         #
# =========================================================================== #
def test_tie_report_gap_is_the_distance_to_the_next_DISTINCT_value():
    """`gap` is the scalar rung (4) needs; `top2` must skip duplicates of top1."""
    import chain_census as CC

    rep = CC.tie_report([(0, 5.0, [0]), (1, 5.0, [1]), (2, 4.25, [2])])
    assert rep["tie_exact"] is True and rep["tie_size_exact"] == 2
    assert rep["top1"] == 5.0 and rep["top2"] == 4.25
    assert rep["gap"] == pytest.approx(0.75)

    rep2 = CC.tie_report([(0, 5.0, [0]), (1, 5.0, [1])])
    assert rep2["top2"] is None and rep2["gap"] is None   # no distinct runner-up


def test_gap_cdf_counts_untied_rows_below_eps_and_normalises_on_fired_mass():
    rows = [
        {"tie_exact": True, "gap": None},        # already fired
        {"tie_exact": True, "gap": 3.0},         # fired; its gap is not "new mass"
        {"tie_exact": False, "gap": 0.05},
        {"tie_exact": False, "gap": 0.20},
        {"tie_exact": False, "gap": 2.00},
    ]
    cdf = MTC.gap_cdf(rows, eps_points=(0.0, 0.05, 0.25, 3.0))
    assert cdf["n_rows"] == 5 and cdf["n_tied_exact"] == 2
    assert cdf["n_untied_with_gap"] == 3
    assert cdf["gap_min_nonzero"] == pytest.approx(0.05)
    phi = cdf["phi_of_eps"]
    assert phi["0.0"]["new_plies"] == 0
    assert phi["0.05"]["new_plies"] == 1
    assert phi["0.25"]["new_plies"] == 2
    assert phi["3.0"]["new_plies"] == 3
    # rel growth is relative to the ALREADY-FIRED mass (PLAN_eps §2.2's currency)
    assert phi["0.25"]["rel_growth_vs_fired"] == pytest.approx(2 / 2)
    assert phi["0.25"]["fired_total"] == 4
    assert phi["0.25"]["fired_rate"] == pytest.approx(4 / 5)


def test_gap_cdf_on_an_all_tied_slice_is_defined_not_a_zero_division():
    cdf = MTC.gap_cdf([{"tie_exact": True, "gap": None}], eps_points=(0.05,))
    assert cdf["phi_of_eps"]["0.05"]["new_plies"] == 0
    assert cdf["gap_min_nonzero"] is None


# --------------------------------------------------------------------------- #
# One real engine ply: a genuine meeple decision, a stub leaf. Verifies the
# whole per-ply path — decode, decompose, string_representation, tie_report —
# without the production leaf and without replaying a game.
# --------------------------------------------------------------------------- #
def _first_meeple_decision(max_seeds: int = 40):
    """(game, board, seat) at the FIRST meeple decision of a fresh game whose
    option set contains an intra-tile duplicate. One tile ply, no replay."""
    for seed in range(max_seeds):
        random.seed(seed)
        game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
        board = game.get_init_board()
        for a in np.flatnonzero(game.get_valid_moves(board)):
            nxt, _ = game.get_next_state(board, int(a))
            if nxt.state.phase != GamePhase.MEEPLES:
                continue
            legal = [int(x) for x in np.flatnonzero(game.get_valid_moves(nxt))]
            if len(legal) < 3:
                continue
            bk, ik = MTC.meeple_action_keys(game, nxt, legal)
            if (MTC.n_groups(MTC.dense_group_ids(bk)) < len(legal)
                    and MTC.n_groups(MTC.dense_group_ids(ik)) < len(legal)):
                return game, nxt, int(nxt.state.current_player)
    pytest.skip("no duplicate-bearing opening meeple decision in the seed window")


@pytest.fixture(scope="module")
def meeple_decision():
    return _first_meeple_decision()


def test_repr_key_splits_slots_that_the_board_region_merges(meeple_decision):
    """The plan's §1 mechanism claim, on a real board: `tiearb.rs` dedupes arms on
    the afterstate repr, which writes the meeple SIDE — so duplicate slots survive
    as separate arms."""
    game, board, seat = meeple_decision
    legal = [int(x) for x in np.flatnonzero(game.get_valid_moves(board))]
    repr_keys = {}
    for a in legal:
        nxt, _ = game.get_next_state(board, a)
        repr_keys[a] = game.string_representation(nxt)
    board_keys, intra_keys = MTC.meeple_action_keys(game, board, legal)

    n_repr = MTC.n_groups(MTC.dense_group_ids(repr_keys))
    n_intra = MTC.n_groups(MTC.dense_group_ids(intra_keys))
    n_board = MTC.n_groups(MTC.dense_group_ids(board_keys))

    assert n_repr == len(legal), "every legal meeple action is its own afterstate arm"
    assert n_board <= n_intra < n_repr, (n_board, n_intra, n_repr)


def test_meeple_census_ply_emits_gap_and_the_three_groupings(meeple_decision):
    """A constant stub leaf forces a total tie, so the row's composition fields
    are exercised end to end; `gap` is None because there is no distinct runner-up."""
    game, board, seat = meeple_decision
    meta = {"corpus": "t", "game_id": 1, "deck_seed": 1, "ply": 1, "n_plies": 10,
            "action_played": int(np.flatnonzero(game.get_valid_moves(board))[0])}

    row = MTC.meeple_census_ply(game, board, seat, lambda st, s: 1.0, meta=meta)
    assert row["ply_class"] == "MEEPLE"
    assert row["tie_exact"] is True
    assert row["tie_size_exact"] == row["n_legal"]
    assert row["gap"] is None and row["top2"] is None
    assert row["repr_arms"] == row["n_legal"]              # rust would build them all
    assert row["equiv_groups_board"] <= row["equiv_groups_intratile"] < row["repr_arms"]
    assert row["n_nonpass"] == row["n_legal"] - (1 if row["pass_legal"] else 0)
    assert row["played_in_tieset_exact"] is True
    assert set(row["by_eps"]) == {str(e) for e in __import__("chain_census").TIE_EPS_GRID}
    assert json.loads(json.dumps(row)) == row              # the row is jsonl-writable


def test_meeple_census_ply_gap_is_the_top2_distance_under_a_separating_leaf(
        meeple_decision):
    """`gap` must be the distance to the next DISTINCT value — the scalar the eps
    rung reads. A leaf counting placed meeples separates the meeple-PASS action
    (0 placed) from every placement (1 placed) by exactly 1.0."""
    game, board, seat = meeple_decision
    meta = {"corpus": "t", "game_id": 1, "deck_seed": 1, "ply": 1, "n_plies": 10}

    def leaf_counting_meeples(state, s):
        return float(sum(len(m) for m in state.placed_meeples))

    row = MTC.meeple_census_ply(game, board, seat, leaf_counting_meeples, meta=meta)
    assert row["pass_legal"] is True
    assert row["top1"] == pytest.approx(1.0) and row["top2"] == pytest.approx(0.0)
    assert row["gap"] == pytest.approx(1.0)
    assert row["tie_exact"] is True and row["tie_size_exact"] == row["n_legal"] - 1
    assert row["pass_in_tieset"] is False   # the pass is the separated runner-up


# =========================================================================== #
# (E) BLIND DISCIPLINE                                                         #
# =========================================================================== #
def test_no_outcome_field_is_ever_read_from_a_corpus(tmp_path):
    rec = {"game_id": 7, "deck_seed": 42, "actions": [1, 2, 3], "n_plies": 3,
           "score_p0": 90, "score_p1": 108, "sentinel": {"x": 1}}
    p = tmp_path / "games.jsonl"
    p.write_text(json.dumps(rec) + "\n")

    got = MTC.load_games(p, "lbl")
    assert len(got) == 1
    assert set(got[0]) == {"corpus", *MTC._GAME_FIELDS_READ}
    assert "score_p0" not in got[0] and "score_p1" not in got[0]
    assert "sentinel" not in got[0]
    assert not any("score" in f or "sentinel" in f for f in MTC._GAME_FIELDS_READ)


def test_limit_games_is_a_smoke_knob(tmp_path):
    p = tmp_path / "games.jsonl"
    p.write_text("".join(
        json.dumps({"game_id": i, "deck_seed": i, "actions": [1], "n_plies": 1}) + "\n"
        for i in range(5)))
    assert len(MTC.load_games(p, "l", limit=2)) == 2
    assert len(MTC.load_games(p, "l")) == 5


def test_no_row_or_summary_field_names_an_outcome():
    """A structural guard: the emitted schema must contain no win/score/margin
    statistic. Cheap, and it fails loudly if someone widens the instrument."""
    rows = [{"tie_exact": True, "gap": None, "corpus": "a", "repr_arms": 2,
             "equiv_groups_board": 1, "equiv_groups_intratile": 1,
             "tie_size_exact": 2, "phase_bucket": "mid", "pass_in_tieset": False,
             "played_in_tieset_exact": True,
             "by_eps": {"0.0": {"tie": True, "size": 2}}}]
    summary = MTC.build_summary(rows, [], {"a": {"meeple_plies": 3, "tile_plies": 5}},
                                {"a": 1})
    blob = json.dumps(summary).lower()
    # Substrings, not words, so a nested key cannot smuggle one in. ("elo" is
    # deliberately absent from the list — it is a substring of "below".)
    for banned in ("score_p0", "score_p1", "win_rate", "winrate", "_elo", "margin",
                   "playout", "world_mean", "outcome", "result"):
        assert banned not in blob, f"{banned!r} leaked into MEEPLE_CENSUS.json"


# =========================================================================== #
# SUMMARY / BRANCH ARITHMETIC                                                  #
# =========================================================================== #
def _row(**kw):
    base = {"corpus": "a", "tie_exact": True, "gap": None, "repr_arms": 2,
            "equiv_groups_intratile": 1, "equiv_groups_board": 1, "tie_size_exact": 2,
            "phase_bucket": "mid", "pass_in_tieset": False,
            "played_in_tieset_exact": True,
            "by_eps": {"0.0": {"tie": True, "size": 2}}}
    base.update(kw)
    return base


def test_summary_splits_duplicates_from_genuinely_tied():
    rows = [
        _row(repr_arms=3, equiv_groups_board=1),                  # pure duplicate
        _row(repr_arms=3, equiv_groups_board=2),                  # mixed
        _row(repr_arms=2, equiv_groups_board=2),                  # pure distinct
        _row(tie_exact=False, gap=0.5, repr_arms=1, equiv_groups_board=1),
    ]
    s = MTC.meeple_group_summary(rows, {"meeple_plies": 8, "tile_plies": 10}, 2)
    assert s["split"] == {"n_tied": 3, "pure_duplicate": 1, "mixed": 1,
                          "pure_distinct": 1, "single_arm": 0}
    assert s["phi_meeple_ply"]["k"] == 3 and s["phi_meeple_ply"]["n"] == 4
    assert s["phi_meeple_move"]["n"] == 10
    assert s["fired_meeple_plies_per_game"] == pytest.approx(3 / 2)
    assert s["arbitrable_plies_per_game"] == pytest.approx(2 / 2)
    assert s["arbitrable_fraction"] == pytest.approx(2 / 3)
    assert s["redundant_arms"]["mean_repr_minus_board"] == pytest.approx((2 + 1 + 0) / 3)


def test_branch_hint_fires_M_DEAD_below_the_supply_bar():
    hint = MTC._branch_hint(1.2, 3.0, 0.4, {"a": 0.16, "b": 0.17})
    assert hint["branch"] == "M-DEAD"


def test_branch_hint_fires_M_DUP_BOUND_when_duplicates_dominate():
    hint = MTC._branch_hint(9.0, 20.0, 0.30, {"a": 0.16})
    assert hint["branch"] == "M-DUP-BOUND"


def test_branch_hint_fires_M_PRICE_only_when_both_conjuncts_hold():
    assert MTC._branch_hint(9.0, 20.0, 0.55, {"a": 0.16})["branch"] == "M-PRICE"
    assert MTC._branch_hint(5.0, 20.0, 0.55, {"a": 0.16})["branch"] == "M-MARGINAL"


def test_branch_hint_voids_when_the_two_corpora_disagree_by_more_than_2x():
    hint = MTC._branch_hint(9.0, 20.0, 0.55, {"champ449": 0.10, "tiearb2_850": 0.30})
    assert hint["branch"] == "M-VOID"


def test_resolve_corpora_accepts_label_equals_path_and_bare_paths():
    got = MTC.resolve_corpora("champ449=/tmp/a.jsonl,/tmp/b.jsonl")
    assert got[0][0] == "champ449" and got[0][1] == Path("/tmp/a.jsonl")
    assert got[1][0] == "b" and got[1][1] == Path("/tmp/b.jsonl")
    assert [l for l, _p in MTC.resolve_corpora(None)] == ["champ449", "tiearb2_850"]
