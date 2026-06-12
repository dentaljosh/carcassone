# Attack the value LOSS — decision-ranking, not outcome-MSE (2026-06-05)

> **Status: COMPLETE** — see the OUTCOME closing addendum at the bottom (Lever 1 WON → residual →
> attempt-2 → production iter8).

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

## STEP B.0 — mimic-v2.7 RESULT (2026-06-05): the de-risk that became the proof
Before the full ranking-loss plumbing, the cheap de-risk (`value_target=v2_7`,
commit `a7691e4`): train a head to predict the **v2.7 LEAF VALUE** tanh(vs2/15) —
the OPTIMAL target (v2.7 itself ranks siblings at τ=0.60). If MSE-on-v2.7
recovers τ + clears λ0.5, the original problem was the *target*; if it ALSO ranks
at chance, the problem is the *loss form*. 3-box gen (400 games, warm iter_01,
vlw=1.0) → train → re-probe + λ-curve (`mimic_v27/`, results.csv `mimic_v27_*`):

| head | trained on | global fit | **sibling τ** | λ0 | λ0.5 | λ1.0 |
|---|---|---|---|---|---|---|
| searchval_tree | deep search-Q | corr 0.84 | 0.081 | +56 | −24 | −576 |
| **mimic-v2.7** | **v2.7 leaf value** | **corr 0.86** | **0.088** | +3.5* | **−38** | **−604** |
| v2.7 (reference) | — | — | 0.598 | — | — | — |

**The head fit v2.7 globally (corr 0.86) yet ranks siblings at τ=0.088 — chance,
identical to the search-Q head, and barely agrees with v2.7 it was trained to
copy (τ_net,v2.7=0.14).** Same λ-curve failure (λ0.5=−38, λ1.0 craters). (*λ0
+3.5 is the n=100 gate at seed 500000, ~1.5σ below searchval's +56 — noise; the
games are near-identical across runs. The decisive, low-noise signal is τ.)

**VERDICT (the proof): MSE regression cannot produce a sibling-ranker REGARDLESS
of target.** Even handed the optimal target it fits global variance but ranks
locally at chance — the within-node Q differences that decide a move are swamped
by the head's approximation error. → **the LOSS FORM is the problem, not the
target → the ranking loss (STEP B.1) is MANDATORY, not optional.** (Quadruply
confirms value-as-leaf failure; first to isolate the cause to the loss form.)

## NEXT action — STEP A ✅ + STEP B.0 ✅ → build STEP B.1 (the ranking loss)
STEP A confirmed the value head ranks at chance; STEP B.0 proved MSE can't fix it
on ANY target. The ranking loss is now the designated (and last clean) lever.

**STEP B.1 build (the ranking-loss retrain) — concrete plumbing:**
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
   (The mimic-v2.7 de-risk above is the control: MSE on the optimal target gave
   τ=chance, so any τ-recovery from the ranking loss is attributable to the loss
   form. If the ranking loss ALSO leaves τ low / λ0.5<0 → "If this ALSO fails".)

Design note (resolved 2026-06-05): all of a node's children share one
current_player (Carcassonne splits tile vs meeple actions → a node's legal moves
are one phase), so the harvest is the **existing search_value_tree interior
harvest + a `group_id` tag** (encode child from its own POV, target = own-POV Q,
value-only row); head outputs within a group are directly comparable and ranking
by own-POV Q matches leaf use. The real work is the **batch-grouped listwise
loss** in train_iter (keep whole groups in a batch; segment-softmax by group_id).
⚠️ remotes were synced to `a7691e4` for STEP B.0; re-bundle-sync after new commits
before any 3-box harvest run.

## STEP B.1 — RESULT (2026-06-05 Shabbos sweep): helps but INSUFFICIENT
Built (`369677f`) + swept (`88a5b5e`, `scripts/rank_sweep.sh` over α∈{.5,1,3}×τ∈{.1,.3},
each train + λ-curve n=200 vs HeuristicMCTS@200; output `/mnt/c/carc-shared/rank_sweep`,
verdict via `scripts/rank_sweep_summary.py`). **Read the MARGINAL (λ0.5 − λ0), not
absolute λ0.5** — absolute is confounded by the policy baseline (λ0 ≈ +70 here;
the rank_data α=0 baseline gated +74). The value head is an ASSET only if
marginal ≥ ~0.

