"""F6 soft cap on the closure-anticipation bonus (CL-063).

The v2.9 leaf HARD-caps the closure bonus: `_capped(x, c) = min(x, c)`. F6 replaces the
clamp with a SOFT cap that gives LINEAR credit above the cap:

    soft(x, c, s) = x               if x <= c
                    c + s*(x - c)   if x >  c

s=0.0 reproduces the hard cap BIT-EXACTLY (routes through the unchanged `_capped`/min
path); s=1.0 is uncapped (identity). Two independently-controllable slopes,
`soft_cap_slope` (SELF, the primary target) and `opp_soft_cap_slope` (OPP).

Gates here:
  * CONTRACT — soft(x,c,s) matches the closed form; s=0 == min; s=1 == identity.
  * OFF bit-exactness — slope 0.0 leaves the object/flat/cy leaf byte-identical to the
    hard-cap champion (int AND float), across a battery of states.
  * ON 3-path parity — object == flat(py) == cy under canonical fsum, for a couple of
    slopes, on states where the self bonus GENUINELY EXCEEDS the cap (branch fires).
  * NON-VACUITY — the soft cap actually changes the leaf on overflow states (else "OFF
    == ON" would pass trivially); and s=1.0 == an uncapped leaf.

Frozen-hash invariance (a36d2e15 / 6dfffd57 / 158f17ff / 7fc930b8 unchanged) is proved
by tests/release/test_factory_manifest.py + test_frozen_substrates.py — the slopes are
default-off-excluded from every hash dialect.
"""
from __future__ import annotations

import os

os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_CY_LEAF", "1")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import dataclasses as dc  # noqa: E402
import random  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai import virtual_score_v2 as vs2  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.virtual_score_v2 import (  # noqa: E402
    LeafConfig,
    _capped,
    _soft_capped,
    virtual_score_v2,
)

flat_leaf_cy = pytest.importorskip("carcassonne_ai.flat_leaf_cy")

CURVE125 = (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25)

# Low cap + generous closure schedule so the SELF/OPP bonus routinely OVERFLOWS the cap
# and the soft branch is actually exercised. Plain (no curve) and champion-curve variants.
_SCHED = {1: 1.0, 2: 0.5, 3: 0.25}
PLAIN_HARD = LeafConfig(closure_p=dict(_SCHED), bonus_cap=1.0, opp_bonus_cap=1.0)
CURVE_HARD = LeafConfig(closure_p=dict(_SCHED), bonus_cap=1.0, opp_bonus_cap=1.0,
                        meeple_k=2.0, v29_meeple_curve=CURVE125)


def _states(n_seeds=45, plies=140, every=3, seed_base=7000):
    out = []
    for s in range(n_seeds):
        g = Game(enable_legal_moves_cache=True)
        b = g.get_init_board()
        rng = random.Random(seed_base + s)
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


# --------------------------------------------------------------------------- #
# CONTRACT                                                                     #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("x,c,s,expected", [
    (3.0, 5.0, 0.5, 3.0),    # below cap -> identity regardless of slope
    (5.0, 5.0, 0.3, 5.0),    # at cap -> identity
    (10.0, 5.0, 0.0, 5.0),   # slope 0 -> hard clamp
    (10.0, 5.0, 1.0, 10.0),  # slope 1 -> uncapped
    (10.0, 5.0, 0.5, 7.5),   # slope 0.5 -> cap + 0.5*(x-cap)
    (12.0, 8.0, 0.25, 9.0),  # 8 + 0.25*4
])
def test_soft_cap_closed_form(x, c, s, expected):
    assert _soft_capped(x, c, s) == expected


def test_soft_cap_slope0_is_hard_cap_bit_exact():
    """s == 0 must return EXACTLY what the unchanged `_capped` returns (no new
    arithmetic on default traffic)."""
    for x in [-3.0, 0.0, 0.4, 1.0, 4.9999, 5.0, 5.0001, 8.3, 100.0]:
        for c in [1.0, 5.0, 8.0, 12.0]:
            assert _soft_capped(x, c, 0.0) == _capped(x, c)


def test_soft_cap_slope1_is_identity():
    for x in [-3.0, 0.0, 5.0, 8.3, 100.0]:
        assert _soft_capped(x, 5.0, 1.0) == x


def test_flat_and_object_soft_capped_agree_with_vs2():
    assert flat_leaf._soft_capped(9.0, 8.0, 0.5) == _soft_capped(9.0, 8.0, 0.5)
    assert flat_leaf._soft_capped(9.0, 8.0, 0.0) == _capped(9.0, 8.0)


# --------------------------------------------------------------------------- #
# helpers for the leaf-level gates                                             #
# --------------------------------------------------------------------------- #
def _both_players(cfg, fn):
    return [fn(st, p, cfg) for st in STATES for p in (0, 1)]


def _bonus_overflows(cfg) -> int:
    """How many (state, player) evals have an UNCAPPED closure bonus > cap — i.e. the
    soft branch fires. Non-zero is required or the ON tests would be vacuous."""
    n = 0
    for st in STATES:
        d = flat_leaf.decompose(st)
        for p in (0, 1):
            if flat_leaf.flat_closure_bonus(st, p, d, cfg) > cfg.bonus_cap:
                n += 1
    return n


