# OPEN-CITY CALIBRATION — READOUT (dose/threshold selection)

> **STATUS: RAN AND READ 2026-08-13. Branch `FUND-SMALLEST` fired.**
> 0 games played, no deck band consumed, no elo statistic computed, no `results.csv`
> row owed. `governance/PRODUCTION.yaml` untouched. The selection rule was committed
> in [CALIB_READ_RULE.md](CALIB_READ_RULE.md) (`6148388`) **before any
> arm's flip rate was read** — the numbers below were produced against a fixed rule,
> not the other way round.
>
> **Fundable cells: A_d0p5, A_d2p0.**

## 1. What ran

Six cells — three threshold arms x two doses, `opencity_symmetric` held **True** in
all of them — replayed the **26 banked E4 human-vs-champion archives**,
re-running the production search at every champion decision ply with the open-city
leaf against the production leaf under CRN (shared agent seed, shared `_move_idx`),
recording whether the **pick changes**. All six candidate arms and the champion arm
share ONE champion search per ply, so every arm is compared against the same pick.
Each cell graded **1,556 champion plies**. Instrument:
[`opencity_e4_replay.py`](../../scripts/classical_search/opencity_e4_replay.py).

**Integrity: 26/26 archives replayed with `replay_scores_match: true`.** Rules epoch resolved per archive from its own stamp,
as required (23 `fixed_v1`, 2 `walled`, 1 `app_aug2`); each archive replays at the budget it was played at. The
champion reproduced the archived move on 72.8% of graded plies.

## 2. The ladder

| arm | `opencity_size_min` (TILES) | `opencity_edge_min` | flip rate @ dose 0.5 | @ dose 2.0 |
|---|---|---|---|---|
| A (production spec) | 4 | 2 | **10.09%** (157/1556) <br><sub>95% CI 8.69%–11.69%</sub> | **18.89%** (294/1556) <br><sub>95% CI 17.03%–20.92%</sub> |
| B (loose) | 3 | 2 | **13.56%** (211/1556) <br><sub>95% CI 11.95%–15.35%</sub> | **23.65%** (368/1556) <br><sub>95% CI 21.61%–25.83%</sub> |
| C (tight) | 6 | 3 | **3.60%** (56/1556) <br><sub>95% CI 2.78%–4.64%</sub> | **5.85%** (91/1556) <br><sub>95% CI 4.79%–7.13%</sub> |

Wilson-95 CIs are reported per CALIB_READ_RULE §1. **The rule anticipated that the
bars would not be knife-edge; for one cell that expectation did not hold, and it is
the cell the rule selects — see §3.**

## 3. Verdict against the committed rule

**§3 branch `FUND-SMALLEST` fires.** §3.1 fires: 4 cell(s) reach f >= 0.10. Among them the smallest dose is 0.5; among cells at that dose the tightest predicate that still clears the bar is (size_min=4 TILES, edge_min=2). Dose is minimised first because T is a PRODUCT of two excesses (TERM_SPEC §5: bracket downward), so an equal dose perturbs the leaf's global scale more than for denial.

⚠️ **THE SELECTED CELL SITS ON THE BAR.** `A_d0p5` reads
**10.09%** against a bar of 10% — it clears by
0.09 pp, and its own Wilson-95 interval
(8.69%–11.69%) **straddles the bar**. The rule is written on `f`, the
point estimate, and it has been applied exactly as written — rewriting it now
to read the interval instead would be precisely the after-the-numbers rule
change §5 forbids. But the consequence should be stated plainly rather than
discovered later:

- Read on the **CI lower bound** instead, the selection would move to
  `B_d0p5` (lower bound 11.95% ≥ 10%) — a **looser**
  predicate at the same dose, which is the direction §3.1's own rationale
  ('prefer widening the predicate over raising the dose') points anyway.
- The funded pair therefore rests on a cell whose expressiveness is
  ~10% ± 1.5 pp. If the screen it
  buys reads null, 'the term does not express' is **not** an available
  reading — the honest one is that it was funded at the edge of the floor.
