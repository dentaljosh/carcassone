# TILE-decision leaf top-2 tie census — CENSUS.md

Generated 2026-08-18T15:11:50Z · git `2565525b` · leaf hash `a36d2e15a3b3d71d` (assert OK) · 14520 rows total.

Wall clock: 35.8s total (30 workers, split {'walled': 30}) · mean seconds/ply (leaf compute only) = 0.040105034435261706.

> **Timing caveat:** tiearb widening corpus (s2); 100% walled self-play (e4 and CL-070 bank strata off via --limit-e4-games 0 / --limit-bank 0)

Question: does the JCZ corpus's reported top-2 exact-tie rate of **55.1%** (7,817/14,190, `scripts/jcz_mining/mine_disagreements.py`) replicate on our own position distributions?

## 1. Exact-tie rate (and the full `TIE_EPS_GRID`)

| group | n | exact tie (eps=0.0) 95% CI | eps=0.05 | eps=0.2 | eps=0.5 | eps=1.0 |
|---|---:|---|---|---|---|---|
| selfplay|ALL|ALL | 14520 | 62.7% [61.9, 63.5] (9106/14520) | 63.1% [62.3, 63.9] (9165/14520) | 65.1% [64.3, 65.9] (9456/14520) | 69.5% [68.7, 70.2] (10088/14520) | 77.7% [77.0, 78.4] (11282/14520) |
| selfplay|champ_games|walled | 14520 | 62.7% [61.9, 63.5] (9106/14520) | 63.1% [62.3, 63.9] (9165/14520) | 65.1% [64.3, 65.9] (9456/14520) | 69.5% [68.7, 70.2] (10088/14520) | 77.7% [77.0, 78.4] (11282/14520) |
| ALL|ALL|ALL | 14520 | 62.7% [61.9, 63.5] (9106/14520) | 63.1% [62.3, 63.9] (9165/14520) | 65.1% [64.3, 65.9] (9456/14520) | 69.5% [68.7, 70.2] (10088/14520) | 77.7% [77.0, 78.4] (11282/14520) |

- `selfplay|champ_games|walled`: 62.7% vs JCZ 55.1% -> **HIGHER**

## 2. Tied-set SIZE distribution (exact ties only)

| group | n_tied | mean | median | size=2 | size=3 | size=4 | size=5 | size=6 | size=7 | size=8 | size=9-12 | size=13+ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| selfplay|ALL|ALL | 9106 | 8.52 | 4 | 3333 | 974 | 1795 | 179 | 483 | 109 | 359 | 350 | 1524 |
| selfplay|champ_games|walled | 9106 | 8.52 | 4 | 3333 | 974 | 1795 | 179 | 483 | 109 | 359 | 350 | 1524 |
| ALL|ALL|ALL | 9106 | 8.52 | 4 | 3333 | 974 | 1795 | 179 | 483 | 109 | 359 | 350 | 1524 |

(pct at size 2 vs size >=5, ALL|ALL|ALL): 36.6% vs 33.0%

## 3. Top-2 gap distribution among NON-exact-tie plies

| group | n | min | p1 | p5 | p10 | p25 | p50 | p75 | p90 | max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| selfplay|ALL|ALL | 5414 | 0.0000 | 0.0500 | 0.1500 | 0.3000 | 0.7500 | 1.5000 | 3.0000 | 5.8000 | 36.9500 |
| selfplay|champ_games|walled | 5414 | 0.0000 | 0.0500 | 0.1500 | 0.3000 | 0.7500 | 1.5000 | 3.0000 | 5.8000 | 36.9500 |
| ALL|ALL|ALL | 5414 | 0.0000 | 0.0500 | 0.1500 | 0.3000 | 0.7500 | 1.5000 | 3.0000 | 5.8000 | 36.9500 |

**Top-20 most common exact gap values (`ALL|ALL|ALL`)** — the lattice:

