# F4_PREREG — the OUT-OF-FAMILY JUDGE leg of the champion EV-loss autopsy

**BLIND STAMP.** This file, `f4_judge_leg.py`, `f4_adjudicate.py` and `test_f4_adjudicate.py`
are committed **before a single tier1-greedy value is computed**. The commit hash of that
commit is the blind stamp and is recorded in `F4_READOUT.json`. Nothing below was written
with an F4 outcome number in view. The R1/R2 **clair-puct** numbers *are* in view — they are
the banked map F4 is testing against, and they are frozen (`R2_READOUT.json`,
blind stamp `2d5cb1f5ad15396b4e324a09d8db01c7cbdf0b16`).

**Status:** PREREGISTRATION — F4 (out-of-family judge) leg of the evloss autopsy.
**Funded:** owner, 2026-08-26, verbatim *"fund f4"*.
**Parent prereg (binding):** `measurement/evloss_autopsy_r2/R2_PREREG.md` §7 (the funnel gate),
§2 (the estimator), §3–§4 (the bucket family); `scratchpad/evloss_autopsy/run/PLAN.md` §1
(the estimand), §6 (the leg structure and the CRN rule), §7 (the read rule).
**Parent deviations:** `run/DEVIATIONS.md` D-L0/D-L1; `evloss_autopsy_r2/DEVIATIONS.md` D-R2-0…6.
**F4 deviations:** `DEVIATIONS.md` beside this file, D-F4-0 …

**Class:** descriptive scouting. 0 evaluation games · no elo · no band-confirmatory use ·
no `results.csv` row · no CL minted · `governance/PRODUCTION.yaml` untouched · no strength
claim · no bucket-gated deployment, ever (the `everyply` DESIGN §4.5 fence).

---

## 1. What R2's prereg actually says about F4, quoted

`R2_PREREG.md` §7, the funnel-gate table, row F4, **verbatim**:

> | **F4** | `tier1-greedy` (out-of-family) agrees on **sign**, and the category has a
> **leaf-computable predicate** | ❌ **sign check** — no out-of-family judge leg exists in
> the banked corpus (PLAN.md §6: it is python-only by construction and was never run).
> ✅ predicate check |

and, in the verdict vocabulary,

> - **`FUNNEL-OPEN-PENDING-SIGN`** — ≥ 1 category satisfies F1∧F2∧F3 and has a
>   leaf-computable predicate. This is the **strongest verdict the banked corpus can
>   support**; F4's sign check is owed before a term dollar is spent, and the named cost is
>   one python-only `tier1-greedy` judge leg over the same rids.

`R2_READOUT.json.funnel_gate.conditions.F4` restates it as:

> "tier1-greedy out-of-family SIGN CHECK — NOT COMPUTABLE from the banked corpus (no such
> leg exists); leaf-computable-predicate half is satisfied by every pre-registered bucket by
> construction"

`PLAN.md` §6 adds the family fact:

