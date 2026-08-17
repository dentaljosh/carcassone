# TERMINAL-GROUNDED TIE ARBITRATION — DESIGN (Stage 1b, the funded successor)

> **STATUS AT WRITING: DESIGN, COMMITTED BEFORE ANY ARBITRATION, HEADROOM OR
> PRICING NUMBER EXISTS ANYWHERE ON THE SUCCESSOR CORPUS.**
> [READ_RULE.md](READ_RULE.md) is committed in the **same commit** as this file,
> and both are committed **before** the instrument (`scripts/tiletie/analyze_tiearb2.py`),
> before the cost pilot, and before one position of the fresh corpus is scored by
> either judge. Only **corpus substrate** precedes this commit — 850 fresh
> champion self-play games (`run_gen.sh`, launched 2026-08-16 15:45 EDT,
> commit `fccd8cb5`) and the mining that turns them into tied-tile-ply roots.
> The funding brief explicitly permits mining ahead of the read-rule commit,
> restricted to **selection metadata only** (tie tags, strata covariates). Git
> history proves the ordering and every run manifest carries this commit's hash.
> **0 strength games. No band. No `experiments/results.csv` row. No claim id.**
> `governance/PRODUCTION.yaml` and `governance/BAND_REGISTRY.csv` are untouched
> on **every** branch.

---

## 0.A — PRE-RUN AMENDMENT, applied BEFORE the pilot and BEFORE any position is scored

⚠️ **Nothing here is a result. No arbitration, headroom or pricing number exists,
for either judge, on either corpus, at the time of this amendment.** One
implementation fact was found while wiring the launch. It changes *how the run is
laid out on disk*; it touches **no estimator, no statistic, no threshold, no bar and
no branch**. [READ_RULE.md](READ_RULE.md) is **untouched**. (This is the Stage-1
§0 precedent, applied in the same way and for the same reason.)

- **0.A.1 — the CRN salt stays `tiletie-v1`; §4.5's `tiearb2-v1` is withdrawn.**
  `WORLD_SEED_SALT = "tiletie-v1"` is a **hardcoded module constant** in
  `scripts/tiletie/run_tiletie.py` (L102), injected into every leg command — it is
  **not** a CLI flag. Exposing it would mean editing a shared script while runs are
  live, which the worktree-isolation rule forbids (spawn respawns and each new
  `--shared-claim` cell re-import from disk).
  **This costs nothing, because world freshness was never carried by the salt.**
  `world_seed(rid, j, salt) = sha256("world" | rid | j | salt)` is keyed on the
  **`rid`**, and this corpus's rids (`tt_sp_281000000xx_p<ply>`) cannot collide
  with the spent corpus's (`tt_sp_280000000xx_p<ply>`) — the deck-seed bands are
  disjoint by construction (§4.2) and `G-DISJOINT` proves it at three levels
  (§4.4). ⇒ **every world of the fresh corpus is an independent draw regardless of
  the salt**, and §4.5's fresh salt was belt-and-braces only.
  **Two consequences, both benign:** (i) the pilot's `G-REPRO` control and the main
  run now share one salt, so there is no salt juggling and no chance of a
  cross-salt mix-up; (ii) `M = 32` and the prefix-stability property (§5.2) are
  unaffected — they are properties of the seed *function*, not of the salt value.

---

## 0. Owner authorization

2026-08-16, verbatim:

> **"fund. both boxes. laptop w22, local w14 for now, but make it easy to bump to
> w30 later. get an agent on it"**

⇒ Both boxes are funded for this run. Per-box worker counts live in exactly one
place, [WORKERS.conf](WORKERS.conf), sourced by every launcher in this directory;
`W_LOCAL=14` is the value the owner named as bumpable to **30**, and bumping it is
a one-line edit with no script surgery. No launcher hard-codes a worker count.

---

## 1. What this is, and what Stage 1 left standing

[../tiearb_20260816/](../tiearb_20260816/READOUT.md) fired pre-registered branch
**`P-PARTIAL`**. It is the **only route on the tile-tie axis that has ever cleared
the mechanism bar**: pooled n=733, `arb = +0.2065` pts/tied ply (z **+3.75**),
`F = 0.811` CI [0.450, 1.320], `F_fixed = 0.737` CI [0.347, 1.125] — graded at the
identical bar and in the identical currency that `E-FLAT` (0.00/0.18/0.18) and
`W-FLAT` (0.11/0.26/0.09/0.09/0.30) failed. Its §4.5 sign check **CORROBORATED**
(55.7%, p 0.0091), a first in this chain.

**One conjunct failed: `C_h`, the blind never-opened holdout** —
`arb_holdout = −0.0051` (z −0.05) against `arb_dev = +0.2920` (z +4.43).
Nothing was licensed; no Stage-2 was funded. The holdout is **spent**, the
read-rule is **spent**, and the 733-position corpus is **burned**.

The recorded re-open bar (READOUT §11, [LEVER_INDEX](../../docs/LEVER_INDEX.md)
row 217) names four requirements. **This design delivers all four**, and §3 states
which section answers which.

⚠️ **This is still Stage 1 — offline, 0 strength games.** A pass licenses exactly
one *Stage-2 game-cell pre-registration*, nothing more (READ_RULE §4).

---

## 2. The mechanism — unchanged, and cited rather than re-argued

> **HYPOTHESIS (verbatim from Stage 1 §2).** At a leaf-tied tile ply, break the tie
> by **CRN-paired playouts to terminal** — arbitration policy `tier1-greedy`
> (`carcassonne_ai.rule_based_player.RuleBasedPlayer`, 1-ply argmax, the v1 object
> leaf `virtual_score_inplace`, no search), one full continuation per
> (arm × determinization), **selected by cross-fit argmax over the world-mean of
> the terminal margin**.

The mechanism argument (every instrument that *sees* the +0.252 headroom prices arms
by continuation to **terminal**; the champion's fair-PIMC estimator never touches
terminal information, scoring every node with the curve125 static leaf at a
**truncated frontier**; E-FLAT and W-FLAT both showed that more compute converges
the *same* frontier ordering) and the kill-table showing why `E-FLAT`, `W-FLAT`, the
two static menus + the 38% reach bound, `CL-065`/`CL-073`, `CL-076` and `CL-078` do
not bind, are **inherited verbatim** from
[../tiearb_20260816/DESIGN.md §2.1–§2.2](../tiearb_20260816/DESIGN.md). They are not
re-argued here and they are not re-litigated by this run.

