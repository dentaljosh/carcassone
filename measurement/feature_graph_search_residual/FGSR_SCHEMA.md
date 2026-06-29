# FGSR_SCHEMA.md — Feature Graph Schema

> **STATUS: 🟢 IMPLEMENTED — extractor built + gate-passed + full dataset built.**
> `scripts/feature_graph_search_residual/extract_graph.py` implements this schema;
> the cheap feasibility gate PASSED (tail-signal 0.80) and the full 10,351-root
> dataset is built ([FGSR_DATASET.md](FGSR_DATASET.md), [FEASIBILITY.md](FEASIBILITY.md)).
> Fold-choices made: open_boundary folded into feature attrs; tile recency omitted;
> road open_ends → has-open binary (see §Graph-lite + the dataset doc).
>
> _Last updated 2026-06-29._

## Design principles

1. **Extract once per ROOT**, from the memo-cached `decompose(state)` + `state`.
   Per-child (`legal_action`) attributes come from applying each action and
   diffing the child decomposition — exactly the comparator pilot's existing 50
   per-child scalars, reused.
2. **Every attribute names its source** (`Decomp` field / `state` attr / derived /
   comparator-fn / search-snapshot) so extraction is a read-off, not new physics.
3. **Phase-normalize** value-like attributes (the residual tail is opening-heavy;
   raw point values are not phase-comparable). Keep both raw and `/k_remaining`
   forms where cheap.
4. **Root-POV sign convention** matches the residual dataset (`Q_rootpov`, tanh-Q).
5. **Two representations ship together:** the full typed graph (§Nodes/§Edges) and
   the **graph-lite fallback** (§Graph-lite) — the model can start on graph-lite
   (a strict superset of the 32-feature MLP) and only escalate to message-passing
   if graph-lite shows life. This bounds the architecture risk.

## Node types

Counts are per root, mid/late game ballpark. ✅ = direct read-off; ⊕ = derived cheaply.

### `tile` — placed tiles  (~30–70/root)
| attr | source |
|---|---|
| (r, c) normalized to board center | `state.placed_coords` ✅ |
| terrain mask (has city/road/farm/monastery side) | `tile.city/road/farms`, `tile.chapel/flowers` ✅ |
| shield / inn flags | `tile.shield`, `tile.inn` ✅ |
| ply-placed (recency) | replay index ⊕ |

### `city_feature` — connected city component  (~3–10)
| attr | source |
|---|---|
| `completed` (finished) | `Decomp.city_root_finished` ✅ |
| `open_edges` | `Decomp.city_root_open_n` ✅ |
| `tile_count` | `len(Decomp.city_root_coords[r])` ✅ |
| `closure_delta` (score if closed) | `Decomp.city_root_delta` ✅ |
| `current_value` / `completed_value` | from delta + finished + shields ⊕ |
| `meeples_p0`, `meeples_p1` | `placed_meeples` × `city_side_root` ⊕ |
| `owner_status` (p0 / p1 / contested / none) | `_winners()` over meeple counts ⊕ |
| `contested_flag` | owner_status == contested ⊕ |
| `adjacent_farms_count` | reverse of `farm_root_adj_city_roots` ⊕ |
| `phase_norm_value` | value / k_remaining ⊕ |

### `road_feature` — connected road component  (~3–10)
| attr | source |
|---|---|
| `completed` | `Decomp.road_root_finished` ✅ |
| `tile_count` | `len(Decomp.road_root_coords[r])` ✅ |
| `open_ends` | road endpoint scan ⊕ |
| `inn_flag` | `tile.inn` on member tiles ✅ |
| `meeples_p0/p1`, `owner_status`, `contested_flag` | `placed_meeples` × `road_side_root` + `_winners()` ⊕ |

