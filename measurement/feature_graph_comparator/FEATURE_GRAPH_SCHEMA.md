# Feature-Graph Action Comparator — SCHEMA

**Status:** proposed (Stage 0) · 2026-06-28
Two levels: **A** minimal tabular action-feature/delta vector (built now), **B** optional graph
(deferred unless A shows promise). For this pilot we build **A**; B is sketched for later.

All features are computed for each **teacher-visited canonical child** of a root, using the same
id-deduped enumeration as `value_resurrection/{dump_dataset,leaf_audit}.py`, from the FIXED root
player's seat (root-POV) — matching the teacher's `action_q` convention. Frozen v2.9 cfg =
`EH._heur_leaf_cfg(2.0)`, config_hash `7fc930b82801cb43` (Bmild curve `-8,-4,-1,0,2,3,4,5`,
bonus_cap=8, opp_cap=8). Sources: `flat_leaf.decompose`, `leaf_v29.decompose_v29`,
`virtual_score_v2`, `game.get_next_state`, `state.meeples` / placed-meeple maps.

Sign convention: all "self/opp" are **root-player vs opponent**. Deltas are **child − parent**
(parent decomposition computed once per root, reused across siblings).

---

## Level A — tabular action-feature schema (~50 scalars)

Each row = one (root, child). Tiered so baselines can ablate **weighting** (Tier-1) vs
**representation** (Tier-2).

### Group F — context (constant across siblings; for conditioning) — 9
Differenced-out in pairwise models (cancels), used raw in listwise / as concat context.
| # | name | source |
|---|---|---|
| F1–F5 | phase one-hot {opening, midgame, late_mid, pre_endgame, endgame} | rec.phase |
| F6 | k_remaining (tiles left, /10) | rec.k_remaining |
| F7 | score_margin signed root-POV (/10) | state.scores |
| F8 | meeples_free_self (parent) | state.meeples[root] |
| F9 | meeples_free_opp (parent) | state.meeples[opp] |

### Tier-1 — leaf-component features (the v2.9 leaf's OWN terms) — 13
Tests: *can a linear reweight of the leaf's own components beat the leaf?*
| # | name | source |
|---|---|---|
| T1.1 | leaf_total (raw virtual_score_v2, /15) | virtual_score_v2(child) |
| T1.2 | leaf_q = tanh(leaf_total) | (same) |
| T1.3 | base (v1 end-of-game diff, /15) | decompose_v29(child).base |
| T1.4 | closure_self (/8) | .closure_self |
| T1.5 | closure_opp (/8) | .closure_opp |
| T1.6 | meeple_contribution (curve term) | .meeple_flat + .meeple_curve_delta |
| T1.7 | pretransform_total (/15) | .pretransform_total |
| T1.8 | terminal flag (child ended) | game.get_game_ended |
| T1.9–T1.13 | parent→child DELTAS: d_base, d_closure_self, d_closure_opp, d_meeple, d_pretransform | child − parent decompose_v29 |

### Tier-2 — structural + action/move features — ~28
Tests: *does explicit feature/action structure beat the leaf?*

**Action/move semantics (8)**
| # | name | source |
|---|---|---|
| T2.1 | meeple_placed (0/1) | action / child meeples delta |
| T2.2–T2.5 | meeple_type one-hot {city, road, farm, monastery} | placed-meeple side/feature |
| T2.6 | net_meeple_delta_self (returns from completions − placement) | meeples[root] child−parent |
| T2.7 | immediate_score_delta_self (points scored by this move) | scores child−parent |
| T2.8 | immediate_score_delta_opp | scores child−parent |

**Child structural state (12)**
| # | name | source (Decomp on child) |
|---|---|---|
| T2.9 | n_open_cities | city_root_finished (False count) |
| T2.10 | n_open_roads | road_root_finished |
| T2.11 | n_open_farms | farm_root_keys |
| T2.12 | total_city_open_edges (sum closure proximity) | Σ city_root_open_n |
| T2.13 | n_cities_self_owned | meeple→city_side_root map |
| T2.14 | n_cities_opp_owned | (same) |
| T2.15 | n_cities_contested (both players) | (same) |
| T2.16 | n_meeples_locked_self (on unfinished feats) | meeples on open roots, root seat |
| T2.17 | n_meeples_locked_opp | (same, opp) |
| T2.18 | max_open_city_value_self (largest unclosed city you hold) | city_root_delta on self-owned open |
| T2.19 | n_farms_self_owned | farm_pos0_root + meeples |
| T2.20 | n_farms_contested | (same) |

**Parent→child structural deltas (8)**
| # | name | source |
|---|---|---|
| T2.21 | d_total_city_open_edges (exposure change) | Σ open_n child−parent |
| T2.22 | d_n_open_cities | child−parent |
| T2.23 | d_meeples_locked_self | child−parent |
| T2.24 | d_n_contested | child−parent |
| T2.25 | opp_feature_touched (move extends/blocks an opp-owned feature) | root-set membership diff |
| T2.26 | feature_completed_by_move (any city/road/monastery closed) | finished-set diff |
| T2.27 | completed_value_self (points to self from closures) | city/road_root_delta of newly-finished, self |
| T2.28 | completed_value_opp | (same, opp) |

> Notes. Continuous features are pre-scaled (the `/10`, `/15`, `/8` above) so a linear model is
> well-conditioned; exact scalers are fit on train and stored in the dataset meta. Monastery
> features (no Decomp field) are read directly from the 3×3 neighbourhood + placed-meeple map.
> The parent decomposition (`decompose`, `decompose_v29`) is computed **once per root** and reused
> across its siblings — the per-child marginal cost is one child decompose pair.

### Stored alongside each row (labels + provenance — reused, not recomputed-blindly)
`oracle_q` (h6400, target), `leaf_q` (v2.9, baseline — must match stored), `group_id` (sibling set),
`action_id`, `game_seed`, `ply`, `phase`, `q_gap`, `legal_n`, `is_teacher_best`. Splits are by
**game_seed** (no sibling set spans train/val/test) — see `FEATURE_GRAPH_DATASET.md`.

---

## Level B — optional graph schema (DEFERRED; sketch only)

Build only if Level-A feature/action baselines beat v2.9 leaf and a graph is the natural next step.
Keep small; do not let it become a framework rewrite.

```
Nodes:    tile · feature(city|road|farm|monastery) · legal-action · player · meeple
Edges:    tile∈feature · feature↔farm-adjacency · action-creates/modifies-feature
          · player-owns/contests-feature · open-boundary relations · possible-completion
Node feats: per-feature (size, open_n, finished, owner, meeple_count, score_delta);
            per-action (the Level-A action vector); per-player (meeples, score)
Model:    small message-passing net over the parent/child graph, action node read-out ->
          per-child score; listwise loss over siblings (same target as C3).
```

---

## How a model consumes this

- **Pairwise (C1/C2):** input = (Tier-1 ⊕ Tier-2)_i − (...)_j ⊕ raw F context; target = sign(Q_i − Q_j),
  weight = |Q_i − Q_j| (emphasize Qgap ≥ 0.02). Context F appended un-differenced.
- **Listwise (C3):** score each child from its full vector; softmax over the set vs teacher Q-softmax.
- **Residual (C4):** target = oracle_q − leaf_q; select by `leaf_q + α·learned_residual`, α swept
  {0, .05, .1, .25, .5, 1}.
- **Ablations:** Tier-1-only vs Tier-1+Tier-2 → attributes any win to weighting vs representation.
