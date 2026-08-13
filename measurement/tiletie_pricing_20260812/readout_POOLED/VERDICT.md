# TILE-TIE PRICING — READ-OUT

**Status: COMPLETE for the scope declared below.**

Pre-registration: [DESIGN.md](../DESIGN.md) — every estimator below is §4, implemented before any record was read. Generated `2026-08-13T15:37:03Z`.

## 1. Completion accounting

- planned positions in scope: **733** · fully scored: **733** · partially scored: **0** · absent: **0**
- positions ENTERING the statistics: **733** (`include_partial_arms=False`)

| profile | planned | complete | partial | absent |
|---|---|---|---|---|
| app_aug2 | 3 | 3 | 0 | 0 |
| fixed_v1 | 53 | 53 | 0 | 0 |
| walled | 677 | 677 | 0 | 0 |

| stratum | planned | complete | partial | absent |
|---|---|---|---|---|
| e4 | 60 | 60 | 0 | 0 |
| selfplay | 673 | 673 | 0 | 0 |

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

### pooled  (n=733 positions, 399 roots, champ arm scored on 733)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 733 | +0.9521 | +0.2234 | [+0.5432, +1.4161] | +4.26 |
| S1a σ²_arm — all (zeros added) [pts²] | 733 | +0.6900 | +0.1621 | [+0.3924, +1.0269] | +4.26 |
| S1b cross-fit gap G — discriminable [pts] | 733 | +0.6244 | +0.1359 | [+0.3587, +0.8927] | +4.60 |
| S1b cross-fit gap G — all [pts] | 733 | +0.4538 | +0.0991 | [+0.2590, +0.6496] | +4.58 |
| S2 headroom_J4 — discriminable [pts] | 733 | +0.3465 | +0.1013 | [+0.1472, +0.5471] | +3.42 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 733 | +0.2519 | +0.0735 | [+0.1073, +0.3977] | +3.43 |
| S2 headroom_J4 — all, zeros_strict | 733 | +0.2696 | +0.0787 | [+0.1149, +0.4257] | +3.43 |
| S2b leaf regret — discriminable [pts] | 733 | +0.3236 | +0.1045 | [+0.1190, +0.5288] | +3.10 |
| S2b leaf regret — all [pts] | 733 | +0.2340 | +0.0758 | [+0.0853, +0.3829] | +3.09 |
| *(audit only, never quoted)* naive range | 733 | +2.8487 | +0.0856 | [+2.6815, +3.0195] | +33.28 |
| *(audit only, never quoted)* naive champ regret | 733 | +1.4475 | +0.0687 | [+1.3146, +1.5839] | +21.07 |
| *(diagnostic)* S1b parity-swapped | 733 | +0.6735 | +0.1351 | [+0.4058, +0.9401] | +4.99 |
| *(diagnostic)* S2 parity-swapped | 733 | +0.3538 | +0.0989 | [+0.1569, +0.5482] | +3.58 |

### capped_only  (n=133 positions, 119 roots, champ arm scored on 133)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 133 | +0.9163 | +0.3202 | [+0.3305, +1.5884] | +2.86 |
| S1a σ²_arm — all (zeros added) [pts²] | 133 | +0.6655 | +0.2322 | [+0.2407, +1.1521] | +2.87 |
| S1b cross-fit gap G — discriminable [pts] | 133 | +0.3712 | +0.2936 | [-0.2066, +0.9408] | +1.26 |
| S1b cross-fit gap G — all [pts] | 133 | +0.2721 | +0.2131 | [-0.1474, +0.6856] | +1.28 |
| S2 headroom_J4 — discriminable [pts] | 133 | +0.3172 | +0.2527 | [-0.1674, +0.8238] | +1.26 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 133 | +0.2320 | +0.1829 | [-0.1191, +0.6002] | +1.27 |
| S2 headroom_J4 — all, zeros_strict | 133 | +0.2481 | +0.1959 | [-0.1280, +0.6422] | +1.27 |
| S2b leaf regret — discriminable [pts] | 133 | +0.0475 | +0.2205 | [-0.3858, +0.4793] | +0.22 |
| S2b leaf regret — all [pts] | 133 | +0.0342 | +0.1603 | [-0.2797, +0.3479] | +0.21 |
| *(audit only, never quoted)* naive range | 133 | +3.3837 | +0.2050 | [+2.9883, +3.7859] | +16.50 |
| *(audit only, never quoted)* naive champ regret | 133 | +1.9417 | +0.1948 | [+1.5718, +2.3355] | +9.97 |
| *(diagnostic)* S1b parity-swapped | 133 | +0.2801 | +0.2786 | [-0.2716, +0.8135] | +1.01 |
| *(diagnostic)* S2 parity-swapped | 133 | +0.4196 | +0.2759 | [-0.1078, +0.9678] | +1.52 |

