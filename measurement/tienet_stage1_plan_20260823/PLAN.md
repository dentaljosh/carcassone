# TIE-NET STAGE-1 — scaling the learned tie-breaker against stage-0's zero-capture null

> # ⚠️ PLAN — NOT FUNDED, NOT A PREREG
>
> **Status: DESIGN ONLY, 2026-08-23.** Nothing here has been run, built, trained, or
> launched. **0 games · no band · no `experiments/results.csv` row · no claim id ·
> `governance/PRODUCTION.yaml` and `governance/BAND_REGISTRY.csv` untouched · no
> `RUN_LIVE.json`.** This document reads no new strength number of any kind; every
> figure below is either (a) read off disk from a completed run, or (b) arithmetic on
> such a figure, labelled as such.
>
> **This is NOT a pre-registration.** A prereg would have to commit the read-rule
> *before* the numbers exist; this plan proposes candidate read-rules so the owner can
> price them. If any tier here is funded, the funded tier gets its own `READ_RULE.md`
> committed before its first fit, in the house style of
> [`tiletie_term_20260814/GATE_READ_RULE.md`](../tiletie_term_20260814/GATE_READ_RULE.md).
>
> **The pre-stated stage-0 gate said PARK.** This plan does not overturn that. §11 states
> plainly what the owner is buying if they override it.

Harness to EXTEND (not rewrite):
[`scripts/tiletie/probe_pickers.py`](../../scripts/tiletie/probe_pickers.py) ·
tests [`tests/test_probe_pickers.py`](../../tests/test_probe_pickers.py) ·
stage-0 pricing + label inventory
[`tiletie_probe_20260822/PRICE.md`](../tiletie_probe_20260822/PRICE.md) ·
stage-0 read [`GRADE_net.json`](../tiletie_probe_20260822/GRADE_net.json) ·
model witness [`NET_SCORES.json`](../tiletie_probe_20260822/NET_SCORES.json) ·
lever row [`docs/LEVER_INDEX.md`](../../docs/LEVER_INDEX.md) "learned tie-breaker net
(distill the arbiter)" · results row
`tiletie_probe_tienet_stage0_pairwise_ranker_offline_n733_rootsplit` in
[`experiments/results.csv`](../../experiments/results.csv).

---

## 1. THE NULL WE ARE SCALING AGAINST (stage-0, read off disk)

| quantity | value | source |
|---|---|---|
| graded corpus | **733 tied plies / 399 roots** | `GRADE_net.json::blocks.net.n`, `.n_roots` |
| rollout arbiter capture `arb` | **+0.20646** pts/tied ply, se 0.05507, z **+3.75** | `blocks.tier1.arb` |
| oracle-argmax ceiling `ora` | **+0.25452**, se 0.05978, z +4.26 | `blocks.tier1.ora` |
| **tie-net capture `arb_net`** | **−0.04510**, se_cluster **0.05515**, se_boot 0.05502, **z −0.82** | `blocks.net.arb` |
| tie-net boot CI95 | **[−0.15241, +0.06415]**, `frac_boot_le_0` = 0.796 | `blocks.net.arb` |
| `F = arb_net/ora` | **−0.1772**, CI95 **[−0.8386, +0.2259]** | `blocks.net.F*` |
| inner-CV sibling-rank accuracy (5 folds) | 0.5285 / 0.5251 / 0.5212 / 0.5229 / **0.5080** — mean **0.5211** | `witnesses.net_model.folds[].inner_cv_acc` |
| training scale | **2,201 arm labels / 399 roots / 2,565 sibling pairs / 84 features** | `witnesses.net_model`, `PRICE.md` §2.1 |
| `sd_positions` (net) | 1.5297 | `blocks.net.arb.sd_positions` |

**The realized dispersion of record is `se = 0.0552` pts/tied ply at n = 733 positions /
399 root clusters.** Every power number in this plan is derived from that one figure.

Two caveats travel with every number here, unchanged, and are reproduced verbatim in any
stage-1 artifact:

* **CEILING CAVEAT** — on this corpus the entire *judge-quality* ceiling is
  `ora − arb = +0.048` with `F` CI95 [0.450, 1.320] **including 1**. That caveat bounds the
  *v2.9-picker* question. It does **not** bound the tie-net question: the tie-net's target
  is `arb` itself (+0.2065 — amortizing the rollouts at ~zero wall), not the +0.048 residual.
  Stated so nobody mis-imports it in either direction.
* **NET FOLD ASYMMETRY** — `tier1`/`v29` select on M/2 worlds and are priced on the disjoint
  M/2; the net's pick is world-independent, so its `arb` is a **full-M** difference — same
  estimand, **less noise**. Its winner's-curse control is the **root split**, not the world
  split. Carried into every stage-1 read; §6.3 proposes a design that strengthens it.

---

## 2. ⚠️ THE LOAD-BEARING DISTINCTION — TRAINING labels ≠ GRADING positions

This is the single most important line in the plan, and it is the thing a naive
"scale the labels" brief gets wrong:

> **Buying training labels does not improve the resolution of the read by one part in a
> thousand.** The read's `se` is **0.0552 and stays 0.0552** for as long as the graded
> corpus is the same 733 positions / 399 roots — whether the net was trained on 2.5K pairs
> or 350K. Training labels move the *estimate*; only graded positions move the *error bar*.

The graded corpus is fixed at 733 because it is the only slice with `clair-puct` oracle
pricing on the same CRN worlds. Growing it is **clair-puct pricing — the expensive judge**
— and is priced honestly in §4.2. Everything in §3 is the cheap axis.

---

## 3. LABELS — three scaling routes, priced separately

Label = the per-`(rid, arm)` CRN world-mean margin under the **arbiter's** judge
(`tier1-greedy`). Counts below are read off disk
([`PRICE.md`](../tiletie_probe_20260822/PRICE.md) §2, `collect_labels` sweep).

