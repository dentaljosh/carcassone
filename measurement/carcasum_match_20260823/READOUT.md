# Carcasum external-reference match — READOUT (mechanical adjudication)

Adjudicated 2026-08-23 against the frozen prereg. Executed READ_RULE mechanically; no
reinterpretation. Ambiguities in the frozen text are flagged, not resolved, in §6.

## 0. Provenance of the frozen rule

- Prereg text read via `git show 35f3c6da:measurement/carcasum_match_prep/PREREG.md` (no
  checkout). This is the blind-commit sha named in the task, and its diff vs the immediately
  preceding commit (`225e2175`, `PREREG_DRAFT.md` → `PREREG.md` rename) is exactly 4 lines:
  the FROZEN banner and the D-first branch-order clarification. Nothing else in the ~370-line
  document changed at freeze — the design was locked well before this diff.
- `carcasum-match-freeze` branch tip is a *later* commit, `f5a7c73` ("claim band 142e9"),
  which only touches `governance/BAND_REGISTRY.csv` + `BAND_CLAIM.json` — band claim, not
  part of the frozen read rule itself.
- Also read at `35f3c6da`: `AUDIT_PLAN.md` (gate 5, the divergence-audit spec) and
  `LAUNCH_PROCEDURE.md` (says to read results via `scripts/carcasum_match/match.py`'s own
  `summarize()`). Both are consistent with PREREG.md §5 and add no independent statistic.
- Analyzer used: `scripts/carcasum_match/match.py::summarize()` extracted from the **same
  frozen commit** (`git show 35f3c6da:scripts/carcasum_match/match.py`) into the scratchpad —
  **not** the working-tree copy, which is dirty/different because the repo is currently on
  `tiearb2-stage2`, a different branch (diff confirmed: working-tree version is missing the
  `opp_driver_ms`/`opp_driver_playouts` telemetry fields present in the frozen version).

## 1. Data provenance

| item | value |
|---|---|
| source | `laptop-wsl:/home/doctor/projects/carcassone/measurement/carcasum_match_20260823/games.jsonl` |
| games.jsonl sha256 (remote, `ssh laptop-wsl sha256sum`) | `9af5cd296cb8373971b4ebee81694b27105bfac54361651802653f48e9ae8ec6` |
| games.jsonl sha256 (local copy, post-scp) | `9af5cd296cb8373971b4ebee81694b27105bfac54361651802653f48e9ae8ec6` — **matches, transfer verified** |
| record count | 400 lines / 400 records (`wc -l` and JSON parse agree) |
| driver.log | fetched alongside; embeds `match.py`'s own end-of-run `summarize()` JSON, used as a cross-check, not the primary computation |
| binary sha256 (driver.log header, "PRIMARY provenance witness") | `c090847e1befa007e9b3b3031a9c880a60915e36f143aa6c3c30691599792968` |
| binary sha256 (per-record `manifest.carcasum_binary_sha256`, all 400) | identical, matches driver.log header |
| champion leaf hash (per-record `manifest.champion_manifest.leaf_hashes`) | `harness_leaf_hash=a36d2e15a3b3d71d`, `frozen_config_hash_meeple_k0=6dfffd57051690f2`, `frozen_config_hash_meeple_k2=158f17ff76adaa02` — **all three match `governance/PRODUCTION.yaml`'s `leaf_hash_dialects` exactly**, champion_id `puct_priors_v29_bmild_cap8` matches `PRODUCTION.yaml`'s `champion.id`, `k_dets=8`/`sims_per_det=1376` matches the `desktop` deploy profile (the champion of record) |
| champion `verify=True` | confirmed in frozen `match.py::_make_champion` — hardcoded on the non-audit path, not a runtime knob, so nothing to check per-record |
| rules profile | `fixed_v1`, `r9_env_expected=True`, `r9_env_observed=True`, `r9_env_ok=True` on every record — matches prereg §2 |
| driver patches | `[R1_tiny_city_modern, B1_revision_pin, B2_qdatastream_include, B3_cmath_include, B4_assert_guard, B5_count_playouts, B6_game_score_detail_accessor, B7_citynode_bonus_accessor, B8_driver_target]` — identical on all 400 records |
| opponent config (`manifest.carcasum_driver_players`) | `MCTSPlayer<PortionUtility, RandomPlayout>(reuseTree=0, m=5000, mIsTimeout=1, Cp=0.5, nodePriors=0, progressiveWidening=0, progressiveBias=0)` on all 400 records — matches prereg §2 exactly. (Manifest has exactly 2 distinct blobs across the 400 records; the only differing field is the order of `["external", "MCTS..."]` vs `["MCTS...", "external"]` in `carcasum_driver_players`, i.e. which seat is listed first — cosmetic, driven by `champ_seat`, not a config drift.) |
| band | `142000000000`–`142000000199` (200 decks × 2 seats), matching the frozen band plan exactly; the reserved top-up range `142000000200`–`142000000299` was **not** touched (consistent with branch A firing, not C) |

