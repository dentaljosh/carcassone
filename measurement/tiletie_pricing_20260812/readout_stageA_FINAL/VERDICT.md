# TILE-TIE PRICING — READ-OUT

**Status: COMPLETE for the scope declared below.**

Pre-registration: [DESIGN.md](../DESIGN.md) — every estimator below is §4, implemented before any record was read. Generated `2026-08-13T07:56:06Z`.

## 1. Completion accounting

- planned positions in scope: **340** · fully scored: **340** · partially scored: **0** · absent: **0**
- positions ENTERING the statistics: **340** (`include_partial_arms=False`)

| profile | planned | complete | partial | absent |
|---|---|---|---|---|
| app_aug2 | 3 | 3 | 0 | 0 |
| fixed_v1 | 53 | 53 | 0 | 0 |
| walled | 284 | 284 | 0 | 0 |

| stratum | planned | complete | partial | absent |
|---|---|---|---|---|
| e4 | 60 | 60 | 0 | 0 |
| selfplay | 280 | 280 | 0 | 0 |

**What is missing, stated loudly:** COMPLETE for the profiles in scope — every planned leg record is present.

## 2. The §0.A analytic zeros (all-transposition positions)

Count source: per-stratum, from the full-supply plan /home/doctor/projects/carcassone/measurement/tiletie_pricing_20260812/positions/POSITIONS_PLAN.json + the dropped index

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

### pooled  (n=340 positions, 247 roots, champ arm scored on 340)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 340 | +0.7004 | +0.2799 | [+0.1678, +1.2652] | +2.50 |
| S1a σ²_arm — all (zeros added) [pts²] | 340 | +0.5111 | +0.2052 | [+0.1218, +0.9265] | +2.49 |
| S1b cross-fit gap G — discriminable [pts] | 340 | +0.5347 | +0.2112 | [+0.1167, +0.9447] | +2.53 |
| S1b cross-fit gap G — all [pts] | 340 | +0.3924 | +0.1555 | [+0.0852, +0.6937] | +2.52 |
| S2 headroom_J4 — discriminable [pts] | 340 | +0.3112 | +0.1383 | [+0.0380, +0.5829] | +2.25 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 340 | +0.2283 | +0.1010 | [+0.0284, +0.4268] | +2.26 |
| S2 headroom_J4 — all, zeros_strict | 340 | +0.2440 | +0.1081 | [+0.0300, +0.4565] | +2.26 |
| S2b leaf regret — discriminable [pts] | 340 | +0.2608 | +0.1478 | [-0.0270, +0.5511] | +1.77 |
| S2b leaf regret — all [pts] | 340 | +0.1891 | +0.1078 | [-0.0223, +0.4014] | +1.75 |
| *(audit only, never quoted)* naive range | 340 | +2.8666 | +0.1238 | [+2.6263, +3.1136] | +23.16 |
| *(audit only, never quoted)* naive champ regret | 340 | +1.4293 | +0.1003 | [+1.2353, +1.6298] | +14.25 |
| *(diagnostic)* S1b parity-swapped | 340 | +0.6757 | +0.1992 | [+0.2812, +1.0558] | +3.39 |
| *(diagnostic)* S2 parity-swapped | 340 | +0.2680 | +0.1502 | [-0.0298, +0.5603] | +1.78 |

