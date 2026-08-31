# Cache-key re-run diffs — this week's meeple-phase-sensitive banked verdicts

**Date:** 2026-08-30 (local 5900XT box) · **Framing: SUPERSEDE-BY-RERUN.**
No banked artifact was read-modified. Every banked file listed below is untouched on
disk; the re-run outputs live beside this file and are keyed to the branch and commit
they were produced from.

**The fix under test:** the default-ON injective `_legal_cache` memo key
(`CARCASSONNE_FIX_LEGAL_CACHE_KEY`, python-only), from worktree
`agent-abfe6c58e4ad5ba70`, branch `worktree-agent-abfe6c58e4ad5ba70`, commit
`74f8d520f315f54da8da2dd315a0967015cdceca`
(`measurement/legal_cache_key_20260830/FINDING.md`). Re-runs imported that worktree's
`src` + `engine` via `PYTHONPATH`; the runner printed
`carcassonne_ai.__file__` under the fix worktree and `_FIX_LEGAL_CACHE_KEY = True`
before any census ran.

Scope taken = the two artifacts `FINDING.md` §6 item **4** names by filename
(`census2_followthrough.py`, `fieldfate_census.py`), **plus** CL-083 Censuses 1 and 3
(`census13_rootstats.py`), which the brief asked for and which the window turned out to
fit. **Nothing was skipped.**

> ### ⚠️ Headline: every verdict STANDS. Censuses 1 and 3 are FLAGGED at the statistic
> ### level — their regenerated search statistics genuinely moved, but no bar flipped.

---

## 1. Verdict table

| Verdict | Statistic | Banked | Re-run | \|Δ\| | Verdict's margin | Read |
|---|---|---|---|---|---|---|
| **CL-083 Census 1 (GT-M1)** | `max_reach_excl_control` (the bar) | 0.3404 | 0.3457 | 0.0053 | bar 0.30; margin 0.040 → 0.046 | **STANDS** (verdict NOT KILLED) |
| CL-083 Census 1 | 200 of 306 scalars (diagnostics) | see §5 | see §5 | up to 3.66 | — | ⚠️ **FLAGGED** |
| **CL-083 Census 3 (SA-M1)** | branch B `P_wv given exists` | 0.8967 | 0.8913 | 0.0054 | bar 0.80; margin 0.097 → 0.091 | **STANDS** (verdict KILLED) |
| CL-083 Census 3 | compound `reachable_share` | 0.0691 | 0.0727 | 0.0036 | bar 0.20; margin 0.131 → 0.127 | **STANDS** (verdict KILLED) |
| CL-083 Census 3 | strata / budget-share diagnostics | see §5 | see §5 | up to 3 ranks | — | ⚠️ **FLAGGED** |
| **CL-083 Census 2 (CF-M1)** | **all 289 scalars in `CENSUS2.json`** | — | — | **0** | — | **STANDS** |
| CL-083 Census 2 | D, N=12 (primary) | −0.0572 | −0.0572 | 0 | bar is `D ≤ 0`; margin 0.0572 | **STANDS** |
| CL-083 Census 2 | D, N=6 / N=20 | −0.0337 / −0.0192 | identical | 0 | same bar | **STANDS** |
| CL-083 Census 2 | raw rows `C2_{fixed_v1,walled,app_aug2}.jsonl` | sha 3/3 | sha 3/3 | byte-identical | — | **STANDS** |
| **HP-M1 field-fate** | `auc.F_FIT_oof` | 0.6518183665176758 | 0.6518183665176758 | 0 | bar a = 0.70; margin 0.0482 | **STANDS** |
| HP-M1 | `auc.F_PF` | 0.6479581470946769 | identical | 0 | — | **STANDS** |
| HP-M1 | `auc.B_LEAF` / `auc.B_BAG` | 0.5609508329947176 | identical | 0 | — | **STANDS** |
| HP-M1 | `auc.d_F_FIT_minus_B_LEAF` | 0.09086753352295818 | identical | 0 | bar b = beats both | **STANDS** |
| HP-M1 | `n_rows_scored` / `n_pos` / `n_neg` | 199 / 107 / 92 | identical | 0 | — | **STANDS** |
| HP-M1 | `primary_universe.*` (n_rows, n_scoring, n_zero, n_games, zero_rate) | all | identical | 0 | — | **STANDS** |
| HP-M1 | `bars.c.perm_p_two_sided` | 9.999000099990002e-05 | identical | 0 | bar c | **STANDS** |
| HP-M1 | **bar a / b / c `pass`** | false / true / false | false / true / false | 0 | — | **STANDS** |
| HP-M1 | **`verdict`, `bars_failed`** | MECHANISM DEAD; `[a, c]` | identical | 0 | — | **STANDS** |
| HP-M1 | `bars.b…weak` | **true** | **false** | flag flip | — | ⚠️ **FLAGGED** |
| HP-M1 | `auc.F_FIT_oof_ci95` | [0.56566, 0.73238] | [0.56640, 0.73387] | 7.4e-4 / 1.5e-3 | — | ⚠️ **FLAGGED** |
| HP-M1 | `auc.ci95` / `ci95_bag` (d vs baselines) | [−0.0013757, 0.185105] | [+0.0039551, 0.184407] | 5.3e-3 / 7.0e-4 | crosses 0 → does not | ⚠️ **FLAGGED** |
| HP-M1 | `bars.c.mean_owner` / `mean_champ` / `delta` | 1.568719017587598 / 1.8709435269163632 / −0.3022245093287652 | …5994 / …3643 / …765 | ≈1.3e-15 | 0.302 | **STANDS** (float noise) |
| HP-M1 | `sp449.AUC_B_LEAF` / `AUC_B_BAG` | 0.5416975452065865 / 0.5413763006364279 | 0.5416967370441459 / 0.5413754924739873 | 8.08e-7 | diagnostic, no bar | **STANDS** |

