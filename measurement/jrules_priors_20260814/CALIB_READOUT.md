# J-RULES SURFACE B — CALIBRATION READ-OUT

> **STATUS 2026-08-14: COMPLETE. 0 GAMES PLAYED.** A mechanical application of
> [CALIB_READ_RULE.md](CALIB_READ_RULE.md) §3, which was committed **before any flip rate
> existed**. No `experiments/results.csv` row, no band, no claim id, `governance/PRODUCTION.yaml`
> untouched. Machine-readable source of every number: [`calib/SUMMARY.json`](calib/SUMMARY.json).

## 1. The run

26 archives · **1,556 graded champion plies per arm** · `rules_profile_histogram`
`{walled: 2, app_aug2: 1, fixed_v1: 23}` · masks `[31]` (`J1|J2|J5|J6|J8`) · budget from each
archive's own stamp · `all_replay_scores_match: true`. Local box, W30, ~10 min wall.

## 2. §3.0 VALIDITY GATE — passed

| gate | evidence |
|---|---|
| `all_replay_scores_match` | **true** (`SUMMARY.json`) |
| not `partial` | no `--limit-*` used; no partial marker |
| production leaf hash | every arm stamps `leaf_hash a36d2e15a3b3d71d` |
| ⚠️ **INVERTED hash gate** (an arm's leaf hash must **equal** the champion's — surface B must NOT move the leaf) | **all three arms equal `a36d2e15a3b3d71d`** — and this is *runtime-enforced*: `jrules_priors_e4_replay.py:502` refuses any arm whose hash differs |
| positive control `_assert_surface_b_live` | *runtime-enforced* at line 491, once per grading subprocess, **before** any grading — it raises if dose 1.0 fails to move expansion priors vs dose 0. A completed 26-archive rollup is the evidence it passed on every subprocess. ⚠️ This control is load-bearing in a way no hash check can replace: **surface B moves no leaf hash, so a zeroed dose would otherwise grade a perfect champion-vs-champion null wearing the shape of a calibration.** |

⚠️ **CORPUS DISCLOSURE, recorded rather than argued away.** The calibration graded the **complete
archive bank as it stood when the run launched (26 archives)**. Five new E4 archives were pulled
mid-run (`3d69c5b8`, ~11:15) and are therefore **not** in this corpus; the bank is now 31.
**The fired branch is insensitive to this**: `d0p5` clears the bar on its point estimate *and* its
Wilson-95 **lower** bound (0.1146), and ~19 % more plies cannot drag 13.05 % under 10 %.
⛔ **This calibration is NOT re-run on the enlarged bank.** Re-running after the rates are known
and then choosing between two reads is precisely the forking path this project has paid for four
times; the rule was applied once, to the corpus it was launched against.

## 3. The ladder (decision statistic = the point estimate, per §2)

| rung | dose | flips / graded | **f** | Wilson-95 | lo ≥ 0.10? |
|---|---|---|---|---|---|
| **`d0p5`** | **0.5** | **203 / 1556** | **13.05 %** | [11.46 %, 14.81 %] | **yes** |
| `d1p0` | 1.0 | 266 / 1556 | 17.10 % | [15.31 %, 19.05 %] | yes |
| `d2p0` | 2.0 | 353 / 1556 | 22.69 % | [20.67 %, 24.83 %] | yes |

Monotone in dose, as expected. Phase split at `d0p5`: 141 tile plies / 62 meeple plies.

## 4. §3 branches, evaluated in order

- **§3.0 `VOID`** — does not fire (table above).
- **§3.1 `FINER-RUNG`** — fires iff `f(1.0) > 0.20` **strictly**. Measured **`f(1.0) = 0.17095`**
  ⇒ **does NOT fire.** No `d0p25` rung is added, and none may be added later: §3.1 is the only
  rung-addition this document authorises.
- **§3.2 `FUND-SMALLEST`** — ⭐ **FIRES.** Eligible rungs (`f ≥ 0.10`): `d0p5`, `d1p0`, `d2p0`.
  The rule funds the **SMALLEST DOSE whose `f ≥ 0.10`, not the largest `f`** ⇒
  **exactly one deploy cell at `jrules_prior_dose 0.5`, mask 31, scope `all`.**
  Its Wilson-95 lower bound is **0.1146 ≥ 0.10**, so the cell is **NOT labelled `marginal`** and
  no marginal caveat rides into the prereg.
- **§3.3 `NO-EXPRESSION`** — not reached.

## 5. What this does and does not buy

⚠️ **Clearing the bar buys RESOLVABILITY, NOT SAFETY** (§2, written before the numbers). The
anchors are unanimous and unfavourable: open-city flipped 10.09 % / 18.89 % and cost **−53.8 /
−190.3 elo**; surface A's floor rung flipped 23.65 % and its cell **lost** (−2.49 pts/deck,
budget-confounded). **A bigger flip rate is a bigger perturbation of the strongest evaluator we
have, never a bigger prize** — which is exactly why the rule funds the smallest qualifying dose.

⭐ One observation, **not** a statistic and **not** a prediction: at 13.05 % this cell perturbs the
champion's picks **less** than surface A's floor rung did (23.65 %), while testing an encoding that
can express what the static form structurally could not (J2's planning clause, the "he must already
be there" predicates, J5/J13's before/after, J8's margin at the decision node). The honest
pre-registered failure mode remains **sims-washout** (DESIGN §1), with CL-051 as the sole
counter-precedent where a lever null on one surface was a win on the prior surface.

## 6. What is owed before game 1

Promote [`DEPLOY_PREREG.md`](DEPLOY_PREREG.md) filling **dose 0.5** and the band;
claim a **fresh band**; per-box wheel + the `_assert_surface_b_live` control **on the box that
plays**; then n=800 deck-paired, fair PIMC k8×1376 both arms, `fixed_v1`+R9, rust, exact-K 2,
margin z primary, all 13 wiring gates — ⚠️ **with the liveness gate INVERTED for this surface: the
candidate leaf hash must EQUAL `a36d2e15a3b3d71d`, and the resolved `cand_jrules_prior.dose` in
the manifest is what proves the dose is live.** A moved leaf hash here is a defect, not evidence.
**Worker counts (owner directive):** laptop W22 · local W30.
