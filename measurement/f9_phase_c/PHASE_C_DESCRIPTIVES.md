# F9 Phase C — fixed-rules descriptives (walled vs fixed)

*Generated 2026-08-03 17:57:47 UTC by `scripts/rules_fixed/run_phase_c.py`.*

> **Gate C (anti-cherry-pick).** The descriptive set below is PRE-REGISTERED by
> [docs/F9_BUILD_SPEC_20260802.md](../../docs/F9_BUILD_SPEC_20260802.md) §3 —
> luck floor, decision density, farm-economy norms — and was fixed before either
> corpus was looked at. **Every metric is reported for both profiles regardless
> of direction.** Descriptives carry no claim id, retire no band, write no
> `experiments/results.csv` row, and touch no `governance/PRODUCTION.yaml`.
> A descriptive selected *after* seeing it would be a finding laundered as a
> fact; that is what this gate exists to prevent.


> ⚠️ **These two corpora are on DIFFERENT deck bands** (different seed ranges), so
> every Δ column below is a CROSS-BAND contrast. CLAUDE.md's standing rule applies:
> cross-band dispersion is 1.8–2.2× the within-band figure, so a Δ here is a
> descriptive difference, not a measured effect. Phase B's transfer-bound cell —
> deck-paired, one fresh band — is the instrument that prices a contrast; this
> document is not.


## 0. Corpora

| | reference | new |
|---|---|---|
| label | `walled449` | `fixed_v1` |
| path | measurement/champ_action_logs/champ_games.jsonl | /mnt/c/carc-shared/f9_wall_probe_20260802/fixed_v1 |
| format | games_jsonl | gen_fair_distill_dir |
| games | 449 | 400 |
| rules_profile | **walled** | **fixed_v1** |
| profile source | --rules-profile (corpus manifest predates F9 A0 stamping) | corpus manifest (rules_profile.name) |
| R9 farm fix | off | ON |
| generator | champion_fair_selfplay · budget 2752 · code_rev 1029d5db1-dirty | champion_fair_selfplay · budget 11008 · code_rev 8dfd96e6ea |

⚠️ **Assumption stated:** the reference corpus predates F9 A0 profile stamping, so its manifest carries no `rules_profile`. It is replayed as `walled` — the engine of record, and the only rules the pre-F9 generator could have played (every elo of record is a walled number). The assumption is checked, not just asserted: all games replay to the generator's own recorded terminal scores under `walled`, which a wrong profile would break.

## 1. Luck floor (σ_game slice)

The spec calls this *the highest-stakes descriptive in F9* — it sizes the whole E4/human program. What a champion self-play corpus can price is σ_game (the per-game score-margin SD) and the seat-0 advantage; the ICC / σ_pair half needs a seat-swap paired archive per profile and is reported as NOT DERIVABLE rather than approximated.

| metric | walled449 | fixed_v1 | Δ |
|---|---:|---:|---:|
| games with scores | 449 | 400 | -49 |
| σ_game (margin SD, pts) | 17.75 | 19.56 | +1.81 |
| σ_game SEM | 0.59 | 0.69 | +0.10 |
| mean seat-0 margin (pts) | -0.54 | 1.41 | +1.95 |
|   ± SEM | 0.84 | 0.98 | +0.14 |
| seat-0 win rate | 0.483 | 0.489 | +0.005 |
| mean abs margin (pts) | 14.28 | 15.44 | +1.16 |
| mean total points/game | 196.52 | 195.91 | -0.61 |

**Implied sizing** (`luck_floor.required_n`, unpaired win-rate test):

| target win-rate vs an equal | edge needed, walled449 (pts) | edge needed, fixed_v1 (pts) | n games (unpaired, either) |
|---|---:|---:|---:|
| 55% | 2.23 | 2.46 | 381 |
| 60% | 4.50 | 4.96 | 93 |
| 65% | 6.84 | 7.54 | 39 |

NOT DERIVABLE from these corpora (both profiles alike): **luck_share_icc** — needs a SEAT-SWAP PAIRED archive (same deck, both seatings, two agents) — a self-play champion corpus has one seating per deck.; **sigma_pair** — same reason; the paired-margin statistic does not exist without the second seating.; **n_games_paired_test** — follows from sigma_pair.

To complete the descriptive: generate a seat-swap paired eval archive under this rules profile (the `seedNNN_a0.json` / `_a1.json` shape luck_floor.load_pairs reads) and add its directory to luck_floor.NEAR_EQUAL, then re-run scripts/human_anchor/luck_floor.py.

