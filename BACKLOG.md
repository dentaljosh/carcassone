# Backlog

Parking lot for ideas, distractions, and things-to-do-later that come up during work on the main project. **Do not action items in here without explicit approval from Joshua.** This is a capture-and-forget tool, not a TODO list.

When something goes in: timestamp it, one-line description, why it's not being done now.
When something comes out: either it gets promoted to an actual phase, or Joshua deletes it.

## Captured ideas

<!-- Format:
## YYYY-MM-DD — [short title]
**Context:** what we were doing when this came up
**Idea:** what the thing is
**Why deferred:** out of scope / premature / nice-to-have / needs Joshua decision
-->

## 2026-05-10 — Phase 4 v2 recipe fixes (after the chain-ELO-vs-anchor regression finding)

**Context:** The 30-iter sanity run on `phase-4-selfplay` regressed -330 ELO vs `warmstart_canonical` while chain ELO climbed +612. See DECISIONS.md "2026-05-10 — Chain-vs-prev ELO discredited as standalone metric". Quarantined those checkpoints; Phase 4 is re-opened.

**Recipe-fix shortlist (needs a plan-mode session before implementing — don't action piecemeal):**

1. **Floor warmstart-mix at ≥0.3 throughout.** Right now `run_phase4_smoke.py --warmstart-mix-schedule "1.0,0.7,0.4,0.0"` drops to 0 at iter 3. Change default to `"1.0,0.7,0.4,0.3"` so the heuristic-labeled distribution stays as a 30% anchor in every iter's training mix.
2. **K=10 → K=30 replay-buffer window** (`run_phase4_smoke.py --window`). More history dilutes noise; ~1 GB extra disk at 200 iters (trivial).
3. **Anchor-gate per iter.** After training iter N, run a 10-game match vs `warmstart_canonical.pt` at sims=50 (~3 min). If win-rate ≥ 40%, accept the new checkpoint as warmstart for iter N+1; else reject and restart iter N+1 from iter N-1's checkpoint. Effectively a regression-stop. Needs a new `--anchor-gate` mode in `run_phase4_smoke.py` plus an "anchor_gate_log.json" alongside `elo_log.json`.
4. **Bump eval games per chained head-to-head from 20 → 50** so single-game swings don't show as ±35 ELO. Independently useful even if the chain stays as a supplementary metric.

**Verification before re-launching:** rerun the 5-iter smoke (same params as 2026-05-03 but with the four fixes). Acceptance is now: anchor wins-vs-warmstart at iter 0 ≥ 30%, monotonically non-decreasing through iter 4, NOT chain ELO trend.

**Why deferred:** needs a plan-mode session to sequence the four fixes (some are CLI defaults, some are real code in `train_iter.py` / `run_phase4_smoke.py`), and to define the new acceptance bar precisely. Don't piecemeal.

---

## 2026-05-08 — fp16 / autocast inference for NeuralMCTS evaluator — LANDED 2026-05-10

`use_fp16` flag added to `evaluators.make_{single,batch}_evaluator` (commit `cc9cc90`); CLI plumbed through `run_selfplay_iter.py`/`eval_iter_head_to_head.py`/`run_phase4_smoke.py` (commit `fe8ede3`); `scripts/bench_fp16_vs_fp32.py` added for numerical-agreement + wallclock check. Default off until benched on a meaningful (non-quarantined) checkpoint.

---

## 2026-04-27 — In-place state mutation for MCTS rollouts (CONFIRMED bottleneck)
**Context:** Game.get_next_state calls StateUpdater.apply_action which deepcopies the entire CarcassonneGameState every step. Phase 2 measurement (post-adjacency-fix): each MCTS sim's rollout (~165 random moves) takes ~600ms total, of which ~70% is in the deepcopy. With s=50 sims/move and ~165 game moves, that's ~80 min/game in pure copy cost.
**Idea:** add `Game.apply_action_inplace(board, action_idx)` that bypasses the engine's internal deepcopy (we already deep-cloned the engine to do this). Use only for rollouts where the state is discarded; tree expansion keeps the safe copy path. Patch StateUpdater to expose an inplace variant.
**Why deferred:** Phase 2 acceptance can run at lower s (s=10 vs s=50) to compensate. Implementing this BEFORE Phase 4 would let us run at s=200+ during self-play, which is what AlphaZero needs.
**Expected speedup:** 3-5x on MCTS sim cost.

---

## 2026-04-27 — LRU bound on legal-moves cache
**Context:** The opt-in cache on `Game(enable_legal_moves_cache=True)` is unbounded. Per-search clear_caches() keeps memory bounded in well-behaved MCTS code, but a forgotten clear could leak memory across many searches.
**Idea:** swap the dict for `functools.lru_cache`-style bounded LRU (maxsize ~50K) so misuse degrades gracefully instead of OOM.
**Why deferred:** premature until something exposes the gap. Clear-on-search pattern is the standard MCTS idiom and unlikely to leak.

---

## 2026-04-27 — Batched GPU inference for Phase 4 MCTS — LANDED 2026-05-08
**Context:** Phase 4 self-play does ~200 sims × ~70 moves × N games = millions of network forward passes. Naive per-position calls tank GPU utilization (5060 Ti hits 49 TFLOPS fp16 only when batched).
**Implementation:** Virtual-loss / leaf-collecting batch evaluation in `NeuralMCTS`. New `batch_size`, `batch_evaluator`, `virtual_loss` constructor params; default `batch_size=1` preserves the existing serial path. Vloss is applied in **parent's perspective** (not the textbook "node's own perspective") so PUCT actually drops in alternating-player trees. Plumbed through `selfplay.play_one_selfplay_game` → `run_selfplay_iter.py --batch-size N` → `run_phase4_smoke.py`. Tests in `test_neural_mcts_virtual_loss.py` (visit-count totals, eval-call accounting, vloss-undo invariants, diversification).
**Measured:** 1.44× single-process speedup at `batch_size=8` against the warmstart canonical checkpoint (48.9s → 34.0s for one 166-position self-play game on RTX 5060 Ti). Multi-worker speedup needs a free PC to measure.

---

## 2026-04-28 — Phase 3 production-prerequisites — DONE (moved to DECISIONS.md)
All three items landed in this session:
- Scalar normalization (features.py: divide by 7/100/50/85)
- Board encoding richness: 40 → 78 channels with internal-topology + per-side meeples
- Streaming/IterableDataset trainer (warmstart.py.make_streaming_dataset + scripts/train_warmstart.py)
108 tests pass. See DECISIONS.md "Phase 3 production prerequisites landed" for full detail.

## 2026-04-28 — encode_board() scans full 35×35 board
**Context:** Reviewer pass 2026-04-28 (round 2). `board_repr.encode_board` iterates every cell of `state.board` (1225 cells) on every encode call, even though the centered window is 25×25 and only ~80 tiles are placed mid/late game. Edge/internal blocks are also recomputed per-tile per-call instead of memoized.
**Idea:** scan only the bounding box of placed tiles (or the window bounds), and memoize tile edge/internal encodings keyed by `(tile.description, rotation_signature)`. Probably 3-5x speedup at gen scale.
**Why deferred:** not on the hot path for training (encoding happens once per position before .npz save). Hot path is generation; benchmark first to confirm encoding is meaningful fraction of gen cost before optimizing.

## 2026-04-28 — Many tiny .npz files: I/O-noisy at 500K+ scale
**Context:** Reviewer pass 2026-04-28 (round 2). 100K positions = 10K .npz files, ~100KB each. Streaming reads one file at a time → lots of file opens. Fine for 100K (10K files); at 500K (50K files) the I/O becomes meaningful overhead.
**Idea:** after train/val split, optionally pack many game files into split-preserving shards (e.g. 100 games per shard → 100 shard files instead of 10K).
**Why deferred:** premature for current scale. If we do scale to 500K and observe DataLoader stalling, this is the fix.

## 2026-04-28 — Phase 4: don't reuse NeuralMCTS.best_action for self-play target generation
**Context:** External review (2026-04-28). Tournament/inference selection picks the highest-Q (with N tiebreak) child. AlphaZero self-play training-target generation samples from the visit-count distribution with temperature (τ=1 first ~15 moves, τ=0 after). Reusing best_action for self-play would give degenerate, deterministic policy targets and kill exploration.
**Action:** Phase 4 plan-mode session must call out a separate `select_for_training(temperature)` API on NeuralMCTS that samples from `visits ** (1/τ)`.
**Why deferred:** not relevant for Phase 3 acceptance (tournament-style play), only for Phase 4 self-play.

## 2026-04-28 — Split string_representation into legal-move key vs MCTS state key
**Context:** External review pass 4 (2026-04-28). `string_representation` omits full deck order, last_river_rotation, and abbots/big-meeple pools. For our in-scope deterministic games, collision risk is low in practice, and the engine doesn't use those out-of-scope pools at all. But for general-purpose MCTS state-keying (especially Phase 4+), it's incomplete.
**Idea:** split into two keys:
- `legal_moves_key(board)` — visible legality state only (what the cache needs)
- `mcts_state_key(board)` — full deck signature, last_river_rotation, all pools, full placed-tile orientations
**Why deferred:** correctness for Phase 3 unaffected. For Phase 4 self-play and Phase 5 analyzer, this should land along with the chance-node / determinization work.

## 2026-04-28 — River edge-case regression tests
**Context:** External review pass 4 (2026-04-28). `RiverRotationUtil.get_river_rotation` can implicitly return None around river start/straight cases. Coverage is thin. Specific cases to test:
- River start tile placed at starting_position
- River end tile placed (last river segment)
- Disallowed repeated bend sequence (engine should refuse)
- last_river_rotation correctly tracked across multiple river placements
**Why deferred:** these are correctness concerns rare in random play but may bite during the production warm-start gen. Targeted tests, ~1 hour.

## 2026-04-28 — Phase 5 deck determinization for analyzer
**Context:** External review (2026-04-28). Current MCTS uses the engine's pre-shuffled future deck (deterministic). For Phase 5 analyzer (where we DON'T know the future tile order from a real family game), we'd need POMDP-style determinization: sample N possible orderings of the remaining bag and average MCTS results. Already noted in `mcts.py` docstring.
**Why deferred:** Phase 5 problem, not Phase 3/4. Standard determinization pattern when we get there.

