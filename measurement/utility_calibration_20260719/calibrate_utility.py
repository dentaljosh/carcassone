#!/usr/bin/env python3
"""Utility calibration audit (external review, Candidate-3 Step 1).

Estimate empirical P(win | on-board margin, tiles-remaining) from existing
self-play npz and compare against the fixed engine-side search utility
    value = tanh(margin / 15)   (constant across game stage).

Hypothesis under test: the fixed /15 tanh MISPRICES win-probability in a
STAGE-DEPENDENT way (a +10 margin with 60 tiles left is a very different win
prob than +10 with 2 tiles left), and saturates past ~+/-30.

DATA / MARGIN CAVEAT (read REPORT.md): the npz scalars give the RAW on-board
score diff (mover POV), NOT the v2.9 LEAF margin (score-if-ended-now incl.
closure/farm bonuses) that the search actually feeds to tanh. This audit runs
on the raw diff and states the caveat; the stage-dependence question is robust
to the margin definition (both proxies grow more decisive as tiles->0).

Join semantics (verified):
  scalars[:,4] = (score_mover - score_opp) / 50   -> raw margin, mover POV
  scalars[:,5] = tiles_remaining / 72             -> tiles remaining
  values[i]    = tanh(final_diff_moverPOV / 15)   -> terminal outcome target
                 => win label = sign(value); final_margin = 15*atanh(value)
Both margin and value are mover-relative, so the per-row join is POV-consistent.
Each npz (one deck seed) is ONE game (144 positions); uncertainty is clustered
BY GAME (deck seed), never by row.

Pure-numpy (no scipy/sklearn on this box). Seeded. LOCAL, nice, single-process.
"""
from __future__ import annotations
import argparse, glob, json, math, os, sys, time
import numpy as np

BASE = "/mnt/c/carc-shared/distill_flywheel_sighted_20260716"
SCORE_DIFF_NORM = 50.0
DECK_NORM = 72.0
VALUE_NORM = 15.0                      # the audited utility norm (tanh(m/15))
AUDIT_T = 15.0

# margin buckets: [-40,40] by 5, tails clipped
MARGIN_EDGES = np.arange(-40, 41, 5, dtype=float)   # -40,-35,...,40
# tiles-remaining stage bands (inclusive lo, inclusive hi)
TILE_BANDS = [(60, 72), (45, 59), (30, 44), (15, 29), (6, 14), (1, 5)]
TILE_BAND_LABELS = ["60-72", "45-59", "30-44", "15-29", "6-14", "1-5"]


def load_data(iters, cap_per_iter):
    """Return a dict of flat arrays over ALL positions in the sampled games."""
    M, T, Y, FM, GID, ITER = [], [], [], [], [], []
    gcount = 0
    per_iter_games = {}
    for it in iters:
        d = f"{BASE}/iter_{it:02d}"
        files = sorted(glob.glob(d + "/seed_*.npz"))
        files = files[:cap_per_iter]
        ng = 0
        for f in files:
            try:
                z = np.load(f, allow_pickle=True)
                sc = z["scalars"]; v = z["values"].astype(np.float64)
            except Exception:
                continue
            if sc.shape[0] == 0:
                continue
            m = sc[:, 4].astype(np.float64) * SCORE_DIFF_NORM
            t = np.rint(sc[:, 5].astype(np.float64) * DECK_NORM).astype(int)
            vc = np.clip(v, -0.999999, 0.999999)
            fm = VALUE_NORM * np.arctanh(vc)                  # mover-POV final margin
            y = np.where(v > 1e-6, 1.0, np.where(v < -1e-6, 0.0, 0.5))
            n = len(m)
            M.append(m); T.append(t); Y.append(y); FM.append(fm)
            GID.append(np.full(n, gcount, dtype=np.int64))
            ITER.append(np.full(n, it, dtype=np.int64))
            gcount += 1
            ng += 1
        per_iter_games[it] = ng
    data = dict(
        m=np.concatenate(M), t=np.concatenate(T), y=np.concatenate(Y),
        fm=np.concatenate(FM), gid=np.concatenate(GID), it=np.concatenate(ITER),
        n_games=gcount, per_iter_games=per_iter_games,
    )
    return data


