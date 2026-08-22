# THREE-PICKER OFFLINE PROBE — COST + LABEL INVENTORY

> **STATUS: BUILD/PRICING ONLY, 2026-08-22. NO LEG HAS BEEN RUN, NO MODEL HAS BEEN
> TRAINED, NO PICKER NUMBER EXISTS.** This file prices two queued roadmap items and
> inventories their labels. It reads no strength number of any kind.
> **0 games · no band · no `experiments/results.csv` row · no claim id ·
> `governance/PRODUCTION.yaml` and `governance/BAND_REGISTRY.csv` untouched.**

Harness: [`scripts/tiletie/probe_pickers.py`](../../scripts/tiletie/probe_pickers.py) ·
tests: [`tests/test_probe_pickers.py`](../../tests/test_probe_pickers.py) ·
prices the roadmap's **"v2.9-GREEDY OFFLINE JUDGE LEG"** and
**"LEARNED TIE-BREAKER NET, STAGE-0"** (both queued 2026-08-21,
[PROGRAM_ROADMAP](../../docs/PROGRAM_ROADMAP_2026-07-07.md) parking lot).

---

## 0. THE GATE FIRED FIRST — the harness reproduces `arb = 0.2065` bit-for-bit

Nothing below may be read if this line is not `PASS`. It is `PASS`:

```
=== KNOWNGOOD GATE (tier1 picker vs measurement/tiearb_20260816/READOUT.json) — PASS ✅ ===
  arb  published 0.2064592832  reproduced 0.2064592832  Δ 0.000e+00
  ora  published 0.2545233140  reproduced 0.2545233140  Δ 0.000e+00
  F    published 0.8111605963  reproduced 0.8111605963  Δ 0.000e+00
  n=733 positions / 399 roots   max per-position Δ 0.000e+00 (tol 1e-09)
```

`Δ = 0` exactly, not "within bootstrap noise": the picker, the cross-fit and the
pricing are the *same imported calls* (`analyze_tiletie.crossfit_regret`,
`.parity_indices`, `._sub_mean`, `.aggregate`; `analyze_tiearb.build_positions`,
`.paired_ratio_bootstrap`) on the *same records*, so anything but bit-equality
would be a bug. `F_fixed` 0.7366 and the bootstrap CI [0.4495, 1.3203] also
reproduce to every printed digit.

> ⚠️ **CEILING CAVEAT — travels with every number this harness will ever print.**
> On this corpus the ENTIRE judge-quality ceiling is `ora − arb = +0.048
> pts/tied ply` at the point estimate, and `F = 0.811` has **CI95 [0.450, 1.320] —
> the CI includes 1, i.e. includes ZERO remaining headroom.** Any picker's gain
> here is an unknown fraction of an effect that is itself consistent with zero.
> The measured point is B=16-grade selection; the DEPLOYED arbiter is B=64 and
> captures more, so the residual gap at deploy is plausibly smaller still.

---

## 1. MEASURED — per-playout cost of the v2.9-greedy policy

**Method.** `probe_pickers.py price --playouts 20 --worlds 2 --policies v29-greedy
tier1-greedy`, local box (`Doctor`, 5900XT), `nice -n 19`, **sequential
single-thread, one tenant** (no bench beside it). Real corpus positions from
`measurement/tiletie_pricing_20260812/positions_pooled`, profile `walled`,
shuffled once at `PROBE_SEED = 20260822`, CRN seeds from
`oracle_score_pilot.world_seed/.playout_seed` (imported, never re-derived).
**Both policies were timed on the identical positions and identical worlds** —
`mean_plies = 62.8` for both, which is the witness that the comparison is matched.
Leaf provenance verified before the first playout:
`harness_leaf_hash = a36d2e15a3b3d71d` (curve125, the production champion leaf).
Raw: [`PRICE.json`](PRICE.json).

| policy | n | mean s/playout | median | p90 | min | max | mean plies |
|---|---:|---:|---:|---:|---:|---:|---:|
| **`v29-greedy`** (production flat leaf, Cython) | 20 | **0.0994** | 0.1044 | 0.1716 | 0.0281 | 0.2106 | 62.8 |
| `tier1-greedy` (`RuleBasedPlayer`, v1 OBJECT leaf) | 20 | **1.2230** | 1.4337 | 1.9502 | 0.4260 | 2.0798 | 62.8 |

