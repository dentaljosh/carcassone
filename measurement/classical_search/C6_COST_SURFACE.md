# C6 Stage-0 — COST SURFACE (the go/no-go gate)

> **STATUS: PENDING RUN** — this file is a stub. It is auto-generated (overwritten
> with results + the pre-registered verdict) by
> `scripts/classical_search/bench_ab_cost.py` when the full cost bench is run.
> Pre-registered by [C6_ALPHABETA_DESIGN.md](C6_ALPHABETA_DESIGN.md) §7. No
> `results.csv` row (bench, not an experiment).

## VERDICT: **PENDING RUN**

Pre-registered rule (§7), median midgame (plies 30-100) achievable completed depth:

- **>= 6 plies (3 full turns) -> GO** — proceed to the Stage-1 agent build (§8).
- **<= 4 plies -> DECLINE** — C6 CLOSED on cost, no agent build (§9 K0).
- **= 5 plies -> GRAY** — attended decision for Joshua with the §2 make/unmake
  escalation arithmetic.

## What this bench measures (all §7)

1. Champion equal-wall-clock budget: PUCT float @2750 sims, reuse OFF, single-thread
   median ms/move on the 20 fixed `bench_equal_time_cy.py` positions (curve125 leaf).
2. Micro-measurements by ply bucket (early/mid/late): flat float leaf µs,
   `get_next_state` µs (the copy-state step), `get_valid_moves` µs (tile vs meeple),
   `string_representation`+blake2b µs, and the legal-count histogram by phase.
3. Throwaway fixed-depth αβ (Δleaf ordering, NO TT — the floor) + a TT variant
   (§3 blake2b-128 key, fail-soft flags): child-steps + wall to COMPLETE
   d ∈ {2,4,6,8}, b_eff, TT-on/off step ratio at d=6, cross-parent EXACT-hit
   fraction at d=6, and achievable depth within the champion budget.

## How to run

```
# correctness self-test first (cheap — validates the mover convention):
nice -n 19 .venv/bin/python -u scripts/classical_search/bench_ab_cost.py --self-test

# the full cost surface (single-thread, <1 box-h — fills this file in):
nice -n 19 .venv/bin/python -u scripts/classical_search/bench_ab_cost.py
```

Raw numbers land in `ab_cost_raw.json` alongside this file.
