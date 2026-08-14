# J-rules on search — DEPLOY-BUDGET CELL, ADJUDICATED VERDICT (2026-08-13)

**Status: ADJUDICATED. Nothing promoted; `governance/PRODUCTION.yaml` untouched; NO claim
minted — `CL-081` was *reserved* by the prereg and is deliberately left UNUSED and available.
Prereg of record: [DEPLOY_PREREG.md](DEPLOY_PREREG.md) §6 branch map + §7 scope clause.
Owner ruling 2026-08-13: "default" ⇒ THE PREREG AS WRITTEN GOVERNS.**

## The cell

One cell, one dose, no ladder. Candidate = the production champion leaf **plus** the `jrules`
term (the anchor's articulated strategy J1 | J2 | J5 | J6 | J8 as additive **static** leaf
terms) at `jrules_dose 0.25` / `jrules_mask 31`, `cand_leaf_hash 15948beccf3472d3`; opponent =
the **UNMODIFIED** production champion `a36d2e15a3b3d71d`. **Both arms FAIR PIMC k8×1376 =
11008** (`eval_fair_puct.py --info fair --opponent fair-champion`), `fixed_v1` + R9, rust both
sides, exact-K 2 shared by both arms. Band **1.28e11**, seeds `128000000000..128000000399`,
400 decks × 2 seats.

The dose is the **floor of the authorized ladder**, named by
[CALIB_READ_RULE.md](CALIB_READ_RULE.md) (committed before any flip rate was read) → branches
`FINER-RUNG` then `FUND-SMALLEST` → [CALIB_READOUT.md](CALIB_READOUT.md). It flips **23.65 %**
of champion picks. That bought **resolvability, not safety**, and it is recorded here as it was
recorded before the run.

**Integrity (N0):** 800 records · 800 unique `(deck_seed, seat)` cells · 0 missing · 0 extra ·
all 400 decks fully paired · every seed inside the band · both arms 8 × 1376 = 11008 ·
`cand_leaf_hash` / `opp_leaf_hash` as pre-registered · **the RESOLVED `jrules_dose 0.25` in the
manifest** (the gate that proves the term is live — a moved hash does not) · no `jrules_mask`
key ⇒ default 31 · no `jrules_*` key on the opponent · `fixed_v1` + `CARCASSONNE_FIX_R9="1"` ·
rust converted on both sides. Machine record: `verdicts/GATES_jrules_d0p25_deploy11008.json`.

⚠️ **ONE N0 CLAUSE IS UNVERIFIABLE AS WRITTEN, and it is not reported as satisfied.** N0
requires "a single `variant_id`". **`eval_fair_puct` emits no `variant_id`** anywhere — in the
manifest or the records; it is a `scripts/joshuabot/h2h.py` field that was carried into this
prereg from the Joshua-bot confirm's integrity line. The surrogate actually checked, and the
only thing that may be quoted: one manifest, and all 800 records agreeing on
`(sims, k_dets, exact_k, opponent, info, rung_sims) = (1376, 8, 2, "fair-champion", "fair", 800)`.

⚠️ **Read [MANIFEST_LABEL_TRAPS.md](MANIFEST_LABEL_TRAPS.md) before describing this cell from
its `manifest.json`.** Three boilerplate strings in that file contradict its own numbers:
`equal_wall_clock_note` calls 11008-vs-11008 "NOT an equal-sims cell"; `cand_curve_drift` says
"NOT curve125" while the candidate and reference curve arrays are element-for-element
identical; `both_sides_curve125: false` has the same root cause. All three are template strings
emitted when a code path is *available*, not when it is *exercised*. **This cell is
equal-sims and both sides are curve125.** None of those labels may be repeated as fact.

**Execution:** the cell ran on **BOTH boxes** (local W14 + laptop W16, shared-claim
work-stealing — see [LAPTOP_REJOIN_20260813.md](LAPTOP_REJOIN_20260813.md)). The deck-paired
margin and `ms_ratio` are first-order insensitive to that; **absolute ms/move and games/h are
shared-tenancy figures** and must not be compared against a single-box cell.

## The number

