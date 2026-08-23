# TILE-decision leaf top-2 tie census — CENSUS.md

Generated 2026-08-18T06:21:35Z · git `06adef99` · leaf hash `a36d2e15a3b3d71d` (assert OK) · 1500 rows total.

Wall clock: 4.9s total (30 workers, split {'walled': 30}) · mean seconds/ply (leaf compute only) = 0.03786093333333333.

> **Timing caveat:** tiearb widening corpus (s2); 100% walled self-play (e4 and CL-070 bank strata off via --limit-e4-games 0 / --limit-bank 0)

Question: does the JCZ corpus's reported top-2 exact-tie rate of **55.1%** (7,817/14,190, `scripts/jcz_mining/mine_disagreements.py`) replicate on our own position distributions?

## 1. Exact-tie rate (and the full `TIE_EPS_GRID`)

| group | n | exact tie (eps=0.0) 95% CI | eps=0.05 | eps=0.2 | eps=0.5 | eps=1.0 |
|---|---:|---|---|---|---|---|
| selfplay|ALL|ALL | 1500 | 63.7% [61.3, 66.1] (956/1500) | 64.5% [62.1, 66.9] (968/1500) | 66.2% [63.8, 68.5] (993/1500) | 70.5% [68.2, 72.8] (1058/1500) | 77.5% [75.4, 79.6] (1163/1500) |
| selfplay|champ_games|walled | 1500 | 63.7% [61.3, 66.1] (956/1500) | 64.5% [62.1, 66.9] (968/1500) | 66.2% [63.8, 68.5] (993/1500) | 70.5% [68.2, 72.8] (1058/1500) | 77.5% [75.4, 79.6] (1163/1500) |
| ALL|ALL|ALL | 1500 | 63.7% [61.3, 66.1] (956/1500) | 64.5% [62.1, 66.9] (968/1500) | 66.2% [63.8, 68.5] (993/1500) | 70.5% [68.2, 72.8] (1058/1500) | 77.5% [75.4, 79.6] (1163/1500) |

- `selfplay|champ_games|walled`: 63.7% vs JCZ 55.1% -> **HIGHER**

## 2. Tied-set SIZE distribution (exact ties only)

| group | n_tied | mean | median | size=2 | size=3 | size=4 | size=5 | size=6 | size=7 | size=8 | size=9-12 | size=13+ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| selfplay|ALL|ALL | 956 | 8.30 | 4 | 338 | 107 | 197 | 30 | 52 | 6 | 37 | 37 | 152 |
| selfplay|champ_games|walled | 956 | 8.30 | 4 | 338 | 107 | 197 | 30 | 52 | 6 | 37 | 37 | 152 |
| ALL|ALL|ALL | 956 | 8.30 | 4 | 338 | 107 | 197 | 30 | 52 | 6 | 37 | 37 | 152 |

(pct at size 2 vs size >=5, ALL|ALL|ALL): 35.4% vs 32.8%

## 3. Top-2 gap distribution among NON-exact-tie plies

| group | n | min | p1 | p5 | p10 | p25 | p50 | p75 | p90 | max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| selfplay|ALL|ALL | 544 | 0.0000 | 0.0500 | 0.1500 | 0.2650 | 0.8500 | 1.5000 | 3.1625 | 6.0000 | 34.7000 |
| selfplay|champ_games|walled | 544 | 0.0000 | 0.0500 | 0.1500 | 0.2650 | 0.8500 | 1.5000 | 3.1625 | 6.0000 | 34.7000 |
| ALL|ALL|ALL | 544 | 0.0000 | 0.0500 | 0.1500 | 0.2650 | 0.8500 | 1.5000 | 3.1625 | 6.0000 | 34.7000 |

**Top-20 most common exact gap values (`ALL|ALL|ALL`)** — the lattice:

