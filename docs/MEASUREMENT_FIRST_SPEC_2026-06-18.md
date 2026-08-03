# Measurement-First Design Spec (2026-06-18)

> **✅ STATUS: EXECUTED — and it is still the DIAGNOSIS of record, but NOT the queue (stamped 2026-08-03).**
> The three-level program below was built and read out (Level-1/Level-2 verdicts CL-022…CL-027, plus the
> clairvoyance-gap and endgame-regret verdicts under `measurement/`); the *diagnosis* — measurement is the
> binding constraint, and a self-anchored ladder can climb while absolute strength regresses — is what
> CLAUDE.md still cites as blocker #1. **The live work queue moved to
> [PROGRAM_ROADMAP_2026-07-07.md](PROGRAM_ROADMAP_2026-07-07.md) on 2026-07-07** — read that for what's
> next, not this file. Two things below are superseded by later work: the *ruler of record* is now the
> **fair** sub-ladder (D0/CL-046, the 2026-07-09 pivot demoted the clairvoyant ladder to a cheap screen),
> and offline value/ranking gates score against the **exact solver**, not h6400 (POST_REVIEW_PLAN F4).
> *(Original status header follows.)*
>
> **Status (as written 2026-06-18):** PROPOSED. Written after the value-head architecture swing was closed
> (CL-021, `value_ranking/VALUE_RANKING_VERDICT.md`). The binding constraint on the superhuman goal is now
> **measurement**, not modeling. This spec is the next-bet design; no build started.

## 1. Why measurement is the binding constraint
Two structural facts (CLAUDE.md "two blockers"), now the *only* things between us and a credible
strength claim:

- **(A) Clairvoyance.** Production search plans along the engine's actual `state.deck` order — it
  knows future tile draws. Real Carcassonne is imperfect-information (you don't know the draw
  order). A clairvoyant agent **over-estimates its own strength** and is **not deployable vs humans**.
  Every elo we have (iter8 +58/+142, the heur ladder) is a *clairvoyant* number of unknown transfer.
- **(B) Saturated ruler.** Our only in-ecosystem reference is the v2.7 leaf, which is topped out
  (Tier-1 saturated; self-anchored elo can climb while absolute strength regresses —
  `feedback_anchor_before_scaling`). With no reference *above* the heuristic, "superhuman" is
  literally unmeasurable.

You cannot fix strength until you can see it. This spec builds the eye.

## 2. The Carcassonne-specific insight (why this is tractable)
Carcassonne's hidden information is **only the ORDER of future draws from a PUBLIC bag** — the
remaining-tile multiset is known to both players, there is **no hidden opponent state** to infer.
This is fundamentally easier than poker/hidden-card games:

- Every **determinization** (a shuffle of the known remaining bag) is a *valid* possible world.
- **Determinization-based search (PIMC / IS-MCTS) is well-suited**, and the classic pathologies
  (strategy fusion, non-locality) are **mild**: hidden info resolves one tile per turn, symmetric
  across both players, no belief-over-opponent to maintain.
- ⟹ A non-clairvoyant agent is a *wrapper* problem, not a rewrite.

**⚠️ Verify-first assumption (Step 0):** that the current MCTS is in fact clairvoyant (uses the real
deck order in expansion/rollout). Strongly implied by the wrapper (`StateUpdater.apply_action_inplace`
draws from `state.deck`), but confirm before building — if draws are already sampled, sub-problem (A)
is moot and we jump to the ladder.

## 3. Reusable infrastructure (don't rebuild)
`odo_paired_tally.py` (paired Δelo + z), `eval_net_vs_heuristic.py`/`eval_iter_head_to_head.py`
(paired, seat-balanced, shared-claim, fresh-band), `clean_eval/` provenance (R1/R7 runtime guards,
deck-hash, seed-floor 1e9), `governance/CHECKPOINT_LINEAGE.csv` + the σ_elo n-thresholds (n=400
paired ≈ ±12 elo). The measurement apparatus *extends* these, it does not replace them.

---

## 4. Level 1 — MINIMAL (the clairvoyance probe)
**Goal:** answer "are our strength numbers clairvoyance-inflated?" with the cheapest sound agent,
and stand up one fixed absolute anchor. This is a *measurement* of our current measurement.

