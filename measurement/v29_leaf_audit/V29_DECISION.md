# V29_DECISION — promote / kill / top-up / combine

**Status: PENDING — awaiting Wave-1 results.** No promotion, no PRODUCTION.yaml edit,
no checkpoint change will happen from this audit without an explicit, winrate-gated
decision recorded here.

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
