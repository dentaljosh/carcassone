# G2 / CL-068 OWED CONFIRMATION — k4×344 (1376 sims) vs the DEPLOY champion

**STATUS: COMPLETE (2026-07-28). Cell ran to full n=400 deck-paired, 0 solver timeouts,
0 guard failures.**

**VERDICT: THE CONFIRM REFUTES THE SCREEN. Halving the deploy budget to 1376 is NOT free —
it costs −53.4 ± 17.6 elo, with BOTH statistics past 3σ negative (winrate z −3.05, deck-paired
margin z −3.54). `k4×344` FAILS pre-registered rule 6 ("costs < ~1σ") and is therefore NOT
proposal-eligible. Nothing to promote; `governance/PRODUCTION.yaml` untouched.**

Run by the experiment-runner session `c0b61ee1`, **laptop only** (`laptop-wsl`), W16,
`--shared-claim`, with `scripts/measurement_infra/run_watchdog.sh` armed on the box
(session-independent). No source file, `results.csv` row, or commit was touched by this run.

---

## What was owed, and why

[docs/PROGRAM_ROADMAP_2026-07-07.md](../../docs/PROGRAM_ROADMAP_2026-07-07.md) Track G / **G2**,
DECISIONS.md 2026-07-27 (**CL-068**), and
[PARETO_CURVE_PREREG.md](PARETO_CURVE_PREREG.md) §4 all record the same debt:

> **What is owed before anyone acts: a fresh-band n=400 confirmation of `k4×344` vs deploy**
> (bands 60/62/64e9 now burned). Only after that is a production proposal appropriate.

The original cell was the one actionable option on the whole Pareto curve — "1376 halves clock
usage to 14.6% for no resolvable strength cost" — and its own honest caveat was that
+0.9 ± 17.4 gives a 95% interval of ≈ [−33, +35], which rules out a *large* loss, not a
*moderate* one. **This run is that confirmation.**

---

## Design — identical to the original cell except the seed band

| | original screen (CL-068) | **this confirm** |
|---|---|---|
| exp_id | `pareto_k4x344_1376_vs_deploy` | `pareto_k4x344_1376_vs_deploy_CONFIRM` |
| candidate | fair champion `k_dets=4 × sims=344` = **1376** | same |
| opponent | deploy champion `k_dets=4 × sims=688` = **2752** | same |
| harness | `eval_fair_puct.py --info fair --opponent fair-champion --exact-k 2 --paired --shared-claim --no-results-csv` | same |
| n | 400 paired (200 decks × 2 seats) | same |
| leaf, both sides | frozen v2.9 curve125, `a36d2e15a3b3d71d` | same (`both_sides_curve125: true`) |
| endgame, both sides | marginalized, `exact_k=2`, `exact_budget=2000000`, `tt_cap=200000` | same |
| leaf env | `V25_CAP=8 V25_OPP_CAP=8 V25_DROP_THREE_OPEN=0 V25_MEEPLE_K=2.0 V25_VALUE_BLEND=0`, `USE_FLAT_LEAF/CY_LEAF/CY_REPR=1`, all BLAS pins = 1 | **byte-identical** — replicated from the original cell's `manifest.json` `env` block |
| **band** | **60e9** | **76e9 (fresh)** |
| boxes | local + laptop, W16 each | **laptop only**, W16 |
| code_rev | `0bfdc00` | `4e67f2b` |

Driver script (stable path, so the watchdog could re-exec it):
`/mnt/carc-shared/g2_confirm_launch.sh`. Out-dir:
`/mnt/c/carc-shared/g2confirm_k4x344_1376_vs_deploy_b76000000000` (share path differs by box).

> ⚠️ Note for the record: the original `k4×344` pareto cell was on band **60e9**, not 9.5e9.
> 9.5e9 belongs to the 2026-07-07 round-robin `rr_puct2750` lineage that CL-069 compared
> against; it is a different cell.

### Band selection (fresh, claimed before launch)

`results.csv` has no `seed_start` column (bands live in the `note` prose), so the authoritative
enumeration is the manifests. Performed before launch:

- **616** `manifest.json` files under `/mnt/c/carc-shared` (maxdepth 5) → every `"seed_start"`.
  Burned at/above 20e9: 20, 20.1, 20.2, 21, 22, 24, 25, 26, 28, 32, 40, 44, 46, 48, 50, 52, 54,
  56, 60, 62, 64, 66, 68, 70, **72**, **74**, 90, 91, 99 (×1e9, plus sub-band offsets).
- `results.csv` note-text scan → same set, nothing above 70e9.
- `/mnt/c/carc-shared/BAND_CLAIMS.txt` → 72e9, 74e9 (burned today, pre-`results.csv`), and 78e9
  (claimed by a concurrent session while I was reading).
- Repo + deep-manifest grep for `76000000000` → **zero** hits before launch.

**Chosen: 76e9.** Claim appended to `BAND_CLAIMS.txt`:

```
76000000000 G2_confirm_k4x344_vs_deploy (CL-068 owed fresh-band n=400) 2026-07-28 claimed-by-session-c0b61ee1
```

---

## Results

**166W / 7D / 227L over n=400 deck-paired (200 decks × 2 seats), band 76e9.**

| statistic | value | z |
|---|---|---|
| winrate | **0.4238** | **−3.05** |
| elo | **−53.4 ± 17.6** (1σ) | −3.05 |
| deck-paired mean seat-balanced margin | **−3.285 pts/deck** | **−3.54** |

95% CI on the elo: **[−87.9, −18.9]**.

Validity / cost detail:

| | value |
|---|---|
| candidate prefix ms/move | 1880 |
| opponent prefix ms/move | 3773 |
| **cost ratio cand/opp** | **0.50×** — independently confirms the halving really happened |
| solver s/game | candidate 24.6, opponent 25.9 |
| endgame latched | 400/400 games, both sides |
| solver timeouts | **0**, both sides |
| deck_hash mismatches | 0 |
| leaf hash guard | candidate = opponent = `a36d2e15a3b3d71d`, banner `BOTH SIDES curve125: YES` |

**Independent recompute:** I re-derived W/D/L, winrate, winrate z, elo, avg diff and the
deck-paired margin/z directly from the 400 per-game `seed*_a*.json` records, mirroring
`eval_fair_puct.py::_summary` formula-for-formula. Every figure matches `summary.json`
(the only difference is the 1σ constant: my 17.38 vs the harness's 17.58, a formula
detail, not a data disagreement).

Clock share is unchanged from the original cell's reported **14.6% of the 900 s tournament
clock** (prefix ms/move 1880 here vs 1928 there, a 2.5% difference).

---

## Original vs confirm

| | band | W/D/L | winrate (z) | elo ± 1σ | margin pts/deck (z) |
|---|---|---|---|---|---|
| original screen (CL-068) | 60e9 | 196/9/195 | 0.5013 (**+0.05**) | **+0.9 ± 17.4** | −1.032 (−1.26) |
| **confirm (this run)** | **76e9** | 166/7/227 | 0.4238 (**−3.05**) | **−53.4 ± 17.6** | **−3.285 (−3.54)** |

- **The two cells disagree at z −2.20** (difference −54.3 ± 24.7, independent bands, not
  deck-paired). That is a real inconsistency, not a rounding difference.
- **The margin statistic was consistent all along.** The original's deck-paired margin already
  leaned negative (−1.03, z −1.26); the confirm deepens it to −3.29 (z −3.54). It is the
  *winrate* reading — the dead-tie z +0.05 that made the headline — that did not reproduce.
  This is exactly the failure mode prereg rule 1 exists for.
- **The confirm lands slightly outside the original's own 95% CI** ([−33, +35]), i.e. the
  original was, if anything, an optimistic-tail draw.
- **Pooling is NOT licensed.** Under the same logic as pre-registered rule 3 (|z| ≥ 1 between
  the two cells blocks pooling), the heterogeneity here (|z| = 2.20) blocks it decisively.
  For completeness only, and **not to be cited as an estimate**: an inverse-variance pool of
  the two cells would give −26.0 ± 12.4.

---

## Verdict — "is halving to 1376 free?"

**No.** The claim "halves clock usage to 14.6% for no resolvable strength cost" **does not
survive its own confirmation.**

- On the fresh band, the halving costs **−53.4 ± 17.6 elo**, both statistics past **3σ**.
- Under **PARETO_CURVE_PREREG.md rule 6**, a sub-deploy config is proposal-eligible only if it
  costs **< ~1σ (≈17 elo)**. −53.4 is **3.1σ of cost**. `k4×344` is **NOT proposal-eligible**.