### 3.1 ROUTE (a) — FREE: unify the existing auxiliary corpora

| corpus | rids | roots | arm labels | **sibling pairs** | m | admissible? | what it does to training validity |
|---|---:|---:|---:|---:|---:|---|---|
| `tiearb` pooled (**the graded corpus**) | 733 | 399 | 2,201 | **2,565** | 32 | ✅ already used | — |
| `tiearb2_20260816` | 1,350 | 724 | 4,053 | **4,730** | 32 | ✅ needs own `--plan-dir` | **clean.** Same arm-floor (2), same `m`, same salt, disjoint band. Only cost is plumbing. |
| `shared_run_r4` S1 | 1,344 | 748 | 4,672 | **8,398** | **128** | ⚠️ needs an `m` fix | `collect_labels` **refuses** `m≠32`. Fix = take the **first 32 CRN worlds** (exact estimand match — seeds are ordered and the salt is identical) for the headline, full-128 as inverse-variance-weighted sensitivity. Arm-floor 2 but a long right tail (k up to 13) ⇒ *broader* than the graded population, not shifted off it. Also carries the rust key-renames (below). |
| `rung3_r5` S2 | 1,060 | 977 | 7,662 | **26,139** | 32 | ⚠️ **covariate shift** | **Arm-floor is 5 by design** (it is the *widening* corpus). Its tie-set width distribution does not overlap the graded corpus except in the k=5 stratum (**194 rids / 1,940 pairs**). Training on it and grading on arm-floor-2 ties is a shift in the covariate that the ranker keys on, not just more data. Admit it only as a **declared stratum** with (i) `k` as a feature, (ii) a k≤5-restricted sensitivity fit, (iii) importance weights by `k`. **62% of all free pairs come from this one shifted corpus** — pooling it silently would let the shift drive the headline. |
| **TOTAL if everything admitted** | **4,487** | **2,848** | **18,588** | **41,832** | | | |
| **"CLEAN FREE" (drop `rung3_r5`)** | **3,427** | **1,871** | **10,926** | **15,693** | | | no arm-floor shift anywhere |

Pair counts are Σ`k(k−1)/2` computed from `PRICE.md`'s banked arm-count histogram;
antisymmetrisation doubles them into training **rows**.

**Rows per feature at 84 features** (the constraint `PRICE.md` §2.1 names):

| pool | pairs | rows (×2) | rows/feature | vs stage-0 |
|---|---:|---:|---:|---:|
| stage-0 (minus 1/5 holdout) | 2,565 | 5,130 | **~49** | 1.0× |
| CLEAN FREE (train-on-aux, no holdout needed) | 15,693 | 31,386 | **374** | 7.6× |
| ALL FREE (incl. shifted `rung3_r5`) | 41,832 | 83,664 | **996** | 20.3× |

