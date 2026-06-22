#!/usr/bin/env python3
"""Phase 1 — consolidate v2.7 failure cases from existing disagreement datasets.

Mines the two disagreement CSVs produced by the pre-tool (endgame, exact/heur@3200
labels) and midgame (heur@3200 teacher labels) audits into ONE normalized table,
tagged by a v2.7-failure CLASS and the candidate v2.8 patch family that would
target it. Measurement only — reads existing artifacts, writes a CSV. No model,
no search run here.

In : measurement/midgame_reference/MIDGAME_DISAGREEMENT_CATEGORIES.csv
     measurement/pre_tool_audit/DISAGREEMENT_CATEGORIES.csv
Out: measurement/heuristic_v28/V27_FAILURE_CASES.csv
"""
from __future__ import annotations
import csv
import os
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MID = os.path.join(REPO, "measurement/midgame_reference/MIDGAME_DISAGREEMENT_CATEGORIES.csv")
PRE = os.path.join(REPO, "measurement/pre_tool_audit/DISAGREEMENT_CATEGORIES.csv")
OUT = os.path.join(REPO, "measurement/heuristic_v28/V27_FAILURE_CASES.csv")

# Normalized failure CLASS + the candidate v2.8 patch family + leaf-addressable flag.
# Mapping is INTERPRETATION (a hypothesis map), marked as such in the taxonomy doc.
MID_MAP = {
    # midgame `category` -> (failure_class, candidate_patch, leaf_addressable)
    "structural/closure":      ("closure-timing/farm-growth", "completion_timing_v1|farm_final_value_v1", "partial"),
    "completion/score-greed":  ("completion-timing",          "completion_timing_v1",                     "partial"),
    "meeple-economy":          ("meeple-economy",             "meeple_economy_v1",                        "yes"),
    "bag/scarcity":            ("open-edge-scarcity",         "open_edge_scarcity_v1",                    "weak"),
    "immediate-score":         ("immediate-scoring",          "(mostly v2.7-covered)",                    "weak"),
    "structural/unclear":      ("structural-positional",      "NONE(search-horizon)",                     "no"),
}
PRE_MAP = {
    # pre-tool `mechanism` -> (failure_class, candidate_patch, leaf_addressable)
    "structural-or-farm":          ("farm-final-scoring/structural", "farm_final_value_v1", "partial"),
    "completion":                  ("completion-timing",             "completion_timing_v1", "yes"),
    "no-stronger-ref(both-miss)":  ("search-horizon(both-miss)",     "NONE(search-horizon)", "no"),
}

rows_out = []

# ---- midgame (teacher = heur@3200) ----
mid = list(csv.DictReader(open(MID)))
for r in mid:
    if r["v27_miss"] != "True":
        continue  # only cases where v2.7-static actually disagrees with the teacher
    fclass, patch, leafable = MID_MAP.get(r["category"], ("other", "?", "?"))
    rows_out.append({
        "case_id": f"mid::{r['pid']}",
        "dataset": "midgame", "position_id": r["pid"], "k": r["k"], "band": r["band"],
        "source": r["source"], "n_legal": r["n_legal"], "gap": r["gap_q"],
        "v27_choice": r["v27"], "ref_choice": r["teacher"], "ref_kind": "teacher(heur@3200)",
        "v27_q": r["v27_q"], "ref_q": r["teacher_q"],
        "v27_eval": "", "ref_eval": "",
        "mechanism_raw": r["category"], "failure_class": fclass,
        "candidate_patch": patch, "leaf_addressable": leafable,
        "also_iter8_miss": r["iter8_miss"], "raw_path": "",
    })

# ---- endgame (ref = exact K=2 / heur@3200 stronger-ref) ----
pre = list(csv.DictReader(open(PRE)))
for r in pre:
    fclass, patch, leafable = PRE_MAP.get(r["mechanism"], ("other", "?", "?"))
    rows_out.append({
        "case_id": f"end::{r['position_id']}",
        "dataset": "endgame", "position_id": r["position_id"], "k": r["k"], "band": "endgame",
        "source": r["source"], "n_legal": r["legal_n"], "gap": r["gap"],
        "v27_choice": r["iter8_v27"], "ref_choice": r["ref_action"], "ref_kind": "exact/heur@3200",
        "v27_q": "", "ref_q": "",
        # iter8_v27 / ref_v27 are the v2.7 ACTION SCORES of iter8's move vs the ref move
        "v27_eval": r["iter8_v27"], "ref_eval": r["ref_v27"],
        "mechanism_raw": r["mechanism"] + "|" + r["v27_axis"], "failure_class": fclass,
        "candidate_patch": patch, "leaf_addressable": leafable,
        "also_iter8_miss": "True", "raw_path": r["raw_path"],
    })

cols = ["case_id", "dataset", "position_id", "k", "band", "source", "n_legal", "gap",
        "v27_choice", "ref_choice", "ref_kind", "v27_q", "ref_q", "v27_eval", "ref_eval",
        "mechanism_raw", "failure_class", "candidate_patch", "leaf_addressable",
        "also_iter8_miss", "raw_path"]
with open(OUT, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols)
    w.writeheader()
    w.writerows(rows_out)

print(f"wrote {len(rows_out)} cases -> {OUT}")
print("by dataset:", Counter(r["dataset"] for r in rows_out))
print("by failure_class:", Counter(r["failure_class"] for r in rows_out))
print("by leaf_addressable:", Counter(r["leaf_addressable"] for r in rows_out))
print("by candidate_patch:", Counter(r["candidate_patch"] for r in rows_out))
