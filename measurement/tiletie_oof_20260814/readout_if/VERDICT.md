# TILE-TIE PRICING — READ-OUT

**Status: tiletie-oof dev slice / IN-FAMILY clair-puct — COMPLETE for the scope declared below.**

Pre-registration: [DESIGN.md](../../tiletie_pricing_20260812/DESIGN.md) — every estimator below is §4, implemented before any record was read. Generated `2026-08-14T23:23:41Z`.

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

Count source: per-stratum, from the full-supply plan measurement/tiletie_pricing_20260812/positions/POSITIONS_PLAN.json + the dropped index

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
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 502 | +0.8555 | +0.2142 | [+0.4377, +1.2833] | +3.99 |
| S1a σ²_arm — all (zeros added) [pts²] | 502 | +0.6185 | +0.1553 | [+0.3153, +0.9277] | +3.98 |
| S1b cross-fit gap G — discriminable [pts] | 502 | +0.6742 | +0.1665 | [+0.3476, +1.0041] | +4.05 |
| S1b cross-fit gap G — all [pts] | 502 | +0.4884 | +0.1215 | [+0.2492, +0.7284] | +4.02 |
| S2 headroom_J4 — discriminable [pts] | 502 | +0.4526 | +0.1225 | [+0.2138, +0.6925] | +3.69 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 502 | +0.3277 | +0.0889 | [+0.1544, +0.5020] | +3.68 |
| S2 headroom_J4 — all, zeros_strict | 502 | +0.3510 | +0.0952 | [+0.1656, +0.5375] | +3.69 |
| S2b leaf regret — discriminable [pts] | 502 | +0.2846 | +0.1262 | [+0.0391, +0.5328] | +2.26 |
| S2b leaf regret — all [pts] | 502 | +0.2050 | +0.0916 | [+0.0269, +0.3850] | +2.24 |
| *(audit only, never quoted)* naive range | 502 | +2.8877 | +0.1011 | [+2.6899, +3.0860] | +28.56 |
| *(audit only, never quoted)* naive champ regret | 502 | +1.5285 | +0.0843 | [+1.3644, +1.6942] | +18.13 |
| *(diagnostic)* S1b parity-swapped | 502 | +0.7033 | +0.1534 | [+0.4017, +1.0059] | +4.59 |
| *(diagnostic)* S2 parity-swapped | 502 | +0.4015 | +0.1201 | [+0.1649, +0.6362] | +3.34 |

### capped_only  (n=94 positions, 84 roots, champ arm scored on 94)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 94 | +0.7406 | +0.3675 | [+0.0980, +1.5391] | +2.02 |
| S1a σ²_arm — all (zeros added) [pts²] | 94 | +0.5387 | +0.2665 | [+0.0722, +1.1169] | +2.02 |
| S1b cross-fit gap G — discriminable [pts] | 94 | +0.3956 | +0.3544 | [-0.2901, +1.0908] | +1.12 |
| S1b cross-fit gap G — all [pts] | 94 | +0.2906 | +0.2569 | [-0.2064, +0.7956] | +1.13 |
| S2 headroom_J4 — discriminable [pts] | 94 | +0.2320 | +0.2742 | [-0.2770, +0.7772] | +0.85 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 94 | +0.1682 | +0.1980 | [-0.1993, +0.5617] | +0.85 |
| S2 headroom_J4 — all, zeros_strict | 94 | +0.1801 | +0.2121 | [-0.2136, +0.6018] | +0.85 |
| S2b leaf regret — discriminable [pts] | 94 | -0.0525 | +0.2769 | [-0.5895, +0.5000] | -0.19 |
| S2b leaf regret — all [pts] | 94 | -0.0374 | +0.2015 | [-0.4273, +0.3663] | -0.19 |
| *(audit only, never quoted)* naive range | 94 | +3.3660 | +0.2337 | [+2.9111, +3.8349] | +14.40 |
| *(audit only, never quoted)* naive champ regret | 94 | +1.8544 | +0.2265 | [+1.4278, +2.3138] | +8.19 |
| *(diagnostic)* S1b parity-swapped | 94 | +0.0665 | +0.3269 | [-0.5829, +0.7000] | +0.20 |
| *(diagnostic)* S2 parity-swapped | 94 | +0.1463 | +0.3313 | [-0.5094, +0.7930] | +0.44 |

