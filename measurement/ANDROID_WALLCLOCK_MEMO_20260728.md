# Android app — EASY WALL-CLOCK GAINS for AI move latency

**STATUS: ADVISORY / MEASURED 2026-07-28. No code changed, nothing committed, no strength
claim made. All timings below are fresh desktop probes taken while the local box was
running the n=600 intra-reuse confirm at W16 — i.e. CONTENDED. Absolute numbers are
inflated; ratios and shares are the load-bearing part.**

Scope: the on-device champion's per-move wall clock (`android_bridge.ai_move` →
`FairHeuristicPriorAgent.choose_action`), k4×688 = 2752 sims/move + exact-K≤2 endgame,
measured at **1.7 s/move on the Pixel 9 Pro** (memory `reference_android_app`).

---

## 0. Ranked table

| # | Lever | Expected saving | Effort | Risk to play-identity |
|---|---|---|---|---|
| 1 | **Bound `exact_budget`** (and expose it). It is hard-coded at 2,000,000 nodes and is not reachable through `make_production_champion`; the largest solve observed in 9 real endgames was **2,214 nodes**. At the measured ~10 ms/node a budget hit is ~5.5 h of solving *on desktop*, with no wall-clock abort and no mid-search cancel. | 0 in the common case; converts an unbounded hang into a bounded one. This is a **safety** fix first, a latency fix second. | ~10 lines (forward the kwarg through `champion_factory` → bridge) | **Changes play only if it fires** — then the champion's own documented `BudgetExceeded` → fair-PIMC fallback for that one decision. At 100k nodes (45× the observed max) it should never fire. Label it. |
| 2 | **Wire the already-compiled Cython terminal scorer into `flat_leaf.flat_base_score`.** It is the exact-endgame solver's leaf and is **pure Python today**; `_decompose_c` / `_final_scores_c` already exist in `flat_leaf_cy.pyx` and already ship in the Android wheel. Measured **≥37% of an 11.9 s latch solve** (915.8 µs × 4,807 calls). | ~1.4–1.6× on the endgame spike (the thing the user actually noticed) | ~half a day + a bit-exactness reconcile + APK rebuild (wheel version is content-addressed off the `.pyx`, so the rebuild is automatic) | **NONE if the gate passes.** Integer-valued output ⇒ exact bit-comparison, precedent `scripts/reconcile_cy_leaf.py`. `verify=True` and the leaf hashes are untouched (different function). |
| 3 | **Copy-on-write the 35×35 board grid** in `CarcassonneGameState.__deepcopy__`. Measured 2.90 µs of the 12.85 µs `get_next_state`, i.e. **~6.7% of every expansion child-step** ⇒ ~6–7% off every move. Exactly **one** production write site (`engine/.../state_updater.py:27`). | ~6–7% of every move (~0.11 s of 1.7 s) | ~1 day incl. a fuzz/golden gate; touches vendored `engine/` | **NONE** (pure aliasing change), but engine-wide — needs the worktree-isolation rule and a full golden run. |
| 4 | **Alpha-beta the post-chance segment of the marginalized solve.** At K=2 everything below the single chance node is pure minimax, so AB is sound there and value-exact at a full window; `_value_ab` already exists. It cuts the *number* of terminal evaluations, which is the term being multiplied. | plausibly ~2× on the endgame spike, on top of #2 | 2–3 days incl. validating bit-identical V* against the no-prune oracle on the solved K2/K3 suites | **NONE if validated** (AB prunes only provably-irrelevant subtrees). The solver's `alphabeta and mode=="marginalized"` assert exists for good reason — it must be narrowed to the post-chance subtree, not removed. |
| 5 | **Set `CARCASSONNE_TT_CAP=200000`** in `android_bridge.PROD_ENV` (the eval harness's value; the app currently sets nothing ⇒ unbounded solver TT). | **Not a speedup** (LEVER_INDEX: "the cap is a safety valve, not a speedup"). Bounds solver RSS on a phone. | 1 line | **NONE** — pure memoization; a missing entry only forces recomputation. Interacts with #1 (more nodes ⇒ closer to budget); 0 timeouts at cap 200000 + budget 2e6 across 400 screen games. |
| 6 | **Gate `refreshOwnership()` on the overlay toggle** (`GameViewModel.kt:771` + the `runAiTurns` loop call it unconditionally, on the shared bridge dispatcher, so it serialises in front of the next search). | **Measured 1.3–1.8 ms.** Negligible. Listed only so nobody re-derives it. | trivial | NONE (read-only bridge call) |
| 7 | **Lower the meeple decision's budget** (the meeple half costs *more* than the tile half — see §2 — while choosing among 2–5 actions vs 16–30). | up to ~0.5 s/move if the meeple half ran at ¼ depth | ~half a day | **CHANGES PLAY.** Needs its own paired screen and a BELOW-CHAMPION label. Not in `docs/LEVER_INDEX.md` — would need a row either way. |
| — | ~~Enable C3-INTRA for speed~~ | **ZERO. Measured wall-clock neutral.** See §1. | — | it is a *strength* question, not a latency one |
| — | ~~`gc.disable()`/`gc.freeze()` around the search~~ | **Measured ~1–2%, inside the noise** (2.176 / 2.133 / 2.225 s means over three matched runs) | — | none — but there is nothing to buy |
| — | ~~Poll-rate / JNI crossings~~ | **Measured `get_progress` = 3–6 µs**, 4 calls/s ⇒ ~0.002% of a move | — | none |
| — | ~~BLAS/thread pins, Cython `-O3`, `boundscheck`~~ | **Already done** (`PROD_ENV` pins OMP/MKL=1; both `.pyx` carry `boundscheck=False, wraparound=False, cdivision=True`; both build paths use `-O3 -DNDEBUG`) | — | — |
| — | ~~Multiprocess / sub-interpreter k_dets~~ | **Dead end under Chaquopy 17.** See §4. | — | — |

**Top 3 by expected-gain ÷ effort: #1 (safety, do it regardless), #2, #3.**

---

## 1. C3-INTRA (`CARCASSONNE_INTRA_TURN_REUSE`) is NOT a latency lever

The brief's premise — "enable it for a large meeple-phase speedup at equal nominal budget"
— does not hold, and the code says why: with the carry ON the meeple decision still runs a
**full `sims` NEW simulations per determinization on top of** the carried visits
(`fair_agent._pimc_move`, and the contract asserted by
`last_intra_root_visits[i] == last_intra_carried_visits[i] + sims`). Nothing is subtracted,
so nothing is saved. What the carry buys is *effective* search depth, i.e. possibly strength.

Measured here (same 4 turns, same position, same seeds, k4×688, `verify=True`):

| | turn-time total (4 turns) | ratio |
|---|---|---|
| intra OFF | 21.966 s | — |
| intra ON | 22.031 s | **1.003×** |

That reproduces the n=200 screen's **0.994×** at the same cell
([DEDUP_INTRA_SCREEN_REPORT_20260728](classical_search/DEDUP_INTRA_SCREEN_REPORT_20260728.md)).

Carried root visits at the **deploy** budget, per world:
`[122, 148, 141, 184]` and `[114, 47, 122, 129]` against `sims=688`
⇒ the warm start is **15–22% of a fresh budget**, not the ~34% quoted in
`docs/LEVER_INDEX.md` — that figure was measured at **k4×172**, where the same absolute
carried visits are 4× the fraction. Anyone sizing an on-device saving off "34%" would be
sizing it off the wrong cell.

**If you wanted to convert the carry into wall clock** you would have to *also* cut the
meeple decision's `sims` by the carried fraction — a code change that does not exist, and a
play change. Ceiling: 0.18 × 0.58 ≈ **10% of a turn ≈ 0.17 s/move**. Not worth the strength
risk. Recommendation: treat the running n=600 confirm purely as a strength decision; if it
lands positive, **bank the strength, do not try to spend it on latency.**

---

## 2. Where a normal 1.7 s move actually goes

Per-child cost inside `make_heuristic_prior_evaluator._legal_deltas` — which runs
`get_next_state` + one leaf **for every legal child at every expansion** (the softmax-Δleaf
prior is what makes an expansion cost `B+1` leaves, not 1):

| term | mid-game (30 tiles placed) | share of a child step |
|---|---|---|
| production Cython float leaf | 29.34 µs | **70%** |
| `Game.get_next_state` | 12.85 µs | 30% |
| …of which the 35×35 board row-slice | 2.90 µs | 6.7% |
| …of which sets / deck / meeple slices | 0.96 µs | 2.2% |
| `string_representation` (once per *node*, not per child) | 51.1 µs | ≈5% of a move |

Scaling with board fill (clean re-measure, cached masks):

| plies | tiles placed | `get_next_state` | `string_representation` | leaf |
|---|---|---|---|---|
| 36 | 18 | 13.4 µs | 54.9 µs | 22.6 µs |
| 60 | 30 | 16.9 µs | 51.1 µs | 25.5 µs |
| 100 | 50 | 17.8 µs | 82.3 µs | 33.2 µs |
| 140 | 70 | 16.0 µs | 104.7 µs | 45.2 µs |

Consequences worth writing down:

- **The leaf is already the optimum it is going to be.** It is the folded Cython port at
  `-O3`; the remaining 70% is intrinsic. There is no easy 2× on a normal move without
  changing `sims`, `k_dets`, or the prior rule — i.e. without changing play.
- **`CARCASSONNE_USE_CY_REPR=1` in `PROD_ENV` is inert for this champion.** It gates
  `board_repr.encode_board`, which only the *neural* path calls. The classical champion's
  transposition key, `Game.string_representation`, is pure Python
  (`game_wrapper.py:631–689`). Harmless, but do not count it as a fast path that is helping.
- **A micro-memoisation of `_tile_rotation_signature` does NOT work** — tried, byte-identical
  output asserted, and it came out **11 µs slower** per key. The cost is building and
  `repr()`-ing ~70 small tuples, not the per-tile call. A faster key needs a real
  reimplementation (Cython twin or incremental hash), not a cache.

Tile-vs-meeple split, measured at k4×688 on turns where the meeple decision is a *real*
choice (`n_legal_meeple` > 1):

| turn | legal tile | tile s | legal meeple | meeple s | meeple share |
|---|---|---|---|---|---|
| A | 30 | 2.801 | 3 | 3.919 | **58.3%** |
| B | 17 | 2.985 | 4 | 4.160 | **58.2%** |

Consistent with the 52.5% on record. Turns whose meeple phase is forced (`n_legal == 1`)
cost **~0 ms** — the forced-move fast path in `_pimc_move` already handles them. Averaged
over all 4 turns (2 forced) the meeple half is 36.8% of turn time.

So the meeple decision spends **more** wall clock than the tile decision while choosing
between 3–4 actions instead of 17–30. That asymmetry is the only large *structural*
inefficiency on the normal-move path — and spending it is lever #7, which changes play.

---

## 3. The endgame spike — what actually bounds it

Measured: play a prefix with Tier-1 (`RuleBasedPlayer`, a real heuristic policy, ~72 tiles
placed) to the first TILES decision with `k_remaining ≤ 2`, then let the production champion
latch and solve. 5 seeds; a second set of 4 seeds with a random-play prefix agreed on shape.

| seed | latch solve (TILES, K=2) | nodes | rest of the endgame | whole endgame |
|---|---|---|---|---|
| 4242 | 1.94 s | 527 | 0.13 s | 2.07 s |
| 777 | 3.11 s | 877 | 0.21 s | 3.32 s |
| 90210 | 4.61 s | 1124 | 0.21 s | 4.82 s |
| 555 | 7.23 s | 2214 | 0.26 s | 7.49 s |
| 31337 | **12.38 s** | 1174 | 0.95 s | 13.33 s |

Two facts fall straight out:

1. **All of it is the first solve.** Once the latch fires, the tile decision pays for the
   whole endgame; the meeple decision and the k=1 turn cost 0.0–0.5 s each. There is no
   "cache the TT across the turn" win to be had — it is already effectively that.
2. **The tail is wide and is not node-count-driven.** Seed 31337 used *fewer* nodes than
   seed 555 and took 71% longer: 10.5 ms/node vs 3.3 ms/node. The variance is in the *cost
   per node*, i.e. how expensive terminal scoring is on that particular board.

Call-count attribution of the 11.89 s seed-31337 solve (counters only — near-zero overhead —
then multiplied by independently microbenchmarked per-call costs, which avoids the cProfile
distortion the house rule warns about):

| primitive | calls | per call | attributed | share |
|---|---|---|---|---|
| `flat_base_score` (exact terminal score, **pure Python**) | 4,807 | 915.8 µs | **4.40 s** | **37.0%** |
| `Game._compute_mask` | 1,175 | 639.9 µs | 0.75 s | 6.3% |
| `Game.string_representation` | 2,374 | 105.5 µs | 0.25 s | 2.1% |
| `Game.get_next_state` | 6,006 | 18.7 µs | 0.11 s | 0.9% |
| accounted | | | 5.52 s | 46.4% |

The unaccounted ~54% is spread (chance-node `_clone_with_tile` deepcopies, `blake2b` over
the 7 KB key string, `np.flatnonzero`, the recursion itself) with no second dominant term;
and the 915.8 µs was microbenchmarked at the *latch* board (72 tiles), while true terminals
carry 74 — so 37% is a **floor** on the terminal-scoring share, not a ceiling.

**`flat_base_score` has a Cython twin that is already compiled and already on the phone.**
`flat_leaf_cy.pyx` contains `_decompose_c` and `_final_scores_c` — exactly the two functions
`flat_base_score` calls — but only exports `flat_virtual_score_v2_cy{,_float}`, and
`flat_leaf.flat_base_score` (line 578) has no `USE_CY_LEAF` dispatch. Wiring it is additive,
integer-valued (so bit-exactness is a straight equality check), and rides the existing
`buildCyWheels` pipeline with no new build machinery. That is lever #2.

### `exact_budget` — the finding that matters most

```
fair_agent.DEFAULT_EXACT_BUDGET = 2_000_000        # nodes
champion_factory.make_production_champion(...)     # has NO exact_budget parameter
android_bridge._Session._build_opponent(...)       # therefore cannot pass one
```

`build_fair_champion` *does* accept `exact_budget`; `make_production_champion` does not
forward it, so the app is pinned at 2,000,000 nodes. Against the observed range
(527–2,214 nodes) that is **900–3,800× headroom**. At seed 31337's 10.5 ms/node, actually
reaching the budget would be **~5.8 hours of solving on this desktop** — on a phone,
unbounded — during which:

- `get_progress` reports `phase: "exact"` with `fraction: null` (the leaf counter does not
  move during a solve), so the UI shows a spinner with no progress and no ETA;
- there is no cancel: `PythonBridge.reset()` queues *behind* the running `ai_move` on the
  single bridge dispatcher (documented in `PythonBridge.kt:86-93`);
- the budget is a **node** budget with no wall-clock component, so no timeout can save it.

0 timeouts were observed in 400 screen games and 9 endgames here, so this is a tail risk, not
a live bug. But it is a tail with no floor, on a device the user holds. Recommendation:
forward `exact_budget` and set the app to **100,000 nodes** (≈45× the largest observed solve,
≈15 min worst case at desktop rates). Keep it a *node* budget — a wall-clock budget would
break the `(deck_seed, action_log)` replay determinism the save/archive contract depends on.

Cheap companion (no code, UI only): `get_progress` could surface `agent.solver_nodes /
exact_budget` while `phase == "exact"`, turning a dead spinner into a real bar.

### On-device translation

Mid-game k4×688 moves measured here: 2.63–4.42 s (mean ≈3.4 s over 8 samples) against the
phone's 1.7 s ⇒ **phone ≈ 0.5× this contended desktop**. Applying that factor to the latch
solves gives **≈1.0 / 1.6 / 2.3 / 3.6 / 6.2 s** on the Pixel. That is the "end-game moves take
longer" the user noticed: median ~2.3 s vs 1.7 s, tail to ~6 s.

⚠️ Treat 0.5× as the **optimistic** end for the solver specifically. The search is
Cython-dominated; the solver is pure-Python-dominated (see the table above), and interpreter
work usually scales worse on ARM than compiled work does. The real on-device endgame tail is
plausibly worse than 6 s.

---

## 4. Parallelism — honest answer: dead end under Chaquopy 17

The four determinizations are independent and would parallelise perfectly. They cannot,
because:

- **`multiprocessing` has no usable start method.** `spawn`/`forkserver` need to re-exec a
  Python interpreter; on Android there is no standalone `sys.executable`. `fork` avoids that,
  but `multiprocessing.Queue`/`Pool` pull in `multiprocessing.synchronize`, which needs POSIX
  named semaphores (`sem_open`) that Android does not implement, and there is no `/dev/shm`.
- **Sub-interpreters are not a route either.** A per-interpreter GIL is a 3.12 *C-API* feature;
  the Python-level `interpreters` module is 3.13+, and neither NumPy nor the `carc_cy`
  extensions declare multi-phase init / per-interpreter state.
- **Threads do not help**: the Cython leaf operates on Python objects throughout and never
  releases the GIL, and the search itself is pure Python.

The only in-principle path is a hand-rolled `os.fork()` + `os.pipe()` + pickle fan-out (4
children, one determinization each, parent pools by `pooled_q_argmax` — which is
order-independent and seeded per-`(move_idx, det_idx)`, so the result would be *identical*).
Ceiling ~4×. But: forking an ART process without exec is fragile, it would need its own
crash/battery/thermal story, and it is a multi-day spike with a real chance of returning
nothing. **Not easy, and not recommended** while levers #1–#3 are unspent. If it is ever
attempted, the cheap first step is a 30-minute on-device spike that only proves `os.fork()`
+ a pipe round-trip survives inside Chaquopy — do not build the fan-out first.

Note also `docs/LEVER_INDEX.md`: **root parallelism is recorded as NEVER-TRIED and
NEVER-NAMED** in this project. If any of the above is pursued, that row needs updating.

---

## 5. Play-identity ledger

**Wall-clock-neutral to play (must keep `verify=True` green, leaf hashes untouched):**
lever #2 (needs a bit-exactness reconcile), #3 (needs a golden/fuzz gate), #5, #6,
`get_progress` node reporting, poll-rate changes.

**Changes play — needs strength evidence and/or honest below-champion labelling:**
lever #1 *only in the branch where the budget fires* (the champion's documented
`BudgetExceeded` → PIMC fallback; the `budget_note` mechanism in
`_Session._build_opponent` is the right place to say so), lever #7, any `sims`/`k_dets`
reduction (already handled honestly by the difficulty slider), and enabling C3-INTRA
(a strength decision gated on the running n=600 confirm — **not** a latency decision).

---

## 6. Method / reproduction

All probes: single process, `nice -n 19`, `android_bridge.PROD_ENV` applied before the first
`carcassonne_ai` import, agents built through `champion_factory.make_production_champion(
"fair", ..., verify=True)` so the runtime leaf guard was live in every run. Cython leaf
confirmed bound (`flat_leaf.USE_CY_LEAF == True`, `USE_FLAT_LEAF == True`). The local box was
running `eval_fair_puct.py --intra-reuse --n 600` at W16 throughout; the probes were never
allowed more than one core and nothing in the repo was modified.

Probe scripts (scratchpad, not checked in):
`probe_latency.py` (first pass), `probe2.py` (`mid` / `endgame`), `probe3.py` (per-child
cost breakdown), `probe4.py` (GC), `probe5.py` (key/leaf scaling), `probe6.py` (signature
memoisation, negative result), `probe7.py` (bridge-side overhead), `probe8.py` (Tier-1-prefix
endgames), `probe10.py` (solve call-count attribution).

Not done, and worth doing before funding lever #4: a proper `py-spy` profile of one latch
solve (the `record` attempt here failed on ptrace permissions, so the attribution above is
call-counts × microbenchmarks rather than sampled — good enough to rank, not good enough to
size a 2–3 day change).
