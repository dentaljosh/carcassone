# Phase 0 — Reuse & Scope (midgame_reference build)

> **Measurement only.** No training, no flywheel, no MCTS integration, no production change,
> no promotion. Base commit at start: `f84eb01`. Champion unchanged:
> `flywheel2_champion_iter8` (`/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt`,
> 96×6 ResNet, `n_scalar_features=12`, v2.7 leaf, `RESIDUAL_SCALE=0.25`, `FLAT_LEAF=1`;
> [governance/PRODUCTION.yaml](../../governance/PRODUCTION.yaml)).
>
> This file states **exactly** what code/data the midgame build reuses, what it changes, and
> what it deliberately does **not** do. It is the contract that keeps this build honest after
> the pre-tool audit's pre-scoring bug (deltas read one half-move too early).

## The question this build answers (scope)

> In **opening/midgame** positions (NOT the K≤4 endgame), do correctly-computed per-action
> deltas, bag/completion quantities, and v2.7/static scores explain **deep-search teacher**
> preferences and **iter8-vs-heuristic** disagreements — i.e. is there a *midgame* case for a
> tool/action-ranker branch that the endgame audit could not test for lack of labels?

The pre-tool audit ([../pre_tool_audit/PRE_TOOL_AUDIT.md](../pre_tool_audit/PRE_TOOL_AUDIT.md))
recommended **more measurement before tool-coding** and named the **opening/midgame as the
blind spot**: iter8's strength and the raw per-action quantities' variance both live there, and
there are no exact-solver labels there. This build constructs the midgame reference the audit
asked for. It is the gate's input, not the gate.

## What I REUSE (verbatim or imported)

| Source | What | Used for |
|---|---|---|
| `scripts/level2/gen_endgame_multisource.py` | `replay_actions(seed, actions)`, `k_remaining(board)` | Reconstruct any position from a recorded action prefix (source-agnostic, no MCTS). Phase 1/2/3. |
| `scripts/level2/build_action_audit_dataset.py` | `_resolve_turn`, `_per_action_features`, `_action_type` — the **corrected scoring-resolved afterstate** logic | Phase 2 per-action deltas. **This is the bug-fix to preserve**: a TILES action lands in the mover's MEEPLES sub-phase and the engine scores completions only *after* the meeple sub-decision; deltas are read on the resolved afterstate (tile+meeple-PASS for forced completions; best-meeple scan for claim-and-score). |
| `scripts/level2/score_baseline_selectors.py` | `kendall_tau_b`, the selector framework (`f_imm_net`, `f_best_meeple`, `f_v27`, `eval_computed`, `agg`) | Phase 4 baseline ranking. |
| `src/carcassonne_ai/virtual_score_v2.py` | `virtual_score_v2`, `DEFAULT_CONFIG`, `_deck_city_supply`, `_close_prob`, `_supply_factor` | v2.7 per-action score (Phase 2) + **bag-aware closure quantities reuse the v2.7 leaf's own supply/close-prob math** (so the bag features are the exact quantities the leaf consults internally — no new heuristic invented). |
| `src/carcassonne_ai/flat_leaf.py` | `decompose(state) -> Decomp` (union-find city/road/farm components, `city_root_open_n`, `city_root_coords`, `*_finished`, `city_side_root`, `road_side_root`) | Phase 2 bag-aware features: affected-feature open-edge counts + ownership, computed from the **production flat-leaf decomposition** (no new structural code). |
| `src/carcassonne_ai/mcts.py` | `HeuristicMCTS(heur_leaf="v2_7")`, `NeuralMCTS`, `.search()` (→ `{action: visits}`), `.best_action()`, root `children[a].Q/.N` | Phase 3 reference labels (heur@N choice + root child-Q gap; iter8 MCTS@200 choice). |
| `src/carcassonne_ai/evaluators.py` | `make_single_evaluator`, `make_v25_value_wrapper` | Phase 3 iter8 leaf (production blend, `residual_scale=0.25`). |
| `/mnt/c/carc-shared/l23_k4_expand.jsonl` (200 records) | Full-game **action prefixes** (ply ~134–136 → K=4), 50 each from greedy / heur@3200 / hybrid:8:3200 / iter8 | Phase 1 position source: replay each prefix to **earlier** plies to snapshot midgame positions at target K-bands. The prefix passes through every K, so one game yields one snapshot per band — **all four source distributions, free, no MCTS at gen time.** |

