# READOUT — D2-R2 rung-compression cell (`track_d2r2_prep`), the instrument-fix successor

> **BRANCH: `U-UNREADABLE`** — §3 gate(s) FAILED: G-TIMING — ANY §3 gate FAILS ⇒ U-UNREADABLE.
>
> Blind pair `70501f74d2797da4d4ec40dba9aa9f681acf054f` (`DESIGN.md` + `READ_RULE.md`, frozen 2026-08-23; band `144000000000` claimed 2026-08-24; probe budget amended pre-game-1 to k4×1376 at `d3c720cf`). The adjudicator (`analyze_d2r2.py`) is a **mechanical port of the predecessor pair's `../track_d2_prep/analyze_d2.py`**, which WAS written from the frozen pair's text alone before any statistic was opened; the port is sound because this pair's READ_RULE §1–§6 are VERBATIM identical to the predecessor's, and every constant, gate predicate and branch condition is carried byte-identical (the file's own module docstring enumerates the seven changes). The branch is taken VERBATIM.

---

## §4 — THE BRANCH THAT FIRED, verbatim from `READ_RULE.md`

### `U-UNREADABLE`

**Says:** no strength or spacing statistic from this run is adjudicated, quoted, or entered in
`results.csv` as a verdict. The failed gate is named with its realized value.
`U-UNREADABLE` is a fully acceptable outcome.

> ⛔ **EVERYTHING BELOW IS PRINTED, NOT ADJUDICATED.** `READ_RULE.md` §4.3 requires the companion table on EVERY branch *including* `U-UNREADABLE`, so `S`, `se(S)`, `z_S` and both cells' absolutes appear below. Under this branch **none of them is adjudicated, quoted as a verdict, or entered in `experiments/results.csv`.** No spacing claim, no rung-compression claim, and no strength claim follows from this run. `U-UNREADABLE` is a fully acceptable outcome (READ_RULE §4).

### Instrument defects observed (post-adjudication diagnosis — moves no bar)

Named here with realized values because `U-UNREADABLE` requires the failed gate to be named. This is DIAGNOSIS, not adjudication: no threshold in the frozen pair was touched, and per READ_RULE §4 **the session that writes any instrument fix MUST be a session that has not seen `S`, `z_S`, or either cell's summary statistics** — this session has, so it writes no fix.

- **`G-TIMING` — CELL R800's realized equal-time ratio is outside the frozen [0.85, 1.2] interval**  
  CELL R800's realized equal-time ratio is **0.8382** (`champ_prefix_ms_per_move` 924.7 — the CANDIDATE side, the field-name trap of DESIGN §3.3 — over `rung_ms_per_move` 1103.1), which is BELOW the frozen interval [0.85, 1.2] by 0.0118 (1.38% of the floor). This is the §9 pilot's own bar re-checked on the real cell, exactly as READ_RULE §3 requires, and it is the check whose absence on the real cells the successor's §3.1 explicitly refused to grant ('a real precondition, not a formality'). THE PILOT PASSED IT: the §9 pilot at this same budget (k4×1376) read 831/881 = 0.9428, comfortably in-bar. The gap between pilot and cell is on the RUNG side — the python `HeuristicMCTS(h800)` rung cost 881 ms/move on a 16-game pilot and 1103.1 ms/move on the 400-game cell (+25.2%), while the rust probe moved 831 -> 924.7 (+11.3%). A 16-game pilot does not saturate 22 workers; a 400-game cell does, and the two sides do not degrade equally under saturation. **The pilot is therefore not a valid predictor of the cell's ratio at this W** — stated as a mechanism observation, not as a fix. See also the co-tenancy disclosure on this gate: an Android cross-compile + gradle build occupied the same box for the final ~10 minutes of this cell, whose effect on the ratio is real in magnitude and undetermined in direction.

**Context, gated by nothing (recorded so a later reader has it):**

- **FIX 1-4 — the whole point of this successor — all VERIFIED on the real cells.** `G-RULES` reads `rules_profile.name`=`fixed_v1` with `r9_env_ok`=`True` in both cells (FIX 1); `G-LEAF` reads `cand_leaf_hash`=`a36d2e15a3b3d71d` = the pinned champion curve125 leaf, DISTINCT from the rung's `42af12fce22e1a0f` (FIX 2); `G-TOOL` reads ONE code rev `d3c720cf-dirty` in both cells (FIX 3) and `BLIND_COMMIT` present and equal to the launcher's frozen value at BOTH searched addresses, manifest top level AND `config.stamps.*` (FIX 4). The four gates that voided the first attempt all PASS.
- **Probe budget realized k4×1376 = 5504**, which is DESIGN §0 item 9 (AMENDMENT 2026-08-25, `d3c720cf`) — the orchestrator's pair-level re-pick from k4×1032 after the §9 pilot read 0.659 on BOTH boxes, taken with the band UNSPENT and under READ_RULE §179-183's own delegation. No §3 gate covers the probe's own `--sims`; recorded as context.
- **The R1600 cell's ratio (0.4087) is NOT gated** — the frozen gate names CELL R800 only, and the R1600 ratio is expected to sit low because the rung side doubles its sims while the probe does not.
- **Gates that PASS: G-BAND, G-SINGLEVAR, G-RUNG, G-LEAF, G-RULES, G-TOOL, G-N, G-SAT.** In particular the cell RAN clean: 400/200-deck and 400/200-deck cells, `n_failed` 0/0, failure rate 0.0/0.0, band 144000000000 in both, and CELL R800's probe winrate 0.67 sits well inside the `G-SAT` interval [0.5, 0.9]. What voids this run is a COST-CALIBRATION precondition, not the games and not the instrument fixes.
- ⚠️ **A LATENT §3.1 DEFECT, found while adjudicating and reported for the orchestrator (not fixed here).** `G-SINGLEVAR` reads PASS under the mirror reading this port implements, but the emitter mirrors `--rung-sims` into `opponent.label`, `opponent.sims`, so under a LITERAL key-set reading of the gate's own words ('nothing else') it would read FAIL — and would read FAIL on EVERY healthy run of this launcher, because the two cells differ in `--rung-sims` by design and the emitter always echoes it. That is the same defect CLASS as the first attempt's unsatisfiable `G-TOOL` sub-clause, surviving a §3.1 re-test that was explicitly re-run over all nine gates. The frozen §3.1's own committed answer for this gate ('structural, not clerical' — i.e. NO, it does not fail on a healthy run) is what makes the mirror reading the pre-registered one, so this run's branch is unaffected; a future pair should nevertheless say so in the gate's TEXT rather than leave it to an adjudicator's reading. **This run's branch does not turn on it either way** — `G-TIMING` fails independently.

---

## §1 — THE PRIMARY STATISTIC

```
S      = M_R800 - M_R1600  = 1.8600 pts/game  (deck-paired, probe-minus-rung)
se(S)  = 1.2825 pts   [REALIZED, from the actual paired per-deck differences]
         DESIGN §4.2 pre-registered expectation: 1.25 pts
z_S    = 1.4503        [convention: eval_fair_puct._paired_z, IMPORTED]
n_common = 200 decks
M_R800   = 9.2475 pts   (se 1.0308, z 8.9714)
M_R1600  = 7.3875 pts   (se 0.8349, z 8.8486)
```

### §1 WITNESS — from-scratch recomputation from the raw per-game records

| quantity | analyzer | witness (independent re-read of every record) | agrees? |
|---|---|---|---|
| `S` | 1.860000000 | 1.860000000 | ✅ |
| `se_S` | 1.282507751 | 1.282507751 | ✅ |
| `z_S` | 1.450283633 | 1.450283633 | ✅ |
| `M_R800` | 9.247500000 | 9.247500000 | ✅ |
| `M_R1600` | 7.387500000 | 7.387500000 | ✅ |
| `n_common` | 200 | 200 | ✅ |

Tolerance: rel 1e-09 / abs 1e-09. **Witness verdict: AGREES.** The witness is a WITNESS, never a branch input (READ_RULE §1).

---

## §3 — THE GATES (fail-closed; ABSENT is FAIL)

| gate | status | realized | address(es) resolved |
|---|---|---|---|
| `G-BAND` | ✅ PASS | R800 seed_start=144000000000; R1600 seed_start=144000000000; record-derived deck sets agree=True (\|R800\|=200, \|R1600\|=200, only-in-R800=0, only-in-R1600=0); n_common=200 | `R800:config.seed_start, R1600:config.seed_start; deck sets: RECORDS` |
| `G-SINGLEVAR` | ✅ PASS | config blocks differ at: opponent.label (HeuristicMCTS(h800) vs HeuristicMCTS(h1600)) [emitter MIRROR of rung.sims], opponent.sims (800 vs 1600) [emitter MIRROR of rung.sims], rung.sims (800 vs 1600) [the single experimental variable]  ⚠️ MIRROR READING APPLIED to opponent.label, opponent.sims — these are the emitter's second copy of --rung-sims, not a second experimental axis; the frozen §3.1 answered NO for this gate ('structural, not clerical'), which only holds under this reading. Under a LITERAL key-set reading this gate would read FAIL — and would read FAIL on EVERY healthy run of this launcher, which is the §3.1 defect class itself. Both readings are printed; see the readout. | `config.* (deep diff, both manifests)` |
| `G-RUNG` | ✅ PASS | R800: c=3 agent=HeuristicMCTS sims=800 leaf_hash=42af12fce22e1a0f; R1600: c=3 agent=HeuristicMCTS sims=1600 leaf_hash=42af12fce22e1a0f; rung leaf_hash identical across cells=True | `R800:config.rung.c/config.rung.agent/config.rung.leaf_hash/config.rung.sims, R1600:config.rung.c/config.rung.agent/config.rung.leaf_hash/config.rung.sims` |
| `G-LEAF` | ✅ PASS | R800 cand_leaf_hash=a36d2e15a3b3d71d; R1600 cand_leaf_hash=a36d2e15a3b3d71d | `R800:config.cand_leaf_hash, R1600:config.cand_leaf_hash` |
| `G-RULES` | ✅ PASS | R800 rules_profile.name=fixed_v1 r9_env_ok=True; R1600 rules_profile.name=fixed_v1 r9_env_ok=True | `R800:rules_profile.name/rules_profile.r9_env_ok, R1600:rules_profile.name/rules_profile.r9_env_ok` |
| `G-TOOL` | ✅ PASS | carc_rs_version: R800=0.1.0 identical_across_cells=True; tile_data_semantic_digest: R800=525f7041ab8402f3008f9cd2… identical_across_cells=True; code_rev: R800=d3c720cf-dirty identical_across_cells=True; BLIND_COMMIT: R800=70501f74d2797da4d4ec40db… identical_across_cells=True; BLIND_COMMIT == launcher's frozen value (70501f74d279…)=True; placeholder=False | `R800.carc_rs_version:carc_rs_version, R1600.carc_rs_version:carc_rs_version, R800.tile_data_semantic_digest:config.backend.tile_data_semantic_digest, R1600.tile_data_semantic_digest:config.backend.tile_data_semantic_digest, R800.code_rev:code_rev, R1600.code_rev:code_rev, R800.BLIND_COMMIT:BLIND_COMMIT, R1600.BLIND_COMMIT:BLIND_COMMIT` |
| `G-N` | ✅ PASS | R800: games scored=400, n_failed=0, failure_rate=0, failure records on disk=0; R1600: games scored=400, n_failed=0, failure_rate=0, failure records on disk=0 | `summary.json + manifest top level (n_failed / failure_rate); games counted from RECORDS` |
| `G-TIMING` | ⛔ FAIL | R800: champ_prefix_ms_per_move=924.7 rung_ms_per_move=1103.1 ratio=0.8382; R1600: champ_prefix_ms_per_move=894.4 rung_ms_per_move=2188.5 ratio=0.4087; CELL R800 ratio inside [0.85, 1.2]=False | `summary.json (both cells)` |
| `G-SAT` | ✅ PASS | CELL R800 winrate=0.67 | `summary.json (CELL R800)` |

**All nine gates: 8/9 PASS, FAILED: G-TIMING.**

Address discipline (READ_RULE §3): every gate is read at the manifest TOP LEVEL first, then at `config.*`, and — for the three witnesses the emitter files inside `config` sub-dicts (`config.backend.*`, `config.env.*`, `config.rung.*`) — at those containers after that. The resolved address is printed for every gate above, so no resolution is silent.

> **`G-TIMING` — DISCLOSURE (context, NOT a gate modifier): the local box was NOT an exclusive tenant for the whole of CELL R800. CELL R800 ran ~19:06-19:51 EDT 2026-08-25; within its final ~10 minutes an ANDROID BUILD ran on the same box — `android/native/carc-cy/build/android/*.c` and the cross-compiled Cython wheels stamp 19:47, the rust wheels and the gradle/kotlin outputs 19:48, and the finished APK landed on the share at 19:51 (`/mnt/c/carc-shared/apk/app-debug-22k-20260825.apk`); `tests/android/*` pytest artifacts stamp 19:35-19:41. A cross-compile + gradle build is a heavy multi-core co-tenant, and the house rule `feedback_no_agent_compute_beside_eval` says a TIMING measurement is an EXCLUSIVE tenant. Contention inflates BOTH sides' ms/move and does so UNEVENLY when the two sides have different bottlenecks (the python `HeuristicMCTS` rung is DRAM-latency-bound; the rust probe is not), so the DIRECTION of any bias on the champ/rung ratio is not determined by this evidence and is NOT asserted here. (The `evloss_autopsy_20260824` shards that touch the share at 20:51-20:56 ran on laptop-wsl, a DIFFERENT box, and fall in CELL R1600's window, which `G-TIMING` does not gate.) `G-TIMING` adjudicates on the realized ratio EXACTLY as the frozen pair wrote it — this disclosure changes no threshold and no verdict; it is printed so a reader can see the known co-tenancy of the measurement window.**

