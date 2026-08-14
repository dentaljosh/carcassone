# k-WIDTH / DETERMINIZATION AT TIED PLIES — DEV LADDER READOUT

Read-rule: [READ_RULE.md](READ_RULE.md) · design: [DESIGN.md](DESIGN.md) (both committed before the run). Generated 2026-08-14T23:23:03Z.

- dev slice positions: **522** · analyzed rows: **522** · counters: `{"oracle_integrity_problems": 0}`
- honest base-rung regret (denominator): **+0.2803 ± +0.0708 pts/ply** (n=518)
- witness (i) base pick vs corpus champ pick (selfplay): 485/485
- witness (ii) base pick vs the VART's own k8x1376 records: 522/522 (missing 0)
- holdout: NOT OPENED — this program has no holdout code path (READ_RULE §1); the 211-position slice stays unburned.

| rung | k × sims/det (total) | class | capture [pts/ply] | se | z | capture ratio | ratio 95% CI | coverage | pick-change (arm) | outside-scored | median s/pos | deploy mult |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **R0** | 8 × 1376 (11,008) | base | — | — | — | — | — | 0.992 | — | — | 1.7 | 1.00 |
| R1 | 16 × 1376 (22,016) | expansion | +0.0319 | +0.0437 | +0.73 | +0.114 | [-0.20, +0.43] | 0.931 | 0.200 | 0.062 | 3.3 | 1.33 |
| R2 | 32 × 1376 (44,032) | expansion | +0.0720 | +0.0431 | +1.67 | +0.257 | [-0.05, +0.56] | 0.912 | 0.223 | 0.081 | 6.7 | 1.99 |
| R3 | 64 × 1376 (88,064) | expansion | +0.0252 | +0.0496 | +0.51 | +0.090 | [-0.26, +0.44] | 0.908 | 0.268 | 0.085 | 13.1 | 3.31 |
| **C1** | 16 × 688 (11,008) | isobudget | +0.0260 | +0.0517 | +0.50 | +0.093 | [-0.28, +0.46] | 0.912 | 0.244 | 0.081 | 1.6 | 1.00 |
| **C2** | 32 × 344 (11,008) | isobudget | +0.0848 | +0.0588 | +1.44 | +0.303 | [-0.12, +0.72] | 0.889 | 0.362 | 0.104 | 1.7 | 1.00 |

## Verdict: **W-FLAT**

Mandatory sentence (READ_RULE §6): *Neither static afterstate functions (two failed menus + the 38% reach bound), nor deeper same-shape search (the vart, E-FLAT), nor wider determinization — at increased budget OR at the champion's own budget — expresses the +0.252 pts/ply oracle spread at leaf-tied plies. With all three named mechanisms closed, the leading remaining explanation of the tile-tie signal is a **judge artifact**: the in-family `clair-puct` oracle's own bias, which only an out-of-family re-pricing can settle.*

⚠️ **SCOPE OF THE FLAT — a rung that did not FIRE has not EXCLUDED the bar.** W-FLAT is a *funding* verdict: no rung cleared ratio ≥ 0.35 ∧ z ≥ +2 ∧ coverage ≥ 0.85. It is NOT an exclusion of a bar-sized effect except where the 95% upper bound on the ratio sits below 0.35 — true for `[]`, NOT true for `['R1', 'R2', 'R3', 'C1', 'C2']`, whose intervals still admit capture at or above the bar. The honest claim is *"the k-width axis did not fire at a mechanism-sized bar on 522 dev positions"*, not *"k-width is worth nothing"*.

### Realized 2σ resolution (READ_RULE §7)

| rung | 2σ [pts/ply] | 2σ [elo, ÷3.2] | 2σ [elo, ÷5.23 low-end] |
|---|---|---|---|
| R1 | 0.0873 | +8.5 | +5.2 |
| R2 | 0.0862 | +8.4 | +5.1 |
| R3 | 0.0992 | +9.7 | +5.9 |
| C1 | 0.1035 | +10.1 | +6.2 |
| C2 | 0.1177 | +11.5 | +7.0 |

⚠️ Wall-clock ratios are indicative only (DESIGN §7.7); absolutes are not a bench.

⚠️ World duplication (DESIGN §7.3): late positions cannot deal 64 distinct worlds from a small unseen deck, so R3 (and to a lesser extent R2/C2) is a weakly-increasing evidence set late — a bias toward FLAT at the top of the ladder.
