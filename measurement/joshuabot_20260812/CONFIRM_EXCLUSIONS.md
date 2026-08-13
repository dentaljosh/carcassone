# CONFIRM exclusions — J7ZERO, band 1.26e11 (`fixed_v1`)

**Status: FINAL for the exclusion question — the confirm leg completed
2026-08-13 09:20 (`DONE_CONFIRM`, 800/800 records). §3 carries the run's own
numbers, read off `confirm/J7ZERO_confirm.jsonl.manifest.json`. This note makes
NO verdict statement: the margin is not adjudicated here.**

Scope: the tournament CONFIRM cell of `TOURNAMENT_PREREG.md` §5 rule 4 —
`--preset current --j7-weight 0.0` (`variant_id current+j7w0`), 400 decks × 2
seats on the sealed band `1.26e11`, out
`confirm/J7ZERO_confirm.jsonl`.

This note exists because **a dropped game is an exclusion, not a non-event.** It
states which cells were dropped, why, at what rate, and the argument for why the
drop does not bias the margin — plus the conditions under which that argument
fails and the readout must say so instead.

---

## 1. The offending cells

| deck seed | joshua seat | champ seat | champion seed | status |
|---|---|---|---|---|
| `126000000135` | **0** | 1 | `9400540` | **EXCLUDED** — raises deterministically |
| `126000000135` | 1 | 0 | `9400542` | completes normally (margin −28) |

Found by replaying **all 30 cells that were in flight** when the first leg died at
269/800 (the crash killed `imap_unordered`, so the offending cell left no record).
Exactly **one of the 30** raised; the other 29 completed. Raw:
`logs/repro_crash_cells_20260813.jsonl`.

The failure is **deck-AND-SEAT specific, and reproducible**: the same cell raised
in the original run, in the 30-cell replay, and in the single-cell instrumented
replay — three times, same exception, and the *other seating of the same deck*
plays out fine. Nothing here is a race, a timeout, or a resource event.

Exception, verbatim:

```
RuntimeError: PUCT reached a node with no valid actions (Python IndexError)
  src/carcassonne_ai/rust_agent.py:657 in choose_action   (the CHAMPION's search)
  scripts/human_anchor/play_harness.py:233 in play_game
```

## 2. Mechanism — the bounded-action-window family, one node deeper

It is the **25×25 centroid action window**, i.e. the same family as
`action_space.WindowOverflowError` / the JCZ `WALL_LEGALITY` divergence class —
but it surfaces differently on the rust backend, and it fires at a *hypothetical*
node rather than at the played position.

1. `carc-core/src/action_space.rs::encode` returns `None` for a **tile placement**
   whose coordinate falls outside the window. Meeple actions and `Pass` are
   window-independent and **always** encode.
2. `carc-core/src/game.rs::legal_mask` counts those as `n_overflow` and **drops
   them silently** (Python's `game_wrapper._compute_mask` raises
   `WindowOverflowError` at exactly this condition instead). `legal_actions()`
   therefore returns an **empty** vector whenever every emitted legal action is an
   out-of-window tile placement.
3. The PUCT expansion writes that empty list into the node
   (`valid_actions = []`, `expanded = true`), and the next descent through it hits
   `search/mod.rs:516` → `SearchError::NoLegalActionsAtInterior`, whose Display
   string is the RuntimeError above.

Step 1 is what makes this a *classification*, not a guess: because `Pass` and
meeple indices always encode, an empty legal list with a non-empty engine
enumeration can **only** be all-tile-placements-outside-the-window. There is no
other route to that state.

**It is NOT a bot-produced illegal state.** Three independent facts:

- the raise comes from the **champion's own** `choose_action`, on the seat
  JoshuaBot is not playing;
- `rust_agent.check_sync` runs **unconditionally** on every decision (2026-08-01)
  and had already asserted the rust mirror is byte-identical to the python board
  at that ply — so the position the search started from is legal and agreed by
  both engine implementations;
- the identical deck under the swapped seating completes and scores.

**The played position was healthy — the wall is inside the search.** Instrumented
replay of the failing cell (`logs/window_diag_126000000135s0.json`) at the failing
ply:

| | |
|---|---|
| ply / phase | 59 / meeples |
| tiles placed / remaining | 61 / 11 |
| window (origin_row, origin_col, size) | (5, 3, 25) |
| legal actions **total / outside window** | 5 / **0** |
| placed tiles outside window | **0** |
| board extent rows / cols | 6–23 / 10–18 |

Every sampled trace point of the game (10 probes, plies 0–59) shows
`n_legal_outside_window = 0` and `n_placed_tiles_outside_window = 0`. So unlike
the `capoff` incident (DECISIONS 2026-07-31, where the *candidate's own play*
drove the real board into the wall), here the **real game never approaches the
window**; the champion's PIMC search descends into a determinized continuation
that sprawls past it. The rust mirror re-derives the window from the centroid
after every applied action (`game.rs:384`), so this is the search exploring a
legal-but-unencodable future, not a stale window.

**Consequence:** it is a search-side defect that costs a whole game, and it is
logged for the F9 / recentring dossier — the same invisible-border programme the
capoff post-mortem fed. It is *not* fixed here; it is *recorded* here.

## 3. Realized rate

**FINAL — the completed leg, straight off `summary` in
`confirm/J7ZERO_confirm.jsonl.manifest.json`:**

