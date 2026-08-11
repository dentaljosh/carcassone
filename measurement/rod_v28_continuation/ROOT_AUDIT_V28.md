# RoD v2.8 Continuation Probe — Root-Action Audit (Phase 6)

**Question:** *how* did `RoD_iter_01` get +53 Elo over the parent — by moving its root moves toward deep heuristic search (teacher-imitation), or by a genuine policy change? Method: replay the 1000 midgame-reference positions (`measurement/midgame_reference/MIDGAME_POSITION_SAMPLE.jsonl`), compute each agent's NeuralMCTS@200 root move under the **v2.8 leaf**, compare to `heur@3200_v28`'s root move. Two runs of `scripts/midgame_reference/label_midgame.py` with `CARCASSONNE_V25_MEEPLE_K=2.0` (one `--ckpt RoD_iter_01`, one `--ckpt iter8`), post-processed by `scripts/rod_v28/rod_root_audit_postprocess.py`. Data: [`ROOT_AUDIT_V28_RESULTS.csv`](ROOT_AUDIT_V28_RESULTS.csv), [`ROOT_AUDIT_V28.jsonl`](ROOT_AUDIT_V28.jsonl). `heur@3200_v28` choices were identical across both runs (1000/1000 — clean comparison).

## Root-move agreement with `heur@3200_v28`

| subset | n | RoD agree | parent agree | Δ (RoD−parent) | RoD agree parent | parent missed ruler | RoD recovers miss |
|---|---|---|---|---|---|---|---|
| **ALL** | 1000 | **0.511** | **0.520** | **−0.009** | 0.652 | 480 | 0.142 |
| opening | 200 | 0.540 | 0.585 | −0.045 | 0.770 | 83 | 0.108 |
| early_mid | 200 | 0.570 | 0.595 | −0.025 | 0.675 | 81 | 0.185 |
| mid | 200 | 0.475 | 0.495 | −0.020 | 0.625 | 101 | 0.139 |
| late_mid | 200 | 0.480 | 0.475 | +0.005 | 0.625 | 105 | 0.105 |
| pre_endgame | 200 | 0.490 | 0.450 | +0.040 | 0.565 | 110 | 0.173 |

## Findings (answers to the Phase-6 questions)

1. **Did RoD move closer to `heur@3200_v28`'s choices? NO (net).** Overall root-move agreement is **unchanged**: RoD 0.511 vs parent 0.520 (Δ = −0.009 ≈ 0). The +53 Elo is **not** explained by imitating the deep heuristic's moves.
2. **Did it improve where the parent disagreed with the ruler? PARTIALLY but net-zero.** On the 480 positions where iter8 disagreed with heur@3200_v28, RoD matches the ruler on 14.2% — but it also *deviates* on positions the parent got right, so the net agreement delta is ~0.
3. **Did it overfit / clone the shallow or deep teacher? NO.** It did not clone heur@3200 (agreement flat) and it changed ~35% of iter8's root choices (agreement 0.652) — a genuine policy shift, not a copy of either teacher.
4. **Concentrated by phase? YES, mildly and informatively.** RoD becomes *more* heuristic-aligned in the **endgame** (pre_endgame Δ+0.040, late_mid Δ+0.005) and *less* in the **opening/early/mid** (Δ−0.045 / −0.025 / −0.020). So the re-distillation reshaped play toward the v2.8 leaf's endgame preferences (the meeple-economy term bites hardest near the endgame) while diverging from the heuristic earlier.

## Interpretation

The mechanism behind RoD's +53-over-parent (and parity-with-heur@3200) is a **genuine, phase-dependent policy reshaping under the stronger v2.8 leaf — NOT teacher-imitation of deep heuristic search.** Root-move agreement with the deep heuristic is a per-move-precision metric, and it is (again) a poor predictor of full-game strength: RoD plays a *much stronger full game* (+53 vs parent, tie vs heur@3200) while agreeing with the heuristic's root picks no more than the parent did. This corroborates the project's standing "whole-game policy ≠ per-move precision" / non-transitivity findings (`measurement/search_policy_mixing/`). The v2.8 meeple-economy term most changes endgame play, which is where RoD's choices shift toward the heuristic.

**Consequence for the verdict:** the gain is real and learned (not a clone), so it is a legitimate strength improvement — but because it is *not* convergence onto the deep-heuristic policy, there is no evidence here that further iterations would push the net to *exceed* the heuristic; iter1 reached parity by reshaping, not by out-searching.
