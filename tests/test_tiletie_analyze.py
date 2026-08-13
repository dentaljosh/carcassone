"""Contracts for `scripts/tiletie/analyze_tiletie.py` — the DESIGN.md §4 read-out.

Unit tests only. No oracle runs, no engine, no subprocesses. Every corpus is synthetic
and every expected number is hand-computed from DESIGN.md's own formulas, so the
estimators are checked against arithmetic rather than against themselves.

Covers:
  1. S1a variance components -- hand-computed sigma2_arm, incl. the SIGNED negative that
     §4.1 forbids truncating, and invariance to a pure CRN world effect
  2. the §4.1 parity cross-fit -- disjointness, the one-based DESIGN reading, and the
     property that makes it exist (a pure selection artefact cross-fits to 0 while the
     naive range does not)
  3. S2 / S2b regret -- hand-computed headroom, and E[R] = 0 requiring the comparator in
     the selection pool
  4. the §4.3 bound chain against the DESIGN-published Kelo = 97.5, and its inverse
  5. the null path: a ZERO-SPREAD corpus must emit branch 1 WITH an explicit pts/ply and
     elo bound (never "ties don't matter")
  6. the §0.A dropped-zeros accounting -- per-stratum rates, the zeros_strict variant for
     the 72 played-outside-the-tie-set rows, and the exact (1-p)*mean identity
  7. partial-corpus handling -- completion accounting, the loud missing statement, and the
     default refusal to mix incomplete arm complements into the headline
  8. the §2.1 CRN witness -- values_a drift is detected
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO / "scripts" / "tiletie",):
    sp = str(_p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import analyze_tiletie as AT  # noqa: E402


# --------------------------------------------------------------------------- #
# 1. S1a -- variance components (DESIGN §4.1)                                   #
# --------------------------------------------------------------------------- #
def test_sigma2_arm_matches_hand_computation_pure_arm_effect():
    """V[0]=[0,0,0,0], V[1]=[2,2,2,2]: no world effect, no residual.

    row means 0 / 2, grand 1, col means all 1.
    MS_arm   = M * sum((rm-grand)^2) / (A-1) = 4 * (1+1) / 1 = 8
    MS_resid = 0
    sigma2_arm = (8 - 0) / 4 = 2  ==  Var([0, 2], ddof=1)
    """
    vc = AT.variance_components([[0.0] * 4, [2.0] * 4])
    assert vc["ms_arm"] == pytest.approx(8.0)
    assert vc["ms_resid"] == pytest.approx(0.0)
    assert vc["sigma2_arm"] == pytest.approx(2.0)


def test_sigma2_arm_is_zero_under_a_pure_crn_world_effect():
    """Blocking on the world is the whole point: a shared world swing is NOT arm spread."""
    vc = AT.variance_components([[1.0, 3.0, -5.0, 9.0], [1.0, 3.0, -5.0, 9.0]])
    assert vc["ms_arm"] == pytest.approx(0.0)
    assert vc["sigma2_arm"] == pytest.approx(0.0)


def test_sigma2_arm_keeps_its_sign_when_negative():
    """§4.1: 'The signed value is kept, including when negative' -- truncating at 0 would
    reintroduce exactly the upward bias the estimator exists to remove.

    V[0]=[0,4], V[1]=[4,0]: pure antisymmetric noise, no arm effect.
    MS_arm = 0; residuals are (-2, 2, 2, -2) => SS 16, df 1 => MS_resid 16.
    sigma2_arm = (0 - 16) / 2 = -8.
    """
    vc = AT.variance_components([[0.0, 4.0], [4.0, 0.0]])
    assert vc["ms_resid"] == pytest.approx(16.0)
    assert vc["sigma2_arm"] == pytest.approx(-8.0)
    assert vc["sigma2_arm"] < 0


def test_variance_components_refuses_degenerate_layouts():
    with pytest.raises(ValueError):
        AT.variance_components([[1.0, 2.0]])                 # one arm
    with pytest.raises(ValueError):
        AT.variance_components([[1.0], [2.0]])               # one world
    with pytest.raises(ValueError):
        AT.variance_components([[1.0, 2.0], [3.0]])          # ragged


# --------------------------------------------------------------------------- #
# 2. the parity cross-fit (DESIGN §4.1)                                         #
# --------------------------------------------------------------------------- #
def test_parity_split_is_disjoint_exhaustive_and_one_based_by_default():
    sel, eva = AT.parity_indices(8, base=1)
    assert sel == [1, 3, 5, 7]           # one-based labels 2,4,6,8 = the EVEN (selection) half
    assert eva == [0, 2, 4, 6]
    assert not set(sel) & set(eva)
    assert sorted(sel + eva) == list(range(8))
    sel0, eva0 = AT.parity_indices(8, base=0)
    assert sel0 == eva and eva0 == sel   # the base flips the two halves, nothing else
    ss, es = AT.parity_indices(8, base=1, swap=True)
    assert (ss, es) == (eva, sel)


def test_crossfit_kills_a_pure_selection_artefact_that_the_naive_range_reports():
    """The reason §4.1 rejects naive range statistics.

    Arm 0 is loud on the SELECTION worlds only and identical to arm 1 on the EVALUATION
    worlds. Cross-fit sees 0; the naive range manufactures a positive out of pure noise.
    """
    matrix = [[0.0, 10.0, 0.0, 10.0], [0.0, 0.0, 0.0, 0.0]]
    sel, eva = AT.parity_indices(4, base=1)          # sel = [1,3] (the loud ones)
    gap, a_plus, a_minus = AT.crossfit_gap(matrix, sel, eva)
    assert (a_plus, a_minus) == (0, 1)
    assert gap == pytest.approx(0.0)
    assert AT.naive_gap(matrix) == pytest.approx(5.0)


def test_crossfit_gap_recovers_a_real_gap():
    """A genuine, world-independent 3-pt separation survives the cross-fit intact."""
    matrix = [[0.0] * 4, [3.0] * 4, [1.0] * 4]
    sel, eva = AT.parity_indices(4, base=1)
    gap, a_plus, a_minus = AT.crossfit_gap(matrix, sel, eva)
    assert (a_plus, a_minus) == (1, 0)
    assert gap == pytest.approx(3.0)


# --------------------------------------------------------------------------- #
# 3. S2 / S2b -- regret (DESIGN §4.2)                                           #
# --------------------------------------------------------------------------- #
def test_headroom_hand_computed():
    """comparator = arm 0 at a flat 1 pt; the tie set contains a flat 3-pt arm.

        R        = mean_eva V[0] - mean_eva V[a+] = 1 - 3 = -2   (<= 0: the search missed)
        headroom = +2 pts per tied tile ply
    """
    matrix = [[1.0] * 4, [3.0] * 4]
    sel, eva = AT.parity_indices(4, base=1)
    head, a_plus = AT.crossfit_regret(matrix, sel, eva, comparator=0)
    assert a_plus == 1
    assert head == pytest.approx(2.0)


def test_headroom_is_exactly_zero_when_the_comparator_is_already_the_best():
    matrix = [[3.0] * 4, [1.0] * 4]
    sel, eva = AT.parity_indices(4, base=1)
    head, a_plus = AT.crossfit_regret(matrix, sel, eva, comparator=0)
    assert a_plus == 0 and head == pytest.approx(0.0)


def test_comparator_is_inside_the_selection_pool_so_the_null_expectation_is_zero():
    """§4.2: a+ is selected from a pool that INCLUDES the comparator, which is what makes
    E[R] = 0 EXACTLY under the null. With identical arms the pool must be able to return
    the comparator itself, giving a hard 0 rather than a positive artefact."""
    matrix = [[2.0, 5.0, 2.0, 5.0]] * 3
    sel, eva = AT.parity_indices(4, base=1)
    for comparator in range(3):
        head, _ = AT.crossfit_regret(matrix, sel, eva, comparator)
        assert head == pytest.approx(0.0)


def test_headroom_can_be_negative_under_the_crossfit():
    """The cross-fit is an unbiased TEST, not a non-negative quantity: when the selection
    half picks the wrong arm the evaluation half returns a negative headroom. Clamping it
    would rebuild the bias."""
    # sel = [1,3], eva = [0,2].  arm0: sel mean 0, eva mean 10.  arm1: sel mean 5, eva 0.
    # The selection half therefore crowns arm1, which the evaluation half scores 10 pts
    # BELOW the comparator => headroom -10.
    matrix = [[10.0, 0.0, 10.0, 0.0], [0.0, 5.0, 0.0, 5.0]]
    sel, eva = AT.parity_indices(4, base=1)
    head, a_plus = AT.crossfit_regret(matrix, sel, eva, comparator=0)
    assert a_plus == 1
    assert head == pytest.approx(-10.0)


# --------------------------------------------------------------------------- #
# 4. the bound chain (DESIGN §4.3 / §7.2)                                       #
# --------------------------------------------------------------------------- #
def test_bound_chain_reproduces_the_designs_published_kelo():
    """§7.2: 'Kelo = 97.5 elo per pt per tied tile ply (headroom = 0.10 pts => +9.75 elo)'."""
    assert AT.pts_to_elo(0.10) == pytest.approx(9.75, abs=0.03)
    assert AT.pts_to_elo(0.10) / 0.10 == pytest.approx(AT.KELO_REFERENCE, rel=0.005)


def test_bound_chain_matches_the_sizing_tables_0_174_pts_for_17_elo():
    """§7.2's table: a +-17-elo bound needs 2*se = 0.174 pts."""
    assert AT.elo_to_pts(17.0) == pytest.approx(0.174, abs=0.001)
    assert AT.elo_to_pts(35.0) == pytest.approx(0.359, abs=0.002)


