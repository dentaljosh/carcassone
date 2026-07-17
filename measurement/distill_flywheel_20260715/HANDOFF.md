# Distill-flywheel — LIVE HANDOFF (2026-07-17 12:00 EDT)

**The single authoritative state doc. Survives compaction — a fresh session picks up from here alone.**
Design: `DESIGN.md` + `DESIGN_FAIR_ADDENDUM.md` (fair pivot). Perf: `PERF_ADVISORY.md`. Audits:
`INPUT_EXPOSURE_HISTORY.md`, `PRIOR_TOP1_CALIBRATION.md`, `PRIOR_GEN_MODE_AUDIT.md`, `SIGHTED_SCOPE.md`.

## 🎉 THE HEADLINE (with the honest caveat)
**A distilled net BEAT the fair champion — +88.7 elo (61W/3D/36L, wr 0.625, n=100, paired z=1.92).**
Candidate = net policy-head priors + FROZEN curve125 leaf value, fair PIMC k4×688; opponent = the
production fair champion (heuristic priors, same 2752 budget, same leaf). Pure PRIOR-SWAP — only the
priors differ. **This is the FIRST time a learned component beat the heuristic in this project** (the
structural blocker that killed every prior neural attempt — see `PRIOR_TOP1_CALIBRATION.md`: the old
neural champion iter8 retro-scores only ~0.37 top-1 vs this teacher).

**⚠️ THE CATCH — it's an EQUAL-SIMS win, not equal-wall-clock.** The net costs **~2.2× the champion per
move** (bs=16; was 12.67× at batch-1). On the CL-046 ladder, giving the champion 2.2× more sims is worth
~+70-80 elo — so at EQUAL WALL-CLOCK the +88.7 likely shrinks toward a **wash**. n=100 z=1.92 is also a
SCREEN, not a verdict, and has the same statistical profile as t020 (+32/z1.68 → collapsed to +3.4 at
n=800, CL-057, three days prior). **So: confirm + wall-clock test both needed before believing it.**

## WHAT'S RUNNING NOW (17:25 — VIABILITY FLYWHEEL sims200 @ W20/f4, iters 4-16 — CONFIG SETTLED)
**Reframe (Joshua):** this flywheel is a **viability probe** — can self-play get the net IMPROVING at all, and
does it PLATEAU early? NOT a max-strength run, so it's cut hard for speed. The earlier sims688 iter-4 was killed
(0 games banked) after it was diagnosed as a ~6.7-DAY run (GPU-forward-bound — see LEVERS EXPLORED below).

- **LOCAL — FLYWHEEL (stage 2, iters 4-16), net-prior ONLY, NO strength-gate.** `run_distill_stage2.sh` with
  `USE_LAPTOP=0 CHAMP_GAMES=0 GAMES=300 NET_GAMES=300 NET_BATCH=16 NET_KDETS=4 NET_SIMS=200 START=4 END=16 W_LOCAL_NET=20 ORCH_WORKERS=20`
  (forwarders default 4). Budget k4×200=**800** (¼ of champion's 2752). **~1.5-2h/iter MEASURED** (~3 games/min
  steady at W20 → iters 4-16 ≈ ~1 day). Launcher log: `measurement/distill_flywheel_20260715/stage2_sims200.log`.
  iter-4 resuming from ~62 games (`--shared-claim` survives kill/relaunch — the config was tuned via many
  pause/resume cycles, games always preserved).
  Collapse-safety screen (rc=3) STAYS ("no gate" = no strength decision-gate, kill/gate manually). Kill (local):
  `pkill -9 -f run_distill_[s]tage2`, then gen main + `pgrep -f multiprocessing.[s]pawn` by PID + `ps -C carc-orch`.
  ⚠️ **pkill self-match bit me twice this session** — NEVER leave the literal pattern UNbracketed in the kill cmd.
- **LAPTOP — n=200 confirm** (goal-1 verification, RESUMING 32/200 — fair games DO complete), OW=**12** (W-sweep
  optimum), band 22.0e9, dir `confirm_n200_laptop/`. Independent of the flywheel. Log (laptop): `/tmp/confirm_laptop_n200.log`.

⚠️ **sims200 = ¼ budget, BELOW the advisor's ½-budget "safe" floor.** A NULL result is AMBIGUOUS (real, OR gen
search too weak to beat the net's own 2752-distilled priors → no gradient). **Protocol:** a POSITIVE signal is
self-validating (viable, cheaply); a NULL → bump to sims **344** (k4×344=1376=½ budget) to disambiguate BEFORE
concluding "doesn't work." The strong frozen champion leaf (value) makes even a shallow search decent, so 200 has
a real shot. (Advisor wanted 344; Joshua chose 200 with this escalation protocol.)

