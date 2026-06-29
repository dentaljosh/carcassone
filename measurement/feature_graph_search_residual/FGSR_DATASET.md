# FGSR_DATASET.md — Post-Search Residual Graph Dataset

> **STATUS: 🟢 BUILT — Stage 2 complete (10,351 roots, 168,567 action rows, 0 errors).**
> Cheap feasibility gate PASSED (tail-signal 0.80) — see [FEASIBILITY.md](FEASIBILITY.md).
> NET-FREE, CPU-only, no search run, no model trained. v2.9 / PRODUCTION.yaml untouched.
> Leaf config_hash `7fc930b82801cb43` (frozen v2.9). _Built 2026-06-29._

## What it is

For every one of the **10,351** post-search-residual MCTS-play roots
(`../post_search_residual/data/roots_mcts.jsonl`, filtered to ≥2 visited children
at the h6400 reference — the `psr_lib.load_roots` set), a CPU replay pass attaches:

1. a **typed feature graph** (per [FGSR_SCHEMA.md](FGSR_SCHEMA.md)) from
   `flat_leaf.decompose(state)` + `state`, and
2. one **action node per legal move** (= deduped canonical child, matching the
   stored level-map action ids) carrying the comparator pilot's **50 per-child
   scalars** (`scripts/feature_graph/build_feat_dataset.py::FEAT_NAMES`, reused
   verbatim) + the stored h200/h800/h6400 `(N, Q_rootpov)`.

No new deep search: all sim levels were already stored per root by the residual
pilot. This pass is pure replay + decompose + graph/action extraction.

## Root counts (per source / phase)

Source: `roots_mcts.jsonl` (real MCTS-play distribution), 12,000 raw → **10,351**
after the `load_roots` filter (drops forced-move / <2-visited-child roots).

| phase | roots | action rows |
|---|---|---|
| opening | 2,334 | 18,720 |
| midgame | 2,241 | 28,984 |
| late_mid | 2,043 | 35,503 |
| pre_endgame | 1,878 | 39,966 |
| endgame | 1,855 | 45,394 |
| **total** | **10,351** | **168,567** |

(`roots_adaptive.jsonl` — 3,000 greedy-self-play roots — was NOT built here; it is
the secondary robustness split available for a later run.)

### Decisive tail / label sizes (derivable, not baked in)

| class | count | frac |
|---|---|---|
| decisive tail (`sel(h200) != sel(h6400)`) | 3,007 | 29.0% |
| `pos_strong` (q_gap_6400 ≥ 0.02 ∧ regret(h200) ≥ 0.02) | 287 | 2.8% |
| `pos_medium` (≥ 0.01 / ≥ 0.01) | 542 | 5.2% |
| negative | 9,454 | 91.3% |

Labels are **NOT stored** — they are re-derived from the stored `q200`/`q6400` via
`psr_lib` (verified: for tail roots the stored-`q6400` argmax action reproduces
`sel(h6400)` exactly). This keeps the dataset label-scheme-agnostic.

## Node / edge count distributions

Per root (mean / p50 / p90 / max), over all 10,351 roots:

| metric | mean | p50 | p90 | max |
|---|---|---|---|---|
| nodes | 100.6 | 106 | 162 | 188 |
| edges | 147.0 | 156 | 233 | 279 |
| action nodes | 16.3 | 11 | 38 | 79 |

Node types: `tile` (~38 mean) · `city_feature` (~10) · `road_feature` (~14) ·
`farm_feature` (~16) · `monastery_feature` (~7) · `player` (2) · `meeple` (~10) ·
`deck_bucket` (1). Edge types: `tile_belongs_to_feature` (~65) ·
`city_touches_farm` / `feature_touches_feature` (~18 each) · `meeple_on_feature`,
`meeple_belongs_to_player`, `player_owns_feature`, `player_contests_feature`,
`feature_has_open_boundary`. Full per-type distribution: [FEASIBILITY.md](FEASIBILITY.md).
The graph stays small (≤ ~188 nodes/root) → a 2–3 layer GNN is CPU-trainable.

## Per-root extraction time

Feasibility-gate timing (single-thread): **mean 66.7 ms/root** extract
(p50 48 ms, p90 158 ms) + ~3 ms replay. Full parallel build: **10,351 roots in
62 s** with 14 fork workers (`nice -n 19`) on the 5900XT box = **168 roots/s**
aggregate. CPU-bound, ~99% on all 14 workers.

## File format spec — `data/`

### `rows_feat.npz` (3.9 MB) — action-node feature matrix (the primary signal)