def test_bound_chain_round_trips_and_is_monotone():
    for pts in (-0.4, -0.05, 0.0, 0.05, 0.3):
        assert AT.elo_to_pts(AT.pts_to_elo(pts)) == pytest.approx(pts, abs=1e-9)
    assert AT.pts_to_elo(0.2) > AT.pts_to_elo(0.1) > AT.pts_to_elo(0.0) == pytest.approx(0.0)


def test_low_end_divisor_shrinks_the_bound_by_the_stated_bracket():
    """§4.3: the divisor enters LINEARLY, so 3.2 -> 5.23 is a ~1.63x bracket."""
    hi = AT.pts_to_elo(0.1, non_additivity=AT.NON_ADDITIVITY)
    lo = AT.pts_to_elo(0.1, non_additivity=AT.NON_ADDITIVITY_LOW_END)
    assert hi / lo == pytest.approx(AT.NON_ADDITIVITY_LOW_END / AT.NON_ADDITIVITY, rel=0.01)


# --------------------------------------------------------------------------- #
# synthetic corpus builder                                                      #
# --------------------------------------------------------------------------- #
def _write_corpus(tmp_path, positions, *, m=8, drop_rows=None, built=None,
                  omit=(), drift_rid=None):
    """Build a plan dir + a records tree from a compact spec.

    `positions` is a list of dicts: rid, root_id, stratum, rules_profile, arms (list of
    per-arm constant values -- index 0 is the reference), champ_arm_index, phase_bucket.
    `omit` is a set of (rid, leg) pairs to leave unwritten (partial-corpus simulation).
    """
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    rec_root = tmp_path / "records_root"
    arms_index, counts = {}, {}
    for p in positions:
        vals = p["arms"]
        n = len(vals)
        arms_index[p["rid"]] = {
            "arms": list(range(100, 100 + n)),
            "capped": p.get("capped", False),
            "champ_action": 100 + p.get("champ_arm_index", 0),
            "champ_arm_action": 100 + p.get("champ_arm_index", 0),
            "champ_arm_index": p.get("champ_arm_index", 0),
            "champ_outside_tieset": False, "champ_pick_missing": False,
            "deck_seed": 1, "game_label": "g", "gap": 1.0, "k_remaining": 10,
            "n_cand": n, "n_distinct_afterstates": n, "n_legal": n,
            "phase_bucket": p.get("phase_bucket", "mid"), "ply": 10,
            "root_id": p["root_id"], "rules_profile": p["rules_profile"], "seat": 1,
            "source": "synthetic", "stratum": p["stratum"], "tercile": 1,
            "tie_size_exact": n,
        }
        for leg in range(1, n):
            key = f"{p['rules_profile']}/leg{leg}"
            counts[key] = counts.get(key, 0) + 1
            if (p["rid"], leg) in omit:
                continue
            d = rec_root / p["rules_profile"] / f"leg{leg}" / "records"
            d.mkdir(parents=True, exist_ok=True)
            va = list(_row(vals[0], m))
            if drift_rid == p["rid"] and leg > 1:
                va[0] += 1.0                      # §2.1 witness violation
            (d / f"{p['rid']}.json").write_text(json.dumps({
                "rid": p["rid"], "root_id": p["root_id"], "m": m,
                "pick_a": 100, "pick_b": 100 + leg,
                "values_a": va, "values_b": list(_row(vals[leg], m)),
                "world_seeds": list(range(m)), "playout_seeds": list(range(m, 2 * m)),
                "crn_verified": True, "checksum_ok": True, "ok": True,
                "distinct_afterstates": m, "elapsed_secs": 1.0,
            }))
    plan = {
        "schema": "carcassonne-tiletie-positions/v1", "cap_j": 4, "m_worlds": m,
        "n_positions": len(positions), "counts_by_profile_leg": counts,
        "counts_by_stratum": _by(positions, "stratum"),
        "afterstate_dedupe": {
            "applied": True,
            "n_dropped_all_transposition": len(drop_rows or []),
            "n_dropped_by_stratum": _by(drop_rows or [], "stratum"),
            "n_dropped_with_action_played_outside_tieset": sum(
                1 for r in (drop_rows or []) if r["action_played_outside_tieset"]),
            "n_qualifying_before_drop": sum((built or {}).values()) + len(drop_rows or []),
        },
    }
    (plan_dir / "POSITIONS_PLAN.json").write_text(json.dumps(plan))
    (plan_dir / "ARMS.json").write_text(json.dumps(arms_index))
    (plan_dir / "DROPPED_ALL_TRANSPOSITION.json").write_text(json.dumps(
        {"schema": "carcassonne-tiletie-positions/v1", "n": len(drop_rows or []),
         "note": "synthetic", "rows": drop_rows or []}))
    full = None
    if built:
        full = tmp_path / "full_plan.json"
        full.write_text(json.dumps({"counts_by_stratum": built}))
    return plan_dir, rec_root, full


