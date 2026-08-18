# TILE-decision leaf top-2 tie census — CENSUS.md

Generated 2026-08-17T00:08:19Z · git `504ddad1` · leaf hash `a36d2e15a3b3d71d` (assert OK) · 3400 rows total.

Wall clock: 6.9s total (30 workers, split {'walled': 30}) · mean seconds/ply (leaf compute only) = 0.03675232352941176.

> **Timing caveat:** tiearb2 corpus assembly; 100% walled self-play (e4 and CL-070 bank strata switched off via --limit-e4-games 0 / --limit-bank 0)

Question: does the JCZ corpus's reported top-2 exact-tie rate of **55.1%** (7,817/14,190, `scripts/jcz_mining/mine_disagreements.py`) replicate on our own position distributions?

## 1. Exact-tie rate (and the full `TIE_EPS_GRID`)

| group | n | exact tie (eps=0.0) 95% CI | eps=0.05 | eps=0.2 | eps=0.5 | eps=1.0 |
|---|---:|---|---|---|---|---|
| selfplay|ALL|ALL | 3400 | 64.4% [62.8, 66.0] (2191/3400) | 64.7% [63.1, 66.3] (2199/3400) | 67.0% [65.4, 68.6] (2278/3400) | 71.1% [69.6, 72.6] (2419/3400) | 78.4% [77.0, 79.7] (2665/3400) |
| selfplay|champ_games|walled | 3400 | 64.4% [62.8, 66.0] (2191/3400) | 64.7% [63.1, 66.3] (2199/3400) | 67.0% [65.4, 68.6] (2278/3400) | 71.1% [69.6, 72.6] (2419/3400) | 78.4% [77.0, 79.7] (2665/3400) |
| ALL|ALL|ALL | 3400 | 64.4% [62.8, 66.0] (2191/3400) | 64.7% [63.1, 66.3] (2199/3400) | 67.0% [65.4, 68.6] (2278/3400) | 71.1% [69.6, 72.6] (2419/3400) | 78.4% [77.0, 79.7] (2665/3400) |

- `selfplay|champ_games|walled`: 64.4% vs JCZ 55.1% -> **HIGHER**

## 2. Tied-set SIZE distribution (exact ties only)

| group | n_tied | mean | median | size=2 | size=3 | size=4 | size=5 | size=6 | size=7 | size=8 | size=9-12 | size=13+ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| selfplay|ALL|ALL | 2191 | 8.76 | 4 | 803 | 198 | 420 | 50 | 143 | 23 | 88 | 84 | 382 |
| selfplay|champ_games|walled | 2191 | 8.76 | 4 | 803 | 198 | 420 | 50 | 143 | 23 | 88 | 84 | 382 |
| ALL|ALL|ALL | 2191 | 8.76 | 4 | 803 | 198 | 420 | 50 | 143 | 23 | 88 | 84 | 382 |

(pct at size 2 vs size >=5, ALL|ALL|ALL): 36.6% vs 35.1%

## 3. Top-2 gap distribution among NON-exact-tie plies

| group | n | min | p1 | p5 | p10 | p25 | p50 | p75 | p90 | max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| selfplay|ALL|ALL | 1209 | 0.0000 | 0.0500 | 0.1500 | 0.2500 | 0.7500 | 1.5000 | 3.1000 | 6.0000 | 27.4000 |
| selfplay|champ_games|walled | 1209 | 0.0000 | 0.0500 | 0.1500 | 0.2500 | 0.7500 | 1.5000 | 3.1000 | 6.0000 | 27.4000 |
| ALL|ALL|ALL | 1209 | 0.0000 | 0.0500 | 0.1500 | 0.2500 | 0.7500 | 1.5000 | 3.1000 | 6.0000 | 27.4000 |

**Top-20 most common exact gap values (`ALL|ALL|ALL`)** — the lattice:

