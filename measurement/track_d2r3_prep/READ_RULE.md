> ## §0 — PROVENANCE BANNER (the pre-registered COST-CALIBRATION successor)
>
> ⛔→✅ **FROZEN 2026-08-25 (the blind commit is THE COMMIT THAT INTRODUCES THIS FILE; its sha is stamped into [`run_cells.sh`](run_cells.sh) and [`BLIND_COMMIT`](BLIND_COMMIT) in the follow-up commit, per the b32v64 / d2r2 pattern). No statistic of any kind exists at freeze time.**
>
> This file is the **pre-registered cost-calibration successor** to
> [`../track_d2r2_prep/READ_RULE.md`](../track_d2r2_prep/READ_RULE.md), which is itself the
> instrument-fix successor to [`../track_d2_prep/READ_RULE.md`](../track_d2_prep/READ_RULE.md).
> **D2 now carries two voids from two different causes:**
>
> | attempt | band | branch | cause |
> |---|---|---|---|
> | 1 (`track_d2_prep`) | `141000000000` | `U-UNREADABLE` | **provenance** — four instrument gates (`G-RULES`, `G-LEAF`, `G-TOOL` ×2) |
> | 2 (`track_d2r2_prep`) | `144000000000` | `U-UNREADABLE` | **cost calibration** — `G-TIMING`, realized `0.8382` vs floor `0.85` |
> | 3 (**this pair**) | `149000000000` | — | — |
>
> **Attempt 2 SUCCEEDED at its own mission.** All four provenance fixes were verified on real
> 400-game cells (`r9_env_ok=True`, candidate leaf `a36d2e15a3b3d71d` distinct from rung
> `42af12fce22e1a0f`, one code rev, `BLIND_COMMIT` at both searched addresses), and eight of nine
> gates passed. **This pair inherits that machinery VERBATIM and fixes ONLY the cost calibration.**
>
> ### ⚠️ BLINDNESS DISCLOSURE — READ THIS BEFORE TRUSTING ANY BAR BELOW
>
> `../track_d2r2_prep/READ_RULE.md` §4 binds: *"the session that writes any instrument fix MUST be
> a session that has not seen `S`, `z_S`, or either cell's summary statistics."* The d2r2
> adjudicating session is therefore **disqualified from authoring this pair**, and did not.
>
> **This authoring session is a fresh session, but it is NOT statistics-blind to attempt 2.** It was
> instructed to read [`../track_d2r2_prep/READOUT_D2R2.md`](../track_d2r2_prep/READOUT_D2R2.md) —
> *"you must learn from its void"* — and that readout **prints `S`, `se(S)` and `z_S` on its
> `U-UNREADABLE` branch** (its own §4.3 requires the companion table on every branch). So this
> session has seen attempt 2's unadjudicated `S` and `z_S`. That is a deliberate trade made by the
> orchestrator: blindness-to-attempt-2's-number in exchange for competence at fixing the instrument
> that voided it. **It is disclosed here, loudly, rather than papered over**, and it is made
> auditable by three mechanical properties a reviewer can check with `diff`:
>
> 1. **§4's branch names, conditions, thresholds and licence text are BYTE-IDENTICAL to
>    `../track_d2r2_prep/READ_RULE.md` §4** — including `z_S ≥ 2.0`, `S ≥ 2.5 pts`, the
>    `D2-COMPRESSED` reachability note and its `1.25 pts` figure. Nothing in the branch structure
>    could have been chosen to favour an outcome, because nothing in it was chosen at all. **The
>    ONLY textual change anywhere in §4 is the APPENDED `§4.1` note**, which adds no branch and
>    moves no condition — it says what an aborted run is (`U-UNREADABLE`, which §4 already covers)
>    and forbids computing `S` from a one-cell archive.
> 2. **§1 and §6 are byte-identical.** The stated prior in §6 predates all three attempts (CL-023
>    and `results.csv`, 2026-06-18/19) and is carried unedited. **§2 and §5 are verbatim plus one
>    clearly-marked addition each** — §2 gains the COST-unit paragraph (a unit definition, not a
>    bar), §5 gains the "Added for this pair, and binding" paragraph, which only *removes*
>    licences. **Every change in this file is additive or restrictive; no bar, branch, threshold or
>    licence is widened anywhere.**
> 3. **Every quantity taken from attempt 2 is a COST or a DISPERSION, never a spacing or a
>    strength.** Exhaustively: the realized rung cost `1103.1 ms/move`, the realized probe cost
>    `924.7 ms/move` at 5504 total sims, the pilot→cell drift figures, the burn-in-window
>    retrospective (§3.2, computed from per-game timing fields only), the co-tenancy disclosure,
>    and `se(S)` as a power-calibration witness (`DESIGN.md` §4.2a). `S` and `z_S` are used
>    **nowhere** — not in a bar, not in a threshold, not in `n`, not in the probe budget.
>
> **The mechanical check. ⚠️ Read the expected outcome of each command — the first one is NOT
> expected to be empty, and a reviewer who assumes it is will misread a PASS as a FAIL:**
>
> ```
> diff <(sed -n '/^## §4 — THE BRANCHES/,/^## §4.3/p' ../track_d2r2_prep/READ_RULE.md) \
>      <(sed -n '/^## §4 — THE BRANCHES/,/^## §4.3/p' READ_RULE.md)
> #  => the ONLY hunk is the added §4.1 block. Any other hunk is a finding.
>
> diff <(sed -n '/^## §1 — THE STATISTIC/,/^## §2 — UNITS/p' ../track_d2r2_prep/READ_RULE.md) \
>      <(sed -n '/^## §1 — THE STATISTIC/,/^## §2 — UNITS/p' READ_RULE.md)          # => EMPTY
>
> diff <(sed -n '/^## §6 — THE STATED PRIOR/,$p' ../track_d2r2_prep/READ_RULE.md) \
>      <(sed -n '/^## §6 — THE STATED PRIOR/,$p' READ_RULE.md)                      # => EMPTY
> ```
>
> `analyze_d2r3.py --selftest` runs the §4 check itself and reports it, so the audit is not left to
> a reviewer's diligence.
>
> ### ⚠️ SECOND DISCLOSURE — the adjudicator's author saw CELL R800's summary statistics
>
> [`analyze_d2r3.py`](analyze_d2r3.py) was written by a delegated session, working from this file
> as already-frozen binding text. **While enumerating `summary.json`'s key SPELLINGS against a real
> emitted archive** — which §3.3 and §9 *require*, and which is the h2h `G-TIEARB` fix — **that
> session printed the whole file and therefore saw attempt 2's CELL R800 outcome numbers** (W/D/L,
> winrate, elo, its own deck-paired margin and z). It did **not** open CELL R1600's summary, and so
> never saw `S` or `z_S`. It disclosed this unprompted; it is recorded here rather than dropped.
>
> By the letter of the predecessor's §4 clause — *"has not seen … either cell's summary
> statistics"* — that is a breach, and it is named as one. **Three structural facts bound what it
> could have affected, and all three are mechanically checkable:**
>
> 1. **Every bar was already frozen before that session began.** `TIMING_LO/HI`,
>    `TIMING_FULL_LO/HI`, `N_BURNIN_DECKS`, `BAND`, the tenancy thresholds and this file's §3/§4
>    text all predate it. It was handed bars; it did not choose any.
> 2. **The adjudicator contains no bar of its own.** Every threshold is *imported* from
>    [`d2r3_lib.py`](d2r3_lib.py), and `--selftest` runs a constant audit asserting that the
>    adjudicator's notion of each constant equals the library's and that §3's text still carries it.
>    A bar moved in the adjudicator fails its own selftest.
> 3. **It is an ADJUDICATOR, not a design.** It computes `S` and compares it to §4's conditions; it
>    cannot choose them, and §4's conditions are byte-identical to the predecessor's (audit above).
>
> **What a reviewer should do with this:** treat it as a disclosed, bounded contamination of the
> *instrument's author*, not of the *bars*. If the owner judges it disqualifying, the remedy is
> cheap and total — have a fresh statistics-blind session re-derive `analyze_d2r3.py` from this
> file and `d2r3_lib.py`, both of which are unaffected. **Nothing about the pair, the band, the
> budget or the gates would need to change.** ⚠️ And the general lesson, which is the reason this
> is here at all: **verifying a gate against a real emitted archive — the fix for the two prior
> voids — puts the verifier in contact with that archive's statistics.** A future pair should hand
> that job a key-spellings-only view, not the whole `summary.json`.
>
> ### What changed, exhaustively
>
> The run id (`track_d2r2_prep` → `track_d2r3_prep`); the band (`144000000000` →
> **`149000000000`**, `DESIGN.md` §5) and the smoke leg's disjoint range
> (`144999999000..007` → `149999999000..007`); the probe budget (`k4×1376 = 5504` →
> **`k4×1600 = 6400`**, re-derived in `DESIGN.md` §3.2 against attempt 2's **cell-realized
> saturated** costs rather than a pilot's); this banner; and **§3, which is where the entire
> cost-calibration fix lives** — the burn-in gate (§3.2), the alias-aware `G-SINGLEVAR`, the new
> `G-PROBE`, `G-TIMING-FULL` and `G-TENANCY`, the `champ_timeouts` clause on `G-N`, and a §3.1
> structural test re-run over all TWELVE gates. **Nothing else.**
>
> ### The four CLOSEOUT items this pair was built to answer
>
> [`../track_d2r2_prep/CLOSEOUT_DRAFT.md`](../track_d2r2_prep/CLOSEOUT_DRAFT.md) named four items
> for a successor. Each is answered by a numbered section here, not by a promise:
>
> | # | closeout item | answered by |
> |---|---|---|
> | 1 | *"`G-TIMING` as written is not verifiable by the §9 pilot"* | **§3.2 — the burn-in gate.** The pilot is demoted to a structural smoke with NO timing authority; the equal-time bar is read over a window INSIDE the adjudicated games, at full production W, and enforced LIVE so a fail costs ≈8% of a pair |
> | 2 | *"the re-pick allowance is exhausted and the budget ladder is now bracketed"* | **`DESIGN.md` §3.2** — a fresh pair re-derives the budget from the bracket attempt 2 produced (`k4×1032` → 0.659, `k4×1376` → 0.9428 pilot / 0.8382 cell). This is a fresh pre-registration, not a third re-pick under attempt 2's exhausted allowance |
> | 3 | *"the latent `G-SINGLEVAR` mirror defect"* | **§3, `G-SINGLEVAR`** — written alias-aware from the start, naming both emitter mirrors and their source lines, and turning the mirror into a CROSS-CHECK. Verified against a manifest the harness actually emits, per §3.3 |
> | 4 | *"exclusive tenancy is a precondition, not a courtesy"* | **§3, `G-TENANCY`** + the launcher's census AND live sampler. `DESIGN.md` §6.2 states the exclusive-tenancy window as a funding requirement |

# READ_RULE — rung compression (D2), attempt 3

> **⚠️ BLIND ORDERING. This file is committed BEFORE the band is claimed, BEFORE game 1, and
> BEFORE any statistic of any kind exists.** Its git commit is the proof. The branch that fires
> is taken **VERBATIM**, whatever it is. No owner call adjudicates any outcome; owner
> authorization funds the cell and does not name its answer.
>
> Design: [`DESIGN.md`](DESIGN.md). Launcher: [`run_cells.sh`](run_cells.sh). Adjudicator:
> [`analyze_d2r3.py`](analyze_d2r3.py). Shared primitives: [`d2r3_lib.py`](d2r3_lib.py).
> Run id `track_d2r3_prep`.

---

## §1 — THE STATISTIC, NAMED BEFORE IT EXISTS

**PRIMARY:**

```
S      = M_R800 − M_R1600, deck-paired over n_common decks, points/game
         M_cell = the cell's deck-paired mean margin (probe minus rung)
se(S)  = computed from the realized paired per-deck differences (NOT assumed —
         DESIGN §4 gives the PRE-REGISTERED EXPECTATION, se(S) ≈ 1.25 pts;
         the readout uses the REALIZED dispersion from the actual records)
z_S    = S / se(S)        (convention: eval_fair_puct._paired_z)
```

**SECONDARY, reported on every branch, never a branch input:** each cell's elo ± 1σ vs h800, its
winrate, its own deck-paired margin, and the realized elo-per-point scale used to convert `S` to
an elo-equivalent (DESIGN §4.3's ~15.6 elo/pt is the pre-registered anchor; the readout recomputes
it from this run's own records and reports both).

⚠️ `z_S` is READ off the analyzer's computed value; a from-scratch recomputation from the raw
per-game records is printed alongside it. A disagreement beyond floating-point tolerance is
`U-UNREADABLE`. The recomputation is a WITNESS, never a branch input.

---

## §2 — UNITS

Primary unit: **points/game of final-score margin, probe-minus-rung, deck-paired.** Elo is a
derived DISPLAY quantity, converted via the realized scale (§1), never the unit a bar is set in.
`n` in every bar below is in **DECKS** (a paired statistic; each deck is 2 games) except where a
games-count is named explicitly. 200 decks = 400 games per cell (the roadmap's committed n); the
§4.4 extensions are unfunded and change nothing here unless a fresh pair funds them.

**The COST unit is `ms/move`, and the equal-time ratio is `CANDIDATE / RUNG`.**
⚠️ **Field-name trap (DESIGN §3.3, inherited from the jcz precedent):** in `eval_fair_puct`,
`champ_prefix_ms_per_move` is the **CANDIDATE** side — the opposite convention from
`eval_puct_priors`. Any read-out that swaps them inverts the timing reading. Both the live gate
and the adjudicator take this quantity from one implementation,
[`d2r3_lib.timing_ratio`](d2r3_lib.py), so the trap can be got wrong at most once.

---

## §3 — PRECONDITIONS (every one must PASS, else `U-UNREADABLE`)

Fail-closed. **ABSENT is FAIL.** Each gate is read at the manifest top level, then at `config.*`,
then — for the witnesses the emitter files inside `config` sub-dicts — at those containers, and
the adjudicator reports which address resolved (the house `G-BAND`/`G-J1` fix precedent).

| id | proposition | VOIDS on |
|---|---|---|
| `G-BAND` | both cells' `manifest.json` `seed_start` == 149000000000; record-derived deck sets agree; `n_common` == 200 | any mismatch |
| `G-SINGLEVAR` | the two cells' `config` blocks differ in **EXACTLY** `rung.sims`, `opponent.sims` and `opponent.label` — the one experimental variable plus its **two named emitter mirrors** (§3.3) — **AND** in each cell the mirrors are consistent with it: `opponent.sims == rung.sims` and `opponent.label == "HeuristicMCTS(h" + str(rung.sims) + ")"` | any fourth differing key; `rung.sims` absent from the diff; any mirror inconsistent with `rung.sims` in either cell |
| `G-PROBE` | both cells, identically: `config.champion.k_dets` == 4, `config.champion.sims_per_det` == 1600, `config.champion.total_sims` == 6400 (and `k_dets × sims_per_det == total_sims`); `c_puct` == 1.5; `exact_k` == 2; backend `rust`; candidate tie-arbiter absent or disarmed | any deviation, or a candidate tie-arbiter armed |
| `G-RUNG` | both manifests: `config.rung.c` == 3.0, `config.rung.agent` == `"HeuristicMCTS"`, `config.rung.leaf_hash` identical across cells, `config.rung.sims` == 800 (R800) / 1600 (R1600) | any deviation |
| `G-LEAF` | `config.cand_leaf_hash` == `a36d2e15a3b3d71d` in BOTH cells | mismatch or absence |
| `G-RULES` | `rules_profile.name` == `"fixed_v1"` and `r9_env_ok` == true, in BOTH cells | anything else |
| `G-TOOL` | same `carc_rs_version` and `tile_data_semantic_digest` across both cells; same code rev in both; `BLIND_COMMIT` in both manifests, at BOTH searched addresses, equal to the launcher's frozen value | any mismatch; a manifest carrying the placeholder |
| `G-N` | 400 games scored in EACH cell; `n_failed` == 0; **`champ_timeouts` == 0 in BOTH cells** (§3.4 — the only channel by which box load could reach a game OUTCOME rather than only its clock) | short of 400 completed games; any solver timeout |
| `G-TIMING` | **CELL R800's BURN-IN WINDOW** — decks `149000000000 .. 149000000039`, both seatings, 80 games — recomputed from the per-game records by [`d2r3_lib.read_burnin`](d2r3_lib.py) is **COMPLETE** (all 80 records present, none malformed) **AND** its realized ratio is inside `[0.85, 1.20]` | outside the interval; an incomplete or malformed window; either timing field absent |
| `G-TIMING-FULL` | **CELL R800's** whole-cell ratio, from `summary.json` **and** cross-checked against a from-records recomputation agreeing to 1e-6 relative, is inside `[0.75, 1.35]`. ⛔ **CELL R1600 IS NOT GATED BY THIS OR BY `G-TIMING`, AND AN ADJUDICATOR THAT APPLIES EITHER TO IT IS WRONG** — R1600's rung doubles its sims while the probe does not, so its ratio is ≈0.4 **by construction** and would void the pair mechanically. R1600's ratio is PRINTED (§4.3 item 2), never adjudicated | outside the interval **for CELL R800**; the two computations disagreeing |
| `G-TENANCY` | CELL R800's tenancy sampler ran for the cell's whole window, and **no `TENANCY_CONFIRM_SAMPLES` (=2) consecutive samples** show foreign CPU ≥ 100% of one core | a confirmed foreign-tenant window; an absent or truncated sampler log |
| `G-SAT` | CELL R800's probe winrate vs h800 is inside `[0.50, 0.90]` | outside — the margin statistic is compressed at a floor/ceiling and does not read as a spacing measurement |

`n_failed` on a healthy rust/python mixed cell is expected near-zero but not guaranteed exactly
zero (the b32v64 precedent saw a 0.100% pre-existing rust engine panic-fail class); a nonzero rate
below 2% is reported and does not by itself fire `G-N`, matching the campaign's `<=2%` floor
precedent — but it is printed on every branch regardless of outcome (§4.3).

---

### §3.2 — THE BURN-IN GATE: how `G-TIMING` is verified under the load regime that produces the adjudicated games

⛔ **THIS SECTION IS THE REASON ATTEMPT 3 EXISTS. It is pre-registered here, before game 1, in
full, including what happens on FAIL.**

**The defect it replaces.** Attempts 1 and 2 verified the equal-time ratio on a **§9 pilot** —
`--n 16` on a throwaway seed range — and then re-checked the same bar on the 400-game cell. Those
are two different measurements. A 16-game leg has **fewer games than workers** at W=22: the box is
never fully occupied, and the two sides of the ratio do not degrade equally when it becomes so.
Attempt 2 measured the gap exactly: **the python rung went 881 → 1103.1 ms/move (+25.2%) and the
rust probe went 831 → 924.7 ms/move (+11.3%)** from pilot to cell, moving the ratio from an in-bar
0.9428 to an out-of-bar 0.8382. **A pilot at unsaturated W cannot predict a saturated-W ratio, and
no amount of care in reading one fixes that.**

**The fix, stated as a property:** *the timing gate is verified under the exact load regime that
produces the adjudicated games, on games that are themselves adjudicated.*

**The mechanism.**

1. **CELL R800 runs FIRST**, as ONE `--n 400 --paired` invocation at production `W=22`, exclusive
   tenant. There is no separate timing leg and no separate output directory.
2. The **burn-in window** is the cell's own **first 40 decks — seeds `149000000000` through
   `149000000039`, both seatings, 80 games.** It is defined by **SEED, never by arrival order**:
   `eval_fair_puct._build_work` enumerates `(seed_start+i, 0), (seed_start+i, 1)` in order, so
   these are the first 80 tasks dispatched; but the pool completes out of order, so an
   arrival-order window would not be reproducible by an adjudicator. A seed-defined window is.
3. A **live watcher** ([`d2r3_lib.py watch`](d2r3_lib.py)) polls the cell's per-game record files —
   which `eval_fair_puct` writes atomically as each game finishes — until **all 80** are present,
   then computes the ratio and adjudicates it against `[0.85, 1.20]`.
4. **The live gate and the post-hoc gate are the SAME CODE.** The watcher and
   [`analyze_d2r3.py`](analyze_d2r3.py) both call `d2r3_lib.read_burnin()`; neither carries its own
   arithmetic or its own thresholds. If they could disagree, the live gate would be a courtesy;
   because they cannot, `G-TIMING` in §3 above *is* the gate that ran.

⭐ **VALIDATED RETROSPECTIVELY, BEFORE GAME 1.** `DESIGN.md` §3.2a runs this pair's own
`d2r3_lib.read_burnin()` over attempt 2's completed CELL R800 archive and asks what this gate would
have done. Answer: the burn-in window reads **0.8333** against that cell's realized whole-cell
**0.8382** — an error of **0.6%**, where the pilot that actually gated it was **12.5%** off in the
wrong direction. **The gate would have fired correctly, at ~10 minutes and ~3.3 core-h** (measured: the 80th burn-in record landed with 81 of 400 games complete, 18.5% of that cell's wall). The window
is marginally *more pessimistic* than its own cell, which for a fail-closed precondition is the
right direction. This is a cost-only computation over per-game timing fields; no outcome field is
read (§0 item 3).

⚠️ **WHAT A BURN-IN PASS DOES NOT SETTLE — named before game 1, not discovered at read time.** The
window is the cell's FIRST 40 decks, so it necessarily contains the startup transient: worker
ramp-up, a cold page cache, the `--shared-claim` scan. A PASS is therefore **not** a guarantee that
the whole-cell ratio lands in bar; it is a cheap, early, same-regime kill for the failure mode that
actually happened. Two things bound the residual risk, and both are stated rather than assumed:
(i) **measured, the transient is worth ≈0.6%** — on attempt 2's archive the window read 0.8333
against a whole-cell 0.8382, *below* it, i.e. the transient makes the window slightly
**pessimistic**, not optimistic; and (ii) `G-TIMING-FULL` is the backstop that reads the whole cell
at `[0.75, 1.35]` (§3.5). **A readout must not narrate a `G-TIMING` PASS as "the cell ran at equal
time throughout" — it means the enforced window did, and `G-TIMING-FULL` says the rest did not
drift out of tolerance.**

**ON PASS.** The cell continues to 400 games. **The 80 burn-in games COUNT.** They are the same
config, the same band, the same invocation and the same process pool as the other 320 — there is
no sense in which they are a pilot, and discarding them would be discarding cell data to no
purpose. `BURNIN_R800.json` records the realized reading. CELL R1600 starts only after CELL R800
completes and that file reads `"pass": true`.

**ON FAIL** (ratio outside the bar) **or on TIMEOUT** (the window still incomplete after 5400 s —
FAIL-CLOSED, an unreadable window is not a passed window):

- the launcher **kills CELL R800** (main pid first, settle, then surviving pool members by exact
  pid — house rule `feedback_isolate_destructive_tool_calls`), writes `ABORT_BURNIN_R800.json` with
  the realized reading and the bar, **does NOT start CELL R1600**, and clears `RUN_LIVE.json`;
- the branch is **`U-UNREADABLE`** (§4), named on `G-TIMING` with its realized value, exactly as if
  the gate had fired at adjudication — because it has;
- **band `149000000000` is RETIRED with ~40 decks of records on it.** It is spent. There is **NO
  re-pick, NO resume and NO salvage under this pair** — a resumed cell would carry burn-in games
  measured in a regime the pair has just declared out of bar;
- **the cost of this outcome is ≈3.6 core-h / ≈10 min wall against the pair's ≈43.9 core-h /
  ≈2.0 h** — **8.2%** (`DESIGN.md` §6, and MEASURED, not estimated: on attempt 2's own archive the
  80th burn-in record landed with **81 of 400 games complete, 18.5% of that cell's wall**, because
  the pool dispatches in task order and the games are of similar length). A cost-calibration void
  now costs under a tenth of what attempt 2's cost, which is the whole practical point of the
  section.

⛔ **NO RE-PICK CLAUSE. This pair has NO `--sims` re-pick allowance of any kind, on any leg.**
Attempt 2's allowance was exhausted twice over and does not renew here or anywhere. The probe
budget `k4×1600 = 6400` is FROZEN by this commit. **A burn-in FAIL is a fourth-attempt decision for
the owner, not a knob for the launcher, the orchestrator, or a future session** — and a fourth
attempt needs a fresh pair, a fresh band, and a fresh funding decision.

---

### §3.3 — THE TWO EMITTER MIRRORS, NAMED BEFORE GAME 1 (the `G-SINGLEVAR` fix)

Attempt 2's adjudicator found, *after the fact*, that `G-SINGLEVAR` as written ("the two cells'
`config` blocks differ in exactly `rung.sims` … nothing else") **would read FAIL on every healthy
run of this launcher.** The harness mirrors the single CLI value `--rung-sims` into two further
manifest addresses, so a literal key-set diff of two healthy cells always shows three differences,
not one. Attempt 2 survived it only because the frozen §3.1 had committed the answer "structural,
not clerical" — i.e. an adjudicator had to *interpret* the gate rather than *apply* it. That is the
same defect class as attempt 1's unsatisfiable `G-TOOL` sub-clause, and the closeout named it.

**It is fixed here by writing the gate alias-aware from the start, with the mirrors named at their
source lines** (`scripts/classical_search/eval_fair_puct.py`, rev as of this freeze):

| address | line | value |
|---|---|---|
| `config.rung.sims` | 4450 | `args.rung_sims` — **THE EXPERIMENTAL VARIABLE** |
| `config.opponent.sims` | 4395 | `args.rung_sims if args.opponent == "h800" else None` — **MIRROR** |
| `config.opponent.label` | `_opp_label`, 1532–1535 | `f"HeuristicMCTS(h{args.rung_sims})"` — **MIRROR** |

All three are renderings of one CLI value. They are not a second experimental axis, and they cannot
independently disagree.

**The gate therefore does two things rather than one.** It (a) requires the diff set to be exactly
`{rung.sims, opponent.sims, opponent.label}` — a fourth differing key still VOIDS, unchanged in
strictness — and (b) **turns the mirror into a cross-check**: in each cell it requires
`opponent.sims == rung.sims` and `opponent.label == "HeuristicMCTS(h"+str(rung.sims)+")"`. A gate
that used to need an adjudicator's charity now catches a class of defect the original could not:
a manifest whose mirrors have drifted apart is no longer a healthy manifest.

⚠️ **This is a gate ADDRESS claim, and the h2h `G-TIEARB` lesson is that address claims must be
checked against what the harness EMITS, not against what a design document describes.** So it is
checked mechanically, before game 1, in two places:

- [`analyze_d2r3.py --selftest`](analyze_d2r3.py) **seeds its passing fixture from a REAL manifest
  read off disk**, not from a synthesized dict. The h2h post-mortem is explicit that a 20/20 green
  selftest certified an instrument that could not read any real archive, precisely because its
  fixture generator "synthesises the manifest `READ_RULE.md` describes, rather than one the
  analyzer of record actually emits."
- **the launcher's smoke leg ENDS by running this pair's own adjudicator against the smoke
  archive** and requires it to fail **only** on the band/N gates that a 16-game throwaway archive
  cannot satisfy by construction. This is the standing rule the h2h `AMENDMENTS.md` proposed, and
  this pair is the first to adopt it. A smoke that cannot be adjudicated is a launch blocker.

---

### §3.4 — WHY CO-TENANCY IS A TIMING THREAT AND NOT AN OUTCOME THREAT (the `G-TENANCY` scope)

Attempt 2 disclosed that an Android cross-compile + gradle build occupied the box during CELL
R800's final ~10 minutes. The house rule (`feedback_no_agent_compute_beside_eval`) is that a timing
measurement is an **exclusive tenant**; the disclosure was honest and the direction of the bias was
correctly declared undetermined.

**Scope, argued rather than assumed.** Every game in this cell is deterministic given its deck seed
and seat: the candidate's PIMC search runs a fixed sim budget, and the rung runs a fixed
`HeuristicMCTS` sim budget. Box load changes how long that takes, not what it decides. **There is
exactly one channel by which load could reach an OUTCOME: an exact-solver timeout**, which would
change the move actually played. `G-N` therefore requires **`champ_timeouts == 0` in both cells**,
which closes that channel; with it closed, co-tenancy is a pure timing threat, and timing is gated
only on CELL R800. `G-TENANCY` is scoped accordingly. The sampler nevertheless runs for **both**
cells and both logs are printed on every branch — a reader is entitled to see the tenancy of the
whole run even where no bar reads it.

**Why a preflight census alone is not enough — the mechanism attempt 2 actually suffered.** The
contaminating build **started after the cell did.** A census at launch would have found the box
clean and passed. `G-TENANCY` is therefore backed by a **sampler that runs for the cell's whole
life**, taking instantaneous per-process CPU readings (from two `/proc/<pid>/stat` reads — ⚠️ `ps
-o %cpu` is a whole-lifetime average and is useless for this) and partitioning them into the
launcher's own process tree versus everything else. Two consecutive samples over the bar and the
launcher **aborts the cell on the same path as a burn-in fail**. A single transient is not a
co-tenant; two in a row is.

---

### §3.1 — the structural test, applied to every gate above, BEFORE any outcome is known

**RE-RUN IN FULL for this successor, over ALL TWELVE gates.** The question is exactly one, asked of
each gate: *would this gate fail on every healthy run of this launcher?* A gate that would is fixed
BEFORE game 1, never discovered after. **A partial structural test is the failure mode, not a
lighter version of the test** — attempt 1's audit covered four of nine gates and shipped an
unsatisfiable `G-TOOL`; attempt 2's covered all nine and still shipped a `G-SINGLEVAR` that only an
adjudicator's charitable reading could pass. **This time the answers are not merely reasoned, they
are EXECUTED: the launcher's smoke leg runs the adjudicator against a real archive (§3.3), so a
gate that cannot read what the harness emits is a launch blocker rather than a readout surprise.**

- **`G-BAND`** — `seed_start` is `--seed-start`, echoed into the manifest by the harness; the
  launcher pins it from `PINNED_BAND` and accepts a `--band` that only CONFIRMS it (a disagreeing
  `--band` is fatal), and BOTH cells take it from the one shared `COMMON` array, so the two cells
  cannot disagree by construction. `n_common == 200` follows from `--n 400 --paired` in that same
  array. **Fails on a healthy run? NO.**
- **`G-SINGLEVAR`** — guaranteed by the launcher building both cells' argv from one shared `COMMON`
  array; the property is structural, not clerical. ⚠️ **The mirror defect that made this gate
  unsatisfiable-as-literally-written in both prior attempts is fixed at the level of the gate's own
  TEXT** (§3.3), not left to an adjudicator's reading, and the alias list is checked against a real
  emitted manifest by the smoke leg. The cross-check half (mirrors consistent with `rung.sims`) is
  satisfied by construction — all three addresses render the same CLI value. **NO.**
- **`G-PROBE`** — new for this pair, and it exists because neither prior pair gated the probe's own
  budget at all (attempt 2's readout records "No §3 gate covers the probe's own `--sims`; recorded
  as context"). `config.champion.{k_dets,sims_per_det,total_sims}` are harness-written from the
  `--k-dets`/`--sims` in the ONE shared `COMMON` array, identical in both cells by construction.
  ⚠️ It also disambiguates a deliberate numeric collision: the candidate's `--sims 1600` and CELL
  R1600's `--rung-sims 1600` are the same integer on different axes, and this gate is what makes
  that checkable rather than merely confusing. **NO.**
- **`G-RUNG`** — `config.rung.{c,agent,sims,leaf_hash}` are written by the harness; `c == 3.0` comes
  from `RUNG_C = DEFAULT_C` inside `eval_fair_puct.py` (DESIGN §2.1), `sims` from `--rung-sims` (the
  one experimental axis), and the rung leaf is ALWAYS env `DEFAULT_CONFIG` — the harness never lets
  `--cand-leaf-json` reach it. The VALUE half is checked, not assumed: `preflight_leaf` asserts the
  rung resolves the CL-022 ruler `42af12fce22e1a0f` before game 1. **NO.**
- **`G-LEAF`** — voided attempt 1; FIXED and VERIFIED on attempt 2's real cells. The launcher passes
  `--cand-leaf-json champion_leaf_curve125.json` in `COMMON`, and `preflight_leaf` builds one
  champion **through the harness's own module** and asserts the hash equals `a36d2e15a3b3d71d`
  before game 1, refusing to start otherwise. **NO.**
- **`G-RULES`** — voided attempt 1; FIXED and VERIFIED on attempt 2's real cells. The launcher
  exports `CARCASSONNE_FIX_R9` at file scope before any leg, and `assert_r9_env` refuses to run if
  it is unset or not truthy. (`fixed_v1` cannot apply R9 itself — import-time farm derivation plus
  a Rust `OnceLock`.) **NO.**
- **`G-TOOL`** — three propositions wearing one id, all three VERIFIED on attempt 2's real cells.
  (a) `carc_rs_version` / `tile_data_semantic_digest` are harness-written and satisfiable by
  construction on one build. (b) same code rev: `snapshot_rev` records `HEAD` plus a code-path
  dirty fingerprint at start, `assert_rev_unmoved` re-checks before EACH cell, and
  `require_clean_code` refuses a real cell on dirty CODE (`LAUNCH_DIRTY=1` + a mandatory logged
  reason is the only override). ⚠️ That refusal is scoped to CODE paths ON PURPOSE — this repo's
  tree carries churning measurement artifacts at all times and the launcher must drop
  `RUN_LIVE.json` under `measurement/`, so a whole-tree dirty refusal would fire on every healthy
  run, the exact defect class this section removes. (c) `BLIND_COMMIT` reaches BOTH searched
  addresses via the harness's additive `--stamp-key` passthrough. **NO, on all three.**
- **`G-N`** — 400 games per cell follows from `--n 400` in `COMMON`; the 2% failure tolerance
  matches the campaign's own precedent. ⚠️ The new `champ_timeouts == 0` clause is a genuine
  property of the DATA, not of the launcher: a solver timeout is possible in principle. It read 0
  on attempt 2's 800 games at a LARGER exact-K workload profile than this pair changes, so it does
  not fail on a healthy run — but it CAN fail, and that is the gate doing its job (§3.4: a timed-out
  solve is the one way box load reaches an outcome). **NO.**
- **`G-TIMING`** — the interval `[0.85, 1.20]` is CARRIED VERBATIM from both prior pairs; **no bar
  moved, the WINDOW moved.** Satisfiability is now enforced rather than argued: the live watcher
  adjudicates this exact bar on this exact window with this exact code, and a run that reaches
  adjudication has already passed it. The gate can still FAIL here only if the records changed
  between the two readings, which would itself be the finding. ⚠️ Newly honest about the direction
  of risk: this gate CAN fail on a healthy run — that is its entire purpose, and the burn-in
  mechanism exists so that when it does, it costs ≈8% of a pair instead of 100%. **Does it fail on
  EVERY healthy run? NO.**
- **`G-TIMING-FULL`** — `[0.75, 1.35]` is a DRIFT envelope around the enforced window, derived in
  `DESIGN.md` §3.5 from measured within-regime variation (3.3% between attempt 2's two cells) and
  sized to be wider than any within-saturated-regime drift the program has measured and narrower
  than the regime CHANGE that voided attempt 2 (11%). Both cells report the two timing fields by
  construction. The cross-check half (summary vs from-records recomputation) is satisfiable because
  `d2r3_lib.timing_ratio` is a transcription of `eval_fair_puct._summary`, and
  `tests/test_d2r3_instrument.py` asserts the two agree to 1e-6 **on a real completed archive**.
  **NO.**
- **`G-TENANCY`** — the sampler is started by the launcher for every real cell, so its log exists by
  construction; the bar (100% of one core, sustained over two consecutive 60 s samples) sits far
  above an idle box's foreign load and far below any real build or sibling run. ⚠️ Named plainly:
  **this gate makes the orchestrator's own conduct a precondition.** An agent that runs compute on
  this box during the cell — a test suite, a build, a sibling measurement — will abort the run. That
  is intended, and `DESIGN.md` §6.2 states the exclusive window as a funding requirement precisely
  so it is scheduled rather than hoped for. **Does it fail on EVERY healthy run? NO.**
- **`G-SAT`** — the probe was measured non-saturating against h800 at this budget class, so
  `[0.50, 0.90]` has room on both sides. This gate is a genuine PROPERTY OF THE DATA, not of the
  launcher — a healthy run CAN fail it if the champion leaf at k4×1600 saturates against h800 where
  the 2752 and 5504 cells did not. That is the gate doing its job (a rails reading is not a spacing
  reading), and it is stated here so a `G-SAT` void reads as the pre-registered outcome it is.
  **NO.**

Answer for every gate: **NO** — none fails on every healthy run of this launcher.

---

## §4 — THE BRANCHES

Read **in order**. The FIRST whose condition holds is the branch, taken verbatim.

### `D2-COARSE` — the spacing is real and large
**Condition:** all §3 gates PASS **AND** `z_S ≥ 2.0` **AND** `S ≥ 2.5 pts`.

**Says:** the ladder's unit is a genuine unit at this rung — the CL-023 reading (+55.2 elo ≈ 3.5
pts) is corroborated on a fresh band, with the ruler's own rung (c=3.0, §2 of `DESIGN.md`), under
a fixed non-saturating probe. **Licenses:** citing the h800→h1600 gap as a real, program-usable
unit at this budget. **Does NOT license:** any claim about spacing at other rungs (h1600→h3200,
etc — that is §6.1(a) of `DESIGN.md`, unfunded), nor a ruler change of any kind.

### `D2-COMPRESSED` — the spacing resolves but is small
**Condition:** gates PASS, `z_S ≥ 2.0`, `S < 2.5 pts`.

**Says:** the spacing is real but compressed relative to the CL-023 magnitude — ladder distances
ARE denominated in a compressed unit at this rung, and every elo quoted against this rung of the
ladder inherits that compression. **Licenses exactly one thing:** an advisory annotation on CL-023
and on the roadmap's D0/D1 lines, flagging that the h800→h1600 increment measured elsewhere may
not carry directly. **Does NOT license:** a ruler change, a re-grading of any existing claim, or a
retraction of CL-023 (CL-023's own band and knobs are untouched by this cell — see §5).

> ⚠️ **THE COARSE/COMPRESSED BOUNDARY IS DISPERSION-CONDITIONAL — named here, before game 1, not
> discovered at read time.** At the committed `se(S) = 1.25 pts` (DESIGN §4.2), `z_S ≥ 2.0`
> arithmetically implies `S ≥ 2.0 × 1.25 = 2.5` — so at the committed dispersion,
> `D2-COARSE`'s and `D2-COMPRESSED`'s conditions **coincide exactly at the boundary**: any run
> that clears `z_S ≥ 2.0` at or above the committed `se(S)` lands in `D2-COARSE` by construction.
> **`D2-COMPRESSED` is reachable only when the REALIZED `se(S)` prints BELOW 1.25 pts** —
> equivalently, at the `S = 2.5` boundary, `se_realized < S / z_S = S / 2.0`. That is, this branch
> requires the run's actual dispersion to come in TIGHTER than the pre-registered expectation; it
> is not reachable at or above the committed `se(S)`, whatever `S` and `z_S` read.
> ⛔ **Consequence for the readout: a `D2-COARSE` finding realized at `se(S) ≥ 1.25 pts` must NOT
> be narrated as "compression is ruled out."** At that dispersion the design cannot separate a
> genuinely large, uncompressed spacing from a moderately compressed one that still clears 2σ —
> it can only say the spacing is real and at least 2.5 pts. Distinguishing "large" from
> "moderately compressed but still significant" needs a realized `se(S)` tighter than committed,
> which is a property of this run's actual data, not something the design can guarantee before
> game 1. §4.3 item 4 prints `se_realized` beside `S` and `z_S` specifically so this reachability
> condition is checkable on every branch, not just on `D2-COMPRESSED`.

### `D2-BOUNDED-NULL` — no spacing detected, and the bound is stated
**Condition:** gates PASS, `|z_S| < 2.0`.

**Says:** no spacing resolves at this power. State the two-sided 95% bound on `S` in points AND
its elo-equivalent, and say plainly that **n=200 cannot separate the results.csv reading (+20 elo)
from zero** (DESIGN §4.3) — this was known and stated before game 1. **This is NOT a zero and must
never be reported as one.** It is consistent with (a) the small prior being correct and simply
unresolved at this n, (b) genuine band-to-band variation of the kind CL-068 already measured, and
(c) the equal-time probe (§3.3 of `DESIGN.md`) adding enough of its own noise to wash out a real
but modest rung gap — this cell **cannot separate these**. Licenses nothing beyond stating the
bound; the DESIGN §4.4 n=400/n=800 extensions are the pre-priced path to resolving it further, and
remain unfunded until a fresh owner decision.

### `D2-REVERSED` — h1600 measures WEAKER than h800 against the probe
**Condition:** gates PASS, `z_S ≤ −2.0`.

**Says:** the deeper heuristic rung measures behind the shallower one at 2σ against this probe.
Report it plainly; do not explain it away in the readout. **Pre-registered follow-up: a direct
rung-vs-rung head-to-head (DESIGN §8 item 1), not a re-run of this cell** — this cell's probe-side
noise (§3.3 of `DESIGN.md`) is a live confound for a reversal specifically, since the probe itself
is one more source of variance sitting between the two rungs.

### `U-UNREADABLE`
**Condition:** ANY §3 gate FAILS.

**Says:** no strength or spacing statistic from this run is adjudicated, quoted, or entered in
`results.csv` as a verdict. The failed gate is named with its realized value.
`U-UNREADABLE` is a fully acceptable outcome.

⚠️ **If an instrument defect is found after a first adjudication, the session that writes the fix
MUST be a session that has not seen `S`, `z_S`, or either cell's summary statistics** — the jcz
precedent's binding instrument-fix discipline, carried here verbatim. Bars do not move. §4 is not
edited post hoc.

> **§4.1 — THE BURN-IN ABORT IS A `U-UNREADABLE`, NOT A NEW BRANCH.** If the run aborts at the
> burn-in gate (§3.2), there is no second cell and no `S`. The branch is `U-UNREADABLE`, named on
> `G-TIMING` with the realized burn-in ratio; `G-N` will also read FAIL (80 of 400 games), and the
> readout says so. [`analyze_d2r3.py`](analyze_d2r3.py) runs on the partial archive and prints the
> §4.3 companion table for everything that exists, exactly as §4.3 requires on every branch. **No
> `S` is computed from a burn-in-aborted archive** — there is no second cell to difference against,
> and the readout must say that rather than printing a one-cell number that a later reader could
> mistake for one.

---

## §4.3 — THE COMPANION TABLE (printed on EVERY branch including `U-UNREADABLE`)

Per cell — CELL R800 and CELL R1600, each:

1. n games, n decks, seat balance, W/D/L, winrate + its z, elo ± 1σ + 95% CI vs h800, own
   deck-paired margin ± se and its z, n_failed, failure rate (stated even when zero),
   `champ_timeouts`.
2. `champ_prefix_ms_per_move`, `rung_ms_per_move`, realized whole-cell time ratio,
   `solver_secs_per_game`, **and — for CELL R800 — the BURN-IN window's own
   `champ_prefix_ms_per_move`, `rung_ms_per_move`, ratio, completeness, and the seed range it
   covered.**
3. band, both leaf hashes (`config.cand_leaf_hash`, `config.rung.leaf_hash`), rules profile, code
   rev, `carc_rs_version`, probe budget (`k_dets × sims_per_det = total_sims`).
4. **the tenancy roll-up**: number of samples, peak foreign CPU %, longest consecutive over-bar
   run, and the top foreign processes by peak CPU — printed for BOTH cells even though only CELL
   R800's is gated (§3.4).

Then, once:

5. `S`, its computed `se(S)` (beside the DESIGN §4.2 pre-registered expectation, 1.25 pts), `z_S`,
   `n_common`, and the elo-equivalent conversion with the scale used. **This `se(S)` — printed here
   as `se_realized` — is also the `D2-COMPRESSED`-reachability witness (§4's boundary note): that
   branch is reachable only where `se_realized < 1.25 pts`, so this line is what a reader checks to
   see whether a `D2-COARSE` finding had any room to have come out `D2-COMPRESSED` instead.**
6. Every §3 gate with its realized value and which manifest address resolved it.
7. The DESIGN §1 table (CL-023's +55.2 elo, results.csv's +20.0 elo) reprinted beside the
   readout's own `S`/elo, so a reader never has to leave the readout to see what this cell was
   adjudicating between.
8. **The cost ledger**: realized wall and core-h per cell against `DESIGN.md` §6's projection, and
   the realized probe cost in ms per total-sim — the quantity a fourth attempt, or any future
   equal-time pairing, would calibrate against (`DESIGN.md` §3.2).

---

## §5 — WHAT NO BRANCH DOES

No branch flips `governance/PRODUCTION.yaml`. No branch licenses a leaf or search change. No
branch re-rates the champion. No branch retires or amends the CL-023 record itself (the CL-023
band, knobs, and numbers stand exactly as published; a `D2-COMPRESSED` result licenses an
*annotation*, not an edit, per §4). No branch transfers to the F5/walled-era ladder's absolutes
(DESIGN §3.4). No branch licenses a second band or extends `n` beyond 200 decks/cell — that needs
a fresh owner funding decision against the DESIGN §4.4/§6.1 priced menu. No branch authorizes
editing `experiments/results.csv`'s five historical mis-stamped rung-`c` cells (DESIGN §2.3) —
that correction is an owner decision independent of this cell's outcome, and is not gated by it in
either direction.

**Added for this pair, and binding:** no branch licenses a `--sims` re-pick, a resumed or salvaged
burn-in-aborted cell, or a fourth attempt (§3.2). No branch adjudicates, quotes, or carries any
statistic from attempts 1 or 2 — both are `U-UNREADABLE` and remain so; the only things this pair
inherits from them are COST figures, DISPERSION calibration, and instrument machinery, enumerated
in §0's blindness disclosure.

---

## §6 — THE STATED PRIOR, RECORDED BEFORE GAME 1

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
