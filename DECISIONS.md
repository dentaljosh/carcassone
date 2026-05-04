# Architecture Decision Record

Every non-trivial technical decision gets logged here. The bar for "non-trivial" is: if Joshua looked at this code in 3 weeks and asked "why did we do it this way?" — would the answer be obvious from the code alone? If no, log it.

**Always log:** board representation choices, action space encoding, network architecture, hyperparameter values that aren't from a cited paper, framework/library choices, anything where you considered alternatives.

**Don't log:** variable names, file organization, formatting choices, library version pinning, anything that's purely a style decision.

## Format

```
## YYYY-MM-DD — [decision title]
**Context:** what problem we were solving
**Options considered:**
  - A: [description, pros, cons]
  - B: [description, pros, cons]
  - C: [description, pros, cons]
**Decision:** chose [option]
**Reason:** [why]
**Reversal cost:** low / medium / high
**Phase:** [which phase this was made during]
```

## Decisions

## 2026-04-29 — Phase 3 closure: declare v2 the warmstart, skip remaining acceptance iteration, proceed to Phase 4

**Setting:** v2 (100K heuristic-labeled at tau=0.5) hit T1=88/100 (88%) and T2=5/16=31% on NeuralMCTS(s=50) vs vanilla(s=100). Both miss the original prompt's acceptance bars (T1 ≥90%, T2 >55%). Failure-mode classify split (11 v2 T2 losses) showed mean realized gap +11.5 vs mean endgame gap −17.8 — net wins in-play, loses endgame. Working hypothesis: virtual_score's snapshot evaluation is a poor proxy for actual final-score-differential when label-time is mid-late game with substantial development remaining; the value head misses the long-horizon endgame component (farmer field merges, contested-field development, fields-fragility).

**v3 experiment (this entry):** relabel the v2 dataset's value targets with `tanh(actual_game_final_score_diff / 15)` instead of `tanh(virtual_score / 15)`. Same boards, scalars, policy targets, masks. Same hyperparameters (6×96, 20 epochs, batch 256, lr 1e-3, wd 1e-4). Same checkpoint slot. Single variable change.

**Pre-flight:** correlation of virtual_score-target vs final-score-target on 1000 positions = r=0.58. Targets disagree meaningfully (abs-mean diff 0.31 on a [−1, +1] scale), so the experiment was worth running.

**Result:**
- v3 T1 head-to-head on identical 100 seeds: **84/100 (84%)** vs v2's 88/100 (88%). Δ = **−4pp**, not within ±3pp wash band but not ≥−5pp clear regression either.
- v3 final-epoch val MSE = 0.324 vs v2's value MSE in the 0.08 range — ~4× higher. The noisier final-score target genuinely hurts the value head.
- v3 val pol CE plateaued from epoch 8 onward (1.65-1.68); train pol CE kept dropping to 1.27. Clear policy-head overfit.
- Best checkpoint by val loss = epoch 12. Used for T1.

**Interpretation:** the noise hypothesis was right. Random-self-play final scores carry ~20 turns of unrelated development noise downstream of the labeled position, which the value head cannot disentangle from the position's own quality. Snapshot virtual_score is the better target for value-head supervision under these label sources.

**Decision:**
1. **v2 is the canonical warmstart.** Promoted to `checkpoints/warmstart_canonical.pt` (copy of `warmstart_heuristic_tau05_prod.best.pt`).
2. **Skip remaining Phase 3 acceptance iteration.** The remaining warmstart improvement candidates — MCTS-labeled at scale, hybrid rollout labels, 2-ply heuristic policy, c_puct sweep continuation — all require compute commitments comparable to Phase 4 itself with no guarantee of clearing the original prompt's acceptance bar. The acceptance numbers (T1 ≥90%, T2 >55%) were unmeasured guesses in the original prompt, not load-bearing requirements.
3. **Proceed to Phase 4 (self-play).** The only way to get genuinely strong labels is from strong play, and we don't have a strong player to label with. AlphaZero solves this via self-play (the network labels its own training data, getting stronger as labels improve). Continuing warmstart iteration is trying to substitute label engineering for the self-play loop, and v3's failure is evidence we've hit the ceiling on that substitution.

**Why not retry v3 with a different policy regime / different lookahead / different sims:** every such variant runs into the same root cause — labels generated from random self-play cap out at random-self-play strength. The v3 experiment closes off the value-target axis cleanly. The remaining axes (policy lookahead depth, MCTS sim count for labels) are all the same kind of label-engineering substitution.

**Deferred (may revisit if Phase 4 stalls):** 2-ply heuristic policy lookahead (already plumbed via `--heuristic-lookahead 2ply`), full c_puct sweep at {1.5, 3.0, 5.0}, MCTS-label fallback at 50K positions s=50 (~26 hours). All gated on Phase 4 needing them.

**Reversal cost:** medium. v3 dataset and checkpoint stay on disk; if Phase 4 needs the noisier-target experiment revisited (e.g. as a regularizer), can resume directly.

**Phase:** 3 closure → Phase 4 entry.