---

## §4.3 — THE COMPANION TABLE (printed on EVERY branch)

### CELL R800 — probe vs HeuristicMCTS(h800, c=3.0)

**1. outcome**

| field | value |
|---|---|
| n games / n decks | 400 / 200 |
| seat balance (candidate's `a_seat`) | 0: 200, 1: 200 |
| W / D / L | 265 / 6 / 129 |
| winrate (z) | 0.6700 (z 6.80) |
| elo ± 1σ | 123.0 ± 18.5 |
| elo 95% CI | [86.8, 159.2] |
| deck-paired margin ± se (z) | 9.2475 ± 1.0308 (z 8.971) over 200 decks |
| avg diff (unpaired) | 9.248 |
| n_failed / failure rate | 0 / 0.00000 (stated even when zero) |
| failed_classes | `{}` |

**2. cost / timing**

`champ_prefix_ms_per_move` (= the CANDIDATE side — the field-name trap, DESIGN §3.3) **924.7** · `rung_ms_per_move` **1103.1** · realized ratio **0.8382×** · `solver_secs_per_game` **1.491**

**3. provenance**

band `144000000000` · `cand_leaf_hash` `a36d2e15a3b3d71d` · `rung.leaf_hash` `42af12fce22e1a0f` · rules `fixed_v1` (`r9_env_ok`=True) · code rev `d3c720cf-dirty` · `carc_rs_version` `0.1.0` · probe budget k4×1376 = 5504 · `rung_sims` 800

### CELL R1600 — probe vs HeuristicMCTS(h1600, c=3.0)

**1. outcome**

| field | value |
|---|---|
| n games / n decks | 400 / 200 |
| seat balance (candidate's `a_seat`) | 0: 200, 1: 200 |
| W / D / L | 263 / 7 / 130 |
| winrate (z) | 0.6663 (z 6.65) |
| elo ± 1σ | 120.1 ± 18.4 |
| elo 95% CI | [84.0, 156.2] |
| deck-paired margin ± se (z) | 7.3875 ± 0.8349 (z 8.849) over 200 decks |
| avg diff (unpaired) | 7.388 |
| n_failed / failure rate | 0 / 0.00000 (stated even when zero) |
| failed_classes | `{}` |

**2. cost / timing**

`champ_prefix_ms_per_move` (= the CANDIDATE side — the field-name trap, DESIGN §3.3) **894.4** · `rung_ms_per_move` **2188.5** · realized ratio **0.4087×** · `solver_secs_per_game` **0.980**

**3. provenance**

band `144000000000` · `cand_leaf_hash` `a36d2e15a3b3d71d` · `rung.leaf_hash` `42af12fce22e1a0f` · rules `fixed_v1` (`r9_env_ok`=True) · code rev `d3c720cf-dirty` · `carc_rs_version` `0.1.0` · probe budget k4×1376 = 5504 · `rung_sims` 1600

### 4. the primary statistic, its dispersion, and the elo-equivalent

| quantity | value |
|---|---|
| `S` = M_R800 − M_R1600 | **1.8600 pts/game** |
| `se_realized` | **1.2825 pts** (DESIGN §4.2 pre-registered: 1.25 pts) |
| `z_S` | **1.4503** |
| `n_common` | 200 decks |
| elo-equivalent of `S` | **24.7 elo** at the realized scale 13.304 elo/pt |
| realized scale, CELL R800 | 13.304 elo/pt (elo ÷ own deck-paired margin) |
| realized scale, CELL R1600 | 16.255 elo/pt |
| pre-registered scale (DESIGN §4.3) | 15.6 elo/pt ⇒ `S` = 29.0 elo |
| direct elo difference (R800 − R1600) | 2.9 elo |

> **`se_realized` as the `D2-COMPRESSED`-reachability witness (READ_RULE §4 / DESIGN §4.3.1):** realized `se(S)` = **1.2825 pts** vs the committed 1.25 pts ⇒ `D2-COMPRESSED` was **NOT REACHABLE** on this run. That branch opens only where the realized dispersion prints BELOW 1.25 pts; at or above it, any `z_S ≥ 2.0` lands in `D2-COARSE` by construction.

### 5. every gate, its realized value, and the address that resolved it

See the §3 table above — it carries the realized value and the resolved address for all nine gates, which is item 5 in full.

### 6. the DESIGN §1 prior table, reprinted beside this readout's own `S`

| source | contrast | n | band | result | ≈ pts (DESIGN §4.3) |
|---|---|---|---|---|---|
| measurement/level2/LEVEL2_LADDER_VERDICT.md (CL-023, 2026-06-18) | heur_v2_7@1600 vs @800 | 400, paired | fresh, 3.0e9+ | **+55.2 ±17.6 elo, paired z 3.23** | ≈3.5 |
| experiments/results.csv row l22_ctrl_heur1600_vs_heur800_b310_n400 (2026-06-19) | heur@1600 vs heur@800 | 400, paired | 3.10e9 | **+20.0 elo, sigma 17.4, z 3.285** | ≈1.3 |
| **THIS CELL (D2, band 144000000000, n_common 200)** | probe k4×1376 vs h800 rung minus same probe vs h1600 rung | 400 games / 200 decks each | 144000000000 | **24.7 elo-equivalent (1.8600 pts, z 1.45)** | 1.86 |

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

## APPENDIX — COST REALIZED vs DESIGN §6 (not a statistic, not a gate input)

| cell | wall | core-h at W=22 | DESIGN §6 projection | ratio |
|---|---|---|---|---|
| CELL R800 (19:06-19:51 EDT 2026-08-25) | 45 min (6.7 s/game × 400) | 16.4 | 6.5 core-h | 2.52× |
| CELL R1600 (19:51-20:58 EDT 2026-08-25) | 68 min (10.2 s/game × 400) | 24.9 | 9.6 core-h | 2.60× |
| **TOTAL** | **1.88 h** | **41.3** | **16.1 core-h** (wall ≈0.75 h at W=22) | **2.57×** |

The overrun was ANTICIPATED, in two named pieces, and needs no explaining away: **(1)** DESIGN §0 item 6 states outright that §6's arithmetic is the k4×688-era figure and reads LOW — the probe actually ran k4×1376 = 5504, **2× §6's 2752 probe sims**; **(2)** DESIGN §0 item 9 (the pre-game-1 amendment) measured that FIX 1's `CARCASSONNE_FIX_R9` export makes the frozen python `HeuristicMCTS` rung **~58% more expensive per move** (553.8 → 877.2 ms/move on the same rung, leaf, rev and box), and §6 was costed against the non-R9 rung. A third piece is NOT pre-priced: the realized rung cost on the 400-game cell (1103.1 ms/move) is a further **+25.8%** over the amendment's own 877.2 ms/move bench — the same gap that moved the timing ratio from the pilot's in-bar 0.9428 to the cell's out-of-bar 0.8382.

---

## §5 — WHAT NO BRANCH DOES (reprinted so the readout cannot be over-read)

No branch flips `governance/PRODUCTION.yaml`. No branch licenses a leaf or search change. No branch re-rates the champion. No branch retires or amends the CL-023 record itself. No branch transfers to the F5/walled-era ladder's absolutes. No branch licenses a second band or extends `n` beyond 200 decks/cell. No branch authorizes editing `results.csv`'s five historical mis-stamped rung-`c` cells.

