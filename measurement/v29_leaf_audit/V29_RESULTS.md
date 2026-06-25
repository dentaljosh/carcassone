# V29_RESULTS — candidate eval table

Numbers from `scripts/v29/analyze_screen.py`; per-cell full config + git in each
`manifest.json`. CSV: `/mnt/c/carc-shared/v29_eval/wave1_screen_summary.csv`.

## Wave 1 — screen @ sims=200, n=200 paired (vs v2.8 baseline) — DONE 2026-06-25

Pre-endgame buckets = snapshot at deck ≤ 6 tiles (PRE-outcome, not the final-margin
collider): even = |lead|≤4, behind ≤−5, ahead 5–19, blowout ≥20.

| cand | n | wr | elo | avgΔ | z(margin) | even | behind | ahead | blowout | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **v28 (null ctrl)** | 200 | 0.495 | −3 | +0.5 | +0.33 | 0.52 | 0.15 | 0.71 | 1.00 | ✓ ≈0.500 (unbiased) |
| A8  | 200 | 0.355 | −104 | −16.7 | −8.85 | 0.57 | 0.13 | 0.68 | 0.87 | **kill** (over-compress) |
| A12 | 200 | 0.475 | −17 | −7.2 | −3.91 | 0.41 | 0.19 | 0.69 | 0.97 | kill |
| A16 | 200 | 0.507 | +5 | −3.8 | −2.33 | 0.50 | 0.16 | 0.80 | 0.90 | null |
| A24 | 200 | 0.507 | +5 | −1.2 | −0.70 | 0.46 | 0.23 | 0.70 | 0.96 | null |
| **A32** | 200 | 0.550 | +35 | +0.8 | +0.52 | **0.45** | 0.23 | 0.84 | 0.87 | **suspicious** (padding) |
| A48 | 200 | 0.490 | −7 | +0.1 | +0.05 | 0.50 | 0.17 | 0.65 | 0.92 | null (≈linear) |
| **Baggr** | 200 | **0.580** | +56 | +4.3 | **+3.08** | 0.57 | 0.22 | 0.64 | 0.89 | **STRONG → n400** |
| Bmild | 200 | 0.537 | +26 | +2.5 | +1.60 | 0.50 | 0.18 | 0.74 | 0.90 | flag → n400 |
| Bk1 (flat k=1) | 200 | 0.417 | −58 | −4.6 | −2.83 | 0.42 | 0.15 | 0.70 | 1.00 | kill (control) |
| Bk3 (flat k=3) | 200 | 0.472 | −19 | −0.1 | −0.08 | 0.46 | 0.11 | 0.61 | 0.94 | kill (control) |
| D2 (punish) | 200 | 0.540 | +28 | +0.7 | +0.45 | 0.68 | 0.22 | 0.65 | 0.98 | noise (fires 0.2%) |
| E1 (farm) | 200 | 0.477 | −16 | −0.1 | −0.09 | 0.50 | 0.19 | 0.72 | 0.91 | kill |
| E2 (farm) | 200 | 0.445 | −38 | −0.8 | −0.54 | 0.57 | 0.13 | 0.66 | 0.94 | kill |

n=200 power: 1σ ≈ ±25 elo — a coarse screen. Promote nothing here; flags go to n=400.

### Interpretation

**Candidate B (nonlinear meeple liquidity) is the signal.**
- **Baggr = 0.580 (z+3.08 on the paired MARGIN, not winrate-only)** is the standout, and
  it's not padding: the even-bucket (competitive) wr is 0.57 and avgΔ is +4.3 spread
  across buckets. The flat-k controls **prove it's the curve SHAPE, not the scalar** —
  flat k=1 (0.417) and k=3 (0.472) both LOSE to the flat k=2 baseline, yet the
  diminishing-returns + emergency-penalty curves beat it (Baggr 0.580, Bmild 0.537).
  This is exactly the predicted result: B refines the one v2.8 term that worked.

**Candidate A (win-shape) is null — and A32 is a trap, not a peak.**
- A8 (0.355) / A12 (0.475) confirm small-T over-compression is harmful (clean,
  monotonic, believable). A16–A48 hover at null.
- **A32 = 0.550 is a lone peak between null neighbors (A24 0.507, A48 0.490) — a noise
  signature.** Its bucket split refutes the win-shape thesis from the inside: even-game
  wr is **0.45 (below 0.5)**, with the edge coming from ahead/blowout buckets. That's
  already-ahead PADDING — the opposite of "help close games." Treat as noise/padding;
  confirm-to-kill at n=400, do not prioritize.

**D2 (punish) = 0.540 is noise.** The term fires in 0.2% of states (pre-registered) —
mechanically it cannot move winrate +28 elo. Almost certainly an n=200 spike.

**E (farm) is dead** (0.477 / 0.445), as the killed-cousin prior (farm-majority/denial,
2026-06-22) predicted. The 3%-firing rate did not translate to winrate.

