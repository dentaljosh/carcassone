"""C7 wave-2 leaf terms — Term R (meeple-return liquidity) + Term F (farm
majority-flip). Structural + property gate for the flat/object reference paths.

Covers (design measurement/classical_search/C7_LEAF_TERMS_DESIGN.md §11.4 mitigations):
  * OFF-inertness: both knobs 0.0 == bit-identical champion (int leaf), object + flat.
  * R-requires-curve: v29_meeple_return_k != 0 with curve None raises (flat + object).
  * antisymmetry: term(player) == -term(opp) EXACTLY (m, free_d, step, ramp all odd).
  * road_root_open_n == the engine _open_road_positions (Term R's only new Decomp field).
  * int == round(float) for the ON configs (the int/float leaves differ only by round).

Object-vs-flat 3-way ON bit-exactness lives in the reconcile gates + test_c7_object_flat.
The cy .so need NOT support C7 for these (a stale .so falls back to pure-Python flat).
"""
from __future__ import annotations

import os

os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import dataclasses as dc  # noqa: E402
import random  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai import leaf_v29  # noqa: E402
from carcassonne_ai import virtual_score_v2 as vs2  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.virtual_score_v2 import (  # noqa: E402
    LeafConfig,
    _open_road_positions,
    _v29_active,
    _v29_flat_eligible,
    virtual_score_v2,
)
from wingedsheep.carcassonne.objects.coordinate_with_side import CoordinateWithSide
from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.objects.terrain_type import TerrainType
from wingedsheep.carcassonne.utils.road_util import RoadUtil

CURVE = (-8.0, -4.0, -1.0, 0.0, 2.0, 3.0, 4.0, 5.0)
CHAMP = LeafConfig(closure_p={1: 0.5, 2: 0.2, 3: 0.05}, bonus_cap=8.0,
                   opp_bonus_cap=8.0, meeple_k=2.0, v29_meeple_curve=CURVE)
R05 = dc.replace(CHAMP, v29_meeple_return_k=0.5)
R10 = dc.replace(CHAMP, v29_meeple_return_k=1.0)
F05 = dc.replace(CHAMP, v29_farm_flip_k=0.5)
RF = dc.replace(CHAMP, v29_meeple_return_k=1.0, v29_farm_flip_k=0.5)
_CARD = (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT)


def _states(n_seeds=40, plies=130, every=4, seed_base=13):
    """Random-play snapshots skewed toward mid+endgame (Term F needs finished
    adjacent cities, which appear late)."""
    out = []
    for s in range(n_seeds):
        g = Game(enable_legal_moves_cache=True)
        b = g.get_init_board()
        rng = random.Random(9000 + s)
        for ply in range(plies):
            if g.get_game_ended(b, 0) != 0.0:
                break
            legal = np.flatnonzero(g.get_valid_moves(b))
            if legal.size == 0:
                break
            b, _ = g.get_next_state(b, int(rng.choice(legal.tolist())))
            if ply % every == 0:
                out.append(b.state)
        out.append(b.state)
    return [s for s in out if s.players == 2]


STATES = _states()


def test_have_states():
    assert len(STATES) > 200


# --------------------------------------------------------------- predicates
def test_predicates_route_flat():
    assert _v29_active(R10) and _v29_active(F05) and _v29_active(RF)
    # curve/return/flip stay flat-eligible; object-only terms do not
    assert _v29_flat_eligible(R10) and _v29_flat_eligible(F05) and _v29_flat_eligible(RF)
    assert not _v29_flat_eligible(dc.replace(RF, v29_util_tanh_t=8.0))
    assert not _v29_flat_eligible(dc.replace(RF, v29_punish_k=1.0))
    assert not _v29_flat_eligible(dc.replace(RF, v29_farm_access_k=1.0))


# ----------------------------------------------------------- R requires curve
def test_r_requires_curve_flat():
    st = STATES[0]
    d = flat_leaf.decompose(st)
    with pytest.raises(ValueError):
        flat_leaf.flat_return_term(st, 0, d, dc.replace(R10, v29_meeple_curve=None))


def test_r_requires_curve_object():
    st = STATES[0]
    with pytest.raises(ValueError):
        leaf_v29._return_liquidity(st, 0, dc.replace(R10, v29_meeple_curve=None))


# ------------------------------------------------------------- OFF-inertness
def test_off_inert_flat_int():
    off = dc.replace(CHAMP, v29_meeple_return_k=0.0, v29_farm_flip_k=0.0)
    mism = 0
    for st in STATES:
        for p in (0, 1):
            if flat_leaf.flat_virtual_score_v2(st, p, CHAMP) != flat_leaf.flat_virtual_score_v2(st, p, off):
                mism += 1
    assert mism == 0