### phase:early  (n=189 positions, 147 roots, champ arm scored on 189)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 189 | +0.3831 | +0.3961 | [-0.3655, +1.1936] | +0.97 |
| S1a σ²_arm — all (zeros added) [pts²] | 189 | +0.2764 | +0.2878 | [-0.2674, +0.8659] | +0.96 |
| S1b cross-fit gap G — discriminable [pts] | 189 | +0.3118 | +0.3058 | [-0.2795, +0.9209] | +1.02 |
| S1b cross-fit gap G — all [pts] | 189 | +0.2262 | +0.2226 | [-0.2028, +0.6705] | +1.02 |
| S2 headroom_J4 — discriminable [pts] | 189 | +0.5112 | +0.2195 | [+0.0920, +0.9471] | +2.33 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 189 | +0.3685 | +0.1589 | [+0.0645, +0.6846] | +2.32 |
| S2 headroom_J4 — all, zeros_strict | 189 | +0.3948 | +0.1702 | [+0.0695, +0.7334] | +2.32 |
| S2b leaf regret — discriminable [pts] | 189 | +0.1868 | +0.2299 | [-0.2568, +0.6466] | +0.81 |
| S2b leaf regret — all [pts] | 189 | +0.1350 | +0.1665 | [-0.1860, +0.4685] | +0.81 |
| *(audit only, never quoted)* naive range | 189 | +3.4178 | +0.1657 | [+3.1012, +3.7478] | +20.63 |
| *(audit only, never quoted)* naive champ regret | 189 | +1.7806 | +0.1513 | [+1.4944, +2.0893] | +11.77 |
| *(diagnostic)* S1b parity-swapped | 189 | +0.2781 | +0.2977 | [-0.3056, +0.8639] | +0.93 |
| *(diagnostic)* S2 parity-swapped | 189 | -0.0823 | +0.2120 | [-0.4903, +0.3305] | -0.39 |

### phase:late  (n=147 positions, 126 roots, champ arm scored on 147)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 147 | +0.9665 | +0.2952 | [+0.4593, +1.6143] | +3.27 |
| S1a σ²_arm — all (zeros added) [pts²] | 147 | +0.7006 | +0.2135 | [+0.3342, +1.1674] | +3.28 |
| S1b cross-fit gap G — discriminable [pts] | 147 | +1.0850 | +0.1833 | [+0.7358, +1.4551] | +5.92 |
| S1b cross-fit gap G — all [pts] | 147 | +0.7869 | +0.1328 | [+0.5334, +1.0541] | +5.93 |
| S2 headroom_J4 — discriminable [pts] | 147 | +0.5374 | +0.1493 | [+0.2613, +0.8408] | +3.60 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 147 | +0.3915 | +0.1085 | [+0.1910, +0.6117] | +3.61 |
| S2 headroom_J4 — all, zeros_strict | 147 | +0.4189 | +0.1161 | [+0.2044, +0.6545] | +3.61 |
| S2b leaf regret — discriminable [pts] | 147 | +0.6059 | +0.1600 | [+0.3080, +0.9269] | +3.79 |
| S2b leaf regret — all [pts] | 147 | +0.4389 | +0.1158 | [+0.2233, +0.6705] | +3.79 |
| *(audit only, never quoted)* naive range | 147 | +1.7929 | +0.1437 | [+1.5220, +2.0859] | +12.48 |
| *(audit only, never quoted)* naive champ regret | 147 | +0.9435 | +0.1135 | [+0.7293, +1.1719] | +8.31 |
| *(diagnostic)* S1b parity-swapped | 147 | +0.9983 | +0.1613 | [+0.6813, +1.3203] | +6.19 |
| *(diagnostic)* S2 parity-swapped | 147 | +0.6148 | +0.1419 | [+0.3425, +0.9001] | +4.33 |

