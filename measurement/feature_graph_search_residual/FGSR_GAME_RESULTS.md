# FGSR_GAME_RESULTS.md — Tiny Game Screen

> **STATUS: ⏳ PENDING — Stage 8, NOT STARTED (gated on Stage 7 PASS).**
>
> _Stub created 2026-06-29._

## Plan (only if search integration preserves the offline win)

Paired games at **matched average compute**. Ask which box before launching
(multi-minute → cluster-ops rules). Deck-paired to halve variance.

**Matchups:** graph-adaptive vs uniform search @ same avg compute · vs `low_top2gap`
adaptive @ same avg compute · vs h200 · vs h800/h3200 references · optionally vs
RoD2_iter04.

**Start n=100–200 paired.** Metrics: WR · Elo · paired margin · paired z · actual
avg sims · wall-clock · escalation rate · phase-escalation distribution · close/even
bucket · blowout distribution.

**Top up to n=400 only if** graph-adaptive directionally beats `low_top2gap` and
uniform at matched compute, runtime is acceptable, and no obvious regression.
(Recall: n=400 unpaired ≈ ±17 elo; the expected effect here is tiny — size honestly.)

**To be recorded here + in `experiments/results.csv`:** the paired result with z,
actual compute, and the verdict (E if root improves but games don't, F if games improve).
