# J-RULES ON SEARCH — CALIBRATION READ-RULE (how `jrules_dose` gets chosen, written BEFORE any flip rate exists)

> **STATUS: WRITTEN AND COMMITTED 2026-08-13, BEFORE THE CALIBRATION RAN AND BEFORE ANY
> ARM'S SEARCH FLIP RATE WAS READ.** At the time of writing, the replay instrument for this
> bundle ([`scripts/classical_search/jrules_e4_replay.py`](../../scripts/classical_search/jrules_e4_replay.py))
> had been built and unit-tested but **never executed against an archive**: no arm has produced
> a search flip rate, and no such number was available to the author of this document. That
> ordering is the entire point — it is what stops the dose from being chosen *after* seeing
> which rung looks best, the forking-path pattern behind four winner's-curse instances in the
> 2026-08-10 campaign.
>
> **0 games. No deck band. No elo statistic anywhere in this document.** Nothing here licenses
> a strength claim, and `governance/PRODUCTION.yaml` / `governance/BAND_REGISTRY.csv` are
> untouched on every branch below.
>
> ⚠️ The only J-rules dose numbers that existed when this was written are the **depth-1 greedy
> leaf-argmax** probe of [DESIGN §6](DESIGN.md#6-expressiveness--measured-and-one-uncomfortable-number)
> (`jr_dose_probe.py`: 0.1 → 6.2%, 0.25 → 12.5%, 0.5 → 18.8%, 1.0 → 25.0%, on 32 positions).
> **That is a DIFFERENT STATISTIC on a different corpus and is explicitly NOT the quantity any
> branch below reads** — DESIGN §7: deep search washes leaf perturbations out (open-city moved
> 21.9% of *leaf values*; denial's arm A flipped **4.45%** of *picks*). It is recorded here so a
> later reader can see exactly what was and was not known in advance, not as a prior to fund on.
>
> Direct parent, cloned deliberately rather than re-derived:
> [open-city CALIB_READ_RULE](../opencity_term_20260812/CALIB_READ_RULE.md) + [its
> READOUT](../opencity_term_20260812/CALIB_READOUT.md) + the deploy outcome those produced
> (**CL-080**). Term build, ladder and gates: [DESIGN.md](DESIGN.md) §6, §7, §8, §11 (G5).

---

## 1. What the calibration measures, and what it explicitly does not

Three arms replay the banked E4 human-vs-champion archives and, at each **champion decision
ply**, re-run the production search with the J-rules leaf against the production leaf under
CRN (shared agent seed, shared `_move_idx`, so every arm searches identical determinized
worlds), recording whether the **pick changes**. Arms share corpus, seeds and budget; only the
dose differs. The ladder is fixed by DESIGN §7 and reproduced here so that this file alone is
sufficient:

| arm | `jrules_dose` | `jrules_mask` |
|---|---|---|
| **d0p5** | 0.5 | 31 (`JR_ALL` = J1\|J2\|J5\|J6\|J8) |
| **d1p0** | 1.0 | 31 |
| **d2p0** | 2.0 | 31 |

`jrules_mask` is held at **31** in every rung. A per-rule ablation mask answers a *different*
question (which rule bites) and is a **new calibration**, run and named as such — mixing it
into this ladder is exactly the forking path this document exists to prevent. The instrument
stamps every mask actually used (`jrules_masks` in the rollup) so an ablation run can never be
mistaken for this one.

There is likewise **no symmetric/asymmetric axis**: DESIGN §12 Q1 ruled the term stays
antisymmetric, and the own-side-only variant is a NEW TERM with its own pre-registration.

**Measured: the champion-ply pick-flip rate.** **Not measured: strength, EV, or regret.**
A flip is not an improvement; a flip may be free in EV, and per §2 below a *large* flip rate is
a *risk*, not a prize. Nothing in this document licenses any statement about elo, and no branch
below may be quoted as evidence that the bundle helps.

⚠️ **The §6 expressiveness table is NOT a flip rate and may not be substituted for one.**
"The bundle fires on 95% of states with mean |T| ≈ 3.03" is an upper bound on decision changes,
measured on a random-play corpus at depth 0. The funding decision uses the search flip rate
from this instrument only.

**Report with the rate, always:** the realized corpus size (**expect ≈ 1,556 champion plies
over 26 archives** — the open-city calibration's realized n on the same bank; the bank grows
~1 game/evening, so re-count and report the realized number), per-arm **Wilson-95 CIs**
(reported as `[lo, hi]` and as `wilson95_lo`), the per-archive rules epoch resolved **from each
archive's own stamp** (never assumed — the bank mixes `fixed_v1`, `walled` and `app_aug2`), and
`replay_scores_match` for every archive. **Any archive that fails its replay checksum voids the
whole calibration** — fix and re-run; re-running is free (no band, no games, deterministic
searches).

---

## 2. The bar, and which statistic it is read on

**The funding bar is `f ≥ 0.10` (10%) on the POINT ESTIMATE of the search pick-flip rate.**

This is stated explicitly because it is the one place a reader could reasonably assume
otherwise. **The bar is on the point estimate, NOT on the Wilson-95 lower bound** — that is the
convention the open-city rule used and the one CL-080's funded arms were selected under
(`A_d0p5` read **10.09%** point estimate at n=1,556, whose Wilson-95 lower bound is *below* 10%,
and it was funded). Re-deriving the convention per term is itself a forking path, and changing
it would silently make this ladder incomparable to the only outcome anchor we have. So:

- **decision statistic:** the point estimate `f = flips / n_graded`, corpus-wide;
- **reported alongside, always:** the Wilson-95 interval and its lower bound;
- **mechanical annotation, no effect on the branch:** if the named rung's Wilson-95 lower bound
  is **below 0.10**, the readout must label it **`marginal`** and carry that word into the
  deploy pre-registration. It changes nothing about which branch fires — it is a disclosure,
  not a tie-break.

**Where the bar comes from** (arithmetic, fixed in advance; inherited unchanged from the
open-city rule §2 and quoted in DESIGN §7): a champion makes ~70 decisions/game, so a term that
changes fraction `p` of them needs a mean gain of `1.32 / (70·p)` points **per changed
decision** to move an n=800 deck-paired deploy cell by 2σ. At `p = 0.02` that is 0.95 pts per
changed move (implausible); at `p = 0.05`, 0.38 (borderline); at `p = 0.10`, 0.19 (plausible).
⇒ **below ~10% the cell buys a guaranteed unreadable null, a consumed fresh deck band, and a
false "the anchor's strategy is worth nothing" line in the record.** That is the failure this
rule exists to prevent.

⚠️ **Clearing the bar buys RESOLVABILITY, NOT SAFETY — this is the CL-080 lesson and it is the
reason branch §3.2 prefers the smallest clearing dose.** The open-city term's two funded arms
flipped **10.09%** and **18.89%** of champion picks and then cost **−53.8 elo** (margin z −5.86)
and **−190.3 elo** (margin z −19.38) at the deploy budget. The flip rate predicted that the cell
would *read*, and it read: **negative, monotonically worse with more expression**. So a bigger
flip rate is a bigger perturbation of a champion leaf that is already the strongest evaluator we
have — it is a bigger *risk*, not a bigger prize, and "expresses more" is never a reason to
prefer a rung.

**The open-city rule's `FUND-MARGINAL` branch (0.05 ≤ f < 0.10) is deliberately NOT inherited.**
CL-080 is why: an underpowered cell at the deploy budget costs a fresh band and returns a null
that bounds nothing, and DESIGN §7 states the bar as 10% with no marginal tier. Under this rule
`f < 0.10` everywhere is `NO-EXPRESSION` (§3.3), full stop, however close the ladder comes.

---

## 3. The decision rule (evaluated in order, first to fire wins)

Let `f(d)` = the corpus-wide champion-ply pick-flip point estimate for the rung at dose `d`,
from the instrument's `SUMMARY.json` `flip_rate` field, over **all** archives in
`measurement/e4_games/` with **no** `--limit-games` / `--limit-plies`.

### 3.0 `VOID` — the validity gate (checked before any rate is quoted)

If `all_replay_scores_match` is not `true`, or any summary is `partial`, or the corpus is not
the full archive bank, or the production leaf hash is not `a36d2e15a3b3d71d`, or any candidate
arm's leaf hash equals the champion's: **the calibration is VOID.** Fix and re-run. No branch
below may be read off a void run, and no number from one may be quoted anywhere.

### 3.1 `FINER-RUNG` — the pre-committed extension (fires before any funding)

**If `f(1.0) > 0.20`** (strictly greater than 0.20 on the point estimate — at exactly 0.20 this
branch does **not** fire), then **before anything is funded**:

1. add the rung **`d0p25` = dose 0.25, mask 31** (`FINER_RUNG_ARM_SPEC` in the instrument) to
   the ladder;
2. measure it on the **same corpus, same seed, same budget** — the instrument is resumable, so
   this is an added `--arm` over the same output directory;
3. re-enter §3 from the top with the ladder `{0.25, 0.5, 1.0, 2.0}`.

This is the **only** rung addition this document authorises, its trigger is a hard number
written before any arm was read, and it fires **at most once** (a `d0p125` rung is a new
calibration, not an extension). Rationale, DESIGN §7(ii): if the bundle expresses at >20% of
picks at its own literal magnitudes, the ladder's low end is where the decision actually lives,
and CL-080 says a 19% flip rate is where the −190 elo cell sat.

### 3.2 `FUND-SMALLEST` — the funding branch

**Else if any rung has `f ≥ 0.10`:** fund **exactly one** deploy cell, at the **SMALLEST dose in
the ladder whose `f ≥ 0.10`**. That dose is the named dose; every larger rung is *not* funded
regardless of how much better it expresses.

- Smallest **dose**, not largest `f`, and not "the dose closest to some target rate". If the
  ladder is non-monotone (e.g. 0.25 clears but 0.5 does not), the smallest clearing dose still
  wins — the rule reads the ladder as measured, it does not smooth it.
- **Exactly one cell.** DESIGN §8 provides for two doses on disjoint seed ranges of one band;
  this rule declines that provision. Under CL-080 the second (larger) rung is a *larger
  perturbation with a worse prior*, and a dose-response curve is not the question the deploy
  budget is being spent on. Funding a second cell is a separate, documented decision by Joshua —
  it is not licensed by this document, and it may not be justified by anything in this ladder.
- The funded cell inherits DESIGN §8 in full: k8×1376 both arms, `rust`, `fixed_v1` + R9,
  `--exact-k 2`, n = 800 deck-paired, **margin z primary**, on a **fresh** band registered in
  `governance/BAND_REGISTRY.csv` before game 1, with the O0–O12 + O4′ wiring gates read from the
  manifest before any strength number is opened.
- If the named rung's Wilson-95 lower bound is below 0.10, the word **`marginal`** is carried
  into the deploy pre-registration (§2). It does not change the choice.

### 3.3 `NO-EXPRESSION` — the stop branch

**Else** (`f < 0.10` on every rung of the ladder, including `d0p25` if §3.1 fired): the finding
is **"the J-rules bundle does not express at deploy depth"**. Report it — the full ladder, CIs,
realized n — flip the LEVER_INDEX row to a **measured "does not express at search depth"**, and
**STOP**. Specifically:

- ⛔ **Do NOT inflate the dose above 2.0 to force expression.** DESIGN §7: above 2.0 this is no
  longer "the champion's leaf plus his strategy", it is a different evaluator, and a cell run
  there answers a question nobody asked. There is no dose at which this branch converts into a
  funding branch.
- ⛔ Do not go fishing through `jrules_mask` ablations for a combination that clears the bar —
  every mask is a fresh multiple comparison against the same corpus.
- ⛔ Do not fund on the depth-1 greedy proxy, the §6 expressiveness table, or "it fires on 95%
  of states".
- ✅ **This is NOT a refutation of the anchor's strategy.** It is the measured statement that,
  expressed as an additive leaf term at these doses, it does not change what an 11,008-sim
  search plays. That is DESIGN §12 Q6's honest failure mode, and it is a real answer to the
  confound the tournament left behind — write it up as one.

### 3.4 Exhaustive map of arithmetic outcome → branch

| arithmetic outcome | branch |
|---|---|
| validity gate fails (checksum / partial / short corpus / hash) | **VOID** (§3.0) |
| `f(1.0) > 0.20`, `d0p25` not yet measured | **FINER-RUNG** (§3.1) → measure 0.25, re-enter |
| `f(1.0) = 0.20` exactly | no finer rung; fall through to §3.2/§3.3 |
| any rung `f ≥ 0.10` (after §3.1 has settled the ladder) | **FUND-SMALLEST** (§3.2) — smallest such dose |
| `f(0.25) ≥ 0.10` (rung present) | FUND-SMALLEST names **0.25** |
| `f(0.25) < 0.10 ≤ f(0.5)` | FUND-SMALLEST names **0.5** |
| `f(0.5) < 0.10 ≤ f(1.0)` | FUND-SMALLEST names **1.0** |
| `f(0.5), f(1.0) < 0.10 ≤ f(2.0)` | FUND-SMALLEST names **2.0** |
| exactly `f(d) = 0.10` at the smallest clearing `d` | clears (`≥`) — FUND-SMALLEST names `d` |
| `f < 0.10` on every rung | **NO-EXPRESSION** (§3.3) — report and STOP |
| `0.05 ≤ max f < 0.10` | **NO-EXPRESSION** (§3.3). There is no marginal tier (§2) |
| all rungs `f = 0` | **NO-EXPRESSION** (§3.3); additionally report the bundle as inert at search depth |

---

## 4. Guards

- **The dose ladder is fixed at {0.5, 1.0, 2.0}**, plus the one pre-committed `0.25` rung whose
  trigger is written in §3.1. Any other rung added after seeing the ladder is a **new
  calibration**, run and named as such.
- **The mask is fixed at 31.** Ablations are a separate calibration (§1).
- **Do not assume the "natural" dose is the fundable one.** Dose 1.0 is "the interview's own
  magnitudes", which makes it the *rhetorically* natural rung and exactly the one a reader would
  reach for by default. The open-city precedent is the warning: its **production-spec** arm read
  4.45% at the denial term and a looser arm read 13.62% — the default cell was not the fundable
  cell. This rule picks by measured expression, not by narrative fit.
- **"Where the flips land" is descriptive only.** Whether flips concentrate on the plies where
  Joshua out-plays the champion is genuinely interesting — and it is **not** a funding criterion
  and must not be used to rescue a rung that fails §3.
- **Corpus disjointness:** the calibration corpus (E4 human games) and the deploy corpus (a
  fresh self-play deck band) are disjoint, so nothing chosen here contaminates the cell's
  statistic.
- **No band is claimed until a cell is actually funded**, and it is claimed at launch in
  `governance/BAND_REGISTRY.csv` (never in this file). Bands 1.25e11 / 1.26e11 are retired (they
  adjudicated the Joshua-bot tournament).
- **Stale-wheel capability is a launch blocker, not a nicety** (DESIGN §11 G3/G4). `carc_rs`
  must carry `jrules_dose` on **every** box that runs a cell. `leaf_config_rs` is fail-closed
  and this instrument probes it explicitly per arm, but a launcher that swallowed the
  `TypeError` would produce a champion-vs-champion cell that reads as a beautiful, meaningless
  null — and here it would read as *"the anchor's strategy is worth nothing"* rather than *"it
  never ran"*.
- **CL-079 rider, carried into whatever this calibration funds:** a 2750-ablation-instrument
  result is a **screen**, never a kill and never an adoption; denial resolved negative at 2750
  (margin z −2.293, n=400) and read a **bounded null** at the deploy budget (z −0.127, n=800),
  and the two are not poolable on any branch. DESIGN §8 already says the deploy budget is the
  budget that decides — this rule funds a deploy cell or it funds nothing.
- **This rule governs the READ, not the build.** Building or extending
  [`jrules_e4_replay.py`](../../scripts/classical_search/jrules_e4_replay.py) is ordinary
  engineering and may proceed at any time — what may not proceed is *reading an arm's flip rate*
  before this file is committed.

---

## 5. The commitment

This document is **committed to git before the calibration is executed**, and the branch is read
off §3 exactly as written, against the numbers the run produces. If §3 turns out to be the wrong
rule, the honest move is to record that in the readout and let the wrong rule bind this
campaign — a rule rewritten after the numbers is not a rule. The readout
(`CALIB_READOUT.md`, this directory, with its JSON alongside — deliberately not linked here,
because at the time this file is committed it does not exist) will state
which branch fired, the full ladder with CIs and realized `n`, and the commit hash of *this*
file as evidence of the ordering — the same pointer the open-city readout carries.
