#!/usr/bin/env python3
"""Probe §5A — GATE ZERO: is tempo a genuine axis, or a re-encoding of what the
already-present (inert) representation can see?

FB = "already-present" block the head can already see = CL-037 aux child_scalars
     [12 base scalars (incl. free-meeple counts col0/1, tiles-remaining col5) + 32
     bag scalars] + farm-summary scalars (the farm axis reduced to scalars).
T  = the novel structural-tempo block (emit_tempo.py).

Pre-registered thresholds (docs/PROBE_5A_TEMPO_AXIS_GATE.md §3):
  per-feature redundancy:  mean_i R2(t_i | FB) < 0.50  AND  max_i R2 < 0.70
  block redundancy:        largest canonical corr rho1(T, FB) < 0.90
PASS  -> all three clear on the full T          -> proceed to training.
PARTIAL -> drop features with R2>=0.70, re-check survivors clear mean-R2 & rho1
           -> proceed with survivors (report which carried the axis).
FAIL  -> no residualized block clears           -> "no uncorrelated tempo axis",
           STOP; ceiling stands on farm/bag + documented failed independence search.

Unsupervised (no labels) -> run on ALL rows, no train/test split needed.
"""
from __future__ import annotations
import json, sys
from collections import defaultdict
from pathlib import Path
import numpy as np

TEMPO = "/home/doctor/carc_step1_gate/tempo_5a/tempo.npz"
DS = "/home/doctor/carc_step1_gate/dataset_both/aux.npz"
OUT = Path("/home/doctor/projects/carcassone/measurement/probe_5a")
MEAN_R2_BAR = 0.50
MAX_R2_BAR = 0.70
RHO1_BAR = 0.90
RIDGE = 1e-6


def _standardize(X):
    mu = X.mean(0); sd = X.std(0)
    keep = sd > 1e-9
    Xs = (X[:, keep] - mu[keep]) / sd[keep]
    return Xs, keep


def _r2_on(t, FB):
    """R^2 of OLS predicting standardized t from FB (with intercept)."""
    A = np.concatenate([FB, np.ones((FB.shape[0], 1))], axis=1)
    beta, *_ = np.linalg.lstsq(A, t, rcond=None)
    pred = A @ beta
    ss_res = float(((t - pred) ** 2).sum())
    ss_tot = float(((t - t.mean()) ** 2).sum())
    return 1.0 - ss_res / max(ss_tot, 1e-12)