- ⇒ **Do not propose k4×344 for production.** The deploy budget (k4×688 = 2752, 26% of clock)
  stays. `governance/PRODUCTION.yaml` is untouched by this run.

### What this does to CL-068's findings

- **Finding 3 (the decision-bearing one) is UNCHANGED and if anything strengthened.** Search
  budget remains a closed lever for clocked play: going *up* buys nothing spendable (5504 =
  +12.2, n.s., at 46.6% of clock; the only real gain sits at 91%), and now going *down*
  demonstrably **costs**. The remaining clock levers are still G1 (pondering) and G3 (per-move
  cost), not sims.
- **Finding 1 ("FLAT-THEN-CLIFF") needs its low edge redrawn.** 1376 was the flat region's
  bottom rung purely on the +0.9 reading. With 1376 at −53.4, the flat region is
  **2752 → 5504**, and the cliff starts one rung *higher* than CL-068 drew it — between 1376
  and 2752, not between 688 and 1376. Note this makes the curve **more monotone**, not less:
  688 −37.5, 1376 −53.4, 2752 = 0 is *not* monotone, which is the one loose end below.
- **Finding 2 (optimal width grows with budget) is untouched** — it rests on deck-matched
  within-band contrasts, none of which this cell revisits.

### Loose end worth naming (do not paper over it)

