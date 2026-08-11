# Strategic-behavior ladder — diagnostic report

**Status: COMPLETE ✅ (2026-06-24).** Exact-K conversion slice: see [`EXACT_SLICE.md`](EXACT_SLICE.md).
> **⚠️ Verdict TIGHTENED by a follow-up validation audit ([`VALIDATION_FARMCLAIM.md`](VALIDATION_FARMCLAIM.md)).**
> The one candidate lever (`farm_claim`) was confound-tested: the headline +17pp was inflated by close-game
> (collider) conditioning — the honest effect is +11pp, falling to **+5pp** after controlling for pre-move
> lead and removing weak opponents; it is **agent-dependent (RoD1's own farm claims are outcome-neutral, −2pp)**;
> and RoD1's deficit lives in **low-leverage** regimes (vs weak / already-won / late). **Revised recommendation:
> STOP — do not run the farm probe (expected winrate move vs h6400 ≈ 0).** Section §G/§exec below updated.
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
Full tables: [`ANALYSIS_DIGEST.md`](ANALYSIS_DIGEST.md); CSVs [`metrics_takerate.csv`](metrics_takerate.csv),
[`positions_labeled.csv`](positions_labeled.csv). **1,918 positions**, 12 regimes, 9-agent panel
counterfactually harvested (every agent on every position). Opportunity inventory:
`avoid_feeding` 780, `farm_claim` 777, `contest_merge` 391, `block` 203.

**Take rate by agent (Table 1), the load-bearing numbers:**

| motif | random | greedy | h800 | h3200 | h6400 | **rod1** | iter08 | outcome-sanity (close games) |
|---|---|---|---|---|---|---|---|---|
| `block` | 29 | 28 | 25 | 25 | 26 | 29 | 31 | −10pp (n=8, low) |
| `avoid_feeding` | 49 | 50 | 50 | 49 | 49 | 51 | 51 | +2pp (flat) |
| `contest_merge` | **18** | 47 | 47 | 48 | 49 | 45 | 43 | −11pp (n=18, low) |
| `farm_claim` | 24 | **12** | 60 | 60 | 60 | **54** | 54 | **+17pp (50%→33%)** |

Three of the four motifs are **non-diagnostic**:
- **`block`, `avoid_feeding` are NOISE.** Absolute spread is ~2–6pp and **random ≈ h6400** (random
  even *beats* h6400 on block-miss, Table 3). Outcome-sanity flat/negative. The +0.30/+0.59 ladder
  correlations are artifacts of a near-flat line. These are the equity-proxies flagged low-fidelity up
  front — confirmed dead. **Kill.**
- **`contest_merge` is a coarse "does the agent search at all" detector** — a *step* (random 18% →
  every search agent ~43–49%), not a strength gradient; it doesn't separate greedy from h6400 from
  rod1, and taking it does **not** predict winning (−11pp). Descriptive, not target-worthy.
- **`farm_claim` is the one credible, outcome-relevant motif.** It discriminates (greedy 12% by its
  no-early-farmers rule → heuristics 60% → rod1 54%) **and** taking it predicts a **+17pp** win-rate
  swing in close games (50% vs 33%). Caveat: the outcome contrast uses the actual mover, so it is
  **confounded by agent strength** (strong agents both claim more and win more) — suggestive of
  outcome-relevance, not a clean causal estimate. The rod1-vs-h6400 *gap*, however, is measured on
  **identical positions** and is clean.

## Part D — pseudo-human ladder

- **Monotonic with strength?** No clean gradient for any motif. The only meaningful *steps* are
  random→search (`contest_merge`) and greedy/random→heuristic (`farm_claim`). Behavior is better
  described as a **floor effect** (you need lookahead to clear it) than a ladder.
- **h6400 > h3200?** No — h3200, h800, h6400 are within 1pp on every motif (`farm_claim` all 60%).
  Deeper heuristic search does **not** buy more strategic behavior on these motifs — consistent with
  the deeper-search-ruler finding (depth sharpens margin, not strategic decisions).
- **RoD1: h3200-like, h6400-like, or RPS-weird?** **Heuristic-like, slightly below.** On the credible
  motifs rod1 tracks the h-agents (`farm_claim` 54 vs 60; `contest_merge` 45 vs 49), far above random
  (24/18) — it is NOT random/RPS-like and NOT a distinct super-heuristic. It compresses h-level
  behavior with one deficit (below).
- **Does RoD1 punish weak opponents?** **No — this is its clearest failure.** On `farm_claim` vs a
  *weak* (random) opponent, h6400 grabs **57%** of high-value fields, rod1 only **41% (−16pp)**; vs
  *strong* opponents they are **equal (53/53)**. rod1 leaves on the table exactly the high-value fields
  a weak opponent fails to defend — and those claims are outcome-relevant (+17pp).
- **Fails to punish obvious weak mistakes?** Yes (the −16pp vs-weak gap above), and the deficit also
  **grows late**: `farm_claim` rod1 vs h6400 by phase is 61/63 (opening) → 33/54 (late_mid) →
  **24/53 (pre_endgame)**. rod1 claims speculative opening fields fine but misses *grounded* late
  fields h6400 takes.
- **Motifs where ALL internal agents fail?** `block`/`avoid_feeding` — but that's a detector failure
  (the motifs are non-diagnostic), not a shared human-strategic blind spot. No evidence of a strategic
  dimension every agent lacks; the agents differ mainly in *farm-claim execution*, not in possessing
  vs lacking a motif.

## Part E — representative examples
See [`EXAMPLES.md`](EXAMPLES.md). The `farm_claim` set is the signal: on multi-city fields
(magnitude 9–12, touching 3–4 cities) **h800/h3200/h6400 all claim and rod1 misses** on identical
positions (e.g. `h200:random` seed 1963002 ply 89, a 4-city field: h800/h3200/h6400=take,
rod1=miss; `greedy:random` seed 1944004/1944006). `block`/`avoid_feeding` examples show no
agent separation (everyone misses together) — visual confirmation they are noise.

### Exact-K conversion slice (motif #8, [`EXACT_SLICE.md`](EXACT_SLICE.md))
140 dedicated endgame positions solved exactly (k=2 marginalized / k=3 clairvoyant+α-β),
measuring each agent's conversion **regret** (distance of its move from the exact-optimal value):

| | random | greedy | h200 | h800 | h3200 | **h6400** | **rod1** | iter08 |
|---|---|---|---|---|---|---|---|---|
| mean regret (pts) | 2.06 | 0.98 | 0.60 | 0.65 | **0.46** | **0.52** | **0.81** | 0.98 |
| match-optimal % | 31 | 75 | 74 | 72 | 81 | **80** | **64** | 63 |

**A second, independent rod1 deficit — in the endgame.** rod1's conversion regret (0.81, 64% optimal)
is **worse than every heuristic agent** (h3200 0.46/81%, h6400 0.52/80%, even h200 0.60/74%) — it sits
between greedy and h200. iter08 is worse still (0.98). This corroborates the behavioral farm-claim
finding (both deficits localize to the **endgame**) and the prior autopsy / exact-endgame-hybrid result
that rod1's loss to h6400 is an endgame (last-tile placement + conversion) problem, not a midgame one.

## Part F — anti-benchmax safeguards (implemented)

1. **dev/test split** — thresholds frozen on a dev band before the held-out audit (above).
2. **No training on labels** — this branch produces no training data from the benchmark; detectors
   never touch a gradient.
3. **Outcome sanity** — Table 5 (close games, |margin|≤5): only **`farm_claim` is predictive (+17pp)**;
   `block` −10pp, `avoid_feeding` +2pp, `contest_merge` −11pp are flat/negative → marked **descriptive
   only, not target-worthy**. This safeguard did its job: it kills 3 of 4 motifs as benchmax bait.
4. **Cross-opponent generalization** — `farm_claim` rod1 generalizes *poorly*: strong vs strong-opp
   (53%≈h6400) but weak vs weak-opp (41% vs h6400 57%). The behavior is suppressed/expressed by
   opponent context, so a single-regime score would mislead — flagged, and reported per opponent class.
5. **Cross-deck generalization** — `farm_claim` take rates are stable across the 12 regimes/seed bands
   (heuristics 59–60% throughout; rod1 54% ±, gap concentrated in vs-weak); not a single-deck artifact.
6. **Human-readability** — structured examples (Part E) output for human review, not blind trust.
7. **Champion quarantine** — behavior score alone cannot promote any agent; any future trained agent
   must still beat `h6400_v2.8` on full-game held-out winrate (PRODUCTION.yaml untouched, v2.7 frozen,
   v2.8 opt-in).

## Part G — verdict (brutally honest)

1. **RoD1: strategic behavior or search/eval compression?** **Compression of heuristic-level behavior**,
   not a distinct strategic capability. On the credible motifs rod1 sits at/below the h-agents and far
   above random — it recognizes farm value and contests, but at heuristic level, with one deficit. No
   evidence of strategy beyond what the v2.7 leaf already encodes. This *confirms* the prior picture
   (rod1 compresses h3200/h6400) rather than revealing a hidden dimension.
2. **Motifs h6400 shows more than RoD1?** Only **`farm_claim`** (+6pp overall; +20–30pp in
   late_mid/pre_endgame; +16pp vs weak opponents). Everything else is equal or noise.
3. **Does RoD1 punish weak opponents?** **No.** It claims 16pp fewer high-value fields than h6400
   against random opponents (the clearest, most outcome-relevant failure), while matching h6400 vs
   strong opponents. It under-exploits weak play specifically on farms.
4. **Failures broad or motif-specific?** **Narrow and ENDGAME-localized.** Two convergent deficits, both
   in the endgame: *late/weak-opponent farm claiming* (behavioral) and *exact conversion regret*
   (0.81 vs h6400 0.52, 64% vs 80% optimal). rod1 is fine on contesting, opening/midgame farms, and the
   (noisy) tile motifs — the weakness is specifically endgame execution, matching the prior autopsy.
5. **Are the motif definitions credible?** **One of four.** `farm_claim` is credible (discriminates +
   outcome-relevant). `contest_merge` is a coarse search-detector (saturated above greedy, not
   outcome-predictive). `block`/`avoid_feeding` are **noise** — equity proxies where random ≈ h6400.
   Honest hit rate: the structural motifs survived, the equity proxies died, as flagged a priori.
6. **Plausible future tools/training targets?** **After the validation audit: none actionable.**
   `farm_claim` survives as a *monitoring diagnostic* (it correlates with winning in competitive games,
   +5pp after lead/opponent controls), but it does **not** point to a fixable RoD1 weakness — RoD1's
   farm deficit is in low-leverage regimes and its own farm claims are outcome-neutral (−2pp). See
   [`VALIDATION_FARMCLAIM.md`](VALIDATION_FARMCLAIM.md).
7. **Kill as benchmax bait?** `block` and `avoid_feeding` (random ≡ h6400 on 82%/87% of opportunities —
   the detector cannot even separate random from the strongest agent). Demote `contest_merge` to a
   descriptive random-vs-search check (its −11pp outcome is thin noise, not "contesting is bad").
8. **Next branch? → STOP (tightened by the validation audit).** The first pass flagged late/weak-opp farm
   claims as a candidate lever; the audit shows it is **not actionable** — the deficit is concentrated vs
   weak opponents (62% of rod1's misses) and in already-won/late positions (top misses at pre-move margin
   +33…+54 = margin-padding, not lost games); where farms have leverage (vs strong, even score, opening)
   RoD1 already matches h6400 (53/53 vs strong). Expected winrate move vs `h6400_v2.8` ≈ 0. **Do not run
   the probe; do not train on this benchmark (3/4 motifs are Goodhart traps).** RoD1's real loss to h6400
   is the separately-characterized endgame **placement/conversion** leak (deeper-search/exact-hybrid), which
   this benchmark corroborates but does not newly unlock.

## 10-line executive summary

1. Built a diagnostic strategic-behavior benchmark (4 operational motifs) over **1,918 labeled positions**,
   12 regimes, a 9-agent weak→strong panel, counterfactually harvested — **diagnostic only, no training, no promotion**.
2. **Rules finding:** in 2p base you cannot place a meeple on an occupied feature, so meeple-phase
   "steal/denial" is impossible (fired 0/22 games); contest/denial exist **only** as TILES-phase merges.
3. **3 of 4 motifs are non-diagnostic:** `block`/`avoid_feeding` are noise (random ≈ h6400, flat outcome);
   `contest_merge` is a coarse "searches-at-all" step (saturated above greedy, outcome-negative).
4. **`farm_claim` is the one credible motif** — it discriminates agents AND predicts winning (+17pp in
   close games; strength-confounded, so suggestive not causal).
5. **RoD1 exhibits real strategic behavior, but only at heuristic level** (farm_claim 54% vs h-agents 60%,
   vs random 24%) — compression, not a new capability.
6. **RoD1's deficits localize to the ENDGAME** — it under-claims farms vs h6400 (−6pp overall, **−16pp
   vs weak**, growing late) AND has higher exact endgame conversion regret (0.81 vs h6400 0.52; 64% vs
   80% match-optimal), corroborating the known endgame last-tile-placement leak.
7. **RoD1 does not punish weak opponents** on farms — it leaves the high-value fields random opponents
   fail to defend, exactly where h6400 feasts.
8. Deeper heuristic search (h3200→h6400) buys **no** extra strategic behavior — consistent with the
   deeper-search ruler (depth sharpens margin, not decisions).
9. **Anti-benchmax safeguards worked:** the outcome-sanity gate killed 3/4 motifs; `farm_claim`'s
   cross-opponent split exposed a vs-weak-only effect a single score would have hidden.
10. **Recommendation (after the validation audit): STOP — no actionable lever.** The one candidate
    (farm_claim) is confounded/low-leverage (honest +11pp → +5pp after controls; rod1's own claims
    outcome-neutral; deficit lives in already-won/vs-weak positions). Keep farm_claim as a monitoring
    diagnostic; retire the others. No champion, no promotion; PRODUCTION.yaml untouched, v2.7 frozen, v2.8 opt-in.
