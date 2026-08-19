# THE `B = 64` GAME CELL — READ-RULE (DRAFT)

> **STATUS: DRAFT FOR A SECOND DRAFTER. NOT A PREREGISTRATION. NOT COMMITTED BLIND ON
> `main`. NOTHING LAUNCHED, NO BAND CLAIMED, NO SMOKE RUN, NO GAME PLAYED, NO
> `summary.json` OR `manifest.json` EXISTS FOR EITHER CELL OF THIS RUN.**
>
> **REVIEWED at [`REVIEW_R1.md`](REVIEW_R1.md) (reviewer commit `769da984`) — verdict
> FAIL, all items folded.** ⛔ **B1 changed a gate conjunct: `G-TOOL` no longer treats
> `+rustcunpinned` as a failure** — it is the *normal* production value and the drafted
> row would have voided every healthy run ([DESIGN](DESIGN.md) §13.1, this campaign's
> **third** unsatisfiable-gate catch). **Whoever merges must re-read that row.** R1 added
> §4.0 (the reachable-branch set) and §4.0.1 (`W`'s three mechanical conjuncts); R2 added
> `G-DIVERGE`'s expected-value print. The pair returns to the reviewer for sign-off.
>
> When it becomes a preregistration it must be committed in the **same commit** as
> [`DESIGN.md`](DESIGN.md), so git history proves the ordering, and every run manifest
> must carry that commit's hash.
>
> ⭐ **Launch precondition adopted from B1 ([DESIGN](DESIGN.md) §13.1): every §3 row must
> be evaluated against Stage 2's completed artifacts and PASS on that known-good run,
> before the blind commit.** A gate that fails a healthy run is a drafting defect, and a
> fail-closed gate that *always* fails is not conservative — it is a rule that cannot be
> run.
>
> **This read-rule is written to be FULLY MECHANICAL.** Every branch is a boolean function
> of numbers the harness emits. **No owner call adjudicates any outcome.** The one owner
> input it accepts — the §4 `A` waiver — is a **file whose existence and commit timestamp
> are checked mechanically**, and it must predate game 1; it is never a judgement made at
> read time.
>
> Definitions are frozen by reference to [`DESIGN.md`](DESIGN.md) §1–§9. It is spent on
> this mechanism and this band; any successor needs a fresh one of each.

---

## 1. Scope

- **Two cells**, `WIDE` (`B` = 64) and `NARROW` (`B` = 16), [DESIGN](DESIGN.md) §1.2/§2,
  **`n` = 1,500 deck-paired games each** (750 decks), on **one fresh band claimed at
  claim time from `governance/BAND_REGISTRY.csv`** and **the same decks**, at production
  budget k8×1376 = 11,008, exact-K 2, against the **unmodified champion**.
- **The PRIMARY statistic is `z_D`, the deck-paired difference of margins between the two
  cells.** Each cell's own margin against the champion is **secondary, reported, and
  adjudicates nothing**; win-rate is **reported and adjudicates nothing** (Stage 2
  precedent: the margin convicts, the win-rate does not — realized elo +23.92 CI
  [−0.21, +48.06] with `wr_z` +1.94 on a `z` +4.445 margin).
- **The branch input is a WITHIN-BAND deck-paired contrast, and nothing else.** No
  cross-band comparison is a branch input anywhere (CLAUDE.md cross-band humility:
  1.8–2.2× over-dispersion, *"never pool across bands and quote the pool as an
  estimate"*). In particular **no comparison against Stage 2's band-132e9 numbers is a
  branch input**, and band 132e9 is retired.
- **`governance/PRODUCTION.yaml` is untouched on every branch.** The most any branch does
  is license a **decision for the owner**.

---

## 2. The committed quantities

Every address carries an **existence-time marker** ([DESIGN](DESIGN.md) §3):
`[pre-run]` · `[post-smoke]` · `[post-cells]`. An unmarked address is a **drafting
defect** that must be fixed before the blind commit, never adjudicated at read time.

| symbol | definition | address | marker |
|---|---|---|---|
| `M_w`, `M_n` | per-deck **seat-balanced paired margin** (pts/game) of the cell's candidate vs the champion | `summary.json::paired_mean_margin` | `[post-cells]` |
| `z_w`, `z_n` | `summary.json::paired_z` (`_paired_z`) — **secondary, adjudicates nothing** | `summary.json::paired_z` | `[post-cells]` |
| `E_w`, `E_n` | the same in elo, by the harness's own conversion, with CI | `summary.json::{elo, elo_sig_1sigma}` | `[post-cells]` |
| `wr_w`, `wr_n` | win-rate and its z — **reported, adjudicates nothing** | `summary.json::{winrate, winrate_z}` | `[post-cells]` |
| ⭐ **`D`** | `M_w − M_n`, **deck-paired over the decks completed in BOTH cells** | analyzer, over `seed*.json` | `[post-cells]` |
| ⭐ **`z_D`** | `D` over its own paired se, computed exactly as `paired_z` — **THE PRIMARY** | analyzer | `[post-cells]` |
| `se_D` | the paired standard error of `D` | analyzer | `[post-cells]` |
| `rho` | realized cross-cell per-deck correlation, back-derived from `se_D`, `se_w`, `se_n` | analyzer | `[post-cells]` |
| `f₀` | fraction of common decks with `D_i` **exactly** 0.0 | analyzer | `[post-cells]` |
| `n_common` | decks completed in **both** cells (the denominator of `D`) | analyzer | `[post-cells]` |
| `phi_x`, `phi_effective_x` | realized fired tied tile plies/game; `phi × (1 − error_rate_on_fired)` | `summary.json::tiearb_phi`, `tiearb_error_rate_on_fired` | `[post-cells]` |
| `ms_ratio_x` | `champ_prefix_ms_per_move / rung_ms_per_move`, in-cell, per cell | `summary.json` | `[post-cells]` |
| `F_w`, `F_n` | failed games per cell; `n_attempted_x` the attempted count | `summary.json::{n_failed, …}` | `[post-cells]` |
| `A` | the affordability predicate, §4 | `[pre-run]` constant ∨ `OWNER_WAIVER.md` | `[pre-run]` |
| — | smoke cost keys, §9 of DESIGN | `SMOKE.json` | `[post-smoke]` |

**The bars are `+2.0` and `+1.0` (both on `z_D`), and the `A` disjunction.** Neither
z-bar is a new constant: `+2.0` is Stage 1's, Stage 1b's, Stage 2 Phase B's, `E-FLAT`'s
and `W-FLAT`'s verbatim; `+1.0` is Stage 2 Phase B's `G-PRESENT`/`G-FLAT` presentation
split. ⚠️ **`+1.0` is not an adjudicating bar** — both branches it separates license
nothing, so it selects a **label and its mandatory rider**, never a permission.

⚠️ **THE FIELD-NAME TRAP, carried:** `champ_prefix_ms_per_move` **IS THE CANDIDATE SIDE**
in `eval_fair_puct.py` (live lines 2361/2371/2389 — the opposite of `eval_puct_priors`).
A read-out that swaps them inverts the cost verdict.

⚠️ **MANIFEST RESOLUTION IS TWO-LEVEL.** Every `manifest.json` address is read **at the
top level, else under `config.`**, and the read-out **prints which was found**. Absent
under both is a failure, not a pass. *(Stage 2 lost an entire adjudication pass to this:
`G-J1` and `G-BAND` read `null` at the top level while the witnesses sat correct under
`config.`.)*

---

## 3. Preconditions — checked FIRST, and they void the run

**`U-UNREADABLE` fires, and no other branch may fire, if ANY of the following holds.**

Every gate carries a **scope marker** ([`rung3_r5/DESIGN.md`](../rung3_r5/DESIGN.md)
§R5-6, adapted from strata to cells). **An unmarked gate is a DRAFTING DEFECT.** A gate
with conjuncts of mixed scope must be SPLIT into separately-named gates.

| marker | meaning | on a single-cell failure |
|---|---|---|
| `[RUN]` | whole-run conjunct (cross-cell quantities) | the **run** fails; no cell is readable |
| `[PER-CELL]` | evaluated separately per cell | ⚠️ **the RUN still fails** — `D` is a two-cell statistic and there is no single-cell reading of this design; the marker records *where* the failure was, not that anything survives it |

⭐ **`[PER-CELL]` here is deliberately NOT the rung3_r5 "the other stratum remains
readable" semantics**, because this run has no per-cell estimand: the primary is a
contrast. Stated in the row rather than inferred, which is exactly what R4's unmarked
`G-DISJOINT` failed to do.

| id | scope | marker | condition |
|---|---|---|---|
| `G-J1` | `[PER-CELL]` | `[post-cells]` | either cell's resolved `cand_leaf_hash` **differs** from the champion's `a36d2e15a3b3d71d`, or is absent under both levels. ⚠️ **Inverted gate: a difference is an ABORT, not a finding** |
| `G-J4` | `[PER-CELL]` | `[post-cells]` | `cand_tiearb` is absent or unresolved in either `manifest.json`, **or** `WIDE`'s resolved dict is not exactly `{enabled: true, B: 64, J: 4, mode: "argmax", salt: "tiearb2-deploy-v1", eps: 0.0}`, **or** `NARROW`'s is not the same with `B: 16`. ⚠️ Also fails if `summary.json::tiearb_B` is not the singleton `[64]` / `[16]` respectively, or `tiearb_J` not `[4]`, or `tiearb_modes` not `["argmax"]` — **a mixed-`B` cell is a void, not a finding** |
| `G-J13` | `[PER-CELL]` | `[pre-run]` | the **two-sided** positive control did not pass **at BOTH `B` values**, on **each** host, **before that host's game 1** (`PREFLIGHT_*_${HOST}_FIRST.json`): the arbiter must **change the pick** at a constructed tied ply **and** leave `root_leaf_value_bits` **unchanged**. ⚠️ Absent file ⇒ fail |
| ⭐ `G-NEST` | `[RUN]` | `[pre-run]` | `GATE_NEST.json` is absent, or its witness is false: at HEAD, for a pinned position/ply/salt, the world seeds and playout seeds generated at `B` = 64 for `j ∈ 0..15` are **byte-identical** to those generated at `B` = 16, and the `build_arms` cap draw and the selection stream are identical. ⚠️ **Without nesting, `WIDE` and `NARROW` are two unrelated draws and the whole "increment" framing is void** ([DESIGN](DESIGN.md) §1.3) |
| `G-FIRE` | `[PER-CELL]` | `[post-cells]` | `phi_effective < 1.0` in either cell — the arbitration surface is inert and the cell grades a champion-vs-champion null wearing the shape of a real cell |
| ⭐ `G-DIVERGE` | `[RUN]` | `[post-cells]` | `1 − f₀ < 0.10`, i.e. fewer than 10% of common decks produced any difference between the two cells. ⚠️ **The widening surface is inert relative to the deployed one**: ≥90% of the paired sample contributes exactly zero to `D` by construction, and the cell would be grading a `B=16`-vs-`B=16` null wearing the shape of a real contrast. ⭐ **SANITY-CHECKED AT REVIEW, floor KEPT at 0.10 (R1 ruling 5).** The offline pick-churn per doubling is **≈0.29 per fired ply** (0.303 / 0.309 / 0.290 / 0.287), and a deck carries ≈35 fired plies (`phi` 17.5725 × 2 seats) ⇒ **the EXPECTED `1 − f₀` is `1 − 0.71^35` ≈ 1.0.** ⇒ **0.10 carries ≈10× headroom: it is an INERTNESS detector, not a power check**, and that looseness is deliberate — a tighter floor would risk failing a healthy run, which is this campaign's most-repeated defect. ⚠️ **Consequence, and it is why R2 requires the expected value printed:** a realized `1 − f₀` of, say, 0.15 would **pass** while sitting wildly below expectation. **A barely-passing value must be legible as an anomaly, not read as a pass** — §4.3 item 3 prints the expected ≈1.0 beside the realized on every branch |
| `G-BAND` | `[RUN]` | `[pre-run]`+`[post-cells]` | the band was not claimed from `governance/BAND_REGISTRY.csv` **before game 1** (no `BAND_CLAIM.json` sentinel predating the first record), **or** the two cells did not run on the **same band and the same decks** (`config.band_seed_start` equal, realized deck sets identical) |
| `G-N` | `[RUN]`+`[PER-CELL]` | `[post-cells]` | `n_common < 600` **decks**, **or** either cell completed fewer than **1,200** of its **1,500** paired **games**. ⚠️ Both clauses are the **same 80% bar** in the two units (1,200 games **is** 600 decks); the deck clause is **independently binding** because two cells can each clear 1,200 games while overlapping on fewer than 600 *common* decks |
| ⭐ `G-FAILED` | `[RUN]`+`[PER-CELL]` | `[post-cells]` | **any of the three clauses of [DESIGN](DESIGN.md) §8**: (1) `F_x / n_attempted_x > 0.02` in either cell; (2) `max(F_w,F_n) ≥ 5` **and** `max(F_w,F_n) > 3 × max(min(F_w,F_n), 1)` — candidate-correlated exclusion, the `capoff` pattern; (3) **any** failed game whose diagnostic class is **not** the known `WindowTruncationError` class ⇒ RAISE and escalate regardless of count |
| `G-TOOL` | `[RUN]` | `[pre-run]`+`[post-cells]` | ⭐ **THE CONJUNCT IS EQUALITY OF `carc_rs_build` ACROSS BOXES, AND NOTHING ELSE.** Fires if the two boxes' `carc_rs_build` values **differ**, or if a cell mixed builds. ⚠️ The authoritative witness is **`carc_rs_build`** = `carc_rs-<version>+<full-commit[:12]>+rustc<toolchain>`, sliced from the **full** commit (`core.abbrev` is per-box: the same commit rendered `cf51bf17` locally and `cf51bf176b` on the laptop); `carc_rs_binary_sha` is a **box-local** "rebuilt here" witness and must **never** be compared across boxes (the `.so` is not reproducible cross-machine); the authoritative cross-box comparison is the two `PREFLIGHT_*_${HOST}_FIRST.json` files, **not** the manifests (under `--shared-claim` the second box writes no manifest, so `mixed_builds` on a manifest is the writer's own observation and cannot see the other box). ⛔ **`+rustcunpinned` is NOT a failure and NOT a sentinel — it is the NORMAL production value**: `src/carcassonne_ai/rust_agent.py:372` is `tc = os.environ.get("RUSTUP_TOOLCHAIN") or "unpinned"`, and [`DEVIATIONS.md`](../DEVIATIONS.md) §D4.13 records **both boxes** emitting exactly `carc_rs-0.1.0+58c2b5395569+rustcunpinned` on the R4 run. **`unpinned` passes provided it is EQUAL on both boxes.** If pinned toolchains are wanted, that is a change to the launch environment (`WORKERS.conf::RUST_TOOLCHAIN`), **never** a gate conjunct that voids the run — see [DESIGN](DESIGN.md) §13 |
| `G-PLY` | `[PER-CELL]` | `[post-cells]` | `tiearb_partial_argmax_total` is **absent, or non-zero**, in either cell. **Absent is unknown-not-zero and fails.** Non-zero means an argmax was taken over a partial world set ⇒ the CRN pairing across arms was broken during play, so the comparison is void whatever the margins say |
| `G-STAT` | `[RUN]` | `[post-cells]` | `z_D`, `D`, `se_D`, `z_w` or `z_n` is `NaN` or absent |
| `G-SMOKE` | `[RUN]` | `[post-smoke]` | the smoke did not run at production knobs before game 1, **or** it HALTed on [DESIGN](DESIGN.md) §9.3 and the cells were launched anyway, **or** `SMOKE.json` contains any forbidden outcome key (§9.2's whitelist is fail-closed) |

`U-UNREADABLE` = report cost, integrity, firing rates, divergence, the failed-record
accounting, and **whichever gate(s) failed — all of them, never short-circuited at the
first.** *(R3.3's corpus driver aborted under `set -e` at the first failing gate and
`GATE_DRAW.json` was never emitted; the gate suite here runs every check and prints every
result.)* **Nothing closes, nothing is licensed, nothing is re-labelled.**

---

## 4. Branches

**Evaluated in this order. `U-UNREADABLE` (§3) pre-empts everything.**

Definitions:

```
A  ==  ( rho_wall(64) <= 1.20 )
       OR
       W                                     # the waiver predicate, defined below

p  ==  z_D >= +2.0        # widening buys game points over the deployed arbiter, resolved
```

⭐ **`rho_wall(64)` = 2.4897 is a COMMITTED ARITHMETIC CONSTANT, not a measurement to
come** — Phase A measured `rho_wall(16)` = 0.6224 and the arbiter's cost is exactly linear
in `B` ([DESIGN](DESIGN.md) §4, §7.2). ⇒ **the first disjunct of `A` is FALSE, and this
read-rule says so before game 1.**

### 4.0 ⭐ THE REACHABLE BRANCH SET, stated BEFORE the run

**`A` is decided entirely by `W`. Therefore, stated as a set rather than left to be
discovered in the read-out:**

| if | reachable branches | unreachable |
|---|---|---|
| **`W` is FALSE** (no waiver on the record before game 1) | `{B-REVERSED, B-COSTKILL, B-PRESENT, B-FLAT, U-UNREADABLE}` | ⛔ **`B-CONFIRMED` is UNREACHABLE** |
| `W` is TRUE | all six | — |

⭐ **AND `W` IS EXPECTED TO BE FALSE.** No waiver exists at drafting time, the owner is
away under a 20-hour delegation, and **obtaining one is outside a drafting delegation**
([DESIGN](DESIGN.md) §10 ruling 2). ⇒ **the realistic ceiling of this run is
`B-COSTKILL`: a `z_D ≥ +2.0` win fires `B-COSTKILL`, not `B-CONFIRMED`, and licenses
nothing deployable.** That is stated plainly here, before the band claim, and it is not
hedged: **a win at `B` = 64 is a scientific result, not a deploy licence, unless the owner
moved the cost bar in writing first.**

⚠️ **This declaration is the Stage-2 `G-N` lesson applied prospectively.** Stage 2's `G-N`
was *unreachable by construction* and nobody noticed until an instrument sweep found it,
because no document ever stated the reachable set. **An unreachable headline branch must
be visible before the run, not discovered in the read-out.** `B-CONFIRMED` is retained in
the table rather than deleted because `W` is a genuine two-valued predicate the owner may
still flip before game 1 — but it is **flagged unreachable-by-default here** so no reader
can mistake its presence for an expectation.

### 4.0.1 `W` — the waiver predicate, mechanical in all three of its conjuncts

`W` is TRUE **iff all three hold**; any one absent ⇒ `W` is FALSE (fail-closed):

1. **EXISTENCE** — a file `OWNER_WAIVER.md` exists in this directory and is tracked.
2. **ORDERING** — its **git commit timestamp strictly precedes** the `BAND_CLAIM.json`
   sentinel's timestamp, i.e. the waiver was on the record **before game 1** and before
   any statistic of this run could exist.
3. ⭐ **CONTENT, checked by a COMMITTED PATTERN, not by judgement.** The file must contain
   **at least one line matching, case-sensitively, the regex**

   ```
   ^> OWNER WAIVER \(N4 rho_wall, B > 16\), (20[0-9]{2}-[01][0-9]-[0-3][0-9]): "(.+)"$
   ```

   i.e. a blockquote line naming **`N4 rho_wall`**, naming the rung **`B > 16`**, carrying
   an **ISO date**, and carrying a **non-empty verbatim owner quote**. The read-out prints
   the captured date and quote in full on every branch.

⚠️ **Conjunct 3 is what makes `W` mechanical rather than a human judgement wearing a file
check's clothes.** The adjudicator matches the pattern; it does not read the quote for
meaning. **Composing a line that matches the pattern is the owner's act, not the
adjudicator's** — and if the owner's actual words do not fit the form, the correct
response is to ask him to restate them in it, **never** for a reader to decide the quote
"means" a waiver. ⛔ **No other route to `A` exists.** In particular the Stage-2 §0.D
waiver does **not** satisfy conjunct 3: it names neither `rho_wall` nor `B > 16`, and its
own anti-gaming clause bounded it at `B` = 16 ([DESIGN](DESIGN.md) §0.4, §4 item 2).

**Then, pre-emptively:**

```
B-REVERSED  ==  z_D <= -2.0
```

| # | condition | read |
|---|---|---|
| **`B-REVERSED`** | `z_D ≤ −2.0` | ⛔ **WIDENING THE SELECTION WORLDS FROM 16 TO 64 MAKES THE ARBITER WORSE IN GAMES, AT 2σ, ON A FRESH BAND.** ⚠️ **Mandatory rider, never separated from the verdict:** this is a **direct tension with the offline `W-RISING` read** (`Δ(16→64)` = +0.0670 pts/tied ply, CI95 [+0.0215, +0.1111], z +2.94, `n` 1,340 plies / 748 roots, committed floor +0.04). **Print both, and do NOT present the tension as resolved.** The offline read stands as adjudicated and this branch does not re-adjudicate it; what it establishes is that the offline→game map fails in *this* direction too, which is a first-class finding about the map. **Nothing closes and nothing is licensed**; the deployed `B` = 16 shape is untouched, and this branch **does** license a decision for the owner **to leave it untouched**. |
| **`B-CONFIRMED`** | `p ∧ A` | ⛔ **UNREACHABLE UNLESS `W` IS TRUE — see §4.0. Absent a conforming, pre-dated `OWNER_WAIVER.md`, this branch cannot fire and a win fires `B-COSTKILL` instead.** ⭐ **WIDENING TO `B` = 64 BUYS GAME POINTS OVER THE DEPLOYED ARBITER, RESOLVED AT 2σ ON A FRESH BAND, AT A RUNG THE OWNER HAS RULED AFFORDABLE.** **Licenses (does NOT do) exactly one thing: a production-flip DECISION for the owner, from `B` = 16 to `B` = 64.** That decision must be put to him carrying the realized `ms_ratio_w` at its true magnitude (projected ≈6.50× the champion's contended per-move wall), `rho_wall(64)` = 2.4897 against the N4 bar of 1.20, and `rho_phone(64)` ∈ {23.90, 22.08} **labelled NOT SOLVED**. ⛔ It does not flip `PRODUCTION.yaml`, does not license an on-device deploy, does not license a leaf term, does not resolve the ladder's shape, and does not license a second cell. |
| **`B-COSTKILL`** | `p ∧ ¬A` | ⭐ **THE EXPECTED BRANCH ON A WIN (§4.0).** ⛔ **THE WIDENING WINS AND THE RUNG IS UNAFFORDABLE — A WIN THAT CANNOT BE BOUGHT.** `z_D ≥ +2.0`, and `rho_wall(64)` = **2.4897**, **2.07× the house N4 bar of 1.20**, with no owner waiver on the record predating game 1. **Licenses NOTHING deployable.** It licenses exactly two things, both of which require a fresh preregistration or a fresh owner ruling and neither of which is taken here: (i) a **fresh owner wall-clock ruling** on whether the N4 bar moves above `B` = 16 — [`PLAN_B_gt_16.md`](../PLAN_B_gt_16.md) §6 question 3, still unanswered; and (ii) a **ladder question** — whether a rung between 16 and 64 is both affordable and captures most of the gain (`Δ(16→32)` = +0.0597 is 89% of `Δ(16→64)` **offline**) — ⚠️ which this cell **did not measure in game points** and which **no branch may infer from two points**. ⛔ **AND THE LADDER QUESTION IS NOT A CHEAPER ROUTE TO A DEPLOY: `rho_wall(32)` = 1.2449 ALSO EXCEEDS 1.20** (by 3.7%), so **`A` is FALSE for `B` = 32 too** — a `B` = 32 win would **also** be `B-COSTKILL`. Reaching "affordable" at any rung above 16 needs the **same waiver**, or a genuine 3.7% cost reduction, and neither is licensed here. ⛔ **On-device is dead at this rung regardless** (`rho_phone(64)` ≈ 24, a third currency, out of scope). |
| **`B-PRESENT`** | `¬p ∧ ¬B-REVERSED ∧ z_D ≥ +1.0` | **PRESENT BUT NOT CONVICTED — UNRESOLVED.** The direction is there and the bar is not met. **Nothing closes and nothing is licensed.** Report both cells, `D`, `se_D`, `z_D`, `rho`, `f₀`, both `phi`, both `ms_ratio`, and **the `n` that would convict at the REALIZED dispersion** — and print it beside [DESIGN](DESIGN.md) §6.3's pre-registered figure so the reader can see whether the dispersion model held. |
| **`B-FLAT`** | `−2.0 < z_D < +1.0` | **WIDENING FROM 16 TO 64 DID NOT EXPRESS AS DECK-PAIRED GAME POINTS AT `n` = 1,500 PER CELL ON A FRESH BAND.** ⚠️ **Mandatory scope sentence, quoted with the verdict and never separated from it:** *"This is a BOUNDED null, not an exclusion, and it does NOT refute `W-RISING`. [DESIGN](DESIGN.md) §6.2 states before the run that `n` = 1,500 deck-paired per cell resolves a 2σ floor of +1.427 pts/game at `ρ` = 0, while §5.2's pre-registered effect bracket is [+0.368, +1.435] pts/game — a 3.9× band whose lower ~74% this cell cannot reach. Convicting the naive floor (+0.368) needs n ≈ 22,540 games/cell ≈ 8,693 worker-h. The honest claim is 'widening B from 16 to 64 did not express as deck-paired game points at n = 1,500 on this band', NOT 'widening is worth nothing'. `W-RISING` is an OFFLINE per-tied-ply read on a different corpus in a different currency, it stands as adjudicated, and this branch does not re-adjudicate it."* **Rider, mandatory when it applies:** if the realized 95% upper bound on `D` is below **+0.368**, the read-out must **additionally** state that the pre-registered bracket is excluded at 95% and the scope sentence is superseded in that one respect. **Second rider, mandatory always on this branch:** print `f₀` and the realized `√(1−f₀)` dilution factor, because a flat read on a surface that rarely disagrees is a **thin** measurement rather than a null one ([DESIGN](DESIGN.md) §1.3 item 2), and the two must not be conflated. |
| **`U-UNREADABLE`** | any §3 precondition fails | §3. |

### 4.1 Exclusivity and exhaustiveness — verified in the pre-registration text

- §3 is evaluated **first** and pre-empts everything. `B-REVERSED` is evaluated **second**
  and pre-empts the rest, so the remaining four are evaluated only where `z_D > −2.0`.
- On that complement the four partition `z_D ∈ (−2.0, +∞)` exactly:
  `z_D ≥ +2.0` splits on `A` into `B-CONFIRMED` / `B-COSTKILL` (`A` is two-valued and
  total); `+1.0 ≤ z_D < +2.0` → `B-PRESENT`; `−2.0 < z_D < +1.0` → `B-FLAT`.
  The three `z_D` intervals are disjoint and their union is `(−2.0, +∞)`.
- ⇒ **exactly one branch matches every possible read, and the match does not depend on
  presentation order.** Any `NaN` in `z_D`/`D`/`se_D`/`z_w`/`z_n` is caught by `G-STAT`
  in §3 **before** a comparison is taken, so no branch is entered on a `NaN` comparison.
- **To be verified by a machine sweep over the branch-condition truth table** in a test
  that **re-transcribes this section independently of the implementation** and asserts
  exactly one branch fires on every cell, `NaN` and both values of `A` included. *(This
  test does not exist yet and is a launch precondition — Stage 2's equivalent
  `tests/test_tiearb2_stage2.py` §4.1 sweep is the template, and it is what found Stage
  2's unreachable `G-N` before any number existed.)*

### 4.2 The cost rider — applied to every branch, and it is NEVER a branch input

`ms_ratio_w` and `ms_ratio_n` are **reported on every branch, and grade nothing.**

- ⛔ **`ms_ratio` is NOT a branch input anywhere in this rule.** The affordability question
  is carried by `A`, which is a `[pre-run]` arithmetic constant plus a `[pre-run]` file
  check — **not** by an in-cell measurement, precisely so that a cost measurement taken
  after the strength numbers exist can never move a branch.
- **`D` and `z_D` are cost-immune only in part, and the read-out must say which part.**
  `WIDE` and `NARROW` are **not** cost-matched to each other (`WIDE` spends 2.23× the
  worker-seconds per game) — unlike Stage 2's `ARB`/`RND`, which were matched by
  construction. ⚠️ **But neither candidate's search budget moves**: both run the identical
  champion at k8×1376 with identical sims, and the arbiter fires *after* the search, at
  the root, on an already-resolved tie. ⇒ **the extra cost buys no extra search**, so the
  contrast is not a budget confound in the sense the N4 bar polices. **It is a wall-clock
  asymmetry and it is disclosed as one, on every branch, rather than being claimed away.**
- The **prediction-vs-realized** table of [DESIGN](DESIGN.md) §9.4 is printed on every
  branch. A wrong cost model must stay visible even where no bar is enforced.
- ⚠️ **The field-name trap** (§2) is named in the read-out beside every `ms_ratio`.
- ⚠️ **The smoke's `ms_ratio` and the cells' `ms_ratio` are both printed and NEITHER
  grades the other** (Stage 2 §0.H, carried): a bar written after a smoke number exists is
  not a bar, and no such bar was pre-registered.

### 4.3 Mandatory on every branch — the full companion table

The read-out MUST print, on **every** branch including `U-UNREADABLE`:

1. **Both cells:** `n` attempted, `n` completed, `n_common`, `M`, `se`, `paired_z`, elo
   with CI, `wr` with `wr_z`, W/D/L, and the seat balance.
2. **The `D` block:** `D`, `se_D`, `z_D`, `n_common`, the realized `rho`, and the `n` that
   would resolve `D` to 2σ **at the realized dispersion** — printed **beside**
   [DESIGN](DESIGN.md) §6.2's pre-registered `se(D)` = 0.7133 and floor +1.427, so a
   dispersion-model miss is visible the way Stage 2's §0.G cost miss was.
3. ⭐ **The divergence block:** `f₀`, `1 − f₀` against `G-DIVERGE`'s 0.10 floor **and
   beside the EXPECTED `1 − f₀` ≈ 1.0** (§3's derivation: churn ≈0.29/fired ply × ≈35
   fired plies/deck), the ≈10× headroom that implies, the `√(1−f₀)` dilution factor, and
   [DESIGN](DESIGN.md) §1.3's nested-CRN statement. ⚠️ **A realized `1 − f₀` materially
   below ≈1.0 that still clears 0.10 is an ANOMALY and must be reported as one, never as
   a pass.** Plus the measurement disclosure: `f₀` is measured as "`D_i` exactly 0.0",
   which **overcounts** identity (two different games can coincide on margin) ⇒ `1 − f₀`
   **undercounts** divergence ⇒ **the floor is CONSERVATIVE**, it can only fire early,
   never late.
4. **`phi_w`, `phi_n`, `phi_effective` for both**, beside the offline prior **22.96** and
   Stage 2's realized **17.5725 / 17.865**, with [DESIGN](DESIGN.md) §7.2's `phi`-equality
   assumption restated and the realized cross-cell `phi` difference printed.
5. **`ms_ratio` for both cells** with the field-name trap named, the §4.2 rider, and the
   §9.4 prediction-vs-realized table.
6. **Every §3 gate with its realized value and its scope marker**, all of them, never
   short-circuited — including the two-sided `G-J13` witness **per host and per `B`
   value**, and the `G-NEST` witness.
7. **The failed-record accounting in full** ([DESIGN](DESIGN.md) §8): `F_w`, `F_n`,
   `n_attempted`, the realized rates against the 2% bar, clause 2's ratio, the diagnostic
   class of every failure, `tiearb_errors_total`, `tiearb_error_rate_on_fired`,
   `tiearb_first_error`, `tiearb_partial_argmax_total` — **printed whether or not any
   failure occurred**, and with the geometry-correlation disclosure sentence.
8. **The cost facts of record:** `rho_wall(16)` 0.6224 (Phase A, measured) and
   `rho_wall(64)` **2.4897** (×4, exact linearity) against the N4 bar **1.20**;
   `rho_phone(64)` ∈ {**23.90** (PLAN_B), **22.08** (Phase A ×4)} labelled **NOT SOLVED**
   and **a third currency**; the realized worker-s/game for both cells against
   [DESIGN](DESIGN.md) §7.2's committed 958.794 / 429.612; the realized two-box wall
   against §7.4's committed 13.24 h.
9. ⭐ **The `W-RISING` verdict carried VERBATIM** — *"lower(CI)>0, d>=0.04, arb_64
   convicts, arb(64)>arb(16)"*, `Δ(16→64)` = 0.0670 CI95 [0.0215, 0.1111] — **together
   with its own scope fence carried verbatim**: *"a null here would have meant 'no rung
   above 16 is worth ≥ +0.04 pts/tied ply', NOT Δ = 0 … the saturating-exp (+0.017) and
   √B-noise (+0.021) models are NOT resolved by this design."*
10. ⭐ **The 3.9× translation caveat carried VERBATIM, and its both-directions rider**:
    *"Stage 1b's +0.1441 pts/tied ply predicts +0.79 pts/game … Phase B realized +3.07 — a
    3.9× under-prediction. So Δ(16→64) = +0.064 maps to anywhere from +0.35 (naive) to
    +1.4 (realized-ratio) pts/game."* and *"the offline→game map is unestablished and
    +0.0670 × 3.9 is not a projection either"*. ⛔ **The offline ratio arb64/arb16 =
    0.2015/0.1345 = 1.498 may be printed as a description of the offline ladder and MUST
    NOT be presented as a projection of the game effect.**
11. **The realized band, the deck range, and the `BAND_REGISTRY` claim row.**
12. **This rule's own blind-commit hash**, and the assertion that it and
    [`DESIGN.md`](DESIGN.md) landed in the same commit before the band claim.

---

## 5. What no branch does

- **No branch edits `governance/PRODUCTION.yaml`.** A pass licenses a production-flip
  **DECISION for the owner** and nothing more. The deployed `B` = 16 / `J` = 4 shape is
  untouched by every branch of this rule.
- **No branch licenses an on-device / phone deploy.** `rho_phone(64)` ≈ 24 — the phone
  currency was never solved even at `B` = 16 (5.520/5.976, *reported, unadjudicated*), and
  `B` > 16 is dead there by ~20×.
- **No branch resolves the ladder's SHAPE.** Two points in game points cannot separate
  "still rising", "saturating-exp" and "√B-noise", and `W-RISING` already declined to.
  **No branch may name `B` = 64 an optimum, and no branch may infer anything about
  `B` = 32 from these two cells.**
- **No branch adds a leaf term, changes the production leaf, or trains anything.**
- **No branch re-reads, re-labels or re-adjudicates** Stage 1, Stage 1b, Phase A, Stage 2
  Phase B, or the R4 widening run (rung 2 `W-RISING` or rung 3 `VOID_S2`). They stand as
  adjudicated; their read-rules are spent and their bands retired.
- **No branch resizes `n`, reopens the trigger, narrows the tie predicate, changes `J`,
  `eps` or the salt, or truncates the playout.** Cost is explicitly **not** a reason to
  revisit any of them (Stage 2 §0.D's anti-gaming clause, carried in spirit to this rung).
- **No branch licenses a second game cell.** ⭐ **This read-rule is SPENT when the read-out
  lands, on every branch, and the band retires from confirmatory use.** Any successor —
  including a `B` = 32 cell, a head-to-head cell behind an opponent-side knob, or an
  extension of `n` — needs a fresh pair and a fresh band.
