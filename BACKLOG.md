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

## 2026-05-13 — Phase 4 v7 candidates (after v6 launch with orchestrator on)

**Context:** v6 cloud launched 2026-05-13 with iter_06.pt as warmstart + orchestrator + W=96 box at W=80 (games-capped). Workers stable at ~50% CPU each; GPU at 4-11% util. Bottleneck shifted from VRAM OOM (pre-orchestrator) to **single-process orchestrator GIL** (Python dispatcher pegged at 95% of 1 core feeding the GPU). Decisions on v7 deferred to v6's outcome (compounds vs ceiling).

### Orchestrator GIL bottleneck — RESOLVED 2026-05-13: NULL RESULT (workers are the bottleneck, not the dispatcher)
**Tested:** built `eval_server_pool.py` (commit `c34ecf9`), cloud-swept N ∈ {1, 2, 4, 8}. N=1 is optimal; N=2/4/8 strictly slower (+4% / +7% / +7%). Dequeue % climbs 64→84 as shards increase — the dispatcher was already idle waiting for requests.
**Conclusion:** workers (CPU-bound MCTS) are the bottleneck, not the orchestrator. Multi-dispatch makes it worse, not better. See DECISIONS.md "2026-05-13 — Orchestrator multi-process pool: NULL RESULT".
**What still applies:** the code is correct + back-compat; n_shards=1 is the production setting. v7 will run with `--orch-shards 1`.
**Real perf levers now:** MCTS hot-path optimization (the 50% of worker time spent on Python tree work). fp16 is NOT a lever — benched as slower (0.82× single / 0.92× batch=8) on both local 5060 Ti and cloud 5090. See DECISIONS.md 2026-05-12 "Cloud bench landed". Addressed below.

