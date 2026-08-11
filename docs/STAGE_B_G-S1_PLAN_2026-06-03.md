# G-S1 — value_blend ramp wiring (Stage-B core mechanism)

> **🕰️ STATUS: HISTORICAL — IMPLEMENTED AND THE LEVER IS DEAD (stamped 2026-08-03).** The "not
> implemented" line below is 2026-06-03 state. G-S1 *was* wired the same night
> ([STAGE_B_LAUNCH_READINESS.md](STAGE_B_LAUNCH_READINESS.md)), Stage B ran, and the verdict was **no-go —
> blending the learned value into the leaf DEGRADES search**
> ([PHASE1_BUILD_SPEC_2026-06-02.md](PHASE1_BUILD_SPEC_2026-06-02.md) outcome addendum;
> [CORRECTION_PLAN_2026-06-02.md](CORRECTION_PLAN_2026-06-02.md)). The whole value-as-leaf route has since
> been closed on much stronger, modern ground — CL-039/CL-042 (route), CL-064 (not capacity), CL-065
> (representation-independent), CL-066 (tabula-rasa flatline), CL-073 (the mechanism: outcome prediction
> is not move discrimination). **Do not re-propose value_blend without a new premise** — see
> [LEVER_INDEX.md](LEVER_INDEX.md). *(Original plan follows.)*

**Status (as written 2026-06-03): PLAN, pending Joshua's approval. Not implemented.** Produced by a code-explorer
trace agent 2026-06-03 (overnight). G-S1 is the fix for the central failure F-B1: the
learned VALUE head is never in the search loop, so it can't beat the v2.7 heuristic. Stage B
blends the net value into the leaf, ramped over iterations.

## 1. How value_blend flows today
- `LeafConfig.value_blend` (`src/carcassonne_ai/virtual_score_v2.py:88`, default 0.0) is set in
  `_config_from_env()` (`:113`) from `CARCASSONNE_V25_VALUE_BLEND`, frozen into `DEFAULT_CONFIG`
  (`:119`) **at import time**.
- Blend math: `evaluators.py::make_v25_value_wrapper` (`:127`) captures `blend` at construction
  (`:154`); closure (`:185-187`) computes `(1-blend)*h + blend*v_nn` **only if blend>0**; else
  `v_nn` is discarded. Same in `make_v25_batch_value_wrapper` (`:192`, `:206`, `:248-250`).
- Today blend is 0.0 everywhere: `run_pathb_cluster_loop.sh:65` `ENVV` sets only
  `DROP_THREE_OPEN=1 CAP=12` — no `VALUE_BLEND` → net value never reaches the leaf.

## 2. The guard bug (3 sites, all in `scripts/run_selfplay_iter.py`)
All read the import-time constant `DEFAULT_CONFIG.value_blend` instead of a per-iter value, so a
per-iter ramp can't take effect:
- `:242-244` per-worker `use_policy_only = (leaf_eval!="nn" and DEFAULT_CONFIG.value_blend==0.0)`
- `:718` orchestrator learner-server `policy_only=(... and DEFAULT_CONFIG.value_blend==0.0)`
- `:755` orchestrator anchor-server `policy_only=(... and DEFAULT_CONFIG.value_blend==0.0)`

When `policy_only` is wrongly True, the value head is stubbed at 0.0 → blend silently computes
`(1-λ)*h + λ*0` — no crash, but the net value never contributes.

**Fix:** add `--value-blend FLOAT` (default 0.0); replace the three reads with `args.value_blend`
(or `cfg.get("value_blend",0.0)`).

## 3. Wiring plan (minimal diff, 2 files)
**`run_selfplay_iter.py`:**
- A. add `--value-blend` arg → `cfg["value_blend"]`.
- B. fix the 3 guard sites to read `args.value_blend`.
- C. in `_build_evaluators`, pass an explicit leaf cfg instead of relying on `DEFAULT_CONFIG`:
  ```python
  import dataclasses
  from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
  leaf_cfg = dataclasses.replace(DEFAULT_CONFIG, value_blend=cfg.get("value_blend", 0.0))
  ev  = make_v25_value_wrapper(ev,  cfg=leaf_cfg)
  bev = make_v25_batch_value_wrapper(bev, cfg=leaf_cfg)
  ```
  (all other LeafConfig fields still come from env: cap, drop-three-open, etc.)

**`run_pathb_cluster_loop.sh`:**
- A. add a `blend_for_iter()` schedule (values are a hyperparameter Joshua picks; structure only):
  e.g. iters 0–1 → 0.0 (warmup), then 0.1 / 0.2 / 0.4 / 0.6 / 1.0.
- B. in the iter loop, `BLEND=$(blend_for_iter "$N")` and add `--value-blend $BLEND` to the
  self-play `cmd` (`:294`). `ENVV` unchanged (CLI overrides).
- C. **keep the anchor-gate eval at blend=0.0** (omit the flag) so the gate stays comparable
  across iters; same for confirm-gate / VERIFY cmds.

**Propagation:** loop → `--value-blend $BLEND` → `cfg["value_blend"]` → `_build_evaluators`
(use_policy_only=False when blend>0 → full forward incl. value head; leaf_cfg blend captured) →
leaf computes `(1-BLEND)*h + BLEND*v_nn`. Orchestrator: `policy_only=(... and args.value_blend==0.0)`
→ server runs full-forward when blend>0 → returns real `v_nn`.

## 4. Risks + 1-iter smoke
- **FPU (G-S4):** fpu_reduction was tuned for the pure v2.7 leaf; blend>0 widens the value range →
  PUCT balance shifts. Re-sweep FPU at an intermediate blend before ramping to 1.0.
- **cap=12:** no interaction (cap affects only `h`, not `v_nn`).
- **score-diff currency:** blend assumes `h=tanh(vs/15)` and `v_nn` share scale (true for
  score_diff targets); if `score_diff_wide` (/40) is used later, match the `h` divisor.
- **anchor:** keep the anchor evaluator policy-only / blend=0.0 (it's the fixed iter_11, trained
  without blend) — consider a separate `anchor_use_policy_only`.
- **OOM:** blend>0 → orchestrator full-forward raises per-request VRAM; smoke on the 8GB xeon
  (W=18, sims=200, 1 game) and watch the Compute/CUDA engine in `nvidia-smi.exe`.
- **Smoke checks:** (1) add a one-shot `print(f"[leaf] blend={blend}")` in the wrapper; run
  `--value-blend 0.1 --games 2 --sims 20`, confirm logs show `0.1` not `0.0`; (2) run blend=1.0
  for 1 game, confirm saved `.npz` value targets differ from pure-`tanh(vs/15)`; (3) no CUDA OOM.

## Files
`virtual_score_v2.py` (LeafConfig :56, _config_from_env :91, DEFAULT_CONFIG :119) ·
`evaluators.py` (make_v25_value_wrapper :127/:154/:185-187, batch :192) ·
`run_selfplay_iter.py` (guards :242-244/:718/:755, evaluator build :276-279, import :78) ·
`run_pathb_cluster_loop.sh` (ENVV :65, cmd :294)