| gap value | count |
|---:|---:|
| 1.000000 | 103 |
| 2.000000 | 52 |
| 3.000000 | 45 |
| 1.500000 | 41 |
| 0.500000 | 38 |
| 0.250000 | 32 |
| 0.750000 | 29 |
| 4.000000 | 23 |
| 1.250000 | 22 |
| 1.750000 | 21 |
| 2.500000 | 17 |
| 0.100000 | 16 |
| 0.600000 | 15 |
| 2.250000 | 14 |
| 0.150000 | 12 |
| 5.000000 | 12 |
| 0.150000 | 10 |
| 6.000000 | 9 |
| 0.600000 | 9 |
| 1.100000 | 9 |

## 4. Phase trend — exact-tie rate + mean tied size

**selfplay|ALL|ALL** (n=3400)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 1082 | 68.7% | 4.02 |
| phase_bucket | mid | 1124 | 60.2% | 7.62 |
| phase_bucket | late | 1194 | 64.6% | 14.32 |
| tercile | 0 | 1087 | 68.7% | 4.02 |
| tercile | 1 | 1171 | 60.4% | 7.62 |
| tercile | 2 | 1142 | 64.5% | 14.65 |
| n_legal quartile | Q1 (<=18) | 884 | 69.3% | 4.00 |
| n_legal quartile | Q2 (<=27) | 856 | 58.6% | 5.93 |
| n_legal quartile | Q3 (<=36) | 851 | 62.0% | 9.00 |
| n_legal quartile | Q4 (>36) | 809 | 67.7% | 16.43 |

**selfplay|champ_games|walled** (n=3400)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 1082 | 68.7% | 4.02 |
| phase_bucket | mid | 1124 | 60.2% | 7.62 |
| phase_bucket | late | 1194 | 64.6% | 14.32 |
| tercile | 0 | 1087 | 68.7% | 4.02 |
| tercile | 1 | 1171 | 60.4% | 7.62 |
| tercile | 2 | 1142 | 64.5% | 14.65 |
| n_legal quartile | Q1 (<=18) | 884 | 69.3% | 4.00 |
| n_legal quartile | Q2 (<=27) | 856 | 58.6% | 5.93 |
| n_legal quartile | Q3 (<=36) | 851 | 62.0% | 9.00 |
| n_legal quartile | Q4 (>36) | 809 | 67.7% | 16.43 |

**ALL|ALL|ALL** (n=3400)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 1082 | 68.7% | 4.02 |
| phase_bucket | mid | 1124 | 60.2% | 7.62 |
| phase_bucket | late | 1194 | 64.6% | 14.32 |
| tercile | 0 | 1087 | 68.7% | 4.02 |
| tercile | 1 | 1171 | 60.4% | 7.62 |
| tercile | 2 | 1142 | 64.5% | 14.65 |
| n_legal quartile | Q1 (<=18) | 884 | 69.3% | 4.00 |
| n_legal quartile | Q2 (<=27) | 856 | 58.6% | 5.93 |
| n_legal quartile | Q3 (<=36) | 851 | 62.0% | 9.00 |
| n_legal quartile | Q4 (>36) | 809 | 67.7% | 16.43 |

## 5. `played_in_tieset_exact` / `played_is_argmax`

| group | n (with action_played) | played in exact tie-set | played == argmax |
|---|---:|---|---|
| selfplay|ALL|ALL | 3400 | 86.2% [85.0, 87.3] (2930/3400) | 64.1% [62.4, 65.7] (2178/3400) |
| selfplay|champ_games|walled | 3400 | 86.2% [85.0, 87.3] (2930/3400) | 64.1% [62.4, 65.7] (2178/3400) |
| ALL|ALL|ALL | 3400 | 86.2% [85.0, 87.3] (2930/3400) | 64.1% [62.4, 65.7] (2178/3400) |

## 6. What this census does NOT show

This is a **leaf-silence** census: it counts how often the production leaf assigns the SAME value to the top TILE placement(s), and how big that tied set is. It says **nothing** about whether the tied moves differ in true VALUE — a leaf tie is consistent with the tied moves being genuinely equally good, or with the leaf being blind to a real difference between them. Answering that requires an oracle/search-based scoring pass over the tied moves, which this census deliberately does not run (leaf evaluations only, no search, no oracle scoring — see the GOAL spec this census answers to).
