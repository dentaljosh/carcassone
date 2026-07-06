"""4.3 — Luck-floor estimate from existing seat-swap paired-deck eval archives.

Pure LIGHT analysis (no games played, no solver run): reads the on-disk paired
archives (`seedNNN_a0.json` = agent-A in seat 0, `..._a1.json` = A in seat 1,
same deck -> identical deck_hash) and decomposes the margin variance into a
COMMON-DECK (luck) component and a PLAY/AGENT (skill) component. From that it
sizes the human-anchor program: the implied ceiling win-rate vs an expert and
the number of games needed to power a superhuman claim.

METHOD
------
Each archive is one agent pair, N decks x 2 seatings. Per game we read the
seat-0-minus-seat-1 score margin S = score_p0 - score_p1 and agent-A's margin
diff (A-perspective). For each deck d we get (S_a0, S_a1) [seat-0 margin with A,
then B, in seat 0] and (diff_a0, diff_a1) [A's margin in each seating].

  * luck_share = corr(S_a0, S_a1) across decks  (ICC of the seat-margin): how
    much of the seat-margin is fixed by the DECK regardless of who sits where.
    high -> the deck dominates the outcome (a high luck floor).
  * sigma_game  = SD(diff over all games)             — per-game margin SD (points)
  * sigma_pair  = SD( (diff_a0+diff_a1)/2 over decks) — SD of A's seat-swap-
    AVERAGED margin (first-player + seat-luck differenced out). The paired test
    statistic; smaller sigma_pair => fewer games needed.
  * seat_adv    = (mean diff_a0 - mean diff_a1)/2     — first-player pt advantage

SIZING. To win vs an expert at rate p the agent needs a mean edge e = sigma_game
* Phi^-1(p) points. Naive per-game win-rate test needs n = p(1-p) z^2/(p-0.5)^2
games for a 95% CI lower bound > 0.5. The seat-swap PAIRED-margin test needs
D deck-pairs with 1.96*sigma_pair/sqrt(D) < e, i.e. it removes the deck/seat luck
from the test and cuts the games required.

Writes measurement/human_anchor/LUCK_FLOOR.md and prints the same to stdout.
"""
from __future__ import annotations

import glob
import json
import math
import os
import statistics as st
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHARE = Path("/mnt/c/carc-shared")
OUT_MD = REPO / "measurement/human_anchor/LUCK_FLOOR.md"

# Curated archives. NEAR-EQUAL pairs drive the luck-share + sigma estimate (a
# strong-vs-weak pair inflates the within-pair variance and understates luck).
# STRONG-vs-EXPERT pairs anchor the ceiling win-rate.
NEAR_EQUAL = [
    SHARE / "deeper_search_ruler/heur6400__vs__heur3200__n400_v28",
    SHARE / "deeper_search_ruler/heur12800__vs__heur6400__n100_v28",
]
# plus any v29 self-play arm with a decent n (auto-added below)
V29_GLOB = str(SHARE / "v29_eval/*_s200")
STRONG_VS_EXPERT = [
    SHARE / "exact_endgame_hybrid/exact_2_clair__vs__heur3200__n400_v28",
    SHARE / "exact_endgame_hybrid/exact_3_clair__vs__heur3200__n400_v28",
    SHARE / "exact_endgame_hybrid/exact_4_clair__vs__heur3200__n100_v28",
    SHARE / "deeper_search_ruler/rod1__vs__heur6400__n200_v28",
]


