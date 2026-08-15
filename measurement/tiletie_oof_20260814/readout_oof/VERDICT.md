# TILE-TIE PRICING — READ-OUT

**Status: tiletie-oof dev slice / OUT-OF-FAMILY tier1-greedy — COMPLETE for the scope declared below.**

Pre-registration: [DESIGN.md](../../tiletie_pricing_20260812/DESIGN.md) — every estimator below is §4, implemented before any record was read. Generated `2026-08-15T01:36:39Z`.

## 1. Completion accounting

- planned positions in scope: **502** · fully scored: **502** · partially scored: **0** · absent: **0**
- positions ENTERING the statistics: **502** (`include_partial_arms=False`)

| profile | planned | complete | partial | absent |
|---|---|---|---|---|
| app_aug2 | 3 | 3 | 0 | 0 |
| fixed_v1 | 28 | 28 | 0 | 0 |
| walled | 471 | 471 | 0 | 0 |

| stratum | planned | complete | partial | absent |
|---|---|---|---|---|
| e4 | 35 | 35 | 0 | 0 |
| selfplay | 467 | 467 | 0 | 0 |

**What is missing, stated loudly:** COMPLETE for the profiles in scope — every planned leg record is present.

## 2. The §0.A analytic zeros (all-transposition positions)

Count source: per-stratum, from the full-supply plan /home/doctor/projects/carcassone/.claude/worktrees/agent-a1badefaaed4b6d69/measurement/tiletie_pricing_20260812/positions/POSITIONS_PLAN.json + the dropped index

| stratum | qualifying | built | dropped (analytic 0) | of which played-action INSIDE tie set | p_drop | scale = 1−p_drop | scale (zeros_strict) |
|---|---|---|---|---|---|---|---|
| e4 | 495 | 380 | 115 | 91 | 0.2323 | 0.7677 | 0.8162 |
| selfplay | 932 | 673 | 259 | 211 | 0.2779 | 0.7221 | 0.7736 |

Every all-transposition position contributes **exactly 0 with zero variance** (§6 threat 3), so the population mean is `(1 − p_drop) × mean(discriminable)` exactly. ⚠️ On the rows whose played action lies OUTSIDE the tie set the analytic zero covers the **tie-set arms only**, so S2 carries `zeros_strict` as a per-row sensitivity (see §6 of this read-out); spread and S2b are unaffected.

## 3. Integrity (§2.1 CRN witness)

- `values_a_drift`: **0**
- `seed_drift`: **0**
- `crn_unverified`: **0**
- `checksum_failed`: **0**
- `arm_index_mismatch`: **0**
- `zero_distinct_afterstates`: **0**

`values_a_drift == 0` is the §2.1 witness: the reference arm is re-scored in every leg under identical (world, playout) seeds, so any drift would VOID the run.

## 4. The pre-registered statistics

All estimates are **pts** (S1b/S2/S2b) or **pts²** (S1a), cluster-robust on `root_id`; CIs are root-resampling bootstrap, 20,000 reps, seed 20260812.

### pooled  (n=502 positions, 277 roots, champ arm scored on 502)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 502 | +4.2208 | +0.7047 | [+2.9488, +5.6589] | +5.99 |
| S1a σ²_arm — all (zeros added) [pts²] | 502 | +3.0720 | +0.5112 | [+2.1491, +4.1129] | +6.01 |
| S1b cross-fit gap G — discriminable [pts] | 502 | +1.6469 | +0.2364 | [+1.1872, +2.1063] | +6.97 |
| S1b cross-fit gap G — all [pts] | 502 | +1.1984 | +0.1720 | [+0.8642, +1.5336] | +6.97 |
| S2 headroom_J4 — discriminable [pts] | 502 | +0.8207 | +0.1909 | [+0.4500, +1.1948] | +4.30 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 502 | +0.5987 | +0.1387 | [+0.3296, +0.8716] | +4.32 |
| S2 headroom_J4 — all, zeros_strict | 502 | +0.6406 | +0.1485 | [+0.3524, +0.9323] | +4.31 |
| S2b leaf regret — discriminable [pts] | 502 | +0.9473 | +0.1905 | [+0.5835, +1.3299] | +4.97 |
| S2b leaf regret — all [pts] | 502 | +0.6867 | +0.1381 | [+0.4228, +0.9636] | +4.97 |
| *(audit only, never quoted)* naive range | 502 | +4.3858 | +0.1712 | [+4.0618, +4.7211] | +25.62 |
| *(audit only, never quoted)* naive champ regret | 502 | +2.1874 | +0.1513 | [+1.8957, +2.4882] | +14.46 |
| *(diagnostic)* S1b parity-swapped | 502 | +1.5867 | +0.2537 | [+1.0921, +2.0807] | +6.25 |
| *(diagnostic)* S2 parity-swapped | 502 | +0.6956 | +0.2143 | [+0.2750, +1.1165] | +3.25 |

