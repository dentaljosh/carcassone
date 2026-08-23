# `B = 32` vs `B = 64` TIE-ARBITER LADDER GAME CELL — READ-OUT

generated: 2026-08-23T03:06:30Z

## BRANCH: `U-UNREADABLE`

**U-UNREADABLE — A §3 PRECONDITION FAILED.**

⛔ A FAILING GATE SUPPRESSES THE VERDICT. Report cost, integrity, firing rates, divergence, the failed-record accounting, and EVERY gate with its realized value — all 13, never short-circuited at the first failure. Nothing closes, nothing is licensed, nothing is re-labelled. ⛔ The read-out may NOT print D, z_D or a branch label as if adjudicated.

## The committed `EQUIV` bar — READ from `WORKERS.conf`, not from code

- `TOLERANCE_PTS` = **0.93** pts/game · `EQUIV_SHAPE` = **`one_sided`**
- predicate: UB95(D) = D + 1.645*se_D <= TOLERANCE_PTS  —  ONE-SIDED NON-INFERIORITY at 95%: the ONE-SIDED 95% UPPER BOUND ON THE COST is below the tolerance. ⚠️ 1.645 here is z_{0.95}, the ONE-SIDED 95% critical value — the read-out must say 'one-sided 95% upper bound', NEVER '90% CI' (READ_RULE §4). ⚠️ The |·| is dropped and the negative arm is governed by BRANCH ORDER, not by the predicate: L-REVERSED (z_D <= -2.0) is branch #2 and pre-empts L-SATURATED (#4) by FIRST-MATCH-WINS (§4.4).
- source: `measurement/tiearb_widening_20260817/b32v64_cell/WORKERS.conf` — ⛔ changing those two committed lines changes this adjudicator with NO code edit; there is no default.

## §4.0 — the reachable branch set, stated BEFORE the run

- reachable: ['U-UNREADABLE', 'L-REVERSED', 'L-RISING', 'L-SATURATED', 'L-AMBIGUOUS']
- unreachable: **none**
- modal pre-run expectation: **L-SATURATED** — at a true D = 0 the EFFECTIVE L-SATURATED probability is 0.556 > 0.444 ⇒ L-SATURATED is the modal pre-run expectation under the ruled shape
- `L-SATURATED` window at the committed `se(D)`: **0.1003** · P(fires | true D = 0) = **0.556** (EFFECTIVE; raw 0.5788, L-REVERSED takes 0.0228 first)
- at the offline bracket top: **0.4459** (EFFECTIVE, committed law)
- `n` for 80% power: 2728 decks/cell (committed law) / 2240 (realized law) — ⚠️ those are RAW one-sided figures (se_D <= 0.93/(1.645+0.8416) = 0.37400); the EFFECTIVE power at that n is ~0.777, because L-REVERSED still takes ~2.3% of the lower tail first
- ⇒ IF B = 32 IS EXACTLY AS GOOD AS B = 64, THIS CELL NOW HAS A ~56% CHANCE (~63% AT THE REALIZED DISPERSION) OF BEING ABLE TO SAY SO — up from ~16% (~30%) under the drafted two-sided shape, at the same tolerance, the same n, and no extra spend. ⚠️ It is still not a well-powered test: ~44% of the equal-rungs world, and ~55% of the bracket-top world, still reads L-AMBIGUOUS. That is a declared property of the owner-funded design, not a failure of it. ⛔ No read-out may present L-AMBIGUOUS as evidence of a difference.

## §4.3 item 6 — ALL 13 §3 gates, with their REALIZED values, never short-circuited

