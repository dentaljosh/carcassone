# Value-ranking architecture swing — build spec (2026-06-17)

> **Status: EXECUTED & CLOSED 2026-06-18 — SWING DISFAVORED.** The Phase-0 kill-test ran
> (`value_ranking/VALUE_RANKING_VERDICT.md`): the spatial-attention head did NOT lift sibling-ranking
> τ over a capacity-matched conv (C−C0 z−0.12), all learned arms ranked ~chance (≤0.029) vs the v2.7
> leaf's 0.579 while the target was reliably rankable ⇒ learned-ranking formulations disfavored (CL-021).
> No production retrain. NEXT = measurement-first (`docs/MEASUREMENT_FIRST_SPEC_2026-06-18.md`). The
> original spec text below is the design that was executed (historical).
>
> _(orig status at authoring: PROPOSED, Phase 0 unrun — Phase 0 **subsequently ran and the spec
> closed 2026-06-18**, verdict in the banner above; stamped 2026-08-29.) Direction chosen by Joshua 2026-06-17 after the
> strength campaign converged (value can't beat the v2.7 leaf; policy washes out at depth —
> STATUS "Right now" + DECISIONS 2026-06-17). This spec REFRAMES "architecture swing" from the
> dead corr-ceiling target to the live τ (sibling-ranking) target, and gates a production retrain
> behind a cheap offline kill-test.

## The reframe (why the obvious version is already dead)

The instinct — "break the 0.47 value-corr ceiling with a board-spanning architecture" — is
**already refuted for corr**, but a sharper version is alive:

1. **corr ceiling is not a sight problem.** `scripts/probe_value_head_c4.py` fed the convnet
   **terminal-ownership oracle channels** (literally leaking the endgame control a GNN would try
   to *infer*) and still hit ~0.47 corr (`+OWN ≈ BLIND ≈ 0.469`). So 0.47 is irreducible *outcome
   variance*, not receptive field. **No architecture breaks the corr ceiling.**
2. **global pooling is also dead.** The `value_global_pool` head (searchval_tree step 2) left
   τ ≈ chance and corr flat 0.84. Global *average* context does nothing.
3. **corr was always the wrong gauge.** The triply-confirmed campaign verdict: a value head with
   corr 0.84 is NOT a usable leaf because it can't **rank siblings** (τ ≈ chance). A leaf needs
   local discrimination (rank the children of a node), not global calibration.

**What was never tried:** a genuinely *relational* board-spanning value head (self-attention /
message-passing — NOT pooling) trained with a **ranking loss**, gauged on **τ**. The hypothesis is
physically motivated: sibling positions differ by one placement whose value is often *board-spanning*
(does this farmer reach a big city cluster across the map?). A local convnet and a global-average
pool both literally cannot compute that pairwise relation → neither can rank the siblings → exactly
the τ ≈ chance we measure.

## The bar (the exact numbers to move)

From `decision_ranking_svtree/summary.json` (convnet iter_00, n=120 nodes, oracle_sims=400):

| ranker | Kendall-τ vs deep oracle | oracle regret (tanh) |
|---|---|---|
| **value-net (convnet, MSE)** | **+0.081 ± 0.023** (≈ chance) | **0.067** (random = 0.079 — barely better than coin-flip) |
| **v2.7 leaf** | **+0.579 ± 0.024** | 0.028 |

The swing must lift the learned head's τ **materially toward v2.7's 0.58** (and regret toward 0.028).
A head that only lifts corr is worthless (proven).

## Phase 0 — offline rankability kill-test (NO production retrain; the gate)

Cheapest-informative-first. Reuses `probe_decision_ranking.py`'s harvest + the τ metric. ~half a day
on one box; bench the harvest cost on a smoke before committing the full run.

**Data:** extend the probe's harvest to dump per-child TRAINING rows — `(child_obs, child_scalars,
child_ownership_oracle, oracle_q, sibling_group_id)` — over ~1.5–2k decision nodes (oracle_sims=400),
held out BY GAME from a ~300-group τ-eval set. (`searchval_tree/iter_00` 400 npz gives the warm net
for harvest; the sibling-Q labels are new.)

**Arms (same data + split; small heads, value-only training):**
| arm | input | head | loss | purpose |
|---|---|---|---|---|
| A | 78 board + scalars | convnet (current) | MSE | reproduce the 0.081 baseline (control) |
| B | 78 board + scalars | convnet | **listwise ranking** | isolate the loss-form effect on τ |
| C | 78 board + scalars | **spatial self-attention** | listwise ranking | **the swing** |
| D (ceiling) | 78 board + **+OWN oracle** | any | listwise ranking | is the sibling-Q rankable AT ALL given ideal sight + the right loss? |

**Gate:**
- **C clears** (τ materially > A/B, heading to ~0.3+ and ideally → 0.58) → the relational arch is the
  missing piece → Phase 1 (production retrain).
- **C flat but D clears** → target is rankable but our learnable arch can't reach it → try the heavier
  GNN-over-feature-graph before concluding.
- **D flat** → sibling-Q is not rankable from a per-position scalar regardless of sight/loss → the
  whole value-as-leaf program is structurally capped → **swing dead, fall back to measurement-first**
  (the other fork: honest-info engine + external/human ruler).

Report each arm's held-out τ ± SE. Discovery ≠ confirmation — a green C gets a second seed/split before
Phase 1.

## Phase 1 — production integration (ONLY if Phase 0 green)

- Fold the relational value head into `CarcassonneNet` (plugs in after the trunk at the
  `_value_forward` seam, `network.py:~131`; keep policy head unchanged).
- Train it in the **residual-leaf framing** (`v2.7 + 0.25·Δ`) — the ONLY value config that ever showed
  a positive marginal (+46.5 z=2.29, survives the heur@800 odometer). The swing's win condition is that
  the residual marginal **grows** past the static +45 and/or the head clears a higher blend λ.
- Gauge on the **leaf** (marginal-vs-scale0 + heur@800 odometer), NOT corr. One batched warmstart→
  self-play→train→ladder cycle (one-retrain discipline). n=400 paired on the clean ruler.

## Kill criteria / honesty
- Phase 0 is the gate; do not retrain on a red or ambiguous Phase 0.
- τ, not corr, is the verdict at every stage (corr is a known liar here).
- If Phase 0 kills it, that is a *real result* — it bounds the value-as-leaf program — and the next
  move is the measurement-first fork (DECISIONS:381 next rungs), not another value variant.
