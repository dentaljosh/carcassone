# DENIAL CALIBRATION — HOW THE SCREEN'S KNOBS GET CHOSEN (written BEFORE the numbers)

> **STATUS: written 2026-08-11 late, while all three calibration arms were still running
> and NO arm's flip rate had been read.** Its only purpose is to stop the screen's dose and
> thresholds from being chosen *after* seeing which arm looks best — the forking-path
> pattern behind four winner's-curse instances in the 2026-08-10 campaign. 0 games, no deck
> band, no elo statistic anywhere in this document.

## 1. What the calibration measures, and what it explicitly does not

Three arms replay the banked E4 human-vs-champion archives and, at each champion decision
ply, re-run the production search with the denial leaf against the production leaf under
CRN, recording whether the **pick changes**. Arms share corpus, seeds and dose ladder; only
the predicate thresholds differ:

| arm | `denial_size_min` | `denial_open_max` | doses |
|---|---|---|---|
| A | 8 | 2 | 1.0, 4.0 |
| B | 5 | 3 | 1.0, 4.0 |
| C | 3 | 4 | 1.0, 4.0 |

**Measured: pick-flip rate.** **Not measured: strength, EV, or regret.** A flip is not an
improvement. Nothing in this document licenses any statement about elo.

## 2. Why a flip-rate floor exists at all (the arithmetic, fixed in advance)

An n=200 deck-paired screen resolves ≈ **±35 elo at 2σ ≈ ±2.0 pts/deck**. A champion plays
~70 decisions per game. If the term changes a fraction `p` of them, the mean gain required
*per changed decision* to produce a resolvable effect is `2.0 / (70p)` points:

| flip rate `p` | changed moves/game | required gain per changed move |
|---|---|---|
| 0.02 | 1.4 | **1.43 pts** — implausible for a marginal move |
| 0.05 | 3.5 | 0.57 pts — borderline |
| 0.10 | 7.0 | 0.29 pts — plausible |
| 0.20 | 14.0 | 0.14 pts — comfortable |

⇒ **A cell whose flip rate is below ~5% cannot produce a resolvable screen result at n=200
even if the term is genuinely good.** Running it would buy a guaranteed null, a consumed
deck band, and a false "targeted denial is dead" line in the record. That is the failure
this rule exists to prevent.

## 3. The decision rule (evaluated in order, first to fire wins)

Let `f(arm, dose)` = champion-ply pick-flip rate over the full corpus.

1. **FUND-SMALLEST.** If any cell has `f ≥ 0.10`: fund the screen using the **smallest dose**
   and the **tightest thresholds** that reach `f ≥ 0.10`. Rationale: dose escalation on a
   rare trigger is a blunt instrument — it distorts the leaf's global scale to buy a few
   flips — so prefer widening the predicate over raising the dose when both reach the bar,
   and prefer the least perturbation that clears it. Up to 3 cells: the chosen cell, plus
   one dose above and (if it also clears 0.05) one below, so the screen sees a dose-response
   rather than a point.
2. **FUND-MARGINAL.** Else if any cell has `0.05 ≤ f < 0.10`: fund **at most two** cells at
   the highest-`f` settings, and record in the screen's prereg that it is **underpowered by
   construction** — a null from it bounds nothing and must be written up as "not resolvable
   at n=200", never as a kill.
3. **STRUCTURAL-NO-FUND.** Else if `f < 0.05` everywhere **and** the ladder is flat
   (arm C's best `f` is less than ~2× arm A's best): **do not fund the screen.** This is the
   pre-registered reading of the mechanism concern raised at code review — the term prices a
   *state* the champion's move usually cannot affect, so it lands as a near-constant offset
   across sibling moves and cancels in the argmax. Widening the predicate then cannot help,
   because the extra firings are also constant-across-siblings. **Consequence:** record the
   structural finding, flip the LEVER_INDEX row to a measured "does not express" rather than
   a strength kill, and name the re-specified successor (a term keyed to *what our move
   changes* — feeds vs. denies — instead of to the state) as NEVER-TRIED for a future
   decision. Explicitly **not** a refutation of targeted denial as an idea.
4. **UNRESOLVED.** Else (`f < 0.05` everywhere but the ladder is clearly rising with
   loosening): the predicate is the binding constraint and the tested range was too tight.
   Do not fund a screen; report the ladder and hand the threshold choice to Joshua, since
   going wider than arm C starts changing what the term *means*.

## 4. Guards

- **The dose ladder is fixed at {1.0, 4.0} in all three arms.** Any temptation to add a dose
  after seeing the ladder is a new calibration, run and named as such — not an extension of
  this one.
- **"Where the flips land" is descriptive only.** Whether flips concentrate on the plies
  where Joshua out-farmed the champion is genuinely interesting and is the reason the E4
  corpus was chosen — but it is **not** a funding criterion in this rule and must not be
  used to rescue a cell that fails §3. It informs the *successor term's* design, nothing
  tonight.
- **The calibration corpus (E4 human games) and the screen corpus (fresh self-play deck
  band) are disjoint**, so nothing chosen here contaminates the screen's statistic.
- No band is claimed until a screen is actually funded, and the band is claimed at launch.
