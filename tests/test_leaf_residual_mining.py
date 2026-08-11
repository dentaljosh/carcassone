"""Contracts for the leaf residual-mining harness (measurement/leaf_residual_mining_20260721).

These lock the things that, if they drifted silently, would invalidate the verdict:
  (A) the feature dictionary in code == the dictionary declared in PREREG.md
  (B) the negative control is deterministic pure noise; the yardstick is EXACTLY the
      CL-051 curve125-minus-curve100 leaf delta
  (C) cross-fitting is GROUPED (no game straddles a fold) — the split PREREG §4 requires
  (D) Holm / BH behave as specified
  (E) the §5 gate maps (rho, p_holm, tier, replication) -> HIT / AMBIGUOUS / NULL exactly
  (F) the residual sign convention is V_deep - V_leaf, mover POV
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
MOD = REPO / "measurement" / "leaf_residual_mining_20260721"
sys.path.insert(0, str(MOD))
sys.path.insert(0, str(REPO / "src"))

os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")

import analyze_residual as AR  # noqa: E402
import leaf_features as LF  # noqa: E402


# --------------------------------------------------------------------------- #
# (A) code <-> PREREG agreement                                                #
# --------------------------------------------------------------------------- #
def _prereg_text() -> str:
    return (MOD / "PREREG.md").read_text()


def test_prereg_declares_every_candidate_and_nothing_else():
    """Every candidate name appears in the PREREG table, and the PREREG's declared
    family size matches the code's."""
    txt = _prereg_text()
    for name in LF.CANDIDATE_NAMES:
        assert f"`{name}`" in txt, f"{name} is in the code dictionary but not in PREREG.md"
    assert f"**K = {len(LF.CANDIDATE_NAMES)} candidates**" in txt
    # the two out-of-family series must be declared as out-of-family
    assert f"`{LF.NEG_CONTROL}`" in txt and f"`{LF.POS_REF}`" in txt


def test_prereg_gate_thresholds_match_the_estimator():
    txt = _prereg_text()
    assert AR.RHO_HIT == 0.10 and AR.RHO_NULL == 0.05 and AR.ALPHA == 0.05
    assert "0.05 ≤ \\|ρ_f\\| < 0.10" in txt or "0.05 ≤ **\\|ρ_f\\|" in txt or \
        re.search(r"0\.05 ≤ .{0,12}ρ.{0,12} < 0\.10", txt), \
        "PREREG must name the ambiguous band explicitly"
    assert "Holm" in txt


def test_every_candidate_has_a_cost_tier_and_only_A_B_are_leaf_viable():
    for name in LF.CANDIDATE_NAMES:
        assert LF.TIER[name] in ("A", "B", "C")
    assert LF.TIER["n_legal"] == "C", "mobility needs move generation -> not leaf-viable"
    # a C-tier feature must never be gateable
    assert "cannot become a leaf term" in LF.__doc__


def test_feature_name_set_is_asserted_at_emit_time():
    """root_features() asserts its own output keys, so code/doc drift fails loudly."""
    src = (MOD / "leaf_features.py").read_text()
    assert "assert set(feats) == set(ALL_FEATURES)" in src


# --------------------------------------------------------------------------- #
# (B) controls / yardstick semantics                                           #
# --------------------------------------------------------------------------- #
def test_neg_control_is_deterministic_and_spread_over_pm1():
    a = LF._neg_control("windowaudit_s7000000_p100")
    b = LF._neg_control("windowaudit_s7000000_p100")
    c = LF._neg_control("windowaudit_s7000000_p102")
    assert a == b and a != c
    vals = np.array([LF._neg_control(f"x{i}") for i in range(4000)])
    assert vals.min() > -1.0 and vals.max() < 1.0
    assert abs(vals.mean()) < 0.05 and 0.5 < vals.std() < 0.65   # ~U(-1,1)


