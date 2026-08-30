# READOUT — CL-083 mechanism kill-gates (2026-08-30)

**STATUS: IN PROGRESS.** Census 2 is closed. Censuses 1 and 3 are computing.
Bars and definitions are read from `PREREG.md`, committed at `aa07fee0` **before**
any number in this file existed. Departures are logged in `DEVIATIONS.md`.

All three censuses are **judge-free** (CL-085) and **zero games** were played.

---

## §0 — Data-availability audit (decided before any statistic was computed)

The prereg's Censuses 1 and 3 both need **per-world root statistics** and **per-action
pooled visit distributions** for the champion at deploy budget. The audit of what is
banked:

| Corpus | What it banks | Usable for Census 1 / 3? |
|---|---|---|
| `measurement/e4_ply_pricing_20260827/targets.jsonl` | the 290 crux plies (game, ply, stratum, profile, actor, played action) | **Yes as the POPULATION.** Carries no search statistics. |
| `measurement/c1_pricing_prep/C1_PRICING.json` | 188 plies × `world_deltas` (per-world realized outcome deltas), `price`, `insample_gap_pts` | **No.** These are per-world *outcome* prices, not per-world *root search* statistics. No action-level Q or visit vectors. |
| `measurement/classical_search/MOVE_AGREEMENT_REPORT.json` (CL-070) | aggregated agreement rates only | **No.** |
| `/mnt/c/carc-shared/classical_search/move_agreement_k4_b28e9/records/` (CL-070, 2696 records over 898 roots) | per-root, per-budget-level: `q_argmax_action`, `pooled_top2_q_gap`, `sum_N`, `n_children`, `played_visit_share` | **No.** Pooled *summaries* only — no per-world stats (Census 1) and no per-action visit vector (Census 3, which needs the visits of a *specific tagged* action, not of the argmax). Two further disqualifiers even if it did: the corpus is `k_dets=4`, and it was generated under the **pre-curve125 leaf** (`v29_meeple_curve = -8,-4,-1,0,2,3,4,5`, leaf `7fc930b8…`), an evidence epoch behind the champion of record `a36d2e15a3b3d71d`. |
| `measurement/tiearb_20260816/per_position.jsonl`, `tiearb_widening_20260817/…` | the banked CRN matrices behind the arb_costopt racing analysis — arm-level judged aggregates per position (`arb`, `ora`, `rnd`, folds) | **No.** "Worlds" there are CRN *evaluation* worlds over a J-arm tie set, not the search's PIMC determinizations, and the values are judge-priced (CL-085 bars using them for a judge-free census). |
| repo-wide grep for `world_stats` / `per_world` / `root_stats_list` in `measurement/**/*.json{,l}` | only documentation strings inside `analyzer_evloss_*` | **No banked per-world root statistics exist anywhere in the repo or on the share.** |

**Decision (pre-compute).** Censuses 1 and 3 regenerate their inputs by lossless
`(deck_seed, action-prefix)` root replay — the standing measurement-infra path the task
explicitly licensed — calling the deployed `fair_agent.search_one_world` /
`_merge_root_stats` / `pooled_q_argmax` at k8×1376. Cost turned out small: 554 cells
(290 plies × 2 salts, split by profile leg) at ≈9 s/cell, ≈14 min wall on the idle
laptop at W18.

**CL-070's 898-root set is NOT folded in.** Its banked records lack both statistics the
censuses need, so including it would require regenerating 898 roots (≈2× the crux job,
≈25–30 min at the same W) *and* would still be a different evidence epoch (k4,
pre-curve125 leaf) and a different position distribution (champion self-play, not E4).
Per the prereg's data-availability clause this is recorded as a **precise missing
input**, not silently dropped: regenerating it is cheap in compute but is a
**cross-epoch** extension, and CL-068's cross-band humility plus CL-085's
family-relativity both argue against pooling it with the E4 crux read. It is
**available on request** as a separate leg; it does not change any bar below.

**Instrument checks (all legs).** Leaf hash resolved to `a36d2e15a3b3d71d` in every
process. `CARCASSONNE_FIX_R9` latched to each profile's `r9_env_expected`
(`fixed_v1` → 1, `walled`/`app_aug2` → 0). Pooled visit counts sum to exactly
11008 = the deploy budget on every cell. 0 replay desyncs, 0 recon failures.

