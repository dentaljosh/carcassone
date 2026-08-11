# RoD2 Flywheel — Stage D: Data-Distribution Autopsy

**Question:** Are LATER self-play datasets *stronger* (sharper policy targets, more decisive
value signal, climbing margins) or merely a *different ecology* (same strength, shifted
distribution)?

**Method:** Pure local analysis of existing self-play `.npz` (no compute / no eval / no
games / no data modified). Sampled **50 of 400** games per iter (sorted filenames, every
8th). Trajectory = `iter2 (RoD1-proxy/earliest) → iter3 → iter4 (mid, iter_03 net) →
iter5 → iter6 (late, iter_05 net)`. Repo venv. Runtime ~13 s.
Script: `scratchpad/audit_rod2_data.py` (kept out of repo).

## Schema (decoded empirically — was undocumented)

Each `seed_*.npz` is **one full game**, ~2052 rows, of which **exactly 144 are real
decision rows** (`aux_mask == True`; equivalently `policies` row-sum ≈ 1). The other
~93% are augmentation/non-decision rows (still carry a residual `values` target → training
sees them). Keys: `boards (N,78,25,25)`, `scalars (N,12)`, `policies (N,2511)` (MCTS visit
dist), `values (N,)` = **residual target** (`search_Q − leaf_value`, per the run config),
`valid_masks`, `ownership`, `aux_mask`, `group_id` (all −1, unused).

Scalar columns decoded: `col0/col1` = my/opp meeples remaining (÷7, 8 levels); `col5` =
**tiles-remaining fraction** (1.0→0.0, monotone) used as the **phase proxy** (progress =
1−col5); `col7/col8` = side-to-move one-hot; `col9` = progress; `col11` = coarse running
score-margin proxy (few levels; its last-decision magnitude is the only recoverable
"outcome margin"). No explicit final-outcome / score field exists → outcome is reported as
the `col11` proxy and flagged as such.

Metrics keyed off the **144 decision rows** unless labelled "ALL-rows". Phase buckets on
progress: opening [0,0.2) · midgame [0.2,0.4) · late_mid [0.4,0.6) · pre_endgame [0.6,0.8)
· endgame [0.8,1.0]. Game length is uniform ~144 decisions (min 141, max 144) — full
games, no truncation.

---

## Header table

| iter | n_games | n_decision_pos | mean policy-entropy (nats) | residual mean / std / p99(|v|) | mean |score-margin| (proxy) |
|---|---|---|---|---|---|
| iter2 (earliest) | 50 | 7198 | 1.494 | 0.0066 / 0.126 / 0.482 | 0.215 |
| iter3            | 50 | 7196 | 1.524 | 0.0060 / 0.123 / 0.480 | 0.175 |
| iter4 (mid)      | 50 | 7190 | 1.508 | 0.0057 / 0.128 / 0.455 | 0.215 |
| iter5            | 50 | 7193 | 1.534 | 0.0063 / 0.135 / 0.516 | 0.255 |
| iter6 (late)     | 50 | 7194 | 1.538 | 0.0057 / 0.127 / 0.485 | 0.240 |

(Residual stats here are on **decision rows**. nlegal ≈ 15 across all iters, so entropy is
comparable across iters — the action-branching denominator is stable.)

---

## 1. Phase distribution (positions per phase)

Essentially identical across all five iters — games run to completion every time, so phase
mix is fixed by game structure, not by the generating net.

| iter | opening | midgame | late_mid | pre_endgame | endgame |
|---|---|---|---|---|---|
| iter2 | 1448 | 1400 | 1500 | 1400 | 1450 |
| iter3 | 1448 | 1398 | 1500 | 1400 | 1450 |
| iter4 | 1440 | 1400 | 1500 | 1400 | 1450 |
| iter5 | 1447 | 1399 | 1499 | 1399 | 1449 |
| iter6 | 1446 | 1399 | 1499 | 1400 | 1450 |

**No phase drift.** (Derived from `col5` tiles-remaining fraction.)

## 2. Value-target (residual) distribution — the key suspicion

The training metrics (`val_loss ~0.007`, `value_corr ~0.45`, both flat) suggested the
residual target has near-zero dynamic range. **Confirmed and quantified: the spread is tiny
and does NOT change across iters.**

Decision rows:

| iter | mean | std | abs-mean | p50(|v|) | p90(|v|) | p99(|v|) | frac |v|<0.02 |
|---|---|---|---|---|---|---|---|
| iter2 | 0.0066 | 0.126 | 0.0787 | 0.046 | 0.195 | 0.482 | 0.317 |
| iter3 | 0.0060 | 0.123 | 0.0777 | 0.047 | 0.185 | 0.480 | 0.290 |
| iter4 | 0.0057 | 0.128 | 0.0818 | 0.048 | 0.201 | 0.455 | 0.286 |
| iter5 | 0.0063 | 0.135 | 0.0823 | 0.048 | 0.198 | 0.516 | 0.296 |
| iter6 | 0.0057 | 0.127 | 0.0804 | 0.048 | 0.193 | 0.485 | 0.281 |

ALL rows (what the trainer actually fits, ~106k rows/iter): std ≈ 0.097–0.101,
abs-mean ≈ 0.057–0.061, **~38–43% of targets within ±0.02 of zero**, max|v| ≈ 0.88→1.21.

