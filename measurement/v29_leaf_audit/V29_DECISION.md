# V29_DECISION — promote / kill / top-up / combine

**Status: INTERIM — n=400 verdict DONE; sims=800 washout running.** No promotion,
no PRODUCTION.yaml edit, no checkpoint change without an explicit winrate-gated decision
here.

## n=400 verdict (sims=200, ±17 elo) — CONFIRMED
- **Bmild 0.570 (z+3.39 margin) and Baggr 0.566 (z+2.97) both CONFIRMED** — nonlinear
  meeple curve beats flat k=2 by ~+45–50 elo, gain in the competitive even-bucket (not
  padding). The two curves are tied; washout (sims=800) will pick the depth-robust one.
- **A32 KILLED** — regressed to 0.534, even-bucket 0.46 (padding), ~0 margin.
- **D2 deferred** — 0.547 weak-positive but fires 0.2% (mechanistically can't carry it).
- **The meeple curve is the v2.9 lever.** Gates remaining before any promotion talk:
  sims=800 washout (does it survive deeper search?) → h6400 (the strength arbiter).

## Interim read (Wave-1 screen, sims=200 n=200 — coarse, ±25 elo)
- **Lead candidate: Candidate B nonlinear meeple curve.** `Baggr` 0.580 (z+3.08 on the
  paired margin), `Bmild` 0.537. Flat-k controls (Bk1 0.417 / Bk3 0.472, both < flat
  k=2) prove it's the curve SHAPE, not the scalar. This is the predicted lever — B
  refines the one v2.8 term that worked (meeple economy). **Confirming at n=400, then
  the sims=800 washout, then h6400.**
- **A (win-shape): null + a trap.** Small T hurts (A8 0.355). A32 0.550 is a lone peak
  whose even-bucket wr is 0.45 → already-ahead padding, not strength. Likely noise.
- **D2 (punish): noise** (fires 0.2%). **E (farm): dead** (killed-cousin prior held).
- **The leaf is NOT fully at the search-compensated ceiling** — B opens real winrate
  headroom (subject to the n=400 + washout gates). That partially answers the program's
  core question: v2.8's tiny leaf WAS leaving winrate on the table, in the meeple term.

## Standing constraints (do not violate)
- v2.7 frozen + bit-identical; v2.8 stays production; v2.9 stays opt-in/experimental.
- No RoD2 training on these results. Classical evaluator/search audit only.
- The final strength arbiter is **paired full-game winrate vs h6400_v2.8** at n≥400.
  Margin / trap-score / endgame-local gains do NOT qualify on their own (the
  endgame-washout lesson).

## Decision rule
- **Promote a v2.9 config to a candidate-for-production** iff wr ≥ 0.55 @ n≥400 vs
  h6400_v2.8 AND it holds across the 200→800→6400 depth ladder (no washout) AND the
  gain is not blowout-bucket padding. Even then: promotion is a separate, explicit
  decision (re-sweep production knobs first — bug-fix-shifts-optima rule).
- **Top-up** a config that is interesting-but-underpowered (0.52–0.55, even/behind gain).
- **Kill** anything ≤ 0.50 @ n≥400 or that only pads blowouts.

## Pre-registered priors (before any eval)
- B (curve) most likely to move winrate (refines the proven meeple term).
- A (win-shape) plausible anti-padding gain; risk = loses margin resolution at small T.
- C dead (not run). D/E low prior (wrong layer / killed cousins).
- **Null hypothesis taken seriously:** v2.8's tiny leaf may already be at the search-
  compensated ceiling, in which case ALL candidates wash out and the honest verdict is
  "no leaf headroom; the lever is elsewhere (policy/search/value-head)."

_Recommendation + final recommended v2.9 config (if any) to be written here after Wave 1._