def _row(v, m):
    """A constant arm value with a large, ARM-INDEPENDENT world effect: the world effect
    must be invisible to every §4 statistic (they all block on the CRN world). A list is
    passed through verbatim, for arms whose per-world pattern is the point."""
    if isinstance(v, (list, tuple)):
        assert len(v) == m
        return list(v)
    return [v + 7.0 * math.sin(j) for j in range(m)]


def _by(rows, key):
    out = {}
    for r in rows:
        out[r[key]] = out.get(r[key], 0) + 1
    return out


def _drop(stratum, i, outside=False):
    return {"rid": f"d{stratum}{i}", "root_id": f"dr{stratum}{i}", "stratum": stratum,
            "rules_profile": "walled", "action_played": 1, "n_distinct_afterstates": 1,
            "action_played_outside_tieset": outside, "phase_bucket": "mid", "ply": 1,
            "deck_seed": 1, "game_label": "g", "source": "synthetic", "tercile": 1,
            "tie_size_exact": 2}


def _run(plan_dir, rec_root, out_dir, full=None, extra=()):
    argv = ["--plan-dir", str(plan_dir), "--records-root", str(rec_root),
            "--out-dir", str(out_dir), "--bootstrap", "400", "--census-summary", "/nonexistent"]
    if full:
        argv += ["--full-supply-plan", str(full)]
    argv += list(extra)
    rc = AT.main(argv)
    assert rc == 0
    return json.loads((out_dir / "VERDICT.json").read_text()), (out_dir / "VERDICT.md").read_text()


