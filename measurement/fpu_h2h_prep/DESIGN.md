# FPU PRODUCTION-H2H — PRICING THE DEPLOYED CONFIGURATION — DESIGN

> **STATUS: FROZEN** (2026-08-31). This document and [`READ_RULE.md`](READ_RULE.md) are **the pair**,
> and the pair is law. ⛔ **NOTHING IN EITHER FILE MOVES AFTER THE BLIND COMMIT.**
>
> ⛔ **0 games have been played at this commit. No band is claimed at this commit.** The instrument
> exists and `analyze_h2h.py --selftest` is `PASS`.
>
> ⛔⛔ **`W_LAPTOP` IS DELIBERATELY UNSET (`TBD_FROM_SWEEP`).** A laptop `W` sweep was live while this
> was built. `run_cells.sh` REFUSES everything — including `--dry-run` and `--smoke` — until the
> orchestrator stamps the swept value. ⭐ **§6 gives the ETA as a FORMULA in `W`** precisely so that
> number can be filled in last and nothing else in the pair moves with it.
>
> ⚠️ **THE GOLDEN GATE IS INHERITED, NOT REBUILT — AND THE ARGUMENT IS IN §9, NOT ASSUMED.** Two gaps
> in the inherited certificate are NAMED there and are paid by the `--smoke` IDENT legs (§9.3).
>
> ⚠️ **THIS ROUND IS OWNER-FUNDED, NOT TRIGGER-FIRED.** The dose ladder read `LADDER-UNRESOLVED`, and
> its own `READ_RULE` §8.3 is explicit that `LADDER-UNRESOLVED` does **not** discharge the incumbent's
> confirmation leg the way `LADDER-DEAD` would. `feedback_execute_prereg_triggers` therefore does
> **not** apply here: no pre-registered branch authorised this. The owner did. §0.2 says so in full.

---

## 0. THE ONE-PARAGRAPH VERSION

`fpu_reduction = 0.2` is the only dose that has ever fired on the classical champion
(`+2.951 ± 0.683 pts/deck`, `z +4.32`, `n=400` deck-paired, band `155e9` — the
[`fpu_resurrection`](../fpu_resurrection_prep/DESIGN.md) round, `F-RESURRECT`). The
[dose ladder](../fpu_ladder_prep/DESIGN.md) that tried to bracket it read **`LADDER-UNRESOLVED`**
(`0.05` bounded; `0.10 / 0.15 / 0.30` unresolved; none adopted). ⛔⛔ **EVERY ONE OF THOSE SIX
READINGS RAN WITH THE TIE ARBITER OFF ON BOTH SIDES**, while `governance/PRODUCTION.yaml` has carried
`tiearb B=64` since 2026-08-20. Both prior rounds' `READ_RULE`s name that as an **unpriced
assumption** and name **step 2 of `ADOPTION_CHAIN`** as the leg that prices it. This round is that
leg: **ONE cell, `n=800` games (400 seat-balanced decks × 2 seatings), on the fresh band `168e9`,
candidate = the DEPLOYED champion (`k16×1376 = 22016` + the deployed arbiter) **plus** the dose;
opponent = **the same deployed agent without the dose**. ⭐⭐ **THE ARBITER IS ARMED ON BOTH SEATS AT
THE FULL DEPLOYED SPEC.** That sentence could not have been written before 2026-08-31 (§2.3), and it
is what makes the single variable *the knob* rather than *the knob and the arbiter together*.

### 0.1 ⭐⭐ THE BAR IS AN EFFECT SIZE — AND IT IS THE **CONFIRMATION** BAR, `+1.0`

The owner ruled on 2026-08-30 ("effect size sounds right"), and it is now a standing rule in
`CLAUDE.md`:

> **BARS ARE SET AT THE EFFECT SIZE THE DECISION CARES ABOUT — NEVER AT `2σ̂` OF THE INSTRUMENT.** …
> Write the prereg bar from "what effect would change the decision", size `n` to resolve THAT, and if
> the honest answer is "we can only afford the bounding direction," SAY SO in the READ_RULE including
> the null's expected read distribution.

`2·se_model(400) = 1.381`, and `screen_lib.sanity_check()` asserts `BAR_EFFECT` is **not** that
number. The bar is **`+1.0 pts/deck`**, read in two directions:

| branch | condition | what it means |
|---|---|---|
| **`H-ADOPT`** | `LB95(M) >= +1.0` | ⭐ licenses **PROPOSING** the `PRODUCTION.yaml` fpu flip **and** funding step 3 (Carcasum external). ⛔ **NEVER an automatic adoption.** |
| **`H-BOUNDED`** | `UB95(M) < +1.0` | ⭐ discharges step 2: the effect does **not** survive into the deployed configuration at the size the decision cares about |
| **`H-NEGATIVE`** | `M <= 0` **and** `z <= -2` | the dose is actively harmful with the arbiter live (checked first) |
| **`H-UNRESOLVED`** | everything else | ⛔ not a null and not a bound |

