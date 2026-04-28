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

## 2026-04-27 — Batched GPU inference for Phase 4 MCTS
**Context:** Phase 4 self-play does ~200 sims × ~70 moves × N games = millions of network forward passes. Naive per-position calls would tank GPU utilization (the 5060 Ti hits 49 TFLOPS fp16 only when batched).
**Idea:** virtual-loss MCTS or leaf-collecting batch evaluation — when a leaf is selected, apply a small virtual loss so other simulations explore elsewhere; collect leaves into a batch; run a single GPU forward pass; backprop in parallel. Standard AlphaZero pattern.
**Why deferred:** Phase 4 design work. Architecture choice will fall out of measuring batch-utilization once Phase 3 has a working network.

---

## 2026-04-27 — Rent Threadripper / EPYC for Phase 4 long runs
**Context:** Phase 1 quick-bench showed Phase 4 is CPU-bound (game simulation dominates, GPU is not the bottleneck). On the 5800X, 50 iterations = 25-50 hours; 200 iterations = 1-2 weeks.
**Idea:** Smoke-test Phase 4 locally for the first 5-10 iterations to confirm the training loop is healthy (ELO monotonically increasing, no policy collapse, etc.), then rent a Threadripper Pro 7965WX (24C/48T, ~5x our 5800X) or 64-core EPYC on RunPod or Vast.ai for the long run. Estimated cost: $30-50 for a 50-iteration run, $100-200 for 200 iterations. GPU-only rentals (A100/H100) aren't useful here — our bottleneck is CPU game-sim, not GPU network forward passes.
**Why deferred:** premature until Phase 2 + 3 are done and the local smoke-test has validated the loop. Want to be sure we're renting compute to do the right work before paying for it.

## Promoted to project

<!-- When an idea graduates to actual work, move it here with a link to the relevant phase or PR. -->

(none yet)

## Killed

<!-- Things Joshua explicitly decided not to do, with reasoning. Keep these so we don't re-litigate. -->

(none yet)
