# J-RULES ON SEARCH — CALIBRATION READOUT (dose selection)

> **STATUS: RAN AND READ 2026-08-13. Branch `FUND-SMALLEST` fired.**
> 0 games played, no deck band consumed, no elo statistic computed, no `results.csv`
> row owed, no claim minted. `governance/PRODUCTION.yaml` and
> `governance/BAND_REGISTRY.csv` untouched. The selection rule was committed in
> [CALIB_READ_RULE.md](CALIB_READ_RULE.md) (`bf0f94cf`) **before any arm's
> flip rate was read**, together with the instrument and this rule-applier — the
> numbers below were produced against a fixed rule, not the other way round.
>
> **Named dose: `d0p25` (jrules_dose = 0.25, mask 31)** — DESIGN §11 **G5 is answered**; G1–G4, G6, G7 remain.

## 1. What ran

4 rungs — dose ladder [0.25, 0.5, 1.0, 2.0] with
`jrules_mask` held at **31** (`JR_ALL` = J1|J2|J5|J6|J8) — replayed the
**26 banked E4 human-vs-champion archives**, re-running the production
search at every champion decision ply with the J-rules leaf against the production
leaf under CRN (shared agent seed, shared `_move_idx`), recording whether the **pick
changes**. Every candidate rung and the champion share ONE champion search per ply, so
all rungs are compared against the same pick. Each rung graded
**1,556 champion plies**. Instrument:
[`jrules_e4_replay.py`](../../scripts/classical_search/jrules_e4_replay.py).

**Integrity: 26/26 archives replayed with `replay_scores_match: true`.** Rules epoch resolved per archive from its own stamp,
as required (23 `fixed_v1`, 2 `walled`, 1 `app_aug2`); each archive replays at the budget it was played at. The
champion reproduced the archived move on 72.8% of graded plies.

### 1b. How the dose-0.25 rung came to be measured (§3.1 fired first)

The ladder was run in two passes, and the second was **mandated by the rule, not
chosen after the fact**:

1. The pre-registered ladder `{0.5, 1.0, 2.0}` ran first. Reading it through this
   same rule-applier fired **`FINER-RUNG`**: `f(1.0)` = 38.88% is strictly above §3.1's 20% trigger, so the
   pre-committed dose-0.25 rung had to be measured **before anything could be
   funded**. Nothing was funded on that first reading.
2. The 0.25 rung was then measured on the same corpus, seed and budget and merged (calib + calib_d0p25).

⚠️ **One mechanism deviation, disclosed rather than buried.** §3.1 says to add the
rung as "an added `--arm` over the same output directory". **That mechanism is
unsound**: the instrument's resume is per-PLY, not per-arm, so an already-graded
ply is never re-searched and a late-added arm would carry no pick on any of them —
rolling up as **0.00%**, a perfect silent null wearing the shape of a real
measurement. The instrument now refuses that (`missing_arms_in_resume`). The rung
was therefore measured in a **fresh output directory** with the champion arm
re-run identically, and merged by
[`merge_calib_dirs.py`](merge_calib_dirs.py), which **proves** the two runs
searched the same determinized worlds instead of asserting it: it diffs the
champion's own pick ply-by-ply and requires every one to agree — **1,556 champion picks identical across 26 archives** — plus the graded-ply set, phase,
`k_remaining`, `n_legal`, `action_played`, deck seed, rules profile, budget and
replay checksum. The *substance* of §3.1 (same corpus, same seed, same budget, one
added rung, measured before funding) is preserved exactly; only the plumbing
differs, and **no rule text was edited**.

## 2. The ladder

| rung | `jrules_dose` | flip rate | flips / n | Wilson-95 | clears 10% bar? |
|---|---|---|---|---|---|
| `d0p25` | 0.25 | **23.65%** | 368/1556 | 21.61%–25.83% | **yes** |
| `d0p5` | 0.5 | **30.46%** | 474/1556 | 28.23%–32.80% | **yes** |
| `d1p0` | 1 | **38.88%** | 605/1556 | 36.49%–41.33% | **yes** |
| `d2p0` | 2 | **46.47%** | 723/1556 | 44.00%–48.95% | **yes** |

