# v2.8 variant registry (Phase 3)

> Every v2.8 variant is an **opt-in `LeafConfig` override** on the frozen v2.7 base. v2.7 is
> bit-identical when all v2.8 fields are OFF (proven — see Parity below). Single source of truth for
> the configs: [V28_VARIANT_CONFIGS.json](V28_VARIANT_CONFIGS.json) +
> [scripts/heuristic_v28/v28_configs.py](../../scripts/heuristic_v28/v28_configs.py).

## Code changes (this phase)

| File | change | v2.7 impact |
|---|---|---|
| [src/carcassonne_ai/virtual_score_v2.py](../../src/carcassonne_ai/virtual_score_v2.py) | +3 `LeafConfig` fields (`v28_farm_majority`, `v28_meeple_k`, `v28_meeple_recovery_t0`), env reads, `_v28_active()`, `_field_owner_counts()`, farm-majority gate in `_closure_anticipation_bonus`, recovery-scaled meeple term in `virtual_score_v2`, extended flat fall-through guard | **none** — all fields default OFF; DEFAULT_CONFIG unchanged; `_v28_active(DEFAULT_CONFIG)==False` |
| [src/carcassonne_ai/mcts.py](../../src/carcassonne_ai/mcts.py) | `HeuristicMCTS(..., leaf_cfg=None)` threaded into the `virtual_score_v2(...)` call | **none** — `leaf_cfg=None` → DEFAULT_CONFIG, bit-identical |
| [tests/test_v28_variants.py](../../tests/test_v28_variants.py) | new — parity + effect + threading tests | — |

## Variants

| name | patch family | overrides (on v2.7 base) | new code? | path |
|---|---|---|---|---|
| `v27_baseline` | — (frozen reference) | — | no | flat (bit-exact) |
| `v28_farm` | farm_final_value_v1 | `v28_farm_majority=True` | **yes** | object (forced) |
| `v28_meeple` | meeple_economy_v1 | `v28_meeple_k=2.0, v28_meeple_recovery_t0=72` | **yes** | object (forced) |
| `v28_completion` | completion_timing_v1 | `closure_continuous_slack=3.0` | no (reuse) | object (forced) |
| `v28_denial` | opponent_denial_v1 | `opp_bonus_cap=24.0` | no (reuse) | object/flat |

Grids for tuning (Phase 5): `v28_meeple` k∈{1,2,3}×t0∈{0,72}; `v28_completion` slack∈{2,3,4};
`v28_denial` opp_cap∈{18,24}. `v28_farm` is parameter-free.

## How a variant is instantiated (opt-in, no production change)

```python
from scripts.heuristic_v28.v28_configs import set_prod_env, build_variants
set_prod_env()                      # CAP=12, DROP_THREE_OPEN, USE_FLAT_LEAF — the v2.7 base
variants = build_variants()         # {name: LeafConfig}
cfg = variants["v28_farm"]
# static leaf:        virtual_score_v2(state, player, cfg)
# heuristic search:   HeuristicMCTS(game, simulations=N, heur_leaf="v2_7", leaf_cfg=cfg)
# neural value (iter8 leaf swap, opt-in MEASUREMENT wrapper only):
#                     make_v25_value_wrapper(base_eval, cfg=cfg)
```
Production launchers are untouched: they keep reading env knobs with every v2.8 field absent (OFF).

## Parity status — PROVEN

`pytest tests/test_v28_variants.py tests/test_virtual_score_v2.py tests/test_flat_leaf_edge_cases.py
tests/test_virtual_score.py` → **all pass** (and the broader mcts/leaf/eval subset, 184 tests, pass).

- `test_default_config_has_no_v28_effect` — DEFAULT_CONFIG (production) carries every v2.8 field OFF.
- `test_v28_off_is_bit_identical_to_v27[object|flat]` — explicit-OFF cfg and `None` == DEFAULT_CONFIG
  byte-for-byte on both code paths, across 24-seed mid-game corpus × both players.
- Each toggle proven to change evaluation: `v28_farm` (uncapped bonus), `v28_meeple` (flat + recovery
  scaling), `v28_denial` (asymmetric cap), `v28_completion` (slack reduces bonus). `v28_*` invariants:
  farm only reduces growth credit, completion only reduces closure bonus.
- `test_heuristic_mcts_leaf_cfg_none_matches_default` — search with `leaf_cfg=None` reproduces the
  default action; `test_heuristic_mcts_v28_leaf_cfg_can_change_action` — a v2.8 cfg changes the action.

## Known interaction (carry to Phase 4/5)

**`v28_farm`'s effect is frequently cap-masked.** `bonus_cap=12` saturates in mid-late game, so removing
a single ≤3 farm-growth contribution often does not move the rounded `virtual_score_v2` int (the change
is visible in the uncapped bonus, 17/920 mid-game states; the capped int moved 34/920 under a fixed
seed). This means `v28_farm` may show little static-selector movement unless the cap is also relaxed —
a hypothesis to test, not a bug.

---
*Phase 3 complete. Next: Phase 4 — root-action audit of each variant vs the existing references.*
