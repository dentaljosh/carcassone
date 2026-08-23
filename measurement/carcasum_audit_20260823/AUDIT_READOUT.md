# Carcasum divergence audit — **PASS**, 50/50, zero REAL divergences

> **Status: COMPLETE 2026-08-23. VERDICT: the two engines are rules-identical on this
> corpus.** 50 games, exact final-score agreement 50/50, exact farm agreement 50/50, farms
> scored in 50/50 games, zero REAL divergences, zero voids, 50/50 replay.
>
> This discharges gate 5 of [`AUDIT_PLAN.md`](../carcasum_match_prep/AUDIT_PLAN.md) and
> unblocks the blind commit of
> [`PREREG_DRAFT.md`](../carcasum_match_prep/PREREG_DRAFT.md) — **not** the rated match
> itself, which is the orchestrator's to fire.
>
> Archive: `audit.jsonl` · harness [`scripts/carcasum_match/`](../../scripts/carcasum_match/) ·
> driver `vendor/carcasum/build-driver/carcasum_driver` (upstream `5f5e365`, patches
> R1/B1–B8) · **dev-tier seeds `5100000..5100024`, deliberately NOT a registry band.**

---

## 1. The numbers

```
records                   50   (25 decks x 2 seats, tier1-greedy vs their MCTS @50ms)
voids                     {}                       none
REAL divergence classes   {}                       <- the bar
final score agreement     50/50                    exact, both seats, every game
replay_ok                 50/50
farm points ours==theirs  50/50                    exact
farms EXERCISED           50/50 = 100%             (check 3 wants >80%)
classified, non-REAL      UNPLACEABLE_REDRAW 4     expected under fixed_v1 A3
                          ENDGAME_TERRAIN_MISMATCH 7  telemetry only -- see 3
```

**Cheap on purpose.** The audit measures *rules coverage, not strength*: a greedy
champion and a 50 ms opponent scatter meeples and leave features open, where strong play
converges on a narrow, well-behaved slice of the state space. The whole corpus ran in
**30 seconds**, which is what makes "fix a divergence and re-audit in the same sitting"
possible.

## 2. What each check bought

| # | check | result |
|---|---|---|
| 1 | final totals | **50/50 exact.** Their `Game::getScores()` vs our `board.state.scores`. |
| 2 | per-ply totals | no `SCORE_FINAL`, no `SCORE_TIMING` — the totals never parted mid-game either. |
| 2a | **farms, computed independently** | **50/50 exact.** Ours from `aux_targets.extract_terminal_ownership` (a recording replica of `count_final_scores`), theirs from `score_detail["field"]`. This is the check that licenses the word *farms*, and it is a real farm-vs-farm number rather than an inference from agreeing totals. |
| 3 | farms exercised | **50/50 = 100 %**, far above the 80 % floor. A farm-free corpus would have certified nothing, and farms are where the R9-class bugs live. |
| 4 | legality | zero `VOID_UNMAPPABLE`, zero `LEGALITY_OURS_EXTRA`. Every Carcasum move inverted onto exactly one of our legal actions. |
| 5 | unplaceable redraw | exercised **4 times**, agreeing, classified non-REAL. (The plan warned this could not be left to volume — at the measured 1.4/100 rate, n=50 fires only ~50 % of the time. It happened to fire here; the *constructed* case remains the standing requirement.) |
| 6 | tiny-city patch | **PASS, proven separately and positively** on a constructed 2-tile city — scores **4**, not 2 — in `tests/test_carcasum_rules_patch.py`. Not inferred from the source diff. |
| 7 | board bounds | zero `WALL_LEGALITY`. Their board is 145×145 with offset 72, so *their* side cannot wall-escape; the constraint is only ours (`centered18`). |
| 8 | replay | **50/50.** |

## 3. The one class that fired, and why it is NOT a rules finding

`ENDGAME_TERRAIN_MISMATCH` fired on 8/50 in the **first** audit pass and was **demoted out
of `REAL`** before this one. That demotion is a measurement, not a judgement call:

* Diffed against the **terminating** ply's `ev_move`, the delta is **exactly zero on every
  terrain** — `game_over.score_detail` and the last `ev_move.score_detail` are identical,
  because Carcasum runs `endGame()` *inside* the terminating `Game::step()`, so the last
  `ev_move` already contains the endgame sweep. Verified directly on deck 5100013.
* Diffed against the ply **before** it (what the code did), the delta additionally carries
  that ply's **mid-game closures**, so it over-reports — which is exactly the direction
  observed: theirs ≥ ours on 8/8, never the reverse.

**There is no ply at which that difference is the endgame-only quantity**, so the class was
firing on a bookkeeping-alignment artefact. The corroboration is that those same 8 games had
*exact* final-score agreement and *exact* farm agreement. Leaving it in `REAL` would have
voided ~16 % of games for a non-rules reason, corrupted the rated match's void accounting,
and — worst — been reported as *"the engines disagree on the rules"*.

`FARM_SCORE_FINAL` stays `REAL` and is sound by construction: fields never score mid-game in
either engine, so their **absolute** `score_detail["field"]` at `game_over` *is* the
endgame-only field figure — no differencing, nothing to contaminate.

**To recover a full per-terrain endgame check**, the driver would need to publish a
`score_detail` snapshot taken after the terminating ply's mid-game closures but before
`endGame()` (a `pre_endgame` field on `game_over` — a small change at the `simEndGame()`
boundary). Recorded as the route; **not needed for the rated match**, because
`FARM_SCORE_FINAL` already covers the terrain that matters.

## 4. Two harness bugs this audit caught, both of which would have faked a rules result

Worth recording because both had the same signature — *a plumbing fault wearing the costume
of a rules disagreement*:

1. **`selectors` on a buffered text stream.** `readline()` on a `TextIOWrapper` pulls a large
   chunk off the fd into userspace, swallowing the next protocol line; the following
   `select()` asks the *kernel*, which says "nothing to read". Every game voided as
   `VOID_ERROR: no protocol line within Ns` with an **empty stderr tail** — indistinguishable
   at a glance from a hung opponent search.
2. **Rotational symmetry.** Carcasum enumerates only physically distinct placements; our
   action space enumerates all four rotations. Chapel/full-city/crossroads have period 1 and
   the four `FCFC`/`FRFR` tiles period 2, so our forward-mapped orientation was simply never
   in their offered set for those tiles. Fixed by deriving each tile's period from the
   driver's own `--dump-tiles` (edges **and** node partition) and reducing mod period.

Together with the 145-vs-72 board-geometry error corrected earlier, that is **three**
distinct ways a coordinate/encoding bug could have been read as "the engines disagree". Hence
the harness's standing rule: the origin comes from the handshake, never a constant; a ply-0
mapping failure is a **distinct** diagnostic class, not an ordinary `VOID_UNMAPPABLE`.

## 5. What this audit does NOT establish

- **Nothing about strength.** The win rate in the archive (0.64 for greedy-vs-50 ms) is an
  artefact of a deliberately cheap pairing and must not be quoted anywhere.
- **Nothing about timing.** These games ran *alongside a live 22-worker D2 eval* on a box at
  loadavg ~23. Correctness verdicts are insensitive to load; the `ms/move` figures in
  `audit.jsonl` are **not** and must not be used. Gate 6's timing smoke is deferred to an
  exclusive box (§6).
- **Coverage is 50 games of cheap play.** It exercises farms heavily and redraw lightly. It
  does not exercise deep-endgame or meeple-contested states at champion strength.
