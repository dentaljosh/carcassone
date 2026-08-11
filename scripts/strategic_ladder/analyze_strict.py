"""Analyze the strict (high-precision) harvest. Take rates by agent/regime/phase,
RoD1-vs-h6400 on identical positions, and PRE-MOVE-controlled outcome sanity (no
close-game collider). Emits a digest + CSV + per-motif examples.
"""
import argparse
import json
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import strict_motifs as S

LADDER = ["random", "greedy", "h200", "h800", "h3200", "h6400", "rod1"]
WEAK = {"random"}
STRONG = {"h3200", "h6400", "rod1", "iter08"}
ALREADY_WON = 20


def opp_class(s):
    return "weak" if s in WEAK else ("strong" if s in STRONG else "mid")


def load(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def took(r, ag, m):
    if m not in r["strict_labels"]:
        return None
    sat = set(r["strict_labels"][m]["sat"])
    a = r["chosen"] if ag == "ACTUAL" else r["choices"].get(ag, -2)
    return a in sat


def rate(recs, ag, m, filt=None):
    k = n = 0
    for r in recs:
        if m not in r["strict_labels"] or (filt and not filt(r)):
            continue
        t = took(r, ag, m)
        if t is None:
            continue
        n += 1
        k += int(t)
    return k, n, (k / n if n else float("nan"))


def wr(recs):
    n = len(recs)
    if not n:
        return (0, float("nan"), float("nan"))
    w = sum(1 for r in recs if r["result_mover"] == "W")
    return (n, w / n, sum(r["final_margin_mover"] for r in recs) / n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--harvest", default="measurement/strategic_behavior_ladder/strict_harvest.jsonl")
    ap.add_argument("--out", default="measurement/strategic_behavior_ladder")
    args = ap.parse_args()
    recs = load(args.harvest)
    L = ["# Strict high-precision motifs — analysis\n", f"positions: {len(recs)}\n"]

    # counts
    L.append("## Opportunity counts (raw + distinct games)\n")
    L.append("| motif | raw | distinct games | by opp-class (weak/mid/strong) |")
    L.append("|---|---|---|---|")
    for m in S.MOTIFS:
        opp = [r for r in recs if m in r["strict_labels"]]
        games = {(r["regime"], r["seed"], r["g"]) for r in opp}
        byc = defaultdict(int)
        for r in opp:
            byc[opp_class(r["opp_spec"])] += 1
        L.append(f"| {m} | {len(opp)} | {len(games)} | {byc['weak']}/{byc['mid']}/{byc['strong']} |")

    # Part C — take rate by agent, overall + competitive + vs weak
    L.append("\n## Part C — take rate by agent (opportunity-normalized)\n")
    for m in S.MOTIFS:
        L.append(f"\n**{m}**\n")
        L.append("| agent | all | vs weak | vs strong | competitive(|m|≤20) | already-won(m>20) |")
        L.append("|---|---|---|---|---|---|")
        for ag in LADDER:
            cells = [rate(recs, ag, m),
                     rate(recs, ag, m, lambda r: opp_class(r["opp_spec"]) == "weak"),
                     rate(recs, ag, m, lambda r: opp_class(r["opp_spec"]) == "strong"),
                     rate(recs, ag, m, lambda r: abs(r["margin_before"]) <= ALREADY_WON),
                     rate(recs, ag, m, lambda r: r["margin_before"] > ALREADY_WON)]
            L.append(f"| {ag} | " + " | ".join(f"{(c[2]*100):.0f}% ({c[0]}/{c[1]})" if c[1] else "--" for c in cells) + " |")

    # Part D — rod1 vs h6400 on identical positions
    L.append("\n## Part D — RoD1 vs h6400 on identical strict positions\n")
    L.append("| motif | h6400 | rod1 | Δ | h6400-take/rod1-miss (competitive / padding) |")
    L.append("|---|---|---|---|---|")
    for m in S.MOTIFS:
        h = rate(recs, "h6400", m)
        r = rate(recs, "rod1", m)
        opp = [x for x in recs if m in x["strict_labels"]]
        dis = [x for x in opp if took(x, "h6400", m) and not took(x, "rod1", m)]
        dis_comp = sum(1 for x in dis if abs(x["margin_before"]) <= ALREADY_WON)
        dis_pad = len(dis) - dis_comp
        dh = (h[2] - r[2]) * 100 if (h[1] and r[1]) else float("nan")
        L.append(f"| {m} | {h[2]*100:.0f}% ({h[0]}/{h[1]}) | {r[2]*100:.0f}% ({r[0]}/{r[1]}) | "
                 f"{dh:+.0f}pp | {len(dis)} ({dis_comp} comp / {dis_pad} padding) |")

    # Part E — pre-move-controlled outcome (NO close-game collider)
    L.append("\n## Part E — pre-move-controlled outcome sanity (ACTUAL mover; no collider)\n")
    L.append("win% = P(mover wins). Stratified by PRE-move margin. (thin cells ⚠)\n")
    for m in S.MOTIFS:
        opp = [r for r in recs if m in r["strict_labels"] and r["result_mover"] in ("W", "L", "D")]
        L.append(f"\n**{m}** (n={len(opp)})")
        L.append("| stratum | take win% (n) | miss win% (n) | Δwin | Δmargin |")
        L.append("|---|---|---|---|---|")
        for lab, f in [("all", lambda r: True),
                       ("behind (≤-5)", lambda r: r["margin_before"] <= -5),
                       ("even (-4..4)", lambda r: -4 <= r["margin_before"] <= 4),
                       ("ahead (≥5)", lambda r: r["margin_before"] >= 5),
                       ("vs weak", lambda r: opp_class(r["opp_spec"]) == "weak"),
                       ("vs strong", lambda r: opp_class(r["opp_spec"]) == "strong")]:
            sub = [r for r in opp if f(r)]
            tk = [r for r in sub if took(r, "ACTUAL", m)]
            ms = [r for r in sub if took(r, "ACTUAL", m) is False]
            nt, pt, mt = wr(tk)
            nm, pm, mm = wr(ms)
            dwin = (pt - pm) * 100 if (nt and nm) else float("nan")
            dmar = (mt - mm) if (nt and nm) else float("nan")
            flag = " ⚠" if (nt < 15 or nm < 15) else ""
            L.append(f"| {lab} | {pt*100:.0f}% ({nt}) | {pm*100:.0f}% ({nm}) | {dwin:+.0f}pp | {dmar:+.1f}{flag} |")

    digest = os.path.join(args.out, "STRICT_ANALYSIS.md")
    with open(digest, "w") as f:
        f.write("\n".join(L) + "\n")
    # CSV
    import csv
    with open(os.path.join(args.out, "strict_positions.csv"), "w", newline="") as f:
        w = csv.writer(f)
        head = ["idx", "motif", "regime", "seed", "g", "ply", "seat", "mover_spec", "opp_spec",
                "tile_phase", "k", "margin_before", "legal_n", "magnitude", "actual_took",
                "final_margin_mover", "result_mover"] + [f"take_{a}" for a in LADDER]
        w.writerow(head)
        for r in recs:
            for m in r["strict_labels"]:
                lab = r["strict_labels"][m]
                w.writerow([r["idx"], m, r["regime"], r["seed"], r["g"], r["ply"], r["mover"],
                            r["mover_spec"], r["opp_spec"], r["tile_phase"], r["k_remaining"],
                            r["margin_before"], r["legal_n"], lab["mag"],
                            int(r["chosen"] in set(lab["sat"])), r["final_margin_mover"], r["result_mover"]]
                           + [int(r["choices"].get(a, -1) in set(lab["sat"])) for a in LADDER])
    print("\n".join(L))
    print(f"\nwrote {digest} + strict_positions.csv")


if __name__ == "__main__":
    main()