def _rho1(T, FB):
    """Largest canonical correlation between blocks T and FB (whiten + SVD)."""
    n = T.shape[0]
    Tc = T - T.mean(0); Fc = FB - FB.mean(0)
    Stt = (Tc.T @ Tc) / n + RIDGE * np.eye(T.shape[1])
    Sff = (Fc.T @ Fc) / n + RIDGE * np.eye(FB.shape[1])
    Stf = (Tc.T @ Fc) / n
    # inverse square roots via eigendecomposition (symmetric PSD)
    def inv_sqrt(S):
        w, V = np.linalg.eigh(S)
        w = np.clip(w, 1e-12, None)
        return V @ np.diag(1.0 / np.sqrt(w)) @ V.T
    M = inv_sqrt(Stt) @ Stf @ inv_sqrt(Sff)
    s = np.linalg.svd(M, compute_uv=False)
    return float(s[0])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    t = np.load(TEMPO, allow_pickle=True)
    d = np.load(DS, allow_pickle=True)
    tempo_names = [str(x) for x in t["tempo_names"]]
    farmsum_names = [str(x) for x in t["farmsum_names"]]

    # --- align tempo rows -> dataset rows by (seed, ply, within-root ordinal) ---
    gs_d, ply_d, gid_d = d["game_seed"], d["ply"], d["group_id"]
    sca_d = np.asarray(d["child_scalars"], dtype=np.float64)   # (N,44)
    # dataset within-group ordinal (rows are group-contiguous, in enumeration order)
    ord_d = np.empty(len(gid_d), dtype=np.int64)
    ctr = defaultdict(int)
    for i in range(len(gid_d)):
        g = int(gid_d[i]); ord_d[i] = ctr[g]; ctr[g] += 1
    ds_key = {(int(gs_d[i]), int(ply_d[i]), int(ord_d[i])): i for i in range(len(gid_d))}

    gs_t, ply_t, ci_t = t["game_seed"], t["ply"], t["child_index"]
    tempo = np.asarray(t["tempo"], dtype=np.float64)
    farm = np.asarray(t["farm_summary"], dtype=np.float64)
    rows_t, rows_d = [], []
    miss = 0
    for j in range(len(gs_t)):
        k = (int(gs_t[j]), int(ply_t[j]), int(ci_t[j]))
        di = ds_key.get(k)
        if di is None:
            miss += 1; continue
        rows_t.append(j); rows_d.append(di)
    rows_t = np.array(rows_t); rows_d = np.array(rows_d)
    print(f"[align] tempo_rows={len(gs_t)} dataset_rows={len(gid_d)} matched={len(rows_t)} miss={miss}")

    T_raw = tempo[rows_t]
    FARM_raw = farm[rows_t]
    BASE_BAG = sca_d[rows_d]                      # 44 already-present scalars
    FB_raw = np.concatenate([BASE_BAG, FARM_raw], axis=1)

    # standardize; drop zero-variance columns
    Ts, tkeep = _standardize(T_raw)
    FBs, _ = _standardize(FB_raw)
    kept_names = [nm for nm, k in zip(tempo_names, tkeep) if k]
    dropped_const = [nm for nm, k in zip(tempo_names, tkeep) if not k]

    # --- per-feature R^2 ---
    r2 = {}
    for idx, nm in enumerate(kept_names):
        r2[nm] = _r2_on(Ts[:, idx], FBs)
    r2_vals = np.array([r2[nm] for nm in kept_names])
    mean_r2 = float(r2_vals.mean()); max_r2 = float(r2_vals.max())
    rho1_all = _rho1(Ts, FBs)

    print("\n=== per-feature R^2 (variance explained by already-present block) ===")
    for nm in sorted(kept_names, key=lambda n: -r2[n]):
        flag = " <-- >=0.70 (residualize)" if r2[nm] >= MAX_R2_BAR else ""
        print(f"  {nm:24s} R2={r2[nm]:.3f}{flag}")
    if dropped_const:
        print(f"  [zero-variance, dropped]: {dropped_const}")
    print(f"\nmean R2 (all kept) = {mean_r2:.3f}  (bar <{MEAN_R2_BAR})")
    print(f"max  R2 (all kept) = {max_r2:.3f}  (bar <{MAX_R2_BAR})")
    print(f"rho1(T, FB)        = {rho1_all:.3f}  (bar <{RHO1_BAR})")

    # --- decision ---
    pass_all = (mean_r2 < MEAN_R2_BAR) and (max_r2 < MAX_R2_BAR) and (rho1_all < RHO1_BAR)
    survivors = [nm for nm in kept_names if r2[nm] < MAX_R2_BAR]
    verdict = None; detail = {}
    if pass_all:
        verdict = "PASS"
    elif survivors:
        sidx = [kept_names.index(nm) for nm in survivors]
        Ts_s = Ts[:, sidx]
        mean_r2_s = float(np.mean([r2[nm] for nm in survivors]))
        rho1_s = _rho1(Ts_s, FBs)
        detail = {"survivors": survivors, "mean_r2_survivors": mean_r2_s, "rho1_survivors": rho1_s}
        print(f"\n[residualize] survivors (R2<{MAX_R2_BAR}): {survivors}")
        print(f"  mean R2 survivors = {mean_r2_s:.3f}  rho1 survivors = {rho1_s:.3f}")
        if mean_r2_s < MEAN_R2_BAR and rho1_s < RHO1_BAR:
            verdict = "PARTIAL"
        else:
            verdict = "FAIL"
    else:
        verdict = "FAIL"

    print(f"\n===== GATE-ZERO VERDICT: {verdict} =====")
    if verdict == "PASS":
        print("tempo is a genuine axis on the full block -> proceed to 4-arm training (§5).")
    elif verdict == "PARTIAL":
        print("proceed to training with the RESIDUALIZED survivor block:", detail["survivors"])
    else:
        print("no uncorrelated tempo axis available -> STOP; ceiling stands on farm/bag")
        print("+ a documented, powered failed search for a third independent axis (§7 branch C).")

    result = {
        "verdict": verdict, "matched_rows": int(len(rows_t)), "miss": int(miss),
        "per_feature_r2": r2, "dropped_const": dropped_const,
        "mean_r2_all": mean_r2, "max_r2_all": max_r2, "rho1_all": rho1_all,
        "bars": {"mean_r2": MEAN_R2_BAR, "max_r2": MAX_R2_BAR, "rho1": RHO1_BAR},
        "fb_dims": int(FB_raw.shape[1]), "tempo_dims_kept": len(kept_names),
        **detail,
    }
    (OUT / "gate_zero_result.json").write_text(json.dumps(result, indent=2))
    print(f"\n[saved] {OUT/'gate_zero_result.json'}")


if __name__ == "__main__":
    main()
