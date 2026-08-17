# STAGE 2 — PHASE B: THE DECK-PAIRED GAME CELL (READ-RULE)

> **STATUS AT WRITING: COMMITTED BEFORE THE INSTRUMENT AND BEFORE ONE GAME EXISTS.**
> No rust arbitration knob, no runtime tie-detector, no positive control, no band
> claim, no `summary.json`, no `manifest.json` for any cell of this run exists at the
> time of this commit. It is committed in the **same commit** as
> [DESIGN.md](DESIGN.md). Git history proves the ordering and every run manifest
> carries this commit's hash. Definitions are frozen here by reference to DESIGN §1–§7.
>
> **This read-rule is fully mechanical.** Every branch is a boolean function of numbers
> the harness emits. **No owner call adjudicates any outcome.** It is spent on this
> mechanism and this band; any successor needs a fresh one of each.

## 0. PRE-RUN AMENDMENT — applied BEFORE the band claim and BEFORE one game is played

> **Amended 2026-08-17, after `b2faa238` and before `claim_next_band.py` was run.**
> At the time of this amendment: **no band is claimed, no game has been played, no
> `summary.json` or `manifest.json` exists for either cell, and no statistic of any
> kind exists anywhere.** The amendment is therefore made under the house pre-run
> amendment discipline, on the `measurement/tiearb2_20260816/DESIGN.md` §0.A
> precedent, and **this text is the audit trail** — the defect is stated verbatim
> before it is resolved.
>
> ⚠️ **It was found by the instrument's own exhaustiveness sweep
> (`tests/test_tiearb2_stage2.py`, 77 tests, commit `3bd1ff7d`), NOT by looking at a
> number.** No number existed to look at. The adjudicator had already implemented the
> committed text **verbatim** and stamped `STAGE2_G_N_INCONSISTENCY` on every branch,
> which is the correct behaviour for an instrument facing an incoherent rule.

### 0.A The defect, stated verbatim before it is resolved

§3's `G-N` precondition, as committed at `b2faa238`, reads:

> | `G-N` | `n_common < 600`, **or** either cell completed fewer than 640 of its 800 paired games |

and §2 defines:

> | `n_common` | decks completed in **both** cells (the denominator of `D`) |

**These are incoherent.** `n_common` is denominated in **decks**, but `600` was written
as though it were **games**. `eval_fair_puct.py:3924` computes
`"n_decks": (args.n // 2 if args.paired else args.n)`, so the design's
`--paired --n 800` yields **400 decks per cell — a hard ceiling.** A floor of
`n_common ≥ 600` decks is therefore **unreachable by construction**, and `G-N` would
fire on a *perfectly complete* run, voiding the cell unconditionally. The second clause
cannot rescue it: 640 completed games is 320 decks, which is also below 600.

⇒ **Left unamended, this read-rule can only ever return `U-UNREADABLE`.** That is not a
conservative failure mode; it is a rule that cannot be run.

### 0.B The resolution, and why it is the direction §1/§6 already implied

The surviving clause — *"fewer than 640 of its 800 paired games"* — is an **80%
completion bar**, and it is the clause that was written in the correct units. The
deck-side floor is set to its **exact analogue**: **80% of the 400 decks a paired
n = 800 cell can produce**, i.e. **`n_common ≥ 320` decks**. `640` games *is* `320`
decks, so after the amendment the two clauses agree at 80% instead of contradicting
each other, and the deck clause remains **independently binding** (two cells could each
complete ≥ 640 games while overlapping on fewer than 320 *common* decks, which would
silently weaken `D`).

**`G-N` as amended:**

> `n_common < 320` **(decks)**, **or** either cell completed fewer than **640** of its
> **800** paired **games**

⚠️ **No bar that adjudicates a finding is touched.** `+2.0`, `+1.0` and `1.20` are
unchanged, every branch condition in §4 is unchanged, and the amendment strictly
*restores* the possibility of a readable run rather than making any branch easier to
reach. The 80% figure is not a new constant — it is the committed 640/800 clause
re-expressed in the units §2 defined.

### 0.C Two further corrections, both report-only in the original

Found in the same sweep; neither can change a branch.

1. **§2's bar sentence did not name the `+1.0` threshold** that §4's
   `G-PRESENT` / `G-FLAT` split uses. It is now named. ⚠️ Stated plainly so it cannot
   be mistaken for a smuggled bar: **`+1.0` chooses between two branches that both
   license NOTHING** (`G-PRESENT` and `G-FLAT` are alike non-licensing), so it cannot
   change what this run permits — it selects a *label* and the mandatory rider that
   travels with it. The two bars that gate a licence remain `+2.0` and `1.20`.
