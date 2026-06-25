# V29_EVAL_PLAN — matchups, depths, n, thresholds

Harness: [scripts/v29/eval_v29_vs_v28.py](../../scripts/v29/eval_v29_vs_v28.py) (paired decks, balanced seats, resumable,
shared-claim, full-config manifest). Side A = v2.9 candidate, side B = v2.8 baseline.
**Winrate is the throne; margin/z is a diagnostic.**

## Measured cost anchors (5900XT, object path, this branch)
- sims=200 → **19.2 s/game** (v2.9 side forces the slower object path)
- sims=800 → ~77 s/game
- sims=6400 → ~615 s/game (≈10 min/game) — extrapolated ×8 from 800, **confirm before trusting**

Per-candidate wall (14 workers, paired):
| depth | n=200 | n=400 | n=800 |
|---|---|---|---|
| sims=200 | ~5 min | ~9 min | ~18 min |
| sims=800 | ~18 min | ~37 min | — |
| sims=6400 | ~2.4 h | ~4.9 h | — |

⇒ **screen cheap at sims=200; reserve sims=6400 for the single survivor (and split it
across all 3 boxes → ~1.7 h).**

## Staged protocol (cheapest-informative-first)

**Wave 1 — screen @ sims=200, n=200 paired** (~5 min each; ~50 min for all 10 local).
Candidates: A8, A12, A16, A24, A32, A48, Bmild, Baggr, Bk1, Bk3, **+ a v28-vs-v28 null
control** (must land ≈0.500 — proves the harness/pairing is unbiased).
- Power: n=200 → 1σ≈±35 elo / ±25? (unpaired); deck-paired tighter. Coarse — KILLS
  losers (wr ≤ 0.48) and FLAGS strong (wr ≥ 0.55); cannot resolve a +20-elo gain.

**Wave 1 — verdict @ sims=200, n=400 paired** (~9 min each). Only candidates with
Wave-1-screen wr ≥ 0.52. n=400 paired ≈ ±12 elo ⇒ resolves wr ≥ 0.53.

**Wave 1 — washout check @ sims=800, n=400 paired** (~37 min each). Only finalists
(n=400 wr ≥ 0.53). This is the key gate: leaf gains can wash out under deeper search
(the deck-aware-closure lesson). A term that holds 200→800 is real leaf quality.

**Wave 2 — combination** (best-A + best-B) only if both pass Wave 1, same ladder.

**Final — strength arbiter @ h6400 / h3200, n=400 paired.** Single best config only.
Split across 5900XT + Xeon + laptop. State ETA + ask box. Secondary: candidate vs
RoD_iter_01 (does the leaf change help/hurt vs the neural champion).

## Matchups
- Primary: `candidate_h{6400,3200}_v2.9 vs h{6400,3200}_v2.8` (same depth both sides).
- Secondary: `candidate_h{6400,3200}_v2.9 vs RoD_iter_01`.
- Screening uses sims=200 both sides (h200-equivalent), NOT h6400.

## Seeds / decks
- Clean-eval seed namespace (`ep.assert_clean_eval_seed_range`); paired (same deck both
  seats). Distinct seed-start per (candidate, depth) cell so caches never collide.
- Default seed-start 1_000_000_000 (clean-eval floor), +N//2 per cell.

## Reporting (per cell → V29_RESULTS.md)
WR, Elo, paired margin, paired z, WDL, **pre-endgame lead split** (snapshot at
deck ≤ 6 tiles — pre-outcome, not a final-margin collider): {behind ≤−5, even −4..4,
ahead 5..19, blowout ≥20}, per-bucket wr + avg margin. Runtime. Phase split deferred to
the analysis script if a candidate survives to Wave-1-verdict.

## Acceptance (from the spec)
- **Interesting:** wr ≥ 0.53 @ n≥400; OR positive-but-underpowered with margin gain
  concentrated in even/behind buckets (NOT blowout) and padding ruled out.
- **Strong:** wr ≥ 0.55 @ n≥400.
- **Suspicious:** margin up but wr flat; gain is blowout-bucket padding; runtime 2× w/o wr.
- **Dead:** wr ≤ 0.50 @ n≥400; OR only improves blowout-bucket margin; OR regresses v2.8.

## What we will NOT do
- Re-run Candidate C (deck-aware) — pre-killed null ×2.
- Train RoD2 / promote any checkpoint / touch PRODUCTION.yaml — classical audit only.
- Promote on a single screen, or on margin/trap-score without the winrate gate.
