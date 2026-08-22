# G-FAILED clause-3 ESCALATION — held for the owner (2026-08-22, ~02:45 EDT)

**The run is COMPLETE (6,000/6,000 games, both cells, both boxes DONE, sentinels
cleared) and the adjudicator HALTED BEFORE ADJUDICATION, exactly as the frozen
pair requires: 3 failed games whose class is NOT the known `WindowTruncationError`.**
No branch, no bar, no statistic moves on this — it decides only whether the run
pauses ([HALT_B32V64.json](verdicts/HALT_B32V64.json)). The orchestrator **cannot
honestly give** the `--failures-confirmed-*` confirmation (its required text asserts
the WindowTruncationError class, which is false here), so per RULING 3 the pause
holds until the owner rules. **Nothing decays while it holds** — all artifacts are
frozen on disk.

## The three failures, verbatim surface

All three: `exc_type: PanicException`, `exc: "IndexError: board row index 35 out of
range (len 35)"`, `window_truncation: false`, `attempts: 1`, `permanent: false`.
Seeds `140000001096` (a_seat 1) · `140000001115` (a_seat 0) · `140000001286`
(a_seat 0) — **one seating each; the sibling seating of each deck succeeded.**
All in **CELL_B32** (B64: 0 failures). Rates: B32 3/3,000 = **0.10%** vs the 2%
clause-1 bar (clears 20×); clause-2 candidate-correlation did **not** fire
(max 3 < 5). A 3-vs-0 split at these counts is p ≈ 0.09 under equal rates —
suggestive, not conviction.

## What this class almost certainly is

The **parked banked-fixture replay panic family** (roadmap parking lot, proven
PRE-EXISTING 2026-08-17, triage unfunded): `carc-core/src/engine/mod.rs:411`
index-out-of-bounds on the 35×35 board (`len 1225` = 35², here surfacing as
`board row index 35 out of range (len 35)`) — a rust engine board-bounds panic at
the grid edge, now observed at ~0.1% in live B=32 games rather than only in
fixture replay. This is a **triage lead the parked bug did not have before**:
three reproducible seeds at production knobs.

## The owner's options at havdalah (one word each)

1. **"confirmed"** — rule the class acceptable for THIS read-out (rate 20× under
   bar, single-seating, deck-pair-dropped whole; the statistics are unaffected
   either way). I re-run the adjudicator with your confirmation recorded verbatim,
   the branch fires mechanically, close-out proceeds. The panic itself goes to the
   parked bug row with its three new repro seeds.
2. **"hold"** — the read-out stays un-adjudicated until the panic is triaged.
   Costs: the verdict (and any swap/128 decision) waits behind an unfunded bug.
3. Anything else you rule — the confirmation text is recorded verbatim and gates
   escalation only.

**Recommendation: option 1.** The failure policy already handles these games
identically under every branch, the rate is far under the committed bar, and the
class — while not WindowTruncationError — is a known, pre-existing, pre-registered-
as-parked engine bug, not an arbiter or instrument defect (`tiearb_errors_total: 0`
in both cells). The three seeds make the parked triage strictly easier, whenever
it gets funded.
