> ## §0 — PROVENANCE BANNER (the pre-registered instrument-fix successor)
>
> ⛔→✅ **FROZEN 2026-08-23 (the blind commit is THE COMMIT THAT INTRODUCES THIS BANNER; its sha is stamped into `run_cells.sh` in the follow-up commit, per the b32v64 pattern). No statistic of any kind exists at freeze time.**
>
> **1. What this is.** This pair is the **pre-registered instrument-fix successor** to
> [`../track_d2_prep/DESIGN.md`](../track_d2_prep/DESIGN.md) / [`READ_RULE.md`](../track_d2_prep/READ_RULE.md),
> whose first attempt adjudicated **`U-UNREADABLE`** — the branch its own §4 names for a gate
> failure, and a fully acceptable outcome. Four INSTRUMENT gates failed. **No strength or spacing
> statistic from that run is adjudicated, quoted, or carried here**, and none was consulted in
> drafting this one.
>
> **2. This drafting session is STATISTICS-BLIND, per the first pair's §4 binding.** That clause
> reads, verbatim: *"If an instrument defect is found after a first adjudication, the session that
> writes the fix MUST be a session that has not seen `S`, `z_S`, or either cell's summary
> statistics."* The session that wrote this pair and the fixed launcher did not open the first
> attempt's `READOUT_D2.*`, any `summary.json`, or any per-game record. It read the frozen pair
> (which predates the run), the harness source, and a mechanics-only description of the four gate
> failures. **Bars do not move. §4 is not edited. Every §-numbered rule, branch, gate, and `n`
> below is VERBATIM from the frozen original.**
>
> **3. What changed, exhaustively:** the run id (`track_d2_prep` → `track_d2r2_prep`); the band
> (`141000000000` → **`144000000000`**, §5) and the pilot's disjoint range
> (`141999999000..007` → `144999999000..007`, §9); the launcher (§7/§9 references now point at the
> FIXED [`run_cells.sh`](run_cells.sh)); this banner; and the §3.1 structural test, re-run over
> **ALL** gates including `G-TOOL` (DESIGN §7 tail and [`READ_RULE.md`](READ_RULE.md) §3.1).
> Nothing else.
>
> **4. THE FOUR INSTRUMENT FIXES**, each closing one of the four failed gates:
>
> | # | gate that failed | mechanism of the failure | the fix, in this launcher |
> |---|---|---|---|
> | 1 | `G-RULES` | the first launcher never exported `CARCASSONNE_FIX_R9`, so `fixed_v1` cells ran with `r9_env_ok=False`. R9 **cannot** live in the rules profile — `base_deck` derives farm data at IMPORT time and the Rust registry latches a `OnceLock`, so it must be in the ENVIRONMENT before the process starts | `run_cells.sh` **exports `CARCASSONNE_FIX_R9=1` at file scope**, before any leg including `--pilot` and `--dry-run`, and `assert_r9_env` REFUSES to run if it is unset or not truthy |
> | 2 | `G-LEAF` | the probe played the **rung-default v2.9 leaf**, not the champion `curve125` leaf: for `--info fair --opponent h800` the harness does not auto-inject `curve125` (that fires only for `fair-netprior` / head-to-head / `bare-net` / `greedy`), so `cand_leaf_hash` read a non-champion hash in both cells | the champion leaf is injected the way production play does it — **in-process via `--cand-leaf-json`** ([`champion_leaf_curve125.json`](champion_leaf_curve125.json)), never by exporting the curve env (which would move `DEFAULT_CONFIG` and therefore MOVE THE RUNG). `preflight_leaf` builds one champion **through the harness's own module** and asserts, before game 1, candidate `== a36d2e15a3b3d71d` **and** rung `== 42af12fce22e1a0f` |
> | 3 | `G-TOOL` (a) | the two cells ran at **different repo revs** — a commit landed on main between the legs via a freeze-latch override — so the pair was not one instrument | the launcher **snapshots `git rev-parse HEAD` + a code-path dirty fingerprint at start and RE-CHECKS before EACH cell**, refusing to start a subsequent cell if either moved, loud, with both revs named. Plus a **dirty-CODE refusal** for real cells (pilot exempt), overridable only by `LAUNCH_DIRTY=1` with a mandatory `LAUNCH_DIRTY_REASON`, logged |
> | 4 | `G-TOOL` (b) | the "`BLIND_COMMIT` in both manifests" sub-clause was **UNSATISFIABLE**: `eval_fair_puct.py` had no stamping path at any address the read-rule searches (its `leaf_env` block is an allowlist of leaf knobs and lands at `manifest["leaf_env"][...]`, which is neither manifest top level nor `config.*`) | a minimal, additive **`--stamp-key KEY=VALUE`** passthrough was added to the harness's manifest writer (inert unless passed; tested). The launcher routes the `BLIND_COMMIT` file's content through it, landing the stamp at **BOTH** searched addresses: **`manifest["BLIND_COMMIT"]`** and **`manifest["config"]["stamps"]["BLIND_COMMIT"]`** |
>
> **5. ⚠️ THE §9 PILOT'S ONE RE-PICK IS ALREADY SPENT AND CARRIES.** The probe budget that runs
> is **k4×1032**, not the `--sims 688` written in §3.1 below. That re-pick was taken under §9's
> *"`--sims` is re-picked **ONCE**, on the pilot, and **FROZEN** before any cell seed is touched"*
> — on the **discarded** first-attempt pilot band, **before any cell ran and therefore before any
> statistic existed**. It is an **execution-layer** value, not a bar, and it **carries verbatim**
> into this successor: §3.1's frozen text is preserved unedited (bars do not move), and the
> launcher's `COMMON` array is the operative value. **§9's re-pick allowance is now EXHAUSTED** —
> a pilot-ratio FAIL here is a pair-level decision for the orchestrator, not a second re-pick.
>
> **6. ⚠️ §6's cost arithmetic is the 688-era figure and reads LOW.** The probe runs at 1.5× the
> per-move sims §6 costed, so the probe side of each cell costs proportionally more; the
> rung-dominated shape of `CELL R1600` (§6's actual point) is unchanged. §6 is preserved verbatim
> because it is not a bar; the operative expectation is that both cells cost more wall-clock than
> the numbers printed there.
>
> **7. Provenance of the original.** Drafted under `docs/TRACK_D_PREP_2026-08-23.md`; reviewed by
> the orchestrator (one REQUIRED amendment: the COARSE/COMPRESSED dispersion-conditional boundary,
> applied pre-freeze). Launch authorization: the owner's 2026-08-23 directive (prep Track D + "if
> everything were ready to launch... launch shortest wallclock first" + "you take it from here").
> That authorization funded the *question*; §0's four owner sign-offs below are owed again for
> this band.
>
> **8. AMENDMENT 2026-08-24 — band substituted, `143000000000` → `144000000000`, nothing else.**
> At draft time (item 4 table, c9fac9b9) `143000000000` was the registry's next free step-aligned
> start. Between that freeze commit and this ceremony, an UNRELATED session claimed
> `143000000000` for `measurement/carcasum_rung2_prep/` (`governance/BAND_REGISTRY.csv`, status
> `claimed`, `claimed_date` 2026-08-23) — a same-day race between two independent prep sessions,
> neither aware of the other. Re-read of the registry at launch time (2026-08-24) shows
> `144000000000` is the next free step-aligned start (`142000000000` and `143000000000` both
> claimed; `145000000000`+ unclaimed). **This is a pure band substitution, mechanically identical
> in kind to the original's own `141000000000` → `143000000000` swap (item 3 above): every
> `143000000000` seed-start / manifest-match literal and the §9 pilot's disjoint sub-range
> (`143999999000..007` → `144999999000..007`) are replaced verbatim; the predecessor's own band
> (`141000000000`, the voided first attempt) is untouched wherever it appears. No bar, gate,
> threshold, branch condition, probe config, or rung config is touched. Zero games exist under
> this pair at amendment time** (`BLIND_COMMIT` still the placeholder, `BAND_CLAIMED` absent), **so
> blindness is preserved trivially — this amendment predates game 1 by construction, same as the
> original successor's own drafting predated the first attempt's readout.** Owed sign-offs (item
> below) are unaffected; the band re-pick itself needs no fresh authorization beyond what the
> band-claim checklist already requires (band claimed in the registry before launch).
>
> **9. AMENDMENT 2026-08-25 — PROBE BUDGET RE-PICKED, `k4×1032` → `k4×1376` (total 4128 → 5504).
> SUPERSEDES ITEM 5's operative value; item 5's text stands verbatim as the record of what it
> superseded. Nothing else in the pair is touched.** Zero games exist under band `144000000000`
> at amendment time (no cell output directory, no `DONE_*` sentinel, no `RUN_LIVE.json`), so this
> amendment **predates game 1 by construction** and the pair remains blind — the same footing as
> item 8's band substitution.
>
> **The reason, verbatim as authorized:** *"FIX 1 (the R9 export, itself mandated by the first
> attempt's void) makes the python h800 rung ~58% more expensive per move (553.8→877.2 ms,
> reproduced within 0.4% on two boxes) — the frozen equal-time budget was derived against non-R9
> rung figures and is arithmetically unreachable under the corrected instrument (ratio 0.659 vs
> bar [0.85,1.20]). Re-pick preserves DESIGN §3.2(2)'s named-lineage-budget property (k4×1376 =
> `fair_ruler_rebase_5504`) and restates the §3.2 derivation against the R9 rung: 5504 × 0.140
> ms/total-sim = 770.6 ms → ratio 0.878, in-bar."*
>
> **The §3.2 derivation, RESTATED against the R9-era rung** (the original §3.2(1) text stands
> verbatim below; it is the non-R9 derivation and is superseded by this paragraph for the purpose
> of picking the probe budget). §3.2(1) priced equal-time against F5 `rung_ms_per_move` figures of
> **383.8 / 384.9 / 387.0 / 388.6 / 443.5 ms (median 387.0)** — all measured with `r9_env_ok`
> **False**, the pre-FIX-1 era. Under FIX 1 the same frozen h800 rung, same code rev, same box,
> measures **877.2 ms/move**. The probe side is nearly unaffected (rust: 539.3 → 577.7 ms, +7%),
> so the equal-time target moves with the rung. Measured probe cost is **577.7 ms / 4128 total
> sims = 0.140 ms per total-sim** (§3.2's own 11008-cell figure implies 0.154; consistent). Equal
> time against the R9 rung therefore needs **877.2 / 0.140 ≈ 6,264 total sims**, and the in-bar
> window `[0.85, 1.20]` spans **≈5,326 to ≈7,519 total**. **k4×1376 = 5,504 total ⇒ 770.6 ms ⇒
> ratio 0.878**, inside the bar with margin on the low side, and it is a **named production-lineage
> budget** (`fair_ruler_rebase_5504`, §3.2(2)'s "not an invented config" property) rather than a
> number assembled to hit a bar. `k4×1566` would centre the ratio at 1.00 but is invented; the
> named budget was preferred, per §3.2(2).
>
> ✅ **REALIZED, on the local box, before any cell seed was touched:**
> `champ_prefix_ms_per_move = 830.581`, `rung_ms_per_move = 880.999`, **ratio = 0.9428, PASS**
> against the unchanged `[0.85, 1.20]` bar — better than the 0.878 projection (the probe scales
> very slightly superlinearly in sims: 830.6 ms realized vs 770.6 ms projected at 5504 total, i.e.
> 0.151 ms/total-sim at this budget against the 0.140 measured at 4128 — which is itself closer to
> §3.2's own 0.154 figure). `n_failed = 0`; probe winrate vs h800 = 0.625, inside `G-SAT`'s
> `[0.50, 0.90]` with room on both rails. The pilot band `144999999000..007` is DISCARDED and
> never pooled, per §9.
>
> ⚠️ **§6's cost arithmetic now reads LOWER STILL.** Item 6 already flagged §6 as a 688-era figure
> reading low at 1032; at 1376 the probe side is 2× the sims §6 costed. `CELL R1600` remains
> rung-dominated (§6's actual point) and the rung side is itself ~58% dearer under FIX 1, so both
> cells cost materially more wall-clock than §6's printed numbers. §6 is preserved verbatim
> because it is not a bar.
>
> ⛔ **THE RE-PICK ALLOWANCE IS NOW EXHAUSTED FOR A SECOND TIME AND DOES NOT RENEW.** This is a
> pair-level decision taken by the orchestrator under READ_RULE §179–183's own delegation
> (*"a fail is a pair-level decision for the orchestrator, not a silent second re-pick"*) — it is
> NOT the launcher re-picking, and §9's clause is not re-armed by it. **If the pilot at k4×1376
> also reads out of bar, the run STOPS and returns to the orchestrator; it does not re-pick a
> third time.** No bar, gate, threshold, branch condition, rung config, band, or `n` is touched by
> this amendment. `G-TIMING`'s interval is unchanged at `[0.85, 1.20]`.
>
> **9a. THE STANDALONE FINDING (it outlives this pair).** **R9's import-time farm derivation costs
> the PYTHON leaf ~58% per move** — measured on the frozen `HeuristicMCTS(h800, c=3.0)` rung,
> leaf `42af12fce22e1a0f`, same code rev and same box: **553.8 ms/move with `r9_env_ok=False` vs
> 877.2 ms/move with `r9_env_ok=True`**, reproduced within 0.4% on a second box (laptop-wsl, W=16:
> 787.3 ms, ratio identical to 3 s.f.). The rust probe side is nearly unaffected (+7%), so the
> cost is specific to the Python leaf path, not to the rules change as such. **Any future
> equal-time pairing of a rust candidate against a Python rung must be priced against R9-era rung
> figures** — the pre-FIX-1 F5 numbers (`383.8`–`443.5` ms) understate an R9 rung by ~2.2×, and a
> budget derived from them will land ~0.66 of equal time and fail a `G-TIMING`-class gate. This is
> recorded here rather than only in this pair's log because the defect it caused (a frozen budget
> invalidated by a *correctness fix applied to the same instrument*) is a general trap: **an
> instrument fix can invalidate a calibration that was frozen against the unfixed instrument.**
>
> **9b. EXECUTION DEVIATION #1, recorded — `CARC_PY`.** The frozen cells were launched from the
> `d2r2-freeze` **worktree** (rev `4105baed`, working tree clean, 0 dirty entries including all
> `CODE_PATHS`). A worktree carries no `.venv`, so `run_cells.sh`'s `PY="${CARC_PY:-$REPO/.venv/bin/python}"`
> resolves to a nonexistent interpreter and the launcher aborts; `CARC_PY` was set to the main
> tree's venv (`/home/doctor/projects/carcassone/.venv/bin/python`). The launcher's header scopes
> `CARC_PY` to dry-run/pre-flight use, so this is named as a deviation rather than passed over.
> **It is inert here:** `src/`, `engine/` and `scripts/classical_search/` are **byte-identical**
> between the freeze rev `4105baed` and the main tree's `HEAD` (`70843eb7`) — `git diff` between
> them touches only `scripts/carcasum_match/`, `scripts/rustport/` and `tests/`, none of which is
> on this cell's execution path — so the venv's editable install resolves the same source the
> pinned rev carries, and `code_rev` in the manifests is not a lie. ⚠️ **The obvious "fix" is
> WRONG:** prefixing `PYTHONPATH` to the worktree's `src`/`engine` would break the run, because the
> worktree carries no built Cython extensions (`flat_leaf_cy`, `flat_repr_cy` `.so` live only in
> the main tree) and `preflight_leaf`'s `_assert_cy_float_path` would fail. The launcher does not
> assert rev equality against the main tree, so no other accommodation was needed.

# RUNG COMPRESSION: IS THE REFERENCE LADDER'S SPACING A USABLE UNIT? — DESIGN (DRAFT)

Run id `track_d2r2_prep`. Pair: this file + [`READ_RULE.md`](READ_RULE.md). Launcher (drafted,
non-executable): [`run_cells.sh`](run_cells.sh). Band claim (drafted, not appended):
[`BAND_CLAIM_DRAFT.json`](BAND_CLAIM_DRAFT.json). Roadmap item **D2**
([`../../docs/PROGRAM_ROADMAP_2026-07-07.md`](../../docs/PROGRAM_ROADMAP_2026-07-07.md), Track D).

Style precedent: [`../jcz_tiearb_20260817/DESIGN.md`](../jcz_tiearb_20260817/DESIGN.md) /
[`READ_RULE.md`](../jcz_tiearb_20260817/READ_RULE.md) — read for shape, not copied for content.

---

## 0. AUTHORIZATION BLOCK

**NOT AUTHORIZED.** Nothing in this pair may launch, claim a band, or spend a core-hour until the
owner signs off on all four of the following, explicitly, before game 1:

| # | owed sign-off | why it is the owner's call, not this draft's |
|---|---|---|
| (a) | **funding the ~16 core-hours** (§6) | this is spend, and the standing cost-discipline rule requires a one-sentence confirm before anything that burns time |
| (b) | **the band claim** — 144000000000 (§5) | `governance/BAND_REGISTRY.csv` is a source of truth the orchestrator edits, not a builder |
| (c) | **the probe-budget choice** — k4×688 = 2752, the equal-time reading (§3) — vs the optional k8×1376 = 11008 production-agent extension (§6) | two different questions at two different costs; the owner picks which is funded |
| (d) | **tie-arbiter OFF** | the probe P is the pre-arbiter fair PIMC champion; running WITH the arbiter would confound the rung-spacing question with the arbiter's own tied-ply behavior, which is exactly the class of confound this cell exists to avoid introducing |

**Pre-launch checklist** (mirrors the jcz / b32v64 precedent, all must be true before any real
cell fires):

- [ ] band claimed in [`../../governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv) (144000000000, per §5)
- [ ] this pair (`DESIGN.md` + `READ_RULE.md`) frozen and committed to `main`
- [ ] `BLIND_COMMIT=<sha>` stamped into the launcher's config (§ launcher, `run_cells.sh` currently reads a placeholder and refuses to run without it)
- [ ] the §9 pilot has run and its gate has PASSED (equal-time ratio inside [0.85, 1.20])
- [ ] process census clean on every box this cell touches (standing repo rule — census before any launch)
- [ ] `RUN_LIVE.json` sentinel dropped for the duration (freeze-latch discipline; see `run_cells.sh`)

---

## 1. THE QUESTION

**Roadmap line, quoted verbatim** ([`../../docs/PROGRAM_ROADMAP_2026-07-07.md:111`](../../docs/PROGRAM_ROADMAP_2026-07-07.md)):

> - **D2. Rung-compression cell** (audit #5): PUCT rung @equal-time-h800 vs h800/h1600 rungs,
>   shared decks, n=200 each (~2h) — are ladder *spacings* denominated in weak-search units? Fix
>   the c=1.5-rungs vs c=3.0-champion inconsistency in the same pass.

Every strength number this program quotes against the heuristic ladder is denominated in ONE
unit — the gap between adjacent h-rungs. If that unit is small and shrinking, elo distances
measured on the ladder compress, and the ladder stops being a ruler: two effects that would read
as "clearly different" on a wide unit can read as noise on a narrow one, and a program that keeps
citing ladder-denominated elo without knowing the unit's size is at risk of over-reading its own
numbers.

The program has **two prior measurements of the h800→h1600 spacing and they disagree by 2.8×**:

| source | contrast | n | band | result |
|---|---|---|---|---|
| [`../level2/LEVEL2_LADDER_VERDICT.md`](../level2/LEVEL2_LADDER_VERDICT.md) (CL-023, 2026-06-18) | heur_v2_7@1600 vs @800 | 400, paired | fresh, 3.0e9+ | **+55.2 ±17.6 elo, paired z 3.23** |
| [`../../experiments/results.csv`](../../experiments/results.csv) row `l22_ctrl_heur1600_vs_heur800_b310_n400` (2026-06-19) | heur@1600 vs heur@800 | 400, paired | 3.10e9 | **+20.0 elo, sigma 17.4, z 3.285** |

The full CL-023 ladder reads **@200→@800 +75.9 (z3.59) · @800→@1600 +55.2 (z3.23) ·
@1600→@3200 +34.9 (z2.36)** — a shrinking-per-doubling pattern that is the house prior for what
this cell should find (§6 of READ_RULE names it explicitly, before game 1).

Same contrast, same n, different bands, 2.8× apart — consistent in *direction* with CL-068's
measured 1.8–2.2× cross-band over-dispersion, but **UNRESOLVED**: the two readings were never
compared within one band, deck-paired, at a fixed knob set. Per the project's results-discipline
rule (`CLAUDE.md`: "a new result that contradicts a prior one is not a discovery until the
contradiction is resolved"), this is an open contradiction, not a settled fact. **D2 resolves it
on a fresh band with a fixed probe, on the rung the ruler of record actually uses.**

---

## 2. THE c=1.5 / c=3.0 INCONSISTENCY — NAMED AND RESOLVED HERE, AT ZERO GAMES

This is load-bearing: the roadmap line asks D2 to "fix the c=1.5-rungs vs c=3.0-champion
inconsistency in the same pass." The evidence chain below shows there is **no configuration
inconsistency to fix** — the inconsistency is a documentation defect, correctable without a single
game.

### 2.1 The evidence chain

1. **The module default has always been 3.0.** [`../../src/carcassonne_ai/mcts.py:36`](../../src/carcassonne_ai/mcts.py):
   `DEFAULT_C = 3.0  # Ameneyro et al. 2020 — UCT exploration constant`. `MCTS.__init__`
   (line 82) reads `c: float = DEFAULT_C`. `HeuristicMCTS.__init__` (line 315) is
   `def __init__(self, *args, heur_leaf: str = "v1", leaf_cfg=None, value_norm=None, **kwargs):`
   — it forwards `**kwargs` to `super().__init__(*args, **kwargs)` and defines no `c` of its own.
   A `HeuristicMCTS(...)` construction that passes no `c` therefore runs at **3.0**, not 1.5.

2. **History: it has NEVER been 1.5.** `git log -L 30,40:src/carcassonne_ai/mcts.py` and
   `git show 534043a4:src/carcassonne_ai/mcts.py` confirm `DEFAULT_C = 3.0` was introduced at
   line 34 in commit `534043a4` ("phase 2: vanilla MCTS with state-mutation rollout
   optimization", 2026-04-28) and has not moved since (the later shift to line 36 is an unrelated
   `import` line added ahead of it in `c96f6003`, 2026-07-27). There is no commit in the file's
   history where `DEFAULT_C` reads 1.5.

3. **Every construction site relevant to the heuristic rungs was enumerated** (grep over
   `scripts/` and `src/` for `HeuristicMCTS(`). The rung constructors that feed the ladder pass
   **no `c`** — i.e. they run at the module default, 3.0:
   - [`../../scripts/ladder_rung_eval.py:89`](../../scripts/ladder_rung_eval.py) — `self._m = HeuristicMCTS(game=game, simulations=sims, seed=seed, heur_leaf=heur_leaf)`, the L2 ladder's own rung.
   - [`../../scripts/level2/eval_hybrid_handoff.py:203,238`](../../scripts/level2/eval_hybrid_handoff.py) — the hybrid-handoff cells' rung constructions, same shape.

   The sites that DO pass `c` explicitly all pass **3.0**:
   - [`../../scripts/classical_search/eval_fair_puct.py:770`](../../scripts/classical_search/eval_fair_puct.py) — `self._m = HeuristicMCTS(game=game, simulations=sims, c=RUNG_C, seed=seed, ...)`, with `RUNG_C = DEFAULT_C  # 3.0` defined at line 421 — this is the CL-022 rung, the exact rung D2 uses.
   - [`../../scripts/classical_search/eval_puct_priors.py:330`](../../scripts/classical_search/eval_puct_priors.py) — `self._m = HeuristicMCTS(game=game, simulations=sims, c=CHAMP_C, seed=seed, ...)`, with `CHAMP_C = 3.0  # production UCT exploration constant for HeuristicMCTS` at line 159.
   - [`../../scripts/f3_public_state_oracle/mine_roots.py:118`](../../scripts/f3_public_state_oracle/mine_roots.py) — `agent = HeuristicMCTS(game=game, simulations=sims, c=3.0, seed=12345, ...)`.
   - [`../../scripts/canonical_az/fairness_decision_probe.py:144`](../../scripts/canonical_az/fairness_decision_probe.py) — `return HeuristicMCTS(game=game, simulations=sims, c=c, seed=seed, ...)`, where the caller's `c` documented at line 21 is `c=3.0`.

⇒ **EVERY heuristic rung this program has ever run — the L2 ladder, the hybrid cells, and the
CL-022 rung inside `eval_fair_puct.py` — ran at UCT c = 3.0.** There is no configuration
inconsistency to fix.

### 2.2 Where the "1.5" claim actually lives — the documentation defect, in two places

**(i) [`../level2/LEVEL2_LADDER_VERDICT.md`](../level2/LEVEL2_LADDER_VERDICT.md), "Config note"
(lines 10–21), quoted:**

> All heuristic rungs use `HeuristicMCTS` at the module default **c_puct = 1.5**. This is **not**
> a deviation: in the production eval gate (`eval_net_vs_heuristic.py`) the `--c-puct 3.0` flag is
> applied to the **neural** side only — the `HeuristicMCTS` opponent is constructed without
> `c_puct` and so has *always* run at 1.5. The `old_c=3.0` column in prior results.csv ladder rows
> is the **net-side** c, not the heuristic's.

This is **inverted**: §2.1 shows the module default is 3.0, not 1.5 — "constructed without `c_puct`"
means it runs at `DEFAULT_C = 3.0`, the opposite of what the note infers. The note's own R4/R5/R5'
rungs (`heur_v2_7@800/1600/3200`, the CL-023 numbers §1 cites) were built exactly this way — no
`c` passed — and therefore ran at **3.0**, not 1.5.

**(ii) [`../../experiments/results.csv`](../../experiments/results.csv) stamps `old_c=1.5` on the
rung side of the F5 fair-ruler rows** — `fair_ruler_rebase_2752`, `fair_ruler_rebase_5504`,
`fair_ruler_rebase_11008`, `fair_ruler_k8x688_5504`, `fair_ruler_k8x1376_11008` — while those
cells' own `manifest.json` records `config.rung.c = 3.0` (verified directly:
`/mnt/c/carc-shared/classical_search/fair_ruler_rebase_2752/manifest.json` §`config.rung` reads
`"agent": "HeuristicMCTS", "c": 3.0, "sims": 800, ...`). The **candidate**-side `new_c` column on
those same rows correctly reads 1.5 — that is the probe's own `--c-puct 1.5` (a PUCT knob, a
different axis entirely from the rung's plain-UCT `c`) — so the csv is not wrong about the
candidate, only mislabeled about the rung. By contrast, the older D0 rows
(`fair_ladder_s*_vs_h800_k2`) correctly carry `old_c=3.0` on the rung side — the mis-stamp is
localized to the five F5 rows above, not systemic across the whole table.

### 2.3 Resolution costs ZERO games

Correcting the LADDER_VERDICT config note and the five mis-stamped `results.csv` rung-`c` cells is
a documentation fix, **owed to the owner, not executed unilaterally by this draft** — `results.csv`
is a source of truth (`CLAUDE.md`: "STATUS / EXPERIMENTS / DECISIONS *cite* results.csv; they must
not carry authoritative numbers that drift"), and a bot editing five historical rows without
sign-off would itself be exactly the kind of unreviewed mutation that rule exists to prevent.

⇒ **D2 therefore carries NO exploration-constant arm and needs NO harness change.** State this
explicitly for the record: an earlier reading of the roadmap line — one that took "fix the
c=1.5-rungs vs c=3.0-champion inconsistency" at face value as a real configuration gap — would
have funded a 2×2 (`rung_sims` × `rung_c`) design at roughly double this cell's cost, for a second
arm that (per §2.1) has no experimental content: there is nothing to sweep, because every rung
this program has ever run was already at c=3.0.

⚠️ **Caveat.** This section is a code-and-history argument against HEAD plus the full `DEFAULT_C`
commit history — it is not a replay of the 2026-06-18/2026-06-19 binaries that produced the two
numbers in §1. It resolves the *configuration* question (was there ever a c=1.5 rung?) with
certainty; it does not, by itself, resolve *why* the two elo readings in §1 disagree by 2.8× — that
is what the two game-cells in §3 measure.

---

## 3. THE TWO CELLS

Both cells run [`../../scripts/classical_search/eval_fair_puct.py`](../../scripts/classical_search/eval_fair_puct.py).
They differ in **exactly one experimental argument: `--rung-sims`**. (They also differ in
`--out-subdir` and `--claim-host`, which are BOOKKEEPING — two cells cannot share one output
directory or one `--shared-claim` tag without corrupting each other, the same shape
`run_cells.sh` in the b32v64 cell states for its own pair.)

| | **CELL R800** | **CELL R1600** |
|---|---|---|
| cell id | `d2_rung800` | `d2_rung1600` |
| rung | `HeuristicMCTS(h800, c=3.0)` | `HeuristicMCTS(h1600, c=3.0)` |
| `--rung-sims` | `800` | `1600` |
| probe P | frozen, identical (below) | frozen, identical (below) |
| n | 200 decks × 2 seatings = 400 games | 200 decks × 2 seatings = 400 games |

### 3.1 Probe P — frozen, identical in both cells

```
--info fair --opponent h800 --backend rust --k-dets 4 --sims 688 --exact-k 2
--c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits
--rules-profile fixed_v1
```

k4×688 = **2752 total sims**, tie-arbiter **OFF** (no `--cand-tiearb-*` flags at all — §0(d)).

### 3.2 Why this probe

**(1) It IS the roadmap's "PUCT rung @equal-time-h800."** Measured `rung_ms_per_move` for the h800
rung across the five F5 fair-ruler cells: **383.8 / 384.9 / 387.0 / 388.6 / 443.5 ms** (median
387.0). The rust champion at total 11008 sims (k8×1376) measures `champ_prefix_ms_per_move`
**1466.5 / 1676.4 / 1721.0 / 1861.6 ms** across four deploy-11008 cells. ⇒ **≈0.154 ms per
total-sim** at the rust champion's scale ⇒ equal-time ≈ **2,507 total sims**, and **k4×688 = 2752
is within 10% of that.**

**(2) It is a NAMED production-lineage config, not an invented one** — k4×688 = 2752 is the
**pre-2026-07-29 deploy champion** (`governance/PRODUCTION.yaml`'s `fair_kdets_folded_in:
2026-07-13`; superseded for *desktop* deploy on 2026-07-29 by the k8×1376=11008 promotion, but
k4×688 remains the correct allocation at total 2752 and is still what the mobile profile runs —
CL-071, the same budget CL-054 confirmed at +5.18±1.24 pts/deck over the then-deployed k8). It is
not a config assembled for this cell; it is a config the program has already run, at this exact
band-independent total, five separate times (§3.3).

**(3) It is measured non-saturating against h800.** `fair_ruler_rebase_2752` at this exact
budget scored **wr 0.685 / +135.0 elo / paired margin +8.64** vs h800 — off both rails, so the
margin statistic has headroom in both directions against both rungs (h800 and h1600 alike).

### 3.3 ⚠️ DEVIATION, NAMED: "equal-time" is a deployable-value statement, not an algorithmic one

"Equal-time" here means equal wall-clock **in the deployed implementations** — a rust candidate
against a rung that is frozen Python by design. `eval_fair_puct.py`'s own manifest note records
that "the h800 / greedy / bare-net rungs are FROZEN RULERS and stay Python by design." The probe
therefore compares a rust PUCT search to a Python plain-UCT search at matched wall-clock, **not**
matched node count or matched algorithm-internal cost. **It is a DEPLOYABLE-VALUE statement — "at
the wall-clock this program actually pays for the deployed candidate, how far ahead of h800 is
it?" — NOT an algorithmic "PUCT search is X× better than UCT search per node" statement.** The
realized ratio is reported, not assumed, from `champ_prefix_ms_per_move` / `rung_ms_per_move` in
each cell's `summary.json` (the field-name trap named below applies to reading it).

⚠️ **Field-name trap, inherited from the jcz precedent (`READ_RULE.md` §0.C):** in
`eval_fair_puct`, `champ_prefix_ms_per_move` is the **CANDIDATE** side — the opposite convention
from `eval_puct_priors`. Any read-out that swaps them inverts the timing reading.

### 3.4 ⚠️ NOT POOLABLE WITH THE F5 LADDER

The F5 fair-ruler rows (`fair_ruler_rebase_*`, `fair_ruler_k8x*`) ran on the **python** backend
(verified: the `fair_ruler_rebase_2752` manifest has no `backend` key and no `rust`-side timing
fields at all) under **pre-`fixed_v1`** rules (the manifest has no `rules_profile` key of any
kind — the field is simply absent, not stamped `walled` or `null`; that absence is itself the
signature of the pre-rules-profile era). D2 runs `fixed_v1` + rust on the probe side. **D2's
ABSOLUTE numbers are therefore not comparable to `fair_ruler_rebase_*`'s absolute numbers; only
D2's internal cell-vs-cell contrast (the primary statistic, §4) is claimed.** This mirrors the
jcz DESIGN §3.2 caveat about cross-era absolutes exactly.

---

## 4. THE PRIMARY STATISTIC AND ITS POWER — arithmetic BEFORE any number

**PRIMARY = the deck-paired spacing**

```
S = M_R800 − M_R1600
```

where `M_cell` is that cell's deck-paired mean margin (points/game, champion-probe-minus-rung,
i.e. probe-minus-rung) computed over the `n_common` decks present in BOTH cells. `S` is the
h800→h1600 rung gap expressed in probe-margin points — the same convention as
`eval_fair_puct._paired_z`. **Elo is SECONDARY**, reported for continuity with CL-023, converted
via the realized scale (§4.3).

### 4.1 The dispersion we are entitled to assume

At n=200 decks the F5 cells realized `paired_mean_margin / paired_z` ⇒ `se(M)`:

```
fair_ruler_rebase_2752    8.6425 / 9.5101  = 0.909 pts
fair_ruler_rebase_5504   10.7825 / 11.3029 = 0.954 pts
fair_ruler_k8x1376_11008  7.935 / 8.4547   = 0.939 pts
```

Take **se(M) ≈ 0.93 pts at n_paired = 200** — the middle of this range, at the same total-sims
order of magnitude as the probe.

### 4.2 CRN and se(S)

CRN (common decks, same seatings) is used across the two cells, but per CL-068 the measured
cross-cell CRN benefit was only ~9.9% of contrast variance in the comparable case (the jcz
DESIGN §4.1 precedent). Assume **ρ ≈ 0.10** — do not bank more than that:

```
se(S) = 0.93 × sqrt(2 × (1 − 0.10)) = 1.25 pts
```

### 4.3 What n=200 buys

```
2σ MDE(S)  = 2 × 1.25 = 2.50 pts
```

Converting with the realized scale of `fair_ruler_rebase_2752` (+135.0 elo ↔ +8.6425 pts ⇒
**~15.6 elo/pt**), that is **≈39 elo**.

| the prior reading | in points | z at n=200 | resolves? |
|---|---|---|---|
| CL-023's +55.2 elo | ≈3.5 pts | ≈2.8 | **YES** — comfortably above 2σ |
| results.csv's +20.0 elo | ≈1.3 pts | ≈1.0 | **NO** — inside the 2σ MDE |

**State this bluntly: at the roadmap's n=200 the cell can confirm the large prior (CL-023) but
cannot discriminate the small prior (results.csv) from zero. A null read at n=200 is therefore
NOT evidence that the spacing is zero — it is only a bound of ≤39 elo.** READ_RULE §4 names a
branch for exactly this outcome so it cannot be narrated as a refutation after the fact.

### 4.3.1 ⚠️ THE COARSE/COMPRESSED BOUNDARY COINCIDES AT THE COMMITTED DISPERSION — named here,
before game 1

READ_RULE §4's `D2-COARSE` (`z_S ≥ 2.0 AND S ≥ 2.5 pts`) and `D2-COMPRESSED`
(`z_S ≥ 2.0 AND S < 2.5 pts`) are read in order, first-match-wins — that is coherent, but the two
conditions' relationship to the committed `se(S) = 1.25 pts` above needs to be stated plainly
before any run exists, not discovered while reading a result.

At the committed `se(S) = 1.25 pts`, `z_S ≥ 2.0` **arithmetically implies** `S ≥ 2.0 × 1.25 =
2.5` — so at the committed dispersion, `D2-COARSE`'s and `D2-COMPRESSED`'s conditions **coincide
exactly at the boundary**. A run whose realized `se(S)` comes in AT or ABOVE 1.25 pts and clears
`z_S ≥ 2.0` lands in `D2-COARSE` by construction; it cannot land in `D2-COMPRESSED`, because doing
so would require `S < 2.5` while `S ≥ 2 × se(S) ≥ 2.5` simultaneously.

**`D2-COMPRESSED` is therefore reachable only when the REALIZED `se(S)` prints BELOW the committed
1.25 pts** — equivalently, at the `S = 2.5` boundary, `se_realized < S / z_S = S / 2.0`. This is
undeclared conditional reachability of exactly the class §3.1's structural test exists to name
before game 1, so it is named here: the branch is not equally reachable across the whole
`z_S ≥ 2.0` region — it opens up only where this run's actual dispersion beats the pre-registered
expectation.

⛔ **Consequence for the readout, stated now so it cannot be narrated later: a `D2-COARSE` finding
realized at `se(S) ≥ 1.25 pts` must NOT be reported as "compression is ruled out."** At that
dispersion the cell cannot separate a genuinely large, uncompressed spacing from a moderately
compressed one that still clears 2σ — it can only say the spacing is real and at least 2.5 pts.
Telling "large" apart from "moderately compressed but still significant" needs a realized `se(S)`
tighter than committed, which is a property of the run's actual data and is not something this
design can guarantee in advance. READ_RULE §4.3 item 4 prints `se_realized` beside `S` and `z_S`
on every branch specifically so this condition is checkable, not just inferred.

### 4.4 The n that would resolve the small reading — recorded now, funded by nobody

```
n=400 decks/cell:  se(S) = 0.88 pts  ⇒  2σ MDE = 1.77 pts ≈ 28 elo   (the +20 reading still only z≈1.5)
n=800 decks/cell:  se(S) = 0.62 pts  ⇒  2σ MDE = 1.25 pts ≈ 19 elo
```

Fully separating +55 from +20 needs **n ≈ 800 decks/cell (≈64 core-hours** — 4× §6's estimate).
**Honest framing: the design as sketched is a SCREEN for the large reading, not an adjudication
between the two priors.** Whether to fund the n=800 extension is a fresh owner decision, priced
here so a future "just add n" ask does not have to re-derive it (jcz DESIGN §4.3 precedent).

---

## 5. THE BAND

**Band `144000000000`** — the next free step-aligned start in
[`../../governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv). Registry high-water
at draft time is **141000000000** (the FIRST D2 attempt's own band, spent on the U-UNREADABLE run and retired with it; 142000000000 is spoken for by the drafted `../carcasum_match_prep/PREREG_DRAFT.md` row).

⛔ **NOT CLAIMED.** The row is DRAFTED in [`BAND_CLAIM_DRAFT.json`](BAND_CLAIM_DRAFT.json) and
must be appended to the registry by the orchestrator before launch.

Seeds `144000000000 .. 144000000199` (200 decks), used by **BOTH** cells (CRN by design — the
same deck set, same seatings, feeding §4's paired statistic).

Per CL-068, **band identity is load-bearing**: never pool D2's numbers across bands, and this
band **retires from confirmatory use** once it has influenced any decision (the standing policy
every retired row in `BAND_REGISTRY.csv` since 133000000000 has followed).

---

## 6. COST

Arithmetic from realized per-game records, not a model.

**Facts (measured, given):** a game is ~143 moves total, split ~70 probe decisions / ~71 rung
decisions (`champ_prefix_moves` 68–70, `rung_moves` 70–72 in real records). Probe at k4×688=2752
rust ≈ 0.425 s/move ⇒ **~29.8 s/game**; rust exact-K=2 solver ≈ 1.3 s/game (`solver_secs_per_game`
1.1–1.4 across four rust deploy-11008 cells). Rung h800 ≈ 0.387 s/move ⇒ **~27.5 s/game**; rung
h1600 ≈ 0.774 s/move (double the per-move cost, same order) ⇒ **~55.0 s/game**.

```
CELL R800    ≈ 29.8 + 27.5 + (1.3 solver amortized) ≈ 58.6 s/game
CELL R1600   ≈ 29.8 + 55.0 + (1.3 solver amortized) ≈ 86.1 s/game
```

At n=200 decks × 2 seatings = **400 games per cell**:

```
CELL R800    400 × 58.6 s = 23,440 core-s  =  6.5 core-h
CELL R1600   400 × 86.1 s = 34,440 core-s  =  9.6 core-h
                                    TOTAL  ≈ 16.1 core-hours
```

⚠️ Note the ~8× rust speedup on the probe side does NOT shrink the rung side (h800/h1600 stay
Python by design, §3.3) — **R1600 is rung-dominated**, and it is the more expensive cell despite
running fewer total probe-side sims than nothing.

**Wall-clock:** local 5900XT at W=22 ⇒ **≈0.75 h**; at W=16 ⇒ **≈1.0 h**. The roadmap sketched
~2h for this item — this design is inside that budget with margin.

### 6.1 Optional extensions — priced, unfunded

| extension | what it buys | cost |
|---|---|---|
| (a) a third cell at `--rung-sims 3200` | completes CL-023's third rung inside this cell's own band — shows whether spacing keeps shrinking within-band, the strongest version of the question | ≈15.7 core-h (h3200 ≈ 1.548 s/move ⇒ ~110.9 s/game rung-dominated, × 400 games) |
| (b) same pair, probe = CURRENT deploy champion k8×1376=11008 instead of the equal-time k4×688 | the production-agent reading rather than the equal-time reading — "how does the ladder unit look from the agent we actually run," at the cost of losing the equal-time framing | ≈35.8 core-h (11008-sims probe ≈ 1.7 s/move ⇒ 400×(≈1.7×70 + rung + solver) ≈ scales roughly with the champ_prefix ms/move figures in §3.2) |
| (c) n=400 or n=800 per §4.4 | resolves the small (+20 elo) prior, not just the large one | 2× or 4× §6's total |

None of (a)–(c) is authorized by this draft; each needs its own owner funding decision.

---

## 7. INTEGRITY GATES

Each is a PRECONDITION. Any FAIL ⇒ `U-UNREADABLE` (READ_RULE §4), no strength statistic is
adjudicated. This section is the summary; `READ_RULE.md` §3 is the binding text.

| id | proposition | VOIDS on |
|---|---|---|
| `G-BAND` | both cells' `manifest.json` `seed_start` == 144000000000; deck sets identical; `n_common` == 200 | mismatch |
| `G-SINGLEVAR` | the two cells' argv differ in exactly `--rung-sims`, `--out-subdir`, `--claim-host` and nothing else — diffed directly from the two `manifest.json` `config` blocks | any other differing key |
| `G-RUNG` | both manifests' `config.rung.c` == 3.0, `config.rung.agent` == `"HeuristicMCTS"`, `config.rung.leaf_hash` identical across cells, `config.rung.sims` == 800 / 1600 respectively | any deviation |
| `G-LEAF` | `config.cand_leaf_hash` == `a36d2e15a3b3d71d` in both cells | mismatch or absence |
| `G-RULES` | `rules_profile.name` == `"fixed_v1"`, `r9_env_ok` true, in both | anything else |
| `G-TOOL` | same `carc_rs_version` and `tile_data_semantic_digest` in both cells; same code rev; `BLIND_COMMIT` stamped in both manifests | any mismatch, or a `BLIND_COMMIT` still reading the placeholder |
| `G-N` | 400 games each, `n_failed` == 0 (failure rate stated even when zero) | short of 400, or any unexplained failure |
| `G-TIMING` | both cells report `champ_prefix_ms_per_move` and `rung_ms_per_move`; the R800 cell's realized ratio `champ_prefix_ms_per_move / rung_ms_per_move` is inside `[0.85, 1.20]` (§9 pilot bar) | outside the interval, or either field absent |
| `G-SAT` | probe winrate vs h800 inside `[0.50, 0.90]` in CELL R800 | outside it — the margin statistic is compressed and the cell is a floor/ceiling reading, not a spacing reading |

**The structural test** (jcz READ_RULE §0.F precedent): every gate above must be SATISFIABLE by
construction before launch — a gate that cannot pass on a healthy run is fixed BEFORE game 1,
never discovered after. **The binding text is [`READ_RULE.md`](READ_RULE.md) §3.1, which for this
successor is RE-RUN OVER ALL NINE GATES**, including the three the first attempt's audit skipped
(`G-BAND`, `G-TOOL`, `G-SAT`). That omission is why this pair exists: `G-TOOL`'s
`BLIND_COMMIT`-in-both-manifests sub-clause was structurally unsatisfiable against the harness at
either address the read-rule searches, and the audit that exists to catch exactly that never
asked it. **A partial structural test is the failure mode, not a lighter version of the test.**
Summary of the answers, in gate order: `G-BAND` pinned from one `COMMON` array; `G-SINGLEVAR`
structural in that same array (and none of the four fixes widens it — they are identical in both
cells); `G-RUNG` and `G-LEAF` now VALUE-checked before game 1 by the launcher's `preflight_leaf`
(rung `42af12fce22e1a0f`, candidate `a36d2e15a3b3d71d`, asserted distinct); `G-RULES` satisfiable
only because the launcher now exports `CARCASSONNE_FIX_R9` and refuses to run without it;
`G-TOOL` (a) harness-written, (b) now pinned by a start-of-run rev snapshot re-checked before each
cell, (c) now satisfiable via the additive `--stamp-key` passthrough writing `BLIND_COMMIT` to
BOTH searched addresses; `G-N` from `--n 400`; `G-TIMING` from the §3.2 derivation, verified by
the §9 pilot (whose one re-pick is already SPENT — §0 item 5); `G-SAT` a genuine property of the
data with room on both rails. Answer for every gate: **would this gate fail on every healthy run
of this launcher? NO.**

---

## 8. WHAT THIS CANNOT SHOW

Stated before launch so no branch can be narrated past them:

1. **It does not measure h1600-vs-h800 head-to-head.** The harness has no rung-vs-rung mode — the
   candidate side is always a PIMC agent, never a second `HeuristicMCTS`. A direct h1600-vs-h800
   cell would be both cheaper (no probe-side rust cost) and ~1.4× more powerful (no probe-side
   noise added to the contrast) — that is the right build if this question recurs and needs
   tighter resolution than §4 buys.
2. **It does not re-rate the champion.** The probe is the pre-2026-07-29 k4×688 mobile-profile
   config, not the current k8×1376 deploy champion (§6.1(b) is the unfunded extension that would
   touch that).
3. **It does not license any `governance/PRODUCTION.yaml` change.** Nothing here is a strength
   lever on the champion; it is an instrument-calibration question about the ruler.
4. **It does not transfer to the walled/python F5 ladder's absolutes** (§3.4) — D2's absolutes are
   `fixed_v1` + rust-probe, a different era from the F5 rows it is contextualized against.
5. **It does not tell you whether the ladder is the RIGHT ruler** — only how coarse its unit is at
   this rung, under this probe, on this band.
6. **A null result is a bound, not a zero** (§4.3) — this is the single most important thing this
   design commits to before any number exists, because it is the easiest thing for a later reader
   to get backwards.

---

## 9. THE PILOT (pre-blind, mandatory, ~5 minutes)

n=8 decks (`--n 16 --paired`) on a **SEPARATE seed range** `144999999000..144999999007` — never
the cell band — running **CELL R800's config only**.

**Purpose:**

(a) verify the realized equal-time ratio `champ_prefix_ms_per_move / rung_ms_per_move` is inside
`[0.85, 1.20]` on the actual box — if it is outside, `--sims` on the probe is re-picked **ONCE**,
on the pilot, and **FROZEN** before any cell seed is touched;

(b) confirm `n_failed == 0` and every §7 gate is structurally satisfiable against real records
from this exact harness invocation, not just against the harness's documented behavior.

The pilot band is **DISCARDED and never pooled** with the cell bands. ⛔ **The pilot is the only
place a knob may move; after the blind commit nothing moves.**

---

## 10. CLOSE-OUT (on adjudication, not before)

The six-touch checklist, verbatim from `CLAUDE.md`: (1) `experiments/results.csv` row — the
primary `S` statistic plus each cell's own vs-h800 reading · (2) `DECISIONS.md` index line ·
(3) status stamp on this `DESIGN.md` and on `READ_RULE.md` · (4) governance row flip
(`../../governance/BAND_REGISTRY.csv` `decision_influenced` + band retirement; a CL-023 amendment
if the branch that fires bears on it) · (5) `STATUS.md` top block · (6) the roadmap D2 line in
[`../../docs/PROGRAM_ROADMAP_2026-07-07.md`](../../docs/PROGRAM_ROADMAP_2026-07-07.md). Then
`python3 scripts/doc_lint.py`. Commit; do not push without asking.
