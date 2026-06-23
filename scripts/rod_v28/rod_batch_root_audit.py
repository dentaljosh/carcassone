#!/usr/bin/env python3
"""rod_batch512_calibration Phase 6 — merge a B512 midgame-label run into the existing
4-way root-audit data, producing the batch-calibration root-action deliverables.

Inputs:
  --b512-labels    : label_midgame.py output run with --ckpt iter_01_b512.pt under
                     CARCASSONNE_V25_MEEPLE_K=2.0 (v2.8 leaf). Its `iter8_choice` col = B512's
                     NeuralMCTS@200 root choice; `heur3200_choice`/`heur800_choice` = the v2.8
                     heuristic-ruler choices (deterministic given position+leaf).
  --existing-merged: measurement/rod_v28_continuation/ROOT_AUDIT_V28.jsonl — already holds, per
                     position_id: parent_choice (iter8), rod_choice (=B256/RoD_iter_01),
                     heur3200_v28_choice, heur800_v28_choice, band.

THE calibration metric: b512_agree_b256 — does the batch-512 net make the SAME root choices as
the batch-256 reference? Plus each net's agreement with the deep heuristic ruler and the parent,
by phase band. (Cross-checks heur3200 consistency between the two label sources.)

Produces (in --out-dir):
  BATCH_ROOT_AUDIT.jsonl         per-position merged record (parent / B256 / B512 / heur3200 / heur800)
  BATCH_ROOT_AUDIT_RESULTS.csv   overall + by-band agreements
  _batch_root_audit_summary.json compact dict for the .md writer
"""
from __future__ import annotations
import argparse, json, csv
from pathlib import Path


def load(p):
    return {r["position_id"]: r for r in (json.loads(l) for l in open(p))}


def agree(rows, a, b):
    rows = [r for r in rows if r.get(a) is not None and r.get(b) is not None]
    n = len(rows)
    return (sum(1 for r in rows if r[a] == r[b]) / n if n else float("nan"), n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--b512-labels", required=True)
    ap.add_argument("--existing-merged", required=True,
                    help="measurement/rod_v28_continuation/ROOT_AUDIT_V28.jsonl")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    b512 = load(args.b512_labels)
    ex = load(args.existing_merged)
    ids = sorted(set(b512) & set(ex))
    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)

    merged = []
    heur_consistent = 0
    for pid in ids:
        b, e = b512[pid], ex[pid]
        b512c = b.get("iter8_choice")                 # B512 root choice
        b256c = e.get("rod_choice")                   # B256 (RoD_iter_01) root choice
        parc = e.get("parent_choice")                 # iter8 parent root choice
        h3 = e.get("heur3200_v28_choice")             # deep heuristic ruler (from existing merge)
        h3_b = b.get("heur3200_choice")               # ruler as seen by the B512 label run
        h8 = e.get("heur800_v28_choice")
        if h3 == h3_b:
            heur_consistent += 1
        merged.append({
            "position_id": pid, "band": e.get("band"),
            "source_bucket": e.get("source_bucket"), "k_remaining": e.get("k_remaining"),
            "b512_choice": b512c, "b256_choice": b256c, "parent_choice": parc,
            "heur3200_v28_choice": h3, "heur800_v28_choice": h8,
            "b512_eq_b256": _eq(b512c, b256c),
            "b512_eq_parent": _eq(b512c, parc),
            "b256_eq_parent": _eq(b256c, parc),
            "b512_eq_heur3200": _eq(b512c, h3),
            "b256_eq_heur3200": _eq(b256c, h3),
            "parent_eq_heur3200": _eq(parc, h3),
            "b512_eq_heur800": _eq(b512c, h8),
            "heur3200_consistent": int(h3 == h3_b),
        })
    with open(out / "BATCH_ROOT_AUDIT.jsonl", "w") as fh:
        for m in merged:
            fh.write(json.dumps(m) + "\n")

    bands = ["opening", "early_mid", "mid", "late_mid", "pre_endgame"]

    def block(rows, label):
        b512_b256, n = agree(rows, "b512_choice", "b256_choice")
        b512_par, _ = agree(rows, "b512_choice", "parent_choice")
        b256_par, _ = agree(rows, "b256_choice", "parent_choice")
        b512_h3, _ = agree(rows, "b512_choice", "heur3200_v28_choice")
        b256_h3, _ = agree(rows, "b256_choice", "heur3200_v28_choice")
        par_h3, _ = agree(rows, "parent_choice", "heur3200_v28_choice")
        b512_h8, _ = agree(rows, "b512_choice", "heur800_v28_choice")
        return {"subset": label, "n": n,
                "b512_agree_b256": _r(b512_b256),
                "b512_agree_parent": _r(b512_par), "b256_agree_parent": _r(b256_par),
                "b512_agree_heur3200": _r(b512_h3), "b256_agree_heur3200": _r(b256_h3),
                "parent_agree_heur3200": _r(par_h3),
                "delta_b512_minus_b256_vs_heur3200": _r(b512_h3 - b256_h3),
                "b512_agree_heur800": _r(b512_h8)}

    results = [block(merged, "ALL")]
    for bd in bands:
        rb = [m for m in merged if m["band"] == bd]
        if rb:
            results.append(block(rb, bd))

    with open(out / "BATCH_ROOT_AUDIT_RESULTS.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
        w.writeheader(); w.writerows(results)

    a = results[0]
    print(f"positions merged: {len(ids)} | heur3200 consistent across label sources: {heur_consistent}/{len(ids)}")
    print(f"B512 agree B256 = {a['b512_agree_b256']}  (THE calibration metric: 1.0 = identical play)")
    print(f"B512 agree heur3200 = {a['b512_agree_heur3200']} | B256 = {a['b256_agree_heur3200']} | parent = {a['parent_agree_heur3200']}")
    print(f"B512 agree parent = {a['b512_agree_parent']} | B256 agree parent = {a['b256_agree_parent']}")
    json.dump({"all": a, "by_band": results[1:], "heur_consistent": heur_consistent, "n": len(ids)},
              open(out / "_batch_root_audit_summary.json", "w"), indent=2)


def _eq(a, b):
    return int(a == b) if (a is not None and b is not None) else None


def _r(x):
    return round(x, 4) if x == x else None   # NaN-safe round


if __name__ == "__main__":
    main()