### ⭐ THE HEADLINE COST FINDING: **v2.9-greedy is ~12.3× CHEAPER than tier1-greedy**

This inverts the LEVER_INDEX row's stated prior that a stronger continuation
"costs more per playout (unbenched)". It does not — for the *offline* leg. The
mechanism is not subtle: `RuleBasedPlayer` scores candidates with
`virtual_score_inplace`, the **v1 OBJECT leaf** (deepcopy + `count_final_scores`),
while `v29-greedy` scores them with `flat_leaf.flat_virtual_score_v2_float` on the
**Cython flat-leaf fast path** (`CARCASSONNE_USE_CY_LEAF=1`). Same 1-ply argmax
shape; ~12× the per-candidate throughput.

⛔ **This says NOTHING about a deploy.** The deployed arbiter's cost is priced
against a *rust* tier1 leg (`rust/carc/carc-core/src/tiearb.rs`,
`scripts/tiletie/tier1_rust_leg.py`), not against this python one, and
`v29-greedy` has **no rust port and no bit-exactness gate**. This is an offline
python-leg figure only.

### Calibrating sequential → W-parallel

The tiearb run's own realized cost on the same corpus (its holdout legs, W=30,
`READOUT.json::cost_from_records`) is **`c_tier1 = 2.5197 worker-s/playout`**
against my sequential 1.2230 s ⇒ a **W-parallel contention factor of 2.060×** on
this box (DRAM-latency-bound, and W=30 oversubscribes 16C/32T — so 2.060 is a
*conservative* multiplier for a W=16 run).

**Projected `c_v29` = 0.0994 × 2.060 = `0.2048` worker-s/playout.**

### Projected wall — full 733-position × 32-world leg, single box

Corpus: **1,468 legs × 32 worlds × 2 picks = 93,952 playouts** (read off the plan,
not assumed).

| scenario | worker-s/playout | worker-hours | wall @ W=16 | wall @ W=30 |
|---|---:|---:|---:|---:|
| **`v29-greedy`, point estimate** | 0.2048 | **5.34** | **≈ 20 min** | ≈ 11 min |
| `v29-greedy`, p90-conservative (0.1716 × 2.060) | 0.3535 | 9.23 | ≈ 35 min | ≈ 18 min |
| `tier1-greedy` equivalent (realized, for scale) | 2.5197 | 65.8 | ≈ 4.1 h | ≈ 2.2 h |

> ⚠️ **Laptop caveat, stated because it is the box the roadmap names.** These are
> **5900XT** numbers. The laptop's single-core ratio to this box is **unmeasured**;
> multiply the wall by it. Even at a pessimistic 2× the laptop leg is **well under
> an hour at W=16**, against the roadmap's "~1 box-night" budget — which was sized
> on the tier1 cost class. **The leg is ~12× cheaper than queued.**
>
> ⚠️ Do not divide worker-hours by W without a real W-parallel bench: the box is
> DRAM-latency-bound and the 2.060 factor is inferred from one prior run at a
> different W, not measured for this policy.

**Chunking is built in** (`score-v29 --chunk k/N`) and reuses the tiearb chunk
shape (`build_tiearb_plan.committed_order` + `.chunk_slices`, one committed
permutation, contiguous slices) so a rid's every leg lands in one chunk. Verified:
`--chunk 3/8 --dry-run` → 91 positions / 179 legs / 10 leg files; the 8 chunks are
a partition of all 733 rids (asserted in the tests).

**Per-record `elapsed_s` is emitted** — the leg is priceable after the fact by
`oracle_score_pilot`'s own `elapsed_secs` stamp, aggregated by
`probe_pickers.cost_from_records` using `run_tiletie.run_smoke`'s convention
(Σ`elapsed_secs`/playouts — never wall-clock, which is inflated by the slowest
position in the pool).

### End-to-end leg smoke (M=4, 2 positions, scratch out-root — not banked)

