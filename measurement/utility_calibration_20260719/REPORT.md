# Utility calibration audit — verdict

**Date:** 2026-07-19 · **Branch:** rod_v2_flywheel · **Task:** External review, Candidate-3 Step 1.
**Question:** Does the fixed engine-side search utility `value = tanh(margin / 15)` (constant across
game stage) mis-price win probability in a **stage-dependent** way material enough to fund a
stage-dependent-utility experiment?

---

## VERDICT: NO-GO on a stage-dependent utility — but the audit surfaced a *larger, stage-invariant* miscalibration worth acting on

The review's mechanism is **qualitatively real** — a given lead is worth less early than late — but
out-of-sample it is the **small term**. The dominant, cheaper fix is a *global* recalibration of the
norm (the `/15` is ~2× too steep and saturates by ±25-30, throwing away gradient). That change is
stage-invariant and captures **92%** of the achievable calibration improvement; stage-conditioning
adds only **8%** on top, and it is concentrated in already-decided positions.

**Important:** this audit runs on the **raw on-board score margin**, not the **v2.9 leaf margin** the
search actually feeds to `tanh`. See the caveat section — it plausibly inflates the *global* finding
and is the reason a leaf-margin re-run is the recommended next step, not a stage-dependent experiment.

### The 5 numbers that carry it
| # | Finding | Value |
|---|---|---|
| 1 | Best single global norm T vs audited T=15 | **T\* ≈ 31** (data wants a curve ~2× flatter) |
| 2 | Per-stage best-fit T, opening→endgame (monotone, OOS-stable) | **62.9 → 57.8 → 39.7 → 29.6 → 23.9 → 22.5** |
| 3 | Out-of-sample logloss: fix from *global rescale* (M0→M1) | **ΔLL 0.0442** / ΔBrier 0.0120 |
| 4 | Out-of-sample logloss: extra fix from *stage-dependence* (M1→M2) | **ΔLL 0.0037** / ΔBrier 0.0014 (**7.7%** of total) |
| 5 | Stage effect at a decisive lead (+10-15), opening vs endgame p_win | **0.53 → 0.76** (spread 0.23); tanh/15 says **0.84** everywhere |

GO would have required the stage interaction to be material out-of-sample. It is real and monotonic in
T, but its **aggregate** predictive value beyond a global rescale is small (0.004 nats), because the
stage spread is largest exactly where positions are rarest and least decision-critical (big leads),
and near-zero at the near-tied positions that dominate the data and the search's hard decisions.

---

## Data used

| | |
|---|---|
| Source | `/mnt/c/carc-shared/distill_flywheel_sighted_20260716/` — the only abundant *live* npz source on the share (rod_v2 gen dirs were cleaned by disk-pressure GC). |
| Sample | Iters **00,02,…,20** (11 iterations spanning the flywheel), **300 games/iter → 3,300 games**, **474,815 positions**. Every game's deck seed is a distinct cluster. |
| Diversity | iter_00 = net-free blind-PIMC teacher (2752 sims/move); later iters = net-prior + frozen-leaf-value blind PIMC (800 sims/move). Same margin/value semantics throughout (verified). All are **FairHeuristicPrior self-play** (teacher-vs-teacher) — so P(win) is conditional on that opponent distribution, which is the same search family the utility serves. |
| npz join (verified) | `scalars[:,4] = (score_mover − score_opp)/50` → **raw margin, mover POV**; `scalars[:,5] = tiles_remaining/72`; `values = tanh(final_diff_moverPOV / 15)` → **terminal outcome** (confirmed: exactly one \|value\| per game across all iters; integer final margins). **Win label = sign(value); final margin = 15·atanh(value).** Both margin and value are mover-relative → per-row join is POV-consistent. |
| Clustering | 1 npz = 1 deck seed = **1 game** (144 positions). All uncertainty (Wilson, bootstrap CIs) and the out-of-sample split are **by game**, never by row. n_games is the effective sample. |
| Draws | 9,211 / 474,815 positions (1.94%) — scored as p_win = 0.5. |

### ⚠️ Margin-definition caveat (read this)
The utility being audited consumes the **v2.9 leaf margin** = *score-if-ended-now* including
closure/farm bonuses, **not** the raw on-board diff. The npz store only the raw diff (per-position
leaf values are not persisted; reconstructing them would require re-running `flat_leaf` on rebuilt
engine states — a follow-up). Consequences:

- The **global** finding (best T ≈ 31 ≫ 15, i.e. "the curve is 2× too steep") is **partly a raw-vs-leaf
  artifact**: the leaf margin adds the pending-feature value that makes a raw lead lag the true
  position value, so under the leaf margin the best global T would sit **closer to 15**. *Do not read
  this as "change /15 to /31 in production."* The correct global norm must be re-measured on the leaf
  margin.
- The **stage-dependence** direction is robust to the margin definition (both proxies grow more
  decisive as tiles→0), but its **magnitude** under the leaf margin is plausibly **smaller** (the leaf
  margin already absorbs some early-game "a lead means less"). So the 7.7% stage share here is an
  **upper bound** on the deployed utility's stage effect.
