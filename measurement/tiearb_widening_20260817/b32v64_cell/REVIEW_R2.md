# `b32v64_cell` PREREGISTRATION PACKAGE — ADVERSARIAL REVIEW R2

> # ✅ **VERDICT: PASS (0 blocking)**
>
> **CLEARED FOR THE BLIND COMMIT.** 0 BLOCKING · 5 REQUIRED · 3 COSMETIC.
>
> All **7 BLOCKING** and all **10 REQUIRED** findings of [`REVIEW_R1.md`](REVIEW_R1.md) are
> **closed at site**, and I verified the load-bearing ones **functionally** — by generating a
> real read-out with the real adjudicator on the `b64_cell`'s real artifacts and scanning the
> output — not by reading the claim. The R1 root cause (RULING 1's landing table omitting the
> adjudicator) is closed with a **standing rule** recorded, which is a better fix than the one
> the review asked for.
>
> ⚠️ **The 5 REQUIRED are drafting/coverage defects, not adjudication defects.** None can void,
> bias or un-adjudicate the run: three are prose-vs-code address errors in the verb-enumeration
> tables, one is a measure-zero timestamp tie-break, one is a launcher kill-quality gap that the
> adjudicator already catches fail-closed. **They should be fixed, and none of them gates
> tonight's commit.**
>
> Reviewed pre-blind: `WORKERS.conf::BLIND_COMMIT` still reads `PENDING`, no `summary.json` /
> `manifest.json` exists for either cell, `run_cells.sh` still refuses a real-cell launch.
> Read-only: nothing outside this file was created, edited, committed or launched.

---

## 0. EXECUTED CHECKS (brief item d)

| check | result |
|---|---|
| `pytest tests/test_tiearb_b32v64.py -q` | **162 passed**, exit 0 |
| `pytest tests/test_tiearb2_stage2.py tests/test_freeze_latch.py -q` | **141 + 14 passed** — no regression in the sibling suites |
| `./run_cells.sh local --dry-run --band 140000000000` | **rc = 0**; both argv printed; the new `smoke-check … --halt-out …/SMOKE_HALT.json` step is wired into the printed plan |
| `RUN_LIVE.json` after the dry-run | **none** ✅ |
| `SMOKE_HALT.json` after the dry-run | **none** ✅ — the dry-run reports the record's absence, never creates one |
| two cells differ in exactly one experimental arg | **`--cand-tiearb-b 32` vs `64`** only ✅ |
| `KNOWNGOOD_EVAL.json` | 13/13 PASS, 0 N-A, `branch_on_known_good = L-RISING` (⛔ not a verdict) ✅ |
| `git status` governance | `BAND_REGISTRY.csv` **+1 / −0** only; `PRODUCTION.yaml`, `CLAIM_REGISTRY.csv` untouched ✅ |
| `DEVIATIONS.md` | unmodified, highest section **D6**, no D7.x — correct, everything this round was fixable in the pair pre-blind ✅ |
| `analyze_b64_cell.py` | untouched ✅ |
| **live end-to-end adjudication** | ran the real CLI against the `b64_cell`'s real `summary.json`/`manifest.json`/`GATE_NEST.json`/`BAND_CLAIM.json`/`SMOKE.json` → `READOUT_B32V64.{json,md}` written, rc 0, `U-UNREADABLE` on 6 correctly-firing scaled gates, **no crash on any of the five branch renderings** |

---

# ✅ R1 FINDINGS — CLOSED AT SITE, VERIFIED FUNCTIONALLY

### B1 / B2 — the branch text (brief item b)
`analyze_b32v64_cell.py:1608–1705` `BRANCH_TEXT_BY_SHAPE` · `1708–1721` `branch_text()`

The `one_sided` `L-SATURATED` text now **verbatim-matches** `READ_RULE` §4.1 branch 4 — the
one-sided headline, `UB95(D)` in licence (i), the ruled MANDATORY SCOPE SENTENCE
(*"This is a ONE-SIDED NON-INFERIORITY result at 95%…"*), the EFFECTIVE 0.556 / 0.446 rider,
**and the THIRD MANDATORY RIDER that did not exist before** (1632–1639). `L-AMBIGUOUS` carries
the ruled headline, the ⭐ **high-side-only** note, `UB95(D)` in rider (i), and the 0.556/0.629
scope sentence.

