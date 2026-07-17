# Stage-2 flywheel — performance advisory (2026-07-17)

**STATUS: ADVISORY — read-only review before the stage-2 relaunch. Nothing here was changed or launched.**
Scope: GEN / TRAIN / EVAL setup, pre-run experiments, code wins, config critique for
`run_distill_stage2.sh` iters 4-11 (interrupted at iter-4 gen 2026-07-17 09:49 for the batch-1 fix).
Every recommendation is labeled **novel / previously-killed / previously-deferred** against
BACKLOG.md + DECISIONS.md per the standing rule. Numbers cite their source; anything extrapolated says so.

## TL;DR

- **Do not relaunch until the gen batch wiring lands.** The fair-agent batch machinery is in the
  working tree, but `gen_fair_distill.py:214-221` still builds the agent with no
  `batch_size`/`batch_evaluator`, and the driver has no knob — a relaunch today is still batch-1 = the ~66h tax.
- The wall is **client-side serialized SHM round-trips (~7.2 ms/forward, 36dff1d)**, not the GPU:
  during the 11-min iter-4 window the orch forwarder was only **28-30% busy** at 3200-3500 ex/s
  (`logs/orch_it04.log`). Batching at `batch_size=8` (the MAX_K wire cap) has ~3× headroom before
  the forwarder binds → expected **~4.5-5.5h/iter instead of ≥8h** (extrapolated; E1 measures it).
- ~half a day of pre-run measurement (E1-E2) + two piggyback screens (E3-E4) plausibly turns the
  66h plan into **~30-40h** and protects the headline claim from a winner's-curse repeat (t020, CL-057).

---

## 1. High-EV experiments to run FIRST (ranked)

### E1 — Finish the batch wiring, then a 2-3h throughput grid at production knobs (MUST-DO; blocks relaunch)
The relaunch is gated on this anyway. Wire `--batch-size` (default 8) + `make_fair_net_prior_batch_evaluator`
into `gen_fair_distill.py` + `run_distill_stage2.sh`, then run the (already-written, never-run)
`scripts/bench/bench_fair_batch.py` plus a warm-gen grid on LOCAL at production knobs
(W28 orch, k4×688, sighted, real Pool path — `--smoke` skips `_worker_init`, HANDOFF gotcha):

| axis | cells | why |
|---|---|---|
| `batch_size` | 1 / 4 / 8 | 8 = the SHM `MAX_K` wire cap (shm_eval_handles.py + rust shm.rs); >8 chunks into sequential trips, no win |
| `MAX_BATCH` | 16 / 64 | only matters if fwd_busy → ~100%; carc-orch's own README example runs 512 |
| W | 20 / 28 at best cell | gen orch bench 2026-06-30: 24=5.91 g/min ≈ 28=5.80; **36=2.91 craters** (`run_step2_flywheel.sh:111`) |

Rank cells by warm **examples/s** + fwd_busy + GPU power (not util%) + RSS, then **confirm the chosen
config by game-count** — the forward-rate proxy was formally killed as a box-verdict metric 2026-06-16
("examples/s proved UNRELIABLE… reverted to GAME-COUNTS"), and at ~15-20 min/game batched a 2h window
yields enough completed games. **Decides:** the real h/iter (hence the real flywheel ETA),
whether MAX_BATCH/fp16 are worth anything, and the production B and W. Cost: ~2-3h local.
Prediction to falsify: fwd_busy 28-30% today → ~3× client headroom → **~90-100 g/h → ~4.5-5h/iter**
(consistent with stage-1 net-free local W16 = 41.5 s/game throughput, `logs/gen_local_it03.log`, + encode overhead).

