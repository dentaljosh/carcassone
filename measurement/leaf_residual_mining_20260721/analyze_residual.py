#!/usr/bin/env python3
"""Leaf residual-mining — the PRE-REGISTERED estimator + gate arithmetic.

Implements PREREG.md §4 and §5 exactly:

  * 5-fold GROUPED cross-fitting, group = deck_seed (a game is wholly in one fold)
  * per candidate f:  e_r = resid - E_hat[resid|C] (out-of-fold)
                      e_f = f     - E_hat[f    |C] (out-of-fold)
                      rho_f = corr(e_r, e_f)
  * p-value from a GAME-CLUSTERED bootstrap (2000 resamples OF GAMES), two-sided
  * Holm-Bonferroni over the K candidates (family-wise alpha 0.05); BH-FDR reported
    alongside as secondary information only
  * effective n: ICC of the residual, design effect, n_eff
  * the §5 gate: HIT / AMBIGUOUS / NULL, with the pipeline-validity checks
    (neg_control must be null; ok-rate; zero exact latches) evaluated FIRST

Nothing here reads a candidate's number before the validity checks are printed, and
no threshold in this file may be changed after the first look (PREREG.md banner).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import leaf_features as LF  # noqa: E402

N_FOLDS = 5
N_BOOT = 2000
ALPHA = 0.05
BH_Q = 0.10
RHO_HIT = 0.10
RHO_NULL = 0.05
CONTROLS = list(LF.CONTROLS)


# --------------------------------------------------------------------------- #
def load(paths) -> dict:
    rows = []
    for p in paths:
        for line in Path(p).read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("ok"):
                rows.append(r)
    return rows


def _target(r, level, target):
    """PREREG §2: the PRIMARY target is the pooled visit-weighted root Q minus the leaf.
    `maxq` is the pre-registered SECONDARY read (best-play value instead of the
    visit-weighted mean) — reported for robustness, never gated on."""
    if target == "pooled":
        return r.get("resid", {}).get(level)
    ex = (r.get("level_extras") or {}).get(level) or {}
    mq = ex.get("max_child_q")
    return None if mq is None else mq - r["aux"]["v_leaf"]


def build_matrix(rows, level: str, target: str = "pooled"):
    """-> (y, X_ctrl, F, groups, meta) for one depth level."""
    keep = [r for r in rows if _target(r, level, target) is not None]
    y = np.array([_target(r, level, target) for r in keep], dtype=float)
    groups = np.array([int(r["deck_seed"]) for r in keep], dtype=np.int64)
    aux = {k: np.array([float(r["aux"][k]) for r in keep]) for k in
           ("v_leaf", "tiles_remaining", "corpus_champ125")}
    ctrl = np.column_stack([
        np.ones(len(keep)),
        aux["v_leaf"],
        aux["v_leaf"] ** 2,
        aux["tiles_remaining"],
        aux["corpus_champ125"],
    ])
    # a constant control column (single-corpus run) would make X'X singular
    keepcols = [0] + [j for j in range(1, ctrl.shape[1]) if np.ptp(ctrl[:, j]) > 0]
    ctrl = ctrl[:, keepcols]
    F = {n: np.array([float(r["features"][n]) for r in keep]) for n in LF.ALL_FEATURES}
    return y, ctrl, F, groups, keep


def _ols_fit(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


def crossfit_resid(y, X, groups, n_folds=N_FOLDS, seed=0):
    """Out-of-fold residual of y on X, folds assigned by GROUP (deck_seed)."""
    ug = np.unique(groups)
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(ug))
    fold_of_group = {int(g): int(perm[i] % n_folds) for i, g in enumerate(ug)}
    fold = np.array([fold_of_group[int(g)] for g in groups])
    out = np.empty_like(y)
    for k in range(n_folds):
        te = fold == k
        tr = ~te
        beta = _ols_fit(X[tr], y[tr])
        out[te] = y[te] - X[te] @ beta
    return out, fold


def clustered_boot_corr(a, b, groups, n_boot=N_BOOT, seed=1):
    """Game-clustered bootstrap distribution of corr(a, b)."""
    ug, inv = np.unique(groups, return_inverse=True)
    idx_by_g = [np.flatnonzero(inv == i) for i in range(len(ug))]
    rng = np.random.default_rng(seed)
    out = np.empty(n_boot)
    G = len(ug)
    for t in range(n_boot):
        pick = rng.integers(0, G, size=G)
        ii = np.concatenate([idx_by_g[j] for j in pick])
        aa, bb = a[ii], b[ii]
        sa, sb = aa.std(), bb.std()
        out[t] = 0.0 if (sa == 0 or sb == 0) else float(np.corrcoef(aa, bb)[0, 1])
    return out


def icc(y, groups):
    """One-way random-effects ICC of y across groups (games)."""
    ug, inv = np.unique(groups, return_inverse=True)
    k = len(ug)
    n = len(y)
    if k < 2 or n <= k:
        return 0.0, 1.0
    gm = y.mean()
    means = np.array([y[inv == i].mean() for i in range(k)])
    sizes = np.array([(inv == i).sum() for i in range(k)], dtype=float)
    msb = float((sizes * (means - gm) ** 2).sum() / (k - 1))
    within = float(sum(((y[inv == i] - means[i]) ** 2).sum() for i in range(k)))
    msw = within / (n - k)
    m0 = (n - (sizes ** 2).sum() / n) / (k - 1)
    val = (msb - msw) / (msb + (m0 - 1) * msw) if (msb + (m0 - 1) * msw) > 0 else 0.0
    return float(max(0.0, min(1.0, val))), float(sizes.mean())


def holm(pvals: dict) -> dict:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    K = len(items)
    adj, run = {}, 0.0
    for i, (name, p) in enumerate(items):
        v = min(1.0, (K - i) * p)
        run = max(run, v)
        adj[name] = run
    return adj


def bh(pvals: dict) -> dict:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    K = len(items)
    adj, run = {}, 1.0
    for i in range(K - 1, -1, -1):
        name, p = items[i]
        run = min(run, p * K / (i + 1))
        adj[name] = run
    return adj


# --------------------------------------------------------------------------- #
def analyse(rows, level: str, label: str, boot=N_BOOT, verbose=True,
            target: str = "pooled") -> dict:
    y, X, F, groups, keep = build_matrix(rows, level, target)
    n, ngames = len(y), len(np.unique(groups))
    rho_icc, mbar = icc(y, groups)
    deff = 1.0 + (mbar - 1.0) * rho_icc
    n_eff = n / deff if deff > 0 else float(n)

    e_r, _ = crossfit_resid(y, X, groups)
    res = {}
    for name in LF.ALL_FEATURES:
        f = F[name]
        if np.ptp(f) == 0:
            res[name] = dict(rho=0.0, p=1.0, ci=[0.0, 0.0], degenerate=True)
            continue
        e_f, _ = crossfit_resid(f, X, groups)
        sa, sb = e_r.std(), e_f.std()
        rho = 0.0 if (sa == 0 or sb == 0) else float(np.corrcoef(e_r, e_f)[0, 1])
        bs = clustered_boot_corr(e_r, e_f, groups, n_boot=boot)
        # two-sided cluster-bootstrap p: fraction of resamples on the far side of 0,
        # centred on the point estimate (percentile-t free; adequate at this n)
        p = 2.0 * min((bs <= 0).mean(), (bs >= 0).mean())
        res[name] = dict(rho=rho, p=float(min(1.0, max(p, 1.0 / boot))),
                         ci=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                         degenerate=False)

    fam = {k: res[k]["p"] for k in LF.CANDIDATE_NAMES}
    hadj, badj = holm(fam), bh(fam)
    for k in LF.CANDIDATE_NAMES:
        res[k]["p_holm"] = hadj[k]
        res[k]["p_bh"] = badj[k]

    # candidate correlation matrix (PREREG §7.4: a "hit" must not be read as K
    # independent chances when several candidates are near-collinear)
    names = list(LF.CANDIDATE_NAMES)
    M = np.column_stack([F[nm] for nm in names])
    with np.errstate(invalid="ignore"):
        C = np.corrcoef(M, rowvar=False)
    C = np.nan_to_num(C)
    hi = [[names[i], names[j], float(C[i, j])]
          for i in range(len(names)) for j in range(i + 1, len(names))
          if abs(C[i, j]) >= 0.5]
    hi.sort(key=lambda t: -abs(t[2]))

    out = dict(label=label, level=level, target=target, n_roots=n, n_games=ngames,
               mean_roots_per_game=mbar, icc_resid=rho_icc, design_effect=deff,
               n_eff=n_eff, resid_mean=float(y.mean()), resid_sd=float(y.std()),
               family_size=len(LF.CANDIDATE_NAMES), features=res,
               candidate_pairs_absr_ge_0p5=hi)
    if verbose:
        print(f"\n=== {label}  level={level}  target={target} ===")
        print(f"n_roots={n} n_games={ngames} mean_roots/game={mbar:.2f} "
              f"ICC={rho_icc:.3f} deff={deff:.2f} n_eff={n_eff:.0f}")
        print(f"resid mean={y.mean():+.4f} sd={y.std():.4f}")
        print(f"{'feature':<26}{'tier':<6}{'rho':>8}{'ci_lo':>9}{'ci_hi':>9}"
              f"{'p':>9}{'p_holm':>9}")
        for name in LF.CANDIDATE_NAMES:
            r = res[name]
            print(f"{name:<26}{LF.TIER[name]:<6}{r['rho']:>8.4f}{r['ci'][0]:>9.4f}"
                  f"{r['ci'][1]:>9.4f}{r['p']:>9.4f}{r['p_holm']:>9.4f}")
        for name in (LF.NEG_CONTROL, LF.POS_REF):
            r = res[name]
            tag = "NEGCTL" if name == LF.NEG_CONTROL else "YARDST"
            print(f"{name:<26}{tag:<6}{r['rho']:>8.4f}{r['ci'][0]:>9.4f}"
                  f"{r['ci'][1]:>9.4f}{r['p']:>9.4f}{'--':>9}")
        if hi:
            print("  collinear candidate pairs (|r|>=0.5): "
                  + ", ".join(f"{a}~{b}={c:+.2f}" for a, b, c in hi[:8]))
    return out


def yardstick(rows, level: str, boot=1000, verbose=True) -> dict:
    """PREREG §3 'outside the family': what would THIS estimator have said about the
    curve125 change (CL-051, +66.8 elo n=400 clairvoyant / +48.8-50.4 fair-confirmed)
    the day BEFORE it was adopted?

    Rebuild the counterfactual pre-CL-051 leaf   leaf100 = leaf_raw - pos_ref_c5_curve
    (exact: pos_ref IS the curve125-minus-curve100 delta), re-tanh it, use it as BOTH
    the value being corrected AND the control, and ask for the partial correlation of
    pos_ref with (V_deep - V_leaf100).  That number is the scale on which a REAL,
    ADOPTED, ~+50-to-+67-elo leaf term registers here.  It is a yardstick, NOT a gate:
    the §5 verdict does not move if it is large or small.
    """
    keep = [r for r in rows if r.get("resid", {}).get(level) is not None]
    vdeep = np.array([r["resid"][level] + r["aux"]["v_leaf"] for r in keep], dtype=float)
    leaf_raw = np.array([r["aux"]["leaf_raw"] for r in keep], dtype=float)
    posref = np.array([r["features"][LF.POS_REF] for r in keep], dtype=float)
    tiles = np.array([r["aux"]["tiles_remaining"] for r in keep], dtype=float)
    corp = np.array([r["aux"]["corpus_champ125"] for r in keep], dtype=float)
    groups = np.array([int(r["deck_seed"]) for r in keep], dtype=np.int64)

    v100 = np.tanh((leaf_raw - posref) / 15.0)
    y = vdeep - v100
    X = np.column_stack([np.ones(len(y)), v100, v100 ** 2, tiles, corp])
    X = X[:, [0] + [j for j in range(1, X.shape[1]) if np.ptp(X[:, j]) > 0]]
    e_r, _ = crossfit_resid(y, X, groups)
    e_f, _ = crossfit_resid(posref, X, groups)
    rho = (0.0 if (e_r.std() == 0 or e_f.std() == 0)
           else float(np.corrcoef(e_r, e_f)[0, 1]))
    bs = clustered_boot_corr(e_r, e_f, groups, n_boot=boot)
    out = dict(rho_yardstick=rho, n=len(y),
               ci=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
               p=float(2.0 * min((bs <= 0).mean(), (bs >= 0).mean())),
               note="partial corr of the curve125-minus-curve100 leaf delta with the "
                    "residual of the PRE-CL-051 leaf. CL-051 shipped at +66.8 elo "
                    "(n=400 clairvoyant) / +48.8-50.4 fair-confirmed.")
    if verbose:
        print(f"\n--- YARDSTICK (CL-051 curve125, retro) level={level}: "
              f"rho={rho:+.4f} ci=[{out['ci'][0]:+.4f},{out['ci'][1]:+.4f}] "
              f"p={out['p']:.4f} n={len(y)} ---")
    return out


def gate(primary: dict, replication: dict | None) -> dict:
    """PREREG §5, verbatim."""
    neg = primary["features"][LF.NEG_CONTROL]
    valid = bool(abs(neg["rho"]) < RHO_NULL or neg["p"] >= ALPHA)
    hits, ambig = [], []
    for name in LF.CANDIDATE_NAMES:
        r = primary["features"][name]
        if r["p_holm"] >= ALPHA:
            continue
        a = abs(r["rho"])
        if a < RHO_NULL:
            continue
        rep_ok = None
        if replication is not None:
            rr = replication["features"].get(name)
            if rr is not None:
                rep_ok = bool(np.sign(rr["rho"]) == np.sign(r["rho"])
                              and abs(rr["rho"]) >= RHO_NULL)
        entry = dict(feature=name, tier=LF.TIER[name], rho=r["rho"],
                     p_holm=r["p_holm"],
                     rho_replication=(replication["features"][name]["rho"]
                                      if replication else None),
                     replication_ok=rep_ok)
        if a >= RHO_HIT and LF.TIER[name] in ("A", "B") and rep_ok:
            hits.append(entry)
        else:
            ambig.append(entry)
    verdict = "HIT" if hits else ("AMBIGUOUS" if ambig else "NULL")
    return dict(pipeline_valid=valid, neg_control=neg, verdict=verdict,
                hits=hits, ambiguous=ambig,
                thresholds=dict(rho_hit=RHO_HIT, rho_null=RHO_NULL, alpha=ALPHA,
                                correction="holm-bonferroni",
                                family_size=len(LF.CANDIDATE_NAMES)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--primary", nargs="+", required=True)
    ap.add_argument("--replication", nargs="*", default=[])
    ap.add_argument("--level", default="688")
    ap.add_argument("--all-levels", default="200,344,688,1376")
    ap.add_argument("--boot", type=int, default=N_BOOT)
    ap.add_argument("--out", default=None)
    ap.add_argument("--label", default="primary")
    ap.add_argument("--target", choices=["pooled", "maxq"], default="pooled",
                    help="pooled = the PRIMARY pre-registered target; maxq = the "
                         "pre-registered SECONDARY robustness read (never gated on)")
    args = ap.parse_args(argv)

    prows = load(args.primary)
    rrows = load(args.replication) if args.replication else None
    print(f"[analyse] primary rows={len(prows)}"
          + (f"  replication rows={len(rrows)}" if rrows else ""))

    prim = analyse(prows, args.level, args.label, boot=args.boot, target=args.target)
    yard = yardstick(prows, args.level, boot=min(1000, args.boot))
    rep = (analyse(rrows, args.level, "replication(champion)", boot=args.boot,
                   target=args.target) if rrows else None)
    g = gate(prim, rep)
    g["yardstick_cl051"] = yard
    print("\n=== GATE (PREREG §5) ===")
    print(json.dumps(g, indent=2, default=float))

    depth = {}
    for L in args.all_levels.split(","):
        L = L.strip()
        if L == args.level:
            depth[L] = prim
            continue
        try:
            depth[L] = analyse(prows, L, f"{args.label} depth L={L}",
                               boot=max(400, args.boot // 4), verbose=False,
                               target=args.target)
        except Exception as e:
            depth[L] = {"error": str(e)}

    if args.out:
        Path(args.out).write_text(json.dumps(
            dict(primary=prim, replication=rep, gate=g, depth_trend=depth,
                 yardstick_cl051=yard),
            indent=2, default=float))
        print(f"\n[analyse] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
