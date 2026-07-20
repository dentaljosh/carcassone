"""F3 §3.2/§3.4 — aggregate the per-root oracle records into the local verdict.

Reads the run_oracle.py record dir and emits:
  * COVERAGE (fully-solved fraction) — a KILL is INVALID if coverage is low (§5.4);
  * paired mean pooled-Q regret vs the exact optimum (+ bootstrap 95% CI) — PRIMARY;
  * regret REDUCTION of coverage-corrected / pooled-N picks vs pooled-Q (+ paired CI);
  * top-action agreement per selector; coverage distribution of the pooled-Q pick and
    of the exact-best action; by-K and by-stratum breakdowns;
  * strategy-fusion attribution (§3.3): of the nonzero-regret roots where pooled-Q is
    wrong, what share is fusion-flagged (mechanism = fusion) vs coverage-flagged
    (mechanism = selection bias) vs neither (sampling noise);
  * the pre-registered LOCAL GO / KILL gate (§3.4).

Reports only; writes no governance/results files (out of F3 scope per the task).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

SELECTORS = ["pooled_q", "pooled_n", "covq_neutral", "covq_pessimistic"]


def _load(rec_dir: Path):
    recs, errors, skips, budget_hit = [], [], [], []
    for p in sorted(rec_dir.glob("*.json")):
        if p.name in ("champion_manifest.json", "suite_manifest.json"):
            continue
        o = json.loads(p.read_text())
        if "_error" in o:
            errors.append(o)
        elif "_skip" in o:
            skips.append(o)
        elif not o.get("completed", False):
            budget_hit.append(o)
        else:
            recs.append(o)
    return recs, errors, skips, budget_hit


def _boot_ci(x, n_boot=10000, alpha=0.05, seed=0):
    """Bootstrap CI of the mean of x (paired over roots when x is a per-root diff)."""
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return (float("nan"), float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, x.size, size=(n_boot, x.size))
    means = x[idx].mean(axis=1)
    lo, hi = np.percentile(means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(x.mean()), float(lo), float(hi)


def _regrets(recs, selector):
    return np.array([r["picks"][selector]["regret"] for r in recs
                     if r["picks"][selector]["regret"] is not None], dtype=float)


def _paired(recs, sel_a, sel_b):
    """Per-root (regret_a, regret_b) for roots where both are defined (paired)."""
    a, b = [], []
    for r in recs:
        ra = r["picks"][sel_a]["regret"]
        rb = r["picks"][sel_b]["regret"]
        if ra is not None and rb is not None:
            a.append(ra)
            b.append(rb)
    return np.array(a), np.array(b)


def analyze(rec_dir: Path) -> dict:
    recs, errors, skips, budget_hit = _load(rec_dir)
    n_total = len(recs) + len(budget_hit) + len(skips) + len(errors)
    n_solved = len(recs)
    coverage = n_solved / n_total if n_total else 0.0
    # the decision set: solved AND not effectively decided (a real decision to get wrong)
    decision = [r for r in recs if not r.get("decided", False)]
    n_dec = len(decision)

    out: dict = {
        "n_total": n_total, "n_solved": n_solved, "n_budget_hit": len(budget_hit),
        "n_skips": len(skips), "n_errors": len(errors),
        "coverage_fully_solved": round(coverage, 4),
        "n_decision_roots": n_dec,
    }
    if n_dec == 0:
        out["verdict"] = "NO DECISION ROOTS — inconclusive (mine more / raise budget)"
        return out

    # --- per-selector regret + agreement ---------------------------------------
    per_sel = {}
    for sel in SELECTORS:
        reg = _regrets(decision, sel)
        mean, lo, hi = _boot_ci(reg)
        agree = np.mean([decision[i]["picks"][sel]["in_optimal"]
                         for i in range(n_dec)]) if n_dec else float("nan")
        per_sel[sel] = {
            "mean_regret": round(mean, 4), "ci95": [round(lo, 4), round(hi, 4)],
            "top_action_agreement": round(float(agree), 4), "n": int(reg.size),
        }
    out["per_selector"] = per_sel

    # --- regret reduction of covq / pooled-N vs pooled-Q (paired) ---------------
    reductions = {}
    for sel in ("covq_neutral", "covq_pessimistic", "pooled_n"):
        a, b = _paired(decision, "pooled_q", sel)     # a=pooled_q, b=alt
        if a.size == 0:
            continue
        diff = a - b                                    # >0 => alt reduces regret
        mean_d, lo_d, hi_d = _boot_ci(diff)
        base = a.mean()
        reductions[sel] = {
            "abs_reduction_vs_pooled_q": round(float(mean_d), 4),
            "abs_reduction_ci95": [round(lo_d, 4), round(hi_d, 4)],
            "pct_reduction": (round(float(mean_d / base) * 100, 2) if base > 1e-9 else None),
            "ci_above_zero": bool(lo_d > 0),
        }
    out["regret_reduction"] = reductions

    # --- coverage stats ---------------------------------------------------------
    pq_pick_cov = [r["picks"]["pooled_q"]["coverage"] for r in decision]
    best_cov = [r["exact_best_coverage"] for r in decision]
    kd = decision[0].get("k_dets", 4)
    out["coverage_stats"] = {
        "k_dets": kd,
        "pooled_q_pick_coverage_hist": {int(c): int(np.sum(np.array(pq_pick_cov) == c))
                                        for c in range(0, kd + 1)},
        "exact_best_coverage_hist": {int(c): int(np.sum(np.array(best_cov) == c))
                                     for c in range(0, kd + 1)},
        "mean_pooled_q_pick_coverage": round(float(np.mean(pq_pick_cov)), 3),
        "mean_exact_best_coverage": round(float(np.mean(best_cov)), 3),
    }

    # --- fusion attribution (§3.3) ---------------------------------------------
    wrong = [r for r in decision if (r["picks"]["pooled_q"]["regret"] or 0) > 1e-9]
    fusion_flagged = sum(1 for r in wrong if r.get("fusion_flag"))
    coverage_flagged = sum(1 for r in wrong if r.get("coverage_flag") and not r.get("fusion_flag"))
    neither = len(wrong) - fusion_flagged - coverage_flagged
    out["fusion_attribution"] = {
        "n_pooled_q_wrong": len(wrong),
        "fusion_flagged": fusion_flagged,
        "coverage_flagged_only": coverage_flagged,
        "neither_sampling_noise": neither,
        "fusion_share": (round(fusion_flagged / len(wrong), 3) if wrong else None),
        "mean_fusion_phi_on_wrong": (round(float(np.mean(
            [r["fusion_phi_mean"] for r in wrong if r.get("fusion_phi_mean") is not None])), 4)
            if any(r.get("fusion_phi_mean") is not None for r in wrong) else None),
    }

    # --- by-K breakdown ---------------------------------------------------------
    byk = {}
    for k in sorted({r["k_remaining"] for r in decision}):
        sub = [r for r in decision if r["k_remaining"] == k]
        reg = _regrets(sub, "pooled_q")
        m, lo, hi = _boot_ci(reg)
        byk[int(k)] = {"n": len(sub), "mean_pooled_q_regret": round(m, 4),
                       "ci95": [round(lo, 4), round(hi, 4)]}
    out["by_k"] = byk

    # --- by-stratum breakdown ---------------------------------------------------
    bystrat = {}
    for name in ("contested_farm", "open_city", "live_meeple"):
        sub = [r for r in decision if (r.get("strata") or {}).get(name)]
        if not sub:
            continue
        reg = _regrets(sub, "pooled_q")
        m, lo, hi = _boot_ci(reg)
        bystrat[name] = {"n": len(sub), "mean_pooled_q_regret": round(m, 4),
                         "ci95": [round(lo, 4), round(hi, 4)]}
    out["by_stratum"] = bystrat

    # --- pre-registered LOCAL gate (§3.4) --------------------------------------
    pq = per_sel["pooled_q"]
    pq_mean, pq_lo, pq_hi = pq["mean_regret"], pq["ci95"][0], pq["ci95"][1]
    go_regret = bool(pq_mean >= 0.5 and pq_lo > 0)
    go_reduction = any(v["ci_above_zero"] and (v["pct_reduction"] or 0) >= 25.0
                       for v in reductions.values())
    local_go = bool(go_regret or go_reduction)
    kill = bool(pq["top_action_agreement"] >= 0.95 and pq_hi < 0.2)
    coverage_ok = coverage >= 0.8    # a KILL is invalid if coverage is low (§5.4)

    if local_go:
        verdict = "LOCAL GO — build the chance-node PUCT / public-tree ISMCTS prototype (2nd gate)"
    elif kill and coverage_ok:
        verdict = "LOCAL KILL — close the search-object route; spend on throughput/utility/classical"
    elif kill and not coverage_ok:
        verdict = ("KILL SIGNAL but COVERAGE TOO LOW ({:.0%}) — INVALID; budget-hit roots are the "
                   "hard ones. Raise budget / TT_CAP before trusting a KILL.".format(coverage))
    else:
        verdict = "INCONCLUSIVE — neither GO nor KILL thresholds met (size up n / pair / re-solve)"

    out["gate"] = {
        "local_go_regret_arm": go_regret, "local_go_reduction_arm": go_reduction,
        "local_go": local_go, "local_kill": kill, "coverage_ok": coverage_ok,
        "pooled_q_mean_regret": pq_mean, "pooled_q_regret_ci95": [pq_lo, pq_hi],
        "pooled_q_top_action_agreement": pq["top_action_agreement"],
    }
    out["verdict"] = verdict
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rec-dir", required=True, help="run_oracle.py --out-dir")
    ap.add_argument("--out", default=None, help="write the verdict JSON here (default: <rec-dir>/VERDICT.json)")
    args = ap.parse_args(argv)
    rec_dir = Path(args.rec_dir)
    res = analyze(rec_dir)
    outp = Path(args.out) if args.out else rec_dir / "VERDICT.json"
    outp.write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
    print(f"\nwrote {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
