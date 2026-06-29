# FGSR_OFFLINE_RESULTS.md — Offline Gate (CRITICAL)

> **STATUS: ⏳ PENDING — Stage 6, NOT STARTED. This is the critical gate.**
>
> _Stub created 2026-06-29._

## The gate (not yet run)

The graph model must **beat `low_top2gap` AND the prior 32-feature MLP at matched
compute** — not merely beat the static leaf — with:
- bootstrap CI not crossing zero,
- on held-out roots,
- on ≥1 source/phase robustness split (not just the random split),
- suggested threshold: **≥10–20 % tail-regret reduction over `low_top2gap`**, or a
  materially better compute-efficiency curve.

**Simulation:** run h200 first → model predicts danger/residual → escalate to
h800/h3200 if triggered, else keep h200. Matched average compute C ∈
{300,400,600,800,1200}. Compare vs uniform h{200,400,800,1600,3200}, `low_top2gap`,
phase/opening heuristic, random escalation, oracle. Also report the
**constant-compute reranker** (G4) decisive-tail regret vs h200's own.

**If the graph model does NOT robustly beat `low_top2gap`:** STOP, write
[FGSR_DECISION.md](FGSR_DECISION.md) (Decision B or C), do **not** integrate with
search, do **not** run games.

**To be recorded here:** per-model AUROC/AUPRC, matched-compute regret table,
bootstrap P + CI vs B3, phase/source robustness, tail recall, decisive-tail
reranking result. Pass/fail verdict.
