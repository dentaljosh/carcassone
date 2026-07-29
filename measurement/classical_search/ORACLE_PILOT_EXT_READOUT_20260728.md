# ORACLE-SCORE PILOT — n=100 EXTENSION READ-OUT

**STATUS: COMPLETE (2026-07-28). 100/100 positions, 0 failed, `crn_verified_all: true`,
M=32 CRN-paired deck completions per position, `--oracle-sims 100`, ~81 min at W16 local
(4865 s for the 80 new positions).**

**VERDICT: THE DISTRUSTED MEAN SURVIVES A 5× EXTENSION. The 11008 pick is genuinely better
than the 2752 pick on the positions where they disagree — mean +0.7375 pts/position,
cluster-robust z ≈ 2.97 (root-collapsed, the conservative reading: z 2.45). ⇒ 2752 is NOT
at the knee; deeper search finds real improvements, corroborating CL-060's directly-measured
+49.85 elo. The full 628-position run is now UNNECESSARY — the question it was funded to
answer is answered at n=100. This banks UNDERSTANDING, not a deploy lever: CL-068 +
[TOURNAMENT_TIMING](../../docs/research/TOURNAMENT_TIMING_2026-07-26.md) stand — the extra
strength costs 11.2 s/move (91% of a 15-min sudden-death clock) and is clock-unusable.**