⚠️ **ANCHOR = GEN data, not eval** (net-free champion games mixed into training, anti-drift). Currently OFF
(net-prior only). ~40% covered anyway by the train `--window` (keeps the stage-1 champ games). If per-iter eval
shows DRIFT, add the champ-anchor on LOCAL's **idle CPU** (gen is GPU-bound → CPU ~50% idle; net-free champ gen
overlaps it perfectly — Joshua's "use the idle half" idea). Needs a driver change (subagent) + a resume.

## THE PLAN (viability run)
1. **Flywheel iters 4-16** (running, sims200) → does the net improve? does it plateau?
2. **MEASURE at LOW sims (advisor, load-bearing):** the flywheel improves the POLICY head only, and policy gains
   WASH OUT under deep search (`feedback_sims_washout_net_eval`: deepteacher +82.8/z3.48 @sims200 → +8/z0.34
   @sims800, SAME nets). So grade at **~k2×172, NOT production 2752** — a paired game screen vs BOTH **iter_03**
   (fixed seed anchor) AND the **fair champion**, at checkpoints (e.g. iters 4/7/11/16). n=100 screen, n=400
   paired confirm on the endpoint. The wired per-iter probe (CE/top-1/entropy) + collapse screen = HEALTH ONLY,
   NEVER read as strength (autopsy: +top1 with −40 elo). Eval harness = `eval_fair_puct.py` / `fair_net_vs_net_orch.sh`
   (already supports `--opponent net` [OPP_CKPT=iter_03] and `--opponent fair-champion`).
3. **Plateau criterion (advisor + `feedback_noisy_plateau_not_a_conclusion`):** a few flat iters ≠ plateau
   (deepteacher iters 3-5 rejected → "definitively no" → 6-8 ALL promoted). "Plateaued" is legit ONLY as a
   POWERED NULL after ≥6-8 iters (cumulative iter_last−iter_03 at low sims, n=400, within ±X of 0). Believe the
   fixed anchor over chain-vs-prev (chain climbed +612 while the fixed anchor showed −330).

## LEVERS EXPLORED THIS SESSION (2026-07-17 — why the config is what it is)
- **Gen is GPU-forward-bound** (28 games funnel net-prior forwards through 1 GPU, orch ~99% / CPU ~50% idle). The
  ONLY real speed levers are cutting the SEARCH (sims/k_dets/games) — not workers, not batching, not more boxes.
- **max_batch: WASH** (mb-sweep this session: MB16=5492 / MB32=5724 (+4%) / MB64=4787 / MB128=5035 fwd/s — GPU
  compute-bound at MB16, bigger batches STALL the latency-sensitive workers). Left at 16. The old "MAX_K" idea
  was the wrong constant (`MAX_K`=per-worker wire cap, strength-affecting; `--max-batch`=the GPU batch, free, strength-neutral).
- **xeon + laptop: too slow to add as gen GPUs** (Joshua: "forget xeon"). Laptop = confirm only.
- **Laptop confirm W-sweep:** optimum ~**W12-16** (1550→1858 fwd/s W8→W22, GPU-capped, RAM drops past W16) —
  NOT the old net-value W26 (different profile: fair net-prior eval is the CPU-leaf-heavy "W≤threads" regime).
