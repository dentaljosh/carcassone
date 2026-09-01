# PREREG — the 44032 budget rung (`budget44k_prep`)

> **STATUS: FROZEN, UNLAUNCHED.** 0 real games exist. No band claimed, no
> `governance/` file touched, no `experiments/results.csv` row written, no
> source change. `BLIND_COMMIT.json` reads `PENDING` until the freeze commit's
> sha is stamped by a mandatory second commit.
>
> **Owner funding, verbatim (2026-09-01): "fund 44k at w30."**
> → the **LOCAL** box at **W = 30**, an explicit owner override of the standing
> `W = logical threads` default (local 32). See §6.1.

**The pair is law.** This document and
[`screen_lib.py`](screen_lib.py) / [`adjudicate_budget44k.py`](adjudicate_budget44k.py)
/ [`launch_budget44k.sh`](launch_budget44k.sh) / [`test_budget44k.py`](test_budget44k.py)
are frozen together. If the code disagrees with this document, **the code is
wrong**.

---

## 1. The question, and why it is asked now

The fleet wheel roll-in (flattening + follow-ons A + the L2 exact-solver swap,
[`measurement/wheel_rollin_20260901/README.md`](../wheel_rollin_20260901/README.md))
made the deployed champion **~2.2× faster**: `2.433 s/move` re-measured at the
deployed `k16 × 1376 = 22016` with the tie-arbiter armed on both seats,
governance-grade, now stamped into `governance/PRODUCTION.yaml`
`deploy_profiles.desktop.measured_s_per_move`.

That speedup pays for exactly **one more budget doubling at roughly the OLD
wall-clock**: 44032 costs ≈ 4.9 s/move against the ≈ 5.38 s/move the program
already tolerated pre-swap. So for the first time on this ladder the question
**"should `champion.fair_deploy` flip to 44032?"** is *nearly clock-free*.

Two sub-questions, and the program can only afford to power one:

1. **Does the doubling pay at all** against the deployed 22016 champion?
2. **At which allocation?** `governance/PRODUCTION.yaml` says so itself: the
   deployed `k16 × 1376` is *"the measured-positive cell's allocation"*, **not**
   a solved optimum, and *"width must be re-solved per budget."*

### 1.1 What is already known, and what is not

| Rung | `experiments/results.csv` row | Result |
|---|---|---|
| 2752 → 11008 — a **4×** jump moving **width AND budget together** | `cl060_h2h_k8x1376_vs_deploy_k4x688` (band 32e9, n=400 = 200 decks × 2) | `+49.85 elo`, **`+2.9775 pts/deck`**, `paired_z 3.48` |
| …its fixed-width decomposition (budget alone, k4 both sides) | `cl060_budget_k4x2752_vs_deploy_k4x688` (band 44e9, n=400) | `+27.85 elo`, **`+2.24 pts/deck`**, `paired_z 2.24` |
| 11008 → 22016 (`k8×1376` → `k16×1376`) — **the only true doubling** | `h2h22016_k16x1376_vs_champ_k8x1376_n700decks_b148e9_AMENDED` | `D = `**`+1.2293 ± 0.48784`**, `z +2.52`, `elo +14.2`, W714/D29/L657, branch `H-POSITIVE`; promoted 2026-08-30 (owner: *"yes, desktop champ becomes 22k"*) |
| 22016 → **44032** | — | **never measured, at either allocation** |

⚠️ **Two riders travel with the `+1.2293` anchor, and this round launders
neither:**

1. **Type-M** — the row's own note: *"Type-M: below own MDE ±1.55 so magnitude
   inflated."* The realized value sits *below* that cell's 80 %-power MDE, so
   its **sign is reliable and its magnitude is biased upward**.
2. **Provenance** — that round's **frozen adjudicator returned
   `U-UNREADABLE`** (two archive-independent instrument defects, `G-REV` /
   `G-TIEARB`). `+1.2293` is an **owner-authorized post-void re-read** of the
   same archive under amended gates, **with the diagnostic `z` visible before
   authorization** (`measurement/h2h_22016_prep/AMENDMENTS.md`). The same row
   also records *"deploy NOT licensed (2.00× wall)"* — the promotion came
   later, by a separate owner ruling.

Both push the same way: **the anchor is softer than its point estimate looks.**

**The width axis** (`docs/LEVER_INDEX.md`, `governance/CLAIM_REGISTRY.csv`):

* **CL-054** (@ fixed budget 2752): an **inverted-U in `k` peaked at k4** —
  ordering `k32 < k16 ≈ k8 < k2 < k4`, with **`k32×86` reading `−6.28`,
  `z −3.55` (significantly worse)**. *Promoted, confidence high.*
* **CL-060 / DECISIONS 2026-07-23**: *"Peak NOT bracketed above k16 (k32+
  untested; CL-054's inverted-U predicts it would hurt.)"*
* CL-060's own item-3 close-out, the one **properly powered fixed-budget width
  contrast** (`k4×2752` vs `k8×1376` at 11008, n=800 paired): `−19.56 ± 12.30
  elo`, `z −1.487` → **BOUNDED NULL**, *"the width axis at fixed 11008 CLOSES
  as unresolvable at affordable n; bound ±22 elo."*
* At 22016 on band 48e9 the two allocations read `k16×1376` **+35.58 elo**
  (`z 2.68`) versus `k8×2752` **+3.51 elo** (`z 0.21`) — directionally
  width-favouring, but each row carries `σ ≈ 24.9`, so their difference is
  `z ≈ 0.9`: **not a resolved contrast.**

**Net:** the width axis is **unresolved at every budget above 2752**, and the
only *resolved* measurement of it (at 2752) **favours narrow**. `k > 16` has
**never** been measured at any budget above 2752.

