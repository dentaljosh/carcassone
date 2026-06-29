# Post-Search Residual — STAGE 2 BASELINES + ORACLE ADAPTIVE-COMPUTE GATE

_generated 2026-06-28 23:08 · net-free · frozen v2.9 leaf · 10351 roots (Phase-B real MCTS-play distribution)_

**The make-or-break gate.** A perfect oracle (escalates exactly the roots with the largest TRUE regret-reduction) upper-bounds any predictor. If it barely beats uniform at matched average compute → **Decision A**, no adaptive-compute opportunity.

## How often is h200 materially wrong vs h6400?

- **positive_strong** (q_gap≥0.02 ∧ regret(h200)≥0.02): **2.8%** (287 roots)
- **positive_medium** (q_gap≥0.01 ∧ regret(h200)≥0.01): **5.2%** (542 roots)
- negative (h200 fine / agrees / h6400 near-tie): 91.3%
- h200 top move == h6400 top move: 70.9%

## Is the residual concentrated enough to predict?

Share of TOTAL h200 regret held by the worst roots: top-5%=**67%**, top-10%=**87%**, top-20%=**99%**, top-50%=100%.
_(High concentration → adaptive compute can win by routing deep search to the few bad roots. Diffuse regret → uniform is near-optimal → Decision A.)_

## Uniform compute curve (mean regret vs avg sims)

| sims | 200 | 400 | 800 | 1600 | 3200 | 6400 |
|---|---|---|---|---|---|---|
| mean regret | 0.00314 | 0.00249 | 0.00184 | 0.00138 | 0.00067 | 0.00000 |

## Matched-average-compute comparison (lower regret = better)

oracle = best of {pairwise escalate-200→D, multi-depth route-each-root} = the *ceiling* on any escalation predictor. heuristic = best simple rule (entropy / low-gap / low-share / legal-n) = the bar a learned model must clear.

| avg compute C | uniform h(C) | random | best heuristic | pairwise oracle | multi-depth oracle | **ORACLE** | Δ vs uniform |
|---|---|---|---|---|---|---|---|
| 400 | 0.00249 | 0.00291 | 0.00237 (low_top2gap→800) | 0.00088 (→3200) | 0.00019 | **0.00019** (→multi) | +0.00230 (+92.5%) |
| 800 | 0.00184 | 0.00258 | 0.00179 (low_top2gap→1600) | 0.00046 (→3200) | 0.00003 | **0.00003** (→multi) | +0.00181 (+98.5%) |
| 1600 | 0.00138 | 0.00193 | 0.00115 (low_top2gap→3200) | 0.00046 (→3200) | — | **0.00046** (→3200) | +0.00092 (+66.7%) |

## Oracle vs uniform across a finer budget sweep (uniform = linear-interp; oracle = multi-depth ceiling)

| avg compute | uniform(interp) | best oracle | Δ vs uniform |
|---|---|---|---|
| 300 | 0.00282 | 0.00043 | +84.8% |
| 400 | 0.00249 | 0.00019 | +92.5% |
| 600 | 0.00216 | 0.00008 | +96.1% |
| 800 | 0.00184 | 0.00003 | +98.5% |
| 1200 | 0.00161 | 0.00046 | +71.4% |

## GATE VERDICT

Rule: _oracle beats uniform at matched avg-compute by >=15% rel AND >=0.002 abs at >=1 anchor_.

### **PASS — adaptive-compute opportunity EXISTS**

Anchors where oracle beats uniform meaningfully: C=400 (+92.5%, +0.00230).

→ Proceed to Stage 3 (train escalation predictors) — but first **broaden roots to real MCTS-play distributions (Phase B)**; this gate ran on greedy-self-play roots.
