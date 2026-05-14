# Experiments — open ablation roadmap

A living priority queue of ablations toward superhuman play. **Not exhaustive** — meant to prevent drift, not to predict everything. Each row is one knob, not a recipe combo. Rewrite priorities when a finding invalidates a downstream question.

**Goal:** superhuman play. Concretely: hybrid_warmstart at sims=100 currently wins 80% vs Tier-1 (n=20, sims=100); a thinking human beat Tier-1 2-of-3 games in casual play. So 80% vs Tier-1 is *not yet* superhuman. We need a winrate well above 80% vs Tier-1 *or* direct evidence of beating a strong human player.

**Phase 5 (analyzer) is gated on superhuman.** Don't drift to Phase 5 work.

## Rules of engagement

- One knob varied per experiment. Hold everything else fixed.
- Bench n ≥ 20 (SE ~10pp); n ≥ 50 if the question is statistical (e.g. small effect).
- Reuse a fixed seed range across comparisons.
- Log result here (date, knob, winrate, conclusion) when complete. Move row from "open" to "done."
- If a finding flips an assumption downstream, *re-prioritize* the open list before continuing.

## Currently running

(none)

## Open — by component, priority order

### Leaf evaluator (highest priority — strongly suspected ceiling)

- [X] ~~**Does NN policy actually help?**~~ DONE 2026-05-14: yes, worth ~18pp. puct_uniform sims=100 → Tier-1 60%; hybrid_warmstart sims=100 → Tier-1 41.7%. Network adds real value; can't drop it.
- [X] ~~**What does virtual_score get wrong?**~~ DONE 2026-05-14: top failure modes are closure-event blindness (3/3 lost games) and farm composition opacity (2/3). Both involve `virtual_score` giving partial credit that doesn't anticipate the partial→full credit swing when features close. Full writeup in [DECISIONS.md](DECISIONS.md). Tooling: [scripts/diagnose_virtual_score.py](scripts/diagnose_virtual_score.py).
- [X] ~~**virtual_score_v2: closure-proximity bonus + farm-growth potential.**~~ DONE 2026-05-14: built and benched. **FAILED** — 30.0% wr vs Tier-1 at sims=400 n=30, a ~47pp regression from v1's 76.7%. Tools (`virtual_score_v2.py`, `_hybrid_v2_evaluator` wiring, 11 tests) are committed for v2.5 / v3 iteration. See DECISIONS.md 2026-05-14 for hypothesized causes (P heuristic too aggressive, possible cathedral-flag bug, possible bonus-dominates-base scale issue).
- [X] ~~**v2-diagnostic: which bonus type misled v2?**~~ DONE 2026-05-14: cathedral branch doesn't fire (not a bug); `bonus` overwhelms `base` in 92% of moves; max bonus ~7× base; tanh saturates → search loses gradient. Farm-growth bonus dominates 20× over city-closure. Root cause = magnitude, not sign or design. See DECISIONS.md.
- [ ] **v2.5: halve P heuristic + cap bonus per player at ±5.** P = {1: 0.5, 2: 0.2, 3: 0.05} (was 1.0/0.5/0.25). Cap so even chained closures can't saturate tanh. Acceptance: ≥76% wr vs Tier-1 at sims=400 n=30 (match v1 baseline). Stretch ≥80%. ~1h code + 30min bench.
- [ ] **v3 (gated on v2.5 failure).** If v2.5 still loses ground, the structural design (anticipation bonus) is wrong, not the magnitude. Pivot to denial-value or meeple-economy. (~1-2 days each.)
- [ ] **PUCT c sweep.** Hybrid_warmstart at sims=100 with c ∈ {0.5, 1.0, 1.5, 2.0, 3.0}, n=20 each. Tests whether deeper search hurts because the prior-trust is wrong (too low c = over-exploration into virtual_score's blind spots). (~30 min.)

### Policy head

- [ ] **Policy retraining on hybrid-generated data.** Generate ~10K games of hybrid_warmstart vs hybrid_warmstart at sims=100. Train a fresh policy head (frozen trunk) on those positions. Test vs Tier-1. Hypothesis: training on hybrid-strength games beats training on heuristic targets. (~1 day code + 4-8h compute, ~$2-5 cloud.)
- [ ] **Bigger policy capacity.** Widen `policy_project_channels` 4 → 16 → 32 (BACKLOG note). Retrain warmstart with the wider head. Test vs Tier-1 with hybrid eval. (~1 day arch + 4h retrain, ~$2.)
- [ ] **Action-space dedup.** Coalesce equivalent meeple-placement slots (BACKLOG note). Bigger refactor — touches action_space.py + decode + dataset shape. Defer unless small-action-space variants give clear wins. (~1 day refactor + 4h retrain.)

### Search

- [ ] **Depth-limited search.** Force the search to reach a minimum depth before evaluating leaves. May counteract virtual_score's exploit-at-deeper-depth failure mode. (~2 days code.)
- [ ] **Alpha-beta variant.** Replace PUCT with classical α-β at depth 4-6. For domains with a strong static eval (which we now have), α-β often beats MCTS. (~3 days code.)
- [ ] **MCTS with NN value retained.** Re-test (NN policy + NN value) vs (NN policy + virtual_score) once the value head is retrained — does fixing value-head training rescue it? Only after policy-retraining experiment lands.

### Network architecture

- [ ] **Bigger trunk.** 192×14 or 256×10 (BACKLOG note). Untested. Defer until policy/leaf experiments converge — bigger trunk only matters if we have a training signal that uses the capacity. (~1 day arch + 8h retrain, ~$5.)
- [ ] **Drop the value head entirely.** With virtual_score-as-leaf, the value head is dead weight: slow forward pass, no contribution to search. Removing it saves ~1M params and ~5ms/inference. (~30 min code if we keep the file, more if we cleanup training pipelines.)

### Training process

- [ ] **Self-play with hybrid players.** Rebuild the self-play loop using `hybrid_warmstart` (not raw NN) as both players. Generates higher-quality training data than the v1-v6 setup that degraded both heads. (~1-2 days code; depends on the policy-retraining experiment outcome.)
- [ ] **Async training.** BACKLOG note. Only sensible if self-play resumes as a useful signal.

## Done — findings ledger

| date | knob | result | conclusion |
|---|---|---|---|
| 2026-05-13 | Tier-1 vs warmstart_canonical (n=50 sims=100) | Tier-1 77% wr | NN-only NeuralMCTS loses to 1-ply heuristic. Recipe ceiling. |
| 2026-05-13 | Tier-1 vs iter_12 (n=50 sims=100) | Tier-1 75% wr | Same as above with v6's best checkpoint. |
| 2026-05-14 | HeuristicMCTS (no NN) vs Tier-1 (n=20 sims=200) | Tier-1 60% wr | Vanilla UCT + virtual_score leaf approaches Tier-1 but doesn't beat. |
| 2026-05-14 | Hybrid iter_12 (NN priors + virtual_score) vs Tier-1 (n=20 sims=100) | Tier-1 40% wr | **Value head was actively harmful.** 35pp swing from one knob. |
| 2026-05-14 | Hybrid iter_12 sims=200 (n=20) | Tier-1 40% wr | More sims didn't help. iter_12's policy is the ceiling. |
| 2026-05-14 | Hybrid warmstart_canonical sims=100 (n=20) | Tier-1 20% wr | **v1-v6 self-play degraded the policy head.** day-0 warmstart > iter_12 by 20pp. |
| 2026-05-14 | Hybrid warmstart_canonical sims=200 (n=20) | Tier-1 35% wr | More sims hurt hybrid_warmstart. Search exploits virtual_score's blind spots at depth. |
| 2026-05-14 | Sims sweep hybrid_warmstart (n=30 each: sims 50/100/150/200/400/800) | Tier-1 winrate: 36.7/41.7/41.7/30.0/23.3/23.3% | Earlier n=20 sims=100 was a lucky sample (was 20%). Curve actually monotone-improving with diminishing returns, plateau by sims=400. sims=800 = 0 gain over sims=400. Production sims=400. |
| 2026-05-14 | puct_uniform (no NN, uniform priors + virtual_score leaf) sims=100 (n=30) | Tier-1 60% wr | **NN policy head is worth ~18pp.** Cannot drop the network — uniform priors much worse than NN priors. |
| 2026-05-14 | virtual_score diagnostic — replay lost games at sims=400 (n=10, 3 losses inspected) | 5 failure modes ranked: closure-event blindness (3/3), farm composition opacity (2/3), denial invisible, over-committed meeples, late-game volatility | Top-2 modes account for the 30-pt-swing-in-1-move pattern. Informs virtual_score_v2 design (closure-proximity bonus + farm-growth potential). |
| 2026-05-14 | hybrid_v2 (v1 base + closure-anticipation + farm-growth) vs Tier-1 sims=400 n=30 | Tier-1 70.0% wr / hybrid_v2 30.0% / avg diff -10.6 | **v2 FAILS, ~47pp regression vs v1.** Adding leaf signal hurt search. Hypotheses: P heuristic too aggressive, cathedral-flag detection broken (`tile.inn` ≠ cathedral), bonus magnitude overwhelms base. Halt v2 deployment; build v2-diagnostic before v2.5/v3 decision. |

## Closed — won't pursue

- **Try-another-recipe variants (v7+).** v1-v6 produced compound recipe knobs without isolating cause. Replaced by ablation-first.
- **Bigger self-play box class.** Was a candidate for v6 perf. Irrelevant now that v1-v6 is judged net-negative.

## Meta-rule

> "When self-play plateaus, the next experiment is component ablation, not another recipe variant. Try-harder-with-the-same-architecture is the trap." (DECISIONS.md 2026-05-14.)
