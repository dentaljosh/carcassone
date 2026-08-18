# Tie-arbiter widening campaign — planning consolidation (2026-08-18)

**Funded 2026-08-17 (late), owner verbatim: "i'm funding all 4. these are our only live
levers for elo. have agents plan them out."** Four rung plans landed the same night
(`PLAN_meeple_ties.md`, `PLAN_B_gt_16.md`, `PLAN_J_gt_4.md`, `PLAN_eps_near_ties.md`),
paper-only — 0 worker-seconds spent, no sealed path touched. This file is the
orchestrator's reconciliation; the rung plans are the authority on their own designs.

## Post-planning state of the four rungs

| rung | state after planning | next physical action |
|---|---|---|
| (1) meeple plies | **likely dead — free prior below supply bar** (JCZ-mining meta: meeple exact-tie 16.5% = 4.8/game vs tile 55.1% = 22.96/game, before removing duplicates, which arithmetic suggests account for ~all of it; the July 60% figure is the *duplicate* class arbitration cannot separate) | ≤0.5 worker-h kill-census over 1,299 banked games (<5 min wall), grouping by board-level claimed-region id; carries the eps gap-CDF piggyback |
| (2) B>16 | **the live rung.** 5-model saturation fits split into two worlds: still-rising (Δ(16→64) +0.05…+0.20) vs saturated (~+0.02); free corroborants (flat pick-churn, climbing oracle-agreement) say still-rising | shared fresh-corpus instrument run, primary Δ(16→64), se≈0.020, 2σ floor +0.040 |
| (3) J>4 | **alive, prize corrected** — the funded ~1.4× is an inherited raw-tie-set extrapolation; on the deduped arm population the same order-statistic math gives **≈1.244× at capped plies / ≈1.087× globally** (~+0.08 pts/capped ply). Arm selection is a seeded draw (no arm-0 side channel); un-capping is a call-site value, 0 LoC in carc-core | rides rung (2)'s shared run (+22% cost) — does not run standalone |
| (4) eps>0 | **DEAD from banked data — recommend formal closure.** Leaf values are a lattice (0.05 grain); phi(eps) is the banked gap CDF; eps=0.05 adds +0.7–1.0% fired plies vs a 5% power-derived kill bar (fires on both independent corpora); meaningful mass needs eps≈1.0 = overriding a full point of leaf preference. Best fundable form ~21,000 games/cell | none — owner ratifies closure; gap-scalar piggyback rides the meeple census |

## Cross-plan reconciliation (orchestrator rulings for the DESIGN phase)

1. **Shared run adopted**: rungs (2)+(3) read disjoint statistics of ONE paid instrument
   run. Both planners converged independently; the load-bearing requirements are
   **M=128 world records** (cross-fit parity halves cap usable B at M/2 — the M=64
   shorthand in the funding row is wrong, per PLAN_B_gt_16 correction #1), **uncapped
   arm recording with CRN worlds shared across ALL full-set arms** (PLAN_J_gt_4 §8
   requirement — without it the campaign pays twice), and **both READ_RULEs in one
   blind commit, one read-out**, with `arb(B=16,J≤4)` declared a shared cell.
2. **Cost figures reconciled**: PLAN_J_gt_4's ~83 worker-h standalone vs PLAN_B_gt_16's
   ~865 worker-h total are not in conflict — the shared-run total is dominated by the
   **python-era clair-puct pricing judge (~582 wh)** and fresh corpus generation
   (~234 wh); the arbiter-side playouts (rust, c=0.178232) are noise. The single
   biggest cost lever is **W1: wire the Phase-A rust ARB judge into
   `scripts/tiletie/run_tiletie.py`** (12.2× on that leg) — instrument work, blocked by
   the commit freeze until the JCZ markers land.
3. **Variance budget ruling** (PLAN_B_gt_16): ~84% of increment variance is pricing
   noise, not position heterogeneity ⇒ buy evaluation worlds (E=64), keep n=1,350.
4. **Band correction**: `133000000000` (suggested in two plans) is the JCZ cells' —
   claimed minutes before the planners read the registry. The widening run reserves
   **`134000000000`** + top-up range; re-read `BAND_REGISTRY.csv` at claim time.
5. **Translation caveat carried programme-wide**: Stage 1b's offline read
   under-predicted Phase B's game-cell result 3.9× (+0.79 predicted vs +3.07 realized
   pts/game). No game cell for B=64 gets sized until the offline increment lands; the
   offline→game map is unestablished in BOTH directions and must be quoted with any
   projection.

## Sequencing (recommended)

0. **Post-JCZ-markers, freeze lifted**: meeple kill-census (+eps gap piggyback) —
   minutes; expected outcome: rungs (1)+(4) close, campaign narrows to (2)+(3).
1. **W1 instrument wiring** (rust ARB judge into `run_tiletie.py`; bit-exactness
   obligation vs the python judge per the Phase-A G-BITEXACT precedent).
2. **Blind DESIGN + READ_RULE** for the shared (2)+(3) run, then the run:
   ≈865 worker-h ≈ **20–22 h wall on local W30 + laptop W22**.
3. Game-cell decision only after the offline read, per ruling 5.

## Owner decision asks (carried to Joshua)

- Ratify **eps>0 closure** on banked data (rung funded, answered without spend).
- Ratify **meeple kill-census** as the rung's entire budget unless it survives its bar.
- Confirm the **shared-run shape** for (2)+(3) at ~20–22 h two-box wall (his "these are
  our only live levers" funding stands; this line item is the realized price of it).
- PLAN_J_gt_4 asks 3/4/6 (adjudicating statistic, mining depth, I6 amendment
  pre-approval) — deferred to the DESIGN commit, flagged here so they don't silently
  default.

*Nothing here is a prereg. The blind DESIGN/READ_RULE for any run that fires comes
later, as its own commit, per house discipline. `PRODUCTION.yaml` untouched.*
