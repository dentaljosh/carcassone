# TILE-TIE PRICING — READ-OUT

**Status: ⛔ SUPERSEDED 2026-08-13 — DO NOT CITE. This is the preliminary walled/rust-arm-only
read (n=284 of the planned 340, E4 python arm still scoring at the time). The authoritative Stage-A
numbers are [`readout_stageA_FINAL/VERDICT.md`](../readout_stageA_FINAL/VERDICT.md) (n=340, all
arms).** The verdict did not change on completion (pre-registered **branch 4, INCONCLUSIVE** in
both), but every number here is superseded — notably the sizing figure: this read says a ±17-elo
bound needs **n ≈ 872**, the FINAL says **n ≈ 896**, and the FINAL is the one to quote.
Kept on disk only as the record of what was known mid-run.

*(Original banner: PRELIMINARY — Stage A walled/rust arm ONLY (E4 python arm still scoring) — COMPLETE for the scope declared below.)*

Pre-registration: [DESIGN.md](../DESIGN.md) — every estimator below is §4, implemented before any record was read. Generated `2026-08-13T04:47:02Z`.

## 1. Completion accounting

- planned positions in scope: **284** · fully scored: **284** · partially scored: **0** · absent: **0**
- positions ENTERING the statistics: **284** (`include_partial_arms=False`)

| profile | planned | complete | partial | absent |
|---|---|---|---|---|
| walled | 284 | 284 | 0 | 0 |

| stratum | planned | complete | partial | absent |
|---|---|---|---|---|
| e4 | 4 | 4 | 0 | 0 |
| selfplay | 280 | 280 | 0 | 0 |

**What is missing, stated loudly:** COMPLETE for the profiles in scope — every planned leg record is present. ⚠️ SCOPE RESTRICTED to profiles ['walled']: the other arms of the plan are NOT in this read-out at all.

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

### pooled  (n=284 positions, 224 roots, champ arm scored on 284)

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

### capped_only  (n=57 positions, 55 roots, champ arm scored on 57)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 57 | +1.4041 | +0.6137 | [+0.3279, +2.7131] | +2.29 |
| S1a σ²_arm — all (zeros added) [pts²] | 57 | +1.0209 | +0.4447 | [+0.2400, +1.9673] | +2.30 |
| S1b cross-fit gap G — discriminable [pts] | 57 | +0.4846 | +0.5109 | [-0.5108, +1.4763] | +0.95 |
| S1b cross-fit gap G — all [pts] | 57 | +0.3567 | +0.3708 | [-0.3652, +1.0761] | +0.96 |
| S2 headroom_J4 — discriminable [pts] | 57 | +0.3388 | +0.4240 | [-0.4565, +1.1830] | +0.80 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 57 | +0.2457 | +0.3062 | [-0.3288, +0.8551] | +0.80 |
| S2 headroom_J4 — all, zeros_strict | 57 | +0.2631 | +0.3280 | [-0.3523, +0.9161] | +0.80 |
| S2b leaf regret — discriminable [pts] | 57 | +0.1020 | +0.3755 | [-0.6328, +0.8326] | +0.27 |
| S2b leaf regret — all [pts] | 57 | +0.0801 | +0.2736 | [-0.4537, +0.6125] | +0.29 |
| *(audit only, never quoted)* naive range | 57 | +3.5521 | +0.3337 | [+2.9126, +4.2232] | +10.65 |
| *(audit only, never quoted)* naive champ regret | 57 | +2.0104 | +0.3209 | [+1.4187, +2.6652] | +6.26 |
| *(diagnostic)* S1b parity-swapped | 57 | +0.6118 | +0.4802 | [-0.3192, +1.5571] | +1.27 |
| *(diagnostic)* S2 parity-swapped | 57 | +0.6535 | +0.5151 | [-0.3318, +1.6775] | +1.27 |

