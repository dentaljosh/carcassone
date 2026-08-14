# OPEN-CITY ROUND 2 CALIBRATION — READOUT (mechanical, rule-first)

> **STATUS: RAN AND READ 2026-08-14.** 0 games played, no deck band consumed, no elo
> statistic computed, no `results.csv` row owed. `governance/PRODUCTION.yaml` untouched.
> The selection rule was committed in [CALIB_READ_RULE.md](CALIB_READ_RULE.md)
> (`9a2abcd5`) **before any arm's flip rate was read**; this file was emitted by
> [make_calib_readout_round2.py](make_calib_readout_round2.py), a pure function from the
> two rollups to the branches.
>
> **Fundable cells: `C_d16p0`, `Acap3_d2p0`, `Asym_d2p0`.**

## 1. What ran

Two runs of [`opencity_e4_replay.py`](../../scripts/classical_search/opencity_e4_replay.py)
over the banked E4 archives (26 archives, 1556 champion
plies per arm, symmetric run; 26 / 1556 asymmetric run),
CRN per ply, rules epoch resolved per archive {"walled": 2, "app_aug2": 1, "fixed_v1": 23}, all replay checksums clean in both runs.

## 2. The ladders

| family | cell | size_min | edge_min | dose | cap | sym | flip rate | Wilson-95 |
|---|---|---|---|---|---|---|---|---|
| C | `C_d4p0` | 6 | 3 | 4 | 0 | T | **7.78%** (121/1556) | 6.55%–9.21% |
| C | `C_d8p0` | 6 | 3 | 8 | 0 | T | **9.25%** (144/1556) | 7.91%–10.80% |
| C | `C_d16p0` | 6 | 3 | 16 | 0 | T | **10.41%** (162/1556) | 8.99%–12.03% |
| ACAP | `Acap1_d0p5` | 4 | 2 | 0.5 | 1 | T | **4.11%** (64/1556) | 3.23%–5.22% |
| ACAP | `Acap1_d2p0` | 4 | 2 | 2 | 1 | T | **9.06%** (141/1556) | 7.73%–10.59% |
| ACAP | `Acap3_d2p0` | 4 | 2 | 2 | 3 | T | **14.20%** (221/1556) | 12.56%–16.03% |
| ASYM | `Asym_d0p5` | 4 | 2 | 0.5 | 0 | F | **8.93%** (139/1556) | 7.62%–10.45% |
| ASYM | `Asym_d2p0` | 4 | 2 | 2 | 0 | F | **16.71%** (260/1556) | 14.94%–18.64% |

## 3. Verdict against the committed rule (per family, then the global cut)

- **C**: branch **`FUND-SMALLEST`** → **`C_d16p0`**.
- **ACAP**: branch **`FUND-SMALLEST`** → **`Acap3_d2p0`**.
- **ASYM**: branch **`FUND-SMALLEST`** → **`Asym_d2p0`**.

- **Prediction (a)** (family C crosses 10% between doses 8 and 16): HELD — observed {'C_d4p0': '7.78%', 'C_d8p0': '9.25%', 'C_d16p0': '10.41%'}.
- **Prediction (b)** (capped <= uncapped counterparts): held.

### ⚠️ ON-THE-BAR selections (recorded AT CALIBRATION TIME, the A_d0p5 precedent)

- `C_d16p0` reads **10.41%** against a bar of 10.00% and its Wilson-95 (8.99%–12.03%) **straddles the bar**. On the CI lower bound the selection would be **no cell in this family**. if this cell lands null, 'the term does not express' is NOT an available reading — it was funded at the edge of the floor (the A_d0p5 precedent).

## 4. Secondary observations (descriptive; NOT inputs to the funding decision)

- `C_d4p0`: 121 flips — 93 tile-phase, 28 meeple-phase
- `C_d8p0`: 144 flips — 109 tile-phase, 35 meeple-phase
- `C_d16p0`: 162 flips — 116 tile-phase, 46 meeple-phase
- `Acap1_d0p5`: 64 flips — 51 tile-phase, 13 meeple-phase
- `Acap1_d2p0`: 141 flips — 96 tile-phase, 45 meeple-phase
- `Acap3_d2p0`: 221 flips — 159 tile-phase, 62 meeple-phase
- `Asym_d0p5`: 139 flips — 110 tile-phase, 29 meeple-phase
- `Asym_d2p0`: 260 flips — 197 tile-phase, 63 meeple-phase

## 5. What this does NOT say

1. **Flip rate is not strength.** Round 1 proved it in the sharpest way: expressiveness
   predicted the magnitude, not the sign, and both funded cells lost (CL-080). Nothing
   here predicts the sign of anything.
2. **Mixed rules epochs and budgets** across archives make this a pooled expressiveness
   measure, not a per-epoch estimate.
3. **Nothing licenses a strength claim**; `governance/PRODUCTION.yaml` untouched on every
   branch. Per CL-079, the verdict instrument is a deploy-budget cell on its own band.
4. **No cross-family or cross-round pooling** — three families, three falsifiers, read
   independently; CL-080's cells are a different candidate set on a retired band.

## 6. Cell identity (provenance)

| cell | dose | size_min | edge_min | cap | symmetric | `cand_leaf_hash` |
|---|---|---|---|---|---|---|
| `C_d4p0` | 4 | 6 | 3 | 0 | True | `cce11e4d05f0d86e` |
| `C_d8p0` | 8 | 6 | 3 | 0 | True | `d52332443bc35fcf` |
| `C_d16p0` | 16 | 6 | 3 | 0 | True | `a4acf6d0925f7606` |
| `Acap1_d0p5` | 0.5 | 4 | 2 | 1 | True | `d3ac9cc459f6d8d7` |
| `Acap1_d2p0` | 2 | 4 | 2 | 1 | True | `a292f2cb05e45a22` |
| `Acap3_d2p0` | 2 | 4 | 2 | 3 | True | `687f99980adaeee7` |
| `Asym_d0p5` | 0.5 | 4 | 2 | 0 | False | `6cfd4e4575aba1bc` |
| `Asym_d2p0` | 2 | 4 | 2 | 0 | False | `3f05d72016d0d09c` |

All 8 distinct: True. None equals the champion `a36d2e15a3b3d71d`: True. Ladders are the pre-registered ones: asserted at collect() (the reader refuses any other grid).