2. **The knob's manifest location** was written as `config.cand_tiearb` in §3 `G-J4`
   and DESIGN §4, but **every shipped sibling knob resolves at manifest TOP level**.
   Corrected to top-level **`cand_tiearb`**, to match the siblings. The analyser reads
   **both** spellings and reports which it found, so this is hygiene rather than a
   trap; `G-J4` still aborts if the resolved dict is absent or wrong under either.

### 0.D OWNER RULING — the N4 downgrade is WAIVED for this cell's reading

> **Ruled 2026-08-17, BEFORE the band claim and BEFORE any game.** At the time of this
> amendment: no band claimed, no `manifest.json`/`summary.json`, **no `ms_ratio` and no
> statistic of any kind in existence.** The ruling is therefore made blind to every
> number it affects.

**Owner, verbatim:**

> "we can afford some wallclock during play, especially if its not every tile draw.
> dont let that be the constraint right now"

**What this changes — exactly one thing.** §4.2's instruction to *"downgrade the
against-champion reading to COST-CONFOUNDED"* when `ms_ratio > 1.20` is **WAIVED for
this cell**. `G-CONFIRMED` / `G-DEPLOYS` / `G-CLOCK` may be read at face value against
the champion regardless of the realized `ms_ratio`.

**What this does NOT change:**

- **`ms_ratio` is still measured and still reported on every branch**, for both cells,
  per §4.3(4), **with the field-name trap named**.
- **DESIGN §5's prediction of ≈1.1985 stays pre-registered**, and the read-out must
  print **prediction vs realized** — the comparison is evidence about the cost model
  regardless of whether the bar is enforced, and it is the only way a wrong cost model
  becomes visible.
- **The `≤ 1.05` cost-neutral annotation is retained** and must be printed if it holds.
- **`D` / `z_D` are untouched.** They were already cost-immune *by construction* —
  `ARB` and `RND` burn the same playouts on the same worlds at the same plies — and this
  ruling extends that same spirit to the champion-comparison reading.
- ⭐ **NO BRANCH CONDITION MOVES.** §4.2 already states, in the committed text, that
  `ms_ratio` is *"a **downgrade trigger**, not a conjunct"* and *"**NEVER a branch
  input**"*. Waiving a rider that was never a branch input cannot change which branch
  fires on any read.

**⚠️ §4 is deliberately left BYTE-IDENTICAL by this amendment.** The waiver lives here
in §0.D and **overrides §4.2 by amendment** rather than by editing it, precisely so the
instrument's mechanical old-vs-new byte-equality proof over the §4 branch section
continues to hold and can be re-run as evidence that no bar moved. **The rule text does
not change; the instrument implements the override.** A reader must therefore read §0
before §4 — which is why §0 sits at the top of this document.

**⛔ ANTI-GAMING CLAUSE, binding.** This ruling is permission to *spend* clock, **never**
licence to *reshape the arbiter to look cheaper*. Nothing may be shaved to duck under
1.20:

- **`B` stays 16** — the evidenced rung, and it may **not** be expanded beyond 16 either;
- **the tie predicate is not narrowed** — it fires at tied tile plies only, as designed,
  which at ~23 per game is exactly the *"not every tile draw"* the ruling points at;
- **no playout truncation for cost reasons** — truncation remains closed on the
  frontier-blindness argument (PHASE_A.md §5), and cost is now explicitly not a reason
  to revisit it.

**Scope limits, unchanged by this ruling:**

- **`rho_phone` is NOT reopened.** 5.520 at `B` = 16; on-device remains a separate
  future question and §5's prohibition on licensing a phone deploy stands.
- **Tournament-clock legality bookkeeping is untouched** — Track G continues to record
  the numbers; this ruling governs *this cell's reading*, not that ledger.

### 0.E PRE-LAUNCH ACCEPTANCES — the arbiter FAILS SOFT, and the `G-TOOL` witness is corrected

> **Recorded 2026-08-17, BEFORE the band claim and BEFORE game 1.** No band claimed, no
> `summary.json`, no strength number in existence. Both preflights pass 14/14 with both
> sides of `J13` true per host; the production-knob smoke is running.

#### 0.E.1 The arbiter fails soft — ACCEPTED, with four conditions

