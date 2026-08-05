# F12 slice 2a — per-move EV-loss readout (2 E4 games)

**Status: RAN 2026-08-05. Acceptance gate PASS on both games.** Built to
[EVLOSS_SPEC.md](EVLOSS_SPEC.md) (pre-registered; D1 units / D2 measured buckets / D3 exact
tail separate / D4 confounds). Tool: `scripts/analyzer/ev_loss.py`; tests
`tests/test_analyzer_evloss.py`. This is **analysis tooling — it makes no strength claim and
touches no production config.**

Artifacts (the source of truth; every number below cites a field of one of them):

| game | archive | JSON | markdown |
|---|---|---|---|
| g1 | `measurement/e4_games/1785205383_867966.json` | [EV_LOSS_g1_867966.json](EV_LOSS_g1_867966.json) | [EV_LOSS_g1_867966.md](EV_LOSS_g1_867966.md) |
| g2 | `measurement/e4_games/1785466497_161583.json` | [EV_LOSS_g2_161583.json](EV_LOSS_g2_161583.json) | [EV_LOSS_g2_161583.md](EV_LOSS_g2_161583.md) |

Grading config, both games (`budget`, `integrity`): rules profile **`walled`** resolved from
the archive's `start_rule`/`grid_rule` (both null ⇒ pre-2026-08-01 engine-of-record epoch),
budget **k4×688 = 2752/move** = `budget.source: "archive sims_effective/k_dets_effective"`,
grading seed 12345, calibration seed 777, Rust backend, leaf
`integrity.leaf_hash_runtime = a36d2e15a3b3d71d` (`leaf_hash_ok: true`),
`integrity.replay_scores_match: true`, `integrity.mirror_desync_events: 0`,
`integrity.n_unrated_pimc: 0` on both.

---

## 1. The acceptance gate (ran BEFORE any human number)

Spec "What would make this wrong": if the champion seat's own mean EV loss is not near the
calibration null, the grader is mis-wired and no human number is reportable.
Criterion shipped: `acceptance_gate.champion_mean_delta_q <= acceptance_gate.null_p95`.

| game | champion mean ΔQ | (sem) | null p95 | `acceptance_gate.pass` |
|---|---:|---:|---:|:--|
| g1 | 0.00827 | 0.00291 | 0.04718 | **true** |
| g2 | 0.01315 | 0.00475 | 0.12452 | **true** |

Both pass with room: the champion seat's residual loss is ~1/6 (g1) and ~1/9 (g2) of the
instrument's own p95 noise, and `≈0.8×` / `≈0.7×` its *mean* (`buckets.null.dist.mean` =
0.01042 / 0.01854). That is what "the grader agrees with the agent that generated the moves"
looks like, and it is the independent evidence that the `walled` profile was the right choice
— together with `integrity.replay_scores_match: true`, i.e. the desktop replay under that
profile reproduces the phone's recorded scores exactly ([111, 113] and [73, 108],
`integrity.final_scores_replayed` == `integrity.recorded_scores`).

## 2. Read this first (D4 — the confounds, not corrected for)

Full list in each artifact's `confounds` block. The four that bound every number below:

1. **Same-family self-preference.** The grading agent *is* the agent that played the game —
   same leaf, same search, same budget. It structurally prefers its own moves. **The human's
   absolute EV loss is not reportable; only the paired human-vs-champion contrast on the same
   board is.**
2. **n = 2 games.** This describes two games of Joshua's play. It is not an estimate of a
   player.
3. **ΔQ is dimensionless (D1).** Q = W/N is a mean of `tanh(virtual_score/15)`, not points.
   `delta_points_tanh_est` is a monotone readability rescaling — never quote it as "you lost N
   points". (This retracts the "Q is natively in expected-margin points" sentence in
   `BACKLOG.md:591` / `ANALYZER_REPORT.md`.)
4. **Buckets are epoch-local.** Thresholds are the measured null of *this* corpus at *this*
   budget with *these* two seeds. A fixed_v1 / k8×1376 archive needs its own calibration
   before its bucket labels mean anything.

Two more, both in the artifacts: eligibility censoring would bias both seats' means *downward*
(it did not fire here — `integrity.n_unrated_pimc: 0` on both games), and exact-tail points are
a different instrument from ΔQ and are never pooled with it.

## 3. THE HEADLINE — paired EV loss, same board, same deck, same budget

`summary.<seat>.mean_delta_q`, over rated non-forced non-exact plies:

| game | seat | rated plies | agree rate | **mean ΔQ** | sd | p95 | max | mean pts (tanh est) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| g1 | human (0) | 61 | 0.5082 | **0.02507** | 0.05139 | 0.0995 | 0.2798 | 1.195 |
| g1 | champion (1) | 66 | 0.7273 | **0.00827** | 0.02367 | 0.0690 | 0.1083 | 0.277 |
| g2 | human (0) | 60 | 0.4500 | **0.03927** | 0.07269 | 0.1869 | 0.2747 | 0.926 |
| g2 | champion (1) | 63 | 0.7302 | **0.01315** | 0.03770 | 0.1312 | 0.1557 | 0.249 |

**The human seat loses ~3× the champion seat's EV per move, in both games independently:
3.03× (g1) and 2.99× (g2).** The median human ply is still a zero-loss ply
(`summary.human.delta_q_dist.p50` = 0.0 in g1, 0.00021 in g2) — the gap is carried by a tail,
not by uniformly worse play. The human's agree rate (the search's own best action) is 0.51 /
0.45 against the champion's 0.73 / 0.73.

Do NOT read the ~3× as "three times worse a player". It is three times the per-move
disagreement-cost *as priced by the champion's own 2752-sim search*, with confound 1 pushing
the champion seat's figure down by construction.

