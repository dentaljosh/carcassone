# J8EX ≡ BASE — the J8 reserve-floor exemption is INERT IN PLAY (2026-08-13)

**Status: FINDING, recorded mid-tournament before adjudication. Not a wiring failure — verified.**

## The observation

Cell `J8EX` reproduced cell `BASE` **exactly**: `win_rate 0.1150`, paired margin
**−23.3333**, sem 1.0728, z −21.75 — identical to every printed digit, and a record-level diff
shows **0 of 300 games differ in margin** (300/300 common (deck_seed, seat) keys).

## It is NOT a plumbing failure — four checks

1. **The flag reached the driver**: `argv` in `cells/J8EX.jsonl.manifest.json` ends
   `--preset current --j8-break-reserve-floor`; BASE's does not.
2. **The variant resolved differently**: `current+j7w1+j8brk` vs `current+j7w1`.
3. **Every per-game record stamps the axis correctly**: 300/300 records differ in
   `joshua_axes` (`j8_break_reserve_floor: true` vs `false`).
4. **The decision code consults it**: `joshua_bot.py`'s F-J3 filter keeps candidates
   `c.closes_own or c.swings_majority or (p.j8_break_reserve_floor and c.is_pivotal_overcommit)`.

## Why it is inert — the mechanism

F-J3 is a hard filter that is **skipped when it would empty the candidate set**. So when the
bot is at/below its reserve floor and *no* closure/majority-swing exists, the filter empties
and is skipped — pivotal overcommits are **already legal without the flag**. The exemption
therefore only bites in the narrow intersection: reserve floor active **AND** at least one
closure/swing exists (so the filter survives) **AND** a pivotal overcommit outscores every
surviving closure/swing. Across 300 games vs the champion that intersection **never decided a
move**.

## ⚠️ This contradicts the build report, and the contradiction matters

The bot build reported *"`j8_overcommit` fires on 0 chosen moves per current-preset game with
the floor intact, and **8–28** with the exemption"* — which is what motivated reframing the
arm as **"J8 present vs J8 absent"** rather than a marginal tweak. That reframe was carried
into `TOURNAMENT_PREREG.md`. The reconciliation is almost certainly that **8–28 counted the
PREDICATE firing (`rule_fires`), not the CHOSEN MOVE changing** — and/or that it was measured
against `RuleBasedPlayer`, whose game shapes differ from the champion's. **Do not cite the
8–28 figure as a behavioural-change rate.**

## Consequences

- **The J8 axis contributes nothing to this tournament.** Under `TOURNAMENT_PREREG.md`'s read
  rule (an axis whose contrast is sub-2σ defaults to interview fidelity), J8 defaults to
  **exemption OFF** — here not because the contrast is noisy but because it is *exactly zero*.
- **`ALLTOG` is partially confounded**: whatever it reads, the J8 component of it is inert, so
  ALLTOG effectively measures J7ZERO+J9ON.
- **A cell that reproduces another cell bit-for-bit is a wiring gate we did not have.** The
  chain's Gate 1 verified the flag's *argparse surface*, which cannot catch an axis that is
  plumbed-but-inert. A cheap future gate: assert that any two cells differing in an axis
  produce ≥1 differing action on a shared seed, run on 1 game before the cell.
- **The J8 mechanism itself is untested by this run**, not refuted. If the intent is "you have
  to take chances on the pivotal feature" (interview J8), the encoding needs the exemption to
  reach cases where it is currently pre-empted by the skip-when-empty rule — i.e. J8 should
  arguably be a *score* term, not a filter-exemption. That is an encoding question for the
  owner, not a measured verdict.
