# Exact-K endgame conversion slice

Solved 140/140 positions. Info model: k=2 marginalized (honest), k=3 clairvoyant+ab (hindsight upper bound). Lower regret = better conversion.

| agent | mean exact regret (pts) | match-optimal % | n | regret k=2 | regret k=3 |
|---|---|---|---|---|---|
| random | 2.057 | 31% | 140 | 1.46 | 2.66 |
| greedy | 0.979 | 75% | 140 | 0.76 | 1.20 |
| h200_v27 | 0.750 | 71% | 140 | 0.57 | 0.93 |
| h200 | 0.600 | 74% | 140 | 0.51 | 0.69 |
| h800 | 0.650 | 72% | 140 | 0.47 | 0.83 |
| h3200 | 0.457 | 81% | 140 | 0.24 | 0.67 |
| h6400 | 0.521 | 80% | 140 | 0.29 | 0.76 |
| rod1 | 0.807 | 64% | 140 | 0.73 | 0.89 |
| iter08 | 0.979 | 63% | 140 | 0.77 | 1.19 |
