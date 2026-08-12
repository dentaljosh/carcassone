# SIMS-SPLIT PRE-GATE CENSUS — per-decision-type pick stability vs budget, PRE-REGISTRATION

> **STATUS: CLOSED — the census RAN 2026-08-11 (late) and fired pre-registered branch `U`
> (PARK-WITH-DECISION). Six-touch closed out 2026-08-12.** This file was written and committed
> BEFORE the 898-root run, for orchestrator review; only a 20-root smoke (0 games, ~6 s) had
> executed at that point, to verify the pipeline, CRN and determinism — no branch below was
> read against it. **0 games played, no deck band consumed, no `results.csv` row owed**
> (nothing was played — precedent: the adaptive-k census and the budget-headroom bound).
> **Verdict in one line: the free-lunch premise is REFUTED** (the bar was `M344 ≤ 5%`; actual
> **13.07%**), while the **comparative asymmetry survives** — tiles vs meeples raw z **5.30**
> at 344 sims and **2.86** at 688, direction unanimous across all four gap strata, but ONLY
> the direction: the lowest-gap bin does not clear 2σ at 344. Secondary read: **71% of meeple
> flips are near-ties.** Readout: [READOUT.md](READOUT.md).
> `governance/PRODUCTION.yaml` is untouched on every branch of this document.

Pre-gate for the **phase-asymmetric sims split** lever
([docs/LEVER_INDEX.md](../../docs/LEVER_INDEX.md) §5 row *"phase-asymmetric sims split (tile
vs meeple budget within a turn)"*, NEVER-TRIED). The row's fact base: each champion turn runs
TWO full fair searches at the same k8×1376 budget — the tile placement (17–30 actions) and the
meeple decision (3–4 actions, measured **58% of turn time**,
[ANDROID_WALLCLOCK_MEMO_20260728](../ANDROID_WALLCLOCK_MEMO_20260728.md)). The lever's
mechanism claim: the meeple search's pick may **saturate** at a fraction of the budget (spend
partly wasted) while the tile search is still below saturation (reclaimed sims would buy real
decision changes there).

Direct precedent and template: the adaptive-k pre-gate census
([ADAPTIVE_K_CENSUS_20260728](../classical_search/ADAPTIVE_K_CENSUS_20260728.md) — 898 roots,
0 games, verdict FAIL/dies-free). Harness:
[`simsplit_census.py`](../../scripts/measurement_infra/simsplit_census.py); tests:
[`test_simsplit_census.py`](../../tests/test_simsplit_census.py); launcher:
[`launch_simsplit_census.sh`](../../scripts/measurement_infra/launch_simsplit_census.sh).

---

## 1. What is measured, on what

**Positions.** All 898 roots of the CL-070 move-agreement bank
(`/mnt/c/carc-shared/classical_search/move_agreement_k4_b28e9/roots.jsonl`), lossless
`(deck_seed, actions, ply)` replay, every root **checksum-verified** against the bank's stored
`string_representation`. Decision-type mix (counted, not assumed): **495 TILES / 403 MEEPLES**
— the corpus is close to balanced, so both arms of the census are well powered.

**Exclusion (turn-atomic latch).** `FairHeuristicPriorAgent` hands the endgame to the exact
solver ONLY at a TILES decision with `k_remaining ≤ 2`, turn-atomically (the boundary tile AND
its meeple; during a MEEPLES decision the engine has already pre-drawn next turn's tile, so
that turn's TILES decision saw `k+1` — verified empirically on the bank). Solver-owned and
excluded: TILES `k ≤ 2` (15 roots) + MEEPLES `k ≤ 1` (5 roots) = **20 excluded, 878 live
(480 TILES / 398 MEEPLES)**. The adaptive-k census's blanket `k ≤ 2` (25 roots) is also
recorded per row for joinability; the 5 MEEPLES-at-`k=2` roots it would drop are genuinely
searched decisions and stay live here.

**Search.** Per root: draw the champion's **k_dets = 8** worlds ONCE (production
`reshuffled_determinization` semantics, salt `20260811`, disjoint from the adaptive-k census
`20260728` and the CL-070 tag salts 9000/9001), then search **the same 8 worlds** at each
per-world sims rung **{172, 344, 688, 1376}** (= production/8, /4, /2, /1; rungs derived from
`PRODUCTION.yaml sims_per_det`, never hardcoded) with the production `HeuristicPriorConfig`
and per-world seeds identical across rungs — **CRN: only sims differs**. Backend: **rust**
(`PRODUCTION.yaml fair_deploy.backend`, via the audited `RustWorldSearcher` seam; pooling and
the pooled-Q decision rule stay the Python production function objects).