**The behaviour.** A `tier1-greedy` continuation can hit the engine's window refusal or
the ply ceiling deep inside a world. Rather than propagate, the arbiter **falls back to
the champion's own `pooled_q_argmax` pick** at that ply and **counts the event**
(`tiearb_errors_total`, `tiearb_error_rate_on_fired`, `tiearb_first_error` in
`summary.json`; `cand_tiearb.errors` per game).

**This is a deviation from "the arbiter always arbitrates" and it is ACCEPTED**, because
the alternative is worse and the direction of its bias is known:

- **Propagating would kill the GAME**, and the resulting exclusion would be
  **candidate-correlated** — the `capoff` pattern. A biased exclusion is a far more
  dangerous failure than a diluted effect.
- **The bias runs toward the champion**, i.e. **conservative against the candidate**: a
  failed arbitration reverts that ply to exactly the champion's behaviour, so the effect
  shrinks toward the null. A positive read is therefore *understated*, not inflated.
- **It is symmetric across `ARB` and `RND` by construction** — both cells run the same
  playouts and fall back by the same rule — so the mechanism contrast `D` is diluted by
  it, never biased by it.

**Conditions of acceptance, binding:**

1. ⭐ **Ply granularity, not world or arm granularity.** If *any* world or *any* arm
   errors at a ply, **the whole ply reverts to the champion's pick.** The arbiter must
   **never** take an argmax over a partial world set: the CRN pairing across arms is the
   entire basis of the comparison, and a mean over a subset of worlds silently breaks
   it. A partial-world argmax would be a defect, not a degradation.
2. **`G-FIRE` binds on the EFFECTIVE rate** (see the amended §3 row): the floor applies
   to `phi_effective = phi × (1 − error_rate_on_fired)`, per cell. This is a faithful
   reading of `G-FIRE`'s committed purpose — it exists to refuse an **inert** surface,
   and a surface that fires but always errors is inert. An arbiter that triggers 23
   times a game and falls back 23 times is a champion-vs-champion null wearing the shape
   of a real cell, which is the exact thing `G-FIRE` was written to catch.
3. **Mandatory reporting, in addition to §4.3** (recorded here rather than in §4 so the
   §4 branch text stays byte-identical): the read-out MUST print, per cell,
   `tiearb_errors_total`, `tiearb_error_rate_on_fired`, `tiearb_first_error`,
   `phi_effective` beside `phi`, and — if `error_rate_on_fired > 0.05` — an explicit
   statement that **the measured effect is diluted by that factor and a null is
   correspondingly weaker evidence.**
4. **Never a branch input** except through condition 2's `G-FIRE` floor.

#### 0.E.2 `G-TOOL`'s witness — corrected, and my earlier instruction was WRONG

I previously asked for a **binary content hash** in preference to `carc_rs_version`.
**That was incorrect and would have failed closed on a perfectly correct run:** the `.so`
is **not reproducible cross-machine** — the same commit and toolchain produced different
binary shas on the two boxes. Corrected:

- **The authoritative witness is `carc_rs_build`** =
  `carc_rs-<version>+<full-commit[:12]>+rustc<toolchain>` — measured **identical** on
  both boxes (`carc_rs-0.1.0+bd94aed5d3ee+rustc1.96.0`).
- **`carc_rs_binary_sha` is a box-local "rebuilt here" witness only** and must never be
  compared across boxes.
- **The authoritative cross-box comparison is the two `PREFLIGHT_*_${HOST}_FIRST.json`
  files**, not the manifests: under `--shared-claim` the second box writes **no
  manifest**, so `mixed_builds` on a manifest is the *writer's own observation* and
  cannot see the other box.
- ⚠️ **Measured trap:** `git rev-parse --short` length is **per-box** (`core.abbrev`), so
  the build id must slice the **full** commit to a fixed 12 characters. A per-box
  abbreviation would make two identical builds read as different.

**`G-TOOL`'s refusal of the sentinel stands unchanged** — unknown provenance is not
agreement. Two *legitimate* sentinel paths were found and fixed **in the driver, not the
gate** (`RUSTUP_TOOLCHAIN` unset ⇒ `+rustcunpinned`, now exported from `WORKERS.conf`;
and a non-interactive ssh on the laptop with no `rustup` on `PATH` ⇒ maturin died ⇒ a
**stale wheel**, now fixed by sourcing `~/.cargo/env` and asserting `rustc --version`
before building). That is the correct resolution and the gate was not relaxed.

