# PeNS_SCHEMA — Primitive-feature (Pe) Net-Substrate (NS) schema for the Step-2 warmstart

**Status:** ✅ **v0 LOCKED 2026-06-30** (Joshua) — groups A–F (~82 inputs, incl. the **full 32-type bag histogram**) are FROZEN for the Step-2 run. This is the gating commitment; the warmstart bakes in this exact width. The consolidated, triaged, cross-referenced primitive superset that GATES the Step-2 value-head warmstart. **MEASUREMENT/PLANNING ONLY** — no code, no production change; PRODUCTION.yaml + champion + v2.7 + v2.9 evaluator UNCHANGED. Origin: charter Step 1 PASS (CL-037, [../measurement/feature_planes_gate/STEP1_GATE_RESULTS.md](../measurement/feature_planes_gate/STEP1_GATE_RESULTS.md)) → Step 2 scoping.

> ⚠️ **Why this doc is a hard gate, not a wishlist.** The Step-2 substrate (input width) is **baked in at warmstart and FIXED for the whole 30–50-iter run**. Adding/removing a primitive mid-run = re-warmstart = restart. So the v0 column below is a commitment, triaged once, deliberately.

---

## DOCTRINE (read this first — keep it at the top)

**Encode the ATOMS, not the strategies.** An atom is an *observable fact* about the position or a candidate move: a count, a meeple owner, an open-edge tally, an exact deck-match count, a score delta. The net **invents the concepts** — stealing, farm wars, blocking, tempo, sacrifice — by combining atoms in its hidden layers. It **cannot invent a missing observation**: if the board's farm connectivity or the deck histogram is not in the input, no architecture recovers it (this is exactly what Step 1/CL-033 proved — the 78-ch board-CNN was *blind* to farm + bag, and that blindness, not an architecture-independent ceiling, was half the value head's inertness).

**The corollary that does most of the triage work:** do **not** feed the net a *strategy's output* (a projected final score, a "completion probability", a volatility number). Those are the **value head's job** — feeding them in as inputs caps the net at the quality of the projection you hand-coded. Feed the **exact inputs** the projection would have consumed (deck-match counts, open-edge counts, dead/no-closer flags) and let the head learn the projection. The litmus test: an **assumption-free combinatorial fact** (a deck-match count, a hypergeometric draw-odd, a "no remaining tile can close this" flag) is pure information → **v0-safe**; anything requiring a model of **future play** (P(actually completes), expected final score) is a **projection** → **not-input**.

**Scope:** 2-player Carcassonne, **Base + Farmers only** (no River, no Inns & Cathedrals, no Abbots, no Big meeples — locked scope). Everything is **current-player-POV** and **us/them**, never p0/p1.

