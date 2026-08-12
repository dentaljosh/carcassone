# SIMS-SPLIT **ALLOCATION** A/B at 1.5× BUDGET — PRE-REGISTRATION

> **STATUS: PRE-REGISTERED 2026-08-12, BEFORE GAME 1.** Written and committed before the
> band was claimed and before any game was played. `governance/PRODUCTION.yaml` is untouched
> on every branch of this document. **No promotion, no `results.csv` row, no claim-registry
> row, no adjudication** is performed by the run or by this file — the orchestrating session
> reads the extracts and closes out.

Funded by Joshua 2026-08-12. Two cells, one shared fresh band, CRN.

---

## 1. Why this cell exists (and why it is NOT last night's S1)

The 2026-08-11 sims-split census
([`measurement/simsplit_census_20260811/READOUT.md`](../simsplit_census_20260811/READOUT.md))
found the **TILE** search unconverged at production budget — **18.5%** of tile picks change
when the per-world budget is halved (27.7% at a quarter) — while the **MEEPLE** search is
near-flat in budget (11.6% / 13.1%) and ~71% of its flips sit at near-tie top-2 gaps.

Last night's **S1 screen** tested a *re-allocation at FIXED per-turn total*
(tile 2408 / meeple 344, band 1.22e11, n=200) and read a null: elo −26.1 ± 24.6,
paired margin −1.435 pts/deck, **margin z −1.037**. That cell answered "can I move budget
off the meeple search for free?" — and at screen resolution, no.

**Joshua has since removed the fixed-budget constraint** (wall clock is not binding —
verbatim: "don't worry about even 10x"). The question therefore changes shape:

> **Does the TILE phase simply want more search than the champion gives it?**

That is a *budget-increase* question, not a *reallocation-at-fixed-cost* question, and it
needs a different pair of cells.

## 2. The two cells — the control IS the design

Production champion of record (`governance/PRODUCTION.yaml`): `k_dets 8 × sims_per_det 1376`
= **11008 per decision**, uniform across phases; a turn runs two searches, so the per-turn
per-`k_dets` total is 2×1376 = 2752 and the per-turn total is **22016**.

| cell | candidate | per-turn total | vs production |
|---|---|---|---|
| **A — allocation** | `--k-dets 8 --sims 2064 --sims-tile 2752 --sims-meeple 1376` | 8×(2752+1376) = **33024** | **1.5×** |
| **B — matched-budget control** | `--k-dets 8 --sims 2064` (uniform, NO split) | 8×(2064+2064) = **33024** | **1.5×** |

**Opponent in BOTH cells = the unmodified production champion**, `--opp-k-dets 8 --opp-sims 1376`
(11008 per decision).

The two candidate command lines are **byte-identical except for the two split flags**. Cell A
is exactly Cell B's budget, re-allocated 2752/1376 instead of 2064/2064. That is why
`--sims 2064` is the base for *both* cells: it makes A's manifest field
`symmetric_per_turn_total_sims` equal 33024 — literally Cell B — and it makes the capability
probe's fixed-per-turn-total arithmetic (`sims_tile + sims_meeple == 2 × sims`) pass
**truthfully** rather than by override. For Cell A the base `--sims` is inert on the
candidate: both phases are named, and `FairHeuristicPriorAgent._sims_for` /
`RustFairAgent.choose_action` resolve **every** decision to a named phase budget
(`src/carcassonne_ai/fair_agent.py:930`, `src/carcassonne_ai/rust_agent.py:635`).

### Cell B is not optional and not padding

Cell A alone **cannot** distinguish an allocation win from simply buying compute. CL-068
calibrates ≈ **+12 elo per doubling** of total compute, so 1.5× hands *both* cells about
**+7 elo for free** (log₂1.5 × 12 ≈ 7.0). Therefore:

> **The claim "tiles specifically want more search" requires A > B. It does NOT follow from
> A > 0.** A > 0 with A ≈ B is the *compute* result, and it is the boring result.

The **primary statistic of this measurement is the A−B deck-paired contrast**, not either
cell's own margin. Both cells share the band and the decks (CRN), which is what makes that
contrast the sensitive quantity — the project's robust class is the within-band deck-matched
contrast (CLAUDE.md, "CROSS-BAND z's GET ~2× HUMILITY"; within-band deck-paired is
unaffected).

## 3. Wiring — fixed, and verified from the manifest BEFORE any number is read