### phase:early  (n=300 positions, 229 roots, champ arm scored on 300)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 300 | +0.3608 | +0.3098 | [-0.2396, +0.9787] | +1.16 |
| S1a σ²_arm — all (zeros added) [pts²] | 300 | +0.2639 | +0.2261 | [-0.1742, +0.7160] | +1.17 |
| S1b cross-fit gap G — discriminable [pts] | 300 | +0.2881 | +0.2378 | [-0.1837, +0.7623] | +1.21 |
| S1b cross-fit gap G — all [pts] | 300 | +0.2119 | +0.1733 | [-0.1310, +0.5574] | +1.22 |
| S2 headroom_J4 — discriminable [pts] | 300 | +0.3035 | +0.1779 | [-0.0379, +0.6575] | +1.71 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 300 | +0.2199 | +0.1288 | [-0.0278, +0.4759] | +1.71 |
| S2 headroom_J4 — all, zeros_strict | 300 | +0.2355 | +0.1379 | [-0.0297, +0.5098] | +1.71 |
| S2b leaf regret — discriminable [pts] | 300 | +0.1535 | +0.1888 | [-0.2125, +0.5229] | +0.81 |
| S2b leaf regret — all [pts] | 300 | +0.1106 | +0.1367 | [-0.1552, +0.3781] | +0.81 |
| *(audit only, never quoted)* naive range | 300 | +3.3550 | +0.1280 | [+3.1087, +3.6143] | +26.21 |
| *(audit only, never quoted)* naive champ regret | 300 | +1.6860 | +0.1160 | [+1.4634, +1.9184] | +14.53 |
| *(diagnostic)* S1b parity-swapped | 300 | +0.2285 | +0.2486 | [-0.2594, +0.7144] | +0.92 |
| *(diagnostic)* S2 parity-swapped | 300 | -0.0600 | +0.1727 | [-0.3972, +0.2826] | -0.35 |

### phase:late  (n=209 positions, 178 roots, champ arm scored on 209)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 209 | +1.4687 | +0.5529 | [+0.6335, +2.7315] | +2.66 |
| S1a σ²_arm — all (zeros added) [pts²] | 209 | +1.0652 | +0.3995 | [+0.4618, +1.9781] | +2.67 |
| S1b cross-fit gap G — discriminable [pts] | 209 | +1.1160 | +0.1776 | [+0.7814, +1.4738] | +6.28 |
| S1b cross-fit gap G — all [pts] | 209 | +0.8100 | +0.1286 | [+0.5676, +1.0690] | +6.30 |
| S2 headroom_J4 — discriminable [pts] | 209 | +0.4728 | +0.1207 | [+0.2435, +0.7176] | +3.92 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 209 | +0.3456 | +0.0878 | [+0.1788, +0.5239] | +3.94 |
| S2 headroom_J4 — all, zeros_strict | 209 | +0.3697 | +0.0940 | [+0.1912, +0.5604] | +3.93 |
| S2b leaf regret — discriminable [pts] | 209 | +0.6618 | +0.1593 | [+0.3736, +0.9901] | +4.16 |
| S2b leaf regret — all [pts] | 209 | +0.4802 | +0.1153 | [+0.2712, +0.7174] | +4.17 |
| *(audit only, never quoted)* naive range | 209 | +1.8551 | +0.1430 | [+1.5897, +2.1456] | +12.97 |
| *(audit only, never quoted)* naive champ regret | 209 | +0.8792 | +0.0890 | [+0.7083, +1.0569] | +9.87 |
| *(diagnostic)* S1b parity-swapped | 209 | +1.0511 | +0.1591 | [+0.7521, +1.3679] | +6.61 |
| *(diagnostic)* S2 parity-swapped | 209 | +0.5356 | +0.1134 | [+0.3159, +0.7595] | +4.72 |

