# P3 READ RULE — pre-stated BEFORE the fit, in the house style of `tiletie_term_20260814/GATE_READ_RULE.md`

> **STATUS: PRE-REGISTERED READ RULE, 2026-08-23. COMMITTED BEFORE THE FIRST P3 FIT.**
> **0 games · no band · no `experiments/results.csv` row written by this file · no claim id ·
> `governance/PRODUCTION.yaml` and `governance/BAND_REGISTRY.csv` untouched · no `RUN_LIVE.json`.**
> This file reads no number. It states what the P3 number will be read to mean, so the
> reading cannot be chosen after the fact.

Authority: [`PLAN.md`](PLAN.md) §9.2 **P3** and §11. Funded by the owner 2026-08-23 as the
**FREE TIER** (P1, P2, P3, A1–A3, M1–M3 + the two protocol changes), **zero worker-hours**.

---

## 1. WHAT P3 IS

Re-train **the identical stage-0 estimator** — the 84-feature pairwise logistic ranker from
[`scripts/tiletie/probe_pickers.py`](../../scripts/tiletie/probe_pickers.py)
(`pairwise_rows` → `fit_ranker(model="pairwise-logistic")`), with the **same 5-fold
root-grouped cross-fit**, the same `--split-seed 20260822`, the same inner root-grouped CV
over the same `C` grid — on the graded corpus's **`clair-puct` ORACLE arm order** instead of
the arbiter's noisy CRN margins.

* **Label count is HELD FIXED** at the graded corpus's own 733 rids / 399 roots / ~2,565
  sibling pairs. P3 buys **no labels**. It removes label **noise** only.
* The oracle order is **already banked for all 733** (`matrix_if`, the `clair-puct`
  world-value matrix that `analyze_tiearb.build_positions` assembles). Nothing is generated.
* The **arbiter-label arm is re-run in the same invocation as a control** and must reproduce
  stage-0's `GRADE_net.json::witnesses.net_model.folds[].inner_cv_acc`
  (0.5285 / 0.5251 / 0.5212 / 0.5229 / 0.5080, mean **0.5211**). If the control does not
  reproduce, **P3 is void** and no branch fires.

### 1.1 The statistic of record

**`p3_acc` = the mean inner-CV sibling-rank accuracy across the 5 root folds** — the *same*
statistic stage-0 reported as 0.5211, computed the *same* way, so the two are directly
comparable. That, and only that, is the number the branches below are read on.

Reported **beside** it, and NOT branch inputs: the out-of-fold (held-out root) pairwise
accuracy under the same folds, the per-fold spread, the selected `C` per fold, and the
top-1 (argmax) agreement rate.

---

## 2. ⚠️ RAILS (from `PLAN.md` §9.2, carried verbatim in force)

* P3 trains against the **same oracle quantity used to grade**. It is a **diagnostic of
  feature informativeness ONLY** and **MUST NEVER be reported as capture**. No `arb`, no `F`,
  no CI on a capture statistic is produced from a P3 fit.
* P3 **keeps the root cross-fit** (it does *not* use the AUX-TRAIN/GRADE-733 design — there
  are no auxiliary labels in P3 by construction).
* P3 **burns no positions and re-opens no blind slice**; the graded 733 is already SPENT.
* `require_knowngood` runs first, with no skip flag. Any read that does not begin with
  `arb published 0.2064592832 reproduced 0.2064592832 Δ 0.000e+00` is **void**.

---

## 3. THE TWO-BRANCH RULE — stated before the number exists

