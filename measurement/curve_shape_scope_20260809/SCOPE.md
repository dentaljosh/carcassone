# MEEPLE-CURVE **SHAPE + PHASE** SEARCH — SCOPING DOCUMENT

> **STATUS: 📋 SCOPE ONLY — NOTHING RUN, NOTHING FUNDED, NO BAND CLAIMED, `PRODUCTION.yaml` UNTOUCHED.**
> Written 2026-08-09 from the 2026-08-08 archaeology ([LEVER_INDEX](../../docs/LEVER_INDEX.md) rows
> "curve SHAPE search" and "turn/phase-indexed meeple value"). No compute was spent producing it.
> Deliverable = a decision. The runnable protocol conditional on funding is
> [PREREG_DRAFT.md](PREREG_DRAFT.md).
>
> **HEADLINE RECOMMENDATION: do NOT fund the sweep yet. Fund a ~3 h, 4-cell
> CURVATURE PROBE first** (§6) — it is the cheap ceiling measurement that decides whether the
> ~4-box-day sweep is measurable at all, and the existing record already leans "probably not."

---

## 0. What this is, in one paragraph

The production leaf's largest single term is the meeple-economy curve
(`v29_meeple_curve`, CL-074: whole term ≈ −300 elo when knocked out, of which the SHAPE — as
opposed to a flat meeple bonus — is ≈ −177 walled / ≈ −136 under `fixed_v1`). That shape is an
**8-entry hand-written table** ([V29_CANDIDATE_TERMS.md](../v29_leaf_audit/V29_CANDIDATE_TERMS.md) §B,
2026-06-25), and the entire shape record is a **single wave of 5 hand-picked shapes**
([V29_RESULTS.md](../v29_leaf_audit/V29_RESULTS.md) Wave-2), which ended in a declared
**statistical tie** between `Bflattop` and `Bmild` — production is `Bmild` × 1.25, i.e. the
winner of a coin-flip. Everything measured since (Wave A, C5, T3, capscurve) moved the **scale**,
never the shape. This document scopes what it would take to search the shape properly, and a
second axis nobody has ever run in the modern era: making the curve depend on `k_remaining`.

---

## 1. Parametrization

### 1.0 First, the arithmetic that dissolves Joshua's "4600 permutations at n=400 each"

The worry is well-placed but it prices the wrong object. Three reductions, in order:

1. **4600 is the DOMAIN, not the search space.** The 8-entry table is a *lookup table over
   game states* — it is consulted thousands of times per search. Its *parameters* are 8 numbers.
   No candidate costs more to evaluate than any other (two table lookups; runtime ≈ 0 per
   `V29_CANDIDATE_TERMS.md` §B).

