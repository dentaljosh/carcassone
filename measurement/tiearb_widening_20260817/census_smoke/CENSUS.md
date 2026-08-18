# MEEPLE-ply leaf tie kill-census — CENSUS.md

Generated 2026-08-18T02:40:20Z · git `bfa2f591` · leaf `a36d2e15a3b3d71d` (assert OK) · 4 games · 245 meeple rows · 142 tile rows · 2.0s wall at W=4.

Instrument: replay + leaf calls only. **No search, no playouts, no outcome statistic is read or emitted** (rung-(1) blind discipline; the corpora's `score_p0`/`score_p1` fields are never loaded).

> **Branch hint (advisory): `M-DEAD`** — arbitrable_plies_per_game 1.250 < 4.0

Adjudicate against `PLAN_meeple_ties.md` §5 on the **POOLED** row; the per-corpus split is shown but never picks a branch.

## 1. phi — the meeple exact-tie rate

| group | games | meeple plies | censused (n_legal>=2) | phi_meeple_ply | phi_meeple_move | tied/game |
|---|---:|---:|---:|---|---|---:|
| POOLED | 4 | 286 | 245 | 13.88% [10.10, 18.77] (34/245) | 11.81% [8.57, 16.04] (34/288) | 8.50 |
| champ449 | 2 | 144 | 134 | 14.18% [9.27, 21.09] (19/134) | 13.19% [8.61, 19.69] (19/144) | 9.50 |
| tiearb2_850 | 2 | 142 | 111 | 13.51% [8.36, 21.10] (15/111) | 10.42% [6.41, 16.48] (15/144) | 7.50 |

Prior to beat (PLAN §2): JCZ mining meta read meeple `leaf_tie` at **16.5%** ⇒ 4.82 tied meeple plies/game, vs the tile rung's **22.96** fired plies/game.

## 2. ⭐ THE DECISION STATISTICS

| group | fired/game (repr_arms>=2) | arbitrable/game (board_groups>=2) | **arbitrable_fraction** |
|---|---:|---:|---:|
| POOLED | 7.500 | 1.250 | 0.167 |
| champ449 | 8.500 | 1.500 | 0.176 |
| tiearb2_850 | 6.500 | 1.000 | 0.154 |

Bars: `M-DEAD` if arbitrable/game < 4.0; `M-PRICE` needs >= 8.0 **and** arbitrable_fraction >= 0.4.

## 3. Tied-set composition — raw vs the three groupings

| group | mean raw tie size | mean repr arms | mean intra-tile groups | mean BOARD regions |
|---|---:|---:|---:|---:|
| POOLED | 2.206 | 2.088 | 1.147 | 1.147 |
| champ449 | 2.263 | 2.158 | 1.158 | 1.158 |
| tiearb2_850 | 2.133 | 2.000 | 1.133 | 1.133 |

Size histograms (POOLED, exact-tied plies only):

- **raw (`tie_size_exact`)**: `{'2': 27, '3': 7}`
- **deduped by afterstate repr (what rust builds)**: `{'1': 4, '2': 23, '3': 7}`
- **deduped by intra-tile feature key (July census)**: `{'1': 29, '2': 5}`
- **deduped by BOARD claimed-region (definition of record)**: `{'1': 29, '2': 5}`

## 4. Duplicate vs genuinely tied

| group | tied | pure DUPLICATE (1 region) | mixed | pure DISTINCT | single-arm | duplicate fraction |
|---|---:|---:|---:|---:|---:|---:|
| POOLED | 34 | 25 | 0 | 5 | 4 | 0.735 |
| champ449 | 19 | 14 | 0 | 3 | 2 | 0.737 |
| tiearb2_850 | 15 | 11 | 0 | 2 | 2 | 0.733 |

## 5. The rust arm-dedup inefficiency, and the `J<=4` cap

| group | mean (repr − board) | mean (repr − intratile) | mean (intratile − board) | fired plies with redundancy | repr arms > 4 |
|---|---:|---:|---:|---:|---|
| POOLED | 1.067 | 1.067 | 0.000 | 0.833 | 0.00% [0.00, 11.35] (0/30) |
| champ449 | 1.118 | 1.118 | 0.000 | 0.824 | 0.00% [0.00, 18.43] (0/17) |
| tiearb2_850 | 1.000 | 1.000 | 0.000 | 0.846 | 0.00% [0.00, 22.81] (0/13) |

A positive `repr − board` is the plan's §1 claim made quantitative: that many arms per fired ply are duplicates that consume `J<=4` slots and return identical world-means.

## 6. Phase cut (POOLED)

| phase | n | phi_meeple_ply | fired/game | arbitrable/game | arb. fraction |
|---|---:|---|---:|---:|---:|
| early | 90 | 20.00% [13.04, 29.41] (18/90) | 4.500 | 1.250 | 0.278 |
| mid | 80 | 11.25% [6.03, 20.02] (9/80) | 1.750 | 0.000 | 0.000 |
| late | 75 | 9.33% [4.59, 18.03] (7/75) | 1.250 | 0.000 | 0.000 |

## 7. THE EPS PIGGYBACK — `phi(eps)` as a full CDF

Per `PLAN_eps_near_ties.md` §8: the per-ply scalar `gap = top1 − top2` (top2 = next DISTINCT leaf value) upgrades rung (4)'s 5-point grid into an arbitrary-eps CDF, for one extra field and zero extra leaf calls.

### MEEPLE

n_rows 245 · exact-tied 34 · untied-with-gap 211 · smallest nonzero gap 0.04999999999999982

| eps | new plies | rel growth vs fired | fired total | fired rate |
|---:|---:|---:|---:|---:|
| 0.0 | 0 | 0.0000 | 34 | 0.1388 |
| 1e-12 | 0 | 0.0000 | 34 | 0.1388 |
| 1e-09 | 0 | 0.0000 | 34 | 0.1388 |
| 0.01 | 0 | 0.0000 | 34 | 0.1388 |
| 0.05 | 1 | 0.0294 | 35 | 0.1429 |
| 0.1 | 1 | 0.0294 | 35 | 0.1429 |
| 0.15 | 1 | 0.0294 | 35 | 0.1429 |
| 0.2 | 3 | 0.0882 | 37 | 0.1510 |
| 0.25 | 21 | 0.6176 | 55 | 0.2245 |
| 0.5 | 29 | 0.8529 | 63 | 0.2571 |
| 0.75 | 45 | 1.3235 | 79 | 0.3224 |
| 1.0 | 53 | 1.5588 | 87 | 0.3551 |
| 1.5 | 80 | 2.3529 | 114 | 0.4653 |
| 2.0 | 113 | 3.3235 | 147 | 0.6000 |
| 3.0 | 146 | 4.2941 | 180 | 0.7347 |

Top gap values: `[{'gap': 4.0, 'count': 20}, {'gap': 0.25, 'count': 18}, {'gap': 2.0, 'count': 17}, {'gap': 3.75, 'count': 16}, {'gap': 0.75, 'count': 15}, {'gap': 5.0, 'count': 13}, {'gap': 1.25, 'count': 12}, {'gap': 1.75, 'count': 10}, {'gap': 2.25, 'count': 9}, {'gap': 1.0, 'count': 7}]`

### TILE

n_rows 142 · exact-tied 91 · untied-with-gap 51 · smallest nonzero gap 0.10000000000000142

| eps | new plies | rel growth vs fired | fired total | fired rate |
|---:|---:|---:|---:|---:|
| 0.0 | 0 | 0.0000 | 91 | 0.6408 |
| 1e-12 | 0 | 0.0000 | 91 | 0.6408 |
| 1e-09 | 0 | 0.0000 | 91 | 0.6408 |
| 0.01 | 0 | 0.0000 | 91 | 0.6408 |
| 0.05 | 0 | 0.0000 | 91 | 0.6408 |
| 0.1 | 0 | 0.0000 | 91 | 0.6408 |
| 0.15 | 1 | 0.0110 | 92 | 0.6479 |
| 0.2 | 1 | 0.0110 | 92 | 0.6479 |
| 0.25 | 2 | 0.0220 | 93 | 0.6549 |
| 0.5 | 5 | 0.0549 | 96 | 0.6761 |
| 0.75 | 7 | 0.0769 | 98 | 0.6901 |
| 1.0 | 17 | 0.1868 | 108 | 0.7606 |
| 1.5 | 26 | 0.2857 | 117 | 0.8239 |
| 2.0 | 28 | 0.3077 | 119 | 0.8380 |
| 3.0 | 33 | 0.3626 | 124 | 0.8732 |

Top gap values: `[{'gap': 1.0, 'count': 6}, {'gap': 3.75, 'count': 4}, {'gap': 1.5, 'count': 3}, {'gap': 0.8999999999999995, 'count': 2}, {'gap': 0.4499999999999993, 'count': 2}, {'gap': 2.25, 'count': 1}, {'gap': 6.75, 'count': 1}, {'gap': 6.5, 'count': 1}, {'gap': 5.0, 'count': 1}, {'gap': 0.25, 'count': 1}]`

## 8. What this census does NOT show

It counts. It never scores. A meeple leaf tie whose options claim DIFFERENT board regions is *arbitrable* — the arbiter could in principle separate it — but this instrument says nothing about whether a playout actually would, and deliberately reads no outcome. Pricing that (`M-PRICE`) is `PLAN_meeple_ties.md` §6, on a FRESH corpus with a FRESH read-rule. C5 (duplicate CRN bit-invariance) is not run here: it needs playouts, which this instrument is forbidden to take.