### capped_only  (n=66 positions, 62 roots, champ arm scored on 66)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 66 | +1.2517 | +0.5427 | [+0.3078, +2.4035] | +2.31 |
| S1a σ²_arm — all (zeros added) [pts²] | 66 | +0.9117 | +0.3942 | [+0.2251, +1.7451] | +2.31 |
| S1b cross-fit gap G — discriminable [pts] | 66 | +0.4706 | +0.4538 | [-0.4058, +1.3580] | +1.04 |
| S1b cross-fit gap G — all [pts] | 66 | +0.3480 | +0.3305 | [-0.2908, +0.9952] | +1.05 |
| S2 headroom_J4 — discriminable [pts] | 66 | +0.4015 | +0.3778 | [-0.3070, +1.1510] | +1.06 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 66 | +0.2958 | +0.2740 | [-0.2184, +0.8378] | +1.08 |
| S2 headroom_J4 — all, zeros_strict | 66 | +0.3161 | +0.2934 | [-0.2344, +0.8964] | +1.08 |
| S2b leaf regret — discriminable [pts] | 66 | -0.0388 | +0.3326 | [-0.6835, +0.6135] | -0.12 |
| S2b leaf regret — all [pts] | 66 | -0.0283 | +0.2431 | [-0.4991, +0.4499] | -0.12 |
| *(audit only, never quoted)* naive range | 66 | +3.4995 | +0.3092 | [+2.9233, +4.1288] | +11.32 |
| *(audit only, never quoted)* naive champ regret | 66 | +2.0118 | +0.2934 | [+1.4632, +2.6043] | +6.86 |
| *(diagnostic)* S1b parity-swapped | 66 | +0.5047 | +0.4209 | [-0.2822, +1.3340] | +1.20 |
| *(diagnostic)* S2 parity-swapped | 66 | +0.5956 | +0.4550 | [-0.2556, +1.5038] | +1.31 |

### phase:early  (n=147 positions, 121 roots, champ arm scored on 147)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 147 | +0.0242 | +0.4569 | [-0.8423, +0.9303] | +0.05 |
| S1a σ²_arm — all (zeros added) [pts²] | 147 | +0.0244 | +0.3369 | [-0.6116, +0.6922] | +0.07 |
| S1b cross-fit gap G — discriminable [pts] | 147 | +0.0089 | +0.3527 | [-0.6796, +0.6909] | +0.03 |
| S1b cross-fit gap G — all [pts] | 147 | +0.0144 | +0.2591 | [-0.4923, +0.5162] | +0.06 |
| S2 headroom_J4 — discriminable [pts] | 147 | +0.1161 | +0.2113 | [-0.2964, +0.5244] | +0.55 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 147 | +0.0853 | +0.1538 | [-0.2142, +0.3824] | +0.55 |
| S2 headroom_J4 — all, zeros_strict | 147 | +0.0912 | +0.1646 | [-0.2295, +0.4093] | +0.55 |
| S2b leaf regret — discriminable [pts] | 147 | +0.0179 | +0.2439 | [-0.4565, +0.4893] | +0.07 |
| S2b leaf regret — all [pts] | 147 | +0.0123 | +0.1771 | [-0.3322, +0.3548] | +0.07 |
| *(audit only, never quoted)* naive range | 147 | +3.2304 | +0.1968 | [+2.8503, +3.6186] | +16.42 |
| *(audit only, never quoted)* naive champ regret | 147 | +1.5249 | +0.1643 | [+1.2165, +1.8614] | +9.28 |
| *(diagnostic)* S1b parity-swapped | 147 | +0.1067 | +0.3645 | [-0.6013, +0.8154] | +0.29 |
| *(diagnostic)* S2 parity-swapped | 147 | -0.3065 | +0.2515 | [-0.8019, +0.1879] | -1.22 |

