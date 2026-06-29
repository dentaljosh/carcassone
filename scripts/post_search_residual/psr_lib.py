#!/usr/bin/env python3
"""Post-Search Residual Pilot — shared derivation library.

Loads the per-root snapshot JSONL (build_adaptive_dataset.py) and derives, per root:
  - sel[L]        : best_action(hL) under the mcts.py rule argmax(Q_rootpov, N), ties->lowest aid
  - regret[L]     : Q6400[sel(h6400)] - Q6400[sel(hL)]  (>=0, target = h6400 - hL)
  - q_gap_6400    : Q6400 top - 2nd  (how decisive the deep reference is)
  - labels        : positive_strong / positive_medium / negative
  - h200 diagnostics: entropy, top_visit_share, top2_q_gap, n_visited, legal_n

These are the building blocks for Stage 2 (oracle/uniform frontiers) and Stage 3 (predictors).
"""
from __future__ import annotations
import json, math
from pathlib import Path

import numpy as np

LEVELS = [200, 400, 800, 1600, 3200, 6400]
REF = 6400
PHASES = ["opening", "midgame", "late_mid", "pre_endgame", "endgame"]

# label thresholds (POST_SEARCH_PLAN.md Stage 0)
PS_GAP, PS_REG = 0.02, 0.02      # positive_strong
PM_GAP, PM_REG = 0.01, 0.01      # positive_medium
NEG_REG = 0.005                  # negative if regret(h200) below this
NEG_GAP = 0.005                  # ... or h6400 near-tie


def _best_action(levelmap):
    """argmax (Q_rootpov, N) over visited children; ties -> lowest action id.
    levelmap: {action(str|int): [N, Q_rootpov]}. Returns (action:int, Q:float, N:int)."""
    items = [(int(a), v[0], v[1]) for a, v in levelmap.items() if v[0] > 0]
    if not items:
        return None
    # sort by action asc so max() ties resolve to lowest aid (mirrors best_action)
    items.sort(key=lambda t: t[0])
    a, n, q = max(items, key=lambda t: (t[2], t[1]))[0], None, None
    # recover N,Q of the chosen action
    for aa, nn, qq in items:
        if aa == a:
            n, q = nn, qq
            break
    return a, q, n


def _diag200(levelmap):
    """h200 search diagnostics for escalation features."""
    Ns = np.array([v[0] for v in levelmap.values()], float)
    Qs = np.array([v[1] for v in levelmap.values()], float)  # root-POV
    tot = Ns.sum()
    if tot <= 0:
        return dict(entropy=0.0, top_share=0.0, top2_q_gap=0.0, n_visited=0)
    p = Ns / tot
    p = p[p > 0]
    entropy = float(-(p * np.log(p)).sum())
    top_share = float(Ns.max() / tot)
    qsort = np.sort(Qs)[::-1]
    top2_q_gap = float(qsort[0] - qsort[1]) if len(qsort) >= 2 else float(qsort[0])
    return dict(entropy=entropy, top_share=top_share, top2_q_gap=top2_q_gap,
                n_visited=int((Ns > 0).sum()))


def load_roots(path):
    rows = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        lv = r["levels"]
        ref = lv[str(REF)]
        ba_ref = _best_action(ref)
        if ba_ref is None:
            continue
        sel_ref = ba_ref[0]
        # Q6400 map keyed by action
        q6400 = {int(a): v[1] for a, v in ref.items()}
        maxQ = max(q6400.values())
        # q_gap_6400 (top - 2nd) over visited
        qv = sorted(q6400.values(), reverse=True)
        q_gap_6400 = float(qv[0] - qv[1]) if len(qv) >= 2 else float(qv[0])

        sel = {}
        regret = {}
        for L in LEVELS:
            ba = _best_action(lv[str(L)])
            if ba is None:
                sel[L] = None
                regret[L] = float("nan")
                continue
            sel[L] = ba[0]
            # selL must be in q6400 (visited-at-L subset of visited-at-6400); guard anyway
            qsel = q6400.get(sel[L])
            regret[L] = float(maxQ - qsel) if qsel is not None else float("nan")

        reg200 = regret[200]
        diag = _diag200(lv["200"])
        # labels
        agree_200_ref = (sel[200] == sel_ref)
        pos_strong = (q_gap_6400 >= PS_GAP) and (reg200 >= PS_REG)
        pos_medium = (q_gap_6400 >= PM_GAP) and (reg200 >= PM_REG)
        negative = (reg200 < NEG_REG) or agree_200_ref or (q_gap_6400 < NEG_GAP)

        rows.append({
            "group_id": int(r["group_id"]), "seed": int(r["seed"]),
            "ply": int(r["ply"]), "phase": r["phase"], "legal_n": int(r["legal_n"]),
            "sel": sel, "regret": regret, "q_gap_6400": q_gap_6400,
            "agree_200_ref": bool(agree_200_ref),
            "pos_strong": bool(pos_strong), "pos_medium": bool(pos_medium),
            "negative": bool(negative),
            "entropy200": diag["entropy"], "top_share200": diag["top_share"],
            "top2_q_gap200": diag["top2_q_gap"], "n_visited200": diag["n_visited"],
        })
    return rows


def seed_split(rows, salt_tr=0, frac_tr=0.70, frac_va=0.15):
    """Deterministic train/val/test split by game_seed (no root crosses splits)."""
    seeds = sorted({r["seed"] for r in rows})
    def bucket(s):
        h = (abs(hash((int(s), 12345))) % 1000) / 1000.0
        if h < frac_tr:
            return "tr"
        if h < frac_tr + frac_va:
            return "va"
        return "te"
    tag = {s: bucket(s) for s in seeds}
    tr = [r for r in rows if tag[r["seed"]] == "tr"]
    va = [r for r in rows if tag[r["seed"]] == "va"]
    te = [r for r in rows if tag[r["seed"]] == "te"]
    return tr, va, te


def regret_array(rows, L):
    return np.array([r["regret"][L] for r in rows], float)
