# Phase 5 — Midgame Disagreement Taxonomy (top cases)

> **Diagnostic labels, not claims** (teacher = heur@3200, soft target). Category is a coarse
> mechanism guess from the competing actions' features. Cases ranked by teacher confidence
> (`gap_q`) with priority to *v2.7-misses-but-iter8-agrees* (the net adds value over static)
> and *v2.7-agrees-but-iter8-misses* (the net throws value away). Raw record: replay
> `replay_actions(seed, prefix)` from MIDGAME_POSITION_SAMPLE.jsonl.

Total disagreement cases (iter8≠teacher OR v2.7≠teacher): **667** / 1000 positions.
- iter8 ≠ teacher: **513**  ·  v2.7-static ≠ teacher: **520**
- v2.7 misses but iter8 agrees (net beats static): **154**
- v2.7 agrees but iter8 misses (net throws it away): **147**

## Category counts (all disagreement cases)

| category | count |
|---|---|
| structural/unclear | 471 |
| structural/closure | 133 |
| meeple-economy | 27 |
| completion/score-greed | 21 |
| bag/scarcity | 9 |
| immediate-score | 6 |

## Top 60 cases by teacher-confidence priority

| pid | band | k | n_leg | gap_q | category | flags | teacher/iter8/v27 | Qs(t/i8/v27) |
|---|---|---|---|---|---|---|---|---|
| heur3200_s3502000042_K10 | pre_endgame | 10 | 54 | 0.1866 | structural/unclear | NET<STATIC,i8miss | 1670/1142/1670 | 0.81283/0.62626/0.81283 |
| greedy_s3500000027_K40 | early_mid | 40 | 16 | 0.2272 | structural/closure | NET>STATIC,v27miss | 1369/1369/957 | -0.11699/-0.11699/-0.41996 |
| greedy_s3500000028_K16 | late_mid | 16 | 54 | 0.0937 | completion/score-greed | NET<STATIC,i8miss | 1167/1556/1167 | -0.23879/-0.33251/-0.23879 |
| greedy_s3500000018_K52 | opening | 52 | 52 | 0.0735 | structural/unclear | NET<STATIC,i8miss | 1444/1548/1444 | 0.13491/-0.15592/0.13491 |
| greedy_s3500000021_K10 | pre_endgame | 10 | 58 | 0.0706 | structural/unclear | NET<STATIC,i8miss | 1256/1444/1256 | 0.15459/0.084/0.15459 |
| heur3200_s3502000046_K16 | late_mid | 16 | 40 | 0.0703 | structural/unclear | NET<STATIC,i8miss | 1641/932/1641 | -0.08019/-0.15361/-0.08019 |
| heur3200_s3502000033_K52 | opening | 52 | 32 | 0.0615 | structural/closure | NET<STATIC,i8miss | 1037/940/1037 | -0.04284/-0.10437/-0.04284 |
| heur3200_s3502000039_K16 | late_mid | 16 | 33 | 0.0579 | structural/unclear | NET<STATIC,i8miss | 1328/660/1328 | 0.28279/0.22184/0.28279 |
| greedy_s3500000041_K40 | early_mid | 40 | 40 | 0.055 | structural/unclear | NET<STATIC,i8miss | 1045/1067/1045 | -0.16316/-0.22918/-0.16316 |
| hybrid_8_3200_s3503000047_K28 | mid | 28 | 27 | 0.0515 | structural/closure | NET<STATIC,i8miss | 1141/967/1141 | 0.14175/0.03807/0.14175 |
| greedy_s3500000014_K40 | early_mid | 40 | 16 | 0.0463 | structural/closure | NET<STATIC,i8miss | 1069/1449/1069 | 0.20723/0.15759/0.20723 |
| iter8_s3501000047_K40 | early_mid | 40 | 30 | 0.0462 | completion/score-greed | NET<STATIC,i8miss | 1227/1130/1227 | -0.15452/-0.2202/-0.15452 |
| greedy_s3500000002_K52 | opening | 52 | 23 | 0.0413 | structural/unclear | NET<STATIC,i8miss | 1156/1248/1156 | -0.1652/-0.20648/-0.1652 |
| greedy_s3500000041_K28 | mid | 28 | 39 | 0.041 | structural/closure | NET<STATIC,i8miss | 855/1131/855 | -0.75165/-0.7944/-0.75165 |
| heur3200_s3502000003_K10 | pre_endgame | 10 | 40 | 0.0355 | structural/unclear | NET<STATIC,i8miss | 1046/1844/1046 | -0.66978/-0.70523/-0.66978 |
| heur3200_s3502000047_K10 | pre_endgame | 10 | 43 | 0.0348 | structural/unclear | NET<STATIC,i8miss | 1474/449/1474 | 0.97584/0.92383/0.97584 |
| iter8_s3501000000_K40 | early_mid | 40 | 26 | 0.0344 | structural/unclear | NET<STATIC,i8miss | 1137/1032/1137 | 0.28723/0.21348/0.28723 |
| hybrid_8_3200_s3503000042_K52 | opening | 52 | 28 | 0.0334 | structural/unclear | NET<STATIC,i8miss | 1453/1045/1453 | 0.47982/0.44646/0.47982 |
| heur3200_s3502000012_K40 | early_mid | 40 | 14 | 0.0322 | structural/unclear | NET<STATIC,i8miss | 1044/1649/1044 | -0.55451/-0.59225/-0.55451 |
| iter8_s3501000003_K52 | opening | 52 | 12 | 0.0307 | structural/closure | NET<STATIC,i8miss | 1333/1559/1333 | 0.46779/0.4317/0.46779 |
| iter8_s3501000003_K10 | pre_endgame | 10 | 28 | 0.0296 | structural/unclear | NET<STATIC,i8miss | 1855/1546/1855 | 0.76196/0.73238/0.76196 |
| greedy_s3500000010_K52 | opening | 52 | 14 | 0.0291 | structural/unclear | NET<STATIC,i8miss | 1260/1357/1260 | 0.32705/0.29799/0.32705 |
| hybrid_8_3200_s3503000025_K10 | pre_endgame | 10 | 38 | 0.0289 | structural/unclear | NET<STATIC,i8miss | 1763/1848/1763 | 0.89894/0.87006/0.89894 |
| hybrid_8_3200_s3503000001_K40 | early_mid | 40 | 20 | 0.0284 | structural/unclear | NET<STATIC,i8miss | 948/1754/948 | -0.49658/-0.57345/-0.49658 |
| greedy_s3500000038_K52 | opening | 52 | 26 | 0.0265 | structural/closure | NET<STATIC,i8miss | 1460/1041/1460 | -0.42038/-0.44684/-0.42038 |
| heur3200_s3502000033_K40 | early_mid | 40 | 22 | 0.0263 | structural/closure | NET<STATIC,i8miss | 1438/737/1438 | -0.38691/-0.41323/-0.38691 |
| heur3200_s3502000015_K40 | early_mid | 40 | 28 | 0.0238 | completion/score-greed | NET<STATIC,i8miss | 1541/1168/1541 | -0.33223/-0.36351/-0.33223 |
| heur3200_s3502000038_K10 | pre_endgame | 10 | 31 | 0.0236 | bag/scarcity | NET<STATIC,i8miss | 1042/1748/1042 | 0.5422/0.51857/0.5422 |
| greedy_s3500000011_K10 | pre_endgame | 10 | 44 | 0.0232 | structural/unclear | NET<STATIC,i8miss | 1161/1031/1161 | -0.72228/-0.7467/-0.72228 |
| heur3200_s3502000036_K10 | pre_endgame | 10 | 35 | 0.0222 | completion/score-greed | NET<STATIC,i8miss | 1242/844/1242 | -0.70995/-0.73214/-0.70995 |
| greedy_s3500000043_K40 | early_mid | 40 | 50 | 0.0206 | completion/score-greed | NET<STATIC,i8miss | 1236/952/1236 | 0.37857/0.34029/0.37857 |
| iter8_s3501000034_K28 | mid | 28 | 33 | 0.0186 | structural/unclear | NET<STATIC,i8miss | 1553/1535/1553 | -0.91379/-0.93334/-0.91379 |
| heur3200_s3502000016_K10 | pre_endgame | 10 | 26 | 0.0177 | completion/score-greed | NET<STATIC,i8miss | 969/1223/969 | 0.23385/0.21505/0.23385 |
| heur3200_s3502000005_K10 | pre_endgame | 10 | 32 | 0.016 | bag/scarcity | NET<STATIC,i8miss | 1649/1361/1649 | 0.92055/0.90451/0.92055 |
| hybrid_8_3200_s3503000029_K16 | late_mid | 16 | 46 | 0.0159 | structural/closure | NET<STATIC,i8miss | 1527/1327/1527 | 0.87222/0.85541/0.87222 |
| heur3200_s3502000040_K10 | pre_endgame | 10 | 19 | 0.0154 | structural/closure | NET<STATIC,i8miss | 1739/954/1739 | 0.7393/0.72393/0.7393 |
| heur3200_s3502000006_K52 | opening | 52 | 17 | 0.0135 | structural/closure | NET<STATIC,i8miss | 1341/1651/1341 | 0.09166/0.04125/0.09166 |
| iter8_s3501000007_K28 | mid | 28 | 43 | 0.0134 | completion/score-greed | NET<STATIC,i8miss | 931/1752/931 | 0.90326/0.87934/0.90326 |
| hybrid_8_3200_s3503000001_K28 | mid | 28 | 28 | 0.0132 | structural/closure | NET<STATIC,i8miss | 848/1060/848 | 0.61087/0.59765/0.61087 |
| hybrid_8_3200_s3503000012_K52 | opening | 52 | 25 | 0.0123 | structural/unclear | NET<STATIC,i8miss | 1551/950/1551 | 0.03813/0.00431/0.03813 |
| greedy_s3500000005_K52 | opening | 52 | 29 | 0.0122 | structural/unclear | NET<STATIC,i8miss | 1536/1546/1536 | 0.40066/0.38846/0.40066 |
| hybrid_8_3200_s3503000037_K40 | early_mid | 40 | 26 | 0.0122 | completion/score-greed | NET<STATIC,i8miss | 1259/1358/1259 | -0.12132/-0.1925/-0.12132 |
| heur3200_s3502000035_K52 | opening | 52 | 34 | 0.0121 | structural/unclear | NET<STATIC,i8miss | 1143/1338/1143 | -0.51078/-0.52288/-0.51078 |
| iter8_s3501000039_K40 | early_mid | 40 | 28 | 0.0107 | immediate-score | NET<STATIC,i8miss | 1158/1343/1158 | 0.97458/0.95834/0.97458 |
| greedy_s3500000048_K10 | pre_endgame | 10 | 32 | 0.0104 | structural/closure | NET<STATIC,i8miss | 745/1227/745 | -0.91134/-0.92219/-0.91134 |
| heur3200_s3502000040_K28 | mid | 28 | 36 | 0.0101 | structural/unclear | NET<STATIC,i8miss | 1645/1756/1645 | 0.51025/0.49035/0.51025 |
| greedy_s3500000032_K40 | early_mid | 40 | 28 | 0.0088 | structural/closure | NET<STATIC,i8miss | 1042/1243/1042 | -0.27759/-0.2864/-0.27759 |
| greedy_s3500000033_K40 | early_mid | 40 | 40 | 0.0088 | structural/closure | NET<STATIC,i8miss | 1465/1461/1465 | 0.75749/0.74868/0.75749 |
| greedy_s3500000036_K40 | early_mid | 40 | 22 | 0.0082 | structural/closure | NET<STATIC,i8miss | 1658/1033/1658 | -0.81823/-0.82645/-0.81823 |
| greedy_s3500000008_K10 | pre_endgame | 10 | 22 | 0.0077 | structural/closure | NET<STATIC,i8miss | 1422/1349/1422 | 0.94832/0.94066/0.94832 |
| greedy_s3500000008_K40 | early_mid | 40 | 22 | 0.0072 | structural/closure | NET<STATIC,i8miss | 1449/1536/1449 | 0.85045/0.84327/0.85045 |
| heur3200_s3502000029_K16 | late_mid | 16 | 43 | 0.0068 | bag/scarcity | NET<STATIC,i8miss | 1545/742/1545 | -0.5229/-0.5297/-0.5229 |
| hybrid_8_3200_s3503000008_K10 | pre_endgame | 10 | 39 | 0.0065 | structural/closure | NET<STATIC,i8miss | 1531/1543/1531 | 0.74683/0.74036/0.74683 |
| iter8_s3501000039_K52 | opening | 52 | 25 | 0.0064 | structural/unclear | NET<STATIC,i8miss | 1262/1367/1262 | 0.94755/0.94118/0.94755 |
| heur3200_s3502000034_K16 | late_mid | 16 | 32 | 0.0064 | structural/unclear | NET<STATIC,i8miss | 1540/1749/1540 | 0.57407/0.56768/0.57407 |
| iter8_s3501000020_K52 | opening | 52 | 13 | 0.0062 | structural/unclear | NET<STATIC,i8miss | 1160/1161/1160 | 0.11211/0.10591/0.11211 |
| heur3200_s3502000035_K28 | mid | 28 | 38 | 0.0062 | structural/closure | NET<STATIC,i8miss | 657/660/657 | -0.34099/-0.46047/-0.34099 |
| iter8_s3501000049_K40 | early_mid | 40 | 19 | 0.0061 | structural/unclear | NET<STATIC,i8miss | 853/956/853 | 0.18503/0.17174/0.18503 |
| iter8_s3501000004_K16 | late_mid | 16 | 48 | 0.0059 | structural/unclear | NET<STATIC,i8miss | 1665/1666/1665 | -0.6728/-0.67866/-0.6728 |
| iter8_s3501000043_K28 | mid | 28 | 40 | 0.0058 | structural/closure | NET<STATIC,i8miss | 745/832/745 | 0.89465/0.88327/0.89465 |

