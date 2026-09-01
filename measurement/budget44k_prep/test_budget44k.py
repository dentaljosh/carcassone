#!/usr/bin/env python3
"""Contract tests for the 44032 budget-rung round (`budget44k_prep`).

Run:  `.venv/bin/python -m pytest measurement/budget44k_prep/test_budget44k.py -q`

⛔ THE FIXTURE TRAP. `selftest_fixture/<CELL>/` must be **real emitter output**,
never hand-authored. `test_fixtures_are_from_a_real_emitter` asserts the
provenance fields only a real `eval_fair_puct.py` run writes, and
`test_fixtures_express_this_rounds_shape` asserts they express the launcher's
own CLI shape (asymmetric budget, both seats armed) rather than an idealised
one. Regenerate with `./launch_budget44k.sh --smoke` (see
`selftest_fixture/README.md`).
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import screen_lib as L                       # noqa: E402
import adjudicate_budget44k as A             # noqa: E402

PY = sys.executable


# =========================================================================== #
# 1. THE LIBRARY'S OWN INVARIANTS                                             #
# =========================================================================== #

def test_sanity_check_clean():
    assert L.sanity_check() == []


def test_budget_arithmetic_is_the_frozen_one():
    assert L.OPP_K_DETS * L.OPP_SIMS_PER_DET == L.OPP_TOTAL_SIMS == 22016
    assert L.CAND_TOTAL_SIMS == 44032 == 2 * L.OPP_TOTAL_SIMS
    for name, s in L.CELLS.items():
        assert s["k_dets"] * s["sims_per_det"] == s["total_sims"] == 44032, name


def test_the_two_allocations_are_the_two_named_shapes():
    k32, sims = L.CELLS["CELL_K32"], L.CELLS["CELL_SIMS"]
    assert (k32["k_dets"], k32["sims_per_det"]) == (32, 1376)
    assert (sims["k_dets"], sims["sims_per_det"]) == (16, 2752)
    # CELL_K32 doubles WIDTH at the deployed depth
    assert k32["k_dets"] == 2 * L.OPP_K_DETS
    assert k32["sims_per_det"] == L.OPP_SIMS_PER_DET
    # CELL_SIMS doubles DEPTH at the deployed width
    assert sims["k_dets"] == L.OPP_K_DETS
    assert sims["sims_per_det"] == 2 * L.OPP_SIMS_PER_DET


def test_deployed_tiearb_matches_the_module_not_a_retyped_copy():
    import tiearb_gates as TA
    assert L.DEPLOYED_TIEARB == TA.DEPLOYED_TIEARB_B64
    assert L.DEPLOYED_TIEARB["B"] == 64 and L.DEPLOYED_TIEARB["J"] == 4
    assert L.DEPLOYED_TIEARB["phase_gate"] == "all"


def test_screen_decks_are_a_prefix_subset_of_the_primary_s():
    p, s = L.CELLS[L.PRIMARY_CELL], L.CELLS[L.SCREEN_CELL]
    assert p["deck_offset"] == s["deck_offset"] == 0
    assert s["n_decks"] < p["n_decks"]
    assert L.WIDTH_CONTRAST_DECKS == s["n_decks"]


def test_owner_W_override_is_recorded():
    assert L.W_LOCAL == 30


# =========================================================================== #
# 2. SIZING, BARS AND THE HONESTY CLAIMS                                      #
# =========================================================================== #

def test_planning_ses_match_the_standing_model():
    assert L.SE_PRIMARY == pytest.approx(13.81 / math.sqrt(800), rel=1e-12)
    assert L.SE_SCREEN == pytest.approx(13.81 / math.sqrt(400), rel=1e-12)
    assert L.SE_PRIMARY == pytest.approx(0.4883, abs=1e-3)
    assert L.SE_SCREEN == pytest.approx(0.6905, abs=1e-3)


def test_elo_planning_se_is_a_function_of_GAMES_not_decks():
    # The recurring trap: elo sigma is per GAME. 800 decks == 1600 games.
    assert L.SE_ELO_PRIMARY == pytest.approx(L.elo_sigma_paired(0.5, 1600))
    assert L.SE_ELO_SCREEN == pytest.approx(L.elo_sigma_paired(0.5, 800))
    assert L.SE_ELO_SCREEN == pytest.approx(8.686, abs=1e-2)


def test_bar_discriminates_the_two_live_families_and_is_not_two_sigma():
    """PREREG §4.3: BAR_M sits AT family A's prediction and well above family
    B's, so the ladder reads as a family test."""
    assert L.BAR_M == pytest.approx(0.80)
    assert L.PRIOR_RATE_FAMILY == pytest.approx(L.DECAY_R * L.D_PREV_RUNG)
    assert L.PRIOR_RATE_FAMILY == pytest.approx(0.8298, abs=1e-3)
    assert abs(L.BAR_M - L.PRIOR_RATE_FAMILY) < 0.10, "bar left family A"
    assert L.BAR_M > 3.0 * L.PRIOR_PRICE_FAMILY, "bar no longer excludes family B"
    # ...and the relationship to 2*sigma-hat is the one PREREG §4.3 states
    assert L.BAR_M < 2 * L.SE_PRIMARY


