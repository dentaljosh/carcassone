# FGSR_MODEL.md — Model Architecture

> **STATUS: ⏳ PENDING — Stage 4, NOT STARTED (gated). Smallest-first.**
>
> _Stub created 2026-06-29._

## Plan (not yet executed) — cheapest-informative-first

Start with the smallest model that consumes graph/action structure; do **not**
build a giant stack before signal.

| id | model | role |
|---|---|---|
| **G0** | **graph-lite MLP** over [FGSR_SCHEMA.md](FGSR_SCHEMA.md) graph-lite rows (strict superset of the prior 32-feature MLP) | bridge; if G0 ties B3/B5 → Decision B, stop before GNN |
| G1 | action-conditioned typed graph encoder (small message-passing or token-transformer with type embeddings); `legal_action` node included | the actual representation test |
| G2 | pairwise action comparator over graph embeddings (h6400 prefers i over j) | only if G1 shows life |
| **G3** | escalation classifier (graph + h200 diagnostics → P(h200 materially wrong)) | adaptive-compute value prop (a) |
| **G4** | search-residual reranker (graph + h200 top-k → h6400-preferred child) | **constant-compute value prop (b) — primary** |

**Avoid:** pure state scalar value; static-leaf residual as primary target; policy
imitation; large model before a cheap one proves signal.

**To be recorded here when built:** input dims, layer sizes, param counts, which
model passed/failed the offline gate.
