# Battery A/B bench — results

Workload: 48 champion moves/run, seed 424242, budget k8x1376=11008, rules `fixed_v1`, backend `rust`.

Identity gate: PASS — all 9 runs report move_hash `ece55328277e4af5…` (identical play across arms).

Idle baseline: 1.70 W (subtracted in the net column).

| rust_threads | tiearb B | reps | J/move (mean ± sd) | s/move (mean ± sd) | mean W | net J/move | fires |
|---|---|---|---|---|---|---|---|
| 2 | — | 3 | 3.177 ± 0.576 | 0.526 ± 0.032 | 6.02 | 2.269 | — |
| 2 | 2 | 3 | 3.992 ± 0.295 | 0.853 ± 0.009 | 4.67 | 2.536 | 39/81 |
| 2 | 16 | 3 | 14.741 ± 3.992 | 3.045 ± 0.250 | 4.93 | 9.551 | 39/81 |

*J/move integrates the whole workload window (search + engine bookkeeping between moves). The J/move-vs-latency trade is the owner's call — see android/tools/BATTERY_BENCH.md.*

## Tie arbiter — measured on-device cost

Projections use `phi` = 17.573 fired tied tile plies per game and 72 champion decisions per game (the desktop cost model's own denominator, measurement/tiearb2_stage2_20260817). Every arm played the CHAMPION trajectory, so this prices arbitration work — not the arbiter's picks.

| B | fires/tile plies | mean arms | s/fired ply (arb clock) | s/fired ply (Δ arms) | ΔJ/fired ply | added s/game | added J/game | errors | partial_argmax |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 39/81 (0.481) | 3.08 | 1.151 | 1.205 | 3.01 | 20.2 | 52.9 | 0 | 0 |
| 16 | 39/81 (0.481) | 3.08 | 9.269 | 9.298 | 42.70 | 162.9 | 750.4 | 0 | 0 |

| B | rho_phone MEASURED (arb clock) | rho_phone (Δ arms) | vs session control | game wall-clock ratio | baseline %batt/game | added %batt/game |
|---|---|---|---|---|---|---|
| 2 | 0.742 | 0.777 | 2.186 | 1.181× | 0.37+ | 0.09 |
| 16 | 5.976 | 5.995 | 17.614 | 2.459× | 0.37+ | 1.23 |

`rho_phone` = added arbiter seconds on a fired ply ÷ **1.551 s**, the shipped phone champion's whole-game s/move (PHASE_A §1's own denominator, so this is directly comparable to its **5.520 at B=16** prediction from desktop worker-seconds at W=30). ⚠️ A bench run covers only the FIRST n moves of a game, which are cheaper than the game average — this session's control measured 0.526 s/move — so the 'vs session control' column is the larger, early-game-relative figure and is NOT the number to compare against 5.520. The two rho routes (the rust agent's internal `tiearb_secs` clock vs the arm-to-arm subtraction) are independent; a large gap between them means the arms drifted and the ΔJ column inherits that doubt.

⚠️ **The opening bias runs AGAINST the arbiter, so these costs are an upper bound.** A tier-1 arbitration playout runs to a terminal state, so a tied ply early in the game is priced over ~140 remaining plies while a late one is priced over a handful — benching the FIRST n moves therefore measures the most expensive arbitration in the game. The opening also ties more often (measured fires/tile ply above vs the whole-game `phi`/72). Read the per-fired-ply and per-game costs as **ceilings**, not central estimates. `game wall-clock ratio` divides the whole-game arbiter bill by the whole-game champion (1.551 s/move × moves/game); `baseline %batt/game` is marked `+` because it is referenced to this session's opening-phase J/move and a full game costs more.