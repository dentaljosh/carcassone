# Corpus stats — `fixed_v1`

**Corpus:** `measurement/f9_phase_c/corpus_fixed_v1.jsonl` — F9 Phase C · rules_profile=fixed_v1 · R9=on · /mnt/c/carc-shared/f9_wall_probe_20260802/fixed_v1  
**Games:** 400 (800 seats) · generated 2026-08-03T13:57:47 · schema `carcassonne-analyzer-corpus-stats/v1`  
**Integrity:** replay scores match 400/400 (mismatch 0, unchecked 0) · score split reconciles 400/400

Every number below is a field of the companion JSON. Definitions: see its `definitions` block (stranding is **non-farmer** unless it says otherwise — farmers are unrecoverable by design).

## Seat-level distributions (both seats pooled)

| stat | mean | sd | p5 | p50 | p95 |
|---|---:|---:|---:|---:|---:|
| final_score | 98 | 17.1 | 68 | 98 | 126 |
| during_play | 55.4 | 17.8 | 26 | 56 | 83 |
| incomplete_pts | 21.7 | 9.65 | 7 | 21 | 39 |
| farm_pts | 20.8 | 10.9 | 0 | 21 | 36 |
| during_play_frac | 0.557 | 0.129 | 0.333 | 0.561 | 0.758 |
| farm_pts_frac | 0.212 | 0.109 | 0 | 0.226 | 0.375 |
| n_meeples_placed | 11.2 | 1.71 | 8 | 11 | 14 |
| n_farmers_placed | 3.67 | 1.13 | 2 | 4 | 5 |
| deploy_rate | 0.315 | 0.0482 | 0.229 | 0.314 | 0.4 |
| stranded_nonfarmer | 3.06 | 1.16 | 1 | 3 | 5 |
| stranding_rate_nonfarmer | 0.418 | 0.16 | 0.181 | 0.4 | 0.714 |
| meeple_turns_locked | 112 | 61.1 | 21 | 106 | 226 |
| first_farm_turn | 5.24 | 6.65 | 1 | 3 | 17.1 |
| first_farm_k_remaining | 64.8 | 6.65 | 52.9 | 67 | 69 |
| mean_farm_turn | 24.5 | 9.95 | 8.45 | 24 | 40.6 |
| farm_pts_per_farmer | 5.74 | 2.93 | 0 | 6 | 10.5 |
| n_farmers_early | 2.02 | 0.956 | 1 | 2 | 4 |
| n_farmers_mid | 0.885 | 0.832 | 0 | 1 | 2 |
| n_farmers_late | 0.762 | 0.796 | 0 | 1 | 2 |
| mean_meeples_in_hand | 2 | 0.38 | 1.39 | 2 | 2.65 |
| min_meeples_in_hand | 0.104 | 0.309 | 0 | 0 | 1 |
| n_features_won | 4.42 | 1.76 | 2 | 4 | 7 |
| mean_city_size_won | 4.55 | 1.92 | 2 | 4 | 8 |
| mean_road_size_won | 5.79 | 2.36 | 3 | 5 | 10.5 |
| pts_per_meeple_placed | 8.85 | 1.47 | 6.64 | 8.8 | 11.4 |

## Move-type mix by phase

The two segmentations label the same turn identically **0.9718** of the time. They coincide exactly whenever every game runs the full 72 tiles (turns 0–23 ↔ k 71–48, 24–47 ↔ k 47–24, 48–71 ↔ k 23–0); they only diverge for short games. Both are printed anyway so the reader can see that, and so the tables stay comparable against a corpus where games DO end early.

**k_remaining bands (absolute: early ≥48, mid 24–47, late <24)**

| phase | turns | city | road | farm | cloister | pass | deploy rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| early | 9200 | 0.165 | 0.128 | 0.176 | 0.081 | 0.450 | 0.550 |
| mid | 9600 | 0.061 | 0.037 | 0.074 | 0.053 | 0.775 | 0.225 |
| late | 9600 | 0.043 | 0.040 | 0.064 | 0.033 | 0.821 | 0.179 |

