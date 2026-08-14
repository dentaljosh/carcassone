# TIE-TRIGGERED SEARCH ESCALATION — DEV LADDER READOUT

Read-rule: [READ_RULE.md](READ_RULE.md) (committed before the run). Generated 2026-08-14T20:28:28Z.

- slice positions: **522** · analyzed rows: **522** · counters: `{"oracle_integrity_problems": 0}`
- honest base-rung regret (denominator): **+0.2803 ± +0.0708 pts/ply** (n=518)
- base-pick vs corpus champ-pick agreement (selfplay, witness): 485/485

| rung (sims/det) | capture [pts/ply] | se | z | capture ratio | coverage | pick-change (arm) | outside-scored | median s/pos | deploy mult est |
|---|---|---|---|---|---|---|---|---|---|
| 1376 (base) | — | — | — | — | 0.992 | — | — | 2.4 | 1.00 |
| 2752 | -0.0094 | +0.0362 | -0.26 | -0.034 | 0.902 | 0.183 | 0.091 | 4.8 | 1.33 |
| 5504 | +0.0494 | +0.0495 | +1.00 | +0.176 | 0.849 | 0.242 | 0.145 | 9.4 | 1.99 |
| 13760 | +0.0502 | +0.0598 | +0.84 | +0.179 | 0.799 | 0.312 | 0.195 | 24.9 | 3.97 |

## Verdict: **E-FLAT**

Mandatory sentence (READ_RULE §4): *neither static afterstate functions (two failed menus + the 38% reach bound) nor deeper same-shape search expresses the oracle spread* — which points at the ORACLE's in-family bias, or at k-width/determinization, as the remaining explanations of the +0.252 pts/ply.

⚠️ Wall-clock measured on a contended box (see DESIGN §7); ratios indicative, absolutes are not a bench.
