# Value/Search Autopsy — Stage 2: intervention matrix

> ⚠️ **These are ROOT-LEVEL (agreement-with-h6400) metrics.** The Stage-5 game screen shows the
> classical/flat-prior root edge does **NOT** convert to head-to-head game strength (classical h200 ≈
> neural iter04). Read these as *decision-quality diagnostics*, not strength claims — see
> [VALUE_SEARCH_DECISION.md](VALUE_SEARCH_DECISION.md).

**Date:** 2026-06-27 · **DIAGNOSTIC ONLY.** Plan: [VALUE_SEARCH_PLAN.md](VALUE_SEARCH_PLAN.md) ·
Miss set: [VALUE_SEARCH_MISS_SET.md](VALUE_SEARCH_MISS_SET.md) (1321 iter04 misses on the gap≥0.02 pool).
All interventions run on the **iter04** baseline over the same miss set (`data/miss_probe.jsonl`),
net-on-CPU W=16 local. (The laptop was hard-down — swap-death from orphaned workers — so this leg ran
local-only; the conclusions are CPU-bound diagnostics, unaffected by which box.)

## The interventions

| id | knob | what it isolates | bottleneck it would implicate |
|---|---|---|---|
| I0 | baseline NMCTS@200 (rs=0.25, net prior) | reference | — |
| I1 | sims 400 / 800 | does more *neural* search recover h6400's move? | B search budget/horizon |
| I2 | teacher-prior injection at root (softmax(Q/0.03)) | does a *perfect prior* fix the miss? | A policy/exploration |
| I3 | flat (uniform-over-legal) prior | is the prior even load-bearing under this search? | A/D policy relevance |
| I4 | residual-scale 0.0 / 0.5 (vs 0.25) | is the neural value helping / neutral / hurting? | C/D neural-value |
| I5 | classical HeuristicMCTS @200 / @800 (net-free) | is h6400's edge deeper *classical* search, not the net? | F |
| I6 | forced-move child eval (static leaf rank of teacher-child vs nmcts-child) | does the leaf *see* the better continuation? | E value/horizon |
| I7 | endgame-only slice of all the above (filter) | is the live failure endgame-specific? | F endgame |

## I6 — forced-move child evaluation (value/leaf-blindness) — FINAL

For each argmax-miss (NMCTS picked `nmcts_top` ≠ `teacher_best`, n=858), force each move and ask whether
the **static v2.9 leaf** — the value NMCTS bottoms out on — ranks the teacher's resulting child above the
NMCTS-pick's child (root POV). h6400 deep search says the teacher child is better (it's the miss); the
question is whether the *leaf* can see it.

| phase | n | leaf rs=0 ranks teacher-child higher | leaf + 0.25·v_nn |
|---|--:|--:|--:|
| opening | 148 | 40% | 50% |
| midgame | 250 | 30% | 44% |
| late_mid | 86 | 22% | 33% |
| pre_endgame | 150 | 10% | 24% |
| endgame | 224 | 9% | 22% |
| **all** | **858** | **22%** | **34%** |

- The static leaf ranks the decision-relevant continuation **correctly only 22%** of the time on
  argmax-misses — it is **wrong/tied 78%** of the time at the very children that distinguish the move.
  In the **endgame it is wrong 91%** of the time. This is the value/horizon bottleneck made concrete:
  the leaf NMCTS bottoms out on cannot order the continuations of the move in question, worst in the
  endgame (where Path-3 saw the only movement and where "never explored" also peaks).
- The neural residual is **strictly helpful and never corrupts** at 1-ply: it flips **107 wrong→right
  and 0 right→wrong** (net +107), lifting the leaf from 22%→34%. So the learned value head *is* real
  signal on the leaf — but far too weak to close the gap (still wrong 66% overall, 78% in endgame).

This already refutes "neural value corrupts search" (Decision C) at the leaf level and points the
finger at **value representation strength / horizon** (Decision E), not policy and not residual sign.
The remaining legs test whether *search depth* (I1) or *classical search* (I5) overcome the bad leaf,
and whether the prior matters at all (I2/I3).

