# TERMINAL-GROUNDED TIE ARBITRATION — DESIGN (Stage 1, offline)

> **STATUS AT WRITING: DESIGN, COMMITTED BEFORE ANY ARBITRATION NUMBER EXISTS
> ANYWHERE.** [READ_RULE.md](READ_RULE.md) is committed in the **same commit** as
> this file, and both are committed **before** the instrument
> (`scripts/tiletie/build_tiearb_plan.py`, `scripts/tiletie/analyze_tiearb.py`),
> before the cost pilot, and before one holdout position is scored. Git history
> proves the ordering, and the run manifest carries this commit's hash.
> **0 games. No band. No `experiments/results.csv` row. No claim id minted.**
> `governance/PRODUCTION.yaml` and `governance/BAND_REGISTRY.csv` are untouched
> on **every** branch.

---

## 0. PRE-RUN AMENDMENT — 2026-08-16, applied BEFORE the pilot and BEFORE any position is scored

⚠️ **Nothing here is a result. No arbitration number exists, for either judge, at
the time of this amendment.** Three implementation facts were found while
building the instrument. All three change *how the run is laid out on disk* or
*how a witness is counted*; **none touches an estimator, a statistic, a
threshold, a bar or a branch.** [READ_RULE.md](READ_RULE.md) is **untouched**.

- **0.A — records land per chunk, then merge.** §8 names
  `/mnt/c/carc-shared/tiearb_20260816/tier1-greedy/<profile>/leg<r>/`, but §5's
  mandated 4-chunk shape forces one `--out-root` per chunk:
  `run_tiletie.verify_leg_records` demands a records directory hold exactly its
  own chunk's rids. The OOF §0.A precedent is adopted verbatim —
  `chunk<k>/tier1-greedy/…`, merged by **file copy** into
  `merged/tier1-greedy/…` before analysis, with a duplicate guard, and
  `discover_records` refuses duplicates so a double-merged chunk cannot pass
  silently.
- **0.B — `G-ARMSET`'s denominator is stated.** READ_RULE §3 says *"more than 5%
  of analysed positions"*, but an arm-set-mismatched position is by definition
  **not** analysed, so the literal denominator excludes the numerator's own
  members. The instrument uses `analysed + armset_mismatched` — the set on which
  the comparison was possible — and prints that note beside the fraction. This
  can only make the gate **stricter**, never looser.
- **0.C — the sign check's "aggregate signs match" is disambiguated.** DESIGN
  §4.5 inherits the OOF wording, which was plural because that run had two
  judges. Here there is one headline statistic, so the taxonomy is read as
  *per-position majority direction* vs *the sign of the pooled `mean(arb)`* —
  the reading under which the E4 autopsy's own Tier-1 example (62.1%, aggregate
  NEGATIVE ⇒ `PARTIAL`) reproduces. All three quantities are emitted so any
  other reading is recomputable without re-running. **The sign check is not a
  branch input under any reading.**
- **0.D — no filename firewall, by design.** The OOF run staged in-family
  records by filename so no holdout record was ever opened. **This run spends the
  holdout**, so there is nothing to firewall on the in-family side; `G-SLICE`
  enforces slice *labels* instead, and it is asserted at plan build, at launch,
  and at analysis.

---

## 1. What this is, and the licence it spends

The 2026-08-14 out-of-family re-pricing
([../tiletie_oof_20260814/READOUT.md](../tiletie_oof_20260814/READOUT.md)) fired
pre-registered branch **`C-CONFIRM`**: the +0.252 pts/tied-ply tile-tie headroom
is **not** substantially a judge artifact — a judge sharing neither the leaf nor
the search sees **1.83×** more of it (`H_IF +0.3277` z +3.68 · `H_OOF +0.5987`
z +4.32 · `R = 1.827` CI [+0.913, +3.995] · `R_norm 0.820` · `G-CAL` PASS).

That verdict licences — and does **not** fund — **exactly one thing**, quoted
verbatim from [../tiletie_oof_20260814/READ_RULE.md](../tiletie_oof_20260814/READ_RULE.md) §4:

> *"a fresh pre-registration on the k-width / determinization-at-ties axis — the
> one axis `docs/LEVER_INDEX.md`'s re-open bar names that has never been tried —
> and that prereg must name its MECHANISM before it may spend compute, because
> three capture routes have already read flat and 'try harder on the same axis'
> is not a mechanism."*

⭐ **This is that prereg, and the mechanism is named in §2.** The owner funded it
2026-08-16. It is **Stage 1: offline only.** A pass licenses a *Stage-2 game-cell
pre-registration* — nothing more, and certainly not a game, a band, or a deploy.

---

## 2. THE MECHANISM — **terminal-grounded tie arbitration**

