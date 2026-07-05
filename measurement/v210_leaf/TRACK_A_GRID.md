# v2.10 Track A — reweight-sweep grid (solver screen)

**Status:** 🚧 RUNNING 2026-07-04 — results land in `screen_trackA.json` (this doc gains a results table after).
Spec: [docs/V210_LEAF_SPEC_2026-07-04.md](../../docs/V210_LEAF_SPEC_2026-07-04.md) Track A.
Harness: `scripts/canonical_az/solver_score.py --leaf-variant` (TASK-1 machinery, commit db111a8) —
one solver pass over the 1,119 exact K≤2 marginalized roots, solve-once-score-many
(baseline + all 19 variants scored on the same SolveResult per root).

## Baseline (the v2.9 `Bmild_cap8` frozen substrate)

`V25_CAP=8, V25_OPP_CAP=8, V25_MEEPLE_K=2.0, V25_DROP_THREE_OPEN=0`
(schedule `{1:0.5, 2:0.2, 3:0.05}`), `V29_MEEPLE_CURVE=-8,-4,-1,0,2,3,4,5`.
Prior screen reference (`measurement/canonical_az/solver_score_m2_final_it00_04.json`):
**regret 0.9508 / top1 0.6095 / tau 0.6153** on the same 1,119 roots.

## Axes (bracket above AND below the v2.9 point — memory rule)

| Axis | Points | Note |
|---|---|---|
| bonus cap (opp=same) | **6, [8], 10, 12** | brackets the production 8 both ways |
| curve positive tail ×s | **0.75, [1.0], 1.25** | scales the `2,3,4,5` tail: 0.75→`1.5,2.25,3,3.75`, 1.25→`2.5,3.75,5,6.25`; negative (stranding) tail kept fixed |
| flat meeple_k (curve OFF) | **1.5, 2.0, 2.5** | ⚠️ `V25_MEEPLE_K` is INERT while the curve is set (the curve REPLACES the flat term) — so this axis disables the curve (`V29_MEEPLE_CURVE:""`). It brackets curve-vs-flat, not just k. |
| closure schedule | **[full], drop3** | `DROP_THREE_OPEN=1` = `{1:0.5, 2:0.2}` (kills 3-open lottery tickets) |

## The 19 variants

| # | name | overrides (JSON knobs) |
|---|---|---|
| 1 | cap6 | `{"V25_CAP":"6"}` |
| 2 | cap10 | `{"V25_CAP":"10"}` |
| 3 | cap12 | `{"V25_CAP":"12"}` |
| 4 | curve075 | `{"V29_MEEPLE_CURVE":"-8,-4,-1,0,1.5,2.25,3,3.75"}` |
| 5 | curve125 | `{"V29_MEEPLE_CURVE":"-8,-4,-1,0,2.5,3.75,5,6.25"}` |
| 6 | flatk15 | `{"V29_MEEPLE_CURVE":"","V25_MEEPLE_K":"1.5"}` |
| 7 | flatk20 | `{"V29_MEEPLE_CURVE":"","V25_MEEPLE_K":"2.0"}` |
| 8 | flatk25 | `{"V29_MEEPLE_CURVE":"","V25_MEEPLE_K":"2.5"}` |
| 9 | drop3 | `{"V25_DROP_THREE_OPEN":"1"}` |
| 10 | cap6_curve075 | cap6 + curve075 |
| 11 | cap6_curve125 | cap6 + curve125 |
| 12 | cap10_curve075 | cap10 + curve075 |
| 13 | cap10_curve125 | cap10 + curve125 |
| 14 | cap12_curve075 | cap12 + curve075 |
| 15 | cap12_curve125 | cap12 + curve125 |
| 16 | drop3_cap6 | drop3 + cap6 |
| 17 | drop3_cap10 | drop3 + cap10 |
| 18 | drop3_curve075 | drop3 + curve075 |
| 19 | drop3_curve125 | drop3 + curve125 |

Rationale for the cross terms: cap and curve-tail are the two axes CL-034 Tier-1 flagged
as the likely −13%-regret-class reweight headroom; drop3 changes which features the cap
even sees, so it crosses both single axes. flatk is a 3-point axis on its own (curve-off
world) — crossing it with caps would double the grid for the least-promising axis.

## Screen decision rule (spec)

A variant earns a game gate only if it beats baseline regret 0.951 / tau 0.615 on the
paired per-root read (better/worse counts, sign-z ≥ 2) — aggregates alone don't promote.
⚠️ K≤2-endgame-distributed screen: mid-game effects only by proxy; the n=400 paired
h800 game gate stays mandatory + h6400 confirm for the finalist (washout, CL-034).
A lone spike vs its parameter-neighbors >1σ = noise signature → re-measure, don't promote.

## Run config

`--max-k 2 --workers 12 --budget 5000000` (defaults otherwise), `nice -19`, detached;
out = `measurement/v210_leaf/screen_trackA.json`, log = `screen_trackA.log`.
GPU untouched (pure-CPU harness, CUDA masked); launched alongside the capacity-probe
training (~2 cores) on the 16C/32T 5900XT box.
