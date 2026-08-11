# MEEPLE-DEDUP + C3-INTRA (within-turn tree carry) — SCREEN RESULTS

**STATUS: COMPLETE (2026-07-28). Both screens run to full n=200 paired per cell.
SUPERSEDED IN PART — see the CONFIRM section at the bottom: intra-reuse was taken to
n=1200 across two fresh bands and DID NOT CLEAR. Read the confirm, not the screen.**

**VERDICT (screens): meeple-dedup DEAD AT SCREEN (not funded further). intra-reuse did not
clear the 2σ screen; the cost caveat is empirically discharged (ms-ratio 0.99x) and the
screen looked promising enough to fund a powered confirm.**

**VERDICT (confirm, the one that counts): intra-reuse DOES NOT CLEAR at n=1200 —
+16.2 ± 10.0 elo (z 1.62), paired +0.77 pts/deck (z 1.55), 95% CI [−3.5, +35.9] includes
zero. The screen's +40.1 was winner's curse, exactly as flagged. NOT ADOPTED.**

Run by the experiment-runner session `c0b61ee1`, local 5900XT-box + laptop, W16 per box,
work-stealing via `--shared-claim` on the shared out-root.

Scripts (unmodified, run as committed):
- `scripts/classical_search/meeple_dedup_screen.sh 16 <out-root> 72000000000 200`
- `scripts/classical_search/intra_reuse_screen.sh 16 <out-root> 74000000000 200`

---

## Bands (fresh, claimed before launch)

Both screens needed their OWN fresh CRN band — the opponent is the champion itself, which has
played every prior band, so cross-screen reuse would be a re-read of old noise.

Enumeration performed before launch (per the script headers):
- `grep -o 'seed_start[^,]*' experiments/results.csv` → **no matches**; results.csv has no
  `seed_start` column (header is `exp_id,date,game,code_rev,n,...`), bands are recorded in
  prose in the `note` column. The authoritative enumeration is the manifests.
- 386 `manifest.json` files under `/mnt/c/carc-shared` (maxdepth 5) → all `"seed_start"` values.
  Burned at/above 20e9: 20, 20.1, 20.2, 21, 22, 24, 25, 26, 28, 32, 40, 44, 46, 48, 50, 52, 54,
  56, 60, 62, 64, 66, 68, **70**, 90, 91, 99 (×1e9, plus sub-band offsets).
- Repo-wide grep for `72000000000` / `74000000000`: only two hits, both the float
  `0.07200000000000001` in unrelated leaf-residual JSON. No share dir or manifest uses either.

**Chosen: 72e9 (meeple-dedup), 74e9 (intra-reuse).** Both verified unused. Claim recorded at
`/mnt/c/carc-shared/BAND_CLAIMS.txt`:

```
72000000000 meeple_dedup_screen 2026-07-28 claimed-by-session-c0b61ee1
74000000000 intra_reuse_screen 2026-07-28 claimed-by-session-c0b61ee1
```

---

## Results — all four cells, n=200 deck-paired (100 decks × 2 seats)

Candidate = the flagged side (`--meeple-dedup` / `--intra-reuse`). Opponent = the SAME agent
with the flag OFF. Both statistics reported per house rule.

| screen | cell | total sims | band | n | W/D/L | winrate | ELO ±1σ | elo z | paired margin (pts/deck) | paired z | ms-ratio cand/opp |
|---|---|---|---|---|---|---|---|---|---|---|---|
| meeple-dedup | k2x172 | 344 | 72e9 | 200 | 110/4/86 | 0.5600 | **+41.9 ± 24.7** | +1.69 | +0.500 | +0.48 | 0.999x |
| meeple-dedup | k4x172 | 688 | 72e9 | 200 | 98/3/99 | 0.4975 | **−1.7 ± 24.6** | −0.07 | −0.200 | −0.20 | 1.010x |
| intra-reuse | k4x344 | 1376 | 74e9 | 200 | 96/5/99 | 0.4925 | **−5.2 ± 24.6** | −0.21 | +0.800 | +0.72 | 1.024x |
| intra-reuse | k4x688 | 2752 | 74e9 | 200 | 109/5/86 | 0.5575 | **+40.1 ± 24.7** | +1.62 | +1.650 | +1.32 | 0.994x |

Screen bar: n=200 paired → 1σ ≈ ±24.7 elo; a cell "clears" only at ~2σ (≈ ±50 elo).
**No cell clears.** Solver timeouts: **0** in all four cells; endgame latched 200/200 games on
both sides in every cell.