### capped_only  (n=94 positions, 84 roots, champ arm scored on 94)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 94 | +3.6709 | +1.1165 | [+1.6582, +5.9938] | +3.29 |
| S1a σ²_arm — all (zeros added) [pts²] | 94 | +2.7078 | +0.8334 | [+1.2111, +4.4444] | +3.25 |
| S1b cross-fit gap G — discriminable [pts] | 94 | +1.8238 | +0.5413 | [+0.7833, +2.8822] | +3.37 |
| S1b cross-fit gap G — all [pts] | 94 | +1.3313 | +0.3960 | [+0.5719, +2.1096] | +3.36 |
| S2 headroom_J4 — discriminable [pts] | 94 | +0.9235 | +0.4763 | [+0.0268, +1.8677] | +1.94 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 94 | +0.6755 | +0.3483 | [+0.0210, +1.3672] | +1.94 |
| S2 headroom_J4 — all, zeros_strict | 94 | +0.7225 | +0.3725 | [+0.0223, +1.4625] | +1.94 |
| S2b leaf regret — discriminable [pts] | 94 | +1.2832 | +0.4209 | [+0.4822, +2.1050] | +3.05 |
| S2b leaf regret — all [pts] | 94 | +0.9235 | +0.3044 | [+0.3437, +1.5178] | +3.03 |
| *(audit only, never quoted)* naive range | 94 | +5.3258 | +0.4138 | [+4.5289, +6.1485] | +12.87 |
| *(audit only, never quoted)* naive champ regret | 94 | +2.5974 | +0.3892 | [+1.8747, +3.3884] | +6.67 |
| *(diagnostic)* S1b parity-swapped | 94 | +2.1582 | +0.6018 | [+1.0186, +3.3345] | +3.59 |
| *(diagnostic)* S2 parity-swapped | 94 | +0.8710 | +0.5265 | [-0.1414, +1.9122] | +1.65 |

### phase:early  (n=189 positions, 147 roots, champ arm scored on 189)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 189 | +2.0728 | +1.0281 | [+0.1095, +4.1061] | +2.02 |
| S1a σ²_arm — all (zeros added) [pts²] | 189 | +1.5440 | +0.7528 | [+0.1058, +3.0356] | +2.05 |
| S1b cross-fit gap G — discriminable [pts] | 189 | +0.8707 | +0.4531 | [-0.0102, +1.7696] | +1.92 |
| S1b cross-fit gap G — all [pts] | 189 | +0.6458 | +0.3316 | [+0.0031, +1.3009] | +1.95 |
| S2 headroom_J4 — discriminable [pts] | 189 | +0.5602 | +0.3772 | [-0.1674, +1.3183] | +1.48 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 189 | +0.4129 | +0.2743 | [-0.1177, +0.9631] | +1.51 |
| S2 headroom_J4 — all, zeros_strict | 189 | +0.4412 | +0.2936 | [-0.1263, +1.0303] | +1.50 |
| S2b leaf regret — discriminable [pts] | 189 | +0.5020 | +0.3457 | [-0.1613, +1.1969] | +1.45 |
| S2b leaf regret — all [pts] | 189 | +0.3736 | +0.2515 | [-0.1063, +0.8786] | +1.49 |
| *(audit only, never quoted)* naive range | 189 | +5.1564 | +0.2651 | [+4.6467, +5.6828] | +19.45 |
| *(audit only, never quoted)* naive champ regret | 189 | +2.8087 | +0.2625 | [+2.3141, +3.3357] | +10.70 |
| *(diagnostic)* S1b parity-swapped | 189 | +0.6118 | +0.4961 | [-0.3773, +1.5690] | +1.23 |
| *(diagnostic)* S2 parity-swapped | 189 | +0.5731 | +0.4128 | [-0.2323, +1.3706] | +1.39 |

