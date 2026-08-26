# CLOSE-OUT DRAFT — `track_d2r2_prep`, branch `U-UNREADABLE`

> ⛔ **DRAFT ONLY. NOTHING HERE IS APPLIED.** The adjudicating session was scoped to the
> pair directory on branch `d2r2-freeze` and made **no main-tree edit**. Every touch below
> is for the orchestrator to apply (or decline). Verdict and evidence:
> [`READOUT_D2R2.md`](READOUT_D2R2.md).

## What the branch licenses

`U-UNREADABLE` (READ_RULE §4) licenses **exactly one substantive thing**: naming the failed
gate with its realized value. It licenses **no** spacing claim, **no** strength claim, **no**
`results.csv` verdict, and (READ_RULE §5) no `PRODUCTION.yaml` flip, no leaf/search change,
no re-rating, no CL-023 amendment, no second band, no `n` extension.

The six close-out touches below are therefore **bookkeeping of a void**, not consequences of
a finding. Touch 3 is already applied on this branch (status banners on `DESIGN.md` and
`READ_RULE.md`).

---

## 1. `experiments/results.csv` — a VOID row, on the first attempt's own precedent

The first attempt's row `d2_rung_compression_U_UNREADABLE_instrument_void_n800_b141e9`
(`confidence` = `void`, `new_var` = `NO_STATISTIC_ADJUDICATED_U_UNREADABLE_see_note`) is the
house precedent: the row exists so a later reader's grep cannot miss the band, and it carries
no number. Proposed row, same shape:

```
exp_id     d2r2_rung_compression_U_UNREADABLE_gtiming_void_n800_b144e9
date       2026-08-25
game       base
code_rev   d3c720cf
n          800
new_ckpt   d2r2_rung_compression_probe_k4x1376_vs_HeuristicMCTS_c3_INSTRUMENT_VOID
new_c      1.5
new_cap    8.0
new_var    NO_STATISTIC_ADJUDICATED_U_UNREADABLE_see_note
new_sims   5504
old_ckpt   cell_R800_h800_and_cell_R1600_h1600_INSTRUMENT_VOID
old_c      3.0
old_cap    (blank)
old_var    shared_200_decks_both_seatings_both_cells_band_144000000000
old_sims   cell_R800_sims800_cell_R1600_sims1600
W L D elo sigma avg_diff   (all blank — NO STATISTIC IS ENTERED)
src_dir    measurement/track_d2r2_prep/
confidence void
```

Note text (proposed): D2-R2 RUNG-COMPRESSION CELL, the pre-registered INSTRUMENT-FIX
SUCCESSOR to the band-141e9 first attempt. VERDICT `U-UNREADABLE` on `G-TIMING` — NO STRENGTH
OR SPACING STATISTIC FROM THIS RUN IS ADJUDICATED, QUOTED, OR TREATED AS A VERDICT (this row
exists to make the band greppable, not to carry a number). Both cells COMPLETED clean: 400/400
games each, `n_failed` 0, band 144000000000, 200 shared decks both seatings, one code rev
`d3c720cf-dirty`. **8 of 9 §3 gates PASS, including all four that voided the first attempt**
(`G-RULES` `r9_env_ok=True`; `G-LEAF` `a36d2e15a3b3d71d` distinct from rung
`42af12fce22e1a0f`; `G-TOOL` one rev + `BLIND_COMMIT` `70501f74` at both searched addresses).
`G-TIMING` FAILS: CELL R800 realized equal-time ratio 0.8382 vs the frozen [0.85, 1.20], a
1.38% miss on the floor. The §9 pilot at the same k4×1376 budget read 0.9428 and passed; the
gap is rung-side saturation (python h800 rung 881 → 1103.1 ms/move pilot→cell, +25.2%; rust
probe 831 → 924.7, +11.3%). Disclosed co-tenancy: an Android cross-compile + gradle build ran
on the same box during CELL R800's final ~10 min. Readout
`measurement/track_d2r2_prep/READOUT_D2R2.md`.

## 2. `DECISIONS.md` — index line (proposed)

`2026-08-25 — D2-R2 rung-compression cell adjudicated U-UNREADABLE (G-TIMING 0.8382 vs floor
0.85). The four instrument fixes all verified on the real cells; the void is now a
cost-calibration precondition, not a provenance defect. Band 144e9 spent and retired. A third
attempt needs a fresh statistics-blind session, a fresh band, and a G-TIMING the pilot can
actually predict at production W. See measurement/track_d2r2_prep/READOUT_D2R2.md.`