def test_off_inert_object_int():
    """The object path (USE_FLAT_LEAF off) with both knobs 0.0 == champion object leaf."""
    saved = flat_leaf.USE_FLAT_LEAF
    off = dc.replace(CHAMP, v29_meeple_return_k=0.0, v29_farm_flip_k=0.0)
    try:
        flat_leaf.USE_FLAT_LEAF = False
        mism = 0
        for st in STATES[:120]:
            for p in (0, 1):
                if virtual_score_v2(st, p, CHAMP) != virtual_score_v2(st, p, off):
                    mism += 1
        assert mism == 0
    finally:
        flat_leaf.USE_FLAT_LEAF = saved


# --------------------------------------------------------------- antisymmetry
def test_r_antisymmetry_flat():
    worst = 0.0
    nz = 0
    for st in STATES:
        d = flat_leaf.decompose(st)
        a = flat_leaf.flat_return_term(st, 0, d, R10)
        b = flat_leaf.flat_return_term(st, 1, d, R10)
        worst = max(worst, abs(a + b))
        nz += a != 0.0
    assert worst == 0.0
    assert nz > 50  # Term R fires broadly (returnable meeples common)


def test_f_antisymmetry_flat():
    worst = 0.0
    nz = 0
    for st in STATES:
        d = flat_leaf.decompose(st)
        a = flat_leaf.flat_farm_flip_term(st, 0, d, F05)
        b = flat_leaf.flat_farm_flip_term(st, 1, d, F05)
        worst = max(worst, abs(a + b))
        nz += a != 0.0
    assert worst == 0.0
    assert nz >= 3  # sparse (needs contested fields w/ finished cities), but must fire


# ------------------------------------------------- road_root_open_n structural
def test_road_open_n_matches_engine():
    """flat decompose's road_root_open_n == the engine _open_road_positions for every
    road component (Term R's only new decomposition field)."""
    checks = mism = 0
    for st in STATES:
        d = flat_leaf.decompose(st)
        seen_roots = set()
        for r in range(len(st.board)):
            for c in range(len(st.board[0])):
                tile = st.board[r][c]
                if tile is None:
                    continue
                for side in _CARD:
                    if tile.get_type(side) != TerrainType.ROAD:
                        continue
                    root = d.road_side_root.get((r, c, side))
                    if root is None or root in seen_roots:
                        continue
                    seen_roots.add(root)
                    road = RoadUtil.find_road(
                        game_state=st,
                        road_position=CoordinateWithSide(Coordinate(r, c), side),
                    )
                    truth = _open_road_positions(st, road)
                    checks += 1
                    if d.road_root_open_n[root] != truth:
                        mism += 1
    assert checks > 100
    assert mism == 0


# ------------------------------------------- object == flat (term floats, exact)
def test_object_flat_term_floats_bit_exact():
    """The object-path term floats == the flat-path term floats EXACTLY (both fsum the
    same contribution multiset). Pre-round, so this catches sub-integer divergence that
    int-rounding would hide."""
    r_checked = f_checked = 0
    for st in STATES:
        d = flat_leaf.decompose(st)
        for p in (0, 1):
            opp = 1 - p
            obj_r = leaf_v29._return_liquidity(st, p, R10) - leaf_v29._return_liquidity(st, opp, R10)
            flat_r = flat_leaf.flat_return_term(st, p, d, R10)
            assert obj_r == flat_r, f"Term R object {obj_r!r} != flat {flat_r!r}"
            r_checked += 1
            obj_f = leaf_v29._farm_flip_term(st, p, opp, F05)
            flat_f = flat_leaf.flat_farm_flip_term(st, p, d, F05)
            assert obj_f == flat_f, f"Term F object {obj_f!r} != flat {flat_f!r}"
            f_checked += 1
    assert r_checked > 400 and f_checked > 400


def test_object_flat_leaf_int_bit_exact():
    """The full int leaf: object path (USE_FLAT_LEAF off) == flat path, canonical sum,
    for +R / +F / +both. Mirrors test_v29_flat_curve's object-vs-flat gate."""
    saved_flat = flat_leaf.USE_FLAT_LEAF
    saved_canon = vs2.CANONICAL_BONUS_SUM
    try:
        vs2.CANONICAL_BONUS_SUM = True
        for cfg in (R10, F05, RF):
            for st in STATES:
                for p in (0, 1):
                    flat_leaf.USE_FLAT_LEAF = True
                    fv = virtual_score_v2(st, p, cfg)
                    flat_leaf.USE_FLAT_LEAF = False
                    ov = virtual_score_v2(st, p, cfg)
                    assert fv == ov, f"flat {fv} != object {ov} for {cfg}"
    finally:
        flat_leaf.USE_FLAT_LEAF = saved_flat
        vs2.CANONICAL_BONUS_SUM = saved_canon


# --------------------------------------------------------- int == round(float)
def test_int_equals_round_float_on_configs():
    mism = 0
    for st in STATES:
        for p in (0, 1):
            for cfg in (R05, R10, F05, RF):
                i = flat_leaf.flat_virtual_score_v2(st, p, cfg)
                fl = flat_leaf.flat_virtual_score_v2_float(st, p, cfg)
                if i != int(round(fl)):
                    mism += 1
    assert mism == 0
