# Level-2 L2-3 — endgame regret (VERDICT)

> **Measurement gate only.** No train / promote / redesign / modify-iter8 follows.
> Solver-grounded (spec §6 / V9): an EXACT minimax/expectiminimax over the final K
> tiles labels GROUND-TRUTH optimal moves — the first NON-circular label in the
> program (L1/L2 are in-ecosystem; this is independent of any heuristic).
> Run 2026-06-19, code_rev `5406c74`+L2-3 tooling. Suite + results:
> `measurement/level2/{l23_positions.jsonl, L23_REGRET_RESULTS.json}`.
> **⚠️ KEPT SEPARATE from full-game Elo (L2-1/L2-2):** endgame-move-optimality ≠
> full-game strength — and the data below shows they genuinely diverge.

## Apparatus
- **Solver** (`scripts/level2/endgame_solver.py`): plain minimax (clairvoyant, real
  deck) / expectiminimax (marginalized over the unknown bag) + exact-value
  transposition table; leaf = real final score-diff (`flat_base_score`). **Brute-force
  validated** (`tests/test_endgame_solver.py`: V-brute == independent reference, V2
  K=1 clair==marg, V9 value realized by optimal play — 9 tests pass).
- **Suite** (150 greedy-self-play positions/K, fresh band 3.2e9, full provenance:
  seed/ply/scores/meeples/bag-multiset/deck-order; `replay_to` round-trips exactly).
- **Tractability bound (HONEST scope):** the engine's per-node deepcopy (~1.7 ms)
  caps exact solving at **K=2** (~4 s/position, fully solved). K≥3 needs >80k nodes
  (~minutes); K≥4 intractable. So this verdict is the **K=2 endgame** (the last two
  tiles). A make/unmake solver (avoid the deepcopy) is the path to K=3-6 — future work.
  ⚠️ **K=3 best-effort OOM-crashed the 5800x WSL at W=20** (20 workers × solver
  transposition-tables + heur@3200 trees + net copies exhausted RAM) → got 74/150
  before the VM restarted. **Memory-heavy solver runs need low W** (≤8–10). The 74
  partial K=3 positions (68 decision) are saved + folded in below.

## K=3 (partial, 68 decision positions — clairvoyant only; the deficit is DEPTH-ROBUST)
| agent | top-1 | mean regret |
|---|---|---|
| heur_v1@200 / greedy | 0.750 | 0.52 / 0.63 |
| heur@1600 | 0.647 | 0.78 |
| heur@800 | 0.632 | 0.81 |
| heur@3200 | 0.618 | 0.82 |
| **iter8** | **0.574** | **0.96 (highest)** |
**iter8 is the WORST at K=3 too** (top-1 0.574, highest mean regret) — its endgame
deficit holds at greater depth. (Twist at K=3: the *shallow* agents v1/greedy top the
list while deep heur search drops — n=68, and at K=3 the clairvoyant agents plan along
2 unknown future tiles; treat the heur ordering as noisy, but **iter8-worst is robust**.)

## Result — K=2 endgame (150 positions, 141 "decision" positions where the move matters)
Clairvoyant GT (== marginalized at K=2: the 1-tile bag is determined). Top-1 = fraction
the agent's move is solver-optimal; regret = points lost vs optimal.

| agent | top-1 | mean regret | median | >2 pt | >5 pt | >10 pt |
|---|---|---|---|---|---|---|
| heur@3200 | **0.837** | 0.40 | 0 | 5.7% | 1.4% | 0% |
| heur_v1@200 | **0.837** | 0.37 | 0 | 4.3% | 0.7% | 0% |
| heur@1600 | 0.780 | 0.46 | 0 | 5.7% | 1.4% | 0% |
| greedy | 0.759 | 0.74 | 0 | 12.8% | 2.8% | 0% |
| heur@800 | 0.759 | 0.52 | 0 | 7.8% | 1.4% | 0% |
| **iter8** | **0.667** | 0.61 | 0 | 6.4% | 1.4% | 0% |

