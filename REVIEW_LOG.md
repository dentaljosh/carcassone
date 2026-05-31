# REVIEW_LOG.md — iterative code-review log

A 4-iteration review loop over the living code (self-play → train → eval
pipeline + GPU orchestrator). Each iteration: parallel review agents →
apply the safe corrections → log everything not fixed here with the reason.

"Deferred" = a real finding deliberately NOT auto-fixed: a judgment call, a
behavior/encoding change needing Joshua's decision, a latent/unreachable
issue, or a phase-3-closed script. Items here are inputs for Joshua, and
later iterations skip re-reporting them.

---

## Iteration 1 — 2026-05-19

6 agents, one per subsystem: MCTS+selfplay core / eval-server IPC /
network+board encoding / game-wrapper+leaf-eval / training+warmstart /
selfplay-orchestration+work-stealing.

### Fixed (safe corrections applied)

| # | File:line | Bug | Fix |
|---|---|---|---|
| F1 | `game_wrapper.py:275` | `get_game_ended` returned `+1e-6` for **both** players on an exact draw, so `v0+v1 == 2e-6` — violates the documented antisymmetry `get_game_ended(b,0) == -get_game_ended(b,1)` that MCTS value backup relies on. | Player-dependent epsilon: `+1e-6` for player 0, `-1e-6` for player 1. Draw-detection window `(-1e-4,1e-4)` unchanged. |
| F2 | `eval_server_pool.py:95-118` | If `start_server` raised partway through the shard loop (e.g. CUDA OOM loading the Nth net copy), shards already started were orphaned — never shut down, leaking GPU processes/VRAM. | Wrapped the shard loop in `try/except`; on failure, `shutdown_server` every started shard, then re-raise. |
| F3 | `eval_server.py:316-324` | `shutdown_server` never closed `request_q`. If the server died without draining it, the parent's queue feeder thread blocks at interpreter exit → parent hangs. | Added `request_q.close()` + `cancel_join_thread()` after the join. |
| F4 | `mcts.py:787` | Serial `_simulate`: a transposition to an existing-but-unexpanded node skipped `_expand` (guard was `child is fresh and not child.expanded`), so `leaf_value` stayed at its `0.0` default and a bogus zero was backed up. | Guard changed to `not child.expanded` — expands any unexpanded leaf, fresh or transposed. Matches `_select_leaf_with_vloss`'s `needs_eval` logic. |

### Deferred (real findings, not auto-fixed)

**D1 — `board_repr.py:321-325` — ref-tile encoding semantics differ between TILES and MEEPLES phases.** [Important]
TILES phase encodes `state.next_tile` (unrotated drawn tile); MEEPLES phase encodes `last_tile_action.tile` (the placed, rotated tile). The network sees two different meanings for the same channel range. Reason deferred: changing the network input encoding invalidates the current checkpoint and all existing self-play training data — needs Joshua's call (re-encode + retrain, or keep + document).

**D2 — `board_repr.py:322`, `features.py:46`, `action_space.py:129` — phase compared by string (`state.phase.value == "tiles"`) not enum (`== GamePhase.TILES`).** [Minor]
Not a current bug — the strings match correctly today. It's a fragility: a silent wrong-branch fallthrough if the vendored engine's enum `.value` strings ever change. A no-op robustness refactor, not a correction.

**D3 — `virtual_score_v2.py:402-403` — `bonus_cap` vs `opp_bonus_cap` asymmetry breaks v2 antisymmetry when the two caps differ.** [Important, latent]
Default config uses equal caps so it is not currently triggered. Leaf-eval changes are an explicit judgment-call carve-out (Joshua, prior review). Recommend either always applying one cap to both sides, or asserting the caps are equal.

**D4 — `virtual_score_v2.py:116` — `DEFAULT_CONFIG` is built from `CARCASSONNE_V25_*` env vars at import time.** [Minor]
Env changes after the module's first import are silently ignored. Known design; tests that need fresh config pass an explicit schedule. Documentation/design judgment call.