> **HYPOTHESIS.** At a leaf-tied tile ply, break the tie by **CRN-paired
> playouts to terminal** — arbitration policy `tier1-greedy`
> (`carcassonne_ai.rule_based_player.RuleBasedPlayer`, 1-ply argmax, the v1
> object leaf `virtual_score_inplace`, no search), one full continuation per
> (arm × determinization), **selected by cross-fit argmax over the world-mean of
> the terminal margin** — and a material fraction of the headroom is recovered.

### 2.1 The mechanism argument, stated before any number

Every instrument that **sees** the headroom prices the tied arms by
**continuation to terminal**: the pricing oracle (`clair-puct`, 100-sim
clairvoyant PUCT played out to the end of the game on a known deck) and the
out-of-family judge (`tier1-greedy`, a full greedy continuation to terminal) both
return `V[p,a,j]` = **the final-score margin at terminal**. Nothing else in this
program has ever seen it.

The champion's own estimator does **not** touch terminal information. It is fair
PIMC — k=8 determinizations × 1376 sims/det — and every node it expands is
scored by the **curve125 static leaf** at a **truncated frontier**. Its entire
discrimination among leaf-tied arms comes from *search depth over a leaf that is
by construction silent at depth 0*.

The three dead capture routes all leave that property intact:

| route | what it changed | what it kept |
|---|---|---|
| hand-crafted menu ([tiletie_term](../tiletie_term_20260814/DESIGN.md)), `G-FAIL` z −1.82 | added static afterstate terms to the leaf | leaf-truncated frontier |
| mined 38-descriptor menu ([tiletie_mining](../tiletie_mining_20260814/MINING_REPORT.md)), `G2-SCREEN-FAIL` z +0.06, **≤62% reach for ANY deterministic afterstate rule** | mined the terms instead of guessing them | leaf-truncated frontier |
| deeper same-shape search ([tieescalation](../tieescalation_20260814/LADDER_READOUT.md)), **`E-FLAT`** ratios 0.00/0.18/0.18 | 2×/4×/10× sims **per determinization** | leaf-truncated frontier |
| wider determinization ([kwidth_ties](../kwidth_ties_20260814/LADDER_READOUT.md)), **`W-FLAT`** ratios 0.11/0.26/0.09/0.09/0.30 | k16/k32/k64 + two iso-budget controls | leaf-truncated frontier |

⇒ **The one thing common to every flat route is the leaf-truncated frontier, and
the one thing common to every instrument that SEES the headroom is terminal
grounding.** E-FLAT and W-FLAT both reported the same signature —
*"MOVES picks at tied plies without IMPROVING them"* — which is exactly what a
**converged-but-biased** frontier estimate looks like: more compute converges to
the same wrong ordering. Replacing the frontier estimate with the terminal
outcome is the only structural change left that is neither a leaf term, nor
depth, nor width.

### 2.2 Why no existing kill binds this — stated as a claim, checkable

| kill | why it does not bind |
|---|---|
| **`E-FLAT`** (deeper same-shape search) | Escalation buys PUCT sims *per determinization*; every added node is still scored by the curve125 leaf at a truncated frontier. The arbiter adds **no sims at all** — it replaces the frontier estimate with the terminal margin. Different estimator, not more of the same one. |
| **`W-FLAT`** (wider determinization at ties) | k16/32/64 and the iso-budget C1/C2 controls fold **more worlds through the same leaf-truncated search**. The arbiter folds worlds through a **terminal-grounded** continuation. W-FLAT's own re-open bar names the survivor verbatim: *"a mechanism that is neither static-leaf, nor depth, nor width"* — terminal grounding is on the determinization axis (it is **which worlds**) but it is none of those three. |
| **static-menu kills** (`G-FAIL`, `G2-SCREEN-FAIL`, the **38% reach bound**) | The mining bound is a bound on **deterministic functions of the afterstate descriptor space** (*"ANY deterministic rule over the whole descriptor space reaches ≤62% of the naive prize"*). The arbiter is **not a state function of the afterstate at all**: it is a function of (afterstate × sampled deck completions × a continuation policy) and is stochastic in the deck draw. The bound has no purchase on it. |
| **CL-065 / CL-073** (learned tie-breakers, prediction ≠ discrimination) | **Nothing is learned. No parameter is fitted, on any slice, at any point.** The arbiter has zero free parameters — it is an argmax over measured world-means. CL-073's mechanism (a value head predicts the outcome better while ranking siblings worse) is a statement about *learned regressors*; the arbiter does move discrimination directly, by playing the moves out. |
| **CL-076** (Exact-K is closed) | That closes *deeper-than-production exact endgame play at the incumbent K*. This is a mid-game tie arbitration by stochastic rollout, not an endgame solver depth. |
| **CL-078** (the caps/curve scale axis) | Scale-axis closure is about leaf-term magnitudes. No leaf term is touched; the production leaf hash `a36d2e15a3b3d71d` is unchanged and is gate-checked at launch (`G-LEAF`). |