⭐ **The mechanism is not on trial again in the abstract — Stage 1 already convicted
it at z +3.75 on 733 positions. What is on trial is (i) whether that survives on a
corpus no programme has ever touched, at an `n` that can actually resolve the bar,
and (ii) whether any *deployable* shape of it retains the capture.**

### 2.1 One consequence of the mechanism that constrains §7 (stated up front)

The named mechanism *is* terminal grounding. ⇒ **Truncating the playout is not a
cheaper version of this arbiter — it is a different arbiter, and it is one that sits
back on the killed axis.** A truncated continuation scores at a frontier, which is
the single property `E-FLAT`, `W-FLAT` and both static menus share. (It is also a
*biased* estimator, not merely a noisier one: `state.scores` mid-game excludes every
unclosed city, road and farm.) **This design therefore does NOT truncate playouts**,
and §7 buys deployability on the axis that leaves the estimand intact — **how many
worlds the arbitration argmax sees**.

---

## 3. The four re-open requirements, and where each is answered

| # | Recorded re-open requirement | Answered in |
|---|---|---|
| **(a)** | a NEW corpus at n ≈ 924+ | **§4** — 850 fresh self-play games ⇒ a root-disjoint corpus, target **1,400** positions, floor **1,040**; §6 the power arithmetic |
| **(b)** | a fresh read-rule | **[READ_RULE.md](READ_RULE.md)** — new branch table (6 branches incl. two cheap-arm branches), new bars where new, committed with this file |
| **(c)** | an argument handling the dev/holdout discrepancy | **§5.4** — the published decomposition, and the *three structural* fixes: symmetric stratified split, an informativeness guard, and a baseline-drift gate input |
| **(d)** | an answer to the cost question | **§7** — a pre-registered cheapened arm on the world-budget axis, costing **zero extra compute**, with its own named branches |

---

## 4. The corpus — fresh, and disjoint at three levels

### 4.1 Why the old corpus cannot be topped up

The 733-position corpus is **root-exhausted**, not merely spent. Its self-play
stratum drew from the CL-070 root bank (495 `TILES` roots, **all consumed**) and
from `measurement/champ_action_logs/champ_games.jsonl` (**449 games**, of which 432
contributed). Those 449 games still hold ~30,132 uncensused eligible tile plies —
but **every one of them belongs to a game that is already a `root_id` in the spent
corpus** (`root_id = sp_<deck_seed>`, i.e. the game *is* the cluster). Topping up
from them would buy positions and no new roots, which is precisely what the re-open
bar forbids ("a NEW corpus (**new roots**, fresh CRN worlds)"). The only remaining
un-mined supply is 320 E4 positions across 26 root clusters, 24 of which already
contributed — root-contaminated, and python-backend at ~6.5× the unit cost.

⇒ **Fresh champion self-play games are required.** The funding brief authorizes
this explicitly; §11 prices it.

### 4.2 Generation — matched verbatim, only the seed band differs

850 games via `scripts/distill_flywheel/gen_fair_distill.py`, configuration matched
**verbatim** to the spent corpus's own provenance
(`measurement/champ_action_logs/CORPUS_MANIFEST.json`) so the fresh roots are drawn
from the **same position distribution**:

| knob | value | why it is not a choice |
|---|---|---|
| agent | `FairHeuristicPriorAgent` (PRODUCTION.yaml champion, fair PIMC) | matches the spent corpus |
| budget | `k_dets 4 × sims 688 = 2752` | matches the spent corpus (PRODUCTION.yaml `fair_deploy`) |
| exact endgame | `True`, `exact_max_k 2` | matches |
| leaf | `v2_9_2_Bmild_cap8_curve125`, runtime frozen-config-hash **`6dfffd57051690f2`** | matches; verified in the launch log on **both** boxes |
| rules profile | **`walled`** | matches the spent corpus's self-play stratum ⇒ same rules epoch ⇒ the `F_fixed` currency is preserved, **and** the rust pricing backend is available (it cannot mirror `fixed_v1`) |
| deck-seed band | **28100000000 .. 28100000849** | the *only* difference. Spent band 28000000000..28000000449; orphan `_b` leg 28000010000+. ⇒ **root-disjoint by construction** |

⚠️ **Declared scope narrowing vs Stage 1: this corpus is 100% `walled` self-play —
the E4 stratum is dropped.** Consequences, both stated before the run:
*(cost against)* the per-stratum and per-profile cuts no longer exist, and the
decision-relevant E4 distribution is not represented;
*(benefit)* the **rules-epoch confound** that pricing §6.6 and Stage 1 §7.5 both
carried as an unremovable threat (94% `walled` self-play vs 6% `fixed_v1` E4)
is **removed** — this corpus is a single stratum, single profile, single rules
epoch. Comparability with Stage 1 is barely affected: Stage 1's `walled` cut read
`arb +0.2043` / `F_fixed 0.729` against its pooled `+0.2065` / `0.737`.

### 4.3 Mining, and the sampler

`collect_action_logs.py --verify 10` → `run_census.py` (`--max-per-game 4`,
`--sample-seed 20260816`, target 4 × realized games) → `transposition_census.py`
→ `champ_picks.py` (the champion arm, a fresh k8×1376 rust search per position) →
`build_positions.py --cap-j 4 --exclude-rids <the 733>`. Exact commands in
[CORPUS_PIPELINE.md](CORPUS_PIPELINE.md).

`--max-per-game 4` **matches Stage 1's sampler exactly**, which keeps
positions-per-root at ≈1.84 and therefore keeps the measured cluster design effect
(§6) transferable. Selection criterion, dedupe rule, arm construction, the `J = 4`
cap and its seeded draw, and `champ_arm_index` are all `build_positions.py`'s own,
**unmodified** — this corpus is built by the same instrument that built the spent one.

Expected yield, from the spent corpus's own measured funnel (exact-tie rate 65.98%,
≤12-way qualifying 54.7%, **deduped scoreable supply 40.4%** of censused tile
plies): 850 games × 4 plies = 3,400 censused ⇒ **≈ 1,400 deduped supply**. Target
build **1,400**, or all supply if less. §6 sets the floor at 1,040 and §11 states
what happens if supply undershoots.

