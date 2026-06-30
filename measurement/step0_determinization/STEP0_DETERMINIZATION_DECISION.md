# Step 0 — Value-target hygiene: DECISION

**Date:** 2026-06-29 · **Charter:** superhuman program §6.1 + §7 Step 0 · **Status:** CONCLUDED → proceed to Step 1
**Scripts:** `scripts/step0_determinization/det_probe.py` · **Data:** `measurement/step0_determinization/det_probe_full.{json,_arrays.npz}` · **MEASUREMENT ONLY** — champion / PRODUCTION.yaml / leaf untouched.

## Verdict (BLUF)

Value-target hygiene is **not the binding constraint on the value head.** Both halves of Step 0 clear:
1. **§6.1 POV sign convention — CLEAN.** The value *training* target is POV-consistent at the same-player TILES→MEEPLE boundary. The known `forced_move.py` sign-flip is **diagnostic-only** (the I6 leg of CL-032) and does not touch training.
2. **Determinization (clairvoyant single-future) noise — REAL but SECONDARY.** ~1/3 of a single-determinization target's variance is irreducible deck noise, but the value head fails **far below** the ceiling that noise imposes → noise is not what's holding it back.

→ **Proceed to Step 1 (the representation gate) as the primary lever.** Step 4 (fair-information / determinization-averaged targets) is confirmed a *real* secondary lever (not a null), with payoff concentrated in the opening — pull it forward only if Step 1/2 show a positive signal.

## §6.1 — POV sign audit (code trace, no compute)

The MCTS uses a **`player_to_move`-keyed** sign convention everywhere — it flips child value *only when the players differ* (`q = child.Q if child.player_to_move == root.player_to_move else -child.Q`, `mcts.py:145/189/763`; backup `mcts.py:231`), not a blind negate-every-edge. The interior/sibling target harvesters return `(board, player_to_move, Q)` paired with `get_canonical_form(board, player_to_move)` and explicitly note *"all children of a node share one player-to-move (Carcassonne splits tile vs meeple actions), so own-POV Q IS the ordering … no per-child flip"* (`mcts.py:719`). The outcome target keys its sign on the recorded `cur_player` (`selfplay.py:466`), not a flip-assumption. **No same-player mis-sign exists in training.** The `forced_move.py:_child_root_pov` `L0=-h` bug is confined to the CL-032 I6 diagnostic; if fixed it makes the leaf look *more* correct → reinforces (not overturns) the value-inert finding. CL-033's α=0 is `forced_move`-independent.

## Step 0(b) — determinization probe (local, N=1600, 320/phase, K=8)

Method: sample roots from the 10,067 h6400_v2.9 sets; per root play K=8 reshuffled-deck determinizations (fixed greedy `RuleBasedPlayer`, fixed tiebreak) to terminal → POV value `tanh((s_pov−s_opp)/15)`. SINGLE target = one determinization; AVG = mean over K.

**Variance decomposition:**
| quantity | value |
|---|---|
| between-root Var(avg) — predictable signal | 0.379 |
| mean within-root Var — irreducible deck noise | 0.191 |
| **noise / (signal+noise)** | **0.335** |
| **corr ceiling for a SINGLE-target value head** | **0.815** |
| corr(single, avg) | 0.834 |

**Per-phase within-root (deck) noise — strongly phase-dependent:**
| phase | within (deck noise) | between (signal) |
|---|---|---|
| opening | **0.436** (dominant) | 0.153 |
| midgame | 0.286 | 0.279 |
| late_mid | 0.153 | 0.412 |
| pre_endgame | 0.069 | 0.504 |
| endgame | **0.0125** (negligible) | 0.547 |

**Train-two-heads** (small ValCNN, 78-ch blind input, scored vs the held-out AVG target, 3 seeds):
| target | held-out corr | held-out MSE |
|---|---|---|
| SINGLE | +0.578 ± 0.038 | 0.370 ± 0.092 |
| AVG | **+0.650 ± 0.007** | **0.250 ± 0.002** |

## Interpretation

- **Not the binding constraint.** The production value head's known held-out corr is ~0.32 (2026-06-04) to ~0.45 — **far below** the 0.815 ceiling that single-determinization noise alone imposes. If target noise were the cause, the head would sit near 0.815. It doesn't → the inertness is **representation / overfitting**, not target noise. This is consistent with §6.1 also being clean, and it is exactly the charter's thesis: the **representation (Step 1)** is the remaining untested lever.
- **Averaging helps — modestly, and opening-concentrated.** Training on K-averaged targets lifts the small-CNN corr +0.072 (0.578→0.650), cuts MSE ~32%, and ~6× tightens seed variance. The deck noise it removes lives almost entirely in the **opening** (within 0.436) and is ~zero by the **endgame** (0.0125). So fair-information targets (Step 4) are a *real* lever with an opening-phase payoff — but secondary to representation.

## Caveats

- Playout policy is greedy `RuleBasedPlayer` (a proxy; the production value target is sims=200 self-play / search root.Q). The **within/between ratio** is the diagnostic, not absolute values; if Step 4 is pursued, re-measure with h200 playouts on a subset.
- **Laptop replication (N=1000, disjoint roots, seed 777, `--no-train`) — CONFIRMS the local result** on an independent root sample: noise fraction **0.357** (local 0.335), corr ceiling **0.802** (local 0.815), opening within-var **0.463** (local 0.436), endgame within-var **0.014** (local 0.013). Same opening-dominated / endgame-negligible structure, same secondary-not-binding magnitude. Verdict robust across boxes.

## Next

**Step 1** — build live farm-connectivity + bag-composition (+ open-edge) **input planes**, re-run the CL-033 sibling-ranking test on the 10,067 h6400_v2.9 sets. The gate is **offline / local / Python-only** (no orch, no Cython port, no warmstart); the production plumbing (Cython `flat_repr_cy` port, shm/Rust layout, full warmstart) is deferred to Step 2, contingent on the gate passing. Governance: register as **CL-037** on close.
