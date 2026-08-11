# Feature-Graph Action Comparator Pilot — PLAN

**Status:** CONCLUDED 2026-06-28 — **Decision C** (offline comparator beats v2.9 leaf, search can't use
it; washes out under MCTS). Stages 0–5 ran; Stage 6 games gated out. See `FEATURE_GRAPH_DECISION.md`.
**Opened:** 2026-06-28 · branch `rod_v2_flywheel`
**Owner doc.** Results live in the sibling `FEATURE_GRAPH_*_RESULTS.md` / `_DECISION.md`; this is the map.

---

## Core question

Can an **action-conditioned, feature-aware comparator** rank sibling child states better
than the v2.9 leaf — where the old *scalar* value/residual head failed?

```
old (dead):   state            -> scalar residual
this pilot:   parent S + move m + child S' + feature deltas -> relative score among siblings of S
```

The value problem MCTS needs is **not** generic outcome prediction; it is *"given this parent
and these legal children, which child should search prefer?"* We test exactly that object.

## Why this is not a re-run of a dead path (priors)

- v2.9 leaf is already a **strong sibling ranker**: τ≈0.895, top1≈0.455 vs h6400 — but it has a
  real **decisive-miss tail**: 1,197 / 10,067 roots with gap≥0.02 **and** regret≥0.02. A target exists.
- The Value Resurrection Pilot (Decision B, commit `3dfe092`) proved a learned **scalar**
  value/ranking *residual* cannot beat that leaf: best α on every learned component was **0**,
  regret rose monotonically with α; net-alone τ=0.105 vs leaf τ=0.895.
- The Value/Search autopsy (Decision D, `b99c9ed`) proved the scalar value head **inert** under
  search and that **root metrics do not predict strength** (gate strength on games, not agreement).

The open question those left: *was the head dead because learned value is hopeless, or because the
model lacked explicit Carcassonne feature/action structure?* This pilot changes the **representation
and the learned object** (action-conditioned, feature-level, sibling-relative) to answer that — then stops.

## Stage 0 verdict — FEASIBLE (Decision-A is NOT triggered)

1. **The expensive teacher labels already exist on disk.** No new search needed:
   - `measurement/high_gap_distillation/scaled/qprobe_A/probe.jsonl` — 10,067 roots, per-child
     `action_q` (h6400_v2.9 root-POV Q) keyed by action id; + `teacher_best`, `q_gap_1_2`, phase, k.
   - `/mnt/c/carc-shared/value_resurrection/dataset_v29_h6400/rows.npz` — 124,842 child rows with
     `oracle_q` (h6400), `leaf_q` (v2.9 leaf), `group_id`, `game_seed`, `ply`, `phase`, `q_gap`.
   - `measurement/value_resurrection_pilot/data/leaf_audit_rows.jsonl` — per-root τ/top1/top3/regret.
   - `measurement/value_search_autopsy/data/miss_probe.jsonl` — 1,321 decisive-miss out-of-pool slice.
   - Not on disk: h12800, bulk exact/endgame labels. **h6400 is the teacher**; that is sufficient.
2. **The new representation is cheaply extractable from existing code** (no engine changes):
   - `flat_leaf.decompose(state) -> Decomp` — city/road/farm root maps, open-edge counts, finished
     flags, closure deltas, farm↔city adjacency (one board pass, ~1–2 ms).
   - `leaf_v29.decompose_v29(state, player, cfg) -> dict` — **separable** v2.9 components (base,
     closure_self, closure_opp, meeple-curve term, pretransform/total). Exactly the "v2.9 component
     values if available" the schema asks for.
   - `replay_to(seed, ply)` (checksum-verified) reconstructs each parent; child enum via
     `game.get_next_state`; child leaf via `virtual_score_v2(child, root_player, cfg)`.

→ Schema IS feasible; data IS on disk. Proceed.

## Cost posture (what spends what)