### phase:mid  (n=166 positions, 138 roots, champ arm scored on 166)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 166 | +1.2949 | +0.3517 | [+0.6411, +1.9927] | +3.68 |
| S1a σ²_arm — all (zeros added) [pts²] | 166 | +0.9352 | +0.2542 | [+0.4626, +1.4393] | +3.68 |
| S1b cross-fit gap G — discriminable [pts] | 166 | +0.7229 | +0.3012 | [+0.1276, +1.3080] | +2.40 |
| S1b cross-fit gap G — all [pts] | 166 | +0.5225 | +0.2188 | [+0.0910, +0.9467] | +2.39 |
| S2 headroom_J4 — discriminable [pts] | 166 | +0.3106 | +0.2330 | [-0.1453, +0.7673] | +1.33 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 166 | +0.2248 | +0.1687 | [-0.1052, +0.5552] | +1.33 |
| S2 headroom_J4 — all, zeros_strict | 166 | +0.2408 | +0.1807 | [-0.1127, +0.5948] | +1.33 |
| S2b leaf regret — discriminable [pts] | 166 | +0.1114 | +0.2524 | [-0.3803, +0.6063] | +0.44 |
| S2b leaf regret — all [pts] | 166 | +0.0778 | +0.1834 | [-0.2811, +0.4368] | +0.42 |
| *(audit only, never quoted)* naive range | 166 | +3.2536 | +0.1782 | [+2.9149, +3.6097] | +18.26 |
| *(audit only, never quoted)* naive champ regret | 166 | +1.7596 | +0.1793 | [+1.4180, +2.1240] | +9.82 |
| *(diagnostic)* S1b parity-swapped | 166 | +0.9262 | +0.2856 | [+0.3731, +1.4824] | +3.24 |
| *(diagnostic)* S2 parity-swapped | 166 | +0.7636 | +0.2632 | [+0.2553, +1.2828] | +2.90 |

### profile:app_aug2  (n=3 positions, 1 roots, champ arm scored on 3)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 3 | -0.2301 | nan | [nan, nan] | nan |
| S1a σ²_arm — all (zeros added) [pts²] | 3 | -0.1766 | nan | [nan, nan] | nan |
| S1b cross-fit gap G — discriminable [pts] | 3 | +0.6667 | nan | [nan, nan] | nan |
| S1b cross-fit gap G — all [pts] | 3 | +0.5118 | nan | [nan, nan] | nan |
| S2 headroom_J4 — discriminable [pts] | 3 | +1.1875 | nan | [nan, nan] | nan |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 3 | +0.9116 | nan | [nan, nan] | nan |
| S2 headroom_J4 — all, zeros_strict | 3 | +0.9692 | nan | [nan, nan] | nan |
| S2b leaf regret — discriminable [pts] | 3 | -0.2708 | nan | [nan, nan] | nan |
| S2b leaf regret — all [pts] | 3 | -0.2079 | nan | [nan, nan] | nan |
| *(audit only, never quoted)* naive range | 3 | +3.6667 | nan | [nan, nan] | nan |
| *(audit only, never quoted)* naive champ regret | 3 | +1.1458 | nan | [nan, nan] | nan |
| *(diagnostic)* S1b parity-swapped | 3 | +1.3958 | nan | [nan, nan] | nan |
| *(diagnostic)* S2 parity-swapped | 3 | -0.2708 | nan | [nan, nan] | nan |