Mirrors the comparator's `rows_feat.npz` so `psr_lib` / `eval_lib` grouping +
labels work unchanged. One row per (root, deduped-child):

| key | shape | dtype | meaning |
|---|---|---|---|
| `feat` | (168567, 50) | float32 | the 50 comparator scalars, `FEAT_NAMES` order |
| `group_id` | (168567,) | int32 | root id (== `roots_mcts.jsonl group_id`) |
| `action_id` | (168567,) | int32 | engine action id of the child |
| `game_seed` | (168567,) | int64 | deck seed — for `seed_split` (no leakage) |
| `game_id` | (168567,) | int64 | source game id |
| `ply` | (168567,) | int16 | root ply |
| `phase` | (168567,) | <U12 | opening / midgame / late_mid / pre_endgame / endgame |
| `n200`, `n800`, `n6400` | (168567,) | int32 | stored visit counts at those levels |
| `q200`, `q800`, `q6400` | (168567,) | float32 | stored `Q_rootpov` (tanh-Q) |
| `in_h200` | (168567,) | int8 | child explored by h200? (see note) |
| `leaf_q` | (168567,) | float32 | static v2.9 leaf-Q of the child (`tanh(vs/15)`) |
| `feat_names` | (50,) | <U40 | the 50 scalar names |

Only levels {200, 800, 6400} are stored (200 = shallow, 6400 = reference, 800 =
escalation diag). The source has {200,400,800,1600,3200,6400} if more are ever needed.

### `graphs.pkl` (97 MB) — typed feature graphs keyed by `group_id`

`pickle` dict `{group_id: graph}` (graphs are heterogeneous, variable-size dicts;
npz is awkward for that). Each `graph`:

```
{
  "nodes": {node_type: [attr_dict, ...]},   # stable per-type local index
  "edges": {edge_type: [(src_type, src_idx, dst_type, dst_idx), ...]},
  "meta":  {root_player, phase, k_remaining, n_nodes, n_edges,
            node_counts, edge_counts, _notes},
}
```

Node/edge attribute names follow [FGSR_SCHEMA.md](FGSR_SCHEMA.md). Owner/contested
fields use the SAME meeple→root mapping `flat_leaf._final_scores` uses
(`city_side_root`/`road_side_root`/`farm_pos0_root` + `_winners`), so they are
bit-consistent with the production leaf scorer.

### `manifest.json` — full resolved config

git rev, leaf config_hash, source files, counts, feat names, levels, node/edge
stats, format spec, fold-choices, leakage note, build wall-clock.

## Leakage note

Split by **`game_seed`** (`psr_lib.seed_split` / `eval_lib.seed_split`, 70/15/15).
Audited: **0 group_ids span >1 game_seed**, and all children of a root share its
`group_id` + `game_seed`, so grouping is leak-free — no root (and no child of a
root) crosses a split. 400 distinct seeds → 270 tr / 64 va / 66 te buckets.

## Schema notes / choices made (carried from the gate)

- `open_boundary` is **folded** into feature `open_edges`/`open_ends` +
  `feature_has_open_boundary` edges to a singleton `_open` sentinel (schema
  open-question §1, "fold first").
- `tile` ply-placed recency is **omitted** (not stored on `state`); move recency
  lives on action nodes implicitly via the move semantics scalars.
- `road_feature.open_ends` is reduced to a **has-open binary** (precise endpoint
  scan needs node-side data; deferred).

## Note on `in_h200` (a finding, not a bug)

`in_h200` is **1 for every action row.** The action enumeration derives from the
same deduped canonical-child set that the level map records, and at every root
in this dataset h200 visited **all** of the (deduped) legal children — i.e. there
are no h200-unexplored children here. So the schema's "explored by h200?"
distinction is degenerate on this root distribution; a reranker therefore re-ranks
h200's *own visited set*, and the adaptive-scheduler's "escalate unexplored
children" framing does not apply at these (mostly low-legal-n) roots. The column
is kept for forward-compat (greedy-distribution roots may differ). **The
training-relevant separation is `decisive tail` (3,007) and `pos_strong` (287),
not `in_h200`.**

## Pointers

- Extractor: `scripts/feature_graph_search_residual/extract_graph.py`
- Gate: `scripts/feature_graph_search_residual/run_feasibility_gate.py`
- Builder: `scripts/feature_graph_search_residual/build_dataset.py`
- Reused: `scripts/feature_graph/build_feat_dataset.py` (50 scalars),
  `scripts/post_search_residual/psr_lib.py` (labels/split),
  `scripts/measurement_infra/` (frozen v2.9 env, lossless replay).