## 2. Gate execution, in frozen order (D first)

### Gate D — void-contaminated: `voids or REAL divergences > 1% of games`

| check | measured | source |
|---|---|---|
| `n_records` | 400 | `summarize()` |
| voids (`void` field non-null) | **0 / 400 (0%)** | independent scan of every record |
| voids breakdown (`summarize()["voids"]`) | `{}` (empty) | `summarize()` |
| REAL divergences (`real` field non-empty) | **0 / 400 (0%)** | independent scan of every record's `real` dict |
| `final_agree` (engine/driver final-score agreement) | **True on 400/400** | independent scan |
| farm agreement (`farm_points_ours == farm_points_theirs`) | **match on 400/400** | independent scan |
| `replay_ok` | **True on 400/400** | independent scan, matches `summarize()["replay_failures"] == []` |
| champ_seat balance | seat 0: 200, seat 1: 200 | independent scan |
| deck coverage | 200 unique deck seeds, each appearing exactly twice (once per seat) — no gaps, no repeats | independent scan |

**D does not fire. 0% ≤ 1% on both void and REAL-divergence counts, by a wide margin (literally zero of either).** The one-time divergence audit (gate 5 of the build, `measurement/carcasum_audit_20260823/AUDIT_READOUT.md`, PASS 50/50) is corroborated, not merely assumed: the rated match's own per-game telemetry independently shows zero REAL divergences and zero voids across all 400 games.

### Branch table (A → B → C, first match after D)

Estimator of record, per PREREG §1 / §5: `d` = deck-paired margin in points (`paired_margin_mean` in `summarize()`), `z = d / SE(d)` (`paired_margin_sem`), over 200 paired decks.

| statistic | value |
|---|---|
| `n_paired_decks` | 200 |
| `d` (paired_margin_mean) | **4.08 points** |
| `SE(d)` (paired_margin_sem) | 0.97720 |
| `z` | **4.1752** |
| `\|z\|` | 4.1752 |

**`\|z\| ≥ 3` → Branch A fires.**

> **Frozen text, branch A, quoted verbatim:** "**A — usable reference** \| `\|z\| ≥ 3` \| Report the sign and size. Carcasum enters the ruler set at this budget. Queue rung 2 (the budget ladder) to find the budget where it equals the champion — *that*, not this cell, is the non-saturating-ruler deliverable."

Sign and size, per the branch's instruction: the champion **beats** Carcasum's `MCTSPlayer<PortionUtility,RandomPlayout>@5000ms/turn, Cp=0.5` by **+4.08 points/deck (paired), z=4.18, n=400 (200 decks × 2 seats)**. Positive margin = champion favored.

(Branch B and C conditions are not evaluated further — first-match-wins per the frozen branch-order clarification, and A already fired.)

## 3. Full statistics defined by the read rule

| statistic | value | definition source |
|---|---|---|
| n_records / n_scored | 400 / 400 | §5 sample |
| wins / draws / losses (champion side) | 223 / 9 / 168 | `summarize()` |
| win_rate (draws = 0.5) | 0.56875 | `summarize()` |
| elo_from_win_rate | **48.08** | `summarize()`, `-400·log10(1/wr − 1)` |
| secondary σ (win-rate→elo), within-band n=400 formula | ±17.375 (`695·√(0.25/400)`) | PREREG §1, "n=400 ⇒ ±17.4 elo" |
| paired_margin_mean (`d`) | **4.08 pts** | PREREG §1, estimator of record |
| paired_margin_sem (`SE(d)`) | 0.97720 | PREREG §1 |
| z = d/SE(d) | **4.1752** | PREREG §1 / §5 |
| mean_margin_unpaired | 4.08 pts (identical to paired mean here) | `summarize()` |
| 95% CI on d (±1.96·SE, informational — not itself a read-rule quantity) | [2.16, 6.00] pts | derived |
| champ_ms_per_move_mean | 1143.2 ms | `summarize()` / driver.log tail |
| opp_driver_ms_per_turn_mean | 5014.9 ms (vs 5000 ms nominal, +0.30%) | `summarize()` |
| opp_driver_playouts_per_turn_mean | 103,501.8 (mean; PREREG §5 flags mean as endgame-skewed, median preferred — not computed by `summarize()`; see §4 note) | `summarize()` |
| wall_secs_per_game_mean | 249.7 s (~120.9 min / 400 games total, matches driver.log `DONE 400 games in 120.9 min`) | `summarize()` / driver.log |
| replay_failures | `[]` | `summarize()`, cross-checked directly |