The bar is read on the **point estimate** (CALIB_READ_RULE §2 — the open-city
convention, under which CL-080's funded `A_d0p5` cleared at 10.09%); the Wilson-95
interval is reported alongside, as the rule requires.

**The CL-080 anchor, for scale:** the open-city term's funded arms flipped **10.09%**
and **18.89%** of champion picks on this same corpus with this same statistic, and
then cost **−53.8 elo** (margin z −5.86) and **−190.3 elo** (z −19.38) at the deploy
budget. Read this ladder against that: a flip rate says the cell will RESOLVE, not
that it will resolve positive.

## 3. Verdict against the committed rule

**§3 branch `FUND-SMALLEST` fires.** §3.2 fires: 4 rung(s) reach f >= 10% on the point estimate. The SMALLEST such dose is 0.25 (f = 23.65%, 368/1556), so that is the named dose and EXACTLY ONE cell is funded. Larger rungs are not funded however much better they express: per CL-080 (open-city flipped 10.09% -> −53.8 elo and 18.89% -> −190.3 elo at the deploy budget) clearing the bar buys RESOLVABILITY, NOT SAFETY, and a bigger flip rate is a bigger risk.

- **Named dose: `d0p25` — `jrules_dose = 0.25`, `jrules_mask = 31`.** Exactly one cell (§3.2 declines DESIGN §8's two-dose
  provision, and this readout may not be quoted to justify a second).
- The funded cell inherits DESIGN §8 in full: k8×1376 both arms, `rust`, `fixed_v1`
  + R9, `--exact-k 2`, n = 800 deck-paired, **margin z primary**, on a **fresh**
  band registered in `governance/BAND_REGISTRY.csv` before game 1, with O0–O12 +
  O4′ read from the manifest before any strength number is opened.
- Still ⛔ before launch: DESIGN §11 **G1, G2, G3, G4, G6, G7**. G5 is now answered.

## 4. Secondary observations (descriptive; NOT inputs to the funding decision)

CALIB_READ_RULE §4 bars "where the flips land" from the funding decision, precisely
because it is the kind of finding that could be used to rescue a rung failing the bar.

- `d0p25`: 368 flips — 253 tile-phase, 115 meeple-phase (69% tiles)
- `d0p5`: 474 flips — 319 tile-phase, 155 meeple-phase (67% tiles)
- `d1p0`: 605 flips — 413 tile-phase, 192 meeple-phase (68% tiles)
- `d2p0`: 723 flips — 515 tile-phase, 208 meeple-phase (71% tiles)

## 5. What this does NOT say

1. **Flip rate is not strength.** A changed pick is not a better pick, and a flip may
   be free in EV. Nothing here predicts the sign of anything — and per CL-080 the one
   time this statistic was followed to a deploy cell, both funded arms went NEGATIVE.
2. **The expressiveness table is not a flip rate.** DESIGN §6's 95%-of-states / mean
   |T| ≈ 3.03 counts leaf VALUES on a random-play corpus at depth 0; this counts
   DECISIONS that change under an 11,008-sim search on real human games.
3. **The depth-1 greedy probe is not this statistic either** (DESIGN §6's
   `jr_dose_probe.py`: 0.25 → 12.5%, 0.5 → 18.8%, 1.0 → 25.0% over 32 positions).
   It was known before the rule was written and the rule forbids funding on it.
4. **A null on the bundle is not a null on any single rule** — J8 fires on 3% of
   states (DESIGN §6) and the mask was held at 31 throughout.
5. **Mixed rules epochs and mixed budgets** across the archives (each replayed at its
   own) make this a pooled *expressiveness* measure, not a per-epoch estimate.
6. **Nothing here licenses a strength claim.** Per **CL-079**, only a deploy-budget
   cell on its own fresh band can produce a kill or an adoption sentence.

## 6. Rung identity (provenance)

| rung | `jrules_dose` | `jrules_mask` | rules | `cand_leaf_hash` |
|---|---|---|---|---|
| `d0p25` | 0.25 | 31 | J1 + J2 + J5 + J6 + J8 | `15948beccf3472d3` |
| `d0p5` | 0.5 | 31 | J1 + J2 + J5 + J6 + J8 | `46a7652670123027` |
| `d1p0` | 1 | 31 | J1 + J2 + J5 + J6 + J8 | `a87fb6801b81d588` |
| `d2p0` | 2 | 31 | J1 + J2 + J5 + J6 + J8 | `56db6c2247dee55f` |

All distinct: True. None equals the champion
`a36d2e15a3b3d71d`: True. Ladder is the
pre-registered one: True.