⭐ **Better than asked:** the third rider is not merely *quoted* — it is **discharged
mechanically**. `build_readout:2694–2705` emits a `negative_D_disclosure` only when
`L-SATURATED ∧ one_sided ∧ D < 0`, printing the realized `D`, the realized `z_D > −2.0`, and
*"THIS BRANCH IS NOT THE PLACE TO CLAIM B = 32 IS BETTER"*; `render:2947–2948` prints it. The
gate is correct at the boundary (`D == 0.0` is not negative, so no disclosure — right).

**Verified functionally.** I scanned all five branch texts under the committed shape for
13 superseded phrases (`"90% CI"`, `"AT 90% CONFIDENCE"`, `"0.158"`, `"3779"`, `"~16%"`,
`"EQUIVALENCE result"`, `"modal outcome"`, `"NEITHER A DIFFERENCE NOR AN EQUIVALENCE"`, …):
**zero hits on every branch.** And the mandatory strings are all present in the rendered
markdown: `ONE-SIDED 95% UPPER BOUND` ✅ · `ONE-SIDED NON-INFERIORITY` ✅ ·
`THIRD MANDATORY RIDER` ✅ · `EFFECTIVE 0.556` ✅ · `0.446 at the offline bracket top` ✅.

The retained `two_sided` text is correct practice, not a residue: it renders **only** if the
committed block says `two_sided`, in which case the text and the predicate agree; it is
labelled *"⚠️ THE DRAFTED TWO-SIDED SHAPE — SUPERSEDED BY RULING 1 (2026-08-21)"*; and
`branch_text()` **refuses** an unknown shape rather than falling back (1717–1720).

### B3 / B4 — the power constants and statement (brief item b)
`analyze_b32v64_cell.py:160–233` `POWER_BY_SHAPE` · `236–245` `power_constants()`

Shape-keyed, fail-closed on an unknown shape. **Every one-sided figure re-derived and correct:**

| | raw | L-REV mass | EFFECTIVE | committed ✓ | realized-proj ✓ |
|---|---|---|---|---|---|
| true `D` = 0 | 0.5788 | 0.0228 | **0.5560** | ✓ | 0.6517 / 0.0228 / **0.6290** ✓ |
| bracket floor +0.0399 | — | — | **0.5288** ✓ | | **0.6005** ✓ |
| bracket top +0.1555 | — | — | **0.4459** ✓ | | **0.5102** ✓ |
| `n` for 80% | | | **2,728** / **2,240** decks ✓ | | (4,480 games ✓) |

⭐ **The two-sided set's `power_l_reversed_mass = 0.0` is correct, not a stub** — I checked:
two-sided `EQUIV` requires `|D| ≤ 0.1003`, which is disjoint from `L-REVERSED`'s `D ≤ −1.0088`,
so no mass is pre-empted and raw = EFFECTIVE there. That is a subtle thing to get right.

**No stale figure survives outside a WAS-side-of-diff quotation.** I grepped the *generated*
markdown: `~16%` appears on exactly one line — *"up from **~16%** (~30%) under the drafted
two-sided shape"*, the pair's own diff sentence — and nowhere else. The live figures read
`~56% (~63%)`. `0.158` / `3779` / `3102` appear **nowhere** in any rendered output under the
committed shape.

### B5 — `UB95(D)` is the rendered PRIMARY
`479 ub95()` · `2120 d_block` · `1367 gate_stat` · `2995–3001 render` · `3389 main`

Confirmed on a **real generated read-out**:

```
[b32v64] branch = U-UNREADABLE | z_D = +2.6561 | UB95(D) = +2.7799
         (ONE-SIDED 95% UPPER BOUND ON THE COST) vs tolerance 0.93 | …
[b32v64] CI90(D) = [+0.6535, +2.7799] — two-sided 90% interval — REPORTED FOR CONTEXT,
         adjudicates nothing
```

