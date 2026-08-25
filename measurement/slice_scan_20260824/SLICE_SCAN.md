# Slice scan — is there ANY slice where a learned ranker beats the v2.9 leaf's sibling ordering?

**Status: DESCRIPTIVE / EXPLORATORY. Banked data only. Zero games, zero net forwards,
no source-tree edits, no commits. Not a preregistered cell and not a verdict.**

Date: 2026-08-24 · Corpus: the 1,119 exact-solver K≤2 roots · Analyst script: `slice_scan.py`
· Raw output: `slice_scan.json`, `slice_scan_console.txt`, `run.log`.

---

## 0. Headline (read this first)

1. **The phase axis does not exist in the banked data, at all.** Every non-circular
   sibling label this program has ever banked comes from ONE phase: the **K=2 endgame**
   (2 tiles left, ply 137–140, mover-0, **tile-placement decisions only**), the same
   **1,119 roots** in every artifact. There is no banked slice-able mid-game or opening
   ground truth, and no banked net per-arm score outside the endgame. So the
   "net early / leaf late" hybrid cannot be tested — in either direction — without new
   compute. (§1, §5.)

2. **Inside the one phase that IS measurable, the leaf wins essentially everywhere.**
   42 cells × 3 metrics, **taking the best of 28 deployable net rankers in every single
   cell** (max-favourable-to-the-net selection):
   - leaf beats best-net on **Kendall-τ in 42/42 cells**;
   - leaf beats best-net on **top-1 in 41/42 cells**;
   - the only CI-clear deployable-net win in 126 comparisons is *regret* in an
     **n=25** corner (`mover meeples free ≥2`) — at that selection width, ~what the
     null predicts.

3. **Even the oracle-supervised upper bound loses on every gate you could actually
   use.** The CL-065 "boring learners" (ridge/GBDT handed the leaf's own union-find
   component read-out **and cross-fit directly on the exact-solver labels**) never post a
   CI-clear τ win in any of the 42 cells (they lead on the point estimate in 2, both
   CIs straddling zero), and **every one of their three CI-clear top-1 wins sits in a
   stratum you cannot gate on** — two cut by the solver label itself
   (`solver best-vs-second gap > 1`: +0.147 [+0.098,+0.209]) and one needing an h6400
   deep search. In **play-time-observable** cells they never clear zero on τ or top-1.

4. **And what they do win is not a "learned" win.** A **4-coefficient free re-weight of
   the leaf's OWN four terms** (`lt_base, lt_bonus_self, lt_bonus_opp, lt_meeple_curve`;
   CL-065's own sanity arm) reproduces or exceeds every gain the 84-feature learners
   show — τ 0.6157 vs leaf 0.6153, top-1 **0.638 vs 0.6095**, regret **0.813 vs 0.951** —
   and beats the leaf in **more** cell-metrics (54) than the learners do (35). The
   residual headroom visible on this ruler is **leaf re-tuning, not learned
   representation.**

**Verdict.** On the only evidence that exists — the K=2 endgame — **there is no slice
where a learned net's sibling ranking beats the classical leaf's**, and the
tile-conditional-net branch of the hybrid family is closed on that evidence. The
**phase-hybrid branch ("net early, leaf late") is not closed and not open — it is
UNTESTED**, because no banked artifact can address it. Closing it needs new compute
(§5), and no amount of it reaches the opening: the exact solver cannot leave the
endgame.

---

## 1. Artifact provenance — what actually exists

### 1a. The non-circular ruler (used here)

`scripts/canonical_az/solver_score.py` scores any per-child ranker's regret / top-1 /
Kendall-τ against **exact endgame-solver child values** (leaf = real `flat_base_score`,
so uncorrelated with the v2.9 heuristic — this is what breaks the circularity that
makes the h6400_v2.9 teacher unusable as a judge, autopsy F4, ~0.995 corr).

Six banked `solver_score*.json` files were loaded. **All six use `max_k=2` and the
identical 1,119 roots**, and the leaf's per-root numbers are **bit-identical across all
six** (verified in-script):

| file | claim | learned rankers contributed |
|---|---|---|
| `measurement/canonical_az/solver_score_derisk_it00_03.json` | CL-042 M2 | iter_00…03 |
| `measurement/canonical_az/solver_score_m2_final_it00_04.json` | CL-042 M2 | iter_00…04 |
| `measurement/capacity_probe/solver_score_capacity_full6.json` | **CL-064** | 6 capacity-ladder ckpts (386K→10M) |
| `measurement/paper_g2_20260803/solver_score_g2.json` | paper G2 | resnet-scratch + 2 transformers, best+final |
| `measurement/probe_5a/arms_retrain/solver_score_5a_arms.json` | probe-5A | 12 feature-ablation arms × 3 seeds |
| `measurement/value_unlock_20260730/solver_score_value_unlock.json` | **CL-073** | `iter_03`, `value_unlock_v1` |

→ **28 distinct deployable net rankers** (torch value heads), all on the same roots.

Corpus root source: `measurement/high_gap_distillation/scaled/{qprobe_A/probe.jsonl,
pool_A.jsonl}`, `n_roots_total` 10,067 → `n_candidates` 1,119 after the K≤2 filter,
`n_scored` 1,119, `n_skipped` 0, `n_errors` 0, mode `marginalized` (== clairvoyant at
K=2), budget 5e6.