### profile:fixed_v1  (n=28 positions, 12 roots, champ arm scored on 28)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 28 | -0.2826 | +0.7432 | [-1.6501, +1.0410] | -0.38 |
| S1a σ²_arm — all (zeros added) [pts²] | 28 | -0.2170 | +0.5705 | [-1.2668, +0.7991] | -0.38 |
| S1b cross-fit gap G — discriminable [pts] | 28 | +0.1875 | +1.1762 | [-2.0137, +1.9899] | +0.16 |
| S1b cross-fit gap G — all [pts] | 28 | +0.1439 | +0.9030 | [-1.5458, +1.5276] | +0.16 |
| S2 headroom_J4 — discriminable [pts] | 28 | +0.2701 | +0.6215 | [-0.8604, +1.2847] | +0.43 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 28 | +0.2073 | +0.4771 | [-0.6605, +0.9863] | +0.43 |
| S2 headroom_J4 — all, zeros_strict | 28 | +0.2204 | +0.5072 | [-0.7022, +1.0485] | +0.43 |
| S2b leaf regret — discriminable [pts] | 28 | -0.3147 | +0.6005 | [-1.4201, +0.6903] | -0.52 |
| S2b leaf regret — all [pts] | 28 | -0.2416 | +0.4610 | [-1.0902, +0.5300] | -0.52 |
| *(audit only, never quoted)* naive range | 28 | +2.3583 | +0.4096 | [+1.5652, +3.0897] | +5.76 |
| *(audit only, never quoted)* naive champ regret | 28 | +1.5089 | +0.2717 | [+0.9833, +2.0525] | +5.55 |
| *(diagnostic)* S1b parity-swapped | 28 | +0.4219 | +0.9743 | [-1.3936, +1.9097] | +0.43 |
| *(diagnostic)* S2 parity-swapped | 28 | +0.6875 | +0.5439 | [-0.2083, +1.8490] | +1.26 |

### profile:walled  (n=471 positions, 264 roots, champ arm scored on 471)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 471 | +0.9300 | +0.2231 | [+0.5082, +1.3850] | +4.17 |
| S1a σ²_arm — all (zeros added) [pts²] | 471 | +0.6732 | +0.1614 | [+0.3677, +1.0024] | +4.17 |
| S1b cross-fit gap G — discriminable [pts] | 471 | +0.7032 | +0.1636 | [+0.3879, +1.0264] | +4.30 |
| S1b cross-fit gap G — all [pts] | 471 | +0.5087 | +0.1183 | [+0.2813, +0.7416] | +4.30 |
| S2 headroom_J4 — discriminable [pts] | 471 | +0.4587 | +0.1255 | [+0.2171, +0.7090] | +3.65 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 471 | +0.3311 | +0.0907 | [+0.1567, +0.5118] | +3.65 |
| S2 headroom_J4 — all, zeros_strict | 471 | +0.3548 | +0.0971 | [+0.1679, +0.5483] | +3.65 |
| S2b leaf regret — discriminable [pts] | 471 | +0.3238 | +0.1293 | [+0.0710, +0.5768] | +2.50 |
| S2b leaf regret — all [pts] | 471 | +0.2342 | +0.0934 | [+0.0516, +0.4169] | +2.51 |
| *(audit only, never quoted)* naive range | 471 | +2.9142 | +0.1048 | [+2.7124, +3.1258] | +27.82 |
| *(audit only, never quoted)* naive champ regret | 471 | +1.5321 | +0.0885 | [+1.3618, +1.7102] | +17.32 |
| *(diagnostic)* S1b parity-swapped | 471 | +0.7156 | +0.1534 | [+0.4149, +1.0200] | +4.66 |
| *(diagnostic)* S2 parity-swapped | 471 | +0.3888 | +0.1243 | [+0.1433, +0.6333] | +3.13 |

### stratum:e4  (n=35 positions, 15 roots, champ arm scored on 35)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 35 | +0.2381 | +0.8310 | [-1.2461, +1.8457] | +0.29 |
| S1a σ²_arm — all (zeros added) [pts²] | 35 | +0.1828 | +0.6380 | [-0.9566, +1.4169] | +0.29 |
| S1b cross-fit gap G — discriminable [pts] | 35 | +0.4946 | +1.0057 | [-1.4722, +2.0884] | +0.49 |
| S1b cross-fit gap G — all [pts] | 35 | +0.3797 | +0.7721 | [-1.1302, +1.6032] | +0.49 |
| S2 headroom_J4 — discriminable [pts] | 35 | +0.2857 | +0.5061 | [-0.6829, +1.1234] | +0.56 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 35 | +0.2193 | +0.3885 | [-0.5243, +0.8624] | +0.56 |
| S2 headroom_J4 — all, zeros_strict | 35 | +0.2332 | +0.4130 | [-0.5574, +0.9168] | +0.56 |
| S2b leaf regret — discriminable [pts] | 35 | -0.1500 | +0.5307 | [-1.1727, +0.7544] | -0.28 |
| S2b leaf regret — all [pts] | 35 | -0.1152 | +0.4074 | [-0.9003, +0.5791] | -0.28 |
| *(audit only, never quoted)* naive range | 35 | +2.8393 | +0.4871 | [+1.9418, +3.7956] | +5.83 |
| *(audit only, never quoted)* naive champ regret | 35 | +1.4714 | +0.2177 | [+1.0648, +1.9268] | +6.76 |
| *(diagnostic)* S1b parity-swapped | 35 | +0.9786 | +0.9763 | [-0.8779, +2.6917] | +1.00 |
| *(diagnostic)* S2 parity-swapped | 35 | +0.5625 | +0.4322 | [-0.1613, +1.4958] | +1.30 |

