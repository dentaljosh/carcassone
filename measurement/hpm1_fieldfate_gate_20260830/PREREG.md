# PREREG — HP-M1 "bag-conditioned field-fate forecast" KILL GATE

> **⛔ RAN AND CLOSED 2026-08-30 — MECHANISM DEAD.** Bar (a) FAIL (AUC 0.6518 <
> 0.70) · bar (b) PASS-weak · **bar (c) FAIL, sign-REVERSED at p = 1.0e-4**
> (the champion's farm deployments score *higher* under the bag-conditioned
> forecast than the owner's, while dying 8× more often). Verdict + post-hoc
> diagnosis: **[READOUT.md](READOUT.md)**; adjudication of record:
> [RESULTS.json](RESULTS.json). No build, no band, no follow-on cell; 0 games,
> 505/505 replays reconciled, ~3 min laptop wall.

> **Status: FROZEN 2026-08-30, BEFORE any statistic of the hypothesis was computed.**
> This is a **KILL GATE, not a build.** Any bar fails ⇒ the mechanism is DEAD:
> no build, no band claimed, no deploy cell, no follow-on. Passing all three bars
> buys **one thing only** — the right to ask the owner for a *next* prereg. It does
> not authorise a leaf term, a dose ladder, or games.
>
> House rules that bind this document: **CL-079** (a screen is not a verdict; a
> re-run needs a mechanism argument, a new prereg and a fresh band), **CL-084**
> (argmax-over-noisy-arms inflates in-sample gaps — every number here that could be
> selected on must be out-of-fold or out-of-sample), **CL-085** (judged headroom is
> family-relative — this instrument is deliberately **judge-free**: no search, no
> net, no evaluator-of-record scoring positions; the only "judge" is the engine's
> own realized end-of-game award).

---

## 0. The mechanism under test

Stage A's scoring-composition ledger
([COMPOSITION.md](../e4_exploit_grading_20260825/COMPOSITION.md) §3) found the single
sharpest number in the E4 record:

| | owner | champion |
|---|---|---|
| farmer deployments | 205 | 184 |
| **zero-point farmer deployments** | **11 / 205 = 5.4 %** | **85 / 184 = 46.2 %** |
| farm pts / deployment | 6.09 | 4.08 |

and — the load-bearing half — **claim size and claim timing are near-identical
between the seats** (both stake farms at a median of 2 tiles at ply-fraction 0.3).
The deficit is therefore **entirely post-claim**: the champion stakes the same
fields at the same moments and then does not own them at the end.

**HP-M1 (the hypothesis):** a farmer deployment's final fate — scores vs scores
zero — is **predictable at claim time from the REMAINING DECK composition**. The
owner's self-described skill is bag counting; if the fate of a field is legible in
the bag at the moment you commit, then the champion (whose leaf has **no
`k_remaining` dependence anywhere** — LEVER_INDEX row 200, `bag_close` OFF,
`tile_counting` gates OFF, recovery OFF) is structurally blind to exactly the
signal that separates a live farm from dead capital.

**What this gate can and cannot conclude.** It is a **retrodiction on BANKED data
only** — zero games, zero search, zero spend beyond CPU. A PASS says the signal
*exists and is not already priced by the incumbent leaf*; it says nothing about
whether a search at 11008 sims would convert it (CL-080's double-counting
mechanism, and the sims-washout, both bite any later conversion attempt). A FAIL
kills the mechanism: if the fate is not legible in the bag at claim time, the
"champion can't count the bag" story cannot be the explanation for the 46.2 %.

**Prior art this must not re-run** (checked in [LEVER_INDEX](../../docs/LEVER_INDEX.md)
before writing this): `bag_close` / `leaf_variant tile_counting` (row 202) is
**TRIED — ties the champion; C5 cell null**. That variant is a **city/cloister
closure gate** (`flat_leaf._bag_stats` + `_bag_city_ok`) and **touches farms
nowhere**. HP-M1 is a different object (field fate, not city closure) — which is
precisely why bar (b) forces the new forecast to beat it head-to-head on identical
rows rather than being merely "different".

---

## 1. Row universe

**One row = one FARMER deployment** (a meeple of type `FARMER` or `BIG_FARMER`
placed on a field component), taken from the Stage-A commit ledger produced by the
union-find replay of [`stage_a_census.py`](../e4_exploit_grading_20260825/stage_a_census.py)
(re-used verbatim as the structural kernel; see §5).

Two corpora, **both seats**, deduped:

| id | corpus | source | seats |
|---|---|---|---|
| **E4** | human-vs-champion archives | `measurement/e4_games/*.json` (all archives with `ok != false`) | owner + champion |
| **SP449** | champion fair self-play | `measurement/champ_action_logs/champ_games.jsonl` (449 games, band 28000000000–449) | champion + champion |

**Inclusion / exclusion, mechanical:**

1. A game enters only if its replay **RECONCILES**: the attributed award total equals
   the engine's own `state.scores` delta at **every** ply *and* the replayed final
   scores equal the archive's recorded scores. Non-reconciling games are excluded
   and **counted in RESULTS.json**.
2. `E4` archives are replayed under the profile resolved by
   `ev_loss.resolve_profile_name` (R9 is import-latched ⇒ one process per profile
   group). `SP449` carries no `rules_profile` stamp; its profile is fixed by the
   pre-stated mechanical rule below (§1.1).
3. Rows are keyed `(corpus, game_id, meeple_uid)`; the census emits each deployment
   exactly once, so dedup is by construction and is **asserted** in the tests.
4. Cloister, city and road commits are **not** rows. Farmer deployments are the
   whole universe.
5. No outcome label (win/loss, final margin) is read anywhere in row construction
   or feature computation — the fate label is the *feature-level* realized award,
   which is the estimand itself, not the game result.

### 1.1 SP449 profile rule (pre-stated, mechanical, no shopping)

Candidate profiles are tried in the fixed order `["walled", "retail",
"centered18", "app_aug2", "fixed_v1"]`; the **first** one under which **≥ 99 % of
the 449 games reconcile** is adopted and stamped into `RESULTS.json`. If none
reaches 99 %, **SP449 is dropped entirely** and the gate runs on E4 alone, with
the drop logged as a deviation. The E4 corpus alone is sufficient for all three
bars; SP449 is a power/replication corpus, never a substitute.

### 1.2 Primary vs secondary universes

* **PRIMARY universe (all three bars are adjudicated here): the E4 CHAMPION
  farmer deployments.** The champion seat is resolved per-archive from the
  archive's `human_player` field (the owner's seat), never assumed to be seat 0.
  The Stage-A pooled-50 census gives ≈ 85 zero / ≈ 99 scoring; **this run's
  realized counts will differ (56 archives are on disk now, not 50) and the
  realized counts are reported in RESULTS.json and READOUT.md as required.**
