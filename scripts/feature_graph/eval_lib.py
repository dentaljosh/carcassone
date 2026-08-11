#!/usr/bin/env python3
"""Feature-Graph Comparator — shared eval library (Stages 2-4).

Loads rows_feat.npz, splits by game_seed (no sibling set spans splits), and computes
the SIBLING-RANKING metrics that gate this pilot. The object under test is always a
per-child SCORE; the leaf baseline B0 uses score=leaf_q. Everything is grouped by
`group_id` (one sibling set per group); metrics are means over groups.

Primary metric: selected-child teacher REGRET (lower is better) =
    oracle_q[argmax oracle_q] - oracle_q[argmax score]
i.e. how much teacher-Q we give up by trusting the model's top child over the teacher's.

The DECISIVE TAIL (the pilot's target) = groups where the v2.9 LEAF decisively misses:
    q_gap_1_2 >= 0.02  AND  leaf_regret >= 0.02      (~1197 groups full-pool; ~1197*test_frac in TEST)
Any candidate must cut mean regret on this tail (suggested >=10-15%) WITHOUT a broad
ordinary-subset regression.
"""
from __future__ import annotations
import numpy as np

NPZ_DEFAULT = "/home/doctor/projects/carcassone/measurement/feature_graph_comparator/data/rows_feat.npz"
PHASES = ["opening", "midgame", "late_mid", "pre_endgame", "endgame"]
DECISIVE_GAP = 0.02
DECISIVE_REGRET = 0.02


# ----------------------------------------------------------------------------- load + split
def load_rows(path: str = NPZ_DEFAULT):
    z = np.load(path, allow_pickle=False)
    d = {k: z[k] for k in z.files}
    d["feat_names"] = [str(s) for s in z["feat_names"]] if "feat_names" in z.files else \
        [f"f{i}" for i in range(d["feat"].shape[1])]
    d["phase"] = np.array([str(s) for s in d["phase"]])
    return d


def seed_split(game_seed: np.ndarray, fracs=(0.70, 0.15, 0.15), salt: int = 12345):
    """Deterministic split by distinct game_seed (a sibling set never spans splits)."""
    uniq = np.unique(game_seed)
    # stable pseudo-random order independent of seed magnitude/locality
    order = sorted(uniq.tolist(), key=lambda s: (hash((int(s), salt)) & 0xFFFFFFFF))
    n = len(order)
    n_tr = int(round(fracs[0] * n)); n_va = int(round(fracs[1] * n))
    tr = set(order[:n_tr]); va = set(order[n_tr:n_tr + n_va]); te = set(order[n_tr + n_va:])
    g = game_seed
    return (np.isin(g, list(tr)), np.isin(g, list(va)), np.isin(g, list(te)))


# ----------------------------------------------------------------------------- tier slicing
def tier_columns(feat_names):
    """Return index lists for ablations. Names follow FEATURE_GRAPH_SCHEMA: context F*,
    Tier-1 leaf-component (prefix 't1'/'leaf'/'base'/'closure'/'meeple'/'pretransform'/'d_'
    of components), Tier-2 structural (prefix 't2'/structural names). We classify by an
    explicit prefix the builder is asked to use: 'F_', 'T1_', 'T2_'."""
    idx = {"context": [], "tier1": [], "tier2": []}
    for i, nm in enumerate(feat_names):
        u = nm.upper()
        if u.startswith("F_") or u.startswith("CTX"):
            idx["context"].append(i)
        elif u.startswith("T1") or u.startswith("LEAF") or u.startswith("TIER1"):
            idx["tier1"].append(i)
        elif u.startswith("T2") or u.startswith("TIER2"):
            idx["tier2"].append(i)
        else:
            idx["tier2"].append(i)  # default unknown -> tier2 (rich)
    idx["t1_ctx"] = sorted(idx["context"] + idx["tier1"])
    idx["all"] = list(range(len(feat_names)))
    return idx


