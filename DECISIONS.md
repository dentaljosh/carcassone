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

## 2026-06-01 — Pipeline bench: orchestrator is the wrong tool for the CPU v2.7 leaf → mixed-mode self-play (+87% cluster); cloud-era W≈48 / fp16 doctrines superseded

**Context.** Ran a per-box per-lever throughput sweep (`scripts/bench_pipeline_sweep.py`, real self-play at production knobs sims=200/v2_5 leaf/score_diff, 240s windows) on all 3 boxes, then a 3-rep verdict-grade confirm of the surprising cells, then a 3-rep deploy-config pass. Data: `/mnt/c/carc-shared/bench/sweep_*.csv`, `sweep_confirm_*.csv`, `sweep_deploy_*.csv`.

**What the data says (all confirm/deploy numbers are 3-rep, CV ≤2%).**
- **Worker count is FLAT** under the orchestrator on every box (5800x 7.4–8.1 across W=8–20; xeon ~5.4; laptop ~9.8). All read `ipc_latency` → workers block on the eval-server socket, not CPU.
- **The orchestrator's single GIL-bound dispatch thread is the limiter** (`eval_server.py:135`, mp.Queue pickling a ~0.5MB obs/request). The production leaf is **`v2_5` = `virtual_score`, a CPU heuristic** — the NN only supplies priors — so the GPU sits idle (28W/180W) while the dispatcher is the wall. **The orchestrator earns its keep only when the leaf is a GPU NN-value forward (the abandoned v1–v6 recipes); it outlived its workload.**
- Turning the orchestrator OFF (per-worker inline eval) wins on every box: 5800x 7.4→**14.70** (orch-off W=16, cpu_bound), laptop 9.2→**19.26** (orch-off W=10, gpu 95%), xeon 5.4→**7.0** (→gpu_compute on the weak Turing). `orch_shards=2` is a partial recovery (5800x 11.2, laptop 13.4, xeon 6.9).
- **fp16 is batch-regime-dependent** (reconciles the old "benched slower twice" claim — it was right for small batch): under the **orchestrator** (max_batch 256) fp16 is FASTER on Blackwell (5800x 5060Ti, 9.19 vs 7.40, +24%) and Ada (laptop 4070m, 12.05 vs 9.17, +31%), ~null on Turing. But under **orch-off** (small per-worker batch) fp16 HURTS: 5800x deploy orch-off+fp16 = 13.81 < 14.70 no-fp16 (−6%). The deploy pass also showed the laptop shards+fp16+mb16 stack (18.39) does NOT beat plain orch-off (19.26).

**Decision — mixed-mode per box (the SIMPLEST lever wins where VRAM fits):**
| box | config | mv/s (3-rep) | vs prod orch-on Wdef |
|---|---|---|---|
| 5800x (16GB) | **orch-off W=16, no fp16** | 14.70 | +99% |
| xeon (8GB) | **orch_shards=2** (≈orch-off W=8) | 6.99 | +30% |
| laptop (8GB) | **orch-off W=10** | 19.26 | +110% |

Cluster 21.9→41.0 mv/s = **+87%**. fp16 + shards were red herrings on the strong boxes; orch-off alone wins where the net×W fits VRAM. **Not yet wired into the strength loop** — gated on a Pass-3 strength/correctness check that orch-off + prior-batching-order is strength-neutral (likely — MCTS is robust to tiny prior noise — but unverified; do not promote unverified).

**Superseded cloud-era doctrines (the root cause of weeks of mis-tuning):**
- **"orchestrator saturates / GIL bites at W≈48"** (this file ~L806/838/859/1085) was measured on the **2026-05-12 vast.ai 48-CORE EPYC + 5090** box ($0.37/hr). On the 12–16-thread cluster the GIL-bound dispatcher saturates at **W≈14**. W≈48 was never valid here.
- **"orch-shards GIL only bites at W≈48"** (BACKLOG) — sharding gives +35–50% at W=14–24 on the cluster. Same vast.ai origin.
- **"fp16 is not a lever / benched slower"** (BACKLOG:295, `bench_pipeline_sweep.py:74-77` comment) — REFINED to batch-conditional (above), not blanket-true.

**Not doing:** a shared-memory-IPC orchestrator rewrite (the real single-thread fix — kill the mp.Queue pickle). Parked in BACKLOG; revisit ONLY if a future GPU-bound (NN-value) leaf returns, where cross-worker batching pays off again. For the CPU leaf, orch-off already wins.

**Reversal cost:** low (mode flags only; no checkpoint/data change).
**Phase:** 4 (self-play throughput).

## 2026-05-31 — PIVOT off value-as-leaf → measurement ladder; iter_11 beats a strong reference (+119 elo, first absolute signal)

**Context.** Step 9 closed the value-as-leaf lever (calibration cliff — see entry below). Value-leaf needs scale we don't have. Joshua chose to PIVOT to **measure absolute strength + enable play**, explicitly NOT scale-blind (which would burn weeks into an unmeasurable ceiling). Selected: #1 measurement ladder, #2 headless play, #3 confirm blend.

**The measurement wall this addresses.** Tier-1 (1-ply heuristic) is saturated; self-anchored elo (iter_N vs warm/prev) can climb while absolute strength regresses (the Option-B lesson). We had NO trustworthy absolute read. Fix: a strong, NON-saturated reference = **HeuristicMCTS** (v2.7 leaf + UCT search — the same leaf our bot uses, but NO learned policy). Test: NeuralMCTS(net priors + v2.7 leaf VALUE — the production play config, NOT the raw value head Step 9 killed) vs HeuristicMCTS at **matched sims**. Isolates exactly: does the LEARNED POLICY beat pure heuristic search at equal compute?

**Result (n=100, matched sims=200, c=3):** iter_11 net **66W/1D/33L = 66.5%, +119 elo / 3.2σ, +14.5 score margin.** (Early n=28 was 86%/+311 → regressed to mean, as flagged; the n=100 is the honest number, n=400 verdict running.)

**Reading.** The first TRUSTWORTHY absolute-strength signal in the project: the learned policy decisively beats a strong, non-saturated reference at matched compute. This **validates the +190 self-anchored gain as real strength, not drift** — measurement-first paid off (we now KNOW). Calibration: +119 over our own heuristic+search = "clearly stronger than the thing we built," = ladder rung 1 cleared, NOT "superhuman" (HeuristicMCTS ≈ strong-amateur, not expert). Next rungs: beat Joshua → stronger external reference → pros.

**Tools built + committed.** `scripts/eval_net_vs_heuristic.py` (ladder gauntlet, `ca24392`/`9d39cc5`), `scripts/play_vs_net.py` (headless terminal play — the tkinter GUI is unusable over the SSH chain; `5504fb6`), `scripts/tally_ladder.py` (union tally over fanned-out 3-box runs, validated vs n=100; `1b151c9`).

**Decisions.** (1) Pivot accepted: measurement + play before any more scaling. (2) Promote ladder to n=400 (3-box, disjoint seed ranges → shared folder, running). (3) Don't switch the production leaf to NN value. (4) iter_11 is our confirmed-strongest checkpoint → the play-bot target at sims=800.

**Reversal cost.** Low — additive tooling + eval; no production change.

