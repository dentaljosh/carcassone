# FGSR_SEARCH_RESULTS.md — Search Integration

> **STATUS: ⏳ PENDING — Stage 7, NOT STARTED (gated on Stage 6 PASS).**
>
> _Stub created 2026-06-29._

## Plan (only if the offline gate passes)

Implement the best graph model as an adaptive scheduler (preferred first) or
reranker. **Do not** globally replace leaf or policy.

- **Preferred:** h200 first → graph model predicts h200 failure → escalate to
  h800/h3200 if triggered, else keep h200.
- **Alternative (only if offline justifies):** graph reranks h200 top-k children.

Measure actual runtime overhead; confirm implementation matches the offline
simulation (actual ≈ simulated regret).

**Metrics:** average sims · wall-clock · escalation rate · regret on held-out roots
· tail recall · ordinary-subset regression · vs `low_top2gap` scheduler.

**To be recorded here:** the actual-vs-simulated reconciliation, runtime overhead,
and whether the offline win survived integration (else Decision D).
