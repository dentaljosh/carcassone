# rod_batch512_calibration — Phase 0: Reuse & Scope

**Branch:** `rod_batch512_calibration` (from `rod_v28_continuation_probe` @ `902b747`) · **Date:** 2026-06-22
**Status banner:** 🔬 IN PROGRESS · **MEASUREMENT / RECIPE-CALIBRATION ONLY** — no promotion, `PRODUCTION.yaml` UNCHANGED, champion still `flywheel2_champion_iter8`, v2.7 leaf bit-identical, v2.8 opt-in. No multi-iteration flywheel. No batch-1024 in this branch.

## The one question

> **Can batch size 512 replace batch size 256 for the RoD v2.8 continuation recipe without weakening the net?**

This is a **recipe-calibration** test, not a new flywheel and not a promotion. The motivation is the wall-clock measurement from the RoD probe: batch 512 trains an epoch ~1.29× faster than 256. The risk is that the speedup comes from doing *half the gradient steps per epoch* at the same LR, which can leave the net under-fit. The 1-epoch A/B/C already flagged this (val-policy after 1 epoch: 256→0.269, 512→**0.434**, 1024→0.780). The calibration resolves whether that 1-epoch gap closes by epoch 3 and, more importantly, whether the **final** B512 net is as strong as the final B256 net in actual play.

## Treat batch size as a scientific variable

Bigger batch at fixed LR and fixed epochs = **fewer optimizer steps** and a different effective learning rate (DECISIONS 2026-06-10). It is NOT a harmless speed toggle: it changes the trained net. So this branch trains a clean sibling and **measures strength**, rather than assuming parity.

## Exact frozen artifacts (all cited)

### Parent (binding comparison anchor — frozen)
- **`ITER8_V28_PARENT`** = `flywheel2_champion_iter8` evaluated under the v2.8 leaf.
- path (local): `/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt`
- sha256: `0d355002e26a968e913396858aa51b52c95a1903db324c4fbab6849cc279ee2c`
- arch: 96×6 ResNet, n_scalar_features=12, value_global_pool=False (7,417,037 params)
- This is the warm-from source for BOTH arms and the Phase-4 opponent. Never modified by this branch.

### v2.8 leaf (held constant — opt-in, search-time only)
- **v2.8 = v2.7 (`virtual_score_v2` / `flat_leaf`) + legacy `LeafConfig.meeple_k = 2.0`**, activated via env **`CARCASSONNE_V25_MEEPLE_K=2.0`**.
- Stays on the flat/Cython fast path; the legacy `meeple_k` field does **not** trip `_v28_active()` (that gate is `cfg.v28_farm_majority or cfg.v28_meeple_k != 0.0`; legacy `meeple_k` ≠ `v28_meeple_k`).
- ⚠️ Do **not** use `CARCASSONNE_V28_MEEPLE_K` (object path, 2.26× slower, recovery-scaled, hurt ~75 elo).
- The leaf is a **search-time** knob (gen + eval). **It is inert during training** — see below.

### Arm A reference checkpoint (existing, do NOT retrain)
- **`ROD_ITER1_B256_REFERENCE`** = the validated RoD_iter_01 checkpoint.
- path (local): `/mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.pt`
- sha256: `a8b824df0786284cbc5caf8e49d27ea90fb263bc1016eed27c2fe30e6d2a1f4b`
- metrics: `/mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.metrics.json`
- Validated result: **+53.4 elo / paired z=3.51 (n=400)** vs `ITER8_V28_PARENT`; **TIE** vs `heur@3200_v28` (n=800). See `measurement/rod_v28_continuation/`.

### Shared training data (held constant — reused verbatim by both arms)
- dir: `/mnt/c/carc-shared/rod_v28_continuation/iter1_data/iter_00/` — **1000 `seed_*.npz`** (seed_600010000 … seed_600010999).
- dataset fingerprint (from B256 provenance): `61a12d76cd65b719`, total_bytes 1,372,882,184.
- positions: **2,064,525 train + 108,671 val = 2,121,164 total** (val_fraction 0.05, seed 0).
- These npz carry the v2.8-guided **policy target** (`mcts_visit_distribution`) and the **residual value target** baked in at gen time. Training does NOT re-run search or re-derive targets, so the v2.8 leaf env is irrelevant at train time (confirmed: `train_iter.py` reads `prov_value_target` only as a logging label; no `getenv`/`MEEPLE`/`RESIDUAL`/`tanh` recompute).

## The exact B256 recipe (Arm A — from `iter_01.metrics.json` provenance)

`code_commit` at train: `9e3c0ea2a97994c9d336b95213ca9826521c6605` (dirty: true).

```
python -u scripts/train_iter.py \
  --output-root /mnt/c/carc-shared/rod_v28_continuation/iter1_data \
  --warmstart-root data/warmstart/heuristic_tau05 \
  --iter 0 \
  --window 10 \
  --warmstart-mix-fraction 0.0 \
  --value-loss-weight 1.5 \
  --stage-local /tmp/rod_stage_1 \
  --warm-from /mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt \
  --output /mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.pt \
  --epochs 3 \
  --prov-value-target residual \
  --prov-selfplay-leaf v2_8_meeple_k2 \
  --prov-run-tag rod_v28_continuation
```

