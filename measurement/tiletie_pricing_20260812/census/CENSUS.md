# TILE-decision leaf top-2 tie census — CENSUS.md

Generated 2026-08-12T23:43:30Z · git `83023d6` · leaf hash `a36d2e15a3b3d71d` (assert OK) · 2607 rows total.

Wall clock: 13.8s total (8 workers, split {'app_aug2': 1, 'fixed_v1': 1, 'walled': 6}) · mean seconds/ply (leaf compute only) = 0.019166896816263906.

> **Timing caveat:** the census ran alongside an unrelated multi-worker oracle_score_pilot smoke (6-8 workers, fixed_v1/clair-puct + tier1-greedy probes) on the same 32-thread box, so the wall-clock and seconds/ply figures below are CONTENDED -- they are an upper bound on cost, not a clean throughput measurement. The tie RATES and tied-set SIZES are unaffected by contention (they are deterministic leaf arithmetic evaluated once per row); only the timing numbers are.

Question: does the JCZ corpus's reported top-2 exact-tie rate of **55.1%** (7,817/14,190, `scripts/jcz_mining/mine_disagreements.py`) replicate on our own position distributions?

## 1. Exact-tie rate (and the full `TIE_EPS_GRID`)

| group | n | exact tie (eps=0.0) 95% CI | eps=0.05 | eps=0.2 | eps=0.5 | eps=1.0 |
|---|---:|---|---|---|---|---|
| e4|ALL|ALL | 912 | 65.5% [62.3, 68.5] (597/912) | 65.8% [62.7, 68.8] (600/912) | 68.6% [65.6, 71.6] (626/912) | 71.5% [68.5, 74.3] (652/912) | 80.6% [77.9, 83.0] (735/912) |
| e4|e4_games|app_aug2 | 35 | 68.6% [52.0, 81.4] (24/35) | 68.6% [52.0, 81.4] (24/35) | 71.4% [54.9, 83.7] (25/35) | 77.1% [61.0, 87.9] (27/35) | 82.9% [67.3, 91.9] (29/35) |
| e4|e4_games|fixed_v1 | 805 | 66.2% [62.9, 69.4] (533/805) | 66.5% [63.1, 69.6] (535/805) | 69.2% [65.9, 72.3] (557/805) | 71.9% [68.7, 74.9] (579/805) | 80.5% [77.6, 83.1] (648/805) |
| e4|e4_games|walled | 72 | 55.6% [44.1, 66.5] (40/72) | 56.9% [45.4, 67.7] (41/72) | 61.1% [49.6, 71.5] (44/72) | 63.9% [52.4, 74.0] (46/72) | 80.6% [70.0, 88.0] (58/72) |
| selfplay|ALL|ALL | 1695 | 66.3% [64.0, 68.5] (1123/1695) | 67.0% [64.7, 69.2] (1135/1695) | 69.3% [67.0, 71.4] (1174/1695) | 72.7% [70.6, 74.8] (1233/1695) | 79.5% [77.5, 81.4] (1348/1695) |
| selfplay|bank|walled | 495 | 64.0% [59.7, 68.1] (317/495) | 64.6% [60.3, 68.7] (320/495) | 68.1% [63.8, 72.0] (337/495) | 70.7% [66.6, 74.5] (350/495) | 77.6% [73.7, 81.0] (384/495) |
| selfplay|champ_games|walled | 1200 | 67.2% [64.5, 69.8] (806/1200) | 67.9% [65.2, 70.5] (815/1200) | 69.8% [67.1, 72.3] (837/1200) | 73.6% [71.0, 76.0] (883/1200) | 80.3% [78.0, 82.5] (964/1200) |
| ALL|ALL|ALL | 2607 | 66.0% [64.1, 67.8] (1720/2607) | 66.6% [64.7, 68.3] (1735/2607) | 69.0% [67.2, 70.8] (1800/2607) | 72.3% [70.6, 74.0] (1885/2607) | 79.9% [78.3, 81.4] (2083/2607) |

- `e4|e4_games|app_aug2`: 68.6% vs JCZ 55.1% -> **REPLICATES**
- `e4|e4_games|fixed_v1`: 66.2% vs JCZ 55.1% -> **HIGHER**
- `e4|e4_games|walled`: 55.6% vs JCZ 55.1% -> **REPLICATES**
- `selfplay|bank|walled`: 64.0% vs JCZ 55.1% -> **HIGHER**
- `selfplay|champ_games|walled`: 67.2% vs JCZ 55.1% -> **HIGHER**