| gap value | count |
|---:|---:|
| 1.000000 | 498 |
| 3.000000 | 212 |
| 1.500000 | 212 |
| 0.500000 | 196 |
| 2.000000 | 174 |
| 0.750000 | 143 |
| 0.250000 | 135 |
| 1.250000 | 119 |
| 4.000000 | 99 |
| 2.500000 | 89 |
| 2.250000 | 60 |
| 0.600000 | 59 |
| 2.750000 | 56 |
| 0.150000 | 52 |
| 5.000000 | 51 |
| 1.750000 | 51 |
| 3.750000 | 47 |
| 0.100000 | 45 |
| 6.000000 | 44 |
| 0.400000 | 43 |

## 4. Phase trend — exact-tie rate + mean tied size

**selfplay|ALL|ALL** (n=14520)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 4633 | 64.5% | 4.14 |
| phase_bucket | mid | 4746 | 59.3% | 7.29 |
| phase_bucket | late | 5141 | 64.2% | 13.54 |
| tercile | 0 | 4649 | 64.5% | 4.14 |
| tercile | 1 | 4951 | 59.4% | 7.29 |
| tercile | 2 | 4920 | 64.4% | 13.82 |
| n_legal quartile | Q1 (<=18) | 3784 | 62.9% | 4.01 |
| n_legal quartile | Q2 (<=27) | 3676 | 58.0% | 5.62 |
| n_legal quartile | Q3 (<=36) | 3592 | 62.8% | 8.80 |
| n_legal quartile | Q4 (>36) | 3468 | 67.4% | 15.51 |

**selfplay|champ_games|walled** (n=14520)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 4633 | 64.5% | 4.14 |
| phase_bucket | mid | 4746 | 59.3% | 7.29 |
| phase_bucket | late | 5141 | 64.2% | 13.54 |
| tercile | 0 | 4649 | 64.5% | 4.14 |
| tercile | 1 | 4951 | 59.4% | 7.29 |
| tercile | 2 | 4920 | 64.4% | 13.82 |
| n_legal quartile | Q1 (<=18) | 3784 | 62.9% | 4.01 |
| n_legal quartile | Q2 (<=27) | 3676 | 58.0% | 5.62 |
| n_legal quartile | Q3 (<=36) | 3592 | 62.8% | 8.80 |
| n_legal quartile | Q4 (>36) | 3468 | 67.4% | 15.51 |

**ALL|ALL|ALL** (n=14520)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 4633 | 64.5% | 4.14 |
| phase_bucket | mid | 4746 | 59.3% | 7.29 |
| phase_bucket | late | 5141 | 64.2% | 13.54 |
| tercile | 0 | 4649 | 64.5% | 4.14 |
| tercile | 1 | 4951 | 59.4% | 7.29 |
| tercile | 2 | 4920 | 64.4% | 13.82 |
| n_legal quartile | Q1 (<=18) | 3784 | 62.9% | 4.01 |
| n_legal quartile | Q2 (<=27) | 3676 | 58.0% | 5.62 |
| n_legal quartile | Q3 (<=36) | 3592 | 62.8% | 8.80 |
| n_legal quartile | Q4 (>36) | 3468 | 67.4% | 15.51 |

## 5. `played_in_tieset_exact` / `played_is_argmax`

| group | n (with action_played) | played in exact tie-set | played == argmax |
|---|---:|---|---|
| selfplay|ALL|ALL | 14520 | 85.7% [85.1, 86.3] (12445/14520) | 63.9% [63.1, 64.7] (9276/14520) |
| selfplay|champ_games|walled | 14520 | 85.7% [85.1, 86.3] (12445/14520) | 63.9% [63.1, 64.7] (9276/14520) |
| ALL|ALL|ALL | 14520 | 85.7% [85.1, 86.3] (12445/14520) | 63.9% [63.1, 64.7] (9276/14520) |

## 6. What this census does NOT show

This is a **leaf-silence** census: it counts how often the production leaf assigns the SAME value to the top TILE placement(s), and how big that tied set is. It says **nothing** about whether the tied moves differ in true VALUE — a leaf tie is consistent with the tied moves being genuinely equally good, or with the leaf being blind to a real difference between them. Answering that requires an oracle/search-based scoring pass over the tied moves, which this census deliberately does not run (leaf evaluations only, no search, no oracle scoring — see the GOAL spec this census answers to).