| statistic | value |
|---|---|
| W / D / L | **354 / 14 / 432** (n 800, 400 fully paired decks) |
| win rate (candidate) | 0.45125 |
| **deck-paired margin** | **−2.4912 pts/deck** |
| realized `se` | 0.6460 |
| **PRIMARY STATISTIC — margin z** | **−3.8564** |
| elo ± 1σ | **−33.98 ± 12.34** |
| `ms_ratio_cand_over_opp` | **1.2116** (source `eval_fair_puct (champ_prefix/rung)`) |
| failed games | **0 / 800 (0.000 %)** — **N5 did NOT fire** |
| solver timeouts | 0 candidate / 0 opponent |

Elo agrees in sign with the primary statistic. Zero failed games is *below* the Joshua-bot
confirm's known-family rate (0.125 %, 1/800) and far below the 0.5 % house reference.

## Adjudication

**Two branches fired, and the second modifies the first.**

- **N1 fired.** Margin z **−3.856 ≤ −2.0**. On its own wording this is REFUTED: *the anchor's
  articulated strategy, encoded as static leaf terms at the smallest authorized dose, does not
  survive inside the champion's own search.*
- **N4 fired.** Measured `ms_ratio_cand_over_opp` = **1.2116 > 1.20**, above even the benched
  prediction (1.12–1.14). N4 is explicit: **N1 downgrades from REFUTED to "loss, confounded by
  budget", no claim is minted at Refuted, and the write-up says so.**

⇒ **THE ADJUDICATED READING IS: A LOSS, CONFOUNDED BY BUDGET.**

**No claim is minted. `CL-081` was reserved by the prereg for the Refuted branch and is left
UNUSED and available** — `governance/CLAIM_REGISTRY.csv` gains no row from this cell.
`governance/PRODUCTION.yaml` is untouched, as it is on every branch of this design.

The `jrules` term **remains default-off**. Nothing in this cell licenses turning it on; the
downgrade removes the word *permanently* (which rested on the refutation), not the default.

⛔ **The "encode the anchor's strategy as static leaf terms" route is NOT CLOSED.** N1's closing
clause is exactly the part the downgrade suspends: a budget-confounded loss does not formally
close a route. Writing "the route is closed" is a forbidden reading of this verdict.

## Recorded dissent — NOT adopted

[AMENDMENT_1_N4_DIRECTION.md](AMENDMENT_1_N4_DIRECTION.md), written **while blind** (before any
strength number existed on disk, verifiably so), argues that N4's consequence points at the
wrong branch: both arms run **identical search** (8 × 1376 on each side), so the candidate is
slower per move only because its *leaf* costs more, not because it is given less search; at
fixed sims wall-clock is not a strength variable, so a loss at equal sims is a clean loss and
it is **N2 (a win)** that would have needed the cost discount.

**The owner ruled "default" — the prereg as written governs. The amendment is NOT adopted.** It
stands on the record as a **recorded dissent** about N4's *logic*; it moved no threshold, no
branch condition and no statistic, and it is not applied to this adjudication. Note the
amendment's own §3: *"a prereg's authority does not depend on its author later liking it, and
the conservative reading costs us a claim we might have been entitled to rather than granting
one we were not."* That is what happened here.

## What this cell answers that the Joshua-bot tournament could not

