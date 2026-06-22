# RoD — Revenge of Demis · v2.8 Continuation Probe — REUSE & SCOPE (Phase 0)

**Branch:** `rod_v28_continuation_probe` (from `stage-b-wiring` @ `ccc33c2`)
**Status:** Phase 0 — scope & baseline registry. MEASUREMENT ONLY. No promotion, no `PRODUCTION.yaml` edit, no v2.7 change, no champion move.
**Date:** 2026-06-22

---

## 0. The one question this probe answers

> The old flywheel/continuation attempts (`flywheel_residual_attempt2` → champion **iter8**; `deepteacher` iter9–12) were all run on the **v2.7 leaf substrate**, which the project repeatedly fingered as *the ceiling* ("the v2.7 leaf caps learned strength … no mixing of the existing components breaks that cap", `measurement/search_policy_mixing/SEARCH_POLICY_MIXING_REPORT.md:19`). The **v2.8 leaf** (v2.7 + `meeple_k=2`) is a confirmed large *classical-engine* improvement. **Does restarting self-play from iter8 under the v2.8 leaf produce a checkpoint that beats the frozen `iter8 + v2.8` parent in same-leaf, deck-paired eval?**

This is a **small continuation probe (1–3 iterations)**, not a heroic flywheel. The binding comparison is against **frozen `ITER8_V28_PARENT`** (iter8 net evaluated *with* the v2.8 leaf), NOT old `iter8 + v2.7`. Beating `iter8 + v2.7` is meaningless — the v2.8 leaf already does that by +154.5 Elo for *any* net.

**Prior on the outcome (stated up front, honestly):** the leaf-swap battery already showed v2.8 lifts heuristic search *and* neural-guided search by ~the same large amount, and at **equal leaf** `heur@3200_v2.8` still beats `iter8+v2.8` by **−38.4 Elo** (`measurement/heuristic_v28/V28_LEAF_SWAP_REPORT.md`), i.e. the neural-vs-deep-heuristic gap is *unchanged* at equal leaf. So the leaf swap by itself is not an ML lever. The open question is narrower: whether *distilling v2.8-guided MCTS* (stronger policy targets) into the net beats iter8's v2.7-distilled policy when both are scored by v2.8. There is a plausible mechanism (better leaf → better visit-count policy targets → better distilled priors), and there is a plausible null (iter8's policy already saturated, deeper-teacher washout). The probe is the cheapest way to discriminate.

---

## 1. Exact iter8 checkpoint / hash (the parent & warm-from)

| field | value | source |
|---|---|---|
| ckpt_id | `flywheel2_champion_iter8` | `governance/PRODUCTION.yaml:14` |
| path (local) | `/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt` | `PRODUCTION.yaml:17` |
| path (remote ssh) | `/mnt/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt` | `PRODUCTION.yaml:18` |
| sha256 | `0d355002e26a968e913396858aa51b52c95a1903db324c4fbab6849cc279ee2c` | `PRODUCTION.yaml:19` |
| arch | `96x6 ResNet, n_scalar_features=12, value_global_pool=False` | `PRODUCTION.yaml:20` |
| lineage | `residual(iter0) → iter2 → iter4 → iter5 → iter8` (attempt-2) | `governance/CHECKPOINT_LINEAGE.csv` row 10 |

iter8 is the **frozen warm-from parent** for RoD. The probe **does not** modify, relabel, or overwrite it.

## 2. Exact v2.8 leaf config

**v2.8 = v2.7 leaf + the LEGACY `meeple_k=2.0` term. One env var is the entire difference.**

- v2.7 leaf in code: `virtual_score_v2` (`src/carcassonne_ai/virtual_score_v2.py`); production hot path = the bit-exact `flat_virtual_score_v2` in `src/carcassonne_ai/flat_leaf.py` under `CARCASSONNE_USE_FLAT_LEAF=1`.
- The meeple term: `virtual_score_v2.py:574-575` — `if cfg.meeple_k > 0.0: score += cfg.meeple_k * (state.meeples[player] - state.meeples[opp])`. Implemented in **object + flat + Cython** paths → runs at full production speed.
- **`meeple_k` is the LEGACY `LeafConfig` field** (env `CARCASSONNE_V25_MEEPLE_K`, default `0.0`). It does **NOT** trigger `_v28_active()` → the leaf stays on the FLAT/Cython fast path.
- ⚠️ **Do NOT** use `CARCASSONNE_V28_MEEPLE_K` / `v28_meeple_k` (the recovery-scaled experimental field). It sets `_v28_active()=True` → forces the ~2.26× slower object path, and the recovery-scaling variant *hurt* ~75 Elo. The leaf-swap battery used the **legacy** field; so do we.

**Env-knob set, v2.7 vs v2.8 (side by side):**

