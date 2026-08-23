> ## §0 — PROVENANCE BANNER (the pre-registered instrument-fix successor)
>
> ⛔→✅ **FROZEN 2026-08-23 (the blind commit is THE COMMIT THAT INTRODUCES THIS BANNER; its sha is stamped into `run_cells.sh` in the follow-up commit, per the b32v64 pattern). No statistic of any kind exists at freeze time.**
>
> This file is the **pre-registered instrument-fix successor** to
> [`../track_d2_prep/READ_RULE.md`](../track_d2_prep/READ_RULE.md), whose first attempt adjudicated
> **`U-UNREADABLE`** on four INSTRUMENT gates (`G-RULES`, `G-LEAF`, and `G-TOOL` twice). No
> strength or spacing statistic from that run is carried, quoted, or adjudicated here.
>
> **The session that drafted this file is STATISTICS-BLIND, per §4's own binding clause** — it did
> not see `S`, `z_S`, or either cell's summary statistics, and did not open the first attempt's
> readout or any `summary.json`. **Bars do not move. §4 is not edited.** Every §-numbered rule,
> branch, gate, threshold and `n` below is **VERBATIM** from the frozen original. The changes are
> exhaustively: the run id, the band (`141000000000` → **`143000000000`**), the launcher
> reference (the FIXED [`run_cells.sh`](run_cells.sh)), this banner, and **§3.1 — re-run over ALL
> gates including `G-TOOL`**, which is the check whose absence let the unsatisfiable `G-TOOL`
> sub-clause ship.
>
> The four instrument fixes are enumerated in [`DESIGN.md`](DESIGN.md) §0 item 4. The one
> execution-layer value that CARRIES from the first attempt is the §9 pilot's single permitted
> `--sims` re-pick, **k4×1032**, frozen on the discarded pilot band before any cell ran and
> therefore before any statistic existed (`DESIGN.md` §0 item 5). §9's re-pick allowance is now
> exhausted.

# READ_RULE — rung compression (D2)

> **⚠️ BLIND ORDERING (once this pair is actually committed). This file is meant to be
> committed BEFORE the band is claimed, BEFORE game 1, and BEFORE any statistic of any
> kind exists.** Its git commit is intended to be the proof. The branch that fires is
> taken **VERBATIM**, whatever it is. No owner call adjudicates any outcome; owner
> authorization funds the cell and does not name its answer.
>
> Design: [`DESIGN.md`](DESIGN.md). Run id `track_d2r2_prep`.

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

---

## §3 — PRECONDITIONS (every one must PASS, else `U-UNREADABLE`)

Fail-closed. **ABSENT is FAIL.** Each gate is read at the manifest top level, then at `config.*`,
and the adjudicator reports which address resolved (the house `G-BAND`/`G-J1` fix precedent).

| id | proposition | VOIDS on |
|---|---|---|
| `G-BAND` | both cells' `manifest.json` `seed_start` == 143000000000; record-derived deck sets agree; `n_common` == 200 | any mismatch |
| `G-SINGLEVAR` | the two cells' `config` blocks differ in exactly `rung.sims`, `out_subdir`/output path, and `claim_host` — nothing else | any other differing key |
| `G-RUNG` | both manifests: `config.rung.c` == 3.0, `config.rung.agent` == `"HeuristicMCTS"`, `config.rung.leaf_hash` identical across cells, `config.rung.sims` == 800 (R800) / 1600 (R1600) | any deviation |
| `G-LEAF` | `config.cand_leaf_hash` == `a36d2e15a3b3d71d` in BOTH cells | mismatch or absence |
| `G-RULES` | `rules_profile.name` == `"fixed_v1"` and `r9_env_ok` == true, in BOTH cells | anything else |
| `G-TOOL` | same `carc_rs_version` and `tile_data_semantic_digest` across both cells; same code rev in both; `BLIND_COMMIT` in both manifests equal to the launcher's frozen value | any mismatch; a manifest carrying the placeholder |
| `G-N` | 400 games scored in EACH cell; `n_failed` == 0 (a nonzero rate is reported, not silently absorbed, and is a DESIGN §7/§9 discussion point, not automatically a void — see §3.1) | short of 400 completed games |
| `G-TIMING` | both cells report `champ_prefix_ms_per_move` and `rung_ms_per_move`; CELL R800's realized ratio is inside `[0.85, 1.20]` | outside the interval, or either field absent — this is the §9 pilot's own bar, re-checked on the real cell |
| `G-SAT` | CELL R800's probe winrate vs h800 is inside `[0.50, 0.90]` | outside — the margin statistic is compressed at a floor/ceiling and does not read as a spacing measurement |

`n_failed` on a healthy rust/python mixed cell is expected near-zero but not guaranteed exactly
zero (the b32v64 precedent saw a 0.100% pre-existing rust engine panic-fail class); a nonzero rate
below 2% is reported and does not by itself fire `G-N`, matching the campaign's `<=2%` floor
precedent — but it is printed on every branch regardless of outcome (§4.3).

### §3.1 — the structural test, applied to every gate above, BEFORE any outcome is known

