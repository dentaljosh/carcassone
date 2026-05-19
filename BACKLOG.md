# Backlog

Parking lot for ideas, distractions, and things-to-do-later that come up during work on the main project. **Do not action items in here without explicit approval from Joshua.** This is a capture-and-forget tool, not a TODO list.

When something goes in: timestamp it, one-line description, why it's not being done now.
When something comes out: either it gets promoted to an actual phase, or Joshua deletes it.

> Cleaned 2026-05-16: removed landed items (batched GPU inference, in-place state mutation, fp16 inference, Phase 3 prerequisites, self-play temperature sampling, rule-based Tier-1 player), dead v1-v6 recipe entries (v2/v3 recipe fixes, v7 candidates framing, right-size-box, S-curve v6 diagnosis, c_puct sweep continuation — the recipe question is resolved, see DECISIONS 2026-05-16), and the orchestrator-GIL null result (lives in DECISIONS). Kept ideas are still valid for the v2.7-retrain line.

## Captured ideas

<!-- Format:
## YYYY-MM-DD — [short title]
**Context:** what we were doing when this came up
**Idea:** what the thing is
**Why deferred:** out of scope / premature / nice-to-have / needs Joshua decision
-->

## 2026-05-19 — Code-review loop: deferred bug fixes (REVIEW_LOG.md)

**Context:** A 4-iteration multi-agent code review (full findings + rationale in `REVIEW_LOG.md` at repo root) applied 13 safe fixes and deferred 16. Four deferred items are real fixes with a known trigger point — parked here so they are not forgotten. D6 (warmstart-mix train/val leakage) was reviewed and deliberately **skipped** — warmstart mixing is over (`--warmstart-mix 0.0`).

