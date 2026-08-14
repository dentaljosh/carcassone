# OPEN-CITY ROUND 2 — CALIBRATION READ-RULE (the CL-080 falsifier arms: C re-dosed, capped A, asymmetric A — written BEFORE any flip rate exists)

> **STATUS: WRITTEN AND COMMITTED 2026-08-14, BEFORE THE ROUND-2 CALIBRATION RAN AND
> BEFORE ANY ARM'S FLIP RATE WAS READ.** At the time of writing, no round-2 arm has
> produced a number and no number from any round-2 arm was available to the author. The
> commit of this file precedes every calibration output in this directory — that ordering
> is the entire point (the forking-path discipline of the round-1 rule, inherited
> unchanged).
>
> **0 games. No deck band. No elo statistic anywhere in this document.** Nothing here
> licenses a strength claim, and `governance/PRODUCTION.yaml` is untouched on every
> branch.
>
> Direct parent, cloned deliberately rather than re-derived:
> [round-1 CALIB_READ_RULE](../opencity_term_20260812/CALIB_READ_RULE.md) (committed
> `6148388`) + [its READOUT](../opencity_term_20260812/CALIB_READOUT.md). Term + cap
> build: [TERM_SPEC](../opencity_term_20260812/TERM_SPEC.md) §2–§6 and **§10** (the
> 2026-08-14 `opencity_cap` addendum; reconcile PASS 90,772/0).

---

## 0. Authorization — what CL-080 left open, verbatim

CL-080 (DECISIONS 2026-08-13; [DEPLOY_PREREG](../opencity_term_20260812/DEPLOY_PREREG.md)
§6) is a resolved negative **for arm A (4 tiles / 2 edges / symmetric / UNCAPPED) at doses
0.5 and 2.0 only**, and its own scope clause names the falsifiers this round funds the
calibration for:

1. **Arm C (6 tiles / 3 edges)** — the predicate closest to the source guides' own
   "avoid three open edges"; calibrated in round 1 at **3.60 % / 5.85 %** flip (doses
   0.5 / 2.0), both below the 10 % resolvable floor, and **never funded**. The
   LEVER_INDEX row is explicit: *"if this lever is ever re-funded the next cell is ARM C
   at a dose re-calibrated to clear the 10 % expressiveness floor."*
2. **A CAPPED form** — the tested form was an uncapped product (TERM_SPEC §9 item 3),
   which is the leading explanation of the monotone harm. `opencity_cap` is now built
   (TERM_SPEC §10), default-off and default-cap bit-exact.
3. **The `opencity_symmetric = False` own-side-only variant** (TERM_SPEC §3's retained
   ablation knob; a different term, run and stamped as such).

"More n on arm A buys nothing; both cells are already resolved" — arm A uncapped is NOT
in this round on any branch.

---

## 1. What the calibration measures, and what it explicitly does not

The instrument is unchanged:
[`opencity_e4_replay.py`](../../scripts/classical_search/opencity_e4_replay.py) replays
the banked E4 human-vs-champion archives and, at each **champion decision ply**, re-runs
the production search with each candidate leaf against the production leaf under CRN
(shared agent seed, shared move index), recording whether the **pick changes**. The
E4 bank held 26 archives at round 1 (1,556 champion plies); the realized corpus size is
re-counted and reported with every rate.

**Measured: the champion-ply pick-flip rate. Not measured: strength, EV, or regret.** A
flip is not an improvement — round 1's funded pair proved this in the sharpest possible
way (expressiveness predicted the magnitude, not the sign, and both cells lost). Nothing
in this document licenses any statement about elo.

**Two runs, because `--asymmetric` is a run-level switch by design** (an asymmetric run
can never be mistaken for a symmetric one):

- **Run 1 (symmetric):** families C and ACAP, six arms in one pass sharing one champion
  search per ply (7 searches/ply).
- **Run 2 (asymmetric):** family ASYM, two arms (3 searches/ply), `--asymmetric`,
  separate output directory `calib_asym/`.

**The arms and ladders, fixed in advance** (`opencity_symmetric` True except family
ASYM; `opencity_cap` 0 except family ACAP; expected `cand_leaf_hash` computed on this
box before this file was committed, every one distinct and ≠ champion
`a36d2e15a3b3d71d`):