**RE-RUN IN FULL for this successor, over ALL NINE gates.** The question is exactly one, asked of
each gate: *would this gate fail on every healthy run of this launcher?* A gate that would is
fixed BEFORE game 1, never discovered after.

⛔ **WHY THIS SECTION IS LONGER THAN THE ORIGINAL'S — the miss, named.** The first attempt's §3.1
audited **four** of the nine gates (`G-SINGLEVAR`, the `G-RUNG`/`G-LEAF`/`G-RULES` group,
`G-TIMING`, `G-N`) and **silently skipped `G-BAND`, `G-TOOL` and `G-SAT`**. `G-TOOL` was the one
that mattered: its `BLIND_COMMIT`-in-both-manifests sub-clause was **structurally unsatisfiable**
against `eval_fair_puct.py`, which had no stamping path at manifest top level or under `config.*`
— the two addresses §3 above says the adjudicator searches. That gate could not pass on ANY
healthy run, and the audit that exists to catch precisely that never asked it. **A partial
structural test is the failure mode, not a lighter version of the test.** Two further lessons are
folded in below: the `G-RUNG`/`G-LEAF`/`G-RULES` group was waved through as *"the harness writes
these fields, so the gate just checks D2 used the harness normally"* — true about the **writing**
and false about the **values**, which is how a non-champion leaf and `r9_env_ok=False` both
shipped; and a gate whose satisfiability depends on the LAUNCHER's behaviour must be audited
against the launcher, not against the harness.

- **`G-BAND`** — `seed_start` is `--seed-start`, echoed into the manifest by the harness; the
  launcher pins it from `PINNED_BAND` and accepts a `--band` that only CONFIRMS it (a disagreeing
  `--band` is fatal), and BOTH cells take it from the one shared `COMMON` array, so the two cells
  cannot disagree by construction. `n_common == 200` follows from `--n 400 --paired` in that same
  array. **Fails on a healthy run? NO.**
- **`G-SINGLEVAR`** — guaranteed by the launcher building both cells' argv from one shared
  `COMMON` array ([`run_cells.sh`](run_cells.sh)); the property is structural, not clerical.
  ⚠️ Re-audited for the successor: the three fields the fixes ADD (`--cand-leaf-json`,
  `--stamp-key`, and the `CARCASSONNE_FIX_R9` env) are all in `COMMON` or at file scope, i.e.
  **identical in both cells**, so no fix widens the single-variable surface. **NO.**
- **`G-RUNG`** — `config.rung.{c,agent,sims,leaf_hash}` are written by the harness; `c == 3.0`
  comes from `RUNG_C = DEFAULT_C` inside `eval_fair_puct.py` (DESIGN §2.1), `sims` from
  `--rung-sims` (the one experimental axis), and the rung leaf is ALWAYS env `DEFAULT_CONFIG` —
  the harness never lets `--cand-leaf-json` reach it. ⚠️ The VALUE half is now checked, not
  assumed: the launcher's `preflight_leaf` asserts the rung resolves the CL-022 ruler
  `42af12fce22e1a0f` before game 1, which is what catches a curve env / `champ_env.sh` having
  moved `DEFAULT_CONFIG` out from under the ruler. **NO.**
- **`G-LEAF`** — ⚠️ this is the gate that voided the first attempt, and it was NOT structurally
  satisfiable there: for `--info fair --opponent h800` the harness does **not** auto-inject
  `curve125` (that fires only for `fair-netprior` / head-to-head / `bare-net` / `greedy`), so a
  launcher that passed no leaf ran the rung-default leaf and `cand_leaf_hash` could never read
  `a36d2e15a3b3d71d`. FIXED: the launcher passes `--cand-leaf-json champion_leaf_curve125.json`
  in `COMMON`, and `preflight_leaf` builds one champion **through the harness's own module** and
  asserts the hash equals `a36d2e15a3b3d71d` **before game 1**, refusing to start otherwise.
  Verified by running the pre-flight: candidate `a36d2e15a3b3d71d`, rung `42af12fce22e1a0f`,
  distinct. **NOW: NO.**
- **`G-RULES`** — ⚠️ also voided the first attempt, for a launcher reason, not a harness reason:
  `rules_profile.name` follows `--rules-profile fixed_v1`, but `r9_env_ok` is an OBSERVATION of
  the process environment, and `fixed_v1` **cannot apply R9 itself** (import-time farm derivation
  + a Rust `OnceLock`). A launcher that did not export `CARCASSONNE_FIX_R9` therefore produced
  `r9_env_ok=False` on every healthy run — unsatisfiable in practice. FIXED: the launcher exports
  it at file scope before any leg, and `assert_r9_env` refuses to run if it is unset or not
  truthy. **NOW: NO.**
