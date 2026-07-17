# Distill-flywheel — LIVE HANDOFF (2026-07-16 20:40 EDT)

**The single answer-ready state doc for this work.** Written to survive a context compaction —
a fresh session should be able to pick up from this file alone. Design: `DESIGN.md` +
`DESIGN_FAIR_ADDENDUM.md` (fair pivot supersedes DESIGN §D2/§4.1/§4.3). Audits:
`INPUT_EXPOSURE_HISTORY.md`, `PRIOR_TOP1_CALIBRATION.md`, `PRIOR_GEN_MODE_AUDIT.md`, `SIGHTED_SCOPE.md`.

## The goal (2 sentences)
Distill the classical champion (`puct_priors_v29_bmild_cap8`, PRODUCTION.yaml) into a net —
goal 1 = a fast champion-strength net; goal 2 = does a flywheel then produce *stronger* nets.
We distill the **FAIR (blind PIMC)** champion, not the clairvoyant one (Joshua's call — see below).

## WHAT'S RUNNING RIGHT NOW
**SIGHTED stage-1 (iters 0-3), launched 12:06 EDT.** Both boxes, `--shared-claim`
(local W16 + laptop W12), net-free CPU gen.
- Teacher: `FairHeuristicPriorAgent` (blind PIMC, **k_dets=4 × sims=688 = 2752**, curve125 leaf,
  c1.5/tau5/vnorm15). Records pooled root-visit POLICY (`agg_n`) + game-OUTCOME value.
- Rep: **SIGHTED** 81ch/42 (bag histogram + farm planes), warm iter0 ← `m2_sighted/warmstart_sighted.pt`.
- Driver: `scripts/distill_flywheel/run_distill_sighted.sh` (STOPS after iter 3).
- Run root: `/mnt/c/carc-shared/distill_flywheel_sighted_20260716/`
- Status @20:40: iter_02 ~344/600. **iter 2 done ~21:55, stage-1 complete ~1:15am.** ~180 games/h.
- Live state: `STAGE1_STATUS.md` (driver-written) + `sighted_driver.log`.

## RESULTS SO FAR — the distillation works; the bag does not

Fidelity to the fair champion on a frozen 24-game probe (`probe_metrics.jsonl`, top-1 = argmax match):

| | warmstart | iter0 | iter1 | iter2 |
|---|---|---|---|---|
| **non-sighted** (78ch/10) — DONE | 0.322 | 0.561 | 0.592 | **0.597** |
| **sighted** (81ch/42) — running | 0.364 | 0.554 | 0.559 | — |

- **Distillation works.** 32% → ~60% champion agreement. Teacher-vs-teacher ceiling is **~0.75**
  (two strong searches only agree ~75%), so ~60% is ~80% of achievable — near-plateau, and
  **2-2.6× any prior net's raw-prior/teacher agreement** (see `PRIOR_TOP1_CALIBRATION.md`).
- **The bag adds nothing.** Sighted wins the *warmstart* (+4.2pp) then the edge evaporates once
  teacher signal arrives. **Correct claim = "no detectable gain," NOT "sighted is worse"** —
  our own noise floor is ~3pp (iter-0 Δ=0.7pp, iter-1 Δ=3.3pp ≈ 1σ). Do not call it a regression.
- **History predicted this** (`INPUT_EXPOSURE_HISTORY.md`): CL-050's bag-blind *control* recovered
  **~95%** of the offline gain (bag ≈5%); CL-037 ablation "largely redundant"; and **no input
  addition has ever fired in games in this project** (the 78ch meeple-fix counterexample was never A/B'd).

## DECISIONS MADE (don't re-litigate)
1. **FAIR teacher, not clairvoyant** (Joshua). Clairvoyant distillation injects strategy-fusion:
   the net (always blind) would learn `E_deck[π(board|true deck)]` = the average of deck-aware
   policies ≠ optimal blind policy. Fair is only **~1.3× clair compute** (measured; the DESIGN's
   "4×" conflated the elo tax with compute). **This is the project's first fair-trained net lineage**
   (`PRIOR_GEN_MODE_AUDIT.md`: every prior net — v1-v6, v25, deepteacher, residual attempt1/2,
   rod_v2/v28, M2 — was clairvoyant-trained; `fair_chance=False` in `play_one_selfplay_game`).
2. **STAY SIGHTED** (Joshua). No detectable gain, but ~zero cost (~1-2% compute, trivial params)
   and it keeps bag optionality for the flywheel's *improvement* step (untested; different from imitation).
3. **The ladder is REJECTED as the reference.** The CL-046 fair ladder (champion vs h800:
   +27.9/+61.4/**+81.4**/+149.3 @ 800/1600/2752/5504, n=200, band 15e9) is **kd8 + curve100** =
   two config generations behind our k4+curve125 teacher. Its *rung* matches ours, but its champion side is stale.
   ⚠️ The rung being "weak" is NOT the flaw — it's non-saturated (champion wr 0.615) = fine as a ruler.
4. **Measure by DIRECT head-to-head, not delta-of-deltas through the rung** (Joshua).

## WHAT'S BUILT (all committed on `rod_v2_flywheel`, not pushed)
| commit | what |
|---|---|
| `a1ae1db` | fair emitter `gen_fair_distill.py` + `fair_agent` agg_n stash + stage-1 driver (21 tests) |
| `4a25a74` | `--sighted` flag (default OFF = byte-unchanged) + `run_distill_sighted.sh` |
| `04b951f` | **STAGE-2 FLYWHEEL** — `make_fair_net_prior_evaluator` + `--net-ckpt` orch mode + `run_distill_stage2.sh`. Integration-smoked: orch serves sighted 81ch/42 forwards end-to-end |
| `60be5b7` | **`--info fair-netprior` strength arm** — net policy priors + frozen curve125 leaf, both reps, rung ruler guarded |
| in flight | **`--opponent {h800,fair-champion,net}`** — direct head-to-heads (agent a459516c) |

## 🌙 OVERNIGHT CHAIN — LAUNCHED 2026-07-17 00:12, RUNNING UNATTENDED
`scripts/distill_flywheel/run_overnight_chain.sh` (commit `2bd7529`), detached, launched with
**`N_HH=100 OW=16`**. Log: `measurement/distill_flywheel_20260715/overnight_chain.log`.
**Morning read: `OVERNIGHT_CHAIN_STATUS.md`** (per-step state) in the run root.
1. **WAIT** for sighted stage-1 to exit (~1:40am; polls `run_distill_[s]ighted` every 120s).
2. **HH1 — the money shot:** sighted iter_03 **vs the fair CHAMPION** (`--info fair-netprior
   --opponent fair-champion`, k4×688, exact-k 2, **n=100 paired**, fresh CRN band **21.0e9**, W16,
   LOCAL, **CPU nets**). Pure prior-swap → the first real STRENGTH number for a distilled net.
   Results: `<run root>/hh1_vs_champion/`.
3. **HH2 — rep A/B on strength:** sighted iter_03 vs non-sighted iter_02 (cross-rep). Same band →
   deck-matched to HH1. Results: `<run root>/hh2_rep_ab/`.
4. **FLYWHEEL LAUNCHES UNCONDITIONALLY** (`run_distill_stage2.sh`, iters 4-11, seeds from sighted
   iter_03) — **Joshua's explicit call 2026-07-16**: it fires regardless of the HH results, even if an
   HH crashed, even if stage-1 died without iter_03.pt. **Fault-tested by injection** (both-HH-crash
   and no-iter_03 cases both still launched step 4).

### ⚠️ THE THREE THINGS TO READ FIRST IN THE MORNING
1. **THE FLYWHEEL IS ~66h (~2.75 DAYS), NOT ~13h.** Measured: net-prior gen is **forward-latency
   bound** (~219k forwards/game; **no game finished in 30 min at W=4**). GPU saturates ~3700 fwd/s;
   W28 demands ~3280/s → per iter 450 games × ≥219k ≈ ≥98M forwards → **≥8h/iter → ≥66h for iters
   4-11.** (Extrapolated — flagged as such.) **The lever is `NET_GAMES` (450) or `END` (11)**; both are
   env knobs, and the driver is iter-resumable via `done/` markers, so retuning after ~1 iter costs
   almost nothing. **I deliberately did NOT cut it** — that's the experiment's data budget = Joshua's call.
2. **A REAL ORCH ROOT CAUSE WAS FOUND + FIXED** (`36dff1d`, revert with `git revert 36dff1d`):
   `sem_timedwait` takes an **absolute CLOCK_REALTIME deadline** but the caller wants a *duration*.
   **WSL2 resyncs its clock to the Windows host — a forward clock step puts the deadline in the past →
   instant ETIMEDOUT → `BrokenServerError` against a healthy, still-batching server whose watchdog
   correctly stays silent.** That is the project's long-standing "known open orch stall"
   (`reference_exact_solver_eval_infra`), and it is **load-independent** — which is why it never
   reproduced on demand. Regression test fails against HEAD with the literal production error;
   validated in-situ (7.2ms/forward, no hot-path regression). **NOT eval-specific** — gen uses the same
   client and just didn't get unlucky in 30 min, so a multi-day flywheel would likely have hit it.
3. **Stage-2 gen does NOT reproduce the stall** (30 min / 876k forwards clean at k4×688) → the driver
   was left UNTOUCHED (a non-problem doesn't get an untested fallback in an unattended launch).
   The HHs still use **CPU nets**: the clock fix is plausible but **unproven for the eval**, and I
   wouldn't gamble the one number Joshua wants on an unproven fix while nobody's watching. `ORCH=1` opts in.

**Known costs of the overnight config (accepted deliberately):** the **laptop idles** during the
LOCAL-only HHs (~1:40am→HH end) — a 2-box eval split would have meant inventing a fragile scheme at
midnight, on the very transport that's broken. **n=100 (not 200)** because the chain's original ETA was
built on stage-1's *net-free* rate and the net-prior side is ~6× slower; n=100 paired ≈ ±25 elo, which
still answers the coarse question ("near the champion, or catastrophic like C-cheap's W0/L100?").
**ETAs for the HHs are UNVERIFIED** — no game completed in the bench window, so treat any HH ETA as a
guess. Step 4 is unconditional, so overruns cannot strand the night.

## GOTCHAS THAT WILL BITE (hard-won)
- ⚠️ **NEVER `source champ_env.sh` before `eval_fair_puct`.** Its `_CANON_ENV` uses
  `os.environ.setdefault`, so a pre-set curve env WINS and silently moves `DEFAULT_CONFIG` —
  **which IS the h800 rung**. That shifts the CL-022 ruler and invalidates every cross-arm number
  while still looking plausible. curve125 is injected **in-process, candidate-side only**;
  `_assert_rung_is_ruler` now fails loud.
- ⚠️ **Two leaf-hash dialects, same leaf:** `a36d2e15a3b3d71d` (harness `c5_leaf_override._leaf_hash`,
  meeple_k=2.0) vs `6dfffd57051690f2` (`snapshot._frozen_config_hash`, meeple_k=0.0). `meeple_k` is
  **inert** under a non-null curve (240/240 byte-identical leaf evals). PRODUCTION.yaml's
  `158f17ff` is **STALE** (LeafConfig gained default-off fields). Assert curve VALUES, not a fingerprint.
- ⚠️ **carc-orch defaults to n_ch=78** — a sighted net needs `--n-ch 81 --n-scalar 42` explicitly, or it
  silently corrupts. The stage-2 driver passes both.
- ⚠️ **`--smoke` never exercises `_worker_init`** → smoke-only checks miss rep-passing + SHM sizing.
  Always drive the real Pool path once.
- Noise floor **~3pp** on the 24-game probe. Two prior noise-spike errors are logged here (c=3 "+47",
  deepteacher "+53.7") — don't add a third.

## REBOOT RESUME (local box has a dirty-reboot history)
Driver is reboot-safe (`done/` markers + ckpt-exists skip):
`cd /home/doctor/projects/carcassone && setsid nice -19 bash scripts/distill_flywheel/run_distill_sighted.sh </dev/null >> measurement/distill_flywheel_20260715/sighted_driver.log 2>&1 &`
It skips completed iters. Laptop drop self-heals (shared-claim + local-only fallback).

## INVARIANTS
`governance/PRODUCTION.yaml` and the champion **UNTOUCHED**. Measurement/exploratory only — no
promotion. Branch `rod_v2_flywheel`, not pushed. The h800 rung ruler must never move.
