# Battery A/B bench — results

Workload: 24 champion moves/run, seed 424242, budget k8x1376=11008, rules `fixed_v1`, backend `rust`.

Identity gate: PASS — all 1 runs report move_hash `d844c5b36bcb07c9…` (identical play across arms).

Idle baseline: 1.01 W (subtracted in the net column).

| rust_threads | reps | J/move (mean ± sd) | s/move (mean ± sd) | mean W | net J/move |
|---|---|---|---|---|---|
| 4 | 1 | 1.447 ± — | 2.003 ± — | 0.72 | -0.584 |

*J/move integrates the whole workload window (search + engine bookkeeping between moves). The J/move-vs-latency trade is the owner's call — see android/tools/BATTERY_BENCH.md.*