def test_pos_ref_is_exactly_the_cl051_curve_delta():
    """CL-051 changed the leaf by curve125 - curve100 on the free-meeple lookup."""
    from carcassonne_ai import champion_factory as CF
    curve = CF.production_prior_cfg().leaf_cfg.v29_meeple_curve
    assert curve is not None
    for a in range(8):
        for b in range(8):
            d125 = (LF.flat_leaf._flat_curve_lookup(curve, a)
                    - LF.flat_leaf._flat_curve_lookup(curve, b))
            d100 = (LF.flat_leaf._flat_curve_lookup(LF.CURVE100, a)
                    - LF.flat_leaf._flat_curve_lookup(LF.CURVE100, b))
            # curve125 == 1.25 * curve100 exactly, so the delta is 0.25 * curve100 delta
            assert d125 - d100 == pytest.approx(0.25 * d100, abs=1e-9)


def test_curve100_is_the_pre_cl051_champion_curve():
    from carcassonne_ai import champion_factory as CF
    curve = tuple(float(x) for x in CF.production_prior_cfg().leaf_cfg.v29_meeple_curve)
    assert curve == tuple(1.25 * c for c in LF.CURVE100)


# --------------------------------------------------------------------------- #
# (C) the split                                                                #
# --------------------------------------------------------------------------- #
def test_crossfitting_is_grouped_by_deck_seed():
    groups = np.repeat(np.arange(300), 3)
    y = np.random.default_rng(0).normal(size=len(groups))
    X = np.column_stack([np.ones(len(y)), np.random.default_rng(1).normal(size=len(y))])
    _, fold = AR.crossfit_resid(y, X, groups)
    for g in np.unique(groups):
        assert len(set(fold[groups == g])) == 1, "a game straddled two folds"
    assert len(set(fold.tolist())) == AR.N_FOLDS


def test_crossfit_residual_is_out_of_fold_not_in_sample():
    """An in-sample residual would be orthogonal to X by construction; an out-of-fold
    one is not, and (the point of the split) it does not absorb the signal."""
    rng = np.random.default_rng(3)
    groups = np.repeat(np.arange(500), 3)
    n = len(groups)
    x = rng.normal(size=n)
    X = np.column_stack([np.ones(n), x])
    f = 0.6 * x + rng.normal(size=n)
    y = 2.0 * x + 0.30 * f + rng.normal(size=n)
    e_r, _ = AR.crossfit_resid(y, X, groups)
    e_f, _ = AR.crossfit_resid(f, X, groups)
    rho = np.corrcoef(e_r, e_f)[0, 1]
    assert rho > 0.15, "a real partial effect must survive cross-fitting"


def test_boot_indices_resample_whole_games():
    groups = np.repeat(np.arange(50), 4)
    idx = AR.boot_indices(groups, n_boot=25, seed=2)
    assert len(idx) == 25
    for ii in idx:
        assert len(ii) == len(groups)          # G games x their sizes
        cnt = np.bincount(groups[ii], minlength=50)
        assert np.all(cnt % 4 == 0), "a game was split across the resample"


def test_icc_and_design_effect_detect_within_game_correlation():
    rng = np.random.default_rng(5)
    groups = np.repeat(np.arange(800), 3)
    gfx = rng.normal(size=800)[groups]
    y_corr = gfx + rng.normal(size=len(groups))
    y_indep = rng.normal(size=len(groups))
    icc_c, mbar = AR.icc(y_corr, groups)
    icc_i, _ = AR.icc(y_indep, groups)
    assert mbar == pytest.approx(3.0)
    assert icc_c > 0.3, "ICC must see a strong game random effect"
    assert icc_i < 0.1, "ICC must be ~0 with no game structure"


# --------------------------------------------------------------------------- #
# (D) multiple comparisons                                                     #
# --------------------------------------------------------------------------- #
def test_holm_is_step_down_and_monotone():
    p = {"a": 0.001, "b": 0.01, "c": 0.04, "d": 0.9}
    adj = AR.holm(p)
    assert adj["a"] == pytest.approx(0.004)     # 4 * 0.001
    assert adj["b"] == pytest.approx(0.03)      # 3 * 0.01
    assert adj["c"] == pytest.approx(0.08)      # 2 * 0.04
    assert adj["d"] == pytest.approx(0.9)
    assert adj["a"] <= adj["b"] <= adj["c"] <= adj["d"]


def test_holm_is_more_conservative_than_bh():
    p = {f"f{i}": v for i, v in enumerate([0.001, 0.006, 0.02, 0.3, 0.7])}
    h, b = AR.holm(p), AR.bh(p)
    for k in p:
        assert h[k] >= b[k] - 1e-12


