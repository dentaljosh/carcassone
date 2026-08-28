# PHASE-GATED TIE ARBITRATION — JUDGE-FREE PHASE DECOMPOSITION — DESIGN

> **STATUS: DESIGN DRAFT — NOT FROZEN, NOT FUNDED, NOT LAUNCHED** (2026-08-28).
> This document and [`READ_RULE.md`](READ_RULE.md) are **the pair**. They become law at the blind
> commit; until the owner funds the round and the pair is stamped `FROZEN`, both are editable.
>
> ⛔ **0 games played. No band claimed. `governance/PRODUCTION.yaml` untouched. No `results.csv`
> row. No claim id. No source file outside `measurement/phasegate_prep/` created or modified.**
>
> ⛔ **THE INSTRUMENT DOES NOT EXIST YET.** The ply-window gate this design measures **is not built**
> — see §7. `run_cells.sh`, `analyze_phasegate.py`, `screen_lib.py` and the selftest fixture are
> **build items with estimates**, not deliverables of this commit.

**Proposed band:** `154000000000` (free, §5) · **Cells:** 2 (Option A) or 4 (Option B) · **Budget:**
k8×1376 = 11008 total sims, both sides · **Boxes:** local (W=14) + laptop (W=22), concurrent
**Sizing memo:** [`SIZING_ETA.md`](SIZING_ETA.md) — read that first.

---

## 0. AUTHORIZATION BLOCK — the sign-off table

| # | Condition | State |
|---|---|---|
| (a) | **FUNDING.** Not requested and not granted. The realized plan is **320–964 core-h** across both boxes / **13.5–40.7 h** round wall depending on option ([`SIZING_ETA.md`](SIZING_ETA.md) §1). | ⛔ **UNFUNDED** |
| (b) | **BAND.** `154000000000` proposed. Zero references anywhere in the tree as of 2026-08-28 (§5). ⛔ **NOT claimed, NOT appended to `governance/BAND_REGISTRY.csv`.** | ⛔ **PROPOSED ONLY** |
| (c) | **INSTRUMENT.** The `tiearb_phase_gate` knob does **not exist** in `rust/`, `carc-py` or `eval_fair_puct.py`. §7 specifies it; §7.6 estimates it. ⛔ **NOTHING WAS BUILT.** | ⛔ **OWED** |
| (d) | **ARBITER CONFIG.** `B=16`, `J=4`, `mode=argmax`, `salt=tiearb2-deploy-v1`, `eps=0.0` on the **candidate only**; opponent structurally disarmed. ⚠️ This is **NOT** the production rung — see §2.3, the config-drift finding. | ⚠️ **DELIBERATE DIVERGENCE FROM PRODUCTION** |
| (e) | **TENANCY.** Exclusive is **not** required (no timing statistic is a branch input), but §6.4's census is. | — |
| (f) | **EXECUTOR INTERLOCK.** No `BAND_CLAIMED`, no `BLIND_COMMIT`, no `PINNED_SRC_REV`, `run_cells.sh` does not exist. | ⛔ **DELIBERATELY ABSENT** |

### 0.1 ⛔ WHAT THIS COMMIT IS

A **design and sizing artefact**. It exists so the owner can price the question before anyone
writes rust. Everything in §7 is a *proposal to build*. Nothing in it has been built.

---

## 1. THE QUESTION

The terminal-grounded tie arbiter beats the champion at the game level. That is settled:

| source | band | contrast | M (pts/game, deck-paired) | z | n |
|---|---|---|---|---|---|
| `tiearb2_stage2_20260817` Phase B, cell `ARB` | `132e9` | arb(B=16) vs unmodified champion | **+3.0700** | **+4.445** | 400 decks / 800 games |
| `tiearb_widening_20260817/b64_cell`, arm `NARROW` | `139e9` | arb(B=16) vs unmodified champion | **+3.6607** | (wr 0.552, +36.26 ± 9.02 elo) | 750 decks / 1500 games |

⛔ **THOSE TWO ARE ON DIFFERENT BANDS AND ARE NEVER POOLED** (CL-068: 1.8–2.2× over-dispersion on
cross-band contrasts, in both the elo and the deck-paired-margin statistics). They are cited
together as a **replication in direction and magnitude**, which is all a cross-band pair can be.

**What has never been done: decomposing that win by game phase, judge-free.**

The only phase decomposition that exists is **in-family and oracle-judged**
(`measurement/tiearb_20260816/READOUT.md` §12, the cuts table):

| cut | n | `arb` (pts/tied ply) | z | `ora` | z | `F` |
|---|---:|---|---|---|---|---|
| `phase:early` | 300 | **+0.1148** | **+1.07** | +0.0880 | +0.87 | 1.303 |
| `phase:mid` | 224 | **+0.3500** | **+3.54** | +0.3710 | +2.96 | 0.943 |
| `phase:late` | 209 | **+0.1843** | **+2.48** | +0.3687 | +4.99 | 0.500 |

That table carries two disqualifications **that travel with every citation of it**:

1. ⛔ **Stage 1's own read rule labels these cuts UNDERPOWERED and forbids adjudicating on them**
   (`READOUT.md` §12 verbatim: *"no branch is ever adjudicated on a cut"*, DESIGN §4.3).
2. ⛔ **The judge family is discredited for headroom purposes by F4** (2026-08-27/28,
   `FUNNEL-CLOSED-BY-F4`): judged headroom is **family-relative** — R1's +1.49 pts/ply clair-puct
   ceiling read **−0.64 (z −3.8)** under an out-of-family judge on the same CRN worlds.

**So:**

> **PRIMARY — do EARLY-GAME arb fires carry real game-level value, measured judge-free?**

### 1.1 ⚠️ THE INFERENCE TO THE STEERING-RULER QUESTION, AND ITS WEAK LINK

The decision this is *for* is whether terminal-grounded rollouts are a cheap ruler for upcoming
**position-steering** work. The chain is:

1. The in-family oracle could not resolve early capture (`+0.115`, z +1.07).
2. If `ARB_EARLY` reads a game-level margin at the §4 bar, early fires carry value.
3. ⇒ terminal-grounded rollouts see value the leaf family does not ⇒ validated as a steering ruler.

⛔⛔ **LINK 1 IS WEAK AND THE WEAKNESS IS STRUCTURAL. This rider is mandatory on every branch.**

The early cut's point estimate was **POSITIVE** (`+0.1148`) and its `F` was **ABOVE 1.0** (`1.303`)
— i.e. the arbiter captured *more* than the in-family oracle's own headroom on that slice. The
honest statement is **"the in-family oracle could not RESOLVE early capture at n=300"**, never
*"the in-family oracle read zero"*. A firing `ARB_EARLY` is therefore **also fully consistent with
the offline early cut simply having been underpowered**, which would teach nothing about
family-blindness at all.

⚠️ And F4 cuts **both** ways: it discredits the oracle's early ≈0 as evidence *for* family-blindness
just as it discredits any judged ceiling. **A judged number cannot be the corroborating half of this
argument, in either direction.**

⭐ **Therefore the honest primary product of this round is the JUDGE-FREE PHASE DECOMPOSITION OF THE
ARBITER'S OWN WIN.** The steering-ruler reading is a **secondary inference with a named broken
link**, and §4 pre-registers it as such. It does **not** measure the owner-hole (the E4 anchor flip,
`measurement/e4_games/`) directly or indirectly, and no branch may be read as touching it.

### 1.2 ⛔ THE SLICES DO NOT SUM TO THE WHOLE, AND NO GATE TESTS THAT THEY DO

Gating the arbiter changes which move is played, which changes every board downstream. `ARB_EARLY`,
`ARB_MID` and `ARB_LATE` therefore play **different games from each other and from `ARB_FULL`**, and

```
M_early + M_mid + M_late  ≠  M_full          (in general, and with no defect implied)
```

