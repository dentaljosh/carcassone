# TIE-ARBITER WIDENING — MECHANICAL READ RULE **rev R4** (successor pair)

> **STATUS: BLIND PREREGISTRATION, DRAFT. NOT LAUNCHED. NO POSITION SCORED. NO NUMBER OF THIS
> RUN EXISTS.**
>
> Predecessor: the R3.3 rule at blind commit **`604edc83`** (`../shared_run/READ_RULE.md`),
> **SPENT-BY-GATE-FAILURE** and frozen ([`../PREREG_FAILURE.md`](../PREREG_FAILURE.md)).
>
> ⚠️ **This rule INCORPORATES the R3.3 rule by reference at `604edc83` and overrides only the
> sections restated below.** Everything not restated is binding **in its R3.3 wording**. Where
> this file and the R3.3 file disagree, **this file governs R4**; where this file is silent,
> **R3.3 governs**.
>
> **SINGLE USE. SPENT ON LANDING.** One adjudication, one analyzer invocation, one read-out for
> both rungs. No re-read, no top-up at any `z`.
>
> `governance/PRODUCTION.yaml` untouched on every branch. No claim minted. No strength row.

## R4 §0 — **`RUN` IS REDEFINED** (rev R4.5; overrides the carried §41)

> **`RUN` = `measurement/tiearb_widening_20260817/shared_run_r4/`.**

The R3.3 rule defines `RUN = shared_run/` and this pair **carried that definition unchanged while
living in `shared_run_r4/`** — so every `RUN`-relative address in this pair pointed into the
**spent, frozen** R3 directory. Redefined here, and the redefinition is **TOTAL**:

1. **It applies to every address in this pair, INCLUDING every address inside the CARRIED
   sections.** Wherever the R3.3 text says `RUN`, read `shared_run_r4/`. No address's *shape*
   changes — `RUN/GATE_DISJOINT.json`, `RUN/FLOORS.json`, `RUN/verdicts/READOUT.json` and the rest
   are all unchanged in form; only the directory they resolve under moves. A reader who resolves a
   carried address under the old `RUN` has resolved the wrong file.
2. **The spent R3 directory `shared_run/` is READ-ONLY for the whole of R4.** Nothing in this run
   writes there — not a manifest, not a gate, not a log. (Third incident of this class in this
   campaign; see DESIGN §R4-0.4.)
3. ⚠️ **`STAGE1B_LADDER.json` is COPIED, not cross-referenced.** It is carried "by reference, not
   rebuilt", and it lived only in the old `RUN` — so the redefinition alone would have left
   `G-REPLICATE`'s `RUN/STAGE1B_LADDER.json` **resolving to a file that does not exist, and ABSENT
   IS FAIL on a healthy run.** A byte-identical copy now sits at `RUN/STAGE1B_LADDER.json`
   (sha256 `8cf952be277ef01b2a69d914d9f01971a8752a64a6c18f5e9229ddbd43edcd21`, verified equal to
   the R3 original). **A copy, not an exception to the address rule** — carve-outs are how this
   class recurs.

## CARRIED UNCHANGED from `../shared_run/READ_RULE.md` @ `604edc83`

| § | content — binding in its R3.3 wording |
|---|---|
| §1 | address discipline; **ABSENT IS FAIL**; the **closed `allow_null` table** (4 entries + witnesses); fallbacks pre-registered; the structural test |
| §2 | **every gate except the three restated below** — `G-LEAF`, `G-SALT`, `G-M`, `G-BACKEND`, `G-BITEXACT@HEAD`, `G-PREFIX`, `G-CRN`, `G-UNCAPPED`, `G-DRAW`, `G-ARMS`, **`G-REPLICATE`** (incl. `STAGE1B_LADDER.json` and its no-fallback rule) — and §2's precedence and binding-scope preamble |
| §3 | the power arithmetic: significance defined **once** on the percentile root bootstrap (2,000 reps, seed 20260819, cluster `root_id`); the `se` bracket `[0.0179, 0.0200]`; the **+0.040 floor as a point test**; `sd_Δ ∈ [0.9, 1.4]` |
| §4 | **rung-2 branch table, verbatim** — `W-NOISY` · `W-REVERSAL` · `W-RISING` · `W-SATURATED` · `W-INCONCLUSIVE`, with the level/increment residue and the mechanism-anomaly print |
| §5 | **rung-3 branch table, verbatim** — the guard, `X-CONFIRMED` · `X-ABOVE` · `X-PARTIAL` · `X-BELOW` · `X-FREE` · `X-INCONCLUSIVE`, the `Δ_ora`-only sub-table, `X-NOISE`, and the three mandatory prints |
| §6 | **all eight riders R1–R8** (σ-inflation, translation, `I7-draw-scope`, two currencies, governance, the open N4 waiver, phone out of scope, `\|z\|<2` is never "refuted") |
| §7 | what the read-out prints; **gate-inputs-only on `W-UNREADABLE`**; the write-only sealed file; deviation discipline |
| §8 | spent-on-landing; the six-touch close-out |