### phase:late  (n=100 positions, 92 roots, champ arm scored on 100)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 100 | +1.3818 | +0.4532 | [+0.5912, +2.3607] | +3.05 |
| S1a σ²_arm — all (zeros added) [pts²] | 100 | +1.0074 | +0.3286 | [+0.4342, +1.7151] | +3.07 |
| S1b cross-fit gap G — discriminable [pts] | 100 | +1.1400 | +0.2312 | [+0.7068, +1.6131] | +4.93 |
| S1b cross-fit gap G — all [pts] | 100 | +0.8318 | +0.1682 | [+0.5167, +1.1763] | +4.95 |
| S2 headroom_J4 — discriminable [pts] | 100 | +0.3700 | +0.1567 | [+0.0689, +0.6784] | +2.36 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 100 | +0.2760 | +0.1155 | [+0.0550, +0.5037] | +2.39 |
| S2 headroom_J4 — all, zeros_strict | 100 | +0.2945 | +0.1234 | [+0.0583, +0.5376] | +2.39 |
| S2b leaf regret — discriminable [pts] | 100 | +0.6306 | +0.2002 | [+0.2537, +1.0462] | +3.15 |
| S2b leaf regret — all [pts] | 100 | +0.4602 | +0.1456 | [+0.1861, +0.7616] | +3.16 |
| *(audit only, never quoted)* naive range | 100 | +2.0144 | +0.1873 | [+1.6638, +2.3965] | +10.76 |
| *(audit only, never quoted)* naive champ regret | 100 | +0.9769 | +0.1270 | [+0.7363, +1.2300] | +7.69 |
| *(diagnostic)* S1b parity-swapped | 100 | +1.2244 | +0.2265 | [+0.7907, +1.6776] | +5.41 |
| *(diagnostic)* S2 parity-swapped | 100 | +0.7031 | +0.1906 | [+0.3358, +1.0807] | +3.69 |

### phase:mid  (n=93 positions, 84 roots, champ arm scored on 93)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 93 | +1.0365 | +0.4823 | [+0.1405, +2.0079] | +2.15 |
| S1a σ²_arm — all (zeros added) [pts²] | 93 | +0.7468 | +0.3491 | [+0.0990, +1.4496] | +2.14 |
| S1b cross-fit gap G — discriminable [pts] | 93 | +0.7151 | +0.4135 | [-0.0976, +1.5071] | +1.73 |
| S1b cross-fit gap G — all [pts] | 93 | +0.5174 | +0.3026 | [-0.0762, +1.0959] | +1.71 |
| S2 headroom_J4 — discriminable [pts] | 93 | +0.5565 | +0.3302 | [-0.0754, +1.1986] | +1.69 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 93 | +0.4029 | +0.2395 | [-0.0553, +0.8684] | +1.68 |
| S2 headroom_J4 — all, zeros_strict | 93 | +0.4315 | +0.2564 | [-0.0594, +0.9299] | +1.68 |
| S2b leaf regret — discriminable [pts] | 93 | +0.2473 | +0.3189 | [-0.3743, +0.8544] | +0.78 |
| S2b leaf regret — all [pts] | 93 | +0.1771 | +0.2339 | [-0.2797, +0.6220] | +0.76 |
| *(audit only, never quoted)* naive range | 93 | +3.2080 | +0.2471 | [+2.7389, +3.6965] | +12.98 |
| *(audit only, never quoted)* naive champ regret | 93 | +1.7648 | +0.2295 | [+1.3349, +2.2296] | +7.69 |
| *(diagnostic)* S1b parity-swapped | 93 | +0.9852 | +0.3685 | [+0.2791, +1.7102] | +2.67 |
| *(diagnostic)* S2 parity-swapped | 93 | +0.7083 | +0.3380 | [+0.0560, +1.3694] | +2.10 |

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