### 0.F `G-PLY` — a WITNESS for §0.E.1 condition 1, which was otherwise unverifiable

> **Recorded before the band claim and before game 1.** Band unclaimed, no
> `summary.json`, no strength number in existence.

§0.E.1 condition 1 requires the fail-soft fallback to be taken at **ply granularity** —
if any world or arm errors, the whole ply reverts to the champion's pick, and the
arbiter **never** takes an argmax over a partial world set, because the CRN pairing
across arms is the entire basis of the comparison.

⚠️ **That condition was UNWITNESSED by every gate in this document.** `G-FIRE` sees error
*counts* only; nothing in `summary.json` or the manifests records the *granularity* at
which a fallback was taken. A partial-world argmax would therefore have been **invisible
to the whole adjudication layer** — a silent break of the comparison's basis, on a
property I had myself flagged as needing explicit confirmation. A condition no gate can
see is not a condition; it is a hope.

**Two witnesses are therefore required before launch, at different levels:**

1. **Implementation level** — a test in `tests/test_tiearb2_stage2.py` section H that
   constructs a mid-playout failure in **one** world and asserts the ply's pick equals
   the champion's own `pooled_q_argmax` pick, **not** an argmax over the surviving
   worlds.
2. **Runtime level** — the arbiter counts any argmax taken over fewer than `B` = 16
   completed worlds for any arm, and exposes **`tiearb_partial_argmax_total`** in
   `summary.json` for both cells.

**`G-PLY`, added to §3:** `tiearb_partial_argmax_total` **absent, or non-zero**, in
either cell ⇒ `U-UNREADABLE`. Absent is a failure, not a pass — an unreported counter is
unknown, not zero, exactly as §0.E's absent-error-rate rule already establishes. A
non-zero value means the CRN pairing was broken during play, so the cell's central
comparison is void whatever the margins say.

⚠️ This is a **witness for an already-committed condition**, not a new condition:
§0.E.1's condition 1 is unchanged and this only makes it checkable. §4 is untouched.

### 0.G ⚠️ THE COST MODEL MISSED BY ~2× — recorded BEFORE the real cells and BEFORE any strength number

> **Recorded 2026-08-17 from the SMOKE (laptop W22, 22 games/cell, throwaway band
> 900000100000, production knobs).** Band 132000000000 unclaimed; no strength number of
> any kind exists. **This framing must not be reconstructed after margins exist.**

**Prediction vs realized:**

| quantity | DESIGN §5 predicted | realized (smoke) |
|---|---|---|
| `ms_ratio` (`ARB`) | **≈ 1.1985** | **≈ 2.42** |
| `ms_ratio` (`RND`) | **≈ 1.1985** | **≈ 2.33** |

**⭐ The decomposition, and it exonerates the arbiter: the NUMERATOR model was right and
the DENOMINATOR was a category error.**

- **Numerator — accurate within 12%.** Predicted `Ā × B × c_tier1_rust` =
  3.0022 × 16 × 0.178232 = **8.561** worker-s per fired ply; realized **9.57**
  (**+11.8%**). **The arbiter cost almost exactly what Phase A said it would cost.**
- **Denominator — the wrong currency.** §5 divided by `t_champ` = **13.7552 s/move**,
  which is a **SEQUENTIAL, single-box, uncontended** measurement. The in-cell `ms_ratio`
  divides by the **opponent's per-move wall under W-way contention**, ≈ **1.7 s/move** —
  a different measurement condition by ≈ 8×. **§5 equated `rho_wall` with the in-cell
  `ms_ratio`. They are not the same currency, and that sentence is WITHDRAWN.**
- **The reconciliation closes.** Recomputing forward with the correct denominator,
  `1 + (9.57 × phi / 72) / 1.7`, gives **2.33** at `phi` = 17.05 and **2.40** at
  `phi` = 17.95, against realized **2.42 / 2.33**. (The cell-to-cell assignment inverts
  within noise at n = 22 games; the *level* is what reconciles, and it does.) The
  residual after correcting the denominator is the +11.8% numerator error and the
  realized `phi` being **74–78% of the 22.96 prior** — both already reported.

