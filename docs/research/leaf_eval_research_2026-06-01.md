# Leaf-eval research — perfect-info stochastic game AI (2026-06-01)

Synthesis of a 5-agent literature sweep run after the anchor-fraction strength push
confirmed (ladder) that the **v2.7 heuristic leaf is the binding ceiling** — the learned
value head can't beat it as an MCTS search leaf (the "calibration cliff": pure NN-value
leaf −800 elo; blending hurt; a *better-calibrated* head hurt *more*).

**Goal of the sweep:** what can we steal from perfect-info STOCHASTIC game AI (Carcassonne
is perfect-info + stochastic via tile draws — the cousin is *backgammon*, NOT poker, which
is imperfect-info/CFR territory) to break the leaf ceiling?

## Headline finding (4 of 5 agents converged independently)

The lever is **afterstate value + explicit, EXACT chance nodes** — not "a better scalar value head."
Stop asking one scalar to *be* the expectation over draws; move the expectation into the tree
where we can compute it **exactly**, because **we know the tile bag** (distinct remaining types
are few, deplete over the game, exact probs = `count/remaining`).

- **Afterstate value** (TD-Gammon, 2048 n-tuple, Stochastic MuZero all use it): evaluate the board
  *after placement, before the next draw*. Factors out our own deterministic move → lower-variance,
  easier target. Likely *why* `virtual_score` (a structural afterstate quantity) beats our
  outcome-trained head (which fights full draw-sequence variance).
- **Exact chance nodes:** back up `Σ P(tile_type)·V(child)` over distinct remaining types. Our edge:
  Stochastic MuZero must *learn* a 32-code chance codebook (no simulator); **we know the true
  distribution** → exact weighted expectimax, strictly better than the 2020 Carcassonne paper's
  determinization (fixed tile orders).
- Explains our mysteries: naive blending hurt + "better-calibrated hurt more" because **calibration
  of the mean was never the issue — the mean over the wrong average is the wrong leaf quantity.**
  MCTS only compares siblings; a sharper point estimate that smears local contrast under draw-noise
  ranks *worse*. Fix = average over draws (in tree), not a smarter scalar.

## Prioritized experimental ladder (cheap-signal-first; each step has an early-abandon gate)

1. **Draw-luck control variate (MEASUREMENT win, cheapest).** Bag is known → compute each draw's
   "luck" = value of drawn tile − exact average over remaining tiles; subtract accumulated luck from
   results. Backgammon gets ~8–25× sample efficiency. Attacks our chronic measurement noise (n=40
   swings, the old c=3 spike) — could make n=100 behave like n=400. Independent of the leaf.
2. **Exact chance-node expectation around the EXISTING v2.7 leaf (diagnostic, no training).** If
   win-rate jumps, the missing draw-expectation is a real *additive* win → justifies the rest.
3. **Afterstate value targets.** Retrain value/leaf to predict the post-placement board, not the
   pre-draw state. Most-recommended single training change.
4. **Learned-residual leaf (our top idea — but the TARGET is load-bearing).** `leaf = v2.7 +
   ε·tanh(residual)` in win-prob space. Train residual on **deep-search value − heuristic**
   (`V_deepsearch − v2.7`, using the existing sims=800 deepsearch teacher), NOT game outcomes
   (outcomes = suspected cliff source). Works where blending failed because it's centered at 0 and
   ε-bounded (nudges locally; blending drags everywhere with a miscalibrated full-range value).
   **Pre-commit gate (cheap):** plot distribution of `V_deepsearch(s) − v2.7(s)` on a few thousand
   states — peaked at 0 ⇒ deep search isn't correcting the leaf ⇒ no signal ⇒ abandon; spread ⇒ learnable.

Stackable: lower-variance value targets (soft-Z / MCTS-root / n-step instead of final outcome —
we already partly do this via score_diff + deepsearch teacher); categorical/quantile value head for
training stability (Lyle: distributional ≠ scalar under *nonlinear* FA, i.e. our ResNet regime);
risk-adjusted leaf statistic (CVaR/quantile over *draw* variance) as a ranking-changing option.

## What NOT to do (confirmed dead-ends)
- **Determinization / fixed tile sequences** (2020 Carcassonne paper) — biased; we have exact chance,
  don't throw away perfect info.