**No estimand, bar, branch condition, threshold or rider changes in R4.** The three gates below
change because R3's versions were **unsatisfiable against the world**, not because a bar moved.

---

## R4 §2a — `G-COMPLETE` (REPLACES the R3.3 row)

R3's floors were computed from raw census rows and were unreachable by 27× on S2
(`PREREG_FAILURE` §2). R4's floors are **parameters fixed by the owner's choice of row in
DESIGN R4-2.2**, and the conjunct is written against whatever that choice commits.

| conjunct (all must hold) | primary address | fallback | on a healthy run |
|---|---|---|---|
| `s1_n ≥ ⌈0.95 × n₁⌉` and `s2_n ≥ ⌈0.95 × n₂⌉`, where **`n₁`/`n₂` are the values committed in `RUN/FLOORS.json` before the extension band is claimed**; mining ceilings honoured (≤4 tied plies/root S1, ≤3 capped plies/root S2); **both counts evaluated AFTER the R4 §2b exclusions** | `READOUT::widening.completion.{s1_n,s2_n,s1_max_per_root,s2_max_per_root}` + `RUN/FLOORS.json::{n1,n2,option_label}` | `RUN/verdicts/per_position_{s1,s2}.jsonl` line counts + `root_id` grouping | **PASSES** — the floors are now sized from measured rates (`r_S1 = 1.574`, `r_S2cap = 0.206`), not from raw row counts |

**`RUN/FLOORS.json` is committed with this pair**, carrying `{n1, n2, option_label, r_s1, r_s2cap,
games_extension_s1, games_extension_s2, sub_ranges}` — the owner's choice frozen **before** the
extension band is claimed and before one game is generated (DESIGN R4-8b's binding order:
`c_IF` remeasure → floor choice → `FLOORS.json` → blind commit → band claim). A floor chosen or
adjusted after supply is known is a floor fitted to the data. It is also the **frozen denominator**
for §2b(iii)'s exclusion bound. **If `n₂ = 0` (the `S1 ONLY` row), rung 3 does not run**: its
branch table is not adjudicated, its riders are not printed, and the read-out states that the J
question was **not bought**, never that it was answered.

⚠️ **Supply is knowable before scoring.** A shortfall must be caught at the corpus stage — where
the only sunk cost is generation — not at the read-out. The corpus driver reports realized supply
against `FLOORS.json` **before** the first scoring leg (DESIGN R4-8, W6).

## R4 §2b — `G-DISJOINT` (REPLACES the R3.3 row)

Digest collisions are now **excluded and counted** rather than fatal-on-first, under a bound
committed before any R4 number exists (DESIGN R4-3).

| conjunct (all must hold) | primary address | fallback | on a healthy run |
|---|---|---|---|
| **(i)** `passed == true` for the **rid** and **root** layers on **every** comparison — these remain **zero-tolerance**: a shared rid or root is a corpus leak, never a transposition. **(ii)** Digest layer: every collision is recorded and resolved by the **total order** `spent ≺ 135e9 ≺ 137e9 ≺ 138e9` — **the later position is excluded**, the earlier never touched; an S1↔S2 collision excludes the **S2** rid regardless of band. **(iii)** `carried + residual ≤ ⌈0.005 × qualifying_deduped(stratum)⌉`, per stratum — **one spelling, this one** — where `carried` is the exclusion count measured on the **probe** build and `residual` the fresh collisions in the **final** build (expected `0`); evaluated **once**, at the final gate, against the denominator in `RUN/FLOORS.json`. A nonzero `residual` is additionally reported as a **determinism defect**. **(iv)** Exclusions applied **before** the **final** `POSITIONS_PLAN` is frozen, so no excluded rid reaches a leg — the probe build is what makes (iii) and (iv) simultaneously satisfiable rather than jointly vacuous (DESIGN R4-0.2). **(v)** `strata_root_overlap == 0`. **(vi)** All **SEVEN** comparisons present: three layers on the four ARMS-vs-ARMS (`s1_vs_tiletie0812`, `s1_vs_tiearb2_0816`, `s2_vs_tiletie0812`, `s2_vs_tiearb2_0816`), three layers on **`base_vs_extension`** — **one comparison key** whose top-level layers are **summed across strata** (zero iff every stratum is zero, so conjunct (i) evaluates correctly on the sum) with a required **`by_stratum`** block carrying each stratum's own three layers for attribution (DESIGN R4-0.1) — three layers on **`s1_vs_s2`**, and `b_rid` only on `s1s2_vs_exclude_rids`. **(vii)** Same-rank pairs (a stratum-band against itself) are **out of scope by construction** — no comparison measures them, so no exclusion fires on one (DESIGN R4-3 rule 3) | `RUN/GATE_DISJOINT.json::{passed, comparisons (incl. `base_vs_extension.by_stratum`), strata_root_overlap, digest_exclusions:{<stratum>:{carried, residual, n_excluded, rate, bound_n, denominator_source, rids, void}}}` | **none** — a missing gate file is a FAIL | **PASSES.** Realized rate on band 135e9 was **1/551 = 0.181%**, ≈2.8× inside the bound. ⚠️ Without `base_vs_extension` a healthy run's expected **order-1** intra-stratum cross-band collisions would be **invisible and unruled** — R3's contiguous band made them impossible; R4's band structure makes them expected. ⚠️ Without **`s1_vs_s2`**, conjunct (ii)'s S1↔S2 rule would govern a case **no comparison measures** — and it is the **largest** such case, ≈1–2 expected events at FULL, ≈3.4× the base↔extension count. ⚠️ Exceeding the bound ⇒ that stratum is **VOID**, not excluded-and-continued, and **a VOID is not curable by generating more games** (the denominator is frozen in `FLOORS.json`): at that density, transposition degeneracy is a property of the generator and "fresh corpus" is the wrong description — a different finding, which must surface rather than be absorbed |