def test_the_four_priors_are_ordered_and_sourced():
    assert (L.PRIOR_PRICE_FAMILY < L.PRIOR_TYPEM_DISCOUNTED
            < L.PRIOR_RATE_FAMILY < L.PRIOR_NO_DECAY == L.D_PREV_RUNG)
    # family B is the CURRENT bound's own g_next, not a guess
    assert L.PRIOR_PRICE_FAMILY == pytest.approx(0.1837)
    assert L.PRICE_RESTATED_TAIL_H == pytest.approx(0.5652)
    # "expected effect is BELOW the last doubling's +1.229" — the brief's own
    # diminishing-returns statement, asserted rather than left in prose.
    assert L.PRIOR_RATE_FAMILY < L.D_PREV_RUNG
    # ...and the whole remaining tail under the CURRENT bound is smaller than
    # the single rung already realized. That tension is the round's premise.
    assert L.PRICE_RESTATED_TAIL_H < L.D_PREV_RUNG


def test_the_two_families_disagree_by_the_factor_the_design_assumes():
    assert 4.0 < L.PRIOR_RATE_FAMILY / L.PRIOR_PRICE_FAMILY < 6.0


def test_the_previous_rung_is_the_only_true_doubling_in_the_ladder():
    """The 2752 -> 11008 step was 4x AND moved width, so it is context, never
    a per-doubling figure."""
    assert L.D_4X_RUNG_CONFOUNDED == pytest.approx(2.9775)
    assert L.D_4X_RUNG_FIXED_WIDTH == pytest.approx(2.24)
    assert L.D_PREV_RUNG < L.D_4X_RUNG_FIXED_WIDTH


def test_type_m_tripwire_the_mde_is_above_every_prior():
    m80 = L.mde(L.SE_PRIMARY)
    assert m80 == pytest.approx(1.387, abs=5e-3)
    for _label, delta in L.POWER_PRIORS:
        if delta > 0:
            assert delta < m80, "a prior above the MDE would void the Type-M rider"


def test_power_table_matches_what_prereg_prints():
    """PREREG §4.4's headline numbers. If these move, the doc is stale."""
    p = L.power_cell(0.0, L.SE_PRIMARY)
    assert p["p_unresolved"] == pytest.approx(0.618, abs=5e-3)
    assert p["p_null_bounded"] == pytest.approx(0.336, abs=5e-3)
    assert L.power_cell(L.PRIOR_RATE_FAMILY, L.SE_PRIMARY)["p_adopt"] == \
        pytest.approx(0.382, abs=5e-3)
    assert L.power_cell(L.PRIOR_NO_DECAY, L.SE_PRIMARY)["p_adopt"] == \
        pytest.approx(0.698, abs=5e-3)
    # §4.4's stated non-inference limit: family B and a true null look alike
    pb = L.power_cell(L.PRIOR_PRICE_FAMILY, L.SE_PRIMARY)
    assert pb["p_adopt"] < 0.10
    assert abs(pb["p_null_bounded"] - p["p_null_bounded"]) < 0.20
    assert L.power_cell(-3.0, L.SE_PRIMARY)["p_regression"] > 0.999
    # the §3.2(3) argument for where the power went
    assert (L.power_cell(-1.0, L.SE_PRIMARY)["p_regression"]
            > L.power_cell(-1.0, L.SE_SCREEN)["p_regression"])