2. **8 numbers are really 7, and the 8th is a mathematical no-op.** The term is
   `curve[m_self] − curve[m_opp]` — a **differential**. Adding a constant `c` to every entry
   cancels exactly, in every state, always. So exactly one degree of freedom is unidentifiable
   and one entry MUST be pinned. Production pins `curve[3] = 0` (3 free meeples; the LEVER_INDEX
   calls this "4-free" by 1-based entry position — **the two namings disagree, use the index**).
   ⚠️ **This retires one of the LEVER_INDEX row's named sub-levers outright: "zero-point
   re-placement" cannot be a lever.** A pure translation of the table is provably a no-op.
   (Wave-2's `Bxaggr` looked like a zero-point move but is not one — its *gaps* differ from
   `Bmild`'s: 10,5,4,2,1,1,1 vs 4,3,1,2,1,1,1. It was killed for its shape, not its zero.)
   ⇒ **The true search space is the 7 non-negative gaps between consecutive entries.**

3. **One of those 7 d.o.f. is the overall SCALE, and the scale is the one axis already swept
   three times** (C5 ×0.75–2.0 → curve125/CL-051; T3 scalar [0.8,1.45] → CL-057 null; capscurve
   ×1.00/×1.50 under `fixed_v1` → null-but-underpowered). Normalize it out and search the
   **6-dimensional shape simplex** at fixed scale, re-checking scale only for a winner.

So: **6 effective dimensions, and Optuna evaluates ~40 candidate curves total**, most of which
die at a cheap screen under successive halving. Not 4600, and not 4600 × n=400.

### 1.1 Candidate A — interpretable low-dim parametric family ✅ **RECOMMENDED (primary)**

Generate the 8 entries from **5 parameters**, anchored at `curve[3] = 0`:

```
low side  (m = 0,1,2):   curve[3-j] = -d * (j/3)**γ            for j = 1,2,3
knee      (m = 3):       curve[3]   = 0                        (PINNED — identifiability)
top side  (m = 4..7):    increments g_1 = s0 ;  g_i = s1 * ρ**(i-2)  for i = 2,3,4
                         curve[3+i] = Σ_{u≤i} g_u
```

| param | meaning | production value | proposed range | bracketed? |
|---|---|---|---|---|
| `d` | **cliff depth** — magnitude of the lockout penalty at 0 free meeples | 10.0 | [0, 24] | ✅ both sides |
| `γ` | **knee sharpness** — γ>1 = penalty concentrated on the last meeple; γ<1 = broad | ≈ 2.0 | [0.5, 3.0] | ✅ both sides |
| `s0` | **first-spare jump** — value of going from 3 → 4 free meeples | 2.5 | [0, 6] | ✅ both sides |
| `s1` | **top slope** — the increment after the jump | 1.25 | [0, 4] | ✅ both sides |
| `ρ` | **top decay** — ρ<1 = flat top / diminishing; ρ=1 = linear; **ρ>1 = rewards hoarding** | 1.0 | [0, 1.2] | ✅ both sides |

**Why 5 and not the 4 the brief guessed.** A single saturating top (one slope + one cap) cannot
represent production exactly: production's top is *jump-then-linear* (increments 2.5, 1.25, 1.25,
1.25), which a concave-saturating form only approximates. **An inexact warm start silently makes
trial 0 ≠ the incumbent**, which would poison every contrast in the sweep — the anchor has to be
exact. `s0`/`s1` split buys that for one extra dimension. A 4-param reduction (`s1 := s0·ρ`)
exists and is offered as a cheaper sub-family, but it does *not* contain production exactly and
should only be used if compute is the binding constraint.

**Family coverage check (does it contain what we know?):**
- production `curve125` = `[-10, -5, -1.25, 0, 2.5, 3.75, 5, 6.25]` → **exact** at
  (d=10, γ=2, s0=2.5, s1=1.25, ρ=1.0). Low side check: `-10·(1/3)²=-1.11` vs −1.25,
  `-10·(2/3)²=-4.44` vs −5 — near-exact; the sweep should enqueue the *literal* production table
  as trial 0 rather than its parametric approximation, and treat the (d,γ) fit as a
  reparametrization only.
- `Bflattop`×1.25 = `[…, 2.5, 3.75, 4.375, 5.0]` → ρ ≈ 0.5. **The tie Wave-2 found is an
  interior contrast in this family** (ρ = 0.5 vs 1.0), which is exactly what we want: the family
  spans the only shape contrast that was ever measured, and extends past both ends of it.
- `Bxaggr` (killed) → d ≈ 20, γ ≈ 1.1 (broad, deep). Also inside the family. Good — the family
  contains a known kill, so the sweep has a built-in sanity direction.

**Limitation, stated up front:** the family is monotone and (for ρ≤1) concave on the top. A
*convex* top — "the 7th meeple is worth more than the 5th" — is only reachable at ρ>1, and
non-monotone curves are excluded entirely. Wave-2's reasoning ("don't reward hoarding the last
meeple") and the `Bxaggr` kill both support that restriction, but it IS a restriction.

### 1.2 Candidate B — free per-entry search with monotonicity constraint (7 params)

Search the 7 gaps directly, each ≥ 0, with the sum pinned to production's (scale held). Strictly
more expressive than A — reaches non-parametric shapes, convex tops, plateaus mid-curve.

**Not recommended as primary.** It buys expressiveness we have no evidence we need, at the price
of 7 correlated dimensions for a TPE sampler that gets ~40 observations. Optuna's TPE with 40
trials in 7-D is barely better than quasi-random. **Recommended role: a follow-up only if
Candidate A finds a real, confirmed edge and we want to know whether the parametric constraint
was leaving anything on the table** — i.e. B is a *refinement of a winner*, never a discovery
instrument at this budget.

### 1.3 Candidate C — parametric family × the PHASE axis

Multiply the whole curve by `f(k_remaining; β)`:

```
f(k; β) = clip( 1 + β * (k - K0) / K0 , 0.0, 2.0 )      with K0 = 35 (mid-deck)
f is then RENORMALIZED so that E[f] = 1 over the empirical k-distribution of a game.
```

