# TIE-NET STAGE-1 FREE TIER — READOUT

> ## ⚠️ STATUS: COMPLETE, 2026-08-23. VERDICT — **§7 GATE INDETERMINATE; §9 READS "THE FEATURES CARRY NOTHING".**
>
> **0 games · no band · no `experiments/results.csv` row written by this file · no
> claim id · `governance/PRODUCTION.yaml` and `governance/BAND_REGISTRY.csv`
> untouched · no `RUN_LIVE.json`.**
>
> **ZERO worker-hours of new label generation and ZERO graded-corpus expansion.**
> Every number below is computed from records already banked on disk. The only
> compute spent was minutes of `nice -n 19` model fitting on one box.
>
> Owner-funded 2026-08-23 ("fund the free tier"). Scope executed exactly as
> [`PLAN.md`](PLAN.md) §11 names it: **P1, P2, P3, A1–A3**, plus the two protocol
> changes (**AUX-TRAIN/GRADE-733** and the pre-registered near-tie pair filter
> κ ∈ {0, 0.5, 1}·`se_pair`). **M1–M3 were NOT run — see §10, that is the
> pre-registered rule's own instruction, not an omission.**
>
> Read rule pre-registered and committed **before the first fit**:
> [`P3_RULE.md`](P3_RULE.md) (commit `17d56dd6`).

Harness: [`scripts/tiletie/probe_pickers.py`](../../scripts/tiletie/probe_pickers.py)
(modes `preflight`, `sweep`) · tests
[`tests/test_probe_pickers.py`](../../tests/test_probe_pickers.py) (59 pass) ·
artifacts [`PREFLIGHT.json`](PREFLIGHT.json) · [`SWEEP.json`](SWEEP.json) ·
[`CORPORA.json`](CORPORA.json) · [`KNOWNGOOD.json`](KNOWNGOOD.json) ·
stage-0 null [`GRADE_net.json`](../tiletie_probe_20260822/GRADE_net.json) ·
inventory [`PRICE.md`](../tiletie_probe_20260822/PRICE.md) ·
lever row [`docs/LEVER_INDEX.md`](../../docs/LEVER_INDEX.md) "learned tie-breaker
net (distill the arbiter)".

---

## 0. THE GATE FIRED FIRST — nothing below may be read otherwise

```
=== KNOWNGOOD GATE (tier1 picker vs measurement/tiearb_20260816/READOUT.json) — PASS ✅ ===
  arb  published 0.2064592832  reproduced 0.2064592832  Δ 0.000e+00
  ora  published 0.2545233140  reproduced 0.2545233140  Δ 0.000e+00
  F    published 0.8111605963  reproduced 0.8111605963  Δ 0.000e+00
  n=733 positions / 399 roots   max per-position Δ 0.000e+00 (tol 1e-09)
```

Run first, with no skip flag, by **both** `preflight` and `sweep`.

**A second, stronger known-good also holds:** the sweep's **T0** cell reproduces
stage-0's published *net* capture bit-for-bit — `−0.04510`, `se_cluster 0.0552`,
boot `[−0.1524, +0.0642]`, `F = −0.1772 [−0.839, +0.226]`, inner-CV fold
accuracies `0.5285 / 0.5251 / 0.5212 / 0.5229 / 0.5080` — against
[`GRADE_net.json`](../tiletie_probe_20260822/GRADE_net.json). So the label sweep's
T0 rung *is* stage-0, not a re-implementation of it, and every rung above it
differs from stage-0 in labels alone.

---

## 1. ⭐ P3 FIRST — THE GATE. **`p3_acc` = 0.5132 ⇒ BRANCH: DEAD**

Per [`P3_RULE.md`](P3_RULE.md) §1.1 the statistic of record is the **mean inner-CV
sibling-rank accuracy over the 5 root folds** — the same statistic, computed the
same way, as stage-0's published 0.5211.

