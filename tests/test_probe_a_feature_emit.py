"""PROBE A — bit-exact contract test for the per-component feature emit.

Asserts `flat_leaf_cy.component_features_cy` (the fast emit, from the scalar
leaf's C decomposition) == the Python reference
`scripts/probe_a/component_features.component_features` on many representative
mid/late-game boards, at BOTH POVs, under the production v2.9 closure schedule
AND the DEFAULT schedule. Integer-valued columns must be EXACT; the two float
P(closure) columns are compared to a tight tolerance.

Also a regression guard: the additive feature-emit must NOT perturb the scalar
leaf `flat_virtual_score_v2_cy` (== the Python flat leaf, bit-exact).

Run:  CARCASSONNE_USE_CY_LEAF=1 .venv/bin/python -m pytest tests/test_probe_a_feature_emit.py -q
"""
from __future__ import annotations

import os
# Frozen v2.9 leaf env — set BEFORE importing engine modules (pins the flat path
# + closure schedule the emit is validated under). Mirrors build_dataset's guard.
os.environ.setdefault("CARCASSONNE_V25_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_OPP_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "0")
os.environ.setdefault("CARCASSONNE_V29_MEEPLE_CURVE", "-8,-4,-1,0,2,3,4,5")
os.environ.setdefault("CARCASSONNE_V25_MEEPLE_K", "2.0")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_CY_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_CY_REPR", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")

