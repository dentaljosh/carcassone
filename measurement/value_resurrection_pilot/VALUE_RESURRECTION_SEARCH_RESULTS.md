# Value Resurrection Pilot — SEARCH RESULTS (Stage 6)

> **STATUS: NOT RUN — gated out by Stage 5 (Decision B).** 2026-06-28.

Stage 6 (plug the best learned value into NMCTS as `eval = v2.9_leaf + α·learned_residual`, α-sweep,
root diagnostics on the miss set / held-out / endgame, **on the rust orchestrator at high W across
local+laptop**) is **not run**. Per the plan's stop rule, NMCTS is attempted only if a learned variant
**beats the v2.9 leaf offline (Stage 5)** — none did (every variant's optimal weight on the net was
α=0; see [VALUE_RESURRECTION_OFFLINE_RESULTS.md](VALUE_RESURRECTION_OFFLINE_RESULTS.md)).

There was therefore **no value head worth integrating into search**, and **no cluster/orch spend** was
incurred. (Independently, b99c9ed Decision D already measured the residual head as *inert in NMCTS* —
rs 0/0.25/0.5 indistinguishable, residual never corrupts — so a Stage-6 integration would reproduce
that null.)
