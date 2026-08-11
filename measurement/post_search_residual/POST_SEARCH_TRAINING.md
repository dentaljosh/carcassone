# Post-Search Residual — STAGE 3 TRAINING

_generated 2026-06-28 23:15_

Models trained on TRAIN, selected on VAL, scored on TEST (split by game — no game crosses splits). All inputs are h200-visible (no h6400 leakage); targets derive from h6400.

- Features (32): entropy200, top_share200, top2_q_gap200, log_n_visited200, log_legal_n, ply, phase_opening, phase_midgame, phase_late_mid, phase_pre_endgame, phase_endgame, x_city_open_n_sum, x_farm_adj_city_sum, x_farm_fin_city_sum, x_k_remaining, x_meeples_free_diff, x_meeples_free_opp, x_meeples_free_self, x_n_city, x_n_city_finished, x_n_city_open, x_n_farm, x_n_road, x_n_road_open, x_open_structures, x_score_margin, x_v29_base, x_v29_closure_opp, x_v29_closure_self, x_v29_meeple_curve_delta, x_v29_meeple_flat, x_v29_pretransform
- n: tr=7031 va=1648 te=1672
- H0 best single heuristic (Stage-2 floor); M1 ridge→regret; M2 logistic→pos_medium; M3 MLP→pos_medium (early-stop on val AUROC).
- Tier-B structural features: ON.

See POST_SEARCH_OFFLINE_RESULTS.md for the Stage-4 gate.