### 1.1b ⭐⭐ Two live families, disagreeing by ~4.5×, and that is the reason to run this

`docs/LEVER_INDEX.md`'s budget-headroom row now carries **two** answers to
"what is a further doubling worth?", and they do not agree.

**Family A — the decay-RATE family.** Fit the per-doubling decay of an
*opponent-free* statistic (CL-070's budget-attributable disagreement `Δ`, no
opponent, no elo, no ruler in the loop) across all five adjacent doublings
(`Δ = 0.0866 / 0.0497 / 0.0287 / 0.0173 / 0.0206`): **`r = 0.675 ± 0.057`**,
95 % CI [0.573, 0.796], reproduced in the narrow-gap stratum at 0.642. Both
fits **exclude 1.0** ⇒ the tail converges. One more rung on the last realized
effect: `0.675 × 1.2293 =` **`+0.830 pts/deck`**.
*Its own asterisk:* the one adjacent ratio measured **at** the extrapolation
point has **`r₄ > 1`** (`Δ₄ 0.0173 → Δ₅ 0.0206`) and the row calls that half of
the anomaly **real** — the rate did **not** keep decaying at the top rung.

**Family B — the measured-PRICE family, and it is the CURRENT bound.**
⛔ **The familiar "≈ +54 elo remaining headroom above 11008" figure is
SUPERSEDED.** It rested on a price of `+0.7375 pts/disagreement` measured on
**one** pair. A powered re-measurement (150/150 ok, 126 roots, cluster-robust)
put the price at **`+0.0673`** (`se 0.2041`, `z +0.330`; bootstrap 95 % CI
`[−0.3300, +0.4668]`) ⇒ the pre-registered `price ≪ 0.2` branch **fired, and
powered, not underpowered**: the memo's own point prediction (0.511) would have
read `z = 2.5` at the realized `se`, and the bootstrap CI's *upper* bound sits
**below** it, so *"the bound stands"* is **excluded at ~95 %**. The restated
chain (only the price replaced): `P_signal 0.591`, **`g_next = +0.1837
pts/game`**, `H = +0.5652 pts/game` ⇒ **≈ +7.1 elo (σ 22.2), honest bracket
≈ [−35, +49] elo, spanning zero.** `H` is the **whole remaining tail above
11008**, summed over *all* further doublings.
Mechanism the row names: *"the decay moved from the RATE into the PRICE …
above 5504 the deeper pick MOVES but does not IMPROVE."*

**The tension, stated plainly.** The single 11008 → 22016 rung then measured
**+1.2293 pts/deck (≈ +14.2 elo) on its own — larger than family B's entire
remaining tail.** That is a ≈ 6.7× out-of-sample miss, and the LEVER_INDEX row
itself logs it as one of two such misses.

> **So family A predicts ≈ +0.83 for this rung and family B predicts ≈ +0.18.
> Nothing in the tree adjudicates between them, and only a direct
> deployed-vs-deployed head-to-head can. That is what this round is.** It is
> also why `BAR_M` is set where it is (§4.3).

### 1.2 CL-070, cited so nobody reaches for the wrong ruler

`governance/CLAIM_REGISTRY.csv` **CL-070**: the RoD-v2 anchor **cannot price
budgets above 2752** — it mis-orders a +50 elo contrast *including the sign* —
*"so stop buying budget rungs graded against it."*

**It is irrelevant here** and is cited only so a later reader does not "improve"
this round by re-grading it against that anchor. This design is
**deployed-vs-deployed direct head-to-head play** — the instrument class the
`fpu_h2h` / `fpu_h2h_r2` / `fpu_swap_cell` rounds battle-tested — and never
touches RoD-v2.

---

## 2. The instrument

| | Candidate | Opponent |
|---|---|---|
| agent | production champion, `fair-champion` | production champion, `fair-champion` |
| budget | **44032** (allocation per cell, §3.1) | **`k16 × 1376 = 22016`** (`governance/PRODUCTION.yaml` `champion.fair_deploy`) |
| flags | `--k-dets` / `--sims` | `--opp-k-dets` / `--opp-sims` |
| tie-arbiter | **ARMED** `B=64 J=4 argmax salt=tiearb2-deploy-v1 eps=0.0 phase_gate=all` | **ARMED**, identical |
| leaf | `a36d2e15a3b3d71d` | `a36d2e15a3b3d71d` |
| endgame | `exact_k 2`, `marginalized`, shared by both arms | same |
| rules | `fixed_v1`, `CARCASSONNE_FIX_R9=1` (env-latched at import) | same |
| backend | `rust` | `rust` |

**The candidate's total per-move budget is the ONLY variable.** Everything else
is byte-identical across the two seats.

### 2.1 The opponent-side budget flags — VERIFIED, not assumed

The brief required this be checked before assuming. It was, at build time,
against `scripts/classical_search/eval_fair_puct.py`'s argparse:

* `--k-dets` (default 4) and `--sims` (default 688) — **candidate side**.
* `--opp-k-dets` (default `None`) — *"ASYMMETRIC determinization COUNT: the
  head-to-head opponent runs THIS many determinizations per move while the
  CANDIDATE keeps `--k-dets` … Default None = the opponent uses the shared
  `--k-dets` (SYMMETRIC head-to-head, byte-identical to today)."*
* `--opp-sims` (default `None`) — the sibling for sims-per-determinization.

