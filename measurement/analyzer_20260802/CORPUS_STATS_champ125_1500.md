# Corpus stats — `champ125_1500`

**Corpus:** `measurement/utility_calibration_20260721/gen_games_champ125.jsonl` — distill-flywheel generation corpus (champ125), 1500 games. NOTE: the path named in the task (measurement/distill_flywheel_20260715/gen_games_champ125.jsonl) does not exist; this is the same-named corpus that does exist, under measurement/utility_calibration_20260721/. No recorded scores in this file, so replay-score verification is unchecked (splits still reconcile).  
**Games:** 1500 (3000 seats) · generated 2026-08-02T00:10:10 · schema `carcassonne-analyzer-corpus-stats/v1`  
**Integrity:** replay scores match 0/1500 (mismatch 0, unchecked 1500) · score split reconciles 1500/1500

Every number below is a field of the companion JSON. Definitions: see its `definitions` block (stranding is **non-farmer** unless it says otherwise — farmers are unrecoverable by design).

## Seat-level distributions (both seats pooled)

| stat | mean | sd | p5 | p50 | p95 |
|---|---:|---:|---:|---:|---:|
| final_score | 98.5 | 16.1 | 72 | 98 | 125 |
| during_play | 55.7 | 16.8 | 28 | 56 | 83 |
| incomplete_pts | 24 | 9.36 | 9 | 24 | 40 |
| farm_pts | 18.8 | 10.3 | 0 | 21 | 33 |
| during_play_frac | 0.559 | 0.12 | 0.356 | 0.563 | 0.748 |
| farm_pts_frac | 0.186 | 0.0963 | 0 | 0.2 | 0.327 |
| n_meeples_placed | 11 | 1.73 | 8 | 11 | 14 |
| n_farmers_placed | 2.9 | 1.05 | 1 | 3 | 5 |
| deploy_rate | 0.306 | 0.0482 | 0.222 | 0.306 | 0.389 |
| stranded_nonfarmer | 3.46 | 1.12 | 2 | 3 | 5 |
| stranding_rate_nonfarmer | 0.44 | 0.153 | 0.2 | 0.429 | 0.714 |
| meeple_turns_locked | 123 | 60.8 | 30 | 120 | 230 |
| first_farm_turn | 7.02 | 8.38 | 0 | 4 | 23 |
| first_farm_k_remaining | 64 | 8.38 | 48 | 67 | 71 |
| mean_farm_turn | 22.5 | 11.4 | 5.33 | 22 | 41.7 |
| farm_pts_per_farmer | 6.63 | 3.85 | 0 | 6.75 | 13.5 |
| n_farmers_early | 1.73 | 0.885 | 1 | 2 | 3 |
| n_farmers_mid | 0.7 | 0.758 | 0 | 1 | 2 |
| n_farmers_late | 0.471 | 0.642 | 0 | 0 | 2 |
| mean_meeples_in_hand | 2.27 | 0.402 | 1.62 | 2.26 | 2.93 |
| min_meeples_in_hand | 0.377 | 0.509 | 0 | 0 | 1 |
| n_features_won | 4.58 | 1.84 | 2 | 4 | 8 |
| mean_city_size_won | 4.58 | 1.86 | 2 | 4 | 8 |
| mean_road_size_won | 5.59 | 2.09 | 3 | 5 | 9.5 |
| pts_per_meeple_placed | 9.07 | 1.55 | 6.73 | 8.92 | 11.8 |

## Move-type mix by phase

The two segmentations label the same turn identically **1.0000** of the time. They coincide exactly whenever every game runs the full 72 tiles (turns 0–23 ↔ k 71–48, 24–47 ↔ k 47–24, 48–71 ↔ k 23–0); they only diverge for short games. Both are printed anyway so the reader can see that, and so the tables stay comparable against a corpus where games DO end early.

**k_remaining bands (absolute: early ≥48, mid 24–47, late <24)**

| phase | turns | city | road | farm | cloister | pass | deploy rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| early | 36000 | 0.155 | 0.137 | 0.144 | 0.073 | 0.491 | 0.509 |
| mid | 36000 | 0.063 | 0.054 | 0.058 | 0.059 | 0.766 | 0.234 |
| late | 36000 | 0.049 | 0.043 | 0.039 | 0.043 | 0.826 | 0.174 |

