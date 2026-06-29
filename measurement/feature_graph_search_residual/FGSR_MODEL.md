# FGSR_MODEL.md — Stage 4 models (G0 graph-lite, G1 typed GNN)

> **STATUS: 🟢 BUILT + TRAINED.** Two models, each with two heads (G3 escalation +
> G4 reranker). CPU-only, net-free, no search, no games.
> `scripts/feature_graph_search_residual/model.py` + `train.py`. Checkpoints under
> `data/` (gitignored). Headline fit numbers + per-model params live in
> `data/train_summary.json` (canonical — this doc cites it, doesn't duplicate drifting numbers).
> _Last updated 2026-06-29._
>
> **Naming note:** the old stub used G2/G3/G4 as *model* ids. The executed pilot has TWO
> MODELS — **G0** (graph-lite MLP) and **G1** (typed GNN) — each carrying BOTH heads:
> **G3 = the per-root escalation scheduler**, **G4 = the per-action constant-compute reranker**.

## The two models (both have a G3 escalation head and a G4 reranker head)

### G0 — graph-lite MLP (the bridge; strict superset of B5)
- **Input** (per action row): the 50 comparator scalars (`FEAT_NAMES`, standardized on
  TRAIN) ‖ per-root diag `[top2_q_gap200, entropy200, top_share200, log_legal_n,
  phase-one-hot(5)]` ‖ Tier-B 21 structural scalars (`features_mcts.jsonl`), the diag+Tier-B
  repeated across the root's action rows. `d_in = 80`.
- **Trunk**: 2×Linear(→128)+ReLU+Dropout(0.1).
- **G3 head**: pool action rows within a root (mean ‖ max → 256) → MLP → root logit.
- **G4 head**: per-action Linear(128→1) score; argmax within a root = selected move.
- Strict superset of the flat B5 MLP (B5 = Tier-A diag + Tier-B only). G0 adds the per-action
  50 scalars + a per-action reranker head, so "G0 > B5" attributes the gain to the per-action
  relational-lite representation, not the scheduler target.

### G1 — typed message-passing GNN (the relational test)
- **Graph** (`graphs.pkl`, per root): 8 node types — `tile, city_feature, road_feature,
  farm_feature, monastery_feature, player, meeple, deck_bucket` (+ an `_open` sentinel pooled
  node) — and 8 edge types (`tile_belongs_to_feature, city_touches_farm,
  feature_touches_feature, meeple_on_feature, meeple_belongs_to_player, player_owns_feature,
  player_contests_feature, feature_has_open_boundary`). Node attr order frozen in
  `model.NODE_SPECS`; owner/feature-type categoricals mapped to scalars; standardized per node
  type on TRAIN. `legal_action` nodes are NOT in the graph — action features live in
  `rows_feat.npz` and condition the G4 head by concatenation.
- **Encoder**: per-type Linear(d_t→64) + learned type embedding(64).
- **3 hetero conv layers**: per-(edge-type, direction) Linear message → mean-aggregate per
  destination node → GRUCell self-update per node type. Both forward and reverse directions.
  The message-passing index plan is precomputed once per graph (`tensorize_graph`); graphs are
  batched by disjoint-union (`collate_graphs`, scatter mean/max pool) for ~2× train speed — the
  batched path is bit-identical to the per-graph path (verified |Δ| < 2e-7).
- **Readout**: masked mean‖max per node type + per-root diag → Linear→64 graph embedding.
- **G3 head**: graph embedding → MLP → root logit P(h200 wrong).
- **G4 head**: `act_enc(50-scalars)` ‖ graph embedding → MLP → per-action score.
- `h=64, layers=3`. Param count in `train_summary.json` (~0.97M; ~16× G0's ~60K).

## Heads / targets (both models)
- **G3 escalation**: BCE on `pos_strong` (q_gap_6400≥0.02 ∧ regret(h200)≥0.02), positives
  weighted by `1 + 30·regret(h200)`. Early-stop on VAL AUROC(pos_strong).
- **G4 reranker**: listwise softmax-cross-entropy of the per-action score toward
  `softmax(q6400/0.05)` within a root, example-weighted by `1 + 20·q_gap_6400`. Early-stop on
  VAL decisive-tail selected-move regret vs h6400.

## Split / leakage
`psr_lib.seed_split` (70/15/15 by game_seed; 270 tr / 64 va / 66 te seeds). Verified identical
to the baselines TEST set (same 1672 group_ids). No root crosses a split; no group spans a seed.
Decisive-tail sizes: tr 186 / va 55 / te 46; pos_strong tr ≈ 186 (see train_summary).

## Sanity (per spec)
Each model must fit the train signal (train AUROC clearly > 0.5, ideally ≳ B5's 0.78 on val).
Realized fit + early-stop selections: `data/train_summary.json` + `FGSR_TRAINING.md`.
