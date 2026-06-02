# CORRECTION PLAN — 2026-06-02

Master plan to fix everything the foundational audit found. Read with
[docs/research/foundational_audit_2026-06-02.md](research/foundational_audit_2026-06-02.md)
(the evidence) and STATUS.md (live state). This is the path forward; supersedes the old
"residual leaf / afterstate / pivot" NEXT block.

## What changed (why this plan exists)
6 weeks of leaf-tuning treated a *symptom*. A 6-agent audit (2026-06-02) found the real story:
the learned value — the engine of AlphaZero — was (1) never in the search loop, (2) taught by a
clairvoyant teacher, (3) on a **corrupted reward** (farm double-count) and **corrupted policy
targets** (MCTS transposition double-count), (4) through a representation **blind to farms and the
bag**, (5) on un-augmented, saturated-target data, (6) in a loop that doesn't keep good iters. The
v2.7 leaf masked all six at strong-amateur. The clairvoyance screen (n=76, 0.474, dead even) proved
future-sight is NOT a strength lever → the chance-node rebuild is DEMOTED.

## Sequencing principle
Bugs that corrupt reward/targets gate EVERYTHING — fix + verify them first (no retrain needed to
verify the fix; verify by direct scoring/visit checks). Then the strength levers (value-in-loop +
representation), which require a retrain. Then data-quality multipliers. Chance handling last.

Each strength change needs a retrain to evaluate → batch them so we retrain ONCE, not six times.
Evaluate every strength claim on the INDEPENDENT HeuristicMCTS ladder at n=400 (not self-anchored).

---

## PHASE 0 — Correctness bugs (cheap, verify WITHOUT retrain, gate everything) — ✅ DONE 2026-06-02

