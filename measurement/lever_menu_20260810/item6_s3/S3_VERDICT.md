# ITEM 6 — JCZ S3 cut (merge-exposure) — readout

Generated 2026-08-10T18:11:15Z. Prereg: `measurement/jcz_mining_20260809/MINING_PREREG.md`. Plan: `docs/LEVER_MENU_PLAN_20260810.md#4.6`.

Oracle-replay instrument. Plays **zero games**. Claims **no band**. Does not touch
`governance/PRODUCTION.yaml`.

## Sign convention
`delta = mean(V(pick_b) - V(pick_a))`; `pick_a` = our leaf-argmax pick, `pick_b` =
JCZ's played pick. `delta > 0` means JCZ's pick was better than ours.

## Per-stratum statistics (cluster-robust z on `root_id`, CR1)

| stratum | n (ok) | n (failed) | mean delta_Q (pts/ply) | se_cluster_root | z | 95% CI | sizing |
|---|---:|---:|---:|---:|---:|---|---|
| S3 (merge_exposure_differs) | 50 | 0 | -0.5194 | 0.4435 | -1.171 | [-1.389, 0.350] | n=50 clears the n>=25 gate but sits BELOW the n=74 re-open bar (80% power at +1.4 pts/ply). Read as a coarse screen, not a powered verdict, per the pre-registered power table. |
| matched control | 50 | 0 | -0.9419 | 0.3140 | -3.000 | [-1.557, -0.326] | n=50 clears the n>=25 gate but sits BELOW the n=74 re-open bar (80% power at +1.4 pts/ply). Read as a coarse screen, not a powered verdict, per the pre-registered power table. |

Ply-class breakdown — S3: {'TILE': {'n': 50, 'mean_delta_pts': -0.519375}, 'MEEPLE': {'n': 0, 'mean_delta_pts': nan}, 'class_dominated': True}; control: {'TILE': {'n': 50, 'mean_delta_pts': -0.941875}, 'MEEPLE': {'n': 0, 'mean_delta_pts': nan}, 'class_dominated': True}.

## Branch fired

**NO CONVICTION** — |z_S3| < 2.0 -> the JCZ steal file CLOSES on S3 and the native-term build stays unfunded.

## Riders (restated, do not drop from any downstream citation)
- Exploratory by construction — no strength claim, no band claimed; band 1.08e11
  stays retired from confirmatory use and this reuse does not un-retire it.
- The oracle prices with a reference that is NOT the leaf under suspicion (clairvoyant
  PUCT continuation on the production curve125 leaf) — that is the point; the leaf
  under suspicion was never substituted in.
- Sizing honesty: PREREG §4's gate is n>=25 scored per stratum or the stratum is
  INCONCLUSIVE BY CONSTRUCTION; the re-open bar for 80% power at +1.4 pts/ply is
  n=74. n=50 sits BETWEEN the gate and the powered bar.
