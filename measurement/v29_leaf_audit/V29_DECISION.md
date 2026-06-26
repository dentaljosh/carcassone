# V29_DECISION — promote / kill / top-up / combine

> **⮑ SUPERSEDED BY THE V2.9.1 RETUNE (2026-06-25) — see [V29_1_RETUNE_PLAN.md](V29_1_RETUNE_PLAN.md).**
> The retune extended Bmild: re-tuning production knobs around it found ONE more lever
> (closure cap 5→8, +46 elo). **Final config = `Bmild_cap8`**, which BEATS *real* production
> v2.8 (`v28prod` = cap12+drop-3-open+flat-k2) by **+55 elo / z+3.94** (sims200 n400,
> depth-robust through sims800). NB: this doc's "v2.8" baseline below was the cap5/3-open
> env default, NOT production — the retune's throne test corrects that. h6400 arbiter on the
> final config deferred to promotion-time. Still nothing promoted.

**Status: AUDIT COMPLETE (core) — h6400 arbiter DONE. Bmild CLEARS the promotion bar;
promotion held for Joshua's explicit call.** No PRODUCTION.yaml edit, no checkpoint
change, no RoD2 training has occurred or will without that call.

## FINAL FINDING (h6400 arbiter, n=209)
**The v2.9 nonlinear meeple liquidity curve (Bmild) beats production v2.8 at the
strength arbiter: 0.581 wr, +3.6 margin, z+2.69 (significant), gain in competitive
games (even-bucket 0.64) not padding.** Depth-robust: 0.570 @ sims200 / 0.545 @ sims800
/ 0.581 @ h6400. This answers the program's core question — **v2.8's tiny expected-score
leaf WAS leaving winrate on the table, in the meeple-economy term; a diminishing-returns
+ emergency-penalty curve recovers ~+30–50 elo that holds to play depth.**

Bmild = `LeafConfig(meeple_k unused, v29_meeple_curve=(-8,-4,-1,0,2,3,4,5))` on the v2.8
base (cap=12, drop-three-open). Replaces the flat `meeple_k=2.0` term.

## Decision-rule check
✅ wr ≥ 0.55 at the h6400 arbiter (0.581, significant at n=209) · ✅ holds across the
200→800→6400 depth ladder (no washout) · ✅ gain in even/behind, not blowout padding.
**Bmild meets the "candidate-for-production" bar.**

## BUT — promotion is a SEPARATE, explicit decision (not taken here). Open items:
1. **Wave-2 curve optimization (DONE):** the best shape is **Bflattop** =
   `(-8,-4,-1,0,2,3,3.5,4)` — 0.583/z+4.42 @ sims200 n400, marginally above Bmild
   (0.570) but within 1σ (tied). The decomposition shows the **FLAT TOP drives the win**
   (cap meeple value: 6≈7 free meeples), NOT the steep low-end penalty (Bsteep≈Bmild),
   and over-aggression breaks it (Bxaggr 0.490 null). **Bflattop @ h6400 CONFIRMED**
   (n=258): 0.552 wr / +4.7 margin / z+3.47 — beats v2.8, **statistically TIED with Bmild**
   (0.581) at the arbiter (≈1σ). The sims=200 edge does NOT translate to a winrate edge at
   depth; Bflattop is margin-favored, Bmild winrate-favored. **Either is a valid v2.9
   curve — interchangeable.** If promoting, pick on taste (Bflattop has the cleaner shape
   logic + higher margin; Bmild has the firmer winrate point).
2. **Re-sweep production knobs (bug-fix-shifts-optima rule):** the curve changes the
   meeple-economy magnitude; cap / drop-three-open / residual_scale optima may shift.
3. **Neural champion-line impact UNTESTED (RoD_iter_01 matchup on hold):** v2.9 is a
   classical leaf win; whether it helps the *neural* agent (whose value head was trained
   against the v2.8 residual base) is unknown — and a clean test needs a retrain (out of
   current scope). The classical win does NOT automatically transfer to the champion.
4. n=209 not n=400 — significant but the tighter number wasn't run (called early).

**Recommendation:** record Bmild as a confirmed, promotion-worthy classical-leaf
candidate; finish Wave-2 to pick the best curve; defer actual production promotion +
the neural matchup to an explicit follow-up. v2.7 frozen, v2.8 production, v2.9 opt-in
throughout.

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