⚠️ A fresh corpus computes its **own** `scale_all` zero add-back factors — they are
a property of *this* corpus's tie-set construction (the analytic-zero population
share), **not** population constants. The build ships its own
`DROPPED_ALL_TRANSPOSITION.json` and `POSITIONS_PLAN.json`.

### 4.4 `G-DISJOINT` — disjointness proved at three levels, not asserted

`scripts/tiletie/gate_disjoint.py`, a **pre-launch abort**: if any intersection is
non-empty the corpus is not scored and the read-out is a harness report.

| layer | identity | spent-side source |
|---|---|---|
| 1 | **`root_id`** (the cluster unit) | the 399 roots in `tiletie_pricing_20260812/positions_pooled/ARMS.json` |
| 2 | **`rid`** (`tt_sp_<deck_seed>_p<ply>`) | the 733 keys of the same `ARMS.json`, also fed to `build_positions.py --exclude-rids` (expect `n_removed_from_supply == 0`, which is itself a witness of layer 1) |
| 3 | **position digest** `sha256(checksum)`, `checksum = game.string_representation(board)` | the `checksum` field of `positions_pooled/positions_*_leg1.jsonl` (733 lines) |

Layer 3 is the strongest and is the one the funding brief names: it catches the
**same board reached from a different game and ply**, which layers 1–2 cannot.
Counts only are recorded, in `DISJOINTNESS.json`; no value is read.

### 4.5 CRN worlds

`world_seeds[j] = sha256("world"|rid|j|salt)`, `playout_seeds[j] = sha256("playout"|rid|j|salt)`
— keyed on `rid` and the salt, never on the arms and never on the judge.

- **Salt: `tiletie-v1`** — ⚠️ **amended by §0.A.1**; the originally-written
  `tiearb2-v1` is withdrawn because the salt is a hardcoded constant in
  `run_tiletie.py` and exposing it would mean editing a shared script while runs are
  live. **The rids are new, so the worlds are fresh under any salt** — freshness is
  carried by the `rid`, not by the salt — so this costs nothing.
- **`M = 32`, and it must NOT be raised** — the OOF §3.2 argument, inherited: the
  cross-fit selects on M/2 and evaluates on M/2, so a larger M makes the selection
  less noisy and the estimand **larger**. Locked at 32 by comparability with Stage 1
  and with the ladders, not by cost.
- The pilot's `G-REPRO` control (§10) runs on **spent-corpus** positions, whose
  bit-reproduction against the adjudicated OOF records is the whole point of it.
  Under §0.A.1 it shares the run's salt, so there is **one salt for everything** and
  no cross-salt mix-up is possible.

---

## 5. Statistics

Notation: `V^IF[p,a,j]` and `V^ARB[p,a,j]` are terminal margins in final-score
points at the root player's seat, position `p`, arm `a`, CRN world `j = 1…32`,
under `clair-puct` (100-sim clairvoyant PUCT, played to terminal on a known deck)
and `tier1-greedy` respectively. `arm_order = [0] + scored_legs`; `champ` is the
corpus's own `ARMS.json::champ_arm_index`; positions whose champion arm is not in
the scored set are dropped, counted and reported.

### 5.1 The estimator — unchanged from Stage 1

Parity halves from `analyze_tiletie.parity_indices(32, base=1)` and its swap. For
each fold `(sel, eva)`:

```
a_arb   = argmax_a  mean_{j ∈ sel} V^ARB[p, a, j]      # ARBITRATION (tier1-greedy)
arb[p]  = mean_{j ∈ eva} V^IF[p, a_arb, j]
        − mean_{j ∈ eva} V^IF[p, champ, j]             # PRICING     (clair-puct)

a_ora   = argmax_a  mean_{j ∈ sel} V^IF [p, a, j]
ora[p]  = mean_{j ∈ eva} V^IF[p, a_ora, j]
        − mean_{j ∈ eva} V^IF[p, champ, j]             # THE HEADROOM
```

Both symmetrized over the two folds; every position scaled by its stratum's
`scale_all`; the `discriminable` (unscaled) reading reported alongside.

⭐ **Non-circularity is structural, not asserted**: the arm is chosen by
`tier1-greedy` on the **selection** worlds and priced by `clair-puct` on the
**disjoint evaluation** worlds — selection and evaluation share neither the judge
nor the world. The arbitration policy is never the pricing judge; the greedy-judge
pricing (`SEC-ARB`) is **audit-only and circular by construction** and is never a
branch input.

### 5.2 The two arbiter arms — and why the second one is free

⭐ **The world seeds are prefix-stable in `M`**: `world_seed(rid, j, salt)` is a
function of `(rid, j, salt)` alone — `M` never enters, and the per-world loop is
stateless across `j` (a fresh `random.Random` and a fresh continuation agent per
world). Therefore *any prefix of the 32 worlds is bit-identical to the same prefix
of the full run*, and **an arbiter that sees fewer worlds is a sub-read of records
this run already pays for**. The cheap arm costs **zero extra compute**.

Define the **selection budget `B`** = the number of CRN worlds the arbitration
argmax sees. For a fold whose selection half is `sel` (16 indices, ascending), the
budget-`B` arbiter selects on `sel[:B]` and is priced, as always, on the **full
16-world evaluation half**. Cross-fit disjointness is preserved exactly.

| arm | budget | role |
|---|---|---|
| **`H` — honest** | `B = 16` (the whole selection half) | **Stage 1's arm**, re-measured on a fresh corpus. The primary. |
| **`C` — cheap** | `B = B*`, frozen by the §7 cost rule | the deployability arm. Its own branches in READ_RULE §4. |
| ladder | `B ∈ {1, 2, 4, 8, 16}` | **reported in full** (capture × cost curve, free). ⛔ **Never a branch input except at `B*`.** |

⚠️ **`B*` is fixed by a mechanical, COST-ONLY rule (§7.2) and is written to
`PILOT.json` before any arbitration statistic on the fresh corpus exists.** The
ladder cannot be shopped: the branch reads at `B*` and at `B=16`, both named in
advance.

