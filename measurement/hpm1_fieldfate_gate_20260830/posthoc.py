#!/usr/bin/env python3
"""HP-M1 gate — POST-HOC diagnostics. DESCRIPTIVE. ADJUDICATES NOTHING.

Written and run AFTER the three pre-registered bars were read, to answer one
question the bars raise but do not answer: *where does the modest AUC that does
exist actually come from?* Nothing here can move a bar (PREREG §9), and the
readout labels every number in it as post-hoc.
"""
from __future__ import annotations

import glob
import importlib.util
import json
import sys

import numpy as np

HPM1 = sys.argv[1] if len(sys.argv) > 1 else "/home/doctor/hpm1_run"
OUT = f"{HPM1}/out"

spec = importlib.util.spec_from_file_location("g", f"{HPM1}/fieldfate_gate.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)
order = json.load(open(f"{OUT}/FEATURES.json"))["order"]


def load(pat, pred):
    out = []
    for f in glob.glob(pat):
        for line in open(f):
            r = json.loads(line)
            if r.get("ok") and pred(r):
                out.append(r)
    return out


prim = load(f"{OUT}/rows_E4_fixed_v1.jsonl", lambda r: r["seat_role"] == "champion")
own = load(f"{OUT}/rows_E4_fixed_v1.jsonl", lambda r: r["seat_role"] == "owner")
spr = load(f"{OUT}/rows_SP449_walled.jsonl", lambda r: True)
y = np.array([r["y"] for r in prim])


def oof(rows, feats, yy):
    X = np.array([[float(r["x"][k]) for k in feats] for r in rows])
    f = G.folds_for(rows)
    o = np.full(len(rows), np.nan)
    for k in range(G.N_FOLDS):
        tr, te = f != k, f == k
        o[te] = G.Model(X[tr], yy[tr]).score(X[te])
    return G.auc(o, yy)


single = {k: G.auc(np.array([float(r["x"][k]) for r in prim]), y) for k in order}
PHASE = ["bag_n", "ply_frac"]
COMP = [k for k in order if k not in PHASE]


def profile(rows, name):
    z = [r for r in rows if r["y"] == 0]
    s = [r for r in rows if r["y"] == 1]

    def fr(v, k):
        return (sum(1 for r in v if r["x"][k] > 0) / len(v)) if v else None

    def mn(v, k):
        return float(np.mean([r["x"][k] for r in v])) if v else None

    return {"name": name, "n": len(rows), "n_zero": len(z),
            "zero_rate": len(z) / len(rows) if rows else None,
            "zero_proj_finished_gt0": fr(z, "proj_finished_cities"),
            "scoring_proj_finished_gt0": fr(s, "proj_finished_cities"),
            "zero_mean_proj_finished": mn(z, "proj_finished_cities"),
            "scoring_mean_proj_finished": mn(s, "proj_finished_cities"),
            "zero_mean_bag_n": mn(z, "bag_n"),
            "scoring_mean_bag_n": mn(s, "bag_n"),
            "zero_mean_entry_cells": mn(z, "field_entry_cells"),
            "scoring_mean_entry_cells": mn(s, "field_entry_cells")}


out = {
    "_note": ("POST-HOC, DESCRIPTIVE, NOT PRE-REGISTERED. Adjudicates NOTHING. "
              "Computed AFTER the bars were read, to explain WHERE the modest "
              "AUC that does exist comes from. Read as diagnosis, never as a bar."),
    "single_feature_auc_top10_by_distance_from_0.5": dict(sorted(
        single.items(), key=lambda kv: -abs(kv[1] - 0.5))[:10]),
    "oof_auc_full_45": oof(prim, order, y),
    "oof_auc_phase_only_bag_n_plus_ply_frac": oof(prim, PHASE, y),
    "oof_auc_no_phase_43": oof(prim, COMP, y),
    "auc_ply_frac_alone": single["ply_frac"],
    "b_leaf_equals_b_bag_rows": {
        "identical": sum(1 for r in prim + own + spr if r["b_leaf"] == r["b_bag"]),
        "total": len(prim) + len(own) + len(spr)},
    "profiles": [profile(prim, "E4 champion (fixed_v1) = PRIMARY"),
                 profile(own, "E4 owner (fixed_v1)"),
                 profile(spr, "SP449 champion self-play (walled)")],
    "bag_minus_deck_note": (
        "264/3520 rows carry bag_minus_deck==2: an unplaceable drawn tile is "
        "discarded, so it is neither on the board nor in the deck and the "
        "board-derived bag keeps counting it as remaining. Bias <=2 tiles in a "
        "bag of ~40-70, on 4.3% of primary rows. DISCLOSED, NOT CORRECTED — the "
        "bar statistics had already been read (PREREG 9)."),
}
json.dump(out, open(f"{OUT}/POSTHOC.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "profiles"}, indent=1))
for p in out["profiles"]:
    print(json.dumps(p))