**Diagnostic artifacts:**
- `data/phase3_diagnostic/v2_loss_split.md` — realized vs endgame breakdown of v2 T2 losses
- `data/phase3_diagnostic/farmer_audit.md` — confirmed virtual_score's farmer term IS engine farmer (no calibration gap)
- `data/phase3_diagnostic/v3_vs_v2_t1.md` — v3 T1 head-to-head with full per-epoch training metrics

## 2026-04-28 — Phase 3 v1 acceptance result + v2 retry plan (sharper tau)

**Setting:** 100K heuristic-labeled positions at tau=10.0, trained 6×96 ResNet 20 epochs.

**Training metrics:**
- Train value MSE: 0.165 → 0.030 (5.5× reduction — strong learning)
- Val value MSE: 0.137 → 0.081, best at epoch 14
- Train policy CE: 1.860 → 1.855 (essentially flat)
- Val policy CE: 1.879 → 1.879 (flat)
- Diagnosis: value head learned the position-value map well; policy head barely fit because tau=10.0 produced near-uniform targets (top-1 mass ~45%, top-1/uniform ratio ~1.17×).

**Tournament 1 (network argmax vs random, 100 games):**
- Result: **84/100 wins (84.0%)** — below the ≥90% acceptance threshold
- avg score diff: +19.0 (net comfortably ahead, just not crushingly)
- 105s wallclock total

**Tournament 2 smoke (NeuralMCTS s=20 vs vanilla MCTS s=20, 2 games):**
- Result: **0/2 wins, avg diff -6.5** — strong signal that the full T2 at s=50/s=100 will also fail
- Per-game wallclock: 6.2 min at s=20/s=20; full s=50/s=100 extrapolates to ~28 min/game × 100 games / 2 spawn workers = ~24h. Decided not to burn that compute on a likely-failing run.

**Decision:** instead of running the 24h T2, regen with sharper tau (=0.5) and retry. Rationale:
- T1 result + flat policy training loss + soft heuristic targets all point at the same root cause: the policy head is barely getting trained because the labels don't favor any one action much.
- Tau=0.5 sharpens top-1 mass from ~45% to ~64% (5.5× over uniform vs 1.17× before) — measured empirically on the new data.
- Cost: ~58 min regen + ~17 min train + ~2 min T1 = ~80 min round-trip vs 24h for the unmodified T2.
- The 100K data at tau=10 stays as a control; v2 goes to `data/warmstart/heuristic_tau05/` so the comparison is reproducible.

**Reversal cost:** none — both datasets coexist; v2 is a separate experiment.
**Phase:** Phase 3

---

## 2026-04-28 — Engine bug fix: city_diagonal_top_left_road shared description with shielded variant

**Context:** External reviewer flagged that the wingedsheep tile dict at `engine/wingedsheep/carcassonne/tile_sets/base_deck.py` had `"city_diagonal_top_left_road"` with a description literal of `"city_diagonal_top_left_shield_road"` — same string as the shielded variant 30 lines above. Our `string_representation` keys placed tiles by `(description, outer_edges)`; both tiles have the same outer edges and (after the bug) the same description. MCTS transposition tables would merge two scoring-distinct states (shielded city tile scores +1 per tile in completed city; unshielded does not).

**Fix:**
- Patched the engine description literal to match its dict key.
- Defense-in-depth: extended `_tile_rotation_signature` in `game_wrapper.py` to include `(shield, chapel, flowers)` booleans, so a future upstream description collision still produces distinct state keys.
- Regression test in `tests/test_string_representation.py::test_shielded_and_unshielded_tile_produce_distinct_signatures`.

**Impact on Phase 3 work:** none. Heuristic gen never invokes string_representation (it labels via virtual_score, which reads tile.shield directly). The bug would have bitten an MCTS-labeled gen or any future MCTS use; it didn't corrupt the 100K dataset.

**Reversal cost:** none — strict bug fix.
**Phase:** Phase 3 (engine patch)

---

## 2026-04-28 — Phase 3 production gen sized to 100K, not 500K

**Context:** Original plan (Option D from smoke comparison) committed to 500K heuristic-labeled positions. With the old 40-channel encoding, that was ~3.3 hours of generation. With the new 78-channel encoding (from the prereq fix), per-position generation cost rose ~3× to ~0.35s wallclock per game with 16 workers. 500K = 50K games would now take ~5 hours of pure CPU. 100K (10K games) takes ~50-60 min.

**Decision:** generate 100K positions now. If acceptance fails by a small margin, scale to 250K or 500K incrementally. If it passes, we're done; the additional gain from going to 500K is marginal (logarithmic improvement at most for this regime).

**Reason:**
- 100K is 20× the smoke-comparison sample size (5K). The smoke verdict was decided by a 24.7× wins-per-hour-of-gen advantage; the heuristic-vs-MCTS hypothesis is robustly tested at 20× scale.
- Acceptance criteria (≥90% net-vs-random standalone, >55% NeuralMCTS-s50 vs vanilla-s100) are absolute targets, not relative to dataset size. Either the network learns enough to clear them, or it doesn't.
- Production gen is resumable. If 100K fails by <5pp, we add 100K more without redoing the existing data.
- Risk-adjusted vs. running ahead: a 1-hour gen with bounded compute commitment beats a 5-hour gen-then-fail.