⚠️ Note that a *deployed* Stage-1-shaped arbiter costs `Ā × 16` playouts per tied
ply, not `Ā × 32`. Stage 1 §2.3 quoted `Ā × 32` because the measurement computes
both parity folds in order to symmetrize; that second fold is a **measurement
device, not a deployment cost**. This design prices deployment at `Ā × B`.

### 5.3 The primary statistics

```
F(x)        =  mean_p arb_x[p]  /  mean_p ora[p]      # PRIMARY captured fraction
F_fixed(x)  =  mean_p arb_x[p]  /  0.2803             # cross-programme currency
z(x)        =  mean_p arb_x[p]  /  se_cluster         # cluster-robust on root_id
```

for each arm `x ∈ {H, C}`. `F`'s 95% CI comes from the **root bootstrap** (20,000
reps, seed **20260816**, resampling roots with replacement and recomputing numerator
*and* denominator inside each rep); the fraction of reps whose denominator crossed 0
is reported as **`G-BOOT`**.

**The bars are `0.35` (ratio) and `+2.0` (z) — they are NOT new constants.** They
are `E-FLAT`'s and `W-FLAT`'s own committed fund bar, verbatim, and Stage 1's.
`0.2803` is the fixed published *honest base-rung regret* both ladders were graded
against.

⚠️ **Declared caveat on `F_fixed`, new to this run:** `0.2803` was measured on the
*spent* corpus's 522-position dev slice. This corpus is fresh, so `F_fixed` is now a
**cross-corpus** ratio. Both corpora are the same population (walled champion
self-play, same generation config, same sampler, same builder), so the comparison is
legitimate — but `F` (numerator and denominator on the *same* fresh positions under
the *same* judge) is the internally-consistent statistic, and `RBAR` continues to
require **both** ≥ 0.35, exactly as Stage 1 did. **No bar is loosened anywhere in
this design.**

### 5.4 ⭐ The split — re-open requirement (c), answered structurally

**What actually happened in Stage 1** — a decomposition of its *published* numbers
([STAGE1_SLICE_DECOMP.json](STAGE1_SLICE_DECOMP.json); post-hoc, adjudicates
nothing, re-labels nothing):

| statistic | dev (n=522) | holdout (n=211) | gap | se_gap | z |
|---|---|---|---|---|---|
| `ora` (headroom) | +0.3020 | +0.1370 | +0.1650 | 0.1343 | **1.23** |
| `arb` (capture) | +0.2920 | −0.0051 | +0.2971 | 0.1172 | **2.53** |
| **`rnd` (random-arm baseline)** | **+0.1296** | **−0.2682** | **+0.3978** | 0.1339 | **2.97** |
| **`arb − rnd`** (mechanism net of the level) | **+0.1624** | **+0.2630** | **−0.1007** | 0.1417 | **−0.71** |

⭐ **The random-arm control moved MORE across the two slices than the arbiter did,
and the mechanism net of that level is FLAT — nominally *higher* on the holdout.**
Under a root-level permutation null the observed `arb − rnd` gap sits at the
**0.561 absolute percentile**: indistinguishable from a random split. The headroom
gap itself is **not significant** (z 1.23).