## 2. Tied-set SIZE distribution (exact ties only)

| group | n_tied | mean | median | size=2 | size=3 | size=4 | size=5 | size=6 | size=7 | size=8 | size=9-12 | size=13+ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| e4|ALL|ALL | 597 | 8.46 | 4 | 221 | 70 | 113 | 12 | 25 | 7 | 30 | 17 | 102 |
| e4|e4_games|app_aug2 | 24 | 15.79 | 4 | 7 | 1 | 5 | 0 | 0 | 0 | 0 | 1 | 10 |
| e4|e4_games|fixed_v1 | 533 | 8.24 | 4 | 199 | 62 | 97 | 12 | 25 | 6 | 29 | 15 | 88 |
| e4|e4_games|walled | 40 | 7.08 | 3 | 15 | 7 | 11 | 0 | 0 | 1 | 1 | 1 | 4 |
| selfplay|ALL|ALL | 1123 | 8.60 | 4 | 435 | 118 | 199 | 17 | 51 | 14 | 47 | 51 | 191 |
| selfplay|bank|walled | 317 | 9.51 | 3 | 123 | 36 | 54 | 3 | 4 | 3 | 16 | 15 | 63 |
| selfplay|champ_games|walled | 806 | 8.24 | 4 | 312 | 82 | 145 | 14 | 47 | 11 | 31 | 36 | 128 |
| ALL|ALL|ALL | 1720 | 8.55 | 4 | 656 | 188 | 312 | 29 | 76 | 21 | 77 | 68 | 293 |

(pct at size 2 vs size >=5, ALL|ALL|ALL): 38.1% vs 32.8%

## 3. Top-2 gap distribution among NON-exact-tie plies

| group | n | min | p1 | p5 | p10 | p25 | p50 | p75 | p90 | max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| e4|ALL|ALL | 315 | 0.0000 | 0.1000 | 0.1500 | 0.2500 | 0.7500 | 1.4000 | 3.0000 | 5.7800 | 24.2500 |
| e4|e4_games|app_aug2 | 11 | 0.2000 | 0.2050 | 0.2250 | 0.2500 | 0.6250 | 1.4000 | 1.8500 | 3.0000 | 5.5000 |
| e4|e4_games|fixed_v1 | 272 | 0.0000 | 0.1000 | 0.1500 | 0.2500 | 0.8000 | 1.5000 | 3.0000 | 5.8900 | 24.2500 |
| e4|e4_games|walled | 32 | 0.0000 | 0.0465 | 0.1500 | 0.1600 | 0.7250 | 1.0000 | 2.2500 | 5.1250 | 10.0000 |
| selfplay|ALL|ALL | 572 | 0.0000 | 0.0000 | 0.1000 | 0.2500 | 0.7500 | 1.5000 | 3.2500 | 6.0000 | 21.9500 |
| selfplay|bank|walled | 178 | 0.0000 | 0.0500 | 0.1425 | 0.1500 | 0.7500 | 1.8000 | 3.5125 | 6.3250 | 15.7500 |
| selfplay|champ_games|walled | 394 | 0.0000 | 0.0000 | 0.1000 | 0.2500 | 0.7500 | 1.5000 | 3.2375 | 5.5000 | 21.9500 |
| ALL|ALL|ALL | 887 | 0.0000 | 0.0000 | 0.1500 | 0.2500 | 0.7500 | 1.5000 | 3.1750 | 6.0000 | 24.2500 |

**Top-20 most common exact gap values (`ALL|ALL|ALL`)** — the lattice:

| gap value | count |
|---:|---:|
| 1.000000 | 94 |
| 3.000000 | 34 |
| 0.250000 | 28 |
| 1.500000 | 28 |
| 2.000000 | 23 |
| 0.500000 | 19 |
| 4.000000 | 19 |
| 0.750000 | 18 |
| 0.150000 | 15 |
| 1.250000 | 14 |
| 2.500000 | 13 |
| 2.250000 | 11 |
| 5.000000 | 10 |
| 0.100000 | 10 |
| 6.000000 | 10 |
| 1.750000 | 10 |
| 0.600000 | 10 |
| 5.500000 | 9 |
| 0.150000 | 8 |
| 3.750000 | 8 |

