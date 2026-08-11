# THE BUDGET-HEADROOM DECAY BOUND — how much strength is left above 11008?

> **STATUS: ✅ ASSEMBLED AND TIGHTENED 2026-08-09 — §7'S ONE CHEAP MEASUREMENT WAS FUNDED AND
> RAN THE SAME DAY. READ [§9](#9-results--the-7-measurement-ran-2026-08-09) BEFORE CITING ANY
> NUMBER IN §4.3 OR §8.**
>
> **⚠️ THE +54 ELO CENTRAL BOUND IS SUPERSEDED. Do not cite it as current.** §7's decision map
> fired **branch 2 (`price ≪ 0.2`)**, and it fired **POWERED**: the measured price at the
> top-of-ladder pair 5504-vs-11008 is **+0.0673 pts/disagreement** (n=150, 126 roots,
> cluster-robust se 0.2041, **z +0.33**, p 0.742, bootstrap 95% CI **[−0.330, +0.467]**) against
> the memo's own P-constant point prediction of **+0.511** — which would have read z = 2.5 at
> the realized se, and which sits **outside** the CI's upper bound. Budget-invariant price is
> **refuted at the extrapolation point**, not merely unconfirmed.
>
> **RE-STATED BOUND: ≈ +0.57 pts/game ≈ +7 elo central (+7.7 at σ_game 20.4, fixed_v1), honest
> bracket ≈ [−35, +49] elo — it now spans zero.**
>
> **The mechanism, and the actual finding:** the *rate* of budget-attributable disagreement did
> NOT keep decaying at the top rung (Δ₄ 0.0173 → Δ₅ 0.0206, r₄ > 1 — that part of §6(iii)'s
> anomaly is real in the data), but the *price* of a disagreement **collapsed** (+0.7375 over the
> 2752→11008 composite vs +0.0673 over its top half alone) ⇒ **essentially all of the composite's
> value came from the 2752→5504 half, and above 5504 the deeper pick MOVES but does not IMPROVE.**
> The geometric family is not withdrawn — the decay is still there, it just lives in the PRICE
> rather than the RATE, which is exactly the quantity §3.2 assumed constant and flagged as *"the
> single largest unbraced lever in the whole assembly."*
>
> Everything in §1–§8 was desk assembly off data already on disk. §9 is the one run. Both
> structural caveats of §6 still point the same way (bound too high), and §6(ii)'s in-family-judge
> caveat is if anything **sharper** now: a same-family judge should FAVOUR the deeper pick, and it
> did not. No CL id, no `results.csv` row, `governance/PRODUCTION.yaml` untouched.

---

## 1. The question and why the obvious route is broken

"How much strength is left in raw search budget above the deployed 11008?" The obvious route —
extrapolate the measured elo-vs-budget curve — is confounded, and the project has the receipts:

- **CL-069 / `blindcurve_*`** reads the top of the ladder as *flat* (2752 → +127.0, 5504 → +94.3,
  11008 → +105.6 elo vs a fixed sighted RoD-v2 anchor; `experiments/results.csv`,
  rows `blindcurve_k4x{688,1376}_*`, `blindcurve_k8x1376_11008_vs_sighted_rodv2_b70e9`).
- **CL-060** measures the *same* budget move directly, head-to-head, at **+49.85 ± 17.55**
  (`results.csv cl060_h2h_k8x1376_vs_deploy_k4x688`).

Those two disagree by ~70 elo *including the sign of the top-of-ladder slope*. That is ruler
compression, not physics, and it is exactly why CL-070 was built with **no opponent, no elo and
no ruler** in the loop.

**The salvageable version of the extrapolation** (Joshua's framing): pick an *opponent-free*
statistic, measure its **per-doubling** value, fit the **decay ratio r** between successive
doublings, and — if the decay is approximately geometric — bound the total remaining headroom
above budget *B* by the convergent sum `H = g_next / (1 − r)`.

---

## 2. Step 0 — prior-art check (mandatory, and it CLEARS)

Grepped `docs/LEVER_INDEX.md`, `DECISIONS.md`, `docs/PROGRAM_ROADMAP_2026-07-07.md`,
`STATUS.md`, `measurement/classical_search/*` and the whole tree for
*headroom / decay / geometric / extrapolat / budget curve / remaining gain / convergent sum*.

**Verdict: the pieces all exist; NOBODY HAS MULTIPLIED THEM THROUGH.** What exists is one
adjacent artefact that must be credited, because this memo reuses its conversion chain:

- **`measurement/classical_search/KWIDTH_110K_READOUT_20260802.md` §"The ladder"** already prints a
  three-rung table of *measured* pairs (2752→11008, 11008→22016, 11008→110080) with a
  pts/move → elo conversion, and explicitly says *"Do not promote the shape; it is what a
  follow-up would test, not a finding."* **This memo is that follow-up.** It differs by (a)
  using the full **adjacent-doubling** Δ matrix rather than three non-adjacent pairs, (b)
  fitting a **decay ratio** rather than eyeballing a shape, and (c) stating a **summed bound**.

No LEVER_INDEX row existed for the bound itself; one has been added
(*"budget-headroom decay bound / geometric extrapolation"*).

---

## 3. The pieces, verified

### 3.1 The opponent-free per-doubling statistic — CL-070's Δ matrix

`measurement/classical_search/MOVE_AGREEMENT_REPORT.json` carries the **full pair matrix**
(21 pairs over 7 budgets), not just the 2752-vs-11008 headline. Fields per pair: `D_paired`,
`D_cross`, `D_cross_null`, `Delta`, `Delta_ci95`, `Delta_z`. **Δ = D_cross − D_cross_null** is the
disagreement attributable to *budget* after subtracting the matched same-budget reseeding floor
(`floor`: 0.1226 @344 → 0.2997 @11008). n = 873 positions, 2694 records, 0 failed.

**The five adjacent doublings (this is the assembly's spine):**

| doubling | Δ (overall) | 95% CI | Δ_z | D_paired | Δ (narrow-gap, n=437) |
|---|---|---|---|---|---|
| 344 → 688 | **0.0866** | [0.0702, 0.1034] | 10.12 | 0.2104 | 0.1463 |
| 688 → 1376 | **0.0497** | [0.0381, 0.0621] | 8.12 | 0.1764 | 0.0832 |
| 1376 → 2752 | **0.0287** | [0.0185, 0.0393] | 5.43 | 0.1802 | 0.0487 |
| 2752 → 5504 | **0.0173** | [0.0094, 0.0258] | 4.13 | 0.1749 | 0.0247 |
| 5504 → 11008 | **0.0206** | [0.0115, 0.0304] | 4.25 | 0.1810 | 0.0293 |

*(So: Δ **is** available per adjacent doubling — the brief's open question. The 2752→11008
headline Δ = 0.0396 is a two-doubling composite.)*

**Additivity sanity check** (Δ's are not guaranteed to add; that they roughly do at the top is
support for the per-doubling decomposition, and that they don't at the bottom is a caveat):

| composite | sum of its adjacent Δ | measured composite Δ |
|---|---|---|
| 2752→11008 | 0.0379 | **0.0396** ✅ additive |
| 688→2752 | 0.0784 | **0.0755** ✅ ~additive |
| 344→2752 | 0.1650 | **0.1234** ⚠️ **sub**-additive by 34% |

⇒ at the **low** end, per-doubling Δ's over-count (disagreements churn back); at the **top** —
where the extrapolation lives — they add. Good news for the bound's arithmetic, bad news for the
low-end rungs used to *fit* r.

### 3.2 The price of a disagreement — the oracle pilot (ONE pair only)

`/mnt/c/carc-shared/classical_search/oracle_score_pilot/summary.json` +
`measurement/classical_search/ORACLE_PILOT_EXT_READOUT_20260728.md`:
**mean_delta_pts = +0.7375** per disagreement, `se_mean_delta` 0.2406, cluster-robust **z +2.97**,
95% CI **[+0.251, +1.226]**, n_positions 100, M = 32, `crn_verified_all: true`, 0 failed,
`wall_secs` 4865.5 (**81.1 min at W16**), `population_disagreements` 628.

**This prices the 2752-vs-11008 pair and nothing else.** It is measured *per D_paired
disagreement*, so the correct per-move product is `D_paired × price`, **not** `Δ × price` — using
Δ with this price would double-subtract the noise floor. To carry the price across doublings this
memo defines the **price per *signal* disagreement**:

```
P = D_paired(2752v11008) × 0.7375 / Δ(2752v11008)
  = 0.2398 × 0.7375 / 0.0396  =  4.466 pts        [CI from the price CI: 1.52 … 7.42]
```

⚠️ **P constant across budgets is an ASSUMPTION, measured at exactly one pair.** It is the
single largest unbraced lever in the whole assembly, and §7 is about buying it.

### 3.3 The G10 10× screen — `KWIDTH_110K_READOUT_20260802.md`

**D̂ = 0.1433 ± 0.0117** (129 disagreements / 900 pick cells / 608 roots), mean Δ per
disagreement **+0.484** (CR se 0.320, z +1.51), pts/move **+0.0693** [−0.020, +0.159],
elo-equivalent **+19.4 [−5.7, +44.6]**. Verdict was *UNDERPOWERED / DO NOT FUND*.
Sibling rung 11008→22016 (n=237): D̂ 0.124, mean Δ +0.105, **pts/move +0.013 ≈ 3.7 elo**.
**No `results.csv` row exists for either** (checked; the readout is the only record).
These two are the memo's **out-of-sample checks** (§5), not inputs.

### 3.4 The non-additivity overshoot — CL-069/CL-070 era arithmetic

From `docs/LEVER_INDEX.md` (clairvoyant-champion row) and reproduced here:
`0.7375 × D_paired 0.2398 × 71.5 decisions = +12.6 pts/game` versus **≈3.98 pts/game** implied by
CL-060's +49.85 at σ_game 22.2 ⇒ **overshoot ≈ 3.2×**. This is hard-coded as
`NON_ADDITIVITY = 3.2` in `scripts/measurement_infra/analyze_kwidth110k_oracle.py:53`
(with `DECISIONS_PER_GAME = 71.5` :52 and `SIGMA_GAME = 22.2` :54, sourced to
`measurement/human_anchor/LUCK_FLOOR.md`).

⚠️ **The 3.2 divisor is n = 1 and it is calibrated at the TOP of the ladder.** §5 shows it is
too small lower down.

### 3.5 The independent low-budget value estimate — CL-069's margin slope

`results.csv blindcurve_*` note: **within-deck slope on the clean k4-only axis (344…5504) =
+2.782 pts/deck per DOUBLING (se 0.426, z +6.54, 100 decks)**; full frontier incl. the k8 rung
+2.449 (se 0.337). Within-band, deck-matched — i.e. **the robust contrast class**. This is a
*constant*-per-doubling fit (r ≡ 1 by construction over that range), so it supplies an *average*
level, not a decay, and that is precisely how §5 uses it.

---

## 4. THE ASSEMBLY

### 4.1 The decay ratio r

**Route A — pairwise adjacent ratios** (se propagated from the bootstrap CIs treating adjacent Δ
as independent; they share positions and are almost certainly *positively* correlated, so these
se's are **conservative/over-stated**):

| transition | r (overall) | ± | 95% CI | r (narrow-gap) |
|---|---|---|---|---|
| (344→688) → (688→1376) | **0.574** | 0.090 | [0.397, 0.751] | 0.569 |
| (688→1376) → (1376→2752) | **0.578** | 0.128 | [0.326, 0.829] | 0.585 |
| (1376→2752) → (2752→5504) | **0.603** | 0.183 | [0.243, 0.962] | 0.507 |
| (2752→5504) → (5504→11008) | ⚠️ **1.191** | 0.401 | **[0.405, 1.976]** | ⚠️ 1.186 |

Inverse-variance mean of the first three: **r = 0.579 ± 0.069, 95% CI [0.445, 0.713]** —
excludes 1.0 decisively. **The narrow-gap stratum reproduces it independently at 0.564 ± 0.072.**
Three transitions landing on 0.57/0.58/0.60 in one stratum and 0.57/0.59/0.51 in the other is a
genuinely clean geometric signature — this is the strongest single fact in the memo.

**Route B — log-linear fit over all five Δ** (the estimate that uses every data point):

| stratum | r_fit | ± | 95% CI |
|---|---|---|---|
| overall | **0.675** | 0.057 | **[0.573, 0.796]** |
| narrow-gap | 0.642 | 0.054 | [0.544, 0.757] |

**Both fits exclude r = 1.0 ⇒ the sum converges at measurable confidence.** The all-5 fit is
adopted as **central (r = 0.675)** because it is the only estimate that uses the top rung at all;
its residual at that rung is the anomaly of §6 (fitted Δ₅ 0.0154 vs observed 0.0206).

### 4.2 Per-doubling gain g_i, both routes

**Route (b) — Δ × P × decisions** (`g = Δ × 4.466 × 71.5 / 3.2` pts/game):

| doubling | pts/move | pts/game **uncorrected** | pts/game **÷3.2** | elo-equiv |
|---|---|---|---|---|
| 344 → 688 | 0.387 | 27.65 | **8.64** | +112 |
| 688 → 1376 | 0.222 | 15.87 | **4.96** | +63 |
| 1376 → 2752 | 0.128 | 9.16 | **2.86** | +36 |
| 2752 → 5504 | 0.077 | 5.52 | **1.73** | +22 |
| 5504 → 11008 | 0.092 | 6.58 | **2.06** | +26 |

**Closure check (not independent — it is how P was defined):** rows 4+5 sum to 3.78 pts/game =
**+47.5 elo**, against CL-060's directly-measured **+49.85 ± 17.55** for exactly that 2752→11008
move. Consistent to 5%.

**Route (a) — margin slope at low budgets (the valid-ruler regime):** +2.782 pts/deck per
doubling averaged over 344…5504. Route (b)'s ÷3.2 numbers over the *same* range average
**4.55 pts/game**. ⇒ **route (b) runs 1.64× hot at the low end even after the 3.2 correction**;
a range-consistent divisor there would be **≈5.23**, not 3.2.

⇒ **The non-additivity divisor is itself budget-dependent** (bigger where disagreements are more
plentiful, exactly as non-additivity predicts). Carried as a bracket, not a fix.

### 4.3 THE BOUND

> **⚠️ SUPERSEDED BY [§9](#9-results--the-7-measurement-ran-2026-08-09) (2026-08-09).** The table
> below is kept visible because it is the arithmetic of record and §9 re-runs *exactly this chain*
> with only `P` replaced by the measured top-rung price (feeding the P-constant price 0.51125
> through it reproduces the +54.1 elo central below, which is how §9's recomputation was
> validated). **The price is now measured at the extrapolation point and is +0.0673, not the
> assumed constant ⇒ the central collapses +54 → ≈ +7 elo and the bracket spans zero.** Cite §9.

`H = g_next / (1 − r)` where `g_next = Δ(5504→11008) × r × P × 71.5 / divisor`, i.e. the
first *unmeasured* doubling (11008 → 22016) and everything above it, summed.

| branch | r | divisor | price | **H (pts/game)** | **H (elo)** |
|---|---|---|---|---|---|
| **PESSIMISTIC** (r low, low-end divisor, price CI lo) | 0.573 | 5.23 | 1.52 | **0.57** | **+7** |
| price CI lo, else central | 0.675 | 3.2 | 1.52 | 1.45 | +18 |
| central r, low-end divisor | 0.675 | 5.23 | 4.47 | 2.61 | +33 |
| central, r from adjacent-3 | 0.579 | 3.2 | 4.47 | 2.83 | +35 |
| **★ CENTRAL** | **0.675** | **3.2** | **4.47** | **4.27** | **+54** |
| **OPTIMISTIC** (r hi, price CI hi) | 0.796 | 3.2 | 7.42 | 13.33 | **+181** |
| *no non-additivity correction at all* | 0.675 | 1.0 | 4.47 | *13.66* | *+187* |
| **⚠️ r from the ADJACENT top rung (r₄ = 1.19)** | 1.191 | — | — | **∞** | **DOES NOT CONVERGE** |

**STATED AS A BOUND:** *under geometric decay of the budget-attributable disagreement rate and a
budget-invariant price per signal disagreement, the total remaining strength available from raw
search budget above 11008 — all the way to infinite budget — is bounded around **+54 elo, with a
defensible bracket of +7 … +181 elo**, and most of it sits in the first two doublings
(11008→44032 alone accounts for ~2.3 of the 4.27 pts/game, i.e. ~55%).*

**Elo-conversion caveat.** Conversion uses the project's standard chain
(`analyze_kwidth110k_oracle.py:68-71`): `wr = 0.5 + (pts_game/σ_game)·φ(0)`, `σ_game = 22.2`
from the **walled-era** `measurement/human_anchor/LUCK_FLOOR.md`. Under the adopted `fixed_v1`
rules σ_game is **20.4** (`measurement/f9_phase_c/LUCK_FLOOR_fixed_v1.md`), which moves the
central bound 54 → **59 elo**. The linear-φ approximation also degrades above ~1σ, so the
+181 optimistic figure is the least trustworthy cell in the table.

---

## 5. Out-of-sample checks — and the bound behaves like a bound

The two rungs *above* 11008 were not used to build anything. Both land **below** the model:

| rung | model prediction (pts/move) | measured | source |
|---|---|---|---|
| 11008 → 22016 | 0.053 | **0.013** (≈3.7 elo) | KWIDTH readout ladder, n=237 |
| 11008 → 110080 (3.32 doublings) | 0.106 | **0.069** [−0.020, +0.159] (≈19.4 elo) | KWIDTH readout, n=129 |

The model over-predicts by 4.1× and 1.5× respectively. Both measured values are inside their own
wide CIs and neither excludes the model — **but the sign of the miss is consistent, and it is the
sign that makes "bound" the honest word.** Note also the 10× rung's point estimate exceeds the
2× rung's by 5× on the same instrument, which the KWIDTH readout already flagged as
*"do not promote the shape"*; it is here as an argument that the decay above deploy is **not
resolved**, in either direction.

---

## 6. THE TWO STRUCTURAL CAVEATS (load-bearing — do not cite the bound without them)

### (i) CLIFF vs GEOMETRIC — and this project has an in-house cliff

**F13 / CL-076** (`measurement/exact_k_ladder_20260803/READOUT.md`,
`results.csv f13_exactk{2,3,5,6}_fixed_v1_vs_champk4_n400`): the marginal value of one more level
of *exact* endgame depth runs **+0.31, +0.76, +0.11, −0.01 pts/deck** — it *rises*, then
**collapses ~7× exactly at the incumbent K=4 and is gone by K6**, with winrate flat at every
rung. That is not geometric decay; it is a cliff with a bump before it.

A geometric fit through a component that actually cliffs **over-states the tail**, because the
geometric tail keeps paying forever while the real component pays zero after the cliff.
**The error is in the flattering direction.** The champion's search is a composite of components
(midgame move ordering, farm-majority timing, the exact-K tail) and F13 proves at least one of
them cliffs. ⇒ **the bound is an upper-leaning bound, and the true remaining headroom is
plausibly well under the central +54.**

### (ii) THE ORACLE JUDGE IS IN-FAMILY — and that biases the bound DOWNWARD

The price P descends entirely from the oracle pilot, whose judge is a **clairvoyant PUCT agent
sharing the champion's search AND its curve125 leaf**. Same-family self-preference would inflate
+0.7375 and therefore inflate the bound. **But this was tested:** the `--oracle-policy
tier1-greedy` discriminator (30 nested rids, a greedy `RuleBasedPlayer` sharing neither search nor
leaf) gave **+0.626 pts with 80% per-position sign agreement (binomial p 0.0012, r +0.415), no
sign flip** — read against the in-family **+1.766** on that same chance-high 30-subset, **not**
against +0.7375 (the LEVER_INDEX row is explicit: *"NEVER compare +0.626 to +0.7375 as
magnitudes"*). The threat is **TESTED-AND-NOT-SUPPORTED, not excluded**, and the out-of-family
read is *lower*, i.e. **if family bias is real it inflates the price and the bound is too high**;
if the out-of-family estimate is nearer the truth the price is too high as well. Either way the
direction is the same.

⚠️ Direction summary, to be quoted with the number: **caveat (i) says the bound is too high
(flattering); caveat (ii)'s residual family bias also says too high.** There is **no identified
mechanism pushing the bound too low** other than the ÷3.2 divisor possibly being too aggressive
at the top — and §4.2 shows the divisor error at the *low* end runs the other way (5.23 > 3.2).
**Treat +54 elo as a ceiling-flavoured central, not a target.**

### (iii) The anomaly that the memo cannot resolve

**r₄ = 1.19 ± 0.40** — the ONE adjacent ratio at the top of the ladder, i.e. the only one measured
at the budgets we are extrapolating *from* — is **greater than 1** in both strata (1.191 overall,
1.186 narrow-gap), and its CI spans [0.41, 1.98]. Taken alone it says the decay has **stopped or
reversed** at deploy and the sum **does not converge**. Two readings, both live:

1. **Noise.** Δ₄ = 0.0173 and Δ₅ = 0.0206 are the two smallest Δ in the matrix with the widest
   relative CIs; their difference is z ≈ 0.5. A ratio of two small noisy numbers with a
   coincident dip at Δ₄ produces exactly this.
2. **Real.** The `D_cross_null` floor rises monotonically with budget (0.1226 → 0.2997), so at the
   top the Δ subtraction removes an ever-larger number and small mis-estimation of the floor moves
   Δ a lot; alternatively a genuine regime change (e.g. depth starting to matter for farm
   majorities that shallow search never contests) could restart the returns.

**This memo cannot distinguish them, and §7 is the cheapest thing that would.**

> **✅ RESOLVED 2026-08-09 — see [§9](#9-results--the-7-measurement-ran-2026-08-09), and the
> resolution is a THIRD reading neither of the two above anticipated.** Reading 1 (noise) is
> *wrong* about the rate: Δ₅ > Δ₄ survives as the measurement. Reading 2 (the decay has stopped)
> is *wrong* about the consequence: the decay has not stopped, it **moved from the rate into the
> price** — the extra disagreements at the top rung are worth **+0.0673 pts each** (cluster-robust
> z +0.33), i.e. the deeper pick **moves but does not improve**. The sum still converges; it
> converges to ≈ +7 elo instead of ≈ +54.

---

## 7. WHAT ONE CHEAP MEASUREMENT WOULD MOST TIGHTEN THE BOUND

**Oracle-price the 5504-vs-11008 disagreement set** — i.e. re-run the existing
`oracle_score_pilot.py` instrument, unchanged, on the adjacent-doubling pair at the TOP of the
ladder instead of the 2752v11008 composite. ~~**DO NOT RUN — costed for a decision, not
launched.**~~

> **✅ FUNDED AND RAN 2026-08-09 — see [§9](#9-results--the-7-measurement-ran-2026-08-09).**
> **Branch 2 fired (`price ≪ 0.2`): measured price +0.0673, cluster-robust z +0.33, bootstrap 95%
> CI [−0.330, +0.467], price ratio 0.091 vs the +0.7375 reference.** The costing below held up:
> 150 positions, 990.1 s at W16 (16.5 min) on `--backend rust`, against the "plausibly ~20–30 min"
> rust-era estimate. The rationale for preferring this pair to a low-end pair is vindicated — it
> converted the weakest link into a measurement, and **the link broke.** The second-cheapest
> follow-on (M → 64 on the banked 2752v11008 positions) is **moot**: it would tighten a price that
> is no longer the binding uncertainty.

Why this one and not a low-end pair (688→1376 / 1376→2752, the brief's suggestion):

- The bound is **directly proportional to `g_next = Δ₅ × r × P`**. Both of its uncertain factors —
  the constant-P assumption *and* the r₄ > 1 anomaly — live at that top rung. A low-end price
  would test P-constancy in the regime that matters *least* and where §3.1 already shows Δ is
  **sub-additive by 34%**, contaminating the comparison.
- It converts the memo's weakest link from *"assume P constant"* to *a measured price at the
  extrapolation point*, and it makes r measurable **on prices (pts/move) instead of on rates**,
  which is what the idea actually wants.
- The disagreement records **already exist** in the CL-070 bank
  (`D_paired(5504v11008) = 0.181 × ~2618 records ≈ 470 candidate positions`), so no new
  self-play, no new search corpus — only oracle scoring.

**Cost.** Pilot rate of record: 100 positions / 4865.5 s = **81.1 min at W16** (python era, M=32).
Power: with `sd_delta_positions = 2.406` at M=32, and a P-constant point prediction of
`Δ₅/D_paired₅ × P = 0.0206/0.181 × 4.466 ≈ 0.51 pts/disagreement`, z = 2 needs
**n ≈ (2 × 2.406 / 0.51)² ≈ 90 positions ≈ 75 min at W16**. Budget **n = 150 ≈ 2.0 h at W16**
for a comfortable margin — and the KWIDTH readout notes rust-era farms run **~7.3× cheaper** than
the era that priced the pilot, so the real figure is plausibly **~20–30 min**.

**Decision map, if it is ever funded:** price ≈ 0.5 ⇒ P-constancy holds, the central bound stands
and r₄ is noise. Price ≪ 0.2 ⇒ the price *falls* faster than the rate and the true bound is well
under +54 (the good outcome — headroom is closed cheaply). Price ≫ 1.0 ⇒ the r₄ > 1 reading is
real, the geometric model is the wrong family above deploy, and the bound must be withdrawn
rather than widened.

**Second-cheapest, if the above fires ambiguous:** M → 64 on the *existing* 100 banked
2752v11008 positions (`sd_delta_projected_by_m["64"] = 1.921` in `summary.json`, a 20% se cut for
zero new positions) — it tightens P but tests nothing new.

---

## 8. Bottom line

> **⚠️ BULLETS 2 AND 3 SUPERSEDED BY [§9](#9-results--the-7-measurement-ran-2026-08-09)
> (2026-08-09).** Bullet 1 (the decay is real and geometric-looking on the *rate*) stands
> unchanged. Bullet 2's **+54 elo / +7 … +181** is superseded by **≈ +7 elo, bracket ≈ [−35, +49]**.
> Bullet 3's "honest asterisk" is resolved: r₄ = 1.19 is *real*, but it no longer breaks
> convergence, because the decay relocated into the **price** — which §9 measures at +0.0673
> (z +0.33) where this memo assumed 0.511. Bullet 4 ("understanding, not a deploy lever") stands,
> and stands harder.

- The **decay is real and geometric-looking across the measured ladder**: r = 0.675 [0.573, 0.796]
  (all-5 fit), r = 0.579 ± 0.069 (adjacent-3), reproduced independently in the narrow-gap stratum.
  **The sum converges at measurable confidence on that fit.**
- The bound: **≈ +54 elo of total remaining budget headroom above 11008**, bracket **+7 … +181**,
  with ~55% of it in the first two doublings. Both out-of-sample rungs above 11008 land **below**
  the model.
- **The honest asterisk:** the one adjacent ratio measured at the extrapolation point is
  **1.19 ± 0.40**, and on that number alone **the bound does not converge**. The convergence is
  imported from the low end of the ladder, where the ruler is valid but the regime is different
  and Δ is demonstrably sub-additive.
- **This is understanding, not a deploy lever.** CL-068's clock sentence and CL-071's promotion
  both still apply: 11008 already runs at ~20.6% of a 15-min clock at `parallel_workers=8`, and
  22016 is the *first* rung this bound says anything about. Nothing here proposes a
  `PRODUCTION.yaml` change.

---

## 9. RESULTS — the §7 measurement RAN (2026-08-09)

**Funded and executed the same day the memo was assembled.** §7's decision map fired
**branch 2 (`price ≪ 0.2`)**, and it fired powered. The headline is not "the bound got smaller";
it is **the rate-vs-price relocation** in §9.5, which resolves §6(iii)'s anomaly in a way neither
of its two readings anticipated.

### 9.1 The command, verbatim

```
.venv/bin/python -u scripts/measurement_infra/oracle_score_pilot.py \
  --level-a 1376 --level-b 2752 --n 150 --m 32 --oracle-sims 100 --workers 16 \
  --out-subdir oracle_score_pilot_5504v11008 --backend rust --resume
```

Levels are `sims_per_det` at `k_dets = 4`, so `1376 → 5504 total` and `2752 → 11008 total` —
i.e. the top-of-ladder **adjacent** doubling, exactly the pair §7 pre-registered. **The instrument
is `oracle_score_pilot.py` UNCHANGED**: no adapter was needed (`--level-a/--level-b` already
existed and `load_disagreements` keys off `q_pick_by_level`), default `clair-puct` judge, M = 32
CRN worlds, `--oracle-sims 100`. Same instrument, same knobs, same judge as the +0.7375 reference
— only the pair differs. That is what makes the two prices comparable.

### 9.2 Backend — the ruler is the same ruler

The run used **`--backend rust`**. That is licensed by the committed identity gate
`measurement/rustport_p6/GATE_ORACLE_PILOT_BACKEND.json` (**20 positions, 940 field checks, 0
mismatches**, every non-timing record field compared as raw f64 bit patterns), and the gate was
**re-verified on the current revision before launch**: **8 positions, 376 field checks, 0
mismatches, speedup 9.48×**. The committed 20-position record was left in place, not overwritten
by the smaller re-verification. ⇒ the rust leg is a bit-exact conversion of the python instrument
that produced +0.7375, not a new ruler. (Scope inherited from the gate: the `clair-puct`
continuation at these knobs; `tier1-greedy` is out of scope, Gap 3 remains OPEN.)

### 9.3 Run health

| field | value |
|---|---|
| `population_disagreements` at the pair | **474** (§7 predicted ~470 from `D_paired₅ 0.181 × ~2618 records`) |
| n sampled / attempted / failed | 150 / 150 / **0** |
| distinct roots among the 150 | **126** |
| `crn_verified_all` | **true** |
| `wall_secs` | **990.1 s = 16.5 min at W16** (§7's rust-era estimate: ~20–30 min) |
| `sd_delta_positions` at M=32 | 2.2787 (the 2752v11008 pilot's was 2.406) |

Artifacts: `/mnt/c/carc-shared/classical_search/oracle_score_pilot_5504v11008/`
(`manifest.json`, `summary.json`, `records/` — 150 files, `price_analysis.json`);
log `measurement/classical_search/oracle_score_pilot_5504v11008.log`.

### 9.4 The result

Recomputed by `scripts/measurement_infra/analyze_oracle_price.py`, which **reproduces the
published 2752v11008 numbers exactly as its acceptance test** — so the two columns below are the
same estimator, not two estimators.

| quantity | **5504 vs 11008 (NEW)** | 2752 vs 11008 (the memo's price) |
|---|---|---|
| n positions / roots | **150 / 126** | 100 / 89 |
| mean Δ pts per disagreement | **+0.0673** | +0.7375 |
| sd per position (M=32) | 2.2787 | 2.4058 |
| naive se / z | 0.1861 / +0.362 | 0.2406 / +3.07 |
| **cluster-robust (root) se / z / p** | **0.2041 / +0.330 / 0.742** | 0.2486 / +2.97 / 0.0030 |
| root-collapsed mean / z | +0.1141 / +0.588 | +0.5920 / +2.45 |
| cluster bootstrap 95% CI (roots, 20000 reps, seed 20260809) | **[−0.3300, +0.4668]** | [+0.251, +1.226] |
| bootstrap P(≤ 0) | 0.365 | 0.0014 |
| design effect | 1.204 | 1.067 |

**Price ratio vs the +0.7375 reference: 0.091, CI [−0.447, +0.633].**

Cluster-robust z is the primary throughout; the naive z is printed only so the design effect is
auditable.

### 9.5 Which branch fired, and why it is POWERED

§7's map: `price ≈ 0.5 ⇒ P-constancy holds, the central bound stands, r₄ is noise` ·
`price ≪ 0.2 ⇒ the price falls faster than the rate, true bound well under +54 (the GOOD outcome,
headroom closes cheaply)` · `price ≫ 1.0 ⇒ r₄ > 1 is real, the geometric family is the wrong
family above deploy, WITHDRAW the bound`.

**Branch 2 fired: `price ≪ 0.2`** (measured +0.0673, ratio 0.091).

**And it fired powered — this must be said explicitly, because a z of +0.33 read carelessly looks
like an underpowered null.** §7's own P-constant point prediction for this cell was
`Δ₅/D_paired₅ × P = 0.0206/0.181 × 4.466 = 0.511` pts/disagreement. At the **realized**
cluster-robust se of 0.2041, that predicted effect would have read **z = 2.5**. Measured z is
**+0.33**. Moreover the bootstrap CI's **upper** bound (+0.4668) sits **below** the 0.511
prediction ⇒ *"the bound stands"* is **excluded at roughly 95%**, not merely disfavoured. This is
a **powered refutation of budget-invariant price AT the extrapolation point**, not a failure to
detect.

### 9.6 The re-stated bound

Identical chain to §4.3 — `P_signal = D_paired₅ × price / Δ₅` with `D_paired₅ = 0.1810`,
`Δ₅ = 0.0206`; `g_next = Δ₅ × r × P_signal × 71.5 / divisor`; `H = g_next/(1 − r)`; elo via
`wr = 0.5 + (pts/σ)·φ(0)` — **only `P` is replaced by the measured top-rung price.**

**Sanity check on the recomputation:** feeding §4.3's P-constant price **0.51125** through this
exact chain reproduces its published **+54.1 elo** central and **4.294 pts/game**. So what follows
is the memo's own arithmetic with one input measured instead of assumed, not a new arithmetic.

With the measured price (r = 0.675 central, divisor 3.2):

| branch | price | P_signal | g_next (pts/game) | H (pts/game) | elo (σ 22.2) | elo (σ 20.4, fixed_v1) |
|---|---|---|---|---|---|---|
| **★ CENTRAL (measured)** | **+0.0673** | 0.591 | +0.1837 | **+0.5652** | **+7.1** | **+7.7** |
| bootstrap CI lo | −0.3300 | −2.899 | −0.9008 | −2.7717 | −34.7 | −37.8 |
| bootstrap CI hi | +0.4668 | 4.101 | +1.2742 | +3.9206 | +49.3 | +53.7 |

r-sensitivity at the measured price: **r = 0.573 → +4.6 elo · r = 0.675 → +7.1 elo ·
r = 0.796 → +13.3 elo.** Note how much **smaller** the r-sensitivity now is than the
price-sensitivity: **the bound's dominant uncertainty has moved off the decay ratio and onto the
price**, which is where §3.2 said the unbraced lever was.

⇒ **the central bound collapses from +54 elo to ≈ +7 elo, with an honest bracket now spanning
zero: roughly [−35, +49] elo.** The +54 figure is **superseded, not merely caveated.**

### 9.7 THE INTERPRETIVE POINT — the decay moved from the RATE into the PRICE

§6(iii) could not distinguish *"r₄ = 1.19 is noise"* from *"the decay really has stopped at
deploy."* **This measurement resolves it in a third way neither reading anticipated, and that is
the interesting result:**

- The **RATE** of budget-attributable disagreement did **not** keep decaying at the top rung
  (Δ₄ = 0.0173 → Δ₅ = 0.0206, r₄ > 1). **That part of the anomaly is real in the data.**
- But the **PRICE** of a disagreement **collapsed**: **+0.7375** over the 2752→11008 *composite*
  versus **+0.0673** over its *top half alone* ⇒ **essentially all of the composite's measured
  value came from the 2752→5504 half.**
- ⇒ **Above 5504 the deeper pick MOVES but does not IMPROVE.** The search keeps changing its mind
  at the top of the ladder; it is churning between moves of ~equal value.
- ⇒ **The geometric family is NOT withdrawn.** The decay is still there — it simply lives in the
  **price** rather than the **rate**, i.e. in exactly the quantity §3.2 held constant and named
  *"the single largest unbraced lever in the whole assembly."*

**§5's out-of-sample misses now have a mechanism rather than just a sign.** Both rungs above 11008
(11008→22016 measured 0.013 vs 0.053 predicted; →110080 measured 0.069 vs 0.106) landed **below**
the model; "the price above deploy is near zero" is precisely the mechanism that produces that.

**§6's caveats survive and still point the same way.** Caveat (i) cliff-vs-geometric and caveat
(ii) in-family judge **both** argue the bound is too high — and (ii) is **sharper now, not
weaker**: a judge sharing the champion's search and its curve125 leaf should *favour* the deeper
pick, and **it did not**. Whatever residual same-family self-preference exists is working against
the null we measured.

### 9.8 What is NOT claimed

- **No `results.csv` row — deliberately, not by oversight.** This instrument has **no opponent, no
  elo and no W/L/D**; the schema has no slot for it. The memo and the `docs/LEVER_INDEX.md` row
  both already state that this line of work carries no results.csv row, and that stands. Its
  numbers live in `summary.json`/`price_analysis.json` and in this section.
- **No CL id minted, `governance/PRODUCTION.yaml` untouched, nothing promoted.** No band-registry
  involvement either — **no games were played**.
- **Still understanding, not a deploy lever.** CL-068's clock sentence and CL-071's promotion both
  still apply; 22016 remains the first rung this bound speaks to, and the bound now says that rung
  is worth ~nothing.
- The measurement prices **one** adjacent pair. It refutes P-constancy *at the top of the ladder*;
  it does not establish the price at any low-end pair, and §3.1's low-end sub-additivity is
  untouched.

---

### Provenance

| quantity | value | source |
|---|---|---|
| Δ per adjacent doubling, D_paired, floors | table §3.1 | `measurement/classical_search/MOVE_AGREEMENT_REPORT.json` (`overall.pairs`, `strata.narrow_gap.pairs`, `overall.floor`); CL-070 |
| price per disagreement (2752v11008) | +0.7375, CI [0.251, 1.226] | `/mnt/c/carc-shared/classical_search/oracle_score_pilot/summary.json` `mean_delta_pts`; [ORACLE_PILOT_EXT_READOUT_20260728](../classical_search/ORACLE_PILOT_EXT_READOUT_20260728.md) |
| pilot cost / sd / population | 4865.5 s @W16, sd 2.406, 628 disagreements | same `summary.json` (`wall_secs`, `sd_delta_positions`, `population_disagreements`) |
| G10 10× screen | D̂ 0.1433, +0.484/disagreement, +0.0693 pts/move, +19.4 elo | [KWIDTH_110K_READOUT_20260802](../classical_search/KWIDTH_110K_READOUT_20260802.md) (no results.csv row exists) |
| 2× rung 11008→22016 | D̂ 0.124, +0.105, 0.013 pts/move | same readout, "The ladder" |
| conversion constants 71.5 / 3.2 / 22.2 | — | `scripts/measurement_infra/analyze_kwidth110k_oracle.py:52-54,68-71` |
| σ_game 22.2 (walled) / 20.4 (fixed_v1) | — | [LUCK_FLOOR.md](../human_anchor/LUCK_FLOOR.md) / [LUCK_FLOOR_fixed_v1.md](../f9_phase_c/LUCK_FLOOR_fixed_v1.md) |
| margin slope +2.782 pts/deck per doubling | se 0.426, z +6.54 | `experiments/results.csv` `blindcurve_k4x86_344_vs_sighted_rodv2_b70e9` note; CL-069 |
| direct 2752→11008 elo | +49.85 ± 17.55 | `experiments/results.csv cl060_h2h_k8x1376_vs_deploy_k4x688`; CL-060 |
| the cliff exemplar | +0.31/+0.76/+0.11/−0.01 pts/deck per K | [F13 READ-OUT](../exact_k_ladder_20260803/READOUT.md); CL-076 |
| in-family discriminator | +0.626, 80% sign agreement | `measurement/classical_search/oracle_score_pilot_t1greedy.log`; LEVER_INDEX clairvoyant-champion row |
| **§9 measured price (5504v11008)** | **+0.0673**, sd 2.2787, naive se 0.1861 | `/mnt/c/carc-shared/classical_search/oracle_score_pilot_5504v11008/summary.json` (`mean_delta_pts`, `sd_delta_positions`, `se_mean_delta`) |
| **§9 cluster-robust + bootstrap** | CR se 0.2041 / z +0.330 / p 0.742; CI [−0.3300, +0.4668]; P(≤0) 0.365; deff 1.204; ratio 0.091 | same dir `price_analysis.json` (20000 reps, seed 20260809); emitted by `scripts/measurement_infra/analyze_oracle_price.py` |
| **§9 run health** | 150/150 ok, 0 failed, `crn_verified_all` true, 126 roots, 474 population, 990.1 s @W16 | same `summary.json`; log `measurement/classical_search/oracle_score_pilot_5504v11008.log`; config in `manifest.json` |
| **§9 backend licence** | 20 positions / 940 field checks / 0 mismatches (committed); re-verified at HEAD 8 positions / 376 checks / 0 mismatches, 9.48× | `measurement/rustport_p6/GATE_ORACLE_PILOT_BACKEND.json`; rustport P6 |

Arithmetic is reproducible from the cited fields alone; no intermediate artefact is required.
