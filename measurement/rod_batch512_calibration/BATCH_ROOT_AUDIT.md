# rod_batch512_calibration — Phase 6: Root-Action Audit

**Question:** does B512 *play like* B256, or is it a different (e.g. degraded) policy? And does the batch change move root behavior toward/away from the deep heuristic, or collapse concentration? Method: replay the fixed 1000 v2.8 midgame-reference positions (`measurement/midgame_reference/MIDGAME_POSITION_SAMPLE.jsonl`), compute B512's NeuralMCTS@200 root move under the **v2.8 leaf** (`label_midgame.py --ckpt iter_01_b512.pt`, `CARCASSONNE_V25_MEEPLE_K=2.0`), and merge against the existing `ROOT_AUDIT_V28.jsonl` (which already holds parent / B256 / heur@3200_v28 / heur@800_v28 root choices for the same positions). Merge: `scripts/rod_v28/rod_batch_root_audit.py`. Data: [`BATCH_ROOT_AUDIT_RESULTS.csv`](BATCH_ROOT_AUDIT_RESULTS.csv), [`BATCH_ROOT_AUDIT.jsonl`](BATCH_ROOT_AUDIT.jsonl). **heur@3200_v28 choices matched the existing data 1000/1000** (clean comparison).

## Root-move agreement

| subset | n | **B512 ≡ B256** | B512 ≡ parent | B256 ≡ parent | B512 ≡ heur3200 | B256 ≡ heur3200 | parent ≡ heur3200 | Δ(B512−B256) vs heur3200 |
|---|---|---|---|---|---|---|---|---|
| **ALL** | 1000 | **0.737** | 0.676 | 0.652 | 0.521 | 0.511 | 0.520 | **+0.010** |
| opening | 200 | 0.800 | 0.785 | 0.770 | 0.600 | 0.540 | 0.585 | +0.060 |
| early_mid | 200 | 0.830 | 0.715 | 0.675 | 0.565 | 0.570 | 0.595 | −0.005 |
| mid | 200 | 0.720 | 0.685 | 0.625 | 0.495 | 0.475 | 0.495 | +0.020 |
| late_mid | 200 | 0.650 | 0.600 | 0.625 | 0.465 | 0.480 | 0.475 | −0.015 |
| pre_endgame | 200 | 0.685 | 0.595 | 0.565 | 0.480 | 0.490 | 0.450 | −0.010 |

## Findings

1. **B512 plays substantially like B256 (73.7% root agreement) — MORE alike than either is to the parent** (B512↔parent 0.676, B256↔parent 0.652). So the half-step-count under-fit did not produce a *different* policy; it produced a **less-converged version of the same policy**. The two siblings share ~3/4 of root choices, and where they differ the differences are **strength-neutral** (Phase 5 head-to-head tie). This is the mechanism behind the tie.

2. **The under-fit did NOT move B512 toward or away from the deep heuristic.** B512↔heur3200 = 0.521 vs B256's 0.511 (Δ +0.010 ≈ 0), and both ≈ the parent's 0.520. Like B256, B512's behavior is **not** convergence onto heur@3200 — the batch change is orthogonal to heuristic-imitation.

3. **No concentration collapse.** Policy entropy 1.5393 (B512) vs 1.5429 (B256) — essentially identical, both well above the floor (0.8731). The under-fit shows up as a slightly less-peaked *fit* (val_pol), not a degenerate/over-concentrated policy.

4. **Divergence concentrates in the endgame.** B512↔B256 agreement is highest in the opening/early-mid (0.80 / 0.83) and lowest in late_mid / pre_endgame (0.65 / 0.685). The opening is the most constrained (few good moves → both agree); the endgame is where the meeple-economy term and the policy have the most freedom, so the under-converged net diverges most there. (This mirrors RoD_iter_01's own opening-vs-endgame reshaping pattern.)

## Interpretation

The root audit **explains the Phase-5 tie**: B512 is not a degraded or qualitatively different agent — it is the *same policy, less converged*, agreeing with B256 on ~74% of roots and tying it in play. The ~26% of roots it changed (concentrated in the endgame) are a wash in head-to-head strength. **But the audit also shows there is nothing redeeming about the change** — B512 is no closer to the deep heuristic, so there is no upside to the under-fit, only the (head-to-head-invisible) loss of B256's specific edge over the parent. This supports treating B512 as **"about-as-strong-but-not-better, and not validated against the fixed references"** — i.e., no reason to prefer it over the proven B256 recipe.
