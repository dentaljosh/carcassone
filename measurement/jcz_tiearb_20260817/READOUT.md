# READOUT — jcz_tiearb_20260817: JCZ out-of-lineage pricing of the tie arbiter

> Adjudicates [`measurement/jcz_tiearb_20260817/READ_RULE.md`](READ_RULE.md) (design: [`measurement/jcz_tiearb_20260817/DESIGN.md`](DESIGN.md)). **Blind ordering: the read-rule and this adjudicator were committed before game 1.** The branch is taken VERBATIM.

## BRANCH: `U-UNREADABLE` — UNREADABLE — a §3 precondition failed.

No strength statistic from this run is adjudicated, quoted, or entered in results.csv as a verdict. The failed gate is named with its realized value. U-UNREADABLE is a FULLY ACCEPTABLE OUTCOME. ⚠️ §4.3's companion table is still printed in full below — which makes the session that reads it NON-BLIND, so per READ_RULE §4 any instrument fix must be written by a session that has NOT seen the strength statistics and must be decidable from gate inputs alone. Bars do not move. §4 is not edited.

**FAILED PRECONDITIONS: G-TOOL**

> a §3 precondition failed

`D = +3.3525` pts/game · `se(D) = 0.8433` · `z_D = +3.9753` · `n_common = 400` decks

READ_RULE §5: No branch flips governance/PRODUCTION.yaml. No branch licenses an on-device deploy. No branch licenses a change to B, J, the tie predicate, the salt, or the playout. No branch licenses a second cell. No branch makes any claim about superhuman strength.

## §4.3 item 1 — per cell

| | CELL A `jcz_CHAMP_deploy11008` | CELL B `jcz_ARB_B16J4_deploy11008` |
|---|---|---|
| archive | jcz_CHAMP_deploy11008.jsonl | jcz_ARB_B16J4_deploy11008.jsonl |
| n games (records / scored) | 800 / 800 | 800 / 800 |
| n decks (seat-balanced) | 400 | 400 |
| half-pair decks (excluded) | 0 | 0 |
| seat balance (champ_seat: n) | {1: 400, 0: 400} | {1: 400, 0: 400} |
| W/D/L | 504/15/281 | 551/12/237 |
| win rate (z) | 0.6394 (+7.88) | 0.6963 (+11.10) |
| elo ±1σ (within-band) | +99.5 ± 12.3 | +144.1 ± 12.3 |
| elo 95% CI | [+75.4, +123.6] | [+120.0, +168.2] |
| deck-paired margin ± se (z) | +6.6225 ± 0.6320 (+10.478) | +9.9750 ± 0.5867 (+17.001) |
| per-seat mean margin | {0: 9.385, 1: 3.86} | {0: 12.635, 1: 7.315} |
| n_failed (voids) / rate | 0 / 0.0000 | 0 / 0.0000 |

## §4.3 item 1b — the TWO-BOX block (owner ruling §0.F.1: "make sure its both boxes, w22 and w30 respectively")

- hosts that PLAYED (derived from the records): `Doctor`, `laptop-wsl` · expected: `Doctor`, `laptop-wsl`
- WORKERS.conf: `W_LOCAL=30` · `W_LAPTOP=22` · `DECKS_LOCAL=215` · `DECKS_LAPTOP=185` · `LAPTOP_HOST=laptop-wsl`

| cell | host | deck range played | n games | n decks | `ms_per_move_champ` (OURS) | worker-s/game |
|---|---|---|---|---|---|---|
| `jcz_CHAMP_deploy11008` | `Doctor` | 133000000000..133000000214 | 430 | 215 | 2014.3 ms | 154.4 |
| `jcz_CHAMP_deploy11008` | `laptop-wsl` | 133000000215..133000000399 | 370 | 185 | 1726.0 ms | 132.4 |
| `jcz_ARB_B16J4_deploy11008` | `Doctor` | 133000000000..133000000214 | 430 | 215 | 4853.6 ms | 353.8 |
| `jcz_ARB_B16J4_deploy11008` | `laptop-wsl` | 133000000215..133000000399 | 370 | 185 | 4331.2 ms | 317.1 |