* **SECONDARY (powered replication, reported, adjudicates nothing): SP449
  champion rows**, and the E4 owner rows (which bar (c) needs).
* **Rules-epoch discipline** (auto-memory `reference_android_app`): every row
  carries its resolved `rules_profile`; the primary universe is reported both
  pooled and cut by profile, and a profile cut that reverses the pooled reading is
  reported as such rather than smoothed over.

---

## 2. The fate label

```
y = 1  if  realized_pts > 0
y = 0  if  realized_pts == 0
```

`realized_pts` is the Stage-A per-meeple realized award: the field's end-of-game
point value (`3 × #distinct finished adjacent cities`) awarded to the majority
holder(s) per `flat_leaf._winners`, split evenly across that seat's meeples on the
field. Farms score only at game end, so every farmer row has a defined fate.
`y = 0` therefore covers **both** failure modes at once — the field was lost on
majority, **and** the field finished worth zero — which is the correct union: both
are "dead capital", which is the phenomenon.

---

## 3. Features — bag-conditioned, computed at the CLAIM PLY

All features are computed on the state **immediately after** the farmer placement
that the row describes. Nothing downstream of the claim ply is read.

### 3.1 The bag, and why it is knowable

The remaining deck is defined **board-derived, not deck-derived**:

```
R  =  multiset(base_tile_counts)  −  multiset(tile.description for every tile on the board)
```

