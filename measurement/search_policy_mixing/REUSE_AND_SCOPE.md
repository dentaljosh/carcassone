# Phase 0 — Reuse & Scope (search/policy mixing audit)

> **Measurement only.** No training, no flywheel, no MCTS/production integration, no champion
> change, no promotion. Base commit at start: `8c42550` (branch `stage-b-wiring`). Champion
> unchanged: `flywheel2_champion_iter8`
> (`/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt`, 96×6 ResNet,
> `n_scalar_features=12`, v2.7 leaf, `RESIDUAL_SCALE=0.25`, `c_puct=3.0`, sims=200, `FLAT_LEAF=1`;
> [governance/PRODUCTION.yaml](../../governance/PRODUCTION.yaml)).
>
> **FACT** = read off an artifact (cited). **INTERPRETATION** = my reading. Kept separate.
> Clairvoyant/real-deck labels kept distinct from fair-information; full-game Elo kept distinct
> from root-action agreement kept distinct from teacher-imitation.

## The question this audit answers (scope)

> **How should iter8 policy, the v2.7/static leaf, the residual/value head, and heuristic search
> depth be mixed across phase, depth, and sharpness?** Is iter8 best as a standalone agent, a root
> prior, a candidate generator, an early-game specialist — and does dynamic hybrid routing beat the
> fixed K≤8 handoff?

This is the live hypothesis after the pre-tool and midgame-reference audits: the bottleneck is
**not** missing cheap scalar tools (both audits closed that), so the open lever is **how the
existing components are combined**. See [../pre_tool_audit/PRE_TOOL_AUDIT.md](../pre_tool_audit/PRE_TOOL_AUDIT.md)
and [../midgame_reference/MIDGAME_REFERENCE_REPORT.md](../midgame_reference/MIDGAME_REFERENCE_REPORT.md).

## What is ALREADY measured (reuse verbatim — do NOT re-run)

| Artifact | What it already answers | Headline (FACT) |
|---|---|---|
| [../midgame_reference/MIDGAME_REFERENCE_LABELS.jsonl](../midgame_reference/MIDGAME_REFERENCE_LABELS.jsonl) (1000 rows) | Per-position root choice of **iter8 MCTS@200**, **iter8 policy-prior**, **v2.7-static**, **heur@800/1600/3200**, + heur@3200 child-Q/visits + `teacher_gap_q` | iter8 vs heur@3200 teacher top-1 **0.487**; v2.7-static **0.480**; iter8-prior **0.259**; heur@800 **0.658** |
| [../midgame_reference/MIDGAME_BASELINE_RESULTS.md](../midgame_reference/MIDGAME_BASELINE_RESULTS.md) | Teacher-imitation top-1 + Kendall τ by band/source/disagreement | iter8 by band: opening 0.61 → pre_endgame 0.39 (inverts); v2.7-static flat ~0.48 |
| [../midgame_reference/MIDGAME_POSITION_SAMPLE.jsonl](../midgame_reference/MIDGAME_POSITION_SAMPLE.jsonl) (1000) | The position bank + per-position routing signals (`k_remaining`, `band`, `n_legal_tile_actions`, `score_diff_mover`, `bag_size`, `source_bucket`) | balanced 250/source × 200/band |
| [../level2/LEVEL2_HYBRID_VERDICT.md](../level2/LEVEL2_HYBRID_VERDICT.md) (n=200–400 paired, band b340) | **HYBRID_FIXED_K5/K8 vs ITER8_PROD and vs HEUR_3200** — Phase-3 matchups **#4 and #5 of this audit are DONE** | K8 vs iter8 **+20.9 elo / +1.36 pts / z=4.68** (n=400 z=5.79); K8 vs heur@3200 **−19.1 elo / −0.76 / z=−0.51** (tie-loss); iter8 vs heur@3200 **−28.7 elo / z=−0.70** |

**Implication:** the fixed-K hybrid is GAP-CLOSING, not champion-beating, and "a cheap heur@800
endgame captures most of the gain" (LEVEL2_HYBRID_VERDICT Phase 1). So this audit does **not**
re-litigate fixed-K vs iter8/heur@3200; it asks the *new* questions (residual decomposition,
dynamic vs fixed routing, policy-only-leaf).

## Key code-path findings (from a thorough source read; cited for script reuse)

| Need | Code path | Note |
|---|---|---|
| Reconstruct any midgame position | `label_midgame.py::_replay(seed, prefix, include_farm)` | replays the recorded action `prefix`, no MCTS at gen |
| Deep heuristic teacher / any heur@N | `HeuristicMCTS(game, simulations=N, seed, heur_leaf="v2_7")` (`src/carcassonne_ai/mcts.py:314`) | **HEUR_200 is trivial** — same API, `simulations=200` |
| iter8 NeuralMCTS | `NeuralMCTS(game, evaluator=leaf, simulations=200, c_puct=3.0, seed)` (`mcts.py:417`) | production agent |
| Production leaf value | `make_v25_value_wrapper(base, cfg)` (`evaluators.py:184`): `leaf = clip(tanh(v2.7/15) + residual_scale·v_nn, ±1)` | residual is **additive** on top of the v2.7 leaf |
| Net policy prior | `make_single_evaluator(net, dev, game)` returns `(priors[A], v_nn)`; priors feed PUCT | `iter8_prior_argmax` already labelled |
| Root visit dist / child-Q | `NeuralMCTS.root_visit_distribution(board)`; `_mover_child_stats` (label_midgame) | for visit-concentration sharpness |
| Hybrid handoff agent | `scripts/level2/eval_hybrid_handoff.py::_HybridAgent` + `hybrid_should_latch(state,K)` | agent specs `iter8 | heur@N | hybrid:K:N`; `--shm-eval-server` orch |
| Full-game paired eval (neural) | `eval_hybrid_handoff.py` (paired-z/elo, both seats, manifests, orch) | the harness for any NEW neural pilot |
| Full-game paired eval (heur-only) | `scripts/ladder_rung_eval.py` | CPU-only, no orch |
| carc-orch SHM orchestrator | `rust/carc-orch/run_server.sh` + `run_hybrid_bands_orch.sh`; attach via `--shm-eval-server <NAME>` | high-W neural eval |

