# SCHEMA SWEEP — the merge layer's classification, closed by enumeration

*Generated `2026-08-19T11:32:12Z` by `measurement/tiearb_widening_20260817/schema_sweep.py` — **re-runnable**: re-run it and diff, do not hand-edit.*

**Commissioned by [`DEVIATIONS.md` §D4.14b](DEVIATIONS.md).** Three merge refusals in a row (`execution` → D3, `git_rev`/`code_rev` → D4.11, `preflight.checks` → D4.14) meant the classification was being built by crashing into it. Enumerating it closes the schema, and the fail-closed default changes meaning: an unclassified-key raise now means **a schema change — a new emitter field**, which is exactly what should raise.

**Enumerated from 355 REAL artifacts** 32 × RUN_MANIFEST, 1 × RUN_MANIFEST_MERGED, 322 × leg · judges ['None', 'clair-puct', 'tier1-greedy'] · chunks ['1', '10', '11', '12', '13', '14', '15', '16', '2', '3', '4', '5', '6', '7', '8', '9', 'None'] · boxes ['/home/doctor/projects/carcassone/.venv/lib/python3.12/site-packages/carc_rs', 'Doctor', 'None', 'laptop-wsl'] · tranches ['None', 'committed_tranche', 'completion_tranche'].

Both emitters are covered: `oracle_score_pilot` writes `execution`, `tier1_rust_leg` writes `preflight.wheel` — reading one would have missed the other, which is why the commission says *enumerate from the artifacts, not from the code*.

**Observed axis** is a MEASUREMENT over those artifacts — the axis the value is a function of — not an opinion: `none` (never differs) · `leg` · `chunk` · `judge` · `box` · `tranche` (the two revs) · `invocation` (differs per run ⇒ telemetry).

- **UNCLASSIFIED keys: 0** — the schema is CLOSED.
- **Gate-addressed paths missing from the schema: 0** — the converse HOLDS.
- **Keys that WOULD REFUSE on today's artifacts: 0** — the merge is clear.

## `RUN_MANIFEST` artifacts