### `farm_feature` — connected field component  (~2–6)
| attr | source |
|---|---|
| `adjacent_finished_cities` | `Decomp.farm_root_finished_cities` ✅ |
| `adjacent_city_roots` (potential value) | `Decomp.farm_root_adj_city_roots` ✅ |
| `tile_count` | `len(Decomp.farm_root_keys[r])` ✅ |
| `meeples_p0/p1`, `owner_status`, `contested_flag` | `placed_meeples` × `farm_*_root` + `_winners()` ⊕ |
| `volatility` (cities that could still complete) | adj_city_roots − finished ⊕ |

### `monastery_feature`  (~0–3)
| attr | source |
|---|---|
| `surrounding_count` (0–8) | 8-neighbor scan of `state.board` ⊕ |
| `completed` | surrounding_count == 8 ⊕ |
| `owner` (p0/p1/none) | `placed_meeples` on chapel side ⊕ |
| `score_if_now` | surrounding_count + 1 ⊕ |

### `player` — exactly 2
| attr | source |
|---|---|
| `score` | `state.scores[p]` ✅ |
| `meeples_free` | `state.meeples[p]` ✅ |
| `meeples_locked` | 7 − free (or scan placed) ⊕ |
| `score_margin_signed` | scores[self] − scores[opp] ✅ |
| `is_current_player` | `state.current_player` ✅ |

### `meeple` — placed meeples  (~0–14)
| attr | source |
|---|---|
| `player` | `placed_meeples` index ✅ |
| `on_feature_root` (edge target) | `coordinate_with_side` × `*_side_root` ⊕ |
| `feature_type` (city/road/farm/monastery) | `tile.get_type(side)` ✅ |
| `returnable_soon` (feature near completion) | feature open_edges/surrounding ⊕ |

### `legal_action` — one per legal move  (~10–20)
**Attributes = the comparator pilot's 50 per-child scalars** (`build_feat_dataset.py`),
reused verbatim. Highlights:
| attr group | source |
|---|---|
| tile type / placement (r,c) / rotation | action decode ✅ |
| meeple placement option + type (city/road/farm/monastery one-hot) | action ✅ |
| `imm_score_delta_self/opp` | child vs parent `_struct_summary` ⊕ |
| `completed_value_self/opp` | `_completed_value()` ⊕ |
| `meeple_returned`, `meeple_locked`, `net_meeple_delta` | child−parent `placed_meeples` ⊕ |
| `d_open_edges`, `d_n_open_cities`, `d_contested` | child−parent Decomp ⊕ |
| `opp_feature_touched` | `_opp_feature_touched()` ⊕ |
| `v29_leaf_child_score` (`leaf_q`) | `virtual_score_v2(child)` ✅ |
| **h200 child `(N, Q_rootpov)`** | `roots_mcts.jsonl levels["200"][action]` ✅ |
| **h800 child `(N, Q)`** (diag, if escalated) | `levels["800"][action]` ✅ |

### `deck_bucket` — remaining tile supply  (1 aggregate node, optional per-type)
| attr | source |
|---|---|
| `k_remaining` | `len(state.deck)` ✅ |
| per-type remaining counts | `Counter(state.deck)` ⊕ |
| `can_complete_open_feature` flags | deck types × open-feature edge profiles ⊕ |

### `open_boundary` — open edges of unfinished features  (optional, can fold into feature attrs)
| attr | source |
|---|---|
| position, parent feature root | `state.open_positions` + adjacency ⊕ |
| `completion_tile_count_estimate` | deck types that fit ⊕ |

## Edge types