**D5 — `warmstart.py:463-465` + `train_iter.py:160-161` — a corrupt/partial `.npz` crashes training.** [Important, low likelihood]
`count_positions` and the streaming loader call `np.load` with no exception handling. Largely mitigated by the atomic temp-file-then-rename write pattern for files this pipeline produces. The fix is a fail-loud-vs-skip-and-warn policy decision; at minimum the error should name the offending path.

**D6 — `train_iter.py` `_build_mixed_file_list` (line 110) + `warmstart.py` `split_files_train_val` — train/val leakage.** [Important]
`_build_mixed_file_list` oversamples warmstart files **with replacement** (`rng.choices`); duplicate paths in the combined list straddle the index-based train/val split, so the same game's positions land in both train and val. NOT triggered at `--warmstart-mix-fraction 0.0` (the upcoming deepsearch iteration uses 0.0). Real for mix>0 iterations. Recommended fix: split unique games into train/val FIRST, then oversample only within the train side (val stays clean, no downside) — a pipeline refactor, deferred for Joshua's call.

**D7 — `mcts.py:627` / `mcts.py:248` — crash on an expanded-but-non-terminal node with zero legal moves.** [Important, latent]
`_expand_with_priors:562-565` creates exactly such a node (`legal.size==0` → `expanded=True`, `valid_actions=[]`); `_select_child_puct` then does `valid_actions[0]` → IndexError; vanilla `_rollout` does `rng.choice([])` → ValueError. Likely unreachable in real Carcassonne (every non-terminal state has ≥1 legal move; the all-outside-window case raises `WindowOverflowError` instead). Internal inconsistency; resolving it requires deciding the semantics of a no-moves non-terminal node.

**D8 — `remote_evaluators.py:99-103`, `evaluators.py:104,210`, `mcts.py:610` — empty-board batch returns priors shape `(0,)` not `(0,A)`.** [Minor]
Unreachable in the current MCTS flow — every call site guards `if not boards` before dispatching. Latent shape inconsistency only.

**D9 — `run_selfplay_iter.py:325-335` — a failed game leaves its `.claim` file live for `--claim-stale-secs` (default 90 min), blocking that seed on both boxes.** [Important]
Real work-stealing throughput bug. The fix is a retry-policy judgment call: immediate claim-unlink risks an infinite retry loop on a deterministically-failing seed (engine bugs do occur — `farm_util IndexError` history); a `.failed` sidecar that permanently skips the seed may be better. Needs Joshua's call.

**D10 — `eval_iter_head_to_head.py:602-603` — `losses`/`avg_diff` use `args.games` as the denominator instead of `len(results)`.** [Minor]
Holds in all current code paths (no partial-result path exists). A no-op robustness change, not a current bug. (Separate: odd `--games` gives a one-game color imbalance — operational, use even `--games`.)

**D11 — `run_phase4_smoke.py:90` — `_tally_anchor_eval_dir` glob ignores `o{old_sims}` filenames.** [Minor]
Not triggerable today (`run_phase4_smoke` never passes `--old-sims` to the anchor gate). Latent.

**D12 — `run_selfplay_iter.py:606` — shared-claim ETA uses the startup `remaining` count, racy cross-box.** [Minor, cosmetic]
The other box completes seeds during this box's startup, so the printed ETA is systematically pessimistic in shared mode.

**Phase-3-closed scripts** (not "living" code — logged for completeness, not fixed):
- `relabel_warmstart_with_finalscore.py:121` — `_check_one_seed` hardcodes the `heuristic_tau05` subdir, ignoring `--input-subdir`; `--check` mode reads the wrong dataset for any other subdir. [Important within that script]
- `train_warmstart.py:196-203` — NaN-skipped batches also skip `scheduler.step()`, so the cosine LR schedule reaches its minimum early. [Important within that script]

**Test gaps** (logged, not fixed):
- No test for `get_game_ended` antisymmetry on an exact DRAW (F1 was untested).
- No test for the `mcts.py:787` unexpanded-transposition path (F4 was untested).
- `test_eval_server.py:107-108` — L1 tolerance `1e-5` may be too tight cross-GPU (fp32 reduction order).
- No test asserting `_build_mixed_file_list` → `split_files_train_val` yields disjoint train/val.
- No test for `eval_server_pool` partial-failure cleanup (F2).
- `run_phase4_smoke` anchor-gate logic (`_tally_anchor_eval_dir`, `_best_so_far_iter`) untested.
- `network.py` value-range test uses a strict `< 1` inequality that is vacuously true for any bounded activation.