The confirm puts 1376 (−53.4, band 76e9) **below** 688 (−37.5, band 62e9). Both are
cross-band comparisons of absolutes, which this project has been burned by twice (L2-2, and
CL-069's own supersession of the cross-band halving screen), and their difference is
−15.9 ± 24.7 = z −0.64, i.e. **not resolved** — so this is a shrug, not a contradiction. But
the honest statement of the curve's low end is now: *both 688 and 1376 are clearly worse than
deploy by roughly 40–55 elo, and their ordering relative to each other is unmeasured.* If
anyone wants the shape of the cliff, it needs one shared fresh band with 688 / 1376 / 2752
deck-matched — which is a new experiment, not a re-read of these cells.

---

## Validity notes

1. **Code drift between the original and the confirm — checked, and symmetric.** The original
   ran at `0bfdc00`; this ran at `4e67f2b`. `scripts/classical_search/eval_fair_puct.py` and
   `src/carcassonne_ai/` are **not** identical across that span (`+888` lines in the harness for
   `--opponent bare-net`; new `intra_reuse.py`, `meeple_equiv.py`; `fair_agent.py`, `mcts.py`,
   `heuristic_prior_mcts.py` touched). `engine/` is byte-identical. Two reasons this does not
   invalidate the cell:
   - Every added feature is **opt-in and defaults OFF** (`meeple_dedup=None`, `intra_reuse`
     per-agent flag, `bare-net` opponent mode); the `heuristic_prior_mcts.py` change is a
     refactor of `_prune_to_subtree` onto `NeuralMCTS.prune_to_subtree`, reached only when
     `reuse_tree=True`, which the champion sets **False**.
   - More importantly, **both sides of this cell run the same code**, so any residual
     behavioural drift is common-mode and cancels in a head-to-head.
   Still, the strict statement is: this is a fresh-band confirm at *current* code, not a
   bit-for-bit replay of the original.
2. **`code_rev` records `4e67f2bd2-dirty`.** The laptop's tracked `src/`, `engine/` and
   `scripts/classical_search/` are clean; the dirty flag comes from three untracked helper
   scripts (`_cl060_laptop*.sh`, `fair_ruler_rebase_launcher.sh`) and unrelated log/TSV churn.
   Nothing on the eval import path is modified.
3. **`CARCASSONNE_V29_MEEPLE_CURVE=-8,-4,-1,0,2,3,4,5` is exported and is INERT here** — kept
   only so the env matches the original cell byte-for-byte. A head-to-head auto-injects
   curve125 into **both** sides in-process; the manifest confirms
   `cand_leaf_hash == opp_leaf_hash == a36d2e15a3b3d71d` and `both_sides_curve125: true`, and
   the env `DEFAULT_CONFIG` leaf (`42af12fce22e1a0f`) has no rung in play.
4. **Single box.** The original was drained by two boxes work-stealing on one pool; this cell
   ran laptop-only. Irrelevant to the result (per-game records are independent and the CRN band
   is fixed by seed), relevant only to wall-clock: ~3.2 h at W16, 28.8 s/game aggregate.
5. **Watchdog exited cleanly** at `2026-07-28 12:27:12 DONE: 400/400 records` (log:
   `/home/doctor/g2_confirm_watchdog.log` on the laptop). It logged `healthy` at every 5-minute
   poll and never needed a relaunch. No G2 watchdog process remains alive.

---

## DRAFT `results.csv` row — NOT written by this run

Paste target: `experiments/results.csv` (header
`exp_id,date,game,code_rev,n,new_ckpt,new_c,new_cap,new_var,new_sims,old_ckpt,old_c,old_cap,old_var,old_sims,W,L,D,elo,sigma,avg_diff,src_dir,confidence,note`).

```csv
pareto_k4x344_1376_vs_deploy_CONFIRM,2026-07-28,base,4e67f2b,400,fair_champion_curve125_k4x344,1.5,8,fair_k4x344,1376,fair_champion_curve125_DEPLOY,1.5,8,fair_k4x688,2752,166,227,7,-53.4,17.6,-3.285,/mnt/c/carc-shared/g2confirm_k4x344_1376_vs_deploy_b76000000000,high,"G2/CL-068 OWED FRESH-BAND CONFIRMATION of k4x344 (1376 sims = 0.5x deploy) vs the deploy champion (k4x688=2752). n=400 deck-paired (200 decks) band 76e9, laptop-only W16. winrate 0.4238 (z -3.05), elo -53.4 +/- 17.6, deck-paired margin -3.285 pts/deck (z -3.54). BOTH STATISTICS REPORTED per house rule; BOTH past 3 sigma NEGATIVE. Cost ratio 0.50x deploy per move (1880 vs 3773 prefix ms/move) -- independently confirms the halving really happened. 0 solver timeouts both sides, endgame latched 400/400 both sides, both sides frozen curve125 a36d2e15, exact-K2, env byte-identical to the original cell's manifest. ==> REFUTES the original screen (pareto_k4x344_1376_vs_deploy, band 60e9, +0.9 +/- 17.4, wr z +0.05, margin z -1.26): the two cells differ by -54.3 +/- 24.7 (z -2.20) and the confirm sits outside the original's own 95% CI [-33,+35]. The original's MARGIN statistic already leaned negative (z -1.26); it was the winrate dead-tie that did not reproduce -- prereg rule 1 working as designed. Pooling BLOCKED by rule-3 logic (inter-cell |z|=2.20); an inverse-variance pool would be -26.0 +/- 12.4 and must NOT be cited as an estimate. VERDICT: 'halving the deploy budget is free' is REFUTED. k4x344 costs 3.1 sigma, fails PARETO_CURVE_PREREG.md rule 6 (<1 sigma), and is NOT proposal-eligible. NOT promoted; governance/PRODUCTION.yaml untouched. CL-068 Finding 3 (budget is a closed lever for clocked play) is unchanged and strengthened -- down now demonstrably costs. CL-068 Finding 1's flat region shrinks to 2752..5504. LOOSE END: this puts 1376 (-53.4, b76e9) below 688 (-37.5, b62e9), difference -15.9 +/- 24.7 z -0.64 = UNRESOLVED cross-band; the cliff's shape needs 688/1376/2752 deck-matched on one shared fresh band. Code drift 0bfdc00->4e67f2b checked: new features opt-in and default OFF, engine tree identical, and both sides share the code so drift is common-mode. G2_CONFIRM_READOUT_20260728.md."
```

Six-touch close-out this row would feed (**none performed by this run — all left to Joshua**):
results.csv row · DECISIONS index line · status stamp on
[PARETO_CURVE_PREREG.md](PARETO_CURVE_PREREG.md) §4 (the OWED debt is now DISCHARGED, and its
§3 headline needs a correction banner) · `governance/CLAIM_REGISTRY` flip on CL-068's
proposal-eligibility field · STATUS.md top block · the G2 roadmap line
(the ⚠️ OWED clause is now satisfied and its verdict inverted).
