# High-Contrast Decision-Signal Distillation — Signal Density (Stage 2 GATE)

**Date:** 2026-06-26 · **Branch:** rod_v2_flywheel · **MEASUREMENT / DIAGNOSTIC ONLY.** No promotion · v2.9 evaluator frozen.

Pilot pool: the 1616-root replay-verified multiphase set, re-labeled with the v2.9 deep teacher HeuristicMCTS@6400 for **per-action Q** (probe_signal_density.py). Students forwarded: rod1 / iter04 / iter06 (device=cuda). Plan: [HIGH_GAP_PLAN.md](HIGH_GAP_PLAN.md).

## GATE VERDICT — **PASS.** Abundant high-contrast, student-wrong signal exists.

Selecting by **Q-gap / regret** (not argmax disagreement) inverts the prior result. Where
hard-policy-repair found only ~3% of its (disagreement) states at gap > 0.02, the **whole** pool here
is **36.9% at gap ≥ 0.02** and **21.8% gap≥0.02 ∧ iter04-wrong** (352 states), **42.6% iter04-regret≥0.02**
(688). The trainable cell is **phase-balanced** (~20–24% every phase incl. 89 endgame) — not a regime
artifact. A 20k–50k mine yields 5k–22k trainable states (§5). **Proceed to Stages 3–6.** The prior
experiment's "diffuse policy" non-failure was a selection artifact (disagreement ⇒ value-indifferent);
the decisive states it missed are plentiful and the student is wrong on them.

## 1. Q-gap density (teacher only — does the choice matter?)

| tier | thr | count | % of pool |
|---|--:|--:|--:|
| weak | 0.005 | 846 | 52.4% |
| medium | 0.010 | 720 | 44.6% |
| strong | 0.020 | 597 | 36.9% |
| very_strong | 0.040 | 462 | 28.6% |

Q-gap mean 0.0471 · median 0.0060 · p90 0.1470 · p95 0.2265. (value scale: best-worst Q-range mean 0.218.)

## 2. Trainable cell — high Q-gap AND student wrong (the gate)

Count of states with `q_gap >= tier` **and** `student_top != teacher_best` (the states worth distilling: decisive AND the net is currently wrong).

| tier | thr | iter04 | iter06 | rod1 |
|---|--:|--:|--:|--:|
| weak | 0.005 | 530 | 522 | 563 |
| medium | 0.010 | 436 | 428 | 479 |
| strong | 0.020 | 352 | 342 | 392 |
| very_strong | 0.040 | 259 | 253 | 294 |

## 3. Student-regret density — Q(teacher_best) − Q(student_top)

| regret tier | thr | iter04 | iter06 | rod1 |
|---|--:|--:|--:|--:|
| weak | 0.005 | 879 | 887 | 931 |
| medium | 0.010 | 798 | 803 | 854 |
| strong | 0.020 | 688 | 693 | 744 |
| very_strong | 0.040 | 574 | 575 | 620 |

## 4. Strong trainable cell (gap≥0.02 ∧ iter04-wrong) by phase / score

| slice | count | % of slice |
|---|--:|--:|
| opening | 63 | 24% |
| midgame | 59 | 22% |
| late_mid | 61 | 23% |
| pre_endgame | 80 | 22% |
| endgame | 89 | 20% |
| close-score(≤5) | 111 | 23% |

## 5. Yield projection to a scaled mine

Trainable yield = pilot trainable-cell fraction × mine size. Held-out test needs ~1k states with gap≥0.02 OR regret≥0.02.

| selector (iter04) | pilot frac | per 25k | per 50k | per 100k |
|---|--:|--:|--:|--:|
| gap≥0.02 ∧ wrong | 21.8% | 5445 | 10891 | 21782 |
| gap≥0.01 ∧ wrong | 27.0% | 6745 | 13490 | 26980 |
| regret≥0.02 | 42.6% | 10643 | 21287 | 42574 |
| gap≥0.02 OR regret≥0.02 | 57.7% | 14433 | 28867 | 57735 |

<!-- q-fallback rows (student_top unvisited by teacher): 13 total across 3 nets -->