| path | class | observed axis | n | gate | why |
|---|---|---|---|---|---|
| `arb_backend` | IDENTITY_REQUIRED | none (1/32) | 32 | ⚠️ **YES** | identity-required path |
| `arb_legal_mask_cache` | IDENTITY_REQUIRED | none (1/32) | 32 | ⚠️ **YES** | identity-required path |
| `arms_path` | PER_CHUNK | chunk (16/32) | 32 |  | legitimately per chunk |
| `arms_sha256` | PER_CHUNK | chunk (16/32) | 32 |  | legitimately per chunk |
| `b_ceiling_from_m` | IDENTITY_REQUIRED | none (1/32) | 32 | ⚠️ **YES** | identity-required path |
| `design_doc` | IDENTITY_REQUIRED | none (1/32) | 32 |  | identity-required path |
| `driver` | IDENTITY_REQUIRED | none (1/32) | 32 |  | identity-required path |
| `error` | IDENTITY_REQUIRED | none (1/32) | 32 |  | no merge rule: equal across chunks or RAISE (fail-closed default) |
| `finished_utc` | PER_CHUNK | chunk+judge (32/32) | 32 |  | legitimately per chunk |
| `git_rev` | LICENCE_GOVERNED | chunk (2/32) | 32 |  | the run's rev under one of its four spellings |
| `judge_backend` | RECOMPUTED | judge (2/32) | 32 |  | union / superset across the (judge, chunk) invocations — no single invocation carries them all, and G-BACKEND quantifies over all of them |
| `judges` | RECOMPUTED | judge (2/32) | 32 |  | union / superset across the (judge, chunk) invocations — no single invocation carries them all, and G-BACKEND quantifies over all of them |
| `legs` | PER_CHUNK | chunk+judge (32/32) | 32 |  | legitimately per chunk |
| `m_max` | IDENTITY_REQUIRED | none (1/32) | 32 |  | identity-required path |
| `m_worlds` | IDENTITY_REQUIRED | none (1/32) | 32 | ⚠️ **YES** | identity-required path |
| `oracle_sims` | IDENTITY_REQUIRED | none (1/32) | 32 | ⚠️ **YES** | identity-required path |
| `positions_plan_path` | PER_CHUNK | chunk (16/32) | 32 |  | legitimately per chunk |
| `positions_plan_sha256` | PER_CHUNK | chunk (16/32) | 32 |  | legitimately per chunk |
| `preflight.checks.arb_backend` | JUDGE_SCOPED_IDENTITY | chunk+judge (3/32) | 32 |  | equal WITHIN a judge, ACTIVELY checked; cross-judge not compared |
| `preflight.checks.gate` | PER_CHUNK | chunk+judge (32/32) | 32 |  | chunk-scoped path/flag |
| `preflight.checks.git_clean` | LICENCE_GOVERNED | chunk (2/32) | 32 |  | carried per chunk; ASSERTED by the D4.12 licence (ruled once, not twice) |
| `preflight.checks.leaf_hash` | IDENTITY_REQUIRED | none (1/32) | 32 | ⚠️ **YES** | design constant / gate-addressed |
| `preflight.checks.m` | IDENTITY_REQUIRED | none (1/32) | 32 |  | design constant / gate-addressed |
| `preflight.checks.positions` | PER_CHUNK | chunk (16/32) | 32 |  | chunk-scoped path/flag |
| `preflight.checks.process_census` | TELEMETRY | chunk+judge (32/32) | 32 |  | timestamped ps+loadavg — differs by construction; the emitter itself excludes it from `ok` |
| `preflight.ok` | IDENTITY_REQUIRED | none (1/32) | 32 |  | unclassified inside `preflight` ⇒ RAISE |
| `python` | PER_CHUNK | none (1/32) | 32 |  | legitimately per chunk |
| `r9_by_profile` | RECOMPUTED | none (1/32) | 32 |  | union / superset across the (judge, chunk) invocations — no single invocation carries them all, and G-BACKEND quantifies over all of them |
| `resolved_backend_by_leg` | RECOMPUTED | chunk+judge (10/32) | 32 | ⚠️ **YES** | union / superset across the (judge, chunk) invocations — no single invocation carries them all, and G-BACKEND quantifies over all of them |
| `resume` | PER_CHUNK | none (1/32) | 32 |  | legitimately per chunk |
| `schema` | IDENTITY_REQUIRED | none (1/32) | 32 |  | identity-required path |
| `workers` | PER_CHUNK | chunk+judge (2/32) | 32 |  | legitimately per chunk |
| `world_seed_salt` | IDENTITY_REQUIRED | none (1/32) | 32 | ⚠️ **YES** | identity-required path |

## `RUN_MANIFEST_MERGED` artifacts

| path | class | observed axis | n | gate | why |
|---|---|---|---|---|---|
| `c_remeasure` | IDENTITY_REQUIRED | none (1/1) | 1 |  | ⭐ **NOT produced by `merge_legs`** — contributed by another tool into the same artifact; the merge carries it forward rather than overwriting it. no merge rule: equal across chunks or RAISE (fail-closed default) |
| `stub` | IDENTITY_REQUIRED | none (1/1) | 1 |  | ⭐ **NOT produced by `merge_legs`** — contributed by another tool into the same artifact; the merge carries it forward rather than overwriting it. no merge rule: equal across chunks or RAISE (fail-closed default) |

## `leg` artifacts

