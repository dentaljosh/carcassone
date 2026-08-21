# THE `B = 32` vs `B = 64` TIE-ARBITER LADDER GAME CELL — READ-RULE (DRAFT)

> **STATUS: DRAFT FOR THE ORCHESTRATOR'S REVIEW. NOT YET A PREREGISTRATION. NOT COMMITTED
> BLIND ON `main`. NOTHING LAUNCHED, NO SMOKE RUN, NO GAME PLAYED, NO `summary.json` OR
> `manifest.json` EXISTS FOR EITHER CELL OF THIS RUN.** The band **is** claimed
> ([DESIGN](DESIGN.md) §12.2) — the one state change the draft made.
>
> When it becomes a preregistration it must be committed in the **same commit** as
> [`DESIGN.md`](DESIGN.md), so git history proves the ordering, and every run manifest must
> carry that commit's hash. `WORKERS.conf::BLIND_COMMIT` reads `PENDING` until the executor
> writes it, and `run_cells.sh` **refuses a real-cell launch while it does**.
>
> ⭐ **This read-rule is written to be FULLY MECHANICAL.** Every branch is a boolean function
> of numbers the harness emits. **No owner call adjudicates any outcome.** ⛔ **And unlike its
> sibling, it accepts NO owner input at all**: the `b64_cell`'s `A` / `W` / `OWNER_WAIVER.md`
> affordability disjunction is **GONE**, because the N4 `rho_wall` bar it enforced was waived
> by [`OWNER_RULING_20260820.md`](../b64_cell/OWNER_RULING_20260820.md)
> ([DESIGN](DESIGN.md) §0.1). **There is exactly one disclosed exception to "no human act
> touches this rule": `G-FAILED` clause 3's escalation confirmation, which gates whether the
> run PAUSES and moves no branch, bar or statistic** (§3, and it is ruled text carried
> verbatim).
>
> ⭐ **Launch precondition, adopted verbatim from the `b64_cell`
> ([its DESIGN §13.1](../b64_cell/DESIGN.md)): every §3 row must be evaluated against a
> COMPLETED, KNOWN-GOOD run's artifacts — here the `b64_cell`'s — and must PASS on that
> healthy run, before the blind commit.** A gate that fails a healthy run is a drafting
> defect, and a fail-closed gate that *always* fails is not conservative — it is a rule that
> cannot be run.
>
> Definitions are frozen by reference to [`DESIGN.md`](DESIGN.md) §1–§9. **It is spent on this
> mechanism and this band; any successor needs a fresh one of each.**

---

## 1. Scope

- **Two cells**, `CELL_B32` (`B` = 32) and `CELL_B64` (`B` = 64), [DESIGN](DESIGN.md) §1.2/§2,
  **`n` = 1,500 deck-paired DECKS each = 3,000 games each** (6,000 games total), on **one fresh
  band `140000000000`** (claimed 2026-08-20, [DESIGN](DESIGN.md) §12.2) and **the same 1,500
  decks**, at production budget k8×1376 = 11,008, exact-K 2, `fixed_v1`, rust both sides,
  against the **unmodified champion**.
- **The PRIMARY statistic is `z_D` and `UB95(D) = D + 1.645·se_D`, the ONE-SIDED 95% UPPER
  BOUND on the COST, over the deck-paired difference of margins between the two cells,
  `D = M_B64 − M_B32`.** (⭐ ONE-SIDED by owner ruling, pre-blind —
  [`RULINGS_PREBLIND.md`](RULINGS_PREBLIND.md) RULING 1, 2026-08-21. The two-sided `CI90(D)`
  is reported for context and adjudicates nothing.) Each cell's own margin, elo and
  win-rate against the champion are **secondary, reported, and adjudicate nothing** (Stage 2
  precedent: the margin convicts, the win-rate does not).
- **The branch input is a WITHIN-BAND deck-paired contrast, and nothing else.** ⛔ **No
  cross-band comparison is a branch input anywhere** (CLAUDE.md cross-band humility: 1.8–2.2×
  over-dispersion, *"never pool across bands and quote the pool as an estimate"*). In
  particular **no comparison against the `b64_cell`'s band-139e9 numbers is a branch input**,
  and band 139e9 is RETIRED.
- **`governance/PRODUCTION.yaml` is untouched on every branch.** The most any branch does is
  license a **decision for the owner**.
- **Cost is reported on every branch and is a branch input NOWHERE.** There is no
  affordability conjunct and no cost bar (§4.2, [DESIGN](DESIGN.md) §0.1/§4.1).

---

## 2. The committed quantities

Every address carries an **existence-time marker** ([DESIGN](DESIGN.md) §3): `[pre-run]` ·
`[post-smoke]` · `[post-cells]`. **An unmarked address is a DRAFTING DEFECT** that must be
fixed before the blind commit, never adjudicated at read time.

| symbol | definition | address | marker |
|---|---|---|---|
| `M_32`, `M_64` | per-deck **seat-balanced paired margin** (pts/game) of the cell's candidate vs the unmodified champion | `summary.json::paired_mean_margin` | `[post-cells]` |
| `z_32`, `z_64` | `_paired_z` per cell — **secondary, adjudicates nothing** | `summary.json::paired_z` | `[post-cells]` |
| `E_32`, `E_64` | the same in elo, harness conversion, with CI | `summary.json::{elo, elo_sig_1sigma}` | `[post-cells]` |
| `wr_32`, `wr_64` | win-rate and its z — **reported, adjudicates nothing** | `summary.json::{winrate, winrate_z}` | `[post-cells]` |
| ⭐ **`D`** | `M_64 − M_32`, **deck-paired over the decks completed in BOTH cells** | adjudicator, over `seed*.json` | `[post-cells]` |
| ⭐ **`se_D`** | the paired standard error of `D`, computed exactly as `_paired_z` does | adjudicator | `[post-cells]` |
| ⭐ **`z_D`** | `D / se_D` — **THE PRIMARY, half 1** | adjudicator | `[post-cells]` |
| ⭐ **`UB95(D)`** | `D + 1.645·se_D` — the **ONE-SIDED 95% UPPER BOUND ON THE COST**, **THE PRIMARY, half 2** (⭐ RULING 1) | adjudicator | `[post-cells]` |
| `CI90(D)` | `[D − 1.645·se_D , D + 1.645·se_D]` — **reported for context, adjudicates nothing** since RULING 1 | adjudicator | `[post-cells]` |
| `rho` | realized cross-cell per-deck correlation, back-derived from `se_D`, `se_32`, `se_64` | adjudicator | `[post-cells]` |
| `f₀` | fraction of common decks with `D_i` **exactly** 0.0 | adjudicator | `[post-cells]` |
| `n_common` | decks completed in **both** cells (the denominator of `D`) | adjudicator | `[post-cells]` |
| `phi_x`, `phi_effective_x` | realized fired tied tile plies/game; `phi × (1 − error_rate_on_fired)` | `summary.json::{tiearb_phi, tiearb_error_rate_on_fired}` | `[post-cells]` |
| `ms_ratio_x` | `champ_prefix_ms_per_move / rung_ms_per_move`, in-cell, per cell | `summary.json` | `[post-cells]` |
| `F_32`, `F_64` | failed games per cell; `n_attempted_x` the attempted count; the per-failure records | `summary.json::{n_failed, failure_rate, failed_cells[], resolved_failed_cells[]}` | `[post-cells]` |
| — | smoke cost keys, **`production_knobs`** (dict echo of the §2 knobs) and **`smoke_utc`** (ISO-8601 UTC) | `SMOKE.json` | `[post-smoke]` |
| — | ⭐ the **HALT decision record**, `{halt, realized, bar}` — written by `smoke-check`, **enforced** by `run_cells.sh` (refuses a real-cell launch on `halt == true`, **no override**), read by `G-SMOKE` conjunct (c) | `SMOKE_HALT.json` | `[post-smoke]` |
| — | the `G-J13` witnesses | `verdicts/PREFLIGHT_${HOST}_FIRST_B{64,32}.json` at `j13_witness.{B,pick_changed,root_leaf_value_bits_unchanged}` + `expected.B` | `[pre-run]` |
| — | the `G-NEST` witness | `GATE_NEST.json` | `[pre-run]` |
| — | the band claim sentinel | `BAND_CLAIM.json` + the `governance/BAND_REGISTRY.csv` row | `[pre-run]` |