**turn terciles (relative to each game's length)**

| phase | turns | city | road | farm | cloister | pass | deploy rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| early | 36000 | 0.155 | 0.137 | 0.144 | 0.073 | 0.491 | 0.509 |
| mid | 36000 | 0.063 | 0.054 | 0.058 | 0.059 | 0.766 | 0.234 |
| late | 36000 | 0.049 | 0.043 | 0.039 | 0.043 | 0.826 | 0.174 |

## Completed-feature sizes (closed during play)

| feature | closed/game | mean size | p50 | p95 | max | mean pts | closed w/ nobody on it |
|---|---:|---:|---:|---:|---:|---:|---:|
| city | 9.32 | 2.96 | 2 | 7 | 19 | 6.71 | 0.626 |
| road | 9.05 | 3.62 | 3 | 8 | 20 | 3.62 | 0.602 |
| cloister | 3.95 | 9.00 | 9 | 9 | 9 | 9.00 | 0.521 |

Completed-size histograms (tiles → count):

- **city**: 2:9022, 3:1938, 4:958, 5:734, 6:497, 7:319, 8:223, 9:122, 10:72, 11:39, 12:29, 13:14, 14:8, 15:3, 17:1, 19:1
- **road**: 2:5542, 3:2697, 4:2281, 5:924, 6:848, 7:429, 8:339, 9:187, 10:137, 11:80, 12:45, 13:30, 14:11, 15:8, 16:11, 17:3, 18:1, 20:1

## Stranding (non-farmer meeples never returned)

- overall rate **0.427** (10387/24316 non-farmer deployments)
- including farmers (occupancy, NOT an error rate): 0.578
- points per meeple-turn earned by returned meeples: **0.4663** (116494 pts / 249833 meeple-turns)
- stranded meeple-turns: 369472 → gross opportunity 57.4 pts/seat/game at that rate, minus the 24.0 pts/seat those stranded meeples DO collect at game end = **net 33.4 pts/seat/game**. Upper read: it assumes a productive alternative placement always existed.

| placement band | non-farmer placed | stranded | rate |
|---|---:|---:|---:|
| early | 13125 | 3574 | 0.272 |
| mid | 6325 | 2907 | 0.460 |
| late | 4866 | 3906 | 0.803 |

| terrain | placed | stranded | rate |
|---|---:|---:|---:|
| city | 9602 | 4155 | 0.433 |
| road | 8394 | 2811 | 0.335 |
| cloister | 6320 | 3421 | 0.541 |

## Farm timing

- farmers per seat: **2.90** (8697 total; 6 seats played none)
- **first** farmer turn: mean 7.0, p5 0, p50 4, p95 23
- ALL farmer placements, turn: mean 23.6, p5 1, p50 17, p95 66
- by band: early 0.596 · mid 0.242 · late 0.163
- farm points per farmer: mean 6.63, p50 6.75

## Score flow (per seat)

| bucket | mean | sd | p5 | p50 | p95 |
|---|---:|---:|---:|---:|---:|
| during_play | 55.73 | 16.79 | 28 | 56 | 83 |
| incomplete_pts | 24.00 | 9.36 | 9 | 24 | 40 |
| farm_pts | 18.75 | 10.29 | 0 | 21 | 33 |
| final_score | 98.49 | 16.05 | 72 | 98 | 125 |

## Meeple economy + openness (mean over corpus, by turn)

| turn | meeples in hand | meeples on board | open cities | open roads | open cloisters |
|---:|---:|---:|---:|---:|---:|
| 0 | 7.00 | 0.96 | 0.66 | 0.85 | 0.20 |
| 6 | 4.79 | 4.90 | 2.34 | 3.34 | 1.35 |
| 12 | 3.68 | 6.93 | 3.32 | 5.00 | 2.49 |
| 18 | 2.83 | 8.55 | 4.13 | 6.41 | 3.56 |
| 24 | 2.26 | 9.62 | 4.79 | 7.66 | 4.51 |
| 30 | 1.91 | 10.27 | 5.31 | 8.86 | 5.37 |
| 36 | 1.65 | 10.76 | 5.85 | 9.92 | 6.22 |
| 42 | 1.47 | 11.12 | 6.32 | 11.00 | 6.92 |
| 48 | 1.29 | 11.46 | 6.82 | 12.12 | 7.57 |
| 54 | 1.16 | 11.72 | 7.29 | 13.25 | 8.26 |
| 60 | 1.04 | 11.93 | 7.78 | 14.44 | 8.90 |
| 66 | 0.95 | 12.15 | 8.33 | 15.67 | 9.55 |