### profile:walled  (n=284 positions, 224 roots, champ arm scored on 284)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 284 | +0.7569 | +0.3010 | [+0.1808, +1.3690] | +2.51 |
| S1a σ²_arm — all (zeros added) [pts²] | 284 | +0.5493 | +0.2180 | [+0.1315, +0.9917] | +2.52 |
| S1b cross-fit gap G — discriminable [pts] | 284 | +0.5114 | +0.2150 | [+0.0928, +0.9300] | +2.38 |
| S1b cross-fit gap G — all [pts] | 284 | +0.3709 | +0.1557 | [+0.0686, +0.6733] | +2.38 |
| S2 headroom_J4 — discriminable [pts] | 284 | +0.2760 | +0.1510 | [-0.0167, +0.5726] | +1.83 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 284 | +0.1991 | +0.1090 | [-0.0120, +0.4129] | +1.83 |
| S2 headroom_J4 — all, zeros_strict | 284 | +0.2133 | +0.1168 | [-0.0129, +0.4425] | +1.83 |
| S2b leaf regret — discriminable [pts] | 284 | +0.3072 | +0.1637 | [-0.0122, +0.6290] | +1.88 |
| S2b leaf regret — all [pts] | 284 | +0.2225 | +0.1184 | [-0.0082, +0.4552] | +1.88 |
| *(audit only, never quoted)* naive range | 284 | +2.9251 | +0.1366 | [+2.6603, +3.2054] | +21.41 |
| *(audit only, never quoted)* naive champ regret | 284 | +1.4445 | +0.1131 | [+1.2284, +1.6709] | +12.77 |
| *(diagnostic)* S1b parity-swapped | 284 | +0.6437 | +0.2115 | [+0.2246, +1.0677] | +3.04 |
| *(diagnostic)* S2 parity-swapped | 284 | +0.2273 | +0.1693 | [-0.1117, +0.5578] | +1.34 |

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

### stratum:selfplay  (n=280 positions, 222 roots, champ arm scored on 280)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 280 | +0.7072 | +0.2986 | [+0.1457, +1.3162] | +2.37 |
| S1a σ²_arm — all (zeros added) [pts²] | 280 | +0.5107 | +0.2157 | [+0.1052, +0.9504] | +2.37 |
| S1b cross-fit gap G — discriminable [pts] | 280 | +0.4828 | +0.2142 | [+0.0700, +0.9032] | +2.25 |
| S1b cross-fit gap G — all [pts] | 280 | +0.3486 | +0.1547 | [+0.0506, +0.6522] | +2.25 |
| S2 headroom_J4 — discriminable [pts] | 280 | +0.2839 | +0.1528 | [-0.0131, +0.5859] | +1.86 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 280 | +0.2050 | +0.1104 | [-0.0095, +0.4231] | +1.86 |
| S2 headroom_J4 — all, zeros_strict | 280 | +0.2196 | +0.1182 | [-0.0101, +0.4533] | +1.86 |
| S2b leaf regret — discriminable [pts] | 280 | +0.2960 | +0.1644 | [-0.0287, +0.6164] | +1.80 |
| S2b leaf regret — all [pts] | 280 | +0.2137 | +0.1187 | [-0.0207, +0.4451] | +1.80 |
| *(audit only, never quoted)* naive range | 280 | +2.8871 | +0.1326 | [+2.6332, +3.1517] | +21.77 |
| *(audit only, never quoted)* naive champ regret | 280 | +1.4444 | +0.1147 | [+1.2270, +1.6724] | +12.59 |
| *(diagnostic)* S1b parity-swapped | 280 | +0.5877 | +0.2023 | [+0.1937, +0.9875] | +2.91 |
| *(diagnostic)* S2 parity-swapped | 280 | +0.2261 | +0.1718 | [-0.1132, +0.5575] | +1.32 |