### 2.1 The committed constants — every one of them, in one place

```
COMMITTED se(D)            = 0.5044  pts/game   = 0.7133 x sqrt(750/1500)   (DESIGN §6.1)
realized-dispersion PROJ.  = 0.4570  pts/game   = 0.6463 x sqrt(750/1500)   NON-BINDING sanity line
Z-BAR                      = +-2.0                                          (Stage 1 / 1b / Stage 2 Phase B / E-FLAT / W-FLAT, verbatim)
2-sigma floor at committed = +-1.0088 pts/game
TOLERANCE (TOLERANCE_PTS)  =   0.93   pts/game                              (the OWNER's +-15 elo tolerance)
EQUIV_SHAPE                = one_sided                                      ⭐ RULING 1, 2026-08-21, OWNER
CRITICAL VALUE             = 1.645 = z_{0.95}, the ONE-SIDED 95% bound      (NOT "a 90% CI" -- see RULING 1)
ELO GLOSS (non-binding)    = 16.1247 elo per pt/game                        (27.6813 elo / 1.7167 pts, b64_cell realized)
G-N deck floor             = 1200 decks         (80% of 1500)
G-N game floor             = 2400 games/cell    (the SAME 80% bar in the other unit)
G-FIRE floor               = phi_effective >= 1.0
G-DIVERGE floor            = 1 - f0 >= 0.10 ;  EXPECTED ~0.98 ; ANOMALY-REPORT bar 0.95
G-FAILED rate bar          = 0.02 of attempted, per cell
SMOKE HALT bar             = 1.50 x 928.025 = 1392.038 worker-s/game on CELL_B64
BAND                       = 140000000000 .. 140000001499
```

⚠️ **THE FIELD-NAME TRAP, CARRIED VERBATIM:** **`champ_prefix_ms_per_move` IS THE CANDIDATE
SIDE** in `eval_fair_puct.py` (live lines 2361/2371/2389 — the opposite of
`eval_puct_priors`). **A read-out that swaps them inverts the cost verdict.**

### 2.2 ⭐ THE FOUR NAMED PREFLIGHT ADDRESSES — and what a TIMESTAMPED ROTATION is

**`G-J13` and `G-TOOL` both read the per-host preflight witnesses. Their addresses are these
four files and NO OTHERS:**

```
verdicts/PREFLIGHT_Doctor_FIRST_B64.json
verdicts/PREFLIGHT_Doctor_FIRST_B32.json
verdicts/PREFLIGHT_laptop-wsl_FIRST_B64.json
verdicts/PREFLIGHT_laptop-wsl_FIRST_B32.json
```

i.e. `verdicts/PREFLIGHT_${HOST}_FIRST_B${B}.json` for `HOST ∈ {Doctor, laptop-wsl}` and
`B ∈ {64, 32}` — **un-timestamped, exactly as `preflight.sh` writes them.** ⚠️ **Absent file
⇒ the reading gate FAILS**; a missing address is never a pass.

⛔⛔ **A TIMESTAMPED ROTATION IS A SUPERSEDED ARTIFACT, RECORDED REPORT-ONLY, AND IS NEVER A
GATE INPUT.** `preflight.sh` writes every attempt to its own
`PREFLIGHT_${HOST}_${LABEL}_B${B}_<epoch>.json` and promotes **only the first** to the
un-timestamped name the gates read (the Stage-2 pattern: *the FIRST attempt's verdict is the
gate witness and is NEVER overwritten by a resume*). Those `_<epoch>` files therefore
accumulate **across wheel epochs**, and a rotation from before a rebuild legitimately carries a
**different `carc_rs_build`** from the promoted witness.

⇒ **the four named addresses above are the gate inputs; every `_<epoch>` rotation is collected
SEPARATELY, labelled a superseded artifact, printed in the read-out beside the gate, and wired
into NO conjunct.** The adjudicator resolves the four names itself
(`analyze_b32v64_cell.py::named_preflights`, §12.1) rather than accepting a caller-supplied
glob. ⚠️ **The supersession is RECORDED, never silently dropped** — a rotation that vanished
without a trace would hide exactly the wheel-rebuild history the `[pre-run]` marker exists to
make visible.