### 1b. CL-065's learnability arms (re-fit here for per-root detail)

`measurement/gatec_c0_20260723/results.json` banks only **aggregates**. Its cache
`cache/c0_cache.npz` banks the inputs: `X (50637, 84)` per-child leaf-component
features, `y` exact-solver child values, `group`, `root_seed`, and the leaf's own
per-root metrics. I re-ran `c0_fit.py`'s **own** cross-fit path (5 folds grouped by deck
seed, `FOLD_RNG_SEED=0`, identical learner hyper-parameters) to recover **per-root**
metrics for four arms plus the leaf-reweight control. Reproduction is exact:

| arm | τ (mine) | τ (banked `results.json`) |
|---|---|---|
| `sanity_leaf_terms_ols` (4-term reweight) | 0.6157 | 0.6157 |
| `gate_full_gbdt` | 0.3856 | 0.3856 |
| `gate_full_ridge` | 0.3466 | 0.3466 |
| `diag_raw_no_leaf_ridge` | 0.3498 | 0.3498 |
| `diag_raw_no_leaf_gbdt` | 0.2825 | 0.2825 |
| leaf floor from the cache | **0.6153** | 0.6153 (== the harness ruler) |

### 1c. Root metadata (the slice keys)

Joined by `(seed, ply)` — 1,119/1,119 matched on both sides:
`pool_A.jsonl` → `in_hand_tile` (**tile class**), `meeples_free`, `meeples_placed`,
`placed_farmers`, `scores`, `score_margin_abs`, `bag_size`, `legal_n`;
`qprobe_A/probe.jsonl` → `q_gap_1_2`, `entropy` (h6400 teacher top-2 gap tag);
solver per-root → `n_legal`, `best_vs_second_gap`, `value_spread`, `nodes`.

### 1d. What is NOT in the bank (searched, confirmed absent)

- **No phase variation.** `k_remaining` == 2 for all 1,119 roots; ply ∈ {137,138,139,140}
  (1,021 at ply 140); `phase` == `endgame` for all; `to_move` == 0 for all.
- **No decision-type variation.** Every one of the 50,355 ranker picks decodes to an
  action index < 2500 = a **TileAction** (`action_space.py` layout: tiles 0…W²·4−1,
  meeple slots 2501…2510). The corpus contains **zero meeple-phase roots**, so the
  "tile placement vs meeple placement" slice cannot be computed at all.
- **No full per-arm solver labels beyond K=2.** `measurement/level2/` does reach K=3
  (`l23_positions.jsonl`, `L23_REGRET_RESULTS.json`) and K=4
  (`K4_PROBE_RESULTS.json`, `l23_k4_multisource.jsonl`, 96 positions), but those records
  store `gt.{mode}.per_agent.{agent}.{move,regret}` — **regret for the single move each
  named agent chose**, not a `child_values` map over all siblings.
  `build_action_audit_dataset.py` says so in its own header ("Full per-action regret
  needs a re-solve"). Full `child_values` are banked only at K=2
  (`measurement/pre_tool_audit/k2_childvalues.jsonl`).
- **No net per-arm scores at non-endgame plies.** The artifacts with full per-arm data
  at every ply — `measurement/feature_graph_comparator/data/rows_feat.npz` (314,911 rows,
  `leaf_q` + `oracle_q` + `ply`/`phase`/`q_gap`), `measurement/value_resurrection_pilot/`,
  `measurement/feature_planes_gate/`, `measurement/midgame_reference/` — carry the leaf
  and/or the **circular** h6400_v2.9 teacher per arm, and the net only as an **argmax
  pick** or as **aggregate** offline metrics. CL-067 (the one learned component that beat
  the champion, via policy priors) banks only full-game deck-paired elo — no per-arm
  record anywhere.

---

## 2. Method

- **Unit of analysis = root.** 1,119 roots / **1,119 distinct deck seeds**, one root per
  seed, so root == source game == cluster; a paired bootstrap over roots *is* the
  cluster-aware interval. 10,000 resamples, percentile 95% CI on the paired mean delta.
- **Metrics**, all from the harness's own `group_metrics` (argmax-regret in RAW POINTS,
  top-1 indicator, Kendall-τ-b over the sibling set), oriented to the mover:
  `τ` and `top1` higher-better, `regret` lower-better. τ is NaN on the 182 roots where
  the solver values admit no discriminable pair — dropped pairwise (identically for every
  ranker, since it is a property of the labels).
- **Ranking is always WITHIN an evaluator.** Net scores are tanh-dimensionless, leaf
  scores are point-scale; nothing is compared across scales, only orderings against the
  solver's ordering. (The trap named in the brief.)
- **Best-of-family selection per cell** — in every cell, for every metric, the reported
  candidate is the **argmax over the whole family**. That is deliberately maximally
  favourable to the learner and makes a negative read stronger; it also means a lone
  CI-clear win in a small cell is expected noise, not a signal.
