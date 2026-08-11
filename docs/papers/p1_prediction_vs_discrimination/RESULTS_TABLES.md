# P1 RESULTS TABLES — drafted with real numbers, every cell traceable

> **Status: DRAFT (2026-08-02).** Every number below is copied verbatim from the named
> source file (file + row/section cited under each table). Where the paper wants a
> number that does not exist on disk, the cell says **TODO-MEASURE** — never an
> estimate. Sources of truth: [measurement/value_unlock_20260730/READOUT.md](../../../measurement/value_unlock_20260730/READOUT.md),
> [measurement/value_unlock_20260730/VERDICT.json](../../../measurement/value_unlock_20260730/VERDICT.json),
> [governance/CLAIM_REGISTRY.csv](../../../governance/CLAIM_REGISTRY.csv),
> [experiments/results.csv](../../../experiments/results.csv).

Conventions: solver regret in RAW POINTS (mover-POV, ≥0, lower better); tau = Kendall
tau-b vs exact solver child values; elo σ are 1σ; "paired" = deck-paired (same deck
both seats).

---

## T1 — HEADLINE: four rankers on the same 1,119 exact-solver roots (the paper's main table)

| ranker | what it is | regret_mean ↓ | regret_median | top1 ↑ | tau ↑ | frac regret=0 |
|---|---|---|---|---|---|---|
| `curve125` | champion's hand-crafted leaf | **0.9508** | 0.0 | **0.6095** | **0.6153** | 0.6988 |
| `v29_leaf` | same leaf, curve100 (harness baseline) | 0.9508 | 0.0 | 0.6095 | 0.6153 | 0.6988 |
| `iter_03` | CL-067 value head (warm parent, control) | 2.0000 | 1.0 | 0.0688 | 0.0177 | 0.3342 |
| **`value_unlock_v1`** | value head refined on strongest corpus | **1.9946** | 1.0 | **0.0670** | **0.0190** | 0.3360 |

Ratios (leaf : refined head): regret **2.10×**, top-1 **9.1×**, tau **32.4×**.
Bootstrap-over-roots (B=10,000): tau 0.0190 ± 0.00533 (candidate) vs 0.6153 ± 0.01201 (leaf).

- Source: READOUT.md §4.1 table + VERDICT.json `aggregate` block (all four arms) and
  `tau_boot_vs_curve125` blocks; results.csv row `value_unlock_solver_score_k2_n1119`
  (avg_diff col = 1.9946, the pre-registered primary statistic).
- Footnote for the paper (instrument resolution): curve125 and v29_leaf pick the same
  child on **1119/1119** roots (0 better / 0 worse / 1119 tie, mean Δregret exactly
  0.0) — this K=2 root set cannot separate leaf-family variants; does not contradict
  the online curve125 win (CL-051). Source: READOUT.md §4.3(b), VERDICT.json
  `v29_leaf.paired_vs_curve125`.
- Instrument-integrity footnote: the leaf arm reproduces 0.9508 / 0.6095 / 0.6153 to 4
  decimals against the 2026-07-03 M2 artifact and the CL-065 self-check. Sources:
  READOUT.md §4 provenance self-check; results.csv `gatec_c0_learnability_probe`.

## T2 — The pre-registered adjudication (goes beside T1 or in its caption)

| statistic | value |
|---|---|
| pre-registered bar (commit `9660f67`, before the ruler ran) | YES iff regret < curve125's AND paired sign-z ≥ +2.0 |
| candidate regret vs baseline | 1.9946 vs 0.9508 (2.10× worse) |
| paired per-root outcome | 91 better / 523 worse / 505 tie |
| paired sign-z | **−17.43** (NO branch ≤ −2.0, cleared 8-fold) |
| mean Δregret (candidate − baseline) | +1.0438 points lost per root |
| paired Δτ | −0.598, dτ-z −44.6 |
| verdict | **NO** |

- Source: READOUT.md §4.2 verbatim block + §3.4 (the bar); VERDICT.json
  `value_unlock_v1.paired_vs_curve125`.

## T3 — The dissociation control: the refine moved prediction, not discrimination

