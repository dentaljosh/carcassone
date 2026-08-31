# Post-flattening W re-sweep — LAPTOP half, ARB-ON-BOTH-SIDES cell shape

**STATUS: COMPLETE (2026-08-31).** Throughput-only; **no claim, no band, no elo, no
results.csv row.** Every cell played THROWAWAY seeds under a `SMOKE_` out-subdir, so
nothing here is adjudicable.

## ⭐ SETTLED: **W_LAPTOP = 26**

Launch the H2H on the laptop at `--workers 26`.

The throughput curve **rises to 26 and is then dead flat**: W26 ≈ W28 ≈ W30 to within
±0.5% (all pairwise |z| < 0.6). W26 is the **smallest W on the measured plateau** — the
knee, not an argmax spike.

> ⚠️ **The house rule's letter and its intent disagree here, and the disagreement is
> disclosed rather than resolved silently.** "Settle the SMALLEST W within ~5% of peak"
> read literally selects **W22** (95.3% of peak). But W22's deficit is **4.73%, 95% CI
> [4.48%, 4.98%]** — it *straddles* the 5% bar rather than clearing it, and it is
> resolved at z = −36, so it is a real 4.7% of wall clock, not noise. The rule's purpose
> ("don't pay for a noisy argmax; leave the box usable") is served by W26: it is the
> cheapest point on a 3-point plateau, and the laptop is an exclusive tenant for the
> H2H with no interactive-use claim on the spare threads.
> **If the orchestrator prefers the rule's letter, W22 is the fallback and costs ~4.7%
> wall clock.**

## Workload — the H2H's exact shape

Verified off the **emitted `manifest.json`**, not restated from the command line:

| | |
|---|---|
| harness | `scripts/classical_search/eval_fair_puct.py`, `--opponent fair-champion`, `--paired` |
| budget | **k16×1376 = 22016 BOTH sides** (`opp-k-dets 16`, `opp-sims 1376`) |
| tie arbiter | **ARMED BOTH SIDES**, deployed dict: B=64, J=4, argmax, salt `tiearb2-deploy-v1`, eps 0.0, phase_gate `all` (`--cand-tiearb-*` **and** the new `--opp-tiearb-*`) |
| candidate-only knob | `--cand-fpu-reduction 0.2` (opponent `fpu_reduction: null`) |
| rules | `fixed_v1` + `CARCASSONNE_FIX_R9=1` (manifest `r9_env_ok: true`) |
| backend / endgame | rust, `rust_threads=1` per worker, `--exact-k 2` marginalized |
| leaf | `a36d2e15a3b3d71d` (curve125), both sides |
| wheel | `carc_rs-0.1.0+395b76700ab1`, binary sha `a9bb2311ab9a635d` — **identical to the local box's** |
| src rev | `ba159c2aab` (laptop bundle-synced from `395b76700a` for the `--opp-tiearb-*` plumbing; **rust untouched between the two revs**, so no wheel rebuild) |
| seeds | throwaway `167999999000`–`167999999038` (39 decks × 2 seatings) |

## Method — identity-gated, deck-PAIRED

⚠️ **The single most important design choice.** Per-game wall time varies ~40%
deck-to-deck and seat-to-seat. With **disjoint** seed ranges per W point, the SEM on a
~30-game point is ~7% — which would swamp the 5%-of-peak settle threshold outright. So
**every W point plays the SAME 78 games from the SAME throwaway deck set** (games are
bit-identical at any W, so this costs nothing), making the ladder a deck-paired
contrast. Realized SEM: **1.7–1.9% per point**, and the paired per-game contrast
resolves a 4.7% difference at **z = −36**. This copies the discipline of the
pre-flattening `wgap_profile_laptop` harness, which also held decks fixed across W.

Estimators (the first-completions order-statistic trap is handled by never reading a
rate off the earliest finishers):

- **P (primary)** — `3600·W / mean(elapsed_s)` over the **steady set** = completions
  ordered by finish time, indices `[0, n−W−1]`, i.e. the **drain** (last W completions)
  dropped. The pool is saturated from t=0 because n=78 ≫ W, so there is no ramp to drop.
  Restricted to the games common to every point's steady set (48 games).
- **A** — same but over each point's own steady set (unpaired).
- **satur** — wall-clock rate from launch to the last steady completion (includes
  process startup, hence lower).
- **gross** — `n / point_wall_s`, drain included; context only.

Exclusive tenancy verified before each point (census by **FULL ARGS**, not `-C python`);
loadavg and free memory sampled every 20 s throughout.

## Points

| W | paired g/h | SEM | steady g/h | satur g/h | gross g/h | s/game | % of peak | loadavg | procs in R | min free MB |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 18 | 121.3 | 1.89% | 119.4 | 102.9 | 113.5 | 29.7 | 89.6% | 18.01 | 18 / 18 | 10104 |
| 22 | 129.0 | 1.69% | 126.9 | 106.9 | 120.0 | 27.9 | 95.3% | 22.05 | 22 / 22 | 10038 |
| **26** | **135.4** | 1.71% | 132.6 | 107.5 | 126.1 | **26.6** | **100.0%** | 26.00 | 26 / 26 | 9976 |
| 28 | 135.3 | 1.71% | 135.0 | 111.3 | 126.5 | 26.6 | 99.9% | 27.97 | 28 / 28 | 9934 |
| 30 | 135.3 | 1.74% | 135.3 | 103.2 | 126.1 | 26.6 | 99.9% | 29.97 | 30 / 30 | 9871 |

