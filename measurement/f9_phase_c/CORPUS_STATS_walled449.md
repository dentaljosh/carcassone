# Corpus stats — `walled449`

**Corpus:** `measurement/champ_action_logs/champ_games.jsonl` — F9 Phase C · rules_profile=walled · R9=off · measurement/champ_action_logs/champ_games.jsonl  
**Games:** 449 (898 seats) · generated 2026-08-03T13:57:30 · schema `carcassonne-analyzer-corpus-stats/v1`  
**Integrity:** replay scores match 449/449 (mismatch 0, unchecked 0) · score split reconciles 449/449

Every number below is a field of the companion JSON. Definitions: see its `definitions` block (stranding is **non-farmer** unless it says otherwise — farmers are unrecoverable by design).

## Seat-level distributions (both seats pooled)

| stat | mean | sd | p5 | p50 | p95 |
|---|---:|---:|---:|---:|---:|
| final_score | 98.3 | 15.6 | 71 | 99 | 122 |
| during_play | 54.8 | 16.5 | 26.9 | 55 | 81 |
| incomplete_pts | 23 | 9.39 | 8 | 23 | 39 |
| farm_pts | 20.5 | 10.7 | 0 | 21 | 36 |
| during_play_frac | 0.549 | 0.118 | 0.349 | 0.556 | 0.738 |
| farm_pts_frac | 0.207 | 0.105 | 0 | 0.225 | 0.353 |
| n_meeples_placed | 11.1 | 1.72 | 8 | 11 | 14 |
| n_farmers_placed | 3.43 | 1.11 | 2 | 3 | 5 |
| deploy_rate | 0.308 | 0.0479 | 0.222 | 0.306 | 0.389 |
| stranded_nonfarmer | 3.3 | 1.15 | 1 | 3 | 5 |
| stranding_rate_nonfarmer | 0.443 | 0.16 | 0.2 | 0.429 | 0.714 |
| meeple_turns_locked | 121 | 61.2 | 28.9 | 116 | 228 |
| first_farm_turn | 6.76 | 7.76 | 0 | 4 | 21 |
| first_farm_k_remaining | 64.2 | 7.76 | 50 | 67 | 71 |
| mean_farm_turn | 25.2 | 10.6 | 7.64 | 25.6 | 42.1 |
| farm_pts_per_farmer | 6.02 | 3.16 | 0 | 6 | 11 |
| n_farmers_early | 1.89 | 0.916 | 1 | 2 | 4 |
| n_farmers_mid | 0.844 | 0.817 | 0 | 1 | 2 |
| n_farmers_late | 0.694 | 0.743 | 0 | 1 | 2 |
| mean_meeples_in_hand | 2.1 | 0.41 | 1.46 | 2.1 | 2.81 |
| min_meeples_in_hand | 0.175 | 0.389 | 0 | 0 | 1 |
| n_features_won | 4.3 | 1.78 | 2 | 4 | 7 |
| mean_city_size_won | 4.52 | 1.92 | 2 | 4 | 8 |
| mean_road_size_won | 5.78 | 2.31 | 3 | 5.25 | 10 |
| pts_per_meeple_placed | 8.97 | 1.55 | 6.7 | 8.82 | 11.7 |

## Move-type mix by phase

The two segmentations label the same turn identically **1.0000** of the time. They coincide exactly whenever every game runs the full 72 tiles (turns 0–23 ↔ k 71–48, 24–47 ↔ k 47–24, 48–71 ↔ k 23–0); they only diverge for short games. Both are printed anyway so the reader can see that, and so the tables stay comparable against a corpus where games DO end early.

**k_remaining bands (absolute: early ≥48, mid 24–47, late <24)**

| phase | turns | city | road | farm | cloister | pass | deploy rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| early | 10776 | 0.164 | 0.125 | 0.158 | 0.078 | 0.476 | 0.524 |
| mid | 10776 | 0.058 | 0.040 | 0.070 | 0.055 | 0.777 | 0.223 |
| late | 10776 | 0.048 | 0.039 | 0.058 | 0.033 | 0.822 | 0.178 |