⛔ **The silent failure mode this creates, and the gate that catches it.**
Omitting the `--opp-*` pair does **not** error: the opponent inherits the shared
`--k-dets`/`--sims` and the cell quietly becomes a **44032-vs-44032 null** that
looks perfectly healthy from the outside. `G-BUDGET` and `G-BUDGET-RATIO` (§5)
read the **emitted manifest** — never the launcher's intent, never the dirname —
and additionally require the *second, independent witness*
`summary.asymmetric_budgets == true` plus its `candidate_*` / `opp_*` triples to
**agree with the manifest**.

### 2.2 Both seats armed

The arbiter is worth ≈ **+66 elo** on its own (`tiearb_widening` B64 row,
measured at `k8×1376`). A cell with the arbiter on one seat only would swamp the
budget effect entirely. `G-TIEARB-SIDES` asserts both seats carry
`tiearb_gates.DEPLOYED_TIEARB_B64` **exactly** (all seven spec keys; a missing
`phase_gate` is a FAIL, never a default), and `G-TIEARB-FIRED` is the
**both-armed positive control**: each seat's realized `fired_plies` must be
non-zero in *play*, not merely requested in *config*.

---

## 3. The design

### 3.1 Two cells, one common opponent, one band

| Cell | Role | Candidate allocation | n decks | n games | chunks |
|---|---|---|---|---|---|
| **`CELL_K32`** | **PRIMARY (powered)** | `k32 × 1376 = 44032` — *double WIDTH at the deployed depth* | **800** | 1600 | 4 × 200 decks |
| `CELL_SIMS` | SCREEN | `k16 × 2752 = 44032` — *double DEPTH at the deployed width* | **400** | 800 | 2 × 200 decks |

