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

## 5. Standing limits (carried from PREREG §4)

1. No re-budgeting measured: the trade is unpriced, only the saturation signal is.
2. Flip rate ≠ regret; a flip at a tiny top-2 gap may be ~free in EV.
3. Worlds are a distributionally-equivalent redraw — aggregates only, no single row.
4. The root bank is **walled-era**; the contrast is within-root, so the epoch shifts the
   position distribution, not the contrast.
5. `k_dets = 8` (today's champion) on a bank generated at k4×688 — deliberate.
