# Post-Search Residual — STAGE 6 GAME SCREEN

**NOT RUN — gated out by Decision C (2026-06-28).**

Stage 6 (paired games at matched average compute) was gated on Stage 5, which was gated on a robust
Stage-4 learned win. Stage 4 returned **Decision C** (predictable, but a simple heuristic suffices;
ML adds no robust value), so no games were run — **no cluster used, no compute spent.**

Rationale for not running even a heuristic-scheduler game screen: the offline matched-compute edge is
**~0.0003 mean tanh-Q regret** at C=400 (oracle ceiling only ~0.0016 on a base mean of 0.0031) — far
below what an n=100–200 paired screen can resolve, and the project's standing `b99c9ed` result (root
metrics don't convert to game strength; now 4× confirmed) makes a null outcome the strong prior. See
`POST_SEARCH_DECISION.md` for the full reasoning and the BACKLOG compute-efficiency note.
