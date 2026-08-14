"""Tests for the F6 win-prob pre-gate instrument (pure functions only — the
corpus scan itself is exercised by the instrument's --integrity-only smoke,
which asserts replay/checksum contracts loudly on the real corpora)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "analyzer"))

import f6_winprob_pregate as F6  # noqa: E402


# --------------------------------------------------------------------------- #
# logistic fit                                                                  #
# --------------------------------------------------------------------------- #
def _synth(beta, n=20000, seed=0, frac_draws=0.0):
    rng = np.random.default_rng(seed)
    X = np.column_stack([np.ones(n), rng.normal(0, 6, n), rng.normal(0, 4, n)])
    p = 1.0 / (1.0 + np.exp(-(X @ beta)))
    y = (rng.random(n) < p).astype(float)
    if frac_draws:
        draw = rng.random(n) < frac_draws
        y[draw] = 0.5
    return X, y


def test_fit_logistic_recovers_coefficients():
    beta = np.array([0.1, 0.30, 0.12])
    X, y = _synth(beta, seed=1)
    got = F6.fit_logistic(X, y)
    assert np.allclose(got, beta, atol=0.03), got


def test_fit_logistic_accepts_fractional_targets():
    # draws as 0.5 shrink |beta| slightly but must not break the solver
    beta = np.array([0.0, 0.25, 0.10])
    X, y = _synth(beta, seed=2, frac_draws=0.1)
    got = F6.fit_logistic(X, y)
    assert got.shape == (3,)
    assert 0.1 < got[1] < 0.4 and 0.02 < got[2] < 0.2


def test_fit_logistic_survives_separation():
    # perfectly separated data: ridge must keep the solve finite
    X = np.column_stack([np.ones(40), np.linspace(-1, 1, 40)])
    y = (X[:, 1] > 0).astype(float)
    got = F6.fit_logistic(X, y)
    assert np.all(np.isfinite(got))


# --------------------------------------------------------------------------- #
# buckets                                                                       #
# --------------------------------------------------------------------------- #
def test_bucket_boundaries_are_the_preregistered_ones():
    assert F6.bucket_of(1) == "late"
    assert F6.bucket_of(12) == "late"
    assert F6.bucket_of(13) == "mid"
    assert F6.bucket_of(36) == "mid"
    assert F6.bucket_of(37) == "early"
    assert F6.bucket_of(71) == "early"


# --------------------------------------------------------------------------- #
# binding statistics                                                            #
# --------------------------------------------------------------------------- #
def _models(a=0.0, b1=0.10, b2=0.05, bm=0.08):
    return {b: {"m1": [a, bm], "m2": [a, b1, b2], "n": 999}
            for b in ("late", "mid", "early")}


def _pos(arms, k_left=10, root_leaf=-5.0, champ=None, rid="r1"):
    return {"rid": rid, "deck_seed": 1, "ply": 0, "seat": 0, "k_left": k_left,
            "root_leaf_mover": root_leaf, "champ_action": champ, "arms": arms}


def test_near_tie_pairs_respects_eps():
    arms = [{"leaf": 0.0}, {"leaf": 0.2}, {"leaf": 1.0}]
    assert F6.near_tie_pairs(arms, 0.25) == [(0, 1)]
    assert len(F6.near_tie_pairs(arms, 1.0)) == 3


def test_position_dp_decomposition_channel():
    # two arms, SAME leaf margin, different banked/prospective split:
    # M2 must separate them, M1 must see exactly zero.
    arms = [{"action": 1, "leaf": 4.0, "banked": 4.0, "prosp": 0.0},
            {"action": 2, "leaf": 4.0, "banked": 0.0, "prosp": 4.0}]
    m = _models(b1=0.10, b2=0.05)
    dp2, npairs = F6.position_dp(_pos(arms), m, 0.25, "m2")
    dp1, _ = F6.position_dp(_pos(arms), m, 0.25, "m1")
    assert npairs == 1
    expected = abs(F6.sigmoid(0.4) - F6.sigmoid(0.2))
    assert math.isclose(dp2, expected, rel_tol=1e-12)
    assert dp1 == 0.0


def test_position_dp_no_near_tie_pair_is_unscoreable():
    arms = [{"action": 1, "leaf": 0.0, "banked": 0.0, "prosp": 0.0},
            {"action": 2, "leaf": 5.0, "banked": 5.0, "prosp": 0.0}]
    dp, npairs = F6.position_dp(_pos(arms), _models(), 0.25, "m2")
    assert dp is None and npairs == 0


def test_position_dp_identical_afterstates_are_analytic_zero():
    arms = [{"action": 1, "leaf": 3.0, "banked": 1.0, "prosp": 2.0},
            {"action": 2, "leaf": 3.0, "banked": 1.0, "prosp": 2.0}]
    dp, _ = F6.position_dp(_pos(arms), _models(), 0.25, "m2")
    assert dp == 0.0


# --------------------------------------------------------------------------- #
# champion posture                                                              #
# --------------------------------------------------------------------------- #
def test_champ_posture_counts_a_sacrifice():
    arms = [{"action": 1, "leaf": 4.0, "banked": 4.0, "prosp": 0.0},
            {"action": 2, "leaf": 4.0, "banked": 0.0, "prosp": 4.0}]
    m = _models(b1=0.10, b2=0.05)
    # trailing mover, champion took the LOWER-P(win) arm (prospective-heavy)
    rec = F6.champ_posture(_pos(arms, root_leaf=-5.0, champ=2), m, 0.25, 0.02)
    assert rec is not None and rec["champ_lower"] is True
    assert rec["sacrifice"] > 0
    # champion took the higher-P(win) arm -> not a sacrifice
    rec2 = F6.champ_posture(_pos(arms, root_leaf=-5.0, champ=1), m, 0.25, 0.02)
    assert rec2 is not None and rec2["champ_lower"] is False


def test_champ_posture_requires_trailing_and_membership():
    arms = [{"action": 1, "leaf": 4.0, "banked": 4.0, "prosp": 0.0},
            {"action": 2, "leaf": 4.0, "banked": 0.0, "prosp": 4.0}]
    m = _models()
    assert F6.champ_posture(_pos(arms, root_leaf=+2.0, champ=2), m, 0.25, 0.02) is None
    assert F6.champ_posture(_pos(arms, root_leaf=-2.0, champ=None), m, 0.25, 0.02) is None
    assert F6.champ_posture(_pos(arms, root_leaf=-2.0, champ=99), m, 0.25, 0.02) is None


# --------------------------------------------------------------------------- #
# adjudication (the pre-registered branches)                                    #
# --------------------------------------------------------------------------- #
def test_adjudicate_branch_k_fires_below_five_percent():
    assert F6.adjudicate(0.049, (0.4, 0.8), 100, 0.9) == "K"


def test_adjudicate_branch_f_needs_all_three():
    assert F6.adjudicate(0.20, (0.4, 0.8), 30, 0.6) == "F"
    # CI includes 1 -> T
    assert F6.adjudicate(0.20, (0.7, 1.2), 30, 0.6) == "T"
    # too few posture cases -> T
    assert F6.adjudicate(0.20, (0.4, 0.8), 10, 0.9) == "T"
    # champion already picks the right arm -> T
    assert F6.adjudicate(0.20, (0.4, 0.8), 30, 0.2) == "T"


def test_fit_bucket_models_refuses_tiny_buckets():
    rows = [{"k_left": 5, "banked": 1.0, "prosp": 0.5, "leaf": 1.5, "y": 1.0}] * 10
    assert F6.fit_bucket_models(rows) == {}


def test_fit_bucket_models_decomposition_identity_and_shape():
    rng = np.random.default_rng(3)
    rows = []
    for _ in range(400):
        banked = float(rng.normal(0, 6))
        prosp = float(rng.normal(0, 4))
        leaf = banked + prosp
        p = 1.0 / (1.0 + math.exp(-(0.12 * banked + 0.06 * prosp)))
        rows.append({"k_left": 10, "banked": banked, "prosp": prosp,
                     "leaf": leaf, "y": float(rng.random() < p)})
    m = F6.fit_bucket_models(rows)
    assert set(m) == {"late"}
    a, b1, b2 = m["late"]["m2"]
    assert b1 > b2 > 0  # the generating discount must be recoverable in sign