| gate | scope | marker | ok | realized |
|---|---|---|---|---|
| `G-BAND` | [RUN] | [pre-run]+[post-cells] | **FAIL** | band=140000000000 same_decks=False |
| `G-DIVERGE` | [RUN] | [post-cells] | PASS | 1−f0=0.9880 vs floor 0.1 |
| `G-FAILED` | [RUN]+[PER-CELL] | [post-cells] | PASS | F_CELL_B64=0 F_CELL_B32=3, total 3 |
| `G-FIRE` | [PER-CELL] | [post-cells] | PASS | CELL_B64 phi_eff=17.472; CELL_B32 phi_eff=17.515 |
| `G-J1` | [PER-CELL] | [post-cells] | PASS | CELL_B64=a36d2e15a3b3d71d; CELL_B32=a36d2e15a3b3d71d |
| `G-J13` | [PER-CELL] | [pre-run] | PASS | 4 file(s) consumed, expected_B=[64, 32] |
| `G-J4` | [PER-CELL] | [post-cells] | PASS | CELL_B64 tiearb_B=[64]; CELL_B32 tiearb_B=[32] |
| `G-N` | [RUN]+[PER-CELL] | [post-cells] | PASS | n_common=1497 decks (floor 1200); games={'CELL_B64': 3000, 'CELL_B32': 2997} |
| `G-NEST` | [RUN] | [pre-run] | PASS | witness=True |
| `G-PLY` | [PER-CELL] | [post-cells] | PASS | CELL_B64=0; CELL_B32=0 |
| `G-SMOKE` | [RUN] | [post-smoke] | PASS | knobs/before-game-1=ok halt=False launched_anyway=False outcome_keys=0 |
| `G-STAT` | [RUN] | [post-cells] | PASS | UB95=+1.4143 se_D>0=True |
| `G-TOOL` | [RUN] | [pre-run]+[post-cells] | PASS | builds=['carc_rs-0.1.0+6542cffb2c30+rustcunpinned'] |

⛔ **FAILED: ['G-BAND']** — a failing gate SUPPRESSES the verdict.


### `G-J13` — RULING 4: the exact filenames consumed, per host

- **Doctor**: `measurement/tiearb_widening_20260817/b32v64_cell/verdicts/PREFLIGHT_Doctor_FIRST_B64.json` carried `j13_witness.B` = 64
- **Doctor**: `measurement/tiearb_widening_20260817/b32v64_cell/verdicts/PREFLIGHT_Doctor_FIRST_B32.json` carried `j13_witness.B` = 32
- **laptop-wsl**: `measurement/tiearb_widening_20260817/b32v64_cell/verdicts/PREFLIGHT_laptop-wsl_FIRST_B64.json` carried `j13_witness.B` = 64
- **laptop-wsl**: `measurement/tiearb_widening_20260817/b32v64_cell/verdicts/PREFLIGHT_laptop-wsl_FIRST_B32.json` carried `j13_witness.B` = 32

- preflight resolution: RESOLVED from the NAMED addresses · 4 superseded rotation(s) excluded and recorded (REPORT-ONLY, wired into NO conjunct — READ_RULE §2.2)


## §4.3 item 2 — the `D` block: THE PRIMARY

- `D` = +0.6460 · `se_D` = 0.4671 · **`z_D` = +1.3830** · `n_common` = 1497 decks
- ⭐ **`UB95(D)` = +1.4143** — **ONE-SIDED 95% UPPER BOUND ON THE COST** — against the +0.93 pts/game tolerance
- `CI90(D)` = [-0.1224, +1.4143] — two-sided 90% interval — REPORTED FOR CONTEXT, adjudicates nothing
- realized `rho` = +0.0895
- committed `se(D)` = 0.5044 · 2σ floor = +1.0088 · non-binding realized-dispersion projection = 0.457
- `EQUIV` (one_sided) = **False** — UB95(D) = +1.414284 > 0.93
- `n` to convict a 2σ COST at the realized dispersion: 3131 decks
- `n` to resolve a NON-INFERIORITY at the realized dispersion: **10954 decks/cell** / 43816 games total / **257.97 two-box wall-h** (at the measured 35.56-worker pool)

## §4.3 item 1 — both cells