## ⚠️ Critical simplification — two named variants COLLAPSE (FACT, from the leaf math)

`make_v25_value_wrapper` with `residual_scale=0` returns `(priors, h)` where `h = tanh(v2.7/15)` —
it **discards the net value `v_nn` entirely**. Therefore:

> **`ITER8_NO_RESIDUAL` (residual_scale=0) ≡ `ITER8_POLICY_ONLY_LEAF_V27` (net policy prior + pure
> v2.7 leaf, value disabled).** They are the *same agent*: net policy → PUCT priors, v2.7-static →
> leaf value, no net value. We compute it **once** (call it `iter8_noresid` / "policy+v2.7 leaf").

This makes the residual-role audit (Phase 5) and the policy-decomposition (Phase 2/3) the **same
measurement**: prod (resid 0.25) vs noresid (resid 0) isolates *exactly* the net value-head
contribution, holding policy + leaf + sims fixed.

## What I COMPUTE NEW (cheap, offline-reusing the 1000-position bank)

A Phase-2 root-action pass (`scripts/search_policy_mixing/root_action_audit.py`, modeled on
`label_midgame.py`, net-on-CPU, W=14) adds per position, joined to existing labels by
`position_id`:

1. **`heur200_choice`** — HeuristicMCTS@200 v2.7 (the missing budget rung; equal-sims comparison to iter8@200).
2. **`iter8_noresid_choice`** — NeuralMCTS@200, net policy + **pure v2.7 leaf** (residual 0). The collapsed variant above.
3. **`iter8_noresid_topvisit_frac`** — top child visit fraction of that search (decisiveness/sharpness).
4. **`policy_entropy`**, **`policy_top1_prob`** — Shannon entropy / max prob of the masked iter8 policy over legal actions (routing/sharpness signal — already have the forward).
5. **`v27_gap`** — best − 2nd-best static `virtual_score_v2` over legal afterstates (cheap sharpness proxy).

Everything else (ITER8_PROD, HEUR_800, HEUR_3200, V27_STATIC_ROOT_ONLY, iter8-prior) is **already
in the labels** — joined, not recomputed. Cost: ~3–4 min @ W=14 local (heur@200 ≪ heur@3200; one
@200 neural search/position) — pilot at `--limit 20` first.

## What requires a NEW full-game pilot (Phase 3, small + paired, report cost first)

Only the genuinely-unmeasured matchups. The hybrid ones are reused. Candidates:
- **`iter8_noresid` (resid 0) vs `iter8_prod` (resid 0.25)** @200, same band — isolates the residual head full-game.
- **`iter8_noresid` @200 vs `HEUR_200`/`HEUR_800`** — does the net policy add over equal/deeper heuristic search.

These need an evaluator-per-agent (env-var `RESIDUAL_SCALE` is process-global, so a direct
resid0-vs-resid0.25 head-to-head needs both wrappers built in one process). Implement as a small
measurement wrapper, **not** production code. Pilot n=100–200 paired, both seats, fresh deck band
(NOT the SPENT 1.7e9 sealed panel).

## What I DELIBERATELY DO NOT do (hard constraints honored)

- **No training, no flywheel, no champion change, no promotion, no production routing integration.**
- **`ITER8_POLICY_ROOT_ONLY`** (net policy ranks root candidates, heuristic search after) and the
  **dynamic routing variants** are first evaluated **offline** on the root-audit data; a full-game
  pilot is run **only if** the offline signal clears the gate. No large routing subsystem is built
  speculatively (the pre-tool audit's "don't build before the weak gate" discipline).
- **No new sealed-panel spend.** Pilots use fresh seeds; the 1.7e9 sealed panel stays spent.
- **No claim of midgame ground truth.** heur@3200 is the strongest practical ruler, real-deck /
  clairvoyant-leaning, flagged on every row. Conclusions reported same-band / same-source where it matters.
- **No re-running already-complete hybrid matchups** (LEVEL2_HYBRID_VERDICT); cited, not redone.

## Honest-labeling invariants (carried forward)
- exact-solver (none at midgame K) vs deep-search teacher (heur@N) vs learned-agent (iter8) vs static (v2.7-d0) — kept distinct;
- clairvoyant/real-deck (all midgame root labels) vs fair-information (full-game pilots reshuffle? — NO: paired same-deck, clairvoyance noted) — flagged;
- same-band paired vs cross-band — source confounds reachable difficulty (iter8 reaches easier midgames).
