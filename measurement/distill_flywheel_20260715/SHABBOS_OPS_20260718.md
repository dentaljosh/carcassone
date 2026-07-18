# SHABBOS AUTONOMOUS OPS — 2026-07-17 ~19:20 → 2026-07-18 ~20:20 (25h)

**Authorization (Joshua, 2026-07-17 ~19:15, verbatim intent):** signing off for Shabbos;
Claude is authorized to operate the two boxes (local 5900XT + laptop) unattended.
**Priority: train as many flywheel iters as possible in 25h.** Also wanted: eval every
3-4 iters (cheap eval = vs **rodv2 iter_02**); test whether eval can run during gen
(maybe pause during train); quick laptop gen W-sweep when the confirm frees it, then
join laptop to the cluster. **Check in ~hourly** — last Shabbos a run crashed and the
session waited on a notification that never came; active periodic checks, not passive.
(Xeon is RETIRED — do not use.)

## Live state at handoff (2026-07-17 19:20)

- **Flywheel** (local): driver `run_distill_stage2.sh` pid 2010969, **iter_05 gen**
  (36/300 at 19:16), W20/f4 sims200 k4 net_seed=700550000, orch shm `distill_stage2`
  (pid ~2047271, model iter_04.ts.pt). ~1.5-2h/iter → expect roughly iters 5→16 in 25h.
  Log: `measurement/distill_flywheel_20260715/stage2_sims200.log`. END=16.
- **Concurrency test RUNNING**: eval iter_03 vs rodv2_iter02, OW=8 GPU (own orchs
  `fairnvnCDoctor/ODoctor`), launched **epoch 1784330195** (19:16:35). n=100 paired
  sims200 kd2 k2, out `/mnt/c/carc-shared/distill_flywheel_sighted_20260716/eval_iter03_vs_rodv2iter02_gpu/`
  (seed*_a*.json ×100 = done). Log: `measurement/distill_flywheel_20260715/eval_iter03_vs_rodv2iter02_gpu.log`.
  - Gen-rate samplers (scratchpad): `gen_timeseries.csv` (baseline, ended ~19:36) +
    `gen_timeseries_b.csv` (during, 40 min from 19:17). Analyze:
    `python3 <scratchpad>/analyze_gen_timeseries.py <combined csv> 1784330195 180`
    (merge: header + data rows of both files). Verdict: >-8% = NO TANK.
- **Laptop**: confirm eval `fair_net_vs_net_orch.sh` (exact-k2 sims688 n=200 paired,
  ~127/200 at 18:33, ~144s/game) → **ETA ~21:00-21:30**. Out: `confirm_n200_laptop`
  (find under laptop share `/mnt/carc-shared/...`; seed*.json). This is the **goal-1
  n=200 confirm** — summarize when done + record in results.csv.
- **Fixes landed this evening**: `2903a6c` (eval_fair_puct 78/12 farm-scalar opponent,
  parity bit-exact), `40a3acd` (fair_net_vs_net_orch pkill scoped to fairnvn*, safe
  next to gen orch — VERIFIED live). `42cc336` (Xeon retired banner).

## ⚠️ TOKEN BUDGET (Joshua, pre-signoff): survival > richness

Premium (fable-tier) tokens are constrained; if the session runs out mid-Shabbos the
loop dies silently. Rules: (1) every Agent spawn passes an explicit `model: "opus"`
override; (2) main-loop turns stay LEAN — terse CHECKLOG lines, no big whole-file
Reads, delegate noisy multi-step checks to one opus subagent that returns a compact
status; (3) at any sign of usage pressure (errors, warnings), stretch the wakeup
interval to ~2h and strip check-ins to bare health checks + heal-if-dead only. A
thin loop that survives 25h beats a rich one that dies at hour 10.

## The hourly loop (each wakeup)

1. **Flywheel health**: `pgrep -f 'run_distill_[s]tage2'` + `pgrep -af 'carc-[o]rch.*distill_stage2'`
   + tail `stage2_sims200.log` + npz count of the active iter. Driver has its own
   stall-healer; only intervene if the DRIVER itself is dead (see contingencies).
