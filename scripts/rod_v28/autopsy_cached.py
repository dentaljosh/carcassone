#!/usr/bin/env python3
"""
RoD v2.8 iter_08 autopsy — Part A/D/E from CACHED per-game match records ONLY.

Reads the per-game result JSONs already on disk (no replay, no new compute) for
the match triangle and emits slice tables + CSVs into measurement/.../autopsy/.

Per-game schema (auto-detected, two variants):
  net_vs_net : {seed, a_player, sims, c_puct, score_p0, score_p1, diff, won_by_a, drew, moves}
  handoff    : {seed, a_seat, agent_a, agent_b, score_p0, score_p1, diff, won_by_a, drew,
                moves, deck_hash, a_neural_moves, a_heur_moves, b_neural_moves, b_heur_moves, ...}

INVARIANT verified at load: `diff` == A_score - B_score (A-relative), consistent across seats.
"""
import json, glob, math, os, statistics as st
from collections import defaultdict

OUT = "measurement/rod_v28_overnight_flywheel/autopsy"
os.makedirs(OUT, exist_ok=True)

# (label, dir, A_name, B_name)
SETS = [
    ("iter08_vs_RoD1",      "/mnt/c/carc-shared/rod_v28_overnight_flywheel/evals/iter08_vs_iter01_n400", "iter08", "RoD1"),
    ("iter10_vs_RoD1",      "/mnt/c/carc-shared/rod_v28_overnight_flywheel/evals/iter10_vs_iter01_n400", "iter10", "RoD1"),
    ("iter08_vs_heur3200",  "/mnt/c/carc-shared/rod_v28_overnight_flywheel/evals/iter08_vs_heur3200_v28", "iter08", "heur3200"),
    ("RoD1_vs_heur3200",    "/mnt/c/carc-shared/v28_rod_probe/rod_iter01_vs_heur3200_v28", "RoD1", "heur3200"),
    ("RoD1_vs_iter8parent", "/mnt/c/carc-shared/v28_rod_probe/nvn_iter_01_mk20_vs_iter8_mk20_s200_rs025", "RoD1", "iter8parent"),
]

def load(d):
    games = []
    for fp in glob.glob(os.path.join(d, "*.json")):
        base = os.path.basename(fp)
        if base in ("result.json", "manifest.json"):
            continue
        try:
            g = json.load(open(fp))
        except Exception:
            continue
        if "diff" not in g or "score_p0" not in g:
            continue
        seat = g.get("a_player", g.get("a_seat"))
        g["_seat"] = seat
        g["_a_score"] = g["score_p0"] if seat == 0 else g["score_p1"]
        g["_b_score"] = g["score_p1"] if seat == 0 else g["score_p0"]
        g["_amargin"] = g["_a_score"] - g["_b_score"]          # A-relative margin
        # invariant check
        if g["_amargin"] != g["diff"]:
            g["_diff_mismatch"] = True
        g["_seed"] = g["seed"]
        games.append(g)
    return games

def winrate_elo(W, L, D):
    n = W + L + D
    if n == 0: return float("nan"), float("nan")
    wr = (W + 0.5 * D) / n
    if wr <= 0 or wr >= 1: return wr, float("inf") if wr >= 1 else float("-inf")
    return wr, -400.0 * math.log10(1.0 / wr - 1.0)

def wdl(games):
    W = sum(1 for g in games if g["won_by_a"] and not g["drew"])
    D = sum(1 for g in games if g["drew"])
    L = sum(1 for g in games if not g["won_by_a"] and not g["drew"])
    return W, D, L

def paired_stats(games):
    """Deck-paired margin (cancels deck luck): group by seed, mean A-margin per deck."""
    byseed = defaultdict(list)
    for g in games:
        byseed[g["_seed"]].append(g["_amargin"])
    deck_marg = [sum(v) / len(v) for v in byseed.values()]
    n = len(deck_marg)
    mean = sum(deck_marg) / n if n else float("nan")
    if n > 1:
        se = st.pstdev(deck_marg) * math.sqrt(n / (n - 1)) / math.sqrt(n)  # ddof=1 / sqrt(n)
        z = mean / se if se else float("nan")
    else:
        se = z = float("nan")
    # fraction of decks A wins the pair (margin>0), ties, losses
    win = sum(1 for m in deck_marg if m > 0)
    tie = sum(1 for m in deck_marg if m == 0)
    los = sum(1 for m in deck_marg if m < 0)
    return dict(n_decks=n, paired_mean=mean, paired_se=se, paired_z=z,
                deck_win=win, deck_tie=tie, deck_los=los, deck_marg=deck_marg)