⭐ **AND THIS IS WHY A GLOB IS FORBIDDEN AS AN ADDRESS.** A pattern such as
`PREFLIGHT_*_FIRST_B*.json` sweeps the rotations in with the witnesses and hands `G-TOOL` two
distinct `carc_rs_build` values **for one host** ⇒ `mixed_within_a_host` ⇒ `U-UNREADABLE` on a
run whose only irregularity was a wheel rebuild between preflight attempts — **the very event
the `[pre-run]` marker mandates** (*"after any wheel rebuild on that host, before that host's
game 1"*). That is the campaign's **unsatisfiable-gate** shape, and it is closed here, in the
pair's own text, before the blind commit.

⚠️ **MANIFEST RESOLUTION IS TWO-LEVEL.** Every `manifest.json` address is read **at the top
level, else under `config.`**, and the read-out **prints which was found**. Absent under both
is a failure, not a pass. *(Stage 2 lost an entire adjudication pass to this: `G-J1` and
`G-BAND` read `null` at the top level while the witnesses sat correct under `config.`)*

---

## 3. Preconditions — checked FIRST, and they void the run

**`U-UNREADABLE` fires, and no other branch may fire, if ANY of the following holds.**

Every gate carries a **scope marker**. **An unmarked gate is a DRAFTING DEFECT.** A gate with
conjuncts of mixed scope must be SPLIT into separately-named gates.

| marker | meaning | on a single-cell failure |
|---|---|---|
| `[RUN]` | whole-run conjunct (cross-cell quantities) | the **run** fails; no cell is readable |
| `[PER-CELL]` | evaluated separately per cell | ⚠️ **the RUN still fails** — `D` is a two-cell statistic and there is **no single-cell reading of this design**; the marker records *where* the failure was, not that anything survives it |

⭐ **`[PER-CELL]` here is deliberately NOT the `rung3_r5` "the other stratum remains readable"
semantics**, because this run has no per-cell estimand: the primary is a contrast. Stated in
the row rather than inferred — which is exactly what R4's unmarked `G-DISJOINT` failed to do.

### 3.1 THE GATE TABLE

| id | scope | marker | condition that FIRES it | what a HEALTHY run produces | TOOL / ADDRESS |
|---|---|---|---|---|---|
| `G-J1` | `[PER-CELL]` | `[post-cells]` | either cell's resolved `cand_leaf_hash` **differs** from `a36d2e15a3b3d71d`, or is absent under **both** levels. ⚠️ **INVERTED GATE: a difference is an ABORT, not a finding** | `a36d2e15a3b3d71d` in both cells (b64_cell realized exactly this) | adjudicator over `manifest.json::config.cand_leaf_hash` |
| `G-J4` | `[PER-CELL]` | `[post-cells]` | `cand_tiearb` absent/unresolved in either `manifest.json`; **or** `CELL_B64`'s resolved dict is not exactly `{enabled: true, B: 64, J: 4, mode: "argmax", salt: "tiearb2-deploy-v1", eps: 0.0}`; **or** `CELL_B32`'s is not the same with `B: 32`; **or** `summary.json::tiearb_B` is not the singleton `[64]` / `[32]` respectively, `tiearb_J` not `[4]`, `tiearb_modes` not `["argmax"]`. ⚠️ **a mixed-`B` cell is a VOID, not a finding** | the exact dicts; singleton `[64]` / `[32]` | adjudicator over `manifest.json::cand_tiearb` + `summary.json::tiearb_*` |
| `G-J13` | `[PER-CELL]` | `[pre-run]` | the **two-sided** positive control did not pass **at BOTH `B` values (64 AND 32)**, on **each** host, **before that host's game 1**: the arbiter must **change the pick** at a constructed tied ply **AND** leave `root_leaf_value_bits` **unchanged**. ⚠️ **ADDRESSES ARE PINNED** (`b64_cell/RULINGS_PREBLIND.md` RULING 2, carried): `j13_witness.B` (int, must equal the file's `B`), `expected.B` (must equal it), `j13_witness.pick_changed` (must be exactly `true`), `j13_witness.root_leaf_value_bits_unchanged` (must be exactly `true`). ⚠️ **ABSENT `B` ⇒ FAIL, never coerced.** ⚠️ **Absent file ⇒ fail.** ⭐ **RULING 4's condition, MANDATORY: the read-out prints, PER HOST, the exact filenames consumed and the `B` each carried — so a zero-match glob reads as ZERO, not as a silent pass** ⭐ **The file set is the FOUR NAMED, UN-TIMESTAMPED addresses of §2.2; `_<epoch>` rotations are SUPERSEDED artifacts, report-only, never gate inputs** | 4 files (2 hosts × 2 `B`), each with all four pinned KEY addresses present, both booleans `true` | `preflight.sh` writes `verdicts/PREFLIGHT_${HOST}_FIRST_B{64,32}.json`; `analyze_b32v64_cell.py::named_preflights` resolves them; adjudicator reads them |
| ⭐ `G-NEST` | `[RUN]` | `[pre-run]` | `GATE_NEST.json` is absent, or its witness is false: at HEAD, for a pinned position/ply/salt, the world seeds and playout seeds generated at `B` = 64 for `j ∈ 0..31` are **byte-identical** to those generated at `B` = 32, and the `build_arms` cap draw and the selection stream are identical; **or** the tautology anchor failed (python `seed_i64` + `carc_rs.shuffle_indices` did not reproduce `tiearb_probe`'s `arms` exactly at a position where the cap genuinely fires). ⚠️ **Without nesting, the two cells are two unrelated draws and the whole "refinement" framing is void** ([DESIGN](DESIGN.md) §1.3) | `witness: true`, anchor reproduced, `n_distinct_worlds` 64 / 32 | `gate_nest.py` writes `GATE_NEST.json` |
| `G-FIRE` | `[PER-CELL]` | `[post-cells]` | `phi_effective < 1.0` in either cell — the arbitration surface is inert and the cell grades a champion-vs-champion null wearing the shape of a real cell | ≈17.4–17.6 (b64_cell realized 17.5533 / 17.4087) ⇒ **17× headroom** | adjudicator over `summary.json::tiearb_phi` × `(1 − tiearb_error_rate_on_fired)` |
| ⭐ `G-DIVERGE` | `[RUN]` | `[post-cells]` | `1 − f₀ < 0.10`, i.e. fewer than 10% of common decks produced any difference between the two cells. ⚠️ **The `B`=64 surface is inert relative to `B`=32**: ≥90% of the paired sample would contribute exactly zero to `D` by construction, and the cell would be grading a `B=32`-vs-`B=32` null wearing the shape of a real contrast. ⭐ **THE FLOOR IS KEPT AT 0.10 AND ITS EXPECTED VALUE IS RE-DERIVED AT THIS RUNG** ([DESIGN](DESIGN.md) §8.2): the measured 32→64 value-change fraction on this campaign's own R4 corpus is **0.4045 per fired ply** (`shared_run_r4/verdicts/per_position_s1.jsonl`, 1,340 plies) and a deck carries ≈**34.96** fired plies ⇒ **the modelled `1 − f₀` is 1.0000**, and calibrated against the `b64_cell`'s realized 0.9840 at a 31%-churnier rung ⇒ **EXPECTED ≈ 0.98.** ⇒ **0.10 carries ≈10× headroom: it is an INERTNESS detector, not a power check.** ⚠️ **A realized `1 − f₀` below 0.95 PASSES the gate and is an ANOMALY that MUST be reported as one (§4.3 item 3), never read as a pass** | ≈0.98 | adjudicator over the per-deck `D_i` |
| `G-BAND` | `[RUN]` | `[pre-run]`+`[post-cells]` | the band was not claimed from `governance/BAND_REGISTRY.csv` **before game 1** (no `BAND_CLAIM.json` sentinel predating the first record); **or** the sentinel does not read `140000000000`; **or** the two cells did not run on the **same band and the same decks** (`config.band_seed_start` equal **and** equal to 140000000000, realized deck sets identical) | sentinel dated 2026-08-20, both cells `band_seed_start` 140000000000, identical deck sets | `claim_next_band.py` wrote both; adjudicator compares |
| `G-N` | `[RUN]`+`[PER-CELL]` | `[post-cells]` | `n_common < 1200` **decks**, **or** either cell completed fewer than **2,400** of its **3,000** paired **games**. ⚠️ Both clauses are the **same 80% bar** in the two units (2,400 games **is** 1,200 decks); the deck clause is **independently binding** because two cells can each clear 2,400 games while overlapping on fewer than 1,200 *common* decks. ⭐ **BOTH CLAUSES VERIFIED REACHABLE**: 1,200 ≤ the 1,500-deck ceiling and 2,400 ≤ the 3,000-game ceiling (Stage 2's version was unreachable by construction — 600 decks against a 400-deck ceiling — and could only ever return `U-UNREADABLE`) | 1,500 / 3,000 / 3,000 | adjudicator over `seed*.json` + `summary.json` |
| ⭐ `G-FAILED` | `[RUN]`+`[PER-CELL]` | `[post-cells]` | **any of the three clauses of [DESIGN](DESIGN.md) §8.1**: **(1)** `F_x / n_attempted_x > 0.02` in either cell; **(2)** `max(F_32,F_64) ≥ 5` **AND** `max(F) > 3 × max(min(F), 1)` — candidate-correlated exclusion, the `capoff` pattern; **(3)** *"If `F_w + F_n > 0`, the read-out must print, for every failed game, the harness's raw failure record verbatim (message and traceback tail as emitted), and the run **HALTS for owner escalation before adjudication** unless every failure is manually confirmed to be the known `WindowTruncationError` class. **The confirmation is a human act recorded in the read-out, and it is the one place this rule admits one** — it gates escalation, never a branch."* (carried VERBATIM from `b64_cell/RULINGS_PREBLIND.md` RULING 3; the reason it is still the narrowed form is [DESIGN](DESIGN.md) §13.2 item 2) | `F_32 = F_64 = 0` (b64_cell realized 0/1500 in both cells) ⇒ clauses 1 and 2 pass, clause 3 is vacuous | adjudicator over `summary.json::{n_failed, failure_rate, failed_cells[]}` |
| `G-TOOL` | `[RUN]` | `[pre-run]`+`[post-cells]` | ⭐ **THE CONJUNCT IS EQUALITY OF `carc_rs_build` ACROSS BOXES, AND NOTHING ELSE.** Fires if the two boxes' `carc_rs_build` values **differ**, or if a cell mixed builds. ⚠️ The authoritative witness is **`carc_rs_build`** = `carc_rs-<version>+<full-commit[:12]>+rustc<toolchain>`, sliced from the **full** commit (`core.abbrev` is per-box); **`carc_rs_binary_sha` is BOX-LOCAL and must NEVER be compared across boxes** (the `.so` is not machine-reproducible); the authoritative cross-box comparison is **the four NAMED, UN-TIMESTAMPED preflight witnesses of §2.2** — `verdicts/PREFLIGHT_{Doctor,laptop-wsl}_FIRST_B{64,32}.json`, and **no glob and no `_<epoch>` rotation** — **not** the manifests (under `--shared-claim` the second box writes no manifest, so `mixed_builds` on a manifest is the writer's own observation and cannot see the other box). ⛔ **`+rustcunpinned` is NOT a failure and NOT a sentinel — it is the NORMAL production value** (`src/carcassonne_ai/rust_agent.py:372`: `tc = os.environ.get("RUSTUP_TOOLCHAIN") or "unpinned"`; [`DEVIATIONS.md`](../DEVIATIONS.md) §D4.13 records **both boxes** emitting exactly `carc_rs-0.1.0+58c2b5395569+rustcunpinned` on the R4 run and it PASSED). **`unpinned` passes provided it is EQUAL on both boxes.** If pinned toolchains are wanted, that is a change to `WORKERS.conf::RUST_TOOLCHAIN`, **never** a gate conjunct that voids the run ⭐ **AND THE INPUT SET IS THE FOUR NAMED ADDRESSES OF §2.2 — timestamped rotations are SUPERSEDED artifacts, collected separately, printed report-only, and wired into NO conjunct.** A rotation predating a wheel rebuild legitimately carries a different `carc_rs_build`; admitting it would fire `mixed_within_a_host` on a healthy run | one identical `carc_rs-…+rustcunpinned` string across the four named witnesses | `preflight.sh` writes them; `analyze_b32v64_cell.py::named_preflights` resolves the four names (never a caller glob); adjudicator compares |
| `G-PLY` | `[PER-CELL]` | `[post-cells]` | `tiearb_partial_argmax_total` is **absent, or non-zero**, in either cell. **Absent is unknown-not-zero and FAILS.** Non-zero means an argmax was taken over a partial world set ⇒ the CRN pairing across arms was broken during play, so the comparison is void whatever the margins say | `0` in both cells (Stage 2 realized 0 across 28,350 fired plies) | adjudicator over `summary.json::tiearb_partial_argmax_total` |
| `G-STAT` | `[RUN]` | `[post-cells]` | `z_D`, `D`, `se_D`, `UB95(D)`, `CI90(D)`, `z_32` or `z_64` is `NaN`, infinite, or absent; **or** `se_D ≤ 0` | finite, `se_D > 0` | adjudicator |
| `G-SMOKE` | `[RUN]` | `[post-smoke]` | **(a)** the smoke did not run **at production knobs** — `SMOKE.json::production_knobs` absent, or any field differing from `WORKERS.conf`'s §2 knobs; **or (b)** it did not run **before game 1** — `SMOKE.json::smoke_utc` absent, or **≥** the earliest `seed*.json` mtime across the two real cells; **or (c)** it HALTed and the cells were launched anyway — `SMOKE_HALT.json::halt == true` **AND** game records exist for either real cell (⭐ **BOTH terms mechanical and `[post-cells]`-observable; NO operator flag, and no default-to-pass** — [DESIGN](DESIGN.md) §9.3.1); **or (d)** `SMOKE.json` contains a **forbidden OUTCOME key at any depth**. ⭐ **RULING 1 CARRIED VERBATIM — §9.2 DEFINES TWO SURFACES:** *"The **emitter** whitelist is fail-closed on unlisted keys and governs what `SMOKE.json` may contain. The **`G-SMOKE` row** fires only on forbidden **outcome** keys, at any depth. Structural keys are expected and never fire the row. A reading that applies the emitter whitelist to the row fails a known-good smoke."* The emitter-whitelist result is **reported beside the gate and is not a gate input** | `production_knobs` matching `WORKERS.conf` field-for-field; `smoke_utc` strictly earlier than the first game record; `halt == false`; no outcome key anywhere; structural keys present and ignored | ⚠️ **TWO MODES, TWO WRITERS, AND THE ORDER IS LOAD-BEARING:** `analyze_b32v64_cell.py` **`aggregate-smoke`** writes `SMOKE.json` (incl. `production_knobs`, `smoke_utc`) from the two smoke cells' own per-game records — ⛔ **it, and not `smoke-check`, is `SMOKE.json`'s writer, so it MUST run first**; then `analyze_b32v64_cell.py` **`smoke-check`** READS `SMOKE.json`, scans it, writes **`b32v64_cell/SMOKE_HALT.json`** `{halt, realized, bar}` (its only file output; the whitelist/gate surfaces go to **stdout**), and **exits non-zero on a HALT**; `run_cells.sh` **reads `SMOKE_HALT.json` and REFUSES a real-cell launch on `halt == true`, with NO override**; adjudicator reads all of it. *(Running `smoke-check` first yields "SMOKE.json ABSENT" — a MISSING ARTIFACT, never a whitelist violation, and `run_cells.sh` is written not to re-attribute it.)* |

**13 gates.** `U-UNREADABLE` = report cost, integrity, firing rates, divergence, the
failed-record accounting, and **whichever gate(s) failed — ALL of them, never short-circuited
at the first.** *(R3.3's corpus driver aborted under `set -e` at the first failing gate and
`GATE_DRAW.json` was never emitted; the gate suite here runs every check and prints every
result.)* **Nothing closes, nothing is licensed, nothing is re-labelled.**

---

## 4. Branches

**Evaluated in this order, FIRST MATCH WINS. `U-UNREADABLE` (§3) pre-empts everything.**

Definitions — **all in pts/game, never in elo**:

```
z_D        ==  D / se_D
UB95(D)    ==  D + 1.645*se_D        # the ONE-SIDED 95% UPPER BOUND ON THE COST
MARGIN     ==  0.93  pts/game        # TOLERANCE_PTS -- the owner's +-15 elo tolerance, DESIGN §6.2
EQUIV      ==  ( D + 1.645*se_D  <=  MARGIN )       # i.e. UB95(D) <= +0.93 .  ONE-SIDED NON-INFERIORITY.
```

⭐⭐ **`EQUIV` IS ONE-SIDED, BY OWNER RULING, PRE-BLIND.**
[`RULINGS_PREBLIND.md`](RULINGS_PREBLIND.md) **RULING 1, 2026-08-21**. The owner selected, from
the orchestrator's option card, **verbatim option label** *"One-sided ±15 (Recommended)"*, whose
**verbatim description shown to him** was: *"Fire the swap license when the one-sided 95% upper
bound on the cost is under 15 elo… Matches the actual question — we only care if 32 COSTS elo,
and the L-REVERSED branch already catches '32 is better'."*

```
WAS (drafted):   EQUIV  ==  ( |D| + 1.645*se_D <= MARGIN )   # two-sided equivalence
IS  (ruled):     EQUIV  ==  (  D  + 1.645*se_D <= MARGIN )   # ONE-SIDED NON-INFERIORITY
```

⚠️ **THE TOLERANCE DID NOT MOVE.** ±0.93 pts/game stands exactly as the owner set it. **Only the
SHAPE moved.** ⚠️ **AND `1.645` IS THE SAME NUMBER DOING A DIFFERENT JOB:** as drafted it was
the 90%-two-sided critical value; as ruled it is **`z_{0.95}`, the ONE-SIDED 95% critical
value.** The arithmetic is identical; the interpretation is not. **The read-out must say
"one-sided 95% upper bound", NEVER "90% CI".** ⚠️ **The `|·|` is dropped and the negative arm is
governed by BRANCH ORDER, not by the predicate** — see §4.4.

⛔ **THERE IS NO AFFORDABILITY PREDICATE.** The `b64_cell`'s `A` (`rho_wall(64) ≤ 1.20 ∨ W`)
and its `W` waiver machinery are **absent by design**: the N4 bar was waived at `B` = 64 by
[`OWNER_RULING_20260820.md`](../b64_cell/OWNER_RULING_20260820.md), so there is no cost bar
left for a branch to test ([DESIGN](DESIGN.md) §0.1). **Cost is reported on every branch and
grades nothing** (§4.2). ⚠️ **This absence is DECLARED rather than left to be noticed** —
silently deleting a predicate that governed the sibling cell would be exactly the quiet
amendment this campaign has ruled against.

### 4.0 ⭐ THE REACHABLE BRANCH SET, and every branch's reachability, stated BEFORE the run

**The Stage-2 `G-N` lesson applied prospectively: an unreachable branch must be visible BEFORE
the run, never discovered in the read-out.** All figures at the **committed** `se(D)` = 0.5044,
with the realized-dispersion projection (0.4570) beside them.

| # | branch | condition | REACHABLE? | the window, and its probability |
|---|---|---|---|---|
| 1 | `U-UNREADABLE` | any §3 gate fails | **REACHABLE** | by construction |
| 2 | `L-REVERSED` | `z_D ≤ −2.0` | **REACHABLE** | `D ≤ −1.0088` (realized-proj `−0.9140`). **25.3× the offline bracket top, in the wrong sign** ⇒ a priori very unlikely |
| 3 | `L-RISING` | `z_D ≥ +2.0` | **REACHABLE** | `D ≥ +1.0088` (realized-proj `+0.9140`). **25.3× the offline bracket top** ⇒ a priori very unlikely |
| 4 | `L-SATURATED` | `EQUIV`, i.e. `UB95(D) ≤ +0.93` | ⚠️ **REACHABLE** | fires on `D̂ ≤ 0.930 − 1.645×0.5044 =` **`+0.1003`** (realized-proj **`+0.1782`**), **unbounded below by the predicate** — but branch 2 pre-empts at `D̂ ≤ −1.0088` (realized-proj `−0.9140`), so the EFFECTIVE region is `(−1.0088, +0.1003]` |
| 5 | `L-AMBIGUOUS` | everything else | **REACHABLE** | the complement: `+0.1003 < D̂` **and** `z_D < +2.0` |

⭐ **RECOMPUTED FOR THE ONE-SIDED SHAPE** ([`RULINGS_PREBLIND.md`](RULINGS_PREBLIND.md) RULING 1,
2026-08-21). ⚠️ **The fire window's UPPER EDGE is numerically unchanged from the drafted
two-sided form** (`0.93 − 1.645·se_D`); what changed is that it is **no longer bounded below by
the predicate**, and the lower bound is now supplied by `L-REVERSED`'s precedence.

⛔⛔ **THE POWER STATEMENT, STATED HERE AND NOT BURIED IN THE DESIGN.** `raw` is the one-sided
test's own probability; `EFFECTIVE` subtracts the mass `L-REVERSED` takes first, and
**`EFFECTIVE` is the number that governs what this read-out can say**:

```
                                      COMMITTED se_D = 0.5044        REALIZED-PROJ se_D = 0.4570
                                      raw     L-REV    EFFECTIVE     raw     L-REV    EFFECTIVE
true D = 0        (the rungs equal)   0.5788  0.0228   0.5560        0.6517  0.0228   0.6290
true D = +0.0399  (bracket FLOOR)     0.5476  0.0188   0.5288        0.6189  0.0184   0.6005
true D = +0.1555  (bracket TOP)       0.4564  0.0105   0.4459        0.5198  0.0096   0.5102

   [for comparison, the DRAFTED two-sided shape: true D=0 -> 0.158 / 0.304 ;
                                                 true D=+0.1555 -> 0.150 / 0.287]

n for 80% one-sided power at a true D = 0   (se_D <= 0.93/(1.645+0.8416) = 0.37400):
   committed law   =>  n >= 2,728 decks/cell (5,456 games)
   realized law    =>  n >= 2,240 decks/cell (4,480 games)
   ⚠️ those are RAW one-sided figures; the EFFECTIVE power at that n is ~0.777, because
      L-REVERSED still takes ~2.3% of the lower tail first.
```

⇒ **IF `B` = 32 IS EXACTLY AS GOOD AS `B` = 64, THIS CELL NOW HAS A ~56% CHANCE (~63% AT THE
REALIZED DISPERSION) OF BEING ABLE TO SAY SO — up from ~16% (~30%) under the drafted two-sided
shape, at the same tolerance, the same `n`, and no extra spend.** ⚠️ **It is still not a
well-powered test**: ~44% of the equal-rungs world, and ~55% of the bracket-top world, still
reads `L-AMBIGUOUS`. **That is a declared property of the owner-funded design, not a failure of
it.** ⛔ **No read-out may present `L-AMBIGUOUS` as evidence of a difference.**

⭐ **AND THE KNIFE-EDGE — UNCHANGED BY THE RULING, AND HERE IS WHY.**
[DESIGN](DESIGN.md) §5.2's offline-implied bracket for the 32→64 rung is
`[+0.0399, +0.1555]` pts/game — **entirely inside the ±0.93 tolerance**. For its TOP, **as a
point estimate**, to fire `L-SATURATED` you need `se_D ≤ (0.93 − 0.1555)/1.645 = 0.4708`:

```
committed law  =>  n >= 1,722 decks/cell   (n = 1,500 MISSES it)
realized law   =>  n >= 1,413 decks/cell   (n = 1,500 CLEARS it)
```

*(Both are the same inequality solved and rounded to the deck: raw 1721.45 and 1413.25.)*

⚠️ **These two numbers are IDENTICAL to the drafted two-sided ones, and that is arithmetic, not
an oversight: for a POSITIVE point estimate `|D| = D`, so the two shapes coincide exactly on
the upper edge.** What the ruling changed is the **probability of landing in the window**
(0.150 → 0.446 at the bracket top, committed law), not the window's upper edge.

⇒ whether an offline-bracket-sized true effect can convict as non-inferior still depends on
**whether the realized dispersion lands nearer the committed 0.7133-law or the `b64_cell`'s
realized 0.6463-law**. The `b64_cell` beat its committed dispersion by 9.4%; this cell needs
9.4% or better again. ⛔ **That is not a reason to resize, and it is not a hedge** — it is the
sentence that tells the reader in advance which side of the line a marginal read lands on.

### 4.1 THE BRANCH TABLE

| # | branch | condition | read |
|---|---|---|---|
| 1 | **`U-UNREADABLE`** | any §3 precondition fails | §3. **A failing gate SUPPRESSES the verdict.** Report cost, integrity, firing rates, divergence, the failed-record accounting, and **every** gate with its realized value — never short-circuited at the first failure. **Nothing closes, nothing is licensed, nothing is re-labelled.** ⛔ The read-out may **not** print `D`, `z_D` or a branch label as if adjudicated. |
| 2 | **`L-REVERSED`** | `z_D ≤ −2.0` | ⛔ **NARROWING THE SELECTION WORLDS FROM 64 TO 32 MAKES THE ARBITER *BETTER* IN GAMES, AT 2σ, ON A FRESH BAND.** ⚠️ **Mandatory rider, never separated from the verdict:** this is a **direct tension with the offline ladder**, which prices `arb(64)` = 0.2015 **above** `arb(32)` = 0.1942, and with the `b64_cell`'s own `+1.7167` pts/game for `16→64`. **Print both and do NOT present the tension as resolved.** Those reads stand as adjudicated and this branch does not re-adjudicate them; what it establishes is that the offline→game map fails in *this* direction too, which is a first-class finding **about the map**. **Licenses: an INVESTIGATION, and an owner swap-down consideration on strictly stronger grounds than `L-SATURATED` would give.** ⛔ **NOTHING AUTOMATIC** — `PRODUCTION.yaml` is untouched, no claim is minted, and a reversal at 2σ on one band is a *reason to look*, not a reason to flip. |
| 3 | **`L-RISING`** | `z_D ≥ +2.0` | ⭐ **THE LADDER IS STILL RISING AT 64: DROPPING TO `B` = 32 COSTS REAL GAME POINTS, RESOLVED AT 2σ ON A FRESH BAND.** **Reading: the deploy STAYS at `B` = 64** (`PRODUCTION.yaml` already carries it; this branch changes nothing, it *confirms* the incumbent). **Licenses exactly one thing: a PREREGISTRATION for a `B` = 128 game cell** — ⛔ **which needs a FRESH prereg AND FRESH owner funding and is NOT automatic.** ⚠️ **Mandatory riders:** (i) print the realized `D` against the offline-implied bracket `[+0.040, +0.156]` and state plainly that a `D ≥ +1.009` read is **≥6.5× the bracket top**, i.e. the offline→game map has missed **again and by more**, which is itself the finding; (ii) print `rho_wall(128)` = 4.9794 and the ≈**5.98×** per-move total (≈10.8 s/move at the 1.8 s baseline) **beside** any `B` = 128 language, so nobody proposes the rung without its price; (iii) ⛔ **no branch may name `B` = 64 or `B` = 128 an optimum** — two points cannot resolve the shape. |
| 4 | **`L-SATURATED`** | `EQUIV`, i.e. `UB95(D) = D + 1.645·se_D ≤ +0.93` (⭐ ONE-SIDED — [RULINGS_PREBLIND](RULINGS_PREBLIND.md) RULING 1) | ⭐ **`B` = 32 DOES NOT COST MORE THAN THE OWNER'S ±15-ELO TOLERANCE: THE ONE-SIDED 95% UPPER BOUND ON THE COST IS BELOW +0.93 pts/game, ON A FRESH BAND, DECK-PAIRED.** **Licenses (does NOT do) exactly two things:** (i) **the deploy swap-down decision, `B` = 64 → `B` = 32**, put to the owner carrying the realized `D`, **`UB95(D)`**, the elo gloss, and the prize — **≈2.24 s/move saved, −35.7% of the per-move wall** ([DESIGN](DESIGN.md) §4.1); the **owner executes with one word and the prereg NEVER edits `PRODUCTION.yaml` itself**; and (ii) it **KILLS the `B` = 128 question** — a rung that adds nothing detectable at 64 adds nothing at 128, and no future prereg may cite this cell as licensing one. ⚠️ **MANDATORY SCOPE SENTENCE, quoted with the verdict and never separated from it:** *"This is a ONE-SIDED NON-INFERIORITY result at 95%: it convicts that `B` = 32 does not COST more than 0.93 pts/game (15 elo), the owner's stated tolerance. It says NOTHING about a 0.20-pts cost, and it is NOT a proof that the two rungs are identical. The realized `UB95(D)` is printed beside it, and the two-sided `CI90(D)` is printed for context and adjudicates nothing."* ⚠️ **Second mandatory rider:** print §4.0's pre-run power figures (**EFFECTIVE 0.556 at a true `D` = 0, 0.446 at the offline bracket top**, both at the committed dispersion) beside the realized `se_D`, so the reader can see how much of this verdict was bought by a favourable dispersion draw. ⚠️ **Third mandatory rider, and it exists because the predicate is one-sided:** if the realized `D` is **negative**, the read-out must state plainly that **`L-REVERSED` did NOT fire** (`z_D > −2.0`), that a negative `D` firing this branch is **correct and expected** under RULING 1 — *"`B` = 32 does not cost 15 elo"* is more comfortably true there than at `D` = 0 — and that **this branch is NOT the place to claim `B` = 32 is better**; that claim belongs to `L-REVERSED` and was not earned. |
| 5 | **`L-AMBIGUOUS`** | everything else (`−2.0 < z_D < +2.0` **and** `¬EQUIV`) — equivalently `D̂ > 0.93 − 1.645·se_D` **and** `z_D < +2.0` | **UNRESOLVED — NEITHER A CONVICTED COST NOR A CONVICTED NON-INFERIORITY.** **The deploy STAYS at `B` = 64 (the incumbent), and `B` = 128 is UNFUNDED BY DEFAULT.** ⛔ **Nothing closes and nothing is licensed.** ⭐ **Note what the one-sided shape does to this branch: it is now reachable ONLY from the HIGH side** (`D̂ > 0.93 − 1.645·se_D`), because every `D̂` below that edge and above `L-REVERSED`'s fires `L-SATURATED`. ⇒ **an `L-AMBIGUOUS` read means the realized point estimate was too HIGH to bound the cost, never too low.** ⚠️ **MANDATORY POWER PRINT, and the branch is not readable without it:** (i) the realized `D`, `se_D`, `z_D`, `UB95(D)` against the +0.93 tolerance, and `CI90(D)` for context; (ii) **the `n` that WOULD have resolved the REALIZED point estimate as a NON-INFERIORITY**, i.e. `n such that D_realized + 1.645·se(n) ≤ 0.93` computed at the **realized** per-deck dispersion, **printed in decks AND in games AND in two-box wall-hours** at [DESIGN](DESIGN.md) §7.5's measured 35.560-worker pool — ⛔ **and if `D_realized ≥ 0.93` the read-out must state that NO `n` resolves it (the point estimate itself exceeds the tolerance, so shrinking `se_D` cannot help) rather than printing an enormous number**; (iii) the same `n` for a 2σ *cost* verdict; (iv) §4.0's pre-run power table. ⚠️ **MANDATORY SCOPE SENTENCE:** *"This is an UNDER-POWERED one-sided non-inferiority test reading a high point estimate. [READ_RULE](READ_RULE.md) §4.0 states before the run that `L-SATURATED` fires with EFFECTIVE probability 0.556 (committed dispersion) / 0.629 (realized-dispersion projection) even when the two rungs are exactly equal — so ~44% of the equal-rungs world lands here. `L-AMBIGUOUS` is therefore NOT evidence that `B` = 32 is worse, and any read-out that presents it as such is over-reading it."* |

### 4.2 The cost rider — applied to every branch, and it is NEVER a branch input

`ms_ratio_32`, `ms_ratio_64`, `rho_wall`, the realized worker-s/game and the realized wall are
**reported on every branch and grade nothing.**

- ⛔ **THE AFFORDABILITY BAR IS WAIVED AND THERE IS NO AFFORDABILITY CONJUNCT.** Cited:
  [`b64_cell/OWNER_RULING_20260820.md`](../b64_cell/OWNER_RULING_20260820.md) ruling 1 —
  *"The N4 `rho_wall ≤ 1.20` bar is waived at `B = 64` for DESKTOP production play."* The
  historical `rho_wall` figures (0.6224 / 1.2449 / 2.4897 at 16 / 32 / 64) are printed as
  **history**, never as a test. **No branch has an affordability conjunct and no branch may be
  read as having one.**
- **`D` and `z_D` are cost-immune only in part, and the read-out must say which part.** The two
  cells are **not** cost-matched (`CELL_B64` spends ~1.60× the worker-seconds per game of
  `CELL_B32`). ⚠️ **But neither candidate's SEARCH BUDGET moves**: both run the identical
  champion at k8×1376 with identical sims, and the arbiter fires *after* the search, at the
  root, on an already-resolved tie ⇒ **the extra cost buys no extra search**. **It is a
  wall-clock asymmetry and it is disclosed as one, on every branch, rather than claimed away.**
- The **prediction-vs-realized** table of [DESIGN](DESIGN.md) §9.4 is printed on every branch.
  A wrong cost model must stay visible even where no bar is enforced.
- ⚠️ **The field-name trap** (§2.1) is named in the read-out **beside every `ms_ratio`**.
- ⚠️ **The smoke's `ms_ratio` and the cells' `ms_ratio` are both printed and NEITHER grades the
  other** (Stage 2 §0.H): a bar written after a smoke number exists is not a bar, and no such
  bar was pre-registered.

### 4.3 Mandatory on every branch — the full companion table

The read-out MUST print, on **every** branch including `U-UNREADABLE`:

1. **Both cells:** `n` attempted, `n` completed, `n_common`, `M`, `se`, `paired_z`, elo with
   CI, `wr` with `wr_z`, W/D/L, and the seat balance.
2. **The `D` block:** `D`, `se_D`, `z_D`, ⭐ **`UB95(D)` = `D + 1.645·se_D` labelled
   "ONE-SIDED 95% UPPER BOUND ON THE COST" and NEVER "90% CI"** (RULING 1), the two-sided
   `CI90(D)` **for context only**, `n_common`, the realized `rho`, and
   the `n` that would resolve `D` to 2σ **at the realized dispersion** — printed **beside**
   §2.1's committed `se(D)` = 0.5044 and floor ±1.0088 **and beside the non-binding
   realized-dispersion projection 0.4570**, so a dispersion-model miss is visible the way
   Stage 2's §0.G cost miss was.
3. ⭐ **The divergence block:** `f₀`, `1 − f₀` against `G-DIVERGE`'s 0.10 floor **and beside the
   EXPECTED ≈0.98** ([DESIGN](DESIGN.md) §8.2's derivation: the measured 32→64 value-change
   fraction 0.4045/fired ply × ≈34.96 fired plies/deck, calibrated on the `b64_cell`'s realized
   0.9840), the ≈10× headroom that implies, the `√(1−f₀)` dilution factor, and §1.3's
   nested-CRN statement. ⚠️ **A realized `1 − f₀` below 0.95 PASSES and is an ANOMALY — it must
   be reported as one, never as a pass.** Plus the measurement disclosure: `f₀` is measured as
   "`D_i` exactly 0.0", which **overcounts** identity (two different games can coincide on
   margin) ⇒ `1 − f₀` **undercounts** divergence ⇒ **the floor is CONSERVATIVE**: it can only
   fire early, never late.
4. **`phi_32`, `phi_64`, `phi_effective` for both**, beside the offline prior **22.96** and the
   `b64_cell`'s realized **17.5533 / 17.4087**, with [DESIGN](DESIGN.md) §7.2's `phi`-equality
   assumption restated and the realized cross-cell `phi` difference printed.
5. **`ms_ratio` for both cells** with the field-name trap named, the §4.2 rider, and the §9.4
   prediction-vs-realized table (committed `CELL_B64` **6.608**, `CELL_B32` **≈3.74**).
6. **Every §3 gate with its realized value and its scope marker**, all 13, never
   short-circuited — including the two-sided `G-J13` witness **per host and per `B` value**,
   ⭐ **with RULING 4's condition discharged: the exact filenames consumed and the `B` each
   carried, so a zero-match glob reads as ZERO** — and the `G-NEST` witness with its anchor
   result.
7. **The failed-record accounting in full** ([DESIGN](DESIGN.md) §8.1): `F_32`, `F_64`,
   `n_attempted`, the realized rates against the 2% bar, clause 2's ratio, ⭐ **the complete
   `summary.json::failed_cells[]` dump — `seed`, `a_seat`, `attempts`, `permanent`, `exc_type`,
   `window_truncation`, `window_diag` — plus `resolved_failed_cells[]`, `failure_rate_trigger`
   and `validity_trigger_fired`**, `tiearb_errors_total`, `tiearb_error_rate_on_fired`,
   `tiearb_first_error`, `tiearb_partial_argmax_total` — **printed whether or not any failure
   occurred**, and with the geometry-correlation disclosure sentence. ⛔ **The `failed_cells[]`
   dump is a REPORT and is wired into NO conjunct** ([DESIGN](DESIGN.md) §13.2 item 2).
8. **The cost facts of record:** `rho_wall` 0.6224 / **1.2449** / **2.4897** at `B` = 16 / 32 /
   64 **and the N4 bar of 1.20 labelled WAIVED AND RETIRED with its citation**; the total
   per-move wall vs the champion baseline (**2.2449×** at 32, **3.4897×** at 64) and the
   **≈2.24 s/move, −35.7%** prize; `rho_phone` at 32 ∈ {11.04, 11.95} and at 64 ∈ {22.08,
   23.90} **labelled NOT SOLVED and a THIRD CURRENCY**; the realized worker-s/game for both
   cells against [DESIGN](DESIGN.md) §7.2's committed **579.389 / 928.025**; the realized
   two-box wall against §7.5's committed **35.33 h** and its measured **35.560**-worker pool.
9. ⭐ **The offline ladder carried as a DESCRIPTION and explicitly NOT as a projection:**
   `arb(32)` = 0.1942, `arb(64)` = 0.2015, `Δ(32→64)` = +0.0073 pts/tied ply, ratio 1.038, and
   the §5.2 bracket `[+0.040, +0.156]` pts/game. ⛔ **MUST NOT be presented as a projection of
   the game effect.**
10. ⭐ **The 3.9× translation caveat carried VERBATIM, with BOTH its directions:** *"Stage 1b's
    +0.1441 pts/tied ply predicts +0.79 pts/game … Phase B realized +3.07 — a 3.9×
    under-prediction"* and *"the offline→game map is unestablished and +0.0670 × 3.9 is not a
    projection either"*. **Plus the second datum:** the `b64_cell`'s bracket `[+0.368, +1.435]`
    realized **+1.7167** — the map missed **low twice, at n = 2, in the same direction**. ⛔
    **That is still not a licence to multiply.**
11. ⭐ **The cross-band humility block** ([DESIGN](DESIGN.md) §11): the four-rung table **with
    its band column**, the statement that **139e9 is RETIRED and MUST NOT be pooled with
    140e9**, the 1.8–2.2× over-dispersion figure, and the statement that **the only branch input
    is the within-band deck-paired `D`**.
12. **The realized band (140000000000), the deck range, and the `BAND_REGISTRY` claim row.**
13. **This rule's own blind-commit hash**, and the assertion that it and [`DESIGN.md`](DESIGN.md)
    landed in the **same commit** before game 1 (the band claim predates the commit here and
    that ordering is itself printed — see [DESIGN](DESIGN.md) §12.2).

### 4.4 Exclusivity and exhaustiveness — VERIFIED in the pre-registration text

**§3 is evaluated first and pre-empts everything.** On its complement, with `se_D > 0` finite
(guaranteed by `G-STAT`) and writing `t = z_D`, `c = 1.645·se_D`:

- **Branch 2, `L-REVERSED`**, is evaluated second: `t ≤ −2`. It pre-empts branches 3–5.
- **Branch 3, `L-RISING`**, is evaluated third: `t ≥ +2`. Disjoint from branch 2 (`t ≤ −2` and
  `t ≥ +2` cannot both hold for finite `t`). It pre-empts branches 4–5.
- **Branch 4, `L-SATURATED`**, is evaluated fourth: `EQUIV`.
- **Branch 5, `L-AMBIGUOUS`**, is the **complement of branches 2 ∪ 3 ∪ 4** by definition.

*(⚠️ The bullets above are numbered by BRANCH, matching §4.0 and §4.1 — not by position in this
list. Branch 1 is `U-UNREADABLE`, evaluated first in §3.)*

⇒ **TOTALITY: branch 5 is defined as the complement, so the union of branches 2–5 is the whole
space.**
⇒ **DISJOINTNESS: guaranteed by FIRST-MATCH-WINS regardless of any arithmetic overlap** —
which is the governing rule and is stated first so nothing rests on the arithmetic below.

⭐⭐ **THE ONE-SIDED PREDICATE MAKES BRANCH ORDER LOAD-BEARING, AND THAT IS DELIBERATE.**
Since [RULINGS_PREBLIND](RULINGS_PREBLIND.md) RULING 1 dropped the `|·|`, **`EQUIV` is TRUE for
every sufficiently negative `D`** — the predicate alone would let `L-SATURATED` swallow the
whole lower half-line. **It does not, because `L-REVERSED` is evaluated SECOND and pre-empts
it.** Spelled out, because a rule that hides this is a rule nobody can audit:

- **A LARGE-NEGATIVE `D` (`z_D ≤ −2.0`) FIRES `L-REVERSED`, BEFORE `L-SATURATED` IS EVALUATED
  AT ALL.** `EQUIV` is also true there, and it is **never reached**. The stronger, more specific
  finding — *"narrowing makes the arbiter BETTER at 2σ"* — wins, with its own mandatory riders.
- **A MILDLY-NEGATIVE `D` (`−2.0 < z_D < 0`) FIRES `L-SATURATED`, AND THAT IS CORRECT AND
  DESIRABLE.** The claim that branch licenses — *"`B` = 32 does not COST 15 elo"* — is **true**
  there, and more comfortably true than at `D` = 0. ⛔ It is **not** a licence to say `B` = 32 is
  better; branch 4's third mandatory rider says so in the read-out.

⇒ **the EFFECTIVE `L-SATURATED` region is `(−2·se_D , 0.93 − 1.645·se_D]`** — bounded below by
**branch order**, not by the predicate. ⚠️ **Anyone re-implementing this rule must preserve the
ORDER, not just the five conditions**; an implementation that evaluates `EQUIV` first is a
different rule and would mislabel every `L-REVERSED` read.

⭐ **AND THE UPPER-SIDE ARITHMETIC, because a first-match rule that hides a real overlap is
worse than one that discloses it.** `L-RISING` and `L-SATURATED` **cannot co-fire at these
constants**:

```
z_D >= 2   =>   D >= 2*se_D   =>   D + 1.645*se_D  >=  3.645*se_D
at the committed se_D = 0.5044:   3.645 x 0.5044 = 1.8385  >  0.93   => EQUIV is FALSE
```

⇒ **the upper overlap is empty for every `se_D > 0.93/3.645 = 0.2551`.** The committed `se_D`
is 0.5044 and the `b64_cell`'s realized dispersion would give 0.4570; an overlap would require
the realized dispersion to beat the committed one by **49.4%** (the `b64_cell` beat its own by
9.4%). ⚠️ **If that happened, FIRST-MATCH-WINS still governs and `L-RISING` takes precedence**
— a 2σ *cost* is not a non-inferiority whatever a wide-margin bound says, and the read-out must
print both facts. ⚠️ **The LOWER overlap, by contrast, is NOT empty and is not meant to be** —
it is the deliberate design above, resolved by order.

- Any `NaN` / infinity / `se_D ≤ 0` in `z_D`, `D`, `se_D`, `UB95(D)`, `CI90(D)`, `z_32`, `z_64` is caught
  by `G-STAT` in §3 **before** any comparison is taken, so no branch is entered on a `NaN`
  comparison.
- ⇒ **exactly one branch matches every possible read.**
- ⛔ **TO BE VERIFIED BY A MACHINE SWEEP over the branch-condition truth table**, in
  `tests/test_tiearb_b32v64.py`, which must **re-transcribe this section independently of the
  implementation** and assert exactly one branch fires on every cell — `NaN`, infinity, the
  `se_D ≤ 0.2551` overlap region, and the exact boundary values `z_D ∈ {−2, +2}` and
  `|D| + 1.645·se_D = 0.93` included. *(This test **does not exist yet** and is a LAUNCH
  PRECONDITION — [DESIGN](DESIGN.md) §12.1. Stage 2's equivalent §4.1 sweep is the template,
  and it is what found Stage 2's unreachable `G-N` before any number existed.)*

---

## 5. What no branch does

- **No branch edits `governance/PRODUCTION.yaml`.** `L-SATURATED` licenses a swap-down
  **DECISION for the owner**; the owner executes it with one word. The deployed `B` = 64 /
  `J` = 4 shape is untouched by **every** branch of this rule.
- **No branch mints a claim in `governance/CLAIM_REGISTRY.csv`.** The `results.csv` rows are the
  citation, with the usual self-anchored caveat (elo vs our own champion within band 140e9, not
  absolute strength).
- **No branch licenses an on-device / phone deploy.** `rho_phone` ∈ [11.0, 11.95] at `B` = 32
  and [22.08, 23.90] at `B` = 64 — the phone currency was never solved even at `B` = 16
  (5.520 / 5.976, *reported, unadjudicated*), and the mobile profile plays the unmodified
  champion.
- **No branch resolves the ladder's SHAPE.** Two points in game points cannot separate
  "log-linear", "saturating-exp" and "√B-noise". **No branch may name `B` = 32, 64 or 128 an
  optimum.** The **only** shape statement any branch makes is the `B` = 128 gate written into
  `L-RISING` (licenses a prereg, not a run) and `L-SATURATED` (kills it).
- **No branch widens or narrows `J`, changes `eps`, the salt, the trigger predicate, the
  playout, or the champion.** `rung3_r5` read `X-INCONCLUSIVE` on `J`; `J` stays 4.
- **No branch adds a leaf term, changes the production leaf, or trains anything.**
- **No branch re-anchors any ruler or eval baseline.** Fixed eval/anchor sides stay the
  unmodified champion (the curve125 ambient-contamination warning pattern applies).
- **No branch resizes `n`** — not from the smoke, not from the realized `ρ`, not from `f₀`. The
  smoke may **HALT**; it may never **RESIZE** ([DESIGN](DESIGN.md) §6.1, §9.3).
- **No branch re-reads, re-labels or re-adjudicates** Stage 1, Stage 1b, Phase A, Stage 2 Phase
  B, the R4 widening run (`W-RISING` or `VOID_S2`), `rung3_r5` (`X-INCONCLUSIVE`), or the
  `b64_cell` (`B-COSTKILL`). They stand as adjudicated; their read-rules are spent and their
  bands retired.
- **No branch licenses a second game cell.** ⭐ **This read-rule is SPENT when the read-out
  lands, on every branch, and band 140000000000 retires from confirmatory use.** Any successor
  — including a `B` = 128 cell, a head-to-head cell behind an opponent-side knob, or an
  extension of `n` — needs a **fresh pair and a fresh band**.
