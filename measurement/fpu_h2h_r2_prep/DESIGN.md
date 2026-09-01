# FPU PRODUCTION-H2H **ROUND 2** — PRICING THE DEPLOYED CONFIGURATION AT DOUBLE `n` — DESIGN

> **STATUS: FROZEN** (2026-09-01). This document and [`READ_RULE.md`](READ_RULE.md) are **the pair**,
> and the pair is law. ⛔ **NOTHING IN EITHER FILE MOVES AFTER THE BLIND COMMIT.**
>
> ⛔ **0 games have been played at this commit. No band is claimed at this commit.** The instrument
> exists and `analyze_h2h.py --selftest` is `PASS`.
>
> ⭐⭐ **THIS ROUND IS ROUND 1'S SUCCESSOR, EXECUTED TO THE LETTER OF ROUND 1'S OWN §8.2.** That
> section pre-committed, *before its game 1*, that an `H-UNRESOLVED` cell is re-runnable **only on a
> NEW BAND, with a NEW PAIR, and only with FRESH OWNER FUNDING**. Round 1 read `H-UNRESOLVED`
> (`M = +1.019 ± 0.683`, band `168e9`). This is that round: new pair, new band (`169e9`), owner-funded
> 2026-08-31 night, **bar unmoved**, and ⛔ **nothing pooled across the two**.
>
> ⭐⭐ **AND IT CARRIES A PRE-REGISTERED FLEXIBLE-BOX CLAUSE (§6.4).** Box assignment is
> **THROUGHPUT-ONLY** and may change mid-round. Frozen at launch: the **laptop** plays the full deck
> range. The owner may add **local** later. ⛔ The clause is not free, and §6.4 + `READ_RULE` §4 state
> the three gates that are its price.
>
> ⛔⛔ **`W_LOCAL` IS DELIBERATELY UNSET (`TBD_FROM_SWEEP`).** No arb-on local `W` sweep existed at the
> freeze commit. `run_cells.sh` REFUSES `--role local` for every mode — including `--dry-run` and
> `--smoke` — until it is stamped. ⭐ **The laptop is unaffected and launches now** (`W_LAPTOP=26`,
> banked from the 2026-08-31 arb-on sweep).
>
> ⚠️ **THE GOLDEN GATE IS INHERITED, NOT REBUILT** — now from three sources, the third being **round
> 1's own banked gate-passing cell** (§9.1). Its two gaps are still NAMED and still paid by the
> `--smoke` IDENT legs, which are now **mandatory per box** (§9.3).
>
> ⚠️ **THIS ROUND IS OWNER-FUNDED, NOT TRIGGER-FIRED.** No pre-registered branch authorised it; an
> `H-UNRESOLVED` fires nothing. The owner did. §0.2 says so in full.

---

## 0. THE ONE-PARAGRAPH VERSION

**ONE cell, `n=1600` games (800 seat-balanced decks × 2 seatings), on the fresh band `169e9`.**
Candidate = the DEPLOYED champion (`k16×1376 = 22016` + the deployed arbiter `B=64`) **plus**
`fpu_reduction = 0.2`; opponent = **the same deployed agent without the dose**, ⭐⭐ **arbiter ARMED
ON BOTH SEATS at the full deployed spec.** Same arms as round 1, verbatim. Same bars as round 1,
verbatim. **Double the `n`.** The 800 decks are executed as **8 chunks of 100** that tile the band, so
that box assignment can move mid-round without any archive losing its provenance (§6.3, §6.4).

### 0.1 ⭐⭐ THE BAR IS ROUND 1'S, AND IT DOES NOT MOVE

| branch | condition | what it means |
|---|---|---|
| **`H-ADOPT`** | `LB95(M) >= +1.0` | ⭐ licenses **PROPOSING** the `PRODUCTION.yaml` fpu flip **and** funding step 3 (Carcasum external). ⛔ **NEVER an automatic adoption.** |
| **`H-BOUNDED`** | `UB95(M) < +1.0` | ⭐ discharges step 2: the effect does **not** survive into the deployed configuration at the size the decision cares about |
| **`H-NEGATIVE`** | `M <= 0` **and** `z <= -2` | the dose is actively harmful with the arbiter live (checked first) |
| **`H-UNRESOLVED`** | everything else | ⛔ not a null and not a bound |

`+1.0 pts/deck` was **derived in round 1** from the two folds this program has actually accepted into
production — the **k16 budget promotion** (`+1.229 pts/deck`, 2026-08-30) and the **tie-arbiter `B=64`
fold** (`+1.7167 pts/game`, 2026-08-20) — and it is carried here **verbatim**.

⛔⛔ **A SUCCESSOR ROUND THAT SOFTENED ITS BAR AFTER SEEING `M = +1.019` WOULD BE CHOOSING A BAR FROM
THE DATA**, which is the single thing this whole apparatus exists to prevent. `sanity_check()` pins
`BAR_EFFECT == 1.0` and additionally pins that round 1's own realized numbers still read
`H-UNRESOLVED` under this round's frozen ladder.

### 0.2 ⚠️⚠️ WHAT FUNDED THIS ROUND — AND WHAT DID NOT

⛔ **ROUND 1's `H-UNRESOLVED` DID NOT.** Its `READ_RULE` §8.2 is explicit: an unresolved read
discharges nothing, licenses nothing, and does not retract the arbiter-off `+2.951` either. It says
the round bought no verdict, and nothing more. ⛔ `feedback_execute_prereg_triggers` does **not**
apply: no prereg branch authorised this.

