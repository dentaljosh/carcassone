# RoD v2.8 Continuation Probe — Frozen Baseline Registry (Phase 1)

**Branch:** `rod_v28_continuation_probe` @ `ccc33c2` · **Date:** 2026-06-22 · **Status:** MEASUREMENT ONLY (no promotion, v2.7 frozen, v2.8 opt-in).
Machine-readable configs: [`BASELINE_CONFIGS.json`](BASELINE_CONFIGS.json). All five baselines are **frozen** for the duration of the probe; nothing here is a champion or a promotion candidate.

---

## The five frozen baselines

| id | agent | ckpt | sims | leaf | residual | meeple_k | role |
|---|---|---|---|---|---|---|---|
| **ITER8_V27_PROD** | NeuralMCTS | iter8 | 200 | v2.7 | 0.25 | 0.0 | lower reference (production champion) — *not* binding |
| **ITER8_V28_PARENT** | NeuralMCTS | iter8 | 200 | v2.8 | 0.25 | **2.0** | **BINDING BASELINE** — every RoD ckpt must beat this at equal leaf |
| **HEUR_3200_V28** | HeuristicMCTS | — | 3200 | v2.8 | 0 | 2.0 | strong out-of-lineage ruler |
| **HEUR_800_V28** | HeuristicMCTS | — | 800 | v2.8 | 0 | 2.0 | matched-budget ruler (keep-best family) |
| **HYBRID_K8_V28** (opt) | hybrid:8:800 | iter8 | 200/800 | v2.8 | 0.25 | 2.0 | optional ruler |

**v2.8 = v2.7 + `CARCASSONNE_V25_MEEPLE_K=2.0`** (legacy `LeafConfig.meeple_k` field → `_v28_active()` stays False → flat/Cython fast path). v2.7 = the same with `meeple_k=0.0` (the env var absent). The *only* difference between any `_V27_` and `_V28_` config is that one env var. Full env sets in `BASELINE_CONFIGS.json` (`base_env_v27_neural` / `base_env_v28_neural` / `base_env_v28_heuristic`).

## The binding decision rule (restated)

- RoD only **"turns on"** if a new checkpoint beats **frozen `ITER8_V28_PARENT`** in same-band, deck-paired, same-leaf (v2.8) eval with a credible margin.
- Beating `ITER8_V27_PROD` is **meaningless** — the v2.8 leaf already does that by **+154.5 Elo** for *any* net, including iter8 itself. The leaf swap is a classical-engine gain, not an ML gain.
- The equal-leaf gap to the strong ruler is set by `ITER8_V28_PARENT` vs `HEUR_3200_V28` = **−38.4 Elo** (already measured, battery row `iter8_v28_vs_heur3200_v28_n200`). RoD's secondary question (Phase 5) is whether a continuation shrinks that −38.4.

## Already-measured anchor strengths (do not re-spend; cite the battery)

From the v2.8 leaf-swap battery (`measurement/heuristic_v28/`, `experiments/results.csv`):

| matchup | n | Elo | z | row |
|---|---|---|---|---|
| ITER8_V28_PARENT vs ITER8_V27_PROD | 400 | +154.5 | 9.82 | `iter8_v28meeplek2_vs_iter8_v27_neural_n400` |
| ITER8_V28_PARENT vs HEUR_3200_V27 | 200 | +153.4 | 5.87 | `iter8_v28_vs_heur3200_v27_n200` |
| ITER8_V28_PARENT vs HEUR_3200_V28 (equal leaf) | 200 | −38.4 | −1.56 | `iter8_v28_vs_heur3200_v28_n200` |
| HYBRID_K8_V28 vs HYBRID_K8_V27 | 200 | +153.4 | 5.87 | `hybrid8_800_v28_vs_v27_n200` |

`HEUR_800_V28` has no direct battery anchor; it will be characterized in Phase 5 only if a RoD checkpoint survives Phase 4.

## Reproduction gate — `ITER8_V28_PARENT` reproduces the v2.8 config EXACTLY ✅

Ran `scripts/rod_v28/verify_iter8_v28_parent.py` (deterministic, CPU-only) on the local box, branch `rod_v28_continuation_probe`:

```
[1] iter8 sha256 OK: 0d355002e26a968e913396858aa51b52c95a1903db324c4fbab6849cc279ee2c
[2] DEFAULT_CONFIG.meeple_k = 0.0 (expect 0.0)
[3] cfg28.meeple_k=2.0  _v28_active(cfg28)=False (expect False -> flat path)
[4] leaf-value check: 100 states; meeple term fired (nonzero) in 25; formula-exact=True
RESULT: REPRODUCED
```

This confirms, deterministically:
1. **Parent identity** — iter8 checkpoint sha256 matches `PRODUCTION.yaml` exactly.
2. **v2.7 bit-identity** — the default leaf config has `meeple_k=0.0` (v2.7 unchanged when the env var is absent).
3. **Fast-path guarantee** — the v2.8 config (`meeple_k=2.0` via the legacy field) keeps `_v28_active()` False, so it runs the production FLAT/Cython leaf, not the 2.26× object path.
4. **Correct leaf semantics** — on real mid-game states, `leaf(v2.8) − leaf(v2.7) == 2·(meeples_self − meeples_opp)` exactly, and the term actually fires (25/100 sampled states had a meeple asymmetry).

**Strength-level reproduction** (the +154.5 Elo headline) is the already-banked **n=400** battery result, measured on the *same* leaf code this branch inherits (no leaf code changed from `ccc33c2`). It will be re-confirmed as a free side-check at small n when the orchestrator is stood up for Phase 3 (the pre-flight orch smoke), per the pre-flight-smoke rule — but the config-level reproduction above is the Phase-1 gate and it passes.

→ **Gate PASSED. Proceed to Phase 2 (probe design).**