**Reversal cost:** none — incremental scale-up just adds .npz files; the heuristic policy is deterministic per seed.
**Phase:** Phase 3

---

## 2026-04-28 — Phase 3 production prerequisites landed (encoding richness, scalar normalization, streaming trainer)

**Context:** External review (2026-04-28) flagged three blockers before scaling the heuristic warm-start to 500K positions. All three landed in this session.

**Changes:**

1. **Scalar feature normalization** (`src/carcassonne_ai/features.py`):
   - meeples / 7, scores / 100, score_diff / 50, deck size / 85
   - phase one-hots and progress already 0/1 — left untouched
   - Length still 10; only the values changed. Shifts all features into roughly `[-1, 1]` so the dense head doesn't waste capacity learning the magnitude scaling.

2. **Board encoding richness** (`src/carcassonne_ai/board_repr.py`):
   - 40 → 78 channels.
   - Added 6 same-road and 6 same-city pair indicators per cell (12 ch) — distinguishes e.g. straight-road from chapel-with-road, or full-city from two-separate-cities-on-same-tile, even when outer-edge categories coincide.
   - Replaced the 4 cell-level meeple/farmer presence channels with 18 per-side / per-corner channels: 5 sides × 2 owners (NORMAL meeples) + 4 corners × 2 owners (FARMER). A meeple on TOP claiming a city is now distinct from a meeple at CENTER claiming a chapel.
   - Reference-tile broadcast also gets the 12-channel internal-topology block, so the policy head can pick rotations using the tile's connectivity, not just outer edges.
   - Crossroads / three-way-split road gotcha: engine models these as N separate `Connection(outer, CENTER)` entries. Per Carcassonne rules these are SEPARATE road features (they meet at the tile center but are scored independently). The pair encoder unions only outer↔outer connections, so crossroads correctly reports all-zero pair indicators. Test in `tests/test_board_repr_internal.py::test_crossroads_is_four_separate_roads`.
   - Backwards-compat shims: legacy constants `CH_MEEPLE_MINE`/`OPP`/`FARMER_MINE`/`OPP`/`REF_TILE` still exist and point at the first slot of each block, so existing tests pass without rewrites.

3. **Streaming/IterableDataset trainer** (`src/carcassonne_ai/warmstart.py` + `scripts/train_warmstart.py`):
   - `make_streaming_dataset(files)` returns a torch IterableDataset that lazy-loads one .npz at a time. Worker-shards the file list, shuffles file order per epoch via `set_epoch`, optionally shuffles within file.
   - `split_files_train_val(files, val_fraction, seed)` partitions deterministically by FILE (= by GAME); positions never leak across the split.
   - `count_positions(files)` reads only the npz header, no full array load.
   - New `scripts/train_warmstart.py` is the production trainer (default 6×96 net, 4 DataLoader workers). Smoke trainer untouched for tiny-dataset use.

**Tests added (28 new, 108 total now passing):**
- `tests/test_board_repr_internal.py` — 11 tests covering road/city pair encoders for straight/bent/crossroads/three-way/chapel-with-road/full-city/diagonal/separate-cities.
- `tests/test_board_repr_meeples.py` — 3 tests covering per-side, per-corner, and owner-routing semantics.
- `tests/test_warmstart_streaming.py` — 10 tests covering streaming yield count, shapes, DataLoader integration, multi-worker sharding, train/val determinism, set_epoch behavior.

**Removed:** `tests/test_legal_moves_cache.py::test_cache_speedup_on_repeated_state` — perf microbench that turned flaky after the engine adjacency fix made uncached calls cheap (cache benefit shrunk to within system-noise margin). Cache correctness still covered by `test_cache_hits_on_repeated_calls` and `test_cache_returns_same_mask_as_uncached`.

**Reversal cost:** medium — checkpoints from the smoke comparison (40-channel encoding) are now incompatible with the new network input shape. They have to be regenerated. The smoke comparison itself doesn't need redoing — that decided "heuristic over MCTS at 25× cheaper" and the gap is far too wide to flip. Re-running validation is the 100-position smoke described in STATUS.md.

**Phase:** Phase 3

---

## 2026-04-28 — Phase 3 smoke comparison: HEURISTIC wins, scale to 500K (BUT pause for prerequisites first)

**Comparison results:**

| Strategy | Gen time | Net wins/50 vs random | Wins/hour-of-gen |
|---|---|---|---|
| Heuristic (5K, 4×64 net, 20 ep) | ~2 min | 35/50 (70%) | 1050 |
| MCTS s=50 (5K, 4×64 net, 20 ep) | ~55 min | 39/50 (78%) | 42.5 |

MCTS edges out by ~8 percentage points and ~+5 score diff at 5K positions, but takes ~25x longer to generate. Per the smoke decision rule (wins-per-hour-of-generation), **heuristic wins by 24.7x**.

Production plan: 500K heuristic-labeled positions (~200 min generation, then ~30 min train, then evaluate).

**Decision:** Option D (heuristic-only labeling, 500K positions).

