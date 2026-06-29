# FEASIBILITY.md — FGSR Stage 0.5 cheap feasibility gate

> **STATUS: 🟢 GATE PASSES** — tail-signal rate 80% on 20 decisive-tail roots; extraction mean 66.7 ms/root, mean graph 98 nodes / 142 edges.

> Leaf config_hash `7fc930b82801cb43` (frozen v2.9). 50/50 roots extracted OK, 0 errors. NET-FREE, CPU. _2026-06-29._


## Graph size (per root)

| metric | mean | p50 | p90 | min | max |
|---|---|---|---|---|---|
| nodes | 97.5 | 102 | 160 | 14 | 176 |
| edges | 142.2 | 148 | 231 | 14 | 256 |

### Node counts by type (mean / min / max)

| node type | mean | min | max |
|---|---|---|---|
| tile | 37.6 | 3 | 69 |
| city_feature | 9.8 | 1 | 20 |
| road_feature | 14.2 | 0 | 29 |
| farm_feature | 15.9 | 2 | 34 |
| monastery_feature | 7.2 | 0 | 14 |
| player | 2 | 2 | 2 |
| meeple | 9.8 | 2 | 14 |
| deck_bucket | 1 | 1 | 1 |

### Edge counts by type (mean / min / max)

| edge type | mean | min | max |
|---|---|---|---|
| tile_belongs_to_feature | 65.2 | 3 | 120 |
| city_touches_farm | 18.5 | 1 | 40 |
| feature_touches_feature | 18.5 | 1 | 40 |
| meeple_on_feature | 8.1 | 2 | 12 |
| meeple_belongs_to_player | 9.8 | 2 | 14 |
| player_owns_feature | 6.1 | 2 | 10 |
| feature_has_open_boundary | 15.1 | 3 | 31 |
| player_contests_feature | 2.4 | 2 | 6 |

## Extraction cost

| metric | mean | p50 | p90 |
|---|---|---|---|
| extract ms/root | 66.69 | 48.4 | 157.7 |
| total ms/root (replay+extract) | 69.82 | 51.9 | 162.9 |
| est bytes/root | 9707 | 9214 | 17443 |

Projected full-dataset size (10,351 roots × mean est_bytes) ≈ **100.5 MB** uncompressed (compresses well — mostly float32).


## TAIL-SIGNAL CHECK (the go/no-go)

On the **20 decisive-tail roots** (h200 top move != h6400 top move), do the structural action-node attributes differ across the two children h200 and h6400 disagree on?

- **16/20 (80%)** show ≥1 differing structural attribute.
- Mean **2.8 of 15** checked structural attrs differ per tail root.
- **Verdict: PASS.** The schema captures discriminating structure on the decisive tail — proceed to Stage 2.

**The 4/20 no-signal tail roots are themselves a finding, not a schema bug.** All 4
have `leaf_q_gap == 0.0` between the two contested children — i.e. the static v2.9
leaf *and* every structural attribute are identical for the move h200 prefers and the
move h6400 prefers (games 60/104, 307/76, 282/136, 191/128). These are positions
where only deep search separates the moves; no static feature graph can, by
construction. This bounds the reranker's ceiling: ~20% of the decisive tail is
structurally invisible to any static model (the "magnitude ceiling" FGSR_PLAN flagged).
The dataset stores `leaf_q` per action so this slice is identifiable downstream and a
model can be told to abstain on it.

### Concrete examples (h200-child vs h6400-child structural attrs that differ)

**Root game 2900000246 ply 62 (midgame)** — h200 picks action 2503, h6400 picks 2510; regret(h200)=0.0249, q_gap_6400=0.0249. leaf-Q gap between the two children = 0.0, h6400-Q gap = 0.0249.

| struct attr | h200 child | h6400 child | Δ (6400−200) |
|---|---|---|---|
| T2_n_meeples_locked_self | 6.0 | 5.0 | -1.0 |
| T2_d_meeples_locked_self | 1.0 | 0.0 | -1.0 |

**Root game 2900000213 ply 74 (late_mid)** — h200 picks action 1266, h6400 picks 1261; regret(h200)=0.0623, q_gap_6400=0.0623. leaf-Q gap between the two children = 0.0, h6400-Q gap = 0.0623.

| struct attr | h200 child | h6400 child | Δ (6400−200) |
|---|---|---|---|
| T2_feature_completed_by_move | 0.0 | 1.0 | 1.0 |

**Root game 2900000013 ply 116 (pre_endgame)** — h200 picks action 860, h6400 picks 1067; regret(h200)=0.0786, q_gap_6400=0.0786. leaf-Q gap between the two children = -0.1241, h6400-Q gap = 0.0786.

| struct attr | h200 child | h6400 child | Δ (6400−200) |
|---|---|---|---|
| T2_total_city_open_edges | 10.0 | 8.0 | -2.0 |
| T2_d_total_city_open_edges | 1.0 | -1.0 | -2.0 |
| T2_d_n_open_cities | 1.0 | -1.0 | -2.0 |
| T2_feature_completed_by_move | 0.0 | 1.0 | 1.0 |
| T2_n_open_cities | 7.0 | 5.0 | -2.0 |


## Schema notes / choices made

- `open_boundary` FOLDED into feature `open_edges`/`open_ends` + `feature_has_open_boundary` edges to a singleton sentinel (schema open-question, 'fold first').
- `tile` ply-placed recency omitted (not stored on state); move recency lives on action nodes.
- `road_feature.open_ends` reduced to a has-open binary (precise endpoint scan needs node-side data; deferred).
- Action-node attrs = the comparator pilot's 50 per-child scalars (`build_feat_dataset.FEAT_NAMES`), reused verbatim; h200/h800/h6400 (N, Q_rootpov) joined from `roots_mcts.jsonl levels`.
- Owner/contested derived with the SAME meeple→root mapping `flat_leaf._final_scores` uses (`city_side_root`/`road_side_root`/`farm_pos0_root` + `_winners`).
