# Stage E — Non-transitivity / Selection Audit (RoD2, v2.9 leaf)

**Question:** Did parent/adjacent wins transfer to a fixed ruler? Is selection-on-adjacent-wins a valid improvement signal?
**Source:** existing eval tallies under `evals/logs/*_tally.log` + `V29_SCREEN_SUMMARY.md`. v2.9 leaf on **both** sides of every match. FREE.

## Fixed-ruler odometer — vs h6400_v2.9 (DEEP ruler = the real target)

| agent | n | WR | elo | paired margin (pts/game) | paired z |
|---|--:|--:|--:|--:|--:|
| RoD1_v29 | 195 | .454 | −32.2 | −4.23 | −2.75 |
| iter02 | 200 | .458 | −29.6 | −4.70 | −3.19 |
| iter04 | 400 | .463 | −26.1 | −5.09 | −4.67 |
| iter06 | 200 | .468 | −22.6 | −2.77 | −1.83 |

**All four LOSE to h6400** (every paired z negative). The chain drifts −32→−23 elo / WR .454→.468 — a faint upward wobble, but every step is inside ±25 elo (n=200) noise and the margins do **not** corroborate (RoD1 −4.23, iter04 −5.09, iter06 −2.77). `iter04 − RoD1 = +6 elo = 0.2σ` → a **tie**.

## Fixed-ruler odometer — vs h3200_v2.9 (SHALLOW ruler)

| agent | n | WR | elo | paired margin | paired z |
|---|--:|--:|--:|--:|--:|
| RoD1_v29 | 200 | .550 | **+34.9** | −0.17 | −0.13 |
| iter02 | 78 | *(incomplete — discard)* | — | — | — |
| iter04 | 200 | .492 | **−5.2** | −2.50 | −1.57 |
| iter06 | — | *(not run)* | — | — | — |

`iter04 − RoD1 = −40 elo = −1.15σ` → not significant, but the chain did **not** improve vs h3200 and hints at **regression**.

## Inter-checkpoint (net-vs-net) cells — UNRELIABLE

`iter04 vs RoD1` and `iter06 vs iter04` ran on the dual-carc-orch-on-one-GPU harness, which **deadlocked / churned** (log: servers ready, parity OK, "200 to play", then `resource_tracker: 12 leaked semaphore objects` at shutdown — incomplete). No trustworthy adjacent deltas. The fixed-ruler odometer is the only valid measure.

## Findings

1. **No significant climb vs the deep ruler.** Every checkpoint loses −22 to −32 elo to h6400; the WR uptick is within noise and uncorroborated by margin.
2. **No climb (hint of regression) vs the shallow ruler.** RoD1 +34.9 → iter04 −5.2.
3. **Ruler-dependent sign flip = non-transitivity.** `(iter04 − RoD1)` is **+6 elo vs h6400** but **−40 elo vs h3200**. Neither is individually significant, but the *flip* means any apparent gain is ruler-dependent (RPS), not a consistent strength gain. Identical to the v2.8 autopsy (+33 adjacent elo → 0 transfer to the ruler).
4. **Whole chain pinned in the h3200–h6400 band.** RoD1 already beats h3200 / loses h6400; iter02–06 sit at ~h3200 parity / lose h6400. The v2.9 leaf swap did **not** move the band off where RoD1 (and the v2.8 chain at iter08) already sat.

## Verdict

Parent/adjacent selection wins did **not** transfer to any fixed ruler — and the inter-checkpoint harness that would have produced those adjacent deltas was itself unreliable. Differences between checkpoints are **non-transitive style shifts inside a fixed strength band**, not strength gains. **Selection-on-adjacent-wins is invalid here** (same conclusion as v2.8).
