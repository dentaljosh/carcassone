# E1 win-objective exact-K pre-gate — READOUT

> **⚠️ STATUS 2026-08-14 — COMPLETE. 0 GAMES PLAYED. PRE-REGISTERED BRANCH `K`
> FIRED (dies free — the deploy cell is NOT owed): divergence 0 / 1,858 solved
> plies, CI95 upper 0.161%.** The [DESIGN §2 proposition](DESIGN.md) predicted
> exactly 0 and the corpus confirmed it — at the deployed `exact_max_k = 2`
> every chance bag is a singleton, so the WIN objective and the MARGIN
> objective provably pick identical moves at every ply the champion actually
> hands to the solver. No `experiments/results.csv` row, no band claim, no
> claim id; `governance/PRODUCTION.yaml` untouched (0-game precedent: F6,
> j13, farm-war). Read-rule committed before any number (`d85cbd40`), then
> the instrument, then this read-out. Machine numbers:
> [VERDICT.json](VERDICT.json).
>
> **The build stays merged, flag-gated default-off** (`exact_objective`,
> solver-side, leaf hash untouched): the objective is now *testable and
> priced* — and it is cost-neutral (solve-time ratio ~1.00) — but nothing
> routes to it in production.

## What was asked (roadmap Track E, E1)

"Win-probability endgame objective + pre-registered exact-K winrate re-run" —
switch the exact-K solver from maximizing the final-score MARGIN
(`E[score diff]`, established at the code level by the F6 pre-gate:
`rust/carc/carc-core/src/{endgame,fair/solver}`) to maximizing WIN, and price
it. The mechanism argued for it: with 2 tiles left and a lead, margin-max
could prefer a risky E[+5] over a guaranteed +1 hold, where "risk" is risk
over the deck marginalization. The exact-K values feed final move selection
directly, so the objective changes picks wherever win-optimal ≠
margin-optimal.

## The structural answer (DESIGN §2, now empirically confirmed)

**At `exact_max_k = 2` the mechanism cannot occur.** The latch fires with at
most one undrawn tile beyond the tile in hand, so every chance node in the
solve has a **singleton bag** — the marginalized solve is a deterministic
minimax, outcome is a monotone transform of its deterministic integral
margin, and the two objectives coincide exactly (same optimal sets, same
`min(optimal)` pick). Divergence requires a chance bag ≥ 2 ⇒ `k_remaining ≥ 3`
⇒ a **depth** change — and depth is closed (CL-076/F13; marginalized K≥5
separately impractical, MARG_FRONTIER 2026-08-04). This corrects F6 DESIGN
§0's aside that the corner is "real, bounded to K≤2": the corner is real only
at K ≥ 3.

## Integrity + the numbers

| check | result |
|---|---|
| self-play games replayed | **449/449** bit-exact final scores |
| E4 archives replayed | **31/31** bit-exact (29 `fixed_v1`, 2 `walled`; profile resolved from the archive stamp, unstamped archives resolved **by replay** — see below) |
| exact-K-solved plies graded | **1,858** (simulated deployed latch; champion seats only on E4) |
| budget-exceeded plies | 0 |
| **divergence (pick ≠ pick)** | **0 / 1,858 = 0.0%**, CI95 upper **0.161%** |
| optimal-SET divergence | 0 / 1,858 |
| archived action == margin pick | **1.0** (every archived champion action at a solved ply reproduces the margin solver's pick — replay + solver + engine all agree) |
| liveness discriminator | asserted per solve: margin payload `win_value=None`, win payload present |
| cost | 258 s wall at W8, 0 games |

**Read-rule branch `K`** (`< 1%`): bounded-tiny — **the honest kill; the
n=800 deploy cell is NOT owed** ([DEPLOY_PREREG_DRAFT.md](DEPLOY_PREREG_DRAFT.md)
stays a draft, never promoted). The §4 guard ("a nonzero rate falsifies the
proposition and must be root-caused") did not trigger: the empirical zero and
the theorem agree.

## Cost bench (the build's obligation)

Both objectives solved per ply, interleaved on the same position in the same
process (RUST production solver, the deployed engine):

* solve-time ratio win/margin: **total 1.0041, median 0.988, p90 1.180**
* absolute: margin median 21.9 ms / p90 1.48 s; win median 21.3 ms / p90 1.50 s

⚠️ Measured on a SHARED box (another agent's W6 run + the control scan were
live — census noted). The **ratio** is the deliverable and is
contention-robust (arms interleaved per position); absolute times are
indicative only. Read: the win objective is **cost-neutral at K=2** (same
tree, pair payload; the marginalized mode has no alpha-beta to lose in either
objective). The DEPLOY_PREREG's ms_ratio 1.20 trigger would not have fired.

## The positive control (liveness; K=3 by necessity)

By the proposition, no K≤2 control can exist, so the flag's liveness proof is
a **K=3** position (the smallest K with a real chance mix — the control's
construction depth only; nothing here proposes K=3 play). The bounded scan of
the 449-game self-play bank (≤1 K=3 TILES ply per game, closeness prefilter
|leaf| ≤ 12, 4M-node budget per solve, early-stop at 4 hits) found real-game
positions where the objectives provably disagree, e.g. deck_seed
**28000000186** ply 138: the win pick buys **+0.50 P(win)** while the margin
pick buys **+7.0 E[margin]** — the exact "guaranteed hold vs risky margin"
gamble the mechanism describes, in a real champion game.
`raw/divergence_controls.json` pins them;
`tests/test_e1_win_objective.py::test_positive_control_objectives_disagree`
recomputes both modes and asserts the disagreement (surface-B
inverted-liveness convention — the leaf hash does not move on this knob).

## What this does NOT say (read before quoting)

1. Nothing about K ≥ 3 play — that is depth, and depth is closed (CL-076/F13).
   The K=3 divergences above are liveness artifacts, not a lever measurement.
2. Nothing about win-prob conditioning ABOVE the latch — F6 killed forms
   (a)/(b) free, and this instrument does not touch them.
3. The E4 corpus contributes plies where the CHAMPION was to move; human
   plies are not solver plies and were not graded.
4. `archived_matches_margin_rate = 1.0` is an integrity statistic
   (replay/solver/engine coherence), not a strength claim.

## Re-open bar

A production `exact_max_k ≥ 3` (a depth change — currently closed by
CL-076/F13 and the marginalized cost frontier) would make the objective
question live again, and the flag-gated build + this instrument are ready for
it; OR an engine change that introduces a chance bag ≥ 2 within the K≤2 latch
(none known — the redraw path was checked).