# --------------------------------------------------------------------------- #
# 5. the NULL path -- a zero-spread corpus must emit an explicit BOUND           #
# --------------------------------------------------------------------------- #
@pytest.fixture
def zero_spread_corpus(tmp_path):
    """40 positions, every arm identical: spread is EXACTLY 0 and headroom EXACTLY 0."""
    pos = [{"rid": f"p{i}", "root_id": f"r{i // 2}", "stratum": "selfplay",
            "rules_profile": "walled", "arms": [4.0, 4.0, 4.0],
            "champ_arm_index": 0} for i in range(40)]
    drops = [_drop("selfplay", i, outside=(i % 5 == 0)) for i in range(10)]
    return _write_corpus(tmp_path, pos, drop_rows=drops,
                         built={"selfplay": 40}) + (tmp_path,)


def test_zero_spread_corpus_yields_exactly_zero_estimators(zero_spread_corpus):
    plan_dir, rec_root, full, tmp = zero_spread_corpus
    v, _ = _run(plan_dir, rec_root, tmp / "out", full)
    b = v["results"]["blocks"]["pooled"]
    assert b["S1a_sigma2_arm_discriminable"]["mean"] == pytest.approx(0.0, abs=1e-12)
    assert b["S1b_gap_discriminable"]["mean"] == pytest.approx(0.0, abs=1e-12)
    assert b["S2_headroom_J4_discriminable"]["mean"] == pytest.approx(0.0, abs=1e-12)
    assert b["S2b_headroom_leaf_discriminable"]["mean"] == pytest.approx(0.0, abs=1e-12)
    # even the naive range is 0 here -- there is no noise for it to capitalise on
    assert b["NAIVE_never_quote"]["gap_naive"]["mean"] == pytest.approx(0.0, abs=1e-12)


def test_null_path_fires_branch_1_with_an_explicit_pts_and_elo_bound(zero_spread_corpus):
    """§4.4 branch 1 + §1: 'a null here has to ship an explicit pts/ply and elo bound,
    never the sentence "ties don't matter"'."""
    plan_dir, rec_root, full, tmp = zero_spread_corpus
    v, md = _run(plan_dir, rec_root, tmp / "out", full)
    assert v["results"]["branch"] == 1
    bound = v["results"]["composites"]["pooled"]["headline"]["bound"]
    assert bound["pts_per_tied_tile_ply"]["ci95_hi"] is not None
    assert bound["elo"]["ci95_hi"] is not None
    assert bound["elo"]["ci95_hi"] < AT.ELO_CLOSE_BAR
    # the bound must be QUOTED in the markdown, in BOTH units, with the 1.6x bracket
    assert "pts/tied tile ply" in md
    assert "elo 95% CI" in md
    assert "5.23" in md
    assert "CLOSED WITH A BOUND" in md
    # the ONLY appearance of the forbidden sentence is the explicit prohibition of it
    assert md.count("ties don't matter") == 1
    assert "does NOT license 'ties don't matter'" in md


def test_a_degenerate_zero_width_interval_does_not_claim_the_spread_excludes_zero(
        zero_spread_corpus):
    """An all-identical corpus has se == 0 exactly; float dust in the bootstrap must not
    be reported as 'the spread CI excludes 0'."""
    plan_dir, rec_root, full, tmp = zero_spread_corpus
    v, _ = _run(plan_dir, rec_root, tmp / "out", full)
    assert v["results"]["spread_ci_excludes_zero"] is False
    assert v["results"]["branch_3_condition_also_met"] is False
    assert v["results"]["sizing"] is None          # no se => no arithmetic extension claim
    assert AT.decide_branch(5.0, -5.0, 1e-30, 1e-30, sigma2_se=0.0) == (1, False, False)


def test_null_path_still_reports_no_conviction_on_a_sub_2_z(zero_spread_corpus):
    """Read-rule: |z| < 2 is no conviction, even when the branch closes."""
    plan_dir, rec_root, full, tmp = zero_spread_corpus
    v, md = _run(plan_dir, rec_root, tmp / "out", full)
    rr = v["results"]["read_rules"]
    assert rr["z_conviction_bar"] == 2.0
    assert rr["S2_has_conviction"] is False
    assert "NO conviction" in md


def test_scope_sentence_travels_with_the_null(zero_spread_corpus):
    """§5: a null through clair-puct closes 'spread visible to a deep clairvoyant search
    over THIS leaf', not 'spread in truth'."""
    plan_dir, rec_root, full, tmp = zero_spread_corpus
    _, md = _run(plan_dir, rec_root, tmp / "out", full)
    assert "spread in truth" in md
    assert "tier1-greedy" in md


