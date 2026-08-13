# OPEN-CITIES TERM — CALIBRATION READ-RULE (how the dose and thresholds get chosen, written BEFORE any flip rate exists)

> **STATUS: WRITTEN AND COMMITTED 2026-08-12, BEFORE THE CALIBRATION RAN AND BEFORE ANY
> ARM'S FLIP RATE WAS READ.** At the time of writing the replay instrument for this term had
> not been extended yet, let alone executed: **no arm has produced a number, and no number
> from any arm was available to the author of this document.** That ordering is the entire
> point — it is what stops the dose and the thresholds from being chosen *after* seeing which
> arm looks best, the forking-path pattern behind four winner's-curse instances in the
> 2026-08-10 campaign.
>
> **0 games. No deck band. No elo statistic anywhere in this document.** Nothing here
> licenses a strength claim, and `governance/PRODUCTION.yaml` is untouched on every branch.
>
> **DOWNSTREAM OUTCOME (added at close-out 2026-08-13, banner only — no rule below was
> touched):** branch **`FUND-SMALLEST`** fired and funded `A_d0p5` + `A_d2p0`
> ([CALIB_READOUT.md](CALIB_READOUT.md)); both cells then ran at deploy budget and both fired
> **`N2 NEGATIVE`** (margin z **−5.86** / **−19.38**, elo **−53.85 ± 12.43** / **−190.27 ±
> 14.17**) ⇒ **the lever closes for ARM A ONLY** — arms **B (3/2)** and **C (6/3, the predicate
> closest to the source guides' "avoid three open edges")** were calibrated here and **never
> funded**, and nothing about them is decided. See [DEPLOY_PREREG.md](DEPLOY_PREREG.md) §5 N2
> and DECISIONS 2026-08-13. **The rule's own §3.1 alternative reading is now on the record as
> untaken and untested:** read on the CI lower bound the rule would have selected `B_d0p5`, a
> *looser* predicate; that cell was never played, so this document's selection is the one thing
> the deploy cells cannot retro-validate. ⚠️ **The instrument lesson of §4b outlives the arm:**
> arm C read **0.0 %** bite on the golden corpus and **0/288** on the capability probe yet
> **3.60 %** on real human games — an offline gate corpus can lack the structures real play
> contains, so a 0 % corpus reading is not evidence a predicate is inert.
>
> Direct parent, cloned deliberately rather than re-derived:
> [denial CALIB_READ_RULE](../denial_screen_20260811/CALIB_READ_RULE.md) +
> [its READOUT](../denial_screen_20260811/CALIB_READOUT.md). Term build + parameter table:
> `measurement/opencity_term_20260812/TERM_SPEC.md` §5–§7 (lands in the main tree with the
> term worktree; not linked here because this file is written before that merge).

---

## 1. What the calibration measures, and what it explicitly does not

Three arms replay the banked E4 human-vs-champion archives and, at each **champion decision
ply**, re-run the production search with the open-city leaf against the production leaf under
CRN (shared seeds, shared move index), recording whether the **pick changes**. Arms share
corpus, seeds and dose ladder; only the predicate thresholds differ. Arms and ladder are
fixed by `TERM_SPEC` §7 and reproduced here so that this file alone is sufficient:

| arm | `opencity_size_min` (distinct TILES) | `opencity_edge_min` (open cells) | doses |
|---|---|---|---|
| **A (production spec)** | 4 | 2 | 0.5, 2.0 |
| **B (loose)** | 3 | 2 | 0.5, 2.0 |
| **C (tight)** | 6 | 3 | 0.5, 2.0 |

`opencity_symmetric` is held at **`True`** in all three arms. Flipping it is a *different
term*, not a rung — mixing it into this ladder is exactly the forking path this document
exists to prevent.

**Measured: the champion-ply pick-flip rate.** **Not measured: strength, EV, or regret.**
A flip is not an improvement; a flip may be free in EV. Nothing in this document licenses any
statement about elo, and no branch below may be quoted as evidence that the term helps.

⚠️ **The wiring bite is NOT a flip rate and may not be substituted for one.** `TERM_SPEC` §6
reports that 21.9% of *leaf values* on the golden corpus differ from the champion's at the
spec thresholds. That is an upper bound on decision changes, measured on a different corpus,
and the denial precedent shows the gap is large (denial's arm A changed plenty of leaf values
and flipped **4.45%** of picks). The funding decision uses the flip rate only.

**Report with the rate, always:** the realized corpus size (the denial calibration graded
**1,079 champion plies over 18 archives**; the E4 bank grows ~1 game/evening, so re-count),
per-arm Wilson-95 CIs (at n ≈ 1,079 the half-width is ≈ ±1.3 pp at f = 5% and ≈ ±1.8 pp at
f = 10%, so the bars below are not knife-edge), the per-archive rules epoch resolved **from
each archive's own stamp** (never assumed — the bank mixes `fixed_v1`, `walled` and
`app_aug2`), and `replay_scores_match` for every archive. **Any archive that fails its replay
checksum voids the whole calibration** — fix and re-run; re-running is free (no band, no
games, deterministic searches).

