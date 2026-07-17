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
- **Concurrency policy** (fill in after the test): if NO TANK → launch evals freely
  during gen. If MILD (-8..-25%) → launch evals only right after a train phase starts
  (gen idle) and let them run into gen. If TANKED → evals only during train windows.
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