**Recorded per root per rung:** pooled pick (production `pooled_q_argmax`), pooled top-2 Q
gap, each world's own pick. **Primary statistic: the pooled PICK-FLIP RATE vs the 1376
reference rung, split TILES vs MEEPLES.** Secondary: flip rate within fixed reference-gap
strata `[0,0.02) [0.02,0.05) [0.05,0.1) [0.1,∞)`, and the per-world own-pick flip fraction.

**Determinism control (gate G0b).** Every root re-searches world 0 at 1376 and asserts a
bit-identical root table (`--determinism-every 1`). On rust this is a same-call repeat —
run-to-run determinism, exactly the property CRN rests on; carc_rs has no search seed and
seed-invariance is separately proven (GAP1_SEED_INVARIANCE.json). The adaptive-k census's
python different-seed control was 898/898 identical.

## 2. The confound, pre-registered before any number exists

Meeple decisions have ~4 legal actions vs ~28 for tiles, so their base flip probability is
**mechanically lower** (fewer alternatives, larger visit shares). The gate therefore splits
its claims:

- **The ABSOLUTE half is confound-immune by construction.** "Meeple flip rate at 344 is X%"
  IS the operational quantity — the fraction of meeple decisions a 4× budget cut would
  change — regardless of why it is low. The SIGNAL branch's meeple bar is absolute.
- **The COMPARATIVE half ("tiles are hungrier than meeples") is confounded** and must
  (a) survive the gap-matched strata (directional consistency in every populated bin), and
  (b) always be reported alongside `n_legal` per type (the summary emits them side by side,
  so the readout cannot silently launder the action-count difference into "saturation").
- No action-count-matched null model is attempted here (tile and meeple `n_legal` ranges do
  not overlap, so direct matching is impossible); the gap strata are the matching variable of
  record, chosen because the top-2 gap is the dimension-free difficulty scale the house
  already uses (h200 tagging, adaptive-k re-open bar).

## 3. Pre-registered branch map (evaluated in order; first to fire wins)

Named quantities: `M344`, `M688` = MEEPLES pooled flip rate at rung 344 / 688; `T344`, `T688`
the TILES analogues; CIs are Wilson-95 at the realized n (~480 tiles / ~398 meeples; at these
n a 5%-vs-10% split resolves at >3σ). Anchor for "cheap-lever territory": the adaptive-k
census's pooled-pick-change rate from removing one of four worlds (25% of budget) was
**6.1–8.4%** by phase.

**G0 — INSTRUMENT (checked first).** (a) 100% of censused roots replay checksum-clean;
(b) 100% of determinism controls bit-identical; (c) 0 worker failures (`ok=false` rows).
Any miss ⇒ **ABORT, no branch is read**; fix and re-run (re-running is free — no band, no
games, deterministic searches).

