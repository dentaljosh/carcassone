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

## 2026-04-28 — Phase 3 production-prerequisites — DONE (moved to DECISIONS.md)
All three items landed in this session:
- Scalar normalization (features.py: divide by 7/100/50/85)
- Board encoding richness: 40 → 78 channels with internal-topology + per-side meeples
- Streaming/IterableDataset trainer (warmstart.py.make_streaming_dataset + scripts/train_warmstart.py)
108 tests pass. See DECISIONS.md "Phase 3 production prerequisites landed" for full detail.

## 2026-04-28 — Heuristic policy: avoid double-deepcopy per legal action
**Context:** Reviewer pass 2026-04-28 (round 2). `_heuristic_policy` calls `get_next_state` (which deepcopies the engine state via `apply_action`) then passes the result to `virtual_score`, which deepcopies *again* before counting final scores. Two deepcopies per legal action × 20 legal actions × 10 sampled positions × 10K games is the dominant cost of generation.
**Idea:** make one owned copy per candidate (deepcopy upfront), apply the action in-place via `apply_action_inplace`, then run a mutating `count_final_scores` on that same owned copy. Should roughly halve heuristic generation wallclock.
**Why deferred:** the v2 100K regen was already mid-flight when the reviewer flagged this. Land before any future regen at >100K scale.

## 2026-04-28 — encode_board() scans full 35×35 board
**Context:** Reviewer pass 2026-04-28 (round 2). `board_repr.encode_board` iterates every cell of `state.board` (1225 cells) on every encode call, even though the centered window is 25×25 and only ~80 tiles are placed mid/late game. Edge/internal blocks are also recomputed per-tile per-call instead of memoized.
**Idea:** scan only the bounding box of placed tiles (or the window bounds), and memoize tile edge/internal encodings keyed by `(tile.description, rotation_signature)`. Probably 3-5x speedup at gen scale.
**Why deferred:** not on the hot path for training (encoding happens once per position before .npz save). Hot path is generation; benchmark first to confirm encoding is meaningful fraction of gen cost before optimizing.

## 2026-04-28 — Many tiny .npz files: I/O-noisy at 500K+ scale
**Context:** Reviewer pass 2026-04-28 (round 2). 100K positions = 10K .npz files, ~100KB each. Streaming reads one file at a time → lots of file opens. Fine for 100K (10K files); at 500K (50K files) the I/O becomes meaningful overhead.
**Idea:** after train/val split, optionally pack many game files into split-preserving shards (e.g. 100 games per shard → 100 shard files instead of 10K).
**Why deferred:** premature for current scale. If we do scale to 500K and observe DataLoader stalling, this is the fix.

## 2026-04-28 — 2-ply heuristic-policy labels (sees both phases of one turn)
**Context:** External review (2026-04-28). Current `_heuristic_policy` evaluates `virtual_score(after applying TILE-action)` — it doesn't see the meeple follow-up. Many strong tile placements depend on the meeple choice, so the policy target may be miscalibrated for tile-phase positions.
**Idea:** for tile-phase labels, look 2 ply ahead: try each tile placement, then for each, find the best meeple decision (or "skip"), score the resulting state. Use that 2-ply best-score as the tile's heuristic value.
**Why deferred:** real quality improvement for Strategy D (heuristic-only). If the smoke comparison says D wins despite 1-ply, this could be a free further gain. Defer until the smoke decides.

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

## Promoted to project

<!-- When an idea graduates to actual work, move it here with a link to the relevant phase or PR. -->

(none yet)

## Killed

<!-- Things Joshua explicitly decided not to do, with reasoning. Keep these so we don't re-litigate. -->

(none yet)
