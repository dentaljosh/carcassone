#!/usr/bin/env python3
"""Adjudicate the PRE-REGISTERED G2 bars (measurement/paper_g2_20260803/PREREG.md
sect 4-5) off the solver_score report + the per-arm training histories.

Arithmetic is IMPORTED-BY-COPY from measurement/value_unlock_20260730/analyze_ruler.py
(the paired sign-z convention of analyze_v210_screen.py:33 and the
bootstrap-over-roots sigma of solver_score_agent.bootstrap_block) so the G2
numbers are produced by the same code path as the CL-073 numbers they are
compared against. No new metric is defined here.

Read-only. Prints JSON.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
WT = HERE.parent.parent
CKROOT = Path("/mnt/c/carc-shared/paper_g2_20260803")

# --- PRE-REGISTERED constants (PREREG.md sect 4.3 / sect 5) -----------------
LEAF_SELFCHECK = {"solver_regret_mean": 0.9508, "top1_rate": 0.6095,
                  "tau_mean": 0.6153}
BASELINE = "curve125"
HEADLINE = "g2_tf_match_best"
R_HEURISTIC_REF = 0.61      # train_iter.py:706 -- Branch A requires r >= this
R_FIT_GATE = 0.55           # PREREG 4.2(2)
ENTROPY_FLOOR = 0.8002      # PREREG 4.2(3) = 0.50 x 1.6004
TAU_PARTIAL = 0.30          # PREREG 5 Branch B-partial == CL-064's LIVE threshold
SIGN_Z = 2.0


def paired(roots, name, baseline):
    """analyze_ruler.py:paired, verbatim arithmetic."""
    better = worse = tie = 0
    dsum = 0.0
    for r in roots:
        rb = r["rankers"][baseline]["solver_regret"]
        rv = r["rankers"][name]["solver_regret"]
        dsum += rv - rb
        if rv < rb:
            better += 1
        elif rv > rb:
            worse += 1
        else:
            tie += 1
    z = (better - worse) / math.sqrt(better + worse) if (better + worse) else 0.0
    return {"vs": baseline, "better": better, "worse": worse, "tie": tie,
            "sign_z": round(z, 3), "mean_dregret": round(dsum / len(roots), 4)}


def tau_boot(roots, name, baseline, B=10_000, seed=0):
    """analyze_ruler.py:tau_boot, verbatim arithmetic."""
    rng = np.random.default_rng(seed)
    n = len(roots)
    idx = rng.integers(0, n, size=(B, n))
    t = np.array([r["rankers"][name]["tau"] for r in roots], dtype=np.float64)
    tb = np.array([r["rankers"][baseline]["tau"] for r in roots], dtype=np.float64)
    out = {"tau_mean": round(float(np.nanmean(t)), 4),
           "tau_sigma_boot": round(float(np.nanstd(np.nanmean(t[idx], axis=1))), 5),
           "n_tau_nan": int(np.isnan(t).sum())}
    ok = np.isfinite(t) & np.isfinite(tb)
    dt = t[ok] - tb[ok]
    if dt.size:
        idx2 = rng.integers(0, dt.size, size=(B, dt.size))
        sig = float(dt[idx2].mean(axis=1).std())
        out[f"dtau_vs_{baseline}_mean"] = round(float(dt.mean()), 4)
        out["dtau_sigma_boot"] = round(sig, 5)
        out["dtau_z"] = round(float(dt.mean() / sig), 3) if sig > 0 else None
        out["n_paired"] = int(dt.size)
    return out


def agreement(roots, a, b):
    """READOUT sect 4.3(b) statistic: fraction of roots where two rankers pick
    the same child."""
    same = 0
    for r in roots:
        ra, rb = r["rankers"][a], r["rankers"][b]
        if ra.get("pick") is not None and ra.get("pick") == rb.get("pick"):
            same += 1
    return round(same / max(len(roots), 1), 4)


# --------------------------------------------------------------------------- #
# PREREG sect 4.1 / 4.2 -- training-validity gates, read off history.json      #
# --------------------------------------------------------------------------- #
def training_gates(arm: str) -> dict:
    hf = CKROOT / arm / "history.json"
    if not hf.exists():
        return {"arm": arm, "status": "MISSING", "history": str(hf)}
    blob = json.loads(hf.read_text())
    h = blob["history"]
    n = len(h)
    tail = max(1, round(n * 0.25))          # PREREG 4.1: final 4 of 16
    head, last = h[:n - tail], h[n - tail:]
    best_head_v = min(e["val_val_loss"] for e in head) if head else float("inf")
    best_tail_v = min(e["val_val_loss"] for e in last)
    best_head_p = min(e["val_pol_loss"] for e in head) if head else float("inf")
    best_tail_p = min(e["val_pol_loss"] for e in last)
    rel_v = (best_head_v - best_tail_v) / best_head_v if best_head_v else 0.0
    rel_p = (best_head_p - best_tail_p) / best_head_p if best_head_p else 0.0
    converged = bool(rel_v < 0.02 and rel_p < 0.02)

    fit_mse = bool(h[-1]["train_val_loss"] < 0.5 * h[0]["train_val_loss"])
    corr = h[-1]["val_value_outcome_corr"]
    best_corr = max((e["val_value_outcome_corr"] or -1) for e in h)
    fit_corr = bool((corr or -1) >= R_FIT_GATE)
    fit_ent = bool(h[-1]["val_policy_entropy"] >= ENTROPY_FLOOR)
    return {
        "arm": arm, "n_epochs": n, "n_params": blob["manifest"]["n_params"],
        "arch": blob["manifest"]["arch"],
        "gpu_sec_total": round(sum(e["wallclock_sec"] for e in h), 1),
        "convergence": {"rel_improve_val_value_mse_final_quarter": round(rel_v, 5),
                        "rel_improve_val_policy_ce_final_quarter": round(rel_p, 5),
                        "CONVERGED": converged},
        "fit_gate": {"train_value_mse_halved": fit_mse,
                     "final_val_value_outcome_corr": corr,
                     "best_val_value_outcome_corr": round(best_corr, 4),
                     "corr_ge_0.55": fit_corr,
                     "final_val_policy_entropy": h[-1]["val_policy_entropy"],
                     "entropy_ok": fit_ent,
                     "VALID_CONTROL": bool(fit_mse and fit_corr and fit_ent)},
        "best": blob.get("best"),
        "curve": [{k: e[k] for k in ("epoch", "train_val_loss", "val_val_loss",
                                     "val_pol_loss", "val_value_outcome_corr",
                                     "val_policy_entropy", "wallclock_sec")}
                  for e in h],
    }


def adjudicate(arm_name, agg, pr, tau, gates):
    """PREREG sect 5, applied verbatim."""
    rc, rb = agg[arm_name]["solver_regret_mean"], agg[BASELINE]["solver_regret_mean"]
    z = pr["sign_z"]
    corr = (gates or {}).get("fit_gate", {}).get("final_val_value_outcome_corr")
    valid = (gates or {}).get("fit_gate", {}).get("VALID_CONTROL")
    if rc < rb and z >= SIGN_Z:
        branch = "B_ARCHITECTURE_SCOPED"
    elif (valid and corr is not None and corr >= R_HEURISTIC_REF
          and rc > rb and z <= -SIGN_Z):
        branch = "A_GENERALISES"
    elif tau["tau_mean"] >= TAU_PARTIAL:
        branch = "B_PARTIAL"
    else:
        branch = "C_GRAY"
    if not valid and branch == "A_GENERALISES":
        branch = "C_GRAY_INVALID_CONTROL"
    return {"arm": arm_name, "regret_mean": rc, "baseline_regret_mean": rb,
            "paired_sign_z": z, "tau_mean": tau["tau_mean"],
            "val_value_outcome_corr": corr, "valid_control": valid,
            "BRANCH": branch}


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        WT / "measurement" / "paper_g2_20260803" / "solver_score_g2.json")
    rep = json.loads(path.read_text())
    roots, names, agg = rep["per_root"], list(rep["rankers"]), rep["aggregate"]

    res = {"report": str(path), "n_roots": len(roots), "n_scored": rep["n_scored"],
           "n_skipped": rep["n_skipped"], "n_errors": rep["n_errors"],
           "max_k": rep["max_k"], "checkpoints": rep["checkpoints"],
           "aggregate": agg, "arms": {}}

    # --- PREREG 4.3: instrument-integrity gate -----------------------------
    integrity = {}
    for leaf in ("v29_leaf", BASELINE):
        if leaf in agg:
            integrity[leaf] = {k: (round(agg[leaf][k], 4), v,
                                   abs(round(agg[leaf][k], 4) - v) < 5e-5)
                               for k, v in LEAF_SELFCHECK.items()}
    res["INSTRUMENT_INTEGRITY"] = {
        "detail": integrity,
        "PASS": all(t[2] for arm in integrity.values() for t in arm.values()),
    }

    # --- PREREG 4.1/4.2: training gates ------------------------------------
    res["TRAINING_GATES"] = {a: training_gates(a)
                             for a in ("resnet_scratch", "tf_match", "tf_large")}

    for nm in names:
        ent = {"aggregate": agg[nm]}
        for base in (BASELINE, "v29_leaf", "value_unlock_v1", "g2_resnet_scratch_best"):
            if base in names and nm != base:
                ent[f"paired_vs_{base}"] = paired(roots, nm, base)
        if BASELINE in names and nm != BASELINE:
            ent[f"tau_boot_vs_{BASELINE}"] = tau_boot(roots, nm, BASELINE)
        res["arms"][nm] = ent

    # --- PREREG 5: the adjudication ----------------------------------------
    gate_of = {"g2_resnet_scratch": "resnet_scratch",
               "g2_tf_match": "tf_match", "g2_tf_large": "tf_large"}
    verdicts = {}
    for nm in names:
        for prefix, arm in gate_of.items():
            if nm.startswith(prefix):
                verdicts[nm] = adjudicate(
                    nm, agg, res["arms"][nm][f"paired_vs_{BASELINE}"],
                    res["arms"][nm][f"tau_boot_vs_{BASELINE}"],
                    res["TRAINING_GATES"].get(arm))
    res["PREREGISTERED_VERDICTS"] = verdicts
    res["HEADLINE"] = verdicts.get(HEADLINE, {"arm": HEADLINE, "BRANCH": "NOT_RUN"})

    # --- secondary: picked-child agreement (READOUT 4.3(b) statistic) ------
    pairs = [(a, b) for a in names for b in names if a < b]
    res["agreement_rate"] = {f"{a}|{b}": agreement(roots, a, b) for a, b in pairs}

    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