### Confirmed clean (agents verified, no action)
PUCT Q-sign / player-perspective in all 4 backup paths; virtual-loss apply/undo symmetry; Dirichlet noise; selfplay value-target sign; IPC request/response routing & batch concat/split offsets; fp16 autocast round-trip; `.npz` atomic-save naming (per-host+pid temp, leading-dot, no `seed_*.npz` glob match); checkpoint round-trip keys; `zero_grad` placement (prior fix held); the O_EXCL claim algorithm (sole arbiter, stale-recovery via `os.rename`, `--reset`+`--shared-claim` refused); eval result-cache key includes `old_sims`; `elo.py` / `eta.py` math.

---

## Iteration 2 — 2026-05-19

6 agents, same subsystem split. Each verified the iteration-1 fixes touching
its files and hunted for issues the first pass missed.

### Iteration-1 fixes verified
F1, F2, F3, F4 all independently confirmed **CORRECT** (antisymmetry holds;
the shard-cleanup loop skips `None` and never double-shuts; queue close is
after a guaranteed-dead consumer; the transposition expand uses the right
board and is idempotent).

### Fixed (safe corrections applied)

| # | File:line | Bug | Fix |
|---|---|---|---|
| F5 | `eval_server.py:124` | The server loop's `request_q.get()` blocks forever in a C-level semaphore where Python signal handlers can't run. An unclean parent exit (no `_SHUTDOWN` sent) leaves the server — and its CUDA context / VRAM — hung indefinitely. | Poll with `get(timeout=1.0)` in a loop so a signal can land within 1s. |
| F6 | `eval_server.py:297` | `start_server` calls `ready_event.wait(timeout=60s)`; if the server dies during init it never sets the event, so the caller blocks the full 60s (×N shards in a pool) before noticing. | Poll `proc.is_alive()` alongside the event — a dead server is caught in <1s with its exitcode. |
| F7 | `mcts.py:801-803` | Comment claimed `leaf_value` "is set by `_create_node` / terminal_value" — factually wrong (`_create_node` sets `terminal_value`, never `leaf_value`). | Corrected the comment to state the real invariant: every node here has been through `_expand`, which sets `leaf_value`. |
| F8 | `train_iter.py:141` | `--seed` is accepted and used for file splitting, but `torch`/`numpy` global RNGs are never seeded → network weight init + AdamW are non-deterministic across runs with identical args. (`train_warmstart.py` seeds both.) | Added `torch.manual_seed(args.seed)` + `np.random.seed(args.seed)` after arg parse. |
| F9 | `verify_shared_claim.py:84` | `_tally` used the CLI `--n` to decide which seeds are "missing". A `--tally` run with a different `--n` than the race used gives a false FAIL, or — worse, on this work-stealing **deploy gate** — a false PASS that skips checking high seeds. (The race result JSON already embeds `n`; `_tally` just ignored it.) | `_tally` now reads `n` from the result files and asserts all boxes agree; CLI `--n` no longer used in tally mode. |

### Deferred (new this iteration)

**D13 — `features.py:44` — `tiles_remaining` overcounts by 1 on every MEEPLES-phase evaluation.** [Important — RETRAINING BOUNDARY]
After `play_tile` the engine does not clear `state.next_tile` (it still holds the just-placed tile until `draw_tile` runs after the meeple decision), so `len(deck) + (1 if next_tile else 0)` counts the placed tile as a future tile. Scalar features 5 (`tiles_remaining`) and 9 (`progress`) are wrong by `1/total_tiles` (~1.2%) for ~50% of all evaluations. `rule_based_player._tiles_remaining` uses `len(deck)` only, confirming the intent. **Not auto-fixed**: the current global-best checkpoint and ALL existing self-play training data were encoded with this bug; fixing `features.py` now desyncs inference from training. Same class as D1 — needs Joshua's decision (fix + retrain from a clean baseline, or keep + document). Recommended fix when taken: `tiles_remaining = len(deck) + (1 if is_tiles and next_tile else 0)`.