The tournament measured J1–J9 as a **scripted opponent on a one-ply greedy base** and lost by
**−16.0 pts/deck** (z −24.42) — *weaker than JCloisterZone's shallow `LegacyAiPlayer`* (−6.50),
so it priced **encoding + depth**, not strategy
([CONFIRM_VERDICT.md](../joshuabot_20260812/CONFIRM_VERDICT.md) §"The design fix this run
earns"). This cell is that design fix: same rules, encoded inside the champion's **own** leaf
at the champion's **own** budget against the **unmodified** champion.

Encoded that way the same strategy loses by **−2.49 pts/deck**. **Removing the depth confound
shrank the deficit ~6×** — the overwhelming majority of the tournament's −16.0 was **depth, not
strategy**. ⚠️ **But the residual is still NEGATIVE, not zero**, and it resolves in sign
(z −3.86). *"The depth confound explains it all"* is not what this says.

⚠️ **The −16.0 and the −2.49 are NOT pooled, contrasted, or differenced as a statistic.**
Different candidates, different bases, different (retired) bands; CL-068 cross-band inflation
and the prereg's read rule 5 both forbid it. The ~6× is an **observation about design**, not a
measured effect.

**Against CL-080 (open-city discipline), the closest comparable:** −33.98 elo here vs **−53.8**
(dose 0.5, z −5.863) and **−190.3** (dose 2.0, z −19.384) there — **milder, same direction**.
Also an observation across bands and levers, not a statistic. What it does support is the
mechanism that both levers now share: a **static** leaf term double-counting something the
11008-sim search already prices for itself.

## §7 scope of refutation — BINDING, and *weaker still* under the downgrade

[DEPLOY_PREREG.md §7](DEPLOY_PREREG.md) is binding on the write-up of this branch. A loss here
prices **"this strategy, as static leaf terms, at this dose, inside the champion's search"** —
it does **NOT** price **"this strategy"**, and it does not price the owner's actual play.

1. **The encoding is disclosed-weaker by construction.** The J-rules are adaptive and
   contextual — bag counting, opponent meeple state, phase-dependent farm surrender — and a
   **static leaf term cannot condition on any of it**. DESIGN §3.1 records that **J2's planning
   clause was never expressed at all**; DESIGN §3.0 records that **J1, J2's steal and J6's road
   join had to DROP the "he must already be there" predicate** to keep the leaf antisymmetric,
   so they credit *holding a share* rather than *stealing*. A negative therefore bounds **the
   encoding**, and speaks to the strategy only as far as the encoding is faithful — which the
   design says, in named places, it is not.
2. **J1 is not vindicated by open-city's failure, and open-city is not resurrected by this.**
   J1 **credits** large open cities you hold; the `opencity` term **penalized** the same object
   and lost decisively (CL-080). The sign is opposite, the **mechanism is the same**, and the
   double-count argument is about **staticness, not sign**. Both directions of *"the other one
   lost, therefore mine wins"* are FORBIDDEN readings.

**Also NOT refuted by any branch of this cell, and named as such:** **J8** (fires on ~3 % of
states — a bundle result is not a J8 result) · the **per-rule mask ablations** (mask pinned at
31 throughout; each mask is a fresh multiple comparison and a **new** calibration) · **J10f and
J3's hard floor** (root filters, deferred and **not built**) · the **asymmetric / own-side-only
variant** (`jrules_symmetric = False` — opponent modelling, a different hypothesis, needs its
own prereg and fresh band) · **J7** (answered by the tournament: `j7_weight` 0 > 1, z +3.71) ·
**J9** (tournament no-conviction) · the **policy-prior surface (B)**, declined by the design on
sims-washout grounds.

⚠️ **Under the downgrade every one of these limits binds harder**, not softer: the adjudicated
reading is a *confounded* loss, so anything §7 already excluded is excluded a fortiori.

## Honesty items carried forward

- **Rust parity for this term rests on `reconcile_leaf.py` ALONE** (83,824 values, 0
  mismatches, 6 cells incl. a dose-0 moved-mask identity control).
  `tests/test_jrules_term.py` is 39 passed / 1 skipped and **the skip is STRUCTURAL, not
  staleness** — `carc_rs` exposes no direct leaf entry point, so it will not become a pass on
  any rebuilt box. There is no second, independent rust-parity check.
- **`code_rev 217f0cdbe-dirty`** — the `-dirty` is real but benign: at launch the tree carried
  **untracked files only**; every file the cell depends on is committed in `217f0cdb`.
- **No pooling** with the 2750 instrument (CL-079), with the 0-game calibration, with the
  tournament cells, or across bands (CL-068).
- **No top-up is licensed and none was run.** There is no cheaper rung to retreat to
  (`CALIB_READ_RULE` §3.1 permits nothing below 0.25); a `d0p125` would be a **new
  calibration**. Re-running at higher n needs a mechanism argument, a new prereg and a fresh
  band — CL-079's precedent is binding.

## Governance

Band **1.28e11** flips **claimed → retired, `decision_influenced = yes`** (it adjudicated this
cell). Reserved headroom above `128000000399`: none was ever claimed by this row, so nothing is
released. **No `governance/CLAIM_REGISTRY.csv` row** — the downgraded branch mints none, and
**CL-081 stays unused**. `experiments/results.csv` row
`jrules_d0p25_deploy_fixed_v1_vs_champ11008_n800_b128e9` **is** owed (800 real head-to-head
games against the production champion) and is written. `governance/PRODUCTION.yaml` untouched;
nothing promoted.