> ⚠️ **`v29-greedy` is IN-FAMILY** (the champion's own curve125 flat leaf at depth 0) — it is
> the *leaf* arm, NOT an out-of-family discriminator. `tier1-greedy` remains the only
> out-of-family judge, is python-only by construction, and is **R2's** sign check, not R1's.

### What is BINDING and what is UNDER-SPECIFIED

**BINDING (restated, not invented):**

| | |
|---|---|
| the judge | `tier1-greedy`, out-of-family, **python-only** |
| the corpus | the **same rids** — no new positions, no re-sampling, the holdout split untouched |
| the test | a **SIGN** check, never a magnitude check |
| the second half | the category must have a **leaf-computable predicate** |
| the categories | the 7 F1∧F2∧F3 winners named in `R2_READOUT.json.funnel_gate.winners` |
| the estimator | R2 §2 — Hájek on `1/π_s`, cluster-robust sandwich on `game_id` |

**UNDER-SPECIFIED — the arithmetic below is written by this prereg and is new:**

1. *Sign of **what**?* `R_champ = max(0, D_leaf, …, D_sib4)` is **non-negative by
   construction**, so "the out-of-family judge agrees on the sign of `R̄_champ`" is
   vacuously true for any judge, including a random one. A sign check on `R̄_champ` is
   **not a test**. §4 defines the non-degenerate statistic instead.
2. *At what significance?* R2 names no bar for F4.
3. *Per-category or family-wide?* R2 names neither.
4. *What verdict enum does the funnel take on afterwards?* R2 defines only the three
   pre-F4 verdicts.
5. *How is the winner's-curse-under-CRN confound priced?* R2 does not raise it; §4.3 does,
   and §4.3 is the reason this leg scores **all four arms** rather than one.

Everything in §§2–7 that is not a quotation is this prereg's own completion, written
before any tier1-greedy value exists.

---

## 2. The leg — same positions, same worlds, one thing changed

| | |
|---|---|
| harness | `scripts/measurement_infra/oracle_score_pilot.py` (the R1 harness, unmodified) |
| the ONE change | `--oracle-policy tier1-greedy --backend python` |
| positions | `<share>/positions/positions_{leaf,sib2,sib3,sib4,rnd}.jsonl` — **byte-identical files R1 consumed** |
| M | 32 worlds |
| salt | `evloss-autopsy-20260824-v1` — **identical to R1**, so `world_seed(rid, j, salt)` is bit-identical and F4 is CRN-paired with the R1 legs position-by-position |
| rules profile | `walled`, resolved **from the corpus** exactly as R1 did: `champ_env.sh` sourced, then `CARCASSONNE_FIX_R9` **unset** (`rules_profile.walled.r9_env_expected = False`), then `--rules-profile walled` verifies the import latch |
| `--strict-crn` | on |
| out root | `<share>/judge_f4_tier1greedy/<leg>/records/<rid>.json` — **a new tree**; `<share>/judge/` (R1) is never written to |
| oracle sims | not passed — `ORACLE_POLICIES["tier1-greedy"]["uses_oracle_sims"] = False`; the greedy continuation has no search |

**Operationally, `tier1-greedy` is** `oracle_score_pilot._GreedyContinuation`: a
`carcassonne_ai.rule_based_player.RuleBasedPlayer` seeded with the same pick-independent
`playout_seed`, wrapped in the `(best_action, clear)` shape the shared playout loop expects.
It plays **both seats** to terminal from each afterstate. It shares **neither the search**
(there is none — a 1-ply argmax) **nor the leaf** (`virtual_score_inplace`, the v1 OBJECT
leaf — not the curve125 flat leaf the champion is steered by). World sampling, CRN seed
derivation, replay and the terminal-score read are the **same shared code path** as
clair-puct; `build_continuation_agent` is the only branch point. Rust is refused for this
policy by construction (`BACKEND_UNAVAILABLE_REASON`) — porting a Rust `RuleBasedPlayer`
would destroy the out-of-family property.

### 2.1 Leg scope and the COST LADDER (pre-stated, outcome-blind)

Five legs, mirroring R1 exactly: `leaf` (n=323) · `sib2` (800) · `sib3` (800) · `sib4` (715)
· `rnd` (200) = **2,838 position-legs**.

The smoke (10 positions, synchronous, production knobs) measures mean worker-seconds per
position. The projected wall is `2838 × mean_worker_secs / W`. **This is a COST gate, not an
outcome gate — it reads no judged value.** First rung that fits **≤ 6.0 h** is run:

| rung | legs | position-legs | what is lost |
|---|---|---|---|
| **L1** | leaf · sib2 · sib3 · sib4 · rnd | 2,838 | — |
| **L2** | leaf · sib2 · sib3 · sib4 | 2,638 | the `R_rnd` instrument gate (§6 g6) becomes unavailable; R2 §5.2 already labels `rnd` diagnostic-only |
| **L3** | `argmax` only (one row per rid, `pick_b` = the position's banked clair-puct argmax arm) | 800 | `R̄^T1_champ`, the half-split witness and every selection-free arm-level statistic. Verdict is capped at **`F4-PARTIAL`** |

If even L3 projects past 6.0 h the leg is **not launched** and the estimate is reported.

---

## 3. Estimator — binding, R2's, not re-derived

`hajek`, `cluster_sandwich`, `cluster_bootstrap`, `wsd`, `load_leg`, `contrast_cluster`,
`norm_sf`, `two_sided_p`, `holm` are **imported** from
`measurement/evloss_autopsy_r2/r2_estimator.py` (themselves byte-for-byte R1's). Category
membership is **imported** from `measurement/evloss_autopsy_r2/r2_taxonomy.py`
(`classify`, `axis_of`, `PARTITION_AXES`, `EXPLOIT_BUCKETS`), and the F7 median cut is
**read from the frozen** `R2_READOUT.json.coverage.f7_median_cut` rather than recomputed, so
membership is bit-identical to R2's by construction rather than by re-derivation.

Weights `w_i = ht_weight = 1/π_s`; cluster = `game_id` (= `deck_seed`). Records admitted
**iff `ok is True` and `crn_verified is True`** — the identical `load_leg` filter.

---

## 4. ⭐ THE AGREEMENT ARITHMETIC (new — this prereg's completion of F4)

Notation, per position *i* and arm *a* ∈ {`leaf`,`sib2`,`sib3`,`sib4`}:

```
D^C(i,a) = clair-puct  record["delta"] = V*_C(a) − V*_C(played)      # banked, R1
D^T(i,a) = tier1-greedy record["delta"] = V*_T(a) − V*_T(played)      # this leg
A_i      = arms with BOTH a clair record and a tier1 record
a*_i     = argmax_{a ∈ A_i} D^C(i,a)          # the arm the IN-FAMILY judge preferred
R^C_i    = max(0, D^C(i, a*_i))               # R2's R_champ, reproduced
R^T_i    = max(0, max_{a ∈ A_i} D^T(i,a))     # the tier1-greedy R_champ
```

### 4.1 The primary sign statistic — the SAME-ARM CROSS-JUDGE WITNESS

```
δ_i = D^T(i, a*_i)
```

*Does the out-of-family judge also think the arm the champion's own family preferred beats
what the champion played?* This is exactly the 2026-07-28 precedent's construction
(`oracle_score_pilot` header: re-score the same `(pick_a, pick_b)` pair out of family and
read the **sign**), lifted to the per-category map. **`δ_i` has no `max(0, ·)` clip**, which
is what makes its sign a test rather than an identity.

Per category *b*: `δ̄_b` = Hájek(δ, w) over the category, `se_b` = `cluster_sandwich` on
`game_id`, `z_b = δ̄_b / se_b`, one-sided upper p = `norm_sf(z_b)`.

### 4.2 The reported map — `R̄^T1_champ`

Per category *b*: Hájek mean of `R^T_i`, cluster-robust `se`, `z_vs_0`, `z_vs_bar` (+0.5),
`UB95`, and the same `contrast_cluster` bucket-vs-complement z R2 reports.
⚠️ **This is a MAP, not a test.** `R^T ≥ 0` by construction, so its z-vs-0 carries no sign
information; it is reported so the two per-category maps can be laid side by side, and it is
**never** compared to R2's `R̄_champ` as a magnitude (the tier1 judge is weaker, noisier —
1.83× on the 2026-07-28 pairing — and carries its own bias: weak follow-up rewards positions
that survive bad play).

### 4.3 The selection confound, and the HALF-SPLIT WITNESS that prices it

`a*_i` is chosen on clair-puct values measured on the **same 32 CRN worlds** the tier1 judge
re-uses. If arm *a* was selected partly because those particular worlds happened to favour
it, a different judge on the *same* worlds inherits that luck: **`δ̄` is biased upward, and
CRN makes this worse rather than better.** R2's prereg does not raise this; it is real and it
is priced here, for free, from per-world values already stored in both judges' records:

```
worlds 0..15  = SELECT half        worlds 16..31 = EVALUATE half
a†_i    = argmax_{a ∈ A_i} mean( per_world_delta^C(i,a)[0:16] )     # clair, select half
δsplit_i = mean( per_world_delta^T(i, a†_i)[16:32] )                # tier1, evaluate half
```

The evaluation half's world draw is independent of the selection, so `δ̄split` is
**selection-unbiased**. It costs nothing extra and requires `a†_i` to be scored — which is
why the leg scores all four arms (rung L1/L2) and why rung L3 is capped at `F4-PARTIAL`.
Reported per category with cluster-robust `se` and `z`.

### 4.4 The per-position agreement rate (the 2026-07-28 precedent's own statistic)

Over positions with `R^C_i > 0`: `agree_i = 1{δ_i > 0}`.
`π_b` = Hájek(agree, w); cluster-robust `se` of `(agree − 0.5)`; one-sided z vs 0.5.
The unweighted, unclustered **binomial** p is reported beside it because that is the form the
2026-07-28 read used (80 %, p = 0.0012) — **the clustered weighted z is the verdict**, per
the `e4_autopsy` owner ruling that a naive-sd z is never the verdict.

### 4.5 Selection-free arm-level agreement (secondary, L1/L2 only)

Over all `(i, a)` pairs in the category, both judges scoring the **same fixed arm**, so no
selection is involved at all:

* `arm_sign_agreement` = weighted fraction with `sign(D^C) == sign(D^T)`, over pairs where
  both are non-zero; cluster-robust one-sided z vs 0.5.
* `pearson_r` between `D^C` and `D^T` over those pairs (descriptive).
* `argmax_concordance` = weighted fraction of positions with
  `argmax_a D^T(i,a) == argmax_a D^C(i,a)` (chance ≈ `1/|A_i|`).

### 4.6 ⭐ THE PER-CATEGORY F4 VERDICT — pre-stated, first match wins

Evaluated on the **7 F1∧F2∧F3 winners** (`R2_READOUT.json.funnel_gate.winners`:
`phase_third=opening`, `structure=FARM`, `structure=CLOISTER`, `move_kind=farm`,
`move_kind=road`, `structure=ROAD`, `H4_DECISIVE_FARM`); computed and reported for all 33.

| verdict | condition |
|---|---|
| **`F4-REFUTED`** | `δ̄_b ≤ 0` — the out-of-family judge does **not** agree on sign |
| **`F4-CONFIRMED`** | `δ̄_b > 0` **and** one-sided `z_b ≥ 1.645` (α = 0.05) **and** `δ̄split_b > 0` |
| **`F4-DIRECTIONAL`** | `δ̄_b > 0` but either `z_b < 1.645` or `δ̄split_b ≤ 0` |

`z ≥ 1.645` **unadjusted** is the primary: the multiplicity of the family was already spent
at F2, and F4 is a directional confirmatory check on 7 pre-specified categories. A
**Holm-across-the-7** column (`F4_confirmed_holm`) is computed on the one-sided p and
reported beside every row, so a reader who wants multiplicity control has it without
anybody choosing after the fact.

⚠️ **Power is expected to be poor and that is a property of the instrument, not of the
finding.** The tier1 judge measured 1.83× noisier than clair-puct on the 2026-07-28 pairing.
`F4-DIRECTIONAL` therefore means *"sign not contradicted, not established"* — it is
explicitly **not** a pass, and it is **not** a fail.

### 4.7 The second half of F4 — the leaf-computable predicate

Pre-stated table (a predicate is leaf-computable iff it is a function of the afterstate
descriptors a static leaf term already sees, with **no search and no judged value**):

| winner | predicate | leaf-computable? |
|---|---|---|
| `phase_third=opening` | `k_remaining ≥ 48` | ✅ deck count |
| `structure=FARM` | `stratum == FARM` | ✅ `autopsy_extract` two-arm structural tag |
| `structure=CLOISTER` | `stratum == CLOISTER` | ✅ |
| `structure=ROAD` | `stratum == ROAD` | ✅ |
| `move_kind=farm` | `decision_type == meeple and move_kind_played == farm` | ✅ |
| `move_kind=road` | `decision_type == meeple and move_kind_played == road` | ✅ |
| `H4_DECISIVE_FARM` | `phase_third == endgame` ∧ farm-engaged ∧ `farm_share ≥ 0.5` | ✅ `farm_share` is a ratio of the production leaf's own term differentials |

All 7 pass, which is what R2 already asserted ("satisfied by every pre-registered bucket by
construction"). It is re-evaluated mechanically by `f4_adjudicate.py` rather than assumed.

---

## 5. ⭐ THE FUNNEL F4 VERDICT ENUM — pre-stated, first match wins

| verdict | condition | consequence |
|---|---|---|
| **`F4-BROKEN`** | any §6 instrument gate fails | ⛔ no read. The leg is re-run or the defect is fixed; **nothing** downstream is read. |
| **`FUNNEL-CLOSED-BY-F4`** | pooled `δ̄ ≤ 0` **or** pooled one-sided `z < 2.0` | ⛔ **CLOSE.** The out-of-family judge does not corroborate the champion's headroom **anywhere**, so the R1/R2 map is not distinguishable from same-family self-preference. **No leaf-term work is licensed.** Deliverable = the refutation. |
| **`FUNNEL-OPEN-F4-CONFIRMED`** | ≥ 1 winner is `F4-CONFIRMED` | ✅ The funnel is open **on the confirmed set only**, which the verdict payload names. Leaf-term work is licensed for those categories, still as a **globally-active** term measured globally (§7). |
| **`FUNNEL-OPEN-F4-DIRECTIONAL`** | no winner `F4-CONFIRMED`, ≥ 1 `F4-DIRECTIONAL`, **0** `F4-REFUTED` | ⚖️ Owner call. Default = **DO NOT fund a term.** The sign is not contradicted but is not established; the honest next purchase is power, not a term. |
| **`FUNNEL-CLOSED-BY-F4-REFUTED`** | every winner is `F4-REFUTED` | ⛔ **CLOSE.** |
| **`FUNNEL-F4-INCONCLUSIVE`** | anything else (e.g. DIRECTIONAL beside REFUTED) | ⚖️ Owner call, default do-not-fund. Per-category table is the deliverable. |
| **`F4-PARTIAL`** *(prefix)* | rung **L3** was run | any verdict above is prefixed `F4-PARTIAL/…`; §4.2, §4.3 and §4.5 are unavailable, and a `CONFIRMED` cannot be reached (the half-split witness is a `F4-CONFIRMED` conjunct). |

The refuted set is **always** named in the payload, whatever the verdict.

---

## 6. Instrument gates — MANDATORY, fail loudly (any failure ⇒ `F4-BROKEN`)

| | gate |
|---|---|
| g1 | every F4 record has `ok is True` **and** `crn_verified is True`; 0 missing, 0 wall-capped, per leg, against the same rid list R1 consumed |
| g2 | every F4 manifest has `oracle_policy == "tier1-greedy"` and `execution.backend_resolved == "python"` |
| g3 | every F4 record has `rules_profile == "walled"` and `world_seed_salt == "evloss-autopsy-20260824-v1"` |
| g4 | ⭐ **cross-judge CRN witness:** for every (rid, leg) present in both trees, the F4 record's `world_seeds` list is **bit-identical** to the R1 record's, and `afterstate_deck_hash_a` / `afterstate_deck_hash_b` are bit-identical too (same worlds, same actions ⇒ same afterstates; only the *continuation* differs). 0 mismatches required. |
| g5 | **reconciliation:** the F4 adjudicator's clair-puct side must reproduce `R2_READOUT.json` — pooled `R_champ` to `1e-12` and **all 33** per-category `R_champ` to `1e-9`. A mismatch is a loader/membership defect; the run stops and nothing F4 is read. |
| g6 | `R_rnd > R_champ` under the tier1 judge, on the rnd subset (L1 only). If an uninformative arm is not worse under the new judge, the new judge is broken. |
| g7 | `arms` availability per rid is identical between the two trees (`A_i` well-defined) |

`R2_READOUT.json`, `funnel_holdout_split.json`, `<share>/judge/**` and the laptop-side D-L1
quarantine are **read-only** to this leg. The holdout split is **not consumed** — F4 is a
judge check, not the Stage-1 screen.

---

## 7. What F4 does NOT license, in any verdict

Nothing about absolute or superhuman strength; nothing about either structural blocker; no
deployment change; **no bucket-gated deployment, ever**. A `FUNNEL-OPEN-F4-CONFIRMED`
licenses a *globally-active leaf-term hypothesis*, measured globally at an n = 800
deck-paired deploy-budget cell — it never licenses "play differently in bucket b". The reach
ceiling still multiplies into every number: a static leaf term reaches at most **62.2 %** of
the oracle spread and 30 % of pools are fully indistinguishable (`tiletie_mining_20260814`).
And the magnitude fence stands: **never quote a tier1-greedy mean as a size**, only as a sign.
