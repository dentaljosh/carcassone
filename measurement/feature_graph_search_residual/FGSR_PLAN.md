# FGSR_PLAN.md — Feature-Graph Search-Residual Architecture Pilot

> **STATUS: 🔴 CONCLUDED — DECISION B.** Full pipeline run through the offline gate
> (Stage 6), which **FAILED** → stopped per spec (no search integration, no games).
> Feasibility PASSED (tail-signal 0.80); dataset built (168,567 rows); but neither
> G0 (graph-lite) nor **G1 (typed GNN, test AUROC 0.559)** beats `low_top2gap` (0.725)
> or the flat MLP (0.78) at matched compute, and a graph-ablation shows the relational
> structure is **inert**. See [FGSR_DECISION.md](FGSR_DECISION.md) /
> [FGSR_OFFLINE_RESULTS.md](FGSR_OFFLINE_RESULTS.md). v2.9 / PRODUCTION.yaml untouched;
> nothing promoted; learned-flywheel line stays CLOSED. **CL-036.**
>
> _Last updated 2026-06-29._
>
> **Decision (2026-06-29, Joshua):** proceed to the cheap feasibility gate **and**
> build the full graph dataset on the 10,351 existing roots before any training
> (report after the build, before training); run **both** G3 (adaptive scheduler)
> and G4 (constant-compute reranker) through the offline gate with **equal** weight
> — not reranker-first. The reranker remains the more *interesting* test (only
> strength-lever framing), but both are gated equally vs `low_top2gap`.

## The one-line question

**Can a Carcassonne-native feature-graph / action-conditioned model learn the
residual that survives shallow search — i.e. beat `h6400 − h200` where every
prior learned component (policy, scalar value, flat-feature comparator/MLP)
either washed out under search or only tied the `low_top2gap` heuristic?**

If yes → first plausible route back to a learned flywheel. If no → the
learned-flywheel chapter stays closed until a much larger architecture/teacher change.

## Hard constraints (echoed so this doc is self-contained)

- Do **not** change the v2.9 evaluator or `governance/PRODUCTION.yaml`.
- Do **not** promote any checkpoint. Do **not** run a RoD flywheel.
- Do **not** train policy, the old scalar value head, or optimize static-leaf regret.
- Do **not** treat root agreement as strength.
- Do **not** run games until the offline + search gates pass.
- Do **not** use cluster-scale compute before the cheap feasibility gate passes.
- Do **not** let this become an unbounded architecture rewrite.

## Stage 0 finding #1 — feasibility: **Decision A risk is LOW**

A real feature graph is cheap, because the production leaf already builds the
decomposition. `flat_leaf.decompose(state) → Decomp`
([src/carcassonne_ai/flat_leaf.py](../../src/carcassonne_ai/flat_leaf.py)) returns a
pure-int union-find decomposition that **already enumerates every city/road/farm
component as a root id** with the attributes a graph node needs:

| Object | Already in `Decomp` | Fields |
|---|---|---|
| city component | ✅ | `city_root_coords` (tiles), `city_root_finished`, `city_root_open_n` (open edges), `city_root_delta` (closure score), `city_side_root` (reverse map) |
| road component | ✅ | `road_root_coords`, `road_root_finished`, `road_side_root` |
| farm component | ✅ | `farm_root_keys` (tiles), `farm_root_adj_city_roots`, `farm_root_finished_cities`, `farm_*_root` |
| meeple→feature | ✅ derivable | `state.placed_meeples[p]` + `*_side_root` + `_winners()` → owner/contested per root |
| monastery / player / deck / open-boundary | ✅ cheap | direct `state` attrs (`board`, `scores`, `meeples`, `deck`, `open_positions`) |

**Cost:** `decompose` is ~45 % of leaf time but is a **pure function of the
board** → memo-cache by board hash (same mechanism as the legal-moves cache).
We extract the graph **once per ROOT**, not per leaf; the residual dataset's 10 k
roots are already replayed once by the residual pilot's
`extract_root_features.py`, so adding graph emission is an extension of an
existing CPU pass — **no new deep searches**. Schema infeasibility is not the
blocker.

## Stage 0 finding #2 — the REAL risk: **magnitude ceiling, not representation**

This pilot is a sharper retry of the **Post-Search Residual / Adaptive-Compute
pilot** ([../post_search_residual/POST_SEARCH_DECISION.md](../post_search_residual/POST_SEARCH_DECISION.md)),
which already closed as **Decision C** with numbers that bound what *any* model
here can win:

| Quantity (tanh-Q, Phase-B MCTS roots) | Value |
|---|---|
| mean `h200` regret vs `h6400` | **0.0031** |
| median `h200` regret | 0.0000 (60 % of roots: h200 == h6400 top move) |
| oracle multi-depth ceiling removed @ C=400 | ~0.0016 (52 % of mean) |
| `low_top2gap` heuristic achievable @ C=400 | ~0.0003–0.0006 |
| best prior **32-feature MLP** AUROC (pos_strong) | 0.780 vs heuristic 0.725 |
| P(MLP beats heuristic @ C=400, bootstrap) | **0.92 < 0.95** → tie within noise |

So the honest prior is: **even a perfect router only removes ~0.0016 tanh-Q, and
the residual pilot judged the achievable slice "likely below game resolution."**
The most probable FGSR outcomes are **Decision B** (graph ties the scalar MLP /
heuristic) or **Decision C** (graph beats scalars offline but not enough to
matter). **Decision F/H (games improve) is a genuine long shot** and we should
say so up front rather than discover it at Stage 8.

**What is genuinely new vs the residual pilot** (and worth the cheap test):
1. **Relational representation.** The prior MLP ate 32 *flat* scalars. The open
   question the comparator pilot raised — "representation, not reweighting, drove
   the offline win" — was never tested on the *post-search* residual with an
   actually-relational model. FGSR answers "does graph structure beat flat
   scalars on `h6400 − h200`?"