| quantity | `CELL_B64` | `CELL_B32` |
|---|---|---|
| `n` attempted (planned) | 3000 | 3000 |
| `n` completed (games) | 3000 | 2997 |
| decks seat-balanced | 1500 | 1497 |
| `M` (pts/game) | +5.2123 | +4.5731 |
| `se` (recomputed) | 0.3421 | 0.3501 |
| `paired_z` | +15.2362 | +13.0629 |
| elo | +66.4644 | +56.8427 |
| elo ±1σ | 6.4597 | 6.4316 |
| `wr` | 0.5945 | 0.5811 |
| `wr_z` | +10.3520 | +8.8775 |
| W / D / L | 1752 / 63 / 1185 | 1710 / 63 / 1224 |
| seat balance | {'a_seat_0': 1500, 'a_seat_1': 1500, 'balanced': True} | {'a_seat_0': 1498, 'a_seat_1': 1499, 'balanced': False} |
| `n_failed` | 0 | 3 |

- `n_common` = 1497 decks

## §4.3 item 3 — the divergence block

- `f0` = 0.0120 · `1 − f0` = 0.9880 vs floor 0.1 — **beside the EXPECTED ≈0.98** (≈10× headroom)
- dilution `√(1−f0)` = 0.9940
- (not flagged anomalous)
- f0 is measured as 'D_i exactly 0.0', which OVERCOUNTS identity (two different games can coincide on margin) ⇒ 1 − f0 UNDERCOUNTS divergence ⇒ the floor is CONSERVATIVE: it can only fire early, never late.

## §4.3 item 4 — the `phi` block

- **`CELL_B64`**: `phi` = 17.4717 · `phi_effective` = 17.4717 (error rate on fired 0.00000)
- **`CELL_B32`**: `phi` = 17.5148 · `phi_effective` = 17.5148 (error rate on fired 0.00000)
- cross-cell `phi` difference: -0.0432
- beside the offline prior **22.96**, the committed **17.481** and the b64 cell's realized [17.5533, 17.4087]
- DESIGN §7.2 assumes phi EQUAL across cells and STATES the assumption: the trigger predicate does not depend on B, so phi should be B-invariant AT THE SAME POSITION — but the cells diverge onto different boards, so realized phi can differ. The realized cross-cell difference is printed.

## Cost — reported on every branch, a branch input NOWHERE

- ⛔ THERE IS NO AFFORDABILITY PREDICATE IN THIS PAIR. The b64 cell's A / W / OWNER_WAIVER.md machinery is ABSENT BY DESIGN: the N4 rho_wall <= 1.20 bar it enforced was WAIVED at B = 64 by b64_cell/OWNER_RULING_20260820.md. Cost is reported on EVERY branch and is a branch input NOWHERE. ⚠️ This absence is DECLARED rather than left to be noticed.
- `rho_wall` 16/32/64/128 = 0.6224 / 1.2449 / 2.4897 / 4.9794 · N4 bar 1.2 — ⛔ WAIVED AND RETIRED at B = 64 by b64_cell/OWNER_RULING_20260820.md ruling 1 — printed as HISTORY, never as a test
- the prize: ≈2.24 s/move saved at the 1.8 s/move baseline = -35.7% of the per-move wall
- `rho_phone` 32 [11.04, 11.95] / 64 [22.08, 23.9] — **NOT SOLVED — a THIRD CURRENCY. The mobile profile plays the UNMODIFIED champion and no branch here changes that.**
- `ms_ratio` predicted {'CELL_B64': 6.608, 'CELL_B32': 3.74} vs realized {'CELL_B64': '6.591', 'CELL_B32': '3.806'}
- ⚠️ champ_prefix_ms_per_move IS THE CANDIDATE SIDE in eval_fair_puct (lines 2361/2371/2389 — the opposite of eval_puct_priors). A read-out that swaps them INVERTS the cost verdict.
- ⚠️ the smoke's ms_ratio and the cells' ms_ratio are both printed and NEITHER grades the other: a bar written after a smoke number exists is not a bar.
- the two cells are NOT cost-matched (CELL_B64 spends ~1.60× the worker-seconds per game of CELL_B32), but NEITHER CANDIDATE'S SEARCH BUDGET MOVES: both run the identical champion at k8×1376 with identical sims and the arbiter fires AFTER the search, at the root, on an already-resolved tie ⇒ the extra cost buys NO extra search. It is a WALL-CLOCK ASYMMETRY and is disclosed as one on every branch, never claimed away.

## §4.3 item 7 — the failed-record accounting, printed whether or not any failure occurred