| Stage | Compute | Spend | Cluster? |
|---|---|---|---|
| 0 schema | local read | none | no |
| 1 dataset | CPU replay+decompose over ~125k children, local, parallel (~minutes) | none | no (local) |
| 2 baselines | numpy/sklearn, seconds | none | no |
| 3 train cheap comparators | local GPU/CPU, seconds–minutes | none | no |
| 4 offline gate | numpy, seconds | none | no |
| 5 search screen | NMCTS over held-out roots, **gated on 4** | minutes | maybe local |
| 6 games | paired games vs h6400/h3200/iter04 — **gated on 5** | the only real spend | **laptop + local, rust orch, W30/W20** |

**No cluster, no metered spend until Stage 6** — and Stage 6 only fires if the comparator beats the
v2.9 leaf offline (Stage 4) **and** improves search diagnostics (Stage 5). I drive 0→4 locally and
stop at the Stage-4 gate for review before anything costs games.

## Cheapest-informative-first feature tiering

Stage 1 builds **two feature tiers** in one replay pass so baselines can ablate them:

- **Tier-1 (cheap, ~20 scalars):** the v2.9 leaf's OWN components (child) + their parent→child
  deltas + leaf_q + context. Pure `decompose_v29` calls. Tests: *can reweighting the leaf's own
  terms beat the leaf?* If yes → it was **weighting**, not representation.
- **Tier-2 (rich, +~30 scalars):** structural counts, contested control, meeple lockup/return,
  action/move semantics, open-edge deltas. Needs `Decomp` + meeple→root mapping. Tests: *does
  explicit feature/action structure beat the leaf?* If Tier-2 wins where Tier-1 didn't →
  **representation** was the issue (the pilot's headline claim).

Schema detail: `FEATURE_GRAPH_SCHEMA.md`.

## Built-in correctness gate (Stage 1)

The builder reuses the **exact** id-deduped, teacher-visited child enumeration of
`value_resurrection/dump_dataset.py` + `leaf_audit.py`. So my recomputed `leaf_q` must reproduce the
stored `leaf_q`, and my recomputed leaf-audit must reproduce **τ=0.895 / top1=0.455 / 1,197 decisive
misses**. If it doesn't, the pipeline is wrong — fail loudly, do not proceed.

## Gates & decision labels (Stage 7)

- **A** schema not feasible → *not triggered* (Stage 0 passed).
- **B** features feasible but v2.9 still unbeatable offline → current learned path stays dead.
- **C** beats v2.9 offline, NMCTS can't use it → integration/search issue.
- **D** search improves, games don't → root/search trap repeats; do not promote.
- **E** games improve → first real evidence for an architecture-change flywheel.
- **F** helps only one slice (opening / low-meeple / farms / decisive tail) → consider gated integration.

**Pass bars:** Stage 4 — beat v2.9 leaf on held-out selected-child regret (suggest ≥10–15% mean-regret
drop on the decisive tail, no broad ordinary regression, nonzero best-α if residual-style; full-pool win
is the higher bar). Stage 5 — search regret improves in the slice value won, limited ordinary regression,
not cosmetic root-agreement. Stage 6 — real movement vs h6400, no regression vs h3200/iter04/h200.

## Hard constraints (from the brief)

Do not change the v2.9 evaluator or `PRODUCTION.yaml`. No RoD flywheel. No policy training. The old
scalar residual head is a **baseline only**, not the main object. Don't optimize generic root agreement
as the success metric. No checkpoint promotion from offline metrics alone. No games until offline +
search gates pass. No architecture sprawl — cheap feature/action baselines first; a heavy GNN only if
they show promise.

## Stage roadmap → deliverables

| Stage | Deliverable |
|---|---|
| 0 feasibility + schema | `FEATURE_GRAPH_PLAN.md` (this), `FEATURE_GRAPH_SCHEMA.md` |
| 1 dataset | `FEATURE_GRAPH_DATASET.md` + `data/rows_feat.npz` (+ built-in audit reproduction) |
| 2 baselines | `FEATURE_GRAPH_BASELINES.md` |
| 3 train | `FEATURE_GRAPH_TRAINING.md` |
| 4 offline gate | `FEATURE_GRAPH_OFFLINE_RESULTS.md` **[GATE — stop for review]** |
| 5 search screen | `FEATURE_GRAPH_SEARCH_RESULTS.md` **[GATE]** |
| 6 games | `FEATURE_GRAPH_GAME_RESULTS.md` |
| 7 decision | `FEATURE_GRAPH_DECISION.md` |
