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
(`census2_followthrough.py`, `fieldfate_census.py`). One item is **SKIPPED** — §7.

---

## 1. Verdict table

| Verdict | Statistic | Banked | Re-run | \|Δ\| | Verdict's margin | Read |
|---|---|---|---|---|---|---|
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

## 5. SKIPPED

| Owed | Status | Exact blocker |
|---|---|---|
| **CL-083 Census 1 (GT-M1)** and **Census 3 (SA-M1)** — `census13_rootstats.py` | **SKIPPED** | These two censuses do not read banked inputs: per `READOUT.md` §0 they **regenerate** their per-world root statistics by lossless root replay, calling `fair_agent.search_one_world` / `_merge_root_stats` / `pooled_q_argmax` at **k8×1376** over **554 cells** (290 crux plies × 2 salts, split by profile leg) — the banked run measured ≈9 s/cell, **≈14 min wall at W18 on an idle box**. That does not fit the remaining window under exclusive-tenant discipline, and a half-finished cell set cannot be diffed against a complete bank. **Not attempted** — no partial artifact was written. `FINDING.md` §6 item 4 names only `census2_followthrough.py` from this round, so this is beyond the licensed list, but the brief asked for GT/CF/SA and it is recorded here rather than silently dropped. |

Census 2 was the census that needed no regenerated search statistics, and it is the one
that ran.

## 6. Provenance

| Input | Source |
|---|---|
| the fix | worktree `agent-abfe6c58e4ad5ba70` @ `74f8d520f315f54da8da2dd315a0967015cdceca` |
| CL-083 banked | `measurement/cl083_mech_censuses_20260830/{CENSUS2.json,out/C2_*.jsonl}` |
| HP-M1 banked | `measurement/hpm1_fieldfate_gate_20260830/{RESULTS.json,rows_*.jsonl}` |
| re-run outputs | `CENSUS2_rerun.json`, `cl083_out/`, `hpm1_out/`, `DIFF.json` (this directory) |

No `results.csv` row, no claim id, no `governance/PRODUCTION.yaml` field, no band.