- **`CELL_B64`**: `n_failed` = 0 / `n_attempted` = 3000 ⇒ rate 0.00000 vs the 0.02 bar · `failure_rate` = 0.0 · `failure_rate_trigger` = 0.005 · `validity_trigger_fired` = False
  - `tiearb_errors_total` = 0 · `tiearb_error_rate_on_fired` = 0.0 · `tiearb_first_error` = None · `tiearb_partial_argmax_total` = 0
  - `failed_cells[]` (0 record(s)): none
  - `resolved_failed_cells[]` (0): none
- **`CELL_B32`**: `n_failed` = 3 / `n_attempted` = 2997 ⇒ rate 0.00100 vs the 0.02 bar · `failure_rate` = 0.001 · `failure_rate_trigger` = 0.005 · `validity_trigger_fired` = False
  - `tiearb_errors_total` = 0 · `tiearb_error_rate_on_fired` = 0.0 · `tiearb_first_error` = None · `tiearb_partial_argmax_total` = 0
  - `failed_cells[]` (3 record(s)): [{"seed": 140000001096, "a_seat": 1, "attempts": 1, "permanent": false, "exc_type": "PanicException", "exc": "IndexError: board row index 35 out of range (len 35)", "window_truncation": false, "window_diag": null}, {"seed": 140000001115, "a_seat": 0, "attempts": 1, "permanent": false, "exc_type": "PanicException", "exc": "IndexError: board row index 35 out of range (len 35)", "window_truncation": false, "window_diag": null}, {"seed": 140000001286, "a_seat": 0, "attempts": 1, "permanent": false, "exc_type": "PanicException", "exc": "IndexError: board row index 35 out of range (len 35)", "window_truncation": false, "window_diag": null}]
  - `resolved_failed_cells[]` (0): none
- clause 2 (candidate-correlation): False — max(F) >= 5 AND max(F) > 3 × max(min(F), 1)
- clause 3: not triggered
- ⛔ **REPORT ONLY — wired into NO conjunct (DESIGN §13.2 item 2)**
- window-truncation failures fire at extreme board extents, so any dropped set is CORRELATED WITH BOARD GEOMETRY — late-game, large-extent positions — and that correlation is DISCLOSED rather than argued away.

## The offline ladder — a DESCRIPTION, explicitly NOT a projection

- `arb(32)` = 0.1942 · `arb(64)` = 0.2015 · `Δ(32→64)` = +0.0073 pts/tied ply · ratio 1.038
- the §5.2 bracket: [0.0399, 0.1555] pts/game
- ⛔ MUST NOT be presented as a projection of the game effect. The offline ratio 1.038 is a DESCRIPTION of the offline ladder; the bracket is a WIDTH, and NEITHER ENDPOINT IS A PROJECTION.

## Carried VERBATIM

- **translation_caveat**: ⚠️ The offline→game translation factor is not established. Stage 1b's +0.1441 pts/tied ply predicts +0.79 pts/game (× phi 17.57 / non_additivity 3.2); Phase B realized +3.07 — a 3.9× under-prediction.
- **translation_caveat_both_ways**: CAMPAIGN ruling 5 binds in BOTH directions: Stage 1b's offline read under-predicted the Phase B game cell 3.9× … so the offline→game map is unestablished and +0.0670 × 3.9 is not a projection either.
- **second_datum**: the b64_cell's §5.2 bracket for Δ(16→64) was [+0.368, +1.435] and it realized +1.7167 — the map missed LOW TWICE, at n = 2, in the SAME direction. ⛔ Still not a licence to multiply.
- **b64_cell_scope_fence**: ⛔ No branch re-adjudicates the b64_cell. Its verdict of record is B-COSTKILL, its read-rule is SPENT and its band 139e9 is RETIRED. No comparison against its numbers is a branch input anywhere.

## ⛔⛔ Cross-band humility — MANDATORY, not optional prose

| rung | band | elo vs the unmodified champion | status |
|---|---|---|---|
| `B` = 16 | 139000000000 | +36.2644 | RETIRED band |
| `B` = 64 | 139000000000 | +63.9457 | RETIRED band |
| `B` = 32 | 140000000000 | +56.8427 | this cell |
| `B` = 64 | 140000000000 | +66.4644 | this cell |