## 2026-04-27 — Rent Threadripper / EPYC for Phase 4 long runs
**Context:** Phase 1 quick-bench showed Phase 4 is CPU-bound (game simulation dominates, GPU is not the bottleneck). On the 5800X, 50 iterations = 25-50 hours; 200 iterations = 1-2 weeks.
**Idea:** Smoke-test Phase 4 locally for the first 5-10 iterations to confirm the training loop is healthy (ELO monotonically increasing, no policy collapse, etc.), then rent a Threadripper Pro 7965WX (24C/48T, ~5x our 5800X) or 64-core EPYC on RunPod or Vast.ai for the long run. Estimated cost: $30-50 for a 50-iteration run, $100-200 for 200 iterations. GPU-only rentals (A100/H100) aren't useful here — our bottleneck is CPU game-sim, not GPU network forward passes.
**Why deferred:** premature until Phase 2 + 3 are done and the local smoke-test has validated the loop. Want to be sure we're renting compute to do the right work before paying for it.

## Deferred — may revisit if Phase 4 stalls

These were candidate Phase 3 acceptance-iteration paths. Phase 3 closed on 2026-04-29 with v2 declared the canonical warmstart (see DECISIONS.md "Phase 3 closure"). All three are kept here in case Phase 4 reveals that the warmstart is materially holding the self-play loop back; in that case any of these could become a fast retry without re-deriving the rationale.

