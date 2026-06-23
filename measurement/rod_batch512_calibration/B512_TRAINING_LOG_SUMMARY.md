# rod_batch512_calibration — Phase 2: B512 Training Log Summary

**Branch:** `rod_batch512_calibration` · **Date:** 2026-06-22 · **Status:** MEASUREMENT ONLY (v2.7 frozen, v2.8 opt-in, no promotion).
Machine-readable: [`B512_CHECKPOINT_MANIFEST.json`](B512_CHECKPOINT_MANIFEST.json).

## What ran

`ROD_ITER1_B512_TEST` = a sibling of `RoD_iter_01` trained from the **same frozen iter8 parent** on the **same 1000-npz v2.8 self-play data** (NOT re-generated — reused `/mnt/c/carc-shared/rod_v28_continuation/iter1_data/`), with **only `--batch-size` changed 256 → 512**. Single clean run on the 5900XT, no crashes/resumes.

**Cleanliness verified:** the training provenance records dataset fingerprint **`61a12d76cd65b719` — identical to B256**, and identical `lr=1e-3 / wd=1e-4 / epochs=3 / value_loss_weight=1.5 / aux=0.15 / seed=0 / window=10`. So the *only* difference from the B256 reference is the batch size (and its direct consequence, half the optimizer steps).

- output: `rod_batch512_calibration/ckpt/iter_01_b512.pt`, sha256 `9cca3edf…`, code_commit `704c0de`.

## Training curve (batch 512, 3 epochs)

| epoch | s | n_batches | train_pol | val_pol | train_val | val_val | train_own | val_own |
|---|---|---|---|---|---|---|---|---|
| 1 | 1167.9 | 4033 | 1.5531 | 0.4344 | 0.0057 | 0.0059 | 0.1897 | 0.0595 |
| 2 | 1162.0 | 4033 | 1.5434 | 0.4348 | 0.0057 | 0.0059 | 0.1476 | 0.0609 |
| 3 | 1163.7 | 4033 | 1.5376 | 0.4354 | 0.0056 | 0.0059 | 0.1215 | 0.0619 |

- **total train 3493.6 s (58.2 min)** vs B256 **4580.4 s (76.3 min)** ⇒ **1.31× wall-clock speedup** (matches the predicted ~1.29× epoch speedup; full-train a touch better as staging/val overhead amortizes).
- **total optimizer steps 12,099** = exactly **half** of B256's 24,196 (4033×3 vs 8065×3).
- **policy entropy 1.5393 nats** (baseline 1.7463, floor 0.8731) — **no collapse** (≈ B256's 1.5429).
- **value↔target corr +0.4115** (residual-vs-residual) ≈ B256's +0.4126 — the value head fits identically.

## Honest read of the curve (diagnostic — does NOT decide the branch)

- **train_pol is basically identical to B256** (final 1.5376 vs 1.5379) — the network *can* fit the training policy targets at batch 512.
- **val_pol is markedly worse and flat-high: ~0.435 (B512) vs ~0.270 (B256)** — a **+0.166 / +61% gap** that is stable across all 3 epochs (B512 even drifts up slightly, 0.4344→0.4354, a whiff of overfit-to-train). `val_own` is likewise worse (~0.060 vs ~0.039).
- **It is not an epochs problem.** Both arms' val_pol plateaus by epoch 1 (B512 0.434→0.435; B256 0.269→0.270). Doing 3 epochs at batch 512 reaches a *worse policy optimum* than 3 epochs at batch 256 — the lost gradient steps are not recoverable within the epoch budget at this LR. This is the textbook "bigger batch, same LR, same epochs ⇒ fewer steps ⇒ under-converged policy head" outcome (the standard fix — LR rescale — is explicitly out of scope for this naive-swap test).

**So on the training curve alone, B512 is a measurably under-fit policy head.** But `val_pol` is a per-position cross-entropy to the MCTS visit distribution, and this project's standing finding is that per-move policy precision ≠ whole-game strength (the net is used as MCTS@200 *priors*, and search corrects imperfect priors; net gains routinely wash out under deep search). The prompt is explicit that **training loss does not decide the branch.** Phase 4 (vs frozen parent) and Phase 5 (vs B256) measure whether this 0.27→0.44 val gap actually costs *playing* strength or washes out under search.

→ Proceed to Phase 4/5 (net-vs-net, carc-orch SHM, work-stealing local W48 + laptop W16).