- **`G-TOOL`** — audited in three parts, because it is three propositions wearing one id.
  **(a) same `carc_rs_version` / `tile_data_semantic_digest`:** written by the harness's own
  close-out provenance patches; satisfiable by construction on one build. **(b) same code rev in
  both cells:** NOT structural in the first attempt — nothing stopped a commit landing between the
  legs, and one did. FIXED at the launcher: `snapshot_rev` records `HEAD` plus a code-path dirty
  fingerprint at start, `assert_rev_unmoved` re-checks before EACH cell and refuses to start a
  subsequent cell if either moved, and `require_clean_code` refuses to start a real cell on dirty
  CODE at all (`LAUNCH_DIRTY=1` + a mandatory logged reason is the only override). ⚠️ That refusal
  is scoped to CODE paths ON PURPOSE, and the scoping is itself an application of this test: this
  repo's tree carries churning measurement artifacts at all times and the launcher must drop
  `RUN_LIVE.json` under `measurement/` for the freeze-latch hook, so a WHOLE-TREE dirty refusal
  would fire on every healthy run — the exact defect class this section exists to remove. Non-code
  dirt is recorded (per-box `PRELAUNCH_<host>.json` + log), never fatal; both manifests will
  therefore still read `<sha>-dirty`, identically, which satisfies "same code rev" as written.
  **(c) `BLIND_COMMIT` in both manifests:** **UNSATISFIABLE in the first attempt at any address
  §3 searches** — the harness had no stamping path, and its `leaf_env` block is a fixed allowlist
  of leaf knobs landing at `manifest["leaf_env"][...]`, which is neither top level nor `config.*`.
  FIXED in the harness with the smallest additive surface: a `--stamp-key KEY=VALUE` passthrough
  (inert unless passed, byte-identical manifests when absent, tested), which the launcher feeds
  from the `BLIND_COMMIT` file. The stamp is written to **BOTH** addresses §3 names, identically:
  **`manifest["BLIND_COMMIT"]`** (top level) and **`manifest["config"]["stamps"]["BLIND_COMMIT"]`**
  (under `config.*`) — the same belt-and-braces the harness already uses for `cand_tiearb`, so no
  adjudicator has to win an argument about which address is canonical. **NOW: NO, on all three.**
- **`G-N`** — 400 games per cell follows from `--n 400` in `COMMON`; the 2% failure tolerance
  matches the campaign's own precedent (the b32v64 cell's 0.100% pre-existing rust panic-fail
  class), not an invented number, and `n_failed` is written by the harness on every run. **NO.**
- **`G-TIMING`** — the interval was derived in DESIGN §3.2 from real measured ms/move figures with
  margin either side, and §9's pilot verifies it on the actual box before any cell band is
  touched. ⚠️ Named honestly for this successor: **§9's one `--sims` re-pick is already SPENT**
  (k4×1032, frozen on the discarded first-attempt pilot band before any cell ran — DESIGN §0 item
  5), so the pilot here CONFIRMS the ratio rather than re-picking. That makes `G-TIMING` a gate
  the pilot can still FAIL — which is correct and intended: it is a real precondition, not a
  formality, and a fail is a pair-level decision for the orchestrator, not a silent second
  re-pick. It does not fail on a healthy run *at the frozen budget the pilot verified*. **NO.**
- **`G-SAT`** — the probe was measured non-saturating against h800 at this budget class
  (`fair_ruler_rebase_2752`: wr 0.685, off both rails — DESIGN §3.2(3)), so `[0.50, 0.90]` has
  room on both sides. ⚠️ Newly named, since the first attempt's §3.1 skipped it: this gate is a
  genuine PROPERTY OF THE DATA, not of the launcher — a healthy run CAN fail it if the champion
  leaf at k4×1032 turns out to saturate against h800 where the 2752 cell did not. That is the
  gate doing its job (a rails reading is not a spacing reading), and it is stated here so a
  `G-SAT` void reads as the pre-registered outcome it is, not as a surprise. **Does it fail on
  EVERY healthy run? NO.**

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

---

## §4.3 — THE COMPANION TABLE (printed on EVERY branch including `U-UNREADABLE`)

Per cell — CELL R800 and CELL R1600, each:

1. n games, n decks, seat balance, W/D/L, winrate + its z, elo ± 1σ + 95% CI vs h800, own
   deck-paired margin ± se and its z, n_failed, failure rate (stated even when zero).
2. `champ_prefix_ms_per_move`, `rung_ms_per_move`, realized time ratio, `solver_secs_per_game`.
3. band, both leaf hashes (`config.cand_leaf_hash`, `config.rung.leaf_hash`), rules profile, code
   rev, `carc_rs_version`.

Then, once:

4. `S`, its computed `se(S)` (beside the DESIGN §4.2 pre-registered expectation, 1.25 pts), `z_S`,
   `n_common`, and the elo-equivalent conversion with the scale used. **This `se(S)` — printed here
   as `se_realized` — is also the `D2-COMPRESSED`-reachability witness (§4's boundary note): that
   branch is reachable only where `se_realized < 1.25 pts`, so this line is what a reader checks to
   see whether a `D2-COARSE` finding had any room to have come out `D2-COMPRESSED` instead.**
5. Every §3 gate with its realized value and which manifest address resolved it.
6. The DESIGN §1 table (CL-023's +55.2 elo, results.csv's +20.0 elo) reprinted beside the
   readout's own `S`/elo, so a reader never has to leave the readout to see what this cell was
   adjudicating between.

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
