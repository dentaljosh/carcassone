# DEVIATIONS — HP-M1 field-fate kill gate

Prereg frozen 2026-08-30 (`PREREG.md`). Every entry states whether any statistic
of the hypothesis had been read at the time. Per PREREG §9, a deviation made
*after* a bar statistic has been read VOIDS that bar rather than re-reading it.

---

### D1 — solver pinned (pre-freeze, no statistic read)

**When:** during the freeze, before any row was extracted.
**What:** the environment has no `sklearn` and no `scipy` (numpy only, verified).
PREREG §4.2 originally said `max_iter = 2000` in sklearn's vocabulary; it now
pins a ridge-penalised IRLS solver explicitly (λ = 1/C = 1.0, intercept
unpenalised, ≤100 Newton steps, `max|Δβ| < 1e-8`, loud failure on
non-convergence). Deterministic, so the fold-CV numbers are reproducible
bit-for-bit.
**Statistic read at the time:** none. This is part of the freeze, not a
deviation from it.

---

### D2 — the bag's self-validating gate, corrected to the measured draw timing

**When:** during the build smoke test (2 games), before any bar statistic.
**Statistic read at the time:** NONE of the hypothesis. Only the wiring
quantity `bag_n` vs `len(state.deck)`.

**What happened.** PREREG §3.1 defines the bag board-derived (public knowledge,
no deck order, no `next_tile` peek). The first implementation asserted
`bag_n == len(state.deck)` at the claim ply, reasoning from
`flat_leaf._bag_stats`' docstring ("StateUpdater only pops the next draw at turn
end"). The smoke run reported that gate FAILING on every row, so it was measured
directly rather than argued about:

```
after action i   phase     board  deck  bag   FULL-board
 0               meeples     2      70   70       70
 1               tiles       2      69   70       70
 2               meeples     3      69   69       69
 3               tiles       3      68   69       69
```

The wrapper draws the next tile at the **end of the meeple action**, so at the
post-claim state (which is the state the features are computed on, and which is
a TILES-phase state) exactly one tile is **drawn but unplaced**:
`bag_n == len(deck) + 1`. The docstring describes the engine's `StateUpdater`,
not `game_wrapper.Game`'s turn transition.

**Why the FEATURE is unchanged and correct.** The tile in question is drawn
*after* the actor committed the meeple. Counting it as unknown is precisely the
decision-time knowledge state the prereg specifies, so no feature value moves.

**What changed.** Only the gate. It is now two independent checks:
1. `bag_n == FULL_total − #tiles on board` — this is the one that matters, and
   it catches the real failure mode: `Counter.__sub__` silently DROPS
   non-positive entries, so a board tile outside `FULL` would shrink the bag
   with no error anywhere;
2. `bag_n − len(state.deck) ∈ {0, 1}` — the engine cross-check, now stated at
   the measured draw timing instead of an assumed one.

`bag_minus_deck` is emitted on every row and asserted in
`tests/test_hpm1_fieldfate.py`, so if the engine's draw timing ever moves, the
test says so rather than the gate quietly passing.

**Also corrected in the same pass:** `FULL` is derived from the game itself
(board + deck + in-hand at ply 0) rather than from `base_tile_counts`. Measured
total is **72** under `fixed_v1`, i.e. the start tile *is* part of the 72 on this
path — which is exactly why the multiset is read from the game rather than
assumed from the tile-count table.