### phase:mid  (n=224 positions, 188 roots, champ arm scored on 224)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 224 | +1.2621 | +0.3159 | [+0.6650, +1.9041] | +4.00 |
| S1a σ²_arm — all (zeros added) [pts²] | 224 | +0.9107 | +0.2283 | [+0.4783, +1.3749] | +3.99 |
| S1b cross-fit gap G — discriminable [pts] | 224 | +0.6161 | +0.2533 | [+0.1188, +1.1060] | +2.43 |
| S1b cross-fit gap G — all [pts] | 224 | +0.4453 | +0.1840 | [+0.0838, +0.8008] | +2.42 |
| S2 headroom_J4 — discriminable [pts] | 224 | +0.2863 | +0.1961 | [-0.0981, +0.6689] | +1.46 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 224 | +0.2072 | +0.1420 | [-0.0710, +0.4836] | +1.46 |
| S2 headroom_J4 — all, zeros_strict | 224 | +0.2219 | +0.1520 | [-0.0760, +0.5179] | +1.46 |
| S2b leaf regret — discriminable [pts] | 224 | +0.2358 | +0.2061 | [-0.1588, +0.6355] | +1.14 |
| S2b leaf regret — all [pts] | 224 | +0.1696 | +0.1497 | [-0.1187, +0.4596] | +1.13 |
| *(audit only, never quoted)* naive range | 224 | +3.0977 | +0.1527 | [+2.8036, +3.4064] | +20.29 |
| *(audit only, never quoted)* naive champ regret | 224 | +1.6583 | +0.1464 | [+1.3795, +1.9508] | +11.33 |
| *(diagnostic)* S1b parity-swapped | 224 | +0.9171 | +0.2534 | [+0.4235, +1.4176] | +3.62 |
| *(diagnostic)* S2 parity-swapped | 224 | +0.7383 | +0.2142 | [+0.3213, +1.1551] | +3.45 |

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

### profile:fixed_v1  (n=53 positions, 22 roots, champ arm scored on 53)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 53 | +0.4502 | +0.8143 | [-0.9189, +2.0609] | +0.55 |
| S1a σ²_arm — all (zeros added) [pts²] | 53 | +0.3456 | +0.6251 | [-0.7054, +1.5821] | +0.55 |
| S1b cross-fit gap G — discriminable [pts] | 53 | +0.6521 | +0.7247 | [-0.8605, +1.8083] | +0.90 |
| S1b cross-fit gap G — all [pts] | 53 | +0.5006 | +0.5563 | [-0.6606, +1.3882] | +0.90 |
| S2 headroom_J4 — discriminable [pts] | 53 | +0.4505 | +0.3659 | [-0.2857, +1.0877] | +1.23 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 53 | +0.3458 | +0.2809 | [-0.2193, +0.8350] | +1.23 |
| S2 headroom_J4 — all, zeros_strict | 53 | +0.3677 | +0.2987 | [-0.2332, +0.8878] | +1.23 |
| S2b leaf regret — discriminable [pts] | 53 | +0.0425 | +0.3657 | [-0.7158, +0.6562] | +0.12 |
| S2b leaf regret — all [pts] | 53 | +0.0326 | +0.2807 | [-0.5495, +0.5038] | +0.12 |
| *(audit only, never quoted)* naive range | 53 | +2.5083 | +0.3125 | [+1.8952, +3.0770] | +8.03 |
| *(audit only, never quoted)* naive champ regret | 53 | +1.3638 | +0.2187 | [+0.9492, +1.7905] | +6.24 |
| *(diagnostic)* S1b parity-swapped | 53 | +0.8066 | +0.5989 | [-0.4557, +1.7702] | +1.35 |
| *(diagnostic)* S2 parity-swapped | 53 | +0.5165 | +0.3313 | [-0.0807, +1.2165] | +1.56 |

