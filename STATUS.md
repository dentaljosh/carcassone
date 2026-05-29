# STATUS — live state of in-flight work

> Update this file whenever the active branch, running task, or immediate next step changes. A new Claude thread reading [CLAUDE.md](CLAUDE.md) → here should be able to take over without missing a beat. Keep this file SHORT — current state only. Historical narrative lives in [DECISIONS.md](DECISIONS.md).

## Right now (2026-05-29) — **🟢 PATH B LAUNCH-READY (HELD). All dev done + committed. Awaiting Joshua's "go" to launch the warmstart→self-play→go/no-go pipeline: 3-box work-stealing, `nice -19`, farm scalars IN (and free).**

**Launch plan (decided 2026-05-29, HOLD until Joshua says go):**
- **Topology:** work-stealing across all 3 boxes (5800X + Xeon + laptop), every worker `nice -n 19`. Same `--shared-claim` mechanism as Run A / deepsearch.
- **Farm scalars: IN** (12-scalar net) — and made **free** (see below). So the go/no-go probe runs with the Step-3 ownership aux heads AND the Step-E farm inputs.
- **Single manual flag:** `generate_warmstart_smoke --include-farm-scalars` + `train_warmstart --include-farm-scalars`. Everything downstream (self-play, train_iter, eval, eval-server) auto-derives the 12-scalar shape from the checkpoint's `n_scalar_features`. Frozen knobs per [docs/PATH_B.md](docs/PATH_B.md) table.
- **DO NOT launch until told.** Full step-by-step recipe in docs/PATH_B.md ("LAUNCH RECIPE").
- **Pre-launch:** ✅ DONE 2026-05-29 — engine/src/scripts/tests propagated to **Xeon** (`/home/doctor/projects/carcassone`, via `code_sync` share + `sync_pathb.sh`) and **laptop** (`/home/pop/carcassone`, direct rsync); `pytest tests/test_farm_index.py` **20/20 on both**. All 3 boxes now run the fixed engine + Path B code. Box choice already made (all 3).

**Today's work (all committed):**
- **Leaf flood-fill speedup** (find_farm + find_city, lazy per-leaf memos): **1.70× leaf / 1.48× end-to-end search**, gated (n=400, 0/0), → `b5ab220`.
- **Step-E farm scalars** (`contested_field_count`, `farm_control_balance`; opt-in): → `a79419f`.
- **Made farm scalars FREE** — shared the farm/city memo across the policy-encode and the leaf-value pass in `make_v25_value_wrapper` (+ batch): **+0.49ms/encode → +0.035ms/leaf (2.2%)**, value-invariant (gate 0/0 + wrapper-value test) → `70e1b62`.
- **Step-E flip-on wired end-to-end** — eval-server / self-play / eval / warmstart-gen all derive the scalar width from the checkpoint → `06b065c`.
- **Run A c=3 re-test: +18.5 elo / 2.1σ at n=1600** — settles the +47 (inflated → corrected to ~+18; c=3 stays default) → logged `results.csv` + `7d57687`.

**Path B progress (see [docs/PATH_B.md](docs/PATH_B.md); TodoWrite mirrors steps). Dev is done; review then launch compute.**
- **Step 1 ✅ + engine bug fixed (validated):** aux-target ownership extractor (`aux_targets.py`) + validation gate (`scripts/validate_aux_targets.py`) + `tests/test_aux_targets.py`. Gate caught a real **engine farm-scoring bug** (non-deterministic, ~2.2% of games, mean 9pt, 0.2% winner-flip; tainted `virtual_score`/v2.7 leaf too). Root cause: `opposite_farmer_side` typo `TRT→BRR` (non-bijective) → `find_farm` start-dependent. **Fixed:** `opposite_farmer_side`→bijection + `find_farm` rewritten as complete CC traversal. **n=2000 reconciliation 0 fails (was 2.2%); start-independence 112→0.** (DECISIONS 2026-05-29.) Joshua green-lit the fix.
  - ⚠️ **Re-sweep flag:** v2.7 leaf changed slightly → cap=12/c_puct=3 optima need re-validation (lands with the fresh warmstart). `find_farm` now **cacheable** (BACKLOG).