- **Three families kept separate**, because they are not the same kind of object:
  1. `deployable_nets` (28) — torch value heads scored by the harness. Real agents.
  2. `c0_oracle_supervised` (4) — CL-065 ridge/GBDT, **cross-fit on the solver labels
     themselves** from the leaf's own component features. An *upper bound on
     learnability from this representation*, not a deployable agent.
  3. `leaf_reweight_ctrl` (1) — free OLS re-weight of the leaf's own 4 terms. The
     attribution control: anything this matches is a leaf-tuning effect, not a learned one.
- **Observability tag on every slice family.** A stratum is only a candidate hybrid gate
  if a deployed agent can evaluate it *before* moving. `solver best-vs-second gap` and
  `solver value_spread` are derived from the label and are therefore **post-hoc**;
  `teacher top-2 gap` is observable but costs an h6400 search. Tile class, branching,
  meeples-free, ply, score-lead are free at play time.

**Pre-stated read (fixed before the tables were produced):** a slice where net > leaf
with a CI clear of zero is a **scouting signal** that would justify a real preregistered
cell — nothing more. Leaf ≥ net everywhere closes the hybrid family citably.

---

## 3. Overall, before slicing

| ranker | τ | top-1 | solver regret (pts) |
|---|---:|---:|---:|
| **v2.9 leaf (the reference)** | **0.6153** | **0.6095** | **0.9508** |
| `leaf_terms_ols` — 4-coeff reweight of the leaf's own terms | 0.6157 | **0.6381** | **0.8132** |
| `c0:gate_full_gbdt` — 84 feats, solver-supervised | 0.4004 | 0.4978 | 0.8633 |
| `c0:gate_full_ridge` | 0.3700 | 0.4638 | **0.7900** |
| `c0:diag_raw_no_leaf_ridge` | 0.3710 | 0.4522 | 0.7954 |
| best **deployable net** (`probe_5a arm_tempo_only_s2`) | 0.1767 | 0.2082 | 1.5380 |
| best deployable net by regret (`capacity f64b4_s0`) | 0.1717 | 0.1841 | 1.3807 |
| CL-073 `value_unlock_v1` | 0.0174 | 0.0670 | 1.9946 |
| CL-073 parent `iter_03` | 0.0194 | 0.0688 | 2.0000 |
| worst arms (`probe_5a arm_none_s1`, `arm_both_s2`) | −0.006 | 0.055 | 2.08–2.10 |

Two things to notice before any slicing. (i) The **best of all 28 deployable nets** is
still 3.5× worse than the leaf on τ and 2.9× worse on top-1 — CL-073's ~30× framing is
about its own arms; the *whole banked population* tops out at τ 0.177. (ii) The **regret**
column is where the learners look good — and the leaf-reweight control gets there too,
which §4 uses to attribute it.

---

## 4. The slice table

Each cell reports `value (Δ vs leaf [95% cluster bootstrap CI])`, with the candidate
being the **best member of that family in that cell**. "Play-time-observable" vs
"post-hoc" is the gate-usability distinction from §2.

### 4.1 Kendall-tau (higher better)

**Play-time-observable slices — the only ones that could gate a hybrid**

| slice | n | leaf | best of 28 deployable nets | best CL-065 learner (oracle-supervised) | leaf-reweight control |
|---|---:|---:|---|---|---|
| ALL ROOTS | 1119 | **0.615** | 0.177 (-0.439 [-0.465,-0.413]) | 0.400 (-0.215 [-0.237,-0.192]) | 0.618 (+0.003 [-0.008,+0.014]) |
| tile: cloister | 100 | **0.655** | 0.141 (-0.514 [-0.618,-0.407]) | 0.537 (-0.118 [-0.231,+0.000]) | 0.719 (+0.064 [+0.004,+0.135]) |
| tile: road_only | 318 | **0.714** | 0.140 (-0.574 [-0.622,-0.524]) | 0.376 (-0.339 [-0.381,-0.297]) | 0.718 (+0.003 [-0.006,+0.013]) |
| tile: city_only | 368 | **0.513** | 0.237 (-0.276 [-0.324,-0.229]) | 0.374 (-0.134 [-0.169,-0.098]) | 0.499 (-0.009 [-0.029,+0.012]) |
| tile: city+road | 333 | **0.632** | 0.183 (-0.449 [-0.492,-0.403]) | 0.427 (-0.205 [-0.235,-0.174]) | 0.635 (+0.003 [-0.018,+0.026]) |
| branching: low | 380 | **0.620** | 0.229 (-0.392 [-0.442,-0.342]) | 0.446 (-0.173 [-0.211,-0.133]) | 0.631 (+0.011 [-0.011,+0.036]) |
| branching: mid | 369 | **0.614** | 0.171 (-0.444 [-0.487,-0.400]) | 0.377 (-0.238 [-0.272,-0.203]) | 0.605 (-0.010 [-0.027,+0.006]) |
| branching: high | 370 | **0.612** | 0.151 (-0.461 [-0.504,-0.419]) | 0.374 (-0.238 [-0.276,-0.198]) | 0.618 (+0.007 [-0.010,+0.024]) |
| mover meeples free = 0 | 903 | **0.720** | 0.186 (-0.535 [-0.561,-0.508]) | 0.484 (-0.236 [-0.258,-0.216]) | 0.722 (+0.002 [-0.011,+0.016]) |
| mover meeples free = 1 | 191 | **0.207** | 0.170 (-0.036 [-0.080,+0.007]) | 0.167 (-0.040 [-0.101,+0.021]) | 0.211 (+0.005 [-0.011,+0.021]) |
| mover meeples free = >=2 | 25 | **0.144** | 0.144 (-0.000 [-0.127,+0.124]) | 0.265 (+0.121 [-0.022,+0.269]) | 0.169 (+0.025 [-0.028,+0.085]) |
| score: behind | 466 | **0.619** | 0.174 (-0.445 [-0.488,-0.402]) | 0.422 (-0.197 [-0.231,-0.163]) | 0.629 (+0.010 [-0.009,+0.030]) |
| score: close(|d|<=3) | 158 | **0.636** | 0.186 (-0.451 [-0.512,-0.389]) | 0.415 (-0.222 [-0.270,-0.173]) | 0.632 (-0.004 [-0.035,+0.024]) |
| score: ahead | 495 | **0.605** | 0.177 (-0.429 [-0.466,-0.390]) | 0.376 (-0.229 [-0.262,-0.196]) | 0.604 (-0.001 [-0.015,+0.014]) |
| ply 139 | 86 | **0.612** | 0.188 (-0.424 [-0.519,-0.327]) | 0.432 (-0.180 [-0.263,-0.096]) | 0.638 (+0.027 [-0.015,+0.077]) |
| ply 140 | 1021 | **0.615** | 0.175 (-0.440 [-0.467,-0.413]) | 0.399 (-0.217 [-0.239,-0.195]) | 0.618 (+0.003 [-0.008,+0.014]) |