Both play the **same** opponent (`k16 × 1376 = 22016`), on the **same** band.
Decks are seat-balanced and deck-paired (`--paired`: `--n` is GAMES, and the
harness's `_build_work` yields `n//2` decks × 2 seatings).

* primary decks: `band + 0 … band + 799`
* screen decks: `band + 0 … band + 399` — a **strict prefix subset**

### 3.2 Why `CELL_K32` is the powered primary

1. **It is the ladder-precedent candidate.** Every promoted budget step since
   2752 has **pinned `sims_per_det` at 1376 and doubled `k`** (`k4×688` →
   `k8×1376` → `k16×1376`). `k32×1376` is therefore what the program would
   deploy *by default*; `k16×2752` is the departure. The powered cell should
   test the config that would actually be shipped.
2. **It is where the standing negative prior lives, and power belongs where
   the answer is uncertain and consequential.** CL-054's inverted-U says `k32`
   was *significantly worse* at 2752 and that `k>16` was never bracketed. If
   that bites at 44032, the candidate can be **worse than the 22016 incumbent
   despite double the budget** — a genuinely decision-changing possibility
   nobody has measured.
3. **A `B-REGRESSION` on this cell is the only result in the round that can
   CLOSE the width ladder** — and it is the one result a 400-deck screen could
   easily leave unresolved (§4.4: a `−1.0` regression fires `B-REGRESSION`
   **51.9 %** of the time at n=800 but only **29.1 %** at n=400).
4. `CELL_SIMS` carries **no standing negative prior** and is the
   minimal-change candidate, so a screen is the proportionate spend. If it
   screens strongly positive while the primary does not, that is a **named
   re-open trigger** for a separately funded powered round (§7), never an
   automatic action.

### 3.3 Why ONE band, and the price of it

Sharing a band with the screen's decks a **prefix subset** of the primary's
makes the §4.5 width contrast a **within-band, deck-matched difference** — the
*robust* class under the standing cross-band ~2× humility rule (CLAUDE.md;
CL-068). Two bands would have made that contrast a cross-band one, i.e. exactly
the class the rule tells us to distrust, and would have retired two bands
instead of one.

⛔ **The price, stated rather than left implicit:** the two cells are **NOT
independent replications**. A pathological deck draw moves both the same way.
Therefore **neither cell's branch may be read as a replication of the other's**,
and no cross-cell pooling of any kind is permitted on any branch.

### 3.4 Chunked and resume-friendly

Each cell is played as **independent, disjoint 200-deck (400-game) blocks**,
each with its own out-dir, `manifest.json`, `summary.json` and `DONE` marker
(the `fpu_h2h_r2_prep` flexible-round pattern). The launcher **skips any chunk
already marked `DONE`**, so an interrupted round resumes without re-play and
without double-counting. There is **no pooled `summary.json` on disk**: every
pooled statistic in the adjudicator is recomputed from the raw `seed*_a*.json`
records and reconciled chunk-by-chunk against each chunk's own summary
(`RECON`).

Three gates exist *only* because the round is chunked:

* **`G-CHUNKS`** — every planned chunk exists, carries both documents, is
  `DONE`. (A chunked round's characteristic failure is a silently short pool:
  four chunks planned, three on disk, every per-chunk gate green.)
* **`G-SHARD-IDENT`** — every chunk resolved the *same two agents*: same wheel
  sha, same leaf hashes, same budget triples, same rules profile, same
  `code_rev`, same `BLIND_COMMIT`. A chunked round can straddle a wheel
  rebuild or a re-pin; pooling across one makes a mixed-era cell.
* **`G-NODUP`** — chunk seed ranges pairwise disjoint and every `(deck, seat)`
  appears **exactly once**. A resume that re-ran a chunk instead of skipping it
  would otherwise double-weight those decks and silently *tighten* the SE.

### 3.5 What is NOT in scope

* ⛔ **Mobile / phone budget.** `deploy_profiles.mobile` stays `k16×1376 =
  22016`. See §7.3.
* ⛔ Any allocation other than the two named (no `k64`, no `k8×5504`, no
  intermediate rungs).
* ⛔ Any source change. This round adds no flag and touches no `src/`,
  `engine/`, `rust/` or `scripts/classical_search/` file.

### 3.6 Alternatives considered and declined

| Alternative | Why declined |
|---|---|
| **`CELL_SIMS` as the powered primary** | The honest counter-case, recorded so it can be overruled before the freeze is stamped: it is the *minimal change*, holds the measured-good width fixed, and has the higher prior probability of a clean `B-ADOPT`. It was declined on §3.2 (2)–(3): putting the power on the *safe* allocation and the screen on the *risky, never-measured* one allocates information backwards. **If the owner prefers this ordering, swap `PRIMARY_CELL`/`SCREEN_CELL` and the two `n_decks` in `screen_lib.py` BEFORE stamping `BLIND_COMMIT`; the bars and gates are unchanged by the swap.** |
| **Both cells at n=600 decks** (same total cost, 21.4 h) | Gives each cell `se = 0.564`, `2σ̂ = 1.128` — moderate power in both, strong power in neither. Optimal for the §4.5 width contrast, worse for the vs-incumbent read that actually licenses the decision. Declined because the round's headline deliverable is a clean adopt/regress verdict on **one** allocation. |
| **A single 1200-deck cell on one allocation** | Would answer "does 44032 pay at k32?" well (`se = 0.399`) and say **nothing** about the width question `PRODUCTION.yaml` itself flags as unsolved. |
| **Re-grading against the RoD-v2 anchor** | CL-070: it cannot price budgets above 2752. §1.2. |
| **n large enough to bound a true null crisply** | Requires `se ≤ BAR_M / 2.84 ≈ 0.282`, i.e. **≈ 2400 decks ≈ 43 h** for the primary alone. Named here so the owner can fund it deliberately if the *bounding* direction is what they want — see §4.4's honest limitation. |

---

## 4. The statistics

### 4.1 The primary statistic — ONE leg, deliberately

**`M` = deck-paired margin, candidate(44032) minus opponent(22016), in
points/deck.** Per deck `D(d) = (diff(d, seat 0) + diff(d, seat 1)) / 2` over
decks played in **both** seatings; `M` is the mean and `se_M` its **realized**
empirical (fsum-variance) SE. `M > 0` means the 44032 candidate is ahead.

**Elo is a reported CO-READ, not a co-primary leg.** The `fpu_swap_cell` round
added elo as a Holm-corrected co-primary because elo was the better-powered
axis *there*. Here it is the worse one: the 22016 promotion's own row fixes the
exchange rate at ≈ **11.6 elo per pt/deck**, so at the primary's n the margin
leg's `se` (0.4883 → ≈ 5.6 elo-equivalent) is **~1.5× tighter** than the elo
leg's (`elo_sigma_paired(0.5, 1600) = 6.14`). Adding elo as a co-primary would
buy a multiplicity correction and no power. It is reported — with its own CI,
its own dispersion anomaly, and a **`coherence` sign-agreement flag** — because
elo is the deployment-relevant currency and because a **margin/elo sign
disagreement is a hand-review trigger** before any branch is acted on. It never
changes a branch label.

### 4.2 The branch ladder — pre-registered, exhaustive, first match wins

Adjudicated at the cell's **own realized `se_M`**, never at a planning constant.
`z = 2.0` (the `2σ` `LB95`/`UB95` convention this tree uses, not 1.645).

| Order | Branch | Condition |
|---|---|---|
| 0 | `U-VOID-INSTRUMENT` | gates failed, **or** `M`/`se_M` absent / NaN / non-positive |
| 1 | **`B-REGRESSION`** | `M + 2·se ≤ 0` — clearly **worse** than the incumbent despite double the budget |
| 2 | **`B-ADOPT`** | `M − 2·se > 0` **AND** `M ≥ BAR_M` |
| 3 | **`B-NULL-BOUNDED`** | `M + 2·se < BAR_M` — the effect is **bounded below** the decision-relevant size |
| 4 | `B-UNRESOLVED` | otherwise |

`B-REGRESSION` is checked **first** so a clearly-negative cell can never fall
through to a bounded-null reading (its condition implies `B-NULL-BOUNDED`'s).
`sanity_check()` and the selftest each sweep a dense `(M, se)` grid and
re-derive the label in closed form as an independent witness.

**Why `B-ADOPT` is `(LB95 > 0) AND (point ≥ bar)` and not `LB95 ≥ bar`.** The
FPU chain used `LB95 ≥ +1.0` because that decision put the burden on a
challenger knob against a zero-cost incumbent. **Here the incumbent has no cost
advantage to defend** — 44032 is ≈ 4.9 s/move against the ≈ 5.38 the program
already tolerated pre-wheel — so demanding the candidate be proven better *by at
least the bar* would import a burden this decision does not carry. The test used
is strictly **weaker** than `LB95 ≥ bar` and strictly **stronger** than the bare
`z ≥ 2` the 11008→22016 round used (which the owner's 2026-08-30 ruling now
forbids as a bar *definition*).

### 4.3 The bar — decision-anchored, and where it came from

> **`BAR_M = +0.80 pts/deck`**

**Derivation, in one line: `BAR_M` is the value that DISCRIMINATES THE TWO LIVE
FAMILIES (§1.1b).**

Family A (decay-RATE) predicts **+0.830** for this rung; family B
(measured-PRICE — the current, powered bound) predicts **+0.184**, with a
whole-remaining-tail of +0.565 whose bracket spans zero. Putting the bar at
**+0.80** places it *at* family A's prediction and ≈ 4.4× family B's, so the
branch ladder reads as a **family test**:

| branch | reads as |
|---|---|
| `B-ADOPT` | *"the RATE family is right, and the flip is worth it"* |
| `B-NULL-BOUNDED` | *"the PRICE family is right, and the budget ladder is DONE"* |

That is decision-anchoring in the strictest sense — the bar sits at **the effect
size that changes what the program does next**, not at a multiple of the
instrument's noise. `sanity_check()` asserts both halves of the derivation
mechanically (`|BAR_M − PRIOR_RATE_FAMILY| < 0.10` and
`BAR_M > 3 × PRIOR_PRICE_FAMILY`), so the bar cannot silently drift away from
the argument that set it.

⛔ **NOT `2·σ̂` of the instrument** (owner ruling 2026-08-30, *"effect size
sounds right"*). Its relationship to `2·σ̂` is stated explicitly, per the
`fpu_swap_cell` convention: at the primary's n, `2·σ̂ = 0.977`, so **`BAR_M`
(0.80) sits BELOW `2·σ̂`**. It was not derived from it. The consequence is that
**the `2σ` condition binds `B-ADOPT` and the BAR binds `B-NULL-BOUNDED`** — the
bar is not decorative, it is precisely the thing that lets a true null discharge
something instead of reading `UNRESOLVED` forever.

**The four planning priors, all derived rather than guessed:**

| Prior | Value | Source |
|---|---|---|
| **A-upper** — no decay (`r₄ ≥ 1`: the rung repeats) | **+1.229** | `D_prev` itself; `r₄ > 1` is called **real** in the LEVER_INDEX row |
| **A-central** — decay-RATE family | **+0.830** | `r × D_prev = 0.675 × 1.2293` |
| **A-lower** — rate family, Type-M discounted | **+0.500** | `r × (D_prev − SE_prev)` — §1.1's Type-M rider taken seriously |
| **B** — measured-PRICE family, **the current bound** | **+0.184** | the restated chain's own `g_next` (§1.1b) |

**Expected effect is BELOW the last doubling's `+1.229`.** Said plainly, as the
brief required: **diminishing returns is the central case**, three of the four
priors sit below the last rung's realized effect, and the *current* bound
(family B) puts this rung at barely a seventh of it.

### 4.4 The power table — and the honest limitation

`se` fixed at `se_model(n_decks) = 13.81/√n`, the standing sizing constant.
`MDE₈₀` = the true effect at which `B-ADOPT` fires 80 % of the time.

**PRIMARY `CELL_K32`, n = 800 decks / 1600 games — `se = 0.4883`, `2σ̂ = 0.977`,
adopt threshold `+0.977` (the 2σ condition binds), `MDE₈₀ = +1.387`**

| true effect | `B-ADOPT` | `B-REGRESSION` | `B-NULL-BOUNDED` | `B-UNRESOLVED` |
|---|---|---|---|---|
| **A-upper** +1.229 (no decay) | **69.8 %** | 0.0 % | 0.2 % | 30.0 % |
| **A-central** +0.830 (rate family) | **38.2 %** | 0.0 % | 2.0 % | 59.8 % |
| A-lower +0.500 (Type-M disc.) | 16.5 % | 0.1 % | 8.2 % | 75.2 % |
| **B** +0.184 (**price family — the current bound**) | 5.2 % | 0.9 % | 22.2 % | 71.7 % |
| **0.000 (exact null)** | 2.3 % | 2.3 % | **33.6 %** | **61.8 %** |
| −1.000 (mild regression) | 0.0 % | **51.9 %** | 43.5 % | 4.6 % |
| −3.000 (CL-054-scale) | 0.0 % | **100.0 %** | 0.0 % | 0.0 % |

**SCREEN `CELL_SIMS`, n = 400 decks / 800 games — `se = 0.6905`, `2σ̂ = 1.381`,
adopt threshold `+1.381`, `MDE₈₀ = +1.962`**

| true effect | `B-ADOPT` | `B-REGRESSION` | `B-NULL-BOUNDED` | `B-UNRESOLVED` |
|---|---|---|---|---|
| +1.229 | 41.3 % | 0.0 % | 0.4 % | 58.3 % |
| +0.830 | 21.2 % | 0.1 % | 2.0 % | 76.7 % |
| +0.500 | 10.1 % | 0.3 % | 5.5 % | 84.0 % |
| +0.184 | 4.1 % | 1.2 % | 12.2 % | 82.4 % |
| 0.000 | 2.3 % | 2.3 % | 17.7 % | 77.7 % |
| −1.000 | 0.0 % | 29.1 % | 43.7 % | 27.2 % |
| −3.000 | 0.0 % | **99.0 %** | 0.9 % | 0.0 % |

#### ⛔⛔ THE HONEST LIMITATION — stated up front, per the owner's 2026-08-30 ruling

The ruling requires that *"if the honest answer is 'we can only afford the
bounding direction,' SAY SO in the READ_RULE including the null's expected read
distribution."* Here is the version of that statement this design owes:

* **A true null reads `B-UNRESOLVED` ≈ 62 % of the time at the primary's n**
  and `B-NULL-BOUNDED` only ≈ 34 %. **This design cannot crisply bound a true
  null below a `+0.80` bar at any affordable n.** Crisp bounding (≥ 80 %
  discharge) needs `se ≤ BAR_M/2.84 ≈ 0.282`, i.e. ≈ **2400 decks ≈ 43 h** for
  the primary alone — named in §3.6 so it can be funded deliberately.
* **The design is genuinely underpowered at its own central prior:** at
  `+0.830` it adopts only **38 %**. It is well powered for exactly three
  things: a repeat of the last rung's realized effect (**70 %**), a CL-054-scale
  width regression (**100 %**), and — weakly — a mild regression (**52 %**).
* ⚠️ **It cannot distinguish family B from an exact null.** At `+0.184` the
  reads are 22 % `B-NULL-BOUNDED` / 72 % `B-UNRESOLVED`, against 34 % / 62 % at
  a true zero. So the round can tell family A from family B (that is what the
  bar is for), but a family-B world and a dead-null world look nearly the same
  to it. **That distinction is not on offer at any affordable n and is not
  claimed.**
* **A `B-UNRESOLVED` read is therefore mostly evidence about the affordable n,
  not about the world.** It must not be reported as "the doubling does
  nothing."

#### The alternative bar, printed rather than asserted

Had `BAR_M = +1.00` been used (the FPU chain's bar class), the primary's read
distribution would be:

| true effect | `B-ADOPT` | `B-REGRESSION` | `B-NULL-BOUNDED` | `B-UNRESOLVED` |
|---|---|---|---|---|
| +1.229 | 68.1 % | 0.0 % | 0.7 % | 31.3 % |
| +0.830 | 36.4 % | 0.0 % | 4.9 % | 58.7 % |
| +0.500 | 15.3 % | 0.1 % | 16.3 % | 68.3 % |
| +0.184 | 4.7 % | 0.9 % | 36.3 % | 58.1 % |
| **0.000** | 2.0 % | 2.3 % | **49.6 %** | **46.1 %** |
| −1.000 | 0.0 % | 51.9 % | 46.3 % | 1.8 % |

i.e. `+1.00` **discharges a true null materially better** (49.6 % vs 33.6 %,
and 36.3 % vs 22.2 % in a family-B world) at a cost of ≈ 2 pp of adopt power.
It was **not** chosen for two reasons: it would be tuning the bar to the
instrument's read distribution rather than to the decision (the exact inversion
of the owner's ruling), and it sits **above family A's own prediction** —
pre-registering a bar that the better-case prior cannot clear. The comparison
is printed so the choice is auditable, and so **the owner can overrule it
before `BLIND_COMMIT` is stamped** if they prefer the bounding direction.
`BLIND_COMMIT.json` names this as the round's one discretionary call.

### 4.5 The secondary width contrast — reported, never licensing

**`W = D(CELL_K32) − D(CELL_SIMS)`** over the decks **both** cells played
(expected 400), with its own realized paired SE and `LB95`/`UB95`.

⛔ **No bar is pre-registered for it.** It is a third statistic on the same
games and reads as a **direction with a CI**, nothing more. It is nevertheless
the **first direct fixed-budget width contrast ever run above 2752 in this
program** — whatever it reads, it belongs on CL-054, CL-060 and
`docs/LEVER_INDEX.md` at close-out.

### 4.6 Type-M applies to THIS round's own result

`MDE₈₀` for the primary is **+1.387**, which is **above every one of this
round's own planning priors** (+1.229 / +0.830 / +0.500). So **if this round
reads `B-ADOPT`, its realized effect will very likely sit below its own MDE** —
exactly the condition that put a Type-M rider on the 11008→22016 row. The
adjudicator computes `type_m.realized_below_own_mde` and the readout must carry
the rider: **the sign is the reliable part; the magnitude is biased upward.**

---

## 5. The gates

**`ABSENT` is `FAIL`** — never a skip, never a default. Every gate names the
document and address that answered it.

### 5.1 Per chunk (must pass on EVERY chunk; a cell is only as clean as its dirtiest chunk)

| Gate | What it refuses |
|---|---|
| **`G-BUDGET`** ⭐ | Candidate `k×sims` ≠ this cell's frozen 44032 triple, **or** opponent ≠ `(16, 1376, 22016)`, read **from the emitted manifest**; `summary.asymmetric_budgets ≠ true`; or manifest and the summary's `candidate_*`/`opp_*` witnesses **disagreeing** (an unreconstructable budget) |
| **`G-BUDGET-RATIO`** ⭐ | Magnitude-free structural check: candidate total ≠ **2 ×** opponent total, or the allocation shape ≠ this cell's (`CELL_K32`: `k` doubles, `sims` held; `CELL_SIMS`: `k` held, `sims` doubles). Separate from `G-BUDGET` so it *can* be asserted on a reduced-budget smoke — which is where a flag-wiring error would actually be introduced |
| **`G-TIEARB-SIDES`** | Either seat unarmed, or armed at anything other than `DEPLOYED_TIEARB_B64` on all seven spec keys (a missing `phase_gate` is a FAIL) |
| **`G-TIEARB-FIRED`** | **Both-armed positive controls**: either seat's realized `fired_plies` zero/absent in play, or either seat's arbiter container never exercised |
| `G-EXACT` | `exact_k ≠ 2` or endgame `mode ≠ marginalized` |
| `G-RULES` | `rules_profile ≠ fixed_v1`, or `r9_env_ok` / `r9_env_observed` not both true |
| `G-BACKEND` | backend not `rust` (name **and** requested), or `mixed_builds` |
| **`G-WHEEL`** | `carc_rs_build` absent/"unavailable", `carc_rs_binary_sha` absent, `mixed_builds` true |
| **`G-LEAF`** | the two sides' leaf hashes differ, or differ from `a36d2e15a3b3d71d` |
| `G-HOST` | not the local box (the round is owner-funded *for* the local box; a box change is a pre-launch amendment) |
| `G-REV` | `code_rev` absent, or not a prefix of `PINNED_SRC_REV` |
| `G-BLIND` | `BLIND_COMMIT` absent or not 40-hex — *a read that was not blind is not a read* |
| **`RECON`** | an independent `math.fsum` witness recomputed from that chunk's raw records disagreeing with that chunk's own `summary.json` on any of `paired_mean_margin` / `paired_z` / `n_paired` / `winrate` / `elo` |

### 5.2 Pool level

| Gate | What it refuses |
|---|---|
| **`G-CHUNKS`** | a planned chunk missing, missing either document, or not `DONE` |
| **`G-SHARD-IDENT`** | wheel sha / leaf hashes / budget triples / rules profile / `code_rev` / `BLIND_COMMIT` **differing across chunks** (a mixed-era pool) |
| **`G-NODUP`** | overlapping chunk seed ranges, or any `(deck, seat)` appearing more than once (the resume-double-count defect) |
| **`G-N`** | pooled scored records ≠ the frozen game count; pooled failure rate ≥ 2 %; `n_common` below 80 % of the frozen deck count |
| `G-BAND` | any chunk's `band_seed_start` ≠ its planned offset inside the **claimed** band; no `BAND_CLAIMED` file at all |
| `G-DECKS` | a deck played at one seat only, a seed outside the cell's registered window, or `n_common` ≠ the frozen count |
| `G-SAT` | pooled winrate outside `(0.35, 0.65)` — a **rail**, not a strength bar |

---

## 6. Operations

### 6.1 Box and W — the owner override, recorded

Owner, 2026-09-01, verbatim: **"fund 44k at w30."** → **LOCAL box, W = 30.**
This is an explicit override of the standing `W = logical threads` default
(local 32, owner ruling 2026-09-01). It agrees with the settled sweep
(`measurement/wsweep_local_20260831/READOUT.md`: `W_LOCAL = 30`, plateau,
W30 ≡ W36 within 0.31 %, `z 1.41`).

⛔ **W is THROUGHPUT-ONLY.** No gate, bar or branch reads it. The launcher
records it and warns if the running W differs, so a smoke at a different W is
not mistaken for a tenancy-comparable rehearsal.

All chunks run `nice -n 19`. A full-args process census runs before every
launch (`ps -eo pid,etime,pcpu,args` — **never** `-C python`/comm, under which a
silent long job is invisible; `feedback_no_agent_compute_beside_eval` quantified
a **1.8×/move** inflation from one stray niced core).

### 6.2 ETA at W = 30

**Cost model.** From `wheel_rollin_20260901`: 22016 arb-armed = `2.433 s/move`
(governance-grade); 22016 search-only = `2.179 s/move` (informal, same dir) ⇒
the arbiter increment ≈ `0.254 s/move`, and it is **post-search at the root**, so
it does *not* scale with the budget. Doubling only the candidate's search:

```
candidate move = 2 × 2.179 + 0.254 = 4.612 s
opponent  move =                     2.433 s
game average   = (4.612 + 2.433)/2 = 3.523 s   ⇒  ×1.448 vs a 22016 game
```

Realized local throughput at 22016 arb-on, W=30, is **162 g/h**
(`measurement/wsweep_local_20260831/READOUT.md`), so the planning rate is
**≈ 112 g/h**.

| | games | ETA @ W=30 |
|---|---|---|
| chunk (200 decks / 400 games) | 400 | **≈ 3.6 h** |
| `CELL_K32` (primary, 4 chunks) | 1600 | **≈ 14.3 h** |
| `CELL_SIMS` (screen, 2 chunks) | 800 | **≈ 7.2 h** |
| **full round** | 2400 | **≈ 21.5 h** |

**The round spans more than one night. That is expected and accepted** — hence
the chunked/resume design (§3.4). The **powered primary plays first**, so if box
time is cut short the cell that licenses the decision is the one that completed.

⚠️ **This is a MODEL.** It assumes search cost is linear in total sims and that
the two allocations cost the same — neither is exactly true: `k32×1376` runs
**2× as many determinizations per move** as `k16×2752`, so it pays 2× the
per-determinization setup **and 2× the marginalized exact-K endgame handoffs**.
The launcher therefore **re-derives the ETA from the round's own first completed
chunk** and prints it (`feedback_eta_before_launch`; and it uses the whole
chunk's wall-clock, never the first completions of a parallel run).

### 6.3 ⚠️⚠️ The pinned-round commit freeze

This round is **rev-pinned and chunked**, so the pin check runs **before every
chunk**. While the round is live:

> ⛔ **NO main-tree git commits AT ALL — not even docs.**

A commit moves `HEAD`, the next chunk's pin check fails, and the launcher dies
mid-round. **Re-pinning is NOT the fix** — it creates a cross-chunk rev split,
which `G-SHARD-IDENT` then voids. Stage work and commit at round end.
(auto-memory `reference_freeze_latch_hook`, the BLIND-SPOT clause; the launcher
also drops a `RUN_LIVE_*.json` sentinel for the freeze latch.)

### 6.4 Detach

```
setsid nohup nice -n 19 ./launch_budget44k.sh >> budget44k_launch.log 2>&1 &
disown
```
The harness's `run_in_background` alone is **not** enough — Mac-sleep SIGHUP and
WSL VM-teardown both kill tty-attached jobs.

### 6.5 Pre-launch checklist (all of these are also enforced by the launcher)

| # | Precondition | Enforced by |
|---|---|---|
| 1 | `screen_lib.sanity_check()` empty | launcher probe, REFUSES |
| 2 | `adjudicate_budget44k.py --selftest` exit 0 | launcher, REFUSES |
| 3 | ⚠️ **`./launch_budget44k.sh --smoke-prod`** — the CLAUDE.md pre-flight norm: **production knobs**, 4 games/cell, throwaway seeds, ~10 min. It is the only smoke that runs the real magnitudes, so it is the one that can **also satisfy `G-BUDGET`** — and the launcher asserts that it does, before ~21 h of box time is committed. **Owed at launch time, on the box that will run the round** (a smoke on a different box or W is not tenancy-comparable). *Not run at freeze: the build box had another agent's short bursts in flight.* | launcher, REFUSES on `G-BUDGET` failure |
| 4 | Band swept fresh and **claimed** → `BAND_CLAIMED` exists | launcher, REFUSES |
| 5 | `BLIND_COMMIT.json` stamped with the freeze commit's 40-hex sha (a **second** commit) | launcher, REFUSES; `G-BLIND` |
| 6 | `PINNED_SRC_REV` stamped and **equal to `HEAD`** | launcher, REFUSES **before every chunk** |
| 7 | `src/`, `engine/`, `scripts/classical_search/` and this dir **clean** | launcher, REFUSES **before every chunk** |
| 8 | Full-args process census; box otherwise idle | launcher prints it; the operator reads it |
| 9 | ⛔ **No main-tree commits for the round's duration** (§6.3) | nothing mechanical — this one is on the operator |

---

## 7. What each branch licenses

⛔ **This round makes no source change and changes no governance file on any
branch.**

### 7.1 `B-ADOPT`

Licenses exactly two things, **neither automatic**:

1. **PROPOSING** a `governance/PRODUCTION.yaml` `champion.fair_deploy` budget
   flip to **44032 at the adopting allocation**, for a **separate owner
   ruling**. The proposal must carry: which cell adopted, the realized `M` and
   its CI, the elo co-read and its sign, the Type-M status (§4.6), the new
   `measured_s_per_move` that will be owed, and the desktop↔mobile parity
   consequence (§7.3).
2. **Funding an out-of-family external Carcasum corroboration step.** A
   promotion of this size should carry an independent-engine cross-check the way
   the arbiter fold did (`carcasum_arbchallenge`, +69 external vs +66 internal).
   The F4 lesson is standing: **never fund work off a single judge family**, and
   judge-free game outcomes outrank any judged number.

An adopt on **one** allocation licenses proposing **only that one**.

### 7.2 The other branches

* **`B-REGRESSION` on `CELL_K32`** ⭐ — the round's highest-value outcome:
  confirms CL-054's inverted-U biting above k16, **closes the "keep doubling k"
  allocation rule**, and re-frames the k8→k16 step as near the top of the curve.
  Update CL-054, CL-060 and `docs/LEVER_INDEX.md`'s budget-headroom row in the
  same sitting.
* **`B-REGRESSION` on `CELL_SIMS`** — a finding about *depth*, with no standing
  prior at all. Hand-review `RECON` and `G-BUDGET` before trusting it.
* **`B-NULL-BOUNDED`** — a **discharging** read, not a failure: the doubling
  does not buy `+0.80`, i.e. **the measured-PRICE family (§1.1b) is the right
  one and the budget ladder is done.** The action is to **stop buying budget
  rungs**, record the realized bound `M + 2·se`, and update the LEVER_INDEX
  budget-headroom row with the first *direct* corroboration of its restated
  chain. Not "fund more n". ⚠️ It does **not** distinguish family B from an
  exact null (§4.4) — do not claim it does.
* **`B-UNRESOLVED`** — see §4.4. An extension to larger n is a **named,
  separately funded re-open** with its own band and its own freeze (the
  `fpu_h2h` → `fpu_h2h_r2` posture). Adding n to *this* round and re-reading at
  the same bars is peeking.
* **`U-VOID-INSTRUMENT`** — the instrument, not the world. No reading is taken
  on any axis.

**Cross-cell:** a screen-positive / primary-unresolved pattern is a **named
re-open trigger** for a powered `CELL_SIMS` round — never an automatic flip.

### 7.3 ⛔ Mobile is out of scope on every branch

`deploy_profiles.mobile` runs `k16×1376 = 22016` on the phone and this round
licenses nothing about it. A desktop flip would **break desktop↔mobile budget
parity** and **open a new E4 archive epoch** (E4 statistics must condition on
the budget epoch exactly as they condition on `rules_profile`). Those are
consequences to **price in the flip proposal**, never changes this round
propagates.

---

## 8. Freeze manifest

Frozen together by the freeze commit; `BLIND_COMMIT.json` is stamped by a
mandatory **second** commit (a commit cannot name its own hash):

* `PREREG.md` — this document
* `screen_lib.py` — constants, priors, the branch ladder, the budget/arbiter
  gates, `sanity_check()`
* `adjudicate_budget44k.py` — the chunk-pooling adjudicator and the read rule
* `launch_budget44k.sh` — the launcher, its precondition ladder, the smoke legs
* `test_budget44k.py` + `selftest_fixture/` — the contract tests and the
  **REAL-EMITTER** fixtures
* `BAND_CLAIMED.placeholder` — the band is **proposed, not claimed**
* `BLIND_COMMIT.json` — `PENDING` at freeze

**State at freeze:** real cell games `0`; band claimed `false`; `results.csv`
rows `0`; `PRODUCTION.yaml` touched `false`; `governance/` touched `false`;
`src`/`engine`/`rust` touched `false`.

## 9. Close-out checklist (the standing six touches)

1. `experiments/results.csv` row per cell (+ the width contrast)
2. `DECISIONS.md` index line
3. status banner on **this** doc
4. governance row flip — `CLAIM_REGISTRY.csv` (CL-054 / CL-060 if the width
   contrast speaks), `BAND_REGISTRY.csv` (retire the band from confirmatory
   use), `PRODUCTION.yaml` **only** on a separate owner ruling
5. `STATUS.md` top block
6. `docs/PROGRAM_ROADMAP_2026-07-07.md` line, **and** a
   `docs/LEVER_INDEX.md` row — the index currently has **no row for the 44032
   rung**, and its budget-headroom-decay row explicitly says it *"says nothing
   about … 44032"*. That row is owed either way.

Then `python3 scripts/doc_lint.py`.