| head/config | λ0 | λ0.5 | **marginal** | note |
|---|---|---|---|---|
| searchval (MSE) | +56 | −24 | **−80** | step-1 |
| GP (MSE) | +56 | −38 | **−94** | step-2 |
| **a05t01 (rank α=.5)** | +64 | +6.9 | **−67** | only COMPLETE config |
| a10t01 / a30t03 (rank) | +63/+69 | partial+noisy | (TBD) | n<80, swinging |

**Verdict: the ranking loss HELPS (best marginal −67 beats pure-MSE −80/−94; the
λ1.0 pure-NN-leaf crater shrank to −356 vs −576/−604) but does NOT make the value
an asset** — no config reached marginal ≥ 0. (⚠️ an early "+6.9 clears the gate"
call was RETRACTED — within noise of 0 AND policy-confounded; the marginal is what
matters.) Final numbers when the sweep's n=200 evals complete (~4-5am).

## NEXT — the 4-lever auto-sequencer (Joshua, 2026-06-05 pm)
The ranking-loss sweep tuned ONE lever (α×τ of the listwise loss). It helped but
fell short → **design all 4 genuinely-different levers and wire them to run
SEQUENTIALLY + automatically** (a multi-lever runner: gen→train→λ-curve per lever,
judged on the **marginal λ0.5−λ0 ≥ 0** gate, early-stop on a winner, resumable like
`rank_sweep.sh`). Levers:

1. **predict-v2.7 + residual.** Value head outputs a residual Δ; the leaf uses
   `v2.7 + Δ` → inherits v2.7's local consistency BY CONSTRUCTION (so it ranks
   siblings ≥ v2.7) and can exceed it via Δ. Build: a new leaf mode in
   `evaluators.make_v25_value_wrapper` (`leaf = tanh(vs2/15) + scale·v_nn` instead
   of a blend), and a Δ target = (search-Q − v2.7) at each position (store v2.7 at
   gen time, like the `v2_7` mode; train value-MSE on the residual). Cheapest /
   most likely to clear the gate.
2. **per-node-centered targets.** Subtract the node-mean child-Q from each group
   row's target → the value fits RELATIVE sibling differences directly. Reuse the
   `group_id` harvest (group_id → node membership → node mean). Multi-task with the
   absolute-Q MSE so backup keeps a sane scale. A different loss than listwise.
