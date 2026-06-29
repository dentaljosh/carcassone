# FGSR_BASELINES.md — Stage 3 baselines (matched-compute, TEST split)

_generated 2026-06-29 01:49 · net-free · frozen v2.9 leaf · TEST = 1672 roots over 66 game-seeds (tr=7031 va=1648)_

## SANITY GATE

- **B3 `low_top2gap` AUROC(pos_strong) on TEST = 0.7255** (expected 0.72–0.73) → **REPRODUCED**.
- B5 flat-MLP AUROC(pos_medium) = 0.7974, AUROC(pos_strong) = 0.7797 (prior pilot reported ~0.78 on pos_medium).

## Uniform compute curve (mean h6400-regret vs avg sims, TEST)

| sims | 200 | 400 | 800 | 1600 | 3200 | 6400 |
|---|---|---|---|---|---|---|
| mean regret | 0.00284 | 0.00235 | 0.00169 | 0.00149 | 0.00061 | 0.00000 |

## Matched-compute regret (lower = better) — the bar to beat is **B3**

| baseline | AUROC(strong) | C=300 | C=400 | C=600 | C=800 | C=1200 |
|---|---|---|---|---|---|---|
| B0_uniform_h200 (h200=0.00284) | — | — | — | — | — | — |
| B1_uniform_h800 (h800=0.00169) | — | — | — | — | — | — |
| B2_uniform_h3200 (h3200=0.00061) | — | — | — | — | — | — |
| B3_low_top2gap | 0.725 | 0.00227 (h800) | 0.00204 (h800) | 0.00168 (h800) | 0.00160 (h1600) | 0.00130 (h3200) |
| B4_phase_opening | 0.691 | 0.00247 (h800) | 0.00213 (h800) | 0.00174 (h800) | 0.00169 (h800) | 0.00150 (h1600) |
| B5_flat_mlp | 0.780 | 0.00232 (h800) | 0.00176 (h800) | 0.00171 (h800) | 0.00161 (h1600) | 0.00110 (h3200) |
| B7_oracle_md | — | 0.00039 | 0.00017 | 0.00008 | 0.00003 | — |

_B0/B1/B2 are uniform constants (no escalation); the matched-compute columns apply to schedulers (B3/B4/B5) and the oracle (B7). D = the deeper level escalated to._