| gap value | count |
|---:|---:|
| 1.000000 | 52 |
| 0.500000 | 23 |
| 1.500000 | 21 |
| 2.000000 | 20 |
| 3.000000 | 16 |
| 0.250000 | 12 |
| 0.750000 | 11 |
| 1.750000 | 11 |
| 2.750000 | 9 |
| 6.000000 | 9 |
| 3.750000 | 7 |
| 4.000000 | 6 |
| 1.250000 | 6 |
| 5.500000 | 6 |
| 0.200000 | 6 |
| 0.450000 | 5 |
| 2.500000 | 5 |
| 2.250000 | 5 |
| 0.050000 | 4 |
| 0.600000 | 4 |

## 4. Phase trend — exact-tie rate + mean tied size

**selfplay|ALL|ALL** (n=1500)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 473 | 67.4% | 4.13 |
| phase_bucket | mid | 490 | 61.6% | 6.88 |
| phase_bucket | late | 537 | 62.4% | 13.54 |
| tercile | 0 | 474 | 67.5% | 4.12 |
| tercile | 1 | 508 | 61.4% | 6.77 |
| tercile | 2 | 518 | 62.5% | 13.89 |
| n_legal quartile | Q1 (<=18) | 408 | 64.7% | 3.92 |
| n_legal quartile | Q2 (<=27) | 371 | 57.7% | 5.43 |
| n_legal quartile | Q3 (<=36) | 381 | 65.9% | 7.86 |
| n_legal quartile | Q4 (>36) | 340 | 66.8% | 16.57 |

**selfplay|champ_games|walled** (n=1500)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 473 | 67.4% | 4.13 |
| phase_bucket | mid | 490 | 61.6% | 6.88 |
| phase_bucket | late | 537 | 62.4% | 13.54 |
| tercile | 0 | 474 | 67.5% | 4.12 |
| tercile | 1 | 508 | 61.4% | 6.77 |
| tercile | 2 | 518 | 62.5% | 13.89 |
| n_legal quartile | Q1 (<=18) | 408 | 64.7% | 3.92 |
| n_legal quartile | Q2 (<=27) | 371 | 57.7% | 5.43 |
| n_legal quartile | Q3 (<=36) | 381 | 65.9% | 7.86 |
| n_legal quartile | Q4 (>36) | 340 | 66.8% | 16.57 |

**ALL|ALL|ALL** (n=1500)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 473 | 67.4% | 4.13 |
| phase_bucket | mid | 490 | 61.6% | 6.88 |
| phase_bucket | late | 537 | 62.4% | 13.54 |
| tercile | 0 | 474 | 67.5% | 4.12 |
| tercile | 1 | 508 | 61.4% | 6.77 |
| tercile | 2 | 518 | 62.5% | 13.89 |
| n_legal quartile | Q1 (<=18) | 408 | 64.7% | 3.92 |
| n_legal quartile | Q2 (<=27) | 371 | 57.7% | 5.43 |
| n_legal quartile | Q3 (<=36) | 381 | 65.9% | 7.86 |
| n_legal quartile | Q4 (>36) | 340 | 66.8% | 16.57 |

## 5. `played_in_tieset_exact` / `played_is_argmax`

| group | n (with action_played) | played in exact tie-set | played == argmax |
|---|---:|---|---|
| selfplay|ALL|ALL | 1500 | 85.9% [84.1, 87.6] (1289/1500) | 63.1% [60.6, 65.5] (946/1500) |
| selfplay|champ_games|walled | 1500 | 85.9% [84.1, 87.6] (1289/1500) | 63.1% [60.6, 65.5] (946/1500) |
| ALL|ALL|ALL | 1500 | 85.9% [84.1, 87.6] (1289/1500) | 63.1% [60.6, 65.5] (946/1500) |

## 6. What this census does NOT show

This is a **leaf-silence** census: it counts how often the production leaf assigns the SAME value to the top TILE placement(s), and how big that tied set is. It says **nothing** about whether the tied moves differ in true VALUE — a leaf tie is consistent with the tied moves being genuinely equally good, or with the leaf being blind to a real difference between them. Answering that requires an oracle/search-based scoring pass over the tied moves, which this census deliberately does not run (leaf evaluations only, no search, no oracle scoring — see the GOAL spec this census answers to).
