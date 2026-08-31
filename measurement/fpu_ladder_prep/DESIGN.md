# FPU DOSE-LADDER — BRACKETING THE ENDPOINT — DESIGN

> **STATUS: FROZEN** (2026-08-30). This document and [`READ_RULE.md`](READ_RULE.md) are **the pair**,
> and the pair is law. ⛔ **NOTHING IN EITHER FILE MOVES AFTER THE BLIND COMMIT.**
>
> ⛔ **0 games have been played at this commit. No band is claimed at this commit.** The instrument
> exists and `analyze_ladder.py --selftest` is `PASS`.
>
> ⚠️⚠️ **THE GOLDEN GATE IS NOT INHERITED AND HAS NOT BEEN RUN.** The parent round's
> `FPU_BITEXACT.json` is `PASS` on a wheel that no longer exists. `golden_gate/run_golden_gate.sh`
> is **built and unlaunched**, and `run_cells.sh` refuses every real rung until it has been run **on
> that box, at the launch rev**. See §9.
>
> ⚠️ **THE FUNDING BRIEF'S "~5.5–6 h" IS NOT ACHIEVABLE AT THE OWNER'S `W_LOCAL=14`.** The honest
> realized-rate wall is **≈ 12.8 h**. §6 shows the arithmetic and names the one lever that would
> change it. That is an owner decision, not a measurement decision, and nothing in the pair moves
> either way.

---

## 0. THE ONE-PARAGRAPH VERSION

The [`fpu_resurrection`](../fpu_resurrection_prep/DESIGN.md) round measured `fpu_reduction` on the
classical champion for the first time — the knob had been **structurally unreachable** on the
champion's backend until 2026-08-29 — and `0.2` fired: `M = +2.951 ± 0.683 pts/deck`, `z +4.32`,
`n = 400` deck-paired on band `155e9`. Its second dose `0.4` read `+0.754 ± 0.715`
(`F-UNRESOLVED`, amended). Two doses give a **direction**, never an optimum, and `0.2` is a **ladder
endpoint** — `feedback_bracket_hyperparams` is explicit that a peak at an endpoint is not bracketed
and must be extended before adoption. This round is that extension: **four rungs at
`0.05 / 0.1 / 0.15 / 0.3`**, each `n = 800` games (400 seat-balanced decks × 2 seatings) candidate-only
against the **unmodified champion**, each **on its own fresh band**, at the deployed budget
`k16 × 1376 = 22016` with the tie arbiter off both sides. Three rungs bracket `0.2` from **below** —
the direction the data points — and one adds an interior point above it.

### 0.1 ⭐⭐ THE BARS ARE EFFECT-SIZED. THIS IS THE POINT OF THE ROUND'S DESIGN.

The owner ruled on 2026-08-30 ("effect size sounds right"), and it is now a standing rule in
`CLAUDE.md`:

> **BARS ARE SET AT THE EFFECT SIZE THE DECISION CARES ABOUT — NEVER AT `2σ̂` OF THE INSTRUMENT.** A
> bar defined as exactly `2·se_model` makes the kill branch fire only on a NEGATIVE point estimate: a
> true null then reads UNRESOLVED ~half the time and the round discharges nothing. … Write the prereg
> bar from "what effect would change the decision", size `n` to resolve THAT, and if the honest answer
> is "we can only afford the bounding direction," SAY SO in the READ_RULE including the null's expected
> read distribution.

The parent round is one of the two realized cases that produced the ruling: its `BAR_M = 1.381` was
*exactly* `2·se_model(400)`, and its `READ_RULE` §8 had to disclose that a true null was very nearly a
coin flip between `F-REKILL` and `F-UNRESOLVED`. So this round's bar is **`+1.5 pts/deck`**, a
decision quantity, read in two directions:

| branch | condition | what it means |
|---|---|---|
| **`R-ADOPT-CANDIDATE`** | `LB95(M) >= +1.5` | this dose is worth taking through the adoption chain |
| **`R-BOUNDED`** | `UB95(M) < +1.5` | this dose is not, at 95% |
| **`LADDER-DEAD`** (round) | **every** rung's `UB95 < +1.5` | `fpu = 0.2` stands best-known; its confirmation leg becomes proposable |

⛔ **AND §8 OF THE READ RULE STATES WHAT THAT COSTS, BEFORE GAME 1.** It is not a small cost and it
is the single most important thing an owner reading this round should know:

- under a **true global null**, `LADDER-DEAD` fires **≈ 10.4 %** of the time. The other ~90 % of the
  time at least one rung reads `R-UNRESOLVED` and **the round discharges nothing**;
