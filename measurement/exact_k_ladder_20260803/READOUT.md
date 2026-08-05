# F13 READ-OUT — the modern exact-K ladder: deeper-than-production exact play SATURATES

> **STATUS: MEASUREMENT COMPLETE 2026-08-05.** All four rungs landed, none censored, the
> negative control is healthy. The pre-registered map fires **branch 2 (screen-positive)**;
> the *scientific* content is a **saturation curve that flattens exactly at the incumbent's
> K=4**, and a **flat winrate at every rung**. The one open item is Joshua's funding call on
> the amended branch-2 confirm (see §5).
> Prereg (incl. the pre-results amendments): [PREREG_DRAFT.md](PREREG_DRAFT.md) ·
> analysis: `scripts/classical_search/analyze_f13_ladder.py` (committed before any cell ran) ·
> machine verdict: [VERDICT.json](VERDICT.json) · rows: `experiments/results.csv f13_exactk*`.

## 1. What ran

Band **1.06e11**, all four rungs on the SAME decks (within-band deck-matched — the robust
class). Candidate = the production champion with its exact tail at K = rung; incumbent = the
same champion at its production **K=4**. Screen budget **SIMS=2750** (the C5/C7 A/B knobs, NOT
the deploy 11008 — see the prereg amendment). Rules `fixed_v1` + R9 both sides, rust solver,
rust backend. Per-solve wall caps 5:300 / 6:600 with the downward fallback floored at K=4.

Two pre-flight gates passed first: **identity 17/20 games, 0 divergences** (the new rust tail
vs the pre-F13 python tail, move for move) and the **K6 bench-then-commit rider** (cap-hit
0.038 on 9 games).

## 2. Results

| rung | n | W-D-L | wr | elo | ±1σ | margin/deck | ±1σ | paired z | cap-hit rate | censored |
|---|---|---|---|---|---|---|---|---|---|---|
| K2 *(control)* | 400 | 191-5-204 | 0.484 | −11.3 | 17.4 | **−1.07** | 0.13 | −8.51 | 0.000 | no |
| K3 | 399 | 190-6-203 | 0.484 | −11.3 | 17.4 | **−0.76** | 0.12 | −6.44 | 0.000 | no |
| K4 | — | *(incumbent — identity, not a cell)* | — | 0 | — | **0** | — | — | — | — |
| K5 | 397 | 194-10-193 | 0.501 | +0.9 | 17.4 | **+0.11** | 0.04 | +2.72 | 0.082 | no |
| K6 | 394 | 194-10-190 | 0.505 | +3.5 | 17.5 | **+0.10** | 0.04 | +2.81 | 0.129 | no |

**Control is healthy:** K=2 is *shallower* than the incumbent and loses decisively
(z −8.51). Branch 4 (the instrument alarm that fires if the control reads POSITIVE) did not
trigger — the harness is measuring the game, not its own wiring.

## 3. The finding: the curve saturates exactly at production

Marginal value of each +1 K step, in points of seat-balanced margin per deck:

| step | Δ margin/deck |
|---|---|
| K2 → K3 | **+0.31** |
| K3 → K4 | **+0.76** ← the incumbent's own last step |
| K4 → K5 | **+0.11** |
| K5 → K6 | **−0.01** |

The marginal return collapses ~7× at the production boundary and is **gone by K6**. Going
shallower is expensive; going deeper is nearly free of benefit. **Production's K=4 already
sits at the knee of this curve** — which is a non-obvious vindication of a threshold that was
originally chosen on cost grounds (DECISIONS 2026-06-24 stopped at K=4 because the winrate
ladder went flat, not because anyone had measured the knee).

⚠️ **The linear trend statistic is therefore misleading on its own.** The analysis reports
slope **+0.321 ± 0.039 pts per +1 K, z = +8.21** — but that is a straight line fitted to a
visibly saturating curve, and it is driven almost entirely by the two rungs *below*
production. Do not quote the slope without the per-step table above.

## 4. Winrate: flat at every rung — the June result replicates, powered and modern

wr = 0.484 / 0.484 / 0.501 / 0.505 across K2/K3/K5/K6; elo +0.9 ± 17.4 (K5) and +3.5 ± 17.5
(K6) against a **2σ MDE of ±35 elo**. No rung resolves a win effect in either direction.

This is the June finding (**margin scales with K, winrate does not**) reproduced at the modern
champion, under the adopted rules, with the rust solver, at a powered n — and the June ladder
was powered only through K=3. The question the prereg asked in its own words — *"does exact
endgame play deeper than production buy **wins** (not margin)?"* — answers **no**.

## 5. ⚠️ Prereg defect, and the open call

**The map's thresholds do not test the map's question.** The question is worded on *wins*;
every branch threshold is written on *paired margin z*. So branch 2 fires mechanically (K5
+2.72, K6 +2.81, trend +8.21) while the question it exists to answer reads null. This is a
drafting defect in the prereg (mine, 2026-08-03), recorded rather than quietly reinterpreted —
the numbers stand exactly as pre-registered; only their sufficiency for *funding* is at issue.

**What the measurement supports as a ceiling argument:** the value of exact play above
production is ~+0.1 pts/deck, saturated, with no detectable winrate effect. The specialized
endgame net's ceiling is the value of the exact play it would distill, so this bounds that
lever at approximately nothing.

**OPEN — Joshua's call:** buy the amended branch-2 confirm (deploy budget 11008, fresh band,
~half a box-day) — or record the ceiling and close the endgame-exactness question.
Standing recommendation: **close it.** A confirm would be asking whether a ~0.1 pts/deck,
winrate-null effect survives a 4× budget increase, and the low-sims inflation pattern
(`feedback_sims_washout_net_eval`) predicts it shrinks rather than grows.

## 6. Caveats

- **Screen budget, not deploy budget** (SIMS=2750). Per the pre-results amendment: a NULL here
  transfers to 11008 (a weaker prefix search gives an exact tail *more* room, not less), a
  POSITIVE does not. The winrate null is therefore the transferable half; the small margin
  positive is the non-transferable half.
- **Cells are 394–400 of 400 games** (game timeouts excluded from strength stats but counted
  in censoring). Slightly under-powered vs plan; immaterial at these effect sizes.
- **The K6 pre-flight underestimated the rung's cap-hit rate ~3×** (0.038 on 9 games vs 0.129
  realised over 2,117 latch solves). Both are under the 0.20 threshold so nothing changed, but
  a 10-game rider is a weak estimator of a rate — size the rider to the decision, not to
  convenience.
- **The K≤4 incumbent tail is uncapped by design**, so every rung ends with an unbounded
  straggler tail (K2 held 30 idle workers ~45 min on two pathological games). Killing
  redundant stragglers once the record count reaches n is safe — the launcher's loop exit
  condition IS the record count — and is what let each rung advance.
