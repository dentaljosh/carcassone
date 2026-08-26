> ## §0 — PROVENANCE BANNER (the pre-registered COST-CALIBRATION successor)
>
> ⛔→✅ **FROZEN 2026-08-25 (the blind commit is THE COMMIT THAT INTRODUCES THIS FILE; its sha is stamped into [`run_cells.sh`](run_cells.sh) and [`BLIND_COMMIT`](BLIND_COMMIT) in the follow-up commit, per the b32v64 / d2r2 pattern). No statistic of any kind exists at freeze time.**
>
> **1. What this is.** Attempt 3 at roadmap item **D2**. Pair: this file +
> [`READ_RULE.md`](READ_RULE.md). Two prior attempts both adjudicated `U-UNREADABLE`, **from two
> different causes**:
>
> | attempt | pair | band | cause of the void |
> |---|---|---|---|
> | 1 | [`../track_d2_prep/`](../track_d2_prep/DESIGN.md) | `141000000000` | **provenance** — `G-RULES` (`r9_env_ok=False`), `G-LEAF` (probe played the rung's leaf), `G-TOOL` ×2 (two code revs; an unsatisfiable `BLIND_COMMIT` sub-clause) |
> | 2 | [`../track_d2r2_prep/`](../track_d2r2_prep/DESIGN.md) | `144000000000` | **cost calibration** — `G-TIMING`, realized `0.8382` against the frozen `[0.85, 1.20]`, a 1.38% miss on the floor |
> | 3 | **this pair** | `149000000000` | — |
>
> **Attempt 2 succeeded at its own mission and this pair inherits the whole of it.** All four
> provenance fixes were verified on real 400-game cells and eight of nine gates passed. **The ONLY
> thing attempt 3 changes is the cost calibration** (plus three gate-text defects the attempt-2
> close-out named). The R9 export, the in-process champion-leaf injection, the rev pinning, the
> dirty-code refusal and the `--stamp-key` dual-address `BLIND_COMMIT` stamp are carried VERBATIM.
>
> **2. ⚠️ BLINDNESS DISCLOSURE.** The d2r2 adjudicating session is disqualified from authoring this
> pair by that pair's own `READ_RULE.md` §4, and did not. This is a fresh authoring session — but it
> is **not statistics-blind to attempt 2**: it was instructed to read
> [`../track_d2r2_prep/READOUT_D2R2.md`](../track_d2r2_prep/READOUT_D2R2.md), which prints `S`,
> `se(S)` and `z_S` on its `U-UNREADABLE` branch. The full disclosure, the reasoning, and the three
> mechanical `diff`-checkable properties that make it auditable, are in
> [`READ_RULE.md`](READ_RULE.md) §0. In one line: **every quantity carried from attempt 2 is a COST
> or a DISPERSION; `S` and `z_S` are used in no bar, no threshold, no `n`, and no budget.**
>
> **3. What changed, exhaustively.** The run id; the band (§5); the probe budget (§3.2, the heart of
> the rebuild); §3.5 (a new drift envelope); §4.2a (a dispersion calibration witness); §6.2 (the
> exclusive-tenancy window as a funding requirement); §9 (the pilot demoted to a structural smoke);
> and [`READ_RULE.md`](READ_RULE.md) §3, where the burn-in gate, the alias-aware `G-SINGLEVAR`, the
> new `G-PROBE`/`G-TIMING-FULL`/`G-TENANCY` and the `champ_timeouts` clause live. **§1, §2, §4's
> statistic and power arithmetic, §7's gate concept, §8 and §10 are carried. `READ_RULE.md` §1 and
> §6 are BYTE-IDENTICAL; its §2, §4 and §5 are verbatim plus one clearly-marked ADDITION each, and
> every such addition is additive or restrictive — no bar, branch, threshold or licence is widened
> anywhere. `READ_RULE.md` §0 gives the three `diff` commands that check this and says which are
> expected empty.**
>
> **4. THE FOUR INSTRUMENT FIXES OF ATTEMPT 2, CARRIED VERBATIM** (each verified on a real 400-game
> cell — this pair changes none of them):
>
> | # | gate it closed | the fix, still in this launcher |
> |---|---|---|
> | 1 | `G-RULES` | `run_cells.sh` **exports `CARCASSONNE_FIX_R9=1` at file scope** before any leg, and `assert_r9_env` REFUSES to run if it is unset or not truthy. R9 cannot live in the rules profile: `base_deck` derives farm data at IMPORT time and the Rust registry latches a `OnceLock` |
> | 2 | `G-LEAF` | the champion leaf is injected the way production play does it — **in-process via `--cand-leaf-json`** ([`champion_leaf_curve125.json`](champion_leaf_curve125.json)), never by exporting the curve env (which would move `DEFAULT_CONFIG` and therefore MOVE THE RUNG). `preflight_leaf` builds one champion through the harness's own module and asserts, before game 1, candidate `== a36d2e15a3b3d71d` **and** rung `== 42af12fce22e1a0f` |
> | 3 | `G-TOOL` (a) | `snapshot_rev` records `HEAD` + a code-path dirty fingerprint at start; `assert_rev_unmoved` re-checks before EACH cell; `require_clean_code` refuses a real cell on dirty CODE (`LAUNCH_DIRTY=1` + a mandatory logged reason is the only override) |
> | 4 | `G-TOOL` (b) | the harness's additive **`--stamp-key KEY=VALUE`** passthrough writes `BLIND_COMMIT` to **BOTH** addresses the read-rule searches: `manifest["BLIND_COMMIT"]` and `manifest["config"]["stamps"]["BLIND_COMMIT"]` |
>
> **5. ⛔ THERE IS NO `--sims` RE-PICK ALLOWANCE IN THIS PAIR, ON ANY LEG.** Attempt 2's allowance
> was exhausted twice over (`k4×688` → `k4×1032` on attempt 1's pilot band; `k4×1032` → `k4×1376` as
> an orchestrator-level pair decision on 2026-08-25) and **does not renew here.** The probe budget
> below is frozen by this commit. A burn-in FAIL stops the run and returns to the owner
> ([`READ_RULE.md`](READ_RULE.md) §3.2); it is not a knob.
>
> **6. The standing finding attempt 2 produced, which this pair is built on.** *"R9's import-time
> farm derivation costs the PYTHON leaf ~58% per move"* (553.8 → 877.2 ms/move on the frozen
> `HeuristicMCTS(h800, c=3.0)` rung, reproduced within 0.4% on a second box; the rust probe side
> moved only +7%). **Any equal-time pairing of a rust candidate against a Python rung must be priced
> against R9-era rung figures.** §3.2 below adds the second half of that lesson: **it must also be
> priced against SATURATED figures.**