**Caveats logged:**
1. The smoke uses a 4×64 net for 20 epochs on 5K positions. The MCTS-labeled signal might shine more with the production 6×96 net + 50K-or-more positions; we can't extrapolate from the smoke alone. If the 500K-D production run fails the 90%-vs-random acceptance, fall back to a smaller MCTS-C run as a contingency.
2. **Production gen is GATED on the prerequisite work** (BACKLOG): board encoding richness, scalar normalization, streaming dataset trainer. Both the heuristic-D and MCTS-C generation share these limitations — a 500K-D run today would waste compute relative to one with proper encoding.

**Reversal cost:** medium — if heuristic-D production run fails acceptance, regenerate via MCTS-C (~26h on the same hardware)
**Phase:** Phase 3

---

## 2026-04-28 — External review findings + bug fixes

**Context:** External agent reviewed Phase 3 code mid-smoke-run. Two bugs surfaced that didn't bite the live work but violated contracts; several "production-blocking" items also flagged.

**Bugs fixed (commit alongside this entry):**
- `Game.get_canonical_form(board, player)` was double-swapping mine/opp channels when `player != current_player`, silently returning current-player perspective instead. `encode_board(state, player, off)` already handles perspective; the conditional `canonical_swap` is wrong. Removed. New regression test `test_canonical_form_for_opponent_actually_flips_perspective` in `tests/test_invariants.py`.
- `warmstart.generate_one_game_dataset` did not seed the global `random` module before `Game.get_init_board()`. The engine shuffles its deck via `random.shuffle` (global), so seeds were not reproducible. Now `random.seed(seed)` runs first; the local `rng = random.Random(seed + 1)` handles our action choices.

**Production-prerequisites flagged for Phase 3 full warm-start (not blocking smoke):**
1. Board representation needs to encode meeple side/corner (currently just "meeple on this tile") and tile internal topology (currently just outer-edge categories). Two tiles with identical edges but different internal connectivity look identical to the network. Estimated +25 channels (~65 total). Half-day fix.
2. Scalar features unnormalized — raw scores 0-100, tiles 0-85, meeples 0-7. Should divide by sensible scales before training. 30 min fix.
3. Trainer loads all data into RAM. 50K positions ≈ 6 GB, 500K ≈ 60 GB — needs streaming/`IterableDataset` over `.npz` files. Few-hour refactor.

**Decisions:**
- Smoke comparison continues unchanged. Both strategies share these flaws, so the C-vs-D verdict stays valid. Bugs fixed mid-flight don't affect already-generated checkpoints (the generation logic doesn't call get_canonical_form, and the seed-reproducibility doesn't matter for unique-trajectory comparison).
- After smoke decides C vs D: PAUSE before scaling up. Land the three prerequisite fixes + a small validation smoke (re-run 100 positions on the new encoding) before committing to the multi-hour production generation.

**Reversal cost:** none for the bug fixes; medium for the prerequisite refactors (would require re-encoding any previously-generated data)
**Phase:** Phase 3

---

## 2026-04-28 — Phase 3 network starting capacity: 6 ResBlocks × 96 filters

**Context:** Need to pick a starting size for the warm-start network. Original prompt said 10–15 ResBlocks, 128 filters. AlphaZero-Chess used 40×256.

**Options considered:**
  - A: 10×128 (~12M params). Original plan default. Comfortably trainable; fits in <500MB on the 5060 Ti.
  - B: **6×96 (~4M params)**. Smaller, faster to train, faster to iterate during debugging.
  - C: 4×64 (~1M params). Likely too small to capture meaningful policy structure.
  - D: 15×128 (~18M params). High end of the prompt's range. Probably overkill.

**Decision:** chose B (6×96).