**Always printed, on every branch, whether or not any exclusion occurred:** the per-stratum
collision count, rate, excluded rids, and the bound they were measured against.

**Why exclusion is legitimate here and was not in the 2026-08-14 open-city void:** the digest is a
function of the **board alone**, computed at corpus-build time, **before any value exists**. That
exclusion was rejected for being outcome-dependent; this one cannot be, by construction.

## R4 §2c — `G-BAND` (REPLACES the R3.3 row; generalised from two files to N)

R3's two-file form does not stretch to base + extension + top-up. The rule generalises; the
principle — **each file checked against ITS OWN range, floors tabular** — is R3's B1 fix.

| conjunct (all must hold) | primary address | fallback | on a healthy run |
|---|---|---|---|
| For **each** generated range, its **own** `verify-champgames` file satisfies `band_ok == true`, `seed_band` equal to **that** range, `n_out_of_band == 0`, `n_duplicate_seeds == 0`; **and each file meets its own committed floor** per the table below; **and** no seed appears in two files. **Never one invocation over a widened band** — it would report `n_out_of_band == 0` for a seed lying in neither range | `RUN/corpus/CHAMP_GAMES_VERIFY.json` (base) · `…_EXT.json` (extension) · `…_TOPUP.json` (top-up, iff exercised) — each `::{band_ok,seed_band,n_out_of_band,n_duplicate_seeds,n_games_realized}` | — (**no seed list anywhere by design**; the emitter publishes `sha256_of_sorted_seeds`) | **PASSES**, including on a healthy run that exercises any subset of the three |

| file | range | its own floor |
|---|---|---|
| base | `135000000000` +0…+849 | `n_games_realized ≥ 850` |
| extension | `137000000000`, **split by stratum**: S1 `+0…+(g₁−1)`, S2 `+g₁…+(g₁+g₂−1)` | `≥ g₁ + g₂`, with `g₁ = FLOORS.json::games_extension_s1` and `g₂ = …_s2`, **and each sub-range fully populated** |
| top-up (iff exercised) | `138000000000` +0…+499 | **the increment only — never a run-level floor** |

⚠️ **The extension's stratum split is a conjunct, not documentation (R4.1/B2).** Every extension
seed must lie in the sub-range of the stratum that mined it. `+games` is a **sum of two disjoint
requirements**, and mining both strata from one undivided range would fail **§2b(v)
`strata_root_overlap == 0` on a healthy corpus** — a self-inflicted gate failure. `FLOORS.json`
carries `games_extension_s1`, `games_extension_s2` and both sub-ranges explicitly; when
`games_extension_s2 == 0` (the `S1 ONLY` row) there is no S2 sub-range and none may be generated.

`136000000000` is **RELEASED UNUSED** and must appear in **no** file; a seed from it anywhere is a
FAIL.

---

## R4 §7a — additions to what the read-out prints

Everything in CARRIED §7, plus:

1. **The supply chain, realized against committed**: raw → qualifying → deduped → capped per
   stratum, beside `FLOORS.json`'s committed `n₁`/`n₂` and the rates they were sized from.
2. **The digest-exclusion block** (R4 §2b), whether or not anything was excluded.
3. **The predecessor's disposition, in one line**: the R3.3 pair `604edc83` is
   SPENT-BY-GATE-FAILURE; band 135e9's games are input, not a prior result; **and R4's `n` is not
   statistically independent of that corpus's structure** (`PREREG_FAILURE` §3.4) — a sizing
   dependence, never an estimand dependence.
4. **The deviation list** (`../DEVIATIONS.md`): D1's signature verdict, and D2 closed as
   unnecessary.
5. **Both `c_IF` figures** — committed 2.35 and smoke-indicated 1.2313 — with the remeasure's
   verdict on the 1.91× gap, and the re-based generation `c` (297.6 measured → 372.0 committed).
6. **If `n₂ = 0`:** an explicit statement that the rung-3 question was **not bought** — not
   answered, not null, not inconclusive. Absence of a purchase is not a result.