### profile:walled  (n=677 positions, 376 roots, champ arm scored on 677)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 677 | +0.9966 | +0.2339 | [+0.5743, +1.4904] | +4.26 |
| S1a σ²_arm — all (zeros added) [pts²] | 677 | +0.7208 | +0.1691 | [+0.4159, +1.0774] | +4.26 |
| S1b cross-fit gap G — discriminable [pts] | 677 | +0.6220 | +0.1362 | [+0.3594, +0.8888] | +4.57 |
| S1b cross-fit gap G — all [pts] | 677 | +0.4499 | +0.0985 | [+0.2601, +0.6431] | +4.57 |
| S2 headroom_J4 — discriminable [pts] | 677 | +0.3347 | +0.1060 | [+0.1280, +0.5424] | +3.16 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 677 | +0.2416 | +0.0765 | [+0.0923, +0.3919] | +3.16 |
| S2 headroom_J4 — all, zeros_strict | 677 | +0.2588 | +0.0820 | [+0.0989, +0.4199] | +3.16 |
| S2b leaf regret — discriminable [pts] | 677 | +0.3482 | +0.1096 | [+0.1336, +0.5621] | +3.18 |
| S2b leaf regret — all [pts] | 677 | +0.2518 | +0.0792 | [+0.0969, +0.4063] | +3.18 |
| *(audit only, never quoted)* naive range | 677 | +2.8717 | +0.0895 | [+2.6987, +3.0506] | +32.08 |
| *(audit only, never quoted)* naive champ regret | 677 | +1.4554 | +0.0724 | [+1.3145, +1.5983] | +20.09 |
| *(diagnostic)* S1b parity-swapped | 677 | +0.6599 | +0.1387 | [+0.3890, +0.9370] | +4.76 |
| *(diagnostic)* S2 parity-swapped | 677 | +0.3438 | +0.1040 | [+0.1383, +0.5507] | +3.31 |

### stratum:e4  (n=60 positions, 25 roots, champ arm scored on 60)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 60 | +0.6685 | +0.7728 | [-0.7153, +2.1679] | +0.87 |
| S1a σ²_arm — all (zeros added) [pts²] | 60 | +0.5132 | +0.5933 | [-0.5491, +1.6643] | +0.87 |
| S1b cross-fit gap G — discriminable [pts] | 60 | +0.7771 | +0.6624 | [-0.6127, +1.8542] | +1.17 |
| S1b cross-fit gap G — all [pts] | 60 | +0.5965 | +0.5085 | [-0.4704, +1.4234] | +1.17 |
| S2 headroom_J4 — discriminable [pts] | 60 | +0.4385 | +0.3283 | [-0.2255, +1.0156] | +1.34 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 60 | +0.3367 | +0.2521 | [-0.1731, +0.7797] | +1.34 |
| S2 headroom_J4 — all, zeros_strict | 60 | +0.3579 | +0.2680 | [-0.1840, +0.8289] | +1.34 |
| S2b leaf regret — discriminable [pts] | 60 | +0.0969 | +0.3432 | [-0.6162, +0.6951] | +0.28 |
| S2b leaf regret — all [pts] | 60 | +0.0744 | +0.2635 | [-0.4731, +0.5336] | +0.28 |
| *(audit only, never quoted)* naive range | 60 | +2.7714 | +0.3386 | [+2.1081, +3.4089] | +8.18 |
| *(audit only, never quoted)* naive champ regret | 60 | +1.3589 | +0.1930 | [+0.9931, +1.7308] | +7.04 |
| *(diagnostic)* S1b parity-swapped | 60 | +1.0865 | +0.6136 | [-0.1837, +2.1507] | +1.77 |
| *(diagnostic)* S2 parity-swapped | 60 | +0.4635 | +0.2934 | [-0.0772, +1.0737] | +1.58 |