### phase:late  (n=147 positions, 126 roots, champ arm scored on 147)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 147 | +4.2002 | +1.3135 | [+2.1730, +7.1822] | +3.20 |
| S1a σ²_arm — all (zeros added) [pts²] | 147 | +3.0457 | +0.9511 | [+1.5754, +5.2079] | +3.20 |
| S1b cross-fit gap G — discriminable [pts] | 147 | +1.8376 | +0.3072 | [+1.2627, +2.4685] | +5.98 |
| S1b cross-fit gap G — all [pts] | 147 | +1.3313 | +0.2237 | [+0.9131, +1.7913] | +5.95 |
| S2 headroom_J4 — discriminable [pts] | 147 | +0.7105 | +0.1995 | [+0.3492, +1.1258] | +3.56 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 147 | +0.5184 | +0.1471 | [+0.2524, +0.8257] | +3.52 |
| S2 headroom_J4 — all, zeros_strict | 147 | +0.5546 | +0.1572 | [+0.2704, +0.8832] | +3.53 |
| S2b leaf regret — discriminable [pts] | 147 | +0.8406 | +0.2322 | [+0.4042, +1.3178] | +3.62 |
| S2b leaf regret — all [pts] | 147 | +0.6054 | +0.1679 | [+0.2899, +0.9508] | +3.60 |
| *(audit only, never quoted)* naive range | 147 | +2.7749 | +0.2689 | [+2.2770, +3.3299] | +10.32 |
| *(audit only, never quoted)* naive champ regret | 147 | +1.0619 | +0.1795 | [+0.7409, +1.4399] | +5.91 |
| *(diagnostic)* S1b parity-swapped | 147 | +1.9243 | +0.3082 | [+1.3551, +2.5522] | +6.24 |
| *(diagnostic)* S2 parity-swapped | 147 | +0.5829 | +0.2215 | [+0.1698, +1.0295] | +2.63 |

### phase:mid  (n=166 positions, 138 roots, champ arm scored on 166)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 166 | +6.6847 | +1.4526 | [+4.1351, +9.7697] | +4.60 |
| S1a σ²_arm — all (zeros added) [pts²] | 166 | +4.8351 | +1.0494 | [+2.9938, +7.0663] | +4.61 |
| S1b cross-fit gap G — discriminable [pts] | 166 | +2.3618 | +0.4038 | [+1.5887, +3.1646] | +5.85 |
| S1b cross-fit gap G — all [pts] | 166 | +1.7099 | +0.2924 | [+1.1520, +2.2905] | +5.85 |
| S2 headroom_J4 — discriminable [pts] | 166 | +1.2150 | +0.3410 | [+0.5640, +1.8865] | +3.56 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 166 | +0.8814 | +0.2474 | [+0.4096, +1.3693] | +3.56 |
| S2 headroom_J4 — all, zeros_strict | 166 | +0.9437 | +0.2649 | [+0.4383, +1.4664] | +3.56 |
| S2b leaf regret — discriminable [pts] | 166 | +1.5489 | +0.3806 | [+0.8203, +2.3076] | +4.07 |
| S2b leaf regret — all [pts] | 166 | +1.1151 | +0.2757 | [+0.5880, +1.6651] | +4.04 |
| *(audit only, never quoted)* naive range | 166 | +4.9349 | +0.3103 | [+4.3460, +5.5464] | +15.90 |
| *(audit only, never quoted)* naive champ regret | 166 | +2.4768 | +0.2665 | [+1.9712, +3.0064] | +9.30 |
| *(diagnostic)* S1b parity-swapped | 166 | +2.3976 | +0.4084 | [+1.6047, +3.2065] | +5.87 |
| *(diagnostic)* S2 parity-swapped | 166 | +0.9349 | +0.3345 | [+0.2859, +1.5826] | +2.79 |