⇒ **The Stage-1 failure was a shift in where the champion's own tie-break sits
relative to arm-average — a property of which positions landed in which slice — not
the arbiter failing to capture.** This is not a new excuse: Stage 1's DESIGN §7.3
**named this exact threat in advance** ("`arb` under an uninformative arbiter is
`mean-over-arms − champ`, not 0 … if `C-RND` is materially positive, part of `arb`
is not the mechanism"), computed it, printed it — and then took a branch that could
not see it. This design makes that named threat load-bearing.

Measured composition drift is a real but **partial** contributor: arm-count drifted
24.1 pp and phase 16.8 pp between the slices, and standardizing on the pooled
level-means explains **11%** (single covariate) to **29%** (the joint 12-cell
reweight) of the `arb` gap, **25–52%** of the `ora` gap. The drift itself is not
chance (root-permutation percentile 0.99–1.00).

**Three structural fixes, all pre-registered here:**

1. **A SYMMETRIC, STRATIFIED HALF-SPLIT — not a dev/holdout carve.** On a fresh
   corpus that no programme has shopped, with an estimator that has **zero free
   parameters** and was named a priori by a mechanism argument, there is nothing to
   hold out *from*: both halves are equally blind. So the honest form is a
   **50/50 split by root** (seed **20260816**), into slices **`S1`/`S2`** — which
   also roughly **doubles the power of the consistency check** relative to Stage 1's
   70/30 carve (each half ≈ 700 positions vs the spent holdout's 211).
   Roots are stratified before assignment, into **18 cells**:
   `phase_bucket (early/mid/late) × arm-count bucket ({2},{3},{4,5}) × champ_is_arm0 (T/F)`,
   with roots allocated alternately within each cell so cell counts are balanced to
   ±1 root. The first two axes are exactly the covariates measured to drive the
   Stage-1 drift; the third is a pre-scoring proxy for where the champion's pick
   sits in its tie set. Stage 1's carve was a **plain uniform shuffle over roots**
   with no stratification at all (`mine_oracle_sep.make_split`) — that is the defect
   being fixed. **Clustering is on `root_id`, so no game straddles the split.**

2. **AN INFORMATIVENESS GUARD — the thing Stage 1 lacked and paid for.** A slice
   whose *own* headroom is not resolved has nothing to capture, and a null on it is
   not evidence against the mechanism. Pre-registered:
   `INFORMATIVE(s) ≡ z(ora_s) ≥ +2.0`.
   A non-informative slice reads **UNINFORMATIVE**, never **FAIL**.
   ⚠️ **The guard is not free**: `C_split` additionally requires that **at least one
   slice be INFORMATIVE**, so a corpus where nothing is resolvable cannot pass. On
   the Stage-1 holdout this guard would have fired on its own terms
   (`z(ora_holdout) = +1.19`).

3. **A BASELINE-DRIFT GATE INPUT.** `rnd_s` is reported per slice on every branch,
   and `D_rnd = |rnd_S1 − rnd_S2|` is a named gate input with a pre-registered bar:
   `BASELINE_DRIFTED ≡ D_rnd ≥ 0.20` pts. Only when the baseline demonstrably
   drifted may a slice satisfy the consistency conjunct on the level-corrected
   statistic `arb_s − rnd_s` instead of `arb_s`. At se(`rnd_s`) ≈ 0.06 each, 0.20 pts
   is ≈2.35σ of the difference — it fires on a real drift, not on noise (Stage 1
   realized **0.3978**). The read-out must state explicitly whether the escape
   clause was used.

Formally (READ_RULE §4 carries this verbatim):

```
INFORMATIVE(s)   ≡ z(ora_s) ≥ +2.0
BASELINE_DRIFTED ≡ |rnd_S1 − rnd_S2| ≥ 0.20
C_split(x) ≡ (at least one slice is INFORMATIVE)
             ∧ ∀ INFORMATIVE s:  arb_s(x) ≥ 0
                                 ∨ ( BASELINE_DRIFTED ∧ (arb_s(x) − rnd_s) ≥ 0 )
```

⚠️ **Nothing above touches the primary conviction statistics.** `arb`, `z`, `F`,
`F_fixed` and their bars are Stage 1's, unchanged, at the identical numbers. Only
the *slice-consistency conjunct* is made robust to a level shift the prior design
had already named as a threat.

### 5.5 Mandatory companions — reported on every branch, never a branch input

| id | quantity |
|---|---|
| `C-RND` | the random-arm arbiter, `a_rnd` drawn by `Random(sha256(rid) ⊕ 20260816)` over `arm_order`, priced identically — the **null level**, per slice and pooled |
| `arb − rnd` | the mechanism net of that level, per arm, per slice and pooled |
| `C-ARM0` | the same statistic with **arm 0** (the leaf's tie-break of record) as comparator — the `headroom_leaf` currency |
| `SEC-ARB` ⚠️ **AUDIT-ONLY, CIRCULAR** | the arbiter's picks priced by `tier1-greedy` itself. **Its capture fraction against its own headroom is 1 BY CONSTRUCTION.** Reported in pts with its `z`, never a branch input |
| `PICKCHG` | fraction where `a_arb ≠ champ`, and where `a_arb = a_ora`; coverage (= 1.0 by construction) |
| **`AGREE_HC`** | **new** — the fraction of positions where the cheap arm and the honest arm select the **same** arm. The cheapest possible readout of how much the world budget matters |
| **B-ladder** | `arb`, `z`, `F`, `F_fixed`, `rho_wall` at `B ∈ {1,2,4,8,16}` — the capture × cost curve, free |
| sign check | §5.6 |
| bound chain | `pts_to_elo` with `TIED_TILE_PLIES_PER_GAME = 22.96`, `NON_ADDITIVITY = 3.2` and its `/5.23` low-end bracket, `σ_game` sensitivity, ×1.40 full-set extrapolation — applied **identically** to numerator and denominator so it **cancels out of `F`**. `NON_ADDITIVITY = 3.2` is **n = 1**, a ±1.6× bracket, not a point |

Per-phase, per-arm-count and capped/uncapped cuts are emitted beside the pooled read
and are **labelled underpowered. No branch is ever adjudicated on a cut.**

### 5.6 The sign check — the E4 autopsy's instrument, unchanged

`analyze_autopsy.py::sign_agreement` over the positions where the arbiter changes the
champion's pick in at least one fold: `agreement_rate`, exact two-sided binomial `p`,
aggregate sign, verdict in the committed taxonomy (CORROBORATES / PARTIAL / NO
CORROBORATION), printed beside the committed benchmarks (80% at p 0.0012 =
corroboration; 61.9% at p 0.38 = NOT) and beside the autopsy's own Tier-1 leg
(62.1% at p 2.8e-05, aggregate sign NEGATIVE ⇒ PARTIAL).
**Mandatory; never a branch input** (the OOF precedent: 57.1% at p 0.0547 = NO
CORROBORATION while the mean convicted at z +4.32). One consequence: if a passing
branch fires with NO CORROBORATION, the licensed Stage-2 prereg must carry that
verdict verbatim.

### 5.7 What is NOT computed

No new estimator of the headroom, no re-fit, no menu, no learned component of any
kind, no leaf change, no champion re-search beyond `champ_picks`, no re-read or
re-adjudication of any finished run. **Nothing in the spent 733-position corpus is
re-opened** except the pilot's `G-REPRO` bit-reproduction control, which reads only
a checksum count.

---

## 6. ⚠️ POWER — the arithmetic, done before pricing

**Anchors — all from Stage 1's realized read, none from this run:**

- realized per-position sd of `arb` (`scale_all`): **1.5819** pts pooled
- realized **cluster design effect** on `root_id`: **0.943** (se_cluster ÷ sd/√n).
  Across all 24 group × metric cells it spans **0.932–1.034** ⇒ clustering costs
  essentially nothing at 1.84 positions/root, which is why §4.3 keeps
  `--max-per-game 4`.

**The bar:** convict `F_fixed ≥ 0.35` at `z ≥ +2.0`.
`F_fixed = 0.35` ⇔ `arb = 0.35 × 0.2803 = 0.0981` pts ⇒ need `se_arb ≤ 0.0491`.

```
n  =  ( DEFF × 1.5819 / 0.0491 )²
      DEFF = 0.943 (realized)  ->  n =   925      <- the figure the READOUT recorded
      DEFF = 1.00  (assume clustering buys nothing) -> n = 1,040
```

⇒ **Pre-registered floor `G-N` = 1,040 analysed positions**, the conservative
figure. **Target build = 1,400.**

| n | 2σ resolution [pts] | in `F_fixed` units |
|---|---|---|
| 1,040 (the floor) | 0.0981 | **0.350** — exactly the bar |
| 1,350 | 0.0861 | **0.307** |
| 1,400 (target) | 0.0846 | **0.302** |
| 700 (one slice at the target) | 0.1196 | **0.427** |
| *(733 — Stage 1, for reference)* | *0.1101* | *0.393* |

⇒ **Unlike Stage 1, this design can resolve the bar it is graded at.** Stage 1's
pooled 2σ resolution was 0.393 in `F_fixed` units against a 0.35 bar; at n = 1,400
it is **0.302**, and each half-slice alone (0.427) resolves more than the spent
*whole corpus* did on the conjunct that failed.

**Expected reading if Stage 1's pooled central value is the truth**
(`F_fixed = 0.737`, `arb = 0.2066`): pooled `z ≈ 4.80`; a single slice `z ≈ 3.39`,
so `P(arb_s < 0) ≈ 0.0004`. ⇒ **`C_split` is a real check that will not fire on
noise** — which is exactly what Stage 1's n=211 conjunct could not promise.

⚠️ **What this design still cannot do:** it cannot resolve a capture in the
0.10–0.20 band, and a null here still does **not** exclude one. `F-FLAT2` is
written as a **funding verdict, not an exclusion**, in the same words `W-FLAT` used.

---

## 7. ⭐ COST — re-open requirement (d), answered

### 7.1 The currency, and its declared bias

```
rho_wall(B)  =  ( Ā × B × c_tier1 )  /  t_champ
```

- `Ā` — the fresh corpus's realized mean arm count (Stage 1: 3.0027), from the plan.
- `c_tier1` — measured worker-s per `tier1-greedy` playout (Stage 1: pilot 2.1236,
  realized 2.5197; OOF pilot 2.1783). Re-measured by this run's pilot.
- `t_champ = 13.7552` s/move — the champion at k8×1376 = 11,008 sims, **sequential,
  on this box** (PRODUCTION.yaml clock-legality block; `kparallel_latency_bench.py`,
  30 replayed real mid-game roots, quiet 5900XT).
- `B` — the selection budget (§5.2). A *deployed* arbiter pays `Ā × B` playouts per
  tied ply.

⚠️ **Declared bias, stated before the run: `rho_wall` OVERSTATES the deployable
cost, and is therefore conservative.** `c_tier1` is a **pure-python, v1-object-leaf**
continuation — the slowest path in the codebase — while `t_champ` is the
cython-accelerated production search. A rust continuation (the project ships
`carc_rs`) would move the numerator by a large factor that this design does **not**
estimate and does **not** claim. The bar is applied to the pessimistic number.

Also reported, never a branch input:
`rho_amortized = rho_wall × 22.96 / 72` — the added clock as a fraction of the
champion's own per-game clock (22.96 tied tile plies per game, ~72 champion moves);
and `rho_phone = Ā × B × c_tier1 / 1.551`, against the shipped phone champion, so
Stage 1's "100–200×" headline stays comparable.

### 7.2 The pre-registered cost rule that fixes `B*`

**Mechanical, cost-only, no owner call, no strength number:**

```
B*  =  max { B ∈ {1, 2, 4, 8, 16} : rho_wall(B) ≤ 1.20 }
       and  B* = 1  if no B qualifies.
DEPLOY  ≡  rho_wall(B*) ≤ 1.20
```

The `1.20` bar is **the N4 trigger currency**, the house budget-confound threshold,
applied at tied plies exactly as the funding brief specifies. `B*` is computed from
`Ā` (mining metadata, available before scoring) and `c_tier1` (the pilot, which
reads only wall-clock / `n_ok` / `crn_verified` / a checksum), and is **written to
`PILOT.json` before one position of the fresh corpus is scored**. It reads no
arbitration, headroom or pricing statistic.

**Advance arithmetic, so the read-out cannot be accused of fitting `B*`:** at
`Ā ≈ 3.0` and `c_tier1 ∈ [2.12, 2.52]`, `rho_wall(B) = (0.462 … 0.550) × B`, so

| B | `rho_wall` | ≤ 1.20? |
|---|---|---|
| 1 | 0.46 – 0.55 | ✅ |
| **2** | **0.92 – 1.10** | ✅ |
| 4 | 1.85 – 2.20 | ❌ |
| 8 | 3.70 – 4.40 | ❌ |
| 16 *(honest)* | 7.40 – 8.79 | ❌ |

⇒ **`B*` is expected to be 2**, under either end of the measured cost bracket. The
honest arm sits at ~7–9× the champion's per-move budget (and ~65–78× against the
phone, the shape of Stage 1's "100–200×" once the second parity fold is correctly
excluded as a measurement device).

### 7.3 What the cheap arm costs to measure: nothing

Because the world seeds are prefix-stable (§5.2), every rung of the ladder — `B*`
included — is a **re-read of records this run already pays for**. The cost answer is
bought for **0 extra worker-seconds**, which is why the ladder can be reported in
full without a multiplicity problem: the branch reads only at `B = 16` and `B = B*`,
both named before any number exists.

### 7.4 What the cost answer will and will not establish

A pass at `B*` establishes that **a budget-legal shape of the arbiter retains a
mechanism-sized capture on a fresh corpus, priced by an independent terminal-grounded
judge**. It does **not** establish deploy elo (§9.1), it does not license a deploy,
and it does not license a game outside the one Stage-2 prereg the READ_RULE names.

---

## 8. Instrument

- **Scoring**: `scripts/tiletie/run_tiletie.py --judges clair-puct tier1-greedy`,
  **unmodified**, driving `scripts/measurement_infra/oracle_score_pilot.py`,
  **unmodified** — the identical path Stage 1 and the OOF run used.
- **New code, additive only**: `scripts/tiletie/build_tiearb2_corpus.*` (the mining
  driver), `scripts/tiletie/gate_disjoint.py` (§4.4), `scripts/tiletie/split_tiearb2.py`
  (the §5.4 stratified carve), and `scripts/tiletie/analyze_tiearb2.py` (the join,
  the §5 statistics, the two arms, the B-ladder, and the READ_RULE adjudication).
  **No existing analyser is modified.** `analyze_tiletie.py`'s `parity_indices`,
  `cluster_robust`, `bootstrap_roots`, `zero_rates`, `pts_to_elo`, `crossfit_regret`,
  `aggregate`, `load_plan`, `discover_records` and `bound_block` are **imported and
  reused, not reimplemented**; `analyze_tiearb.py`'s `paired_ratio_bootstrap`,
  `sign_check`, `rnd_arm_position` and `binom_two_sided` likewise.
  Tests: `tests/test_tiearb2.py` and `tests/test_tiearb2_corpus.py`, with
  `tests/test_tiearb.py` (52 tests) kept green.

| knob | value | why it is not a choice |
|---|---|---|
| `--m` | **32** | §4.5 — raising it inflates the estimand |
| `--world-seed-salt` | **`tiletie-v1`** | §0.A.1 — a hardcoded constant in `run_tiletie.py`, not a flag; freshness is carried by the `rid`, not the salt |
| `--oracle-sims` | 100 (inert for `tier1-greedy`) | manifest comparability |
| `--backend` | `rust` for `clair-puct` (available: profile is `walled`), `python` for `tier1-greedy` | forced by the harness |
| arms / dedupe / cap `J = 4` / reference arm | as built by `build_positions.py` | the same builder that built the spent corpus |
| `--strict-crn` | **on** | a deck-hash mismatch fails the position loudly |
| `--workers` | [WORKERS.conf](WORKERS.conf) | throughput only; cannot move a value |
| `--parity-base` | **1**, symmetrized | Stage 1's convention |
| bootstrap | 20,000 reps, seed **20260816** | Stage 1's convention |

---

## 9. Integrity gates — mechanical, and they void the run

| id | check | consequence |
|---|---|---|
| `G-CRN` | every scored `tier1-greedy` leg's `world_seeds`/`playout_seeds` **bit-identical** to the `clair-puct` record for the same `rid`; `crn_verified` and `checksum_ok` true | **`U-UNREADABLE`** |
| `G-ARM` | `pick_a`/`pick_b` agree with `ARMS.json` for the leg, in **both** judges | `U-UNREADABLE` |
| `G-VA` | `values_a` bit-identical across all legs of a position, within each judge | `U-UNREADABLE` |
| `G-ARMSET` | the two judges' scored `arm_order` identical; differing positions excluded and counted (denominator = analysed + armset-mismatched); **>5% ⇒** `U-UNREADABLE` |
| `G-SPLIT` | `S1 ∪ S2` = the analysed corpus, `S1 ∩ S2 = ∅` at the **root** level; the 18 stratification cells balanced to ±1 root | `U-UNREADABLE` |
| `G-N` | **≥ 1,040** analysed pooled (§6), **and ≥ 400** in each slice | `U-UNREADABLE` |
| `G-DENOM` | `ora ≤ 0` **or** `z(ora) < +2.0` on the pooled read — no headroom to capture, `F` has no meaningful denominator | `U-UNREADABLE` |
| `G-BOOT` | fraction of bootstrap reps with denominator ≤ 0; **> 0.05 ⇒** `F` is void as a branch input for that arm, the ratio conjunct rests on `F_fixed` alone and the read-out says so | reported always |
| `G-DISJOINT` | §4.4, all three intersections empty | **pre-launch abort** |
| `G-LEAF` | `run_tiletie` preflight harness leaf hash `== a36d2e15a3b3d71d` | **pre-launch abort** |
| `G-REPRO` | the pilot's spent-corpus legs bit-reproduce the existing OOF/Stage-1 records (sha256 over `values_a`/`values_b`/`world_seeds`/`playout_seeds`); **count only** | **pre-launch abort** |
| `G-GEN` | `collect_action_logs --verify`: replayed games reproduce their recorded final scores; every deck seed in band 28100000000..28100000849 | **pre-launch abort** |

---

## 10. The cost pilot — and it reads NO strength number

⚠️ **The pilot fixes the launch shape, measures `c_tier1`, instantiates `B*`, and
proves the pipeline. Nothing else.** It reads **only**: wall-clock, `elapsed_secs`,
`n_ok`, `n_failed`, `crn_verified`, the world/playout-seed identity witness, and one
checksum count (`G-REPRO`). **It does not read `values_a`, `values_b`,
`per_world_delta`, `mean_a`, `mean_b`, `delta`, any sd, or any statistic derived
from them.**

- **Draw: the spent corpus's own OOF pilot rids** (`../tiletie_oof_20260814/PILOT_RIDS.json`),
  at the **old salt `tiletie-v1`** — already scored twice under the identical
  convention, so choosing them is not a draw at all and there is nothing to shop.
  They are burned for inference and therefore free for a plumbing check, exactly as
  the funding brief permits.
- **`G-REPRO`** — the re-scored legs must be **bit-identical** to the existing
  records. Only the count of matching legs is reported, never a value.
- **Pre-committed mechanical rule** (no owner call):
  1. `n_failed > 0`, or any `crn_verified` false, or any seed mismatch, or `G-REPRO`
     short of its expected count ⇒ **ABORT; the fresh corpus is not scored** and the
     read-out is a `U-UNREADABLE` harness report.
  2. Otherwise `c_tier1 = Σ elapsed_secs / playouts`, `B*` is computed by §7.2 and
     **written to `PILOT.json`**, and the main run launches.
- **Order:** the fresh corpus's rids are put in a **seeded permutation (seed
  20260816)**, written to `POSITION_ORDER.json` **before** launch, and cut into
  **4 sequential chunks** — because `load_positions_jsonl` sorts by `root_id`, a
  line-order prefix would be composition-biased. **Any number of completed chunks is
  a uniform random subsample**, so a partial run is still an unbiased read at its
  realized `n`.

---

## 11. Compute plan, boxes, and ETA

All figures are measured, from the sources named.

| phase | unit cost (measured) | total | box |
|---|---|---|---|
| **1. self-play generation** — 850 games | ~586 worker-s/game (`champ_action_logs/gen_local.log`: 124 games / 9,075 s at W8) | **138 worker-h** | **both**, `--shared-claim` work-stealing |
| 2. census | 0.0192 s/ply (`census/manifest.json`) | ~1 min | local |
| 3. transposition map | negligible | ~1 min | local |
| 4. `champ_picks` (k8×1376 rust) | **1.409** worker-s/position (measured over 932 records; the DESIGN budget of 13.755 was ~10× conservative) | **0.6 worker-h** | local |
| 5. `clair-puct` pricing (rust, `walled`) | 1.60 worker-s/playout × 128.2 playouts/position | **80 worker-h** | **local** (rust) |
| 6. `tier1-greedy` arbitration (python-only) | ~2.5 worker-s/playout × 128.2 | **125 worker-h** | **laptop** (python-only, so it needs no rust) + local overflow |
| | | **≈ 344 worker-h** | |

**ETA at the authorized worker counts (`W_LOCAL=14`, `W_LAPTOP=22` ⇒ 36 workers):**
phase 1 **≈ 3.8 h** (both boxes); phases 2–4 **≈ 15 min**; phases 5–6 run
**concurrently on the two boxes** — pricing 80 worker-h at W14 ≈ 5.7 h, arbitration
125 worker-h at W22 ≈ 5.7 h — so **≈ 5.7 h**. **Total ≈ 10 h wall**, an overnight
run, which the funding brief explicitly permits.
⚠️ At `W_LOCAL=30` (the owner's named bump) phases 5–6 rebalance to ≈ 4 h and the
total falls to ≈ 8 h. That bump is a **one-line edit to `WORKERS.conf`**.

**Analysis phases run on the LOCAL box only** — the laptop's `/mnt/c` resolves to
its own Windows drive and would silently read the wrong share
([CLUSTER_OPS](../../docs/CLUSTER_OPS.md)).

**If supply undershoots.** Realized deduped supply is measured at phase 2. If it is
below **1,100**, the pre-committed response is **mechanical: generate additional
games in the same band and re-run phases 2–4**, never to lower `G-N`. `G-N = 1,040`
is a floor on the *analysed* corpus and is not renegotiable, because it is the `n`
at which this design's 2σ resolution equals the bar it is graded at.

---

## 12. Threats — stated before the numbers

1. ⭐ **The arbiter and the pricing judge are both terminal-grounded.** They differ
   in policy (`RuleBasedPlayer` 1-ply argmax vs 100-sim clairvoyant PUCT) and are
   independent in the leaf, but they **share the property under test**. ⇒ **a
   positive here is evidence that terminal grounding at ties is worth points *as
   measured by a terminal-grounded ruler*, which is the estimand — it is NOT yet
   evidence of deploy elo.** This is why a pass licenses only a game-cell prereg,
   and why that prereg must be graded on games.
2. **Regression to the mean cuts toward the null.** Positions are selected on a
   *leaf* property; re-scoring by an independent instrument pushes measured spread
   toward 0. ⇒ **a positive read is conservative.**
3. **The arbiter's null level is not zero.** `C-RND` measures it directly, per slice
   and pooled, and `arb − rnd` is printed beside `arb` everywhere. §5.4 makes it a
   gate input for the *consistency* conjunct only; the primary estimand remains
   `arb`, as in Stage 1.
4. **A weak continuation is a different estimand, not a noisier one.** Greedy play
   may wash out deck-dependent tactics — which cuts **against** the mechanism, since
   the arbiter *is* the greedy continuation.
5. **Single stratum.** §4.2: the rules-epoch confound is removed, but the E4
   decision-relevant distribution is not represented, and no stratum cut exists.
6. **Chain-granularity on the TILE class** — inherited: the continuation picks the
   meeple, so neither arm gets the meeple its chain value assumed. Direction unknown.
7. **Cap `J = 4` and the ×1.40 full-set extrapolation** — inherited, applied
   identically to numerator and denominator, so they **cancel out of `F`**.
8. **`F_fixed` is now cross-corpus** — §5.3. `F` is the internally-consistent
   statistic and `RBAR` requires both.
9. **Fresh games share the *generation* config with the spent corpus but not its
   decks.** That is the point (root disjointness); it also means any deck-band
   over-dispersion (the CLAUDE.md cross-band 1.8–2.2× humility rule) applies to
   *comparisons between* this corpus and the spent one — i.e. to `F_fixed`, not to
   the within-corpus `F` or to the within-corpus slice contrast, which are the
   robust class.
10. **Contended box** — none expected (both censused idle 2026-08-16 15:40 EDT: 0
    python processes, loadavg 0.10 local / 0.01 laptop). Any co-tenant is reported.
    **No value depends on wall-clock** except `c_tier1`, which sets `B*` — and `B*`
    is expected to be 2 across the entire measured cost bracket (§7.2), so a
    contended pilot cannot move it without a >2.2× cost error.

---

## 13. Governance

**Measurement only. 0 strength games on every branch.** The 850 self-play games are
**corpus substrate**, not a strength evaluation: no `experiments/results.csv` row
(mirroring Stage 1's and the OOF run's disposition for a 0-game analysis), no band,
no `governance/BAND_REGISTRY.csv` entry, no claim id minted,
`governance/PRODUCTION.yaml` untouched — on **every** branch. A
`docs/LEVER_INDEX.md` amendment to row 217 (*terminal-grounded tie arbitration*) is
made at start as in-progress and flipped at close.

Outputs land in this directory (`READOUT.{md,json}`, `PILOT.json`,
`POSITION_ORDER.json`, `DISJOINTNESS.json`, `SPLIT.json`, `RUN_PROVENANCE.json`,
`per_position.jsonl`, `corpus/`, `logs/`); oracle records land on the share at
`/mnt/c/carc-shared/tiearb2_20260816/<judge>/walled/leg<r>/`.

## Pointers

- [READ_RULE.md](READ_RULE.md) — the pre-committed branches (committed with this file, before any number)
- [WORKERS.conf](WORKERS.conf) · [PROGRESS.md](PROGRESS.md) · [CORPUS_PIPELINE.md](CORPUS_PIPELINE.md)
- [STAGE1_SLICE_DECOMP.json](STAGE1_SLICE_DECOMP.json) — the §5.4 decomposition of Stage 1's published numbers
- [../tiearb_20260816/DESIGN.md](../tiearb_20260816/DESIGN.md) · [READ_RULE](../tiearb_20260816/READ_RULE.md) · [READOUT](../tiearb_20260816/READOUT.md) — Stage 1, `P-PARTIAL`, the mechanism argument inherited by §2
- [../tiletie_oof_20260814/READOUT.md](../tiletie_oof_20260814/READOUT.md) — `C-CONFIRM`, the licence this chain spends, and the CRN/harness template
- [../tiletie_pricing_20260812/DESIGN.md](../tiletie_pricing_20260812/DESIGN.md) — the corpus construction, the estimators, the inherited threats
- [../tieescalation_20260814/LADDER_READOUT.md](../tieescalation_20260814/LADDER_READOUT.md) — `E-FLAT`, and the **+0.2803** denominator
- [../kwidth_ties_20260814/LADDER_READOUT.md](../kwidth_ties_20260814/LADDER_READOUT.md) — `W-FLAT`
- [../tiletie_mining_20260814/MINING_REPORT.md](../tiletie_mining_20260814/MINING_REPORT.md) — the 38% reach bound; `mine_oracle_sep.make_split`, the unstratified carve §5.4 replaces
- [docs/LEVER_INDEX.md](../../docs/LEVER_INDEX.md) — the tile-tie rows 212–217