| family | arm | `size_min` (TILES) | `edge_min` | dose | cap | expected `cand_leaf_hash` |
|---|---|---|---|---|---|---|
| C (tight, re-dosed) | `C_d4p0` | 6 | 3 | 4.0 | — | `cce11e4d05f0d86e` |
| C | `C_d8p0` | 6 | 3 | 8.0 | — | `d52332443bc35fcf` |
| C | `C_d16p0` | 6 | 3 | 16.0 | — | `a4acf6d0925f7606` |
| ACAP (spec predicate, capped) | `Acap1_d0p5` | 4 | 2 | 0.5 | 1.0 | `d3ac9cc459f6d8d7` |
| ACAP | `Acap1_d2p0` | 4 | 2 | 2.0 | 1.0 | `a292f2cb05e45a22` |
| ACAP | `Acap3_d2p0` | 4 | 2 | 2.0 | 3.0 | `687f99980adaeee7` |
| ASYM (own-side-only) | `Asym_d0p5` | 4 | 2 | 0.5 | — | `6cfd4e4575aba1bc` |
| ASYM | `Asym_d2p0` | 4 | 2 | 2.0 | — | `3f05d72016d0d09c` |

**Why these ladders (a-priori sizing, written before any number):**

- **Family C {4, 8, 16}:** round 1 measured C at 3.60 % (dose 0.5) → 5.85 % (dose 2.0),
  i.e. ≈ ×1.63 per 4× dose. Log-linear extrapolation puts dose 8 near ≈ 9.5 % and dose
  16 near ≈ 12 % — so the ladder is chosen to **bracket the 10 % floor**, with dose 4 as
  the low anchor (≈ 7.5 %). The extrapolation is a guess and is written down so its
  failure is informative; the doses are NOT tuned after reading. A dose-16 C cell puts
  16 leaf points on a 6-tile 3-open city when the predicate fires — large, and priced
  deliberately: C's whole character is *rare but decisive*, and the floor arithmetic (§2)
  only cares whether the pick changes often enough to read.
- **Family ACAP {(0.5, c1), (2.0, c1), (2.0, c3)}:** capping strictly reduces the
  perturbation at fixed dose, so the round-1 uncapped rates (10.09 % at 0.5, 18.89 % at
  2.0) are **upper bounds** for the matching capped cells. The fundable capped cell
  therefore most plausibly sits at dose 2.0; dose 0.5 cap 1 measures the ladder bottom.
  Cap 1.0 is the count-of-cities degenerate form — the maximum mechanistic distance from
  the uncapped product CL-080 killed — and cap 3.0 admits bounded escalation.
- **Family ASYM {0.5, 2.0}:** the house doses, unchanged from round 1, because the
  asymmetric variant is a different *term*, not a different dose scale, and inheriting
  the round-1 ladder keeps the two calibrations comparable.

**Report with every rate:** realized corpus size and per-arm Wilson-95 CIs, the
per-archive rules epoch resolved **from each archive's own stamp**, and
`replay_scores_match` for every archive — any checksum failure voids the whole
calibration (re-running is free). ⚠️ Round 1's §4b instrument lesson is standing:
**calibrate on the real-game corpora** — arm C read 0.0 % on the golden corpus and 0/288
on the capability probe yet 3.60 % on real human games, so no offline-corpus reading and
no capability-probe pass may substitute for these flip rates.

---

## 2. The resolvable floor (inherited unchanged)

The bars are **inherited unchanged from the round-1 rule (5 % / 10 %)**, which inherited
them unchanged from denial. Re-deriving a bar per round is itself a forking path, and the
arithmetic has not moved: a champion plays ~70 decisions/game; an n=800 deck-paired
deploy cell resolves ≈ 1.32 pts/deck at 2σ; the mean gain required per changed decision
is `resolution / (70·p)` — below p ≈ 5 % no resolvable result is possible at affordable
n even if the term is genuinely good, and running such a cell buys a guaranteed null
plus a consumed band.

---

## 3. The decision rule (evaluated in order, first to fire wins — per FAMILY, then the global cut)

Let `f(arm)` = champion-ply pick-flip rate over the full corpus. The three families are
**separate ladders answering separate falsifiers** and are read independently; the
global constraint is that **at most 3 cells are funded in total, at most 1 per family.**

**Within each family, in its pre-committed least-perturbation order** —
C: `C_d4p0` ≺ `C_d8p0` ≺ `C_d16p0` (dose ascending) ·
ACAP: `Acap1_d0p5` ≺ `Acap1_d2p0` ≺ `Acap3_d2p0` (dose ascending, then cap ascending —
a tighter cap is the smaller perturbation at fixed dose) ·
ASYM: `Asym_d0p5` ≺ `Asym_d2p0` (dose ascending):

1. **FUND-SMALLEST (per family).** If any cell in the family has `f ≥ 0.10`: fund the
   **first** cell in the family's least-perturbation order that reaches `f ≥ 0.10`.
   One cell per family — no "one dose above" companion this round; round 1 already
   bought the dose-response observation for this term, and the 3-cell global budget is
   the binding constraint.