`records/` written, `ok=True`, `crn_verified=True`, `oracle_policy="v29-greedy"`,
`elapsed_secs` stamped, and the emitted CRN seeds are **bit-identical to the
banked clair-puct records for the same rid** (`world_seeds[:2] = [1107460950,
1297523957]`, `playout_seeds[:2] = [2083724373, 1494856255]` — matched). The v2.9
leg will therefore be CRN-paired, world for world, with the spent corpus.

---

## 2. STAGE-0 LABEL INVENTORY

Label = the per-`(rid, arm)` **CRN world-mean margin under the ARBITER's judge**
(`tier1-greedy`), i.e. the quantity the LEVER_INDEX row names ("train a net to
reproduce the tie arbiter's CRN world-mean margins ... at leaf-tied plies").
Counted by `probe_pickers.collect_labels` / a direct record sweep — every number
below is read off disk.

| corpus (tier1-greedy records) | tied plies (rids) | roots | **(rid, arm) labels** | `m` | salt | usable as-is? |
|---|---:|---:|---:|---:|---|---|
| **`tiearb` pooled** (`tiletie_oof_20260814` + `tiearb_20260816`, the graded corpus) | **733** | **399** | **2,201** | 32 | `tiletie-v1` | ✅ 0 shape problems |
| `tiearb2_20260816` main/merged | 1,350 | 724 | 4,053 | 32 | `tiletie-v1` | ✅ needs its own `--plan-dir` |
| `rung3_r5` S2 (`tiearb_widening_20260817`) | 1,060 | 977 | 7,662 | 32 | `tiletie-v1` | ⚠️ see §2.2 |
| `shared_run_r4` S1 (`tiearb_widening_20260817`) | 1,344 | 748 | 4,672 | **128** | `tiletie-v1` | ⚠️ see §2.2 |
| **TOTAL if everything is admitted** | **4,487** | **2,848** | **18,588** | | | |

Arm-count distribution (the pairwise-ranking budget is driven by this, not by the
rid count — a `k`-arm ply yields `k(k−1)/2` ordered sibling pairs):

| corpus | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| `tiearb` pooled | 295 | 206 | 167 | 65 | — | — | — | — | — | — | — | — |
| `tiearb2_20260816` | 558 | 344 | 335 | 113 | — | — | — | — | — | — | — | — |
| `shared_run_r4` S1 | 542 | 358 | 188 | 67 | 87 | 22 | 25 | 24 | 13 | 12 | 5 | 1 |
| `rung3_r5` S2 | — | — | — | 194 | 357 | 143 | 101 | 94 | 61 | 44 | 57 | 9 |

### 2.1 What stage-0 can actually train on today

The **graded** corpus is the `tiearb` pooled 733 — that is the only slice with a
matching oracle (`clair-puct`) pricing on the same worlds, so it is the only slice
whose capture can be *read*. Training on it alone, with a 5-fold **root** split:

* **2,201 arm labels** over **399 roots**; **2,565 unordered sibling pairs**
  (Σ `k(k−1)/2` = 295·1 + 206·3 + 167·6 + 65·10), doubled by antisymmetrisation to
  **5,130 training rows**, minus exact-tie pairs (dropped — a tie carries no order),
  minus ~1/5 held out per fold.
* Against **84 features** (`measurement/gatec_c0_20260723/c0_features.py`).
* ⇒ roughly **50 rows per feature**, with roots — not positions — as the effective
  sample. **This is the binding constraint, and it is why the default model is a
  pairwise LOGISTIC ranker, not a GBDT or an MLP.** CL-064 already established the
  learned-track failures are not a capacity problem; buying capacity first would
  re-run a settled question. `--model gbdt` (sklearn
  `HistGradientBoostingClassifier` — xgboost/lightgbm are NOT installed) is
  available as the capacity check. `C` is chosen by an **inner** root-grouped CV
  *inside the training folds only*.
* Adding `tiearb2` + `rung3_r5` + (resampled) `shared_run_r4` raises the label pool
  to ~18.6K arm labels / ~2.8K roots — **but those corpora have no oracle pricing
  on this harness's positions**, so they can only enlarge TRAINING, never the
  graded read. That is exactly the stage-1 shape the LEVER_INDEX row describes.

### 2.2 SHAPE MISMATCHES — named, not forced

1. ⛔ **`shared_run_r4` S1 is `m = 128`, not 32.** Field-for-field the same schema,
   same salt, but 4× the worlds. A world-MEAN from 128 worlds is the same estimand
   with ~½ the label noise of an `m=32` mean — **mixing them silently weights the
   two populations differently.** Use them as a separate stratum or subset to the
   first 32 worlds; do not pool and call it one training set.
   `collect_labels` **refuses** any record whose `m != 32` and reports it under
   `shape_problems` rather than coercing it.
2. ⚠️ **The widening corpora's `tier1-greedy` records come from the RUST leg
   runner** (`scripts/tiletie/tier1_rust_leg.py`), not `oracle_score_pilot`, and
   carry a renamed afterstate-key family:
   `afterstate_board_key_{a,b}_root` **instead of** `afterstate_board_key_{a,b}`,
   plus extra `arb_backend` / `crn_witness` / `legal_mask_cache*` /
   `world_deck_hash` / `n_distinct_worlds` keys, and **no**
   `afterstate_deck_hash_{a,b}` / `alloc_{a,b}` / `level_{a,b}`. Harmless for
   *labels* (`values_a`/`values_b`/`m`/`world_seed_salt` are unchanged), **fatal to
   any fixed-key parser** and to the `crn_verified`-by-deck-hash witness. Confirmed
   by direct key-set diff on both S1 and S2.
3. ⚠️ **`rung3_r5` S2's arm-count floor is 5** — by design (it is the *widening*
   corpus). Its tie-set population is systematically wider than the graded corpus's
   (floor 2). Training on it and grading on `tiearb` is a **covariate shift**, not
   just more data.
