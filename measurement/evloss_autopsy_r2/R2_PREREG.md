# R2_PREREG — the taxonomy read of the champion EV-loss autopsy

**BLIND STAMP.** This file and `r2_taxonomy.py` are committed **before any per-category
outcome number is computed**. The commit hash of that commit is the blind stamp and is
recorded in `R2_READOUT.json`. Nothing in this file was written with a per-category
number in view.

**Status:** PREREGISTRATION — R2 (taxonomy) leg of the evloss autopsy.
**Parent prereg (binding):** `scratchpad/evloss_autopsy/run/PLAN.md` §5 (taxonomy), §7
(read rule), and `scratchpad/evloss_autopsy/SCOPE.md` §4 (the term-discovery read table),
§6 (taxonomy + the four controls), §8 (what funds a term attempt).
**Parent deviations:** `scratchpad/evloss_autopsy/run/DEVIATIONS.md` D-L0, D-L1.
**R2 deviations:** `DEVIATIONS.md` beside this file, D-R2-0 … D-R2-5.

**Class:** descriptive scouting. 0 evaluation games · no elo · no band-confirmatory use ·
no `results.csv` row · no CL minted · `governance/PRODUCTION.yaml` untouched · no strength
claim · no bucket-gated deployment, ever (the `everyply` DESIGN §4.5 fence, restated in
PLAN.md §7).

---

## 1. Corpus — frozen, not regenerated

R2 reads the **banked R1 judged corpus** and adds no compute to it.

| | |
|---|---|
| judged corpus | `<share>/judge/{leaf,sib2,sib3,sib4,rnd}/records/*.json` |
| covariate side file | `<share>/positions/positions_meta.jsonl` (A4: the taxonomy block rides here, joined on `rid`) |
| sampling frame readout | `<share>/positions/R0_READOUT.json` |
| R1 readout being reproduced | `<share>/R1_READOUT.json` |
| share | `/mnt/c/carc-shared/evloss_autopsy_20260824` (`/mnt/carc-shared/...` from any box) |
| expected | n = 800 positions · 498 games · legs leaf 323 / sib2 800 / sib3 800 / sib4 715 / rnd 200 |

Records are admitted **iff `ok is True` and `crn_verified is True`** — the identical filter
`05_analyze_r1.py:load_leg` applies. The D-L1 quarantine is laptop-side and never enters
this path: the banked corpus is the clean post-D-L1 rebuild that R1 was read from, and the
n/leg reconciliation below is what proves it.

---

## 2. Estimator — binding, copied from R1, not re-derived

`hajek`, `cluster_sandwich`, `cluster_bootstrap` and `wsd` are **copied verbatim** from
`scratchpad/evloss_autopsy/run/05_analyze_r1.py` into `r2_estimator.py` with attribution.
Weights are `ht_weight = 1/π_s`; the cluster is `game_id` (= `deck_seed`). Per position:

```
D_arm       = record["delta"]  = V*(arm) − V*(played)
R_champ_i   = max(0, D_leaf, D_sib2, D_sib3, D_sib4)      # PLAN.md §1, arms-only argmax
G_search_i  = R_leaf_i − R_champ_i = −D_leaf_i            # identity, see below
```

**`G_search = −D_leaf` is an identity, not an approximation.** With
`M = max(0, D_leaf, D_sib2, D_sib3, D_sib4)` and a common baseline `V*(played)`:
`R_leaf = V*(a_orc) − V*(leaf) = (V*(played)+M) − (V*(played)+D_leaf) = M − D_leaf`, hence
`G_search = (M − D_leaf) − M = −D_leaf`. Per A6 a **missing `leaf` leg means the depth-0
leaf argmax equalled the played action**, so `D_leaf ≡ 0` and `G_search ≡ 0` there — the
same convention `05_analyze_r1.py` uses in the `R_champ` max.

