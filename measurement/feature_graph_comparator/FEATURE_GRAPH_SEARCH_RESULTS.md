# Feature-Graph Comparator — STAGE 5 SEARCH SCREEN

_generated 2026-06-28 18:09 · net-free · frozen v2.9 leaf (hash 7fc930b82801cb43) · HeuristicMCTS(sims=200) · 30 workers · 41s_

Roots: **596** = decisive-tail **196** (all) + ordinary **400** (random of 1313). TEST split only (no leakage; same `eval_lib.seed_split` as offline).

> b99c9ed caveat in force: root sibling-ranking is a **screen, not strength**. This stage asks only whether the offline comparator win survives / fills room left by MCSearch — NOT whether to replace the v2.9 leaf.

## Selected-move teacher regret + top1 — mode × slice

| slice | n | leaf_only reg / top1 | comparator_only reg / top1 | search_leaf reg / top1 |
|---|---|---|---|---|
| overall | 596 | 0.04968 / 0.3658 | 0.02892 / 0.5201 | 0.00839 / 0.6326 |
| decisive | 196 | 0.12209 / 0.1837 | 0.07491 / 0.4847 | 0.01946 / 0.7908 |
| ordinary | 400 | 0.0142 / 0.455 | 0.00638 / 0.5375 | 0.00296 / 0.555 |
| phase:opening | 78 | 0.07384 / 0.4359 | 0.04458 / 0.5769 | 0.01717 / 0.6538 |
| phase:midgame | 143 | 0.08939 / 0.3357 | 0.06048 / 0.4406 | 0.01215 / 0.6434 |
| phase:late_mid | 66 | 0.02615 / 0.4242 | 0.00568 / 0.6667 | 0.00273 / 0.6818 |
| phase:pre_endgame | 129 | 0.02787 / 0.3721 | 0.01208 / 0.5581 | 0.00294 / 0.6667 |
| phase:endgame | 180 | 0.03192 / 0.3333 | 0.01764 / 0.4778 | 0.00757 / 0.5722 |

## search_blend[α,k] selected-move regret (top1 in parens)

| α\|k | overall | decisive | ordinary |
|---|---|---|---|
| 0.05|2 | 0.00855 (0.6376) | 0.02002 (0.7857) | 0.00292 (0.565) |
| 0.05|3 | 0.00892 (0.6359) | 0.02002 (0.7857) | 0.00348 (0.5625) |
| 0.05|9999 | 0.00885 (0.6342) | 0.01954 (0.7959) | 0.00362 (0.555) |
| 0.0|2 | 0.00839 (0.6326) | 0.01946 (0.7908) | 0.00296 (0.555) |
| 0.0|3 | 0.00839 (0.6326) | 0.01946 (0.7908) | 0.00296 (0.555) |
| 0.0|9999 | 0.00839 (0.6326) | 0.01946 (0.7908) | 0.00296 (0.555) |
| 0.1|2 | 0.0086 (0.6342) | 0.02018 (0.7806) | 0.00292 (0.5625) |
| 0.1|3 | 0.00897 (0.6326) | 0.02018 (0.7806) | 0.00348 (0.56) |
| 0.1|9999 | 0.00891 (0.6309) | 0.0197 (0.7908) | 0.00362 (0.5525) |
| 0.25|2 | 0.00905 (0.6326) | 0.02149 (0.7755) | 0.00295 (0.5625) |
| 0.25|3 | 0.00942 (0.6309) | 0.02149 (0.7755) | 0.0035 (0.56) |
| 0.25|9999 | 0.00936 (0.6275) | 0.021 (0.7857) | 0.00365 (0.55) |

## search_blend_gated[α] selected-move regret (top1 in parens)

| α | overall | decisive | ordinary |
|---|---|---|---|
| 0.1 | 0.00877 (0.6309) | 0.02063 (0.7857) | 0.00296 (0.555) |
| 0.25 | 0.0092 (0.6292) | 0.02193 (0.7806) | 0.00296 (0.555) |

## Visit share & backed-up Q on the TEACHER child

| slice | visit_share_on_teacher | backed_up_Q_teacher | teacher_explored_frac |
|---|---|---|---|
| overall | 0.0481 | 0.1459 | 1.0 |
| decisive | 0.0535 | 0.1255 | 1.0 |
| ordinary | 0.0454 | 0.1558 | 1.0 |

## Explored-but-misranked FIXED by blend (decisive roots)

_eligible = decisive AND search explored teacher child (N>0) AND search_leaf picked a different child._

| α\|k | fixed / eligible | frac |
|---|---|---|
| 0.05|2 | 1 / 41 | 0.0244 |
| 0.05|3 | 1 / 41 | 0.0244 |
| 0.05|9999 | 3 / 41 | 0.0732 |
| 0.0|2 | 0 / 41 | 0.0 |
| 0.0|3 | 0 / 41 | 0.0 |
| 0.0|9999 | 0 / 41 | 0.0 |
| 0.1|2 | 1 / 41 | 0.0244 |
| 0.1|3 | 1 / 41 | 0.0244 |
| 0.1|9999 | 3 / 41 | 0.0732 |
| 0.25|2 | 1 / 41 | 0.0244 |
| 0.25|3 | 1 / 41 | 0.0244 |
| 0.25|9999 | 3 / 41 | 0.0732 |

## Does any blend BEAT search_leaf on decisive regret without ordinary regression?

- search_leaf regret: overall **0.00839**, decisive **0.01946**, ordinary **0.00296**.
- **Verdict: NO** — no α>0 blend beats search_leaf on decisive regret without ordinary regression.
- best **α>0 search_blend** = `0.05|9999`: decisive regret **0.01954** (Δ vs search_leaf +0.00008, +0.4%); ordinary regret 0.00362 (search_leaf ord 0.00296); no_ord_regression=**False**.
- best **search_blend_gated** = `α=0.1`: decisive regret **0.02063** (Δ +0.00117); ordinary 0.00296; no_ord_regression=**True**.

## Built-in sanity asserts

1. `search_blend[α=0,k=all] == search_leaf` (identical selections): **PASS** (mismatches=0).
2. mean search_leaf regret ≤ mean leaf_only regret on decisive tail: **PASS** (search_leaf 0.01946 vs leaf_only 0.12209).
3. comparator_only top1 over FULL TEST ≈ 0.52–0.54 (reproduces offline ridge_pointwise[all]): **PASS** (full-TEST 0.5335; subset overall 0.5201).