This is *exactly* the multiset a bag-counting human knows at that moment: it never
touches `state.deck` (whose **order** is shuffled private information) and it never
peeks at `state.next_tile`. `|R|` therefore includes the next turn's tile, which
the actor has not yet seen — the correct knowledge state for a meeple decision.
(Contrast `flat_leaf._bag_stats`, which reads `state.deck` directly; the two agree
on counts at TILES phase and differ by the in-hand tile at MEEPLES phase. The
board-derived form is used here **because** it is provably knowable; the
difference is disclosed, not hidden.)

### 3.2 Tile-class derivation — mechanical, from the engine's own tile set

Classes are derived from `wingedsheep.carcassonne.tile_sets.base_deck.base_tiles`
by three structural attributes read off each `Tile` object, with **no hand
curation**:

* `CE` = number of distinct **cardinal** sides belonging to any city region
  (`tile.city`, flattened, intersected with {TOP,RIGHT,BOTTOM,LEFT})
* `FR` = number of farm regions (`len(tile.farms)`)
* `CH` = `bool(tile.chapel)`

The 32 base tile kinds (72 tiles) fall into exactly **12 occupied classes**:

| CE | FR | CH | tiles | kinds |
|---|---|---|---|---|
| 0 | 1 | 1 | 6 | chapel_with_road, chapel |
| 0 | 2 | 0 | 17 | straight_road(+flowers), bent_road(+flowers) |
| 0 | 3 | 0 | 4 | three_split_road |
| 0 | 4 | 0 | 1 | crossroads |
| 1 | 1 | 0 | 5 | city_top(+flowers) |
| 1 | 2 | 0 | 10 | city_top_straight_road, city_top_road_bend_right/left |
| 1 | 3 | 0 | 3 | city_top_crossroads |
| 2 | 1 | 0 | 10 | city_left_right, city_top_bottom_flowers, city_top_right, city_top_left_flowers, city_diagonal_top_right(×4 variants) |
| 2 | 2 | 0 | 8 | city_narrow(+shield), city_diagonal_top_left_road(+shield) |
| 3 | 1 | 0 | 4 | city_bottom_grass(+shield/+flowers) |
| 3 | 2 | 0 | 3 | city_bottom_road(+shield) |
| 4 | 0 | 0 | 1 | full_city_with_shield |
| | | | **72** | **32 kinds** |

`CE` is the **farm-relevance** axis on the scoring side (a field's points are
`3 × #finished adjacent cities`, so what can close a city is what can pay a
farmer); `FR` is the farm-relevance axis on the **connectivity** side (a
1-farm-region tile merges fields, a 3/4-region tile fragments them, and a
0-region tile is a wall). The derivation is emitted verbatim to
`TILE_CLASSES.json` at run time and the table above is asserted against it by a
test — if the engine's tile set ever changes, the test fails loudly rather than
the table silently rotting.

### 3.3 The feature vector (frozen)

**BAG (28)** — exact counts over `R`:
`bag_n`; `bag_ce0..bag_ce4` (5); `bag_fr0..bag_fr4` (5); `bag_chapel`;
`bag_cls_*` = the 12 exact class counts above minus one redundant (12 emitted, the
model sees all 12 — collinearity with `bag_n` is handled by L2, not by dropping).
Also `bag_ge1..bag_ge4` = #tiles in `R` with ≥ k city edges (the `_bag_stats`
classes, so the incumbent variant's own primitives are inside the new forecast's
reach — a PASS must beat B-BAG *while containing it*).