| path | class | observed axis | n | gate | why |
|---|---|---|---|---|---|
| `assumed_effect_pts` | IDENTITY_REQUIRED | none (1/161) | 161 |  | no merge rule: equal across chunks or RAISE (fail-closed default) |
| `champion_manifest.agent_class` | IDENTITY_REQUIRED | none (1/161) | 161 |  | a different champion is a different run |
| `champion_manifest.champion_id` | IDENTITY_REQUIRED | none (1/161) | 161 |  | a different champion is a different run |
| `champion_manifest.code_commit` | LICENCE_GOVERNED | chunk (2/161) | 161 |  | the run's rev under one of its four spellings |
| `champion_manifest.dirty` | IDENTITY_REQUIRED | none (1/161) | 161 |  | a different champion is a different run |
| `champion_manifest.env_knobs` | IDENTITY_REQUIRED | none (1/161) | 161 |  | a different champion is a different run |
| `champion_manifest.fair_deploy` | IDENTITY_REQUIRED | none (1/161) | 161 |  | a different champion is a different run |
| `champion_manifest.leaf` | IDENTITY_REQUIRED | none (1/161) | 161 |  | a different champion is a different run |
| `champion_manifest.leaf_hashes` | IDENTITY_REQUIRED | none (1/161) | 161 |  | a different champion is a different run |
| `champion_manifest.leaf_value_panel` | IDENTITY_REQUIRED | none (1/161) | 161 |  | a different champion is a different run |
| `champion_manifest.mode` | IDENTITY_REQUIRED | none (1/161) | 161 |  | a different champion is a different run |
| `champion_manifest.provenance_note` | IDENTITY_REQUIRED | none (1/161) | 161 |  | a different champion is a different run |
| `champion_manifest.reshuffle_semantics` | IDENTITY_REQUIRED | none (1/161) | 161 |  | a different champion is a different run |
| `champion_manifest.schema` | IDENTITY_REQUIRED | none (1/161) | 161 |  | a different champion is a different run |
| `champion_manifest.search` | IDENTITY_REQUIRED | none (1/161) | 161 |  | a different champion is a different run |
| `champion_manifest.source` | IDENTITY_REQUIRED | none (1/161) | 161 |  | a different champion is a different run |
| `code_rev` | LICENCE_GOVERNED | chunk (2/161) | 161 |  | the run's rev under one of its four spellings |
| `cost_note` | IDENTITY_REQUIRED | none (1/161) | 161 |  | no merge rule: equal across chunks or RAISE (fail-closed default) |
| `crn` | IDENTITY_REQUIRED | none (1/161) | 161 |  | no merge rule: equal across chunks or RAISE (fail-closed default) |
| `design_doc` | IDENTITY_REQUIRED | none (1/161) | 161 |  | identity-required path |
| `driver` | IDENTITY_REQUIRED | none (1/161) | 161 |  | identity-required path |
| `elapsed_secs_sum` | AGGREGATE_SUM | leg+chunk (161/161) | 161 |  | pure counter |
| `env` | IDENTITY_REQUIRED | none (1/161) | 161 |  | no merge rule: equal across chunks or RAISE (fail-closed default) |
| `errors` | AGGREGATE_UNION | none (1/161) | 161 |  | set-unioned |
| `execution.audit_item` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `execution` ⇒ RAISE |
| `execution.backend` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `execution` ⇒ RAISE |
| `execution.backend_resolution` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `execution` ⇒ RAISE |
| `execution.carc_rs_binary_sha` | PER_CHUNK | chunk (2/161) | 161 |  | BOX-LOCAL — recorded, never compared across hosts (JCZ §0.F.2c) |
| `execution.carc_rs_build` | LICENCE_GOVERNED | chunk (2/161) | 161 |  | cross-host source-rev witness; a cross-tranche divergence is licensed only under D4.13's four conjuncts |
| `execution.carc_rs_path` | PER_CHUNK | chunk (2/161) | 161 |  | BOX-LOCAL — recorded, never compared across hosts (JCZ §0.F.2c) |
| `execution.carc_rs_version` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `execution` ⇒ RAISE |
| `execution.code_rev` | LICENCE_GOVERNED | chunk (2/161) | 161 |  | the run's rev under one of its four spellings |
| `execution.code_rev_dirty` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `execution` ⇒ RAISE |
| `execution.continuation_tree_policy` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `execution` ⇒ RAISE |
| `execution.evidence` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `execution` ⇒ RAISE |
| `execution.gap2_status` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `execution` ⇒ RAISE |
| `execution.gap_status` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `execution` ⇒ RAISE |
| `execution.identity_gate` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `execution` ⇒ RAISE |
| `execution.rust_available` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `execution` ⇒ RAISE |
| `execution.rust_threads` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `execution` ⇒ RAISE |
| `execution.rust_toolchain` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `execution` ⇒ RAISE |
| `execution.rust_unavailable_reason` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `execution` ⇒ RAISE |
| `execution.seam` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `execution` ⇒ RAISE |
| `execution.threads_note` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `execution` ⇒ RAISE |
| `execution.tile_data_semantic_digest` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `execution` ⇒ RAISE |
| `execution.tile_data_source_sha256` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `execution` ⇒ RAISE |
| `generated_utc` | PER_CHUNK | leg+chunk (157/161) | 161 |  | legitimately per chunk |
| `git_rev` | LICENCE_GOVERNED | chunk (2/161) | 161 |  | the run's rev under one of its four spellings |
| `goal` | IDENTITY_REQUIRED | none (1/161) | 161 |  | no merge rule: equal across chunks or RAISE (fail-closed default) |
| `harness` | IDENTITY_REQUIRED | none (1/161) | 161 |  | identity-required path |
| `host` | PER_CHUNK | chunk (2/161) | 161 |  | legitimately per chunk |
| `levels` | IDENTITY_REQUIRED | none (1/161) | 161 |  | no merge rule: equal across chunks or RAISE (fail-closed default) |
| `m_worlds` | IDENTITY_REQUIRED | none (1/161) | 161 | ⚠️ **YES** | identity-required path |
| `max_plies` | IDENTITY_REQUIRED | none (1/161) | 161 |  | identity-required path |
| `n_crn_verified` | AGGREGATE_SUM | leg+chunk (51/161) | 161 |  | pure counter |
| `n_failed` | AGGREGATE_SUM | none (1/161) | 161 |  | pure counter |
| `n_ok` | AGGREGATE_SUM | leg+chunk (51/161) | 161 |  | pure counter |
| `n_playouts` | AGGREGATE_SUM | leg+chunk (51/161) | 161 |  | pure counter |
| `n_rows_in` | AGGREGATE_SUM | leg+chunk (51/161) | 161 |  | pure counter |
| `n_scored` | AGGREGATE_SUM | leg+chunk (51/161) | 161 |  | pure counter |
| `oracle` | IDENTITY_REQUIRED | none (1/161) | 161 |  | no merge rule: equal across chunks or RAISE (fail-closed default) |
| `preflight.m` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `preflight` ⇒ RAISE |
| `preflight.profile` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `preflight` ⇒ RAISE |
| `preflight.seeds` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `preflight` ⇒ RAISE |
| `preflight.wheel.carc_rs_binary_sha` | PER_CHUNK | none (1/161) | 161 |  | box-local; WITHIN-BOX constancy is a standing assertion |
| `preflight.wheel.carc_rs_build` | LICENCE_GOVERNED | chunk (2/161) | 161 |  | the tier1 emitter's spelling of the build stamp |
| `preflight.wheel.carc_rs_file` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `preflight.wheel` ⇒ RAISE |
| `preflight.wheel.carc_rs_version` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `preflight.wheel` ⇒ RAISE |
| `preflight.wheel.ok` | IDENTITY_REQUIRED | none (1/161) | 161 |  | unclassified inside `preflight.wheel` ⇒ RAISE |
| `python` | PER_CHUNK | none (1/161) | 161 |  | legitimately per chunk |
| `replay_game_kwargs` | IDENTITY_REQUIRED | none (1/161) | 161 |  | no merge rule: equal across chunks or RAISE (fail-closed default) |
| `resolved_config.arb_backend` | IDENTITY_REQUIRED | none (1/161) | 161 |  | identity-required path |
| `resolved_config.legal_mask_cache` | IDENTITY_REQUIRED | none (1/161) | 161 | ⚠️ **YES** | identity-required path |
| `resolved_config.m` | IDENTITY_REQUIRED | none (1/161) | 161 | ⚠️ **YES** | identity-required path |
| `resolved_config.m_max` | IDENTITY_REQUIRED | none (1/161) | 161 |  | must agree across chunks or RAISE |
| `resolved_config.max_plies` | IDENTITY_REQUIRED | none (1/161) | 161 |  | must agree across chunks or RAISE |
| `resolved_config.n` | PER_CHUNK | leg+chunk (51/161) | 161 |  | chunk-scoped run config |
| `resolved_config.oracle_policy` | IDENTITY_REQUIRED | none (1/161) | 161 |  | identity-required path |
| `resolved_config.oracle_sims` | IDENTITY_REQUIRED | none (1/161) | 161 |  | must agree across chunks or RAISE |
| `resolved_config.oracle_sims_note` | IDENTITY_REQUIRED | none (1/161) | 161 |  | must agree across chunks or RAISE |
| `resolved_config.out_root` | PER_CHUNK | chunk (16/161) | 161 |  | chunk-scoped run config |
| `resolved_config.out_subdir` | PER_CHUNK | leg (12/161) | 161 |  | chunk-scoped run config |
| `resolved_config.positions_jsonl` | PER_CHUNK | leg+chunk (161/161) | 161 |  | chunk-scoped run config |
| `resolved_config.resume` | PER_CHUNK | none (1/161) | 161 |  | chunk-scoped run config |
| `resolved_config.rules_profile` | IDENTITY_REQUIRED | none (1/161) | 161 |  | identity-required path |
| `resolved_config.strict_crn` | IDENTITY_REQUIRED | none (1/161) | 161 |  | must agree across chunks or RAISE |
| `resolved_config.workers` | PER_CHUNK | leg+chunk (12/161) | 161 |  | chunk-scoped run config |
| `resolved_config.world_deck_witness` | IDENTITY_REQUIRED | none (1/161) | 161 |  | must agree across chunks or RAISE |
| `resolved_config.world_seed_salt` | IDENTITY_REQUIRED | none (1/161) | 161 | ⚠️ **YES** | identity-required path |
| `rules_profile` | IDENTITY_REQUIRED | none (1/161) | 161 |  | identity-required path |
| `sampling` | PER_CHUNK | leg+chunk (140/161) | 161 |  | legitimately per chunk |
| `schema` | IDENTITY_REQUIRED | judge (2/322) | 322 |  | identity-required path |
| `source` | PER_CHUNK | leg+chunk (161/161) | 161 |  | legitimately per chunk |
| `src_root` | IDENTITY_REQUIRED | none (1/161) | 161 |  | no merge rule: equal across chunks or RAISE (fail-closed default) |
| `started_utc` | PER_CHUNK | leg+chunk (19/161) | 161 |  | legitimately per chunk |
| `status` | IDENTITY_REQUIRED | none (1/161) | 161 |  | no merge rule: equal across chunks or RAISE (fail-closed default) |
| `wall_cap_secs` | PER_CHUNK | none (1/161) | 161 |  | legitimately per chunk |
| `wall_secs` | AGGREGATE_SUM | leg+chunk (161/161) | 161 |  | pure counter |
| `workers` | PER_CHUNK | leg+chunk (13/161) | 161 |  | legitimately per chunk |