### stratum:selfplay  (n=467 positions, 262 roots, champ arm scored on 467)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 467 | +0.9017 | +0.2219 | [+0.4798, +1.3421] | +4.06 |
| S1a σ²_arm — all (zeros added) [pts²] | 467 | +0.6511 | +0.1602 | [+0.3465, +0.9691] | +4.06 |
| S1b cross-fit gap G — discriminable [pts] | 467 | +0.6876 | +0.1633 | [+0.3671, +1.0090] | +4.21 |
| S1b cross-fit gap G — all [pts] | 467 | +0.4965 | +0.1179 | [+0.2651, +0.7286] | +4.21 |
| S2 headroom_J4 — discriminable [pts] | 467 | +0.4651 | +0.1265 | [+0.2203, +0.7164] | +3.68 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 467 | +0.3358 | +0.0913 | [+0.1591, +0.5173] | +3.68 |
| S2 headroom_J4 — all, zeros_strict | 467 | +0.3598 | +0.0978 | [+0.1705, +0.5542] | +3.68 |
| S2b leaf regret — discriminable [pts] | 467 | +0.3172 | +0.1297 | [+0.0669, +0.5748] | +2.45 |
| S2b leaf regret — all [pts] | 467 | +0.2290 | +0.0936 | [+0.0483, +0.4151] | +2.45 |
| *(audit only, never quoted)* naive range | 467 | +2.8913 | +0.1028 | [+2.6927, +3.0959] | +28.12 |
| *(audit only, never quoted)* naive champ regret | 467 | +1.5328 | +0.0892 | [+1.3605, +1.7094] | +17.18 |
| *(diagnostic)* S1b parity-swapped | 467 | +0.6827 | +0.1489 | [+0.3943, +0.9742] | +4.59 |
| *(diagnostic)* S2 parity-swapped | 467 | +0.3895 | +0.1254 | [+0.1420, +0.6303] | +3.11 |

### uncapped_only  (n=408 positions, 243 roots, champ arm scored on 408)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 408 | +0.8819 | +0.2505 | [+0.4123, +1.3915] | +3.52 |
| S1a σ²_arm — all (zeros added) [pts²] | 408 | +0.6369 | +0.1815 | [+0.2969, +1.0056] | +3.51 |
| S1b cross-fit gap G — discriminable [pts] | 408 | +0.7384 | +0.1891 | [+0.3702, +1.1021] | +3.90 |
| S1b cross-fit gap G — all [pts] | 408 | +0.5340 | +0.1381 | [+0.2646, +0.7997] | +3.87 |
| S2 headroom_J4 — discriminable [pts] | 408 | +0.5034 | +0.1366 | [+0.2429, +0.7709] | +3.68 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 408 | +0.3645 | +0.0993 | [+0.1750, +0.5588] | +3.67 |
| S2 headroom_J4 — all, zeros_strict | 408 | +0.3903 | +0.1063 | [+0.1876, +0.5985] | +3.67 |
| S2b leaf regret — discriminable [pts] | 408 | +0.3623 | +0.1437 | [+0.0827, +0.6460] | +2.52 |
| S2b leaf regret — all [pts] | 408 | +0.2609 | +0.1043 | [+0.0582, +0.4663] | +2.50 |
| *(audit only, never quoted)* naive range | 408 | +2.7775 | +0.1097 | [+2.5670, +2.9993] | +25.33 |
| *(audit only, never quoted)* naive champ regret | 408 | +1.4534 | +0.0891 | [+1.2839, +1.6314] | +16.31 |
| *(diagnostic)* S1b parity-swapped | 408 | +0.8500 | +0.1711 | [+0.5185, +1.1789] | +4.97 |
| *(diagnostic)* S2 parity-swapped | 408 | +0.4603 | +0.1290 | [+0.2097, +0.7166] | +3.57 |

