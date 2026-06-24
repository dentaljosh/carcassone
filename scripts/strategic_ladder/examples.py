"""Mine representative examples (Part E): per motif, positions where the strategic
divergence is clear and consequential -- a strong agent takes the motif and a weaker
one (or RoD1) misses, at high magnitude, with the eventual game outcome attached.

Structured descriptions (not ASCII) -- more reliable and reproducible. Each example
is fully provenance-stamped (seed/seat/ply/regime) so it can be replayed.

Run: .venv/bin/python scripts/strategic_ladder/examples.py \
   --harvest 'measurement/strategic_behavior_ladder/harvest/*.jsonl' \
   --out measurement/strategic_behavior_ladder/EXAMPLES.md
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from motifs import MOTIFS

REF_AGENTS = ["random", "greedy", "h800", "h3200", "h6400", "rod1", "iter08"]


def load(paths):
    recs = []
    for p in paths:
        with open(p) as f:
            recs.extend(json.loads(l) for l in f if l.strip())
    return recs


def took(rec, agent, motif):
    if motif not in rec["labels"]:
        return None
    sat = set(rec["labels"][motif]["sat"])
    a = rec["chosen"] if agent == "ACTUAL" else rec.get("choices", {}).get(agent, -2)
    return a in sat


def score(rec, motif):
    """Illustrativeness: high magnitude + h6400 takes while a weaker agent misses."""
    mag = rec["labels"][motif]["mag"]
    h6 = took(rec, "h6400", motif)
    rod = took(rec, "rod1", motif)
    gr = took(rec, "greedy", motif)
    diverge = 0
    if h6 and rod is False:
        diverge += 2          # h6400 takes, RoD1 misses -- the key contrast
    if h6 and gr is False:
        diverge += 1
    if took(rec, "random", motif) is False and h6:
        diverge += 1
    return diverge * 100 + mag


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--harvest", nargs="+", required=True)
    ap.add_argument("--out", default="measurement/strategic_behavior_ladder/EXAMPLES.md")
    ap.add_argument("--per-motif", type=int, default=6)
    args = ap.parse_args()
    paths = []
    for g in args.harvest:
        paths.extend(sorted(glob.glob(g)))
    recs = load(paths)

    L = ["# Representative strategic-behavior examples (Part E)\n",
         "Selected for clear, consequential divergence (strong agent takes, weaker misses), "
         "high magnitude. Each is provenance-stamped for replay.\n"]
    for m in MOTIFS:
        pool = [r for r in recs if m in r["labels"]]
        pool.sort(key=lambda r: score(r, m), reverse=True)
        L.append(f"\n## {m}  ({len(pool)} opportunities)\n")
        shown = 0
        for r in pool:
            if shown >= args.per_motif:
                break
            lab = r["labels"][m]
            takes = {ag: took(r, ag, m) for ag in REF_AGENTS}
            # require some divergence to be illustrative
            vals = [v for v in takes.values() if v is not None]
            if len(set(vals)) < 2 and shown >= 2:
                continue
            shown += 1
            tk = " ".join(f"{ag}={'T' if takes[ag] else ('m' if takes[ag] is False else '·')}"
                          for ag in REF_AGENTS)
            L.append(
                f"**{shown}.** regime=`{r['regime']}` seed={r['seed']} g={r['g']} ply={r['ply']} "
                f"mover=P{r['mover']}(`{r['mover_spec']}`) opp=`{r['opp_spec']}`  \n"
                f"   phase={r['phase']} k={r['k_remaining']} scores={r.get('scores')} "
                f"free_meeples={r.get('meeples_free')} legal_n={r['legal_n']} "
                f"magnitude={lab['mag']} detail={lab.get('detail', {})}  \n"
                f"   takes: {tk}  \n"
                f"   eventual: mover margin={r.get('final_margin_mover')} result={r.get('result_mover')}  \n")
    with open(args.out, "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"wrote {args.out} ({sum(1 for _ in open(args.out))} lines)")


if __name__ == "__main__":
    main()
