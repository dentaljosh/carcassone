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

## NEXT STEPS (in order)
1. **Stage-1 finishes ~1:15am** → sighted iter_3 ckpt. (Watcher `bvaubs0mj` armed; if lost, poll
   `pgrep -f 'run_distill_[s]ighted'`.)
2. **Two DIRECT head-to-heads** (once `--opponent` lands + boxes free):
   - **best distilled net vs CHAMPION** — "did the distillation work?" A pure prior-swap: same 2752
     fair budget, same frozen curve125 leaf, only priors differ (net vs heuristic softmax).
     ⚠️ Interesting: the net's priors encode the champion's *search output* (pooled visits after 2752
     sims), not its raw one-ply priors → net-priors + same search could **exceed** the champion. That's
     the flywheel's whole bet.
   - **sighted net vs non-sighted iter_02** — does the bag matter for STRENGTH (not imitation)?
   - ~n=200/arm, band 15e9, seat-balanced + deck-paired.
3. **W28 orch bench** for the real stage-2 ETA (the W2 smoke's 74s/game was tiny-batch under-utilization).
4. **Flywheel launch decision** (Joshua's go) → `run_distill_stage2.sh` iters 4-11.

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
