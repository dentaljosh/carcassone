# RUNG 3 (`J > 4`) — READ-OUT, rev R5.1 (stratum `s2`)

generated: 2026-08-20T21:24:22Z
read rule: `measurement/tiearb_widening_20260817/rung3_r5/READ_RULE.md rev R5.1`

> Significance is ONE test, taken ONCE: `lower(CI95) > 0` on the
> pre-committed percentile ROOT bootstrap (2000 reps, seed
> 20260819, cluster = `root_id`).
> `clair-puct` is the ORACLE and ADJUDICATES; `tier1-greedy`
> is the ARBITER and RIDES — it adjudicates nothing.

## Gates (READ_RULE §2 — every row resolved, none short-circuited)

| gate | verdict | resolved_at |
|---|---|---|
| `G-ARMS` | PASS | `READOUT::widening.gates.arms` |
| `G-BACKEND` | PASS | `RUN/RUN_MANIFEST_R5.json::{arb_backend, resolved_backend_by_leg, arb_legal_mask_cache} · fallback RUN/legs/s2/tier1-greedy/walled/leg<N>/manifest.json::resolved_config.legal_mask_cache` |
| `G-BAND` | PASS | `RUN/CORPUS_R5.json::{seed_ranges, n_distinct_seeds, n_out_of_band, n_seeds_136e9, max_positions_per_seed}` |
| `G-BITEXACT@HEAD` | PASS | `RUN/GATE_BITEXACT_HEAD.json::{pass, digests_equal, n_value_mismatch} · RUN/INSTRUMENT_IDENTITY_R5.json::{committed_diff.empty, working_tree.by_box.<box>.clean}` |
| `G-COMPLETE` | PASS | `READOUT::widening.completion.s2_n` |
| `G-CORPUS` | PASS | `RUN/CORPUS_R5.json::{leg_path, leg_sha256, r4_exclusion_list_sha256, n_in, n_excluded_r5, n_positions, excluded_rids, arms_r5_sha256} · RUN/ARMS_R5.json` |
| `G-CRN` | PASS | `READOUT::widening.gates.crn` |
| `G-DDRAW` | PASS | `READOUT::widening.j_rider.d_draw.d_draw_ran · RUN/D_DRAW.json` |
| `G-DISJOINT` | PASS | `RUN/GATE_DISJOINT_R5.json::{passed, comparisons.<name>.layers.{a_root_id,b_rid}.n_intersection, comparisons.<name>.{layers_absent, layers_absent_reason}}` |
| `G-DRAW` | PASS | `RUN/GATE_DRAW_R5.json::{ok, n_mismatch, deployed_cap_j}` |
| `G-FAILED` | PASS | `READOUT::widening.failed.{n_failed_rids, n_attempted, rate, by_class}` |
| `G-INTERNAL-DUPE` | PASS | `RUN/GATE_INTERNAL_DUPE.json::{n_positions, n_dupe_groups, n_dupe_positions, d_internal, ply_histogram, band_pairs, leg_sha256}` |
| `G-LEAF` | PASS | `RUN/RUN_MANIFEST_R5.json::preflight.checks.leaf_hash` |
| `G-M` | PASS | `pre-leg RUN/SMOKE_R5.json::m_worlds (TOP-LEVEL) · post RUN/RUN_MANIFEST_R5.json::{m_worlds,b_ceiling_from_m} · fallback RUN/legs/s2/tier1-greedy/walled/leg<N>/manifest.json::resolved_config.m` |
| `G-PREFIX` | PASS | `analyze_widening.build_rows uncapped counters (n_rids / n_prefix_ok), over RUN/ARMS_R5.json::<rid>.{arms, arms_full}` |
| `G-SALT` | PASS | `RUN/RUN_MANIFEST_R5.json::world_seed_salt · RUN/corpus/positions_s2/POSITIONS_PLAN.json::deployed_cap_j · RUN/ARMS_R5.json::<rid>.cap_seed · fallback RUN/legs/s2/tier1-greedy/walled/leg<N>/manifest.json::resolved_config.world_seed_salt` |
| `G-STAGED` | PASS | `RUN/STAGING_R5.json::{arms_r5_sha256, staged_arms_sha256, arms_copy_identical, n_leg_rids, n_arms_rids, rid_sets_equal, missing_in_leg, missing_in_arms, stage_chunks_rid_set_agrees, n_chunks}` |
| `G-TWOBOX` | PASS | `RUN/MERGE_REPORT_s2.json::{ok, problems, dry_run, legs}` |
| `G-UNCAPPED` | PASS | `READOUT::widening.gates.uncapped` |
| `G-REPLICATE` | DROPPED | — |

