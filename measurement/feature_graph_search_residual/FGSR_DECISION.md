# FGSR_DECISION.md — Decision

> **STATUS: ⏳ PENDING — Stage 9, NOT STARTED. Written when the pilot concludes.**
>
> _Stub created 2026-06-29._

## Questions to answer at close

1. Was a real feature-graph schema feasible? _(Stage 0: provisionally YES — see
   [FGSR_PLAN.md](FGSR_PLAN.md). flat_leaf.Decomp already enumerates components.)_
2. Did the graph model learn post-search residual better than scalar features?
3. Did it beat `low_top2gap`?
4. Did it improve matched-compute adaptive simulation?
5. Did actual search integration preserve the offline win?
6. Did games improve?
7. Is feature-graph architecture a live route toward recursive learned improvement?
8. Or only useful for diagnostics / evaluator archaeology?

## Decision labels (one will be selected)

- **A** — schema infeasible (extraction too costly/fragile).
- **B** — graph feasible but no signal beyond simple features.
- **C** — graph beats simple features offline but not `low_top2gap`.
- **D** — graph beats `low_top2gap` offline but search integration fails.
- **E** — search/root improves, games do not (root-metric trap).
- **F** — graph-adaptive improves games (first real learned contribution beyond stack).
- **G** — graph helps only diagnostics / v2.10 heuristic archaeology.
- **H** — full resurrection candidate (games improve **and** improved search yields
  better labels for a next training round).

## Governance reminders

Not a flywheel unless games improve. Not recursive unless a second generation
improves from first-gen labels. No cluster-scale compute before the offline
graph-vs-`low_top2gap` gate passes. Do not optimize static-leaf regret. Do not
trust root agreement.

_On close: stamp results.csv, DECISIONS.md index line, this banner, governance row,
STATUS.md (the 5-touch close-out)._