*Post-hoc strata (derived from the solver label / needing a deep search) — NOT usable as a gate*

| slice | n | leaf | best of 28 deployable nets | best CL-065 learner (oracle-supervised) | leaf-reweight control |
|---|---:|---:|---|---|---|
| solver gap==0 (tied best) | 825 | **0.633** | 0.182 (-0.451 [-0.483,-0.420]) | 0.415 (-0.218 [-0.245,-0.192]) | 0.629 (-0.004 [-0.016,+0.008]) |
| solver gap 0<g<=1 | 131 | **0.624** | 0.179 (-0.445 [-0.517,-0.367]) | 0.371 (-0.253 [-0.317,-0.187]) | 0.658 (+0.034 [-0.008,+0.080]) |
| solver gap >1 | 163 | **0.535** | 0.196 (-0.339 [-0.395,-0.283]) | 0.364 (-0.172 [-0.216,-0.128]) | 0.543 (+0.007 [-0.014,+0.030]) |
| solver value_spread: low | 468 | **0.730** | 0.181 (-0.548 [-0.595,-0.501]) | 0.450 (-0.279 [-0.319,-0.239]) | 0.735 (+0.005 [-0.017,+0.030]) |
| solver value_spread: mid | 335 | **0.572** | 0.176 (-0.396 [-0.439,-0.352]) | 0.371 (-0.201 [-0.237,-0.165]) | 0.574 (+0.002 [-0.017,+0.020]) |
| solver value_spread: high | 316 | **0.543** | 0.204 (-0.338 [-0.380,-0.296]) | 0.380 (-0.163 [-0.198,-0.127]) | 0.544 (+0.002 [-0.012,+0.016]) |
| h6400 teacher top-2 gap: low | 373 | **0.693** | 0.204 (-0.489 [-0.542,-0.438]) | 0.457 (-0.233 [-0.273,-0.195]) | 0.686 (-0.005 [-0.025,+0.017]) |
| h6400 teacher top-2 gap: mid | 373 | **0.594** | 0.168 (-0.426 [-0.471,-0.381]) | 0.407 (-0.187 [-0.224,-0.149]) | 0.596 (+0.002 [-0.018,+0.024]) |
| h6400 teacher top-2 gap: high | 373 | **0.576** | 0.184 (-0.391 [-0.434,-0.348]) | 0.351 (-0.225 [-0.260,-0.189]) | 0.585 (+0.010 [-0.006,+0.027]) |

### 4.2 top-1 agreement with the solver's best move (higher better)

**Play-time-observable slices — the only ones that could gate a hybrid**

