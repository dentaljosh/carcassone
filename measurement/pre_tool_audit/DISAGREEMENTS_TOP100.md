# Phase 4 — iter8 Disagreement Audit (top 100)

> High-value positions where iter8's move is NOT solver-optimal. Reference 'better' move = an exact-optimal action (K=2) or heur@3200's better move (K=3/K=4). Categories are **first-pass diagnostic labels, NOT proven** (prompt §Phase4). Full table: [DISAGREEMENT_CATEGORIES.csv](DISAGREEMENT_CATEGORIES.csv).

**Totals:** 158 positions where iter8 is sub-optimal (of 408 labelled). iter8-correct-but-heur@3200-misses: 12.

**By K:** {4: 82, 2: 47, 3: 29}  ·  **By source:** {'greedy_selfplay': 100, 'hybrid:8:3200_selfplay': 21, 'heur@3200_selfplay': 20, 'iter8_selfplay': 17}


## The load-bearing split — would iter8's OWN leaf (v2.7) have caught the miss?

| v2.7 axis | all iter8 misses | top-100 |
|---|---|---|
| v2.7-rankable | 8 | 6 |
| iter8-move-v2.7-preferred | 4 | 4 |
| no-stronger-ref(both-miss) | 69 | 44 |
| beyond-v2.7 | 77 | 46 |

*'v2.7-rankable' = the v2.7 leaf already scores the better move higher (by >2) — iter8 deviated from a signal it already consumes. 'beyond-v2.7' / 'iter8-move-v2.7-preferred' = v2.7 ALSO mis-ranks it (a new exact signal would be needed).*


## Mechanism (first-pass)

| mechanism | all | top-100 |
|---|---|---|
| structural-or-farm | 82 | 49 |
| completion | 7 | 7 |
| no-stronger-ref(both-miss) | 69 | 44 |

## Top 30 disagreements (highest iter8 regret)

