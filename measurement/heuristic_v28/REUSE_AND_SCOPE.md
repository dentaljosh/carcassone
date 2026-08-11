# v2.8 heuristic-leaf branch — REUSE & SCOPE (Phase 0)

> **Branch framing.** v2.8 is a candidate *classical-engine* heuristic leaf. It is **opt-in and
> versioned** until proven. **v2.7 stays frozen forever** as the historical reference ruler.
> This is ML progress ONLY if a later neural/hybrid search can *use, distill, or surpass* v2.8.
> Nothing here trains a model, runs a flywheel, or touches the production champion
> ([governance/PRODUCTION.yaml](../../governance/PRODUCTION.yaml): `flywheel2_champion_iter8`,
> NeuralMCTS@200, leaf `virtual_score_v2` = "v2.7", residual_scale 0.25, c_puct 3.0).
>
> **FACT vs INTERPRETATION** is marked throughout. Numbers cite artifact rows.

---

## 1. Where v2.7 lives (the code, exactly)

| Component | File | Notes |
|---|---|---|
| **v2.7 leaf (object path)** | [src/carcassonne_ai/virtual_score_v2.py](../../src/carcassonne_ai/virtual_score_v2.py) | `virtual_score_v2(state, player, cfg=None)` → `int`. v1 base + closure-anticipation bonus (self) − bonus (opp) + optional meeple term. **Already takes a `LeafConfig`** (`cfg`); None → `DEFAULT_CONFIG` (env-built). |
| **v1 base** | [src/carcassonne_ai/virtual_score.py](../../src/carcassonne_ai/virtual_score.py) | `virtual_score(state, player)` = engine `PointsCollector.count_final_scores` on a snapshot ("if the game ended now"). Scores incomplete features at partial value; farms count only `finished==True` cities. |
| **v2.7 leaf (flat hot path)** | [src/carcassonne_ai/flat_leaf.py](../../src/carcassonne_ai/flat_leaf.py) | `flat_virtual_score_v2` — de-objectified union-find, **bit-exact** under canonical fsum, ~2.26×/leaf. Production runs this (`CARCASSONNE_USE_FLAT_LEAF=1`). |
| **Flat redirect guard** | virtual_score_v2.py:459 | `if flat_leaf.USE_FLAT_LEAF and not (cfg.tile_counting_closure or cfg.closure_continuous_slack>0.0): return flat_leaf.flat_virtual_score_v2(...)`. **Experimental knobs the flat path doesn't implement fall through to the engine path** — the established opt-in pattern. |
| **LeafConfig** | virtual_score_v2.py:58–99 | `closure_p`, `bonus_cap`, `opp_bonus_cap`, `meeple_k`, `tile_counting_closure`, `closure_continuous_slack`, `value_blend`, `residual_scale`. Env defaults from `CARCASSONNE_V25_*`. |
| **Leaf in heuristic search** | [src/carcassonne_ai/mcts.py](../../src/carcassonne_ai/mcts.py):314–346 | `HeuristicMCTS(heur_leaf="v1"|"v2_7")`. When `"v2_7"` → calls `virtual_score_v2(board.state, leaf_player)` **with no cfg** (DEFAULT_CONFIG). **No way to pass a custom LeafConfig today** → see §2. |
| **Leaf as neural value** | [src/carcassonne_ai/evaluators.py](../../src/carcassonne_ai/evaluators.py):184–338 | `make_v25_value_wrapper(base, cfg=None)` / batch variant. Leaf value `tanh(virtual_score_v2(st, cp, cfg)/15)`, optional residual/blend. **Already cfg-parameterized.** |
| **Production env knobs** | PRODUCTION.yaml `play_config.env_knobs` | `V25_RESIDUAL_SCALE=0.25, V25_CAP=12, V25_DROP_THREE_OPEN=1, V25_VALUE_BLEND=0, USE_FLAT_LEAF=1`. |
| **Tests (parity patterns to mirror)** | [tests/test_virtual_score_v2.py](../../tests/test_virtual_score_v2.py) | `test_explicit_default_config_matches_no_config` (DEFAULT_CONFIG == no-cfg), `test_leaf_config_is_actually_threaded` (a non-default cfg CAN change output), `test_tile_counting_gate_only_reduces_bonus` (gate monotonicity). [tests/test_flat_leaf_edge_cases.py](../../tests/test_flat_leaf_edge_cases.py) for flat bit-parity. |

**What v2.7 actually computes** (so we don't re-propose what's already there):
- v1 base = end-of-game engine scoring of the *current* board (partial credit for open features).
- v2.7 adds, per placed meeple on an **incomplete** feature, `P(closure) × score-delta`:
  - city: delta = (full − partial) = T+S (or cathedral math); `P` from open-position count via `closure_p={1:0.5, 2:0.2}` (DROP_THREE_OPEN).
  - cloister/flowers: delta = `8 − n_surround`.
  - **farm-growth**: for each incomplete city adjacent to a farmed field, `+3 × P(closes)` (finished cities already in v1 farm score).
