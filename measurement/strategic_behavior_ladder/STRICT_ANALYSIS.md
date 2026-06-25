# Strict high-precision motifs — analysis

positions: 312

## Opportunity counts (raw + distinct games)

| motif | raw | distinct games | by opp-class (weak/mid/strong) |
|---|---|---|---|
| MUST_BLOCK_CITY | 12 | 9 | 0/2/10 |
| MUST_NOT_FEED | 115 | 67 | 9/43/63 |
| MUST_PUNISH_WEAK | 179 | 104 | 64/56/59 |
| HIGH_VALUE_FARM_CLAIM_REFINED | 95 | 63 | 28/33/34 |

## Part C — take rate by agent (opportunity-normalized)


**MUST_BLOCK_CITY**

| agent | all | vs weak | vs strong | competitive(|m|≤20) | already-won(m>20) |
|---|---|---|---|---|---|
| random | 8% (1/12) | -- | 10% (1/10) | 8% (1/12) | -- |
| greedy | 33% (4/12) | -- | 30% (3/10) | 33% (4/12) | -- |
| h200 | 50% (6/12) | -- | 40% (4/10) | 50% (6/12) | -- |
| h800 | 50% (6/12) | -- | 40% (4/10) | 50% (6/12) | -- |
| h3200 | 50% (6/12) | -- | 40% (4/10) | 50% (6/12) | -- |
| h6400 | 50% (6/12) | -- | 40% (4/10) | 50% (6/12) | -- |
| rod1 | 42% (5/12) | -- | 40% (4/10) | 42% (5/12) | -- |

**MUST_NOT_FEED**

| agent | all | vs weak | vs strong | competitive(|m|≤20) | already-won(m>20) |
|---|---|---|---|---|---|
| random | 77% (88/115) | 78% (7/9) | 73% (46/63) | 72% (65/90) | 100% (6/6) |
| greedy | 85% (98/115) | 100% (9/9) | 81% (51/63) | 83% (75/90) | 100% (6/6) |
| h200 | 85% (98/115) | 100% (9/9) | 79% (50/63) | 83% (75/90) | 100% (6/6) |
| h800 | 85% (98/115) | 100% (9/9) | 79% (50/63) | 83% (75/90) | 100% (6/6) |
| h3200 | 85% (98/115) | 100% (9/9) | 79% (50/63) | 83% (75/90) | 100% (6/6) |
| h6400 | 85% (98/115) | 100% (9/9) | 79% (50/63) | 83% (75/90) | 100% (6/6) |
| rod1 | 82% (94/115) | 89% (8/9) | 76% (48/63) | 81% (73/90) | 83% (5/6) |

**MUST_PUNISH_WEAK**

| agent | all | vs weak | vs strong | competitive(|m|≤20) | already-won(m>20) |
|---|---|---|---|---|---|
| random | 15% (26/179) | 12% (8/64) | 15% (9/59) | 15% (26/170) | -- |
| greedy | 55% (99/179) | 61% (39/64) | 58% (34/59) | 54% (91/170) | -- |
| h200 | 89% (159/179) | 86% (55/64) | 85% (50/59) | 88% (150/170) | -- |
| h800 | 93% (167/179) | 92% (59/64) | 90% (53/59) | 93% (158/170) | -- |
| h3200 | 92% (164/179) | 91% (58/64) | 90% (53/59) | 91% (155/170) | -- |
| h6400 | 92% (165/179) | 91% (58/64) | 90% (53/59) | 92% (156/170) | -- |
| rod1 | 84% (151/179) | 81% (52/64) | 78% (46/59) | 86% (146/170) | -- |

**HIGH_VALUE_FARM_CLAIM_REFINED**

| agent | all | vs weak | vs strong | competitive(|m|≤20) | already-won(m>20) |
|---|---|---|---|---|---|
| random | 25% (24/95) | 21% (6/28) | 26% (9/34) | 26% (24/93) | -- |
| greedy | 13% (12/95) | 14% (4/28) | 18% (6/34) | 12% (11/93) | -- |
| h200 | 86% (82/95) | 82% (23/28) | 79% (27/34) | 86% (80/93) | -- |
| h800 | 89% (85/95) | 89% (25/28) | 82% (28/34) | 89% (83/93) | -- |
| h3200 | 87% (83/95) | 86% (24/28) | 82% (28/34) | 87% (81/93) | -- |
| h6400 | 89% (85/95) | 86% (24/28) | 85% (29/34) | 89% (83/93) | -- |
| rod1 | 82% (78/95) | 71% (20/28) | 79% (27/34) | 83% (77/93) | -- |

