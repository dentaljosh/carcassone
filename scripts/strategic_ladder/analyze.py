"""Analyze the panel harvest -> the 6 benchmark tables + pseudo-human ladder +
anti-benchmax safeguards. Opportunity-normalized rates only (never raw counts).

Reads merged harvest jsonl(s). Each record carries:
  meta: regime, mover_spec, opp_spec, phase, k_remaining, legal_n, chosen,
        final_margin_mover, result_mover, meeples_free
  labels: {motif: {sat:[...], mag, detail}}   (only motifs whose OPPORTUNITY fired)
  choices: {agent_spec: action_idx}           (counterfactual panel)

A take = chosen action in the motif's satisfying set. "ACTUAL" uses the mover's real
move (chosen); panel agents use choices[agent] (every agent on the SAME position ->
agent-unbiased). Writes ANALYSIS_DIGEST.md + per-table CSVs.
"""
import argparse
import glob
import json
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from roster import PANEL
from motifs import MOTIFS

WEAK = {"random"}
MID = {"greedy", "h200", "h200_v27", "h800"}
STRONG = {"h3200", "h6400", "rod1", "iter08"}
LADDER = ["random", "greedy", "h200_v27", "h200", "h800", "h3200", "h6400", "rod1", "iter08"]
CLOSE_MARGIN = 5


def opp_class(spec):
    return "weak" if spec in WEAK else ("strong" if spec in STRONG else "mid")


def load(paths):
    recs = []
    for p in paths:
        with open(p) as f:
            for line in f:
                line = line.strip()
                if line:
                    recs.append(json.loads(line))
    return recs


def wilson(k, n):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    z = 1.96
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (p, max(0.0, centre - half), min(1.0, centre + half))


def took(rec, agent, motif):
    """True/False if agent took the motif; None if no choice available."""
    if motif not in rec["labels"]:
        return None
    sat = set(rec["labels"][motif]["sat"])
    if agent == "ACTUAL":
        a = rec.get("chosen", -1)
    else:
        a = rec.get("choices", {}).get(agent, -2)
    return a in sat


def rate_table(recs, agents, motif, filt=None):
    """{agent: (k, n, p, lo, hi)} over opportunity positions (optionally filtered)."""
    out = {}
    pool = [r for r in recs if motif in r["labels"] and (filt is None or filt(r))]
    for ag in agents:
        k = n = 0
        for r in pool:
            t = took(r, ag, motif)
            if t is None:
                continue
            n += 1
            k += int(t)
        p, lo, hi = wilson(k, n)
        out[ag] = (k, n, p, lo, hi)
    return out


def fmt_rate(t):
    k, n, p, lo, hi = t
    if n == 0:
        return "  --  "
    return f"{p*100:4.0f}% ({k}/{n})"


