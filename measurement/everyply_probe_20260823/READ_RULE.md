> ⛔→✅ **FROZEN 2026-08-23 (branch-freeze on everyply-freeze; the blind commit INTRODUCES THIS BANNER; local main latched under a live suite; merges at the quiet window). Owner funding: "every ply. fund." 2026-08-23. PRE-FREEZE ORCHESTRATOR RULING, per the pair's own §3.1 pre-committed fallback: --arm-builder leaf_topk IS the instrument (pooled-Q unreachable through the mandated seams — rust exposes pooled N, not Q); the drafters' ten applied readings are adopted as pre-freeze resolutions. No statistic exists at freeze time; §0.A stands: KILL-ONLY interim.**

# EVERY-PLY ROLLOUT ARBITRATION (SIZE-1) — READ-RULE

> **⚠️ BLIND ORDERING (once this pair is actually committed). This file is meant to be committed
> BEFORE the corpus is built, BEFORE the first leg runs, and BEFORE any statistic of any kind
> exists.** Its git commit is intended to be the proof. **The branch that fires is taken
> VERBATIM, whatever it is. No owner call adjudicates any outcome**; owner authorization funds
> the screen and does not name its answer.
>
> Design: [`DESIGN.md`](DESIGN.md). Run id `everyply_probe_20260823`.
> **This read-rule is fully mechanical.** Every branch is a boolean function of numbers the
> analyser emits. It is **spent on this mechanism and this corpus**; any successor design needs a
> fresh one.

---

## §0 — SCOPE, AND THE ONE THING MOST LIKELY TO BE READ BACKWARDS

- **0 games on every branch.** No `experiments/results.csv` strength row, **no deck band, no
  `governance/BAND_REGISTRY.csv` entry, no claim id**, `governance/PRODUCTION.yaml` untouched —
  **regardless of outcome** ([`BAND_NOTE.md`](BAND_NOTE.md)).
- **SIZE-1 is a KILL-ORIENTED SCREEN.** It has good power against the prior-favoured hypothesis
  (harm) and **poor power against a modest gain**.

> ### ⛔ §0.A — THE POSITIVE BRANCHES ARE NOT REACHABLE AT SIZE-1. NAMED HERE, BEFORE GAME 1.
>
> SIZE-1 funds **one** read point: **n = 400**, and the plan declares it a **one-sided,
> KILL-ONLY futility interim** — *"the interim may fire `E-HARM` or stop for futility and **may
> not fire any positive branch**"*. Consequently, at this pair's only read point:
>
> | branch | reachable at SIZE-1? |
> |---|---|
> | `E-HARM` | ✅ **YES** — at `κ̂ ≤ −0.168` |
> | `E-FLATNULL` | ⚠️ **MARGINALLY** — needs `κ̂ ≤ −0.018` (§4 note) |
> | `E-UNRESOLVED` | ✅ YES (the residual) |
> | `U-UNREADABLE` | ✅ YES |
> | **`E-FUND`** | ⛔ **NO — structurally, by the kill-only declaration** |
> | **`E-CLEAN`** | ⛔ **NO — structurally, by the kill-only declaration** |
>
> `E-FUND` and `E-CLEAN` are carried below **verbatim as the plan states them** because they are
> the branches a *funded top-up* would read on the **same committed seeded order** — but **this
> pair cannot fire them.** A SIZE-1 read that clears `κ̂ ≥ +0.168` therefore lands
> **`E-UNRESOLVED`**, and `E-UNRESOLVED`'s own required print (the `n` that would resolve the
> observed `κ̂`) is what a top-up decision would rest on.
>
> ⚠️ **This is a declared limit of the funded size, NOT a discovered one, and it must not be
> narrated after the fact as "the probe found nothing positive."** A positive κ̂ at SIZE-1 is an
> *unresolved* reading, and the readout must say so in those words.

---

## §1 — THE STATISTIC, NAMED BEFORE IT EXISTS

**PRIMARY:**

```
kappa   = SUM_s w_s * mean_{p in s} kappa[p]        [points per NON-TIED tile ply]
          w = the EXACT census weights (0.0997, 0.4290, 0.4713) -- known, not estimated
se      = cluster-robust on root_id, root_id := game_id   (analyze_tiletie.cluster_robust)
z_kappa = kappa / se
```