**⭐ The strongest structural argument for route (a): it is leak-proof by construction.**
Every auxiliary corpus is a **disjoint seed band with 0 rid overlap** (`G-DISJOINT`:
`sp_28e9` / `sp_281e8` / `sp_135e9`,`sp_137e9` vs the graded corpus's own band). A net
trained *only* on auxiliaries and graded on all 733 has **no leakage channel at all** — the
root split becomes unnecessary and the whole 733 is a pure holdout. See §6.3.

**Route (a) engineering cost (the only cost it has):**

| item | effort | risk |
|---|---|---|
| `--plan-dir` plumbing for `tiearb2` | ~1 h | none — the flag exists |
| rust-leg key-alias shim (`afterstate_board_key_{a,b}_root` → `..._{a,b}`; tolerate missing `afterstate_deck_hash_*`/`alloc_*`/`level_*`; extra `arb_backend`/`crn_witness`/`world_deck_hash` keys ignored) + a fixture test asserting both key families parse to **bit-identical labels** | ~2 h | the `crn_verified`-by-deck-hash witness is **unavailable** on rust-leg records — replace with the `crn_witness` field the rust leg does emit, and say so in the artifact |
| `m=128` → first-32 subsetting, with a test that the subset mean equals an `m=32` record's estimand construction | ~2 h | low; keep `collect_labels`' refusal as the default and require an explicit `--allow-m 128 --subset-worlds 32` |
| **exclusions to keep** | — | `shared_run_r4/corpus/champ_picks_*/records/*.json` are **NOT margin records** (8,648 wrong files a naive glob hits first) and `verdicts/per_position_s2.jsonl` is **0 bytes / gate-VOIDed**. `shared_run_r4` contributes **0 usable S2 labels**. Keep `PRICE.md` §2.2's exclusion list in code. |
| feature build for 3 rules profiles (`CARCASSONNE_FIX_R9` is an **import-time latch** — one profile per process, 3 invocations, cache merges) | ~1 h wall | already solved in `build_features` |
| **TOTAL** | **≈ 1 engineering day** | **0 worker-hours of compute** |

### 3.2 ROUTE (b) — CHEAP: fresh self-play tied-ply label generation

Measured constants (all read off disk):

* `c_tier1_rust` = **0.178232 worker-s/playout** at W=30, m=32
  (`measurement/tiearb2_stage2_20260817/COST_REMEASURE.json::c_tier1_rust_w30`; also
  `rust/carc/carc-core/src/tiearb.rs`).
* `mean_arms_A_bar` = **3.0022** scored arms per tied ply **under the J=4 cap**
  (same file). ⚠️ The *uncapped* census mean is **8.55** (median 4) —
  `tiletie_pricing_20260812/census/CENSUS.md`. **Every price below assumes the J=4 cap is
  retained; uncapping is a ~2.85× cost multiplier on this whole route.**
* Pairs per tied ply, banked: 2,565/733 = **3.50**. Rids per root: 733/399 = **1.837**.

**Two leg geometries, and the 1.34× that separates them:**

| design | playouts per ply at B=64 | worker-s/ply |
|---|---:|---:|
| **as-built** (each non-arm0 arm is a *leg*, each leg replays arm0: `(k−1)·2·B`) | 256.3 | **45.7** |
| **lean** (arm0 played once per world, shared across legs: `k·B`) | 192.1 | **34.2** |

The lever row's "**~34 worker-s per labeled ply at B=64**" is the **lean** figure. The lean
design is available *if and only if* the CRN world seed is keyed on `(rid, world_idx)` and
not on the leg — `PRICE.md` §1's end-to-end smoke shows `world_seeds[:2]` matching the
banked clair-puct records **for the same rid**, which is consistent with per-rid keying but
is **not a proof**. ⚠️ **Verify before pricing on 34; otherwise the honest number is 45.7.**
Both are tabled.

| plies | arm labels | pairs | rows | roots | **worker-h @ 34.2 s/ply (lean)** | worker-h @ 45.7 (as-built) | wall @ W=16 (lean) | wall @ W=30 (lean) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **10K** | 30,022 | 35,000 | 70,000 | 5,444 | **95.0** | 127.0 | **5.9 h** | 3.2 h |
| **30K** | 90,066 | 105,000 | 210,000 | 16,333 | **285.0** | 380.8 | **17.8 h** | 9.5 h |
| **100K** | 300,220 | 350,000 | 700,000 | 54,444 | **950.0** | 1,269.4 | **59.4 h** | 31.7 h |

*(95.0 worker-h at 10K reproduces the lever row's "10K plies ≈ 95 wh" exactly. **`wh` here
means WORKER-HOURS, not watt-hours** — the lever row's abbreviation, kept for continuity.)*

**Position sourcing for route (b) is FREE up to ~38K plies.** The `champ_games` bank
(`measurement/champ_action_logs/champ_games.jsonl`) holds **449 champion self-play games /
57,675 eligible tile plies**; at the measured self-play tie rate **67.2%** [64.5, 69.8]
(`tiletie_pricing_20260812/census/CENSUS.md`, `selfplay|champ_games|walled`) that is
**~38.8K nominal tied plies already on disk**. ⚠️ **NOT MEASURED: the transposition-dedup
yield at a relaxed sampling cap.** The census sampled ≤4 plies/game, and the deduped supply
it produced was 1,053 positions; the dedup fraction when mining the bank at full depth is
unknown. A **zero-compute dry-run of the miner** prices it exactly — make that a
pre-flight, not an assumption. Beyond the bank, new self-play costs **290 worker-s/game**
(`measurement/classical_search/WSWEEP_GEN_RUST_local.tsv`, W=48 settle row: 48×870/144);
⚠️ `docs/CLUSTER_OPS.md` prose implies **527 worker-s/game** for the same profile —
**the two disagree by 1.8× and the discrepancy is unresolved**; use 527 for any commitment.
At ~23 tied plies/game (the only per-game density on disk, and it is the **E4** figure) the
100K rung needs ~2,700 new games ≈ **217–394 worker-h** of self-play *on top of* the 950.

**⭐ The deeper-labels alternative, which this route's framing hides.** At fixed
worker-seconds you may buy **more plies** or **deeper labels**. The label is a world-mean
margin with `se ∝ 1/√B`. 2,500 plies at B=256 costs the same 95 worker-h as 10,000 plies at
B=64 and **halves the label noise** instead of quadrupling the count. Stage-0 dropped only
**exact**-tie pairs; it fed the ranker every pair whose margin difference was smaller than
its own standard error — i.e. **coin-flip labels presented as data**. If most of the 2,565
pairs are in that regime, the effective label count was far below 2,565, the "tiny pool"
story is *worse* than stated, and **the fix is B, not n**. Which it is, is **free to compute
today** from banked `values_a`/`values_b` — see pre-flight **P2** (§9).

### 3.3 ROUTE (c) — combination

Free pool first (it is leak-proof and costs no compute), fresh labels layered on top as the
*upper rungs of the label-scaling curve* (§9), not as a replacement:

| tier | pairs | rows/feature | compute (worker-h) |
|---|---:|---:|---:|
| **T0** stage-0 (incumbent) | 2,565 | 49 | 0 |
| **T1** + `tiearb2` | 7,295 | 174 | **0** |
| **T2** + `shared_run_r4` (first-32) = **CLEAN FREE** | 15,693 | 374 | **0** |
| **T3** + `rung3_r5` (declared shifted stratum) = **ALL FREE** | 41,832 | 996 | **0** |
| **T4** + 10K fresh plies | 76,832 | 1,829 | **95** |
| **T5** + 30K fresh plies (instead of T4) | 146,832 | 3,496 | **285** |
| **T6** + 100K fresh plies (instead of T5) | 391,832 | 9,329 | **950** (+218–394 self-play above ~38K plies) |

T0→T3 is a **16.3× pair sweep for zero compute.** T0→T6 is **153×**.

---

## 4. POWER — what any of this can actually resolve

### 4.1 At the FIXED graded corpus (n = 733, se = 0.0552)

| statement | arithmetic | value | as a fraction of `arb` = 0.2065 |
|---|---|---:|---:|
| 1σ | — | 0.0552 | 26.7% |
| **2σ resolution** | 2×0.0552 | **0.1104** | **53.5%** |
| CI95 excludes 0 (convict) requires | est > 1.96σ | **0.1082** | **52.4%** |
| 80%-power detectable effect (1-sided α=.05) | (1.645+0.842)σ | 0.1373 | 66.5% |
| 80%-power detectable effect (2-sided α=.05) | (1.96+0.842)σ | 0.1547 | 74.9% |

**Read that honestly: the 733-position corpus can only convict a tie-net that reproduces
more than half the rollouts' capture, and is only 80%-powered against one that reproduces
three-quarters of it.** No amount of training labels changes this line.

### 4.2 Buying GRADED positions (the expensive judge, priced)

Per-position cost of a **new** graded position (self-play / `walled` / rust-eligible),
J=4-capped, m=32 — playouts/position = `(3.0022−1)·2·32` = **128.14**:

| component | rate (worker-s/playout) | source | worker-s/position | worker-h/position |
|---|---:|---|---:|---:|
| **`clair-puct` oracle (IF), rust** | **1.5999** (realized) | `tiletie_pricing_20260812/STAGE_B_ADDENDUM.md` §5.1 — the planning constant was 1.4755, realized was +8.4% | 205.0 | 0.05694 |
| `tier1-greedy` arbiter, rust | 0.178232 | `tiearb2_stage2_20260817/COST_REMEASURE.json` | 22.8 | 0.00634 |
| **TOTAL per graded position** | | | **227.8** | **0.0633** |

⚠️ **This is the rust rate and it only applies to self-play/`walled` positions.** The graded
733 is **673 rust + 60 E4/python**; the python rate is **9.85 worker-s/playout**
(`tiletie_pricing_20260812/DESIGN.md` §7.4) ⇒ **0.357 worker-h/position, 5.6× more**. The
1,053-position deduped supply already has 733 scored; the **320 unscored leftovers are the
E4/python arm** (~114 worker-h for the lot) and are a different rules-profile population.
**Do not grow the graded corpus with E4 positions** — grow it with self-play positions mined
from the bank.

| graded n | roots | se | 2σ | 2σ as % of `arb` | **new positions** | **worker-h** | wall @ W=16 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| **733** (current) | 399 | **0.0552** | 0.1104 | 53.5% | 0 | **0** | — |
| 1,466 | ~798 | 0.0390 | 0.0781 | 37.8% | +733 | **46.4** | 2.9 h |
| **1,645** ⭐ | ~896 | **0.0368** | 0.0736 | 35.6% | **+912** | **57.7** | **3.6 h** |
| 2,199 | ~1,197 | 0.0319 | 0.0638 | 30.9% | +1,466 | 92.8 | 5.8 h |
| **2,932** ⭐⭐ | ~1,596 | **0.0276** | 0.0552 | 26.7% | **+2,199** | **139.2** | **8.7 h** |
| 7,330 | ~3,990 | 0.0175 | 0.0349 | 16.9% | +6,597 | 417.6 | 26.1 h |

*(se scaled as `0.0552·√(733/n)`, i.e. the realized cluster-robust dispersion, not a
re-derivation. Root counts scaled at the banked 1.837 rids/root.)*

⭐ **n = 1,645 (+912 positions, 57.7 worker-h, one 4-hour box-afternoon at W=16)** is the
point at which the gate in §7 becomes **80%-powered at the 50%-of-`arb` bar**.
⭐⭐ **n = 2,932 (+2,199 positions, 139 worker-h, one box-night at W=16)** is the point at
which the gate becomes a **partition** — see §7.3. These two rows are the only graded-corpus
purchases this plan would ever recommend.

---

## 5. FEATURES — the ladder, and the CL-064 caveat stated without flinching

Stage-0 used **84 fixed-order floats** from
[`measurement/gatec_c0_20260723/c0_features.py`](../gatec_c0_20260723/c0_features.py)
(`emit_features_dict`): the leaf's own decomposed terms (`lt_base`, `lt_bonus_self/opp`,
`lt_meeple_curve`, `lt_leaf_score`, uncapped variants), pooled per-component-type features
(city/road/farm/cloister × me/opp/tie/none: counts, sizes, open edges, shields, closure
deltas, finished points), and meeple/bag globals. Cost: **one `flat_leaf.decompose` per
child** — no `encode_board`, no engine objects, no `count_final_scores`.

| rung | representation | Δ features | compute cost | engineering cost | honest verdict on the prior |
|---|---|---:|---|---|---|
| **R0** | 84 scalars (incumbent) | 0 | free (cached) | 0 | the thing that read chance |
| **R1** | **+ afterstate-minus-ROOT diffs** | +84 | ~free (one extra `decompose` per rid, amortised over k arms) | ~2 h | ⚠️ **TRAP, state it in the artifact: for a LINEAR pairwise ranker on `x_a − x_b`, the root term cancels exactly** — `(x_a−x_r)−(x_b−x_r) = x_a−x_b`. R1 is **perfectly collinear** with R0 in a linear model and adds literally nothing. It can only help a **nonlinear** model. Therefore R1 is not a rung on its own; it is a rung **only paired with M2/M3**. |
| **R2** | **+ leaf-term / tie-geometry decomposition**: the `tiletie_term_20260814` 4-feature geometry menu (closure-cell constrainedness `occ4−1`, frontier constrainedness, frontier size) + the `tiletie_mining_20260814` mined descriptors | +10–20 | ~free (code exists, pure-py flat predictor measured at a 1.082 leaf-cost ratio) | ~3 h | ⛔ **Both menus have ALREADY been tested as hand-crafted terms and BOTH FAILED** (`G-FAIL`, −0.0546 ± 0.0300, 8.4% of ceiling; the mined route failed too). Feeding them as *net inputs* is not a strict re-litigation — a net can combine them nonlinearly where a scalar term could not — but **the prior is bad and must be written down as bad**. Cheap enough to include; must not be sold as new evidence. |
| **R3** | **full board planes** — `board_repr.encode_board`, the 78-plane tensor the net stack already computes | 78×35×35 | encode is trivial (≤50K afterstates × ~ms = minutes) | ⚠️ **real: ~1 week.** 50K afterstates × 78 × 35 × 35 float32 = **~19 GB** ⇒ memmap/npz + batched loader, a conv/ResNet trunk with a RankNet head (sklearn cannot do this), a new training loop, new tests | see the CL-064/065 box below |

### ⭐ THE CL-064 CAVEAT — what is different here, and what is not

The brief asks for this honestly, so:

**What IS different about the tie niche** (this is the lever row's own argument, and it is
real):
1. **The leaf ABSTAINS.** Every member of the kill set — CL-039, CL-042, CL-064, CL-065,
   CL-066, CL-073, the flywheel value-unlock — gated a learner against the leaf **where the
   leaf speaks**. At a leaf-tied ply the leaf has no opinion; the incumbent is the rollouts.
2. **The target is amortisation, not superiority.** The prize is reproducing a measured
   +36→64-elo mechanism at ~zero wall (and it is the **only** named route to tie-arbitration
   elo on the E4 phone anchor, where `rho_phone ≈ 24` kills on-device rollouts).
3. **The labels are terminal-grounded and CRN-paired across arms**, which licenses the
   sibling-**ranking** loss — the direct antidote to CL-073's pathology.

**What is NOT different — and R3 is squarely in it:**
* **CL-065 closed the learned route *representation-independently***: no learner beat the
  leaf's move ordering **even handed the leaf's own features and exact-solver labels**. R3's
  pitch is "give it a richer representation." CL-065 already ran the strongest version of
  that experiment in the other direction and it did not bind.
* **CL-064 measured that capacity is not the blocker.** R3 buys capacity. Buying capacity
  first re-runs a settled question — `PRICE.md` §2.1 says exactly this, which is why
  stage-0's default was a *logistic* ranker.
* **CL-073's mechanism is about sibling ranking specifically** (a value head predicted the
  result *better* than the heuristic while ranking siblings **~30× worse**). Stage-0 already
  used a ranking loss and still read 0.508. The niche did not exempt it.