**Verdict on value:** the residual target is a **tight, near-zero band** (std ≈ 0.13
decision / ≈ 0.10 all-rows; median |residual| ≈ 0.048; a third-to-half of targets are
within ±0.02 of 0). This is exactly the "near-zero dynamic range" that pins `val_loss` at
~0.007 and `value_corr` at ~0.45 — there is little signal for the value head to fit. **The
spread is flat across iters (std 0.123→0.135, no monotone trend; p99 wobbles 0.455–0.516
within noise).** Later data carries **no more decisive value signal** than earliest data.

## 3. Policy-target (visit-distribution) entropy — sharper or noisier?

| iter | mean ent | std | p10 | p50 | p90 | norm-ent (ent/log nlegal) |
|---|---|---|---|---|---|---|
| iter2 | 1.494 | 1.172 | 0.0 | 1.501 | 3.024 | 0.583 |
| iter3 | 1.524 | 1.121 | 0.0 | 1.506 | 2.999 | 0.617 |
| iter4 | 1.508 | 1.113 | 0.0 | 1.478 | 2.991 | 0.613 |
| iter5 | 1.534 | 1.089 | 0.0 | 1.484 | 2.980 | 0.631 |
| iter6 | 1.538 | 1.067 | 0.0 | 1.503 | 2.951 | 0.637 |

Mean policy-target entropy **rises 1.494 → 1.538** (iter2→iter6), and the
branching-normalized entropy rises **0.583 → 0.637** — i.e. the rise is real, not a
side-effect of more legal moves (nlegal is flat ≈15). This **confirms the training
signature** (policy_entropy 1.567→1.609, pol_loss 1.562→1.619 both rising): the policy
target is getting **noisier / less peaked**, not sharper. Per-phase the rise concentrates in
midgame/late_mid/pre_endgame (e.g. late_mid 1.489→1.606); opening and endgame entropy are
flat. **Direction is the opposite of "converging toward sharp strong-play targets."**

## 4. Meeple-count distribution

| iter | my-meeple mean (÷7) | opp-meeple mean | low-meeple frac (≤1 meeple either side) |
|---|---|---|---|
| iter2 | 0.189 | 0.174 | 0.785 |
| iter3 | 0.218 | 0.203 | 0.755 |
| iter4 | 0.225 | 0.210 | 0.735 |
| iter5 | 0.241 | 0.226 | 0.702 |
| iter6 | 0.238 | 0.223 | 0.718 |

A mild, monotone-ish **upward drift in meeples-on-hand** (≈0.18→0.24) and a corresponding
**drop in low-meeple states** (0.785→0.718). Later nets hold/recover meeples slightly more —
a genuine behavioral shift, but small and equally consistent with "different style" as with
"better". Not a strength signal on its own.

## 5. Score-margin / outcome distribution (proxy only)

No final-outcome or score field exists. Using `col11` (coarse running-margin proxy):
mean |final-decision margin| = 0.215 / 0.175 / 0.215 / 0.255 / 0.240 (iter2→6) and
mean |running margin| = 0.200 / 0.220 / 0.203 / 0.224 / 0.252. There is a **slight upward
drift** in late-game margin magnitude (≈0.21→0.24–0.25), but it is non-monotone (iter3 dips
to 0.175) and within the per-iter std (≈0.19–0.23). **Too weak and too noisy to call
"climbing decisiveness"** — and it is a margin *proxy*, not a true game outcome, so treat as
suggestive at best.

## 6. Diversity proxy

The first decision row is a forced/canonical opening (top action identical in all 50 games
→ `n_unique_first_action = 1`; degenerate, ignore). A better proxy — top action at the 10th
decision — gives **36–40 unique / 50** across iter2/iter4/iter6, i.e. high and **flat**
opening diversity. No collapse, no narrowing: later data is **not** more concentrated. The
ecology is broad at every iter.

---

## Verdict — STRONGER vs MERELY DIFFERENT

**Merely different, not stronger — with moderate-to-high confidence.** Across iter2→iter6
the dataset is a *shifted ecology, not a climbing one*: the **value (residual) target spread
is flat and near-zero** (std 0.123→0.135, no trend; median |residual| ≈0.048; 38–43% of
all-row targets within ±0.02 of 0) — there is no growth in decisive value signal, which is
exactly why `val_loss`/`value_corr` are pinned and flat. The **policy target moves the
*wrong* way for strengthening** — mean entropy rises 1.494→1.538 and branching-normalized
entropy 0.583→0.637 (targets getting *noisier/less peaked*, confirming the rising
pol_loss/policy_entropy in training), the opposite of converging toward sharp strong-play.
Phase mix and opening diversity are unchanged. The only directional shifts are a mild
meeple-on-hand drift (0.18→0.24) and a weak, non-monotone, proxy-only late-game margin
uptick (~0.21→0.24) — both consistent with a style change rather than a strength gain, and
neither is a clean climbing signal. **No metric that would indicate genuine strengthening
(decisive value signal, sharpening policy targets) improves; the one that moves clearly
(policy entropy) moves against it.** Later self-play data is a different distribution of
roughly equal strength — consistent with a flywheel that is drifting, not climbing.