⚠️ **S1b carries its sentence (§4.1):** `G` is a *downward-biased estimate of the true range and an unbiased test of the null*. The naive rows are printed ONLY so the winner's-curse correction is auditable (§4.2) and are never results.

## 5. The bound chain (§4.3) — the mandatory statement

### pooled

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.4588 | [+0.2162, +0.7027] | +44.98 | [+21.10, +69.43] | +27.43 |
| zeros_strict | +0.4913 | [+0.2318, +0.7526] | +48.21 | [+22.63, +74.50] | +29.38 |
| discriminable | +0.6336 | [+0.2993, +0.9695] | +62.44 | [+29.25, +96.97] | +37.95 |

### capped_only

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.2355 | [-0.2790, +0.7864] | +22.99 | [-27.26, +77.96] | +14.06 |
| zeros_strict | +0.2522 | [-0.2990, +0.8426] | +24.63 | [-29.22, +83.74] | +15.05 |
| discriminable | +0.3249 | [-0.3878, +1.0880] | +31.76 | [-37.96, +109.58] | +19.40 |

### phase:early

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.5158 | [+0.0903, +0.9585] | +50.65 | [+8.80, +95.81] | +30.85 |
| zeros_strict | +0.5528 | [+0.0973, +1.0267] | +54.33 | [+9.49, +103.02] | +33.08 |
| discriminable | +0.7157 | [+0.1289, +1.3259] | +70.75 | [+12.57, +135.79] | +42.92 |

### phase:late

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.5481 | [+0.2674, +0.8564] | +53.87 | [+26.12, +85.17] | +32.79 |
| zeros_strict | +0.5865 | [+0.2861, +0.9163] | +57.71 | [+27.96, +91.39] | +35.11 |
| discriminable | +0.7524 | [+0.3659, +1.1772] | +74.48 | [+35.80, +119.25] | +45.14 |

### phase:mid

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.3147 | [-0.1473, +0.7773] | +30.77 | [-14.37, +77.02] | +18.79 |
| zeros_strict | +0.3371 | [-0.1577, +0.8327] | +32.96 | [-15.39, +82.71] | +20.13 |
| discriminable | +0.4349 | [-0.2035, +1.0742] | +42.61 | [-19.86, +108.09] | +25.99 |

### profile:app_aug2

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +1.2763 | [nan, nan] | +130.21 | [nan, nan] | +77.39 |
| zeros_strict | +1.3569 | [nan, nan] | +139.31 | [nan, nan] | +82.46 |
| discriminable | +1.6625 | [nan, nan] | +175.68 | [nan, nan] | +102.01 |

### profile:fixed_v1

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.2903 | [-0.9247, +1.3808] | +28.37 | [-92.27, +142.04] | +17.33 |
| zeros_strict | +0.3086 | [-0.9831, +1.4680] | +30.17 | [-98.41, +152.16] | +18.43 |
| discriminable | +0.3781 | [-1.2046, +1.7986] | +37.01 | [-122.26, +193.05] | +22.59 |

### profile:walled

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.4636 | [+0.2194, +0.7165] | +45.46 | [+21.42, +70.82] | +27.72 |
| zeros_strict | +0.4967 | [+0.2350, +0.7676] | +48.74 | [+22.95, +76.03] | +29.70 |
| discriminable | +0.6422 | [+0.3039, +0.9926] | +63.31 | [+29.70, +99.41] | +38.47 |