Full machine-readable form, every scalar with its `abs_delta`: `DIFF.json`.

## 2. The FLAGGED rows, stated without interpretation

Three HP-M1 rows moved: the two bootstrap CI pairs, and the `weak` sub-flag that is
computed from one of them. **Every point estimate they are CIs around is bit-identical**,
and every bar's `pass` value and the round's `verdict` string are bit-identical.

The `weak` flip is mechanical: `weak` is set when the `d_leaf` CI lower bound is ≤ 0.
Banked lower bound −0.0013757; re-run lower bound +0.0039551. The bar-b `pass` value
(`true`) is unchanged in both.

**What is established about the cause, and what is not:**

* **ESTABLISHED — the census rows did not change.** Sorted as a multiset, the re-run's
  rows are **bit-identical to the banked rows** in all four row files:
  `rows_E4_fixed_v1` 418/418, `rows_E4_walled` 17/17, `rows_E4_app_aug2` 5/5,
  `rows_SP449_walled` 3080/3080. Not one row's content differs. What differs is the
  **order** the multiprocess pool emitted them in, which is why three of the four files
  have a different sha256 (`rows_E4_app_aug2` is single-game and matches byte-for-byte).
* **ESTABLISHED — the order is not reproducible even at the banked worker count.** The
  first re-run used `W=30`; a second was run at **`W=16`, the banked run's own worker
  count**, and produced a *third* distinct order (the banked run was on the laptop). Both
  re-runs' rows are the same multiset as the bank. The numbers in the table above are
  from the `W=16` run.
* **NOT ESTABLISHED — nothing here isolates the cache-key fix as the cause of the moved
  CIs, and nothing rules it in.** The bootstrap/permutation resampling consumes rows in
  file order, so a re-ordering alone is sufficient to move a CI endpoint. Separating the
  two would need a legacy-pinned (`CARCASSONNE_FIX_LEGAL_CACHE_KEY=0`) run at a fixed row
  order; that was not run inside this window. **Reported, not diagnosed.**

## 3. What each re-run actually executed

| Artifact | Command | Cost |
|---|---|---|
| CL-083 Census 2 | `census2_followthrough.py --profile {fixed_v1,walled,app_aug2}` then `analyze_census2.py --inputs out/C2_*.jsonl` | ~3 s |
| CL-083 Censuses 1 + 3 | `census13_rootstats.py --profile {fixed_v1,walled,app_aug2} --workers 18` then `analyze_census13.py --primary-profile fixed_v1` | ~50 min, 580/580 ok |
| HP-M1 | `fieldfate_census.py --corpus E4 --profile {fixed_v1,walled,app_aug2}`, `--corpus SP449 --profile walled`, then `fieldfate_gate.py --dir out --primary-profile fixed_v1` | ~6 s |

SP449 profile selection was **not** re-derived by the PREREG-1.1 ladder; the banked
`SP449_PROFILE.json` (`walled`) was reused, and the re-run reconciled 449/449 (100%) on
it, which is the ≥99% the ladder tests. E4 reconciled 53/53, 2/2, 1/1 — the banked
counts.

## 4. Loadavg / tenancy

`loadavg` 1.76 before / 2.79 after on the `W=16` re-run — that is this job's own 16
workers on a 32-thread box, decaying. No foreign tenant appeared in any census during
the window. Phase 2 is compute, not a timing bench, so contention is not a validity
threat here; the phase-1 timing benches were run as an exclusive tenant and are reported
separately in `../quiet_benches_20260830/`.

## 5. CL-083 Censuses 1 (GT-M1) and 3 (SA-M1) — **the material result**

These two do not read banked inputs. Per `READOUT.md` §0 they **regenerate** their
per-world root statistics by lossless root replay, calling
`fair_agent.search_one_world` / `_merge_root_stats` / `pooled_q_argmax` at **k8×1376**.
Re-run in full: **580 cells** (`fixed_v1` 554, `walled` 20, `app_aug2` 6), **580/580 ok,
0 replay desyncs, 0 recon failures**, leaf hash `a36d2e15a3b3d71d` verified in every
process, ~50 min wall at W18. Diffs: `DIFF_census13.json`.

### The bars — every one survives

