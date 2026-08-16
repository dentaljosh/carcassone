# Battery A/B bench — results

Workload: 24 champion moves/run, seed 424242, budget k8x1376=11008, rules `fixed_v1`, backend `rust`.

Identity gate: PASS — all 9 runs report move_hash `d844c5b36bcb07c9…` (identical play across arms).

Idle baseline: 1.04 W (subtracted in the net column).

| rust_threads | reps | J/move (mean ± sd) | s/move (mean ± sd) | mean W | net J/move |
|---|---|---|---|---|---|
| 1 | 3 | 3.074 ± 0.042 | 0.461 ± 0.001 | 6.65 | 2.591 |
| 2 | 3 | 1.956 ± 0.582 | 0.351 ± 0.004 | 5.49 | 1.584 |
| 4 | 3 | 3.797 ± 0.486 | 0.465 ± 0.001 | 8.10 | 3.307 |

*J/move integrates the whole workload window (search + engine bookkeeping between moves). The J/move-vs-latency trade is the owner's call — see android/tools/BATTERY_BENCH.md.*