### Survivors → Wave-1 verdict @ n=400
**Baggr** (primary), **Bmild** (secondary), **A32** + **D2** (confirm-to-kill).
Reuses the n=200 games (resumable); adds 100 new deck-pairs each.

## Wave 1 — verdict @ sims=200, n=400 paired — DONE 2026-06-25

| cand | n | wr | elo | avgΔ | z(margin) | even | behind | ahead | blowout | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **Bmild** | 400 | **0.570** | +49 | +3.8 | **+3.39** | 0.51 | 0.17 | 0.77 | 0.93 | **CONFIRMED** |
| **Baggr** | 400 | **0.566** | +46 | +3.1 | **+2.97** | 0.52 | 0.24 | 0.62 | 0.92 | **CONFIRMED** |
| A32 | 400 | 0.534 | +23 | +0.5 | +0.44 | **0.46** | 0.19 | 0.83 | 0.90 | **KILL** (padding) |
| D2 | 400 | 0.547 | +33 | +1.8 | +1.64 | 0.60 | 0.20 | 0.70 | 0.97 | defer (suspect) |

n=400 paired: 1σ ≈ ±17 elo. **Both meeple curves CONFIRMED** (~0.57, z+3 on margin —
significant; gain in the competitive even-bucket, not padding). Bmild ≈ Baggr (tied).
**A32 KILLED** — partially regressed (0.550→0.534) and the even-bucket stays 0.46 with
~0 margin = already-ahead padding, not strength (the win-shape thesis fails from inside).
**D2 deferred** — 0.547 is weak-positive but the term fires in 0.2% of states
(mechanistically can't carry +33 elo); not worth washout compute until/unless the
curves wash out.

→ **Washout (sims=800) on Bmild + Baggr** — the key gate before the expensive h6400.

## Wave 1 — washout check @ sims=800, n=200 paired — DONE 2026-06-25

| cand | n | wr | elo | avgΔ | z(margin) | even | behind | ahead | blowout | vs sims=200 |
|---|---|---|---|---|---|---|---|---|---|---|
| **Bmild** | 200 | 0.545 | +31 | +2.4 | +1.62 | 0.52 | 0.26 | 0.71 | 1.00 | 0.570 → 0.545 |
| **Baggr** | 200 | 0.532 | +23 | +2.7 | +1.77 | 0.42 | 0.16 | 0.69 | 0.88 | 0.566 → 0.532 |

**Verdict: the gain PERSISTS at depth, shrinking ~50% (not a washout).** Both curves
stay clearly > 0.50 with positive margin z (~+1.7) — categorically different from
deck-aware-closure's tight null (47.5%/z≈0). The ~50% retention (sims-200→800) **matches
the flat meeple term's own retention** (+179 elo @ heur200 → +95 @ heur800), so the
curve is a genuine refinement of a real term, not a shallow-search artifact. n=200 at
sims=800 is ±25 elo, so the ~+27 elo is suggestive-not-significant — a clean verdict at
this depth needs n=400. Bmild ≥ Baggr at both depths → **Bmild is the lead curve.**

→ Decision point (compute spend): h6400 arbiter on Bmild, OR confirm sims=800 at n=400
first. See V29_DECISION.md.

## Final — h6400 ARBITER, Bmild vs v2.8 — DONE 2026-06-25 (n=209, called early)

| cand | n | wr | elo | avgΔ | z(margin) | even | behind | ahead | blowout |
|---|---|---|---|---|---|---|---|---|---|
| **Bmild @ h6400** | 209 | **0.581** | +57 | +3.6 | **+2.69** | 0.64 | 0.26 | 0.68 | 0.93 |

**VERDICT: the meeple curve beats production v2.8 at the strength arbiter.** 0.581 wr,
z+2.69 on the paired margin (significant), gain in the competitive even-bucket (0.64),
not padding. Called at n=209 (already significant; n=400 would only tighten ±24→±17).

**The gain is depth-robust, NOT shrinking** (my earlier sims=800-based "washout" worry
was a small-n artifact):

| depth | Bmild wr | avg margin |
|---|---|---|
| sims=200 (n=400) | 0.570 | +3.8 |
| sims=800 (n=200) | 0.545 | +2.4 |
| **h6400 (n=209)** | **0.581** | **+3.6** |

Run cost note (for the record): h6400 is ~7 min/game single-worker but the leaf is
DRAM-latency-bound, so throughput plateaus at ~1 game/min regardless of worker count —
bumping local W14→30 + laptop→22 (62 workers) gave ZERO speedup over 34 workers
(confirmed the standing "W≈14–16 optimum" memory). 3-box (local+laptop+xeon) gen.

→ The audit's core question is answered: **v2.8's tiny leaf WAS leaving winrate on the
table, in the meeple-economy term, and a nonlinear curve recovers ~+30–50 elo that
holds to the reference depth.** Wave-2 (curve-shape decomposition) running; RoD_iter_01
neural matchup on hold.

## Final — h6400 / h3200, n=400  (single best config)

_(to be filled)_
