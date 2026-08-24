> ⛔→✅ **FROZEN 2026-08-23 (branch-freeze on everyply-freeze; the blind commit INTRODUCES THIS BANNER; local main latched under a live suite; merges at the quiet window). Owner funding: "every ply. fund." 2026-08-23. PRE-FREEZE ORCHESTRATOR RULING, per the pair's own §3.1 pre-committed fallback: --arm-builder leaf_topk IS the instrument (pooled-Q unreachable through the mandated seams — rust exposes pooled N, not Q); the drafters' ten applied readings are adopted as pre-freeze resolutions. No statistic exists at freeze time; §0.A stands: KILL-ONLY interim.**

# EVERY-PLY ROLLOUT ARBITRATION — CHEAP OFFLINE PROBE (SIZE-1) — DESIGN (DRAFT)

Run id `everyply_probe_20260823`. Pair: this file + [`READ_RULE.md`](READ_RULE.md).
Launcher (drafted, non-executable): [`run_probe_DRAFT.sh`](run_probe_DRAFT.sh).
Band: **none owed** — [`BAND_NOTE.md`](BAND_NOTE.md).
Plan of record: [`../everyply_probe_plan_20260823/PLAN.md`](../everyply_probe_plan_20260823/PLAN.md).

Style precedent: [`../track_d2_prep/DESIGN.md`](../track_d2_prep/DESIGN.md) /
[`READ_RULE.md`](../track_d2_prep/READ_RULE.md) — read for shape and banner discipline, not
copied for content. Estimator and corpus precedent: [`../tiearb_20260816/DESIGN.md`](../tiearb_20260816/DESIGN.md).

