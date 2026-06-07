# CLEAN_EVAL_AUDIT — old headline claims re-judged on the repaired ruler

This audit re-evaluates the project's headline strength claims on the
**provenance-verified** evaluation ruler built in Phases 1–2 (runtime-asserted
leaf identity, clean 1e9 seed namespace + deck hashes, full both-sides manifests,
deterministic semantic contracts). **No training was done.** Phase-3 reruns are
evaluation only.

Each old claim is classified as one of:

| Class | Meaning |
|---|---|
| **survives** | clean number agrees within ~1σ; the claim stands |
| **directionally survives (magnitude changes)** | sign/direction holds but the magnitude moves materially (e.g. the leaf-gap discount) |
| **inconclusive** | the clean n cannot resolve the effect; report σ + required top-up, do not call it |
| **invalidated** | the clean number contradicts the claim (sign flip or effect vanishes) |
| **not reproducible** | the cell could not be re-run cleanly (missing ckpt/config) |

The two structural defects the ruler now blocks:
- **R1** — the strength yardstick (`HeuristicMCTS`) ran the **v1** leaf while the
  agent ran **v2.7**; every vs-yardstick *absolute* was inflated by the v1→v2.7
  leaf gap. Now the opponent leaf is recorded + runtime-asserted (`--heur-leaf`).
- **R7** — a residual eval (`residual_scale>0`) could silently fall back to pure
  v2.7 with `v_nn=0`. Now `assert_provenance_consistent` fails unless the residual
  path actually fired.

---

## Clean reruns (source of the new numbers)

All cells: **n=400 deck-paired, balanced seats, `--seed-start 1e9` (clean namespace),
sims=200, matched v2.7 opponent (`CAP=12 DROP_THREE_OPEN=1`), runtime-verified
provenance**. Raw per-game JSON + full manifests under
`/mnt/c/carc-shared/clean_eval_runs/<rerun>/`; aggregated in `CLEAN_RESULTS.csv`.

| # | Rerun | What it isolates |
|---|---|---|
| 1 | HeuristicMCTS-v2.7 vs HeuristicMCTS-v1 | the PURE leaf gap (no net) |
| 2 | iter_11 vs matched v2.7 | iter_11 policy at a matched leaf |
| 3 | Stage-B iter_01 vs matched v2.7 | clean rerun of the +48.1 cell |
| 4 | residual net scale 0 vs 0.25 | the value-head MARGINAL |
| 5 | residual net scale 0.25 vs v2.7 | residual ABSOLUTE (shares #4's cell) |

_Numbers below are filled from `CLEAN_RESULTS.csv` once the reruns converge._

---

## Claim-by-claim classification

<!-- FILLED ON CONVERGENCE. Template rows below carry the OLD number + the cell
     that re-judges it; the clean number + class are written after aggregation. -->

| # | Old claim (source) | Old number | Clean number | Class | Note |
|---|---|---|---|---|---|
| A | Stage-B iter_01 vs HeuristicMCTS (results.csv, A8) | +86.9 (v1 opp) | _#3_ | _tbd_ | already corrected to +48.1 at v2.7 leaf (`d472d10`); #3 re-confirms on the clean ruler |
| B | iter_11 vs HeuristicMCTS base, s200 (A1) | +25.2 / 1.45σ | _#2_ | _tbd_ | was z=1.45 = inconclusive even when reported |
| C | iter_11 vs HeuristicMCTS s800 (Phase-4 notes) | +56.7 | _n/a (s200 rerun)_ | _tbd_ | clean s200 #2 informs; s800 not re-run this pass |
| D | iter_11 +181.7 / 9.2σ (River+buggy, A1) | +181.7 | _superseded_ | **invalidated** | River+farm-bug artifact; base-only already collapsed it to +25.2 |
| E | residual value-head marginal (lever-1, A6) | +46.5 pooled (z≈2.29) | _#4 marginal_ | _tbd_ | clean deck-paired Δ from #4; R7 now guarantees the value path fired |
| F | residual absolute vs yardstick | (various) | _#5_ | _tbd_ | absolute read of the scale-0.25 cell |
| G | the v1→v2.7 leaf gap itself (R1) | ~+39 (implied) | _#1_ | _tbd_ | measured DIRECTLY, leaf-vs-leaf, no net |
| H | c=3.0 = +47.2 / 2.8σ (A6) | +47.2 → +18.5 (n=1600) | _not re-run_ | **directionally survives** | already known noise spike → +18.5; not a Phase-3 cell |
| I | value-as-leaf cliff λ=0.5≈−24..−38, λ=1.0≈−552..−604 (A2) | large negative | _not re-run_ | **survives (qualitative)** | not a Phase-3 cell; the cliff is a separate, consistently-reproduced finding |
| J | odometer 588/325 crossover | — | _not re-run_ | **carry-forward** | not in the Phase-3 set; flagged for a later clean pass |

### Power discipline
Per the project's own n-thresholds (n=400 paired ≈ ±12 elo for ~35-elo effects):
any clean effect in **[20, 35] elo** is reported as **inconclusive at n=400** with
the σ and the n needed for a verdict (~700–1500 paired), not called success/failure.

---

## What changes in the strategic narrative

<!-- FILLED ON CONVERGENCE: a short paragraph on whether the learned policy edge
     survives the matched-leaf correction (expected: real but ~half the headline),
     and whether the residual value head shows a real marginal (R7-guaranteed). -->
