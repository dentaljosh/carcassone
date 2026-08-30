# SIZING — S1 OPPONENT-MODEL ASYMMETRY: power and cost, before anything is funded

> **⚠️ DESIGN ONLY — PRE-OUTCOME, NO BAND, NO CELL, NO LAUNCH.** Every input below is
> read off an artifact already on disk and cited to it. Nothing here is pre-registered.
> Companion: [`DESIGN.md`](DESIGN.md).

---

## 1. THE INPUTS — all measured, all cited

| # | quantity | value | source |
|---|---|---|---|
| I1 | realized cost, **22016 vs 11008**, arb OFF, rust, `fixed_v1`+R9, exact-K 2 | **382.0 worker-s/game** (`22 × 24,309 s ÷ 1,400`); 6 h 45 m wall at 22 workers | `measurement/h2h_22016_20260824/ADJUDICATION_READOUT.md` §"REALIZED worker-s/game" |
| I2 | realized cost, **2752 vs 2752**, same instrument class | **96.2 worker-s/game** (≈171 core-h ÷ 6,400 games) | `results.csv invasion_screen_r3_…` note ("~171 core-h"); 8 cells × 400 decks × 2 seats |
| I3 | realized cost, champion 11008 **vs Carcasum @5000 ms/turn** | **249.7 s/game** (400 games in 120.9 min driver-wall) | `measurement/carcasum_match_20260823/READOUT.md` |
| I4 | deck-paired margin **sem at n=800** (400 decks × 2 seats), deploy budget | **0.6214** (jpriors surface B) · **0.6460** (jrules surface A) | `results.csv jpriors_d0p5_…`, `jrules_d0p25_…` |
| I5 | elo σ at n=800 | **12.285** / **12.343** (1σ) | same two rows |
| I6 | prior-surface runtime overhead at 1376 sims | **1.154×** (`scope=all`) · **1.069×** (`scope=own`) | LEVER_INDEX surface-B row, "Cost MEASURED (shared-tenancy, min-of-reps)" |
| I7 | per-game dispersion, self-play champion-vs-champion @2752 | margin **sd 18.9–20.2**; deliberate invasions/side **mean 0.32–0.63, sd 0.53–0.71**; farm pts/side **mean 21.1, sd ≈10** | computed for this doc from `measurement/s0v2_scripted_prep/smoke_ctrl{,_a,_b}_signature.json`, 3 × 60 games |
| I8 | laptop:local per-worker speed ratio | **1.0935** (laptop slower) | `results.csv invasion_screen_r3_…` ("laptop ratio 1.0935 confirmed") |
| I9 | worker defaults | local **W=30**, laptop **W=22** | owner ruling 2026-08-28, roadmap |
| I10 | E4 corpus available for replay calibration | **50 ok archives**, ~1,556 champion plies per rung at 26 archives (surface-B calibration) | `measurement/e4_exploit_grading_20260825/STAGE_A_CENSUS.md`; `jrules_priors_20260814` calibration |

---

## 2. THE COST MODEL — a two-point fit, and its honest error bars

A game's worker cost splits into a **fixed** part (the exact-K 2 marginalized endgame solve,
which does not scale with search sims) and a **search** part linear in the *total* sims both
sides spend. Fitting I1 and I2:

```
cost(worker-s/game) = 39.0 + 0.010385 × (sims_cand + sims_opp)

  I2 check:  39.0 + 0.010385 × ( 2752 +  2752) =  96.2  ✔ (fit point)
  I1 check:  39.0 + 0.010385 × (22016 + 11008) = 382.0  ✔ (fit point)
```

Predictions:

| both sides at | total sims | worker-s/game |
|---|---:|---:|
| 2752 | 5,504 | 96 |
| 11008 | 22,016 | **268** |
| **22016** | 44,032 | **496** |

⚠️ **Three caveats, stated because a two-point fit deserves them.**

1. **Two points determine a line whether or not the line is true.** The fixed intercept
   (39 s/game) is a *derived* quantity, not a measured one; the F3 desk reconciliation
   priced the exact-K solve at ≈34 s/game, which is reassuringly close, but that is
   corroboration, not measurement.
2. **The two anchors ran on different box mixes** (I1: one box, 22 workers; I2: local +
   laptop with ratio I8), and DRAM-bound per-worker throughput varies with W.
3. **House rule** (`feedback_pre_flight_smoke_test`, `feedback_bracket_hyperparams`):
   *bench, then extrapolate, then commit.* **A 20-game smoke at production knobs is owed
   before launch** — 20 × ~516 s ÷ 30 workers ≈ **6 min wall, ~1.5 worker-h**. If it comes
   back > 620 worker-s/game, re-plan rather than absorb.

---

## 3. THE CANDIDATE'S OVERHEAD AND THE `N4` COST TRIGGER