**⇒ Nothing about the plane representation is exempted by the tie niche. R3 is rung 3 and is
funded only if the label sweep at R0–R2 shows a rising rank-accuracy curve (§9).** Writing
"more capacity" at the top of the ladder would be the exact mistake CL-064 was bought to
prevent.

---

## 6. MODEL, LOSS, AND PROTOCOL

### 6.1 Loss — pairwise ranking, unchanged

Keep the **sibling pairwise ranking** objective. It is the CL-073 antidote and the whole
reason this lever was not dead on arrival. **No outcome-regression head anywhere in stage-1**
— CL-073 is precisely the finding that a better outcome predictor is a worse move
discriminator.

### 6.2 Model ladder

| rung | model | availability | cost | why it is on the ladder |
|---|---|---|---|---|
| **M0** | pairwise logistic, `C` by inner root-grouped CV | **built** (`--model pairwise-logistic`) | seconds | the incumbent; the comparator for every rung above |
| **M1** | pairwise logistic + degree-2 interactions on a screened top-20 subset | ~1 h | seconds | the cheapest possible test of "the map is nonlinear", which is the *only* thing R1 can buy |
| **M2** | GBDT — sklearn `HistGradientBoostingClassifier` on antisymmetrised `x_a − x_b` | **built** (`--model gbdt`; xgboost/lightgbm are **NOT installed**) | minutes | the declared capacity check; pairs with R1/R2 |
| **M3** | small MLP, **RankNet head by construction**: score `f(x_a) − f(x_b)` → logistic, 2×64 hidden | ~4 h | minutes | antisymmetric by construction (no need to antisymmetrise the data); the last cheap rung |
| **M4** | conv trunk on planes + RankNet head | ~1 week | hours | **gated** — see §5 R3 |

