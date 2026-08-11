# Outside-Review Package — Carcassonne AlphaZero/KataGo-style project

This directory is a **self-contained review package** for an external technical
reviewer with no prior involvement in the project. Its purpose is to make
implementation bugs, invalid assumptions, misleading measurements, and dead ends
**findable** — not to defend the current approach.

Assembled 2026-06-07 at repo HEAD **`fd9952e`** (branch `stage-b-wiring`).

> **Note:** this bundle is a **frozen snapshot** assembled at a fixed commit. The
> **LIVE** governance layer now lives in [`../governance/`](../governance/README.md)
> (claim registry, checkpoint lineage, evidence epochs, protocols) — use that for
> any current/ongoing work. `EXPERIMENT_LEDGER.csv` here is a derived, point-in-time
> view; the canonical raw ledger is `experiments/results.csv`.

## Start here
1. **`OUTSIDE_REVIEW.md`** — the main document (15 sections). Read top to bottom; §1 orients, §11 is the high-risk code, §14 is what we want you to answer.

## Supporting files (referenced by the main doc)
| File | What it is |
|---|---|
| `CODE_MAP.md` | where every component lives, with file:line anchors |
| `EXPERIMENT_LEDGER.csv` | chronological, enriched ledger (hypothesis / confounds / reproduced / alt-interpretation) |
| `CURRENT_CONFIG.yaml` | the resolved production config, with risk flags inline |
| `METRIC_DICTIONARY.md` | exact definition of every number we report + how each misleads |
| `KNOWN_ANOMALIES.md` | A1–A10: things that don't fit our explanation (fact / explanation / still-unexplained) |
| `REPRODUCTION.md` | smallest practical reproductions, with exact commands + UNVERIFIED flags |
| `OPEN_QUESTIONS.md` | the 11 framed questions + our unresolved internal questions |
| `artifacts/` | raw evidence (see below) |

## Raw evidence (`artifacts/`)
| File | Relevance |
|---|---|
| `results.csv` | **the authoritative experiment table** (verbatim copy of `experiments/results.csv`, 110 rows) |
| `foundational_audit_2026-06-02.md` | round-1 6-agent audit: 2 live bugs + 6 architectural caps (the F-* findings) |
| `foundational_audit_round2_2026-06-02.md` | round-2: measurement/training/Stage-B gaps (the G-* findings) |
| `CORRECTION_PLAN_2026-06-02.md` | the staged A/B/C correction plan |
| `example_manifest_*.json` | representative resolved per-eval configs |
| `iter_timings.csv` | the only per-iteration time/corr series (partial) |

## The four things we most want you to check first
1. **`OUTSIDE_REVIEW.md §11 R1 / KNOWN_ANOMALIES A8`** — ✅ **CONFIRMED + measured 2026-06-07.** The strength yardstick (HeuristicMCTS) used a *different leaf* (v1) than the agent (v2.7), contradicting its docstrings. We re-ran the headline cell with a matched leaf: **+86.9 → +48.1 elo** (n=400 paired) — ~45% of the headline was the leaf gap; the policy edge is real but ~half. Fixed `d472d10`. **The open question for you: by the same logic, discount the other vs-HeuristicMCTS absolutes (+25/+57) ~45% — does any of the strategic narrative change?**
2. **§11 R2** — the value head is gradient-starved ~5–10× by default; "value can't help" may be a loss-weighting artifact.
3. **§11 R3 / A9** — eval seed floors overlap trained-on self-play decks.
4. **§5 / A1** — our most confident number (+181.7 / 9.2σ) collapsed to +25.2 from a "non-strength" change; calibrate your trust in every vs-HeuristicMCTS σ accordingly.

## Caveats about the package itself
- Findings labeled **[FACT]** are checked in code or quoted from `results.csv`; **[INTERPRETATION]** is our (distrust-able) reading. **UNKNOWN** = not determinable from the repo.
- A few reproduction commands carry **UNVERIFIED** flags (argparse names we did not run-test).
- The current best checkpoints (Stage-B / residual) live on the CIFS share `/mnt/c/carc-shared`, not in the repo; in-repo `checkpoints/` holds the superseded pre-Phase-0 nets.
- This package does not modify any project file outside `outside_review/`.