`kappa[p]` is the two-fold-symmetrized cross-fit capture of DESIGN §4.1: the arm is chosen by
`tier1-greedy` on the **selection** worlds, priced by `clair-puct` on the **disjoint evaluation**
worlds, minus the champion's own arm priced on the same evaluation worlds.

**DECLARED CONVENTIONS — fixed here so they cannot be chosen after seeing a number:**

| symbol | definition |
|---|---|
| `UB95(κ̂)` | **`κ̂ + 2.0 · se`**. The 2.0 (not 1.96) is the plan's own arithmetic: it is what reproduces both published `E-FLATNULL` thresholds, **−0.018 at n=400** and **+0.038 at n=900**. |
| `scale_all` | **≡ 1.0** (DESIGN §4.2). There is no degenerate collapse class at a non-tied ply. |
| cluster unit | **`root_id := game_id`** — the census carries no `root_id` field. |
| `q` | `pickchg` — fraction of positions where `a_arb ≠ champ`. Planning-central **0.76**. |
| `n_analysed` | priced positions **plus** zero-filled positions (§3 `G-ZEROFILL`). |

⚠️ `z_κ` is **READ off the analyser's computed value**; a from-scratch recomputation from the raw
per-position records is printed alongside it. A disagreement beyond floating-point tolerance is
`U-UNREADABLE`. The recomputation is a **WITNESS, never a branch input**.

---

## §2 — UNITS

Primary unit: **points of final-score margin per NON-TIED TILE PLY**, at the root player's seat.

⚠️ **`κ` IS NOT COMPARABLE TO THE TIED-PLY `arb = +0.2065`** — that number is `scale_all`-scaled
and this one is not (its unscaled *discriminable* sibling is +0.2844). **This sentence is printed
on every read-out** (§4.3 rail 5).

Elo is a **derived DISPLAY quantity only**, converted through the DESIGN §4.3 **bracket**
`NA ∈ [0.31, 0.85]`, `pts_per_game = κ × 12.812 × NA`, `elo ≈ 7.79 × pts_per_game` — **never the
unit a bar is set in, and never quoted as a point estimate.** `n` in every bar below is in
**POSITIONS**, never games or decks.

---

## §3 — PRECONDITIONS (every one must PASS, else `U-UNREADABLE`)

**Fail-closed. ABSENT IS FAIL.** Each gate names the tool that computes it and the exact address
it is read at; the adjudicator reports which address resolved (the house `G-BAND`/`G-J1` fix
precedent).