### Right-size box for games-per-iter
**Idea:** games=80 caps worker count to 80 regardless of box CPU. Current setup (48-core box, 80 workers = 1.67× oversubscription) sits in yesterday's perf valley. Two clean fixes for next run:
- **Stay at games=80**: rent 32-core boxes at 3.7 GHz (~$0.30/hr instead of $0.375/hr; 2.5× oversubscription matches yesterday's W=96 optimum on the smaller box class).
- **Stay on 48-core box**: bump games to 96 or 120, use the full headroom. Breaks the v5↔v6 recipe A/B though, so only valid for v7+ where we're free to change knobs.
**Why deferred:** v6 must hold games=80 for clean recipe comparison with v5. Right-sizing kicks in for v7.

### Train alongside self-play (async)
**Idea:** v1-v6 are all synchronous — generate iter N data, train iter N, eval. GPU sits idle during self-play (well, it does until orchestrator is fixed). Run training continuously in a separate process consuming replay buffer; check in on convergence at iter boundaries.
**Why deferred:** Big architectural change. Only sensible after orchestrator GIL fix lifts GPU util enough that async training has compute headroom.

### Bigger net — but actually understand what "bigger" means here
**Idea:** Current net is 96×6 → 7.4M params. The structural truth (discovered 2026-05-13 by counting params): trunk is only ~1M; the **policy head's `Linear(2500, 2511)` dominates at ~6M**. So scaling filters/blocks gives modest growth:
- 128×10 → 9.4M (1.3×)
- 192×14 → 15.8M (2.1×)
- 256×10 → 18.3M (2.5×)
To get into KataGo-class param counts (50M+), the lever is **widening `policy_project_channels`** (currently 4) — bumping to 32 makes flatten go from 2500 → 20000 and the policy_fc Linear from 6M → 50M. That requires a fresh warmstart and re-arch.
**Why deferred:** capacity question only matters if recipe is the bottleneck. v6 outcome arbitrates. If v6 plateaus, the cheapest experiment is 192×14 (2.1× params, only an arch-arg change, retrain warmstart). The big-headroom experiment is wider policy_project, which is more invasive.

### Hand-curated tactical probe set — measure WHAT the network learned
**Idea:** 30-50 hand-labeled positions where the right move is a known tactical play: city stealing (meeple flip via tile placement), city blocking (deny opponent's completion), cloister flooding (deny 8-neighbor close), meeple-economy endgame, farm sniping, etc. Run every checkpoint (warmstart_canonical, iter_06, v6's best) through the probe set; record `top1` and `top5` agreement with the labeled move.
**Why this matters:** anchor-wr at n=20 can't distinguish "learned to time meeples better" from "learned city stealing". Probe set can. Also: this IS Phase 5's training material — the analyzer needs a "good move bank" to explain "where you lost points". Building it isn't a v6/v7 sidequest; it de-risks Phase 5.
**Cost:** 4-6 hours of human labeling work + ~100 LoC python eval harness. Zero compute.
**Why deferred:** worth doing as soon as v6 hits its result; gates v7 decisions.

### Rule-based player — Tier 1 baseline
**Idea:** Encode the ~8-12 "fast rules" we've discussed (city quick-close, farm-threshold-with-context, endgame-meeple-deployment, cloister-EV, etc.) as a fixed-policy player. Benchmark head-to-head vs random / warmstart_canonical / iter_06 at n=50 games.
**Why this matters:** if rule-based beats warmstart_canonical ≥45% wr, the network hasn't learned anything beyond what explicit rules already capture — strong evidence the ceiling is recipe-bound, not capacity-bound. Decisive signal at ~$0.50 of compute.
**Why deferred:** orthogonal to v6 outcome but always-useful baseline. Worth running locally when there's idle time.

### KataGo-style domain features as input channels (HIGH LEVERAGE)
**Idea:** Add input planes the network would otherwise have to *learn* from sparse self-play signal:
- `tiles_remaining` (broadcast scalar plane — turns deck-counting from "hard-to-learn" into "trivial-read")
- `my_meeples_in_hand`, `opponent_meeples_in_hand`
- `is_river_phase`, `is_endgame`
- `my_dominant_farms_count`, `contested_features_count`
These would let the net learn the user's "endgame: place a meeple every move" rule in 1-2 iters instead of 50+. Closest published parallel: KataGo's territory + ladder features.
**Cost:** ~50 LoC in `board_repr.py` + retrain warmstart from scratch on bigger input dim (~3 hours local).
**Why deferred:** changes net input shape → breaks weight compatibility with all existing checkpoints. Only worth doing if we're committed to a fresh warmstart anyway (probably yes if v6 plateaus).

### KataGo-style auxiliary loss heads
**Idea:** Add prediction heads with auxiliary losses (KataGo's biggest single ablation win):
- Predict who controls each feature at game-end (territory-equivalent)
- Predict final score-delta (richer than W/L; aligns with how Carcassonne actually plays — often 1-5 point games)
- Predict tile-count-remaining when each open feature closes
- Predict meeple-deployment-rate over remaining tiles
**Cost:** ~150 LoC architecture change + retrain warmstart. The losses are auxiliary (small weight); main training objective unchanged.
**Why deferred:** invasive change. Save for after v6 outcome.

### MCTS-side domain tweaks
**Idea:** Three cheap MCTS-only changes (no network change required):
- **Endgame depth boost**: last 10 tiles use sims=400 instead of 200. ~12% more total compute, concentrates depth where mistakes are decisive.
- **Heuristic prior blending**: at PUCT root, blend `0.1 × heuristic_policy + 0.9 × neural_prior`. Cheap regularizer; prevents confident pursuit of obviously-bad late-game lines.
- **Forced-move shortcut**: tiles with only one legal placement skip the search entirely.
**Why deferred:** small changes; defer until we have a stable recipe to test them against.

### MCTS Python hot-path optimization (PROMOTED priority 2026-05-13 after orchestrator null result)
**Context:** the orchestrator N-sweep proved workers (not dispatcher) are the bottleneck. Workers spend ~50% of their time on Python MCTS tree work — selection, expansion, backup, all in pure Python with numpy. This is now the highest-leverage perf change.
**Idea:** profile `src/carcassonne_ai/mcts.py` against a 200-sim self-play game; identify the hot lines (likely PUCT selection or virtual-loss accounting); rewrite in Cython or as a single numpy vectorized pass. KataGo and Leela Chess Zero both have C++ MCTS for the same reason.
**Cost:** ~1-2 days of profiling + rewrite + tests. Compute cost negligible.
**Why deferred:** v7 will validate the data-scarcity hypothesis first (symmetry augmentation + iter_12 warmstart). MCTS perf only matters if the recipe is the right shape.
**Note:** fp16 was already benched twice and is SLOWER for our workload (autocast overhead exceeds compute savings on 7M-param net + small batch). Not a perf lever. Order: profile MCTS → v7 recipe → MCTS hot-path rewrite.

### Symmetry exploitation — CONFIRMED not used (free ~4× data on the table)
**Status:** Verified 2026-05-13: grep for `rot90|symmetr|augment` in `src/`, `train_iter.py`, `train_warmstart.py` finds zero matches (only `flip` for player-perspective handling, semantically different).
**Idea:** Carcassonne is symmetric under 90/180/270° board rotation IF you simultaneously rotate every tile's representation (the matching-edge structure is preserved). That's ~4× effective training data for free. Reflection (mirror) augmentation is trickier because some tiles aren't reflection-symmetric (curved road), requires a tile-mirror lookup — defer.
**Cost:** Moderate. Need to: (a) implement `rotate_board_repr_90()` that re-encodes the 78-channel tensor under rotation, (b) implement `rotate_action(action, k)` to remap policy targets, (c) hook into the data loader. ~200 LoC. No retrain needed — works on any existing checkpoint's training data.
**Expected payoff:** unclear. If we're data-limited (we are: 80 games × ~150 positions = 12k positions per iter), 4× augmentation could be meaningful. KataGo uses 8× (rotation + reflection) and credits it as load-bearing.
**Why deferred:** non-trivial implementation, but **cheap experiment if done right** — apply augmentation to a re-train of warmstart_canonical at 96×6 and measure anchor wr vs current warmstart_canonical. If +5pp or more, this is a high-leverage v7 ingredient.

### Probing classifiers — interpretability for the black box
**Idea:** Train small linear probes on hidden-layer activations of a trained net to predict: "how many city tiles remain in deck?", "who controls farm X?", "is this an endgame position?" If probes are accurate, the net has implicitly learned the concept. If not, it hasn't. Tells us *what* the network learned without forcing us to guess.
**Cost:** ~1 day of work, mostly tooling. Compute negligible.
**Why deferred:** doesn't fix anything, just measures. Useful diagnostic when v6 lands and we're deciding v7 direction.

### Defensive assert against accidental abbots/big-meeples
**Context:** wingedsheep engine defaults to `(FARMERS, ABBOTS)` for supplementary rules. Our `game_wrapper.py` short-circuits this, but if anyone instantiates `CarcassonneGame()` directly without going through our wrapper (e.g. in a new analysis script), they'd silently get abbots — out of scope for Phase 1-5.
**Idea:** Add a module-level assert in `game_wrapper.py` that fails loudly if `ABBOTS` ever appears in any `Game` instance passed to it.
**Cost:** 5 LoC.
**Why deferred:** no current bug; only a footgun for future tooling.

### Specialist warmstarts + league play (DOMAIN-SPECIFIC — high priority if v6 plateaus)
**Idea:** Bias the existing heuristic labeler 3 ways (roads-weight=2/cities-weight=2/farms-weight=2), train 3 warmstart nets (~30 min × 3 = ~$1.50). Run a 3-way round-robin (n=30 games, sims=50, ~2 hr) to see if specialists dominate the generalist. Two consume options:
- **Distill**: train a single new warmstart net targeting a weighted mix of the 3 specialists' outputs. New v7 starting point.
- **League**: in v7 self-play, opponents come 25% from each specialist + 25% from the generalist (vs current 100%-self play). Stops mode collapse — the loop has to play against diverse strategies, not just its own most recent self.
**Why this is different from v1-v6:** all prior recipe twiddles were generic AlphaZero knobs. This one exploits Carcassonne-specific structure (our heuristic labeler). Closest published parallel: AlphaStar's main-exploiters league. No Carcassonne-specific AlphaZero league work in the literature → genuinely novel territory.
**Why deferred:** v6 must arbitrate first. If v6 plateaus at ~65% wr, this jumps the queue.

### S-curve framing — diagnose whether v6 plateau is "same curve, further along" or "different curve, higher ceiling"
**Idea:** Jones 2021 ("Scaling Scaling Laws with Board Games") shows AlphaZero ELO-vs-compute follows clean sigmoids. The asymptote is set by model capacity, search depth, buffer diversity, and starting conditions. v1-v5 hit one plateau; v6 starts further along the same curve but recipe is identical so the curve shape is identical. If v6 peak ≈ v5 peak → same curve, recipe family ceiling confirmed; only structural changes (bigger net, specialist league, longer search) lift the ceiling. If v6 peak > v5 peak → iter_06 was below the curve's plateau and there's more headroom on this recipe.
**Why deferred:** purely an analysis lens, not an experiment. Apply this framework when interpreting v6 results in DECISIONS.md.

### Multi-box self-play sharding
**Idea:** Rent 4× boxes, each generating 25% of iter's games, all writing to a shared S3/GCS replay buffer. Centralized trainer consumes the buffer. Cuts wall-clock per iter by ~4×.
**Why deferred:** Coordinating multi-box runs is fiddly (sync, dropout, retries). Only worth it for a 50+ iter run where the per-iter wallclock savings amortize the setup cost.

## 2026-05-10 — Phase 4 v2 recipe fixes — LANDED 2026-05-10 (commit `a1f29ec`); FAILED 2026-05-11

The four fixes (warmstart-mix floor 0.3, K=30, anchor-gate, eval-games 50) all landed cleanly. 5-iter sanity ran 4h. Chain ELO drift -98 (vs v1's misleading +612 — chain-vs-anchor agreement confirms the methodology fix). Definitive iter_4 anchor at n=50: **24% wr, ELO -200**. Below the 40% acceptance threshold. v2 quarantined; v3 recipe TBD. See DECISIONS.md "2026-05-11 — Phase 4 v2 recipe FAILED acceptance".

---

## 2026-05-11 — Phase 4 v3 recipe candidates (after v2 mix=0.3 floor regressed -200 ELO)

**Context:** v2 (mix=0.3 floor) slowed but didn't stop the regression. Drift was ~25 ELO/iter vs v1's ~50 ELO/iter. Recipe needs more anchoring.

**Candidates (select 1-2 per v3 attempt — don't try all four; confounds the diagnosis):**

1. **Higher warmstart-mix floor (0.5 or 0.7).** Most direct extension of v2. Tradeoff: less pure self-play signal per iter.
2. **Best-so-far reference instead of warmstart_canonical.** Track best-passing iter; on FAIL, restart next iter's warm-from from best-so-far instead of latest. Existing `anchor_gate_log.json` infrastructure makes this easy.
3. **Higher sims for self-play (200 vs 100).** AlphaZero used 800. Doubles per-iter cost (~7h for 5-iter sanity) but might cleanly fix the noise floor in policy targets.
4. **Reject-iter on anchor FAIL.** Currently FAIL just logs. Could delete the failing checkpoint and re-train from the previous good starting point with new RNG seed. Preserves "checkpoint chain advances only on improvement".

**Most likely combo for v3**: (1) + (2) — higher floor as the anchor strength bump, plus best-so-far reference as the ratchet. Both implementable in <2h without changing the inner training loop.

**Why deferred:** needs a plan-mode session to pick the candidate combo + define a sharper acceptance bar (e.g., monotonic non-regression across 5 iters, not just ≥40% at iter_4).

---

## 2026-05-10 — Phase 4 v2 recipe fixes (HISTORICAL — landed/failed; see entries above)

This entry is preserved for reference to what was attempted in v2.

**Recipe-fix shortlist (4 fixes implemented in commit `a1f29ec`):**

1. **Floor warmstart-mix at ≥0.3 throughout.** Changed `--warmstart-mix-schedule` default from `"1.0,0.7,0.4,0.0"` to `"1.0,0.7,0.4,0.3"`.
2. **K=10 → K=30 replay-buffer window.**
3. **Anchor-gate per iter** (10 games at sims=50 vs warmstart_canonical, ≥40% wr to PASS, halt after 3 consecutive FAILs).
4. **Bump eval games per chained head-to-head from 20 → 50.**

Result: insufficient. See FAILED entry above.

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
