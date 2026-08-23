# EVERY-PLY ROLLOUT ARBITRATION — CHEAP OFFLINE PROBE

> ## ⚠️ PLAN — NOT FUNDED, NOT A PREREG
>
> **Written 2026-08-23. Nothing here is committed, nothing is registered, no compute is
> booked, no branch is binding.** This is the scoping note that the LEVER_INDEX row
> *"every-ply rollout arbitration"* names as the **only sanctioned first step**
> (*"Cheapest probe if ever funded: OFFLINE — oracle-grade champion-pick vs rollout-argmax
> on NON-tied plies via the existing measurement infra; no game cell until that reads
> positive"*). If the owner funds it, a **DESIGN + a mechanical READ_RULE must be committed
> at a git hash BEFORE the first pricing leg runs**, in the house pattern of
> [tiearb READ_RULE](../tiearb_20260816/READ_RULE.md). The §5 branch table below is a
> *draft* of that read-rule, not the read-rule.
>
> **0 games on every branch. No deck band is claimed, no `governance/BAND_REGISTRY.csv`
> row, no claim id, `governance/PRODUCTION.yaml` untouched — regardless of outcome.**

Owner question, verbatim (2026-08-20): *"is it possible we get elo for using it every tile,
even if our leaf has an opinion?"*
Roadmap line: [PROGRAM_ROADMAP](../../docs/PROGRAM_ROADMAP_2026-07-07.md) — *"EVERY-PLY
ARBITRATION PROBE — PLAN FUNDED 2026-08-23 … the probe itself remains unfunded pending the
plan's cost table."*

---

## 0. The headline, first

| | |
|---|---|
| **Minimum-viable screen (SIZE-1)** | **16.2 / 22.3 / 29.1 worker-h** (lo / central / hi) — ≈ **1.4 h at W=16**, ≈ 0.7 h at W=30 |
| **Powered read (SIZE-2)** | **36.4 / 50.0 / 65.3 worker-h** — ≈ 3.1 h at W=16 |
| **Powered + oracle-ceiling companions (SIZE-3)** | **54.3 / 70.3 / 86.6 worker-h** — ≈ 4.4 h at W=16 |
| **Recommendation** | **Fund SIZE-1 as a standalone kill-screen. Do NOT pre-authorise SIZE-2/3** — the n=400 interim is kill-only, and the top-up decision should be re-priced by the pilot's measured pick-change rate `q`, which moves the powered `n` by ~2×. (§8) |

**The brief's cost fear does not survive contact with the artifacts.** The
*"~582 worker-h for ~1,300 legs at M=32"* figure quoted in the funding brief is a
**conflation of two different runs** and is not on disk as a single coherent number:

- **582.3 worker-h** is the `tiearb_widening_20260817` shared-run's **S1 clair-puct line item
  at M = 128**, n₁ = 1,350 positions, 891,993 playouts × c_IF 2.35
  ([shared_run/DESIGN.md](../tiearb_widening_20260817/shared_run/DESIGN.md) §, cost table) —
  one component of that campaign's ≈ 1,174 worker-h total.
- **~1,300** is [`tiletie_pricing_20260812`](../tiletie_pricing_20260812/DESIGN.md) §7.3's
  **position cap**, at **M = 32**, and it was **never reached** — the deduped supply ran out
  at n = 733 positions / 1,468 leg-records. **That entire M=32 run cost ≈ 55.8 worker-h**
  ([STAGE_B_ADDENDUM](../tiletie_pricing_20260812/STAGE_B_ADDENDUM.md)), i.e. **10.4× less**
  than the number the brief carried.

Four independent things make this probe cheap, and all four are properties of *this* design,
not optimism:

1. **The sampling frame is already on disk and costs zero compute** — the eps census emitted
   `gap = top1 − top2` for **all 31,827 tile plies of all 449 `champ449` games**
   (`measurement/tiearb_widening_20260817/census/tile_gap_rows.jsonl`, tracked). Every
   non-tied ply is already labelled with gap, phase, seat, `k_remaining`, `n_legal` and its
   `(deck_seed, ply)` replay key. **§1 is a query, not a run.**
2. **M = 32, not 128.** M=128 was bought only to support B=64 arbiter widths
   ([PLAN_B_gt_16](../tiearb_widening_20260817/PLAN_B_gt_16.md) §0.2). This probe asks a
   B=16-shaped question; 16 selection worlds is exactly the deployed B.
3. **Selfplay/`walled` only ⇒ the RUST clair-puct path.** c_IF = 1.60–2.35 worker-s/playout.
   Adding E4 positions would force the **python** path at **9.85** worker-s/playout — a 5×
   cost multiplier for a stratum that is 8% of the supply. **E4 is excluded by design.**
4. **Selective pricing (§3.4)** — the primary statistic `κ` only needs the champion arm and
   the arms the *arbiter* actually selects. Measured on the spent tiearb corpus, that is
   **2.19× fewer clair-puct playouts** than full-arm-set pricing, with **zero** loss of
   unbiasedness and **zero** loss of the cross-fit's non-circularity.

---

## 1. Sampling frame — which non-tied plies

### 1.1 The population, measured (not modelled)

Recomputed for this plan directly off `census/tile_gap_rows.jsonl`, 449 champion-selfplay
games, all tile plies, both seats:

| | plies | per game | per game per seat |
|---|---:|---:|---:|
| all tile plies | 31,827 | 70.88 | 35.44 |
| exact-tied (`tie_exact`) | 20,322 | 45.26 | 22.63 |
| **non-tied** | **11,505** | **25.62** | **12.81** |
| non-tied with `n_legal` < 2 (forced) | **0** | — | — |

Every non-tied tile ply is arbitrable in principle (no forced moves in the class). The
tied count reproduces the campaign's `TIED_TILE_PLIES_PER_GAME = 22.96` constant to within
1.5%, which is the frame's own sanity check.

### 1.2 Strata — by leaf gap, and why these cuts

`gap` = top1 − top2 over **distinct** leaf values, i.e. the margin by which the v2.7/curve125
leaf prefers its own best move. The census's `K-STRUCTURAL` finding is that the mass sits
*above* the near-tie region: the strata below are cut so the read-out can say **where**
any signal lives, and so the near-tie stratum is not swamped.

| stratum | gap band | plies | share of non-tied | per game per seat |
|---|---|---:|---:|---:|
| **A — near-tie** | 0 < gap ≤ 0.25 | 1,147 | **9.97%** | 1.277 |
| **B — mid-gap** | 0.25 < gap ≤ 1.5 | 4,936 | **42.90%** | 5.497 |
| **C — clear-gap** | gap > 1.5 | 5,422 | **47.13%** | 6.038 |

Supporting CDF over the non-tied class: gap ≤ 0.05 → 1.16% · ≤ 0.10 → 2.87% ·
≤ 0.25 → 9.97% · ≤ 0.50 → 17.87% · ≤ 1.0 → 40.08% · ≤ 1.5 → 52.87% · ≤ 2.0 → 61.89% ·
≤ 3.0 → 75.01% · ≤ 5.0 → 87.08%. Mean `n_legal` = 27.55 (median 27, p90 43, max 88) —
**"all legal arms" is unaffordable and always was**; see §2.

Phase is a **secondary** cut (`phase_bucket` early/mid/late, already on every census row);
the frame's realized phase histogram is balanced enough to read without an explicit quota
(A: 350/407/390 · B: 1,635/1,723/1,578 · C: 1,427/1,977/2,018 early/mid/late). It is
reported per stratum, and it is **never** a branch input.

### 1.3 Allocation — and the variance price of over-sampling A

Population weights `w = (0.0997, 0.4290, 0.4713)`. Sampling proportionally would put only
~100 of 1,000 positions in stratum A. The committed allocation over-samples A:

**`f = (0.25, 0.375, 0.375)`** ⇒ at n = 900: **225 / 337 / 338**.

The pooled estimate is population-reweighted by the *known, exact* `w`, so it stays unbiased.
The variance price is `Σ wₛ²/fₛ = 1.123` vs 1.000 for proportional allocation ⇒ **se inflated
by 1.06×**. That 6% is bought in exchange for 2.5× the near-tie sample. `f = (0.40,0.30,0.30)`
was considered and rejected: it costs 1.17× se for no branch benefit.

### 1.4 Position source and the corpus-blindness property

- **Source:** `measurement/champ_action_logs/champ_games.jsonl` — 449 games, `gen =
  champion_fair_selfplay`, `k_dets=4`, `sims_per_det=688`, `total_budget_per_move=2752`,
  leaf `v2_9_2_Bmild_cap8_curve125`. Lossless `(deck_seed, actions)` replay via
  `scripts/measurement_infra/root_replay.py::replay_actions(deck_seed, actions, ply)` —
  which is policy-agnostic and ply-agnostic (the engine touches the global RNG only at the
  deck shuffle), so an arbitrary non-tied ply is a first-class replay target.
  See [measurement_infra README](../../scripts/measurement_infra/README.md).
- ⭐ **Blindness:** every priced corpus in this programme (`tiletie_pricing_20260812`,
  `tiearb_20260816`, `tiearb2_20260816`, the widening R4 legs, the tie-net stage-0 labels)
  is **tied-ply-only**. **No non-tied ply of this file has ever been priced by any judge, by
  any estimator, on any menu pass.** The frame is therefore unshopped in the strict sense —
  no multiplicity is inherited, and no dev/holdout split is needed to buy blindness. A
  holdout is nonetheless carried (§5.4) purely as a sign-consistency conjunct.
- **Cap 2 positions per game** (seeded) so the root-cluster design effect stays ≈ 1.0; the
  tiearb corpus realized 733 positions / 399 roots with design effect ≈ 0.94.
- **Committed seeded permutation**, cut into sequential chunks exactly as
  `build_tiearb_plan.chunk_slices` does, so **every completed-chunk prefix is a uniform
  random subsample** and a partially-completed run is still readable at its realized n.

---

## 2. Arm sets — what competes, and the incumbent asymmetry

### 2.1 The arm set

Mean `n_legal` at a non-tied tile ply is **27.55**. Pricing all legal arms at M=32 would cost
~2(27.55−1)×32 = 1,699 playouts/position — **~9× the whole SIZE-3 budget for n=900**.
Unaffordable, and also not the deployable question: a deployed every-ply arbiter would sit
at the same **`pooled_q_argmax` root hook** the Stage-2 arbiter sits at, arbitrating the
search's own top candidates.

**Committed arm set: `K = 4`.**

```
arm[0..K-1] = top-K distinct-afterstate actions by the champion's own POOLED ROOT Q,
              from the SAME fresh production search that resolves the champion pick
champ_pos   = 0                                       (argmax pooled Q, by construction)
```

- **K = 4 is not a new constant** — it is `J = 4`, the arm cap the whole tie-arbitration
  family has used since `tiletie_pricing_20260812`.
- **Coverage is 1.0 by construction.** The champion's pick *is* arm 0. This is deliberate:
  `E-FLAT`'s 10× rung died partly on **coverage 0.799** (its pick left the scored set 19.5%
  of the time). That failure mode cannot occur here.