| id | proposition (must be TRUE) | tool + address | VOIDS on |
|---|---|---|---|
| `G-KNOWNGOOD` | the shared estimators still reproduce the adjudicated tied-ply instrument | `scripts/tiletie/probe_pickers.py knowngood` → `KNOWNGOOD.json["ok"] == true`; `require_knowngood` (`probe_pickers.py:677`) pins `arb = +0.2065`, `N_POSITIONS_OF_RECORD = 733`, `N_ROOTS_OF_RECORD = 399`, `KNOWNGOOD_TOL = 1e-9` against `measurement/tiearb_20260816/READOUT.json` | `ok` false or absent |
| `G-CRN` | selection and pricing ran on **bit-identical** worlds | fields written by `scripts/measurement_infra/oracle_score_pilot.py::_process` — `crn_verified`, `checksum_ok`, `world_seeds`, `playout_seeds`; cross-leg identity by `scripts/tiletie/run_tiletie.py::verify_leg_records` | any record with `crn_verified != true` or `checksum_ok != true`; or `world_seeds`/`playout_seeds` not bit-identical between the ARB and clair-puct records of the same `rid` |
| `G-COVER` | the champion arm is present on **every** analysed position | `ARMS.json[rid]["champ_pos"] == 0` and `arm_order[0] == champ_action`, counted by `analyze_everyply.py` | **any** nonzero absence count — this is 0 by construction (DESIGN §3.1), so a nonzero count is an **instrument defect**, never a finding |
| `G-ARMSET` | the two judges agree on what was scored | per `rid`: every priced arm present in **both** judges' records, and the two `arm_order` lists equal | any missing arm; any `arm_order` disagreement |
| `G-ZEROFILL` | the selective economy is accounted, not silently dropped | `READOUT.json`: `n_priced + n_zero == n_analysed`, and every zero-filled `rid` has `len(arms_to_price) == 1` | either identity false |
| `G-DISTINCT` | the dedup did not eat the corpus | `n_dropped_lt2_distinct / n_planned <= 0.10` (dropped positions are **counted and reported in every case**) | > 10% dropped |
| `G-FRAME` | the realized draw is the committed draw | `PLAN_SUMMARY.json` — `max_abs_f_deviation_pp <= 3.0` **and** `population_weights_w` equals `FRAME.json`'s census-derived `w`; both emitted by `scripts/tiletie/build_everyply_plan.py` | deviation > 3 pp, or `w` differs from the census |
| `G-N` | enough of the plan actually ran | `READOUT.json.n_analysed >= 0.85 * 400 = 340` | fewer than 340 positions analysed at the read point |
| `G-EPOCH` | one leaf, one rules profile, one champion config | `governance/PRODUCTION.yaml` `champion.leaf_hash` (**the `harness_leaf_hash` dialect**) `== a36d2e15a3b3d71d`, stamped per row; every leg's `rules_profile == "walled"`; resolved champion config identical across all rows | any mismatch, any non-`walled` leg, any per-row disagreement |
| `G-CHAMP` | the incumbent is one fixed agent | the resolved agent's own manifest `fair_deploy.k_dets` / `.sims_per_det` **and** the resolved `tiearb` block (`enabled`/`B`/`J`/`mode`/`eps`) stamped on every row and **constant** | any row disagreeing with any other |
| `G-BLIND` | the pre-registration really preceded the numbers | git history: the commit introducing `DESIGN.md` + `READ_RULE.md` precedes the first pricing leg record; `BLIND_COMMIT` in the run manifest equals that sha; **§4 byte-identical across revisions** | ordering violated, `BLIND_COMMIT` still a placeholder, or §4 edited after launch |

### §3.1 — THE STRUCTURAL TEST, applied to EVERY gate above, BEFORE any outcome is known

The question, asked of each gate in turn: **"would this gate FAIL on every healthy run of this
launcher (fail-always), or PASS regardless of what happened (pass-always)?"** Both are defects and
both are fixed **before** game 1, never discovered after. This is the jcz / `tiearb_widening`
precedent that caught unsatisfiable gates before they could void a healthy run.

| gate | fail-always? | pass-always? | why |
|---|---|---|---|
| `G-KNOWNGOOD` | **NO** | **NO** | it reproduced `arb = +0.2065` on the spent corpus when `tiearb` adjudicated; it is an independent binary that a broken estimator import genuinely flips. ⚠️ It is run as the **`knowngood` subcommand only** — `grade`/`preflight`/`sweep` call `require_knowngood` against constants hard-pinned to the OLD corpus and would fail-always here (DESIGN §6.2). Using them would be exactly a fail-always gate. |
| `G-CRN` | **NO** | **NO** | `crn_verified`/`checksum_ok` are written per record by `oracle_score_pilot._process` and were true across the whole tiearb corpus; a genuine seed divergence flips them. |
| `G-COVER` | **NO** | ⚠️ **YES BY CONSTRUCTION — and that is the point** | the champion pick *is* arm 0, so on a healthy run this gate always passes. It is retained deliberately as an **instrument-defect detector** (the `root_stats_list` dedup trap, DESIGN §3.1): the only way it can fail is if the arm-builder is broken. **A pass-always gate is acceptable ONLY when its failure mode is a build defect rather than an experimental outcome; that is the case here and is declared, not discovered.** |
| `G-ARMSET` | **NO** | **NO** | the two judges are driven from the same `ARMS.json`, so agreement is expected; a partial/mixed-rev leg genuinely breaks it. |
| `G-ZEROFILL` | **NO** | **NO** | an identity the analyser must satisfy; a dropped-instead-of-zero-filled position breaks it. It is the one gate that guards the §5.2 economy's unbiasedness. |
| `G-DISTINCT` | **NO** | **NO** | at *tied* plies 80.5% of arms were afterstate duplicates; at **non-tied** plies the top arm is unique by construction, so the `< 2 distinct` class should be **rare**. The 10% bar therefore has real headroom in the expected direction. ⚠️ If it fires, the correct reading is *"the frame is not what the census implied"*, not *"the lever failed."* |
| `G-FRAME` | **NO** | **NO** | the realized deviation is **0.111 pp** against a 3 pp bar on the committed draw (measured, `PLAN_SUMMARY.json`), so a healthy run passes with ~27× margin — and a mis-seeded or hand-edited draw genuinely fails. |
| `G-N` | **NO** | **NO** | 340 of 400; the chunked launcher completes 100/100/100/100, and a partial run is *designed* to be readable at its realized `n` (DESIGN §2.4) down to this floor. |
| `G-EPOCH` | **NO** — **but only after the dialect fix** | **NO** | ⚠️ **This gate WOULD have been fail-always as literally worded in the plan.** The corpus games stamp `leaf_hash_runtime = 6dfffd57051690f2`, which is the `frozen_config_hash_meeple_k0` **dialect** of the *same* leaf whose `harness_leaf_hash` is `a36d2e15a3b3d71d`. A gate comparing the two strings fails on every healthy run. **Fixed pre-freeze by naming the dialect** (DESIGN §10 item 5). This is exactly what the structural test exists to catch. |
| `G-CHAMP` | **NO** | **NO** | `champion_factory` resolves one config per run and `champ_picks.py`'s convention already stamps it per row; a mid-run `PRODUCTION.yaml` edit or a mixed-rev respawn genuinely breaks it. |
| `G-BLIND` | **NO** | **NO** | the launcher hard-refuses without a real 40-hex `BLIND_COMMIT`, and git history is checkable independently of any number. |