### uncapped_only  (n=274 positions, 207 roots, champ arm scored on 274)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 274 | +0.5676 | +0.3094 | [-0.0170, +1.1754] | +1.83 |
| S1a σ²_arm — all (zeros added) [pts²] | 274 | +0.4146 | +0.2265 | [-0.0141, +0.8592] | +1.83 |
| S1b cross-fit gap G — discriminable [pts] | 274 | +0.5502 | +0.2323 | [+0.0874, +0.9926] | +2.37 |
| S1b cross-fit gap G — all [pts] | 274 | +0.4031 | +0.1713 | [+0.0604, +0.7281] | +2.35 |
| S2 headroom_J4 — discriminable [pts] | 274 | +0.2895 | +0.1459 | [-0.0029, +0.5742] | +1.98 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 274 | +0.2120 | +0.1068 | [-0.0010, +0.4200] | +1.98 |
| S2 headroom_J4 — all, zeros_strict | 274 | +0.2267 | +0.1142 | [-0.0015, +0.4492] | +1.98 |
| S2b leaf regret — discriminable [pts] | 274 | +0.3330 | +0.1683 | [+0.0020, +0.6663] | +1.98 |
| S2b leaf regret — all [pts] | 274 | +0.2415 | +0.1229 | [-0.0004, +0.4841] | +1.96 |
| *(audit only, never quoted)* naive range | 274 | +2.7142 | +0.1280 | [+2.4667, +2.9674] | +21.21 |
| *(audit only, never quoted)* naive champ regret | 274 | +1.2890 | +0.1002 | [+1.0940, +1.4897] | +12.86 |
| *(diagnostic)* S1b parity-swapped | 274 | +0.7169 | +0.2188 | [+0.2745, +1.1319] | +3.28 |
| *(diagnostic)* S2 parity-swapped | 274 | +0.1891 | +0.1495 | [-0.1056, +0.4796] | +1.26 |

⚠️ **S1b carries its sentence (§4.1):** `G` is a *downward-biased estimate of the true range and an unbiased test of the null*. The naive rows are printed ONLY so the winner's-curse correction is auditable (§4.2) and are never results.

## 5. The bound chain (§4.3) — the mandatory statement

### pooled

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.3196 | [+0.0398, +0.5975] | +31.24 | [+3.88, +58.81] | +19.08 |
| zeros_strict | +0.3417 | [+0.0420, +0.6391] | +33.42 | [+4.09, +63.00] | +20.41 |
| discriminable | +0.4357 | [+0.0531, +0.8161] | +42.69 | [+5.18, +81.01] | +26.04 |

### capped_only

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.4141 | [-0.3058, +1.1729] | +40.56 | [-29.89, +118.78] | +24.75 |
| zeros_strict | +0.4425 | [-0.3281, +1.2549] | +43.37 | [-32.08, +127.82] | +26.45 |
| discriminable | +0.5621 | [-0.4298, +1.6113] | +55.27 | [-42.11, +169.36] | +33.64 |

### phase:early

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.1194 | [-0.2999, +0.5353] | +11.64 | [-29.31, +52.59] | +7.12 |
| zeros_strict | +0.1276 | [-0.3213, +0.5730] | +12.45 | [-31.41, +56.36] | +7.61 |
| discriminable | +0.1625 | [-0.4149, +0.7341] | +15.85 | [-40.64, +72.62] | +9.70 |

### phase:late

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.3865 | [+0.0770, +0.7051] | +37.83 | [+7.51, +69.67] | +23.09 |
| zeros_strict | +0.4123 | [+0.0817, +0.7526] | +40.38 | [+7.96, +74.50] | +24.64 |
| discriminable | +0.5180 | [+0.0965, +0.9498] | +50.87 | [+9.41, +94.89] | +30.98 |

### phase:mid

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.5640 | [-0.0774, +1.2157] | +55.46 | [-7.55, +123.48] | +33.75 |
| zeros_strict | +0.6041 | [-0.0831, +1.3018] | +59.47 | [-8.11, +133.08] | +36.17 |
| discriminable | +0.7790 | [-0.1056, +1.6780] | +77.20 | [-10.30, +177.62] | +46.75 |

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
| headline | +0.2787 | [-0.0168, +0.5781] | +27.23 | [-1.64, +56.87] | +16.64 |
| zeros_strict | +0.2987 | [-0.0181, +0.6195] | +29.19 | [-1.76, +61.02] | +17.83 |
| discriminable | +0.3864 | [-0.0233, +0.8017] | +37.82 | [-2.27, +79.53] | +23.08 |

### stratum:e4

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.4713 | [-0.2423, +1.0915] | +46.22 | [-23.67, +109.96] | +28.18 |
| zeros_strict | +0.5011 | [-0.2577, +1.1605] | +49.18 | [-25.16, +117.42] | +29.97 |
| discriminable | +0.6140 | [-0.3157, +1.4219] | +60.46 | [-30.86, +146.79] | +36.76 |