**D14 — `virtual_score_v2.py:225-230` — `_city_closure_delta` computes the wrong closure delta for cathedral (inn-flagged) city tiles.** [Important — dead code]
Uses `6 if tile.shield else 3` per tile, overestimating the shield bonus. Unreachable in the locked scope: INNS_AND_CATHEDRALS is rejected at `Game` construction, so no tile carries the cathedral-city flag. Logged for completeness; fix only if that tile set is ever enabled.

**D2 extended** — `rule_based_player.py:68` also compares `state.phase.value` to a string literal — same fragility as D2 (`board_repr.py`/`features.py`/`action_space.py`). Same status: a no-op robustness refactor, not a current bug.

**mcts.py:801-804 (noted, not a finding)** — the serial `_simulate` backup reads `node.leaf_value` directly while `_run_batch` reads `leaf.leaf_value if leaf.expanded else leaf.terminal_value`. Safe today (every serial-path node is expanded before backup), but the asymmetry is a latent trap; a defensive `node.leaf_value if (node.expanded or not node.is_terminal) else node.terminal_value` would make the two paths consistent. Minor; left for a future maintainer.

### Test gaps (new this iteration)
- `test_neural_mcts_virtual_loss.py` `test_w_bounded_by_n_with_unit_vloss` — vacuous: the uniform evaluator returns value 0.0, so `W` is always 0 and the bound holds trivially. Needs a non-zero-value evaluator.
- `test_warmstart.py` `test_normalized_value_target_in_tanh_range` — vacuous: uses the initial board (scores 0-0 → `virtual_score`=0 → `tanh(0)`=0). Needs a few moves played first.

---

## Iteration 3 — 2026-05-19

6 agents, third pass. Fixes F5-F9 all independently verified **CORRECT**.

### Fixed (safe corrections applied)

| # | File:line | Bug | Fix |
|---|---|---|---|
| F10 | `selfplay.py:180` | The self-play game loop exits on game-end OR the `max_plies` cap OR a no-legal-moves `break`. On the latter two the game has NOT finished, yet the code still backfills value targets from `board.state.scores` (mid-game) — silently emitting a training game with wrong value labels. | Guard after the loop: if `get_game_ended == 0.0` (not terminal), raise `RuntimeError` instead of emitting a corrupt dataset. |
| F11 | `rule_based_player.py:168` | `_meeples_in_hand` docstring claimed "FARMER meeples come from a separate pool" — false. The engine draws NORMAL + FARMER from the same per-player `state.meeples[player]` pool. Implementation was already correct; only the comment misled. | Corrected the docstring. |
| F12 | `eval_iter_head_to_head.py:382` | `_append_elo_log` appended unconditionally; a direct rerun for the same (iter, vs_iter) pair produced duplicate ELO-chain entries. The sibling `_append_anchor_gate_log` already dedups. | Dedup on (iter, vs_iter) before append, mirroring the sibling. |

### Deferred — D15, the most important finding of the loop

**D15 — `run_selfplay_iter.py:204-233` `_try_claim` stale-claim recovery has a TOCTOU race that yields MULTIPLE winners.** [Important — live work-stealing primitive]