- This is a decision for Joshua, not for this readout: the rule's answer is
  `A_d0p5`, and the alternative is recorded, not taken.

- **Funded: A_d0p5, A_d2p0.**

## 4. Secondary observations (descriptive; NOT inputs to the funding decision)

CALIB_READ_RULE §4 bars "where the flips land" from the funding decision, precisely
because it is the kind of finding that could be used to rescue a cell failing the bar.

- `A_d0p5`: 157 flips — 114 tile-phase, 43 meeple-phase (73% tiles)
- `A_d2p0`: 294 flips — 222 tile-phase, 72 meeple-phase (76% tiles)
- `B_d0p5`: 211 flips — 150 tile-phase, 61 meeple-phase (71% tiles)
- `B_d2p0`: 368 flips — 260 tile-phase, 108 meeple-phase (71% tiles)
- `C_d0p5`: 56 flips — 46 tile-phase, 10 meeple-phase (82% tiles)
- `C_d2p0`: 91 flips — 73 tile-phase, 18 meeple-phase (80% tiles)

### 4b. Arm C is NOT zero — the one place the term surprised its own spec

TERM_SPEC §6 measured the `(6 tiles, 3 edges)` predicate firing on **0.0%** of
golden-corpus leaf values, CALIB_READ_RULE §3 recorded the expectation that
"arm C is expected to read ≈ 0", and the capability probe reproduces that on
scripted playouts (0 of 288 sampled leaf values move, on BOTH the rust and the
python leaf). **On the real E4 boards it fires anyway:**
`C_d0p5` 3.60% and `C_d2p0` 5.85% of champion plies flip.

The read-rule asked for this explicitly — "a nonzero arm C would itself be
information" — so it is recorded as such. The reconciliation is that the golden
corpus and the probe's scripted playouts simply do not contain 6-tile cities with
3 open edges, while real games against a human do. **The operational lesson is
about the instruments, not the term: a predicate that reads 0.0% on the golden
corpus is not thereby inert in play, and the capability probe cannot gate an arm
whose bite it cannot reproduce** (which is why `run_calib_laptop.sh` gates on arms
A and B and merely reports C).

## 5. What this does NOT say

1. **Flip rate is not strength.** A changed pick is not a better pick, and a flip may
   be free in EV. Nothing here predicts the sign of anything.
2. **The wiring bite is not a flip rate.** TERM_SPEC §6's 21.9% counts leaf VALUES
   that differ on the golden corpus; this counts DECISIONS that change on the E4
   corpus. The denial precedent shows the gap is large.
3. **Mixed rules epochs and mixed budgets** across the archives (each replayed at its
   own) make this a pooled *expressiveness* measure, not a per-epoch estimate.
4. **Nothing here licenses a strength claim** and `governance/PRODUCTION.yaml` is
   untouched on every branch. Per **CL-079**, even a funded screen at the 2750
   ablation instrument is a screen — never a kill and never an adoption.

## 6. Cell identity (provenance)

| cell | dose | size_min | edge_min | symmetric | `cand_leaf_hash` |
|---|---|---|---|---|---|
| `A_d0p5` | 0.5 | 4 | 2 | True | `c128083fb485d20d` |
| `A_d2p0` | 2 | 4 | 2 | True | `2cf0b7507e6a0921` |
| `B_d0p5` | 0.5 | 3 | 2 | True | `520c3f4cfe6a7792` |
| `B_d2p0` | 2 | 3 | 2 | True | `b9d3fcb9ad14a527` |
| `C_d0p5` | 0.5 | 6 | 3 | True | `3adfbf1bd306b4a6` |
| `C_d2p0` | 2 | 6 | 3 | True | `bb34bcc045a6368e` |

All six distinct: True. None equals the champion
`a36d2e15a3b3d71d`: True. Ladder is the
pre-registered one: True.

