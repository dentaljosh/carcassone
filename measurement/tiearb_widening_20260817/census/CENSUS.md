# MEEPLE-ply leaf tie kill-census — CENSUS.md

Generated 2026-08-18T02:41:30Z · git `1627a801` · leaf `a36d2e15a3b3d71d` (assert OK) · 1299 games · 74894 meeple rows · 31827 tile rows · 52.2s wall at W=30.

Instrument: replay + leaf calls only. **No search, no playouts, no outcome statistic is read or emitted** (rung-(1) blind discipline; the corpora's `score_p0`/`score_p1` fields are never loaded).

> **Branch hint (advisory): `M-DEAD`** — arbitrable_plies_per_game 1.410 < 4.0

Adjudicate against `PLAN_meeple_ties.md` §5 on the **POOLED** row; the per-corpus split is shown but never picks a branch.

## 1. phi — the meeple exact-tie rate

| group | games | meeple plies | censused (n_legal>=2) | phi_meeple_ply | phi_meeple_move | tied/game |
|---|---:|---:|---:|---|---|---:|
| POOLED | 1299 | 93387 | 74894 | 14.55% [14.30, 14.80] (10896/74894) | 11.65% [11.45, 11.86] (10896/93528) | 8.39 |
| champ449 | 449 | 32282 | 25848 | 14.43% [14.01, 14.86] (3730/25848) | 11.54% [11.19, 11.89] (3730/32328) | 8.31 |
| tiearb2_850 | 850 | 61105 | 49046 | 14.61% [14.30, 14.93] (7166/49046) | 11.71% [11.46, 11.97] (7166/61200) | 8.43 |

Prior to beat (PLAN §2): JCZ mining meta read meeple `leaf_tie` at **16.5%** ⇒ 4.82 tied meeple plies/game, vs the tile rung's **22.96** fired plies/game.

## 2. ⭐ THE DECISION STATISTICS

| group | fired/game (repr_arms>=2) | arbitrable/game (board_groups>=2) | **arbitrable_fraction** |
|---|---:|---:|---:|
| POOLED | 7.236 | 1.410 | 0.195 |
| champ449 | 7.218 | 1.394 | 0.193 |
| tiearb2_850 | 7.246 | 1.419 | 0.196 |

Bars: `M-DEAD` if arbitrable/game < 4.0; `M-PRICE` needs >= 8.0 **and** arbitrable_fraction >= 0.4.

## 3. Tied-set composition — raw vs the three groupings

| group | mean raw tie size | mean repr arms | mean intra-tile groups | mean BOARD regions |
|---|---:|---:|---:|---:|
| POOLED | 2.201 | 2.057 | 1.187 | 1.182 |
| champ449 | 2.193 | 2.057 | 1.191 | 1.185 |
| tiearb2_850 | 2.206 | 2.057 | 1.186 | 1.181 |

Size histograms (POOLED, exact-tied plies only):

- **raw (`tie_size_exact`)**: `{'2': 9023, '3': 1573, '4': 279, '5': 21}`
- **deduped by afterstate repr (what rust builds)**: `{'1': 1496, '2': 7596, '3': 1508, '4': 275, '5': 21}`
- **deduped by intra-tile feature key (July census)**: `{'1': 8874, '2': 2002, '3': 20}`
- **deduped by BOARD claimed-region (definition of record)**: `{'1': 8925, '2': 1955, '3': 16}`

## 4. Duplicate vs genuinely tied

| group | tied | pure DUPLICATE (1 region) | mixed | pure DISTINCT | single-arm | duplicate fraction |
|---|---:|---:|---:|---:|---:|---:|
| POOLED | 10896 | 7568 | 389 | 1443 | 1496 | 0.695 |
| champ449 | 3730 | 2615 | 130 | 496 | 489 | 0.701 |
| tiearb2_850 | 7166 | 4953 | 259 | 947 | 1007 | 0.691 |

## 5. The rust arm-dedup inefficiency, and the `J<=4` cap

| group | mean (repr − board) | mean (repr − intratile) | mean (intratile − board) | fired plies with redundancy | repr arms > 4 |
|---|---:|---:|---:|---:|---|
| POOLED | 1.029 | 1.027 | 0.003 | 0.846 | 0.22% [0.15, 0.34] (21/9400) |
| champ449 | 1.022 | 1.017 | 0.004 | 0.847 | 0.12% [0.05, 0.32] (4/3241) |
| tiearb2_850 | 1.033 | 1.032 | 0.002 | 0.846 | 0.28% [0.17, 0.44] (17/6159) |

A positive `repr − board` is the plan's §1 claim made quantitative: that many arms per fired ply are duplicates that consume `J<=4` slots and return identical world-means.

## 6. Phase cut (POOLED)

| phase | n | phi_meeple_ply | fired/game | arbitrable/game | arb. fraction |
|---|---:|---|---:|---:|---:|
| early | 29582 | 19.54% [19.09, 19.99] (5779/29582) | 4.323 | 0.819 | 0.189 |
| mid | 25121 | 10.09% [9.72, 10.47] (2534/25121) | 1.574 | 0.249 | 0.158 |
| late | 20191 | 12.79% [12.34, 13.26] (2583/20191) | 1.340 | 0.343 | 0.256 |

## 7. THE EPS PIGGYBACK — `phi(eps)` as a full CDF

Per `PLAN_eps_near_ties.md` §8: the per-ply scalar `gap = top1 − top2` (top2 = next DISTINCT leaf value) upgrades rung (4)'s 5-point grid into an arbitrary-eps CDF, for one extra field and zero extra leaf calls.

### MEEPLE

n_rows 74894 · exact-tied 10896 · untied-with-gap 63998 · smallest nonzero gap 1.1102230246251565e-16

| eps | new plies | rel growth vs fired | fired total | fired rate |
|---:|---:|---:|---:|---:|
| 0.0 | 0 | 0.0000 | 10896 | 0.1455 |
| 1e-12 | 79 | 0.0073 | 10975 | 0.1465 |
| 1e-09 | 79 | 0.0073 | 10975 | 0.1465 |
| 0.01 | 79 | 0.0073 | 10975 | 0.1465 |
| 0.05 | 378 | 0.0347 | 11274 | 0.1505 |
| 0.1 | 828 | 0.0760 | 11724 | 0.1565 |
| 0.15 | 1158 | 0.1063 | 12054 | 0.1609 |
| 0.2 | 1603 | 0.1471 | 12499 | 0.1669 |
| 0.25 | 6134 | 0.5630 | 17030 | 0.2274 |
| 0.5 | 8502 | 0.7803 | 19398 | 0.2590 |
| 0.75 | 12810 | 1.1757 | 23706 | 0.3165 |
| 1.0 | 15940 | 1.4629 | 26836 | 0.3583 |
| 1.5 | 21269 | 1.9520 | 32165 | 0.4295 |
| 2.0 | 31863 | 2.9243 | 42759 | 0.5709 |
| 3.0 | 44907 | 4.1214 | 55803 | 0.7451 |

Top gap values: `[{'gap': 4.0, 'count': 6794}, {'gap': 2.0, 'count': 5169}, {'gap': 0.25, 'count': 4144}, {'gap': 1.75, 'count': 3624}, {'gap': 3.0, 'count': 3186}, {'gap': 0.75, 'count': 3060}, {'gap': 3.75, 'count': 3013}, {'gap': 2.75, 'count': 2954}, {'gap': 5.0, 'count': 2556}, {'gap': 1.0, 'count': 2467}]`

### TILE

n_rows 31827 · exact-tied 20322 · untied-with-gap 11505 · smallest nonzero gap 2.220446049250313e-16

| eps | new plies | rel growth vs fired | fired total | fired rate |
|---:|---:|---:|---:|---:|
| 0.0 | 0 | 0.0000 | 20322 | 0.6385 |
| 1e-12 | 90 | 0.0044 | 20412 | 0.6413 |
| 1e-09 | 90 | 0.0044 | 20412 | 0.6413 |
| 0.01 | 90 | 0.0044 | 20412 | 0.6413 |
| 0.05 | 134 | 0.0066 | 20456 | 0.6427 |
| 0.1 | 330 | 0.0162 | 20652 | 0.6489 |
| 0.15 | 590 | 0.0290 | 20912 | 0.6571 |
| 0.2 | 799 | 0.0393 | 21121 | 0.6636 |
| 0.25 | 1147 | 0.0564 | 21469 | 0.6746 |
| 0.5 | 2056 | 0.1012 | 22378 | 0.7031 |
| 0.75 | 3027 | 0.1490 | 23349 | 0.7336 |
| 1.0 | 4611 | 0.2269 | 24933 | 0.7834 |
| 1.5 | 6083 | 0.2993 | 26405 | 0.8296 |
| 2.0 | 7120 | 0.3504 | 27442 | 0.8622 |
| 3.0 | 8630 | 0.4247 | 28952 | 0.9097 |

Top gap values: `[{'gap': 1.0, 'count': 1029}, {'gap': 1.5, 'count': 413}, {'gap': 2.0, 'count': 405}, {'gap': 3.0, 'count': 402}, {'gap': 0.5, 'count': 361}, {'gap': 0.25, 'count': 300}, {'gap': 0.75, 'count': 297}, {'gap': 1.25, 'count': 229}, {'gap': 4.0, 'count': 209}, {'gap': 2.5, 'count': 163}]`

## 8. What this census does NOT show

It counts. It never scores. A meeple leaf tie whose options claim DIFFERENT board regions is *arbitrable* — the arbiter could in principle separate it — but this instrument says nothing about whether a playout actually would, and deliberately reads no outcome. Pricing that (`M-PRICE`) is `PLAN_meeple_ties.md` §6, on a FRESH corpus with a FRESH read-rule. C5 (duplicate CRN bit-invariance) is not run here: it needs playouts, which this instrument is forbidden to take.