| # | condition | verdict | action |
|---|---|---|---|
| **S1 SIGNAL** (the lever's own mechanism) | `M344 ≤ 5%` with CI95-upper ≤ 7% **AND** `T344 ≥ 10%` with CI95-lower ≥ 7% **AND** two-proportion z(T344 vs M344) ≥ 3 **AND** tile rate ≥ meeple rate in every gap bin holding ≥ 30 roots of each type | **meeple search saturated where tile search is not** | Fund the play-time knob build (`sims_tile`/`sims_meeple`) + a NEW pre-registered deck-paired A/B at fixed total budget. The census licenses a *measurement*, never a promotion — flip rate is not elo. |
| **S2 REVERSED** | S1 with the two types swapped | tiles saturate, meeples do not — the lever inverts (budget should move TOWARD meeples) | Same action shape; the LEVER_INDEX row gets a direction-corrected rewrite first. |
| **N1 NO-ASYMMETRY (kill)** | \|two-prop z\| < 2 at **both** 344 and 688, raw **and** in every gap bin holding ≥ 30 roots of each type | no per-decision-type asymmetry for a split to exploit at this resolution (2σ floor ≈ 4–5 pp at these n) | **Lever dies free.** LEVER_INDEX row → measured-dead with pointer here; readout doc records the effect floor. |
| **N2 BOTH-SATURATED (kill, with a caveat owed)** | `M688` and `T688` both ≤ 2% with CI95-upper ≤ 4% | halving EITHER search changes almost nothing at the pick level — no headroom at 2× granularity | Dies free, **but the readout MUST flag the tension with CL-060** (+49.85 elo for 4× total budget): if budget buys elo while picks barely move, the value lives in flips this statistic is too coarse to see (or in gap-weighted quality) — report, do not extrapolate the kill to the budget axis. |
| **U UNRESOLVED** | anything else (e.g. asymmetry at 2–3σ; S1 partially met; rates between the bars) | park with measured rates + CIs | Orchestrator decides whether more corpus (a second root bank) is worth buying. No build on a sub-3σ comparative signal. |

N1 and N2 can co-fire (then both are recorded; the verdict is still dies-free). S1/S2 take
precedence over N2 by the evaluation order.

## 4. What this census CANNOT say (carried into any write-up)

1. **No re-budgeting.** The ladder only goes DOWN from production on each decision type; it
   measures the saturation *signal*, it cannot price the reallocation *trade* (a real split
   spends reclaimed sims on the other search — that is the follow-up A/B's job). Same
   limitation class as the adaptive-k census §3.
2. **Flip rate ≠ regret.** A flip at a tiny top-2 gap may be ~free in EV; the gap strata are
   the guard, and pricing flips in points (the EV-loss grader exists) is out of scope.
3. **Seed lineage, not the literal in-game draw** — worlds are a distributionally-equivalent
   redraw (the bank stores no agent seed); only aggregates are valid, no single row.
4. **Rules epoch: the bank is walled-era** (pre-`fixed_v1`) k4×688 self-play; replay matches
   the generating rules (checksum-enforced). The contrast is within-root across rungs — both
   sides of every flip see the identical position — so the epoch shifts the position
   *distribution*, not the *contrast*. No fixed_v1 root bank exists yet; if one is built the
   census re-runs there for ~4 min.
5. **k_dets is today's 8** (PRODUCTION.yaml), not the bank-generation era's 4 — deliberate:
   the census asks about the CURRENT champion's budget response on those positions.

## 5. Design deviations from the direct template (adaptive_k_census), recorded

1. **Turn-atomic latch exclusion** (TILES k≤2 / MEEPLES k≤1 = 20 roots) instead of the
   blanket k≤2 (25) — the blanket rule wrongly discards 5 genuinely-searched MEEPLES
   decisions; both flags are on every row for joinability.
2. **Backend rust by default** (`--backend auto` → PRODUCTION.yaml), where adaptive-k
   defaulted python for byte-compat with its pre-flag runs; the determinism control changes
   flavor accordingly (§1).
3. **`RustWorldSearcher.search_world` gained an additive keyword-only `scfg`** so one seated
   mirror serves the whole sims ladder; `None` (every pre-existing caller) is byte-identical.
4. **Output lands in-repo** (`measurement/simsplit_census_20260811/`) per the build brief,
   not on the share.

## 6. Cost, smoke, and launch

20-root stratified smoke (11 TILES / 9 MEEPLES, W14 local, rust): **0 failures, 18/18
determinism-identical, 6 s wall; per-root worker-time mean 2.76 s / p90 4.26 s** (mean over
all completions, not first-k). Full census ≈ 878 live × 2.76 s / 14 workers ≈ **3–4 min wall
at W14 on the 5900XT** (the 45–60 min prior was python-era arithmetic; the rust seam is ~10×).
Launch (detached, niced, logs + manifest + per-root jsonl into this directory):

```bash
scripts/measurement_infra/launch_simsplit_census.sh
```

Unit tests (pure parts: rung derivation, turn-atomic latch, salt disjointness, flip/gap-bin/
two-prop-z helpers, summary aggregation, AK-machinery identity pins):
`tests/test_simsplit_census.py` — 20 tests, all pass alongside the 33 adaptive-k tests.