---

# RUNG COMPRESSION: IS THE REFERENCE LADDER'S SPACING A USABLE UNIT? — DESIGN (attempt 3)

Run id `track_d2r3_prep`. Pair: this file + [`READ_RULE.md`](READ_RULE.md). Launcher:
[`run_cells.sh`](run_cells.sh). Adjudicator: [`analyze_d2r3.py`](analyze_d2r3.py). Shared
primitives: [`d2r3_lib.py`](d2r3_lib.py). Band claim: [`BAND_CLAIM.json`](BAND_CLAIM.json).
Roadmap item **D2** ([`../../docs/PROGRAM_ROADMAP_2026-07-07.md`](../../docs/PROGRAM_ROADMAP_2026-07-07.md),
Track D).

---

## 0. AUTHORIZATION BLOCK

**NOT AUTHORIZED TO LAUNCH.** The owner greenlit *rebuilding* the pair (2026-08-25, verbatim
*"let's greenlight redoing the wall clock thing"*). That funds the BUILD. Nothing here may launch,
claim a band, or spend a core-hour until the owner signs off on all five of the following,
explicitly, before game 1:

| # | owed sign-off | why it is the owner's call |
|---|---|---|
| (a) | **funding ≈44 core-h / ≈2.0 h wall** (§6) | spend; the standing cost-discipline rule requires a one-sentence confirm |
| (b) | **the band claim** — `149000000000` (§5) | `governance/BAND_REGISTRY.csv` is a source of truth the orchestrator edits, not a builder |
| (c) | **the probe budget** — `k4×1600 = 6400` (§3.2) | it is deliberately **not** a named-lineage budget, reversing the preference stated by both prior pairs. §3.2 argues why; the owner should agree with the reversal or overrule it |
| (d) | **tie-arbiter OFF** | the probe P is the pre-arbiter fair PIMC champion; running WITH the arbiter would confound rung spacing with the arbiter's own tied-ply behaviour |
| (e) | ⭐ **the EXCLUSIVE-TENANCY WINDOW** — a contiguous **≈2.5 h** with the local box as sole tenant (§6.2) | **new for this attempt, and it constrains the ORCHESTRATOR, not just the box.** No agent compute, no builds, no sibling cells, no test suites, for the whole window. Attempt 2 was contaminated by an Android build; `G-TENANCY` now aborts the run rather than disclosing it afterwards |

**Pre-launch checklist** (all must be true before any real cell fires):