### 6.3 ⭐ Split protocol — the recommended change: **AUX-TRAIN / GRADE-733**

Stage-0 used a 5-fold **cross-fit by `root_id`** on the graded corpus (`root_folds` asserts
a partition; per-fold assertion that no test root is in training). That was correct when the
only labels were the graded corpus's own. Once route (a) lands it is no longer the best
design:

> **Train ONLY on auxiliary corpora. Grade on all 733.**
>
> The auxiliaries are **disjoint seed bands with 0 rid overlap by construction**
> (`G-DISJOINT`). There is therefore **no leakage channel**, the cross-fit disappears, the
> full 733 becomes a pure out-of-sample holdout (no 1/5 shrinkage of the graded n), and the
> winner's-curse control strengthens from "a root split" to "a different band entirely".

Caveats that must travel with it:
* This makes the *training set* out-of-band; the **grading is entirely within the graded
  corpus's own band**, so CLAUDE.md's "inflate σ 1.5–2× on cross-band **contrasts**" does
  **not** bite the read. What bites is **distribution shift in the model**, which is a bias
  risk on the estimate, not a variance risk on the error bar. Say exactly that.
* The **fold-asymmetry caveat is still printed** — the net's pick remains world-independent
  and its `arb` remains a full-M difference, i.e. less noisy than the rollouts' cross-fit.
  Do not read a net-vs-rollout gap of order the noise as a strength difference.
* Retain the stage-0 root cross-fit as a **secondary consistency check** on the same fits.
  If AUX-TRAIN and cross-fit disagree by more than ~1σ, the shift is doing real work and the
  headline is the cross-fit (the conservative one).

### 6.4 Additional protocol commitments

* **Pre-registered near-tie pair filter.** Stage-0 dropped only **exact**-tie pairs. Declare
  a sweep `κ ∈ {0, 0.5, 1.0}` on `|margin_a − margin_b| ≥ κ · se_pair` (with
  `se_pair = sd_worlds·√2/√m`, CRN-paired ⇒ use the paired sd). `κ=0` reproduces stage-0
  exactly. The κ-curve **is** the label-noise readout.
* **`k` enters as a feature and as a stratifier** whenever `rung3_r5` is admitted, and the
  k≤5-restricted fit is reported beside the pooled one.
* **Inner CV stays inside the training folds only.** Never touch the graded corpus for
  hyperparameter selection under AUX-TRAIN; under the cross-fit, keep stage-0's behaviour.
* **`m=128` records default to REFUSED**; admission requires the explicit
  `--allow-m 128 --subset-worlds 32` and is reported in the witness.
* **CRN seeds imported, never re-derived** (`OSP.world_seed` / `OSP.playout_seed`). The file
  must continue to contain no `sha256`.
