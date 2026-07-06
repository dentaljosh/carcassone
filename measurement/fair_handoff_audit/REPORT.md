# PHASE 0.1 — Executable audit of the production FAIR endgame handoff — REPORT

**Date:** 2026-07-06 · **Status:** COMPLETE · **Verdict:** the PRODUCTION.yaml "K≤4 alpha-beta" wording describes the CLAIRVOYANT reference agent, NOT the fair deployable path. The fair agent is honest: **0 clairvoyant/alpha-beta solves, marginalized solve bit-invariant to deck order.** MEASUREMENT ONLY — nothing promoted; a PRODUCTION.yaml wording fix is *proposed* below, not applied.

Harness: `scripts/fair_handoff_audit/audit.py`. Data: `audit_summary.json`, `audit_raw.pkl`, `full.log`. Config: 20 production-config fair games (v2.9 Bmild_cap8 leaf, FairHeuristicMCTSAgent sims=200 K=4 pooled-Q, exact_endgame=True) vs the clairvoyant champion; 4.6 min.

> **Scope note:** this is a CODE-PATH + INFORMATION-LEAK census, not a strength claim. The conclusions (which k triggers the exact handoff; whether any solve reads true deck order) are **independent of sims and n** — they are properties of the latch logic and solver mode, exercised fully by 40 solves across 20 games. A larger n would not change them.

## The reconciled truth (the two conflated code paths)

| | CLAIRVOYANT reference / eval agent | FAIR deployable agent |
|---|---|---|
| Where | `scripts/level2/eval_hybrid_handoff.py` `exact:K:MODE` (+ HeuristicMCTS descending the true `state.deck`) | `src/carcassonne_ai/fair_agent.py` |
| Endgame | exact **K≤4 clairvoyant alpha-beta** (`mode="clairvoyant"`) | exact **K≤2 marginalized** expectiminimax (`mode="marginalized"`, `alphabeta=False`); PIMC above K=2 |
| Uses true deck order? | YES (clairvoyant — this is the *reference*, fair by symmetry only in clair-vs-clair A/Bs) | **NO** — reshuffles the unseen deck (PIMC) and sorts the bag multiset (marginalized) |
| What strength was measured with | THIS (the champion of record's numbers) | the *honest deployable* number (never fully measured — see STATUS "fair-config verdict") |

`endgame_solver.py` enforces the split structurally: line ~105 asserts `alpha-beta is clairvoyant-only (chance nodes break minimax cutoffs)`, and the marginalized `_key` (line ~133) keys on `tuple(sorted(descs))` — the **sorted** bag multiset — so a marginalized solve is order-independent *by construction*. `fair_agent.py` sets `EXACT_MAX_K = 2` and its docstring already names clairvoyant K=3–4 "the cheating path." **PRODUCTION.yaml line 29's "exact K≤4 alpha-beta solver handoff" can therefore only describe the clairvoyant reference agent** — a K≤4 *alpha-beta* solve is impossible in the fair (marginalized) path.

## (A) Per-move code-path census (which k triggers the exact handoff)

`exact_marginalized` fires at **k=1 (20/20 games) and k=2 (20/20 games)** only. Every decision at **k=3…72 is `pimc`** (20/20 at each k). Zero `exact_timeout_fallback` (no BudgetExceeded in these games). Latch-k distribution: **k=2 in 10 games, k=1 in 10 games** (the first TILES decision to reach the ≤2 band lands on k=2 or k=1 by phase/parity). This is exactly the `EXACT_MAX_K=2`, latch-on-first-TILES-decision behavior — no path fires the exact solver above k=2.

## (B) Solver-call ledger (the leak test)

Every `endgame_solver.solve` call during the 20 fair games was recorded via monkeypatch:

- **40 solves total, 100% `mode="marginalized", alphabeta=False`.**
- **`B_clairvoyant_or_alphabeta_solves = 0`** — no fair-mode solve ever ran clairvoyant or with alpha-beta, so **no solve ever received the true deck order beyond `next_tile`.**
- Solve-k distribution: {k=1: 20, k=2: 20} — solves happen only in the ≤2 band, as designed.

## (C) Order-invariance probes (executable "no hidden-order information used")

- **SOLVER (marginalized, k≤2 TILES):** 12 positions checked, **12/12 invariant**, 0 violations, 0 budget-skips. Marginalizing-solve on the board vs a deck-permutation (same multiset, same `next_tile`) yields **bit-identical `value` + `optimal_actions`**. Confirms the by-construction order-independence executably.
- **PIMC (full fair decision):** 14 non-latched positions, **4 flipped a move under deck permutation (8/42 permutation trials ≈ 19%).** This is **benign RNG-sampling sensitivity, not information exploitation**: `fair_agent._pimc_move` reshuffles the unseen deck with its own `random.Random`, and `random.Random.shuffle` produces a different permutation from a different *input* order — so the specific determinization sample (hence the pooled-Q pick) can depend on the input order, even though the reshuffle destroys the order *signal* in expectation. It does **not** let the agent exploit the true future; it does mean the PIMC move is not a pure function of observable state.
  - **Proposed hardening (NOT applied):** sort `board.state.deck` (by tile description) before the internal reshuffle in `_pimc_move` / `reshuffled_determinization`. That makes the determinization sample a function of the *multiset* only, so a fair decision becomes invariant to the (unobservable) input deck order — closing the last order-dependency while changing nothing about legality or expected play. Cheap, low-risk; worth doing before human-facing play, but out of scope for this measurement.

## Proposed PRODUCTION.yaml wording fix (PROPOSE — DO NOT APPLY)

Current line 29:
```yaml
  endgame: "exact K<=4 alpha-beta solver handoff (scripts/level2/endgame_solver.py) — margin-correct endgame"
```
Suggested replacement (distinguishes the two configs the single champion actually runs):
```yaml
  endgame: >
    Two handoffs share this champion. (a) CLAIRVOYANT reference/eval agent — what the
    champion's strength numbers were measured with: exact K<=4 clairvoyant alpha-beta solver
    (scripts/level2/endgame_solver.py, mode=clairvoyant), margin-correct. (b) FAIR deployable
    agent for human-facing play (src/carcassonne_ai/fair_agent.py): exact K<=2 MARGINALIZED
    expectiminimax handoff (mode=marginalized, no alpha-beta). Alpha-beta and K=3-4 are
    clairvoyant-only (they read the true deck order) so the fair agent caps at K<=2 marginalized.
    Audited 2026-07-06 (measurement/fair_handoff_audit/REPORT.md): 0 clairvoyant/alpha-beta
    solves in 20 fair games; the marginalized solve is bit-invariant to deck permutation.
```

## Impact on claims
No `governance/CLAIM_REGISTRY.csv` claim is *contradicted* (the fair machinery was reported as K≤2 marginalized in STATUS 2026-07-05). This audit **upgrades** that from documentation to a runtime-verified fact and flags the PRODUCTION.yaml wording as the one place the two configs are conflated. Recommend the wording fix + (before any human match) the PIMC deck-sort hardening.