**Per category b, reported:** `n`, `Σw`, `n_games`, `R̄_champ` (Hájek), cluster-robust se,
`z` vs **0** and `z` vs the pre-registered **+0.5 pt bar**, 95 % sandwich CI, `UB95`,
`Ḡ_search` with its cluster-robust se and z, the ⭐-cell flag, and the bucket-vs-complement
contrast with its cluster-robust z.

**The +0.5 bar** is PLAN.md §7's `B-CEILING` bar and `everyply`'s own named re-open bar
(*"a mechanism argument that predicts a per-ply effect ≥ ~0.5 pts"*). `z_vs_0.5 =
(R̄_champ − 0.5)/se`. It is the R2 primary because the pooled read already cleared it at
z 20.8 — a bucket that only clears **0** is not news.

---

## 3. The pre-registered bucket family

PLAN.md §5's axis table, taken literally, using its own ⚠️-corrected **real field names**
(`stratum` is the uppercase disjoint cell; `move_kind_{best,played}` and
`contested_{best,played}` are two-arm constructs; arm B is pinned = `sib2` per A7). See
D-R2-1 for the K-count bookkeeping.

| # | axis | partition? | buckets |
|---|---|---|---|
| 1 | `structure` (field `stratum`) | **yes**, over all 800 | `DEG` `FARM` `CLOISTER` `CITY` `ROAD` `NEUTRAL` |
| 2 | `decision_type` | **yes**, over all 800 | `tile` `meeple` |
| 3 | `phase_third` | **yes**, over all 800 | `opening` `middle` `endgame` |
| 4 | `move_kind` (field `move_kind_played`) | yes, over the **meeple** subset | `farm` `cloister` `city` `road` `pass` |
| 5 | `commit_direction` | **no** — PLAN names only 2 of the 4 realized values | `spend` `hold` |
| 6 | contest shape | **no** — 6 overlapping indicators | `contested_best` `contested_played` `reinforce_losing_contest_best` `reinforce_losing_contest_played` `tie_force_join_best` `tie_force_join_played` |
| 7 | F7 `cross_world_spread` | **yes**, over the 800 (median split) | `low` (≤ median) `high` (> median) |

**26 pre-registered buckets.** The F7 median cut is taken on the 800 scored positions'
`cross_world_spread` — a covariate-only operation, computed by the classifier, never a
function of any judged value.

⚠️ **`commit_direction = spend` is PRE-DECLARED WEAK** (PLAN.md §5, SCOPE §6) and **cannot
fund a term at any z**. It is reported with that label attached and is excluded from the
funnel gate by construction.

---

## 4. The owner's exploit categories (H2 / H4)

Pre-registered in `measurement/e4_owner_exploit_hypotheses_20260825.md` (recorded
verbatim-faithful from the owner **before** any grading), read out on the E4 corpus by
`measurement/e4_exploit_grading_20260825/` Stage A: **H2 CONFIRMED** (deliberate invasions
owner 90 vs champion 7, p = 0.0002; all 133 contests arose *by merge*), **H4 CONFIRMED and
outcome-linked** (late farm captures 15 vs 2, p = 0.0012), and **H2+H4 are one mechanism**
(40/95 invasions are farm invasions).

SCOPE §6 pre-authorizes exactly this move: *"Named-but-not-in-the-list hypotheses (farm
timing, feature abandonment, opponent-blocking) are expressible as **conjunctions of the
above** and are declared as such … before the run."* H2 is opponent-blocking; H4 is farm
timing. They are declared here as conjunctions of the §3 covariates — **not** as new
mechanical features (see D-R2-3 for why the Stage-B ply predicates cannot be ported).

The mechanical anchor is `autopsy_extract._tile_touch`'s two tested majority flags:

- **F2 `tie_force_join`** — *"the placement NEWLY CONNECTS into a structure where the
  opponent holds SOLE majority — the late majority-steal move class."* That is the
  claim-a-stub-then-connect **merge invasion**, i.e. H2's mechanism, in code.