### stratum:e4

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.3071 | [-0.7340, +1.2073] | +30.01 | [-72.60, +122.56] | +18.34 |
| zeros_strict | +0.3265 | [-0.7803, +1.2836] | +31.92 | [-77.33, +131.03] | +19.50 |
| discriminable | +0.4000 | [-0.9561, +1.5727] | +39.17 | [-95.56, +164.65] | +23.90 |

### stratum:selfplay

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.4702 | [+0.2228, +0.7242] | +46.11 | [+21.75, +71.61] | +28.11 |
| zeros_strict | +0.5037 | [+0.2386, +0.7758] | +49.44 | [+23.30, +76.88] | +30.12 |
| discriminable | +0.6511 | [+0.3085, +1.0029] | +64.20 | [+30.15, +100.49] | +39.00 |

### uncapped_only

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.5102 | [+0.2451, +0.7823] | +50.09 | [+23.93, +77.54] | +30.52 |
| zeros_strict | +0.5464 | [+0.2626, +0.8379] | +53.70 | [+25.65, +83.26] | +32.69 |
| discriminable | +0.7047 | [+0.3400, +1.0792] | +69.63 | [+33.25, +108.63] | +42.25 |

**σ_game sensitivity (§4.3)** on the headline elo CI-hi: σ=20.4 → +69.43 elo · σ=22.2 → +63.67 elo. elo scales as 1/σ_game, so the SMALLER σ is the larger, conservative-against-closure bound.

σ_game = **20.4** (§4.3: 20.4 `fixed_v1` / 22.2 `walled`); tied tile plies/game = **22.96** (census-measured); `Kelo` linear check = **97.5** elo per pt per tied tile ply.

⚠️ **§4.6 extrapolation, labelled:** the headline multiplies the measured `headroom_J4` by **1.4** to reach the full-set ceiling (order statistics a_n = {'2': 0.56, '4': 1.03, '8.55': 1.44}). That is an **extrapolation through the S1a spread estimate, never a measurement**. §4.4's thresholds are applied to the extrapolated figure so the cap cannot manufacture a closure. Realized capped fraction: **18.7%** of scored positions.

⚠️ **§4.3 caveats, inherited verbatim:** `NON_ADDITIVITY = 3.2` is **n = 1**, is calibrated at the TOP of the ladder, and the memo's range-consistent low-end divisor is ≈5.23. The divisor enters **linearly**, so this bound is quoted with a ±1.6× bracket, not as a point. The linear-φ step degrades above ~1σ.

## 6. §4.4 branch

### BRANCH 2 — HEADROOM IS REAL AND RESOLVED

A hand-crafted tie-break term is warranted. Next step is NOT to build one blind: mine WHICH feature separates a+ from arm 0 inside the tied sets. ⚠️ CL-065 forbids the learned route; the term must be hand-crafted, and must then be shown to add value on top of an optimally-scaled leaf (CL-078).

- read-rule: `|z| < 2.0` is **no conviction**. S1a z = **+3.98** (conviction) · S2 z = **+3.68** (conviction).
- `branch_3_condition_also_met` = **False** (spread CI excludes 0: True). ⚠️ See interpretation **I4** — branch 3 is unreachable under the pre-registered precedence; the flag is reported rather than the precedence silently re-ordered.
- §4.4 stratum rule: Strata agree in sign (or only one is present); the pooled estimate is primary per §4.4. (stratum means {'e4': 0.21933621933621933, 'selfplay': 0.3358281504167777}, n {'e4': 35, 'selfplay': 467})

**Sizing (mandatory on branch 4, reported always):** realized per-position sd = **+1.9557 pts**, cluster-robust se = **+0.0889 pts** at n = 502 over 277 roots. A ±17-elo bound needs 2·se ≤ +0.1742 pts ⇒ **n ≈ 1026**; a ±35-elo bound ⇒ **n ≈ 243** (composite scale included).

**§4.5 epsilon band (secondary, EXTRAPOLATION):** census tie rates eps=0.0 → 0.660, eps=0.05 → 0.666, eps=0.2 → 0.690, eps=0.5 → 0.723, eps=1.0 → 0.799. Stretched elo CI-hi: 0.0 → +69.43, 0.05 → +70.03, 0.2 → +72.66, 0.5 → +76.09, 1.0 → +84.08.

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
