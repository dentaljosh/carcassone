#!/usr/bin/env python3
"""Slice scan — is there ANY slice where a learned ranker beats the v2.9 leaf's
sibling move-ordering on the NON-CIRCULAR exact-solver ruler?

DESCRIPTIVE / banked data only.  Zero games, zero net forwards, no source edits.

Inputs (all banked):
  * every measurement/**/solver_score*.json  -> per-root {solver_regret, top1, tau}
    for the v2.9 leaf and for 28 learned rankers (CL-042 M2, CL-064 capacity,
    CL-073 value-unlock, paper G2 transformers, probe-5a arms).  All six files
    score the SAME 1,119 exact K<=2 marginalized roots; the leaf's per-root
    numbers are bit-identical across files (verified).
  * measurement/gatec_c0_20260723/cache/c0_cache.npz + c0_fit.py -> re-fit of the
    CL-065 "boring learner" arms (ridge / GBDT on the leaf's own union-find
    component read-out) to recover PER-ROOT metrics (results.json only banked
    aggregates).  Same 5-fold-by-seed cross-fit, same code path.
  * measurement/high_gap_distillation/scaled/pool_A.jsonl  -> root metadata
    (in_hand_tile, meeples_free, score_margin_abs, bag_size, legal_n, ...)
  * measurement/high_gap_distillation/scaled/qprobe_A/probe.jsonl -> teacher
    top-2 gap / entropy tags.

Statistics: each root is a distinct deck seed (1,119 roots / 1,119 seeds), so the
cluster (source game/root) == the unit of analysis.  Paired per-root deltas,
95% CI by paired bootstrap over roots (10k resamples).
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "measurement" / "gatec_c0_20260723"))

SOLVER_FILES = [
    "measurement/canonical_az/solver_score_derisk_it00_03.json",
    "measurement/canonical_az/solver_score_m2_final_it00_04.json",
    "measurement/capacity_probe/solver_score_capacity_full6.json",
    "measurement/paper_g2_20260803/solver_score_g2.json",
    "measurement/probe_5a/arms_retrain/solver_score_5a_arms.json",
    "measurement/value_unlock_20260730/solver_score_value_unlock.json",
]
LEAF = "v29_leaf"
# curve125 is a LEAF VARIANT (a re-tuned meeple curve), not a learned ranker.
LEAF_VARIANTS = {"curve125"}

RNG = np.random.default_rng(12345)
N_BOOT = 10000


# --------------------------------------------------------------------------- #
# 1. load the solver ruler                                                      #
# --------------------------------------------------------------------------- #
def load_solver():
    roots = {}          # seed -> meta
    metrics = defaultdict(dict)   # ranker -> seed -> (regret, top1, tau, pick)
    provenance = {}
    for rel in SOLVER_FILES:
        p = REPO / rel
        d = json.load(open(p))
        provenance[rel] = {
            "rankers": d["rankers"], "max_k": d["max_k"], "n_scored": d["n_scored"],
            "n_errors": d["n_errors"], "qprobe": d["qprobe"], "pool": d["pool"],
        }
        for r in d["per_root"]:
            s = r["seed"]
            meta = dict(ply=r["ply"], k=r["k"], mode=r["mode"], n_legal=r["n_legal"],
                        to_move=r["to_move"], nodes=r["nodes"],
                        best_vs_second_gap=r["best_vs_second_gap"],
                        value_spread=r["value_spread"])
            if s in roots:
                assert roots[s] == meta, f"root meta mismatch {s} in {rel}"
            else:
                roots[s] = meta
            for name, m in r["rankers"].items():
                key = name if name != LEAF else LEAF
                # dedupe identical arms across files (e.g. arm_all_three_s0 appears
                # in both probe_5a and capacity_probe -> tag by file to be safe)
                if name in (LEAF,) or name in LEAF_VARIANTS:
                    tag = name
                else:
                    tag = f"{Path(rel).stem}:{name}"
                if s in metrics[tag]:
                    continue
                metrics[tag][s] = (m["solver_regret"], m["top1"], m["tau"], m["pick"])
    return roots, dict(metrics), provenance


# --------------------------------------------------------------------------- #
# 2. re-fit the CL-065 boring learners for per-root metrics                      #
# --------------------------------------------------------------------------- #
def load_c0_learners():
    import c0_fit as C
    z = np.load(REPO / "measurement/gatec_c0_20260723/cache/c0_cache.npz",
                allow_pickle=True)
    X = z["X"].astype(np.float64)
    y = z["y"].astype(np.float64)
    group = z["group"].astype(np.int64)
    names = [str(s) for s in z["feature_names"]]
    root_seed = z["root_seed"].astype(np.int64)
    root_leaf_tau = z["root_leaf_tau"].astype(np.float64)
    fold_of_root = C.make_folds(root_seed, C.N_FOLDS, C.FOLD_RNG_SEED)
    name_ix = {nm: i for i, nm in enumerate(names)}
    no_leaf = [i for nm, i in name_ix.items() if not nm.startswith("lt_")]

    leaf_terms = [name_ix[k] for k in C.LEAF_TERM_KEYS]
    arms = {}
    specs = [
        # CONTROL: free re-weight of the LEAF'S OWN 4 terms (CL-065 sanity arm).
        # Nothing "learned" beyond 4 coefficients -> attributes any gain to
        # leaf re-tuning rather than to a learned representation.
        ("lw:leaf_terms_ols", leaf_terms,
         lambda a, b, c: C.ridge_fit_predict(a, b, c, 0.0), False),
        ("c0:gate_full_gbdt", list(range(X.shape[1])),
         lambda a, b, c: C.gbdt_fit_predict(a, b, c), False),
        ("c0:gate_full_ridge", list(range(X.shape[1])),
         lambda a, b, c: C.ridge_fit_predict(a, b, c, 1.0), False),
        ("c0:diag_raw_no_leaf_ridge", no_leaf,
         lambda a, b, c: C.ridge_fit_predict(a, b, c, 1.0), False),
        ("c0:diag_raw_no_leaf_gbdt", no_leaf,
         lambda a, b, c: C.gbdt_fit_predict(a, b, c), False),
    ]
    for tag, cols, fn, dm in specs:
        reg, t1, tau, _ = C.crossfit_eval(X[:, cols], y, group, fold_of_root, fn,
                                          C.N_FOLDS, demean=dm)
        arms[tag] = {int(root_seed[i]): (float(reg[i]), int(t1[i]), float(tau[i]), -1)
                     for i in range(len(root_seed))}
        print(f"[c0] {tag}: tau={np.nanmean(tau):.4f} top1={t1.mean():.4f} "
              f"regret={reg.mean():.4f}", flush=True)
    # sanity: leaf floor from the cache must reproduce 0.6153
    print(f"[c0] leaf floor tau from cache = {np.nanmean(root_leaf_tau):.4f} "
          f"(expected 0.6153)", flush=True)
    return arms, float(np.nanmean(root_leaf_tau))


# --------------------------------------------------------------------------- #
# 3. root metadata                                                              #
# --------------------------------------------------------------------------- #
def load_pool(roots):
    want = {s: roots[s]["ply"] for s in roots}
    out = {}
    with open(REPO / "measurement/high_gap_distillation/scaled/pool_A.jsonl") as f:
        for line in f:
            r = json.loads(line)
            s = r["seed"]
            if s in want and r["ply"] == want[s]:
                r.pop("checksum", None)
                out[s] = r
    return out


def load_qprobe(roots):
    want = {s: roots[s]["ply"] for s in roots}
    out = {}
    with open(REPO / "measurement/high_gap_distillation/scaled/qprobe_A/probe.jsonl") as f:
        for line in f:
            r = json.loads(line)
            s = r["seed"]
            if s in want and r["ply"] == want[s]:
                r.pop("action_q", None)
                out[s] = r
    return out


# --------------------------------------------------------------------------- #
# 4. tile taxonomy                                                              #
# --------------------------------------------------------------------------- #
def tile_class(name: str) -> str:
    n = name.lower()
    if "chapel" in n or "cloister" in n or "monast" in n:
        return "cloister"
    has_city = "city" in n
    has_road = "road" in n or "crossroads" in n
    if has_city and has_road:
        return "city+road"
    if has_city:
        return "city_only"
    if has_road:
        return "road_only"
    return "other"


# --------------------------------------------------------------------------- #
# 5. slicing                                                                    #
# --------------------------------------------------------------------------- #
def tercile_labels(vals, names=("low", "mid", "high")):
    v = np.asarray(vals, dtype=float)
    q1, q2 = np.quantile(v, [1 / 3, 2 / 3])
    lab = np.where(v <= q1, names[0], np.where(v <= q2, names[1], names[2]))
    return lab, (float(q1), float(q2))


def build_slices(seeds, roots, pool, qprobe):
    S = {}
    n_legal = np.array([roots[s]["n_legal"] for s in seeds], float)
    gap = np.array([roots[s]["best_vs_second_gap"] for s in seeds], float)
    spread = np.array([roots[s]["value_spread"] for s in seeds], float)
    ply = np.array([roots[s]["ply"] for s in seeds], int)
    tile = np.array([tile_class(pool[s]["in_hand_tile"]) for s in seeds])
    tile_raw = np.array([pool[s]["in_hand_tile"] for s in seeds])
    mover = np.array([pool[s]["to_move"] for s in seeds], int)
    mfree = np.array([pool[s]["meeples_free"][pool[s]["to_move"]] for s in seeds], int)
    mfree_opp = np.array([pool[s]["meeples_free"][1 - pool[s]["to_move"]] for s in seeds], int)
    farmers = np.array([pool[s]["placed_farmers"] for s in seeds], int)
    margin = np.array([pool[s]["score_margin_abs"] for s in seeds], int)
    sc = np.array([pool[s]["scores"] for s in seeds], int)
    lead = np.array([sc[i, mover[i]] - sc[i, 1 - mover[i]] for i in range(len(seeds))], int)
    bag = np.array([pool[s]["bag_size"] for s in seeds], int)
    qgap = np.array([qprobe[s]["q_gap_1_2"] if s in qprobe else np.nan for s in seeds], float)
    qent = np.array([qprobe[s]["entropy"] if s in qprobe else np.nan for s in seeds], float)

    S["ALL"] = {"all": np.ones(len(seeds), bool)}

    S["tile_class"] = {c: tile == c for c in sorted(set(tile))}

    # top individual tiles (n >= 40)
    cnt = Counter(tile_raw)
    S["tile_identity(n>=40)"] = {t: tile_raw == t for t, c in cnt.most_common() if c >= 40}

    lab, cuts = tercile_labels(n_legal)
    S[f"branching n_legal (cuts {cuts[0]:.0f}/{cuts[1]:.0f})"] = {
        f"{k}": lab == k for k in ("low", "mid", "high")}

    S["solver decisiveness"] = {
        "gap==0 (tied best)": gap == 0,
        "gap 0<g<=1": (gap > 0) & (gap <= 1),
        "gap >1": gap > 1,
    }

    lab, cuts = tercile_labels(spread)
    S[f"solver value_spread (cuts {cuts[0]:.1f}/{cuts[1]:.1f})"] = {
        f"{k}": lab == k for k in ("low", "mid", "high")}

    ok = ~np.isnan(qgap)
    lab = np.full(len(seeds), "na", dtype=object)
    if ok.sum():
        q1, q2 = np.quantile(qgap[ok], [1 / 3, 2 / 3])
        lab[ok & (qgap <= q1)] = "low"
        lab[ok & (qgap > q1) & (qgap <= q2)] = "mid"
        lab[ok & (qgap > q2)] = "high"
        S[f"teacher top-2 gap (cuts {q1:.3f}/{q2:.3f})"] = {
            k: lab == k for k in ("low", "mid", "high")}

    S["mover meeples free"] = {"0": mfree == 0, "1": mfree == 1, ">=2": mfree >= 2}
    S["opp meeples free"] = {"0": mfree_opp == 0, ">=1": mfree_opp >= 1}
    S["farmers on board"] = {"0": farmers == 0, "1-2": (farmers >= 1) & (farmers <= 2),
                             ">=3": farmers >= 3}
    S["mover score lead"] = {"behind": lead < -3, "close(|d|<=3)": np.abs(lead) <= 3,
                             "ahead": lead > 3}
    S["score margin |d|"] = {"<=3": margin <= 3, "4-10": (margin >= 4) & (margin <= 10),
                             ">10": margin > 10}
    S["bag_size"] = {str(b): bag == b for b in sorted(set(bag.tolist()))}
    S["ply"] = {str(p): ply == p for p in sorted(set(ply.tolist()))}
    return S


# --------------------------------------------------------------------------- #
# 6. metric machinery                                                           #
# --------------------------------------------------------------------------- #
def paired_stats(a, b, mask, higher_better=True, n_boot=N_BOOT):
    """a = candidate per-root metric, b = leaf per-root metric (aligned arrays).
    NaNs (tau on all-tied roots) dropped pairwise.  Returns dict."""
    m = mask & ~np.isnan(a) & ~np.isnan(b)
    n = int(m.sum())
    if n < 3:
        return {"n": n, "cand": float("nan"), "leaf": float("nan"),
                "delta": float("nan"), "ci": [float("nan")] * 2}
    av, bv = a[m], b[m]
    d = av - bv
    idx = RNG.integers(0, n, size=(n_boot, n))
    boot = d[idx].mean(axis=1)
    lo, hi = np.quantile(boot, [0.025, 0.975])
    return {"n": n, "cand": float(av.mean()), "leaf": float(bv.mean()),
            "delta": float(d.mean()), "ci": [float(lo), float(hi)],
            "z": float(d.mean() / (d.std(ddof=1) / math.sqrt(n))) if d.std(ddof=1) > 0 else 0.0}


def main():
    roots, metrics, prov = load_solver()
    seeds = sorted(roots)
    print(f"[solver] {len(seeds)} roots, rankers={len(metrics)}", flush=True)

    c0_arms, leaf_floor = load_c0_learners()
    metrics.update(c0_arms)

    pool = load_pool(roots)
    qprobe = load_qprobe(roots)
    print(f"[meta] pool matched {len(pool)}, qprobe matched {len(qprobe)}", flush=True)
    assert len(pool) == len(seeds)

    # per-ranker aligned arrays
    def arr(tag, j):
        return np.array([metrics[tag][s][j] if s in metrics[tag] else np.nan
                         for s in seeds], float)

    leaf_reg, leaf_t1, leaf_tau = arr(LEAF, 0), arr(LEAF, 1), arr(LEAF, 2)
    nets = [t for t in metrics if t != LEAF and t.split(":")[-1] not in LEAF_VARIANTS]
    nets = sorted(nets)
    print(f"[rankers] {len(nets)} learned rankers", flush=True)

    net_arrays = {t: (arr(t, 0), arr(t, 1), arr(t, 2)) for t in nets}

    # two ranker FAMILIES, kept separate because they are not the same kind of object
    #  A) deployable nets  = torch value-head rankers scored by solver_score.py
    #  B) c0 learners      = CL-065 ridge/GBDT REGRESSED DIRECTLY ON THE SOLVER
    #                        LABELS from the leaf's own component features
    #                        (cross-fit, in-corpus; an upper bound on learnability,
    #                        NOT an agent that could be deployed)
    FAM = {
        "deployable_nets": [t for t in nets
                            if not t.startswith("c0:") and not t.startswith("lw:")],
        "c0_oracle_supervised": [t for t in nets if t.startswith("c0:")],
        "leaf_reweight_ctrl": [t for t in nets if t.startswith("lw:")],
    }

    slices = build_slices(seeds, roots, pool, qprobe)

    report = {
        "provenance": prov,
        "n_roots": len(seeds),
        "leaf_floor_tau_from_c0_cache": leaf_floor,
        "overall": {},
        "learned_rankers": nets,
        "families": {k: v for k, v in FAM.items()},
        "slices": {},
    }

    # overall table for every ranker
    allmask = np.ones(len(seeds), bool)
    for t in nets:
        r, t1, tau = net_arrays[t]
        report["overall"][t] = {
            "tau": paired_stats(tau, leaf_tau, allmask),
            "top1": paired_stats(t1, leaf_t1, allmask),
            "regret": paired_stats(r, leaf_reg, allmask),
        }
    report["overall"][LEAF] = {
        "tau": {"n": int((~np.isnan(leaf_tau)).sum()), "cand": float(np.nanmean(leaf_tau))},
        "top1": {"n": len(seeds), "cand": float(leaf_t1.mean())},
        "regret": {"n": len(seeds), "cand": float(leaf_reg.mean())},
    }

    METRICS = [("tau", 2, True), ("top1", 1, True), ("regret", 0, False)]

    for fam, cells in slices.items():
        report["slices"][fam] = {}
        for cell, mask in cells.items():
            if mask.sum() < 15:
                continue
            entry = {"n_roots": int(mask.sum())}
            for famname, taglist in FAM.items():
                sub = {}
                for mname, j, hb in METRICS:
                    leafv = {2: leaf_tau, 1: leaf_t1, 0: leaf_reg}[j]
                    # pick the BEST ranker in this cell (max favourable to the net)
                    best_tag, best_val = None, None
                    for t in taglist:
                        v = net_arrays[t][j]
                        mm = mask & ~np.isnan(v)
                        if mm.sum() < 3:
                            continue
                        val = float(np.nanmean(v[mm]))
                        if best_val is None or (val > best_val if hb else val < best_val):
                            best_val, best_tag = val, t
                    if best_tag is None:
                        continue
                    v = net_arrays[best_tag][j]
                    st = paired_stats(v, leafv, mask)
                    st["best_net"] = best_tag
                    st["direction"] = "higher_better" if hb else "lower_better"
                    sub[mname] = st
                entry[famname] = sub
            report["slices"][fam][cell] = entry

    with open(OUT / "slice_scan.json", "w") as f:
        json.dump(report, f, indent=1, default=float)

    # ---- console table ---- #
    def fmt(st, hb):
        win = (st["delta"] > 0) if hb else (st["delta"] < 0)
        ciclear = (st["ci"][0] > 0) if hb else (st["ci"][1] < 0)
        flag = "  <<< NET WINS" if (win and ciclear) else ""
        return (f"n={st['n']:4d}  leaf={st['leaf']:+.4f}  bestnet={st['cand']:+.4f}  "
                f"d={st['delta']:+.4f} [{st['ci'][0]:+.4f},{st['ci'][1]:+.4f}] "
                f"({st['best_net'].split(':')[-1]}){flag}")

    lines = []
    lines.append("=" * 100)
    lines.append("OVERALL (all 1,119 K=2 roots) — every learned ranker vs the v2.9 leaf")
    lines.append(f"  LEAF v29        tau={report['overall'][LEAF]['tau']['cand']:+.4f}  "
                 f"top1={report['overall'][LEAF]['top1']['cand']:+.4f}  "
                 f"regret={report['overall'][LEAF]['regret']['cand']:+.4f}")
    for t in sorted(nets, key=lambda x: -report["overall"][x]["tau"]["cand"]):
        o = report["overall"][t]
        lines.append(f"  {t:56s} tau={o['tau']['cand']:+.4f}  top1={o['top1']['cand']:+.4f}  "
                     f"regret={o['regret']['cand']:+.4f}")
    win_count = {f: 0 for f in FAM}
    cell_count = 0

    def observability(fam):
        # can a deployed agent condition on this stratum AT PLAY TIME?
        if fam.startswith("solver "):
            return "POST-HOC (derived from the solver label — NOT a usable gate)"
        if fam.startswith("teacher "):
            return "OBSERVABLE but EXPENSIVE (needs the h6400 deep search)"
        if fam == "ALL":
            return "-"
        return "OBSERVABLE at play time (usable hybrid gate)"

    for fam, cells in report["slices"].items():
        report["slices"][fam]["_observability"] = observability(fam)
        lines.append(f"\n### SLICE FAMILY: {fam}   [{observability(fam)}]")
        for cell, e in cells.items():
            if cell == "_observability":
                continue
            cell_count += 1
            lines.append(f"  [{cell}] n_roots={e['n_roots']}")
            for famname in ("deployable_nets", "c0_oracle_supervised", "leaf_reweight_ctrl"):
                sub = e.get(famname, {})
                for mname, hb in (("tau", True), ("top1", True), ("regret", False)):
                    if mname not in sub:
                        continue
                    st = sub[mname]
                    win = (st["delta"] > 0) if hb else (st["delta"] < 0)
                    ciclear = (st["ci"][0] > 0) if hb else (st["ci"][1] < 0)
                    if win and ciclear and fam != "ALL":
                        win_count[famname] += 1
                    lines.append(f"     {famname[:10]:10s} {mname:7s} " + fmt(st, hb))
    lines.append(f"\nCells scanned: {cell_count}; CI-clear net wins by family: {win_count}")
    txt = "\n".join(lines)
    print(txt)
    (OUT / "slice_scan_console.txt").write_text(txt)


if __name__ == "__main__":
    main()