### stratum:selfplay  (n=673 positions, 374 roots, champ arm scored on 673)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 673 | +0.9774 | +0.2340 | [+0.5502, +1.4665] | +4.18 |
| S1a σ²_arm — all (zeros added) [pts²] | 673 | +0.7058 | +0.1690 | [+0.3973, +1.0589] | +4.18 |
| S1b cross-fit gap G — discriminable [pts] | 673 | +0.6108 | +0.1360 | [+0.3438, +0.8775] | +4.49 |
| S1b cross-fit gap G — all [pts] | 673 | +0.4411 | +0.0982 | [+0.2483, +0.6336] | +4.49 |
| S2 headroom_J4 — discriminable [pts] | 673 | +0.3383 | +0.1065 | [+0.1286, +0.5471] | +3.18 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 673 | +0.2443 | +0.0769 | [+0.0929, +0.3950] | +3.18 |
| S2 headroom_J4 — all, zeros_strict | 673 | +0.2617 | +0.0824 | [+0.0995, +0.4232] | +3.18 |
| S2b leaf regret — discriminable [pts] | 673 | +0.3438 | +0.1098 | [+0.1310, +0.5577] | +3.13 |
| S2b leaf regret — all [pts] | 673 | +0.2483 | +0.0793 | [+0.0946, +0.4027] | +3.13 |
| *(audit only, never quoted)* naive range | 673 | +2.8556 | +0.0885 | [+2.6845, +3.0315] | +32.28 |
| *(audit only, never quoted)* naive champ regret | 673 | +1.4554 | +0.0729 | [+1.3148, +1.6004] | +19.98 |
| *(diagnostic)* S1b parity-swapped | 673 | +0.6367 | +0.1364 | [+0.3670, +0.9042] | +4.67 |
| *(diagnostic)* S2 parity-swapped | 673 | +0.3440 | +0.1046 | [+0.1373, +0.5519] | +3.29 |

### uncapped_only  (n=600 positions, 349 roots, champ arm scored on 600)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 600 | +0.9601 | +0.2640 | [+0.4806, +1.5111] | +3.64 |
| S1a σ²_arm — all (zeros added) [pts²] | 600 | +0.6954 | +0.1913 | [+0.3471, +1.0946] | +3.63 |
| S1b cross-fit gap G — discriminable [pts] | 600 | +0.6805 | +0.1521 | [+0.3884, +0.9750] | +4.48 |
| S1b cross-fit gap G — all [pts] | 600 | +0.4941 | +0.1109 | [+0.2805, +0.7086] | +4.45 |
| S2 headroom_J4 — discriminable [pts] | 600 | +0.3530 | +0.1106 | [+0.1380, +0.5706] | +3.19 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 600 | +0.2563 | +0.0802 | [+0.1002, +0.4140] | +3.19 |
| S2 headroom_J4 — all, zeros_strict | 600 | +0.2744 | +0.0859 | [+0.1073, +0.4433] | +3.19 |
| S2b leaf regret — discriminable [pts] | 600 | +0.3848 | +0.1193 | [+0.1513, +0.6136] | +3.22 |
| S2b leaf regret — all [pts] | 600 | +0.2783 | +0.0866 | [+0.1083, +0.4444] | +3.21 |
| *(audit only, never quoted)* naive range | 600 | +2.7301 | +0.0917 | [+2.5544, +2.9153] | +29.76 |
| *(audit only, never quoted)* naive champ regret | 600 | +1.3380 | +0.0714 | [+1.2016, +1.4813] | +18.75 |
| *(diagnostic)* S1b parity-swapped | 600 | +0.7607 | +0.1515 | [+0.4654, +1.0576] | +5.02 |
| *(diagnostic)* S2 parity-swapped | 600 | +0.3392 | +0.1045 | [+0.1360, +0.5422] | +3.25 |