`D_block.UB95 = 2.779856…` present; `G-STAT`'s checked slots are
`['CI90_hi','CI90_lo','D','UB95','se_D','z_CELL_B32','z_CELL_B64','z_D']` — **`UB95` named, per
R7**, and recomputed from `D`/`se_D` when not supplied. `render` bolds `UB95(D)` first with
`UB95_LABEL` and demotes `CI90(D)` with `CI90_LABEL`. The generated `.md` contains `UB95(D)` ✅
and contains the literal `"90% CI"` **only inside the prohibition sentence** (*"the read-out
must say 'one-sided 95% upper bound', NEVER '90% CI'"*) — R1/R2 closed.

### B6 — the HALT chain, enforced end-to-end (brief item a)
`DESIGN` §9.3.1 · `analyze:1397 halt_record` · `3320–3322, 3367` writer · `run_cells.sh:134–170`
enforcer · `analyze:1436–1546` reader

All three links closed, and the pair's §9.3.1 actor table matches the code actor-for-actor:

- **WRITER** — `smoke-check` writes `SMOKE_HALT.json` unconditionally (3320–3322) **before** its
  exit, and `halt` **is** in the exit condition: `return 0 if (wl["ok"] and not outcome and not
  hd["halt"]) else 1` (3367).
- **ENFORCER** — `require_no_halt()` reads the record, refuses with `exit 9`, prints the full
  §9.3 disclosure, and **takes no argument that could bypass it**; an unreadable record parses
  to `"true"` (fail-closed, 153–154). `--launched-after-halt` is **deleted from the parser**.
- **READER** — `launched_anyway = halt ∧ cells_ran` (1466), `cells_ran` derived from real game
  counts (2611), `halt_doc` read from the record with a fail-closed recompute when absent
  (1463 → `halt_record(smoke)`, which **HALTs on a non-finite cost**, 1404–1410).

⭐ The deletion path is closed too: deleting `SMOKE_HALT.json` does **not** dodge the reader
(it recomputes from `SMOKE.json`), and deleting `SMOKE.json` fires the gate on `present: False`.

The orchestrator's ruling that `require_blind_commit` precedes `require_no_halt` is **sound and
has no observable consequence**: both refuse, both are unconditional for a real cell, and only
the message order differs. Noted, not a finding.

### B7 — `resolve_preflights` is the single path (brief item a)
`analyze:905–958`, called at `2593` (adjudicate) and inside `knowngood`

Both modes go through the same exclusion. Nothing supplied ⇒ the four named addresses of
`READ_RULE` §2.2 are resolved from `verdicts_dir`. Paths supplied ⇒ **a rotation is a REFUSAL**
that names the superseded path *and* the named address to use instead — ⭐ **not** a silent
drop, which the docstring argues (correctly) would be worse than either failing or accepting.
The live run reported `mode = RESOLVED from the NAMED addresses`. `READ_RULE` §2.2 states the
four addresses, defines a rotation as a superseded report-only artifact, and **forbids a glob as
an address** with the unsatisfiable-gate reasoning spelled out. R4's malformed
`PREFLIGHT_*_${HOST}_FIRST_B*.json` pattern is gone from the `G-TOOL` row.

### R1–R3, R5, R7–R10 and C1/C2/C4/C5 — all closed
`EQUIV_SHAPE_TEXT` and `CI_Z`'s comment now say *one-sided 95% upper bound* · R3
`modal_pre_run_expectation = L-SATURATED` with the `0.556 > 0.444` note, rendered · R5 `render`
emits §4.3 item 1 (a full both-cells table), item 6 (**realized values** per gate via
`_gate_realized`, plus `G-J13`'s exact filenames per host and a zero-files line), and the
rotations-excluded line · R8 the band row's release clause is thorough and even wires the flip
to `SMOKE_HALT.json::halt == true` with no game records · **R9 is closed better than reported**
— the landing table now names the adjudicator and the tests surface-by-surface, and records a
standing rule: *"Ownership decides who edits; RESTATEMENT decides who is listed."* · R10 the
sweep is shape-parameterized, plus text-conformance and `branch_text`/`power_constants` refusal
tests · C1 fixed to **1,722** *and* improved with the raw `1721.45` disclosure · C2 → **4,480**.

### Item (c) — is the known-good `G-SMOKE` "scaled" reading defensible?
**Yes — defensible, and NOT a new pass-always.** Four reasons: the vintage reason is *true* (the
`b64_cell`'s `SMOKE.json` genuinely predates `production_knobs`/`smoke_utc` — I confirmed both
keys are absent from it); it is disclosed twice (the row's `scaled=` text and the emitted
`conjunct1` block's `"evaluated": false` + reason), so the read-out cannot silently claim
coverage; **the other two conjuncts still bind**, and the newly-built launched-anyway conjunct is
exercised with `cells_ran=True` — *the real state of that completed run*, not a convenient
default; and, decisively, **I ran the missing check myself** (see N4): conjunct 1 *is* satisfiable
end-to-end on real artifacts. The residual is a coverage-bookkeeping gap, filed as **N4**.

---

# ⚠️ REQUIRED (5) — none gates the commit

- **N1 — `READ_RULE` §3's `G-SMOKE` TOOL column names the wrong writer for `SMOKE.json`.**
  `READ_RULE.md:193` says *"`analyze_b32v64_cell.py smoke-check` **writes** `SMOKE.json` (incl.
  `production_knobs`, `smoke_utc`)"*. The writer is **`aggregate-smoke`** (`analyze:2017–2019`);
  `smoke-check` writes only `SMOKE_HALT.json` (`3320–3322`) and stdout. `DESIGN` §12.1:1080 has
  it right, so the package contradicts itself in the one column the verb-enumeration rule exists
  to police — the same defect class as R1's R4. *Failure scenario:* an executor following §3
  runs `smoke-check` first, gets "SMOKE.json ABSENT", and re-attributes the refusal — the exact
  mis-attribution `run_cells.sh:384–390` was written to prevent.
- **N2 — `DESIGN` §12.1's verb table carries two stale build markers and one address nothing
  writes.** Rows `DESIGN.md:1082` (the HALT decision record) and `:1083` (the HALT enforcement)
  are still marked **`⛔ BUILDER'S QUEUE (R6/B6)`** though both are built and tested
  (`tests:1444`, `tests:1463`) — the same stale-status class as C4/C5, fixed elsewhere but
  missed here. And `DESIGN.md:1081` names `smoke-check`'s output as *"stdout + `SMOKE.json::
  whitelist_report`"*: **`whitelist_report` exists nowhere** (grep over `scripts/tiletie/` and
  the cell dir returns only that line). The whitelist result is printed to stdout as
  `emitter_surface` and is never written into `SMOKE.json` — a named address nothing writes,
  inside the table whose entire job is naming addresses.
- **N3 — the `smoke_utc` ordering comparison mixes two ISO formats and its tie-break errs toward
  PASS.** `smoke_utc` is `manifest::utc_end`, which a real manifest writes as
  `'2026-08-20T20:47:05+00:00'` (offset form — verified on the b64 manifest); but
  `_earliest_record_utc` (`analyze:2045`) emits `'…Z'`. The comparison is **lexicographic**
  (`str(smoke_utc) < str(earliest_cell_record_utc)`, `analyze:1501`). The shared 19-char prefix
  makes ordering correct at second resolution, but on an exact same-second tie `'+'` (0x2B)
  sorts before `'Z'` (0x5A) ⇒ **reads PASS**, whereas `DESIGN` §9.2 says *"`smoke_utc` ≥ that
  ⇒ FIRES"*. Measure-zero (the smoke and the cells are separate launches) and always in the
  passing direction, but it is a spec violation on the boundary. Parse both to datetimes, or
  normalize `utc_end` to the `Z` form. `tests:1022` uses `Z` on both sides so it cannot see this.
- **N4 — nothing exercises the emitter→gate round trip for `G-SMOKE` conjunct 1, and the
  known-good headline over-states coverage.** The positive case (`tests:998–1002`) feeds
  `expected_production_knobs()` back in as the *observed* dict — tautological: it proves the
  comparator, not that `_production_knobs_from_manifest` (`analyze:318`) plus `aggregate_smoke`'s
  injected `cand_tiearb_per_cell` (`analyze:1975–1979`) actually *agree* with the expectation.
  The known-good scales the conjunct away (`expected_knobs=None`, `analyze:2381`), yet
  `KNOWNGOOD_EVAL.json` reads **"13/13 PASS, 0 N-A"** — and that file's own banner promises that
  a row whose machinery cannot be exercised is `N-A` and **NAMED, never silently counted as
  covered**. There is no conjunct-level marker for partial coverage.
  ⭐ **I ran the round trip: `aggregate_smoke` over the `b64_cell`'s two real cell dirs →
  `production_knobs` with all 12 fields → compared against `expected_production_knobs`:
  `MISMATCHED = NONE`, `gate_smoke` → `ok = True`, `conjunct1.ok = True`.** So the current state
  is good and this is a **latent-drift** gap, not a live failure — but a drift in one manifest
  address or one type would fire `G-SMOKE` on a healthy 6,000-game run and no test would notice.
  Add the round trip as a test, or a conjunct-coverage line to the known-good.
- **N5 — `require_no_halt` treats an ABSENT `SMOKE_HALT.json` as pass, and the launcher has no
  "a smoke exists at all" precondition.** `run_cells.sh:147`: `[ -f "$rec" ] || return 0`. It is
  *declared* in the comment, and the adjudicator is fail-closed behind it (absent record ⇒
  recompute; absent `SMOKE.json` ⇒ `G-SMOKE` fires), so **no run can be mis-adjudicated by it**.
  But the launcher's own precondition 2 (*"the smoke has run and its HALT bar has been
  evaluated"*) is not enforced, and "no smoke yet" is indistinguishable from "record deleted".
  *Failure scenario:* a real-cell launch with no smoke burns **~35 two-box wall-hours and 6,000
  games** before `G-SMOKE` reports `present: false` ⇒ `U-UNREADABLE`. Kill quality: make the
  absent record refuse a real cell, so the loss is a refused launch instead of the whole run.

---

# ○ COSMETIC (3)

- **X1** — test-count reconciliation: the cell's suite collects **162** (all pass), but the
  reported total *"234 = 162 + 58 + 14"* does not reconcile — `test_tiearb2_stage2.py` collects
  **141** and `test_freeze_latch.py` **14** (317 across the three, all green). The `58` looks
  like the stale R1-era sub-count. No defect in the code; the figure quoted to the owner should
  be corrected.
- **X2** — `POWER_BY_SHAPE["two_sided"]["power_at_bracket_floor_committed"/"…_realized_proj"]`
  are `None` (`analyze:214–215`), so a `two_sided` rendering emits `None` in the JSON power
  table where the one-sided set carries figures. Harmless under the committed shape; either
  compute them or mark them `"not quoted by the pair"`.
- **X3** — `_gate_realized`'s `G-SMOKE` one-liner (`analyze:2912–2915`) prints
  `halt / launched_anyway / outcome_keys` but **not** conjunct 1's status — the newest and most
  complex conjunct is the one absent from the gate table's realized column. It is in the JSON
  detail and in the `ok` column, so nothing is hidden, but the summary line under-reports.

---

## §V — WHAT I TRIED TO BREAK AND COULD NOT

- **Fabricated knob addresses.** `_production_knobs_from_manifest` reads 11 fields off a real
  `eval_fair_puct` manifest — **all 11 resolve** (`k_dets` 8, `sims` 1376, `exact_k` 2,
  `rules_profile` `fixed_v1`, `cand_leaf_hash`, `c_puct` 1.5, `tau_p` 5.0, `leaf_quantize`
  `float`, `final_select` `visits`, `opponent` `fair-champion`, `backend` `rust`). Not invented.
- **Strict nested-dict equality on `cand_tiearb_per_cell`.** This was my prime candidate for a
  fresh fail-always: `gate_smoke` compares the whole nested dict with `!=`, unlike `gate_j4`'s
  subset check. I checked the real manifests — `S2._tiearb_cfg` returns **exactly**
  `{enabled, B, J, mode, salt, eps}` with matching types (`B` int, `eps` float), **no extra and
  no missing keys** against the expectation. It holds.
- **The `expected_knobs is None ⇒ pass` escape hatch** (`analyze:1471–1480`). Unreachable on the
  real path: `build_readout:2646` passes `expected_production_knobs(args.workers_conf)`
  unconditionally — not from a flag — and that function is itself fail-closed on a conf missing
  any knob line. Only `knowngood` uses the hatch, deliberately and disclosed (→ N4).
- **Deleting the HALT record to dodge the enforcer.** Caught by the reader (recompute from
  `SMOKE.json`); deleting both is caught by `present: false`.
- **Rendering crashes.** All five branches render cleanly (19.2k–20.6k chars) on a real
  read-out; `_gate_realized`'s path helper returns `"n/a"` on any missing address, so a partial
  gate detail cannot except.
- **Branch order / oracle.** Unchanged from R1 and still verified: the oracle is an independent
  re-transcription, the order is `U-UNREADABLE → L-REVERSED → L-RISING → EQUIV → complement`,
  both shapes swept, boundaries inclusive, and I found no input separating implementation from
  pair text.

*Reviewed 2026-08-21, pre-blind, after both fix rounds. Read-only: nothing outside this file was
created, edited, committed or launched, and no `RUN_LIVE.json` or `SMOKE_HALT.json` exists.*