| slice | n | leaf | best of 28 deployable nets | best CL-065 learner (oracle-supervised) | leaf-reweight control |
|---|---:|---:|---|---|---|
| ALL ROOTS | 1119 | **0.609** | 0.208 (-0.401 [-0.435,-0.367]) | 0.498 (-0.112 [-0.141,-0.081]) | 0.638 (+0.029 [+0.010,+0.047]) |
| tile: cloister | 100 | **0.670** | 0.270 (-0.400 [-0.510,-0.280]) | 0.580 (-0.090 [-0.190,+0.010]) | 0.740 (+0.070 [+0.020,+0.120]) |
| tile: road_only | 318 | **0.632** | 0.179 (-0.453 [-0.509,-0.393]) | 0.465 (-0.167 [-0.217,-0.116]) | 0.642 (+0.009 [-0.013,+0.031]) |
| tile: city_only | 368 | **0.592** | 0.293 (-0.299 [-0.356,-0.242]) | 0.473 (-0.120 [-0.171,-0.068]) | 0.598 (+0.005 [-0.027,+0.038]) |
| tile: city+road | 333 | **0.589** | 0.276 (-0.312 [-0.378,-0.249]) | 0.532 (-0.057 [-0.117,+0.003]) | 0.649 (+0.060 [+0.018,+0.102]) |
| branching: low | 380 | **0.629** | 0.311 (-0.318 [-0.379,-0.255]) | 0.534 (-0.095 [-0.145,-0.042]) | 0.655 (+0.026 [-0.005,+0.058]) |
| branching: mid | 369 | **0.591** | 0.206 (-0.385 [-0.442,-0.325]) | 0.455 (-0.136 [-0.190,-0.081]) | 0.599 (+0.008 [-0.027,+0.043]) |
| branching: high | 370 | **0.608** | 0.195 (-0.414 [-0.470,-0.357]) | 0.503 (-0.105 [-0.157,-0.054]) | 0.659 (+0.051 [+0.022,+0.081]) |
| mover meeples free = 0 | 903 | **0.712** | 0.231 (-0.481 [-0.518,-0.443]) | 0.575 (-0.137 [-0.173,-0.102]) | 0.744 (+0.032 [+0.010,+0.054]) |
| mover meeples free = 1 | 191 | **0.194** | 0.157 (-0.037 [-0.094,+0.021]) | 0.215 (+0.021 [-0.026,+0.068]) | 0.209 (+0.016 [-0.016,+0.047]) |
| mover meeples free = >=2 | 25 | **0.080** | 0.200 (+0.120 [-0.040,+0.280]) | 0.160 (+0.080 [+0.000,+0.200]) | 0.080 (+0.000 [+0.000,+0.000]) |
| score: behind | 466 | **0.631** | 0.191 (-0.440 [-0.494,-0.388]) | 0.513 (-0.118 [-0.165,-0.071]) | 0.659 (+0.028 [+0.000,+0.056]) |
| score: close(|d|<=3) | 158 | **0.633** | 0.209 (-0.424 [-0.513,-0.335]) | 0.481 (-0.152 [-0.234,-0.070]) | 0.639 (+0.006 [-0.044,+0.057]) |
| score: ahead | 495 | **0.582** | 0.232 (-0.349 [-0.398,-0.301]) | 0.491 (-0.091 [-0.135,-0.046]) | 0.618 (+0.036 [+0.010,+0.065]) |
| ply 139 | 86 | **0.581** | 0.209 (-0.372 [-0.477,-0.267]) | 0.453 (-0.128 [-0.244,-0.012]) | 0.605 (+0.023 [-0.035,+0.081]) |
| ply 140 | 1021 | **0.614** | 0.212 (-0.403 [-0.438,-0.368]) | 0.508 (-0.106 [-0.137,-0.074]) | 0.643 (+0.029 [+0.010,+0.050]) |

*Post-hoc strata (derived from the solver label / needing a deep search) — NOT usable as a gate*

| slice | n | leaf | best of 28 deployable nets | best CL-065 learner (oracle-supervised) | leaf-reweight control |
|---|---:|---:|---|---|---|
| solver gap==0 (tied best) | 825 | **0.617** | 0.185 (-0.432 [-0.472,-0.390]) | 0.439 (-0.178 [-0.215,-0.142]) | 0.610 (-0.007 [-0.028,+0.013]) |
| solver gap 0<g<=1 | 131 | **0.603** | 0.374 (-0.229 [-0.321,-0.145]) | 0.718 (+0.115 [+0.046,+0.191]) | 0.725 (+0.122 [+0.069,+0.183]) |
| solver gap >1 | 163 | **0.577** | 0.466 (-0.110 [-0.184,-0.037]) | 0.724 (+0.147 [+0.098,+0.209]) | 0.712 (+0.135 [+0.086,+0.190]) |
| solver value_spread: low | 468 | **0.737** | 0.237 (-0.500 [-0.553,-0.447]) | 0.491 (-0.246 [-0.297,-0.197]) | 0.718 (-0.019 [-0.047,+0.009]) |
| solver value_spread: mid | 335 | **0.499** | 0.212 (-0.287 [-0.343,-0.230]) | 0.478 (-0.021 [-0.075,+0.033]) | 0.570 (+0.072 [+0.036,+0.107]) |
| solver value_spread: high | 316 | **0.538** | 0.282 (-0.256 [-0.316,-0.196]) | 0.538 (+0.000 [-0.047,+0.047]) | 0.592 (+0.054 [+0.019,+0.092]) |
| h6400 teacher top-2 gap: low | 373 | **0.697** | 0.209 (-0.488 [-0.544,-0.429]) | 0.456 (-0.241 [-0.298,-0.185]) | 0.665 (-0.032 [-0.064,-0.003]) |
| h6400 teacher top-2 gap: mid | 373 | **0.544** | 0.169 (-0.375 [-0.432,-0.319]) | 0.418 (-0.126 [-0.182,-0.067]) | 0.587 (+0.043 [+0.008,+0.078]) |
| h6400 teacher top-2 gap: high | 373 | **0.587** | 0.373 (-0.214 [-0.271,-0.161]) | 0.657 (+0.070 [+0.035,+0.107]) | 0.662 (+0.075 [+0.048,+0.105]) |

