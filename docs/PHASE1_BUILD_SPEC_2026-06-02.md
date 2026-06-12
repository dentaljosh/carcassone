# PHASE 1 BUILD SPEC — 2026-06-02 (DRAFT, awaiting Joshua approval)

Concrete build plan for the post-audit "turn on the actual engine" work. Grounded in a
direct read of the current code (not the audit's secondhand summary). Read with
[CORRECTION_PLAN_2026-06-02.md](CORRECTION_PLAN_2026-06-02.md) (the why) and
[research/foundational_audit_2026-06-02.md](research/foundational_audit_2026-06-02.md).

**Status of prerequisites:** Phase 0 DONE (C1 farm bug, C2 MCTS bug + PUCT-selection residual,
River dropped — all committed & verified). This spec is what comes next.

> **Outcome (addendum 2026-06-12):** Stage A EXECUTED (stamped inline below). Stage B EXECUTED
> → **no-go** (value-blend degrades search). Stage C **KILLED** — the C4a representation-probe
> refutation removed its premise (see [CEILING_AND_C4C6_2026-06-04.md](CEILING_AND_C4C6_2026-06-04.md)).
> Successors: [VALUE_LOSS_ATTACK_2026-06-05.md](VALUE_LOSS_ATTACK_2026-06-05.md) → [ATTEMPT2_SPEC_2026-06-08.md](ATTEMPT2_SPEC_2026-06-08.md) → [DEEPER_TEACHER_SPEC_2026-06-11.md](DEEPER_TEACHER_SPEC_2026-06-11.md).

---

## The key reframe vs the original plan: stage by QUESTION, cheapest-informative-first

The correction plan said "batch C3+C4+C5+C6+C7+C8 into ONE retrain (pay it once)." That's
compute-optimal but science-poor. The review showed **C4 (representation planes) is the biggest
build (~1 day) and is independent of whether C3 (value-head-in-loop — the actual root cause F-B1)
even helps.** So we test the cheap root-cause lever FIRST, then invest in the expensive
representation work only if it pays. One retrain per *question*, not one retrain total.

**Ground truth confirmed by code read:**
- Production self-play hardcodes `--leaf-eval v2_5` (`run_pathb_cluster_loop.sh:283`) → the net
  value never drives a move (F-B1 real). `leaf_eval=nn` + `value_blend` knobs already exist & wired.
- The loop warm-froms `iter_(N-1)` UNCONDITIONALLY (`:277`); the anchor-gate is **advisory**
  (`:311`) — used only for the plateau stop, never to accept/reject. BUT `best_iter` tracking +
  `confirm_gate` (verdict-n) already exist → C7 is a ~20-line shell change, not a build.
- `board_repr.py` = 78 documented channels. Adding input planes changes net input width → fresh
  warmstart. Ownership infra in `aux_targets.py` is TERMINAL-only (training targets) → C4 needs a
  new LIVE-board ownership/connectivity computation.
- Value target `tanh(diff/15)` at `selfplay.py:300`; modes `score_diff`/`wl`. Exploration
  `dirichlet_alpha=0.3`, `temp_threshold=15` (`run_selfplay_iter.py:378-380`), both CLI-exposed.
- No symmetry augmentation anywhere in the data loader (`warmstart.py`).

---

## STAGE A — No-retrain work (cheap; do first; re-establishes measurement on the new game)

Everything here is unit-testable or eval-only — NO multi-hour self-play. All of it is owed anyway.

### A1. Re-baseline measurement on the bug-fixed, base-only game — 🔵 RUNNING (2026-06-02)
- **Why:** C1 changed scoring, C2 changed search, River is gone → every prior elo/cap/c_puct
  number was measured on a different game. We are flying blind until we re-anchor.
- **Do:** re-run the HeuristicMCTS ladder reference and the iter_11 vs HeuristicMCTS anchor at the
  new game (n=400, sims=200, base-only). Establishes the new "where we actually are" number.
- **Status:** n=400 3-box run live (`/home/doctor/run_rebaseline.sh`, disjoint seed shards 700000–700399
  → `/mnt/c/carc-shared/rebaseline/iter_11_s200_h200_c30`). n=8 smoke was **3W/5L = 0.375** (vs +181.7
  elo on the old River/buggy game) — if confirmed, iter_11 is no longer champion on the real game.

### A2. Re-sweep v2.7 caps (owed after C1) + c_puct/FPU (owed after C2)
- **Files:** env `CARCASSONNE_V25_CAP`, `CARCASSONNE_V25_DROP_THREE_OPEN`; `c_puct`; FPU in
  `mcts.py:_select_child_puct` (currently unvisited child q=0; the audit's F-D-FPU wants
  `parent.Q − reduction`).
- **Do:** bracket each ≥3 points (per `bracket_hyperparams` rule), n=100 screen → n=400 verdict on
  the winners. Write to `experiments/results.csv` with manifests.
- **Note:** FPU change is a code edit to `_select_child_puct` (the same hot path we just touched) —
  small, A/B it.

### A3. Symmetry augmentation (C5) — ✅ DONE 2026-06-02
- **Built:** `board_repr.rotate_board_repr_90` (+ `_batch`), `action_space.rotate_action` +
  `action_rotation_perm`, `warmstart.rotate_dataset_90` / `augment_with_rotations`, wired into the
  streaming loader (`make_streaming_dataset(augment_rotations=)`) + `train_iter.py --augment-rotations`
  (default OFF). 90° only; reflection deferred (curved roads).
- **Verified:** 16 tests (`tests/test_symmetry_aug.py`) — round-trip ×4==identity, hand-geometry
  direction, tile-rotation delta matched to the edge-channel perm, policy mass preserved, streaming
  yields 4× rows with the flag. **To USE: pass `--augment-rotations` at the Stage-B retrain.**

### A4. Exploration knobs (C8)
- **Files:** `run_selfplay_iter.py:378-380` defaults → `dirichlet_alpha 0.3→0.53` (measured),
  widen `temp_threshold` past the opening. Pure config; A/B during the Stage-B retrain.

### A5. Conditional gate (C7) — keep best, don't random-walk
- **pt1 ✅ DONE 2026-06-02:** the loop script is now version-controlled at
  `scripts/run_pathb_cluster_loop.sh` (md5-verified snapshot; running copy stays in `~/` per the
  share chicken-egg). Confirmed against real code: warm-from iter_(N-1) is unconditional (:285), the
  gate is advisory (:318), but `best_iter` + `confirm_gate` machinery already exists (:355,:148) → the
  logic change is small.
- **pt2 PENDING (Stage-B wiring):** change `warm_from` to the **best-so-far** checkpoint (track
  `best_ckpt`); adopt iter N as parent only when it beats best at **verdict-n** (`confirm_gate`) vs a
  FIXED, ideally OUT-OF-LINEAGE reference (HeuristicMCTS, per `anchor_before_scaling`). Validated only
  when the loop runs → do it in the Stage-B pass, not blind.

### A6. De-saturated value target (C6) — add the mode now, use it in Stage B
- **File:** `selfplay.py:300` + `run_selfplay_iter.py` `--value-target`. Add a `score_diff_wide`
  (`tanh(diff/40)`) and/or `wl_bce` mode. Re-derive the corr reference. No retrain to add the mode.

**Stage A exit:** all committed + unit-tested; `results.csv` has fresh base-only baselines + the
re-swept caps/c_puct/FPU. NOW we know our real starting point and have clean knobs.

---

## STAGE B — The cheap root-cause retrain: does turning the value head ON help at all? (C3)

**One question:** with the bugs fixed and the game clean, does putting the learned value in the
search loop beat the v2.7 leaf — WITHOUT any new representation? This is the F-B1 test.

- **Build:** none new — flip the loop to `--leaf-eval nn` (or a `value_blend` ramp low→high),
  `--value-target score_diff_wide` (C6), exploration knobs (A4), conditional gate (A5).
  Optionally train value on deep-search root-Q targets (NOT built — defer to Stage B2 if score-diff
  targets stall).
- **Warmstart:** from scratch base-only (River gone) at the CURRENT channel/scalar width (no new
  planes yet) — fast, reuses the existing net architecture.
- **Evaluate:** independent HeuristicMCTS ladder, n=400, sims=200. Expect an initial dip (value
  head goes on-distribution) then — the question — does it climb past the v2.7-leaf ceiling?
- **Cost:** a real self-play→train→gate loop, but the SHORT version (few iters to see the trend),
  base-only (shorter games). **Bench + smoke at production knobs before the full run** (pre-flight
  rule). State ETA + pick boxes.
- **Decision gate:** if value-in-loop shows ANY upward break vs the leaf ceiling → Stage C is
  justified (representation will amplify it). If it's flat/worse even on-distribution → the ceiling
  is deeper than F-B1; reconsider before spending a day on C4.

---

## STAGE C — The representation retrain (C4): only if Stage B says go

The expensive build. Gate it on Stage B.

- **C4a Farm-connectivity INPUT planes:** new LIVE-board ownership/connectivity computation
  (reuse `FarmUtil.find_farm` flood-fill + current meeple majority — NOT the terminal-only
  `aux_targets` recorder). Project onto the window as input channels (which fields merge, which
  cities each field borders, current farm majority). ~2-3 channels. Biggest piece (~½–1 day).
- **C4b Bag-composition histogram:** per-tile-type remaining counts from `state.deck` (~24 types,
  normalized), appended to scalars. ~1hr.
- **C4c Open-feature completion planes:** per-cell city open-edge count / monastery neighbor count.
  ~1hr.
- **C4d Turn ON farm scalars** (`include_farm_scalars=True`) at minimum (currently OFF).
- **Impact:** changes net input width → fresh warmstart at the new width (network.py already takes
  `n_scalar_features`; confirm channel-count propagates the same way).
- **Evaluate:** same independent ladder, n=400. With C5 symmetry aug active, data efficiency ↑.

---

## STAGE D — De-prioritized (per the clairvoyance screen)
- Root-Q value targets (if Stage B score-diff targets stall) — moderate build.
- Chance nodes / determinization ensemble for value-target variance (C9) — only if value learning
  is variance-bound after C4; the screen proved it's not a search-strength lever.
- Housekeeping (C10): window-overflow instrumentation, single SCORE_NORM symbol.

---

## Risks / discipline threaded through
- **Bench → smoke → run** before every retrain at PRODUCTION knobs (base-only changes the cost
  profile; don't extrapolate old ETAs).
- **Independent reference, n=400 verdicts** — self-anchored & same-lineage anchors lie
  (`anchor_before_scaling`). The gate ref should be HeuristicMCTS (out-of-lineage), not iter_11.
- **Commit the untracked loop script into the repo** as part of A5 so the gate is reviewable.
- **One lever per question** — don't co-vary C3 and C4 in one run or we can't attribute the result.
- The superhuman CLAIM is still gated by the measurement wall (HeuristicMCTS ≈ strong-amateur is
  the ceiling reference; proving superhuman needs a stronger reference — Joshua / expert humans).

## Rough effort (NOT a launch ETA — compute ETAs come after bench)
- Stage A: ~1 day of coding + unit tests + the eval sweeps (the sweeps are the wall-clock).
- Stage B: ~½ day wiring + a short retrain loop.
- Stage C: ~1 day build + a full retrain loop.
