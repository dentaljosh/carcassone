# v2.7 failure taxonomy (Phase 1) — a HYPOTHESIS MAP

> **This is a hypothesis map, not a verdict.** It classifies *where* v2.7 disagrees with stronger
> references and *what mechanism* each disagreement plausibly belongs to. Mechanism tags are
> **INTERPRETATION**; the disagreement counts and reference picks are **FACT** (cited rows). A tag of
> "leaf-addressable" is a *claim to be tested* in Phases 4–5, not an established result.
>
> Data: [V27_FAILURE_CASES.csv](V27_FAILURE_CASES.csv) (678 cases, built by
> [scripts/heuristic_v28/build_failure_cases.py](../../scripts/heuristic_v28/build_failure_cases.py)
> from the pre-tool endgame + midgame disagreement CSVs). v2.7 ≡ `virtual_score_v2` / `flat_leaf`.

## 0. The headline (FACT, then the hard truth)

678 cases where v2.7-static's pick ≠ a stronger reference (520 midgame vs heur@3200 teacher; 158
endgame iter8-misses vs exact/heur@3200). Split by whether a *leaf* change could plausibly fix them:

| leaf_addressable | cases | % | what it is |
|---|---:|---:|---|
| **no** | 454 | 67% | structural/unclear (385) + both-miss/search-horizon (69) — deeper SEARCH recovers these, not a leaf feature |
| **partial** | 187 | 28% | closure-timing / farm-growth (93) + farm-final-scoring/structural (82) + completion (12) |
| **yes** | 29 | 4% | meeple-economy (22) + endgame completion-mechanism (7) |
| **weak** | 8 | 1% | bag/scarcity (3) + immediate-score (5) — measured τ≈0 as raw features |

**The hard truth (must stay front-of-mind):** ~67% of v2.7's disagreements are **not leaf-addressable**
on the existing evidence. The midgame audit measured it directly: deeper search recovers ~47% of
iter8's misses, cheap features 2–7% (MIDGAME_REFERENCE_REPORT). So the realistic v2.8 ceiling is
**modest**, and any apparent gain that turns out to be search-imitation or overfitting to these stale
disagreement sets must be killed (Phase 4/5 gates). The credible target pool is the **~216
partial+yes cases, dominated by farm/closure scoring (175) and meeple economy (29).**

---

## 1. Failure mechanisms, ranked by leaf-addressable evidence

### M1 — Farm / final-scoring undervaluation  ·  **STRONGEST leaf-addressable signal**
- **FACT.** Endgame bucket `structural-or-farm` = **82 / 158** iter8 endgame misses
  (pre_tool DISAGREEMENT_CATEGORIES.csv `mechanism`). Midgame `structural/closure` = 93 v2.7-misses,
  a large share of which are farm-growth/closure timing.
- **FACT.** v2.7-static's **K=2 mean regret 0.843 > iter8's 0.573** at equal top-1 (BASELINE_RESULTS.csv
  `v2.7-action-score-only,2`) — its wrong endgame picks are costlier, consistent with mis-pricing the
  final farm/city conversion.
- **Mechanism (INTERP).** v2.7 farm value = v1 base (only `finished` cities count) + a flat `+3×P`
  per incomplete adjacent city. It does **not** model: field majority/ties between players, the number
  of *distinct* cities a field touches at final scoring, or the deck's actual ability to finish those
  cities. → systematic under/mis-valuation of mature contested fields.
- **Candidate patch:** `farm_final_value_v1`. **Risk:** the engine already scores finished-city farms
  in v1; the gain must come from the *incomplete*-city / contested-field estimate, and must beat the
  existing `+3×P` term — small surface, easy to wash out.

### M2 — Completion / closure timing (patience vs greed)  ·  leaf-addressable, but greed is a TRAP
- **FACT.** Midgame `completion/score-greed` = 21 (12 v2.7-miss); `structural/closure` = 133 (93
  v2.7-miss). Endgame `completion` mechanism = 7.
- **FACT (the trap).** Naive completion-greed is the **worst** simple selector: K=2 top-1 **0.331**,
  regret **2.47** (`completion-then-score` in BASELINE_RESULTS.csv) vs v2.7-static 0.682. So the fix is
  *not* "complete more" — it is correctly pricing *when* a closure is worth taking now vs preserving
  control / denying.
- **Mechanism (INTERP).** v2.7's `closure_p={1:0.5,2:0.2}` is a fixed schedule independent of deck
  supply, score margin, or whose tempo it is. It can over-credit a closure that won't actually finish
  or under-credit a near-certain one.
- **Candidate patch:** `completion_timing_v1` and/or the **already-implemented** deck-aware closure
  knobs (`tile_counting_closure`, `closure_continuous_slack`) re-evaluated as v2.8 variants.

### M3 — Meeple economy / recovery  ·  leaf-addressable, small but clean bucket
- **FACT.** Midgame `meeple-economy` = 27 (22 v2.7-miss). The `meeple_k` term **exists but is OFF in
  production** (DEFAULT_CONFIG meeple_k=0.0).