`scope=opp` boosts a **complementary** node set to `scope=own`. If the per-expansion cost of
the boost is roughly uniform across node types, then from I6:

```
overhead(opp) ≈ overhead(all) − overhead(own) + 1 = 1.154 − 1.069 + 1 = 1.085×
```

Applied to the **candidate's search half only** (the solver and the opponent's search are
untouched):

```
candidate search @22016  = 0.010385 × 22016 = 228.6 worker-s/game
                 armed   = 228.6 × 1.085     = 248.0  (+19.4)
cell cost, both sides    = 496.3 + 19.4      ≈ 516 worker-s/game

predicted ms_ratio_cand_over_opp = 248.0 / 228.6 = 1.085   (search-only timer)
                                 ≈ 1.078                   (if the shared fixed cost is inside the timer)
```

**Both are comfortably under the house `N4` trigger of 1.20** — and materially under
surface A's realized **1.2116**, which is what downgraded that cell's loss to
*confounded by budget*. Surface B's own realized ratio at `scope=all` was **1.1751**, also
under. ⚠️ **Inferred, not measured** — `jp_bench.rs` with an `opp` arm measures it directly
in minutes and should be run as part of G0.

---

## 4. POWER — what each cell can and cannot resolve

Deck-paired margin, pts/deck. From I4 take **sem ≈ 0.63 at n = 800** (400 decks × 2 seats)
and scale as `1/√n`:

| n (games) | decks | sem | **2σ MDE** | 1σ elo |
|---:|---:|---:|---:|---:|
| 400 | 200 | 0.891 | **±1.78** | ≈17.4 |
| **800** | 400 | **0.630** | **±1.26** | ≈12.3 |
| 1,200 | 600 | 0.514 | ±1.03 | ≈10.0 |
| 1,600 | 800 | 0.445 | **±0.89** | ≈8.7 |

**P2, the asymmetry contrast `D = margin(OPP) − margin(OWN)`** on a **shared** deck set.
The two arms' margins are already deck-paired within themselves, so the residual
cross-arm correlation ρ comes only from the shared champion play:

```
sem_D = 0.63 × √(2(1 − ρ)) / √(n/800)
      ρ = 0.0 (conservative) → 0.891 at n=800/arm
      ρ = 0.2 (plausible)    → 0.797 at n=800/arm
```

### 4.1 What that buys, said plainly

| hypothesised true effect | where it comes from | P1 at n=800 | P2 at n=800/arm (ρ=0) |
|---|---|---:|---:|
| **+2.0 pts/deck** on `opp` | `CL-083`'s own falsifier bar (≥2 pts/game) | z **3.17** ✅ | — |
| **+1.0 / −1.0** (opp/own), i.e. D = +2.0 | ⭐ **DESIGN §4's decomposition arithmetic** — the size the banked `all` null actually implies | z **1.59** ⚠️ *inconclusive* | z **2.25** ✅ marginal |
| +0.5 / −0.5, D = +1.0 | a small real asymmetry | z 0.79 ❌ | z 1.12 ❌ |

⭐ **This is the single most consequential line in the sizing, and it is uncomfortable:**
**the effect size the design's own arithmetic predicts (≈+1 pt/deck on the `opp` arm) is
NOT resolvable by the primary at n = 800.** P2 is why the `OWN` arm is mandatory rather
than nice-to-have — it is the only leg with 2σ power against the predicted effect, and even
it lands at z ≈ 2.25, i.e. *marginal by construction*. Two honest options:

* **(a) run n = 800/arm and accept** that a `S1-BOUNDED-NULL` at ±1.26 is the modal outcome
  for a true +1 — a real result (it caps the lever) but not a discovery; **or**
* **(b) size the two gated arms at n = 1,200 from the start** (P1 2σ = ±1.03, P2 z ≈ 2.75
  against D = +2), at **+115 worker-h ≈ +2.3 h two-box**.

**My recommendation: (b) for OPP and OWN, n = 800 for the ALL control** (the control only
needs to reproduce a known null, and 2σ = ±1.26 does that). Costed in §5.

### 4.2 Signature power (G2) — the cheap half

From I7, deck-matched **(S1-side − champion-side)** contrasts, both seatings, at n games:

| statistic | per-side sd | sem @ n=2,400 | sem @ n=800 |
|---|---:|---:|---:|
| deliberate invasions initiated /game | 0.53–0.71 | **≈0.019** | ≈0.032 |
| farm points /game | ≈10 | **≈0.29** | ≈0.50 |
| margin (for reference) | 18.9–20.2 | ≈0.58 | ≈1.00 |

The invasion-rate contrast resolves a **±0.04/game** change at 2σ on a single arm at n=800 —
against a champion baseline of 0.14/game (vs the owner) to 0.55/game (self-play). **The
signature is ~25× easier to resolve than the margin.** That asymmetry is the reason G2 is a
free rider and G3 is the expensive gate.