**SOLE REMAINING THREAT TO VALIDITY: same-family self-preference** (§6). Nothing measured
today excludes it. `governance/PRODUCTION.yaml` untouched; no `results.csv` row (this is not
an elo cell, consistent with the morning's decision).

Extends the morning's n=20 pilot, which was parked as *"underpowered vs an assumed 0.07-pt
effect, and the mean distrusted"* — DECISIONS 2026-07-28 (oracle-pilot entry, items 5–6);
[LEVER_INDEX](../../docs/LEVER_INDEX.md) §8 'clairvoyant-champion reference'. This document
**amends the mean**, not the sd: the sd deliverable (2.406 at n=100 vs 2.428 at n=20) is
unchanged and still on the memo's pessimistic branch. The parking decision rested on
distrusting the mean; that is the part that did not survive.

Data: `/mnt/c/carc-shared/classical_search/oracle_score_pilot/` (100 per-position records +
`manifest.json` + `summary.json`); log `oracle_score_pilot_ext.log` (this directory).

---

## 1. Headline — naive vs cluster-robust

The 628-record disagreement bank spans only **385 distinct roots** (a root can disagree
under more than one seed lineage / salt), so records are **not independent**. The sample of
100 records covers **89 distinct roots**: 78 roots contribute 1 record, 11 roots contribute
2. Every number below is computed from the 100 on-disk records.

| estimator | n / G | mean (pts) | se | **z** | two-sided p |
|---|---:|---:|---:|---:|---:|
| naive (record-level, i.i.d. assumed) | 100 | **+0.7375** | 0.2406 | **3.07** | 0.0022 |
| **cluster-robust sandwich, clustered on root** (G/(G−1) corrected) | 100 / 89 | **+0.7375** | **0.2486** | **+2.97** | **0.0030** |
| **root-collapsed** (one mean per root, unit-weighted — the conservative read) | 89 | **+0.5920** | 0.2416 | **+2.45** | 0.0143 |

**Cite the cluster-robust row.** Clustering costs almost nothing here — the design effect is
**1.067** (variance ratio CR/naive), because only 11 of 89 roots carry a second record. The
root-collapsed estimator moves the *point estimate* (+0.592 vs +0.738) rather than the
variance, because it down-weights the doubly-sampled roots, which happen to be positive on
average. Both readings clear 2σ; the conservative one clears it by less.

**Non-parametric confirmation** — 20 000 bootstrap resamples **of roots** (seed 20260728):

| bootstrap target | mean | 95% CI | P(mean ≤ 0) |
|---|---:|---|---:|
| record-level mean | +0.734 | [+0.251, +1.226] | 0.0014 |
| root-collapsed mean | +0.593 | [+0.123, +1.077] | 0.0069 |

**Sign test** (distribution-free, immune to the heavy tails): records **58 + / 36 − / 6 zero**;
roots **51 + / 34 − / 4 zero**, one-sided binomial p = **0.041**. Weaker than the mean-based
tests — the signal lives partly in magnitude, not only in sign — but same direction.

Robustness of the location estimate: median **+0.391**, 10%-trimmed mean **+0.660**, range
[−5.844, +7.219]. The mean is not one outlier's doing.

Sign convention throughout: **positive = the 11008 (deeper) pick scores better**, in engine
points, root-player POV, averaged over the same 32 deck completions for both picks.

---

## 2. The 1.91 → 0.74 regression is regression to the mean, not a recompute

**Verified: the first 20 records were NOT recomputed.** The extension launched with
`--resume` and logged `resume: 20 already done, 80 to go`. Re-reading the 20 morning records
off disk and re-running the morning statistic reproduces the morning summary **exactly**:

| subsample | n | mean | sd | se | z |
|---|---:|---:|---:|---:|---:|
| first 20 (morning, on disk today) | 20 | **+1.9141** | 2.4280 | 0.5429 | +3.53 |
| morning `summary.json` `mean_delta_pts` | 20 | **+1.9140625** | 2.4280 | 0.5429 | +3.53 |
| new 80 only | 80 | **+0.4434** | 2.3231 | 0.2597 | +1.71 |
| all 100 | 100 | **+0.7375** | 2.4058 | 0.2406 | +3.07 |

(Two morning-log lines looked like mismatches at 4-decimal tolerance — `+0.438` vs 0.4375
and `+3.812` vs 3.8125 — both are the log's 3-dp rounding of an exact eighth. No record
changed.)

**Is the shrink itself a finding?** No. The first-20-vs-new-80 difference is
**+1.471 ± 0.602, z 2.44** — but that split was chosen *post hoc precisely because the first
20 looked high*, which is the definition of a selection-conditioned contrast, so its nominal
z is not interpretable. Three things say "early-sample fluctuation":

- **The sample is nested and seeded.** All 20 morning rids are members of the 100-rid draw
  (`sample_seed: 20260728`, `include_solver_region: false`); the sampler is position-blind.
- **Covariates are balanced** — first-20 vs new-80: mean root ply 72.8 / 78.6 · `k_remaining`
  35.8 / 32.9 · `n_legal` 18.7 / 22.3 · `h200_top2_q_gap` 0.031 / 0.021 · phase mix
  6/7/7 vs 23/23/34 (early/mid/late). Nothing structural distinguishes the two halves.
- **The direction is the one winner's-curse predicts.** This project has now watched the
  same shape three times in a fortnight (c=3 "+47", flywheel it16 "+88.7", C3-intra "+40.1").
  A screen selected for being interesting shrinks on extension; the *sign* is what carries.

The honest statement is therefore: **the effect is real and roughly +0.6 to +0.75 pts per
disagreed decision, not the +1.9 the 20-position screen advertised.**

---

## 3. Strata (descriptive only — no stratum is a finding)

| stratum | n | mean | se |
|---|---:|---:|---:|
| phase early | 29 | +1.509 | 0.451 |
| phase mid | 30 | −0.244 | 0.424 |
| phase late | 41 | +0.910 | 0.353 |
| `h200_top2_q_gap` tercile 1 (0 – 0.0003) | 33 | +0.415 | 0.374 |
| `h200_top2_q_gap` tercile 2 (0.0003 – 0.0170) | 33 | +1.607 | 0.413 |
| `h200_top2_q_gap` tercile 3 (0.0170 – 0.2696) | 34 | +0.207 | 0.430 |

⚠️ **Do not promote any of these.** They are unpowered post-hoc splits of an already-small
sample, and the gap-tercile pattern is **non-monotone** (middle tercile highest, both ends
near zero) with no mechanism to explain it — the shape of noise on a three-way split, not of
structure. The mid-phase negative and the mid-gap positive are each ~1 stratum out of 3 or 6
looks. Recorded so a future re-open does not re-discover them and mistake them for signal.

---

## 4. Effect translation — an ORDER-OF-MAGNITUDE consistency check only

⚠️ **This arithmetic is a sanity check against CL-060, not a measurement, and it is not
additive-valid.** Each per-position delta is a *whole-game terminal margin difference*
produced by swapping **one** decision. Switching budget for an entire game does not sum
these — the swaps overlap, compete for the same board resources, and change each other's
continuations. The sum below is therefore expected to **overstate**. Treated as a
falsification test ("is +0.74 pts/disagreement absurdly large?") it passes; treated as a
price for budget it is wrong.

Inputs, all cited:

- **mean delta per disagreed decision** = **+0.7375 pts** (this run).
- **disagreement rate** `D_paired(2752, 11008)` = **0.2398** overall
  ([MOVE_AGREEMENT_REPORT.json](MOVE_AGREEMENT_REPORT.json), CL-070; the bank scored here
  *is* the D_paired disagreement set, so this is the right multiplier). Note the pilot memo
  assumed 0.30.
- **decisions per game per player** ≈ **71.5** — the CL-070 root bank spans plies 1…143 and
  the wrapper counts tile and meeple decisions as separate plies, so ~143 decisions per game,
  ~half of them the root player's.
- **pts ↔ elo.** [LUCK_FLOOR.md](../human_anchor/LUCK_FLOOR.md): per-game margin
  σ_game ≈ 22.2 pts, win-rate = Φ(e/σ_game). CL-060's **+49.85 elo** ⇒ wr 0.5713 ⇒ a true
  edge of **≈ 3.98 pts/game**. (The memo instead used the linear rate from
  `results.csv luckfloor_champ_k4x688_vs_greedy_n200_b54e9`, +27.40 pts/deck ↔ +478 elo ≈
  17.4 elo/pt — but that row sits at **wr 0.94**, deep in the non-linear tail, so it is not a
  valid local rate near wr 0.5. On that rate CL-060 would be ≈2.86 pts/game.)

Forward (measured → predicted game advantage):

> 0.7375 pts × 0.2398 × 71.5 decisions ≈ **+12.6 pts/game**

Backward (CL-060 → implied per-disagreement effect):

> 3.98 pts/game ÷ (0.2398 × 71.5 ≈ 17.1 disagreements) ≈ **+0.23 pts/disagreement**
> (≈ **+0.17** on the memo's linear rate)

**Read:** same sign, same order of magnitude. The naive additive sum overshoots CL-060 by
**≈3.2×** (≈4.4× on the memo's rate) — in exactly the direction non-additivity predicts, and
small enough that the two measurements are consistent rather than contradictory. Equivalently:
the measured +0.7375 is **3–4× the per-disagreement effect that would exactly reproduce
CL-060**, and **~10× the +0.07 pts the pilot's power arithmetic pre-registered**.

**Footnote on the 0.07.** The memo's own stated formula — "mean gain per disagreed move ×
0.30 disagreement rate × ~70 moves = pts/game" — applied to +50 elo on its own linear rate
yields **0.137**, i.e. ~2× the 0.07 it then used. So the pre-registered effect was
conservative by roughly 2× *before* the non-linear-rate and D_paired corrections. **This is
the whole reason the power calculation said "don't fund" while the observation says
"already resolved":** the probe was sized against an assumption ~10× below the truth. Worth
carrying as a reusable lesson — **a power calculation is only as good as its assumed effect,
and the pilot that measures the variance can also falsify the effect assumption.**

---

## 5. What this does and does not change

**Changes — the knee question.** CL-069/CL-068 showed the strength curve goes flat above
~2064–2752. CL-070 showed the *pick* still changes at 4× budget but could not say whether it
improves. **It improves.** So the flat top of the curve is not "the search has converged and
2752 is the knee" — deeper search is finding genuinely better moves, and the flatness is
(at least partly) the ruler. That corroborates CL-060's direct +49.85 ± 17.55 with an
instrument that has **no opponent, no elo, and no ruler compression at all**.

**Does NOT change — anything deployable.** CL-068 finding 3 and
[TOURNAMENT_TIMING_2026-07-26](../../docs/research/TOURNAMENT_TIMING_2026-07-26.md) stand
untouched: 11008 costs **11.2 s/move = 91% of a 15-min sudden-death clock**, and 8× is an
automatic loss. Budget remains an **unclocked-play knob only**. Nothing here is a promotion
candidate, and no `PRODUCTION.yaml` change is implied or proposed.

**Does NOT change — the sd.** 2.406 pts at M=32 (vs 2.428 at n=20), between-position variance
1.591 ⇒ sd floor ≈ 1.26 as M→∞, median CRN variance reduction 1.60×, 7/100 positions perfectly
paired, 0 identical afterstates. The memo's pessimistic branch is confirmed with 5× the data.
**The full 628-position run is not merely unfunded — it is now pointless**: it was designed to
detect +0.07 pts, and the effect it would have been chasing is ~10× larger and already
resolved at n=100. Running it would buy a tighter estimate of a quantity that changes no
decision.

---

## 6. The standing caveat — same-family self-preference (UNRESOLVED)

The oracle is **not independent of the thing it judges**. `V(afterstate | world)` is the
terminal margin after playing out with the **clairvoyant PUCT champion** — the same search
family, steered by the **same frozen curve125 leaf**, as the 2752 and 11008 agents whose
picks are being compared. A deeper same-family search may systematically prefer positions
that a same-family continuation then converts well, independent of true quality. That is
memo open-risk #1 (shared-leaf blindness) sharpened, and **nothing in today's data excludes
it** — a 5× extension tightens the mean against sampling noise, and self-preference is a
*bias*, which more samples make more precise rather than smaller.

Two distinct sub-threats, worth keeping separate:

1. **Family bias** (the live one). Shared search algorithm + shared leaf.
2. **Weak-continuation bias** (flagged in the manifest, secondary). `--oracle-sims 100` is
   *below* the per-determinization budgets under test (688 and 2752), so the oracle is not
   "a much deeper search" — it is a cheaper same-family search averaged over 32 worlds.

**Cheapest discriminating test — NAMED, NOT RUN, NOT FUNDED HERE.** Re-score a random ~30-
position subset with the **continuation policy swapped out of the family**, holding the world
seeds and the CRN pairing fixed: play the two afterstates out with the **Tier-1 greedy
`RuleBasedPlayer`** (v1 1-ply leaf, no search, no curve125 — the same rung used as the
opponent in `luckfloor_champ_k4x688_vs_greedy_n200_b54e9`). It shares **neither** the search
**nor** the leaf, so a surviving positive sign cannot be same-family self-preference. Cost is
trivial — greedy runs ~26 ms/move against the clairvoyant PUCT's seconds, so the whole
100 × 32 rescore is minutes, not hours, which makes it strictly cheaper than the pilot that
produced this document.

⚠️ **How to read that test if anyone runs it: as a SIGN check only, never a magnitude check.**
A Tier-1 continuation is a much weaker and much noisier oracle and carries its own bias
(weak play rewards positions that survive bad continuations). A sign flip would be damning;
a sign survival would exclude family bias without validating the +0.74 magnitude. The
weaker alternative — raising `--oracle-sims` to 400/800 on the same subset — addresses
**only** sub-threat 2, since the family is unchanged; do not mistake it for a discriminator.

---

## 7. Provenance

- Harness `scripts/measurement_infra/oracle_score_pilot.py` (STATUS banner updated with this
  read-out); launcher `oracle_score_pilot.sh`; `--resume` used, verified non-recomputing (§2).
- Local box only, W16, detached, `run_watchdog.sh` armed. 100/100 ok, 0 failed,
  `crn_verified_all: true` (deck-order hash asserted equal across the two picks for every
  world of every position).
- Analysis recomputed from the 100 on-disk records by the read-out session, not read off the
  harness summary — except `sd_delta_positions`, `mean_within_position_var`,
  `var_between_positions_est` and the projection table, which are quoted from
  `summary.json` and independently agree with the record-level recompute of the mean.
- **No claim row.** No CL id was ever issued for this probe. A parked-then-answered pilot that
  changes no production decision does not earn one; if the discriminating test in §6 is ever
  run and the finding is asserted as a claim, it gets a CL id then.
- **No `results.csv` row** — not an elo cell. Consistent with the morning's decision.
