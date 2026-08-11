"""Tests for the v2.9.1 retune candidate parser (scripts/v29/eval_v29_vs_v28.py).

The composable `Bmild_<mods>` parser drives the local re-tune waves (scale / cap /
closure-P). A silent parser bug corrupts experiment validity, so these lock the
contract — especially the COMPOSITION and the closure-P STRUCTURE caveat that the
retune plan calls out (p<AA>-<BB> drops the anchor's 3-open ticket).
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "v29"))
from eval_v29_vs_v28 import MILD_CURVE, candidate_cfg, candidate_value_norm  # noqa: E402

ANCHOR_CLOSURE_P = {1: 0.5, 2: 0.2, 3: 0.05}  # 3-open (env default; the anchor's schedule)


def test_anchor_is_cap5_3open_mildcurve():
    """The Bmild anchor: cap=5, 3-open schedule, MILD curve, inert flat meeple_k."""
    c = candidate_cfg("Bmild")
    assert c.bonus_cap == 5.0 and c.opp_bonus_cap == 5.0
    assert c.closure_p == ANCHOR_CLOSURE_P
    assert c.v29_meeple_curve == MILD_CURVE
    assert c.meeple_k == 2.0  # present but inert (curve replaces it)


@pytest.mark.parametrize("k,scale", [("Bmild_x075", 0.75), ("Bmild_x125", 1.25), ("Bmild_x150", 1.50)])
def test_scale_multiplier(k, scale):
    """Wave A: _x<NNN> scales the curve by NNN/100; cap & schedule stay at anchor."""
    c = candidate_cfg(k)
    assert c.v29_meeple_curve == tuple(round(v * scale, 4) for v in MILD_CURVE)
    assert c.bonus_cap == 5.0 and c.closure_p == ANCHOR_CLOSURE_P


@pytest.mark.parametrize("k,cap", [("Bmild_cap8", 8.0), ("Bmild_cap12", 12.0), ("Bmild_cap16", 16.0), ("Bmild_cap20", 20.0)])
def test_cap_override(k, cap):
    """Wave B: _cap<N> sets bonus_cap==opp_bonus_cap; curve & schedule unchanged."""
    c = candidate_cfg(k)
    assert c.bonus_cap == cap and c.opp_bonus_cap == cap
    assert c.v29_meeple_curve == MILD_CURVE and c.closure_p == ANCHOR_CLOSURE_P


@pytest.mark.parametrize("k,p1,p2", [("Bmild_p040-015", 0.4, 0.15), ("Bmild_p050-010", 0.5, 0.1)])
def test_closure_p_override_drops_3open(k, p1, p2):
    """Wave C: _p<AA>-<BB> sets closure_p={1:AA,2:BB} — and DROPS the anchor's 3:0.05.

    This is the documented structure caveat: the p-cell is NOT a pure magnitude change
    vs the anchor; it also removes the 3-open ticket. The test pins that behaviour so a
    future 3-entry fix is an explicit decision, not an accident.
    """
    c = candidate_cfg(k)
    assert c.closure_p == {1: p1, 2: p2}
    assert 3 not in c.closure_p  # the 3-open ticket is dropped
    assert c.v29_meeple_curve == MILD_CURVE and c.bonus_cap == 5.0


@pytest.mark.parametrize("k,expect", [
    ("Bmild_p050-020-005", {1: 0.5, 2: 0.2, 3: 0.05}),   # == anchor (structure-preserving control)
    ("Bmild_p040-015-005", {1: 0.4, 2: 0.15, 3: 0.05}),
    ("Bmild_p060-025-005", {1: 0.6, 2: 0.25, 3: 0.05}),
])
def test_closure_p_three_entry_preserves_3open(k, expect):
    """Wave C structure-preserving form: _p<AA>-<BB>-<CC> keeps the 3-open ticket.

    p050-020-005 reproduces the anchor's schedule EXACTLY, so it is the clean control
    that isolates magnitude perturbations from the schedule-structure change.
    """
    c = candidate_cfg(k)
    assert c.closure_p == expect
    if k == "Bmild_p050-020-005":
        assert c.closure_p == candidate_cfg("Bmild").closure_p  # genuinely == anchor


def test_composition_scale_and_cap():
    """Composable: Bmild_x125_cap16 applies BOTH the scale and the cap."""
    c = candidate_cfg("Bmild_x125_cap16")
    assert c.v29_meeple_curve == tuple(round(v * 1.25, 4) for v in MILD_CURVE)
    assert c.bonus_cap == 16.0 and c.opp_bonus_cap == 16.0


@pytest.mark.parametrize("name,norm", [
    ("Bmild", 15.0), ("Bmild_cap8", 15.0),            # no _n -> default 15.0
    ("Bmild_cap8_n12", 12.0), ("Bmild_n18", 18.0), ("Bmild_cap8_n24", 24.0),
])
def test_value_norm_extraction(name, norm):
    """Wave D: _n<NN> rides ALONGSIDE candidate_cfg (MCTS knob, not a LeafConfig field)."""
    assert candidate_value_norm(name) == norm
    # the _n modifier must NOT corrupt the LeafConfig (cap/curve still resolve normally)
    assert candidate_cfg(name).bonus_cap == (8.0 if "cap8" in name else 5.0)


def test_compose_true_production_base():
    """Bmild_cap12_p050-020 = Bmild on the REAL documented production base (cap12 + drop-3-open)."""
    c = candidate_cfg("Bmild_cap12_p050-020")
    assert c.bonus_cap == 12.0 and c.closure_p == {1: 0.5, 2: 0.2}
    assert c.v29_meeple_curve == MILD_CURVE


def test_v28prod_is_real_production():
    """v28prod = ACTUAL production v2.8 (cap12, drop-3-open, flat-k2, NO curve) — the throne-test
    baseline. Distinct from the harness 'v28' (cap5/3-open env default) every prior run used."""
    p = candidate_cfg("v28prod")
    assert p.bonus_cap == 12.0 and p.opp_bonus_cap == 12.0
    assert p.closure_p == {1: 0.5, 2: 0.2}     # drop-3-open (no 3:0.05 ticket)
    assert p.meeple_k == 2.0 and p.v29_meeple_curve is None   # flat meeple, no curve
    assert candidate_cfg("v28").bonus_cap == 5.0              # the harness 'v28' is NOT production