Supporting per-cell cost/quality detail:

| cell | cand prefix ms/move | opp prefix ms/move | cand solver s/game | opp solver s/game | mean game s |
|---|---|---|---|---|---|
| dedup k2x172 | 483 | 483 | 28.6 | 22.6 | 119 |
| dedup k4x172 | 972 | 963 | 30.3 | 26.4 | 192 |
| intra k4x344 | 1963 | 1916 | 21.8 | 23.2 | 316 |
| intra k4x688 | 3795 | 3819 | 22.2 | 18.1 | 573 |

My independent read-out (recomputed from the per-game records, mirroring
`eval_fair_puct.py::_summary` formula-for-formula) matches each cell's `summary.json` exactly.

---

## Exact configuration (identical across all four cells except the one flag)

From the cell manifests (`<out-dir>/manifest.json`):

- Harness: `scripts/classical_search/eval_fair_puct.py --info fair --opponent fair-champion
  --exact-k 2 --paired --shared-claim --claim-stale-secs 300 --no-results-csv`
- Agent both sides: `FairHeuristicPriorAgent`, `c_puct=1.5`, `tau_p=5.0`,
  `leaf_quantize=float`, `final_select=visits`, `value_norm=15.0`, priors
  `heuristic_softmax_dleaf_tau`, aggregation pooled-Q over `k_dets` determinizations.
- Leaf both sides: FROZEN v2.9 **curve125** production leaf, auto-injected in-process,
  `leaf_hash=a36d2e15a3b3d71d`, `frozen_config_hash=6dfffd57051690f2`.
  `both_sides_curve125: true` — confirmed in every cell's startup banner.
- Endgame both sides: marginalized, `exact_k=2`, `exact_budget=2000000`, `tt_cap=200000`.
- Leaf env: `V25_CAP=8 V25_OPP_CAP=8 V25_DROP_THREE_OPEN=0 V25_MEEPLE_K=2.0 V25_VALUE_BLEND=0`,
  `USE_FLAT_LEAF=1 USE_CY_LEAF=1 USE_CY_REPR=1`, all BLAS thread pins = 1.
- **The only asymmetry** is the per-agent flag on the candidate:
  - dedup: `meeple_dedup {enabled: true, prior_mode: fold, grouping:
    carcassonne_ai.meeple_equiv.feature_groups (INTRA-TILE only), applies_to: candidate}` —
    meeple-phase nodes only, keeps the lowest action id per group and folds the dropped
    members' prior mass onto it; the true legal mask is UNCHANGED.
  - intra: `intra_turn_reuse {enabled: true, flag: CARCASSONNE_INTRA_TURN_REUSE}` — carries the
    k_dets trees AND their determinized decks from a turn's TILE decision into the SAME turn's
    MEEPLE decision, re-rooted at the tile action played; any mismatch discards and searches
    fresh.
- Deviation warning emitted (expected, benign): the screen budgets are not the production
  budget, but BOTH sides use them, so the swap stays single-variable. **These cells are NOT
  "vs production"** — the opponent is the champion agent at the cell's budget.

---

## Verdicts

### meeple-dedup — **DEAD AT SCREEN. Do not fund the deploy-budget confirm.**

One line: *both cells fail the 2σ bar, the deeper cell is dead flat (−1.7, z −0.07), and the
cheap cell's +41.9 is contradicted by its own paired statistic (z +0.48) — a win-rate noise
signature, not a margin shift.*

