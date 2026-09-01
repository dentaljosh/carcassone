#!/usr/bin/env python3
"""HP-M1 KILL GATE -- forecast + AUC harness + bar adjudication.

Prereg: measurement/hpm1_fieldfate_gate_20260830/PREREG.md (FROZEN 2026-08-30).
Every constant here is the one the prereg names; nothing is chosen at read time.

    bar (a)  AUC >= 0.70 on the PRIMARY universe (E4 champion farmer deploys),
             primary forecast = F-FIT out-of-fold.
    bar (b)  F-FIT must BEAT, on IDENTICAL rows, both B-LEAF and B-BAG.
    bar (c)  seat contrast owner-high / champion-low.
    ANY bar FAILS => MECHANISM DEAD.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import numpy as np

SEED = 20260830
N_BOOT = 2000
N_PERM = 10000
N_FOLDS = 5
LOGIT_C = 1.0


# --------------------------------------------------------------------------- #
# AUC -- Mann-Whitney U, ties credited 0.5 (PREREG 7)                          #
# --------------------------------------------------------------------------- #
def auc(scores, labels) -> float:
    s = np.asarray(scores, dtype=float)
    y = np.asarray(labels, dtype=int)
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), dtype=float)
    sorted_s = s[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and sorted_s[j + 1] == sorted_s[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    n1, n0 = len(pos), len(neg)
    r1 = ranks[y == 1].sum()
    return float((r1 - n1 * (n1 + 1) / 2.0) / (n1 * n0))


# --------------------------------------------------------------------------- #
# ridge-penalised IRLS logistic regression (PREREG 4.2)                        #
# --------------------------------------------------------------------------- #
def fit_logistic(X, y, lam=1.0 / LOGIT_C, max_iter=100, tol=1e-8):
    n, p = X.shape
    Xb = np.hstack([np.ones((n, 1)), X])
    beta = np.zeros(p + 1)
    pen = np.eye(p + 1) * lam
    pen[0, 0] = 0.0                       # intercept unpenalised
    for _ in range(max_iter):
        eta = np.clip(Xb @ beta, -30, 30)
        mu = 1.0 / (1.0 + np.exp(-eta))
        w = np.clip(mu * (1 - mu), 1e-9, None)
        grad = Xb.T @ (y - mu) - pen @ beta
        H = (Xb * w[:, None]).T @ Xb + pen + np.eye(p + 1) * 1e-8
        try:
            step = np.linalg.solve(H, grad)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(H, grad, rcond=None)[0]
        beta = beta + step
        if np.max(np.abs(step)) < tol:
            return beta
    raise RuntimeError("IRLS did not converge in 100 Newton steps "
                       "-- loud failure, not a silent partial fit (PREREG 4.2)")


class Model:
    def __init__(self, X, y):
        self.mu = X.mean(axis=0)
        self.sd = X.std(axis=0)
        self.sd[self.sd < 1e-12] = 1.0
        self.beta = fit_logistic((X - self.mu) / self.sd, y)

    def score(self, X):
        Z = (X - self.mu) / self.sd
        return np.hstack([np.ones((len(Z), 1)), Z]) @ self.beta


# --------------------------------------------------------------------------- #
# rows                                                                          #
# --------------------------------------------------------------------------- #
def load_rows(paths):
    rows = []
    for p in paths:
        for line in Path(p).read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("ok"):
                rows.append(r)
    return rows


def matrix(rows, order):
    return np.array([[float(r["x"][k]) for k in order] for r in rows], dtype=float)


def folds_for(rows):
    """PREREG 4.2: 5 folds grouped by game; a game's fold is its index in the
    sorted game_id list mod 5. Every deployment of a game shares a fold."""
    games = sorted({r["game"] for r in rows})
    fmap = {g: i % N_FOLDS for i, g in enumerate(games)}
    return np.array([fmap[r["game"]] for r in rows], dtype=int)


def oof_scores(rows, order):
    X = matrix(rows, order)
    y = np.array([r["y"] for r in rows], dtype=int)
    f = folds_for(rows)
    out = np.full(len(rows), np.nan)
    for k in range(N_FOLDS):
        tr, te = f != k, f == k
        if te.sum() == 0 or len(set(y[tr].tolist())) < 2:
            continue
        out[te] = Model(X[tr], y[tr]).score(X[te])
    return out, y


def pf_scores(rows):
    """F-PF: proj_finished_cities - invade_risk. No fitted constants."""
    return np.array([r["x"]["proj_finished_cities"] - r["x"]["invade_risk"]
                     for r in rows], dtype=float)


# --------------------------------------------------------------------------- #
# clustered resampling                                                          #
# --------------------------------------------------------------------------- #
def game_clusters(rows):
    """Row-index clusters, one per game, in a CANONICAL order.

    ⭐ Canonicalization key: `r["game"]`, string-sorted. `boot_auc_ci` resamples
    clusters BY POSITION (`clusters[rng.choice(keys)]` over `keys =
    range(len(clusters))`), so "the game at index 0" has to mean the same game
    every time a given `--seed` is replayed — otherwise the SAME seed draws a
    DIFFERENT set of games whenever the input row order changes, and nothing
    about a re-extraction (glob order is already sorted in `main()`, but
    within-file row order is not guaranteed stable across re-extractions —
    e.g. a parallel-worker census writing rows in completion order) promises
    that order is stable. `folds_for` already canonicalizes this way
    (`sorted({r["game"] for r in rows})`); this was the one place that didn't."""
    idx = {}
    for i, r in enumerate(rows):
        idx.setdefault(r["game"], []).append(i)
    return [idx[g] for g in sorted(idx)]