- Caps: self bonus ≤ `bonus_cap` (prod 12), opp bonus ≤ `opp_bonus_cap`; opponent bonus **subtracted** (denial signal already partially present).
- Optional (OFF in prod): `meeple_k·(meeples_self − meeples_opp)`, deck-aware tile-counting gate, continuous supply ramp, value_blend, residual_scale.

---

## 2. How to instantiate a new heuristic version WITHOUT modifying v2.7

**Mechanism (chosen): extend `LeafConfig` with v2.8 fields, all defaulting OFF, implemented inside
`virtual_score_v2` / `_closure_anticipation_bonus`.** This reuses the existing `cfg` threading and
gives bit-identical v2.7 when every v2.8 field is at its default. Three integration points:

1. **Leaf eval** — `virtual_score_v2(state, player, cfg)` already takes a cfg. New v2.8 fields read here.
2. **Flat fast path** — extend the redirect guard (virtual_score_v2.py:459) so any active v2.8 knob
   forces the engine path (the flat path does **not** implement v2.8). Same pattern as
   `tile_counting_closure`. → v2.7 with v2.8 OFF still hits `flat_virtual_score_v2` (bit-exact, fast).
3. **Heuristic search** — add `leaf_cfg: LeafConfig | None = None` to `HeuristicMCTS.__init__`,
   threaded into the `virtual_score_v2(...)` call (mcts.py:341). `None` → today's behavior exactly
   (DEFAULT_CONFIG). A v2.8 `heur@N` is `HeuristicMCTS(heur_leaf="v2_7", leaf_cfg=<v28 cfg>)`.
4. **Neural value (iter8-leaf swap)** — `make_v25_value_wrapper(base, cfg=<v28 cfg>)` already works;
   pass a v2.8 cfg to run `ITER8_PROD_WITH_V28_LEAF` as an **opt-in measurement wrapper** (never prod).

**Guarantees:** (a) v2.7 stays bit-identical under existing configs (DEFAULT_CONFIG / env knobs);
(b) every v2.8 variant is explicitly named and independently toggleable; (c) no production default
changes — env knobs keep all v2.8 fields off; the candidate cfg is constructed only inside v28 eval
scripts.

---

## 3. What diagnostics reveal about v2.7's failure modes (FACTS, cited)

Distinguish two leaf roles — **v2.7-static** (depth-0 argmax of `virtual_score_v2` over legal
afterstates) vs **iter8** (NeuralMCTS@200, net policy prior + v2.7 leaf value). The exact-solver
verdicts (L23/K4) measure *iter8* and the *heur@N search ladder*, **not** v2.7-static; v2.7-static-as-
selector is measured separately in the pre-tool, midgame, and root-action audits.

### 3a. v2.7-static as a selector — direct measurements
| Setting | v2.7-static | iter8 | heur@800 | heur@3200 | teacher/optimum | source row |
|---|---|---|---|---|---|---|
| **Exact K=2 top-1** | **0.682** | 0.687 | 0.773 | 0.847 | exact solver | [pre_tool BASELINE_RESULTS.csv](../pre_tool_audit/BASELINE_RESULTS.csv) `v2.7-action-score-only,2,all` |
| **Exact K=2 mean regret** | **0.843** | 0.573 | 0.487 | 0.373 | 0 | same row |
| **Midgame root top-1 vs teacher(h3200)** | **0.48** | 0.487 | 0.658 | 1.0 | h3200 | [ROOT_ACTION_RESULTS.csv](../search_policy_mixing/ROOT_ACTION_RESULTS.csv) `V27_STATIC_ROOT_ONLY` |
| **Midgame Kendall τ vs teacher** | **+0.61** | — | — | — | — | [MIDGAME_REFERENCE_REPORT.md](../midgame_reference/MIDGAME_REFERENCE_REPORT.md) |
| **Midgame top-1 (depth0 label)** | **0.48** | 0.487 | 0.658 | — | — | [MIDGAME_BASELINE_RESULTS.csv](../midgame_reference/MIDGAME_BASELINE_RESULTS.csv) `v2.7-static(depth0)` |

**Key reads (FACT):**
- v2.7-static ≈ iter8 at root selection (both ~0.48–0.49 vs teacher; ~0.68 vs exact K=2). The neural
  net does **not** beat its own static leaf at picking the root move — consistent with the
  "iter8 is ~95% policy distillation of the v2.7 leaf" decomposition (PRODUCTION.yaml caveat).