4. ⚠️ **Every auxiliary corpus is a disjoint seed BAND** (`sp_28e9` vs `sp_281e8`
   vs `sp_135e9`/`sp_137e9`; 0 rid overlap by construction, `G-DISJOINT`). Per
   CLAUDE.md's cross-band rule, **inflate σ ~1.5–2× on any cross-band contrast**;
   within-band deck-paired contrasts are the robust class. A net trained on one
   band and graded on another is a cross-band read.
5. ⛔ **`shared_run_r4/corpus/champ_picks_*/records/*.json` are NOT CRN margin
   records** (keys: `backend, champ_action, champ_secs, deck_seed, error, k_dets,
   ply, rid, root_id, seat, sims`) and `verdicts/per_position_s2.jsonl` is **0
   bytes** (S2 gate-VOIDed). A naive `**/records/*.json` glob under that tree hits
   8,648 of the wrong files first. Excluded.
6. ⚠️ **`shared_run_r4` contributes 0 usable S2 labels** — S2 was gate-voided;
   `rung3_r5` is the corpus that supplied it.
7. ⛔ **The OOF DEV leg `positions_*.jsonl` files are GONE.** The plan at
   `measurement/tiletie_oof_20260814/positions_main/POSITIONS_PLAN.json` points at
   `.claude/worktrees/agent-a1badefaaed4b6d69/...` — a since-deleted agent
   worktree. **This is not a blocker**: the FULL 733-position / 1,468-leg corpus
   (with inline `actions` for 1,353 legs and `archive_path` for 115) survives at
   `measurement/tiletie_pricing_20260812/positions_pooled/`, which is what the
   harness uses as `--plan-dir`. Recorded so nobody rebuilds it.
8. ⚠️ **Feature building is ONE RULES PROFILE PER PROCESS.** `CARCASSONNE_FIX_R9`
   is an import-time latch; `build_features` verifies it and refuses a mismatch.
   The corpus spans `walled` / `fixed_v1` / `app_aug2`, so a full feature cache is
   3 invocations with `CARCASSONNE_FIX_R9` exported per profile (the cache merges).

---

## 3. THE FEATURE REPRESENTATION (stage-0)

`measurement/gatec_c0_20260723/c0_features.py::emit_features_dict(state,
root_player, cfg)` → **84 fixed-order floats** per candidate afterstate: the leaf's
own decomposed terms (`lt_base`, `lt_bonus_self/opp`, `lt_meeple_curve`,
`lt_leaf_score`, uncapped variants), pooled per-component-type features
(city/road/farm/cloister × me/opp/tie/none: counts, sizes, open edges, shields,
closure deltas, finished points), and the meeple/bag economy globals.

