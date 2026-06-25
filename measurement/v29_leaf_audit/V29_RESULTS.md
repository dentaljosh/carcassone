# V29_RESULTS — candidate eval table

**Status: PENDING — no eval compute spent yet.** Scaffold + harness built and tested
(2026-06-25). This table fills in as the Wave-1 screen lands. Numbers come from
`scripts/v29/eval_v29_vs_v28.py --summary-only`; each cell's full config + git commit
is in its `manifest.json`.

## Wave 1 — screen @ sims=200, n=200 paired (vs v2.8 baseline)

| candidate | n | wr | elo | avg margin | paired z | even-bucket wr | blowout-bucket wr | verdict |
|---|---|---|---|---|---|---|---|---|
| v28 (null control) | — | | | | | | | _expect ≈0.500_ |
| A8  | — | | | | | | | |
| A12 | — | | | | | | | |
| A16 | — | | | | | | | |
| A24 | — | | | | | | | |
| A32 | — | | | | | | | |
| A48 | — | | | | | | | |
| Bmild | — | | | | | | | |
| Baggr | — | | | | | | | |
| Bk1 | — | | | | | | | |
| Bk3 | — | | | | | | | |

## Wave 1 — verdict @ sims=200, n=400  (survivors only)

_(to be filled)_

## Wave 1 — washout check @ sims=800, n=400  (finalists only)

_(to be filled)_

## Final — h6400 / h3200, n=400  (single best config)

_(to be filled)_

---

### Interpretation notes
- Pre-endgame split uses a snapshot at deck ≤ 6 tiles (pre-outcome) — a margin gain
  that lives in the **blowout-ahead** bucket is already-won padding (suspicious), not
  strength; a gain in **even/behind** is the signal we want.
- Per the n-threshold rule: n=200 is a coarse screen (±~35 elo); promote nothing on it.
