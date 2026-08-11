#!/usr/bin/env python3
"""Part B aggregate — endgame top-1 agreement + mean regret vs the exact solver,
for RoD1 / iter_08 / parent (v2.8 leaf) and the h3200 reference, from the per-net
regret dirs written by run_partb_regret.sh. Directly comparable to the cached L2-3
verdict numbers (iter8 0.667 / heur@3200 0.837 at K=2).

  python scripts/exact_hybrid/partb_aggregate.py [--base <partb_regret>] [--ks 2 3]
"""
from __future__ import annotations
import argparse, json, statistics as st
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
BASE = REPO / "measurement" / "exact_endgame_hybrid" / "partb_regret"
NETS = ["rod1", "iter08", "parent"]


def collect(d: Path, k: int):
    """-> {agent: {'top1':.., 'mean_regret':.., 'n':.., 'gt2','gt5'}} over solved positions."""
    per = {}
    npos = 0
    for p in sorted(d.glob(f"*_k{k}.json")):
        try:
            rec = json.load(open(p))
        except Exception:
            continue
        gt = rec.get("gt", {}).get("clairvoyant") or rec.get("gt", {}).get("marginalized")
        if not gt or not gt.get("solved"):
            continue
        npos += 1
        for a, m in gt.get("per_agent", {}).items():
            if m.get("regret") is None:
                continue
            per.setdefault(a, {"match": [], "regret": []})
            per[a]["match"].append(1 if m.get("match") else 0)
            per[a]["regret"].append(float(m["regret"]))
    out = {}
    for a, v in per.items():
        r = v["regret"]
        out[a] = dict(n=len(r), top1=sum(v["match"]) / len(v["match"]),
                      mean_regret=sum(r) / len(r), median_regret=st.median(r),
                      gt2=sum(1 for x in r if x > 2) / len(r),
                      gt5=sum(1 for x in r if x > 5) / len(r),
                      worst=max(r))
    out["_npos"] = npos
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(BASE))
    ap.add_argument("--ks", type=int, nargs="+", default=[2])
    args = ap.parse_args(argv)
    base = Path(args.base)

    L = ["# Part B — endgame top-1 agreement + regret vs the EXACT solver (v2.8 agents)", "",
         "clairvoyant solver (== marginalized at K=2). top-1 = fraction the agent's move is",
         "solver-optimal; regret = mean points lost vs optimal (mover perspective, >=0).",
         "h3200 here is the SAME v2.7-leaf reference used by the L2-3 verdict (iter8 0.667 /",
         "heur@3200 0.837 @K=2) -> the RoD1/iter08 rows are directly comparable to it.", ""]
    rows = []
    for k in args.ks:
        L.append(f"## K={k}")
        L.append("net (agent) | n | top-1 | mean regret | median | >2pt | >5pt | worst")
        L.append("--- | --- | --- | --- | --- | --- | --- | ---")
        for net in NETS:
            d = base / net
            if not d.exists():
                continue
            res = collect(d, k)
            rod = res.get("iter8")          # the loaded net == this `net`
            h = res.get("heur@3200")
            if rod:
                L.append(f"**{net}** (v2.8) | {rod['n']} | **{rod['top1']:.3f}** | {rod['mean_regret']:.2f} | "
                         f"{rod['median_regret']:.1f} | {100*rod['gt2']:.1f}% | {100*rod['gt5']:.1f}% | {rod['worst']:.0f}")
                rows.append(dict(k=k, net=net, **{kk: rod[kk] for kk in ("n", "top1", "mean_regret", "worst")}))
            if h and net == NETS[0]:        # h3200 identical across dirs; print once
                L.append(f"heur@3200 (v2.7 ref) | {h['n']} | **{h['top1']:.3f}** | {h['mean_regret']:.2f} | "
                         f"{h['median_regret']:.1f} | {100*h['gt2']:.1f}% | {100*h['gt5']:.1f}% | {h['worst']:.0f}")
        L.append("")
    # one-line read
    L += ["## Read",
          "If RoD1/iter08 top-1 << h3200 top-1 with sub-point mean regret, the picture matches L2-3:",
          "the learned agents play the endgame measurably worse than the deep heuristic, but the",
          "point-cost is small -> exact handoff fixes a real-but-tiny leak; h3200 needs little fixing."]
    outp = base.parent / "PART_B_digest.md"
    open(outp, "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\n[written] {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
