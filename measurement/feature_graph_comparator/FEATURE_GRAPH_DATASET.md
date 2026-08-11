# Feature-Graph Action Comparator — DATASET (Stage 1)

**Status:** BUILT · all correctness gates PASS (exact reproduction) · 2026-06-28
**Builder:** `scripts/feature_graph/build_feat_dataset.py` · **Validator:** `scripts/feature_graph/validate_dataset.py`
**Artifact:** `measurement/feature_graph_comparator/data/rows_feat.npz` (+ `meta.json`)

## What it is

One row per **teacher-visited canonical child** of each root sibling set, with a 50-dim handcrafted
action-feature vector + the reused h6400_v2.9 teacher label and v2.9 leaf baseline. No CNN board
tensor is stored — this dataset is for the *feature/action* comparator, not the old conv net.

| | |
|---|---|
| rows (children) | **314,911** |
| features | **50** (float32) — see ordered list below |
| groups (sibling sets) | **10,067** (ALL roots, no cap) |
| games (distinct seeds) | **1,120** |
| per-root build errors | **0** |
| teacher | h6400_v2.9 (`oracle_q`, root-POV Q) |
| leaf baseline | v2.9 Bmild_cap8, config_hash `7fc930b82801cb43` (`leaf_q`) |

## Provenance & reuse

Source roots = `qprobe_A/probe.jsonl` ∩ `pool_A.jsonl` (joined on seed,ply), reconstructed via
`replay_to(seed,ply)` and checksum-verified. Child enumeration is the **bit-identical** id-deduped,
teacher-visited canonical set used by `value_resurrection/{dump_dataset,leaf_audit}.py` — so every
child here lines up 1:1 with the existing `oracle_q`/`leaf_q` labels (no relabeling, no new search).

## Built-in correctness gate — PASS (exact, not just within tolerance)

| metric | built | reference (`leaf_audit_summary.json`) |
|---|---|---|
| overall top1 (leaf vs h6400) | **0.4553** | 0.4553 |
| τ_mean (leaf vs h6400) | **0.8951** | 0.8951 |
| decisive misses (gap≥0.02 & regret≥0.02) | **1197** | 1197 |
| leaf_q vs stored `dataset_v29_h6400/rows.npz` | **200/200 groups, max_abs_diff 0.0** | bit-exact |

Ownership sanity: locked_self/opp ≤ 7 (engine cap), cities self+opp+contested ≤ 8, exactly one
`is_teacher_best` per group, all 15,745,550 feat entries finite. The exact audit reproduction +
bit-exact leaf_q prove the replay → enumerate → decompose → score spine is faithful end-to-end.

## Feature columns (50, fixed order; tier-prefixed for clean ablation)

- **Group F — context (9):** `F_phase_{opening,midgame,late_mid,pre_endgame,endgame}`,
  `F_k_remaining_div10`, `F_score_margin_signed_div10`, `F_meeples_free_self`, `F_meeples_free_opp`.
  Constant across a set; cancels in pairwise differences; used raw in listwise / as context.
- **Tier-1 — leaf-component (13):** `T1_leaf_total_div15`, `T1_leaf_q_tanh`, `T1_base_div15`,
  `T1_closure_self_div8`, `T1_closure_opp_div8`, `T1_meeple_contribution`, `T1_pretransform_div15`,
  `T1_terminal_flag`, and parent→child deltas `T1_d_{base,closure_self,closure_opp,meeple,pretransform}`.
  Tests: *can reweighting the leaf's own terms beat the leaf?*
- **Tier-2 — structural + action (28):**
  - action/move (8): `T2_meeple_placed`, `T2_mtype_{city,road,farm,monastery}`,
    `T2_net_meeple_delta_self`, `T2_imm_score_delta_{self,opp}`
  - child structure (12): `T2_n_open_{cities,roads,farms}`, `T2_total_city_open_edges`,
    `T2_n_cities_{self,opp,contested}`, `T2_n_meeples_locked_{self,opp}`,
    `T2_max_open_city_value_self_div8`, `T2_n_farms_{self,contested}`
  - structure deltas (8): `T2_d_total_city_open_edges`, `T2_d_n_open_cities`,
    `T2_d_meeples_locked_self`, `T2_d_n_contested`, `T2_opp_feature_touched`,
    `T2_feature_completed_by_move`, `T2_completed_value_{self,opp}_div8`
  Tests: *does explicit feature/action structure beat the leaf?*

## Per-row stored fields

`feat` (314911×50 f32), `oracle_q`, `leaf_q`, `group_id`, `action_id`, `game_seed`, `ply`, `phase`,
`q_gap` (=q_gap_1_2), `legal_n`, `is_teacher_best`, plus `feat_names` (`<U40`).

## Splits (consumed by `eval_lib.seed_split`)

By **distinct game_seed** (1,120 seeds), 70/15/15 → a sibling set never spans train/val/test
(no leakage). Deterministic (int-tuple hash, PYTHONHASHSEED-independent).

## Known modeling note

`T2_meeple_placed`/`mtype` and mover-relative deltas use the engine property that a TILES-phase
action does not flip `current_player` (documented in `leaf_audit.py`); the placed meeple is found by
diffing `placed_meeples[root_player]` parent→child. The bit-exact audit reproduction validates this.