### E2 — Batched-search strength sanity (fold into E1 + one n=50-100 screen; ~2-4h)
`batch_size>1` **changes the search** (documented in the in-flight diff: "a batch_size>1 tree does NOT
reproduce the serial tree"). Before generating ~3600 games of training targets with it:
(a) read `bench_fair_batch.py`'s pick-agreement-vs-bs=1 diagnostic (free, already built);
(b) if agreement is not near-ceiling, one paired n=50-100 net@B8 vs net@serial screen.
Expect ~0 (virtual-loss batching is standard AZ practice), but no vloss-strength A/B exists in DECISIONS —
the 2026-05-14 entry validated **batch-fill 3×**, never strength. If B8 costs >~25 elo, fall back B=4.
**Decides:** the candidate's production batch config for gen AND eval. *Champion stays serial/byte-identical —
the diff pins this (bit-exact default; champion-path golden-pick test).*

### E3 — n=400 confirm of the +88.7 screen, on the laptop's idle hours (marginal cost ≈ 0)
HH1: **+88.7 ±35.9, paired z=1.92, n=100** (61W/3D/36L, `hh1_vs_champion/summary.json`) — a screen, not a
verdict, and this project's freshest scar is exactly this shape: **t020 +32.1/z1.68 at n=400 → +3.4 at n=800**
(CL-057, 2026-07-15), after c=3 "+47" and deepteacher "+53.7". Extend to n=400 with fresh decks,
**net side serial batch-1** (search-identical to the screen — transport may be CPU or orch, it doesn't change
moves), on the LAPTOP, which finishes its 150-game side-stream in ~2-3h and then idles ~5h **every iter**.
At ~8-13 g/h serial that's ~25-35h of idle time — lands around iter 9-10, and the running total
(n≈250 → ±~20 elo paired) feeds the iter-6 gate (E5/§5). **Decides:** whether the flywheel's premise
(net-priors ≥ champion at equal sims) survives, and what the post-run claim can say.

### E4 — Half-budget gen probe: k4×344 vs the k4×688 inheritance (~3-4h post-E1; can halve iters 6-11)
Nobody chose 2752 for the net side — it's the champion's equal-time budget (`equal_time_cy.log`:
cy s≈2754 matches h6400). The net at equal sims already beats the champion by **+88.7** ≈ >2 sims-doublings
of headroom on the CL-046 ladder shape (+27.9/+61.4/+81.4/+149.3 @ 800/1600/2752/5504 — stale config,
shape only). So net@k4×**344** is plausibly still ≥ champion@2752 → gen targets still above the anchor
stream's quality at **half the cost**. Test: paired n=100, fair-netprior@k4×344 vs fair-champion@k4×688,
after iter 5 (batched, orch). If it holds, set `SIMS=344` for iters 6+ (env knob, iter-resumable driver)
→ ~2.5-3h/iter. **Cut sims, not k_dets and not `NET_GAMES`**: k4 is a measured inverted-U peak
(**CL-054, 2026-07-13**: k4×688 beats k8 +5.18/z4.17 at fixed budget; k2 worse), and cutting games would
halve the ~64k positions/iter that feed train.
*Boundary note: this is a flat budget cut for gen-target efficiency — NOT the adaptive-compute escalation
scheduler, which is CLOSED FOR STRENGTH (CL-035 / Decision C, 2026-06-29; do not re-suggest that one).*
Per HANDOFF, the data budget is Joshua's call — E4 is the measured basis for it, not a silent cut.

Total pre-spend: ~half a day of local GPU + laptop idle time, against an expected 25-35h of savings on a
66h plan. E1/E2 before relaunch; E3 starts with iter 4; E4 between iters 5 and 6.

---

## 2. Recommended setup per workload

### GEN — net stream (LOCAL)
| knob | value | grounding |
|---|---|---|
| orch | **ON** (SHM, per-iter server, kill per iter) | streams verdict 1.33× W28-vs-off-W14 (`carc-orch/README.md:7-10`, 2026-06-15); net-prior gen is forward-bound so orch-off is not viable |
| W | **28** (E1 checks 20/24) | production gen W28 (`CLUSTER_OPS.md:26-34`); 2026-06-30 bench 24≈28 within noise, 36 craters; RAM ~17GB free @28 |
| batch_size | **8** + virtual_loss 1.0 (E2-gated) | MAX_K=8 wire cap; vloss machinery landed 2026-05-08, "3× batch-fill" validated 2026-05-14 |
| MAX_BATCH / FORWARDERS / timeout | 16 / 4 / 2.0ms, raise MAX_BATCH only per E1 | fwd_busy 28-30% today (`orch_it04.log`) says the server isn't the wall yet |
| sims / k_dets | k4×688 iters 4-5; **k4×344 iters 6+ if E4 passes** | §1 E4 |
| rep/net dims | `--n-ch 81 --n-scalar 42` always | orch defaults 78/12 → **silent corruption** (HANDOFF gotcha) |
| fast paths | USE_CY_LEAF + USE_CY_REPR ON | CY_REPR converts on orch paths: +5.7-7.3% eval (`eval_orch.sh:29`), 1.07× orch gen (DECISIONS 2026-06-17 era) |
| watchdog | **STALL_GEN 15→30 for the relaunch iter** | first net npz lands ~20+ min after TS-export+orch-spinup even batched; at batch-1 the 15-min watchdog would heal-kill a healthy gen 8× then FATAL if the laptop stream ever drops (local-only fallback) |
| build | verify **36dff1d** (monotonic shm-client wait) is in the running tree AND in the laptop bundle | the clock-step ETIMEDOUT would eventually hit a multi-day gen (HANDOFF pt 2); offline git-bundle sync required |

### GEN — champion side-stream (LAPTOP)
Unchanged: net-free, orch-OFF, **W12** (stage-1 proven; W16 risks OOM on 11GB WSL,
`run_step2_flywheel.sh:112`), 150 games ≈ 2-3h/iter. Then the box runs E3 — don't let it idle ~5h/iter.

### TRAIN (LOCAL) — leave it alone
batch 256 / epochs 3 / VLW 1.5 / window 12 / `--stage-local` (mandatory — the 9p mid-epoch wedge,
`train_iter.py:257-260`) / warm-from-prev. Measured **~10 min/iter** (184 s/epoch × 3 at iter_03,
`logs/train_it3.log`) = <4% of an iter. Train is GPU-latency-bound — laptop's faster CPU trained **10%
slower** (0.216 vs 0.196 s/batch, `reference_training_latency_bound`) — so no CPU-shopping, no dataloader
workers, no npz games. Any train tuning here is EV≈0.

### EVAL (post-run + screens)
- **E3 confirm**: laptop, net-side serial (replicates the screen), n→400 fresh decks, exact-k 2.
- **Final deployable eval** (post-iter-11): candidate at its production config (**B8**, the thing you'd ship),
  n=400 paired. LOCAL orch-ON **W40** (benched peak 8.70 g/min, 28=7.16, 48=8.51 — 2026-06-30,
  `run_step2_flywheel.sh:113`; supersedes the older single-ctx W48 row in CLUSTER_OPS), LAPTOP **W12**
  (RAM-benched 5.24 g/min, `:114`; the CLUSTER_OPS W26 figure is the lighter net-vs-heur path — this eval
  carries k4 PIMC trees + a K2 solver per worker, so take the conservative row and watch `free`).
- ORCH=1 for eval is now reasonable post-36dff1d, but certify with a 30-60 min slice first (the HANDOFF
  kept the HHs on CPU nets precisely because the fix was unproven on the eval path).
- exact-k stays ≤2 through the orch; the K≥4 net-on-CPU RAM rule stands (`reference_exact_solver_eval_infra`).

---

## 3. Easy-ish code wins, ranked by (wall-clock bought ÷ risk)

1. **Wire batch_size=8 into the gen emitter + driver** — *previously-built, never-wired* (vloss+batched-eval
   MCTS landed **2026-05-08**; "bigger lever not yet pulled… estimated 2-4×" flagged ~2026-05-12; the same
   batch-1 disease was called out for evals in BACKLOG **2026-05-31**). Fair-agent side is in-flight
   uncommitted; the gap is `gen_fair_distill.py` + `run_distill_stage2.sh` plumbing. Buys ~66h→~40h
   (extrapolated, E1). Risk: low — tests exist, E2 guards strength. **This is the run-blocker.**
2. **fp16 TorchScript export for the orch forward** — *previously-killed-then-refined; its stated revisit
   condition only now comes true.* Full lineage (the "2026-05-28 FP16 embarrassment" makes this the
   canonical re-proposal trap, so cite it precisely): 2026-05-12 5090 "officially dead — B=1 0.82×,
   B=8 0.92×; **revisit only if net >30M params or batch >32**"; DECISIONS **2026-06-01** refined to
   batch-conditional — under the orchestrator at max_batch 256 **+24% Blackwell / +31% Ada**, orch-off −6%;
   BACKLOG:383's deferral reason: "only worth it before a long multi-iter run." The batch>32 condition is
   exactly what an E1 MAX_BATCH=64 win would satisfy, and the multi-iter run is now. Implement at export
   only (wrap forward with internal `.half()` casts; carc-orch src has no fp16 today → zero rust change).
   Do it **only if E1 shows fwd_busy binding AND the MAX_BATCH=64 cell wins**; needs a prior-parity check
   (2026-06-01's own "don't promote unverified" caveat). Risk: low-medium.
3. **Interleave the 4 determinizations in `_pimc_move`** — **novel** (zero hits for it in
   DECISIONS/BACKLOG; not in the in-flight diff; the k_dets loop is strictly sequential,
   `fair_agent.py:509-522`). Round-robin the 4 trees and pool their leaves per request → same
   amortization at 1/4 the per-tree vloss depth, and fills batches at low W (the eval path).
   Buys: mostly search-quality insurance, some eval latency. Risk: medium (cross-instance restructure).
   Build only if E2 shows B8-per-tree distortion costs elo.
4. **Raise the SHM MAX_K wire cap 8→32** — **novel** (compile-time in `shm_eval_handles.py` + rust
   `shm.rs`; no DECISIONS entry). Only pays if E1 shows round-trip count still binding at B8.
   Risk: medium — a coordinated protocol change + rust rebuild on the transport that just had its first
   root-caused bug, days before an unattended multi-day run. Defer to post-run.
5. **Cython the MCTS tree ops (selection/backup)** — *previously-deferred, and partially pre-killed*:
   BACKLOG "MCTS Python hot-path optimization" (2026-05-13-era: workers ~50% tree work, deferral reason
   again "before a long multi-iter run") — but the same 2026-05-13 profiling explicitly ruled the PUCT
   select loop **never-hot** ("didn't appear in the top 40"), and the full flat-array engine rewrite was
   SHELVED 2026-06-12 (caps ~1.3-1.6× per-search, multi-week). Post-batch-fix the CPU plausibly becomes
   the wall, but it's a 1-2 day build vs a run starting now, and the production-path profile must come
   first (`feedback_profile_the_production_path`). Defer; py-spy the batched gen path after E1.
6. **One zero-risk knob**: STALL_GEN 15→30 for the relaunch iter (precedent: the telemetry-gate
   "stall-window < game-time → heal-loops, ~1h/iter wasted" failure, BACKLOG 2026-06-14, still deferred).

---

## 4. What NOT to bother with (the re-treads)

- **fp16 orch-OFF / small-batch** — killed for that regime: −6% (DECISIONS 2026-06-01; the "benched slower
  twice" result was real at small batch). Only the gated big-batch variant in §3.2 is live.
- **More workers / SMT** — gen W36 craters (2.91 g/min, 2026-06-30); SMT gave 0 gain; CPU work sizes at
  W ≈ physical cores.
- **Any train-side lever** — measured 10 min/iter; GPU-latency-bound; laptop 10% slower despite faster CPU.
  Specifically pre-killed: **batch 512** (2026-06-23 calibration: 1.31× wall-clock but +61% under-fit,
  B512−B256 tie, "KEEP BATCH 256"), DataLoader workers, uncompressed npz, symmetry aug (NULL z=−0.38,
  2026-06-10, and it OOM-killed the box at num_workers 12).
- **Train∥gen async overlap** — KILLED 2026-06-30 (PeNS async variant DOA: "work-sharing both stages is
  already the wall-clock optimum on this 2-box cluster"); doubly dead now that train is 10 min/iter.
- **Orch micro-squeezes** — all tried 2026-06-15: **cuDNN benchmark ~7% early but drifts + parity risk →
  REVERTED** (do not re-flip casually — parity is the objection, not throughput); more forwarders (FWD=8)
  capped/neutral; **H2D double-buffer 0.94× worse**. CUDA **MPS** killed 2026-05-12 (~10% VRAM, zero throughput).
- **Classical knob re-tuning for strength** — T3 joint Optuna sweep CLOSED NULL (**CL-057, 2026-07-15**):
  "leaf AND search are now tapped out; the frontier is the distill-champion→net→flywheel bet."
- **Adaptive-compute escalation** (learned OR heuristic) as a strength/scheduling lever — CLOSED
  (**CL-035, 2026-06-29**, 4th instance of the b99c9ed pattern).
- **Gumbel completed-Q selector for speed** (~23% faster) — CLOSED clair-only (**CL-052, 2026-07-13**);
  fair mode is already Q-based selection, inapplicable by construction.
- **Tree reuse for the flywheel teacher/candidate** — *don't flip it mid-run*: cross-move re-rooting was
  ADOPTED for the production champion (**CL-044, 2026-07-08**: +39.3 elo / z=2.81 / n=400 at verified
  equal wall-clock, `reuse_tree: true` in PRODUCTION.yaml) but the **reuse×determinization re-check for
  FAIR mode was left pending**, and the champion side here must stay byte-identical to stage-1's teacher.
  A real post-run candidate for the net agent, not a mid-flywheel change.
- **compact_leaf** (superseded, stays OFF) and **profiling the legacy object-leaf path** (CLAUDE.md 2026-06-09).
- **Xeon re-add** — retired 2026-06-17; out of the cluster.
- **TensorRT / ONNX / torch.compile for the 7M net** — no recorded trial (technically novel) but dominated
  by the already-benched TS+fp16 path on this exact stack; EV too low to spend integration risk now.
- **Laptop-GPU net gen** (second orch on the 4070m) — plausible +20-40% (unverified) but adds a second
  GPU/orch failure surface to an unattended multi-day run on an 8GB box; the laptop's idle hours are worth
  more running E3. Reconsider post-run.

---

## 5. Is the planned config wrong or over-provisioned? (judgement calls)

1. **Relaunching without the batch wiring would be wrong** — it re-buys the whole 66h. The interrupt was
   the right call; E1 is the gate.
2. **k4×688 for the net side is inherited, not chosen — and probably 2× over-provisioned.** It's the
   champion's equal-time budget vs h6400; the net's +88.7 at equal sims implies >2 doublings of headroom.
   Run iters 4-5 at 688 (continuity with stage-1 targets + E4's baseline), then cut to 344 if E4 passes.
   Cut **sims, not games**: 450 games/iter ≈ 64k positions is the training signal; halving games would
   halve that, halving sims doesn't.
3. **8 blind iters is over-committed — add a decision gate after iter 6** (2-3 net-gen iters of probe
   top1/CE + the E3 running total + optionally one n=100 screen). The driver's `done/` markers + `END`
   env make this free. Both directions of the discipline apply: don't run 8 iters on autopilot, and don't
   early-stop on 1-2 flat iters either (`feedback_noisy_plateau_not_a_conclusion`; probe noise floor ~3pp).
4. **Window-12 accumulate dilutes the flywheel late.** By iter 11 the window is ~50% champion-source
   targets (2400 stage-1 + 1200 side-stream vs 3600 net); around iter 7 it's ~70%. The anchor is
   deliberate (anti-drift), but if net search truly exceeds the champion, the window caps the improvement
   it's supposed to measure. Related lever already deferred: replay-window A/B (BACKLOG 2026-06-11).
   Don't change it mid-run un-A/B'd — log it as the first post-run ablation (window 6-8), or pre-agree
   with Joshua a rule like "drop iters 0-1 from the window at iter 8+ if probe divergence is real."
5. **450 games/iter is fine; 150-game side-stream is fine** — the real waste is the laptop's ~5 idle
   h/iter, which E3 absorbs.
6. **MAX_BATCH=16 is likely under-provisioned once clients batch** (the orch's own README example is 512);
   E1's 16-vs-64 cell decides — don't raise it on vibes, fwd_busy is only 28-30% today.
7. **n=100 → n=400 on the headline is non-negotiable** given CL-057 (t020's n=400→800 collapse) happened
   two days before the screen. Run the confirm at the screen's serial config; evaluate the deployable B8
   config separately post-run.
8. **REVIEW_LOG D9 is due**: "failed self-play game holds its claim ~90 min — fix BEFORE the next
   MULTI-ITERATION run." This is that run (multi-day, 2-box `--shared-claim`, 600 claims/iter). At
   minimum verify the stage-B-style self-heal / claims-without-npz cleanup covers the stage-2 driver's
   heal path (`feedback_shared_claim_orphan_stall`), or budget for silent per-iter tail stalls.

*Sources: measured rows above cite file:line or DECISIONS/BACKLOG date / CL-id inline. Extrapolations
(iter-time predictions, fp16 gain transfer to carc-orch, laptop-gen estimate) are labeled as such and are
exactly what E1-E4 exist to replace with measurements.*