* **`require_knowngood` runs first, with no skip flag.** Any stage-1 read that does not
  begin with `arb published 0.2064592832 reproduced 0.2064592832 Δ 0.000e+00` is void.
* **Every fit writes a `manifest.json`** with the fully resolved config (corpora admitted,
  κ, model rung, feature rung, split design, n_pairs, n_roots).

---

## 7. THE GATE, PRE-STATED

Candidate read-rule, to be frozen in a `READ_RULE.md` **before any stage-1 fit**. Two
statistics, both on the graded corpus, both computed by the existing
`aggregate_picker` → `paired_ratio_bootstrap` path (20,000 reps, root clusters, seed
20260816):

### 7.1 STAGE-2 FIRES (a game cell is licensed) iff **both**

1. **`arb_net ≥ 0.50 · arb_tier1`** — the committed fraction, i.e. **`≥ +0.1033`
   pts/tied ply.** (0.50 is the number this plan proposes; the lever row says only "a
   committed fraction". Rationale for 0.50: below half the rollouts' capture, an
   amortisation lever is not worth a game cell against a mechanism already measured at
   +36→64 elo.)
2. **root-bootstrap CI95 lower bound > 0.**

### 7.2 KILL FOR GOOD (lever CLOSED with prejudice) iff **both**

1. **CI95 upper bound < 0.50 · arb_tier1** (`= +0.1033`) at the **top label rung**, and
2. **inner-CV sibling-rank accuracy < 0.53** at the top label rung.

### 7.3 ⚠️ REACHABILITY ARITHMETIC AT THE REALIZED DISPERSION — read this before funding

At `se = 0.0552` (n=733):

| condition | threshold on the point estimate |
|---|---|
| convict (CI_lo > 0) | est > **+0.1082** |
| kill (CI_hi < 0.1033) | est < **−0.0049** |
| **INDETERMINATE dead zone** | **(−0.005, +0.108)** — width **0.113 = 55% of `arb`** |

* **Power of the §7.1 gate at n=733:** against a true capture of exactly 0.50·`arb`
  (z = 1.87), power to clear CI_lo>0 is **Φ(1.87−1.96) = 46%** — a coin flip. Against
  0.75·`arb` (z = 2.81) it is **80%**. **The current corpus is only 80%-powered against a
  three-quarters-of-`arb` net.**
* **⭐ Stage-0 ALREADY satisfies §7.2 condition 1**: its est −0.0451 gives CI_hi = +0.0642 <
  +0.1033. Its rank accuracy 0.5211 also satisfies condition 2. **Under this gate, the kill
  has already fired *at stage-0's label scale*.** Everything stage-1 buys is the
  **label-axis conditional** — "…and it stays dead when you give it 16×/153× the labels."
  That, and nothing else, is the honest description of the deliverable.
* **What graded positions buy** (§4.2 rows): at n=1,645 (`se` 0.0368) the dead zone narrows
  to (0.031, 0.072), width 20% of `arb`, and the §7.1 gate becomes **80%-powered at the 0.50
  bar**. At n=2,932 (`se` 0.0276) the convict bar (0.0541) falls **below** the kill bar
  (0.0492) by less than 0.005 — **the gate becomes an effective partition: every outcome
  either convicts or kills, with no dead zone.** That is what 139 worker-h purchases.

### 7.4 Anti-shopping rail

The graded 733 is a **spent** corpus (the tiearb holdout is spent; nothing here re-opens a
blind slice). Stage-1 is licensed **one** headline read against it: the top label rung × the
best feature rung selected by the **inner** CV, declared in the READ_RULE before fitting.
Every other cell on the label × feature grid is a **diagnostic**, reported as rank accuracy
only, and **may not be quoted as capture**. Menu-shopping against these 733 positions is
already capped at ~1–2 mechanism-argued passes by the `tiletie_term_20260814` close-out;
stage-1 spends one of them.

---

## 8. HONEST PRIORS — stated before any number is bought

1. **Stage-0 read EXACTLY zero.** Not "weakly positive", not "trending". `arb_net` =
   −0.0451, `frac_boot_le_0` = 0.796, `F` = −0.177 with CI95 through zero and well past it,
   inner-CV rank accuracy **0.5211** with the worst fold at **0.5080**.
2. **The program's learned-discriminator record is 0-for-everything.** CL-039/CL-042 closed
   the learned-value route; CL-064 showed it is not capacity; CL-065 closed it
   representation-independently even with exact-solver labels; CL-066 is the tabula-rasa
   flatline; CL-073 named the mechanism (prediction ≠ discrimination). The two hand-crafted
   tie-geometry menus (`tiletie_term_20260814`, `tiletie_mining_20260814`) also failed. The
   base rate for this class of lever in this program is zero, over ~8 attempts.
3. **THE ONE STRUCTURAL HOPE, stated at full strength:** the label pool was **genuinely
   tiny** — 2,565 pairs / **~49 rows per feature** / 399 effective root clusters against 84
   features. A ridge-regularised linear ranker at 49 rows/feature is in the regime where a
   real but modest signal is indistinguishable from noise, and route (a) multiplies it by
   **16.3× for zero compute**. Note also that stage-0's inner CV selected `C = 0.01` or
   lower in **4 of 5 folds** — the model was being regularised nearly to a constant, which
   is exactly the fingerprint of "not enough data to trust any coefficient".
4. **⛔ THE COUNTER, which is stronger:** the rank accuracy is **0.508–0.529, mean 0.5211,
   with fold-to-fold sign-flipping in the selections**. Underfitting from too few labels
   produces a model that is *directionally right and noisy* — a positive-but-unstable
   accuracy. **Chance** accuracy on the *training-adjacent* inner CV is the fingerprint of
   *no learnable signal at these features*, not of insufficient data. And a design-effect-3
   cluster correction puts stage-0's 0.5211 at roughly **z ≈ 1.2 above chance** — it was
   never significantly above chance to begin with.