- The **saturation** finding (below) *is* robust — it is a property of the `tanh` shape at large \|m\|,
  and large leaf margins occur too.

---

## Method
Pure-numpy (no scipy/sklearn on this box), seeded (`--seed 1234`). Script: `calibrate_utility.py`.
- **Buckets:** margin in [−40,40] by 5 (tails clipped); tiles-remaining bands 60-72 / 45-59 / 30-44 /
  15-29 / 6-14 / 1-5.
- **Per bucket:** p_win (draws=0.5), n_games, Wilson 95% interval, mean margin, `tanh(m̄/15)` prediction.
- **Per-stage norm fit:** T minimizing soft-label Bernoulli log-loss of `p = ½(tanh(m/T)+1)`; 95% CI by
  **bootstrap over games** (n=200).
- **Out-of-sample:** 2-fold split **by game** (seed), fit on one half, evaluate log-loss & Brier on the
  held-out half, averaged over both folds. Four models:
  - **M0** `tanh(m/15)` — the audited utility;
  - **M1** `tanh(m/T*)` — single best global T (isolates a stage-invariant rescale);
  - **M2** `tanh(m/T_stage)` — per-stage T (the stage-dependent utility on test);
  - **M3** per-stage **isotonic** (nonparametric shape upper bound).
  The stage interaction's true value = **M1→M2** (gain *beyond* just fixing the constant), not M0→M2.

---

## Sanity gate (sign / join correctness)
- P(win | margin>0, ≤5 tiles) = **0.787**; P(win | margin<0, ≤5 tiles) = **0.227** → symmetric
  (0.787 ≈ 1−0.227) ⇒ sign/POV correct.
- P(win | margin>15, ≤5 tiles) = **0.896** — a big endgame lead wins ~90%, *not* 100%, because raw
  on-board margin excludes end-of-game farm/incomplete scoring that still flips ~10% of these. This is
  the raw-margin caveat made visible, not a bug.

---

## Empirical surface — the "same margin, different stage" contrast
p_win by (margin bucket × stage band); columns left=opening → right=endgame; `tanh/15` is the single
stage-invariant prediction. Full machine-readable table: `calibration_surface.csv`. Helper:
`stage_contrast.py`.

```
    margin  tanh/15 |     60-72     45-59     30-44     15-29      6-14       1-5  | spread
   [-15:-10)   0.16 | 0.45( 371) 0.40(1718) 0.37(2078) 0.31(1829) 0.27(1240) 0.26( 831) | 0.19
     [-5:0)    0.42 | 0.47(2504) 0.48(2591) 0.48(1984) 0.47(1549) 0.47(1021) 0.46( 693) | 0.03
      [0:5)    0.58 | 0.51(3300) 0.52(2848) 0.53(2195) 0.55(1754) 0.55(1182) 0.56( 806) | 0.05
     [5:10)    0.73 | 0.57( 993) 0.56(2403) 0.58(2351) 0.64(1947) 0.67(1282) 0.69( 884) | 0.12
    [10:15)    0.84 | 0.53( 229) 0.61(1413) 0.64(1855) 0.72(1693) 0.76(1195) 0.76( 823) | 0.23
    [15:20)    0.91 | 0.58(  14) 0.63( 496) 0.72(1128) 0.76(1356) 0.82(1015) 0.83( 707) | 0.25
    [20:25)    0.95 |    -       0.64( 144) 0.77( 617) 0.82( 889) 0.84( 754) 0.86( 576) | 0.22
    [25:30)    0.98 |    -       0.72(  41) 0.82( 277) 0.85( 580) 0.90( 551) 0.92( 420) | 0.20
```
(n_games in parentheses.) Two effects are visible, and the **stage-invariant** one is larger:

1. **Global overconfidence + saturation (dominant, stage-invariant).** `tanh/15` overstates win-prob
   for *every* stage at any real lead. A +12 lead: predicted **0.84**, actual **0.53-0.76**. By m≈25 the
   utility is pinned at **0.95-0.98 and flat**, while true win-prob is **0.64-0.92 and still rising** →
   the utility has thrown away discriminating gradient exactly where the review predicted (≥±30).
2. **Stage interaction (secondary, real).** At a fixed +10-25 lead, later stages win 0.15-0.25 more
   often than earlier ones (spread grows with |margin|). Monotone, but concentrated in the
   less-frequent large-margin cells.

---

## Per-stage norm T (the headline fit)
| tiles band | T | 95% CI (bootstrap-by-game) | n_games |
|---|---|---|---|
| 60-72 (opening) | 62.9 | [45.4, 70.0]† | 3300 |
| 45-59 | 57.8 | [47.5, 70.0]† | 3300 |
| 30-44 | 39.7 | [35.3, 43.5] | 3300 |
| 15-29 | 29.6 | [27.1, 31.2] | 3300 |
| 6-14 | 23.9 | [23.0, 25.1] | 3300 |
| 1-5 (endgame) | 22.5 | [21.0, 23.0] | 3300 |