The fast-path O_EXCL create is correct (single winner — `test_32_threads_race_one_winner` passes). The STALE-RECOVERY path is not:
1. N workers all `os.open(O_EXCL)` → all get FileExists; all call `_claim_is_stale` against the SAME old claim → all see stale=True.
2. Each enters recovery: `os.rename(claim_path, staged_i)`. The docstring claims "only one racer can rename a given source; the rest get FileNotFoundError" — true for ONE generation of the file.
3. Winner A renames aside, unlinks, O_EXCL-recreates `claim_path` — a FRESH claim.
4. Worker B — which already passed `_claim_is_stale` in step 1 against the OLD claim — now runs `os.rename(claim_path, staged_B)`. `claim_path` exists (A's fresh claim), so the rename SUCCEEDS: B renames aside a perfectly valid fresh claim, recreates its own, and also "wins."
5. Repeat for C, D, … — each stale-info worker in turn renames whatever claim currently sits at the path. Up to N winners.

`test_32_threads_race_for_one_stale_claim` caught this (5 winners where it asserts 1); it is now `xfail(strict=False)` pending the fix. The docstring's "still exactly one winner / never an unbounded cascade" is **false** — bounded by N, but not 1.

**Impact:** bounded duplicate games *only when stale-recovery fires* — i.e. after a box crashes mid-game and leaves a >90-min-old claim. Each duplicate winner replays the seed; the atomic `.npz` write is last-writer-wins, so **no corruption — only wasted compute**. Normal operation (no crash → no stale recovery) is unaffected. **Not urgent for the current deepsearch run.**

**Why not auto-fixed:** no correct minimal patch exists. `_claim_is_stale`→`os.rename` cannot be made atomic with POSIX primitives; "re-check the staged file and rename it back if fresh" still races (rename-back can clobber a fast-path claim). Needs a deliberate redesign. Two directions for Joshua:
- **(a) Proper fix** — prevent a stale-info worker from acting on a newer claim: capture the claim's `st_ino` at the staleness check and abort recovery if the file identity changed before the rename (narrows the window); or gate recovery through a separate per-seed `.recovering` lock created with O_EXCL.
- **(b) Accept + document** — bounded duplicate games are genuinely harmless (atomic `.npz`, last-writer-wins). Relax the docstring and the test to `1 <= winners <= N` and rely on the `.npz` layer for correctness.

### Deferred — minor (new this iteration)
- `eval_server.py:267` — `stage_t["forward"]` can go negative if `_process_batch` raises mid-dispatch. Unreachable in practice (server crashes, the timing log never prints). Cosmetic.
- `run_selfplay_iter.py:546` `remaining==0` early exit — an agent flagged it for shared-claim mode; on tracing it is correct (`remaining==0` iff every `.npz` exists = genuine completion, mode-independent). Not a bug — recorded so a later pass doesn't re-raise it.

### Test gaps (new this iteration)
- `test_selfplay.py` — nothing exercises the F10 non-termination guard.
- `test_eval_server_pool.py` `test_pool_routing_*` — builds `{id(rq): ...}`; `id(None)` collides for skipped shards when `n_shards > n_workers` (degenerate, untested). Also spawns 3 real CUDA processes to check a pure-Python dict invariant.
- `test_board_repr.py` — no test for `CH_LAST_TILE_POS`; `test_canonical_swap_is_involutive` may pass vacuously if seed-7 play places no meeples.
- `test_selfplay_claim.py` `test_fork_processes_race_one_winner` — `q.get()` has no timeout; a child crashing before `q.put()` deadlocks the test.
- `test_virtual_score_v2.py` `test_v2_bonus_dedupes_duplicate_meeples` — may pass vacuously if every sampled meeple sits on an already-finished city.

---

## Iteration 4 — 2026-05-19

6 agents, fourth and final pass. Fixes F10, F11, F12 all verified **CORRECT**.
Five of six subsystems found nothing new — the expected convergence after 12
fixes. One new finding:

**D16 — `virtual_score_v2.py:305-313` — `_close_prob(0)` returns 1.0 for a board-edge city that is unfinished but has zero in-bounds open positions.** [Important — Medium confidence — leaf-eval judgment call]
`_open_city_positions` excludes out-of-bounds neighbour coordinates, so a city whose only open edge points off the 35×35 board counts 0 open positions. The engine still marks it `finished=False`, so the code does not `continue`; `_close_prob(0)` then hits the defensive `open_positions <= 0 → return 1.0` branch and applies a 100%-closure anticipation bonus to a city that physically cannot close. Recommended fix: when `_open_city_positions` returns 0 on an unfinished city, `continue` (no bonus) — at both the city-closure loop and the farm-growth loop (~line 351). **Not auto-fixed:** this is a v2.7 leaf-eval behaviour change — per CLAUDE.md "a bug fix in scored heuristics shifts hyperparameter optima," the tuned caps (`CARCASSONNE_V25_CAP=12`, drop-3-open) would need re-sweeping. Same disposition as D3/D4 — leaf-eval changes are Joshua's call. Trigger is an uncommon board-edge configuration; low practical impact.

---

## Loop summary (4 iterations, 2026-05-19)

**13 safe corrections applied** (F1-F13): game-ended draw antisymmetry;
eval-server pool orphan-cleanup, queue-feeder hang, signal-uninterruptible
loop, slow init-failure detection; MCTS transposition-expand + comment;
self-play non-termination guard; train_iter RNG seeding; verify_shared_claim
deploy-gate tally; eval ELO-log dedup; rule_based_player docstring; and F13 —
a float-tolerance fix to a flaky `test_virtual_score_v2` assertion (exact `<=`
on hash-ordered float sums) that the final full-suite run surfaced.

**16 items deferred** (D1-D16) with rationale — the ones needing Joshua's
decision: **D6** (warmstart-mix train/val leakage), **D9** (failed game holds
a claim 90 min), **D13** (`tiles_remaining` off-by-one — a retraining
boundary), **D15** (work-stealing stale-recovery multi-winner race — bounded
duplicate games, not corruption), **D16** (leaf-eval board-edge city bonus).
D1/D13 are encoding/feature changes that desync the current checkpoint; D3/D4/D16
are leaf-eval changes that need a cap re-sweep.

**1 test marked xfail** (`test_32_threads_race_for_one_stale_claim` → D15).
All other tests green. No production code is left in a broken state.

---

## Follow-up — 2026-05-19 (post-loop; dispositions by Joshua)

**F14 — `warmstart.py` corrupt-`.npz` handling (was D5).** `GameDataset.load` and `count_positions` now wrap their `np.load` calls: a corrupt/truncated `.npz` raises a `RuntimeError` naming the offending file instead of a bare `BadZipFile` with no path. Fail-loud-with-context — deliberately *not* skip-and-continue (that would have been a judgment call). Verified: `warmstart.py` compiles, 23 warmstart tests pass.

**Deferred-item dispositions (Joshua, 2026-05-19):**
- **D1** → BACKLOG.md — fix at the next clean retrain (encoding change); decide together with D13.
- **D5** → fixed now (F14).
- **D6** → **skipped** — warmstart mixing is over (`--warmstart-mix 0.0`); the leakage cannot fire.
- **D9** → BACKLOG.md — fix before the next multi-iteration run.
- **D13** → BACKLOG.md — fix at the next clean retrain (fixing the feature in isolation desyncs the current checkpoint).
- **D15** → BACKLOG.md — **accept + document** (option b): do NOT redesign the stale-recovery primitive. A redesign risks losing a claim on a live primitive, for a bug whose worst case is bounded duplicate games. Relax the docstring + test.
- **D16** → BACKLOG.md — fix at the next leaf-eval cap re-sweep (leaf-eval change shifts the tuned caps).
- D2/D3/D4/D7/D8/D10/D11/D12/D14 and the two phase-3-closed script bugs remain logged above — latent, unreachable, cosmetic, or in closed tooling; no action.

Total: **14 safe fixes applied** (F1–F14); 16 findings deferred (D1–D16).

---

## Follow-up — 2026-05-19 (D15 executed; river-rotation coverage)

**F15 — D15 executed (accept + document, per the disposition above).**
`_try_claim`'s docstring no longer overpromises "exactly one winner / never an
unbounded cascade." It now states the contract honestly: the fast-path O_EXCL
create is exactly-once; stale-recovery yields 1–N bounded winners (harmless —
crash-recovery only; the atomic `.npz` write is the real correctness layer).
`test_32_threads_race_for_one_stale_claim` dropped its `xfail` and now asserts
`1 <= winners <= N`, the real contract. **No `xfail` remains in the suite.**

**River-rotation test coverage** (BACKLOG 2026-04-28 — a thin-coverage item,
not a D-finding). New `tests/test_river_rotation.py`, 13 tests pinning
`RiverRotationUtil`: the pure rotation geometry (straight / CW / CCW),
real-tile checks via `the_river_tiles`, and the two easy-to-miss behaviors —
`get_river_rotation` *implicitly returns `None`* (not `Rotation.NONE`) at
river-start and for non-river tiles, and a straight segment carries the
previous rotation forward.

Running total: **15 safe fixes** (F1–F15). 16 findings logged (D1–D16); D5 and
D15 since resolved (F14, F15).

---

## Follow-up — 2026-05-29 (D1 + D13 resolved at the Path B retrain boundary)

Both were deferred as "fix at the next clean retrain" because fixing them in
isolation desyncs the current checkpoint/data. Path B regenerates all data +
warmstart from scratch, so that boundary is now — both taken:

- **D13 — RESOLVED (fixed).** `features.py:encode_scalars` now counts
  `state.next_tile` only in the TILES phase:
  `tiles_remaining = len(deck) + (1 if (is_tiles and next_tile) else 0)`. The
  MEEPLES-phase overcount (and the `progress` jump at TILES→MEEPLES) is gone.
  Regression test added: `tests/test_features.py` asserts the deck count in BOTH
  phases over a random game. (Committed in 6ac64f1; test 2026-05-29.)
- **D1 — RESOLVED (keep + document).** The phase-dependent ref-tile is
  *intentional*, not a bug: TILES decision needs the UNROTATED `next_tile`
  (rotation is part of the action); MEEPLES decision needs the PLACED, rotated
  tile. The phase one-hots + `CH_LAST_TILE_POS` let the net disambiguate the two
  meanings; always-encode-the-placed-tile was considered and rejected (it would
  hide the to-be-placed tile's identity during the TILES decision). Documented
  inline at `board_repr.py:321-329`.

Both also recorded in BACKLOG.md (✅ RESOLVED 2026-05-29). No deferred D-finding
remains that gates Path B.

---

## Iteration 5 (pre-launch, anchor-fraction self-play) — 2026-05-31

Multi-agent workflow review (6 dimensions → 2-skeptic adversarial verify →
synthesis) over the exact code path of the upcoming anchor-fraction run. 5 raw
findings → 3 survived verify (2 confirmed 2/2, 1 disputed 1/1). **3 of 6
dimensions came back clean after verification: `training`, `eval-gating`,
`scoring-labels`** — the parts that most directly determine checkpoint quality
(value/policy targets, anchor-gate logic, outcome/label backfill).

### Fixed (safe corrections applied)

| # | File:line | Bug | Fix |
|---|---|---|---|
| F-iter5-1 (B1) | `run_selfplay_iter.py:589` | **Anchor/learner scalar-width mismatch silently corrupts training.** `include_farm_scalars` derived from the learner checkpoint only; a single learner-width `Game` feeds BOTH evaluators, so a 12-scalar learner + 10-scalar anchor → wrong-width scalars → anchor forward crashes → server returns **uniform stub priors** → learner trains against a RANDOM opponent, poisoned games recorded unflagged. (Independently confirms the 2026-05-31 config-audit lineage finding.) | Capture `learner_ns`; if `--anchor-checkpoint` set, peek its `n_scalar_features` and `raise SystemExit` on mismatch. Fail loud, same-lineage required. |
| F-iter5-2 (B2) | `~/run_pathb_cluster_loop.sh:125` (untracked launcher) | **`wait_for_count` ALL_DEAD return swallowed.** `set -e` is off, so the `return 1` on the all-PIDs-dead path was ignored → `train_iter.py` runs on PARTIAL data and `--window 10` propagates the poisoned iter into the next 9, silently. | Guarded the call: `if ! wait_for_count …; then … exit 1; fi` — halts like train-failure already does (`:133-134`). |

### Deferred (judgment call for Joshua)

**S1 — `selfplay.py:228,244` — `temp_threshold` counts TOTAL plies, not learner-only plies.** [Minor, disputed 1/1]
In anchor mode `ply` increments on every move but the τ=1 exploration schedule (`ply < temp_threshold`) gates the *learner's* moves — so with alternating play the learner samples τ=1 on only ~7-8 of its own opening moves instead of `temp_threshold`. **Genuine split:** one verifier calls it a real ~halving of learner opening diversity; the other argues game-clock gating (decay tied to game progress, not a per-agent quota) is the correct AlphaZero convention. No data corruption either way; only affects the minority anchor-fraction games. **Recommendation:** a one-line decision — document the game-clock gating as intentional, OR add a `learner_ply` counter. Not a launch blocker.

**Verdict:** safe to launch after F-iter5-1 + F-iter5-2 (both applied). S1 is a clarity decision, not a gate.
