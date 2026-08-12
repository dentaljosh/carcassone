# DENIAL CALIBRATION — READOUT (dose/threshold selection for the D1 screen)

> **STATUS: RAN AND READ 2026-08-12 (~01:00). Branch `FUND-SMALLEST` fired.**
> 0 games played, no deck band consumed, no elo statistic computed, no `results.csv` row
> owed. `governance/PRODUCTION.yaml` untouched. The selection rule was committed in
> [CALIB_READ_RULE.md](CALIB_READ_RULE.md) (`e2af769`) **before any arm's flip rate was
> read** — the numbers below were produced against a fixed rule, not the other way round.

## 1. What ran

Three arms replayed the **18 banked E4 human-vs-champion archives**, re-running the
production search at every champion decision ply with the denial leaf against the production
leaf under CRN (shared seed, shared `_move_idx`), recording whether the **pick changes**.
Arms share corpus, seeds and dose ladder; only the predicate thresholds differ. Each arm
graded **1,079 champion plies**. Instrument:
[`denial_e4_replay.py`](../../scripts/classical_search/denial_e4_replay.py).

**Integrity: 18/18 archives replayed with `replay_scores_match: true` in every arm — 0
mismatches.** Rules epoch resolved per archive from its own stamp, as required (15
`fixed_v1`, 2 `walled`, 1 `app_aug2`); each archive replays at the budget it was played at.

## 2. The ladder

| arm | `size_min` | `open_max` | flip rate @ dose 1.0 | @ dose 4.0 |
|---|---|---|---|---|
| A (production spec) | 8 | 2 | **4.45%** (48/1079) | 8.25% (89/1079) |
| **B** | **5** | **3** | **13.62%** (147/1079) | 23.91% (258/1079) |
| C (deliberately wide) | 3 | 4 | 22.89% (247/1079) | 39.48% (426/1079) |

Rates independently recomputed from the per-game JSONs and cross-checked against each arm's
own `SUMMARY.json` rollup — they agree exactly.

## 3. Verdict against the committed rule

**§3 branch 1 `FUND-SMALLEST` fires** (some cell has `f ≥ 0.10`). The rule directs the
smallest dose and tightest thresholds reaching the bar, plus the measured dose above it:

- **Funded: dose 1.0 and dose 4.0, both at `size_min = 5`, `open_max = 3`.**
- **Arm A is excluded by its own number.** At `f = 4.45%` the production-spec predicate sits
  below the 5% floor — the band where, per the rule's arithmetic, an n=200 screen cannot
  resolve the effect *even if the term is genuinely good*. It is worth stating plainly that
  **(8, 2) is what a default screen would have used**, and it would have bought a guaranteed
  null on a term that demonstrably does change play at a wider predicate.
- No dose below 1.0 is funded: none was measured, and the rule's guard forbids adding a
  ladder rung after seeing the ladder.

## 4. The mechanism hypothesis this refutes

Code review of the term raised a specific structural worry: the term prices a **state** (a
large, near-complete, opponent-majority city) that the champion's move often cannot affect,
so it might land as a near-constant offset across sibling moves and **cancel in the argmax**
— which would have made it inert regardless of dose, and would have made widening the
predicate useless. That was pre-registered as branch `STRUCTURAL-NO-FUND`.

**It did not fire, and the hypothesis is refuted at these thresholds.** The ladder rises
~5× from A to C at both doses; loosening the predicate buys flips roughly proportionally.
The term expresses fine — the production-spec predicate was simply too narrow. Arm C was
added mid-run purely to make this branch decidable, on cores that were otherwise idle.

## 5. Secondary observations (descriptive; NOT inputs to the funding decision)

- **Flips are overwhelmingly tile-phase: 75–78% in every arm × dose** (B @ 1.0: 111 tiles vs
  36 meeples). Consistent with the term's mechanism — city feeding/denial is expressed when
  placing tiles — and it coincides with the E4 grading's finding that the human's ΔQ
  concentrates in tile placement. Coincidence of location, not evidence of anything.
- **Whether flips concentrate on the plies where the human out-farmed the champion has
  deliberately NOT been computed yet.** [CALIB_READ_RULE.md](CALIB_READ_RULE.md) §4 bars it
  from the funding decision precisely because it is the kind of finding that could be used
  to rescue a cell failing the bar. It is now safe to compute (funding is settled) and is
  intended input to the *successor* term's design, not to D1.

## 6. What this does NOT say

1. **Flip rate is not strength.** A changed pick is not a better pick. Nothing here predicts
   the sign of the D1 screen.
2. **The calibration corpus is human games; the screen's corpus is fresh self-play decks.**
   Disjoint by construction, so nothing chosen here contaminates the screen's statistic —
   but it also means the flip rate observed against a human opponent need not hold against
   the champion's own play distribution.
3. **Mixed rules epochs and mixed budgets** across the 18 archives (each replayed at its own)
   make this a pooled *expressiveness* measure, not a per-epoch estimate.