- **Dedup by successor board** (`string_representation`), reusing
  `build_positions.dedupe_tie_actions` — the census already shows that at *tied* plies 80.5%
  of arms are afterstate duplicates. Positions left with < 2 distinct afterstates are
  **dropped and counted** (`G-DISTINCT`).
- ⚠️ **BUILD RISK, named up front:** the champion's pooled root stats are read from
  `root_stats_list`, which **dedups children by node identity, so the played action is often
  absent from the pool** (the documented EV-loss-grader trap). The DESIGN must (a) union the
  pooled ranking with `{champ_pick}`, (b) gate on `G-COVER` = champ present in 100% of arm
  sets, and (c) carry a **pre-committed fallback**: if the pooled ranking cannot be extracted
  reliably, arms = `{champ_pick} ∪ top-(K−1) by LEAF value` from `carc_core::tiearb::chain_values`,
  which needs no root stats at all and costs ~4 ms/ply. The fallback is *weaker* (it hands
  the arbiter the leaf's own shortlist) but it is fully constructible and it still answers
  the owner's question.

### 2.2 The champion pick — and why it is not free

The house precedent is explicit and it costs money:
`scripts/tiletie/champ_picks.py` requires a **fresh production search** at selfplay
positions, because **CL-070 measured that reseeding alone flips ~26–30% of picks at fixed
budget** — the archived `action_played` is *a* champion pick, not *the* champion pick.
Budgeted at `t_champ` = **13.7552 s/position** (`build_positions.DEFAULT_T_CHAMP_SECS`),
bracketed to 25 s at the top end because that constant is a **sequential, uncontended**
measurement and Stage-2's §0.G showed that equating sequential and contended per-move walls
is a category error.

⭐ **This re-search is also what makes the K=4 arm set free** — the pooled root Q ranking
comes out of the same search. The champion is whatever
`champion_factory.make_production_champion("fair", …)` resolves from
`governance/PRODUCTION.yaml` at run time, **read back off the built agent's own manifest and
stamped into every row, never hardcoded** (`champ_picks.py`'s own convention).

### 2.3 ⚠️ THE INCUMBENT ASYMMETRY — the caveat that travels with every number

**The champion's pick IS one of the arms.** Therefore:

- The statistic is **capture-vs-incumbent** and it is **negative-capable**. `κ = 0` means
  *"the rollout arbiter is no better than the champion's own search"*, **not** *"there is no
  signal in the rollouts."*
- `κ` is **not** zero-mean under "the arbiter is uninformative" — an uninformative arbiter
  reads `mean-over-arms − champ`, which Stage-2 measured to be **strongly negative**
  (`RND` = −4.4287 pts/game, **−60.09 elo**). That is why the `rnd` companion (§4.3) exists.
- At a **tied** ply the champion's tie-break is the leaf's lowest-index rule — a near-arbitrary
  incumbent. At a **non-tied** ply the incumbent is an 11k-sim PUCT argmax. **The arbiter's
  opponent is categorically stronger here**, which is prior-against #2 restated as a
  property of the estimator.

### 2.4 The arbiter

`tier1-greedy` (rust `carc_core::tier1`, `RuleBasedPlayer`, v1 object leaf, 1-ply argmax, no
search, played to terminal), argmax of the world-mean over the **16 selection worlds** — which
is exactly the deployed **B = 16** width. Bit-exactness against the python definition of
record is already proven (`G-BITEXACT`, 15,360/15,360 value-bit-identical,
[PHASE_A](../tiearb2_stage2_20260817/PHASE_A.md)). ⚠️ B is **not** a resolved axis: the
`b32v64` cell read `EQUIV` FALSE / `U-UNREADABLE` at `z_D` +1.38. This probe fixes B=16 and
makes no B claim.

---

## 3. Estimand, statistic, and the pricing economy

### 3.1 The estimand

Notation follows [tiearb DESIGN §4](../tiearb_20260816/DESIGN.md) verbatim.
`V^IF[p,a,j]` = terminal margin in final-score points at the root player's seat, position `p`,
arm `a`, CRN world `j = 1…M`, under **`clair-puct`** (production curve125 leaf, PUCT @ 100
clairvoyant sims, played to terminal on a known deck). `V^ARB` = the same physical quantity
under **`tier1-greedy`**, on **bit-identical world and playout seeds**.

For each parity fold `(sel, eva)` — `analyze_tiletie.parity_indices(M, base=1)` and its swap:

```
a_arb   = argmax_a  mean_{j ∈ sel} V^ARB[p, a, j]           # ARBITRATION   (tier1-greedy, B=16)
κ[p]    = mean_{j ∈ eva} V^IF[p, a_arb, j]
        − mean_{j ∈ eva} V^IF[p, champ, j]                  # PRICING       (clair-puct)
```

symmetrized over the two folds. **PRIMARY:**

```
κ  =  Σ_s w_s · mean_{p ∈ s} κ[p]        [pts per NON-TIED tile ply]
z_κ = κ / se_cluster                      cluster-robust on root_id (analyze_tiletie.cluster_robust)
```

Non-circularity is **structural**: the arm is chosen by `tier1-greedy` on the selection
worlds and priced by `clair-puct` on the **disjoint** evaluation worlds. Selection and
evaluation share neither the judge nor the world. Cross-fitting is **not optional** — the two
judges' values at the same world are correlated through the shared deck, so pricing on all M
would leak a winner's curse through the deck draw.

### 3.2 ⚠️ `scale_all` DOES NOT APPLY — declared currency change

`scale_all` (the analytic-zero add-back) is the tied-ply population correction for
*"positions whose entire tie set collapses to one afterstate"*. **There is no such degenerate
class at a non-tied ply** — the top arm is unique by construction. **`scale_all ≡ 1.0`.**
Consequence: **κ is NOT directly comparable to the tied-ply `arb = +0.2065`**, which is a
`scale_all`-scaled number (its unscaled *discriminable* sibling is +0.2844). Every readout
must print this sentence.

### 3.3 The elo chain — calibrated on Stage-2, not on the ÷3.2 prior

The ÷3.2 `NON_ADDITIVITY` constant is **n = 1 with a ±1.6× bracket**. Stage-2 supplies a
*measured* end-to-end mapping, and it says ÷3.2 was ~2.2× conservative:

| | |
|---|---|
| offline tied-ply `arb` | +0.2065 pts/tied ply |
| realized fire rate `phi` | 17.5 fired plies/game |
| ⇒ raw | +3.614 pts/game |
| **realized deck-paired margin** | **+3.0700 pts/game** ⇒ realized/raw = **0.849** (divisor 1.18) |
| realized elo | **+23.92** [−0.21, +48.06] ⇒ **7.79 elo per pts/game** |

So the honest chain is a **bracket**, `NA ∈ [0.31 (÷3.2 prereg), 0.85 (Stage-2 realized)]`:

```
pts_per_game  =  κ × 12.812 × NA          elo ≈ 7.79 × pts_per_game
```

| κ [pts/non-tied ply] | pts/game | elo image |
|---:|---|---|
| 0.10 | 0.40 – 1.09 | **+3.1 … +8.5** |
| **0.15** | 0.60 – 1.63 | **+4.6 … +12.7** |
| 0.20 | 0.79 – 2.18 | +6.2 … +17.0 |
| 0.35 | 1.39 – 3.81 | +10.8 … +29.7 |

⚠️ **The +23.92 elo Stage-2 headline may never be quoted bare** — its winrate `z` is +1.94,
below 2. The margin convicts; the win-rate does not. Same rider applies to every elo image
above.

### 3.4 ⭐ Selective pricing — the 2.19× saving, and why it is exactly unbiased

`κ[p] = 0` **identically** when both folds' `a_arb` equal `champ` — no clair-puct value is
needed to know that. So price, per position, only

```
arms_to_price(p)  =  {champ} ∪ {a_arb(fold 1), a_arb(fold 2)}
```

Measured on the spent `tiearb_20260816` corpus (733 positions, mean 3.0 arms, fold agreement
0.508): `|arms_to_price|` = 1 / 2 / 3 for **174 / 448 / 111** positions ⇒ mean **1.914**
⇒ mean playout multiplier `2·(A−1)` = **1.828** against **4.005** for full-arm pricing =
**2.19× cheaper**. At K = 4 the full multiplier is 6.0, so the saving is larger still
(budgeted conservatively at m_sel ∈ [1.8, 2.6], central 2.2).

Three properties that must be gated, not assumed:

1. **Unbiased.** The un-priced positions enter the mean as **exact zeros** and enter `n` and
   the cluster structure. `G-ZEROFILL`: `n_priced + n_zero == n_analysed`.
2. **Non-circular.** `a_arb` depends only on `V^ARB`. **No clair-puct value influences which
   arms get priced.** The cross-fit is untouched.
3. **What it costs us:** `ora`, `rnd` and `arm0` are *not* computable at full n. They move to
   the **Tier-2 companion subsample** (§4.3), labelled underpowered.

---

## 4. The bar — pre-stated, and derived from the cell it would fund

### 4.1 The fund bar

> **`κ* = +0.15` pts per non-tied tile ply, with `z_κ ≥ +2.0`.**

**Derivation (not a taste judgement).** The only thing a positive probe can license is a
DESIGN for a deck-paired game cell. Stage-2's realized game-cell precision at n = 800 paired
is `se_D` = 0.933 pts/game on the ARB−RND contrast and `se` = 0.691 on the single-cell
margin ⇒ **an n=800 cell resolves ≈ 1.38 pts/game at 2σ.** Requiring the funded cell to be
resolvable gives:

- under the **optimistic** (Stage-2-realized) chain `NA = 0.85`: κ ≥ **0.127**
- under the **conservative** (÷3.2 prereg) chain `NA = 0.31`: κ ≥ **0.347**

`κ* = 0.15` sits just above the optimistic requirement. **Therefore the read-out is required
to print, mechanically, the implied game-cell size** `n_cell = 800 · (1.38 / pts_per_game)²`
at both NA ends, so a `E-FUND` firing at κ̂ = 0.16 cannot be mistaken for *"an n=800 cell will
settle it"*. A second, cleaner threshold is carried:

> **`κ** = +0.35`** — an n=800 cell resolves it under **both** NA ends.

### 4.2 ⛔ The near-tie-only deployment variant is arithmetically dead BEFORE the probe runs

A natural fallback — *"arbitrate only where the leaf is nearly indifferent"* — is closed by
the mass desert, and this is free to state now:

Stratum A carries **1.277 non-tied plies per game per seat**. For an n=800 cell to resolve an
A-only deployment under the conservative chain would need
`κ_A ≥ 1.38 / (1.277 × 0.31)` = **3.49 pts per ply**. The *tied*-ply oracle **ceiling**
(`ora`) is **+0.2545**. A near-tie-only deployment would need a per-ply effect ~14× the
entire oracle headroom of the adjacent ply class. **It cannot be funded at any κ_A the probe
could measure.** ⇒ **The probe must be sized on the FULL non-tied population or not at all,**
and per-stratum reads are for *mechanism interpretation only* — they can never rescue a
pooled null by carving out a sub-population.

This is the census's `K-STRUCTURAL` finding cashed out one step further: the mass desert
means there is no cheap partial deployment hiding between "tied only" and "every tile".

### 4.3 Companions — reported on every branch, never a branch input

| id | quantity | why |
|---|---|---|
| `ora` (Tier-2) | oracle headroom: arm selected by the **IF** judge's own selection-half argmax, priced on the disjoint half — `analyze_tiletie`'s `headroom_champ` | the **ceiling** on κ within this arm set. If the champion's PUCT pick is already at the oracle, no arbiter can pay. |
| `F` (Tier-2) | `κ / ora` on the subsample, root bootstrap 20,000 reps | the cross-programme capture currency E-FLAT (0.00/0.18/0.18), W-FLAT (0.11/0.26/0.09/0.09/0.30) and tiearb (0.811) were all graded in. **Secondary here** — the decision is absolute (§4.1), not fractional. |
| `rnd` (Tier-2) | seeded random arm over `arm_order`, priced identically | **the null level.** κ is *not* zero-mean under an uninformative arbiter (§2.3); Stage-2 measured `RND` at −60.09 elo. |
| `arm0_leaf` (Tier-2) | the **leaf's own argmax** as comparator | answers a second free question the owner's phrasing implies: *at non-tied plies, does the champion's search even beat its own leaf?* |
| `q` = `pickchg` | fraction of positions where `a_arb ≠ champ`, per fold and pooled, per stratum | E-FLAT/W-FLAT's own diagnostic (*"moves picks without improving them"*), **and** the quantity that re-prices the powered `n` (§6). |
| `sel_agree` | fraction where `a_arb = a_ora` (Tier-2) | selector quality independent of magnitude. |
| `phi_nontied` | realized arbitrable non-tied plies/game after dedup | the deployed fire rate; feeds the ρ_wall estimate for any successor. |
| `n_cell` | implied game-cell size at both NA ends (§4.1) | so no branch can imply an unfunded cell is cheap. |

`SEC-ARB` (the arbiter's picks priced by `tier1-greedy` itself) is **audit-only and circular
by construction** — its capture against its own headroom is 1 — and may never be a branch
input. Same status as in [tiearb DESIGN §4.3](../tiearb_20260816/DESIGN.md).

---

## 5. Branch table (DRAFT) + reachability arithmetic

### 5.1 Preconditions — `U-UNREADABLE` fires and no other branch may fire

| id | condition |
|---|---|
| `G-KNOWNGOOD` | `scripts/tiletie/probe_pickers.py knowngood` does not reproduce `arb = +0.2065`, `n = 733`, `n_roots = 399` on the spent tied corpus with the shared estimator functions this probe imports |
| `G-CRN` | any ARB record has `crn_verified != true` / `checksum_ok != true`, or `world_seeds`/`playout_seeds` not **bit-identical** to the clair-puct record for the same `rid` |
| `G-COVER` | the champion arm is absent from the arm set on **any** analysed position (must be 0 by construction — a nonzero count is an instrument defect) |
| `G-ARMSET` | any priced arm is missing from either judge, or the two judges' `arm_order` disagree |
| `G-ZEROFILL` | `n_priced + n_zero != n_analysed`, or any zero-filled position has `|arms_to_price| != 1` |
| `G-DISTINCT` | > 10% of planned positions dropped for `n_distinct_afterstates < 2` (dropped positions are counted and reported in every case) |
| `G-FRAME` | realized stratum shares deviate from the committed `f = (0.25, 0.375, 0.375)` by > 3 pp, or realized `w` differs from the census `w` |
| `G-N` | fewer than **85%** of the planned positions analysed at the read point |
| `G-EPOCH` | leaf hash ≠ `a36d2e15a3b3d71d`, or any leg not on the `walled` rules profile, or a resolved champion config that differs across rows |
| `G-BLIND` | the DESIGN + READ_RULE commit hash does not precede the first pricing leg in git history; or the branch section is not byte-identical across revisions |

### 5.2 Branches on the primary read

Read points: **interim at n = 400 (KILL-ONLY)** and **final at n = 900**. The interim may fire
`E-HARM` or stop for futility and **may not fire any positive branch** — a one-sided futility
interim, so essentially no alpha is spent on the positive side. Stated before the run.

| branch | condition | what it licenses |
|---|---|---|
| **`E-HARM`** | `κ̂ ≤ −0.15` ∧ `z_κ ≤ −2.0` | Every-ply arbitration is **actively harmful** at non-tied plies. **Lever CLOSED**, LEVER_INDEX row flipped to KILLED. Licenses nothing else. |
| **`E-CLEAN`** | `κ̂ ≥ +0.35` ∧ `z_κ ≥ +2.0` ∧ ≥ 2 of 3 stratum point estimates ≥ 0 | Licenses **a DESIGN for one deck-paired game cell** (owner decision), resolvable at n = 800 under both NA ends. **Not a game cell.** |
| **`E-FUND`** | `κ̂ ≥ +0.15` ∧ `z_κ ≥ +2.0` ∧ ≥ 2 of 3 stratum point estimates ≥ 0 ∧ `κ̂_holdout ≥ 0` | Same, **but** the read-out must print `n_cell` at both NA ends; under the conservative chain the cell it funds is **not** n=800. |
| **`E-FLATNULL`** | `UB95(κ̂) < +0.15` ∧ ¬`E-HARM` | **A FUNDING VERDICT, NOT AN EXCLUSION** — same words `W-FLAT` and `F-FLAT` used. Lever **PARKED** with its printed re-open bar. |
| **`E-UNRESOLVED`** | anything else | Nothing closes, nothing is licensed. The read-out **must** print the `n` that would resolve the observed κ̂ at the realized dispersion (the `tiearb` READ_RULE's own discipline). |

### 5.3 Reachability — every headline branch, at committed dispersion

Realized per-position dispersion, recomputed from `tiearb_20260816/per_position.jsonl` (not
projected): `sd(arb) = 1.5819` at `q = 0.7626` ⇒ **per-changed-position sd = 1.8115**, cluster
design effect **0.94** (use 1.0). With the §1.3 stratification penalty **×1.06**:

```
se(κ)  =  1.06 × 1.8115 × sqrt(q) / sqrt(n)
```

| n | q = 0.50 | q = 0.76 | q = 0.90 |
|---:|---:|---:|---:|
| 400 | 0.068 | **0.084** | 0.091 |
| 600 | 0.055 | 0.068 | 0.074 |
| **900** | 0.045 | **0.056** | 0.061 |
| 1200 | 0.039 | 0.048 | 0.053 |

**At the planning-central `q = 0.76`:**

| branch | fires when κ̂ … | n = 400 | n = 900 |
|---|---|---|---|
| `E-HARM` | ≤ −0.15 **and** z ≤ −2 | κ̂ ≤ **−0.168** ✅ reachable | κ̂ ≤ **−0.150** ✅ |
| `E-FUND` | ≥ +0.15 **and** z ≥ +2 | κ̂ ≥ **+0.168** ✅ (interim cannot fire it) | κ̂ ≥ **+0.150** ✅ |
| `E-CLEAN` | ≥ +0.35 **and** z ≥ +2 | κ̂ ≥ 0.35 ✅ | κ̂ ≥ 0.35 ✅ |
| `E-FLATNULL` | UB95 < +0.15 | κ̂ < **−0.018** ⚠️ marginal | κ̂ < **+0.038** ✅ |

**No unreachable headline branch.** ⚠️ Two honest limits, stated before the run:

- **`E-FLATNULL` is marginal at n = 400.** The screen can only park the lever if κ̂ comes in
  **at or below −0.018**, i.e. essentially at or below zero. That is the *expected* case under
  all three priors, but it is not guaranteed, and the screen must not be sold as *"it will
  settle it either way."*
- **The screen cannot convict the fundable effect.** At n = 400 a true κ = +0.15 reads z = 1.8.
  A positive verdict needs the n = 900 top-up. **This is a kill-oriented screen** — it has
  good power against the prior-favoured hypothesis (harm) and poor power against a modest gain.

**Per-stratum se at n = 900** (225/337/338): **0.105 / 0.086 / 0.086** at q = 0.76. Every
per-stratum number is therefore a **sign read at best**, is labelled underpowered, and is
**never** a branch input except through the `E-FUND`/`E-CLEAN` sign-consistency conjunct.

### 5.4 Holdout

25% of roots reserved by seeded split **before any leg runs**, entering `E-FUND` only as the
blind sign-consistency conjunct `κ̂_holdout ≥ 0`. Rationale is the tiearb precedent, which is
also the warning: **tiearb's pooled read fired every conjunct except `C_h` and landed
`P-PARTIAL` on a holdout of −0.0051** — a 211-position holdout that its own DESIGN §4.4 had
already shown could not convict even a 100% capture. Here the holdout is ~225 positions, so
the same limitation applies and **the branch input is the pooled read**, declared now, not
after the fact.

---

## 6. Cost table

### 6.1 Unit costs — all realized, none modelled

| quantity | value | conditions | source |
|---|---:|---|---|
| `c_IF` clair-puct **rust**, planning | 1.4755 ws/playout | phase-weighted, M=32 | `tiletie_pricing_20260812/DESIGN.md` |
| `c_IF` clair-puct **rust**, Stage-A **realized** | **1.5999** (2.24 / 1.69 / 0.80 early/mid/late) | W=14, 587 leg-records | `tiletie_pricing_20260812/STAGE_B_ADDENDUM.md` |
| `c_IF` clair-puct **rust**, widening committed | **2.35** | W=30 **contended** | `tiearb_widening_20260817/shared_run/DESIGN.md` |
| `c_IF` clair-puct **python** | 9.85–9.86 | e4 `fixed_v1`/`app_aug2` — **excluded from this probe** | `tiletie_pricing_20260812/SMOKE.md` |
| `c_ARB` tier1-greedy **rust**, committed | **0.178232** | W=30, `G-BITEXACT` 15,360/15,360 | `tiearb2_stage2_20260817/COST_REMEASURE.json` |
| `c_ARB` tier1-greedy rust, W=1 | 0.093769 | same sample | same |
| `c_ARB` fresh remeasure | 0.136–0.1392 | W=30, two strata | `tiearb_widening_20260817/c_remeasure_r4_driver.log` |
| `t_champ` champion pick re-search | 13.7552 s/position | **sequential, uncontended** | `build_positions.DEFAULT_T_CHAMP_SECS` |

Cost model — the repo's own, unmodified (`scripts/tiletie/build_positions.py::cost_plan`,
schema "DESIGN.md #7.1"), in the harness's **leg-record** unit (reference + candidate):

```
playouts        = Σ_p 2 · (A_p − 1) · M
worker_secs     = playouts · c   +   n · t_champ
wall_hours(W)   = worker_secs / (3600 · W)
```

`c` is treated as **constant per playout in M** (seeds are `sha256("world"|rid|j|salt)`,
prefix-stable in M) so cost scales linearly in M. ⚠️ **No artifact on disk ties `c_IF` to
`--oracle-sims`;** 100 is the only value ever run for this backend and no sims-scaling curve
is inferred here.

Budget brackets used below: `c_IF` ∈ {1.5999, 2.0, 2.35}, `t_champ` ∈ {13.76, 19.0, 25.0} s,
`c_ARB` = 0.178232 (the committed value; the remeasure came in **cheaper**, so this is
one-sided conservative), `m_sel` = 2·(Ā−1) ∈ {1.8, 2.2, 2.6}, `m_full` = 2·(K−1) = 6.0.

### 6.2 Line items (worker-hours, lo / central / hi)

| line item | n | wh |
|---|---:|---|
| corpus build — champion re-search + pooled-Q arm sets | 450 | 1.7 / 2.4 / 3.1 |
| corpus build — champion re-search + pooled-Q arm sets | 1,000 | 3.8 / 5.3 / 6.9 |
| ARB judge (tier1-greedy rust, all K=4 arms, M=32) | 450 | 4.3 |
| ARB judge (tier1-greedy rust, all K=4 arms, M=32) | 1,000 | 9.5 |
| **IF pricing — selective** (§3.4) | 400 | **10.2 / 15.6 / 21.7** |
| IF pricing — selective, top-up | +500 | 12.8 / 19.6 / 27.2 |
| IF pricing — full-K **delta** for `ora`/`rnd`/`arm0` companions | 300 | 17.9 / 20.3 / 21.3 |
| frame query + replay + dedup | — | < 0.5 (negligible) |

### 6.3 Sizes

| size | contents | worker-h (lo / central / hi) | wall @ W=16 | what it can / cannot resolve |
|---|---|---|---|---|
| **SIZE-1 — MVS screen** | pool 450 · ARB all-K · IF selective n=400 · **no `ora`** | **16.2 / 22.3 / 29.1** | **1.4 h** | **CAN**: fire `E-HARM` (κ̂ ≤ −0.168); put a 2σ upper bound on κ (κ̂ + 0.168) — e.g. it excludes a tied-ply-sized per-ply effect κ ≥ +0.25 whenever κ̂ ≤ +0.082; measure `q`, `phi_nontied`, distinct-afterstate rate, per-stratum signs; re-price SIZE-2 exactly. **CANNOT**: convict `E-FUND`; park via `E-FLATNULL` unless κ̂ ≤ −0.018; resolve any single stratum; produce `F` or the oracle ceiling. |
| **SIZE-2 — powered** | pool 1,000 · ARB all-K · IF selective n=900 · no `ora` | **36.4 / 50.0 / 65.3** | 3.1 h | Adds: `E-FUND`/`E-CLEAN`/`E-FLATNULL` all reachable at q ≤ 0.90; per-stratum sign reads at se 0.086–0.105. Still no `F`, no ceiling, no null level. |
| **SIZE-3 — powered + companions** | SIZE-2 + full-K on an n₂ = 300 subsample | **54.3 / 70.3 / 86.6** | 4.4 h | Adds `ora` / `F` / `rnd` / `arm0_leaf` / `sel_agree` at se ≈ 0.095 — **underpowered by construction**, interpretation only. |
| *(reference)* powered **without** the selective trick | n=900 all arms full-K | 90.1 / 110.8 / 129.3 | 6.9 h | identical statistics to SIZE-3 at **1.5×** the cost — the §3.4 economy quantified. |

**The minimum-viable screen comes in at ≈ 22 worker-h central, ≈ 29 worker-h at the
pessimistic end — comfortably under the ~50 worker-h line, and under 1.5 h of one box.**

### 6.4 Build cost (agent time, not compute)

| item | ~LoC | note |
|---|---:|---|
| `build_everyply_plan.py` — frame query, strata, seeded order, chunk slices | ~200 | mirrors `build_tiearb_plan.py`; frame is a pure query over the tracked census jsonl |
| `build_positions.build_topk_arms()` — sibling of `build_tie_arms` | ~40 | drops the two tie asserts (`len(tie_actions) ≥ 2`, `arms[0] == argmax_action`); everything downstream (`_seeded_cap`, `dedupe_tie_actions`, `resolve_champion_arm`, `build_arms_index`, `write_leg_files`) is already shape-agnostic |
| champ-pick + pooled-root-Q pass | ~60 | extends `champ_picks.py`; **carries the `root_stats_list` dedup trap + the leaf-top-K fallback** (§2.1) |
| `analyze_everyply.py` — fork of `analyze_tiearb.py` | ~300 | `scale_all ≡ 1.0`; population reweighting; zero-fill; the §5 branch table |
| tests | ~250 | zero-fill identity, reweighting, frame reproduction, and a golden that reproduces `arb = 0.2065` through the shared estimators |

**No rust change is required.** `carc_core::tiearb::build_arms` is already candidate-list
agnostic (only `detect_tie` is tie-specific) but this probe is entirely offline and uses the
python arm-builder; a rust PyO3 surface would only be needed by a *deployed* every-ply
arbiter, i.e. after a positive game cell. ⚠️ `probe_pickers.py` **cannot be run unmodified** —
`cmd_grade` calls `require_knowngood` unconditionally against hard-pinned `n = 733 /
n_roots = 399`, so a new corpus fails by construction. Run `knowngood` as a **separate gate**
(§5.1) and import the estimator functions directly; do not fork the pinned constants.

---

## 7. Honesty rails — printed on EVERY read-out, verbatim

1. **PRIOR-AGAINST 1 — the mass desert.** The eps census (`K-STRUCTURAL`, corroborated on a
   fresh 31,827-ply read) shows **no gentle widening exists between exact ties and eps ≈
   1.5–2.0**: 90% of non-tied tile plies sit above a quarter-point of leaf preference, and
   `m ≥ 0.30` first arrives at eps ≈ 1.5. The plies this probe adds are ones where **the leaf
   has a real opinion**. [census READOUT §8](../tiearb_widening_20260817/census/READOUT.md)
2. **PRIOR-AGAINST 2 — "the vart".** Tie-triggered search escalation died at its pre-gate
   (`E-FLAT`): 2× / 4× / 10× more search **moves** tied-ply picks (18/24/31%) but does not
   **improve** them (−0.0094 / +0.0494 / +0.0502, all below the ratio-0.35 ∧ z-2 bar; 10×
   also failed coverage at 0.799). The tie-arbiter's win is an **orthogonal terminal-grounded
   signal breaking a ply where the primary signal is exactly ZERO.** At a non-tied ply it must
   instead **beat an 11,008-sim PUCT search, not silence.**
3. **PRIOR-AGAINST 3 — the `RND` control.** Stage-2's matched-compute control read
   **−4.4287 pts/game, −60.09 elo**: **a leaf-tied set is NOT a set of interchangeable moves,
   and the champion's own tie-break is far better than arm-average.** The greedy-continuation
   values carry policy bias that is common-mode across arms **only when the primary signal is
   silent** — which is exactly the condition this probe removes.
4. **INCUMBENT ASYMMETRY** (§2.3) — the champion's pick is one of the arms; κ is
   capture-vs-incumbent and negative-capable; κ = 0 means *"no better than the champion"*, not
   *"no signal"*; and κ is not zero-mean under an uninformative arbiter.
5. **CURRENCY** (§3.2) — `scale_all ≡ 1.0`; κ is **not** directly comparable to the tied-ply
   `arb = +0.2065`.
6. **⚠️ OFFLINE CAPTURE HAS UNDER-READ THE GAME CELL ON THIS EXACT AXIS.** At tied plies the
   offline instrument returned `P-PARTIAL` — *not convicted*, with a **negative blind
   holdout** (−0.0051) — and the Stage-2 game cell then fired `G-CONFIRMED` at `z_D` +8.04.
   **⇒ `E-FLATNULL` is a FUNDING verdict, never an exclusion**, in the same words `W-FLAT` and
   `F-FLAT` used. An offline null here does **not** prove the deploy effect is null; it proves
   we will not spend a game cell on it.
7. **BUDGET-EPOCH MISMATCH** — the corpus *games* were generated by the k4×688 / 2752-budget
   champion (`champ_games.jsonl` header); the *incumbent priced* is whatever
   `PRODUCTION.yaml` resolves at run time. Inherited verbatim from `tiletie_pricing_20260812`
   and unchanged by this design.
8. **NO DEPLOY IS LICENSED ON ANY BRANCH.** `rho_phone` = 5.520 at B=16 is **unsolved** for
   the *tied-ply* arbiter already; every-ply arbitration roughly doubles fire rate
   (12.81 non-tied plies/game/seat added to a realized `phi` of 17.5) and therefore roughly
   doubles it again. Desktop-only at best.
9. **`SEC-ARB` is circular by construction** and may never be a branch input.

---

## 8. Recommendation

**Fund SIZE-1 — the ≈ 22 worker-h (29 worst-case) minimum-viable screen — and nothing beyond
it yet.** My reasoning, stated as a judgement rather than an arithmetic result: the three
priors-against are strong, independent and *mechanistic*, so the modal outcome is a negative
κ, and a negative κ is exactly what SIZE-1 is good at — it can fire `E-HARM` at κ̂ ≤ −0.168,
which is well inside the range the `RND` result (−60.09 elo from re-picking among arms the
leaf calls *equal*) makes plausible once the leaf's opinion is non-zero. That is high kill
quality per worker-hour: a named, owner-raised lever closes permanently for less than a
box-hour and a half, and the LEVER_INDEX row stops being a "NAMED, NEVER TRIED" invitation to
re-propose. Two further things make the screen worth more than its own verdict: it produces
**the first non-tied CRN-priced corpus in the programme** — every existing priced corpus is
tied-ply-only, and sibling-ranking labels off the leaf's *non*-tied shortlist are the one
thing the CL-065/CL-073 move-discrimination line and the parked tie-net have never had — and
it measures `q`, which re-prices the powered top-up by ~2× in either direction (n ≈ 660 at
q = 0.5, n ≈ 1,180 at q = 0.9). **Do not pre-authorise SIZE-2/3 in the same decision:** the
n = 400 interim is deliberately kill-only, the top-up is cheap to add later on the *same*
committed seeded order with no multiplicity cost, and pre-authorising it would spend ~30
extra worker-h against a hypothesis the screen may already have killed.

**The honest case against funding even SIZE-1**, which the owner should weigh: rail 6 is
real — offline capture *under-read* the game cell on this exact axis, so a null result here
is a funding verdict and not knowledge, and the screen's `E-FLATNULL` branch is marginal at
n = 400 (it needs κ̂ ≤ −0.018 to park the lever). The realistic distribution of outcomes is
therefore **≈ kill / ≈ unresolved**, with a genuine-but-unlikely `E-CLEAN`. If the owner's
appetite is for *strength*, not for closing levers, ~22 worker-h buys more elsewhere. My view
is that closing it is still worth it at this price, chiefly because the question is the
owner's own and it will otherwise be asked again.

**⛔ What I would NOT fund at any size:** a game cell before the offline read; a near-tie-only
deployment variant (§4.2 — arithmetically dead); an M > 32 or `--oracle-sims` > 100 variant
(no artifact on disk prices either axis); and any E4-stratum positions (the python clair-puct
path is 5× the rust cost for 8% of the supply).

---

## 9. Pointers

- [LEVER_INDEX](../../docs/LEVER_INDEX.md) — rows *"every-ply rollout arbitration"*,
  *"terminal-grounded tie arbitration"*, *"tie-triggered search escalation" (the vart)*,
  *"k-width / determinization at tied plies" (the wart)*, *"learned tie-breaker net"*
- [eps / tie census READ-OUT §8](../tiearb_widening_20260817/census/READOUT.md) — the mass desert
- [PLAN_eps_near_ties](../tiearb_widening_20260817/PLAN_eps_near_ties.md) — rung (4), `K-DEAD` / `K-STRUCTURAL`
- [tiearb DESIGN §4](../tiearb_20260816/DESIGN.md) · [READ_RULE](../tiearb_20260816/READ_RULE.md) · [READOUT](../tiearb_20260816/READOUT.md) — the cross-fit capture estimator, the branch-table house style, the realized dispersions
- [tiletie_pricing DESIGN](../tiletie_pricing_20260812/DESIGN.md) · [STAGE_B_ADDENDUM](../tiletie_pricing_20260812/STAGE_B_ADDENDUM.md) — the pricing machinery and its realized costs
- [Stage-2 PHASE_A](../tiearb2_stage2_20260817/PHASE_A.md) · [Stage-2 READOUT](../tiearb2_stage2_20260817/READOUT.md) — `c_tier1_rust`, `G-BITEXACT`, the deploy-elo calibration, the `RND` control
- [shared_run DESIGN](../tiearb_widening_20260817/shared_run/DESIGN.md) · [PLAN_B_gt_16](../tiearb_widening_20260817/PLAN_B_gt_16.md) — the 582 worker-h / M=128 line item
- [measurement_infra README](../../scripts/measurement_infra/README.md) — lossless root replay, snapshot search, h200 gap tagging, the 4-strata queue
- `scripts/tiletie/probe_pickers.py` · `scripts/tiletie/analyze_tiearb.py` · `scripts/tiletie/build_positions.py` — the harness this probe forks and imports
- [PROGRAM_ROADMAP](../../docs/PROGRAM_ROADMAP_2026-07-07.md) — the queue line this plan answers
