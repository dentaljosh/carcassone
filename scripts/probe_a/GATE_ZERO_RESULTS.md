# Probe A — Gate Zero (leaf-speed feasibility) — results

**Spec:** `docs/PROBE_A_STRUCTURED_VALUE_SPEC.md` §3. **Date:** 2026-06-30. **Box:** local 5900XT (idle).
**Bench:** `scripts/probe_a/gate_zero_speed.py` (`nice -n 19`, `CARCASSONNE_USE_CY_LEAF=1`).
Full stdout: `scripts/probe_a/gate_zero_results.txt`. NOT committed (working-tree note only).

## Question
Can `v_leaf(s) = aggregate(g_theta(comp_i) for comp_i in decompose(s))` be evaluated
within **≤ 3× the production Cython leaf per node**?

## Baseline (the bar)
Production entry `flat_leaf.flat_virtual_score_v2` → binds `flat_leaf_cy.flat_virtual_score_v2_cy`
(confirmed bound). **Median ≈ 30–35 µs/leaf** on 60 mid/late-game boards (40–80 tiles,
median ~59 tiles / ~88 components). Reproducible across runs.

## Results (ratios to the 30 µs baseline)

| impl | ns/node | ×base | verdict |
|---|---|---|---|
| BASELINE Cython leaf | 30,000 | 1.00× | — |
| (a) torch head only (feats given) | 26,300 | 0.88× | head is cheap |
| (b) numpy head only (feats given) | 8,400 | 0.28× | head is cheap |
| **PATH-PY** py-`decompose()` + numpy head (drop-in) | 413,000 | **13.8×** | **FAIL** |
| (c) memo: py-`decompose()` + k-comp head | 409,000 | **13.6×** | **FAIL** |
| **PATH-CY** baseline + numpy head (Cython feature-emit) | 38,400 | **1.28×** | **PASS** |

## The load-bearing finding
The tiny per-component head is **not** the bottleneck (numpy 0.28×, torch 0.88× — both clear 3×
even at batch-1). The bottleneck is the **decomposition**: the Cython baseline computes a full board
decomposition in a C `_WS` struct and returns only the scalar — it does **not** expose a Python
`Decomp`. So the head's feature source decides everything:

- **PATH-PY** (the spec's literal `decompose()` + head): pure-Python `flat_leaf.decompose()` alone
  is **13.5× the whole compiled leaf** → a second full decompose per node → **13.8×, FAIL**.
- **PATH-CY**: emit per-component features from the *same* C decomposition the baseline already
  computes, then run the head → marginal cost is only featurize+head → **1.28×, PASS**. This is
  **not a drop-in** — it needs `flat_leaf_cy` extended to return per-component features (bounded,
  ~1 day of Cython work).

## Memoization lever (c) — assessed, does NOT clear
- **Component-identity keying is FEASIBLE** (spec open-question 1): components key stably on their
  member-position frozensets — `Decomp.city_root_positions` / `road_root_positions` / `farm_root_keys`
  are invariant sets. Measured **~96% of components reused** per placement (median 3, mean ~3 of ~90
  change per tile).
- **But memo does not rescue the budget.** Stable keys save the *head* eval, which was already cheap.
  You still must `decompose()` the child board to learn *which* components changed → **13.6×, FAIL**.
  Memoization is the wrong lever; the cost is structural extraction, not head arithmetic.

## VERDICT: MARGINAL / CONDITIONAL PASS
Gate zero is **not a clean FAIL** — a structured per-component head *can* be evaluated at ~1.28×
leaf speed. But **only via PATH-CY** (features emitted from the Cython decomposition). The spec's
assumed drop-in (`flat_leaf.decompose()` in Python + head) is **13.8×, a hard FAIL**, and the
memoization lever the spec flagged as "highest-leverage" also **fails (13.6×)** because it can't
avoid the per-node decompose.

**Recommendation:** Probe A survives gate zero **conditional on** a bounded piece of Cython work
(extend `flat_leaf_cy` to emit per-component features + wire the head over the C decomposition).
Budget that ~1 day before the offline pre-gate (§4). If that Cython emit is deemed out of scope,
gate zero fails on the drop-in path and Probe A is a non-starter at the spec's stated implementation.

Caveats: micro-bench only (single-process, net-on-CPU). The spec also asks for a **W-parallel
games/hr A/B** — that should confirm PATH-CY once the feature-emit exists; do not promote on the
micro-bench alone.