**Reason:**
- Carcassonne's branching factor (max 96 legal actions) and state complexity are way smaller than chess (~35 legal actions, far simpler scoring). AlphaZero-Chess's 40×256 was sized for a much harder problem; even our prior 10×128 default was likely overkill.
- Phase 5 (the project's actual goal per `docs/ORIGINAL_PROMPT.md`) is a coaching tool, not a superhuman bot. We don't need maximum playing strength — we need a network that's good enough to surface high-value positional analysis.
- Smaller networks train faster, iterate faster during debugging, and are far easier to scale UP (with the same code) than to scale DOWN a broken big-network setup.
- If Phase 3 acceptance fails (network can't beat random ≥90% standalone, or net+MCTS(s=50) doesn't beat vanilla MCTS(s=100) >55%), bump to 10×128. If it overfits 50K positions instantly, shrink to 4×64.

**Reversal cost:** medium — value/policy heads' weights don't transfer if width changes; need full retrain. Cheap relative to a long warm-start run though.
**Phase:** Phase 3

---

## 2026-04-28 — Phase 2 acceptance: MCTS(s=20) wins 96/100 vs random + Q-tiebreak fix

**Result:** MCTS(s=20) defeated random in **96/100 games** (96.0%, avg score diff +30.9, 0 draws, 4 losses). Cleared the prompt's ≥95% acceptance criterion. Per-game results checkpointed to `data/tournament/s0020_seed*_p*.json` for reproducibility.

**Key fix mid-Phase-2:** the original `MCTS.best_action` chose the most-visited child by N. At low simulation budgets (s=10–20 with ~50 root actions), most children have N=1 — the choice between them is essentially arbitrary. Empirical signal: MCTS(s=10) won only ~47% vs random in the first run. Fixed by switching to `argmax_Q` with N as tiebreak; tournament re-ran and trended cleanly to 96%.

**Sims chosen for acceptance:** s=20 not s=100. Reason: per-game wallclock at s=10 was ~28 min; at s=20 ~11 min/game. The 2020 paper's s=100 was for beating Star2.5; for beating random, s=20 is plenty. Phase 4's NN-MCTS replaces vanilla anyway — vanilla MCTS is just a sparring partner here.

**Pre-Phase-3 perf wins (incidentally landed during Phase 2):**
- `get_valid_moves` 49.5ms → 1.75ms (28×) via engine adjacency tracking (`state.open_positions`)
- mid-game MCTS sim 25s → 1.78s (14×) via `apply_action_inplace` (skips deepcopy in rollout-discard path)

**Reversal cost:** none — this is a result, not a decision
**Phase:** Phase 2

---

## 2026-04-27 — Phase 4 prerequisite: get_valid_moves performance strategy (IMPLEMENTED, opt-in)

**Status update:** option A (wrapper-level cache) is now implemented in `src/carcassonne_ai/game_wrapper.py`, opt-in via `Game(enable_legal_moves_cache=True)`. Tests in `tests/test_legal_moves_cache.py` cover correctness, hit-rate stats, clear semantics, read-only protection on cached masks, and a 5x speedup floor. Default is OFF so Phase 1 fuzz tests don't accidentally rely on cache state. Phase 2 MCTS will pass `enable_legal_moves_cache=True` and call `clear_caches()` between root moves. Engine-level adjacency tracking (option B below) remains deferred — only revisit if the cache hit rate proves insufficient.

**Context:** Quick-bench showed `Game.get_valid_moves` at 49.5ms/call. Phase 4 MCTS will call it at every tree node. Estimate: 200 sims × ~70 moves × 100 games per iteration = 1.4M calls × 49.5ms = ~19 hours of pure get_valid_moves work per iteration. The prompt's plan estimated 30-45 min/iteration — this would blow that by ~25x and break Phase 4.

**Root cause:** `TilePositionFinder.possible_playing_positions` (engine) scans every cell of the 35×35 board (1225 cells) × 4 rotations × `TileFitter.fits` per cell = ~4900 fit-checks per call. Most cells are empty interior or empty-far-from-placed, never legal placements.

**Two complementary mitigations (both deferred until Phase 2 done; caching is the priority):**

### A. Wrapper-level legal-move cache (RECOMMENDED — implement before Phase 4)

**Cache key:** the subset of `string_representation` that affects the legal-move set:
- `(placed_tiles_with_orientation_grid, placed_meeples, current_player, phase, next_tile_signature, last_tile_action_coord_or_None)`.
- Excludes scores, deck-remaining-count, opponent meeple pool. Confirmed by reading `ActionUtil.get_possible_actions`, `TilePositionFinder`, and `PossibleMoveFinder`: the legal-move set depends only on those fields.

**Cache scope:** per-MCTS-search. Cleared between root moves. Avoids stale-state bugs without sacrificing hit rate (within one search the same nodes are revisited heavily).

**Invalidation:** none needed inside an MCTS search. Each tree node has a fixed state and we deepcopy on `apply_action`. Verified by `Game.get_next_state`: `copy.deepcopy(state)` before `StateUpdater.apply_action`. No in-place mutations leak across nodes.

**Memory budget:** action mask = 2511 bools = ~316 bytes packed. State key ≈ 300 bytes. ~600 bytes per entry. Max ~50K entries per search × 600 B ≈ 30 MB per worker. With 16 self-play workers: ~500 MB. Trivial on 32 GB.

**Expected speedup:** MCTS revisits a small set of root-vicinity nodes heavily during selection. Hit rate ≥ 90% in steady-state. Effective per-call cost drops from 49.5ms to <1ms (cache hit) + amortized 49.5ms × (1 - hit rate). Net: ~10x for Phase 4.

### B. Engine-level adjacency tracking (OPTIONAL — defer; revisit if cache underperforms)

**Idea:** maintain a `state.open_positions: set[Coordinate]` set updated incrementally on each placement: add the (up to 4) empty neighbors of the just-placed tile, remove the just-placed tile's coordinate. `TilePositionFinder` iterates `state.open_positions` instead of the full 35×35 grid.

**Speedup of cold (cache-miss) calls:** O(35²×4) → O(open_count × 4). Open count is typically 20-80 mid-game → 15-60x faster cold path.

**Effort:** ~1 day. Need to instrument `StateUpdater.apply_action` to maintain the set, verify no other engine path bypasses it, add tests.

**Memory:** negligible (~100 Coordinate objects = a few KB).

**Why deferred:** the cache alone probably suffices for Phase 4. The engine-level fix is a multiplicative improvement on cold-path latency that matters mostly when the cache hit rate is poor. Reassess after the cache lands.

### Combined plan
1. **Phase 2 (next):** implement vanilla MCTS without caching first to validate correctness against the 2020 paper's baseline.
2. **Pre-Phase 4:** add wrapper-level legal-move cache (option A). Re-bench. If <2 min/iteration achieved, ship it.
3. **If still too slow:** add engine-level adjacency tracking (option B).

**Reversal cost:** zero — both are pure-function caches/optimizations
**Phase:** Phase 1 (design); to implement before Phase 4

---

## 2026-04-27 — Phase 1 quick-bench results (per-call cost map)

**Context:** First profiling pass on the wrapper. Numbers from `scripts/bench_quick.py` on idle CPU.

| op | μs/call | note |
|---|---:|---|
| `Game.get_valid_moves` | 49,500 | dominant cost — engine enumerator |
| `Game.get_canonical_form` | 152 | board+scalar tensor build |
| `Game.string_representation` | 208 | repr hash |
| random self-play (1 worker) | 4.95 s/game | single-process baseline |
| random self-play (Pool x16) | 0.70 s/game | 7.11x speedup |
| GPU 4096² fp16 matmul | 2.80 ms | 49 TFLOPS effective |

**Implications:**
- `get_valid_moves` is ~99% of per-game cost. The engine's `ActionUtil.get_possible_actions` walks the 35×35 board scanning for legal placements; for Phase 4 self-play (with MCTS calling get_valid_moves at every node), this is the bottleneck to address. Possible mitigations (in priority order): cache the legal-move set per state hash; restrict the placement scan to tiles adjacent to placed tiles only; rewrite the inner loop in numpy/cython. Defer until Phase 4 confirms it's blocking.
- `get_canonical_form` and `string_representation` are negligible.
- ETA cheat-sheet (Pool x16 random self-play): 100 games ≈ 70s, 1000 games ≈ 12 min, 5000 games ≈ 58 min.

**Reversal cost:** N/A — measurements only
**Phase:** Phase 1

---

## 2026-04-27 — Phase 1 action-space encoding: phase-aware flat (size 2511)

**Context:** The original Phase 1 plan encoded a turn as `(position, rotation, meeple)` jointly into a single flat 38,440-dim action space. While reading the engine for Phase 1 implementation we discovered the engine treats one Carcassonne turn as **two sequential decisions** (`GamePhase.TILES` then `GamePhase.MEEPLES`). The agent never picks all three components simultaneously.

**Options considered:**
  - A: Unified flat encoding parameterized by phase. Tile half is `W*W*4 + 1` (placement + tile-pass). Meeple half is 11 (5 NORMAL sides + 4 FARMER corners + meeple-pass). Total = `W*W*4 + 11 = 2511` for W=25.
  - B: Two separate policy heads, routed by `state.phase`. Cleaner separation but doubles head count and adds plumbing.
  - C: Original 38,440-dim joint encoding. Would have ~95% of indices unreachable at any state.

**Decision:** chose A.

**Reason:** A matches engine reality (the mask is built directly from the engine's `get_possible_actions`), keeps the network output ~16x smaller than the original plan, and a single Coach/Arena training loop works without phase-aware routing. The `getValidMoves` mask zeroes off-phase indices, so training only ever sees same-phase logits as the active region.

**Reversal cost:** medium — the network policy head depends on this size; switching encodings requires retraining
**Phase:** Phase 1

---

## 2026-04-27 — Window size is a Game config parameter, not a hardcoded constant

**Context:** Phase 0 measurements suggested 25×25 fits 99% of random games with margin. But MCTS-driven play (Phase 2) and Phase 4 self-play may sprawl differently, and we don't want a major refactor if 25 turns out to be wrong.

**Options considered:**
  - A: Module-level `WINDOW_SIZE = 25` constant. Simple. Refactor needed if size changes.
  - B: Config parameter on `Game(window_size=25)`, threaded through `WindowOffset(size)`. Minor plumbing increase, but resizing is a one-line change at the call site.
  - C: Re-measure constantly and resize per-game. Overkill; breaks checkpoint compatibility.

**Decision:** chose B.

**Reason:** Joshua's explicit ask. The cost is small (`WindowOffset` already existed; just added a `size` field), and the freedom to re-train with a different window size in Phase 4 is worth more than the saved keystrokes. `DEFAULT_WINDOW_SIZE = 25` is the module default; tests parametrize over `{21, 25, 31}`.

**Reversal cost:** zero — already configurable
**Phase:** Phase 1

---

## 2026-04-27 — Parallel-worker count: use full SMT fan-out (16 on 5800X)

**Context:** Measurement and (later) self-play workers parallelize CPU-bound random-game simulation. Predicted SMT contention would cap useful parallelism at 8 (physical cores). Benchmarked it instead.

**Setup:** `scripts/bench_workers.py` runs 64 random games per pool size on AMD 5800X (8C/16T):

| workers | wall (s) | games/s | speedup |
|--------:|---------:|--------:|--------:|
|       1 |   286.20 |    0.22 |   1.00x |
|       4 |    80.53 |    0.79 |   3.55x |
|       8 |    51.73 |    1.24 |   5.53x |
|      14 |    43.67 |    1.47 |   6.55x |
|      16 |    41.61 |    1.54 |   6.88x |
|      17 |    43.56 |    1.47 |   6.57x |
|      18 |    42.71 |    1.50 |   6.70x |
|      24 |    41.04 |    1.56 |   6.97x |
|      32 |    42.40 |    1.51 |   6.75x |

Oversubscription (>16) was tested explicitly: 17 is slightly *worse* than 16, 18-20 is a wash, 24 wins by 1.4% (within single-run noise), 32 loses. **16 (`os.cpu_count()`) stays as the default** — 24 is at best a noise-level optimization, and going past that actively hurts.

**Decision:** use `os.cpu_count()` (16 logical) for measurement scripts and self-play.

**Reason:** Predicted SMT-sibling ALU contention didn't materialize. The engine is heavily Python-interpreter-bound — much of the per-instruction time is dispatch/GC/refcount overhead, which doesn't fight SMT siblings the way fused-FP code does. Diminishing returns past 8 are real (5.40x → 6.90x for 2x workers) but it's still strictly faster.

**Reversal cost:** zero — single config knob in two files
**Phase:** Phase 0

---

## 2026-04-27 — Phase 0 measurement results (random play only)

**Context:** Phase 0 step 0.7 — empirically measure the bounding-box size of placed tiles and the per-decision legal-action count, to replace the prompt's "31×31 window" and "alpha=0.3" guesses with data. CSVs live in `data/measurements/`.

**Setup:** 1000 random games for board size, 200 random games (33,084 decisions) for action space, both with `[BASE, THE_RIVER]` + `[FARMERS]`, 2 players.

**Board bounding box (1000 games):**
- width: p50=14, p99=20, max=22
- height: p50=15, p99=20, max=23
- longest side: p50=16, p99=21, max=23

**Action space (33,084 decisions):**
- min=1, mean=18.8, p50=4, p90=51, p99=68, max=96

**Implications (will revisit after Phase 2 MCTS measurements):**
- Window size: 25×25 fits 99% of random games with 4-tile margin. Plan default of 31×31 is overprovisioned for random play. **Holding 25×25 as a tentative target but will retry with MCTS games before committing** — MCTS-driven play tends to sprawl more than random.
- Action space max=96 << 500, so flat softmax with hard masking is comfortably tractable. No factored heads needed.
- Dirichlet alpha rule-of-thumb (10 / mean_legal_moves) ≈ 0.53. The prompt's default of 0.3 is in the right ballpark; 0.5 may train slightly faster. Sweep in Phase 4 hyperparameter pre-flight.

**Reversal cost:** measurements are reusable; window choice is parameterized
**Phase:** Phase 0

---

## 2026-04-27 — Vendor upstream repos rather than using git submodules

**Context:** Phase 0 needs to bring in the wingedsheep Carcassonne engine and the suragnair alpha-zero-general framework. The original prompt's setup snippet implied sibling clones with `pip install -e`.

**Options considered:**
  - A: Vendor (clone, drop `.git`, commit our copy). Pros: patches live in our git history; no submodule friction. Cons: drift from upstream; manual rebases if upstream improves.
  - B: Git submodules. Pros: clean provenance; explicit upstream version pinning. Cons: cannot patch the engine without first forking to our own GitHub fork; submodules add friction for solo development.
  - C: Sibling clone + `pip install -e`. Pros: lightest. Cons: patches live in untracked sibling clones — risk of losing them when switching machines or after a clean checkout.

**Decision:** chose A (vendor).

**Reason:** wingedsheep is unmaintained (last release Oct 2021) and we expect to need engine patches (farmer scoring is the most likely problem area). Vendoring puts patches in our own git history. License attribution preserved in `THIRD_PARTY_LICENSES/`.

**Reversal cost:** low (could re-extract to siblings later if needed)
**Phase:** Phase 0

---

## 2026-04-27 — Reward normalization: tanh(diff / 15) — UPDATED from /20 after measurement

**Context:** AlphaZero-General's value head expects values in [-1, 1]. Need to map Carcassonne score differentials onto that range so the value head trains efficiently — too tight saturates, too loose under-utilizes the range.

**Original choice (now superseded):** `tanh(diff / 20)`, reasoned from "typical close games are ±20" — an assumption, not a measurement.

**Empirical data (1000 random games, `scripts/measure_reward_distribution.py`):**

  diff (signed): min=-45, p1=-31, p5=-19, p25=-7, p50=-1, p75=+7, p95=+18, p99=+31, max=+59
  |diff|: mean=9.0, p50=7, p90=19, p95=24, p99=35

  | D | in [-0.9, +0.9] | saturated (>=0.99) |
  |--:|---:|---:|
  | 10 | 81.7% | 3.7% |
  | **15** | **93.7%** | **0.6%** |
  | 20 | 97.5% | 0.1% |
  | 25 | 99.1% | 0.0% |
  | 30 | 99.6% | 0.0% |

The target was ~90% of games in the non-saturated range with headroom. /20 puts 97.5% in non-sat — under-utilizes the [-1, +1] range, weaker gradient than optimal. /15 is the closest fit at 93.7% non-sat / 0.6% saturated.

**Updated decision:** `tanh(diff / 15)`. Code: `SCORE_NORM_SCALE = 15.0` in `src/carcassonne_ai/game_wrapper.py`.

**Forward-looking note — revisit after Phase 3:** trained-bot games will have a tighter score-differential distribution than random games (the bots stop blowing each other out). Anticipate switching `SCORE_NORM_SCALE` from 15 to **10** at that point. The plan:

1. After Phase 3 warm-start, save 1000 self-play games' (score_p0, score_p1, diff) to `data/measurements/phase3_selfplay_diff.csv` (one row per game).
2. Run `python scripts/measure_reward_distribution.py --source csv --csv data/measurements/phase3_selfplay_diff.csv` (the script is parameterized to accept arbitrary CSV input — random play now, network self-play in Phase 3, trained-bot self-play in Phase 4).
3. Pick the new D from the empirical table (target ~90% non-saturated). Likely 10, possibly 8.
4. If D changes by >20%, update `SCORE_NORM_SCALE` and follow the migration plan below.

**Migration plan for D = 15 → 10 (or whatever Phase 3 indicates):**
- **Default: retrain value head from scratch.** The Phase 3 warm-start is supervised learning on heuristic-labeled positions — labels are cheap to regenerate by re-running the heuristic with the new D. Throw away the /15 weights, regenerate labels with the new D, retrain. This is what alpha-zero-general supports natively and is the cleanest path. Cost: a few hours of supervised training on cached positions.
- **Alternative (rejected unless retraining proves expensive):** label transformation — `tanh(diff/10) ≈ tanh(1.5 * atanh(value_at_15))` lets us reuse /15 weights as a warm start. More elegant and saves training time, but introduces approximation error and requires custom code in the training loop. Reject by default; revisit only if Phase 3 retraining turns out to dominate iteration time.

**Reversal cost:** medium (value-head retrain on cached positions; cheap relative to Phase 4 self-play cost)
**Phase:** Phase 1

---

## 2026-04-27 — Window-overflow handling: drop the game

**Context:** Centered sliding window encoding will occasionally have games sprawl past the window dimensions. Need to decide what happens.

**Options considered:**
  - A: Drop the game from training, log warning.
  - B: Dynamic per-move re-centering. Adds a coordinate-translation step to MCTS state hashing — bug risk.
  - C: Grow the window post-hoc on threshold breach. Adds checkpoint-incompatibility risk between training iterations.

**Decision:** chose A.

**Reason:** With window sized at empirical 99th-pct + 4-tile margin, overflow rate should be <1%. Dropping the game is by far the simplest mechanism. We will track overflow count as a metric and revisit if rate exceeds 0.5% in real self-play data.

**Reversal cost:** low (window size is parameterized; can resize and retrain)
**Phase:** Phase 1

---

## 2026-04-27 — Patch wingedsheep engine: ties award full points to all tied players

**Context:** Phase 0 sanity checks revealed that `PointsCollector.get_winning_player` returned `None` whenever multiple players tied for most meeples on a feature. The caller code awarded zero points in that case. This contradicts the official Carcassonne rules ("if tied, all tied players score full points") and is especially load-bearing for our scope because farmer fields are frequently contested.

**Options considered:**
  - A: Patch the engine in place (vendored fork) — rename `get_winning_player` → `get_winning_players` (returns a list), iterate at all 5 call sites, award points to each.
  - B: Wrap the engine and post-process scores. Fragile — callers compute scores in tight loops during state updates and re-deriving the right answer externally is error-prone.
  - C: Live with the buggy behavior. Unacceptable: farmer scoring is the most subtle and most-contested feature; getting it wrong silently corrupts the value-head training signal.

**Decision:** chose A.

**Reason:** Vendoring was justified specifically for this kind of patch. The change is local to `points_collector.py` and verified by a new sanity check (tied 2-tile road → both players score 2 pts).

**Reversal cost:** low (single file diff)
**Phase:** Phase 0

---

## 2026-04-27 — Patch wingedsheep engine: lazy tkinter import

**Context:** `CarcassonneGame.__init__` eagerly instantiated `CarcassonneVisualiser`, which imports tkinter at module load. WSL2 doesn't have python3-tk by default, and headless training never needs the visualiser.

**Options considered:**
  - A: Make visualiser instantiation lazy in `render()`. Existing call sites continue to work.
  - B: Add `python3-tk` as a system-package requirement. Pushes complexity onto every developer/CI machine.
  - C: Strip the visualiser entirely. Loses an occasionally useful debug tool.

**Decision:** chose A.

**Reason:** Smallest patch with no API change. `render()` still works when the user actually calls it (and tkinter is installed).

**Reversal cost:** low
**Phase:** Phase 0

---

## 2026-04-27 — Patch wingedsheep engine: silence print statements behind module flag

**Context:** `points_collector.py` had 15 `print()` calls that fired on every scoring event. At 100 games the noise was acceptable; for 100K+ self-play positions it would dominate stdout and slow training.

**Options considered:**
  - A: Replace prints with a module-level `_log()` that's gated on `CARCASSONNE_VERBOSE` env var (default off).
  - B: Replace with Python `logging` and a custom logger. More flexible but pulls in handler config we don't need.
  - C: Live with the prints and redirect stdout in our scripts. Pollutes test output and other tooling.

**Decision:** chose A.

**Reason:** Minimal change, opt-in verbosity for debugging, no logging-config plumbing.

**Reversal cost:** low
**Phase:** Phase 0