### 4.3 solver regret in POINTS (LOWER better)

**Play-time-observable slices — the only ones that could gate a hybrid**

| slice | n | leaf | best of 28 deployable nets | best CL-065 learner (oracle-supervised) | leaf-reweight control |
|---|---:|---:|---|---|---|
| ALL ROOTS | 1119 | **0.951** | 1.381 (+0.430 [+0.313,+0.550]) | 0.790 (-0.161 [-0.233,-0.090]) | 0.813 (-0.138 [-0.188,-0.091]) |
| tile: cloister | 100 | **0.750** | 0.800 (+0.050 [-0.330,+0.420]) | 0.410 (-0.340 [-0.600,-0.100]) | 0.550 (-0.200 [-0.400,-0.050]) |
| tile: road_only | 318 | **1.119** | 1.396 (+0.277 [+0.116,+0.434]) | 1.022 (-0.097 [-0.189,-0.016]) | 1.047 (-0.072 [-0.148,-0.016]) |
| tile: city_only | 368 | **0.965** | 1.356 (+0.391 [+0.185,+0.609]) | 0.785 (-0.179 [-0.323,-0.057]) | 0.864 (-0.101 [-0.185,-0.014]) |
| tile: city+road | 333 | **0.835** | 1.498 (+0.664 [+0.429,+0.919]) | 0.646 (-0.189 [-0.336,-0.018]) | 0.613 (-0.222 [-0.324,-0.126]) |
| branching: low | 380 | **0.755** | 1.195 (+0.439 [+0.250,+0.663]) | 0.697 (-0.058 [-0.168,+0.082]) | 0.661 (-0.095 [-0.153,-0.037]) |
| branching: mid | 369 | **1.125** | 1.558 (+0.434 [+0.187,+0.696]) | 0.897 (-0.228 [-0.388,-0.092]) | 0.967 (-0.157 [-0.266,-0.051]) |
| branching: high | 370 | **0.978** | 1.322 (+0.343 [+0.176,+0.511]) | 0.773 (-0.205 [-0.311,-0.111]) | 0.816 (-0.162 [-0.246,-0.092]) |
| mover meeples free = 0 | 903 | **0.442** | 0.983 (+0.542 [+0.436,+0.654]) | 0.271 (-0.171 [-0.238,-0.112]) | 0.295 (-0.147 [-0.195,-0.103]) |
| mover meeples free = 1 | 191 | **3.005** | 2.885 (-0.120 [-0.492,+0.288]) | 2.864 (-0.141 [-0.424,+0.178]) | 2.901 (-0.105 [-0.288,+0.073]) |
| mover meeples free = >=2 | 25 | **3.640** | 2.600 (-1.040 [-2.040,-0.160]) | 3.280 (-0.360 [-0.920,+0.080]) | 3.600 (-0.040 [-0.120,+0.000]) |
| score: behind | 466 | **0.830** | 1.225 (+0.395 [+0.253,+0.541]) | 0.616 (-0.215 [-0.333,-0.118]) | 0.682 (-0.148 [-0.219,-0.084]) |
| score: close(|d|<=3) | 158 | **1.000** | 1.335 (+0.335 [-0.032,+0.728]) | 0.943 (-0.057 [-0.222,+0.120]) | 0.962 (-0.038 [-0.177,+0.114]) |
| score: ahead | 495 | **1.048** | 1.541 (+0.493 [+0.313,+0.689]) | 0.881 (-0.168 [-0.265,-0.077]) | 0.889 (-0.160 [-0.236,-0.091]) |
| ply 139 | 86 | **0.942** | 1.488 (+0.547 [+0.140,+0.953]) | 0.860 (-0.081 [-0.349,+0.174]) | 0.884 (-0.058 [-0.291,+0.174]) |
| ply 140 | 1021 | **0.955** | 1.365 (+0.410 [+0.295,+0.526]) | 0.782 (-0.173 [-0.241,-0.111]) | 0.809 (-0.146 [-0.197,-0.099]) |

*Post-hoc strata (derived from the solver label / needing a deep search) — NOT usable as a gate*