## 4. Bucket census (thresholds MEASURED, D2)

Thresholds are the quantiles of the calibration null = `|ΔQ(seed 12345) − ΔQ(seed 777)|` on
the same played action (`buckets.null`):

| game | null n | null mean | **p95 → `inaccuracy` cut** | **p99 → `blunder` cut** | best-action agreement between passes |
|---|---:|---:|---:|---:|---:|
| g1 | 127 | 0.01042 | **0.04718** | **0.13979** | 0.8268 |
| g2 | 123 | 0.01854 | **0.12452** | **0.16807** | 0.7236 |

g2's instrument is ~2.6× noisier at p95 than g1's, so its bar for "blunder" is much higher —
which is exactly why the thresholds are measured per artifact and are not portable.

`summary.<seat>.buckets` / `.bucket_frac`:

| game | seat | agree | within_noise | inaccuracy | **blunder** |
|---|---|---:|---:|---:|---:|
| g1 | human | 31 (0.508) | 18 (0.295) | 10 (0.164) | **2 (0.033)** |
| g1 | champion | 48 (0.727) | 13 (0.197) | 5 (0.076) | **0 (0.000)** |
| g2 | human | 27 (0.450) | 22 (0.367) | 6 (0.100) | **5 (0.083)** |
| g2 | champion | 46 (0.730) | 13 (0.206) | 4 (0.063) | **0 (0.000)** |

**The champion seat produced zero blunders in either game; the human produced 2 and 5.** Seven
blunder-class moves across 121 rated human plies = 5.8%. Given confound 1, treat the *count
asymmetry* (7 vs 0) as the finding and the *rate* as an upper-bounded description of two games.

## 5. Exact tail (k_remaining ≤ 2 — TRUE final-score points, D3)

Graded with `endgame_solver.solve(mode="marginalized")` → `regret_of()`. Forced plies (one
legal action) are excluded from this block as from every other. `exact_tail.<seat>`:

| game | seat | plies | played optimally | mean regret (pts) | max | total |
|---|---|---:|---:|---:|---:|---:|
| g1 | human | 2 | 1 | 0.50 | 1.0 | 1.0 |
| g1 | champion | 2 | 2 | 0.00 | 0.0 | 0.0 |
| g2 | human | 1 | 1 | 0.00 | 0.0 | 0.0 |
| g2 | champion | 1 | 1 | 0.00 | 0.0 | 0.0 |

The entire measured endgame cost across both games is **1.0 point**, at g1 ply 140
(`exact_tail.human.plies[0]`: k_remaining 1, 28 legal, played 1663, six optimal actions
1565/1566/1567/1629/1630/1631, 10,291 solver nodes). g1 finished 111–113 — that single point
is not the game, but it is half the margin. **Never add these to the ΔQ table**: different
instrument, different scale.

## 6. Top-3 worst moves per game per seat (`top_losses`)

| game | seat | ply | k left | phase | n legal | played | best | ΔQ | pts (tanh est) | bucket |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| g1 | human | 100 | 21 | tiles | 39 | 1031 | 839 | 0.2798 | 14.18 | blunder |
| g1 | human | 124 | 9 | tiles | 32 | 958 | 1467 | 0.2209 | 3.33 | blunder |
| g1 | human | 5 | 69 | meeples | 5 | 2510 | 2501 | 0.1066 | 1.60 | inaccuracy |
| g1 | champion | 11 | 66 | meeples | 7 | 2507 | 2502 | 0.1083 | 1.79 | inaccuracy |
| g1 | champion | 139 | 2 | meeples | 3 | 2504 | 2510 | 0.0997 | 1.50 | inaccuracy |
| g1 | champion | 130 | 6 | tiles | 50 | 926 | 1633 | 0.0895 | 1.35 | inaccuracy |
| g2 | human | 48 | 47 | tiles | 19 | 1462 | 1051 | 0.2747 | 4.40 | blunder |
| g2 | human | 53 | 45 | meeples | 2 | 2510 | 2505 | 0.2734 | 4.18 | blunder |
| g2 | human | 44 | 49 | tiles | 28 | 1458 | 1051 | 0.2287 | 3.75 | blunder |
| g2 | champion | 39 | 52 | meeples | 5 | 2509 | 2510 | 0.1557 | 2.44 | inaccuracy |
| g2 | champion | 50 | 46 | tiles | 24 | 941 | 1156 | 0.1494 | 2.26 | inaccuracy |
| g2 | champion | 6 | 68 | tiles | 12 | 1148 | 1345 | 0.1427 | 2.16 | inaccuracy |

(Table rendered from `top_losses.<seat>` of each artifact — read the JSON, not this table, if
the two ever disagree.) Two shapes stand out and are **leads, not
findings** at n=2: g1 ply 100 is the single largest disagreement in either game
(ΔQ 0.2798, `delta_points_tanh_est` 14.18 — that estimate is deep in the atanh blow-up region
and is the clearest case in this document of why D1 forbids quoting it as points), and g2's
three worst human moves are all in the 44–53 ply window (k 49→45), i.e. one bad mid-game
stretch rather than a spread.

## 7. What this does and does not settle

- It **converts CL-070's "the move changed" into "the move cost N ΔQ"** — the named successor
  the claim asked for.
- It gives a **calibrated, paired instrument**: the champion seat is graded on the same board
  every time, and the acceptance gate is a live wiring check, not a promise.
- It **does not** make a strength claim, does not price the human in points, and does not
  generalise past two games at k4×688 on the walled epoch.
- Next natural steps, unfunded here: a post-2026-08-01 `fixed_v1` archive (needs its own
  calibration), and grading the same games at k8×1376 to read "a stronger reader's opinion"
  against this one (`budget.source` would flip to `"CLI override"`).
