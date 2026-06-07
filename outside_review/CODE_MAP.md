# CODE_MAP — where every important component lives

All paths are relative to the repository root (`/home/doctor/projects/carcassone`).
Line numbers were accurate at commit **`fd9952e`** (branch `stage-b-wiring`, 2026-06-07);
treat them as anchors, not guarantees — grep the symbol if a line has drifted.

This map is **descriptive**. Risk flags (⚠) point to `OUTSIDE_REVIEW.md §11` and
`KNOWN_ANOMALIES.md`.

---

## 1. Engine (vendored, patched)

| Path | Role |
|---|---|
| `engine/wingedsheep/carcassonne/` | vendored fork of [wingedsheep/carcassonne](https://github.com/wingedsheep/carcassonne) (MIT, Oct 2021) |
| `engine/.../carcassonne_game_state.py` | game state; deck shuffle uses the **global** `random.shuffle` (`:129`,`:147`) → deck is a deterministic function of the process RNG seed |
| `engine/.../utils/points_collector.py` | scoring. `count_farm_points` (`:284-299`) — the **C1 farm double-count** bug site (fixed by frozenset dedup) |
| `engine/.../utils/city_util.py`, `farm_util.py` | `find_cities`, `FarmUtil.find_farm` (flood-fill farm regions). `find_farm` was start-dependent until the 2026-05-29 `opposite_farmer_side` involution fix |
| `engine/.../objects/city.py` | `City` — was missing `__eq__`/`__hash__` (root of C1); now patched |

Patches (see `CLAUDE.md` "Engine notes" + `DECISIONS.md`): tied-feature scoring,
numpy-2 compat, `open_positions` adjacency tracking, `apply_action_inplace`, lazy tkinter,
verbose-gated prints, farmer-adjacency involution, River support (now off by default).

---

## 2. Our package — `src/carcassonne_ai/`

### State / representation
| File | Key symbols | Notes |
|---|---|---|
| `game_wrapper.py` | `Game`, `get_canonical_form` (`:296-312`), `get_game_ended` (`:273-292`), `get_next_state`, `get_valid_moves` | `SCORE_NORM_SCALE = 15.0` (`:53`); tie → ±1e-6 antisymmetric (`:286-291`); base deck default `tile_sets=(BASE,)`; `WindowOverflowError` surfaced at `:435` |
| `board_repr.py` | `encode_board` (`:253-349`), `rotate_board_repr_90` (`:465`), `canonical_swap` (`:352`) | **78 input planes**; farmers = 4 corner bits (`:296-303`); ⚠ no farm-connectivity / no bag / no open-feature plane |
| `features.py` | `encode_scalars` (`:104-137`), `farm_control_scalars` (`:44-101`) | **10 scalars** in prod (farm scalars OFF, `include_farm_scalars=False`); ⚠ idx9 ≡ 1−idx5 exactly |
| `action_space.py` | `action_size` (`:71`, **2511**), `encode/decode` (`:208-281`), `rotate_action` (`:150`) | phase-aware; ⚠ no equivalent-action coalescing |
| `aux_targets.py` | `extract_terminal_ownership` (`:63-181`), `ownership_planes` (`:193-223`) | **training-only** target, never an input; OFF in all 3 global-best ckpts |

### Network
| File | Key symbols | Notes |
|---|---|---|
| `network.py` | `CarcassonneNet` (`:56`), `ResBlock` (`:38`), `forward` (`:144`), `forward_train` (`:164`) | 6 blocks × 96 filters, **7,411,887 params** (docstring "~4M" is stale); policy 2511-dim, value tanh; aux ownership head training-only |

### Search
| File | Key symbols | Notes |
|---|---|---|
| `mcts.py` | `MCTS` (`:68`), `HeuristicMCTS` (`:284`), `NeuralMCTS` (`:357`) | base UCT `c=3.0` (`:35`); PUCT `c_puct=1.5` (`:311`); ⚠ `HeuristicMCTS._rollout` uses **v1** `virtual_score` (`:298-304`), not v2.7 |
| | `_select_child_puct` (`:878`), backup (`:1022-1033`,`:1072-1078`) | negamax sign convention; FPU `node.Q − reduction` (`:893-895`) |
| | `_link_child` (`:750`), `_deduped_children` (`:498`) | **C2 transposition alias fix** (NeuralMCTS only; base MCTS selection unchanged) |
| | `root_value` (`:578`), `interior_sibling_groups` (`:647`) | search-value targets; clairvoyant (`:18-21`); `fair_chance` single-determinization (`:442-461`, ⚠ unsound vs transposition key) |
| `evaluators.py` | `make_v25_value_wrapper` (`:127-195`) | leaf = `tanh(virtual_score_v2/15)`; residual (`:186-190`) and blend (`:191-192`) entry |

### Leaf heuristic
| File | Key symbols | Notes |
|---|---|---|
| `virtual_score.py` | `virtual_score` | **v1** leaf = engine end-of-game scoring of the current board (no bonuses) |
| `virtual_score_v2.py` | `virtual_score_v2` (`:385-452`), `_closure_anticipation_bonus` (`:261-376`), `LeafConfig` (`:90`), `_config_from_env` (`:99-128`) | **v2.7** leaf = v1 + capped closure bonuses; env knobs `CARCASSONNE_V25_*` read once at import |
| `rule_based_player.py` | `RuleBasedPlayer` (`:49`) | **Tier-1** baseline: 1-ply v1 argmax |

### Self-play / training / data
| File | Key symbols | Notes |
|---|---|---|
| `selfplay.py` | `play_one_selfplay_game` (`:~150`), value-target dispatch (`:334-358`,`:448-467`) | learner-vs-anchor (`:204-225`); temp schedule (`:322`); ⚠ value-target = `score_diff` (tanh/15) in prod |
| `warmstart.py` | `GameDataset` (`:48`), streaming loader (`:577-603`), `augment_with_rotations` (`:176`) | **8-array .npz schema**; atomic save (`:91-107`) |
| `claim.py` | `_try_claim` (`:55-126`) | O_EXCL work-stealing; ⚠ stale-recovery not exactly-once (D15) |
| `eval_server.py`, `eval_server_pool.py`, `remote_eval_bridge.py`, `remote_evaluators.py`, `remote_socket_handles.py` | GPU inference-server "orchestrator" | orch-OFF in production (CPU v2.7 leaf) |
| `elo.py` | `elo_delta_from_winrate` (`:22-44`) | 400·log10(score/(1−score)), ±800 clamp, draw=½ |
| `run_manifest.py` | `write_manifest` (`:64-88`) | ⚠ records ckpt **path** not content hash; `_LEAF_ENV_KEYS` omits residual_scale |

### Scripts (entry points)
| File | Role |
|---|---|
| `scripts/run_pathb_cluster_loop.sh` | **outer loop**: gen→train→gate→keep-best (⚠ tracked snapshot ≠ live `~/` copy; header `:2-8`) |
| `scripts/run_selfplay_iter.py` | one self-play iteration (workers, claim, orch) |
| `scripts/train_iter.py` | one train step; loss assembly (`:574-580`); replay window (`:198-210`) |
| `scripts/eval_net_vs_heuristic.py` | the **measurement ladder** rung (NeuralMCTS vs HeuristicMCTS); σ at `:194-200` |
| `scripts/eval_iter_head_to_head.py` | net-vs-net; ⚠ `_effective_blend` drops residual_scale (`:238-247`) |
| `scripts/ladder_asymmetric.py` | the **odometer** (net@200 vs heur@{50,200,800,3200}); crossover (`:44-62`) |
| `scripts/train_warmstart.py` | the 100K-position cold-start trainer |
| `scripts/diag_clairvoyance.py` | the only caller of `fair_chance=True` |

---

## 3. Tracking docs (truth sources)
| File | Answers |
|---|---|
| `STATUS.md` | live state, current verdict |
| `DECISIONS.md` (~310 KB) | every dated decision + why (latest dated entry 2026-06-03; the 06-04→07 arc is in STATUS + git log) |
| `experiments/results.csv` | **authoritative experiment numbers** |
| `EXPERIMENTS.md` | ablation roadmap narrative |
| `BACKLOG.md` | deferred/killed ideas |
| `REVIEW_LOG.md` | code-review F-items (fixed) and D-items (deferred) |
| `docs/research/foundational_audit_2026-06-02.md` + `_round2_` | the two 6-agent audits (F-* and G-* findings) |
| `docs/CORRECTION_PLAN_2026-06-02.md`, `docs/PHASE1_BUILD_SPEC_2026-06-02.md` | the staged-correction plan |
| `docs/VALUE_LOSS_ATTACK_2026-06-05.md` | the residual-lever plan |
| `docs/TEST_SUITE_GAP_ANALYSIS_2026-06-03.md` | test coverage gaps |
