# TILE-decision leaf top-2 tie census — CENSUS.md

Generated 2026-08-18T15:11:14Z · git `2565525b` · leaf hash `a36d2e15a3b3d71d` (assert OK) · 2032 rows total.

Wall clock: 5.7s total (30 workers, split {'walled': 30}) · mean seconds/ply (leaf compute only) = 0.03924424212598425.

> **Timing caveat:** tiearb widening corpus (s1); 100% walled self-play (e4 and CL-070 bank strata off via --limit-e4-games 0 / --limit-bank 0)

Question: does the JCZ corpus's reported top-2 exact-tie rate of **55.1%** (7,817/14,190, `scripts/jcz_mining/mine_disagreements.py`) replicate on our own position distributions?

## 1. Exact-tie rate (and the full `TIE_EPS_GRID`)

| group | n | exact tie (eps=0.0) 95% CI | eps=0.05 | eps=0.2 | eps=0.5 | eps=1.0 |
|---|---:|---|---|---|---|---|
| selfplay|ALL|ALL | 2032 | 62.5% [60.4, 64.6] (1271/2032) | 63.0% [60.9, 65.1] (1281/2032) | 65.3% [63.2, 67.3] (1327/2032) | 69.6% [67.6, 71.6] (1415/2032) | 77.9% [76.0, 79.6] (1582/2032) |
| selfplay|champ_games|walled | 2032 | 62.5% [60.4, 64.6] (1271/2032) | 63.0% [60.9, 65.1] (1281/2032) | 65.3% [63.2, 67.3] (1327/2032) | 69.6% [67.6, 71.6] (1415/2032) | 77.9% [76.0, 79.6] (1582/2032) |
| ALL|ALL|ALL | 2032 | 62.5% [60.4, 64.6] (1271/2032) | 63.0% [60.9, 65.1] (1281/2032) | 65.3% [63.2, 67.3] (1327/2032) | 69.6% [67.6, 71.6] (1415/2032) | 77.9% [76.0, 79.6] (1582/2032) |

- `selfplay|champ_games|walled`: 62.5% vs JCZ 55.1% -> **HIGHER**

## 2. Tied-set SIZE distribution (exact ties only)

| group | n_tied | mean | median | size=2 | size=3 | size=4 | size=5 | size=6 | size=7 | size=8 | size=9-12 | size=13+ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| selfplay|ALL|ALL | 1271 | 8.37 | 4 | 459 | 126 | 249 | 25 | 81 | 13 | 63 | 50 | 205 |
| selfplay|champ_games|walled | 1271 | 8.37 | 4 | 459 | 126 | 249 | 25 | 81 | 13 | 63 | 50 | 205 |
| ALL|ALL|ALL | 1271 | 8.37 | 4 | 459 | 126 | 249 | 25 | 81 | 13 | 63 | 50 | 205 |

(pct at size 2 vs size >=5, ALL|ALL|ALL): 36.1% vs 34.4%

## 3. Top-2 gap distribution among NON-exact-tie plies

| group | n | min | p1 | p5 | p10 | p25 | p50 | p75 | p90 | max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| selfplay|ALL|ALL | 761 | 0.0000 | 0.0500 | 0.1500 | 0.2500 | 0.7500 | 1.5000 | 3.3500 | 5.7500 | 33.6000 |
| selfplay|champ_games|walled | 761 | 0.0000 | 0.0500 | 0.1500 | 0.2500 | 0.7500 | 1.5000 | 3.3500 | 5.7500 | 33.6000 |
| ALL|ALL|ALL | 761 | 0.0000 | 0.0500 | 0.1500 | 0.2500 | 0.7500 | 1.5000 | 3.3500 | 5.7500 | 33.6000 |

**Top-20 most common exact gap values (`ALL|ALL|ALL`)** — the lattice:

