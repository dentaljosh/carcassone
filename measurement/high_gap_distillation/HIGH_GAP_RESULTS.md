# High-Contrast Decision-Signal Distillation — RESULTS (scaled)

**Date:** 2026-06-26 · **Branch:** rod_v2_flywheel · **MEAS/DIAGNOSTIC ONLY.** No promotion · v2.9 frozen.
Plan: [HIGH_GAP_PLAN.md](HIGH_GAP_PLAN.md) · Gate: [HIGH_GAP_SIGNAL_DENSITY.md](HIGH_GAP_SIGNAL_DENSITY.md) ·
Decision: [HIGH_GAP_DECISION.md](HIGH_GAP_DECISION.md).

Scaled pool: 20160 roots (1120 fresh games, k=2..62) labeled h6400_v2.9 across local(A)+laptop(B),
soft Q-softmax targets (temp=0.03). Hard train=6342, held-out hard TEST=1390 (game-disjoint).
Repair: policy-only fine-tune from iter04 (+stabiliser mix). Pilot (1616-pool) precedent: regret
-16% mean / -32% median, top1 0->0.135 strong-gap on n=96.

## Stage 5 — held-out hard TEST (baseline vs repaired)  (n=1390, device=cuda)

| net | top1 | top3 | rank | p_teach | regret | med_reg |
|---|--:|--:|--:|--:|--:|--:|
| iter04 | 0.000 | 0.299 | 10.48 | 0.059 | 0.1130 | 0.0645 |
| iter06 | 0.085 | 0.306 | 10.21 | 0.064 | 0.1038 | 0.0555 |
| R1 | 0.180 | 0.416 | 9.35 | 0.094 | 0.0828 | 0.0373 |
| R2 | 0.179 | 0.406 | 9.47 | 0.094 | 0.0834 | 0.0370 |

### endgame / strong-gap(≥0.02) subsets — top1 / regret

| net | eg n | eg top1 | eg regret | strong n | st top1 | st regret |
|---|--:|--:|--:|--:|--:|--:|
| iter04 | 410 | 0.000 | 0.1087 | 621 | 0.000 | 0.1592 |
| iter06 | 410 | 0.049 | 0.1057 | 621 | 0.113 | 0.1470 |
| R1 | 410 | 0.171 | 0.0769 | 621 | 0.269 | 0.1128 |
| R2 | 410 | 0.176 | 0.0805 | 621 | 0.261 | 0.1163 |

## Stage 5 — ordinary/stabiliser regression  (n=3611, device=cuda)

| net | top1 | top3 | rank | p_teach | regret | med_reg |
|---|--:|--:|--:|--:|--:|--:|
| iter04 | 1.000 | 1.000 | 1.00 | 0.368 | 0.0000 | 0.0000 |
| R1 | 0.924 | 0.977 | 1.20 | 0.585 | 0.0099 | 0.0000 |
| R2 | 0.949 | 0.987 | 1.13 | 0.635 | 0.0067 | 0.0000 |

### endgame / strong-gap(≥0.02) subsets — top1 / regret

| net | eg n | eg top1 | eg regret | strong n | st top1 | st regret |
|---|--:|--:|--:|--:|--:|--:|
| iter04 | 520 | 1.000 | 0.0000 | 3611 | 1.000 | 0.0000 |
| R1 | 520 | 0.898 | 0.0111 | 3611 | 0.924 | 0.0099 |
| R2 | 520 | 0.931 | 0.0095 | 3611 | 0.949 | 0.0067 |

## Stage 5b — NMCTS@200 on held-out hard TEST (n=400)

| net | NMCTS top1 (=h6400) | NMCTS regret | eg n | eg top1 | eg regret |
|---|--:|--:|--:|--:|--:|
| iter04 | 0.497 | 0.0191 | 145 | 0.483 | 0.0164 |
| R1 | 0.453 | 0.0255 | 145 | 0.517 | 0.0142 |
| R2 | 0.497 | 0.0242 | 145 | 0.552 | 0.0139 |

**Washout.** iter04's raw prior is wrong on every hard state (top1 0.000) yet its NMCTS@200 already
reaches **0.497** — search recovers the decision from a bad prior. R2's much better prior (0.179)
reaches the **same 0.497**: the policy gain is **redundant with what search already provides** at
production depth. (R1 is *worse*, 0.453.) Only the endgame subset moves (R2 0.552 vs iter04 0.483) —
the autopsy's collapse region, where search has the least room to compensate.

## Stage 6 — game screen: R2 vs h6400_v2.9 (n=126, paired, sims=200 c=3.0 rs=0.25, v2.9 leaf)

| net (vs h6400_v2.9) | n | W/L/D | WR | elo | paired margin | paired z |
|---|--:|--:|--:|--:|--:|--:|
| **R2 (repaired)** | 126 | 51/74/1 | **0.409** | **−64** | **−11.7** | −4.77 |
| iter04 (baseline, results.csv) | 400 | 182/212/6 | 0.463 | −26.1 | −5.09 | −4.67 |

**The repair does NOT convert — it is, if anything, harmful.** R2 (WR 0.409) is *below* the iter04
baseline (0.463) it was fine-tuned from; the eval's own read: *"net LOSES to pure heuristic search at
matched compute → the policy is not adding strength over the leaf+search."* The −0.054 gap to iter04
is ~1σ (n=126 vs n=400), so formally **R2 ≤ iter04, definitely not better**. The held-out prior gain
(top1 0→0.18) is real but (a) redundant at the root under search and (b) bought at a broad-distribution
cost (ordinary top1 1.0→0.95) that search does *not* wash out in full play.

## Synthesis

| stage | signal | verdict |
|---|---|---|
| 2 gate | high-contrast signal density | **abundant** (gap≥0.02 = 37%, regret≥0.02 = 43%, phase-balanced) |
| 5 prior | held-out hard top1 / regret | **learns + generalises** (0→0.18 / −27%); endgame 0→0.17 |
| 5b NMCTS | searched move vs h6400 | **washout** (R2 = iter04 = 0.497; endgame-only moves) |
| 6 games | WR vs h6400 | **no conversion** (0.409 ≤ iter04 0.463) |

The high-contrast decision signal **exists and is learnable** (refuting "no signal") — but distilling
it onto the **policy** does not translate to strength, because **search already extracts the
decision-relevant move from the existing prior**. The failed flywheel is **not** a policy-exposure
problem; the binding constraint is **value/search** (RoD2 autopsy blocker #2). See
[HIGH_GAP_DECISION.md](HIGH_GAP_DECISION.md).