def test_false_adopt_under_a_true_null_is_the_2sigma_rate():
    assert L.power_cell(0.0, L.SE_PRIMARY)["p_adopt"] == pytest.approx(0.0228,
                                                                       abs=2e-3)


def test_power_probabilities_are_a_partition():
    for se in (L.SE_PRIMARY, L.SE_SCREEN, 0.25, 1.4):
        for delta in (-4, -1, -0.2, 0, 0.18, 0.5, 0.83, 1.23, 3):
            p = L.power_cell(delta, se)
            assert sum(p[k] for k in ("p_adopt", "p_regression",
                                      "p_null_bounded",
                                      "p_unresolved")) == pytest.approx(1.0)


# =========================================================================== #
# 3. THE BRANCH LADDER                                                        #
# =========================================================================== #

@pytest.mark.parametrize("M,se,expect", [
    (-5.0, 0.49, "B-REGRESSION"),        # clearly worse
    (-0.98, 0.49, "B-REGRESSION"),       # exactly at M + 2se == 0
    (2.00, 0.49, "B-ADOPT"),             # clearly better and above the bar
    (0.90, 0.49, "B-UNRESOLVED"),        # above the bar but not 2-sigma clear
    (0.00, 0.10, "B-NULL-BOUNDED"),      # tight and null
    (0.30, 0.10, "B-NULL-BOUNDED"),      # tight and below the bar
    (0.50, 0.49, "B-UNRESOLVED"),
])
def test_branch_ladder_pinned(M, se, expect):
    assert L.branch_for_cell(M, se, gates_ok=True) == expect


def test_adopt_needs_BOTH_conditions():
    # 2-sigma clear but BELOW the bar -> not an adopt
    assert L.branch_for_cell(0.5, 0.10, gates_ok=True) != "B-ADOPT"
    # above the bar but NOT 2-sigma clear -> not an adopt
    assert L.branch_for_cell(0.9, 0.49, gates_ok=True) != "B-ADOPT"
    # both -> adopt
    assert L.branch_for_cell(1.5, 0.30, gates_ok=True) == "B-ADOPT"


def test_regression_is_checked_before_null_bounded():
    # A strongly negative reading satisfies BOTH conditions; the registered
    # order must resolve it to REGRESSION.
    M, se = -3.0, 0.49
    assert (M + L.BRANCH_Z * se) <= 0.0             # regression eligible
    assert (M + L.BRANCH_Z * se) < L.BAR_M          # null-bounded eligible too
    assert L.branch_for_cell(M, se, gates_ok=True) == "B-REGRESSION"


def test_branches_are_mutually_exclusive_and_total_on_a_grid():
    for m in range(-400, 401, 7):
        for se100 in (10, 25, 49, 69, 100, 150):
            M, se = m / 100.0, se100 / 100.0
            b = L.branch_for_cell(M, se, gates_ok=True)
            assert b in L.BRANCHES
            reg = (M + 2 * se) <= 0
            adopt = (M - 2 * se) > 0 and M >= L.BAR_M
            assert not (reg and adopt)


def test_gates_not_ok_forces_void_regardless_of_statistics():
    assert L.branch_for_cell(5.0, 0.1, gates_ok=False) == "U-VOID-INSTRUMENT"


@pytest.mark.parametrize("M,se", [(None, 0.4), (1.0, None), (1.0, float("nan")),
                                  (1.0, 0.0), (1.0, -0.5), (None, None)])
def test_unusable_statistic_forces_void(M, se):
    assert L.branch_for_cell(M, se, gates_ok=True) == "U-VOID-INSTRUMENT"


# =========================================================================== #
# 4. THE STATISTIC                                                            #
# =========================================================================== #

def test_per_deck_margins_drops_half_played_decks():
    recs = [{"seed": 1, "a_seat": 0, "diff": 2.0},
            {"seed": 1, "a_seat": 1, "diff": 4.0},
            {"seed": 2, "a_seat": 0, "diff": 9.0}]          # half played
    assert L.per_deck_margins(recs) == {1: 3.0}