def digest(label, games):
    W, D, L = wdl(games)
    wr, elo = winrate_elo(W, L, D)
    ps = paired_stats(games)
    mism = sum(1 for g in games if g.get("_diff_mismatch"))
    lines = []
    lines.append(f"### {label}  (n={len(games)} games, {ps['n_decks']} decks)")
    if mism: lines.append(f"  !! DIFF-MISMATCH in {mism} games (A-margin != diff) — investigate")
    lines.append(f"  W/D/L = {W}/{D}/{L}   winrate={wr:.4f}   winrate_elo={elo:+.1f}")
    lines.append(f"  paired_margin = {ps['paired_mean']:+.3f}  (se {ps['paired_se']:.3f}, paired_z {ps['paired_z']:+.2f})")
    lines.append(f"  deck pair W/T/L = {ps['deck_win']}/{ps['deck_tie']}/{ps['deck_los']}  "
                 f"({100*ps['deck_win']/ps['n_decks']:.1f}% of decks A wins the pair)")
    # seat split
    for seat in (0, 1):
        sg = [g for g in games if g["_seat"] == seat]
        if sg:
            w, d, l = wdl(sg); _, e = winrate_elo(w, l, d)
            am = sum(g["_amargin"] for g in sg) / len(sg)
            lines.append(f"  seat A={seat}: W/D/L {w}/{d}/{l}  elo {e:+.1f}  avg A-margin {am:+.2f}")
    # margin-shape: among A-wins vs B-wins, distribution of |margin|
    awins = [g["_amargin"] for g in games if g["_amargin"] > 0]
    bwins = [-g["_amargin"] for g in games if g["_amargin"] < 0]
    def shape(xs, tag):
        if not xs:
            lines.append(f"  {tag}: none"); return
        xs = sorted(xs)
        lines.append(f"  {tag}: n={len(xs)} mean={sum(xs)/len(xs):.2f} "
                     f"median={xs[len(xs)//2]} p90={xs[int(0.9*len(xs))-1]} max={xs[-1]}  "
                     f"close(<=5)={sum(1 for x in xs if x<=5)} blowout(>=20)={sum(1 for x in xs if x>=20)}")
    shape(awins, "A-win margins")
    shape(bwins, "B-win margins")
    # margin buckets (outcome distribution, descriptive)
    buckets = [("A blowout>=20", lambda m: m >= 20), ("A 6..19", lambda m: 6 <= m <= 19),
               ("A 1..5", lambda m: 1 <= m <= 5), ("draw 0", lambda m: m == 0),
               ("B 1..5", lambda m: -5 <= m <= -1), ("B 6..19", lambda m: -19 <= m <= -6),
               ("B blowout<=-20", lambda m: m <= -20)]
    lines.append("  margin buckets (A-relative): " +
                 "  ".join(f"[{name}]={sum(1 for g in games if pred(g['_amargin']))}" for name, pred in buckets))
    return "\n".join(lines), ps

def concentration_csv(label, ps):
    """Per-deck paired margin sorted — to read whether the edge is broad or narrow."""
    fp = os.path.join(OUT, f"deck_margins_{label}.csv")
    with open(fp, "w") as f:
        f.write("rank,deck_paired_margin\n")
        for i, m in enumerate(sorted(ps["deck_marg"], reverse=True)):
            f.write(f"{i},{m:.3f}\n")
    return fp

def main():
    all_digest = ["# RoD v2.8 iter_08 autopsy — CACHED match-record analysis (Parts A/D/E core)\n"]
    summary_rows = []
    for label, d, A, B in SETS:
        if not os.path.isdir(d):
            all_digest.append(f"### {label}  — DIR MISSING: {d}\n"); continue
        games = load(d)
        if not games:
            all_digest.append(f"### {label}  — NO GAMES PARSED from {d}\n"); continue
        txt, ps = digest(f"{label}  [A={A} vs B={B}]", games)
        all_digest.append(txt + "\n")
        cfp = concentration_csv(label, ps)
        all_digest.append(f"  deck-margin CSV: {cfp}\n")
        W, D, L = wdl(games); wr, elo = winrate_elo(W, L, D)
        summary_rows.append((label, A, B, len(games), ps["n_decks"], W, D, L,
                             round(wr, 4), round(elo, 1), round(ps["paired_mean"], 3),
                             round(ps["paired_z"], 2)))
    # summary CSV
    sfp = os.path.join(OUT, "triangle_summary.csv")
    with open(sfp, "w") as f:
        f.write("set,A,B,n,n_decks,W,D,L,winrate,winrate_elo,paired_margin,paired_z\n")
        for r in summary_rows:
            f.write(",".join(str(x) for x in r) + "\n")
    all_digest.append(f"\n## Triangle summary CSV: {sfp}\n")
    all_digest.append("set | A | B | n | W/D/L | wr_elo | paired_margin | paired_z")
    all_digest.append("--- | --- | --- | --- | --- | --- | --- | ---")
    for r in summary_rows:
        all_digest.append(f"{r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[5]}/{r[6]}/{r[7]} | "
                          f"{r[9]:+} | {r[10]:+} | {r[11]:+}")
    digest_fp = os.path.join(OUT, "PART_ADE_digest.md")
    open(digest_fp, "w").write("\n".join(all_digest))
    print("\n".join(all_digest))
    print(f"\n[written] {digest_fp}")

if __name__ == "__main__":
    main()
