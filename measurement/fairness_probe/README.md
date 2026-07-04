# Fairness decision probe — exact-solver move regret, clairvoyant vs fair (stage 1)

**Status: RUNNING 2026-07-04** (`fairness_decision_s1600_k8_n300.json` + `.log`).

## Question

At the CHAMPION's config (HeuristicMCTS, v2.9 Bmild_cap8 leaf — see
`governance/PRODUCTION.yaml`), how much does deck-clairvoyance change/improve
DECISIONS — measured as exact-solver move regret on already-solved roots?

This is the **cheap, non-circular first stage** of the fairness-tax measurement.
HeuristicMCTS is structurally clairvoyant (simulations descend the true
`state.deck` order; it has no `fair_chance` flag — that exists only on
NeuralMCTS). The game-level fair-vs-clair head-to-head (n=400, deck-paired) is
only worth its budget if this shows a real decision-level tax.

## Design (`scripts/canonical_az/fairness_decision_probe.py`)

- **Roots:** the qprobe_A ∩ pool_A sibling set (same 10,067-root reuse set as
  `scripts/canonical_az/solver_score.py`), filtered `k_remaining<=2` (1,119
  roots, all K=2), seeded shuffle, `--n` subset. Replay via
  `replay_to(seed, ply)` + checksum verify.
- **Truth:** exact marginalized endgame solve per root
  (`scripts/level2/endgame_solver.py`; marginalized == clairvoyant at K<=2, so
  the ground truth is fair-legit). `regret_of` = raw points lost vs optimal.
- **CLAIR arm:** HeuristicMCTS(sims=S, c=3.0, v2.9 Bmild_cap8) `best_action`
  on the true board — the champion's move.
- **FAIR arm:** root-determinization PIMC — K× {deepcopy board, reshuffle ONLY
  the unseen `state.deck` (multiset preserved, `next_tile` untouched — the
  `NeuralMCTS._reshuffled_root` semantics), fresh HeuristicMCTS per
  determinization (no cross-determinization tree reuse — the `fair_isolate`
  discipline), pool deduped root visits}. Pick = argmax pooled-N (primary,
  spec rule); pooled-Q (best_action's rule generalized, the
  `clairvoyance_gap._choose_action` statistic) recorded as a secondary
  read-out so an aggregation-rule confound can't hide/fake the verdict.
- Output: per-root `{seed, ply, clair_move, fair_move, differ, clair_regret,
  fair_regret, ...}` + aggregate (per-arm mean/median regret + top1 vs solver,
  paired fair−clair delta + z, differ rate, sign test on differ-roots) + a
  self-describing manifest (sims, K, leaf env + resolved LeafConfig, code rev).

## Scope caveats (read before interpreting)

1. **(by design)** at K<=2 the deck has <=1 hidden draw beyond the current
   tile — clairvoyance advantage is structurally SMALL here (this measures the
   endgame-decision tax, not the midgame tax).
2. **(sharper, found at smoke)** every K=2 root here is TILES-phase →
   `deck_len == 1`: the single unseen tile's identity is inferable from the
   public multiset, so the reshuffle is an **identity permutation**. The two
   arms then differ only by search RNG and aggregation (K pooled searches vs
   one) — **zero hidden information**. `deck_len_dist` in the output states how
   much of the sample is in that regime (smoke: 8/8). A nonzero "tax" here is
   an aggregation/noise effect, NOT clairvoyance; a genuine clairvoyance tax
   needs deck_len>=2 roots (K>=3, solver = clairvoyant+AB there, no longer
   marginalized-fair-legit) or midgame roots (no exact solver).

## Smoke (n=8, sims=200, K=3, 2026-07-04)

clair regret mean 0.375 (top1 6/8) · fair_pooledQ identical to clair ·
fair_pooledN mean 1.75 (one root spread 3×200 visits over 59 legal moves →
argmax-N noise picked an 11-point blunder). Regrets all >= 0; moves agree 5/8.
Solve ≈ 3–34 s/root dominates; search ≈ 0.35 s per 800 sims.

Real run: `--n 300 --sims 1600 --k 8 --workers 10` (nice -19, CPU-only, local).
