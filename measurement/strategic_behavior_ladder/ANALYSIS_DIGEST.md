# Strategic-behavior ladder — analysis digest

Positions: 1918  |  panel: ['random', 'greedy', 'h200_v27', 'h200', 'h800', 'h3200', 'h6400', 'rod1', 'iter08']


## Opportunity inventory (positions where each motif fires)

| motif | n_opp | by opp-class (weak/mid/strong) | by phase |
|---|---|---|---|
| block | 203 | 4/67/132 | endgame:32 late_mid:55 midgame:64 opening:11 pre_endgame:41 |
| avoid_feeding | 780 | 129/290/361 | endgame:77 late_mid:196 midgame:258 opening:139 pre_endgame:110 |
| contest_merge | 391 | 161/61/169 | endgame:31 late_mid:62 midgame:122 opening:133 pre_endgame:43 |
| farm_claim | 777 | 235/332/210 | endgame:23 late_mid:57 midgame:142 opening:517 pre_endgame:38 |

## Table 1 — motif take rate by agent (opportunity-normalized)

| agent | block | avoid_feeding | contest_merge | farm_claim |
|---|---|---|---|---|
| random |   29% (58/203) |   49% (383/780) |   18% (72/391) |   24% (188/777) |
| greedy |   28% (56/203) |   50% (390/780) |   47% (185/391) |   12% (96/777) |
| h200_v27 |   25% (51/203) |   50% (390/780) |   48% (188/391) |   72% (560/777) |
| h200 |   25% (50/203) |   50% (390/780) |   47% (182/391) |   59% (461/777) |
| h800 |   25% (51/203) |   50% (387/780) |   47% (184/391) |   60% (467/777) |
| h3200 |   25% (50/203) |   49% (385/780) |   48% (187/391) |   60% (469/777) |
| h6400 |   26% (52/203) |   49% (385/780) |   49% (190/391) |   60% (466/777) |
| rod1 |   29% (59/203) |   51% (396/780) |   45% (177/391) |   54% (419/777) |
| iter08 |   31% (63/203) |   51% (400/780) |   43% (167/391) |   54% (420/777) |
| _ACTUAL(mover)_ |   26% (53/203) |   49% (381/780) |   29% (113/391) |   32% (251/777) |

## Table 2 — take rate by opponent strength (board context)


**block**

| agent | vs weak | vs mid | vs strong |
|---|---|---|---|
| random |    0% (0/4) |   22% (15/67) |   33% (43/132) |
| greedy |    0% (0/4) |   24% (16/67) |   30% (40/132) |
| h200_v27 |    0% (0/4) |   25% (17/67) |   26% (34/132) |
| h200 |    0% (0/4) |   25% (17/67) |   25% (33/132) |
| h800 |    0% (0/4) |   24% (16/67) |   27% (35/132) |
| h3200 |    0% (0/4) |   24% (16/67) |   26% (34/132) |
| h6400 |    0% (0/4) |   25% (17/67) |   27% (35/132) |
| rod1 |    0% (0/4) |   28% (19/67) |   30% (40/132) |
| iter08 |    0% (0/4) |   30% (20/67) |   33% (43/132) |

**avoid_feeding**

| agent | vs weak | vs mid | vs strong |
|---|---|---|---|
| random |   43% (56/129) |   54% (157/290) |   47% (170/361) |
| greedy |   46% (59/129) |   56% (161/290) |   47% (170/361) |
| h200_v27 |   47% (60/129) |   57% (164/290) |   46% (166/361) |
| h200 |   47% (61/129) |   57% (164/290) |   46% (165/361) |
| h800 |   47% (61/129) |   56% (162/290) |   45% (164/361) |
| h3200 |   47% (61/129) |   55% (160/290) |   45% (164/361) |
| h6400 |   46% (59/129) |   56% (161/290) |   46% (165/361) |
| rod1 |   48% (62/129) |   58% (167/290) |   46% (167/361) |
| iter08 |   47% (60/129) |   58% (168/290) |   48% (172/361) |

**contest_merge**

| agent | vs weak | vs mid | vs strong |
|---|---|---|---|
| random |   13% (21/161) |   20% (12/61) |   23% (39/169) |
| greedy |   26% (42/161) |   59% (36/61) |   63% (107/169) |
| h200_v27 |   30% (49/161) |   39% (24/61) |   68% (115/169) |
| h200 |   30% (48/161) |   43% (26/61) |   64% (108/169) |
| h800 |   32% (51/161) |   38% (23/61) |   65% (110/169) |
| h3200 |   32% (52/161) |   41% (25/61) |   65% (110/169) |
| h6400 |   34% (54/161) |   38% (23/61) |   67% (113/169) |
| rod1 |   31% (50/161) |   39% (24/61) |   61% (103/169) |
| iter08 |   29% (47/161) |   36% (22/61) |   58% (98/169) |

**farm_claim**

| agent | vs weak | vs mid | vs strong |
|---|---|---|---|
| random |   23% (55/235) |   25% (83/332) |   24% (50/210) |
| greedy |   14% (33/235) |   11% (37/332) |   12% (26/210) |
| h200_v27 |   69% (162/235) |   77% (256/332) |   68% (142/210) |
| h200 |   56% (132/235) |   66% (218/332) |   53% (111/210) |
| h800 |   59% (138/235) |   65% (217/332) |   53% (112/210) |
| h3200 |   58% (137/235) |   67% (221/332) |   53% (111/210) |
| h6400 |   57% (135/235) |   66% (220/332) |   53% (111/210) |
| rod1 |   41% (97/235) |   64% (211/332) |   53% (111/210) |
| iter08 |   44% (104/235) |   61% (203/332) |   54% (113/210) |