**Step-2 v0 model = a FIXED-SCALAR MLP** (~40–60 scalars). This is not a guess: the **CL-034 comparator** (a cheap linear/MLP over **50 handcrafted scalars** from `decompose`/`decompose_v29`) is the **first and only learned ranker to beat the v2.9 leaf offline** (full-pool sibling-regret **−41%**, the win driven by Tier-2 *explicit structure*, not reweighting the leaf's own components — see DECISIONS 2026-06-29 / [`scripts/feature_graph/build_feat_dataset.py`](../scripts/feature_graph/build_feat_dataset.py)). The v0 shortlist below is essentially that proven 50-scalar set, audited against this superset and extended with the **deck-composition axis** Step 1 flagged as the cleanest "net saw something the heuristic can't." The richer **per-object set-transformer / GNN** is the **(b)-tier escalation** — and note CL-036 already found a typed GNN's relational structure **inert** on the post-search residual, so b-tier is justified only on superhuman-headroom grounds, eyes open.

### How to read this doc

Each of the 20 candidate **buckets** is enumerated comprehensively below. Every primitive carries a **tier**:

- **v0** — goes in the fixed-scalar MLP now. Because the MLP cannot take a per-object list, a v0 primitive must be an **owner-split AGGREGATE** (sum / max / count over objects) **or a per-ACTION delta**. For each per-feature primitive tiered v0, the **v0 aggregate form** column gives the concrete reduction (e.g. "city open-edges" → "sum & max of my open-city tiles-to-close, count of my open cities").
- **b** — needs the per-object set/GNN model (the full per-feature tables, geometry, reachability/contest-paths/merge-routes). Superhuman-headroom escalation.
- **not-input** — excluded from net inputs. Three sub-categories: **(a)** model-laden **projections** (value-head's job), **(b)** **search diagnostics** (scheduler/reranker territory; CL-035 found a one-line heuristic beats ML there and it doesn't convert to strength), **(c)** **teacher values** (these are the LABELS / warmstart target, not deployable inputs).

**Symmetry (bucket 18) is MANDATORY infra, not a feature choice** — POV-normalize everything, encode us/them. It is a hard requirement on the whole substrate, not a row to triage.

**Leakage rule:** the deck **HISTOGRAM** is allowed (fair information — both players know the bag composition); the deck **ORDER** is forbidden (would leak the future draw). Bucket-2 and bucket-8 primitives are flagged for leakage risk accordingly.

### THE MUST-HAVE-10 v0 SET (called out per spec)

These ten families are **v0 by default** — the backbone of the pilot MLP:

1. **Global score / phase / player** (score margin POV, tiles-left, phase one-hot)
2. **Meeple economy** (free/locked per player, us/them)
3. **Feature ownership** (counts of cities/roads/farms owned self/opp/contested)
4. **City open-edges** (sum/max/count aggregates over my & opp open cities)
5. **Road open-edges** (analogous aggregates)
6. **Farm connectivity** (who owns which field — the Step-1 +3 farm planes, aggregated)
7. **Farm–city adjacency** (count of incomplete & finished cities touching my/opp fields)
8. **Bag histogram** (the Step-1 +32 per-tile-type deck-composition vector — the newly-sighted axis)
9. **Action-deltas** (immediate score Δ, meeple Δ, completion Δ, open-edge Δ for the candidate move)
10. **Opponent-deltas** (the same deltas applied to the opponent's score/features/meeples)

---

## Cross-reference legend (the honesty columns)

- **in v2.9 leaf?** — does `flat_leaf.decompose` / `virtual_score_v2` / `leaf_v29.decompose_v29` already derive this? (`src/carcassonne_ai/flat_leaf.py`, `virtual_score_v2.py`, `leaf_v29.py`.) If **yes**, a net using it is *refining a known axis*; if **no**, it is where the net can add value over the leaf.
- **in old net?** — does the 78-channel `encode_board` (`src/carcassonne_ai/board_repr.py`) or the 10/12 scalar `features.py` already expose it?
- **in Step-1?** — added by `scripts/feature_planes_gate/step1_planes.py` (the +3 farm-connectivity planes + 32-type bag histogram that PASSED the Gate-A lock).
- **parent / child / action-delta?** — parent-state fact (current position), child-state fact (after a candidate move), or a parent→child delta.

---

## Bucket 1 — Global state

| primitive | observable? | leakage | in v2.9 leaf? | in old net? | in Step-1? | impl source | parent | child | Δ | tier | v0 aggregate form | priority | ablation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| current player | yes | none | implicit (POV) | `features.py` ch6 | — | `state.current_player` | ✓ | | | **v0** | current_player_flag (already POV) | hi | global |
| score p0 / p1 | yes | none | yes (`state.scores`, base) | `features.py` ch2/3 | — | `state.scores` | ✓ | | | **v0** | score_self, score_opp (norm) | hi | global |
| score margin (POV) | yes | none | yes (base = scores diff) | `features.py` ch4 | — | `state.scores[p]-scores[opp]` | ✓ | | | **v0** | score_margin_signed (norm /10) — CL-034 `F_score_margin_signed_div10` | hi | global |
| tiles remaining | yes | none | partial (used in deck scans) | `features.py` ch5 | — | `len(state.deck)` | ✓ | | | **v0** | k_remaining (norm /10 or /72) — CL-034 `F_k_remaining_div10` | hi | global |
| turn / phase (TILES/MEEPLES) | yes | none | no | `features.py` ch7/8 | — | `state.phase` | ✓ | | | **v0** | phase_tiles, phase_meeples one-hot | hi | global |
| phase bucket (opening/mid/pre-end/endgame) | yes | none | no | partial (`game_progress` ch9) | — | derived from tiles-left | ✓ | | | **v0** | 5-way phase one-hot — CL-034 `F_phase_*` | hi | global |
| current tile type / edge-pattern / feature-pattern | yes | none | no (consumed structurally) | yes (ref-tile block ch49–77) | — | `state.next_tile` | ✓ | | | **v0** | ref-tile edge/internal scalars (in old net; carry as small fixed block) | med | global |
| #legal placements | yes | none | no | no | — | `len(legal placements)` | ✓ | | | **v0** | n_legal_placements | med | global |
| #legal meeple options | yes | none | no | no | — | legal meeple count | ✓ | | | **v0** | n_legal_meeple_options | med | global |
| is-leading | yes | none | derivable | derivable | — | sign(margin) | ✓ | | | **v0** | is_leading flag (cheap, redundant w/ margin) | lo | global |
| margin normalized by tiles-left | yes | none | no | no | — | margin / max(1,tiles) | ✓ | | | **v0** | margin_per_tile_remaining (urgency) | med | global |
| points-to-overcome-deficit | yes | none | no | no | — | max(0,-margin) | ✓ | | | **v0** | deficit_points (=relu(-margin)) | lo | global |
| volatility (scoring potential remaining) | **no** (a PROJECTION) | none | no | no | — | — | | | | **not-input (a)** | — feed its INPUTS (open-edge sums, bag) instead | — | excl |

## Bucket 2 — Bag / tile-counting (the newly-sighted axis — Step 1)

> **Leakage gate for the whole bucket:** the per-type **count / histogram is ALLOWED** (fair info); the deck **ORDER is FORBIDDEN**. All v0 forms below are *counts*, never positions in the deck.

| primitive | observable? | leakage | in v2.9 leaf? | in old net? | in Step-1? | impl source | parent | child | Δ | tier | v0 aggregate form | priority | ablation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| remaining count per tile type (raw + normalized) | yes | order=high, hist=none | **NO** (leaf scores current board only) | **NO** | **YES** (32-vec) | `step1_planes.bag_histogram` | ✓ | | | **v0** | the 32-type normalized bag histogram (Step-1, verbatim) | **hi** | bag |
| totals: city-edge / road-edge / cloister-filler tiles remaining | yes | hist=none | no | no | derivable from 32-vec | sum over `state.deck` by type | ✓ | | | **v0** | n_city_tiles_left, n_road_tiles_left, n_cloister_tiles_left | hi | bag |
| straights/curves/junctions/caps/corners/city-road-mixed/farm-connectors remaining | yes | hist=none | no | no | derivable | grouped sums over deck | ✓ | | | **v0** | ~7 coarse-shape-class remaining counts | med | bag |
| per-feature #remaining tile-TYPES that can complete it | yes | hist=none | partial (`_deck_city_supply` permissive) | no | no | deck scan vs feature edge | ✓ | | | **v0** | sum/max over my open features of #completer-types (log-space) | **hi** | bag |
| per-feature #physical copies that can complete it | yes | hist=none | partial | no | no | deck scan | ✓ | | | **v0** | sum/max of #completer-copies for my open features (log-space) | **hi** | bag |
| combinatorial completion-availability (hypergeometric draw-odds) | yes (EXACT combinatorial fact) | hist=none | no | no | no | from counts + tiles-left | ✓ | | | **v0** | P(≥1 completer drawn) per open feature → sum/max (log-space) | med | bag |
| dead / near-dead / live flag (no closer remains) | yes (assumption-free) | none | partial (D16 board-edge only) | no | no | completer-count == 0 | ✓ | | | **v0** | count of my dead / near-dead open features | **hi** | bag |

## Bucket 3 — Meeple economy

| primitive | observable? | leakage | in v2.9 leaf? | in old net? | in Step-1? | impl source | parent | child | Δ | tier | v0 aggregate form | priority | ablation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| free meeples per player | yes | none | yes (`meeple_k`/curve term) | `features.py` ch0/1 | — | `state.meeples` | ✓ | | | **v0** | meeples_free_self, meeples_free_opp — CL-034 `F_meeples_free_*` | **hi** | meeple |
| locked-in {city,road,farm,monastery} per player | yes | none | implicit | no | no | `_struct_summary` locked tally | ✓ | | | **v0** | n_meeples_locked_self/opp (CL-034 T2) + per-kind split | **hi** | meeple |
| scarcity ratio | yes | none | no | no | — | free/(free+locked) | ✓ | | | **v0** | meeple_scarcity_self/opp | med | meeple |
| relative advantage | yes | none | yes (curve diff) | derivable | — | free_self−free_opp | ✓ | | | **v0** | meeple_free_diff (curve already in leaf) | med | meeple |
| features likely/unlikely to return meeples soon | **no** (PROJECTION) | none | no | no | — | — | | | | **not-input (a)** | feed open-edge + completer counts; head infers return | — | excl |
| #legal meeple placements | yes | none | no | no | — | legal count | ✓ | | | **v0** | (= bucket-1 n_legal_meeple_options) | med | meeple |
| per-move: places / returns / traps meeple? net meeple delta | yes | none | no | no | — | child vs parent meeple count | | ✓ | ✓ | **v0** | net_meeple_delta_self, meeple_placed flag — CL-034 T2 | **hi** | action |
| per-move: frees opponent meeple? increases opp pressure? | yes | none | no | no | — | opp meeple count Δ | | ✓ | ✓ | **v0** | net_meeple_delta_opp (mirror) | hi | opp |

## Bucket 4 — City (per component)

> Full per-object table = **b-tier**. v0 takes owner-split aggregates over the components `decompose` already labels (`city_root_*`).

| primitive | observable? | leakage | in v2.9 leaf? | in old net? | in Step-1? | impl source | parent | child | Δ | tier | v0 aggregate form | priority | ablation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| id / segments / meeple count per player (per city) | yes | none | yes (`city_side_root`, `_final_scores`) | partial (per-cell) | — | `flat_leaf.decompose` | ✓ | | | **b** | — (per-object) | — | city |
| current value / completed value | yes | none | yes (`city_root_delta`, `_city_points`) | no | — | `decompose` | ✓ | | | **v0** | sum & max of my/opp open-city closure-delta (CL-034 `max_open_city_value_self`) | hi | city |
| #open edges / open-edge types | yes | none | yes (`city_root_open_n`) | no | — | `decompose` | ✓ | | | **v0** | total_city_open_edges (self/opp) + count_open_cities — CL-034 T2 | **hi** | city |
| owner status (us/them/contested/unowned) | yes | none | yes (via `_winners`) | no | — | `decompose`+meeple tally | ✓ | | | **v0** | n_cities_self / n_cities_opp / n_cities_contested — CL-034 T2 | **hi** | city |
| completable-now? / tiles-needed | yes | none | yes (`city_root_open_n`) | no | — | `decompose` | ✓ | | | **v0** | count of my open cities with open_n==1 (1-tile-from-close) | hi | city |
| remaining completers / extenders | yes | hist=none | partial (`_deck_city_supply`) | no | no | deck scan (bucket 2) | ✓ | | | **v0** | (see bucket-2 completer counts, log-space) | hi | bag |
| dead / live | yes | none | partial (D16) | no | no | open_n==0 or no completer | ✓ | | | **v0** | n_dead_cities_self/opp | med | city |
| touches which farms / pennants (shields) | yes | none | yes (`farm_root_adj_city_roots`, shield in delta) | shield ch17 | — | `decompose` | ✓ | | | **v0** | n_shield_tiles_in_my_open_cities | med | city |
| Move-Δ: completes / extends / adds-edges / reduces-edges | yes | none | no | no | — | child vs parent `decompose` | | ✓ | ✓ | **v0** | feature_completed_by_move, d_total_city_open_edges, d_n_open_cities — CL-034 | **hi** | action |
| Move-Δ: changes-owner / contests / steals | yes | none | no | no | — | owner tally Δ | | ✓ | ✓ | **v0** | d_n_contested (CL-034) + ownership-transition counts | hi | steal |
| Move-Δ: eases/hardens completion / adds-to-farm-value | yes | none | no | no | — | open_n Δ, adj-city Δ | | ✓ | ✓ | **v0** | d_city_open_edges (self), d_farm_adj_incomplete_city | med | action |

## Bucket 5 — Road (per component)

| primitive | observable? | leakage | in v2.9 leaf? | in old net? | in Step-1? | impl source | parent | child | Δ | tier | v0 aggregate form | priority | ablation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| id / length / value / meeple p0/p1 / owner (per road) | yes | none | yes (`road_root_*`, `_road_points`) | partial | — | `decompose` | ✓ | | | **b** | — (per-object) | — | road |
| #open ends / completable? | yes | none | yes (`road_root_finished`); open-ends derivable | no | — | `decompose` | ✓ | | | **v0** | n_open_roads (CL-034) + total_road_open_ends | hi | road |
| owner status self/opp/contested | yes | none | yes (`_winners`) | no | — | `decompose`+tally | ✓ | | | **v0** | n_roads_self / n_roads_opp / n_roads_contested | med | road |
| remaining closers / extenders | yes | hist=none | partial | no | no | deck scan | ✓ | | | **v0** | (bucket-2 road completer counts) | med | bag |
| dead / live / branchiness | yes | none | partial | no | — | open-ends / no closer | ✓ | | | **v0** | n_dead_roads_self/opp | lo | road |
| Move-Δ: completes / extends / branches / changes-owner / traps-meeple / creates-steal / returns-meeple | yes | none | no | no | — | child vs parent | | ✓ | ✓ | **v0** | d_n_open_roads + road feature_completed contribution to imm_score_delta | med | action |

## Bucket 6 — Farm / field (per region) — the Step-1 sighted axis

> Leaf **flood-fills farms** (`farm_*_root`), so farm connectivity is a **known** leaf axis; Step-1 confirmed planes still help (net refines it). v0 = owner-split aggregates from `decompose` + the Step-1 farm planes reduced.

| primitive | observable? | leakage | in v2.9 leaf? | in old net? | in Step-1? | impl source | parent | child | Δ | tier | v0 aggregate form | priority | ablation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| id / region / segments / farmer p0/p1 (per field) | yes | none | yes (`farm_pos0_root`, `farm_root_keys`) | no | farm planes (per-cell) | `decompose` + `step1_planes` | ✓ | | | **b** | — (per-object) | — | farm |
| owner status us/them/contested | yes | none | yes (`_winners` on farm counts) | no | **YES** (`_farm_component_owners`) | `step1_planes` | ✓ | | | **v0** | n_farms_self / n_farms_opp / n_farms_contested — CL-034 T2 | **hi** | farm |
| completed cities touching | yes | none | yes (`farm_root_finished_cities`) | no | — | `decompose` | ✓ | | | **v0** | sum of finished-cities-touching over my fields (= live farm score) | **hi** | farm |
| incomplete cities touching | yes | none | yes (`farm_root_adj_city_roots`) | no | — | `decompose` | ✓ | | | **v0** | sum of incomplete-cities-touching over my/opp fields (growth potential INPUT) | **hi** | farm |
| POTENTIAL future cities touching | yes (geometry) | none | no | no | — | empty-neighbor city-edges | ✓ | | | **b** | (reachability — per-object) | — | farm |
| score-if-game-ended-now | yes | none | yes (3×finished-cities) | no | — | `decompose` | ✓ | | | **v0** | farm_score_now_self/opp (= 3× finished touching) | hi | farm |
| potential score / volatility | **no** (PROJECTION) | none | no | no | — | — | | | | **not-input (a)** | feed incomplete-cities-touching + their open-edges; head projects | — | excl |
| #access / contest paths / ways opp/us can enter / mergeable regions | yes (geometry) | none | no | no | — | board reachability search | ✓ | | | **b** | (contest-paths / merge-routes — GNN) | — | farm |
| city-completions that raise value | yes | none | yes (adj incomplete cities) | no | — | `decompose` | ✓ | | | **v0** | (= incomplete-cities-touching, above) | med | farm |
| Move-Δ: adds-city-adjacency / completes-touching-city / merges-farms | yes | none | no | no | — | child vs parent | | ✓ | ✓ | **v0** | d_farm_finished_cities_self, farm-touch growth Δ | hi | action |
| Move-Δ: splits/denies-access / creates-opp-entry / contests-opp-farm / secures-our-farm / feeds-opp-farm / converts-incomplete-city-into-farm-points | yes | none | partial (growth bonus) | no | — | child vs parent | | ✓ | ✓ | **v0** (aggregate) / **b** (path-level) | d_n_farms_contested, d_farm_score_opp; access-path detail → b | hi | farm |

## Bucket 7 — Monastery / cloister (per)

| primitive | observable? | leakage | in v2.9 leaf? | in old net? | in Step-1? | impl source | parent | child | Δ | tier | v0 aggregate form | priority | ablation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| id / owner / current value / filled neighbor cells | yes | none | yes (`_cloister_points`, `_surrounding_count`) | chapel flag ch18 | — | `flat_leaf` cloister path | ✓ | | | **v0** | n_my_cloisters, sum & max of filled-neighbors (8-n) | med | monastery |
| missing neighbor count / completion value | yes | none | yes (8−surround) | no | — | `_surrounding_count` | ✓ | | | **v0** | sum/max of (8−surround) over my cloisters (closure INPUT) | med | monastery |
| remaining likely fillers | yes | hist=none | no | no | no | deck has any-tile (cloisters fill from any) | ✓ | | | **v0** | tiles-left already covers it (any tile fills a cloister) | lo | bag |
| current tile fills a neighbor? / move places monastery meeple? / eases completion? | yes | none | no | no | — | child vs parent | | ✓ | ✓ | **v0** | mtype_monastery (CL-034), d_cloister_surround | med | action |
| Move-Δ: points / completion-likelihood change / lockup risk / opp monastery aided | yes / **no** for "likelihood" | none | partial | no | — | child vs parent | | ✓ | ✓ | **v0** (Δ-surround) / **not-input (a)** (likelihood) | d_cloister_surround_self/opp | lo | monastery |

## Bucket 8 — Open-boundary / completion-shape

> Leakage gate as bucket 2 (counts allowed, deck order forbidden). Per-boundary detail = b-tier; v0 = aggregates.

| primitive | observable? | leakage | in v2.9 leaf? | in old net? | in Step-1? | impl source | parent | child | Δ | tier | v0 aggregate form | priority | ablation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| per open boundary: feature type / edge location / required edge type | yes | none | partial (`city_root_open_n` counts only) | edge channels (per-cell) | — | `decompose` + board scan | ✓ | | | **b** | (per-boundary — GNN) | — | shape |
| per boundary: #compatible remaining tiles / compatible type list / rarity | yes | hist=none | no | no | no | deck scan vs boundary | ✓ | | | **v0** (aggregate) | min/sum of #compatible tiles over my open boundaries; rarity = 1/count (log-space) | hi | bag |
| awkward / easy / near-impossible / requires-specific-rotation / conflicts-with-neighbor | yes (assumption-free) | hist=none | no | no | no | deck+geometry scan | ✓ | | | **v0** (count) / **b** (per-boundary) | count of my near-impossible boundaries; per-boundary → b | med | shape |
| per feature: min tiles to completion | yes | none | yes (`city_root_open_n` proxy) | no | — | `decompose` | ✓ | | | **v0** | min/sum tiles-to-close over my open features | hi | city |
| #1-ply / 2-ply completion sequences / remaining immediate closers/extenders | yes (combinatorial) | hist=none | no | no | no | 1-ply enumerate + deck | ✓ | | | **v0** (count) / **b** (sequence) | count of my features closable in 1 ply with a remaining tile | med | bag |
| completion-scarcity score | yes (combinatorial) | hist=none | no | no | no | from counts | ✓ | | | **v0** | scarcity = need/supply per open feature → sum (log-space) | med | bag |

## Bucket 9 — Ownership / contest (per feature)

| primitive | observable? | leakage | in v2.9 leaf? | in old net? | in Step-1? | impl source | parent | child | Δ | tier | v0 aggregate form | priority | ablation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| owner / majority margin / tied? (per feature) | yes | none | yes (`_winners`) | no | farm only (Step-1) | `decompose`+tally | ✓ | | | **v0** (aggregate) / **b** (per-object margin) | count tied/contested features (city+road+farm); per-feature margin → b | hi | steal |
| stealable? / opp-can-contest-with-current-tile? / we-can-contest? | yes | none | no | no | — | tile-edge vs feature + meeple-count | ✓ | | | **v0** (count) / **b** (per-object) | count of opp features we can contest with the current tile | hi | steal |
| #meeples to take control | yes | none | no | no | — | majority margin +1 | ✓ | | | **v0** | min meeples-to-flip over contestable opp features | med | steal |
| value controlled per player | yes | none | yes (`_final_scores`) | no | — | `decompose` | ✓ | | | **v0** | controlled_value_self/opp | hi | steal |
| ownership swing if move played (full unowned↔us↔contested↔opp matrix + margin Δ) | yes | none | no | no | — | child vs parent owner map | | ✓ | ✓ | **v0** (Δ counts) / **b** (full matrix) | d_n_contested, +counts of each transition; full 4×4 matrix → b | hi | action |

## Bucket 10 — Action-delta (per legal action)

> The MLP's natural home — every row is a candidate child, so these are first-class. Mostly CL-034 Tier-2.

| primitive | observable? | leakage | in v2.9 leaf? | in old net? | in Step-1? | impl source | parent | child | Δ | tier | v0 aggregate form | priority | ablation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| immediate score delta | yes | none | derivable | no | — | child−parent scores | | ✓ | ✓ | **v0** | imm_score_delta_self — CL-034 T2 | **hi** | action |
| PROJECTED final score delta | **no** (PROJECTION) | none | leaf IS this | no | — | — | | | ✓ | **not-input (a)** | feed leaf_q as a FEATURE (CL-034 does — see below), not as the projection target | — | excl |
| meeple delta | yes | none | no | no | — | child−parent meeples | | ✓ | ✓ | **v0** | net_meeple_delta_self — CL-034 | hi | action |
| ownership delta | yes | none | no | no | — | owner map Δ | | ✓ | ✓ | **v0** | d_n_contested — CL-034 | hi | action |
| city/road completion delta | yes | none | no | no | — | finished Δ | | ✓ | ✓ | **v0** | feature_completed_by_move, completed_value_self/opp — CL-034 | hi | action |
| farm score / potential delta | yes (score) / no (potential) | none | partial | no | — | farm-adj Δ | | ✓ | ✓ | **v0** (score) / **not-input (a)** (potential) | d_farm_finished_cities | med | action |
| open-edge delta | yes | none | no | no | — | open_n Δ | | ✓ | ✓ | **v0** | d_total_city_open_edges, d_n_open_cities — CL-034 | hi | action |
| dead-feature delta | yes | none | no | no | — | dead-count Δ | | ✓ | ✓ | **v0** | d_n_dead_features | lo | action |
| opponent score / farm / meeple delta | yes | none | no | no | — | opp-side Δ | | ✓ | ✓ | **v0** | imm_score_delta_opp — CL-034 + opp meeple/farm Δ | **hi** | opp |
| #features modified / completed / #farms affected | yes | none | no | no | — | touched-component count | | ✓ | ✓ | **v0** | n_features_touched_by_move | med | action |
| consumes-rare-tile? | yes | hist=none | no | no | no | bag count of placed type | | ✓ | ✓ | **v0** | placed_tile_remaining_count (log-space) | med | bag |
| preserves/reduces future flexibility / increases frontier / creates forced response | **no** (PROJECTION) | none | no | no | — | — | | | | **not-input (a)** | feed frontier-cell count (bucket 19) + open-edge Δ; head learns it | — | excl |

## Bucket 11 — Opponent interaction (per move)

> All mirror-of-self deltas applied to the opponent. v0 = the opp-POV aggregates; per-touched-feature detail = b.

| primitive | observable? | leakage | in v2.9 leaf? | in old net? | in Step-1? | impl source | parent | child | Δ | tier | v0 aggregate form | priority | ablation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gives opp points? / helps opp complete? / feeds opp farm? / returns opp meeple? | yes | none | no | no | — | opp-side Δ | | ✓ | ✓ | **v0** | imm_score_delta_opp, d_opp_completed, d_opp_farm, d_opp_meeple_freed | **hi** | opp |
| blocks opp feature? / denies opp farm access? | yes | none | no | no | — | opp open_n Δ, opp-touched | | ✓ | ✓ | **v0** | opp_feature_touched (CL-034) + d_opp_open_edges (negative = block) | hi | block |
| creates opp steal? / forces opp to defend? | yes / **no** (forces=projection) | none | no | no | — | contest-path Δ | | ✓ | ✓ | **v0** (steal-route count) / **not-input (a)** (forces) | d_opp_contestable_of_ours | med | block |
| reduces opp legal meeple use? / increases opp dead-meeple risk? | yes / **no** (risk) | none | no | no | — | opp legal Δ | | ✓ | ✓ | **v0** (legal Δ) / **not-input (a)** (risk) | d_opp_legal_meeple_options | lo | opp |
| per-touched-feature: benefits us/them/both, denies us/them | yes | none | no | no | — | per-feature Δ | | ✓ | ✓ | **b** | (per-object — GNN) | — | block |

## Bucket 12 — Tempo / initiative

| primitive | observable? | leakage | in v2.9 leaf? | in old net? | in Step-1? | impl source | parent | child | Δ | tier | v0 aggregate form | priority | ablation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| creates immediate scoring/completion threat? | yes | none | no | no | — | child completable-now count | | ✓ | ✓ | **v0** | n_my_close_now_after_move | med | tempo |
| requires opp response? / opp has direct reply? | **no** (PROJECTION) | none | no | no | — | — | | | | **not-input (a)** | head infers from threat counts + open-edges | — | excl |
| #opp replies that punish / complete / steal / contest | **no** (search-derived projection) | none | no | no | — | needs 1-ply opp search | | | | **not-input (a)/(b)** | (search territory; not a static atom) | — | excl |
| defers vs cashes points | yes | none | derivable | no | — | imm vs leaf delta | | ✓ | ✓ | **v0** | imm_score_delta vs leaf_q delta gap | lo | tempo |
| improves / narrows future options | **no** (PROJECTION) | none | no | no | — | — | | | | **not-input (a)** | feed n_legal Δ + frontier; head learns | — | excl |
| cheap proxy: #high-value opp moves after ours / opp best h200/h800 value | yes but **search-derived** | none | no | no | — | shallow search | | | | **not-input (b)** | TAG search-derived → scheduler territory, not a value input | — | excl |

## Bucket 13 — Blocking / denial

| primitive | observable? | leakage | in v2.9 leaf? | in old net? | in Step-1? | impl source | parent | child | Δ | tier | v0 aggregate form | priority | ablation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| opp feature open-edges / compatible-completers / farm-access-points / steal-paths / high-value-placements / deadness — before AND after | yes (counts) / **b** (paths) | hist=none | partial (open_n) | no | — | parent & child `decompose` + deck | ✓ | ✓ | ✓ | **v0** (Δ counts) / **b** (paths) | d_opp_open_edges, d_opp_dead_features, d_opp_completer_supply | hi | block |
| flags: blocks city/road/farm-connection/monastery-fill/meeple-return/farm-contest | yes | none | no | no | — | child vs parent | | ✓ | ✓ | **v0** | opp_feature_touched + per-kind block flags (city/road/farm) | hi | block |

## Bucket 14 — Feature-stealing (per move)

| primitive | observable? | leakage | in v2.9 leaf? | in old net? | in Step-1? | impl source | parent | child | Δ | tier | v0 aggregate form | priority | ablation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| adds our meeple to opp feature? / connects our→opp feature? | yes | none | no | no | — | child owner map vs parent | | ✓ | ✓ | **v0** | n_opp_features_we_entered_this_move | hi | steal |
| equalizes / overtakes meeple count? | yes | none | no | no | — | majority margin Δ | | ✓ | ✓ | **v0** | d_n_features_we_now_tie_or_lead (ownership-transition Δ) | hi | steal |
| creates future steal route? / closes feature after stealing? | yes (route exists) / **b** (route detail) | none | no | no | — | contest reachability | | ✓ | ✓ | **v0** (count) / **b** | n_new_steal_routes; route geometry → b | med | steal |
| points stolen now / swung at completion | yes (now) / no (swung) | none | partial | no | — | owner-value Δ | | ✓ | ✓ | **v0** (now) / **not-input (a)** (swung) | controlled_value swing on touched feature | hi | steal |
| meeple cost / tile rarity required / opp counter-steal ability | yes (cost,rarity) / no (counter) | hist=none | no | no | — | move + deck | | ✓ | ✓ | **v0** | meeple_cost_of_steal, required_tile_rarity (log-space) | med | steal |

## Bucket 15 — Endgame

| primitive | observable? | leakage | in v2.9 leaf? | in old net? | in Step-1? | impl source | parent | child | Δ | tier | v0 aggregate form | priority | ablation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tiles remaining | yes | none | partial | `features.py` ch5 | — | `len(deck)` | ✓ | | | **v0** | (= bucket-1 tiles-remaining) | hi | global |
| uncompleted city/road points / monastery remaining points | yes | none | yes (partial-credit base) | no | — | `decompose` | ✓ | | | **v0** | sum of my open-feature partial value (score-if-end-now) | hi | endgame |
| farm final-score estimate | yes (=3×finished now) / **no** (with growth) | none | yes (3×finished) | no | — | `decompose` | ✓ | | | **v0** (now) / **not-input (a)** (growth projection) | farm_score_now_self/opp | hi | farm |
| dead meeples / free meeples / features unlikely to complete | yes (dead/free) / **no** (unlikely) | hist=none | partial | no | — | `decompose` + deck | ✓ | | | **v0** (dead/free) / **not-input (a)** (unlikely) | n_dead_meeples_self/opp; "unlikely" → feed completer-supply | med | endgame |
| features worth abandoning | **no** (PROJECTION) | none | no | no | — | — | | | | **not-input (a)** | feed dead/supply atoms; head decides | — | excl |
| Move-Δ: endgame score swing if game ended soon / improves final farm? / rescues dead meeple? / abandons completion but gains final points? | yes (score-now Δ) / no (others) | none | partial | no | — | child score-now Δ | | ✓ | ✓ | **v0** (score-now Δ) / **not-input (a)** | d_score_if_end_now_self/opp; "rescues dead meeple" → d_n_dead_meeples | med | action |

## Bucket 16 — Search diagnostics — **NOT-INPUT (b)** wholesale

> CL-035/CL-036: a one-line heuristic (`low_top2gap`) beats an ML model on the post-search residual, and it doesn't convert to game strength. These are scheduler/reranker territory, NOT value-head inputs.

| primitive | observable? | leakage | tier | note |
|---|---|---|---|---|
| h200 top move / Q, 2nd Q, top2-gap | yes (search-derived) | none | **not-input (b)** | the `low_top2gap` escalation signal — scheduler use only |
| visit count / share / policy prior / entropy / #explored children | yes | none | **not-input (b)** | search internals; not a static observation |
| h200/h800 disagreement / leaf-vs-backed-up gap | yes | none | **not-input (b)** | the CL-035 residual target's diagnostics |

## Bucket 17 — Teacher / label — **NOT-INPUT (c)** (these are the WARMSTART TARGET)

| primitive | tier | note |
|---|---|---|
| static-leaf value (v2.9 `leaf_q`) | **v0 as a FEATURE** (exception) | CL-034 feeds `T1_leaf_q_tanh` / `T1_leaf_total_div15` as INPUTS — the residual-on-leaf design; the net inherits the leaf's ranking by construction and corrects it. NOT the same as feeding a projected final score. |
| h200 / h800 / h3200 / h6400 / h12800 / exact value | **not-input (c)** | the LABEL. Step-2 warmstarts the value on **h6400_v2.9 deep-search targets** (the Step-1 oracle_q), not the static leaf. |
| regret vs teacher / teacher top move / top-k / Q-gap | **not-input (c)** | label-side / selection metadata, not a deployable input |

## Bucket 18 — Symmetry / normalization — **MANDATORY INFRA (not a feature choice)**

| requirement | status | impl precedent |
|---|---|---|
| all values current-player-POV | **hard requirement** | `features.py`, `board_repr.canonical_swap`, CL-034 `root_player` |
| margin / scores current-POV | hard | `features.py` ch4 |
| ownership encoded us/them, NOT p0/p1 | hard | `step1_planes._farm_component_owners`, CL-034 self/opp |
| meeple / farm counts us/them | hard | CL-034 `_struct_summary` self/opp |
| phase normalized; tile counts normalized by initial | hard | `features.py` norms, `step1_planes` `/_BAG_MAX` |

> This bucket is asserted once over the whole substrate. No row here is "optional." It is the reason the v0 list says "self/opp", never "p0/p1".

## Bucket 19 — Board geometry

| primitive | observable? | leakage | in v2.9 leaf? | in old net? | in Step-1? | impl source | parent | child | Δ | tier | v0 aggregate form | priority | ablation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| frontier cells / empty neighbor cells / board bounding box | yes | none | partial (empty-adj in `city_root_open_n`) | implicit (window) | — | board scan / `state.open_positions` | ✓ | | | **v0** (count) / **b** (map) | n_frontier_cells, board_extent; per-cell map → b | med | geo |
| feature distance-to-frontier / feature openness | yes | none | partial | no | — | BFS | ✓ | | | **b** | (per-object reachability) | — | geo |
| #adjacent legal placements / local congestion / isolated-feature flag | yes | none | no | no | — | board scan | ✓ | | | **v0** (count) / **b** (per-cell) | n_legal_placements (bucket 1), congestion_mean; per-feature → b | lo | geo |

## Bucket 20 — Risk / uncertainty — **NOT-INPUT (a)** wholesale (all projections)

> Every item here is a *number summarizing future play* — the value head's job. Feed the underlying combinatorial atoms (open-edge counts, completer-supply, contested-counts) instead.

| primitive | observable? | tier | feed-instead |
|---|---|---|---|
| completion-chance proxy (as a number) | no (projection) | **not-input (a)** | completer-supply count + open_n (buckets 2, 8) |
| deadness proxy | borderline | **not-input (a)** as a *proxy*; the **hard dead flag** (no closer remains) is **v0** (bucket 2) | the exact dead-flag is v0; the soft proxy is not |
| opp-contest-chance proxy | no | **not-input (a)** | contestable-count + meeples-to-flip (bucket 9) |
| farm volatility / score-swing volatility / feature-value variance | no | **not-input (a)** | incomplete-cities-touching + open-edges (bucket 6) |
| meeple-lockup risk | no | **not-input (a)** | n_meeples_locked + completer-supply |

---

## (1) THE v0 SHORTLIST — the ~40–60 aggregates we feed the pilot MLP (deduped)

Grounded in the **CL-034 proven 50-scalar set** (which already beat the v2.9 leaf offline) and **extended with the deck-composition / completability axis** Step 1 sighted (bag is the cleanest "net saw something the leaf can't"). Total below: **~58 scalars**.

**A. Global context (9)** — CL-034 Group F, verbatim
1. phase one-hot ×5 (opening / midgame / late_mid / pre_endgame / endgame)
2. tiles_remaining (k_remaining, norm /10)
3. score_margin_signed (norm /10)
4. meeples_free_self
5. meeples_free_opp

**B. Leaf-component context (8)** — CL-034 Tier-1, leaf already computes (`decompose_v29`); feeding leaf_q is the residual-on-leaf design (NOT a projection)
6. leaf_q (tanh) — the v2.9 leaf value as a feature
7. leaf_total (/15)
8. base (/15)
9. closure_self (/8)
10. closure_opp (/8)
11. meeple_contribution (flat + curve)
12. pretransform_total (/15)
13. terminal_flag

**C. Per-action move semantics + deltas (13)** — CL-034 Tier-2 action + leaf-component deltas (bucket 10/11)
14. meeple_placed flag
15–18. mtype one-hot: city / road / farm / monastery
19. net_meeple_delta_self
20. imm_score_delta_self
21. imm_score_delta_opp
22. d_base
23. d_closure_self
24. d_closure_opp
25. d_meeple
26. d_pretransform

**D. Child structural ownership/open-edge aggregates (12)** — CL-034 Tier-2 child struct (buckets 4/5/6/9)
27. n_open_cities
28. n_open_roads
29. n_open_farms
30. total_city_open_edges
31. n_cities_self
32. n_cities_opp
33. n_cities_contested
34. n_meeples_locked_self
35. n_meeples_locked_opp
36. max_open_city_value_self (/8)
37. n_farms_self
38. n_farms_contested

**E. Parent→child structural deltas (8)** — CL-034 Tier-2 deltas (buckets 4/9/11/13)
39. d_total_city_open_edges
40. d_n_open_cities
41. d_meeples_locked_self
42. d_n_contested
43. opp_feature_touched (the block/steal flag)
44. feature_completed_by_move
45. completed_value_self (/8)
46. completed_value_opp (/8)

**F. NEW — deck-composition / completability axis (the Step-1 sighted information, ~12)** — bucket 2/8, all log-space (see §3)
47. bag histogram digest: 32-type vector is the *full* signal; for the v0 MLP feed it directly **(32 scalars)** OR a reduced digest. **Pilot decision: feed the full 32-vec** (Step-1 verbatim, proven to recover ~the whole Gate-A effect) — this is the single biggest "new vs leaf" lever.
48. n_completer_copies for my open cities (sum, log-space)
49. n_completer_copies for my open cities (max, log-space)
50. n_completer_copies for opp open cities (sum, log-space)
51. n_dead_features_self (no remaining closer)
52. n_dead_features_opp
53. P(≥1 completer drawn) over my closable-soon features (sum, log-space)
54. placed_tile_remaining_count for this move (consumes-rare-tile, log-space)

> **Width note:** if the full 32-vec bag is included, total ≈ **50 + 32 = ~82 inputs** (still tiny for an MLP). If a reduced bag digest (~8 shape-class counts) is used instead, total ≈ **58**. The pilot should include the **full 32-vec** — it is cheap and is the load-bearing new axis; trimming is a later efficiency question, not a v0 risk.

Everything in C/E is computed as **child − parent** from one `decompose` pair per child (the CL-034 cost model: one parent decompose reused across siblings + one child decompose + one leaf eval per child).

## (2) WHAT'S GENUINELY NEW vs the v2.9 leaf (the highest-value adds)

The leaf already flood-fills cities/roads/farms/monasteries and scores them (so buckets 4/5/6/7 *current-board* facts are "refining a known axis"). The net adds value where the leaf is **structurally blind** or where it **only sees the static board, not the move or the future supply**. Top ~8:

1. **Bag / deck-composition histogram (bucket 2).** The single cleanest add — the v2.7/v2.9 leaf scores the **current board only** and **cannot see what remains to draw**. Step-1 bag-only alone recovered ~the whole Gate-A effect (+19.7%). **#1 priority.**
2. **Per-feature completer-supply counts (buckets 2/8).** #remaining tile-copies/types that can close each of my/opp open features — exact combinatorial facts the leaf's permissive `_deck_city_supply` only crudely approximates and never per-feature.
3. **Hard dead/no-closer flags (bucket 2).** "This open feature can never close" as an exact flag (leaf only handles the D16 board-edge special case). Distinguishes a live partial-credit feature from a dead one.
4. **Per-action structural deltas (buckets 10/11).** The leaf evaluates a *static* position; it has no notion of "this *move* completes / contests / blocks / opens-an-edge." `feature_completed_by_move`, `d_total_city_open_edges`, `opp_feature_touched` are move-semantics the leaf cannot express — these drove CL-034's −41%.
5. **Contest / steal aggregates (buckets 9/14).** Counts of contestable/stealable opp features, meeples-to-flip, ownership-transition counts — the leaf scores final ownership but exposes no "who can take what" axis.
6. **Opponent-delta block aggregates (buckets 11/13).** `imm_score_delta_opp`, `d_opp_open_edges` (negative = block) — the leaf's opp term is a symmetric score, not a per-move denial signal.
7. **Contested-field count & farm-control balance over the live board (bucket 6/9).** Already a Step-E scalar (`features.farm_control_scalars`) and a Step-1 plane; gives the net farm-war structure the conv couldn't derive.
8. **Hypergeometric draw-odds / completion-scarcity (buckets 2/8).** P(≥1 completer drawn) and need/supply scarcity — assumption-free probabilities (NOT future-play projections) the leaf has no concept of.

> The unifying theme: the leaf is a **static board scorer**; the net's edge is **(a) the deck**, **(b) the move**, and **(c) contest/denial structure**. The per-object *granularity* of buckets 4–9 (and geometry/reachability, bucket 19) is the **b-tier** escalation if v0 plateaus.

## (3) Exact-deck-calculator features go in LOG-SPACE

All bucket-2/8 **deck-match / completer-count / draw-odds** features are heavy-tailed and multiplicatively-scaled (a feature needing 1 of 8 copies vs 1 of 1 copy is a large ratio, not a large difference). **Feed them as `log1p(count)` / log-odds**, not raw counts, so the MLP sees ratios linearly and isn't dominated by the high-count tiles. The 32-type bag *fraction* histogram (Step-1) is already in [0,1] and stays linear; the **derived per-feature supply counts and scarcity ratios go in log-space.**

## (3b) The combinatorial "calculator" — PRE-COMPUTED vs LEARNED (LOCKED 2026-06-30)

The deck-odds "calculator" lives **inside group F**, fed two ways so the pilot answers calculator-vs-learn empirically:

- **Calculator's ANSWER (pre-computed):** F#53 `P(≥1 completer drawn)` — exact hypergeometric draw-odds from the known remaining-tile multiset + tiles-left + the feature's open-edge requirement. A CPU precompute, **not a runtime module** (the deck is tiny and fully known, so a live differentiable calculator would be overkill).
- **Raw INPUTS (net combines them itself):** F#48–50/#54 completer-copy counts (log-space).
- **"Method not the answer" = the §3 log-space encoding, NOT a Bayes module.** Hypergeometric/Bayesian combination is *products of ratios*; in log-space products become sums, which a single linear layer computes natively. We hand the net the coordinate system where the math is linear, not the formula.

**Leakage / projection line (doctrine, hard):** only **DECK-ONLY** combinatorics are calculator-safe — they depend solely on the remaining-tile multiset + board geometry, never on a model of future play. `P(≥1 completer remains/drawn)` is **IN**; `P(I actually COMPLETE this)` / expected-final-score is **OUT** (play-dependent projection → the value head's job, bucket 20 not-input).

**Ablation:** `bag_calc` (the pre-computed F#53) vs `bag_raw` (the F#48–50 counts) is a pilot ablation bucket — if the net matches without #53, it learned the calculator from the counts; if #53 helps, the explicit calculator earns its place. Additional deck-only odds (expected drawable copies, `P(meeple returns)`) are a cheap (b)-tier add **only if** the ablation says #53 pays.

---

## Tier tally

| tier | approx primitive count (across the 20 buckets) |
|---|---|
| **v0** (in the fixed-scalar MLP now; deduped to ~58 aggregates) | ~62 candidate primitives → **~58 deduped v0 scalars** |
| **b** (needs the per-object set/GNN) | ~22 (per-object city/road/farm/monastery tables, geometry/reachability, contest-paths, merge-routes, full transition matrices) |
| **not-input (a)** projections (value-head's job) | ~20 (volatility, potential scores, completion-chance, forces-response, abandonment, all of bucket 20) |
| **not-input (b)** search diagnostics | ~7 (all of bucket 16 + tempo's search-proxy) |
| **not-input (c)** teacher/labels | ~6 (bucket 17, minus leaf_q which is a v0 feature) |
| **mandatory infra** (symmetry/normalization, bucket 18) | 5 requirements (not features) |

## Provenance / cross-reference sources read

- v2.9 leaf decomposition: [`src/carcassonne_ai/flat_leaf.py`](../src/carcassonne_ai/flat_leaf.py) (`decompose`, `city_root_*`/`road_root_*`/`farm_*_root`, `_final_scores`), [`src/carcassonne_ai/virtual_score_v2.py`](../src/carcassonne_ai/virtual_score_v2.py) (closure bonus, caps, meeple curve), [`src/carcassonne_ai/leaf_v29.py`](../src/carcassonne_ai/leaf_v29.py) (`decompose_v29` → base/closure_self/closure_opp/meeple/pretransform).
- Old net representation: [`src/carcassonne_ai/board_repr.py`](../src/carcassonne_ai/board_repr.py) (78-channel `encode_board`), [`src/carcassonne_ai/features.py`](../src/carcassonne_ai/features.py) (10 scalars + 2 farm-control scalars).
- Step-1 planes (Gate-A PASS): [`scripts/feature_planes_gate/step1_planes.py`](../scripts/feature_planes_gate/step1_planes.py) (+3 farm-connectivity planes, +32 bag histogram), verdict [../measurement/feature_planes_gate/STEP1_GATE_RESULTS.md](../measurement/feature_planes_gate/STEP1_GATE_RESULTS.md).
- v0 substrate precedent (the proven 50 scalars): [`scripts/feature_graph/build_feat_dataset.py`](../scripts/feature_graph/build_feat_dataset.py) (CL-034 `FEAT_NAMES`), DECISIONS 2026-06-29 (CL-034 −41% offline; CL-036 GNN inert; CL-035 search washout).