| edge | from → to | source |
|---|---|---|
| `tile_belongs_to_feature` | tile → city/road/farm | reverse `*_root_coords` / `*_side_root` ✅ |
| `feature_touches_feature` | city↔road, city↔farm | board adjacency + `farm_root_adj_city_roots` ⊕ |
| `city_touches_farm` | city → farm | `farm_root_adj_city_roots` (reversed) ✅ |
| `road_touches_farm` | road → farm | shared-tile adjacency ⊕ |
| `player_owns_feature` | player → feature | `_winners()` per root ⊕ |
| `player_contests_feature` | player → feature | tie in meeple count ⊕ |
| `meeple_on_feature` | meeple → feature | `coordinate_with_side` × `*_side_root` ⊕ |
| `feature_has_open_boundary` | feature → open_boundary | `*_root_open_n > 0` ✅ |
| `tile_type_can_complete_feature` | deck_bucket → feature | deck types × open profile ⊕ |
| `action_modifies_feature` | legal_action → feature | child decomp diff vs parent ⊕ |
| `action_completes_feature` | legal_action → feature | `feature_completed_by_move` ⊕ (`_completed_value`) |
| `action_extends_feature` | legal_action → feature | child tile_count > parent ⊕ |
| `action_places_meeple` | legal_action → meeple/feature | action semantics ✅ |
| `action_returns_meeple` | legal_action → meeple | `meeple_returned` ⊕ |
| `action_creates_open_boundary` | legal_action → open_boundary | child open_n diff ⊕ |

**Derivation cost:** the only edges needing genuine traversal are
`road_touches_farm` and the `action_*_feature` diffs (one extra `decompose` on the
child — already done by the comparator's per-child pass). Everything else is a dict
lookup over `Decomp`.

## Tensorization (for the GNN, G1+)

- Per node type `t`: a feature matrix `X_t ∈ ℝ^{n_t × d_t}` with a learned type
  embedding prepended. Heterogeneous → either typed message-passing (per-edge-type
  weights) or a single token-transformer over `[type_emb ‖ attr]` tokens with an
  edge-type bias.
- Per edge type `e`: an `edge_index_e ∈ ℤ^{2 × m_e}`.
- Readout for the two tasks:
  - **escalation classifier (G3):** global graph pooling → scalar P(h200 wrong).
  - **reranker (G4):** per-`legal_action`-node head → score per explored child;
    rank within the root's child set.
- Graph is small (≤ ~120 nodes/root incl. actions) → a 2–3 layer model, CPU-trainable.

## Graph-lite fallback (the safe bridge — ship first)

If full typed-graph extraction is fragile or shows no signal, fall back to a
flat/relational-lite row that is a **strict superset of the prior 32-feature MLP**:

1. **Action rows** — the comparator's 50 per-child scalars (already includes
   feature/action/delta groups, completed value, meeple lockup/return, contested
   control, open-edge exposure, move semantics).
2. **Top-k child relational features** — for each child: its rank by h200 Q, gap to
   sibling, gap to leaf-best; pooled summaries over the sibling set (so the model
   sees *relative* structure without message passing).
3. **Parent-level search diagnostics** — `top2_q_gap200`, `entropy200`,
   `top_share200`, `n_visited200`, `log_legal_n`, phase one-hot (the residual
   pilot's Tier-A 11).
4. **Root structural scalars** — the residual pilot's Tier-B 21
   (`features_mcts.jsonl`).

Graph-lite is the **G0** model in [FGSR_MODEL.md](FGSR_MODEL.md). It directly tests
"does adding relational/structural representation beat the flat 32-feature MLP?"
before any message-passing complexity. If G0 ties the 32-feature MLP and
`low_top2gap` → Decision B without building the GNN.

## Open questions for review

1. **Node granularity:** include `open_boundary` and per-type `deck_bucket` nodes
   from the start, or fold them into feature/aggregate attrs? (Leaning: fold first,
   add only if G1 needs them.)
2. **Action-node child features:** recompute the comparator's 50 scalars fresh on
   the residual roots (state-agnostic fns) — confirm the MCTS-play root
   distribution doesn't break any assumption baked into those fns.
3. **Reranker target:** rank `legal_action` nodes by `h6400 Q` directly, or by
   `(h6400 Q − h200 Q)` residual? (Leaning: rank by h6400 Q on the decisive tail;
   weight by `q_gap_6400`.)
4. **Do we need new roots?** The decisive tail is ~2.8 % of 10,351 ≈ 290 roots. Is
   that enough to train a relational model, or do we mine more low_top2gap/opening
   roots via the labeling queue first? (Decide at the cheap feasibility gate.)
