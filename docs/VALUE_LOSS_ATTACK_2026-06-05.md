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

#### STEP A — RESULT (2026-06-05): ✅ CONFIRMED, even starker than predicted
Built `scripts/probe_decision_ranking.py` (parallel CPU; net on CPU per worker
→ no fork+CUDA crash). On-distribution decision positions (real v2.7-leaf
self-play), each legal move's child scored 3 ways from the decision-maker's POV;
**oracle = a deep `oracle_sims=400` v2.7-leaf search from each child** (the
move's converged value). `searchval_tree/ckpt/iter_00.pt`, **n=120 nodes, mean
k=13.8** (`/mnt/c/carc-shared/decision_ranking_svtree/summary.json`):

| ranker | Kendall-τ vs oracle | top-1 = oracle-best | oracle regret (pts) |
|---|---|---|---|
| **value-net (corr 0.84)** | **+0.081 ± 0.023** | 0.150 | **1.92** |
| **v2.7** | **+0.579 ± 0.024** | 0.442 | **0.62** |
| random baseline | ~0 | ~0.07 (1/k) | (0.079 tanh) |

The corr-0.84 value head ranks sibling moves at **essentially chance** — τ=0.08
(≈22 SE below v2.7), top-1 barely above 1/k, and its oracle regret (0.0675 tanh)
is **barely better than picking at random** (0.0794). v2.7 ranks them well
(τ=0.58, 3× lower regret). The two rankers barely agree (τ_net,v2.7 = 0.10).
**→ a 0.84-outcome-corr value has near-ZERO local move-discrimination. The LOSS
is the problem; corr is definitively the wrong gauge.**

Methodology notes that mattered: (a) **oracle DEPTH is load-bearing** — a shallow
oracle (sims=60) ≈ 1-ply v2.7 (circular) and *understated* the gap (net τ 0.48);
deepening to 400 collapsed net τ → 0.08 while v2.7 held ~0.58. (b) the v2.7
column is mildly inflated by construction (oracle uses the v2.7 leaf), but the
DECISIVE signal — net regret ≈ random, net τ ≈ 0 — is construction-independent,
and the oracle-Q is literally what `search_value_tree` *trained* the head on.

**⚠️ Caveat carried into STEP B:** the 1-ply regret gap (1.9 vs 0.6 pts) is real
but *smaller* than the λ1.0 = −576 crater → that crater is ALSO error-compounding
at depth + off-distribution (search drives into the net's blind spots), which a
1-ply probe can't capture. So **STEP B's realistic target is the λ0.5 ≥ 0 gate**
(where v2.7 still anchors local consistency at 50%), NOT necessarily fixing λ1.0.
A value that ranks siblings like v2.7/deep-search should move λ0.5 across 0; the
pure-NN-leaf cliff is a separate (flywheel) problem.

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

## NEXT action — STEP A is ✅ DONE & CONFIRMED → build STEP B
STEP A (`scripts/probe_decision_ranking.py`, committed `98364bd`) decisively
confirmed the diagnosis (value-net sibling-ranking τ=0.08 ≈ chance vs v2.7 0.58;
see "STEP A — RESULT" above). The cheap gate passed → the value LOSS is the
problem.

**STEP B build (the ranking-loss retrain) — concrete plumbing:**
1. **Sibling-set harvest in self-play** (the main cost). New MCTS method
   `interior_sibling_groups(root_board, *, min_parent_visits, min_child_visits,
   max_groups)` → for each well-visited interior PARENT (board recorded via
   `record_boards`), emit its visited children as a group: `(child_board,
   child_player, child_Q)` with child_Q flipped to the PARENT's POV
   (`child.Q if child.player_to_move==parent.player_to_move else -child.Q`).
   `selfplay.py` accumulates these as value-only rows tagged with a `group_id`
   (contiguous per node); add `group_id: np.ndarray|None` to `GameDataset`
   (mirrors the `aux_mask` add) + npz save/load + `make_streaming_dataset` 8th
   tuple element. Group rows are aux_mask=False (value-only; no policy/ownership).
2. **Listwise ranking loss** within groups (the doc's primary): segment-softmax
   over each group's child value outputs → cross-entropy vs the softmax of the
   group's child search-Q (a temperature τ_rank to tune). Implement via a
   batch collate that keeps whole groups together (pack "N groups/batch"; segment
   the loss by `group_id` offsets) — avoids the centered-MSE's loss-of-absolute-
   scale problem. **Multi-task:** keep the existing value-MSE (absolute scale for
   backup) + α·listwise term; sweep α. (Pairwise-margin is the fallback if
   listwise is finicky.)
3. **Re-eval the λ-curve** vs HeuristicMCTS@200, n≥100 paired. **SUCCESS = λ0.5 ≥ 0.**
   Cheaper de-risk first: a value head trained to *mimic v2.7* (target =
   tanh(vs2/15)) should recover τ≈0.58 + λ0.5≥0 — proves the head CAN represent a
   good ranker before spending the full in-loop ranking harvest (needs v2.7 target
   stored at gen time; simpler than sibling grouping).
⚠️ remotes are STALE (`e4a77ed`) — bundle-sync before any 3-box harvest run.