⛔ **No branch, no gate and no companion statistic in [`READ_RULE.md`](READ_RULE.md) tests the sum
against `ARB_FULL`.** A shortfall or an overshoot is **expected behaviour of a decomposition by
intervention**, not an anomaly, and it may never be reported as one. (This is the same class as
Stage 1b's `translation_caveat`: the offline→game map is unestablished in both directions.)

### 1.3 ⛔ AN EARLY-GATED ARBITER IS NOT A DEPLOYABLE VARIANT

The gated cells are a **decomposition instrument**. Cost is not the point and cheapness is not a
claim. ⛔ **No branch licenses deploying a phase-gated arbiter**, and the fact that `ARB_EARLY`
happens to be ~27% cheaper than `ARB_FULL` (§6.1) is a **scheduling fact, never a finding.**

---

## 2. THE CELLS

Every cell is **candidate vs the unmodified production champion**, deck-paired, seat-balanced, on
ONE band and ONE deck set. **The single variable across cells is the arbiter's phase gate.**

| cell | arbiter | fires at | opponent | asks |
|---|---|---|---|---|
| `ARB_FULL` | B=16, J=4, argmax | **all** tied tile plies | unmodified champion | ⭐ **THE ANCHOR** — does the arbiter still win in this band? Validates the instrument. |
| `ARB_EARLY` | B=16, J=4, argmax | tied tile plies with `phase_bucket == "early"` | unmodified champion | ⭐⭐ **THE PRIMARY** — do early fires carry game-level value? |
| `ARB_MID` *(Option B only)* | B=16, J=4, argmax | `phase_bucket == "mid"` | unmodified champion | secondary decomposition |
| `ARB_LATE` *(Option B only)* | B=16, J=4, argmax | `phase_bucket == "late"` | unmodified champion | secondary decomposition |
| `IDENT` | B=16, J=4, argmax, **gate = `none`** | nothing | unmodified champion | ⭐ **PREFLIGHT** — gate-off must be the champion. |

At every **non-gated** tied ply the arbiter does not run at all and the champion's own
`pooled_q_argmax` pick stands — the *identical* code path the unmodified champion takes.

### 2.1 ⭐ `IDENT` — the weight-0 / gate-off bit-exact identity cell

Two layers, and **both are owed**:

- **`IDENT-BITEXACT` (free, 0 games, a selftest — §7.5).** `phase_gate = all` ⟹ the emitted action
  sequence is **byte-identical** to today's ungated arbiter over ≥20 seeded games; `phase_gate =
  none` ⟹ **byte-identical to the unmodified champion**. This is the *real* proof and it costs
  nothing. It is a **HARD ABORT**: a non-identity here voids the build, not the round.
- **`IDENT` (a game cell, 40 decks / 80 games).** Champion vs champion with the knob **armed** at
  `gate = none`, adjudicated `|z| ≤ 2.0`. It proves the knob reached the *harness* — the
  `G-J4`/inverted-liveness class. ⚠️ IS-D1's lesson applies: the ident precheck reads **config from
  `manifest.json`** and **statistics from `summary.json`**, never config off `summary.json`, which
  in this harness carries **no config block at all** and returns `{}` — an empty dict that fails
  closed on one conjunct and passes *vacuously* on another.

### 2.2 ⭐⭐ THE PHASE BOUNDARY — PINNED, AND REPRODUCED BIT-EXACTLY

The gate **MUST** match the existing census phase cut. It does, and it is online-computable.

**Source of record:** `scripts/measurement_infra/sample_agreement_roots.py:96`

```python
PHASE_CUTS = {"early": (48, 10**9), "mid": (24, 48), "late": (-1, 24)}

def phase_bucket(k_remaining: int) -> str:
    for name, (lo, hi) in PHASE_CUTS.items():
        if lo < k_remaining < hi:       # STRICT on BOTH ends
            return name
    return "late"                        # the fall-through
```

`scripts/tiletie/chain_census.py:63` copies this verbatim and documents the copy
(*"NOT redefined independently"*), and `measurement/tiearb_widening_20260817/census/CENSUS.md` §6
is keyed on it. **This is the axis every other measurement artefact in the repo uses.**

**The clock:** `k_remaining` = **undrawn deck + the tile in hand**.

- python — `src/carcassonne_ai/fair_agent.py:111` `len(state.deck) + (1 if state.next_tile is not None else 0)`
- rust — `rust/carc/carc-core/src/fair/mod.rs:190` `pub fn k_remaining(g: &Game) -> i64`, documented
  at `:188` as *"`fair_agent.k_remaining(state)` — undrawn deck + the one in hand"*

⇒ **the gate is online-computable at the arbitration hook with zero new engine work.** It ranges
`71` (first tile decision) down to `0`.

⛔⛔ **USE `crate::fair::k_remaining(g)`. NEVER `g.state.deck_len()`.** `search/window_diag.rs:156`
sets its own `k_remaining` field from `g.state.deck_len()` — that is the deck **without** the tile
in hand, an **off-by-one against the census axis**. A gate built from `window_diag` would shift
every boundary by one tile and silently mis-slice the round.

#### ⭐ THE PINNED WINDOWS — resolved to integers, edge cases included

| phase | condition | `k_remaining` ∈ |
|---|---|---|
| `early` | `48 < k` | **[49, 71]** |
| `mid` | `24 < k < 48` | **[25, 47]** |
| `late` | `-1 < k < 24` | **[0, 23]** |

⚠️⚠️ **`k_remaining == 48` AND `k_remaining == 24` MATCH NO INTERVAL AND FALL THROUGH TO `"late"`.**
Both ends of every cut are strict, so `48` fails `48 < 48` (early) and `48 < 48` (mid), and `24`
fails `24 < 24` (mid) and `24 < 24` (late) — both land on the function's terminal `return "late"`.
**Verified by executing the function**, not inferred:

```
k=71 -> early   k=49 -> early   k=48 -> late    k=47 -> mid
k=25 -> mid     k=24 -> late    k=23 -> late
```

⛔ **THIS IS NOT A BUG TO FIX HERE.** It is the behaviour of the canonical function, and every
existing artefact keyed on `phase_bucket` — the CL-070 root bank, `split_tiearb2.py`'s strata,
CENSUS.md §6, the Stage-1 cuts table this round is testing — carries it. **The gate reproduces it
exactly.** Two tile decisions per game (the one at `k=48` and the one at `k=24`) are therefore
classified `late`, and `ARB_EARLY` does **not** fire at `k=48`. §7.5's golden-table test pins all
seven values above. If the owner wants the edge repaired, that is a **separate, tree-wide** change
that re-labels prior artefacts and it is **out of scope for this round**.

### 2.3 ⚠️⚠️ CONFIG DRIFT — THE ARBITER IS NOW PRODUCTION, AT A DIFFERENT `B`

**This is the finding that most constrains the design, and it post-dates the +3.07 measurement.**

`governance/PRODUCTION.yaml` folds the arbiter **in**:

- `tiearb_folded_in: "2026-08-20"` — desktop, **`B=64`, `J≤4`**, on the owner ruling *"I'm buying b64"*
  (`measurement/tiearb_widening_20260817/b64_cell/OWNER_RULING_20260820.md`)
- mobile arbiter folded 2026-08-24
- `fair_deploy.tiearb.threads: 8` armed 2026-08-22

⇒ **"the champion" now MEANS champion + arb(B=64).** A design whose single variable is "the arb
gate" has to say which champion it means, and there is no free choice:

⭐ **DECISION: run the candidate at `B=16` and the opponent ARBITER-OFF — i.e. reproduce the
Stage-2 Phase B contrast exactly.**

**Why.** The anchor's entire job is to reproduce **+3.07**, and +3.07 is a *B=16-vs-arb-off*
number. At `B=64` the anchor would measure a **different and larger** quantity — the b64 cell's
`WIDE` arm read `M = +5.3773` against the unmodified champion vs `NARROW`'s `+3.6607` — and the
instrument-validation property is forfeited: a `B=64` anchor reading, say, +5.1 tells you nothing
about whether *this* band and *this* build reproduce the effect the phase question is decomposing.

⛔ **THE PRICE, STATED PLAINLY AND CARRIED ON EVERY BRANCH:** the answer is about the **B=16**
arbiter. Its transfer to the **deployed B=64** arbiter is an **assumption, not a measurement**.
Nothing in this round licenses a phase claim about production play. The widening campaign measured
`Δ(16→64) = +0.0670 pts/tied ply CI95 [0.0215, 0.1111]` **offline** and its own read-out forbids
projecting that into game points (`offline_ratio_disclaimer`), so the gap cannot be closed by
arithmetic either.

### 2.4 THE FROZEN CONFIG — every knob, both sides

Read off `measurement/tiearb2_stage2_20260817/WORKERS.conf` and `run_cells.sh:13,103,214`.

| knob | value | both sides? |
|---|---|---|
| search | FAIR PIMC, `k_dets=8`, `sims_per_det=1376`, `total=11008` | ✅ identical |
| leaf | `a36d2e15a3b3d71d` (curve125) | ✅ **identical — the arbiter is NOT a leaf change** |
| endgame | `exact_k=2`, `mode=marginalized` | ✅ identical |
| backend | `rust` | ✅ identical |
| rules | `fixed_v1`, `CARCASSONNE_FIX_R9=1` (env-latched at **import**) | ✅ identical |
| arbiter | `B=16 · J=4 · mode=argmax · salt=tiearb2-deploy-v1 · eps=0.0` | ⛔ **CANDIDATE ONLY** |
| **phase gate** | `all` / `early` / `mid` / `late` / `none` — **the single variable** | ⛔ **CANDIDATE ONLY** |

⚠️ Unlike the invasion rounds, **`G-LEAF` here asserts the two sides carry the SAME leaf hash.** The
arbiter is a post-search root hook, not a leaf term. A cell whose two leaf hashes *differ* is
misconfigured and voids.

---

## 3. THE STATISTIC

Per cell, PRIMARY — the house form, unchanged:

```
D(deck) = ( diff(deck, a_seat=0) + diff(deck, a_seat=1) ) / 2
M       = mean over decks appearing in BOTH seatings
SE      = sample sd (ddof=1) / sqrt(n_paired)
z       = M / SE
```

`diff` is `eval_fair_puct.py:1603`'s final-score margin, **candidate minus opponent, in POINTS**.
`M > 0` ⇒ the candidate won. A deck missing a seating is **DROPPED**, never zero-filled.

⛔ Adjudicated **against zero, at the cell's OWN REALIZED SE**. §4's sizing σ is power arithmetic
only and is **never a denominator in a branch test**.

### 3.1 The dispersion model, derived from realized numbers only

From Stage-2 Phase B cell `ARB`: `M = +3.0700`, `paired_z = +4.445`, `n_paired = 400 decks`.

```
se(M)   = 3.0700 / 4.445            = 0.6907  pts/game   [realized]
sigma_D = 0.6907 * sqrt(400)        = 13.81   pts/deck   [realized, the sizing constant]
```

⚠️ **`n` IS 400 DECKS, NOT 800.** The cell played **800 games** = 400 seat-balanced decks × 2
seatings. Sizing on 800 would understate every `n` in §4 by a factor of 2. (This is exactly the
class of `G-N` defect Stage 2's own §0.B amendment caught pre-launch: *a paired n=800 cell yields at
most 400 decks*.)

### 3.2 The cross-cell contrast, and what deck-matching actually buys

All cells share **one band and one deck set**, so `ARB_FULL − ARB_EARLY` is deck-paired. Using the
**realized** cross-cell correlation between two arbiter cells on one deck set — `rho = +0.1237`,
measured in `b64_cell/verdicts/READOUT_B64.md`:

```
se(D_cross) = sqrt(2) * (13.81/sqrt(n)) * sqrt(1 - 0.1237) = 18.28 / sqrt(n)
```

⛔ **DECK-MATCHING BUYS ALMOST NOTHING IN VARIANCE: `sqrt(1 - 0.1237) = 0.936`, a 6.4% SE
reduction** — ~12% fewer games for equal resolution. This replicates `simsplit_alloc_20260812`'s
finding that *CRN bought only 9.9%* of the correlation it was budgeted for. **Do not size a design
on an assumed CRN gain.** The b32v64 cell's own committed `se(D) = 0.7133` was derived assuming
`rho = 0` for precisely this reason.

⭐ **The reason to deck-match anyway is not variance.** It is that (i) it removes the deck-draw
confound entirely, (ii) `G-DECKS` can then prove **one** deck set across every cell, and (iii) it
keeps every contrast **within-band**, which is the only robust class (CL-068).

⛔ **A CROSS-CELL CONTRAST IS NEVER THE PRIMARY.** The primary is `ARB_EARLY`'s own margin against
the unmodified champion. `ARB_FULL − ARB_EARLY` is a pre-registered **companion** (§4.4) and is
never a branch input — it is ~1.3× noisier than the primary and answers a different question.

---

## 4. SIZING — MDEs stated honestly

⚠️ Every figure below is **50%-power** unless the row says otherwise: an effect exactly at the
2σ MDE is detected half the time. The 80%-power column is the one to plan against.

| n decks | games | `se(M)` | **2σ MDE (50% pwr)** | effect resolvable at **80% pwr** |
|---:|---:|---:|---:|---:|
| 400 | 800 | 0.691 | ±1.381 | +1.93 |
| 800 | 1,600 | 0.488 | ±0.977 | +1.37 |
| **1,200** | **2,400** | **0.399** | **±0.798** | **+1.12** |
| **1,600** | **3,200** | **0.345** | **±0.691** | **+0.97** |
| 2,400 | 4,800 | 0.282 | ±0.564 | +0.79 |

**(a) The minimum `ARB_EARLY` cell distinguishing "early ≥ +0.8" from zero at 2σ.**

```
se <= 0.80/2 = 0.40   =>   n >= (2 * 13.81 / 0.80)^2 = 1193 decks
```

⇒ **`n = 1,200 decks / 2,400 games`**, `se ≈ 0.399`, 2σ resolution **±0.798**.

⚠️ **HONEST STATEMENT OF WHAT THAT `n` BUYS.** At 1,200 decks a *true* effect of exactly +0.80
yields `z = 2.01` — **50% power**. What the `n` guarantees is the **bounding** direction, which is
the branch that actually needs guaranteeing: a null there returns `UB95 < +0.80`, i.e. **E-DEAD**
is a real, reachable, 95% bound rather than an absence of evidence. Detecting +0.80 at **80%**
power needs `((1.96+0.84)*13.81/0.80)^2 = 2,337 decks / 4,674 games` — **1.95× the cost**, and it
is not recommended: the bounding property is what the decision turns on.

**(b) The 3-way decomposition with each slice's CI at ±0.7 pt.**

Reading "CI" as the conventional 95% ≈ 2σ half-width:

```
se <= 0.35   =>   n >= (13.81/0.35)^2 = 1557 decks
```

⇒ **`n = 1,600 decks / 3,200 games` per slice cell**, `se ≈ 0.345`, 2σ **±0.691**.
*(At the looser 1σ = ±0.7 reading it would be 389 decks — a screen, not a verdict. §4's bars use
the 2σ reading. [`SIZING_ETA.md`](SIZING_ETA.md) prices a middle rung at ±1.0.)*

### 4.1 THE BAR, AND WHY IT IS +0.80

The **proportional-share expectation** — what early would return if the arbiter's value were spread
uniformly over fired plies — is:

```
0.3380 (early share of fired plies, §6.2)  x  3.07 (the anchor)  =  +1.038 pts/game
```

**The bar `+0.80` is 77% of proportional share.** Three reasons, all pre-registered:

1. It sits **below** proportional, so a genuinely proportional early slice **CONVICTS**. A bar above
   proportional would make E-DEAD fire on a perfectly healthy uniform arbiter.
2. It is the largest bar affordable at ~215 core-h for the primary cell (§6, Option A1).
3. Below +0.80 the early fires are not a useful steering ruler **regardless of sign** — a ruler that
   resolves less than a quarter of the effect it is meant to steer by cannot price a steering
   intervention. The bar is therefore a **decision** bar, not a significance threshold.

⭐ `+1.038` is pre-registered as a **NAMED COMPANION** and is ⛔ **never a branch input**.

### 4.2 What the anchor needs, and why it is small

`ARB_FULL` need only **convict**. Stage 2's own read-out gives *"the `n` that would convict `z_arb`
at 2σ: 81 decks"*. At `n = 400` decks — Stage 2's exact `n`, which makes the replication claim
maximally clean — a true +3.07 reads `z ≈ 4.4`, and even +1.5 reads `z ≈ 2.2`.

⛔⛔ **ANCHOR-FIRST IS A HARD ORDERING (see [`READ_RULE.md`](READ_RULE.md) §4.0).** If the anchor
does not convict, **no branch on `ARB_EARLY` is taken at all** — the entire design presupposes the
arbiter wins in this band and on this build. A failed anchor is `U-VOID-ANCHOR` and the round
produces no phase reading of any kind.

### 4.3 Option B's slice bars

Each of `ARB_MID` / `ARB_LATE` is adjudicated on its **own** margin at the **same** `+0.80` bar and
the same branch names, suffixed by slice. ⛔ Per §1.2 nothing tests the three against `ARB_FULL`.

### 4.4 Pre-registered companions — ⛔ NEVER branch inputs

- `ARB_FULL − ARB_EARLY` deck-paired over `n_common`, with `se(D) = 18.28/sqrt(n_common)`
- proportional-share expectation `+1.038` and the realized early fired-share from `G-PHI`
- per-cell winrate, elo and elo 95% CI. ⚠️ **`elo` may never be quoted bare here** — Stage 2's
  secondary did **not** convict (`+23.92`, CI `[−0.21, +48.06]`, winrate z `+1.94`), and a
  phase *slice* of it will be weaker still. **The margin is the statistic; the winrate is not.**
- `tiearb_pickchanges` per phase, and the fail-soft `tiearb_errors` block (report-only)

---

## 5. THE BAND

**Proposed: `154000000000`.** ⛔ **Not claimed. Not registered.**

- Highest registered id is `153000000000` (`spent`, 2026-08-27, invasion round 3). `154e9` is the
  next monotone id.
- Sweep 2026-08-28: **0 references** to `154000000000` anywhere in the tree.
- ⚠️ **`146000000000` is a trap: absent from `governance/BAND_REGISTRY.csv` but carrying 20
  references in the tree.** A "next free id" search that trusts the registry alone would pick it.
  ⛔ **Do not reuse 146e9.** The registry is necessary but not sufficient — the tree sweep is the
  binding check, and it is re-run immediately before the CSV append.

**Deck-range allocation** (Option A1; every cell on the SAME deck set, disjoint per-cell subdirs):

| cell | decks | seeds |
|---|---:|---|
| `IDENT` | 40 | `154999999000 .. 154999999039` (a throwaway sub-range, never in the claim) |
| `ARB_FULL` | 400 | `154000000000 .. 154000000399` |
| `ARB_EARLY` | 1,200 | `154000000000 .. 154000001199` ⭐ **superset — the anchor's 400 are the `n_common`** |

⚠️ The two cells' ranges **overlap by design** so `ARB_FULL − ARB_EARLY` is deck-paired on 400
common decks. This is the *opposite* of invasion r3's disjoint-ranges rule, and it is deliberate: a
decomposition wants a shared deck set, whereas a ladder of unrelated knobs wants disjoint ones.
`G-DECKS` is written to that shape and must **not** be copied from invasion r3 unedited.

Band retires `decision_influenced=yes` on every branch, per house rule.

---

## 6. COST — from realized numbers only

### 6.1 Per-game worker-seconds

From Stage-2 Phase B's realized per-move walls (`READOUT.md` §4.3(4)) at ~72 moves per side:

| quantity | value | source |
|---|---:|---|
| opponent (unmodified champion) | **1,808.2** ms/move | `rung_ms_per_move`, ARB cell |
| candidate (champion + arb B=16) | **4,383.6** ms/move | `champ_prefix_ms_per_move`, ARB cell |
| `ms_ratio` | **2.4242** | candidate ÷ opponent |

⚠️⚠️ **THE FIELD-NAME TRAP, CARRIED VERBATIM:** in `eval_fair_puct` (lines 2361/2371/2389)
`champ_prefix_ms_per_move` **IS THE CANDIDATE SIDE** — the opposite of `eval_puct_priors`. A
read-out that swaps them **inverts the cost verdict.**

```
champion-vs-champion    = 2 * 72 * 1.8082                  = 260.4 worker-s/game
ARB_FULL                =     72 * (4.3836 + 1.8082)       = 445.8 worker-s/game
arbiter overhead        = 445.8 - 260.4                    = 185.4 worker-s/game
```

Cross-check against the independent numerator route: `phi 17.573 x 9.57 worker-s/fired ply = 168.2`
— the ms/move route is **10% higher**. ⭐ **The ms/move route is used throughout because it is the
conservative one and it is directly measured.**

### 6.2 ⚠️ The early fired-share — A PROXY, AND THE DESIGN'S WEAKEST INPUT

Computed here from `measurement/tiearb_widening_20260817/census/tile_gap_rows.jsonl`
(corpus `champ449`, 449 games, 31,827 tile plies), bucketed by the row's own `phase_bucket`:

| phase | tile plies | exact-tied | tie rate | **share of tied plies** | mean tie size |
|---|---:|---:|---:|---:|---:|
| early | 10,280 | 6,868 | 0.6681 | **0.3380** | 4.12 |
| mid | 10,324 | 6,217 | 0.6022 | **0.3059** | 7.40 |
| late | 11,223 | 7,237 | 0.6448 | **0.3561** | 13.41 |
| **total** | 31,827 | 20,322 | 0.6385 | 1.0000 | 8.43 |

⛔⛔ **THIS IS A PROXY AND IT IS KNOWN TO BE BIASED. Three reasons, all disclosed:**

1. **It is the RAW exact-tie share; the arbiter fires on the DEDUPED arm set** (`repr_arms >= 2`).
   The funnel is *65.98% exact-tie → 40.4% deduped scoreable*. **Mean tie size varies 3.3× across
   phases (4.12 early → 13.41 late)**, and large late tie-sets are overwhelmingly *duplicate*
   placements (CENSUS §4: 69.5% pure-duplicate pooled). ⇒ **dedup will cut LATE hardest**, so the
   true early share is very likely **HIGHER** than 0.3380 — which makes the cost estimate for
   `ARB_EARLY` **optimistic** (it will cost more than §6.3 says).
2. `tile_gap_rows.jsonl` **carries no repr-dedup column**, so the deduped-by-phase split **cannot be
   recovered from any artefact on disk.** This is a genuine, unresolvable-from-here gap.
3. The census ran under `rules_profile: walled`, R9 **off**; the game cells run `fixed_v1`, R9
   **on**. The *phase cut itself* is rules-independent (it is a deck count), but the *fired share*
   is measured on a different rules epoch.

⭐ **THE FIX IS FREE AND IS FOLDED INTO THE BUILD (§7.2).** Per-phase fire counters in the rust
`stats()` mean **`ARB_FULL` measures its own exact per-phase fired split**, at zero extra cost, as a
by-product of the anchor. That number then (i) replaces this proxy for any future sizing and (ii)
becomes `G-PHI`'s evidence. ⛔ It arrives *after* the round is sized, so §6.3 is planned on the
proxy and the residual risk is **≈ +5% wall on the gated cells**, disclosed here.

### 6.3 Per-game cost by cell

```
ARB_EARLY = 260.4 + 0.3380 * 185.4 = 323.1 worker-s/game    (27.5% cheaper than FULL)
ARB_MID   = 260.4 + 0.3059 * 185.4 = 317.1 worker-s/game
ARB_LATE  = 260.4 + 0.3561 * 185.4 = 326.4 worker-s/game
IDENT     =                          260.4 worker-s/game
```

### 6.4 Fleet throughput — realized, and its caveat

From `measurement/tiearb2_20260816/PROGRESS.md` §[t4], the only realized two-box figure on record
for this fleet shape (local W14 + laptop W22):

```
combined            98.6 games/h at 864 worker-s/game  =  23.66 worker-s per wall-second
  local  W14        61.7 s/game  at 864 worker-s/game  =  14.00 worker-s/s   (~1.00 x W14)
  laptop W22        23.66 - 14.00                      =   9.66 worker-s/s   (~0.44 x W22)
```

⇒ **36 nominal workers deliver ~23.66, i.e. 66% efficiency, and LOCAL W14 IS 1.45× THE LAPTOP W22.**
That asymmetry drives the cell→box assignment, not the nominal W.

⚠️ **CAVEAT, AND IT RUNS IN THE SAFE DIRECTION.** That measurement is a **python k4×688 self-play
generation** job, not rust fair PIMC. Its own log root-causes it to the **DRAM wall** (*"W14
delivers only 1.18× W8's throughput"*). The rust path is markedly less memory-bound, so the true
fleet rate for these cells is **likely higher**. `23.66` is used as the **conservative planning
rate**; at 85% efficiency (30.6 worker-s/s) every ETA falls ~23%.

⛔ **No timing statistic is a branch input**, so tenancy is result-safe. But
`feedback_no_agent_compute_beside_eval` still binds on the **census**: census by **FULL ARGS**
(`ps -eo args`), never `-C python` / comm — one niced 1-core DRAM-churner inflated a saturated W=22
eval ~1.8×/move on 2026-08-26.

### 6.5 `G-HOST` — whole cells per box, and what it costs

House shape is **whole cells per box** (disjoint cells ⇒ disjoint `--out-subdir`s ⇒ no shared claims
to race over). With two boxes at a 1.45:1 speed ratio and Option A1's two very unequal cells, the
naive assignment is badly unbalanced:

| assignment | local (14.00 w-s/s) | laptop (9.66 w-s/s) | round wall |
|---|---:|---:|---:|
| naive: `ARB_EARLY`→local, `ARB_FULL`+`IDENT`→laptop | 775,440 w-s → 15.4 h | 377,472 w-s → 10.9 h | **15.4 h** |
| ⭐ balanced: split `ARB_EARLY` into two same-config sub-cells on disjoint deck sub-ranges | ~670k w-s → 13.3 h | ~483k w-s → 13.9 h | **13.5 h** |

⭐ **RECOMMENDED: the balanced shape.** `ARB_EARLY_L` (local, decks `+0..+1036`) and `ARB_EARLY_R`
(laptop, decks `+1037..+1199`) are **one cell in two archives** — identical config, disjoint deck
sub-ranges of one band, pooled for the primary. That pooling is **within-band and same-config**, so
it is legitimate in a way cross-band pooling never is (CL-068), and it is the shape the widening
campaign already used (`ALLOCATION.conf` / `stage_chunks.py`). `G-HOST` then binds per **sub-cell**,
and `G-SUBPOOL` (§7.6 item 6) asserts the two sub-cells' configs are byte-identical before pooling.

[`SIZING_ETA.md`](SIZING_ETA.md) quotes the **balanced** wall as the headline and the naive
whole-cell wall in a footnote.

---

## 7. ⛔ THE INSTRUMENT DOES NOT EXIST — WHAT MUST BE BUILT

### 7.1 THE ANSWER TO "DOES A PLY-GATE KNOB EXIST?" — ⛔ **NO.**

Searched exhaustively across `rust/carc/carc-core/src/`, `rust/carc/carc-py/src/`,
`scripts/classical_search/eval_fair_puct.py` and `scripts/tiletie/`.

**What exists** (`rust/carc/carc-core/src/search/mod.rs:183–252`):

```rust
pub tiearb_enabled:    bool,     // :183   master on/off
pub tiearb_max_plies:  usize,    // :201   default TIEARB_MAX_PLIES = 400
```

⛔⛔ **`tiearb_max_plies` IS NOT A FIRE-GATE AND MUST NOT BE MISTAKEN FOR ONE.** `tiearb.rs:112–116`
documents it as the **playout ply ceiling** — how deep a single `tier1-greedy` *rollout* may run
before it aborts (a full base game is ~144 plies; the default 400 is slack). `carc-py/src/lib.rs:1653`
rejects `< 1` with *"it is a GUARD, not a truncation"*. It says nothing about **which game plies the
arbiter fires at**.

**The hook** (`rust/carc/carc-core/src/fair/mod.rs:654`) is unconditional:

```rust
if !self.cfg.search.tiearb_enabled {
    return Ok(champ_pick);          // the champion — byte-identical default path
}
self.tiearb_arbitrate(g, move_idx, info, champ_pick)
```

⇒ **once enabled, the arbiter fires at every detected tie. There is no window, no phase test, no
min/max fire-ply, and no env var.** ⭐ The good news: `tiearb_arbitrate` already receives `g`, and
`crate::fair::k_remaining(g)` is in scope in the same module — **the gate is a one-line predicate at
an existing call site**, not new plumbing through the engine.

### 7.2 Build item 1 — rust: `tiearb_phase_gate` + per-phase counters

- `rust/carc/carc-core/src/search/mod.rs` — new field `pub tiearb_phase_gate: TiearbPhaseGate`
  beside `:183`, **default `All`** at `:246`.
- `rust/carc/carc-core/src/tiearb.rs` — `TiearbPhaseGate` enum (`All|Early|Mid|Late|None`) with a
  `parse`/`value` pair matching the existing `TiearbMode` shape (`:127`, `:137`), plus
  `phase_bucket(k_remaining: i64) -> &'static str` reproducing §2.2 **including the `k=48`/`k=24`
  fall-through**.
- `rust/carc/carc-core/src/fair/mod.rs::tiearb_arbitrate` — gate test **before** the arbitration
  call, using `crate::fair::k_remaining(g)` (⛔ **never `g.state.deck_len()`** — §2.2). A gated-out
  ply returns `champ_pick` down the **same** path as `tiearb_enabled == false`.
- ⭐ **Per-phase counters in the same change** (`tiearb_fired_{early,mid,late}`,
  `tiearb_pickchanges_{early,mid,late}`) — this is what makes §6.2's proxy self-correcting and gives
  `G-PHI` its address. It is nearly free once `phase_bucket` is called at the hook anyway.

⭐ **IDENTITY PROPERTY, WHICH IS THE WHOLE POINT:** `gate = All` must be **bit-exact** with today's
ungated arbiter, and `gate = None` **bit-exact** with the unmodified champion. Both are proved in
7.5, not asserted.

**Estimate: 4–5 h** (3–4 h gate + ~1 h counters).

### 7.3 Build item 2 — `carc-py` plumbing

`rust/carc/carc-py/src/lib.rs`: new kwarg `tiearb_phase_gate: &str` in the `SearchConfig` signature
(`:1533–1568`), validated in the `:1653–1675` block (an unparseable or empty value **errors**, the
same fail-closed shape as `tiearb_salt`), threaded at `:1700–1706`, exported in `stats()` beside
`:2588`, and shown in `__repr__` at `:1816`.

**Estimate: 1.5–2 h.**

### 7.4 Build item 3 — python harness

`scripts/classical_search/eval_fair_puct.py`:

- `--cand-tiearb-phase-gate` argparse entry in the `:3417–3447` block, default `all`
- the `tiearb` dict at `:1029–1033` gains `tiearb_phase_gate=str(tiearb["phase_gate"])`
- `_cand_tiearb_telemetry` (`:2311+`) exports `phase_gate` and the six per-phase counters — ⭐ **this
  is `G-GATE`'s address, and without it the gate is unwitnessed**
- the manifest carries it at `config.cand_tiearb.phase_gate`

⛔⛔ **THE INVERTED-LIVENESS HAZARD, and it is the design's single most dangerous failure mode:** a
`phase_gate` that silently defaults to `all` makes **`ARB_EARLY` *BE* `ARB_FULL`**, and the primary
becomes a guaranteed-meaningless duplicate of the anchor that **looks perfectly healthy**. This is
exactly the `G-J4` / `simsplit` W9 class (*"a silently-default-off cell A would BE cell B and A−B
would be a guaranteed meaningless null"*). `G-GATE` + `G-PHI` (§4 of the read rule) exist for this
and nothing else; **`ABSENT` is `FAIL`** at both.

**Estimate: 1.5 h.**

### 7.5 Build item 4 — tests (`tests/test_tiearb_phase_gate.py`)

1. ⭐ **`gate=all` ⟹ byte-identical action sequences to today's ungated arbiter**, ≥20 seeded games.
2. ⭐ **`gate=none` ⟹ byte-identical to the unmodified champion**, same seeds.
3. ⭐ **Golden table on the boundary**, pinning all seven values of §2.2 — `71,49→early`;
   `47,25→mid`; `48,24,23→late` — asserted **against the python
   `sample_agreement_roots.phase_bucket`** rather than against a hand-written expectation, so the
   two implementations cannot drift.
4. **Partition:** `fired_early + fired_mid + fired_late == fired_plies` on `gate=all`, same seeds.
5. **Disjointness:** on `gate=early`, `fired_mid == 0 and fired_late == 0 and fired_early > 0`.
6. Fail-soft is unchanged: a gated-out ply is **not** an error and must not touch `tiearb_errors`.

**Estimate: 2–3 h.**

### 7.6 Build item 5 — this pair's own instrument

`run_cells.sh`, `analyze_phasegate.py`, `screen_lib.py`, `selftest_fixture/`, `WORKERS.conf`,
`BAND_CLAIM.json`, `tests/test_phasegate_instrument.py`.

⭐ **Fork `measurement/invasion_screen_r3_prep/screen_lib.py` rather than writing fresh** — reuse
`cross_box_rev_gate()` (`:1141`, the **IS-A1 fold**: pins agree *and* every emitted rev canonicalizes
to the 40-hex pin, ⛔ never box-rev-vs-box-rev), `paired_margin()` (the independent
`math.fsum` re-implementation that powers `RECON` and can only **void**, never move, a number),
`rev_matches()` and `is_hex40()`.

⛔ **Two gates must be REWRITTEN, not copied** — an unedited copy voids every healthy cell:
`G-DECKS` (this round's ranges **overlap by design**, §5) and `G-LEAF` (here the two sides carry the
**SAME** leaf, §2.4). Plus one new: `G-SUBPOOL` (§6.5).

⛔ **IS-D1 IS BINDING ON EVERY ADDRESS:** config-shaped values resolve from **`manifest.json`**;
statistics from **`summary.json`**, which carries **no config block at all**. A precheck that reads
`config` off `summary.json` gets `{}` — fails closed on one conjunct and passes **vacuously** on
another. And IS-D1's own instrument-hardening note applies directly: **any launcher-side gate that
runs once per round needs its own selftest fixture**, because the smoke will not exercise it.

**Estimate: 6–8 h.**

### 7.7 Build total, and the wheel consequence

**15–20 h of agent time, 0 compute.** Built in a **git worktree** (`feedback_worktree_isolation_live_tree`
— the rust change touches shared source; spawn respawns and each new `--shared-claim` cell re-import
from disk), merged at a quiet window.

⚠️⚠️ **THE RUST CHANGE REBUILDS THE WHEEL ⇒ `carc_rs_binary_sha` CHANGES ⇒ THE PRODUCTION ARBITER'S
`IDENT` INHERITANCE IS RE-OWED** (the `G-WHEEL-SAME` rule: *"a changed wheel RE-OWES an IDENT
cell"*). §2.1's `IDENT` cell discharges it for this round. Any *other* live pair inheriting an
earlier ident across this wheel change must be told.

⛔ **Install the SAME WHEEL FILE on both boxes** — scp + `pip install --force-reinstall --no-deps`.
**NEVER a laptop-local `maturin build`**: different bytes, different `carc_rs_binary_sha`,
`G-WHEEL-SAME` refuses, and it is right to.

---

## 8. PRE-LAUNCH CHECKLIST — executor-owed, if and when funded

| # | Artifact | Where | Who |
|---|---|---|---|
| 1 | ⛔⛔ **`PINNED_SRC_REV` on *BOTH* boxes, byte-identical** — `git -C <repo> rev-parse HEAD > measurement/phasegate_prep/PINNED_SRC_REV`, run separately on each box **after** the bundle sync. The IS-A1 defect turned on. | each box | executor |
| 2 | `BLIND_COMMIT` stamped with the freeze commit's own 40-hex sha; `WORKERS.conf::BLIND_COMMIT` moved off `PENDING`. | repo | orchestrator |
| 3 | Bundle-sync the laptop (`reference_offline_git_bundle_sync` — remotes cannot reach github), then re-run step 1 there. | share → laptop | executor |
| 4 | Install the **same wheel file** on both boxes (§7.7). | both boxes | executor |
| 5 | ⭐ `IDENT-BITEXACT` selftest (§7.5 tests 1–2) → exit 0. **A HARD ABORT.** | local | executor |
| 6 | `python3 analyze_phasegate.py --selftest` → exit 0. | local | executor |
| 7 | §9 smoke on **each** box at that box's own frozen W, on a throwaway band, ending in the adjudicator's `--smoke-mode`. | both boxes | executor |
| 8 | Process census by **FULL ARGS** (`ps -eo args`) on both boxes (§6.4). | both boxes | executor |
| 9 | Re-run the §5 tree sweep; abort if `154000000000` appeared. Then append `BAND_CLAIM.json::_csv_row`. | repo | orchestrator |
| 10 | **THEN** drop `BAND_CLAIMED` and `chmod +x run_cells.sh`. | each box | orchestrator |
| 11 | Launch **detached** (`setsid nohup … & disown`; laptop via `ssh host 'bash -s' < file.sh` with `cd` on line 1 — the inline `cd` form is stripped in transit) and **arm a completion Monitor on each box**. | both boxes | executor |
| 12 | `RUN_LIVE.json` sentinel — note the **freeze-latch hook**: main-tree commits mechanically refuse while any `measurement/**/RUN_LIVE.json` exists. | repo | orchestrator |

---

## 9. THE SMOKE

Per box, at that box's frozen W, on throwaway band `154999999000+`, **production knobs**, only the
game count reduced: local runs an `ARB_EARLY`-shaped leg, laptop an `ARB_FULL`-shaped leg, 22
games each. Each leg ends by running this pair's own adjudicator in `--smoke-mode`.

⛔ **The smoke emits NO outcome key.** Structural keys only (the Stage-2 `G-SMOKE` ruling: the
emitter whitelist is a **WRITE** surface, the gate a **READ** surface that fires only on forbidden
**OUTCOME** keys at any depth). Both must PASS before any real deck.

⭐ **The smoke's one substantive job beyond liveness:** it returns the **realized per-phase fired
counts** (§7.2), which is the first real measurement of §6.2's proxy — and if the early share is
materially above 0.3380, the ETA is revised **before** the round starts rather than discovered
inside it.

---

## 10. WHAT THIS ROUND CANNOT DO

- ⛔ It does not measure the **owner-hole** (§1.1). No branch touches `measurement/e4_games/`.
- ⛔ It does not license a **phase-gated deploy** (§1.3).
- ⛔ It does not measure the **B=64 production arbiter** (§2.3).
- ⛔ It does not prove **family-blindness** on its own — the offline early cut may simply have been
  underpowered (§1.1). Out-of-family corroboration would be a separate, cheap, later act, and the
  F4 lesson says it must come from a **judge-free** source or an out-of-family judge, never from
  the same oracle family.
- ⛔ It does not test that the slices sum to the whole, because they need not (§1.2).
- ⛔ It licenses **no** `PRODUCTION.yaml` change on any branch.
