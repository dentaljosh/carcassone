# Carcasum divergence audit — the gate before any strength number

> **Status: current.** This is gate 5 of the Carcasum harness build. It runs *before*
> [`PREREG_DRAFT.md`](PREREG_DRAFT.md) may be blind-committed, and it is the reason a later win
> rate cannot quietly be a rules artefact.

## The bar, stated as a precedent

The JCZ oracle set it and the JCZ match met it: **0 REAL divergences, final scores agree
N/N** ([`measurement/jcz_match_20260809/CONFIRM_READOUT.md`](../jcz_match_20260809/CONFIRM_READOUT.md)
— 400/400 across 56,777 plies). Anything less is not a smaller pass, it is a fail.

## Why cheap games

The audit measures **rules coverage, not strength**. So: their AI at a *low* budget against our
`tier1-greedy` (or `random`), ~50 games, via `match.py --audit-mode`. Cheap play is not a
weakness here — it is the point. Two reasons it is actually *better* than strong play for this
purpose:

- **Coverage.** Weak/greedy players scatter meeples and leave features open; strong players
  converge on a narrow, well-behaved slice of the state space. The audit wants the messy slice.
- **Volume per unit time.** 5 s/move × 71 plies × 50 games is ~5 hours; a low-budget audit is
  minutes, so a failure can be fixed and re-audited the same sitting.

## What must be true

| # | check | pass condition |
|---|---|---|
| 1 | **Final score agreement** | N/N exact, both seats, every game. Their `Game::getScores()` vs our `board.state.scores`. |
| 2 | **Per-ply total agreement** | Their `Game::getScores()` vs our `board.state.scores` after **every ply**, not just at the end — that is what localises a divergence to the ply where it first appears. ⚠️ **A symmetric per-terrain diff is NOT available**: our engine tracks only a flat `game_state.scores[player]` and has no field/city/road/cloister breakdown, and instrumenting shared `engine/` code for an audit is not on the table. Their `score_detail` is recorded verbatim as telemetry; checks 2a/2b below recover the part that matters without it. |
| 2a | **Full per-terrain ENDGAME decomposition, both sides** | `src/carcassonne_ai/aux_targets.py::extract_terminal_ownership` is a *recording replica* of `PointsCollector.count_final_scores` whose attributed points sum to the engine's end-of-game additions **by construction**, already validated against farm-heavy endgames by `scripts/validate_aux_targets.py`. Summing its records by terrain gives OUR city/road/farm/monastery endgame vector, diffed against their `score_detail`. **This is the check that licenses the word *farms*** — a real farm-vs-farm number, not an inference from agreeing totals. ⚠️ It needs a terminal state with meeples **still placed**; by the time `get_game_ended` is true the engine has already consumed them, so the harness follows the established stub-`count_final_scores` technique in `src/carcassonne_ai/selfplay.py`. Mid-game per-terrain remains unavailable on our side; per-ply totals + a full endgame decomposition is the achievable shape. |
| 2b | **Endgame-delta agreement** | `final_total − total_at_last_midgame_ply`, both sides. Covers incomplete cities + roads + cloisters + farms in aggregate and cross-checks 2a. Together, 2 + 2a + 2b close the "a farm error exactly cancelled by a city error" hole that a totals-only check would leave open. |
| 3 | **Farms exercised** | Farm points non-zero for at least one seat in **> 80 %** of audit games, read straight off the `farm_points` field the harness records per game. A farm-free corpus certifies nothing about farm scoring — and farms are where the R9-class bugs live (a single half-edge convention produced 66 farm-partition divergences before the JCZ audit). |
| 4 | **Legality agreement** | Every Carcasum move inverts onto exactly one of our legal actions (modulo the documented meeple-slot multiplicity). Zero `VOID_UNMAPPABLE`. |
| 5 | **Unplaceable-tile redraw** | Agreeing wherever it occurs: Carcasum discards and the SAME player keeps the turn (`Game::step()` does **not** call `setNextPlayer()` on that branch), which is exactly `fixed_v1`'s `draw_rule="redraw"`. Class `UNPLACEABLE_TURN_LOSS` on mismatch. ⚠️ **Do not write this as "≥ 1 occurrence" and call it covered by volume.** A3's own gate measured the redraw rate at **1.4 per 100 games under the `retail` start rule** (7.8/100 under the engine start rule) — an unplaceable tile is almost purely a first-move event. At n=50 the expected count is ~0.7 and P(at least one) ≈ 50 %, so a clean audit that never exercised it proves nothing. **Construct the case** rather than fishing for it: hand-build a deck order whose first draw is unplaceable and replay it through both engines. |
| 6 | **Tiny-city patch is live** | At least one plain 2-tile city completes in the corpus and scores **4**, not 2. If the corpus contains none, construct one — this is the one divergence we *know* exists and it must be positively observed as fixed, not assumed from a diff. |
| 7 | **Board bounds** | No Carcasum placement outside our 25×25 action window. Their board is 72×72 with offset 36; ours is 35×35. A wall escape is `WALL_LEGALITY` and must be counted (the JCZ match saw 2 and they were benign — count, don't ignore). |
| 8 | **Replay** | Their `history` fed back through their own `Game::newGame(..., history)` reproduces the game; our action list replays through our engine (`replay_actions`). Both must be 100 %. |

## Divergence taxonomy

Imported from `scripts/jcz_oracle/replay_diff.py`, **not redefined**. `REAL` is REAL; a class
that is cosmetic for JCZ is cosmetic here only if the same argument holds, and the burden is on
the person claiming it.

## Outcome

- **Clean** → record the counts, note which classes fired and why they are benign, and unblock
  the prereg's blind commit.
- **Divergent** → document first, patch only what rules agreement requires, never touch their
  search/AI code, re-run. Every patch lands in `vendor/carcasum/CARCASUM_PATCHES.md` and is
  echoed by the driver's `ready` line into every manifest.
- **Irreconcilable** → say so loudly and stop. An unfixable divergence does not become
  acceptable by being small; it becomes a stated limit on what the cell can claim, and if it
  touches scoring at all, the cell does not run.

## Band hygiene

Audit games use **dev-tier seeds**, never band 1.41e11. They are looked at, iterated on, and
re-run — which is exactly what disqualifies a band from confirmatory use.