### D13 — `features.py` `tiles_remaining` off-by-one — fix at the NEXT CLEAN RETRAIN
**Idea:** `tiles_remaining` counts the just-placed tile on every MEEPLES-phase encode (the engine doesn't clear `state.next_tile` until `draw_tile`). Wrong by ~1.2% for ~50% of evaluations; `progress` jumps by 1/total at each TILES→MEEPLES transition. Fix: `len(deck) + (1 if is_tiles and next_tile else 0)`.
**Why deferred:** it's a network INPUT feature. Currently benign — training and inference agree (both buggy). Fixing `features.py` alone desyncs inference from the current checkpoint + every existing `.npz` (which store pre-encoded scalars). Only fix as part of a fresh from-scratch baseline (fix feature → regen data → retrain). **Decide together with D1.**

### D1 — `board_repr.py` ref-tile encoded differently in TILES vs MEEPLES phase — decide at the NEXT CLEAN RETRAIN (with D13)
**Idea:** the reference-tile channels encode the *unrotated* `state.next_tile` during the TILES phase but the *rotated* `last_tile_action.tile` during the MEEPLES phase — two different meanings for the same channel range. May be partly intentional (in the MEEPLES phase the decision genuinely concerns the just-placed tile), but it is an unexamined inconsistency the network has to absorb.
**Why deferred:** changing it is a network-INPUT encoding change → retraining boundary, exactly like D13. Make it a conscious call (unify the two, or keep + document the rationale) at the next from-scratch baseline.

### D16 — `virtual_score_v2.py` board-edge city 100% closure bonus — fix at the NEXT LEAF-EVAL CAP RE-SWEEP
**Idea:** `_close_prob(0)` returns 1.0; a city whose only open edge points off the 35×35 board counts 0 in-bounds open positions but is still `finished=False`, so it gets a full closure-anticipation bonus it physically cannot earn. Fix: `continue` (no bonus) when `_open_city_positions==0` on an unfinished city — at both the city-closure and farm-growth loops (~line 351).
**Why deferred:** it changes the v2.7 leaf eval → per CLAUDE.md "a bug fix in scored heuristics shifts hyperparameter optima," the tuned caps (`CAP=12`, drop-3-open) must be re-swept. Trigger is rare (city at the literal board edge). Fold into the next leaf-eval change / cap re-sweep; never standalone.

### D9 — failed self-play game holds its claim ~90 min — fix BEFORE the next MULTI-ITERATION run
**Idea:** a game that raises leaves `seed_NNNNNN.claim` undeleted; the seed is blocked until the 90-min stale threshold, and a deterministically-failing seed never completes (iteration count never reaches `args.games`). Fix: a `.failed` sidecar — workers skip it; "iteration done" becomes `npz + failed >= games`.
**Why deferred:** needs a small policy call (fail after 1 attempt vs a retry budget). Pure orchestration, no model impact — fine to do any time before the next multi-iter self-play run.

### D15 — work-stealing stale-recovery multi-winner race — DECISION: accept + document
**Idea:** `_try_claim` stale-recovery can yield multiple winners (a stale-info thread renames aside a fresh claim re-created by an earlier winner). Bounded duplicate games on crash-recovery only, never corruption (the atomic `.npz` write is the real correctness layer).
**Decision (2026-05-19):** do NOT attempt the concurrency redesign — high risk on a live primitive, a botched fix could lose a claim (worse than the duplication). Instead relax the docstring's "exactly one winner" overpromise and change `test_32_threads_race_for_one_stale_claim` from `xfail` to assert `1 <= winners <= N`. Small, safe; do whenever.

## 2026-05-17 — Search self-consistency check: sims=200 vs sims=1000

**Context:** Reviewing a second agent's idea list against the iter_02 saturation diagnosis. The whole Option-2 plan rests on the premise that the policy has saturated against the fixed v2.7 leaf. Most of that agent's ideas were already captured below or already in the active plan (tactical probe set, aux heads, domain planes, league play, determinization, action-space dedup all already in this file; richer score-diff value targets already landed; value-head blending IS Option 2). This self-consistency check was the one genuinely new item.

**Idea:** run MCTS at sims=200 and sims=1000 on the same set of positions; measure how often the chosen move disagrees. Strong disagreement ⇒ the policy prior is misleading the search and there is headroom (more search finds moves the policy doesn't propose). Agreement ⇒ the policy has internalized what extra search would find — saturation confirmed at the *search* level, not just the recipe level.

**Why this matters:** a direct, cheap test of the saturation premise the Option-2 plan depends on. Diagnostic only — it doesn't fix anything.

**Cost:** ~5× per-position MCTS cost for the 1000-sim arm; a few hundred positions suffices. No training; ~100 LoC eval harness.

**Why deferred:** the iter_02 +0.2 flatline already evidences saturation — not worth blocking Option 2 now. Worth running if iter_B1/iter_B2's result is ambiguous and we need to know whether the ceiling is the leaf or the search.

## 2026-05-16 — Leaf-eval refinements from competitive-strategy lit review

**Context:** While iter_02 was retraining, ran a strategy lit review (general-purpose research agent, `agentId: a8b5319eb8e50bf52`) across BGG forums + Carcassonne strategy blogs, looking for concrete priorities the `virtual_score_v2` leaf eval might be missing. **Key caveat:** competitive Carcassonne tournaments are base-game-oriented; there is *no* high-credibility pro corpus for our exact 2p Base+River+Farmers scope. Findings are directional (strategy blogs, moderate credibility), not authoritative. Most encoded principles were *confirmed* — the gaps are formulation/weighting, not missing categories.

**Ideas (ordered by leverage):**

1. **Tile-counting closure probability.** `_close_prob` currently estimates feature-completion likelihood from the open-edge *count*. Experts compute it from *which specific tiles remain in the deck* — if all edge-matching tiles are already drawn, P(completion) is exactly 0 (the meeple is permanently stuck). The engine knows the remaining deck. This is a concrete precision upgrade to a term we already have. Lowest-risk, highest-clarity item.

2. **Penalize large open cities, don't just discount them.** Big incomplete cities are pure liability (sabotage target + meeple lock). The closure-anticipation bonus rewards *progress*, which may over-reward them. Consider an explicit penalty on large-open-city exposure.

3. **Targeted denial — reframe of the failed v3 opp_cap.** v3's blanket asymmetric opponent cap was noise. Lit review suggests denial value is *targeted*: sabotaging an opponent's **near-complete large** city ≈ halving its projected payout. The principle isn't wrong; the v3 functional form (blanket cap) was. A targeted term keyed on (opponent feature, near-complete, large) is the right shape.

4. **Meeple economy — reframe of the failed v3 meeple_K.** v3's flat `K × free-meeple-count` was noise. Lit review: the value isn't idle meeples, it's the *opportunity stream* — weight by *stranding risk* (meeples committed to features with low completion probability), plus the *option value* of holding ≥1 reserve meeple for a high-EV instant claim (drawn cloister = 9, 1-tile city = 7).

5. **Farm majority-flip awareness.** The base score already handles *current* farm majority (engine scorer). Missing: anticipating majority *flips* — a 2nd farmer that only ties a contested field is worth far less than one that flips majority; conceding a saturated lost field and redeploying is correct.

**Why deferred:** the whole leaf-redesign is gated on iter_02's result. If iter_02 keeps the ~+13/iter compounding cadence, the free recipe still has room and leaf work waits. If iter_02 flattens (policy saturated against the fixed leaf), this list — plus the competing "NN value head as a correction term, especially for farms" direction — becomes the headline Phase-4 experiment. Item 1 (tile-counting P) is low-risk enough to consider regardless. Per the n=20-noise lessons this week, any leaf change must be confirmed at n≥50.

## 2026-05-14 — Action-space dedup: redundant meeple-placement slots

**Context:** While playing vs Tier-1 in the GUI, Joshua noticed the engine often offers multiple meeple-placement positions on what is logically the same feature — e.g. "place on this side of the road" and "place on that side of the road" when both sides belong to the same connected road segment on the freshly-placed tile. Same for cities that span multiple tile sides.

**Idea:** dedupe equivalent meeple actions in the action space (or at decode time) so each *feature* has exactly one slot, not one slot per side touching the feature.

**Why this matters (and how much):**
- Tier-1 tiebreaks randomly across equal-virtual_score actions — duplicates cost nothing here.
- Vanilla-UCT MCTS at low sims wastes some sim budget visiting equivalent siblings before UCT consolidates — moderate efficiency loss, not a strength loss.
- For NN training (warmstart + self-play), the policy target either picks one variant arbitrarily or splits mass across them. Either way the model has to learn that equivalent actions are interchangeable, which is real wasted capacity.
- Estimated action-space inflation: 10-25% on meeple-phase actions (not measured precisely).

**Why deferred:** non-blocking. Deduping changes the policy-head shape, so it invalidates every existing checkpoint — the right time is at a fresh re-arch / warmstart, not mid-retrain-line. Estimate: ~1 day in `action_space.py` + decode + re-issuing the warmstart dataset.

## Phase 4 — deferred ideas (captured during the v1-v6 era; still valid)

These were parked while the v1-v6 self-play recipes were active. The recipe question is now resolved — v2.7 leaf + retrain compounds (DECISIONS 2026-05-16) — but these implementation / architecture ideas remain valid and un-actioned.

### Train alongside self-play (async)
**Idea:** the retrain pipeline is synchronous — generate iter N data, train iter N, eval. Run training continuously in a separate process consuming the replay buffer; check in on convergence at iter boundaries.
**Why deferred:** big architectural change. The GPU is largely idle during CPU-bound self-play so async training does have compute headroom — but it's only worth the complexity for a long multi-iter run, not the current one-iter-at-a-time cadence.

### Bigger net — but actually understand what "bigger" means here
**Idea:** Current net is 96×6 → 7.4M params. The structural truth (discovered 2026-05-13 by counting params): trunk is only ~1M; the **policy head's `Linear(2500, 2511)` dominates at ~6M**. So scaling filters/blocks gives modest growth:
- 128×10 → 9.4M (1.3×)
- 192×14 → 15.8M (2.1×)
- 256×10 → 18.3M (2.5×)
To get into KataGo-class param counts (50M+), the lever is **widening `policy_project_channels`** (currently 4) — bumping to 32 makes flatten go from 2500 → 20000 and the policy_fc Linear from 6M → 50M. That requires a fresh warmstart and re-arch.
**Why deferred:** capacity only matters if the recipe is the bottleneck — and as of iter_01 it isn't (data-scarcity confirmed, recipe compounds). Revisit if iter_02+ flatten. Cheapest experiment is 192×14 (arch-arg change + warmstart retrain); the big-headroom move is widening policy_project, which is more invasive. Note: a bigger net can't warm-start from a 96×6 checkpoint (different tensor shapes) — but the accumulated self-play corpus trains it fine.

### Hand-curated tactical probe set — measure WHAT the network learned
**Idea:** 30-50 hand-labeled positions where the right move is a known tactical play: city stealing (meeple flip via tile placement), city blocking (deny opponent's completion), cloister flooding (deny 8-neighbor close), meeple-economy endgame, farm sniping, etc. Run every checkpoint through the probe set; record `top1` and `top5` agreement with the labeled move.
**Why this matters:** anchor-wr at n=20 can't distinguish "learned to time meeples better" from "learned city stealing". A probe set can. Also: this IS Phase 5's training material — the analyzer needs a "good move bank" to explain "where you lost points".
**Cost:** 4-6 hours of human labeling + ~100 LoC python eval harness. Zero compute.
**Why deferred:** worth doing whenever we want to know *what* a checkpoint learned, and it de-risks Phase 5.

### KataGo-style domain features as input channels (HIGH LEVERAGE)
**Idea:** Add input planes the network would otherwise have to *learn* from sparse self-play signal:
- `tiles_remaining` (broadcast scalar plane — turns deck-counting from "hard-to-learn" into "trivial-read")
- `my_meeples_in_hand`, `opponent_meeples_in_hand`
- `is_river_phase`, `is_endgame`
- `my_dominant_farms_count`, `contested_features_count`
These would let the net learn the "endgame: place a meeple every move" rule in 1-2 iters instead of 50+. Closest published parallel: KataGo's territory + ladder features.
**Cost:** ~50 LoC in `board_repr.py` + retrain warmstart from scratch on bigger input dim (~3 hours local).
**Why deferred:** changes net input shape → breaks weight compatibility with all existing checkpoints. Only worth doing if we're committed to a fresh warmstart anyway.

### KataGo-style auxiliary loss heads
**Idea:** Add prediction heads with auxiliary losses (KataGo's biggest single ablation win):
- Predict who controls each feature at game-end (territory-equivalent)
- Predict final score-delta (richer than W/L; aligns with how Carcassonne actually plays — often 1-5 point games)
- Predict tile-count-remaining when each open feature closes
- Predict meeple-deployment-rate over remaining tiles
**Cost:** ~150 LoC architecture change + retrain warmstart. The losses are auxiliary (small weight); main training objective unchanged.
**Why deferred:** invasive change. Bundle with any fresh-warmstart re-arch.

### MCTS-side domain tweaks
**Idea:** Three cheap MCTS-only changes (no network change required):
- **Endgame depth boost**: last 10 tiles use sims=400 instead of 200. ~12% more total compute, concentrates depth where mistakes are decisive.
- **Heuristic prior blending**: at PUCT root, blend `0.1 × heuristic_policy + 0.9 × neural_prior`. Cheap regularizer; prevents confident pursuit of obviously-bad late-game lines.
- **Forced-move shortcut**: tiles with only one legal placement skip the search entirely.
**Why deferred:** small changes; defer until we have a stable recipe to test them against.

### MCTS Python hot-path optimization
**Context:** the 2026-05-13 orchestrator N-sweep proved workers (not the dispatcher) are the bottleneck. Workers spend ~50% of their time on Python MCTS tree work — selection, expansion, backup, all in pure Python with numpy.
**Idea:** profile `src/carcassonne_ai/mcts.py` against a 200-sim self-play game; identify the hot lines (likely PUCT selection or virtual-loss accounting); rewrite in Cython or as a single numpy vectorized pass. KataGo and Leela Chess Zero both have C++ MCTS for the same reason.
**Cost:** ~1-2 days of profiling + rewrite + tests. Compute cost negligible.
**Why deferred:** a throughput win, not a strength win — only worth it before a long multi-iter run. fp16 is NOT a lever (benched slower twice: autocast overhead exceeds compute savings on a 7M-param net + small batch).

### Symmetry exploitation — CONFIRMED not used (free ~4× data on the table)
**Status:** Verified 2026-05-13: grep for `rot90|symmetr|augment` in `src/`, `train_iter.py`, `train_warmstart.py` finds zero matches (only `flip` for player-perspective handling, semantically different).
**Idea:** Carcassonne is symmetric under 90/180/270° board rotation IF you simultaneously rotate every tile's representation (the matching-edge structure is preserved). That's ~4× effective training data for free. Reflection (mirror) augmentation is trickier because some tiles aren't reflection-symmetric (curved road), requires a tile-mirror lookup — defer.
**Cost:** Moderate. Need to: (a) implement `rotate_board_repr_90()` that re-encodes the 78-channel tensor under rotation, (b) implement `rotate_action(action, k)` to remap policy targets, (c) hook into the data loader. ~200 LoC. No retrain needed — works on any existing checkpoint's training data.
**Expected payoff:** unclear. If we're data-limited, 4× augmentation could be meaningful. KataGo uses 8× (rotation + reflection) and credits it as load-bearing. Cheap to A/B: re-train a warmstart with augmentation on, measure anchor wr.

### Probing classifiers — interpretability for the black box
**Idea:** Train small linear probes on hidden-layer activations of a trained net to predict: "how many city tiles remain in deck?", "who controls farm X?", "is this an endgame position?" If probes are accurate, the net has implicitly learned the concept.
**Cost:** ~1 day of work, mostly tooling. Compute negligible.
**Why deferred:** doesn't fix anything, just measures. Useful diagnostic when deciding the next structural direction.

### Defensive assert against accidental abbots/big-meeples
**Context:** wingedsheep engine defaults to `(FARMERS, ABBOTS)` for supplementary rules. Our `game_wrapper.py` short-circuits this, but if anyone instantiates `CarcassonneGame()` directly without going through our wrapper (e.g. in a new analysis script), they'd silently get abbots — out of scope for Phase 1-5.
**Idea:** Add a module-level assert in `game_wrapper.py` that fails loudly if `ABBOTS` ever appears in any `Game` instance passed to it.
**Cost:** 5 LoC.
**Why deferred:** no current bug; only a footgun for future tooling.

### Specialist warmstarts + league play
**Idea:** Bias the existing heuristic labeler 3 ways (roads-weight=2 / cities-weight=2 / farms-weight=2), train 3 warmstart nets (~30 min × 3 = ~$1.50). Run a 3-way round-robin to see if specialists dominate the generalist. Two consume options:
- **Distill**: train a single new warmstart net targeting a weighted mix of the 3 specialists' outputs.
- **League**: in self-play, opponents come 25% from each specialist + 25% from the generalist (vs current 100%-self-play). Stops mode collapse — the loop has to play against diverse strategies, not just its own most recent self.
**Why this is interesting:** it exploits Carcassonne-specific structure (our heuristic labeler). Closest published parallel: AlphaStar's main-exploiters league.
**Why deferred:** the current v2.7-retrain line compounds without it; league play is a mode-collapse insurance policy worth revisiting only if a long multi-iter run shows diversity collapse.

### Multi-box self-play sharding
**Idea:** Rent N boxes, each generating 1/N of an iter's games, all writing to a shared replay buffer. Centralized trainer consumes the buffer. Cuts wall-clock per iter by ~N×.
**Why deferred:** coordinating multi-box runs is fiddly (sync, dropout, retries). Only worth it for a 50+ iter run where the per-iter wallclock savings amortize the setup cost.

## 2026-04-27 — LRU bound on legal-moves cache
**Context:** The opt-in cache on `Game(enable_legal_moves_cache=True)` is unbounded. Per-search clear_caches() keeps memory bounded in well-behaved MCTS code, but a forgotten clear could leak memory across many searches.
**Idea:** swap the dict for `functools.lru_cache`-style bounded LRU (maxsize ~50K) so misuse degrades gracefully instead of OOM.
**Why deferred:** premature until something exposes the gap. Clear-on-search pattern is the standard MCTS idiom and unlikely to leak.

## 2026-04-28 — encode_board() scans full 35×35 board
**Context:** Reviewer pass 2026-04-28. `board_repr.encode_board` iterates every cell of `state.board` (1225 cells) on every encode call, even though the centered window is 25×25 and only ~80 tiles are placed mid/late game. Edge/internal blocks are also recomputed per-tile per-call instead of memoized.
**Idea:** scan only the bounding box of placed tiles (or the window bounds), and memoize tile edge/internal encodings keyed by `(tile.description, rotation_signature)`. Probably 3-5x speedup at gen scale.
**Why deferred:** not on the hot path for training (encoding happens once per position before .npz save). Hot path is generation; benchmark first to confirm encoding is a meaningful fraction of gen cost before optimizing.

## 2026-04-28 — Many tiny .npz files: I/O-noisy at 500K+ scale
**Context:** Reviewer pass 2026-04-28. 100K positions = 10K .npz files, ~100KB each. Streaming reads one file at a time → lots of file opens. Fine for 100K; at 500K (50K files) the I/O becomes meaningful overhead.
**Idea:** after train/val split, optionally pack many game files into split-preserving shards (e.g. 100 games per shard → 100 shard files instead of 10K).
**Why deferred:** premature for current scale. If we scale to 500K and observe DataLoader stalling, this is the fix.

## 2026-04-28 — Split string_representation into legal-move key vs MCTS state key
**Context:** External review pass 4 (2026-04-28). `string_representation` omits full deck order, last_river_rotation, and abbots/big-meeple pools. For our in-scope deterministic games, collision risk is low in practice, and the engine doesn't use those out-of-scope pools at all. But for general-purpose MCTS state-keying (especially Phase 4+), it's incomplete.
**Idea:** split into two keys:
- `legal_moves_key(board)` — visible legality state only (what the cache needs)
- `mcts_state_key(board)` — full deck signature, last_river_rotation, all pools, full placed-tile orientations
**Why deferred:** correctness for Phase 3 unaffected. For Phase 5 analyzer, this should land along with the chance-node / determinization work.

## 2026-04-28 — River edge-case regression tests
**Context:** External review pass 4 (2026-04-28). `RiverRotationUtil.get_river_rotation` can implicitly return None around river start/straight cases. Coverage is thin. Specific cases to test:
- River start tile placed at starting_position
- River end tile placed (last river segment)
- Disallowed repeated bend sequence (engine should refuse)
- last_river_rotation correctly tracked across multiple river placements
**Why deferred:** these are correctness concerns rare in random play but may bite during production gen. Targeted tests, ~1 hour.

## 2026-04-28 — Phase 5 deck determinization for analyzer
**Context:** External review (2026-04-28). Current MCTS uses the engine's pre-shuffled future deck (deterministic). For Phase 5 analyzer (where we DON'T know the future tile order from a real family game), we'd need POMDP-style determinization: sample N possible orderings of the remaining bag and average MCTS results. Already noted in `mcts.py` docstring.
**Why deferred:** Phase 5 problem, not Phase 3/4. Standard determinization pattern when we get there.

## Deferred — may revisit if Phase 4 stalls

These were candidate Phase 3 acceptance-iteration paths. Phase 3 closed on 2026-04-29 with v2 declared the canonical warmstart (see DECISIONS.md "Phase 3 closure"). Both are kept here in case Phase 4 reveals that the warmstart is materially holding the self-play loop back; in that case either could become a fast retry without re-deriving the rationale.

### 2026-04-28 — 2-ply heuristic-policy labels (sees both phases of one turn)
**Context:** External review (2026-04-28). Current `_heuristic_policy` evaluates `virtual_score(after applying TILE-action)` — it doesn't see the meeple follow-up. Many strong tile placements depend on the meeple choice, so the policy target may be miscalibrated for tile-phase positions.
**Idea:** for tile-phase labels, look 2 ply ahead: try each tile placement, then for each, find the best meeple decision (or "skip"), score the resulting state. Use that 2-ply best-score as the tile's heuristic value.
**Status (2026-04-29):** Already plumbed via `--heuristic-lookahead 2ply` in `warmstart.py` and `scripts/generate_warmstart_smoke.py`. Untested at scale. Smoke at low position count produced near-identical policies to 1-ply (not yet diagnosed). To revisit: regen 100K with `--heuristic-lookahead 2ply`, retrain with same hyperparameters, run T1 head-to-head against v2.
**Cost if revisited:** ~3-4× generation slowdown (~6-12h for 100K), then ~30 min train + ~80 sec T1.

### 2026-04-29 — MCTS-label fallback (Option C from the original Phase 3 plan)
**Context:** Phase 3 smoke comparison (2026-04-28) showed Option D (heuristic-only at 100K) won 24.7× over Option C (MCTS-labeled at smaller scale) on a wins-per-hour-of-gen basis, so Option D was promoted to production. Option C was never run at production scale.
**Idea:** generate ~50K positions via MCTS s=50 visit distributions for policy targets (still using virtual_score for value targets). MCTS-derived policy targets capture multi-ply lookahead structure that 1-ply heuristic targets miss; the trade-off is ~25× more compute per position.
**Status (2026-04-29):** estimated ~26 hours for 50K positions on 16-worker Pool. Skipped during Phase 3 closure. May revisit if Phase 4 self-play converges below v2 strength.
**Cost if revisited:** ~26h gen + ~30 min train + T1 + T2. Whole experiment ~2 days end-to-end.

## Promoted to project

<!-- When an idea graduates to actual work, move it here with a link to the relevant phase or PR. -->

(none yet)

## Killed

<!-- Things Joshua explicitly decided not to do, with reasoning. Keep these so we don't re-litigate. -->

(none yet)