### stratum:selfplay

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.2870 | [-0.0132, +0.5923] | +28.05 | [-1.29, +58.29] | +17.14 |
| zeros_strict | +0.3075 | [-0.0142, +0.6346] | +30.06 | [-1.38, +62.54] | +18.36 |
| discriminable | +0.3975 | [-0.0183, +0.8203] | +38.92 | [-1.79, +81.44] | +23.75 |

### uncapped_only

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.2968 | [-0.0014, +0.5879] | +29.00 | [-0.14, +57.85] | +17.72 |
| zeros_strict | +0.3174 | [-0.0021, +0.6289] | +31.03 | [-0.20, +61.97] | +18.95 |
| discriminable | +0.4052 | [-0.0040, +0.8039] | +39.68 | [-0.39, +79.75] | +24.21 |

**σ_game sensitivity (§4.3)** on the headline elo CI-hi: σ=20.4 → +58.81 elo · σ=22.2 → +53.97 elo. elo scales as 1/σ_game, so the SMALLER σ is the larger, conservative-against-closure bound.

σ_game = **20.4** (§4.3: 20.4 `fixed_v1` / 22.2 `walled`); tied tile plies/game = **22.96** (census-measured); `Kelo` linear check = **97.5** elo per pt per tied tile ply.

⚠️ **§4.6 extrapolation, labelled:** the headline multiplies the measured `headroom_J4` by **1.4** to reach the full-set ceiling (order statistics a_n = {'2': 0.56, '4': 1.03, '8.55': 1.44}). That is an **extrapolation through the S1a spread estimate, never a measurement**. §4.4's thresholds are applied to the extrapolated figure so the cap cannot manufacture a closure. Realized capped fraction: **19.4%** of scored positions.

⚠️ **§4.3 caveats, inherited verbatim:** `NON_ADDITIVITY = 3.2` is **n = 1**, is calibrated at the TOP of the ladder, and the memo's range-consistent low-end divisor is ≈5.23. The divisor enters **linearly**, so this bound is quoted with a ±1.6× bracket, not as a point. The linear-φ step degrades above ~1σ.

## 6. §4.4 branch

### BRANCH 4 — INCONCLUSIVE

Report the estimate and its CI; promote nothing. The realized sd and the n required for a +-17-elo bound are stated below so the extension decision is arithmetic.

- read-rule: `|z| < 2.0` is **no conviction**. S1a z = **+2.49** (conviction) · S2 z = **+2.26** (conviction).
- `branch_3_condition_also_met` = **False** (spread CI excludes 0: True). ⚠️ See interpretation **I4** — branch 3 is unreachable under the pre-registered precedence; the flag is reported rather than the precedence silently re-ordered.
- §4.4 stratum rule: Strata agree in sign (or only one is present); the pooled estimate is primary per §4.4. (stratum means {'e4': 0.3366582491582492, 'selfplay': 0.20502567443286326}, n {'e4': 60, 'selfplay': 280})

**Sizing (mandatory on branch 4, reported always):** realized per-position sd = **+1.8423 pts**, cluster-robust se = **+0.1010 pts** at n = 340 over 247 roots. A ±17-elo bound needs 2·se ≤ +0.1742 pts ⇒ **n ≈ 896**; a ±35-elo bound ⇒ **n ≈ 213** (composite scale included).

**§4.5 epsilon band (secondary, EXTRAPOLATION):** census tie rates eps=0.0 → 0.660, eps=0.05 → 0.666, eps=0.2 → 0.690, eps=0.5 → 0.723, eps=1.0 → 0.799. Stretched elo CI-hi: 0.0 → +58.81, 0.05 → +59.33, 0.2 → +61.55, 0.5 → +64.46, 1.0 → +71.23.

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