### profile:app_aug2  (n=3 positions, 1 roots, champ arm scored on 3)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 3 | +26.1184 | nan | [nan, nan] | nan |
| S1a σ²_arm — all (zeros added) [pts²] | 3 | +20.0505 | nan | [nan, nan] | nan |
| S1b cross-fit gap G — discriminable [pts] | 3 | +10.3958 | nan | [nan, nan] | nan |
| S1b cross-fit gap G — all [pts] | 3 | +7.9806 | nan | [nan, nan] | nan |
| S2 headroom_J4 — discriminable [pts] | 3 | +3.5833 | nan | [nan, nan] | nan |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 3 | +2.7508 | nan | [nan, nan] | nan |
| S2 headroom_J4 — all, zeros_strict | 3 | +2.9246 | nan | [nan, nan] | nan |
| S2b leaf regret — discriminable [pts] | 3 | +2.1875 | nan | [nan, nan] | nan |
| S2b leaf regret — all [pts] | 3 | +1.6793 | nan | [nan, nan] | nan |
| *(audit only, never quoted)* naive range | 3 | +11.0104 | nan | [nan, nan] | nan |
| *(audit only, never quoted)* naive champ regret | 3 | +4.4688 | nan | [nan, nan] | nan |
| *(diagnostic)* S1b parity-swapped | 3 | +10.1458 | nan | [nan, nan] | nan |
| *(diagnostic)* S2 parity-swapped | 3 | +4.0625 | nan | [nan, nan] | nan |

### profile:fixed_v1  (n=28 positions, 12 roots, champ arm scored on 28)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 28 | +5.7585 | +2.0502 | [+2.1293, +10.6577] | +2.81 |
| S1a σ²_arm — all (zeros added) [pts²] | 28 | +4.4206 | +1.5739 | [+1.6346, +8.1817] | +2.81 |
| S1b cross-fit gap G — discriminable [pts] | 28 | +2.2902 | +0.9533 | [+0.3775, +4.2375] | +2.40 |
| S1b cross-fit gap G — all [pts] | 28 | +1.7581 | +0.7319 | [+0.2898, +3.2530] | +2.40 |
| S2 headroom_J4 — discriminable [pts] | 28 | +1.4174 | +0.9041 | [-0.2863, +3.4225] | +1.57 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 28 | +1.0881 | +0.6941 | [-0.2198, +2.6274] | +1.57 |
| S2 headroom_J4 — all, zeros_strict | 28 | +1.1568 | +0.7379 | [-0.2337, +2.7933] | +1.57 |
| S2b leaf regret — discriminable [pts] | 28 | +0.8527 | +0.8306 | [-0.6211, +2.4293] | +1.03 |
| S2b leaf regret — all [pts] | 28 | +0.6546 | +0.6376 | [-0.4768, +1.8649] | +1.03 |
| *(audit only, never quoted)* naive range | 28 | +4.9107 | +0.7061 | [+3.5869, +6.5192] | +6.96 |
| *(audit only, never quoted)* naive champ regret | 28 | +2.6696 | +0.6882 | [+1.4943, +4.2656] | +3.88 |
| *(diagnostic)* S1b parity-swapped | 28 | +1.0156 | +0.9392 | [-0.6901, +3.1536] | +1.08 |
| *(diagnostic)* S2 parity-swapped | 28 | +0.7812 | +1.0783 | [-1.2768, +3.0025] | +0.72 |

### profile:walled  (n=471 positions, 264 roots, champ arm scored on 471)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 471 | +3.9899 | +0.7284 | [+2.6538, +5.5394] | +5.48 |
| S1a σ²_arm — all (zeros added) [pts²] | 471 | +2.8837 | +0.5261 | [+1.9189, +4.0049] | +5.48 |
| S1b cross-fit gap G — discriminable [pts] | 471 | +1.5529 | +0.2391 | [+1.0883, +2.0262] | +6.50 |
| S1b cross-fit gap G — all [pts] | 471 | +1.1219 | +0.1726 | [+0.7864, +1.4637] | +6.50 |
| S2 headroom_J4 — discriminable [pts] | 471 | +0.7676 | +0.1959 | [+0.3893, +1.1627] | +3.92 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 471 | +0.5559 | +0.1417 | [+0.2818, +0.8416] | +3.92 |
| S2 headroom_J4 — all, zeros_strict | 471 | +0.5953 | +0.1518 | [+0.3019, +0.9013] | +3.92 |
| S2b leaf regret — discriminable [pts] | 471 | +0.9451 | +0.1973 | [+0.5672, +1.3369] | +4.79 |
| S2b leaf regret — all [pts] | 471 | +0.6823 | +0.1425 | [+0.4094, +0.9652] | +4.79 |
| *(audit only, never quoted)* naive range | 471 | +4.3124 | +0.1728 | [+3.9809, +4.6609] | +24.95 |
| *(audit only, never quoted)* naive champ regret | 471 | +2.1442 | +0.1558 | [+1.8487, +2.4611] | +13.76 |
| *(diagnostic)* S1b parity-swapped | 471 | +1.5661 | +0.2589 | [+1.0584, +2.0758] | +6.05 |
| *(diagnostic)* S2 parity-swapped | 471 | +0.6691 | +0.2191 | [+0.2376, +1.0974] | +3.05 |