### phase:early  (n=122 positions, 107 roots, champ arm scored on 122)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 122 | -0.0166 | +0.4798 | [-0.9174, +0.9325] | -0.03 |
| S1a σ²_arm — all (zeros added) [pts²] | 122 | -0.0057 | +0.3490 | [-0.6616, +0.6836] | -0.02 |
| S1b cross-fit gap G — discriminable [pts] | 122 | -0.1163 | +0.3774 | [-0.8698, +0.6100] | -0.31 |
| S1b cross-fit gap G — all [pts] | 122 | -0.0802 | +0.2740 | [-0.6277, +0.4459] | -0.29 |
| S2 headroom_J4 — discriminable [pts] | 122 | +0.0922 | +0.2393 | [-0.3720, +0.5577] | +0.39 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 122 | +0.0662 | +0.1729 | [-0.2697, +0.4022] | +0.38 |
| S2 headroom_J4 — all, zeros_strict | 122 | +0.0709 | +0.1852 | [-0.2888, +0.4309] | +0.38 |
| S2b leaf regret — discriminable [pts] | 122 | +0.0722 | +0.2871 | [-0.5046, +0.6260] | +0.25 |
| S2b leaf regret — all [pts] | 122 | +0.0538 | +0.2078 | [-0.3643, +0.4550] | +0.26 |
| *(audit only, never quoted)* naive range | 122 | +3.2725 | +0.2188 | [+2.8613, +3.7082] | +14.96 |
| *(audit only, never quoted)* naive champ regret | 122 | +1.5884 | +0.1889 | [+1.2362, +1.9692] | +8.41 |
| *(diagnostic)* S1b parity-swapped | 122 | -0.0102 | +0.3987 | [-0.7866, +0.7594] | -0.03 |
| *(diagnostic)* S2 parity-swapped | 122 | -0.3335 | +0.2945 | [-0.9104, +0.2426] | -1.13 |

### phase:late  (n=83 positions, 80 roots, champ arm scored on 83)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 83 | +1.4121 | +0.5271 | [+0.5178, +2.5787] | +2.68 |
| S1a σ²_arm — all (zeros added) [pts²] | 83 | +1.0197 | +0.3806 | [+0.3739, +1.8621] | +2.68 |
| S1b cross-fit gap G — discriminable [pts] | 83 | +1.1453 | +0.2630 | [+0.6619, +1.6837] | +4.36 |
| S1b cross-fit gap G — all [pts] | 83 | +0.8270 | +0.1899 | [+0.4780, +1.2158] | +4.36 |
| S2 headroom_J4 — discriminable [pts] | 83 | +0.2116 | +0.1577 | [-0.0911, +0.5221] | +1.34 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 83 | +0.1528 | +0.1139 | [-0.0658, +0.3770] | +1.34 |
| S2 headroom_J4 — all, zeros_strict | 83 | +0.1637 | +0.1220 | [-0.0705, +0.4039] | +1.34 |
| S2b leaf regret — discriminable [pts] | 83 | +0.6310 | +0.2287 | [+0.2131, +1.1057] | +2.76 |
| S2b leaf regret — all [pts] | 83 | +0.4557 | +0.1651 | [+0.1539, +0.7984] | +2.76 |
| *(audit only, never quoted)* naive range | 83 | +2.0407 | +0.2124 | [+1.6521, +2.4827] | +9.61 |
| *(audit only, never quoted)* naive champ regret | 83 | +0.8498 | +0.1268 | [+0.6153, +1.1037] | +6.70 |
| *(diagnostic)* S1b parity-swapped | 83 | +1.2673 | +0.2483 | [+0.8133, +1.7660] | +5.10 |
| *(diagnostic)* S2 parity-swapped | 83 | +0.5753 | +0.1916 | [+0.2168, +0.9583] | +3.00 |