def boot_auc_ci(score, y, clusters, rng, extra=None):
    """Game-clustered bootstrap. `extra`: list of comparison score vectors; the
    CI of each (score - extra_j) AUC difference is returned alongside."""
    base, diffs = [], [[] for _ in (extra or [])]
    keys = list(range(len(clusters)))
    for _ in range(N_BOOT):
        pick = [clusters[rng.choice(keys)] for _ in keys]
        ii = np.array([i for grp in pick for i in grp], dtype=int)
        yy = y[ii]
        if yy.min() == yy.max():
            continue
        a0 = auc(score[ii], yy)
        base.append(a0)
        for j, e in enumerate(extra or []):
            diffs[j].append(a0 - auc(e[ii], yy))

    def ci(v):
        v = np.sort(np.asarray(v, dtype=float))
        if len(v) == 0:
            return [float("nan"), float("nan")]
        return [float(v[int(0.025 * len(v))]), float(v[int(0.975 * len(v)) - 1])]

    return ci(base), [ci(d) for d in diffs]


class _RNG:
    def __init__(self, seed):
        self.r = random.Random(seed)

    def choice(self, keys):
        return self.r.choice(keys)


# --------------------------------------------------------------------------- #
# main                                                                          #
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--primary-profile", default="fixed_v1")
    args = ap.parse_args()
    d = Path(args.dir)
    order = json.loads((d / "FEATURES.json").read_text())["order"]

    e4 = load_rows(sorted(d.glob("rows_E4_*.jsonl")))
    sp = load_rows(sorted(d.glob("rows_SP449_*.jsonl")))

    res = {"prereg": "PREREG.md (frozen 2026-08-30)", "seed": SEED,
           "n_features": len(order),
           "corpora": {"E4_rows": len(e4), "SP449_rows": len(sp)}}

    # ---- universes ------------------------------------------------------- #
    champ = [r for r in e4 if r["seat_role"] == "champion"]
    owner = [r for r in e4 if r["seat_role"] == "owner"]
    res["e4_seat_counts"] = {"champion": len(champ), "owner": len(owner)}
    res["e4_profiles"] = {p: sum(1 for r in e4 if r["profile"] == p)
                          for p in sorted({r["profile"] for r in e4})}

    prim = [r for r in champ if r["profile"] == args.primary_profile]
    if len(prim) < 40:
        prim = champ
        res["primary_universe_note"] = (
            f"profile {args.primary_profile!r} had <40 rows; PRIMARY falls back to "
            "ALL E4 champion rows pooled across profiles (disclosed, PREREG 1.2)")
    res["primary_universe"] = {
        "definition": "E4 champion farmer deployments",
        "profile": args.primary_profile if prim is not champ else "pooled",
        "n_rows": len(prim),
        "n_scoring": sum(r["y"] for r in prim),
        "n_zero": sum(1 - r["y"] for r in prim),
        "n_games": len({r["game"] for r in prim}),
        "zero_rate": (sum(1 - r["y"] for r in prim) / len(prim)) if prim else None,
    }
    res["e4_zero_rate_by_seat"] = {
        "champion": (sum(1 - r["y"] for r in champ) / len(champ)) if champ else None,
        "owner": (sum(1 - r["y"] for r in owner) / len(owner)) if owner else None,
    }
    res["bag_ok_all"] = all(bool(r.get("bag_ok")) for r in (e4 + sp))
    res["bag_ok_fail_n"] = sum(1 for r in (e4 + sp) if not r.get("bag_ok"))

    if not prim:
        res["verdict"] = "ABORTED — empty primary universe"
        (d / "RESULTS.json").write_text(json.dumps(res, indent=1))
        return

    y = np.array([r["y"] for r in prim], dtype=int)
    clusters = game_clusters(prim)
    rng = _RNG(SEED)

    # ---- forecasts + baselines on IDENTICAL rows ------------------------- #
    s_fit, _ = oof_scores(prim, order)
    keep = ~np.isnan(s_fit)
    for r, k in zip(prim, keep):
        r["_keep"] = bool(k)
    if not keep.all():
        res["oof_unscored_rows"] = int((~keep).sum())
    prim_k = [r for r, k in zip(prim, keep) if k]
    y = np.array([r["y"] for r in prim_k], dtype=int)
    clusters = game_clusters(prim_k)
    s_fit = np.array([v for v, k in zip(s_fit, keep) if k], dtype=float)
    s_pf = pf_scores(prim_k)
    b_leaf = np.array([r["b_leaf"] for r in prim_k], dtype=float)
    b_bag = np.array([r["b_bag"] for r in prim_k], dtype=float)

    a_fit, a_pf = auc(s_fit, y), auc(s_pf, y)
    a_leaf, a_bag = auc(b_leaf, y), auc(b_bag, y)
    ci_fit, (ci_d_leaf, ci_d_bag) = boot_auc_ci(s_fit, y, clusters, rng,
                                                extra=[b_leaf, b_bag])
    res["auc"] = {
        "F_FIT_oof": a_fit, "F_FIT_oof_ci95": ci_fit,
        "F_PF": a_pf, "B_LEAF": a_leaf, "B_BAG": a_bag,
        "d_F_FIT_minus_B_LEAF": a_fit - a_leaf, "ci95": ci_d_leaf,
        "d_F_FIT_minus_B_BAG": a_fit - a_bag, "ci95_bag": ci_d_bag,
        "n_rows_scored": int(len(y)), "n_pos": int(y.sum()),
        "n_neg": int((1 - y).sum()),
    }

    # ---- SP449 replication (secondary, adjudicates nothing) -------------- #
    if sp:
        s_sp, y_sp = oof_scores(sp, order)
        m = ~np.isnan(s_sp)
        sp_k = [r for r, k in zip(sp, m) if k]
        res["sp449"] = {
            "n_rows": len(sp), "n_scored": int(m.sum()),
            "n_games": len({r["game"] for r in sp}),
            "zero_rate": float(1 - np.mean([r["y"] for r in sp])),
            "AUC_F_FIT_oof": auc(s_sp[m], y_sp[m]),
            "AUC_F_PF": auc(pf_scores(sp_k), np.array([r["y"] for r in sp_k])),
            "AUC_B_LEAF": auc(np.array([r["b_leaf"] for r in sp_k]),
                              np.array([r["y"] for r in sp_k])),
            "AUC_B_BAG": auc(np.array([r["b_bag"] for r in sp_k]),
                             np.array([r["y"] for r in sp_k])),
        }

    # ---- transfer (tertiary) --------------------------------------------- #
    seat_model = None
    if sp:
        seat_model = Model(matrix(sp, order),
                           np.array([r["y"] for r in sp], dtype=int))
        res["transfer_SP449_to_E4champ_AUC"] = auc(
            seat_model.score(matrix(prim_k, order)), y)
        seat_src = "SP449-trained (never saw an E4 row)"
    else:
        seat_model = Model(matrix(prim_k, order), y)
        seat_src = ("E4-champion-trained (SP449 dropped; never saw an owner row) "
                    "— PREREG 6 fallback")
    res["seat_model_source"] = seat_src

    # ---- bar (c): seat contrast ------------------------------------------ #
    bar_c = {"n_owner": len(owner), "n_champ": len(champ)}
    if owner and champ:
        so = seat_model.score(matrix(owner, order))
        sc = seat_model.score(matrix(champ, order))
        bar_c.update(mean_owner=float(so.mean()), mean_champ=float(sc.mean()),
                     delta=float(so.mean() - sc.mean()))
        # game-clustered seat-label permutation: flip the seat label within game
        bygame = {}
        for r, v in list(zip(owner, so)) + list(zip(champ, sc)):
            bygame.setdefault(r["game"], {"o": [], "c": []})[
                "o" if r["seat_role"] == "owner" else "c"].append(float(v))
        rr = random.Random(SEED)
        obs = bar_c["delta"]
        ge = 0
        for _ in range(N_PERM):
            oo, cc = [], []
            for g in bygame.values():
                if rr.random() < 0.5:
                    oo += g["o"]; cc += g["c"]
                else:
                    oo += g["c"]; cc += g["o"]
            m = (sum(oo) / len(oo) if oo else 0) - (sum(cc) / len(cc) if cc else 0)
            if abs(m) >= abs(obs) - 1e-12:
                ge += 1
        bar_c["perm_p_two_sided"] = (ge + 1) / (N_PERM + 1)
        bar_c["owner_zero_rate"] = float(1 - np.mean([r["y"] for r in owner]))
        bar_c["champ_zero_rate"] = float(1 - np.mean([r["y"] for r in champ]))

    # ---- adjudication (PREREG 6, literal readings) ----------------------- #
    pa = bool(a_fit >= 0.70)
    pb = bool(a_fit > a_leaf and a_fit > a_bag)
    pc = bool(bar_c.get("delta") is not None and bar_c["delta"] > 0)
    weak_b = pb and (ci_d_leaf[0] <= 0 <= ci_d_leaf[1]
                     or ci_d_bag[0] <= 0 <= ci_d_bag[1])
    res["bars"] = {
        "a_AUC_ge_0.70": {"pass": pa, "value": a_fit, "bar": 0.70,
                          "ci95": ci_fit},
        "b_beats_B_LEAF_and_B_BAG": {
            "pass": pb, "weak": bool(weak_b),
            "F_FIT": a_fit, "B_LEAF": a_leaf, "B_BAG": a_bag,
            "d_leaf": a_fit - a_leaf, "d_leaf_ci95": ci_d_leaf,
            "d_bag": a_fit - a_bag, "d_bag_ci95": ci_d_bag},
        "c_seat_owner_high": {"pass": pc, **bar_c},
    }
    res["verdict"] = ("SURVIVES (all three bars PASS — buys a NEXT PREREG only, "
                      "no build, no band)" if (pa and pb and pc)
                      else "MECHANISM DEAD (a bar failed) — no build, no band, "
                           "no follow-on cell")
    res["bars_failed"] = [k for k, v in res["bars"].items() if not v["pass"]]
    (d / "RESULTS.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: res[k] for k in
                      ("primary_universe", "auc", "bars", "verdict")},
                     indent=1, default=str))


if __name__ == "__main__":
    main()