- **Step 3 ✅ (the real lever) — ownership aux head wired end-to-end:** `network.forward_train` returns policy+value+ownership; `forward` (inference) **unchanged** (2-tuple, head skipped → zero play-time cost). Masked ownership MSE loss + `--aux-weight` (default 0.15) in `train_iter.py` AND `train_warmstart.py`. `GameDataset.ownership` (N,3,W,W) added to schema/save/load/stream. Labels emitted in **self-play** (rebuilds a meeple-intact terminal state by re-applying the final action with scoring stubbed for that one call — does NOT disturb the leaf eval) and **warmstart** (score-now ownership, consistent with its virtual_score value). Per-cell POV ownership planes (city/road/farm) via `aux_targets.ownership_planes`. **Checkpoint-load shim:** `CarcassonneNet.load_state_dict` tolerates a missing ownership head so pre-Path-B checkpoints still load. New tests + all downstream breakage fixed (streaming/relabel).
- **Step 4 ✅ (low-hanging fruit):** **D13** `tiles_remaining` off-by-one **FIXED** in `features.py` + **regression test** `tests/test_features.py` (deck count correct in BOTH phases over a random game); **D1** ref-tile phase-semantics **resolved as keep+document** (the phase-dependent reference tile is correct). BACKLOG entries marked resolved; REVIEW_LOG D1/D13 loop closed (`852f526`).
- **Step 5 ✅:** warmstart pipeline emits ownership (gen smoke writes valid labels).
- **Step 6 (warmstart half) ✅:** tiny gen→train_warmstart smoke green — 7.4M-param net (incl. aux head) trains, no NaN, ownership loss flows; aux-weight sweep {0.0,0.15,0.5} mechanism verified.
- **Step 2 DEFERRED (needs Joshua's call):** 4/6 proposed domain inputs already exist as scalars; net-new farm inputs (contested/dominant-farms) add **hot-path cost** (`encode_scalars` runs at every MCTS leaf) + a scalar-vs-plane choice → not low-hanging, needs a caching plan + your decision.
- **Tests:** full suite was green except 13 cases the Step-3 arch change touched (checkpoint-load + autograd) — **all 13 fixed and re-run green**; D13/D1-affected files re-run green (68 passed). Recommend one clean full-suite run on an uncontended box during review.

**Remaining = COMPUTE (paused for Joshua):** Step 6 self-play-half smoke (1 short self-play iter→train_iter→anchor-gate, needs `run_selfplay_iter`), then Steps 7 (new-arch warmstart) → 8 (self-play loop, knobs frozen per PATH_B.md) → 9 (go/no-go A/B + value↔outcome corr). **Ask which box before launching.**

**Hygiene runs (PRE-fix engine):**
- **Run B (cap=20 vs cap=12, n=1600): ✅ DONE — TIED at +1.1 elo** (792W/787L/21D). Logged to `experiments/results.csv` (commit 1b57fd5). Settles the cap dispute (Optuna #5 +12.2 / Phase4 −21.7 were n=400 noise). **cap=12 holds.**
- **Run A (c=3 vs c=1.5, n=1600): ✅ DONE 2026-05-29 — +18.5 elo / 2.1σ** (832W/747L/20D, n=1599). RE-VALIDATES and CORRECTS Phase 2b's +47.2: c=3 is a real positive over c=1.5 but ~40% the headline magnitude (the +47 was an inflated estimate / regression-to-mean; agrees with Optuna #17's +13.9/n=100). **c=3 stays the production default; the "+47 free win" framing is retired → ~+18.** Logged to `experiments/results.csv` (`hygiene_c3_vs_c15_n1600`). Pre-fix engine (matches the original c=3 measurement's leaf), iter_B1 both sides, work-stealing 5800X+Xeon+laptop. This settles the last open eval-config re-validation; the strength levers now are the structural/Path-B work, not c_puct.
- **Propagation ✅ 2026-05-29:** the engine fix + all Path B code (engine/src/scripts/tests) is now deployed to **Xeon** (via `code_sync` share + `sync_pathb.sh`) and **laptop** (`/home/pop/carcassone`, direct rsync); `test_farm_index.py` 20/20 on both. The hygiene runs above were PRE-fix; future FIXED-engine runs (Path B) are clear to use all 3 boxes.

## Right now (2026-05-28, late) — **🧭 STRATEGIC REGROUP. Goal changed: GENUINELY SUPERHUMAN (beat the world champ) is now primary — overrides the original prompt's analyzer-as-win-condition (see CLAUDE.md + DECISIONS 2026-05-28). Diagnosis: the last month of eval-config tuning (c_puct/cap/leaf-variant, incl. tonight's Optuna) has been chasing noise the docs already flagged — the "c=3 +47" was a spike (re-screened +13.9). Two real walls for superhuman: (1) no strong reference = blind measurement; (2) hand-crafted leaf caps learned strength. Now standing up measurement infrastructure (experiments/results.csv + discipline) as the prerequisite. Backfill running via subagent.**

### Strategic state (2026-05-28 regroup)
- **Goal is now superhuman**, not the analyzer. Roadmap (not yet committed): (1) **strong reference ladder** [unblocks measurement — Tier-1 is saturated, self-anchored elo lies], (2) **structural leaf/architecture change** [KataGo-style domain planes + aux heads; the real lever past the hand-crafted-leaf ceiling], (3) scale compute + Optuna-over-*recipe*. Eval-config tuning is rounding error against this — stopping it.
- **Measurement refactor underway:** `experiments/results.csv` becomes source of truth (one row per eval, self-describing). Backfill of the 54 scattered evals running as a background subagent (config recovered from dirnames + docs; low-confidence rows flagged not fabricated). Discipline added to CLAUDE.md operating norms + EXPERIMENTS.md rules + memory.
- **Docs updated this regroup:** CLAUDE.md (goal + results discipline), DECISIONS.md (goal-change + measurement-infra entries), EXPERIMENTS.md (goal + n-threshold rules), 2 memory entries. Pending commit.
- **🎯 PRIMARY PLAN: [docs/PATH_B.md](docs/PATH_B.md)** — the step-by-step to the value-bootstrap **go/no-go probe** (KataGo-style aux heads + domain planes → does a learned value beat the v2.7 heuristic leaf?). This is the post-compaction execution doc; the TodoWrite list mirrors its 9 steps. Joshua will launch these step-by-step. Dev is ~a day; the multi-day part is detached compute (warmstart + self-play iters + the A/B). Gates are deterministic + baked into the loop (NaN guard, entropy floor, anchor-gate stop-after-2-flat) — self-play is launch-and-walk-away.
- **Reference ladder** (strong non-saturated opponent for absolute measurement) = parallel/next workstream, needed once Path B Step 9 returns GO.

### Prior tactical state (2026-05-28 evening) — Optuna study
⚠️ **Optuna softened (not refuted) the c=3 "+47."** 16+ trials; best (c=2.0, cap=19, tcc) +24.4 [n=400]. Canonical (c=3, cap=12, v2_7) re-screened **+13.9 at n=100** (trial #17) — ~2σ below Phase 2's +47.2 (n=400), but n=100 too noisy to refute alone. Winners cluster c=1.5–2.0; c=3 does not stand out. **Treat the c=3 production default as UNDER RE-VALIDATION.** Study was left running on 5800X+Xeon; given the regroup it's low-value — fine to let finish or stop.

### What's new (2026-05-28 evening)
- **⚠️ Phase 2's c=3 "+47 free win" looks softer, but is NOT cleanly refuted (sample-size caveat).** Optuna trial #17 ran the EXACT canonical config (c=3.0, cap=12, v2_7) as the NEW side vs the (c=1.5, cap=12) baseline OLD side — same A/B design as Phase 2 — and screened at **+13.9 at n=100**. It did NOT promote (below the +15 threshold), so it stayed at n=100, where 1σ ≈ ±17 elo. **That means +13.9 (n=100) is ~2σ below Phase 2's +47.2 (n=400) — suggestive of regression-to-mean / an inflated original point estimate, but a single n=100 screen can't refute an n=400 result.** What it does do: it removes the *expectation* that c=3 is a standout. To settle it cleanly we'd need a fresh n=400 at (c=3, cap=12) vs (c=1.5, cap=12) — the deferred c×cap disambiguation, now upgraded to "re-validate the headline c=3 claim."
- **Emerging Optuna picture (16 COMPLETE, 3 RUNNING) — the soft signal:** winners cluster at **c=1.5–2.0**, c=3 does not stand out:
  - #9 (c=2.0, cap=19, tile_counting_cont) → **+24.4** [PROMOTED n=400] ← study best
  - #13 (c=5.0, cap=17, v2_7) → +18.3 [PROMOTED] (lone high-c survivor; noisy)
  - #17 (c=3.0, cap=12, v2_7) → +13.9 [screen, Phase-2 reference point]
  - #5 (c=1.5, cap=20, v2_7) → +12.2 [PROMOTED]
  - #8 (c=2.0, cap=11, v2_7) → +12.2 [PROMOTED]
  - high-c probes (#1 c=2.75, #2 c=2.0/cap=8, #10 c=3.75) all negative.
  - **Caveat: most of these are n=100 (1σ ≈ ±17), so the ordering within +12 to +24 is NOT significant.** What IS reasonably clear: nothing is hugely better than baseline, and c=3 is not specially favored.
  - **My earlier "strong c×cap interaction" claim (10:30 entry below) was overstated** — it was built on n=100 noise. Trial #18 (c=3.0, cap=20) is running now to nail it down; trial #17 already softens the story.
- **Laptop REJOINED the cluster (3 boxes again).** Brought to the same physical LAN, mounts the 5800X SMB share over **LAN CIFS** (not tailscale — locking risk gone), runs an Optuna worker (W=24, PID 4743, `--worker-id laptop`, n_trials=3). Trial game-output goes to laptop-local /tmp; only study.db on the share (minimizes wifi traffic). Launcher: `/home/doctor/launch_laptop_optuna.sh`. Laptop LAN IP 192.168.0.221 (wifi); tailnet IP 100.82.188.43 still resolves (tailscale does direct-LAN).
- **2 reference trials enqueued** via `study.enqueue_trial`: (c=3, cap=12) [done → #17, +13.9] and (c=3, cap=20) [running → #18]. These fill the gap TPE didn't sample on its own.
- **Earlier overnight results (still valid):**
  - **sims=800 plane (iter_B1 vs deepsearch_v1 @ c=3, n=400): TIED at −4.3 elo.** Either is fine. Data at `data/laptop_results/b1_vs_ds_s800_n400_c3/`.
  - **deepsearch_v3 anchor-gate (sims=200 c=3 n=100): +17.4 elo** (1σ). Re-train of v1's recipe; marginal, doesn't displace iter_B1.
- **Operational fixes (in this commit):**
  - **Per-worker TPE seed** — `sampler_seed = 42 + crc32(worker_id)` so distributed workers don't sample identical points. Triggered by a 3-trial seed-42 collision overnight.
  - **ssh keepalives** (`-o ServerAliveInterval=60 -o ServerAliveCountMax=5`) on remote launches — the Xeon worker died once at 02:28 ("Broken pipe", killed a 104-min trial) before this.
  - **`nice -n 19`** on all production processes. Standing rule (memory: [[nice-19-for-production]]).

### What's new (2026-05-26 → 2026-05-27)
1. **Phase 3 retest queue DONE.** All 4 jobs verdicted at n=400:
   - **J1 anchor-fraction @ c=3, sims=200: RECOVERED +30.5 elo** (was −1 at c=1.5). Stale-c false-negative now confirmed real.
   - **J2 deepsearch_v2 @ c=3, sims=800: confirmed dead −0.9 elo** (198W/199L/3D, almost exactly even). Plane-match didn't rescue it. Don't chain.
   - **J3 tile_counting leaf @ c=3: confirmed dead −12.2 elo.** Leaf variant is not a lever at any c we've tested.
   - **J4 sims=800 c-probe: c=3 vs c=1.5 → +39.3 elo / 3.4σ.** **c=3 transfers cleanly to sims=800** with a meaningful boost (smaller than sims=200's +47 but in the same ballpark).
2. **Phase 2b sweep DONE earlier — c=3.0 is the peak, sharp.** Full curve at iter_B1, sims=200, n=400 each:
   - c=0.5 → −54.3 (catastrophic) · c=1.0 → −11.3 · c=1.5 → 0 (baseline) · c=2.0 → +5.2 · c=2.5 → +7.8 · **c=3.0 → +47.2** · c=4.0 → +25.2 · c=5.0 → +19.1
3. **Production config bumped (this commit).** `--c-puct` default in `scripts/eval_iter_head_to_head.py` and `scripts/run_selfplay_iter.py` is now **3.0** (was 1.5). Old callers passing `--c-puct 1.5` explicitly still work. **⚠️ Caveat (added 2026-05-28):** Phase 2b + J4 validated c=3 as the *eval-side* exploration constant only (head-to-head play, same checkpoint each side, different c). The self-play-side bump (c_puct used by MCTS *during training data generation*) was made on the hypothesis that c=3 also yields stronger training data — never A/B'd. To validate: train one iter with c=1.5 self-play and one with c=3 self-play from the same warm-from, eval head-to-head.
4. **Cluster: 3 active boxes (Mac parked 2026-05-28).** 5800X + Xeon + Laptop = **~391 g/h** at sims=200 c=3 (2.0× the pre-cluster dual-box rate). Per-box:
   - **Laptop (popos-usb, 14650HX + RTX 4070m, deployed 2026-05-27):** CUDA on Pop!_OS 22.04 + driver 580, peak **W=24 → 196 g/h** at sims=200 c=3. Confirmed clean curve, dip at W=22 only (CPU-scheduling pathology). Sleep masked at systemd level to prevent suspend during cluster runs.
   - **Mac M5 Air — PARKED 2026-05-28.** Sweep complete (W=4→53, W=6→57.5, W=8→56.6, W=10→56.6 g/h, MPS no-orchestrator) — plateaus around W=6 at ~57 g/h, MPS device-bound. Not joining the active cluster for now (marginal contribution + tailnet dependency + battery management). Can resume by ssh'ing in another Optuna worker pointed at the shared study DB.
5. **MPS patch (this commit):** `eval_server.py` and `eval_iter_head_to_head.py` now auto-fall-back CUDA→MPS→CPU. No-op on CUDA boxes; lets Mac participate in orchestrator path (even if no-orch is faster for it).
6. **Optuna wrapper drafted (this commit, `scripts/optuna_eval_search.py`):** TPE over {c_puct, leaf_cap, leaf_variant}, multi-fidelity (n=100 screen → n=400 promote). 20 trials ≈ 15-23h dual-box. NOT YET RUN — runs after Phase 4 docs settle.
7. **BACKLOG audits surfaced 1 "already done":** **NeuralMCTS transposition table is already implemented** (`_nodes: dict[str, _NeuralNode]` + `setdefault` in both serial and batch leaf-selection paths). The 5-20% sim throughput benefit is already baked into our numbers. Removed from Tier 1 task queue; BACKLOG entry now serves as anti-rediscovery.

### Verdict table — what we now know
| lever | best result | conclusion |
|---|---|---|
| **c_puct=3.0 vs 1.5 (sims=200)** | **+18.5 elo / 2.1σ (n=1600, 2026-05-29 Run A)** | **✅ RE-VALIDATED & CORRECTED. The fresh n=1600 (iter_B1 both sides, pre-fix engine) lands +18.5 — REAL positive but ~40% of Phase 2b's +47.2, which was an inflated point estimate (regression to mean; matches Optuna #17's +13.9/n=100). c=3 stays the production default; headline magnitude corrected +47→+18. results.csv `hygiene_c3_vs_c15_n1600`.** |
| **c_puct=3.0 vs 1.5 (sims=800)** | **+39.3 elo / 3.4σ** | **🎯 transfers to sims=800 — eval-side bump justified** |
| c_puct=3.0 in *self-play data generation* | UNTESTED | bumped 2026-05-27 on hypothesis; no A/B run. Train two iters (c=1.5 vs c=3 self-play, same warm-from) → head-to-head to validate. |
| sims=200 → sims=800 (prior) | +200 elo | known free win (different lever) |
| iter_B1 vs iter_01 (sims=200) | +25.2 elo | sims=200-plane global best |
| deepsearch v1 vs iter_01 (sims=800) | +35.8 elo | sims=800-plane global best (pending iter_B1 vs deepsearch @ sims=800 c=3 — running overnight) |
| **anchor-fraction at sims=200 / c=3** | **+30.5 elo / 1.7σ** | **🎯 RECOVERED — was −1 at c=1.5** |
| Option B chain (B2, B4 vs iter_01) | −6, −19 | dead recipe (chain broken from step 1) |
| deepsearch_v2 @ c=3 sims=800 (J2) | −0.9 | confirmed dead even at plane match + peak c |
| tile-counting leaf @ c=3 (J3) | −12.2 | confirmed dead at peak c; leaf variant is not a lever |
| cap=20 vs cap=12 @ c=1.5 (Optuna #5, n=400) | **+12.2** | **🎯 NEW — cap=20 wins at c=1.5 (contradicts Phase 4a at −21.7; possibly baseline shifted or stronger at n=400)** |
| cap=20 vs cap=12 (Phase 4a, c=1.5) | −21.7 | superseded by Optuna #5 at n=400 |
| cap=∞ vs cap=12 (Phase 4b) | −0.9 | null |
| value-blend=0.5 vs pure (Phase 4c) | −18.8 | confirms Option 2 (NN value blend) dead |
| iter_B1 vs deepsearch_v1 @ sims=800 c=3 (n=400, laptop overnight) | −4.3 | **TIED — both checkpoints equivalent at sims=800 c=3 plane** |
| deepsearch_v3 vs iter_01 @ sims=200 c=3 (n=100) | +17.4 | marginal positive, not significant; doesn't displace iter_B1 |
| **(c=2.75, cap=20) vs (c=1.5, cap=12) baseline (Optuna #1)** | **−17.4** | **🚨 c×cap negative interaction — joint effect ≠ sum of marginals** |

### Current global best
- **sims=200 plane**: `checkpoints/v25_retrain_optionB_iter1/iter_00.pt` (iter_B1). With **c=3.0, cap=12** (current production config): ~+72 elo over iter_01 (iter_B1's +25 + c=3 lift ~+47 — additivity ASSUMED, c×cap interaction discovered 2026-05-28 weakens this; verify with (iter_B1 at c=3 cap=12) vs (iter_01 at c=1.5 cap=12) at n=400).
- **sims=800 plane**: iter_B1 ≈ deepsearch_v1 (TIED at sims=800 c=3, n=400, 2026-05-28). Either is fine. Both ~+35-40 elo over iter_01 at c=3.

### Forward queue — the next few days
1. **Optuna study completes ~16:30 today** (5800X + Xeon still running 4 more trials each). Watch trial #8 (c=2.0, cap=11, v2_7 — possibly promoting) and #9 (c=2.0, cap=19, tile_counting_cont). All future trials use per-worker TPE seeds → diverging suggestions.
2. **Disambiguate c×cap interaction (Optuna #5 finding):** explicit (c=3, cap=20) vs (c=3, cap=12) head-to-head at n=400 — needed to know whether the production default (c=3, cap=12) is actually the joint optimum or just one of several local optima. Optuna may probe this naturally before the study ends; if not, run as a targeted eval.
3. **Anchor-fraction chain at c=3** (~25h per iter dual-box) — train iter_AF2 with c=3 self-play from iter_B1; verify +30 lever stacks with iter_B1's +25 + c=3's +47. Highest-EV remaining lever after Optuna lands.
4. **Self-play c_puct A/B** — validates the 2026-05-27 self-play-side bump (eval-side is already verified; self-play-side is hypothesis-only — see DECISIONS 2026-05-28). Train two iters from same warm-from with c=1.5 vs c=3 self-play, head-to-head.
5. **Stale-hyperparam screen** — dirichlet/temp_threshold/virtual_loss at c=3. Lower priority since most are self-play-only (need full retrain per trial, expensive).
6. **Laptop has rejoined cluster post-overnight reboot** — available again at 100.82.188.43 (tailscale IP is permanent across reboots). Can add to Optuna later by ssh'ing in another worker pointed at the shared study DB.

### Pipeline-running scripts (for fresh-thread takeover)
- **In-flight Optuna study (continues until ~16:30):**
  - **5800X worker**: PID 16218, launched by sequencer ~01:49, currently on its 4th trial (#8). Log: `/tmp/optuna_5800x.log`.
  - **Xeon worker**: revived 03:21 after ssh broken-pipe; current ssh PID 50551, xeon-side python PID 288. Log: `/tmp/optuna_xeon_v3.log`.
  - **Study DB**: `/mnt/c/carc-shared/optuna_runs/study.db` (SQLite, both boxes read/write). Study name `eval_time_search_v1`. Per-trial output dirs `trial_NNNN_<workerid>/`.
  - **Inspect**: `python -c "import optuna; s = optuna.load_study(study_name='eval_time_search_v1', storage='sqlite:////mnt/c/carc-shared/optuna_runs/study.db'); print(s.best_trial)"`
- **Laptop overnight (DONE, shut down):** results at `data/laptop_results/b1_vs_ds_s800_n400_c3/` (400 JSONs + elo_log.json, 1.7M). Laptop powered off 2026-05-28 ~10:00; rebooted ~10:14 to test tailscale-after-reboot (verified IP unchanged); can be shut down again safely.
- **`/home/doctor/launch_xeon_eval.sh`** — Xeon launcher for dual-box anchor-gates (mounts CIFS, syncs from `/mnt/carc-shared/code_sync/scripts/`, runs eval with `--shared-claim --claim-host xeon`, `nice -n 19`). Currently UNUSED in tonight's pipeline (5800X-only finish-line) but ready for future dual-box anchor-gates.
- **`/home/doctor/launch_xeon_optuna.sh`** — Xeon launcher for Optuna worker (mounts CIFS, syncs scripts, runs optuna_eval_search.py with `--worker-id xeon`, `nice -n 19`). Pattern: same launcher can be invoked again from any new box (laptop, etc.) to add a worker to the running study.
- **`/home/doctor/laptop_cluster_lib.sh`** — helpers for launching laptop in work-stealing pattern (rsync-from-laptop-to-5800X-CIFS instead of CIFS-over-tailscale chatter). Includes `kill_stale_workers_on_laptop` precondition.
- **`/home/doctor/phase3_continue.sh`** (done) — sequencer that ran J2/J3/J4. Reference for the dual-box pattern.

### Code-sync state (5800X ↔ Xeon ↔ laptop; Mac parked)
- **5800X** on `gpu-orchestrator` HEAD with uncommitted edits: STATUS.md, DECISIONS.md, scripts/optuna_eval_search.py (distributed-worker refactor), scripts/run_selfplay_iter.py (c_puct docstring caveat).
- **Xeon** auto-syncs latest scripts via `/mnt/carc-shared/code_sync/scripts/` on every launcher invocation. After tonight, Xeon repo has the same versions of optuna_eval_search.py / eval_iter_head_to_head.py / run_selfplay_iter.py as 5800X.
- **Laptop (popos-usb)** has GitHub-cloned `gpu-orchestrator` HEAD (pre-this-commit). Has the c_puct=3.0 default + MPS patch. Currently running the iter_B1 vs deepsearch eval — don't disturb until ~06:15.

### Cluster hardware summary
| box | arch | workers | g/h (sims=200) | role |
|---|---|---|---|---|
| 5800X (`/home/doctor/projects/carcassone`) | Zen 3, 8C/16T, RTX 5060 Ti | W=14 | 120 | primary, orchestrator, GPU train |
| Xeon (`ssh xeon`) | Skylake-X, 6C/12T, Quadro RTX 4000 | W=10 | 75 | secondary, shared-claim |
| Laptop popos-usb (`ssh laptop`) | Raptor 14650HX 8P+8E, RTX 4070m | W=24 | 196 | tertiary, tailscale; sleep masked |
| **total cluster** | | | **~391** | **2.0× the pre-cluster dual-box rate** |
| Mac M5 Air — PARKED 2026-05-28 | Apple M5 10-core, MPS | W=6 | 57 | not active; rejoin by ssh'ing a new Optuna worker pointed at the shared study DB |

### Lessons memorialized
- [feedback_no_sigstop_mp_queue](../.claude/projects/-home-doctor-projects-carcassone/memory/feedback_no_sigstop_mp_queue.md) — SIGSTOP on mp.Queue processes breaks them
- [feedback_xeon_ssh_quoting](../.claude/projects/-home-doctor-projects-carcassone/memory/feedback_xeon_ssh_quoting.md) — don't wrap wsl invocation in outer quotes when ssh'ing Xeon
- [feedback_bracket_hyperparams](../.claude/projects/-home-doctor-projects-carcassone/memory/feedback_bracket_hyperparams.md) — sweep with brackets above AND below; never declare an axis settled from one off-baseline sample (the c_puct lesson)

**Production config (post-this-commit):** v2.7 leaf (`CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12`) + **c_puct=3.0** (was 1.5; eval-side validated, self-play-side hypothesis — see DECISIONS 2026-05-28) + sims=200 default, W per box from cluster table above. **All production processes run at `nice -n 19`** (low priority, keeps boxes responsive) — Joshua's standing rule 2026-05-28.

**Zenbook called dead-end** (2026-05-21). Bridge infrastructure stays committed for future deploy. Bridge code: `src/carcassonne_ai/remote_eval_bridge.py` + `src/carcassonne_ai/remote_socket_handles.py` + `scripts/run_selfplay_iter.py` `--serve-on`/`--remote-eval-server` flags + 9 unit tests (pass). Loopback smoke: 12932 evals, 0 failures. Not in production use.

### Lessons memorialized
- [feedback_no_sigstop_mp_queue](../.claude/projects/-home-doctor-projects-carcassone/memory/feedback_no_sigstop_mp_queue.md) — SIGSTOP on mp.Queue processes breaks them
- [feedback_xeon_ssh_quoting](../.claude/projects/-home-doctor-projects-carcassone/memory/feedback_xeon_ssh_quoting.md) — don't wrap wsl invocation in outer quotes when ssh'ing Xeon

**Zenbook called dead-end for now** (2026-05-21). Bridge infrastructure stays in tree as committed code for future deploy. Sequencer v3 (`/home/doctor/maximalist_sequencer_v3.sh`) sits ready but is NOT in use.

**Bridge code (committed, unchanged):** `src/carcassonne_ai/remote_eval_bridge.py` (TCP listener + bridge thread, length-prefixed `np.save(allow_pickle=False)` wire format) + `src/carcassonne_ai/remote_socket_handles.py` (drop-in socket-backed ServerHandles) + `scripts/run_selfplay_iter.py` `--serve-on`/`--remote-eval-server`/`--serve-slots` flags + 9 unit tests (pass on 5800X **and** Zenbook). Loopback smoke: 12932 evals, 0 failures. The earlier "W=10 production" recommendation came from a STUB-eval bench — the only real-GPU bench attempt (today) was junk; no validated production W yet.

---

## Recent (2026-05-20, 16:10) — **retroactive-validation pipeline COMPLETE; 2 of 4 false-negatives recovered.**

Final verdicts (all jobs n=400 at the named sims; full table + decision context in [DECISIONS.md](DECISIONS.md) 2026-05-20 (results)):

| job | n | result | elo Δ | σ vs 50% | verdict |
|---|---|---|---|---|---|
| deepsearch vs iter_01 @ sims=800 | 380 | 208W/169L/3D | **+35.8** | 2.0σ | **recovered FN** (suspected → confirmed) |
| iter_02 vs iter_01 @ sims=200 | 400 | 193W/198L/9D | **−4.3** | 0.25σ below 0 | genuine null |
| iter_B1 vs iter_01 @ sims=200 | 400 | 213W/184L/3D | **+25.2** | 1.5σ | **🎯 NEW recovered FN** |
| iter_01 c=2.0 NEW vs c=1.5 OLD @ sims=200 | 400 | 200W/194L/6D | **+5.2** | 0.3σ | genuine null |

**Global-best updated:**
- **sims=200-plane play** → `checkpoints/v25_retrain_optionB_iter1/iter_00.pt` (iter_B1) replaces iter_01. +25.2 elo, 1.5σ at n=400.
- **sims=800-plane play** → `checkpoints/v25_retrain_deepsearch/iter_00.pt` (deepsearch) replaces iter_01 at that plane. +35.8 elo, 2.0σ at n=380. Pair with the +200 elo sims=200→800 play-time win (sims-ladder, 2026-05-18) for the strongest play config.

**Plateau retraction:** the 2026-05-19 entry's "plain v2.7 plateau across all three strategies" overreached. Only iter_02 (the plain W/L-target recipe) really plateaued. Option B (`score_diff` value targets) gave +25 elo — it is **not** plateaued; chaining Option B forward (iter_B2, iter_B3, ...) is the highest-EV next move.

**Next (queued, multi-day autonomous pipeline while Joshua is away — to be wired):** chain Option B → iter_B2/B3/B4 (each ~9h: self-play + train + n=400 anchor-gate vs iter_B(n-1)); wider c_puct sweep at sims=200 (c=0.5, c=3.0, c=5.0 each n=400 vs iter_B1); cap=20 and cap=∞ smokes. Plan + sequencer to be wired before Joshua's away days.

**Code-review loop — DONE 2026-05-19:** a 4-iteration multi-agent review of all living code applied **14 safe fixes** and logged **16 deferred findings** with rationale → [REVIEW_LOG.md](REVIEW_LOG.md). Action-needed deferrals are parked in [BACKLOG.md](BACKLOG.md): D1/D13 (encoding — next retrain), D16 (leaf-eval — next cap re-sweep), D9 (claim cleanup — before next multi-iter run), D15 (stale-recovery race — accept+document). The running self-play workers are unaffected — edits apply on next launch.

**deepsearch iter — RUNNING on work-stealing (migrated 2026-05-18 from the fixed split):**
- The strength-lever call: deeper-search self-play — retrain with sims=800 self-play (stronger teacher; may un-stick the policy plateau the sims-ladder reframed as a *training*-recipe saturation, not a net+leaf ceiling).
- 1200 games, sims=800, leaf v2_5, orchestrator, batch_size=8, value-target score_diff, warm-from `checkpoints/v25_retrain_iter01/iter_00.pt`.
- **Work-stealing, not a fixed split:** both boxes run the SAME command (`--shared-claim --seed-start 0 --games 1200`) against ONE shared folder; each worker atomically claims (`O_CREAT|O_EXCL` on a `seed_NNNNNN.claim` sidecar) the next unplayed seed. Auto load-balances (faster box does more, no idle-at-end) and every `.npz` lands in one durable place the instant it's produced. 5800X W=14, Xeon W=10.
- **Shared folder** = an SMB share on the 5800X's Windows side (`C:\carc-shared`). 5800X reaches it via drvfs `/mnt/c/carc-shared/deepsearch` (WSL2 NAT can't loopback-mount its own host's share). Xeon reaches the SAME folder via CIFS `/mnt/carc-shared/deepsearch` (`//192.168.0.195/carc-shared`, vers=3.1.1, nobrl, creds `/home/doctor/.carc-smb.creds`).
- **sims=800 per-game cost = 4.81× sims=200** (pre-flight smoke: first game 1478s vs sims=200's 307s) — superlinear; the bigger MCTS tree adds ~20% over a naive 4×.
- **Migration (2026-05-18):** the run started as a fixed seed-split (5800X 0-759, Xeon 760-1199); after work-stealing was built + verified, the in-flight run was migrated — 336 done games consolidated into the shared folder, both boxes relaunched with `--shared-claim`. No recomputation (`path.exists()` fast-path skips done seeds). Verified live: 24 claim files on disk, 14 `5800X` + 10 `xeon`.
- **Xeon launch + detachment:** `/home/doctor/launch_xeon_ws.sh` (on the Xeon) remounts the CIFS share (WSL drops non-fstab mounts on distro teardown) then execs the run — invoked by path over `nohup ssh xeon 'wsl … bash launch_xeon_ws.sh'` on the 5800X (held-open ssh keeps the Xeon's WSL session alive for the run; survives Mac sleep). Relaunch = re-run that ssh; the launcher self-heals the mount, cached seeds skip.
- Logs (both local to the 5800X): 5800X `/tmp/deepsearch_ws_5800x.log`, Xeon `/tmp/deepsearch_ws_xeon.log`. Persistent monitor armed.
- **At completion:** all 1200 `seed_*.npz` are already in `/mnt/c/carc-shared/deepsearch/iter_00/` (no rsync) → `train_iter.py` (warm-from iter_01, warmstart-mix 0.0, 3 epochs — mirrors iter_01/iter_B1) → anchor-gate n=100 @ sims=200 vs iter_01 (`eval_iter_head_to_head.py`). Verdict: did the deeper-search teacher beat iter_01 at equal production search depth.
- **Work-stealing code (committed `1895b02`, branch `gpu-orchestrator`):** `run_selfplay_iter.py` (`--shared-claim`/`--claim-stale-secs`/`--claim-host` + `--seed-start` + claim primitive + gate), `warmstart.py` (per-writer-unique temp filename), new `tests/test_selfplay_claim.py` (8 tests, pass) + `scripts/verify_shared_claim.py` (two-box O_EXCL deploy-gate). Code-reviewed — 3 fixes applied (CIFS-`os.close()`-EIO crash guard, staged-file unlink log, cross-machine temp filename). O_EXCL deploy-gate PASSED on the real drvfs+CIFS mount (701/299 split, all 1000 seeds won exactly once).

**iter_B1 — Option 2 Phase B stage 1 — DONE 2026-05-18 00:29 (533.9 min):**
- 1200-game v2.7 self-play from iter_01 + train + anchor-gate. Checkpoint: `checkpoints/v25_retrain_optionB_iter1/iter_00.pt`. Self-play value targets are `score_diff` (`tanh(margin/15)`), not W/L — the deliverable for the iter_B2 blend.
- **Anchor-gate vs iter_01: 14W/0D/6L, wr=0.70, avg diff +12.6 — PASS.** STATUS expected iter_B1 ≈ iter_02 (flat); it *gained* over iter_01 instead. But n=20 is noisy — treat as "promising, wants n=100 to confirm" before calling it a new global best.
- log `/tmp/optionB_iter1.log`.

**Overnight chain — RESULT (2026-05-18 00:53):** orchestrator ran iter_B1 → n=50 re-smoke → **POORLY**, stopped. **No iter_B2 launched.**
- Re-smoke (iter_B1 blended-leaf λ=0.5 vs plain leaf, n=50): **−15.5 avg diff, 31% wr (15W/1D/34L)** — worse than Phase A's W/L blend (−11.3/46%). **Option 2 (NN value-head blend) is dead** — the score-diff currency fix did not rescue it; the currency hypothesis is refuted.
- Residual diagnostic (`/tmp/residual_structure.log`): NN value head corr **+0.18** with the outcome vs the heuristic's **+0.61**, beaten by the heuristic in every game phase; best static blend cuts prediction MSE only 4% (in-sample-optimised → inflated). The script auto-verdict said "headroom" but that threshold is miscalibrated — honest read: **value-head injection (blend AND residual) is exhausted.** Don't spend 10h on residual.
- **iter_B1 strength — n=20 anchor (70%/+12.6) was a fluke.** n=100 confirm: **49W/0D/51L, +4.6 avg diff, elo −6.9** — iter_B1 ≈ iter_01, no new global best. The plain v2.7 recipe is **plateaued** (iter_00→01 +13.3, 01→02 +0.2, 01→B1 +4.6/49%).
- **Pivot (Branch B) — sims-depth A/B DONE 2026-05-18 ~10:30.** iter_01 @ sims=800 vs iter_01 @ sims=200, same checkpoint both sides (only search depth varies), n=50, plain v2.7 leaf: **38W/0D/12L = 76% wr, +24.9 avg diff, +200 elo.** Decisive (3.7σ) — **the policy is significantly under-searched at the production sims=200; deeper search is a large, under-exploited lever.** Reframes the "plateau": the v2.7 leaf is *not* a hard wall — iter_01→02→B1 flattening was the *training* recipe saturating, not the ceiling of what net+leaf can do with more search at play time. Log `/tmp/sims_ab_800v200.log`. Code: `eval_iter_head_to_head.py` gained an `--old-sims` flag, committed d613e13.
- **Sims ladder — COMPLETE 2026-05-18.** 3 rungs, all n=50, iter_01 both sides: 800 v 200 = **76%**; 800 v 400 = **62%/+10.8/+85 elo**; 1600 v 800 = **52%/+3.1/+14 elo**. **Knee at 800, confirmed both sides** — 400 is not enough (800 wins 62%), 1600 buys nothing over 800. 200→800 ≈ +200 elo. Logs `/tmp/sims_ab_{800v200,800v400,1600v800}.log`.
- **Free win available:** set production/play inference sims 200→800 (~+200 elo, no retrain, ~4× per-move latency — fine for human-paced play). Search is now a closed lever.
- **Next strength lever — Joshua's call (nothing auto-started):** (a) deeper-search self-play — retrain with sims=800 self-play (stronger teacher, may un-stick the policy plateau). Cost confirmed ~4× per-iter compute — 400 was tested, not enough, no 2× shortcut. ~1.5-2 day local on the 5800X; the Xeon (Quadro RTX 4000, WSL CUDA OK) could add ~1.4-1.6× throughput via a seed-range split once deployed. (b) leaf-eval redesign — the v2.7 heuristic is the other ceiling; bigger project.
- **Still open:** human benchmark (the documented superhuman blocker) — deferred until Joshua can play. Other harder levers: heuristic-leaf redesign, net capacity — see EXPERIMENTS.md.
- Artefacts (one-off, in `/tmp`): `optionB_overnight.sh`, `optionB_iter1_resmoke*.sh`, `residual_structure.py`, logs. Not committed.

**Option 2 (NN value-head blend) — why a 2-stage Phase B:** Phase A wired the leaf↔value-head blend — `LeafConfig.value_blend`, the evaluators, the eval_server `compute_value` path, `--value-target score_diff` (committed eb42c25). The λ=0.5 fixed-checkpoint smoke blended iter_01's *W/L*-trained value head and was mildly harmful (46% wr, −11.3 avg diff) — a currency mismatch with the graded score-diff leaf. So Phase B splits: iter_B1 mints a score-diff value head; iter_B2 is the real blended co-improvement test.

**Self-play perf optimization — parked (full rationale: DECISIONS.md 2026-05-17):**
- **Shipped** (`gpu-orchestrator`, 080fea7): hash-cache the engine value objects + precompute `FarmerSide.get_side` → ~20-24% faster leaf eval (cProfile). Live in iter_B1.
- **Option A** (memoize the find_* flood-fills) and **Option B** (incremental union-find) were **parked** here because `find_farm` was start-dependent. **⚡ SUPERSEDED 2026-05-29:** the farmer-adjacency fix made `find_farm` start-independent, and the **lazy per-leaf farm memo** (above / DECISIONS 2026-05-29) now realizes the find_farm half at **~1.2-1.3×** — the better-shaped version of "Option B" for this functional-MCTS architecture (per-leaf, not incremental-across-tree). The find_road half (Option A) is still verified-correct on branch `leaf-memoization` (3db30f1, unmerged) but only ~6%. The find_city/find_cities half (~31% of the leaf) is now ALSO done via the same lazy memo (2026-05-29, combined 1.70× leaf / 1.48× search).

**Production config:** v2.7 leaf (`CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12`) + c_puct=1.5 + sims=200, W=14 on the 5800X.

## Active branch

`gpu-orchestrator` — ahead of `origin/gpu-orchestrator` by 8. The v2.7-leaf retrain line + GPU orchestrator + Option-2 blend wiring live here. Single worktree (`carcassone`) — side worktrees removed 2026-05-18. Two unmerged side branches (no worktrees, reachable from the main repo): `leaf-memoization` (3db30f1 — parked find_city/road memo, ~6%, not worth merge-risk) and `play-vs-mcts` (04e4330 — stale human-vs-AI play UI, 93 commits behind, needs a forward-port before it runs). No merge to `phase-4-selfplay`/`main` pending.

## Second machine (Xeon) — deployed 2026-05-18

Xeon W-2135 (192.168.0.110, `ssh xeon` → WSL Ubuntu-24.04). Repo rsync'd, venv built (torch 2.11.0+cu128, CUDA OK on the Quadro RTX 4000). **Deployed + benched 2026-05-18 — ready to take a self-play shard.** Worker bench: engine-sim peak W≈10. Self-play smoke DONE — path validated end-to-end (orchestrator + Quadro eval-server + v2.7 leaf, 28 games across both boxes, 0 failures). Self-play throughput **~0.6× the 5800X** (single sims=200 game: 5800X ~307s, Xeon ~375s; optimal W=10 vs 14) → **combined ~1.6×**. GPU not the bottleneck on either box (eval-server 70%+ idle). **WSL gotcha:** detached processes die when the ssh/wsl session closes — hold the ssh session open for the run, or use `systemd-run` for a multi-day run. Full Xeon details in CLAUDE.md.

## Cloud note

vast.ai's docker-pull infra failed across 7 boxes on 2026-05-15 (all images, all regions, "Verifying Checksum" stalls) — iter_01/iter_02 ran locally instead ($0). If cloud is needed again, evaluate **RunPod Secure Cloud** (pre-cached templates sidestep the cold-pull stall). cloud helper scripts: `scripts/cloud_bootstrap.sh`, `cloud_pull_destroy.sh`, `cloud_retrain_watchdog.sh`.

## Recent history (full detail in DECISIONS.md)

- **2026-05-14** — diagnosed v1-v6 failure: the NN value head was the broken leaf eval. Pivoted to hand-crafted `virtual_score` leaf (v1 → v2 → v2.5).
- **2026-05-15** — v2.5 dedup bug fix + cap/P re-sweep → v2.7 (`cap=12`, drop-3-open); cloud-retrained iter_00 (+21pp over warmstart). v3 leaf cap tuning = n=20 noise (v2.7 holds). PUCT c sweep: low c catastrophic, c=1.5 default holds. W-bench: W=14 optimum for v2.7 recipe.
- **2026-05-16** — iter_01 retrain confirmed (+13.3, new global best). Strategy lit-review parked in BACKLOG. Docs hygiene + checkpoint cleanup (v1-v6 checkpoints removed, 2.7G→563M; `iter_12.pt` kept as `checkpoints/v6_iter12.pt`).
- **2026-05-17** — iter_02 flattened (+0.2 — policy saturated against the fixed leaf). Closure-P leaf refinement = null (pooled 47.5%, n=200) → pivot to Option 2 (NN value-head blend). Phase A wired (eb42c25); W/L-blend smoke mildly harmful → 2-stage Phase B, iter_B1 launched. Self-play hot path profiled + optimized (hash-cache + get_side, ~20-24%, 080fea7); deeper memoization (Options A/B) parked — find_farm is start-dependent.
- **2026-05-19 → 2026-05-20 (overnight)** — 4-iter multi-agent review → 14 fixes (F1–F14) + 16 deferred; see [REVIEW_LOG.md](REVIEW_LOG.md) / [BACKLOG.md](BACKLOG.md). **Deepsearch retrain anchor-gate**: sims=200 plane FAILED (45W/0D/55L, −34.9 elo), sims=800 matched plane AMBIGUOUS (52W/1D/47L, +17.4 elo, 0.5σ — clean sign flip from the sims=200 reading). Triggered a meta-audit: realized matched-strength comparisons at n=100 have ~50-60% power against +30 elo edges → project has been systematically false-negative-prone. **Wired up 4-job autonomous re-test sequencer** (deepsearch n=400 sims=800, iter_02 n=400 sims=200, iter_B1 n=400 sims=200, PUCT c=2.0-vs-c=1.5 n=400 sims=200), running overnight. **Infra extracted in the process:** new `src/carcassonne_ai/claim.py` shared module (refactored out of `run_selfplay_iter.py`); `eval_iter_head_to_head.py` gained `--shared-claim`/`--claim-stale-secs`/`--claim-host` (work-stealing + crash-tolerance for evals) and `--new-c-puct`/`--old-c-puct` (per-side PUCT for A/B testing exploration constants with the same checkpoint both sides). 12 tests green; backwards-compat preserved for all existing call sites.
- **2026-05-20 (results)** — pipeline COMPLETE. **2 of 4 false-negatives recovered:** deepsearch confirmed at +35.8 elo / 2σ (sims=800 plane); iter_B1 newly recovered at +25.2 elo / 1.5σ (sims=200 plane). iter_02 (−4.3 elo) and PUCT c=2.0 (+5.2 elo) confirmed genuine nulls. **iter_B1 is the new sims=200-plane global-best**, replacing iter_01. The "plain v2.7 plateau across all strategies" claim is retracted — only the W/L-target recipe (iter_02) plateaued; the score-diff-target recipe (Option B) is a +25 elo lever not yet chained. Highest-EV next move: chain Option B → B2/B3/B4. Full table + audit of remaining false-negative reservoirs in [DECISIONS.md](DECISIONS.md) 2026-05-20 (results).

## Key contact files for a fresh thread

1. [CLAUDE.md](CLAUDE.md) — project goal, scope, operating norms
2. [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md) — verbatim spec
3. [DECISIONS.md](DECISIONS.md) — every non-trivial decision + why; supersedes the original prompt
4. [EXPERIMENTS.md](EXPERIMENTS.md) — open ablation roadmap + findings ledger
5. [BACKLOG.md](BACKLOG.md) — deferred ideas (don't action without Joshua's OK)
6. This file (STATUS.md) — what's running, what's next

## Hooks active in this environment

- `~/.claude/hooks/idle_check_with_bg_tasks.sh` — Stop hook. Detects active bg tasks; if elapsed >5min, instructs Claude to actively check status (`ps`, tail output) rather than idle. Registered in `~/.claude/settings.json`.
