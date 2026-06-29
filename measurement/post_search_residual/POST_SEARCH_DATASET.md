# Post-Search Residual — STAGE 1 DATASET

**Status:** built 2026-06-28 · `data/roots_adaptive.jsonl` (3000 roots, 18.8 MB) · net-free · frozen
v2.9 leaf (config_hash `7fc930b82801cb43`) · branch `rod_v2_flywheel`.
Builder: `scripts/post_search_residual/build_adaptive_dataset.py`. Derivation: `psr_lib.py`.

## What it is

Per root, **one HeuristicMCTS(6400) search**, with the root's child statistics
`{action → (N, Q_rootpov)}` snapshotted at cumulative sim counts **{200, 400, 800, 1600, 3200,
6400}**. Because MCTS is incremental, snapshot-at-L is bit-identical to a standalone
HeuristicMCTS(L) — so one search yields every uniform compute level **and** the h6400 reference.

**Snapshot-equivalence audit (correctness gate): PASS.** On 5 roots, snapshot-at-200 child
N-distribution == a freshly-constructed `HeuristicMCTS(200).search()`, exactly (sum N = 200, same
child count, same per-action visits). `build_adaptive_dataset.py --verify`.

## Source roots (Phase A — greedy-self-play)

Unique `group_id → (game_seed, ply)` from the feature-graph / value-resurrection pool
(`measurement/feature_graph_comparator/data/rows_feat.npz`), sampled **600 per phase** (3000 total,
1094 distinct game seeds, ply 29–140). This is the **greedy-self-play** distribution — a known bias
(flagged in the FG pilot). It is sufficient for the Stage-2 oracle go/no-go and carries a sanity
anchor (h200 regret reproduces the FG pilot's scale). **Phase B (real MCTS-play roots) is required
before Stage 3 training** and is gated on the Stage-2 verdict.

## Per-root fields (derived in `psr_lib.load_roots`)

`sel[L]` = best_action(hL) under the mcts.py rule `argmax(Q_rootpov, N)` · `regret[L]` =
`Q6400[sel(h6400)] − Q6400[sel(hL)]` (≥0) · `q_gap_6400` · labels (positive_strong / _medium /
negative) · h200 diagnostics (entropy, top_visit_share, top2_q_gap, n_visited, legal_n).

## Distribution of the post-search residual `regret(h200)` (tanh Q units)

| stat | value |
|---|---|
| median | **0.0000** (h200 ties h6400 on ≥50% of roots) |
| p75 | 0.0016 |
| p90 | 0.0110 |
| p95 | 0.0282 |
| p99 | 0.1092 |
| mean | 0.0061 |
| max | 0.6912 |

**Extremely long-tailed:** half the roots have zero regret; the opportunity is entirely in a thin
upper tail. (Concentration: the worst 5% of roots hold 72% of all h200 regret — see BASELINES.)

## Labels

| label | rule | rate |
|---|---|---|
| positive_strong | q_gap_6400 ≥ 0.02 ∧ regret(h200) ≥ 0.02 | **3.6%** (109) |
| positive_medium | q_gap_6400 ≥ 0.01 ∧ regret(h200) ≥ 0.01 | 5.9% (178) |
| negative | regret(h200) < 0.005 ∨ agree(h200,h6400) ∨ q_gap_6400 < 0.005 | 90.0% |

h200 top move == h6400 top move on **60%** of roots.

## Where h200 is wrong (per phase) — the residual is phase-concentrated

| phase | n | positive_strong | mean regret(h200) | h200==h6400 top |
|---|---|---|---|---|
| **opening** (ply~32) | 600 | **9.3%** | **0.0128** | 62.3% |
| midgame (ply~68) | 600 | 5.2% | 0.0077 | 60.2% |
| late_mid (ply~100) | 600 | 1.7% | 0.0037 | 63.0% |
| pre_endgame (ply~120) | 600 | 0.8% | 0.0023 | 59.2% |
| endgame (ply~136) | 600 | 1.2% | 0.0039 | 55.3% |

h200's residual error vs h6400 is **concentrated in the opening/early-midgame** — long horizons +
many near-equal moves are where shallow search most often picks a materially worse move. This is a
Decision-G ("narrow slice") signature to watch.

## Escalation recovers the regret on the bad roots

On the 109 positive_strong roots, deeper uniform search removes most of the regret:

| level | mean regret on positive_strong roots |
|---|---|
| h200 | 0.0852 |
| h400 | 0.0412 |
| h800 | 0.0308 |
| h1600 | 0.0160 |
| h3200 | 0.0035 |
| h6400 | 0.0000 |

→ the opportunity is real and escalation-addressable: routing deep search to these roots collapses
their regret. **The open question is whether a model can *identify* them from h200-visible features
— and Stage 2 shows the obvious uncertainty heuristics cannot.** See `POST_SEARCH_BASELINES.md`.