Resolved hyperparameters (argparse defaults that were NOT overridden):
- **`--batch-size 256`** (default) ← **the ONLY axis this branch varies**
- `--seed 0` (default) — seeds `torch.manual_seed`, `np.random.seed`, the loader RNG, the warmstart-mix RNG, and the train/val split. Same `--seed` ⇒ identical data ordering across batch sizes.
- `--lr 1e-3`, `--weight-decay 1e-4`, `--lr-schedule none`
- `--aux-weight 0.15`, `--rank-weight 0.0`, `--center-weight 0.0`
- `--val-fraction 0.05`, `--num-workers 2`, `--entropy-floor-frac 0.5`

### B256 training outcome (already measured — Arm A baseline)
| epoch | s | n_batches | train_pol | val_pol | train_val | train_own |
|---|---|---|---|---|---|---|
| 1 | 1562.2 | 8065 | 1.5557 | 0.2693 | 0.0057 | 0.1718 |
| 2 | 1496.7 | 8066 | 1.5436 | 0.2693 | 0.0056 | 0.1316 |
| 3 | 1521.5 | 8065 | 1.5379 | 0.2699 | 0.0056 | 0.1089 |

policy entropy 1.5429 (floor 0.8731, no collapse); value↔target corr (residual-vs-residual) +0.4126; total train ~4580 s (~76 min).

## Known wall-clock speed results (from the RoD A/B/C, 1 epoch each, throwaway)
| batch | s/epoch | n_batches/epoch | s/batch | epoch speedup vs 256 | val_pol @1 epoch |
|---|---|---|---|---|---|
| 256 | ~1527 (3-ep avg) | 8065 | 0.189 | 1.00× | 0.269 |
| 512 | 1180.6 | 4033 | 0.293 | **1.29×** | 0.434 |
| 1024 | 1045.8 | 2017 | 0.519 | 1.46× | 0.780 |

(1024 is explicitly **out of scope** for this branch — the optimizer-step reduction is too aggressive for a modest extra wall-clock gain over 512.)

## What is HELD CONSTANT (both arms)
warm-from `iter8` · v2.8 leaf (baked into data) · arch 96×6 / n_scalar=12 / no global pool · the exact 1000-npz dataset + `--window 10` + `--warmstart-mix-fraction 0.0` · `--epochs 3` · `--lr 1e-3` · `--weight-decay 1e-4` · `--lr-schedule none` · `--value-loss-weight 1.5` · `--aux-weight 0.15` · `--value-target residual` (baked) · `--seed 0` · residual_scale 0.25 (gen-time, baked) · eval config (NeuralMCTS@200, c_puct 3.0, residual_scale 0.25, v2.8 leaf, deck-paired both seats).

## What is ALLOWED TO VARY
**`--batch-size` only: 256 → 512.** Downstream consequences that are *part of the variable*, NOT separate knobs:
- optimizer steps per epoch: 8065 → ~4033 (≈half)
- effective gradient averaging / effective LR per example

**Explicitly NOT compensated** (would confound the test): no LR rescale, no extra epochs, no extra data. This is the **naive same-epochs/same-LR swap** — exactly what someone reaching for the 1.29× speedup "for free" would do. (Any LR-rescaled variant would be a *separate, labeled* follow-up, not this calibration.)

## Cost / ETA (all local 5900XT + RTX 5060 Ti 16GB, $0)
- **Phase 2 train B512:** ~3× 1181 s ≈ **~59 min** (single retrain; gen reused, not re-run).
- **Phase 4** B512 vs parent net-vs-net (two carc-orch servers): n=200 screen → top up to 400. ~25–45 min.
- **Phase 5** B512 vs B256 net-vs-net: same. ~25–45 min.
- **Phase 6** root audit (label_midgame quick path, v2.8 env): ~15–20 min.
- Box rationale: training is **GPU-launch-latency-bound** (laptop trains ~10% slower — `reference_training_latency_bound`), and net-vs-net needs **two GPU contexts** (16GB local only; laptop 8GB can't host two). So this calibration runs **local-only**.

## Reuse map
| Need | Reuse (unchanged) |
|---|---|
| self-play data | `/mnt/c/carc-shared/rod_v28_continuation/iter1_data/iter_00/` (1000 npz) — NO re-gen |
| training script | `scripts/train_iter.py` (only `--batch-size` differs) |
| net-vs-net eval | `scripts/heuristic_v28/v28_net_vs_net_orch.{py,sh}` (two-server SHM; routes `mcts_a`/`mcts_b` by seat) |
| root audit | `scripts/midgame_reference/label_midgame.py` + `scripts/rod_v28/rod_root_audit_postprocess.py` |
| parent verify | `scripts/rod_v28/verify_iter8_v28_parent.py` |
| frozen baselines | `measurement/rod_v28_continuation/BASELINE_CONFIGS.json` (ITER8_V28_PARENT, HEUR_3200_V28, HEUR_800_V28) |