# ---- helpers -------------------------------------------------------------
def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (center - half, center + half)


def tile_band_of(t):
    """Vectorized: map tiles-remaining -> band index (0..5), -1 if outside."""
    out = np.full(t.shape, -1, dtype=int)
    for i, (lo, hi) in enumerate(TILE_BANDS):
        out[(t >= lo) & (t <= hi)] = i
    return out


def tanh_winprob(m, T):
    return 0.5 * (np.tanh(m / T) + 1.0)


def soft_logloss(y, p, eps=1e-6):
    p = np.clip(p, eps, 1 - eps)
    return float(np.mean(-(y * np.log(p) + (1 - y) * np.log(1 - p))))


def brier(y, p):
    return float(np.mean((p - y) ** 2))


def fit_T(m, y, grid):
    """Best T on a grid minimizing soft log-loss of tanh_winprob."""
    best_T, best_L = grid[0], float("inf")
    for T in grid:
        L = soft_logloss(y, tanh_winprob(m, T))
        if L < best_L:
            best_L, best_T = L, T
    return best_T, best_L


def refine_T(m, y, T0, span=0.35, n=41):
    """Local refine around T0 (multiplicative span)."""
    grid = np.linspace(T0 * (1 - span), T0 * (1 + span), n)
    grid = grid[grid > 0.5]
    return fit_T(m, y, grid)


# ---- PAV isotonic (monotone increasing) ----------------------------------
def isotonic_fit(x, y, w=None):
    """Pool-Adjacent-Violators. Returns (xs_sorted_unique_breaks, y_hat_at_x).
    We return a step function via sorted x and fitted values; predict by
    np.interp on the sorted x with the pooled values (piecewise-constant-ish)."""
    order = np.argsort(x, kind="mergesort")
    xs = x[order]; ys = y[order].astype(float)
    if w is None:
        ws = np.ones_like(ys)
    else:
        ws = w[order].astype(float)
    # PAV
    vals = list(ys); wts = list(ws); cnt = [1] * len(ys)
    i = 0
    # iterative pooling
    val_stack = []; w_stack = []; n_stack = []
    for v0, w0 in zip(ys, ws):
        val_stack.append(v0); w_stack.append(w0); n_stack.append(1)
        while len(val_stack) > 1 and val_stack[-2] > val_stack[-1]:
            v2 = val_stack.pop(); w2 = w_stack.pop(); n2 = n_stack.pop()
            v1 = val_stack.pop(); w1 = w_stack.pop(); n1 = n_stack.pop()
            wv = w1 + w2
            val_stack.append((v1 * w1 + v2 * w2) / wv)
            w_stack.append(wv); n_stack.append(n1 + n2)
    # expand back
    yhat = np.empty_like(ys)
    idx = 0
    for v, nseg in zip(val_stack, n_stack):
        yhat[idx:idx + nseg] = v
        idx += nseg
    return xs, yhat


def isotonic_predict(xs, yhat, xq):
    xq = np.asarray(xq, float)
    # piecewise-constant / linear interp on the fitted step function
    return np.interp(xq, xs, yhat, left=yhat[0], right=yhat[-1])