### stratum:e4  (n=35 positions, 15 roots, champ arm scored on 35)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 35 | +7.6028 | +2.4344 | [+3.4315, +12.9234] | +3.12 |
| S1a σ²_arm — all (zeros added) [pts²] | 35 | +5.8365 | +1.8688 | [+2.6343, +9.9210] | +3.12 |
| S1b cross-fit gap G — discriminable [pts] | 35 | +2.8786 | +1.0238 | [+0.9357, +4.9518] | +2.81 |
| S1b cross-fit gap G — all [pts] | 35 | +2.2098 | +0.7860 | [+0.7183, +3.8014] | +2.81 |
| S2 headroom_J4 — discriminable [pts] | 35 | +1.9054 | +0.8199 | [+0.3316, +3.5809] | +2.32 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 35 | +1.4627 | +0.6294 | [+0.2546, +2.7490] | +2.32 |
| S2 headroom_J4 — all, zeros_strict | 35 | +1.5551 | +0.6692 | [+0.2706, +2.9226] | +2.32 |
| S2b leaf regret — discriminable [pts] | 35 | +0.8196 | +0.6800 | [-0.4052, +2.1204] | +1.21 |
| S2b leaf regret — all [pts] | 35 | +0.6292 | +0.5221 | [-0.3110, +1.6278] | +1.21 |
| *(audit only, never quoted)* naive range | 35 | +5.7455 | +0.8121 | [+4.2611, +7.4688] | +7.07 |
| *(audit only, never quoted)* naive champ regret | 35 | +2.9161 | +0.5860 | [+1.8702, +4.1801] | +4.98 |
| *(diagnostic)* S1b parity-swapped | 35 | +1.6625 | +1.1218 | [-0.3859, +3.9961] | +1.48 |
| *(diagnostic)* S2 parity-swapped | 35 | +0.8554 | +0.9368 | [-1.0246, +2.6765] | +0.91 |

### stratum:selfplay  (n=467 positions, 262 roots, champ arm scored on 467)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 467 | +3.9674 | +0.7338 | [+2.6286, +5.4818] | +5.41 |
| S1a σ²_arm — all (zeros added) [pts²] | 467 | +2.8648 | +0.5299 | [+1.8982, +3.9584] | +5.41 |
| S1b cross-fit gap G — discriminable [pts] | 467 | +1.5546 | +0.2411 | [+1.0869, +2.0268] | +6.45 |
| S1b cross-fit gap G — all [pts] | 467 | +1.1226 | +0.1741 | [+0.7848, +1.4636] | +6.45 |
| S2 headroom_J4 — discriminable [pts] | 467 | +0.7394 | +0.1953 | [+0.3626, +1.1247] | +3.79 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 467 | +0.5339 | +0.1411 | [+0.2619, +0.8122] | +3.79 |
| S2 headroom_J4 — all, zeros_strict | 467 | +0.5720 | +0.1511 | [+0.2805, +0.8701] | +3.79 |
| S2b leaf regret — discriminable [pts] | 467 | +0.9569 | +0.1988 | [+0.5740, +1.3559] | +4.81 |
| S2b leaf regret — all [pts] | 467 | +0.6910 | +0.1436 | [+0.4145, +0.9791] | +4.81 |
| *(audit only, never quoted)* naive range | 467 | +4.2839 | +0.1725 | [+3.9480, +4.6269] | +24.84 |
| *(audit only, never quoted)* naive champ regret | 467 | +2.1328 | +0.1567 | [+1.8319, +2.4483] | +13.61 |
| *(diagnostic)* S1b parity-swapped | 467 | +1.5810 | +0.2603 | [+1.0614, +2.0873] | +6.07 |
| *(diagnostic)* S2 parity-swapped | 467 | +0.6836 | +0.2202 | [+0.2576, +1.1098] | +3.10 |