def section(title):
    return f"\n## {title}\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--harvest", nargs="+", required=True, help="harvest jsonl path(s)/globs")
    ap.add_argument("--out", default="measurement/strategic_behavior_ladder")
    args = ap.parse_args()

    paths = []
    for g in args.harvest:
        paths.extend(sorted(glob.glob(g)))
    recs = load(paths)
    os.makedirs(args.out, exist_ok=True)
    L = []
    L.append(f"# Strategic-behavior ladder — analysis digest\n")
    L.append(f"Positions: {len(recs)}  |  panel: {PANEL}\n")

    # opportunity inventory
    L.append(section("Opportunity inventory (positions where each motif fires)"))
    L.append("| motif | n_opp | by opp-class (weak/mid/strong) | by phase |")
    L.append("|---|---|---|---|")
    for m in MOTIFS:
        opp = [r for r in recs if m in r["labels"]]
        byc = defaultdict(int)
        byp = defaultdict(int)
        for r in opp:
            byc[opp_class(r["opp_spec"])] += 1
            byp[r["phase"]] += 1
        cls = "/".join(str(byc[c]) for c in ("weak", "mid", "strong"))
        ph = " ".join(f"{k}:{v}" for k, v in sorted(byp.items()))
        L.append(f"| {m} | {len(opp)} | {cls} | {ph} |")

    # TABLE 1 — motif take rates by agent (ladder)
    L.append(section("Table 1 — motif take rate by agent (opportunity-normalized)"))
    L.append("| agent | " + " | ".join(MOTIFS) + " |")
    L.append("|---|" + "|".join("---" for _ in MOTIFS) + "|")
    t1 = {m: rate_table(recs, LADDER + ["ACTUAL"], m) for m in MOTIFS}
    for ag in LADDER:
        row = [fmt_rate(t1[m][ag]) for m in MOTIFS]
        L.append(f"| {ag} | " + " | ".join(row) + " |")
    L.append(f"| _ACTUAL(mover)_ | " + " | ".join(fmt_rate(t1[m]["ACTUAL"]) for m in MOTIFS) + " |")

    # TABLE 2 — take rate by OPPONENT strength (strong-vs-weak vs strong-vs-strong)
    L.append(section("Table 2 — take rate by opponent strength (board context)"))
    for m in MOTIFS:
        L.append(f"\n**{m}**\n")
        L.append("| agent | vs weak | vs mid | vs strong |")
        L.append("|---|---|---|---|")
        for ag in LADDER:
            cells = []
            for cls in ("weak", "mid", "strong"):
                rt = rate_table(recs, [ag], m, filt=lambda r, c=cls: opp_class(r["opp_spec"]) == c)
                cells.append(fmt_rate(rt[ag]))
            L.append(f"| {ag} | " + " | ".join(cells) + " |")

    # TABLE 3 — high-value MISSED opportunities by agent (magnitude-weighted)
    L.append(section("Table 3 — missed-opportunity rate on HIGH-magnitude chances"))
    L.append("(opportunities with magnitude >= median for that motif; lower = better)")
    L.append("| agent | " + " | ".join(MOTIFS) + " |")
    L.append("|---|" + "|".join("---" for _ in MOTIFS) + "|")
    med = {}
    for m in MOTIFS:
        mags = sorted(r["labels"][m]["mag"] for r in recs if m in r["labels"])
        med[m] = mags[len(mags)//2] if mags else 0
    for ag in LADDER:
        cells = []
        for m in MOTIFS:
            rt = rate_table(recs, [ag], m, filt=lambda r, mm=m: r["labels"][mm]["mag"] >= med[mm])
            k, n, p, lo, hi = rt[ag]
            cells.append(f"{(1-p)*100:4.0f}% miss ({n})" if n else "  --  ")
        L.append(f"| {ag} | " + " | ".join(cells) + " |")

    # TABLE 4 — motif take rate by game phase
    L.append(section("Table 4 — take rate by game phase"))
    phases = ["opening", "midgame", "late_mid", "pre_endgame", "endgame"]
    for m in MOTIFS:
        L.append(f"\n**{m}**\n")
        L.append("| agent | " + " | ".join(phases) + " |")
        L.append("|---|" + "|".join("---" for _ in phases) + "|")
        for ag in ("h6400", "rod1", "greedy", "ACTUAL"):
            cells = []
            for ph in phases:
                rt = rate_table(recs, [ag], m, filt=lambda r, pp=ph: r["phase"] == pp)
                cells.append(fmt_rate(rt[ag]))
            L.append(f"| {ag} | " + " | ".join(cells) + " |")

    # TABLE 5 — outcome correlation in CLOSE games (ANTI-BENCHMAX outcome-sanity)
    L.append(section("Table 5 — outcome-sanity: does taking the motif predict winning? (close games)"))
    L.append(f"(positions in games with |final margin| <= {CLOSE_MARGIN}; mover's ACTUAL choice; "
             "win = mover result W. If take<=miss winrate, motif is DESCRIPTIVE not target-worthy.)")
    L.append("| motif | n_take | win%|take | n_miss | win%|miss | delta | verdict |")
    L.append("|---|---|---|---|---|---|---|")
    for m in MOTIFS:
        pool = [r for r in recs if m in r["labels"]
                and abs(r.get("final_margin_mover", 99)) <= CLOSE_MARGIN]
        tk = [r for r in pool if took(r, "ACTUAL", m)]
        ms = [r for r in pool if took(r, "ACTUAL", m) is False]
        wt = sum(1 for r in tk if r.get("result_mover") == "W")
        wm = sum(1 for r in ms if r.get("result_mover") == "W")
        pt = wt/len(tk) if tk else 0
        pm = wm/len(ms) if ms else 0
        d = pt - pm
        verdict = "predictive" if (len(tk) >= 20 and len(ms) >= 20 and d > 0.03) else \
                  ("counter/flat" if (len(tk) >= 20 and len(ms) >= 20) else "low-n")
        L.append(f"| {m} | {len(tk)} | {pt*100:.0f}% | {len(ms)} | {pm*100:.0f}% | "
                 f"{d*100:+.0f}pp | {verdict} |")

    # TABLE 6 — h6400 vs RoD1 motif deltas
    L.append(section("Table 6 — h6400 vs RoD1 take-rate deltas (same positions)"))
    L.append("| motif | h6400 | rod1 | delta (h6400-rod1) | n |")
    L.append("|---|---|---|---|---|")
    for m in MOTIFS:
        rt = rate_table(recs, ["h6400", "rod1"], m)
        h = rt["h6400"]; r = rt["rod1"]
        n = min(h[1], r[1])
        L.append(f"| {m} | {fmt_rate(h)} | {fmt_rate(r)} | {(h[2]-r[2])*100:+.0f}pp | {n} |")

    # LADDER monotonicity + strength<->behavior correlation
    L.append(section("Pseudo-human ladder — does behavior track strength?"))
    L.append("`corr` = Pearson(ladder position, take rate) over agents with n>=10. "
             "Positive+large => behavior rises with strength (credible diagnostic); "
             "~0 => motif doesn't separate these agents.")
    L.append("| motif | take rate along ladder (weak->strong %) | corr | monotone? |")
    L.append("|---|---|---|---|")

    def pearson(xs, ys):
        n = len(xs)
        if n < 3:
            return float("nan")
        mx = sum(xs) / n
        my = sum(ys) / n
        cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        vx = sum((x - mx) ** 2 for x in xs)
        vy = sum((y - my) ** 2 for y in ys)
        return cov / math.sqrt(vx * vy) if vx > 0 and vy > 0 else float("nan")

    for m in MOTIFS:
        seq = []
        for ag in LADDER:
            rt = rate_table(recs, [ag], m)[ag]
            seq.append(rt[2] if rt[1] >= 10 else None)
        shown = " ".join(f"{(v*100):.0f}" if v is not None else "·" for v in seq)
        idx = [i for i, v in enumerate(seq) if v is not None]
        vals = [seq[i] for i in idx]
        r = pearson(idx, vals)
        mono = "yes" if vals == sorted(vals) else ("rev" if vals == sorted(vals, reverse=True) else "no")
        L.append(f"| {m} | {shown} | {r:+.2f} | {mono} |")

    digest = os.path.join(args.out, "ANALYSIS_DIGEST.md")
    with open(digest, "w") as f:
        f.write("\n".join(L) + "\n")

    # ---- deliverable CSVs ---------------------------------------------------
    import csv
    pos_csv = os.path.join(args.out, "positions_labeled.csv")
    with open(pos_csv, "w", newline="") as f:
        w = csv.writer(f)
        head = ["idx", "regime", "mover_spec", "opp_spec", "opp_class", "phase",
                "k_remaining", "legal_n", "final_margin_mover", "result_mover", "motifs"]
        for m in MOTIFS:
            head += [f"{m}_opp", f"{m}_mag", f"{m}_actual_took"]
        w.writerow(head)
        for i, r in enumerate(recs):
            row = [r.get("idx", i), r["regime"], r["mover_spec"], r["opp_spec"],
                   opp_class(r["opp_spec"]), r["phase"], r["k_remaining"], r["legal_n"],
                   r.get("final_margin_mover"), r.get("result_mover"),
                   "|".join(m for m in MOTIFS if m in r["labels"])]
            for m in MOTIFS:
                if m in r["labels"]:
                    t = took(r, "ACTUAL", m)
                    row += [1, r["labels"][m]["mag"], int(t) if t is not None else ""]
                else:
                    row += [0, "", ""]
            w.writerow(row)

    met_csv = os.path.join(args.out, "metrics_takerate.csv")
    with open(met_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["agent", "motif", "slice", "k", "n", "rate", "lo", "hi"])
        slices = [("all", None)]
        for c in ("weak", "mid", "strong"):
            slices.append((f"opp_{c}", (lambda r, cc=c: opp_class(r["opp_spec"]) == cc)))
        for ph in ("opening", "midgame", "late_mid", "pre_endgame", "endgame"):
            slices.append((f"phase_{ph}", (lambda r, pp=ph: r["phase"] == pp)))
        for m in MOTIFS:
            for sl_name, sl in slices:
                rt = rate_table(recs, LADDER + ["ACTUAL"], m, filt=sl)
                for ag in LADDER + ["ACTUAL"]:
                    k, n, p, lo, hi = rt[ag]
                    if n:
                        w.writerow([ag, m, sl_name, k, n, f"{p:.4f}", f"{lo:.4f}", f"{hi:.4f}"])

    print("\n".join(L))
    print(f"\nwrote {digest}\nwrote {pos_csv}\nwrote {met_csv}")


if __name__ == "__main__":
    main()