⚠️ **S1b carries its sentence (§4.1):** `G` is a *downward-biased estimate of the true range and an unbiased test of the null*. The naive rows are printed ONLY so the winner's-curse correction is auditable (§4.2) and are never results.

## 5. The bound chain (§4.3) — the mandatory statement

### pooled

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.3526 | [+0.1502, +0.5568] | +34.49 | [+14.65, +54.73] | +21.06 |
| zeros_strict | +0.3774 | [+0.1608, +0.5960] | +36.94 | [+15.69, +58.66] | +22.55 |
| discriminable | +0.4851 | [+0.2061, +0.7660] | +47.60 | [+20.11, +75.86] | +29.01 |

### capped_only

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.3247 | [-0.1667, +0.8403] | +31.75 | [-16.26, +83.50] | +19.39 |
| zeros_strict | +0.3473 | [-0.1792, +0.8991] | +33.97 | [-17.48, +89.60] | +20.75 |
| discriminable | +0.4441 | [-0.2344, +1.1534] | +43.52 | [-22.89, +116.65] | +26.54 |

### phase:early

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.3079 | [-0.0389, +0.6662] | +30.09 | [-3.79, +65.73] | +18.38 |
| zeros_strict | +0.3297 | [-0.0416, +0.7137] | +32.24 | [-4.05, +70.54] | +19.69 |
| discriminable | +0.4250 | [-0.0531, +0.9205] | +41.63 | [-5.18, +91.82] | +25.40 |

### phase:late

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.4839 | [+0.2503, +0.7334] | +47.47 | [+24.45, +72.54] | +28.93 |
| zeros_strict | +0.5176 | [+0.2677, +0.7846] | +50.82 | [+26.15, +77.77] | +30.96 |
| discriminable | +0.6619 | [+0.3409, +1.0046] | +65.29 | [+33.34, +100.68] | +39.66 |

### phase:mid

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.2900 | [-0.0994, +0.6771] | +28.34 | [-9.69, +66.83] | +17.32 |
| zeros_strict | +0.3106 | [-0.1064, +0.7251] | +30.36 | [-10.38, +71.70] | +18.55 |
| discriminable | +0.4008 | [-0.1373, +0.9365] | +39.24 | [-13.39, +93.51] | +23.95 |

### profile:app_aug2

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +1.2763 | [nan, nan] | +130.21 | [nan, nan] | +77.39 |
| zeros_strict | +1.3569 | [nan, nan] | +139.31 | [nan, nan] | +82.46 |
| discriminable | +1.6625 | [nan, nan] | +175.68 | [nan, nan] | +102.01 |

### profile:fixed_v1

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.4841 | [-0.3071, +1.1690] | +47.50 | [-30.01, +118.36] | +28.95 |
| zeros_strict | +0.5147 | [-0.3265, +1.2429] | +50.54 | [-31.92, +126.49] | +30.79 |
| discriminable | +0.6307 | [-0.4000, +1.5228] | +62.14 | [-39.17, +158.65] | +37.77 |

### profile:walled

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.3382 | [+0.1292, +0.5486] | +33.08 | [+12.61, +53.92] | +20.20 |
| zeros_strict | +0.3623 | [+0.1384, +0.5878] | +35.45 | [+13.51, +57.84] | +21.64 |
| discriminable | +0.4685 | [+0.1791, +0.7594] | +45.95 | [+17.48, +75.19] | +28.01 |