def test_paired_margin_sign_is_candidate_minus_opponent():
    recs = [{"seed": 1, "a_seat": 0, "diff": 1.0},
            {"seed": 1, "a_seat": 1, "diff": 1.0},
            {"seed": 2, "a_seat": 0, "diff": 3.0},
            {"seed": 2, "a_seat": 1, "diff": 3.0}]
    m, z, n, se, _ = L.paired_margin(recs)
    assert n == 2 and m == pytest.approx(2.0) and m > 0


def test_winrate_elo_is_candidate_referenced():
    recs = [{"seed": i, "a_seat": i % 2, "diff": 1.0, "won_by_champ": True}
            for i in range(10)]
    we = L.winrate_elo(recs)
    assert we["W"] == 10 and we["winrate"] == 1.0 and we["elo"] > 0


def test_paired_difference_is_the_width_contrast():
    a = {1: 3.0, 2: 5.0, 3: 1.0, 7: 0.0}
    b = {1: 1.0, 2: 1.0, 3: 1.0}
    mean, z, n, se, _ = L.paired_difference(a, b)
    assert n == 3 and mean == pytest.approx(2.0)


# =========================================================================== #
# 5. THE BUDGET GATES — the reason this round exists                          #
# =========================================================================== #

def _man(cand=(32, 1376, 44032), opp=(16, 1376, 22016)):
    return {"config": {
        "champion": {"k_dets": cand[0], "sims_per_det": cand[1],
                     "total_sims": cand[2]},
        "opponent": {"k_dets": opp[0], "sims_per_det": opp[1],
                     "total_sims": opp[2], "champ_cfg": {}},
    }}


def _summ(cand=(32, 1376, 44032), opp=(16, 1376, 22016), asym=True):
    return {"asymmetric_budgets": asym,
            "candidate_k_dets": cand[0], "candidate_sims": cand[1],
            "candidate_total_sims": cand[2],
            "opp_k_dets": opp[0], "opp_sims": opp[1], "opp_total_sims": opp[2]}


def test_budget_gate_healthy():
    g = L.budget_gate(_man(), _summ(), "CELL_K32")
    assert g["ok"], g["why"]


def test_budget_gate_rejects_the_forgotten_opp_flag_symmetric_cell():
    """⛔ THE silent failure: omit --opp-k-dets/--opp-sims and the opponent
    inherits the candidate's budget. Nothing errors; the cell measures nothing."""
    g = L.budget_gate(_man(opp=(32, 1376, 44032)),
                      _summ(opp=(32, 1376, 44032)), "CELL_K32")
    assert not g["ok"]
    r = L.budget_ratio_gate(_man(opp=(32, 1376, 44032)),
                            _summ(opp=(32, 1376, 44032)), "CELL_K32")
    assert not r["ok"], "the magnitude-free gate must catch it too"


def test_budget_gate_requires_the_summary_second_witness():
    assert not L.budget_gate(_man(), _summ(asym=False), "CELL_K32")["ok"]
    m = _man()
    s = _summ()
    del s["opp_total_sims"]
    assert not L.budget_gate(m, s, "CELL_K32")["ok"]


def test_budget_gate_rejects_manifest_summary_disagreement():
    g = L.budget_gate(_man(), _summ(opp=(16, 1376, 11008)), "CELL_K32")
    assert not g["ok"]
    assert "DISAGREE" in g["why"] or "!=" in g["why"]


def test_budget_gate_absent_is_fail():
    assert not L.budget_gate({}, {}, "CELL_K32")["ok"]
    assert not L.budget_gate(None, None, "CELL_SIMS")["ok"]


def test_budget_gate_pins_the_exact_44032_and_22016_magnitudes():
    # the previous rung's budget on the candidate side must FAIL
    assert not L.budget_gate(_man(cand=(16, 1376, 22016)),
                             _summ(cand=(16, 1376, 22016)), "CELL_K32")["ok"]


