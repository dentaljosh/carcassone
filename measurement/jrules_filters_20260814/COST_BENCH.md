# Surface C cost bench — root filter at deploy budget

**2026-08-14, local 5900XT, IDLE box (exclusive tenant), worktree wheel,
pinned toolchain.** `FairAgentRs` mask **11 (JF_CURRENT)** vs mask **0**
(champion) at **k8×1376 = 11008, threads=1** (the farm-rule per-worker shape),
interleaved legs, **min-of-3 reps** per (position, arm), on **16 non-forced
replayed roots** (2 seeded games × 4 TILE roots + 4 MEEPLE roots; 6 of the 8
meeple roots had live drops — F-J10 dropping 1–2 farmer claims — so the ON leg
is exercised, not vacuous).

| statistic | value |
|---|---|
| aggregate on/off ratio | **1.0024×** |
| median ratio | **1.0018×** |
| per-position range | 0.968 – 1.052 |
| probe alone (`jrules_filter_probe(11)`, non-forced meeple root) | **~7.3 µs** |

Reading: **the filter is cost-free at bench resolution** — exactly the §7
expectation (it runs once per meeple move; its most expensive path, F-J3's
child-afterstate tags, arms only at reserve ≤ 1 and never fired on these
roots; the per-position spread is bench noise, and a live drop changes the
search tree, which is a *search* difference, not filter overhead). Tile roots
(the expensive searches, where the filter is inapplicable by design) read
1.00× throughout.

⚠️ Per the family's record (surface A predicted 1.12–1.14 and realized
1.2116), the ratio of record is the CELL's own `ms_ratio_cand_over_opp`
(prereg N4, 1.20 trigger, first-block read) — never this bench.

Raw rows: the session's `jf_cost_bench.py` output (16 JSON lines), reproduced
from `rust/carc/carc-core` + the pyo3 wheel at commit `82f3fa96`.