# --------------------------------------------------------------------------- #
# 6. the §0.A dropped-zeros accounting                                          #
# --------------------------------------------------------------------------- #
def test_zero_rates_are_per_stratum_and_use_qualifying_as_the_denominator(tmp_path):
    pos = [{"rid": f"p{i}", "root_id": f"r{i}", "stratum": "selfplay",
            "rules_profile": "walled", "arms": [0.0, 1.0], "champ_arm_index": 0}
           for i in range(4)]
    drops = ([_drop("selfplay", i, outside=(i < 4)) for i in range(20)]
             + [_drop("e4", i, outside=(i < 2)) for i in range(10)])
    plan_dir, rec_root, full = _write_corpus(
        tmp_path, pos, drop_rows=drops, built={"selfplay": 80, "e4": 40})
    rates = AT.zero_rates(AT.load_plan(plan_dir), full)
    sp = rates["by_stratum"]["selfplay"]
    assert sp["n_qualifying"] == 100 and sp["n_dropped"] == 20
    assert sp["p_all"] == pytest.approx(0.20)
    assert sp["scale_all"] == pytest.approx(0.80)
    # 16 of the 20 have the played action INSIDE the tie set -> the strict rate is 16/100
    assert sp["p_strict"] == pytest.approx(0.16)
    assert sp["scale_strict"] == pytest.approx(0.84)
    e4 = rates["by_stratum"]["e4"]
    assert e4["n_qualifying"] == 50 and e4["p_all"] == pytest.approx(0.20)
    assert "per-stratum" in rates["source"]


def test_zero_rates_fall_back_loudly_without_the_full_supply_plan(tmp_path):
    pos = [{"rid": "p0", "root_id": "r0", "stratum": "selfplay", "rules_profile": "walled",
            "arms": [0.0, 1.0], "champ_arm_index": 0}]
    drops = [_drop("selfplay", i) for i in range(20)]
    plan_dir, rec_root, _ = _write_corpus(tmp_path, pos, drop_rows=drops,
                                          built={"selfplay": 80})
    rates = AT.zero_rates(AT.load_plan(plan_dir), None)
    assert "POOLED FALLBACK" in rates["source"]
    assert rates["by_stratum"]["selfplay"]["n_qualifying"] is None


def test_analytic_zeros_dilute_the_estimate_by_exactly_one_minus_p(tmp_path):
    """§6: `headroom_all = 0.74 x headroom_discriminable`. The zeros have zero value AND
    zero variance and their COUNT is known, so the dilution is an exact identity -- the
    point estimate, the se and both CI ends all scale by (1 - p_drop)."""
    pos = [{"rid": f"p{i}", "root_id": f"r{i}", "stratum": "selfplay",
            "rules_profile": "walled", "arms": [0.0, 2.0 + 0.1 * i], "champ_arm_index": 0}
           for i in range(12)]
    drops = [_drop("selfplay", i) for i in range(25)]     # 25 of 100 qualifying
    plan_dir, rec_root, full = _write_corpus(tmp_path, pos, drop_rows=drops,
                                             built={"selfplay": 75})
    v, _ = _run(plan_dir, rec_root, tmp_path / "out", full)
    b = v["results"]["blocks"]["pooled"]
    disc, allv = b["S2_headroom_J4_discriminable"], b["S2_headroom_J4_all"]
    assert allv["mean"] == pytest.approx(0.75 * disc["mean"])
    assert allv["se_cluster"] == pytest.approx(0.75 * disc["se_cluster"])
    assert allv["boot_hi"] == pytest.approx(0.75 * disc["boot_hi"], rel=1e-9)
    # the z is invariant to the dilution -- it is a pure scale change
    assert allv["z"] == pytest.approx(disc["z"])
    # and S1a gets the same treatment
    assert (b["S1a_sigma2_arm_all"]["mean"]
            == pytest.approx(0.75 * b["S1a_sigma2_arm_discriminable"]["mean"]))


def test_zeros_strict_is_the_larger_magnitude_sensitivity_not_the_headline(tmp_path):
    """§0.A: on the rows whose played action is OUTSIDE the tie set the analytic zero
    covers the tie-set arms only, so S2 carries them as a per-row sensitivity. Counting
    fewer zeros dilutes less => a LARGER magnitude => conservative against closure."""
    pos = [{"rid": f"p{i}", "root_id": f"r{i}", "stratum": "selfplay",
            "rules_profile": "walled", "arms": [0.0, 3.0], "champ_arm_index": 0}
           for i in range(8)]
    drops = [_drop("selfplay", i, outside=(i < 10)) for i in range(30)]
    plan_dir, rec_root, full = _write_corpus(tmp_path, pos, drop_rows=drops,
                                             built={"selfplay": 70})
    v, md = _run(plan_dir, rec_root, tmp_path / "out", full)
    b = v["results"]["blocks"]["pooled"]
    assert (abs(b["S2_headroom_J4_all_zeros_strict"]["mean"])
            > abs(b["S2_headroom_J4_all"]["mean"]))
    assert v["results"]["composites"]["pooled"]["headline"]["source_statistic"] \
        == "S2_headroom_J4_all"
    assert "zeros_strict" in v["results"]["composites"]["pooled"]
    assert "zeros_strict" in md


