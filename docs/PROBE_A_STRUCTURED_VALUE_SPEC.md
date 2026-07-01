# PROBE A — STRUCTURE-EMITTING VALUE HEAD (as the leaf) — 2026-06-30 (DRAFT, awaiting Joshua approval)

Pre-registered design spec for the first of two post-Gate-B AlphaZero-family probes. Read with
the companion [PROBE_B_FAIR_INFO_SPEC.md](PROBE_B_FAIR_INFO_SPEC.md), the Gate-B autopsy in
[DECISIONS.md](../DECISIONS.md) (2026-06-30 entry), [PeNS_SCHEMA.md](PeNS_SCHEMA.md), and the
charter's abandonment criteria ([PROJECT_CHARTER.md](../PROJECT_CHARTER.md) §"Abandonment / redesign").

> **Status: SPEC ONLY — no implementation, no runs, no cluster spend.** This document pre-registers
> hypotheses, gates, and kill criteria *before* any run (boxing rule 1). Nothing here is authorized to
> execute until Joshua signs off on the plan and the shared time-box (see §7). This is the **structured**
> object Gate-B did **not** test; it is not a re-run of any cleanly-killed lever (see §0.3).

> **Reconciled against live repo state 2026-06-30.** The brief's factual basis checks out (CL-038 =
> genuine Gate-B, three nails, τ/additive/frozen numbers, 10,067 sibling sets, 50 scalars). Corrections
> folded in: (i) the per-component decomposition and the per-term supervision target are **two different
> callables** (`flat_leaf.decompose()` vs `leaf_v29.decompose_v29()`) — see §2; (ii) the speed bar is the
> **Cython** leaf, default-ON, not pure-Python — see §3; (iii) the additive-arm pre-gate harness
> (`eval_step2.py`) already threads the **real parent board** (`wants_parent=True`), so reusing it does
> **not** inherit the superseded zeroed-delta "wiring smoke" — verified 2026-06-30, see §4.

---

## 0. Framing (honest prior + boxing rules)

**Prior is modestly-positive-at-best.** The higher-EV project move is the analyzer pivot (endgame-2, the
original Phase-5 win condition, served by the already-proven sighted value head). This probe exists because
the Gate-B *mechanism* points here, not because the evidence says it will work. Spec it to run **boxed** and
die **fast**.

**Boxing rules (binding):**
1. Pre-register hypotheses, success metric, kill criterion — done here, before any run.
2. Time-box explicitly — §7, inside the shared ~10-day single-attempt envelope with Probe B.
3. **Gate on GAMES, not offline metrics.** Offline screens gate; the promotion bar is games. (Four-times-burned rule.)
4. **The bar is EXCEED or CLIMB, not parity.** Parity is a fail — RoD already reached parity and it wasn't enough.
5. Same kill-window discipline as Step 2: don't kill on a scary iter-3 number, don't resurrect on a hopeful
   iter-1 number. The read-out iter is pre-committed (§6).
6. If this probe **and** Probe B both fail their gates, the charter's abandon rule is satisfied → **ship the
   analyzer** (§6, failure path is clean and loses no analyzer work).

**Do NOT respec anything already cleanly killed.** This probe is checked against each: it is **not** the dense
scalar value leaf (Gate-B/CL-038); **not** the CL-034 sibling-*relative reranker* (fitted feature-reweighting,
washed out); **not** CL-030/031 policy distillation; **not** the CL-035 ML compute scheduler; **not** the CL-036
typed GNN on the *post-search residual* (graph embedding was inert — zeroing it *lowered* regret). This probe
**is the leaf**, evaluated at every MCTS node, aggregating per-component the way `virtual_score` does. That
specific object was never tested. (§0.3 records the falsification check in full.)

### 0.3 — Distinctness ledger (why this is not a dead lever)

| Dead lever | What it was | Why Probe A ≠ it |
|---|---|---|
| CL-038 scalar value leaf | one scalar per board, weaned into leaf | Probe A emits **per-component** values, not one scalar — the exact axis the mechanism blames |
| CL-034 feature-graph comparator | sibling-**relative** reranker over 50 scalars | Probe A is an **absolute leaf** at every node, not a top-of-search reranker |
| CL-036 typed GNN | predicts **post-search residual** with a graph embedding | Probe A predicts the **leaf value itself**, and the graph is structural bookkeeping, not an embedding added to a scalar |
| CL-035 ML scheduler | learned compute allocation | unrelated |
| CL-030/031 policy distillation | learned **policy**, any target | Probe A is a **value** object |

