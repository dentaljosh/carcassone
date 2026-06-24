# Strategic-behavior ladder — diagnostic report

**Status: IN PROGRESS (generation + harvest running). Results sections marked [FILL].**
Branch `strategic-behavior-ladder`. Diagnostic only — **not** a promotion benchmark, **not**
a training target. Full-game held-out winrate vs `h6400_v2.8` remains the final strength arbiter.

## What this answers

Internal Elo/score-margin rulers are saturated/ambiguous (RoD_iter_01 compresses h3200_v2.8 but
loses to h6400_v2.8; exact-endgame handoff lifts margin not winrate; deeper search sharpens margin
not wins). This suite asks a different question: **do agents exhibit recognizable higher-level
strategic behaviors** — blocking, contesting/denial, farm control, conversion — and, if so, does
behavior track strength, and is any failure mode actionable without becoming a new Goodhart ruler.

## Part A — operational motifs (frozen)

Full computable definitions + thresholds: [`MOTIF_DEFINITIONS.md`](MOTIF_DEFINITIONS.md).
Detector: [`scripts/strategic_ladder/motifs.py`](../../scripts/strategic_ladder/motifs.py). Four motifs,
fidelity-tiered honestly:

| motif | phase | tier | one-line |
|---|---|---|---|
| `farm_claim` | MEEPLES | **structural / credible** | take an unowned field worth ≥2 cities |
| `contest_merge` | TILES | **structural / credible** | place a tile that favorably merges into a contested ≥2-city field |
| `block` | TILES | equity-proxy / low-fidelity | choose the placement denying the opponent the most pending completion |
| `avoid_feeding` | TILES | equity-proxy / low-fidelity | don't hand the opponent pending completions |

**Rules insight that reshaped the set (a real finding).** In 2-player BASE Carcassonne you cannot
place a meeple on an occupied feature, so you cannot "steal" or "deny" a field by placing on the
opponent's field — it is illegal. The **only** legal contest/denial mechanism is a **TILES-phase
merge** of two pre-placed farmers. The spec's "steal/contest" (#2) and "farm denial" (#4) therefore
collapse into `contest_merge`; a naive meeple-phase steal detector fired **0 times across 22 games**,
correctly. Meeple liquidity/lock is reported descriptively; pre-endgame conversion is a separate
exact-K slice ([`EXACT_SLICE.md`](EXACT_SLICE.md)).

Detectors are **structural** (feature decomposition: ownership majority, completion distance,
farm→city adjacency), not gated on the v2.7 leaf score — otherwise "took the motif" would collapse
to "agreed with v2.7", which heuristic agents win by construction. The v2.7 closure schedule
`{1:0.5, 2:0.2}` is used only as a labeled `P(close)` model. **Residual circularity is acknowledged**:
structural motifs still correlate with what v2.7 values, so heuristic agents are *expected* to score
high — the diagnostic question is whether the NEURAL agent (RoD1) matches them, and whether strong
agents punish weak-CREATED chances more than strong-created ones.

## Part B — dataset

- **Agents (ladder, weak→strong):** random · greedy(RuleBased) · h200_v2.7 · h200_v2.8 · h800_v2.8 ·
  h3200_v2.8 · h6400_v2.8 · RoD_iter_01+v2.8 · iter_08+v2.8. (v2.8 = v2.7 + flat meeple_k=2.0;
  production agent construction reused verbatim — residual_scale 0.25, c_puct 3.0, sims 200 for neural.)
- **Position bank:** 12 regimes (greedy/rod1/h800 self-play; rod1/h6400/h3200/h200 vs random;
  rod1-vs-h6400, h3200-vs-h6400; random-vs-random) as one flat work-stealing game pool. Every decision
  is labeled; positions with ≥1 motif opportunity are snapshotted (pickled board), seat-balanced,
  tagged `mover_spec`/`opp_spec`/regime, and **outcome-backfilled** with the game's eventual
  mover-perspective final margin (true farm scoring) for outcome-sanity.
- **Counterfactual harvest:** every panel agent's chosen action on every labeled position — agent-
  *unbiased* (all agents face identical positions, so take-rate gaps are pure agent differences).
- **dev/test split (Part F.1):** detector thresholds tuned on a greedy DEV band (seeds 1930xxx) and
  **frozen**; the entire audit suite (seeds 1940xxx+) is the **held-out test set**.
- **Provenance:** agent configs + checkpoint hashes (RoD1 `a8b824df0786284c`, iter08 `5843b3cf0d172f73`),
  regime, seed, seat, ply, k_remaining, labels, satisfying sets, magnitudes, eventual outcome — all stored.

## Part C — benchmark metrics  [FILL]
See [`ANALYSIS_DIGEST.md`](ANALYSIS_DIGEST.md) (Tables 1–6 + ladder) and CSVs
[`metrics_takerate.csv`](metrics_takerate.csv), [`positions_labeled.csv`](positions_labeled.csv).
Summary + interpretation here.

## Part D — pseudo-human ladder  [FILL]
- Does behavior improve monotonically with agent strength? (per-motif corr) — [FILL]
- Does h6400 show more strategic behavior than h3200? — [FILL]
- Does RoD1 look h3200-like, h6400-like, or weird/RPS-like? — [FILL]
- Does RoD1 punish weak opponents (take rate vs weak)? — [FILL]
- Does RoD1 fail to punish weak mistakes even when obvious? — [FILL]
- Motifs where ALL internal agents fail (missing human dimension)? — [FILL]

## Part E — representative examples  [FILL]
See [`EXAMPLES.md`](EXAMPLES.md).

## Part F — anti-benchmax safeguards (implemented)

1. **dev/test split** — thresholds frozen on a dev band before the held-out audit (above).
2. **No training on labels** — this branch produces no training data from the benchmark; detectors
   never touch a gradient.
3. **Outcome sanity** — for each motif, Table 5 tests whether taking it predicts winning in *close*
   games (|final margin| ≤ 5). A motif whose take-rate doesn't beat its miss-rate winrate is marked
   **descriptive only, not target-worthy**. [FILL verdict]
4. **Cross-opponent generalization** — take rates split by opponent strength (Table 2); a behavior
   appearing only vs one opponent class is flagged as possible exploit/RPS, not general skill. [FILL]
5. **Cross-deck generalization** — take rates compared across regimes/seed groups for stability. [FILL]
6. **Human-readability** — structured examples (Part E) output for human review, not blind trust.
7. **Champion quarantine** — behavior score alone cannot promote any agent; any future trained agent
   must still beat `h6400_v2.8` on full-game held-out winrate (PRODUCTION.yaml untouched, v2.7 frozen,
   v2.8 opt-in).

## Part G — verdict (brutally honest)  [FILL]
1. Does RoD1 exhibit higher-level strategic behavior, or mostly search/eval compression? — [FILL]
2. Which motifs does h6400 show more than RoD1? — [FILL]
3. Does RoD1 punish weak opponents appropriately? — [FILL]
4. Are failures broad or motif-specific? — [FILL]
5. Are the motif definitions credible, or too noisy/subjective? — [FILL]
6. Which motifs are plausible future tools/training targets? — [FILL]
7. Which motifs to KILL as non-predictive / benchmax bait? — [FILL]
8. Next branch: targeted tool construction / h6400-motif distillation / v2.9 heuristic concept patch /
   exact-lookahead conversion setup / human expert labeling / STOP? — [FILL]

## 10-line executive summary  [FILL]