**Production leaf env (set in every script before importing carcassonne_ai):**
`CARCASSONNE_USE_FLAT_LEAF=1`, `CARCASSONNE_V25_CAP=12`, `CARCASSONNE_V25_DROP_THREE_OPEN=1`,
`CARCASSONNE_V25_VALUE_BLEND=0` — identical to the pre-tool audit manifest and PRODUCTION.yaml.

## What I CHANGE / ADD (vs the endgame audit)

1. **Position regime: midgame, not endgame.** Bands by tiles-remaining
   K ∈ {52, 40, 28, 16, 10} = opening / early-mid / mid / late-mid / pre-endgame. All are
   **above the exact-solver region** (the audit solved K≤4, occasionally K=5/6), so there are
   **no exact-solver labels here** — a hard constraint that shapes Phase 3.
2. **Reference labels replace the exact solver.** Endgame had alpha-beta ground truth. Midgame
   has none. Phase 3 builds **multiple, separately-kept** references: deep-search teacher
   (heur@800/1600/3200), the production agent (iter8 MCTS@200 + its raw policy prior), and the
   static v2.7 best action. **None is called ground truth.** The strongest practical ruler is
   heur@3200; its best-vs-2nd root child-Q gap is the **teacher-confidence** signal.
3. **New bag-aware per-action features** (audit input-inventory candidate #6, cleanly ABSENT
   from the net input): affected-feature open-edge count before/after, a completion-scarcity
   bucket from the v2.7 leaf's own `_deck_city_supply`/`_supply_factor`, and affected-feature
   ownership (self/opp/shared/empty). Built from `decompose`, not new structural code.
4. **Disagreement buckets are derived tags, not a separate generation pass.** Buckets "iter8 vs
   heur@3200 disagree" and "shallow vs deep heur disagree" are computed *after* labeling every
   sampled position with every agent (Phase 3), then tagged — cheaper and cleaner than
   pre-selecting, and it keeps the sample's source/band strata intact.

## What I DELIBERATELY DO NOT do (hard constraints honored)

- **No training, no flywheel, no production/champion change, no promotion, no MCTS feature
  integration.** A small *offline, diagnostic* linear/logistic ranker (Phase 4) is the only fit
  permitted, and only if it is strictly offline, explicit train/test split, coefficients
  reported, presented as diagnostic — never as a production component.
- **No claim of midgame ground truth.** All midgame references are agent/search labels with
  known biases; reported as such.
- **No bag-marginalized / fair-information midgame labels.** heur@N and iter8 search descend the
  **real fixed deck order** (the board carries the shuffled deck; no reshuffle), so these labels
  are **clairvoyant-leaning**, NOT honest-information — same caveat as the endgame audit, but
  the leakage is **weaker at midgame** (3200 sims with a v2.7 leaf is shallow relative to a
  ~10–52-tile future, so the search rarely reaches the deck-dependent tail). A fair-information
  (determinized/marginalized) midgame variant is **intractable** and is logged in
  FEATURE_BACKLOG, not built. **Every label carries a `clairvoyance` flag.**
- **No new farm tools / full strategic features.** Farms never score mid-game; farm structure is
  read only where `decompose` already exposes it cheaply (ownership). Anything expensive or
  ambiguous (exact "which bag tiles close feature F" edge-matching, farm value projection,
  opponent-denial search) → FEATURE_BACKLOG.md, not implemented.
- **No re-running the exact solver** (it does not apply at midgame K).
- **No regeneration of source games where existing prefixes suffice.** The multisource 96-game
  set (`measurement/level2/l23_k4_multisource.jsonl`, a different seed band) is **available but
  not used**, to keep a uniform 50-games-per-source × 5-bands stratification from the cleaner
  200-game `l23_k4_expand.jsonl`.

## Honest-labeling invariants (carried from the audit)

Every reported number cites its artifact/rows. **FACT** = read off an artifact. **INTERPRETATION**
= my reading. Kept separate at all times:
- **exact solver labels** (none here — endgame only) vs **deep-search teacher labels** (heur@N)
  vs **learned-agent choices** (iter8) vs **heuristic/static scores** (v2.7-depth-0);
- **clairvoyant/real-deck** vs **fair-information** (all midgame labels are real-deck → flagged);
- **same-band paired** comparisons vs cross-band (source is confounded with reachable difficulty,
  exactly as in the K4 probe — iter8 reaches different midgames than greedy).

## Validation gate against repeating the pre-scoring bug

Phase 2 ships **FEATURE_VALIDATION.md**: ≥20 randomly-sampled positions with before/after action
examples proving the per-action features **vary across legal actions where they should** (the
exact check the v1 audit failed). No feature table is trusted until this passes.
