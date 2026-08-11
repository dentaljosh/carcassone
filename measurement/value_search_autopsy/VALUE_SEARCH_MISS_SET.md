# Value/Search Autopsy — Stage 1: the miss set

**Date:** 2026-06-27 · **Branch:** rod_v2_flywheel · **DIAGNOSTIC ONLY** (no promotion / no v2.9 change).
Plan: [VALUE_SEARCH_PLAN.md](VALUE_SEARCH_PLAN.md). Source pool: the Path-3 h6400-labeled roots
(pilot 1616 + scaled-leg-A 10,067), restricted to **decision-relevant** roots (h6400 Q-gap ≥ 0.02) =
**4277 roots**, phase-balanced. Harness: `miss_harness.py` (native production NMCTS@200, c=3.0,
rs=0.25, v2.9 leaf), net-on-CPU, W=16 local. Each root's searched move is compared to the h6400
per-action adjusted-Q; **regret = q_best − Q(searched move)**.

## Reproduction of the Path-3 anchor (native re-derivation)

Running NMCTS@200 natively over the gap≥0.02 pool reproduces — and sharpens — the Path-3 finding
that the R2 policy repair does not help search:

| ckpt | n | NMCTS top1 (=h6400) | mean regret | eg n | eg top1 | eg regret |
|---|--:|--:|--:|--:|--:|--:|
| **iter04** (baseline) | 4277 | **0.799** | 0.0189 | 1889 | 0.802 | 0.0173 |
| **R2** (Path-3 repair) | 4277 | **0.775** | 0.0220 | 1889 | **0.819** | 0.0147 |

- On the broad decision-relevant pool R2's searched top1 is **lower** than iter04 (0.775 < 0.799) and
  its mean regret **higher** (0.0220 > 0.0189) — i.e. the policy repair makes NMCTS *worse* overall,
  consistent with the Path-3 game regression (R2 WR 0.409 < iter04 0.463).
- The **only** place R2 helps is the endgame argmax (top1 0.819 > 0.802; eg regret 0.0147 < 0.0173) —
  exactly the "only-endgame-moves" effect Path-3 saw at Stage 5b. Net of the two, R2 is negative.

⟹ Anchor confirmed: **policy signal is learnable but not the binding constraint under search.** The
remaining failure is in how search/value converts, not in the prior. The rest of the autopsy localizes
it on the **iter04** baseline miss set below.

## The miss set

A **miss** = h6400 has a decision-relevant preference (this pool is all gap≥0.02) **and** baseline
iter04 NMCTS@200 fails it: wrong-argmax **OR** visit-share on h6400-best < 0.10 **OR** regret ≥ 0.02.

> **1321 / 4277 misses (30.9%).** → `data/misses_iter04.jsonl` (+ `data/miss_probe.jsonl`, the
> action_q-carrying probe rows the Stage-2 interventions re-search).

### by phase
| phase | misses | mean regret | not-explored | wrong-argmax |
|---|--:|--:|--:|--:|
| opening | 161 | 0.0902 | 3% | 92% |
| midgame | 321 | 0.0816 | 4% | 78% |
| late_mid | 146 | 0.0519 | 12% | 59% |
| pre_endgame | 280 | 0.0452 | 15% | 54% |
| endgame | 413 | 0.0486 | 20% | 54% |

### by score-state
| score-state | misses | mean regret | not-explored | wrong-argmax |
|---|--:|--:|--:|--:|
| close (≤4) | 396 | 0.0745 | 11% | 75% |
| mid (5-12) | 442 | 0.0603 | 8% | 63% |
| blowout (>12) | 483 | 0.0515 | 18% | 58% |

### by legal-action count
| legal-n | misses | mean regret | not-explored | wrong-argmax |
|---|--:|--:|--:|--:|
| ≤8 | 7 | 0.0917 | 0% | 100% |
| 9-20 | 125 | 0.0817 | 4% | 80% |
| >20 | 1189 | 0.0590 | 13% | 63% |

## What the structure already says (pre-intervention)

- **Most misses are wrong-argmax, not unexplored.** Overall ~63% of misses are wrong-argmax;
  not-explored (h6400-best never visited by NMCTS) is the minority — but it **grows monotonically
  opening→endgame (3%→20%)**. So in the early/mid game the search *visits* the right move and still
  ranks another above it (a value/ranking failure, not exploration); only in the endgame does
  "never explored it" become a material share (an exploration/horizon failure).
- **Regret is front-loaded:** opening/midgame misses are individually the costliest (regret 0.090 /
  0.082) though fewer; endgame misses are the most numerous (413) but individually cheaper (0.049).
- **Misses live in wide branching** (1189/1321 at legal-n>20) and across all score states (close
  states are the highest-regret bucket, 0.075).

This frames the interventions: the dominant "visited-but-ranked-below" misses point at the
**value/leaf** ranking (I4 residual, I6 forced-move, I5 classical) and at **search budget** (I1); the
endgame not-explored tail points at exploration/horizon (I1/I2 in the endgame slice, I7). Stage 2
runs the controlled interventions; Stage 3 classifies each miss.