**Components**
- **Non-clairvoyant agent = root-determinization wrapper** (no MCTS-internals change): at each move,
  K times replace the unrevealed deck suffix with a fresh permutation of the remaining multiset
  (keep the already-revealed current tile), run the *existing* search, aggregate root visit-counts
  across the K runs, play the consensus action. K≈8–16.
- **Fixed calibration micro-suite (~60 positions):** "reference move" = the move a very deep search
  (sims≈3200) agrees on across determinizations; used as a relative move-quality gauge.

**Correctness risks**
- *Strategy fusion* (averaging root actions across worlds) — mild here, but real; bounds how much to
  trust Level 1 as more than a screen.
- *Circular labels* — the deep-search "reference move" is itself clairvoyant ⇒ the calibration suite
  measures *agreement-with-deep-search*, NOT absolute correctness. Flag explicitly; it is an
  internal-consistency gauge, not a human-anchor.
- *K too small* → noisy consensus; *determinizer leak* → re-shuffles the wrong suffix.

**Expected runtime**
Root-determinization is ≈K× the per-move search. n=200 paired games, K=12, sims=200 ≈ **~12× a
normal eval** ≈ a few hours across the 5800x+laptop cluster (orch helps). Tunable down: n=100, K=8,
sims=120 for a first screen (~1 hr).