def test_dropped_index_counts_are_reported_verbatim(tmp_path):
    pos = [{"rid": "p0", "root_id": "r0", "stratum": "selfplay", "rules_profile": "walled",
            "arms": [0.0, 1.0], "champ_arm_index": 0}]
    drops = [_drop("selfplay", i, outside=(i < 3)) for i in range(11)]
    plan_dir, rec_root, full = _write_corpus(tmp_path, pos, drop_rows=drops,
                                             built={"selfplay": 39})
    v, md = _run(plan_dir, rec_root, tmp_path / "out", full)
    sp = v["zero_rates"]["by_stratum"]["selfplay"]
    assert sp["n_dropped"] == 11 and sp["n_dropped_inside_tieset"] == 8
    assert "analytic zeros" in md


# --------------------------------------------------------------------------- #
# 7. partial-corpus handling                                                    #
# --------------------------------------------------------------------------- #
@pytest.fixture
def partial_corpus(tmp_path):
    """20 three-arm positions; 6 are missing their leg-2 record, 3 are missing entirely."""
    pos = [{"rid": f"p{i}", "root_id": f"r{i}", "stratum": "selfplay",
            "rules_profile": "walled", "arms": [0.0, 1.0, 2.0], "champ_arm_index": 1}
           for i in range(20)]
    omit = {(f"p{i}", 2) for i in range(6)} | {(f"p{i}", 1) for i in range(17, 20)} \
        | {(f"p{i}", 2) for i in range(17, 20)}
    return _write_corpus(tmp_path, pos, drop_rows=[_drop("selfplay", 0)],
                         built={"selfplay": 99}, omit=omit) + (tmp_path,)


def test_partial_corpus_accounting_is_exact(partial_corpus):
    plan_dir, rec_root, full, tmp = partial_corpus
    v, md = _run(plan_dir, rec_root, tmp / "out", full)
    c = v["completion"]
    assert c["planned_positions"] == 20
    assert c["scored_complete"] == 11        # 20 - 6 partial - 3 absent
    assert c["scored_partial"] == 6
    assert c["absent"] == 3
    assert c["n_analysed"] == 11             # partials excluded from the headline by default
    assert c["partial"] is True
    assert c["by_profile"]["walled"]["planned"] == 20
    assert c["by_stratum"]["selfplay"]["complete"] == 11


def test_partial_corpus_states_the_missing_legs_loudly(partial_corpus):
    plan_dir, rec_root, full, tmp = partial_corpus
    v, md = _run(plan_dir, rec_root, tmp / "out", full)
    ml = v["completion"]["missing_legs_by_profile_leg"]
    assert ml["walled/leg1"] == {"planned": 20, "present": 17, "missing": 3}
    assert ml["walled/leg2"] == {"planned": 20, "present": 11, "missing": 9}
    assert v["completion"]["missing_statement"].startswith("INCOMPLETE")
    assert "PARTIAL" in v["status_banner"]
    assert "PARTIAL CORPUS" in md
    assert "9" in md and "walled/leg2" in md


def test_partial_arms_are_admitted_only_on_an_explicit_flag(partial_corpus):
    """The missing legs are the HIGH action indices, which is NOT the seeded uniform draw
    §4.6's cap-invariance argument needs -- so mixing them in is opt-in."""
    plan_dir, rec_root, full, tmp = partial_corpus
    v, _ = _run(plan_dir, rec_root, tmp / "out2", full, extra=["--include-partial-arms"])
    assert v["completion"]["n_analysed"] == 17
    assert v["args"]["include_partial_arms"] is True


def test_a_complete_corpus_is_not_stamped_partial(tmp_path):
    pos = [{"rid": f"p{i}", "root_id": f"r{i}", "stratum": "selfplay",
            "rules_profile": "walled", "arms": [0.0, 1.0], "champ_arm_index": 0}
           for i in range(6)]
    plan_dir, rec_root, full = _write_corpus(tmp_path, pos, drop_rows=[_drop("selfplay", 0)],
                                             built={"selfplay": 29})
    v, md = _run(plan_dir, rec_root, tmp_path / "out", full)
    assert v["completion"]["partial"] is False
    assert v["completion"]["missing_statement"].startswith("COMPLETE")
    assert "PARTIAL CORPUS" not in md


def test_only_profiles_scopes_the_read_and_says_so(tmp_path):
    pos = ([{"rid": f"w{i}", "root_id": f"rw{i}", "stratum": "selfplay",
             "rules_profile": "walled", "arms": [0.0, 1.0], "champ_arm_index": 0}
            for i in range(6)]
           + [{"rid": f"f{i}", "root_id": f"rf{i}", "stratum": "e4",
               "rules_profile": "fixed_v1", "arms": [0.0, 1.0], "champ_arm_index": 0}
              for i in range(4)])
    omit = {(f"f{i}", 1) for i in range(4)}          # the fixed_v1 arm has not run
    plan_dir, rec_root, full = _write_corpus(
        tmp_path, pos, drop_rows=[_drop("selfplay", 0), _drop("e4", 0)],
        built={"selfplay": 29, "e4": 19}, omit=omit)
    v, md = _run(plan_dir, rec_root, tmp_path / "out", full,
                 extra=["--only-profiles", "walled"])
    assert v["completion"]["planned_positions"] == 6
    assert "SCOPE RESTRICTED" in v["completion"]["missing_statement"]
    assert "walled" in md