Shared by both cells: FAIR PIMC (`eval_fair_puct.py --info fair --opponent fair-champion`),
`--backend rust`, `--rules-profile fixed_v1` + `CARCASSONNE_FIX_R9=1`, `--exact-k 2` both
arms, `--c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits`, `--paired`,
`--shared-claim`, `--no-results-csv`, `nice -n 19`, detached, two-box work-stealing
(**W=30 local, W=22 laptop**). Launcher: `scripts/classical_search/menu_fair_cell.sh`.

**Leaf: `a36d2e15a3b3d71d` on BOTH sides of BOTH cells.** This is a BUDGET/ALLOCATION
contrast, not a leaf contrast — no `--cand-leaf-json`, no `--allow-cand-curve-drift`, and the
candidate leaf hash must **EQUAL** the champion's. (The usual denial/ablation gate is
inverted here: "cand_leaf_hash == champion" is the PASS condition, not the failure signature.)

### 3.1 The asymmetry-flag trap (Block D's prereg, verbatim)

`--opp-sims` **alone silently gives the opponent the CANDIDATE's `k_dets`**. Both flag pairs
are set explicitly in both cells: candidate `--k-dets 8` / `--sims 2064`, opponent
`--opp-k-dets 8` / `--opp-sims 1376`.

### 3.2 Pre-registered wiring gates (ALL must pass, per cell, before any result is read)

| # | gate | Cell A | Cell B |
|---|---|---|---|
| W1 | `rules_profile.name` | `fixed_v1` | `fixed_v1` |
| W2 | `rules_profile.r9_env_ok` | `true` | `true` |
| W3 | `config.cand_leaf_hash` | `a36d2e15a3b3d71d` | `a36d2e15a3b3d71d` |
| W4 | `config.opp_leaf_hash` | `a36d2e15a3b3d71d` | `a36d2e15a3b3d71d` |
| W5 | `config.champion.k_dets` (candidate) | `8` | `8` |
| W6 | `config.opponent.k_dets` | `8` | `8` |
| W7 | `config.opponent.sims_per_det` / `total_sims` | `1376` / `11008` | `1376` / `11008` |
| W8 | `config.champion.sims_per_det` (the BASE) | `2064` | `2064` |
| **W9** | **`config.sims_split`** | **PRESENT**: `sims_tile 2752`, `sims_meeple 1376`, `effective_sims_tile 2752`, `effective_sims_meeple 1376`, `per_turn_total_sims 33024`, `symmetric_per_turn_total_sims 33024` | **ABSENT** (key must not exist) |
| W10 | `config.band_seed_start` | same band, both cells | same band, both cells |
| W11 | completion | ≥ 90% of n=800 | ≥ 90% of n=800 |

**W9 is the gate that matters most.** Last night's S1 verdict extract surfaced only
`cand_sims_per_det: 1376` and did **not** show the split; only the run `manifest.json`'s
`config.sims_split` block proved the knob was applied. A silently-default-off Cell A **would
be Cell B**, and A−B would be a guaranteed, meaningless, perfectly-clean null. `W9-absent on
A` or `W9-present on B` ⇒ **the pair is UNREADABLE, not merely suspicious.**

Note the field-name traps carried into the readout: in this harness `champ_prefix_ms_per_move`
is the **CANDIDATE's** cost, and `config.champion.*` is the **candidate** block. Cell A's
`cand_total_sims` will read `8 × 2064 = 16512`, which is **not** its real per-turn spend —
the truth for Cell A is the `sims_split` block (`per_turn_total_sims 33024`).

### 3.3 Pre-flight gates, on BOTH boxes, before game 1

1. `git rev-parse HEAD` identical on both boxes (stale remote code is a contamination class).
2. `chain_capability_probe.py --require simsplit --harness .../eval_fair_puct.py
   --sims-tile 2752 --sims-meeple 1376 --sims 2064` exits 0 (flags advertised by argparse;
   fixed-total arithmetic 2752+1376 == 2×2064 == 4128).
