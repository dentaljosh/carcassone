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

## WHAT'S RUNNING NOW (12:30 — SPLIT: the confirm is CPU-bound, so it moved OFF the strong box)
The both-box confirm banked **0 games in 31 min** (each k4×688 fair game is a >40-min wall; parallelism just
fans many long games out — it's CPU-bound, orch only ~37% busy). The flywheel is the priority, so Joshua split
the boxes: confirm → laptop-only, flywheel → local now.

- **LAPTOP — n=200 confirm** (cut from 400: laptop-only is ~22% of combined throughput → n=400 would be ~37h;
  n=200 ±25 elo still separates +88 from a wash, ~19h). Candidate bs=16 net vs the fair champion, k4×688, band
  **22.0e9**, dir `<run>/confirm_n200_laptop/`, OW=8, own carc-orch. Rung guard PASSED (both sides curve125, no
  leak). Log (laptop): `/tmp/confirm_laptop_n200.log`. Relaunch = pipe `scratchpad/confirm_laptop_n200.sh` to
  laptop-wsl. Kill (laptop): `pkill -9 -f eval_fair_[p]uct` + its orch (`ps -C carc-orch`).
- **LOCAL — the FLYWHEEL (stage 2, iters 4-11), net-gen ONLY.** `run_distill_stage2.sh` with
  `USE_LAPTOP=0 CHAMP_GAMES=0 GAMES=450 NET_GAMES=450 NET_BATCH=16 NET_KDETS=4 NET_SIMS=688` (full-budget k4×688,
  proven — NOT the unvalidated 2× sims cut). iter-4 gen live: 28 workers, load ~12-18 (NOT oversubscribed — gen
  self-play batches BOTH sides through the orch, avg_batch 14.3, fwd_busy 43%). Launcher log:
  `measurement/distill_flywheel_20260715/stage2.log`; per-iter status: `measurement/<TAG>/STAGE2_STATUS.md`;
  gen log: `<run>/logs/gen_local_it<NN>.log`. Kill (local): `pkill -9 -f run_distill_stage2` then
  `pkill -9 -f gen_fair_distill` + `ps -C carc-orch`.

⚠️ **ANCHOR-FREE recipe deviation (monitored, deliberate):** the intended flywheel mixes a 25% net-free champion
side-stream on the laptop (anti-drift anchor). The laptop is on the confirm and the two timelines are ~even
(~19h each), so the laptop won't realistically free up mid-run — this flywheel runs WITHOUT the champ anchor.
The **severed value loop** (value = frozen champion leaf, never the net) is the PRIMARY anti-collapse mechanism
and is intact; the anchor is secondary belt-and-suspenders on the policy side. Watched via the per-iter collapse
screen (rc=3 halts), the iter-6 gate, and iter-resumability — if drift shows, add the anchor back or abort cheap.

## THE PLAN (steps 1 and 4 now run CONCURRENTLY — see WHAT'S RUNNING)
1. **n=200 confirm** (laptop-only, running) → does +88.7 hold at equal sims for the deployable bs=16 agent?
2. **E4 — the DEPLOYABILITY verdict (now the key experiment):** a net-sims ladder (344 / 688 / 1376,
   all bs=16) vs the FIXED 2752 champion. The champion at 2752 costs ~what the net costs at ~1376, so
   **if net-1376 still beats champion-2752, that's a real wall-clock win + a fast agent.** If it needs
   the full 2752, +88.7 is an equal-sims curiosity. One ladder answers goal-1 (deployable performance).
3. **Restructure stage-2 to shared work-stealing** (see design principle) + fix REVIEW_LOG D9 (a claim
   held ~90 min by a failed game; its gate is "before the next multi-iter run" = this run).
4. **Flywheel (stage 2, iters 4-11)** on the fast path, with the net-side sims CUT (advisory: 2752 is
   ~2× over-provisioned for the net — cut SIMS, never k_dets [CL-054 inverted-U peak] or games).
   Decision gate after iter 6 (free — driver is iter-resumable). Goal 2: does self-play produce
   STRONGER nets. **~66h at batch-1; batching + a sims cut should bring it well down — re-bench first.**

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
