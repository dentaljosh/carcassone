# READOUT — D2 rung-compression cell (`track_d2_prep`)

> **BRANCH: `U-UNREADABLE`** — §3 gate(s) FAILED: G-SINGLEVAR, G-LEAF, G-RULES, G-TOOL — ANY §3 gate FAILS ⇒ U-UNREADABLE.
>
> Blind pair `db901b295e754cc9ae6a7fc6fcf2755d9efcb483` (`DESIGN.md` + `READ_RULE.md`, frozen 2026-08-23). The adjudicator (`analyze_d2.py`) was written from the pair's text alone, before any statistic was opened. The branch is taken VERBATIM.

---

## §4 — THE BRANCH THAT FIRED, verbatim from `READ_RULE.md`

### `U-UNREADABLE`

**Says:** no strength or spacing statistic from this run is adjudicated, quoted, or entered in
`results.csv` as a verdict. The failed gate is named with its realized value.
`U-UNREADABLE` is a fully acceptable outcome.

> ⛔ **EVERYTHING BELOW IS PRINTED, NOT ADJUDICATED.** `READ_RULE.md` §4.3 requires the companion table on EVERY branch *including* `U-UNREADABLE`, so `S`, `se(S)`, `z_S` and both cells' absolutes appear below. Under this branch **none of them is adjudicated, quoted as a verdict, or entered in `experiments/results.csv`.** No spacing claim, no rung-compression claim, and no strength claim follows from this run. `U-UNREADABLE` is a fully acceptable outcome (READ_RULE §4).

### Instrument defects observed (post-adjudication diagnosis — moves no bar)

Named here with realized values because `U-UNREADABLE` requires the failed gate to be named. This is DIAGNOSIS, not adjudication: no threshold in the frozen pair was touched, and per READ_RULE §4 **the session that writes any instrument fix MUST be a session that has not seen `S`, `z_S`, or either cell's summary statistics** — this session has, so it writes no fix.

- **`G-SINGLEVAR` — the two cells' `config` blocks differ beyond the single experimental variable**  
  The unexpected differing keys are `code_rev` (ce235373-dirty vs 513a509d-dirty), `backend.code_rev`, and `backend.carc_rs_build` — the two cells did NOT run at the same repo revision. `opponent.label` / `opponent.sims` also differ, but those are the rung's own knob mirrored under `opponent` (aliases of `rung.sims`, not a second experimental axis); **even under the most generous reading that treats them as aliases, this gate still FAILS on the code-rev / build triple.** DESIGN §3.1 argued this property was STRUCTURAL because both argv are built from one `COMMON` array — that argument covers the ARGV, and the tree moving underneath the launcher between two sequential cells is a path it does not cover.
- **`G-LEAF` — the probe did not run the curve125 champion leaf the pair pinned**  
  `config.cand_leaf_hash` reads `42af12fce22e1a0f` in BOTH cells, where the pair requires `a36d2e15a3b3d71d` (`champion_factory.LEAF_HASH_HARNESS`, the C7 curve125 champion leaf). The realized hash is identical to `config.rung.leaf_hash` (`42af12fce22e1a0f`) — i.e. the candidate ran the RUNG's own DEFAULT v2.9 leaf, because `run_cells.sh` passes no `--cand-leaf-json` and no curve125 injection. The mismatch is IDENTICAL in both cells, so it is a probe-IDENTITY defect (the probe is not the config DESIGN §3.1/§3.2 costed and justified), not a cross-cell inconsistency.
- **`G-RULES` — `fixed_v1` was stamped but its R9 env latch was never exported**  
  `rules_profile.name` = `fixed_v1` in both cells (correct), but `r9_env_ok` = `False` in both. `fixed_v1` carries `r9_env_expected=True`, and R9 CANNOT live in the profile — `base_deck` derives the farm data at import time and the Rust registry latches a `OnceLock`, so `CARCASSONNE_FIX_R9` must be exported into the ENVIRONMENT before the process starts. `run_cells.sh` exports nothing, so both cells played the `fixed_v1` bundle WITHOUT the R9 farm fix. This is the F9 A0 fail-loud path doing exactly what it was built to do.
