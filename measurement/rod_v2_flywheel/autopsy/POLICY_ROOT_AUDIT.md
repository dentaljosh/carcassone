# Stage A-lite — Policy Root Audit (RoD2, v2.9 rulers)

Fixed set: multiphase_positions.jsonl · n_valid=400 · h3200≠h6400 disagreement subset n=111 (28%)

Question: on the disagreement subset, does each net pick the **h6400** (deep) move, the **h3200** (shallow) move, or **neither** (diffuse)? `lean = P(h6400) − P(h3200)`; lean>0 = moving toward deep search.


## Overall top-1 agreement (all valid positions)

| net | prior=h6400 | prior=h3200 | NMCTS=h6400 | NMCTS=h3200 |
|---|--:|--:|--:|--:|
| rod1 | 0.225 | 0.228 | 0.512 | 0.525 |
| iter04 | 0.263 | 0.280 | 0.477 | 0.502 |
| iter06 | 0.260 | 0.268 | 0.468 | 0.460 |

## Disagreement subset (h3200≠h6400, n=111) — the crux

| net | signal | P(h6400) | P(h3200) | P(neither) | lean (h6400−h3200) |
|---|---|--:|--:|--:|--:|
| rod1 | prior | 0.108 | 0.117 | 0.775 | -0.009 |
| rod1 | NMCTS@200 | 0.198 | 0.243 | 0.559 | -0.045 |
| iter04 | prior | 0.081 | 0.144 | 0.775 | -0.063 |
| iter04 | NMCTS@200 | 0.153 | 0.243 | 0.604 | -0.090 |
| iter06 | prior | 0.099 | 0.126 | 0.775 | -0.027 |
| iter06 | NMCTS@200 | 0.216 | 0.189 | 0.595 | +0.027 |

## Trajectory (prior lean on disagreement subset)

RoD1 -0.009 → iter04 -0.063 → iter06 -0.027

Δlean(iter06 − RoD1) = -0.018. (|Δ| within ~0.095 ≈ 1/√n is noise.)


## Per-phase disagreement lean (prior; lean = P(h6400) − P(h3200))

| phase | n_dis | rod1 | iter04 | iter06 | rod1 Pneither | iter06 Pneither |
|---|--:|--:|--:|--:|--:|--:|
| opening | 9 | +0.000 | -0.111 | -0.111 | 0.556 | 0.667 |
| late_mid | 10 | +0.000 | -0.100 | +0.100 | 1.000 | 0.900 |
| pre_endgame | 31 | +0.097 | +0.000 | +0.065 | 0.774 | 0.742 |
| endgame | 34 | -0.147 | -0.088 | -0.059 | 0.794 | 0.824 |
| midgame | 27 | +0.037 | -0.074 | -0.111 | 0.741 | 0.741 |

## Per-phase top-1 prior agreement with each ruler (all positions, not just disagreements)

| phase | n | rod1≡h3200 | rod1≡h6400 | iter06≡h3200 | iter06≡h6400 |
|---|--:|--:|--:|--:|--:|
| opening | 44 | 0.455 | 0.455 | 0.477 | 0.455 |
| late_mid | 44 | 0.250 | 0.250 | 0.318 | 0.341 |
| pre_endgame | 89 | 0.191 | 0.225 | 0.270 | 0.292 |
| endgame | 134 | 0.134 | 0.097 | 0.119 | 0.104 |
| midgame | 89 | 0.281 | 0.292 | 0.360 | 0.326 |