| # | position | K | src | tile | legalN | sharp | iter8 reg | iter8 v27 | ref v27 | mech | v2.7 axis |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | heur3200_s3502000036_k4 | 4 | heur@3200 | three_split_road | 35 |  | 19 | -17 | -17 | structural-or-farm | beyond-v2.7 |
| 2 | iter8_s3501000033_k4 | 4 | iter8 | city_diagonal_top_left | 44 | Y | 13 | 9 | None | no-stronger-ref(both-miss) | no-stronger-ref(both-miss) |
| 3 | greedy_s3500000008_k4 | 4 | greedy | city_top_right | 42 | Y | 12 | 26 | 32 | completion | v2.7-rankable |
| 4 | hybrid_8_3200_s3503000027_k4 | 4 | hybrid:8:3200 | city_diagonal_top_righ | 28 | Y | 12 | -74 | -73 | structural-or-farm | beyond-v2.7 |
| 5 | hybrid_8_3200_s3503000015_k4 | 4 | hybrid:8:3200 | chapel | 60 |  | 12 | 25 | 25 | structural-or-farm | beyond-v2.7 |
| 6 | iter8_s3501000009_k4 | 4 | iter8 | city_top_road_bend_lef | 43 | Y | 11 | 32 | None | no-stronger-ref(both-miss) | no-stronger-ref(both-miss) |
| 7 | greedy_s3500000032_k4 | 4 | greedy | bent_road | 49 | Y | 9 | -10 | None | no-stronger-ref(both-miss) | no-stronger-ref(both-miss) |
| 8 | heur3200_s3502000028_k4 | 4 | heur@3200 | city_diagonal_top_righ | 48 | Y | 9 | 5 | None | no-stronger-ref(both-miss) | no-stronger-ref(both-miss) |
| 9 | g3200000129_k2 | 2 | greedy | bent_road | 76 |  | 9 | 19 | 19 | structural-or-farm | beyond-v2.7 |
| 10 | heur3200_s3502000034_k4 | 4 | heur@3200 | straight_road | 46 |  | 9 | 11 | None | no-stronger-ref(both-miss) | no-stronger-ref(both-miss) |
| 11 | greedy_s3500000018_k4 | 4 | greedy | bent_road | 50 | Y | 8 | -15 | None | no-stronger-ref(both-miss) | no-stronger-ref(both-miss) |
| 12 | greedy_s3500000009_k4 | 4 | greedy | crossroads | 24 |  | 8 | -10 | None | no-stronger-ref(both-miss) | no-stronger-ref(both-miss) |
| 13 | g3200000022_k2 | 2 | greedy | bent_road | 50 |  | 6 | 25 | 31 | structural-or-farm | v2.7-rankable |
| 14 | g3200000022_k3 | 3 | greedy | city_bottom_grass_shie | 36 |  | 6 | -23 | None | no-stronger-ref(both-miss) | no-stronger-ref(both-miss) |
| 15 | g3200000059_k3 | 3 | greedy | three_split_road | 50 |  | 6 | 0 | None | no-stronger-ref(both-miss) | no-stronger-ref(both-miss) |
| 16 | g3200000075_k3 | 3 | greedy | crossroads | 28 |  | 6 | 8 | 9 | completion | beyond-v2.7 |
| 17 | hybrid_8_3200_s3503000022_k4 | 4 | hybrid:8:3200 | city_diagonal_top_righ | 34 |  | 6 | 8 | None | no-stronger-ref(both-miss) | no-stronger-ref(both-miss) |
| 18 | greedy_s3500000016_k4 | 4 | greedy | city_bottom_road_shiel | 37 | Y | 5 | 19 | 20 | completion | beyond-v2.7 |
| 19 | heur3200_s3502000031_k4 | 4 | heur@3200 | city_diagonal_top_righ | 29 | Y | 5 | 17 | None | no-stronger-ref(both-miss) | no-stronger-ref(both-miss) |
| 20 | g3200000092_k2 | 2 | greedy | city_top | 71 |  | 5 | 19 | 15 | structural-or-farm | iter8-move-v2.7-preferred |
| 21 | greedy_s3500000007_k4 | 4 | greedy | city_top_right | 44 |  | 5 | -2 | -3 | structural-or-farm | beyond-v2.7 |
| 22 | greedy_s3500000002_k4 | 4 | greedy | bent_road | 72 | Y | 4 | -1 | None | no-stronger-ref(both-miss) | no-stronger-ref(both-miss) |
| 23 | heur3200_s3502000010_k4 | 4 | heur@3200 | bent_road_flowers | 53 | Y | 4 | -15 | -14 | structural-or-farm | beyond-v2.7 |
| 24 | heur3200_s3502000045_k4 | 4 | heur@3200 | city_top_road_bend_lef | 44 | Y | 4 | 1 | None | no-stronger-ref(both-miss) | no-stronger-ref(both-miss) |
| 25 | hybrid_8_3200_s3503000004_k4 | 4 | hybrid:8:3200 | city_diagonal_top_righ | 37 | Y | 4 | -6 | None | no-stronger-ref(both-miss) | no-stronger-ref(both-miss) |
| 26 | iter8_s3501000048_k4 | 4 | iter8 | city_bottom_grass_flow | 21 | Y | 4 | 16 | None | no-stronger-ref(both-miss) | no-stronger-ref(both-miss) |
| 27 | g3200000099_k2 | 2 | greedy | three_split_road | 47 |  | 4 | -3 | -3 | structural-or-farm | beyond-v2.7 |
| 28 | g3200000121_k2 | 2 | greedy | city_top_crossroads | 24 |  | 4 | 1 | 1 | structural-or-farm | beyond-v2.7 |
| 29 | g3200000011_k3 | 3 | greedy | bent_road | 47 |  | 4 | 27 | 27 | completion | beyond-v2.7 |
| 30 | g3200000023_k3 | 3 | greedy | city_top_road_bend_lef | 32 |  | 4 | -13 | None | no-stronger-ref(both-miss) | no-stronger-ref(both-miss) |