| axis | iter_03 (parent) | value_unlock_v1 (refined) | movement |
|---|---|---|---|
| held-out value↔outcome Pearson r | 0.6564 | **0.6795** | **+0.0231 (improved; beats the ≈0.61 heuristic reference)** |
| train value MSE (ep1→ep4) | — | 0.1000 → 0.0455 | improved 2.2× |
| held-out value MSE (ep1→ep4) | — | 0.2862 → 0.2768 (best 0.2708 at ep2) | flat-to-worse (memorization signature) |
| solver regret_mean | 2.0000 | 1.9946 | Δ −0.0054 |
| paired vs parent (same 1,119 roots) | — | 161 better / 144 worse / 814 tie | **sign-z +0.97 (inert)** |
| paired Δτ vs parent | — | +0.0013 | dτ-z +0.25 (inert) |
| agreement on picked child, parent vs refined | — | **310/1119 = 27.7%** | different move at 72.3% of roots, identical (bad) scores |

- Sources: READOUT.md §2 (r values, loss curve verbatim), §4.3(a) (paired-vs-parent
  numbers, 27.7%); heuristic reference ≈0.61 per READOUT §2 (citing
  `train_iter.py:706`); results.csv `value_unlock_solver_score_k2_n1119` (CONTROL
  sentence).
- Caveat that must travel with r=0.6795 (READOUT §2/§4.4): within-window,
  position-level; the off-distribution precedent is 0.891 in-window → 0.437 on foreign
  strong games ([measurement/az_zero_20260724/PROBE_OFFDIST_20260724.md](../../../measurement/az_zero_20260724/PROBE_OFFDIST_20260724.md)).

## T4 — Capacity ladder (CL-064): 25× params, tau never moves toward the leaf

| net | params (arch) | solver tau (seed 0 / seed 1 mean, per registry) |
|---|---|---|
| f64b4 | 386K → | 0.1331 |
| f128b6 | (~4× steps) | 0.0953 |
| f256b8 | ~10M | 0.0829 |
| leaf reference | — | 0.6153 |
| best single checkpoint of six | — | 0.1686 |
| pre-registered DEAD gate | best < 0.25 AND slope < +0.05/4× | slope = **−0.0251** → DEAD |

Per-size seed spreads 0.0710 / 0.1028 / 0.0494 exceed the step deltas (−0.0378,
−0.0124): the *decline* is not read as real; the verdict rests on the level.

- Sources: CLAIM_REGISTRY.csv CL-064 (claim + counterevidence fields);
  `measurement/capacity_probe/solver_score_capacity_full6.json` (canonical artifact);
  [measurement/capacity_probe/CAPACITY_PROBE.md](../../../measurement/capacity_probe/CAPACITY_PROBE.md).
- TODO for figure prep: per-seed tau values (6 cells) — read them off
  `solver_score_capacity_full6.json`, not the registry (registry carries means).

## T5 — Representation-independence probe (CL-065): the leaf's own features + exact labels

| learner | input | held-out tau |
|---|---|---|
| leaf floor (OLS self-check) | the leaf value itself | 0.6153 |
| free re-weight of the leaf's own 4 terms | 4 leaf terms | 0.6157 (tie) |
| ridge | 84 component features | 0.3466 |
| GBDT | 84 component features | **0.3856** |
| pre-registered DEAD gate | max full-feature tau < 0.62 | satisfied by ~0.23 |

- Sources: CLAIM_REGISTRY.csv CL-065; results.csv `gatec_c0_learnability_probe`
  (method detail: 84 mover-POV features = leaf's own terms + per-component pooled raw
  attributes, 5-fold cross-fit grouped by deck seed, same 1,119 roots);
  [measurement/gatec_c0_20260723/results.json](../../../measurement/gatec_c0_20260723/results.json).

## T6 — The M2 canonical-AZ cell (CL-042): five iterations, tau flat, prediction rising

| arm | regret_mean | top1 | tau |
|---|---|---|---|
| v29_leaf | 0.9508 | 0.6095 | 0.6153 |
| iter_00 | 1.8668 | 0.0804 | 0.0180 |
| iter_01 | 1.9651 | 0.0840 | 0.0206 |
| iter_02 | 1.9008 | 0.0760 | 0.0180 |
| iter_03 | 1.8177 | 0.0742 | 0.0212 |
| iter_04 | 1.8570 | 0.0769 | 0.0232 |