# --------------------------------------------------------------------------- #
# OFF bit-exactness — slope 0.0 == the hard-cap leaf, all three paths           #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("hard", [PLAIN_HARD, CURVE_HARD])
def test_off_slope0_flat_cy_bit_identical(hard):
    soft0 = dc.replace(hard, soft_cap_slope=0.0, opp_soft_cap_slope=0.0)
    mism = 0
    for st in STATES:
        for p in (0, 1):
            a = flat_leaf.flat_virtual_score_v2(st, p, hard)
            b = flat_leaf.flat_virtual_score_v2(st, p, soft0)
            af = flat_leaf.flat_virtual_score_v2_float(st, p, hard)
            bf = flat_leaf.flat_virtual_score_v2_float(st, p, soft0)
            ci = flat_leaf_cy.flat_virtual_score_v2_cy(st, p, soft0)
            cf = flat_leaf_cy.flat_virtual_score_v2_cy_float(st, p, soft0)
            if not (a == b == ci and af == bf == cf):
                mism += 1
    assert mism == 0


def test_off_slope0_object_bit_identical():
    """Object path (USE_FLAT_LEAF off, canonical sum): slope-0 == hard cap."""
    saved_flat, saved_canon = flat_leaf.USE_FLAT_LEAF, vs2.CANONICAL_BONUS_SUM
    try:
        flat_leaf.USE_FLAT_LEAF = False
        vs2.CANONICAL_BONUS_SUM = True
        soft0 = dc.replace(PLAIN_HARD, soft_cap_slope=0.0, opp_soft_cap_slope=0.0)
        mism = sum(
            1 for st in STATES for p in (0, 1)
            if virtual_score_v2(st, p, PLAIN_HARD) != virtual_score_v2(st, p, soft0)
        )
    finally:
        flat_leaf.USE_FLAT_LEAF, vs2.CANONICAL_BONUS_SUM = saved_flat, saved_canon
    assert mism == 0


# --------------------------------------------------------------------------- #
# ON 3-path parity — object == flat(py) == cy on overflow states               #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("base_cfg", [PLAIN_HARD, CURVE_HARD])
@pytest.mark.parametrize("s_self,s_opp", [(0.25, 0.25), (0.5, 0.0), (0.0, 0.5), (1.0, 1.0)])
def test_on_three_path_parity(base_cfg, s_self, s_opp):
    cfg = dc.replace(base_cfg, soft_cap_slope=s_self, opp_soft_cap_slope=s_opp)
    # branch must actually fire for this to mean anything
    assert _bonus_overflows(cfg) > 100
    saved_flat, saved_canon, saved_cy = (
        flat_leaf.USE_FLAT_LEAF, vs2.CANONICAL_BONUS_SUM, flat_leaf.USE_CY_LEAF)
    try:
        flat_leaf.USE_FLAT_LEAF = False   # force real object path in virtual_score_v2
        flat_leaf.USE_CY_LEAF = False     # force pure-Python flat_virtual_score_v2
        vs2.CANONICAL_BONUS_SUM = True     # order-independent object bonus == flat fsum
        mism = 0
        for st in STATES:
            for p in (0, 1):
                obj = virtual_score_v2(st, p, cfg)
                fpy = flat_leaf.flat_virtual_score_v2(st, p, cfg)
                cyi = flat_leaf_cy.flat_virtual_score_v2_cy(st, p, cfg)
                fpyf = flat_leaf.flat_virtual_score_v2_float(st, p, cfg)
                cyf = flat_leaf_cy.flat_virtual_score_v2_cy_float(st, p, cfg)
                if not (obj == fpy == cyi and fpyf == cyf):
                    mism += 1
    finally:
        (flat_leaf.USE_FLAT_LEAF, vs2.CANONICAL_BONUS_SUM,
         flat_leaf.USE_CY_LEAF) = saved_flat, saved_canon, saved_cy
    assert mism == 0


# --------------------------------------------------------------------------- #
# NON-VACUITY — the soft cap changes the leaf; s=1.0 == uncapped                #
# --------------------------------------------------------------------------- #
def test_soft_cap_changes_leaf_on_overflow():
    """On overflow states a positive slope must move at least some leaf values away
    from the hard cap — otherwise the OFF==ON tests are meaningless."""
    hard = PLAIN_HARD
    soft = dc.replace(hard, soft_cap_slope=0.5, opp_soft_cap_slope=0.5)
    diffs = sum(
        1 for st in STATES for p in (0, 1)
        if flat_leaf.flat_virtual_score_v2_float(st, p, hard)
        != flat_leaf.flat_virtual_score_v2_float(st, p, soft)
    )
    assert diffs > 50


def test_slope1_equals_uncapped_leaf():
    """slope 1.0 gives full credit above the cap == no cap at all."""
    uncapped = dc.replace(PLAIN_HARD, bonus_cap=1e9, opp_bonus_cap=1e9)
    slope1 = dc.replace(PLAIN_HARD, soft_cap_slope=1.0, opp_soft_cap_slope=1.0)
    mism = sum(
        1 for st in STATES for p in (0, 1)
        if flat_leaf.flat_virtual_score_v2_float(st, p, uncapped)
        != flat_leaf.flat_virtual_score_v2_float(st, p, slope1)
    )
    assert mism == 0