# --------------------------------------------------------------------------- #
# 8. the §2.1 CRN integrity witness                                             #
# --------------------------------------------------------------------------- #
def test_values_a_drift_across_legs_is_detected(tmp_path):
    """§2.1: the reference arm is re-scored in EVERY leg under identical (world, playout)
    seeds, so values_a must be bit-identical across legs. Drift VOIDS the run."""
    pos = [{"rid": "p0", "root_id": "r0", "stratum": "selfplay", "rules_profile": "walled",
            "arms": [0.0, 1.0, 2.0], "champ_arm_index": 0}]
    plan_dir, rec_root, full = _write_corpus(tmp_path, pos, drop_rows=[_drop("selfplay", 0)],
                                             built={"selfplay": 9}, drift_rid="p0")
    v, md = _run(plan_dir, rec_root, tmp_path / "out", full)
    assert len(v["integrity"]["values_a_drift"]) == 1
    assert v["integrity"]["values_a_drift"][0]["rid"] == "p0"
    assert "values_a_drift" in md


def test_clean_corpus_has_an_empty_integrity_ledger(tmp_path):
    pos = [{"rid": f"p{i}", "root_id": f"r{i}", "stratum": "selfplay",
            "rules_profile": "walled", "arms": [0.0, 1.0, 2.0], "champ_arm_index": 2}
           for i in range(5)]
    plan_dir, rec_root, full = _write_corpus(tmp_path, pos, drop_rows=[_drop("selfplay", 0)],
                                             built={"selfplay": 29})
    v, _ = _run(plan_dir, rec_root, tmp_path / "out", full)
    assert all(len(x) == 0 for x in v["integrity"].values())


# --------------------------------------------------------------------------- #
# 9. wiring: the branch map, the cap extrapolation and the governance stamp      #
# --------------------------------------------------------------------------- #
def test_branch_precedence_is_literal_and_branch_3_is_flagged_not_reordered():
    """INTERPRETATIONS I4: branch 3's condition contains branch 1's, so under the
    pre-registered first-match precedence branch 3 is unreachable. We honour the
    precedence and report the flag."""
    b, b3, nz = AT.decide_branch(elo_hi=5.0, elo_lo=-5.0, sigma2_lo=0.5, sigma2_hi=2.0)
    assert (b, b3, nz) == (1, True, True)          # branch 1 fires, branch 3 also true
    b, b3, _ = AT.decide_branch(elo_hi=50.0, elo_lo=20.0, sigma2_lo=-1.0, sigma2_hi=2.0)
    assert (b, b3) == (2, False)
    b, b3, _ = AT.decide_branch(elo_hi=50.0, elo_lo=-20.0, sigma2_lo=-1.0, sigma2_hi=2.0)
    assert (b, b3) == (4, False)


def test_interpretations_are_shipped_in_both_artifacts(tmp_path):
    pos = [{"rid": f"p{i}", "root_id": f"r{i}", "stratum": "selfplay",
            "rules_profile": "walled", "arms": [0.0, 1.0], "champ_arm_index": 0}
           for i in range(5)]
    plan_dir, rec_root, full = _write_corpus(tmp_path, pos, drop_rows=[_drop("selfplay", 0)],
                                             built={"selfplay": 29})
    v, md = _run(plan_dir, rec_root, tmp_path / "out", full)
    ids = {i["id"] for i in v["interpretations"]}
    assert {"I1-parity-base", "I2-zero-addback-weighting", "I3-the-72-outside-tieset",
            "I4-branch-3-unreachable"} <= ids
    for i in ids:
        assert i in md


def test_headline_applies_the_140x_fullset_extrapolation_and_labels_it(tmp_path):
    pos = [{"rid": f"p{i}", "root_id": f"r{i}", "stratum": "selfplay",
            "rules_profile": "walled", "arms": [0.0, 2.0], "champ_arm_index": 0}
           for i in range(6)]
    plan_dir, rec_root, full = _write_corpus(tmp_path, pos, drop_rows=[_drop("selfplay", 0)],
                                             built={"selfplay": 29})
    v, md = _run(plan_dir, rec_root, tmp_path / "out", full)
    c = v["results"]["composites"]["pooled"]["headline"]
    base = v["results"]["blocks"]["pooled"]["S2_headroom_J4_all"]["mean"]
    assert c["pts"]["mean"] == pytest.approx(AT.FULLSET_EXTRAP * base)
    assert "EXTRAPOLATION, NOT A MEASUREMENT" in c["extrapolation_label"]
    assert "EXTRAPOLATION, NOT A MEASUREMENT" in md or "extrapolation through the" in md