**FIELD geometry at claim (11)**:
`field_tiles`, `field_adj_cities`, `field_finished_cities`,
`field_unfinished_cities`, `field_unfin_open_edges`, `field_entry_cells`
(# empty board cells orthogonally adjacent to a tile of the field), `own_w`,
`opp_w` (farmer weight on the field post-placement), `own_meeples_left`,
`opp_meeples_left`, `ply_frac` = claim_ply / n_plies.

**BAG × FIELD interaction (6)** — the mechanism proper:
* `bag_closable_unfin` — of the field's adjacent **unfinished** cities, how many
  the bag can **still** close, under Hall's condition via the incumbent's own
  `flat_leaf._city_faces_ge` + `flat_leaf._bag_city_ok` evaluated against `R`.
  *This is the `bag_close` primitive pointed at the farm's cities instead of at
  the player's own city meeples — the single most direct expression of HP-M1.*
* `bag_closable_pts` = `3 × bag_closable_unfin`
* `proj_finished_cities` = `field_finished_cities + bag_closable_unfin`
* `entry_supply` = `field_entry_cells × (#tiles in R with FR ≥ 1) / max(bag_n,1)`
* `invade_risk` = `min(1, field_entry_cells × opp_meeples_left / max(bag_n,1))`
* `invade_pressure` = `field_entry_cells × opp_meeples_left / max(bag_n,1)` (uncapped)

Total: **45 features** (28 bag + 11 field + 6 interaction). The exact emitted
names and order are frozen in `FEATURES.json` at run time and asserted by
`tests/test_hpm1_fieldfate.py`.

---

## 4. The forecasts, and the split discipline

### 4.1 F-PF — parameter-free (preferred form, reported always)

```
s_PF  =  proj_finished_cities  −  invade_risk
```

No fitted constants. `proj_finished_cities` is an integer count; `invade_risk ∈
[0,1]` acts strictly as a tie-break inside a city count. The two-term structure
is the mechanism stated arithmetically: *what the bag can still pay this field,
minus the chance the bag lets the opponent in.*

### 4.2 F-FIT — fitted, and therefore fold-disciplined (PRIMARY)

L2-regularised logistic regression, `C = 1.0` **fixed a priori** (no sweep — a
sweep is an argmax and CL-084 prices argmaxes), features standardised on the
training folds only.

**Solver, pinned because the environment has no sklearn/scipy** (the repo venv
carries numpy only — verified before this freeze): ridge-penalised IRLS
(Newton–Raphson on the penalised log-likelihood), penalty `λ = 1/C = 1.0` applied
to the coefficients and **not** to the intercept, ridge-stabilised solve
(`+1e-8·I`) so a singular Hessian cannot silently produce garbage, at most 100
Newton steps, converged when `max|Δβ| < 1e-8`. Deterministic — no RNG in the fit,
so the fold-CV numbers are reproducible bit-for-bit. Non-convergence in any fold
is a **loud failure**, not a silently-returned partial fit.

**PRIMARY statistic is the OUT-OF-FOLD prediction, never an in-sample one.**

**Fold rule (frozen):** 5 folds, **grouped by game**. For a corpus, sort its
`game_id`s ascending; a game's fold is `index mod 5`; **every deployment of a
game lands in the same fold**. Fitting happens on the other 4 folds of the **same
corpus**; the held-out fold's predictions are the only ones scored. No corpus
mixing inside a fold.

**F-FIT is the primary forecast for all three bars.** Rationale, stated before
seeing anything: this is a kill gate, so the mechanism gets its *best* shot — if a
fitted 39-feature model given the bag cannot separate fates out-of-fold, the
weaker parameter-free form certainly cannot, and the mechanism is dead by the
stronger argument. F-PF is reported alongside as the honest deployable form.

### 4.3 Transfer check (tertiary, adjudicates nothing)

Fit on **all** of SP449, predict **all** of E4 — fully out-of-sample across both
corpus and rules epoch. Reported for generality only. It is **not** pooled with
the fold-CV numbers and is never quoted as the gate's estimate (CL-068: no
cross-epoch pooling).

---

## 5. Baselines — "on identical rows" means literally the same rows

Both baselines score **exactly the same row set** (same games, same deployments,
same claim states), so bar (b) is a within-row contrast with no universe drift.

* **B-LEAF — the current leaf's own farm valuation.** The production leaf's
  marginal valuation of *this* farmer:

  ```
  B_LEAF = leaf(s_claim, player) − leaf(s_claim without this farmer, player)
  ```

  with `leaf = flat_leaf.flat_virtual_score_v2_float` under the champion leaf
  config of record (`governance/PRODUCTION.yaml`; curve125 — the resolved hash is
  stamped into `RESULTS.json`). The counterfactual removes exactly that one meeple
  and returns it to the seat's reserve; everything else is untouched. Higher = the
  leaf thinks the deployment is worth more. This is the incumbent's literal
  answer to "is this farmer any good?".

* **B-BAG — the existing `bag_close` / `tile_counting` variant.** Identical
  construction, with `bag_close=True` on both terms (`flat_leaf._bag_stats`-gated
  closure anticipation). Note for the record: `tile_counting_closure` **raises**
  `NotImplementedError` on the flat path (`flat_closure_bonus`), so `bag_close` is
  the only member of that lever family that is executable on the production leaf;
  B-BAG is therefore the strongest available form of the incumbent bag variant,
  and that is disclosed rather than being quietly the weakest.