5. **The 38% mining bound** (deterministic rules over the descriptor space reach ≤62% of the
   naive prize) hints the state→arbitration map is not simple — though a net on raw state is
   outside that bound's function class, so nothing *forbids* representing it
   (`E_worlds[margin]` **is** a deterministic function of the information set).

**Prior, stated as a number so it can be scored later: ~10–15% that any stage-1 tier clears
§7.1.** This plan is designed to be worth running *at that prior*, because its primary
deliverable is a **powered kill**, not a hoped-for win.

---

## 9. ⭐ THE DISCRIMINATING READOUT — separating "more labels fixes it" from "the features carry nothing"

This is the section the whole plan exists for. The design is an **"L"**, not a full grid —
a label sweep at fixed features, plus a feature ladder at fixed (maximum) labels — **9 fits**,
all graded on the same frozen 733.

### 9.1 The sensitive instrument is RANK ACCURACY, not capture

Capture has `se = 0.0552` **forever** (§2). Sibling-rank accuracy is computed on the pairs
themselves, so **its** error bar shrinks with labels:

| pool | pairs | roots | nominal se(acc) = √(0.25/pairs) | with cluster design-effect ≈ 3 | z of a true 0.53 |
|---|---:|---:|---:|---:|---:|
| stage-0 | 2,565 | 399 | 0.0099 | **0.017** | 1.8 |
| CLEAN FREE (T2) | 15,693 | 1,871 | 0.0040 | **0.0069** | 4.3 |
| ALL FREE (T3) | 41,832 | 2,848 | 0.0024 | **0.0042** | **7.1** |
| T5 (+30K plies) | 146,832 | 18,204 | 0.0013 | **0.0023** | 13.2 |

**The accuracy axis is ~4× better resolved than the capture axis at T3 and ~7× at T5.** So:
**rank accuracy is the primary readout of the label sweep; capture is the decision statistic
of the gate.** Never the reverse.

* **"MORE LABELS FIXES IT" signature:** rank accuracy rises monotonically in `log(n_pairs)`
  across T0→T3(→T5), with the rise larger than the (shrinking) error bar. Then, and only
  then, extrapolate what accuracy is needed for 0.50·`arb` capture (calibrated by **P1**
  below) and fund exactly the rung that reaches it.
* **"THE FEATURES CARRY NOTHING" signature:** rank accuracy **flat at 0.50–0.52** across a
  16×–57× label sweep while its error bar falls to ±0.004. That is a **powered null on the
  label axis** — which is the thing the program has never once bought on a learned lever,
  and it is worth more than another inconclusive park.

### 9.2 THREE FREE PRE-FLIGHTS — run these BEFORE funding anything

All three are pure compute-free analysis on already-banked records. Together ≈ 1 engineering
day. **They are the actual recommendation of this plan (§11).**

**P1 — Calibrate accuracy → capture.** Compute the **rollout arbiter's own** sibling-rank
accuracy against the `clair-puct` oracle order on the graded 733 (both orderings are banked).
This answers "what rank accuracy is +0.2065 capture worth?" and converts the whole accuracy
axis from a diagnostic into a **predictor of capture**. Without P1, a rising accuracy curve
is uninterpretable. **Cost: 0 worker-h.**

**P2 — Label-noise audit (the B-vs-n decision).** Distribution of
`|Δ margin| / se_pair` over the 2,565 pairs; report the **effective** (non-coin-flip) pair
count at κ ∈ {0.5, 1.0}. If a large fraction of pairs sit below 1 `se_pair`, the effective
stage-0 label count was far below 2,565 and **route (b) should buy B (deeper labels), not n
(more plies)** — a same-cost, different-lever decision that is invisible without this audit.
**Cost: 0 worker-h.**

**P3 — ⭐⭐⭐ THE DECISIVE ONE: feature informativeness against a NOISELESS target.**
Re-train the identical 84-feature pairwise ranker, same root cross-fit, on the graded
corpus's **`clair-puct` oracle arm order** instead of the arbiter's noisy CRN margins. The
oracle order is already banked for all 733 positions. This holds the label **count** fixed
at 2,565 pairs and removes the label **noise**, isolating the feature axis exactly:

| P3 outcome | conclusion | consequence for funding |
|---|---|---|
| rank accuracy ≈ **0.50** | the 84 features **cannot rank siblings even against a noiseless target**. "More labels" cannot be the story at this representation. | **Do not fund route (b) or (c).** Run T2/T3 (free) to convert §7.2 into a label-scaled kill, then **close the lever.** |
| rank accuracy ≈ **0.55–0.60** | the features carry real signal; stage-0 was noise- and/or count-limited. | Fund per P2: deeper labels if P2 shows a noise problem, more plies if it does not. |
| rank accuracy **> 0.60** | strong feature signal; the binding constraint was the label pool. | Fund T4/T5 **and** the §4.2 `n=1,645` graded expansion so the gate can actually convict. |

⚠️ **P3 rail:** it trains against the same oracle quantity used to grade. It is a
**diagnostic of feature informativeness only** and **must never be reported as capture**,
must keep the root cross-fit, and must be labelled as such in its artifact. It burns no
positions and re-opens no blind slice.

### 9.3 The "L" design, if funded past the pre-flights

* **Label arm** (features fixed at R0, model fixed at M0): T0 → T1 → T2 → T3 (→T4/T5). 4–6
  fits, **0 worker-h through T3**. Primary readout: rank accuracy + κ-curve. Secondary:
  capture (diagnostic at every rung, headline at the top rung only, per §7.4).
* **Feature arm** (labels fixed at the top rung): R0/M0 → R0/M2 → R1+R2/M2 → R1+R2/M3
  (→ R3/M4 only if the label arm rises). 4–5 fits, minutes each.

---

## 10. MASTER COST TABLE