### uncapped_only  (n=408 positions, 243 roots, champ arm scored on 408)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 408 | +4.3475 | +0.8346 | [+2.8289, +6.0798] | +5.21 |
| S1a σ²_arm — all (zeros added) [pts²] | 408 | +3.1559 | +0.6035 | [+2.0571, +4.4057] | +5.23 |
| S1b cross-fit gap G — discriminable [pts] | 408 | +1.6062 | +0.2631 | [+1.0947, +2.1128] | +6.11 |
| S1b cross-fit gap G — all [pts] | 408 | +1.1678 | +0.1909 | [+0.7974, +1.5349] | +6.12 |
| S2 headroom_J4 — discriminable [pts] | 408 | +0.7970 | +0.2153 | [+0.3835, +1.2159] | +3.70 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 408 | +0.5810 | +0.1561 | [+0.2810, +0.8842] | +3.72 |
| S2 headroom_J4 — all, zeros_strict | 408 | +0.6217 | +0.1672 | [+0.3008, +0.9465] | +3.72 |
| S2b leaf regret — discriminable [pts] | 408 | +0.8699 | +0.2188 | [+0.4510, +1.3068] | +3.98 |
| S2b leaf regret — all [pts] | 408 | +0.6321 | +0.1587 | [+0.3287, +0.9493] | +3.98 |
| *(audit only, never quoted)* naive range | 408 | +4.1692 | +0.1815 | [+3.8187, +4.5286] | +22.97 |
| *(audit only, never quoted)* naive champ regret | 408 | +2.0930 | +0.1601 | [+1.7833, +2.4098] | +13.07 |
| *(diagnostic)* S1b parity-swapped | 408 | +1.4550 | +0.2709 | [+0.9244, +1.9799] | +5.37 |
| *(diagnostic)* S2 parity-swapped | 408 | +0.6552 | +0.2220 | [+0.2222, +1.0917] | +2.95 |

⚠️ **S1b carries its sentence (§4.1):** `G` is a *downward-biased estimate of the true range and an unbiased test of the null*. The naive rows are printed ONLY so the winner's-curse correction is auditable (§4.2) and are never results.

## 5. The bound chain (§4.3) — the mandatory statement

### pooled

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.8382 | [+0.4614, +1.2202] | +83.28 | [+45.24, +123.98] | +50.35 |
| zeros_strict | +0.8968 | [+0.4934, +1.3052] | +89.36 | [+48.42, +133.46] | +53.93 |
| discriminable | +1.1490 | [+0.6300, +1.6727] | +116.17 | [+62.07, +176.96] | +69.46 |

### capped_only

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.9457 | [+0.0294, +1.9141] | +94.47 | [+2.86, +208.51] | +56.92 |
| zeros_strict | +1.0115 | [+0.0312, +2.0475] | +101.41 | [+3.04, +227.35] | +60.96 |
| discriminable | +1.2930 | [+0.0375, +2.6148] | +132.08 | [+3.66, +325.50] | +78.44 |

### phase:early

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.5780 | [-0.1647, +1.3483] | +56.86 | [-16.07, +138.34] | +34.60 |
| zeros_strict | +0.6176 | [-0.1768, +1.4424] | +60.83 | [-17.26, +149.18] | +36.98 |
| discriminable | +0.7843 | [-0.2344, +1.8457] | +77.74 | [-22.89, +199.27] | +47.07 |

### phase:late

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.7258 | [+0.3534, +1.1560] | +71.77 | [+34.57, +116.94] | +43.52 |
| zeros_strict | +0.7765 | [+0.3786, +1.2364] | +76.94 | [+37.06, +125.77] | +46.60 |
| discriminable | +0.9946 | [+0.4888, +1.5761] | +99.62 | [+47.96, +165.06] | +59.92 |

### phase:mid

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +1.2339 | [+0.5734, +1.9170] | +125.50 | [+56.40, +208.91] | +74.74 |
| zeros_strict | +1.3212 | [+0.6136, +2.0530] | +135.26 | [+60.43, +228.14] | +80.21 |
| discriminable | +1.7010 | [+0.7896, +2.6411] | +180.51 | [+78.29, +331.14] | +104.52 |

### profile:app_aug2

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +3.8512 | [nan, nan] | +3600.00 | [nan, nan] | +276.23 |
| zeros_strict | +4.0944 | [nan, nan] | +3600.00 | [nan, nan] | +303.40 |
| discriminable | +5.0167 | [nan, nan] | +3600.00 | [nan, nan] | +451.21 |