| env knob | v2.7 (frozen) | v2.8 (this probe) |
|---|---|---|
| `CARCASSONNE_V25_CAP` | `12` | `12` |
| `CARCASSONNE_V25_DROP_THREE_OPEN` | `1` | `1` |
| `CARCASSONNE_USE_FLAT_LEAF` | `1` | `1` |
| `CARCASSONNE_USE_CY_REPR` | `1` | `1` |
| `CARCASSONNE_V25_VALUE_BLEND` | `0` | `0` |
| `CARCASSONNE_V25_RESIDUAL_SCALE` | `0.25` (neural) | `0.25` (neural) |
| **`CARCASSONNE_V25_MEEPLE_K`** | **`0.0` (absent)** | **`2.0`** ← the only difference |

Source: `measurement/heuristic_v28/V28_CANDIDATE_CONFIG.json` (`env_to_reproduce`), `V28_VARIANT_CONFIGS.json` (`base_env_knobs`), `V28_LEAF_SWAP_REPORT.md`.

**k=2 is the validated peak** (inverted-U, heur@200 paired n=200): k1 +75.9, **k2 +179.5 (z=9.92)**, k3 +159.8, k4 +34.9 (`V28_LEAF_SWAP_REPORT.md:20-21`). `HEURISTIC_VALUE_NORM=15`, so k=2 is near-interior-optimal, not an edge value. **No hoarding pathology** (`V28_LEAF_SWAP_REPORT.md:22-25`).

**v2.8 leaf-swap headline battery (the parent/ruler numbers this probe builds on):**

| matchup | n | Elo | z | results.csv row |
|---|---|---|---|---|
| `iter8+v2.8` vs `iter8+v2.7` | 400 | **+154.5** | 9.82 | `iter8_v28meeplek2_vs_iter8_v27_neural_n400` |
| `iter8+v2.8` vs `heur@3200_v2.7` | 200 | **+153.4** | 5.87 | `iter8_v28_vs_heur3200_v27_n200` |
| `iter8+v2.8` vs `heur@3200_v2.8` (EQUAL LEAF) | 200 | **−38.4** | −1.56 | `iter8_v28_vs_heur3200_v28_n200` |
| `hybrid:8:800 v2.8` vs `hybrid:8:800 v2.7` | 200 | **+153.4** | 5.87 | `hybrid8_800_v28_vs_v27_n200` |

The **−38.4 at equal leaf** is the load-bearing line: the leaf swap is a *classical* gain, not an ML/superhuman lever. v2.8 = an **experimental stronger ruler**, not a production replacement (`V28_LEAF_SWAP_REPORT.md:55-56`).

## 3. Prior old-substrate (v2.7) flywheel failure summary

Across two structurally-different residual self-play flywheels on the **v2.7 substrate**, compounding self-improvement was real but **bounded and policy-only**:

- **Attempt #1** (`flywheel_residual_v2`): out-of-lineage NULL (best cumulative +14.3 / z0.49 over iter0; CL-011 Disfavored).
- **Attempt #2** (`flywheel_residual_attempt2`, external keep-best on deck-paired heur@800-v2.7): produced champion **iter8**, sealed **+67.4 Elo / z2.73** over iter0 (n=400 paired, band 1.7e9) — but the climb **saturated by iter5** (iters 6–10 within ~1.5σ). Stage-A/B decomposition (`docs/PLATEAU_DECOMP_2026-06-10.md`): the gain is **~95% policy distillation** (policy-only iter0 +10.4 → iter5 +52.5 → iter8 +54.3); the residual/value head is a **static ~+22 additive that ranks sibling moves at chance (τ≈0)** and never bootstraps local discrimination.
- **Deeper-teacher** (`docs/DEEPER_TEACHER_SPEC_2026-06-11.md`; gen sims 200→800, 12 iters warm-from iter8): clean **powered-null vs iter8** — +14.6 / z0.65 @s200, +12.4 / z0.51 @s800 (`deepteacher_audit/ITER8_VS_ITER12_VERDICT.md`). Net (policy) gains **wash out** under deep search; both nets lift ~+70 from deep search regardless of priors.

**The repeated hypothesis** (`SEARCH_POLICY_MIXING_REPORT.md:19,92-96`; `DEEPER_TEACHER_SPEC` §ceiling; `DECISIONS.md` 2026-06-04 & 2026-06-18): the **hand-crafted v2.7 leaf is the shared ceiling** — "raising the leaf raises both heuristic search AND iter8's leaf simultaneously — the one lever that moves the shared cap." The search-policy-mixing report **explicitly names a stronger leaf (v2.8) as the recommended unstick lever**. RoD tests exactly that.

## 4. What is REUSED (no new code where avoidable)