⚠️ **Read within-cell, never CTRL-relative across ranges.** The same three CTRL arms in I7
read 0.633 / 0.517 / 0.317 invasions/game on three disjoint 60-game ranges — a 2× spread
with the agent held fixed. This is S0v2's `§7.4` park diagnosis (*"at this budget every
CTRL-relative gate measures the deck range, not the agent"*), and the deck-matched
both-seatings contrast is immune to it because the range effect is common-mode.

---

## 5. THE COST LADDER

Throughput denominator: local W=30 + laptop W=22 at ratio I8 ⇒ **≈50.1 local-equivalent
workers**.

| gate | arms × n | worker-s/game | worker-h | two-box wall |
|---|---|---:|---:|---:|
| **G0** build + `jp_bench` cost check | — | — | ~0 | ~1 agent-day |
| **G1** expression replay, champion + 4 dose rungs, 50 archives @22016 | 5 × ~3,000 plies | ~3.2 s/search | **~13** | ~15 min |
| **pre-flight smoke** (owed) | 20 games | ~516 | **1.5** | ~6 min |
| **G3** OPP 1,200 + OWN 1,200 + ALL 800 | 3,200 games | ~516 | **459** | **~9.2 h** |
| *(G3 at the cheaper n=800/arm variant)* | 2,400 games | ~516 | *344* | *~6.9 h* |
| **G2** Stage-A census of G3's archives | 0 | — | ~0.2 | minutes |
| **G4** Carcasum guard, n=400 @22016 (conditional) | 400 games | ~364 | **40** | ~0.8 h |
| **confirm** OPP at n=1,600 (only on `S1-FIRES`) | 1,600 games | ~516 | 229 | ~4.6 h |

**To a verdict (G0→G3→G2), recommended sizing: ≈474 worker-h ≈ 9.5 h two-box wall**, plus
~1 agent-day of build. At the cheaper n=800/arm sizing: **≈359 worker-h ≈ 7.2 h**.

For scale, this program has recently spent: invasion round 3 = **171 core-h**; round 2 =
**~150 core-h**; `h2h_22016` = **149 worker-h**; the Carcasum r1 match = **28 worker-h**.
S1's verdict cell is **~3× a single invasion round** and buys a decomposition of a measured
null rather than another dose rung.

### 5.1 Disk and hygiene

G2's archive banking writes E4-schema JSON per game: 3,200 games × ~30 KB ≈ **~100 MB** on
the share. ⚠️ `reference_disk_pressure_c_drive`: the constrained drive is Windows `C:`, and
the share lives there. Budget it explicitly and prune after the census.

---

## 6. BAND AND DECK PLAN (proposed, unclaimed)

* ⚠️ **SUPERSEDED 2026-08-30: 155e9 (and 156/157e9) were CLAIMED by the FPU-resurrection round** (`governance/BAND_REGISTRY.csv` 2026-08-30 append) — G3 must re-propose from the registry+tree-sweep at its own claim time. The text below stands as the frozen proposal record only.
* **Band 155000000000** — the next free integer above `154000000000`
  (`governance/BAND_REGISTRY.csv` tail, the phase-gated arbitration band). **Not claimed by
  this document.**
* **One shared deck range for all three arms**, `155000000000 .. 155000000599` (600 decks at
  the recommended sizing; `+0..+399` at the cheaper sizing). Shared, not disjoint —
  P2 requires CRN across arms, the `tiearb_widening` `WIDE − NARROW` precedent.
* Both seatings per deck; seat-balanced.
* ⚠️ Verify the range is clean of prior use (the `28e9` action-log incident: a band recorded
  as "unused" had been consumed by root mining).
* The band **retires as decision-influenced** the moment any statistic is read.

---

## 7. WHAT THIS SIZING DOES NOT COVER

* **Option (i-b)** (invasion-shape priors at opponent nodes): its dose ladder is in *points*,
  not in the J-term's units, so no calibration transfers and no cost figure exists. Add
  ~2–3 agent-days build + its own G1-class calibration before any cell.
* **Option (ii)** (`opp_leaf`): unpriced deliberately — DESIGN §3 recommends against it.
* **The arbiter-on variant** of G3: post-tier1-swap the arbiter costs ≈42 worker-s/game/side
  (355.5 s/game sequential at B=64 pre-swap, ÷ the measured 8.46× swap), i.e. **+~84
  worker-s/game ≈ +17 %** on the cell, plus a re-owed production IDENT. Affordable if the
  owner prefers deploy fidelity to the arbiter-off precedent (DESIGN Q5).
* **Any E4 leg.** DESIGN §5.1 shows n ≈ 800 owner-played games would be needed to resolve
  +2 pts/game at 2σ against the measured per-game dispersion; the corpus is 50. E4 is
  corroboration, never a verdict, and is not costed here.