2. **FUND-MARGINAL (per family).** Else if any cell has `0.05 ≤ f < 0.10`: the family's
   highest-`f` cell is *eligible* — but is funded **only if fewer than 2 cells were
   funded by rule 1 across all families**, and its prereg must state it is
   **underpowered by construction** (a null from it bounds nothing and must be written
   up as "not resolvable at this n", never as a kill).
3. **NO-FUND (per family).** Else (`f < 0.05` throughout the family): the family is not
   funded. For family C specifically, `f < 0.05` even at dose 16 is a **structural**
   finding — the tight predicate cannot express at sane doses on real play — and the
   LEVER_INDEX row gets that as a measured "does not express at ≤16× dose", explicitly
   NOT a strength kill.
4. **Global cut.** If rules 1–2 would fund more than 3 cells, keep at most 3 by family
   priority **C ≻ ACAP ≻ ASYM** (C is the guides' own predicate and the falsifier
   CL-080's close-out named first; ASYM is the weakest mechanism argument — it breaks
   antisymmetry, the wart §3 of TERM_SPEC argues against).

**⚠️ On-the-bar recording (the `A_d0p5` precedent, now mandatory):** for every funded
cell, if the Wilson-95 CI straddles the funding bar, that fact is recorded **in the
readout at calibration time** — including which cell the rule would have selected on the
CI lower bound instead. The rule is still read on `f`, the point estimate, exactly as
round 1 read it; the recording is so a later null can be priced honestly ("funded at the
edge of the floor"), never so the selection can be re-litigated.

**Pre-registered predictions, so the branches can falsify something:** (a) family C's
ladder is predicted to cross 10 % between doses 8 and 16 (the §1 extrapolation); (b)
capped rates are predicted ≤ their uncapped round-1 counterparts at matching dose
(`Acap1_d0p5` ≤ 10.09 %, `Acap*_d2p0` ≤ 18.89 %) — a capped rate *above* its uncapped
counterpart would mean the cap is not merely shrinking the perturbation and the term's
shape is misunderstood; write that up as a surprise, fund nothing from that family, and
stop.

---

## 4. Guards

- **The ladders are fixed as §1 states.** Adding a dose, a cap value, or an arm after
  seeing any number is a **new calibration**, run and named as such.
- **The three families are never merged into one ladder.** A capped cell and an
  asymmetric cell are different terms, not rungs; the global cut of §3.4 is a budget
  rule, not a pooling license.
- **"Where the flips land" stays descriptive only** — barred from the funding decision,
  as in both parent rules.
- **Corpus disjointness:** the calibration corpus (E4 human games) and any funded cell's
  corpus (fresh self-play deck band) are disjoint by design.
- **No band is claimed by this calibration on any branch.** The band is claimed by the
  orchestrator at launch in `governance/BAND_REGISTRY.csv`, never in this directory.
- **Stale-wheel capability probe is a launch blocker, upgraded for the cap:** every box
  runs `chain_capability_probe.py --require opencity` **with `--cap`** for any capped
  cell before game 1 (TERM_SPEC §10's warning: a box that passed the CL-080-era probe
  still `TypeError`s on capped cells, and a launcher that swallowed it would produce a
  champion-vs-champion null). A capability-probe **pass is not proof of bite** (§4b
  lesson) — it gates wiring, never expressiveness.
- **CL-079 rider, carried forward:** whatever this calibration funds, the verdict
  instrument is a **deploy-budget (k8×1376 = 11008) fair-PIMC cell at n ≥ 800 on its own
  fresh band** — no 2750 screen substitutes, and nothing is poolable across instruments
  or bands.
- **CL-080 scope discipline:** no cell this round re-measures arm A uncapped at any
  dose, and no result this round may be summed, contrasted, or meta-analysed with the
  CL-080 cells (different candidates, different bands; CL-068 over-dispersion applies to
  any cross-band remark, which must remain qualitative).
- **This rule governs the READ, not the build.** The cap build, the instrument's 5th
  arm field, and the wheel work may proceed and be committed at any time — what may not
  proceed is *reading a round-2 arm's flip rate* before this file is committed.

---

## 5. The commitment

This document is committed to git before the round-2 calibration is executed, and the
funding branches are read off §3 exactly as written. If §3 turns out to be the wrong
rule, the honest move is to record that in the readout and let the wrong rule bind this
campaign. The readout (`CALIB_READOUT.md`, this directory) will state which branches
fired per family, the full ladders with Wilson-95 CIs and realized `n`, every on-the-bar
condition of §3, and the commit hash of *this* file as evidence of the ordering.