## 4. Phase trend — exact-tie rate + mean tied size

**e4|ALL|ALL** (n=912)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 288 | 71.5% | 4.38 |
| phase_bucket | mid | 289 | 61.2% | 8.29 |
| phase_bucket | late | 335 | 63.9% | 12.54 |
| tercile | 0 | 311 | 72.0% | 4.30 |
| tercile | 1 | 311 | 60.8% | 8.43 |
| tercile | 2 | 290 | 63.4% | 13.56 |
| n_legal quartile | Q1 (<=18) | 249 | 69.5% | 4.02 |
| n_legal quartile | Q2 (<=28) | 239 | 64.0% | 6.55 |
| n_legal quartile | Q3 (<=37) | 199 | 59.8% | 10.25 |
| n_legal quartile | Q4 (>37) | 225 | 67.6% | 14.05 |

**e4|e4_games|app_aug2** (n=35)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 11 | 72.7% | 5.75 |
| phase_bucket | mid | 11 | 72.7% | 13.12 |
| phase_bucket | late | 13 | 61.5% | 28.50 |
| tercile | 0 | 12 | 75.0% | 5.33 |
| tercile | 1 | 12 | 66.7% | 13.12 |
| tercile | 2 | 11 | 63.6% | 32.29 |
| n_legal quartile | Q1 (<=18) | 9 | 66.7% | 4.33 |
| n_legal quartile | Q2 (<=31) | 10 | 60.0% | 6.83 |
| n_legal quartile | Q3 (<=35) | 8 | 87.5% | 25.57 |
| n_legal quartile | Q4 (>35) | 8 | 62.5% | 26.60 |

**e4|e4_games|fixed_v1** (n=805)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 253 | 70.8% | 4.41 |
| phase_bucket | mid | 254 | 61.8% | 7.83 |
| phase_bucket | late | 298 | 66.1% | 12.04 |
| tercile | 0 | 275 | 71.3% | 4.33 |
| tercile | 1 | 275 | 61.5% | 8.03 |
| tercile | 2 | 255 | 65.9% | 13.01 |
| n_legal quartile | Q1 (<=18) | 213 | 71.4% | 4.02 |
| n_legal quartile | Q2 (<=28) | 209 | 63.2% | 6.63 |
| n_legal quartile | Q3 (<=38) | 193 | 62.2% | 10.30 |
| n_legal quartile | Q4 (>38) | 190 | 67.9% | 12.94 |

**e4|e4_games|walled** (n=72)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 24 | 79.2% | 3.58 |
| phase_bucket | mid | 24 | 50.0% | 11.00 |
| phase_bucket | late | 24 | 37.5% | 9.22 |
| tercile | 0 | 24 | 79.2% | 3.58 |
| tercile | 1 | 24 | 50.0% | 11.00 |
| tercile | 2 | 24 | 37.5% | 9.22 |
| n_legal quartile | Q1 (<=17) | 21 | 52.4% | 3.64 |
| n_legal quartile | Q2 (<=22) | 18 | 61.1% | 5.36 |
| n_legal quartile | Q3 (<=32) | 15 | 66.7% | 5.10 |
| n_legal quartile | Q4 (>32) | 18 | 44.4% | 16.62 |

**selfplay|ALL|ALL** (n=1695)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 529 | 69.4% | 4.02 |
| phase_bucket | mid | 587 | 60.8% | 6.45 |
| phase_bucket | late | 579 | 68.9% | 14.74 |
| tercile | 0 | 529 | 69.4% | 4.02 |
| tercile | 1 | 608 | 61.2% | 6.41 |
| tercile | 2 | 558 | 68.8% | 15.10 |
| n_legal quartile | Q1 (<=18) | 437 | 66.4% | 3.88 |
| n_legal quartile | Q2 (<=28) | 467 | 64.2% | 5.59 |
| n_legal quartile | Q3 (<=36) | 368 | 62.8% | 9.26 |
| n_legal quartile | Q4 (>36) | 423 | 71.4% | 15.62 |