⭐ **WHY `+1.0` AND NOT THE LADDER'S `+1.5`, DERIVED AND NOT ASSERTED.** The ladder was a *screen*
over four unmeasured doses, and it set its bar so a new rung had to be **at least as good as the
incumbent** (`0.2`'s own realized `LB95` was `+1.586`). This round is the **confirmation leg of a dose
we already hold**, and the decision it feeds is *"is this worth proposing as a production flip?"*. The
honest reference for that is **what this program has actually accepted as a production fold**:

| fold | realized effect | `z` | `n` | outcome |
|---|---|---|---|---|
| **k16×1376 budget promotion** (2026-08-30, `h2h_22016_20260824`, band `148e9`) | **+1.229 pts/deck** | +2.52 | 700 decks | folded into `PRODUCTION.yaml` |
| **tie-arbiter `B=64`** (2026-08-20, `tiearb_widening/b64_cell`, band `139e9`) | **+1.7167 pts/game** | +2.656 | 750 decks | folded into `PRODUCTION.yaml` |

`+1.0 pts/deck` is at or below both, so a cell that clears it has produced an effect of the size this
program has **twice** judged worth deploying. `sanity_check()` asserts the bar is (a) strictly below
the ladder's `+1.5` screen bar and (b) no harder than the k16 fold's own realized `+1.229`.

⛔⛔ **AND THE LOWER BAR IS NOT FREE. §3.2 STATES WHAT IT COSTS, BEFORE GAME 1.** A lower bar makes
`H-ADOPT` easier and `H-BOUNDED` **harder**:

- under a **true null**, this cell reads **`H-UNRESOLVED` ≈ 70.9 %** of the time and `H-BOUNDED` only
  ≈ 26.8 % — where the ladder's higher bar gave ≈ 43 % / ≈ 55 %. ⛔ **The bounding direction is WEAK
  BY CONSTRUCTION here.**
- against a **repeat of the incumbent's `+2.951`**, the cell adopts **≈ 79.6 %** of the time — and
  `n_decks_for_adopt_power(2.951, 0.80) = 405`, so the funded **400 decks is, to within a deck,
  exactly the `n` the house rule asks for**. That is the one direction this round is properly sized
  for, and it is the direction the decision needs.
- against the **ladder's largest point estimate `+1.835`**, power is only **≈ 21.5 %**
  (`n` for 80 % would be **2,209 decks**). ⛔ This round cannot afford that and does not pretend to.
- a **true null false-adopts ≈ 0.03 %** of the time. ⭐ **The bar cannot fire on noise.**

### 0.2 ⚠️⚠️ WHAT FUNDED THIS ROUND — AND WHAT DID NOT

⛔ **`LADDER-UNRESOLVED` DID NOT.** The ladder's `READ_RULE` §8.3 pre-committed, before its game 1,
that an unresolved ladder may **not** be read as if it were `LADDER-DEAD`, and that only
`LADDER-DEAD` makes the incumbent's confirmation leg *proposable*. That pre-commitment stands and is
not being quietly walked back here.

⭐ **THE OWNER FUNDED IT**, holding this prereg pending launch, on the shape of what the ladder
actually produced: three of its four rungs carried positive point estimates, the curve peaked at the
incumbent, and none of it says anything at all about the configuration that ships. ⭐ The strongest
argument for the round is not the ladder's numbers — it is that **an unpriced deviation sits under
every fpu reading this program owns**, and pricing it is worth `n=400` regardless of which way it
reads. A `H-BOUNDED` here is as useful as an `H-ADOPT`: it closes the axis at the deployed
configuration.

⛔ **NOTHING IN THIS ROUND IS AN AMENDMENT TO THE LADDER.** Its verdict, bands and read-rule are
spent and frozen.

---

## 1. WHAT IS BEING ASKED

**In the configuration that actually ships — champion budget `22016`, tie arbiter `B=64` live on both
sides — is `fpu_reduction = 0.2` worth at least `+1.0 pts/deck`?**

⚠️ It is a **strength** question, judge-free, decided by game outcomes. `feedback_evloss_grader`'s F4
lesson binds on any temptation to grade it with a judge: judged headroom is family-relative, and a
`+1.49` in-family ceiling read `−0.64` at `z −3.8` out-of-family on the same CRN worlds. Game
outcomes outrank any judged number and this round uses nothing else.

### 1.1 The mechanism, restated — and why the arbiter is not neutral to it

The champion's priors are a **heuristic softmax over Δleaf** at `τ_p = 5`, deliberately flat. A flat
prior plus the legacy optimistic FPU (`q = 0` for every unvisited child) makes the search spend visits
**breadth-first** across a wide root. A pessimistic FPU (`q = parent.Q − r`) makes an unexplored
sibling look *worse* than the parent's current estimate, concentrating visits on children the priors
already like.

⭐⭐ **THE TIE ARBITER IS A POST-SEARCH ROOT HOOK THAT FIRES ON EXACT TIES**, playing `B=64` CRN
determinization worlds per tied arm (capped at `J=4` arms) and argmaxing the mean. The realized rate
on champion traffic is ~20 fires/game over ~35 tile plies, changing the pick on **~46 %** of the plies
it fires on (measured, the 2026-08-31 wiring smoke). ⛔ **So the two surfaces are not orthogonal in
principle: FPU changes the visit distribution, the visit distribution decides which root ties are
REACHED, and the arbiter is what happens at a tie.** That is precisely why the arbiter-off readings do
not transfer for free, and precisely why this leg exists rather than being waved through.

⚠️ It is also why `H-NEGATIVE` is a real branch and not a formality: an interaction with the wrong
sign is a live mechanism, and no arbiter-off cell could have produced it.

---

## 2. THE CELL

| cell | box | knob | dose | band | n |
|---|---|---|---|---|---|
| `CELL_H2H_FPU02` | **laptop** | `fpu_reduction` | **0.2** | `168000000000` | 400 decks × 2 = 800 games |

Both sides:

- fair PIMC **`k16 × 1376 = 22016`** — the 2026-08-30 promoted desktop champion
- ⭐⭐ **tie arbiter ARMED, BOTH SEATS**: `B=64, J=4, mode=argmax, salt=tiearb2-deploy-v1, eps=0.0,
  phase_gate=all` — the full deployed spec (§2.2)
- `rules_profile = fixed_v1`, `CARCASSONNE_FIX_R9=1` (env-latched at import)
- `exact_k = 2`, mode `marginalized`
- backend `rust` — ⛔ **not optional**: the arbiter is RUST-ONLY and the harness refuses
  `--{cand,opp}-tiearb-enabled` on python, so a python leg could not arm either seat and would
  silently be the arbiter-off cell this round exists to stop being
- leaf `a36d2e15a3b3d71d` (curve125) — **the same leaf on both sides**; neither the dose nor the
  arbiter is a leaf term
- the knob on the **candidate only**, via `--cand-fpu-reduction`

⛔ **LAPTOP ONLY.** The owner holds the local box. `run_cells.sh` refuses `--role local` at launch
rather than letting `G-HOST` void the archive after ~7 h of compute, and `screen_lib` freezes
`role="laptop"` so the two cannot disagree.

### 2.1 Why `0.2` and not another dose

`0.2` is the **only dose that has ever fired** on the classical champion. `0.4` read `F-UNRESOLVED`;
the ladder's `0.05` read `R-BOUNDED` and its `0.10 / 0.15 / 0.30` read `R-UNRESOLVED`. ⛔ Re-running
a ladder rung here would be a second screen on a new band, not a confirmation of anything — and the
ladder's own `READ_RULE` §8.2 forbids extending an unresolved rung. **The confirmation leg confirms
the dose that fired.**

### 2.2 ⭐⭐ THE ARBITER IS ARMED ON BOTH SEATS, AND THAT IS THE ROUND

`governance/PRODUCTION.yaml` has carried `tiearb B=64` on the desktop deploy since 2026-08-20 (owner
ruling, "I'm buying b64"). Every fpu cell this program owns ran with it **off both sides**, for a
reason both prior rounds stated honestly: an armed arbiter injects fire-driven variance on both arms,
orthogonal to the knob under test — *and* interacts with the visit distribution, which is what FPU
moves. Turning it off made those rounds cleaner **and made their readings statements about an agent
that is not the one we ship.**

⛔ **THE PRICE RODE ON EVERY BRANCH OF BOTH ROUNDS, AND THIS LEG IS WHERE IT IS PAID.** The transfer
`B=0 → B=64` was an **assumption** there; here it is the measurement.

⚠️ **THE ARITHMETIC RUNS THE OTHER WAY NOW.** This cell says nothing about the arbiter-free champion,
and no reading here may be quoted back onto the `155e9` / `164–167e9` cells.

### 2.3 ⛔⛔ WHAT BECAME EXPRESSIBLE ON 2026-08-31 — AND WHAT THIS LEG WOULD HAVE BEEN WITHOUT IT

Until the morning of 2026-08-31 `eval_fair_puct.py` could arm the tie arbiter on the **candidate
only**: `_make_opponent` took no `tiearb` parameter, and `_cfg_from_dict` reads exactly five keys by
name and drops the rest, so the opponent seat was **structurally** disarmed. A wiring smoke run for
this very prereg found it, and the finding was blunt: **"ARB-ON both sides" was INEXPRESSIBLE, and a
naive launch would have shipped a CONFOUNDED arb+fpu cell claiming a single variable** — candidate =
champion + arb + fpu vs opponent = champion + neither.

The owner funded the plumbing the same day (`--opp-tiearb-*`, a second `GameResult` slot, opponent
telemetry off its own `FairAgentRs.stats()`, the manifest and summary shapes, and
`scripts/classical_search/tiearb_gates.py`). This round is built on the **clean** shape.

⛔⛔ **AND THE OLD GATE VOCABULARY WOULD FAIL THIS HEALTHY CELL.** `measurement/phasegate_prep/
READ_RULE.md`'s `G-TIEARB-ARM` requires *"Opponent: **no** tiearb container, **no** terminal
`*.tiearb_enabled` true"* — because while the seat was structurally disarmed, an armed opponent could
only be a defect. Running a healthy both-sides cell past that gate FAILS A GOOD CELL. ⛔ **Those
frozen prereg gates are NOT edited** (a frozen prereg keeps its frozen gates); this round cites the
**new** vocabulary — `tiearb_gates.assert_tiearb_sides` — and `screen_lib` says so at the point of
use.

### 2.4 ⛔ Single-variable discipline

The cell changes **exactly one** thing:

- `G-SINGLEVAR` asserts `fpu_reduction` **DIFFERS** across the two sides and equals `0.2` on the
  candidate, and that **every other** alias (`c_puct`, `tau_p`, the three budget fields, `value_norm`,
  `leaf_quantize`, `final_select`) is **EQUAL**.
- ⭐ `G-FPU` **additionally** asserts `config.cand_search.c_puct` is `null` — the request side and the
  resolved side are different bugs, and both get a witness.
- ⛔ `run_cells.sh` carries **no** `--cand-c-puct`, **no** `--c-puct` and **no** `--tau-p`. The last
  two are the **shared** flags: they build `champ_cfg_dict`, which `_make_opponent` feeds through the
  *same* `_cfg_from_dict`, so they move **both sides** and a cell built on one is
  champion-vs-champion.
- ⛔⛔ **THE `tiearb_*` TERMINALS ARE DELIBERATELY *NOT* IN `G-SINGLEVAR`'s ALIAS TABLE**, and that is
  a fact about the emitted manifest rather than a choice: the candidate stamps
  `config.champion.tiearb_*`, but the opponent **cannot** stamp them under
  `config.opponent.champ_cfg` (five keys by name). A `G-SINGLEVAR` clause over `tiearb_*` would read
  ABSENT on the opponent and **void every healthy cell**. The proposition *"both seats run the
  DEPLOYED arbiter"* is owned by `G-TIEARB-SIDES` (config, at the opponent's own addresses) and
  `G-TIEARB-FIRE` (play).

---

## 3. SIZING, POWER, AND THE PRICE OF THE BAR

The sizing constant is carried unchanged: `sigma_D = 13.81 pts/deck`, so `se_model(400) = 0.6905`.

⭐ **IT IS NOW CORROBORATED SEVEN TIMES**, at exactly this shape (`n ≈ 400` decks, `22016` both sides):

| sibling | realized `se` | implied `sigma_D` |
|---|---:|---:|
| `fpu_resurrection/CELL_FPU02` (b155e9) | 0.6826 | 13.65 |
| `fpu_resurrection/CELL_FPU04` (b156e9) | 0.7153 | 14.29 |
| `fpu_resurrection/CELL_CPUCT10` (b157e9) | 0.6511 | 13.02 |
| `fpu_ladder/CELL_FPU005` (b164e9) | 0.6952 | 13.90 |
| `fpu_ladder/CELL_FPU010` (b165e9) | 0.6981 | 13.96 |
| `fpu_ladder/CELL_FPU015` (b166e9) | 0.6861 | 13.72 |
| `fpu_ladder/CELL_FPU030` (b167e9) | 0.7152 | 14.30 |

### 3.1 ⚠️⚠️ ALL SEVEN ARE ARBITER-OFF, AND THIS CELL IS NOT — DISCLOSED BEFORE GAME 1

The arbiter is a **stochastic** root hook that changes the pick on ~46 % of the plies it fires on, on
**both** seats. Its rollout variance rides both arms and CRN deck-pairing absorbs the deck draw as
usual, but there is no reason to assume the per-deck dispersion is unchanged, and **no cell in the
corroboration table can speak to it.**

⭐ **THAT COSTS POWER, NEVER VALIDITY.** `READ_RULE` §1 adjudicates every branch at the cell's **own
realized SE**; `sigma_D` is ⛔ **power arithmetic only** and is never a denominator in a branch test.
`se_anomaly()` prints the realized/modelled ratio and FLAGS a value outside `[0.70, 1.43]` — and a
**wider** ratio is pre-disclosed here as plausible rather than surprising. ⛔ It is REPORTED and is
never a branch input.

### 3.2 ⛔⛔ THE READ DISTRIBUTION — WHAT `+1.0` COSTS, COMPUTED NOT ASSERTED

`screen_lib.read_distribution(delta, se)` computes these and `sanity_check()` asserts them, so the
round cannot quietly improve its own advertised odds:

| true effect `δ` | `H-ADOPT` | `H-BOUNDED` | `H-NEGATIVE` | `H-UNRESOLVED` |
|---|---:|---:|---:|---:|
| **0 (true null)** | **0.028 %** | 26.8 % | 2.28 % | **70.9 %** |
| **+1.0 (at the bar)** | 2.28 % | 2.25 % | ~0 % | **95.4 %** |
| **+1.835 (the ladder's largest point estimate)** | 21.5 % | ~0 % | ~0 % | 78.5 % |
| **+2.951 (a repeat of the incumbent)** | **79.6 %** | ~0 % | ~0 % | 20.4 % |

Read that table honestly:

- ⭐ **THE ROUND IS PROPERLY SIZED FOR ITS OWN QUESTION.** *"Does the `+2.951` survive into the
  deployed configuration?"* is answered with ~80 % power at the funded `n`. That is the house rule's
  "size `n` to resolve THAT", satisfied rather than apologised for.
- ⛔ **THE BOUNDING DIRECTION IS WEAK.** A true null reads `H-UNRESOLVED` ~71 % of the time.
- ⛔ **A TRUE EFFECT EXACTLY AT THE BAR IS ESSENTIALLY UNRESOLVABLE** (95 % unresolved). The bar is a
  *decision* threshold, not a detection threshold.
- ⛔ **AND THE MIDDLE CASE IS THE UNCOMFORTABLE ONE.** If the deployed configuration halves the effect
  to the ladder's `+1.835`-ish scale, this cell reads `H-UNRESOLVED` ~4 times in 5. That is the
  realistic disappointment and it is written down before game 1.
- ⭐ **The bar cannot fire on noise** (0.028 % false-adopt), and this round runs ONE cell, so there is
  no multiplicity to correct.

### 3.3 ⛔ THE `n` THIS BAR WOULD ACTUALLY NEED, STATED PLAINLY

| goal | decks | games | vs funded |
|---|---:|---:|---:|
| **funded** | 400 | 800 | 1× |
| adopt a repeat of `+2.951` at 80 % power | **405** | 810 | **1.01×** ⭐ |
| adopt `+1.835` at 80 % power | 2,209 | 4,418 | 5.5× |
| `H-BOUNDED` at 80 % under a true null | **1,540** | 3,080 | 3.9× |

⭐ The first row is the round's own question and the funded `n` meets it. ⛔ The other two are what
this round **cannot afford**, and `READ_RULE` §8.2 pre-commits the price of an unresolved read so the
option of buying more `n` after seeing the sign — the `rodv3` failure mode — is closed before game 1.

### 3.4 The secondary

**Primary: the deck-paired margin**, `D(deck) = (diff(a_seat=0) + diff(a_seat=1)) / 2`, in POINTS,
candidate minus opponent. `M > 0` ⇒ the candidate won. It carries every branch.

**Secondary: elo**, reported beside it with its own **deck-paired** CI (R4) on every branch. ⚠️ It is
**not a bar**: `+1.0 pts/deck` has no exchange rate into elo that this round measures. The
instrument's own 2σ elo resolution (`±17.4`, deck-paired at 800 games) is printed as a **resolution**,
and ⭐ **a disagreement between the margin and the elo is DISCLOSED, never arbitrated.**

---

## 4. THE CONTEXT ROWS

### 4.1 Every fpu reading this program owns, stated before game 1

| dose | band | arbiter | `M` | `se` | `LB95` | `UB95` | read |
|---|---|---|---:|---:|---:|---:|---|
| **0.2** | `155e9` | OFF | **+2.951** | 0.683 | **+1.586** | +4.316 | `F-RESURRECT` |
| 0.4 | `156e9` | OFF | +0.754 | 0.715 | −0.676 | +2.185 | `F-UNRESOLVED` (amended, FPU-A1) |
| 0.05 | `164e9` | OFF | +0.081 | 0.695 | −1.309 | +1.472 | `R-BOUNDED` |
| 0.10 | `165e9` | OFF | +1.503 | 0.698 | +0.106 | +2.899 | `R-UNRESOLVED` |
| 0.15 | `166e9` | OFF | **+1.835** | 0.686 | +0.463 | +3.207 | `R-UNRESOLVED` |
| 0.30 | `167e9` | OFF | +1.059 | 0.715 | −0.372 | +2.489 | `R-UNRESOLVED` |

### 4.2 ⛔⛔ THEY ARE CONTEXT AND NOTHING ELSE

**NEVER POOLED. NEVER z-COMBINED. NEVER A BRANCH INPUT. NEVER INTERPOLATED.** Every contrast between
one of these and this cell is **cross-band**, and CL-068 measured **1.8–2.2× over-dispersion** on
exactly that class — in *both* the elo and the deck-paired-margin statistics, with an identity control
exonerating the harness. ⛔ **AND THESE ARE WORSE THAN CROSS-BAND: every one is ARBITER-OFF.** That is
a different **agent pair**, not a different deck draw, and it is the very thing this round is
measuring. There is no arithmetic that combines them with this cell's number.

⭐ What they legitimately did is a **design act, spent before any number of this round exists**: they
fixed **which dose** to confirm. `sanity_check()` pins two consequences of that act so the bar cannot
drift: the incumbent's own realized numbers **do** clear `+1.0` (a repeat of the effect is adoptable),
and the ladder's largest point estimate (`0.15`, `LB95 +0.463`) **does not** — so the lower bar is not
quietly a bar the ladder already cleared.

### 4.3 The axis's older history

`docs/LEVER_INDEX.md:146` recorded FPU as **CLOSED** on neural / value-blended evidence (`+45.4` /
`+31.4` elo screens at `n=200`, never confirmed; the M3 curve peaking at parity). `fpu_resurrection`
reopened it narrowly — none of that evidence could have measured the classical champion, because the
knob was unreachable on its backend until 2026-08-29. ⛔ Those figures are **cross-era as well as
cross-band**, which is strictly worse than cross-band alone, and they enter no arithmetic here.

---

## 5. THE BAND — ONE, `168000000000`

⭐ **PROPOSED: `168000000000`** (400 decks, `168000000000..168000000399`). ⛔ Not claimed, not
registered, not appended to `governance/BAND_REGISTRY.csv` at this commit.

- Highest **registered** id is `167000000000` (the dose ladder, claimed and SPENT 2026-08-31). `162e9`
  and `163e9` remain **RESERVED** by S1 G3 (they appear in `s1_asymmetry_prep/BAND_CLAIM_G3.json` and
  `tests/test_s1_g3_instrument.py` but carry no registry row) — **not taken**. This round starts at
  the next monotone id above the ladder.
- **Tree sweep, 2026-08-31 (batched single pass): 0 references** to `168e9`. Method, the full result
  set, and the free-but-unused `169e9` / `170e9` are in [`BAND_CLAIM.json`](BAND_CLAIM.json).
- ⚠️⚠️ **`146000000000` IS THE TRAP THE CLAIM ORDER EXISTS FOR** — absent from the registry but
  carrying references in the tree. The registry is **necessary and not sufficient**; the **tree sweep
  is the binding check** and is re-run immediately before the CSV append.
- ⭐ `158e9` and `160e9` remain **DROPPED** (0 registry rows, live tree hits), carried forward so the
  next reader does not rediscover them as "free".

### 5.1 ⚠️ THE SWEEP METHOD, AND THE ONE WAY IT CAN SILENTLY LIE

The method is the ladder's: **one combined pass** — `git grep` over tracked files (packed objects,
near-zero filesystem IO) plus exactly one filesystem pass over `git ls-files --others
--exclude-standard` — with per-band classification done against the few hit files. ⛔ Do **not** run
per-band full-tree greps; the `measurement/` tree is multi-GB and the owner stopped exactly that
during the ladder's build.

⚠️⚠️ **AND ONE REFINEMENT LEARNED IN THIS BUILD, RECORDED SO IT IS NOT REDISCOVERED: THE UNTRACKED
HALF MUST BE RUN AGAINST THE MAIN TREE, NOT A WORKTREE.** A `git worktree` has its own index and
reports **zero** untracked files, so a sweep run from one silently skips half the method and reports a
clean band on the strength of the tracked pass alone. The recorded sweep scanned 7,630 untracked files
/ 141 MB in the main tree.

⭐ **The boundary reading also stands** (carried from the ladder): a band id is an **integer deck
seed**, so a digit run inside a float mantissa — or glued to another digit, like the IEEE-754 hex
`4017000000000000` that contains `170000000000` — cannot be one. Without it a naive substring rule
would refuse ids in this range forever.

**Throwaway sub-range: `168999999000`+** — the §9.2 smoke at `+500`, the §9.3 IDENT legs at `+700`.
⛔ Never in the claim.

---

## 6. COST AND ETA — A FORMULA IN `W`, BECAUSE `W` IS NOT KNOWN YET

⛔⛔ **`W_LAPTOP` IS UNSET AT THIS COMMIT.** A laptop `W` sweep was live while this was built, and its
result is the number the orchestrator stamps. So the cost is given as an **arithmetic the orchestrator
can evaluate**, not as a wall-clock claim.

### 6.1 The throughput model, and it is VERIFIED against realized cells

Each game occupies one worker for `T_game` seconds; `W` workers run in parallel:

```
games/h   = 3600 * W / T_game
wall_h    = 800 * T_game / (3600 * W)
```

⭐ **VERIFIED on the dose ladder's own four archives** (read off the record files' timestamps, mean
over completed records — `feedback_eta_before_launch`'s order-statistic trap avoided):

| realized cell | box | `W` | mean `elapsed_s`/game | model `3600W/T` | observed |
|---|---|---:|---:|---:|---:|
| `fpu_ladder/CELL_FPU015` | laptop | 22 | 502.4 | 157.6 g/h | **159.3 g/h** |
| `fpu_ladder/CELL_FPU030` | laptop | 22 | 489.4 | 161.8 g/h | **163.1 g/h** |
| `fpu_ladder/CELL_FPU005` | local | 30 | 487.9 | 221.4 g/h | **224.6 g/h** |
| `fpu_ladder/CELL_FPU010` | local | 30 | 525.3 | 205.6 g/h | **208.5 g/h** |

The model is within ~1.5 % on all four. ⚠️ Note `T_game` is nearly **W-insensitive** across
`W ∈ [22, 30]` on both boxes (both are DRAM-bandwidth saturated), which is what makes a single
`T_game` a usable planning constant rather than a fitted curve.

### 6.2 ⚠️ THE ARBITER MULTIPLIER — MEASURED, WITH ITS `n` DISCLOSED

Those four cells are **arbiter-off**. The only arb-on measurement at `22016` is the 2026-08-31 wiring
smoke (`SMOKE_ARBON_H2H`, **n=4 games, LOCAL box, W=8, CANDIDATE seat only**):

```
per game:  elapsed 333.8 s   of which the candidate's arbiter = 49.1 s   (14.7 %)
           => arbiter-free part = 284.7 s
BOTH seats armed  =>  T_game ~ 284.7 * (1 + 2*0.147/0.853) ~ 1.345x the arbiter-off game
```

**Planning constant: `T_game ≈ 673 s` (arbiter-off `≈ 500 s` × 1.345).** ⚠️ `n=4`, on the other box,
one seat — this is an **estimate with a stated provenance, not a measurement of this cell**. Bracket
it at `600–700 s`:

| `W` | `T=600 s` | `T=673 s` (planning) | `T=700 s` |
|---:|---:|---:|---:|
| 16 | 96 g/h → 8.3 h | 86 g/h → **9.4 h** | 82 g/h → 9.7 h |
| 22 | 132 g/h → 6.1 h | 118 g/h → **6.8 h** | 113 g/h → 7.1 h |
| 26 | 156 g/h → 5.1 h | 139 g/h → **5.8 h** | 134 g/h → 6.0 h |
| 30 | 180 g/h → 4.4 h | 161 g/h → **5.0 h** | 154 g/h → 5.2 h |

⭐ **THE ORCHESTRATOR SHOULD RE-DERIVE FROM THE CELL'S OWN FIRST HOUR** rather than trusting the row:
`observed games/h` after ~60 min is a direct measurement of `3600·W/T_game` at the realized tenancy,
and it supersedes this table.

⚠️ **`W` IS THROUGHPUT-ONLY:** games are bit-identical at any `W` and **no gate in this pair reads a
clock**, so raising or lowering it changes no bar, no branch and no number. ⛔ It is still refused
while unset — not for correctness, but because a `--smoke` at a `W` the round will not run is a smoke
of a different tenancy, and because the ETA the orchestrator reports must be derived from the `W`
actually used.

### 6.3 The smoke's own cost

- §9.2 smoke: 8 games at production knobs ≈ one `T_game` batch if `W ≥ 8` ⇒ **~11 min** at the
  planning constant.
- §9.3 IDENT legs: 3 legs × 2 games at `k2 × 96` — a ~230× smaller per-move budget ⇒ **seconds to a
  couple of minutes each**.

⛔ The smoke is not optional and it is not free; at ~15 min against a ~7 h round it is the cheapest
insurance this design has.

---

## 7. THE INSTRUMENT — what was forked, what was rewritten

`screen_lib.py` is a fork of [`../fpu_ladder_prep/screen_lib.py`](../fpu_ladder_prep/screen_lib.py)
(itself a fork of `fpu_resurrection`'s, itself a fork of phasegate's). **Carried verbatim in
construction:** `cross_box_rev_gate` (the IS-A1 fold), `rev_matches`, `is_hex40`, `host_matches_box`,
`paired_margin`, `winrate_elo` **with R4's deck-paired elo footing**, `recon_close`, `resolve`/`gate`,
`se_anomaly`, `twosided_gate`, `singlevar_gate`, `knob_gate`, `leaf_gate`, and — the most important
carried fix — `decks_gate` / `n_gate` **written to the prose** (the `FPU-A1` lesson, §7.2).

### 7.1 ⛔ REWRITTEN, and why a copy would have been wrong

| gate / object | the ladder's version | here |
|---|---|---|
| **`G-ARB-OFF`** | walks the manifest, FAILS on any armed arbiter | ⭐⭐ **DELETED AND INVERTED.** Replaced by `G-TIEARB-SIDES` (config, via `tiearb_gates.assert_tiearb_sides`, both seats ARMED at the full deployed dict incl. `phase_gate`) and `G-TIEARB-FIRE` (play, via `tiearb_sides_summary`, nonzero fires on BOTH seats). ⛔ Phasegate's `G-TIEARB-ARM` is **not** reused: it requires "opponent: no tiearb container" and would fail this healthy cell |
| **the bar** | `BAR_EFFECT = 1.5`, a SCREEN bar set at the incumbent's own `LB95` | ⭐⭐ `BAR_EFFECT = 1.0`, the **CONFIRMATION** bar, derived from the two realized production folds (§0.1). `sanity_check()` asserts it is below the ladder's bar, no harder than the k16 fold, and **not** `2σ̂` |
| **`G-PROD`** | budget only (its arbiter was off) | ⭐ **budget AND the arbiter dict**, read out of `PRODUCTION.yaml`. Both halves define the opponent now |
| **the round verdict** | `LADDER-DEAD/LIVE/UNRESOLVED/VOID` over four rungs | **collapsed**: one cell, so the verdict IS the branch. `round_verdict` is kept only as the VOID-or-branch wrapper (a round-gate failure, or an ABSENT archive, must still void) |
| **the golden gate** | built fresh, 6 legs, `run_golden_gate.sh` | ⭐⭐ **INHERITED with the wheel re-asserted**, two gaps NAMED, and the gaps paid by **new IDENT legs in `--smoke`** (§9) |
| **`--ident-mode`** | did not exist | ⭐⭐ **NEW.** `IDENT-REPRODUCES` (the arb-on path reproduces across processes) and `POSITIVE-ARB-ON` (the dose binds with the arbiter live) |
| **the launcher's probes** | one: does `fpu` bind? | ⭐ **two**: does `fpu` bind, **and** can this box arm the OPPONENT seat (`_make_opponent(tiearb=…)`, `_opp_tiearb_telemetry`, `tiearb_gates.assert_tiearb_sides`)? Both plumbings are PYTHON-ONLY, so a stale box fails silently on either |
| **`W`** | frozen per box | ⭐ **refused until stamped**, for every mode including `--dry-run` |

### 7.2 ⭐⭐ `G-N` AND `G-DECKS` — THE CARRIED `FPU-A1` FIX

`fpu_resurrection`'s `CELL_FPU04` was **VOIDED** by its own adjudicator over **one** deterministic
`WindowTruncationError` — `1/800 = 0.125 %`, an order of magnitude below the 2 % void bar its own
frozen prose set — because a **condition column was stricter than the prose beside it**, and
`AMENDMENTS.md` FPU-A1 had to amend the verdict with the statistics already visible.

Here, as in the ladder, the prose *is* the implementation, with **one shared denominator**:

- ⭐ **the denominator is GAMES, not decks**, in both gates. A deck played at one seat only **is**
  exactly one failed game, so `G-DECKS`' one-seat-only rate and `G-N`'s `n_failed / n_games` are the
  **same quantity read off two different documents**.
- `< 2 %` ⇒ **REPORTED, never silently absorbed** (the `b32v64` 0.100 % rust-panic precedent), and the
  cell still READS.
- `>= 2 %` ⇒ the cell **VOIDS**, on both gates.
- `n_common >= 80 %` of 400 — a **fraction**, never an equality, and a backstop.
- ⛔ **the accounting identity `n + n_failed == 800` is NOT absorbed by the bar.**

`analyze_h2h.py --selftest` tests **both directions at the frozen 400-deck scale** (15/800 = 1.875 %
must READ; 16/800 = 2.000 % must VOID), because the shipped 12-deck fixture cannot express a sub-2 %
whole number of failures and a test that could not express it would be a test of nothing.

### 7.3 ⭐ Carried launcher/adjudicator fixes

- **R1 — the smoke adjudicates its own `SMOKE_` dir from the EMITTED manifest**, and **exits non-zero
  on zero cells or an empty knob**, so `run_cells.sh`'s `|| DIE` is reachable. ⭐ Extended here: the
  smoke's required-gate set now includes `G-TIEARB-SIDES` and `G-TIEARB-FIRE`, so a launcher that
  armed only the candidate fails the smoke instead of shipping a confounded cell.
- **R2 — test import isolation by explicit path.** Four sibling rounds now ship a module named
  `screen_lib`; `tests/test_fpu_h2h_instrument.py` loads this one as `fpu_h2h_screen_lib` via
  `importlib.util.spec_from_file_location` and pins that it is not any sibling's fork. ⭐ `screen_lib`
  itself loads `tiearb_gates` the same way, under `fpu_h2h_tiearb_gates`, for the same reason.
- **R4 — the paired elo CI.** `winrate_elo` emits `elo_sig_1sigma_paired` and
  `elo_sig_1sigma_unpaired`; the unlabelled key is gone on purpose.
- **The provenance ladder** — `BLIND_COMMIT=PENDING`, the `BAND_CLAIMED` sentinel, `PINNED_SRC_REV`,
  and `assert_rev` **before and after** the cell including the dirty-code-path check over
  `src engine scripts rust tests`.
- ⭐ **`production_config_deviations` is REPORTED, never a gate.** The harness stamps it against
  `PRODUCTION.yaml`; on the morning of 2026-08-31 it was **stale** (a hard-coded `k_dets=8` against
  the promoted 16) and stamped a FALSE deviation on a healthy cell. The loader now reads the YAML —
  but a gate over that field would have voided a healthy cell then and could again on the next
  promotion. `G-BUDGET` is the gate, and it reads the manifest directly.

---

## 8. PRE-LAUNCH ACTS — the executor's checklist

1. **Merge** the build branch; **bundle-sync the laptop** to the launch `HEAD`
   (`reference_offline_git_bundle_sync`). ⚠️⚠️ **THIS IS THE ROUND'S PRIMARY PROVENANCE RISK, AND IT
   NOW HAS TWO HEADS:** the fpu plumbing **and** the `--opp-tiearb-*` plumbing are **python-only**, so
   a box on stale source serves a **dose-free candidate** and/or an **unarmed opponent** with a
   healthy wheel, a healthy `carc_rs_build` and the correct leaf hash.
2. **Stamp `W_LAPTOP`** in `WORKERS.conf` from the laptop `W` sweep. ⛔ Everything refuses until this
   is a positive integer.
3. `git -C <repo> rev-parse HEAD > measurement/fpu_h2h_prep/PINNED_SRC_REV` **on the laptop, after its
   sync**. ⛔ Never committed (`.gitignore`).
4. **Stamp `BLIND_COMMIT`** — a follow-up commit writes the freeze commit's 40-hex sha into
   `WORKERS.conf`. A commit cannot name its own hash.
5. ⭐⭐ **Confirm the INHERITED golden gate on the laptop**: `measurement/fpu_ladder_prep/
   FPU_BITEXACT_LADDER.json` must read `PASS` **and** carry that box's own installed
   `carc_rs_binary_sha`. If the wheel has moved, re-run the ladder's `golden_gate/
   run_golden_gate.sh` **on that box** first (§9.1).
6. **Claim the band**: re-run the tree sweep **with the combined method, from the MAIN TREE**, then
   append the one row from `BAND_CLAIM.json::_csv_rows` to `governance/BAND_REGISTRY.csv`, **then**
   drop `BAND_CLAIMED`. ⚠️ In that order — `146e9` is the trap it exists for.
7. **Smoke the laptop** (`--smoke`) and **read `SMOKE_laptop.json` and `IDENT_laptop.json` by hand**.
8. Launch detached, `nice -n 19`.

`run_cells.sh` enforces 2–7 mechanically and refuses without them.

⚠️ **`--dry-run` is exempt from `G-PROD` and from the golden gate** (loud, not fatal) — it spends no
compute, no band and no blindness, and its purpose is to show the **emitted argv** before anything has
run. ⛔ **`--smoke` is exempt from neither**: it is real play, on the real wheel, on the real code
path. ⛔ **Nothing is exempt from the `W_LAPTOP` check.**

---

## 9. ⭐⭐ THE GOLDEN GATE — INHERITED, WITH THE ARGUMENT STATED

### 9.1 The inheritance question, and the answer

``../fpu_ladder_prep/FPU_BITEXACT_LADDER.json`` (box-local, untracked by design — it stamps the box binary sha) reads
`PASS` on `carc_rs` binary **`a9bb2311ab9a635d`**, adjudicated 2026-08-31 — **hours** before this
round, not epochs. Its twelve checks include `IDENTITY` (`fpu=None` is the champion **bit-for-bit** on
that wheel, against a `git archive` of the pre-plumbing tree), `POSITIVE-0.05/0.1/0.15/0.3`,
`DOSE-DISTINCT`, `ONE-WHEEL`, `TWO-TREES`, `SAME-SEEDS`, `SAME-BUDGET`.

⭐ **THE INHERITANCE IS MECHANICALLY CHECKED, NOT ASSERTED.** `run_cells.sh` reads that artefact on
the launching box and refuses unless it is `PASS` **and** its `wheel.binary_sha` equals that box's own
installed binary. ⚠️ The artefact is **box-local and gitignored** (`carc_rs_binary_sha` differs between
boxes compiling identical source), so the box that ran the ladder has one; a box that did not must run
the ladder's `golden_gate/run_golden_gate.sh` first. If the wheel has moved since the ladder, the
inheritance is **void** and the launcher says so.

**The arbiter path** rides the b64-era certificates plus this morning's wiring smoke:

- `measurement/tiearb_widening_20260817/b64_cell/GATE_NEST.json` (`G-NEST`, 2026-08-20): the cap draw,
  world seeds, playout seeds and world **bytes** are identical at `B16 ⊂ B64` — the arbiter's CRN
  construction, certified. ⚠️ On a **pre-`a9bb2311`** wheel, and on the **candidate seat only**.
- `/mnt/c/carc-shared/fpu_ladder/SMOKE_ARBON_H2H` (2026-08-31, n=4 throwaway): the resolved arbiter
  dict **including `phase_gate`** read back off an **emitted** manifest, coexisting with
  `fpu_reduction = 0.2` in one resolved config, with `φ = 20.0` fires/game, `pickchange_rate 0.4625`,
  `playouts_total = 15,936 = 249 arms × 64` (B=64 confirmed arithmetically). ⚠️ **Candidate seat
  only** — the opponent seat could not be armed until that afternoon.

### 9.2 ⛔⛔ THE TWO GAPS, NAMED

1. **No certificate has ever exercised `fpu` AND the arbiter TOGETHER.** Every golden-gate leg this
   family owns is arbiter-off; every arbiter certificate is dose-free.
2. **`0.2` is not one of the ladder gate's four control doses** (`0.05/0.1/0.15/0.3`). Its own
   positive control lives in the parent round's `FPU_BITEXACT.json`, on a wheel that no longer exists.

⛔ A build in which the arbiter overrode the dose's effect at the root would pass **every** inherited
check and flatten this cell into champion-vs-champion — moving no leaf hash, sitting inside `G-SAT`'s
rail, and reading as a clean, credible null. That is the same shape of defect the hard-coded `None`
had, and this family exists because that argument was wrong once already. ⛔ **"Argued play-neutral"
is not a certificate.**

### 9.3 ⭐⭐ THE IDENT LEGS — WHAT PAYS FOR THE GAPS

`--smoke` runs three extra legs at the golden gate's **own tiny budget** (`k2 × 96`), arbiter ARMED on
BOTH seats, on the throwaway sub-range, all three on **the same seeds**:

| leg | flags | proposition |
|---|---|---|
| `SMOKE_IDENT_A` | arb both seats, `--cand-fpu-reduction 0.2` | — |
| `SMOKE_IDENT_A2` | **identical to A**, different out-dir | ⭐ **`IDENT-REPRODUCES`**: `A == A2` |
| `SMOKE_IDENT_B` | same as A, **dose DROPPED** | ⭐⭐ **`POSITIVE-ARB-ON`**: `A != B` |

- ⭐ **`IDENT-REPRODUCES`** — the arbiter is a **stochastic** root hook driven by a CRN salt. If it
  does not reproduce across processes, this cell's numbers are not reproducible and **no downstream
  gate would notice**.
- ⭐⭐ **`POSITIVE-ARB-ON`** — this is the **`0.2`-with-the-arbiter-live positive control that has
  never existed on any wheel**, and it closes both §9.2 gaps in one leg.

`analyze_h2h.py --ident-mode` adjudicates them into `IDENT_<role>.json` and **exits non-zero** on
either failure, so `run_cells.sh`'s `|| DIE` is reachable. Per-game comparison is over
`(seed, a_seat, diff, score_p0, score_p1, won_by_champ, drew, moves, deck_hash)`; ⚠️ `elapsed_s` and
the `*_secs` fields are **excluded on purpose** — they are wall clock and differ between two identical
runs by construction, and a comparison that included them would fail every healthy leg.

⚠️ **`POSITIVE-ARB-ON` HAS A FALSE-ALARM MODE AND IT IS DISCLOSED:** at `IDENT_GAMES = 2` two shallow
searches *can* coincide. The adjudicator says so in its own failure text. **If it fires, raise
`IDENT_GAMES` and re-smoke before concluding the wiring is broken — and do not launch either way until
it passes.**

⛔ **THE IDENT LEGS ARE A CODE-PATH GATE AT A TINY BUDGET AND NO NUMBER IN THEM IS A STRENGTH
MEASUREMENT.**

---

## 10. WHAT THIS ROUND DOES NOT DO

- ⛔ It does not touch `governance/PRODUCTION.yaml` on any branch. `H-ADOPT` licenses **proposing** a
  flip; the flip needs an owner ruling, exactly as the k16 and `B=64` folds did.
- ⛔ It does not locate an optimum and licenses no interpolation. One dose, one band.
- ⛔ It says nothing about the arbiter-FREE champion, and no reading here may be quoted back onto the
  `155e9` / `164–167e9` cells.
- ⛔ It does not re-open, re-read or amend the dose ladder. That verdict is spent and frozen.
- ⛔ It does not run out-of-family. Step 3 (Carcasum, the arm-on T-TRANSFER protocol) is the
  out-of-family check and it is its own prereg, its own band and its own owner funding.
- ⛔ It does not measure the owner-hole. No branch touches `measurement/e4_games/`.
- ⛔ It does not pool anything, with anything.
