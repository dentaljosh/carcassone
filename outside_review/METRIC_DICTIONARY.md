# METRIC_DICTIONARY — exact definitions of every number we report

The point of this file is so a reviewer never has to guess what a number means.
Each metric: how it is computed (with code ref), what it is sensitive to, and the
known ways it misleads.

---

## Strength / outcome metrics

### `elo` (the headline number)
- **Definition:** `400 · log10(score / (1 − score))`, where `score = (W + 0.5·D) / N`. Clamped to ±800. Code: `src/carcassonne_ai/elo.py:22-44`.
- **It is a transform of win-rate, nothing more.** "+87 elo" = 62.3% score. It is NOT a FIDE-style rating anchored to any external scale.
- **Always relative to a named opponent.** "+87 vs HeuristicMCTS@200" and "+25 vs iter_11" are different rulers. The opponent must be read with the number.
- **Misleads when:** the opponent is in the training lineage (self-anchored elo can climb +600 while absolute strength regresses −300 — observed 2026-05-10, `DECISIONS.md`); the opponent is saturated (Tier-1); n is small (see σ below); or the ±800 clamp fires (degenerate 0/N or N/N games, σ→NaN).

### `sigma` (σ_elo) — the uncertainty on elo
- **Definition (unpaired binomial, delta-method):** `σ_wr = √(score·(1−score)/N)`, then `σ_elo = (400/ln10)·σ_wr/(score·(1−score))`. Code: `eval_net_vs_heuristic.py:194-200`.
- **Reference values near wr=0.5:** n=100 → ≈ **±35 elo**; n=400 → ≈ **±17 elo**; ±9 elo needs n≈1500. (This corrects the older CLAUDE.md "n=400 = ±9" doctrine, which was ~2× too optimistic — see round-2 audit G-M1.)
- **⚠ The σ formula assumes independent games and does NOT credit deck-pairing.** Under `--paired`, the two color-swapped games of a deck are correlated, so the true variance is lower than this σ reports — but the verdict threshold logic uses this (conservative) σ anyway. So a paired result's real significance may be slightly higher than the printed z; the formula never *over*-states significance from pairing, but it also is computed as if the paired games were 2 independent trials, which is a mild model error in both directions. Treat z within ±0.3 of a threshold as unresolved.

### `z` / "σ" multiples
- `z = elo / σ_elo`. The project's stated bars: **z≥2 = verdict, z<2 = screen.** A single screen at z≈1.4–1.9 is explicitly NOT a finding (the "noise signature" rule).

### `avg_diff`
- **Definition:** mean (net_score − opponent_score) over the games, from the net's seat. Code: `eval_net_vs_heuristic.py:174`. A margin estimator; lower-variance than W/L/D but **unused in the verdict logic** (round-2 audit G-M8 flags this as wasted signal).

### `wr` (win-rate / score)
- `(W + 0.5·D)/N`. Draws count half. Reported as a %.

### `marginal` (used only for the value levers)
- **Definition:** `elo(leaf with value, scale=λ) − elo(same net, scale=0)`, same checkpoint both sides, paired seeds. This isolates the **value head's contribution** from the policy's. The residual "win" is a *marginal* (+45), NOT an absolute strength gain. Reading the absolute number instead of the marginal would credit the policy retrain to the value lever.

---

## Training / learning metrics

### `value_corr` (a.k.a. value↔outcome corr, held-out)
- **Definition:** Pearson r between the value head's prediction and the stored value target, on held-out positions. Code: `train_iter.py:156-192` (in-loop readout) and `scripts/probe_heldout_value_corr.py` (gate probe).
- **Target reference:** the v2.7 heuristic leaf scores **0.61** against final outcome; the net is "good" if it clears that.
- **⚠ This is the single most over-interpreted metric in the project.** The value head was driven from corr 0.18 → 0.81 (and a tree-target head to 0.84) — yet at every corr level the value-as-search-leaf stayed a 80–576-elo liability, and ranked sibling moves at Kendall-τ ≈ chance (0.08 vs v2.7's 0.58). **Conclusion the project reached: outcome-correlation is the WRONG gauge for "is this value useful in search."** A reviewer should not read rising value_corr as rising strength.

### `tau` / Kendall-τ (decision-ranking probe)
- **Definition:** Kendall rank correlation between a leaf's scoring of a node's sibling children and the deep-search oracle Q ranking of those children. Code: `scripts/probe_decision_ranking.py`. v2.7 ≈ +0.58; learned value heads ≈ +0.08 (chance). Introduced 2026-06-05 as the *correct* gauge after value_corr proved misleading.

### `entropy` (policy entropy)
- Mean policy-head entropy over a batch; `train_iter.py:_mean_policy_entropy`. Used as a collapse guard (exit if trained entropy < `entropy_floor_frac` × baseline). Stable ~1.74 through the policy_scale erosion, i.e. erosion was NOT exploration collapse.

### `policy_loss` / `value_loss` / `own_loss` / `rank_loss` / `center_loss`
- Cross-entropy (policy, 2511-way), MSE (value, vs tanh target), MSE (ownership aux), listwise-CE (ranking), centered-MSE. Assembled as a **weighted sum** at `train_iter.py:574-580`. ⚠ Default weights: policy 1.0 + value 1.0 + aux 0.15. Because policy CE is O(2–6) and value MSE is O(0.1–1), value is **~5–10× under-weighted** in the gradient by default (round-2 audit G-T2). Any "value-in-loop doesn't help" conclusion is confounded by this unless `--value-loss-weight` was raised.

---

## Search / self-play diagnostics

### `sims`
- MCTS simulations per move. Production self-play & default eval = **200**. Ladder/depth probes sweep {50,100,200,400,800,1600,3200}. The "sims plane" matters: a checkpoint can be best at sims=200 and not at sims=800 (deepsearch vs iter_B1).

### `heur-equiv depth` / `crossover`
- The HeuristicMCTS sim budget at which the net's win-rate crosses 0.5; interpolated in log2(sims) space. Code: `ladder_asymmetric.py:44-62`. The odometer's headline: residual net ≈ 588 heur-equiv sims vs pure-policy ≈ 325. **⚠ Both sides bottom out in the virtual_score family**, so this measures "how deep a heuristic searcher you out-play," not absolute skill.

### `value_blend` (λ) / `residual_scale` (scale)
- λ: leaf = `(1−λ)·v2.7 + λ·v_nn`. scale: leaf = `clip(v2.7 + scale·Δ, ±1)`, Δ = head's prediction of (searchQ − v2.7). Code: `evaluators.py:186-192`. λ=1 = pure NN leaf (the −576 "calibration cliff").

---

## Provenance fields (results.csv columns)
| column | meaning | gotcha |
|---|---|---|
| `game` | `river` or `base` | **river ≠ base** — scores not comparable across the 2026-06-02 game change (the +181.7→+25.2 collapse) |
| `code_rev` | git short hash + `-dirty` | `unknown` for all pre-2026-06-02 rows (manifests didn't exist) → those rows are NOT reproducible to a commit |
| `new_var`/`old_var` | leaf variant (`v2_7`, `tile_counting`, `v2_7+resid_s0.25`, …) | the residual_scale is NOT captured in the manifest `leaf_env` |
| `confidence` | hand-set `low`/`medium`/`high` | tracks n (low≈n100, high≈n400) but is a human judgement, not computed |
| `src_dir` | path to the raw eval dir (mostly on the CIFS share `/mnt/c/carc-shared`) | many dirs are off-repo; manifest.json inside each is the resolved config |