import random
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
for _p in (str(REPO / "src"), str(REPO / "engine"), str(REPO / "scripts" / "probe_a")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
from wingedsheep.carcassonne.tile_sets.tile_sets import TileSet
from wingedsheep.carcassonne.tile_sets.supplementary_rules import SupplementaryRule
from wingedsheep.carcassonne.utils.action_util import ActionUtil
from wingedsheep.carcassonne.utils.state_updater import StateUpdater

from carcassonne_ai.flat_leaf import decompose, flat_virtual_score_v2
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

import component_features as cf

# Skip cleanly (rather than error) if the .so isn't built on this box.
cy = pytest.importorskip("carcassonne_ai.flat_leaf_cy")

PROD_CLOSURE_P = DEFAULT_CONFIG.closure_p           # {1:0.5, 2:0.2, 3:0.05} (v2.9)
ALT_CLOSURE_P = {1: 1.0, 2: 0.5, 3: 0.25}           # the original v2 schedule


def _rollout(seed: int, target_tiles: int) -> CarcassonneGameState:
    rng = random.Random(seed * 7919 + 13)
    st = CarcassonneGameState(
        players=2, tile_sets=[TileSet.BASE],
        supplementary_rules=[SupplementaryRule.FARMERS],
    )
    rng.shuffle(st.deck)
    placed = 1
    while not st.is_terminated() and placed < target_tiles:
        acts = ActionUtil.get_possible_actions(st)
        if not acts:
            break
        StateUpdater.apply_action_inplace(game_state=st, action=rng.choice(acts))
        placed = sum(1 for row in st.board for t in row if t is not None)
    return st


def _boards(n: int = 60, lo: int = 30, hi: int = 85):
    out = []
    for i in range(n):
        target = lo + (hi - lo) * i // max(1, n - 1)
        out.append(_rollout(seed=2000 + i, target_tiles=target))
    return out


BOARDS = _boards()


def test_boards_are_representative():
    """The bench/test corpus must actually be mid/late-game (else the emit is
    validated on trivial boards)."""
    tiles = [sum(1 for row in b.board for t in row if t is not None) for b in BOARDS]
    assert min(tiles) >= 15
    assert max(tiles) >= 60
    comps = [cf.component_features(b, decompose(b)).shape[0] for b in BOARDS]
    assert max(comps) >= 20  # real structural variety


@pytest.mark.parametrize("closure_p", [PROD_CLOSURE_P, ALT_CLOSURE_P])
@pytest.mark.parametrize("root_player", [0, 1])
def test_emit_bit_exact(root_player, closure_p):
    """Cython emit == Python reference on every board: integer columns EXACT,
    float P columns within tight tolerance, shapes identical."""
    n_int_mismatch = 0
    max_float_abs = 0.0
    for b in BOARDS:
        d = decompose(b)
        xpy = cf.component_features(b, d, root_player=root_player, closure_p=closure_p)
        xcy = cy.component_features_cy(b, root_player, closure_p)
        assert xpy.shape == xcy.shape, (xpy.shape, xcy.shape)
        assert xpy.shape[1] == cf.FEAT_DIM == cy.PROBE_A_FEAT_DIM
        ic = list(cf.INT_COLS)
        if not np.array_equal(xpy[:, ic], xcy[:, ic]):
            n_int_mismatch += 1
        fc = list(cf.FLOAT_COLS)
        if xpy.shape[0]:
            max_float_abs = max(max_float_abs, float(np.max(np.abs(xpy[:, fc] - xcy[:, fc]))))
    assert n_int_mismatch == 0, f"{n_int_mismatch} boards with integer-column mismatch"
    assert max_float_abs <= 1e-6, f"float P columns diverge by {max_float_abs}"


def test_row_order_and_kinds():
    """Rows are grouped city -> road -> farm -> exactly one meeple-econ row, and
    the one-hot kind columns are mutually exclusive and cover every row."""
    for b in BOARDS[:10]:
        d = decompose(b)
        x = cf.component_features(b, d)
        kinds = x[:, :4]
        assert np.all(kinds.sum(axis=1) == 1.0)          # exactly one kind per row
        assert x[-1, cf.C_IS_ECON] == 1.0                # econ row is last
        assert x[:, cf.C_IS_ECON].sum() == 1.0           # exactly one econ row


def test_meeple_ownership_present():
    """The whole point of the enriched vector: at least SOME board carries
    player-relative meeple ownership on real components (self and opp columns
    are not identically zero across the corpus)."""
    tot_self = 0.0
    tot_opp = 0.0
    for b in BOARDS:
        d = decompose(b)
        x = cf.component_features(b, d, root_player=0)
        real = x[x[:, cf.C_IS_ECON] == 0.0]
        tot_self += float(real[:, cf.C_SELF_MEEPLE_W].sum())
        tot_opp += float(real[:, cf.C_OPP_MEEPLE_W].sum())
    assert tot_self > 0.0 and tot_opp > 0.0


def test_pov_swaps_self_opp():
    """Swapping root_player must swap the self/opp meeple columns and the econ
    free-meeple columns (a correctness cross-check on the POV wiring)."""
    for b in BOARDS[:15]:
        d = decompose(b)
        x0 = cf.component_features(b, d, root_player=0)
        x1 = cf.component_features(b, d, root_player=1)
        # real components: self@p0 == opp@p1 and vice versa
        r0 = x0[x0[:, cf.C_IS_ECON] == 0.0]
        r1 = x1[x1[:, cf.C_IS_ECON] == 0.0]
        assert np.array_equal(r0[:, cf.C_SELF_MEEPLE_W], r1[:, cf.C_OPP_MEEPLE_W])
        assert np.array_equal(r0[:, cf.C_OPP_MEEPLE_W], r1[:, cf.C_SELF_MEEPLE_W])
        # econ row free meeples swap
        assert x0[-1, cf.C_ECON_SELF_FREE] == x1[-1, cf.C_ECON_OPP_FREE]
        assert x0[-1, cf.C_ECON_OPP_FREE] == x1[-1, cf.C_ECON_SELF_FREE]


def test_scalar_leaf_unperturbed():
    """Regression: the additive emit must NOT change the scalar leaf output —
    flat_virtual_score_v2_cy stays bit-exact to the Python flat leaf."""
    for b in BOARDS:
        for p in (0, 1):
            assert cy.flat_virtual_score_v2_cy(b, p, DEFAULT_CONFIG) == \
                flat_virtual_score_v2(b, p, DEFAULT_CONFIG)