# ----------------------------------------------------------------------------- grouping
def make_groups(d, mask):
    """Build per-group views (sibling sets) restricted to rows in `mask`.
    Returns list of dicts: oracle_q, leaf_q, q_gap (scalar), phase, row_idx (global)."""
    gid = d["group_id"][mask]
    rows = np.flatnonzero(mask)
    order = np.argsort(gid, kind="stable")
    gid_s, rows_s = gid[order], rows[order]
    groups = []
    start = 0
    for i in range(1, len(gid_s) + 1):
        if i == len(gid_s) or gid_s[i] != gid_s[start]:
            r = rows_s[start:i]
            if len(r) >= 2:
                groups.append({
                    "rows": r,
                    "oracle_q": d["oracle_q"][r].astype(np.float64),
                    "leaf_q": d["leaf_q"][r].astype(np.float64),
                    "q_gap": float(d["q_gap"][r][0]),
                    "phase": str(d["phase"][r][0]),
                })
            start = i
    return groups


def _kendall_tau(x, y):
    n = len(x)
    if n < 2:
        return np.nan
    c = d = 0
    for i in range(n):
        for j in range(i + 1, n):
            s = (x[i] - x[j]) * (y[i] - y[j])
            if s > 0:
                c += 1
            elif s < 0:
                d += 1
    t = c + d
    return (c - d) / t if t else np.nan


# ----------------------------------------------------------------------------- metrics
def group_eval(groups, scores_by_row):
    """scores_by_row: dict-like / np array indexed by GLOBAL row id -> model score.
    Computes per-group selection metrics; returns per-group arrays for aggregation."""
    out = {k: [] for k in ("regret", "top1", "top3", "tau", "q_gap", "phase",
                            "leaf_regret", "n")}
    for g in groups:
        oq = g["oracle_q"]
        sc = np.asarray([scores_by_row[r] for r in g["rows"]], dtype=np.float64)
        tb = int(np.argmax(oq))
        sel = int(np.argmax(sc))
        leaf_sel = int(np.argmax(g["leaf_q"]))
        out["regret"].append(oq[tb] - oq[sel])
        out["leaf_regret"].append(oq[tb] - oq[leaf_sel])
        out["top1"].append(int(sel == tb))
        top3 = set(np.argsort(sc)[::-1][:3].tolist())
        out["top3"].append(int(tb in top3))
        out["tau"].append(_kendall_tau(sc, oq))
        out["q_gap"].append(g["q_gap"])
        out["phase"].append(g["phase"])
        out["n"].append(len(oq))
    return {k: np.asarray(v) if k != "phase" else np.asarray(v) for k, v in out.items()}


def summarize(ev, mask=None):
    sel = np.ones(len(ev["regret"]), bool) if mask is None else mask
    if sel.sum() == 0:
        return {"n": 0}
    taus = ev["tau"][sel]
    return {
        "n": int(sel.sum()),
        "regret_mean": round(float(np.mean(ev["regret"][sel])), 5),
        "regret_median": round(float(np.median(ev["regret"][sel])), 5),
        "top1": round(float(np.mean(ev["top1"][sel])), 4),
        "top3": round(float(np.mean(ev["top3"][sel])), 4),
        "tau_mean": round(float(np.nanmean(taus)), 4),
    }


def decisive_mask(ev):
    return (ev["q_gap"] >= DECISIVE_GAP) & (ev["leaf_regret"] >= DECISIVE_REGRET)


def report_block(name, ev):
    """Full metric block for one model: overall, decisive tail, ordinary, by phase."""
    dec = decisive_mask(ev)
    blk = {
        "model": name,
        "overall": summarize(ev),
        "decisive_tail": summarize(ev, dec),
        "ordinary": summarize(ev, ~dec),
        "by_phase": {ph: summarize(ev, ev["phase"] == ph) for ph in PHASES},
    }
    return blk
