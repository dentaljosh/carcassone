# Reading guide — for an ML-literate outsider

*Written 2026-08-25 for a first-time reader with an ML background (you know what MCTS, AlphaZero,
and a value/policy net are). The repo is large because it is a lab notebook, not a library; this
page tells you where the signal is.*

## What this is
An attempt at superhuman 2-player Carcassonne (base + farmers), run since May 2026 by one
non-programmer owner directing Claude. The current champion is **classical**: PIMC/PUCT search
(k=8 determinizations × 1376 sims) over a hand-crafted evaluation ("the leaf"), an exact endgame
solver for the last plies, and — since August — a rollout **tie-arbiter** that settles the leaf's
exact value-ties by simulating to game end. There is deliberately no neural net in the champion;
the story of *why* is the most interesting thing here.

## The five documents that matter, in order
1. **[docs/LEVER_INDEX.md](LEVER_INDEX.md)** — every intervention ever tried, killed, or declined,
   one row each, with evidence pointers. This is the map. Grep it before wondering "did they try X".
2. **[governance/PRODUCTION.yaml](../governance/PRODUCTION.yaml)** — the champion of record and its
   exact config. Prose never carries these facts; this file does.
3. **[measurement/e4_exploit_grading_20260825/](../measurement/e4_exploit_grading_20260825/)** —
   the freshest arc (read STAGE_A_CENSUS.md → COMPOSITION.md → STAGE_B_VERDICT.md, with
   [the pre-registered hypotheses](../measurement/e4_owner_exploit_hypotheses_20260825.md) first).
   The owner beats his own champion 80% over the last 15 phone games; these instruments measure
   *how*, and converge on a structural blind spot (below).
4. **[DECISIONS.md](../DECISIONS.md)** — 386KB append-only decision log. Grep by date; never read whole.
5. **[experiments/results.csv](../experiments/results.csv)** — source of truth for every number.

## The headline findings (each with a measured record behind it)
- **The learned-value route is closed here, mechanistically** (claims CL-039/042/064/065/066/073):
  value heads learn to *predict outcomes better than the hand leaf while ranking sibling moves ~30×
  worse*. Prediction ≠ discrimination. The freshest instance is live vs a human: the champion grades
  its own play 4.3× better than the opponent beating it by 13 pts/game (p≈2e-20), while playing the
  solver-verified endgame *perfectly*.
- **The policy half of AZ transferred; the value half died** — distilled search-visit priors were
  worth +35.7 elo at equal sims (CL-067); iterating the flywheel produced zero growth (frozen value
  = fixed point; CL-072 refuted the growth premise).
- **The tie-arbiter is real, transferable strength**: +1.7 pts/game internally, and the transfer
  challenge (2026-08-25, `carcasum-arb-freeze` branch) read **T-TRANSFER**: +69 elo against an
  external engine, z=4.49 — champion+arbiter is +134 elo over the strongest published bot we found.
- **The structural blind spot** (2026-08-25, the E4 arc): the vendored full-points-on-tie rule means
  a meeple *invasion* costs the victim nothing direct — so self-play never generates the punishment,
  the leaf never prices it, search demotes the invasion plan's first move, and a human found and
  farms the gap (deliberate invasions 90-vs-7; 46% of the champion's farmers score zero). A
  "contested-feature risk" leaf term is the queued fix.
- **Compute is nearly mined out on-lineage**: the budget ladder pays ~17 elo/doubling at the top and
  the headroom-above-production bound is ≈+7 elo [−35,+49] (a re-test is mid-adjudication).

## House conventions you'll hit
- **Blind pre-registration**: experiments freeze DESIGN.md + READ_RULE.md (branch tables,
  first-match-wins) on a `*-freeze` branch *before* any game runs; adjudicators are written from the
  read-rule text alone. Deviations get numbered entries, never silent fixes.
- **Bands** = pre-claimed deck-seed ranges (governance/BAND_REGISTRY.csv), single-use once they
  influence a decision. **CRN/deck-pairing** = same decks both arms/colors (halves variance).
- **The E4 corpus** = owner-vs-champion phone games, auto-archived, replayable bit-exact from
  (deck_seed, action_log).
- Numbers in prose are pointers; `results.csv` and per-run `manifest.json` are authoritative.

## Honest status (2026-08-25)
Strongest measured machine player in its niche; **not superhuman** — the owner himself currently
beats it at phone conditions, which the instruments above turned from an embarrassment into the
program's best lead. Questions welcome: the lab notebook answers most "why didn't you just…"
questions in LEVER_INDEX, usually with a corpse attached.