def test_uncapped_only_block_exists_as_the_assumption_free_check(tmp_path):
    """§4.6: 'the read-out additionally reports branch-1/2 arithmetic on the UNCAPPED
    subset alone as the assumption-free check on that extrapolation'."""
    pos = [{"rid": f"p{i}", "root_id": f"r{i}", "stratum": "selfplay",
            "rules_profile": "walled", "arms": [0.0, 1.0], "champ_arm_index": 0,
            "capped": i < 3} for i in range(8)]
    plan_dir, rec_root, full = _write_corpus(tmp_path, pos, drop_rows=[_drop("selfplay", 0)],
                                             built={"selfplay": 29})
    v, _ = _run(plan_dir, rec_root, tmp_path / "out", full)
    assert v["results"]["blocks"]["uncapped_only"]["n_positions"] == 5
    assert v["results"]["blocks"]["capped_only"]["n_positions"] == 3
    assert "uncapped_only" in v["results"]["composites"]


def test_stratum_sign_disagreement_blocks_pooling(tmp_path):
    """§4.4 stratum rule, enforced mechanically."""
    # selfplay: the champion (arm 0) is flatly 4 pts worse         => headroom +4
    # e4: arm 1 looks best on the SELECTION worlds and is 10 pts worse on the EVALUATION
    #     worlds, so the cross-fit returns a NEGATIVE headroom     => headroom -10
    sel_loud = [10.0, 0.0] * 4
    eva_loud = [0.0, 5.0] * 4
    pos = ([{"rid": f"a{i}", "root_id": f"ra{i}", "stratum": "selfplay",
             "rules_profile": "walled", "arms": [0.0, 4.0], "champ_arm_index": 0}
            for i in range(6)]
           + [{"rid": f"b{i}", "root_id": f"rb{i}", "stratum": "e4",
               "rules_profile": "walled", "arms": [sel_loud, eva_loud],
               "champ_arm_index": 0}
              for i in range(6)])
    plan_dir, rec_root, full = _write_corpus(
        tmp_path, pos, drop_rows=[_drop("selfplay", 0), _drop("e4", 0)],
        built={"selfplay": 29, "e4": 19})
    v, md = _run(plan_dir, rec_root, tmp_path / "out", full)
    pr = v["results"]["pooling_rule"]
    assert set(pr["stratum_means_pts"]) == {"selfplay", "e4"}
    assert pr["stratum_means_pts"]["selfplay"] > 0 > pr["stratum_means_pts"]["e4"]
    assert pr["sign_disagreement"] is True
    assert pr["stratum_n"] == {"selfplay": 6, "e4": 6}
    assert "FORBIDS pooling" in pr["verdict"]
    # both strata are n=6, so the underpowered warning must ride along with the rule
    assert pr["underpowered_strata_n_lt_30"] == {"selfplay": 6, "e4": 6}
    assert "NOT evidence of a real stratum difference" in pr["verdict"]
    assert "stratum:selfplay" in v["results"]["blocks"]
    assert "stratum:e4" in v["results"]["blocks"]


def test_plan_without_the_dedupe_is_refused(tmp_path):
    """§0.A guard rail: the analytic-zero population is undefined for a pre-dedupe plan."""
    pos = [{"rid": "p0", "root_id": "r0", "stratum": "selfplay", "rules_profile": "walled",
            "arms": [0.0, 1.0], "champ_arm_index": 0}]
    plan_dir, _, _ = _write_corpus(tmp_path, pos, drop_rows=[], built={"selfplay": 1})
    p = plan_dir / "POSITIONS_PLAN.json"
    d = json.loads(p.read_text())
    d["afterstate_dedupe"]["applied"] = False
    p.write_text(json.dumps(d))
    with pytest.raises(SystemExit):
        AT.load_plan(plan_dir)


def test_governance_block_forbids_a_results_csv_row(tmp_path):
    pos = [{"rid": f"p{i}", "root_id": f"r{i}", "stratum": "selfplay",
            "rules_profile": "walled", "arms": [0.0, 1.0], "champ_arm_index": 0}
           for i in range(5)]
    plan_dir, rec_root, full = _write_corpus(tmp_path, pos, drop_rows=[_drop("selfplay", 0)],
                                             built={"selfplay": 29})
    v, md = _run(plan_dir, rec_root, tmp_path / "out", full)
    assert "results.csv" in v["governance"] and "0 games" in v["governance"]
    assert "PRODUCTION.yaml` untouched" in md


def test_per_position_jsonl_is_emitted_for_the_mining_step(tmp_path):
    """§4.4 branch 2's next step needs the per-position records (which arm was a+)."""
    pos = [{"rid": f"p{i}", "root_id": f"r{i}", "stratum": "selfplay",
            "rules_profile": "walled", "arms": [0.0, 1.0, 5.0], "champ_arm_index": 0}
           for i in range(4)]
    plan_dir, rec_root, full = _write_corpus(tmp_path, pos, drop_rows=[_drop("selfplay", 0)],
                                             built={"selfplay": 29})
    _run(plan_dir, rec_root, tmp_path / "out", full)
    lines = [json.loads(x) for x in
             (tmp_path / "out" / "per_position.jsonl").read_text().splitlines()]
    assert len(lines) == 4
    assert lines[0]["a_plus_gap"] == 2          # the 5.0 arm, by its PLAN arm index
    assert lines[0]["sigma2_arm"] > 0
