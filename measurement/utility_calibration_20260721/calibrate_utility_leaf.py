#!/usr/bin/env python3
"""F0b' STEP 2 — utility calibration on the TRUE v2.9 LEAF margin (+ RAW control).

Re-runs the 2026-07-19 utility-calibration analysis (`measurement/
utility_calibration_20260719/calibrate_utility.py`) UNCHANGED, but on the margin
the SEARCH actually consumes:

    leaf margin = flat_virtual_score_v2_float(state, mover, champion v2.9 leaf_cfg)
                  -> the search computes value = tanh(leaf_margin / value_norm=15)

and, on the IDENTICAL position sample, on the RAW on-board score diff (the column
the 07-19 audit used) as the CONTROL — so a leaf-vs-raw difference cannot be
confounded with a corpus difference.

Every estimator (Wilson, tanh-winprob, soft log-loss, Brier, grid+refine best-T,
PAV isotonic, the 2-fold-by-GAME out-of-sample harness) is IMPORTED verbatim from
the 07-19 script rather than re-typed, so the two analyses cannot drift.

Additions over 07-19 (both applied identically to raw and leaf):
  * game-clustered bootstrap CI on the GLOBAL best-T (07-19 bootstrapped only the
    per-stage T);
  * explicit calibration-GAP statistics — the pre-registered F0b' trigger:
      - dLL15   = logloss(T=15) - logloss(T*)          [in-sample and OOS]
      - dLL_iso = logloss(T=15) - logloss(global isotonic, OOS)  (shape ceiling)
      - mean |p_emp - tanh(m/15)/..|, n-weighted over margin buckets;
  * a per-bucket IMPLIED T  (T_imp = m / atanh(2p_emp - 1)) — the direct read on
    "is tanh(m/15) ~2x too steep / does it saturate".

Input: margins npz from extract_margins.py. Pure-numpy, seeded, single-process.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_PRIOR = _REPO / "measurement" / "utility_calibration_20260719" / "calibrate_utility.py"


def _load_prior_module():
    """Import the 07-19 analysis module by path (no drift: same estimators)."""
    spec = importlib.util.spec_from_file_location("calibrate_utility_20260719", _PRIOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


P = _load_prior_module()
# estimators, verbatim
wilson, tile_band_of, tanh_winprob = P.wilson, P.tile_band_of, P.tanh_winprob
soft_logloss, brier = P.soft_logloss, P.brier
fit_T, refine_T = P.fit_T, P.refine_T
isotonic_fit, isotonic_predict = P.isotonic_fit, P.isotonic_predict
evaluate_oos = P.evaluate_oos
TILE_BANDS, TILE_BAND_LABELS, AUDIT_T = P.TILE_BANDS, P.TILE_BAND_LABELS, P.AUDIT_T

COARSE = np.concatenate([np.linspace(3, 20, 35), np.linspace(20.5, 80, 60)])   # == 07-19
BOOT_COARSE = np.concatenate([np.linspace(4, 20, 25), np.linspace(21, 70, 25)])  # == 07-19


# --------------------------------------------------------------------------- #
def bucket_table(m, y, gid, band, edges):
    """(margin bucket x tile band) calibration cells + a stage-POOLED margin table."""
    mb = np.clip(np.digitize(m, edges) - 1, 0, len(edges) - 2)
    centers = (edges[:-1] + edges[1:]) / 2.0
    rows = []
    for bi in range(len(TILE_BANDS)):
        for mi in range(len(edges) - 1):
            sel = (band == bi) & (mb == mi)
            n = int(sel.sum())
            if n == 0:
                continue
            ys = y[sel]
            k = float((ys == 1.0).sum()) + 0.5 * float((ys == 0.5).sum())
            p = float(ys.mean())
            mm = float(m[sel].mean())
            lo, hi = wilson(k, n)
            rows.append(dict(tiles_band=TILE_BAND_LABELS[bi], tiles_band_idx=bi,
                             margin_bucket=f"[{edges[mi]:g}:{edges[mi+1]:g})",
                             margin_center=float(centers[mi]), margin_mean=mm,
                             n_pos=n, n_games=int(np.unique(gid[sel]).size), p_win=p,
                             wilson_lo=float(lo), wilson_hi=float(hi),
                             emp_value=2 * p - 1.0,
                             tanh15_pred=float(np.tanh(mm / AUDIT_T)),
                             tanh15_pwin=float(tanh_winprob(mm, AUDIT_T))))
    pooled = []
    for mi in range(len(edges) - 1):
        sel = (mb == mi) & (band >= 0)
        n = int(sel.sum())
        if n == 0:
            continue
        ys = y[sel]
        k = float((ys == 1.0).sum()) + 0.5 * float((ys == 0.5).sum())
        p = float(ys.mean())
        mm = float(m[sel].mean())
        lo, hi = wilson(k, n)
        ev = 2 * p - 1.0
        # implied T: the tanh denominator that would REPRODUCE this bucket's empirical value
        t_imp = float("nan")
        if abs(ev) < 0.999 and abs(mm) > 1e-6 and abs(ev) > 1e-6:
            t_imp = float(mm / math.atanh(ev))
        pooled.append(dict(margin_bucket=f"[{edges[mi]:g}:{edges[mi+1]:g})",
                           margin_center=float(centers[mi]), margin_mean=mm,
                           n_pos=n, n_games=int(np.unique(gid[sel]).size),
                           p_win=p, wilson_lo=float(lo), wilson_hi=float(hi),
                           emp_value=ev, tanh15_pred=float(np.tanh(mm / AUDIT_T)),
                           tanh15_pwin=float(tanh_winprob(mm, AUDIT_T)),
                           implied_T=t_imp))
    return rows, pooled


def weighted_abs_gap(pooled, T):
    """n-weighted mean |p_emp - tanh_winprob(m_mean, T)| over pooled margin buckets."""
    num = sum(r["n_pos"] * abs(r["p_win"] - float(tanh_winprob(r["margin_mean"], T))) for r in pooled)
    den = sum(r["n_pos"] for r in pooled)
    return float(num / den) if den else float("nan")


def boot_global_T(m_s, y_s, band_s, slices, rng, n_boot):
    """Game-clustered bootstrap of the GLOBAL best-T."""
    ng = len(slices)
    out = []
    for _ in range(n_boot):
        pick = rng.integers(0, ng, size=ng)
        mm = np.concatenate([m_s[slices[i]] for i in pick])
        yy = np.concatenate([y_s[slices[i]] for i in pick])
        bb = np.concatenate([band_s[slices[i]] for i in pick])
        v = bb >= 0
        T, _ = fit_T(mm[v], yy[v], BOOT_COARSE)
        out.append(float(T))
    return np.asarray(out)


def boot_stage_T(m_s, y_s, band_s, slices, rng, n_boot):
    ng = len(slices)
    acc = {bi: [] for bi in range(len(TILE_BANDS))}
    for _ in range(n_boot):
        pick = rng.integers(0, ng, size=ng)
        mm = np.concatenate([m_s[slices[i]] for i in pick])
        yy = np.concatenate([y_s[slices[i]] for i in pick])
        bb = np.concatenate([band_s[slices[i]] for i in pick])
        for bi in range(len(TILE_BANDS)):
            sel = bb == bi
            if sel.sum() < 50:
                continue
            T, _ = fit_T(mm[sel], yy[sel], BOOT_COARSE)
            acc[bi].append(float(T))
    return acc


def global_isotonic_oos(m, y, band, inA):
    """OOS log-loss/Brier of a STAGE-FREE isotonic fit on the margin (the shape ceiling
    available to any monotone margin->winprob map). 2 folds by game, averaged."""
    lls, brs = [], []
    for train_mask in (inA, ~inA):
        test = ~train_mask
        vtr = train_mask & (band >= 0)
        vte = test & (band >= 0)
        xs, yh = isotonic_fit(m[vtr], y[vtr])
        p = np.clip(isotonic_predict(xs, yh, m[vte]), 1e-4, 1 - 1e-4)
        lls.append(soft_logloss(y[vte], p)); brs.append(brier(y[vte], p))
    return dict(logloss=float(np.mean(lls)), brier=float(np.mean(brs)))


def analyze(name, m, y, tiles, gid, edges, rng, n_boot, outdir, tag):
    band = tile_band_of(tiles)
    valid = band >= 0
    n_games = int(np.unique(gid).size)
    print(f"\n=== [{name}] n_pos={len(m)} (valid {int(valid.sum())})  n_games={n_games} "
          f"  margin range [{m.min():.1f},{m.max():.1f}]  sd={m.std():.2f}", flush=True)

    # sanity (mirrors 07-19)
    eg = (band == 5) & (m > 0)
    beg = (band == 5) & (m < 0)
    big = (band == 5) & (m > 15)
    print(f"[{name}][sanity] P(win|m>0,t1-5)={y[eg].mean():.3f} (n={int(eg.sum())})  "
          f"P(win|m<0,t1-5)={y[beg].mean():.3f}  P(win|m>15,t1-5)={y[big].mean():.3f} "
          f"(n={int(big.sum())})  draws={(y==0.5).sum()} ({100*(y==0.5).mean():.2f}%)", flush=True)

    rows, pooled = bucket_table(m, y, gid, band, edges)

    # ---- point estimates ----
    T0, _ = fit_T(m[valid], y[valid], COARSE)
    gT, gL = refine_T(m[valid], y[valid], T0)
    L15 = soft_logloss(y[valid], tanh_winprob(m[valid], AUDIT_T))
    B15 = brier(y[valid], tanh_winprob(m[valid], AUDIT_T))
    BgT = brier(y[valid], tanh_winprob(m[valid], gT))
    print(f"[{name}][globalT] T*={gT:.2f}  logloss {gL:.4f}  |  T=15 logloss {L15:.4f}  "
          f"(dLL15 = {L15-gL:+.4f})  brier {B15:.4f}->{BgT:.4f}", flush=True)

    stage_T = {}
    for bi in range(len(TILE_BANDS)):
        sel = band == bi
        t0, _ = fit_T(m[sel], y[sel], COARSE)
        Tb, Lb = refine_T(m[sel], y[sel], t0)
        stage_T[bi] = dict(band=TILE_BAND_LABELS[bi], T=float(Tb), logloss=float(Lb),
                           n_pos=int(sel.sum()), n_games=int(np.unique(gid[sel]).size),
                           logloss_at15=soft_logloss(y[sel], tanh_winprob(m[sel], 15)))

    # ---- game-clustered bootstrap ----
    uniq = np.unique(gid)
    order = np.argsort(gid, kind="mergesort")
    gid_s, m_s, y_s, band_s = gid[order], m[order], y[order], band[order]
    b = np.searchsorted(gid_s, uniq, side="left")
    b = np.append(b, len(gid_s))
    slices = [slice(b[i], b[i + 1]) for i in range(len(uniq))]

    t0 = time.time()
    bg = boot_global_T(m_s, y_s, band_s, slices, rng, n_boot)
    gci = (float(np.percentile(bg, 2.5)), float(np.percentile(bg, 97.5)))
    print(f"[{name}][globalT] bootstrap-by-game 95% CI = [{gci[0]:.2f}, {gci[1]:.2f}] "
          f"(n_boot={n_boot}, {time.time()-t0:.0f}s)", flush=True)

    bs = boot_stage_T(m_s, y_s, band_s, slices, rng, n_boot)
    for bi in range(len(TILE_BANDS)):
        arr = np.asarray(bs[bi])
        stage_T[bi]["T_ci_lo"] = float(np.percentile(arr, 2.5)) if arr.size else float("nan")
        stage_T[bi]["T_ci_hi"] = float(np.percentile(arr, 97.5)) if arr.size else float("nan")
    print(f"[{name}][stageT] band     T   [95% CI]      n_games   L      L@15", flush=True)
    for bi in range(len(TILE_BANDS)):
        s = stage_T[bi]
        print(f"   {s['band']:>6}  T={s['T']:6.2f}  [{s['T_ci_lo']:5.1f},{s['T_ci_hi']:5.1f}]  "
              f"ng={s['n_games']:5d}  L={s['logloss']:.4f}  L@15={s['logloss_at15']:.4f}", flush=True)

    # ---- OOS 2-fold by GAME (07-19 harness verbatim) + global isotonic ----
    perm = rng.permutation(uniq)
    inA = np.isin(gid, perm[: len(uniq) // 2])
    oos = evaluate_oos(m, y, band, gid, inA, COARSE)
    giso = global_isotonic_oos(m, y, band, inA)
    oos["summary"]["M4_global_isotonic"] = giso
    print(f"[{name}][oos] 2-fold-by-game:", flush=True)
    for k, v in oos["summary"].items():
        print(f"      {k:20s} logloss={v['logloss']:.4f}  brier={v['brier']:.4f}", flush=True)

    ll0 = oos["summary"]["M0_tanh15"]["logloss"]
    gap = dict(
        dLL15_insample=float(L15 - gL),
        dLL15_oos=float(ll0 - oos["summary"]["M1_globalT"]["logloss"]),
        dLL_globiso_oos=float(ll0 - giso["logloss"]),
        dLL_stageT_oos=float(ll0 - oos["summary"]["M2_stageT"]["logloss"]),
        dLL_bandiso_oos=float(ll0 - oos["summary"]["M3_isotonic"]["logloss"]),
        mean_abs_gap_T15=weighted_abs_gap(pooled, AUDIT_T),
        mean_abs_gap_Tstar=weighted_abs_gap(pooled, gT),
        brier_at15=float(B15), brier_at_Tstar=float(BgT),
    )
    print(f"[{name}][GAP] dLL15 in-sample={gap['dLL15_insample']:+.4f}  OOS={gap['dLL15_oos']:+.4f}  "
          f"| global-isotonic OOS={gap['dLL_globiso_oos']:+.4f}  "
          f"| mean|p_emp-tanh15| {gap['mean_abs_gap_T15']:.4f} -> {gap['mean_abs_gap_Tstar']:.4f} @T*",
          flush=True)

    # ---- write per-margin CSVs ----
    with open(outdir / f"calibration_surface_{name}_{tag}.csv", "w") as f:
        f.write("margin_bucket,margin_center,margin_mean,tiles_band,n_pos,n_games,p_win,"
                "wilson_lo,wilson_hi,emp_value,tanh15_pred,tanh15_pwin\n")
        for r in rows:
            f.write(f"{r['margin_bucket']},{r['margin_center']:.1f},{r['margin_mean']:.3f},"
                    f"{r['tiles_band']},{r['n_pos']},{r['n_games']},{r['p_win']:.4f},"
                    f"{r['wilson_lo']:.4f},{r['wilson_hi']:.4f},{r['emp_value']:.4f},"
                    f"{r['tanh15_pred']:.4f},{r['tanh15_pwin']:.4f}\n")
    with open(outdir / f"calibration_pooled_{name}_{tag}.csv", "w") as f:
        f.write("margin_bucket,margin_center,margin_mean,n_pos,n_games,p_win,wilson_lo,"
                "wilson_hi,emp_value,tanh15_pred,tanh15_pwin,implied_T\n")
        for r in pooled:
            f.write(f"{r['margin_bucket']},{r['margin_center']:.1f},{r['margin_mean']:.3f},"
                    f"{r['n_pos']},{r['n_games']},{r['p_win']:.4f},{r['wilson_lo']:.4f},"
                    f"{r['wilson_hi']:.4f},{r['emp_value']:.4f},{r['tanh15_pred']:.4f},"
                    f"{r['tanh15_pwin']:.4f},{r['implied_T']:.3f}\n")

    return dict(
        name=name, n_pos=int(len(m)), n_pos_valid=int(valid.sum()), n_games=n_games,
        margin_sd=float(m.std()), margin_min=float(m.min()), margin_max=float(m.max()),
        global_T=dict(T=float(gT), ci=[gci[0], gci[1]], logloss=float(gL),
                      logloss_at15=float(L15), brier_at15=float(B15), brier_at_T=float(BgT),
                      boot_mean=float(bg.mean()), boot_sd=float(bg.std())),
        stage_T=stage_T, oos=oos["summary"], oos_stageT_by_fold=oos["stageT_by_fold"],
        gap=gap, pooled_buckets=pooled,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--margins", default=str(_HERE / "margins_windowaudit.npz"))
    ap.add_argument("--tag", default="windowaudit")
    ap.add_argument("--edge-lo", type=float, default=-60.0)
    ap.add_argument("--edge-hi", type=float, default=60.0)
    ap.add_argument("--edge-step", type=float, default=5.0)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--n-boot", type=int, default=120)
    ap.add_argument("--outdir", default=str(_HERE))
    args = ap.parse_args()

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    edges = np.arange(args.edge_lo, args.edge_hi + 1e-9, args.edge_step, dtype=float)

    z = np.load(args.margins)
    raw, leaf, tiles, y, gid = z["raw"], z["leaf"], z["tiles"], z["y"], z["gid"]
    print(f"[load] {args.margins}: {len(raw)} positions / {np.unique(gid).size} games", flush=True)
    print(f"[load] corr(raw,leaf) = {np.corrcoef(raw, leaf)[0,1]:.4f}", flush=True)

    t0 = time.time()
    res = {}
    for name, m in (("leaf", leaf.astype(np.float64)), ("raw", raw.astype(np.float64))):
        rng = np.random.default_rng(args.seed)      # SAME resample draws for both margins
        res[name] = analyze(name, m, y, tiles, gid, edges, rng, args.n_boot, outdir, args.tag)

    # side-by-side
    print("\n=== SIDE BY SIDE (identical sample) ===", flush=True)
    for k in ("leaf", "raw"):
        g = res[k]["global_T"]; gp = res[k]["gap"]
        print(f"  {k:5s} T*={g['T']:6.2f} [{g['ci'][0]:.2f},{g['ci'][1]:.2f}]   "
              f"L@15={g['logloss_at15']:.4f} L@T*={g['logloss']:.4f}  "
              f"dLL15_oos={gp['dLL15_oos']:+.4f}  dLL_globiso_oos={gp['dLL_globiso_oos']:+.4f}  "
              f"mean|gap|@15={gp['mean_abs_gap_T15']:.4f}", flush=True)

    try:
        rev = subprocess.run(["git", "-C", str(_REPO), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        rev = "unknown"
    man_extract = {}
    p_ext = Path(args.margins).with_name(f"manifest_extract_{Path(args.margins).stem}.json")
    if p_ext.exists():
        man_extract = json.loads(p_ext.read_text())
    out = dict(
        kind="f0b_prime_utility_calibration_leaf_vs_raw", tag=args.tag,
        utc=time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
        code_rev=rev, host=os.uname().nodename,
        config=dict(margins_npz=args.margins, seed=args.seed, n_boot=args.n_boot,
                    margin_edges=edges.tolist(), tile_bands=TILE_BANDS,
                    audit_T=AUDIT_T, estimators_imported_from=str(_PRIOR)),
        extract_manifest=man_extract,
        corr_raw_leaf=float(np.corrcoef(raw, leaf)[0, 1]),
        results=res, elapsed_s=time.time() - t0,
    )
    (outdir / f"calibration_stats_{args.tag}.json").write_text(json.dumps(out, indent=2))
    print(f"\n[done] wrote calibration_stats_{args.tag}.json in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