Both bugs fixed + verified without a retrain; full test suite green (323 passed). River
also dropped here (folded forward from Phase 1's scope decision — Joshua confirmed). Carry-over:
the two re-sweeps below (v2.7 caps, c_puct/FPU) still owed, do them alongside the retrain prep.

**Post-fix review (2026-06-02, 3 parallel agents — reviewer + 2 explore):** no new critical
bugs; agents independently re-verified the negamax signs, canonical form, action encode/decode
round-trip, and terminal scoring (the audit's "CORRECT" list holds). Findings:
- **F-B1 CONFIRMED (was in doubt).** `run_selfplay_iter.py`'s `--leaf-eval` argparse *default*
  is `nn`, but the production loop `run_pathb_cluster_loop.sh:283` explicitly passes
  `--leaf-eval v2_5` for self-play (and `v2_5` for every eval at :149/:217/:317). So prod
  self-play really did run the v2.7 leaf — the net value never drove a move. Root-cause intact.
- **C2 residual [OPEN DECISION]:** the C2 fix covers the training *target* (`root_visit_distribution`)
  and `best_action`, but `NeuralMCTS._select_child_puct` still scores transposition-collided
  actions separately in the in-search PUCT argmax (pre-existing; corrupts search *exploration*,
  not training *data*). Clean fix is invasive (expansion-time state-dedup + prior-summing in the
  hot path) and changes search behavior → re-validate. Decide: fix now (retrain validates it) vs defer.
- **C7 line-number drift:** the plan's C7 offsets (277/311/140) predate the current untracked loop
  script. Real gate = the anchor eval at `run_pathb_cluster_loop.sh:317`; whether it ever REJECTS
  (vs advisory) must be confirmed during the Phase-1 build, not assumed.
- **Plan infra reality (agent 2):** ownership planes exist only as AUX TARGETS (not inputs);
  farm-connectivity input planes, bag histogram, and city-open-edge planes do NOT exist yet;
  `value_blend` knob exists + wired; root-Q value targets NOT built (only final-score). Size the
  Phase-1 build accordingly.

### C1 [BLOCKER] ✅ DONE — Farm scoring double-count
- **File:** `engine/wingedsheep/carcassonne/utils/points_collector.py:284-299` (`count_farm_points`);
  `engine/.../objects/city.py` (City has no `__eq__/__hash__`).
- **Fix:** dedup touched cities by `frozenset(city.city_positions)` (mirror virtual_score_v2.py:348);
  add value `__eq__/__hash__` to `City` as defense-in-depth.
- **Verify (no retrain):** re-run the farm-discrepancy check (buggy vs content-deduped) over ~150
  games → expect 0 mismatches after fix. Audit measured 17% of farms wrong pre-fix.
- **After:** RE-SWEEP the v2.7 caps (CARCASSONNE_V25_CAP, drop-3-open) — a scoring-bug fix shifts
  hyperparam optima (standing rule). The whole v2.7 leaf changes when this lands.

**C1 verified:** `scripts/verify_farm_dedup_fix.py` n=150 (876 farms): NEW==REF on ALL farms,
16.3% over-scored pre-fix, 633 spurious pts removed. Re-sweep of v2.7 caps still owed.

### C2 [BLOCKER] ✅ DONE — MCTS transposition visit double-count
- **File:** `src/carcassonne_ai/mcts.py` — children keyed by action via `setdefault(state_key)`;
  `root_visit_distribution`/`select_for_training`/`best_action` read `children[a].N` per action.
  Rotationally-symmetric tiles emit ≥2 rotations → identical board → both action slots share one node
  → ~2× mass. ~20% of nodes.
- **Fix:** AlphaZero edge/node split (per-edge N/W; state-node shared only for value), OR (minimal)
  dedup actions mapping to the same child object when building the visit distribution + best_action.
- **Verify (no retrain):** collision check — assert no action pair shares a child in the visit
  vector / counts sum consistently; the 24/120 collision nodes now report correct per-move mass.
- **After:** re-sweep c_puct + FPU (C-D below), since the visit distribution the old c-sweep tuned
  against just changed.

---

## PHASE 1 — Turn on the actual engine (strength levers; ONE batched retrain)

### C3 [BLOCKER] Put the value head in the search loop
- **Why:** production self-play uses `leaf_eval=v2_5` → the net value never drives a move, so it
  can't bootstrap past the heuristic (the calibration cliff, root cause).
- **Fix:** run the self-play→train→eval cycle with the value head driving search — either
  `leaf_eval=nn` with `value_blend` ramped from low→high, AND/OR train the value head on deep-search
  root-Q targets (nn-leaf search) instead of only final score. Expect an initial strength dip; that's
  the only regime where the value head is on-distribution and can improve.

### C4 [BLOCKER] Fix the representation blind spots (net architecture input change)
- **Farm connectivity:** add LIVE feature-ownership/connectivity INPUT planes — which fields merge,
  which cities each field borders, current majority. Infra exists in `aux_targets.py` (ownership_planes,
  currently training-only); compute a current-board version + city-adjacency plane, feed as input
  channels. (A 3×3-kernel/6-block conv can't reconstruct board-spanning farms from corner dots.)
- **Bag composition:** add a per-tile-type remaining-count histogram (~24 types, normalized) to the
  scalars (derivable from `state.deck`). Without it the net can't represent draw-expectation at all.
- **Open-feature completion:** per-cell channels for city open-edge count / monastery neighbor count.
- **Minimum:** turn `include_farm_scalars=True` (currently OFF in prod global-best checkpoints).
- **Impact:** changes net input width → retrain from a fresh warmstart.

### SCOPE DECISION (fold in here): DROP RIVER? — ✅ DONE 2026-06-02 (Joshua confirmed)
Done early (in Phase 0). `Game` default `tile_sets=(BASE,)`, `DECK_NORM 85→72` (base deck = 72
tiles). Engine keeps River support for explicit callers; production self-play/eval/training is
base-only. Suite green. Caveat stands: base-only opening is MORE chaotic → deeper+sharper AND
higher-variance (the ×1.21 control variate barely dents that). Existing river-trained checkpoints
are off-distribution now (expected — Phase 1 warmstarts from scratch).

---

## PHASE 2 — Data / training-quality multipliers (do alongside the Phase-1 retrain)

- **C5 [MAJOR] Symmetry augmentation:** rotation (4×) in the data loader — `rotate_board_repr_90`
  (permute per-side edge / internal-pair / meeple-side channels + farmer corners) + `rotate_action`
  (remap policy target). Works on existing .npz, no scratch retrain. Defer reflection (curved roads
  aren't reflection-symmetric). BACKLOG-known, never done.
- **C6 [MAJOR] De-saturate the value target:** `tanh((p0-p1)/15)` pins to ±1 for 30-80pt margins →
  MSE kills mid-range calibration. Widen norm (e.g. /40) or switch to W/L + BCE; re-derive the 0.61
  corr reference. (selfplay.py:300, train_iter.py:359)
- **C7 [MAJOR] Make the loop gate keep good iters:** `run_pathb_cluster_loop.sh` warm-froms the prev
  iter unconditionally (line 277); gate is "advisory" (line 311). Accept iter N only if it beats
  best-so-far at verdict-n vs the fixed ref (confirm machinery at line 140 exists); else warm-from
  best-so-far. Stops the chain random-walk.
- **C8 [MAJOR] Exploration:** dirichlet_alpha 0.3 → measured ~0.53; widen temp_threshold (τ=1 window)
  past the opening. A/B at n≥100. (run_selfplay_iter.py:378-380)
- **C-D [re-sweep] c_puct + FPU:** FPU=0 for unvisited children is mis-scaled vs the ±0.1-0.5 Q
  range (mcts.py:664) → use parent.Q − reduction. Re-sweep c_puct after C2.

---

## PHASE 3 — De-prioritized (value-target quality, NOT strength; clairvoyance screen proved it)

- **C9 chance handling:** proper chance nodes / determinization ensemble for value TARGETS (reduce
  single-future label variance). If any non-clairvoyant search is used, first fix the `fair_chance`
  transposition-key unsoundness (deck order not in state key → determinized children merge). LOW
  priority — screen showed future-sight isn't a strength lever.
- **C10 housekeeping:** instrument window-overflow rate (silent drops, run_selfplay_iter.py:319);
  collapse the two value currencies to one `SCORE_NORM_SCALE` symbol (selfplay.py:300).

---

## Measurement caveats (thread through all of it)
- Strength verdicts vs the INDEPENDENT HeuristicMCTS ladder, n=400 (self-anchored elo lies).
- The draw-luck control variate (×1.21) is built (`diag_leaf_gate.py --with-luck`) — apply to tighten
  eval n where it helps.
- The real superhuman CLAIM is still gated by the measurement wall: HeuristicMCTS ≈ strong-amateur is
  our ceiling reference; proving superhuman needs a reference above it (Joshua → strong/expert humans).

## One-retrain discipline
C1+C2 land + verify first (no retrain). Then batch C3+C4(+River)+C5+C6+C7+C8 into ONE warmstart→
self-play→train→ladder cycle so we pay the retrain once. C9/C10 only if Phase 1-2 needs them.
