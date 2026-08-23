> ⛔ **DRAFT — NOT BLIND-COMMITTED — NOT LAUNCHED.** Prepared 2026-08-23 under
> `docs/TRACK_D_PREP_2026-08-23.md`. No band is claimed, no games have been played,
> no owner authorization exists. The blind-commit discipline (freeze the pair, commit
> it, stamp `BLIND_COMMIT=<sha>` before game 1) is DEFERRED to the orchestrator —
> nothing here may be cited as a pre-registration until that commit exists.

# READ_RULE — rung compression (D2)

> **⚠️ BLIND ORDERING (once this pair is actually committed). This file is meant to be
> committed BEFORE the band is claimed, BEFORE game 1, and BEFORE any statistic of any
> kind exists.** Its git commit is intended to be the proof. The branch that fires is
> taken **VERBATIM**, whatever it is. No owner call adjudicates any outcome; owner
> authorization funds the cell and does not name its answer.
>
> Design: [`DESIGN.md`](DESIGN.md). Run id `track_d2_prep`.

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
| `G-BAND` | both cells' `manifest.json` `seed_start` == 141000000000; record-derived deck sets agree; `n_common` == 200 | any mismatch |
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

Answered here, before launch, in the style of the jcz/`tiearb_widening` precedent that caught
unsatisfiable gates before they could void a healthy run:

- `G-SINGLEVAR`: guaranteed by the launcher building both cells' argv from one shared `COMMON`
  array (`run_cells_DRAFT.sh`) — the property is structural, not clerical, so it cannot fail on a
  healthy run.
- `G-RUNG`/`G-LEAF`/`G-RULES`: these fields are written by `eval_fair_puct.py`'s own manifest
  logic, already exercised identically by every F5 and tiearb cell that has run under this
  harness; the gate is checking that D2 used the harness normally, not asking it to do anything
  new.
- `G-TIMING`'s interval was derived in DESIGN §3.2 from real measured ms/move figures with margin
  either side, and the §9 pilot re-picks `--sims` ONCE if violated, before any cell band is
  touched — so a real-cell run inherits an already-verified-on-this-box ratio.
- `G-N`'s 2% failure tolerance matches the campaign's own precedent (b32v64 cell), not an
  invented number.

Answer for every gate: **NO** — none fails on a healthy run.

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