# ---- main analysis -------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=str, default="0,2,4,6,8,10,12,14,16,18,20")
    ap.add_argument("--cap-per-iter", type=int, default=300)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--n-boot", type=int, default=120)
    ap.add_argument("--outdir", type=str,
                    default="/home/doctor/projects/carcassone/measurement/utility_calibration_20260719")
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    iters = [int(x) for x in args.iters.split(",")]

    t0 = time.time()
    data = load_data(iters, args.cap_per_iter)
    print(f"[load] {data['n_games']} games, {len(data['m'])} positions in "
          f"{time.time()-t0:.1f}s; per-iter games={data['per_iter_games']}")

    m, t, y, fm, gid = data["m"], data["t"], data["y"], data["fm"], data["gid"]
    band = tile_band_of(t)

    # ---- sanity gate: sign/POV correctness on endgame ----
    endgame = (band == 5) & (m > 0)
    n_eg = int(endgame.sum())
    p_eg = float(y[endgame].mean()) if n_eg else float("nan")
    behind_eg = (band == 5) & (m < 0)
    p_beg = float(y[behind_eg].mean()) if behind_eg.sum() else float("nan")
    big_eg = (band == 5) & (m > 15)
    p_big = float(y[big_eg].mean()) if big_eg.sum() else float("nan")
    print(f"[sanity] P(win | m>0, tiles 1-5) = {p_eg:.3f}  (n={n_eg})   "
          f"P(win | m<0, tiles 1-5) = {p_beg:.3f}   "
          f"P(win | m>15, tiles 1-5) = {p_big:.3f} (n={int(big_eg.sum())})")
    draws = int((y == 0.5).sum())
    print(f"[sanity] draws = {draws} / {len(y)} positions "
          f"({100*draws/len(y):.2f}%)")

    # ---- calibration table: (margin bucket x tile band) ----
    mb_idx = np.clip(np.digitize(m, MARGIN_EDGES) - 1, 0, len(MARGIN_EDGES) - 2)
    n_mb = len(MARGIN_EDGES) - 1
    mb_centers = (MARGIN_EDGES[:-1] + MARGIN_EDGES[1:]) / 2.0

    rows = []
    for bi in range(len(TILE_BANDS)):
        for mi in range(n_mb):
            sel = (band == bi) & (mb_idx == mi)
            npos = int(sel.sum())
            if npos == 0:
                continue
            ngames = int(np.unique(gid[sel]).size)
            ys = y[sel]
            k = float((ys == 1.0).sum()) + 0.5 * float((ys == 0.5).sum())
            pwin = float(ys.mean())        # draws already 0.5
            mmean = float(m[sel].mean())
            lo, hi = wilson(k, npos)
            rows.append(dict(
                tiles_band=TILE_BAND_LABELS[bi], tiles_band_idx=bi,
                margin_bucket=f"[{int(MARGIN_EDGES[mi])}:{int(MARGIN_EDGES[mi+1])})",
                margin_center=float(mb_centers[mi]), margin_mean=mmean,
                n_pos=npos, n_games=ngames, p_win=pwin,
                wilson_lo=float(lo), wilson_hi=float(hi),
                emp_value=2 * pwin - 1.0,
                tanh15_pred=float(np.tanh(mmean / AUDIT_T)),
                tanh15_pwin=float(tanh_winprob(mmean, AUDIT_T)),
            ))

    # ---- per-stage best-fit T (point estimate) ----
    coarse = np.concatenate([np.linspace(3, 20, 35), np.linspace(20.5, 80, 60)])
    stage_T = {}
    global_valid = band >= 0
    gT0, gL0 = fit_T(m[global_valid], y[global_valid], coarse)
    gT, gL = refine_T(m[global_valid], y[global_valid], gT0)
    print(f"[globalT] best single T = {gT:.2f} (logloss {gL:.4f}); "
          f"audited T=15 logloss {soft_logloss(y[global_valid], tanh_winprob(m[global_valid],15)):.4f}")

    for bi in range(len(TILE_BANDS)):
        sel = band == bi
        T0, _ = fit_T(m[sel], y[sel], coarse)
        Tb, Lb = refine_T(m[sel], y[sel], T0)
        stage_T[bi] = dict(T=float(Tb), logloss=float(Lb), n_pos=int(sel.sum()),
                           n_games=int(np.unique(gid[sel]).size),
                           logloss_at15=soft_logloss(y[sel], tanh_winprob(m[sel], 15)))

    # ---- bootstrap-by-game CIs for stage T ----
    uniq_games = np.unique(gid)
    ng = len(uniq_games)
    # precompute per-game index lists for speed
    order = np.argsort(gid, kind="mergesort")
    gid_s = gid[order]; m_s = m[order]; y_s = y[order]; band_s = band[order]
    # boundaries of each game in sorted array
    bounds = np.searchsorted(gid_s, uniq_games, side="left")
    bounds = np.append(bounds, len(gid_s))
    game_slices = [slice(bounds[i], bounds[i + 1]) for i in range(ng)]

    boot_T = {bi: [] for bi in range(len(TILE_BANDS))}
    boot_coarse = np.concatenate([np.linspace(4, 20, 25), np.linspace(21, 70, 25)])
    for b in range(args.n_boot):
        pick = rng.integers(0, ng, size=ng)
        mm = np.concatenate([m_s[game_slices[i]] for i in pick])
        yy = np.concatenate([y_s[game_slices[i]] for i in pick])
        bb = np.concatenate([band_s[game_slices[i]] for i in pick])
        for bi in range(len(TILE_BANDS)):
            sel = bb == bi
            if sel.sum() < 50:
                continue
            Tb, _ = fit_T(mm[sel], yy[sel], boot_coarse)
            boot_T[bi].append(Tb)
    for bi in range(len(TILE_BANDS)):
        arr = np.array(boot_T[bi])
        if arr.size:
            stage_T[bi]["T_ci_lo"] = float(np.percentile(arr, 2.5))
            stage_T[bi]["T_ci_hi"] = float(np.percentile(arr, 97.5))
        else:
            stage_T[bi]["T_ci_lo"] = float("nan"); stage_T[bi]["T_ci_hi"] = float("nan")

    print("[stageT] band  T  [95% CI]  n_games  logloss  logloss@15")
    for bi in range(len(TILE_BANDS)):
        s = stage_T[bi]
        print(f"   {TILE_BAND_LABELS[bi]:>6}  T={s['T']:6.2f}  "
              f"[{s['T_ci_lo']:5.1f},{s['T_ci_hi']:5.1f}]  ng={s['n_games']:5d}  "
              f"L={s['logloss']:.4f}  L@15={s['logloss_at15']:.4f}")

    # ---- out-of-sample: 2-fold by GAME ----
    perm = rng.permutation(uniq_games)
    half = ng // 2
    foldA = set(perm[:half].tolist()); foldB = set(perm[half:].tolist())
    inA = np.isin(gid, list(foldA))
    oos = evaluate_oos(m, y, band, gid, inA, coarse)
    print("[oos] 2-fold-by-game held-out metrics (avg over folds):")
    for k, v in oos["summary"].items():
        print(f"      {k}: logloss={v['logloss']:.4f}  brier={v['brier']:.4f}")

    # ---- write outputs ----
    os.makedirs(args.outdir, exist_ok=True)
    # CSV of fitted surface
    csv_path = os.path.join(args.outdir, "calibration_surface.csv")
    with open(csv_path, "w") as fcsv:
        fcsv.write("margin_bucket,margin_center,margin_mean,tiles_band,n_pos,"
                   "n_games,p_win,wilson_lo,wilson_hi,emp_value,tanh15_pred,tanh15_pwin\n")
        for r in rows:
            fcsv.write(f"{r['margin_bucket']},{r['margin_center']:.1f},"
                       f"{r['margin_mean']:.3f},{r['tiles_band']},{r['n_pos']},"
                       f"{r['n_games']},{r['p_win']:.4f},{r['wilson_lo']:.4f},"
                       f"{r['wilson_hi']:.4f},{r['emp_value']:.4f},"
                       f"{r['tanh15_pred']:.4f},{r['tanh15_pwin']:.4f}\n")

    stats = dict(
        config=dict(iters=iters, cap_per_iter=args.cap_per_iter, seed=args.seed,
                    n_boot=args.n_boot, base=BASE, audit_T=AUDIT_T,
                    margin_edges=MARGIN_EDGES.tolist(), tile_bands=TILE_BANDS,
                    n_games=data["n_games"], n_positions=int(len(m)),
                    per_iter_games=data["per_iter_games"]),
        sanity=dict(p_win_ahead_endgame=p_eg, n_ahead_endgame=n_eg,
                    p_win_behind_endgame=p_beg, draws=draws,
                    draw_frac=draws / len(y)),
        global_T=dict(T=float(gT), logloss=float(gL),
                      logloss_at15=float(soft_logloss(y[global_valid],
                                    tanh_winprob(m[global_valid], 15)))),
        stage_T=stage_T,
        oos=oos["summary"],
        oos_stageT_by_fold=oos["stageT_by_fold"],
    )
    with open(os.path.join(args.outdir, "calibration_stats.json"), "w") as fj:
        json.dump(stats, fj, indent=2)
    print(f"[done] wrote {csv_path} and calibration_stats.json in {time.time()-t0:.1f}s")
    return stats


