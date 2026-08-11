# Post-Search Residual — STAGE 2 BASELINES + ORACLE ADAPTIVE-COMPUTE GATE

_generated 2026-06-28 21:43 · net-free · frozen v2.9 leaf · 3000 roots (Phase-A greedy-self-play distribution)_

**The make-or-break gate.** A perfect oracle (escalates exactly the roots with the largest TRUE regret-reduction) upper-bounds any predictor. If it barely beats uniform at matched average compute → **Decision A**, no adaptive-compute opportunity.

## How often is h200 materially wrong vs h6400?

- **positive_strong** (q_gap≥0.02 ∧ regret(h200)≥0.02): **3.6%** (109 roots)
- **positive_medium** (q_gap≥0.01 ∧ regret(h200)≥0.01): **5.9%** (178 roots)
- negative (h200 fine / agrees / h6400 near-tie): 90.0%
- h200 top move == h6400 top move: 60.0%

## Is the residual concentrated enough to predict?

Share of TOTAL h200 regret held by the worst roots: top-5%=**72%**, top-10%=**86%**, top-20%=**96%**, top-50%=100%.
_(High concentration → adaptive compute can win by routing deep search to the few bad roots. Diffuse regret → uniform is near-optimal → Decision A.)_

## Uniform compute curve (mean regret vs avg sims)

| sims | 200 | 400 | 800 | 1600 | 3200 | 6400 |
|---|---|---|---|---|---|---|
| mean regret | 0.00609 | 0.00412 | 0.00302 | 0.00193 | 0.00089 | 0.00000 |

## Matched-average-compute comparison (lower regret = better)

oracle = best of {pairwise escalate-200→D, multi-depth route-each-root} = the *ceiling* on any escalation predictor. heuristic = best simple rule (entropy / low-gap / low-share / legal-n) = the bar a learned model must clear.

| avg compute C | uniform h(C) | random | best heuristic | pairwise oracle | multi-depth oracle | **ORACLE** | Δ vs uniform |
|---|---|---|---|---|---|---|---|
| 400 | 0.00412 | 0.00536 | 0.00502 (low_top2gap→800) | 0.00154 (→3200) | 0.00047 | **0.00047** (→multi) | +0.00365 (+88.6%) |
| 800 | 0.00302 | 0.00384 | 0.00302 (entropy→800) | 0.00078 (→3200) | 0.00012 | **0.00012** (→multi) | +0.00290 (+96.0%) |
| 1600 | 0.00193 | 0.00241 | 0.00193 (entropy→1600) | 0.00073 (→3200) | — | **0.00073** (→3200) | +0.00120 (+62.4%) |

## Oracle vs uniform across a finer budget sweep (uniform = linear-interp; oracle = multi-depth ceiling)

| avg compute | uniform(interp) | best oracle | Δ vs uniform |
|---|---|---|---|
| 300 | 0.00511 | 0.00093 | +81.7% |
| 400 | 0.00412 | 0.00047 | +88.6% |
| 600 | 0.00357 | 0.00017 | +95.1% |
| 800 | 0.00302 | 0.00012 | +96.0% |
| 1200 | 0.00248 | 0.00002 | +99.3% |

## GATE VERDICT

Rule: _oracle beats uniform at matched avg-compute by >=15% rel AND >=0.002 abs at >=1 anchor_.

### **PASS — adaptive-compute opportunity EXISTS**

Anchors where oracle beats uniform meaningfully: C=400 (+88.6%, +0.00365), C=800 (+96.0%, +0.00290).

→ Proceed to Stage 3 (train escalation predictors) — but first **broaden roots to real MCTS-play distributions (Phase B)**; this gate ran on greedy-self-play roots.