### profile:fixed_v1

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +1.5234 | [-0.3077, +3.6783] | +158.72 | [-30.07, +3600.00] | +93.04 |
| zeros_strict | +1.6196 | [-0.3271, +3.9106] | +170.37 | [-31.98, +3600.00] | +99.23 |
| discriminable | +1.9844 | [-0.4008, +4.7915] | +218.29 | [-39.24, +3600.00] | +123.31 |

### profile:walled

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.7783 | [+0.3946, +1.1783] | +77.12 | [+38.63, +119.37] | +46.71 |
| zeros_strict | +0.8335 | [+0.4227, +1.2618] | +82.79 | [+41.41, +128.59] | +50.06 |
| discriminable | +1.0747 | [+0.5450, +1.6278] | +108.15 | [+53.56, +171.37] | +64.86 |

### stratum:e4

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +2.0478 | [+0.3564, +3.8485] | +227.38 | [+34.86, +3600.00] | +127.61 |
| zeros_strict | +2.1771 | [+0.3789, +4.0916] | +246.84 | [+37.08, +3600.00] | +136.49 |
| discriminable | +2.6675 | [+0.4642, +5.0132] | +336.91 | [+45.52, +3600.00] | +171.91 |

### stratum:selfplay

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.7475 | [+0.3666, +1.1370] | +73.98 | [+35.87, +114.87] | +44.84 |
| zeros_strict | +0.8008 | [+0.3928, +1.2181] | +79.44 | [+38.45, +123.75] | +48.08 |
| discriminable | +1.0352 | [+0.5077, +1.5746] | +103.92 | [+49.84, +164.88] | +62.42 |

### uncapped_only

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.8134 | [+0.3934, +1.2379] | +80.73 | [+38.52, +125.93] | +48.84 |
| zeros_strict | +0.8704 | [+0.4211, +1.3252] | +86.61 | [+41.25, +135.71] | +52.31 |
| discriminable | +1.1158 | [+0.5369, +1.7022] | +112.58 | [+52.75, +180.66] | +67.40 |

**σ_game sensitivity (§4.3)** on the headline elo CI-hi: σ=20.4 → +123.98 elo · σ=22.2 → +113.17 elo. elo scales as 1/σ_game, so the SMALLER σ is the larger, conservative-against-closure bound.

σ_game = **20.4** (§4.3: 20.4 `fixed_v1` / 22.2 `walled`); tied tile plies/game = **22.96** (census-measured); `Kelo` linear check = **97.5** elo per pt per tied tile ply.

⚠️ **§4.6 extrapolation, labelled:** the headline multiplies the measured `headroom_J4` by **1.4** to reach the full-set ceiling (order statistics a_n = {'2': 0.56, '4': 1.03, '8.55': 1.44}). That is an **extrapolation through the S1a spread estimate, never a measurement**. §4.4's thresholds are applied to the extrapolated figure so the cap cannot manufacture a closure. Realized capped fraction: **18.7%** of scored positions.

⚠️ **§4.3 caveats, inherited verbatim:** `NON_ADDITIVITY = 3.2` is **n = 1**, is calibrated at the TOP of the ladder, and the memo's range-consistent low-end divisor is ≈5.23. The divisor enters **linearly**, so this bound is quoted with a ±1.6× bracket, not as a point. The linear-φ step degrades above ~1σ.

## 6. §4.4 branch

### BRANCH 2 — HEADROOM IS REAL AND RESOLVED

A hand-crafted tie-break term is warranted. Next step is NOT to build one blind: mine WHICH feature separates a+ from arm 0 inside the tied sets. ⚠️ CL-065 forbids the learned route; the term must be hand-crafted, and must then be shown to add value on top of an optimally-scaled leaf (CL-078).

- read-rule: `|z| < 2.0` is **no conviction**. S1a z = **+6.01** (conviction) · S2 z = **+4.32** (conviction).
- `branch_3_condition_also_met` = **False** (spread CI excludes 0: True). ⚠️ See interpretation **I4** — branch 3 is unreachable under the pre-registered precedence; the flag is reported rather than the precedence silently re-ordered.
- §4.4 stratum rule: Strata agree in sign (or only one is present); the pooled estimate is primary per §4.4. (stratum means {'e4': 1.4626984126984128, 'selfplay': 0.5339425988640855}, n {'e4': 35, 'selfplay': 467})

**Sizing (mandatory on branch 4, reported always):** realized per-position sd = **+3.1168 pts**, cluster-robust se = **+0.1387 pts** at n = 502 over 277 roots. A ±17-elo bound needs 2·se ≤ +0.1742 pts ⇒ **n ≈ 2496**; a ±35-elo bound ⇒ **n ≈ 592** (composite scale included).

