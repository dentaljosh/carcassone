# Hard-Position Policy Repair — Plan

> **STATUS: CONCLUDED 2026-06-26 — DECISION A (repair fails; STOP, no games).** Pilot only
> (1620-pool, no generation). The `h3200≠h6400` target is **signal-free** (disagreement states
> are value-indifferent: Q-gap ~0.002). Results: [HARD_POLICY_REPAIR_RESULTS.md](HARD_POLICY_REPAIR_RESULTS.md)
> · Decision: [HARD_POLICY_REPAIR_DECISION.md](HARD_POLICY_REPAIR_DECISION.md). Stages 6/7 not run.

**Date:** 2026-06-26 · **Branch:** rod_v2_flywheel · **MEASUREMENT / DIAGNOSTIC ONLY.**
No promotion · PRODUCTION.yaml unchanged · champion unchanged · v2.9 evaluator frozen + unchanged.

This is **not** a new RoD flywheel. It is a single, narrow diagnostic repair test built on the
RoD2 autopsy ([../rod_v2_flywheel/autopsy/ROD2_AUTOPSY_REPORT.md](../rod_v2_flywheel/autopsy/ROD2_AUTOPSY_REPORT.md)).

## The one question

> Can explicit **h6400-labeled hard-position exposure** repair the policy failure the RoD2 autopsy
> diagnosed — namely that on `h3200≠h6400` disagreement states the prior puts mass on *neither*
> ruler's move ~77.5% of the time and shows **no movement toward h6400** across iters?

Answer that *first*. Full-game strength is secondary; the first success criterion is movement on the
**exact failed metric** (held-out `h3200≠h6400` disagreement states), not training loss.

## What the autopsy established (the baseline failure)

- iter04 vs h6400_v2.9: WR .463, Elo −26.1, paired z −4.67 (n=400) → clearly below h6400.
- iter04 vs h3200_v2.9: WR .492, Elo −5.2, paired z −1.57 (n=200) → ~h3200 strength.
- Disagreement-subset prior lean toward h6400 (n=111): RoD1 −0.009 → iter04 −0.063 → iter06 −0.027
  (no movement). `P(neither) ≈ 0.775`. Endgame prior agreement collapses to ~0.10–0.13.

Diagnosis: the self-play flywheel does not naturally teach the policy the deep-search distinctions.
Hypothesis under test: maybe it *can* learn them if explicitly exposed (supervised) to them.

## Frozen substrate (unchanged)

v2.9 leaf "Bmild_cap8": curve `(-8,-4,-1,0,2,3,4,5)` replaces flat meeple_k, `bonus_cap=8`,
`opp_cap=8`, 3-open (`DROP_THREE_OPEN=0`), `config_hash 7fc930b82801cb43`. Rulers
`h3200_v2.9` / `h6400_v2.9` / (optional) `h12800_v2.9` = HeuristicMCTS@{3200,6400,12800} on this leaf.

## Stages

- **Stage 0 — dataset** (`scripts/rod_v2/repair/mine_label.py`). State source = the fixed 1620-root
  multiphase pool (`measurement/deeper_search_ruler/multiphase_positions.jsonl`, seed+ply+checksum,
  greedy-selfplay, spans opening→endgame). Each root: run h3200 (classify) + h6400 (teacher), tag
  `disagree = h3200_top ≠ h6400_top`. Hard = disagreement states. Split hard 70/15/15
  train/val/test (deterministic, split-seed 7). Ordinary (agreement) states kept for the P2 mix +
  the Stage-5 regression set. **Pilot = the 1620 pool (no generation, ~450 hard expected).** If the
  pilot shows signal, *scale*: generate ~6k more roots (`gen_multiphase_positions.py`) → minimum
  viable train≥2000 / val≥500 / test≥500, labeled across local+laptop.
- **Stage 1 — label.** Policy target = h6400 visit distribution (clipped to the snapshot legal mask),
  stored as the 2511-d policy vector in train_iter.py-format npz. Labels are FIXED (never on-the-fly).
  (Optional h12800 on a subset later to validate h6400 label stability — deferred, not required.)
- **Stage 2 — baseline** (`hardset_eval.py`). RoD1_v29 / iter04 / iter06 prior metrics on the held-out
  hard **test** set: top1 / top3 / rank / KL(h6400‖prior) / lean / P_neither, + endgame and close-score
  splits. Reproduces the failure baseline.
- **Stage 3 — repair** (`scripts/train_iter.py`, policy-only). Warm from the best RoD checkpoint
  (iter04 / iter06). POLICY-only fine-tune to the h6400 visit dist: `--aux-weight 0
  --value-loss-weight 0` (value & ownership losses zeroed; value target unchanged, just unweighted).
  Variants, first wave small:
  - **P0** no-train baseline (Stage 2).
  - **P1** policy-only fine-tune on hard states, low LR.
  - **P2** P1 + ordinary-state mix (50–70% hard / rest ordinary) to prevent forgetting.
  - **P3** P1 from RoD1_v29 (instead of iter04/06) if cheap.
- **Stage 4 — post eval.** Same `hardset_eval.py` on the repaired net, held-out hard **test** set.
  **Primary pass/fail (must move materially):** lean toward h6400 ↑ · P_neither ↓ (below 0.775) ·
  top3-contains-h6400 ↑ · endgame agreement no longer collapsed at 0.10–0.13. Useful targets:
  top1 +10pp, top3 +15pp. If the policy does **not** move on held-out hard states → STOP (outcome A:
  the setup cannot absorb the signal); do not run games.
- **Stage 5 — regression.** On ordinary states (h3200=h6400): policy entropy, agreement with both
  rulers, legality sanity. If hard accuracy rises but normal policy collapses → outcome D.
- **Stage 6 — game screen (ONLY if Stage 4 passes).** repaired vs h6400_v2.9 / vs h3200_v2.9 / vs
  original iter04/06, n=100–200, paired. local+laptop + rust orch, high W. Do not overread.
- **Stage 7 — decision** (`HARD_POLICY_REPAIR_RESULTS.md` + `HARD_POLICY_REPAIR_DECISION.md`):
  - **A** policy doesn't move on held-out hard states → setup can't absorb h6400 signal. Stop.
  - **B** policy moves, games don't → value/search/tether is the next bottleneck.
  - **C** policy moves and games improve → flywheel lacked hard-state exposure; integrate distillation.
  - **D** policy moves but normal-state regression severe → need better mixing/regularization first.

## Hard constraints (governance)

Do NOT: change the v2.9 evaluator · change PRODUCTION.yaml · promote any checkpoint · start a new
self-play flywheel · add heuristic terms · add tools / feature channels / aux heads · judge success by
training loss alone · open curriculum/tools/random-state/aux-head ideas mid-experiment. One narrow
question only.

## Artifacts

`scripts/rod_v2/repair/{mine_label.py, hardset_eval.py}` · `measurement/hard_policy_repair/{data/,
manifest_*.jsonl, *.log, HARD_POLICY_REPAIR_PLAN.md}`. Checkpoints under
`/mnt/c/carc-shared/hard_policy_repair/` (not promoted).