If, during build, the object reduces to any row above (e.g. the per-component head collapses to a global scalar
under aggregation, or the only signal it adds is a sibling-relative reranking), **stop and say so** — that is a
kill, not a pivot.

---

## 1. Hypothesis (pre-registered)

A value head that emits **per-component values that aggregate the way the heuristic's do** — rather than
collapsing the board to one scalar — preserves the cross-node **magnitude-commensurability** that search
needs, and can therefore drive the leaf where the scalar could not.

Formally the leaf is

```
v_leaf(s) = aggregate( g_θ(component_i) for component_i in decompose(s) )
```

where `decompose` is the union-find the leaf already computes, `g_θ` is a *learned* per-component evaluator
replacing the heuristic's hand-tuned per-component terms, and `aggregate` is matched to the heuristic leaf's
own aggregation so `v_leaf` is a **drop-in leaf** at every MCTS node.

**Mechanism being tested (the load-bearing Gate-B finding):** search needs *commensurable magnitudes across
backed-up nodes*; a scalar value collapses the per-component structure that makes magnitudes commensurable, so
small magnitude errors compound multiplicatively through backup. The heuristic's magnitudes are commensurable
*because* they are computed from per-component structure (per-city closure, per-farm connectivity, per-road,
meeple economy). The bet: keep the structure, learn the terms.

**Null (what Gate-B already established, that this must beat):** a learned value can order siblings well
(interior-τ 0.42–0.45 at every depth, +43% offline regret) and still be a bad *search substrate* (additive arm
0.500→0.285; frozen-warmstart 0.215). Probe A fails if the structured object shows the **same signature**.

---

## 2. Reuse map (verified paths — a spec that rebuilds any of these is wrong)