- Deeper search on the **same v2.7 leaf** is what lifts root agreement: heur@200 0.578 → heur@800
  0.658 → heur@1600 0.715 (ROOT_ACTION_RESULTS.csv). **Search, not features, closes the gap today.**
- v2.7-static's K=2 *top-1* ties iter8 but its **mean regret is higher (0.843 vs 0.573)** — its wrong
  picks are costlier. A leaf-addressable sharpness signal, if any, lives here.

### 3b. iter8 (neural, v2.7 leaf) on the exact endgame ladder — bounds the leaf's downstream use
| K | iter8 top-1 | heur@3200 top-1 | iter8 regret | source |
|---|---|---|---|---|
| K=2 | 0.667 | **0.837** | 0.61 | [LEVEL2_L23_VERDICT.md](../level2/LEVEL2_L23_VERDICT.md):46–53 |
| K=3 | 0.574 (worst) | 0.618 | 0.96 | LEVEL2_L23_VERDICT.md:30–37 |
| K=4 | 0.561 (worst) | **0.679** | 1.48 | [LEVEL2_K4_PROBE_VERDICT.md](../level2/LEVEL2_K4_PROBE_VERDICT.md):66–72 |

- **By source (K=4)**: iter8 0.92 on its own endgames, **0.36 on greedy-generated**, heur@3200 0.64
  there (K4_PROBE_VERDICT:49–56). iter8 is near-optimal on the (easy) endgames it reaches but
  worst on **sharp / OOD** endgames. *(INTERPRETATION: this is the NEURAL agent; the leaf's static
  contribution is bounded by the heur@N rows, which the v2.8 leaf could move.)*

### 3c. What recovers v2.7/iter8 misses — search, not cheap features (FACT)
- On the 513 midgame positions where iter8 ≠ teacher: **heur@800 recovers 46.8%**, v2.7-static 28.7%,
  raw/bag features only **6–7%** ([MIDGAME_REFERENCE_REPORT.md](../midgame_reference/MIDGAME_REFERENCE_REPORT.md)).
- Of 667 midgame disagreement cases, **604 (90.6%) structural/positional**, only 63 (9.4%)
  cheap-feature-addressable (meeple 27, completion-greed 21, bag/scarcity 9, imm-score 6)
  ([MIDGAME_DISAGREEMENT_CATEGORIES.csv](../midgame_reference/MIDGAME_DISAGREEMENT_CATEGORIES.csv)).
- Of iter8's 158 endgame misses: ~7 completion-mechanism, ~82 structural/positional, ~69 both-miss
  (heur@3200 also fails) ([DISAGREEMENT_CATEGORIES.csv](../pre_tool_audit/DISAGREEMENT_CATEGORIES.csv)).
- **completion-greed is the WORST simple selector** (K=2 top-1 0.331, regret 2.47;
  `completion-then-score` in BASELINE_RESULTS.csv). It is a **trap**, not a fix.
- Bag-aware / open-edge features carry **τ ≈ +0.01** vs the teacher (near-zero), top-1 ~0.10
  (MIDGAME_BASELINE_RESULTS.csv `bag-aware-closure`, `open-edge-progress`).

### 3d. The hybrid-handoff result (CL-026) — endgame weakness is locally patchable by SEARCH
- Handoff to heur@3200 at k_remaining≤8 beats iter8 by +20.9 elo (paired z≈+5.6, n=400), monotone in
  K ([LEVEL2_HYBRID_VERDICT.md](../level2/LEVEL2_HYBRID_VERDICT.md)). **But the hybrid still loses to
  heur@3200** (−19.1 elo) — search closes the gap to the deep heuristic, doesn't surpass it. This
  bounds what a leaf change alone (without more search) could buy at the top end.

---

## 4. In-scope improvements (justified by §3, to be tested as small independent ablations)

Each must be small, independently toggleable, and faithful to "improve the leaf's *static value*,"
not "duplicate search." Final selection happens in Phase 2 after the failure taxonomy.

1. **Farm / final-scoring potential** — v2.7 only adds `+3×P` for incomplete cities adjacent to a
   farmed field; the base farm score uses `finished` cities. Candidate: a better estimate of a
   field's *final* point yield (city-count maturity, majority/ties on contested fields). *Targets:
   §3a costly-regret K=2 + structural farm cases.*
2. **Sharp-endgame / regret-aware tie-breaking** — v2.7-static's K=2 regret (0.843) exceeds iter8's
   (0.573) at equal top-1. Candidate: a leaf term that is more decisive on the genuine last-tile
   point-squeeze (where heur@3200 wins). *Risk: may just duplicate 1-ply lookahead — must verify it
   adds static value, not search.*
3. **Meeple economy / recovery** — `meeple_k` term exists but is OFF in prod; midgame disagreement
   bucket "meeple-economy" = 27 cases. Candidate: phase-sensitive value for freeing meeples
   (return-on-closure) vs trapped low-recovery meeples.