### 2026-04-28 — 2-ply heuristic-policy labels (sees both phases of one turn)
**Context:** External review (2026-04-28). Current `_heuristic_policy` evaluates `virtual_score(after applying TILE-action)` — it doesn't see the meeple follow-up. Many strong tile placements depend on the meeple choice, so the policy target may be miscalibrated for tile-phase positions.
**Idea:** for tile-phase labels, look 2 ply ahead: try each tile placement, then for each, find the best meeple decision (or "skip"), score the resulting state. Use that 2-ply best-score as the tile's heuristic value.
**Status (2026-04-29):** Already plumbed via `--heuristic-lookahead 2ply` in `warmstart.py` and `scripts/generate_warmstart_smoke.py`. Untested at scale. Smoke at low position count produced near-identical policies to 1-ply (not yet diagnosed). To revisit: regen 100K with `--heuristic-lookahead 2ply`, retrain with same hyperparameters, run T1 head-to-head against v2.
**Cost if revisited:** ~3-4× generation slowdown (so ~6-12h for 100K depending on perf), then ~30 min train + ~80 sec T1.

### 2026-04-29 — MCTS-label fallback (Option C from the original Phase 3 plan)
**Context:** Phase 3 smoke comparison (2026-04-28) showed Option D (heuristic-only at 100K) won 24.7× over Option C (MCTS-labeled at smaller scale) on a wins-per-hour-of-gen basis, so Option D was promoted to production. Option C was never run at production scale.
**Idea:** generate ~50K positions via MCTS s=50 visit distributions for policy targets (still using virtual_score for value targets). MCTS-derived policy targets capture multi-ply lookahead structure that 1-ply heuristic targets miss; the trade-off is ~25× more compute per position.
**Status (2026-04-29):** estimated ~26 hours for 50K positions on 16-worker Pool. Skipped during Phase 3 closure on the rationale that label-engineering substitutes for the self-play loop and v3's failure suggests we've hit a substitution ceiling. May revisit if Phase 4 self-play converges below v2 strength (i.e., the warmstart is confirmed too weak even for self-play to escape).
**Cost if revisited:** ~26h gen + ~30 min train + T1 + T2. Whole experiment ~2 days end-to-end.

### 2026-04-29 — c_puct sweep continuation
**Context:** Phase 3 Plan B started a c_puct sweep over {0.5, 1.5, 3.0, 5.0} but only the c_puct=0.5 group ran (12 games at s=50/s=50, neural 6/12 = 50%). Other three groups never ran (sweep script exited after first group).
**Idea:** finish the sweep — run c_puct ∈ {1.5, 3.0, 5.0} at the same 12 games each. If any variant lands ≥58% (7/12), re-run T2 at production sims (s=50/s=100) with that c_puct.
**Why deferred:** the c_puct sweep was a tuning knob, not a label-quality fix. Phase 3 closure decision is that label engineering is hitting diminishing returns; tuning NeuralMCTS hyperparameters around v2's policy probably can't lift T2 from 31% past 55%. May revisit if Phase 4 self-play needs an explicit NeuralMCTS hyperparameter search at the start of the loop.
**Cost if revisited:** ~1.5h for the remaining three groups. Diagnostic only; no model changes.

## Promoted to project

<!-- When an idea graduates to actual work, move it here with a link to the relevant phase or PR. -->

(none yet)

## Killed

<!-- Things Joshua explicitly decided not to do, with reasoning. Keep these so we don't re-litigate. -->

(none yet)
