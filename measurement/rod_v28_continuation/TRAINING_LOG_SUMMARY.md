# RoD v2.8 Continuation Probe — Training Log Summary (Phase 3)

**Branch:** `rod_v28_continuation_probe` @ base `ccc33c2` · **Date:** 2026-06-22 · **Status:** MEASUREMENT ONLY (v2.7 frozen, v2.8 opt-in, no promotion).
Machine-readable: [`CHECKPOINT_MANIFEST.json`](CHECKPOINT_MANIFEST.json).

---

## RoD_iter_01 — self-play gen

- **1000 games** of v2.8-guided self-play (`CARCASSONNE_V25_MEEPLE_K=2.0`, legacy field → flat fast path), warm-from **iter8**.
- sims=200, c_puct=3.0, leaf v2.8, residual_scale=0.25, value_target=residual, seed_start=600010000 (band < 1e9).
- Boxes: 5800x carc-orch SHM **W28** + laptop carc-orch SHM **W8**, shared-claim into one pool.
- Result: 562 fresh (local) + 438 fresh (laptop) + 24 skipped + **0 failed** = 1000 npz, **2,121,164 positions**, ~49 min wallclock (local 2939 s / laptop 2853 s, overlapped).

## RoD_iter_01 — training (production recipe: batch 256, 3 epochs)

`scripts/train_iter.py --warm-from iter8 --epochs 3 --batch-size 256 --value-loss-weight 1.5 --window 10 --warmstart-mix-fraction 0.0` on the 1000-game buffer (2,064,525 train + 108,671 val positions).

| epoch | s | batches | train_pol | val_pol | train_val | train_own |
|---|---|---|---|---|---|---|
| 1 | 1562.2 | 8065 | 1.5557 | 0.2693 | 0.0057 | 0.1718 |
| 2 | 1496.7 | 8066 | 1.5436 | 0.2693 | 0.0056 | 0.1316 |
| 3 | 1521.5 | 8065 | 1.5379 | 0.2699 | 0.0056 | 0.1089 |

- **policy entropy 1.5429 nats** (baseline 1.7463, floor 0.8731) — no collapse.
- value↔target corr (residual-vs-residual) = **+0.4126** (NOT the value-vs-outcome ruler; tracked iter-over-iter).
- **val policy loss flat across all 3 epochs (0.269→0.269→0.270)** → the policy fit converges by epoch 1–2; epoch 3 is marginal.
- Output: `rod_v28_continuation/ckpt/iter_01.pt`, sha256 `a8b824df0786284cbc5caf8e49d27ea90fb263bc1016eed27c2fe30e6d2a1f4b`, total train 4580 s (~76 min). No crashes/resumes.
- Parent iter8 sha verified unchanged (`0d355002…`).

## Batch-size speed A/B/C (MEASUREMENT ONLY — throwaway, never promoted)

Per the user, an A/B/C of training wall-clock vs batch size (1 epoch each, warm-from iter8, same staged data, output to `/tmp`, **never loaded by anything**). Bigger batch = a *systematically different net* (effective-LR change; DECISIONS 2026-06-10), so these are speed measurements only — **production stays batch 256 / 3 epochs.**

| batch | s/epoch | batches/epoch | s/batch | epoch speedup vs 256 | val_pol @1 epoch |
|---|---|---|---|---|---|
| **256 (A)** | ~1527 (3-epoch avg) | 8065 | 0.189 | 1.00× | 0.269 |
| **512 (B)** | 1180.6 | 4033 | 0.293 | **1.29×** | 0.434 |
| **1024 (C)** | 1045.8 | 2017 | 0.519 | **1.46×** | 0.780 |

**Interpretation:**
- **Diminishing returns.** Per-batch time grows ~1.55× (256→512) then ~1.77× (512→1024) per doubling, while batch count halves — so wall-clock does *not* halve. Net epoch speedup tops out at ~1.46× (batch 1024).
- **Latency-bound only at small batch.** At 256 the per-batch sync round-trip dominates (0.189 s/batch on a 7M net); by 512–1024 the GPU forward/backward compute dominates (0.29→0.52 s/batch), so the "fewer sync round-trips" lever saturates fast. Confirms the project's measured `reference_training_latency_bound` picture.
- **Strength caveat (visible in the data).** val policy loss after 1 epoch worsens monotonically with batch (0.27 → 0.43 → 0.78) — bigger batch = fewer gradient steps = less converged per epoch. To use a bigger batch in production you'd rescale LR and run a strength A/B (DECISIONS 2026-06-10), not assume parity.
- **Cheaper, safer lever:** dropping epoch 3 at batch 256 gives ~1.5× (76→51 min) with **zero** strength risk, since val loss was already flat by epoch 2. So for any iters 2–3 the recommended speed cut is **2 epochs @ batch 256** (safe), optionally + batch 512 with LR rescale if more speed is needed.

→ Proceed to Phase 4 (net-vs-net eval: RoD_iter_01 + v2.8 vs frozen ITER8_V28_PARENT).