| Piece | Path | Role in Probe A |
|---|---|---|
| Union-find decomposition | [`src/carcassonne_ai/flat_leaf.py`](../src/carcassonne_ai/flat_leaf.py) `decompose(state) -> Decomp` | **the component set** `g_θ` runs over — per-city/road/farm roots + positions/finished/open-n/delta (frozensets/dicts/ints). No engine objects. |
| Heuristic per-term breakdown | [`src/carcassonne_ai/leaf_v29.py:203`](../src/carcassonne_ai/leaf_v29.py#L203) `decompose_v29(state, player, cfg) -> dict` | **pretraining target (i)** — the heuristic's *own* per-component decomposition (`closure_self`, `closure_opp`, `meeple_flat`, `farm_access_delta`, …). Supervise `g_θ` against these terms first. |
| Cython leaf (speed bar) | `flat_leaf_cy.flat_virtual_score_v2_cy` (`CARCASSONNE_USE_CY_LEAF=1`, default-ON) | **gate-zero baseline** — the per-node time budget `g_θ` must meet. |
| Feature-graph extractor | [`scripts/feature_graph_search_residual/extract_graph.py`](../scripts/feature_graph_search_residual/extract_graph.py) + `data/graphs.pkl` | typed per-component node/edge features, net-free, CPU-only, memoizes `decompose`. Reuse for `g_θ`'s per-component input featurization. |
| 50 per-action scalars (CL-034) | [`scripts/step2_pens/build_dataset.py`](../scripts/step2_pens/build_dataset.py) `FEAT_NAMES`; live: [`src/carcassonne_ai/step2_leaf.py`](../src/carcassonne_ai/step2_leaf.py) `extract_step2_features` | available as auxiliary per-component/context features; do **not** rebuild the comparator (CL-034 is dead). |
| h6400_v2.9 sibling sets (10,067 roots) | reproduced via `gen_endgame_positions.replay_to(seed, ply, checksum)`; labels cached `measurement/high_gap_distillation/qprobe/probe.jsonl` + `measurement/feature_graph_search_residual/data/` | **fine-tune target (ii)** and the offline regret ruler (non-saturated). |
| Wean-blend training loop | [`scripts/step2_pens/train_warmstart.py`](../scripts/step2_pens/train_warmstart.py) (`ScalarMLP`, `listnet_loss`, α-sweep, md5 `bucket()` split) | reuse the loop/splits; swap `ScalarMLP` for the structured head. TEST split is bit-identical to Step-1. |
| Additive-arm screen | [`scripts/step2_pens/eval_step2.py`](../scripts/step2_pens/eval_step2.py) + `step2_leaf.make_step2_value_wrapper` (`wants_parent=True`, `leaf_mode="additive"`) | **the offline pre-gate** (§4). Already parent-threaded (Path A, commit `47c6e17`). |

---

## 3. Gate zero — leaf-speed feasibility (decisive, cheap, runs FIRST)

**The binding constraint.** The heuristic leaf is DRAM-latency-bound and evaluated **millions of times per
game**; the flat leaf is ~2.3× the object version *because leaf speed dominates the cycle*. A neural
per-component head that cannot be evaluated at ~leaf speed **cannot drive search** and is dead on arrival
regardless of accuracy.

**Baseline.** Per-node wall-time of `flat_leaf_cy.flat_virtual_score_v2_cy` (default-ON Cython path), measured
on the production self-play path, not pure-Python. **The bar is the compiled leaf.**

**Pre-registered budget.** `g_θ`-aggregated `v_leaf` must land within **≤ 3× the Cython leaf per node** on the
production path (proposed ceiling — the scalar-net leaf already costs a forward per node and search tolerated
that; 3× is the headroom before leaf cost re-dominates the cycle and halves games-per-hour). If a candidate
implementation cannot be shown (by micro-bench + a short W-parallel A/B on games-per-hour) to hit ≤3×, **gate
zero fails and the probe is a non-starter — say so before any training.**

**Feasibility levers to spec (at least one must clear the budget):**
- **Tiny per-component MLP** — `g_θ` is a 2–3 layer MLP on a small fixed per-component feature vector; components
  per board are O(tens), so cost ≈ (n_components × tiny-forward) + aggregate.
- **Component-value memoization across the tree** — components persist as tiles are added (a closed city never
  re-opens); key `g_θ(component_i)` by the component's identity and reuse across sibling/child nodes that share it.
  This is the highest-leverage lever and is unique to the structured object (a scalar leaf can't memoize sub-values).
- **Cached component embeddings** — precompute `g_θ` inputs once per component, refresh only touched components.
- **Distilled lookup** — if `g_θ` turns out low-rank over the realized component space, distil to a table.

**Deliverable of gate zero:** a per-node budget number, the chosen lever, a micro-bench vs the Cython leaf, and a
games-per-hour A/B stub. **Pass/fail is read before any training compute is spent.**

---

## 3A. Farm/bag independence pre-gate — "is there room at all" (before ANY in-loop budget)

**This is the load-bearing test of whether Probe A has room at all** — cheaper than the crater screen (§4) and
the loop (§6), so a kill here saves both. It re-runs the **CL-037 farm/bag ablation** on the *structured* head.

**Established fact (the null this must break) — CL-037** (charter Step-1 representation gate, DECISIONS 2026-06-29,
`measurement/feature_planes_gate/STEP1_GATE_RESULTS.md`): giving the *scalar/dense* value-ranker farm-connectivity
planes **and** a bag/deck-composition histogram flipped its inertness (α 0→0.05, regret −20.5%), but the **farm/bag
attribution came back LARGELY REDUNDANT**: farm-only **−17.1%**, bag-only **−19.7%**, both **−20.5%** — each alone
recovers most of the signal; the second adds little (the +0.8pp increment is within the n=1544 noise). The bag axis
is information the v2.7/v2.9 leaf **structurally cannot see** (it scores the board, not the remaining draw).

**The hypothesis Probe A stakes its thesis on.** If the scalar *merged* farm and bag into one redundant direction
*because a scalar collapses structure*, then the structured head — which preserves the per-component structure —
should let them load onto **independent** directions: `both` should recover a meaningful gain **over the best
single**. If instead they **stay redundant even in the structured head**, the game's value signal is genuinely
**low-dimensional** (not a scalar-bottleneck artifact), the structured object has nothing to preserve that the
scalar destroyed, and Probe A's whole thesis is empty.

**Design implication (surface it — this is a real head-architecture addition).** To run this ablation the
structured head must ingest **both** axes: farm-connectivity is already in the per-component features (farm
components carry `farm_root_adj_city_roots` / farm-potential — cols 12–14 of the frozen 24-dim contract), but
**bag-composition is NOT in the current per-component contract** (only col 18 `econ_k_remaining` ≈ deck completion).
The 32-dim bag/deck histogram must be added as a **board-level side-input to the aggregate** (e.g. on the econ
pseudo-row or a separate board-context vector fed alongside `Σ g_θ(comp_i)`) before this gate can run. Pre-register
that addition as part of the head; keep the aggregate a pure sum so the leaf stays a drop-in.

**Pre-registered metric + threshold.** Re-run the CL-037 ablation on the **structured head's own offline
sibling-regret eval** — same 10,067 h6400_v2.9 sibling sets, same regret metric, same group-split (n_test=1544
groups; scale n up if the margin below needs a tighter σ). Train/fit the structured head under three input regimes
— **farm-only, bag-only, both** — and read the regret improvement of each.
- **Independence statistic:** `Δ_indep = regret_gain(both) − max(regret_gain(farm-only), regret_gain(bag-only))`.
- **"Separated" threshold:** `Δ_indep ≥ 3pp` (≈ 2σ at n=1544; CL-037's scalar `Δ_indep ≈ +0.8pp` was sub-noise =
  redundant). Pre-register the exact margin against the measured eval σ before reading the result.

**Read-out point.** Immediately after g_θ training (milestone 2 delivers the head), **before the crater screen (§4)
and before any in-loop budget (§6).** Ordering note: gate-zero's *speed* micro-bench (§3) has already run and passed
(additive arm 2.56×, committed `16dcd02`); this gate needs a trained head so it cannot literally precede training,
but it is the **cheapest of the offline gates**, so it runs first among them — a kill here saves the crater screen
and the loop, which is exactly Joshua's "cheap kill first" intent.

**Kill / continue branch:**
- **Redundant** (`Δ_indep < 3pp`, farm/bag stay substitutes in the structured head) → **KILL Probe A here.** The
  value signal is genuinely low-dimensional; the scalar was *not* the bottleneck; the structured object extracts
  nothing the scalar destroyed. Do **not** spend the crater screen or the loop. Combined with Probe B's outcome
  this routes to the analyzer (§6).
- **Separated** (`Δ_indep ≥ 3pp`, structured head gives farm and bag independent contributions) → **first real
  evidence the scalar was the bottleneck** → proceed to the crater screen (§4) and, if it clears, the in-loop (§6).

**Not a duplicate of CL-037.** CL-037 established the redundancy *in the scalar/dense ranker*; this gate tests
whether the *structured object breaks* it — the thesis test, not a repeat. It also does not duplicate Probe B's
fair-target bag test (§4A there): this is clairvoyant-target, scalar-vs-structured; that is fair-vs-clairvoyant
targets on the same-arch head. Different variable held fixed in each.

---

## 4. Offline pre-gate — the exact test the scalar failed

Before any loop: swap the structured leaf in **at fixed sims** and check it does **not** reproduce the additive
crater. Reuse [`eval_step2.py`](../scripts/step2_pens/eval_step2.py) `leaf_mode="additive"` with the structured
head in place of `ScalarMLP`.

- **Setup:** heuristic held at full strength, structured value added on top (additive arm) — identical protocol
  to Nail 2. Paired games (deck both seats), seat-balanced, `sims=100` (Nail-2 config), n pre-registered to the
  effect (n=400 paired → ±12 elo; a crater like 0.500→0.285 is resolvable at n≈120, but size n to the *pass*
  case where the effect is small).
- **Spec check (rider 3):** confirm the pre-gate config keeps `wants_parent=True` (real parent-threaded delta
  features) — **no silent zeroed-delta fallback.** Nail 2 was measured parent-threaded ([step2_leaf.py:335](../src/carcassonne_ai/step2_leaf.py#L335); commit `47c6e17`); the pre-gate must inherit that, not the superseded smoke.
- **Also run the convex/wean-blend arm** as a second read (Step-2 used both `additive` and `convex`).

**Pre-gate pass:** structured leaf **match-or-beats** the pure-heuristic leaf in the paired additive screen at
equal compute (i.e., avoids the crater). **Pre-gate fail (same signature as Step 2):** it craters → the
structured object also can't add magnitude-consistent value → **kill** (this is a real kill, not a "try harder";
it means structure did not fix the mechanism).

Only a pre-gate **pass** earns in-loop budget.

---

## 5. Training target — pointed at the mechanism, not at accuracy

We already have a good ranker that failed; do not build another. Target a magnitude-consistent **substrate**:

1. **Structure-first supervision (i):** train `g_θ` per-component against the heuristic's own per-term
   decomposition `leaf_v29.decompose_v29()` — does the head *reproduce the leaf's structure at leaf speed*?
   Success metric: per-term reconstruction + aggregate-reconstruction of `virtual_score_v2` within tolerance,
   at the gate-zero speed. (If it can only match by relearning the heuristic exactly, that is informative — see
   the open question on relearning the ceiling.)
2. **Aggregate fine-tune (ii):** fine-tune the aggregate against `h6400` root-Q / search-Q on the 10,067 sibling
   sets, **with the per-component structure held as an architectural constraint** (aggregation fixed to the
   heuristic's form; only `g_θ` learns). The point is magnitude-commensurability across nodes, so the loss must
   penalize *magnitude* error, not just rank — pair an MSE-on-aggregate term with a per-component magnitude
   regularizer, and explicitly *not* a pure ListNet rank loss (rank is the thing that already passed and lost).

---

## 6. In-loop test + pre-registered success / kill

**Only if gate-zero passes and the offline pre-gate passes.** Run the crutch-wean loop (Step-2 protocol) with
the structured head as the weaned-in leaf, gated on **games vs `h6400_v2.9`** on **fresh seed bands** (never a
band the head trained/selected on; same-band paired composes, cross-band stacks noise).

**Pre-committed read-out iter:** verdict is read at **iter 6** of the wean loop (matches Step-2's kill-window;
no kill before iter 3 on a scary number, no resurrection on a hopeful iter-1). Held-out cumulative SEALED
measure decides, **read at low sims** (net/leaf effects wash out under deep MCTS — the sims-washout trap;
measure at the sims the leaf actually drives, not 800).

- **SUCCESS:** the structured leaf **exceeds** the v2.9 heuristic leaf in games at equal compute on fresh bands
  (the thing the scalar could not) — margin ≥ 2σ at the pre-registered n — **OR** a **positive multi-iteration
  derivative** in the wean loop (climb, not parity) sustained through the read-out iter.
- **KILL (any one):** (a) structured leaf still craters when added/weaned (Step-2 signature); (b) **fails gate
  zero** (too slow); (c) passes offline but **washes out in the loop** (CL-034 pattern); (d) reduces to a dead
  lever (§0.3). Any → the **value-leaf route is dead across both scalar and structured objects**. Combined with a
  Probe-B kill this satisfies the charter abandon rule → **stop and ship the analyzer** (endgame-2), served by
  the already-proven sighted value head. No analyzer work is lost; it is only deferred (DECISIONS 2026-05-28).

---

## 7. Time-box (inside the shared ~10-day single-attempt envelope with Probe B)

Charter budget note: the ratified "1 attempt / ≤10 days" ([PROJECT_CHARTER.md:175](../PROJECT_CHARTER.md#L175))
was relaxed 2026-06-08 pm (≤2-attempt cap lifted, pivot clock paused) and the whole PeNS program ran since, with
no fresh numeric budget restated post-Gate-B. Per Joshua's rider, A+B are boxed as **one ~10-day single-attempt
envelope**:

| Stage | Budget | Notes |
|---|---|---|
| Gate zero (speed) | ~0.5 day | micro-bench + games/hr A/B vs Cython leaf; **front-loaded, decisive** |
| Structure-first supervision (i) | ~1 day | reproduce `decompose_v29` terms at leaf speed |
| Offline pre-gate (additive swap) | ~1.5 days | includes fine-tune (ii); parallel with Probe B's offline screen |
| In-loop wean (only if pre-gate passes) | ~4–6 days | read-out at iter 6 |

**Envelope trigger (rider 2):** the expensive in-loop budget is spent on **at most one probe**. If **both** A and
B clear their offline pre-gates, that is an **explicit budget decision for Joshua**, not a silent overrun; A is
sequenced first (brief's ordering: A's gate-zero is the cheap decisive one). No cluster spend before sign-off.

---

## 8. Open questions the build must resolve

1. **Component keying/caching across the tree.** How are components identified so `g_θ(component_i)` memoizes
   across sibling/child nodes? Do contested/merged features (two players' meeples, a city merge on tile placement)
   break the drop-in aggregation, and if so does aggregation degrade gracefully or corrupt magnitudes?
2. **Distillability.** Can `g_θ` be distilled small enough for leaf speed without losing the magnitude signal the
   whole probe is about?
3. **Is "reproduce the heuristic's structure" the right pretraining target,** or does it just relearn the v2.7/v2.9
   *ceiling* the project is trying to exceed? Fine-tune (ii) is meant to move past the ceiling — but if (i) locks
   the head onto the heuristic and (ii) can't move it, that is itself a finding (the structure carries the ceiling,
   not just the commensurability). Pre-register that outcome as a **soft kill** distinct from the crater.
4. **Aggregation faithfulness.** Is matching the heuristic's aggregation exactly necessary for drop-in, or can a
   learned aggregate stay commensurable? (A learned aggregate risks re-collapsing to the scalar failure — treat
   with suspicion.)
