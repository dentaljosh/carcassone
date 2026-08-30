# AMENDMENTS — fpu_resurrection round

## FPU-A1 (2026-08-30, ~11:50 EDT) — G-N/G-DECKS implemented stricter than their frozen prose; FPU04 amended U-VOID → F-UNRESOLVED

**The contradiction, ground-truthed (both texts frozen pre-outcome in READ_RULE.md §4):**
- G-N's condition column demands `n == 800, n_failed == 0`; its notes column says *"a failure
  rate strictly below 2% is REPORTED, never silently absorbed (the b32v64 0.100% rust-panic
  precedent); at or above it the cell voids."* Realized: 1/800 = 0.125% — below the void bar
  the prose sets.
- G-DECKS voided on `n_common 399 != frozen 400`; the frozen G-N row's own common-deck bar is
  `n_common >= 80% of 400` (= 320). 399 passes it.
The adjudicator took the strict columns; the prose (which carries the b32v64 precedent — the
reasoned rule) is the law of the pair. This is the PG-A1/IS-A1 execution-layer class.

**The failure is deterministic, evidenced:** seed 156000000329 seat 0 raised
`WindowTruncationError` ("PUCT reached a node with no valid actions") on the original pass AND
on a clean single-game resume at the same pin (two byte-identical failure records,
`failed/seed156000000329_a0*.json`). A seeded game cannot be re-rolled; the deck drops from the
paired margin as the emitter itself states ("EXCLUSIONS, not zeros").

**Disclosure:** this amendment is written with the cell's statistics VISIBLE (the frozen
adjudicator printed them beside the void). It is defensible anyway because the amended branch
is forced by frozen arithmetic on frozen data — no judgment enters: M = +0.754, se 0.715,
UB95 = 2.185 > BAR_M 1.381, M positive ⇒ **F-UNRESOLVED** (the only branch consistent with
§4's ladder). It could not have produced F-RESURRECT (LB95 −0.676) or F-REKILL (UB95 > bar)
under any reading. Per the READ_RULE §8 caveat (added pre-launch), F-UNRESOLVED discharges
nothing.

**Amended round read:** FPU02 F-RESURRECT (untouched) · FPU04 **F-UNRESOLVED (amended, n=799
games / 399 common decks)** · CPUCT10 F-REKILL (untouched, τ not fired). The frozen U-VOID
readout is retained in the adjudication JSON of record.

**Owed:** the adjudicator's G-N/G-DECKS conditions brought to the prose for any future round
(NOT retro-edited for this one); the WindowTruncationError dead-node seed logged as a
known-rare engine edge (1/2400 this round) — chores queue, low priority.
