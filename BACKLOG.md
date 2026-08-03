# Backlog

Parking lot for ideas, distractions, and things-to-do-later that come up during work on the main project. **Do not action items in here without explicit approval from Joshua.** This is a capture-and-forget tool, not a TODO list.

When something goes in: timestamp it, one-line description, why it's not being done now.
When something comes out: either it gets promoted to an actual phase, or Joshua deletes it.

> ⚠️ **Read every entry's "why deferred" as point-in-time.** Many entries below were written under premises that have since expired ("the recipe still compounds", "the champion is a net", "value learning is the live lever"). Two companions, both mandatory before actioning or re-proposing anything here:
> **(1) [docs/BACKLOG_REAUDIT_2026-07-13.md](docs/BACKLOG_REAUDIT_2026-07-13.md)** — every item re-scored against *current* premises.
> **(2) [docs/LEVER_INDEX.md](docs/LEVER_INDEX.md)** — the intervention index; several ideas parked here were later tried and killed, and the index is where that shows up under the name you'd grep.

> Cleaned 2026-05-16: removed landed items (batched GPU inference, in-place state mutation, fp16 inference, Phase 3 prerequisites, self-play temperature sampling, rule-based Tier-1 player), dead v1-v6 recipe entries (v2/v3 recipe fixes, v7 candidates framing, right-size-box, S-curve v6 diagnosis, c_puct sweep continuation — the recipe question is resolved, see DECISIONS 2026-05-16), and the orchestrator-GIL null result (lives in DECISIONS). Kept ideas are still valid for the v2.7-retrain line.

## Captured ideas

## 2026-08-02 — Differential rules oracle (JCloisterZone as external referee) — ✅ BUILT + VALIDATED 2026-08-03 (F9/D1)

> ✅ **DONE — this is no longer a backlog item.** Built as roadmap **F9/D1** and validated the same
> week it was captured: **43/43 uncontaminated games agree on exact final scores** under `fixed_v1`+R9
> (zero divergences of any class; an E4 human-vs-champion game reproduced at 111–113), the meeple-slot
> mapping semantically verified 121/121, and it **found R9** (the RCr tile claiming a field on its city
> edge) before any number was taken. It is now a permanent CI referee — `tests/test_jcz_replay_oracle.py`,
> ~1.2 s. → [VALIDATION_REPORT.md](measurement/jcz_oracle_20260803/VALIDATION_REPORT.md), DECISIONS
> 2026-08-03 (early + mid-morning), roadmap F9. *(Original capture follows.)*
**Context:** the border + cloister-rebinding bugs are RULES-FIDELITY divergences — invisible to every
self-consistency gate by construction (both sides of every comparison play the same wrong rule; the Rust
port certifies them bit-exactly). The rulebook audit (docs/RULES_FIDELITY_AUDIT_20260802.md, launched
2026-08-02) is the cheap sweep; THIS is the machine-checkable form: an adapter replaying our
`(deck_seed, actions)` archives through an independent mature implementation (JCloisterZone — Java,
rules-complete, no shared code) and diffing legality + scores mechanically. Shared-wrongness impossible.
**Cost:** ~an agent-day (save-format adapter + tile-id mapping + scoring extraction). **When:** bundle
with the F9 re-baselining program — the oracle certifies the FIXED rules before re-measurement, and
doubles as a permanent CI referee. Joshua raised the class 2026-08-02 ("bad taste in my mouth").

## 2026-07-31 — Shared-claim launcher hardening: no-progress abort on the retry loop
⚠️ **ROOT CAUSE CORRECTED (the first post-mortem blamed contention; it was a BUG CLASS).**
The leaf-ablation launcher's `while count<N && iter<60` retry loop spun ~5 h relaunching 16
games that could never finish: the worker raised `action_space.WindowOverflowError` ~40–60 min
into each game (the capoff candidate's play sprawls into the grid wall until the 25×25 centroid
window can encode no legal move), the pool died recordless, and the launcher relaunched into the
**identical deterministic crash** — same CRN decks, same outcome, forever. Nothing anywhere
noticed zero progress (DECISIONS 2026-07-31 Shabbat eve; the operator-side rule is memory
`no-agent-compute-beside-eval`). ⚠️ **This changes the fix:** cross-workload contention only
STRETCHED each crash cycle (~11 min → 40–65 min) and made it look like a timeout problem — that
is the operator-side lesson, not the root cause — so a wall-clock or load-aware guard would NOT
have caught this. Only a **no-progress abort** would. Hardening: any
shared-claim retry loop should track records-at-iteration-start and ABORT LOUDLY (STALLED
row + nonzero rc) after N (say 2) consecutive zero-new-record iterations, instead of
spinning; optionally print a load warning when loadavg >> W at iteration start. Applies to
`leaf_ablation_launcher.sh` and any future launcher cloned from it (c7_s1 pattern).
**Addendum 2026-08-01:** `run_watchdog.sh`'s worker-detection pgrep ALSO false-positives —
a laptop instance reported "healthy: workers alive" for 33+ h against a dead cell (its
`pgrep -f 'seed-start …'` matched something the `$$`/`$PPID` exclusion misses — a variant
of the bug 4e67f2b claimed fixed). Same fix window: make the health check require actual
worker pids (match the harness script path AND exclude self/ancestors by walking ppid).

## 2026-07-17 — Laptop GEN W-sweep (never done; the local W20/f4 result does NOT transfer)
**Context:** This session settled the LOCAL distill-flywheel gen config via a full W + forwarder sweep — W20 knee, forwarders=4, gen is dispatch-latency-bound, ~5400 fwd/s ceiling (detail + VALIDITY SCOPE in `measurement/distill_flywheel_20260715/HANDOFF.md` "LEVERS EXPLORED"). Those numbers are valid ONLY for the sims200 net-prior gen on the LOCAL 5900XT box + its GPU.
**Idea:** If the laptop ever runs GEN — a net-free champ-anchor side-stream, or joining the flywheel's net-prior gen — it needs its OWN gen W-sweep. It won't transfer from local because: (1) different/weaker GPU (mobile), (2) different profile (net-free champ-anchor is CPU-bound; net-prior gen is dispatch-latency-bound), (3) the laptop is RAM-capped (~11 GB). We only ever swept the laptop CONFIRM (one-net-side eval, ~W12-16 optimum) — NOT gen.
**Why deferred:** the laptop currently only runs the n=200 confirm; no laptop gen role is live yet. Do the sweep when/if we actually put the laptop on gen (e.g. wiring the champ-anchor stream there).

