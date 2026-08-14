# J-RULES SURFACE B — CALIBRATION READ-RULE (how `jrules_prior_dose` gets chosen, written BEFORE any flip rate exists)

> **STATUS: WRITTEN AND COMMITTED 2026-08-14, BEFORE THE CALIBRATION RAN AND BEFORE ANY ARM'S
> SEARCH FLIP RATE WAS READ.** At the time of writing, the replay instrument
> ([`scripts/classical_search/jrules_priors_e4_replay.py`](../../scripts/classical_search/jrules_priors_e4_replay.py))
> had been built, unit-tested (15 pure tests) and **wiring-smoked once** on one archive at
> `--limit-games 1 --limit-plies 12` — a run whose summary is stamped `partial` and which §3.0
> below therefore VOIDS as a calibration by construction (observed: 6 graded plies, 0 flips at
> dose 0.25 — n=6 of an expected ~1,500+, quoted here ONLY as provenance of what was and was
> not known, never as a rate). **No full-corpus arm has ever been graded.** That ordering is
> the point: it stops the dose from being chosen after seeing which rung looks best — the
> forking-path pattern behind the campaign's four winner's-curse instances.
>
> **0 games. No deck band. No elo statistic anywhere in this document.** Nothing here licenses
> a strength claim; `governance/PRODUCTION.yaml` / `governance/BAND_REGISTRY.csv` untouched on
> every branch.
>
> Direct parent, cloned deliberately rather than re-derived:
> [surface A's CALIB_READ_RULE](../jrules_on_search_20260813/CALIB_READ_RULE.md) (which itself
> cloned open-city's), its [READOUT](../jrules_on_search_20260813/CALIB_READOUT.md), and the
> deploy outcomes those produced (surface A's confounded loss; **CL-080**). Term build and
> gates: [DESIGN.md](DESIGN.md) §3–§6, §11.

---

## 1. What the calibration measures, and what it explicitly does not

Arms replay the banked E4 human-vs-champion archives and, at each **champion decision ply**,
re-run the production search with the J-rules PRIOR boost against the unmodified production
search under CRN (shared agent seed, shared `_move_idx` — identical determinized worlds),
recording whether the **pick changes**. Arms share corpus, seeds and budget; only the dose
differs. **This is the same statistic as surface A's and CL-080's calibrations** (same corpus,
same arithmetic, same budget), so the three ladders are directly comparable.

| arm | `jrules_prior_dose` | `jrules_prior_mask` | `jrules_prior_scope` |
|---|---|---|---|
| **d0p5** | 0.5 | 31 (`JR_ALL`) | all |
| **d1p0** | 1.0 | 31 | all |
| **d2p0** | 2.0 | 31 | all |

The mask is held at **31** and the scope at **`all`** in every rung. A mask ablation is a
different question (which rule bites); a `scope=own` arm is a **different hypothesis** (the
internal opponent model stays the champion — DESIGN §4) — each is a NEW calibration, run and
named as such, never a rung of this ladder. The instrument stamps every mask and scope
actually used, so neither can be mistaken for the pre-registered ladder.

**Measured: the champion-ply pick-flip rate. Not measured: strength, EV, or regret.** A flip
is not an improvement, and per §2 a large flip rate is a RISK, not a prize.

**Report with the rate, always:** realized corpus size (expect the full archive bank —
surface A realized 1,556 champion plies over 26 archives; the bank grows, so re-count),
per-arm **Wilson-95 CIs**, the per-archive rules epoch resolved from each archive's own
stamp, and `replay_scores_match` for every archive. **Any archive that fails its replay
checksum voids the whole calibration** — fix and re-run (free: no band, no games,
deterministic searches).

---

## 2. The bar, and which statistic it is read on

**The funding bar is `f ≥ 0.10` (10%) on the POINT ESTIMATE of the search pick-flip rate** —
the same convention as the open-city and surface-A rules (the only outcome anchors we have
were selected under it; re-deriving the convention per term is itself a forking path).

- **decision statistic:** the point estimate `f = flips / n_graded`, corpus-wide;
- **reported alongside, always:** the Wilson-95 interval and its lower bound;
- **mechanical annotation, no branch effect:** if the named rung's Wilson-95 lower bound is
  below 0.10, the readout labels it **`marginal`** and the word rides into the deploy prereg.

Where the bar comes from (inherited arithmetic, unchanged): ~70 champion decisions/game ⇒ a
term changing fraction `p` of them needs `1.32/(70·p)` points per changed decision to move an
n=800 deck-paired cell by 2σ; below ~10% the cell buys a guaranteed unreadable null and a
consumed band.

⚠️ **Clearing the bar buys RESOLVABILITY, NOT SAFETY.** The anchors: open-city flipped 10.09%
/ 18.89% and cost −53.8 / −190.3 elo; surface A's floor rung flipped 23.65% and its cell lost
(confounded). A bigger flip rate is a bigger perturbation of the strongest evaluator we have.
"Expresses more" is never a reason to prefer a rung.

**No marginal tier** (`0.05 ≤ f < 0.10` is `NO-EXPRESSION`), as in surface A's rule.

---

## 3. The decision rule (evaluated in order, first to fire wins)

Let `f(d)` = the corpus-wide champion-ply pick-flip point estimate for the rung at dose `d`,
from the instrument's `SUMMARY.json`, over **all** archives with no `--limit-*`.

### 3.0 `VOID` — the validity gate (checked before any rate is quoted)

If `all_replay_scores_match` is not `true`, or any summary is `partial`, or the corpus is not
the full archive bank, or the production leaf hash is not `a36d2e15a3b3d71d`, **or any arm's
leaf hash DIFFERS from the champion's** (⚠️ INVERTED vs every leaf-term calibration — surface
B must not move the leaf; a moved hash means a leaf change was smuggled into a prior cell),
or the instrument's positive control (`_assert_surface_b_live`) did not pass on the grading
box: **the calibration is VOID.** Fix and re-run. No number from a void run is quoted
anywhere.

### 3.1 `FINER-RUNG` — the pre-committed extension (fires before any funding)

**If `f(1.0) > 0.20`** (strictly; at exactly 0.20 it does not fire): add the rung
**`d0p25` = dose 0.25, mask 31, scope all** — measured in a **FRESH out-dir** (resume is
per-ply; a late-added arm over an existing dir rolls up as a silent 0.00% — the instrument
refuses that path, exactly as surface A's did after disclosing the defect) and merged with
`merge_calib_dirs.py`-style champion-pick diffing — then re-enter §3 with the ladder
`{0.25, 0.5, 1.0, 2.0}`. This is the only rung addition this document authorises; it fires at
most once; a `d0p125` is a NEW calibration.

### 3.2 `FUND-SMALLEST` — the funding branch

**Else if any rung has `f ≥ 0.10`:** fund **exactly one** deploy cell, at the **SMALLEST dose
whose `f ≥ 0.10`**. Smallest dose, not largest `f`; a non-monotone ladder is read as
measured. The funded cell inherits [`DEPLOY_PREREG.md`](DEPLOY_PREREG.md) in
full: k8×1376 both arms, rust, `fixed_v1`+R9, exact-K 2, n=800 deck-paired, margin z primary,
fresh band claimed before game 1, all 13 wiring gates. If the named rung's Wilson-95 lower
bound is below 0.10, `marginal` rides into the prereg. A second cell is Joshua's separate,
documented decision, never licensed by this ladder.

### 3.3 `NO-EXPRESSION` — the stop branch

**Else** (`f < 0.10` on every rung, including `d0p25` if §3.1 fired): the finding is **"the
J-rules bundle does not express on the PRIOR surface at deploy depth"** — which, note, is
exactly the sims-washout outcome DESIGN §1 pre-registers as the honest failure mode, and it
is a REAL answer: it closes the last named encoding surface for the articulated strategy
short of root filters. Report the full ladder + CIs + realized n, flip the LEVER_INDEX row to
a measured "does not express", and **STOP**. Do NOT inflate the dose above 2.0; do NOT fish
through masks or scopes; do NOT fund on the §6 rust-unit "priors moved" evidence (bits moving
is not picks moving). **This is not a refutation of the anchor's strategy.**

### 3.4 Exhaustive map

| arithmetic outcome | branch |
|---|---|
| validity gate fails (checksum / partial / short corpus / hash INEQUALITY / control) | **VOID** |
| `f(1.0) > 0.20`, `d0p25` not yet measured | **FINER-RUNG** → measure 0.25 fresh-dir, re-enter |
| `f(1.0) = 0.20` exactly | no finer rung; fall through |
| any rung `f ≥ 0.10` (ladder settled) | **FUND-SMALLEST** — smallest such dose |
| `f < 0.10` on every rung | **NO-EXPRESSION** — report and STOP |
| all rungs `f = 0` | **NO-EXPRESSION**; additionally report the prior surface as inert at search depth |

---

## 4. Guards

- Ladder fixed at {0.5, 1.0, 2.0} + the one pre-committed 0.25; mask fixed at 31; scope fixed
  at `all`. Anything else is a new calibration.
- **Do not assume the "natural" dose is the fundable one** (the open-city lesson).
- "Where the flips land" is descriptive only — never a funding criterion.
- Corpus disjointness: E4 archives (calibration) vs a fresh self-play band (deploy).
- No band is claimed until a cell is funded; claimed at launch in `BAND_REGISTRY.csv`, never
  here. 1.25e11/1.26e11/1.27e11/1.28e11 are retired.
- **Stale-wheel capability is a launch blocker per box.** `search_config_rs` is fail-closed
  (TypeError) and the instrument runs a positive control, but a launcher that swallowed either
  would produce a champion-vs-champion cell reading *"the anchor's strategy is worth nothing"*
  instead of *"it never ran"* — and on THIS surface no hash can catch it, so the manifest's
  resolved `cand_jrules_prior.dose` and the control are the only guards. Treat them as such.
- **CL-079 rider:** this rule funds a deploy cell or nothing; no 2750 screen substitutes.
- **This rule governs the READ, not the build.** Extending the instrument is ordinary
  engineering; reading an arm's flip rate before this file is committed is what is forbidden.

---

## 5. The commitment

Committed to git before the calibration is executed; the branch is read off §3 exactly as
written. If §3 turns out to be the wrong rule, the readout records that and the wrong rule
binds — a rule rewritten after the numbers is not a rule. The readout (`CALIB_READOUT.md`,
this directory — deliberately not linked, it does not exist yet) will state which branch
fired, the full ladder with CIs and realized n, and this file's commit hash as evidence of
the ordering.
