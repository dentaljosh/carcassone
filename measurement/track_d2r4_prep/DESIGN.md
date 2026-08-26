> ## §0 — PROVENANCE BANNER (the pre-registered RESPIN of attempt 3)
>
> ⛔→✅ **FROZEN 2026-08-26 (the blind commit is THE COMMIT THAT INTRODUCES THIS FILE; its sha is stamped into [`BLIND_COMMIT`](BLIND_COMMIT) in the follow-up stamping commit, per the b32v64 / d2r2 / d2r3 pattern). No statistic of any kind exists at freeze time.**
>
> **1. What this is.** Attempt 4 at roadmap item **D2**. Pair: this file +
> [`READ_RULE.md`](READ_RULE.md). Three prior attempts all adjudicated `U-UNREADABLE`. The first died
> of PROVENANCE; the second and third died of the **same** cause with **opposite signs**:
>
> | attempt | pair | band | cause of the void |
> |---|---|---|---|
> | 1 | [`../track_d2_prep/`](../track_d2_prep/DESIGN.md) | `141000000000` | **provenance** — `G-RULES` (`r9_env_ok=False`), `G-LEAF` (probe played the rung's leaf), `G-TOOL` ×2 (two code revs; an unsatisfiable `BLIND_COMMIT` sub-clause) |
> | 2 | [`../track_d2r2_prep/`](../track_d2r2_prep/DESIGN.md) | `144000000000` | **cost calibration** — `G-TIMING`, realized `0.8382` against the frozen `[0.85, 1.20]`, **below** the floor by 1.38% |
> | 3 | [`../track_d2r3_prep/`](../track_d2r3_prep/DESIGN.md) | `149000000000` | **cost calibration** — `G-TIMING` **burn-in abort at 80 of 800 games**, realized `1.5491`, **above** the ceiling by 29% |
> | 4 | **this pair** | `150000000000` | — |
>
> **⭐ ATTEMPT 3 SUCCEEDED AT ITS OWN MISSION AND THIS PAIR INHERITS THE WHOLE OF IT.** Attempt 3 was
> built to make a cost-calibration void CHEAP and to make co-tenancy IMPOSSIBLE TO MISS. Both worked
> on the first run: the burn-in gate fired at 80 of 800 games for **≈3.7 core-h instead of ≈44**, and
> `G-TENANCY` certified that window CLEAN — which is precisely what let the root cause be found the
> same morning. **The ONLY things attempt 4 changes are the probe budget (§3.2) and the band (§5).**
> Every gate, every bar, every branch, the burn-in window, the tenancy sampler, the alias-aware
> `G-SINGLEVAR`, `G-PROBE`, `G-TIMING-FULL`, the `champ_timeouts` clause and all four of attempt 2's
> instrument fixes are carried **VERBATIM**.
>
> **2. ⚠️ BLINDNESS DISCLOSURE — and it is STRONGER than any prior attempt's.** This is a fresh
> authoring session. **Attempt 3 produced NO statistic of strength whatsoever**: it aborted at the
> burn-in gate before a single adjudication ran, so no `S`, no `z_S`, no elo, no margin and no winrate
> exists from it anywhere in the program. The one attempt-3 artifact this pair reads is
> `/mnt/c/carc-shared/track_d2r3_prep/BURNIN_R800.json` — a **pure COST artifact**
> whose schema contains no outcome field at all. Attempt 3 had to disclose that it had read attempt
> 2's `S` and `z_S`; this pair has read no strength statistic from any D2 attempt, and there is none
> to read. The standing rule is unchanged and now trivially satisfied: **every quantity carried
> forward is a COST or a DISPERSION; no `S`, `z_S`, elo, margin or winrate from attempts 1–3 is used
> in any bar, threshold, `n` or budget.** [`READ_RULE.md`](READ_RULE.md) §0 carries the binding text.
>
> **3. What changed, exhaustively.** The run id; the band (§5, and the smoke leg's disjoint range);
> **the probe budget (§3.2, and it is the only experimental constant that moves)**; §4.1's dispersion
> table, which inherited a mislabeled row and is corrected here; and the `G-PROBE` justification text,
> because attempt 3's deliberate numerical collision does not exist at this budget. **§1, §2, §3.1's
> frozen-probe structure, §3.3, §3.4, §3.5, §4's statistic and its power arithmetic, §6.2's tenancy
> requirement, §7's twelve gates, §8, §9 and §10 are carried.** `READ_RULE.md` §1, §2, §3 (every gate
> and every bar), §4 (all five branches, their order and their constants), §5 and §6 are carried; its
> §0 change-list and the `G-PROBE` note are the only edits.
>
> **4. THE FOUR INSTRUMENT FIXES OF ATTEMPT 2, CARRIED VERBATIM THROUGH ATTEMPT 3** (each verified on
> real 400-game cells; this pair changes none of them):
>
> | # | gate it closed | the fix, still in this launcher |
> |---|---|---|
> | 1 | `G-RULES` | `run_cells.sh` **exports `CARCASSONNE_FIX_R9=1` at file scope** before any leg, and `assert_r9_env` REFUSES to run if it is unset or not truthy. R9 cannot live in the rules profile: `base_deck` derives farm data at IMPORT time and the Rust registry latches a `OnceLock` |
> | 2 | `G-LEAF` | the champion leaf is injected the way production play does it — **in-process via `--cand-leaf-json`** ([`champion_leaf_curve125.json`](champion_leaf_curve125.json)), never by exporting the curve env (which would move `DEFAULT_CONFIG` and therefore MOVE THE RUNG). `preflight_leaf` builds one champion through the harness's own module and asserts, before game 1, candidate `== a36d2e15a3b3d71d` **and** rung `== 42af12fce22e1a0f` |
> | 3 | `G-TOOL` (a) | `snapshot_rev` records `HEAD` + a code-path dirty fingerprint at start; `assert_rev_unmoved` re-checks before EACH cell; `require_clean_code` refuses a real cell on dirty CODE (`LAUNCH_DIRTY=1` + a mandatory logged reason is the only override) |
> | 4 | `G-TOOL` (b) | the harness's additive **`--stamp-key KEY=VALUE`** passthrough writes `BLIND_COMMIT` to **BOTH** addresses the read-rule searches: `manifest["BLIND_COMMIT"]` and `manifest["config"]["stamps"]["BLIND_COMMIT"]` |
>
> **4a. AND THE FOUR CONTRIBUTIONS OF ATTEMPT 3, ALSO CARRIED VERBATIM** — two of which have now been
> exercised on a real cell rather than only reasoned about:
>
> | contribution | status after attempt 3 |
> |---|---|
> | **the burn-in gate** (`READ_RULE.md` §3.2) — `G-TIMING` read live over the cell's own first 40 decks, at full production W, inside the adjudicated games | ⭐ **FIRED FOR REAL.** 80 of 800 games, ≈3.7 core-h against ≈44. The mechanism is no longer a projection |
> | **`G-TENANCY`** (§6.2) — a preflight census plus a live per-process CPU sampler that aborts the cell on two consecutive foreign-load samples | ⭐ **VALIDATED.** It measured attempt 3's window CLEAN, and that clean reading is the entire basis of §3.2 below. Attempts 1 and 2 had disclosure-after-the-fact, which is how a 1.8× contamination survived two attempts unnoticed |
> | **`G-PROBE`** — the candidate's own budget gated (`k_dets`, `sims_per_det`, `total_sims` and their identity) | carried unchanged; see §3.1's note on why its *justification* text changed while the gate did not |
> | **`G-TIMING-FULL`**, alias-aware **`G-SINGLEVAR`**, `G-N`'s `champ_timeouts == 0` | carried verbatim |
>
> **5. ⛔ THERE IS NO `--sims` RE-PICK ALLOWANCE IN THIS PAIR, ON ANY LEG.** The probe budget below is
> frozen by this commit. A burn-in FAIL stops the run and returns to the owner
> ([`READ_RULE.md`](READ_RULE.md) §3.2); it is not a knob. **Three attempts have now spent a band on a
> budget; none of them spent one on a re-pick, and this pair does not introduce the option.**
>
> **6. The two standing findings this pair is built on.**
> (i) *"R9's import-time farm derivation costs the PYTHON leaf ~58% per move"* (attempt 2; 553.8 →
> 877.2 ms/move on the frozen `HeuristicMCTS(h800, c=3.0)` rung, reproduced within 0.4% on a second
> box; the rust probe side moved only +7%). **Any equal-time pairing of a rust candidate against a
> Python rung must be priced against R9-era rung figures.**
> (ii) *"…and against SATURATED figures"* (attempt 2's void). **§3.2 adds the third and final clause:
> and against figures measured under ENFORCED EXCLUSIVE TENANCY** — because a ratio of two costs looks
> robust to a common scaling error and is not, and a co-tenant scales the two sides by different
> factors (1.8× python, 1.13× rust).

---

# RUNG COMPRESSION: IS THE REFERENCE LADDER'S SPACING A USABLE UNIT? — DESIGN (attempt 4)

Run id `track_d2r4_prep`. Pair: this file + [`READ_RULE.md`](READ_RULE.md). Launcher:
[`run_cells.sh`](run_cells.sh). Adjudicator: [`analyze_d2r4.py`](analyze_d2r4.py). Shared
primitives: [`d2r4_lib.py`](d2r4_lib.py). Band claim: [`BAND_CLAIM.json`](BAND_CLAIM.json).
Roadmap item **D2** ([`../../docs/PROGRAM_ROADMAP_2026-07-07.md`](../../docs/PROGRAM_ROADMAP_2026-07-07.md),
Track D).

---

## 0. AUTHORIZATION BLOCK

**NOT AUTHORIZED TO LAUNCH — but two of the five sign-offs are now GIVEN.** The owner authorized the
respin on **2026-08-26, verbatim *"respon d2"***, in reply to an orchestrator proposal that named
**both** the new candidate constant (`k4×1024 = 4096`) **and** a fresh band. That reply is recorded
here as pre-authorizing **(a) funding** and **(c) the candidate**. The remaining three are
ORCHESTRATOR-PROCEDURAL: they are things the orchestrator must *do and record*, not things the owner
must re-decide. **Nothing here launches, claims a band, or spends a core-hour until all five lines
below read GIVEN or DONE.**

| # | sign-off | state | why |
|---|---|---|---|
| (a) | **funding ≈27 core-h / ≈1.3 h wall** (§6) | ✅ **PRE-AUTHORIZED** by *"respon d2"* — and it is **≈38% cheaper than attempt 3's ≈44 core-h**, because the probe budget went DOWN | spend; the standing cost-discipline rule requires a one-sentence confirm, and it was given for this exact proposal |
| (b) | **the band claim** — `150000000000` (§5) | ⚙️ **ORCHESTRATOR-PROCEDURAL** — the all-branches sweep is re-run and the row appended in the stamping commit | `governance/BAND_REGISTRY.csv` is a source of truth the orchestrator edits, not a builder |
| (c) | **the probe budget** — `k4×1024 = 4096` (§3.2) | ✅ **PRE-AUTHORIZED** — the owner's reply answered a proposal that named this exact constant | it is deliberately **not** a named-lineage budget (§3.2 step 5); the owner agreed to the calibration-over-lineage framing when he approved the constant |
| (d) | **tie-arbiter OFF** | ⚙️ **ORCHESTRATOR-PROCEDURAL** — carried unchanged from all three prior attempts | the probe P is the pre-arbiter fair PIMC champion; running WITH the arbiter would confound rung spacing with the arbiter's own tied-ply behaviour |
| (e) | ⭐ **the EXCLUSIVE-TENANCY WINDOW** — a contiguous **≈1.6 h** with the local box as sole tenant (§6.2) | ⚙️ **ORCHESTRATOR-PROCEDURAL, AND THE ONE THAT ACTUALLY BINDS** | **it constrains the ORCHESTRATOR, not just the box.** No agent compute, no builds, no sibling cells, no test suites, no solver suites, for the whole window. This is the constraint whose violation cost attempts 2 AND 3 their bands — the second one without anybody noticing until after the fact |

⛔ **THE INTERLOCK IS UNCHANGED AND IS NOT A FORMALITY.** `BAND_CLAIMED` is **deliberately NOT created
at freeze**, and [`run_cells.sh`](run_cells.sh) refuses every real cell without it. Claiming the
registry row protects against a concurrent-session band race; it does **not** arm the launcher.

**Pre-launch checklist** (all must be true before any real cell fires):

- [ ] band claimed in [`../../governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv) (`150000000000`, per §5), **after re-running the all-branches sweep** — a main-tree-scoped check is what produced the `143e9` and `144e9` collisions
- [ ] this pair (`DESIGN.md` + `READ_RULE.md` + launcher + adjudicator + `d2r4_lib.py`) frozen and committed
- [ ] `BLIND_COMMIT` stamped (the launcher refuses to run a real cell on the placeholder)
- [ ] `analyze_d2r4.py --selftest` GREEN, **seeded from a real manifest** (§9)
- [ ] the §9 **smoke** leg has run, `n_failed == 0`, **and the adjudicator has been run against the smoke archive and failed only on the band/N family** (§9 — the launcher enforces this; a smoke that cannot be adjudicated is a launch blocker)
- [ ] process census clean on the local box, **and the exclusive window agreed** (§6.2)
- [ ] `RUN_LIVE.json` sentinel dropped for the duration (freeze-latch discipline)

---

## 1. THE QUESTION

**Roadmap line, quoted verbatim** ([`../../docs/PROGRAM_ROADMAP_2026-07-07.md`](../../docs/PROGRAM_ROADMAP_2026-07-07.md)):

> - **D2. Rung-compression cell** (audit #5): PUCT rung @equal-time-h800 vs h800/h1600 rungs,
>   shared decks, n=200 each (~2h) — are ladder *spacings* denominated in weak-search units? Fix
>   the c=1.5-rungs vs c=3.0-champion inconsistency in the same pass.

Every strength number this program quotes against the heuristic ladder is denominated in ONE
unit — the gap between adjacent h-rungs. If that unit is small and shrinking, elo distances
measured on the ladder compress, and the ladder stops being a ruler.

The program has **two prior measurements of the h800→h1600 spacing and they disagree by 2.8×**:

| source | contrast | n | band | result |
|---|---|---|---|---|
| [`../level2/LEVEL2_LADDER_VERDICT.md`](../level2/LEVEL2_LADDER_VERDICT.md) (CL-023, 2026-06-18) | heur_v2_7@1600 vs @800 | 400, paired | fresh, 3.0e9+ | **+55.2 ±17.6 elo, paired z 3.23** |
| [`../../experiments/results.csv`](../../experiments/results.csv) row `l22_ctrl_heur1600_vs_heur800_b310_n400` (2026-06-19) | heur@1600 vs heur@800 | 400, paired | 3.10e9 | **+20.0 elo, sigma 17.4, z 3.285** |

The full CL-023 ladder reads **@200→@800 +75.9 (z3.59) · @800→@1600 +55.2 (z3.23) ·
@1600→@3200 +34.9 (z2.36)** — a shrinking-per-doubling pattern that is the house prior
([`READ_RULE.md`](READ_RULE.md) §6 names it, before game 1).

Same contrast, same n, different bands, 2.8× apart — consistent in *direction* with CL-068's
measured 1.8–2.2× cross-band over-dispersion, but **UNRESOLVED**: the two readings were never
compared within one band, deck-paired, at a fixed knob set. Per the results-discipline rule
(`CLAUDE.md`: *"a new result that contradicts a prior one is not a discovery until the contradiction
is resolved"*), this is an open contradiction. **D2 resolves it on a fresh band with a fixed probe,
on the rung the ruler of record actually uses.**

---

## 2. THE c=1.5 / c=3.0 INCONSISTENCY — ALREADY RESOLVED, AT ZERO GAMES

The roadmap line asks D2 to *"fix the c=1.5-rungs vs c=3.0-champion inconsistency in the same
pass."* **There is no configuration inconsistency to fix.** The full evidence chain — the module
default (`DEFAULT_C = 3.0`, `src/carcassonne_ai/mcts.py:36`), its complete commit history (it has
never read 1.5), and an enumeration of every `HeuristicMCTS(` construction site that feeds the
ladder — is in [`../track_d2r2_prep/DESIGN.md`](../track_d2r2_prep/DESIGN.md) §2 and is not
re-derived here (house rule: point, don't copy). It concludes: **every heuristic rung this program
has ever run was already at UCT c = 3.0.**

The "1.5" claim is a **documentation defect** in two places — the `LEVEL2_LADDER_VERDICT.md` config
note, and the `old_c=1.5` stamp on the rung side of five F5 `fair_ruler_*` rows in `results.csv`
whose own manifests record `config.rung.c = 3.0`. Correcting both is an owner decision, independent
of this cell in either direction ([`READ_RULE.md`](READ_RULE.md) §5), and costs zero games.

⇒ **D2 carries NO exploration-constant arm and needs NO harness change.**

---

## 3. THE TWO CELLS

Both cells run [`../../scripts/classical_search/eval_fair_puct.py`](../../scripts/classical_search/eval_fair_puct.py)
and differ in **exactly one experimental argument: `--rung-sims`**.

| | **CELL R800** | **CELL R1600** |
|---|---|---|
| cell id | `d2r4_rung800` | `d2r4_rung1600` |
| rung | `HeuristicMCTS(h800, c=3.0)` | `HeuristicMCTS(h1600, c=3.0)` |
| `--rung-sims` | `800` | `1600` |
| probe P | frozen, identical (§3.1) | frozen, identical (§3.1) |
| n | 200 decks × 2 seatings = 400 games | 200 decks × 2 seatings = 400 games |
| order | **runs FIRST** — it carries `G-TIMING` and is the shorter cell | runs only after R800 completes AND the burn-in passed |

### 3.1 Probe P — frozen, identical in both cells

```
--info fair --opponent h800 --backend rust --k-dets 4 --sims 1024 --exact-k 2
--c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits
--rules-profile fixed_v1
```

k4×1024 = **4096 total sims**, tie-arbiter **OFF** (no `--cand-tiearb-*` flags at all — §0(d)).

✅ **ATTEMPT 3's NUMERIC COLLISION IS GONE — AND `G-PROBE` STAYS ANYWAY.** Attempt 3's candidate ran
`--sims 1600`, the same integer as CELL R1600's `--rung-sims 1600` on a completely different axis,
and that pair spent a paragraph and a gate making the clash checkable. At `--sims 1024` there is no
clash: the candidate's number is **per-determinization sims** (`config.champion.sims_per_det`, ×4
determinizations = 4096 total) and cannot be confused with the rung's **total plain-UCT sims**
(`config.rung.sims` = 800 or 1600). This is a **side-effect** of the recalibration, not a reason for
it — recorded so a reader diffing the two pairs cannot mistake a removed paragraph for a removed
check.

⛔ **`G-PROBE` IS RETAINED, UNCHANGED, AND IT WAS NEVER REALLY A COLLISION GATE.**
[`READ_RULE.md`](READ_RULE.md) §3 asserts, in **both** cells, the candidate's
`(k_dets, sims_per_det, total_sims) == (4, 1024, 4096)`, plus `c_puct == 1.5`, `exact_k == 2`,
backend `rust`, and the tie-arbiter absent or disarmed — **and it checks the identity
`k_dets × sims_per_det == total_sims` rather than assuming it.** The gap it closes is that **no pair
before attempt 3 gated the probe's own budget at all**: attempt 2's readout records *"No §3 gate
covers the probe's own `--sims`; recorded as context."* That is the merit it stands on, and it is a
stronger one now that the probe budget is the single experimental constant this attempt moves.

### 3.2 ⭐ WHY THIS BUDGET — the re-derivation against the FIRST CLEAN calibration this program has had

**This section is the whole of attempt 4.** Attempt 3 got the METHOD right and the INPUTS wrong.

**Step 0 — what attempt 3 did, and why it was defensible.** Attempt 2 died because its budget was
priced against a 16-game pilot at unsaturated W. Attempt 3 fixed that: it priced `k4×1600 = 6400`
against attempt 2's **cell-realized, 400-game, W=22-saturated** costs — rung `1103.1 ms/move`, probe
`924.7 ms/move` at 5504 total sims ⇒ `0.168 ms` per total-sim — and projected an equal-time ratio of
`0.975` (linear) to `1.014` (superlinear). In bar under both models, with ≥12.8% margin. **It
realized `1.5491`.**

**Step 1 — the root cause, resolved the same morning and transcript-verified.** ⛔ **Attempt 2's cell
costs were CO-TENANT-INFLATED.** The reconcile exact-solver suite ran a **silent ~100%-CPU job
through d2r2's entire cell window**, invisible to that era's census (a silent job plus a
comm-truncated `ps`). The disclosed Android build was only the minor final-ten-minutes contaminant.

```
rung  (python, DRAM-latency-bound)  1103.1 ms/move  ->  601.19 clean   =  x1.83 inflated
probe (rust)                         924.7 ms/move  @5504            ~=  x1.13 inflated
```

**The ASYMMETRY is what flagged the diagnosis** — and it is the same asymmetry §3.2's general trap
warns about, arriving from the other direction. Zero code changes to `src/` / `engine/` / `rust/` /
the harness between the two revs (`d3c720cf..65589b8e`); env and config byte-identical per manifests.
The record is [`../../experiments/results.csv`](../../experiments/results.csv) row
`d2r3_rung_compression_U_UNREADABLE_burnin_abort_n80_b149e9` and
[`../../DECISIONS.md`](../../DECISIONS.md) **"2026-08-26 (midday)"**.

⭐ **`G-TENANCY` IS THEREFORE VALIDATED, TWICE OVER.** It is new in attempt 3, and it did two things:
it certified attempt 3's own window CLEAN, and — by producing a *clean* rung figure — it is what made
attempt 2's number visibly wrong. A disclosure-after-the-fact census, which is all attempts 1 and 2
had, let a 1.83× contamination survive two attempts and cost two bands.

**Step 2 — THE CLEAN BASIS. The first tenancy-enforced saturated measurement any attempt has had.**
`/mnt/c/carc-shared/track_d2r3_prep/BURNIN_R800.json`
— 40 decks × 2 seatings = **80 games**, W=22, **exclusive box**, `n_malformed = 0`, `n_missing = 0`,
`complete = true`:

```
rung   HeuristicMCTS(h800, c=3.0), python, R9      =  601.19 ms/move   (5,676 rung moves)
probe  rust fair PIMC, k4x1600 = 6400 total sims   =  931.30 ms/move   (5,520 candidate moves)
                                                   =>  0.14552 ms per total-sim
```

This window is statistically ample for a COST reading: 11,196 timed moves. What it measures is the
**load regime**, which is exactly the quantity in question.

**Step 3 — two cost models, and NOTE WHAT IS NOT FITTED.**

- **(M1) LINEAR through the origin.** `ms(N) = 0.14552 × N`.
  ```
  probe(4096) = 4096 x 0.14552 = 596.03 ms/move
  ratio       = 596.03 / 601.19 = 0.9914
  ```
- **(M2) FIXED-OVERHEAD-BOUNDED.** Write the probe as `F + c×N` and fit through the same one clean
  point (`F + 6400c = 931.30`, so `c = (931.30 − F)/6400`). Substituting:
  ```
  probe(4096) = F + 4096c = 0.64 x 931.30 + 0.36 x F = 596.03 + 0.36 F
  ```
  ⭐ **This is INCREASING in `F`, and equals M1 exactly at `F = 0`.** So M1 is the FLOOR of this
  family, the **ceiling is the only rail a fixed overhead can push us through**, and it is reached
  only at
  ```
  596.03 + 0.36 F >= 1.20 x 601.19 = 721.43   =>   F >= 348.3 ms/move   (equivalently c <= 0.09109)
  ```
  i.e. **`F` would have to be 37% of the probe's entire cost at 6400, as pure per-move fixed
  overhead**, for `k4×1024` to breach `1.20`. That is implausible for a rust PIMC search whose cost is
  dominated by playouts — and note the *shape* of the bound: the two models cannot straddle the bar,
  because one is a special case of the other.

⛔ **ATTEMPT 3 FITTED A SUPERLINEAR EXPONENT (1.262) AND THIS PAIR DELIBERATELY DOES NOT.** That
exponent came from two co-tenant-era scaling points. There is exactly **one** clean scaling point in
existence, and the only honest model through one point is a line through the origin plus a bound on
what a second parameter could do. Re-using a contaminated slope to manufacture a second model would
be the *appearance* of the two-model discipline without its substance.

**Step 4 — the pick, and its margins to BOTH rails.** `k4×1024 = 4096 total`:

| model | projected ratio at 4096 | what it would take to leave `[0.85, 1.20]` |
|---|---|---|
| **(M1) linear** | **0.9914** | — |
| **(M2) fixed-overhead-bounded** | ≥ 0.9914, and `= 0.9914` at `F = 0` | `F ≥ 348.3 ms/move` (37% fixed overhead) to breach the ceiling |

Stated on the rung side, which is where the surprise came from last time:

```
to breach the 1.20 CEILING: the rung must run >=17.4% FASTER than the clean 601.19  (<= 496.7 ms/move)
to breach the 0.85 FLOOR:   the rung must run >=16.6% SLOWER                        (>= 701.2 ms/move)
```

⭐ **This is the first D2 candidate to sit near the CENTRE of the bar rather than near a rail.**
Attempt 2 projected `0.975`/`1.014` and realized `0.8382` — 1.4% outside. Attempt 3 projected the
same pair of numbers off contaminated inputs and realized `1.5491` — 29% outside. `0.9914` is 0.9%
from dead centre, and it takes a **±17% move in the realized rung cost** in either direction to leave
the bar.

**Step 5 — the named-lineage preference stays REVERSED, and that is why the owner was asked.** Both
attempt-1 and attempt-2 pairs preferred a *named production-lineage* budget (`k4×688 = 2752`,
`k4×1376 = 5504`) over an assembled one. Attempt 3 reversed that and this pair keeps the reversal:
the named ladder is a doubling sequence — 2752, 5504, 11008 — and the equal-time target (≈4,132 total
sims under M1) again falls in a gap where no named budget exists. **When the estimand's denominator
is equal wall-clock, the budget is a CALIBRATION, not a config claim.** `1024` is chosen over the
exact optimum `1033` because it is a power of two and a 0.9% difference is far inside the ±3.3%
cell-to-cell cost spread — nothing is being tuned. The owner approved this constant by name
(§0(c)). **The consequence for interpretation, stated up front: this cell's probe is NOT a config the
program has run before**, so §3.4's non-poolability caveat binds, and §8 item 2 restates it.

**Step 6 — and the burn-in gate is what makes any residual error cheap.** Every figure above is an
extrapolation from **one** window, on one box, on one day — a better window than any attempt has had,
and still one window. **The design does not rely on being right.**
[`READ_RULE.md`](READ_RULE.md) §3.2 verifies the realized ratio on this cell's own first 40 decks, at
full production W, inside the adjudicated games, and aborts if it is out of bar. At attempt 4's
cheaper probe that abort costs **≈2.2 core-h / ≈6 min wall — about 8% of the pair** (§6). **The
calibration is a best estimate; the burn-in is the guarantee.** It is also no longer a promise: it
fired on attempt 3, exactly as specified, and that is why attempt 3 cost 3.7 core-h instead of 44.

### 3.2a ⭐ THE BURN-IN MECHANISM IS NO LONGER VALIDATED RETROSPECTIVELY — IT HAS FIRED

Attempt 3's DESIGN could only argue this section by replaying its gate over attempt 2's completed
archive. **Attempt 4 does not have to argue it.** The gate ran live, on a real cell, and did exactly
what it was specified to do:

| | attempt 3's *prediction* for the mechanism | what actually happened |
|---|---|---|
| when the window completed | ~81 of 400 games — 18.5% of CELL R800's wall, ~7.9 min in | **80 of 800 games, ≈7.7 min wall** |
| what it cost | ≈3.6 core-h | **≈3.7 core-h** |
| what a full void would have cost | ≈44 core-h | ≈44 core-h |
| did it read the cell's own regime, not a different one | claimed | **yes — window `complete`, 0 malformed, 0 missing, and the reading is the basis of §3.2** |

Three things follow, and they are why attempt 4 is a cheap bet rather than a fourth roll of a die:

1. **The gate is real.** It is the only D2 mechanism that has ever been exercised end-to-end on a
   live cell and behaved to spec.
2. **A wrong budget is now a ≈2.2 core-h event**, not a band-and-a-day event. That changes what
   "residual calibration risk" is worth worrying about — and it is why §3.2 can honestly say the
   design does not rely on being right.
3. **The clean window it produced is worth more than the band it spent.** Attempt 3's void bought the
   program its first uncontaminated saturated cost figures for BOTH sides of a rust-vs-python
   equal-time pairing. Any future equal-time cell anywhere in this program calibrates against them.

⚠️ **What this does NOT show.** One window, one box, one day, one budget. It demonstrates that the
burn-in window tracks its own cell's regime and that the abort path works; it does not promise that
`k4×1024` lands in bar. **That is what the gate is for.**

### 3.3 ⚠️ DEVIATION, NAMED: "equal-time" is a deployable-value statement, not an algorithmic one

"Equal-time" means equal wall-clock **in the deployed implementations** — a rust candidate against
a rung that is frozen Python by design. `eval_fair_puct.py`'s own manifest note records that *"the
h800 / greedy / bare-net rungs are FROZEN RULERS and stay Python by design."* The probe therefore
compares a rust PUCT search to a Python plain-UCT search at matched wall-clock, **not** matched node
count or matched algorithm-internal cost. **It is a DEPLOYABLE-VALUE statement — "at the wall-clock
this program actually pays for the deployed candidate, how far ahead of h800 is it?" — NOT an
algorithmic claim.**

⚠️ **Field-name trap, inherited from the jcz precedent:** in `eval_fair_puct`,
`champ_prefix_ms_per_move` is the **CANDIDATE** side — the opposite convention from
`eval_puct_priors`. Any read-out that swaps them inverts the timing reading. This pair takes the
quantity from ONE implementation ([`d2r4_lib.timing_ratio`](d2r4_lib.py)), used by both the live
watcher and the adjudicator, so the trap can be got wrong at most once.

### 3.4 ⚠️ NOT POOLABLE WITH THE F5 LADDER — nor with any earlier D2 attempt

The F5 `fair_ruler_*` rows ran on the **python** backend under **pre-`fixed_v1`** rules. D2 runs
`fixed_v1` + R9 + rust on the probe side. **D2's ABSOLUTE numbers are not comparable to
`fair_ruler_rebase_*`'s; only D2's internal cell-vs-cell contrast (§4) is claimed.**

Carried and strengthened for attempt 4: the probe budget `k4×1024` has **no prior cell at all**
(§3.2 step 5), and attempts 1, 2 and 3 are **all** `U-UNREADABLE` — attempt 3 so thoroughly that it
never produced a statistic at all. So **nothing about this cell's absolutes may be compared to any
earlier D2 attempt either.** The only claim is the within-band, deck-paired, cell-vs-cell contrast.

### 3.5 THE DRIFT ENVELOPE — why `G-TIMING-FULL` is `[0.75, 1.35]`

`G-TIMING` binds on the burn-in window (the first 40 decks) because that is the only window whose
load regime is both *verified* and *enforced*. But a cell could pass its burn-in and then have its
regime collapse — a co-tenant, a thermal throttle, a swap event. `G-TIMING-FULL` is the backstop,
read over the whole cell, and its width is derived rather than picked:

- **within-saturated-regime variation, measured:** the same probe config read 924.7 vs 894.4
  ms/move across attempt 2's two cells — **3.3%**;
- **the regime CHANGE that voided attempt 2, measured:** the ratio moved **11.1%** (0.9428 → 0.8382)
  going from unsaturated to saturated.

`[0.75, 1.35]` widens `[0.85, 1.20]` by **11.8% below and 12.5% above**. That is: **wider than the
largest regime change the program has ever measured within this instrument (11.1%), so it will not
void on drift; and far narrower than a genuine collapse**, which a heavy co-tenant or a throttled
box would push well past 25%. It is a *drift tolerance around an enforced window*, explicitly not a
second, laxer attempt at equal time — and it is stated here, before game 1, so that a reader cannot
later mistake it for one.

⚠️ **AN HONEST ANNOTATION ON THE TWO INPUTS ABOVE, CARRIED WITHOUT MOVING THE ENVELOPE.** Both
bullets are attempt-2-era figures, and attempt 2's era is now known to have been co-tenanted. The
3.3% cell-to-cell spread is a *within-era* comparison and survives that (both cells sat in the same
contaminated regime); the 11.1% figure is the *pilot-vs-cell* move and is likewise a real, measured
regime change. **What the co-tenancy diagnosis adds is a much larger data point in the same
direction: a foreign 100%-CPU tenant moved the python rung 1.83×.** That is far outside `[0.75,
1.35]` — which is the correct behaviour, because a confirmed co-tenant is exactly what `G-TENANCY`
aborts on rather than what `G-TIMING-FULL` tolerates. The two gates partition the failure space:
**drift is tolerated up to 12%, contamination is aborted on.** The envelope does not move.

---

## 4. THE PRIMARY STATISTIC AND ITS POWER — arithmetic BEFORE any number

**PRIMARY = the deck-paired spacing**

```
S = M_R800 − M_R1600
```

where `M_cell` is that cell's deck-paired mean margin (points/game, probe-minus-rung) computed over
the `n_common` decks present in BOTH cells. **Elo is SECONDARY**, reported for continuity with
CL-023, converted via the realized scale (§4.3).

### 4.1 The dispersion we are entitled to assume — ⚠️ CORRECTED, an inherited mislabel

At n=200 decks the F5 cells realized `paired_mean_margin / paired_z` ⇒ `se(M)`:

```
fair_ruler_rebase_2752    8.6425 / 9.5101  = 0.909 pts
fair_ruler_rebase_5504   10.7825 / 11.3029 = 0.954 pts
fair_ruler_k8x1376_11008  9.765  / 9.866   = 0.990 pts     <- CORRECTED
```

Take **se(M) ≈ 0.95 pts at n_paired = 200**.

⛔ **THE CORRECTION, NAMED SO IT CANNOT PROPAGATE A FOURTH TIME.** Attempt 3's DESIGN §4.1 carried
`7.9350 / 8.4547 = 0.939` on the third line under the label `fair_ruler_k8x1376_11008`. **That row is
mislabeled.** `7.935 / 8.4547` are `fair_ruler_rebase_11008`'s realized figures (the k4×2752 cell);
`fair_ruler_k8x1376_11008`'s own are **`9.765 / 9.866`**. The defect was inherited from
`track_d1_fair_rebase`'s DESIGN §4.1 and is reconciled against the cells' own `summary.json` files in
[`../track_d1_fair_rebase/READOUT.md`](../track_d1_fair_rebase/READOUT.md) **"ADDENDUM 2026-08-26"**,
which is the source of record. The corrected three-row average moves `se(M)` from **≈0.93 → ≈0.95
pts** — a 2.2% widening, entirely inside the precision this design uses it at. §4.2 and §4.3 below
carry the consequence explicitly rather than quietly.

### 4.2 CRN and se(S)

CRN (common decks, same seatings) is used across the two cells, but per CL-068 the measured
cross-cell CRN benefit was only ~9.9% of contrast variance in the comparable case. Assume
**ρ ≈ 0.10** — do not bank more than that:

```
se(S) = 0.93 × sqrt(2 × (1 − 0.10)) = 1.25 pts     [THE COMMITTED EXPECTATION -- FROZEN]
se(S) = 0.95 × sqrt(2 × (1 − 0.10)) = 1.27 pts     [the same model on §4.1's CORRECTED se(M)]
```

⛔ **THE COMMITTED CONSTANT DOES NOT MOVE.** `se(S) = 1.25 pts` is a **frozen constant of the branch
structure** — it is what `READ_RULE.md` §4's `D2-COMPRESSED` reachability note is written against, and
a pair that quietly re-tunes its own branch constants after finding a 2% correction is a pair that
can re-tune them again. The corrected model figure `1.27` is reported alongside it everywhere it
matters (§4.3), so a reader never has to guess which is operative, and the readout prints both.

### 4.2a ⭐ THE COMMITTED DISPERSION IS NOW A MEASUREMENT, NOT A MODEL

Attempts 1 and 2 had to *assume* §4.2's figure. **Attempt 2 realized it.** On exactly this design
shape — `n_common = 200`, the same two rungs, the same CRN scheme, a probe of the same class, one
band — the realized paired dispersion was **`se(S) = 1.2825 pts`**, **2.6% above** the committed
1.25. (This is a DISPERSION, not a spacing or a strength; see [`READ_RULE.md`](READ_RULE.md) §0's
blindness disclosure for why it is the one class of attempt-2 quantity this pair is entitled to
use.)

Consequences, all of them conservative:

- **the committed `se(S) = 1.25 pts` is carried UNCHANGED** into `READ_RULE.md` §4 and §4.3 — it is
  a frozen constant of the branch structure and this pair does not move it;
- the **power table below is quoted at ALL THREE** dispersions — 1.25 (committed), 1.27 (§4.2's
  corrected model) and 1.2825 (attempt-2-realized) — so no reader has to guess which is operative;
- the `D2-COMPRESSED` reachability condition is **unaffected**: it depends on the branch constant
  `S < 2.5 pts` against `z_S ≥ 2.0`, i.e. on `se_realized < 1.25`, not on what the design expected.
  Attempt 2's realized 1.2825 means that on a run of this shape **`D2-COMPRESSED` is a narrow
  branch**, and `READ_RULE.md` §4's boundary note — which says exactly this, verbatim, and predates
  all four attempts — is now backed by data rather than arithmetic alone.

⚠️ **AND NOTE WHAT ATTEMPT 3 DID NOT ADD HERE.** Attempt 3 aborted at its burn-in and produced **no**
dispersion of its own — no `se(S)`, no `S`, nothing. The realized figure above is still attempt 2's
and is still the only one that exists. A dispersion is a COST-class quantity under
[`READ_RULE.md`](READ_RULE.md) §0 item 3 and is used here for a power table, never in a bar.

### 4.3 What n=200 buys

```
2σ MDE(S) = 2 × 1.25   = 2.50 pts     [committed dispersion -- the frozen branch constant]
2σ MDE(S) = 2 × 1.27   = 2.55 pts     [§4.2 model on §4.1's CORRECTED se(M) = 0.95]
2σ MDE(S) = 2 × 1.2825 = 2.57 pts     [attempt-2-realized dispersion]
```

Converting with the F5 scale (`fair_ruler_rebase_2752`: +135.0 elo ↔ +8.6425 pts ⇒ **~15.6
elo/pt**) that is **≈39.0 / 39.8 / 40.0 elo**; at attempt 2's own realized CELL R800 scale (13.304
elo/pt) it is **≈33.3 / 33.9 / 34.1 elo**. So the honest statement of this design's resolution is
**an MDE band of ≈33–40 elo**, and it is *unchanged at that precision* by §4.1's correction — the
correction moves the band by ≈0.8 elo. All three are reported in the readout
([`READ_RULE.md`](READ_RULE.md) §4.3 item 5).

| the prior reading | in points | z at n=200 (se 1.27) | resolves? |
|---|---|---|---|
| CL-023's +55.2 elo | ≈3.5 pts | ≈2.75 | **YES** — above 2σ |
| results.csv's +20.0 elo | ≈1.3 pts | ≈1.0 | **NO** — inside the 2σ MDE |

**State this bluntly: at the roadmap's n=200 the cell is a SCREEN FOR CL-023's +55.2, NOT AN
ADJUDICATOR OF THE +20.0 READING. It can confirm the large prior; it cannot discriminate the small
prior from zero. A null read at n=200 is therefore NOT evidence that the spacing is zero — it is only
a bound of ≈33–40 elo.** `READ_RULE.md` §4 names a branch (`D2-BOUNDED-NULL`) for exactly this
outcome so it cannot be narrated as a refutation after the fact. **This framing is carried verbatim
from attempt 3 and predates every number in this pair.**

### 4.4 The n that would resolve the small reading — recorded now, funded by nobody

```
n=400 decks/cell:  se(S) = 0.90 pts  ⇒  2σ MDE = 1.80 pts ≈ 28 elo   (the +20 reading still only z≈1.4)
n=800 decks/cell:  se(S) = 0.64 pts  ⇒  2σ MDE = 1.27 pts ≈ 20 elo
```

(Both recomputed on §4.1's corrected `se(M) = 0.95`; attempt 3 quoted 0.88 / 0.62 off the mislabeled
0.93.) Fully separating +55 from +20 needs **n ≈ 800 decks/cell ≈ 110 core-h** (4× §6 — and note
that is ≈60 core-h *less* than the same extension would have cost at attempt 3's probe budget).
**Honest framing:
this design is a SCREEN for the large reading, not an adjudication between the two priors.**
Whether to fund an extension is a fresh owner decision, priced here so a future "just add n" ask
does not have to re-derive it.

⚠️ **One thing the burn-in changes about that menu — and it is now a MEASURED claim.** The dominant
risk of a bigger `n` used to be that a whole expensive pair could void on a timing precondition
discovered at the end. With [`READ_RULE.md`](READ_RULE.md) §3.2 in place a cost-calibration void costs
**≈2.2 core-h regardless of `n`** — attempt 3 paid exactly this price, at ≈3.7 core-h on its more
expensive probe — which makes an n=400 extension materially less risky than it was for attempts 1
and 2. That is
an *observation for the owner's funding decision*, **not a request** — no branch of this pair
licenses an extension ([`READ_RULE.md`](READ_RULE.md) §5).

---

## 5. THE BAND

**Band `150000000000`.** Seeds `150000000000 .. 150000000199` (200 decks), used by **BOTH** cells
(CRN by design — the same deck set, same seatings, feeding §4's paired statistic). The burn-in
window ([`READ_RULE.md`](READ_RULE.md) §3.2) is the first 40 of those decks,
`150000000000 .. 150000000039`; it is part of the cell, not a separate allocation.

⛔ **NOT CLAIMED at freeze-draft time.** The row is in [`BAND_CLAIM.json`](BAND_CLAIM.json) and is
appended to the registry by the orchestrator in the stamping commit, before launch.

**Picked by the ALL-BRANCHES SWEEP, which is the procedure of record** — established by
[`../carcasum_arb_challenge_prep/DESIGN.md`](../carcasum_arb_challenge_prep/DESIGN.md) §4.1 after a
main-tree-scoped registry check missed `144000000000` sitting on an unmerged sibling branch and
double-claimed it. The corrected procedure, re-run for this pair: for **every** ref in
`refs/heads` and `refs/remotes`, read that ref's own `governance/BAND_REGISTRY.csv` **and** every
`measurement/**/BAND_CLAIM*.json` it carries, then take the lowest integer clear of everything
found anywhere. Result:

Re-run 2026-08-26 over **135 refs / 563 registry-and-claim files**. Result:

| band | status found | source |
|---|---|---|
| `143000000000` | claimed | `carcasum_rung2_prep` |
| `144000000000` | **retired** (attempt 2's spent void) | `track_d2r2_prep` |
| `145000000000` | claimed | `track_d1_fair_rebase` (PRIMARY) |
| `146000000000` | **soft-reserved, no registry row on any ref** | `track_d1_fair_rebase` — earmarked for its own n=800 extension |
| `147000000000` | claimed | `carcasum_arb_challenge_prep` |
| `148000000000` (+ top-up to `148000000699`) | claimed | `h2h_22016_prep` — the highest *live* allocation on any ref |
| `149000000000` | ⛔ **RETIRED** — attempt 3's spent void; ~40 decks of real records exist on it | `track_d2r3_prep` |
| **`150000000000`** | **free everywhere** | no ref, no registry version, no claim file mentions it |

`146000000000` is skipped on the same reasoning `carcasum_arb_challenge_prep`, `h2h_22016_prep` and
attempt 3 all used: by the letter it is unclaimed, but a sibling track has spent a committed
paragraph earmarking it for its own n=800 extension and asked that nothing run there without a fresh
funding decision. Taking it for an unrelated cell would manufacture the exact collision the corrected
procedure exists to prevent, the moment that extension is funded.

⚠️ **`149000000000` IS NOT REUSABLE, AND THIS IS WHY THE SWEEP MATTERS EVEN WHEN A BAND "FAILED".**
Attempt 3 aborted at 80 games — a fifth of one cell — and a reader could reasonably think the band is
barely touched. It is **spent**: the `RELEASE-IF-NEVER-LAUNCHED` clause releases a band only when
**no real records exist**, and ~40 decks of them do. A band with records on it can never again be a
clean draw for the same contrast.

Per CL-068, **band identity is load-bearing**: never pool D2's numbers across bands, and this band
**retires from confirmatory use** once it has influenced any decision.

⚠️ **The RELEASE-IF-NEVER-LAUNCHED clause does NOT apply to a burn-in abort.** If the burn-in gate
fires, ~40 decks of real records exist on `150000000000` and the band is **spent and retired**
([`READ_RULE.md`](READ_RULE.md) §3.2). The band is released only if the cell never runs at all.

---

## 6. COST

⛔ **THIS SECTION IS REBUILT ON CLEAN NUMBERS. EVERY PRIOR D2 COST SECTION WAS DERIVED FROM A
CO-TENANTED ERA.** Attempts 2 and 3 both priced themselves off attempt 2's realized per-cell figures,
which are now known to be ~1.83× inflated on the rung side. The arithmetic below is derived
end-to-end from attempt 3's **tenancy-enforced clean burn-in** (§3.2 step 2), which is the only
uncontaminated per-move cost measurement this program has.

**The inputs, all measured, none modelled:**

```
rung  h800, python, R9, W=22, exclusive   =  601.19 ms/move   (5,676 moves over 80 games => 70.95/game)
probe rust, k4x1600 = 6400 total          =  931.30 ms/move   (5,520 moves over 80 games => 69.00/game)
probe rust, k4x1024 = 4096 total          =  596.03 ms/move   (§3.2 M1: 4096 x 0.14552)
realized wall for those 80 games at W=22  =  ~7.7 min  =>  W-utilisation ~84%
```

**Per game, at attempt 4's budget:**

```
CELL R800   rung 70.95 x 0.60119 = 42.65 s  +  probe 69.00 x 0.59603 = 41.13 s  =   83.8 s/game
CELL R1600  rung ~2x h800 => ~85.3 s        +  probe                   41.13 s  =  126.4 s/game
```

| | attempt 3 PROJECTED (probe @6400) | **attempt 4 PROJECTED (probe @4096)** |
|---|---|---|
| CELL R800 | ≈48 min wall · ≈17.7 core-h | **≈30 min wall · ≈11.1 core-h** |
| CELL R1600 | ≈72 min wall · ≈26.2 core-h | **≈46 min wall · ≈16.7 core-h** |
| **TOTAL** | **≈2.0 h wall · ≈43.9 core-h** | **≈1.3 h wall · ≈27.8 core-h** |

Plus the §9 smoke leg (n=16): **≤5 min**. `CELL R1600` remains **rung-dominated** — the rust probe
does not shrink the Python rung (§3.3) — which is why the deeper-rung cell is the more expensive one,
and why attempt 4's saving lands mostly on R800.

⚠️ **THE RESIDUAL UNCERTAINTY, NAMED.** Two places this can be wrong, both bounded: (i) `h1600 ≈ 2 ×
h800` is an assumption, not a measurement — if the rung is sublinear in sims the pair comes in nearer
**≈26 core-h**, if superlinear nearer **≈30**; (ii) the 84% W-utilisation figure is one window's. The
band **≈26–30 core-h** is what the funding line in §0(a) should be read as, and it is well under
attempt 3's ≈44 either way.

**The burn-in abort cost — no longer modelled, PAID.** ([`READ_RULE.md`](READ_RULE.md) §3.2.) The
watcher waits until all 80 burn-in games have records. Attempt 3 reached that moment at **80 of 800
games in ≈7.7 min wall, ≈3.7 core-h**. At attempt 4's cheaper probe the same window costs
```
80 games x 83.8 s / 0.84 utilisation = ~7,960 core-s  =  ~2.2 core-h  /  ~6 min wall
                                                      =  ~8% of the pair's ~27.8 core-h
```
That number is the whole argument for the burn-in: **it converts a cost-calibration void from a
28-core-h loss into a 2.2-core-h one** — and unlike every earlier statement of this claim, the
mechanism has now been observed doing it.

### 6.2 ⭐ THE EXCLUSIVE-TENANCY WINDOW — a funding requirement, not a courtesy

**This cell is a timing-gated instrument. It is an EXCLUSIVE TENANT of the local box for its whole
window.** House rule `feedback_no_agent_compute_beside_eval`: *nice + thread-caps are NOT
coexistence on this DRAM-bound box*, and a TIMING bench is an exclusive tenant.

⛔ **THE PRECEDENT IS NO LONGER A DISCLOSURE — IT IS THE ROOT CAUSE OF TWO VOIDS.** Attempt 2's
readout disclosed an Android cross-compile + gradle build on the box for CELL R800's final ~10
minutes, effect *"real in magnitude and undetermined in direction."* **That was the small half.** The
2026-08-26 analysis established that the reconcile exact-solver suite held ~100% CPU across d2r2's
**entire** cell window, invisible to that era's census, and inflated the python rung **1.83×**. That
contaminated number then became attempt 3's calibration basis and cost attempt 3 its band too.
**One undetected co-tenant voided two attempts and two bands.** This is the single most expensive
failure mode in D2's history, and it is the reason §0(e) is the sign-off that actually binds.

**What is required, concretely:**

- a **contiguous ≈1.6 h window** (≈1.3 h of games + smoke + pre-flights + adjudication) with the
  local 5900XT box as **sole tenant**;
- for that whole window: **no agent compute, no builds (APK/cargo/gradle/Cython), no test suites,
  no sibling measurement cells, no other `--shared-claim` runs, and — named explicitly because it is
  the one that did the damage — no `reconcile_exact_solver.py` or any other solver suite** —
  including work started by the orchestrating session itself, which is what happened both times;
- the laptop and any other box are unaffected and may run whatever they like — **the constraint is
  on the box the cell is timing.**

**It is enforced in two places, because a preflight alone is provably insufficient** — attempt 2's
disclosed co-tenant **started after the cell did**, and its undisclosed one was **already running and
still invisible to a `ps`-based census**:

1. `run_cells.sh` **refuses to start** on a non-exclusive box (foreign `RUN_LIVE.json` sentinels,
   sibling-run processes, or foreign CPU at or above one core), overridable only by
   `ALLOW_COTENANT=1` with a mandatory logged reason;
2. a **sampler runs for the cell's whole life**, taking instantaneous per-process CPU readings, and
   **aborts the cell** on two consecutive over-bar samples — the same cheap-abort path as a burn-in
   fail. `G-TENANCY` ([`READ_RULE.md`](READ_RULE.md) §3) then adjudicates the log.

⭐ **AND IT WORKS.** This machinery ran for the first time on attempt 3 and certified that window
clean — which is exactly why attempt 3's ratio, wrong as it was, is a **trustworthy** number, and why
§3.2 can be built on it. Mechanism 2 computes instantaneous per-process CPU% from two `/proc` reads
rather than trusting `ps -o %cpu` (a whole-lifetime average), which is the difference between the
census that missed the solver suite and the one that would not have.

### 6.3 Optional extensions — priced, unfunded

| extension | what it buys | cost |
|---|---|---|
| (a) a third cell at `--rung-sims 3200` | completes CL-023's third rung inside this band — shows whether spacing keeps shrinking within-band | ≈26 core-h (rung-dominated; the probe saving does not reach it) |
| (b) same pair, probe = current deploy champion k8×1376=11008 | the production-agent reading rather than the equal-time reading, at the cost of losing the equal-time framing | ≈47 core-h |
| (c) n=400 or n=800 per §4.4 | resolves the small (+20 elo) prior, not just the large one | ≈56 or ≈110 core-h |

None is authorized by this draft; each needs its own owner funding decision.

---

## 7. INTEGRITY GATES

Twelve, each a PRECONDITION; any FAIL ⇒ `U-UNREADABLE`. **The binding text is
[`READ_RULE.md`](READ_RULE.md) §3**, and its §3.1 structural test is re-run over all twelve.
Summary of what is inherited and what is new:

⭐ **NOTHING IN THIS TABLE MOVES FOR ATTEMPT 4. ALL TWELVE ARE CARRIED VERBATIM FROM ATTEMPT 3.** The
column below records where each gate came from and what standing it has now.

| id | provenance and standing |
|---|---|
| `G-BAND`, `G-RUNG`, `G-LEAF`, `G-RULES`, `G-TOOL`, `G-SAT` | **carried verbatim since attempt 2.** All six passed on attempt 2's real cells |
| `G-SINGLEVAR` | attempt 3's fix — alias-aware, with both emitter mirrors named at their source lines and the mirror turned into a cross-check ([`READ_RULE.md`](READ_RULE.md) §3.3). Carried |
| `G-N` | attempt 3's extension — `champ_timeouts == 0`, closing the one channel by which box load could reach a game OUTCOME rather than only its clock ([`READ_RULE.md`](READ_RULE.md) §3.4). Carried |
| `G-TIMING` | **same bar `[0.85, 1.20]`, same burn-in WINDOW, same live enforcement** ([`READ_RULE.md`](READ_RULE.md) §3.2). ⭐ **NO BAR HAS MOVED ACROSS FOUR ATTEMPTS** — not when attempt 2 missed the floor by 1.38%, and not when attempt 3 overshot the ceiling by 29%. The *budget* is what moves; the bar never has |
| `G-PROBE` | attempt 3's addition — the probe's own budget was ungated before it. Carried unchanged; its collision-note *justification* is rewritten (§3.1) because the collision no longer exists, but the gate is byte-identical |
| `G-TIMING-FULL` | attempt 3's addition — the whole-cell drift backstop (§3.5). Carried |
| `G-TENANCY` | attempt 3's addition — exclusive tenancy adjudicated from a live sampler (§6.2). ⭐ **Carried, and now VALIDATED on a real cell** |

**The structural test is EXECUTED, not only reasoned — and attempt 3 proved that matters.** Attempt
1's audit covered four of nine gates and shipped an unsatisfiable `G-TOOL`; attempt 2's covered all
nine and still shipped a `G-SINGLEVAR` that only a charitable reading could pass. Attempt 3 was the
first to make the launcher's §9 smoke leg **run this pair's own adjudicator against a real emitted
archive**, refusing to proceed unless it fails only on the band/N family — and on attempt 3's live
run every gate that could be exercised behaved to spec, including the one that stopped the cell. A
gate that cannot read what the harness emits is a **launch blocker**, not a readout surprise.

---

## 8. WHAT THIS CANNOT SHOW

Stated before launch so no branch can be narrated past them:

1. **It does not measure h1600-vs-h800 head-to-head.** The harness has no rung-vs-rung mode. A
   direct cell would be cheaper (no probe-side rust cost) and ~1.4× more powerful (no probe-side
   noise between the two rungs) — that is the right build if this question recurs.
2. **It does not re-rate the champion, and the probe is not a deployed config.** k4×1024 is an
   equal-time calibration (§3.2 step 5), not the mobile k4×1376 or the desktop k8×1376, and it is a
   *smaller* budget than either. Nothing about the probe's absolute strength transfers anywhere.
3. **It does not license any `governance/PRODUCTION.yaml` change.**
4. **It does not transfer to the walled/python F5 ladder's absolutes** (§3.4) — nor to attempts 1,
   2 or 3, all `U-UNREADABLE`.
5. **It does not tell you whether the ladder is the RIGHT ruler** — only how coarse its unit is at
   this rung, under this probe, on this band.
6. **A null result is a bound, not a zero** (§4.3) — the single most important thing this design
   commits to before any number exists, because it is the easiest thing to get backwards.
7. **A PASS on `G-TIMING` does not mean the two agents were equally fast in general.** It means
   they were equally fast **on this box, at W=22, on this band's first 40 decks**. Equal-time is a
   property of a config pair *and a load regime* — that is the entire lesson of attempts 2 and 3,
   and it applies to reading a success just as much as to reading a failure.
8. ⭐ **It does not establish that 601.19 ms/move is "the" cost of the h800 rung.** That figure is
   this box, this W, this rules era, one exclusive window. It is the best such figure the program
   has, and it is still a single window — which is exactly why the burn-in gate re-measures rather
   than assuming it (§3.2 step 6).

---

## 9. THE SMOKE LEG (pre-blind, mandatory) — the pilot, DEMOTED

n=8 decks (`--n 16 --paired`) on a **SEPARATE seed range** `150999999000..150999999007` — never
the cell band — running **CELL R800's config only**. The smoke band is **DISCARDED and never
pooled**.

⛔ **THE SMOKE LEG HAS NO TIMING AUTHORITY.** Attempts 1 and 2 used this leg to *verify the
equal-time ratio*, and attempt 2 proved that a 16-game leg at W=22 measures a different quantity than
the cell does. Attempt 3 demoted it, and this pair carries the demotion verbatim. The leg is retained
for what it CAN do and stripped of what it cannot:

**What the smoke leg verifies (all structural):**

(a) `n_failed == 0` and the harness runs clean at this exact invocation;

(b) every leaf/rules/stamp pre-flight fires against real records rather than against the harness's
documented behaviour;

(c) ⭐ **it produces the REAL MANIFEST that the pair's instrument is validated against.** The leg
**ends by running [`analyze_d2r4.py`](analyze_d2r4.py) against the smoke archive** and requires it
to fail **only** on the band/N family that a 16-game throwaway cannot satisfy by construction. This
is the standing rule proposed by the h2h post-mortem after its `G-TIEARB` gate — written against a
manifest the design *described* rather than one the harness *emits* — would have voided a healthy
archive: *"the launcher's smoke step must end by running the cell's own adjudicator against the
smoke archive, and must require it to fail only on band/N gates."* **Attempt 3 was the first to adopt
it; this pair carries it.** For the same reason, `analyze_d2r4.py --selftest` **seeds its passing fixture from a real
manifest read off disk** and refuses to run against a synthesized-only fixture.

**What it explicitly does NOT do:** verify, confirm, re-pick or gate the equal-time ratio. It
PRINTS the realized ratio under a banner saying so. **The equal-time gate is the burn-in window
inside the real cell** ([`READ_RULE.md`](READ_RULE.md) §3.2).

⛔ **Nothing moves after the blind commit.** There is no knob for any leg to re-pick (§0 item 5).

---

## 10. CLOSE-OUT (on adjudication, not before)

The six-touch checklist, verbatim from `CLAUDE.md`: (1) `experiments/results.csv` row — the primary
`S` statistic plus each cell's own vs-h800 reading (or a VOID row on the three prior attempts'
precedent) · (2) `DECISIONS.md` index line · (3) status stamp on this `DESIGN.md` and on
`READ_RULE.md` · (4) governance row flip
([`../../governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv) `decision_influenced` +
band retirement) · (5) `STATUS.md` top block · (6) the roadmap D2 line in
[`../../docs/PROGRAM_ROADMAP_2026-07-07.md`](../../docs/PROGRAM_ROADMAP_2026-07-07.md). Then
`python3 scripts/doc_lint.py`. Commit; do not push without asking.

**Owed regardless of branch, including `U-UNREADABLE`:** the realized probe cost in **ms per
total-sim at saturation, under enforced exclusive tenancy** ([`READ_RULE.md`](READ_RULE.md) §4.3
item 8). ⭐ **This is the one deliverable every D2 attempt has produced whether it succeeded or not,
and it is why the track has been worth its bands.** Attempt 2's void produced the R9-era rung figure;
attempt 3's void produced the first *clean* pair of figures (601.19 / 931.30 ms/move ⇒ 0.14552 ms per
total-sim), which is the entire basis of this pair's §3.2. A fifth attempt — or any future equal-time
pairing anywhere in this program — calibrates against whatever this cell realizes.