| slice | n | leaf | best of 28 deployable nets | best CL-065 learner (oracle-supervised) | leaf-reweight control |
|---|---:|---:|---|---|---|
| solver gap==0 (tied best) | 825 | **0.749** | 1.080 (+0.331 [+0.215,+0.452]) | 0.661 (-0.088 [-0.164,-0.006]) | 0.669 (-0.080 [-0.133,-0.030]) |
| solver gap 0<g<=1 | 131 | **0.794** | 1.382 (+0.588 [+0.313,+0.863]) | 0.473 (-0.321 [-0.672,-0.076]) | 0.611 (-0.183 [-0.298,-0.092]) |
| solver gap >1 | 163 | **2.098** | 2.669 (+0.571 [+0.160,+0.982]) | 1.663 (-0.436 [-0.613,-0.264]) | 1.706 (-0.393 [-0.571,-0.221]) |
| solver value_spread: low | 468 | **0.152** | 0.355 (+0.203 [+0.152,+0.254]) | 0.111 (-0.041 [-0.068,-0.015]) | 0.109 (-0.043 [-0.064,-0.024]) |
| solver value_spread: mid | 335 | **1.000** | 1.299 (+0.299 [+0.158,+0.439]) | 0.764 (-0.236 [-0.352,-0.125]) | 0.785 (-0.215 [-0.299,-0.137]) |
| solver value_spread: high | 316 | **2.082** | 2.753 (+0.671 [+0.304,+1.060]) | 1.816 (-0.266 [-0.491,-0.038]) | 1.886 (-0.196 [-0.342,-0.057]) |
| h6400 teacher top-2 gap: low | 373 | **0.544** | 0.890 (+0.346 [+0.193,+0.499]) | 0.488 (-0.056 [-0.142,+0.021]) | 0.472 (-0.072 [-0.139,-0.021]) |
| h6400 teacher top-2 gap: mid | 373 | **0.941** | 1.402 (+0.461 [+0.279,+0.665]) | 0.727 (-0.214 [-0.357,-0.102]) | 0.769 (-0.172 [-0.255,-0.094]) |
| h6400 teacher top-2 gap: high | 373 | **1.367** | 1.802 (+0.434 [+0.172,+0.708]) | 1.145 (-0.223 [-0.378,-0.048]) | 1.198 (-0.169 [-0.276,-0.067]) |

---

## 5. Reading the table

### 5.1 Deployable nets: nothing, anywhere

Across 42 cells × 3 metrics = **126 comparisons, each taking the best of 28 nets**:

| family | point-estimate wins (of 126) | **CI-clear** wins (of 126) | of those, on τ | on top-1 | on regret |
|---|---:|---:|---:|---:|---:|
| `deployable_nets` | 4 | **1** | 0 | 0 | 1 |
| `c0_oracle_supervised` | 50 | 35 | 0 | 3 | 32 |
| `leaf_reweight_ctrl` | 103 | 54 | 1 | 21 | 32 |

The single deployable-net win is **regret in `mover meeples free ≥2`, n=25**
(2.60 vs 3.64, Δ −1.04 [−2.04,−0.16], best of 28 arms). At 126 comparisons × best-of-28,
one marginal CI-clear result in the smallest cell in the scan is what the null predicts.
It is **not** a scouting signal.

On τ the leaf leads in **42/42** cells; on top-1 in **41/42** (the exception is the same
n=25 cell, +0.120 [−0.040,+0.280] — not CI-clear). There is no tile class, no branching
regime, no score situation, no ply, and no gap stratum in which any of 28 nets — spanning
CL-042's canonical-AZ iterations, CL-064's 386K→10M capacity ladder, CL-073's
full-strength-corpus value head, the G2 transformers, and probe-5A's feature ablations —
orders sibling moves as well as the heuristic leaf.

### 5.2 Where the *leaf* is weak is not where the net is strong

The one place the gap closes is **meeple availability**: with the mover's meeples
exhausted (n=903, the modal endgame state) the leaf reads τ **0.720** / top-1 **0.712**;
with one meeple free (n=191) it collapses to τ **0.207** / top-1 **0.194**, and with ≥2
(n=25) to τ **0.144** / top-1 **0.080**. Regret triples, 0.44 → 3.01 → 3.64 points.

But the nets do not rise into that gap — they sit at τ 0.170 / 0.144, statistically
indistinguishable from the leaf *because the leaf fell to meet them*
(Δτ −0.036 [−0.081,+0.007] and −0.000 [−0.127,+0.124]). And the CL-065 oracle-supervised
upper bound, given the leaf's own features **and** the solver labels, also gets τ 0.167 /
0.265 there. So the meeple-placement corner is not a learned-model opportunity; it is a
**hard region for every ranker in the bank, including the label-supervised one** — the
signature of a genuinely difficult decision class, not of a representational advantage.
It is also n=216 inside one phase, and it is the *last two tiles*, where a meeple
placement is nearly a terminal-score computation. A scouting note at most.

### 5.3 The oracle-supervised upper bound wins only on ungateable strata

`c0_oracle_supervised` is the strongest thing here after the leaf, and it is not an
agent: it is a cross-fit regression trained on the exact-solver values it is then scored
against. Even so it **never clears zero on τ in any of the 42 cells** (2 point-wins, both
CIs straddling zero: `chapel` +0.005 and the n=21 `meeples free ≥2` corner +0.121), and
in **play-time-observable** cells it never clears zero on top-1 either (3 point-wins, all
CI-straddling). **All three** of its CI-clear top-1 wins are in ungateable strata:

- `solver best-vs-second gap > 1` (n=163): top-1 **0.724 vs 0.577**, Δ +0.147 [+0.098,+0.209]
- `solver gap 0<g≤1` (n=131): +0.115 [+0.046,+0.191]
- `h6400 teacher top-2 gap: high` (n=373): +0.070 [+0.035,+0.107]

You cannot gate on the solver's own gap at play time — knowing it means you already
solved the position. The teacher-gap stratum *is* observable, but only by paying for an
h6400 search, which is far more expensive than either evaluator being compared.

### 5.4 The gains that exist are leaf re-tuning, not learning