def test_budget_gate_rejects_the_other_cell_s_allocation():
    """A CELL_SIMS archive adjudicated as CELL_K32 must fail — same total,
    wrong allocation."""
    m, s = _man(cand=(16, 2752, 44032)), _summ(cand=(16, 2752, 44032))
    assert L.budget_gate(m, s, "CELL_SIMS")["ok"]
    assert not L.budget_gate(m, s, "CELL_K32")["ok"]
    assert not L.budget_ratio_gate(m, s, "CELL_K32")["ok"]


def test_budget_ratio_gate_is_magnitude_free():
    """It passes on a reduced-budget archive that preserves the shape — which
    is what lets the smoke and the fixtures exercise it."""
    m = _man(cand=(4, 32, 128), opp=(2, 32, 64))
    s = _summ(cand=(4, 32, 128), opp=(2, 32, 64))
    assert L.budget_ratio_gate(m, s, "CELL_K32")["ok"]
    assert not L.budget_gate(m, s, "CELL_K32")["ok"], \
        "the MAGNITUDE gate must still reject a reduced-budget archive"


def test_budget_ratio_gate_rejects_a_non_doubling():
    m = _man(cand=(32, 688, 22016))
    s = _summ(cand=(32, 688, 22016))
    assert not L.budget_ratio_gate(m, s, "CELL_K32")["ok"]


def test_budget_gate_rejects_internally_inconsistent_manifest():
    m = _man(cand=(32, 1376, 99999))
    s = _summ(cand=(32, 1376, 99999))
    assert not L.budget_gate(m, s, "CELL_K32")["ok"]


# =========================================================================== #
# 6. THE ARBITER GATES — both-armed, with positive controls                   #
# =========================================================================== #

def _arb_man(cand=True, opp=True, cand_over=None, opp_over=None):
    m = {}
    if cand:
        d = dict(L.DEPLOYED_TIEARB)
        d.update(cand_over or {})
        m["cand_tiearb"] = d
    if opp:
        d = dict(L.DEPLOYED_TIEARB)
        d.update(opp_over or {})
        m["opp_tiearb"] = d
    return m


def test_tiearb_sides_gate_healthy_both_armed():
    assert L.tiearb_sides_gate(_arb_man())["ok"]


@pytest.mark.parametrize("kw", [
    {"cand": False}, {"opp": False},
    {"cand_over": {"enabled": False}}, {"opp_over": {"enabled": False}},
    {"cand_over": {"B": 16}}, {"opp_over": {"B": 32}},
    {"cand_over": {"phase_gate": "late"}}, {"opp_over": {"salt": "other"}},
    {"cand_over": {"J": 3}}, {"opp_over": {"mode": "random"}},
])
def test_tiearb_sides_gate_rejects_any_deviation(kw):
    assert not L.tiearb_sides_gate(_arb_man(**kw))["ok"]


def test_tiearb_sides_gate_rejects_a_missing_phase_gate_key():
    m = _arb_man()
    del m["opp_tiearb"]["phase_gate"]
    assert not L.tiearb_sides_gate(m)["ok"], \
        "an absent phase_gate silently runs the arbiter UNGATED"


def test_tiearb_fired_gate_needs_BOTH_positive_controls():
    healthy = {"tiearb_games": 4, "tiearb_fired_plies_total": 60,
               "opp_tiearb_games": 4, "opp_tiearb_fired_plies_total": 55}
    assert L.tiearb_fired_gate(healthy)["ok"]
    for k in ("tiearb_fired_plies_total", "opp_tiearb_fired_plies_total"):
        s = dict(healthy)
        s[k] = 0
        assert not L.tiearb_fired_gate(s)["ok"], k
    for k in ("tiearb_games", "opp_tiearb_games"):
        s = dict(healthy)
        s[k] = 0
        assert not L.tiearb_fired_gate(s)["ok"], k


def test_tiearb_fired_gate_absent_is_fail():
    assert not L.tiearb_fired_gate({})["ok"]
    assert not L.tiearb_fired_gate(None)["ok"]


# =========================================================================== #
# 7. THE ADJUDICATOR — empty pools, chunk pooling, smoke mode                 #
# =========================================================================== #

