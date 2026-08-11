# Stage F — Training Dynamics Audit (RoD2, v2.9 leaf Bmild_cap8)

**Question:** Is training healthy but target-limited?
**Source:** `ckpt/iter_0{2..6}.metrics.json`, `CHEAP_SCREEN_RESULTS.csv`. FREE (logs only, no compute).

## Per-iter (final-epoch) trajectory

| iter | train_pol↓ | val_pol | train_val | value_corr | policy_entropy | n_train_pos |
|---|--:|--:|--:|--:|--:|--:|
| 02 | 1.5619 | 0.2753 | 0.0074 | 0.4454 | 1.5669 | 806,973 |
| 03 | 1.5914 | 0.3308 | 0.0074 | 0.4459 | 1.6023 | 797,200 |
| 04 | 1.5952 | 0.2922 | 0.0072 | 0.4390 | 1.6077 | 795,885 |
| 05 | 1.6142 | 0.2553 | 0.0074 | 0.4670 | 1.6136 | 786,872 |
| 06 | 1.6193 | 0.2977 | 0.0073 | 0.4448 | 1.6085 | 789,484 |

baseline_policy_entropy = 1.7463 · entropy_floor = 0.8731 · recipe frozen (batch 256, 3 epochs, VLW 1.5, residual_scale 0.25).

## Findings

**1. Within each iter, training is mechanically HEALTHY.** Every iter's `train_pol` decreases monotonically across its 3 epochs (e.g. iter02: 1.5867→1.5699→1.5619), `val_pol` stays flat within the iter (no overfit blowup), no NaN/divergence. The optimizer is doing its job.

**2. Across iters, `train_pol` RISES 1.562 → 1.619 (+0.057, ~monotone).** The policy target gets *harder to fit* each iter — i.e. it is becoming **noisier / higher-entropy**, not sharper.

**3. `policy_entropy` RISES 1.567 → 1.609, drifting toward the warmstart baseline 1.746** (away from the floor 0.873). A healthy AlphaZero flywheel *sharpens* (entropy falls as the net concentrates on stronger moves). This chain does the **inverse** — the policy is diffusing. Corroborated independently by Stage D (self-play policy-target entropy 1.494→1.538).

**4. The value head is INERT.** `train_val` flat ~0.0072–0.0078; `value_corr` flat ~0.44–0.47 with no trend across 5 iters. Stage D shows why: the `residual` value target has near-zero dynamic range (std ~0.13, **38–43 % of targets within ±0.02 of zero**), so the head saturates on the mean immediately and has nothing new to learn iteration-over-iteration.

**5. No training metric improves across the chain, and none could predict an h6400 gain.** `val_pol` is noisy (0.255–0.331) with no trend; entropy and `train_pol` move the wrong way; `value_corr` is pinned.

## Verdict

Training is **healthy but target-limited**. The pipeline converges cleanly every iter, but it is fitting targets that are not getting stronger: the **value target carries no teaching signal beyond the heuristic** (near-zero dynamic range → corr pinned ~0.45) and the **policy target is getting noisier, not sharper** (train_pol + entropy both rising). This is the same signature the v2.8 autopsy recorded ("value head degrading, self-play diffusing"). The v2.9 leaf swap did not change it.