**§4.5 epsilon band (secondary, EXTRAPOLATION):** census tie rates eps=0.0 → 0.660, eps=0.05 → 0.666, eps=0.2 → 0.690, eps=0.5 → 0.723, eps=1.0 → 0.799. Stretched elo CI-hi: 0.0 → +123.98, 0.05 → +125.06, 0.2 → +129.75, 0.5 → +135.87, 1.0 → +150.15.

## 7. Scope, threats and where DESIGN was ambiguous

**§5 scope sentence, mandatory on any null:** a null through `clair-puct` closes *"spread visible to a deep clairvoyant search over THIS leaf"*, **not** *"spread in truth"*. The judge uses the leaf under test at its own leaves; systematic leaf blindness would make it UNDER-report the true spread. The out-of-family `tier1-greedy` sign leg (n=80, §5/§7.3) is the check, and it is bought only if the primary does not branch-1-close.

Other pre-stated threats that travel with every number here: chain-granularity on the TILE class (§6.2 — neither arm gets the meeple its chain value assumed); "exact tie" is a **lattice** property, not an indifference proof (§6.4); selection on ties makes regression to the mean push the measured spread toward 0 (§6.5 — this protects branch 2 and threatens branch 1); the scored population is the **≤12-way** tied set (§7.3); the self-play champion pick is *a* champion pick, not *the* one (§6.9); rules-epoch confound between strata (§6.6).

| id | where | resolution |
|---|---|---|
| **I1-parity-base** | §4.1 'even j = SELECTION half, odd j = EVALUATION half' | Implemented one-based-literal (default --parity-base 1). The choice cannot change validity -- both halves are exchangeable and E[G]=E[R]=0 under the null either way -- only the realized draw. The swapped split is computed and reported as `parity_swap` so the reader can see it is not a lever. |
| **I2-zero-addback-weighting** | §0.A / §6 'the analyser MUST add them back as exact zeros' | The zeros enter as their POPULATION SHARE, per stratum, not as literal rows: mean over (discriminable + analytic zeros) = (1 - p_drop) * mean(discriminable) exactly, because the zeros have zero value AND zero variance and their count is known. Applied as a per-position multiplier inside the bootstrap, so the CI scales exactly too. This reproduces DESIGN §6's own `headroom_all = 0.74 * headroom_discriminable`. |
| **I3-the-72-outside-tieset** | §0.A '72 of the 374 have the played action OUTSIDE the tie set' | Two zero-rates are carried. Spread (S1a/S1b) and S2b use ALL 374 rows as zeros. S2 (headroom) reports a headline using all 374 AND a per-row sensitivity `zeros_strict` that counts only the 302 rows whose played action is inside the tie set, leaving the 72 imputed at the discriminable mean. `zeros_strict` is the LARGER magnitude, i.e. the conservative-against-closure direction. It is a sensitivity row, never the headline. |
| **I4-branch-3-unreachable** | §4.4 'branch precedence 1 -> 2 -> 3 -> 4, first match wins' | Precedence is honoured EXACTLY as written (branch 1 fires), and the verdict additionally carries `branch_3_condition_also_met` plus this note. The reader gets both the literal pre-registered branch and the fact that the more specific reading ('the leaf is blind but the search is not') also holds. No silent re-ordering. |
| **I5-pooled-weighting** | §4.4 'the pooled estimate is primary' | Pooled = the unweighted mean over all scored positions (the farm-war reading, and what 'pooled' means everywhere else in this project). Per-stratum reads are always emitted beside it, and §4.4's no-pooling-on-sign-disagreement rule is enforced mechanically. |
| **I6-fullset-extrapolation-scope** | §4.6 'the full-set ceiling is ~= 1.40x the J=4 measured headroom' | Applied GLOBALLY exactly as written (so the cap cannot manufacture a closure), and the realized capped fraction is reported beside it so the reader can see how conservative that is. §4.6's own assumption-free check -- branch arithmetic on the UNCAPPED subset alone -- is emitted as a separate block. |

## 8. Governance

Measurement only (§8): `governance/PRODUCTION.yaml` untouched, **no `experiments/results.csv` row** (0 games played), no band claim. A claim id is minted only on branch 1, 2 or 3 — and never off a PARTIAL corpus.