2. **Two distinct value propositions, kept separate** (the residual pilot only
   tested #a):
   - **(a) Adaptive-compute scheduler** — predict which roots h200 gets wrong,
     escalate those to h800/h3200. Ceiling = the 0.0016 oracle gap above. Known small.
   - **(b) Constant-compute reranker (the more valuable test)** — at *fixed* h200
     budget, re-rank h200's top-k explored children toward h6400's choice on the
     decisive tail (q_gap≥0.02 & regret≥0.02, ~2.8 % of roots, where h200 plays a
     *materially wrong* move). This is a strength lever at constant compute, not an
     efficiency lever. The comparator pilot's negative ("search subsumes static
     reranking") used *static-leaf* features and a different target; whether a
     *relational* model trained on the *post-search* residual can re-rank h200's
     own backed-up Q is untested. **This is the primary question.**

**Recommendation:** lead with (b) the decisive-tail reranker as the headline
test, carry (a) the scheduler as secondary. Reason: (a)'s ceiling is already
measured and small; (b) is the only framing that could produce a strength (not
efficiency) contribution, and it's the most direct form of "can structure beat
shallow search."

## Reused infrastructure (the spine — exact paths)

**Pillar 1 — comparator pilot feature extractor + model/eval harness**
`scripts/feature_graph/`:
- `build_feat_dataset.py::_process / _struct_summary / _opp_feature_touched /
  _completed_value` — 50 per-(root,child) scalars (13 leaf-component, 28
  structural/action, 9 context). **These ARE the `legal_action`-node attributes.**
  State-agnostic → reuse the functions, recompute on residual roots.
- `eval_lib.py::load_rows / seed_split / make_groups / group_eval / summarize /
  decisive_mask` — grouping + regret/top-1/τ/decisive-tail metrics. Reuse as-is.
- `run_offline.py::ridge_fit / torch_mlp_residual` — scalar baselines (we need
  these as B5 anyway).

**Pillar 2 — residual pilot dataset + baseline + matched-compute/bootstrap harness**
`measurement/post_search_residual/data/` + `scripts/post_search_residual/`:
- `data/roots_mcts.jsonl` — **10,351 roots** (real MCTS-play distribution), each
  with `levels = {200,400,800,1600,3200,6400} → {action:(N, Q_rootpov)}` in tanh-Q,
  `seed/game_id/ply` for lossless replay, `root_player`, `phase`, `legal_n`.
  `data/roots_adaptive.jsonl` — 3,000 greedy-self-play roots.
- `data/games_mcts.jsonl` — action sequences for replay. `data/features_mcts.jsonl`
  — the prior 21 structural scalars (Tier-B) per root.
- `psr_lib.py::load_roots / seed_split / regret derivation / labels`
  (`pos_strong` = q_gap_6400≥0.02 ∧ regret(h200)≥0.02 = 2.8 %; `pos_medium` = 5.2 %;
  `negative` = 91.3 %).
- `run_adaptive_gate.py` / `run_baselines.py` — `low_top2gap` baseline
  (`score = −top2_q_gap200`, AUROC 0.725), matched-compute simulation
  (`best_adaptive`, budgets C∈{300,400,600,800,1200}), multi-depth oracle frontier
  (`md_oracle_at`), and the **2000-resample bootstrap** P(model beats heuristic) + CI.
  **This is the exact Stage-3/6 gate harness — reuse verbatim, swap in the graph model's scores.**

**Pillar 3 — measurement_infra** `scripts/measurement_infra/`:
- `snapshot_search(agent, board, levels)` → one deep search, all levels bit-exact
  (only needed if we mine NEW roots; the existing 10 k already have all levels).
- `root_replay.replay_actions(deck_seed, actions, ply)` → lossless `(game, board)`.
- `tagging.tag_from_snaps(snaps, level)` → top2_q_gap / entropy / top_share.
- `frozen_v29_cfg()` (config_hash `7fc930b82801cb43`) — pin the leaf.

## What we actually build (small, bounded)

1. **Graph extractor** — `decompose(state)` + `state` → typed node/edge tensors
   (schema in [FGSR_SCHEMA.md](FGSR_SCHEMA.md)). Reuses Decomp fields + the
   comparator's per-child scalars as `legal_action`-node attributes. ~one module.
2. **Graph dataset emitter** — extend the residual pilot's replay pass to attach a
   graph + per-child action features to each of the 10,351 roots (labels/Q already
   present). CPU-only, no deep search.
3. **Minimal graph model** — start at **G0 graph-lite MLP** (bridge), then **G1
   typed message-passing / token-transformer** only if G0 shows life. No giant
   stack before signal.
4. **Offline gate** — graph model's escalation score + reranking, run through
   Pillar-2's matched-compute + bootstrap harness, vs `low_top2gap` and the
   32-feature MLP.

## Cheap → expensive ladder (cost discipline)

| Step | Cost | Gate |
|---|---|---|
| Graph extraction on ~50 roots, verify schema + measure per-root ms | seconds, local | **cheap feasibility gate (next step after review)** |
| Full graph dataset on 10,351 existing roots (CPU replay+decompose) | minutes, local 1 box | — |
| Train G0/G1 offline, run matched-compute + bootstrap gate | minutes, local (no GPU needed for a small model) | **Stage 6 OFFLINE GATE — the critical one** |
| Search integration (re-run h200 + escalate/rerank live) | small, local | Stage 7 |
| Paired games n=100–200 | hours, **ask which box** | Stage 8 |
| New deep-search root mining (only if tail too thin) | hours, cluster | only if justified |

**No GPU/cluster spend is needed until the offline gate passes.** The graph is
small (≤ a few dozen nodes/root); a small GNN trains on CPU in minutes.

## Gate plan (pass criteria — from the spec)

- **Stage 6 (critical):** graph model must **beat `low_top2gap` AND the 32-feature
  MLP at matched compute**, with bootstrap CI not crossing zero, on held-out roots,
  on ≥1 source/phase robustness split — not merely beat the static leaf. Suggested:
  ≥10–20 % tail-regret reduction over `low_top2gap`, or a materially better
  compute-efficiency curve. **Fail → write FGSR_DECISION.md, stop, no search, no games.**
- **Stage 7:** integration must preserve the offline win (actual ≈ simulated),
  acceptable runtime overhead.
- **Stage 8:** paired games at matched average compute must directionally improve
  before topping up to n=400.

## Proposed next step (post-review)

**Cheap feasibility gate (Stage 0.5):** extract the graph for ~50 sampled residual
roots, dump node/edge counts + per-root extraction time, and sanity-check that the
schema captures the decisive-tail signal (e.g. that contested-control / open-edge /
meeple-lockup nodes vary across the children h6400 and h200 disagree on). If the
graph is well-formed and cheap → proceed to Stage 2. If extraction is fragile or
the graph carries no tail signal → Decision A and stop.

**Governance:** not a flywheel unless games improve; not recursive unless a second
generation improves from first-gen labels; no cluster spend before the offline gate.

## Decision space (restated for the close)

A schema infeasible · B graph = scalars (no signal beyond simple features) ·
C graph > scalars offline but not > `low_top2gap` · D graph > heuristic offline but
search integration fails · E search/root improves but games don't (root-metric
trap) · **F graph-adaptive improves games** (first real learned contribution) ·
G graph useful only for diagnostics / v2.10 heuristic archaeology ·
H full resurrection (games improve **and** the better search yields better labels
for a next round).

**Honest prior after Stage 0: most likely B or C; G is a useful consolation
(structure → v2.10 heuristic); F/H are the long shot we are testing for.**
