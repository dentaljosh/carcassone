# Phase 1 — Variant Registry (search/policy mixing audit)

> **Measurement only.** Champion unchanged (`flywheel2_champion_iter8`). Machine-readable configs:
> [VARIANT_CONFIGS.json](VARIANT_CONFIGS.json). Every variant records exact budget, leaf, policy
> source, value source, residual scale, c_puct, routing rule, and cost/status.
>
> **Design discipline:** start from the minimum viable set. Most variants are **already labelled
> or already full-game-measured** — the only NEW compute is one cheap Phase-2 root pass and (gated)
> a small Phase-3 pilot.

## Status legend
- **baseline-reused** — root choice already in `MIDGAME_REFERENCE_LABELS.jsonl`; no recompute.
- **fullgame-reused** — full-game paired result already in `LEVEL2_HYBRID_VERDICT.md`; no recompute.
- **new-cheap** — computed in the Phase-2 root pass (net-on-CPU, ~3–4 min @ W14).
- **collapsed-duplicate** — provably identical to another variant (no separate compute).
- **gated-offline-first** — evaluated offline (Phase 4) before any full-game spend.

## Required baseline variants

| # | variant | agent | sims | leaf | policy | value / residual | c_puct | root label | status |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **ITER8_PROD** | NeuralMCTS | 200 | v2.7 | net | v2.7 + 0.25·net_resid | 3.0 | `iter8_choice` | baseline-reused |
| 2 | **HEUR_200_V27** | HeuristicMCTS | 200 | v2.7 | — | v2.7 | — | `heur200_choice` (NEW) | new-cheap |
| 3 | **HEUR_800_V27** | HeuristicMCTS | 800 | v2.7 | — | v2.7 | — | `heur800_choice` | baseline-reused |
| 4 | **HEUR_3200_V27** | HeuristicMCTS | 3200 | v2.7 | — | v2.7 | — | `heur3200_choice` (teacher) | baseline-reused |

## Decomposition variants

| # | variant | agent | sims | leaf | policy | value / residual | root label | status |
|---|---|---|---|---|---|---|---|---|
| 5 | **ITER8_POLICY_ONLY_LEAF_V27** | NeuralMCTS | 200 (+800 opt) | v2.7 | net | **net value DISABLED** (resid 0) | `iter8_noresid_choice` (NEW) | new-cheap |
| 6 | **ITER8_NO_RESIDUAL** | NeuralMCTS | 200 | v2.7 | net | residual 0 | **= #5** | collapsed-duplicate |
| 7 | **ITER8_POLICY_ROOT_ONLY** | policy argmax @root | 0 | — | net argmax | — | `iter8_prior_argmax` | baseline-reused (root pick) |
| 8 | **V27_STATIC_ROOT_ONLY** | static argmax | 0 | v2.7-d0 | — | v2.7 static | `v27_static_choice` | baseline-reused |

> **⚠️ #5 ≡ #6 (FACT).** `make_v25_value_wrapper(..., residual_scale=0)` returns `(priors, h)` with
> `h=tanh(v2.7/15)` — it discards the net value `v_nn`. So "policy-only + v2.7 leaf" and "no
> residual" are the **same agent**: net policy prior → PUCT, v2.7-static → leaf, no net value.
> One compute (`iter8_noresid_choice`) serves both, and the prod-vs-noresid contrast isolates
> *exactly* the residual head (Phase 5). This is the single most useful new measurement in the audit.

## Candidate hybrid / routing variants

| # | variant | rule | full-game | status |
|---|---|---|---|---|
| 9 | **HYBRID_FIXED_K8** | iter8 → heur@3200 at k≤8 | **+20.9 elo vs iter8 (z=5.79 n400); −19.1 vs heur@3200 (z=−0.51)** | fullgame-reused |
| 10 | **HYBRID_FIXED_K5** | iter8 → heur@3200 at k≤5 | +10.4 vs iter8 (z=3.45); −13.9 vs heur@3200 (z=−0.30) | fullgame-reused |
| 11 | **HYBRID_PHASE_DYNAMIC** | handoff on (k-band, legal count) | — | gated-offline-first |
| 12 | **HYBRID_SHARPNESS_DYNAMIC** | handoff on policy_entropy / policy_top1 / v27_gap / visit-conc / k | — | gated-offline-first |

## What this registry buys (INTERPRETATION)

- **8 of 12 variants need NO new compute** — 6 are already labelled/measured, 1 is a provable
  duplicate, and the two dynamic candidates are gated behind offline analysis.
- The only **new** compute is the Phase-2 root pass (variants 2 and 5) — cheap, reusing the
  1000-position bank — plus the routing signals (`policy_entropy`, `policy_top1_prob`, `v27_gap`,
  `iter8_noresid_topvisit_frac`) that variants 11/12 are evaluated on.
- A Phase-3 full-game pilot is run **only** for the residual decomposition (#5 vs #1, #5 vs
  #2/#3) and **only if** the root pass shows the residual moves the root choice materially.

## Cost summary (FACT/estimate)

| work | what | est. cost |
|---|---|---|
| Phase-2 root pass | `heur200` + `iter8_noresid@200` + signals on 1000 positions, W=14 net-on-CPU | ~3–4 min local (heur@200 ≪ heur@3200; one @200 neural search) |
| Phase-2 analysis | join + agreement/τ by band/disagreement/sharpness | seconds (offline) |
| Phase-4 routing | offline rule scoring on root-audit data | seconds (offline) |
| Phase-3 pilot (gated) | n=100–200 paired neural games, fresh band, both seats | est. ~8–15s/game neural (per hybrid verdict) → ~15–40 min @ orch W high; **pilot n=20 first, report cost** |
| reused | ITER8_PROD/HEUR_800/HEUR_3200/v2.7-static/iter8-prior roots + all fixed-K hybrid full-games | $0 |