| arm | label source | label count | inner-CV acc (the branch statistic) | per-fold | OOF acc (held-out roots) |
|---|---|---:|---:|---|---:|
| **control** | arbiter CRN margins (stage-0's own) | 2,458 pairs | **0.5211** | 0.5285 / 0.5251 / 0.5212 / 0.5229 / 0.5080 | 0.5098 |
| **⭐ P3** | **`clair-puct` ORACLE arm order** | 2,451 pairs | **0.5132** | 0.5292 / 0.5031 / 0.5073 / 0.5077 / 0.5188 | **0.4863** |

**CONTROL: PASS ✅** — the arbiter arm reproduces `GRADE_net.json`'s per-fold
inner-CV accuracies to every published digit, so P3 is not void and the branch fires.

> ### `p3_acc = 0.5132 < 0.55` ⇒ **DEAD**, per the rule committed before the fit.

**Removing 100% of the label noise makes the ranker WORSE, not better** — 0.5211 →
0.5132 on the branch statistic, and 0.5098 → **0.4863 on held-out roots, which is
*below chance*.** The label count was held fixed at the graded corpus's own
2,4xx pairs; the *only* thing that changed was that the target became perfect.

Selected `C` per fold, arbiter arm: `0.01, 1.0, 0.01, 0.01, 0.003`; oracle arm:
`0.3, 0.03, 0.1, 0.003, 1.0`. The sign-flipping selection instability
[`PLAN.md`](PLAN.md) §8.4 named as "the fingerprint of no learnable signal" is
present in **both** arms — it is not a symptom of label noise, because it survives
the noise being deleted.

**What this licenses, verbatim from the rule:** the 84 features cannot rank
siblings even against a perfect, noiseless target, so *"more labels"* is
**arithmetically not the story** at this representation. Run the free A1–A3 sweep,
then **STOP**. No M-ladder rescue; no funding for B1/B2/B3/B′ or G1/G2.

**⚠️ RAIL, in force:** P3 trains against the same oracle quantity used to grade. It
is a **diagnostic of feature informativeness ONLY** and is **never** reported as
capture. No `arb`, no `F`, no capture CI is produced from a P3 fit.

---

## 2. P1 — the accuracy → capture calibration (previously uncomputed)

The arbiter's own sibling-rank accuracy against the `clair-puct` oracle order, on
the graded 733. Both orderings were already banked.

| statistic | value | pairs |
|---|---:|---:|
| arbiter acc vs oracle order, **cross-fit** (the estimand `arb = +0.2065` was priced on) | **0.5379** | 4,881 |
| arbiter acc vs oracle order, **full-M** (the estimand a *net* is graded on) | **0.5486** | 2,451 |
| arbiter **top-1** agreement with the oracle argmax, cross-fit / full-M | **0.4283** / 0.4440 | 733 |

| capture anchor | mean | se_cluster | z |
|---|---:|---:|---:|
| `rnd` (uniform random arm) | **+0.01512** | 0.05989 | +0.25 |
| `arb` (the deployed arbiter) | **+0.20646** | 0.05507 | +3.75 |
| `ora` (oracle argmax ceiling) | **+0.25452** | 0.05978 | +4.26 |

Fitting the local slope on the two empirical anchors `(0.5, rnd)` and
`(0.5379, arb)` — the `(1.0, ora)` anchor is printed for scale and deliberately
**not** on the line:

* **slope = 5.048 pts per unit accuracy.**
* **accuracy needed for `0.50·arb` (= +0.1033): only 0.5175.**
* accuracy needed for full `arb`: 0.5379 (the anchor, by construction).

### ⭐ 2.1 THE HEADLINE OF P1: the exchange rate is brutally steep

**The arbiter wins +0.2065 pts/tied ply while agreeing with the oracle's argmax
under half the time (0.4283) and getting barely 54% of sibling pairs in the right
order.** A tie-net needs only **0.5175** oracle-order accuracy to be worth half the
rollouts. That is a *low* bar — which is precisely what makes the sweep's failure
to clear it informative rather than merely underpowered.

Accuracy falls with tie width, gently: k=2 arms 0.5490 · k=3 0.5596 · k=4 0.5502 ·
k=5 0.5353.

### ⚠️ 2.2 A TRAP THIS READOUT CREATES AND MUST DEFUSE

[`PLAN.md`](PLAN.md) §9 says "rank accuracy" without ever naming **which target**.
There are two, and they are not interchangeable:

| accuracy | target | what it means | what it is for |
|---|---|---|---|
| `acc/arb` | the **arbiter's** CRN margins | "did the net learn what it was *taught*" | commensurable with stage-0's 0.5211 and with §7.2's bar |
| `acc/ora` | the **`clair-puct` oracle** order | "did the net learn the **truth**" | **the only one P1's calibration is keyed to**, because capture is priced by the oracle |

Applying P1's slope to the *arbiter-target* number would predict **+0.19** capture
at T3 against a **measured +0.015** — a **13× error**. Applied to the
*oracle-target* number at T0 it predicts **−0.0014** against a measured **−0.0451**
(≈0.8σ). **The calibration is sound; the target is the whole ballgame.** Both are
reported for every cell below, and the harness refuses to let the oracle labels
reach a training call (asserted in tests).

---

## 3. P2 — label-noise audit (the B-vs-n decision)

`se_pair` is **CRN-PAIRED**: sd over worlds of `(margin_i − margin_j)` ÷ √m. This
is smaller than the unpaired `sd·√2/√m` [`PLAN.md`](PLAN.md) §6.4 writes beside its
own "use the paired sd" instruction, so it declares **fewer** pairs to be coin
flips — the conservative choice for a near-tie filter.

| judge | pairs | exact ties dropped by stage-0 | median `t` | frac `t` < 0.5 | < 1.0 | < 2.0 | effective pairs at κ=0.5 / 1.0 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **`tier1-greedy`** (the training label of record) | 2,439 | 107 | 0.929 | **0.290** | **0.528** | 0.834 | 1,733 / **1,150** |
| `clair-puct` (P3's noiseless-target arm) | 2,423 | 114 | 0.852 | 0.323 | 0.574 | 0.874 | 1,641 / 1,032 |

**More than half the pairs stage-0 trained on had a margin difference smaller than
its own standard error** — coin-flip labels presented as data. The *effective*
stage-0 label count was ≈1,150, not the nominal 2,565: a **2.1× inflation**. So the
"tiny pool" story was genuinely worse than [`PLAN.md`](PLAN.md) §8.3 stated.

**⚠️ But P2's decision is now moot, and §5 shows why empirically:** P2 exists to
choose **B** (deeper labels) over **n** (more plies). The κ-curve in §5.3 removes
exactly these coin-flip pairs and **changes nothing** — so buying B would not have
helped either. Route **B′ is refuted, not merely defunded.**

---

## 4. A1–A3 — what the free label unification actually bought

All three auxiliary corpora admitted through the *same* shape gates, with the
`m=128` waiver explicit. **G-DISJOINT is a hard gate that REFUSES on overlap**; it
measured **0 rid and 0 root overlap** for all three, which is the entire licence
for AUX-TRAIN/GRADE-733.

| corpus | rids | roots | arm labels | **realized pairs** | nominal ([`PLAN.md`](PLAN.md) §3.1) | m | notes |
|---|---:|---:|---:|---:|---:|---:|---|
| graded (the read) | 733 | 399 | 2,201 | **2,458** | 2,565 | 32 | 107 exact ties dropped |
| **A1** `tiearb2` | 1,350 | 724 | 4,053 | **4,544** | 4,730 | 32 | clean; arm-floor 2 |
| **A2** `shared_run_r4` S1 | 1,344 | 748 | 4,672 | **7,915** | 8,398 | **128→32** | explicit waiver, first 32 ordered CRN worlds |
| **A3** `rung3_r5` S2 | 1,060 | 977 | 7,662 | **24,300** | 26,139 | 32 | ⚠️ **DECLARED SHIFT**, arm-floor 5 |
| **ALL FREE total** | 4,487 | 2,848 | 18,588 | **39,217** | 41,832 | | **15.95× T0** |

Arm-label counts match [`PRICE.md`](../tiletie_probe_20260822/PRICE.md) §2
**exactly** (4,053 / 4,672 / 7,662), 0 shape problems, 0 feature-build skips.

**⚠️ Correction to the plan's arithmetic (1 of 4):** realized pair counts run ~5%
below the plan's nominal `Σk(k−1)/2` because exact ties carry no order and are
dropped. The sweep is **15.95×**, not 16.3×.

**A2's honest deficit, carried:** the rust-leg records do not emit the
`crn_verified`-by-deck-hash witness; they emit `crn_witness = "world_deck_hash"`
instead. Stated, not papered over.
[`PRICE.md`](../tiletie_probe_20260822/PRICE.md) §2.2's exclusion list is enforced
in [`CORPORA.json`](CORPORA.json): the 8,648 wrong-schema `champ_picks_s{1,2}`
files and the 0-byte gate-VOIDed `per_position_s2.jsonl` are never globbed, and
`shared_run_r4` contributes 0 S2 labels.

**A3's declared shift, carried:** arm-floor 5 by design; **62% of all free pairs
come from this one shifted corpus**. It is admitted as its own tier (T3) and never
pooled silently into the CLEAN FREE headline (T2).

---

## 5. THE SWEEP TABLE

Features fixed at **R0** (84 scalars), model fixed at **M0** (pairwise logistic),
seed 20260822, bootstrap seed 20260816 / 20,000 reps. Every cell graded on the
**same** 733 positions / 399 roots / 2,458 unfiltered pairs.

### 5.1 Capture vs label count, at fixed features

| tier | pools | design | train rows | `acc/arb` | `acc/ora` | **capture** | se | z | boot CI95 | `F` |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| **T0** | stage-0 | cross-fit | 19,664 | 0.5098 ±.0087 | **0.4967** ±.0085 | **−0.04510** | .0552 | −0.82 | [−0.1524, +0.0642] | −0.177 |
| **T1** | +`tiearb2` | cross-fit | 65,104 | 0.5218 ±.0092 | 0.5184 ±.0088 | −0.00472 | .0519 | −0.09 | [−0.1076, +0.0959] | −0.019 |
| **T1** | +`tiearb2` | aux-train | 9,088 | 0.5238 ±.0096 | 0.5182 ±.0092 | +0.02255 | .0544 | +0.41 | [−0.0846, +0.1288] | +0.089 |
| **T2** | +`shared_run_r4` (CLEAN FREE) | cross-fit | 144,254 | 0.5146 ±.0091 | 0.5120 ±.0088 | **+0.04899** | .0500 | +0.98 | [−0.0478, **+0.1476**] | +0.193 |
| **T2** | +`shared_run_r4` | aux-train | 24,918 | 0.5153 ±.0092 | 0.5098 ±.0089 | +0.03420 | .0541 | +0.63 | [−0.0715, +0.1409] | +0.134 |
| **⭐ T3** | +`rung3_r5` (ALL FREE) | **cross-fit** | **387,254** | **0.5352** ±.0091 | **0.5116** ±.0088 | **+0.01500** | **.0521** | **+0.29** | **[−0.0868, +0.1169]** | +0.059 |
| **T3** | ALL FREE | aux-train | 73,518 | 0.5323 ±.0092 | 0.5073 ±.0087 | +0.02573 | .0505 | +0.51 | [−0.0726, +0.1244] | +0.101 |

⭐ = **the one headline capture read** [`PLAN.md`](PLAN.md) §7.4 licenses against
the spent 733: top label rung × cross-fit (the conservative design) × κ=0.
**Every other cell in this document is a DIAGNOSTIC and its capture may not be
quoted as a result.**

The net changes the champion's pick on ~46–49% of positions throughout, and agrees
with the oracle's argmax on only **19–22%** of them — against the arbiter's 42.8%.

### 5.2 ⭐⭐ THE DISSOCIATION — the single most important number in this readout

Paired root-clustered bootstrap (4,000 reps), same 2,458 test pairs in both arms,
so the correlated error cancels. The unpaired quadrature se is shown to make the
point that pairing *helps* the trend, not hurts it:

| contrast | target | Δacc | se (paired) | z | CI95 | (unpaired se) |
|---|---|---:|---:|---:|---|---:|
| **T3 − T0, cross-fit** | **arbiter** | **+0.0254** | 0.0091 | **+2.78** | **[+0.0073, +0.0432]** | 0.0126 |
| **T3 − T0, cross-fit** | **oracle** | **+0.0149** | 0.0091 | **+1.63** | **[−0.0035, +0.0323]** | 0.0123 |
| T3 aux-train − T0 | arbiter | +0.0226 | 0.0095 | +2.37 | [+0.0039, +0.0406] | 0.0127 |
| T3 aux-train − T0 | oracle | +0.0106 | 0.0097 | +1.10 | [−0.0084, +0.0293] | 0.0122 |

> **A 15.95× label sweep produces a statistically real gain at predicting the
> ARBITER's noisy labels (z +2.78, CI excludes 0) and NO detectable gain at ranking
> the TRUTH (z +1.63, CI through 0).**
>
> Read the `acc/ora` column of §5.1 down the page: **0.4967 → 0.5184 → 0.5120 →
> 0.5116.** It steps once off chance between T0 and T1 and then goes **flat — and
> slightly down — across the next 6× of labels**, while `acc/arb` keeps climbing to
> 0.5352. **The extra labels buy fit to the arbiter's CRN noise, not to the
> oracle's order.** That is the mechanism, and it is exactly what P3 predicts from
> the other direction: a representation that cannot rank a noiseless target has
> nothing to converge *to*, so extra noisy labels can only sharpen the noise.

And `acc/ora` never reaches **0.5175**, the P1 bar for merely half the rollouts'
capture — at T3 it sits at 0.5116 ± 0.0088, i.e. **below that bar**, and the best
cell in the entire sweep (T3 aux-train κ=0.5, 0.5188) clears it by 0.15σ.

### 5.3 The pre-registered near-tie filter κ, at the top rung (T3)

`|margin_a − margin_b| ≥ κ·se_pair`, training-set filter only; all cells graded on
the same unfiltered pairs. **κ=0 reproduces stage-0 byte-identically** (asserted in
tests).

| κ | design | train rows | `acc/arb` | `acc/ora` | capture | boot CI95 |
|---:|---|---:|---:|---:|---:|---|
| 0 | cross-fit | 387,254 | 0.5352 | 0.5116 | +0.01500 | [−0.0868, +0.1169] |
| 0.5 | cross-fit | 276,286 | 0.5303 | 0.5159 | +0.02431 | [−0.0772, +0.1255] |
| 1.0 | cross-fit | 181,532 | 0.5303 | 0.5106 | +0.01140 | [−0.0924, +0.1165] |
| 0 | aux-train | 73,518 | 0.5323 | 0.5073 | +0.02573 | [−0.0726, +0.1244] |
| 0.5 | aux-train | 52,454 | 0.5362 | 0.5188 | +0.04002 | [−0.0651, +0.1460] |
| 1.0 | aux-train | 34,436 | 0.5374 | 0.5182 | +0.02463 | [−0.0772, +0.1285] |

Paired contrasts at T3 cross-fit: κ=1.0 − κ=0 reads **−0.0049 ± 0.0057 (z −0.86)**
on the arbiter target and **−0.0010 ± 0.0060 (z −0.17)** on the oracle target;
κ=0.5 − κ=0 reads −0.0049 (z −0.92) and +0.0043 (z +0.77).

> **The κ-curve is FLAT.** Discarding 53% of the training pairs as coin flips
> changes nothing on either target or on capture. **This is a free, decisive
> refutation of the deeper-labels lever (B′):** if halving the label noise by
> *deleting* the noisiest pairs buys nothing, halving it by *quadrupling B* will
> not either. P2's B-vs-n question is answered "neither".

### 5.4 The §6.3 design consistency check

AUX-TRAIN − cross-fit at the top rung: **−0.0028 ± 0.0053 (z −0.54)** on the
arbiter target, **−0.0043 ± 0.0061 (z −0.70)** on the oracle target; capture
+0.02573 vs +0.01500, a difference of 0.0107 against se ≈0.05, i.e. **≈0.2σ**.

**The two designs agree well inside the plan's ~1σ tolerance**, so distribution
shift is *not* doing visible work here and the plan's "if they disagree the
cross-fit is the headline" clause is not triggered. The cross-fit is nevertheless
declared the headline as the conservative choice.

---

## 6. THE §7 GATE, ARITHMETIC — read on the headline cell (T3 / cross-fit / κ=0)

Point estimate **+0.01500**, boot CI95 **[−0.0868, +0.1169]**, inner-CV accuracy
**0.5199**.

| rule | condition | value | fires? |
|---|---|---|---|
| **§7.1 STAGE-2** | `arb_net ≥ 0.50·arb` = +0.1033 | +0.0150 | ❌ |
| **§7.1 STAGE-2** | boot CI95 lower bound > 0 | −0.0868 | ❌ |
| **§7.2 KILL** | CI95 upper bound < +0.1033 | **+0.1169** | ❌ |
| **§7.2 KILL** | inner-CV sibling-rank accuracy < 0.53 | 0.5199 | ✅ |

* **STAGE-2 DOES NOT FIRE.** No cell anywhere in the sweep clears +0.1033, and
  **every single cell's CI95 lower bound is below zero.** The best point estimate
  in the whole grid (T2 cross-fit, +0.04899) is 2.1σ short of the bar.
* **§7.2's KILL DOES NOT FIRE EITHER**, because it needs *both* conditions and
  CI_hi = +0.1169 exceeds +0.1033.
* ⇒ **The verdict on the plan's own gate is INDETERMINATE — the §7.3 dead zone**,
  `(−0.005, +0.108)`, and +0.0150 sits squarely inside it.

### ⚠️ 6.1 SAY THE UNCOMFORTABLE PART PLAINLY

[`P3_RULE.md`](P3_RULE.md)'s DEAD branch promised to *"convert §7.2's already-fired
kill into a label-scaled kill."* **It did not.** At stage-0's label scale the kill
*had* fired (CI_hi = +0.0642 < +0.1033). Adding 15.95× the labels **moved the point
estimate up into the dead zone and un-fired it.**

That is not a rescue of the lever — the capture is still statistically
indistinguishable from zero (z +0.29) and 7× short of the gate — but it means the
formal §7.2 kill is **not on the books**, and this readout must not claim it is.
[`PLAN.md`](PLAN.md) §7.3 predicted this exact failure mode: at `se = 0.0552` the
dead zone is 55% of `arb` wide, and **no quantity of training labels narrows it.**
Buying the formal kill costs graded positions: **G1 (+912, 57.7 wh)** for
80%-power, **G2 (+2,199, 139 wh)** for a partition with no dead zone.

**Recommendation: do not buy them.** §7 was only ever the *weaker* instrument at
n=733. The mechanism evidence in §1 and §5.2 is a far stronger statement than a
capture CI on 733 positions could produce, and it points one way.

---

## 7. ⭐ THE §9 DISCRIMINATING READOUT — which signature fired

[`PLAN.md`](PLAN.md) §9.1 defines two signatures. This is the section the whole
plan exists for.

| signature | what it requires | observed |
|---|---|---|
| "MORE LABELS FIXES IT" | rank accuracy rises monotonically in `log(n_pairs)`, the rise larger than the shrinking error bar | ❌ **`acc/ora` = 0.4967 → 0.5184 → 0.5120 → 0.5116** — one step off chance, then flat/down over the next 6×. T3−T0 z **+1.63**, CI through 0. Not monotone. |
| **"THE FEATURES CARRY NOTHING"** | accuracy flat near chance across the label sweep while its error bar falls | ✅ **fires**, and is **independently corroborated by P3**: with the label noise deleted entirely the same features read **0.5132 inner-CV / 0.4863 OOF (below chance)**. |

**Two independent instruments — a noise-free target at fixed label count (P3), and
a 15.95× label sweep at fixed noise (A1–A3) — agree: the 84-feature afterstate
representation does not carry sibling-discriminating information about a leaf-tied
Carcassonne ply.** The one axis on which the model demonstrably improves with
labels is fitting the arbiter's *sampling noise*.

This is the powered null on the label axis that [`PLAN.md`](PLAN.md) §9.1 says "the
program has never once bought on a learned lever" — delivered, for zero
worker-hours, though see §8 for the honest size of the error bar it comes with.

---

## 8. ⚠️ FOUR CORRECTIONS TO THE PLAN'S OWN ARITHMETIC

1. **The cluster design-effect is ~0.9, not ~3.** [`PLAN.md`](PLAN.md) §9.1 inflated
   the accuracy error bar by an *assumed* `deff ≈ 3`. Measured by root-clustered
   bootstrap across all 12 cells: **0.87–0.95**. The accuracy axis is therefore
   **~3× better resolved** than the plan budgeted — which is what makes the flat
   `acc/ora` line in §5.2 a real null rather than an underpowered one.
2. **But §9.1's se(acc) table is keyed to the wrong denominator.** It computes
   se(acc) from the *training* pair count (±0.0042 at T3). The decision-relevant
   accuracy is graded on the **graded corpus's own 2,458 pairs**, so its se stays
   **±0.009 no matter how many training labels are bought.** The plan's "±0.004 at
   T3" is reachable only for the *inner-CV* accuracy on the training pool, not for
   anything graded on the 733. The claim "the accuracy axis is ~4× better resolved
   than the capture axis at T3" survives — but at ±0.009 vs ±0.052, i.e. ~5.8×, for
   a different reason than the plan gives.
3. **Realized pair counts are ~5% under nominal** (exact ties carry no order):
   graded 2,458 not 2,565; ALL FREE **39,217 not 41,832**; the sweep is **15.95×**.
4. **"Rank accuracy" is ambiguous in §9 and the ambiguity is worth 13×.** See §2.2.

---

## 9. HONESTY RAILS — carried verbatim, as required

* **CEILING CAVEAT** — on this corpus the entire *judge-quality* ceiling is
  `ora − arb = +0.048` with `F` CI95 [0.450, 1.320] **including 1**. That caveat
  bounds the *v2.9-picker* question. It does **not** bound the tie-net question:
  the tie-net's target is `arb` itself (+0.2065 — amortizing the rollouts at ~zero
  wall), not the +0.048 residual. Stated so nobody mis-imports it in either
  direction.
* **NET FOLD ASYMMETRY** — `tier1`/`v29` select on M/2 worlds and are priced on the
  disjoint M/2; the net's pick is world-independent, so its `arb` is a **full-M**
  difference — same estimand, **less noise**. Its winner's-curse control is the
  **root split** (and, under AUX-TRAIN, a different band entirely), not the world
  split. **Do not read a net-vs-rollout gap of order the noise as a strength
  difference.** This caveat *flatters the net*, and the net still read nothing.
* **R1 COLLINEARITY** — for a LINEAR pairwise ranker on `x_a − x_b` the
  afterstate-minus-ROOT diff features **cancel exactly**:
  `(x_a−x_r)−(x_b−x_r) = x_a−x_b`. R1 is perfectly collinear with R0 in a linear
  model and adds **literally nothing**; it is a rung **only** paired with M2/M3.
  Since M2/M3 were not run (§10), **R1 was correctly not run either** — running it
  on M0 would have produced an identical model and a fake rung.
* **AUX-TRAIN band note** — the *training* set is out-of-band but the *grading* is
  entirely within the graded corpus's own band, so CLAUDE.md's "inflate σ 1.5–2× on
  cross-band **contrasts**" does **not** bite the error bar. What bites is
  **distribution shift in the model** — a bias risk on the estimate, not a variance
  risk on the interval. §5.4 measures that shift at ≈0.2σ.
* **THE ~10–15% PRIOR** ([`PLAN.md`](PLAN.md) §8) — stated before any number was
  bought: ~10–15% that any stage-1 tier clears §7.1. **None did.** The free tier was
  designed to be worth running at that prior because its deliverable is a diagnosis,
  not a hoped-for win.
* **The stage-0 park gate said PARK, and nothing here overturns it.** The override
  the owner funded was an **engineering-time decision, not a compute-spend
  decision**, and it stayed one: zero worker-hours.

---

## 10. WHAT WAS **NOT** RUN, AND WHY

| item | status | reason |
|---|---|---|
| **M1–M3** (interactions / GBDT / MLP-RankNet) | **NOT RUN** | [`P3_RULE.md`](P3_RULE.md) §3's DEAD branch: *"Do not run the M1–M3 ladder as a rescue."* Pre-registered before the number existed. Capacity is also the settled question CL-064 was bought to close. |
| **R1 / R2 / R3** feature rungs | **NOT RUN** | R1 is collinear with R0 under M0 (§9). R2's two menus already failed as hand-crafted terms (`G-FAIL`). R3/M4 is the CL-064/CL-065 re-litigation and stays gated. |
| **B1 / B2 / B3** (fresh plies) | **NOT FUNDED** | DEAD branch + §5.2: labels do not move oracle-order accuracy. |
| **B′** (deeper labels, B=256) | **REFUTED, not merely defunded** | §5.3: deleting 53% of the noisiest pairs changes nothing. |
| **G1 / G2** (graded-corpus expansion) | **NOT FUNDED — recommended against** | §6.1: buys a formal §7.2 kill for 58–139 worker-h that the §7 mechanism evidence already exceeds. |

---

## 11. VERDICT

> **The tie-net lever stays PARKED, and its named re-open clause is now directly
> tested and refuted.**
>
> [`docs/LEVER_INDEX.md`](../../docs/LEVER_INDEX.md)'s stage-0 row closes with:
> *"Honest re-open: the label pool was tiny (~50 rows/feature); stage-1 labels cost
> ~95 wh per 10K plies — funding stage-1 against this null is an owner call."*
> **The free tier bought that re-open for zero worker-hours and it does not hold.**
> At 15.95× the labels (996 rows/feature, up from ~49) the net's ability to rank
> siblings *against the truth* is statistically unchanged (z +1.63, CI through
> zero), and with the label noise removed entirely the same features rank a
> perfect target at **0.5132 / 0.4863 OOF — chance and below.**
>
> **On the plan's §7 gate the state is INDETERMINATE**, not a formal kill — adding
> labels moved the estimate into the §7.3 dead zone, exactly as §7.3 warned it
> could. Closing that formally requires graded positions (G1/G2, 58–139 worker-h),
> which this readout **recommends against**: the §7 capture gate at n=733 is the
> weaker instrument, and the §9 mechanism result is unambiguous.
>
> **Recommended disposition: close the LABEL ROUTES of this lever with prejudice
> (routes (b), (c), B′, G1, G2 — all of §3.2/§3.3 above T3), and leave the lever
> itself PARKED at stage-0's gate.** What is *not* closed is the representation
> question: R3/M4 (board planes) remains untested here and remains **gated** behind
> CL-064/CL-065, which this readout does not disturb.
>
> **The one thing the program gains that it has never had: a powered null on the
> label axis of a learned discriminator, bought for 0 worker-hours** — plus the P1
> exchange rate (0.5175 oracle-order accuracy = half the rollouts' capture), which
> is a reusable ruler for any future tie-arbitration lever.

---

## 12. `results.csv`-READY ROW — **hand to the orchestrator; this file does not edit `results.csv`**

Headline cell only (T3 / cross-fit / κ=0 / R0 / M0), the one read
[`PLAN.md`](PLAN.md) §7.4 licenses. Paste as a single line:

```csv
tienet_stage1_freetier_labelsweep_T3_allfree_offline_n733_crossfit,2026-08-23,base,d103bee2,733,stage1_pairwise_logistic_ranker_84feat_39217_sibling_pairs_ALLFREE_15.95x_OFFLINE_PICKER,1.5,8.0,capture_pts_per_tied_ply_scale_all_vs_clairpuct_oracle,2752,tier1_greedy_judge_argmax_OFFLINE_REFERENCE_the_deployed_arbiters_picker,1.5,8.0,root_crossfit_plus_aux_train_NO_GAMES_PLAYED_offline_probe,2752,,,,,0.0521,0.0150,measurement/tienet_stage1_plan_20260823/,probe,"TIE-NET STAGE-1 FREE TIER (0 worker-hours; P1/P2/P3 + A1-A3 + kappa curve on banked data). VERDICT: sec7 gate INDETERMINATE, sec9 reads THE FEATURES CARRY NOTHING. Headline capture +0.0150 (z +0.29) boot [-0.0868,+0.1169], F=+0.059 -- 7x short of the +0.1033 stage-2 bar, and NO cell in the 12-cell grid has CI_lo>0. sec7.2's kill does NOT fire either (CI_hi +0.1169 > +0.1033): 15.95x labels moved the estimate INTO the sec7.3 dead zone and un-fired the kill that HAD fired at stage-0 scale. THE MECHANISM (two independent instruments): (1) P3 -- retraining the identical 84-feature ranker on the clair-puct ORACLE arm order at FIXED label count reads inner-CV 0.5132 / OOF 0.4863 (BELOW chance) vs the arbiter-label control's 0.5211/0.5098 which reproduces stage-0 exactly; removing ALL label noise makes it WORSE. (2) The 15.95x label sweep raises accuracy against the ARBITER's noisy labels (+0.0254 paired z+2.78) but NOT against the oracle order (+0.0149 z+1.63, CI through 0): acc/ora 0.4967->0.5184->0.5120->0.5116, flat after T1, never reaching the 0.5175 P1 bar for half the rollouts' capture. Extra labels buy fit to the arbiter's CRN noise, not the truth. kappa in {0,0.5,1}*se_pair is FLAT (|z|<1) => route B' (deeper labels) REFUTED not merely defunded, though P2 shows 52.8% of stage-0 pairs sat below 1 se_pair (effective count ~1150 not 2565). P1 NEW RULER: the arbiter captures +0.2065 at only 0.5379 oracle-order sibling accuracy / 0.4283 top-1 agreement => slope 5.05 pts per unit accuracy, 0.5175 needed for 0.50*arb. Measured cluster deff 0.87-0.95, NOT the assumed 3. AUX-TRAIN/GRADE-733 vs root cross-fit agree at 0.2 sigma (G-DISJOINT 0 rid / 0 root overlap, hard-gated). M1-M3 NOT RUN per the pre-registered P3_RULE.md DEAD branch. Recommend: close the LABEL routes (b)/(c)/B'/G1/G2 with prejudice; lever stays PARKED; R3/M4 planes untouched and still gated by CL-064/065. Rails carried: ceiling caveat, net fold asymmetry, R1 collinearity, the ~10-15% prior. KNOWNGOOD arb 0.2064592832 reproduced delta 0.000e+00; T0 rung reproduces stage-0's -0.04510 bit-for-bit. PREFLIGHT.json + SWEEP.json + CORPORA.json in src_dir."
```

**Suggested companion touches for the orchestrator** (not made by this file):

* `docs/LEVER_INDEX.md` "learned tie-breaker net" row — append: *"⭐⭐⭐ STAGE-1
  FREE TIER RAN 2026-08-23 FOR 0 WORKER-HOURS AND REFUTES THIS ROW'S OWN RE-OPEN
  CLAUSE: at 15.95× the labels (996 rows/feature) oracle-order sibling accuracy is
  statistically unchanged (+0.0149, z +1.63) while arbiter-label accuracy rises
  (z +2.78) — the labels buy fit to the arbiter's noise; and P3 (same ranker, same
  label count, NOISELESS oracle target) reads 0.5132 / 0.4863 OOF, below chance.
  Label routes CLOSED; lever stays PARKED. §7 gate is formally INDETERMINATE (CI_hi
  +0.1169 vs the +0.1033 bar) — a formal kill needs G1/G2 graded positions, not
  recommended."*
* `docs/PROGRAM_ROADMAP_2026-07-07.md` — close the "tie-net stage-0/stage-1" queue
  line with a pointer here.
* `governance/CLAIM_REGISTRY.csv` — this is a **probe**, not a claim; no new claim
  id is warranted unless the owner wants the label-axis null registered as one.

---

*Executed 2026-08-23 on branch `tienet-free-tier`, worktree-isolated. Harness at
`d103bee2`. `SWEEP.json`'s own `git` field records `fc67c4a0`, the parent commit —
the dual-target and paired-contrast additions were in the working tree at run time
and landed in `d103bee2` unchanged. `doc_lint` clean.*
