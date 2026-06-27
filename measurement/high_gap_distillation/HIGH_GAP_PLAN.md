# High-Contrast Decision-Signal Distillation — Plan (Stage 0)

**Date:** 2026-06-26 · **Branch:** rod_v2_flywheel · **MEASUREMENT / DIAGNOSTIC ONLY.**
No promotion · PRODUCTION.yaml unchanged · champion unchanged · v2.9 evaluator frozen + unchanged.

This is **not** a new RoD flywheel, and **not** the failed `h3200≠h6400` disagreement curriculum.
It is the experiment the hard-policy-repair **named boundary** flagged as the real open question
(see [../hard_policy_repair/HARD_POLICY_REPAIR_DECISION.md](../hard_policy_repair/HARD_POLICY_REPAIR_DECISION.md)):
define "hard" by **decision-relevance (h6400 Q-gap)**, not by argmax disagreement, and ask whether a
genuinely high-contrast teacher signal exists, is learnable on held-out states, and converts.

## The one question

> Is there enough **high-contrast, decision-relevant** teacher signal available for the current net
> to learn beyond the heuristic — and if so, does learning it on held-out high-gap states repair the
> RoD2 policy failure that self-play could not?

Answer that. Games are Stage 6, gated on held-out high-gap policy repair (Stage 5) passing.

## Why the prior experiment does NOT answer this

Hard-policy-repair (2026-06-26, decision A) distilled h6400 onto the policy on **argmax-disagreement**
states and failed because those states are **value-indifferent**: the deep teacher's top two moves
were Q-tied to ~0.002 (median 0.0007), so the argmax was noise and could not transfer (one-hot fit
memorised train to 0.775, generalised to 0.061 < baseline). The reframe: two search depths disagree
on a position *precisely when* its top moves are near-equal in value. **Disagreement ⇒ indifferent.**

This experiment inverts the selection: mine states by **large h6400 Q-gap** (the choice genuinely
matters) **where the student is wrong**, and train soft/regret-weighted targets. Whether the policy
fails *there* is untested — a different, much rarer state set (~3% of the disagreement pool had
gap > 0.02).

## Frozen substrate (unchanged)

v2.9 leaf "Bmild_cap8": curve `(-8,-4,-1,0,2,3,4,5)` replaces flat meeple_k, `bonus_cap=8`,
`opp_cap=8`, 3-open (`DROP_THREE_OPEN=0`), `config_hash 7fc930b82801cb43`. Env hard-set before any
carcassonne import (identical to the autopsy/repair harnesses).

## Definitions (Stage 0 — precise, fixed before mining)

### Teacher
- **Primary:** `h6400_v2.9` = `HeuristicMCTS@6400` on the frozen v2.9 leaf. Provides per-root, per-legal-action
  **adjusted Q** (root-player perspective; child Q negated since the move flips the mover) via the
  id-deduped root children — the same extraction validated in `probe_q_separation.py`.
- **Optional validation:** `h12800_v2.9` on a high-gap subset — does h6400's best stay best / top-3,
  and the gap stay ≥ tier, under deeper search? (teacher-stability check; not required for all states.)
- **Optional:** exact-K endgame label where already implemented and cheap (corroboration only).

### Students (the nets under test)
- `RoD1_v29` = `/mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.pt`
- `RoD2_iter04` = `/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_04.pt`  (primary repair start — healthiest)
- `RoD2_iter06` = `/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_06.pt`
- All RoD nets: 12 scalar features, 96 filters, 6 blocks, `value_global_pool=False`; encode with
  `Game(include_farm_scalars=True)`.

### Hard / useful state (NOT argmax disagreement)
A root is a **decision-relevant** training candidate when **one or more** of:
- **Q-gap** between teacher best and second-best ≥ a tier threshold (the primary axis), AND/OR
- **student regret** `Q(teacher_best) − Q(student_top)` ≥ a tier threshold (student is wrong by a
  value-meaningful amount), with
- teacher preference **stable** across h6400/h12800 (where validated),
- exact-K agreement (where applicable),
- close-score and/or late/pre-endgame relevance recorded as covariates.

The minimal trainable cell = **high Q-gap AND student wrong** (regret ≥ tier). A diffuse policy is
*correct* on low-gap states (prior finding); we train only where the teacher is decisive and the
student is not already correct.

### Q-gap tiers (calibrated to the v2.9 value scale)
Reference scale (prior measurement): full best-worst Q-range ≈ 0.17 per root; ordinary (decisive)
states' mean #1−#2 gap ≈ 0.040; disagreement states' ≈ 0.002.

