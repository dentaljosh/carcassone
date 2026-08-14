# TILE-TIE OUT-OF-FAMILY RE-PRICING — DESIGN

> **STATUS AT WRITING: DESIGN, COMMITTED BEFORE ANY OUT-OF-FAMILY NUMBER EXISTS
> ANYWHERE.** The read-rule ([READ_RULE.md](READ_RULE.md)) is committed in the
> same commit as this file, and both are committed **before** the instrument,
> before the cost pilot, and before the run. Git history proves the ordering.
> 0 games this round. `governance/PRODUCTION.yaml`,
> `governance/BAND_REGISTRY.csv` and `experiments/results.csv` are **untouched**;
> no band is claimed; no claim id is minted on any branch.

Overnight, owner-unavailable (Shabbos window). Every choice below is either
fixed from first principles or fixed by a **pre-committed mechanical rule**
evaluated on a ≤20-position cost pilot that is **excluded from the main read**
(§6). Nothing in this program requires an owner decision to adjudicate.

---

## 1. The question

The tile-tie pricing run's headline residual —
**+0.252 pts per tied tile ply, z +3.43, ≈ +34.5 elo, CI [+14.7, +54.7]**
([tiletie_pricing_20260812/readout_POOLED/VERDICT.md](../tiletie_pricing_20260812/readout_POOLED/VERDICT.md))
— is the program's only live positive residual signal. It has now survived
every route that should have *captured* it:

| route | result |
|---|---|
| hand-crafted geometry menu ([tiletie_term_20260814](../tiletie_term_20260814/DESIGN.md)) | `G-FAIL`, z −1.82, leaning harmful |
| mined 38-descriptor menu + reach bound ([tiletie_mining_20260814](../tiletie_mining_20260814/MINING_REPORT.md)) | `G2-SCREEN-FAIL`, z +0.06; **~38% of the spread unreachable by ANY static afterstate function**; 157/522 pools indistinguishable |
| deeper same-shape search ([tieescalation_20260814](../tieescalation_20260814/LADDER_READOUT.md)) | `E-FLAT`, 2×/4×/10× capture ratios 0.00/0.18/0.18, all z < +2 |

Three independent capture routes, all flat. That is the signature of a number
the **ruler** partly invented — and the pricing DESIGN said so in writing
before any of them ran.

> **THE QUESTION.** Does the +0.252 pts/tied-ply headroom survive when the
> tied arms are re-scored by a judge that does **not** share the leaf under
> test?

### 1.1 Why the judge is the prime suspect, in the pricing design's own words

[tiletie_pricing_20260812/DESIGN.md §5](../tiletie_pricing_20260812/DESIGN.md)
("The judge, and the in-family bias — honestly") states the residual bias and
its **direction**:

> *"The residual bias is second-order, and it points DOWN. The judge's deeper
> nodes are still scored by the same leaf. If the leaf's blindness is
> **systematic** — a feature it never represents, e.g. farm-race tempo — then a
> judge built on it is blind to that feature at every node too, and will
> **under-report** the true spread. If the blindness is **idiosyncratic**
> (lattice quantisation at this particular node), the judge recovers it and the
> estimate is unbiased. ⇒ A null through this judge closes 'spread visible to a
> deep clairvoyant search over THIS leaf', not 'spread in truth'."*

⚠️ **That argument prices the direction of a NULL. It does not price a
POSITIVE.** §5 explicitly declares the *positive* case unaudited:

> *"The out-of-family sign check is therefore **not optional here**."*

and §7.3 / the readout's §7 record that the leg was **pre-registered at n = 80,
seed 20260812, and never bought** — because §5 made it purchasable only on a
branch-1 close, and the run landed on branch 4:

> *"The out-of-family `tier1-greedy` sign leg (n=80, §5/§7.3) is the check, and
> it is **bought only if the primary does not branch-1-close**."*
> — [readout_POOLED/VERDICT.md §7](../tiletie_pricing_20260812/readout_POOLED/VERDICT.md)

**This measurement executes that pre-registered leg**, enlarged (§4) and given
its own fresh read-rule. It is the route `docs/LEVER_INDEX.md` already names as
the axis's re-open bar, verbatim:

> *"Re-open bar: a mechanism on a DIFFERENT axis — k-width-at-ties, **or an
> out-of-family oracle leg pricing the spread itself** — each needing its own
> fresh read-rule."*

### 1.2 What this measurement is, and why the corpus-reuse cap does not bind

⚠️ **THIS IS A RE-MEASUREMENT OF PRE-REGISTERED STATISTICS UNDER A DIFFERENT
JUDGE. IT IS NOT MENU SHOPPING.**

[tiletie_term_20260814/DESIGN.md §7](../tiletie_term_20260814/DESIGN.md) sets
the corpus-reuse cap, quoted verbatim:

> *"**A better feature, mined not guessed.** The corpus (`features_*.jsonl` +
> the CRN oracle records) is now joined and reusable at zero cost:
> `term_gate.py --analyze` re-grades any new hand-crafted feature menu in
> minutes — but a new menu needs a NEW pre-committed read-rule file first
> (this one is spent on this menu), and **repeated menu-shopping against the
> same 733 positions burns the corpus (each pass is a new multiplicity; the
> honest route caps it at one or two more mechanism-argued menus).**"*

That cap governs **FITTING**: each menu pass *selects* a hypothesis (a feature,
a weight, a variant) by maximising measured capture **against the same fixed
oracle labels**, and each such pass is a fresh multiplicity on numbers that do
not change. Three properties make this run categorically different:

1. **No hypothesis is selected from data.** The two statistics are
   [pricing DESIGN §4.1 S1a](../tiletie_pricing_20260812/DESIGN.md) and
   **§4.2 S2**, pre-registered 2026-08-12, implemented in
   `scripts/tiletie/analyze_tiletie.py` before any record was read, and
   re-executed here **byte-for-byte through the same code path** with zero free
   parameters. There is nothing to shop.
2. **The labels are NEW.** Every number here comes from *new playouts* by a
   *different judge*. The 733 in-family oracle labels are not re-graded, not
   re-fitted and not re-partitioned; they enter only as the **denominator of a
   pre-declared ratio** (§4.3), on the same positions, computed by the same
   function.
3. **It was itself pre-registered.** §5 of the pricing DESIGN named this exact
   judge, on this exact corpus, before any pricing number existed.

⇒ **No multiplicity is spent and the cap does not bind.** What *is* spent is
this program's own one-shot: the read-rule in [READ_RULE.md](READ_RULE.md) is
consumed on this judge and this slice, and any successor needs a fresh one.

### 1.3 The holdout is not touched

⛔ **`measurement/tiletie_mining_20260814/HOLDOUT_ROOTS.json` — 120 roots /
211 positions — is NEVER READ by any instrument in this directory, on any
branch.** It has survived attempt 2 (`G2-SCREEN-FAIL`) and the escalation
ladder (`E-FLAT`) unburned and it stays unburned here. The instrument filters
it out **by `root_id` before any record path is constructed**, and the
analyser's own slice guard re-asserts it (§7). This program runs on the
**522-position / 279-root DEV slice only**.

---

## 2. The judge — choice, and why it is the only genuinely out-of-family one

### 2.1 The enumeration is closed, and it has exactly two members

`scripts/measurement_infra/oracle_score_pilot.py::ORACLE_POLICIES` is the whole
universe of judges this harness can build (`build_continuation_agent`,
:637-676). There are **two**:

| policy | continuation agent | leaf it evaluates with | family |
|---|---|---|---|
| `clair-puct` *(the pricing judge)* | `HeuristicPriorAgent` via `champion_factory.build_clairvoyant_champion`, PUCT @ `--oracle-sims 100`, clairvoyant deck | **the production curve125 leaf** — `production_prior_cfg()` → `production_leaf_cfg()`, flat/cy leaf, curve125 `(-10,-5,-1.25,0,2.5,3.75,5,6.25)`, cap8/opp_cap8, **leaf hash `a36d2e15a3b3d71d`** | ⛔ **IN-FAMILY — it *is* the leaf under test** |
| **`tier1-greedy`** ⭐ | `_GreedyContinuation` → `carcassonne_ai.rule_based_player.RuleBasedPlayer`, **1-ply argmax, no search at all** | **the v1 OBJECT leaf** — `virtual_score.virtual_score_inplace`; **no `LeafConfig`, no curve125, no flat_leaf, no cap/opp_cap knobs, no meeple curve** | ✅ **OUT-OF-FAMILY** |

**`tier1-greedy` is adopted.** It is the *only* implemented judge that shares
neither the search nor the leaf with the object under test.

### 2.2 The judges considered and rejected — from first principles

- **`h6400_v2.9`** (`HeuristicMCTS@6400`, `heur_leaf="v2_7"`, frozen v2.9
  Bmild_cap8, leaf-cfg hash `7fc930b82801cb43`) — the auto-memory's *"offline
  sibling-regret ruler"*. ⛔ **REJECTED ON TWO INDEPENDENT GROUNDS.**
  (a) **It is not out-of-family.** It is the *same leaf family* as the object
  under test: `champion_factory.py` builds the production leaf as exactly the
  v2.9 Bmild_cap8 leaf with the meeple curve swapped from `CURVE100
  (-8,-4,-1,0,2,3,4,5)` to `CURVE125` — and `CURVE100` is precisely what
  h6400_v2.9 runs. A judge differing from the leaf under test in **one tuned
  constant** cannot arbitrate whether that leaf's blindness is real; it inherits
  the same systematic blindness §5 warns about, and the §5 argument would apply
  to it essentially unchanged. (b) **It is not implemented** as an
  `--oracle-policy`, and `tests/test_oracle_score_pilot.py:341` asserts
  `policy="h6400"` raises.