| # | item | labels / positions bought | compute (worker-h) | wall | engineering | buys |
|---|---|---|---:|---|---|---|
| **P1** | arbiter rank-accuracy calibration | — | **0** | minutes | ~2 h | makes the accuracy axis interpretable |
| **P2** | label-noise audit (`\|Δ\|/se_pair`) | — | **0** | minutes | ~2 h | the **B-vs-n** decision |
| **P3** | **feature informativeness vs noiseless oracle order** | — | **0** | minutes | ~4 h | **the labels-vs-features discriminator** |
| **A1** | route (a) T1: `tiearb2` | +4,730 pairs (2.8× total) | **0** | — | ~1 h | plumbing only |
| **A2** | route (a) T2: `shared_run_r4` first-32 = **CLEAN FREE** | +8,398 pairs (6.1× total, 374 rows/feat) | **0** | — | ~4 h | leak-proof 6× label sweep, no covariate shift |
| **A3** | route (a) T3: `rung3_r5` as declared shifted stratum = **ALL FREE** | +26,139 pairs (16.3× total, 996 rows/feat) | **0** | — | ~3 h | the 16× rung; **62% of pairs come from the shifted corpus** |
| **M** | model ladder M1–M3 (+R1/R2 features) | — | **0** | minutes | ~8 h | the nonlinearity + capacity check |
| **B1** | route (b) 10K fresh plies @ B=64 lean | +35,000 pairs (T4: 30× total) | **95.0** | 5.9 h @W16 | ~4 h | the 30× rung |
| **B2** | route (b) 30K fresh plies | +105,000 pairs (T5: 57× total) | **285.0** | 17.8 h @W16 | — | the 57× rung |
| **B3** | route (b) 100K fresh plies | +350,000 pairs (T6: 153× total) | **950** (+218–394 self-play beyond ~38K plies) | 59 h @W16 | — | the 153× rung |
| **B′** | route (b) alternative: 2,500 plies @ **B=256** | +8,750 pairs, **half the label noise** | **95.0** | 5.9 h @W16 | ~4 h | the deeper-labels lever, if **P2** says noise |
| **G1** | ⭐ graded corpus → **n = 1,645** (+912 positions) | +912 graded | **57.7** | 3.6 h @W16 | ~6 h | §7.1 gate becomes **80%-powered at the 0.50·`arb` bar** |
| **G2** | ⭐⭐ graded corpus → **n = 2,932** (+2,199 positions) | +2,199 graded | **139.2** | 8.7 h @W16 | — | §7 gate becomes a **partition** (no dead zone) |
| **R3/M4** | board planes + conv RankNet | — | hours | — | **~1 week** | capacity — the CL-064/065 re-litigation; gated |
| | **FREE TIER TOTAL (P1–P3 + A1–A3 + M)** | **16.3× labels** | **0** | ~1 day | **~24 h eng** | the label-vs-feature answer + a label-scaled §7.2 kill |
| | **FULL BUILD (free tier + B2 + G1)** | 57× labels, n=1,645 graded | **343** | ~21 h @W16 | ~34 h eng | a powered, convictable gate |

---

## 11. RECOMMENDATION

**Fund the FREE TIER only — P1, P2, P3, A1–A3, and the M1–M3 model rungs: zero worker-hours
of compute, roughly one engineering day — and make P3 the funding gate for everything
below it.** The reason is that the expensive routes are all conditioned on a question that
is free to answer and has not been asked. Route (b) at any rung, and the graded-corpus
expansions G1/G2, are purchases against the hypothesis *"stage-0 was label-limited"* — but
stage-0's own fingerprint argues the opposite: an inner-CV rank accuracy of **0.5211** with
its worst fold at **0.5080**, sign-flipping fold selections, and `C` regularised to 0.01 or
below in 4 of 5 folds, is the signature of *no learnable signal at these 84 features*, not
of a model straining against too little data — underfitting looks like directionally-right
and noisy, not like chance. **P3 settles it for free**: retrain the same ranker on the
`clair-puct` oracle's own arm order, which is already banked for all 733 positions, holding
the label count fixed and removing the label noise. If that reads ~0.50, the features cannot
rank siblings even against a perfect target, "more labels" is arithmetically not the story,
and the honest move is to run the free 16.3× label sweep (A1–A3) purely to convert §7.2 into
a *label-scaled* kill and close the lever with prejudice. If P3 reads ≥0.55, the features do
carry signal, P2 then decides whether to buy depth (B′) or breadth (B1/B2), and **only then**
does G1 make sense — because a convicting read is otherwise unreachable: at the realized
`se = 0.0552` the gate has a dead zone 55% of `arb` wide and is a coin flip against a
50%-of-`arb` net, and it takes **+912 graded positions / 57.7 worker-h** to make it
80%-powered and **+2,199 / 139 worker-h** to make it a partition. Sequencing the free
diagnostic ahead of the compute keeps the program from spending 95–950 worker-hours to
re-learn something a day of analysis can settle.

**What the owner is buying by overriding the stage-0 park gate — stated plainly.** They are
**not** buying a strength result, and the prior that stage-1 clears §7.1 is ~10–15%. The
stage-0 park was the correct *strength* decision and this plan does not overturn it. What
the override buys is a **diagnosis**: whether the program's 0-for-everything
learned-discriminator record is a *feature-representation* fact or a *label-scale* fact —
which, after CL-039/042/064/065/066/073 and two failed hand-crafted tie-geometry menus, has
never actually been established, and which the tie niche is the last clean place to test
(the leaf abstains, the labels are terminal-grounded and CRN-paired, and a ranking loss is
licensed). Under the §7.2 rule as written, the **kill has already fired at stage-0's label
scale**; the free tier is what earns the right to say "…and it stays dead at 16× the labels,
with the rank-accuracy error bar down to ±0.004." Because the recommended tier costs **zero
worker-hours**, the override is an **engineering-time decision, not a compute-spend
decision** — and it is the cheapest powered kill available anywhere in the learned track.