- **F9 `reinforce_losing_contest`** — the mover adds to a structure whose majority it is
  losing or tied on: the victim/waste side of the same contest.

| category | predicate (all fields from the `taxonomy` block) | H |
|---|---|---|
| `H2_STEAL_AVAILABLE` | `tie_force_join_best` | H2 (a/c) — a majority-steal join is on the table among the champion's own top alternatives |
| `H2_STEAL_TAKEN` | `tie_force_join_played` | H2 — the champion took it |
| `H2_STEAL_FOREGONE` | `tie_force_join_best and not tie_force_join_played` | ⭐ H2 (c) — steal available, champion declined. The direct form of *"neither defends NOR takes invasions"* |
| `H2_REINFORCE_LOSING` | `reinforce_losing_contest_played` | H2 (b) — the champion pours into a contest it is losing/tied on |
| `H4_LATE_FARM` | `phase_third == "endgame"` **and** farm-engaged | H4 — late farm decision |
| `H4_DECISIVE_FARM` | `H4_LATE_FARM` **and** `farm_share >= 0.5` | ⭐ H4 — late farm decision **where the farm term dominates the leaf differential** ("this farm decides the game") |
| `H2xH4_FARM_STEAL` | `tie_force_join_best` **and** `"farm" in contested_best` | ⭐ the shared mechanism: the steal is mostly a farm steal |

where **farm-engaged** ≡ `stratum == "FARM"` or `structure == "farm"` or
`move_kind_best == "farm"` or `move_kind_played == "farm"` or `"farm" in contested_best`
or `"farm" in contested_played`.

**`farm_share ≥ 0.5`** is the pre-registered "decisive" cut: `farm_share =
|farm_leaf_diff| / |total_leaf_diff|` (`autopsy_extract`, `None` on degenerate plies), so
≥ 0.5 means *the farm term alone accounts for at least half of the production leaf's entire
preference between the two arms*. `None` ⇒ not in the category.

⚠️ **Approximation, stated before the run:** `tie_force_join` and
`reinforce_losing_contest` are **scalar** flags — `autopsy_extract` does not emit them per
feature kind (only `contest_detail`, which does not ride in the side file). So
`H2xH4_FARM_STEAL` conjoins a scalar steal flag with a per-kind contested set and can
therefore admit a ply whose steal was on a city while a *different* touched region was a
contested farm. It is reported as an **indicative** category, not a clean intersection.

**7 exploit categories**, overlapping with each other and with §3. Family total for
multiplicity: **33**.

---

## 5. Controls (SCOPE §6 — all four, pre-stated)

1. **Structural.** `G_search` cancels winner's curse, strategy fusion and arm dispersion.
   It is the x-axis of the §4 read table and is reported for every category.
2. **`R_rnd`.** Already read at R1 (gate passed, paired z 5.34). R2 re-reports it per
   category on the n = 200 subset **as a diagnostic only** — the subset is too thin for a
   per-category verdict and is labelled as such.
3. **Label-permutation null**, 10,000 reps, statistic `max_b |z_b|` over the whole family.
   See D-R2-2: the prereg's *within-game* permutation is near-degenerate at cap 2/game, so
   the primary null is a **game-block** permutation and the within-game variant is reported
   beside it.
4. **Multiplicity + clustering.** Holm across the family of 33 on the primary
   (`z_vs_0.5`, two-sided α = 0.05); cluster-robust on **game**, never ply. A naive-sd z is
   not reported at all (the `e4_autopsy` owner ruling).
   ⚠️ A bucket with **`n_games < 2`** has no cluster-robust SE (`cluster_sandwich` returns
   `NaN` below 2 clusters) and is excluded from the Holm family and the permutation family
   — a mechanical, **outcome-blind** criterion (`n`/`n_games` are fixed by the classifier
   before any judged value is read). The excluded set is reported with counts and reasons;
   every such bucket still appears in the per-category table. See D-R2-6.