| tier | threshold (Q #1 − #2, or regret) |
|---|--:|
| weak | ≥ 0.005 |
| medium | ≥ 0.010 |
| strong | ≥ 0.020 |
| very_strong | ≥ 0.040 |

### Tracked per candidate root
`teacher_best` (Q-argmax) · `ruler_choice` (best_action) · `q_best` · `q_second` · `q_gap_1_2` ·
`q_gap_1_med` · per-action adjusted Q map · top visit share · teacher entropy · per-student
{`student_top`, `student_top_q`, `regret`, `top3_contains_teacher`, `prob_on_teacher`} ·
`Q(teacher_best) − Q(h3200_top)` (where h3200 available) · phase · score_margin_abs · k_remaining ·
meeples_free · legal_n · source_agent · config_hash · git commit.

## Stages (cheapest-informative-first)

- **Stage 0 — definitions + provenance** (this doc). DONE.
- **Stage 1 — mine candidate roots.** Broad pool. **Pilot reuses the existing 1620-root replay-verified
  multiphase pool** (`measurement/deeper_search_ruler/multiphase_positions.jsonl`; phases
  endgame/pre_endgame/late_mid/midgame/opening already balanced) — zero generation. Only if the
  signal-density gate (Stage 2) passes do we *scale*: mine 25k–100k diverse roots across RoD1/RoD2
  self-play, h3200/h6400 games, weak-vs-strong, late/close-score slices, local+laptop.
- **Stage 2 — label + measure signal density** (`probe_signal_density.py` → `analyze_signal_density.py`).
  **THE GATE.** Re-label the pilot pool with h6400 to extract per-action Q (the prior run stored only
  visit dists), forward the 3 students, and tabulate per tier: count, %, %student-wrong, regret
  distribution, phase/close-score splits. **Critical question: are there enough high-gap student-wrong
  states to train and hold out?** Minimum to proceed: ≳1k held-out-testable states with Q-gap ≥ 0.02
  **or** regret ≥ 0.02 (after the scale-up), or a much larger medium-gap set with h12800/exact
  confirmation. **If density is terrible → STOP, write `HIGH_GAP_DECISION.md`, do not train.**
  → `HIGH_GAP_SIGNAL_DENSITY.md`.
- **Stage 3 — splits** (only if Stage 2 passes). Tier A (strong: gap or regret ≥ 0.020), Tier B
  (medium ≥ 0.010), Tier C (ordinary decisive stabiliser, anti-forgetting). No same-game leakage,
  fixed seeds, phase + source-agent preserved, separate endgame test slice. Soft teacher / advantage
  labels (NOT one-hot argmax). → `HIGH_GAP_DATASET.md`.
- **Stage 4 — train repair models.** Warm from iter04 (primary; iter06/RoD1 secondary if cheap).
  Regret-weighted policy distillation: `loss = CE(policy, teacher_dist) · clamp(Qgap/scale)` (or
  `clamp(regret/scale)`); optional pairwise/ranking. Mixes R0 (no-train) / R1 (70/30 hard/stabiliser)
  / R2 (50/50) / R3 (hard-only pilot) / R4 (medium+strong regret-weighted). First wave small: low LR,
  few epochs, early-stop on val regret/CE. → `HIGH_GAP_TRAINING.md`.
- **Stage 5 — held-out policy + root-search eval.** Held-out high-gap **test**: teacher top1/top3,
  rank, prob-mass on teacher best, **mean/median regret**, regret@top1, phase (esp. endgame) + gap-tier
  splits, ordinary regression. Then NMCTS@normal-sims on a subset: top1/regret vs h6400. → `HIGH_GAP_RESULTS.md`.
  **Pass = top1 ↑ materially · top3 ↑ · mean regret ↓ ≥20% · endgame not collapsed · ordinary not badly
  degraded** (useful target: top1 +10pp, top3 +15pp). If policy doesn't move → STOP, no games.
- **Stage 6 — small game screen (ONLY if Stage 5 passes).** repaired vs h6400/h3200/original iter04-06,
  n=100–200 paired, local+laptop + rust orch high W. Top-up n=400 for one best candidate only.
- **Final — `HIGH_GAP_DECISION.md`** (A/B/C/D/E): (A) policy doesn't learn high-gap → net/training can't
  absorb high-contrast signal; (B) policy ↑ NMCTS flat → value/search/tether bottleneck; (C) policy+NMCTS
  ↑ games flat → real but not strength-converting → value/search autopsy; (D) all ↑ → first evidence
  injected high-contrast signal repairs the flywheel → next phase may integrate distillation;
  (E) severe normal-state regression → fix mixing/regularisation first.

## Hard constraints (governance)

Do NOT: change the v2.9 evaluator · change PRODUCTION.yaml · promote any checkpoint · run a new RoD
flywheel · add heuristic terms · use `h3200≠h6400` disagreement alone as "hard" · use one-hot argmax as
the main training target · run games unless Stage 5 passes · open tools/curriculum/aux-head/random-game
branches mid-run. **The experiment is only this one narrow question; answer it, then stop for review.**

## Artifacts

`scripts/rod_v2/highgap/{probe_signal_density.py, analyze_signal_density.py, ...}` ·
`measurement/high_gap_distillation/{HIGH_GAP_PLAN.md, HIGH_GAP_SIGNAL_DENSITY.md, HIGH_GAP_DATASET.md,
HIGH_GAP_TRAINING.md, HIGH_GAP_RESULTS.md, HIGH_GAP_DECISION.md, qprobe/}`. Checkpoints (if Stage 4
runs) under `/mnt/c/carc-shared/high_gap_distillation/` (not promoted).