The two statistics disagree in size by a factor of 3.5 at k2x172: 56.0% win rate (z +1.69) on a
mean seat-balanced margin of only **+0.50 points/deck** (z +0.48). A real strength gain moves
both; a coin-flip band moves the win rate alone. Per the house rule ("a lone value that beats its
neighbours by >1σ is a noise signature, not a peak"), and given that the *neighbouring, deeper*
cell is exactly zero, this reads as noise.

Honest caveat on the direction: the sign pattern (larger at 344 than at 688) is what the dilution
theory predicts, since splitting a small budget across a duplicated subtree costs proportionally
more. So this is "not demonstrated at screen power", not a proof of zero. But the lever's own
theory says the effect *shrinks* toward the deploy budget (k4x688=2752), and k4x172 already shows
it gone by 688. Resurrecting it would need n≥800 paired at the *cheapest* cell to chase an effect
the theory says is absent where we actually ship. Not worth it. **Recommend: kill, index in
docs/LEVER_INDEX.md as screened-and-dead.**

Cost note: ms-ratio 0.999x / 1.010x — the mask is cost-neutral, so there is no wall-clock story
that could rescue it either.

### intra-reuse — **DOES NOT CLEAR THE SCREEN at n=200, but NOT dead. Decision required.**

One line: *neither cell reaches 2σ, but the deploy-budget cell shows +40.1 elo (z +1.62) with the
paired statistic agreeing in sign (+1.65 pts/deck, z +1.32) at a measured cost ratio of 0.994x —
the effect grows with depth, which is what the search-efficiency theory predicts.*

Unlike dedup, the two statistics here **agree in sign and are both directionally positive at the
deploy budget**, and the effect is larger at the deeper cell (1376 → −5.2, 2752 → +40.1). That is
the opposite of a sims-washout profile and matches the header's prediction that a search-
efficiency effect should hold at depth. It is still only 2 points and neither is significant — a
2-point trend is not a ladder, and z +1.62 is exactly the region where the noisy-plateau rule
says "don't conclude either way."

**The mandatory read-out caveat, addressed.** The script header warns that at equal *nominal*
sims the ON candidate does more total work per turn (measured warm start ~34% of a fresh budget,
max ~81% at k4x172), so a positive delta could be "more effective search per turn helps" rather
than "the carry is free". I read the emitter before trusting the field (see below) and the
measurement does **not** support that confound at these budgets:

- `champ_prefix_ms_per_move` = **CANDIDATE** (the `--intra-reuse` side);
  `rung_ms_per_move` = **OPPONENT** — in the head-to-head branch it is computed from
  `opp_prefix_secs / opp_prefix_moves`, i.e. the opponent's own handoff prefix counters, NOT the
  driver-timed `rung_secs` (which would wrongly include one side's endgame solve; the emitter
  carries an explicit comment that doing so once made two identical agents look 4× apart).
- Measured ratio candidate/opponent: **0.994x at k4x688** and **1.024x at k4x344** — the
  candidate is, at the deploy budget, marginally *cheaper* per move, not more expensive. The
  carried subtree's simulations were already paid during the tile search; the meeple search's
  own `sims` budget is unchanged, so per-turn wall clock lands at parity.
- For reference, CL-044 (the across-move sibling) was accepted at ms-ratio **1.06**. These cells
  are tighter than that.

**So the cost caveat is empirically discharged: what this lever is missing is statistical power,
not time-matching.** I am nevertheless flagging, per the header's standing house rule, that
**an equal-wall-clock confirm remains formally mandatory before any positive intra-reuse result
is believed** — the screen's ms-ratio ≈ 1.0 is evidence that such a confirm would be a
near-no-op resize, but it has not itself been run, and this screen must not be read as a
strength result on its own.

**Calibration note that argues for caution AND for a proper test.** From the 2026-07-27 pareto
curve (`experiments/results.csv`), *doubling* the deploy search budget (5504 vs 2752, n=400) buys
only **+12.2 elo (z +0.70)**. A true +40 from a free within-turn carry would exceed the measured
value of 2× compute, which is a reason to suspect the point estimate is inflated by the winner's
curse at z +1.62 — and equally a reason that, if even a third of it is real, it is cheap elo.

**Recommended next step (NOT auto-funded — Joshua's call):** a single k4x688 cell on a FRESH band
at **n=600 paired** (1σ ≈ ±14 elo) would resolve a +40 effect at ~3σ and a +15 effect at ~1σ.
At the observed 573 s/game and 32 workers that is roughly 3 h wall-clock. n=400 (1σ ≈ ±17) is the
cheaper option at ~2 h but only resolves the effect if it is near the full +40.

---

## DRAFT results.csv rows — TEXT ONLY, NOT WRITTEN TO experiments/results.csv

Per the brief, `experiments/results.csv` was **not** touched. These are drafts for whoever does
the close-out. `code_rev` is the rev the games were played at (`dcd7c96`); see the anomaly note
about the single resumed game.

```csv
meepledup_k2x172_screen,2026-07-28,base,dcd7c96,200,fair_champion_curve125_k2x172_DEDUP_ON,1.5,8,fair_k2x172_meeple_dedup,344,fair_champion_curve125_k2x172,1.5,8,fair_k2x172,344,110,86,4,+41.9,24.7,+0.500,/mnt/c/carc-shared/meepledup_k2x172_tot344_vs_champ_off_b72000000000,low,"MEEPLE-DEDUP SCREEN cheapest cell. SYMMETRIC head-to-head: candidate = production champion + --meeple-dedup, opponent = SAME agent flag OFF, both curve125 a36d2e15, both k2x172, exact-K2. n=200 deck-paired (100 decks) band 72e9 (FRESH, claimed in BAND_CLAIMS.txt). winrate 0.560 (z +1.70), elo +41.9 +/- 24.7, deck-paired margin +0.500 pts/deck (z +0.48). BOTH STATISTICS REPORTED per house rule -- THEY DISAGREE (wr z1.70 vs margin z0.48) = win-rate noise signature. Cost ratio 0.999x (mask is cost-neutral). Solver 28.6s/game candidate / 22.6s opponent, timeouts 0, latched 200/200 both sides. DOES NOT CLEAR the 2-sigma screen bar. See measurement/classical_search/DEDUP_INTRA_SCREEN_REPORT_20260728.md."
meepledup_k4x172_screen,2026-07-28,base,dcd7c96,200,fair_champion_curve125_k4x172_DEDUP_ON,1.5,8,fair_k4x172_meeple_dedup,688,fair_champion_curve125_k4x172,1.5,8,fair_k4x172,688,98,99,3,-1.7,24.6,-0.200,/mnt/c/carc-shared/meepledup_k4x172_tot688_vs_champ_off_b72000000000,high,"MEEPLE-DEDUP SCREEN deploy-width cell (k4, quarter depth). SYMMETRIC head-to-head, both sides curve125 a36d2e15 k4x172, exact-K2. n=200 deck-paired band 72e9. winrate 0.4975 (z -0.07), elo -1.7 +/- 24.6, deck-paired margin -0.200 pts/deck (z -0.20). BOTH STATISTICS REPORTED. DEAD FLAT on both. Cost ratio 1.010x. Solver 30.3s/game, timeouts 0, latched 200/200 both sides. => with the cheap cell's +41.9 contradicted by its own paired stat, MEEPLE-DEDUP IS DEAD AT SCREEN; deploy-budget confirm NOT funded. See measurement/classical_search/DEDUP_INTRA_SCREEN_REPORT_20260728.md."
intrareuse_k4x344_screen,2026-07-28,base,dcd7c96,200,fair_champion_curve125_k4x344_INTRA_ON,1.5,8,fair_k4x344_intra_reuse,1376,fair_champion_curve125_k4x344,1.5,8,fair_k4x344,1376,96,99,5,-5.2,24.6,+0.800,/mnt/c/carc-shared/intrareuse_k4x344_tot1376_vs_champ_off_b74000000000,high,"C3-INTRA (within-turn tile->meeple tree carry) SCREEN, half-depth at deployed width. SYMMETRIC head-to-head, both sides curve125 a36d2e15 k4x344, exact-K2. n=200 deck-paired (100 decks) band 74e9 (FRESH, claimed in BAND_CLAIMS.txt). winrate 0.4925 (z -0.21), elo -5.2 +/- 24.6, deck-paired margin +0.800 pts/deck (z +0.72). BOTH STATISTICS REPORTED. Flat; statistics disagree in sign. MEASURED COST RATIO candidate/opponent 1.024x (champ_prefix_ms_per_move 1963 vs opp 1916 -- emitter verified: champ_=CANDIDATE, rung_=OPPONENT via opp_prefix_* in the head-to-head branch). Solver 21.8s/game, timeouts 0, latched 200/200 both sides. NOT a strength result on its own -- equal-wall-clock confirm remains formally mandatory. See measurement/classical_search/DEDUP_INTRA_SCREEN_REPORT_20260728.md."
intrareuse_k4x688_screen,2026-07-28,base,dcd7c96,200,fair_champion_curve125_k4x688_INTRA_ON,1.5,8,fair_k4x688_intra_reuse,2752,fair_champion_curve125_DEPLOY,1.5,8,fair_k4x688,2752,109,86,5,+40.1,24.7,+1.650,/mnt/c/carc-shared/intrareuse_k4x688_tot2752_vs_champ_off_b74000000000,low,"C3-INTRA (within-turn tile->meeple tree carry) SCREEN at the EXACT DEPLOYED BUDGET. SYMMETRIC head-to-head, both sides curve125 a36d2e15 k4x688=2752, exact-K2. n=200 deck-paired (100 decks) band 74e9. winrate 0.5575 (z +1.63), elo +40.1 +/- 24.7, deck-paired margin +1.650 pts/deck (z +1.32). BOTH STATISTICS REPORTED -- both positive, both BELOW the 2-sigma screen bar. Effect GROWS with depth (1376 -> -5.2, 2752 -> +40.1), opposite of a sims-washout profile. MEASURED COST RATIO candidate/opponent 0.994x (3795 vs 3819 ms/move) -- candidate marginally CHEAPER, tighter than CL-044's accepted 1.06x, so the header's 'more work per turn' confound is NOT what is driving this. Solver 22.2s/game candidate / 18.1s opponent, timeouts 0, latched 200/200 both sides. CALIBRATION: doubling deploy compute (pareto 5504 cell) buys only +12.2 elo, so a true +40 from a free carry would exceed the value of 2x compute -- suspect winner's curse at z1.62. DOES NOT CLEAR THE SCREEN; NOT DEAD. Proposed follow-up: k4x688 n=600 paired on a FRESH band (1sigma ~14 elo, ~3h on 2 boxes). NOT PROMOTED. See measurement/classical_search/DEDUP_INTRA_SCREEN_REPORT_20260728.md."
```

---

## Anomalies and operational notes

1. **Session restart orphaned the runs mid-flight.** The detached evals kept running correctly
   (this is what the detach rule is for). The intra `k4x688` cell was left stranded at **199/200**
   by an orphan `.claim` for `seed074000000098_a0`; the coordinator cleared the claim and
   relaunched at W4 to play the single missing game, which completed cleanly
   (`elapsed_s=554.6`, no crash) and the cell's `summary.json` was rewritten at full n=200.
   Resume log: `measurement/classical_search/intra_screen_resume.log`.

2. **Mixed code_rev in one cell's manifest — verified cosmetic.** The 199 original games ran at
   `dcd7c9648-dirty`; the resumed game and the rewritten manifest carry `47c2e59-dirty` (the
   checkout advanced while the session was down; HEAD is now `4e67f2b`).
   `git diff --name-only dcd7c96 47c2e59 -- src engine scripts` returns only two **new,
   unrelated** files (`scripts/measurement_infra/oracle_score_pilot.{py,sh}`) plus docs/tests —
   **no change to `src/`, `engine/`, or `scripts/classical_search/`**. The search, leaf, and eval
   code the games ran on are byte-identical across the two revs, so the cell is not
   behaviourally mixed. The draft results.csv row cites `dcd7c96`.

3. **"dirty" in every manifest's code_rev is pre-existing and benign** — the working tree's
   tracked modifications are confined to `measurement/` logs and progress TSVs; no source file is
   modified (`git status --porcelain | grep -v '^??' | grep -v measurement/` is empty).

4. **results.csv has no machine-readable band column.** The header-prescribed
   `grep -o 'seed_start[^,]*' experiments/results.csv` returns nothing — bands live only in prose
   in the `note` column. The share manifests are the real enumeration surface. Worth fixing in the
   header's instructions, or the next reader will believe zero bands are burned.

5. Zero solver timeouts and 200/200 endgame latches on both sides in all four cells — the
   marginalized K=2 endgame behaved identically for candidate and opponent everywhere.

6. No source edits, no commits, no governance or results.csv writes were made by this session.
   PID 1188398 (the local pytest sweep) was left untouched throughout.

---
---

# CONFIRM — C3-INTRA taken to n=1200 on two fresh bands (2026-07-28)

**STATUS: COMPLETE. VERDICT: DOES NOT CLEAR. NOT ADOPTED — no flag flip proposed.**

The screen's k4x688 cell (+40.1 elo, z +1.62, n=200, band 74e9) was funded to a powered
confirm. Two independent tranches of n=600 paired were run on fresh bands. The point estimate
decayed monotonically as power increased — the textbook winner's-curse signature, which the
screen read-out explicitly flagged as the thing to watch for.

## Results

Candidate = `--intra-reuse` side; opponent = same agent, flag OFF. Both statistics reported.

| cell | band | n | W/D/L | winrate | ELO ±1σ | elo z | paired margin | paired z | ms-ratio | status |
|---|---|---|---|---|---|---|---|---|---|---|
| SCREEN k4x688 | 74e9 | 200 | 109/5/86 | 0.5575 | +40.1 ± 24.7 | +1.62 | +1.650 | +1.32 | 0.994x | selection-biased — **excluded from the pooled estimate** |
| CONFIRM tranche 1 | 78e9 | 600 | 316/15/269 | 0.5392 | +27.3 ± 14.2 | +1.92 | +1.200 | +1.76 | 1.011x | unbiased |
| CONFIRM tranche 2 | 80e9 | 600 | 297/15/288 | 0.5075 | **+5.2 ± 14.2** | +0.37 | +0.340 | +0.47 | 1.010x | unbiased |
| **COMBINED (T1+T2)** | 78e9+80e9 | **1200** | 613/30/557 | 0.5233 | **+16.2 ± 10.0** | **+1.62** | **+0.770** | **+1.55** | 1.010x | **the verdict** |

**95% CI on the combined elo: [−3.5, +35.9] — includes zero.** Neither statistic reaches 2σ.

Decay across increasing power: **+40.1 (n=200) → +27.3 (n=600) → +5.2 (n=600)**, combined
+16.2. The screen cell is excluded from the pool because it is the cell that *selected* this
lever for follow-up; including it would re-import the selection bias the confirm exists to remove.

**Tranche heterogeneity (is pooling legitimate?)** T1 − T2 = +22.1 ± 20.1 elo → z = +1.10;
on the paired margin, +0.860 ± 0.992 → z = +0.87. The two tranches are statistically
consistent, so pooling them is sound; the spread is ordinary sampling noise, not a
band-dependent effect.

**Calibration held.** The screen read-out predicted the +40 was inflated on the grounds that
*doubling the entire search budget* buys only +12.2 elo (pareto 5504 cell, n=400), so a free
within-turn carry worth +40 would have to exceed the value of 2× compute. The confirmed +16.2
sits comfortably below that ceiling and is not distinguishable from zero.

## Equal-wall-clock: satisfied, and the lever is still not worth adopting

ms/move ratio candidate/opponent across all three cells: **0.994x / 1.011x / 1.010x**. At
nominal-equal sims the carry is wall-clock-neutral at this budget (tighter than CL-044's
accepted 1.06x), so these cells ARE the equal-wall-clock confirm — the mandatory follow-up
named in `intra_reuse_screen.sh`'s header is discharged, not deferred. The lever is
time-neutral; it simply does not buy resolvable strength.

## Adoption question — NOT live

The coordinator asked for the adoption question to be stated crisply *if* the combined result
cleared 2σ cleanly. **It does not** (z 1.62 / 1.55, CI includes zero), so there is no adoption
proposal to put to Joshua and no governance touch is warranted. For the record, had it cleared:
expected gain +16 elo, cost neutral (ms-ratio 1.01x), and the touches would have been a
`PRODUCTION.yaml` flag flip (`intra_reuse: true`), a CLAIM_REGISTRY row, a CHECKPOINT_LINEAGE
note, and a LEVER_INDEX status change. None of that is being requested.

**What the evidence supports instead:** the lever is time-neutral and non-negative across three
independent bands (all three point estimates positive, none significant). That is a "parked,
not killed" profile. Resolving +16 elo at 2σ would need n ≈ 4800 paired (1σ ≈ ±5 elo) —
roughly 32 box-hours at the observed ~190 games/h on two boxes. **Recommend parking it**: the
cost to confirm a +16 effect exceeds what the effect is worth at this stage, and the same box
time buys more elsewhere. Not recommended without Joshua explicitly wanting that trade.

## Code-rev provenance across tranches (why combining is defensible)

The two tranches ran at **different revisions** — recorded from the cell manifests, not assumed:

- Tranche 1 (78e9): `693ef39-dirty`
- Tranche 2 (80e9): `81f6e5da4-dirty`

⚠️ Note the coordinator's brief named tranche 1's rev as `4e67f2b`; the manifest shows
`693ef39`. The tree advanced between my HEAD check and the launch, and **the manifest is the
authority** — 693ef39 is what tranche 1 actually ran.

Only two source files differ across that range on the code paths these cells touch:

1. **`src/carcassonne_ai/flat_leaf.py`** — commit `8949fd7`, dispatching `flat_base_score` to
   the Cython port under `USE_CY_LEAF`. **Proven bit-exact**, verified by reading the commit's
   own gate output rather than taking the claim on trust
   (`scripts/reconcile_cy_leaf.py`, 300 games, production leaf env):
   690,816 leaf int evals / **0 mismatches**; 86,352 base int evals / **0 mismatches**;
   9,000 of them ENDGAME states (4,500 states, deck ≤ 6) / **0 mismatches**; 1,727 structure
   compares / 0 mismatches; wiring `bound=True routed_value_ok=True
   decomp_arg_stays_python=True`.
   This path IS exercised here — `flat_base_score` is the exact endgame solver's terminal leaf
   and these cells run `--exact-k 2`.
   **Empirical corroboration in our own data:** solver time per game fell 22.6 → 17.8 s
   (candidate, **1.27×**) and 24.2 → 19.2 s (opponent, **1.26×**) between tranches — matching
   the commit's measured 1.28–1.34× and, critically, **applying to both arms equally**, so it
   cannot bias the candidate-vs-opponent comparison. Outcomes bit-exact, timings faster.

2. **`src/carcassonne_ai/champion_factory.py`** — commit `40c79c8`, adding an optional
   `exact_budget` kwarg for the Android app. **Inert here**: it defaults to `None`, in which
   case `budget_kw = {}` and the constructor is called with exactly the pre-kwarg argument
   list. Verified that `eval_fair_puct.py` never passes it (both `exact_budget` occurrences in
   that file are manifest-recording dict literals), and both tranche manifests record an
   identical endgame block: `{'mode': 'marginalized', 'exact_k': 2, 'exact_budget': 2000000,
   'shared_by_both_arms': True, 'tt_cap': '200000'}`.

Conclusion: behaviour is identical across the two tranches; the only measurable difference is
that tranche 2's endgame solver is ~1.27× faster on both sides. Combining them is defensible.

## Configuration (identical to the screen's k4x688 cell)

Both tranches: `--info fair --opponent fair-champion --exact-k 2 --k-dets 4 --sims 688
--intra-reuse --n 600 --paired --shared-claim --claim-stale-secs 300 --no-results-csv`,
W16 per box, both boxes work-stealing on one shared out-root. Manifests confirm for both:
`intra_turn_reuse.enabled = true` (candidate only), `both_sides_curve125 = true`,
`cand_leaf_hash == opp_leaf_hash == a36d2e15a3b3d71d`, candidate and opponent both k4×688.

Run via `/home/doctor/runners/intra_confirm.sh` (a stable-path launcher outside the repo, md5-
verified identical on both boxes). It deliberately does **not** call `intra_reuse_screen.sh`,
which runs two cells and would have burned hours on a k4x344 cell nobody asked for; its env
block and flags are copied verbatim from that script's k4x688 iteration.

Bands claimed in `/mnt/c/carc-shared/BAND_CLAIMS.txt`: `78000000000`, `80000000000`.

## DRAFT results.csv rows — TEXT ONLY, still NOT written to experiments/results.csv

```csv
intrareuse_k4x688_confirm_t1,2026-07-28,base,693ef39,600,fair_champion_curve125_k4x688_INTRA_ON,1.5,8,fair_k4x688_intra_reuse,2752,fair_champion_curve125_DEPLOY,1.5,8,fair_k4x688,2752,316,269,15,+27.3,14.2,+1.200,/mnt/c/carc-shared/intrareuse_k4x688_tot2752_vs_champ_off_b78000000000_n600,high,"C3-INTRA POWERED CONFIRM tranche 1 at the DEPLOYED budget. SYMMETRIC head-to-head, both sides curve125 a36d2e15 k4x688=2752, exact-K2. n=600 deck-paired (300 decks) FRESH band 78e9. winrate 0.5392 (z +1.92), elo +27.3 +/- 14.2, deck-paired margin +1.200 pts/deck (z +1.76). BOTH STATISTICS REPORTED. Below 2 sigma. ms-ratio cand/opp 1.011x (equal wall-clock). Solver 22.6s/game cand / 24.2s opp. Superseded as a standalone read by the COMBINED n=1200 row. See measurement/classical_search/DEDUP_INTRA_SCREEN_REPORT_20260728.md CONFIRM section."
intrareuse_k4x688_confirm_t2,2026-07-28,base,81f6e5d,600,fair_champion_curve125_k4x688_INTRA_ON,1.5,8,fair_k4x688_intra_reuse,2752,fair_champion_curve125_DEPLOY,1.5,8,fair_k4x688,2752,297,288,15,+5.2,14.2,+0.340,/mnt/c/carc-shared/intrareuse_k4x688_tot2752_vs_champ_off_b80000000000_n600,high,"C3-INTRA POWERED CONFIRM tranche 2 at the DEPLOYED budget. Config identical to tranche 1, FRESH band 80e9. n=600 deck-paired. winrate 0.5075 (z +0.37), elo +5.2 +/- 14.2, deck-paired margin +0.340 pts/deck (z +0.47). BOTH STATISTICS REPORTED. ESSENTIALLY NULL. ms-ratio 1.010x. Solver 17.8s/game cand / 19.2s opp (1.27x faster than T1 on BOTH arms — the bit-exact Cython flat_base_score dispatch, commit 8949fd7, reconcile 0/86352 base + 0/9000 endgame mismatches; outcomes unaffected). Heterogeneity vs T1: elo diff z +1.10, margin diff z +0.87 => tranches consistent, pooling legitimate. See DEDUP_INTRA_SCREEN_REPORT_20260728.md CONFIRM section."
intrareuse_k4x688_confirm_COMBINED,2026-07-28,base,693ef39+81f6e5d,1200,fair_champion_curve125_k4x688_INTRA_ON,1.5,8,fair_k4x688_intra_reuse,2752,fair_champion_curve125_DEPLOY,1.5,8,fair_k4x688,2752,613,557,30,+16.2,10.0,+0.770,"/mnt/c/carc-shared/intrareuse_k4x688_tot2752_vs_champ_off_b78000000000_n600 + _b80000000000_n600",high,"C3-INTRA (within-turn tile->meeple tree carry) POWERED CONFIRM, COMBINED over two DISJOINT fresh bands (78e9 + 80e9), n=1200 deck-paired (600 decks). winrate 0.5233 (z +1.62), elo +16.2 +/- 10.0, 95% CI [-3.5,+35.9] INCLUDES ZERO, deck-paired margin +0.770 pts/deck (z +1.55). BOTH STATISTICS REPORTED -- NEITHER CLEARS 2 SIGMA. The n=200 screen cell (band 74e9, +40.1 z1.62) is EXCLUDED from this pool as the selecting observation. DECAY WITH POWER: +40.1 (n200) -> +27.3 (n600) -> +5.2 (n600) => the screen was WINNER'S CURSE, as pre-flagged (doubling total compute buys only +12.2 elo, so a free carry worth +40 was implausible). EQUAL-WALL-CLOCK DISCHARGED: ms-ratio 0.994/1.011/1.010x across cells, tighter than CL-044's accepted 1.06x -- the lever is time-neutral, it just does not buy resolvable strength. NOT ADOPTED, no PRODUCTION.yaml flag flip proposed. PARKED not killed: all three point estimates positive, none significant; resolving +16 at 2 sigma needs n~4800 paired (~32 box-hours), which is not worth it now. Two code revs combined -- delta is the PROVEN bit-exact Cython flat_base_score dispatch (8949fd7) + an inert optional kwarg (40c79c8); see report for the reconcile counts and the both-arms 1.27x solver speedup that corroborates it. See measurement/classical_search/DEDUP_INTRA_SCREEN_REPORT_20260728.md CONFIRM section."
```

## Confirm-phase anomalies

1. **Tranche 1's code_rev is `693ef39`, not the `4e67f2b` named in the brief** — the tree moved
   between my HEAD verification and the launch. Recorded from the manifest, which is the
   authority. Does not affect the result (the intervening commits are the same proven-bit-exact
   set analysed above).
2. **Laptop contention during tranche 1 (my error, corrected).** I censused the laptop idle at
   09:09, G2 launched at 09:12, and I launched at 09:22 — briefly putting 32 workers on 24
   threads. I killed my laptop run by exact pid, cleared 16 orphan claims (0 records lost), left
   G2 untouched, and ran tranche 1 local-only. Lesson: re-census immediately before launch, not
   minutes before. Tranche 2 ran both boxes cleanly from the start.
3. **`run_watchdog.sh` self-match (found and worked around, since fixed upstream).** At the
   tranche-1 rev the watchdog did `pgrep -f "$PAT"` with no self-exclusion, and `PAT` sits in
   the watchdog's own argv — so the suggested pattern `eval_fair_puct` would have matched the
   watchdog itself, reported "healthy, workers alive" forever, and never relaunched. Verified
   empirically with a throwaway script that matched its own pid. Worked around with a bracket
   regex (`'seed-start 7800000000[0]'`) that matches the workers but not the literal argv;
   verified in situ that the pattern matched only `python` processes. Commit `f4ea0b8` has since
   fixed this upstream. The G2 agent independently hit the same trap (`eval_fair[_]puct`).
4. **Cross-run watchdog interference (still latent).** G2's watchdog pattern `eval_fair[_]puct`
   matches *any* eval on that box. While my workers were co-resident, G2's stall detection was
   masked. No harm occurred (G2's driver stayed alive and it completed 400/400), but a
   band-specific pattern is the safer default for any shared box.
5. All four confirm/screen cells: **zero solver timeouts**, endgame latched on both sides in
   every game.
6. Fences held throughout the confirm phase: no source edits, no commits, no governance or
   `experiments/results.csv` writes. The only files written are this report, the stable-path
   launcher/monitor under `/home/doctor/runners/`, and `BAND_CLAIMS.txt` on the share.