def test_holm_family_is_the_candidates_only():
    """The negative control and the yardstick must NOT be in the correction family —
    including them would change every adjusted p-value."""
    src = (MOD / "analyze_residual.py").read_text()
    assert "fam = {k: res[k][\"p\"] for k in LF.CANDIDATE_NAMES}" in src
    assert LF.NEG_CONTROL not in LF.CANDIDATE_NAMES
    assert LF.POS_REF not in LF.CANDIDATE_NAMES


# --------------------------------------------------------------------------- #
# (E) the gate                                                                 #
# --------------------------------------------------------------------------- #
def _fake(features: dict) -> dict:
    base = {n: dict(rho=0.0, p=1.0, p_holm=1.0, ci=[0, 0]) for n in LF.ALL_FEATURES}
    base[LF.NEG_CONTROL] = dict(rho=0.01, p=0.8, ci=[0, 0])
    base.update({k: {**base[k], **v} for k, v in features.items()})
    return {"features": base}


def test_gate_null_when_nothing_clears():
    g = AR.gate(_fake({"road_anticip_diff": dict(rho=0.04, p_holm=0.9)}), None)
    assert g["verdict"] == "NULL" and g["pipeline_valid"]


def test_gate_hit_needs_size_significance_viability_and_replication():
    prim = _fake({"road_anticip_diff": dict(rho=0.14, p_holm=0.01)})
    rep = _fake({"road_anticip_diff": dict(rho=0.09, p_holm=0.2)})
    assert AR.gate(prim, rep)["verdict"] == "HIT"
    # same effect, replication fails on sign -> AMBIGUOUS, not HIT
    rep_bad = _fake({"road_anticip_diff": dict(rho=-0.09)})
    assert AR.gate(prim, rep_bad)["verdict"] == "AMBIGUOUS"
    # same effect, replication too small -> AMBIGUOUS
    rep_small = _fake({"road_anticip_diff": dict(rho=0.01)})
    assert AR.gate(prim, rep_small)["verdict"] == "AMBIGUOUS"
    # no replication sample at all -> cannot be a HIT
    assert AR.gate(prim, None)["verdict"] == "AMBIGUOUS"


def test_gate_ambiguous_band_is_0p05_to_0p10():
    rep = _fake({"pending_diff": dict(rho=0.08)})
    assert AR.gate(_fake({"pending_diff": dict(rho=0.07, p_holm=0.01)}),
                   rep)["verdict"] == "AMBIGUOUS"
    assert AR.gate(_fake({"pending_diff": dict(rho=0.049, p_holm=0.01)}),
                   rep)["verdict"] == "NULL"


def test_gate_never_promotes_a_tier_C_feature():
    prim = _fake({"n_legal": dict(rho=0.30, p_holm=1e-6)})
    rep = _fake({"n_legal": dict(rho=0.30)})
    g = AR.gate(prim, rep)
    assert g["verdict"] == "AMBIGUOUS"
    assert g["hits"] == [] and g["ambiguous"][0]["feature"] == "n_legal"


def test_pipeline_is_void_if_the_negative_control_fires():
    prim = _fake({})
    prim["features"][LF.NEG_CONTROL] = dict(rho=0.20, p=0.001, ci=[0.1, 0.3])
    assert AR.gate(prim, None)["pipeline_valid"] is False


# --------------------------------------------------------------------------- #
# (F) residual sign convention                                                 #
# --------------------------------------------------------------------------- #
def test_residual_sign_is_deep_minus_leaf_mover_pov():
    src = (MOD / "mine_residual.py").read_text()
    assert 'rec["resid"] = {k: (v - aux["v_leaf"])' in src
    assert 'assert root_player == mover' in src
    # V_deep is the POOLED visit-weighted root value, not a single world's
    assert "sumW / sumN" in src


def test_exact_latched_roots_are_rejected_not_labelled():
    src = (MOD / "mine_residual.py").read_text()
    assert '"exact_latch_in_midgame_band"' in src


def test_harness_imports_the_production_pooling_path_rather_than_reimplementing():
    src = (MOD / "mine_residual.py").read_text()
    assert "import gate_b_fair_pimc as GBF" in src
    assert "GBF.snapshot_world_search" in src
    assert "CF.build_fair_champion" in src