## 2026-06-29 — Adaptive-compute escalation scheduler — ❌ CLOSED FOR STRENGTH (CL-035 / Decision C); efficiency-only candidate, deferred
**Context:** The Post-Search Residual / Adaptive-Compute pilot (DECISIONS 2026-06-28, **CL-035**, `measurement/post_search_residual/`) retargeted from `h6400 − static_leaf` to **`h6400 − h200_search`** and asked: can we predict where shallow search is still wrong vs h6400 and escalate deep search only there, beating uniform compute at matched average sims? **Result = Decision C.** A perfect oracle beats uniform decisively (+92.5% @ matched C=400; residual is extreme-tail-concentrated — worst 5% of roots = 67% of all h200 regret), and the escalation signal IS predictable — but a **one-line heuristic `low_top2gap`** (escalate when h200's top-2 backed-up Q are nearly tied) captures it, a learned MLP+structural model does **not** robustly beat it (bootstrap P=0.92 @C=400, CI crosses 0; 0.54 @C=800), and the magnitudes are tiny (mean regret 0.0031; oracle removes ~0.0016; achievable ~0.0003–0.0006) → below game-resolution.
**Strength verdict: CLOSED — do NOT re-suggest adaptive compute (learned OR heuristic escalation) as a STRENGTH lever.** It is the 4th instance of the `b99c9ed` "root metrics don't convert to game strength" pattern; no ML scheduler, no flywheel justified.
**Idea (efficiency-only, deferred):** a *heuristic* (not ML) escalation scheduler — run h200, escalate that root to h800 only when the h200 top-2 Q gap < τ — as a **compute-EFFICIENCY** tool: reach the *same* strength at fewer *average* sims (spend the saved compute where it's wasted on already-decided roots). NOT a strength play. The offline matched-compute edge is ~0.0003 mean Q-regret, so validating it needs a **large-n paired game screen** (adaptive avg≈400 vs uniform h400) — small effect, easily a null.
**Why deferred:** efficiency-only, not on the superhuman-strength critical path; the expected effect is small and may not survive a game screen; needs Joshua sign-off + a clear "are we optimizing compute now?" boundary before spending on the game test. Capture-and-forget; reusable infra already exists (`scripts/post_search_residual/`: lossless MCTS-game replay, snapshot-search dataset builder).

## 2026-06-21 — Endgame solver memory: make/unmake is the real lever; compact keys only ~1.5× (K=5 prerequisite)
**Context:** The K=4 multi-source probe (`endgame_solver.py` AB clairvoyant) hit a hard memory wall — ~10–12GB/worker on "monster" positions — forcing low W. I first hypothesized the bloat was the fat `string_representation` TT key and that compact keys would dissolve it ~200×. **MEASURED (2026-06-21) and that was WRONG — corrected below.**
**What the measurement actually showed (committed `6f9dd08` = compact keys):**
- A 400k-node monster's RSS = **4.92GB**, of which the TT (compact) is only **0.04GB** and the projected string-key TT would be **2.80GB**. So the dominant cost is **~4.88GB of TRANSIENT object churn** — the per-node `get_next_state` **deepcopy** of the engine state — NOT the TT keys.
- The transient churn **plateaus** (Python reuses freed arenas as the DFS unwinds), so it scales sub-linearly with nodes; 1M-node monsters settle ~7GB compact (vs ~12GB string).
- **Compact 128-bit keys (DONE, validated bit-identical 12/12 incl. exact node count) buy only ~1.5–1.7×** (remove the string-TT half): monster ~12GB → ~7GB. Enables ~local W=5 / Xeon W=2 / laptop W=1-uncapped (all solve monsters) vs pre-compact 3/1/1-capped. Real but modest; W is STILL memory-limited because transient churn dominates.
**The REAL lever for K=5 = make/unmake (kill the transient churn):** replace per-node `copy.deepcopy(state)` + new Board with an **incremental apply/undo** on a single mutable state (push the diff, recurse, pop). That removes the ~5–7GB/worker transient entirely → monsters become ~TT-sized (now tiny with compact keys, ~0.1GB) → **then** W=ncores uncapped is real. It reuses the trusted engine transition (validate bit-exact vs the current solver, like the AB gauntlet). ~3–5× per-solve speedup too (no deepcopy). This is the change that actually makes K=5 tractable; compact keys alone do not.
- A memory-aware governor (W=ncores + admission-gate on `psutil available`, solve-start lock for the race) is a fallback if make/unmake is deferred — but with make/unmake it's unnecessary. The TT-cap (`CARCASSONNE_TT_CAP`, freeze-at-cap) is correctness-neutral but NOT a throughput fix (~7.8× node inflation; only shrinks the solved set) — laptop safety valve only.
**Why deferred:** Joshua wants K=4 finished now (running on compact 3-box). Build **make/unmake before the K=5 feasibility probe** — K=5's deeper trees make the deepcopy churn worse, and it's the binding constraint, not the TT.

## 2026-06-14 — Flywheel orchestrator: graceful degradation on a remote-box outage (HOSTS knob)
**Context:** Overnight 06-13→14 the **laptop dropped off Tailscale AND xeon's ssh died** (box pinged but both WSL-proxy + Windows sshd unreachable). The deeper-teacher run (iter9) churned and **burned all 6 chain-watcher relaunches → parked at iter9** (gen 355/400). Root cause was infra, not code, BUT the orchestrator amplified it: `run_residual_flywheel_v2.sh` **hard-codes the 3-box fan-out** (5800x local + `_ssh_bg laptop` + `_ssh_bg xeon`) in `_gen_launch`/`_eval_launch` with NO HOSTS knob. A dead remote → ~60s/cycle wasted on ConnectTimeout×3 retries + lost capacity → gen stalls → heal/FATAL → chain relaunch → repeat until RELAUNCH_CAP=6 exhausts.
**Idea:** (1) **`HOSTS` env knob** (default "5800x laptop xeon") so a run can be launched/resumed on a partial cluster without churning on dead boxes. (2) **Pre-flight + periodic reachability probe** — drop an unreachable box from the active set for the iter (re-add on recovery) instead of blocking on its ssh each cycle. (3) **Don't count a dead-remote-induced stall against RELAUNCH_CAP** the same as a real crash — or raise the cap / make it time-based. (4) Chain watcher could detect "all relaunches failed at the same iter with the same remote-ssh error" and pause-with-alert rather than silently exhausting.
**Why deferred:** infra-hardening, not a strength lever; needs Joshua sign-off + a non-running-flywheel boundary. Today's workaround = wake/restore the boxes then resume (STATUS resume recipe). The single-box fallback isn't worth building unless multi-box outages recur.

## 2026-06-14 — Telemetry-gate stall-window < game-time at high sims (heal-loops → wasted hours)
**Context:** Resuming deeper-teacher at SIMS=800, the per-iter telemetry gate (`gate_it${it}`, n=300, `_run_eval … stallmax=12`) **heal-looped to HEAL_CAP on the iter it ran**. Root cause: `_run_eval` heals when the game-count is flat for `stallmax` polls × `sleep 30` → stallmax=12 = a **6-min stall window**, but at 800 sims one game takes **~16 min**, so a *fresh* gate (0 cached) can never complete a game before the heal kills the pool → guaranteed loop → cap. NON-fatal (launcher line 273 is `|| { … continuing }`, unlike the iter0 gate at line 200 which is `|| exit 1` — that one WOULD abort) but burns ~1 h/iter for zero telemetry. The *selection* (`stallmax=20` = 10-min window) survives only marginally — the shortest games finish ~8–10 min, just inside it — and reliably only because it usually resumes from cached games. Workaround this run: `TELEMETRY_GATE=0` (gate is the discredited non-authoritative proxy anyway).
**Idea:** make `_run_eval`'s stall window **sims-aware** — floor it at ≥ ~2× the measured single-game wall-clock at the run's SIMS (or pass explicit minutes) instead of a hard-coded 12/20. Bump the selection margin too (10 min is too tight at 800 sims). Cheapest correct fix: detect "0 completions but pool alive + CPU busy" as not-a-stall.
**Why deferred:** gate is OFF for the rest of this run; needs a non-running boundary + sign-off. Fix before the next *gated* high-sims run or it silently wastes hours (and the iter0 `|| exit 1` gate could abort a fresh high-sims run outright).

<!-- Format:
## YYYY-MM-DD — [short title]
**Context:** what we were doing when this came up
**Idea:** what the thing is
**Why deferred:** out of scope / premature / nice-to-have / needs Joshua decision
-->

## 2026-06-12 — Two small throughput candidates from the deps/leaf audit (clean boundary only)
**Context:** Joshua asked (a) whether outdated Python/CUDA deps were costing us speed, (b) for an easy latency fix in the leaf. Audit: the stack is current (Python 3.12.3, torch 2.11+cu128, numpy 2.4.4, cuDNN 9.19) — no version rot; the hot path is pure-Python dict/list work + tiny-tensor latency, so BLAS/CUDA versions are near-irrelevant. The production flat leaf is already de-objectified; profile = decompose-enumeration ~45% / union-find bookkeeping ~22% / label+find ~9% / residual enum-hash ~8%.
**Ideas (both deferred, neither is a strength lever):**
  1. **CPython 3.12 → 3.14 bench.** The 3.13/3.14 interpreter work is ~5–10% on exactly our profile (pure-Python interpreter time). Cost: rebuild venvs on all 3 boxes + revalidate torch → a clean-boundary job. Bench single-box first (`uv venv` with 3.14, run the fixed-seed selfplay bench) before any cluster rollout.
  2. **Residual enum-key swap in `flat_leaf.py`.** The root-position sets still key on `(r, c, Side)` enum tuples (lines ~285/325) — the last ~8% of enum hashing. Swap to int `side_ix` keys; output-identical (keys never leave the function) but needs the reconcile gate re-run. ~5–8% per leaf at best.
**Why deferred:** flywheel mid-run (no leaf edits, no venv changes); both are throughput-only. Don't action without Joshua.

## 2026-06-12 (pm) — Cython leaf + window-offset — ✅ BOTH FOLDED TO PRODUCTION 2026-06-17. DON'T re-suggest.
> **FOLDED 2026-06-17** (between-runs boundary, post-deepteacher): Cython flat-leaf (`f48ffd1`, default-ON + graceful Python fallback) + O(1) window-offset (`62d3772`). Bit-exact-reconciled on ALL 3 boxes (5800x/laptop built, xeon got the py3.12 `.so` by copy). ~1.5× heur search / ~1.3× cycle. Per-box build `python setup_flat_leaf_cy.py build_ext --inplace` (`.so` gitignored). Original dev/profile notes kept below for history.
**Cython flat-leaf port (built + clean-benched, default OFF).** Worktree branch `worktree-agent-a1588eba8dbe3e8f6`, commit `dd893e4`; `src/carcassonne_ai/flat_leaf_cy.pyx` + `CARCASSONNE_USE_CY_LEAF` flag (additive, lazy-redirect; unset = compiled module never imported). **Bit-exact** (0 mism / 345k position-player evals across 3 configs; root ids bit-identical). **Clean bench (idle box): 12.5× isolated leaf** (345→27.5 µs), **but leaf = only 27.4% of a HeuristicMCTS@800 search** → measured end-to-end **≈1.23× cycle** (eval ~1.34×, gen ~1.14× GPU-bound, train 1×; ~1.5h off each ~8h cycle). 12.5× already captures ~97% of the achievable leaf win (ceiling 1.38×) → no further leaf opt worth it. **Fold = SUPERVISED clean boundary** (iter6→7 chain handoff or post-run): needs a per-box native `.so` build (5800x/laptop/xeon) + per-box reconcile re-run + flag flip; partial build = boxes crash loud on `ModuleNotFoundError` → never deploy unsupervised. Correctness-safe (bit-exact = no ruler change, no re-sweep). Fold steps in the worktree's `CYTHON_LEAF_REPORT.md`.
**Self-time profile (heur@800 search) — py-spy (undistorted sampling, USE THIS) vs cProfile (distorted):** LEAF **27.1%** (cProfile 17%self/27%cum; Cython DONE 12.5×) · `compute_window_offset` **12.3%** (cProfile 8.6% — UNDERstated; fix DONE) · stdlib primitives (hash/set/dict) **16.1%** (cProfile **37%** — OVERstated ~2.3×) · ENGINE feature/score 15.5% · MCTS tree-ops 6.6% · coord/side objects 5.2% (de-objectify removes only ~0.9% = the null) · string_representation 3.1% · state-access 4.2% · board-mutation 4.1% · move-gen 1.7%. **py-spy folded stacks `/tmp/pyspy_folded.txt`; parser `/tmp/parse_pyspy.py`.** **Verdict: no other good Cython target** — the leaf was unique (separable + frozen + already int-flat). Cython does NOT help the engine/object-model tax (objects stay Python objects across the C boundary); the only path is DE-OBJECTIFICATION (ints+flat arrays, like the leaf already is) — but see the spike result below: **the cheap version is a NULL and the full version caps at ~1.3–1.6×.**
> **⚠️ SCOPE-CORRECTED 2026-06-17 — this "no other Cython target" verdict was the `heur@800` SEARCH profile, which has NO network → NEVER calls `encode_board`.** The NEURAL self-play/eval path (production gen + the 64%-of-cycle eval gate) DOES call `encode_board` once per leaf, and there it was ~15% self / ~25% cum — the next good Cython target. **Ported: `flat_repr_cy.encode_board_cy` (`1b55721`), bit-exact (28,988 encodes 0-mism), 18.25× isolated / 1.275× (−21.6%) single-process end-to-end, DEFAULT OFF.** It qualified precisely on the leaf's criteria (separable + frozen tile→repr is cacheable + union-find/numpy-fill interior is int-flat). So the 06-12 verdict held only for heur-search; the neural path had one more. **Remaining open Cython/de-obj items (still deferred):** the two `flat_leaf.py` residual-enum / py3.14 ideas above, and the multi-week full engine de-objectification (still NOT worth it — gen/train GPU-latency-bound). DON'T re-suggest `encode_board`. See STATUS/DECISIONS 2026-06-17.
**🔴 DE-OBJECTIFY ENGINE — SPIKE RAN 2026-06-12, cheap cut = NULL (branch `worktree-agent-a659ae688bb3dbf22`, commit `6050ecd`, default ships unconditionally since bit-exact).** Cut #1 (cheap-hash the Coordinate/Side objects: cached int `__hash__`/`_ix`, injective packed-int `_key` for single-compare `__eq__`, `__slots__`, preserved original tuple-hash so set iteration order stays byte-identical). **Bit-exact: 120 games / 17,270 plies / 0 mismatches** (legal moves+indices, full-state digest, both `flat_virtual_score_v2` AND `virtual_score_v2` leaf ints, terminal scores; byte-identical move sequence OLD==NEW); farm determinism doubly proven (2,296 cross-starts / 0 mism); **pytest 423 passed** (the 1 fail is a pre-existing jsonschema env artifact, reproduces on pristine). **BUT end-to-end heur@800 search = BREAK-EVEN (mean OLD/NEW 0.993, Amdahl ceiling ~0.9%):** per-op wins are real (`CoordinateWithSide.__eq__` −48%, `hash(Side)` −16%) but the ops are 70–140 ns each and the construction `_key` cost (+3% on builds) cancels the eq/hash win. **This HARD-CONFIRMS the cProfile-overstatement lesson: cProfile's "~14% object tax" for these ops was really ~0.9%** (they're the highest-call-count fns → maximally inflated by per-call profiler overhead). **Cuts #2 (int-key engine sets) and #3 (full state-array rewrite) NOT made** — cut #1's ceiling killed the cheap-win thesis. **Fuller-rewrite assessment:** a flat int/numpy state engine (extend `flat_leaf.decompose`'s pattern to apply_action + points-collection + move-gen + copy-free rollout) targets ~40–45% of search CPU but realistically caps at **~1.3–1.6× per-search / ~1.1–1.2× cycle** (much of that 40% is irreducible union-find/flood-fill/score arithmetic, not object overhead; calibrated off flat-leaf's 2.26×-leaf→+8%-cycle) — a **multi-week project, NOT worth it while gen/train are GPU-latency-bound.** Cut #1 is safe-but-useless: fold ONLY opportunistically alongside another engine-touching change, never standalone. Report: worktree `DEOBJ_ENGINE_REPORT.md`.
**🟢 `compute_window_offset` incremental — DONE + bit-identical (branch `worktree-agent-aedf22c2f3ce51fd9`, commit `775a8c0`).** `game_wrapper.py:199` rescanned the whole 35×35 board for the placed-tile centroid on EVERY `get_next_state` (incl. every rollout state). Replaced with O(1) incremental running sums (only `TileAction` updates them; meeple/pass are no-ops — verified `play_tile` is the sole `placed_coords` writer). Gate: 140 games / ~20.1K plies / 80,572 offset+sums checks (both new-Board and inplace-rollout paths, full games) → **0 mismatches**; `pytest -k offset/board_repr/wrapper/mcts/rollout` 136 passed. Bonus: fixed a latent bug (`diag_value_leaf.py` bare `Board(...)` left sums at 0) + a stale "first tile auto-placed" docstring (it isn't). **ROI (CORRECTED by py-spy 2026-06-12 — earlier "~few %" note was WRONG):** un-profiled per-call is 4.27× (3.25→0.76 µs). Whole `get_next_state` is only 1.04× on the deepcopy/new-Board path (offset is a sliver vs `apply_action`'s deepcopy) — but the SEARCH runs the deepcopy-free **inplace rollout** path, where offset is heavy. **py-spy (undistorted sampling) puts `compute_window_offset` at 12.3% of the heur@800 search self-time** — i.e. cProfile's 8.6% UNDER-stated it (heavy-per-call full-board scan; its attribution was stolen by the millions-of-calls primitives → NOT a cProfile-overstatement victim, contra my first note). So the fix is a real **~9% search win** (12.3%×(1−1/4.27)), the 2nd-biggest cheap lever after the Cython leaf. Worth folding (free, bit-exact, removes an O(board-area) term that worsens as games grow); clean boundary + per-box reconcile. **Leaf (Cython, 27% at 12.5×) + this (12.3% at 4.27×) together ≈ 1.5× on the heur@800 search ≈ ~1.3× cycle.**
**Why deferred:** all three perturb the live flywheel (native build / venv / hot-path tree edit). Action at a between-runs boundary with Joshua reachable.

## 2026-06-11 — Replay-window A/B for the selection-gated flywheel (accepted-iters-only)
**Context:** Joshua asked why `train_iter.py` has a `--window` (replay-buffer) flag we don't appear to use, and whether we ever tried it. History check: the flag is the ORIGINAL Phase-4 design (commit 79905cd) — `_select_buffer_files(root, iter, window)` trains iter N on the last `window` iters' `.npz` under one accumulating root. It ran LIVE for all 13 iters of `run_pathb_cluster_loop.sh` (`--iter $N` against the single accumulating `pathb_loop/` root, iter_00..iter_12; 7,629 games — our biggest lineage). The newer selection-gated loops (flywheel v1/v2, `lever_sequencer`, `rank_sweep`) all pass `--iter 0` against a per-step FRESH `iterN_data/` dir → the window collapses to that step's 400 games. That collapse is **intentional**, not a bug: warm-from-best + external-selection + reject-if-not-better means accumulating a (possibly-rejected) step's games would pollute the next train; each candidate is meant to be a clean independently-judged net on its own fresh on-policy data. (Architectural read from the code — there is NO explicit "we dropped the window because X" line in DECISIONS.md; worth recording one if we revisit.)
**Idea:** We have run BOTH designs but never a CONTROLLED isolated A/B of the replay window as the single variable (pathb-windowed vs flywheel-single-batch differ in window AND selection AND warm-from-best AND leaf — confounded). Test: in the current flywheel architecture, train iter N on a small window (last 2–3 **ACCEPTED** iters only, not naïve accumulation — that's the rejection-pollution guard) vs the current single-400-batch, all else identical, and read the per-iter external-selection delta. Data + the `--window` code already exist; the only wiring is pointing `--output-root` at a shared root that symlinks/holds accepted iters' gen dirs and passing the real `--iter N`.
**Expected ceiling caveat:** a replay window is a sample-efficiency / training-variance win (each game reused across more updates, more diverse batches), NOT a v2.7-leaf-ceiling break. Don't expect a strength jump — expect cleaner/cheaper iters. Same "helps the warm start, doesn't break the wall" caveat as every other within-v2.7 tweak.
**Why deferred:** changing the training recipe mid-run perturbs the live "does the deeper-teacher gain COMPOUND?" flywheel (pid 553974, iters 3→6). Action only at a clean between-runs boundary, and only with Joshua's sign-off. Capture-and-forget for now.

## 2026-06-09 — Compact leaf: Phase-4 bench + the `CANONICAL_BONUS_SUM` decision
**Context:** Built the compact flat-union-find leaf rewrite on branch `leaf-rewrite` (logic-exact, default OFF; see DECISIONS 2026-06-09 (leaf) + docs/COMPACT_LEAF_REWRITE_ASBUILT_2026-06-09.md). Validation is done; perf and the determinism fix are deferred.
**Idea:** Three follow-ups, none to be actioned without Joshua:
  1. **Bench the compact leaf (Phase 4, quiet box).** Compile the union-find core (numba `@njit cache=True`, or Cython-AOT) — numba is NOT installed and must not go into the shared venv mid-flywheel. Success = it MOVES the bandwidth wall (per-worker erosion flattens, saturation-W rises >16 via `scan_loww.sh`), not merely "faster". Pure-Python as-built is correctness-only, likely NOT a win yet.
     - **→ KILLED AS SCOPED 2026-06-11 (cheap microbench, no env change).** `microbench_compact_leaf.py` (n=20): `_label_components` (the numba target) is only **4.7% of build self-time** → numba-on-the-core caps ~5%, NOT a bandwidth-wall move. The dominant cost is engine-object **enumeration** (`enum.__hash__`/`builtins.hash` of `Coordinate`/`FarmerConnectionWithCoordinate`, `opposite_farmer_side`, object creation) — numba can't touch Python objects. The genuine win needs a **de-objectified enumeration** (build the flat-int edge list without instantiating/hashing engine objects) = a bigger engine-level rewrite; only worth it if/when leaf throughput is the binding constraint. **Don't do the numba bench.** Correctness IS banked: `reconcile_compact_leaf.py` n=40 → compact ≡ production bit-identical (93604 farm + 58021 city partitions, scores[], virtual_score all 0-mismatch); `--canonical` (math.fsum) drives closure-bonus float drift 12→0 = a true bit-exact drop-in. So `USE_COMPACT_LEAF` is a correct, ready-but-speed-neutral drop-in.
  2. **Decide on `CANONICAL_BONUS_SUM` (math.fsum bonus).** Independently worth doing: the v2.7 closure bonus currently sums floats in hash-seed-dependent SET order, so the leaf — the measurement ruler — gives different ints for the same position across workers in ~1e-4 of evals. fsum makes it deterministic + lets compact be truly bit-exact. Cost: changes production output vs any running flywheel by those ~1e-4 ±1 flips → adopt at a clean boundary (with the compact merge), never mid-run.
  3. **Merge gate:** only if BOTH provably-equivalent (the `reconcile_compact_leaf.py` gate) AND meaningfully faster → propose merge to `stage-b-wiring` + bundle refresh as a separate decision; wire into `eval_provenance.py` if it becomes production.
**Why deferred:** the box was running attempt-#2 (no benchmarking allowed); the determinism fix is a deliberate production-output change needing Joshua's sign-off at a non-flywheel boundary.

## 2026-06-02 — PreToolUse "failure-mode linter" hook (PROJECT-SCOPED only)

**Context:** Joshua noticed the same failure modes recur across threads and asked whether a hook could catch them. A transcript-audit agent mined the last 7 days (8 files, 645MB) — its findings RE-PRIORITIZED the rule set below.

**Audit reframe (important):** the "parallel tool call cancelled" pattern (262×) is NOT a tool-batching bug — 0 multi-tool messages in 6,953. It's 8 USER INTERRUPTS of long single Bash calls, each cascading. Root cause = the blocking-`sleep` polling habit (447 sleep calls, ~2.8h of deliberate blocking). So the polling habit, not parallelism, is the dominant cost.

**Two hooks (build PostToolUse logger first — passive, zero-risk):**
- **PostToolUse logger** → append failures to `<project>/.claude/tool_failures.jsonl` (ts, tool, command, error sig, cwd). Mine the small log instead of re-chewing 645MB transcripts. ⚠️ verify which failure classes PostToolUse actually sees (Bash nonzero: yes; harness-validation like Read-before-Edit / parallel-cancel: maybe not → still need occasional transcript mining).
- **PreToolUse blocker (`Bash`)** — audit-prioritized:
  - **Tier 1 (block), TOP = reject foreground `sleep ≥10s`** → steer to Monitor / `run_in_background`. Kills the 447-sleep habit + all 8 interrupt-cascades at the source. THE highest-ROI rule (was not the original top pick).
  - **Tier 1 #2 = CIFS-path validator (NEW finding N1):** assert a `carc-shared` path matches the box (`/mnt/c/carc-shared` on 5800x vs `/mnt/carc-shared` laptop/xeon) or that `mountpoint -q` passes. 27 failed turns came from this. Cheaper alt: a `$SHARE` env convention + a box→mount table in CLAUDE.md.
  - **Tier 2 (advisory):** `--seed-start` without `--shared-claim` (work-stealing nudge); backgrounded `python &` without detach; cluster launch without `nice -n 19`.
  - **Demoted (mostly under control now):** xeon ssh operator-mangling (only 5/44 errored), pkill `|| true` (minor). Don't lead with these.
  - **NOT hookable → CLAUDE.md/memory:** parallel ssh (one call at a time), Read-before-Edit (harness-enforced; 22 hits, half on hot docs → pre-load DECISIONS/MEMORY/PATH_B at session start instead).
- Start surgical; block path is the only reliable feedback channel → keep blocks rare + high-confidence.
- **⚠️ SCOPE (Joshua, explicit):** register in **`<project>/.claude/settings.json`** (exists), NOT global `~/.claude` (where the idle hook lives). Project settings fire only in this dir → inherently project-only. `.claude/` is gitignored → hook config+script live on this dev box only (fine).

**Non-hookable workflow findings (track separately):** N2 — doc/self-knowledge gaps surfaced as frustration ("200k tokens to get here", raised 39×) → keep STATUS/results.csv answer-ready, enforce per-run manifest.json. N3 — orphan-process anxiety (Joshua asked for a census 31×) → make a pre-launch process census (pid+age+CPU) a DEFAULT step, don't wait to be asked.

**✅ BUILT 2026-06-02 (commit 390b482).** Both hooks live: `scripts/hooks/pretooluse_lint.py` + `posttooluse_log.py` (tracked), registered project-scoped in gitignored `.claude/settings.local.json` (see `scripts/hooks/README.md`). N1 (CIFS box→mount table + $SHARE) and N3 (pre-launch census) folded into CLAUDE.md. Remaining/optional: tune the advisory set as `.claude/tool_failures.jsonl` accumulates; verify which failure classes PostToolUse actually catches vs need transcript mining.

## 2026-06-02 — Work-stealing claim-tail inefficiency + dashboard reachability/Tier-C

**Context:** built `--shared-claim` work-stealing for eval sweeps + the cluster dashboard (DECISIONS 2026-06-02 late).
**Ideas (two, both deferred):**
1. **Claim-tail re-steal.** Claim-based stealing kills the bulk idle but leaves a tail: once all remaining seeds are claimed-in-flight, a box that drains its queue exits instead of re-attempting another box's slow claim (claims expire only after `claim-stale-secs`=90min). The last ~Σworkers games finish on the fastest box while others idle (seen on the dashboard: laptop idle on the fpu04 tail). Fix options: a short stale window for the *final* N games, a queue-drain re-attempt loop, or a tiny coordinator handing out the tail.
2. **Dashboard reachability + Tier C.** Web server binds inside WSL2 (NAT'd), tailscaled is on the Windows host → currently reach via SSH `-L` or a manual `netsh portproxy`. Clean long-term: WSL **mirrored networking** (`.wslconfig networkingMode=mirrored`) — needs a WSL restart so deferred to a between-runs window. *(NB 2026-06-11: mirrored was assessed for the XEON ssh-flap and SKIPPED there — it doesn't fix idle VM-teardown, the keepalive does. This dashboard item is a different box/purpose; if revisited, weigh that precedent.)* Tier C (FastAPI + history graphs + kill buttons) is overkill for 3 boxes. Also fold heartbeat+server relaunch into a launcher (4 long-lived procs die on box reboot, e.g. the 5950x swap).
**Why deferred:** the MVP work-stealing + dashboard deliver the value; these are polish. Don't action without Joshua.

## 2026-05-31 — Eval/measurement gauntlets are CPU-bound; their GPU sits ~75% idle (batch-1)

**Context:** during the iter_11 n=400 ladder run (`eval_net_vs_heuristic.py`) Joshua noticed the 5800X GPU read **76% util but only 47 W of its 180 W limit** (clocks near-boost at 2820/3090, so not throttling). CPU was a genuine ~90%. This is the **eval-script corollary** to the already-documented self-play GPU-boundedness (DECISIONS 2026-05-19 "Open gaps" #2: self-play is CPU-leaf-bound, GPUs ~26-40%; DECISIONS 2026-05-20 eval-server bridge).

**Finding:** the eval/measurement gauntlets (`eval_net_vs_heuristic.py`, `eval_iter_head_to_head.py`) run **per-worker batch-1 inference with NO orchestrator** — each worker holds its own `make_single_evaluator`. So the net-prior forward passes are tiny single-position kernels: GPU "utilization" pins high (a kernel is almost always resident) but actual throughput/power is ~25% (latency-bound, kernel-launch + memory-latency dominated). The real bottleneck is the **CPU `virtual_score` v2.7 leaf**, used by *both* sides (HeuristicMCTS's whole search + the neural side's leaf VALUE — only the priors come from the net).

**Operational takeaways (act on these now, no code needed):**
1. **Pick eval boxes by CPU cores, not GPU.** A bigger/faster GPU does ~nothing for gauntlet throughput; more/faster CPU cores do. (Retroactively: the laptop's weak GPU was never the eval throughput problem — its 8 GB VRAM ceiling at high W and flaky net were.)
2. **`util%` is a misleading "busy" signal for batch-1 — read `power.draw`.** 90% util + 26% power = nearly-idle GPU. Use `nvidia-smi --query-gpu=power.draw,utilization.gpu,clocks.sm` to tell real load from nominal.

**Why deferred (the code fix):** wiring the eval gauntlets onto the existing eval-server/orchestrator (batched inference, already built for self-play, DECISIONS 2026-05-20) would only batch the **prior** fraction — the CPU `virtual_score` leaf still dominates, so the win is modest for evals specifically (unlike pure-NN self-play, where batching is the known big lever and is already done). The higher-ROI eval lever is the **`virtual_score`/`find_farm` speedup** (union-find/cacheable after the start-independent rewrite — "active dev" per CLAUDE.md), which cuts the actual bottleneck. Revisit GPU-batching for evals only if/when a future leaf is GPU-heavy. Related: [[results-table-source-of-truth]], the self-play eval-server entries in DECISIONS.

## 2026-05-28 — Shortened-game variant (fewer tiles) as a screening regime

**Context:** Joshua flagged 2026-05-28: would training/eval on shortened games (subset of the tile deck → shorter games → faster wall-clock) let us screen more ablations cheaply, with findings then validated on the full game? Engine supports trivial deck subsetting (the deck is a list of tile counts in the wingedsheep code).

**Idea:** monkey-patch the deck to N% of normal counts (try N=50%, N=30%). Train one iter and eval at the subset size. Then re-evaluate the winning configs on the full deck to check whether findings transfer. If they do within ~10 elo, use the subset deck as the default screening regime.

**Estimated speedup ceiling:** ~2-3×. Per-game compute = (sims/position) × positions × per-position-cost. Halving the deck halves positions; engine per-position cost also grows ~linearly with placed tiles (board adjacency scan), so a small extra multiplier. Not transformative — sims=200 → sims=100 would give comparable speedup with less risk.

**Why deferred:**
1. **Generalization risk is real.** The findings that drive our search (c_puct, leaf cap, value-target) are partly *endgame*-driven: c matters most in late midgame when most cities/roads close, leaf cap matters because of completion-timing, farm scoring only triggers at game end. Cutting 50% of tiles cuts ~80% of the closing-phase decisions. A short-game finding could disagree with full-game by 20-30 elo, bigger than most deltas we chase. Risk: false-negative screening (missing real wins) AND false-positive screening (chasing artifacts).
2. **Validation pilot would cost ~1 day** (train one full-deck iter + one half-deck iter from the same warm-from + cross-eval). Worth doing only if we anticipate 50+ more screening ablations. At current pace (5-10 planned) it doesn't pay off.
3. Adjacent idea — **feature curriculum staging** (base-game-only → +farmers → +river) — is already in BACKLOG with a similar generalization risk and similar deferral logic. Both are "train on a simpler variant first" with different axes.

**Why this is in the backlog, not killed:** if we ever move into a regime of doing many cheap ablations (e.g., heuristic-leaf redesign sweep, or post-distillation re-tunes on the smaller student), revisit this. The pilot cost is bounded and the speedup is real if generalization holds.

**Related:** [[curriculum-stage-by-feature]] (BACKLOG above) — adjacent idea, simpler-variant axis is "rules" not "tile count."

## 2026-05-27 — Optuna / TPE over eval-time hyperparameters

**Context:** 2026-05-26 c_puct find (+47 elo) was missed for 6 weeks because we manually tested one knob at a time and never joint-searched. With ~9+ tunable hyperparameters (c_puct, leaf_cap, leaf_variant, dirichlet_alpha/eps, virtual_loss, temp_threshold, tile_counting, anchor_fraction) the combinatorial space is intractable for manual exploration. Joshua flagged this 2026-05-27 — Optuna/TPE/Bayesian optimization is the standard answer.

**Idea:** wrap `eval_iter_head_to_head.py` as an Optuna objective function. Search joint space over eval-time knobs (the cheap ones): {c_puct ∈ [1.5, 5.0], leaf_cap ∈ [8, 20], leaf_variant ∈ {v2_7, tile_counting, tile_counting_cont}, sims ∈ {200, 400, 800}}. TPE sampler with ~20-30 trials at n=400 each. Each trial ~2.5-12h dual-box depending on sims. Full study: ~2-3 days dual-box. Returns Pareto frontier of (elo vs compute) and identifies joint optima.

**Why this is Tier 1 (speed multiplier):** automates the search loop forever. Every future re-tune (after a new training iter shifts the landscape) just re-runs the study. Catches joint-knob optima manual search would miss. Roughly halves search-phase wall-clock by avoiding redundant single-knob sweeps.

**Why deferred:** ~half day of code work; should land right after Phase 3 queue finishes. Eval-time knobs only — training-time knobs (dirichlet, anchor_fraction, value_target) cost ~9-25h per trial which is too expensive for BO with our budget. For training knobs keep manual reasoning + targeted experiments. May revisit population-based training (PBT) for training knobs if we have a 6+ box cluster.

**Cost if pursued:** ~50 LoC wrapper script using `optuna` (pip install). Trial dispatch reuses existing eval infrastructure (dual-box work-stealing, `--shared-claim`). Logs land in an Optuna SQLite study + the existing per-eval JSON files.

## 2026-05-27 — Multi-fidelity screening (Hyperband / successive halving)

**Context:** Most "is this lever real?" questions hit a noise wall: at n=100 we can't distinguish +10 elo from zero, at n=400 we can but it costs 4× compute. We currently default to n=400 for every test — risk-averse but expensive. Multi-fidelity BO (Hyperband, BOHB) screens cheaply, promotes promising trials to deeper evaluation.

**Idea:** every search trial starts at n=100. If point estimate is within (current best ± 25 elo), kill it. If clearly positive (+20+ elo at n=100, ~2σ), promote to n=200. If still positive, promote to n=400. Most trials die at n=100 (the screening tier), saving ~75% of search compute. Risk: a real +15 elo win gets killed at the screen (1.5σ at n=100 → not promoted). Mitigation: re-screen the killed list periodically against a fresh baseline, since shifting landscapes can resurrect false-negative levers (the same lesson as [[bracket-hyperparams]]).

**Why this is Tier 1 (speed multiplier):** roughly halves search compute on the screening phase. Pairs naturally with the Optuna entry above — Optuna handles "where to look next", multi-fidelity handles "how many games per trial."

**Why deferred:** wait until Optuna wrapper lands; multi-fidelity is a natural extension. ~1 additional day of code.

**Cost if pursued:** ~100 LoC adding tiered-n trial dispatch. Optuna has built-in support via `optuna.pruners.SuccessiveHalvingPruner`.

## 2026-05-27 — Transposition table in MCTS — ALREADY IMPLEMENTED

**Context (original):** suggested adding a state-keyed node cache to `NeuralMCTS` for ~5-20% sim throughput improvement on every search.

**Status (2026-05-27 audit):** **already done.** `NeuralMCTS._nodes: dict[str, _NeuralNode]` exists, keyed by `game.string_representation(board)`. Both code paths that create child nodes (serial `_select_leaf` ~line 786 and batched `_select_leaf_with_vloss` ~line 705) call `self._nodes.setdefault(fresh.state_key, fresh)` — identical states reached via different move orders share one node. Backup propagates only along the path actually taken (the standard DAG-safe approach). `clear()` resets the table per-game.

**Implication:** the 5-20% speedup benefit is already baked into our throughput numbers. No code work needed. Removing from Tier 1 task queue; leaving this entry in the backlog as anti-rediscovery: don't propose adding a transposition table again — it's there.

## 2026-05-29 — leaf flood-fill speedup (farm + city) — ✅ DONE (lazy per-leaf memo, 1.70× leaf / 1.48× search)

**Shipped 2026-05-29** (dev complete, gated, benched; commit pending Joshua). Implemented NOT as the incremental union-find imagined here but as **lazy per-leaf memos** (`_farm_cache` farm regions, `_city_cache` city components) — the production leaf path (NeuralMCTS) reaches leaves via functional `get_next_state` (deepcopy, no rollback), so per-leaf-state is the correct shape, not incremental-across-tree. Profiling reset the priors below: post-fix `find_farm` is **~41%** of the leaf (not 58%), `find_cities`/`find_city` ~31%, **>50% of those calls redundant within one eval**, deepcopy negligible. A/B picked lazy over eager whole-board decomposition (farm-only 1.27× vs eager 1.11×); **combined farm + city = 1.70× leaf / 1.48× end-to-end search.** The city memo returns a fresh `City` per call (caches only flood-fill data) to preserve count_farm_points' identity-dedup → value-invariant. Gate `scripts/reconcile_farm_index.py` (both caches) **n=400, 921,953 nodes, 0/0 mismatches**; `tests/test_farm_index.py`. `find_all_farms` (eager) kept for Step E farm inputs + as oracle. Full detail: DECISIONS 2026-05-29 "Leaf flood-fill speedup IMPLEMENTED". The original rationale (kept below for history):

**No longer deferred.** This was the next dev task. Execution plan lived in [docs/PATH_B.md](docs/PATH_B.md) Step 2 (revised). Sequence: incremental union-find + reconciliation gate (union-find == `find_farm`, mirror the aux n=2000 gate) + throughput bench → leaf-pass sharing → then the deferred Step-2 farm inputs become cheap.

**Context:** `FarmUtil.find_farm` is the #1 hot path in the v2.7 leaf (~58% of leaf cost per the 2026-05-17 profiling) and was previously flagged un-cacheable because its flood-fill was *start-dependent* (different result depending on which farmer the search started from). The 2026-05-29 engine fix (DECISIONS.md — `opposite_farmer_side` bijection + complete-CC `find_farm`) makes the farm region **a well-defined function of the board state**, identical from any start. That removes the blocker on caching.

**Idea:** memoize farm regions keyed by board state (or incrementally maintain a farmer union-find as tiles are placed). Because the region is now canonical, a state-keyed cache or union-find is correctness-safe. Potential large win on the leaf hot path (farms dominate it), which directly speeds self-play + eval throughput across the cluster.

**Why deferred:** correctness fix shipped first; caching is a pure-perf follow-up. Bench the fixed `find_farm` against the old one first (the CC rewrite changed the traversal — confirm no per-call regression) before adding a cache layer. Don't cache until after Path B's fresh warmstart so the leaf behaviour is stable.

**Cost if pursued:** ~60-120 LoC (state-keyed memo is the cheap version; incremental union-find is the bigger, faster one). Mirror the legal-moves-cache invalidation discipline (clear per-move / per-search).

**Caveat (2026-05-29) — a state-keyed memo gives only PARTIAL relief.** MCTS visits a different position at nearly every leaf, so a per-state cache mostly *misses* within a search (helps only on transpositions / cross-move recurrence). The near-zero-cost path is **reuse, not caching**: the v2.7 leaf ALREADY runs `find_farm` at every leaf (virtual_score → count_final_scores), so compute the farm structure once per leaf and share it between the leaf-value and any consumer, rather than recomputing. The biggest win is **incremental union-find** (maintain farm structure as tiles are placed down the tree). Either way, BENCH actual throughput before trusting "no slowdown."

**Primary consumer = the deferred Step-2 farm INPUT features** (`my/opp_dominant_farms`, `contested_features`). Those were deferred from Path B precisely because they'd run farm enumeration at every leaf-encode; this speedup is the prerequisite. Gate both on **Step 9 = GO** — at scale the union-find speeds the whole pipeline (self-play + eval), so it earns its dev cost; before GO it's not worth it (farm inputs are lower-EV than the Step-3 aux heads).

## 2026-05-27 — Multi-anchor league (extends anchor-fraction beyond N=1)

**Context:** Anchor-fraction at c=3 just recovered (+30.5 elo at n=400) — validates the lever. But our implementation uses ONE fixed anchor checkpoint (iter_B1) for the anchor fraction. AlphaStar's league play uses N anchors at varied skills (current main, main-exploiters, league-exploiters) — addresses RPS-style cycles by training against a diverse opponent portfolio. Pluribus did similar with blueprint mixing.

**Idea:** extend `selfplay.py` anchor-fraction to support a *list* of anchor checkpoints, sampled per-game. Initial portfolio: {iter_01, iter_B1, deepsearch, deepsearch_v2} (covers different training histories). Anchor fraction stays at 0.3; each anchor game uniformly samples from the portfolio.

**Why deferred:** Phase 3 J1 just validated single-anchor; need to confirm the chain works (iter_AF2, iter_AF3 at c=3) before adding portfolio complexity. Also: 4× checkpoints in VRAM means ~6GB total — fits on 5800X 24GB but tight on Xeon's RTX 4000 8GB. If pursued, evaluator pool needs lazy loading or rotation.

**Cost if pursued:** ~80 LoC in selfplay.py + run_selfplay_iter.py. Existing dual-evaluator code path generalizes — just becomes N-evaluator.

**Related:** existing entry "Specialist warmstarts + league play" (Phase 4 deferred section) — that one proposed heuristic-biased specialists; this one is checkpoint-history-based. Both could coexist.

## 2026-05-27 — Distillation (small fast student from strong teacher)

**Context:** Current production net is 6×96 ResNet (~7M params, ~5-6ms inference per batch). For family-game play, latency matters — Joshua wants to play and not wait 30 seconds for a move. Distillation: train a smaller student net to mimic a larger/stronger teacher's policy + value outputs on the teacher's self-play games.

**Idea:** train a 4×64 student net (~1-2M params, ~2× faster inference) using KL divergence loss against iter_B1 (or whatever the future global-best is) on the existing self-play buffer. Should retain most of the teacher's strength at lower inference cost. Alternative: 6×64 (fewer params, same depth) or 4×96 (same width, less depth). Bench each.

**Why this is Tier 3 (strategic):** doesn't make us stronger, makes us faster — important for the eventual family-play use case. Speeds up play time and potentially self-play if the student becomes the next iter's teacher (but quality drops, so probably not for self-play). Pairs well with sims=800 production play: if student inference is 2× faster, sims=1600 becomes affordable.

**Why deferred:** premature until we have a stable global-best strong teacher. Worth doing once the recipe stops compounding (we're not there yet — c_puct find proved we're still in compounding regime).

**Cost if pursued:** ~150 LoC training script + 4-6 hours train + bench. The architectural variants need a fresh warmstart (different tensor shapes from teacher).

## 2026-05-27 — MuZero-style learned dynamics model

**Context:** Our MCTS uses the vendored engine for state transitions — perfect for known-rules games but limits what the net can learn. MuZero learns the dynamics model end-to-end (state + action → next-state representation), and uses it for MCTS planning. For Carcassonne the dynamics are deterministic and the engine is correct, so MuZero offers no game-mechanics advantage — but the *latent* representation it learns can encode strategic features the engine doesn't expose (e.g. "this position has high meeple-lock risk"), which COULD be useful for Phase 5 analyzer.

**Idea:** retrain with a MuZero-style head that predicts a latent state representation from raw board features, then uses MCTS over the latent dynamics. Largest end-state architectural change in our backlog.

**Why this is Tier 4 (research bet):** ~6 week project. May not even improve playing strength (MuZero matched, didn't exceed, AlphaZero on Go). Worth considering only if (a) recipe truly plateaus AND (b) Phase 5 analyzer needs richer state representations than the engine exposes.

**Why deferred:** not even close to needed. Current recipe still compounds; Phase 5 is gated on superhuman strength which we haven't hit. Park here so it doesn't get forgotten as a long-horizon option.

## 2026-05-27 — Apple Neural Engine (ANE) inference on M5

> **Status update 2026-07-28 (stage Eff Jensen): the latency half is now MEASURED, and it beat this entry's guess** — CL-067 (7.5M-param) batch-1 forward = **0.42 ms fp16 with all 52 ops on the ANE, zero CPU fallback, argmax-faithful** (vs 2.6 ms torch-CPU same box, 19.4 ms on the gate-loaded 5900XT GPU path). See [measurement/m5_bench_20260728/M5_BENCH_READOUT_20260728.md](measurement/m5_bench_20260728/M5_BENCH_READOUT_20260728.md) + `scripts/m5_bench/ane_coverage_probe.py`. The *integration* (wiring ANE into a play/eval path) remains not-built, and the original deferral logic is half-expired: the question is no longer cluster throughput (Air CPU throttles, fanless) but batch-1 deploy latency for net-prior search, where the first revisit bullet below ("ANE inference at <1ms would dominate") is now the measured reality. Whether net priors deserve deployment at all is what the 2026-07-28 equal-wall-clock gate decides.

**Context:** M5 Mac Air joined the cluster 2026-05-27 with MPS (Apple GPU) for forward passes. ANE (Neural Engine) is a separate dedicated NN inference accelerator on Apple silicon — ~38 TOPS on M5, optimized specifically for inference, much more power-efficient than GPU.

**Idea:** export the 7M-param ResNet to Core ML format via `coremltools`, run inference through Core ML Python API, wire into eval-server as a third backend alongside CUDA / MPS. Could be 2-5× faster than MPS for our small net.

**Why deferred:** ~1-2 days dev work (export + integration + per-op compatibility check). Mac is currently the smallest cluster contributor (<25% even with MPS); the marginal speedup from ANE goes from "small contributor" to "still-small contributor that uses less power." Dev time better spent on Optuna improvements, league play, or anchor-fraction chain — all higher-EV. PyTorch can't target ANE directly so this is a real integration project, not a one-line patch.

**When to revisit:**
- Phone/iPad version for Phase 5 family-game UX — ANE inference at <1ms would dominate
- Multi-Mac cluster (M-series farm) where per-Mac throughput matters more
- Bigger network where forward-pass dominates per-game cost more
- If we ever care about power-efficient inference (e.g. always-on coach mode)

Currently: MPS is the right level of Apple silicon optimization. ANE stays in this entry.

## 2026-05-27 — Transformer over board features

**Context:** STATUS.md mentions this once as "bigger project" and we've never costed it. Convolutional ResNet has structural assumptions (local features, translation invariance) that suit images but may not match Carcassonne where strategic features are spatial relationships between distant tiles (farm connections, road-network topology). A small transformer over board features could capture those long-range interactions natively.

**Idea:** replace the ResNet trunk with a 4-layer transformer encoder over a board-as-sequence representation (e.g. each placed tile + each open position as a token). Output flattens through the same policy/value heads. ~5-10M params depending on width.

**Why this is Tier 4 (research bet):** unclear whether attention helps on a 35×35 grid with ~80 tokens (small). Modern AlphaZero variants (KataGo, recent chess engines) still use CNNs because the inductive bias matches the grid structure. The argument for transformer is the long-range interaction one, but it's speculative.

**Why deferred:** ~3-4 week project (arch + warmstart + retrain). Only worth it if recipe truly plateaus AND we suspect long-range modeling is the bottleneck. Bench a feature-distance probe first (does a probe classifier on ResNet activations predict "long-range" structure poorly?) before committing.

## 2026-05-19 — Curriculum self-play: Base-game-first, then add farmers/river

**Context:** Reading the Dwarkesh × Eric Jang interview (rebuilding AlphaGo) against our state. Eric's data-efficiency trick: don't train AlphaZero tabula-rasa on 19×19 — bootstrap a value function on 5×5/9×9 self-play, then transfer. Our value head is the documented bottleneck (Option 2 closed 2026-05-18: a 7.4M-param value head on ~1200 games is a weaker evaluator than the hand-tuned v2.7 heuristic) and the plain recipe is plateaued — so the interesting lever is data efficiency, not another recipe knob.

**Idea:** stage self-play by feature complexity instead of training the full game all at once. Base-game-only self-play first (no farmers, no river), then warm-start a farmers stage, then a river stage. Farmers carry the hard long-range credit assignment; grounding the value head on cheaper, shorter base-game games first may give it usable structure before farmers are introduced. Architecture is unchanged (farmer/river channels sit unused in the base stage) so weight transfer between stages is clean. Final model still trained + evaluated on the full locked scope.

**Why deferred:** (1) can't make changes now; (2) the analogy is imperfect — 9×9 Go *is* 19×19 scaled down, but Base Carcassonne vs Carcassonne-with-farmers is closer to a different game (farmers dominate scoring and strategy), so transfer could be weak — pressure-test this before building; (3) it's a new training pipeline (base-only deck/self-play path), not a one-knob ablation, so it does not belong in the EXPERIMENTS.md priority queue (whose validated #1 lever is currently deeper-search self-play); (4) needs Joshua's call on build cost vs. just running deeper-search self-play. If pursued, smoke the base→farmers transfer on a tiny run first.

## 2026-05-19 — Record `value_target` in self-play buffer `.npz` metadata

**Context:** Prompted by the Eric Jang interview's "ground the value or MCTS falls apart" point, audited the replay buffer — it's healthy: v25_retrain* buffers are ~50/50 p0/p1, no resignation (a non-terminating game raises `RuntimeError`), every game an exact terminal value. The audit found all v25 buffers are `wl`-encoded ({-1, 0, +1}), while `run_selfplay_iter.py`'s `--value-target` default is `score_diff` — so the in-flight deepsearch run is producing a `score_diff` buffer. Investigated whether that matters.

**Finding (it does not — do NOT "fix" the default):** `value_target` only changes the value-row *encoding* — `score_diff` = `tanh((p0-p1)/15)`, `wl` = `sign(p0-p1)` — same games, same outcomes. Policy targets (MCTS visit distributions) are byte-identical regardless. The NN value head is **not consulted anywhere in the v2_5 pipeline**: self-play and the anchor-gate eval both run `policy_only` (value_blend=0; Option 2 closed 2026-05-18), so the value head exists only as a `train_iter.py` co-training target. `value_target` therefore affects only the shared trunk via the value-MSE term — a minor auxiliary-signal difference, not a data-integrity issue. And `wl` is losslessly recoverable from a `score_diff` buffer (`sign(tanh(margin/15)) == wl`), so a `score_diff` buffer is a strict *superset*. The deepsearch buffer is fine — train on it as-is and let the anchor gate be the safety net.

**Recommendation:** do **not** flip the default to `wl`. `score_diff` is the better default — a richer, smoother co-training signal for the trunk, and a margin-predicting value head is more useful than a binary one for the eventual Phase 5 analyzer (the win condition). The one real gap is hygiene: the encoding is undeclared — not stored in the `.npz` (the run banner prints it, but an old buffer can only be re-identified by inspecting its values). Action: stamp `value_target` into `GameDataset` / the `.npz` metadata so a buffer is self-describing. The 2026-05-17 note ("richer score-diff value targets landed") is accurate as-is.

**Why deferred:** metadata hygiene only, zero model impact, not urgent — do whenever convenient. (The original "before the next self-play run" urgency was based on a mistaken inconsistency framing and no longer applies.)

## 2026-05-19 — Code-review loop: deferred bug fixes (REVIEW_LOG.md)

**Context:** A 4-iteration multi-agent code review (full findings + rationale in `REVIEW_LOG.md` at repo root) applied 13 safe fixes and deferred 16. Four deferred items are real fixes with a known trigger point — parked here so they are not forgotten. D6 (warmstart-mix train/val leakage) was reviewed and deliberately **skipped** — warmstart mixing is over (`--warmstart-mix 0.0`).

### D13 — `features.py` `tiles_remaining` off-by-one — ✅ RESOLVED 2026-05-29 (Path B retrain boundary)
**Fixed** in `features.py:encode_scalars`: `tiles_remaining = len(deck) + (1 if is_tiles and next_tile else 0)`. Was counting the just-placed tile on every MEEPLES-phase encode (~1.2% off on ~50% of evals; `progress` jumped 1/total at TILES→MEEPLES). Taken now because Path B regenerates all data + warmstart from scratch, so the inference/training desync the deferral worried about doesn't apply.

### D1 — `board_repr.py` ref-tile encoded differently in TILES vs MEEPLES phase — ✅ RESOLVED 2026-05-29 (keep + document)
**Resolution: keep the phase-dependent reference tile — it is correct, not a bug.** TILES phase encodes the *unrotated* `next_tile` (the decision is where/how to place+rotate it); MEEPLES phase encodes the *rotated* placed tile (the decision is meeple placement on the now-fixed tile). The phase one-hots + `CH_LAST_TILE_POS` let the net disambiguate. The alternative (always encode the placed tile) would hide the to-be-placed tile during the TILES decision. Rationale documented inline at `encode_board`.

### D16 — `virtual_score_v2.py` board-edge city 100% closure bonus — ✅ RESOLVED 2026-06-08
**Idea:** `_close_prob(0)` returns 1.0; a city whose only open edge points off the 35×35 board counts 0 in-bounds open positions but is still `finished=False`, so it gets a full closure-anticipation bonus it physically cannot earn. Fix: `continue` (no bonus) when `_open_city_positions==0` on an unfinished city — at both the city-closure and farm-growth loops (~line 351).
**✅ FIXED 2026-06-08** (the "fix all outstanding bugs" pass, DECISIONS 2026-06-08 pm-2 / REVIEW_LOG): applied at both leaf call sites; **no cap re-sweep needed** — the trigger (a city chain reaching the literal edge of the 35×35 board in a ~72-tile game) is practically unreachable, so the leaf/ruler change is negligible. *(Original deferral reason: leaf changes shift tuned optima → fold into a cap re-sweep.)*

### D9 — failed self-play game holds its claim ~90 min — fix BEFORE the next MULTI-ITERATION run
**Idea:** a game that raises leaves `seed_NNNNNN.claim` undeleted; the seed is blocked until the 90-min stale threshold, and a deterministically-failing seed never completes (iteration count never reaches `args.games`). Fix: a `.failed` sidecar — workers skip it; "iteration done" becomes `npz + failed >= games`.
**Why deferred:** needs a small policy call (fail after 1 attempt vs a retry budget). Pure orchestration, no model impact — fine to do any time before the next multi-iter self-play run.

### D15 — work-stealing stale-recovery multi-winner race — DONE 2026-05-19
**Idea:** `_try_claim` stale-recovery can yield multiple winners (a stale-info thread renames aside a fresh claim re-created by an earlier winner). Bounded duplicate games on crash-recovery only, never corruption (the atomic `.npz` write is the real correctness layer).
**Decision (2026-05-19):** do NOT attempt the concurrency redesign — high risk on a live primitive, a botched fix could lose a claim (worse than the duplication). Instead relax the docstring's "exactly one winner" overpromise and change `test_32_threads_race_for_one_stale_claim` from `xfail` to assert `1 <= winners <= N`.
**Done (2026-05-19):** `_try_claim` docstring relaxed; `test_32_threads_race_for_one_stale_claim` flipped off `xfail`, asserts `1 <= winners <= N`. No `xfail` remains in the suite. See REVIEW_LOG.md follow-up (F15).

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

### Train alongside self-play (async) → DEVELOPED, see [docs/ASYNC_FLYWHEEL_DESIGN_2026-06-10.md](docs/ASYNC_FLYWHEEL_DESIGN_2026-06-10.md)
**Idea:** the retrain pipeline is synchronous (gen iter N → train iter N → eval, all barriered). Run gen/train/eval as continuous async services so no resource sits idle.
**Refined 2026-06-10 (measured the phase split on the live attempt-#2 run):** the idle GPU isn't the prize — the dominant phase is **eval (64% of the cycle)**, the *in-loop* heur@800 selection gate; train is only ~21%, gen ~15%. So the highest-value move is taking heur@800 **off the per-iter critical path** (async odometer + cheap-but-never-crowning warm-from), which the design doc shows preserves attempt #2's philosophy intact (heur@800 stays the sole promotion authority; warm-from is always confirmed-best; the cheap proxy never crowns). Honest sizing: ~20% on the current 3 boxes (fills the train hole); the real multiple needs cutting eval *work* (don't re-play best every band; accumulate-until-significant) + adding boxes (which async finally lets pay off).
**Why deferred:** big architectural change + needs Joshua sign-off (changes the run's operational shape, not its philosophy) + the per-box W-retune underneath it is untrustworthy until the 5800x VRM throttle is fixed. Design-now, build-after-fins.
**Step-2 PeNS angle (Joshua 2026-06-30) — ❌ DOA, killed same day by the iter-1 timings.** The idea was: the step2 wean-eval is measurement-only (doesn't gate the blend schedule), so fork iter N's eval to the laptop async while local runs iter N+1, ≈halving the ~56m iter. **Why it's dead:** (1) the iter-1 split showed train (the ONLY local-only stage, the would-be overlap lever) is **~2.4m total** — there's almost no local-only window to fill; (2) both gen AND eval already **work-share across both boxes** (gen local W24+laptop W12; eval local W40+laptop W12), so no box is ever free to do the other stage; (3) the role-split alternative (pin laptop→eval, local→gen+train, pipeline across iters) is **WORSE** — laptop-alone eval ≈76m/iter (5.24 games/min × 400 games) bottlenecks vs the current ~56m serial 2-box, because the weak box can't carry a whole stage solo. **Work-sharing both stages is already the wall-clock optimum on this 2-box cluster.** No action. (The RoD-v2 async-flywheel idea above is separate and still stands — it was about a 3-box cluster + a load-bearing heur@800 selection gate, a different topology.)

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
**Why deferred:** a throughput win, not a strength win — only worth it before a long multi-iter run. fp16 is **batch-conditional** (REFINED 2026-06-01, see DECISIONS): the old "slower twice" result holds at small per-worker batch (orch-off / virtual-loss), but under the **orchestrator** (max_batch 256) fp16 is FASTER on Blackwell (+24%) / Ada (+31%), ~null on Turing — not a blanket "not a lever."

### Symmetry exploitation — ✅ DONE 2026-06-02 (C5, Stage A3 of the correction plan)
**Status:** BUILT. `board_repr.rotate_board_repr_90` (+ batched), `action_space.rotate_action` + `action_rotation_perm`, `warmstart.rotate_dataset_90` / `augment_with_rotations`, wired into the streaming loader (`make_streaming_dataset(augment_rotations=)`) + `train_iter.py --augment-rotations` (default OFF, zero behavior change). 16 tests in `tests/test_symmetry_aug.py` (round-trip, hand-geometry direction, edge-perm-matched tile-rotation delta, mass preservation, 4× row count). 90° rotation only; reflection deferred (curved roads aren't reflection-symmetric). Came in ~as predicted below. To USE: pass `--augment-rotations` at the Stage-B retrain. The original "not used" note (pre-2026-06-02):
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

## 2026-04-28 — River edge-case regression tests — DONE 2026-05-19
**Context:** External review pass 4 (2026-04-28). `RiverRotationUtil.get_river_rotation` can implicitly return None around river start/straight cases. Coverage is thin. Specific cases to test:
- River start tile placed at starting_position
- River end tile placed (last river segment)
- Disallowed repeated bend sequence (engine should refuse)
- last_river_rotation correctly tracked across multiple river placements
**Done (2026-05-19):** `tests/test_river_rotation.py` — 13 unit tests over `RiverRotationUtil`: pure rotation geometry (straight / CW / CCW), real river-tile checks via `the_river_tiles`, the implicit-`None` river-start and non-river-tile branches, and straight-segment carry-forward. The bend-sequence *refusal* case is tile-placement legality (`TileFitter`), not `RiverRotationUtil` — out of scope for this file, not covered.

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

## 2026-05-21 — Validate remote_eval_bridge slot-leakage / stale-response handling

**Context:** Today's Zenbook bridge worker-count bench saw throughput collapse with more workers (W=4 → 1.0 g/min, W=6 → 0.5, W=8 → 0 — STUB+contention bench, never re-run cleanly). One plausible cause is a real correctness bug in the bridge's stale-response drain logic.

**Suspect:** `src/carcassonne_ai/remote_eval_bridge.py:_conn_loop` lines ~175-196. When a remote connection dies mid-request (`pending=True`), the bridge tries to `handles.response_q.get(timeout=60.0)` to drain the in-flight response before returning the slot to the pool. If the server's response takes >60s (under load), the drain fails and the slot goes back to the pool **with a stale response still queued**. The NEXT connection to grab that slot does `handles.response_q.get()` and receives the stale prior response — which `send_framed(conn, pack_response(resp))` sends to the new client **without verifying `request_id`**. Silent corruption: the client gets priors/values for a different board.

**Why deferred:** Zenbook is dead-end for now (2026-05-21, Joshua), so bridge isn't being used. No production impact. But this needs fixing before the next bridge deploy — and the fix is easy: in `_conn_loop` either (a) verify `resp.request_id == req.request_id` before sending and drop the response if not, or (b) drain unconditionally with no timeout (block until the in-flight response arrives or the server dies, then release the slot). Option (b) is simpler and correct because the server is guaranteed to respond eventually (or be dead, in which case we shouldn't reuse its slots anyway).

**Verification when picked up:** rebench W={4,8,16} against a clean GPU (no other workload sharing). If throughput scales monotonically, the prior degradation was contention, not this bug. If W>4 still degrades, the bug is real — fix per above, re-bench.

## 2026-07-28 — Fixed start tile (retail/tournament rules fidelity) — ✅ SHIPPED FOR THE APP 2026-07-30; library default still PARKED, bundle with G1

**Context:** Joshua noticed the retail game pre-places a fixed start tile (the city+road "D" pattern) before any draw. Verified: our engine does NOT — `initialize_deck` shuffles all base tiles into one deck and the first player draws a random tile onto an empty board (`engine/wingedsheep/carcassonne/carcassonne_game_state.py:112`). Tournament play uses the retail convention, so this is a rules-fidelity divergence for official-contest play (G1) and for app-feel.
**Why deferred:** strategically near-null (first placement on an empty board is an almost-free decision; deck differs by one tile), but every training run, eval, and solver measurement to date consistently uses the random-start convention — switching is a rule change that shifts all baselines slightly and needs explicit approval per the locked-scope rule. Fix if and only if we register for an official contest (bundle with G1's re-baselining), or if Joshua wants the app retail-faithful (which would then diverge from the convention the champion was measured under).

**UPDATE 2026-07-30 (Joshua): app-side APPROVED.** "I'd like that also fixed for the android app" — he also flagged: if the border fix forces any strength recharacterization under amended rules, consider bundling this rule in at the same time rather than re-baselining twice. The champion-vs-app convention divergence the entry warned about is accepted for the app (E4 games grade against the k4×688 carve-out, so the divergence is an E4-manifest footnote, not a measurement break). **Implemented (worktree, merged 2026-08-01):** Implemented as an opt-in: `Game(fixed_start_tile=True)` → `game_wrapper.preplace_retail_start_tile` (draws one `city_top_straight_road` out of the shuffled pool, places it unrotated at `starting_position`, leaves `last_tile_action` None so nobody spends a turn or a meeple on it; totals stay 72 placed). The bridge carries `START_RULE = "retail"` and writes `start_rule` into the save payload, so games archived before today (no field) still replay under `"engine"` — `(deck_seed, actions)` is only lossless with respect to its own rule. **The library default is unchanged and bit-identical** (`tests/test_fixed_start_tile.py::test_default_is_bit_identical`, golden suite green), so no baseline moved. What is still PARKED is flipping the *global* default — that remains the G1 re-baselining decision.
**Not a fix for the invisible-border bug** (below): retail changes *which* tile starts, not *where* — `starting_position` is still `Coordinate(6, 15)`, and the row-0 wall bites at the same rate (72% vs 77% of games, n=60 each).

**UPDATE 2026-08-03 — it did NOT wait for G1: the retail tile shipped inside `fixed_v1`.** `start_rule:
"retail"` is one of the four composed levers in the `fixed_v1` rules profile (`src/carcassonne_ai/rules_profile.py`),
and `governance/PRODUCTION.yaml` now carries `rules_profile: fixed_v1` as the profile of record for new
eval/desktop work (DECISIONS 2026-08-03 morning). So the "bundle with G1's re-baselining" plan was
superseded by F9 — the re-baselining happened there instead, priced by CL-075's transfer bound and the
all-null caps/curve re-sweep. ⚠️ **Still parked exactly as written: the GLOBAL library default.** `fixed_v1`
is opt-in; a bare `Game()` is still `engine`-start and walled. Also worth knowing for A3 sequencing: the
retail rule **absorbs ~5.6×** of the unplaceable-tile redraw rate (7.8 → 1.4 events/100 games), so these two
rules are not independent (roadmap F9, A3 gate verdict).

## 2026-07-30 — Invisible border: the engine grid's start tile is NOT centred — ✅ DECIDED AND SHIPPED (app 2026-08-02, eval/desktop 2026-08-03)

> ✅ **NO LONGER AWAITING JOSHUA.** Two decisions closed it. (1) **App-only recentring 6→18 approved and
> shipped 2026-08-02** — `Game` gained an opt-in `start_row`/`start_col`, the bridge gained `grid_rule`
> (`centered18` / `engine6`, missing ⇒ engine6), verified on the Pixel; the even-shift rule this entry
> derived is exactly what was implemented (DECISIONS 2026-08-02 early). (2) **The geometry was then
> settled BY DATA and adopted for eval/desktop**: the F9 wall probe found **0/400 sentinel events at row
> 18 under champion play** (bigger boards buy nothing ⇒ W2, not W3), and `centered18` shipped inside the
> **`fixed_v1`** bundle that `governance/PRODUCTION.yaml` now names as `rules_profile` of record for new
> eval/desktop work (DECISIONS 2026-08-03 night + morning; CL-075 is the transfer bound on the walled
> record). ⚠️ The **global engine default is still walled** — `fixed_v1` is an opt-in profile, and the
> strict-xfail sentinel in `tests/test_start_tile_grid_bound.py` still xfails by design. *(Original
> diagnosis follows.)*

**Context:** Joshua hit an "invisible border" playing the champion on the Pixel — no tile placeable above the topmost row, and later the whole row above the board was dead. Root cause is the engine, not the app: `carcassonne_game_state.py:24-25` has `board_size = (35, 35)` with `starting_position = Coordinate(6, 15)`, leaving only **6 rows of headroom above** the start tile vs 28 below (columns 15/19). Observed placed-tile spans reach 17 rows, so upward-drifting boards hit row 0 routinely; `StateUpdater.play_tile:42` bounds-checks before adding to `open_positions`, so off-grid cells never enter the candidate set and `TilePositionFinder` never offers them — silently. The bridge and Kotlin canvas are pure pass-throughs of that mask and are exonerated (0 disagreements); the 25×25 action window is not involved (0 dropped actions in 96k+ enumerated).
**Blast radius** (`scripts/diagnose_grid_wall.py`, 400 random games): 67.8% of games have ≥1 rule-legal placement denied, 21.7% of tile plies, 2.6% of all legal placements, 100% of them at row < 0, 0 forced passes. True for all self-play, training data and evals to date — symmetric between players, so results are *fair*, but the game is not canonical Carcassonne. On the reported archive: first touched row 0 at ply 88, 25 denied plies, 12 on the human's turn.
**Why not fixed:** recentring changes the legal-move set in ~68% of games → every existing eval number becomes non-reproducible and every deck band measured under it retires. Joshua's call; possibly bundle with G1 and the start-tile default above.
**How to fix it safely when approved:** the trained representation is translation-invariant, so recentring is representation-neutral **provided the shift is EVEN on both axes** — `board_repr.offset_from_centroid_sums` centres the window with `round(sum/count)` and banker's rounding is only equivariant under even translations (`round(6.5)=6` but `round(17.5)=18`). Row 6 → **18** is bit-identical; row 6 → 17 (the "obvious" centre) silently slips the window one row on ~half of all positions. Contracts pinned in `tests/test_start_tile_grid_bound.py`, whose `xfail(strict)` XPASSes the moment the start tile is recentred.

## 2026-07-28 — WC tie rule: starting player LOSES ties — PARKED, bundle with G1

**Context:** the official World Championship rules resolve a tied final score by ruling the STARTING player the loser (source: TOURNAMENT_LANDSCAPE_MEMO_20260728.md, verbatim quote from WC rules). Our `game_wrapper.get_game_ended` returns a symmetric draw. Draws are ~1–2.5% of our games, so under WC rules the second seat is strictly preferable and correct endgame play differs by seat (the leader-by-seat should steer differently near ties). Never modeled, not in LEVER_INDEX.
**Why deferred:** same shape as the fixed-start-tile gap above — a rules-fidelity change that shifts training/eval baselines and needs explicit approval; near-null in most games but strictly nonzero. Fix if we register for official contest (bundle with G1's re-baselining): tie handling becomes a game-wrapper option + the agent's value function needs the seat-asymmetric terminal value.

## 2026-07-30 — Phase 5/6 descriptive-stats catalog: champion-corpus distributions diffable against E4 human games

**Context:** Joshua, brainstorming the Phase 5 analyzer / Phase 6 mining pass after the strength program converged. The design insight: compute distributional play statistics from the champion self-play corpus (the 11008-teacher corpus, 2,400 games / 345K rows, full champion budget) and **diff them against any E4 record** (human-vs-champion games archived by the Android app). Joshua's seed list:
- **Phase-dependent play** — how play changes early → mid → late (e.g. by tiles-remaining terciles: meeple deploy rate, feature-type mix city/road/cloister/farm, completion-vs-extension moves).
- **City and road size distributions** — completed-feature size histograms; extendable to points-per-meeple-turn (efficiency of meeple capital).
- **Meeple stranding** — how often early-laid meeples never get reclaimed (this is exactly what the leaf's meeple curve prices; the meeple_K term is worth +179.5 ± 27.9 elo, so the champion's stranding discipline should be *visibly* different from human play).
- **Farm timing** — how early farmers go down; first-farmer turn distribution, farm points per farmer (also directly tests the folk claim "first farmer in a field usually wins it" — Phase 6 Track A).

All are **replay-only**: computable from (deck_seed, action_sequence) via `root_replay` with zero search compute. The E4 diff is naturally **paired** — each E4 game contains a human side and a champion side on the *same* board and deck, killing tile-luck variance the same way deck-pairing does in evals. Known confound: E4 human stats are conditioned on facing a champion opponent, while the reference corpus is champ-vs-champ — so the primary diff should be within-E4-game (human side vs champ side), with the self-play corpus as the champ-vs-champ reference to detect opponent-conditioning.

**Why deferred:** Phase 5/6 work; awaiting Joshua's go on the analyzer/mining MVP (step 1 of the 3-step shape proposed 2026-07-30: descriptive mining memo → analyzer pipeline on phone archives → paired-constraint validation of the top candidates). Mining is ~an afternoon of CPU when greenlit; the binding constraint is E4 sample size (needs actual human games on the phone).

## 2026-07-30 — Real-time move grading in the app ("coach mode" / the analyzer's first live increment)

**Context:** Joshua, same Phase 5 brainstorm as the stats catalog above: after each human move in the Android app, tell the player whether the champion agrees and, if not, the EV delta ("how much of a moronic move it was"). This is the original prompt's Phase 5 expected-value-loss + the "coach mode" stretch goal, made real-time on-device.

**Design sketch (agreed in discussion 2026-07-30):**
- The champion searches the HUMAN's position (same agent/budget it already runs) — either pondering on the human's thinking time (instant feedback, costs battery/thermal) or after commit (~2–4 s delay). Q values are natively in expected-margin points (virtual-score scale), so Δ = Q(best) − Q(played) is the EV loss in points.
- Bridge function `grade_last_move()` → {played, best, delta_points, rank, bucket}; UI badge; settings toggle.
- **⚠️ Noise-floor bucketing is mandatory, and CL-070 is the calibration table:** the champion self-disagrees ~26–30% at fixed budget (44.9% narrow-gap), so "not its top move" is NOT a blunder signal. Buckets by Δ magnitude only: agree / within-noise (say nothing) / inaccuracy / blunder, thresholds derived from the move-agreement probe's self-churn distribution.
- **⚠️ E4 integrity: `coached: true` flag in the archive schema from day one** — coached games are excluded (or separated) in E4 strength stats; they measure the learning curve, uncoached games measure the rating.
- Bonus: every graded move is a labeled (position, played, best, Δ) record — the postgame "top-3 worst moves" report becomes a sort over coach output; the grading tree also contains the champion's next root (future tree-reuse/pondering synergy).

**Why deferred:** the app worktree already carries the unmerged border/start-tile work and the boxes are owned by the leaf ablation overnight; this slots in as the next app work item after the merge window. Needs no new measurement to start — CL-070's data already exists for threshold calibration.

## 2026-07-30 — "Eff Hans": rule-variant exploration to find a better game

**Context:** Joshua, same-night brainstorm: use the apparatus to experiment with RULE changes — road scoring weights, tile-bag composition — and measure whether the variant is a *better game*. Precedent: DeepMind + Kramnik, "Assessing Game Balance with AlphaZero" (2020, chess variants). Our version is far cheaper: the classical champion's search adapts to new rules instantly; only the leaf needs a re-sweep per variant (C5/C7 machinery), no training runs.

**⚠️ The methodological rule (non-negotiable):** never judge a variant with an agent tuned for the old rules — "bug fix shifts optima" applies to rule changes with full force. Pipeline per variant: change rule (scoring table + bag are engine/leaf parameters) → re-sweep affected leaf weights → generate self-play corpus under the retuned champion → judge on the metric suite.

**Game-quality metric suite (instruments already exist for all of these):**
- Luck floor (champ-vs-greedy paired-deck wr; base game measured 6.25% pooled) — the skill/luck dial.
- Decision density (CL-070 self-disagreement machinery; base ~30% near-tie rate).
- Blowout rate + comeback dynamics (margin distributions, lead changes — replay stats / E4 catalog engine).
- Strategy monoculture (farm share of total points, feature-mix diversity — cf. the 2026-07-30 farm autopsy).
- Seat balance (first-player advantage; relates to the parked WC tie-rule entry above).
- Endgame triviality (how early the exact solver latches).

**Note:** we already run an *accidental* variant — walled Carcassonne (the row-6 start-tile grid bound, 68% of games affected; see the 2026-07-30 border diagnosis). Eff Hans makes deviation deliberate and instrumented. Also a charming preprint sibling: "built a champion to beat the game, then used it to redesign the game."

**Why deferred:** each variant costs ~a night of leaf re-sweep + corpus + metrics — a "pick 3–5 candidates" program, queued behind the live Tier-1 items (ANE cell, external anchor). Needs Joshua's go per variant set.

## Killed

<!-- Things Joshua explicitly decided not to do, with reasoning. Keep these so we don't re-litigate. -->

(none yet)

## 2026-08-02 — mutation-test false-green: order-dependent test + benign Tile._turn_cache memo (triage verdict: LOW correctness / MEDIUM test hygiene)
`test_puct_choose_action_never_mutates_caller_board` fails in isolation and ALWAYS HAS —
it was authored (67470f1, 2026-07-07) already-red in a fresh process and only collection
order made it look green. What "mutates": `Tile._turn_cache`, the lazy memo b9431de
(2026-05-13, the 1.79× tile.turn cache) added to the process-global Tile singletons that
every deck shares by design — a pure memo of a pure function; deck order/identity/values
all preserved. **Triage verdict: NO measurement is suspect** (no production code pickles
or identity-keys board.state; flat_leaf's WeakKey memo explicitly depends on the cache).
Deferred fix options (pick one when funded): (a) semantic-snapshot assertion instead of
pickle-byte equality (cheapest, test-only); (b) `Tile.__getstate__` dropping the three
derived caches (fixes all five pickle call sites + shrinks worker payloads, but is an
ENGINE change → needs a bit-exactness gate); plus soften the two "never mutates" docstrings
(`fair_agent.py:449/:893` also warm `board._str_repr_cache`). Same disease class as the
conftest DEFAULT_CONFIG import-order note. Full report: triage agent 2026-08-02 (session
transcript); introducing commit b9431de, test 67470f1.

## 2026-08-02 — two small tickets from the F7b build (agent-found, deferred)
- **Test-isolation failure (pre-existing):** `tests/test_puct_priors_opponent_backend.py` fails
  with `PicklingError: _play_one is not the same object` when run in the same pytest session as
  `test_c5_leaf_ab.py` (module reload aliasing); passes in isolation; reproduced on the unmodified
  main tree. Same disease family as the conftest import-order note and the Tile._turn_cache
  order-dependence (BACKLOG 2026-08-02 above). Fix candidate: spawn-target import hygiene.
- **`gate_eval_puct_priors_backend.py` sets no leaf env** — the 2026-08-02 port-1 G6 artifact
  almost certainly graded the curve100 DEFAULT leaf, not the champion a36d2e15 (identity still
  valid — both legs same leaf — but the label reads stronger than it is). F7b's gate re-ran under
  the launcher's champion env explicitly; patch the gate script to install the champion env (or
  stamp the resolved leaf hash in its artifact) next time it's touched.

## 2026-08-03 — REMEASURE the anticipation pair (and optionally the full component table) under fixed_v1 (Joshua: "we need to remember to remeasure later")
The CL-074 component values (incl. the anticoff pair-null and its +234 interaction) were
measured under WALLED rules with the R9 bug in the farm data. fixed_v1 moved meeple
economy (cloister fix) and farm decomposition (R9) — the balance between the anticipation
halves is coupled to the caps that clip them, so the pair-null does not automatically
transfer. At rust-era cell costs (~13 min/cell two-box) the full 8-cell table under
fixed_v1 is ~2 h. Sequencing: AFTER the caps/curve re-sweep verdict (if the optima moved,
re-tune first, then re-measure components at the new optima — measuring components at
stale optima answers the wrong question). Trigger word: "phase-6 table on canonical
footing."

## 2026-08-03 — WC tie-break rule flag (APPROVED to build, unscheduled)

**Joshua 2026-08-03 evening ("wc tie rule, fine we'll update"):** the one rules divergence
`fixed_v1` does not cover — official WC tie-break vs our engine's tie handling — is approved
for a flag-gated fix in the F9 pattern (default-off flag in both engines, A3-style gates:
flags-off replay regate + flags-on lockstep + mutation probe + composition gate with the
fixed_v1 set; would become part of a future `fixed_v2` profile bundle, adoption a separate
decision). Terminal-scoring-only change ⇒ no mid-game search effect expected; the ablation
sensitivity is tie-frequency-bounded (ties are rare — measure the rate in the Phase C corpora
first to size whether the flag can matter at all). Build when convenient; not launched
2026-08-03 (three agents already in flight).