## Table 3 — missed-opportunity rate on HIGH-magnitude chances

(opportunities with magnitude >= median for that motif; lower = better)
| agent | block | avoid_feeding | contest_merge | farm_claim |
|---|---|---|---|---|
| random |   75% miss (102) |   61% miss (395) |   81% miss (199) |   76% miss (777) |
| greedy |   77% miss (102) |   60% miss (395) |   39% miss (199) |   88% miss (777) |
| h200_v27 |   81% miss (102) |   60% miss (395) |   44% miss (199) |   28% miss (777) |
| h200 |   84% miss (102) |   60% miss (395) |   45% miss (199) |   41% miss (777) |
| h800 |   83% miss (102) |   61% miss (395) |   45% miss (199) |   40% miss (777) |
| h3200 |   84% miss (102) |   61% miss (395) |   45% miss (199) |   40% miss (777) |
| h6400 |   83% miss (102) |   61% miss (395) |   43% miss (199) |   40% miss (777) |
| rod1 |   75% miss (102) |   58% miss (395) |   50% miss (199) |   46% miss (777) |
| iter08 |   72% miss (102) |   56% miss (395) |   53% miss (199) |   46% miss (777) |

## Table 4 — take rate by game phase


**block**

| agent | opening | midgame | late_mid | pre_endgame | endgame |
|---|---|---|---|---|---|
| h6400 |   18% (2/11) |   14% (9/64) |   31% (17/55) |   24% (10/41) |   44% (14/32) |
| rod1 |   18% (2/11) |   12% (8/64) |   35% (19/55) |   39% (16/41) |   44% (14/32) |
| greedy |   18% (2/11) |   14% (9/64) |   31% (17/55) |   37% (15/41) |   41% (13/32) |
| ACTUAL |    9% (1/11) |   14% (9/64) |   31% (17/55) |   32% (13/41) |   41% (13/32) |

**avoid_feeding**

| agent | opening | midgame | late_mid | pre_endgame | endgame |
|---|---|---|---|---|---|
| h6400 |   40% (55/139) |   49% (127/258) |   51% (100/196) |   52% (57/110) |   60% (46/77) |
| rod1 |   39% (54/139) |   50% (129/258) |   53% (103/196) |   59% (65/110) |   58% (45/77) |
| greedy |   41% (57/139) |   48% (123/258) |   52% (101/196) |   57% (63/110) |   60% (46/77) |
| ACTUAL |   42% (58/139) |   47% (122/258) |   50% (98/196) |   53% (58/110) |   58% (45/77) |

**contest_merge**

| agent | opening | midgame | late_mid | pre_endgame | endgame |
|---|---|---|---|---|---|
| h6400 |   43% (57/133) |   56% (68/122) |   45% (28/62) |   47% (20/43) |   55% (17/31) |
| rod1 |   41% (54/133) |   52% (63/122) |   44% (27/62) |   49% (21/43) |   39% (12/31) |
| greedy |   37% (49/133) |   54% (66/122) |   47% (29/62) |   56% (24/43) |   55% (17/31) |
| ACTUAL |   26% (34/133) |   36% (44/122) |   23% (14/62) |   30% (13/43) |   26% (8/31) |

**farm_claim**

| agent | opening | midgame | late_mid | pre_endgame | endgame |
|---|---|---|---|---|---|
| h6400 |   63% (328/517) |   55% (78/142) |   54% (31/57) |   53% (20/38) |   39% (9/23) |
| rod1 |   61% (314/517) |   50% (71/142) |   33% (19/57) |   24% (9/38) |   26% (6/23) |
| greedy |    0% (0/517) |   30% (43/142) |   46% (26/57) |   42% (16/38) |   48% (11/23) |
| ACTUAL |   28% (147/517) |   39% (56/142) |   46% (26/57) |   37% (14/38) |   35% (8/23) |

## Table 5 — outcome-sanity: does taking the motif predict winning? (close games)

(positions in games with |final margin| <= 5; mover's ACTUAL choice; win = mover result W. If take<=miss winrate, motif is DESCRIPTIVE not target-worthy.)
| motif | n_take | win%|take | n_miss | win%|miss | delta | verdict |
|---|---|---|---|---|---|---|
| block | 8 | 25% | 34 | 35% | -10pp | low-n |
| avoid_feeding | 54 | 39% | 67 | 37% | +2pp | counter/flat |
| contest_merge | 18 | 33% | 63 | 44% | -11pp | low-n |
| farm_claim | 32 | 50% | 85 | 33% | +17pp | predictive |

## Table 6 — h6400 vs RoD1 take-rate deltas (same positions)

| motif | h6400 | rod1 | delta (h6400-rod1) | n |
|---|---|---|---|---|
| block |   26% (52/203) |   29% (59/203) | -3pp | 203 |
| avoid_feeding |   49% (385/780) |   51% (396/780) | -1pp | 780 |
| contest_merge |   49% (190/391) |   45% (177/391) | +3pp | 391 |
| farm_claim |   60% (466/777) |   54% (419/777) | +6pp | 777 |

## Pseudo-human ladder — does behavior track strength?

`corr` = Pearson(ladder position, take rate) over agents with n>=10. Positive+large => behavior rises with strength (credible diagnostic); ~0 => motif doesn't separate these agents.
| motif | take rate along ladder (weak->strong %) | corr | monotone? |
|---|---|---|---|
| block | 29 28 25 25 25 25 26 29 31 | +0.30 | no |
| avoid_feeding | 49 50 50 50 50 49 49 51 51 | +0.59 | no |
| contest_merge | 18 47 48 47 47 48 49 45 43 | +0.44 | no |
| farm_claim | 24 12 72 59 60 60 60 54 54 | +0.52 | no |