## Gate-addressed paths named in the READ_RULEs (the CONVERSE check)

- **`RUN_MANIFEST`**: `arb_backend`, `arb_legal_mask_cache`, `b_ceiling_from_m`, `c_remeasure.failed_smokes`, `c_remeasure.halt_fired`, `c_remeasure.legs.arb.committed`, `c_remeasure.legs.arb.halt_fired`, `c_remeasure.legs.arb.ratio`, `c_remeasure.legs.arb.realized`, `c_remeasure.legs.generation.committed`, `c_remeasure.legs.generation.halt_fired`, `c_remeasure.legs.generation.ratio`, `c_remeasure.legs.generation.realized`, `c_remeasure.legs.if.committed`, `c_remeasure.legs.if.halt_fired`, `c_remeasure.legs.if.ratio`, `c_remeasure.legs.if.realized`, `c_remeasure.ok`, `m_worlds`, `preflight.checks.leaf_hash.ok`, `resolved_backend_by_leg`, `world_seed_salt`
- **`leg`**: `preflight.seeds.ok`, `preflight.seeds.prefix_stable_at`, `resolved_config.legal_mask_cache`, `resolved_config.m`, `resolved_config.world_seed_salt`

✅ Every gate-addressed path named in the READ_RULEs EXISTS in the enumerated schema.

---

*Measurement plumbing only: this sweep opens no record, computes no statistic, and writes nothing under the prereg dir.*