**turn terciles (relative to each game's length)**

| phase | turns | city | road | farm | cloister | pass | deploy rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| early | 10776 | 0.164 | 0.125 | 0.158 | 0.078 | 0.476 | 0.524 |
| mid | 10776 | 0.058 | 0.040 | 0.070 | 0.055 | 0.777 | 0.223 |
| late | 10776 | 0.048 | 0.039 | 0.058 | 0.033 | 0.822 | 0.178 |

## Completed-feature sizes (closed during play)

| feature | closed/game | mean size | p50 | p95 | max | mean pts | closed w/ nobody on it |
|---|---:|---:|---:|---:|---:|---:|---:|
| city | 9.80 | 2.90 | 2 | 7 | 19 | 6.56 | 0.628 |
| road | 9.21 | 3.44 | 3 | 8 | 19 | 3.44 | 0.681 |
| cloister | 3.98 | 9.00 | 9 | 9 | 9 | 9.00 | 0.527 |

Completed-size histograms (tiles → count):

- **city**: 2:2958, 3:557, 4:302, 5:189, 6:137, 7:86, 8:72, 9:42, 10:21, 11:14, 12:9, 13:7, 14:3, 16:1, 19:1
- **road**: 2:1821, 3:953, 4:589, 5:226, 6:196, 7:118, 8:89, 9:55, 10:30, 11:21, 12:17, 13:9, 14:4, 15:4, 17:2, 19:1

## Stranding (non-farmer meeples never returned)

- overall rate **0.431** (2966/6889 non-farmer deployments)
- including farmers (occupancy, NOT an error rate): 0.606
- points per meeple-turn earned by returned meeples: **0.4714** (33893 pts / 71898 meeple-turns)
- stranded meeple-turns: 108961 → gross opportunity 57.2 pts/seat/game at that rate, minus the 23.0 pts/seat those stranded meeples DO collect at game end = **net 34.2 pts/seat/game**. Upper read: it assumes a productive alternative placement always existed.

| placement band | non-farmer placed | stranded | rate |
|---|---:|---:|---:|
| early | 3946 | 1136 | 0.288 |
| mid | 1643 | 758 | 0.461 |
| late | 1300 | 1072 | 0.825 |

| terrain | placed | stranded | rate |
|---|---:|---:|---:|
| city | 2901 | 1195 | 0.412 |
| road | 2201 | 836 | 0.380 |
| cloister | 1787 | 935 | 0.523 |

## Farm timing

- farmers per seat: **3.43** (3080 total; 0 seats played none)
- **first** farmer turn: mean 6.8, p5 0, p50 4, p95 21
- ALL farmer placements, turn: mean 26.0, p5 2, p50 20, p95 67
- by band: early 0.552 · mid 0.246 · late 0.202
- farm points per farmer: mean 6.02, p50 6.00

## Score flow (per seat)

| bucket | mean | sd | p5 | p50 | p95 |
|---|---:|---:|---:|---:|---:|
| during_play | 54.76 | 16.47 | 26.9 | 55 | 81 |
| incomplete_pts | 23.01 | 9.39 | 8 | 23 | 39 |
| farm_pts | 20.49 | 10.72 | 0 | 21 | 36 |
| final_score | 98.26 | 15.62 | 71 | 99 | 122 |

## Meeple economy + openness (mean over corpus, by turn)

| turn | meeples in hand | meeples on board | open cities | open roads | open cloisters |
|---:|---:|---:|---:|---:|---:|
| 0 | 7.00 | 0.99 | 0.68 | 0.81 | 0.21 |
| 6 | 4.73 | 4.96 | 2.20 | 3.25 | 1.39 |
| 12 | 3.51 | 7.31 | 3.05 | 4.88 | 2.60 |
| 18 | 2.66 | 8.87 | 3.64 | 6.32 | 3.68 |
| 24 | 2.11 | 9.92 | 4.17 | 7.65 | 4.57 |
| 30 | 1.71 | 10.61 | 4.64 | 8.92 | 5.47 |
| 36 | 1.49 | 11.12 | 5.10 | 10.12 | 6.19 |
| 42 | 1.26 | 11.53 | 5.66 | 11.36 | 6.80 |
| 48 | 1.12 | 11.78 | 6.05 | 12.68 | 7.51 |
| 54 | 0.96 | 12.15 | 6.76 | 13.82 | 8.18 |
| 60 | 0.85 | 12.34 | 7.30 | 15.12 | 8.77 |
| 66 | 0.71 | 12.60 | 7.95 | 16.39 | 9.38 |