## A few worked examples (iter8 misses)

- **heur3200_s3502000036_k4** (K=4, src=heur@3200, tile=`three_split_road`, legal_n=35, n_optimal=7): iter8 played action 1840 (regret **19**, v27=-17, imm_net=0, meeple Δ=0); better action 1033 (v27=-17, imm_net=0, meeple Δ=0, completes=False). → mechanism: *structural-or-farm*, axis: *beyond-v2.7*. raw: `/mnt/c/carc-shared/l23_k4_expand_probe/heur3200_s3502000036_k4.json`
- **iter8_s3501000033_k4** (K=4, src=iter8, tile=`city_diagonal_top_left_road`, legal_n=44, n_optimal=1): iter8 played action 1538 (regret **13**, v27=9, imm_net=0, meeple Δ=0); better action None (v27=None, imm_net=0, meeple Δ=None, completes=None). → mechanism: *no-stronger-ref(both-miss)*, axis: *no-stronger-ref(both-miss)*. raw: `/mnt/c/carc-shared/l23_k4_expand_probe/iter8_s3501000033_k4.json`
- **greedy_s3500000008_k4** (K=4, src=greedy, tile=`city_top_right`, legal_n=42, n_optimal=1): iter8 played action 1285 (regret **12**, v27=26, imm_net=0, meeple Δ=0); better action 1527 (v27=32, imm_net=18, meeple Δ=1, completes=True). → mechanism: *completion*, axis: *v2.7-rankable*. raw: `/mnt/c/carc-shared/l23_k4_expand_probe/greedy_s3500000008_k4.json`
- **hybrid_8_3200_s3503000027_k4** (K=4, src=hybrid:8:3200, tile=`city_diagonal_top_right`, legal_n=28, n_optimal=1): iter8 played action 1534 (regret **12**, v27=-74, imm_net=0, meeple Δ=0); better action 1460 (v27=-73, imm_net=0, meeple Δ=0, completes=False). → mechanism: *structural-or-farm*, axis: *beyond-v2.7*. raw: `/mnt/c/carc-shared/l23_k4_expand_probe/hybrid_8_3200_s3503000027_k4.json`
- **hybrid_8_3200_s3503000015_k4** (K=4, src=hybrid:8:3200, tile=`chapel`, legal_n=60, n_optimal=4): iter8 played action 928 (regret **12**, v27=25, imm_net=0, meeple Δ=0); better action 1360 (v27=25, imm_net=0, meeple Δ=0, completes=False). → mechanism: *structural-or-farm*, axis: *beyond-v2.7*. raw: `/mnt/c/carc-shared/l23_k4_expand_probe/hybrid_8_3200_s3503000015_k4.json`

## iter8 right, heur@3200 wrong (learned-policy strengths) — top 10

| position | K | src | iter8 reg | heur@3200 reg | iter8 v27 | tile |
|---|---|---|---|---|---|---|
| g3200000123_k2 | 2 | greedy | 0 | 6 | 38 | city_top_flowers |
| g3200000066_k2 | 2 | greedy | 0 | 4 | -6 | city_top_road_bend_right |
| g3200000003_k2 | 2 | greedy | 0 | 3 | 43 | chapel_with_road |
| g3200000100_k2 | 2 | greedy | 0 | 3 | 14 | city_top_left_flowers |
| g3200000104_k2 | 2 | greedy | 0 | 2 | 5 | three_split_road |
| g3200000043_k3 | 3 | greedy | 0 | 2 | -11 | bent_road |
| g3200000063_k3 | 3 | greedy | 0 | 2 | 26 | city_diagonal_top_right |
| g3200000067_k2 | 2 | greedy | 0 | 1 | -9 | city_top |
| g3200000017_k3 | 3 | greedy | 0 | 1 | 3 | city_top_road_bend_right |
| g3200000029_k3 | 3 | greedy | 0 | 1 | 29 | city_top_straight_road |