4. **Opponent denial weighting** — opp bonus is already subtracted (symmetric). Candidate: asymmetric
   `opp_bonus_cap` / denial of opponent high-value completions/claims. *Cheapest; partly already a
   knob.*
5. **Open-edge / completion scarcity** — bag-aware features measured τ≈0 as *raw per-action* signals,
   BUT v2.7's `closure_p` is a fixed schedule ignoring deck supply. Candidate: the existing
   `tile_counting_closure` / `closure_continuous_slack` knobs (already implemented!) re-evaluated as
   v2.8 leaf variants. *Cheap to test — code exists.*
6. **Phase weighting** — phase-specific closure/cap weights (opening vs endgame). *Risk of overfitting
   the phase split; keep minimal.*

## 5. Explicitly OUT of scope

- **Anything that modifies v2.7 behavior** under existing configs (frozen forever).
- **Training, flywheel, promotion, or changing production defaults / PRODUCTION.yaml.**
- **Per-action "tool"/bag/structural ranker features** — the pre-tool + midgame audits already
  killed these (τ≈0, recover 2–7% of misses). v2.8 is a *leaf value* change, not a per-action tool.
- **completion-greed as a primary signal** — measured trap (worst selector).
- **Composing all six patches into a blob** — Phase 6 composes only ablation-survivors.
- **Search-horizon fixes** (hybrid-handoff, policy-weighting) — that's a *different* live branch; ~90%
  of misses are structural/search-depth, not leaf-addressable, so the realistic v2.8 ceiling is modest
  and must be demonstrated, not assumed.
- **River / I&C / non-base rules** — locked scope (2p Base+Farmers).

## 6. Reusable artifacts (labelled positions for Phase 4 root audit — verified present)

| Path | rows | labels / columns | reuse |
|---|---|---|---|
| [measurement/midgame_reference/MIDGAME_POSITION_SAMPLE.jsonl](../midgame_reference/MIDGAME_POSITION_SAMPLE.jsonl) | 1000 | `source_game_seed`,`prefix` (replayable), band/phase/K, source. **No exact solver (soft labels).** | replay → score v2.8-static argmax |
| [measurement/midgame_reference/MIDGAME_REFERENCE_LABELS.jsonl](../midgame_reference/MIDGAME_REFERENCE_LABELS.jsonl) | 1000 | teacher (heur@3200) pick, iter8 pick, v27_static pick, per-`position_id` | join key for agreement metrics |
| [measurement/search_policy_mixing/ROOT_ACTION_AUDIT.jsonl](../search_policy_mixing/ROOT_ACTION_AUDIT.jsonl) | 1000 | heur200/iter8_noresid/v27 picks, gaps, entropy | paired same-band reference |
| [measurement/level2/l23_positions.jsonl](../level2/l23_positions.jsonl) | 750 | greedy K=2, `seed`,`ply`,`known_order`,`checksum`, exact-solvable | exact K=2 v2.8 audit |
| [measurement/level2/l23_k4_multisource.jsonl](../level2/l23_k4_multisource.jsonl) | 96 | multi-source K=4, exact-solvable | exact K=4 v2.8 audit (sharp/OOD) |
| [measurement/level2/K4_PROBE_RESULTS.json](../level2/K4_PROBE_RESULTS.json) | 187 solved | per-position exact best + per-agent regret | join exact labels |
| [measurement/pre_tool_audit/ACTION_AUDIT_DATASET.jsonl](../pre_tool_audit/ACTION_AUDIT_DATASET.jsonl) | 408 | K=2/3/4 endgame, per-action deltas + exact(K=2) | exact endgame action audit |
| [measurement/pre_tool_audit/DISAGREEMENT_CATEGORIES.csv](../pre_tool_audit/DISAGREEMENT_CATEGORIES.csv) | 158 | endgame miss mechanism | target-subset eval |
| [measurement/midgame_reference/MIDGAME_DISAGREEMENT_CATEGORIES.csv](../midgame_reference/MIDGAME_DISAGREEMENT_CATEGORIES.csv) | 667 | midgame miss mechanism | target-subset eval |

**Replay harness to adapt:** [scripts/search_policy_mixing/root_action_audit.py](../../scripts/search_policy_mixing/root_action_audit.py)
(`_replay(seed, prefix)`, static-argmax loop, fork-Pool). **Full-game A/B harness:**
[scripts/eval_heur_vs_heur.py](../../scripts/eval_heur_vs_heur.py) (deck-paired, balanced seats,
resumable, provenance manifest) — adapt for v2.7-leaf-vs-v2.8-leaf at matched sims.

---
*Phase 0 complete. Next: Phase 1 failure taxonomy (V27_FAILURE_TAXONOMY.md + V27_FAILURE_CASES.csv).*