def evaluate_oos(m, y, band, gid, inA, coarse):
    """2-fold by game. Fit on A, eval on B and vice versa; average.
    Models: M0 tanh(m/15) fixed; M1 tanh(m/T*) single global T fit on train;
    M2 tanh(m/T_stage) per-band T fit on train; M3 isotonic per-band on train."""
    results = {"M0_tanh15": [], "M1_globalT": [], "M2_stageT": [], "M3_isotonic": []}
    stageT_by_fold = []
    for train_mask, name in [(inA, "A->B"), (~inA, "B->A")]:
        test_mask = ~train_mask
        mtr, ytr, btr = m[train_mask], y[train_mask], band[train_mask]
        mte, yte, bte = m[test_mask], y[test_mask], band[test_mask]
        vtr = btr >= 0; vte = bte >= 0
        # M0
        p0 = tanh_winprob(mte[vte], AUDIT_T)
        # M1
        gT0, _ = fit_T(mtr[vtr], ytr[vtr], coarse)
        gT, _ = refine_T(mtr[vtr], ytr[vtr], gT0)
        p1 = tanh_winprob(mte[vte], gT)
        # M2 per-band T
        Tband = {}
        p2 = np.empty(vte.sum()); mte_v = mte[vte]; bte_v = bte[vte]
        for bi in range(len(TILE_BANDS)):
            seltr = btr == bi
            T0, _ = fit_T(mtr[seltr], ytr[seltr], coarse)
            Tb, _ = refine_T(mtr[seltr], ytr[seltr], T0)
            Tband[bi] = float(Tb)
        for bi in range(len(TILE_BANDS)):
            sel = bte_v == bi
            p2[sel] = tanh_winprob(mte_v[sel], Tband[bi])
        # M3 isotonic per band
        p3 = np.empty(vte.sum())
        for bi in range(len(TILE_BANDS)):
            seltr = btr == bi
            xs, yhat = isotonic_fit(mtr[seltr], ytr[seltr])
            sel = bte_v == bi
            p3[sel] = np.clip(isotonic_predict(xs, yhat, mte_v[sel]), 1e-4, 1 - 1e-4)
        yv = yte[vte]
        results["M0_tanh15"].append((soft_logloss(yv, p0), brier(yv, p0)))
        results["M1_globalT"].append((soft_logloss(yv, p1), brier(yv, p1)))
        results["M2_stageT"].append((soft_logloss(yv, p2), brier(yv, p2)))
        results["M3_isotonic"].append((soft_logloss(yv, p3), brier(yv, p3)))
        stageT_by_fold.append(dict(fold=name, global_T=gT, stage_T=Tband))
    summary = {}
    for k, v in results.items():
        ll = float(np.mean([a for a, _ in v]))
        br = float(np.mean([b for _, b in v]))
        summary[k] = dict(logloss=ll, brier=br)
    return dict(summary=summary, stageT_by_fold=stageT_by_fold)


if __name__ == "__main__":
    sys.exit(0 if main() else 0)