def test_empty_pool_fails_every_gate_and_voids():
    for name in L.CELLS:
        empty = {"cell": name, "out_root": "<x>", "chunks": [], "records": []}
        v = A.adjudicate_cell(empty, claimed_band=None, pinned_src_rev=None)
        assert not v["gates_ok"]
        assert v["branch"] == "U-VOID-INSTRUMENT"
        for g in v["pool_gates"]:
            assert not g["ok"], f"{g['gate']} vacuously passed on an empty pool"


def test_full_selftest_passes():
    r = subprocess.run([PY, str(HERE / "adjudicate_budget44k.py"), "--selftest"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_smoke_mode_exits_nonzero_on_an_empty_read(tmp_path):
    """The `fpu_resurrection_prep` R1 defect: a smoke that silently adjudicates
    nothing makes the launcher's `|| DIE` unreachable."""
    (tmp_path / "EMPTY").mkdir()
    r = subprocess.run([PY, str(HERE / "adjudicate_budget44k.py"),
                        "--smoke-mode", "--cell", "CELL_K32",
                        "--root", str(tmp_path / "EMPTY")],
                       capture_output=True, text=True)
    assert r.returncode != 0
    assert "NO manifest.json FOUND" in r.stdout


def test_smoke_mode_passes_on_the_shipped_fixture():
    for cell in L.CELLS:
        r = subprocess.run([PY, str(HERE / "adjudicate_budget44k.py"),
                            "--smoke-mode", "--cell", cell,
                            "--root", str(HERE / "selftest_fixture" / cell)],
                           capture_output=True, text=True)
        assert r.returncode == 0, f"{cell}: {r.stdout}"


def _fixture_cell(cell):
    return A.load_single_dir_as_cell(HERE / "selftest_fixture" / cell, cell)


def test_chunk_pooling_gnodup_catches_a_resumed_duplicate():
    cell = _fixture_cell(L.PRIMARY_CELL)
    dup = json.loads(json.dumps(cell))
    c2 = json.loads(json.dumps(dup["chunks"][0]))
    c2["name"] = L.PRIMARY_CELL + "__c2"
    dup["chunks"].append(c2)
    dup["records"] = [r for c in dup["chunks"] for r in c["records"]]
    v = A.adjudicate_cell(dup, claimed_band=None, pinned_src_rev=None)
    assert not {g["gate"]: g["ok"] for g in v["pool_gates"]}["G-NODUP"]


def test_chunk_pooling_gshardident_catches_a_wheel_change_mid_round():
    cell = _fixture_cell(L.PRIMARY_CELL)
    drift = json.loads(json.dumps(cell))
    c2 = json.loads(json.dumps(drift["chunks"][0]))
    c2["name"] = L.PRIMARY_CELL + "__c2"
    c2["manifest"]["carc_rs_binary_sha"] = "0" * 16
    drift["chunks"].append(c2)
    drift["records"] = [r for c in drift["chunks"] for r in c["records"]]
    v = A.adjudicate_cell(drift, claimed_band=None, pinned_src_rev=None)
    assert not {g["gate"]: g["ok"] for g in v["pool_gates"]}["G-SHARD-IDENT"]


def test_gchunks_requires_the_full_planned_chunk_count():
    cell = _fixture_cell(L.PRIMARY_CELL)
    v = A.adjudicate_cell(cell, claimed_band=None, pinned_src_rev=None)
    g = {x["gate"]: x for x in v["pool_gates"]}["G-CHUNKS"]
    assert not g["ok"] and g["detail"]["planned"] == 4


def test_width_contrast_is_reported_and_never_licensing():
    a = {"_per_deck_margins": {1: 3.0, 2: 5.0}, "gates_ok": True}
    b = {"_per_deck_margins": {1: 1.0, 2: 1.0}, "gates_ok": True}
    wc = A.width_contrast(a, b)
    assert wc["W"] == pytest.approx(3.0)
    assert wc["n_common_decks"] == 2
    # It reports a statistic and a direction — never a branch, never a bar.
    assert "branch" not in wc, "the width contrast must NOT emit a branch label"
    assert not any(k.startswith("bar") for k in wc), \
        "the width contrast must carry NO pre-registered bar"
    assert set(("W", "se_realized", "z", "LB95", "UB95", "direction",
                "riders")) <= set(wc)


def test_elo_is_a_coread_not_a_branch_input():
    """Two cells identical on margin but opposite on elo must read the SAME
    branch — elo cannot move a label."""
    base = [{"seed": i, "a_seat": s, "diff": 2.0,
             "won_by_champ": (i % 2 == 0)}
            for i in range(20) for s in (0, 1)]
    flipped = [dict(r, won_by_champ=not r["won_by_champ"]) for r in base]
    m1 = L.paired_margin(base)
    m2 = L.paired_margin(flipped)
    assert m1[0] == m2[0]
    assert (L.branch_for_cell(m1[0], 0.4, gates_ok=True)
            == L.branch_for_cell(m2[0], 0.4, gates_ok=True))


# =========================================================================== #
# 8. THE FIXTURE TRAP                                                          #
# =========================================================================== #

REAL_EMITTER_FIELDS = ("code_rev", "host", "utc", "carc_rs_build",
                       "carc_rs_binary_sha", "rust_toolchain", "rules_profile",
                       "cand_tiearb", "opp_tiearb", "mixed_builds")


@pytest.mark.parametrize("cell", sorted(L.CELLS))
def test_fixtures_are_from_a_real_emitter(cell):
    fx = HERE / "selftest_fixture" / cell
    assert fx.is_dir(), f"{cell}: no fixture — see selftest_fixture/README.md"
    man = json.loads((fx / "manifest.json").read_text())
    for f in REAL_EMITTER_FIELDS:
        assert f in man, f"{cell}: manifest lacks {f} — hand-authored fixture?"
    summ = json.loads((fx / "summary.json").read_text())
    assert summ.get("asymmetric_budgets") is True
    assert len(list(fx.glob("seed*_a*.json"))) >= 4
    assert (fx / "PINNED_SRC_REV").read_text().strip()
    assert (fx / "CLAIMED_BAND").read_text().strip()


@pytest.mark.parametrize("cell", sorted(L.CELLS))
def test_fixtures_express_this_rounds_shape(cell):
    """The fixture must express the LAUNCHER's CLI shape: the candidate's total
    exactly 2x the opponent's, allocated as this cell allocates it, and BOTH
    seats armed at the deployed spec."""
    fx = HERE / "selftest_fixture" / cell
    man = json.loads((fx / "manifest.json").read_text())
    summ = json.loads((fx / "summary.json").read_text())
    assert L.budget_ratio_gate(man, summ, cell)["ok"]
    assert L.tiearb_sides_gate(man)["ok"]
    assert L.tiearb_fired_gate(summ)["ok"], \
        "both seats' arbiters must have FIRED in play, not merely been requested"
    # ...and it must be a REDUCED-budget fixture, so the magnitude gate fails
    assert not L.budget_gate(man, summ, cell)["ok"]


@pytest.mark.parametrize("cell", sorted(L.CELLS))
def test_fixture_seeds_are_in_the_throwaway_range_and_claim_no_band(cell):
    fx = HERE / "selftest_fixture" / cell
    for p in fx.glob("seed*_a*.json"):
        seed = int(p.name[len("seed"):p.name.index("_a")])
        assert L.THROWAWAY_BASE <= seed < L.THROWAWAY_BASE + L.THROWAWAY_SPAN, \
            f"{p.name} is outside the throwaway range — a fixture must never " \
            f"sit on a claimable band"


def test_no_band_is_claimed_by_this_build():
    assert not (HERE / "BAND_CLAIMED").exists(), \
        "this build must NOT claim a band — only BAND_CLAIMED.placeholder"
    assert (HERE / "BAND_CLAIMED.placeholder").exists()


def test_blind_commit_starts_pending():
    bc = json.loads((HERE / "BLIND_COMMIT.json").read_text())
    assert bc["blind_commit"] == "PENDING" or L.is_hex40(bc["blind_commit"])


def test_launcher_gitignores_its_own_runtime_files():
    """The defect fixed in 9dc5da13: a launcher whose own runtime files trip
    its own dirty-guard."""
    ign = (HERE / ".gitignore").read_text()
    for pat in ("RUN_LIVE_*.json", "PINNED_SRC_REV", "VERDICT.json"):
        assert pat in ign, pat