- **`rodv2_iter02`** — ⛔ **REJECTED.** Not implemented as an oracle policy
  (there is no network continuation agent in `build_continuation_agent`), and
  independently disqualified by its **CL-070 ceiling**: it cannot price
  contrasts above 2752 and mis-orders a +50-elo contrast *including the sign*
  (auto-memory `reference_rodv2_iter2_eval_anchor`). A ruler that mis-signs
  +50 elo cannot arbitrate ≈ +34 elo.
- **Building a leaf-override judge channel** (the `c5_leaf_override.py` /
  `solver_score.py --leaf-variant` dialect) — ⛔ **REJECTED FOR TONIGHT.** It
  would be new measurement machinery inside the ruler on an unattended run, and
  it would need its own identity gate before any number it produced could be
  cited. It is recorded here as the honest successor if `tier1-greedy` proves
  unusable (branch `P-BLIND`, §4.5).

### 2.3 Why `tier1-greedy` is genuinely out-of-family — the mechanism, not the label

The two judges are independent in **all three** places the pricing design's
§5 bias could enter:

1. **Different value function.** `virtual_score_inplace` (v1, object) vs the
   flat curve125 v2.9 leaf. Different code path, different terms, different
   scale. If curve125's blindness is *systematic* — the §5 failure mode — the
   v1 object leaf does not share it, because it does not share the terms.
2. **Different search.** 100-sim clairvoyant PUCT with a persistent tree vs a
   **1-ply argmax with no tree at all**. The pricing §5 argument is that
   `clair-puct`'s *entire discrimination among tied arms comes from search
   depth over a leaf that is silent at depth 0*. `tier1-greedy` has no depth:
   its discrimination comes only from **the terminal outcome of a full
   deterministic greedy continuation**. Nothing in one judge's mechanism is
   reachable from the other's.
3. **Different failure modes.** The v1 object leaf is the very evaluator the
   flat leaf was *built to replace*; the two disagree on real positions by
   construction.

⚠️ **What it is NOT.** It is a *weak* player, and a weak continuation changes
the **estimand**, not merely the noise: it measures *"value of this arm under
greedy continuation on this known deck"*, where the primary measures *"value
under 100-sim clairvoyant PUCT continuation"*. §4.3 and §7 carry that
distinction into every reported number; the read-rule never pretends the two
estimands are the same quantity measured twice.

### 2.4 Affordability — measured, not assumed

| fact | source |
|---|---|
| `tier1-greedy` costs **0.534×** the primary judge on the *same* position (143.2 s vs 268.2 s) | [e4_autopsy_20260812/DESIGN.md](../e4_autopsy_20260812/DESIGN.md) ETA §, measured on a 1-position `fixed_v1` probe |
| it is **rules-agnostic** — a python `RuleBasedPlayer` on the same engine the position is replayed in, so unlike the rust clairvoyant it runs on **every** profile (`walled`, `fixed_v1`, `app_aug2`) with no mirror problem | same |
| it is **python-only**; `--backend rust\|auto` is refused twice (parse time `:1062-1064`, build time `:658-660`) — *"there is no Rust `RuleBasedPlayer`, and porting one would destroy the whole point of an OUT-OF-FAMILY judge"* | `oracle_score_pilot.py:265-274` |
| `--oracle-sims` is **inert** for it (`uses_oracle_sims: False`) — it has no search | `oracle_score_pilot.py:839-849, 1006` |

⇒ **Pre-pilot ETA.** The main slice is 502 positions ⇒ ≈ 1,035 legs ⇒
**≈ 66,240 arm-playouts**. At the pricing run's measured `c_python = 9.85`
worker-s/playout scaled by the autopsy's 0.534× ⇒ `c_tier1 ≈ 5.26` ⇒
**≈ 96.8 worker-h ⇒ ≈ 3.2 h wall at W30.** ⚠️ This is a *transplant* (a
`fixed_v1` E4 probe, and this corpus is 94% `walled` self-play with a different
phase mix), so §6's cost pilot firms it **before** the main launch and §6's
mechanical rule decides what to do if it comes in high.

---

## 3. Instrument — UNMODIFIED, and the CRN is shared with the primary

