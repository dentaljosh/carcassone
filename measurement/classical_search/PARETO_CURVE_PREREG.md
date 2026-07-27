# PRE-REGISTRATION — budget/elo Pareto curve for the deploy champion

> **STATUS: PRE-REGISTERED 2026-07-26, BEFORE ANY CELL RAN.** Nothing in this file
> may be edited after the first result lands; corrections go in a dated Results
> section below. Approved by Joshua 2026-07-26 ("get it going, launch overnight").

## Why

[TOURNAMENT_TIMING_2026-07-26](../../docs/research/TOURNAMENT_TIMING_2026-07-26.md)
established that competitive play is **15 min per player, sudden death, no
increment** ⇒ ~12.9 s per searched decision. The deploy champion (k4×688 = 2752
sims) uses **26% of clock**; every stronger config we have measured uses 91–178%.
So the decision-relevant question is no longer "how much elo can compute buy"
(answered: ~+40–50, plateauing by 4×, per CL-060) but **"what does elo cost when
we go DOWN, and where is the knee"** — because clock margin is now a resource.

The sub-deploy region is **entirely unmeasured at production width**. The only
low-budget ladder (CL-046 D0: +27.9/+61.4/+81.4/+149.3 at 800/1600/2752/5504) was
run at `k_dets=8`, and k8→k4 alone is worth ~+66 elo at 2752 (CL-054), so its
LEVELS do not transfer — only its shape (~−27 to −34 elo per halving) is
indicative.

## Design

**Opponent for every cell: the deploy champion itself** (`--opponent fair-champion`,
k4×688), head-to-head. NOT the h800 rung. Reason: the h800 rung is
ceiling-compressed for strong configs — both arms beat it by ~9 pts/deck, which is
exactly what made CL-060's original closure return "flat past 2752" at z=0.86
before the direct H2H refuted it at z=3.48. Head-to-head vs the config we would
actually field is the design of record.

**Width is re-solved at each budget.** Non-negotiable: at 8× total, k8×2752 scored
+3.5 (flat) while k16×1376 scored +35.6 — same budget, allocation was the entire
effect (CL-060 budget-curve extension). A budget point measured at one arbitrary
allocation is uninterpretable. CL-054 found k4 optimal at 2752 with k2 close
behind (direct k4−k2 z=1.33, a flat peak), and the textbook story is that optimal
width GROWS with budget ⇒ below deploy the candidates are k4 and k2.

**Cells** (all `--info fair`, i.e. the classical champion on both sides; frozen
curve125 leaf `a36d2e15a3b3d71d` both sides; exact-K=2; n=400 deck-paired =
200 decks × 2 seats):

| # | cell | candidate | total | ×deploy | band |
|---|---|---|---|---:|---|
| 1 | `pareto_k4x344_1376_vs_deploy` | k4×344 | 1376 | 0.5× | 60e9 |
| 2 | `pareto_k2x688_1376_vs_deploy` | k2×688 | 1376 | 0.5× | 60e9 |
| 3 | `pareto_k4x172_688_vs_deploy` | k4×172 | 688 | 0.25× | 62e9 |
| 4 | `pareto_k2x344_688_vs_deploy` | k2×344 | 688 | 0.25× | 62e9 |
| 5 | `pareto_k4x1376_5504_vs_deploy` | k4×1376 | 5504 | 2× | 64e9 |

Cells 1+2 **share band 60e9** and 3+4 **share band 62e9** — deliberately, so the
within-tier allocation contrast is a **deck-matched double-CRN delta** (the CL-054
method) rather than a comparison of two independent absolutes. Bands 58/60/62/64e9
were chosen by ENUMERATION of every band in `results.csv` (burned:
1.2–3.13, 4.21, 5, 6, 8.8, 9.4, 10, 12.7, 13, 13.2, 15, 17, 22, 24, 26, 28, 32, 39,
40, 44, 46, 48, 52, 56e9; 99e9 is pre-flight scratch, never harvested).

Cell 5 fills a real gap: **2× has never been measured head-to-head vs deploy** —
CL-060 measured 1×, 4×, 8× vs deploy, and 2× only against the h800 rung.

## Read-out rules (pre-registered)

1. **Report BOTH statistics for every cell** — winrate z AND deck-paired margin z.
   Quoting only the one that clears 2σ is how three findings here were later
   overturned (c=3 "+47", anchor-fraction "+39", flywheel "+88.7").
2. **Within-tier allocation contrast = deck-matched delta on the shared band**, not
   a difference of the two absolute elos.
3. **If the allocation delta is |z| < 1**, POOL the tier's two cells into a single
   n=800 estimate of what that budget costs vs deploy. Registered here, in advance,
   because post-hoc pooling was the un-preregistered step in CL-067.
4. **The curve is plotted against MEASURED wall-clock** (`prefix ms/move` from each
   cell's own summary, both sides solver-free counters) — not nominal sims — plus
   solver s/game, plus the resulting **% of the 900 s tournament clock**.
5. **⚠️ EXPECTED SIGN IS NEGATIVE.** Less compute should be weaker. A *positive*
   result at a lower budget is a red flag for a config error (wrong side, wrong
   leaf, seat imbalance) — investigate the manifest before believing it. This guard
   is registered because the curve's whole purpose is to price a downgrade, which
   makes a flattering result the dangerous one.
6. **NOTHING IS PROMOTED FROM THIS.** `governance/PRODUCTION.yaml` and the champion
   stay untouched. A sub-deploy config becomes a *proposal for Joshua* only if it
   costs **< ~1σ (≈17 elo at n=400)** while materially cutting clock usage — and
   then it owes its own fresh-band confirmation before any promotion, per the
   never-promote-from-a-single-screen rule.

## Validity guards (a cell is INVALID, not merely negative, if any fail)

- `deck_hash` mismatches ≠ 0 within a cell.
- Either side's leaf hash ≠ `a36d2e15a3b3d71d`, or the log's "BOTH SIDES curve125"
  line is not YES.
- Solver `timeouts` ≠ 0 (a timeout silently changes the endgame policy).
- Games short of the requested n (the harness has clipped before — CL-023 n=384).

## Operational

Two boxes, `--shared-claim` work-stealing on one pool per cell, **W=16 each**
(Joshua's call; the measured pure-CPU optimum on local is higher, so this
sacrifices some throughput for interactive headroom). Pure CPU — `--info fair` runs
no net, so no carc-orch, no GPU, no OMP-pin concern. Cells run in the listed
priority order and are individually resumable; whatever the queue does not reach
by morning simply stays queued.

**ETA (from `cl060_budget_local.log`, the same harness at W16 local: 91 s/game at
candidate 11008 + opponent 2752):** modelled serial cost/game = cand ms/move × 70
+ 263 s opponent + ~31 s solver ⇒ n=400 combined-box ≈ **2.0 h** (cells 1,2),
**1.7 h** (cells 3,4), **3.8 h** (cell 5); **~11 h for the full queue**, i.e. the
first four cells should land overnight.

⚠️ If the queue must be killed, **clean stranded `.claim` files before resuming** —
a killed `--shared-claim` run strands claims and a resume stalls forever.