- `jcz_CHAMP_deploy11008` deck→host source: **hostmap** (sidecar `jcz_CHAMP_deploy11008.hostmap.json`, parsed=True, shape=hostmap.deck_seed -> host) · decks per host: {'Doctor': 215, 'laptop-wsl': 185}
- `jcz_ARB_B16J4_deploy11008` deck→host source: **hostmap** (sidecar `jcz_ARB_B16J4_deploy11008.hostmap.json`, parsed=True, shape=hostmap.deck_seed -> host) · decks per host: {'Doctor': 215, 'laptop-wsl': 185}

- **`G-SPLIT` ✅ PASS** — deck→host assignment IDENTICAL across both cells over 400 common decks · mismatched decks: 0  · decks with NO host in either cell: 0 
- **`G-COVER` ✅ PASS** — per cell: `jcz_CHAMP_deploy11008` dups 0, out-of-band 0, decks missing a seating 0 · `jcz_ARB_B16J4_deploy11008` dups 0, out-of-band 0, decks missing a seating 0
  - G-N owns VOLUME (its committed 80% floor: n_common >= 320 decks, >= 640 games/cell) and G-COVER owns SHAPE. G-COVER is therefore evaluated over what the cell CLAIMS to cover: no duplicate (deck_seed, champ_seat, replicate), no seed outside the cell's own record-derived band window, and BOTH seatings present for every deck that is present. A partial run fails G-N on volume rather than G-COVER on absence — the alternative reading would repeal G-N's floor and void every healthy-but-short run (READ_RULE §3.1's defect class).

| host | JVM version string (REPORTED — NEVER a branch input) |
|---|---|
| `Doctor` | (absent) |
| `laptop-wsl` | (absent) |

⚠️ THE JVM *PACKAGING* DIFFERS BY HOST — `17.0.19+10-1-24.04.2-Ubuntu` locally vs `+10-1-26.04.2-Ubuntu` on the laptop, the SAME OpenJDK 17.0.19 on a different distro base (DESIGN §0.1). It is **REPORTED HERE AND IS NEVER A BRANCH INPUT**: the PINNED artifacts are the jar (sha256, verified on each host) and the shim CLASSES (copied, not rebuilt — byte-identical bytecode on both hosts), and both are gated. The runtime difference cannot touch `D` because `G-SPLIT` holds the deck→host map IDENTICAL across the two cells, so every per-box effect is common to both terms of `margin_B(d) − margin_A(d)` and cancels exactly (DESIGN §0.1.2).

DESIGN §0.1.2: `D` is deck-paired, so a deck that ran on different boxes in the two cells puts every per-box difference (JVM packaging, W and hence contention, RAM) INSIDE `margin_B(d) − margin_A(d)`, arithmetically indistinguishable from the arbiter's effect. With the split identical, every per-box effect is common to both terms and CANCELS EXACTLY.

## §4.3 item 2 — `D`, its se, `z_D`, `n_common`, the diagnostic, and the resolving `n`

- **`D = M_B − M_A = +3.3525` pts/game**, deck-paired over `n_common = 400` decks (seeds 133000000000..133000000399)
- `se(D) = 0.8433` · **`z_D = +3.9753`** (convention: `eval_fair_puct._paired_z`)
- on the common decks: `M_A = +6.6225` · `M_B = +9.9750`
- DIAGNOSTIC ONLY — naive difference of the two cell summaries: `+3.3525`. **The branch uses the deck-paired `D`.**
- **the `n` (DECKS/cell) that would resolve `D` to 2σ at the realized dispersion: 102** (`n · (2/|z_D|)²`; `None` when `z_D` is absent, NaN or exactly zero)
- committed power (DESIGN §4.2, before any number): se(D) assumed 0.86 ⇒ 2σ conviction floor |D| = 1.72 pts/game; §4.3's unfunded ladder: D=+1.00 needs 1183 decks/cell, D=+1.50 needs 526
- §1 WITNESS (never a branch input): analyzer-path `z_D` = +3.975340, independently recomputed `z_D` = +3.975340 — agreement: `G-WITNESS` PASS (tolerance 1e-09 relative)

## §4.3 item 3 — CELL B arbiter telemetry

| quantity | realized | reference |
|---|---|---|
| `phi` (fired tied tile plies / game) | 19.1938 | offline prior **22.96**, Stage-2 realized **17.573** |
| `error_rate_on_fired` | 0.000000 | — |
| **`phi_effective`** (G-FIRE binds here) | 19.1938 | floor **1.0** |
| `pickchanges` | 9365.0 | — |
| `arms_total` | 52208.0 | — |
| `playouts_total` | 835328.0 | — |
| `tiearb_errors_total` | 0.0 | — |
| `tiearb_first_error` | None | — |
| `tile_plies_total` | 27578.0 | — |
| games with telemetry | 800 / 800 | — |

## §4.3 item 4 — cost (`ms_ratio`), and DESIGN §6.2's prediction vs realized

⚠️ THE FIELD-NAME TRAP (READ_RULE §0.C): in `eval_fair_puct`, `champ_prefix_ms_per_move` is the CANDIDATE side, the opposite of `eval_puct_priors`. ⭐ IN **THIS** HARNESS (`scripts/jcz_match/`) THE FIELDS ARE `ms_per_move_champ` = OUR SIDE (the champion, ± the arbiter) and `ms_per_move_jcz` = JCZ, THE OPPONENT. `ms_ratio = ms_per_move_champ / ms_per_move_jcz` is ours-over-theirs. Do NOT import eval_fair_puct's inverted convention: a read-out that swaps them INVERTS the reading.

- fields read: **OUR side = `ms_per_move_champ`**, **opponent = `ms_per_move_jcz`**
- CELL A `ms_ratio` = 13.5821 (`ms_per_move_champ` 1881.0 ms / `ms_per_move_jcz` 138.5 ms)
- CELL B `ms_ratio` = 33.5903 (`ms_per_move_champ` 4612.0 ms / `ms_per_move_jcz` 137.3 ms)
- **DESIGN §6.2 PREDICTED: CELL B ≈ 2.71× CELL A per game, 266.0 worker-s/game** (CELL A 98.1 worker-s/game)
- REALIZED: CELL A 144.2 worker-s/game · CELL B 336.8 worker-s/game · **B/A = 2.335×** (per-move `ms_ratio` B/A = 2.473×)

READ_RULE §0.A (OWNER RULING, inherited from Stage-2 §0.D), verbatim: "we can afford some wallclock during play, especially if its not every tile draw. dont let that be the constraint right now." ⇒ `ms_ratio` and every wall-clock quantity are MEASURED AND REPORTED on every branch and are NEVER a branch input. WAIVED: the consequence. NOT WAIVED: the measurement. ⛔ ANTI-GAMING (binding): permission to spend clock is never licence to reshape the arbiter to look cheaper — B stays 16 and may not be expanded, the tie predicate is not narrowed, and there is no playout truncation for cost reasons.

## §4.3 item 5 — every §3 gate, its realized value, and which address resolved

| gate | PASS | key realized evidence |
|---|---|---|
| `G-BAND` | ✅ | {"declared_band": 133000000000, "band_claim": {"path": "/home/doctor/projects/carcassone/measurement/jcz_tiearb_20260817/BAND_CLAIM.txt", "exists": true, "band": 133000000000, "claimed_at": 1787012053.3272333, "claimed_at_source": "file mtime", "raw": "133000000000\njcz_tiearb_20260817\nclaimed 2026-08-17\n"}, "claimed_before_game_1": true, "sentinel_timestamp": 1787012053.3272333, "sentinel_timestamp_source": "file mtime", "earliest_finished_at": 1787012204.059709, "decks_per_cell_declared": 400, "per_cell": {"jcz_CHAMP_deploy11008": {"n_decks": 400, "deck_seed_min": 133000000000, "deck_seed_… |
| `G-LEAF` | ✅ | {"expected_equal": "a36d2e15a3b3d71d", "observed": {"jcz_CHAMP_deploy11008": {"cand_leaf_hash": "a36d2e15a3b3d71d", "resolved_at": "champion_manifest.leaf_hashes.harness_leaf_hash", "consistent_across_records": true, "distinct": [{"value": "a36d2e15a3b3d71d", "resolved_at": "champion_manifest.leaf_hashes.harness_leaf_hash", "n_records": 800}], "ok": true}, "jcz_ARB_B16J4_deploy11008": {"cand_leaf_hash": "a36d2e15a3b3d71d", "resolved_at": "champion_manifest.leaf_hashes.harness_leaf_hash", "consistent_across_records": true, "distinct": [{"value": "a36d2e15a3b3d71d", "resolved_at": "champion_mani… |
| `G-SPLIT` | ✅ | {"n_common_decks_compared": 400, "mismatched_decks": {"n_total": 0, "listed": [], "truncated": false, "list_cap": 20}, "decks_with_no_host_in_either_cell": {"n_total": 0, "listed": [], "truncated": false, "list_cap": 20}, "unparseable_hostmap": null, "intra_cell_host_conflicts": null, "per_cell": {"jcz_CHAMP_deploy11008": {"host_source_resolved": "hostmap", "n_decks_from_hostmap": 400, "n_decks_from_record_stamps": 0, "hostmap": {"searched": ["jcz_CHAMP_deploy11008.hostmap.json", "jcz_CHAMP_deploy11008.jsonl.hostmap.json", "/home/doctor/projects/carcassone/measurement/jcz_tiearb_20260817/jcz_C… |
| `G-COVER` | ✅ | {"per_cell": {"jcz_CHAMP_deploy11008": {"n_scored": 800, "n_decks": 400, "band_derived_from_records": 133000000000, "band_window": [133000000000, 133000000399], "duplicate_deck_seat_replicate": {"n_total": 0, "listed": [], "truncated": false, "list_cap": 20}, "out_of_band_deck_seeds": {"n_total": 0, "listed": [], "truncated": false, "list_cap": 20}, "decks_without_both_seatings": {"n_total": 0, "listed": [], "truncated": false, "list_cap": 20}, "n_games_if_complete": 800, "ok": true}, "jcz_ARB_B16J4_deploy11008": {"n_scored": 800, "n_decks": 400, "band_derived_from_records": 133000000000, "ban… |
| `G-ARB` | ✅ | {"expected_rung": {"enabled": true, "B": 16, "J": 4, "mode": "argmax", "salt": "tiearb2-deploy-v1", "eps": 0.0}, "cell_b": {"resolved": {"enabled": true, "B": 16, "J": 4, "mode": "argmax", "salt": "tiearb2-deploy-v1", "eps": 0.0}, "resolved_at": {"enabled": "champion_manifest.cand_tiearb", "B": "champion_manifest.cand_tiearb", "J": "champion_manifest.cand_tiearb", "mode": "champion_manifest.cand_tiearb", "salt": "champion_manifest.cand_tiearb", "eps": "champion_manifest.cand_tiearb"}, "checks": {"enabled": {"expected": true, "observed": true, "resolved_at": "champion_manifest.cand_tiearb", "ok… |
| `G-FIRE` | ✅ | {"phi": 19.19375, "phi_effective": 19.19375, "error_rate_on_fired": 0.0, "fired_plies_total": 15355.0, "fired_field_used": "fired_plies", "errors_total": 0.0, "games_denominator": 800, "n_games_with_telemetry": 800, "floor": 1.0, "binds_on": "phi_effective", "formula": "phi = fired_plies_total / games; phi_effective = phi * (1 - error_rate_on_fired)", "offline_prior_phi": 22.96, "stage2_realized_phi": 17.573} |
| `G-J13` | ✅ | {"verdicts_dir": "/home/doctor/projects/carcassone/measurement/jcz_tiearb_20260817/verdicts", "hosts": {"Doctor": {"pick_changed": true, "root_leaf_value_bits_unchanged": true, "all_preflight_pass": true, "path": "/home/doctor/projects/carcassone/measurement/jcz_tiearb_20260817/verdicts/PREFLIGHT_Doctor_FIRST.json", "parse_error": null, "ok": true}, "laptop-wsl": {"pick_changed": true, "root_leaf_value_bits_unchanged": true, "all_preflight_pass": true, "path": "/home/doctor/projects/carcassone/measurement/jcz_tiearb_20260817/verdicts/PREFLIGHT_laptop-wsl_FIRST.json", "parse_error": null, "ok":… |
| `G-RULES` | ✅ | {"expected_rules_profile": "fixed_v1", "expected_r9_env": "1", "observed": {"jcz_CHAMP_deploy11008": {"rules_profile": "fixed_v1", "rules_profile_resolved_at": "rules_profile", "r9_env": "1", "r9_env_resolved_at": "r9_env", "r9_env_ok_advisory": true, "consistent_across_records": true, "ok": true}, "jcz_ARB_B16J4_deploy11008": {"rules_profile": "fixed_v1", "rules_profile_resolved_at": "rules_profile", "r9_env": "1", "r9_env_resolved_at": "r9_env", "r9_env_ok_advisory": true, "consistent_across_records": true, "ok": true}}} |
| `G-DIVERGE` | ✅ | {"final_agree_floor": 0.99, "observed": {"jcz_CHAMP_deploy11008": {"real_total": 0, "real": {}, "classified_counts": {"UNPLACEABLE_REDRAW": 46}, "n_scored": 800, "final_agree_n": 800, "final_agree_frac": 1.0, "replay_ok_all": true, "ok": true}, "jcz_ARB_B16J4_deploy11008": {"real_total": 0, "real": {}, "classified_counts": {"UNPLACEABLE_REDRAW": 36}, "n_scored": 800, "final_agree_n": 800, "final_agree_frac": 1.0, "replay_ok_all": true, "ok": true}}, "benign_classes": ["WALL_LEGALITY", "UNPLACEABLE_REDRAW"], "note": "`WALL_LEGALITY` (the bounded 25\u00d725 action window running out before the 3… |
| `G-JCZ` | ✅ | {"expected": {"jcz_git_rev": "29a156154c75ad7bf5a3af6e2e5db3eaeb1af76a", "jcz_ai_class": "com.jcloisterzone.ai.AiEngine", "tile_set": "basic:2", "jcz_jar_sha256": "4dc5439dbf228b1360b0b1987f5e90454c4a6ac434a8509be4d2c089f9671190", "ai_player": "LegacyAiPlayer"}, "observed": {"jcz_CHAMP_deploy11008": {"checks": {"jcz_git_rev": {"observed": "29a156154c75ad7bf5a3af6e2e5db3eaeb1af76a", "expected": "29a156154c75ad7bf5a3af6e2e5db3eaeb1af76a", "resolved_at": "jcz_git_rev", "ok": true, "matches_pin": true, "records_agree": true, "values_seen": ["29a156154c75ad7bf5a3af6e2e5db3eaeb1af76a"], "records_wit… |
| `G-TOOL` | ❌ **FAIL** | {"cross_host_build_identity": {"preflight_build_id_by_host": {"Doctor": "carc_rs-0.1.0+a8b6cf87000d+rustc1.96.0", "laptop-wsl": "carc_rs-0.1.0+a8b6cf87000d+rustc1.96.0"}, "preflight_binary_sha_by_host": {"Doctor": "a4318fd59d9d8349", "laptop-wsl": "8ae0b98427debb2e"}, "build_id_equal_across_hosts": true, "build_id_witness_present": true, "binary_sha_equal_across_hosts": false, "binary_sha_equal_across_hosts_IS_NON_BINDING": true, "binary_sha_cross_host_note": "\u26d4 REPORTED, NEVER BINDING (READ_RULE \u00a70.F.2c). `carc_rs_binary_sha` is BOX-LOCAL staleness evidence and is NEVER compared acr… |
| `G-N` | ✅ | {"n_common": 400, "n_common_floor": 320, "n_common_units": "DECKS (\u00a72)", "n_games_scored": {"CELL_A": 800, "CELL_B": 800}, "cell_games_floor": 640, "cell_games_planned": 800, "deck_clause_independently_binding": "two cells can each clear 640 games while overlapping on fewer than 320 COMMON decks \u2014 that weakens D and still voids"} |
| `G-PLY` | ✅ | {"per_cell": {"jcz_CHAMP_deploy11008": {"n_scored": 800, "n_with_ply_witness": 800, "witness": "moves_by_seat\|moves + n_actions", "ok": true}, "jcz_ARB_B16J4_deploy11008": {"n_scored": 800, "n_with_ply_witness": 800, "witness": "moves_by_seat\|moves + n_actions", "ok": true, "arbiter_ply_witness": {"tile_plies_total": 27578.0, "partial_argmax_total": 0.0, "telemetry_on_every_game": true, "ok": true, "semantics": "Stage-2 \u00a70.F verbatim: partial_argmax ABSENT is unknown-not-zero and FAILS; NON-ZERO means an argmax was taken over a partial world set (CRN pairing broken during play) and FAIL… |
| `G-WITNESS` | ✅ | {"tolerance_relative": 1e-09, "fields": {"D": {"analyzer_path": 3.3525, "recomputed": 3.3525, "agree": true}, "se_D": {"analyzer_path": 0.8433240617091654, "recomputed": 0.8433240617091654, "agree": true}, "z_D": {"analyzer_path": 3.9753401476598285, "recomputed": 3.9753401476598285, "agree": true}, "n_common": {"analyzer_path": 400, "recomputed": 400, "agree": true}}, "semantics": "\u00a71 \u2014 the recomputation is a WITNESS, never a branch input; disagreement beyond float tolerance is U-UNREADABLE"} |

### `G-TOOL` — the four conjuncts (§0.F.2b + §0.F.2c)

1. CROSS-HOST build identity (pre-flights vs pre-flights ONLY), **BINDING ON `carc_rs_build` (THE BUILD ID) ALONE**: build id by host {'Doctor': 'carc_rs-0.1.0+a8b6cf87000d+rustc1.96.0', 'laptop-wsl': 'carc_rs-0.1.0+a8b6cf87000d+rustc1.96.0'} · equal = True · witness present = True · **conjunct ok = True** — **MIXED BUILDS ACROSS BOXES FAIL**
   - binary sha by host {'Doctor': 'a4318fd59d9d8349', 'laptop-wsl': '8ae0b98427debb2e'} · equal = False — **NON-BINDING, REPORTED ONLY**
   - ⛔ REPORTED, NEVER BINDING (READ_RULE §0.F.2c). `carc_rs_binary_sha` is BOX-LOCAL staleness evidence and is NEVER compared across boxes: the `.so` is NOT reproducible across machines. Measured on THIS pair of boxes at the SAME `carc_rs_build` — `a4318fd59d9d8349` (Doctor) vs `8ae0b98427debb2e` (laptop-wsl) — so a cross-host equality conjunct on the sha would void EVERY healthy two-box run. ACROSS HOSTS the binding witness is `carc_rs_build` (the build id, machine-independent by construction); WITHIN a host the sha binds across the two cells (conjunct 1b), which is its true meaning.
1b. WITHIN-HOST staleness — `carc_rs_binary_sha` across the two cells, host via the hostmap: hosts evaluated ['Doctor', 'laptop-wsl'] · per host {'Doctor': {'per_cell': {'jcz_CHAMP_deploy11008': ['"a4318fd59d9d8349"'], 'jcz_ARB_B16J4_deploy11008': ['"a4318fd59d9d8349"']}, 'mixed_within_a_cell': False, 'equal_across_cells': True, 'ok': True, 'n_cells_with_witness': 2}, 'laptop-wsl': {'per_cell': {'jcz_CHAMP_deploy11008': ['"8ae0b98427debb2e"'], 'jcz_ARB_B16J4_deploy11008': ['"8ae0b98427debb2e"']}, 'mixed_within_a_cell': False, 'equal_across_cells': True, 'ok': True, 'n_cells_with_witness': 2}} · present = True · **ok = True** (a sha that MOVED within a host between cells FAILS)
2. CROSS-CELL code identity (`our_git_rev` → `champion_manifest.code_commit`): equal across cells = False · `jcz_CHAMP_deploy11008` = a8b6cf87000d2a4110cd5399a84e39fa29e8464b (at `our_git_rev`, consistent=False) · `jcz_ARB_B16J4_deploy11008` = 2eab07d5a6d475bba05b4997f763c1c1704cdf5d (at `our_git_rev`, consistent=False)
3. the commit range — below. Any build witness present at all: True (ABSENT AT EVERY SOURCE STILL FAILS).

#### the commit-range delta, on its own line

- pre-flight commit `a8b6cf87000d2a4110cd5399a84e39fa29e8464b` .. manifest commit `a8b6cf87000d2a4110cd5399a84e39fa29e8464b`
- command: `(none — degenerate range)`
- output: `(empty)`
- **DEGENERATE RANGE — the pre-flight and the manifest name the same commit, so no wheel-relevant path can have changed**
- DISPOSITIVE IN ONE DIRECTION: a NON-EMPTY or UNRESOLVED wheel-relevant diff VOIDS; an EMPTY diff or a degenerate range PASSES (READ_RULE §3.1 — the fix for Stage 2's unsatisfiable-by-construction gate).

## §4.3 item 6 — fail-soft dilution (READ_RULE §0.B)

CELL B `tiearb_errors_total` = **0.0**

`tiearb_errors_total` is 0 or unknown, so §0.B's verbatim dilution statement is not triggered by errors. The ASYMMETRY still holds and is restated: CELL A has no arbiter to fail, so any fail-soft dilutes `D` toward zero — a positive `D` is a lower bound and a null is weaker evidence of absence. (An UNKNOWN error count is itself a `G-FIRE` failure: absent is fail.)

## ⭐ §4.3 item 7 — CELL A's ABSOLUTE RESULT vs JCZ (printed on EVERY branch, `U-UNREADABLE` included)

| | CELL A, THIS RUN | 2026-08-09 reading |
|---|---|---|
| elo | **+99.5** ± 12.3 (1σ) | **+111.4** |
| win rate | **0.6394** | **0.655** |
| deck-paired margin | **+6.6225 ± 0.6320** (z +10.478) over 400 decks | **+6.5 ± 0.86** over 200 decks |
| band / rev | see `G-BAND` | 1.08e+11 / `9c4bb50` |

**Δelo vs the 2026-08-09 reading: -11.9**

⚠️ CROSS-BAND CONTRAST (this band vs 1.08e11, at a different code era): CLAUDE.md's over-dispersion rider applies — σ inflates ≈1.8-2.2×, so ±17.4 elo becomes ≈±31-38 elo on this contrast. It is a REGRESSION TRIPWIRE, not a precision comparison. D — the primary statistic — is WITHIN-band and deck-matched, i.e. the robust class, and is unaffected.

DESIGN §3.2: the champion's out-of-lineage strength is a finding independent of D, and it is the single thing an out-of-lineage anchor exists to catch.

## §4.3 item 8 — the divergence ledger, by class, for both cells

| cell | classified `counts` | REAL |
|---|---|---|
| `jcz_CHAMP_deploy11008` | {'UNPLACEABLE_REDRAW': 46} | {} |
| `jcz_ARB_B16J4_deploy11008` | {'UNPLACEABLE_REDRAW': 36} | {} |

`WALL_LEGALITY` (the bounded 25×25 action window running out before the 35×35 grid — it only ever ADDS options on JCZ's side, boards stay identical, and both affected 2026-08-09 games carried final_agree=True) and `UNPLACEABLE_REDRAW` (both engines discarded and redrew in lockstep; the divergent form `UNPLACEABLE_TURN_LOSS` fired 0 times) are the TWO CLASSIFIED-BENIGN classes, DESIGN §2.1. ⛔ ANY entry in a record's `real` ledger is a REAL divergence and VOIDS the run through `G-DIVERGE` — it is never re-classified here.

## Provenance

- WORKERS.conf parsed: **True** (`/home/doctor/projects/carcassone/measurement/jcz_tiearb_20260817/WORKERS.conf`)
- deck pairing: `scripts/jcz_match/analyze.py` imported = **True** (/home/doctor/projects/carcassone/scripts/jcz_match/analyze.py)
- band sentinel: `/home/doctor/projects/carcassone/measurement/jcz_tiearb_20260817/BAND_CLAIM.txt` · verdicts: `/home/doctor/projects/carcassone/measurement/jcz_tiearb_20260817/verdicts` · repo: `/home/doctor/projects/carcassone`

