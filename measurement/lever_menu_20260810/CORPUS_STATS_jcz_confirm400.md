# Corpus stats — `jcz_confirm400`

**Corpus:** `measurement/lever_menu_20260810/jcz_confirm_adapted.jsonl` — JCZ external-AI match n=400 confirm (jcz_match_20260809/confirm.jsonl), fixed_v1+R9, champion k8x1376=11008 vs JCloisterZone LegacyAiPlayer, band 1.08e11 (retired) -- item-1 farm-norm replay, no strength claim  
**Games:** 400 (800 seats) · generated 2026-08-10T12:13:06 · schema `carcassonne-analyzer-corpus-stats/v1`  
**Integrity:** replay scores match 400/400 (mismatch 0, unchecked 0) · score split reconciles 400/400

Every number below is a field of the companion JSON. Definitions: see its `definitions` block (stranding is **non-farmer** unless it says otherwise — farmers are unrecoverable by design).

## Seat-level distributions (both seats pooled)

| stat | mean | sd | p5 | p50 | p95 |
|---|---:|---:|---:|---:|---:|
| final_score | 96.3 | 15.8 | 69 | 96 | 123 |
| during_play | 52.7 | 18.1 | 22 | 53 | 83 |
| incomplete_pts | 27.3 | 12.6 | 8 | 27 | 48 |
| farm_pts | 16.2 | 16.7 | 0 | 13.5 | 42 |
| during_play_frac | 0.537 | 0.137 | 0.3 | 0.537 | 0.758 |
| farm_pts_frac | 0.165 | 0.17 | 0 | 0.151 | 0.424 |
| n_meeples_placed | 11.5 | 1.96 | 8 | 12 | 15 |
| n_farmers_placed | 1.91 | 1.98 | 0 | 1 | 5 |
| deploy_rate | 0.324 | 0.0549 | 0.229 | 0.333 | 0.417 |
| stranded_nonfarmer | 4.53 | 1.85 | 2 | 5 | 7 |
| stranding_rate_nonfarmer | 0.48 | 0.155 | 0.222 | 0.5 | 0.75 |
| meeple_turns_locked | 164 | 78.4 | 38 | 164 | 292 |
| first_farm_turn | 7.17 | 15 | 1 | 2 | 50.3 |
| first_farm_k_remaining | 62.8 | 15 | 19.7 | 68 | 69 |
| mean_farm_turn | 23.7 | 14 | 6.5 | 21.6 | 50.3 |
| farm_pts_per_farmer | 8.84 | 2.89 | 5.47 | 8.25 | 13.5 |
| n_farmers_early | 1.17 | 1.33 | 0 | 1 | 4 |
| n_farmers_mid | 0.367 | 0.669 | 0 | 0 | 2 |
| n_farmers_late | 0.369 | 0.658 | 0 | 0 | 2 |
| mean_meeples_in_hand | 2.1 | 0.432 | 1.41 | 2.08 | 2.83 |
| min_meeples_in_hand | 0.164 | 0.377 | 0 | 0 | 1 |
| n_features_won | 4.83 | 2.17 | 1 | 5 | 8 |
| mean_city_size_won | 4.46 | 2.04 | 2 | 4 | 8 |
| mean_road_size_won | 5.45 | 1.93 | 3 | 5 | 9 |
| pts_per_meeple_placed | 8.53 | 1.63 | 6.46 | 8.27 | 11.5 |

## Move-type mix by phase

The two segmentations label the same turn identically **0.9718** of the time. They coincide exactly whenever every game runs the full 72 tiles (turns 0–23 ↔ k 71–48, 24–47 ↔ k 47–24, 48–71 ↔ k 23–0); they only diverge for short games. Both are printed anyway so the reader can see that, and so the tables stay comparable against a corpus where games DO end early.

**k_remaining bands (absolute: early ≥48, mid 24–47, late <24)**

| phase | turns | city | road | farm | cloister | pass | deploy rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| early | 9200 | 0.210 | 0.146 | 0.102 | 0.076 | 0.466 | 0.534 |
| mid | 9600 | 0.088 | 0.060 | 0.031 | 0.062 | 0.759 | 0.241 |
| late | 9600 | 0.069 | 0.059 | 0.031 | 0.046 | 0.795 | 0.205 |