- **k_dets STAYS 4** (advisor: CL-054 strength peak AND target-quality — the policy target is pooled over the k
  trees, so k4 = lower-variance targets; cutting to k2 noisies the small signal we're hunting). Cut SIMS only.
- **Local gen W-sweep (sims200):** throughput FLAT ~5200 fwd/s from W20→W44 (latency-capped, not worker-bound).
  **W20 = knee** (min-W holding the plateau, 65% pipeline, load ~15/32, max headroom); below it worker-starved
  (W16 −9%, W12 −23%). → run **W20**.
- **Forwarder sweep (proportional-knee, ~5 workers/forwarder):** more forwarders BARELY help — f6/W30=+4.7% (5421
  fwd/s), f8/W40=+1.5% AND hits the CPU-spin wall (load 30/32, throughput reverses). Gen is **DISPATCH-LATENCY-BOUND**
  (the per-forward round-trip: SHM handoff + H2D/D2H + CUDA dispatch/sync — NOT compute [GPU 76W], NOT PCIe-bw, NOT
  workers, NOT forwarders). Ceiling ~**5400 fwd/s**. → **f4** default; the +4.7% isn't worth spending the headroom.
  Matches the project's "training is GPU-latency-bound" finding. **W/forwarder rabbit-hole CLOSED — don't re-run.**
  The freed W20 headroom (load ~15/32, GPU 76W) is for the champ-anchor and/or concurrent per-iter eval instead.

## DESIGN PRINCIPLE (Joshua, standing)
**Every workload = a shared work-stealing pool at per-box OPTIMAL W; nothing pinned to one box.**
- **GEN orch-ON:** local **W28** / laptop **W8** (laptop RAM-capped — W12+ OOMs the 11 GB box, W26 gen
  wedged sshd. Source: `docs/CLUSTER_OPS.md:30-34`, `gen_flywheel.sh:_OWD`).
- **EVAL orch-ON:** local **W40** benched peak (`step2_pens/run_step2_flywheel.sh` 2026-06-30: 40=8.70
  g/min > 48=8.51 > 28=7.16) / laptop W26. **BUT** for the batched net-prior eval (heavier, unmeasured)
  the confirm is running local OW=28 / laptop OW=8 — re-tune from the confirm's rate.
- **TRAIN:** local only (GPU-latency-bound, can't span boxes). Laptop IDLES during train — **do NOT get
  fancy filling it** (Joshua; ~10 min/iter, not worth the coordination).
- Per-box orch is a proven pattern (`gen_flywheel.sh` runs a `$HOST`-keyed server per box; rod_v28 ran
  both boxes on one net-gen pool, shared-claim). Laptop-orch-batched-net-prior SMOKE-VALIDATED 2026-07-17.

## KEY RESULTS SO FAR
- **Distillation works:** sighted stage-1 final top-1 vs the fair champion = 0.602 (32%→60%, ~80% of the
  ~0.75 teacher-vs-teacher ceiling). 5 ckpts at `<run>/ckpt/iter_00..03.pt` (iter_03 = the seed).
- **The bag adds nothing** (sighted ≈ non-sighted, tie): confirmed 3 ways — our A/B (0.594 vs 0.597 at
  matched iter-2), our ~3pp noise floor, and CL-050's bag-blind control recovering ~95%. STAY SIGHTED
  (free, keeps optionality). This is the project's FIRST fair-trained net lineage (all prior clairvoyant).
- **Batching:** 3.4× (bs=16 optimal, bs=32 no better — MAX_K=8 SHM wire cap; residual is the net FORWARD,
  GPU-compute-bound, not further batchable). max-batch **16 > 64** (measured — demand-limited, not
  cap-limited). Batched picks == serial 3/3 (no strength collapse). Champion path byte-identical.

## COMMITS (branch `rod_v2_flywheel`, NOT pushed)
`a1ae1db` fair emitter + agg_n stash · `4a25a74` --sighted · `04b951f` stage-2 flywheel (net-prior +
orch driver) · `60be5b7` --info fair-netprior eval arm · `f5c99d3` --opponent {h800,fair-champion,net}
· `1b5c9bd` two-server orch net-vs-net · `2bd7529` overnight chain · `36dff1d` **orch clock-step fix**
(sem_timedwait MONOTONIC) · `6463398`+`96b22b0` **within-search batching**. HH1 result banked at
`<run>/hh1_vs_champion/summary.json`.

## GOTCHAS THAT BITE (hard-won)
- ⚠️ **NEVER `source champ_env.sh` before `eval_fair_puct`** — its `_CANON_ENV` uses `setdefault`, so a
  pre-set curve env WINS and silently moves `DEFAULT_CONFIG` = the h800 rung → invalidates cross-arm
  numbers while looking plausible. curve125 is injected in-process, candidate-side only;
  `_assert_rung_is_ruler` fails loud. (This bit two agents; both caught.)
- ⚠️ **Two leaf-hash dialects, SAME leaf:** `a36d2e15` (harness, meeple_k=2.0) vs `6dfffd57` (snapshot,
  meeple_k=0.0) — meeple_k inert under a non-null curve (240/240 identical). PRODUCTION.yaml's `158f17ff`
  is STALE. Assert curve VALUES, not a fingerprint.
- ⚠️ **carc-orch defaults n_ch=78** — a sighted net needs explicit `--n-ch 81 --n-scalar 42` or it
  silently corrupts. (The nvn driver + stage-2 driver pass both.)
- ⚠️ **max-batch: leave at 16** (64 is measurably WORSE — my "try 64" was refuted by the bench).
- ⚠️ **The orch stall was a WSL2 clock-step bug** (`36dff1d`), not a load issue — load-independent, which
  is why the "known open orch stall" never reproduced on demand. Now fixed on the MONOTONIC clock.
- ⚠️ **Laptop RAM:** monitor `free -g`, not loadavg — a WSL OOM restarts the whole VM. Gen W8, not W12+.
- Noise floor ~3pp on the 24-game probe; n=100 eval is a SCREEN (±35). Two prior noise-spike errors
  logged here (c=3 "+47", deepteacher "+53.7") + the t020 collapse — confirm before believing.
- A 2.7 GB WSL2 phantom GPU allocation persists (no process holds it; leaked dxg context from a crash);
  harmless, 13 GB free, only `wsl --shutdown` reclaims it.

## INVARIANTS
`governance/PRODUCTION.yaml` and the champion **UNTOUCHED** (the champion is also the RULER + stage-1's
teacher — its heuristic-priors search stays byte-identical; batching is candidate-only). Measurement/
exploratory only — no promotion. Branch `rod_v2_flywheel`, not pushed. The h800 rung ruler never moves.
