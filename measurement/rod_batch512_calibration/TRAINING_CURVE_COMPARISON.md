# rod_batch512_calibration — Phase 3: Training-Curve Comparison (B512 vs B256)

**Branch:** `rod_batch512_calibration` · **Date:** 2026-06-22 · **Status:** MEASUREMENT ONLY.
**Diagnostic only — training loss does NOT decide the branch** (the prompt; Phase 4/5 strength evals decide). Sources: [`B512_CHECKPOINT_MANIFEST.json`](B512_CHECKPOINT_MANIFEST.json) and `/mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.metrics.json` (B256).

## Side-by-side

| metric | B256 (reference) | B512 (test) | Δ |
|---|---|---|---|
| batch size | 256 | 512 | 2× |
| n_batches / epoch | 8065 | 4033 | ½ |
| **total optimizer steps** | **24,196** | **12,099** | **½** |
| total train wall-clock | 4580.4 s (76.3 min) | 3493.6 s (58.2 min) | **1.31× faster** |
| s / epoch (mean) | 1526.8 | 1164.5 | 1.31× faster |
| s / batch | 0.189 | 0.289 | 1.53× slower/batch |
| **train_pol** (ep1/2/3) | 1.5557 / 1.5436 / **1.5379** | 1.5531 / 1.5434 / **1.5376** | ≈ identical |
| **val_pol** (ep1/2/3) | 0.2693 / 0.2693 / **0.2699** | 0.4344 / 0.4348 / **0.4354** | **+0.166 (+61%) worse** |
| train_val (ep3) | 0.0056 | 0.0056 | identical |
| val_val (ep3) | 0.0060 | 0.0059 | ≈ identical |
| train_own (ep3) | 0.1089 | 0.1215 | slightly worse |
| val_own (ep3) | 0.0383 | 0.0619 | worse (+0.024) |
| policy entropy | 1.5429 | 1.5393 | ≈ identical (no collapse) |
| value↔target corr | +0.4126 | +0.4115 | ≈ identical |

## What the curves say

1. **Speed: 1.31× wall-clock** for the full 3-epoch train (58 vs 76 min). Per-batch time grows 1.53× (0.189→0.289 s) but batch count halves, so the net win is ~1.3× — exactly the diminishing-returns picture from the RoD A/B/C (the latency-bound "fewer sync round-trips" lever saturates fast once GPU compute dominates).

2. **The network fits the *training* policy fine at batch 512** — final train_pol is identical (1.5376 vs 1.5379). Capacity/optimization is not broken; the issue is purely *how far* it converges in the step budget.

3. **The policy head is under-converged: val_pol ~0.435 vs ~0.270 (+61%).** Half the optimizer steps at the same LR ⇒ a worse policy optimum. This is **not** an epochs deficit — both arms' val_pol is flat by epoch 1 (B512 0.434→0.435; B256 0.269→0.270), and B512 even drifts up slightly (overfit-to-train tendency). Extra epochs at this LR would not close it; only more steps (smaller batch) or a rescaled LR would — and LR rescale is explicitly out of scope (a separate labeled variant, not this naive-swap test).

4. **The value and ownership-aux signals are essentially unaffected** (value corr +0.4115 vs +0.4126; val_val identical). The under-fit is concentrated in the **policy** head — which matters because the policy is exactly what the net contributes to play (MCTS priors), while the residual value head is held at scale 0.25.

5. **No collapse, no instability.** Entropy 1.5393 (well above the 0.8731 floor), monotone train losses, clean run.

## Diagnostic verdict

On the training curve, **B512 is a measurably under-fit policy head** (the direct, expected consequence of halving the optimizer steps at fixed LR/epochs). This is a real *yellow flag* for accepting batch 512 as a drop-in.

**But it is not dispositive.** `val_pol` is per-position cross-entropy to the MCTS visit distribution; the net is consumed as **MCTS@200 priors**, and this project has repeatedly found that (a) per-move policy precision is a poor predictor of whole-game strength, and (b) net/policy gains wash out under deep search. So a +61% val-policy gap could translate to a real strength loss, or could largely wash out once search corrects the priors. **Phase 4 (B512 vs frozen parent) and Phase 5 (B512 vs B256) settle it by measuring play.** The interesting scientific outcome to watch: does the clean training-loss regression survive into actual playing strength, or does MCTS launder it away?