**turn terciles (relative to each game's length)**

| phase | turns | city | road | farm | cloister | pass | deploy rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| early | 9600 | 0.207 | 0.143 | 0.100 | 0.076 | 0.475 | 0.525 |
| mid | 9600 | 0.086 | 0.060 | 0.030 | 0.061 | 0.764 | 0.236 |
| late | 9200 | 0.069 | 0.059 | 0.031 | 0.046 | 0.795 | 0.205 |

## Completed-feature sizes (closed during play)

| feature | closed/game | mean size | p50 | p95 | max | mean pts | closed w/ nobody on it |
|---|---:|---:|---:|---:|---:|---:|---:|
| city | 8.80 | 3.10 | 2 | 7 | 19 | 7.08 | 0.543 |
| road | 8.76 | 3.54 | 3 | 8 | 17 | 3.54 | 0.601 |
| cloister | 3.40 | 9.00 | 9 | 9 | 9 | 9.00 | 0.447 |

Completed-size histograms (tiles → count):

- **city**: 2:2166, 3:531, 4:277, 5:180, 6:129, 7:79, 8:38, 9:39, 10:24, 11:11, 12:15, 13:15, 14:6, 15:7, 17:2, 18:1, 19:2
- **road**: 2:1444, 3:717, 4:617, 5:253, 6:181, 7:95, 8:81, 9:43, 10:28, 11:17, 12:10, 13:14, 14:2, 15:2, 17:1

## Stranding (non-farmer meeples never returned)

- overall rate **0.473** (3625/7666 non-farmer deployments)
- including farmers (occupancy, NOT an error rate): 0.560
- points per meeple-turn earned by returned meeples: **0.4547** (35726 pts / 78569 meeple-turns)
- stranded meeple-turns: 131398 → gross opportunity 74.7 pts/seat/game at that rate, minus the 27.3 pts/seat those stranded meeples DO collect at game end = **net 47.3 pts/seat/game**. Upper read: it assumes a productive alternative placement always existed.

| placement band | non-farmer placed | stranded | rate |
|---|---:|---:|---:|
| early | 3976 | 1338 | 0.337 |
| mid | 2020 | 974 | 0.482 |
| late | 1670 | 1313 | 0.786 |

| terrain | placed | stranded | rate |
|---|---:|---:|---:|
| city | 3446 | 1604 | 0.465 |
| road | 2485 | 1000 | 0.402 |
| cloister | 1735 | 1021 | 0.588 |

## Farm timing

- farmers per seat: **1.91** (1525 total; 366 seats played none)
- **first** farmer turn: mean 7.2, p5 1, p50 2, p95 50
- ALL farmer placements, turn: mean 23.0, p5 1, p50 14, p95 69
- by band: early 0.614 · mid 0.193 · late 0.193
- farm points per farmer: mean 8.84, p50 8.25

## Score flow (per seat)

| bucket | mean | sd | p5 | p50 | p95 |
|---|---:|---:|---:|---:|---:|
| during_play | 52.70 | 18.06 | 22 | 53 | 83 |
| incomplete_pts | 27.34 | 12.59 | 8 | 27 | 48 |
| farm_pts | 16.25 | 16.71 | 0 | 13.5 | 42 |
| final_score | 96.30 | 15.82 | 69 | 96 | 123 |

## Meeple economy + openness (mean over corpus, by turn)

| turn | meeples in hand | meeples on board | open cities | open roads | open cloisters |
|---:|---:|---:|---:|---:|---:|
| 0 | 7.00 | 0.77 | 0.82 | 1.47 | 0.23 |
| 5 | 5.14 | 4.30 | 2.25 | 3.28 | 1.28 |
| 10 | 3.91 | 6.64 | 3.32 | 4.65 | 2.23 |
| 15 | 2.96 | 8.39 | 4.00 | 6.05 | 3.24 |
| 20 | 2.34 | 9.56 | 4.64 | 7.48 | 4.05 |
| 25 | 1.90 | 10.35 | 5.16 | 8.53 | 4.88 |
| 30 | 1.57 | 10.88 | 5.70 | 9.71 | 5.75 |
| 35 | 1.42 | 11.27 | 6.20 | 10.71 | 6.45 |
| 40 | 1.23 | 11.59 | 6.50 | 11.89 | 7.17 |
| 45 | 1.13 | 11.78 | 6.80 | 12.97 | 7.78 |
| 50 | 1.06 | 11.96 | 7.25 | 14.04 | 8.34 |
| 55 | 0.99 | 12.04 | 7.47 | 15.01 | 8.94 |
| 60 | 0.92 | 12.24 | 7.78 | 16.09 | 9.50 |
| 65 | 0.87 | 12.27 | 7.93 | 16.94 | 10.08 |
| 70 | 0.76 | 12.88 | 8.17 | 17.78 | 10.59 |
