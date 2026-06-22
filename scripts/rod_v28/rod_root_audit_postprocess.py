#!/usr/bin/env python3
"""RoD Phase 6 — post-process two v2.8 midgame-label runs into the root-audit deliverables.

Inputs (each = label_midgame.py output under CARCASSONNE_V25_MEEPLE_K=2.0, i.e. v2.8 leaf):
  --rod-labels     : run with --ckpt RoD_iter_01.pt  (its `iter8_choice` col = RoD's NeuralMCTS@200 root choice)
  --parent-labels  : run with --ckpt iter8.pt        (its `iter8_choice` col = parent's root choice)
Both ran the SAME 1000 midgame positions; `heur3200_choice` / `heur800_choice` are the
v2.8 heuristic-ruler choices (deterministic given position+leaf, ~identical across runs).

Produces (in --out-dir):
  ROOT_AUDIT_V28.jsonl          per-position merged record
  ROOT_AUDIT_V28_RESULTS.csv    overall + by-band agreements and the parent-delta
  ROOT_AUDIT_V28.md             narrative

The headline metric: agreement of each agent's root move with heur@3200_v28's root move,
and the DELTA (RoD - parent). A positive delta = RoD moved its root choices TOWARD deep
heuristic search (the mechanism behind the closed equal-leaf gap).
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
    ap.add_argument("--rod-labels", required=True)
    ap.add_argument("--parent-labels", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    rod = load(args.rod_labels)
    par = load(args.parent_labels)
    ids = sorted(set(rod) & set(par))
    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)

    # merged per-position records
    merged = []
    heur_consistent = 0
    for pid in ids:
        r, p = rod[pid], par[pid]
        rc, ic = r.get("iter8_choice"), p.get("iter8_choice")          # RoD choice / parent (iter8) choice
        h3 = r.get("heur3200_choice"); h3p = p.get("heur3200_choice")
        h8 = r.get("heur800_choice")
        if h3 == h3p:
            heur_consistent += 1
        merged.append({
            "position_id": pid, "band": r.get("band"), "source_bucket": r.get("source_bucket"),
            "k_remaining": r.get("k_remaining"),
            "rod_choice": rc, "parent_choice": ic,
            "heur3200_v28_choice": h3, "heur800_v28_choice": h8,
            "rod_eq_heur3200": int(rc == h3), "parent_eq_heur3200": int(ic == h3),
            "rod_eq_parent": int(rc == ic),
            "parent_disagrees_heur3200": int(ic != h3),
            "rod_fixed_parent_miss": int(ic != h3 and rc == h3),   # parent wrong vs ruler, RoD matches ruler
        })
    with open(out / "ROOT_AUDIT_V28.jsonl", "w") as fh:
        for m in merged:
            fh.write(json.dumps(m) + "\n")

    # aggregate overall + by band
    bands = ["opening", "early_mid", "mid", "late_mid", "pre_endgame"]
    def block(rows, label):
        rod_h3, n = agree(rows, "rod_choice", "heur3200_v28_choice")
        par_h3, _ = agree(rows, "parent_choice", "heur3200_v28_choice")
        rod_h8, _ = agree(rows, "rod_choice", "heur800_v28_choice")
        rod_par, _ = agree(rows, "rod_choice", "parent_choice")
        miss = [m for m in rows if m["parent_disagrees_heur3200"]]
        fixed = (sum(m["rod_fixed_parent_miss"] for m in miss) / len(miss)) if miss else float("nan")
        return {"subset": label, "n": n,
                "rod_agree_heur3200": round(rod_h3, 4), "parent_agree_heur3200": round(par_h3, 4),
                "delta_rod_minus_parent": round(rod_h3 - par_h3, 4),
                "rod_agree_heur800": round(rod_h8, 4),
                "rod_agree_parent": round(rod_par, 4),
                "n_parent_missed_ruler": len(miss),
                "rod_recovers_parent_miss": (round(fixed, 4) if fixed == fixed else None)}

    rows_all = merged
    results = [block(rows_all, "ALL")]
    for b in bands:
        rb = [m for m in merged if m["band"] == b]
        if rb:
            results.append(block(rb, b))

    with open(out / "ROOT_AUDIT_V28_RESULTS.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
        w.writeheader(); w.writerows(results)

    a = results[0]
    print(f"positions merged: {len(ids)} | heur3200 consistent across runs: {heur_consistent}/{len(ids)}")
    print(f"ROD agree heur3200_v28 = {a['rod_agree_heur3200']}  |  PARENT = {a['parent_agree_heur3200']}  |  DELTA = {a['delta_rod_minus_parent']:+}")
    print(f"ROD agree parent(iter8) = {a['rod_agree_parent']}  | ROD recovers parent's ruler-misses = {a['rod_recovers_parent_miss']}")
    # stash a compact dict for the .md writer
    json.dump({"all": a, "by_band": results[1:], "heur_consistent": heur_consistent, "n": len(ids)},
              open(out / "_root_audit_summary.json", "w"), indent=2)


if __name__ == "__main__":
    main()