| branch | condition on `p3_acc` | conclusion | what is executed next |
|---|---|---|---|
| **DEAD** | `p3_acc` ≲ **0.50** (operationally: `p3_acc < 0.55`, i.e. it fails to clear the plan's own ≥0.55 bar) | The 84 features **cannot rank siblings even against a perfect, noiseless target.** "More labels" is then **arithmetically not the story** at this representation — a label route cannot recover an ordering the features do not carry. The label routes (b)/(c) and the graded-corpus expansions G1/G2 are **dead on arrival**. | Still run the **free** A1–A3 label sweep (T1/T2/T3) to convert `PLAN.md` §7.2's already-fired kill into a **label-scaled** kill — "…and it stays dead at 16.3× the labels, with the rank-accuracy error bar down to ±0.004" — and then **STOP**. The readout closes the lever. **Do not** run the M1–M3 ladder as a rescue, do not fund B1/B2/B3/B′, do not fund G1/G2. |
| **ALIVE** | `p3_acc` ≥ **0.55** | The features carry real signal; stage-0 was noise- and/or count-limited. | Proceed to the **full free tier**: A1–A3 label sweep, the M1–M3 model ladder at the top label rung, the κ ∈ {0, 0.5, 1}·`se_pair` near-tie sweep. The readout then says **P2 decides depth-vs-breadth** for any future funded route (B′ if P2 shows a label-noise problem, B1/B2 if it does not), and **only then** does G1 make sense. |

### 3.1 The boundary is declared, not negotiable

`0.55` is `PLAN.md` §9.2's own boundary between its "≈0.50" row and its "≈0.55–0.60" row.
There is no third branch and no "close enough" clause. A `p3_acc` of, say, 0.538 is **DEAD**
under this rule — it does not license the M-ladder rescue, and the readout must say so
plainly rather than re-describing the bar.

`p3_acc > 0.60` is a **sub-case of ALIVE**, not a separate branch: it additionally licenses
*recommending* (not executing — the free tier funds no compute) `PLAN.md`'s T4/T5 rungs and
the `n = 1,645` graded expansion.

### 3.2 What P3 CANNOT do, in either branch

* It cannot **convict** the lever. `PLAN.md` §7.1 needs a capture read on the graded 733 with
  `CI_lo > 0`; P3 produces no capture number at all.
* It cannot **rescue** stage-0's `arb_net` = −0.0451. A high `p3_acc` would say the features
  can rank against the *oracle*; the tie-net's target is the *arbiter*, and the gap between
  those two is exactly what P2 prices.
* A **DEAD** reading is a statement about **these 84 features**, not about every possible
  representation. `PLAN.md` §5 R3 (board planes) is untouched by P3 — and stays **gated**,
  because CL-064/CL-065 already priced that re-litigation and the plan's own §5 box refuses
  to put "more capacity" at the top of the ladder.

---

## 4. HONESTY RAILS THAT TRAVEL WITH EVERY P3 NUMBER

Reproduced verbatim from `PLAN.md`; they are printed in `FREE_TIER_READOUT.md` too.

* **CEILING CAVEAT** — on this corpus the entire *judge-quality* ceiling is `ora − arb =
  +0.048` with `F` CI95 [0.450, 1.320] **including 1**. That caveat bounds the *v2.9-picker*
  question. It does **not** bound the tie-net question: the tie-net's target is `arb` itself
  (+0.2065 — amortizing the rollouts at ~zero wall), not the +0.048 residual. Stated so
  nobody mis-imports it in either direction.
* **NET FOLD ASYMMETRY** — `tier1`/`v29` select on M/2 worlds and are priced on the disjoint
  M/2; the net's pick is world-independent, so its `arb` is a **full-M** difference — same
  estimand, **less noise**. Its winner's-curse control is the **root split**, not the world
  split.
* **COLLINEARITY NOTE** (`PLAN.md` §5 R1) — for a LINEAR pairwise ranker on `x_a − x_b` the
  afterstate-minus-ROOT diff features **cancel exactly**: `(x_a−x_r)−(x_b−x_r) = x_a−x_b`.
  R1 is perfectly collinear with R0 in a linear model and adds **literally nothing**. It is a
  rung **only** paired with M2/M3.
* **THE ~10–15% PRIOR** (`PLAN.md` §8) — stated before any number was bought: ~10–15% that
  any stage-1 tier clears §7.1. The free tier is designed to be worth running *at that
  prior* because its primary deliverable is a **powered kill**, not a hoped-for win.
* **The stage-0 park gate said PARK.** Nothing in the free tier overturns it. The override
  the owner funded is an **engineering-time decision, not a compute-spend decision**.

---

## 5. ANTI-SHOPPING

Per `PLAN.md` §7.4 the graded 733 is a **spent** corpus and stage-1 is licensed **one**
headline capture read against it. P3 is **not** that read — it produces no capture. The one
headline capture read is spent by the top label rung × the inner-CV-selected feature rung of
the A/M sweep, and every other cell on the label × feature grid is reported as **rank
accuracy only** and **may not be quoted as capture**.

---

*Committed 2026-08-23 before the first P3 fit. Branch: `tienet-free-tier`.*