### 2.3 Is the arbiter deployable? — the honest answer, stated up front

**Information-wise, yes.** The worlds `j` are deck completions sampled from the
root's information set (`world_seeds[j] = sha256("world"|rid|j|salt)`), which is
exactly what fair PIMC already does; the continuation policy is a real policy the
project ships. The arbiter uses **no** information the champion could not have.
The only non-deployable element is the **cross-fit**, and it is a *measurement*
device that makes the estimate **conservative**: a deployed arbiter would select
on all 32 worlds and be at least as good as one selecting on 16.

**Cost-wise, no — not at this shape, and that is stated before the run.** At the
measured `c_tier1 = 2.1783` worker-s/playout, one tied ply with `A` arms costs
`A × 32 × 2.18` worker-s ≈ **140 s (A=2) to 350 s (A=5)** against the champion's
**1.551 s/move** on the phone — a 100–200× overrun. ⇒ **Stage 1 is a
value-of-information test: is terminal grounding worth anything at all at tied
plies?** If it is, the Stage-2 prereg this licences must confront cost on its own
terms (fewer worlds · a rust continuation · a cheaper policy · trigger-gating),
and **that budget question is explicitly NOT answered here.**

---

## 3. Instrument, corpus, and the CRN property that makes it affordable

### 3.1 The corpus is the pricing corpus, and 71% of the compute already exists

| slice | positions | roots | legs | `clair-puct` (IF) records | `tier1-greedy` (ARB) records |
|---|---|---|---|---|---|
| **DEV** | 522 | 279 | 1,076 | ✅ exist (pricing 2026-08-12) | ✅ exist (OOF 2026-08-14: 1,033 main + 43 pilot) |
| **HOLDOUT** ⛔ never opened by any program | 211 | 120 | 392 | ✅ exist (pricing 2026-08-12, never read) | ❌ **this run produces them** |
| **POOLED** | **733** | **399** | **1,468** | | |

Arm-count composition — pooled `{2:295, 3:206, 4:167, 5:65}`; holdout
`{2:103, 3:53, 4:37, 5:18}`.

⚠️ **THIS RUN SPENDS THE HOLDOUT.** It has survived `G2-SCREEN-FAIL`, `E-FLAT`,
`W-FLAT` and `C-CONFIRM` unburned. After this run it is **burned** and is no
longer available as a reserve. That is a governance fact recorded on every branch.

### 3.2 Instrument — unmodified where it matters

- **Scoring**: `scripts/tiletie/run_tiletie.py --judges tier1-greedy`,
  **unmodified**, driving `scripts/measurement_infra/oracle_score_pilot.py`,
  **unmodified** — the identical path the OOF run used.
- **New code, additive only, living in `scripts/tiletie/`**:
  `build_tiearb_plan.py` (plan surgery: selects the holdout slice, writes
  `run_tiletie`-shaped leg files, asserts the slice) and `analyze_tiearb.py`
  (the join + the §4 statistics + the read-rule adjudication). Neither modifies
  any existing analyser. `analyze_tiletie.py`'s `parity_indices`,
  `cluster_robust`, `bootstrap_roots`, `zero_rates`, `pts_to_elo` and
  `crossfit_regret` are **imported and reused**, not reimplemented.
  Tests: `tests/test_tiearb.py`.

### 3.3 The CRN convention — forced, not chosen

`world_seeds[j] = sha256("world" | rid | j | salt)`,
`playout_seeds[j] = sha256("playout" | rid | j | salt)` — keyed on `rid` and the
run-wide salt, **never on the arms and never on the judge**. The in-family
holdout records already exist at **salt `tiletie-v1`, M = 32**, so the arbiter's
salt is **`tiletie-v1`** and `M = 32`: there is no free choice, and the
consequence is that the arbiter scores **the identical 32 deck completions, in
the identical order, arm for arm**, as the pricing judge did. Every cross-judge
comparison in §4 is therefore **CRN-paired at the world level**, and bit-identity
of `world_seeds`/`playout_seeds` is a hard integrity witness (`G-CRN`, §6).

⚠️ **`M` is load-bearing and must NOT be raised** (the OOF §3.2 argument,
inherited verbatim): the cross-fit selects on M/2 and evaluates on M/2, so a
larger M makes the selection less noisy and the estimand **larger**. Locked at 32
by comparability with the existing records, not by cost.

### 3.4 Knobs