| Census | Bar statistic | Bar | Banked | Re-run | \|Δ\| | Margin to bar | Read |
|---|---|---|---|---|---|---|---|
| **1 (GT-M1)** | `max_reach_excl_control` | survive ≥ 0.30 | 0.3404 | **0.3457** | 0.0053 | 0.040 → **0.046** | **STANDS** (NOT KILLED) |
| 1 | `already_agree_label` (U ≤ 0.50) | — | FALSE | FALSE | 0 | — | **STANDS** |
| **3 (SA-M1)** | branch B `P_wv given exists` | kill ≥ 0.80 | 0.8967 | **0.8913** | 0.0054 | 0.097 → **0.091** | **STANDS** (KILLED) |
| 3 | compound `reachable_share` | kill ≤ 0.20 | 0.0691 | **0.0727** | 0.0036 | 0.131 → **0.127** | **STANDS** (KILLED) |

Both `VERDICT` strings keep their verdict word and only move their quoted figure:
`GT-M1 NOT KILLED (max reach 0.340 → 0.346 ≥ 0.30)` and
`SA-M1 KILLED -- BRANCH B (0.897 → 0.891 ≥ 0.80); COMPOUND (0.069 → 0.073 ≤ 0.20)`.
Population sizes are identical (Census 1 n=188; Census 3 n=275, n_exists=184,
`P_exists` bit-identical), as are `mean_n_tagged`, `mean_n_legal`,
`P_best_seed_unvisited_given_exists` and `median_rank_of_best_seed` (primary).

### ⚠️ FLAGGED — the regenerated statistics genuinely changed

Unlike HP-M1, this is **not** a row-order effect. The C13 row files differ **as
multisets**, in all three profile legs (554/554, 20/20, 6/6 rows) — the replayed search
statistics themselves moved. 200 of 306 Census-1 scalars and a large fraction of
Census-3's differ. The largest movers, reported without interpretation:

| Statistic | Banked | Re-run | \|Δ\| |
|---|---|---|---|
| C1 `PRIMARY.mean_cvar_eligible` | 17.957 | **21.617** | **3.660** (≈20% relative) |
| C1 `PRIMARY.U_unanimous` | 0.3670 | **0.3138** | **0.0532** |
| C1 `PRIMARY.dissent_rate` | 0.6330 | 0.6862 | 0.0532 |
| C1 `PRIMARY.mean_agree_frac` | 0.6762 | 0.6589 | 0.0173 |
| C1 `COMPANION_control.U_unanimous` | 0.3448 | 0.3218 | 0.0230 |
| C1 `COMPANION_control.max_reach_excl_control` | 0.3333 | 0.3678 | 0.0345 |
| C1 `OTHER_PROFILE_LEG.walled.U_unanimous` (n=7) | 0.5714 | 0.4286 | 0.1429 |
| C3 `PRIMARY.mean_budget_share_of_best_seed` | 0.4136 | **0.3757** | **0.0379** (≈9%) |
| C3 `by_stratum.defense.median_rank_of_best_seed` | 5 | **8** | **3** |
| C3 `by_stratum.defense.P_wv_given_exists` | 0.6939 | 0.6735 | 0.0204 |
| C3 `by_stratum.invasion.mean_budget_share_of_best_seed` | 0.6277 | 0.5805 | 0.0472 |
| C3 `PRIMARY.n_seed_quartiles` | [0, 458, 3983, 8131, 11008] | [0, 320, 3401, 7560, 11008] | up to 582 visits |
| `instrument_faults.prereg_alpha1_control_disagreements` | 88 | **86** | 2 |

**What this establishes:** the fixed injective cache key changes the *meeple-phase
continuation set* the regenerated PIMC search sees, and that propagates into per-world
picks, CVaR eligibility and visit distributions at a scale of a few percent to ~20%
relative on individual diagnostics. **The bars are far enough from their thresholds
(margins 0.04–0.13 against shifts of 0.004–0.005) that none of them flips.**

**What this does NOT establish:** no attribution beyond "the re-run differs". These
censuses regenerate their inputs, so a legacy-pinned
(`CARCASSONNE_FIX_LEGAL_CACHE_KEY=0`) control leg at the same salts would be needed to
separate the cache-key fix from any other run-to-run variation in the replay. That
control was **not** run. Reported, not diagnosed.

Census 2, by contrast, needed no regenerated search statistics and came back
byte-identical — which is the cleanest available contrast: **the pure rules replay is
untouched by the fix; the search-regenerating censuses are not.**

## 6. Provenance

| Input | Source |
|---|---|
| the fix | worktree `agent-abfe6c58e4ad5ba70` @ `74f8d520f315f54da8da2dd315a0967015cdceca` |
| CL-083 banked | `measurement/cl083_mech_censuses_20260830/{CENSUS1.json,CENSUS2.json,CENSUS3.json,out/C{2,13}_*.jsonl}` |
| HP-M1 banked | `measurement/hpm1_fieldfate_gate_20260830/{RESULTS.json,rows_*.jsonl}` |
| re-run outputs | `CENSUS2_rerun.json`, `c13_rerun/{CENSUS1,CENSUS3}.json`, `cl083_out/`, `hpm1_out/`, `DIFF.json`, `DIFF_census13.json` (this directory) |

No `results.csv` row, no claim id, no `governance/PRODUCTION.yaml` field, no band.