gate set: **ALL PASS** (19 rows resolved)

- ⛔ `G-REPLICATE`: DROPPED deliberately (READ_RULE §0): its (B <= 16, E = 16) corner is S1's, and S1 is not this run's stratum. Dropped with this sentence rather than silently — R2's objection was the silence, not the drop.

## Rung 3 — the primary

| quantity | value | CI95 |
|---|---|---|
| `Delta_ora` (ora_full − ora_J4, capped plies) | 0.0268 | [-0.0593, 0.1155] |
| `ora_J4` (the ratio's denominator) | 0.2521 | [0.1035, 0.4004] |
| `R_ora` (ora_full / ora_J4) | 1.1063 | [0.7665, 1.7280] |
| `Delta_arb` (deploy RIDER — adjudicates nothing) | 0.0204 | [-0.0584, 0.0968] |

`n_capped` = 1059 over 976 roots at `E = 16`.

## Branch: `X-INCONCLUSIVE`

- none of rows 1-5
- READ_RULE §5, read IN ORDER, FIRST MATCH WINS; the table is TOTAL by row 6, so exactly one row fires for every input.
- the pre-branch guard did NOT fire: lower(CI95(ora_J4)) > 0, so R_ora is a ratio of like quantities and IS reported.

### Mandatory prints (READ_RULE §5 — on every branch)

1. SEPARABILITY, carried blind spot: this design CANNOT separate 1.400 from 1.244. The gap is Delta = 0.054, which is z 1.28-2.00 across the pre-registered sd_delta bracket [0.9, 1.4] — under 2 sigma at every point of it. A point estimate that lands BETWEEN the two predictions reads as the partial-resolution row of the branch table (READ_RULE §5 names it; it is deliberately not spelled here) ONLY IF the realized CI EXCLUDES 1.400 OUTRIGHT — never 'whichever of the two the reader prefers'.

2. POWER: the corrected prediction +0.0842 is UNRESOLVED at the top of the sd_delta bracket — z = 1.995 at sd_delta = 1.4, i.e. it fails 2 sigma by a hair at the pessimistic end. It resolves at 2 sigma iff sd_delta <= 1.371 (READ_RULE §4's power table at n2 = 1,060; se(Delta_ora) = sd_delta/sqrt(1060) in [0.0276, 0.0430]).

3. NEAR-EMPTY at the realized se: the `xfree_window` row ('the cap was free') required a strictly NEGATIVE point estimate (reachable only on [-0.08740676718204808, -0.003206767182048084)). Its non-firing is NOT evidence against the cap being free.

   window (`xfree_window`): lo = -0.0874, hi = -0.0032, half_width = 0.0874, empty = False

⛔ NOT NARRATED. The rows that did not fire are named in the READ_RULE and nowhere in this read-out — a near-miss narration is how a second branch token ends up on a page that fired one.

## Riders

- `d_draw`: ran = True, n_checked = 1060, agreement_rate = 0.0443 — reports the MAGNITUDE of rider I7's dedupe-partition conditional and adjudicates nothing.
- `s1_replication` / `interaction`: R5 HAS NO S1 STRATUM. This address is carried in the §5 address list because that list was inherited from R3.3/R4, which had one. Nothing was measured for it here — no positions, no worlds, no contrast. It is NOT a weak result, NOT a null result and NOT inconclusive: there is no result. Any number reported at this address would be a number about a different run.

## Completion, failures, supply chain

- `completion.s2_n` = 1059 against the committed floor 1007 (= ceil(0.95 x 1060)), evaluated AFTER exclusions and AFTER the §3 whole-rid drop.
- `failed`: 1 rid(s) of 1060 attempted = 0.00094 against the bound 0.02; by class {'WindowTruncationError': 1}.
- READ_RULE §3, CORRECTED ON THE RECORD: R5's corpus sits slightly DEEPER than S1's (mean ply 69.15, median 68, max 142; 63.3% at ply >= 50; only 2.63% at ply <= 2, against S1's mean 66.50) — in exactly the region where the encoder-window limitation fires. The pre-registered expectation is therefore EQUAL-OR-HIGHER than S1's realized 0.30%, NOT lower. The inferential error, named so it is not repeated: the previous revision reasoned from the ply of the three COLLISIONS (forced early by the birthday argument) and generalised it to the ply of the CORPUS. Where collisions happen is not where the population lives.
- supply chain: n_in = 1064, n_excluded_r5 = 4, n_positions = 1060, n_distinct_seeds = 980, max_positions_per_seed = 3.
- `d_internal` = 0.002820 against the absolute 0.05 guard. READ_RULE §2.1: BOTH degeneracy gates are CORPUS-IDENTITY checks, NOT discovery gates. The collision quantity for this corpus was already known (3 groups / 6 positions) because the calibration measured the SAME PHYSICAL FILE. Their live content is 'the corpus is the one that was measured' — a real and falsifiable property (a different leg file, a re-mine, a truncated read all fail it) — and it is ALL they establish.
- `d_model(G) = a*G^b`: VACUOUS — reported because §6 requires it, and marked vacuous because r^2 = 1.0 on a fit with as many parameters as points says nothing. ⛔ It is NOT the bound; the absolute 5% guard is.

## Existence-time markers

Every address this file writes is `[post-scoring]`. READ_RULE §1: every address carries EXACTLY ONE existence-time marker, and every address THIS file writes is [post-scoring] — it exists only after scoring. 'as carried' is not a marker.

A3, before adjudication. ⭐ The A1 pass audits THIS LIST against the committed fixture, so an address added here without its fixture entry FAILS A1 rather than passing silently.

⚠️ The DESIGN's fixture list names `fixtures/READOUT.fixture.json` while its execution-layer ruling names `fixtures/READOUT_R5.fixture.json`, and the RUN dir contains the former. This tool PREFERS READOUT_R5, ACCEPTS READOUT, and records which name it used. The conflict is DISCLOSED, not resolved — resolving it is a prereg amendment, not an analyzer decision.

Addresses:

- `widening.j_rider.s2.delta_ora` `[post-scoring]`
- `widening.j_rider.s2.ci95_ora` `[post-scoring]`
- `widening.j_rider.s2.r_ora` `[post-scoring]`
- `widening.j_rider.s2.ci95_r_ora` `[post-scoring]`
- `widening.j_rider.s2.ora_j4_ci95` `[post-scoring]`
- `widening.j_rider.s2.delta_arb` `[post-scoring]`
- `widening.j_rider.s2.ci95_arb` `[post-scoring]`
- `widening.j_rider.s2.n_capped` `[post-scoring]`
- `widening.j_rider.s2.xfree_window` `[post-scoring]`
- `widening.j_rider.s2.r_ora_reported` `[post-scoring]`
- `widening.j_rider.d_draw.n_checked` `[post-scoring]`
- `widening.j_rider.d_draw.agreement_rate` `[post-scoring]`
- `widening.j_rider.d_draw.d_draw_ran` `[post-scoring]`
- `widening.completion.s2_n` `[post-scoring]`
- `widening.failed.n_failed_rids` `[post-scoring]`
- `widening.failed.n_attempted` `[post-scoring]`
- `widening.failed.rate` `[post-scoring]`
- `widening.failed.by_class` `[post-scoring]`
- `widening.gates` `[post-scoring]`
- `widening.supply_chain` `[post-scoring]`
- `widening.branch.fired` `[post-scoring]`
- `widening.branch.reasons` `[post-scoring]`
- `widening.branch.mandatory_prints` `[post-scoring]`