- **Learned chance codebook (VQ-VAE, MuZero)** — we know the true distribution; approximating it is strictly worse.
- **Double Progressive Widening on chance** — for infinite outcome spaces; ours is small/discrete.
- **Star1/Star2 chance pruning** — needs small enumerable chance fan-out + bounded eval; our placement
  branching is too large (but our chance fan-out is small — so *exact enumeration* of draws is fine).
- **Deep *-minimax** (Star2.5, Heyden 2009) — stalls on long-term/farm strategy.
- **MCTS-RAVE/AMAF** — *worse* than vanilla here; breaks on farm timing (claims fields too early).
- **Tuning vs weak/random opponents** — learns to exploit mistakes, not play well (= our anchor-before-scaling rule).

## Field context (Carcassonne lit is ~3 papers — we're not behind)
- Best published agent: vanilla MCTS, **uses our exact `virtual_score` leaf + `score_diff` reward**
  (Ameneyro/Galván/Kuri-Morales, IEEE CoG 2020). Beats Star2.5 ~88%/77%; **no human anchor.** Validates
  our design. Nobody has a learned value beating a good heuristic leaf; nobody anchors vs humans.
- 2048 (n-tuple + afterstate TD + shallow expectimax) is the strongest transferable recipe.
- Kingdomino (CIG 2018): in short high-variance games, flat Monte-Carlo eval beat MCTS ⇒ **wide+shallow
  search with a strong leaf > deep narrow search**; put compute into eval quality, not tree depth.
- CatAnalysis (AZ-style Catan): under-compute AZ only marginally beat random, never superhuman ⇒
  chain-elo ↑ ≠ absolute strength (our anchor-before-scaling rule, again).

## Honest ceiling
A residual trained on deep-search-*over-v2.7* is bounded by v2.7's worldview — likely clears
strong-human, probably **not superhuman alone**. Superhuman needs the **NNUE-style bootstrap flywheel**
(regenerate deep-search targets with the residual-equipped searcher, retrain, repeat) so the teacher
drifts genuinely beyond v2.7 — OR a stronger non-v2.7 reference.

## Key references
**Backgammon / afterstate / rollout:** Sutton&Barto §6.8/§16.1 (afterstates/TD-Gammon);
Tesauro TD-Gammon (CACM 1995); GNU Backgammon rollout+variance-reduction docs (bkgm.com/gnu);
Montgomery "Variance Reduction" (bkgm.com/articles/GOL/Feb00/var.htm).
**Stochastic search/MuZero:** Antonoglou et al., Stochastic MuZero, ICLR 2022 (openreview X6D9bAHhBQ1);
Ballard *-Minimax (AIJ 1983); Lanctot et al. Monte Carlo *-Minimax (IJCAI 2013, arXiv 1304.6057);
Hsueh&Ikeda, Tabular AlphaZero on stochastic games (IEEE Access 2023).
**Distributional/variance-aware:** Bellemare et al. C51 (2017); Dabney et al. IQN (2018);
Lyle/Bellemare/Castro, "distributional ≠ scalar under nonlinear FA" (2019, arXiv 1901.01560);
Willemsen et al. value targets / greedy backups (NCA 2021); MuZero categorical value (Schrittwieser 2020).
**NNUE / residual / distillation:** nnue-pytorch docs (target = sigmoid(search_eval/400) interp w/ result,
lambda→search side); Stockfish NNUE intro (2020) + HCE removal (SF16); Anthony et al. ExIt
"Thinking Fast and Slow" (1705.08439); Sabatelli et al. limited-lookahead chess eval (2018);
deep-learning Black–Scholes-delta residual (arXiv 2407.19367); "Ensembles+aug can harm calibration" (2010.09875).
**Carcassonne / euro games:** Ameneyro et al. MCTS Carcassonne (arXiv 2009.12974); Galván et al. evolving UCT
(2112.09697); Heyden MSc thesis 2009 (Star2.5); Szubert&Jaśkowski 2048 n-tuple (arXiv 1606.07374);
Gedda et al. Kingdomino (arXiv 1807.04458); CatAnalysis (thegravity.app/catanrl.pdf).

_Full per-agent reports available in the 2026-06-01 session transcript._
