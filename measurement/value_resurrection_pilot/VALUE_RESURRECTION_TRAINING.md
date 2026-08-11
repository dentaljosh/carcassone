# Value Resurrection Pilot — TRAINING (Stage 4)

> **STATUS: DONE (cut short after 3/5 variants — all decisive). 2026-06-28. DIAGNOSTIC ONLY.**
> Policy frozen throughout (standalone value/ranking head only; no policy loss, no PRODUCTION change).

## Setup

- **Harness:** `scripts/rod_v2/value_resurrection/train_eval.py`, reusing the CL-021 model/loss blocks
  (`RankNet`, `listnet_loss`, `kendall_tau_b` from `scripts/value_ranking_train.py`) unchanged.
- **Dataset:** `/mnt/c/carc-shared/value_resurrection/dataset_v29_h6400/rows.npz` — 124,842 child rows /
  4,000 sibling groups / 1,113 games (a 4,000-group cap of the 10,067 available, to bound RAM; **logged,
  not silent**). Leakage-safe split **by game_seed** = train/val/test **2,802 / 561 / 637 groups**
  (777 / 164 / 172 games). `leaf_q ~ oracle_q` (h6400) correlation = **0.995**.
- **Net:** 64-filter / 4-block trunk + conv (arms A/B/E) or attention (C) head, **382k params**, fresh
  random init (CL-021 arch). Adam lr 1e-3, wd 1e-4, 40 epochs, groups-per-batch 32, ListNet temp 0.25,
  best-on-val-loss checkpoint. Single GPU (5900XT box), ~17 min/variant (25×25 obs H2D dominates).

## Variants & targets

| variant | arm | training target | note |
|---|---|---|---|
| **V4_listwise** | B (ListNet) | `oracle_q` (absolute h6400) | ≈ CL-021 arm B — the kill-test |
| **V2_advantage** | E (ListNet, within-group centered) | `oracle_q` | sibling-advantage ranking |
| **V1_residual_mse** | A (MSE) | `oracle_q − v2.9_leaf` | **the residual-regression variant — predict the leaf's correction** |
| V1r_residual_list | B (ListNet) | `oracle_q − v2.9_leaf` | NOT RUN (cut short) |
| V5_endgame | B (ListNet) | `oracle_q`, train on end/pre_endgame only | NOT RUN (cut short) |

**V1r and V5 were not run** (run cut after 3/5 — V4/V2/V1 were already decisive, and the residual head
is independently shown inert by b99c9ed Decision D). No silent truncation: this is recorded.

## Training behaviour

All three trained nets converged to **val ListNet loss ≈ 3.317** (V4 3.3174, V2 3.3178) — i.e. they
learn essentially the *uniform* sibling distribution (no discriminative ranking signal extracted). The
residual MSE net (V1) drove val MSE down by memorising the train mean but produced a held-out ranking
of **τ = +0.005** — it cannot predict the leaf's correction at all.

Per-variant artifacts: `measurement/value_resurrection_pilot/stage4/<variant>/{summary.json, head.pt}`
(`head.pt` are NOT_CHAMPION diagnostic heads — not promoted, not committed). Results → Stage 5
([VALUE_RESURRECTION_OFFLINE_RESULTS.md](VALUE_RESURRECTION_OFFLINE_RESULTS.md)).