| knob | value | why it is not a choice |
|---|---|---|
| `--m` | **32** | §3.3. |
| `--world-seed-salt` | **`tiletie-v1`** | §3.3 — forced by the existing IF records. |
| `--oracle-sims` | 100 (recorded, **inert** — the judge has no search) | manifest comparability only. |
| `--backend` | **python** | forced by the harness for `tier1-greedy`; no rust `RuleBasedPlayer` exists. |
| arms / dedupe / cap `J` / reference arm | **as built** in the corpus's own `ARMS.json` | not rebuilt, not re-drawn, not re-capped. |
| `--strict-crn` | **on** (default) | a deck-hash mismatch fails the position loudly. |
| `--workers` | **30** (local box) | throughput only; cannot move a value. Box censused idle before launch. |

**Nothing above is tuned on data.** The only quantity the §5 pilot may set is the
launch shape, which cannot move an estimate.

---

## 4. Statistics

Notation: `V^IF[p,a,j]` and `V^ARB[p,a,j]` are the terminal margins in final-score
points at the root player's seat, position `p`, arm `a`, CRN world `j = 1…32`,
under `clair-puct` and `tier1-greedy` respectively — **the same physical
quantity on the same decks**, differing in the continuation policy (the OOF §4.3
estimand caveat is inherited verbatim and travels with every number below).

`arm_order = [0] + scored_legs` exactly as `analyze_tiletie.build_positions`
assembles it; `champ` = the corpus's own `ARMS.json::champ_arm_index`; positions
whose champion arm is not in the scored set are **dropped** (counted and
reported), which is `analyze_tiletie`'s own behaviour.

### 4.1 The arbiter, and the cross-fit that makes it winner's-curse-clean

Parity halves from `analyze_tiletie.parity_indices(32, base=1)` — the primary
run's realized `I1-parity-base` choice — plus its swap. For each fold
`(sel, eva)`:

```
a_arb   = argmax_a  mean_{j ∈ sel} V^ARB[p, a, j]        # ARBITRATION  (tier1-greedy)
arb[p]  = mean_{j ∈ eva} V^IF[p, a_arb, j]
        − mean_{j ∈ eva} V^IF[p, champ, j]               # PRICING      (clair-puct)
```

and the pre-registered target, computed by the **same** function on the **same**
worlds (this is `analyze_tiletie.crossfit_regret`'s `headroom_champ`):

```
a_ora   = argmax_a  mean_{j ∈ sel} V^IF [p, a, j]
ora[p]  = mean_{j ∈ eva} V^IF[p, a_ora, j]
        − mean_{j ∈ eva} V^IF[p, champ, j]               # THE HEADROOM
```

Both are **symmetrized over the two folds** (`(fold1 + fold2)/2`), which is the
escalation/kwidth ladders' own `honest_regret` convention, so the `I1`
parity-base ambiguity cannot matter; the single-fold `parity_base=1` readings are
reported beside them as diagnostics. Every position's value is multiplied by its
stratum's `scale_all` (the analytic-zero population share, `INTERPRETATIONS I2`)
so the numbers are in the **same currency as every prior tile-tie number**; the
`discriminable` (unscaled) reading is reported alongside.

⭐ **Non-circularity is structural, not asserted**: the arm is chosen by
`tier1-greedy` on the **selection** worlds; it is priced by `clair-puct` on the
**disjoint evaluation** worlds. Selection and evaluation share neither the judge
nor the world. Because the two judges' values at the *same* world `j` are
correlated (same deck), pricing on all 32 worlds would leak a winner's curse
through the shared deck draw — which is precisely why the cross-fit is not
optional here, even though the ladders (whose selector is a search that never
touches the oracle values) could legitimately price on all M.

### 4.2 The primary statistic — captured fraction

```
F        =  mean_p arb[p]  /  mean_p ora[p]          # PRIMARY captured fraction
F_fixed  =  mean_p arb[p]  /  0.2803                 # cross-programme currency
```

- **`F`** — numerator and denominator under the **same judge** (`clair-puct`), on
  the **same positions**, in the **same scaling**, sharing the same champion
  baseline on the same evaluation worlds. 95% CI from the **root bootstrap**
  (20,000 reps, seed **20260816**, resampling the 399 roots with replacement and
  recomputing *both* numerator and denominator inside each rep, so their positive
  correlation is priced automatically). The fraction of bootstrap reps whose
  **denominator crossed 0** is reported so a bimodal ratio cannot hide (the OOF
  `G-DENOM` discipline).
- **`F_fixed`** — the denominator **+0.2803 ± 0.0708 pts/ply** is the
  *honest base-rung regret* that **both** `E-FLAT` and `W-FLAT` were adjudicated
  against ([LADDER_READOUT §](../tieescalation_20260814/LADDER_READOUT.md), n=518
  dev, `scale_all` applied, symmetrized parity-split, base = the corpus champ
  pick, witness 485/485). It is a **fixed constant with no holdout noise**, and
  it puts this run's capture ratio in **exactly the same currency** as
  E-FLAT's 0.00/0.18/0.18 and W-FLAT's 0.11/0.26/0.09/0.09/0.30. ⚠️ Declared
  difference: the ladders' numerators are full-M mean differences (their selector
  is independent of the oracle values); ours is a cross-fit half-M difference —
  unbiased for the same estimand, **noisier**, never *larger* in expectation.