**This document is a TRANSCRIPTION, not a redesign.** Where it states a number, that number
comes from the plan; where it adds anything, the addition is (a) an *address* — the exact tool,
function or field a gate reads — or (b) an arithmetic consequence that is now **mechanically
verified by tests** ([`../../tests/test_everyply_plan.py`](../../tests/test_everyply_plan.py),
75 tests). Two places where the transcription had to *sharpen* the plan rather than copy it are
flagged inline as **⚠️ SHARPENED** (§7.1 and §11's `G-EPOCH`); neither moves a bar.

---

## 0. AUTHORIZATION BLOCK

**SIZE-1 IS FUNDED. NOTHING ELSE IS.** The owner's 2026-08-23 *"every ply. fund."* funds the
≈22 worker-h minimum-viable screen. Per the plan's §8, **SIZE-2 and SIZE-3 are NOT
pre-authorised** and must not be launched, budgeted, or implied by any branch of this pair.

Still owed before game 1 — the orchestrator's calls, not this draft's:

| # | owed | why it is not a builder's call |
|---|---|---|
| (a) | **freeze + commit this pair**, then stamp `BLIND_COMMIT` into the launcher | the blind ordering IS the pre-registration; git history is the proof |
| (b) | **the two OWED BUILDS of §6.3 land and their gates pass** | the corpus stage and the analyser do not exist yet; the launcher hard-refuses without them |
| (c) | **which box, and a clean process census on it** | standing repo rule; the local 5900XT was **busy** at drafting time (a `reconcile_backend` run at W=14) — this pair therefore assumes the **laptop** (§5.4) |
| (d) | **the §12 pilot has run and its mechanical rule returned LAUNCH** | the pilot is the only place a knob may move; after the blind commit nothing moves |

**Pre-launch checklist** (mirrors the jcz / b32v64 / D2 precedent):

- [ ] this pair (`DESIGN.md` + `READ_RULE.md`) frozen and committed
- [ ] `BLIND_COMMIT=<sha>` stamped into [`run_probe_DRAFT.sh`](run_probe_DRAFT.sh) (it reads a placeholder and refuses to run without it)
- [ ] `scripts/tiletie/build_everyply_corpus.py` and `scripts/tiletie/analyze_everyply.py` exist and their tests pass (§6.3)
- [ ] `G-KNOWNGOOD` PASS — `probe_pickers.py knowngood` reproduces `arb = +0.2065` on the spent tied corpus
- [ ] §12 pilot run, mechanical rule returned LAUNCH
- [ ] process census clean on the target box
- [ ] `RUN_LIVE.json` sentinel dropped for the duration (freeze-latch discipline; the launcher does this on a trap)
- [ ] **NO band claimed** — verify [`BAND_NOTE.md`](BAND_NOTE.md)'s conclusion still holds

---

## 1. THE QUESTION

**Owner, verbatim (2026-08-20):** *"is it possible we get elo for using it every tile, even if
our leaf has an opinion?"*

The tie arbiter (`tier1-greedy` rollouts, B=16, J=4) currently fires only where the leaf is
**exactly** tied. This probe asks whether it would pay to fire it at **non-tied** tile plies
too — where the leaf has a real preference and the champion's own 11,008-sim PUCT search has
already spoken.

Roadmap line ([`../../docs/PROGRAM_ROADMAP_2026-07-07.md`](../../docs/PROGRAM_ROADMAP_2026-07-07.md)):
*"EVERY-PLY ARBITRATION PROBE — PLAN FUNDED 2026-08-23 … the probe itself remains unfunded
pending the plan's cost table."* The plan landed; its cost table says ≈22 worker-h central; the
owner funded SIZE-1.

The [`LEVER_INDEX`](../../docs/LEVER_INDEX.md) row *"every-ply rollout arbitration"* names the
**only sanctioned first step**: *"Cheapest probe if ever funded: OFFLINE — oracle-grade
champion-pick vs rollout-argmax on NON-tied plies via the existing measurement infra; no game
cell until that reads positive."* **This design is exactly that step and nothing more.**

---

## 2. THE SAMPLING FRAME

### 2.1 The population — measured, not modelled

Recomputed directly off the tracked census
[`../tiearb_widening_20260817/census/tile_gap_rows.jsonl`](../tiearb_widening_20260817/census/tile_gap_rows.jsonl)
(449 `champ449` champion-selfplay games, all tile plies, both seats). **§1 is a query, not a
run — it costs zero compute.** Every figure below is re-derived at build time by
`scripts/tiletie/build_everyply_plan.py::frame_report` and asserted by `::assert_frame`, so a
changed census cannot silently re-base the design:

| | plies | per game | per game per seat |
|---|---:|---:|---:|
| all tile plies | 31,827 | 70.88 | 35.44 |
| exact-tied (`tie_exact`) | 20,322 | 45.26 | 22.63 |
| **non-tied** | **11,505** | **25.62** | **12.81** |
| non-tied with `n_legal` < 2 (forced) | **0** | — | — |

Every non-tied tile ply is arbitrable in principle — **there are no forced moves in the class.**
The tied count reproduces the campaign's `TIED_TILE_PLIES_PER_GAME = 22.96` constant to within
1.5%, which is the frame's own sanity check.

### 2.2 Strata — by leaf gap

`gap` = `top1 − top2` over **distinct** leaf values: the margin by which the v2.7/curve125 leaf
prefers its own best move. The census's `K-STRUCTURAL` finding is that the mass sits *above* the
near-tie region; these cuts exist so the read-out can say **where** any signal lives, and so the
near-tie stratum is not swamped.

| stratum | gap band | plies | share of non-tied | per game per seat |
|---|---|---:|---:|---:|
| **A — near-tie** | 0 < gap ≤ 0.25 | 1,147 | **9.97%** | 1.277 |
| **B — mid-gap** | 0.25 < gap ≤ 1.5 | 4,936 | **42.90%** | 5.497 |
| **C — clear-gap** | gap > 1.5 | 5,422 | **47.13%** | 6.038 |

Both cuts are **closed on the upper edge** (`gap = 0.25` is A; `gap = 1.5` is B) — pinned by test
so the convention cannot drift. Supporting CDF over the non-tied class: `≤0.05` 1.16% · `≤0.10`
2.87% · `≤0.25` 9.97% · `≤0.50` 17.87% · `≤1.0` 40.08% · `≤1.5` 52.87% · `≤2.0` 61.89% · `≤3.0`
75.01% · `≤5.0` 87.08%. Mean `n_legal` = 27.55 (median 27, p90 43, max 88) — **"all legal arms"
is unaffordable and always was** (§3.1).

Phase is a **secondary** cut (`phase_bucket`, already on every census row); the realized
histogram is balanced enough to read without a quota (A: 350/407/390 · B: 1,635/1,723/1,578 ·
C: 1,427/1,977/2,018 early/mid/late). It is reported per stratum and is **never a branch input.**

### 2.3 Allocation — and the variance price of over-sampling A

Population weights `w = (0.0997, 0.4290, 0.4713)`. Proportional sampling would put only ~10% of
positions in stratum A. The committed allocation deliberately over-samples it:

**`f = (0.25, 0.375, 0.375)`** ⇒ at the SIZE-1 pool n = 450: **112 / 169 / 169**.
(At the unfunded n = 900 it would be 225 / 337 / 338 — the plan's own figure, pinned by test
including the leftover-seat tie-break, which goes to **C**.)

The pooled estimate is population-reweighted by the *known, exact* `w`, so it stays **unbiased**.
The variance price is `Σ wₛ²/fₛ` = **1.1229** vs 1.000 for proportional ⇒ **se inflated 1.0597×**
(both computed, both tested). That ~6% buys 2.5× the near-tie sample.
`f = (0.40, 0.30, 0.30)` was considered and **rejected**: it costs **1.17×** se for no branch
benefit (also computed and tested, so the rejection is checkable rather than asserted).

⚠️ **The 1.06 penalty is the price of REWEIGHTING THE POOL and belongs to the pooled se ONLY.**
A within-stratum se reweights nothing and carries **no** penalty. This is why §7.2's per-stratum
figures read 0.105 / 0.086 / 0.086 and not 1.06× those. The builder exposes the two as separate
functions (`se_kappa` / `se_kappa_stratum`) precisely so the distinction cannot be lost.

### 2.4 Position source, and the corpus-blindness property

- **Source:** [`../champ_action_logs/champ_games.jsonl`](../champ_action_logs/champ_games.jsonl)
  — 449 games, `gen = champion_fair_selfplay`, `k_dets=4`, `sims_per_det=688`,
  `total_budget_per_move=2752`, leaf `v2_9_2_Bmild_cap8_curve125`. Positions are reconstructed by
  **lossless `(deck_seed, actions)` replay**:
  `scripts/measurement_infra/root_replay.py::replay_actions(deck_seed, actions, ply) -> (game, board)`,
  which is policy-agnostic and ply-agnostic (the engine touches the global RNG only at the deck
  shuffle), so an arbitrary non-tied ply is a first-class replay target. See
  [`../../scripts/measurement_infra/README.md`](../../scripts/measurement_infra/README.md).
- ⭐ **BLINDNESS — the strongest property this design has.** Every priced corpus in this
  programme (`tiletie_pricing_20260812`, `tiearb_20260816`, `tiearb2_20260816`, the widening R4
  legs, the tie-net stage-0 labels) is **tied-ply-only**. **No non-tied ply of this file has ever
  been priced by any judge, by any estimator, on any menu pass.** The frame is unshopped in the
  strict sense — **no multiplicity is inherited**, and no dev/holdout split is needed to *buy*
  blindness. A holdout is carried anyway (§6.4), purely as a sign-consistency conjunct.
- **Cap 2 positions per game** (seeded) so the root-cluster design effect stays ≈ 1.0 — the
  tiearb corpus realized 733 positions / 399 roots at design effect ≈ 0.94. At n = 450 over 449
  games the realized cap is ≈ 1.0 positions/game (311 games touched, max 2).
- **Committed seeded permutation** (seed `20260823`), cut into sequential chunks by
  `build_everyply_plan.chunk_slices` — arithmetic copied verbatim from
  `build_tiearb_plan.chunk_slices` — so **every completed-chunk prefix is a uniform random
  subsample** and a partially-completed run is still readable at its realized `n`.
  ⚠️ Unbiased at **CHUNK** granularity only, never line granularity.

---

## 3. ARMS, JUDGES, AND THE INCUMBENT ASYMMETRY

### 3.1 The arm set — `K = 4`

Mean `n_legal` at a non-tied tile ply is **27.55**. Pricing all legal arms at M = 32 would cost
~2(27.55−1)×32 = **1,699 playouts/position** — ~9× the entire SIZE-3 budget. Unaffordable, and
also **not the deployable question**: a deployed every-ply arbiter would sit at the same
`pooled_q_argmax` root hook the Stage-2 arbiter sits at, arbitrating the search's own top
candidates.

```
arm[0..K-1] = top-K distinct-afterstate actions by the champion's own POOLED ROOT Q,
              from the SAME fresh production search that resolves the champion pick
champ_pos   = 0                                       (argmax pooled Q, by construction)
```

- **`K = 4` is not a new constant** — it is `J = 4`, the arm cap the whole tie-arbitration family
  has used since `tiletie_pricing_20260812`.
- **Coverage is 1.0 by construction.** The champion's pick *is* arm 0. Deliberate: `E-FLAT`'s 10×
  rung died partly on **coverage 0.799** (its pick left the scored set 19.5% of the time). That
  failure mode **cannot occur here**, and `G-COVER` gates it at 100%.
- **Dedup by successor board** (`string_representation`) via
  `scripts/tiletie/build_positions.py::dedupe_tie_actions` — at *tied* plies 80.5% of arms are
  afterstate duplicates. Positions left with < 2 distinct afterstates are **dropped and counted**
  (`G-DISTINCT`).
- ⚠️ **BUILD RISK, NAMED UP FRONT AND CONFIRMED BY INSPECTION.** The champion's pooled root stats
  come from `root_stats_list`, which **dedups children by node identity, so the played action is
  often absent from the pool** — the documented EV-loss-grader trap. Confirmed during this
  transcription: `scripts/tiletie/champ_picks.py` **exposes no pooled root Q at all** (it reads
  only `champ.manifest["fair_deploy"]`), so the pooled-Q extraction is genuinely new code, not a
  flag. The corpus stage therefore MUST (a) union the pooled ranking with `{champ_pick}`, (b) gate
  on `G-COVER`, and (c) carry a **pre-committed fallback**, declared here before any run:

  > **FALLBACK (pre-committed):** if the pooled ranking cannot be extracted reliably, arms =
  > `{champ_pick} ∪ top-(K−1) by LEAF value` from `chain_census.chain_values` (re-exported by
  > `scripts/tiletie/__init__.py`), which needs no root stats and costs ~4 ms/ply. The fallback is
  > **weaker** — it hands the arbiter the leaf's own shortlist — and **the read-out must state
  > which arm-builder ran, on every branch.** It still answers the owner's question.

### 3.2 The champion pick — and why it is not free

House precedent is explicit and it costs money: `scripts/tiletie/champ_picks.py` requires a
**fresh production search** at selfplay positions, because **CL-070 measured that reseeding alone
flips ~26–30% of picks at fixed budget** — the archived `action_played` is *a* champion pick, not
*the* champion pick. Budgeted at `t_champ` = **13.7552 s/position**
(`build_positions.DEFAULT_T_CHAMP_SECS`), bracketed to **25 s** at the top because that constant
is a **sequential, uncontended** measurement and Stage-2's §0.G showed equating sequential and
contended per-move walls is a category error.

⭐ **This re-search is also what makes the K=4 arm set free** — the pooled root Q ranking comes
out of the same search. The champion is whatever
`carcassonne_ai.champion_factory.make_production_champion("fair", …)` resolves from
[`../../governance/PRODUCTION.yaml`](../../governance/PRODUCTION.yaml) at run time, **read back
off the built agent's own manifest and stamped into every row, never hardcoded**
(`champ_picks.py`'s own convention). At drafting time that resolves to
`puct_priors_v29_bmild_cap8`, leaf `v2_9_2_Bmild_cap8_curve125`, `k_dets=8 × sims_per_det=1376 =
11008`.

⚠️ **The resolved champion has the tie arbiter ENABLED (`tiearb.enabled: true`, `B: 64`, `J: 4`,
`eps: 0.0`).** At a **non-tied** ply `detect_tie` is false at `eps = 0.0`, so the arbiter does not
fire and the incumbent pick is the plain pooled-Q argmax — but this is a *property being relied
on*, not an assumption: `G-CHAMP` stamps the resolved `tiearb` block on every row and requires it
constant, and the read-out prints it.

### 3.3 The arbiter

`tier1-greedy` (rust `carc_core::tier1`, `RuleBasedPlayer`, v1 object leaf, 1-ply argmax, **no
search**, played to terminal), argmax of the world-mean over the **16 selection worlds** — exactly
the deployed **B = 16**. Bit-exactness against the python definition of record is already proven
(`G-BITEXACT`, 15,360/15,360 value-bit-identical,
[`../tiearb2_stage2_20260817/PHASE_A.md`](../tiearb2_stage2_20260817/PHASE_A.md)).

⚠️ **B is NOT a resolved axis:** the `b32v64` cell read `EQUIV` FALSE / `U-UNREADABLE` at
`z_D` +1.38. **This probe fixes B = 16 and makes no B claim of any kind.**

### 3.4 ⚠️ THE INCUMBENT ASYMMETRY — the caveat that travels with every number

**The champion's pick IS one of the arms.** Therefore:

- The statistic is **capture-vs-incumbent** and it is **negative-capable**. `κ = 0` means *"the
  rollout arbiter is no better than the champion's own search"*, **NOT** *"there is no signal in
  the rollouts."*
- `κ` is **not zero-mean under "the arbiter is uninformative"** — an uninformative arbiter reads
  `mean-over-arms − champ`, which Stage-2 measured **strongly negative** (`RND` = −4.4287
  pts/game, **−60.09 elo**). That is why the `rnd` companion exists (§4.5) and why its absence
  from SIZE-1 is a named limitation.
- At a **tied** ply the champion's tie-break is the leaf's lowest-index rule — a near-arbitrary
  incumbent. At a **non-tied** ply the incumbent is an 11k-sim PUCT argmax. **The arbiter's
  opponent is categorically stronger here** — prior-against #2, restated as a property of the
  estimator rather than as an opinion.

---

## 4. ESTIMAND, STATISTIC, CURRENCY, BAR

### 4.1 The estimand

Notation follows [`../tiearb_20260816/DESIGN.md`](../tiearb_20260816/DESIGN.md) §4 verbatim.
`V^IF[p,a,j]` = terminal margin in final-score points at the root player's seat, position `p`,
arm `a`, CRN world `j = 1…M`, under **`clair-puct`** (production curve125 leaf, PUCT @ 100
clairvoyant sims, played to terminal on a known deck). `V^ARB` = the same physical quantity under
**`tier1-greedy`**, on **bit-identical world and playout seeds**.

For each parity fold `(sel, eva)` — `analyze_tiletie.parity_indices(M, base=1)` and its swap:

```
a_arb   = argmax_a  mean_{j in sel} V^ARB[p, a, j]      # ARBITRATION (tier1-greedy, B=16)
kappa[p]= mean_{j in eva} V^IF[p, a_arb, j]
        - mean_{j in eva} V^IF[p, champ, j]             # PRICING     (clair-puct)
```

symmetrized over the two folds. **PRIMARY:**

```
kappa  = SUM_s w_s * mean_{p in s} kappa[p]      [pts per NON-TIED tile ply]
z_kappa= kappa / se_cluster        cluster-robust on root_id (analyze_tiletie.cluster_robust)
```

⚠️ The census carries **no `root_id` field** (it keys on `game_id`). The cluster unit is therefore
**`root_id := game_id`** — the deck — declared here, before any run, so the clustering cannot be
chosen after seeing a number.

**Non-circularity is STRUCTURAL:** the arm is chosen by `tier1-greedy` on the selection worlds and
priced by `clair-puct` on the **disjoint** evaluation worlds. Selection and evaluation share
neither the judge nor the world. Cross-fitting is **not optional** — the two judges' values at the
same world are correlated through the shared deck, so pricing on all M would leak a winner's curse
through the deck draw.

### 4.2 ⚠️ `scale_all` DOES NOT APPLY — declared currency change

`scale_all` (the analytic-zero add-back) is the **tied**-ply population correction for *"positions
whose entire tie set collapses to one afterstate."* **There is no such degenerate class at a
non-tied ply** — the top arm is unique by construction. **`scale_all ≡ 1.0`.**

⇒ **`κ` is NOT directly comparable to the tied-ply `arb = +0.2065`**, which is a
`scale_all`-scaled number (its unscaled *discriminable* sibling is +0.2844).
**Every read-out must print this sentence** (READ_RULE §4.3 rail 5).

### 4.3 The elo chain — a BRACKET, calibrated on Stage-2, never a point

The ÷3.2 `NON_ADDITIVITY` constant is **n = 1 with a ±1.6× bracket**. Stage-2 supplies a
*measured* end-to-end mapping, and it says ÷3.2 was ~2.2× conservative:

| | |
|---|---|
| offline tied-ply `arb` | +0.2065 pts/tied ply |
| realized fire rate `phi` | 17.5 fired plies/game |
| ⇒ raw | +3.614 pts/game |
| **realized deck-paired margin** | **+3.0700 pts/game** ⇒ realized/raw = **0.849** |
| realized elo | **+23.92** [−0.21, +48.06] ⇒ **7.79 elo per pts/game** |

So the honest chain is a **bracket**, `NA ∈ [0.31 (÷3.2 prereg), 0.85 (Stage-2 realized)]`:

```
pts_per_game  =  kappa * 12.812 * NA          elo  ~=  7.79 * pts_per_game
```

| κ [pts/non-tied ply] | pts/game | elo image |
|---:|---|---|
| 0.10 | 0.40 – 1.09 | **+3.1 … +8.5** |
| **0.15** | 0.60 – 1.63 | **+4.6 … +12.7** |
| 0.20 | 0.79 – 2.18 | +6.2 … +17.0 |
| 0.35 | 1.39 – 3.81 | +10.8 … +29.7 |

⚠️ **The +23.92 elo Stage-2 headline MAY NEVER BE QUOTED BARE** — its winrate `z` is +1.94, below
2. **The margin convicts; the win-rate does not.** The same rider applies to every elo image
above, on every branch.

### 4.4 The fund bar — derived from the cell it would fund, not chosen

> **`κ* = +0.15` pts per non-tied tile ply, with `z_κ ≥ +2.0`.**

**Derivation.** The only thing a positive probe can license is a *DESIGN for* a deck-paired game
cell. Stage-2's realized game-cell precision at n = 800 paired is `se_D` = 0.933 pts/game on the
ARB−RND contrast and `se` = 0.691 on the single-cell margin ⇒ **an n=800 cell resolves ≈ 1.38
pts/game at 2σ.** Requiring the funded cell to be *resolvable* gives:

- under the **optimistic** (Stage-2-realized) chain `NA = 0.85`: κ ≥ **0.127**
- under the **conservative** (÷3.2 prereg) chain `NA = 0.31`: κ ≥ **0.347**

`κ* = 0.15` sits just above the optimistic requirement. **Therefore the read-out is REQUIRED to
print, mechanically, the implied game-cell size** `n_cell = 800 · (1.38 / pts_per_game)²` at both
NA ends — so an `E-FUND` firing at κ̂ = 0.16 **cannot** be mistaken for *"an n=800 cell will settle
it."* A second, cleaner threshold is carried:

> **`κ** = +0.35`** — an n=800 cell resolves it under **both** NA ends.

### 4.5 ⛔ §4.5 IS A BINDING SCOPE FENCE — the near-tie-only variant is arithmetically DEAD, before the probe runs

A natural fallback — *"arbitrate only where the leaf is nearly indifferent"* — is closed by the
mass desert, and this is free to state **now, at zero games**:

Stratum A carries **1.277 non-tied plies per game per seat**. For an n=800 cell to resolve an
A-only deployment under the conservative chain would need

```
kappa_A  >=  1.38 / (1.277 * 0.31)  =  3.49 pts per ply
```

The *tied*-ply oracle **ceiling** (`ora`) is **+0.2545**. A near-tie-only deployment would need a
per-ply effect **~14× the entire oracle headroom of the adjacent ply class.** (Both figures are
recomputed and pinned by test.)

⇒ **THE PROBE MUST BE SIZED ON THE FULL NON-TIED POPULATION OR NOT AT ALL.** Per-stratum reads are
for **mechanism interpretation only**. **No branch, no read-out, and no successor design may
rescue a pooled null by carving out a sub-population** — not stratum A, not a phase bucket, not a
`k_remaining` band. This is the census's `K-STRUCTURAL` finding cashed one step further: there is
**no cheap partial deployment hiding between "tied only" and "every tile."**

### 4.6 Companions — reported on every branch, never a branch input

| id | quantity | why | in SIZE-1? |
|---|---|---|---|
| `q` = `pickchg` | fraction where `a_arb ≠ champ`, per fold, pooled, per stratum | E-FLAT/W-FLAT's own diagnostic (*"moves picks without improving them"*), **and** the quantity that re-prices any powered top-up by ~2× | ✅ **YES** |
| `phi_nontied` | realized arbitrable non-tied plies/game after dedup | the deployed fire rate; feeds `rho_wall` for any successor | ✅ **YES** |
| `n_cell` | implied game-cell size at both NA ends (§4.4) | so no branch can imply an unfunded cell is cheap | ✅ **YES** |
| `arm_builder` | `pooled_q` or the §3.1 `leaf_topk` fallback | the read-out must say which instrument ran | ✅ **YES** |
| `n_distinct` rate | positions dropped for < 2 distinct afterstates | `G-DISTINCT`'s substrate | ✅ **YES** |
| `ora` | oracle headroom — arm selected by the **IF** judge's own selection-half argmax, priced on the disjoint half (`analyze_tiletie`'s `headroom_champ`) | the **ceiling** on κ. If the champion's PUCT pick is already at the oracle, no arbiter can pay. | ⛔ **NO — SIZE-3** |
| `F` | `κ / ora`, root bootstrap 20,000 reps | the cross-programme capture currency (E-FLAT 0.00/0.18/0.18, W-FLAT 0.11/0.26/0.09/0.09/0.30, tiearb 0.811). **Secondary** — this decision is absolute (§4.4), not fractional | ⛔ **NO — SIZE-3** |
| `rnd` | seeded random arm over `arm_order`, priced identically | **the null level** (§3.4); Stage-2 measured `RND` at −60.09 elo | ⛔ **NO — SIZE-3** |
| `arm0_leaf` | the **leaf's own argmax** as comparator | *at non-tied plies, does the champion's search even beat its own leaf?* | ⛔ **NO — SIZE-3** |
| `sel_agree` | fraction where `a_arb = a_ora` | selector quality independent of magnitude | ⛔ **NO — SIZE-3** |

⛔ **`SEC-ARB`** (the arbiter's picks priced by `tier1-greedy` itself) is **audit-only and circular
by construction** — its capture against its own headroom is 1 — and **may never be a branch
input.** Same status as [`../tiearb_20260816/DESIGN.md`](../tiearb_20260816/DESIGN.md) §4.3.

**⚠️ SIZE-1 buys NO ceiling and NO null level.** That is the price of the §5.2 selective economy
and it is a *named* limitation, not an oversight: `ora`, `rnd`, `arm0_leaf` and `F` are **not
computable at full n** under selective pricing, because they need arms the arbiter never selects.

---

## 5. COST — SIZE-1 ONLY

### 5.1 Unit costs — all realized on disk, none modelled

| quantity | value | conditions | source |
|---|---:|---|---|
| `c_IF` clair-puct **rust**, Stage-A realized | **1.5999** (2.24/1.69/0.80 early/mid/late) | W=14, 587 leg-records | `tiletie_pricing_20260812/STAGE_B_ADDENDUM.md` |
| `c_IF` clair-puct **rust**, widening committed | **2.35** | W=30 **contended** | `tiearb_widening_20260817/shared_run/DESIGN.md` |
| `c_IF` clair-puct **python** | 9.85–9.86 | e4 profiles — **EXCLUDED BY DESIGN** | `tiletie_pricing_20260812/SMOKE.md` |
| `c_ARB` tier1-greedy **rust**, committed | **0.178232** | W=30, `G-BITEXACT` 15,360/15,360 | `tiearb2_stage2_20260817/COST_REMEASURE.json` |
| `t_champ` champion re-search | **13.7552** s/position | **sequential, uncontended** | `build_positions.DEFAULT_T_CHAMP_SECS` |

Budget brackets: `c_IF ∈ {1.5999, 2.0, 2.35}`, `t_champ ∈ {13.76, 19.0, 25.0}` s,
`c_ARB = 0.178232` (the remeasure came in **cheaper** at 0.136–0.139, so this is one-sided
conservative), `m_sel = 2·(Ā−1) ∈ {1.8, 2.2, 2.6}`, `m_full = 2·(K−1) = 6.0`, `M = 32`.

Cost model — the repo's own, unmodified (`build_positions.py::cost_plan`, schema "DESIGN.md #7.1"):

```
playouts     = SUM_p 2*(A_p - 1)*M
worker_secs  = playouts * c   +   n * t_champ
wall_hours(W)= worker_secs / (3600 * W)
```

`c` is treated as **constant per playout in M** (seeds are `sha256("world"|rid|j|salt)`,
prefix-stable in M), so cost scales linearly in M. ⚠️ **No artifact on disk ties `c_IF` to
`--oracle-sims`**; 100 is the only value ever run for this backend and **no sims-scaling curve is
inferred here.**

### 5.2 ⭐ Selective pricing — the 2.19× saving, and why it is exactly unbiased

`κ[p] = 0` **identically** when both folds' `a_arb` equal `champ` — no clair-puct value is needed
to know that. So price, per position, only

```
arms_to_price(p)  =  {champ} UNION {a_arb(fold 1), a_arb(fold 2)}
```

Measured on the spent `tiearb_20260816` corpus (733 positions, mean 3.0 arms, fold agreement
0.508): `|arms_to_price|` = 1/2/3 for **174/448/111** positions ⇒ mean **1.914** ⇒ mean playout
multiplier `2(A−1)` = **1.828** vs **4.005** for full-arm pricing = **2.19× cheaper**. At K = 4 the
full multiplier is 6.0, so the saving is larger still.

Three properties, **gated not assumed**:

1. **Unbiased.** Un-priced positions enter the mean as **exact zeros** and enter `n` and the
   cluster structure. `G-ZEROFILL`: `n_priced + n_zero == n_analysed`.
2. **Non-circular.** `a_arb` depends only on `V^ARB`. **No clair-puct value influences which arms
   get priced.** The cross-fit is untouched.
3. **What it costs:** `ora`, `rnd`, `arm0_leaf` are not computable at full n (§4.6).

### 5.3 SIZE-1 line items and the total

Pool **450** · ARB all-K (M=32) · IF **selective** on n = **400** · **no `ora`**:

| line item | n | worker-h (lo / central / hi) |
|---|---:|---|
| corpus build — champion re-search + pooled-Q arm sets | 450 | 1.72 / 2.38 / 3.13 |
| ARB judge (tier1-greedy rust, all K=4 arms, M=32) | 450 | 4.28 / 4.28 / 4.28 |
| IF pricing — selective (§5.2) | 400 | 10.24 / 15.64 / 21.72 |
| frame query + replay + dedup | — | < 0.5 (negligible) |
| **TOTAL** | | **16.2 / 22.3 / 29.1** |

**Wall-clock at W=16: ≈ 1.0 / 1.4 / 1.8 h.** Every figure is emitted by
`build_everyply_plan.cost_table` and pinned by test against the plan's own headline.

**What SIZE-1 CAN do:** fire `E-HARM` (κ̂ ≤ −0.168); put a 2σ upper bound on κ (κ̂ + 0.168) — e.g.
it excludes a tied-ply-sized per-ply effect κ ≥ +0.25 whenever κ̂ ≤ +0.082; measure `q`,
`phi_nontied`, the distinct-afterstate rate and per-stratum **signs**; re-price a top-up exactly.
**What SIZE-1 CANNOT do:** convict `E-FUND`; park via `E-FLATNULL` unless κ̂ ≤ −0.018; resolve any
single stratum; produce `F`, the oracle ceiling, or the null level.

### 5.4 ⛔ SIZE-2 / SIZE-3 ARE NOT FUNDED AND NOT PRE-AUTHORISED

Priced here **only** so a later "just add n" ask does not re-derive it: SIZE-2 (pool 1,000, IF
selective n=900) ≈ **36.4 / 50.0 / 65.3** worker-h; SIZE-3 (SIZE-2 + full-K on an n₂=300
subsample, buying `ora`/`F`/`rnd`/`arm0_leaf`) ≈ **54.3 / 70.3 / 86.6** worker-h. Per the plan's
§8: the n=400 interim is **deliberately kill-only**, the top-up is cheap to add later on the
**same committed seeded order with no multiplicity cost**, and pre-authorising it would spend ~30
extra worker-h against a hypothesis the screen may already have killed. **A top-up needs a fresh
owner decision, re-priced by the measured `q`** (n ≈ 660 at q = 0.5, n ≈ 1,180 at q = 0.9).

> ⚠️ **AND A HARD SUPPLY CONSTRAINT THE PLAN DOES NOT STATE — found in transcription, recorded
> before it can bite a top-up ask.** The corpus is **449 games** and §2.4 caps positions at **2
> per game**, so the **maximum constructible supply is 449 × 2 = 898 positions.**
> **SIZE-2 as the plan states it (pool 1,000, priced n = 900) DOES NOT FIT — both exceed 898.**
> SIZE-1 (pool 450, priced 400) fits with room to spare. A funded top-up must therefore either
> raise the cap (degrading the root-cluster design effect the cap exists to protect, which
> inflates `se(κ)` beyond the §7.1 table it would be sized on), cap itself at n ≤ 898, or
> **generate new games — which owes a band claim** ([`BAND_NOTE.md`](BAND_NOTE.md) §4).
> **None of this affects SIZE-1.**

### 5.5 The box

**Assumed target: the LAPTOP** (`ssh laptop`), share **`/mnt/carc-shared`**, **W = 16**. The local
5900XT was censused **busy** at drafting time. ⚠️ The share mount path differs by box: local
commands use `/mnt/c/carc-shared`, anything inside an `ssh laptop` uses `/mnt/carc-shared`. The
launcher takes a role argument and never guesses.

---

## 6. THE PIPELINE — exact tools, and what is BUILT vs OWED

### 6.1 Stages

| # | stage | tool (exact address) | output |
|---|---|---|---|
| 0 | frame query, strata, seeded draw, holdout split, committed order, chunks | ✅ **BUILT** — [`../../scripts/tiletie/build_everyply_plan.py`](../../scripts/tiletie/build_everyply_plan.py) | `FRAME.json`, `HOLDOUT_GAMES.json`, `POSITION_ORDER.json`, `SELECTION.jsonl`, `PLAN_SUMMARY.json` |
| 1 | champion re-search + pooled-Q top-K arms + dedupe + leg files | ⛔ **OWED** — `scripts/tiletie/build_everyply_corpus.py` | `positions_chunk<k>/` (`POSITIONS_PLAN.json`, `ARMS.json`, `positions_<profile>_leg<r>.jsonl`) |
| 2 | ARB legs (all K arms) | ✅ reused — `scripts/tiletie/run_tiletie.py --judges tier1-greedy --arb-backend rust --m 32` | leg records under the share |
| 3 | IF legs (**selective** arm subset) | ✅ reused — `scripts/tiletie/run_tiletie.py --judges clair-puct --m 32 --oracle-sims 100` | leg records under the share |
| 4 | join, statistics, mechanical adjudication | ⛔ **OWED** — `scripts/tiletie/analyze_everyply.py` | `READOUT.md`, `READOUT.json`, `per_position.jsonl` |

Leg records are written by `scripts/measurement_infra/oracle_score_pilot.py::_process`, which is
where `crn_verified`, `checksum_ok`, `world_seeds` and `playout_seeds` originate; cross-leg
identity is verified by `scripts/tiletie/run_tiletie.py::verify_leg_records`. `run_tiletie.py`
launches that pilot as a subprocess — **it has no `--shared-claim` flag**; resumability is
`--resume` (default true) at `records/<rid>.json` granularity, plus the launcher's per-chunk
`DONE_CHUNK<k>` sentinels.

### 6.2 Estimators — imported UNMODIFIED, never re-implemented

`scripts/tiletie/analyze_tiletie.py` is the module of record for
`parity_indices`, `crossfit_regret`, `cluster_robust`, `bootstrap_roots`, `aggregate`,
`zero_rates`, `load_plan`, `discover_records`, `pts_to_elo`, `bound_block`.
`analyze_everyply.py` **imports them via the house `sys.path` pattern and must not fork any of
them** — the same contract `analyze_tiearb.py` states in its own docstring.

⚠️ **`probe_pickers.py` CANNOT be run unmodified on this corpus.** Its `grade`, `preflight` and
`sweep` subcommands call `require_knowngood` (`probe_pickers.py:677`) **unconditionally** against
hard-pinned `N_POSITIONS_OF_RECORD = 733` / `N_ROOTS_OF_RECORD = 399` / `KNOWNGOOD_TOL = 1e-9`
read off `measurement/tiearb_20260816/READOUT.json`, so a new corpus **fails by construction**.
⇒ Run `probe_pickers.py knowngood` as a **separate gate** (`G-KNOWNGOOD`, READ_RULE §3) and import
the estimators directly. **Do not fork the pinned constants.**

### 6.3 The two OWED builds — scoped, addressed, and gating

**Neither may be built in the MAIN TREE while a run is live.** A `reconcile_backend` run was live
at drafting time and `measurement/tiearb2_stage2_20260817/RUN_LIVE.json` exists, so
`build_everyply_plan.py` and its tests were added as **NEW FILES ONLY** — nothing existing was
edited, because spawn respawns and new cells re-import from disk. The same rule binds the two
builds below: **new modules, no edits to `build_positions.py` / `champ_picks.py` /
`analyze_tiearb.py`.**

| build | ~LoC | notes |
|---|---:|---|
| `scripts/tiletie/build_everyply_corpus.py` | ~180 | consumes `SELECTION.jsonl`; replays via `root_replay.replay_actions`; one fresh `make_production_champion("fair", …)` search per position with `mirror_protocol.reseat` (the `champ_picks.champion_search_pick` shape); extracts pooled root Q **with the `root_stats_list` dedup trap handled** and the §3.1 leaf-top-K fallback; reuses `build_positions.dedupe_tie_actions`, `_seeded_cap`, `build_arms_index`, `write_leg_files` (all four are shape-agnostic — only `build_tie_arms` carries the two tie asserts, which is why it is NOT reused) |
| `scripts/tiletie/analyze_everyply.py` | ~300 | `scale_all ≡ 1.0`; population reweighting by the exact `w`; zero-fill accounting; the READ_RULE §4 branch table, mechanically |
| tests | ~250 | zero-fill identity, reweighting, arm-set coverage, and a golden that reproduces `arb = 0.2065` through the shared estimators |

**No rust change is required.** `carc_core::tiearb::build_arms` is already candidate-list agnostic
(only `detect_tie` is tie-specific), but this probe is entirely offline and uses the python
arm-builder; a rust PyO3 surface would only be needed by a *deployed* every-ply arbiter — i.e.
after a positive game cell that this design does not license.

### 6.4 Holdout

**25% of ROOTS (games)** reserved by seeded split (`split_games`, seed `20260824`) **before any
position is drawn and before any leg runs** — realized 108 of 450 positions, and **no game
straddles the boundary** (pinned by test). It enters `E-FUND` **only** as the blind
sign-consistency conjunct `κ̂_holdout ≥ 0`.

⚠️ **The precedent is also the warning.** `tiearb`'s pooled read fired every conjunct **except**
`C_h` and landed `P-PARTIAL` on a holdout of **−0.0051** — a 211-position holdout its own DESIGN
§4.4 had already shown could not convict even a 100% capture. **Here the holdout is ~108
positions, so the same limitation applies with less power, and THE BRANCH INPUT IS THE POOLED
READ** — declared now, not after the fact.

---

## 7. POWER AND REACHABILITY — arithmetic BEFORE any number

### 7.1 Dispersion

Realized per-position dispersion, **recomputed from
[`../tiearb_20260816/per_position.jsonl`](../tiearb_20260816/per_position.jsonl)** (733 rows, not
projected): `sd(arb) = 1.5819` at `q = 0.7626` ⇒ **per-changed-position sd = 1.8115**; cluster
design effect **0.94** (use 1.0). With the §2.3 stratification penalty **×1.06**:

```
se(kappa)  =  1.06 * 1.8115 * sqrt(q) / sqrt(n)
```

| n | q = 0.50 | q = 0.76 | q = 0.90 |
|---:|---:|---:|---:|
| **400** (interim + SIZE-1 read) | 0.068 | **0.084** | 0.091 |
| 450 (pool) | 0.064 | 0.079 | 0.086 |
| 600 | 0.055 | 0.068 | 0.074 |
| *900 (unfunded)* | 0.045 | 0.056 | 0.061 |

⚠️ **SHARPENED:** the plan prints per-stratum se figures (0.105/0.086/0.086 at n=900) that are
**inconsistent with a literal reading of the ×1.06 formula** — they are computed **without** the
penalty. That is correct, and §2.3 now says why: the penalty prices pooled reweighting, not a
within-stratum mean. No bar moves; the formula is simply now unambiguous about which se it is.

### 7.2 Reachability of every headline branch, at the planning-central `q = 0.76`

| branch | fires when κ̂ … | n = 400 |
|---|---|---|
| `E-HARM` | ≤ −0.15 **and** z ≤ −2 | κ̂ ≤ **−0.168** ✅ reachable |
| `E-FUND` | ≥ +0.15 **and** z ≥ +2 | κ̂ ≥ **+0.168** ✅ reachable — **but the interim may not fire it** |
| `E-CLEAN` | ≥ +0.35 **and** z ≥ +2 | κ̂ ≥ **0.35** ✅ reachable |
| `E-FLATNULL` | `UB95(κ̂) < +0.15` | κ̂ < **−0.018** ⚠️ **marginal** |

**No unreachable headline branch.** Every cell above is reproduced by
`build_everyply_plan.se_kappa` and pinned by test. **Two honest limits, stated before the run:**

- ⚠️ **`E-FLATNULL` is MARGINAL at n = 400.** The screen can park the lever only if κ̂ comes in
  **at or below −0.018** — essentially at or below zero. That is the *expected* case under all
  three priors, but it is **not guaranteed**, and **this screen must never be sold as "it will
  settle it either way."**
- ⚠️ **The screen CANNOT convict the fundable effect.** At n = 400 a true κ = +0.15 reads
  **z = 1.79**. A positive verdict needs a top-up that is **not funded**. **This is a
  kill-oriented screen** — good power against the prior-favoured hypothesis (harm), poor power
  against a modest gain.

**Per-stratum se at the SIZE-1 pool** (112/169/169, `q = 0.76`, **within-stratum, no penalty**):
**0.148 / 0.121 / 0.121**. Every per-stratum number is therefore **a sign read at best**, is
labelled underpowered, and is **never a branch input** except through `E-FUND`/`E-CLEAN`'s
sign-consistency conjunct.

---

## 8. THE BAND — none is owed

**NO deck band is consumed, NO `governance/BAND_REGISTRY.csv` row is claimed, on any branch.**
Every position is an **offline replay** of the already-claimed, already-**retired** band
**28000000000**, whose registry note states the governing precedent verbatim: *"Roots from this
band are replayed by opponent-free instruments (no new band consumed)."* No self-play generation
happens anywhere in this design. Full reasoning, including the condition under which a band
**would** be owed: [`BAND_NOTE.md`](BAND_NOTE.md).

---

## 9. HONESTY RAILS — printed on EVERY read-out, verbatim

Binding text: [`READ_RULE.md`](READ_RULE.md) §4.3. Summarised here:

1. **PRIOR-AGAINST 1 — the mass desert** (`K-STRUCTURAL`): no gentle widening exists between
   exact ties and eps ≈ 1.5–2.0. **The plies this probe adds are ones where the leaf has a real
   opinion.**
2. **PRIOR-AGAINST 2 — "the vart":** 2×/4×/10× more search **moves** tied-ply picks (18/24/31%)
   but does not **improve** them. The tie-arbiter's win is an **orthogonal terminal-grounded
   signal breaking a ply where the primary signal is exactly ZERO.** At a non-tied ply it must
   instead **beat an 11,008-sim PUCT search, not silence.**
3. **PRIOR-AGAINST 3 — the `RND` control:** −4.4287 pts/game, **−60.09 elo**. A leaf-tied set is
   **not** a set of interchangeable moves. The greedy-continuation values carry policy bias that
   is common-mode across arms **only when the primary signal is silent** — exactly the condition
   this probe removes.
4. **INCUMBENT ASYMMETRY** (§3.4).
5. **CURRENCY** (§4.2) — `scale_all ≡ 1.0`; κ is **not** comparable to `arb = +0.2065`.
6. **⚠️ OFFLINE CAPTURE HAS UNDER-READ THE GAME CELL ON THIS EXACT AXIS** (§10 item 6).
7. **BUDGET-EPOCH MISMATCH** (§10 item 5).
8. **NO DEPLOY IS LICENSED ON ANY BRANCH** (§10 item 7).
9. **`SEC-ARB` is circular by construction** and may never be a branch input.

---

## 10. WHAT THIS CANNOT SHOW — stated before launch so no branch can be narrated past it

1. **It is not a game cell and licenses none.** The best possible outcome (`E-CLEAN`) licenses a
   **DESIGN for** one deck-paired cell, which is a separate owner decision.
2. **It resolves nothing about `B`.** B = 16 is fixed; the `b32v64` cell already read
   `U-UNREADABLE` at `z_D` +1.38.
3. **It prices no `--oracle-sims` or `M` axis.** M = 32 and 100 clairvoyant sims are the only
   values any artifact on disk prices.
4. **It carries no oracle ceiling and no null level** (§4.6) — so it cannot say whether a null κ
   means "no headroom" or "headroom the arbiter cannot capture."
5. **BUDGET-EPOCH MISMATCH.** The corpus *games* were generated by the k4×688 / 2752-budget
   champion; the *incumbent priced* is whatever `PRODUCTION.yaml` resolves at run time
   (k8×1376 = 11008 at drafting). Inherited verbatim from `tiletie_pricing_20260812`.
   ⚠️ **SHARPENED:** `champ_games.jsonl` stamps `leaf_hash_runtime = 6dfffd57051690f2`, which is
   **not** a different leaf — it is the `frozen_config_hash_meeple_k0` **dialect** of the same
   `v2_9_2_Bmild_cap8_curve125` whose harness dialect is `a36d2e15a3b3d71d`. `G-EPOCH` therefore
   **must name the dialect it reads**, or it fails on a healthy run (§11).
6. **⚠️ OFFLINE CAPTURE HAS UNDER-READ THE GAME CELL ON THIS EXACT AXIS.** At tied plies the
   offline instrument returned `P-PARTIAL` — *not convicted*, with a **negative blind holdout**
   (−0.0051) — and the Stage-2 game cell then fired `G-CONFIRMED` at `z_D` **+8.04**.
   ⇒ **`E-FLATNULL` IS A FUNDING VERDICT, NEVER AN EXCLUSION**, in the same words `W-FLAT` and
   `F-FLAT` used. **An offline null here does NOT prove the deploy effect is null; it proves we
   will not spend a game cell on it.**
7. **NO DEPLOY IS LICENSED ON ANY BRANCH.** `rho_phone` = 5.520 at B=16 is **unsolved** for the
   *tied-ply* arbiter already; every-ply arbitration roughly doubles the fire rate (12.81 non-tied
   plies/game/seat added to a realized `phi` of 17.5) and therefore roughly doubles it again.
   **Desktop-only at best, and not licensed here.**
8. **It is a `walled`-rules instrument.** Only `walled` may use the rust clair-puct path
   (`run_tiletie.RUST_OK_PROFILES`); the deployed champion runs `fixed_v1`. E4 positions are
   **excluded by design** — the python path is 5× the cost for 8% of the supply.
9. **It cannot rescue a pooled null by sub-population** (§4.5, binding).

---

## 11. INTEGRITY GATES

Each is a PRECONDITION; any FAIL ⇒ `U-UNREADABLE` and **no branch may fire**. This section is the
summary — [`READ_RULE.md`](READ_RULE.md) §3 is the **binding** text and carries the tool+address
for each, plus the §3.1 structural test applied to every one of them before launch.

`G-KNOWNGOOD` · `G-CRN` · `G-COVER` · `G-ARMSET` · `G-ZEROFILL` · `G-DISTINCT` · `G-FRAME` ·
`G-N` · `G-EPOCH` · `G-CHAMP` · `G-BLIND`.

---

## 12. THE PILOT (pre-blind, mandatory, ~10 minutes)

**20 positions drawn from chunk 1's head**, run through stages 1–3 at production knobs.

**It reads ONLY:** wall-clock, `elapsed_secs`, `n_ok`, `n_failed`, `crn_verified`, the
world/playout-seed identity witness, `n_distinct_afterstates`, the champion-arm coverage count,
and which arm-builder ran. **It does NOT read `values_a`, `values_b`, `per_world_delta`, `mean_a`,
`mean_b`, `delta`, any sd, `κ`, `q`, or any statistic derived from them.**

**Pre-committed mechanical rule** (no owner call, no judgement):

1. `n_failed > 0` **or** any `crn_verified` false **or** any world/playout-seed mismatch **or**
   champion-arm coverage < 20/20 ⇒ **ABORT.** Nothing further launches; the read-out is a
   `U-UNREADABLE` harness report and the corpus stays unspent.
2. Otherwise let `c = Σ elapsed_secs / playouts` and `H = (SIZE-1 playouts) · c / (3600 · 16)` the
   projected wall-hours at W=16.
   - `H ≤ 3.0` ⇒ **launch all 4 chunks**;
   - `H > 3.0` ⇒ launch the first `ceil(4 · 3.0 / H)` chunks, **floor 2** — every completed chunk
     is still an unbiased subsample (§2.4).
3. If the pooled-Q extraction failed, the §3.1 **leaf-top-K fallback** engages **once**, here, and
   is **FROZEN and STAMPED** before any further leg runs.

⛔ **The pilot is the ONLY place a knob may move. After the blind commit, nothing moves.**

---

## 13. CLOSE-OUT (on adjudication, not before)

The six-touch checklist, verbatim from `CLAUDE.md`: (1) **no** `experiments/results.csv` row —
this probe produces no strength claim and no elo (its read-out is the record) · (2) `DECISIONS.md`
index line · (3) status stamp on this `DESIGN.md` and on `READ_RULE.md` · (4) governance row flip
— **`LEVER_INDEX` row *"every-ply rollout arbitration"* moves off NAMED, NEVER TRIED to whatever
branch fired**; `BAND_REGISTRY.csv` is **untouched** (§8) · (5) `STATUS.md` top block · (6) the
roadmap's every-ply line in
[`../../docs/PROGRAM_ROADMAP_2026-07-07.md`](../../docs/PROGRAM_ROADMAP_2026-07-07.md).
Then `python3 scripts/doc_lint.py`. Commit; do not push without asking.