**turn terciles (relative to each game's length)**

| phase | turns | city | road | farm | cloister | pass | deploy rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| early | 9600 | 0.161 | 0.126 | 0.172 | 0.080 | 0.461 | 0.539 |
| mid | 9600 | 0.060 | 0.036 | 0.074 | 0.052 | 0.779 | 0.221 |
| late | 9200 | 0.043 | 0.040 | 0.063 | 0.033 | 0.822 | 0.178 |

## Completed-feature sizes (closed during play)

| feature | closed/game | mean size | p50 | p95 | max | mean pts | closed w/ nobody on it |
|---|---:|---:|---:|---:|---:|---:|---:|
| city | 9.86 | 2.92 | 2 | 7 | 16 | 6.61 | 0.628 |
| road | 9.06 | 3.47 | 3 | 8 | 20 | 3.47 | 0.680 |
| cloister | 3.96 | 9.00 | 9 | 9 | 9 | 9.00 | 0.463 |

Completed-size histograms (tiles → count):

- **city**: 2:2614, 3:540, 4:270, 5:169, 6:120, 7:71, 8:55, 9:48, 10:25, 11:15, 12:12, 13:3, 14:1, 15:1, 16:1
- **road**: 2:1573, 3:796, 4:570, 5:202, 6:190, 7:91, 8:76, 9:40, 10:33, 11:18, 12:17, 13:2, 14:9, 15:2, 16:4, 19:1, 20:1

## Stranding (non-farmer meeples never returned)

- overall rate **0.407** (2445/6005 non-farmer deployments)
- including farmers (occupancy, NOT an error rate): 0.602
- points per meeple-turn earned by returned meeples: **0.4839** (31332 pts / 64743 meeple-turns)
- stranded meeple-turns: 89839 → gross opportunity 54.3 pts/seat/game at that rate, minus the 21.7 pts/seat those stranded meeples DO collect at game end = **net 32.6 pts/seat/game**. Upper read: it assumes a productive alternative placement always existed.

| placement band | non-farmer placed | stranded | rate |
|---|---:|---:|---:|
| early | 3440 | 944 | 0.274 |
| mid | 1452 | 621 | 0.428 |
| late | 1113 | 880 | 0.791 |

| terrain | placed | stranded | rate |
|---|---:|---:|---:|
| city | 2515 | 980 | 0.390 |
| road | 1919 | 724 | 0.377 |
| cloister | 1571 | 741 | 0.472 |

## Farm timing

- farmers per seat: **3.67** (2935 total; 1 seats played none)
- **first** farmer turn: mean 5.2, p5 1, p50 3, p95 17
- ALL farmer placements, turn: mean 25.1, p5 1, p50 19, p95 66
- by band: early 0.551 · mid 0.241 · late 0.208
- farm points per farmer: mean 5.74, p50 6.00

## Score flow (per seat)

| bucket | mean | sd | p5 | p50 | p95 |
|---|---:|---:|---:|---:|---:|
| during_play | 55.42 | 17.82 | 26 | 56 | 83 |
| incomplete_pts | 21.73 | 9.65 | 7 | 21 | 39 |
| farm_pts | 20.81 | 10.92 | 0 | 21 | 36 |
| final_score | 97.96 | 17.05 | 68 | 98 | 126 |

## Meeple economy + openness (mean over corpus, by turn)

| turn | meeples in hand | meeples on board | open cities | open roads | open cloisters |
|---:|---:|---:|---:|---:|---:|
| 0 | 7.00 | 0.79 | 0.81 | 1.53 | 0.21 |
| 5 | 5.01 | 4.62 | 2.04 | 3.22 | 1.25 |
| 10 | 3.74 | 6.91 | 2.86 | 4.61 | 2.28 |
| 15 | 2.87 | 8.57 | 3.48 | 5.87 | 3.19 |
| 20 | 2.25 | 9.68 | 3.98 | 6.95 | 4.07 |
| 25 | 1.85 | 10.42 | 4.43 | 8.02 | 4.83 |
| 30 | 1.57 | 10.91 | 4.90 | 8.88 | 5.47 |
| 35 | 1.40 | 11.29 | 5.32 | 9.83 | 6.03 |
| 40 | 1.24 | 11.60 | 5.64 | 10.75 | 6.70 |
| 45 | 1.07 | 11.89 | 6.11 | 11.88 | 7.35 |
| 50 | 0.96 | 12.11 | 6.47 | 12.90 | 7.85 |
| 55 | 0.82 | 12.41 | 6.93 | 14.02 | 8.43 |
| 60 | 0.70 | 12.66 | 7.47 | 15.05 | 8.97 |
| 65 | 0.61 | 12.79 | 7.92 | 16.20 | 9.50 |
| 70 | 0.39 | 13.45 | 8.44 | 17.66 | 10.04 |