Paired vs leaf: sign-z −17..−18 (+0.87..1.01 pts exact margin lost/root). Heads NOT
dead-forward: value↔score-diff correlation rises 0.50 → 0.65 across the same
iterations — "position LEVEL learned, between-sibling discrimination ZERO" (the first
recorded appearance of the paper's dissociation).

- Sources: `measurement/canonical_az/solver_score_m2_final_it00_04.json` `aggregate`
  block (⚠️ file is currently UNTRACKED in git — must be committed or archived before
  submission; flagged in the report); results.csv `m2_solver_score_k2_it00_04_n1119`
  (row 241, incl. the sign-z band and 0.50→0.65); CLAIM_REGISTRY.csv CL-042 (FINAL
  2026-07-03 block).

## T7 — Tabula-rasa arm (CL-066): 12 iterations, never approaches the bar

| iter | deck-matched margin vs heuristic-taught anchor (elo) |
|---|---|
| 0 | −47.12 |
| 3 | −32.78 |
| 5 | −27.46 |
| 7 | −34.60 |
| 9 | −36.08 |
| 10 | −26.86 |
| 11 | −29.84 |

Best gap-closure 43% vs the pre-registered 50% ALIVE bar; best winrate 0.12 vs 0.35
bar; random floor solved by iter 2 (0.98–1.00). Explicitly a compute-bounded null:
3,600 games total. Mechanism probe: value head memorizes ~1,200 independent game
labels — held-out corr 0.530 vs a neutral control net's 0.717 on the SAME games.

- Sources: CLAIM_REGISTRY.csv CL-066 (margins sequence verbatim, iter indices per the
  row's "(it0) → … → (it11)" listing — ⚠️ the registry lists 7 values for iters
  0..11 without explicit indices for the middle entries; confirm the per-iter mapping
  against [measurement/az_zero_20260724/RESULTS.md](../../../measurement/az_zero_20260724/RESULTS.md)
  before typesetting); PROBE_OFFDIST_20260724.md (0.530 / 0.717).

## T8 — Depth-conditional ladder ("beats the heuristic" reverses with opponent depth)

| opponent | elo (candidate − heuristic) | z | record |
|---|---|---|---|
| heur@800 | +40.1 ± 17.5 | +2.29 | 220W-174L-6D |
| heur@1600 | +24.4 ± 17.4 | +1.40 | 213W-185L-2D |
| heur@3200 | −28.7 ± 17.4 | −0.70 | 180W-213L-7D |

One shared deck band (3.10e9), n=400 deck-paired per rung, same candidate
(iter8+residual @ sims 200), matched v2.7 leaf both sides. Monotone decay, ~69-elo
swing, crosses zero by h3200. Transitivity control on the same band: heur@1600 vs
heur@800 = +20.0, predicting 40.1−20.0 = 20.1 vs 24.4 measured (dz ~0.3).

- Source: CLAIM_REGISTRY.csv CL-010 best_evidence field (cite the ladder ONLY; the
  claim row itself is SUPERSEDED/era-bound — per CLAUDE.md, the blocker is cited to
  the kill set). results.csv rows `l22_iter8_vs_heur3200_b310_n400`,
  `l22_ctrl_iter8_vs_heur1600_b310_n400` + h800 sibling (grep `l22_` for exact row ids
  at typesetting).

## T9 — Positive controls: the same apparatus detects learned wins where they exist

| control | channel | result | n / design |
|---|---|---|---|
| CL-067 gate | policy priors, equal sims | +42.8 ± 17.5 (wr z +2.45) | n=400 paired, band 52e9 |
| CL-067 confirm | policy priors, equal sims | +28.7 ± 17.4 (wr z +1.65) | n=400 paired, disjoint band 56e9 |
| CL-067 pooled | policy priors, equal sims | **+35.7 ± 12.3 (z +2.89)**; margin paired_z +2.12 | 800 deck-paired games |
| CL-051 leaf re-tune (fair confirm) | heuristic leaf, curve125 | **+48.8 elo, z 3.13** (margin +50.4, z 2.77) | 451 paired decks, fresh band |
| CL-034 offline comparator | LTR objective, offline | beats leaf: regret 0.0289 → **0.0171 (−41%)**, top-1 0.464 → 0.535 | 10,067 sibling sets, seed-split test 1,509 groups |
| CL-034 Stage 5 (the conversion failure) | same comparator through search | all 4 integrations lose to plain search_leaf; search alone collapses decisive regret 0.122 → 0.019 | 596 held-out roots, sims=200 |

- Sources: CLAIM_REGISTRY.csv CL-067 (both cells + pooled, verbatim), CL-051 (S3 fair
  re-confirm), CL-034 (best_evidence Stage 4/5 numbers). results.csv rows
  `distill_strong_iter03_netprior_vs_champ_deploy_k4x688_n400_paired`,
  `distill_strong_iter03_netprior_vs_champ_CONFIRM_56e9_n400_paired`,
  `c5_confirm_curve125_fair`.
- Pooling caveat to carry (CL-067 counterevidence field): neither CL-067 cell clears
  2σ alone; the 2σ result is pooled, and pooling across bands was not pre-registered.
  Report as stated there.

## T10 — The closure ladder at a glance (the paper's signature summary table)

| escape hatch ("but maybe…") | experiment | key statistic | verdict (pre-registered bar) |
|---|---|---|---|
| …the target/head structure was wrong | CL-039 §3A + Probe B | Δ_indep +0.05pp (σ 0.36) vs +3pp bar; 6/6 fair arms α=0 | closed |
| …integration (FPU/blend) was wrong | CL-042 M3 | FPU curve peaks at parity (wr 0.496, z −0.15 vs anchor), never exceeds | closed (parity, not gain) |
| …the canonical AZ cell was never run | CL-042 M2 | tau 0.018–0.023 flat over 5 iters vs leaf 0.615; sign-z −17..−18 | closed |
| …the model was too small | CL-064 | tau 0.133/0.095/0.083 across 386K→10M; best-of-six 0.169 | closed (DEAD gate) |
| …the representation was wrong | CL-065 | leaf's own features + exact labels: best tau 0.386 vs floor 0.615 | closed (DEAD gate) |
| …the heuristic warm-start poisoned it | CL-066 | tabula rasa: best gap-closure 43% vs 50% bar, 12 iters | closed (compute-bounded) |
| …the teacher/corpus was too weak | **CL-073** | strongest corpus (champion @11008): r ↑ 0.680, regret 2.1× worse, sign-z −17.43 | **closed + mechanism named** |

- Sources: each row's registry entry (CLAIM_REGISTRY.csv); CL-039 evidence field for
  §3A/§4A numbers; CL-042 for M3 FPU curve (0.265 → 0.391 → 0.496 peak → 0.4825 →
  0.476, isotonic 0.33) and M2.

---

## Figure plan

| fig | content | data source (plot from disk, no re-measurement) |
|---|---|---|
| F1 | The closure ladder as a diagram (T10 rendered graphically: seven escape hatches, each with its bar and verdict; CL-073 as the keystone) | T10 sources (hand-drawn schematic; numbers from registry) |
| F2 | **The dissociation scatter (headline figure):** x = value↔outcome r, y = solver tau; points = heuristic leaf (0.61, 0.6153), iter_03 (0.6564, 0.0177), value_unlock_v1 (0.6795, 0.0190), M2 iters 00–04 (x = 0.50→0.65 trajectory, y = T6 taus). Shows prediction improving left→right while discrimination stays on the floor. ⚠️ M2 per-iter r values: the registry gives only the range "0.50→0.65" — **TODO-MEASURE (locate the per-iter corr in `/mnt/c/carc-shared/m2_sighted/` eval logs, or plot the range as an arrow)** | READOUT.md §2; VERDICT.json; `solver_score_m2_final_it00_04.json`; CL-042 |
| F3 | Per-root paired regret distribution: histogram of (candidate − leaf) regret over 1,119 roots, annotated 91/523/505 | `measurement/value_unlock_20260730/solver_score_value_unlock.json` per-root records |
| F4 | Capacity: tau vs params (6 checkpoints + leaf line at 0.6153) | `measurement/capacity_probe/solver_score_capacity_full6.json` |
| F5 | Depth-conditional ladder: elo vs opponent sims with 1σ bars (T8), zero line | results.csv `l22_*` rows |
| F6 | Tabula-rasa trajectory: margin vs iteration with the 50%-gap-closure bar (T7) | measurement/az_zero_20260724/RESULTS.md per-iter screens |
| F7 | (optional, mechanism section) residual-target histogram from the F13 probe: measured Δ distribution, |Δ|>1 region annotated EMPTY (0 of 52,971) | READOUT.md §1.2 verbatim histogram |

All figures plot existing on-disk artifacts; no figure requires new games. F2's M2
per-iter r is the only TODO-MEASURE in the figure plan (fallback: arrow annotation).