- **`G-TOOL` — two independent failures — a real mixed-rev cell pair, and a structurally unsatisfiable `BLIND_COMMIT` sub-clause**  
  (1) SUBSTANTIVE: `code_rev` differs across the cells (`ce235373-dirty` vs `513a509d-dirty`; both `-dirty`) — the main tree moved between the R800 and R1600 legs, which the `RUN_LIVE.json` freeze latch exists to prevent. `carc_rs_version` and `tile_data_semantic_digest` DO match across cells, so the rust engine build is not implicated; the repo revision is. (2) INSTRUMENT: `BLIND_COMMIT` is ABSENT from both manifests at every address searched (top level, `config.*`, `config.backend.*`, `config.env.*`, `config.rung.*`, `evaluator.*`, plus the `blind_commit` / `CARC_BLIND_COMMIT` spellings). `eval_fair_puct.py` has NO `BLIND_COMMIT` stamping path at all, and this launcher only checks the `BLIND_COMMIT` FILE as a precondition — it never passes the value to the harness. That sub-clause therefore could not pass on ANY healthy run of this launcher: a §3.1 structural-test miss (§3.1 applied the test to G-SINGLEVAR / G-RUNG / G-LEAF / G-RULES / G-TIMING / G-N and never to G-TOOL's BLIND_COMMIT clause). Named as an instrument defect; NOT fixed here.

**Context, gated by nothing (recorded so a later reader has it):**

- **Probe budget realized k4×1032 = 4128**, not DESIGN §3.1's k4×688 = 2752. That is the §9 pilot's ONE allowed re-pick (repo commit `ce235373`: "D2 pilot re-pick … probe sims 688→1032, equal-time ratio 0.6455→0.9737 PASS"), taken on the discarded pilot band before any cell seed was touched, exactly as §9 permits. No §3 gate covers the probe's own `--sims`; recorded as context.
- **`G-TIMING` PASSED on its own bar**: CELL R800's realized ratio 0.9750 is inside [0.85, 1.2]. The R1600 cell's ratio (0.4801) is NOT gated by the pair (the gate names CELL R800 only) and is expected — the rung side doubles its sims while the probe does not.
- **`G-BAND`, `G-RUNG`, `G-N`, `G-TIMING`, `G-SAT` all PASS**: the band, the 200 shared decks with both seatings in both cells, the c=3.0 / HeuristicMCTS / 800-vs-1600 rung identity, 400/400 scored games with a ZERO failure rate in each cell, the equal-time ratio, and the non-saturation check are all clean. The cell RAN well; what voids it is provenance and probe identity, not the games.

---

## §1 — THE PRIMARY STATISTIC

```
S      = M_R800 - M_R1600  = 1.9575 pts/game  (deck-paired, probe-minus-rung)
se(S)  = 1.2765 pts   [REALIZED, from the actual paired per-deck differences]
         DESIGN §4.2 pre-registered expectation: 1.25 pts
z_S    = 1.5335        [convention: eval_fair_puct._paired_z, IMPORTED]
n_common = 200 decks
M_R800   = 6.9500 pts   (se 0.9124, z 7.6170)
M_R1600  = 4.9925 pts   (se 0.9516, z 5.2466)
```

### §1 WITNESS — from-scratch recomputation from the raw per-game records

| quantity | analyzer | witness (independent re-read of every record) | agrees? |
|---|---|---|---|
| `S` | 1.957500000 | 1.957500000 | ✅ |
| `se_S` | 1.276477258 | 1.276477258 | ✅ |
| `z_S` | 1.533517333 | 1.533517333 | ✅ |
| `M_R800` | 6.950000000 | 6.950000000 | ✅ |
| `M_R1600` | 4.992500000 | 4.992500000 | ✅ |
| `n_common` | 200 | 200 | ✅ |

Tolerance: rel 1e-09 / abs 1e-09. **Witness verdict: AGREES.** The witness is a WITNESS, never a branch input (READ_RULE §1).

---

## §3 — THE GATES (fail-closed; ABSENT is FAIL)

| gate | status | realized | address(es) resolved |
|---|---|---|---|
| `G-BAND` | ✅ PASS | R800 seed_start=141000000000; R1600 seed_start=141000000000; record-derived deck sets agree=True (\|R800\|=200, \|R1600\|=200, only-in-R800=0, only-in-R1600=0); n_common=200 | `R800:config.seed_start, R1600:config.seed_start; deck sets: RECORDS` |
| `G-SINGLEVAR` | ⛔ FAIL | config blocks differ at: backend.carc_rs_build (carc_rs-0.1.0+ce2353739955+rustcunpinned vs carc_rs-0.1.0+513a509d3023+rustcunpinned), backend.code_rev (ce235373-dirty vs 513a509d-dirty), code_rev (ce235373-dirty vs 513a509d-dirty), opponent.label (HeuristicMCTS(h800) vs HeuristicMCTS(h1600)), opponent.sims (800 vs 1600), rung.sims (800 vs 1600)  ⛔ UNEXPECTED: backend.carc_rs_build, backend.code_rev, code_rev, opponent.label, opponent.sims | `config.* (deep diff, both manifests)` |
| `G-RUNG` | ✅ PASS | R800: c=3 agent=HeuristicMCTS sims=800 leaf_hash=42af12fce22e1a0f; R1600: c=3 agent=HeuristicMCTS sims=1600 leaf_hash=42af12fce22e1a0f; rung leaf_hash identical across cells=True | `R800:config.rung.c/config.rung.agent/config.rung.leaf_hash/config.rung.sims, R1600:config.rung.c/config.rung.agent/config.rung.leaf_hash/config.rung.sims` |
| `G-LEAF` | ⛔ FAIL | R800 cand_leaf_hash=42af12fce22e1a0f; R1600 cand_leaf_hash=42af12fce22e1a0f | `R800:config.cand_leaf_hash, R1600:config.cand_leaf_hash` |
| `G-RULES` | ⛔ FAIL | R800 rules_profile.name=fixed_v1 r9_env_ok=False; R1600 rules_profile.name=fixed_v1 r9_env_ok=False | `R800:rules_profile.name/rules_profile.r9_env_ok, R1600:rules_profile.name/rules_profile.r9_env_ok` |
| `G-TOOL` | ⛔ FAIL | carc_rs_version: R800=0.1.0 identical_across_cells=True; tile_data_semantic_digest: R800=525f7041ab8402f3008f9cd2… identical_across_cells=True; code_rev: R800=ce235373-dirty identical_across_cells=False; BLIND_COMMIT: R800=ABSENT identical_across_cells=False; BLIND_COMMIT == launcher's frozen value (db901b295e75…)=False; placeholder=False | `R800.carc_rs_version:carc_rs_version, R1600.carc_rs_version:carc_rs_version, R800.tile_data_semantic_digest:config.backend.tile_data_semantic_digest, R1600.tile_data_semantic_digest:config.backend.tile_data_semantic_digest, R800.code_rev:code_rev, R1600.code_rev:code_rev, R800.BLIND_COMMIT:ABSENT, R1600.BLIND_COMMIT:ABSENT` |
| `G-N` | ✅ PASS | R800: games scored=400, n_failed=0, failure_rate=0, failure records on disk=0; R1600: games scored=400, n_failed=0, failure_rate=0, failure records on disk=0 | `summary.json + manifest top level (n_failed / failure_rate); games counted from RECORDS` |
| `G-TIMING` | ✅ PASS | R800: champ_prefix_ms_per_move=608.6 rung_ms_per_move=624.3 ratio=0.9750; R1600: champ_prefix_ms_per_move=602.9 rung_ms_per_move=1255.6 ratio=0.4801; CELL R800 ratio inside [0.85, 1.2]=True | `summary.json (both cells)` |
| `G-SAT` | ✅ PASS | CELL R800 winrate=0.615 | `summary.json (CELL R800)` |

**All nine gates: 5/9 PASS, FAILED: G-SINGLEVAR, G-LEAF, G-RULES, G-TOOL.**

Address discipline (READ_RULE §3): every gate is read at the manifest TOP LEVEL first, then at `config.*`, and — for the three witnesses the emitter files inside `config` sub-dicts (`config.backend.*`, `config.env.*`, `config.rung.*`) — at those containers after that. The resolved address is printed for every gate above, so no resolution is silent.

> **`G-TIMING` — DISCLOSURE (context, NOT a gate modifier): a 50-game Carcasum audit ran on the same box beside these cells for ~a few minutes. Wall-clock contention over that window inflates BOTH sides' ms/move, and only unevenly if the two sides were not equally exposed. `G-TIMING` adjudicates on the realized ratio EXACTLY as the frozen pair wrote it — this disclosure changes no threshold and no verdict; it is printed so a reader can see the one known co-tenant of the measurement window.**

---

## §4.3 — THE COMPANION TABLE (printed on EVERY branch)

### CELL R800 — probe vs HeuristicMCTS(h800, c=3.0)

**1. outcome**

| field | value |
|---|---|
| n games / n decks | 400 / 200 |
| seat balance (candidate's `a_seat`) | 0: 200, 1: 200 |
| W / D / L | 242 / 8 / 150 |
| winrate (z) | 0.6150 (z 4.60) |
| elo ± 1σ | 81.4 ± 17.9 |
| elo 95% CI | [46.4, 116.4] |
| deck-paired margin ± se (z) | 6.9500 ± 0.9124 (z 7.617) over 200 decks |
| avg diff (unpaired) | 6.950 |
| n_failed / failure rate | 0 / 0.00000 (stated even when zero) |
| failed_classes | `{}` |

**2. cost / timing**

`champ_prefix_ms_per_move` (= the CANDIDATE side — the field-name trap, DESIGN §3.3) **608.6** · `rung_ms_per_move` **624.3** · realized ratio **0.9750×** · `solver_secs_per_game` **1.106**

**3. provenance**

band `141000000000` · `cand_leaf_hash` `42af12fce22e1a0f` · `rung.leaf_hash` `42af12fce22e1a0f` · rules `fixed_v1` (`r9_env_ok`=False) · code rev `ce235373-dirty` · `carc_rs_version` `0.1.0` · probe budget k4×1032 = 4128 · `rung_sims` 800

### CELL R1600 — probe vs HeuristicMCTS(h1600, c=3.0)

**1. outcome**

| field | value |
|---|---|
| n games / n decks | 400 / 200 |
| seat balance (candidate's `a_seat`) | 0: 200, 1: 200 |
| W / D / L | 237 / 14 / 149 |
| winrate (z) | 0.6100 (z 4.40) |
| elo ± 1σ | 77.7 ± 17.8 |
| elo 95% CI | [42.8, 112.6] |
| deck-paired margin ± se (z) | 4.9925 ± 0.9516 (z 5.247) over 200 decks |
| avg diff (unpaired) | 4.992 |
| n_failed / failure rate | 0 / 0.00000 (stated even when zero) |
| failed_classes | `{}` |

**2. cost / timing**

`champ_prefix_ms_per_move` (= the CANDIDATE side — the field-name trap, DESIGN §3.3) **602.9** · `rung_ms_per_move` **1255.6** · realized ratio **0.4801×** · `solver_secs_per_game` **1.119**

**3. provenance**

band `141000000000` · `cand_leaf_hash` `42af12fce22e1a0f` · `rung.leaf_hash` `42af12fce22e1a0f` · rules `fixed_v1` (`r9_env_ok`=False) · code rev `513a509d-dirty` · `carc_rs_version` `0.1.0` · probe budget k4×1032 = 4128 · `rung_sims` 1600

### 4. the primary statistic, its dispersion, and the elo-equivalent

| quantity | value |
|---|---|
| `S` = M_R800 − M_R1600 | **1.9575 pts/game** |
| `se_realized` | **1.2765 pts** (DESIGN §4.2 pre-registered: 1.25 pts) |
| `z_S` | **1.5335** |
| `n_common` | 200 decks |
| elo-equivalent of `S` | **22.9 elo** at the realized scale 11.707 elo/pt |
| realized scale, CELL R800 | 11.707 elo/pt (elo ÷ own deck-paired margin) |
| realized scale, CELL R1600 | 15.565 elo/pt |
| pre-registered scale (DESIGN §4.3) | 15.6 elo/pt ⇒ `S` = 30.5 elo |
| direct elo difference (R800 − R1600) | 3.7 elo |

> **`se_realized` as the `D2-COMPRESSED`-reachability witness (READ_RULE §4 / DESIGN §4.3.1):** realized `se(S)` = **1.2765 pts** vs the committed 1.25 pts ⇒ `D2-COMPRESSED` was **NOT REACHABLE** on this run. That branch opens only where the realized dispersion prints BELOW 1.25 pts; at or above it, any `z_S ≥ 2.0` lands in `D2-COARSE` by construction.

### 5. every gate, its realized value, and the address that resolved it

See the §3 table above — it carries the realized value and the resolved address for all nine gates, which is item 5 in full.

### 6. the DESIGN §1 prior table, reprinted beside this readout's own `S`

| source | contrast | n | band | result | ≈ pts (DESIGN §4.3) |
|---|---|---|---|---|---|
| measurement/level2/LEVEL2_LADDER_VERDICT.md (CL-023, 2026-06-18) | heur_v2_7@1600 vs @800 | 400, paired | fresh, 3.0e9+ | **+55.2 ±17.6 elo, paired z 3.23** | ≈3.5 |
| experiments/results.csv row l22_ctrl_heur1600_vs_heur800_b310_n400 (2026-06-19) | heur@1600 vs heur@800 | 400, paired | 3.10e9 | **+20.0 elo, sigma 17.4, z 3.285** | ≈1.3 |
| **THIS CELL (D2, band 141000000000, n_common 200)** | probe k4×1032 vs h800 rung minus same probe vs h1600 rung | 400 games / 200 decks each | 141000000000 | **22.9 elo-equivalent (1.9575 pts, z 1.53)** | 1.96 |

⚠️ DESIGN §3.4: D2's ABSOLUTE numbers are NOT comparable to the F5 `fair_ruler_*` rows (different backend + pre-`fixed_v1` rules era). Only D2's internal cell-vs-cell contrast is claimed.

---

## §6 — THE STATED PRIOR, RECORDED BEFORE GAME 1 (reprinted)

Two conflicting readings of the same nominal contrast: CL-023 (+55.2 ± 17.6 elo, paired z 3.23,
band 3.0e9+) and `results.csv`'s `l22_ctrl_heur1600_vs_heur800_b310_n400` (+20.0 elo, sigma 17.4,
z 3.285, band 3.10e9) — same contrast, same n, 2.8× apart. CL-068's measured cross-band
over-dispersion (1.8–2.2×) is consistent in direction with a band-driven explanation but has never
been checked against this specific pair within one band.

**The house prior — recorded before this cell's first game — is that ladder rungs shrink with
depth**, from CL-023's own sequence: `@200→@800 +75.9 (z3.59) · @800→@1600 +55.2 (z3.23) ·
@1600→@3200 +34.9 (z2.36)`. A `D2-COARSE` or `D2-COMPRESSED` result — spacing detected, whether
large or attenuated — is therefore the expected shape; `D2-BOUNDED-NULL` says this cell could not
resolve which magnitude is closer to true; `D2-REVERSED` would contradict the house prior outright
and is the branch most in need of the pre-registered rung-vs-rung follow-up rather than
over-interpretation from a single equal-time probe cell.

---

## §5 — WHAT NO BRANCH DOES (reprinted so the readout cannot be over-read)

No branch flips `governance/PRODUCTION.yaml`. No branch licenses a leaf or search change. No branch re-rates the champion. No branch retires or amends the CL-023 record itself. No branch transfers to the F5/walled-era ladder's absolutes. No branch licenses a second band or extends `n` beyond 200 decks/cell. No branch authorizes editing `results.csv`'s five historical mis-stamped rung-`c` cells.