Both `summarize()`'s embedded run-end JSON (found verbatim in the tail of `driver.log`) and an
independent re-run of the same frozen `summarize()` function against the freshly-scp'd
`games.jsonl` produced **byte-identical numbers** — the readout does not rest on trusting the
driver's own logged summary alone.

## 4. Notes, not gate failures

- **Median playouts/turn not computed here.** PREREG §5 "What must appear in the readout"
  says "median, not mean, for playouts/turn" (referring to the §2.1/smoke skew argument). The
  frozen `summarize()` function itself only emits the mean (`opp_driver_playouts_per_turn_mean`).
  This is a **gap between the launch procedure's stated readout requirement and what the
  frozen analyzer actually computes** — flagged, not resolved (§6). The per-move raw data
  (`carcasum_playouts` inside each record's `moves` list) is present in `games.jsonl` if a
  median is wanted; not computed here since the frozen analyzer doesn't compute it and the
  branch decision does not depend on it.
- `champion_manifest.dirty: true` / `code_rev_dirty: true` on every record (code_commit
  `f5a7c73495a44a6f05f40e5c14274d3a1e4e2263-dirty`). The load-bearing provenance witness per
  PREREG §2 ("Leaf hash stamped in every record's manifest") is the **leaf/config hash**, which
  matches `PRODUCTION.yaml` exactly (§1 above) — the dirty flag reflects uncommitted files
  elsewhere in the tree at launch time, not a leaf/config deviation. Noted for completeness,
  not a gate failure.
- `rust_threads=1` in every manifest. `PRODUCTION.yaml`'s `rust_threads: 2` is scoped to the
  **mobile/Android** deploy profile only; the desktop profile (the champion of record) doesn't
  pin a thread count, and the champion factory's own note states play is "BEHAVIOR-IDENTICAL
  (rustport G4 proved threads {1,4,8} bit-identical)... A single-GAME latency lever." No
  strength implication.

## 5. Not evaluated (out of scope per frozen text)

- §1.1 explicitly defers the budget ladder to "rung 2" — not part of this cell's read rule.
- §0.1's "+188 elo" transitive estimate is explicitly barred from being compared against by
  the frozen text itself ("Any readout that opens by comparing the result to '+188' has
  misread this section") — not used here.

## 6. Ambiguity flagged, not resolved

The frozen `PREREG.md` (as retrieved at `35f3c6da`, unedited) contains, in its first two
blockquote paragraphs:

> "⛔→✅ **FROZEN 2026-08-23 (branch-freeze: the blind commit is THE COMMIT INTRODUCING THIS
> BANNER, on branch carcasum-match-freeze ...)**"

immediately followed, unchanged from the pre-freeze draft, by:

> "**STATUS: DRAFT — NOT BLIND-COMMITTED, NOT AUTHORISED, NOT LAUNCHED.** Nothing in this file
> is frozen."

These two sentences are in direct tension within the same frozen file. The commit diff
(`git show 35f3c6da`) confirms the second paragraph is leftover, unedited text from
`PREREG_DRAFT.md` — the blind commit added the FROZEN banner and the D-first clarification but
did not delete the stale DRAFT-status paragraph beneath it. Per the task brief, this is flagged
rather than resolved. It does not change the mechanical outcome here: the task's framing
("the prereg... was FROZEN as a commit... before any game ran") and the git-provable single-diff
blind commit are treated as authoritative for executing the read rule; the stale paragraph is a
documentation defect in the frozen artifact, not a live ambiguity in the §5 decision rule text
itself (which is internally consistent and was applied as written).

## 7. Verdict

**Branch A — usable reference** fired. `|z| = 4.175 ≥ 3`. Deck-paired margin **+4.08 pts/deck**
(champion favored), win rate 0.56875 (223W/9D/168L of 400), elo_from_win_rate **+48.08**
(secondary statistic, within-band 1σ ≈ ±17.4 elo at n=400). Zero voids, zero REAL divergences,
100% final-score/farm/replay agreement across all 400 games — gate D does not fire.