## Part D — RoD1 vs h6400 on identical strict positions

| motif | h6400 | rod1 | Δ | h6400-take/rod1-miss (competitive / padding) |
|---|---|---|---|---|
| MUST_BLOCK_CITY | 50% (6/12) | 42% (5/12) | +8pp | 1 (1 comp / 0 padding) |
| MUST_NOT_FEED | 85% (98/115) | 82% (94/115) | +3pp | 5 (3 comp / 2 padding) |
| MUST_PUNISH_WEAK | 92% (165/179) | 84% (151/179) | +8pp | 14 (10 comp / 4 padding) |
| HIGH_VALUE_FARM_CLAIM_REFINED | 89% (85/95) | 82% (78/95) | +7pp | 7 (6 comp / 1 padding) |

## Part E — pre-move-controlled outcome sanity (ACTUAL mover; no collider)

win% = P(mover wins). Stratified by PRE-move margin. (thin cells ⚠)


**MUST_BLOCK_CITY** (n=12)
| stratum | take win% (n) | miss win% (n) | Δwin | Δmargin |
|---|---|---|---|---|
| all | 50% (4) | 25% (8) | +25pp | +23.1 ⚠ |
| behind (≤-5) | nan% (0) | 0% (5) | +nanpp | +nan ⚠ |
| even (-4..4) | 0% (1) | 0% (1) | +0pp | -7.0 ⚠ |
| ahead (≥5) | 67% (3) | 100% (2) | -33pp | -0.5 ⚠ |
| vs weak | nan% (0) | nan% (0) | +nanpp | +nan ⚠ |
| vs strong | 33% (3) | 14% (7) | +19pp | +19.9 ⚠ |

**MUST_NOT_FEED** (n=115)
| stratum | take win% (n) | miss win% (n) | Δwin | Δmargin |
|---|---|---|---|---|
| all | 32% (95) | 20% (20) | +12pp | +4.4 |
| behind (≤-5) | 7% (43) | 0% (10) | +7pp | -0.6 ⚠ |
| even (-4..4) | 33% (30) | 0% (4) | +33pp | +5.9 ⚠ |
| ahead (≥5) | 77% (22) | 67% (6) | +11pp | +18.5 ⚠ |
| vs weak | 62% (8) | 0% (1) | +62pp | +45.4 ⚠ |
| vs strong | 20% (49) | 21% (14) | -1pp | -2.9 ⚠ |

**MUST_PUNISH_WEAK** (n=179)
| stratum | take win% (n) | miss win% (n) | Δwin | Δmargin |
|---|---|---|---|---|
| all | 68% (118) | 41% (61) | +27pp | +34.9 |
| behind (≤-5) | 28% (18) | 11% (19) | +17pp | +38.0 |
| even (-4..4) | 71% (68) | 40% (30) | +31pp | +30.3 |
| ahead (≥5) | 84% (32) | 92% (12) | -7pp | +4.3 ⚠ |
| vs weak | 98% (45) | 79% (19) | +19pp | +27.1 |
| vs strong | 53% (38) | 24% (21) | +29pp | +46.7 |

**HIGH_VALUE_FARM_CLAIM_REFINED** (n=95)
| stratum | take win% (n) | miss win% (n) | Δwin | Δmargin |
|---|---|---|---|---|
| all | 53% (45) | 46% (50) | +7pp | +7.8 |
| behind (≤-5) | 0% (8) | 8% (12) | -8pp | +17.2 ⚠ |
| even (-4..4) | 57% (21) | 42% (26) | +15pp | +4.5 |
| ahead (≥5) | 75% (16) | 92% (12) | -17pp | -15.0 ⚠ |
| vs weak | 91% (11) | 88% (17) | +3pp | +0.1 ⚠ |
| vs strong | 43% (23) | 27% (11) | +16pp | +33.0 ⚠ |