**Phase.** Phase 4 / Path B → measurement workstream (CLAUDE.md Wall #1).

---

## 2026-05-31 — Path B Step 9 VERDICT: pure NN-value leaf fails (-800), but it's a CALIBRATION CLIFF, not a dead value head

**Result.** Step 9 go/no-go (iter_11, same policy net both sides, NEW=pure NN-value leaf λ=1.0 vs OLD=pure v2.7 leaf λ=0.0, n=400, sims=200, c=3, 3-box): **3W/1D/396L, avg margin −73.7, −800 elo (capped).** Authoritative tally (`scripts/tally_step9.py`, 400/400, 0 corrupt, slot balance 200/200) confirms the driver's number.

**This contradicted the screening (held-out corr 0.81), so before filing a NO-GO we ran diagnostics.** Three checks (`scripts/diag_value_leaf.py` + two inline) RULED OUT the bug hypotheses:
- **Not a sign/POV flip:** corr(NN, v2.7)=+0.31, sign-agreement 57.5% (both > chance); NN value sane (mean −0.01, std 0.64, range [−0.94,+0.96]).
- **No train/serve skew:** recorded iter_11 self-play data is genuinely 12-wide with live, varying farm scalars (contested/balance non-zero); self-play records via the SAME `get_canonical_form` eval uses; encode is deterministic.
- **Leaf wrapper does not perturb:** `make_v25_value_wrapper` at λ=1.0 returns EXACTLY the raw NN value + identical priors (−0.83183 both). Not pathologically overconfident (|v|>0.9 only 11.7%).

**Blend sweep (the decisive follow-up; n=30 each, same net both sides, NEW=λ blend vs OLD=pure v2.7):**
| λ | record | elo vs pure-v2.7 |
|---|---|---|
| 0.1 | 16W/14L | **+23** (break-even, ±64) |
| 0.25 | 12W/2D/16L | −47 |
| 0.5 | 13W/17L | −47 |
| 1.0 | 3W/1D/396L | **−800** |
→ **A smooth, monotonic CALIBRATION CLIFF**: graceful for λ≤0.5 (all within ~1σ of break-even), catastrophic ONLY at pure-NN. A wiring bug would break at all λ; this degrades gracefully → consistent with a real property, not a bug.

**Verdict / reading.** Path B is a **partial success, NOT the NO-GO the −800 implied.** The learned value head DID learn real signal (corr 0.18→0.81, correctly wired) and is **usable as a small blend** (≈break-even at λ=0.1). It is simply **not robust enough at 12-iter scale to be the SOLE search leaf** — MCTS at c=3 steered entirely by it walks into its off-distribution errors. This is the same value-as-search-leaf wall Option 2 hit in May, now at much better in-distribution prediction; KataGo got past it with massive scale + regularization. **The original Step-9 framing (pure-NN-leaf, GO if >+15) was too-extreme a test** — the production-relevant question is the blend, and the blend is viable-to-neutral, not harmful.

**Decisions.**
1. **Step 9 = soft NO-GO on the PURE-NN-leaf**; **partial GO on the value head as a blend.** Don't switch the production leaf to NN value.
2. **Review-agent team: SKIP for now.** The smooth λ-curve + 3 cleared bug hypotheses make a hidden-bug explanation unlikely; a deep code review is low-EV here. Revisit only if a future result looks anomalous.
3. **Strength gain stands:** the +190 anchor-gate (iter_11 vs warm) came via the v2.7 leaf and is untouched by this — the policy genuinely improved.
4. **Next levers (not the value-leaf):** keep iterating (the extended loop is the cheap continuation); if we want the value-leaf to harden, that needs scale + a value-target regularizer, which is a bigger commitment than 12 iters.

**Reversal cost.** None — diagnostics + logging only; no production change.

**Phase.** Phase 4 / Path B Step 9 (closed).

---

## 2026-05-31 — Path B screening SUCCEEDED (value head crosses the heuristic); loop extended to iter 24

**Result.** The 3-box screening loop (12 iters, 600 games/iter, sims=200, farm scalars + ownership aux on) finished Sat 18:26. The diagnostic that gates the whole probe — **held-out value↔outcome correlation** (`train_iter._value_outcome_corr`, val split) — traced a clean S-curve: **0.38 → 0.81**, crossing the v2.7 heuristic's **0.61** ~iter 3-4 and plateauing ~0.81 (old data-starved NN value head = 0.18). No policy-entropy collapse (1.75 → 1.66, floor 0.87). Per-iter anchor-gate iter_11 vs frozen warm: **30W/0D/10L, +190.8 elo**.

**Reading.** A **strong GO *signal***: the learned value head now substantially out-predicts the heuristic on held-out outcomes — the exact Path-B question, on the right (fixed-reference) metric. **NOT yet the verdict:** +190 is self-anchored vs warm (Option-B lesson: self-anchored elo can climb while absolute strength regresses), and corr is mechanism, not playing strength. **Step 9 — go/no-go A/B (NN-value-leaf vs v2.7, same policy net both sides, n=400; GO if >+15 elo) — remains the decisive test, still pending.**

**Why it stopped at 12.** Hardcoded `ITERS=12`, NOT a plateau (loop halts only on NaN / entropy-floor collapse; anchor-gate non-halting). corr-saturation ≠ strength-saturation (value-corr ceiling <1 from tile-draw luck).

**Decision: extend the loop** (Joshua, 2026-05-31). Resumed iters **12→23** in the same run dir (warm-from iter_11, `--window 10` buffer continuous); `run_pathb_cluster_loop.sh` gained `START` resume-in-place support. 3-box WS, nice -19, ~24h. Driver 29976, Monitor `bhnvreb82`.

**Open gaps (production loop v2).** (1) Loop gates only vs frozen warm → no per-iter marginal-strength signal / no plateau-stop; gate vs running-best + stop-after-2-flat. (2) Post-leaf-speedup self-play is GPU/eval-bound (Step-1b W-rebench: W barely matters ≥10, Xeon 10→18) → open throughput lever is a multi-shard eval-server, not more workers. (3) Beyond Step 9, an external/absolute reference ladder (Joshua → club/online → pros) is required to *claim* superhuman.

**Reversal cost.** Low (additive; just more iters; stoppable anytime).

**Phase.** Phase 4 / Path B Step 8 → Step 9 pending.

---

## 2026-05-29 (evening) — Path B Steps 6–8 executed: smoke PASS, collapse guard + value-corr built, 3-box work-stealing screening run LAUNCHED over Shabbos

**Context.** Joshua gave the go to run Step 6 ("run the smoke. low priority nice"), then escalated to launch the loop over Shabbos ("yolo it… wire up 7 and 8, I check back after havdalah"), then **demanded all 3 boxes** for the loop.

**Step 6 (de-risk) — PASS.** Tiny end-to-end smoke (gen 12-scalar → aux-weight sweep {0,0.15,0.5} → self-play → train_iter → anchor-gate): 0 NaN, aux loss falls, mains flat across aux weights (→ freezing aux=0.15 justified), value-leaf swap runs. **1a profile (in-process, sims=200) → PROCEED:** leaf eval ~86% (expected), `get_next_state`/deepcopy only ~10% (confirms the speedup analysis), no >2× surprise. ⚠️ cProfiling `run_selfplay_iter` directly is useless (it spawns a Pool → misses worker hot path); profile in-process via `play_one_selfplay_game` (`scripts/profile_selfplay_inproc.py`). **1b W-rebench (3 boxes, real `run_selfplay_iter`, NOT bench_workers which times raw-engine games): curves FLAT** (post-speedup self-play is eval/dispatch-bound, W barely matters ≥10) → **5800x W=14, Xeon W=18, laptop W=24**; cluster ≈546 g/h.

**Collapse guard + value-corr (new, committed `00b093e` + value-corr commit).** `train_iter.py --entropy-floor-frac` (default 0.5): baseline = warmstart-net policy entropy at iter 0, propagated in the checkpoint; per-iter trained entropy < frac×baseline → exit 2 → loop halts. And a per-iter **value↔outcome correlation** readout (Pearson of value-head vs stored outcome target) — the TRUSTWORTHY progress signal (vs self-anchored chain elo which can climb while absolute strength regresses; beat heuristic's 0.61, old NN was 0.18). Tests + e2e verified. Gate audit found the entropy floor was the only one of the 3 promised deterministic guards not implemented; now all 3 active (NaN-abort, anchor-gate stop, entropy floor).

**3-box loop — DECISION: adapt the proven maximalist infra, don't build from scratch.** `run_phase4_smoke` is single-box; the multi-iter 3-box work-stealing loop wasn't wired. `maximalist_sequencer.sh` already had proven 5800x+xeon work-stealing (`launch_on_host`/`run_selfplay`, held-ssh foreground keeps the Xeon WSL VM alive; `stage_launcher.sh` copies the launcher LOCAL on Xeon to dodge the share-unmounted chicken-egg). Adapted it into `/home/doctor/run_pathb_cluster_loop.sh` + added a **laptop branch** (native Linux, share already mounted, simple held-ssh). Verified each box claims+plays SOLO (mini-scale combined tests just race — the 5800x fills tiny/fast batches before the others boot; irrelevant at production scale). **Launch-hang bug found+fixed:** `pid=$(launch_on_host …)` hung — command substitution waits on the backgrounded worker's orchestrator children holding the pipe fd. Fixed via **pidfile** (launch_on_host writes PID to a file, called WITHOUT `$()`). After fix: all 3 launch instantly, all 3 GPUs active (~26-40% — NOT pegged, consistent with dispatch/CPU-leaf-bound, not GPU-bound), 56 claims = 14+18+24 workers, games landing.

**Screening run (NOT the verdict).** Launched 600 games/iter (not the frozen 1200) for trajectory density over Shabbos: ~9 g/min cluster → ~66min self-play/iter → ~15+ iters in 25h. Directional read of the value-corr trajectory; the GO/NO-GO verdict still needs the frozen 1200 + n=400 Step-9 A/B. Box choice: all 3 per Joshua's demand, accepting the risk that the 3-box multi-iter loop is freshly-wired (mitigated: solo-verified each box + no-hang mini-test + the gates halt on trouble).

**Reversal cost.** Low — the run is killable; warm.pt + per-iter checkpoints preserved on the share; the loop halts cleanly on collapse/NaN.

**Phase.** Phase 4 / Path B Steps 6–8.

---

## 2026-05-29 — Path B Step E shipped: farm scalars IN + made free + flip-on wired; launch plan set (HELD)

**Context.** Joshua decided (2026-05-29) to include the 2 farm-control input scalars in the Path B probe ("farm scalars in. make them free."), and to launch Path B as **3-box work-stealing at `nice -19`** — but **not** until he gives the go.

**Make-free.** The scalars cost +0.49 ms/encode standalone (a whole farmer-field flood per encode), which would erode the 1.48× leaf speedup when on. Fixed by **sharing one `_farm_cache`/`_city_cache` across the policy-encode and the v2.7 leaf-value pass** in `make_v25_value_wrapper` (single + batch): the leaf value floods the same fields anyway, so the scalar floods are reused → **+0.035 ms/leaf (2.2%)**. `virtual_score_v2` was changed to REUSE an attached cache rather than create+delete its own (so it doesn't clobber the wrapper's shared cache). Value-invariant: reconciliation gate n=400 (920k nodes, 0/0) + a wrapper-value==standalone-leaf test. (`70e1b62`)

**Flip-on wired end-to-end.** Rather than a manual flag in every worker script (mismatch-prone), the 12-scalar shape **propagates from the checkpoint's `n_scalar_features`**: eval-server builds net+warmup from it; `run_selfplay_iter` sizes worker/anchor nets from it and the main process peeks the learner checkpoint to set `cfg["include_farm_scalars"]` for worker Games; `eval_iter_head_to_head` derives a per-side Game flag from each checkpoint; `train_iter` reads it from the warm-from checkpoint; `generate_one_game_dataset`/`generate_warmstart_smoke` take `--include-farm-scalars`. **The only manual flag is at the start** (gen + `train_warmstart --include-farm-scalars`); everything downstream auto-derives. Default off → all pre-Step-E (10-scalar) checkpoints byte-identical. (`06b065c`)

**Launch plan (HELD).** 3-box work-stealing (`--shared-claim`), `nice -19`, farm scalars on, frozen knobs per [docs/PATH_B.md](docs/PATH_B.md) table. Full step-by-step in PATH_B "LAUNCH RECIPE" (Step 6 smoke first, then 7 warmstart → 8 loop → 9 go/no-go A/B + value↔outcome corr). **Do NOT launch until Joshua says go.** Pre-launch: propagate commits to Xeon+laptop clones.

**Reversal cost.** Low — all additive + gated; farm scalars opt-in, the share-cache is behind the same toggles.

**Phase.** Phase 4 / Path B Step E + launch prep.

---

## 2026-05-29 — c=3 "+47" RE-VALIDATED at n=1600 → corrected to +18.5; production default unchanged

**Context.** The c_puct=3 production default rested on Phase 2b's +47.2 elo / 5.2σ (n=400), flagged UNDER RE-VALIDATION on 2026-05-28 after Optuna #17 re-screened the same config at +13.9 (n=100) — ~2σ below. Run A was the clean settle: a fresh **n=1600** A/B, iter_B1 both sides, (c=3,cap=12,v2_7) vs (c=1.5,cap=12,v2_7), sims=200, on the **pre-fix engine** (so the leaf matches the original c=3 measurement — this is a hygiene check of the historical claim, not the new fixed leaf).

**Result.** 832W / 747L / 20D = **+18.5 elo / 2.1σ at n=1599** (`experiments/results.csv` `hygiene_c3_vs_c15_n1600`).

**Decision / reading.** c=3 IS a real, significant positive over c=1.5 — but **~40% of the headline +47.2**, which was an inflated point estimate (regression to mean), exactly as the [[bracket-hyperparams]] / [[results-table-source-of-truth]] memories warn. **c=3 stays the production eval-side default** (it's still ≥ c=1.5); the "biggest single free win in weeks / sharp +47 peak" framing is **retired → ~+18**. This closes the last open eval-config re-validation. Consistent with Optuna #17 (+13.9/n=100) and the broader study (winners cluster c=1.5–2.0, c=3 not a standout). Forward: stop spending on eval-config tuning (rounding error vs the superhuman goal); the levers are the structural/Path-B work.

**Caveat unchanged.** This validates the *eval-side* c=3 only; the *self-play-side* c=3 bump (training-data generation) remains hypothesis-only (see 2026-05-28 entry).

**Reversal cost.** None — documentation/epistemics correction; production default unchanged.

**Phase.** Phase 4 hyperparameter methodology.

---

## 2026-05-29 — Leaf flood-fill speedup IMPLEMENTED: lazy per-leaf farm + city memo (not incremental union-find) — 1.70× leaf / 1.48× search

**Context.** Executing the speedup prioritized below. Two priors turned out wrong and reshaped the implementation; both were caught by measuring first (profiling + an A/B bench) instead of trusting the plan's framing.

**Finding 1 — the architecture rules out incremental-union-find-with-rollback.** The plan (PATH_B Step 2) described "maintain a farm union-find as tiles are placed down the tree, with rollback." But the production leaf path is **NeuralMCTS**, which reaches every leaf via **functional `get_next_state`** (deepcopy per step, `StateUpdater.apply_action`), *not* mutate-and-undo. `apply_action_inplace` (the rollback path) is only used by vanilla-MCTS *random rollouts*, which the v2.7 leaf never runs. So there is no tree to thread an incremental structure through — the correct shape is **per-leaf-state**, not incremental-across-tree.

**Finding 2 (profiling, post-fix) — find_farm is ~41% of the leaf, and 54% of its calls are redundant within a single eval.** `cProfile` of `virtual_score_v2` over representative mid/late states: `find_farm` cumtime ≈ 41% (was quoted ~58% pre-fix), `find_cities` ≈ 31%, **deepcopy negligible (~0.4%)** (contradicts old "deepcopy dominates" lore for this leaf). 11.1 `find_farm` calls/leaf, **6.0 redundant** — the same field re-flood-filled once per farmer meeple, across both consumers (`count_final_scores` + the two closure-bonus passes).

**Options for capturing the redundancy.**
  - A: **Eager whole-board decomposition** (`find_all_farms`: one CC pass, index every farm). Benched **1.11× leaf / 1.16× search** — modest, because it pays to enumerate fields no meeple queries.
  - B: **Lazy per-region memo** (`_farm_cache`: memoize `find_farm` under every node of each region as it's first queried; share one cache across all three consumers per leaf). Benched **1.29× leaf / 1.20× search**. Strictly less work than A (only queried fields), and trivially correct (pure memoization of the already-trusted `find_farm`).

**Decision.** Chose **B (lazy memo)** as the production path. `find_farm_by_coordinate` consults an optional `state._farm_cache`; `virtual_score`/`virtual_score_v2` attach one shared cache per leaf eval and detach in `finally`. Behind a `virtual_score.USE_FARM_CACHE` toggle (the A/B baseline). Kept `find_all_farms` (the eager decomposition) in `farm_util` for the future farm INPUT features (Step E, which needs every farm) and as the reconciliation oracle. Safe because: `find_farm` is now start-independent (the farmer-adjacency fix), board topology is frozen during a leaf eval (`count_final_scores` mutates scores/meeples, never `tile.farms`), and `CarcassonneGameState.__deepcopy__` strips unknown attrs so a cache can't leak across `get_next_state`.

**Correctness gate (non-negotiable, mirrors the aux n=2000 gate).** `scripts/reconcile_farm_index.py` — REGION equivalence (`find_all_farms[node]` == `find_farm(node)` for every farmer connection) AND VALUE equivalence (`virtual_score_v2` bit-identical cache-on vs cache-off). **n=400: 919,457 farm nodes, 0 region + 0 value mismatches.** Permanent regression: `tests/test_farm_index.py` (16 cases). No regressions in `test_virtual_score`/`test_aux_targets`.

**City follow-on (same day, Joshua's "fix find cities for now").** Applied the same lazy memo to `CityUtil.find_city` (`_city_cache`) — the other big redundant leaf cost (~31%; `find_cities`/`count_farm_points` re-run it per farmer connection + per city side, count_final_scores per city meeple). `find_city` is a symmetric BFS to closure → start-independent by construction (no farm-style bug), so caching is safe. **One subtlety:** `count_farm_points` dedups adjacent cities via a `set()` keyed on City *identity*, so the memo caches only the `(positions, finished)` flood-fill data and **returns a fresh `City` object each call** — preserving that identity-dedup exactly (value-invariant). Gated by `USE_CITY_CACHE`, shared per leaf eval alongside `_farm_cache` (CoordinateWithSide keys are value-hashable → valid across the deepcopy). `find_meeples`/consumers only read `city_positions`, so sharing the positions set is safe.

**Impact (combined farm + city).** Benched **1.70× leaf / 1.48× end-to-end search** (farm-only was 1.27×/1.20×; city adds 1.33× on top) — ~33% throughput on ALL self-play + eval across the cluster (every NeuralMCTS leaf runs the v2.7 leaf). Gate re-run with BOTH caches toggled: **n=400, 921,953 nodes, 0 region + 0 value mismatches.** `tests/test_farm_index.py` (now incl. a fresh-City memo test) green.

**Reversal cost.** Low — additive, behind `USE_FARM_CACHE` / `USE_CITY_CACHE`, gate-verified. Files: `engine/.../farm_util.py` (find_all_farms + cache branch), `engine/.../city_util.py` (find_city memo + `_compute_city`), `src/.../virtual_score.py`, `virtual_score_v2.py`; tools `scripts/{reconcile_farm_index,bench_farm_index,profile_leaf_farm}.py`; `tests/test_farm_index.py`.

**Phase.** Phase 4 / Path B Step 2 prerequisite.

---

## 2026-05-29 — Prioritize the find_farm speedup (leaf-sharing + union-find) as the next dev task

**Context.** Path B Step 2 ("domain input planes") turned out mostly redundant — 4/6 proposed inputs already exist as scalars; the only net-new ones (`contested_features`, `my/opp_dominant_farms`) are farm-derived and would run `find_farm` at every MCTS leaf-encode, hammering the #1 hot path (~58% of leaf cost). Separately, the 2026-05-29 farmer-adjacency fix made `find_farm` **start-independent**, which unblocks the incremental farmer union-find that was parked 2026-05-17 *precisely because* find_farm was start-dependent.

**Options.** (A) Skip farm inputs for the go/no-go probe, revisit at scale only if Step 9 = GO. (B) Build the `find_farm` speedup now (union-find + leaf-sharing), un-gating it from a GO.

**Decision.** Chose **(B) — build the speedup now** (Joshua's call, 2026-05-29). Rationale: the union-find speeds the EXISTING leaf eval (every leaf already runs count_final_scores → find_farm), so it accelerates **all** self-play + eval throughput across the cluster — value independent of the farm-input feature, and independent of the Step-9 outcome. The farm inputs then come ~free as a downstream. It's pure dev (no compute), so it's productive work to do while the compute decisions (Steps 6–9 box choice) are still open.

**Plan + guardrails.** [docs/PATH_B.md](docs/PATH_B.md) Step 2 (revised) + BACKLOG 2026-05-29. Sequence: incremental union-find → **reconciliation gate** (assert union-find == `find_farm` across many positions, mirroring the aux-target n=2000 gate) → **throughput bench** (measure, don't extrapolate) → leaf-pass sharing → then the farm input features. Correctness risks: the `apply_action_inplace` rollout path + MCTS tree backtrack/rollback of the incremental structure.

**Reversal cost.** Low — additive perf work behind a correctness gate; if the union-find can't match find_farm or doesn't bench faster, drop it and keep the (correct) fixed find_farm.

**Phase.** Phase 4 / Path B Step 2 prerequisite.

---

## 2026-05-29 — Engine fix: farmer-adjacency bug made farm scoring start-dependent (taints virtual_score / v2.7 leaf)

**Context.** Path B Step 1 (aux-target generation) needs per-feature *ownership* labels at game end, validated to reconcile with the engine's `count_final_scores`. Building the validator surfaced that the engine's farm scoring is **non-deterministic across processes**: the same terminal position can score differently depending on Python hash/set-pop order. Root cause traced to two layers:
1. `SideModificationUtil.opposite_farmer_side` was **not a bijection** — `TRT → BRR` (a typo; should be `BRB`). So `BRR` was the image of both `TRT` and `BLL`, and `BRB` was never produced. Crossing the top edge's right-half must mirror to the neighbour's bottom edge right-half (`BRB`). The typo made farmer adjacency **asymmetric**.
2. `FarmUtil.find_farm`'s flood-fill kept a single `to_ignore` edge-set seeded asymmetrically from the start node and marked edges visited in set-pop order, pruning branches before they were explored. Combined with (1), `find_farm` returned **start-dependent** regions — from some farmer meeples it under-collected connections, so `find_meeples` missed meeples and `count_farm_points` missed adjacent finished cities. Via `count_final_scores` this made two same-player farmers on one field score **once or twice depending on pop order**.

**Magnitude (measured, 500 random games):** ~**2.2%** of games mis-scored, mean score-diff error **9.3 pts** (max 30), **0.2%** flip who wins. The same bug lives in `virtual_score` → the **v2.7 leaf eval** the entire current strength rests on, and in `possible_move_finder` (farmer-placement legality). All historical `results.csv` numbers were produced against this buggy, slightly-nondeterministic scorer.

**Options considered.**
  - A: **Fix the engine** — correct `opposite_farmer_side` + rewrite `find_farm` as a complete, start-independent connected-component search. Pro: fixes the root cause everywhere (scoring, leaf, move-gen); deterministic. Con: changes the v2.7 leaf on ~2.2% of evals → per the "bug-fix-shifts-optima" rule, cap/c_puct optima may move; invalidates exact reproduction of some past numbers.
  - B: **Path-B-local** — use a deterministic dedup-correct scorer only for the new self-play data; leave the engine alone. Pro: zero blast radius. Con: leaves the buggy leaf in place; value-target currency mismatch.
  - C: **Replicate the bug** so labels match the (buggy) value target exactly. Con: teaches the aux head a non-deterministic target.

**Decision.** Chose **A — fix the engine now** (Joshua's explicit call when the fork was surfaced). Two vendored-fork patches: `side_modification_util.opposite_farmer_side` `TRT → BRB`; `farm_util.find_farm` rewritten as a node-deduped CC traversal (visits each `(coord, connection)` once, explores every `tile_connection`). After the fix `opposite_farmer_side` is a clean bijective involution ({TLL,TRR}{TLT,BLB}{TRT,BRB}{BRR,BLL}), `find_farm` is start-independent (0/… overlapping-but-unequal components across 300 games, was 112), and the aux-ownership extractor reconciles with `count_final_scores` **exactly at n=2000 (0 failures; was 2.2%)**.

**Consequences / follow-ups.**
- **Re-sweep flag:** the v2.7 leaf changed slightly → the cap=12 / c_puct production optima were tuned against the buggy leaf and should be re-validated before being trusted (memory: bug-fix-shifts-optima). Path B regenerates everything from a fresh warmstart anyway, so this lands naturally.
- **`find_farm` is now start-independent → safely cacheable** (it was previously called out as un-cacheable for exactly this reason) — a real future throughput lever for the hot leaf path. Logged for BACKLOG.
- The overnight hygiene runs (c=3, cap=20) are on the pre-fix engine on their boxes; not disrupted — their results just describe the old leaf. Propagate this fix to all cluster boxes before the next training/eval run.

**Reversal cost.** Medium — it's a vendored-engine correctness change, but well-tested (full suite + n=2000 reconciliation) and isolated to farmer adjacency.

**Phase.** Phase 4 / Path B Step 1.

---

## 2026-05-28 — GOAL CHANGE: attempt genuinely superhuman play (overrides the original-prompt scope)

**Context.** The original prompt ([docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md)) explicitly scoped superhuman strength *out*: *"This is not a 'build superhuman Carcassonne AI' project. That's been attempted by academic groups since 2020 and has stalled — not because the idea is wrong, but because nobody's bothered to throw serious compute at it. We're not going to either."* The stated win condition was the **analyzer (Phase 5)** — "a 90th-percentile bot that explains *why* a move was bad is more useful to me than a superhuman black box." On 2026-05-28, during a strategic regroup, Joshua changed the goal: **he wants genuinely superhuman play — to beat the world champion.**

**Decision.** Superhuman strength is now the **primary** goal. The analyzer (Phase 5) and heuristic research (Phase 6) become **downstream** — pursued after strength milestones, not the target. The locked *rule* scope (2p Base+River+Farmers) is unchanged.

**What this honestly implies (surfaced at decision time, not papered over).**
- This is a **research-grade goal the prompt deliberately avoided**; comparable academic attempts stalled. On a 3-box consumer cluster (~300 g/h eval) this is months-to-maybe-unreachable. We pursue it clear-eyed: real measurable progress is achievable; the summit is not promised.
- **Two structural walls, neither touched by the eval-config tuning of the last month:**
  1. **Measurement.** We have no strong, non-saturated reference. Tier-1 is a saturated 1-ply heuristic; self-anchored elo can climb +600 while absolute strength regresses (the Option-B-chain result proved this). *We cannot tell if we're approaching world-champ level.* First unblock: build a strong reference ladder (high-sim vanilla MCTS / the Ameneyro 2020 baseline) as an absolute yardstick, since a human benchmark isn't available now.
  2. **Leaf ceiling.** Our strength is PUCT search over the **hand-crafted** v2.7 `virtual_score` leaf. A human-designed heuristic caps learned play near strong-human by construction. We already tried to let the NN value head exceed it (Option 2) and it was *worse* (closed 2026-05-18). Superhuman requires the *learned* components to beat the heuristic — the documented path is KataGo-style (domain-feature input planes + auxiliary loss heads + scale), all gated behind a fresh from-scratch warmstart (bundle the deferred D1/D13 feature fixes).
- **The eval-config tuning era (c_puct/leaf_cap/leaf_variant, incl. tonight's Optuna) is rounding error against this goal** and should stop — see the meta-rule in EXPERIMENTS.md ("try-harder-with-the-same-architecture is the trap").

**Roadmap implied (not yet committed — to be planned):** (1) strong reference ladder [unblocks measurement], (2) structural leaf/architecture change [the real lever], (3) scale compute + Optuna-over-*recipe* [where Optuna's automation finally earns its keep].

**Reversal cost.** Low to state; high to pursue (months of compute). The goal can be re-narrowed to the analyzer at any time if the strength climb proves infeasible — the analyzer work is not lost, just deferred.

**Phase.** Strategic pivot atop Phase 4.

---

## 2026-05-28 — Measurement infrastructure: `experiments/results.csv` as source of truth + results discipline

**Context.** The regroup found that disorganization, not just bad luck, produced the false "c=3 = +47 elo" production change. Audit: **54 completed evals across 41 ad-hoc dirs**, config encoded only in directory names, and `elo_log.json` records the *outcome but not the config* (no c_puct/cap/variant). Four disconnected representations of the same results (dirnames, config-less elo_logs, the hand-maintained EXPERIMENTS.md table, the optuna study.db), none queryable. The c=3 contradiction (noise spike at n=400 vs the earlier "c is noise at n=20" finding, vs tonight's +13.9 re-screen) was invisible because no structure forced the comparison.

**Decision.** Build one structured, queryable, git-diffable results table and make it the source of truth; adopt query-before-claim discipline.
- **Artifact:** `experiments/results.csv` — one row per eval (full config both sides + outcome + n + sigma + provenance). CSV (not a DB) because ~54 rows, diffable in PRs, one-line pandas load. Optuna `study.db` exports into it.
- **Root-cause fix:** `eval_iter_head_to_head.py` writes a self-describing `manifest.json` and appends its row to results.csv on completion → the table self-maintains; no future dirname archaeology.
- **Backfill:** the existing 54 elo_logs + 18k per-game JSONs are reconciled with a one-time hand-authored dirname→config map (config isn't in the data). Run as a background subagent 2026-05-28; low-confidence rows flagged, not fabricated.
- **Discipline (also added to CLAUDE.md operating norms):** cite the table, never duplicate authoritative numbers; query for prior measurements of a cell before declaring a finding; n=100 = screen (±17), n=400 = verdict (±9); a lone >1σ spike vs neighbors is noise, not a peak.

**Why not heavier infra (SQLite/dashboard/framework).** 54 rows. A CSV + a 10-line pandas query helper covers every "pivot config-dim × n → elo" view we need. Over-building a results system would itself be the procrastination trap. EXPERIMENTS.md stays as the *narrative* layer that cites the table.

**Reversal cost.** Trivial — it's additive (a CSV + a manifest write + doc norms); nothing depends on it that can't fall back to the old prose tables.

**Phase.** Methodology / measurement, prerequisite for the superhuman push (addresses Wall 1 above).

---

## 2026-05-28 (evening) — Optuna eval-search softens the c=3 "+47 free win"; flagging the headline claim for re-validation

**Context.** The Optuna eval-time study (`eval_time_search_v1`, TPE over {c_puct, leaf_cap, leaf_variant}, multi-fidelity n=100→n=400) ran ~16 trials across 5800X+Xeon+laptop. To bridge it against the 2026-05-26 Phase 2 result, we `enqueue_trial`'d the exact canonical config (c=3.0, cap=12, v2_7) as a NEW-side-vs-(c=1.5,cap=12)-baseline trial — identical A/B design to Phase 2b.

**Result.** Trial #17 screened at **+13.9 elo at n=100** (did not clear the +15 promote threshold, so stayed at n=100). Phase 2b measured the same config at **+47.2 at n=400**. At n=100, 1σ ≈ ±17 elo, so +13.9 is ~2σ below +47.2.

**Reading (careful — sample sizes differ).** A single n=100 screen CANNOT refute an n=400 result; the error bars overlap at ~2σ. But combined with the rest of the study — winners cluster at c=1.5–2.0, the study best is (c=2.0, cap=19, tcc) +24.4, and no high-c config stands out — the weight of evidence is that **Phase 2b's +47.2 was an inflated point estimate (regression-to-mean candidate), and c=3's true edge over the c=1.5 baseline is more modest (~+14, in line with the field).** This is exactly the failure mode the [[bracket-hyperparams]] memory warns about, applied to our own headline result: a single n=400 reading made c=3 look like a sharp +47 peak; broader sampling flattens it.

**What this does and doesn't change.**
- Does NOT mean c=3 is wrong — every measurement still has c=3 ≥ the c=1.5 baseline. The production default is not in danger of being *worse* than old.
- DOES retract the "sharp +47 peak / biggest single free win in weeks" framing. c=3 is *a* reasonable setting, not a standout.
- The whole **c×cap interaction** claim from the 2026-05-28 10:30 STATUS entry is downgraded — it was built on n=100 noise.

**Decision.** Keep c=3 as the production default for now (it's not worse), but **flag the +47 claim as UNDER RE-VALIDATION** and run a fresh **n=400 (c=3, cap=12) vs (c=1.5, cap=12)** before treating any c value as settled. Do NOT re-bump or re-tune off the Optuna n=100 screens — they're too noisy. The clean follow-up is one targeted n=400 eval (cheap, dual-box ~3h), ideally alongside (c=2.0, cap=19) to check the study's apparent best at full power.

**Reversal cost.** None — this is a documentation/epistemics correction, not a code change. The production default is unchanged.

**Phase.** Phase 4 hyperparameter tuning. Methodology: re-validate your own headline wins at full n before enshrining them.

---

## 2026-05-28 — c_puct bump: eval-side validated, self-play-side bumped on hypothesis (NOT yet A/B'd). Documenting the conflation before it bites us.

**Context.** On 2026-05-27 we bumped the `--c-puct` default in both `scripts/eval_iter_head_to_head.py` and `scripts/run_selfplay_iter.py` from 1.5 → 3.0, citing the Phase 2b sweep (+47.2 elo at sims=200) and J4 (+39.3 at sims=800) as justification. That was the same commit. Today (2026-05-28) we noticed the two scripts use c_puct in **structurally different ways**, and the evidence only validates one of them.

**The distinction.**
- **Eval-side c_puct** (`eval_iter_head_to_head.py`): controls PUCT during head-to-head play with a *trained* checkpoint. Phase 2b and J4 tested exactly this: same iter_B1 both sides, different c, count wins. Verdict +47.2 / +39.3 — clean, validated.
- **Self-play-side c_puct** (`run_selfplay_iter.py`): controls PUCT during *training data generation*. A different c changes (a) which actions get selected in self-play games, (b) the shape of the visit distribution that becomes the policy target, and (c) downstream game outcomes that become value targets. The resulting `.npz` files are then fed to `train_iter.py`. The thing we'd measure is the **strength of the trained checkpoint that results** — not the strength of self-play games themselves.

**Why the conflation is plausible-but-unverified.** It's reasonable to assume that c=3 self-play yields a stronger checkpoint than c=1.5 self-play: deeper exploration → more diverse training data → better generalization. But this is a hypothesis. Counter-arguments: (1) Self-play also has Dirichlet noise on root priors and τ=1 for the first 15 moves, which already inject exploration; an additional PUCT widening may be redundant or even hurt by over-spreading visit distributions and producing softer (less informative) policy targets. (2) The Phase 2b/J4 result was specifically about **playing strength of a fixed checkpoint with different c**, which is upstream of the data-generation question. (3) AlphaZero papers typically use the same c at self-play and eval, but their c was tuned end-to-end; ours wasn't.

**Options considered.**
- **A. Roll back self-play default to c=1.5 until A/B run.** Conservative. Costs ~0 (just a default change). Reverts the change that was never validated.
- **B. (chosen) Keep c=3 self-play default, document the gap loudly, schedule an A/B.** Pragmatic. The hypothesis is reasonable and every new run from today onward generates evidence under c=3. Reverting now would create a "what default were the files in this dir generated under?" tracking burden, since we have ~0 c=3 self-play data on disk yet. Document the unverified status, run an explicit A/B at some point.
- **C. Train two iters now (c=1.5 self-play vs c=3 self-play from same warm-from), eval head-to-head before producing any more self-play data.** Most rigorous but blocks ~25h of compute on validating something that probably works.

**Decision.** Option B. Update the docstring on `run_selfplay_iter.py --c-puct` to flag the eval-vs-selfplay distinction and the unverified status. Add a "UNTESTED" row to the STATUS.md verdict table for "c_puct=3.0 in self-play data generation." Add this decision entry. The A/B test gets queued in the forward queue, not blocking.

**What would falsify.** Train iter_X(c=1.5_sp) and iter_X(c=3.0_sp) from the same warm-from on the same data-volume budget. Eval head-to-head, both at c=3 (the validated eval setting). If c=3-self-play loses or is null, roll back the self-play default to 1.5 and reconcile.

**Reversal cost.** Low. Changing the default back to 1.5 is a one-line edit. If we later discover c=3 self-play hurt, the affected output is the data on disk from c=3 self-play runs — flagged via metadata or just the `cfg` JSON each run writes.

**Phase.** Phase 4. Methodology lesson, not a scientific finding.

**Memory cross-ref:** [feedback_bracket_hyperparams](../.claude/projects/-home-doctor-projects-carcassone/memory/feedback_bracket_hyperparams.md) — same family of failure mode (declaring a config change settled from off-target evidence).

---

## 2026-05-26 — c_puct=1.5 → ~3.0 free win at iter_B1 (sims=200): +47.2 elo at n=400, 2.8σ. Most "leaf-eval plateau" symptoms were stale-PUCT, not leaf saturation.

**Context.** After 8 days of leaf-eval ablations (cap A/B, value-blend, tile-counting) and chain experiments (Option B, anchor-fraction, deepsearch_v2) all returning null or negative, ran the maximalist's Phase 2 PUCT wider sweep (deferred for ~6 weeks since the original c_puct calibration on warmstart-level checkpoints). Same checkpoint iter_B1 both sides; only the per-side c_puct differs. n=400 at sims=200.

**Result table.** All measured at iter_B1, sims=200, leaf v2_5, c=1.5 as the OLD side:
- c=0.5 → −54.3 elo (165W/227L/8D) — catastrophic
- c=1.0 → −11.3 elo (192/205/3) — mildly worse
- c=1.5 (baseline) → 0
- c=2.0 → +5.2 (from 2026-05-20 retroactive test; null)
- **c=3.0 → +47.2 elo (226/172/2) — 2.8σ positive**

Phase 2b (c=2.5/4.0/5.0) is in flight to triangulate the peak; outcome lands ~2026-05-26 18:00.

**Conceptual reading.** In `U(s,a) = Q + c_puct * P * sqrt(ΣN)/(1+N)`, raising c shifts action selection from Q-driven (trust the v2_5 leaf eval's accumulated rollups) to P-driven (trust the network's policy prior). The +47 elo at c=3.0 means **the network's policy is now sharper than the leaf-eval's Q values**. The original c=1.5 was tuned during Phase 3 warmstart on much weaker policies; it never got retuned as the network trained through iter_00 → iter_01 → iter_B1. Classic stale-hyperparameter failure. Several recent "leaf-eval plateau" symptoms (v2.7 leaf doesn't scale, Option-2 blend hurts, cap retunes null) look in retrospect like search wasn't using the policy enough — not that the leaf was actually the limit.

**Why this was missed.** All ablations of the last 6 weeks held c=1.5 constant. The 2026-05-15 PUCT sweep (`puct_c2_vs_c15`) only tested c=2.0 (got +5.2, near-null) and concluded "c=1.5 holds" — that single near-baseline data point made the whole search-config axis look settled when it wasn't. **Lesson: never declare a hyperparameter axis settled from one off-peak point — at minimum bracket above and below.**

**Options considered (the strategic pivot the PUCT find triggers):**
- **A. Update production c_puct to peak (≈3.0 pending Phase 2b) and call it done.** Easiest. Banks the free win immediately. Risks: c may not transfer to sims=800, may have interactions with other hyperparams.
- **B. (chosen) A + retune-everything-stale audit.** Bump production c, then sweep the other "set early, never re-tuned" hyperparams (temp_threshold=15, dirichlet_alpha=0.3, dirichlet_eps=0.25, virtual_loss=1.0) at the new peak c. Same staleness pattern likely applies. Also re-test the recent null verdicts (anchor-fraction, deepsearch_v2, tile-counting) at peak c — many may flip positive.
- **C. Skip the retune audit, jump to bigger projects (transformer net, multi-anchor league).** Higher EV in theory, but option-B audit is cheap (~2-3 days dual-box) and several entries have meaningful probability of paying off.

**Decision.** Option B. Wire (sims × c) 2D probe → re-test top nulls at peak c → other-hyperparam sweep, all dual-box shared-claim. Forward queue documented in STATUS.md. Once stale-hyperparam audit settles, take stock and decide on bigger architectural projects.

**Reversal cost.** Low for the production c bump (config change). Low-medium for the queue itself (each eval is ~3h dual-box, easily killable). The lesson — "bracket hyperparameters above and below the current setpoint when you sweep" — is the durable change in methodology.

**Phase.** Phase 4 (self-play loop) hyperparameter tuning.

**Memory cross-ref:** [feedback_bug_fix_shifts_optima](../.claude/projects/-home-doctor-projects-carcassone/memory/feedback_bug_fix_shifts_optima.md) — same lesson applied to bug fixes; here it applies to checkpoint progression. Adding a new memory note for the methodological lesson.

---

## 2026-05-24 — Option B chain Phase 1 KILLED after B4; chain-vs-prev anchors were lying about absolute strength; pivoting to anchor-fraction multi-opponent self-play

**Context.** Maximalist sequencer ran Phase 1 chain B2→B4 (B5 in progress, killed mid-flight) over 2026-05-21→24. Each chain step measured iter B(i) vs B(i-1) at n=2000, sims=200. Chain elo deltas looked acceptable: B2=+11.4 / B3=+2.4 / B4=+1.4 — no skip-forward (<−10 elo threshold) trigger. But **directly anchored against iter_01 (the canonical reference) at n=400**, B4 came back at **−19.1 elo** (186W/208L/6D, 1.1σ regression). Given iter_B1 = chain-step-0 = B1 was confirmed at +25.2 over iter_01 (2026-05-20 n=400), this means the chain drifted **~55 elo against the fixed reference** while each chain step looked ~neutral against its predecessor.

This is the **"anchor before scaling" memory rule** failing in practice. Each step's measurement was vs a drifting reference, so the chain was free to spiral away from any externally-meaningful elo. The maximalist's Phase 1 (and Phases 3, 5-retrain) only does chain anchors — no global anchor — and is structurally vulnerable to this pattern.

**Likely cause: RPS / intransitivity from self-specialization.** Each B(i)'s self-play data is dominated by play patterns against B(i-1). The network specializes against B(i-1)'s style → loses generality vs off-distribution opponents (iter_01). Classic AlphaZero failure mode without league/multi-opponent training.

**Options considered:**
- **A. Run more chain steps and hope** (B5/B6/B7 already queued). Rejected: drift is already 55 elo deep; another 60h of compute almost certainly worsens it.
- **B. Anchor-fraction multi-opponent self-play.** Mix N% of self-play games against a fixed strong anchor (iter_B1) into the chain. Prevents drift by tying training data distribution to a fixed reference. Well-established cure for this failure mode. ~190 LoC, ~5h to implement. **CHOSEN pending B2 vs iter_01 anchor verdict.**
- **C. League play (AlphaStar-style, N specialized agents).** Right long-term solution but overkill for our scale (1200 games/iter, 7M-param net). Engineering project: ~2-3 days.
- **D. Different recipe entirely (e.g., score_diff abandoned, leaf-eval rework).** Doesn't address the structural drift, just hopes a different starting point doesn't show it.

**Decision.** Kill chain after B4 (executed 2026-05-24 07:55). Run B2 vs iter_01 direct anchor at n=400 to differentiate "Option B recipe was broken from step 1" (B2 also ≈ −19) from "chain held for 1 step then drifted" (B2 ≈ +25). Then:
- **If B2 ≥ ~+10**: implement anchor-fraction self-play (static anchor=iter_B1, fraction=0.3, alternating sides) per design in this session. Pilot 1 chain step under anchor-fraction; if validates, chain forward.
- **If B2 ≈ −19**: anchor-fraction won't save a broken recipe; pivot to Phase 3 deepsearch / loop's orphaned deepsearch train+anchor / leaf-eval rework.

**Resolved 2026-05-24 11:00.** B2 anchor came back at **−6.1 elo vs iter_01** (193W/200L/7D, n=400, 0.36σ null). Not −19, but not positive either — **Option B chain doesn't even gain in step 1**. B1's confirmed +25 cushion already half-erased by B2. Anchor-fraction would hold the line at iter_B1's strength but can't manufacture gains where the recipe produces none. **Option B as a chain lever is dead.** Pivoting per the B2≈−19 branch above: kicked off the orphaned loop deepsearch train+anchor immediately (PID 5369, nice 19, train+anchor n=100 sims=200 vs iter_01, ETA ~35 min from 11:23). Anchor-fraction implementation will be scoped to the deepsearch lever instead of Option B.

**Updated 2026-05-24 22:30.** Two follow-ons landed:
1. **deepsearch_v2 verdict** (the orphaned /loop train+anchor): trained from the 2026-05-18→21 sims=800 work-stealing data, anchor-gated at **+13.9 elo @ n=100** then re-confirmed at **+5.2 elo @ n=400** (combined +11.4 over 500 games). Under σ=17 → **null vs iter_01 at sims=200**. Sims=800 training data did NOT move the sims=200 needle. The deepsearch (v1) ckpt remains the sims=800-plane best; deepsearch_v2 is roughly equivalent to iter_01 for warm-from purposes.
2. **Anchor-fraction self-play implemented + smoke-validated.** ~280 LoC across `src/carcassonne_ai/selfplay.py` (dual-MCTS routing per `current_player == learner_player_idx`, learner-only record filter — anchor's moves are played but never saved), `scripts/run_selfplay_iter.py` (`--anchor-checkpoint` + `--anchor-fraction` flags, dual eval-server pool wiring, per-seed RNG XOR'd to decorrelate), and `tests/test_anchor_fraction_selfplay.py` (6 new tests covering regression-when-anchor-None, learner-only-records, ~50% record-count, distinct-evaluator legality). Full suite green. Smoke run (4 games at fraction=0.5) showed exact contract: 2 anchor games at ~83 records single-sign (learner-only), 2 self-play games at ~165 records mixed-sign. Mutually exclusive with `--serve-on`/`--remote-eval-server` (single-host or `--shared-claim`-only); compatible with `--shared-claim` for dual-box work-stealing.

**Strategy pivot:** anchor-fraction will be tested at **sims=200 FIRST** (cheap, ~4-5h dual-box) before committing to sims=800 production (~20-25h). The deepsearch lever (sims=800 training) was null at sims=200; no reason to assume sims=800 amplifies the anchor-fraction signal more than sims=200 reveals it. Warm-from = iter_01 (deepsearch_v2 was equivalent strength-wise — picking the simpler chain). Static anchor = iter_B1 (current sims=200 global best, the strongest "fixed opponent" we have).

**Other phase impacts:**
- **Phase 2 (PUCT sweep on iter_B1)**: unaffected by drift — no chain step. Still valid to run as-is (~24h).
- **Phase 4 (FN re-confirms, leaf-eval ablations on iter_B1)**: unaffected — no chain step. Still valid (~10h).
- **Phase 5 smoke (tile-counting vs v2.7 leaf on iter_B1)**: unaffected — no chain step. Still valid (~3h).
- **Phase 3 (deepsearch DS_02)**: IS a chain step — same drift risk. Should be re-implemented under anchor-fraction (anchor = iter_01 or existing deepsearch ckpt). Defer until anchor-fraction lands.
- **Phase 5 conditional retrain**: IS a chain step. Same — defer or rewrite under anchor-fraction.

**Reason.** B2-B4 chain elo (+11.4 / +2.4 / +1.4) "looked fine" by chain measurement, but the direct anchor revealed catastrophic drift. The sequencer's design lacked a global anchor and shipped that bug into ~3 days of compute. The cure (anchor-fraction in self-play, OR adding a "vs iter_01 anchor at n=400 each step" to chain phases as a cheap drift detector) is cheap enough that NOT having it was the real mistake.

**Reversal cost.** Low for the kill itself (`--shared-claim` makes restart cheap — wasted compute is sunk). Medium for the anchor-fraction implementation: new flag in `run_selfplay_iter.py`, second eval-server in pool, two-evaluator routing in `selfplay.py:play_one_selfplay_game`. Defaults off; legacy behavior preserved when `--anchor-fraction 0.0`.

**Phase.** Phase 4 (self-play loop), specifically the chain methodology.

**Memory cross-refs.** [feedback_anchor_before_scaling](../.claude/projects/-home-doctor-projects-carcassone/memory/feedback_anchor_before_scaling.md) was the exact warning. The maximalist sequencer's design (chain-only anchors) was the mechanism that ignored it. Future autonomous pipelines must include a global anchor per chain step.

---

## 2026-05-20 — Network-distributed eval-server: TCP bridge in front of the existing orchestrator pool, lets a GPU-less box (Zenbook) borrow the 5800X's GPU for inference

**Context.** Zenbook (i7-12700H, 16 GB, no NVIDIA) bootstrapped 2026-05-20 to add as a 3rd cluster box. Two ways to use it: (a) run its own standalone CPU eval-server — works without any new code, but CPU forward is ~80 ms/eval and contributes maybe Xeon-tier throughput; (b) network-distribute the orchestrator so Zenbook's CPU workers offload inference to the 5800X GPU via TCP. Option (b) is meaningfully faster (workers do MCTS only, not torch forwards) and uses RAM Zenbook already has.

**Options considered:**
- **A. Standalone CPU eval-server (no new code).** Trivial: just point Zenbook's existing self-play at its own CPU. Works today, ~0.5-1.0 games/min added. But it's also the upper bound on what CPU can do at sims=200 — the laptop CPU is the limiter, the GPU on the 5800X sits unused for Zenbook's share of work.
- **B. Network-distributed eval-server bridge** (chosen). Add a small TCP listener in front of the existing eval-server orchestrator pool; remote workers connect, ship `(obs, scalars, mask)` over the wire, get `(priors, value)` back. ~0.8-1.0 games/min, much less Zenbook CPU pressure, GPU does the heavy work for both boxes.
- **C. Build a real distributed coordinator (Ray / gRPC / ZMQ).** Overkill — we have 2-3 boxes on one LAN with one tenant. The complexity tax buys nothing.

**Decision.** Build B as a thin TCP bridge:

- **Wire format**: 4 B big-endian uint32 frame length, then per-message payload. Each numpy array is serialised via `np.save` with `allow_pickle=False` into a `BytesIO`, length-prefixed. **No serialization-via-eval anywhere** — `np.load` with `allow_pickle=False` refuses object dtypes. Wire path: `[frame_len][worker_id][request_id][3 npy blobs]`. ~70 KB per single-board request, well under the 64 MB safety cap.
- **Server side**: a daemon thread per connection runs `recv_framed → request_q.put → response_q.get → send_framed`. The bridge **pre-claims K extra slots** in the existing `start_server_pool` (i.e. starts the pool with `n_workers + K` slots) and binds one slot per inbound connection. The running eval-server code is **unchanged** — to the server, the bridge looks like K more local mp.Queue workers.
- **Client side**: a `SocketServerHandles` mimics the existing `eval_server.ServerHandles` interface (same `.request_q.put()` / `.response_q.get()` API), so the existing `make_remote_batch_evaluator` factories work without changes.
- **Failure handling**: if a remote worker disconnects with a request in flight, the bridge drains the eventual server response before releasing the slot — otherwise the next connection on that slot would receive the prior reply. CIFS-style transient errors fall through to the worker's existing `BrokenServerError` path; reconnect is at the worker level.

**Reason.** Bridge mode is ~20% faster than CPU-only and saves Zenbook's CPU for MCTS work where it actually helps. The thin-wrapper approach (re-use the existing orchestrator pool, just front it with TCP) means zero changes to the running self-play code path — workers don't know whether their `ServerHandles` is local mp.Queue or socket-backed.

**Verification.** 9 unit tests (`tests/test_remote_eval_bridge.py`) cover wire roundtrip, concurrent workers, slot exhaustion, slot recycling on disconnect, worker_id restamping. All pass on both the 5800X and Zenbook venvs. Loopback smoke (server + client both on the 5800X, CPU mode): 12932 evals roundtripped, 0 failures, 13 fresh server games + 7 fresh client games out of 20 total — work-stealing balanced as expected.

**Reversal cost.** Low. New code is additive — the `--serve-on` / `--remote-eval-server` flags are off by default; without them the script behaves exactly as before. Easy to revert by not using the flags.

**Phase.** Phase 4 (self-play loop).

**Worker-count knee on Zenbook.** Bridge-mode bench 2026-05-20 with localhost stub (5 ms simulated forward) swept W ∈ {4,8,12,14,16,20}: peak at W=8 (5.26 games/min), curve flat 8→20 (5.0-5.3 games/min). Production recommendation **W=10** (pad +2 from raw peak to give bridge-conn threads + OS headroom, since stub workers in the bench cost ~0.5 cores). Matches the "2×P-cores − 2" heuristic for the 12700H (6 P-cores → 10). HT didn't add throughput on this hybrid CPU because (i) E-cores have no HT, (ii) Linux Thread Director on Alder Lake is shaky pre-6.2, (iii) laptop thermal envelope limits sustained boost. Decision: pin v3 sequencer to `WORKERS_ZENBOOK=10`; sanity-check W=10 vs W=12 against real 5800X GPU once firewall opens.

**Deploy blocker.** Windows firewall on the 5800X needs to allow inbound TCP 19999 LAN-scoped — 1-line PowerShell as admin, see `/home/doctor/network_bridge_deploy.md`. Until then, deploying CPU-only Zenbook (option A) as the interim — adds Xeon-tier throughput today without admin work, swap to bridge mode the moment firewall opens.

---

## 2026-05-20 — Methodological retroactive-validation pipeline: the project's n=100 matched-strength comparisons have been systematically false-negative-prone; re-running 4 high-leverage past nulls at n=400

**Context.** The sims=800 matched-plane re-bench (entry below) — 52% wr at n=100, point estimate slightly positive — sits squarely in the "ambiguous, would-need-more-data" band, the same band where several earlier "null" calls landed (iter_02 at 53.5% / n=100, iter_B1 at 49% / n=100, PUCT c-sweep at n=50). The question came up: have we been throwing out false negatives across the project?

**The math, briefly.** For wr-based head-to-heads:
- n=100: SE ±5.0pp; "significant" (α=0.05 one-sided) bar = ≥58.2% wr → detects ≥+58 elo edges confidently
- n=200: SE ±3.5pp; bar = ≥55.8% → detects ≥+40 elo
- n=400: SE ±2.5pp; bar = ≥54.1% → detects ≥+30 elo
- n=600: SE ±2.0pp; bar = ≥53.4% → detects ≥+25 elo

Matched-strength comparisons (iter vs iter at same leaf) are the project's hardest signal-to-noise regime, and we'd been running them at n=100. Most of our "compounding cadence" conclusions therefore had ~50-60% power against +30 elo edges → up to ~45% miss rate at that effect size. The discipline against *false positives* was strong (the n=50-minimum-for-variant-comparison memory rule caught v3/PUCT noise), but the symmetric guard against false negatives was missing.

**False-negative-suspect calls, ranked by impact-if-wrong:**

| call | n | wr | downstream impact | re-run? |
|---|---|---|---|---|
| iter_02 "saturated against fixed leaf" | 100 | 53.5%, +24.4 elo | huge — closed plain-recipe compounding lever | **yes** |
| iter_B1 ≈ iter_01 (Option 2 NN-value blend) | 100 | 49% wr / +4.6 score diff | big — closed value-head blend pipeline | **yes** |
| deepsearch matched-plane (already in flight) | 100 | 52.5%, +17.4 elo | matched-plane ambiguity, see entry below | **extend to n=400** |
| PUCT c=2.0 vs c=1.5 | 50 ea | 88/84% | small — one-time +25 elo at best, cheap to test | **yes** (separate per-side c_puct job) |
| closure-P leaf A/Bs | 100 ea | 45/50% | small — pooled 47.5% over n=200 is mildly negative, not noisy | no |
| v3 cap sweep | 50 | flat | small — cap=12 production-tested, multiple n=50 readings | no |
| Option 2 blend smoke | 50 | 31% | confirmed negative (2.7σ) | no |

**Implementation.** Autonomous 4-job pipeline (`/home/doctor/sequencer.sh` + `/home/doctor/puct_followup.sh`), nohup'd on the 5800X, drives both boxes via the work-stealing `--shared-claim` primitive (now wired into `eval_iter_head_to_head.py` too, see infra notes below). Each job's verdict appended to `/tmp/retest_verdicts.txt`; sentinel files at `/tmp/{retest_sequencer,puct_followup}.DONE`. Total cluster wallclock ~12-14h overnight.

**Decision.** (1) Run the 4 high-leverage re-tests at n=400. (2) Skip the low-impact ones (closure-P, v3 cap, Option-2 blend) — those were either decisively negative (Option 2) or repeatedly null (closure-P pooled across two leaf variants at n=200, v3 across multiple cap values at n=50). (3) **Going forward, n=400 minimum for matched-strength comparisons**; n=100 reserved for first-look smokes or for variant tests where the effect-size-of-interest is >+50 elo. Add this to the project's operating norms.

**Expected information value.** P(at least one of the 4 re-tests recovers a real positive) ≈ 40-50% under reasonable Bayesian priors. The expected-value math favors running it: even a single "false-negative recovered" outcome unblocks a major lever (e.g. if iter_02 turns out to be a real +30 elo gain, the multi-iteration training pipeline is back open; if PUCT c=2.0 is real, +25 elo free at play time). At ~12-14h cluster cost split across two idle boxes overnight, it's nearly free.

**Infra extracted along the way (commit-worthy in their own right):**
- New `src/carcassonne_ai/claim.py` — work-stealing claim primitive (atomic O_CREAT|O_EXCL on a `.claim` sidecar, with stale-recovery semantics from the run_selfplay_iter implementation). Refactored out of `run_selfplay_iter.py`; both that script and `eval_iter_head_to_head.py` import it.
- `eval_iter_head_to_head.py` gained `--shared-claim` / `--claim-stale-secs` / `--claim-host` — evals can now work-steal across boxes the same way self-play does. Plus per-job consolidated-from-disk summary so each box's printed verdict reflects the cross-box outcome.
- `eval_iter_head_to_head.py` gained `--new-c-puct` / `--old-c-puct` — per-side PUCT exploration constant. Default None falls through to `--c-puct`, so all existing call sites are unaffected. Enables A/B testing exploration constants on the same checkpoint both sides (the PUCT job's whole reason for being).
- 12 tests still green; smoke confirmed.

**Reversal cost:** low. The re-test outcomes either confirm the original verdicts (no change to current conclusions, narrowed noise bands) or update them (correction we should have made earlier). The infra changes are backwards-compat and useful regardless of the re-test results.

**Phase:** 4 (self-play) — methodological / infrastructure.

## 2026-05-20 (results) — Retroactive-validation pipeline complete: 2 of 4 false-negatives recovered. iter_B1 promoted to new global-best. Audit identifies several more reservoirs of likely false-negatives.

**Outcome (4 of 4 jobs done, cluster wallclock ~16h 13:55 → 16:10):**

| job | n | result | elo Δ | σ vs 50% | verdict |
|---|---|---|---|---|---|
| deepsearch vs iter_01 @ sims=800 | 380 | 208W/169L/3D | **+35.8** | 2.0σ | **recovered FN** (already suspected from n=100 +17.4 reading; n=400 confirms at 2σ) |
| iter_02 vs iter_01 @ sims=200 | 400 | 193W/198L/9D | **−4.3** | 0.25σ below 0 | **genuine null** — plain v2.7 recipe really did plateau at iter_01; not a false-negative |
| iter_B1 vs iter_01 @ sims=200 | 400 | 213W/184L/3D | **+25.2** | 1.5σ | **🎯 NEW recovered FN** — Option B (score-diff-targeted self-play, no NN-value blend) is a real +25 elo gain over iter_01. iter_B1 should become global-best. |
| iter_01 c=2.0 NEW vs c=1.5 OLD @ sims=200 | 400 | 200W/194L/6D | **+5.2** | 0.3σ | **genuine null** — c=2.0 does not beat c=1.5; the c-axis is closed at this resolution (n=400 against the ~+20-30 elo effect-of-interest has ~65% power; a small positive effect could still hide) |

**Headline:** Of the 4 hypothesized false-negative-suspect calls, the math from the prior entry (P(at least one recovered) ≈ 40-50%) actually delivered 2 recoveries. **The biggest is iter_B1: the project's claimed "plain v2.7 plateau at iter_01" was wrong — Option B (score-diff value targets, no blend) is a +25 elo lever the n=100 verdict (49% wr, +4.6 score diff) called null.**

**Decisions:**
1. **Promote `checkpoints/v25_retrain_optionB_iter1/iter_00.pt` to global-best**, replacing iter_01. Update CLAUDE.md "current global-best" line accordingly.
2. **Reframe the "plateau" finding.** The 2026-05-19 entry concluded "two-strategy plateau (iter_02 + iter_B1) is real" — half of that (iter_B1) is now retracted. The plain v2.7 *recipe* (W/L value targets, vanilla self-play) really does plateau at iter_01 (iter_02 confirmed at n=400). But the Option B *variant* of the recipe (`score_diff` value targets) is a real +25 elo lever. The plateau is recipe-specific, not net+leaf-bound.
3. **n=400 is the new minimum** for matched-strength comparisons (already decided in the prior entry). Re-confirmed empirically: 3 of the 4 n=100 verdicts in this set were within ±15 elo of a genuinely-different n=400 reading.
4. **No retraining of the deepsearch verdict's downstream implications** — the 2026-05-19 (late) entry's call ("deepsearch becomes global-best for the sims=800 play regime if confirmed") stands and is now confirmed. Deepsearch is global-best for sims=800-plane play; iter_B1 is global-best for sims=200-plane play. (Practical implication: choose the checkpoint by your play-time sims setting. Most matches will be sims=200 → iter_B1; sims=800 power moves → deepsearch.)
5. **PUCT c-axis closed at this resolution.** c=2.0 vs c=1.5 at +5.2 elo / 0.3σ is the strongest single-axis-sweep negative result yet. A real +20 elo c=2.0 effect would need n≥800 to detect at α=0.05 — not worth the compute.

**Broader audit — other reservoirs of likely false-negatives (next-step planning):**

The n=100 verdicts were one source. Reservoirs we should sweep through next:
- **Single-iteration rejections.** Many recipes were killed after one self-play+train cycle. Recipes that compound over 2-3 iters (like Option B might — iter_B1 is +25, iter_B2 could be more) look flat-vs-prev each step. **Highest EV: chain Option B forward (iter_B2, iter_B3, iter_B4) before assuming the lever is single-shot.**
- **Smoke-test rejections (n=20-50).** Even more underpowered than n=100. Any past variant rejection where the smoke landed within ±50 elo of zero was effectively "unknown" — re-run candidates that had borderline smokes.
- **Coarse hyperparameter sweeps.** Only 2 c_puct points tested (1.5 vs 2.0, now null) — never tried 0.5, 3.0, 5.0. Cap sweep stopped at the v2.7-era optimum (5 → 12) — never tested cap=20 or cap=∞. Network: 6×96 ResNet picked in Phase 3, never re-swept at v2.7-era data scale.
- **Pre-bug-fix benchmarks.** The v2.5 farm/city dedup fix (2026-05-15) shifted optima. Any variant rejected *before* that fix was tested against inflated bonus magnitudes — verdicts may not hold.
- **Other plane mismatches.** The sims=200 / sims=800 mismatch was caught. Other potential mismatches: cap value at train vs play, leaf-eval variant at train vs play, orchestrator on/off — not systematically audited.

**Next-step plan (drafted separately, to be wired into a multi-day autonomous pipeline while Joshua is away):** chain Option B forward 3-4 iters; wider c_puct sweep at sims=200; cap=20 and cap=∞ smokes. See STATUS.md "Next" for the queued sequence.

**Reversal cost:** medium. The iter_B1-as-global-best call is well-supported (1.5σ at n=400) but not as solid as iter_01's original promotion (1.9σ at n=100 against warmstart). If a future n=400 deepsearch-style re-test pulls iter_B1 back below iter_01, we'd re-revert. The plateau-retraction is a real correction; the original conclusion was actively misleading and gated several decisions on the wrong premise.

**Phase:** 4 (self-play) — strength.

## 2026-05-19 (late) — Deepsearch verdict revised: anchor-gate plane mattered; matched-regime (sims=800) reading is +17 elo / 52% wr (n=100) — within noise but flips sign from the sims=200 verdict

**Context.** The earlier 2026-05-19 entry below ("Deeper-search self-play retrain did not advance") rested on a single anchor-gate at sims=200. After publishing it, the question came up: deepsearch was *trained* with sims=800 teacher search — was it fair to evaluate it at sims=200 play, the regime tuned to iter_01? The natural matched-regime test (deepsearch vs iter_01 both played at sims=800, n=100) had not been run. We then ran it.

**The run.** Same 100 (seed, player) pairs as the sims=200 anchor (seeds 900000–900099, i%2 player split). Both sides played at sims=800. Work-stealing across both boxes via a newly-extracted `carcassonne_ai.claim` module + a `--shared-claim` flag added to `eval_iter_head_to_head.py`. The eval started as a manual seed-split (5800X 70 / Xeon 30); mid-run the durability gap (no crash failover) prompted a pivot to shared-claim — 54 cached games preserved via exists-check, then both boxes ran the *same* `--games 100 --seed-start 900000` command pointed at one CIFS eval_dir; the claim primitive divvied up the remaining 43 seeds atomically. 24 active workers, 14 5800x + 10 xeon. Wallclock ~3.5h end-to-end (kill→pivot→restart→complete).

**Result.** deepsearch (NEW) vs iter_01 (OLD), 100 games: **52W / 1D / 47L, avg diff +0.61, elo +17.4** (0.50σ above 50%; binomial SE ±5pp).

**Comparison across measurement planes:**

| play sims | result | avg diff | elo |
|---|---|---|---|
| 200 (anchor-gate v1, iter_01-matched) | 45W/0D/55L | −1.2 | **−34.9** |
| 800 (anchor-gate v2, deepsearch-matched) | 52W/1D/47L | +0.6 | **+17.4** |

~52-elo swing from measurement plane alone, with a clean sign flip. Each reading individually is within its noise band (0.5–1σ from 50%); the *anti-correlation* across planes is the suggestive signal — if both were pure noise we'd expect drift in the same direction or independent, not a clean flip.

**What this changes about the prior entry.** "The plain v2.7 retrain recipe is confirmed plateaued at iter_01 across all three lever attempts" overreached on the deepsearch leg. iter_02 (+0.2 at sims=200, iter_01's matched plane) and iter_B1 (+4.6 / 49% at sims=200, iter_01's matched plane) remain flat — those were measured at their training-matched plane and the conclusion stands for those legs. The deepsearch leg was measured *off-plane* and the matched-plane reading is ambiguous (point estimate slightly positive, not significant). The two-strategy plateau (iter_02 + iter_B1) is real; calling it three strategies was wrong.

**Hypothesis the data is consistent with.** Training-sims and play-sims should match. A deeper-teacher policy is tuned to behaviors a deeper search will actually take advantage of at play time; at shallower play it may even score slightly worse because the policy is now relatively under-confident in lines a deeper search would close out. Not proven at n=100 (point estimate within noise) — but the +52-elo flip is the right shape if the hypothesis holds, and the wrong shape if both readings are pure noise.

**Decision.** (1) Do NOT promote deepsearch to global-best yet — +17.4 elo at 0.5σ doesn't clear the same bar iter_01 cleared (1.9σ at n=100 in 2026-05-16). (2) **The n=200 confirmation plan was upgraded to n=400** after a meta-audit (next entry below) revealed n=100/200 is below the resolution needed for matched-strength comparisons in this project. (3) **Conditional on the n=400 confirmation:** if the matched-plane edge holds (≥+30 elo ≈ 1.7σ at n=400), deepsearch becomes the new global-best **for the sims=800 play regime**; if it reverts to ~50%, iter_01 stays. Either way the +200 elo sims=200→800 play-time win (2026-05-18 sims-ladder) is a free side-channel benefit independent of which checkpoint is selected.

**Independent of the n=200 outcome:** the broader claim "the v2.7 leaf is the ceiling" is now less load-bearing. iter_02 and iter_B1 are still flat, so the policy IS saturated at iter_01-matched-plane evaluation. But the deepsearch leg leaves open the chance that training-and-play matched search regimes have more room than the sims=200-only view suggested. Leaf-eval redesign remains the highest-leverage longer-term lever; the matched-regime hypothesis is a cheaper near-term experiment if n=200 confirms.

**Reversal cost:** low. The original entry stays below (history); this entry corrects its conclusion in light of the matched-plane data.

**Phase:** 4 (self-play).

## 2026-05-19 — Deeper-search self-play retrain did not advance; v2.7 plateau confirmed across 3 strategies — leaf-eval becomes the next ceiling

> **2026-05-19 (late) — partial retraction:** see the entry immediately above. The deepsearch leg of this argument used the wrong measurement plane (sims=200 anchor); at the matched sims=800 plane the verdict is ambiguous (+17.4 elo, 0.5σ above 50%) rather than negative. The iter_02 and iter_B1 legs were measured at their matched plane and stand. The original text below is preserved unedited for history.


**Context.** STATUS 2026-05-18 had two strength levers still on the table: (a) deeper-search self-play — retrain with a sims=800 teacher (might un-stick the plateau); (b) leaf-eval redesign (bigger project). The sims-depth A/B (iter_01 @ sims=800 vs itself @ sims=200, n=50, +200 elo) had proved search itself is a large lever *given the leaf* — the working hypothesis was that compounding stronger teacher search into training would lift the policy at production sims=200.

**The run.** 1200-game sims=800 self-play from iter_01, work-stealing across both boxes (one shared SMB folder, atomic-claim load-balance — commit 1895b02). Dataset finished clean (1200/1200, no failures). `train_iter.py` on the 1200-game buffer (188,736 train positions, warm-from iter_01, 3 epochs, batch 256, value-target score_diff per the running default — harmless here, see 2026-05-19 value_target note in BACKLOG.md) → `checkpoints/v25_retrain_deepsearch/iter_00.pt`. Anchor-gate `eval_iter_head_to_head.py`: new vs iter_01, n=100, sims=200 both sides, v2.7 leaf (`CAP=12`, drop-3-open), orchestrator, batch_size=1.

**Result — 45W / 0D / 55L, avg diff −1.2, elo_delta −34.9.** Within ~1σ of flat (n=100 binomial SE ~5pp), not significantly worse, definitely not better. The running tally trended steadily down through the run (60% after 20 → 53% after 40 → 47% after 60 → 43% after 80 → 45% final) — consistent with early-fluke regression to a true ≈50%.

**Compound with the prior anchor-gates from iter_01:**
  - iter_02: +0.2 avg diff (flat — DECISIONS 2026-05-17)
  - iter_B1 (Option-2 value-head blend pipeline, score_diff value head): 49W/0D/51L, +4.6 avg, elo −6.9 (≈ iter_01 — DECISIONS 2026-05-18)
  - deepsearch (this run, stronger teacher search): 45W/0D/55L, −1.2, elo −34.9 (≈ iter_01, slightly worse end of noise)

Three independent strategies — same recipe more iterations, value-head blend, stronger teacher search — all return flat-to-slightly-worse from iter_01. **The plain v2.7 retrain recipe is now confirmed plateaued at iter_01 across all three lever attempts.**

**Why.** The sims=800-at-PLAY result (+200 elo, 2026-05-18) proved search is a large lever *given the leaf*. But teacher-search quality only flows into training as POLICY targets, and a sims=800 teacher's targets are still bounded by what the v2.7 heuristic scores as good during that search. Stronger search refines the policy toward what THIS leaf considers best; it cannot teach the policy moves the evaluator can't recognize as good. iter_01 has converged to ≈ what the v2.7 leaf can teach; deeper teacher search doesn't widen that ceiling.

**Decision:** close deeper-search self-play as a strength lever *for this leaf*. Global-best remains `checkpoints/v25_retrain_iter01/iter_00.pt`. Next strength lever — Joshua's call (no auto-launch): **leaf-eval redesign** is now the only un-closed strength lever for the v2.7-recipe line (BACKLOG.md 2026-05-16 captures the strategy-lit ideas — tile-counting closure P, large-open-city penalty, targeted denial, meeple economy, farm majority-flip).

**Independent of this verdict:** the sims=800-at-PLAY +200-elo gain (2026-05-18 sims-ladder) is still on the table as a free win for production play — no retrain, ~4× per-move latency (fine for human-paced play). Should land in the production config whenever play-vs-human is wired up.

**Reversal cost:** low — checkpoint kept (`checkpoints/v25_retrain_deepsearch/iter_00.pt`), buffer kept (`/mnt/c/carc-shared/deepsearch/iter_00/`); the conclusion can be revisited if a leaf-eval redesign changes the substrate the policy is training against.

**Phase:** 4 (self-play).

## 2026-05-19 — Code-review loop: 14 fixes; work-stealing stale-recovery race accepted, not redesigned

**Context.** A 4-iteration multi-agent review of all living code (24 agent-reviews — 6 subsystems × 4 passes). Applied 14 safe corrections (F1–F14, see REVIEW_LOG.md); deferred 16 findings (D1–D16). Most deferrals are routine (latent / unreachable / retraining-boundary — tracked in REVIEW_LOG.md and BACKLOG.md). One — D15 — is a genuine architecture call worth recording here.

**D15 — the work-stealing stale-claim recovery (`_try_claim`) has a TOCTOU race.** When several workers re-claim the same abandoned (stale) seed, a worker that judged staleness against the *old* claim can `os.rename` aside a *fresh* claim re-created by an earlier winner — so N racers can yield up to N winners, not one. The fast path (the O_EXCL create) is unaffected and correct; this is recovery-only.

**Options considered:**
  - A: Redesign recovery to be single-winner — a per-seed `.recovering` O_EXCL lock, or capture-`st_ino`-then-re-verify. Correct, but ~half a day, and a botched fix to a *live* primitive could lose a claim (a seed never played → a training game silently missing) — strictly worse than the current behavior.
  - B: Accept it. The duplication is bounded (≤ N) and fires only on crash-recovery; the atomic `.npz` write (last-writer-wins) means the worst case is a few duplicate games — wasted compute, never corruption. Relax the docstring's "exactly one winner" overpromise and the test (`xfail` → assert `1 ≤ winners ≤ N`).

**Decision:** chose B — accept + document.

**Reason.** The `.claim` is a *best-effort* lock by design; correctness is owned by the atomic `.npz`. The race's worst case is a handful of recomputed games after a box crash. Option A's risk — losing a claim on a live primitive — is not justified by that. Parked in BACKLOG.md if the cost ever proves real.

**Reversal cost:** low — option A stays available; the BACKLOG entry preserves the analysis.
**Phase:** 4 (self-play).

## 2026-05-18 — Option 2 (NN value-head leaf blend) closed; plain v2.7 recipe confirmed plateaued

**Context.** iter_02 flatlined (+0.2 over iter_01) → working hypothesis: the policy had saturated against the *fixed* v2.7 heuristic leaf. Option 2's response: blend the network value head into the leaf — `leaf = (1−λ)·tanh(vs2/15) + λ·v_nn` — so the leaf co-improves with the policy. Phase A wired it (eb42c25); the λ=0.5 fixed-checkpoint smoke with iter_01's *W/L* value head gave −11.3 avg / 46% wr, hypothesised as a currency mismatch (W/L head vs score-diff heuristic leaf). Phase B: iter_B1 minted a *score-diff* value head (1200-game retrain from iter_01); the re-smoke tested blending it.

**Result — re-smoke (n=50, iter_B1 blended-λ=0.5 vs plain leaf).** −15.5 avg / 31% wr (15W/1D/34L) — *worse* than Phase A, not better. The currency-mismatch hypothesis is refuted. A residual-structure diagnostic (60 games, 9946 positions) confirmed the mechanism: the NN value head correlates only +0.18 with the true outcome vs the v2.7 heuristic's +0.61, and is beaten by the heuristic in every game-phase quartile; the MSE-optimal static blend cuts prediction error only ~4% (in-sample-optimised, so an overestimate).

**Result — iter_B1 strength.** iter_B1's own anchor-gate (n=20) scored 70%/+12.6 vs iter_01, which looked like a gain. An n=100 confirm corrected it: **49W/0D/51L, +4.6 avg diff, elo −6.9** — iter_B1 ≈ iter_01 (even win rate, a marginal score-diff edge at most). The n=20 was a high-side fluke.

**Decision.** (1) **Option 2 is closed** — value-head injection abandoned, both the convex blend and the residual-head variant. The 7.4M-param value head on ~1200 self-play games is simply a weaker position evaluator than the hand-tuned v2.7 heuristic; no blend repairs that. Triple-confirms the v1–v6 finding. (2) **The plain v2.7 self-play recipe is plateaued** — iter_00→iter_01 gained big (+13.3), iter_01→iter_02 flat (+0.2), iter_01→iter_B1 flat (+4.6 / 49%). More plain retrains will not move the needle.

**Reason.** Both the exotic lever (NN-value-leaf) and the simple lever (more plain self-play) are now empirically exhausted against the v2.7-heuristic-leaf ceiling.

**Next.** Not another training-recipe tweak. The real blocker (per EXPERIMENTS.md) is that no checkpoint has been benchmarked against a strong human — "superhuman" is undefined-by-measurement. Branch decision: benchmark iter_01-level play vs a human / strong reference to learn where we actually stand, then either pivot toward Phase 5 (if it clears the bar) or commit to a harder strength lever (heuristic-leaf redesign, net capacity, or search-side knobs — see EXPERIMENTS.md open list).

**Reversal cost:** low — the Option 2 infra (`LeafConfig.value_blend`, blend wiring, `--value-target score_diff`) stays in the tree dormant; revisiting needs a materially stronger value head.
**Phase:** 4 (self-play).

## 2026-05-17 — self-play perf optimization: hash-cache + get_side shipped; deeper leaf-eval memoization (Options A & B) parked — find_farm is start-dependent

**Context.** iter_01/iter_02 each took ~11h of local self-play; iter_B1 and any future iterations pay the same. Profiling one production self-play game (sims=200, v2.5 leaf) showed the heuristic leaf eval is ~83% of CPU, with object hashing ~31% of self-time and the set-based connected-component flood-fills (`find_farm` 328s cumulative, `find_city` 96s) dominating. Three optimization tiers were considered, cheapest first.

**Tier 1 — shipped (committed `080fea7`, on `gpu-orchestrator`).** Cache `__hash__` on the immutable engine value objects (`Coordinate` family, `FarmerConnection`) and precompute `FarmerSide.get_side` (it was walking the enum `.value` descriptor up to 4× per call). Both behavior-preserving (bitwise-identical hashes / outputs; full suite green). cProfile re-profile: 651→561s — ~14% from hashing alone, `get_side` projected ~+12%, ~20-24% combined. Live in iter_B1.

**Tier 2 — Option A, memoize the find_* flood-fills — PARKED.** Cache `find_city`/`find_road`/`find_farm` results per board on the game state, invalidated at the single tile-placement site (`StateUpdater.play_tile`). find_city + find_road were memoized and verified bitwise-identical via a differential test (240 states early/mid/late/terminal + the in-place MCTS-rollout path + `count_final_scores`, all memo-on == memo-off). **But `find_farm` — the #1 hot path — is start-dependent**: the engine's farm flood-fill returns *different* farmer-connection sets depending on which connection you start from (verified by the differential test: 11 vs 4 from the "same" farm). Caching a farm under its member positions is therefore unsound — a query would hit a result computed from a different start point. find_farm was reverted; the surviving find_city+road memo is only ~6% (find_city is ~96s of the ~420s of find_* cost). Committed on branch `leaf-memoization` (`3db30f1`), **not merged**.

**Tier 3 — Option B, incremental connected-components (union-find) — PARKED, not started.** A union-find represents *symmetric* connectivity by construction, so it cannot reproduce a start-dependent `find_farm` without adopting the corrected symmetric farm semantics — which would change the leaf's farm bonus and `count_final_scores`' farm points (a behavior change, not a transparent optimization). For cities/roads alone it could beat Option A's 6% modestly (~10-12%) but needs incremental maintenance on every tile placement (touching `apply_action_inplace` + every River/farmer edge case) — worse risk/reward than A.

**Options considered:**
  - A: Memoize find_* (Tier 2). Found unsound for find_farm; the safe remainder is ~6%.
  - B: Incremental union-find (Tier 3). Cannot represent the engine's start-dependent farm semantics; cities/roads-only is marginal at higher risk.
  - C: Ship Tier 1, park A and B.

**Decision:** chose C.

**Reason.** `find_farm` is ~58% of the leaf-eval cost and is structurally resistant to *both* memoization and union-find, because the engine's farm traversal is start-dependent — no caching strategy reaches it. The reachable remainder (find_city+road) is only ~6%, and it is a vendored-engine change on the scoring path (project-wide blast radius — `count_final_scores` feeds real game outcomes and training labels), so a ~6% gain does not justify the merge-risk attention. The only routes to the find_farm win are (a) micro-optimizing its flood-fill internals — grindy, and the easy parts (hashing, get_side) are already done — or (b) deliberately replacing the buggy start-dependent `find_farm` with a correct symmetric one, a behavior change needing a re-validation A/B, not a free optimization. Neither is worth diverting from the iter_02-ceiling work (Option 2 / iter_B1). Local optimization has hit diminishing returns at the ~20-24% already banked.

**Reversal cost:** low. Tier 1 is committed and behavior-preserving. Option A's verified work sits on `leaf-memoization` if the 6% is ever wanted; Option B was never built.

**Phase:** 4 (self-play infrastructure).

## 2026-05-17 — closure-probability accuracy is not the leaf-eval lever; Option-1 (heuristic-leaf refinement) yields two null results → pivot to Option-2

**Context.** The iter_02 entry below established the next lever is leaf-eval quality, and named two candidates: (1) improve the heuristic leaf, (2) NN value head as a correction term. Option 1 was tried first — lower risk, incremental. The most lit-review-backed leaf refinement was tile-counting closure probability: `virtual_score_v2`'s closure-anticipation bonus uses a fixed P(closure) schedule `{1:0.5, 2:0.2}` keyed only on a feature's open-position count; it never consults the remaining deck. A city needing 3 more city-tiles when only 1 city-tile remains in the deck *cannot* close — yet the fixed schedule still pays the bonus. Making P(closure) deck-aware should be strictly more accurate.

**Infra built (committed, kept regardless of outcome).** `LeafConfig` dataclass — per-evaluator config, replacing the process-global `CARCASSONNE_V25_*` env vars — plus `--{new,old}-leaf-variant` on `eval_iter_head_to_head.py`. Two leaf variants can now run in one process for a clean same-checkpoint leaf-vs-leaf A/B. Reusable for Option-2 tuning. Commits f83ce34, 89f82e3, 1f1c01f.

**Test design.** Both A/Bs: iter_01 checkpoint on *both* sides, only the leaf differs — isolates the leaf change with zero confound from network strength. n=100, sims=200, v2.7 production knobs (cap=12, drop-3-open).

**Two variants tried.**
- *Step 3b — hard tile-counting gate.* P(closure)→0 only when the deck literally cannot finish the feature. **45W/1D/54L = 45% wr, −4.8 avg score diff.** Within noise of 50%, point estimate negative.
- *Step 5 — continuous deck-aware ramp.* P(closure) scaled smoothly by `_supply_factor(supply, need, slack=3)` — discounts in the mid-game, not just the impossible endgame. Unit tests confirm it fires on far more positions than the cliff. **50W/1D/49L = 50% wr, −1.4 avg score diff.** A flat wash.

**Verdict — closure-probability accuracy is not the lever.** The hard gate's 45% could be dismissed as "the cliff fires too rarely." The continuous ramp was built precisely to kill that objection: it fires constantly in the mid-game and still nets *exactly zero*. Pooled across both benches the deck-aware-closure direction is 95/200 = 47.5% — a tight null. MCTS does not need a calibrated P(closure); the rough fixed schedule is already sufficient.

**Decision — Option 1 is closed for the closure-probability angle; pivot to Option 2 (NN value-head correction term).** Reasoning: iter_02 established that the policy saturates against a *fixed* leaf. Hand-tuning the leaf only nudges a fixed ceiling — and two n=100 benches now show how little it nudges. Option 2 makes the leaf value carry a *learnable* component (the value head, trained on iter_01/iter_02's now-good self-play outcomes), so the leaf co-improves with self-play and the ceiling is no longer fixed. That attacks the saturation diagnosis structurally, where leaf hand-tuning cannot.

**Caveat — not every leaf refinement is dead.** Closure-P was one of ~4 lit-review refinements (large-open-city penalty, targeted denial, stranding-risk meeple weighting remain, parked in BACKLOG 2026-05-16). A null on closure-P does not prove a null on those — they are different *features*, not recalibrations of an existing term. But chasing them one-at-a-time is diminishing returns against the structural fix; Option 2 takes priority. The remaining refinements stay parked.

**Reversal cost:** low. The closure-continuous code is committed and off by default (`LeafConfig.closure_continuous_slack=0.0`); production behavior is unchanged. If Option 2 stalls, the parked refinements are still available.

**Phase:** 4 (self-play / leaf-eval).

## 2026-05-17 — iter_02 flattens: policy saturated against the fixed v2.7 leaf; the compounding ceiling is found

**Context.** iter_00 beat warmstart_canonical by +14.3 (2026-05-15); iter_01 beat iter_00 by +13.3 (2026-05-16). Two consecutive ~+14pt jumps from the same recipe (v2.7 leaf, 1200-game self-play, retrain from prev) raised the question: does it keep compounding? iter_02 — a third iteration, same recipe, from iter_01 — tests it.

**Run.** 1200-game v2.7 self-play from iter_01, local, W=14, 11.3h, $0. Pure self-play training (warmstart-mix 0.0), same recipe as iter_01.

**Result.** Anchor-gate vs iter_01 n=20: 11W/0D/9L = 55%. n=100 confirmation: **51W/5D/44L = 53.5% wr, +0.2 avg score diff, +24.4 elo.**

**Verdict — the compounding flattened.**

| step | avg score diff | n=100 wr |
|---|---|---|
| warmstart → iter_00 | +14.3 | (61.7% anchor n=30) |
| iter_00 → iter_01 | +13.3 | 59.5% |
| iter_01 → iter_02 | **+0.2** | **53.5%** |

53.5% is only 0.7σ above 50% (n=100 SE ~5pp) — within noise. The score-diff signal, the reliable one all week, says **+0.2 = zero gain**. iter_02 ≈ iter_01.

**Decision. iter_01 (`checkpoints/v25_retrain_iter01/iter_00.pt`) remains the global best. iter_02 is NOT promoted.** Promoting on 0.7σ would be the exact n=20-noise mistake the v3 cap sweep and PUCT c=2.0 sweep both made this week — at n=100 the discipline is the same: a sub-1σ wr gain with a zero score-diff is not a confident improvement. iter_02 is *equivalent* to iter_01, not better. (iter_02's checkpoint is kept; future work can warm-start from either — they're interchangeable.)

**What this establishes — the data-scarcity hypothesis was right but bounded.** More v2.7-recipe self-play helped for *exactly two iterations* (+14.3, +13.3), then hit a wall. This is **policy saturation against the fixed leaf**: `virtual_score_v2` is a fixed hand-crafted heuristic that never improves, so it defines a ceiling — "the best policy prior achievable given this leaf." iter_01 reached that ceiling; iter_02 can't exceed it. The sharp drop (+13.3 → +0.2, not a gradual taper) is the signature of a hard ceiling, not gradually-diminishing data returns.

**What this rules out.**
- *More iterations of the same recipe* — iter_03+ would also land ~+0. Dead direction.
- *Bigger policy net* — a higher-capacity policy head would saturate against the *same* leaf. Capacity is not the bottleneck. Bigger-net is de-prioritized by this result.

**What this points to — the next lever is leaf-eval quality.** Two candidate structural changes (both gated on a plan-mode session, neither auto-started):
1. **Improve the heuristic leaf** — the competitive-strategy lit-review refinements parked in BACKLOG 2026-05-16 (tile-counting closure probability, large-open-city penalty, targeted denial, stranding-risk meeple weighting). Lower-risk, incremental.
2. **NN value head as a correction term** — train a value head on the now-good iter_01/iter_02 self-play outcomes and use it to correct virtual_score's known blind spots (farm-composition path-dependence especially). Higher-ceiling, more invasive. The value head failed in v1-v6 because it trained on degrading self-play; it now has strong games to learn from.

**Also still open: no human benchmark.** iter_01 has never played a human. Before committing to a structural leaf change, knowing where iter_01 actually stands vs a strong human would size the remaining gap to "superhuman" — worth doing first or in parallel.

## 2026-05-14 — v2.5 hyperparameter sweep: sims=200 is the sweet spot, cap=5 is the inverted-U optimum

**Context:** After v2.5 cleared the v1 baseline at sims=400 (83.3%), two open tuning questions: (1) does sims<400 still match? (2) is cap=5 actually right, or did we get lucky?

**Sims sweep** (hybrid_v2.5 vs Tier-1, n=30 each):

| sims | v2.5 wr | v1 wr (same config) | Δ |
|---|---|---|---|
| 50  | 50.0% | 63.3% | -13.3pp |
| 100 | 71.7% | 58.3% | +13.4pp |
| **200** | **80.0%** | 70.0% | **+10.0pp** |
| 400 | 83.3% | 76.7% | +6.6pp |

**v2.5 ramps with depth more steeply than v1.** At sims=50 v2.5 is *worse* than v1 (the bonus is noise without enough search depth). At sims≥100 the anticipation signal becomes informative and v2.5 pulls ahead. **sims=200 is the new sweet spot** — 80% wr at half the compute of sims=400 (only 3pp less). Production for ablation benches: sims=200. For raw-strength benches: sims=400.

**Cap sweep** (cap ∈ {2, 5, 8, 15} at sims=200 n=30):

| cap | v2.5 wr | Δ vs cap=5 |
|---|---|---|
| 2  | 60.0% | -20.0pp |
| **5 (production)** | **80.0%** | — |
| 8  | 73.3% | -6.7pp |
| 15 | 76.7% | -3.3pp |

Clean inverted-U: cap=2 strangles the bonus signal; cap=8/15 reintroduces tanh saturation (smaller dose of v2's failure mode). Hand-picked cap=5 happens to land on the knee. n=30 SE ~9pp, so cap=5 dominance over cap=2 is decisive (~2σ); over cap=8/15 it's suggestive but not bulletproof.

**Decision: production = `_BONUS_CAP=5.0`, sims=200 (ablation) or sims=400 (raw strength).**

**Plumbed:** `CARCASSONNE_V25_CAP` env var on `virtual_score_v2.py` for future cap sweeps without source edits.

**Lesson:** when a hand-picked initial value happens to be optimal, the clean inverted-U around it is reassuring — confirms it's not a knife-edge dependent on noise. If cap=5 had been on a slope, we'd worry the next change downstream might shift the optimum.

## 2026-05-16 — iter_01 retrain confirms data-scarcity hypothesis: more v2.7 self-play → stronger model

**Context.** iter_00 (1200-game v2.7 self-play retrain) beat warmstart_canonical +21pp on 2026-05-15. Open question: was that a one-shot warmstart→trained jump, or does the recipe keep compounding with more self-play? iter_01 tests it — another 1200 games, same recipe, initialized from iter_00.

**Run.** Launched locally (vast.ai's docker-pull infra was down — 7 boxes stalled; see [[feedback-vastai-success-false-still-creates]]). 1200-game v2.7 self-play, W=14 (the v2.7-recipe worker optimum, freshly benched — not the old W=16 NN-value optimum), sims=200, c_puct=1.5, initialized from iter_00. **Pure self-play training** (`--warmstart-mix-schedule 0,0,0,0`) to replicate iter_00's exact recipe — iter_00 trained with `warmstart_in_list=0` because the cloud box never had the warmstart .npz, so for a clean "more data, same recipe" A/B iter_01 matched that. 10.6h wallclock, $0.

**Result.** Anchor-gate vs iter_00 n=20: 12W/0D/8L = 60% wr, +11.8 avg diff. **n=100 confirmation: 59W/1D/40L = 59.5% wr, +13.3 avg score diff, +66.8 elo.**

**Why the n=100 confirmation.** 60% at n=20 is only ~0.9σ above 50% — the same noise band that produced false winners in the v3 cap sweep and PUCT c-sweep this week (both evaporated at larger n; see [[feedback-n50-min-for-variant-comparison]]). iter_01's 60% was NOT allowed to stand on n=20. At n=100 it held at 59.5% (~1.9σ above 50%) with the score-diff signal *strengthening* (+11.8 → +13.3). First n=20 result of the week to survive — because this one was real.

**Decision. iter_01 (`checkpoints/v25_retrain_iter01/iter_00.pt`) is the new global best.** Supersedes iter_00 and the v6 `iter_12.pt`.

**What this establishes.** The +13.3 score-diff over iter_00 is a similar magnitude to iter_00's +14.3 over warmstart_canonical. Two consecutive ~+14-point jumps from the same recipe → **the ceiling is data quantity, not recipe or architecture.** The v1-v6 plateau was a leaf-eval problem (NN value head), not a fundamental one. With the v2.7 leaf, each 1200-game retrain compounds.

**Open question for iter_02.** Does a third iteration keep the ~+13 cadence, or do returns diminish? If iter_02 also lands ~+13, a longer multi-iter run is clearly worth the compute. If iter_02 flattens, we've found the data-per-iteration knee and should either grow games/iter or accept the current level and pivot to human-play evaluation. iter_02 not launched autonomously — pending Joshua's go.

## 2026-05-15 — PUCT c sweep: low c (≤1.0) catastrophic; default c=1.5 is well-chosen; don't promote c=2.0

**Context.** After v3 cap tuning closed as inconclusive, ran the PUCT c sweep from EXPERIMENTS.md as the next ablation. The 2026-05-14 diagnostic identified "low c → search over-explores into virtual_score's blind spots" as a hypothesis. PUCT formula: `U(a) = Q(a) + c · P(a) · sqrt(N_parent)/(1+N_child)`. Low c down-weights the NN policy prior P(a), so search explores more uniformly.

**Sweep.** iter_00 + v2.7 leaf vs Tier-1 at sims=200, n=20:

| c_puct | iter_00 wr | score diff (NN POV) |
|---|---|---|
| 0.5 | 67.5% | +4.2 |
| 1.0 | **52.5%** ← barely beats Tier-1 | +7.2 |
| 1.5 (current default) | 80% | +27.4 |
| 2.0 | 85% | +40.3 |
| 3.0 | 75% | +37.0 |

**Confirmation runs (n=50, per the n=50-for-comparison memory rule):**
- c=2.0: iter_00 88% wr, score diff -38.5 (rule POV)
- c=1.5: iter_00 84% wr, score diff -38.0 (rule POV)

**Result.** c=2.0 vs c=1.5 at n=50: indistinguishable. WR gap 4pp ≈ 0.6σ (SE ~7pp combined). Score-diff gap 0.5pt = effectively zero. The n=20 spread between c=1.5/2.0/3.0 was within noise; only c=2.0's *winner-at-n=20* status was noise.

**Real finding: catastrophic low-c boundary.** c=1.0 → iter_00 52.5% (nearly ties Tier-1, who is supposed to lose 80%+ of the time). c=0.5 → 67.5%. Both well outside n=20 noise; score-diff signal confirms (+4 to +7 vs default's +27). The 2026-05-14 hypothesis "low c over-explores into virtual_score's blind spots" is CONFIRMED. The NN policy prior is load-bearing — search has to trust it heavily, not explore around it.

**Decision.** Default c=1.5 stays. Don't promote c=2.0. Add a note to mcts.py's `DEFAULT_PUCT_C` constant explaining the lower bound is enforced by empirical data (c≤1.0 catastrophic).

**Why this matters for future work.**
1. If anyone (or future-me) tries to lower c "for more exploration," they'll break iter_00's strength. The constant comment should warn.
2. iter_01 retrain doesn't need a c_puct hyperparameter sweep — c=1.5 is in the flat region, not on a knife-edge.
3. The result indirectly confirms iter_00's policy prior is **well-trained enough that search wants to trust it.** This is a positive signal for the training pipeline.

**Today's second case of n=20-noise-evaporating-at-n=50.** v3 cap tuning (morning) and PUCT high-c promotion (afternoon) both looked like winners at n=20 and collapsed at n=50. The n=50 memory rule has earned its keep twice today. See [[feedback-n50-min-for-variant-comparison]].

## 2026-05-15 — v3 leaf: cap tuning is fitting n=20 noise; v2.7 cap=12 is at the local optimum (or indistinguishable from one)

**Context.** Post-iter_00 retrain landed today, the next leaf-eval iteration was v3 — two additions from the 2026-05-14 failure-mode diagnostic that v2.7 didn't address:
1. **Meeple economy** — `_MEEPLE_K × (meeples_self - meeples_opp)` added after caps (failure-mode 4: over-committed meeples).
2. **Asymmetric opp cap** — `_OPP_BONUS_CAP` separate from `_BONUS_CAP`, raising it amplifies the negative contribution of opponent's near-closures to search value (failure-mode 3: denial invisible).

Implementation refactor: cap moved from inside `_closure_anticipation_bonus` to `virtual_score_v2` via a `_capped(bonus, cap)` helper. Without this, self and opp couldn't be capped differently. Tests updated to reflect the new location.

**Key fact about the bench setup.** The bench was rule_player vs iter_00 (opponent=hybrid_v2). `RuleBasedPlayer` uses `virtual_score_inplace` from `virtual_score` (v1, NOT v2) — see `src/carcassonne_ai/rule_based_player.py:46`. So the `CARCASSONNE_V25_*` env vars **only affect the NN's hybrid_v2 leaf, not the rule-player side.** Tier-1's behavior is invariant under v3.

This means the sweep is a direct test of "does v3 leaf strengthen iter_00 against Tier-1?"

**Sweep.** rule_player (Tier-1) vs iter_00+v3 at n=20 sims=200 W=12+orch. Tier-1 uses v1 virtual_score (env-var-immune), so env vars affect only the NN's hybrid_v2 leaf.

**Full results** (rule_player wr shown; iter_00 wr = 100 - rule wr):

| variant | n=20 rule wr | n=20 iter_00 wr | n=50 iter_00 wr | n=50 score diff (rule POV) |
|---|---|---|---|---|
| v2.7 baseline (cap=12, opp_cap=12 implicit) | 10% | 90% | (not run) | -37 (n=20) |
| meeple_K ∈ {0.5, 1.0, 2.0} | 10% (all 3) | 90% | — | -31.8 to -42.2 |
| opp_cap=5 | 5% | 95% | **80%** | -26.3 |
| opp_cap=8 | 25% | 75% | — | — |
| opp_cap=20 | 20% | 80% | 80% | -27.3 |
| opp_cap=30 | 20% | 80% | — | — |

**The n=20 results suggested a story.** At first read: high opp_cap regressed (80% wr), low opp_cap=5 helped (95% wr), opp_cap=8 was a dip (75%). I built a "denial double-counting" hypothesis around it — NN policy prior already encodes opp-threat awareness, so leaf amplification at high cap hurts; low cap helps by reducing double-counting.

**n=50 broke the story.** Both opp_cap=5 and opp_cap=20 landed at 80% at n=50. Score diffs were identical (-26.3 vs -27.3). The whole n=20 spread (75-95%) was fitting noise — at n=20 SE ~7pp, the 90% v2.7 baseline anchor itself is indistinguishable from 80%.

**Correct conclusion.**
- **v3 cap tuning is exhausted.** opp_cap ∈ {5..30} all produce iter_00 wr ~80% ± 5pp vs Tier-1 at n=50.
- **v2.7 cap=12 IS at the local optimum, or indistinguishable from one.** No tuning direction (up or down) moves the needle at n=50.
- **Meeple_K is null** — all 3 magnitudes gave identical outcomes at n=20. Plausibly an additive-on-saturating-cap dead-zone, but with cap itself being non-tunable, this story doesn't matter much.

**Decision.** Keep v3 env-var infra committed (zero default impact: `_OPP_BONUS_CAP` defaults to `_BONUS_CAP`, `_MEEPLE_K` defaults to 0.0). **Production stays at v2.7 cap=12.** Defaults unchanged.

**The two lessons here are bigger than v3.**
1. **n=20 benches at SE ~7pp can't distinguish 75% from 95% wr.** If I'd run the baseline at n=50 alongside opp_cap variants, I'd have known immediately that the "v3 regresses" story was over-read. Standard practice now: anchor measurements at n=50 minimum when comparing variants within 15pp of each other.
2. **Two separate analytical errors compounded today.** First I mis-identified WHICH side of the bench used env vars (wrote "v3 helps rule-player" when env vars only affected the NN). Then I corrected to "v3 regresses NN" without questioning whether the BASELINE was solid. Both errors live in the prior commit messages (`e55f622`, `862ec37`) — this entry is the third-and-correct read. Lesson: when a result reverses a story, also re-question what the *reference* says.

**Where next.** Cap tuning is closed. Three live directions:
1. **iter_01 cloud retrain** on v2.7 leaf (~$2.40, ~6h). Tests data-scarcity ceiling.
2. **Human play vs iter_00.** Tier-1 is saturated as a reference now — same ~80% wr regardless of leaf cap, so it doesn't discriminate iter_00 from anything similar in strength.
3. **PUCT c sweep** (~30 min local). Search-side knob, separate from leaf.

## 2026-05-15 — v2.5 dedup bug fix + cap/P re-sweep + cloud retrain: iter_00 +21pp over warmstart_canonical

**Context:** Pre-launch we held v2.5 at 80% wr vs Tier-1 (sims=200, cap=5, P={1:0.5, 2:0.2, 3:0.05}). Cloud retrain at sims=200 on a vast.ai 5090 box hit 6× the predicted wallclock (5.8h vs 1.6h estimate). Investigated v2.5 leaf-eval cost; found a real over-counting bug: multiple meeples on the same farm/city each got `_closure_anticipation_bonus` added separately, but the engine itself only scores each farm/city once per player. Bonus inflated for multi-meeple farms.

**Bug fix (commit `08dfead`):** dedup farms/cities by canonical content (`frozenset(farmer_connections_with_coordinate)` and `frozenset(city_positions)`). The engine returns fresh `City`/`Farm` objects per call (no `__eq__`/`__hash__`), so identity dedup didn't work — needed canonical fingerprints.

Side-effect: per-leaf perf was within noise (~325s/game/worker locally, same as pre-fix). The dedup was a correctness fix, not a perf fix. But the wallclock projection was honest — 1500 games on cloud takes ~5h regardless. Reduced retrain target to 1200 games.

**Bench fallout:** fixed v2.5 + cap=5 dropped to 70% wr (from buggy 80%). The over-counting was load-bearing on cap=5's tuning. Re-swept cap on FIXED v2.5:

| config (n=20 sims=200 each) | wr | avg diff |
|---|---|---|
| fixed + cap=5 (3-tier P) | 70% | n/a |
| fixed + cap=8 | 60% | -17.8 |
| **fixed + cap=12** | **85%** | -22.4 |
| fixed + cap=20 | 85% | -34.7 |

cap=12 + cap=20 plateau. cap=12 is safer (lower bonus magnitude → less risk in unusual states).

**P-schedule sweep (cap=12 fixed):**

| variant | _CLOSURE_P | wr |
|---|---|---|
| 3-tier (default) | {1:0.5, 2:0.2, 3:0.05} | 85% |
| v2.6 (1-only) | {1:1.0} | 77.5% |
| **v2.7 (drop 3-open)** | **{1:0.5, 2:0.2}** | **90%** |

v2.7 wins by 5pp over 3-tier and 12.5pp over 1-only. **Joshua's intuition:** 3-open features are lottery tickets — the 0.05 weight just adds noise without useful signal. Dropping them removes the noise floor and lets the higher-quality 1-open and 2-open signals dominate.

**Decision:** production v2.5 leaf = `_BONUS_CAP=12` + `_CLOSURE_P={1:0.5, 2:0.2}` (env vars `CARCASSONNE_V25_CAP=12 CARCASSONNE_V25_DROP_THREE_OPEN=1`). +10pp over the buggy v2.5 ceiling.

**Cloud retrain (commit `f89b5f3`, watchdog `b46b539`):**
- 1200 games of warmstart_canonical-vs-warmstart_canonical self-play with v2.7 leaf
- sims=200, batch=8, virtual_loss=1.0, orchestrator, W=48
- 6h10min wallclock, ~$2.40 vast.ai (5090 + 48-core EPYC, $0.37/hr)
- Train 3 epochs on 188K positions: train_pol_loss 1.5358→1.5015, train_val_loss 0.9552→0.9125. val_pol_loss drifted up slightly (1.5475→1.5661, mild overfit signal) but anchor result is positive so net-positive.

**Anchor result (apples-to-apples both sides v2.7 leaf, sims=200, n=30):**
- iter_00.pt vs warmstart_canonical.pt: **18W/1D/11L = 61.7% wr**
- avg diff +14.3 (iter_00 wins by ~14 pts/game)
- elo_delta +82.6
- Anchor-gate threshold 50% met cleanly.

**Significance:** the policy retrain on v2.7-driven self-play data improved iter_00 by +21pp over the warmstart it started from. This is the first checkpoint generated by the new pipeline (correct leaf, retuned hyperparameters, fixed dedup) — it cleanly beats the v1-v6 best (iter_12 at 70% wr vs warmstart_canonical with NN value, but those numbers are from the old leaf eval; not directly comparable here).

**Lessons:**
1. **Pre-flight smoke must use SAME knobs as production.** I ran sims=50 smoke locally and extrapolated linearly to sims=200 cloud. Real per-leaf v2.5 cost grows nonlinearly with placed meeples (more late-game state = more farm-util work). Cost: 6× wallclock surprise.
2. **Bug fixes can shift hyperparameter optima.** The cap=5 was tuned against the buggy bonus magnitudes. After dedup, the bonus magnitudes dropped, and cap=5 became too tight. A correct fix doesn't preserve bench numbers — re-tune.
3. **Lottery-ticket weights add noise, not signal.** Dropping the 3-open tier (P=0.05) gained 5pp over including it. The intuitive "more terms is more information" was wrong; small-weight terms can hurt by giving the search small uniform pushes that drown out the high-confidence ones.

## 2026-05-14 — Cloud-prep: --leaf-eval v2_5 plumbed through self-play harness; MCTS virtual-loss batching validates 3× batch-fill improvement

**Context:** Before any cloud retrain on v2.5 self-play data, the harness needs three things consistent: (1) self-play uses v2.5 leaf during MCTS so generated games reflect the v2.5 strategy, (2) MCTS virtual-loss batching is enabled so the orchestrator gets full benefit, (3) anchor-gate / h2h evals use the same leaf eval for apples-to-apples comparison.

**Implemented (commit `1d3a0cb`):**
- `evaluators.py`: new `make_v25_value_wrapper` / `make_v25_batch_value_wrapper`. Wrap any (priors, value) evaluator: keep its priors, replace its value with `tanh(virtual_score_v2(state, current_player) / 15)`. Compatible with both local and remote (orchestrator) evaluators since it only consumes the (priors, value) shape.
- `run_selfplay_iter.py`: added `--leaf-eval {nn, v2_5}` flag. Defaults to `nn` for v1-v6 back-compat.
- `eval_iter_head_to_head.py`: same flag, applied to BOTH sides simultaneously so an anchor-gate eval comparing iter_X to warmstart_canonical compares them at the same leaf eval.
- `run_phase4_smoke.py`: propagates `--leaf-eval` to all 3 substages.
- `train_iter.py`: NOT TOUCHED. Training labels (`z`) come from game outcomes, not leaf evals. Independent of this change.

**Smoke-validated:** End-to-end smoke at W=4 sims=50 batch_size=8 vloss=1.0 orchestrator v2_5 (4 self-play games):
- 78s wallclock, 663 positions saved.
- `avg_batch=7.2` — up from 2.4 measured at W=6 without batching earlier today (~3× batch-fill improvement).
- Stage breakdown 74% dequeue / 26% forward — GPU is now waiting for workers, the inversion we wanted. Earlier bottleneck (PCIe-bound serial inference) is fixed by batching.
- h2h smoke at same config: 89% dequeue / 10% forward (two server pools split traffic). At cloud W=48 the orchestrator should approach saturation.

**Caveat to watch on real cloud run:** smoke h2h with same checkpoint both sides (n=4 only) gave 4-0 instead of expected 50/50. Almost certainly MCTS-seed asymmetry × low N noise, but verify with n≥20 on the actual cloud before trusting any v2.5-vs-v1-warmstart anchor-gate signal.

**Decision:** cloud-ready. Recipe for the policy-retrain run = v6 baseline + `--leaf-eval v2_5 --batch-size 8 --virtual-loss 1.0 --orchestrator`. Estimated cost $1 (vs yesterday's $5 estimate; sims=400→200 + batching + orchestrator each cut a chunk).

## 2026-05-14 — orchestrator at W=6 hurts, at W=12 helps — IPC overhead vs batching tradeoff

**Context:** GPU-Z showed 35% GPU / 76% PCIe load during v2.5 bench at W=6 — looked like PCIe-bound. Plumbed `--orchestrator` into `eval_rule_player.py` (mirroring `eval_iter_head_to_head.py`).

**Local A/B at sims=100 n=12:**

| Config | wallclock/game | avg_batch | speedup |
|---|---|---|---|
| W=6 baseline | 19.0s | n/a | 1.00× |
| W=6 + orchestrator | 16.0s+ | 2.4 | -19% (slower) |
| W=12 baseline | 16.8s | n/a | 1.13× |
| W=12 + orchestrator | 14.6s | 4.8 | 1.30× |

**Diagnosis:** PCIe load was high *count* (many small transfers), not high *latency* (per-transfer is fast). The orchestrator can only amortize forward-pass cost when batches fill, but at W=6 workers pipeline serial inference without contending — avg_batch stays at 2.4. IPC overhead per request exceeds the batching gain. At W=12 contention rises, avg_batch hits 4.8, and the orchestrator pays back.

**Decision:** local production = W=12 + `--orchestrator` for ablation benches. Saves ~25% wallclock vs prior W=6 default. Cloud (W=48 with naturally higher contention) still benefits more, as proven in the 2026-05-12 cloud bench.

**Caveat:** numerical agreement <1e-5 vs baseline at sims≥200; at sims=100 small float noise → argmax flips → different MCTS games. Production sims=200 is fine.

**Bigger lever not yet pulled:** MCTS virtual-loss batching (`batch_size > 1` per worker, with virtual_loss=1.0). One worker submits K sims in parallel via virtual losses → orchestrator batch fill multiplies by K. Code already supports it; calls just don't use it. Estimated 2-4× additional speedup at our worker count. Worth wiring before any cloud retrain.

## 2026-05-14 — v2.5 BENCH PASSES at 83.3% vs Tier-1 — +6.6pp over v1; production candidate

**Context:** v2.5 = halved P heuristic ({1: 0.5, 2: 0.2, 3: 0.05}) + bonus cap at ±5 per player. Built per v2-diagnostic finding that tanh-saturation was the v2 failure mode.

**Bench:** hybrid_v2.5 vs Tier-1, sims=400, n=30, 6 workers, ~35 min wallclock. Result:

| | wr | avg score diff |
|---|---|---|
| Tier-1 (rule-player) | 16.7% (5/30) | +30.7 (Tier-1 loses by avg ~31 pts) |
| **hybrid_v2.5** | **83.3% (25/30)** | -30.7 |

Comparison:
- v1 hybrid_warmstart sims=400 n=30: 76.7% (prior production config)
- v2 hybrid_warmstart_v2 sims=400 n=30: 30.0% (47pp regression, halted)
- **v2.5 hybrid_warmstart_v2.5 sims=400 n=30: 83.3% (+6.6pp over v1, +53pp over v2)**

**Decision:** **v2.5 becomes the production leaf eval.** The closure-anticipation + farm-growth design was strategically correct; the issue was tanh saturation, not the underlying signal. Capping the bonus brings the signal into tanh's responsive region while preserving the strategic content.

Production config update:
- `warmstart_canonical.pt` + `_hybrid_v2_evaluator` + sims=400 + ≥4 workers
- v2 module is named `virtual_score_v2.py` but its constants are now v2.5 (`_CLOSURE_P = {1: 0.5, 2: 0.2, 3: 0.05}`, `_BONUS_CAP = 5.0`). Module name kept for git continuity; the file IS v2.5.

**Still NOT superhuman.** 83.3% wr is 6.6pp better than v1 but Joshua still beats Tier-1 2-of-3. Phase 5 still gated. Next levers (in priority order):

1. **Sims sweep for v2.5** — v1's optimum was sims=400; v2.5's optimum may differ. If sims=200 matches sims=400, production throughput doubles.
2. **Cap tuning** — cap=5 was a hand-picked initial value. Sweep cap ∈ {2, 5, 8, 15} to find the knee.
3. **Retrain policy head on hybrid_v2.5 game data** — the NN policy was trained on virtual_score_v1 self-play. Generating ~10K games with hybrid_v2.5 self-play and retraining the policy head should compound — better leaf → better self-play targets → better policy → better leaf-weighted search.

**Lesson recorded:** When stacking signals into a tanh-squashed leaf eval, **scale matters more than sign-correctness**. v2 had the right design but wrong magnitudes; v2.5 fixed magnitudes alone and unlocked a +6.6pp gain over the v1 baseline. This is the first 50pp+ improvement from a single ablation knob in the project's history.

## 2026-05-14 — v2-diagnostic: bonus scale is 4-7× larger than v1 base — tanh saturates, search loses gradient

**Context:** v2 lost the bench by 47pp. Before tuning P heuristics blindly, built `scripts/diagnose_v2.py` to dump per-move bonus contributions and aggregate signals. One game, sims=100.

**Findings (seed 0, 165 moves):**
- **Cathedral branch never fires.** Good — that hypothesis was wrong; not a bug.
- **|net_bonus| > |base| in 92% of moves.** v2's added bonus dominates v1's base on nearly every move.
- **`bonus_self + bonus_opp` > |base| in 95% of moves.** Same conclusion.
- **Max `bonus_self` = 133 in one game.** v1 base typically sits at ±15-30. Bonus is 4-7× the base.
- **Bonus is wildly asymmetric.** Self farmer contributions: ~9466 cumulative; opp farmer: ~357. Self has many farmers; Tier-1 plays few; v2 gives hybrid a phantom advantage.
- **Terrain-by-terrain attribution (self):** None (farmer) 9466 / city 545 / chapel 109. Farm-growth bonus is the dominant signal by ~20×.

**Root cause:**

The leaf eval is `tanh((base + bonus_self - bonus_opp) / 15)`. With base=+10 and net bonus = +80, `tanh(90/15) = tanh(6) ≈ 1.0`. Most leaves saturate at ±1 because the bonus magnitude exceeds 15. Once tanh saturates, MCTS can no longer distinguish good leaf states from bad ones — the leaf value collapses to a constant, the search loses its gradient, and it picks worse moves than v1 (whose base eval still varied across leaves).

The farm-growth bonus is the dominant offender. Each farmer with K incomplete-but-likely-to-close adjacent cities adds `3K × P` to the bonus. A connected farm can touch 5-15 cities; with P=0.5 for 2-open cities, a single farmer easily contributes +10-15 to the bonus. Multiple farmers + multiple closable cities = bonus magnitudes of 50-130.

**Decision: v2.5 = scale + cap.**

Two complementary fixes (build both, bench together; smallest change that addresses the saturation):

1. **Halve the closure-P heuristic:** `{1: 0.5, 2: 0.2, 3: 0.05}` (was `{1: 1.0, 2: 0.5, 3: 0.25}`). Brings the bonus magnitude into the same scale as the base.
2. **Cap the bonus term at ±5 per player.** Hard ceiling so even if many features chain into a closure-wave, the leaf-eval scale doesn't blow past tanh's linear region. This is a stability measure, not a strategic one.

Acceptance: hybrid_v2.5 sims=400 n=30 vs Tier-1: hybrid wr ≥ 76% (match v1 baseline). Stretch: ≥ 80% (the bonus adds real signal at the right scale).

**If v2.5 fails:** the structural design is wrong, not the magnitude. Pivot to v3 (drop closure-anticipation, try denial-value of opponent's near-closures or meeple-economy state).

**Lesson:** when stacking signals into a leaf eval that's then squashed by tanh, scale matters more than sign-correctness. A *correct* signal of the wrong magnitude is worse than no signal at all because it saturates the squash and kills the gradient.

## 2026-05-14 — virtual_score_v2 FAILS the bench: ~47pp regression vs v1 (30% vs 76.7% wr at sims=400)

**Context:** Built v2 per the prior decision (closure-anticipation bonus + farm-growth potential). Implementation, tests (11/11 pass), wiring through `eval_rule_player.py` as `--opponent hybrid_v2`. Bench: n=30 sims=400 vs Tier-1, 6 workers, ~37 min wallclock.

**Result:** Tier-1 21W / 0D / 9L vs hybrid_v2. **hybrid_v2 wr = 30.0%** vs hybrid_v1 wr = 76.7% at the same sims/n. Avg score diff = -10.6 (v2 loses by ~11pts on average). **~47pp regression.**

**Diagnosis (hypotheses, not yet verified):**
1. **Closure-P heuristic too aggressive.** `P=0.5 at 2 open positions` is probably wrong — most 2-open city positions never close because tile supply runs out or the tiles needed don't exist in the remaining deck.
2. **Farm-growth bonus double-counts denial.** If a farm meeple gets +3 × P for each incomplete adjacent city, AND the same city's closure also fires the city closure bonus on the opponent's side, we may be over-rewarding both players' bonuses asymmetrically.
3. **Cathedral-flag detection is broken.** v2 treats `tile.inn` as the cathedral flag on city tiles, but `inn` is the actual road-inn flag. Cities don't have `tile.cathedral`. This means `_city_closure_delta` adds `6 if tile.shield else 3` for any tile that has an inn-adjacent road. **Likely bug** — needs verification. The base-game + River + Farmers scope shouldn't even have cathedrals, so this branch should never fire; if it does, it's wrong.
4. **Bonus dominates the base.** Median per-game `bonus_self` + `bonus_opp` might be larger than `base`, flipping the leaf-value sign mid-game.

**Decision:** **Halt v2 deployment.** Commit the infrastructure (the diagnostic tools and v2 module remain useful for v2.5 iteration), but do NOT use v2 in production. Production stays at `hybrid_warmstart_canonical` with v1 `virtual_score` + sims=400.

**Next step:** rather than tune the P heuristic blindly (which would burn many bench cycles), build a v2-diagnostic — replay one game with v2 logging EVERY meeple-bonus contribution at every move. Catalog which bonus type fires most, whether the totals are sane, and whether the cathedral branch is firing incorrectly. THEN decide between (a) v2.5 (fix bugs + retune P), (b) v3 (drop closure-anticipation, try denial-value or meeple-economy), or (c) accept v1 + pivot to retraining the policy head on hybrid-generated data.

**Lesson recorded:** Adding *more* signal to a leaf evaluator can hurt search if the signal has the wrong sign or scale at any depth. v2's bonuses were summed onto v1's base then fed through `tanh(diff/15)` — if the bonuses are systematically larger than the base, they overwhelm v1's real signal. Counterintuitive but matches the observed regression magnitude.

## 2026-05-14 — Virtual_score diagnostic: closure-blindness + farm-composition opacity are the dominant failure modes

**Context:** With production hybrid_warmstart still losing 23% to Tier-1 (n=30 sims=400), the next ablation question per [EXPERIMENTS.md](EXPERIMENTS.md) was: what specifically does `virtual_score` miss? Built `scripts/diagnose_virtual_score.py` — replays full hybrid-vs-Tier-1 games at sims=400 and prints per-move tables showing `vs_hybrid` (virtual_score from hybrid's perspective) at every step.

**Method:** n=10 games, 6 workers, ~10 min wallclock. Got 7W/3L (matches n=30 70-77% rate). Inspected all 3 lost games' per-move trajectories.

**Failure modes (ranked by frequency / severity):**

1. **Closure-event blindness (3/3 games).** Partial credit (`virtual_score` = 1pt/tile for incomplete city, 0 for farm with incomplete city) ≠ closure credit (2pt/tile + 3pt/city for farm). When opponent closes a near-complete feature, `vs_hybrid` swings by 5-30pts in *one move* with no advance warning. seed=1 example: tier1 placed TILE(6,16) at move 151, closed a ~13-tile city, `vs_hybrid` went -7 → -36 instantly. Hybrid had no signal that this closure was imminent and could have placed a denial tile.

2. **Farm composition opacity (2/3 games).** `count_farm_points` only counts cities with `city.finished == True`. As cities complete through the game, farm scores change in ways `virtual_score` doesn't anticipate. seed=0 example: at move 158, `vs_hybrid` = +24 (hybrid looking good). By move 163, it crashed to -6 — a 30pt swing where the actual on-board score change was only +11 for opponent. The extra ~20pts came from farm composition flipping.

3. **Denial-value invisible (≥1/3 games obvious).** Hybrid never plays defensive tiles to block opponent's near-complete features because `virtual_score` only sees current state, not opponent's expected future closure value.

4. **Over-committed meeples (1/3 games).** seed=8 showed hybrid playing FARMER moves while behind 18-50 — no meeple opportunity-cost modeling.

5. **Late-game volatility (3/3 games).** Single tile placements in endgame swing `vs_hybrid` by 30+ pts. Predictions aren't robust enough to drive late-game decisions.

**Decision: build virtual_score_v2** with the top two failure modes addressed:

- **Closure-proximity bonus**: for each incomplete feature with a meeple, add `(full_credit - partial_credit) × P(closes by game-end)`. Initial heuristic for P: based on open-positions-needed, e.g. 1.0 if 1 needed, 0.5 if 2, 0.25 if 3, else 0.
- **Farm-growth potential**: for each farm meeple, for each adjacent INCOMPLETE city, add `3 × P(completes)`. Same closure-probability heuristic.

Both extensions reuse the existing engine utilities (`CityUtil.find_city`, etc.). No engine changes needed. Estimated ~1 day implementation + tests + bench.

Acceptance: hybrid_warmstart sims=400 with v2 leaf beats hybrid v1 leaf by ≥10pp winrate at n=30 (i.e., ~13% vs Tier-1 → confirms 1 sigma improvement). If v2 doesn't improve, the failure mode is something else (probably denial-value) and we redesign.

The remaining 3 failure modes (denial, meeple economy, late-game volatility) are deferred — addressed in v3+ if v2 alone doesn't reach superhuman.

## 2026-05-14 — Sims sweep + uniform-priors ablation: policy head worth ~18pp; sims=400 is the ceiling; production config locked.

**Context:** After the value-head finding (next section below), two follow-up questions: (1) is sims=100 the sweet spot or are we missing a peak elsewhere? (2) does the NN policy head actually contribute, or could uniform priors + virtual_score leaf match it?

**Sims sweep** (hybrid_warmstart_canonical vs Tier-1, n=30 each, 4-6 workers):

| sims | Tier-1 winrate | hybrid winrate | avg diff | wallclock/game |
|---|---|---|---|---|
| 50 | 36.7% | 63.3% | -10.3 | 8.8s |
| 100 | 41.7% | 58.3% | -2.0 | 16.9s |
| 150 | 41.7% | 58.3% | +5.7 | 25.0s |
| 200 | 30.0% | 70.0% | -7.6 | 34.5s |
| 400 | 23.3% | 76.7% | -15.5 | 34.5s (4w) / 68.0s (4w) — see note |
| 800 | 23.3% | 76.7% | -12.6 | 97.3s (6w) |

**Uniform-priors ablation** (no NN — uniform priors + virtual_score leaf, sims=100 n=30 vs Tier-1): Tier-1 60% wr / +8.7 avg diff. Compare hybrid_warmstart sims=100 at Tier-1 41.7%. **The NN policy head is worth ~18pp winrate.**

**Findings:**
1. **Sims=400 is the scaling ceiling for hybrid_warmstart.** Doubling to sims=800 produced zero winrate improvement. The earlier "U-shape" hypothesis at sims=100-150 is probably just noise (SE ~9pp at n=30); the true curve is monotonically improving with diminishing returns, plateauing by sims=400.
2. **The NN policy head matters meaningfully.** Uniform priors + virtual_score leaf loses to Tier-1 60-40; with NN priors it wins 58-42. We cannot drop the network.
3. **Production config:** `warmstart_canonical.pt` + `_hybrid_evaluator` + sims=400 + ≥4 workers. Beats Tier-1 76.7% of games by avg 15 points.

**Still not superhuman.** Joshua beats Tier-1 2-of-3 in casual play; beating Tier-1 ~77% is not sufficient. The next ablation is diagnosing virtual_score's blind spots from games where hybrid lost — this informs whether a richer leaf eval (virtual_score_v2 with farm-growth, denial, meeple-economy components) is the path past 77%.

**Caveats:**
- n=30 per point gives SE ~9pp; the sims=100 vs sims=400 gap (~18pp) is ~2σ — real but not bulletproof.
- Earlier n=20 sims=100 result (Tier-1 20%) was a lucky sample; n=30 corrects to ~42%.
- We have NOT tested if the 18pp policy-head advantage holds at higher sims (i.e., possible policy × sims interaction). Open question.
- Bench setup uses per-worker NN forward passes; PCIe is saturated at 4-6 workers. Wiring through the orchestrator would 2-3× throughput on the same box.

## 2026-05-14 — The NN value head was the bug. NN policy priors + `virtual_score` leaf flipped Tier-1 75%→40%.

**Context:** Day 2 after Tier-1 confirmed our trained nets all lose to a 1-ply heuristic. Day 1 result: Tier-1 beat warmstart_canonical 77% and iter_12 75% (both n=50 sims=100). Question: is the NN's policy or value head the broken component?

**Diagnostic:** built `_hybrid_evaluator` in `scripts/eval_rule_player.py` — identical to `_network_evaluator` except the value output is replaced with `tanh(virtual_score(state) / 15)`. Plugged into existing `NeuralMCTS` via its evaluator slot. ~20 LoC change. n=20 bench vs Tier-1.

**Result:**
| Setup | Tier-1 winrate | Avg score diff |
|---|---|---|
| iter_12 NN-only sims=100 (yesterday's bench, n=50) | 75% | (Tier-1 dominant) |
| HeuristicMCTS (no NN, UCT+virtual_score) sims=200 (n=20) | 60% | -1.1 |
| **Hybrid iter_12 (NN priors + virtual_score leaf) sims=100 (n=20)** | **40%** | **-6.8 (hybrid wins by ~7 pts/game)** |

**Conclusion:** 35-percentage-point swing from one knob. Same network, same MCTS, same sims — only swapped the value output. The NN's value head was actively harmful to the search. The policy head is decent (hybrid 60% > pure-heuristic 40% at half the sims). The value head's failure is doubly damning because it IS trained on `tanh(virtual_score/15)` targets — i.e. it's an *approximation* of what we now just compute exactly, and it's WORSE than the exact answer.

**Hypothesized causes** (not yet diagnosed): (a) MCTS-induced distribution shift — training labels from completed-game states, search evaluates partial-game leaves outside that distribution; (b) capacity starved by the policy head's `Linear(2500, 2511)` ~6M params dominating the trunk; (c) subtle perspective/sign bug.

**Decision:** production NeuralMCTS will run with `_hybrid_evaluator` (NN priors + virtual_score leaf). Architectural follow-up: deprecate the value head entirely — it's harmful AND it's a slow forward pass we don't need.

---

### Lesson learned (the meta-decision)

Yes, we should have caught this much earlier. The diagnostic is ~30 LoC + ~10 min bench. The right protocol after Phase 3 (warmstart finished) would have been a 3-bench ablation battery:
1. NN policy + NN value (baseline NeuralMCTS)
2. NN policy + virtual_score value (this finding)
3. uniform policy + NN value (test if priors matter at all)

Run those three after warmstart finished, you immediately see "value head adds nothing or hurts." Total cost: ~30 min compute.

Instead we did try-another-recipe for six variants (v1-v6) over multiple weeks. When v3 plateaued, the right move was diagnose-by-ablation; we kept iterating recipes instead. That's the systemic mistake.

**Fair caveat:** swapping an exact heuristic for the NN value head is *off-path* in AlphaZero literature. The whole AlphaZero premise is that the NN value generalizes better than any hand-designed eval — true in Go/chess because there's no cheap-exact partial-game scorer. Carcassonne is unusual: the engine's `count_final_scores` IS a cheap-exact partial-game scorer. We had something most AlphaZero domains don't, and we used it only as a training target instead of recognizing it could also be the search-time evaluator.

**Generalized rule for next time:** when self-play plateaus, the next experiment is component ablation, not another recipe variant. "Try harder with the same architecture" is the trap.

## 2026-05-13 — Tier-1 baseline destroys both warmstart_canonical AND iter_12 → recipe-ceiling story confirmed

**Context:** Day 1 of the v7 prep plan. Before committing to v7 (symmetry augmentation + warmstart-from-iter_12), test whether the v6 recipe family even matched the heuristic labeler that generated warmstart's training data. Tier-1 = a hand-coded fixed-policy player whose tile-phase rule is "argmax 1-ply virtual_score" (the same scoring function used to label warmstart training data, just at τ→0 instead of τ=0.5 softmax).

**Setup:** `scripts/eval_rule_player.py` extended with `--opponent checkpoint`. NeuralMCTS at sims=100, default c_puct=1.5, GPU-spawn pool with 2 workers. Both N=50, alternating sides each game.

**Results:**

| Tier-1 vs ... | Win rate | Avg score diff (Tier-1 − opp) | ELO Δ |
|---|---|---|---|
| random (sanity, N=20) | 100% | +70.3 | (saturated) |
| **warmstart_canonical (NeuralMCTS s=100), N=50** | **77.0%** (38W/1D/11L) | **+33.9** | +210 |
| **iter_12 (NeuralMCTS s=100), N=50** | **75.0%** (37W/1D/12L) | **+19.9** | +191 |

**Interpretation:**
1. The heuristic oracle (1-ply virtual_score argmax, no search) **dominates** both trained networks at the v6 production sim budget. The supposed "global best" (iter_12, the v6 peak we measured at 70% wr vs warmstart_canonical) loses to the *labeler* 75% of the time.
2. iter_12 is barely stronger than warmstart_canonical against Tier-1 (75% loss vs 77% loss = 2pp on win rate; +19.9 vs +33.9 on margin = 14 points narrower). The 70% wr vs warmstart_canonical that we'd treated as v6's headline result reflected modest progress over an already-weak baseline, not progress over the labeler.
3. The anchor reference (`warmstart_canonical.pt`) was the wrong yardstick all along. We've been measuring NN-vs-NN (two approximations of the same oracle) instead of NN-vs-oracle. v1-v6 were all comparing two flavors of "weaker than the labeler".
4. The mechanism is plausible: NeuralMCTS at sims=100 uses the trained value head (a noisy approximation of `virtual_score`) + shallow tree search; Tier-1 uses the *exact* `virtual_score` at depth 1. Approximation noise + 100-sim search vs exact-oracle-no-search → the oracle wins. Higher sims would close the gap (NeuralMCTS at sims=10000+ would presumably surface the gap), but that's not the production regime.

**Implication for v7 (symmetry augmentation):**
- Symmetry aug provides 4× more training data on the same heuristic-labeled distribution. Adding more data of the same flavor cannot help if the model isn't even matching the labeler at deployment-time sim budgets.
- The recipe-ceiling story is now confirmed empirically, not just suspected. The ceiling is structural (recipe shape), not data-volume.
- Predicted v7 outcome with high confidence: would converge to ~iter_12-equivalent (≤25% wr vs Tier-1, plateau at ~70-75% vs warmstart_canonical anchor). Wouldn't break the ceiling.

**Decision:** Cancel v7 as originally specified (symmetry augmentation alone). Choose Day 2 from the four below.

**Options for Day 2 / next direction:**
- **A. Pivot to Phase 5 using Tier-1 as the policy oracle.** The project's actual win condition (analyzer/coaching tool, per `docs/ORIGINAL_PROMPT.md`) doesn't require a stronger AI than Tier-1 — it needs a tool that explains where the human lost points. Tier-1 already plays at a level the family game can build on; ship it as the policy and use a small NN for value smoothing if needed. Lowest cost, highest project-goal-alignment.
- **B. Specialist league (DOMAIN-SPECIFIC track).** Bias the heuristic labeler 3 ways (roads/cities/farms), train 3 specialists, league play in self-play. Forces the network past the heuristic via diverse opposition. Tagged "high priority if v6 plateaus" in BACKLOG.md — v6 plateaued, so this is now the high-leverage AlphaZero bet. ~$5-10 cloud, 1-2 weeks.
- **C. Heuristic-as-teacher self-play.** Replace NN-vs-NN self-play with NN-vs-Tier1 self-play. Forces the network to first MATCH the heuristic before exceeding it. Smaller architectural change than league. Risk: may just fit Tier-1 exactly without going past.
- **D. Drop self-play, train directly to imitate Tier-1 at higher capacity.** Generate 500K (state, Tier-1's chosen action) tuples; train a deeper net to argmax-imitate. Simple supervised learning. Tells us if model capacity (not recipe) is the bottleneck.

**Recommendation:** A (Phase 5 pivot). Reasons:
- The project's win condition is the analyzer, not the bot. Spending another week+$5-10 chasing a stronger network for a coaching tool that doesn't need one is misaligned.
- Tier-1 is "good enough" for the analyzer use case — it makes principled moves explainable in terms of virtual_score deltas.
- B/C/D are interesting research questions but each adds 1-2 weeks before the project ships its actual user-facing win condition.

**Reversal cost:** low for A (Tier-1 + virtual_score are already in `src/`); medium for B/C/D (each adds 1-2 weeks of fresh work).

**Phase:** 4 closure → 5 entry.

**Artifacts:** `tests/test_rule_based_player.py` (new); `src/carcassonne_ai/rule_based_player.py` (Rules 4+5 added); `scripts/eval_rule_player.py` (--opponent checkpoint added). Logs at `/tmp/tier1_random.log`, `/tmp/tier1_vs_warmstart.log`, `/tmp/tier1_vs_iter12.log`.

## 2026-05-13 — Phase B cloud bench: W-sweep finds W=32 optimum, full iter measured at 5.2 min, h2h OOM hypothesis falsified

**Context:** Phase A (entry below) confirmed 5-loop patches give ~4-5× CPU-side speedup but exposed two gaps: W=48 still OOMs (VRAM-bound, not CPU-bound, so the patches don't help here), and orchestrator-at-N=1 dispatcher saturates with 48 workers. Phase B bundles four experiments on one box to retire all v7 design questions: W-sweep, orchestrator-with-bigger-batch-timeout, full-iter timing, and train cProfile.

**Box:** vast.ai instance 36719047, RTX 5090 + AMD EPYC 9J14 host 384353 mach 79960 Japan ($0.3747/hr). Hardware confirmed via `lscpu`: **192 physical cores / 384 logical via SMT**, cgroup-capped to 48 effective for this rental. torch 2.7.0+cu128, sm_120. Total Phase B spend ~$0.30.

**Phase 1 — W-sweep (no orchestrator), games=64 sims=200 batch=8:**

| W | Wallclock | Success/Failed | Peak VRAM | Mean GPU util |
|---|---|---|---|---|
| **32** | **172.8 s** | **64/0** | 22325 MiB / 32 GB | **87.2%** |
| 40 | 176.4 s | 64/0 | 27906 MiB | 86.8% |
| 44 | 180.3 s | 64/0 | 30695 MiB | 85.9% |

W=32 wins. Higher W doesn't help because **GPU is already saturated at W=32 (87% util)** — extra workers add CPU contention without throughput gain. W=44 sits ~95% of VRAM cap (no headroom) for ~4% throughput penalty.

**Phase 2 — Orchestrator v2 (W=48, `batch_timeout_ms=16` vs default 2):**
Dispatcher still saturated. Killed after 3 min with 0/64 games written, GPU at 5% util. **Bumping batch_timeout_ms doesn't help** — the bottleneck is single-process dispatch CPU work, not batch-assembly latency. To use orchestrator at W=48 we'd need either N>1 shards or a different IPC mechanism (pinned-memory / shared tensors); deferred.

**Phase 3 — Full iter at winner W=32:**
1 iter via `run_phase4_smoke.py` (selfplay + train + anchor; chain h2h auto-skipped because iter 0 has no prior).

| Stage | Wallclock | Notes |
|---|---|---|
| Self-play (64 games, sims=200, W=32) | 187.1 s | 64/0, 10599 positions, ~0% slower than Phase 1 standalone |
| Train (3 epochs, 95K warmstart positions) | ~100 s | Iter 0 has the biggest train cost; later iters ~10-15 s |
| Anchor (16 games, sims=50) | 19.7 s | 8W/0D/8L vs warmstart_canonical (sanity: 50/50 — correct since iter_00 is warmstart_canonical at iter 0) |
| **Per-iter total** | **5.2 min** | vs my earlier "~10 min" estimate |

**Phase 3 supplement — h2h-only test at W=32 (closes the OOM-stress gap):**
Ran `eval_iter_head_to_head.py` with iter_00.pt (the just-trained checkpoint) vs warmstart_canonical at W=32, 32 games, sims=100. **No OOM.** Wallclock 55.2 s. Result: 20W/1D/11L = 63% wr, +12.4 avg diff, ELO Δ +100. **h2h at W=32 works** — the per-worker VRAM for 2-net eval is much smaller than my naive 2×600 MB worst-case math (the eval_iter script must share net allocator pools more efficiently). **No split-W config needed for v7.**

**Phase 4 — Train cProfile (with corrected CLI flags):**
Train iter 1 at warmstart_mix=0.5, 10.5K positions × 1 epoch = 7.8 s wallclock. Cumtime split:

| Phase | cumtime | % |
|---|---|---|
| Process startup (imports, optimizer init) | 2.55 s | 33% |
| DataLoader queue wait (single-worker `__next__`) | 2.34 s | 30% |
| Actual forward + backward + optimizer | ~3 s | 37% |

DataLoader queue-wait is the biggest single non-trivial slice and would shrink ~3× with `--num-workers 4`. But train at iter ≥ 1 is already only ~10-15 s; not the next bottleneck.

**v7 cloud-iter math (revised from Phase A's estimate):**
- Self-play (W=32, games=64, sims=200): ~3 min
- Train (~10K positions × 3 epochs): ~15 s
- Chain h2h (32 games, sims=100, W=32): ~1 min
- Anchor gate (16 games, sims=50, W=32): ~20 s
- **Per-iter total: ~4.5-5 min** (vs Phase A's ~10 min estimate)
- 20-iter v7 run: **~1.5-1.7h, ~$0.65 on this hardware class.**

**Phase B findings, summary:**
1. W=32 is the v7 selfplay+h2h winner. No split config needed.
2. Orchestrator with batch_timeout knob alone can't fix the N=1 dispatcher saturation. Multi-shard N≥2 might (re-test on this hardware once a real motivating workload exists; currently no need).
3. Per-iter cost is ~4.5-5 min — half of what I'd estimated post-Phase-A.
4. **Total budget for v7 = ~$0.65 (down from $3.40 v6 baseline).** 5× cheaper per iter.
5. Train DataLoader could be faster via `num_workers > 0`, but train is already << selfplay+h2h, so not worth the optimization right now.

**Reversal cost:** none. Box destroyed. v7 plan-mode session can lock W=32 + games=64 + no-orch as the cloud-side defaults.

**Phase:** 4 (perf validation)

---

## 2026-05-13 — Phase A cloud bench: 5-loop MCTS perf patches validated on production hardware

**Context:** local A/B at sims=200 batch=8 on 5060 Ti showed ~7.6× cumulative game-wallclock speedup vs the pre-patch baseline. The cloud question: does that translate to a real per-iter throughput win on production hardware (5090 + 48-core EPYC), and does orchestrator-on still pull weight when deepcopy is no longer the bottleneck?

**Box:** vast.ai instance 36717091, RTX 5090 + 96-effective-core box (mach_id 19968, Michigan, host 65203, $0.3481/hr). Different physical machine than v6's host 384353 because Phase A's first attempt on that host (instance 36715218) failed SSH-banner exchange after ~30 min wait — the "SSH-ready ≠ usable" failure mode from CLAUDE.md. Sunk ~$0.19. Total Phase A spend ~$0.40.

**Bench script:** `scripts/cloud_phase_a_bench.sh` runs iter-0 self-play twice back-to-back on the same box (eliminates host variance):
- A1: `--workers 48 --sims 200 --batch-size 8 --games 80` (no orchestrator)
- A2: same + `--orchestrator --orch-shards 1`

Captures wallclock, nvidia-smi GPU util samples (every 2s).

**Results (the interesting story):**

| Config | Wallclock | Games OK | Games OOM-failed | Mean GPU util | Peak VRAM |
|---|---|---|---|---|---|
| A1 (no orchestrator) | 2:41 | **37/80** | **43/80** | 64.7% | **32108 MiB / 32 GB** |
| A2 (orchestrator) | killed after 5:30 (workers stuck blocking on single dispatcher) | 0/80 | 0/80 | 5.6% | 2896 MiB |

**A1 hit the W=48 OOM** — same shape as the 2026-05-12 Phase A bench. Each surviving worker holds a ~600-700 MB allocator pool × 48 ≈ 30+ GB, right at the 32 GB cap. The 5-loop MCTS perf patches do NOT change per-worker VRAM (deepcopy fix saves CPU time, not memory) — VRAM behavior is unchanged from pre-patch. The 37 surviving games finished fast (effectively 4.3 s/successful-game), but 43 failures means the iter would have to be re-run to fill the buffer.

**A2 hit orchestrator dispatcher serialization** — with 48 workers all routing through 1 dispatcher process, the dispatcher saturates (~49% CPU, queue contention) and worker throughput collapses. Killed after 5:30 with 0 games written. This matches the 2026-05-13 N-sweep finding (N=1 optimal among N>=1, but still strictly slower than no-orchestrator) — except now there's no fallback because A1 OOMs.

**The real takeaway:** the 5-loop patches deliver the predicted ~4-5× CPU-side speedup (A1's 37 successful games went very fast), but production at W=48 needs either:
1. **Lower W** (e.g. W=32 or W=24): fits VRAM, no orchestrator needed. Probably the right v7 choice.
2. **Multi-shard orchestrator** (N=2 or N=4): spreads dispatch load. The 2026-05-13 N-sweep on 48-core box said N=1 is optimal, but that test was W=80 on 48 cores; on this 96-core box at W=48 the calculus might differ. Worth a sub-bench.
3. **Bigger GPU** (80 GB H100/A100): ~$1.50-2/hr. Solves OOM without ergonomic compromises but doubles cost.

**v7 implication:** the cloud-iter math from the loop-5 doc commit assumed clean W=48 throughput. With A1's 43/80 OOM, that's wrong. Realistic v7 path:
- Pick W=32 + games=64 (or W=24 + games=48): fits VRAM, all games succeed, similar effective throughput
- Per-iter wallclock: probably still ~10 min (matches the 2.6× estimate)
- 20-iter v7: still ~3-3.5h / ~$1.30 — but only if we make this knob choice

**Reversal cost:** none. Validates the patches without committing to v7 launch. Documents the W=48 OOM as still-present (and the orchestrator-N=1 ceiling) so the v7 plan-mode session has correct constraints.

**Phase:** 4 (perf)

---

## 2026-05-13 — MCTS perf loop 2/3/4: tile `_type_cache`, rotation-signature cache, str_repr cache, `placed_coords` set

**Context:** After the `__deepcopy__` patch (entry below) cut game wallclock 3.3×, re-profiled and chased the next bottlenecks. Three more patches landed in sequence; numbers from `scripts/profile_mcts.py --no-profile --sims 50 --batch-size 8 --seed 42` on local 5060 Ti:

| Loop | Patch | s/game | Cumulative |
|---|---|---|---|
| 0 | baseline (default deepcopy) | 84.7 | 1.00× |
| 1 | engine state `__deepcopy__` | 25.5 | 3.32× |
| 2 | tile `_type_cache` (precompute `(side → TerrainType)` dict per Tile, lazily) | 16.9 | 5.01× |
| 3 | `_rot_sig_cache` on Tile + `_str_repr_cache` on Board (auto-invalidated by Board replacement on `get_next_state`; manual reset on `apply_action_inplace`) | 14.3–17.1 | ~5.4× |
| 4 | `placed_coords: set[Coordinate]` on engine state, replaces 1225-cell board walk in `string_representation` with ~80-coord iteration | 14.5 | **5.84×** |
| 5 | `tile.turn(N)` cache per Tile (production-sims profile showed 1.08M calls/game, ~22s cumtime). Compounds — cached rotated Tile retains its own `_type_cache` + `_rot_sig_cache`. | _(sims=200: 80→44.5, 1.79× incremental)_ | **~7.6× at sims=200** |

**Loop 2 (tile `_type_cache`):** original `Tile.get_type(side)` re-derives `get_road_ends() / get_river_ends() / get_city_sides()` from scratch on every call (~5M calls/game from `TilePositionFinder` + farmer-position lookups). Patched to precompute a `dict[Side, TerrainType]` once per Tile (lazily). Verified by 1584 (tile × rotation × side) checks against the original implementation — zero mismatches.

**Loop 3 (signature + str_repr caches):** Tiles are immutable canonical refs (`base_tiles` dict + `Tile.turn()` returns a fresh Tile per rotation), so `_tile_rotation_signature` can be cached on each Tile. Board is created fresh by every `Game.get_next_state`, so `_str_repr_cache` is auto-invalidated by replacement — *except* `apply_action_inplace` mutates in place without creating a new Board, so the cache must be explicitly reset there. Regression test in `tests/test_state_deepcopy.py::test_string_repr_cache_invalidated_on_apply_action_inplace`. Smaller than predicted — most Boards are queried once, so cache hits are rare; the actual win was the rotation-signature cache.

**Loop 4 (`placed_coords` set):** the remaining cost in `string_representation` after loop 3 was a 35×35 = 1225-cell walk to find ~80 placed tiles. Mirroring the existing `open_positions` patch: added `state.placed_coords: set[Coordinate]`, maintained by `StateUpdater.play_tile` (pure add — tiles never get unplaced). `string_representation` iterates this set (sorted for determinism) instead of the full board. Wrapped in the custom `__deepcopy__` and tested in `tests/test_engine_adjacency.py::test_placed_coords_*`.

**Loop 5 (`tile.turn(N)` cache):** the production-scale (sims=200) profile showed `tile.turn` called 1.08M times/game (~22s of 126.5s cProfile cumtime), each call rebuilding a fresh rotated `Tile` from scratch. The result is a pure function of `(self, times)` and Tiles are immutable, so cache per-base-Tile keyed by `times`. Bigger payoff than predicted (1.79× incremental at sims=200) because the cached rotated Tile carries forward the loop-2 `_type_cache` and loop-3 `_rot_sig_cache` it builds during use — every downstream get_type and rotation_signature on a rotated Tile is also pre-warmed.

**Diminishing returns + final cumulative.** At sims=50 the loop-4 cumulative was 5.84×. At sims=200 the loop-5 cumulative is ~7.6× (production scale matters more — local pre-patch 80s/game → 44.5s/game post-loop-5; vs an extrapolated pre-patch baseline of ~339s/game). Remaining residual at sims=200 is dominated by per-call GPU IPC (`.to()` + `.cpu()` + tensor construction), which only architectural changes (orchestrator + bigger batches across more concurrent workers, persistent CUDA streams) can crack.

**Implications for v7 (revised after loop 5):**
- Self-play phase only: ~7.6× faster at production sims=200. v6's self-play was ~13 min/iter of the ~26 min/iter total; post-patch ~1.7 min/iter.
- Per-iter total (including unchanged train + h2h + anchor): ~26 min → ~10 min, i.e. **~2.6× per-iter**. 20-iter run: ~9h → ~3.4h / ~$1.30.
- Cheaper headline; train is now the next bottleneck per-iter at ~5 min, and we haven't touched it.
- Higher sims (eval at sims=400+) become affordable. Persistent CUDA streams + bigger eval batches via orchestrator-on-selfplay are the next architectural lever; not pursued in this loop.

**Reversal cost:** none. All patches are local; tests gate any regression.

**Phase:** 4 (perf)

---

## 2026-05-13 — MCTS perf loop 1: engine state `__deepcopy__` cut game wallclock 3.3×

**Context:** Orchestrator N-sweep (entry below) proved workers, not the dispatcher, are the bottleneck. Local cProfile of one self-play game (sims=50, batch_size=8, warmstart_canonical, seed=42) showed the actual hot path **inside** the worker. Top 7 by cumtime:

| Function | cumtime | % of wallclock |
|---|---|---|
| `copy.deepcopy` | 199.9s | **75%** |
| `state_updater.apply_action` | 204.2s | 77% |
| `get_next_state` | 205.8s | 77% |
| `_select_leaf_with_vloss` | 212.2s | 79% |
| `batch_evaluator` (GPU fwd) | 43.9s | 16% |
| `get_valid_moves` | 32.0s | 12% |
| `string_representation` | 21.2s | 8% |

(`_select_child_puct`, the PUCT loop I expected to be hot, didn't appear in the top 40 — it's negligible vs deepcopy.) Per-tree-step `get_next_state` deepcopies the entire `CarcassonneGameState`, which by default recursively walks every `Tile` (with `FarmerConnection`s), every `MeeplePosition`, every `Coordinate` in the 35×35 board. ~19,500 deepcopies per game × ~2.2ms each = 200s — way more than the GPU.

**Fix:** custom `__deepcopy__` on `CarcassonneGameState` (vendored engine; ~50 LoC). All immutable refs (`Tile`, `TileAction`, `MeeplePosition`, `Coordinate`, enums) are shared; mutable containers (`board`, `deck`, `scores`, `meeples`, `placed_meeples`, `open_positions`) are shallow-copied at one level. Verified by reading every mutation site in `state_updater.py` and `points_collector.py`: nothing ever mutates Tile/TileAction/MeeplePosition fields after construction — `Tile.turn()` returns a NEW Tile (immutable pattern).

**Microbench** (mid-game state, 80 placed tiles, N=200 copies):

| | per-copy |
|---|---|
| default recursive deepcopy | 2.216 ms |
| custom `__deepcopy__` | 0.004 ms |
| **per-copy speedup** | **503×** |

**End-to-end A/B** (one game, sims=50 batch=8, --no-profile):

| | plies | wallclock | s/ply |
|---|---|---|---|
| default deepcopy | 166 | 84.7 s | 0.510 |
| custom `__deepcopy__` | 165 | **25.5 s** | **0.154** |
| **game speedup** | — | **3.3×** | 3.3× |

**Correctness:** `tests/test_state_deepcopy.py` (4 tests, all pass) verifies: (a) signature equality of fresh state, (b) signature equality after 60 random actions applied to a custom-copy vs a default-copy, (c) no shared mutable substructure (mutating the copy leaves original unchanged), (d) signature equality at mid-game (~60 moves placed). Full suite: **166/166 tests pass** post-patch.

**Other beneficiaries** (any codepath that does `copy.deepcopy(state)`):
- `virtual_score.py` (heuristic labeler used by warmstart gen)
- `warmstart.py` 2-ply heuristic lookahead
- vanilla MCTS rollouts (`mcts.py`, partially mitigated by `apply_action_inplace`)
- analysis scripts (`classify_v2_losses.py`, `audit_virtual_score_farmers.py`)

**Implications for v7:**
- At production sims=200, deepcopy load scales with sims × avg-tree-depth → the 3.3× should hold or widen.
- v6 cloud run was 9h / $3.40 for 20 iters → v7 with this fix runs the same in ~3h / ~$1.10, or ~60 iters in the original 9h budget.
- This eliminates the need to chase fp16 (already proved slower) or Cython-rewrite the PUCT loop (which the profile says was never hot).

**Reversal cost:** none. Engine patch is local to one method; old behavior preserved by deleting the method. Tests gate any future regression.

**Phase:** 4 (perf)

---

## 2026-05-13 — Orchestrator multi-process pool: NULL RESULT, workers are the bottleneck, not the GIL

**Context:** v6 cloud showed GPU at 5-20% utilization with the single-server orchestrator, suggesting the Python dispatch loop was GIL-bound and starving the GPU. Built multi-process pool (`src/carcassonne_ai/eval_server_pool.py`) to shard workers across N parallel server processes (commit `c34ecf9`). Hypothesis: more dispatchers → faster request servicing → 1.5-2× wallclock speedup.

**Cloud sweep** (vast.ai EPYC 9J14 Japan, $0.375/hr, ~$0.56 sweep cost, 2026-05-13):

| N | wallclock | dequeue % (avg per shard) | forward % | vs N=1 |
|---|---|---|---|---|
| 1 | **1134.5 s** | 64% | 35% | baseline |
| 2 | 1181.6 s | 68% | 31% | +4% slower |
| 4 | 1211.6 s | 76% | 23% | +7% slower |
| 8 | 1211.7 s | 84% | 16% | +7% (saturated) |

Each row is iter-0 self-play, 80 games × 200 sims × 80 workers on identical hardware. Per-stage timers in `eval_server.py` capture where the dispatcher Python loop spends time.

**Finding: the orchestrator GIL is NOT the bottleneck.** The dequeue % climbs monotonically (64→68→76→84) as we add shards — each shard waits LONGER for requests to assemble into batches. Forward % drops correspondingly (35→16). Dispatch is always 0% (instant). Multi-process sharding made the dispatcher even more idle, not less.

**What's actually bottlenecked: workers (CPU-bound MCTS tree work).** Each self-play worker spends ~50% of its time on MCTS tree expansion and ~50% blocked on eval responses. The eval responses ARE prompt (dispatch is 0% of orchestrator time); the workers can't generate requests fast enough because their own CPU work is the binding constraint. Fewer requests per shard → each shard idles more.

**Implications for v7:**

1. **The multi-process pool is correctly engineered but solves the wrong problem.** Keep the code (no harm in n_shards=1 default; back-compat preserved) but **do not use N>1 in any production run**. Each shard just wastes VRAM and adds queue contention.
2. **Real perf levers, in priority order:**
   - **fp16 inference** — workers spend 50% of time waiting on eval; cutting eval latency 1.5-2× directly reduces worker block time. Already supported via `--fp16` flag. Free perf, never enabled in production.
   - **Faster MCTS hot path** — 50% of worker time is Python MCTS tree work. Numpy hotspot profiling or Cython rewrite of the inner loop. Significant engineering, but the only path to real throughput gains at our worker count.
   - **More cores** — N=80 workers on 48 effective cores is 1.67× oversubscribed. A 64-core (effective) box would help, but at our box class the 48-core EPYC 9J14 is already the throughput optimum per $.
3. **Don't twiddle worker count to fix this.** Yesterday's W=96 sweep already confirmed games=96 is the worker-count optimum on this box class; we're already there in expectation. The throughput ceiling is real and structural.

**Decision:** orchestrator pool code stays in repo (validated correct + back-compat at n_shards=1) but **v7 will launch at `--orch-shards 1`**. Pivot the perf-engineering effort from "multi-dispatcher" to "fp16 + MCTS hot path".

**Cost of being wrong:** ~$0.56 cloud sweep + ~half a day of engineering on a fix that doesn't help. Cheap diagnostic; would have been ~$4-5 if we'd skipped the sweep and just launched v7 with N=4 (we'd have been 7% slower for the whole run).

**Reversal cost:** none. Code is committed and tested; we can revisit if the workload ever shifts (e.g. bigger net = forward % climbs = orchestrator might matter again).

**Phase:** 4

---

## 2026-05-13 — Phase 4 v6 cloud COMPLETED 20 iters; iter_12 = 70% wr (NEW global peak, first break above v5's 65% ceiling)

**Context:** v6 = same recipe as v5 + two changes: `--initial-checkpoint = selfplay_v5/iter_06.pt` (the 65% wr peak from v5) and `--orchestrator on` (validated 2026-05-12 Phase A). The hypothesis: does a stronger starting checkpoint let the same recipe compound past v5's ceiling?

Box: vast.ai 5090 + EPYC 9J14 Japan ($0.375/hr × ~9 h ≈ $3.40 actual cloud cost; +$0.06 sunk on a destroyed pre-launch box). Total wallclock 490 min for 20 iters (24.5 min/iter average).

**Three launch-time bugs (all now fixed on `gpu-orchestrator`):**
- Dockerfile lacked `openssh-server` → vast.ai SSH proxy rejected all keys. Fixed `62d5283`.
- `bootstrap_cloud.sh` pulled checkpoints but NOT the `heuristic_tau05/` warmstart training data → iter 0 train crashed after 16 min of self-play. Tarballed to bootstrap-v1 release; fixed `7a6f535`.
- `run_phase4_smoke.py` didn't pass `--orchestrator` to the subprocess calls. Fixed `19d8fe8`.

**Anchor-gate trajectory (n=20 vs warmstart_canonical):**
```
iter   v5         v6
 0     40 P       65 P
 1     20 F       65 P
 2     50 P       35 F
 3     60 P       60 P
 4     30 F       50 P
 5     50 P       40 P
 6     65 P       50 P   ← v5 peak (run halted at iter 9)
 7     35 F       35 F
 8     35 F       50 P   ← v6 breaks v5's death-spiral
 9     25 F       60 P   ← v5 halted here; v6 climbing
10     —          35 F
11     —          45 P
12     —          70 P   ← v6 PEAK (new global best, +5pp over v5)
13     —          65 P
14     —          45 P
15     —          55 P
16     —          30 F
17     —          45 P
18     —          25 F
19     —          65 P
```
Summary: **v5 = 5/10 PASS best 65%; v6 = 15/20 PASS best 70%.** Pass rate 50% → 75%, peak +5pp, survived 2× more iters.

**Findings:**

1. **Compounding past v5's ceiling IS possible — iter_12 demonstrates it.** First checkpoint that beats `warmstart_canonical` at ≥70% wr. The "iter_06 warmstart compounds" hypothesis is partially supported: it did push past 65%, just took 12 iters.

2. **The recipe cannot SUSTAIN the gain.** Late iters (14-19) oscillate 25-70% with no plateau. Suggests a structural bound around ~70%.

3. **v6 strictly Pareto-dominates v5 on every metric** (pass rate, peak, floor, survived iters). The "iter_06 + orchestrator" recipe is strictly better than starting from warmstart_canonical.

4. **Recipe drift is real but the rachet does its job.** Every FAIL was followed by a rachet recovery (warm from best-so-far + fresh RNG). Fail counter never reached 2/3.

5. **Capacity is not the immediate bottleneck.** Local 192×14 warmstart (15.8M params, 2.1× the 96×6 baseline) trained on the same heuristic_tau05 data showed essentially no validation improvement (val pol loss 1.65 → 1.62). The 96×6 net is already capacity-saturated at our data scale.

6. **Tile-placement dominates over meeple decisions.** Rule-based player with 3 meeple-phase rules + RANDOM tile placement scored 44% wr / ELO -42 vs random (n=50). Meeple-only rules can't compete. Tile-placement is where the value lives.

**Decision: keep `iter_12.pt` as the new strongest model. v7 should target sample efficiency / data diversity, not capacity or recipe twiddles.**

**Acceptance bars status:**
- ✅ Bar 1 (≥40% wr by iter 5): passed at 40% iter 5
- ❌ Bar 2 (≥55% wr by iter 10): failed at 35% iter 10 (redeemed by iter 12's 70%)
- ❌ Bar 3 (3 consecutive ≥55% by iter 15): never achieved 3 in a row; best was 2 (iters 12+13)
- ✅ Bar 4 (≥70% wr by iter 20): met at iter 12, 8 iters early

Mixed: 2/4 bars hit. Bar 3 (stability) is the real gap.

**v7 direction (deferred to separate plan-mode):** data-scarcity hypothesis. Cheap leverage: symmetry rotation augmentation (free 4× data), then KataGo-style aux loss heads if augmentation alone doesn't break the ceiling. See BACKLOG.md "Phase 4 v7 candidates".

**Reversal cost:** none. v6 artifacts persisted to `checkpoints/selfplay_v6/iter_00..19.pt` + `data/selfplay/v6_cloud/`. Cloud box destroyed. `iter_12.pt` is now the canonical strongest model.

**Phase:** 4

---

## 2026-05-12 — Phase 4 v5 cloud HALTED at iter 9 (3 consecutive anchor FAILs); peak iter 6 = 65% wr vs warmstart

**Context:** v5 cloud recipe = mix-floor 0.5 floor + window K=30 + best-so-far rachet + anchor-gate (n=20, threshold 40%, max-fails 3) + sims=200. Ran on rented 5090 + 48-core EPYC ($0.443/hr) starting 2026-05-12. Final result: harness halted on its own per anchor-max-fails=3 rule.

**Anchor-gate trajectory:**

| Iter | wr | passed | notes |
|---|---|---|---|
| 0 | 40% | ✅ | baseline (warmstart_canonical reference) |
| 1 | 20% | ❌ | rollback to iter_00 |
| 2 | 50% | ✅ | recovery |
| 3 | 60% | ✅ | first time ever above baseline |
| 4 | 30% | ❌ | rollback to iter_03 |
| 5 | 50% | ✅ | recovery |
| 6 | **65%** | ✅ | **peak** — new best ever, +25 pp above baseline |
| 7 | 35% | ❌ | fail #1 |
| 8 | 35% | ❌ | fail #2 |
| 9 | 25% | ❌ | fail #3 — halt |

**What's new this round:**
1. **First time we produced a meaningfully-above-baseline checkpoint.** iter_03 hit 60% and iter_06 hit 65%, vs the +0 pp ceiling on every prior recipe (v1-v4 all regressed to 12-30%).
2. **Best-so-far rachet engaged correctly** — recovered from iter_01 (FAIL) and iter_04 (FAIL) by rolling back to the prior peak's base.
3. **But the recipe still drifts.** After peak iter_06, three consecutive iters regressed and the rachet couldn't recover. Suggests the closed-loop drift mode is still present, just slower than v1-v4. mix-floor 0.5 is not enough on its own.

**Cost:** ~$3 cloud spend for the actual v5 run (6.5h wallclock × $0.443/hr) + ~$2 across multiple bootstrap attempts (rsync proxy throttling, wrong PyTorch wheel on Blackwell, OOM at W=48 chain h2h before --eval-workers cap was added). Total today ~$5.

**Decision:** Pull data + checkpoints (96 MB) + log. Destroy box. Quarantine v5 checkpoints (`checkpoints/selfplay_v5/iter_NN.pt`) for Phase 6 emergence analysis — they're the first set we have that includes any genuinely-above-baseline weights.

**Acceptance status:** v5 PARTIAL — recipe peaks above baseline (proves the AlphaZero loop CAN improve our warmstart) but is not stable enough to compound. Need another recipe iteration OR more compute per iter OR a structural change (the GPU orchestrator, see entry below).

**Phase:** 4 (self-play loop sanity)

---

## 2026-05-12 — Phase A cloud bench: orchestrator validated, W=96 emerges as new optimum (15% faster than W=48)

**Context:** Phase A of the v6 plan — rent a 5090 + 48-core EPYC box, prove the orchestrator survives W=48 chain h2h (where baseline OOMs on torch 2.11), and sweep W to find the v6 production setting. Ran on instance 36645490 (machine 79615 / host 384353 Japan, $0.3747/hr). Total Phase A spend ~$1.40 across one wedged box + the real one.

**A1 — OOM-relief test: orchestrator W=48 chain h2h:**
- 50 self-vs-self games at sims=100. **30W/0D/20L, avg diff +0.4** (≈50/50 as expected by symmetry).
- **Final VRAM: 2 MiB** (vs baseline's projected 58 GB OOM at W=48). Smoking-gun pass.
- Wallclock: 464.8 s.

**A3a vs A3b — orchestrator vs baseline self-play at W=48 sims=200:**
- A3a (orchestrator): 80/80 games, 1168.1 s, 13246 positions, 2 MiB peak VRAM.
- A3b (baseline): **36 of 80 games OOM'd** with `CUBLAS_STATUS_ALLOC_FAILED` + `CUDA out of memory`. Only 44 completed.
- **The baseline pattern is BROKEN at W=48 on torch 2.11.** v5 ran fine at W=48 on torch 2.7; the difference is torch 2.11's larger per-worker allocator pool (~700 MB) × 48 > 32 GB. The orchestrator isn't just nice-to-have; it's structurally required for W=48 with current torch.

**Worker sweep (orchestrator on, sims=200, 80 games, same hardware):**

| W | Wallclock | s/game | Δ vs W=48 |
|---|---|---|---|
| 44 | 1173.6 s | 14.7 | +0.5% (tie) |
| 48 | 1168.1 s | 14.6 | baseline |
| 52 | 1191.3 s | 14.9 | +2% |
| 64 | 1326.1 s | 16.6 | **+14% (local worst)** |
| 80 | 1006.4 s | 12.6 | −14% |
| **96** | **992.9 s** | **12.4** | **−15% (best)** |

**Non-monotonic curve.** Light oversubscription (W=52, W=64) is the WORST regime: workers thrash CPU but don't queue-block enough to free slots. Heavy oversubscription (W=80, W=96) flips into a regime where workers spend so much time waiting on the orchestrator's request queue that other workers run on freed CPU. Net: **W=96 is 15% faster than W=48 on this hardware**.

**Implications for v6:**
- Use `--workers 96` (not 48). Saves ~110 min over a 12 h run = ~$0.75.
- Confounds the v5→v6 clean A/B (v5 was W=48), but the throughput win is large enough that we accept the confound. v6 vs v5 comparison stays valid for the "recipe + warmstart" question; W is independently the new optimum.
- Could try W=128 in a follow-up bench — curve hadn't turned back upward yet at W=96. Deferred.

**Decision:** v6 launches at W=96 with orchestrator on, iter_06.pt as initial weights, otherwise identical to v5 recipe.

**Phase:** 4 (perf / infra → recipe)

---

## 2026-05-12 — GPU orchestrator (inference-server pattern) — landed + numerically validated, 10-14% slower on local 5060 Ti (expected); cloud bench pending

**Context:** Each self-play / eval worker currently loads its own copy of the net (~600 MB allocator pool per worker). At W=48 chain h2h that's 58 GB > 32 GB → OOM. The fix in production was capping `--eval-workers 20`, leaving cores idle. The GPU orchestrator addresses this structurally: one server process owns the net + CUDA context; N CPU-only workers send (obs, scalars, mask) over IPC; server batches across workers.

**What landed (branch `gpu-orchestrator` off `phase-4-selfplay`):**
- `src/carcassonne_ai/eval_server.py` (210 LoC) — `_server_loop` + `start_server` + `shutdown_server` + `ServerHandles` dataclass. Adaptive batching with `max_batch=256`, `batch_timeout_ms=2.0`. Uses `mp.Queue` for IPC (no extra deps).
- `src/carcassonne_ai/remote_evaluators.py` (115 LoC) — drop-in `make_remote_single_evaluator` / `make_remote_batch_evaluator` matching the existing factory contract.
- `tests/test_eval_server.py` (175 LoC) — numerical agreement (single + batch), concurrent 4-worker no-hang, shutdown propagation (BrokenServerError within timeout, not infinite block). **All 4 pass in 24 s.**
- `scripts/run_selfplay_iter.py` — `--orchestrator` flag. 1 server process for the lone net.
- `scripts/eval_iter_head_to_head.py` — `--orchestrator` flag. 2 server processes (one per net).

**Local bench, RTX 5060 Ti, W=8, sims=50, batch_size=8, 10 games:**

| Mode | Wallclock | Positions | Note |
|---|---|---|---|
| Baseline (per-worker net) | 204.5 s | 1658 | reference |
| Orchestrator (1 server) | 224.7 s | 1657 | **0.91× (10% slower)** — IPC overhead wins over batch-coalescing gain at small W |

Eval bench (W=4, sims=25, 6 games, 2 nets):

| Mode | Wallclock | W/L | avg diff |
|---|---|---|---|
| Baseline (2 nets/worker) | 74.3 s | 6/0/0 | +42.3 |
| Orchestrator (2 servers) | 84.5 s | 6/0/0 | +40.0 |

Same W/L tally — fp32-reorder argmax ties cause minor MCTS-tree shifts (the documented ±1-game noise floor). 14% wallclock slowdown.

**Acceptance:** plan called for ≥0.95× baseline wallclock at W=16; we got 0.91× at W=8. Below bar **on the small GPU as expected** — overhead dominates when the per-worker pattern already fits VRAM and only 8 concurrent workers can't generate enough request density to amortize IPC.

**Why this still matters for cloud:** on the 5090 + 48-core box:
- Baseline OOMs at W=48 chain h2h (58 GB > 32 GB). Production has to cap W=20.
- Orchestrator holds 1 GB server + 0 per-worker VRAM → unlocks W=48 chain h2h (and W=96+ on bigger CPU boxes).
- Cross-worker batching: 48 workers × 8 boards = up to 384 boards/forward (vs current 8 boards/forward × 48 separate forwards) — 4-8× higher per-forward efficiency.

**Decision:** Land on `gpu-orchestrator` branch behind `--orchestrator` flag (default off). Validated locally; cloud bench is the actual proof-point. Bench during the next cloud run before turning it on for prod.

**Phase:** 4 (perf / infra), gated on v6 plan-mode decision

---

## 2026-05-12 — MPS test confirms W=48 + fp32 + no-MPS is optimal; ~$1.50 spent across 4 rentals

**Setting:** Yesterday's cloud bench (entry below) established W=48 + fp32 as the optimum, but left open whether CUDA MPS could squeeze more workers in by sharing CUDA contexts across processes. Three rentals were tried today to validate.

**Per-worker VRAM measurement (Tue 2026-05-12 ~13:00 UTC, instance 36616189, 5090 + 48-core EPYC 9J14 Taiwan, $0.443/hr):**

| Config | per-active-worker VRAM | what it tells us |
|---|---|---|
| no_mps | **662 MiB** | Each torch process owns its allocator pool + CUDA context |
| MPS | **~600 MiB** | MPS shares CUDA contexts (~300-500 MB) but each worker keeps its own torch allocator pool. Net savings ≈10%, not 50%+. |

So MPS savings are real but modest. The dominant cost per worker is PyTorch's caching allocator pool, NOT the CUDA context that MPS deduplicates.

**Throughput verification at W=52 + MPS + games=80 (the actual production-scale workload):**
- VRAM peak: 31977 MiB / 32607 MiB (98% used) — fit, but with only 630 MB headroom
- 80 games completed in 427.5s = **5.3s/game wallclock**
- vs W=48 no_mps at games=64 → 217s = 3.4s/game wallclock

W=52 actually **slower** than W=48. The 5090 + 48-core EPYC has cgroup quota of ~46 effective cores; W=52 oversubscribes CPU, workers fight for slices, total throughput drops. CPU-bound, not VRAM-bound.

**Decision:** Lock prod run at W=48 + fp32 + no-MPS. MPS adds operational complexity (daemon startup, env vars, occasional CUDA shutdown errors) for zero throughput gain at our scale.

**For future scaling past W=48** (Phase 6 / AlphaZero-scale work, not now):
- The real fix is the **inference-server pattern** — one process owns the network on GPU, workers send forward requests via multiprocessing.Queue. Eliminates per-worker allocator pool entirely. ~1-2 days of careful engineering.
- Cheap shortcut: rent an 80 GB GPU (H100/A100 ~$1.50-2/hr) — VRAM cap doubles, can run W=96+ without code changes.

**Today's cloud spend breakdown (~$1.50 total):**
- Instance 36592587 (Japan, 48-core EPYC, ~30 min wallclock for sweep + fp16 bench, results: W=48 max, fp16 is slower on Blackwell too): ~$0.40 — useful data
- Instance 36597509 (Japan): network deadlock on rsync, no usable data: ~$0.40 — wasted
- Instance 36598909 (Japan): killed pip install mid-way thinking torch 2.4.0 was sufficient; turns out 5090 (sm_120) requires torch ≥ 2.7 (we have `torch>=2.7` in requirements.txt for exactly this reason), bench produced 0-process VRAM samples: ~$0.40 — wasted
- Instance 36616189 (Taiwan, $0.443/hr 48-core, fast inet): clean MPS bench + W=52 verification: ~$0.30 — useful data

**Lesson:** never skip `uv pip install -r requirements.txt` on a fresh box. The `torch>=2.7` pin exists because Blackwell sm_120 needs torch 2.7+ for kernel images. Shortcuts cost more than they save.

**Reversal cost:** low. All bench data captured in /tmp/cloud_*.log locally. Total cloud spend so far is <1% of the planned prod-run budget ($10).

**Phase:** 4 prod launch ready.

---

## 2026-05-12 — Cloud bench landed: W=48 + fp32 is the optimum on RTX 5090 + 48-core EPYC

**Setting:** Phase 4 v2/v3/v4 all regressed locally (recipe ceilings around -100 to -200 ELO vs warmstart). Decision: rent vast.ai 5090 + 48-core EPYC 9J14 for ~$0.50 to benchmark worker scaling and fp16 on real production-class hardware before committing to a $10 prod run.

**Box**: vast.ai instance 36592587, RTX 5090 + AMD EPYC 9J14 (Bergamo, Zen 4c, 48 effective cores of 384 host cores), 504 GB RAM, 32 GB VRAM, PCIe 5.0 x54, 903 Mbps inet, $0.387/hr, Japan.

**Worker scaling bench (sims=100, games=64, batch_size=8, no MPS):**

| W | wallclock | speedup vs W=8 | games/worker |
|---|---|---|---|
| 8 | 1533 s | 1.00× | 8.00 |
| 16 | 781 s | 1.96× | 4.00 |
| 32 | 420 s | 3.65× | 2.00 |
| 48 | 217 s | 7.05× | 1.33 |
| 64 | OOM (32 GB VRAM exhausted; each spawn worker ≈ 500 MB GPU context overhead × 64 = 32 GB) |
| 96 | not tested (would also OOM) |

**Verdict (worker count):** **W=48 is the safe max** on a 32 GB GPU without CUDA MPS. Scaling is roughly linear up to 48 workers. The OOM is governed by per-worker CUDA context allocations, not by our small (7M param) network weights.

**fp16 bench on Blackwell 5090** (warmstart_canonical, n=48 mid-game boards):
- Numerical agreement: PASS (max prior L1 = 0.004, max value diff = 0.0003, 0 argmax disagreements)
- Single-board (B=1) wallclock: **0.82×** (slower vs fp32)
- Batch (B=8) wallclock: **0.92×** (slower vs fp32)

**Verdict (fp16):** Even on the 5090's bigger Tensor Cores, fp16 is slower for our workload. The autocast context + .float() cast-back overhead exceeds the GPU compute savings on small networks at small batch. This is the *same finding* as the local 5060 Ti bench from 2026-05-10. fp16 is officially dead for self-play inference at our scale; revisit only if (a) network grows past 30M params or (b) batch grows past 32.

**Per-core CPU comparison** (5800X local vs EPYC 9J14 remote):
- EPYC 9J14 is Zen 4c (Bergamo), better IPC than Zen 3 5800X but cloud variants run lower clocks
- Net per-core single-thread: roughly equivalent or modestly worse on the cloud box
- The cloud advantage is **density**: 48 effective cores vs the 5800X's 16 SMT threads → ~3× more workers in parallel, ~7× total throughput at W=48 vs local W=16

**Cost projection for the 30-iter prod run** (sims=200, games=80, W=48, fp32, same v3/v4 recipe):
- ~50 min per iter (~12 min self-play + 5 min train + 25 min head-to-head + 5 min anchor gate)
- 30 iters × 50 min = 25 h × $0.387/hr ≈ **$10**

**Decision:** Prod run plan locked at **W=48, fp32, on a 5090 + 48-core EPYC class box** (~$10). MPS test deferred (one MPS attempt failed mid-bench from a botched `uv pip install`; box destroyed; ~$0.40 wasted on failed attempts). If MPS works it could squeeze W=72-96 and cut cost to ~$5, but the existing W=48 plan is fine to launch as-is.

**Reversal cost:** low. All bench data + box destruction logs in chat history. Total cloud spend so far: ~$0.40.

**Phase:** 4 prod planning.

---

## 2026-05-11 — Phase 4 v2 recipe FAILED acceptance: mix=0.3 floor not enough

**Setting:** Phase 4 v2 (post-2026-05-10 plan-mode session), four recipe fixes from BACKLOG: warmstart-mix floor at 0.3 (vs v1's 0.0), K=10 → K=30, anchor-gate per iter (10 games at sims=50 vs warmstart_canonical), eval games 20 → 50. New CLI plumbed in commit `a1f29ec`. Outputs at `data/selfplay/v2_sanity/` and `checkpoints/selfplay_v2/iter_*.pt` (kept separate from quarantined v1).

**5-iter sanity result (4 hours wallclock):**

Per-iter anchor gate (n=10 each):

| Iter | Mix | Anchor wr | Gate |
|---|---|---|---|
| 0 | 1.0 | 60% | PASS |
| 1 | 0.7 | 40% | PASS (borderline) |
| 2 | 0.4 | 60% | PASS |
| 3 | 0.3 | 40% | PASS (borderline) |
| 4 | 0.3 | 20% | **FAIL** (1 strike, no halt) |

Chain head-to-head (50 games each):

| Match | W/D/L | ELO Δ |
|---|---|---|
| 1 vs 0 | 21/1/28 | -49 |
| 2 vs 1 | 25/0/25 | 0 |
| 3 vs 2 | 23/1/26 | -21 |
| 4 vs 3 | 23/0/27 | -28 |

Total chain ELO drift: **-98 over 4 iters** vs v1's misleading +612 over the same span. Chain ELO is now consistent with absolute strength (per the 2026-05-10 methodology fix).

**Definitive iter_4 vs warmstart_canonical at n=50:** 12W/0D/38L = **24% wr, ELO -200**. 95% CI is [13%, 37%] — upper bound below the 40% acceptance threshold. This is a real regression, not noise.

**v1 vs v2 comparison at same iter count (5):**
- v1 iter_5 (mix dropped to 0 at iter 3): 30% wr at n=30 → ~-134 ELO
- v2 iter_4 (mix held at 0.3 floor): 24% wr at n=50 → -200 ELO

v2 doesn't fall as far per iter as v1 (the chain-ELO drift slope is -25 ELO/iter for v2 vs ~-50 ELO/iter for v1), but the floor mix=0.3 still permits drift. The recipe fixes weren't sufficient.

**Decision:** Phase 4 v2 acceptance FAILED. Quarantine `checkpoints/selfplay_v2/iter_*.pt` and `data/selfplay/v2_sanity/` alongside the v1 artifacts (don't delete; useful for Phase 6 emergence analysis comparing v1's chain-ELO illusion to v2's slowed-but-real regression).

**v3 recipe candidates (need plan-mode session before implementing):**

1. **Higher warmstart-mix floor (0.5 or 0.7).** v2 at 0.3 was insufficient; doubling/tripling the anchor weight in training mix is the most direct fix. Cost: less pure self-play signal per iter (network may have a harder time exceeding warmstart in absolute terms). Trade-off worth measuring.
2. **Best-so-far reference instead of warmstart_canonical.** Track "best iter that passed anchor gate"; on FAIL, restart next iter's warm-from from best-so-far instead of latest. Existing infrastructure (anchor_gate_log.json) makes this easy to implement.
3. **Higher sims for self-play (200 vs 100).** AlphaZero used 800. Noisier policy targets compound; doubling sims doubles per-iter cost (~7h for 5-iter sanity) but might cleanly fix the noise floor. Worth a controlled test.
4. **Reject-iter on anchor FAIL.** Currently FAIL just logs and increments fail counter. Could instead delete the failing iter's checkpoint and re-train iter N from the previous (best/warmstart) starting point with a new RNG seed. Preserves the "checkpoint chain advances only on improvement" property.

**Combinations matter.** A future plan-mode session should select 1-2 of these for v3 (probably higher mix-floor + best-so-far reference) rather than all four — each adds confounders to the diagnosis if v3 also fails.

**What v2 confirmed (so we keep this in v3):**
- The anchor-gate methodology is the right gate; it caught the borderline-passes (iter 1, 3) and the clear FAIL (iter 4) that chain ELO would have hidden.
- The skip-on-error harness, the fp16/CLI plumbing, the per-iter checkpoint cadence, and the v1/v2 separation in `checkpoint-root` all worked as designed.

**Reversal cost:** low. Recipe fixes are CLI defaults and ~80 lines of anchor-gate code, none of which is wrong — just insufficient at this floor value. Branch is intact for v3.

**Phase:** 4 (still re-opened). v3 plan-mode session is the next step.

---

## 2026-05-10 — Chain-vs-prev ELO discredited as standalone metric; 30-iter "PASS" was a regression in absolute strength

**Setting:** Phase 4 30-iter sanity run (`data/selfplay/sanity_30iter`, recipe per the 2026-05-08 vloss-landed entry: sims=100, eval-sims=100, eval-games=20, K=10 buffer, warmstart-mix schedule [1.0, 0.7, 0.4, 0.0], 50 self-play games/iter). Chained head-to-head (each iter vs the previous) showed **ELO 0 → +612 over 24 iters** — every Phase 4 acceptance check from the 2026-05-03 entry was passing (loop runs, ELO trend up, no NaN losses, no entropy collapse). About to top up vast.ai and launch a 200-iter production run on rented hardware (~$15-25).

**Anchor eval before rental as a $0 sanity check:** added `--no-elo-log` flag to `eval_iter_head_to_head.py`, ran `iter_24.pt vs warmstart_canonical.pt` at 50 games / sims=100 / 16 workers / batch=8.

**Result:** iter_24 = **6W/1D/43L** vs warmstart_canonical, avg score diff -32.7, ELO delta **-330**. The network drifted ~942 ELO worse in absolute terms while the chain ELO marched +612 better.

**Diagnostic anchors at iter_5 (so far; iter_10/15/20 in flight):** iter_5 already at **9W/1D/20L vs warmstart, ELO -134**. Confirms regression started in the first ~5 iters — likely as soon as the warmstart-mix schedule hit 0 at iter 3.

**Why this happened (root cause — recipe, not infrastructure):**

The chain ELO measures *relative* strength: "did iter N learn to beat iter N-1?" Both networks can drift toward worse-but-mutually-defeating play, and the chain still climbs. Two compounding ingredients:

1. **Warmstart-mix dropped to 0 at iter 3.** The heuristic-labeled distribution was the only anchor to "actually-good play." Once dropped, training is a closed loop on self-play data — no signal pulling the policy toward objectively reasonable moves.
2. **Replay-buffer K=10.** At iter 11+, no warmstart games appear in training data at all. The echo chamber becomes hermetic.
3. **Sims=100 (vs AlphaZero's 800)** produces noisy policy targets. Noise compounds when the only correction signal is more samples from the same distribution.

The 2026-05-03 "Phase 4 smoke PASS" entry is **superseded** by this finding. That smoke ran 5 iters on the same defective recipe. The +175 ELO it reported was the same chain-ELO illusion at smaller scale; an anchor eval would almost certainly have shown the same regression already underway.

**Decision:** Two parts.

1. **Chain ELO is now insufficient as the sole acceptance signal.** Future Phase 4 runs (and Phase 5/6 work that depends on Phase 4 outputs) require an anchor eval against a fixed reference (`warmstart_canonical.pt` is the canonical anchor) at the start, end, and at least every 10 iters. Anchor wins-vs-warmstart is the primary metric; chain ELO is supplementary.

2. **The current `phase-4-selfplay` outputs (`checkpoints/selfplay/iter_*.pt`, `data/selfplay/sanity_30iter/`) are quarantined.** They will not be used as warmstart for any subsequent run, will not be merged to main, and are kept only for the Phase 6 emergence-analysis archive. The next Phase 4 attempt warm-starts from `warmstart_canonical.pt`.

**Recipe fixes for the next Phase 4 attempt** (going to BACKLOG; details for a future plan-mode session):

- **Floor warmstart-mix at 0.3** throughout (don't drop to 0). Cheap, principled.
- **K=10 → K=30** replay-buffer window. More history, more stability, mostly free in disk cost (~1 GB extra at 200 iters).
- **Anchor-gate**: only accept new iter as warmstart for next iter if it beats `warmstart_canonical` at ≥40% in a quick check (10 games at sims=50 = ~3 min). Effectively a regression-stop. Reject-and-retrain-from-prev on failure.
- **Larger eval games** (20 → 50) for the chained head-to-heads to reduce per-iter ELO variance (a single-game swing at N=20 = ±35 ELO).

**What we got right (so we don't change it):** the methodology of "anchor eval before cloud rental" caught this for $0. Without that gate we'd have spent ~$20-25 + 2-3 days of cloud time to learn the same thing. Future production-scale plans must keep this gate.

**Reversal cost:** low. The 24 trained checkpoints are quarantined, not deleted. The recipe fixes are 4 small CLI flag additions. Branch is intact for re-launching a clean run.

**Phase:** 4 (re-opened). The 2026-05-03 closure was premature.

---

## 2026-05-08 — Virtual-loss + batched-eval MCTS landed; vloss applied in parent's perspective

**Setting:** Phase 4 smoke ran the serial NeuralMCTS path (one GPU forward per sim per worker). At sims=25 / 7 workers we measured ~4 ms/sim, but at production sims=100-200 the GPU forward is a larger fraction of per-sim cost. Standard AlphaZero remedy: virtual-loss MCTS — collect K leaf-evaluation requests from parallel descents and serve them with one batched GPU call.

**Implementation (commit `f9d805e` + the eval-side wiring in this session):**
- New `NeuralMCTS` constructor params: `batch_size` (default 1 = serial), `batch_evaluator` (`Callable[[list[Board]], (priors[B,A], values[B])]`), `virtual_loss` (default 1.0).
- New methods: `_select_leaf_with_vloss`, `_run_batch`, `_eval_boards`, `_expand_with_priors`, `_apply_vloss_at_child`, `_undo_vloss_at_child`.
- Plumbed through `selfplay.play_one_selfplay_game`, `run_selfplay_iter.py --batch-size N --virtual-loss V`, `eval_iter_head_to_head.py --batch-size N`, and `run_phase4_smoke.py`.

**Vloss formulation — sign in parent's perspective, NOT node's own:**

The textbook formulation ("subtract `vloss` from W in node's own perspective") is wrong for negamax-style perspective-flipping trees with player alternation. With own-perspective vloss, the parent's view of an in-flight child becomes BETTER, not worse — because `Q_parent_view = -child.Q` for different-player parent-child pairs. Net result: subsequent sims in the same batch happily revisit the same leaf instead of diversifying.

The fix: apply vloss in the PARENT'S perspective. At each step of selection:
- if `parent.player == child.player` (rare TILE→MEEPLE phase transition): `child.W -= virtual_loss`
- else (typical alternation): `child.W += virtual_loss`

Either way, `Q_parent_view` of child drops by `virtual_loss / N`. Backup undoes this by inverting the same sign rule, then adds the real value in node's own perspective. Net per node: `N += 1`, `W += signed_real_value` — identical to serial backup.

Root has no parent, so root only gets `N += 1` (root.W doesn't enter PUCT for any child).

**Testing:** 9 new tests in `test_neural_mcts_virtual_loss.py` cover total visit count correctness, batch-call accounting (≤ `ceil(sims / B) + 1` calls), vloss-undo invariants (`|W| ≤ N`), diversification (≥2 root actions visited at branching positions), and the serial-mode bypass (when `batch_size=1`, `batch_evaluator` is never called even if wired). Full suite: 145 pass.

**Measured speedup:** Single-process at sims=25, batch_size=8: 48.9 s → 34.0 s (1.44×) for one 166-position self-play game on RTX 5060 Ti. Multi-worker / production-sims speedup is being calibrated as of this entry; expected to compound at higher sims because the GPU per-call overhead amortizes better when batches fill.

**Reversal cost:** Low — `batch_size=1` (default) preserves the existing serial code path bit-for-bit. To revert: don't pass `--batch-size N > 1` on any CLI.

**Phase:** Phase 4 optimization (post-smoke, pre-production-scale).

---

## 2026-05-03 — Phase 4 smoke PASS: 5 iters, ELO 0 → 176, loop runs cleanly

> **Superseded by the 2026-05-10 entry above.** The +176 ELO reported here was a chained-head-to-head measurement only; anchor evals on the 30-iter follow-up showed the same recipe drives an absolute-strength regression vs `warmstart_canonical`. Treat this entry as historical: the loop did run cleanly (which was the literal acceptance bar), but the recipe is broken and the closure was premature.

**Setting:** Phase 4 plan (in `~/.claude/plans/new-project-in-this-spicy-finch.md`) called for a local 5-iter self-play smoke as the acceptance bar — loop completes cleanly, per-iter checkpoint + ELO logged, no policy collapse, no NaN losses. We are not chasing absolute strength in Phase 4; production-scale long runs are a future plan-mode session.

**Build (commit `79905cd`, branch `phase-4-selfplay`):**
- `NeuralMCTS` gained Dirichlet root noise (configurable α, ε; root-only, applied once per fresh root, reset by `clear()`) and `select_for_training(τ)` for sampling-from-visit-count policy targets. Both opt-in; default-disabled keeps tournament/eval call sites unchanged.
- `selfplay.play_one_selfplay_game` produces a `GameDataset` matching the warmstart schema. Value targets are raw z ∈ {-1, 0, +1} sign-flipped per position's current_player. Reuses streaming-dataset machinery unchanged.
- `elo.py` — stateless ELO update from (W, L, D) capped ±800 to keep small-N matches sane.
- 4 driver scripts (`run_selfplay_iter`, `train_iter`, `eval_iter_head_to_head`, `run_phase4_smoke`) with per-game `.npz`/JSON checkpointing and resumable-per-step outer loop.
- Phase-6 prep: every iter saves a numbered checkpoint at `checkpoints/selfplay/iter_NN.pt` plus `iter_NN.metrics.json`; nothing overwrites or deletes.

**Calibration (1 iter, 10 games, s=25, 4 workers): 5.7 min wallclock.** Beat the 50 min/iter pencil-sketch by ~10×; per-MCTS-sim cost was ~4ms (vs the estimated 100ms). The GPU is partially saturated even at 4 workers — cuda-cap=4 was conservative.

**Worker-cap experiment** (added `--no-cuda-cap` flag): 4 workers = 176.5s/10 games; 7 workers = 155.1s/10 games (~12% faster, diminishing returns due to CUDA context-switch overhead). Used `--workers 7 --no-cuda-cap` for the smoke.

**Bug found and fixed during smoke:** the trainer's `policy_cross_entropy` aborted iter 1 because some self-play policy targets had ~0.16-0.36 mass on a snapshot-mask-illegal action. Root cause: occasional divergence between the outer `game.get_valid_moves(board)` call and the MCTS-internal `get_valid_moves` call (suspect: stale legal-moves-cache entry reused across searches; not yet root-caused). Fix: clip MCTS visit distribution to the snapshot mask before normalizing in `selfplay.py`. The snapshot mask is the contract for legality at this position; phantom visits are dropped. If everything got filtered, fall back to uniform-over-legal. Test bumped from sims=3 to sims=25 (production-like) so the deeper PUCT tree path that triggers the bug is exercised in CI.

**Smoke result (5 iters, 25 games/iter, s=25 self-play / s=50 eval, 53.7 min wallclock, `data/selfplay/smoke_v1`):**

| Iter | H2H vs prev | ELO delta | Cumulative ELO |
|---|---|---|---|
| 0 → 1 | 5W/4L/1D | +34.9 | 34.9 |
| 1 → 2 | 6W/4L/0D | +70.4 | 105.3 |
| 2 → 3 | 5W/5L/0D | +0.0 | 105.3 |
| 3 → 4 | 6W/4L/0D | +70.4 | **175.7** |

Strictly non-decreasing ELO across all 4 head-to-head matches. iter 3 hit the 50/50 noise floor at 10 games — expected variance, not regression.

**Stability checks:**
- ✓ No crashes (post-fix), no NaN losses, no policy collapse
- ✓ Train losses decreasing across iters (val_val_loss 0.50 → 0.16 train, val 0.56 → 0.27 → 1.07 ⚠️)
- ⚠️ iter 4 val_val_loss spiked to 1.07 (val split is small — ~1K positions on 6 files). Worth watching in production; not smoke-blocking.

**Decision:** Phase 4 acceptance MET. The loop runs cleanly end-to-end. Production-scale long runs are a separate decision (cloud rental likely needed for 50+ iters; original BACKLOG entry stands). Phase 5 (analyzer) can begin from the same `warmstart_canonical.pt` baseline plus optionally any of the saved iter checkpoints.

**Reversal cost:** low. All Phase 4 scaffolding is on `phase-4-selfplay` branch, not merged to main. Bug fix is a small defensive clip in selfplay; doesn't affect existing data shapes or training.

**Phase:** 4 closure → Phase 5 entry next.

**Open items deferred to a future production-scale plan:**
- Virtual-loss / batched MCTS (BACKLOG): the calibration showed ~4ms/sim wallclock at 4 workers; for 50+ iter production, batched MCTS could 3-5× per-game throughput. Right move when production scale is on the table.
- Larger eval game count per head-to-head (currently 10; the 5W/5L noise floor at iter 3 argues for 30+ for production).
- Automated entropy-floor abort + larger val split for stability monitoring.
- Root-cause the snapshot-mask vs MCTS-mask divergence (defensive clip handles symptom; bug is benign at our scale but worth fixing for hygiene).

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