### phase:mid  (n=79 positions, 72 roots, champ arm scored on 79)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 79 | +1.2630 | +0.5514 | [+0.2522, +2.3821] | +2.29 |
| S1a σ²_arm — all (zeros added) [pts²] | 79 | +0.9120 | +0.3982 | [+0.1821, +1.7202] | +2.29 |
| S1b cross-fit gap G — discriminable [pts] | 79 | +0.8149 | +0.4318 | [-0.0276, +1.6579] | +1.89 |
| S1b cross-fit gap G — all [pts] | 79 | +0.5884 | +0.3118 | [-0.0199, +1.1972] | +1.89 |
| S2 headroom_J4 — discriminable [pts] | 79 | +0.6274 | +0.3735 | [-0.0945, +1.3675] | +1.68 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 79 | +0.4530 | +0.2697 | [-0.0683, +0.9875] | +1.68 |
| S2 headroom_J4 — all, zeros_strict | 79 | +0.4853 | +0.2890 | [-0.0731, +1.0579] | +1.68 |
| S2b leaf regret — discriminable [pts] | 79 | +0.3299 | +0.3264 | [-0.3057, +0.9704] | +1.01 |
| S2b leaf regret — all [pts] | 79 | +0.2382 | +0.2357 | [-0.2208, +0.7007] | +1.01 |
| *(audit only, never quoted)* naive range | 79 | +3.3176 | +0.2772 | [+2.7887, +3.8758] | +11.97 |
| *(audit only, never quoted)* naive champ regret | 79 | +1.8473 | +0.2607 | [+1.3608, +2.3754] | +7.09 |
| *(diagnostic)* S1b parity-swapped | 79 | +0.9984 | +0.4033 | [+0.2102, +1.7995] | +2.48 |
| *(diagnostic)* S2 parity-swapped | 79 | +0.7278 | +0.3765 | [-0.0166, +1.4647] | +1.93 |

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

### stratum:e4  (n=4 positions, 2 roots, champ arm scored on 4)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 4 | +4.2345 | +3.3992 | [-2.5638, +6.5006] | +1.25 |
| S1a σ²_arm — all (zeros added) [pts²] | 4 | +3.2507 | +2.6095 | [-1.9682, +4.9904] | +1.25 |
| S1b cross-fit gap G — discriminable [pts] | 4 | +2.5156 | +2.4766 | [-2.4375, +4.1667] | +1.02 |
| S1b cross-fit gap G — all [pts] | 4 | +1.9312 | +1.9012 | [-1.8712, +3.1987] | +1.02 |
| S2 headroom_J4 — discriminable [pts] | 4 | -0.2812 | +1.0781 | [-2.4375, +0.4375] | -0.26 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 4 | -0.2159 | +0.8277 | [-1.8712, +0.3359] | -0.26 |
| S2 headroom_J4 — all, zeros_strict | 4 | -0.2295 | +0.8799 | [-1.9894, +0.3571] | -0.26 |
| S2b leaf regret — discriminable [pts] | 4 | +1.0938 | +1.7344 | [-2.3750, +2.2500] | +0.63 |
| S2b leaf regret — all [pts] | 4 | +0.8396 | +1.3314 | [-1.8232, +1.7273] | +0.63 |
| *(audit only, never quoted)* naive range | 4 | +5.5859 | +1.5742 | [+2.4375, +6.6354] | +3.55 |
| *(audit only, never quoted)* naive champ regret | 4 | +1.4531 | +0.0547 | [+1.4167, +1.5625] | +26.57 |
| *(diagnostic)* S1b parity-swapped | 4 | +4.5625 | +3.8438 | [-3.1250, +7.1250] | +1.19 |
| *(diagnostic)* S2 parity-swapped | 4 | +0.3125 | +0.1562 | [+0.0000, +0.4167] | +2.00 |

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

### uncapped_only  (n=227 positions, 187 roots, champ arm scored on 227)

