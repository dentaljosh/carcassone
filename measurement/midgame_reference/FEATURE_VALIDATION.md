# Phase 2 — Feature Validation (guard against the pre-scoring bug)

> The v1 pre-tool audit read per-action deltas one half-move too early, so every delta was
> CONSTANT across legal actions (an artifact). This file proves the midgame features VARY
> across legal actions where they should — by showing, for 25 randomly-sampled positions,
> how many distinct values each feature takes across that position's legal tile actions,
> plus concrete before/after action examples. **FACT** (computed from the dataset).

## Per-position feature variation (distinct values across legal actions)

| position_id | band | n_act | v27 | imm_net | best_meeple | aff_min_open | scarcity | owner |
|---|---|---|---|---|---|---|---|---|
| hybrid_8_3200_s3503000037_K28 | mid | 20 | 2 | 1 | 1 | 2 | 1 | 2 |
| iter8_s3501000031_K10 | pre_endgame | 28 | 6 | 1 | 1 | 3 | 2 | 4 |
| iter8_s3501000021_K10 | pre_endgame | 54 | 2 | 1 | 1 | 1 | 1 | 1 |
| hybrid_8_3200_s3503000043_K10 | pre_endgame | 30 | 1 | 1 | 1 | 2 | 2 | 1 |
| iter8_s3501000025_K28 | mid | 33 | 2 | 2 | 2 | 1 | 1 | 1 |
| iter8_s3501000029_K40 | early_mid | 21 | 5 | 3 | 3 | 2 | 2 | 3 |
| hybrid_8_3200_s3503000039_K40 | early_mid | 26 | 3 | 1 | 1 | 4 | 1 | 3 |
| greedy_s3500000028_K10 | pre_endgame | 30 | 2 | 1 | 1 | 4 | 3 | 2 |
| heur3200_s3502000013_K28 | mid | 35 | 8 | 3 | 3 | 3 | 2 | 3 |
| iter8_s3501000006_K52 | opening | 11 | 6 | 3 | 3 | 4 | 2 | 4 |
| iter8_s3501000045_K10 | pre_endgame | 38 | 4 | 2 | 2 | 3 | 2 | 1 |
| greedy_s3500000026_K28 | mid | 28 | 3 | 1 | 1 | 3 | 1 | 2 |
| greedy_s3500000015_K52 | opening | 17 | 4 | 2 | 2 | 1 | 1 | 1 |
| heur3200_s3502000031_K52 | opening | 18 | 2 | 1 | 1 | 1 | 1 | 1 |
| iter8_s3501000034_K10 | pre_endgame | 27 | 2 | 1 | 1 | 3 | 2 | 2 |
| greedy_s3500000013_K16 | late_mid | 39 | 4 | 1 | 1 | 3 | 2 | 2 |
| hybrid_8_3200_s3503000042_K52 | opening | 28 | 4 | 1 | 1 | 2 | 1 | 4 |
| iter8_s3501000031_K52 | opening | 21 | 6 | 2 | 2 | 2 | 1 | 3 |
| greedy_s3500000026_K16 | late_mid | 50 | 3 | 1 | 1 | 1 | 1 | 1 |
| iter8_s3501000035_K16 | late_mid | 30 | 3 | 1 | 1 | 2 | 2 | 1 |
| hybrid_8_3200_s3503000027_K28 | mid | 31 | 2 | 1 | 1 | 1 | 1 | 1 |
| hybrid_8_3200_s3503000027_K10 | pre_endgame | 33 | 4 | 1 | 1 | 2 | 2 | 1 |
| greedy_s3500000036_K28 | mid | 59 | 5 | 2 | 2 | 4 | 2 | 2 |
| iter8_s3501000022_K40 | early_mid | 19 | 4 | 2 | 2 | 3 | 2 | 2 |
| hybrid_8_3200_s3503000016_K10 | pre_endgame | 45 | 1 | 1 | 1 | 1 | 1 | 1 |

(Each cell = # distinct values that feature takes across the position's legal actions. >1 everywhere a feature is meaningful ⇒ NOT the constant-delta artifact.)

## Concrete before/after action contrasts (3 positions, 2 actions each)

### hybrid_8_3200_s3503000037_K28 (band=mid, k=28, in_hand=city_bottom_road, n_act=20)

| action | type | v27 | imm_net | best_meeple | meeple_Δ | completion | aff_min_open | scarcity | city_open_Δ | owner |
|---|---|---|---|---|---|---|---|---|---|---|
| 756 (worst-v27) | tile | -6 | 0 | 0 | 0 | False | 3 | many | -3 | empty |
| 1036 (best-v27) | tile | -4 | 0 | 0 | 0 | False | 2 | many | -1 | opp |

### iter8_s3501000031_K10 (band=pre_endgame, k=10, in_hand=city_bottom_road_shield, n_act=28)

| action | type | v27 | imm_net | best_meeple | meeple_Δ | completion | aff_min_open | scarcity | city_open_Δ | owner |
|---|---|---|---|---|---|---|---|---|---|---|
| 1347 (worst-v27) | tile | 3 | 0 | 0 | 0 | False | 2 | moderate | 3 | shared |
| 828 (best-v27) | tile | 10 | 0 | 0 | 0 | False | 1 | many | 0 | self |

### iter8_s3501000021_K10 (band=pre_endgame, k=10, in_hand=straight_road, n_act=54)

| action | type | v27 | imm_net | best_meeple | meeple_Δ | completion | aff_min_open | scarcity | city_open_Δ | owner |
|---|---|---|---|---|---|---|---|---|---|---|
| 745 (worst-v27) | tile | 11 | 0 | 0 | 0 | False | 0 | none_open | 0 | empty |
| 1830 (best-v27) | tile | 12 | 0 | 0 | 0 | False | 0 | none_open | 0 | empty |

