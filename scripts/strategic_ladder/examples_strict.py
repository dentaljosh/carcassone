"""Mine 20-50 inspectable examples per strict motif (full provenance). Prioritises
competitive (|margin_before|<=20) positions with clear agent divergence + high magnitude,
spread across distinct games. -> HIGH_PRECISION_EXAMPLES.md
"""
import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import strict_motifs as S

SHOW = ["random", "greedy", "h800", "h3200", "h6400", "rod1"]


def took(r, ag, m):
    sat = set(r["strict_labels"][m]["sat"])
    a = r["chosen"] if ag == "ACTUAL" else r["choices"].get(ag, -2)
    return a in sat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--harvest", default="measurement/strategic_behavior_ladder/strict_harvest.jsonl")
    ap.add_argument("--out", default="measurement/strategic_behavior_ladder/HIGH_PRECISION_EXAMPLES.md")
    ap.add_argument("--per-motif", type=int, default=30)
    args = ap.parse_args()
    recs = [json.loads(l) for l in open(args.harvest) if l.strip()]
    L = ["# High-precision strategic-trap examples (inspect for plausibility)\n",
         "deck id = `seed` (deck is deterministic from seed). T=took, .=missed.\n"]
    for m in S.MOTIFS:
        opp = [r for r in recs if m in r["strict_labels"]]
        def sc(r):
            takes = [took(r, a, m) for a in SHOW]
            div = len(set(takes)) > 1
            comp = abs(r["margin_before"]) <= 20
            return (div * 2 + comp) * 100 + r["strict_labels"][m]["mag"]
        opp.sort(key=sc, reverse=True)
        seen_games = defaultdict(int)
        L.append(f"\n## {m}  ({len(opp)} opportunities)\n")
        shown = 0
        for r in opp:
            gk = (r["regime"], r["seed"], r["g"])
            if seen_games[gk] >= 3:   # spread across games
                continue
            if shown >= args.per_motif:
                break
            seen_games[gk] += 1
            shown += 1
            lab = r["strict_labels"][m]
            tk = " ".join(f"{a}={'T' if took(r,a,m) else '.'}" for a in SHOW)
            L.append(
                f"**{shown}.** idx={r['idx']} regime=`{r['regime']}` seed={r['seed']} seat=P{r['mover']} "
                f"ply={r['ply']} {r['tile_phase']}  \n"
                f"   phase-K={r['k_remaining']} margin_before={r['margin_before']:+d} "
                f"scores={r['scores']} free_meeples={r['meeples_free']} legal={r['legal_n']} "
                f"qualifying={len(lab['sat'])} mag={lab['mag']:.0f}  \n"
                f"   threat: {lab['threat']}  \n"
                f"   takes: {tk}   actual(`{r['mover_spec']}`)={'T' if took(r,'ACTUAL',m) else '.'}  \n"
                f"   eventual: result {r['result_mover']} ({r['final_margin_mover']:+d})  \n")
    with open(args.out, "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