| statistic | n | mean | se (cluster) | 95% CI (boot) | z |
|---|---|---|---|---|---|
| S1a σ²_arm — discriminable [pts²] ⭐PRIMARY | 227 | +0.5944 | +0.3352 | [-0.0461, +1.2745] | +1.77 |
| S1a σ²_arm — all (zeros added) [pts²] | 227 | +0.4308 | +0.2423 | [-0.0323, +0.9235] | +1.78 |
| S1b cross-fit gap G — discriminable [pts] | 227 | +0.5182 | +0.2316 | [+0.0676, +0.9730] | +2.24 |
| S1b cross-fit gap G — all [pts] | 227 | +0.3745 | +0.1673 | [+0.0489, +0.7035] | +2.24 |
| S2 headroom_J4 — discriminable [pts] | 227 | +0.2602 | +0.1574 | [-0.0472, +0.5658] | +1.65 |
| S2 headroom_J4 — all [pts] ⭐DELIVERABLE | 227 | +0.1874 | +0.1137 | [-0.0346, +0.4085] | +1.65 |
| S2 headroom_J4 — all, zeros_strict | 227 | +0.2008 | +0.1218 | [-0.0370, +0.4377] | +1.65 |
| S2b leaf regret — discriminable [pts] | 227 | +0.3588 | +0.1842 | [+0.0008, +0.7257] | +1.95 |
| S2b leaf regret — all [pts] | 227 | +0.2583 | +0.1331 | [+0.0001, +0.5234] | +1.94 |
| *(audit only, never quoted)* naive range | 227 | +2.7676 | +0.1442 | [+2.4910, +3.0599] | +19.19 |
| *(audit only, never quoted)* naive champ regret | 227 | +1.3025 | +0.1134 | [+1.0821, +1.5277] | +11.49 |
| *(diagnostic)* S1b parity-swapped | 227 | +0.6517 | +0.2256 | [+0.2081, +1.0943] | +2.89 |
| *(diagnostic)* S2 parity-swapped | 227 | +0.1203 | +0.1692 | [-0.2135, +0.4452] | +0.71 |

⚠️ **S1b carries its sentence (§4.1):** `G` is a *downward-biased estimate of the true range and an unbiased test of the null*. The naive rows are printed ONLY so the winner's-curse correction is auditable (§4.2) and are never results.

## 5. The bound chain (§4.3) — the mandatory statement

### pooled

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.2787 | [-0.0168, +0.5781] | +27.23 | [-1.64, +56.87] | +16.64 |
| zeros_strict | +0.2987 | [-0.0181, +0.6195] | +29.19 | [-1.76, +61.02] | +17.83 |
| discriminable | +0.3864 | [-0.0233, +0.8017] | +37.82 | [-2.27, +79.53] | +23.08 |

### capped_only

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.3440 | [-0.4603, +1.1971] | +33.64 | [-45.14, +121.43] | +20.55 |
| zeros_strict | +0.3683 | [-0.4932, +1.2825] | +36.04 | [-48.40, +130.91] | +22.00 |
| discriminable | +0.4743 | [-0.6391, +1.6562] | +46.52 | [-62.99, +174.90] | +28.36 |

### phase:early

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.0926 | [-0.3775, +0.5631] | +9.03 | [-36.95, +55.37] | +5.53 |
| zeros_strict | +0.0993 | [-0.4044, +0.6033] | +9.69 | [-39.60, +59.39] | +5.93 |
| discriminable | +0.1291 | [-0.5208, +0.7807] | +12.59 | [-51.14, +77.37] | +7.70 |

### phase:late

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.2139 | [-0.0921, +0.5278] | +20.88 | [-8.98, +51.84] | +12.77 |
| zeros_strict | +0.2292 | [-0.0987, +0.5654] | +22.37 | [-9.62, +55.60] | +13.68 |
| discriminable | +0.2962 | [-0.1276, +0.7309] | +28.95 | [-12.44, +72.29] | +17.69 |

### phase:mid

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.6342 | [-0.0956, +1.3824] | +62.50 | [-9.32, +142.24] | +37.99 |
| zeros_strict | +0.6795 | [-0.1024, +1.4810] | +67.07 | [-9.99, +153.70] | +40.72 |
| discriminable | +0.8783 | [-0.1323, +1.9145] | +87.44 | [-12.91, +208.56] | +52.80 |

### profile:walled

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.2787 | [-0.0168, +0.5781] | +27.23 | [-1.64, +56.87] | +16.64 |
| zeros_strict | +0.2987 | [-0.0181, +0.6195] | +29.19 | [-1.76, +61.02] | +17.83 |
| discriminable | +0.3864 | [-0.0233, +0.8017] | +37.82 | [-2.27, +79.53] | +23.08 |

### stratum:e4

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | -0.3023 | [-2.6197, +0.4702] | -29.54 | [-326.54, +46.11] | -18.05 |
| zeros_strict | -0.3214 | [-2.7852, +0.4999] | -31.42 | [-364.62, +49.06] | -19.19 |
| discriminable | -0.3937 | [-3.4125, +0.6125] | -38.55 | [-665.93, +60.32] | -23.53 |