Cost: **one `flat_leaf.decompose` per child** — no `board_repr.encode_board`
78-plane tensor, no engine `Farm`/`City` objects, no `count_final_scores`. This is
the cheap scalar path the brief asked for, and it is already the repo's validated
component-feature vector (Gate C0, `scripts/feature_graph/run_offline.py` trains
sklearn on it today).

Smoke (40 rids, `walled`, 4 folds by root): features built, ~190–220 pairwise rows
per training fold, model fit, held-out arms scored, `grade --picker net` produced a
table. **Those numbers are a 40-position plumbing smoke and are NOT a result** —
they are not reported here and must not be quoted.

---

## 4. HONESTY RAILS THE HARNESS ENFORCES IN CODE

| rail | where | test |
|---|---|---|
| known-good must pass before anything else is read | `cmd_grade` calls `require_knowngood` first; it raises `SystemExit` on failure; **there is no skip flag** | `test_grade_runs_the_knowngood_gate_before_anything_else`, `test_no_flag_can_skip_the_gate` |
| `F = arb_picker/ora` is the headline, with the root bootstrap CI | `aggregate_picker` → `ATB.paired_ratio_bootstrap` (20,000 reps, the tiearb run's own seed 20260816) | `test_the_capture_path_calls_the_imported_estimators` |
| ceiling caveat printed beside every result | `CEILING_CAVEAT`, printed unconditionally by `cmd_grade` | `test_ceiling_caveat_names_the_measured_ceiling` |
| stage-0 never reported alone | `blocks["tier1"]` is computed unconditionally, before any picker branch | `test_tier1_is_always_in_the_table_so_no_picker_is_read_alone` |
| net split is by `root_id`, holdout never trained on | `root_folds` asserts a partition; per-fold assertion that no test root appears in training | `test_root_folds_is_a_partition_of_roots`, `test_training_rows_never_contain_a_held_out_root` |
| CRN is imported, never re-derived | `OSP.world_seed` / `OSP.playout_seed`; the file contains no `sha256` | `test_crn_seed_derivation_matches_banked_records_bit_for_bit`, `test_probe_pickers_never_re_derives_a_seed` |
| the ruler stays byte-identical for every other caller | the v2.9 policy is registered process-locally at `build_continuation_agent` | `test_oracle_score_pilot_is_unmodified_on_disk` |

### Two caveats that flatter the candidates and must travel with any read

* **NET FOLD ASYMMETRY.** `tier1`/`v29` select on M/2 worlds and are priced on the
  disjoint M/2 (the cross-fit that makes them winner's-curse-clean). The net's pick
  is world-independent, so its two folds agree and its `arb` is a **full-M**
  difference — same estimand, **less noise**. Its winner's-curse control is the
  root split, not the world split. Printed automatically beside any net number.
* **`v29-greedy` differs from `tier1-greedy` in TWO declared ways**, not one: the
  leaf (curve125 flat vs v1 object) **and** the absence of `RuleBasedPlayer`'s two
  meeple hand-rules (endgame force-place, no-early-farmers). A leg that moves the
  number does not by itself say which of the two moved it. Also: `tier1-greedy` was
  chosen precisely because it is **OUT-OF-FAMILY**; `v29-greedy` is **IN-FAMILY**
  (it is the champion's own leaf), so a positive sign here *can* be same-family
  self-preference and must be read as such.

---

## 5. WHAT IS QUEUED AFTER THIS (not done here, not authorised here)

1. `score-v29 --chunk k/N` on an idle box — **≈20 min at W=16, not a box-night.**
2. `grade --picker v29` → `F₂.₉ = arb₂.₉ / ora` with its bootstrap CI, beside
   `F_tier1 = 0.811 [0.450, 1.320]`.
3. `train-net --build-features` (×3 rules profiles) then `grade --picker net`.
4. A DEPLOY change still needs the mechanism argument that beats
   **F ≈ 0.81 with a CI through 1** — no offline capture number can supply it.
