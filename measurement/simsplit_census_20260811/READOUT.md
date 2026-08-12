# SIMS-SPLIT PRE-GATE CENSUS — READOUT

> **STATUS: RAN 2026-08-11 (late) → PRE-REGISTERED BRANCH `U` (PARK-WITH-DECISION).**
> 0 games played, no deck band consumed, no `results.csv` row owed (nothing was played).
> `governance/PRODUCTION.yaml` untouched. Pre-registration:
> [PREREG.md](PREREG.md) (committed before the run; only a 20-root smoke preceded it).
> Instrument: [`simsplit_census.py`](../../scripts/measurement_infra/simsplit_census.py).

## 1. Instrument gate G0 — PASS

| check | required | actual |
|---|---|---|
| replay checksum-clean | 100% | **898/898** |
| determinism controls bit-identical | 100% | **878/878** |
| worker failures (`ok=false`) | 0 | **0** |

878 live roots after the turn-atomic latch exclusion (20 solver-owned: TILES `k≤2` = 15,
MEEPLES `k≤1` = 5), split **480 TILES / 398 MEEPLES**. Per-root worker time mean 3.23 s /
p90 5.54 s; whole census ≈ 4 min wall at W14.

## 2. Primary statistic — pooled pick-flip rate vs the 1376 reference

| rung (per world) | TILES (n=480) | MEEPLES (n=398) | contrast |
|---|---|---|---|
| 688 (½) | 18.54% | 11.56% | z **2.86** |
| 344 (¼) | **27.71%** | **13.07%** | z **5.30** |
| 172 (⅛) | 35.21% | 14.07% | z **7.14** |

Mean legal actions: TILES **28.25**, MEEPLES **4.19** (the confound the prereg named).
Median reference top-2 gap is near-identical across types (0.0593 vs 0.0609), so the two
arms are not sitting at different difficulty levels.

## 3. Adjudication — branch `U`, because the two halves of S1 disagree

**S1 (SIGNAL) did NOT fire.** Its confound-immune half is the *absolute* meeple bar:
`M344 ≤ 5%` with CI95-upper ≤ 7%. Actual **M344 = 13.07%, CI95 [10.10%, 16.73%]** — the bar
is missed by ~2.6×. Cutting the meeple search 4× changes **one meeple decision in eight**.
The lever's stated mechanism — *the meeple search's budget is partly wasted* — is therefore
**refuted in the sense that matters**: there is no free budget to reclaim.

**S2 (REVERSED)** — no. **N1 (NO-ASYMMETRY)** did not fire either: it required |z| < 2 at
both 344 and 688, and the raw contrasts are 5.30 and 2.86. **N2 (BOTH-SATURATED)** did not
fire: both rates at 688 are far above the ≤2% bar.

⇒ **`U` — park with measured rates, orchestrator decides.**

**What did survive, and strongly: the comparative claim.** Tiles are hungrier than meeples,
and it is not the action-count artifact. Within fixed reference-gap strata (the
pre-registered matching variable), the tile flip rate exceeds the meeple flip rate in **all
four bins at every rung** — the direction is unanimous. Bin-level significance at the 344
rung: `[0,0.02)` z 1.67 · `[0.02,0.05)` z 3.59 · `[0.05,0.1)` z 4.32 · `[0.1,∞)` z 2.09.
(At the 172 rung: 3.23 / 4.32 / 5.04 / 2.42.) ⚠️ **Only the direction is unanimous — the
lowest-gap bin does not clear 2σ at 344**, so quote the bins, not a blanket "significant in
every stratum".

## 4. What this changes about the lever

The lever was framed as a **free lunch** (reclaim wasted meeple sims). The census kills that
framing and replaces it with a **trade**: moving budget meeple → tile pays ~13% of meeple
picks to buy a tile budget increase (1376 → ~2400 at a 4× meeple cut, since the meeple
decision is ~58% of turn time). Whether that trade is positive is **exactly what this census
cannot say** (PREREG §4.1 — the ladder only descends; flip rate is not regret). Only a
deck-paired game screen can price it.

Secondary observation, recorded because it bears on a different claim: **neither search is
converged at production budget** (18.5% / 11.6% of picks still move when halved). That sits
comfortably with CL-060's +49.85 elo for 4× total budget, and it is the reason the N2
"both-saturated" branch — which would have owed a CL-060 tension caveat — never fired.

## 4b. The gap-stratified read — the meeple flips are overwhelmingly COIN-FLIPS

This is the pre-registered secondary statistic (PREREG §1 strata, §4.2 "flip rate ≠ regret …
the gap strata are the guard") used exactly as designed — **not** a post-hoc re-slice. It is
still a secondary read: **branch `U` stands on the primary statistic and is not revised by
this section.**

Flip rate at the 344 rung, by reference top-2 Q gap:

| gap bin | TILES | MEEPLES |
|---|---|---|
| `[0, 0.02)` | 47.9% (67/140) | **37.0%** (37/100) |
| `[0.02, 0.05)` | 39.5% (32/81) | 13.7% (10/73) |
| `[0.05, 0.1)` | 23.1% (21/91) | **2.1%** (2/94) |
| `[0.1, ∞)` | 7.8% (13/167) | **2.3%** (3/131) |

**71% of all meeple flips (37/52) sit in the near-tied `[0,0.02)` bin**, and above a gap of
0.05 the meeple search essentially stops changing its mind — 5 flips in 225 roots. The tile
search, by contrast, flips across **every** stratum, including 13 flips at gap > 0.1: it
changes picks it had previously scored as *clear*.

**Why this matters for the shape of the curve.** The meeple flip rate is nearly flat across
an 8× budget range (14.07 → 13.07 → 11.56%) while the tile rate falls steeply
(35.21 → 27.71 → 18.54%). A flat flip rate across 8× is the signature of decisions whose top
two options are close enough that the pick is near-arbitrary at any budget — the marginal
meeple sim is buying re-rolls of a coin, not convergence. A steep rate is the signature of a
search still genuinely converging.

⚠️ **What this does NOT license.** Flip rate weighted by gap is still not regret in points,
and "the search had a small Q gap" is not proof the two moves are equal in EV — the leaf
could be mis-pricing both (that is the entire premise of the neighbouring denial lever). The
honest statement is: **the unweighted primary statistic counts coin-flips as if they were
losses, so it is an upper bound on the cost of a meeple budget cut, and the gap strata say
the true cost is concentrated where the search itself is close to indifferent.** Pricing the
flips in points needs the EV-loss grader, which is out of scope here.

⇒ Practical consequence: the S1 bar was stated on the unweighted rate, so it failed
correctly and honestly — but the trade the screen must price is **better than the raw 13.07%
implies**, and the reallocation ladder should be sized aggressively (meeple → 344), because
the marginal meeple sim demonstrably buys the least where the search is least decided.

## 5. Standing limits (carried from PREREG §4)

1. No re-budgeting measured: the trade is unpriced, only the saturation signal is.
2. Flip rate ≠ regret; a flip at a tiny top-2 gap may be ~free in EV.
3. Worlds are a distributionally-equivalent redraw — aggregates only, no single row.
4. The root bank is **walled-era**; the contrast is within-root, so the epoch shifts the
   position distribution, not the contrast.
5. `k_dets = 8` (today's champion) on a bank generated at k4×688 — deliberate.