| gap value | count |
|---:|---:|
| 1.000000 | 78 |
| 3.000000 | 31 |
| 1.500000 | 27 |
| 2.000000 | 24 |
| 0.250000 | 24 |
| 0.500000 | 24 |
| 4.000000 | 23 |
| 0.750000 | 14 |
| 1.250000 | 12 |
| 0.150000 | 11 |
| 0.600000 | 11 |
| 5.000000 | 10 |
| 1.750000 | 10 |
| 5.500000 | 9 |
| 2.250000 | 9 |
| 2.500000 | 8 |
| 6.000000 | 8 |
| 0.100000 | 8 |
| 4.500000 | 7 |
| 3.750000 | 7 |

## 4. Phase trend — exact-tie rate + mean tied size

**selfplay|ALL|ALL** (n=2032)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 640 | 65.8% | 4.42 |
| phase_bucket | mid | 632 | 58.5% | 7.26 |
| phase_bucket | late | 760 | 63.2% | 12.68 |
| tercile | 0 | 643 | 65.6% | 4.42 |
| tercile | 1 | 655 | 58.2% | 7.16 |
| tercile | 2 | 734 | 63.8% | 12.90 |
| n_legal quartile | Q1 (<=18) | 534 | 64.2% | 4.07 |
| n_legal quartile | Q2 (<=27) | 509 | 56.2% | 5.68 |
| n_legal quartile | Q3 (<=36) | 486 | 62.8% | 8.92 |
| n_legal quartile | Q4 (>36) | 503 | 67.0% | 14.51 |

**selfplay|champ_games|walled** (n=2032)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 640 | 65.8% | 4.42 |
| phase_bucket | mid | 632 | 58.5% | 7.26 |
| phase_bucket | late | 760 | 63.2% | 12.68 |
| tercile | 0 | 643 | 65.6% | 4.42 |
| tercile | 1 | 655 | 58.2% | 7.16 |
| tercile | 2 | 734 | 63.8% | 12.90 |
| n_legal quartile | Q1 (<=18) | 534 | 64.2% | 4.07 |
| n_legal quartile | Q2 (<=27) | 509 | 56.2% | 5.68 |
| n_legal quartile | Q3 (<=36) | 486 | 62.8% | 8.92 |
| n_legal quartile | Q4 (>36) | 503 | 67.0% | 14.51 |

**ALL|ALL|ALL** (n=2032)

| axis | bucket | n | exact-tie rate | mean tied size |
|---|---|---:|---:|---:|
| phase_bucket | early | 640 | 65.8% | 4.42 |
| phase_bucket | mid | 632 | 58.5% | 7.26 |
| phase_bucket | late | 760 | 63.2% | 12.68 |
| tercile | 0 | 643 | 65.6% | 4.42 |
| tercile | 1 | 655 | 58.2% | 7.16 |
| tercile | 2 | 734 | 63.8% | 12.90 |
| n_legal quartile | Q1 (<=18) | 534 | 64.2% | 4.07 |
| n_legal quartile | Q2 (<=27) | 509 | 56.2% | 5.68 |
| n_legal quartile | Q3 (<=36) | 486 | 62.8% | 8.92 |
| n_legal quartile | Q4 (>36) | 503 | 67.0% | 14.51 |

## 5. `played_in_tieset_exact` / `played_is_argmax`

| group | n (with action_played) | played in exact tie-set | played == argmax |
|---|---:|---|---|
| selfplay|ALL|ALL | 2032 | 86.1% [84.6, 87.6] (1750/2032) | 64.4% [62.3, 66.4] (1308/2032) |
| selfplay|champ_games|walled | 2032 | 86.1% [84.6, 87.6] (1750/2032) | 64.4% [62.3, 66.4] (1308/2032) |
| ALL|ALL|ALL | 2032 | 86.1% [84.6, 87.6] (1750/2032) | 64.4% [62.3, 66.4] (1308/2032) |

## 6. What this census does NOT show

This is a **leaf-silence** census: it counts how often the production leaf assigns the SAME value to the top TILE placement(s), and how big that tied set is. It says **nothing** about whether the tied moves differ in true VALUE — a leaf tie is consistent with the tied moves being genuinely equally good, or with the leaf being blind to a real difference between them. Answering that requires an oracle/search-based scoring pass over the tied moves, which this census deliberately does not run (leaf evaluations only, no search, no oracle scoring — see the GOAL spec this census answers to).