- [ ] band claimed in [`../../governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv) (`149000000000`, per §5), **after re-running the all-branches sweep** — a main-tree-scoped check is what produced the `143e9` and `144e9` collisions
- [ ] this pair (`DESIGN.md` + `READ_RULE.md` + launcher + adjudicator + `d2r3_lib.py`) frozen and committed
- [ ] `BLIND_COMMIT` stamped (the launcher refuses to run a real cell on the placeholder)
- [ ] `analyze_d2r3.py --selftest` GREEN, **seeded from a real manifest** (§9)
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
| cell id | `d2r3_rung800` | `d2r3_rung1600` |
| rung | `HeuristicMCTS(h800, c=3.0)` | `HeuristicMCTS(h1600, c=3.0)` |
| `--rung-sims` | `800` | `1600` |
| probe P | frozen, identical (§3.1) | frozen, identical (§3.1) |
| n | 200 decks × 2 seatings = 400 games | 200 decks × 2 seatings = 400 games |
| order | **runs FIRST** — it carries `G-TIMING` and is the shorter cell | runs only after R800 completes AND the burn-in passed |

### 3.1 Probe P — frozen, identical in both cells

```
--info fair --opponent h800 --backend rust --k-dets 4 --sims 1600 --exact-k 2
--c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits
--rules-profile fixed_v1
```

k4×1600 = **6400 total sims**, tie-arbiter **OFF** (no `--cand-tiearb-*` flags at all — §0(d)).

⚠️ **A DELIBERATE NUMERIC COLLISION, NAMED HERE SO IT CANNOT CONFUSE A READER LATER.** The
candidate's `--sims 1600` is the same integer as CELL R1600's `--rung-sims 1600`, on a completely
different axis: the candidate's is **per-determinization sims** (`config.champion.sims_per_det`,
×4 determinizations = 6400 total), the rung's is **total plain-UCT sims**
(`config.rung.sims`). They are unrelated. Rather than perturb the budget away from its arithmetic
optimum to dodge a cosmetic clash, this pair **gates it**: `G-PROBE`
([`READ_RULE.md`](READ_RULE.md) §3) is new for attempt 3 and asserts the candidate's
`(k_dets, sims_per_det, total_sims) == (4, 1600, 6400)` in both cells. Neither prior pair gated the
probe's own budget at all — attempt 2's readout records *"No §3 gate covers the probe's own
`--sims`; recorded as context."* That gap is closed here.

### 3.2 ⭐ WHY THIS BUDGET — the re-derivation against SATURATED costs

**This section is the rebuild.** Attempt 2 died because its budget was derived against costs
measured on a **16-game pilot at unsaturated W**, and then run in a **400-game cell at saturated
W=22**. The two sides of the ratio do not degrade equally when the box fills:

| quantity | §9 pilot (n=16, W=22 unsaturated) | CELL (n=400, W=22 saturated) | drift |
|---|---|---|---|
| python `HeuristicMCTS(h800)` rung | 881.0 ms/move | **1103.1 ms/move** | **+25.2%** |
| rust probe, k4×1376 = 5504 total | 830.6 ms/move | **924.7 ms/move** | **+11.3%** |
| **equal-time ratio** | **0.9428 — in bar** | **0.8382 — OUT of bar** | **−11.1%** |

The mechanism is not subtle: at `--n 16` there are **fewer games than workers**, so the box is
never fully occupied. The python rung is DRAM-latency-bound and degrades hard under memory-system
contention; the rust probe does not. **A pilot at unsaturated W cannot predict a saturated-W
ratio.**

**So attempt 3 prices the budget against the SATURATED CELL figures, which now exist.**

**Step 1 — the probe's realized cost rate at saturation.**
```
924.7 ms/move ÷ 5504 total sims = 0.16801 ms per total-sim   [CELL R800, W=22 saturated]
```
(For comparison, the same probe read 894.4 ms/move in CELL R1600 — a 3.3% cell-to-cell spread at
identical config, which is the within-regime variation §3.5 uses.)

**Step 2 — two cost models, because the probe is not exactly linear in sims.** The only two probe
scaling points that exist, both measured at this box and this W:
```
4128 total (k4×1032)  ->  577.7 ms/move   (0.13995 ms/total-sim)
5504 total (k4×1376)  ->  830.6 ms/move   (0.15091 ms/total-sim)
exponent = ln(830.6/577.7) / ln(5504/4128) = 1.2620
```
- **(M1) LINEAR** at the saturated rate: `ms(N) = 0.16801 × N`
- **(M2) SUPERLINEAR**, anchored at the saturated point: `ms(N) = 924.7 × (N/5504)^1.2620`

**Step 3 — equal time against the saturated R9 rung (1103.1 ms/move).**
```
M1:  N = 1103.1 / 0.16801              = 6,566 total sims
M2:  N = 5504 × (1103.1/924.7)^(1/1.2620) = 6,330 total sims
geometric optimum (the N whose two projected ratios have geometric mean 1.00) = 6,429
```

**Step 4 — the pick.** `k4×1600 = 6400 total`:

| model | projected ratio at 6400 | margin to the nearest rail of `[0.85, 1.20]` |
|---|---|---|
| M1 (linear) | **0.975** | +12.8% above the floor |
| M2 (superlinear) | **1.014** | +16.2% above the floor |

⭐ **The property that matters, and the one attempt 2 lacked: 6400 is in bar under BOTH cost
models, with ≥12.8% margin in the worst case.** Its realized margin was **−1.4%**; this pair's
worst-case projected margin is **+12.8%**.

**Where attempt 2's arithmetic actually went wrong, stated precisely** (not "it picked a bad
number" — it picked a defensible number from the wrong measurements). At the SAME budget, `k4×1376
= 5504`, the pilot **measured 0.9428** and the cell **realized 0.8382**. The decomposition is
exact:

```
rung  881.0 -> 1103.1 ms/move   x1.252   (python, DRAM-latency-bound: degrades hard under contention)
probe 830.6 ->  924.7 ms/move   x1.113   (rust: degrades much less)
ratio 0.9428 -> 0.8382          x1.113/1.252 = x0.889   =  -11.1%
```

⛔ **The general trap, worth carrying well past this pair: a RATIO of two costs looks robust to a
common scaling error, and is not — because the two sides of a rust-vs-python pairing have different
bottlenecks and therefore different load sensitivities.** A calibration that would survive a
uniform 25% slowdown is destroyed by a 25%/11% split one. This is why §3.2 prices against saturated
figures on **both** sides rather than assuming the regime factors out, and why nothing in steps 1–6
is trusted to be sufficient on its own — **step 7 is what actually makes the design safe.**

**Step 5 — a convergence check against an independent derivation.** Attempt 2's own §0 item 9
computed that `k4×1566 = 6264` *"would centre the ratio at 1.00"* — from the *pilot* rung (877.2)
and the *pilot* probe rate (0.140). That derivation and this one share no input, and they land 2.2%
apart. Two independent routes to the same budget is worth more than either alone.

**Step 6 — the named-lineage preference is DELIBERATELY REVERSED, and this is sign-off (c).** Both
prior pairs preferred a *named production-lineage* budget (`k4×688 = 2752`, `k4×1376 = 5504` are
real `fair_ruler_*` configs) over an assembled one, and attempt 2 explicitly rejected `k4×1566`
because it was *"invented"*. **That preference is what cost attempt 2 its band.** The named ladder
is a doubling sequence — 2752, 5504, 11008 — and the equal-time target (≈6,430) falls in a gap
where **no named budget exists**: the next one up projects a ratio of ~2.01, five times outside the
bar. When the estimand's denominator is equal wall-clock, **the budget is a CALIBRATION, not a
config claim**, and calibrating to a round number near the arithmetic optimum is more defensible
than calibrating to a familiar number 21% below it. `1600` is chosen over the exact optimum `1629`
because it is round, and because a 0.5% difference is far inside the ±3.3% cell-to-cell cost
spread — nothing is being tuned. **The consequence for interpretation, stated up front: this
cell's probe is NOT a config the program has run before**, so §3.4's non-poolability caveat binds
harder than it did for attempt 2, and §8 item 2 is restated accordingly.

**Step 7 — and the burn-in gate is what makes any residual error cheap.** Every figure above is an
extrapolation from one prior cell, on one box, on one day. It can still be wrong: thermal state,
a kernel change, a different deck band's game-length distribution. **The design does not rely on
being right** — [`READ_RULE.md`](READ_RULE.md) §3.2 verifies the realized ratio on the cell's own
first 40 decks, at full production W, inside the adjudicated games, and aborts for ≈3.6 core-h if
it is out of bar. **The calibration is a best estimate; the burn-in is the guarantee.**

### 3.2a ⭐ THE BURN-IN MECHANISM IS VALIDATED RETROSPECTIVELY, ON ATTEMPT 2's OWN RECORDS

The claim "a window inside the cell predicts the cell; a pilot outside it does not" is not left as
an argument. It is **measured**, by running this pair's own
[`d2r3_lib.read_burnin()`](d2r3_lib.py) over attempt 2's completed CELL R800 archive — i.e. by
asking *what would the burn-in gate have done, had it existed?* (Only `champ_prefix_secs/moves` and
`rung_secs/moves` are read; no outcome field is touched. These are cost quantities, the permitted
class under [`READ_RULE.md`](READ_RULE.md) §0 item 3.)

| predictor of CELL R800's realized whole-cell ratio (**0.8382**) | reading | error | would it have fired the gate correctly? |
|---|---|---|---|
| the **§9 pilot** — n=16, disjoint band, unsaturated W | **0.9428** | **+12.5%** | ❌ **NO — it PASSED, and the cell then failed** |
| the **burn-in window** — decks +0..+39 of the cell itself, 80 games, production W | **0.8333** | **−0.6%** | ✅ **YES — FAIL against `[0.85, 1.20]`, correctly, on the cell's own first 40 decks** |

Three things follow, and they are the empirical case for the whole redesign:

1. **The burn-in window is a ~20× more accurate predictor of the cell than the pilot was** (0.6% vs
   12.5%), because it is the same games in the same regime rather than a different quantity that
   merely shares a name.
2. **It errs on the CONSERVATIVE side** — 0.8333 sits slightly *below* the whole-cell 0.8382, i.e.
   the window is marginally more pessimistic than the cell it gates. For a fail-closed precondition
   that is the right direction.
3. **Attempt 2 would have aborted at ~10 minutes and ~3.3 core-h instead of running 1.88 h to a
   void**, and its band would have been retired at 40 decks instead of 200. That decision point is
   MEASURED, not modelled: on that archive the 80th burn-in record landed with **81 of 400 games
   complete — 18.5% of the cell's wall** — because the pool dispatches in task order and the games
   are of similar length, so only ONE game beyond the window had been played when the gate could
   have fired.

The window is also statistically ample: 80 games carry **5,515 candidate moves and 5,682 rung
moves**, so per-move timing noise in the ratio is negligible and what the window measures is the
*load regime*, which is exactly the quantity in question.

⚠️ **What this does NOT show.** It is one archive, on one box, at one budget. It demonstrates that
the burn-in window tracks its own cell tightly under saturation; it does not promise that
`k4×1600` will land in bar. That is what the gate is for.

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
quantity from ONE implementation ([`d2r3_lib.timing_ratio`](d2r3_lib.py)), used by both the live
watcher and the adjudicator, so the trap can be got wrong at most once.

### 3.4 ⚠️ NOT POOLABLE WITH THE F5 LADDER — and now not with attempt 2 either

The F5 `fair_ruler_*` rows ran on the **python** backend under **pre-`fixed_v1`** rules. D2 runs
`fixed_v1` + R9 + rust on the probe side. **D2's ABSOLUTE numbers are not comparable to
`fair_ruler_rebase_*`'s; only D2's internal cell-vs-cell contrast (§4) is claimed.**

Added for attempt 3: the probe budget `k4×1600` has **no prior cell at all** (§3.2 step 6), and
attempts 1 and 2 are both `U-UNREADABLE` — so **nothing about this cell's absolutes may be compared
to any earlier D2 attempt either.** The only claim is the within-band, deck-paired, cell-vs-cell
contrast.

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

---

## 4. THE PRIMARY STATISTIC AND ITS POWER — arithmetic BEFORE any number

**PRIMARY = the deck-paired spacing**

```
S = M_R800 − M_R1600
```

where `M_cell` is that cell's deck-paired mean margin (points/game, probe-minus-rung) computed over
the `n_common` decks present in BOTH cells. **Elo is SECONDARY**, reported for continuity with
CL-023, converted via the realized scale (§4.3).

### 4.1 The dispersion we are entitled to assume

At n=200 decks the F5 cells realized `paired_mean_margin / paired_z` ⇒ `se(M)`:

```
fair_ruler_rebase_2752    8.6425 / 9.5101  = 0.909 pts
fair_ruler_rebase_5504   10.7825 / 11.3029 = 0.954 pts
fair_ruler_k8x1376_11008  7.935 / 8.4547   = 0.939 pts
```

Take **se(M) ≈ 0.93 pts at n_paired = 200**.

### 4.2 CRN and se(S)

CRN (common decks, same seatings) is used across the two cells, but per CL-068 the measured
cross-cell CRN benefit was only ~9.9% of contrast variance in the comparable case. Assume
**ρ ≈ 0.10** — do not bank more than that:

```
se(S) = 0.93 × sqrt(2 × (1 − 0.10)) = 1.25 pts        [THE COMMITTED EXPECTATION]
```

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
- the **power table below is quoted at BOTH** 1.25 (committed) and 1.2825 (realized), so no reader
  has to guess which is operative;
- the `D2-COMPRESSED` reachability condition is **unaffected**: it depends on the branch constant
  `S < 2.5 pts` against `z_S ≥ 2.0`, i.e. on `se_realized < 1.25`, not on what the design expected.
  Attempt 2's realized 1.2825 means that on a run of this shape **`D2-COMPRESSED` is a narrow
  branch**, and `READ_RULE.md` §4's boundary note — which says exactly this, verbatim, and predates
  all three attempts — is now backed by data rather than arithmetic alone.

### 4.3 What n=200 buys

```
2σ MDE(S) = 2 × 1.25   = 2.50 pts     [committed dispersion]
2σ MDE(S) = 2 × 1.2825 = 2.57 pts     [attempt-2-realized dispersion]
```

Converting with the F5 scale (`fair_ruler_rebase_2752`: +135.0 elo ↔ +8.6425 pts ⇒ **~15.6
elo/pt**) that is **≈39–40 elo**; at attempt 2's own realized CELL R800 scale (13.304 elo/pt) it is
**≈33–34 elo**. Both are reported in the readout ([`READ_RULE.md`](READ_RULE.md) §4.3 item 5).

| the prior reading | in points | z at n=200 | resolves? |
|---|---|---|---|
| CL-023's +55.2 elo | ≈3.5 pts | ≈2.7–2.8 | **YES** — above 2σ |
| results.csv's +20.0 elo | ≈1.3 pts | ≈1.0 | **NO** — inside the 2σ MDE |

**State this bluntly: at the roadmap's n=200 the cell can confirm the large prior (CL-023) but
cannot discriminate the small prior (results.csv) from zero. A null read at n=200 is therefore NOT
evidence that the spacing is zero — it is only a bound of ≈39 elo.** `READ_RULE.md` §4 names a
branch (`D2-BOUNDED-NULL`) for exactly this outcome so it cannot be narrated as a refutation after
the fact.

### 4.4 The n that would resolve the small reading — recorded now, funded by nobody

```
n=400 decks/cell:  se(S) = 0.88 pts  ⇒  2σ MDE = 1.77 pts ≈ 28 elo   (the +20 reading still only z≈1.5)
n=800 decks/cell:  se(S) = 0.62 pts  ⇒  2σ MDE = 1.25 pts ≈ 19 elo
```

Fully separating +55 from +20 needs **n ≈ 800 decks/cell ≈ 176 core-h** (4× §6). **Honest framing:
this design is a SCREEN for the large reading, not an adjudication between the two priors.**
Whether to fund an extension is a fresh owner decision, priced here so a future "just add n" ask
does not have to re-derive it.

⚠️ **One thing the burn-in changes about that menu.** The dominant risk of a bigger `n` used to be
that a whole expensive pair could void on a timing precondition discovered at the end. With
[`READ_RULE.md`](READ_RULE.md) §3.2 in place a cost-calibration void costs ≈3.6 core-h regardless of
`n`, which makes an n=400 extension materially less risky than it was for attempts 1 and 2. That is
an *observation for the owner's funding decision*, **not a request** — no branch of this pair
licenses an extension ([`READ_RULE.md`](READ_RULE.md) §5).

---

## 5. THE BAND

**Band `149000000000`.** Seeds `149000000000 .. 149000000199` (200 decks), used by **BOTH** cells
(CRN by design — the same deck set, same seatings, feeding §4's paired statistic). The burn-in
window ([`READ_RULE.md`](READ_RULE.md) §3.2) is the first 40 of those decks,
`149000000000 .. 149000000039`; it is part of the cell, not a separate allocation.

⛔ **NOT CLAIMED at freeze-draft time.** The row is in [`BAND_CLAIM.json`](BAND_CLAIM.json) and is
appended to the registry by the orchestrator in the stamping commit, before launch.

**Picked by the ALL-BRANCHES SWEEP, which is the procedure of record** — established by
[`../carcasum_arb_challenge_prep/DESIGN.md`](../carcasum_arb_challenge_prep/DESIGN.md) §4.1 after a
main-tree-scoped registry check missed `144000000000` sitting on an unmerged sibling branch and
double-claimed it. The corrected procedure, re-run for this pair: for **every** ref in
`refs/heads` and `refs/remotes`, read that ref's own `governance/BAND_REGISTRY.csv` **and** every
`measurement/**/BAND_CLAIM*.json` it carries, then take the lowest integer clear of everything
found anywhere. Result:

| band | status found | source |
|---|---|---|
| `143000000000` | claimed | `carcasum_rung2_prep` |
| `144000000000` | **retired** (attempt 2's spent void) | `track_d2r2_prep` |
| `145000000000` | claimed | `track_d1_fair_rebase` (PRIMARY) |
| `146000000000` | **soft-reserved, no registry row anywhere** | `track_d1_fair_rebase` — earmarked for its own n=800 extension |
| `147000000000` | claimed | `carcasum_arb_challenge_prep` |
| `148000000000` (+ top-up to `148000000699`) | claimed | `h2h_22016_prep` — the highest allocation found on any ref |
| **`149000000000`** | **free everywhere** | no ref, no registry version, no claim file mentions it |

`146000000000` is skipped on the same reasoning `carcasum_arb_challenge_prep` and `h2h_22016_prep`
both used: by the letter it is unclaimed, but a sibling track has spent a committed paragraph
earmarking it, and taking it would manufacture the exact collision the corrected procedure exists
to prevent.

Per CL-068, **band identity is load-bearing**: never pool D2's numbers across bands, and this band
**retires from confirmatory use** once it has influenced any decision.

⚠️ **The RELEASE-IF-NEVER-LAUNCHED clause does NOT apply to a burn-in abort.** If the burn-in gate
fires, ~40 decks of real records exist on `149000000000` and the band is **spent and retired**
([`READ_RULE.md`](READ_RULE.md) §3.2). The band is released only if the cell never runs at all.

---

## 6. COST

Arithmetic from attempt 2's **realized** per-cell figures (W=22, saturated, R9 rung, rust probe),
not from a model. The only delta is the probe budget, `5504 → 6400 total sims` (+16.3%), which
raises the probe side by ~18% per move (§3.2 M2) and leaves the rung side untouched.

| | attempt 2 REALIZED (probe @5504) | attempt 3 PROJECTED (probe @6400) |
|---|---|---|
| CELL R800 | 45 min wall · 16.4 core-h | **≈48 min wall · ≈17.7 core-h** |
| CELL R1600 | 68 min wall · 24.9 core-h | **≈72 min wall · ≈26.2 core-h** |
| **TOTAL** | **1.88 h wall · 41.3 core-h** | **≈2.0 h wall · ≈43.9 core-h** |

Plus the §9 smoke leg (n=16): **≤5 min**. `CELL R1600` remains **rung-dominated** — the rust
speed-up on the probe side does not shrink the Python rung (§3.3) — which is why the deeper-rung
cell is the more expensive one.

⚠️ **§6 is honest about its own lineage this time.** Both prior pairs printed a cost section derived
from a *pre-R9, pre-rebudget* era and then had to disclaim it twice (attempt 2's §0 items 6 and 9,
and a 2.57× realized overrun). The table above is derived from realized 400-game figures at the
production knobs; the residual uncertainty is the probe-scaling exponent, worth ~±1.5 core-h.

**The burn-in abort cost — MEASURED, not modelled** ([`READ_RULE.md`](READ_RULE.md) §3.2). The
watcher waits until all 80 burn-in games have records. Replayed against attempt 2's own archive
(record mtimes), that moment arrives with **81 of 400 games complete — 18.5% of CELL R800's wall,
7.9 min into the record stream**: the pool dispatches in task order and the games are of similar
length, so exactly one game beyond the window had been played. At attempt 3's budget that is
**≈10 min wall / ≈3.6 core-h = 8.2% of the pair's ≈43.9 core-h.** That number is the whole argument
for the burn-in: it converts a cost-calibration void from a 44-core-h loss into a 3.6-core-h one.

### 6.2 ⭐ THE EXCLUSIVE-TENANCY WINDOW — a funding requirement, not a courtesy

**This cell is a timing-gated instrument. It is an EXCLUSIVE TENANT of the local box for its whole
window.** House rule `feedback_no_agent_compute_beside_eval`: *nice + thread-caps are NOT
coexistence on this DRAM-bound box*, and a TIMING bench is an exclusive tenant.

**The precedent is this cell's own immediate predecessor.** Attempt 2's readout discloses that an
Android cross-compile + gradle build ran on the same box during CELL R800's final ~10 minutes,
whose effect on the ratio was *"real in magnitude and undetermined in direction."* The
gate that voided the run is the one that co-tenancy most directly threatens.

**What is required, concretely:**

- a **contiguous ≈2.5 h window** (≈2.0 h of games + smoke + pre-flights + adjudication) with the
  local 5900XT box as **sole tenant**;
- for that whole window: **no agent compute, no builds (APK/cargo/gradle/Cython), no test suites,
  no sibling measurement cells, no other `--shared-claim` runs** — including work started by the
  orchestrating session itself, which is what happened last time;
- the laptop and any other box are unaffected and may run whatever they like — **the constraint is
  on the box the cell is timing.**

**It is enforced in two places, because a preflight alone is provably insufficient** — attempt 2's
co-tenant **started after the cell did**:

1. `run_cells.sh` **refuses to start** on a non-exclusive box (foreign `RUN_LIVE.json` sentinels,
   sibling-run processes, or foreign CPU at or above one core), overridable only by
   `ALLOW_COTENANT=1` with a mandatory logged reason;
2. a **sampler runs for the cell's whole life**, taking instantaneous per-process CPU readings, and
   **aborts the cell** on two consecutive over-bar samples — the same cheap-abort path as a burn-in
   fail. `G-TENANCY` ([`READ_RULE.md`](READ_RULE.md) §3) then adjudicates the log.

### 6.3 Optional extensions — priced, unfunded

| extension | what it buys | cost |
|---|---|---|
| (a) a third cell at `--rung-sims 3200` | completes CL-023's third rung inside this band — shows whether spacing keeps shrinking within-band | ≈17 core-h (rung-dominated) |
| (b) same pair, probe = current deploy champion k8×1376=11008 | the production-agent reading rather than the equal-time reading, at the cost of losing the equal-time framing | ≈36 core-h |
| (c) n=400 or n=800 per §4.4 | resolves the small (+20 elo) prior, not just the large one | ≈88 or ≈176 core-h |

None is authorized by this draft; each needs its own owner funding decision.

---

## 7. INTEGRITY GATES

Twelve, each a PRECONDITION; any FAIL ⇒ `U-UNREADABLE`. **The binding text is
[`READ_RULE.md`](READ_RULE.md) §3**, and its §3.1 structural test is re-run over all twelve.
Summary of what is inherited and what is new:

| id | status vs attempt 2 |
|---|---|
| `G-BAND`, `G-RUNG`, `G-LEAF`, `G-RULES`, `G-TOOL`, `G-SAT` | **carried verbatim.** All six passed on attempt 2's real cells |
| `G-SINGLEVAR` | **fixed** — alias-aware from the start, with both emitter mirrors named at their source lines, and the mirror turned into a cross-check ([`READ_RULE.md`](READ_RULE.md) §3.3) |
| `G-N` | **extended** — `champ_timeouts == 0` added, closing the one channel by which box load could reach a game OUTCOME rather than only its clock ([`READ_RULE.md`](READ_RULE.md) §3.4) |
| `G-TIMING` | **same bar `[0.85, 1.20]`, different WINDOW** — read over the burn-in window and enforced live ([`READ_RULE.md`](READ_RULE.md) §3.2). **No bar moved across three attempts** |
| `G-PROBE` | **new** — the probe's own budget was never gated |
| `G-TIMING-FULL` | **new** — the whole-cell drift backstop (§3.5) |
| `G-TENANCY` | **new** — exclusive tenancy adjudicated from a live sampler (§6.2) |

**The structural test is EXECUTED this time, not only reasoned.** Attempt 1's audit covered four of
nine gates and shipped an unsatisfiable `G-TOOL`; attempt 2's covered all nine and still shipped a
`G-SINGLEVAR` that only a charitable reading could pass. For attempt 3 the launcher's §9 smoke leg
**runs this pair's own adjudicator against a real emitted archive** and refuses to proceed unless it
fails only on the band/N family — so a gate that cannot read what the harness emits is a **launch
blocker**, not a readout surprise.

---

## 8. WHAT THIS CANNOT SHOW

Stated before launch so no branch can be narrated past them:

1. **It does not measure h1600-vs-h800 head-to-head.** The harness has no rung-vs-rung mode. A
   direct cell would be cheaper (no probe-side rust cost) and ~1.4× more powerful (no probe-side
   noise between the two rungs) — that is the right build if this question recurs.
2. **It does not re-rate the champion, and the probe is not a deployed config.** k4×1600 is an
   equal-time calibration (§3.2 step 6), not the mobile k4×1376 or the desktop k8×1376. Nothing
   about the probe's absolute strength transfers anywhere.
3. **It does not license any `governance/PRODUCTION.yaml` change.**
4. **It does not transfer to the walled/python F5 ladder's absolutes** (§3.4) — nor to attempts 1
   or 2, both `U-UNREADABLE`.
5. **It does not tell you whether the ladder is the RIGHT ruler** — only how coarse its unit is at
   this rung, under this probe, on this band.
6. **A null result is a bound, not a zero** (§4.3) — the single most important thing this design
   commits to before any number exists, because it is the easiest thing to get backwards.
7. **A PASS on `G-TIMING` does not mean the two agents were equally fast in general.** It means
   they were equally fast **on this box, at W=22, on this band's first 40 decks**. Equal-time is a
   property of a config pair *and a load regime* — that is the entire lesson of attempt 2, and it
   applies to reading a success just as much as to reading a failure.

---

## 9. THE SMOKE LEG (pre-blind, mandatory) — the pilot, DEMOTED

n=8 decks (`--n 16 --paired`) on a **SEPARATE seed range** `149999999000..149999999007` — never
the cell band — running **CELL R800's config only**. The smoke band is **DISCARDED and never
pooled**.

⛔ **THE SMOKE LEG HAS NO TIMING AUTHORITY. This is the single most important change from attempts
1 and 2, and it is the direct answer to close-out item 1.** Both prior pairs used this leg to
*verify the equal-time ratio*, and attempt 2 proved that a 16-game leg at W=22 measures a different
quantity than the cell does (§3.2). The leg is retained for what it CAN do and stripped of what it
cannot:

**What the smoke leg verifies (all structural):**

(a) `n_failed == 0` and the harness runs clean at this exact invocation;

(b) every leaf/rules/stamp pre-flight fires against real records rather than against the harness's
documented behaviour;

(c) ⭐ **it produces the REAL MANIFEST that the pair's instrument is validated against.** The leg
**ends by running [`analyze_d2r3.py`](analyze_d2r3.py) against the smoke archive** and requires it
to fail **only** on the band/N family that a 16-game throwaway cannot satisfy by construction. This
is the standing rule proposed by the h2h post-mortem after its `G-TIEARB` gate — written against a
manifest the design *described* rather than one the harness *emits* — would have voided a healthy
archive: *"the launcher's smoke step must end by running the cell's own adjudicator against the
smoke archive, and must require it to fail only on band/N gates."* **This pair is the first to adopt
it.** For the same reason, `analyze_d2r3.py --selftest` **seeds its passing fixture from a real
manifest read off disk** and refuses to run against a synthesized-only fixture.

**What it explicitly does NOT do:** verify, confirm, re-pick or gate the equal-time ratio. It
PRINTS the realized ratio under a banner saying so. **The equal-time gate is the burn-in window
inside the real cell** ([`READ_RULE.md`](READ_RULE.md) §3.2).

⛔ **Nothing moves after the blind commit.** There is no knob for any leg to re-pick (§0 item 5).

---

## 10. CLOSE-OUT (on adjudication, not before)

The six-touch checklist, verbatim from `CLAUDE.md`: (1) `experiments/results.csv` row — the primary
`S` statistic plus each cell's own vs-h800 reading (or a VOID row on the two prior attempts'
precedent) · (2) `DECISIONS.md` index line · (3) status stamp on this `DESIGN.md` and on
`READ_RULE.md` · (4) governance row flip
([`../../governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv) `decision_influenced` +
band retirement) · (5) `STATUS.md` top block · (6) the roadmap D2 line in
[`../../docs/PROGRAM_ROADMAP_2026-07-07.md`](../../docs/PROGRAM_ROADMAP_2026-07-07.md). Then
`python3 scripts/doc_lint.py`. Commit; do not push without asking.

**Owed regardless of branch, including `U-UNREADABLE`:** the realized probe cost in **ms per
total-sim at saturation** ([`READ_RULE.md`](READ_RULE.md) §4.3 item 8). Attempt 2's void was worth a
band precisely because it produced that number for the R9 rung; a fourth attempt, or any future
equal-time pairing anywhere in this program, calibrates against it.
