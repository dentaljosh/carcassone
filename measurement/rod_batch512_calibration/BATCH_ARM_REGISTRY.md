# rod_batch512_calibration — Phase 1: Batch-Arm Registry

**Branch:** `rod_batch512_calibration` · **Date:** 2026-06-22 · **Status:** MEASUREMENT ONLY.
Machine-readable: [`BATCH_ARM_CONFIGS.json`](BATCH_ARM_CONFIGS.json).

Two arms. They differ in **exactly one** training hyperparameter — `--batch-size` (256 → 512). Everything else (warm-from, data, epochs, LR, weight-decay, schedule, value-loss-weight, aux-weight, value-target, seed, architecture, leaf) is identical. Both are evaluated under the identical play config (NeuralMCTS@200, c_puct 3.0, residual_scale 0.25, **v2.8 leaf**, deck-paired both seats).

---

## Arm A — `ROD_ITER1_B256_REFERENCE` (reference; existing, NOT retrained)

The validated RoD_iter_01. Used as-is; reproducibility already established by the RoD probe (verify_iter8_v28_parent + the +53.4/z3.51 parent matchup).

| field | value |
|---|---|
| checkpoint | `/mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.pt` |
| sha256 | `a8b824df0786284cbc5caf8e49d27ea90fb263bc1016eed27c2fe30e6d2a1f4b` |
| metrics | `/mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.metrics.json` |
| **batch_size** | **256** |
| epochs | 3 |
| warm-from | iter8 (`0d355002…`) |
| n_batches/epoch | 8065 |
| seed | 0 |
| code_commit @ train | `9e3c0ea` |
| validated strength | +53.4 elo / z3.51 (n=400) vs ITER8_V28_PARENT; TIE vs heur@3200_v28 (n=800) |

## Arm B — `ROD_ITER1_B512_TEST` (test; to be trained in Phase 2)

Sibling from the SAME frozen iter8 parent on the SAME data, **only batch 256→512**. No LR rescale, no extra epochs, no extra data.

| field | value |
|---|---|
| checkpoint (planned) | `/mnt/c/carc-shared/rod_batch512_calibration/ckpt/iter_01_b512.pt` |
| sha256 | *(filled in Phase 2)* |
| **batch_size** | **512** |
| epochs | 3 |
| warm-from | iter8 (`0d355002…`) — identical to Arm A |
| n_batches/epoch | ~4033 (≈half of A) |
| seed | 0 — identical data ordering to Arm A |
| code_commit @ train | *(filled in Phase 2)* |

## Identical-vs-differing matrix

| knob | Arm A (B256) | Arm B (B512) | same? |
|---|---|---|---|
| `--batch-size` | 256 | **512** | ❌ THE VARIABLE |
| warm-from | iter8 | iter8 | ✅ |
| data (1000 npz, fp `61a12d76…`) | same | same | ✅ |
| `--window` | 10 | 10 | ✅ |
| `--warmstart-mix-fraction` | 0.0 | 0.0 | ✅ |
| `--epochs` | 3 | 3 | ✅ |
| `--lr` | 1e-3 | 1e-3 | ✅ |
| `--weight-decay` | 1e-4 | 1e-4 | ✅ |
| `--lr-schedule` | none | none | ✅ |
| `--value-loss-weight` | 1.5 | 1.5 | ✅ |
| `--aux-weight` | 0.15 | 0.15 | ✅ |
| `--value-target` | residual (baked) | residual (baked) | ✅ |
| `--seed` | 0 | 0 | ✅ |
| arch | 96×6, n_scalar=12, no pool | 96×6, n_scalar=12, no pool | ✅ |
| leaf (search-time) | v2.8 | v2.8 | ✅ |
| eval config | NMCTS@200 c3.0 rs0.25 v2.8 paired | identical | ✅ |
| **derived** optimizer steps/epoch | 8065 | ~4033 | (consequence of the variable) |

## Planned B512 train command (Phase 2)

```
python -u scripts/train_iter.py \
  --output-root /mnt/c/carc-shared/rod_v28_continuation/iter1_data \
  --warmstart-root data/warmstart/heuristic_tau05 \
  --iter 0 \
  --window 10 \
  --warmstart-mix-fraction 0.0 \
  --value-loss-weight 1.5 \
  --batch-size 512 \
  --stage-local /tmp/rod_b512_stage \
  --warm-from /mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt \
  --output /mnt/c/carc-shared/rod_batch512_calibration/ckpt/iter_01_b512.pt \
  --epochs 3 \
  --prov-value-target residual \
  --prov-selfplay-leaf v2_8_meeple_k2 \
  --prov-run-tag rod_batch512_calibration
```
(identical to the B256 command except `--batch-size 512`, the `--output` path, the `--stage-local` dir, and `--prov-run-tag`.)