## Findings (endgame regret — NOT full-game strength)
1. **The full-game Elo champion iter8 plays the K=2 endgame the WORST** (top-1 0.667,
   the lowest of all six). Its learned policy wins the full game (L2-2: > both heuristic
   rungs) but is the *least precise* at the very last tiles.
2. **Endgame precision is DECOUPLED from full-game strength.** `heur_v1@200` — the
   *weakest* full-game agent (L1: barely above greedy) — ties heur@3200 for the *best*
   endgame top-1 (0.837). Full-game Elo rank and endgame-optimality rank are nearly
   inverted. This concretely justifies keeping the two measurements separate (#7).
3. **Deeper heuristic search monotonically improves endgame play:** heur@800 (0.759) <
   @1600 (0.780) < @3200 (0.837). More search → more endgame precision, as expected.
4. **Blunders are rare and small.** No agent ever loses >10 pts; >5-pt errors are 0.7–2.8%.
   iter8's single worst error is 9 pts (a missed completion, seed 3200000129), but it is
   *bidirectional*: iter8 is also optimal where heuristics blunder up to 6 pts
   (seed 3200000123). So iter8 is *less precise*, not *uniformly worse* — it cedes small
   amounts more often, the heuristics occasionally cede large amounts.
5. **Mechanism (hypothesis):** at K=2 all meeples are already placed (7/7), so the task is
   pure last-tile score-squeeze. iter8 is trained on full-game value, where the final
   tile barely moves the outcome — so its policy underweights the endgame point-grab that
   a score-maximizing search (heuristic) nails. iter8's edge is *earlier* in the game.

## Validation (V9/V2 — passed)
- V9: the solver's value is realized by optimal self-play (tested). V2: K=1 clair==marg.
  V-brute: solver == independent brute-force (exact). So the ground-truth labels are
  trustworthy — this is the program's first non-circular agreement measure.

## Caveats
- **K=2 only** (the deepest *fully* tractable bucket given the engine cost). The
  endgame-regret picture at K=3-6 (more decisions, meeples sometimes still in hand) is
  not yet measured — the K=3 extension (running) is the first step.
- **Marginalized GT adds nothing at K=2** (single determined draw) — its preferred role
  is at K≥3, pending a faster solver.
- Regrets are **small in absolute points** (mean 0.37–0.74); the *ranking* is the signal,
  the magnitudes are modest. Positions are from greedy self-play (neutral generator).
- **NOT an Elo statement.** iter8 still wins full games (L2-2); it just isn't the most
  precise endgame technician.

## Bottom line
The first ground-truth (solver-labeled) measurement says: **iter8's strength is not
endgame precision.** It wins the full game via earlier policy while ceding small,
non-catastrophic amounts in the last-tile endgame, where deep heuristic search (and even
the weak v1 heuristic) is more optimal. Endgame-regret and full-game-Elo are genuinely
different axes — neither dominates the other. **No train/promote follows — measurement gate.**

## Cross-reference — Joshua #8 (Elo, SEPARATE from this regret verdict)
The same-band (3.10e9) iter8-vs-heur ladder completed: iter8 vs heur@800 **+40.1**,
heur@1600 **+24.4**, **heur@3200 −28.7 (45.9% wr, paired z−0.70 = tie/marginally behind)**.
iter8's full-game margin shrinks monotonically with heur depth and is **erased by
heur@3200**. This dovetails with the regret result: **heur@3200 is simultaneously the
most endgame-precise (this verdict) AND the heuristic that catches iter8 full-game (#8)**
— deep search wins on both axes. (Recorded in results.csv `l22_iter8_vs_heur3200_b310_n400`,
kept out of the endgame-regret conclusions per #7.)

## Next / future
- **K=3-6 exact** needs the make/unmake solver (the deepcopy wall + the OOM); then the
  marginalized GT where it matters (K≥3) + larger n. The K=3 partial already confirms
  iter8-worst is depth-robust.
- Re-run K=3 at **low W (≤8)** if completing the 150 is wanted (the W=20 OOM lesson).