> **✅ ADDENDUM 2026-08-03 (same day, later) — the paired half is now MEASURED.** The seat-swap
> archive was generated (`/mnt/c/carc-shared/f9_luck_pairs_fixed_v1`: champion-vs-champion, 200
> decks × 2 seatings, fixed_v1+R9 manifest-gated, k8×1376 both sides; h2h sanity 0.487 wr /
> −8.7 ± 17.4 elo = identity-consistent) and analyzed with `luck_floor.py --only-extra` →
> **[LUCK_FLOOR_fixed_v1.md](LUCK_FLOOR_fixed_v1.md)**. Numbers under the adopted rules:
> **deck-luck ICC ~0.19 · σ_game 20.4 · σ_pair 12.8 · seat_adv +3.1 · pairing factor ~0.79**
> (June walled pool for scale, NOT a controlled contrast — different pairings/budgets/era:
> ICC ~0.14, σ_game 22.2, σ_pair 14.5, factor 0.86). E4 sizing under fixed_v1: true-wr 0.55 →
> **193 seat-swap paired games** (vs 381 naive; 0.60 → 48 paired). This section's Δs remain
> cross-band/cross-instrument DESCRIPTIVE.

## 2. Decision density

Instrument: `scripts/rules_fixed/descriptives.py` (built for this gate — the spec's *no instrument exists* row). Pure replay under each corpus's own rules profile. `searched` = the ply had ≥2 legal actions; `forced` = exactly one legal action existed.

| per game | walled449 | fixed_v1 | Δ |
|---|---:|---:|---:|
| n_plies | 143.90 | 141.95 | -1.95 |
| n_tile_plies | 72.00 | 71.00 | -1.00 |
| n_meeple_plies | 71.90 | 70.95 | -0.95 |
| n_tiles_placed | 71.90 | 70.95 | -0.95 |
| tile_pass_plies | 0.10 | 0.05 | -0.05 |
| decisions | 143.90 | 141.95 | -1.95 |
| searched | 128.45 | 125.94 | -2.51 |
| forced_total | 15.45 | 16.01 | +0.56 |
| tile_decisions | 72.00 | 71.00 | -1.00 |
| tile_searched | 70.88 | 70.94 | +0.06 |
| tile_forced | 1.12 | 0.06 | -1.06 |
| meeple_decisions | 71.90 | 70.95 | -0.95 |
| meeple_searched | 57.57 | 55.00 | -2.57 |
| meeple_forced | 14.33 | 15.95 | +1.62 |
| tile_branching_mean | 27.81 | 28.35 | +0.54 |
| tile_branching_mean_searched | 28.23 | 28.37 | +0.14 |
| meeple_branching_mean | 3.47 | 3.38 | -0.09 |
| meeple_branching_mean_searched | 4.09 | 4.08 | -0.01 |
| meeples_committed | 32.64 | 32.33 | -0.31 |
| farmers_committed | 6.86 | 7.34 | +0.48 |
| meeples_free_end | 0.89 | 0.78 | -0.11 |
| margin | -0.54 | 1.41 | +1.95 |

**Branching (legal actions) by ply kind and phase tercile**

| ply kind | phase | mean walled449 | mean fixed_v1 | Δ mean | median walled449 | median fixed_v1 | p90 walled449 | p90 fixed_v1 | forced% walled449 | forced% fixed_v1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| tile | all | 27.81 | 28.35 | +0.54 | 27.0 | 27.0 | 45.0 | 47.0 | 1.5% | 0.1% |
| tile | early | 15.69 | 16.65 | +0.96 | 15.0 | 16.0 | 26.0 | 27.0 | 4.6% | 0.2% |
| tile | mid | 29.84 | 29.80 | -0.04 | 29.0 | 29.0 | 42.0 | 43.0 | 0.0% | 0.1% |
| tile | late | 37.97 | 39.06 | +1.09 | 37.0 | 38.0 | 53.0 | 54.0 | 0.0% | 0.0% |
| meeple | all | 3.47 | 3.38 | -0.09 | 3.0 | 3.0 | 6.0 | 6.0 | 19.9% | 22.5% |
| meeple | early | 3.92 | 3.95 | +0.04 | 4.0 | 4.0 | 6.0 | 6.0 | 4.9% | 4.3% |
| meeple | mid | 3.55 | 3.46 | -0.09 | 3.0 | 3.0 | 6.0 | 6.0 | 15.4% | 17.4% |
| meeple | late | 2.99 | 2.76 | -0.23 | 3.0 | 2.0 | 6.0 | 6.0 | 38.2% | 45.0% |

**Meeples committed by phase tercile** (per game)

| phase | slot | walled449 | fixed_v1 | Δ |
|---|---|---:|---:|---:|
| early | normal | 9.08 | 9.30 | +0.22 |
| early | monk | 1.82 | 1.86 | +0.04 |
| early | farmer | 3.69 | 4.04 | +0.36 |
| early | pass | 8.41 | 7.79 | -0.62 |
| early | *free meeples (both seats)* | 7.90 | 7.68 | -0.22 |
| mid | normal | 6.78 | 6.51 | -0.26 |
| mid | monk | 1.35 | 1.32 | -0.03 |
| mid | farmer | 1.74 | 1.77 | +0.02 |
| mid | pass | 14.13 | 14.35 | +0.22 |
| mid | *free meeples (both seats)* | 3.11 | 2.84 | -0.26 |
| late | normal | 5.84 | 5.16 | -0.68 |
| late | monk | 0.91 | 0.83 | -0.08 |
| late | farmer | 1.43 | 1.52 | +0.10 |
| late | pass | 16.71 | 16.48 | -0.23 |
| late | *free meeples (both seats)* | 1.71 | 1.49 | -0.22 |

Replay integrity: walled449 449/449 terminal scores reproduced · fixed_v1 400/400. (A single mismatch aborts the leg — a wrong profile shows up here first.)

## 3. Farm-economy norms

Instrument: `scripts/analyzer/corpus_stats.py` (existing), one run per corpus under its own profile/R9 environment. Per-seat distributions unless stated.

| metric | walled449 | fixed_v1 | Δ |
|---|---:|---:|---:|
| farm_pts (mean) | 20.492 | 20.809 | +0.317 |
| farm_pts (median) | 21.000 | 21.000 | +0.000 |
| farm_pts_frac (mean) | 0.207 | 0.212 | +0.005 |
| farm_pts_per_farmer (mean) | 6.020 | 5.736 | -0.284 |
| first_farm_turn (mean) | 6.761 | 5.243 | -1.518 |
| first_farm_turn (median) | 4.000 | 3.000 | -1.000 |
| first_farm_k_remaining (mean) | 64.239 | 64.757 | +0.518 |
| farm_meeple_turns_locked (mean) | 157.815 | 168.452 | +10.637 |
| farmers per seat (mean) | 3.430 | 3.669 | +0.239 |
| seats with no farmer | 0.000 | 1.000 | +1.000 |
| farmers placed, total | 3080.000 | 2935.000 | -145.000 |
| placement k-band frac: early | 0.552 | 0.551 | -0.001 |
| placement k-band frac: mid | 0.246 | 0.241 | -0.005 |
| placement k-band frac: late | 0.202 | 0.208 | +0.006 |
| final_score (mean) | 98.261 | 97.956 | -0.304 |
| during_play_frac (mean) | 0.549 | 0.557 | +0.008 |
| incomplete_pts (mean) | 23.011 | 21.726 | -1.285 |
| stranding rate, non-farmer | 0.431 | 0.407 | -0.023 |
| n_turns (mean) | 72.000 | 71.000 | -1.000 |
| n_completions (mean) | 22.989 | 22.887 | -0.101 |
| n_cloisters_closed (mean) | 3.982 | 3.962 | -0.020 |
| n_cities_closed (mean) | 9.797 | 9.863 | +0.065 |
| n_roads_closed (mean) | 9.209 | 9.062 | -0.147 |
| total_points (mean) | 196.521 | 195.912 | -0.609 |

## 4. Artifacts

- `measurement/f9_phase_c/LUCK_SLICE.json`
- `measurement/f9_phase_c/DECISION_DENSITY_walled449.json`
- `measurement/f9_phase_c/CORPUS_STATS_walled449.json`
- `measurement/f9_phase_c/CORPUS_STATS_walled449.md`
- `measurement/f9_phase_c/DECISION_DENSITY_fixed_v1.json`
- `measurement/f9_phase_c/CORPUS_STATS_fixed_v1.json`
- `measurement/f9_phase_c/CORPUS_STATS_fixed_v1.md`
- `measurement/f9_phase_c/corpus_fixed_v1.jsonl`

Reproduce:

```
scripts/rules_fixed/run_phase_c.py measurement/champ_action_logs/champ_games.jsonl /mnt/c/carc-shared/f9_wall_probe_20260802/fixed_v1/ --ref-label walled449 --new-label fixed_v1 --ref-profile walled -o measurement/f9_phase_c --workers 4
```
