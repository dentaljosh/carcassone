# Batch-512 Calibration — FINAL REPORT (Phase 7)

**Branch:** `rod_batch512_calibration` (from `rod_v28_continuation_probe` @ `902b747`) · **Date:** 2026-06-23
**Status banner:** ✅ COMPLETE · **MEASUREMENT / RECIPE-CALIBRATION ONLY** — no promotion, `PRODUCTION.yaml` UNCHANGED, champion still `flywheel2_champion_iter8`, v2.7 leaf bit-identical, v2.8 opt-in, no checkpoint promoted, no batch-1024, no multi-iteration flywheel.

## Verdict: **KEEP BATCH 256** for the RoD recipe

> Strength reading is **mixed/inconclusive, not a clean pass**: B512 **ties** the validated B256 head-to-head (−1.7 Elo, z=−0.41, n=400) — the under-fit washed out under search — **but it fails to beat the frozen parent** (+10.4, z=1.65, inconclusive) that *defined* the RoD-positive result, and it measurably under-trains the policy. The decision is therefore clear even though the pure strength delta is ~0: **do not adopt batch 512.** The 1.31× speedup does not justify abandoning the one validated recipe, especially since a safer speed lever exists (2-epoch batch-256 ≈ 1.5×, zero strength risk).

## Evidence (all cited)

| measurement | result | n | artifact |
|---|---|---|---|
| train speed (3-epoch) | **1.31×** (3493.6 s vs 4580.4 s); ½ the optimizer steps (12,099 vs 24,196) | — | [B512_CHECKPOINT_MANIFEST](B512_CHECKPOINT_MANIFEST.json) |
| training stability | no collapse (entropy 1.5393 vs floor 0.8731); **policy under-fit** val_pol 0.435 vs 0.270 | — | [TRAINING_CURVE_COMPARISON](TRAINING_CURVE_COMPARISON.md) |
| B512 vs frozen `ITER8_V28_PARENT` | **+10.4 Elo, paired z 1.65 — INCONCLUSIVE** | 400 | [B512_PARENT_MATCHUP](B512_PARENT_MATCHUP.md) |
| _ref: B256 vs same parent, same decks_ | +53.4 Elo, z 3.51 (decisive) | 400 | (RoD probe) |
| **B512 vs B256 (decider)** | **−1.7 Elo, paired z −0.41 — TIE** | 400 | [B512_VS_B256_MATCHUP](B512_VS_B256_MATCHUP.md) |
| root-move agreement B512↔B256 | **0.737** (more alike than either vs parent); heur3200 Δ +0.010 | 1000 pos | [BATCH_ROOT_AUDIT](BATCH_ROOT_AUDIT.md) |

**Provenance:** B512 = `rod_batch512_calibration/ckpt/iter_01_b512.pt`, sha `9cca3edf…`, code `704c0de`, warm-from iter8 (`0d355002…`), **dataset fingerprint `61a12d76` = identical to B256** (only `--batch-size` differs; verified). B256 ref sha `a8b824df…`.

## The seven questions

**1. Wall-clock speedup in the actual RoD recipe?** **1.31×** for the full 3-epoch train (58.2 vs 76.3 min). Per-batch time grows 1.53× but batch count halves → net ~1.3× (the latency-bound "fewer sync round-trips" lever saturates fast once GPU compute dominates). B512 does exactly **half** the optimizer steps.

**2. Does B512 train stably?** **Yes — no collapse** (entropy 1.5393, well above floor; monotone losses; clean single run). **But the policy head is under-converged:** val_pol plateaus at ~0.435 vs B256's ~0.270 (+61%), stable across all 3 epochs — the direct, expected consequence of halving the gradient steps at fixed LR. Value head unaffected (corr +0.4115 vs +0.4126).

**3. Does B512 beat frozen `ITER8_V28_PARENT`?** **No, not credibly.** +10.4 Elo / paired z 1.65 (n=400) is below the 2σ bar — we cannot confirm B512 > parent. On the **identical decks**, B256 beat the same parent by +53.4 / z3.51. B512 retains only ~1/5 of B256's margin over the parent.

**4. Does B512 match or beat the successful B256?** **Matches — a statistical tie.** Direct head-to-head −1.7 Elo / paired z −0.41 (n=400), point estimate converging on 0 (−6.9 → −1.7 as n doubled). Root agreement 0.737 confirms they play substantially alike. **So the val_pol under-fit did NOT cost head-to-head strength** — MCTS@200 search laundered the less-converged priors (per the project's "policy precision ≠ play strength").

**5. Does B512 change root behavior suspiciously?** **No.** It plays 73.7% like B256 (more than either plays like the parent), entropy is uncollapsed, and its heuristic agreement is flat (Δ +0.010 vs B256). The under-fit = a *less-converged version of the same policy*, with divergence concentrated harmlessly in the endgame. Nothing pathological — but nothing redeeming either (no move toward the deep heuristic).

**6. Future RoD flywheel: batch 256, 512, or defer?** **Batch 256.** Even though B512 ties B256 head-to-head, three things block adopting it: (a) it **fails the parent gate** — the parent-beating is the defining RoD-positive result, and a recipe that doesn't reproduce it is unvalidated; (b) it **under-trains the policy**; (c) **non-transitivity risk** — B512 lost B256's edge over a *fixed external reference* (the parent), and it is **untested against the heuristic ruler** where B256 reached parity (n=800); a net that's "equal head-to-head but weaker vs fixed references" may underperform the ruler too. The 1.31× speedup is modest and dominated by a **safe alternative: 2 epochs @ batch 256 ≈ 1.5×** with zero strength risk (val loss was already flat by epoch 2 for B256).

**7. If 512 were accepted — restart from frozen iter8/B512, or continue from B256?** **N/A (rejected).** For the record, were 512 ever wanted for speed, the correct path is **not** this naive same-LR swap (which under-trains): it would need an **LR-rescaled batch-512 variant** (a separate, labeled follow-up — out of scope here), validated to *beat the parent*, then a **fresh clean lineage from frozen iter8**, treating B256 `RoD_iter_01` as the validated pilot (never a mixed-batch lineage).

## Honest caveats
- **B512 is not *clearly worse* — it ties B256 head-to-head.** "Keep 256" is a decision under a validation gate (fails to beat parent) + a risk argument (untested vs ruler) + a cost argument (modest speedup, safer alternative), not a measured head-to-head strength loss. The true direct gap is within ±~12 Elo (1σ, n=400).
- The non-transitivity (parent margins +10/+53 vs head-to-head tie) is itself a **real, ~41-Elo result** corroborating the project's "parent-relative Elo is a non-transitive proxy" finding — useful beyond this calibration.
- Strength here is measured against the heuristic-family leaf only; **no external/human anchor** — nothing in this branch bears on the superhuman question.

## Recommended lineage plan
- **Keep batch 256** for any serious RoD continuation / flywheel. If speed is needed, drop to **2 epochs @ batch 256** (safe ~1.5×) before considering a batch change.
- A properly **LR-rescaled batch-512** is the only path worth a future look, as a labeled speed variant that must clear the parent gate before adoption — not pursued here.
- `B512` (`iter_01_b512.pt`) is retained as a measured calibration artifact (NOT a champion, NOT promoted). Production + `PRODUCTION.yaml` + champion unchanged; v2.7 frozen.