All five points `rc=0`, 78/78 games each. Wall per point 2219–2474 s. Memory was never
a constraint (≥9.8 GB free of 11.7 GB at every W).

### Paired per-game contrasts (log-ratio, 95% CI)

```
W18 vs W22:  −5.65%  [−6.45, −4.84]  z=−13.33
W18 vs W26: −10.16%  [−10.98, −9.35] z=−23.14
W22 vs W26:  −4.73%  [−4.98, −4.48]  z=−36.33
W22 vs W30:  −4.72%  [−5.21, −4.24]  z=−18.53
W26 vs W28:  +0.11%  [−0.29, +0.51]  z=+0.53   ← plateau
W26 vs W30:  +0.04%  [−0.46, +0.55]  z=+0.16   ← plateau
W28 vs W30:  −0.07%  [−0.64, +0.50]  z=−0.24   ← plateau
```

The peak is **bracketed**: rising 18 → 22 → 26, flat 26 → 28 → 30. (The crude ladder
{18,22,26} peaked at its own endpoint, which is not a peak; W30 and W28 were added for
exactly this reason.)

## Prior check — did oversubscription's edge move?

⚠️ **First, correct the premise.** The laptop is **24 threads** (`nproc`), not 16. So
W26/W28/W30 are 1.08× / 1.17× / 1.25× oversubscribed, not 2×.

**Prior evidence (all arb-OFF or arb-one-sided — this is the first arb-on-both-sides W
data on this box):** `/mnt/c/carc-shared/wgap_profile_laptop/pt_L_w{2,8,14,16,22,24}`,
2026-08-30, **pre-flattening** wheel `23bbf834`, budget **11008**, arbiter on the
**candidate only**, n=W (single wave):

```
  W   n   wall_s   games/h   %peak   conc_running_mean
  2   8    458.9      62.8   20.5%       1.87
  8   8    163.1     176.6   57.6%       5.97
 14  14    210.1     239.9   78.3%      10.83
 16  16    231.2     249.1   81.3%      12.00
 22  22    270.5     292.7   95.5%      17.72
 24  24    281.9     306.5  100.0%      19.57
```

⚠️ **There was no measured pre-flattening "W22 knee."** That ladder was **still climbing
at its endpoint W=24** and was never extended. W_LAPTOP=22 is the owner's standing
Shabbos-envelope default (2026-08-28, "we should default to w22 laptop w30 local"),
which the ladder happened to be consistent with (W22 = 95.5% of W24). Recording it as a
knee would have been an unbracketed-endpoint error.

**What moved — the mechanism, measured:**

- **Pre-flattening at W=22 only 17.72 of 22 workers were RUNNABLE** — 4.3 workers' worth
  of the pool stalled at any instant. That stall is precisely the slack that
  oversubscription exists to hide.
- **Post-flattening the pool is fully runnable at every W tested**: median processes in
  `R` state = 18/18, 22/22, 26/26, 28/28, 30/30. The DRAM stall flattening was meant to
  remove is **gone**.
- **And with it, the oversubscription edge.** Past ~the thread count the curve is dead
  flat: 26 → 28 → 30 buys **+0.11% / +0.04% / −0.07%** (all |z| < 0.6, CIs ±0.5%). The
  pre-flattening *local* finding that motivated this sweep — **W36 +5.3% over W30** at
  the descheduling boundary on the 32-thread box — has **no analogue here**: at 1.08× →
  1.25× oversubscription the laptop gains nothing measurable.

**⇒ The prediction is CONFIRMED. Oversubscription's edge compressed to zero on the
laptop:** there is no longer any stall for extra workers to hide, so W past the core
count is free but worthless. What *did* move the default is the other direction — the
saturation point sits at **26, not 22**, and the incumbent W22 is leaving **4.7%** of
laptop wall clock on the table (z = −36).

⚠️ **Scope.** Laptop only, arb-on-both-sides, 22016, wheel `+395b76700ab1`. The local
box's W is **not** re-measured here and the pre-flattening local W36-over-W30 result is
**not** refuted by this — it is a different box, a different cell shape and a different
code era. The local half of the sweep remains owed.

## Artifacts

- `points.jsonl` — per-point wall clock, rc, game count, timestamps
- `POINTS.json` — the estimator table above, machine-readable
- `PAIRED_DELTAS.txt` — all ten pairwise paired contrasts
- `wsweep_driver.sh` / `analyze_wsweep.py` / `paired_delta.py` — the instrument
- raw per-game records: `/mnt/c/carc-shared/fpu_ladder/SMOKE_WSWEEP_W{18,22,26,28,30}/`
  (throwaway; `SMOKE_` prefix keeps them out of every adjudication)
- driver logs + resource samplers: `/mnt/c/carc-shared/wsweep_laptop_20260831/`