2. **Iter progress ledger**: note iter N + npz/300 (or "train") in the CHECKLOG below.
3. **Eval slot** (see cadence): if a scheduled eval's iter ckpt exists and no eval is
   running and the concurrency verdict allows it → launch (template below).
4. **Laptop**: while confirm runs → hands off. When done (200 json or process gone) →
   execute LAPTOP JOIN playbook below.
5. **Local box safety**: loadavg <28, RAM `free -g` available >6G, GPU mem <14G. The
   box has a history of dirty reboots under sustained load — if the whole session is
   fresh (WSL restarted), see contingency C3.
6. Commit any results/doc updates. Re-schedule next wakeup (~60 min; sooner if an event
   is imminent, e.g. eval analysis window or laptop ETA).

## Eval cadence (Joshua: every 3-4 iters, vs rodv2_iter02)

Evals done/planned (n=100 paired sims200 kd2 k2, OW=8, out-subdir pattern
`eval_iterNN_vs_rodv2iter02_gpu`): **iter_03 RUNNING** (the concurrency test itself) →
next at **iter_07**, **iter_11**, **iter_15 or 16** (whichever exists when slot opens).
- Template (run from repo root; CAND is the iter's ckpt):
  `CAND_CKPT=/mnt/c/carc-shared/distill_flywheel_sighted_20260716/ckpt/iter_NN.pt OPP_CKPT=/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt OW=8 setsid nice -n 19 bash scripts/classical_search/fair_net_vs_net_orch.sh --exact-k 2 --k-dets 2 --sims 200 --n 100 --paired --seed-start 13000000000 --out-root /mnt/c/carc-shared/distill_flywheel_sighted_20260716 --out-subdir eval_iterNN_vs_rodv2iter02_gpu --shared-claim --no-results-csv </dev/null > measurement/distill_flywheel_20260715/eval_iterNN_vs_rodv2iter02_gpu.log 2>&1 &`
- **Concurrency VERDICT (measured 19:54): TANKED at W8-as-launched — but confounded
  by thread-thrash.** Gen 3.11→1.51 npz/min (−52%); load 17→**70**/32; and the eval
  itself crawled (3/100 games in 38 min — useless even standalone). Root-cause
  hypothesis: the wrapper sets no OMP/MKL pinning → 8 client workers × unpinned
  BLAS/torch thread pools = classic torch-thread thrash (memory
  reference_desktop_friendly_selfplay: BOTH env vars needed). Eval KILLED 19:57
  (clean: gen orch/driver intact, shm + 12 stale claims cleaned, 4 jsons kept for
  shared-claim resume).
  **RETRY RESULT (21:07-21:55): FAILED DIFFERENTLY — LOCAL CONCURRENT EVAL IS DEAD.**
  Pinned retry (OMP/MKL/OPENBLAS/NUMEXPR=1, OW=4) fixed the load thrash (10-16, sane)
  but its 4 mp workers DIED silently (~resource_tracker "process died unexpectedly");
  0 new games in 48 min, main at 0% CPU. Two distinct failure modes in two attempts →
  per the flywheel-first rule, NO MORE local concurrent evals this run. Killed+cleaned
  21:55 (note: my unbracketed pgrep killed my own shell twice — ALWAYS bracket).
  **PLAN B (ACTIVE): LAPTOP CHECKPOINT EVALS.** The laptop runs this harness flawlessly
  (whole n=200 confirm, zero incidents). At checkpoint iters (07, 11, 15/16): kill the
  laptop GEN worker cleanly (by PID; clean laptop-host claims-without-npz in the live
  iter), run the eval ON THE LAPTOP (same wrapper, laptop paths, OW~10-12, n=200
  --paired, k2×200: est ~21s/game aggregate → n=200 ≈ 70-90 min ≈ one gen window),
  then relaunch laptop gen on the then-live iter. Local box NEVER runs evals.
  Eval cmd = the iter_NN template below but on laptop via 'bash -s' script, out-subdir
  eval_iterNN_vs_rodv2iter02_lap, OPP ckpt path /mnt/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt.
  (The 78/12 encoder fix 2903a6c is in the bundle synced to the laptop — required.)
- **W ratchet (Joshua 19:35, pre-signoff):** if W8 = NO TANK, run the NEXT eval
  (iter_07) at OW=12-16 and re-measure the gen delta with the same sampler method;
  keep stepping W up per eval until gen notices, back off one step. Each scheduled
  eval doubles as the next rung's measurement.
- **Cadence from quality, NOT n from window (Joshua correction, 19:45):** do NOT
  shrink n to fit a gen window. Fix the eval at GOOD-ENOUGH quality — **n=200 paired**
  (~±12-17 elo, a real trend point; n=100 is only a screen) — at the max non-tanking
  W. Measure its actual duration D from the iter_03 run (extrapolate 100→200), and set
  the cadence x = eval every ceil(D / gen-window) iters (window ~60-90 min). E.g.
  D≈3 windows → eval every 3-4 iters; faster → denser. The running iter_03 eval is
  n=100 (launched pre-correction) — fine as the calibration + first screen; from
  iter_07 on, use `--n 200`.
- **Train-phase impact:** iter_05's train will overlap the running eval — compare its
  train duration vs iter_04's (stage2 log timestamps). If train slows meaningfully
  (>~20%), adopt PAUSE-VIA-KILL: kill the eval (wrapper + 2 fairnvn orchs by PID, rm
  /dev/shm/carc_fairnvn*) when a train phase starts, relaunch the SAME command at the
  next gen window — `--shared-claim` resumes, losing only in-flight games. If train
  doesn't slow, skip the pause complexity entirely.
- **Adaptive cadence:** default every 3-4 iters (07, 11, 15/16). If evals prove ~free,
  densify to every 2-3 iters (more trend points); never >1 eval per gen window, and
  FLYWHEEL ITERS ALWAYS WIN — any wedge/slowdown/RAM pressure → eval yields (kill,
  resume later). The 25h iter count is the priority.
- **Never SIGSTOP** an eval to "pause during train" (mp.Queue procs break —
  memory feedback_no_sigstop_mp_queue). If an eval must yield: kill wrapper+its two
  fairnvn orchs by PID, cleanup `/dev/shm/carc_fairnvn*`; `--shared-claim` resumes later.
  Stale eval claims: remove `*.claim` without matching json in the eval out-dir first.
- Summarize each finished eval: count W/L from jsons (candidate = seat a0/a1 paired),
  wr + naive elo, append to CHECKLOG + results.csv row (screen, n=100 → ±35 elo 1σ —
  label it screen, NOT a verdict).

## LAPTOP JOIN playbook (when confirm finishes, ~21:00-21:30)

1. Summarize confirm from its seed jsons (n=200 paired vs champion at equal budget?
   — read its manifest.json for the exact cell) → results.csv + CHECKLOG.
2. **Code sync**: regenerate bundle + laptop fetch/reset (memory
   reference_offline_git_bundle_sync): local `git bundle create /mnt/c/carc-shared/code_sync/carc_rod_v2_flywheel.bundle rod_v2_flywheel` then on laptop (via `ssh laptop-wsl 'bash -s' < script`, cd line 1): fetch bundle + `git reset --hard FETCH_HEAD`.
3. **Quick W probe** (BACKLOG says local W20/f4 does NOT transfer): start laptop gen
   joining the LIVE iter's net band via standalone `gen_fair_distill.py` — same recipe
   as driver: `--games 300 --k-dets 4 --sims 200 --c-puct 1.5 --tau-p 5.0 --value-norm 15.0 --sighted --net-ckpt <share>/ckpt/iter_<N-1>.pt --batch-size 16 --seed-start <net_seed of live iter> --out <share>/iter_N --shared-claim --claim-host laptop`
   with a **laptop-local carc-orch on its 4070m** (mirror the driver's orch launch,
   distinct shm name e.g. `distill_lap`, `--n-ch 81 --n-scalar 42`, W start **8**).
   net_seed(iter N) = 700000000 + N*100000 + 50000. Probe: W8 ~8 min → note laptop
   RAM (`free -g` ≥2G avail) + aggregate npz rate; if clearly safe try W10-12 for one
   step (kill cleanly by PID; clean laptop-owned .claim without npz before relaunch —
   check claim file content identifies host). Pick safe W, leave it running.
4. **Per-iter follow**: laptop gen is pinned to one iter. Each wakeup, if its iter
   finished, relaunch it at the new live iter (bump --net-ckpt/--seed-start/--out).
   (If gen code changed meaning of args — it hasn't — re-verify.)
5. Laptop safety: WSL RAM 11G total — keep ≥2G available; if sshd wedges, that's the
   W26-gen failure mode (too high W).

## Contingencies

- **C1 driver dead mid-iter** (pgrep run_distill_stage2 empty): census orphans
  (`ps -o pid,etime,%cpu,args -C python --sort=-etime | head`), kill leftover gen/orch
  by exact PID (spawn workers don't die with main). Clean current iter's claims-without-npz.
  Relaunch: `USE_LAPTOP=0 CHAMP_GAMES=0 GAMES=300 NET_GAMES=300 NET_BATCH=16 NET_KDETS=4 NET_SIMS=200 START=<current iter N> END=16 W_LOCAL_NET=20 ORCH_WORKERS=20 setsid nice -n 19 bash scripts/distill_flywheel/run_distill_stage2.sh </dev/null > measurement/distill_flywheel_20260715/stage2_sims200_r2.log 2>&1 &`
- **C2 gen stalled but driver alive**: driver self-heals (proven 5× on iter_04). Only
  act if >30 min with 0 new npz AND no heal lines in the log.
- **C3 box rebooted** (session survives only if WSL did): everything above is dead —
  relaunch driver per C1, relaunch laptop join per playbook, note gap in CHECKLOG.
- **C4 eval wedged/BrokenServer**: kill eval by PID (wrapper + 2 fairnvn orchs), rm
  its /dev/shm/carc_fairnvn* files; retry once in the next slot; if it re-wedges, drop
  concurrent evals and log it.
- **C5 disk**: if C: fills (`df /mnt/c`), free with
  `find /mnt/c/carc-shared -name '*.npz' -mmin +2880 -delete` — but ONLY dirs of
  CONCLUDED runs; NEVER the live `distill_flywheel_sighted_20260716` iters (training
  --window needs them) and KEEP all .pt.
- **C6 iters run out** (iter_16 trains before the 25h ends): launch continuation
  START=17 END=20 (same env as C1, START/END changed) — "as many iters as possible."

## CHECKLOG (append at each wakeup: time | iter/npz | laptop | actions)

- 2026-07-17 19:20 | it5 36/300 gen | laptop confirm ~127/200 | eval it3-vs-rodv2 W8 launched (concurrency test), samplers live, ops doc committed.
- 2026-07-17 20:00 | it5 93/300 gen, driver+orch healthy | laptop not checked (next wake) | CONCURRENCY TEST: TANKED −52% at load 70/32 (thread-thrash suspected, no OMP pinning) + eval itself crawled 3/100 in 38m → eval KILLED clean 19:57, load draining 70→51, 4 jsons kept, 12 stale claims cleaned. Retry plan: OMP/MKL=1 + OW=4 at a train-phase start. Next wake ~21:00 (laptop confirm ETA + train-window watch).
- 2026-07-18 08:40 | it13 opened → fairnvn cleaned + laptop REJOINED (orch iter_12.ts READY 08:38, gen W8 seed 701350000, RAM 7G) — 2-box it13 | plan: it14 ~09:50, it15 ~11:10 (+deploy it16 eval runner), END=16 ~13:45 → C6 continuation 17-20.
- 2026-07-18 08:25 | **it11 EVAL FINAL: TIE #2 — n=200, 96-102-2, wr 0.485, elo −10.4±25, margin +0.07** (results row eval_iter11_vs_rodv2iter02; trend it7→it11 FLAT vs anchor at low sims) | it12 trained 08:19 → it13 ~08:32; it13 rejoin scripts prepped + watcher armed | remaining: it13-16 (~78min each → END=16 ~13:45), FINAL eval on iter_16 endpoint (runner deploy ~13:00 wake), then C6 continuation 17-20.
- 2026-07-18 07:25 | it12 solo 147/300 (~2.7/min, done ~08:15) | it11 eval 107/200 PARTIAL wr 0.481 — tracking a tie like it7 | trend so far: it3=champ-tie(prod), it7=rodv2-tie, it11 partial tie → flywheel HOLDS tier, not yet exceeding anchor at low sims | healthy (load 17, RAM 27G).
- 2026-07-18 06:25 | it11 gen DONE 300/300 (06:07), train running → iter_11.pt ~06:20 → eval runner fires (within its 200min window, expires ~07:00 — fine) | watcher armed on first eval json | RAM 32G, healthy.
- 2026-07-18 05:25 | it11 69/300 2-box (laptop 40 claims), driver healthy, load 16, RAM 27G, disk 21G. Quiet wake — eval fires ~06:20.
- 2026-07-18 05:03 | it11 opened → laptop ADVANCED (orch iter_10.ts READY 05:02, gen W8 seed 701150000, RAM 7G) — 2-box it11 | it11 gen ETA ~06:05, iter_11.pt ~06:20 → eval runner fires (laptop), local solo-gens it12 | all healthy.
- 2026-07-18 04:22 | it10 gen 193/300 2-box (laptop 91 claims), all healthy, load 17 | it11 advance scripts prepped + watcher armed on [it11] READY (launch on notification); it11 eval runner standing by on laptop (fires at iter_11.pt ~06:15). Safety green.
- 2026-07-18 03:40 | it10 opened → laptop ADVANCED (orch iter_09.ts READY 03:37, gen W8 seed 701050000, RAM 7G) — 2-box it10 | **it11 eval-swap runner deployed** (timeout bug caught: 50min window would expire before iter_11.pt ~06:15 — redeployed with 200min window, pid 19203); fires autonomously → eval_iter11_vs_rodv2iter02_lap n=200 | next wake 04:20 (fallback): it10 progress + arm it11-advance watcher.
- 2026-07-18 03:20 | it9 298/300 done-ish (laptop 116 claims = 39%!), train imminent, it10 ~03:35 | it10 advance scripts + it11 eval-swap runner PREPPED (sed bug caught: eval_iter07 subdir survived — fixed); bg watcher armed on [it10] orch READY → launch both on notification. Safety green (RAM 26G, disk 22G).
- 2026-07-18 02:20 | **EVAL it7-vs-rodv2 FINAL: TIE — n=200, 93-103-4, wr 0.475, elo −17.4±25, margin +2.22** (results.csv row eval_iter07_vs_rodv2iter02) | it8 trained (02:12) → it9 gen open; laptop fairnvn cleaned + REJOINED it9 (orch iter_08.ts READY 02:16, gen W8, RAM 7G) — 2-box again | next checkpoint eval iter_11: deploy runner when it10 underway (~04:30). Pace ~78min/iter → END=16 well before deadline.
- 2026-07-18 01:45 | it8 253/300 (done ~02:00) | eval 179/200: **regressed to TIE — wr 0.497 (87-88-4), elo −1.9, avg_diff +1.59** (the 00:45 wr .595 partial was noise — lone-spike lesson). iter_07 ≈ rodv2 anchor tier at low sims. Final summary + results row + laptop it9 rejoin at ~02:15 wake.
- 2026-07-18 00:45 | it7 trained (00:09), it8 local-solo gen 88/300 (~2.6/min, done ~02:05) | **laptop eval FIRED autonomously, 63/200 in ~30min (2.1 g/min, ETA ~01:45) — PARTIAL: iter_07 vs rodv2 wr 0.595 (37-25-1), avg_diff -0.84** (leading the anchor; narrow wins). Cadence calibrated: n=200 eval = ~1.3 gen windows -> every-3-iters affordable. Next wake ~01:40: final eval summary + laptop REJOINS it8 mid-band (orch iter_07.ts, seed 700850000).
- 2026-07-17 23:50 | it7 gen 260/300 2-box (laptop 115 claims — pulling hard; rate ~4.6/min vs 3.3 solo), driver healthy, load 17.5 | **laptop eval-swap runner DEPLOYED** (detached on laptop): waits for iter_07.pt + gen self-exit → kills distill_lap orch → runs it7-vs-rodv2 n=200 paired k2×200 OW=10 pinned, out eval_iter07_vs_rodv2iter02_lap, log /tmp/lap_eval_runner_it07.log; est eval ~80-90min (done ~01:40), local gens it8 solo meanwhile, laptop rejoins gen at it9. Next wake ~00:45.
- 2026-07-17 22:55 | **it6 DONE 300/300 (laptop contributed 74 = 25%), trained, it7 gen started 22:49** | laptop ADVANCED to it7: orch restarted on iter_06.ts.pt (READY 22:49:56), gen W8 relaunched seed 700750000, RAM 7G free | local driver+orch healthy, load ok | 2-box it7 ETA ~00:00 + train -> **iter_07.pt ~00:15 = first Plan-B eval slot (laptop swaps gen->eval next window)**. Next wake ~23:45.
- 2026-07-17 22:05 | **LAPTOP JOINED iter_06** (agent report): synced to tip 8f228d1; laptop orch shm `distill_lap` on 4070m READY (iter_05.ts.pt loaded direct from share, ~4735 ex/s, fwd_busy 44%), gen W8 via champ_env (thread-pinned, no thrash), 8 laptop claims in it6, RAM 7G free, local unaffected. **PER-ITER FOLLOW (my job each wake): laptop gen self-exits when the iter band exhausts; to advance → relaunch laptop orch with the NEW iter's ts.pt (it's pinned!) then gen with +100000 seed band — staged scripts scratchpad/lap_orch_launch.sh + lap_gen_launch.sh. EXCEPT at checkpoint iters (when ckpt/iter_{07,11,15}.pt appears): that window the laptop runs the Plan-B EVAL instead of gen, rejoining gen the next window.** Laptop logs: /tmp/distill_lap_orch_it06.log, /tmp/distill_lap_join_it06.log.
- 2026-07-17 21:55 | it5 trained 12.5min (21:02→21:15, w/ eval concurrent — train unaffected); it6 gen 100/300 healthy | pinned eval retry FAILED (workers died silently, 0 games/48min) → local concurrent eval ABANDONED (2 failure modes), killed+cleaned; PLAN B active: laptop checkpoint evals (~70-90min at k2×200 n=200) at iters 07/11/15, laptop gens otherwise | join agent kicked via message (its it6 poll never fired) — laptop gen launch in flight | load 15.5, RAM 25G, disk 22G. Next wake ~22:50.
- 2026-07-17 21:10 | it5 292/300 (gen recovered 3.3/min post-kill; train imminent) | **LAPTOP CONFIRM DONE: n=200 TIE** — 100W/100L wr .5000 elo +0.0 avg_diff +1.87 (iter_03 net-priors vs fair champion, k4×688 single-var swap; distillation FAITHFUL at production depth; results.csv row distill_s1_confirm_n200) | pinned eval retry LAUNCHED (OMP/MKL/OPENBLAS/NUMEXPR=1, OW=4): resumed 7 games, load 10.4 — **thread-thrash CONFIRMED as the tank cause** (laptop manifest showed same harness healthy WITH pinning) | laptop-join subagent dispatched (bundle sync → wait iter_06 → orch W8 + gen launch). Next wake ~22:00.
