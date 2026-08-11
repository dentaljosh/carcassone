# FGSR_DECISION.md — Decision

> **STATUS: 🔴 CONCLUDED — DECISION B.** The offline gate FAILED. A
> Carcassonne-native feature-graph / action-conditioned model does **not** learn
> the post-search residual (`h6400 − h200`) better than flat scalars, and beats
> **neither** the prior 32-feature MLP **nor** the `low_top2gap` heuristic at
> matched compute. Per the spec, the pilot STOPS at the offline gate: **no search
> integration, no games.** v2.9 / PRODUCTION.yaml untouched; nothing promoted.
> The learned-flywheel chapter stays closed.
>
> _Concluded 2026-06-29. Evidence: [FGSR_OFFLINE_RESULTS.md](FGSR_OFFLINE_RESULTS.md),
> [FGSR_BASELINES.md](FGSR_BASELINES.md), `data/offline_gate.json`, `data/train_summary.json`._

## The question, answered

> Can a Carcassonne-native feature-graph model learn the residual that survives
> shallow search?

**No.** The graph model neither beats the flat-scalar MLP nor `low_top2gap`, and a
graph-ablation shows its relational structure is **inert** (the reranker does
*better* with the graph embedding zeroed). The honest Stage-0 prior — magnitude
ceiling, most-likely B/C — held, landing on **B**.

## Answers to the close-out questions

1. **Real feature-graph schema feasible?** ✅ Yes. `flat_leaf.decompose` already
   enumerates city/road/farm components; extraction is ~67 ms/root, 0 errors on
   10,351 roots. Feasibility was never the blocker (Decision A ruled out at Stage 0.5).
2. **Did the graph model learn the residual better than scalar features?** ❌ No —
   *worse*. G1 (969K-param typed GNN) generalizes to **test AUROC 0.559** (train
   0.678) vs the flat G0 0.660 and the prior flat MLP B5 **0.78**. High capacity +
   186 train positives → it overfits and underperforms the simple models.
3. **Did it beat `low_top2gap` (B3, AUROC 0.725)?** ❌ No. At matched compute,
   P(G1 beats B3)=0.05–0.34, P(G0 beats B3)=0.23–0.34 (need ≥0.95); max regret
   reduction vs B3 = **−100 %** (i.e. worse). Both **FAIL**.
4. **Improve matched-compute adaptive simulation?** ❌ No — see #3. The oracle
   ceiling (~0.0016 tanh-Q @ C=400) is never approached; `low_top2gap` remains the
   best cheap router.
5. **Search integration preserve the offline win?** N/A — gate failed, not run.
6. **Did games improve?** N/A — gate failed, not run.
7. **Live route toward recursive learned improvement?** ❌ No.
8. **Useful only for diagnostics / evaluator archaeology?** ✅ Partially — see
   "Consolation (Decision-G flavor)" below.

## Evidence (TEST = 1672 roots, net-free, frozen v2.9, 2000-resample bootstrap)

| model | head | metric | result | verdict |
|---|---|---|---|---|
| B3 `low_top2gap` | — | AUROC(pos_strong) | 0.725 | the bar |
| B5 flat MLP | — | AUROC | 0.780 | tied B3 (P=0.92, prior pilot) |
| **G0** graph-lite | G3 sched | AUROC / P(beats B3) @C400,C800 | 0.660 / 0.23, 0.34 | **FAIL** |
| **G0** graph-lite | G4 rerank | tail 0.04582→0.03703, P=0.94, ordinary-no-regression | **false** | **TIE → not a win** |
| **G1** typed GNN | G3 sched | AUROC / P(beats B3) | **0.559** / 0.05, 0.34 | **FAIL** |
| **G1** typed GNN | G4 rerank | tail 0.04582→0.03602, P=0.92, ordinary-no-regression | **false** | **TIE → not a win** |
| **G1** graph-ablation | G4 | tail with-graph 0.03602 vs **zeroed 0.03324** | Δ=−0.00278 | **graph INERT** |

**Why B and not C:** Decision C would require the graph to beat *simple features*
offline (just not `low_top2gap`). It does not — G1 is **worse** than both flat
models (G0, B5), and the ablation proves the relational structure adds nothing.
The marginal G4 tail effect (P~0.92–0.94 on 46 roots) is (a) below the 0.95 bar,
(b) carried by the action-feature scalars not the graph (ablation), and (c)
accompanied by **catastrophic ordinary-position regression** (the first full-pool
run: h200 0.00164 → 0.0086, 5×), so it fails the no-regression criterion.

## Why it failed (root cause, not a fluke)

- **The signal is thin and structurally shallow.** Post-search residual is
  concentrated in ~2.8 % of roots (287 pos_strong train / 46 test); ~20 % of the
  decisive tail is *structurally blind* (`leaf_q_gap≈0` between the contested
  children — only deep search separates them, [FEASIBILITY.md](FEASIBILITY.md)).
- **A flat MLP already extracts what's extractable** (B5 AUROC 0.78); the relational
  GNN has nothing left to add and only adds variance/overfit.
- **The magnitude is below game resolution anyway** (oracle ~0.0016, achievable
  ~0.0003–0.0006 tanh-Q), exactly as the residual pilot warned. Even a perfect
  router wins too little to convert to games.
- **Methodology note:** the GNN's first run looked like a null but was *underfit*
  (best_epoch 1, train AUROC 0.62). After a real fix (LR/early-stop, balanced
  subsample, per-epoch logging) it **fit train to 0.68–0.92 yet still generalized to
  0.56** — so the null is now a *fair* one: the model can learn the train signal, it
  just doesn't generalize. This is genuine evidence, not a training artifact.

## Consolation (Decision-G flavor) — diagnostics, not a live module

The feature graph is a useful **evaluator-archaeology** tool even though it is not a
live search module:
- It localizes the residual: opening-heavy, low-`top2gap`, ~20 % static-invisible.
- The **graph-ablation harness** cleanly proves "structure adds nothing here," which
  is itself a strong negative result worth keeping.
- The extractor + dataset (`extract_graph.py`, `data/graphs.pkl`) remain available if
  a future, much larger teacher/architecture change wants to revisit (per the spec's
  "until a much larger architecture/teacher change").

## Decision label

**Decision B — graph feasible but no signal beyond simple features.** (With a
secondary G-flavored note: useful for diagnostics, not as a live search/scheduler
module.) **NOT** F/H — no flywheel, not recursive, games never reached.

## Governance close-out

Gate failed → stopped at Stage 6 as the spec mandates. The learned-flywheel line
remains **closed**; v2.9 stays the production evaluator. Five-touch close-out:
results.csv row · DECISIONS.md index line · this banner · governance row · STATUS.md.