`z_arb = mean_p arb[p] / se_cluster`, cluster-robust on `root_id` (the house
sandwich estimator, `analyze_tiletie.cluster_robust`, `G/(G−1)` corrected).

### 4.3 Mandatory companions — reported on every branch, never a branch input

| id | quantity | why |
|---|---|---|
| `C-RND` | a **random-arm arbiter**: `a_rnd` drawn by `random.Random(sha256(rid)⊕20260816)` over `arm_order`, priced identically | the null level. `arb[p]` is **not** zero-mean under "the arbiter is uninformative" — it is `mean-over-arms − champ`. `C-RND` measures that offset directly, on the same worlds, for free. |
| `C-ARM0` | the same statistic with **arm 0** (the leaf's lowest-index tie-break) as the comparator instead of `champ` — i.e. `analyze_tiletie`'s `headroom_leaf` currency | the ladders' and the pricing run's `S2b`; guards against the champion baseline carrying the result. |
| `SEC-ARB` ⚠️ **AUDIT-ONLY** | the arbiter's picks **priced by `tier1-greedy` itself** | it shares the arbitration policy. ⚠️ **Its capture fraction against its own headroom is `1` BY CONSTRUCTION** (self-arbitration priced by the self-judge *is* the cross-fit headroom) — which is the whole reason it can never be a branch input. Reported as the **pts** value with its `z`, labelled circular. |
| `R_holdout` | `H_ARB / H_IF` on the **holdout only** — the OOF run's retention ratio, recomputed on positions it never opened | a **free out-of-sample replication of `C-CONFIRM`**. Reported; adjudicates nothing (the OOF read-rule is spent). |
| `H_IF_holdout` | the in-family headroom on the holdout, with `z` | a free out-of-sample confirmation of the +0.252 itself. |
| `PICKCHG` | fraction of positions where `a_arb ≠ champ` (per fold and pooled), and where `a_arb = a_ora` (selector agreement) | the E-FLAT/W-FLAT diagnostic — *"moves picks without improving them"* is read off this beside `arb`. |
| sign check | §4.5 | mandatory, in the E4-autopsy taxonomy. |
| bound chain | `pts_to_elo` with `TIED_TILE_PLIES_PER_GAME = 22.96`, `NON_ADDITIVITY = 3.2` and its `/5.23` low-end bracket, `σ_game` sensitivity, and the ×1.40 full-set extrapolation | applied **identically** to numerator and denominator so it **cancels out of `F`**. Every §4.3 caveat inherited verbatim: `NON_ADDITIVITY = 3.2` is **n = 1** with a ±1.6× bracket, not a point. |

Per-stratum (`e4`/`selfplay`), per-profile, per-phase and capped/uncapped cuts
are emitted beside the pooled read and are labelled underpowered.
**No branch is ever adjudicated on a cut.**

### 4.4 ⚠️ POWER — the arithmetic, and the deviation it forces

**Anchors (all published, none from this run):**

- pricing realized per-position sd of `headroom_all` = **1.9697** pts at n=733,
  cluster-robust se **0.0735** (design effect ≈ 1.0);
- E-FLAT/W-FLAT numerator se at n=522 = **0.0362–0.0598** at pick-change
  **0.18–0.31** ⇒ implied pooled per-position sd **1.37** at q=0.31 ⇒
  per-changed-position sd ≈ **2.45** pts.

**Projection for `arb`.** Two things move it off the ladder anchor:
(i) cross-fit pricing on M/2 per fold, fold-averaged ⇒ **×1.0–1.4**;
(ii) a much higher pick-change rate — the arbiter is an argmax over 16 measured
world-means, not a deeper search, so plan `q ≈ 0.5–0.8` against the ladders'
0.18–0.31 ⇒ **×√(q/0.31) = ×1.27–1.61**. Hence

```
sd_position(arb)  ≈  1.37 × (1.0–1.4) × (1.27–1.61)   =  1.74 – 3.09  pts
se(arb) at n = 733                                     =  0.064 – 0.114   (central ≈ 0.085)
se(arb) at n = 211 (holdout alone)                     =  0.120 – 0.213   (central ≈ 0.159)
```

(Upper-bounded independently: `ora`'s own realized sd is 1.9697, and the oracle's
argmax is the most extreme selector available, so `sd(arb) ≲ 2 × sd(ora)` — the
bracket above is consistent with that.)

**Consequences, stated before the run:**

| | 2σ resolution [pts/ply] | in `F_fixed` units |
|---|---|---|
| holdout alone, n = 211 | **0.24 – 0.43** | **0.86 – 1.52** |
| pooled, n = 733 | **0.13 – 0.23** | **0.46 – 0.81** |

⛔ **The holdout alone cannot resolve the gate — it cannot reliably convict even a
100% capture.** It *can* resolve the **sign**.
⇒ **DECLARED DEVIATION FROM THE FUNDING BRIEF** (which specified the holdout as
the main read): **the branch input is the POOLED n = 733 read**, and the holdout
enters `A-CAPTURE` as a **blind sign-consistency conjunct** (`F_holdout ≥ 0`), so
a pooled pass driven entirely by the burned slice cannot fire. The brief
anticipated this exact case in writing (*"If the holdout is too small to resolve
the gate, say so in the DESIGN and define what IS resolvable"*), so the deviation
is licensed by the brief, but it is flagged here and in the read-out.

**Why pooling with dev is legitimate, argued not assumed.** The corpus-reuse cap
governs **fitting** — each menu pass *selects* a hypothesis by maximising measured
capture against the same fixed oracle labels. Here (a) **the arbiter has zero free
parameters** and was named a priori by a mechanism argument, so there is nothing
to shop and no multiplicity is spent; (b) **no arbitration statistic has ever been
computed on any part of this corpus** — dev is as blind to *this estimator* as
holdout is; and (c) this read-rule is committed before either slice is touched.
What dev *has* been shopped for is **menus and rungs**, none of which can select
an argmax-over-playouts arbiter. The holdout's extra value is that it is blind to
the three failed programmes as well, which is exactly what the conjunct buys.

**Even at n = 733 the design can only convict a LARGE capture:** `z ≥ 2.0` needs
`arb ≥ 0.13–0.23` pts, i.e. `F_fixed ≥ 0.46–0.81`. A capture in the 0.18–0.30
band that E-FLAT and W-FLAT saw would land in `P-PARTIAL`, not `A-CAPTURE`.
**Resolving `F_fixed` to ±0.35 at 2σ needs n ≈ 2,200 positions; the entire
deduped supply is 733.** That is stated now so the read-out cannot present an
underpowered null as an exclusion — and it is why `F-FLAT` is written as a
**funding verdict, not an exclusion**, in the same words `W-FLAT` used.

### 4.5 The sign check — the E4 autopsy's instrument, unchanged

`scripts/analyzer/analyze_autopsy.py::sign_agreement` applied to the per-position
`arb[p]` over the positions where **the arbiter would change the champion's pick
in at least one fold** (the positions where the mechanism does anything):

- `agreement_rate` = fraction with `arb[p] > 0`, exact two-sided binomial `p` vs
  0.5, and the aggregate sign;
- adjudicated in the autopsy's committed taxonomy — **CORROBORATES** (rate > 0.5,
  p < 0.05, aggregate signs match) · **PARTIAL** (rate > 0.5, p < 0.05, aggregate
  signs opposite) · **NO CORROBORATION** (not distinguishable from chance) —
  printed beside its committed benchmarks (**80% at p 0.0012 = corroboration;
  61.9% at p 0.38 = NOT**) and beside the autopsy's own Tier-1 leg
  (**62.1% at p 2.8e-05, aggregate sign NEGATIVE ⇒ PARTIAL**).

**Mandatory reporting; never a branch input** — the OOF precedent is decisive
here: its own sign check read 57.1% at p 0.0547 (**NO CORROBORATION**) while both
aggregate signs were +1 and the mean was convicted at z +4.32, because a
per-position sign statistic is far weaker than a well-estimated mean. It does
carry one consequence: **if `A-CAPTURE` fires with NO CORROBORATION, the licensed
Stage-2 prereg must carry that fact verbatim** (READ_RULE §4).

### 4.6 What is NOT computed

No new estimator of the headroom, no re-fit, no menu, no re-partition of the
in-family labels, no champion re-search, no eps-band re-read, no leaf change, no
learned component of any kind. Nothing outside the 733-position pricing corpus is
opened.

---

## 5. The cost pilot — 20 DEV positions, and it reads NO strength number

⚠️ **The pilot exists to fix the launch shape and to prove the pipeline, nothing
else.** It runs **after** this DESIGN and [READ_RULE.md](READ_RULE.md) are
committed. It reads **only**: wall-clock, `elapsed_secs`, `n_ok`, `n_failed`,
`crn_verified`, the world/playout-seed identity witness, and one **checksum**
(`G-REPRO`, below). **It does not read `values_a`, `values_b`, `per_world_delta`,
`mean_a`, `mean_b`, `delta`, any sd, or any statistic derived from them.**

- **Draw: the OOF run's own 20 pilot rids** (`../tiletie_oof_20260814/PILOT_RIDS.json`)
  — DEV, non-holdout, and already scored by `tier1-greedy` under the identical
  convention. Choosing them is not a draw at all, so there is nothing to shop,
  and it buys a control the OOF run could not have:
- **`G-REPRO` (new)** — the re-scored pilot legs must be **bit-identical** to the
  OOF run's existing records. Compared as `sha256` over the
  `values_a`/`values_b`/`world_seeds`/`playout_seeds` lists; **only the count of
  matching legs is reported, never a value.** This proves the new plan-builder
  and the new launch reproduce the adjudicated instrument exactly.
- **Pre-committed mechanical rule** (no owner call, no judgement):
  1. `n_failed > 0` **or** any `crn_verified` false **or** any world/playout-seed
     mismatch vs the pricing record **or** `G-REPRO` < 43/43 ⇒ **ABORT; the
     holdout is not launched and stays unburned**; the read-out is a
     `U-UNREADABLE` harness report.
  2. Let `c = Σ elapsed_secs / playouts` and
     `H = 25,088 · c / (3600 · 30)` the projected holdout wall-hours at W30.
     - `H ≤ 4.0` ⇒ **launch all 4 chunks** *(expected: the OOF pilot measured
       `c_tier1 = 2.1783`, giving `H = 0.51` h ≈ 30 min)*;
     - `H > 4.0` ⇒ launch the first `ceil(4 · 4.0 / H)` chunks, floor **3**.
- **Order:** the holdout rids are put in a **seeded permutation (seed 20260816)**,
  written to `POSITION_ORDER.json` **before** launch, and cut into **4 sequential
  chunks** — the OOF §0.A mechanism, because
  `oracle_score_pilot.load_positions_jsonl` sorts by `root_id` and a line-order
  prefix would be stratum-biased. **Any number of completed chunks is a uniform
  random subsample of the holdout**, so a partial run is still an unbiased read at
  its realized `n`.

**ETA, stated before launch:** pilot `43 legs × 64 = 2,752` playouts ×
2.1783 s = **1.67 worker-h ⇒ ≈ 3.3 min at W30**; holdout `392 legs × 64 =
25,088` playouts × 2.1783 s = **15.18 worker-h ⇒ ≈ 30 min at W30**. Local box
only (W30, `nice -n 19`, detached); no laptop leg — the analysis phase reads the
share and the laptop's `/mnt/c` resolves to its own Windows drive
([CLUSTER_OPS](../../docs/CLUSTER_OPS.md)), and 30 minutes does not justify the
split.

---

## 6. Integrity gates — mechanical, and they void the run

| id | check | consequence |
|---|---|---|
| `G-CRN` | for every scored leg, the ARB record's `world_seeds` and `playout_seeds` are **bit-identical** to the `clair-puct` record for the same `rid`; `crn_verified` true; `checksum_ok` true | any failure ⇒ **`U-UNREADABLE`**, run void |
| `G-ARM` | `pick_a == ARMS[rid]["arms"][0]` and `pick_b == ARMS[rid]["arms"][r]` for leg `r`, in **both** judges | any failure ⇒ `U-UNREADABLE` |
| `G-VA` | `values_a` bit-identical across all legs of a position, **within** each judge | any failure ⇒ `U-UNREADABLE` |
| `G-SLICE` | every scored ARB `root_id` in the holdout leg **is** in `HOLDOUT_ROOTS.json`; the DEV leg contains **no** holdout root; the two legs are disjoint and their union is the 733-position corpus | any failure ⇒ `U-UNREADABLE` |
| `G-ARMSET` | for every analysed position the two judges' scored `arm_order` are **identical**; positions where they differ are excluded and counted | count reported; >5% ⇒ `U-UNREADABLE` |
| `G-LEAF` | `run_tiletie` preflight: harness leaf hash `== a36d2e15a3b3d71d` | launch refused |
| `G-REPRO` | §5 — 43/43 pilot legs bit-reproduce the OOF records | below 43 ⇒ abort before the holdout launch |
| `G-N` | **≥ 650** of 733 pooled positions analysed, **and ≥ 158** of 211 holdout positions (3 of 4 chunks) | below either ⇒ `U-UNREADABLE` |
| `G-DENOM` | `mean_p ora[p] ≤ 0` **or** `z(ora) < +2.0` on the **pooled** read | ⇒ `U-UNREADABLE` — there is no headroom to capture and `F` has no meaningful denominator. (Pooled `z(ora)` is expected ≈ +3.4 from the pricing readout; the bar is the OOF precedent's, applied where it is affordable.) |
| `G-BOOT` | fraction of bootstrap reps with denominator ≤ 0 | reported always; **> 0.05** ⇒ `F`'s percentile interval is bimodal and **`F` is void as a branch input**; the branch is then read on `F_fixed` alone and the read-out says so |

---

## 7. Threats — stated before the numbers

1. ⭐ **The arbiter and the pricing judge both play to terminal.** They differ in
   policy (`RuleBasedPlayer` 1-ply argmax vs 100-sim clairvoyant PUCT) and are
   independent in the leaf, but they **share the property under test**
   (terminal grounding). ⇒ **a positive here is evidence that terminal grounding
   at ties is worth points *as measured by a terminal-grounded ruler*, which is
   the estimand — it is NOT yet evidence of deploy elo.** That is precisely why a
   pass licenses only a *game-cell prereg* and nothing else, and why the Stage-2
   prereg must be graded on games, not on this corpus.
2. **Regression to the mean cuts toward the null.** Positions were selected on a
   *leaf* property (pricing §6.5); re-scoring by an independent instrument pushes
   measured spread toward 0. ⇒ **a positive read is conservative; a null is the
   expected direction of this bias.** Stated, not corrected.
3. **The arbiter's null level is not zero** — `arb` under an uninformative
   arbiter is `mean-over-arms − champ`, not 0. `C-RND` measures it directly.
   If `C-RND` is materially positive, the champion's pick is below arm-average
   and **part of `arb` is not the mechanism** — the read-out must say so and
   report `arb − rnd` beside `arb`. This is reported, never adjudicated on.
4. **A weak continuation is a different estimand, not a noisier one** (OOF §2.3,
   inherited). Greedy play may wash out the deck-dependent tactics the mining
   pointed at — which here cuts *against* the mechanism, since the arbiter *is*
   the greedy continuation.
5. **94% `walled` self-play, 6% E4** — the rules-epoch confound of pricing §6.6,
   inherited unchanged. Per-stratum reads emitted and labelled underpowered.
6. **Chain-granularity on the TILE class** (pricing §6.2) — inherited, and worse
   here for the same reason as OOF §8.6: the continuation picks the meeple, so
   neither arm gets the meeple its chain value assumed. Direction unknown.
7. **Cap `J = 4` and the ×1.40 full-set extrapolation** — inherited verbatim,
   applied identically to numerator and denominator, so they **cancel out of `F`**.
8. **Contended box** — none expected (censused idle, reserved). Any co-tenant is
   reported. **No value depends on wall-clock.**

---

## 8. Governance

**Measurement only. 0 games on every branch.** No `experiments/results.csv` row
(mirroring the OOF run's disposition for a 0-game analysis: nothing was played,
so nothing is owed), no band, no `governance/BAND_REGISTRY.csv` entry, no claim
id minted, `governance/PRODUCTION.yaml` untouched — on **every** branch. A
`docs/LEVER_INDEX.md` row for *terminal-grounded tie arbitration / playout-priced
tie-break* is created **at start** as in-progress and flipped at close. Outputs
land in this directory (`READOUT.{md,json}`, `PILOT.json`, `POSITION_ORDER.json`,
`positions_holdout/`, `positions_chunk*/`, `positions_pilot/`, `logs/`); oracle
records land on the share at
`/mnt/c/carc-shared/tiearb_20260816/tier1-greedy/<profile>/leg<r>/`.

## Pointers

- [READ_RULE.md](READ_RULE.md) — the pre-committed branches (committed with this file, before any number)
- [../tiletie_oof_20260814/READOUT.md](../tiletie_oof_20260814/READOUT.md) · [DESIGN](../tiletie_oof_20260814/DESIGN.md) · [READ_RULE](../tiletie_oof_20260814/READ_RULE.md) — `C-CONFIRM`, the licence this spends, and the harness/CRN template reused here
- [../tiletie_pricing_20260812/DESIGN.md](../tiletie_pricing_20260812/DESIGN.md) — §4 the estimators, §5 the judge caveat, §6 the threats inherited above
- [../tieescalation_20260814/LADDER_READOUT.md](../tieescalation_20260814/LADDER_READOUT.md) — `E-FLAT`, and the **+0.2803** denominator `F_fixed` is quoted against
- [../tiletie_mining_20260814/MINING_REPORT.md](../tiletie_mining_20260814/MINING_REPORT.md) — the 38% reach bound and `HOLDOUT_ROOTS.json`, the reserve this run spends
- [../tiletie_term_20260814/DESIGN.md](../tiletie_term_20260814/DESIGN.md) — the first failed menu, and §7's corpus-reuse cap addressed in §4.4
- `docs/LEVER_INDEX.md` — the tile-tie rows (212–216) and the new row this run opens