- **Mechanism (INTERP).** v2.7 ignores meeple supply: a placement that strands a meeple for the rest
  of the game (low recovery) vs one returned at imminent closure are valued identically in the base.
- **Candidate patch:** `meeple_economy_v1` — phase-sensitive value for free/recoverable meeples,
  penalty for trapped low-recovery ones. **Risk:** `meeple_k` was left off historically; a flat linear
  term may be too crude. Phase-sensitivity is the differentiator.

### M4 — Opponent denial / contested ownership  ·  partly already present
- **FACT.** v2.7 already **subtracts** the opponent's closure-anticipation bonus (`bonus_opp`) — a
  denial signal exists. No dedicated disagreement bucket isolates "denial-miss"; it is folded into
  structural/unclear.
- **Mechanism (INTERP).** The denial is symmetric (`opp_bonus_cap` defaults = self cap). Asymmetric
  weighting of *blocking an opponent's high-value completion / majority flip* may help, but evidence is
  weak/indirect.
- **Candidate patch:** `opponent_denial_v1` (asymmetric opp cap / contested-feature weighting).
  **Lowest evidence; cheapest to test (a knob already exists).** Treat as speculative.

### M5 — Open-edge / completion scarcity  ·  **WEAK** (measured near-zero as raw feature)
- **FACT.** `bag-aware-closure` and `open-edge-progress` features score **top-1 ~0.10, τ ≈ +0.01** vs
  the teacher (MIDGAME_BASELINE_RESULTS.csv) — essentially no teacher-aligned signal *as raw
  per-action features*. Only 3 v2.7-miss cases tag `bag/scarcity`.
- **Mechanism (INTERP).** Whether deck-supply-awareness helps the *leaf value* (vs the *raw feature*)
  is the open question — the deck-aware closure knobs (M2) are the only credible form.
- **Candidate:** subsumed into M2's deck-aware closure; not a standalone patch.

### M6 — Phase misweighting  ·  speculative
- **FACT.** v2.7-static disagreements are spread roughly evenly across bands (opening 103, early_mid
  98, mid 114, late_mid 108, pre_endgame 97 — V27_FAILURE_CASES.csv). The root-action audit shows
  v2.7-static's gap to the teacher is *largest in the opening* (0.48 vs heur@800 0.755) and compresses
  by endgame (ROOT_ACTION_AUDIT.md).
- **Mechanism (INTERP).** A single fixed schedule/cap across all phases may be suboptimal, but there is
  no clean evidence a *phase-split of the same terms* helps rather than overfits.
- **Candidate:** `phase_weighting_v1` — **lowest priority, highest overfit risk.** Only test if a
  base patch (M1–M3) shows phase-localized gains worth conditioning.

### M0 — NOT leaf-addressable (the 67% to be honest about)
- **FACT.** structural/unclear 385 + both-miss 69 = **454 cases**. These are positional/search-horizon:
  heur@800 recovers 46.8% of iter8's misses, v2.7-static 28.7%, raw/bag features 6–7%
  (MIDGAME_REFERENCE_REPORT). The hybrid-handoff (search) closes the endgame gap; no leaf feature did.
- **Implication.** A v2.8 leaf change is **expected to leave most of these untouched.** If a v2.8
  variant's *only* gain is on this bucket, it is search-imitation, not a leaf fix — flag accordingly.

---

## 2. Distinguishing "leaf-addressable" from "search-horizon" (the central discipline)

| Signal it is **leaf**-addressable | Signal it is **search/horizon** (NOT a leaf job) |
|---|---|
| v2.7's *static eval* ranks the ref move below its pick by a small margin a better term would flip | Deeper heur search (heur@800/1600/3200) recovers it but v2.7-static can't |
| The miss is in a *nameable scoring class* (farm final value, closure delta, meeple return) | tagged `structural/unclear` or `both-miss` (heur@3200 also fails) |
| A counterfactual mutation (deck supply, meeple count, margin) flips the preference *as predicted* | preference only changes with more *simulations*, not with the leaf term |

The autopsy layer ([MECHANISTIC_AUTOPSIES.md](MECHANISTIC_AUTOPSIES.md)) operationalizes this: for each
candidate patch, force the v2.7 line vs the v2.8-preferred line, let a strong continuation play both,
and locate where the margin first diverges — to confirm the *named* mechanism, not just an Elo bump.

## 3. What Phase 2 should propose (preview)

Based on the evidence weight above, the justified candidates are **M1 farm_final_value_v1**,
**M2 completion_timing_v1** (incl. the free deck-aware knobs), and **M3 meeple_economy_v1** — each with
10–30 concrete target cases drawn from V27_FAILURE_CASES.csv. M4 (denial) is a cheap speculative add;
M5/M6 are held unless a base patch localizes a gain. **We do NOT implement all six** — the taxonomy
only supports 3 (+1 speculative).

---
*Phase 1 complete. Artifacts: V27_FAILURE_TAXONOMY.md, V27_FAILURE_CASES.csv (678 cases). Next: Phase 2 patch proposals.*