### stratum:selfplay

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.2870 | [-0.0132, +0.5923] | +28.05 | [-1.29, +58.29] | +17.14 |
| zeros_strict | +0.3075 | [-0.0142, +0.6346] | +30.06 | [-1.38, +62.54] | +18.36 |
| discriminable | +0.3975 | [-0.0183, +0.8203] | +38.92 | [-1.79, +81.44] | +23.75 |

### uncapped_only

| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | elo 95% CI | elo (÷5.23 low-end) |
|---|---|---|---|---|---|
| headline | +0.2623 | [-0.0485, +0.5718] | +25.63 | [-4.73, +56.24] | +15.66 |
| zeros_strict | +0.2812 | [-0.0518, +0.6127] | +27.47 | [-5.05, +60.34] | +16.79 |
| discriminable | +0.3643 | [-0.0661, +0.7922] | +35.64 | [-6.45, +78.55] | +21.76 |

**σ_game sensitivity (§4.3)** on the headline elo CI-hi: σ=20.4 → +56.87 elo · σ=22.2 → +52.19 elo. elo scales as 1/σ_game, so the SMALLER σ is the larger, conservative-against-closure bound.

σ_game = **20.4** (§4.3: 20.4 `fixed_v1` / 22.2 `walled`); tied tile plies/game = **22.96** (census-measured); `Kelo` linear check = **97.5** elo per pt per tied tile ply.

⚠️ **§4.6 extrapolation, labelled:** the headline multiplies the measured `headroom_J4` by **1.4** to reach the full-set ceiling (order statistics a_n = {'2': 0.56, '4': 1.03, '8.55': 1.44}). That is an **extrapolation through the S1a spread estimate, never a measurement**. §4.4's thresholds are applied to the extrapolated figure so the cap cannot manufacture a closure. Realized capped fraction: **20.1%** of scored positions.

⚠️ **§4.3 caveats, inherited verbatim:** `NON_ADDITIVITY = 3.2` is **n = 1**, is calibrated at the TOP of the ladder, and the memo's range-consistent low-end divisor is ≈5.23. The divisor enters **linearly**, so this bound is quoted with a ±1.6× bracket, not as a point. The linear-φ step degrades above ~1σ.

## 6. §4.4 branch

### BRANCH 4 — INCONCLUSIVE

Report the estimate and its CI; promote nothing. The realized sd and the n required for a +-17-elo bound are stated below so the extension decision is arithmetic.

- read-rule: `|z| < 2.0` is **no conviction**. S1a z = **+2.52** (conviction) · S2 z = **+1.83** (NO conviction).
- `branch_3_condition_also_met` = **False** (spread CI excludes 0: True). ⚠️ See interpretation **I4** — branch 3 is unreachable under the pre-registered precedence; the flag is reported rather than the precedence silently re-ordered.
- §4.4 stratum rule: §4.4 FORBIDS pooling: the strata disagree in sign. Read them separately. ⚠️ BUT the sign flip involves stratum(s) ['e4'] at n = {'e4': 4} -- far below any resolving n. The rule is applied mechanically as pre-registered; the flip is NOT evidence of a real stratum difference at this n. (stratum means {'e4': -0.21590909090909094, 'selfplay': 0.20502567443286326}, n {'e4': 4, 'selfplay': 280})

**Sizing (mandatory on branch 4, reported always):** realized per-position sd = **+1.8816 pts**, cluster-robust se = **+0.1090 pts** at n = 284 over 224 roots. A ±17-elo bound needs 2·se ≤ +0.1742 pts ⇒ **n ≈ 872**; a ±35-elo bound ⇒ **n ≈ 207** (composite scale included).

**§4.5 epsilon band (secondary, EXTRAPOLATION):** census tie rates eps=0.0 → 0.660, eps=0.05 → 0.666, eps=0.2 → 0.690, eps=0.5 → 0.723, eps=1.0 → 0.799. Stretched elo CI-hi: 0.0 → +56.87, 0.05 → +57.36, 0.2 → +59.51, 0.5 → +62.32, 1.0 → +68.87.

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