**`scripts/measurement_infra/oracle_score_pilot.py`, unmodified**, driven by
**`scripts/tiletie/run_tiletie.py --judges tier1-greedy`, unmodified.** Both
already support this judge as a first-class path
(`run_tiletie.JUDGE_BACKEND = {"clair-puct": "rust", "tier1-greedy": "python"}`).
The analyser is **`scripts/tiletie/analyze_tiletie.py`, unmodified**, pointed
at the new records with `--records-root` and at the dev plan with `--plan-dir`.

The only new code is (a) a plan **filter** (`build_oof_plan.py`) that selects
the dev slice and writes the leg files, and (b) a **join** (`analyze_oof.py`)
that puts the two judges' pre-registered outputs side by side and computes the
§4.3 ratio. Neither touches an estimator. Tests: `tests/test_tiletie_oof.py`.

### 3.1 The CRN convention is the primary's, byte-for-byte

`world_seeds[j] = sha256("world" | rid | j | salt)` and
`playout_seeds[j] = sha256("playout" | rid | j | salt)` — **keyed on `rid` and
the run-wide salt, never on the arms and never on the judge**
(`oracle_score_pilot.py:333-355`). So with

- **salt `tiletie-v1`** (the primary's, `run_tiletie.WORLD_SEED_SALT`),
- **M = 32** (the primary's), and
- **the same `rid`s and the same `pick_a`/`pick_b` per leg**,

the out-of-family judge scores **the identical 32 deck completions, in the
identical order, from the identical root**, arm for arm, as `clair-puct` did.
This is the single most important design property here and it is free:

1. Every cross-judge comparison in §4.3 is **CRN-paired at the world level**.
   The deck draw — the dominant variance component — is *shared*, so the paired
   contrast is far tighter than two independent estimates would be.
2. It gives a hard integrity witness: for every scored leg, the new record's
   `world_seeds` and `playout_seeds` **must be bit-identical** to the primary's
   record for the same `rid`. Any mismatch **voids the run** (§7, `G-CRN`).

### 3.2 Knobs — all matched to the primary, none tuned

| knob | value | why it is not a choice |
|---|---|---|
| `--m` | **32** | Matched. ⚠️ **M is load-bearing and must NOT be raised.** The §4.1/§4.2 cross-fit statistics select `a⁺` on M/2 worlds and evaluate on the other M/2, so a larger M makes the selection less noisy and the estimand **larger**. Raising M would silently compare a *different quantity* to the primary's. Locked at 32 by comparability, not by cost. |
| `--world-seed-salt` | **`tiletie-v1`** | Matched — §3.1 is the whole design. |
| `--oracle-sims` | 100 (recorded, **inert**) | The judge has no search; passed only so the manifest is comparable. |
| `--backend` | **python** | Forced by the harness for this judge; no choice exists. |
| cap `J`, arm order, dedupe, reference arm | **as built** | The arms are the corpus's own `ARMS.json` — not rebuilt, not re-drawn, not re-capped. Arm 0 is the leaf's lowest-index tie-break; the champion's pick is an arm exactly where it already was. |
| `--strict-crn` | **on** (default) | A CRN deck-hash mismatch fails the position loudly. |
| `--workers` | **30** | Throughput only; cannot affect a value. Box is idle (verified). |

**Nothing above is tuned on data.** The only quantity the pilot may set is the
**launch shape** (§6), which cannot move an estimate.

---

## 4. Statistics — the pre-registered ones, re-run; plus one declared ratio

Notation as [pricing DESIGN §4](../tiletie_pricing_20260812/DESIGN.md):
`V[p,a,j]` = terminal margin in final-score points, root player's seat, at
position `p`, arm `a`, CRN world `j = 1…32`. Superscript `IF` = in-family
(`clair-puct`, the existing records), `OOF` = out-of-family (`tier1-greedy`,
the new records). **Both are computed on the SAME 502 positions by the SAME
function.**

### 4.1 S1a — SPREAD (pricing §4.1, verbatim)

```
sigma2_arm[p] = (MS_arm[p] - MS_resid[p]) / M          # signed, negatives KEPT
```
Headline `mean_p sigma2_arm` in **pts²**, cluster-robust on `root_id`, root
bootstrap 20,000 reps seed 20260812, reported in both the `discriminable` and
the zero-added `all` scalings exactly as the pricing readout reports them.
Cap-invariant, unbiased under the null at any `J ≥ 2`.

### 4.2 S2 — HEADROOM (pricing §4.2, verbatim) — **the deliverable**

Parity cross-fit, `--parity-base 1` (the primary's realized choice, interpretation
`I1-parity-base`): select `a⁺ = argmax_a mean_{j ∈ sel} V` on the selection half
from a pool **including the champion's own pick**; evaluate on the disjoint half:

```
R[p]        =  mean_{j ∈ eva} V[p, champ, j]  -  mean_{j ∈ eva} V[p, a+, j]
headroom[p] = -R[p]                                            # pts per tied tile ply
```

Reported: `headroom_J4` in the `all` scaling (⭐ the deliverable, the direct
counterpart of the primary's **+0.2519**), the `discriminable` scaling, the
`zeros_strict` sensitivity, **S2b** (leaf regret, arm 0 as comparator), the
`parity_swap` diagnostic, and the audit-only naive companions — i.e. **every
row of the pricing readout's table, regenerated under the new judge.** The
§4.3 bound chain (`pts_to_elo`, `TIED_TILE_PLIES_PER_GAME = 22.96`,
`NON_ADDITIVITY = 3.2` with the `5.23` low-end bracket, `σ_game = 20.4/22.2`)
is applied identically, with every one of its inherited caveats.

### 4.3 The one new quantity: **R, the retention ratio**

```
R  =  headroom_OOF_all  /  headroom_IF_all                (same 502 positions)
```

with a **95% CI from the root bootstrap**: resample the 279 dev roots with
replacement (20,000 reps, seed **20260814**), recompute *both* judges' headroom
on the resampled set, take the ratio, and read the 2.5/97.5 percentiles.
Because the two judges are CRN-paired at the world level and clustered on the
same roots, the bootstrap prices the **correlation between them automatically**
— which is exactly why R can be resolved at n = 502 when neither judge's
absolute headroom can be resolved to ±17 elo at that n.

⚠️ **R IS A MAGNITUDE COMPARISON, AND THE PRICING §5 CAVEAT SAYS NOT TO MAKE
ONE. THE DEVIATION IS DELIBERATE AND IS ARGUED HERE, NOT PAPERED OVER.**

§5's rule — *"Its magnitude is **never** compared to the primary's"* — exists
because the Tier-1 judge is *"~1.83× noisier, has no curve125"*. Both of those
are **scale/precision** objections, and both are answered rather than ignored:

- **The unit is not judge-dependent.** Both judges report the *same physical
  quantity*: the final-score margin at terminal, in points, on the *same
  clairvoyantly-completed decks*. There is no rescaling between them. What
  differs is the **estimand** (value under greedy vs under 100-sim clairvoyant
  PUCT continuation) — a difference of *meaning*, which §7 carries explicitly,
  not a difference of *units*, which would make a ratio meaningless.
- **The noise objection is answered by the estimator, not by assertion.** R's
  CI is bootstrapped over roots with both judges recomputed inside each rep, so
  the Tier-1 judge's extra noise **widens R's interval** exactly as much as it
  should. A noisier judge cannot manufacture a tight R.
- **A noise-normalised companion is mandatory.** The read-out also reports
  ```
  R_norm = (headroom_OOF / sqrt(max(0, S1a_OOF)))  /  (headroom_IF / sqrt(max(0, S1a_IF)))
  ```
  — headroom in units of *each judge's own between-arm spread*, which is
  scale-free by construction and is the strictest reading of the §5 caveat. The
  read-rule's `B-PARTIAL` branch fires if `R` and `R_norm` **straddle the bar**,
  so a branch can never rest on the scale-dependent reading alone.
- **The §5 sign check is ALSO run, unchanged**, in the E4 autopsy's own
  taxonomy (§4.4). So §5's own prescribed statistic is delivered *in addition*
  to R, never replaced by it.

### 4.4 The §5 sign check — the autopsy's precedent instrument, reused unchanged

`scripts/analyzer/analyze_autopsy.py::sign_agreement` (:591-629), applied to
the per-position `headroom` of the two judges over positions where **both** are
non-zero:

- `agreement_rate`, exact two-sided binomial `p`, and each judge's **own
  aggregate sign**;
- adjudicated with the autopsy's committed taxonomy: **CORROBORATES** (rate
  > 0.5, p < 0.05, aggregate signs match) · **PARTIAL** (rate > 0.5, p < 0.05,
  aggregate signs **opposite**) · **NO CORROBORATION** (rate not distinguishable
  from chance);
- against the autopsy's committed benchmarks: **80% at p 0.0012 = corroboration
  (2026-07-28 precedent); 61.9% at p 0.38 = NOT corroboration (farm-war)**.

⚠️ **The precedent is a warning, not a prior.** The E4 autopsy's own Tier-1 leg
read **62.1% agreement at p 2.8e-05 with the secondary's aggregate sign
NEGATIVE ⇒ `PARTIAL`** — *"per-position signs agree above chance, but the
out-of-family judge's own aggregate sign is OPPOSITE the primary's, so it does
not corroborate the DIRECTION."* That is the same agreement rate as the
farm-war run that did **not** corroborate. It is reported here beside our
number so the reader can calibrate ours against a known non-corroboration.

### 4.5 `G-CAL` — the blind-ruler control, free, and it gates COLLAPSE only

⚠️ **The single most dangerous failure mode of this measurement is a
FALSE COLLAPSE**: `tier1-greedy` returning ≈ 0 not because the value is absent
but because a greedy continuation **destroys the tactical difference** the tied
arms embody — which is exactly what the mining's steer
(*"deck/lookahead-dependent tactics, not cheap afterstate geometry"*) predicts
is at stake. `docs/LEVER_INDEX.md`'s false-negative-reservoir row states the
transferable lesson: *"in every case examined the decisive defect was the
INSTRUMENT, not the sample size … when citing a kill, check what graded it."*

So COLLAPSE must not be reachable through a ruler that cannot resolve anything.
`G-CAL` is a **cross-judge, cross-parity calibration** that costs **zero extra
compute** — it is a post-hoc subset of records already scored:

1. **Select** on the *primary's* SELECTION-half worlds only: the arm pairs
   `(0, a)` in the top quartile of `|mean_{j ∈ sel} V^IF[p,a,·] − mean_{j ∈ sel} V^IF[p,0,·]|`
   — i.e. the contrasts the in-family judge, on its own evidence, calls
   **large**.
2. **Evaluate** on the *out-of-family* judge's EVALUATION-half worlds only:
   the sign-aligned mean of
   `mean_{j ∈ eva} V^OOF[p,a,·] − mean_{j ∈ eva} V^OOF[p,0,·]`,
   with cluster-robust `z` on `root_id`.

Selection and evaluation use **different judges AND disjoint worlds**, so the
control is free of the winner's curse in both dimensions.

- **Bar `G-CAL`: aggregate sign-aligned `z ≥ +2.0`.**
- **If `G-CAL` fails, the `X-COLLAPSE` branch is VOID and the read falls to
  `P-BLIND`** (§4.5 of [READ_RULE.md](READ_RULE.md)). A judge that cannot see
  the contrasts the primary calls its largest and most confident is not an
  arbiter of this corpus, and its null is uninformative by the project's own
  standing rule.
- `G-CAL` does **not** gate `C-CONFIRM`: a confirmation does not need a
  power control, because it *is* one.

### 4.6 What is NOT computed

No new estimator, no re-fit, no menu, no re-partition of the in-family labels,
no eps-band re-read, no champion re-search (the champion arm is already scored
— `ARMS.json::champ_arm_index`). The holdout is not read.

---

## 5. Scope — the 502-position dev slice

| | positions | roots |
|---|---|---|
| pricing pooled corpus | 733 | 399 |
| − holdout (`HOLDOUT_ROOTS.json`, seed 2026081402) ⛔ never read | 211 | 120 |
| **= DEV slice** | **522** | **279** |
| − cost pilot (§6, seed 20260814, **excluded from the main read**) | 20 | — |
| **= MAIN READ** | **502** | ≈ 271 |

Dev-slice composition (mechanically verified before the run):
phase **early 201 / mid 170 / late 151**; profile **walled 489 / fixed_v1 30 /
app_aug2 3**; stratum **selfplay 485 / e4 37**; capped 99, uncapped 423.
The main read is the dev slice minus a **seeded uniform** 20, so it inherits
that stratification; the realized composition of whatever completes is reported.

### 5.1 Why the full dev slice, and not the 150–250 the brief suggested

**Power arithmetic, stated before the run.** The primary's realized
per-position sd of `headroom_all` was **1.9697 pts** at n = 733 / 399 roots
with cluster-robust se **0.0735** (design effect ≈ 1.0). Transplanting the
autopsy's **1.83×** noise factor gives `sd_OOF ≈ 3.60 pts`, hence
`2·se ≈ 0.51 pts` at n = 200 and `≈ 0.32 pts` at n = 502 — against an
in-family effect of **+0.252 pts**. At n ≈ 200 the out-of-family leg could not
exclude *anything*: it would return `P-BLIND` almost by construction and the
box-hours would buy no decision. **The full dev slice is therefore taken**, and
it is affordable (§2.4: ≈ 3.2 h at W30 vs a whole overnight window).

⚠️ **Even at n = 502 the *absolute* out-of-family headroom is not resolvable to
±17 elo** — that would need n ≈ 816 and the dev supply is 522. **That is why
§4.3's paired ratio `R`, not the absolute, is the branch input**: the CRN
world-pairing between the judges is the only thing that buys a decision at the
available supply, and `P-BLIND` exists to say so honestly if even that fails.

### 5.2 Deviations from the pricing §5 pre-registration, declared

| §5 as written | here | why |
|---|---|---|
| n = 80, drawn seed 20260812 from the **scored set** | n = 502, the whole **dev** slice | §5's n = 80 was sized for a *sign* check; §5.1's arithmetic shows it cannot support the ratio, and the holdout must stay unburned so the draw is restricted to dev. |
| **SIGN ONLY** | sign check **plus** the declared ratio `R` | §4.3 — the sign check is delivered unchanged *in addition*, never replaced. |
| bought only on a branch-1 close | bought on the standing `LEVER_INDEX` re-open bar | §1.1 — the branch-4 close plus three flat capture routes is the condition the re-open bar names. |

---

## 6. The cost pilot — ≤20 positions, EXCLUDED, and it reads NO value

⚠️ **The pilot exists to fix the LAUNCH SHAPE, nothing else.** It is run
**after** this DESIGN and [READ_RULE.md](READ_RULE.md) are committed, and it
**reads only**: wall-clock, `elapsed_secs`, `n_ok`, `n_failed`, `crn_verified`,
and the world-seed identity witness. **It does not read `values_a`, `values_b`,
`per_world_delta`, `mean_a`, `mean_b`, `delta`, or any statistic derived from
them.** This is the discipline
[tiletie_pricing_20260812/SMOKE.md §4](../tiletie_pricing_20260812/SMOKE.md)
applied to its own smoke, and §7.2's rule — *"the smoke's mean delta is
deliberately NOT reported … quoting it would be peeking at the result the run
exists to measure"* — applied one step more strictly (we do not even read the
sd, because §5.1 fixes n from supply, not from a planning sd, so no nuisance
parameter is needed).

- **Draw:** 20 positions, seeded uniform over the 522 dev positions, seed
  **20260814**, recorded to `PILOT_RIDS.json` **before** the pilot runs.
- **Exclusion:** those 20 rids are removed from the main plan and the analyser
  refuses to include them (§7, `G-PILOT`).
- **Pre-committed mechanical rule** (no owner call, no judgement):
  1. If `n_failed > 0` or `crn_verified` is not true on every pilot record or
     any world-seed mismatch vs the primary ⇒ **abort; the run does not
     launch**; the read-out is a `U-UNREADABLE` harness report.
  2. Let `c` = `Σ elapsed_secs / playouts` from the pilot and
     `H = 66,240 · c / (3600 · 30)` the projected main wall-hours at W30.
     - `H ≤ 8.0` ⇒ **launch the full 502-position main read.** *(expected)*
     - `H > 8.0` ⇒ launch the **largest seeded prefix** of the shuffled main
       order that satisfies `H ≤ 8.0`, floor **n ≥ 250**; if even n = 250
       exceeds 8.0 h, launch n = 250 anyway and let the watchdog carry it.
- **Order:** the main position order is a **seeded random permutation**
  (seed 20260814) written to disk before launch, so **any prefix is a uniform
  random subsample of the dev slice** and a partially-completed run is still an
  unbiased read at its realized n. This is what makes the run safe to leave
  unattended.

---

## 7. Integrity gates — all mechanical, all void the run on failure

| id | check | consequence |
|---|---|---|
| `G-CRN` | for every scored leg, the new record's `world_seeds` and `playout_seeds` are **bit-identical** to the primary's record for the same `rid`; `crn_verified` true; `checksum_ok` true | any failure ⇒ **`U-UNREADABLE`**, run void |
| `G-ARM` | `pick_a == ARMS[rid]["arms"][0]` and `pick_b == ARMS[rid]["arms"][r]` for leg `r`, in **both** judges' records | any failure ⇒ `U-UNREADABLE` |
| `G-VA` | `values_a` bit-identical across all legs of a position (the pricing §2.1 witness), **within each judge** | any failure ⇒ `U-UNREADABLE` |
| `G-HOLDOUT` | **no `root_id` in `HOLDOUT_ROOTS.json` appears anywhere** in the plan, the records, or the analysis | any failure ⇒ `U-UNREADABLE`; asserted at plan build, at launch, and at analysis |
| `G-PILOT` | no pilot rid enters the main read | any failure ⇒ `U-UNREADABLE` |
| `G-LEAF` | `run_tiletie` preflight: harness leaf hash `== a36d2e15a3b3d71d` | launch refused |
| `G-N` | completion `n ≥ 250` positions | below ⇒ `U-UNREADABLE` (report cost + integrity only) |
| `G-CAL` | §4.5, sign-aligned `z ≥ +2.0` | failure ⇒ `X-COLLAPSE` is **VOID**, read falls to `P-BLIND` |

---

## 8. Threats — stated before the numbers

1. ⭐ **A weak continuation is a different estimand, not a noisier one** (§2.3).
   Greedy play may wash out precisely the deck-dependent tactics the mining
   pointed at. **This is the threat `G-CAL` was built for, and `G-CAL` bounds
   it only partially** — it shows the judge can resolve *the primary's largest
   contrasts*, not that it can resolve *tactical* ones specifically. A
   `X-COLLAPSE` therefore closes *"headroom visible to EITHER an in-family
   clairvoyant search OR an out-of-family greedy continuation"* — a materially
   stronger statement than the primary alone supports, but still not
   *"headroom in truth"*. The read-rule's COLLAPSE branch carries that sentence
   verbatim and mandatorily.
2. **Regression to the mean protects COLLAPSE and threatens CONFIRM.** Pricing
   §6.5: positions are selected on a *leaf* property, so re-scoring by an
   independent instrument pushes the measured spread **toward 0**. Under
   `tier1-greedy` this is a second, independent instrument ⇒ the effect is if
   anything **stronger** here. ⇒ **a positive out-of-family read is
   conservative and strong; a null is the expected direction of this bias.**
   Stated, not corrected — and it is the reason `X-COLLAPSE` needs `G-CAL`
   while `C-CONFIRM` does not.
3. **The in-family denominator is itself an estimate.** `R`'s denominator is
   the primary's headroom **on the 502 dev positions**, not the published
   pooled +0.2519. It is recomputed by the same function on the same slice and
   reported explicitly; if the dev-slice in-family headroom is itself ≈ 0 or
   sign-flipped, `R` is meaningless and the read-out says so
   (`U-UNREADABLE`, via the `G-DENOM` rider in the read-rule).
4. **94% `walled` self-play, 6% E4** (dev composition) — the rules-epoch
   confound of pricing §6.6, inherited unchanged. Per-stratum reads are
   emitted and are underpowered on their own.
5. **Cap `J = 4` and the ×1.40 full-set extrapolation** — inherited verbatim,
   applied identically to both judges, so it **cancels out of `R`**.
6. **Chain-granularity on the TILE class** (pricing §6.2) — inherited, and
   **worse here**: the greedy continuation picks the meeple, so neither arm
   gets the meeple its chain value assumed, under a *different* meeple policy
   than the primary used. Direction unknown.
7. **`--oracle-sims 100` is inert** for this judge, so the "the judge is not
   the champion" threat takes a different form: this judge is *far* weaker than
   the champion, not merely shallower.
8. **Contended box** — none expected (the box is idle and reserved), but any
   co-tenant is reported. Wall-clock is indicative; **no value depends on it.**

---

## 9. Governance

**Measurement only. 0 games on every branch.** No `experiments/results.csv`
row, no band claimed, no entry in `governance/BAND_REGISTRY.csv`, no claim id
minted, `governance/PRODUCTION.yaml` untouched — on **every** branch including
`X-COLLAPSE`. A `docs/LEVER_INDEX.md` row is updated regardless of outcome, and
the tile-tie row's *"the +0.252 headroom itself stands, unexplained"* clause is
amended to whatever this run adjudicates. Outputs land in this directory:
`READOUT.{md,json}`, `PILOT.json`, `PILOT_RIDS.json`, `POSITION_ORDER.json`,
`positions_dev/` (plan + leg files), `logs/`; oracle records land on the share
at `/mnt/c/carc-shared/tiletie_oof_20260814/tier1-greedy/<profile>/leg<r>/`.

## Pointers

- [READ_RULE.md](READ_RULE.md) — the pre-committed branches (committed with this file, before any number)
- [../tiletie_pricing_20260812/DESIGN.md](../tiletie_pricing_20260812/DESIGN.md) — §4 the estimators, §5 the judge caveat this run discharges, §7.3 the un-bought n=80 leg
- [../tiletie_pricing_20260812/readout_POOLED/VERDICT.md](../tiletie_pricing_20260812/readout_POOLED/VERDICT.md) — the +0.252 / z +3.43 / +34.5 elo being re-priced
- [../tiletie_term_20260814/DESIGN.md](../tiletie_term_20260814/DESIGN.md) — §7's corpus-reuse cap, quoted in §1.2
- [../tiletie_mining_20260814/MINING_REPORT.md](../tiletie_mining_20260814/MINING_REPORT.md) — the reach bound; `HOLDOUT_ROOTS.json` is the firewall this run honours
- [../tieescalation_20260814/LADDER_READOUT.md](../tieescalation_20260814/LADDER_READOUT.md) — `E-FLAT`, the third flat capture route
- [../e4_autopsy_20260812/DESIGN.md](../e4_autopsy_20260812/DESIGN.md) / [READOUT.md](../e4_autopsy_20260812/READOUT.md) — the out-of-family judge machinery and the 62.1%/`PARTIAL` precedent reused in §4.4
- `docs/LEVER_INDEX.md` — the tile-tie row (the re-open bar this run answers)