⇒ **THE COST MODEL MISSED, NOT THE ARBITER.** No re-tuning of `B`, the trigger, or the
playout is implied or permitted (§0.D's anti-gaming clause stands).

**What this does and does not touch:**

- **No branch moves.** `ms_ratio` was never a branch input (§4.2), and §0.D waived its
  consequence. The adjudication is unaffected — but the *measurement* was always
  mandatory precisely so a wrong cost model would become visible, and it did. This is
  that mechanism working, not failing.
- **Phase A's `rho_wall` is NOT invalidated.** It is a correct statement in its own
  sequential currency, and `B_affordable` = 16 was graded on that currency against the
  N4 bar as the programme has always defined it. What is now known is that **`rho_wall`
  and in-cell `ms_ratio` must never again be equated**, and any future design that
  quotes one as a prediction of the other is repeating this error.
- ⚠️ **DEPLOY-RELEVANT, AND IT MUST NOT BE BURIED:** the honest realized figure for a
  deployed arbiter under contention is **≈ 2.3–2.4× the champion's per-move wall**, not
  ≈ 1.2×. The owner ruling ("*we can afford some wallclock during play… dont let that be
  the constraint right now*") stands and governs this cell's reading — but the owner is
  entitled to know the number is **≈ 2.4×, not ≈ 1.2×**, when the production-flip
  decision is put to him. The read-out MUST state it at that magnitude.
- **`rho_phone` is untouched and still NOT solved** (5.520 at `B` = 16) — and note it is
  a **third** currency again, so it may not be inferred from either figure above.

**Mandatory in the read-out:** this table, the decomposition, the reconciliation, and the
sentence *"the cost model missed, not the arbiter"* — printed as a first-class item, not
a footnote, and **never** presented as an arbiter defect.

### 0.H The real cells' `ms_ratio` is NOT graded against the smoke — a decision, not an omission

> Recorded before the band claim and before game 1.

The read-out prints the §0.G smoke figure (≈2.42 / 2.33) **and** the realized in-cell
`ms_ratio` **separately, and does not compare them.** No committed text says what a
divergence between them would mean. **That is deliberate and it stands.**

- **No bar may be invented here.** A threshold written now would be written *after* a
  smoke number exists — the exact pattern blind ordering exists to prevent. The
  discipline that made §0.G honest is the same discipline that forbids §0.H inventing a
  companion bar for it.
- **It could not change anything anyway.** `ms_ratio` is not a branch input (§4.2), and
  §0.D waived its consequence, so a smoke-vs-cell comparison would be machinery that
  cannot move a verdict — pure added surface, zero decision value.
- **The descriptive route is already open and sufficient.** §0.G's decomposition —
  numerator, denominator, `phi` — applies to the real cells as prose. A reader who wants
  the comparison can make it from numbers the read-out already prints; what they may not
  get is an adjudicated verdict on it, because none was pre-registered.

⇒ **Both numbers are printed; neither grades the other.** If a future design wants that
comparison adjudicated, it must pre-register the bar **before** its own smoke.

---

## 1. Scope

- Two cells, **`ARB`** and **`RND`** (DESIGN §1), **n = 800 deck-paired games each**,
  on the **same fresh band `132000000000`** and the **same decks**, at production
  budget k8×1376 = 11,008, exact-K 2, against the unmodified champion.
- **The branch input is the pair of within-band deck-paired reads.** Cross-band
  comparison is not a branch input anywhere (CLAUDE.md cross-band humility); the robust
  class is exactly what is used.
- The arbiter is `B` = 16, `J` = 4, salt `tiearb2-deploy-v1` (DESIGN §2), i.e. the
  selection half of Stage 1b's arm `H` — the rung that captured *and*, after Phase A,
  the rung that is affordable (`rho_wall` 0.6224).
- **`governance/PRODUCTION.yaml` is untouched on every branch.** A pass licenses a
  production-flip **decision for the owner**, never an automatic flip.

## 2. The committed quantities

| symbol | definition |
|---|---|
| `M_arb`, `M_rnd` | the per-deck **seat-balanced paired margin** (points/game) of the cell's candidate vs the champion, `summary.json` |
| `z_arb`, `z_rnd` | `summary.json::paired_z` (`_paired_z`, `eval_fair_puct.py`) — **the primary statistic** |
| `E_arb`, `E_rnd` | the same in elo, by the harness's own conversion |
| **`D`** | `M_arb − M_rnd`, **deck-paired over the decks completed in BOTH cells** |
| **`z_D`** | `D` over its own paired se, computed the same way as `paired_z` |
| `ms_ratio_x` | `champ_prefix_ms_per_move / rung_ms_per_move`, in-cell, per cell. ⚠️ **`champ_prefix_ms_per_move` IS THE CANDIDATE SIDE** in `eval_fair_puct` |
| `phi_x` | realized tied tile plies per game at which the arbiter fired, per cell |
| `n_common` | decks completed in **both** cells (the denominator of `D`) |

**The bars are `+2.0` (z) and `1.20` (the N4 cost trigger)**, plus **`+1.0`**, the
`G-PRESENT` / `G-FLAT` presentation split (§0.C.1). Neither adjudicating bar is a new
constant: `+2.0` is Stage 1's, Stage 1b's, `E-FLAT`'s and `W-FLAT`'s verbatim; `1.20` is
the house N4 trigger currency, the same bar Phase A's `rho_wall` was graded at.
⚠️ **`+1.0` is not an adjudicating bar** — both branches it separates license nothing,
so it selects a label and its mandatory rider, never a permission.

## 3. Preconditions — checked FIRST, and they void the run

**`U-UNREADABLE` fires, and no other branch may fire, if ANY of:**

| id | condition |
|---|---|
| `G-J1` | either cell's resolved `cand_leaf_hash` **differs** from the champion's `a36d2e15a3b3d71d`. ⚠️ **Inverted gate: a difference is an ABORT, not a finding** |
| `G-J4` | **top-level `cand_tiearb`** (§0.C.2) is absent or unresolved in either `manifest.json`, or its `mode` is not `argmax` for `ARB` and `random` for `RND`, or its `B` ≠ 16 or `J` ≠ 4 |
| `G-J13` | the **two-sided** positive control did not pass on **each** host before that host's game 1 (`PREFLIGHT_*_${HOST}_FIRST.json`): the arbiter must **change the pick** at a constructed tied ply **and** leave `root_leaf_value_bits` **unchanged** |
| `G-FIRE` | **(AMENDED §0.E.1)** `phi_effective < 1.0` in either cell, where `phi_effective = phi × (1 − error_rate_on_fired)` — the surface is inert and the cell would grade a champion-vs-champion null wearing the shape of a real cell. ⚠️ The effective rate is the binding one because the arbiter **fails soft**: a ply whose arbitration errored reverts to the champion's pick and is therefore not arbitrated at all |
| `G-BAND` | band `132000000000` was not claimed before game 1, or the two cells did not run on the same band and the same decks |
| `G-N` | **(AMENDED §0.B)** `n_common < 320` **decks**, **or** either cell completed fewer than **640** of its **800** paired **games**. ⚠️ The text committed at `b2faa238` read `n_common < 600`, which is unreachable: a paired `n = 800` cell yields at most **400** decks (`eval_fair_puct.py:3924`) |
| `G-TOOL` | the two boxes did not run the same rust toolchain / the same `carc_rs` build, or a cell mixed builds |
| `G-STAT` | `z_arb`, `z_rnd` or `z_D` is `NaN` or absent |
| `G-PLY` | **(ADDED §0.F)** `tiearb_partial_argmax_total` is **absent, or non-zero**, in either cell — absent is unknown-not-zero and fails; non-zero means an argmax was taken over a partial world set, i.e. **the CRN pairing across arms was broken during play**, so the cell's central comparison is void whatever the margins say |

`U-UNREADABLE` = report cost, integrity, firing rates, and whichever gate failed.
**Nothing closes, nothing is licensed, nothing is re-labelled.**

## 4. Branches

**Evaluated in this order. `U-UNREADABLE` (§3) pre-empts everything.**

**Then, pre-emptively:**

```
G-ANOMALY  ≡  z_rnd ≥ +2.0
```

Let, on the complement (so `z_rnd < +2.0` below):

```
p ≡ C_arb ≡ z_arb ≥ +2.0        # the arbiter beats the champion
q ≡ C_ctl ≡ D ≥ 0               # ...and is not below its own cost-matched control
r ≡ C_res ≡ z_D ≥ +2.0          # ...and the two are RESOLVED against each other
```

`r ⇒ q` (a `z_D ≥ +2.0` requires `D > 0`), so the cell `p ∧ ¬q ∧ r` is vacuous; `G-CLOCK`
is defined as `p ∧ ¬q` irrespective of `r` so the table stays total.

| # | condition | read |
|---|---|---|
| **`G-ANOMALY`** | `z_rnd ≥ +2.0` | **THE COST-MATCHED CONTROL ITSELF BEATS THE CHAMPION — THE FRAME IS WRONG AND NOTHING ELSE IN THIS TABLE MEANS WHAT IT SAYS.** A *random* arm chosen at tied plies, after burning the identical playouts, wins games. That is a finding about the champion's own tie-break (or about spending clock at tied plies), **not** about terminal grounding. Report both cells in full, `D`, `z_D`, both `phi`, both `ms_ratio`. **Nothing closes and nothing is licensed.** |
| **`G-CONFIRMED`** | `p ∧ q ∧ r` | ⭐ **TERMINAL-GROUNDED TIE ARBITRATION WINS GAMES AGAINST THE CHAMPION, AND IT IS THE MECHANISM RATHER THAN THE CLOCK.** The candidate convicts at 2σ on a fresh band, its wall-clock-matched control does not, and the two are **resolved against each other at 2σ**. This is the first deploy-elo evidence on this axis and the only reading that discharges DESIGN §12.1's caveat. **Licenses (does NOT do) exactly one thing: a production-flip DECISION for the owner.** ⛔ It does not flip `PRODUCTION.yaml`, does not license a leaf term (CL-065 + two dead menus + the 38% reach bound stand), does not license an on-device deploy (**`rho_phone` = 5.520 at `B` = 16 — the phone currency was never solved**), and does not license a second cell. |
| **`G-DEPLOYS`** | `p ∧ q ∧ ¬r` | **THE CANDIDATE BEATS THE CHAMPION AND THE CONTROL DOES NOT — BUT THE TWO ARE NOT RESOLVED AGAINST EACH OTHER.** `z_arb ≥ +2` and `D ≥ 0` and `z_rnd < +2`, yet `z_D < +2`. **DESIGN §6 states before the run that n = 800 cannot resolve `D` to 2σ at the expected effect size** (se(`D`) ≈ 1.41× the single-cell se ⇒ a true +18 elo reads `z_D` ≈ 1.5), so this branch is *expected* on a real effect and is **not** a demerit. **Licenses (does NOT do) a production-flip DECISION for the owner, explicitly labelled as resting on an unresolved control.** The read-out must print `z_D` and the `n` that would resolve `D` to 2σ. |
| **`G-CLOCK`** | `p ∧ ¬q` | **THE CANDIDATE BEATS THE CHAMPION, BUT ITS WALL-CLOCK-MATCHED CONTROL IS NOT EXCLUDED — THE WIN CANNOT BE ATTRIBUTED TO THE MECHANISM.** `RND` burns the identical playouts on the identical worlds at the identical plies and picks at random, and it did at least as well. ⇒ what is being measured is clock, or pick perturbation, not terminal grounding. **Nothing closes and nothing is licensed**, and in particular this does **not** license a deploy decision. |
| **`G-PRESENT`** | `¬p ∧ ( z_arb ≥ +1.0 ∨ z_D ≥ +1.0 )` | **PRESENT BUT NOT CONVICTED — UNRESOLVED.** The direction is there and the bar is not met. **Nothing closes and nothing is licensed.** Report both cells, `D`, `z_D`, both `phi`, both `ms_ratio`, and **the `n` that would convict at the realized dispersion.** |
| **`G-FLAT`** | `¬p ∧ ¬( z_arb ≥ +1.0 ∨ z_D ≥ +1.0 )` | **THE MECHANISM DID NOT EXPRESS AS DEPLOY ELO ON A FRESH BAND AT n = 800.** ⚠️ **Mandatory scope sentence, quoted with the verdict and never separated from it:** *"This is a BOUNDED null, not an exclusion. DESIGN §6 states before the run that n = 800 deck-paired resolves ≈ ±8.5 elo at 1σ (±17 at 2σ), while the offline bound chain reads +18.09 elo CI [+6.32, +30.04] with a ÷5.23 low-end bracket at +11.06 — so a null here does NOT exclude the low end of the offline estimate. The honest claim is 'terminal-grounded tie arbitration did not express as deploy elo at n = 800 on band 132000000000', NOT 'terminal grounding is worth nothing in games'."* **Rider, mandatory when it applies:** if the 95% upper bound on `E_arb` is below +6.32 elo, the read-out must **additionally** state that the offline CI is excluded at 95% and the scope sentence is superseded in that one respect. **Second rider, mandatory always on this branch:** Stage 1b read `arb_H` = +0.1441 pts/tied ply at z +3.01 with the sign check CORROBORATING, so a flat game read is a **tension with a published result** and must be reported as such — print both, and do **not** present the tension as resolved. The operative statement to record: *the mechanism is real under a terminal-grounded ruler and did not survive the transfer to games at this power; DESIGN §12.1's caveat is therefore **not** discharged.* |
| **`U-UNREADABLE`** | any §3 precondition fails | §3. |

### 4.1 Exclusivity and exhaustiveness — verified in the pre-registration text

- §3 is evaluated **first** and pre-empts everything. `G-ANOMALY` is evaluated **second**
  and pre-empts the rest, so the remaining five are evaluated only where
  `z_rnd < +2.0`.
- On that complement the five partition `(p, q, r)` exactly: `p∧q∧r` → `G-CONFIRMED`;
  `p∧q∧¬r` → `G-DEPLOYS`; `p∧¬q` → `G-CLOCK` (total in `r`, and `r ⇒ q` makes `p∧¬q∧r`
  vacuous); `¬p` splits into `G-PRESENT` and its **exact negation** `G-FLAT`.
- ⇒ **exactly one branch matches every possible read, and the match does not depend on
  presentation order.** Any `NaN` in `z_arb`/`z_rnd`/`z_D` is caught by `G-STAT` in §3
  before a comparison is taken, so no branch is entered on a `NaN` comparison.
- This is verified by a machine sweep over the branch-condition truth table in
  `tests/test_tiearb2_stage2.py`, which **re-transcribes this section independently of
  the implementation** and asserts exactly one branch fires on every cell, `NaN`
  included.

### 4.2 The N4 cost rider — applied to every branch, and it is NEVER a branch input

`ms_ratio` is a **downgrade trigger**, not a conjunct:

- If `ms_ratio_arb > 1.20` or `ms_ratio_rnd > 1.20`, the read-out **downgrades the
  against-champion reading to COST-CONFOUNDED** and says so **in the branch sentence**.
- It does **not** touch the mechanism contrast `D` / `z_D`: `ARB` and `RND` are
  cost-matched to each other by construction, so `D` is immune to a budget confound.
- ⚠️ **DESIGN §5 predicts `ms_ratio` ≈ 1.1985 — just under the bar — and says so before
  the measurement.** A reading either side of 1.20 was therefore anticipated and is not
  a surprise; `ms_ratio ≤ 1.05` restores a fully cost-neutral reading.
- ⚠️ **The field-name trap**: `champ_prefix_ms_per_move` is the **CANDIDATE** side in
  `eval_fair_puct` (confirmed at live lines 2361/2371/2389). A read-out that swaps them
  inverts the verdict.

### 4.3 Mandatory on every branch — the full companion table

The read-out MUST print:

1. Both cells: `n` completed, `n_common`, `M`, `paired_z`, elo with CI, wr, and the
   seat balance.
2. `D`, its paired se, `z_D`, and the `n` that would resolve `D` to 2σ at the realized
   dispersion.
3. `phi_arb` and `phi_rnd` beside the offline prior **22.96** and its funnel (65.98%
   exact-tie rate on tile plies, 40.4% deduped scoreable), with **DESIGN §2.1's two
   runtime-vs-corpus mismatches restated verbatim** — the offline rate *estimates*, and
   does not equal, the runtime rate.
4. `ms_ratio` for both cells with the field-name trap named, and the §4.2 rider.
5. Every §3 gate with its realized value, including the two-sided J13 witness per host.
6. **DESIGN §12.1 of Stage 1b carried verbatim** (condition (b)) and **arm `C`'s NO
   CORROBORATION sign-check verdict carried verbatim** (condition (c)) — on every
   branch, including the passing ones.
7. The Phase-A cost facts that licensed this cell: `c_tier1_rust` 0.178232 worker-s/
   playout, 15.30× the pilot, `rho_wall(16)` 0.6224 — and **`rho_phone(16)` = 5.520,
   labelled NOT SOLVED**.
8. The realized band, the deck range, and the `BAND_REGISTRY` claim row.

## 5. What no branch does

- No branch edits `governance/PRODUCTION.yaml`. **A pass licenses a production-flip
  DECISION for the owner and nothing more.**
- No branch licenses an **on-device / phone** deploy: `rho_phone` was never brought
  under 1.20 above `B` = 2, and Phase A stamped it *reported, unadjudicated*.
- No branch adds a leaf term, changes the production leaf, or trains anything.
- No branch re-reads, re-labels or re-adjudicates Stage 1, Stage 1b, or Phase A. They
  stand as adjudicated; the Stage-1b read-rule is spent and its corpus burned.
- No branch licenses a second game cell. **This read-rule is spent when the read-out
  lands**, on every branch.