## I0–I5 root-level comparison (on the iter04 miss set, n=1321)

top1 = searched move == h6400 best; regret = q_best − Q(searched move); fixed-frac = misses flipped to a hit.

| intervention | top1 (=h6400) | mean regret | Δregret vs I0 | eg top1 | eg regret |
|---|--:|--:|--:|--:|--:|
| I0 baseline (net prior, 200 sims, rs=0.25) | 0.350 | 0.0613 | — | 0.460 | 0.0472 |
| I4 rs0 (no neural value) | 0.365 | 0.0611 | −0% | 0.469 | 0.0470 |
| I4 rs0.5 (2× neural value) | 0.357 | 0.0610 | −1% | 0.457 | 0.0473 |
| I1 sims 400 | 0.457 | 0.0482 | −21% | 0.538 | 0.0394 |
| I1 sims 800 | 0.553 | 0.0377 | −39% | 0.619 | 0.0314 |
| I2 teacher-prior inject (root) | 0.637 | 0.0325 | −47% | 0.704 | 0.0230 |
| **I3 flat (uniform) prior** | **0.794** | **0.0134** | **−78%** | 0.799 | 0.0129 |
| **I5 classical h200 (net-free)** | **0.815** | **0.0137** | — | 0.872 | 0.0077 |
| I5 classical h800 (net-free, 4× sims) | 0.899 | 0.0067 | — | 0.941 | 0.0033 |

Reading the matrix:
- **I4 (value): inert at every scale** — rs0 / rs0.25 / rs0.5 all ≈ 0.35–0.37. The neural value head
  does nothing for search. (Kills Decision C value-corrupts AND Decision D value-helps.)
- **I1 (neural search budget): helps, but slowly and inefficiently** — 200→400→800 sims =
  0.350→0.457→0.553. Even 4× the budget only reaches 0.553; the net prior's misdirection is overcome
  by brute search only gradually.
- **I3/I5 (prior): the lever.** Replacing the net prior with *uniform* (0.794) — or dropping the net
  entirely for classical UCB (0.815) — recovers ~80% of the misses at the SAME 200-sim budget. Flat ≈
  classical, so it is the **prior** that hurts, not PUCT-vs-UCB (that accounts for only 0.815−0.794).
- **I2 (teacher-prior at root) < I3 (flat):** injecting the h6400-peaked prior *at the root only* (0.637)
  is worse than uniform (0.794). Mechanism: `best_action` ranks by **backed-up search Q**, not visits;
  a peaked root prior over-commits but the deeper tree still uses net priors and the value-blind leaf,
  so the subtree Q doesn't confirm teacher_best. Broad (uniform) exploration lets the leaf's *aggregate*
  Q rank correctly. This is why a *better prior* (Path-3's repair) was redundant: the issue is not prior
  accuracy, it's prior **concentration**.

## Full-pool CONTROL (the un-confounded test) — gap≥0.02, n=4277 same states

The miss-set legs above are conditioned on iter04 being wrong (flat "helps" almost tautologically). This
re-runs the key agents on the **full** decision-relevant pool — the SAME states iter04's neural NMCTS@200
scored 0.799 on (Stage 1):

| agent @200 sims, v2.9 leaf | top1 (=h6400) | regret | eg top1 | eg regret |
|---|--:|--:|--:|--:|
| neural net-prior (production iter04) | 0.799 | 0.0189 | 0.802 | 0.0173 |
| neural **flat**-prior | 0.867 | 0.0104 | 0.833 | 0.0137 |
| **classical h200 (net-free)** | **0.911** | **0.0070** | 0.933 | 0.0046 |

**Not a miss-set artifact.** On the full pool, flattening the net's *own* prior gains **+6.8pp / −45%
regret**, and dropping the net for classical search gains **+11.2pp / −63% regret**. The ordering
**net < flat < classical** is monotone and large. The trained policy prior is **net-harmful** on
decision-relevant states; the neural value is inert; classical HeuristicMCTS at matched compute is
strictly best and already recovers 91% of the teacher's decisions at 1/32 its budget.