---

## 6. The bars — FROZEN, verbatim from the funded menu

All three are adjudicated on the **PRIMARY universe** (E4 champion farmer
deployments), with the primary forecast **F-FIT out-of-fold**.

> **(a)** `AUC ≥ 0.70` separating the champion's zero-scoring farmer deployments
> from its scoring ones. Realized row counts (n_zero / n_scoring) are stated in
> the readout.
>
> **(b)** The forecast must **BEAT, on identical rows, BOTH** the current leaf's
> own farm valuation (B-LEAF) **AND** the existing `bag_close`/`tile_counting`
> variant (B-BAG).
>
> **(c)** The **seat contrast** must run **owner-high / champion-low** — the
> owner's deployments should score better under the same forecast.

**Adjudication rules, fixed now so no reading can be chosen later:**

* **(a) PASS iff** the point-estimate out-of-fold AUC on the primary universe is
  `≥ 0.70`. A 95 % CI is reported (2 000 bootstrap resamples **clustered by
  game**, seed `20260830`) but does **not** move the bar. Literal reading of the
  menu; no extra strictness invented.
* **(b) PASS iff** `AUC(F-FIT) > AUC(B-LEAF)` **and** `AUC(F-FIT) > AUC(B-BAG)`,
  both strictly, both on the identical primary rows. Game-clustered bootstrap CIs
  on each **difference** are reported as evidence quality; a point win whose CI
  includes 0 still PASSES the bar as written, and the readout must label it
  **weak** in that case. (Deliberate: inventing a significance threshold the
  funder did not fund is how a false kill gets minted.)
* **(c) PASS iff** `mean(F-FIT | E4 owner rows) > mean(F-FIT | E4 champion rows)`.
  Direction only, per the menu's wording. A game-clustered seat-label permutation
  p (10 000 perms, seed `20260830`) is reported as evidence quality and does not
  move the bar. **Bar (c) requires the forecast to be applied to owner rows with a
  model that never saw them:** the owner-row scores come from the SP449-trained
  model (champion-only data, so the seat contrast cannot be manufactured by
  fitting on owner rows), and this is stated here rather than chosen later. If
  SP449 is dropped under §1.1, the fallback — stated now — is the E4
  champion-rows-only 5-fold model applied to owner rows, which likewise never saw
  an owner row.

**VERDICT RULE: all three bars PASS ⇒ the mechanism SURVIVES this gate (and buys
only a next prereg). ANY bar FAILS ⇒ MECHANISM DEAD — no build, no band, no
follow-on cell.**

---

## 7. Pre-stated constants

| | |
|---|---|
| RNG seed (all bootstraps, permutations, fold construction) | `20260830` |
| bootstrap resamples (AUC CIs and AUC-difference CIs) | 2 000, **clustered by game** |
| permutations (bar (c)) | 10 000, seat-label flip **within game** |
| logistic `C` | 1.0, fixed a priori, **no sweep** |
| folds | 5, grouped by game, `sorted(game_ids).index(g) mod 5` |
| AUC | Mann–Whitney U form, **ties credited 0.5** |

---

## 8. What is NOT being done (scope fence)

* **Zero games.** No self-play, no eval cell, no band claimed, no `results.csv`
  row minted by this gate, no `PRODUCTION.yaml` touch, no registry write, no
  roadmap write. (Registry/roadmap are the orchestrator's, not this agent's.)
* **No search, no net, no judge.** Judge-free by construction (CL-085).
* **No leaf term is built**, regardless of outcome. A PASS earns a *next prereg*,
  nothing else.
* **No hyperparameter selection of any kind.** One model form, one `C`, one fold
  rule, one feature set — all frozen above.
* **No pooling** across corpora, rules profiles, or bands for any quoted estimate.

## 9. Deviations

Statistics-blind fixes only after this freeze (a crash, a wiring bug, a
reconciliation failure). Every deviation is appended to `DEVIATIONS.md` with its
timestamp and whether any statistic had been read at the time. If a deviation is
made *after* any bar statistic has been read, the affected bar is reported as
**VOID**, not re-read.