This is the load-bearing attribution. `leaf_terms_ols` — **four free coefficients on the
leaf's own four terms**, zero new features, zero learned representation — matches the leaf
on τ (0.6157 vs 0.6153) and **beats it on top-1 (0.638 vs 0.6095, Δ +0.029 [+0.010,+0.047])
and on regret (0.813 vs 0.951, Δ −0.138 [−0.188,−0.091])**, and it beats the leaf in
**54 cell-metrics vs the 84-feature learners' 35** — including the decisive strata where
the learners look best (`solver gap >1`: +0.135 top-1, essentially the learners' +0.147).

So the "learner beats the leaf on regret" pattern visible throughout §4.3 is **not evidence
for a learned representation**. It is evidence that **the v2.9 leaf's four weights are
mis-tuned for point-scale endgame regret** — the leaf's tanh-compressed ordering is
excellent at fine sibling *order* (τ) and comparatively blunder-prone on *decisive*
positions, and re-fitting four numbers fixes most of that. That is a **leaf-tuning lever,
not a hybrid lever**, and it was already sitting inside CL-065's banked `results.json` as
the `sanity_leaf_terms_ols` row (regret 0.8132 vs the leaf's 0.9508); CL-065's headline
quoted τ only, where it correctly ties.

*(Caveat before anyone actions it: `leaf_terms_ols` is cross-fit on this same K=2 corpus.
It is an in-corpus upper bound on what re-weighting buys, at one phase, on regret — not a
promotable config. The honest next step for that thread is a real preregistered leaf
re-tune with a held-out band, not a promotion off this table.)*

---

## 6. What a phase slice would actually cost

The brief asked me to stop and price the gap rather than launch anything. Two pieces are
missing, and **only the first is expensive**:

**(a) Full per-arm exact-solver labels beyond K=2.** `solver_score.py` already computes
`SolveResult.child_values` for every root action; it is simply never persisted above K=2.
The `qprobe_A` set already contains **1,119 K=4 roots** at the same discrete strata. K=2
marginalized solves ran at **12.8 s/root mean** (banked). K=4 needs
clairvoyant+alpha-beta and the M2_PLAN median is **~21 min/root** → **≈390 core-hours ≈
24 h on 16 cores** for the K=4 tier in Python. The rust `carc_core::endgame` path is
**20.8× faster with 19× smaller RSS** (memory `reference_exact_solver_eval_infra`), which
would put it near **~1.2 h on 16 cores** *if* rust supports the mode required — that needs
checking before anyone quotes it, and clairvoyant≠marginalized labels are a different
ground truth than the K=2 tier, so the two tiers are not poolable without an explicit
mode-matched control.

**(b) Net per-arm re-scoring.** Essentially free once (a) exists: `solver_score.py` takes
repeatable `--checkpoint` and scores every ranker on the same `SolveResult`, CPU-only, at
~45 children/root. Adding the nets to a K=4 run costs minutes, not hours.

**The hard limit, which no budget removes:** even a complete K=4 tier is still the
*endgame*. The exact solver cannot reach the midgame, let alone the opening — K=5 is
flagged PENDING and was never run, and `measurement/midgame_reference/` explicitly
disclaims itself as ground truth ("no exact solver at midgame K… none is ground truth").
**The phase axis of the hybrid question is not budget-limited, it is
ruler-limited**: testing "net early, leaf late" requires a non-circular midgame ruler
that this program has repeatedly established does not exist — which is the same
measurement blocker named in CLAUDE.md and MEASUREMENT_FIRST_SPEC. The one legitimately
cheap thing available is a *within-endgame* extension (K=2 → K=4), which broadens the
existing negative by one rung and cannot address the early-game claim at all.

---

## 7. Verdict

Sliced 42 ways across tile class, branching, meeple availability, score situation, ply,
and both decisiveness strata, and taking in every cell the **most favourable of 28 banked
learned rankers**, **the v2.9 classical leaf's sibling move-ordering is not beaten
anywhere on the exact-solver ruler**: it leads on Kendall-τ in 42/42 cells and on top-1
in 41/42, with the lone exception an n=25 corner whose single CI-clear result is what
best-of-28 selection across 126 comparisons produces by chance. Raising the ceiling to an
*oracle-supervised* upper bound — ridge/GBDT cross-fit directly on the solver labels from
the leaf's own component read-out — does not change the answer on any stratum a deployed
agent could gate on; its only real wins live inside strata cut by the solver label itself,
and a **four-coefficient re-weight of the leaf's own terms reproduces or exceeds those
wins**, which relocates the entire residual from "learned representation" to "leaf
re-tuning". **The tile-conditional / decision-conditional branch of the hybrid family is
therefore closed on the evidence that exists, and the closure is now sliced rather than
pooled** — a citable strengthening of CL-065 and CL-073 rather than a new claim. But the
**phase branch — "net early, leaf late" — is neither closed nor opened here: it is
untested and, on banked data, untestable.** Every non-circular sibling label this program
owns describes the last two tiles of the game; no artifact anywhere carries a net's
per-arm scores at an opening or midgame root. Anyone citing this scan should cite it as
**"no slice of the ENDGAME favours the net"**, and should treat a phase-hybrid proposal as
blocked on the same missing midgame ruler that gates the whole superhuman program — not
as refuted.