---

## §2 — CENSUS 2 (CF-M1, setup-abandonment) — **VERDICT: CF-M1 KILLED**

*(numbered §2 to match the prereg's census numbering; it closed first because it needed
no regenerated search statistics.)*

**Artifacts:** `CENSUS2.json`, raw rows `out/C2_{fixed_v1,walled,app_aug2}.jsonl`,
harness `census2_followthrough.py`, analysis `analyze_census2.py`.

**Coverage.** 56 archives (`fixed_v1` 53 / `walled` 2 / `app_aug2` 1), **0 recon
failures** (every replayed final score matches the archive's recorded score),
642 setups — 336 champion, 306 owner. Primary window N = 12; 37 setups censored by
the game ending inside their window and dropped as pre-registered.

### The headline

| Window | owner abandonment | champion abandonment | **D = champ − owner** | 95% game-cluster CI |
|---|---|---|---|---|
| N = 6 | 0.7138 (n=297) | 0.6801 (n=322) | **−0.0337** | [−0.114, +0.043] |
| **N = 12 (primary)** | **0.4251 (n=287)** | **0.3679 (n=318)** | **−0.0572** | [−0.126, +0.020] |
| N = 20 | 0.2635 (n=277) | 0.2444 (n=311) | **−0.0192** | [−0.088, +0.052] |

**D ≤ 0 at every pre-declared window.** By the prereg's read rule — *"CF-M1 IS KILLED
if D ≤ 0 — the champion abandons its own setups no more than the owner does"* —
**CF-M1 is dead.** The champion does not merely fail to abandon more; the point
estimate runs the other way at all three windows.

### It is not a slice artifact

| Slice | D (N = 12) | n owner / champion |
|---|---|---|
| city | **−0.0740** | 212 / 175 |
| road | **−0.0224** | 75 / 143 |
| `fixed_v1` (the dominant rules epoch) | **−0.0584** | 269 / 298 |
| `walled` | −0.2115 | 13 / 16 |
| budget epoch k8×1376 (the 22k epoch) | **−0.0426** | 270 / 295 |
| budget epoch k4×688 | −0.2115 | 13 / 16 |
| budget epoch k16×1376 | −0.3571 | 4 / 7 |
| `app_aug2` | +0.5500 | 5 / 4 |

Every slice with a usable n is negative. The single positive cell is `app_aug2` at
n = 4/5 — one archive, and exactly the "carried by fewer than 20 setups" case the
prereg pre-committed to discount.

### The companions point the same way, and one of them is interesting

| Companion (N = 12, eligible setups) | owner | champion |
|---|---|---|
| mean own-growth events per setup | 0.683 | **0.811** |
| finished-in-window rate | 0.195 | 0.192 |
| still-open-at-window-end rate | 0.801 | 0.808 |
| **opponent-growth rate in the window** | **0.136** | **0.223** |

The champion follows through on its own setups **more** often (0.811 vs 0.683 growth
events per setup), on features that are equally often still live at the end of the
window — so the contrast is not an artifact of the champion's features being foreclosed
or completed at different rates.

The last row is a by-catch worth flagging and *not* part of any bar: when the
**champion** claims a feature, the **owner** extends it 22.3% of the time; when the
**owner** claims one, the champion extends it 13.6%. The owner reaches into the
champion's features at roughly 1.6× the rate the champion reaches into his. That is
consistent with — though in no way a test of — CL-083's invasion story, and it is a
purely descriptive count with no pricing attached (CL-084 forbids reading a gap off a
selected statistic).

### What this kills, and what it does not

**Killed:** the compute-first lens's proposed behavioral signature. There is no
"champion abandons its setups" phenomenon in the E4 record to explain, so a CF gate
built to price setup-abandonment has nothing to price. The next CF gate is **not**
licensed.

**Not touched:** this says nothing about whether *follow-through quality* differs, only
about follow-through *occurrence*. And the census deliberately scopes out farms and
cloisters (`PREREG` §Census 2), so it is silent on farm-side setup behaviour — which is
the stratum CL-083 already flags as its live counterevidence.

---

## §1 — CENSUS 1 (GT-M1, world-spread) — *computing*

## §3 — CENSUS 3 (SA-M1, contested-seed reachability) — *computing*
