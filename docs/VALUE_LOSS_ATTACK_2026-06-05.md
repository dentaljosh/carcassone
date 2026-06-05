# Attack the value LOSS — decision-ranking, not outcome-MSE (2026-06-05)

**Decision (Joshua, 2026-06-05):** after step 1 (interior targets) and step 2
(global pooling) both failed to make the learned value a usable MCTS leaf,
attack the **value loss / objective**, not more data or architecture.

## The diagnosis (TRIPLY confirmed)
A learned value with **outcome-corr 0.84** is *not* a usable search leaf. Blending
it into the v2.7 leaf degrades strength MONOTONICALLY, and three independent value
nets give the same curve (vs HeuristicMCTS@200, n=100 paired):

| net | held-out corr | λ0 | λ0.5 | λ1.0 |
|---|---|---|---|---|
| outcome head (iter_01) | 0.29 | +96 | −123 | — |
| search_value trajectory | 0.46 | (+96) | −37 | −576 |
| **search_value_tree (interior)** | **0.84** | +56 | −24 | −576 |
| **+ global pooling (step 2)** | **0.84** | ~+56 | **−38** | −552 |

corr nearly **tripled** (0.29→0.84) while value-in-leaf stayed a ~80–120-elo
liability. **The corr metric is the wrong gauge** (regroup's core lesson) — and
neither label scarcity (step 1) nor board-wide context (step 2) is the bottleneck.

## The hypothesis
A leaf eval needs to **rank sibling positions** correctly (relative ordering of
the moves out of a node) — NOT predict the absolute final outcome. Outcome/Q-MSE
rewards global calibration; it does nothing for *local discrimination* among
nearby positions. v2.7 (corr 0.61) is a hand-crafted positional eval that's
**locally consistent**, so it ranks siblings well → a good leaf. The learned
value is globally calibrated but locally noisy → a bad leaf. **The loss optimizes
the wrong objective.**

## Plan — cheapest-first, GATED

### STEP A — offline decision-ranking PROBE (the gate; ~1–2 hr, NO training)
Confirm the diagnosis before any retrain (the C4a/C6 cheap-probe discipline).
- Harvest a small set of **decision nodes with their sibling sets**: per node,
  the children's `(encoded board, search Q [oracle], v2.7 leaf value)`. (New: the
  npz stores positions but not sibling groups / states — needs a focused
  instrumented self-play harvest, ~extend `interior_value_targets` to emit
  parent→children with Q + v2.7. ~quick generation, a few hundred nodes.)
- For each node, rank the children by: **value-net**, **v2.7**, vs the **search-Q
  oracle**. Metrics: Kendall-τ, top-1 agreement, and **oracle regret** (search-Q
  of the value-picked move vs the search-best move).
- **PREDICTION:** value-net move-ranking τ is LOW (poor) despite corr 0.84, AND
  v2.7's τ is HIGH. → confirms "loss is the problem" → do step B.
  If value-net ranking is actually GOOD → the leaf failure is elsewhere; rethink
  before spending the retrain.

### STEP B — ranking-loss retrain (only if A confirms)
Add a **sibling-ranking loss**: train the value so its ordering of a node's
children matches the search-Q ordering. Concretely (pick/compose):
- **Listwise:** softmax over the node's child value-logits → cross-entropy vs the
  search-Q softmax (or visit-count distribution). Directly trains decision-ranking.
- **Pairwise margin:** for child pairs, `max(0, m − (v_i − v_j)·sign(Q_i−Q_j))`.
- Likely **multi-task** with a small MSE term (keep absolute scale sane).
Needs sibling-set harvesting in production self-play (parent → children boards +
search Q) — the main plumbing cost (step-1-scale). Re-eval the λ-curve.
**SUCCESS = λ0.5 crosses ≥ 0** (value finally an asset in the blend).

### Cheaper variants to consider (if ranking-loss plumbing is heavy)
- **predict-v2.7 + residual:** target = v2.7_value + learned residual → inherits
  v2.7's local consistency by construction.
- **per-node-centered MSE:** subtract the node's mean child-Q from each target →
  the value fits *relative* sibling differences, not absolute level. (Still needs
  sibling grouping.)

## If this ALSO fails
Then the learned value genuinely can't beat the v2.7 leaf with our resources
(quadruply confirmed) → the v2.7-leaf ceiling is real; pivot to measurement / a
fundamentally different approach (e.g. learn a *better hand-feature* leaf, or
accept ~strong-amateur+ and revisit the goal). Record honestly.

## FIRST action (post-compaction)
Build STEP A (the offline decision-ranking probe): the sibling-set harvest +
the τ/regret comparison (value-net vs v2.7 vs search-Q oracle). It's the cheap
gate that tells us if the loss is really the problem before any retrain.