| quantity | value |
|---|---|
| `n_records` (cells attempted) | **800** |
| `n_scored` | **799** |
| `n_failed` | **1** |
| `failure_rate` | **0.00125 = 0.125 %** |
| `failed_by_seat` | seat 0: **1** · seat 1: **0** |
| `n_paired_decks` | **399** of 400 (deck `126000000135` contributes **0**, not 1) |

So the confirm is **n = 399 paired decks / 799 scored games, not 400 / 800**, and
that is the n any readout must quote.

House reference figures for the same family: **0.5 %** of games
(`WALL_LEGALITY` ×2 / 400, JCZ match 2026-08-09) and the original design contract
"revisit if the rate exceeds **0.5 %** in real self-play data" (DECISIONS
2026-04-28, line 2654). **0.125 % is 4× below both** — the trigger in §5 did not
fire on rate.

Neither pre-stated failure condition fired, but read §5 for what "did not fire"
is and is not worth: 1 event on seat 0 is **not** evidence of seat-neutrality,
only the absence of evidence against it.

The guard is **confirmed live in production, not just in tests**: on the resumed
leg the same cell came up at `[11/531]`, printed
`⚠️ FAILED CELL deck=126000000135 joshua_seat=0 RuntimeError: PUCT reached a node
with no valid actions`, landed its `failed: true` record in the JSONL, and the
pool ran on to 531/531. The leg that crashed had cost 531 games and left zero
trace of the offending cell; this one cost one deck and named it.

## 4. Why the exclusion is outcome-INDEPENDENT

The claim being defended is: dropping these cells does not shift the paired
margin toward either player.

1. **The game cannot be completed by EITHER side.** The raise happens inside the
   champion's search *before a move is returned*; there is no legal continuation
   for the harness to record for anybody. It is not a resignation, a timeout, an
   adjudication, or a forfeit — nothing is scored, so nothing is scored in
   anyone's favour.
2. **It is not conditioned on who is winning.** The trigger is a property of the
   *action encoding* of a hypothetical continuation (a coordinate outside a
   25×25 box), which carries no information about the score. No branch of the
   code reads the score, the margin, or the seat's standing.
3. **The excluded set is fixed before the game is observed.** Both players are
   deterministic (JoshuaBot by construction; the champion by
   `champion_seed(deck, seat)`), so the exclusion set is a deterministic function
   of `(deck_seed, joshua_seat)` — decided by the seeds, not by the realized
   result. Re-running the cell re-produces the same exclusion, never a different
   outcome.
4. **The paired statistic degrades gracefully and conservatively.** A deck with
   one dead seating is dropped from the paired margin ENTIRELY
   (`summarize` requires both seatings), so no half-deck — which *would* be
   seat-biased — can leak in. The cost is n, not bias.

## 5. Where that argument would fail — pre-stated, so it cannot be waved through

Two conditions, both to be checked against the final manifest and **reported in
the readout rather than passed over**:

- **Rate materially above the ~0.5 % house figure.** More than ~4 failed cells in
  800 means this is no longer a rare edge and the confirm's n must be quoted with
  the exclusion attached (the capoff precedent quotes n=384, not 400, with an
  adversarial worst-case bound in the same sentence).
- **Correlation with seat.** The exclusion is only outcome-neutral because the
  *pair* is dropped. A skew toward one seat means the losses concentrate in decks
  that were going to be scored from one side, and the deck-pairing defence
  weakens. With a single event (seat 0) there is **no power to test this** — that
  is a caveat, not a clean bill.

Two further honest disclosures, neither of which supports a conclusion at n=1:

- **Candidate-correlation is not excluded.** The trajectory that walks the search
  into the wall is produced by *this* pair of players, so a different variant on
  the same deck might not hit it. This exclusion is therefore **not exchangeable
  across variants** — it is a fact about the J7ZERO cell, and a sibling cell's
  n is not automatically comparable minus the same deck. (This is the exact shape
  of the capoff finding.)
- **The score at the moment of the raise was `[40, 54]`** — Joshua (seat 0) 14
  behind, ply 59, 11 tiles left. One observation says nothing about whether
  exclusions favour a side; it is recorded because the honest way to handle a
  single unfalsifiable data point is to publish it, not to omit it. If the final
  count stays at 1, this line is anecdote; if it grows, it is the first thing to
  re-examine.

## 6. What changed in the driver (so this is the last time it costs 531 games)

`scripts/joshuabot/h2h.py`: a cell that raises is caught, written to the same
JSONL as a `failed: true` record (seed, seat, champion seed, variant, exception
type + text + traceback) and the pool **continues**. `summarize` reports
`n_failed` / `failure_rate` / `failed_by_seat` / `failed_cells`; the driver prints
a `⚠️ FAILED CELL` line live and an exclusion banner at the end; the manifest
carries `summary.n_failed` and `n_failed_this_leg`. A failed cell counts as done
on `--resume` (these failures are deterministic — retrying just re-burns a
game-time); `--retry-failed` re-opens them after a code fix. Covered by 14 tests
in `tests/test_joshuabot_h2h.py`, including a real spawn-pool run that survives a
stub cell exploding mid-pool.

The house lesson this implements: **a game that dies deterministically and leaves
zero records is the dangerous pattern**, because the loss is invisible and can be
candidate-correlated (DECISIONS 2026-07-31, capoff).