- `β = 0` → production (no phase dependence). **Interior**, so bracketed both ways.
- `β > 0` → meeples worth less as the deck empties (the `v28_meeple_recovery_t0` intuition;
  Joshua independently reinvented it 2026-08-08).
- `β < 0` → **meeples worth MORE late — never tested, in any era.** Not obviously wrong: late
  meeples are the ones that can still be *placed and scored*, and the endgame handoff means the
  leaf is what prices the pre-handoff phase.

**Why this is not just re-running the v28 kill.** The kill (−75 elo vs the flat term, 2026-06-22)
is real but era-bound and, more importantly, **confounded**:

1. It scaled the **flat** `meeple_k` term. The modern object is the **curve** — and CL-074 says
   the shape carries ~136–177 elo of the term. Phase-modulating a shape is a different object
   from phase-modulating a scalar.
2. Measured pre-curve, pre-PUCT, pre-`fixed_v1`, pre-rust, under random-expansion UCT at n=200.
3. **ONE never-bracketed `t0` (=72, the full deck), i.e. an endpoint** — the exact pattern the
   bracket rule and the CL-051 false-negative history warn about.
4. **The confound that matters most: `min(1, k/t0) ≤ 1` everywhere, so it does not only change
   the phase profile — it lowers the term's MEAN MAGNITUDE.** C5 later showed that axis is worth
   ±60 elo on its own. The v28 cell therefore measured "phase profile + a scale cut" and
   attributed the loss to phase. **The `E[f]=1` renormalization above is the fix, and it is the
   single reason this retry is methodologically new rather than repetitive.** Its own autopsy
   already falsified the recovery *mechanism* ("flips came from magnitude crossing rank
   boundaries") — which is a statement that it was measuring magnitude, not phase.

**Recommended role: a separate, cheap, 1-D DOSE LADDER — not an Optuna dimension.** β is one
parameter with a signed, ordered prior. Per the "a trend beats underpowered steps" rule, a
5-point ladder (β ∈ {−0.6, −0.3, 0, +0.3, +0.6}) with a **fitted within-deck slope** across the
ladder is a strictly better instrument than 5 independent underpowered cells, and it costs ~2 h.
Folding β into the shape sweep would add a 6th/7th dimension and throw away the ordering prior.

### 1.4 Recommendation summary

| | instrument | when |
|---|---|---|
| **Primary** | **Candidate A** (5-param family, 6 effective d.o.f. after scale normalization), Optuna TPE + successive halving | conditional on the §6 curvature probe |
| **Secondary, independent** | **Candidate C** as a 1-D β ladder with slope fit | can run standalone; cheapest live item here |
| Deferred | **Candidate B** free-gap search | only as a refinement of a confirmed A-winner |

---

## 2. Search design

### 2.1 What T3 got wrong, and the two fixes

T3 ([OPTUNA_KNOB_SWEEP_DESIGN.md](../classical_search/OPTUNA_KNOB_SWEEP_DESIGN.md), CL-057) ran
exactly the machinery proposed here — TPE `multivariate=True`, 32 trials, 3-rung successive
halving (n=52 → 120 → 240) — and returned a **null after 27.9 h**. Its Stage-1 *did* fire two
candidates at the +30/z2.0 gate (t020 +36.3/z2.97, t27 +34.9/z2.35). Both died at the fair gate:
t27 was the incumbent in disguise, and t020 collapsed from +32.1/z1.68 at n=400 to **+3.4/z0.73**
when extended to fresh decks. Two distinct causes, and this design must fix **both**:

**Cause 1 — PLANE MISMATCH.** T3 optimized on the **clairvoyant** plane and promoted on the
**fair PIMC** plane; clairvoyant edges wash out ~4:1 under PIMC (CL-045/CL-048). It was
optimizing a proxy.

> **FIX: screen on the plane that promotes.** Every stage of this sweep runs **fair PIMC at the
> production deploy budget `k8 × 1376 = 11008`**, `fixed_v1` + R9, rust both sides
> ([PRODUCTION.yaml](../../governance/PRODUCTION.yaml) `fair_deploy`). This was unaffordable in
> T3's python era and is affordable now: the rust port collapsed an n=400 cell from ~7.5 h to
> ~45–50 min. **The rust port is what makes this design newly possible.** It also fixes the
> budget mismatch T3 flagged separately (knob optima are budget-dependent) — screen budget =
> deploy budget, no transfer step, no attenuation to argue about.

**Cause 2 — SELECTION BIAS INSIDE THE RUNGS.** T3's own design priced it: "under the global null
the selection cascade hands the winner an expected **+10–20 elo of selection bias** at rung C
(40 of its 240 games were selected ON)", with a pre-registered global-null false-fire probability
of **15–25%**.

> **FIX: fresh decks at every rung.** A trial's screening games are NEVER pooled into its confirm
> read. Halving selects; the next rung re-measures from zero on a new deck range. The final
> promotion read runs on a **sealed** band claimed after the candidate is frozen. This costs
> games (no reuse) and buys the only thing that matters — an unbiased confirm.

### 2.2 Warm start and controls

- **Trial 0 = production `curve125`, literal table**, enqueued (not sampled). Its read against
  the champion is an **identity cell and must come back ≈ 0** — the S0 wiring gate. Both
  `capscurve` and the C5 sweeps prove out the `--cand-leaf-json` path; the manifest must show
  candidate/champion leaf hashes differing exactly as intended (`a36d2e15…` for production).
- **Trial 1 = `Bflattop`×1.25** (ρ=0.5), enqueued. Known tied with production at the v2.9 era.
  ⚠️ **A re-found tie here is CONFIRMATION, not news, and must not be written up as a finding.**
- **Trial 2 = `Bxaggr`×1.25**-equivalent (d≈20, γ≈1.1), enqueued as a **negative control**. If a
  known-killed shape does NOT read clearly negative, the instrument is broken and the sweep aborts.
- Remaining trials: 10 QMC startup + ~27 TPE, `TPESampler(multivariate=True)`, seeded, SQLite storage.

### 2.3 Stage ladder

| stage | what | n (games, deck-paired) | decks | gate to advance |
|---|---|---|---|---|
| **S0** | wiring smoke: identity cell + negative control | 100 / 200 | 50 / 100 | identity \|elo\| < 25 **and** `Bxaggr` clearly negative; manifest leaf-hash check |
| **S1** | screen, all ~40 trials, fair k8×1376 | 200 | 100 | rank by **paired point margin**; keep top 10 |
| **S2** | confirm survivors, **fresh decks** | 400 | 200 | margin z ≥ 2.0 **and** ≥ +25 elo; keep top 2 |
| **S3** | fair confirm, **fresh decks**, C5-precedent depth | 900 | 450 | margin z ≥ 2.0 **and** win-paired z ≥ 2.0 (both parts, as CL-051) |
| **S4** | promotion read, **SEALED fresh band**, candidate frozen | 1600 | 800 | the promotion bar (§5) |

Deck-band discipline: **fresh band per stage**, claimed in
[BAND_REGISTRY.csv](../../governance/BAND_REGISTRY.csv) via `csv.writer` (8 fields, `newline=''`;
the file contains quoted commas and doubled-quote escapes — hand-editing is the wrong tool) in the
same commit that pre-registers the stage, `status=claimed`, before game 1, flipped to `retired` at
close-out. **All contrasts within-band only**; no pooling across bands, and any cross-band remark
carries the ~1.5–2× σ inflation. Highest currently-registered band is `1.06e11` with unregistered
share consumption at `1.09e11` ⇒ **start at `1.10e11`**, verified at launch by BOTH the registry
and a `grep seed_start` over the share manifests (the registry's own caveat: results.csv has no
band column and the naive check fails silently open).

### 2.4 Operational riders

- `OPENBLAS_NUM_THREADS=1` on every worker. The C5 ×1.75 cell hung at 141/400 from OpenBLAS
  thread oversubscription and produced a **hang-biased +134** that looked like a discovery.
- Never route a candidate through `make_production_champion` — `champion_factory.verify_leaf`
  hard-raises unless the curve is exactly `CURVE125`. Candidates go through
  `eval_fair_puct --cand-leaf-json` only.
- Local box dirty-crashed 3× on 2026-08-04 (one at near-idle): per-cell checkpointing, and
  `--shared-claim` hygiene (clean claims-without-records before any resume).

---

## 3. Power arithmetic, honestly

Standing figures (near wr 0.5, `σ_elo ≈ 695·√(0.25/n)` unpaired; deck pairing ≈ halves variance):

| n (games) | 1σ unpaired | **1σ deck-paired** | **2σ paired = what the stage can VERDICT** |
|---|---|---|---|
| 200 | ±24.6 | **±17** | **±35 elo** |
| 400 | ±17.4 | **±12** | **±25 elo** |
| 900 | ±11.6 | **±8** | **±16 elo** |
| 1600 | ±8.7 | **±6** | **±12 elo** |

**The empirical fair-plane check, which is the one that binds.** The C5 fair confirm of curve125
— a **+48.8 elo** effect — resolved at **451 paired decks** (z 3.13 win-paired / 2.77 margin), and
its n=200 fair read was an *underpowered positive* (+33.9, z +0.58) whose own analysis computed
that resolving ~1 pt/deck at z≥2 needs **~1200 decks**. Scaling that: an effect of size `E`
needs ≈ `450 · (48.8/E)²` paired decks on the fair plane.

| true effect | paired decks needed | games | two-box wall, one candidate |
|---|---|---|---|
| +50 elo | ~450 | 900 | ~1.9 h |
| +35 elo | ~875 | 1750 | ~3.6 h |
| +25 elo | ~1700 | 3400 | ~7 h |
| **+20 elo** | **~2700** | **5400** | **~11 h** |
| +15 elo | ~4800 | 9600 | ~20 h |

**What the search CAN resolve:** a shape improvement of **≥ ~35 elo** — screened at S1, confirmed
at S2/S3, promotable at S4. This is the regime C5's curve125 lived in (+48.8 fair).

**What it CANNOT resolve, and this must be said in the funding conversation:** anything at or
below **~15–20 elo**. At that size the S1 screen is blind (2σ = ±35), and confirming a single
candidate costs 11–20 h — meaning even *one* such candidate is a day of cluster, and screening 40
of them at that resolution is ~20 box-days and not fundable. **If the true headroom is ≤ ~20 elo,
this sweep returns "unresolvable", not "null".** That is exactly the outcome the capscurve
re-sweep already produced on the neighbouring axis, and its pre-registered wording is the
template: *"this screen resolves ~50 elo (unpaired) / ~35 elo (deck-paired) at 2σ, and nothing
smaller… A null on those is uninformative about ±20 elo and must not be written up as 'flat'."*

**Multiplicity.** ~40 screened trials at a 2σ threshold expect ~1 false fire under the global
null. Mitigated by: (a) a permissive screen (rank-and-halve, not a significance gate), (b) fresh
decks at every subsequent rung so no selection propagates into a read, (c) a two-part gate at S3
(margin AND win-paired, the CL-051 precedent), (d) the sealed-band S4. Compound false-promotion
under the global null ≈ 0.1–0.2%.

**Estimator choice.** **Paired point margin (pts/deck) is the PRIMARY statistic** — lower variance
than win-paired, and it is the statistic in which the question is posed ("does this shape price
meeple liquidity better?"). Win-paired elo is reported alongside and is the second half of the S3
gate. For any **ordered dose axis** (`d`, `ρ`, `β`) prefer a **fitted within-deck slope across the
ladder** to independent point comparisons — the line across a ladder is a much stronger
measurement than any of its steps, and this is the whole design of the Candidate-C β ladder.

---

## 4. Cost

**Unit costs** (all measured, rust era, `fixed_v1` + R9, two-box: local 5900XT W30 + laptop W26):

| unit | measured cost | source |
|---|---|---|
| clairvoyant @2750, n=200 paired | **7–11 min** (mean ~10) | capscurve `SWEEP_PROGRESS.tsv` |
| clairvoyant @2750, n=400 paired | ~11.5 min | `ABL_PROGRESS_fixed_v1.tsv` |
| **fair k8×1376, n=400 paired** | **~50 min** | DECISIONS 2026-08-04 (champ-vs-champ, 200 decks × 2 seats) |
| ⇒ fair k8×1376, per 100 games | **~12.5 min** | linear scaling of the above |

⚠️ The fair budget is ~4.26× sequential wall-clock vs the old deploy budget and does **not**
benefit from k-parallelism in a game-parallel eval farm (PRODUCTION.yaml's own warning). The
~50 min figure already reflects that; do not re-apply the multiplier.

**Priced plan (Candidate A shape sweep):**

| stage | cells | games each | games | two-box wall |
|---|---|---|---|---|
| S0 smoke (identity + neg control) | 2 | 100 / 200 | 300 | 0.6 h |
| S1 screen | 40 | 200 | 8 000 | **16.7 h** |
| S2 confirm | 10 | 400 | 4 000 | 8.3 h |
| S3 fair confirm | 2 | 900 | 1 800 | 3.8 h |
| S4 sealed promotion read | 1 | 1 600 | 1 600 | 3.3 h |
| | | | **15 700** | **32.7 h** |

**Overrun allowance.** T3 spent **27.9 h against a 19 h projection (+47%)** — cells scale
worse-than-linearly in n because throughput is long-tail-bound across workers, not a clean wave.
Apply +45%:

> ### 💰 **~47 h two-box wall ≈ 2 two-box-days ≈ ~3.9 box-days**, full-fire.
> Null-case (dies at S1/S2) ≈ **25–37 h ≈ 2–3 box-days** — and note T3's warning that a joint
> sweep has **no cheap early exit**: the S1 screen is 16.7 h whether or not anything survives it.

**Assumptions, visible:** two boxes available for the duration (local + laptop; the Xeon is
retired) · rust both sides, `fixed_v1`+R9, W30/W26 · fair k8×1376 at both arms · no cross-run
game reuse (fresh decks per rung — this is ~25% of the cost and is deliberately spent) · ~40
Optuna trials · game length distribution unchanged from the champ-vs-champ cell that produced the
50 min figure · local box does not dirty-crash mid-run.

**Sensitivity.** At 30 trials: ~40 h. At 60 trials: ~62 h (~5.2 box-days). The **cheap fallback**
— screen on the clairvoyant plane at 2750 (~10 min/cell, S1 drops 16.7 h → 6.7 h, total ~2.3
box-days) — **is exactly T3's mistake and is not recommended**; if compute forces it, the design
must carry an explicit fair-transfer stage and budget for a ~4:1 washout prior.

**Candidate C (β phase ladder), priced separately:** 5 cells × n=200 fair (~25 min) = **2.1 h**,
plus one n=400 fresh-deck confirm (~50 min) = **≈ 3 h two-box ≈ 0.25 box-days.** This is the
cheapest live item in the document.

---

## 5. Decision map (draft-prereg quality)

Branch precedence: **kill > unresolvable > park > promote.** Read in order; the first that fires wins.

| # | branch | condition | action |
|---|---|---|---|
| **0** | **INSTRUMENT BROKEN** | S0 identity cell \|elo\| ≥ 25, or the `Bxaggr` negative control fails to read clearly negative, or any manifest shows the wrong leaf hash / rules profile | **ABORT.** Fix wiring; no games count. |
| **1** | **KILL SHAPE AXIS** | S1: no trial reaches +35 elo with margin z ≥ 1.5, **and** the spread across the 40 trials is consistent with the null (see §6 curvature reading) | Shape axis **dead at this instrument's resolution**. Write CL. ⚠️ Word it as "no shape gain ≥ ~35 elo exists", NOT "the shape is optimal." |
| **2** | **UNRESOLVABLE** | S1 top trials sit in the +15…+35 band and do not separate from the incumbent at S2 (fresh decks) | **PARK-UNRESOLVABLE.** Record the effect-size floor. Reopen only if a cheaper instrument or a bigger box budget appears. Capscurve precedent is the template. |
| **3** | **KILL PHASE AXIS** | β ladder: fitted within-deck slope not distinguishable from 0 (\|z\| < 2), or negative in the β>0 direction (which would *reconfirm* v28) | Phase axis dead **in the modern era with the magnitude confound removed** — a materially stronger kill than v28's, and worth a CL on its own. |
| **4** | **PROMOTE** | S3 both gate parts pass (margin z ≥ 2.0 **and** win-paired z ≥ 2.0, ≥ +25 elo) **AND** S4 sealed-band read confirms at margin z ≥ 2.0 | Propose to Joshua. **Even here, `PRODUCTION.yaml` is not edited inside this scope** — promotion is a separate decision with the six-touch close-out. |
| **5** | **CONFIRMATION, NOT NEWS** | A candidate lands statistically tied with production (e.g. `Bflattop` re-found at ρ≈0.5) | Log as **confirmation of the 2026-06-25 Wave-2 tie.** Not a finding, not a CL, not a promotion. |

### Riders (each must be restated in the write-up)

- **CL-051 rider — the consumer is the search.** A leaf knob's value depends on the search that
  reads it. This sweep is valid for **production PUCT + `fixed_v1` + rust at k8×1376 only**. Any
  result is void for a different budget, a different rules profile, or a neural consumer.
- **The "bug fix shifts hyperparameter optima" rule does NOT apply here.** There is no bug. The
  curve is not wrong, it is *unsearched*. Nothing licenses re-opening previously settled optima
  on the back of this work.
- **Bflattop tie rider** — see branch 5. The one shape contrast that was ever measured came back
  tied; re-finding it is the expected outcome and is not evidence of anything new.
- **Phase-axis prior kill rider** — `v28_meeple_recovery_t0` measured −75 elo. The retry is
  licensed ONLY by the `E[f]=1` renormalization (which removes the magnitude confound) plus the
  bracketed, signed β ladder. **If the β>0 arm reproduces the loss, that is a reconfirmation and
  the axis closes for good** — write it that way.
- **Cross-band rider** — every contrast within-band; any cross-band remark carries ~1.5–2× σ
  inflation; a band that influenced a decision retires from confirmatory use.
- **Noise-signature rider** — a lone trial beating its parameter-neighbours by >1σ is a noise
  signature, not a peak. In a 5-param family this is checkable and MUST be checked: a real
  optimum has a *neighbourhood* that also reads positive.

---

## 6. The dominance-order question: is there a cheaper probe that bounds shape headroom?

This is the F13 lesson applied in advance — a cheap ceiling measurement killed an expensive lever.
Two candidate cheap probes were investigated. **One is dead; one is recommended.**

### 6.1 Offline pre-screen via the solver / sibling-discrimination ruler — ❌ **NOT VIABLE**

The machinery exists and is *already wired for this exact input*:
`scripts/canonical_az/solver_score.py` scores a **bare leaf eval with no search**
(`make_variant_leaf_ranker` = `tanh(virtual_score_v2(child)/15)` over root children), takes
`--leaf-variant NAME:{"V29_MEEPLE_CURVE":"…"}` directly, scores every ranker against one cached
exact `SolveResult` (solve-once-score-many, so 50 candidates cost the same as 1), and returns
solver regret / top-1 / Kendall τ over 1,119 K≤2 roots. Marginal cost ≈ **20 s per candidate**
(~1.5 s with the Cython leaf) — about **1000× cheaper** than a game cell. It looks perfect.

**It is measured to have exactly zero resolution on this term.** From
[value_unlock READOUT](../value_unlock_20260730/READOUT.md) §4.3b: `curve125` and `curve100`
**pick the same child on 1119/1119 roots** — mean Δregret exactly 0.0, τ differing at ~1e-5.
Those two curves are separated by **+48.8 fair elo** (CL-051). The ruler scores a ~50-elo
difference as *identically zero*. Mechanism: the corpus is K≤2 endgames, where meeple liquidity is
near-constant across siblings by construction — and that is precisely the region the deployed
agent hands to the exact solver anyway.

And the correlation question has been asked before and answered the wrong way, three times:
- **DECISIONS 2026-07-05:** "the K≤2 solver-endgame screen does **NOT** predict full-game leaf
  strength" — `cap6` won the offline screen (τ 0.615→0.648) and read **+4.3 / z 0.45** at n=400
  in games. That is a direct, funded test of exactly this dominance order, and it failed.
- **CL-034 (LEVER_INDEX):** an LTR ranker beat the v2.9 leaf outright offline (regret −41%, top-1
  0.464→0.535) and **no LTR result has ever converted through search** — four integrations, all lost.
- **CL-063:** 10,047 midgame roots, best offline survivor ρ = +0.05, funded to 5 doses × n=400 →
  **flat-to-negative at every slope.** The best-resourced attempt at this exact pattern.
- **CL-073 is the converse, not support.** It shows outcome prediction and sibling discrimination
  *dissociate*; its own READOUT §4.4.1 disclaims strength-proxy status ("offline regret ≠ online
  search value… A win here would have funded the blend test and nothing more").

Could a *better* corpus fix it? It would need **midgame** roots (K ≈ 20+) with per-child labels
from a reference that does **not** use the curve125 leaf — otherwise the ruler is circular
(scoring candidate curves against a teacher that already believes production). Exact solve at
K≈20 does not exist; the existing midgame corpora are either v2.7-era h3200-labelled (no
established elo correlation) or root-level-only (`leaf_residual_mining` stores no per-child Q map,
so it cannot score an ordering without re-running searches). And `scripts/measurement_infra`
labels come from the champion's own deep search — circular by construction.

> **Verdict: no offline pre-screen. Do not build one.** If anyone proposes one later, the
> pre-registered admission gate is: **it must first recover the known CL-051 ordering
> (nocurve −92.5 < ×0.75 −34.9 < ×1.0 = 0 < ×1.25 +48.8) with separation.** An instrument that
> cannot see a 140-elo spread has no business screening a 20-elo one.

### 6.2 The record already contains a partial ceiling — and it argues *small*

CL-074 bounds the shape's total contribution: `meepleflat` reads −136 (`fixed_v1`) / −177
(walled). ⚠️ **Read that narrowly: it prices shape-vs-*flat*, not production-shape-vs-*best*-shape.**
It is an upper bound on headroom (the best possible shape cannot beat production by more than the
shape term is worth in total), but a very loose one.

The *tighter* prior is Wave-2's outcome: five hand-picked shapes spanning a wide range produced
four that were statistically tied (+46 to +58, ±~12–22) and one that broke (−7). **A response
surface with a broad tied plateau and a cliff at the edge is a surface with little to win near
the incumbent.** Production sits in the middle of the plateau.

### 6.3 ✅ **RECOMMENDED cheap probe: the 4-cell CURVATURE PROBE (~3 h, one band)**

Rather than an offline proxy (dead) or the full sweep (~4 box-days), spend **~3 hours** measuring
whether the shape response surface has any curvature the instrument can see:

| cell | shape | purpose |
|---|---|---|
| C-0 | production `curve125`, identity | wiring gate; must read ≈ 0 |
| C-1 | ρ = 0.4 (hard flat top, beyond `Bflattop`) | one end of the top axis, past the known tie |
| C-2 | γ = 0.8, d = 16 (broad deep low-end penalty) | the low-end axis, deliberately far from production |
| C-3 | ρ = 1.2 (rising top — **rewards hoarding**) | the direction production is NOT in; bracket ABOVE |

Four cells × n=400 fair k8×1376 ≈ **3.3 h two-box**, one fresh band, `fixed_v1`+R9, rust.

**Reading, pre-registered:**
- **If C-1/C-2/C-3 all read within ±25 elo of production** → the response surface is **flat over a
  wide neighbourhood at this instrument's resolution.** A TPE sweep searching that surface with a
  ±35-elo screen cannot find anything. **⇒ Do not fund the sweep.** ~3 h saved ~4 box-days, and
  that is the F13 pattern reproduced.
- **If any cell reads ≤ −40** → there IS real curvature and production sits on a genuine ridge.
  The sweep becomes a reasonable bet (a surface with structure can have a nearby better point).
- **If any cell reads ≥ +35** → a hand-picked shape beat production on the first try. Fund
  immediately, and go straight to S2/S3 on that candidate rather than running the sweep.

This probe also **doubles as the sweep's S0** if funded, so it is not wasted work on either branch.

---

## 7. Explicit non-goals

1. **No `PRODUCTION.yaml` change in this scope.** Not by this document, not by the probe, not by
   the sweep. Promotion is a separate decision with the six-touch close-out.
2. **The sweep itself is a separate funding decision.** This document prices it; it does not
   authorize it. The only thing recommended for funding here is the §6.3 curvature probe.
3. **Superhuman is not the claim.** This is a leaf-quality lever with an **unknown ceiling** and
   a prior (§6.2) that the ceiling is low. It does not touch either structural blocker — not
   measurement, and not "the hand-crafted leaf caps learned strength." Making the hand-crafted
   leaf slightly better is, if anything, orthogonal to the learned-track question.
4. **No new rules scope, no new game features, no engine changes.**
5. **No claim about the K≤2 offline ruler's general validity** — §6.1 is a statement about *this
   term* plus a citation of three prior failures, not a global condemnation of offline rulers.
6. **Candidate B (free-gap search) is not scoped for execution here** — it is named so that a
   future reader's grep finds it with its reason for deferral attached.

---

## 8. One-line recommendation

**Fund the §6.3 curvature probe (~3 h two-box, one band); fund the full ~4-box-day sweep only if
that probe shows curvature ≥ the instrument floor — and run the ~3 h Candidate-C β ladder
alongside it, since it is the only genuinely never-tried axis in this document.**
