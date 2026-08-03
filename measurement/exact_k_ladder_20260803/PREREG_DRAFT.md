# F13 — Modern exact-K winrate ladder under fixed_v1 (PREREG DRAFT)

> **STATUS: 📝 DRAFT — NOT AUTHORIZED, NOT FUNDED, no band claimed, nothing launched.**
> Written 2026-08-03 while the rust solver bench was fresh, so that funding the ladder
> (roadmap F13, Joshua's call) is a launch, not a design session. Open choices for
> Joshua are marked ⚖️. Charter: DECISIONS 2026-08-03 (afternoon) solver-port entry;
> cost basis: [../rust_solver_bench_20260803/BENCH.md](../rust_solver_bench_20260803/BENCH.md).

## Question

Does exact endgame play deeper than production buy **wins** (not margin) at today's
champion, under the adopted rules? The June null (DECISIONS 2026-06-24) is powered only
through K=3, is era-bound (RoD1/h3200 prefixes, v2.8 leaf, walled), and its winrate ladder
0.526 → 0.537 → 0.568 was monotone-up. This closes the question powered at every rung —
or fires the specialized-endgame-net lever (LEVER_INDEX) if winrate moves at K≥5.

## Design

- **Incumbent (both-sides base):** the production champion in clairvoyant matched-mode with
  its production exact tail **K≤4** (PRODUCTION.yaml: clairvoyant runs K≤4 identical both
  sides). Candidate = the same champion with the tail at **K = rung**.
- **Rungs:** K=2 (negative-control rung — *shallower* than production, expects ≤0),
  K=5, K=6 vs the K=4 incumbent. (K=4 vs K=4 is an identity, not a cell.)
  ⚖️ Option: add K=3 for a denser trend line (+1 cell cost).
- **n=400 deck-paired per rung** (200 decks × 2 seats), one fresh band per the registry
  (claim at launch; 1.05e11+ is free), all rungs on the SAME band → within-band
  deck-matched contrasts (the robust class). Solver = `carc_rs` (gates PASS; node-count
  equality means the python solver would agree on every solve that completes).
- **Rules:** fixed_v1 + `CARCASSONNE_FIX_R9=1` both sides, manifest-stamped (`r9_env_ok`).
- **Primary statistic:** deck-paired margin z per rung + the **within-band trend across
  rungs** (`feedback_trend_beats_underpowered_steps`); winrate secondary.

## The cap-hit branch (the part the June design lacked)

Per-position solve cost spans orders of magnitude (bench: 434 vs 74k nodes at equal K).
Pre-registered per-solve wall caps: **K≤4 uncapped · K=5 cap 300 s · K=6 cap 600 s.**
On cap hit the candidate's tail **falls back to the K−1 solve of the same position**
(never a raw leaf — the arm degrades toward the incumbent, biasing the measured effect
toward ZERO, i.e. conservatively). Every cap hit is counted in the manifest;
**if >20% of a rung's latch solves cap out, the rung reports "censored at rate r" and
its point estimate carries a ⚠️ not-a-verdict banner** regardless of z.

## Cost (bench-derived, pre-registered as an estimate not a promise)

Latch fires once per game per side + cheap TT-carried re-solves. Using bench p90s (not
medians): K=5 ≈ 1–5 min/game of tail, K=6 ≈ 3–10 min/game censored at 600 s. Two-box
W-wide (rust solves are ~100–250 MB/worker — cores-bound, not RAM-bound):
**K=2 rung ~1 h · K=5 ~2–4 h · K=6 ~4–8 h.** Whole ladder ≈ **1–2 box-days**;
schedule K=6 overnight. ⚠️ Bench-then-commit rider: run 10 games of the K=6 arm first
and check the realized cap-hit rate before launching the full rung.

## Decision map (pre-registered)

1. **All rungs' paired-margin z < +2 and the trend slope z < +2** → the June null
   generalizes, powered, modern-era: exact:K row gets its final stamp; the endgame-net
   lever is STILLBORN (ceiling argument); no further endgame-exactness work.
2. **K≥5 rung ≥ +2σ (uncensored) or trend z ≥ +2** → deeper endgame exactness is real
   at the modern champion: fund the endgame-net design (fair labels = marginalized —
   the expensive mode; bench prices that next) and/or evaluate shipping a deeper
   clairvoyant tail where mode permits.
3. **Censored-positive** (signal but cap-hit rate >20%) → raise caps ×3 on the affected
   rung only, n=200 re-run, then re-enter this map.
4. K=2 control rung reads **>+2σ** (shallower beats production) → instrument alarm:
   halt, audit the harness before interpreting anything.

## Falsifiers / guards

- Identity smoke before the ladder: K=4-vs-K=4, 20 games, must be 100% identical actions.
- Per-cell manifest: leaf hash both sides, profile, r9, caps, cap-hit counts, solver mode.
- The fair agent's production K≤2 marginalized latch is untouched by all of this.

**No results.csv row, no claim id, no PRODUCTION.yaml change until run + verdict.**
