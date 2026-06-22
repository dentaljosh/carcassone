# Phase 4 — Midgame Baseline Ranking vs the heur@3200 Teacher

> **Soft target, not ground truth.** heur@3200 (deep v2.7 search, real-deck) is the strongest
> practical midgame ruler; its choice is the top-1 target and its root child mover-Q gives both
> the ranking (Kendall τ) and `q_regret` (best−picked child-Q, value units, over visited picks).
> Clairvoyance-leaning (see REUSE_AND_SCOPE.md). **FACT** unless marked INTERPRETATION.

Joined positions: **1000**. Random top-1 ≈ 0.038.

## Overall (all bands)

| selector | n | top1 | top3 | q_regret | reg_cov |
|---|---|---|---|---|---|
| random | 1000 | 0.038 | None | 0.0822 | 0.84 |
| iter8(MCTS@200) | 1000 | 0.487 | None | 0.0071 | 1.0 |
| iter8(policy-prior) | 1000 | 0.259 | None | 0.0412 | 0.999 |
| v2.7-static(label) | 1000 | 0.48 | None | 0.0113 | 1.0 |
| heur@800(shallow-teacher) | 1000 | 0.658 | None | 0.0016 | 1.0 |
| immediate-score(forced-net) | 1000 | 0.132 | 0.981 | 0.0629 | 1.0 |
| score-diff-after | 1000 | 0.132 | 0.981 | 0.0629 | 1.0 |
| meeple-recovery | 1000 | 0.127 | 0.987 | 0.0663 | 1.0 |
| best-meeple(incl-claim) | 1000 | 0.138 | 0.958 | 0.0612 | 1.0 |
| completion-then-score | 1000 | 0.13 | 0.955 | 0.0757 | 1.0 |
| open-edge-progress | 1000 | 0.104 | 0.773 | 0.084 | 1.0 |
| bag-aware-closure | 1000 | 0.105 | 0.757 | 0.0835 | 1.0 |
| composite-simple | 1000 | 0.183 | 0.77 | 0.0616 | 1.0 |
| v2.7-static(depth0) | 1000 | 0.48 | 0.964 | 0.0113 | 1.0 |
| composite-v2.7+delta | 1000 | 0.478 | 0.9 | 0.0116 | 1.0 |

## Kendall τ-b — feature vs teacher child-Q ranking (over VISITED legal actions)

| feature | mean τ | informative positions | informative frac |
|---|---|---|---|
| v2.7 | 0.6104 | 904 | 0.904 |
| imm_net | 0.3002 | 315 | 0.315 |
| best_meeple | 0.2796 | 355 | 0.355 |
| score_diff | 0.3002 | 315 | 0.315 |
| meeple_delta | 0.2197 | 221 | 0.221 |
| open_edge_delta | 0.0159 | 602 | 0.602 |
| bag_closure | 0.0092 | 608 | 0.608 |
| composite | 0.1097 | 717 | 0.717 |

## Offline diagnostic linear ranker (train/test split by position — NOT production)

**Without v2.7 (raw+bag features only):**
- test top-1 vs teacher: **0.1467** (train 700 / test 300 positions)
- standardized coefficients: `{'imm_net': 0.0099, 'meeple_delta': -0.008, 'completion_pts': 0.0068, 'open_edge_delta': 0.0102, 'aff_min_open': -0.0064, 'bag_supply_factor': -0.0127}`

**With v2.7 added:**
- test top-1 vs teacher: **0.4533**
- standardized coefficients: `{'imm_net': 0.0007, 'meeple_delta': -0.002, 'completion_pts': 0.0036, 'open_edge_delta': -0.0065, 'aff_min_open': 0.0074, 'bag_supply_factor': 0.0022, 'v2.7': 0.5943}`

(A ranker that needs v2.7 to match the teacher, and where the raw/bag coefficients are small,
would indicate the features carry little signal independent of v2.7. INTERPRETATION in the report.)

## Splits

Full tables: [MIDGAME_RESULTS_BY_PHASE.csv](MIDGAME_RESULTS_BY_PHASE.csv) ·
[_BY_SOURCE.csv](MIDGAME_RESULTS_BY_SOURCE.csv) ·
[_BY_DISAGREEMENT.csv](MIDGAME_RESULTS_BY_DISAGREEMENT.csv).

### top-1 vs teacher by band (key selectors)

| selector | opening | early_mid | mid | late_mid | pre_endgame |
|---|---|---|---|---|---|
| iter8(MCTS@200) | 0.61 | 0.5 | 0.485 | 0.45 | 0.39 |
| v2.7-static(label) | 0.485 | 0.51 | 0.43 | 0.46 | 0.515 |
| heur@800(shallow-teacher) | 0.755 | 0.72 | 0.58 | 0.6 | 0.635 |
| immediate-score(forced-net) | 0.14 | 0.115 | 0.12 | 0.135 | 0.15 |
| completion-then-score | 0.145 | 0.11 | 0.12 | 0.135 | 0.14 |
| open-edge-progress | 0.095 | 0.09 | 0.09 | 0.115 | 0.13 |
| composite-v2.7+delta | 0.485 | 0.52 | 0.45 | 0.44 | 0.495 |
| random | 0.075 | 0.035 | 0.04 | 0.03 | 0.02 |