⭐ **THE OWNER FUNDED IT** (2026-08-31 night, *"launch 1 on laptop now, but make it flexible so we can
add local into the mix later"*), on the shape of what round 1 produced: a positive point estimate at
`z +1.49`, an instrument that passed every gate including both arbiter gates on both seats, and a
realized dispersion that turned out **not** to be inflated by arming the arbiter. The honest argument
for the round is that **doubling `n` is the only lever left that does not change the question**, and
§3 states exactly what it buys and what it does not.

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
determinization worlds per tied arm (capped at `J=4` arms) and argmaxing the mean. ⛔ **The two
surfaces are not orthogonal in principle: FPU changes the visit distribution, the visit distribution
decides which root ties are REACHED, and the arbiter is what happens at a tie.** That is why the
arbiter-off readings do not transfer for free, and why `H-NEGATIVE` is a real branch rather than a
formality.

---

## 2. THE CELL

| cell | boxes | knob | dose | band | n |
|---|---|---|---|---|---|
| `CELL_H2H2_FPU02` | **laptop at launch; local may be added (§6.4)** | `fpu_reduction` | **0.2** | `169000000000` | 800 decks × 2 = **1600 games** |

Both sides:

- fair PIMC **`k16 × 1376 = 22016`** — the 2026-08-30 promoted desktop champion
- ⭐⭐ **tie arbiter ARMED, BOTH SEATS**: `B=64, J=4, mode=argmax, salt=tiearb2-deploy-v1, eps=0.0,
  phase_gate=all` — the full deployed spec
- `rules_profile = fixed_v1`, `CARCASSONNE_FIX_R9=1` (env-latched at import)
- `exact_k = 2`, mode `marginalized`
- backend `rust` — ⛔ **not optional**: the arbiter is RUST-ONLY and the harness refuses
  `--{cand,opp}-tiearb-enabled` on python
- leaf `a36d2e15a3b3d71d` (curve125) — **the same leaf on both sides**
- the knob on the **candidate only**, via `--cand-fpu-reduction`

### 2.1 ⛔ Single-variable discipline (carried verbatim from round 1)

- `G-SINGLEVAR` asserts `fpu_reduction` **DIFFERS** across the two sides and equals `0.2` on the
  candidate, and that **every other** alias (`c_puct`, `tau_p`, the three budget fields, `value_norm`,
  `leaf_quantize`, `final_select`) is **EQUAL**.
- ⭐ `G-FPU` **additionally** asserts `config.cand_search.c_puct` is `null`.
- ⛔ `run_cells.sh` carries **no** `--cand-c-puct`, **no** `--c-puct` and **no** `--tau-p`. The last
  two are the **shared** flags: they build `champ_cfg_dict`, which `_make_opponent` feeds through the
  *same* `_cfg_from_dict`, so they move **both sides**.
- ⛔⛔ **THE `tiearb_*` TERMINALS ARE DELIBERATELY *NOT* IN `G-SINGLEVAR`'s ALIAS TABLE** — the
  opponent **cannot** stamp them under `config.opponent.champ_cfg` (five keys by name), so such a
  clause would read ABSENT and void every healthy cell. `G-TIEARB-SIDES` and `G-TIEARB-FIRE` own that
  proposition.

### 2.2 Why `0.2` and not another dose

`0.2` is the **only dose that has ever fired** on the classical champion (`+2.951 ± 0.683`, `z +4.32`,
band `155e9`, arbiter OFF). `0.4` read `F-UNRESOLVED`; the dose ladder that tried to bracket `0.2` read
**`LADDER-UNRESOLVED`** (`0.05` `R-BOUNDED`; `0.10 / 0.15 / 0.30` all `R-UNRESOLVED`; none adopted).
⛔ Re-running a ladder rung here would be a second screen on a new band, not a confirmation of
anything, and the ladder's own `READ_RULE` §8.2 forbids extending an unresolved rung. **The
confirmation leg confirms the dose that fired.**

---

## 3. SIZING, POWER, AND WHAT DOUBLING `n` ACTUALLY BUYS

### 3.1 ⭐⭐ THE SIZING CONSTANT MOVED, AND THE MOVE IS AN IMPROVEMENT

Round 1 was the first — and remains the **only** — cell this program owns with the arbiter **armed on
both seats**. It realized `se = 0.68247` at `n = 400` decks, i.e. **`sigma_D = 13.6495`**.

⭐ **That is a measurement of THIS EXACT AGENT PAIR**, where the carried `13.81` was an arbiter-off
constant used as a stand-in. Round 2 sizes on it: **`se_model(800) = 0.4826`**.

⭐ **And it settles a question round 1 had to disclose as an open risk.** Round 1's §3.1 pre-disclosed
that an armed arbiter — a stochastic root hook changing the pick on ~46 % of the plies it fires on, on
both seats — *might* widen the per-deck dispersion, and that a wider realized SE would cost power. It
did not: `13.6495` lands **inside** the seven arbiter-off siblings' `13.02–14.30` spread.

| sibling | realized `se` | implied `sigma_D` | arbiter |
|---|---:|---:|---|
| **`fpu_h2h` ROUND 1 / `CELL_H2H_FPU02` (b168e9)** | **0.6825** | **13.65** | ⭐ **ON, both seats** |
| `fpu_resurrection/CELL_FPU02` (b155e9) | 0.6826 | 13.65 | OFF |
| `fpu_resurrection/CELL_FPU04` (b156e9) | 0.7153 | 14.29 | OFF |
| `fpu_resurrection/CELL_CPUCT10` (b157e9) | 0.6511 | 13.02 | OFF |
| `fpu_ladder/CELL_FPU005` (b164e9) | 0.6952 | 13.90 | OFF |
| `fpu_ladder/CELL_FPU010` (b165e9) | 0.6981 | 13.96 | OFF |
| `fpu_ladder/CELL_FPU015` (b166e9) | 0.6861 | 13.72 | OFF |
| `fpu_ladder/CELL_FPU030` (b167e9) | 0.7152 | 14.30 | OFF |

⛔ **`sigma_D` IS POWER ARITHMETIC ONLY** and is never a denominator in a branch test. `se_anomaly()`
prints the realized/modelled ratio and is ⛔ **never a branch input**.

### 3.2 ⛔⛔ THE READ DISTRIBUTION AT THE FUNDED `n` — COMPUTED, NOT ASSERTED

`screen_lib.read_distribution(delta, se)` computes these at `se = 0.4826` and `sanity_check()` asserts
them, so the round cannot quietly improve its own advertised odds:

| true effect `δ` | `H-ADOPT` | `H-BOUNDED` | `H-NEGATIVE` | `H-UNRESOLVED` |
|---|---:|---:|---:|---:|
| **0 (true null)** | 0.002 % | **50.6 %** | 2.28 % | 47.1 % |
| **+1.0 (at the bar)** | 2.28 % | 2.27 % | ~0 % | **95.4 %** |
| ⛔⛔ **+1.019 (ROUND 1's OWN point estimate)** | **2.5 %** | 2.1 % | ~0 % | **95.4 %** |
| **+1.835 (the ladder's largest point estimate)** | 39.4 % | ~0 % | ~0 % | 60.6 % |
| **+2.0** | 52.9 % | ~0 % | ~0 % | 47.1 % |
| **+2.951 (a repeat of the incumbent)** | **97.9 %** | ~0 % | ~0 % | 2.1 % |

**And the same table at round 1's `n=400` (`se = 0.6825`), so the delta is visible rather than
claimed:** a true null gave `H-BOUNDED` **27.4 %** / `H-UNRESOLVED` **70.3 %**, and a repeat of the
incumbent adopted **80.5 %**.

Read that honestly:

- ⭐ **WHAT DOUBLING `n` BOUGHT.** The bounding direction nearly **doubled** (27.4 % → 50.6 % under a
  true null) and the unresolved mass fell from 70.3 % to 47.1 %. Against a repeat of the incumbent the
  round is now near-certain (80.5 % → 97.9 %).
- ⛔⛔ **WHAT IT DID NOT BUY, AND THIS IS THE ROUND'S CENTRAL LIMITATION: IF THE TRUE EFFECT IS WHAT
  ROUND 1 MEASURED, THIS ROUND IS BLIND TO IT.** At `δ = +1.019` the cell reads `H-UNRESOLVED`
  **95.4 %** of the time, and `n_decks_for_adopt_power(1.019, 0.80)` is **4,279,208 decks** — over four
  million. ⛔ No affordable round resolves an effect that size, and pretending otherwise would be the
  round's one available lie.
- ⭐ **THE HONEST ONE-NUMBER SUMMARY:** the smallest true effect this cell adopts at even **coin-flip**
  odds is **`+1.97 pts/deck`**. That is the instrument's MDE and it is what "sized for the ADOPT
  direction against a LARGE effect" means concretely.
- ⭐ **The bar cannot fire on noise** (0.002 % false-adopt under a true null), and this round runs ONE
  cell, so there is no multiplicity to correct.

### 3.3 ⛔⛔⛔ THE BAR HAS COLLIDED WITH `2σ̂`, AND IT IS DISCLOSED RATHER THAN FIXED

**This was found by the round's own `sanity_check()`, not by a reader.**

At `n = 800`, `2 · se_model(800) = 0.9652`, and the frozen bar is `+1.0`. ⚠️ **The bar has numerically
landed on `2σ̂` of this instrument** — the exact coincidence the owner's 2026-08-30 ruling names as a
defect, and round 1's own guard fires on it.

⭐ **WHY THE BAR STILL DOES NOT MOVE.** The ruling is about **provenance**: *"a bar defined as exactly
`2·se_model`"*, i.e. a bar read off the instrument instead of off the decision. This bar is not that.
It was derived in round 1 from two realized production folds, frozen there, and is carried verbatim.
At round 1's own `n` it sat at `0.73 · 2σ̂`; the collision is an artefact of **doubling `n` while
correctly refusing to move a pre-registered bar**. ⛔ Moving it now — in either direction — after
seeing round 1's `M = +1.019` would be the strictly worse sin.

⛔⛔ **BUT THE PATHOLOGY THE RULING WARNS ABOUT IS REAL HERE AND IS PRICED.** The ruling's mechanism is
*"a bar at `2·se_model` makes the kill branch fire only on a NEGATIVE point estimate."* At this `n`,
`H-BOUNDED` requires `M < BAR − 2se = +0.034` — **so in practice the bounding branch fires almost
exactly when the point estimate is non-positive**, and a true null splits ~50.6 % `H-BOUNDED` /
~47.1 % `H-UNRESOLVED`. That is computed above, asserted in `sanity_check`, carried in
`screen_lib.BAR_COINCIDENCE_AT_FUNDED_N`, surfaced in every read-out, and stated **before game 1** —
which is precisely what the house rule demands of a round that can afford only one direction.

### 3.4 ⛔ THE `n` THIS BAR WOULD ACTUALLY NEED

| goal | decks | games | vs funded |
|---|---:|---:|---:|
| **funded** | **800** | **1600** | 1× |
| adopt a repeat of `+2.951` at 80 % power | 396 | 792 | 0.5× ⭐ |
| adopt `+1.835` at 80 % power | 2,158 | 4,316 | 2.7× |
| adopt `+2.0` at 80 % power | 1,505 | 3,010 | 1.9× |
| `H-BOUNDED` at 80 % under a true null | 1,505 | 3,010 | 1.9× |
| ⛔⛔ adopt `+1.019` (round 1's estimate) at 80 % power | **4,279,208** | 8,558,416 | **5,349×** |

### 3.5 The secondary

**Primary: the deck-paired margin**, `D(deck) = (diff(a_seat=0) + diff(a_seat=1)) / 2`, in POINTS,
candidate minus opponent. `M > 0` ⇒ the candidate won. It carries every branch.

**Secondary: elo**, reported beside it with its own **deck-paired** CI (R4) on every branch. ⚠️ It is
**not a bar**. The instrument's own 2σ elo resolution (**`±12.3`**, deck-paired at 1600 games) is
printed as a **resolution**. ⚠️ Note and do not be misled: `±17.4` was round 1's *paired* figure at 800
games and is round 2's *unpaired* figure at 1600 — every emitted field names its footing, and that is
the defence. ⭐ **A disagreement between the margin and the elo is DISCLOSED, never arbitrated.**

---

## 4. THE CONTEXT ROWS

### 4.1 Every fpu reading this program owns, stated before game 1

| dose | band | arbiter | `M` | `se` | `LB95` | `UB95` | read |
|---|---|---|---:|---:|---:|---:|---|
| ⭐⭐ **0.2** | **`168e9` (ROUND 1)** | **ON, both seats** | **+1.019** | 0.682 | −0.346 | +2.384 | **`H-UNRESOLVED`** |
| **0.2** | `155e9` | OFF | **+2.951** | 0.683 | +1.586 | +4.316 | `F-RESURRECT` |
| 0.4 | `156e9` | OFF | +0.754 | 0.715 | −0.676 | +2.185 | `F-UNRESOLVED` (amended, FPU-A1) |
| 0.05 | `164e9` | OFF | +0.081 | 0.695 | −1.309 | +1.472 | `R-BOUNDED` |
| 0.10 | `165e9` | OFF | +1.503 | 0.698 | +0.106 | +2.899 | `R-UNRESOLVED` |
| 0.15 | `166e9` | OFF | **+1.835** | 0.686 | +0.463 | +3.207 | `R-UNRESOLVED` |
| 0.30 | `167e9` | OFF | +1.059 | 0.715 | −0.372 | +2.489 | `R-UNRESOLVED` |

### 4.2 ⛔⛔ THEY ARE CONTEXT AND NOTHING ELSE — INCLUDING ROUND 1's

**NEVER POOLED. NEVER z-COMBINED. NEVER A BRANCH INPUT. NEVER INTERPOLATED.**

⛔⛔ **AND THE ROUND-1 ROW IS THE ONE MOST AT RISK OF BEING AVERAGED IN, precisely BECAUSE it is the
same agent pair.** It must not be. It is **still cross-band**, and CL-068 measured **1.8–2.2×
over-dispersion** on exactly that class — in *both* the elo and the deck-paired-margin statistics, with
an identity control exonerating the harness and the "different decks" explanation arithmetically
excluded. Round 1's own `READ_RULE` §8.2 additionally pre-committed that its cell may not be extended
or topped up and **could not be pooled with an extension anyway**.

⭐⭐ **THIS ROUND IS 800 FRESH DECKS, NOT 400 + 400.** A reader who wants "1200 decks of evidence" is
asking for an arithmetic that does not exist.

⭐ What round 1 legitimately contributes is a **design act, spent before game 1**: its realized
**DISPERSION** (`sigma_D = 13.6495`) is this round's sizing constant, because it is the only
arbiter-on-both-seats measurement in existence. Its **MEAN** enters nothing.

The six arbiter-off rows are **worse than cross-band**: a different **agent pair**, not a different
deck draw. The older neural-era FPU screens (`+45.4` / `+31.4` elo at `n=200`, `docs/LEVER_INDEX.md:146`)
are cross-band **and** cross-era **and** cross-agent **and** cross-budget, and enter no arithmetic here.

---

## 5. THE BAND — ONE, `169000000000`

⭐ **PROPOSED: `169000000000`** (800 decks, `169000000000..169000000799`). ⛔ Not claimed, not
registered, not appended to `governance/BAND_REGISTRY.csv` at this commit.

- Highest **registered** id is `168000000000` (round 1, claimed and SPENT 2026-08-31). `162e9` and
  `163e9` remain **RESERVED** by S1 G3 — **not taken**. This round starts at the next monotone id.
- **Tree sweep, 2026-09-01 (batched single pass): 0 unglued references** to `169e9`. Method, the full
  result set, and the free-but-unused `170e9` / `171e9` are in [`BAND_CLAIM.json`](BAND_CLAIM.json).
- ⚠️⚠️ **`146000000000` IS THE TRAP THE CLAIM ORDER EXISTS FOR** — absent from the registry but
  carrying references in the tree. The registry is **necessary and not sufficient**; the **tree sweep
  is the binding check** and is re-run immediately before the CSV append.
- ⭐ `158e9` and `160e9` remain **DROPPED**, carried forward so the next reader does not rediscover
  them as "free".

### 5.1 ⚠️ THE SWEEP METHOD, AND THE TWO WAYS IT CAN SILENTLY LIE

The method is round 1's: **one combined pass** — `git grep` over tracked files (packed objects,
near-zero filesystem IO) plus exactly one filesystem pass over the MAIN TREE's untracked files — with
per-band classification done against the few hit files. ⛔ Do **not** run per-band full-tree greps; the
`measurement/` tree is multi-GB.

⚠️⚠️ **LIE #1, CARRIED FROM ROUND 1's BUILD: THE UNTRACKED HALF MUST BE RUN AGAINST THE MAIN TREE, NOT
A WORKTREE.** A `git worktree` has its own index and reports **zero** untracked files, so a sweep run
from one silently skips half the method and reports a clean band on the strength of the tracked pass
alone. **The method was repeated here**, and the deviation this build had to make (the worktree
isolation hook refuses `git -C <main>`, so the untracked set was computed as a main-tree filesystem
walk minus the tracked set) is **recorded in full in `BAND_CLAIM.json::⚠️ method_deviation_disclosed`**.
⭐ That set is a **superset** of the canonical one — it does not honour `.gitignore` — which is why it
scanned 25,870 files / 649.7 MB against round 1's 7,630 / 141.3 MB.

⚠️⚠️ **LIE #2, NEW THIS ROUND AND RECORDED SO IT IS NOT REDISCOVERED AS A BLOCKER:** the untracked
superset surfaced `measurement/value_resurrection_pilot/data/leaf_audit_rows.jsonl`, a **gitignored**
diagnostics file carrying **dozens of glued digit runs** matching ids across this whole range (169e9:
4, 170e9: 29, 171e9: 4). ⭐ **Every one is glued** — a digit on at least one side — and a band id is an
**integer deck seed**, so a digit run inside a longer number cannot be one. ⛔ A naive substring rule
over ignored files would refuse every id in this range **forever**. The next sweeper should expect
these hits and classify them, not stop at them.

**Throwaway sub-range: `169999999000`+**, with ⭐ **per-box offsets** — the §9.2 smoke at `+500`
(laptop) / `+520` (local), the §9.3 IDENT legs at `+700` / `+740` — so one box's smoke can never stand
in for the other's. ⛔ Never in the claim.

---

## 6. COST, ETA, CHUNKING, AND ⭐⭐ THE FLEXIBLE-BOX CLAUSE

### 6.1 The throughput model, verified

```
games/h   = 3600 * W / T_game
wall_h    = 1600 * T_game / (3600 * W)
```

⭐ **The laptop's rate is ROUND 1's OWN REALIZED ONE at `W=26` with the arbiter armed on both seats:
`135 games/h`** (⇒ `T_game ≈ 693 s`). That is the only arb-on throughput measurement this program
owns, and it is an exact match to this round's configuration — not an extrapolation.

⚠️ **The local rate is an ESTIMATE and is NOT a licence to launch:** `≈165 g/h`, scaled from the dose
ladder's arb-off cross-box ratio (local `T_game` 487.9 s vs laptop 502.4 s) at the same 1.345× arb-on
multiplier. ⛔ Local cannot play until `W_LOCAL` is stamped.

### 6.2 ETA

| configuration | rate | wall-clock for 1600 games |
|---|---:|---:|
| **laptop only (frozen at launch)** | 135 g/h | **11.9 h** |
| laptop + local (⚠️ estimate; needs `W_LOCAL`) | ≈300 g/h | **≈5.3 h** |

⭐ **THE ORCHESTRATOR SHOULD RE-DERIVE FROM EACH BOX'S OWN FIRST HOUR** rather than trusting the row —
and, per `feedback_eta_before_launch`'s order-statistic trap, from the **mean over completed records**,
never from the first completions of a parallel run.

⚠️ **`W` IS THROUGHPUT-ONLY:** games are bit-identical at any `W` and **no gate in this pair reads a
clock**. It is still refused while unset, for the box it is unset on.

### 6.3 ⭐⭐ THE CHUNKING — 8 × 100 DECKS, AND IT IS NOT A CONVENIENCE

The 800 decks are executed as **8 chunks of 100** (`CELL_H2H2_FPU02__c0 … __c7`), each its own
out-dir, that **tile the band exactly**.

⛔⛔ **THE REASON IS A HARNESS FACT, NOT A PREFERENCE.** `eval_fair_puct` writes `manifest.json` at run
**START** and `summary.json` at run **END**. So a run **killed mid-flight** — which is exactly what
adding a box does to the laptop's in-flight work — leaves a manifest and **no summary**. If the whole
band were one out-dir:

- stopping the laptop would destroy that dir's summary permanently, and
- the next launch would **clobber** it, because the harness's summary covers only the seeds of the
  invocation that wrote it.

With chunks: a killed chunk is **RESUMED** (its per-game records are on disk and the harness
cached-skips them — `todo = [t for t in tasks if not <record>.exists()]`), every completed chunk
carries a full manifest+summary pair, and **a box change can only ever land on a chunk BOUNDARY**.
That last property is what makes *"which box played which range"* an exactly answerable question
rather than an estimate.

⚠️ The cost is 8 process startups instead of 1 (~8 min of import + worker spawn across the round,
against ~12 h of play). ⭐ It is the cheapest insurance in this design after the smoke.

### 6.4 ⭐⭐⭐ THE FLEXIBLE-BOX CLAUSE, PRE-REGISTERED BEFORE GAME 1

**BOX ASSIGNMENT IS THROUGHPUT-ONLY AND MAY CHANGE MID-ROUND.**

**Frozen at launch:** the **laptop** plays the full deck range (`--role laptop`, chunks 0–7).

**If the owner adds local, the change is executed as — and only as:**

1. **CLEAN STOP of the laptop main, by EXACT PID.**
   ```
   ssh laptop 'ps -eo pid,etime,pcpu,args' | grep eval_fair_puct   # census by FULL ARGS
   ssh laptop 'kill <MAIN_PID>'        # the mp MAIN first
   ...settle...
   ssh laptop 'ps -eo pid,args' | grep eval_fair_puct              # survivors
   ssh laptop 'kill <SURVIVOR_PIDS>'   # spawn workers do NOT get reaped
   ```
   ⚠️ A **LIVE Pool REPLACES killed workers** — kill the MAIN first, let it settle, **then** the
   survivors (`feedback_isolate_destructive_tool_calls`). ⛔ **Never `pkill -f eval_fair_puct`**: it
   would also match the launcher's own command line (`feedback_wsl_ssh_launch_pkill_traps`).
2. **`./run_cells.sh --role laptop --plan`** — reads the share and reports, per chunk: `DONE` /
   `PARTIAL (resume it)` / `UNTOUCHED`, who claimed it, the remaining game count, both ETAs, and a
   suggested split. ⛔ It spends **no** compute, band or blindness.
3. **Relaunch BOTH boxes on DISJOINT contiguous sub-ranges of the UN-PLAYED remainder**, e.g.
   ```
   laptop: ./run_cells.sh --role laptop --chunks 3-5
   local : ./run_cells.sh --role local  --chunks 6-7
   ```
   ⭐ Cached records are skipped by the harness itself, so resuming an interrupted chunk costs only its
   unplayed games.

**⚠️⚠️ HOW RANGE RESTRICTION IS IMPLEMENTED — THE HARNESS HAS NO SUCH FLAG.** `eval_fair_puct` exposes
only `--n` and `--seed-start` (checked: there is no `--seed-lo` / `--seed-hi` / `--band`). The
restriction is therefore **per-chunk seed-start/count arithmetic in the launcher**:

```
--seed-start <chunk lo>   --n <2 * decks_per_chunk>   --paired
```

which is exact, because `_build_work(seed_start, n, paired=True)` yields seeds
`seed_start … seed_start + n/2 − 1`, each at `a_seat` 0 and 1. ⭐ `run_cells.sh` **probes that contract
at launch** (`_build_work(1000, 6, True)` must equal the six expected pairs) — if the harness's
work-builder ever changed shape, every chunk would quietly play the wrong seeds with every other gate
passing at its own address.

`run_cells.sh` accepts `--chunks LO-HI` **or** `--seed-lo N --seed-hi N` as equivalent spellings of the
same arithmetic. ⛔ **A `--seed-lo/--seed-hi` that is not CHUNK-ALIGNED is REFUSED**, loudly, by
`screen_lib.CellSpec.chunks_for_seed_range`: a partial chunk would put two boxes' records in one
out-dir, and that dir emits exactly **one** `manifest.json` with exactly **one** `host`, so the
provenance map would become a **silent lie no gate could see**.

**⛔ THE CLAIM INTERLOCK.** Each chunk dir carries `CLAIM.json {host, role, utc, rev}`. A box refuses a
chunk claimed by a different host **unless** `--reclaim` is passed **and the chunk holds ZERO
records**. ⭐ So an **interrupted chunk is resumed on the box that started it**, and only **untouched**
chunks change hands — which is why step 3's split is computed over the un-played remainder and lands on
chunk boundaries.

**⭐⭐ WHAT THE READ DOES WITH ALL THIS: NOTHING.** The read **POOLS every record on the one band**.
`G-HOST` becomes **PROVENANCE-ONLY** — it publishes the chunk → host → realized-range map and voids on
**nothing** about which box played what (it fails only on an ABSENT host, or a host that is not one of
the two funded boxes). `G-NODUP` owns the proposition that the ranges did not overlap.

**⭐⭐ AND NO CROSS-BOX STATISTIC EXISTS, SO CROSS-BOX FLOAT IDENTITY IS NOT RELIED ON.** This is worth
stating exactly, because it is the obvious objection. Both seatings of every deck are played inside
**one chunk on one box**, so `D(deck) = (diff(a_seat=0) + diff(a_seat=1)) / 2` is computed entirely
within a box. The box is therefore a factor **common to both arms** of every contrast that enters the
statistic, and **cannot bias candidate-minus-opponent**. A box difference could only add between-deck
dispersion, which the realized SE already prices. ⛔ No quantity computed on one box is ever
differenced against one computed on another.

⛔ **What IS required across boxes is SOURCE identity**, and that is `G-REV`'s
(`cross_box_rev_gate`, the IS-A1 fold): every box must publish a `PINNED_SRC_REV`, they must be the
**same 40-hex sha**, and every emitted short rev must canonicalize to it — **never** by comparing one
box's short rev to another's. ⚠️ `carc_rs_binary_sha` is **box-local by construction**, so
`G-WHEEL-SAME` asserts one wheel **within** each box and **reports** the shas across them.

⛔⛔ **AND THE SECOND BOX IS THE HIGHER PROVENANCE RISK, NOT THE LOWER ONE.** Both the fpu plumbing and
the `--opp-tiearb-*` plumbing are **python-only**, so a box on a stale bundle serves a **dose-free
candidate** and/or an **unarmed opponent** with a healthy wheel, a healthy `carc_rs_build` and the
correct leaf hash. A box added mid-round was not on the launch checklist. That is why `--smoke` is
**MANDATORY PER BOX** (§9.3) and why the two plumbing probes run on every invocation.

---

## 7. THE INSTRUMENT — what was carried, what was rewritten

`screen_lib.py` / `analyze_h2h.py` are forks of [round 1's](../fpu_h2h_prep/DESIGN.md). **Carried
verbatim in construction:** `cross_box_rev_gate` (the IS-A1 fold), `rev_matches`, `is_hex40`,
`paired_margin`, `winrate_elo` **with R4's deck-paired elo footing**, `recon_close`, `resolve`/`gate`,
`se_anomaly`, `twosided_gate`, `singlevar_gate`, `knob_gate`, `leaf_gate`, `tiearb_sides_gate`,
`tiearb_fire_gate`, and `decks_gate` / `n_gate` **written to the prose** (the `FPU-A1` fix).

### 7.1 ⛔ REWRITTEN, and why a copy would have been wrong

| gate / object | round 1 | here |
|---|---|---|
| **the loader** | one archive per cell | ⭐⭐ `load_sharded_cell` reads the **frozen chunk plan**, never a glob — a missing chunk arrives as ABSENT, a stray dir cannot become a shard |
| **per-shard gates** | ran once | ⭐ run **per chunk** and folded by **conjunction**, with `bool(per_shard)` guarded so an empty shard map cannot pass vacuously |
| **`G-BAND`** | one `band_seed_start` vs one band | ⭐ **STRICTER** — every chunk must declare **exactly its own** frozen `seed_lo` and deck count, so a mis-typed `--seed-lo` fails at its own address before `G-NODUP` sees the overlap |
| **`G-N`** | one summary's `n + n_failed == 800` | ⭐⭐ **SUMMED over chunks**, `== 1600` — which makes the accounting identity **also the TILING CHECK**: a two-box split that left a hole fails here loudly |
| **`G-SAT`** | `summary:winrate` | ⭐ recomputed on the **POOL** (no summary spans it); a per-chunk rail at 100 decks would be ±4σ and catch nothing |
| **`RECON`** | one archive vs its summary | ⭐⭐ **PER CHUNK**, and §7.2 explains why a "pooled RECON" would witness nothing |
| **`G-HOST`** | VOIDED a cell run off the frozen box | ⭐⭐ **PROVENANCE-ONLY** (§6.4). Fails on an ABSENT host or an UNFUNDED box; never on which funded box played what |
| **`G-WHEEL-SAME`** | one sha per role, cells | ⭐ per **chunk**, bucketed by **strictly resolved** host; reported across boxes |
| **`G-CHUNKS` / `G-NODUP` / `G-SHARD-IDENT`** | did not exist | ⭐⭐ **NEW — the price of §6.4** (§7.3) |
| **`n`** | 400 decks | **800 decks**, 8 chunks |
| **`sigma_D`** | 13.81 (arb-OFF stand-in) | ⭐ **13.6495 — round 1's own arb-ON realization** |
| **the bar's `2σ̂` guard** | numeric collision test | ⭐ **provenance test + a MANDATORY DISCLOSURE** (§3.3), because the numeric test now fires on a correctly-frozen bar |
| **`--role local`** | REFUSED at launch | ⭐ **permitted**, and refused only while `W_LOCAL` is unstamped |
| **the smoke** | once, on the one box | ⭐ **MANDATORY PER BOX**, on per-box throwaway offsets |
| **`--plan`** | did not exist | ⭐ **NEW** — reads the share, reports chunk state, proposes a split. Spends nothing |

### 7.2 ⭐⭐ WHY `RECON` IS PER-CHUNK AND THE PRIMARY IS NOT

The **pooled** statistic has no `summary.json` to be checked against — the harness never computed it.
A "pooled RECON" could therefore only compare `paired_margin` against a number this instrument
synthesized itself, which would **agree by construction and witness nothing** — exactly the defect
`paired_margin` exists to avoid (it is a deliberately independent `math.fsum` re-implementation of
`eval_fair_puct._paired_z`, not an import of it).

⭐ So the division of labour is: **`RECON` certifies the implementation against the HARNESS's own
arithmetic, chunk by chunk, on real emitted `summary.json`s** — and `READ_RULE` §1 then applies that
**certified** implementation to the union. A chunk-level disagreement VOIDS the cell.

### 7.3 ⭐⭐ THE THREE SHARDING GATES — THE PRICE OF §6.4, PRE-REGISTERED

Round 1 was one archive on one box, so *"is this one cell?"* was answered by the filesystem. Round 2
may be 8 archives on 2 boxes, and three propositions that used to be free must now be **proven**:

- **`G-CHUNKS`** — every chunk of the band EXISTS and is COMPLETE (**manifest AND summary**).
  ⛔ A chunk killed mid-flight has the first and not the second; **ABSENT is FAIL and the fix is to
  RESUME that chunk**, never to read around it (a summary-less chunk has no `RECON` witness, no
  `G-TIEARB-FIRE` aggregate and no `n_failed` accounting).
- **`G-NODUP`** — the chunks' realized seed ranges are pairwise **DISJOINT** and every `(deck, seat)`
  appears **EXACTLY ONCE** across the pool. ⚠️ The `(deck, seat)` clause is strictly stronger and is the
  one that binds: records are keyed by `(seed, a_seat)` *inside* a dir, so a duplicate can only arise
  **across** dirs — which is exactly what a mis-typed `--seed-lo` on the second box produces.
- **`G-SHARD-IDENT`** — every chunk resolved the **SAME two agents**. ⛔ Each chunk passes its own
  config gates against the frozen constants; a value that differs *between* chunks (a second box on a
  stale `WORKERS.conf`) is invisible to all of them. This gate compares the chunks **to each other**.

⭐ All three carry **ANTI-VACUITY clauses**, and they are there because the selftest caught the first
drafts **passing on an empty archive**: "no duplicates among zero records" is true and meaningless, and
chunks that agree because none of them says anything agree about nothing. Both are the IS-D1 class.

### 7.4 ⭐⭐ A REAL DEFECT THIS ROUND'S OWN SELFTEST FOUND, AND FIXED

`host_matches_box(h, "local")` carries a **catch-all**: *"not the laptop ⇒ treated as local"*. In round
1 that was harmless — the round was laptop-only and the gate voided anything that was not the laptop,
so the catch-all was never consulted for an *accept*. **In round 2 both boxes are legal, and the
catch-all would silently map ANY unrecognised host** — a cloud node, a mistyped box, a machine nobody
planned — **onto `local`, and let its archive into the pool with a clean provenance line.**

⚠️ It surfaced as the selftest defect `a_chunk_ran_on_an_UNFUNDED_box` firing `G-WHEEL-SAME` and
**not** `G-HOST` — the wrong gate, for the wrong reason, by luck. ⭐ Fixed by a new
`screen_lib.host_role_strict`, which resolves a role **only on an explicit alias hit**;
`host_matches_box` is left exactly as round 1 froze it.

### 7.5 ⭐ Carried launcher/adjudicator fixes

- **R1** — the smoke adjudicates its own `SMOKE_` dir from the EMITTED manifest and **exits non-zero**
  on zero cells or an empty knob, so `run_cells.sh`'s `|| DIE` is reachable. Its required-gate set
  includes `G-TIEARB-SIDES` and `G-TIEARB-FIRE`.
- **R2** — test import isolation by explicit path; five sibling rounds now ship a module named
  `screen_lib`, and `ROUND_ID` pins which fork loaded.
- **R4** — the paired elo CI; `elo_sig_1sigma_paired` / `_unpaired`, the unlabelled key gone on purpose.
- **The provenance ladder** — `BLIND_COMMIT=PENDING`, the `BAND_CLAIMED` sentinel, `PINNED_SRC_REV`
  **per box**, and `assert_rev` **before and after every chunk** including the dirty-code-path check.
- ⭐ **`production_config_deviations` is REPORTED, never a gate.**
- ⭐⭐ **`G-N` / `G-DECKS` are the prose** (the carried `FPU-A1` fix), on **one denominator: GAMES**.
  `< 2 %` ⇒ REPORTED and the cell still READS; `>= 2 %` ⇒ VOID, on both gates; the accounting identity
  is a HARD fail and is **not** absorbed by the bar. `--selftest` tests both directions at the frozen
  **1600-game** scale (`31/1600 = 1.9375 %` must READ; `32/1600 = 2.000 %` must VOID), because the
  12-deck fixture cannot express a sub-2 % whole number of failures.

---

## 8. PRE-LAUNCH ACTS — the executor's checklist

1. **Merge** the build branch; **bundle-sync the laptop** to the launch `HEAD`
   (`reference_offline_git_bundle_sync`). ⚠️⚠️ **THE ROUND'S PRIMARY PROVENANCE RISK, WITH TWO HEADS**
   (the fpu plumbing and the `--opp-tiearb-*` plumbing, both python-only).
2. `git -C <repo> rev-parse HEAD > measurement/fpu_h2h_r2_prep/PINNED_SRC_REV` **on the laptop, after
   its sync**. ⛔ Never committed (`.gitignore`).
3. **Stamp `BLIND_COMMIT`** — a follow-up commit writes the freeze commit's 40-hex sha into
   `WORKERS.conf`. A commit cannot name its own hash.
4. ⭐⭐ **Confirm the INHERITED golden gate on the laptop**: `measurement/fpu_ladder_prep/
   FPU_BITEXACT_LADDER.json` must read `PASS` **and** carry that box's own installed
   `carc_rs_binary_sha`. If the wheel has moved, re-run the ladder's `golden_gate/run_golden_gate.sh`
   **on that box** first (§9.1).
5. **Claim the band**: re-run the tree sweep **with the combined method, from the MAIN TREE**, then
   append the one row from `BAND_CLAIM.json::_csv_rows` to `governance/BAND_REGISTRY.csv`, **then**
   drop `BAND_CLAIMED`. ⚠️ In that order — `146e9` is the trap it exists for.
6. **Smoke the laptop** (`./run_cells.sh --role laptop --smoke`) and **read `SMOKE_laptop.json` and
   `IDENT_laptop.json` by hand**.
7. **Launch detached, `nice -n 19`**: `./run_cells.sh --role laptop` (all 8 chunks).
8. ⭐ **Arm a completion Monitor and a 55-minute session heartbeat** — the watchdog only restarts a
   DEAD chain, never announces a finished one (`feedback_execute_prereg_triggers`,
   `feedback_hourly_heartbeat_for_background_runs`).

**IF AND WHEN LOCAL IS ADDED (§6.4), additionally:**

9. **Stamp `W_LOCAL`** in `WORKERS.conf` from a local arb-on `W` sweep. ⛔ Everything for `--role
   local` refuses until this is a positive integer.
10. **Bundle-sync local**, and `git -C <repo> rev-parse HEAD > .../PINNED_SRC_REV` **on local** — the
    same 40-hex sha as the laptop's, or `G-REV` voids the round.
11. **Confirm the inherited golden gate on local** (its own box-local artefact) and **smoke local**
    (`--role local --smoke`). ⛔ Local has never run a gate-passing cell of this family; round 1's
    banked pass was on the laptop and is inherited **per box**.
12. **Stop the laptop by EXACT PID, run `--plan`, then relaunch both boxes on disjoint chunk ranges**
    (§6.4 steps 1–3).

`run_cells.sh` enforces 2–6 and 9–11 mechanically and refuses without them.

⚠️ **`--dry-run` and `--plan` are exempt from `G-PROD` and from the golden gate** (loud, not fatal) —
they spend no compute, no band and no blindness. ⛔ **`--smoke` is exempt from neither.** ⛔ **Nothing
is exempt from the `W` check for the box it runs on.**

---

## 9. ⭐⭐ THE GOLDEN GATE — INHERITED FROM THREE SOURCES, WITH THE ARGUMENT STATED

### 9.1 The inheritance, and what round 1 adds to it

1. `../fpu_ladder_prep/FPU_BITEXACT_LADDER.json` (box-local, gitignored) reads `PASS` — on the
   laptop's wheel **`a9bb2311ab9a635d`** as of 2026-08-31 — and proves `IDENTITY` (`fpu=None` is the
   champion **bit-for-bit**), `POSITIVE-0.05/0.1/0.15/0.3`, `DOSE-DISTINCT`, `ONE-WHEEL`, `TWO-TREES`,
   `SAME-SEEDS`, `SAME-BUDGET`. ⭐ `run_cells.sh` re-asserts its `wheel.binary_sha` against **the
   launching box's own** installed binary, so the inheritance is **mechanically checked** and cannot be
   inherited across boxes by accident.
2. The arbiter path rides the b64-era certificates: `measurement/tiearb_widening_20260817/b64_cell/
   GATE_NEST.json` (`G-NEST`: the CRN cap draw, world seeds, playout seeds and world **bytes** are
   identical at `B16 ⊂ B64`) plus the 2026-08-31 wiring smoke.
3. ⭐⭐ **NEW: ROUND 1's OWN BANKED PASS.** Round 1 played **800 games of the EXACT arms of this cell**
   and cleared every gate in this family — including `G-TIEARB-SIDES` and `G-TIEARB-FIRE` on **both
   seats**, `G-FPU`, `G-TWOSIDED`, `G-SINGLEVAR`, `RECON` and `G-SAT`.
   ⛔⛔ **THAT IS AN *INSTRUMENT* CERTIFICATE, NOT A STATISTICAL ONE.** Round 1's **number** is a
   context row that is never pooled (§4.2, CL-068); the fact that its **archive passed the gates** is
   evidence about the **code path** and is inherited as such. The distinction is the whole reason this
   sub-section exists rather than a sentence saying "round 1 worked".
   ⚠️⚠️ **AND IT IS INHERITED PER BOX.** Round 1 was banked on the **laptop**. ⛔ **The local box has
   never run a gate-passing cell of this family** — which is exactly why `--smoke` is mandatory per box.

### 9.2 ⛔⛔ THE TWO GAPS, STILL NAMED

1. **No certificate has ever exercised `fpu` AND the arbiter TOGETHER.** Every golden-gate leg this
   family owns is arbiter-off; every arbiter certificate is dose-free.
2. **`0.2` is not one of the ladder gate's four control doses** (`0.05/0.1/0.15/0.3`).

⛔ A build in which the arbiter overrode the dose's effect at the root would pass **every** inherited
check and flatten this cell into champion-vs-champion — moving no leaf hash, sitting inside `G-SAT`'s
rail, and reading as a clean, credible null. ⛔ **"Argued play-neutral" is not a certificate.**

### 9.3 ⭐⭐ THE IDENT LEGS — WHAT PAYS FOR THE GAPS, ⭐ NOW PER BOX

`--smoke` runs three extra legs at the golden gate's **own tiny budget** (`k2 × 96`), arbiter ARMED on
BOTH seats, on that box's own throwaway offset, all three on **the same seeds**:

| leg | flags | proposition |
|---|---|---|
| `SMOKE_IDENT_A_<role>` | arb both seats, `--cand-fpu-reduction 0.2` | — |
| `SMOKE_IDENT_A2_<role>` | **identical to A**, different out-dir | ⭐ **`IDENT-REPRODUCES`**: `A == A2` |
| `SMOKE_IDENT_B_<role>` | same as A, **dose DROPPED** | ⭐⭐ **`POSITIVE-ARB-ON`**: `A != B` |

- ⭐ **`IDENT-REPRODUCES`** — the arbiter is a **stochastic** root hook driven by a CRN salt. If it
  does not reproduce across processes, this cell's numbers are not reproducible and **no downstream
  gate would notice**.
- ⭐⭐ **`POSITIVE-ARB-ON`** — the `0.2`-with-the-arbiter-live positive control, closing both §9.2 gaps.

⭐⭐ **EVERY BOX RUNS ITS OWN.** Round 1 needed one smoke because one box played. Here a box may join
mid-round, and it is the box **least** likely to have been on the launch checklist — so its smoke is
the only thing that proves it can express the cell at all. The offsets are per-box so one box's smoke
can never stand in for the other's.

`analyze_h2h.py --ident-mode` adjudicates them and **exits non-zero** on either failure. Per-game
comparison is over `(seed, a_seat, diff, score_p0, score_p1, won_by_champ, drew, moves, deck_hash)`;
⚠️ `elapsed_s` and the `*_secs` fields are **excluded on purpose** — they are wall clock and differ
between two identical runs by construction.

⚠️ **`POSITIVE-ARB-ON` HAS A FALSE-ALARM MODE AND IT IS DISCLOSED:** at `IDENT_GAMES = 2` two shallow
searches *can* coincide. **If it fires, raise `IDENT_GAMES` and re-smoke before concluding the wiring
is broken — and do not launch either way until it passes.**

⛔ **THE IDENT LEGS ARE A CODE-PATH GATE AT A TINY BUDGET AND NO NUMBER IN THEM IS A STRENGTH
MEASUREMENT.**

---

## 10. WHAT THIS ROUND DOES NOT DO

- ⛔ It does not touch `governance/PRODUCTION.yaml` on any branch. `H-ADOPT` licenses **proposing** a
  flip; the flip needs an owner ruling, exactly as the k16 and `B=64` folds did.
- ⛔⛔ **It does not pool with round 1, in any direction, by any arithmetic.** 800 fresh decks, not
  400 + 400 (§4.2).
- ⛔ It does not locate an optimum and licenses no interpolation. One dose, one band.
- ⛔ It says nothing about the arbiter-FREE champion, and no reading here may be quoted back onto the
  `155e9` / `164–167e9` cells.
- ⛔ It does not run out-of-family. Step 3 (Carcasum, the arm-on T-TRANSFER protocol) is its own
  prereg, band and owner funding.
- ⛔ It does not measure the owner-hole. No branch touches `measurement/e4_games/`.
- ⛔⛔ **AND IT DOES NOT AUTHORISE A ROUND 3.** `READ_RULE` §8.3 pre-commits, before game 1, that a
  second unresolved read closes the axis on **affordability** rather than funding another doubling.
  Escalating `n` after each unresolved read is the `rodv3` failure mode wearing a new band each time.
