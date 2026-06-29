# Post-Search Residual — STAGE 3 (train) + STAGE 4 (offline adaptive GATE)

_generated 2026-06-28 23:15 · TEST split (held out by game) · tier-B structural feats=ON_

Roots: 10351 usable · tr=7031 va=1648 te=1672. Features (32): entropy200, top_share200, top2_q_gap200, log_n_visited200, log_legal_n, ply, phase_opening, phase_midgame, phase_late_mid, phase_pre_endgame, phase_endgame, x_city_open_n_sum, x_farm_adj_city_sum, x_farm_fin_city_sum, x_k_remaining, x_meeples_free_diff, x_meeples_free_opp, x_meeples_free_self, x_n_city, x_n_city_finished, x_n_city_open, x_n_farm, x_n_road, x_n_road_open, x_open_structures, x_score_margin, x_v29_base, x_v29_closure_opp, x_v29_closure_self, x_v29_meeple_curve_delta, x_v29_meeple_flat, x_v29_pretransform.

Gate: a LEARNED adaptive policy must beat **uniform** at matched avg compute AND beat the best simple heuristic (**H0_low_top2gap**) on the held-out TEST split.

## Model escalation-score quality + adaptive regret at matched compute (TEST)

| model | AUROC(pos_strong) | adaptive@C=400 (D) | vs uniform | adaptive@C=800 (D) | vs uniform |
|---|---|---|---|---|---|
| H0_low_top2gap | 0.725 | 0.00204 (h800) | **beats** | 0.00160 (h1600) | **beats** |
| M1_ridge_regret | 0.626 | 0.00197 (h800) | **beats** | 0.00168 (h1600) | **beats** |
| M2_logistic | 0.704 | 0.00212 (h800) | **beats** | 0.00169 (h800) | no |
| M3_mlp | 0.780 | 0.00176 (h800) | **beats** | 0.00161 (h1600) | **beats** |

## Ceilings + floors (TEST)

| avg C | uniform | random | best heuristic-tie | pairwise oracle | multi-depth oracle |
|---|---|---|---|---|---|
| 400 | 0.00235 | 0.00234 | — | 0.00073 | 0.00017 |
| 800 | 0.00169 | 0.00169 | — | 0.00041 | 0.00003 |

## Bootstrap robustness — is the win real or tail-noise? (2000 resamples of TEST)

best learned = **M3_mlp** vs heuristic **H0_low_top2gap**. P = fraction of resamples where the learned model wins; Δ vs heuristic 95% CI.

| avg C | P(learned beats uniform) | P(learned beats heuristic) | Δ vs heuristic (95% CI) |
|---|---|---|---|
| 400 | 1.00 | 0.92 | +0.00023 [-0.00009, +0.00059] |
| 800 | 0.68 | 0.54 | +0.00001 [-0.00019, +0.00022] |

## GATE VERDICT (bootstrap-aware)

### **C — predictable, but a simple heuristic suffices.** The escalation signal IS predictable and a learned (and heuristic) policy beats **uniform** at matched compute robustly — but the learned model does **NOT** robustly beat the simple `H0_low_top2gap` heuristic (P<0.95; Δ CI crosses 0). **ML adds no robust value over a trivial rule.**

Per spec Decision C: use the heuristic scheduler if useful; **no ML flywheel**. AND note the magnitudes: even the oracle ceiling removes only ~0.0016 of ~0.0031 mean Q-regret; the heuristic captures a small fraction of that. The absolute matched-compute gain is tiny → game-conversion is doubtful (the `b99c9ed` root-metrics-don't-convert pattern). **Do NOT train an ML scheduler.** Whether even the *heuristic* scheduler converts to games at matched compute is the one open question — a SPEND (games) gate.