---

## 6. Reconciliation (MANDATORY, fails loudly)

1. **Pooled identity.** The R2 loader + estimator must reproduce R1's
   `R_champ.mean_hajek = 1.4928485121941815`, `se = 0.07179985263453552`, n = 800,
   n_games = 498 and the five per-leg counts to `1e-12`. A mismatch is a loader defect and
   the run **stops**; nothing downstream is read.
2. **Partition recombination.** For each partition axis (1, 2, 3, 7, and axis 4 within the
   meeple subset), `Σ_b W_b·μ_b / Σ_b W_b` must equal the pooled Hájek mean to `1e-9`.
3. **Coverage.** Every one of the 800 positions must carry a label on every partition axis;
   the count of positions carrying **0** exploit labels and the multi-label histogram are
   reported, not swept.

---

## 7. ⭐ THE FUNNEL GATE — pre-stated, evaluated in this order

SCOPE §8 *"FUNDS a term attempt (all four required, conjunctively)"*, evaluated per
category:

| # | condition | computable from the banked corpus? |
|---|---|---|
| **F1** | the category lands in the ⭐ cell of SCOPE §4 — `R̄_champ` significantly > 0 **and** `Ḡ_search` **not** significantly > 0 (`z_G < 2.0`) | ✅ |
| **F2** | clears **Holm-adjusted 2σ** on the cluster-robust (game) SE, on the primary | ✅ |
| **F3** | the family's `max_b |z_b|` beats the **label-permutation null** at p < 0.05 | ✅ |
| **F4** | `tier1-greedy` (out-of-family) agrees on **sign**, and the category has a **leaf-computable predicate** | ❌ **sign check** — no out-of-family judge leg exists in the banked corpus (PLAN.md §6: it is python-only by construction and was never run). ✅ predicate check |

**Verdict vocabulary, first match wins:**

- **`FUNNEL-CLOSED`** — no category satisfies F1∧F2∧F3. Deliverable is the **map of
  bounds** (per-category `UB95` on `R̄_champ`, HT-reweighted to the ply population), which
  is what sizes every future term proposal.
- **`FUNNEL-OPEN-PENDING-SIGN`** — ≥ 1 category satisfies F1∧F2∧F3 and has a
  leaf-computable predicate. This is the **strongest verdict the banked corpus can
  support**; F4's sign check is owed before a term dollar is spent, and the named cost is
  one python-only `tier1-greedy` judge leg over the same rids.
- **`FUNNEL-BLOCKED`** — F3 fails family-wide (the permutation null is not beaten): the
  taxonomy as a whole is indistinguishable from a random taxonomy of the same shape, and
  **no** category may be read, whatever its own z.

**Stage-1 screen feasibility** (the roadmap's *leaf-reweight screening funnel*, gate 1
opened 2026-08-26 by R1's `B-CEILING`) is reported beside the verdict, because the R2
judged corpus **is** that funnel's instrument: the count of positions carrying ≥ 2
CRN-paired scored arms with stored per-world oracle values, and a **pre-registered
game-level 50/50 holdout split** (seed `20260826`, emitted as
`funnel_holdout_split.json`) so that the eventual brute-force weight grid has a holdout
that predates it. The split is a function of `game_id` only — never of any judged value.

---

## 8. What R2 does NOT license, in any verdict

Nothing about absolute or superhuman strength; nothing about either structural blocker; no
deployment change; **no bucket-gated deployment ever**. A category finding may license a
*globally-active leaf-term hypothesis*, measured globally at an n = 800 deck-paired
deploy-budget cell. And the reach ceiling still multiplies into every number here: a
static leaf term reaches at most **62.2 %** of the oracle spread, and 30 % of pools are
fully indistinguishable (`tiletie_mining_20260814`).