**Validation tests**
- **V1 (monotonicity):** non-clairvoyant strength ≤ clairvoyant (perfect info can't hurt). Violation ⇒ determinizer bug.
- **V2 (degenerate case):** at the *last* unrevealed tile, non-clairvoyant == clairvoyant (no hidden info left) — exact.
- **V3 (sampler):** unit test — every sampled deck is a permutation of the remaining multiset and preserves the revealed tile.

---

## 5. Level 2 — ROBUST (a deployable, non-saturated ruler)
**Goal:** a measurement apparatus that neither lies (clairvoyance) nor tops out (saturation).

**Components**
- **Determinized search done right:** either **IS-MCTS** (one info-set tree, re-determinize per
  simulation — sounder, kills most strategy fusion) or root-determinization **with the deck-order
  transposition leak fixed** (transposition/zobrist key = *observable* state only: board + scores +
  meeples + remaining-bag multiset + revealed tile; **exclude unrevealed order**). Proper chance
  nodes at draws.
- **Diverse anchored ladder** spanning the full strength range so the scale can't saturate:
  `random → greedy-1ply → heur-v1 → heur-v2.7 → MCTS{50,200,800} → learned{iter8,iter12}` (+ the
  Level-1 non-clairvoyant variants). Elo via paired/seat-balanced games against **fixed anchors**
  (never self-anchored), n sized per rung to the σ_elo thresholds; the *supra-heuristic* rungs
  (deep MCTS, learned+search) are what give the scale headroom above v2.7.
- **Versioned `MEASUREMENT_PROTOCOL`** extending clean_eval: runtime-verified provenance, deck-paired,
  fresh seed band per claim, manifest per run, both agents' full effective config recorded.

**Correctness risks**
- *Saturation persists* if no rung genuinely exceeds v2.7 — then the ladder still can't see above the
  heuristic (this is the core risk; mitigated only if deep-MCTS/learned+search is really stronger,
  which Level 1's gap + the ladder will reveal).
- *IS-MCTS bugs* (info-set bookkeeping, double-counting); *anchor drift* across epochs; *residual
  determinization bias*.

**Expected runtime**
Ladder is O(#agents × n) paired games × K-determinization (only the non-clairvoyant rungs pay K).
**Days** on the cluster; scope n per pair to the *expected* effect size (coarse screens at n=100,
verdicts at n=400; ±9 elo needs n≈1500). Front-load the rungs adjacent to v2.7.

**Validation tests**
- **V4 (ladder sanity):** monotone with non-overlapping CIs: random < greedy < v1 < v2.7 < MCTS-deep.
- **V5 (no leak):** unit test — two states differing only in unrevealed deck order hash-collide (key excludes order).
- **V6 (reproduce):** the new apparatus reproduces a known clean result (iter8 vs heur sealed, +58/z3.76) within CI.
- **V7 (unbiasedness):** a clairvoyant agent restricted to a single fixed determinization ≈ a non-clairvoyant agent at K=1 (same world) — sanity on the determinization plumbing.

---

## 6. Level 3 — IDEAL (human-anchored, solver-grounded)
**Goal:** the apparatus that can actually support "beats strong/expert humans."

**Components**
- **Human/expert anchor:** games or expert-annotated positions from strong human play (online
  platform logs / recruited experts / published expert games) to place the elo scale at a
  human-meaningful zero. **The only path to a superhuman CLAIM** (everything else is in-ecosystem).
- **Endgame solver:** exact retrograde/expectimax solve of late positions (≤~6–8 tiles left) →
  *ground-truth* best-move labels independent of any heuristic, killing the clairvoyant-label
  circularity of Levels 1–2.
- Full **IS-MCTS + light opponent/belief modeling**, variance-reduced (common decks, antithetic
  determinizations).

**Correctness risks**
- Human-data scarcity/quality and **rating calibration** (whose "expert"? what platform elo?).
- Solver tractable only deep in the endgame (state space explodes earlier).
- Opponent-model overfitting to a narrow human pool.

**Expected runtime**
Human data is the long pole — **weeks, not compute** (acquisition/cleaning). Solver: seconds per
solved endgame, but only ≤~8 tiles. IS-MCTS: similar order to Level 2.

**Validation tests**
- **V8:** human-anchored scale places v2.7/iter8 in a plausible human band (face validity).
- **V9:** solver agreement = 100% on solved positions (by construction; tests the solver).
- **V10:** solver-labeled vs deep-search-labeled calibration agree where both apply (cross-check that deep search ≈ truth in the endgame, bounding its bias mid-game).

---

## 7. The first experiment that would change our beliefs
**Measure the clairvoyance gap** (Level-1 only, ~1–3 hr).

Pre-register: estimand = paired **Δelo(clairvoyant − non-clairvoyant)** for a fixed agent;
matchups (fresh band, seat-balanced, sims=200): **clairvoyant-iter8 vs non-clairvoyant-iter8 (K=12)**,
plus each vs heur-v2.7 for an external anchor; n=200; threshold ±24 elo (2σ at n=200 paired).

- **If the gap is LARGE (≳100 elo):** every strength number we own is clairvoyance-inflated; our
  "strong" agents may be far weaker in real/human play. The entire strength narrative (and the
  superhuman target) must be re-grounded on the non-clairvoyant agent. **Beliefs change hard** —
  Level 2 must be built around the non-clairvoyant agent as *the* baseline.
- **If the gap is SMALL (≲30 elo):** Carcassonne's hidden info is minor, our clairvoyant numbers
  ≈ transfer, and the measurement problem collapses to "just" the **saturated ruler** — a much
  cheaper fix (go straight to the Level-2 ladder, skip the expensive non-clairvoyant search).
- **Intermediate (30–100):** quantifies the deployable-strength discount; informs how much K and
  search the deployable agent needs.

This is the load-bearing assumption behind *all* our measurement. It's cheap, it's decisive in
either direction, and it gates whether Level 2/3 must pay the K× non-clairvoyance cost or not.
**Do not build Level 2/3 before this number exists.**

## 8. Decision gates
1. **Step 0:** confirm the current search is clairvoyant. If not → (A) is moot, jump to §5 ladder.
2. **Level 1 / first experiment:** the clairvoyance gap. Large ⇒ non-clairvoyant agent is mandatory
   in Level 2; small ⇒ ladder-only.
3. **Level 2:** stand up the anchored ladder; **gate on V4/V6**. If no rung exceeds v2.7 (saturation
   persists), the honest conclusion is that we have no supra-heuristic agent yet — which loops back
   to *strength*, now measured on a trustworthy (if heuristic-capped) scale.
4. **Level 3:** only once Levels 1–2 are validated and a human-anchor source is secured. This is the
   superhuman-claim apparatus; everything before it is in-ecosystem.
