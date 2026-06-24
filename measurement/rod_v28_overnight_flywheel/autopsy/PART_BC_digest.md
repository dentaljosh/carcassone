# Autopsy Part B/C — iter_08 ROOT-move audit (the decisive toward/away-h3200 test)

Merged 1000 positions (iter08 labels ∩ ROOT_AUDIT_V28). v2.8 leaf, NeuralMCTS@200/c3.0,
best_action selector, net-on-CPU — identical method to the cached rod/parent labels.

## Root-move agreement vs heur@3200_v28 (top-1), by band
band | n | iter08≡h3200 | RoD1≡h3200 | parent≡h3200 | **Δ(iter08−RoD1)** | iter08≡RoD1 | iter08≡parent
--- | --- | --- | --- | --- | --- | --- | ---
opening | 200 | 0.570 | 0.540 | 0.585 | +0.030 | 0.645 | 0.620
early_mid | 200 | 0.575 | 0.570 | 0.595 | +0.005 | 0.615 | 0.610
mid | 200 | 0.530 | 0.475 | 0.495 | +0.055 | 0.540 | 0.525
late_mid | 200 | 0.445 | 0.480 | 0.475 | -0.035 | 0.530 | 0.500
pre_endgame | 200 | 0.485 | 0.490 | 0.450 | -0.005 | 0.500 | 0.485
**ALL** | 1000 | 0.521 | 0.511 | 0.520 | **+0.010** | 0.566 | 0.548

## Toward/away decomposition (iter_08's divergence FROM RoD1)

- **ALL**: iter08 diverged from RoD1 on 434/1000 (43.4%): toward h3200=101, away=91, neither=242 → net +10 (h3200-ALIGNED)
- **opening**: iter08 diverged from RoD1 on 71/200 (35.5%): toward h3200=22, away=16, neither=33 → net +6 (h3200-ALIGNED)
- **early_mid**: iter08 diverged from RoD1 on 77/200 (38.5%): toward h3200=20, away=19, neither=38 → net +1 (h3200-ALIGNED)
- **mid**: iter08 diverged from RoD1 on 92/200 (46.0%): toward h3200=27, away=16, neither=49 → net +11 (h3200-ALIGNED)
- **late_mid**: iter08 diverged from RoD1 on 94/200 (47.0%): toward h3200=12, away=19, neither=63 → net -7 (ANTI-aligned)
- **pre_endgame**: iter08 diverged from RoD1 on 100/200 (50.0%): toward h3200=20, away=21, neither=59 → net -1 (ANTI-aligned)

## Part C (lite) — iter_08's most CONFIDENT distinctive picks
(positions where iter08 disagrees with BOTH RoD1 and h3200, sorted by iter08 root visit-share;
these are iter08's stylistic signature moves — candidates for move-level inspection)

position_id | band | k | n_legal? | iter08 | rod | h3200 | it_top1_share | it_rootv
--- | --- | --- | --- | --- | --- | --- | --- | ---
hybrid_8_3200_s3503000011_K16 | late_mid | 16 | — | 1548 | 747 | 1324 | 0.935 | 0.99361
iter8_s3501000038_K52 | opening | 52 | — | 1159 | 1359 | 1359 | 0.915 | 0.40809
hybrid_8_3200_s3503000026_K52 | opening | 52 | — | 1157 | 1259 | 1259 | 0.85 | 0.67232
iter8_s3501000003_K52 | opening | 52 | — | 1333 | 1449 | 1449 | 0.77 | 0.54632
heur3200_s3502000029_K40 | early_mid | 40 | — | 1455 | 959 | 959 | 0.725 | -0.26276
iter8_s3501000022_K28 | mid | 28 | — | 1366 | 1367 | 1365 | 0.7 | 0.75186
heur3200_s3502000024_K16 | late_mid | 16 | — | 1749 | 1657 | 1657 | 0.68 | 0.98138
greedy_s3500000034_K40 | early_mid | 40 | — | 1467 | 1148 | 1148 | 0.645 | 0.93701
iter8_s3501000011_K10 | pre_endgame | 10 | — | 869 | 1528 | 1118 | 0.645 | 0.6628
greedy_s3500000037_K52 | opening | 52 | — | 1160 | 1343 | 1343 | 0.615 | 0.35103
iter8_s3501000041_K10 | pre_endgame | 10 | — | 650 | 837 | 1957 | 0.57 | 0.10808
iter8_s3501000045_K16 | late_mid | 16 | — | 829 | 1061 | 1572 | 0.555 | 0.19135
heur3200_s3502000013_K10 | pre_endgame | 10 | — | 1257 | 1432 | 1432 | 0.55 | 0.25242
greedy_s3500000021_K16 | late_mid | 16 | — | 1252 | 861 | 861 | 0.5 | -0.31325
greedy_s3500000048_K10 | pre_endgame | 10 | — | 934 | 1128 | 745 | 0.49 | -0.941
greedy_s3500000049_K40 | early_mid | 40 | — | 858 | 1536 | 1536 | 0.48 | 0.81435
heur3200_s3502000018_K28 | mid | 28 | — | 1343 | 1450 | 1450 | 0.48 | 0.45995
hybrid_8_3200_s3503000000_K16 | late_mid | 16 | — | 1432 | 1843 | 1360 | 0.48 | -0.33071
hybrid_8_3200_s3503000032_K52 | opening | 52 | — | 1260 | 850 | 850 | 0.47 | 0.55522
greedy_s3500000016_K28 | mid | 28 | — | 1055 | 1259 | 1259 | 0.465 | 0.95007
greedy_s3500000035_K28 | mid | 28 | — | 961 | 960 | 962 | 0.455 | 0.08773
greedy_s3500000048_K28 | mid | 28 | — | 664 | 1364 | 1364 | 0.45 | -0.81066
greedy_s3500000049_K52 | opening | 52 | — | 1357 | 1545 | 848 | 0.45 | 0.59812
hybrid_8_3200_s3503000016_K52 | opening | 52 | — | 1644 | 1548 | 1548 | 0.45 | 0.12561
heur3200_s3502000001_K40 | early_mid | 40 | — | 1132 | 1652 | 1652 | 0.44 | 0.71578

Full table CSV: measurement/rod_v28_overnight_flywheel/autopsy/root_disagreement_iter08.csv
iter08 labels: measurement/rod_v28_overnight_flywheel/autopsy/iter08_root_labels.jsonl