**selfplay|bank|walled** (n=495)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 148 | 64.9% | 3.35 |
| phase_bucket | mid | 179 | 57.5% | 7.04 |
| phase_bucket | late | 168 | 70.2% | 16.68 |
| tercile | 0 | 148 | 64.9% | 3.35 |
| tercile | 1 | 184 | 58.2% | 6.94 |
| tercile | 2 | 163 | 69.9% | 17.11 |
| n_legal quartile | Q1 (<=18) | 124 | 61.3% | 3.55 |
| n_legal quartile | Q2 (<=28) | 135 | 60.7% | 6.60 |
| n_legal quartile | Q3 (<=37) | 115 | 60.9% | 9.27 |
| n_legal quartile | Q4 (>37) | 121 | 73.6% | 17.47 |

**selfplay|champ_games|walled** (n=1200)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 381 | 71.1% | 4.25 |
| phase_bucket | mid | 408 | 62.3% | 6.20 |
| phase_bucket | late | 411 | 68.4% | 13.93 |
| tercile | 0 | 381 | 71.1% | 4.25 |
| tercile | 1 | 424 | 62.5% | 6.19 |
| tercile | 2 | 395 | 68.4% | 14.26 |
| n_legal quartile | Q1 (<=18) | 313 | 68.4% | 4.00 |
| n_legal quartile | Q2 (<=28) | 287 | 63.4% | 5.31 |
| n_legal quartile | Q3 (<=36) | 304 | 65.5% | 8.59 |
| n_legal quartile | Q4 (>36) | 296 | 71.3% | 14.74 |

**ALL|ALL|ALL** (n=2607)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 817 | 70.1% | 4.15 |
| phase_bucket | mid | 876 | 61.0% | 7.06 |
| phase_bucket | late | 914 | 67.1% | 13.97 |
| tercile | 0 | 840 | 70.4% | 4.13 |
| tercile | 1 | 919 | 61.0% | 7.09 |
| tercile | 2 | 848 | 67.0% | 14.60 |
| n_legal quartile | Q1 (<=18) | 686 | 67.5% | 3.93 |
| n_legal quartile | Q2 (<=28) | 706 | 64.2% | 5.91 |
| n_legal quartile | Q3 (<=37) | 586 | 60.9% | 9.61 |
| n_legal quartile | Q4 (>37) | 629 | 71.1% | 15.17 |

## 5. `played_in_tieset_exact` / `played_is_argmax`

| group | n (with action_played) | played in exact tie-set | played == argmax |
|---|---:|---|---|
| e4|ALL|ALL | 912 | 82.5% [79.9, 84.8] (752/912) | 58.8% [55.5, 61.9] (536/912) |
| e4|e4_games|app_aug2 | 35 | 85.7% [70.6, 93.7] (30/35) | 34.3% [20.8, 50.8] (12/35) |
| e4|e4_games|fixed_v1 | 805 | 83.0% [80.2, 85.4] (668/805) | 60.1% [56.7, 63.5] (484/805) |
| e4|e4_games|walled | 72 | 75.0% [63.9, 83.6] (54/72) | 55.6% [44.1, 66.5] (40/72) |
| selfplay|ALL|ALL | 1695 | 86.0% [84.2, 87.5] (1457/1695) | 61.8% [59.5, 64.1] (1048/1695) |
| selfplay|bank|walled | 495 | 89.3% [86.3, 91.7] (442/495) | 65.7% [61.4, 69.7] (325/495) |
| selfplay|champ_games|walled | 1200 | 84.6% [82.4, 86.5] (1015/1200) | 60.2% [57.5, 63.0] (723/1200) |
| ALL|ALL|ALL | 2607 | 84.7% [83.3, 86.1] (2209/2607) | 60.8% [58.9, 62.6] (1584/2607) |

## 6. What this census does NOT show

This is a **leaf-silence** census: it counts how often the production leaf assigns the SAME value to the top TILE placement(s), and how big that tied set is. It says **nothing** about whether the tied moves differ in true VALUE — a leaf tie is consistent with the tied moves being genuinely equally good, or with the leaf being blind to a real difference between them. Answering that requires an oracle/search-based scoring pass over the tied moves, which this census deliberately does not run (leaf evaluations only, no search, no oracle scoring — see the GOAL spec this census answers to).
