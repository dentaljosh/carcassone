# FGSR_TRAINING.md — Training Objectives

> **STATUS: ⏳ PENDING — Stage 5, NOT STARTED (gated).**
>
> _Stub created 2026-06-29._

## Plan (not yet executed)

Train against **post-search residual** targets. Reuse `scripts/feature_graph/run_offline.py`
(ridge / MLP early-stop on val regret) + `scripts/post_search_residual/run_adaptive_gate.py`.

Objectives (positives weighted by regret; **do not** optimize generic accuracy):
1. **Escalation classification** — predict strong/medium h200 failure (G3).
2. **Regret regression** — predict `regret(h200)` vs h6400.
3. **Top-k reranking** — among h200 top-k explored children, predict h6400-preferred (G4).
4. **Pairwise high-gap ranking** — compare candidate actions by h6400 Q diff, only
   where `q_gap_6400` is meaningful.
5. **Adaptive-compute utility loss** — directly optimize expected regret removed per
   extra sim (if cheap to implement).

**Centered metrics:** regret captured · regret removed per compute ·
adaptive matched-compute performance — **not** accuracy/τ.

**To be recorded here when run:** loss curves, early-stop selections, the val-regret
metric each model was selected on.