- over-dispersion: 1.8–2.2× in BOTH statistics (CLAUDE.md)
- ⛔⛔ The 139e9 numbers MUST NOT be pooled with the 140e9 numbers, plotted as one curve without the band labels, or differenced to produce any estimate. Band 139e9 is RETIRED from confirmatory use and cannot support a new verdict at all. THE ONLY ROBUST CONTRAST IN THIS RUN IS THE WITHIN-BAND DECK-PAIRED D, and it is the only branch input. The table may be SHOWN, with its band column, as a DESCRIPTION — never fitted, differenced across bands, or called a curve measurement.

## §4.3 items 12–13 — the band, and this rule's own blind commit

- band **140000000000**, decks 140000000000..140000001499 · claim: measurement/tiearb_widening_20260817/b32v64_cell/BAND_CLAIM.json (claimed_before_game_1 = True)
- the band is ONE-USE and retires from confirmatory use at close-out on EVERY branch
- **blind commit: `71b3286c`** — `DESIGN.md` and `READ_RULE.md` landed in the SAME commit before game 1, and the band claim (2026-08-20) PREDATES that commit; that ordering is itself printed here (DESIGN §12.2).
- §9.3 HALT record: halt = **False** (realized 843.323 vs bar 1392.037) — CELL_B64 realized 843.323 worker-s/game <= 1392.037 (= 1.5 x 928.025, MEASURED on the b64 cell's WIDE)

## ⚠️ SPEC-vs-BUILDABLE — REPORTED, never resolved here

- **READ_RULE §3 G-FAILED clause 3 / DESIGN §8.1 clause 3** [REPORTED — carried as the pair drafted it] — eval_fair_puct emits no `diagnostic_class` / `failed_classes` field (re-checked at HEAD). ⭐ But a per-failure surface DOES exist: summary.json::failed_cells[].{seed, a_seat, attempts, permanent, exc_type, window_truncation, window_diag} plus resolved_failed_cells[], failure_rate, failure_rate_trigger and validity_trigger_fired.
  - adjudicator: clause 3 carries RULING 3's narrowing VERBATIM (verbatim disclosure + an escalation HALT before adjudication, cleared only by a recorded HUMAN confirmation). The mechanical surface is PRINTED in full and wired into NO conjunct.
  - resolution: ⛔ NOT PROMOTED HERE. Wiring a new address into a gate conjunct after sign-off is how the three unsatisfiable gates shipped. Whether a FUTURE pair promotes failed_cells[].window_truncation to a mechanical conjunct is the orchestrator's decision; this tool does not take it quietly.
- **READ_RULE §3 G-J13 / DESIGN §3** [CLOSED — strict read, verified against real artifacts] — the b64 cell's residual — RULING 2 pins FOUR addresses, but on that cell's earlier known-good fixture the two BOOLEANS sat at `two_sided.*`, so its adjudicator carried a fallback.
  - adjudicator: ⭐ CLOSED HERE: this cell reads all four addresses STRICTLY at the pinned paths with NO two_sided.* fallback, because b32v64_cell/preflight.sh now ASSERTS all four on the emitting host before that host's game 1. An absent B — or an absent pinned boolean — FAILS.
  - resolution: no ruling required: the emitter obligation the b64 cell NOTED is discharged by this cell's preflight, and the known-good evaluation confirms the strict read still passes a healthy run.
- **READ_RULE §3 G-SMOKE / DESIGN §9.2** [CARRIED — RULING 1 implemented] — §9.2 states TWO rules on TWO surfaces. Read as ONE whitelist over the artefact, the row FAILS a known-good smoke, whose SMOKE.json legitimately carries structural keys.
  - adjudicator: the GATE fires on forbidden OUTCOME keys at any depth; the EMITTER whitelist is evaluated and REPORTED beside it, never as the gate verdict (RULING 1, carried VERBATIM).
  - resolution: carried as ruled on the sibling cell; no new ruling needed.
- **DESIGN §13.2 item 7 — gate_nest.py's cross-cell dependency** [CLOSED — moved, not re-derived] — b32v64_cell/gate_nest.py imported `nest_witness` from scripts/tiletie/analyze_b64_cell.py — a live dependency on a SPENT run's tooling, which the drafter reported for the orchestrator to rule on.
  - adjudicator: ⭐ DISCHARGED as the drafter's own stated resolution requires: `nest_witness` is COPIED into this module (not imported), gate_nest.py's import is repointed here, and analyze_b64_cell.py is UNTOUCHED.
  - resolution: the structural claim is B-INDEPENDENT (a property of the rust source, not of any (B_lo, B_hi) pair), so the copy is verbatim rather than re-parameterized.
- **DESIGN §9.3 HALT bar / READ_RULE §3 G-SMOKE launched-anyway (REVIEW R1 finding B6)** [CLOSED — three links, all enforced] — ⛔ THE BAR WAS UNENFORCED END-TO-END. The launcher LOGGED the bar's value and never compared; smoke-check computed `halt` and dropped it out of its exit condition; and the gate's conjunct hung on `--launched-after-halt`, an operator store_true flag whose DEFAULT WAS THE PASSING VALUE — a pass-always gate on a live §3 row, and a SECOND undeclared human input into a rule that declares exactly one.
  - adjudicator: smoke-check WRITES SMOKE_HALT.json (DESIGN §9.3.1) and puts `halt` in its exit condition; run_cells.sh READS it and refuses a real-cell launch; G-SMOKE derives launched_anyway = halt AND cells_ran, both mechanical at [post-cells]. The flag is DELETED.
  - resolution: ⛔ NO OVERRIDE FLAG EXISTS: a HALT holds until the owner rules (stop, or re-fund at the realized cost). An absent or unreadable cost also HALTS — an unevaluable cost check must not wave a 6,000-game run through.
- **READ_RULE §2.2 / §3 G-TOOL — the preflight address (REVIEW R1 finding B7)** [CLOSED — one resolution path, both modes] — the rotation-exclusion lookup was wired into `knowngood` ONLY, so the REAL adjudication path had no protection: an operator glob would hand G-TOOL two builds for one host and fail a healthy run whose only irregularity was the wheel rebuild the [pre-run] marker MANDATES.
  - adjudicator: `resolve_preflights` is the SINGLE resolution path for both modes: with no --preflight it resolves READ_RULE §2.2's four named addresses; with paths supplied it REFUSES any timestamped rotation by name rather than silently dropping an argument the operator passed. Rotations are reported beside G-TOOL.
  - resolution: the pair now states the address and the supersession rule in §2.2, so the behaviour is supported by the TEXT and not only by this docstring.
- **READ_RULE §4 EQUIV / WORKERS.conf committed constants block** [RULED — parameterized, committed value one_sided] — ⭐ THE BAR IS OWNER-RULED AND MUST BE CHANGEABLE WITHOUT A CODE EDIT. A tolerance or a test shape hard-coded in the adjudicator would make the pair's committed block decorative — the 'pass-always gate (constant input)' disease §13.1 audits for.
  - adjudicator: TOLERANCE_PTS and EQUIV_SHAPE are READ, fail-closed, from b32v64_cell/WORKERS.conf. Two shapes are supported — two_sided (CI90 containment) and one_sided (non-inferiority on the upper bound). An absent, unparseable or out-of-vocabulary value is a REFUSAL, with NO coerced default.
  - resolution: OWNER RULING 2026-08-21 selected ONE-SIDED ±15 ⇒ the COMMITTED shape is `one_sided`. ⚠️ Under one_sided a large-negative D satisfies EQUIV arithmetically; FIRST-MATCH-WINS resolves it to L-REVERSED, which is branch #2, and the read-out prints BOTH facts.

*PRODUCTION.yaml is UNTOUCHED on every branch and no branch mints a claim in CLAIM_REGISTRY.csv. L-SATURATED LICENSES a swap-down DECISION for the owner; the owner executes it with one word and the prereg never edits the file. This read-rule is SPENT when the read-out lands, on every branch, and band 140000000000 retires from confirmatory use.*