### stratum:e4

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.4713 | [-0.2423, +1.0915] | +46.22 | [-23.67, +109.96] | +28.18 |
| zeros_strict | +0.5011 | [-0.2577, +1.1605] | +49.18 | [-25.16, +117.42] | +29.97 |
| discriminable | +0.6140 | [-0.3157, +1.4219] | +60.46 | [-30.86, +146.79] | +36.76 |

### stratum:selfplay

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.3420 | [+0.1301, +0.5530] | +33.45 | [+12.69, +54.36] | +20.43 |
| zeros_strict | +0.3664 | [+0.1393, +0.5925] | +35.85 | [+13.59, +58.31] | +21.89 |
| discriminable | +0.4736 | [+0.1801, +0.7659] | +46.46 | [+17.57, +75.86] | +28.32 |

### uncapped_only

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.3588 | [+0.1403, +0.5796] | +35.10 | [+13.68, +57.02] | +21.43 |
| zeros_strict | +0.3841 | [+0.1502, +0.6206] | +37.60 | [+14.66, +61.13] | +22.95 |
| discriminable | +0.4942 | [+0.1932, +0.7988] | +48.50 | [+18.85, +79.23] | +29.55 |

**σ_game sensitivity (§4.3)** on the headline elo CI-hi: σ=20.4 → +54.73 elo · σ=22.2 → +50.23 elo. elo scales as 1/σ_game, so the SMALLER σ is the larger, conservative-against-closure bound.

σ_game = **20.4** (§4.3: 20.4 `fixed_v1` / 22.2 `walled`); tied tile plies/game = **22.96** (census-measured); `Kelo` linear check = **97.5** elo per pt per tied tile ply.

⚠️ **§4.6 extrapolation, labelled:** the headline multiplies the measured `headroom_J4` by **1.4** to reach the full-set ceiling (order statistics a_n = {'2': 0.56, '4': 1.03, '8.55': 1.44}). That is an **extrapolation through the S1a spread estimate, never a measurement**. §4.4's thresholds are applied to the extrapolated figure so the cap cannot manufacture a closure. Realized capped fraction: **18.1%** of scored positions.

⚠️ **§4.3 caveats, inherited verbatim:** `NON_ADDITIVITY = 3.2` is **n = 1**, is calibrated at the TOP of the ladder, and the memo's range-consistent low-end divisor is ≈5.23. The divisor enters **linearly**, so this bound is quoted with a ±1.6× bracket, not as a point. The linear-φ step degrades above ~1σ.

## 6. §4.4 branch

### BRANCH 4 — INCONCLUSIVE

Report the estimate and its CI; promote nothing. The realized sd and the n required for a +-17-elo bound are stated below so the extension decision is arithmetic.

- read-rule: `|z| < 2.0` is **no conviction**. S1a z = **+4.26** (conviction) · S2 z = **+3.43** (conviction).
- `branch_3_condition_also_met` = **False** (spread CI excludes 0: True). ⚠️ See interpretation **I4** — branch 3 is unreachable under the pre-registered precedence; the flag is reported rather than the precedence silently re-ordered.
- §4.4 stratum rule: Strata agree in sign (or only one is present); the pooled estimate is primary per §4.4. (stratum means {'e4': 0.3366582491582492, 'selfplay': 0.24429989270386263}, n {'e4': 60, 'selfplay': 673})

**Sizing (mandatory on branch 4, reported always):** realized per-position sd = **+1.9697 pts**, cluster-robust se = **+0.0735 pts** at n = 733 over 399 roots. A ±17-elo bound needs 2·se ≤ +0.1742 pts ⇒ **n ≈ 1023**; a ±35-elo bound ⇒ **n ≈ 243** (composite scale included).

**§4.5 epsilon band (secondary, EXTRAPOLATION):** census tie rates eps=0.0 → 0.660, eps=0.05 → 0.666, eps=0.2 → 0.690, eps=0.5 → 0.723, eps=1.0 → 0.799. Stretched elo CI-hi: 0.0 → +54.73, 0.05 → +55.21, 0.2 → +57.28, 0.5 → +59.99, 1.0 → +66.29.

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
