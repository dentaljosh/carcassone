# FGSR_BASELINES.md — Baselines

> **STATUS: ⏳ PENDING — Stage 3, NOT STARTED (gated).**
>
> _Stub created 2026-06-29._

## Plan (not yet executed)

The graph model must clear these, not just the static leaf. Harness reused from
`scripts/post_search_residual/run_baselines.py` + `run_adaptive_gate.py`.

| id | baseline | status |
|---|---|---|
| B0 | uniform h200 | prior numbers exist (residual pilot) |
| B1 | uniform h800 | prior |
| B2 | uniform h3200 | prior |
| **B3** | **`low_top2gap` scheduler** (AUROC ~0.725) — **primary non-ML baseline to beat** | prior |
| B4 | phase/opening scheduler (tail is opening-heavy) | to run |
| B5 | MLP/linear over 21–50 structural scalars (prior AUROC ~0.780, **tied B3**) | prior + re-run |
| B6 | static feature comparator (reference; not expected to help) | prior |
| B7 | **oracle adaptive routing** — upper bound (~0.0016 removed @ C=400) | prior (`md_oracle_at`) |

**Metrics:** AUROC/AUPRC for h200 failure; regret captured at top-k escalation;
regret removed per extra sim; **matched-compute regret at C ∈ {300,400,600,800,1200}**;
vs uniform search; vs `low_top2gap`; phase/source split; tail recall. Bootstrap
(2000 resamples) P(model beats B3) + 95 % CI.
