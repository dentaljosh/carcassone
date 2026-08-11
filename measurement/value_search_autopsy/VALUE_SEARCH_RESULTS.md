# Value/Search Autopsy — Stage 3: miss classification + results

**Date:** 2026-06-27 · **DIAGNOSTIC ONLY.** Plan: [VALUE_SEARCH_PLAN.md](VALUE_SEARCH_PLAN.md) ·
Miss set: [VALUE_SEARCH_MISS_SET.md](VALUE_SEARCH_MISS_SET.md) ·
Interventions: [VALUE_SEARCH_INTERVENTIONS.md](VALUE_SEARCH_INTERVENTIONS.md) ·
Decision: [VALUE_SEARCH_DECISION.md](VALUE_SEARCH_DECISION.md).

## Stage 3 — miss classification (primary bucket × phase, n=1321)

| bucket | endgame | non-endgame | total | share |
|---|--:|--:|--:|--:|
| 1. not-explored (h6400-best never visited) | 127 | 34 | 161 | 12% |
| 2. explored-undervalued (visited, search-Q ranks it below the bad move) | 145 | 290 | 435 | 33% |
| 2b. explored-other (visited, Q ~tied/higher, argmax/visit miss) | 318 | 144 | 462 | 35% |
| 6. horizon/leaf-blind (visited, static leaf can't rank, no cheap fix) | 103 | 160 | 263 | 20% |
| **all** | | | **1321** | |

**~88% of misses are EXPLORED, not unexplored.** The search *visits* h6400's move and ranks another
above it; only 12% never visit it (and those cluster in the endgame, 127/161). So the dominant failure
is **mis-ranking under the search, not under-exploration** — the move is in the tree but its backed-up Q
is wrong because the prior concentrated visits elsewhere and the leaf is value-blind at its children.

## Which intervention flips each miss to a hit (resolving lever, n=1321)

| lever | % of misses fixed |
|---|--:|
| **classical h800 (net-free, 4× sims)** | **90%** |
| **classical h200 (net-free, matched sims)** | **81%** |
| **flat (uniform) prior, matched sims** | **79%** |
| teacher-prior injection (root) | 64% |
| more neural sims (800) | 55% |
| no neural value (rs0) | 36% (≈ baseline 35%) |

The fixers rank **prior-removal ≈ classical ≫ teacher-prior > more-sims ≫ value**. Removing the net's
policy prior (flat) recovers 79% of misses *at the same 200-sim budget*; the neural value is inert.

## I6 — the value/leaf-blindness underneath (n=858 argmax-misses)

On argmax-misses, the static v2.9 leaf ranks the teacher's child above the NMCTS-pick's child only
**22%** of the time (endgame **9%**); the neural residual lifts it to 34% (endgame 22%) and never
corrupts (107 wrong→right, 0 right→wrong). So the leaf is value-blind at 1-ply — but deep search with
**broad** exploration aggregates the leaf over the subtree and recovers the move 79–81% of the time. The
net prior prevents that aggregation by concentrating visits; see [VALUE_SEARCH_INTERVENTIONS.md](VALUE_SEARCH_INTERVENTIONS.md).

## The decisive control — full pool, un-confounded (gap≥0.02, n=4277)

| agent @200 sims, v2.9 leaf | top1 (=h6400) | regret | eg top1 | eg regret |
|---|--:|--:|--:|--:|
| neural net-prior (production iter04) | 0.799 | 0.0189 | 0.802 | 0.0173 |
| neural **flat**-prior | 0.867 | 0.0104 | 0.833 | 0.0137 |
| **classical h200 (net-free)** | **0.911** | **0.0070** | 0.933 | 0.0046 |

**net < flat < classical**, monotone and large, on the SAME states (not just misses). Flattening the
net's own prior gains +6.8pp / −45% regret; dropping the net for classical gains +11.2pp / −63%. The
neural stack makes 200-sim search *worse* than 200-sim uniform-UCB search on decision-relevant states.
Classical HeuristicMCTS at 1/32 the teacher's budget already recovers 91% of its decisions.

## Search-budget trajectory (neural, net prior, on the miss set)

200 → 400 → 800 sims = top1 0.350 → 0.457 → 0.553. More neural search overcomes the bad prior only
**slowly**; classical reaches 0.815 at 200 sims and 0.899 at 800. So the binding constraint is **not**
search budget — it is the prior.

## Synthesis

| candidate bottleneck | verdict |
|---|---|
| A policy/exploration | **CONFIRMED, inverted** — the prior is the bottleneck, but it is *over-confident*, not *under-trained*: a FLAT prior beats it. The fix is not a better policy, it is *less* policy concentration. |
| B search budget/horizon | partial — more sims helps slowly (0.35→0.55 at 4×) but is dominated by prior-removal at matched budget. |
| C neural-value corrupts | **rejected** — residual never corrupts (I6: 0 right→wrong); rs0/rs0.25/rs0.5 indistinguishable. |
| D neural-value irrelevant | **CONFIRMED** — the value head is inert for search (I4). |
| E horizon/endgame value | partial — the leaf is value-blind at 1-ply (worst in endgame), but deep search recovers it *given broad exploration*; the endgame also holds most of the not-explored tail. |
| F classical-search edge | **at the ROOT only** — classical at matched budget agrees with h6400 more on decision states; BUT the Stage-5 game screen shows this does **not** convert (classical h200 ≈ neural iter04 in games). So NOT "strictly better" where it counts. |

**Root level:** the value head is inert and the policy prior makes worse *decisions* than bare heuristic
search on decision-relevant states. **Game level (the correction):** this does **not** convert — classical
h200 ≈ neural iter04 head-to-head at matched compute (WR 0.438, margin −2.6, n=96). The decision-state errors
wash out because most game positions are low-gap. So the net is **game-neutral** vs classical, not
game-harmful; the binding constraint for strength is search depth + the (inert) value head, not the
policy. See [VALUE_SEARCH_DECISION.md](VALUE_SEARCH_DECISION.md). **Methodological takeaway: root/policy
agreement metrics do not predict head-to-head strength — gate on games.**