---

## 2. Why a flip-rate floor exists at all (the arithmetic, fixed in advance)

A champion plays ~70 decisions per game. If the term changes a fraction `p` of them, the mean
gain required **per changed decision** to produce a resolvable cell is `resolution / (70·p)`
points. The two instruments this term could be judged on have measured resolutions:

| | resolution (2σ) | source |
|---|---|---|
| n=200 deck-paired **screen** at the 2750 ablation instrument | ≈ **2.0 pts/deck** (≈ ±35 elo) | house table + capscurve realized σ |
| n=800 deck-paired cell at the **deploy** budget (k8×1376) | ≈ **1.32 pts/deck** (≈ ±23 elo) | band 1.24e11 realized se, the denial deploy confirm |

| flip rate `p` | changed moves/game | required gain per changed move — screen | — deploy n=800 |
|---|---|---|---|
| 0.02 | 1.4 | **1.43 pts** — implausible for a marginal move | **0.95 pts** — still implausible |
| 0.05 | 3.5 | 0.57 pts — borderline | 0.38 pts — borderline |
| 0.10 | 7.0 | 0.29 pts — plausible | 0.19 pts — plausible |
| 0.20 | 14.0 | 0.14 pts — comfortable | 0.09 pts — comfortable |

⇒ **A cell whose flip rate is below ~5% cannot produce a resolvable result at either
instrument at affordable n, even if the term is genuinely good.** Running it buys a
guaranteed null, a consumed deck band, and a false "open-city shaping is dead" line in the
record. That is the failure this rule exists to prevent.

**The bars below (5% / 10%) are INHERITED UNCHANGED from the denial rule, deliberately.**
Re-deriving a bar per term — even with better arithmetic — is itself a forking path, and the
deploy column above shows the better instrument would only *loosen* them slightly. Inheriting
also keeps the two calibrations comparable, which is the only way the ladder shapes can ever
be read against each other.

---

## 3. The decision rule (evaluated in order, first to fire wins)

Let `f(arm, dose)` = champion-ply pick-flip rate over the full corpus.

1. **FUND-SMALLEST.** If any cell has `f ≥ 0.10`: fund the screen using the **smallest dose**
   and the **tightest thresholds** that reach `f ≥ 0.10`. Rationale, and it is stronger here
   than for denial: this term's `T` is a **product** of two excesses (tiles over `size_min`
   × open cells over `edge_min`), so it grows faster than denial's linear escalation and an
   equal dose is a larger perturbation of the leaf's global scale — `TERM_SPEC` §5 is explicit
   that the ladder must be bracketed **downward** from the defaults. So: prefer widening the
   predicate over raising the dose when both reach the bar, and prefer the least perturbation
   that clears it. Up to 3 cells: the chosen cell, plus one dose above and (if it also clears
   0.05) one below, so the screen sees a dose-response rather than a point.
2. **FUND-MARGINAL.** Else if any cell has `0.05 ≤ f < 0.10`: fund **at most two** cells at
   the highest-`f` settings, and record in the screen's prereg that it is **underpowered by
   construction** — a null from it bounds nothing and must be written up as "not resolvable
   at n=200", never as a kill.