**Answer for every gate: NO fail-always.** One gate (`G-COVER`) is **pass-always on a healthy
run**, declared above with its justification: its failure mode is a build defect, not an
experimental outcome, and it is the named guard on the one documented trap in the arm-builder.

---

## §4 — THE BRANCHES

Read **in order**. The FIRST whose condition holds is the branch, **taken verbatim**.
⛔ Subject to **§0.A**: at SIZE-1, `E-CLEAN` and `E-FUND` cannot fire and fall through to
`E-UNRESOLVED`.

| # | branch | condition | what it licenses |
|---|---|---|---|
| 1 | **`E-HARM`** | `κ̂ ≤ −0.15` ∧ `z_κ ≤ −2.0` | Every-ply arbitration is **actively harmful** at non-tied plies. **Lever CLOSED**; the `LEVER_INDEX` row *"every-ply rollout arbitration"* flips to **KILLED**. **Licenses nothing else.** |
| 2 | **`E-CLEAN`** | `κ̂ ≥ +0.35` ∧ `z_κ ≥ +2.0` ∧ ≥ 2 of 3 stratum point estimates ≥ 0 | Licenses **a DESIGN for one deck-paired game cell** (owner decision), resolvable at n = 800 under **both** NA ends. **NOT a game cell.** ⛔ *Unreachable at SIZE-1 (§0.A).* |
| 3 | **`E-FUND`** | `κ̂ ≥ +0.15` ∧ `z_κ ≥ +2.0` ∧ ≥ 2 of 3 stratum point estimates ≥ 0 ∧ `κ̂_holdout ≥ 0` | Same, **but** the read-out must print `n_cell` at **both** NA ends; under the conservative chain the cell it funds is **NOT n=800**. ⛔ *Unreachable at SIZE-1 (§0.A).* |
| 4 | **`E-FLATNULL`** | `UB95(κ̂) < +0.15` ∧ ¬`E-HARM` | **A FUNDING VERDICT, NOT AN EXCLUSION** — the same words `W-FLAT` and `F-FLAT` used. Lever **PARKED** with its printed re-open bar. |
| 5 | **`E-UNRESOLVED`** | anything else | **Nothing closes, nothing is licensed.** The read-out **MUST** print the `n` that would resolve the observed `κ̂` at the **realized** dispersion (the `tiearb` READ_RULE's own discipline). |
| — | **`U-UNREADABLE`** | ANY §3 gate FAILS | No statistic from this run is adjudicated, quoted, or cited. The failed gate is named with its realized value. **`U-UNREADABLE` is a fully acceptable outcome.** |

> ⚠️ **`E-FLATNULL` REACHABILITY IS MARGINAL AND CONDITIONAL — named here, before game 1.**
> At the planning-central `q = 0.76`, n = 400, `se = 0.084` ⇒ `E-FLATNULL` requires
> `κ̂ < 0.15 − 2(0.084) = −0.018`. **The screen can park the lever only if κ̂ comes in at or below
> essentially zero.** That is the *expected* case under all three §6 priors, but it is **not
> guaranteed**, and this screen **must never be described as "it will settle it either way."**
> If the realized `q` comes in **below** 0.76 the bound tightens and `E-FLATNULL` opens up; if `q`
> runs high it closes further. §4.3 item 3 prints `q` and the realized `se` beside `κ̂` on every
> branch **specifically so this reachability condition is checkable rather than inferred.**

⚠️ **If an instrument defect is found after a first adjudication, the session that writes the fix
MUST be a session that has not seen `κ`, `z_κ`, or any per-stratum estimate** — the jcz
precedent's binding instrument-fix discipline, carried here verbatim. **Bars do not move. §4 is
not edited post hoc.**

---

## §4.3 — PRINTED ON EVERY BRANCH, INCLUDING `U-UNREADABLE`

**A. The numbers.**

1. `κ̂`, its cluster-robust `se`, `z_κ`, `n_analysed`, `n_priced`, `n_zero`, `n_roots`, and the
   from-scratch recomputation witness (§1).
2. The **per-stratum** `κ̂_s` with counts and within-stratum `se` (**112/169/169 ⇒ 0.148 / 0.121 /
   0.121** at `q = 0.76`), each explicitly labelled **UNDERPOWERED — SIGN READ AT BEST**.
3. **`q` (`pickchg`)** per fold, pooled and per stratum; the realized `se`; and the realized
   `phi_nontied`. These three are what re-price any top-up.
4. `n_cell` = `800 · (1.38 / pts_per_game)²` at **both** NA ends (0.31 and 0.85), so no branch can
   imply an unfunded cell is cheap.
5. The `n` that would resolve the observed `κ̂` at the **realized** dispersion.
6. `κ̂_holdout` with its `n` — **reported on every branch**, and **flagged as a conjunct that only
   `E-FUND` reads** (which cannot fire at SIZE-1).
7. Which **arm-builder** ran (`pooled_q` or the `leaf_topk` fallback), the distinct-afterstate
   drop count and rate, and every §3 gate with its realized value and the address that resolved it.
8. The resolved champion (`fair_deploy`, `tiearb` block, leaf hash + dialect), rules profile, code
   rev.

**B. The honesty rails — VERBATIM, all nine, on every read-out.**

1. **PRIOR-AGAINST 1 — the mass desert.** The eps census (`K-STRUCTURAL`, corroborated on a fresh
   31,827-ply read) shows **no gentle widening exists between exact ties and eps ≈ 1.5–2.0**: 90%
   of non-tied tile plies sit above a quarter-point of leaf preference. **The plies this probe
   adds are ones where the leaf has a real opinion.**
2. **PRIOR-AGAINST 2 — "the vart".** Tie-triggered search escalation died at its pre-gate
   (`E-FLAT`): 2×/4×/10× more search **moves** tied-ply picks (18/24/31%) but does not **improve**
   them (−0.0094 / +0.0494 / +0.0502, all below the ratio-0.35 ∧ z-2 bar; 10× also failed coverage
   at 0.799). The tie-arbiter's win is an **orthogonal terminal-grounded signal breaking a ply
   where the primary signal is exactly ZERO.** At a non-tied ply it must instead **beat an
   11,008-sim PUCT search, not silence.**
3. **PRIOR-AGAINST 3 — the `RND` control.** Stage-2's matched-compute control read **−4.4287
   pts/game, −60.09 elo**: **a leaf-tied set is NOT a set of interchangeable moves, and the
   champion's own tie-break is far better than arm-average.** The greedy-continuation values carry
   policy bias that is common-mode across arms **only when the primary signal is silent** — which
   is exactly the condition this probe removes.
4. **INCUMBENT ASYMMETRY.** The champion's pick is one of the arms; `κ` is capture-vs-incumbent
   and **negative-capable**; `κ = 0` means *"no better than the champion"*, **not** *"no signal"*;
   and `κ` is **not zero-mean** under an uninformative arbiter.
5. **CURRENCY.** `scale_all ≡ 1.0`; **`κ` is NOT directly comparable to the tied-ply
   `arb = +0.2065`.**
6. **⚠️ OFFLINE CAPTURE HAS UNDER-READ THE GAME CELL ON THIS EXACT AXIS.** At tied plies the
   offline instrument returned `P-PARTIAL` — *not convicted*, with a **negative blind holdout**
   (−0.0051) — and the Stage-2 game cell then fired `G-CONFIRMED` at `z_D` **+8.04**.
   ⇒ **`E-FLATNULL` is a FUNDING verdict, never an exclusion**, in the same words `W-FLAT` and
   `F-FLAT` used. **An offline null here does NOT prove the deploy effect is null; it proves we
   will not spend a game cell on it.**
7. **BUDGET-EPOCH MISMATCH.** The corpus *games* were generated by the k4×688 / 2752-budget
   champion; the *incumbent priced* is whatever `PRODUCTION.yaml` resolves at run time. Inherited
   verbatim from `tiletie_pricing_20260812` and unchanged by this design.
8. **NO DEPLOY IS LICENSED ON ANY BRANCH.** `rho_phone` = 5.520 at B=16 is **unsolved** for the
   *tied-ply* arbiter already; every-ply arbitration roughly doubles the fire rate and therefore
   roughly doubles it again. **Desktop-only at best.**
9. **`SEC-ARB` is circular by construction** and may never be a branch input.

**C. The scope fence, restated on every branch** (DESIGN §4.5, binding): a near-tie-only
deployment would need `κ_A ≥ 1.38 / (1.277 × 0.31) = 3.49` pts/ply against a tied-ply oracle
**ceiling** of **+0.2545** — **~14× the entire oracle headroom of the adjacent ply class.**
⛔ **No branch, and no successor design, may rescue a pooled null by carving out stratum A, a
phase bucket, or any other sub-population.**

**D. If SIZE-1 was truncated** (fewer than 4 chunks completed), state the realized `n`, that the
completed-chunk prefix is a uniform random subsample **at chunk granularity**, and re-check `G-N`.

---

## §5 — WHAT NO BRANCH DOES

No branch flips [`../../governance/PRODUCTION.yaml`](../../governance/PRODUCTION.yaml). No branch
licenses a leaf, search, `B`, `M`, `--oracle-sims`, or arbiter change. No branch re-rates the
champion. No branch licenses an on-device or desktop **deploy**. No branch writes a strength row
to [`../../experiments/results.csv`](../../experiments/results.csv). **No branch claims a deck
band or touches [`../../governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv)**
([`BAND_NOTE.md`](BAND_NOTE.md)). No branch authorizes SIZE-2 or SIZE-3 — a top-up is a **fresh
owner funding decision**, re-priced by the measured `q` (DESIGN §5.4). No branch licenses a game
cell; **`E-CLEAN` at most licenses a DESIGN for one**, and `E-CLEAN` cannot fire at SIZE-1 (§0.A).
**No branch licenses a near-tie-only or any other sub-population deployment** (§4.3 C).

---

## §6 — THE STATED PRIOR, RECORDED BEFORE THE FIRST LEG

**The house prior is that `κ` is negative or indistinguishable from zero.** Three independent,
*mechanistic* priors-against stack (§4.3 B items 1–3), and they are the reason SIZE-1 was funded
as a kill-screen rather than a powered read: the modal outcome is a negative `κ`, and a negative
`κ` is exactly what this size is good at.

**The realistic distribution of outcomes, stated before game 1: ≈ kill / ≈ unresolved**, with a
genuine-but-unlikely large positive that this size **cannot convict** (§0.A).

⚠️ **The honest case against having funded even SIZE-1, recorded so it is not rediscovered as a
disappointment:** rail 6 is real — offline capture *under-read* the game cell on this exact axis —
so a null here is a **funding verdict, not knowledge**, and `E-FLATNULL` is marginal at n = 400.
Two things make the screen worth more than its own verdict regardless of which branch fires: it
produces **the first non-tied CRN-priced corpus in the programme** — every existing priced corpus
is tied-ply-only, and sibling-ranking labels off the leaf's *non*-tied shortlist are the one thing
the CL-065/CL-073 move-discrimination line and the parked tie-net have never had — and it measures
**`q`**, which re-prices any top-up by ~2× in either direction.