## 3. Status stamps — ✅ ALREADY APPLIED on `d2r2-freeze`

Banners on [`DESIGN.md`](DESIGN.md) and [`READ_RULE.md`](READ_RULE.md). No bar, gate,
threshold or branch condition was edited.

## 4. `governance/` row flips

- **`BAND_REGISTRY.csv` band `144000000000`:** `status` `claimed` → **`retired`**;
  `decision_influenced` `pending` → **`no`** (a void influences no decision — this is exactly
  how band `141000000000` was closed); `evidence_or_claim` → the `results.csv` void row above.
- ⚠️ **Two defects in that row, worth fixing in the same edit:**
  1. its notes still describe the probe as **`k4x1032`** — the pre-game-1 AMENDMENT #9
     (`d3c720cf`) moved it to **`k4x1376` = 5504 total**, and the registry never caught up;
  2. **the row exists only on branch `d2r2-freeze`**, not in the main tree (main is on
     `tiearb2-stage2`). Until the branch is merged, the main-tree registry does not show
     band 144e9 as claimed at all — a live re-claim race of exactly the kind that forced the
     143e9 → 144e9 substitution in the first place.
- **`CLAIM_REGISTRY.csv`:** **no flip.** Nothing was adjudicated; CL-023 is untouched
  (READ_RULE §5).

## 5. `STATUS.md` top block (proposed content)

D2-R2 ran to completion and adjudicated `U-UNREADABLE` on `G-TIMING` (0.8382 vs floor 0.85).
The instrument-fix mission SUCCEEDED — all four first-attempt voids are closed and verified on
real cells — but the equal-time precondition failed on the real cell after passing on the
pilot. Track D2 remains **unanswered**; band 144e9 is spent. Nothing else changed.

## 6. `docs/PROGRAM_ROADMAP_2026-07-07.md` — D2 line

D2 stays **OPEN**, now at **two voids, from different causes** (attempt 1: provenance/probe
identity; attempt 2: cost calibration). Recommend the roadmap line record that a third attempt
is **not** a re-run of the same launcher and should not be scheduled as one — see below.

Then run `python3 scripts/doc_lint.py`.

---

## The one thing an orchestrator must decide, stated plainly

A third attempt is a **fresh owner/orchestrator decision**, not a licensed consequence, and it
needs a **statistics-blind session** to write any instrument fix (READ_RULE §4 — the
adjudicating session has seen `S` and `z_S` and is therefore disqualified). Four items belong
in that decision, all reported here as findings, **none of them fixed**:

1. **`G-TIMING` as written is not verifiable by the §9 pilot.** A 16-game pilot does not
   saturate W=22; a 400-game cell does, and the python rung and the rust probe do not degrade
   equally under saturation (+25.2% vs +11.3% here). Any successor either verifies the ratio
   on a *saturating* pilot, or gates on a bar the pilot can honestly predict.
2. **The §9 re-pick allowance is exhausted and the budget ladder is now bracketed.** k4×1032
   read 0.659, k4×1376 read 0.9428 on a pilot and 0.8382 on a real cell. A blind session has
   the arithmetic it needs to pick a budget for a saturating cell without seeing any strength
   statistic — that pick is a cost calibration, not a bar.
3. **The latent `G-SINGLEVAR` mirror defect** (emitter copies `--rung-sims` into
   `config.opponent.{sims,label}`; a literal key-set reading fails on every healthy run). This
   run scores it PASS under the frozen §3.1's own committed answer, and the branch does not
   turn on it — but the gate's TEXT should say so rather than leaving it to an adjudicator.
4. **Exclusive tenancy is a precondition, not a courtesy.** An Android build shared the box
   with CELL R800. House rule `feedback_no_agent_compute_beside_eval`: a timing measurement is
   an exclusive tenant. A successor should refuse to start, or record and abort, on a
   non-exclusive box.

**Cost, for the funding decision:** this attempt realized **41.3 core-h / 1.88 h wall at
W=22** (2.57× DESIGN §6's 16.1 core-h, for reasons §0 items 6 and 9 pre-announced). A third
attempt at the same shape prices similarly; the DESIGN §4.4 `n`-extensions remain unfunded.