- at a **true `+1.5`** — the bar itself — a rung reads `R-UNRESOLVED` **≈ 95 %** of the time;
- against a **repeat of the incumbent's `+2.951`**, a rung adopts **≈ 54 %** of the time;
- `LADDER-DEAD` at 80 % power under a true null would need **≈ 1,100 decks per rung** (2,200 games
  per rung, 8,800 games total — ~2.8× this round's compute). Adopting a repeat of `+2.951` at 80 %
  would need **≈ 730 decks per rung**.

⭐ The other side of that ledger: at the `LB95` bar the **family-wise false-adopt rate under a global
null is ≈ 0.006 %** across all four rungs. **This bar cannot fire on noise.** The round is bought as
a *screen against a demanding bar*, and its bounding direction is weak by construction. `READ_RULE`
§8 is where that is written down; this section exists so it is not discovered afterwards.

### 0.2 ⚠️ WHAT THE PARENT ROUND LICENSED, AND WHAT IT DID NOT

`F-RESURRECT` on `0.2` licensed **proposing follow-on work**. It licensed **no production change**,
it located **no optimum**, and — because the two doses sat on **different bands** — it did not even
license reading `0.2 > 0.4` as a fact about the axis. CL-068 measured **1.8–2.2× over-dispersion on
merely cross-band contrasts**, in both the elo and the deck-paired-margin statistics. Everything this
round says about the *shape* of the dose response is subject to the same limit, which is why §5 puts
the shape in a companion table and the **round verdict is a conjunction over independent within-band
readings**, never a curve fit.

---

## 1. WHAT IS BEING ASKED

**Is there a dose of `fpu_reduction` worth taking through the adoption chain — or does the incumbent
`0.2` stand as best-known?**

⚠️ It is a **strength** question, judge-free, decided by game outcomes. `feedback_evloss_grader`'s F4
lesson binds on any temptation to grade it with a judge: judged headroom is family-relative, and a
`+1.49` in-family ceiling read `−0.64` at `z −3.8` out-of-family on the same CRN worlds. Game
outcomes outrank any judged number and this round uses nothing else.

### 1.1 The mechanism, restated

The champion's priors are a **heuristic softmax over Δleaf** at `τ_p = 5`, deliberately flat. A flat
prior plus the legacy optimistic FPU (`q = 0` for every unvisited child) makes the search spend
visits **breadth-first** across a wide root. A pessimistic FPU (`q = parent.Q − r`) makes an
unexplored sibling look *worse* than the parent's current estimate, concentrating visits on children
the priors already like. `r` is a **dose**: at `r → 0` the behaviour approaches the champion's own
(but is **not** the champion — see §3.1), and at large `r` the search narrows to the point of
tunnel vision. The parent round found `+2.95` at `0.2` and `+0.75` at `0.4`. **The interesting
question is what happens below `0.2`**, and this round asks it three ways.

### 1.2 ⛔ WHY THE LADDER STILL CANNOT DRAW A CURVE

`feedback_bracket_hyperparams` wants ≥3 well-spread points on a **comparable footing**. Four rungs on
four bands are four *within-band* readings that do **not** share a footing: a rung-vs-rung difference
is cross-band and carries CL-068's over-dispersion in full. ⭐ **The one-band-per-rung shape is a
deliberate trade** (§5): it keeps every *primary* in the robust class and retires cleanly, at the
price of forbidding the curve. `READ_RULE` §5.3 says so and the read-out prints the shape as a
DIRECTION under an explicit warning.

---

## 2. THE RUNGS

| rung | box | knob | dose | band | n |
|---|---|---|---|---|---|
| `CELL_FPU005` | local | `fpu_reduction` | **0.05** | `164000000000` | 400 decks × 2 = 800 games |
| `CELL_FPU010` | local | `fpu_reduction` | **0.10** | `165000000000` | 800 games |
| `CELL_FPU015` | laptop | `fpu_reduction` | **0.15** | `166000000000` | 800 games |
| `CELL_FPU030` | laptop | `fpu_reduction` | **0.30** | `167000000000` | 800 games |

Opponent, all four: the **UNMODIFIED champion**. Both sides:

- fair PIMC **`k16 × 1376 = 22016`** — the 2026-08-30 promoted desktop champion
- `rules_profile = fixed_v1`, `CARCASSONNE_FIX_R9=1` (env-latched at import)
- `exact_k = 2`, mode `marginalized`
- backend `rust`
- leaf `a36d2e15a3b3d71d` (curve125) — **the same leaf on both sides** (the knob is not a leaf term)
- **tie-arbiter OFF** (§2.3)
- the knob on the **candidate only**, via `--cand-fpu-reduction`

### 2.1 Why these four doses

`0.2` fired and `0.4` did not. The direction is **falling with dose**, so the informative extension is
**downward**: `0.15` (adjacent), `0.10` (half), `0.05` (a quarter). `0.30` adds the one interior point
between the two measured doses so the region between them is not assumed. ⛔ `0.2` and `0.4` are **not
re-run**: their bands are spent, they are context rows (§4.2), and re-running a dose on a new band to
"confirm" it is the incumbent's own confirmation leg, which is step 2 of the adoption chain and a
separate prereg.

### 2.2 ⭐⭐ `0.05` IS THE ROUND'S OWN LIVENESS WORRY, AND IT IS ANSWERED IN THE GOLDEN GATE

A dose small enough to change **no decision** is indistinguishable from **a knob that never bound** —
and "a knob that never bound" is the exact defect this entire family of rounds was funded to close
(`rust_agent.search_config_rs` passed a hard-coded `None` until 2026-08-29). Such a rung plays
champion-vs-champion, moves no leaf hash, sits comfortably inside `G-SAT`'s rail, and reads as a
clean, credible null.

Three things answer it, and the first is new in this round:

1. ⭐⭐ **The golden gate runs its positive control AT `0.05`, and adds `DOSE-DISTINCT`** — the four
   dosed legs must produce four *different* action sequences. A build that clamped, rounded or
   bucketed the dose would pass a per-dose positive check and still flatten the ladder into one
   measurement repeated four times, with four healthy manifests and four distinct claimed bands (§9).
2. ⭐ **The launcher probes every rung dose** before spending anything: it asserts `fpu=Some(0.05)`,
   `Some(0.1)`, `Some(0.15)` and `Some(0.3)` in `repr(SearchConfigRs)` from *this box's* source.
3. ⭐ **`G-FPU` and `G-TWOSIDED`** read the request and the two sides' resolved configs
   (`READ_RULE` §4).

⚠️ None of these can tell you that `0.05` **matters**; they tell you it **binds**. A rung whose dose
binds and whose effect is nil is a real, reportable `R-BOUNDED`.

### 2.3 ⚠️ THE TIE ARBITER IS OFF, AND THAT IS A DEVIATION FROM THE DEPLOYED CHAMPION

`governance/PRODUCTION.yaml` has carried `tiearb B=64` since 2026-08-20. It is **disabled on both
sides here**, exactly as in the parent round. The reason: the arbiter is a **stochastic post-search
root hook** that fires on exact ties and runs CRN determinization playouts. Leaving it on would inject
fire-driven variance on both sides, orthogonal to the dose under test — and it interacts with the
search's visit distribution, which is precisely what FPU changes, so an armed arbiter would confound
the mechanism rather than merely add noise.

⛔ **The price rides on every branch:** every reading here is about the **arbiter-free** champion.
Transfer to the deployed `B=64` one is an **assumption**, and **step 2 of the adoption chain
(`screen_lib.ADOPTION_CHAIN`) is the leg that prices it**: a production H2H with the arbiter armed, on
a fresh band. `run_cells.sh` contains no `--cand-tiearb-*` flag anywhere, by construction, and
`G-ARB-OFF` walks the whole manifest to prove nothing armed it.

### 2.4 ⛔ Single-variable discipline

Every rung changes **exactly one** knob, and in this round it is the same knob on every rung. So:

- `G-SINGLEVAR` asserts `fpu_reduction` **DIFFERS** across the two sides and equals the frozen dose on
  the candidate, and that **every other** alias (`c_puct`, `tau_p`, the three budget fields,
  `value_norm`, `leaf_quantize`, `final_select`) is **EQUAL**.
- ⭐ `G-FPU` **additionally** asserts `config.cand_search.c_puct` is `null` on every rung — the
  request side and the resolved side are different bugs, and both get a witness.
- ⛔ `run_cells.sh` carries **no** `--cand-c-puct`, **no** `--c-puct` and **no** `--tau-p`. The last
  two are the **shared** flags: they build `champ_cfg_dict`, which `_make_opponent` feeds through the
  *same* `_cfg_from_dict`, so they move **both sides** and a rung built on one is
  champion-vs-champion.

---

## 3. SIZING, POWER, AND THE PRICE OF THE BAR

The sizing constant is carried unchanged from the parent round (which carried it from the Stage-2
Phase B cell `ARB`): `sigma_D = 13.81 pts/deck`, so `se_model(400) = 0.6905`.

⭐ **It is now corroborated rather than merely inherited.** The parent round realized three siblings
at exactly this shape — `n ≈ 400` decks, 22016 both sides, arbiter off — with `se` `0.6826` / `0.7153`
/ `0.6511`, i.e. `sigma_D` `13.65` / `14.29` / `13.02`. The carried `13.81` sits inside that spread.

⛔ **POWER ARITHMETIC ONLY.** `READ_RULE` §1: `sigma_D` is never a denominator in a branch test —
every branch is adjudicated at the rung's **own realized SE**.

### 3.1 ⛔⛔ THE READ DISTRIBUTION — WHAT `+1.5` COSTS, COMPUTED NOT ASSERTED

`screen_lib.read_distribution(delta, se)` computes these and `sanity_check()` asserts them, so the
round cannot quietly improve its own advertised odds:

| true effect `δ` | `R-ADOPT` | `R-BOUNDED` | `R-NEGATIVE` | `R-UNRESOLVED` | `P(LADDER-DEAD)` if all four rungs are at `δ` |
|---|---:|---:|---:|---:|---:|
| **0 (true null)** | 0.0015 % | 54.6 % | 2.28 % | **43.2 %** | **10.4 %** |
| **+1.5 (at the bar)** | 2.28 % | 2.27 % | ~0 % | **95.4 %** | ~0 % |
| **+2.951 (incumbent repeat)** | **54.1 %** | ~0 % | ~0 % | 45.9 % | ~0 % |

Read that table honestly:

- ⛔ **The round's most likely single outcome under a true global null is `LADDER-UNRESOLVED`**
  (~90 % chance at least one rung lands there). That is not a failure of execution; it is what a
  demanding `LB95` bar at `n=400` buys.
- ⛔ **A true effect exactly at the bar is essentially unresolvable here** (95 % unresolved). The bar
  is a *decision* threshold, not a detection threshold, and `n` was not sized to detect it.
- ⭐ **What the round CAN do well is fire on a large effect without ever firing on noise.** A rung
  that adopts has cleared `LB95 >= +1.5` — no point-estimate spike gets there.

### 3.2 ⛔ THE `n` THIS BAR WOULD ACTUALLY NEED, STATED PLAINLY

| goal | decks/rung | games/rung | round games | vs funded |
|---|---:|---:|---:|---:|
| **funded** | 400 | 800 | 3,200 | 1× |
| adopt a repeat of `+2.951` at 80 % power | **732** | 1,464 | 5,856 | 1.8× |
| `LADDER-DEAD` at 80 % under a true null | **1,102** | 2,204 | 8,816 | **2.8×** |

⭐ This is exactly the "size `n` to resolve THAT" half of the house rule, and the honest answer is
**this round cannot afford it**. `READ_RULE` §8 repeats the table and §8.2 pre-commits the price of
an unresolved read, so the option of buying more `n` after seeing the sign — the `rodv3` failure mode
— is closed before game 1.

### 3.3 The secondary

**Primary: the deck-paired margin**, `D(deck) = (diff(a_seat=0) + diff(a_seat=1)) / 2`, in POINTS,
candidate minus opponent. `M > 0` ⇒ the candidate won. It carries every branch.

**Secondary: elo**, reported beside it with its own **deck-paired** CI (R4) on every branch. ⚠️ In
this round the elo is **not a bar at all**: `+1.5 pts/deck` has no exchange rate into elo that this
round measures. The instrument's own 2σ elo resolution (`±17.4`, deck-paired at 800 games) is printed
as a **resolution**, and ⭐ **a disagreement between the margin and the elo is DISCLOSED, never
arbitrated.**

---

## 4. THE CONTEXT ROWS

### 4.1 The realized `0.2` and `0.4`, stated before game 1

| dose | band | `M` | `se` | `z` | `LB95` | `UB95` | `n_paired` | elo (paired CI) | read |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| **0.2** | `155e9` | **+2.951** | 0.683 | **+4.32** | **+1.586** | +4.316 | 400 | +26.1 `[+8.7, +43.5]` | `F-RESURRECT` |
| **0.4** | `156e9` | +0.754 | 0.715 | +1.05 | −0.676 | +2.185 | 399 | −1.7 `[−19.1, +15.6]` | `F-UNRESOLVED` (amended, FPU-A1) |

### 4.2 ⛔⛔ THEY ARE CONTEXT AND NOTHING ELSE

**NEVER POOLED. NEVER z-COMBINED. NEVER A BRANCH INPUT. NEVER INTERPOLATED AGAINST A RUNG.** Every
contrast between one of these and a rung of this round is **cross-band**, and CL-068 measured
**1.8–2.2× over-dispersion** on exactly that class — in *both* the elo and the deck-paired-margin
statistics, with an identity control exonerating the harness and the "different decks" explanation
arithmetically excluded because the per-deck SEM already prices the deck draw.

⭐ What they legitimately did is a **design act, spent before any number of this round exists**: they
fixed **which doses** to ask about, and **what bar is worth paying for**. `0.2`'s own realized `LB95`
was `+1.586`, so a `+1.5` bar asks a new rung to be **at least as good as what we already hold** —
and, narrowly, the incumbent itself would clear it (by `+0.086 pts/deck`). `screen_lib.sanity_check()`
asserts that property so the bar cannot drift away from it.

### 4.3 The axis's older history

`docs/LEVER_INDEX.md:146` recorded FPU as **CLOSED** on neural / value-blended evidence
(`+45.4` / `+31.4` elo screens at `n=200`, never confirmed; the M3 curve peaking at parity). The
parent round reopened it narrowly — none of that evidence could have measured the classical champion,
because the knob was unreachable on its backend — and its `0.2` cell fired. ⛔ Those figures are
**cross-era as well as cross-band**, which is strictly worse than cross-band alone, and they enter no
arithmetic here.

---

## 5. THE BANDS — FOUR, ONE PER RUNG

⭐ **PROPOSED: `164000000000`, `165000000000`, `166000000000`, `167000000000`.** ⛔ Not claimed, not
registered, not appended to `governance/BAND_REGISTRY.csv` at this commit.

- Highest **registered** id is `161000000000` (S1 gate G3, 2026-08-30). ⚠️ `162e9` and `163e9` are
  **RESERVED** by that round (they appear in `measurement/s1_asymmetry_prep/BAND_CLAIM_G3.json` and
  `tests/test_s1_g3_instrument.py` but carry no registry row) — **not taken**. This ladder starts at
  the next monotone id above the reservation.
- **Tree sweep, 2026-08-30: 0 references** to any of the four. Method and the full result set are in
  [`BAND_CLAIM.json`](BAND_CLAIM.json).
- ⚠️⚠️ **`146000000000` IS THE TRAP THE CLAIM ORDER EXISTS FOR** — absent from the registry but
  carrying references in the tree. The registry is **necessary and not sufficient**; the **tree sweep
  is the binding check** and is re-run immediately before the CSV append.
- ⭐ `158e9` and `160e9` remain **DROPPED** (0 registry rows, live tree hits), carried forward from
  the parent round's sweep so the next reader does not rediscover them as "free".

### 5.1 ⚠️ THE SWEEP METHOD CHANGED MID-BUILD, AND BOTH HALVES ARE RECORDED

The first attempt ran **one full-tree `grep -rIl` per candidate band**. The `measurement/` artefact
tree is multi-GB, so that thrashed the disk at ~170 MB/s per pass and **the owner stopped it**. The
final method is **one combined pass** — `git grep` over tracked files (packed objects, near-zero
filesystem IO) plus exactly one filesystem pass over `git ls-files --others` — with per-band
classification done against the few hit files. Every band was **re-verified under the final method**
so all four share one method. ⛔ Do not run per-band full-tree greps in a future round.

⭐ **AND ONE REFINEMENT OF THE REFUSAL RULE, RECORDED SO THE NEXT READER DOES NOT REDISCOVER IT.**
The abandoned substring sweep reported hits for **every** id in `164e9..169e9` — all of them inside
`measurement/value_resurrection_pilot/data/leaf_audit_rows.jsonl`, all of them **float mantissa
tails** (`"regret": 0.006164000000000003` contains `164000000000`). A naive substring rule would
refuse every band in this range forever. **The refusal rule stands; what is refined is what counts as
a reference:** a band id is an **integer deck seed**, so a digit run straddling a decimal point cannot
be one. A boundary-aware read returns **zero** for all four bands.

### 5.2 Why four bands and not one shared deck set

Nothing in this round is pooled or deck-matched across rungs: four independent questions, four
independent primaries, each its own margin against zero. A shared deck set (the S1 G3 pattern) would
buy **no** deck-matching that any gate reads, and would spend **one** band's `decision_influenced`
retirement on **four** verdicts. Four bands keep every *primary* within-band — the only robust class
under CL-068 — and retire cleanly.

⛔ **The price, disclosed:** every rung-vs-rung contrast is cross-band. §1.2 and `READ_RULE` §5.3
carry it.

**Throwaway sub-range: `167999999000`+** (the §9.3 smoke). ⛔ Never in any claim.

---

## 6. COST AND ETA — FROM REALIZED RATES, AND THE BRIEF'S ESTIMATE IS WRONG

⭐ **Anchored on realized cells at exactly this budget** (`k16 × 1376 = 22016`, arbiter off, rust,
`exact_k 2` marginalized), read off the archives' own file timestamps:

| realized reference | box | W | games | wall | games/h |
|---|---|---:|---:|---:|---:|
| `fpu_resurrection/CELL_FPU02` | local | 30 | 800 | 4.72 h | 169.5 |
| `fpu_resurrection/CELL_FPU04` | local | 30 | 799 | 4.62 h | 172.9 |
| `fpu_resurrection/CELL_CPUCT10` | laptop | 22 | 800 | 4.90 h | 163.3 |
| `s1_g3/CELL_G3_OPP` (live, in progress) | local | **14** | 107 | 0.89 h | **≈ 120–135** |
| `s1_g3/CELL_G3_OWN` (live, in progress) | laptop | 22 | 137 | 0.89 h | ≈ 154–176 |

⚠️ The two live rows are read **from process start**, not from first completion —
`feedback_eta_before_launch`'s order-statistic trap: the first completions of a parallel run are the
fastest and a rate derived from them is inflated. They are also a **jrules-armed** cell, so they are
if anything slightly pessimistic for this round.

**The figures this round is priced at:** **local `W14` ≈ 125 games/h**, **laptop `W22` ≈ 160 games/h**.

```
local   800 games / 125 = 6.4 h per rung
laptop  800 games / 160 = 5.0 h per rung
```

| split | local wall | laptop wall | **round wall** |
|---|---:|---:|---:|
| 1 local + 3 laptop | 6.4 h | 15.0 h | 15.0 h |
| **2 local + 2 laptop (TAKEN)** | **12.8 h** | 10.0 h | **12.8 h** |
| 3 local + 1 laptop | 19.2 h | 5.0 h | 19.2 h |

⭐ **`2 + 2` is the shortest wall a whole-rung assignment admits** — the ideal fractional split is
`125/(125+160) = 44 %` local ≈ 1.75 rungs, and 2 rounds to the better of the two feasible integers.
The residual **≈ 2.8 h laptop idle** is DISCLOSED, not engineered away.

**Core-hours: ≈ 399 worker-h** (local `14 × 12.8 = 179`; laptop `22 × 10.0 = 220`).

### 6.1 ⛔⛔ THE BRIEF'S "~5.5–6 h" IS OFF BY ~2×, AND HERE IS WHY

The funding brief priced a rung at "≈ 2.6 box-h at W30-era rates". The realized W30 figure is
**4.7 h** per 800-game rung, not 2.6 — the brief's number predates the `11008 → 22016` budget
promotion in per-game cost. Correcting that alone doubles the estimate; the owner's `W_LOCAL 30 → 14`
ruling then adds the rest. ⚠️ `feedback_verify_numbers_before_reporting` binds: this section is built
only from numbers read off disk.

### 6.2 The one lever that would change it — and it is the owner's, not the measurement's

`W_LOCAL = 14` is the **owner's ruling of 2026-08-30** (interactive-use constraint on his own
desktop; commit `56cabcbf`). At the pre-ruling `W_LOCAL = 30` the local box realized **≈ 170 games/h**
and the round would be:

```
local  1600 / 170 = 9.4 h      laptop 1600 / 160 = 10.0 h     round wall = 10.0 h
```

— a saving of **≈ 2.8 h**, with the laptop then the binding box. ⚠️ **`W` IS THROUGHPUT-ONLY:** games
are bit-identical at any `W` and **no gate in this pair reads a clock**, so raising it changes no bar,
no branch and no number. ⛔ It is still not taken here: it is a decision about the owner's desktop
during his own waking hours, and the pair does not make it. If the round launches at ~02:00 as
planned, the orchestrator may put the question to the owner; absent an answer, `W_LOCAL = 14` stands.

### 6.3 ⛔ The sub-rung split, considered and NOT taken

Splitting each rung into `_L`/`_R` halves across both boxes would balance perfectly:
`3200 / (125 + 160) = 11.2 h`, a saving of ~1.6 h (12 %). ⛔ **Not taken**, for the same reason the
parent round declined it: it needs a `G-SUBPOOL` gate and a **pooled primary**, which is a strictly
more complicated object to adjudicate, for a 12 % wall-clock saving. The brief specified whole rungs.

---

## 7. THE INSTRUMENT — what was forked, what was rewritten

`screen_lib.py` is a fork of `measurement/fpu_resurrection_prep/screen_lib.py` (itself a fork of
phasegate's). **Carried verbatim in construction:** `cross_box_rev_gate` (the IS-A1 fold),
`rev_matches`, `is_hex40`, `host_matches_box`, `paired_margin`, `winrate_elo` **with R4's deck-paired
elo footing**, `recon_close`, `resolve`/`gate`, `se_anomaly`, `arb_off_gate`, `twosided_gate`,
`leaf_gate`.

### 7.1 ⛔ REWRITTEN, and why a copy would have been wrong

| gate / object | the parent's version | here |
|---|---|---|
| **the bars** | `BAR_M = 1.381` = exactly `2·se_model(400)` | ⭐⭐ `BAR_EFFECT = 1.5`, an **effect size**, read on `LB95` for adoption and `UB95` for the bound. `sanity_check()` asserts the bar has **NOT** collapsed onto `2σ̂` — the inverse of the parent's own assert |
| **`G-N`** | condition column `n == 800, n_failed == 0` (its own notes said sub-2 % is *reported*) | ⭐⭐ **the prose IS the condition**: the 2 % bar, the 80 % floor, and an explicit **accounting identity** `n + n_failed == n_games` |
| **`G-DECKS`** | `n_common == 400` exactly | ⭐⭐ `n_common >= 80 %`, one-seat-only decks **REPORTED** below the 2 % bar. Out-of-range seeds and band-range intersection stay **hard** fails |
| **`G-CPUCT`** | a whole gate, for the `c_puct` cell | **deleted** — no rung varies `c_puct`. ⭐ But `G-FPU` now asserts the override is `null` on every rung |
| **`tau_trigger` / `TAU_PAIR_SPEC`** | the funded conditionality | **deleted** — the parent's `c_puct` cell read `F-REKILL` and dissolved τ |
| **the round verdict** | none (three independent questions) | ⭐⭐ **new**: `LADDER-DEAD` / `LADDER-LIVE` / `LADDER-UNRESOLVED` / `LADDER-VOID`, computed in `screen_lib.round_verdict` so it cannot be re-read favourably |
| **the golden gate** | `FPU_BITEXACT.json`, 3 legs, one positive control at `0.2` | ⭐⭐ **6 legs, a positive control PER RUNG, plus `DOSE-DISTINCT`**, and the wheel **stamped** so the launcher can refuse a mismatched one (§9) |

### 7.2 ⭐⭐ `G-N` AND `G-DECKS` — THE `FPU-A1` FIX, AND IT IS THE MOST IMPORTANT CARRIED FIX

The parent round's `FPU04` cell was **VOIDED** by its own adjudicator over **one** deterministic
`WindowTruncationError` — `1/800 = 0.125 %`, an order of magnitude below the 2 % void bar its own
frozen prose set. `AMENDMENTS.md` FPU-A1 had to amend the verdict **with the statistics already
visible**, which is a position no round should be in. The cause was a **condition column stricter
than the prose beside it**.

Here the prose *is* the implementation, in both gates, with **one shared denominator**:

- ⭐ **the denominator is GAMES, not decks**, in both gates. A deck played at one seat only **is**
  exactly one failed game, so `G-DECKS`' one-seat-only rate and `G-N`'s `n_failed / n_games` are the
  **same quantity read off two different documents** (raw records vs `summary.json`) — which is the
  whole point of having both. ⚠️ The first draft of `decks_gate` used a *decks* denominator; the two
  gates then disagreed by a factor of two on the same archive, one voiding while the other reported.
  **Caught in build, before game 1**, by the selftest that checks both sides of the bar.
- `< 2 %` ⇒ **REPORTED, never silently absorbed** (the `b32v64` 0.100 % rust-panic precedent), and the
  rung still READS.
- `>= 2 %` ⇒ the rung **VOIDS**, on both gates.
- `n_common >= 80 %` of the frozen decks — a **fraction**, never an equality. ⚠️ It is a **backstop**:
  at 400 decks the 80 % floor allows 80 lost decks while the 2 % bar voids at 16 games, so the 2 % bar
  is the operative one.
- ⛔ **the accounting identity is NOT absorbed by the bar.** Games that vanished *without* being
  recorded as failures mean the denominator is unknown, which is a strictly worse defect than a
  recorded failure.

`analyze_ladder.py --selftest` tests **both directions at the frozen 400-deck scale** (15/800 = 1.875 %
must READ; 16/800 = 2.000 % must VOID), because the shipped 12-deck fixture cannot express a sub-2 %
whole number of failures and a test that could not express it would be a test of nothing.

### 7.3 ⭐ Carried launcher/adjudicator fixes from the parent's pre-launch merge review

- **R1 — the smoke adjudicates its own `SMOKE_` dir from the EMITTED manifest**, and **exits non-zero
  on zero cells or an empty knob**, so `run_cells.sh`'s `|| DIE` is reachable. The parent's original
  `--smoke-mode` produced `"cells": {}` and exited 0; the identical defect is realized in phasegate's
  banked `SMOKE_local.json`.
- **R2 — test import isolation by explicit path.** Three sibling rounds now ship a module named
  `screen_lib`; `tests/test_fpu_ladder_instrument.py` loads this one as `fpu_ladder_screen_lib` via
  `importlib.util.spec_from_file_location` and pins that it is not any sibling's fork.
- **R4 — the paired elo CI.** `winrate_elo` emits `elo_sig_1sigma_paired` and
  `elo_sig_1sigma_unpaired`; the unlabelled key is gone on purpose.
- **The provenance ladder** — `BLIND_COMMIT=PENDING`, the `BAND_CLAIMED` sentinel, per-box
  `PINNED_SRC_REV`, and `assert_rev` **before and after every rung** including the dirty-code-path
  check over `src engine scripts rust tests`.

---

## 8. PRE-LAUNCH ACTS — the executor's checklist

1. **Merge** the build branch; **bundle-sync** every box to the launch `HEAD`
   (`reference_offline_git_bundle_sync`). ⚠️⚠️ **This is the round's primary provenance risk:** the
   fpu plumbing is **python-only**, so a box on stale source serves a **dose-free candidate** with a
   healthy wheel, a healthy `carc_rs_build` and the correct leaf hash.
2. `git -C <repo> rev-parse HEAD > measurement/fpu_ladder_prep/PINNED_SRC_REV` **on each box, after
   its sync**. ⛔ Never committed (`.gitignore`).
3. **Stamp `BLIND_COMMIT`** — a follow-up commit writes the freeze commit's 40-hex sha into
   `WORKERS.conf`. A commit cannot name its own hash.
4. ⭐⭐ **Run the golden gate ON EACH BOX**: `golden_gate/run_golden_gate.sh`. It must produce
   `FPU_BITEXACT_LADDER.json` = `PASS` carrying *that box's* `carc_rs_binary_sha` (§9).
5. **Claim the four bands**: re-run the tree sweep **with the combined method**, then append the four
   rows from `BAND_CLAIM.json::_csv_rows` to `governance/BAND_REGISTRY.csv`, **then** drop
   `BAND_CLAIMED`. ⚠️ In that order — `146e9` is the trap it exists for.
6. **Smoke each box** (§9.3) and **read `SMOKE_<role>.json` by hand**.
7. Launch detached, `nice -n 19`, whole rungs per box.

`run_cells.sh` enforces 2–6 mechanically and refuses without them.

⚠️ **`--dry-run` is exempt from `G-PROD` and from the golden gate** (loud, not fatal) — it spends no
compute, no band and no blindness, and its purpose is to show the **emitted argv** before anything has
run, which at build time is necessarily before the gate exists. ⛔ **`--smoke` is exempt from
neither**: it is real play, on the real wheel, on the real code path, and it is the last thing that
happens before the round. ⚠️ Both still require `PINNED_SRC_REV` — act 2 above — so run a `--dry-run`
*after* the sync, not before it.

---

## 9. ⭐⭐ THE GOLDEN GATE — OWED, NOT INHERITED

### 9.1 The inheritance question, and the answer

[`../fpu_resurrection_prep/FPU_BITEXACT.json`](../fpu_resurrection_prep/FPU_BITEXACT.json) reads
`PASS`. Its `ONE-WHEEL` check binds all three of its legs to `carc_rs` binary **`f6316d42838574de`**.
Since then:

- the S1 **`R7`/`R6`** merge (commit `316df67d`, 2026-08-30) changed `carc_core::search` — adding
  `search::JrExpansions` and `search::carried_scope_guard` — and changed the **signature and body of
  `fair::search_worlds`**, which is the PIMC descent every rung of this round plays on;
- the installed binary has moved **twice**: the parent round's own cells ran on `5c53dd8b3085ab4a`,
  and the current build is `2ef38b5123514fc9` (`carc_rs-0.1.0+ec0e52bb7b7e`).

⛔ **THE INHERITANCE IS THEREFORE NOT VALID, AND A FRESH 20-GAME BIT-EXACT RUN IS OWED.** The R7
counters live inside the `jrules_prior_dose != 0.0` branch and are **argued** to be play-neutral on
champion traffic. That argument is very probably right. It is also **exactly the class of claim the
hard-coded `None` satisfied** — a healthy-looking config echo with no play-derived witness — and this
entire family of rounds exists because that argument was wrong once already. `README`-level
reassurance is not a golden gate.

### 9.2 What the new gate proves (`golden_gate/`, BUILT AND NOT RUN)

Six legs of `identity_leg.py`, 20 frozen seeded self-play games each (`k2 × 96`), adjudicated by
`ladder_diff.py` into `FPU_BITEXACT_LADDER.json`:

| leg | tree | `fpu` |
|---|---|---|
| `OLD` | `git archive` of the **pre-plumbing** commit (`a369f437^`, discovered at run time and **verified** to carry no `fpu_reduction` field) | unset |
| `NEW` | the launch tree | unset |
| `CTRL_005` / `CTRL_010` / `CTRL_015` / `CTRL_030` | the launch tree | **0.05 / 0.1 / 0.15 / 0.3** |

- ⭐ **`IDENTITY`** — `OLD == NEW`. The plumbing does not move the champion's play by one action **on
  the wheel this round will play**.
- ⭐⭐ **`POSITIVE-<dose>`, one per rung** — each dosed leg differs from `NEW`. ⛔ Without these
  `IDENTITY` is worth nothing.
- ⭐⭐ **`DOSE-DISTINCT`** — **NEW IN THIS ROUND, and it is the check a ladder specifically needs.**
  The four dosed legs must differ **from each other**. A build that clamped, rounded or bucketed the
  dose would pass every `POSITIVE-*` and still flatten the ladder into one measurement repeated four
  times — four healthy manifests, four healthy winrates, four distinct claimed bands.
- **`RUNG-SET`** — every frozen dose has a control leg.
- ⭐⭐ **`ONE-WHEEL`** — all six legs on one binary sha, which is then **stamped into the artefact**.
  `run_cells.sh` refuses unless that sha equals the launching box's own installed binary.
- **`TWO-TREES`**, **`SAME-SEEDS`**, **`SAME-BUDGET`**, **`AUDIT-ADJUDICATED`** — as in the parent.

⚠️ **THE GATE IS BOX-LOCAL.** `carc_rs_binary_sha` differs between boxes compiling identical source,
so **each box runs its own**, exactly as `G-WHEEL-SAME` is asserted per box.

⚠️ **What it does NOT prove:** that the wheel move was play-neutral. Comparing this round's champion
play to the parent's would need the *old binary* rebuilt, and this gate deliberately does not attempt
it. What it does instead is make the wheel a **constant of this round**: every rung and its own
opponent play the same binary. ⛔ Cross-round comparisons against the parent's `0.2` / `0.4` numbers
were already forbidden by CL-068; the wheel move is one more reason.

⛔ **It is a code-path gate at a tiny budget and NO number in it is a strength measurement.**

### 9.3 The smoke — 8 games per box, throwaway range, production knobs

⛔ **Emits no outcome key.** Its one substantive job beyond liveness: it drives the **real argparse**
and the adjudicator reads the **resolved dose back out of the emitted `manifest.json`** — the
PG-D7…D9 lesson, where three separate launcher defects (an ambiguous `--out`, a silently-defaulted
`walled` rules profile, and a **missing `--paired`** that would have zeroed `n_paired` on every cell)
all survived review and were caught only by a smoke adjudicated against emitted output.

⚠️ **The local box smokes `0.05` and the laptop smokes `0.30`** — the ladder's two extremes, each on a
box that will actually run that dose. `0.05` is the load-bearing one (§2.2).

---

## 10. WHAT THIS ROUND DOES NOT DO

- ⛔ It does not touch `governance/PRODUCTION.yaml` on any branch.
- ⛔ It does not re-run `0.2` or `0.4`, and does not confirm either.
- ⛔ It does not draw a dose-response curve (§1.2) or locate an optimum.
- ⛔ It says nothing about the arbiter-armed champion (§2.3) — that is step 2 of the adoption chain.
- ⛔ It does not measure the owner-hole. No branch touches `measurement/e4_games/`.
- ⛔ It does not pool anything, across rungs or with the context rows.