3. **in-loop flywheel.** Take the best value net (from levers 1-3) and use it as a
   λ-leaf (e.g. λ=0.5) in NEW self-play, retrain on that self-play's search data,
   ITERATE — value+search co-adapt (KataGo; the regroup's #1 rec; the one thing the
   one-shot sweep can't test). `STAGE_B_BLEND`/`STAGE_B_BLEND_CONST` in
   `run_pathb_cluster_loop.sh` already do value-blend-in-self-play; wire the
   value_target + a keep-best-on-marginal gate.
4. **measurement / accept the ceiling.** If 1-3 all fail, the v2.7-leaf ceiling is
   real (now ~6× confirmed) → build the non-saturated odometer (asymmetric-compute
   ladder `scripts/ladder_asymmetric.py` = rung 1; + diverse non-v2.7 opponents +
   deck-paired cross-play) to measure absolute strength, OR pursue a fundamentally
   different leaf (better hand-features), OR accept ~strong-human and revisit the
   goal. (Not an auto-run experiment like 1-3; a branch/decision.)

**Sequencer design (to flesh out post-compaction):** one driver that runs levers
1→2→3 as stages (each = its own gen [if needed] + train + λ-curve), writes
results.csv + manifests, gates each on marginal≥0, and stops/flags when one clears
(then hand to the flywheel). Lever 4 is the fallback branch if all fall short.

## BUILT (2026-06-05): all 4 levers + the auto-sequencer
The B.1 ranking-loss sweep's final verdict: **value still HURTS** — best marginal
≈ −51 (a10t01), every config negative; the a30t03 "+12.4 @ n=48" spike decayed to
−88 @ n=88 (the predicted noise-decay). So all 4 levers were built:

- **Lever 1 — predict-v2.7 + residual** (`44100a9`). `LeafConfig.residual_scale` +
  `CARCASSONNE_V25_RESIDUAL_SCALE`; both leaf wrappers do `clip(tanh(vs2/15) +
  scale·v_nn, ±1)` (precedence over blend). `selfplay value_target="residual"`:
  trajectory + interior rows store Δ = root.Q − v2.7 leaf value (ungrouped, plain
  MSE). Eval needs no change — the wrapper reads the env-built DEFAULT_CONFIG, so
  the scale-curve is driven by the env var (mirrors the blend λ-curve). The leaf
  inherits v2.7's sibling-ranking BY CONSTRUCTION → its marginal can't crater like
  pure-NN-leaf; **highest-EV / most-likely to clear the gate.**
- **Lever 2 — per-node-centered MSE** (`d2a6a53`). `train_iter --center-weight β`:
  `centered_group_mse` subtracts the group mean from BOTH pred and target then MSEs
  the residuals — fits within-node relative sibling-Q differences while the plain
  value-MSE keeps absolute scale (multi-task). **Reuses the existing rank_data
  group_id harvest → NO new gen.** A regression objective for the same goal B.1's
  listwise ranking loss attacks.
- **Sequencer + summary** (`2340842`). `scripts/lever_sequencer.sh`: self-contained,
  single-box, RESUMABLE (per-stage `.done`; eval self-caches). L1 = residual gen
  (`GEN_GAMES`, default 300) + train + scale-curve {0,0.25,0.5}; L2 = retrain
  rank_data --center-weight + λ-curve {0,0.5,1.0}. `scripts/lever_summary.py`
  reports each lever's **marginal ± σ + z** (a low-n point ≥0 is NOT a win) and
  writes `VERDICT.txt` (WINNER=l1|l2|none).
- **Lever 3 (flywheel) hand-off** + **Lever 4 branch** are the sequencer's final
  stage: on a CONFIDENT winner it prints (or with `FLYWHEEL_ON_WIN=1` launches)
  `run_pathb_cluster_loop STAGE_B_BLEND` seeded with the winning net+value_target —
  guarded OFF by default (a multi-hour 3-box run wants a human OK on the marginal).
  If no lever clears → it flags the Lever 4 measurement / accept-ceiling decision.
  ⚠️ **Known gap — the printed l1 flywheel command is mechanism-mismatched:** for
  Lever 2 (centered, value head ≈ Q) `STAGE_B_BLEND=1` (the value_blend ramp) is
  correct, but Lever 1's head predicts Δ and its leaf is `v2.7 + scale·Δ` — the
  residual mode, NOT the blend. `run_pathb_cluster_loop` only ramps `--value-blend`,
  so an l1 flywheel needs self-play run with `CARCASSONNE_V25_RESIDUAL_SCALE` set
  (residual leaf takes precedence over blend) + `value_target=residual`, and the
  per-iter gate (currently value_blend=0) wouldn't capture the residual leaf's
  contribution. So if **Lever 1** wins, wire the residual-scale-in-self-play path
  before flywheeling (hand-craft the launch); the printed STAGE_B_BLEND line is a
  placeholder for l1. l2's printed command is correct as-is.

**To run** (when the cluster frees — the B.1 sweep holds it ~till it finishes):
`SHARE=/mnt/c/carc-shared nohup nice -n 19 bash scripts/lever_sequencer.sh >
/tmp/lever_seq.log 2>&1 & disown`. Prereqs verified present: WARM
`stage_b/ckpt/iter_01.pt`, `rank_data/iter_00`, `data/warmstart/heuristic_tau05`.
Rough ETA single-box 5800x: L1 gen ~35m + L1 train ~22m + L1 eval ~15m + L2 train
~22m + L2 eval ~15m ≈ **~1h50m**.

---

## OUTCOME (closing addendum, 2026-06-12)

The sequencer ran 2026-06-06. **Lever 1 (predict v2.7 + residual Δ) WON** — the first
asset-positive learned value (+46.5 pooled, z=2.29; later resolved cleanly as the +37.6/z=2.98
PROTOCOL_001 marginal). That residual net became the seed of the flywheel attempts →
[ATTEMPT2_SPEC_2026-06-08.md](ATTEMPT2_SPEC_2026-06-08.md) (champion iter8, production
2026-06-11) → [DEEPER_TEACHER_SPEC_2026-06-11.md](DEEPER_TEACHER_SPEC_2026-06-11.md) (live).
See DECISIONS 2026-06-06/07.