# --------------------------------------------------------------------------- #
# normal cdf / ppf  (no scipy dependency)
# --------------------------------------------------------------------------- #
def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """Acklam's inverse-normal approximation (abs err < 1.2e-9)."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


# --------------------------------------------------------------------------- #
# archive loading + per-archive stats
# --------------------------------------------------------------------------- #
def load_pairs(archive_dir: Path):
    """Return {seed: {seat_layout: record}} for a paired archive, both seats present."""
    by: dict[int, dict] = {}
    for jf in glob.glob(str(archive_dir / "*seed*_a?.json")):
        if jf.endswith(".partial.json"):
            continue
        try:
            r = json.load(open(jf))
        except Exception:
            continue
        seed = r.get("seed")
        a_seat = r.get("a_seat", r.get("a_player"))
        if seed is None or a_seat is None or "score_p0" not in r:
            continue
        by.setdefault(seed, {})[int(a_seat)] = r
    return {s: v for s, v in by.items() if 0 in v and 1 in v}


def archive_stats(archive_dir: Path):
    pairs = load_pairs(archive_dir)
    if len(pairs) < 10:
        return None
    S_a0, S_a1 = [], []          # seat0-margin, A-in-seat0 vs B-in-seat0
    diff_a0, diff_a1 = [], []    # A-perspective margin per seating
    won_a0, won_a1 = [], []
    all_diff = []
    for seed, rec in pairs.items():
        g0, g1 = rec[0], rec[1]  # a_seat==0 record, a_seat==1 record
        s0 = g0["score_p0"] - g0["score_p1"]   # A in seat0 -> = A's margin
        s1 = g1["score_p0"] - g1["score_p1"]   # A in seat1 -> = -A's margin
        S_a0.append(s0)
        S_a1.append(s1)
        diff_a0.append(g0.get("diff", s0))
        diff_a1.append(g1.get("diff", -s1))
        won_a0.append(0.5 if g0.get("drew") else (1.0 if g0.get("won_by_a") else 0.0))
        won_a1.append(0.5 if g1.get("drew") else (1.0 if g1.get("won_by_a") else 0.0))
    all_diff = diff_a0 + diff_a1

    # luck share = correlation of the seat-0 margin across the two agent-in-seat0
    # conditions (ICC of the deck on the seat margin).
    luck_share = _pearson(S_a0, S_a1)
    sigma_game = st.pstdev(all_diff)
    pair_mean = [(diff_a0[i] + diff_a1[i]) / 2 for i in range(len(diff_a0))]
    sigma_pair = st.pstdev(pair_mean)
    seat_adv = (st.mean(diff_a0) - st.mean(diff_a1)) / 2
    wr_A = st.mean(won_a0 + won_a1)
    return {
        "archive": archive_dir.name,
        "n_pairs": len(pairs), "n_games": 2 * len(pairs),
        "wr_A": wr_A, "sigma_game": sigma_game, "sigma_pair": sigma_pair,
        "luck_share": luck_share, "seat_adv": seat_adv,
        "mean_A_margin": st.mean(all_diff),
    }


def _pearson(x, y):
    n = len(x)
    mx, my = st.mean(x), st.mean(y)
    sx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
    sy = math.sqrt(sum((yi - my) ** 2 for yi in y))
    if sx == 0 or sy == 0:
        return float("nan")
    return sum((x[i] - mx) * (y[i] - my) for i in range(n)) / (sx * sy)


# --------------------------------------------------------------------------- #
# sizing
# --------------------------------------------------------------------------- #
def required_n(target_wr: float, sigma_game: float, sigma_pair: float, z=1.96):
    """Games needed for a 95% (two-sided) CI lower bound > 0.5 at true win-rate.
    Returns (n_unpaired_games, n_paired_games, edge_points)."""
    e = sigma_game * norm_ppf(target_wr)             # point edge implied by target_wr
    p = target_wr
    n_unpaired = p * (1 - p) * z ** 2 / (p - 0.5) ** 2
    # paired-margin test: D deck-pairs, SE = sigma_pair/sqrt(D); want z*SE < e.
    D = (z * sigma_pair / e) ** 2
    n_paired_games = 2 * D
    return math.ceil(n_unpaired), math.ceil(n_paired_games), e


# --------------------------------------------------------------------------- #
def main() -> int:
    near = [s for d in NEAR_EQUAL if (s := _safe(archive_stats, d))]
    for d in sorted(glob.glob(V29_GLOB)):
        s = _safe(archive_stats, Path(d))
        # keep self-play / near-equal arms (small mean margin) with enough n
        if s and s["n_pairs"] >= 100 and abs(s["mean_A_margin"]) <= 12:
            near.append(s)
    strong = [s for d in STRONG_VS_EXPERT if (s := _safe(archive_stats, d))]

    if not near:
        print("ERROR: no near-equal paired archives found under", SHARE)
        return 1

    # aggregate luck share + sigma from the near-equal pairs (n-weighted)
    def wmean(rows, key):
        w = sum(r["n_pairs"] for r in rows)
        return sum(r[key] * r["n_pairs"] for r in rows) / w
    luck = wmean(near, "luck_share")
    sg = wmean(near, "sigma_game")
    sp = wmean(near, "sigma_pair")
    pair_reduction = (2 * sp ** 2) / (sg ** 2)   # <1 => seat-swap pairing helps

    # ceiling: the strongest agent that BEATS the expert proxy (largest POSITIVE
    # edge; a negative-edge pair means that agent is weaker than the proxy and is
    # not a ceiling anchor).
    positive = [r for r in strong if r["mean_A_margin"] > 0]
    ceil_rows = sorted(positive or strong, key=lambda r: -r["mean_A_margin"])
    ceiling_emp = ceil_rows[0] if ceil_rows else None

    lines = []
    P = lines.append
    P("# Luck-floor estimate — human-anchor program sizing")
    P("")
    P(f"_Generated by `scripts/human_anchor/luck_floor.py` on the on-disk paired "
      f"eval archives. Pure analysis (no games/solver run)._")
    P("")
    P("## Headline")
    P("")
    P(f"- **Deck-luck share of margin variance: ~{luck:.2f}** "
      f"(seat-margin ICC across near-equal agent pairs, n-weighted over "
      f"{sum(r['n_pairs'] for r in near)} deck-pairs).")
    P(f"- **Per-game margin SD: sigma_game ~ {sg:.1f} points** "
      f"(seat-swap paired-avg SD sigma_pair ~ {sp:.1f} points).")
    P(f"- **Seat-swap deck-pairing variance-reduction factor: ~{pair_reduction:.2f}** "
      f"of the naive per-game variance (removes first-player + seat luck).")
    if ceiling_emp:
        P(f"- **Empirical strong-vs-expert edge:** `{ceiling_emp['archive']}` "
          f"-> win-rate {ceiling_emp['wr_A']:.3f}, mean margin "
          f"{ceiling_emp['mean_A_margin']:+.1f} pts.")
    P("")

    P("## Required games to power a superhuman claim")
    P("")
    P("A superhuman claim needs the agent's win-rate vs a strong human to have a "
      "95% CI lower bound > 0.5. Games needed at plausible TRUE win-rates:")
    P("")
    P("| true wr | implied edge (pts) | n (naive per-game) | n (seat-swap paired) |")
    P("|--------:|-------------------:|-------------------:|---------------------:|")
    for p in (0.52, 0.55, 0.60):
        nu, npd, e = required_n(p, sg, sp)
        P(f"| {p:.2f} | {e:+.1f} | {nu} | {npd} |")
    P("")
    P("_'implied edge' = mean point margin an agent needs to win at that rate given "
      "sigma_game; naive n from the binomial CI; paired n from the seat-swap "
      "paired-margin test (SE = sigma_pair/sqrt(D), 2 games/deck-pair)._")
    P("")

    P("## Implied ceiling win-rate vs an expert")
    P("")
    P("Deck luck caps the win-rate even under perfect play: with an irreducible "
      f"per-game margin SD of ~{sg:.1f} pts, a true point-edge of `e` yields "
      "win-rate `Phi(e/sigma_game)`:")
    P("")
    P("| true edge (pts) | ceiling win-rate |")
    P("|----------------:|-----------------:|")
    for e in (3, 5, 8, 10, 15, 20):
        P(f"| {e:+d} | {norm_cdf(e / sg):.3f} |")
    P("")
    if ceiling_emp:
        P(f"The strongest agent on disk (`{ceiling_emp['archive']}`) beats the "
          f"strong-search expert proxy at **{ceiling_emp['wr_A']:.3f}** "
          f"(margin {ceiling_emp['mean_A_margin']:+.1f} pts). Humans are likely "
          f"weaker than that search proxy, so the true edge — and ceiling win-rate "
          f"— vs a human expert is *at least* this, but the deck floor keeps it "
          f"well below 1.0 (see table).")
    P("")

    P("## Per-archive detail")
    P("")
    P("### Near-equal pairs (drive the luck share + sigma)")
    P("")
    P("| archive | n_pairs | wr_A | mean margin | sigma_game | sigma_pair | luck_share | seat_adv |")
    P("|---|--:|--:|--:|--:|--:|--:|--:|")
    for r in near:
        P(f"| {r['archive']} | {r['n_pairs']} | {r['wr_A']:.3f} | "
          f"{r['mean_A_margin']:+.1f} | {r['sigma_game']:.1f} | {r['sigma_pair']:.1f} | "
          f"{r['luck_share']:.2f} | {r['seat_adv']:+.1f} |")
    P("")
    P("### Strong-vs-expert pairs (anchor the ceiling)")
    P("")
    P("| archive | n_pairs | wr_A | mean margin | sigma_game | luck_share |")
    P("|---|--:|--:|--:|--:|--:|")
    for r in strong:
        P(f"| {r['archive']} | {r['n_pairs']} | {r['wr_A']:.3f} | "
          f"{r['mean_A_margin']:+.1f} | {r['sigma_game']:.1f} | {r['luck_share']:.2f} |")
    P("")

    P("## Method + caveats")
    P("")
    P("- **Variance decomposition:** each archive is one agent pair played on N "
      "decks x 2 seatings (same shuffled deck, seats swapped; identical "
      "`deck_hash`). `luck_share` = Pearson corr of the seat-0-minus-seat-1 score "
      "margin between the two seatings (the ICC of the deck on the seat margin); "
      "the residual `1 - luck_share` is play divergence + agent skill + who's in "
      "seat 0. `sigma_game` = SD of the agent's per-game point margin; "
      "`sigma_pair` = SD of the agent's seat-swap-averaged per-deck margin (deck "
      "seat-luck differenced out).")
    P("- **Why near-equal pairs for the headline:** a strong-vs-weak pair inflates "
      "the within-pair (skill) variance and *understates* the luck share, so the "
      "deck-luck fraction is read off near-equal pairs (heur ladder rungs + v29 "
      "self-play arms).")
    P("- **Proxy caveat:** these are agent-vs-agent games, not agent-vs-human, so "
      "the luck share is a proxy — a human's higher move variance would ADD to the "
      "non-deck (play) variance, *lowering* the luck share and *raising* the games "
      "needed. Treat the naive-n column as an optimistic floor.")
    P("- **Recommendation:** run the human protocol as **seat-swap deck-pairs** "
      "(each deck played twice, seats swapped, scoring the agent's averaged "
      "margin) — it removes the first-player + seat luck and cuts the games needed "
      f"by ~{(1-pair_reduction)*100:.0f}% vs a naive per-game win count.")
    P("")
    P("### Archives used")
    P("")
    for r in near + strong:
        P(f"- `{SHARE}/.../{r['archive']}`  (n_pairs={r['n_pairs']})")
    P("")
    P("### Perfect-play edge bound (pending)")
    P("")
    P("A tighter ceiling needs the solver-vs-h6400 full-game win-rate on solved "
      "roots (Phase-3 K<=4 `child_values` cache). The on-disk K=2 cache "
      "(`measurement/pre_tool_audit/k2_childvalues.jsonl`, 150 roots) gives exact "
      "endgame values but not a full-game perfect-play win-rate; the "
      "`exact_*_clair__vs__heur3200` hybrids above are the closest available "
      "empirical proxy. Generating the solver-vs-expert full games is a boxes job.")

    md = "\n".join(lines) + "\n"
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md)
    print(md)
    print(f"\n[wrote {OUT_MD}]")
    return 0


def _safe(fn, arg):
    try:
        return fn(arg)
    except Exception as e:  # missing archive dir etc.
        print(f"  [skip {getattr(arg,'name',arg)}: {e}]")
        return None


if __name__ == "__main__":
    raise SystemExit(main())