| reused asset | path | role in probe |
|---|---|---|
| iter8 checkpoint | `flywheel_residual_attempt2/ckpt/iter8.pt` | frozen parent + warm-from |
| flywheel master loop | `scripts/run_residual_flywheel_v2.sh` | turn-key 3-box gen→train→select→seal (self-healing); the scaffold |
| self-play gen (orch) | `scripts/gen_flywheel.sh` → `scripts/run_selfplay_iter.py` | per-box orchestrated gen |
| training | `scripts/train_iter.py` | `--warm-from iter8 --output rod/iter_N.pt`, epochs 3, VLW 1.5 (attempt-2 settings) |
| Rust orchestrator | `rust/carc-orch/` (`target/release/carc-orch`, `run_server.sh`) | SHM net server, high-W |
| net-vs-net leaf-swap eval | `scripts/heuristic_v28/v28_leaf_swap_orch.py` (+ `.sh`) | reference; **note: same-net/diff-leaf only** |
| agent-vs-agent eval | `scripts/level2/eval_hybrid_handoff.py` (+ `scripts/heuristic_v28/v28_handoff_orch.sh`) | diff-checkpoint / vs-heur eval with `--meeple-k-a/-b` |
| v2.8 leaf | `CARCASSONNE_V25_MEEPLE_K=2.0` (legacy field, flat path) | self-play + eval leaf |

**The one wiring gap to close (Phase 2/3):** `run_selfplay_iter.py` has **no `--meeple-k` flag** and `--leaf-eval` has no `v2_8` option. v2.8 self-play is enabled by setting `CARCASSONNE_V25_MEEPLE_K=2.0` in the gen env (legacy field → flat path → `_v28_active` stays False). This MUST be verified with a 1-game smoke (leaf value differs from v2.7, flat path active) before any long run.

## 5. What is intentionally NOT changed (hard constraints)

- `governance/PRODUCTION.yaml` — untouched. Champion stays `flywheel2_champion_iter8`.
- v2.7 leaf — bit-identical under legacy configs (`CARCASSONNE_V25_MEEPLE_K` defaults `0.0`). v2.8 is opt-in via that one env var.
- **architecture** — same 96×6 ResNet, n_scalar=12 (warm-from requires it).
- **residual_scale = 0.25**, **c_puct = 3.0**, **sims = 200**, leaf family, deck bands, evaluator configs — held fixed; not silently changed. (Re-sweeping `residual_scale`/`CAP` *would* be defensible since the leaf term shifts optima — but that is a broad hyperparameter search, explicitly **out of scope** here. Noted as a caveat, not actioned.)
- No promotion, no champion move, no long multi-day run, no broad hyperparameter search.

## 6. Cost estimate per iteration (owned hardware; no cloud $)

Boxes for this probe (per user): **local 5800x-box (5900XT 16C/32T + RTX 5060 Ti) + laptop (i7-14650HX + RTX 4070m)**. Rust orch, high W.

- **Self-play gen, sims=200, orch:** 5800x W28 ≈ 10 games/min; laptop W8 ≈ 7 games/min → combined ≈ **17 games/min**. (Source: memory `reference_carc_orch_verdict`, `feedback_worker_count_by_bottleneck`.)
  - 1000 games ≈ **~1 h**; 1500 games ≈ **~1.5 h**.
- **Training, 5900XT:** 0.196 s/batch (memory `reference_training_latency_bound`); measured train phases 9–16 min/iter. Train on the 5900XT, **not** the laptop (laptop trains ~10% slower).
- **Per-iteration end-to-end** (gen + train + a paired eval gate): **~1.5–2 h** for ~1000 games; gen+train only ≈ **~1.25 h**.
- **1–3 iterations:** ~1.5 h (1 iter, gen+train+pilot eval) up to ~5–6 h (3 iters with full gates). **Plan: run iter-1 first, gate on the pilot, only continue if it shows signal** (cost discipline — cheapest-informative first, stop early).

n-power reminder (`CLAUDE.md`): n=400 paired ≈ ±12 Elo (resolves ≥~35 Elo); n=100 ≈ ±35 Elo (coarse screen). Pilot at n=100–200, top up only if positive/noisy.

---

## Phase 0 close-out

- Exact iter8 checkpoint/hash: **§1** ✅
- Exact v2.8 leaf config (`v2.7 + meeple_k=2`, `CARCASSONNE_V25_MEEPLE_K=2.0`, legacy field/flat path): **§2** ✅
- Prior old-substrate flywheel failure summary: **§3** ✅
- What is reused: **§4** ✅
- What is intentionally not changed: **§5** ✅
- Cost estimate per iteration: **§6** ✅

→ Proceed to Phase 1 (frozen baseline registry + reproduce `ITER8_V28_PARENT`).
