# TILE-decision leaf top-2 tie census — CENSUS.md

Generated 2026-08-18T06:21:30Z · git `06adef99` · leaf hash `a36d2e15a3b3d71d` (assert OK) · 1400 rows total.

Wall clock: 4.5s total (30 workers, split {'walled': 30}) · mean seconds/ply (leaf compute only) = 0.03944792857142857.

> **Timing caveat:** tiearb widening corpus (s1); 100% walled self-play (e4 and CL-070 bank strata off via --limit-e4-games 0 / --limit-bank 0)

Question: does the JCZ corpus's reported top-2 exact-tie rate of **55.1%** (7,817/14,190, `scripts/jcz_mining/mine_disagreements.py`) replicate on our own position distributions?

## 1. Exact-tie rate (and the full `TIE_EPS_GRID`)

| group | n | exact tie (eps=0.0) 95% CI | eps=0.05 | eps=0.2 | eps=0.5 | eps=1.0 |
|---|---:|---|---|---|---|---|
| selfplay|ALL|ALL | 1400 | 64.6% [62.1, 67.1] (905/1400) | 65.2% [62.7, 67.7] (913/1400) | 67.3% [64.8, 69.7] (942/1400) | 71.0% [68.6, 73.3] (994/1400) | 77.9% [75.6, 80.0] (1090/1400) |
| selfplay|champ_games|walled | 1400 | 64.6% [62.1, 67.1] (905/1400) | 65.2% [62.7, 67.7] (913/1400) | 67.3% [64.8, 69.7] (942/1400) | 71.0% [68.6, 73.3] (994/1400) | 77.9% [75.6, 80.0] (1090/1400) |
| ALL|ALL|ALL | 1400 | 64.6% [62.1, 67.1] (905/1400) | 65.2% [62.7, 67.7] (913/1400) | 67.3% [64.8, 69.7] (942/1400) | 71.0% [68.6, 73.3] (994/1400) | 77.9% [75.6, 80.0] (1090/1400) |

- `selfplay|champ_games|walled`: 64.6% vs JCZ 55.1% -> **HIGHER**

## 2. Tied-set SIZE distribution (exact ties only)

| group | n_tied | mean | median | size=2 | size=3 | size=4 | size=5 | size=6 | size=7 | size=8 | size=9-12 | size=13+ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| selfplay|ALL|ALL | 905 | 8.51 | 4 | 341 | 87 | 177 | 21 | 50 | 9 | 34 | 31 | 155 |
| selfplay|champ_games|walled | 905 | 8.51 | 4 | 341 | 87 | 177 | 21 | 50 | 9 | 34 | 31 | 155 |
| ALL|ALL|ALL | 905 | 8.51 | 4 | 341 | 87 | 177 | 21 | 50 | 9 | 34 | 31 | 155 |

(pct at size 2 vs size >=5, ALL|ALL|ALL): 37.7% vs 33.1%

## 3. Top-2 gap distribution among NON-exact-tie plies

| group | n | min | p1 | p5 | p10 | p25 | p50 | p75 | p90 | max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| selfplay|ALL|ALL | 495 | 0.0000 | 0.0000 | 0.1500 | 0.2500 | 0.7500 | 1.5500 | 3.6000 | 5.5000 | 27.0000 |
| selfplay|champ_games|walled | 495 | 0.0000 | 0.0000 | 0.1500 | 0.2500 | 0.7500 | 1.5500 | 3.6000 | 5.5000 | 27.0000 |
| ALL|ALL|ALL | 495 | 0.0000 | 0.0000 | 0.1500 | 0.2500 | 0.7500 | 1.5500 | 3.6000 | 5.5000 | 27.0000 |

**Top-20 most common exact gap values (`ALL|ALL|ALL`)** — the lattice:

| gap value | count |
|---:|---:|
| 1.000000 | 39 |
| 4.000000 | 23 |
| 1.500000 | 20 |
| 2.000000 | 19 |
| 0.250000 | 15 |
| 0.500000 | 12 |
| 3.000000 | 11 |
| 2.250000 | 8 |
| 1.750000 | 7 |
| 0.600000 | 7 |
| 1.250000 | 6 |
| 5.000000 | 6 |
| 0.750000 | 5 |
| 2.750000 | 5 |
| 0.600000 | 4 |
| 4.250000 | 4 |
| 1.100000 | 4 |
| 0.650000 | 4 |
| 2.500000 | 4 |
| 0.650000 | 4 |

## 4. Phase trend — exact-tie rate + mean tied size

**selfplay|ALL|ALL** (n=1400)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 434 | 68.9% | 4.27 |
| phase_bucket | mid | 467 | 61.5% | 8.06 |
| phase_bucket | late | 499 | 63.9% | 12.88 |
| tercile | 0 | 435 | 69.0% | 4.34 |
| tercile | 1 | 482 | 61.2% | 7.95 |
| tercile | 2 | 483 | 64.2% | 13.06 |
| n_legal quartile | Q1 (<=19) | 353 | 68.0% | 3.70 |
| n_legal quartile | Q2 (<=28) | 386 | 61.4% | 6.25 |
| n_legal quartile | Q3 (<=37) | 328 | 59.5% | 9.64 |
| n_legal quartile | Q4 (>37) | 333 | 70.0% | 14.80 |

**selfplay|champ_games|walled** (n=1400)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 434 | 68.9% | 4.27 |
| phase_bucket | mid | 467 | 61.5% | 8.06 |
| phase_bucket | late | 499 | 63.9% | 12.88 |
| tercile | 0 | 435 | 69.0% | 4.34 |
| tercile | 1 | 482 | 61.2% | 7.95 |
| tercile | 2 | 483 | 64.2% | 13.06 |
| n_legal quartile | Q1 (<=19) | 353 | 68.0% | 3.70 |
| n_legal quartile | Q2 (<=28) | 386 | 61.4% | 6.25 |
| n_legal quartile | Q3 (<=37) | 328 | 59.5% | 9.64 |
| n_legal quartile | Q4 (>37) | 333 | 70.0% | 14.80 |

**ALL|ALL|ALL** (n=1400)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 434 | 68.9% | 4.27 |
| phase_bucket | mid | 467 | 61.5% | 8.06 |
| phase_bucket | late | 499 | 63.9% | 12.88 |
| tercile | 0 | 435 | 69.0% | 4.34 |
| tercile | 1 | 482 | 61.2% | 7.95 |
| tercile | 2 | 483 | 64.2% | 13.06 |
| n_legal quartile | Q1 (<=19) | 353 | 68.0% | 3.70 |
| n_legal quartile | Q2 (<=28) | 386 | 61.4% | 6.25 |
| n_legal quartile | Q3 (<=37) | 328 | 59.5% | 9.64 |
| n_legal quartile | Q4 (>37) | 333 | 70.0% | 14.80 |

## 5. `played_in_tieset_exact` / `played_is_argmax`

| group | n (with action_played) | played in exact tie-set | played == argmax |
|---|---:|---|---|
| selfplay|ALL|ALL | 1400 | 85.6% [83.7, 87.4] (1199/1400) | 64.6% [62.0, 67.0] (904/1400) |
| selfplay|champ_games|walled | 1400 | 85.6% [83.7, 87.4] (1199/1400) | 64.6% [62.0, 67.0] (904/1400) |
| ALL|ALL|ALL | 1400 | 85.6% [83.7, 87.4] (1199/1400) | 64.6% [62.0, 67.0] (904/1400) |

## 6. What this census does NOT show

This is a **leaf-silence** census: it counts how often the production leaf assigns the SAME value to the top TILE placement(s), and how big that tied set is. It says **nothing** about whether the tied moves differ in true VALUE — a leaf tie is consistent with the tied moves being genuinely equally good, or with the leaf being blind to a real difference between them. Answering that requires an oracle/search-based scoring pass over the tied moves, which this census deliberately does not run (leaf evaluations only, no search, no oracle scoring — see the GOAL spec this census answers to).
