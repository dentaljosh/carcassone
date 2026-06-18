# Phase 4A — value-ranking label-reliability ceiling (2026-06-18)

Source: `scripts/value_ranking_label_reliability.py` → `/mnt/c/carc-shared/value_ranking/label_reliability/summary.json`
(n=119 decision nodes, mean 13.5 children, oracle_sims=400, deep_sims=1600, deep_frac=0.25,
harvest/oracle net = champion iter8).

## Purpose
Before reading any arm's Kendall-τ, establish how reliable the **ranking target** (the deep-oracle
sibling value) is — a model τ is meaningless without knowing the achievable ceiling.

## Results
| measure | value | meaning |
|---|---|---|
| oracle self-agreement τ(400_A, 400_B) | **+1.000 ± 0.000** | two seeds give identical rankings |
| oracle top-1 / pairwise agreement | 1.000 / 1.000 | identical |
| cross-regret (tanh) | 0.0000 | identical |
| τ(400-sim, **1600-sim** deeper oracle) | **+0.644 ± 0.051** | 400 vs deeper truth |
| top-1(400 vs 1600) | 0.692 | |

## Interpretation (raw vs caveat)
- **⚠️ The τ(A,B)=1.000 is DEGENERATE, not a "perfect-reliability" result.** The 400-sim oracle
  (NeuralMCTS, no root Dirichlet, deterministic PUCT) is a **fixed function of the position** — the
  search seed changes nothing, so two "independent" seeds agree trivially. The two-seed design
  cannot measure label noise on a deterministic search. (Design note for any re-run: perturb the
  *target* via search depth or leaf-config, not the RNG seed.)
- **The meaningful reliability number is τ(400, 1600) = 0.644**: the 400-sim target is a *decent
  but imperfect* proxy for a deeper oracle (it flips ~31% of sibling pairs vs 1600 sims). So the
  achievable ceiling for ranking the *true deep* value from the 400-sim labels is ~0.64, not 1.0.
- **Either way, the target is RELIABLY RANKABLE:** the hand-crafted **v2.7 leaf extracts τ=0.579**
  from these same siblings (`decision_ranking_svtree`), and the target is internally self-consistent.
  So a ranker *can* achieve ~0.58 here — the signal is there.

## Bearing on the arms (Phase 4C)
Best learned arm τ = **0.029** (arm B). Against a ceiling that is high (target rankable; v2.7=0.58),
the arms extract **~3–5% of the achievable ranking**. This is the **"all arms fail while labels are
reliable"** branch of the 4E decision rule → the learned-ranking formulations are **disfavored**,
NOT probe/target-limited. See [VALUE_RANKING_VERDICT.md](VALUE_RANKING_VERDICT.md).