3. **Functional gate (added here, beyond the chain's requirement):**
   `pytest tests/test_simsplit_knob.py` passes on both boxes. The capability probe can only
   attest that the flags *exist*; this suite asserts the per-move `sims_used` actually takes
   the per-phase value on the rust path and that the OFF path stays byte-identical. It is the
   closest available substitute for the "the knob CHANGES the number" check the probe
   explicitly cannot do for simsplit, and it is why this cell does not need a hand-written
   go-file the way block S1 did.

## 4. Band, decks, n, and the honest power statement

**One shared fresh band** claimed from `governance/BAND_REGISTRY.csv` at launch time
(next free above the 1.22e11 high-water mark), registry row written **at claim time** in the
existing 8-field format with `decision_influenced=pending`.

- **n = 800 deck-paired per cell** = **400 decks × 2 seats**, the SAME 400 decks in both
  cells (CRN). Seeds `<band>+0 .. <band>+399`.
- Seeds `<band>+400 .. <band>+799` are **RESERVED** for the single pre-registered top-up
  (branch R5) and must not be drawn for anything else.

**Power, derived from realized σ — not chosen.** Last night's S1 at n=200 realized
`elo_sig_1sigma = 24.64` and `paired_mean_margin −1.435 / z −1.037` ⇒ per-deck margin
se ≈ 1.38 pts at 100 decks. Scaling to 400 decks / n=800:

| quantity | n=800, 400 decks |
|---|---|
| elo, 1σ | **≈ ±12.3** |
| elo, 2σ | **≈ ±24.6** |
| deck-paired margin, se | ≈ **0.5–0.7 pts/deck** (band-1.20e11 cells at 400 decks realized 0.45–0.55; S1's variance extrapolates to 0.69 — the readout reports the REALIZED value, not this range) |
| deck-paired margin, 2σ | ≈ **±1.0 to ±1.4 pts/deck ≈ ±17 to ±24 elo** |

**Stated plainly, before game 1: the expected allocation effect may sit at or below this
resolution.** The free-compute term alone (≈ +7 elo for 1.5×) is *less than a third* of the
2σ bar, so **neither cell is expected to clear 2σ on its own**, and an allocation effect
smaller than the compute effect would be invisible. Consequently:

> **A null in this measurement is a BOUNDED null and must be written as one.** The sentence
> "tiles don't want more search" is **forbidden** as a reading of any branch below. The only
> licensed null statement is of the form *"no tile-allocation effect larger than ±X elo /
> ±Y pts/deck at 2σ, at 1.5× budget, on this band"*, with X and Y the REALIZED numbers.

The **A−B contrast's** standard error is **computed empirically from the per-deck deltas**
(`crn_delta_fairnet.py`, which pairs on `(seed, a_seat)` and differences the per-deck
seat-balanced margins) — it is **not assumed**. CRN should shrink it relative to
√2 × se(cell), but that is a hope, not a pre-registered claim: if the realized
se(A−B) ≈ √2 × se(cell), the contrast resolves only ~±35 elo at 2σ and R4 fires almost by
construction. **The realized se(A−B) is reported first, before its z is interpreted.**

## 5. Pre-registered branch map — WRITE IT, THEN HONOUR IT

**Primary statistic:** `z(A−B)` = paired z on the per-deck seat-balanced margin difference
(Cell A margin − Cell B margin), over decks present in BOTH cells.
**Secondary:** each cell's own deck-paired margin z vs the champion, `z(A)` and `z(B)`.

House map applied to the primary: **|z| ≥ 2.0** resolve with sign · **1.5 ≤ |z| < 2.0** top-up
once on fresh decks of the same band · **|z| < 1.5** bounded null.

Branches are evaluated **in order; the first to fire wins.**

| # | condition | reading | action |
|---|---|---|---|
| **R0 VOID** | any wiring gate W1–W11 fails | the pair is UNREADABLE | Report the gate failure. **No number is quoted.** Fix and re-run on a FRESH band. |
| **R1 ALLOCATION WINS** | `z(A−B) ≥ +2.0` | at matched total budget, moving sims toward the tile phase beats spending them uniformly — **the tile phase specifically wants more search** | Report with sign and size. **Still not a promotion**: a 1.5×-budget candidate is not a deploy config, and CL-070-class budget-anchoring caveats apply. Next step (Joshua's call) = a deploy-budget-neutral formulation, pre-registered separately on a fresh band. |
| **R2 ALLOCATION IS ACTIVELY WRONG** | `z(A−B) ≤ −2.0` | uniform beats tile-skewed at matched total — reallocation *toward tiles* is the wrong direction; combined with last night's S1 (tile-skew at fixed total also negative) the tile-hunger reading of the census does **not** survive contact with play | `docs/LEVER_INDEX.md` §5 row rewritten direction-corrected; the census's comparative half is flagged as not transferring to elo. |
| **R3 TOP-UP** | `1.5 ≤ \|z(A−B)\| < 2.0` | suggestive, unresolved | **ONE** top-up, n→1600/cell, on the RESERVED fresh decks of THIS band (`<band>+400..+799`), both cells, then re-verdict on the pooled within-band result. The chain does **not** auto-run it — the spend is Joshua's call. No second top-up, ever (the forking-path pattern behind four winner's-curse instances this campaign). |
| **R4a BOUGHT COMPUTE, NOT ALLOCATION** | `\|z(A−B)\| < 1.5` **AND** `z(A) ≥ +2.0` | the 1.5× budget shows up in play, but the *split* contributes nothing distinguishable | Report as a **compute** result, explicitly NOT an allocation result. Feeds the budget axis (CL-060 territory), not the split lever. |
| **R4b BOUNDED NULL** | `\|z(A−B)\| < 1.5` **AND** `\|z(A)\| < 2.0` | nothing resolves at this n | **Bounded null.** Report the realized 2σ bounds on both `A−B` and `A`. The forbidden sentence in §4 stays forbidden. `LEVER_INDEX` §5 row updated with the measured floor, lever parked-not-killed. |

**Cross-checks reported on every branch (not verdicts):**

- `z(B)` on its own. Under CL-068 the *expected* value of B is ≈ +7 elo, well inside noise; a
  B that lands far outside `0 ± 2σ` in either direction is a flag on the compute calibration
  itself and is reported as such.
- Sign agreement between elo and paired margin per cell. Disagreement is the house win-rate
  noise signature (seen on band 1.20e11's curve175) and downgrades confidence in the elo.
- `ms_ratio_cand_over_opp` for both cells (§6).
- `n_paired_decks` for the contrast. If fewer than 380 of 400 decks are common to both cells,
  the contrast is reported with that caveat prominent.

## 6. Cost is RECORDED, not owed

Equal-wall-clock is **not** owed here — Joshua removed the clock constraint explicitly. But
the cost is part of the result and is reported: `ms_ratio_cand_over_opp` for both cells, from
the summary's `cand_prefix_ms_per_move` / `champ_prefix_ms_per_move` pair (**and yes, in this
harness `champ_prefix_*` is the CANDIDATE's cost — read the emitter, not the field name**).

Prior: last night's S1 split ran **1.0888×** the opponent at *fixed* sims. These cells are
1.5× total budget, so **expect ~1.5×** in both cells; Cell A and Cell B should be close to
each other (same total). A materially *lower* ratio than ~1.4 in Cell A is itself evidence the
split did not apply and is escalated to the W9 gate rather than explained away.

Ratios only — never an absolute ms/move from a shared-tenancy run.

## 7. ETA and throughput

Realized last night on the same two boxes at W30/W22: ~238 s/game at k8×1376 both arms ⇒
≈ 790 games/h steady state. These cells run the candidate at 1.5×, so ≈ (1.5+1.0)/2.0 ×
per-game cost ⇒ ≈ **630 games/h**. 1600 games total (two sequential cells, each with a
start/tail wave) ⇒ **≈ 2.5–3 h wall**. Reported against realized throughput at close.

## 8. What this measurement CANNOT say

1. **It cannot price a deploy config.** Both cells run at 1.5× the champion's budget. Nothing
   here is deployable and nothing is proposed for `governance/PRODUCTION.yaml`.
2. **It cannot separate "tiles want more" from "meeples want less".** A−B contrasts one
   specific 2752/1376 skew against uniform 2064/2064 at the same total; it is one point on a
   skew axis, not a dose ladder.
3. **It cannot resolve small effects.** See §4 — the 2σ floor is ~±17–25 elo per cell and is
   computed empirically for the contrast.
4. **Band epoch.** Fresh band, `fixed_v1` + R9 both sides; not comparable to walled-era elo,
   and the band retires from confirmatory use if it influences a decision.
5. **The census that motivated this is a pick-flip statistic, not elo.** Flip rate ≠ regret
   (`simsplit_census_20260811/PREREG.md` §4.2). A null here does not falsify the census.

## 9. Standing constraints on this run

`governance/PRODUCTION.yaml` untouched · no promotion · no `results.csv` row · no
claim-registry row · no adjudication by the launcher · band registry row written at claim
time with `decision_influenced=pending` and flipped only at close-out by the orchestrating
session.