3. **STRUCTURAL-NO-FUND.** Else if `f < 0.05` everywhere **and** the ladder is flat (arm B's
   best `f` is less than ~2× arm C's best): **do not fund the screen.** Record the structural
   finding, flip the LEVER_INDEX row to a measured "does not express" rather than a strength
   kill, and name the re-specified successor (a term keyed to *what our move changes* — does
   this placement enlarge or close an over-open city — instead of to the board state) as
   NEVER-TRIED for a future decision. Explicitly **not** a refutation of open-city shaping as
   an idea.
   **⚠️ Pre-registered prediction, recorded so this branch can falsify something:** for
   denial, this branch was the code-reviewer's constant-offset-cancellation hypothesis, and
   the measured ladder **refuted** it (rates rose ~5× A→C). For *this* term the a-priori case
   for cancellation is **weaker still** — the champion's own tile placement directly changes a
   city's tile count and open-edge count, so the term is not merely pricing a state the move
   cannot affect. If this branch nevertheless fires, that is a genuine surprise and should be
   written up as one, not as a routine null.
4. **UNRESOLVED.** Else (`f < 0.05` everywhere but the ladder is clearly rising as the
   predicate loosens): the predicate is the binding constraint and the tested range was too
   tight. Do not fund a screen; report the ladder and hand the threshold choice to Joshua —
   going looser than arm B (`size_min` 3 at `edge_min` 2 already prices nearly every
   incomplete city) starts changing what the term *means*.

**Arm C is expected to read ≈ 0** — `TERM_SPEC` §6 measured the `(6, 3)` predicate firing on
**0.0%** of golden-corpus leaf values. It is in the ladder so the ladder's *shape* is
measured rather than assumed, and a nonzero arm C would itself be information. **A zero arm C
is not a failure of the calibration and does not license dropping it from the report.**

---

## 4. Guards

- **The dose ladder is fixed at {0.5, 2.0} in all three arms.** Any temptation to add a dose
  after seeing the ladder is a **new calibration**, run and named as such — not an extension
  of this one. The same applies to adding a fourth arm.
- **The resolvable-floor guard is the whole point, and the denial precedent is the reason
  it is not optional:** denial's **production-spec** arm read **4.45%** — *below* the floor —
  while a looser arm read **13.62%**. A default screen would have used the spec thresholds
  and bought a guaranteed null on a term that demonstrably does change play at a wider
  predicate. **Do not assume the spec cell is the fundable cell.** This term's spec cell
  (`4, 2`) is a *guess from the strategy guides*, not a calibrated recommendation, and
  `TERM_SPEC` §5 says so in the table itself.
- **"Where the flips land" is descriptive only.** Whether flips concentrate on the plies where
  Joshua out-plays the champion is genuinely interesting and is why the E4 corpus was chosen —
  but it is **not** a funding criterion here and must not be used to rescue a cell that fails
  §3. It informs the successor term's design, nothing tonight.
- **Corpus disjointness:** the calibration corpus (E4 human games) and any screen corpus
  (fresh self-play deck band) are disjoint, so nothing chosen here contaminates the screen's
  statistic.
- **No band is claimed until a screen is actually funded**, and the band is claimed at launch
  in `governance/BAND_REGISTRY.csv` (never in this file). The screen must draw a band no
  earlier decision has influenced.
- **Stale-wheel capability probe is a launch blocker, not a nicety.** `carc_rs` must be
  rebuilt and *proved* to carry the four knobs on **every** box before a single cell runs
  (`TERM_SPEC` §6's manual step; the house pattern is
  `scripts/classical_search/chain_capability_probe.py --require <term>`, which needs an
  `opencity` mode). `leaf_config_rs` is fail-closed, but a launcher that swallows the
  `TypeError` would produce a champion-vs-champion cell that reads as a perfect null.
- **CL-079 rider, carried into whatever this calibration funds:** a 2750-ablation-instrument
  result is a **screen**, never a kill and never an adoption. Denial resolved negative at 2750
  (margin z −2.293, n=400) and read a **bounded null** at the deploy budget (z −0.127, n=800)
  — the two are not poolable on any branch. So the funding decision here buys at most a
  screen, and any kill or adoption sentence about the open-city term requires a deploy-budget
  cell on its own band. See [PREREG_DEPLOY_CONFIRM](../denial_screen_20260811/PREREG_DEPLOY_CONFIRM.md).
- **This rule governs the READ, not the build.** Extending
  [`denial_e4_replay.py`](../../scripts/classical_search/denial_e4_replay.py) (or adding a
  sibling) to replay the open-city term is ordinary engineering and may proceed at any time —
  what may not proceed is *reading an arm's flip rate* before this file is committed.

---

## 5. The commitment

This document is **committed to git before the calibration is executed**, and the funding
branch is read off §3 exactly as written, against the numbers the run produces. If §3 turns
out to be the wrong rule, the honest move is to record that in the readout and let the wrong
rule bind this campaign — a rule rewritten after the numbers is not a rule. The readout
(`CALIB_READOUT.md`, this directory) will state which branch fired, the full 3×2 ladder with
CIs and realized `n`, and the commit hash of *this* file as evidence of the ordering — the
same pointer the denial readout carries.