- **Monotone decreasing** opening→endgame: a given raw lead becomes steadily more decisive as the game
  ends. Adjacent **late** bands have **non-overlapping CIs** (30-44 vs 15-29 vs 6-14 vs 1-5) → the
  variation is real, not noise.
- **Every** band's T > 15 → `tanh/15` is too steep at every stage (on the RAW margin; see caveat).
- † The two opening bands are **weakly identified** (opening margins cluster near 0, the flat part of
  `tanh`, so T is barely constrained) and are **unstable out-of-sample** (fold A T=81 vs fold B T=52 for
  60-72). Bands 30-44→1-5 are stable across folds (A: 40/30/24.5/22; B: 39/29/23/23). So the *robust*
  signal is the mid→endgame monotone descent ~40→22.5 (**1.8×**), not the full 2.8× that includes the
  noisy opening.

---

## Out-of-sample decomposition (the arbiter)
2-fold by game, averaged:

| model | held-out log-loss | held-out Brier |
|---|---|---|
| M0 `tanh(m/15)` (audited) | 0.6696 | 0.2263 |
| M1 `tanh(m/31)` best global | 0.6254 | 0.2144 |
| M2 `tanh(m/T_stage)` stage-dependent | 0.6217 | 0.2130 |
| M3 per-stage isotonic (shape bound) | 0.6227 | 0.2133 |

- **Global rescale (M0→M1):** ΔLL **0.0442**, ΔBrier **0.0120** — large. Just picking a better *constant*
  norm fixes most of the miscalibration.
- **Stage-dependence (M1→M2):** ΔLL **0.0037**, ΔBrier **0.0014** — small; **7.7%** of the total LL fix.
- **M2 ≈ M3** ⇒ a per-stage `tanh` already captures essentially all the recoverable *shape*; nothing
  is being left on the table by the parametric form.

---

## GO / NO-GO
**NO-GO for funding a stage-dependent utility experiment as the next step.** Reasons, with effect sizes:

1. Beyond a *stage-invariant* rescale, stage-dependence buys only **0.004 nats / 0.0014 Brier**
   out-of-sample (**7.7%** of the calibration gap). Not material by the OOS criterion the review set.
2. The stage spread is largest (0.15-0.25) at big leads that are **rare and already fairly decided**,
   and ~0 (0.03-0.05) at the near-tied positions that dominate the data and the search's hard choices.
3. The whole measurement is on the **raw** margin, not the **leaf** margin the search uses; the leaf
   margin already absorbs part of the early-game discount, so the true stage effect is **≤** what's
   measured here (7.7% is an upper bound).

**What to fund instead (the audit's actionable finding):**
- **(a) Re-run this exact audit on the true v2.9 leaf margin** (re-emit root/leaf values from a small
  self-play batch, or reconstruct states and call `flat_leaf`). This is the cheap prerequisite that
  tells you whether *any* recalibration is warranted in production, and by how much.
- **(b) If a gap survives, soften the GLOBAL norm** (a single scalar, or an unsaturating link) —
  stage-invariant, captures ~92% of the recoverable calibration, and directly fixes the review's real
  and robust concern: **`tanh/15` saturates by ±25-30 and loses gradient** between winning-but-different
  leaves. Re-tune search hyperparameters after any norm change (bug-fix-shifts-optima rule).
- **(c) Only revisit stage-conditioning** if the leaf-margin audit still shows a material residual
  stage term after the global norm is corrected. On this evidence it will not.

---

## Cross-check vs prior ONLINE evidence (added by the main session)
The C4 value_norm bracket (results.csv rows `rr_puct2750-vn{8,30}_vs_puctchamp2750_k2`, 2026-07-07)
already played `value_norm=30` (≈ this audit's raw-margin T*≈31) against the vn=15 champion in games:
**−36.6 elo (n=200, paired z=−0.66)** — a weak null, mildly negative, not a confirmation of the
calibration gap. vn=8 was also negative (−24.4, z=−0.80). Two readings are consistent: (i) the
raw-vs-leaf artifact explanation is right and the deployed leaf-margin norm is near-correct — the
leaf-margin re-run adjudicates; (ii) calibration ≠ strength: a better-calibrated VALUE need not win
games when both sides share the same search family (F7's offline↔online dissociation, again). Either
way, (b) must clear a fresh online gate before touching production; the C4 wings temper expectations.

---

## Reproduce
```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 \
  .venv/bin/python measurement/utility_calibration_20260719/calibrate_utility.py \
  --cap-per-iter 300 --n-boot 200 --seed 1234
python measurement/utility_calibration_20260719/stage_contrast.py
```
Outputs (this dir): `calibration_surface.csv` (the fitted surface),
`calibration_stats.json` (all fitted T, CIs, OOS metrics), and this `REPORT.md`.
Runtime ≈ 3.5 min single-process on the local box.
