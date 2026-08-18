# TIE-ARBITER WIDENING — SHARED RUN, DESIGN **rev R4** (successor pair)

> **STATUS: BLIND PREREGISTRATION, DRAFT. NOT LAUNCHED. NO POSITION SCORED. NO OUTCOME
> STATISTIC OF THIS RUN OR ITS PREDECESSOR EXISTS OR WAS READ.**
>
> **Why there is a successor.** The R3.3 pair (blind commit **`604edc83`**, `../shared_run/`)
> is **SPENT-BY-GATE-FAILURE**: `G-DISJOINT` and `G-COMPLETE` fired **pre-scoring**, exactly as
> written. Disposition, and the blindness argument that makes band 135e9's games reusable as
> **input**: [`../PREREG_FAILURE.md`](../PREREG_FAILURE.md). That file is a precondition for
> reading this one.
>
> ⚠️ **`../shared_run/` IS FROZEN HISTORY.** Nothing in it moves. This document **incorporates
> it by reference at commit `604edc83`** and restates **only what changes**. A section marked
> **CARRIED** is binding in its R3.3 wording; do not re-derive it, do not paraphrase it.
>
> **Blind-order requirement:** this pair + `READ_RULE.md` commit to main in **ONE** commit,
> after the §8 W-code delta merges and its acceptance pass, before the extension band is claimed
> and before one position is scored.
>
> `governance/PRODUCTION.yaml` untouched on every branch. No claim minted. No strength row.

---

## What is CARRIED UNCHANGED from `shared_run/DESIGN.md` @ `604edc83`

Binding in their R3.3 wording, **not restated here**:

| § | content |
|---|---|
| §1 | what the run is; the two rungs; out-of-scope list (incl. the phone, owner ruling) |
| §2 | **cells and statistics** — every estimand, the declared shared cell, `ora` adjudicates rung 3 |
| §4 | instrument invocation, the W6 driver pointer, the three salts, the graded-knob table |
| §5 | the W4/`G-CAP` resolution and **`I7-draw-scope` verbatim** (incl. both R2 amendments) |
| §6 | **power arithmetic**: the `se` bracket `[0.0179, 0.0200]`, the +0.040 floor, `sd_Δ ∈ [0.9, 1.4]`, the root bootstrap (2,000 reps, seed 20260819), significance defined once on the percentile CI |
| §9 | freeze-and-sequence, 4a / 4b-pre / 4b, the two-source merge discipline |
| §10 | required manifests |
| §11 | the draft `I6` amendment text |
| §0.A–§0.O | every pre-blind amendment: `c_remeasure` spelling, the `allow_null` mechanism, `STAGE1B_LADDER.json`, W9/`D-DRAW`, the `WORKERS.conf` consumer mapping, `--backend rust`. ⚠️ **EXCEPT §0.O, which R4-0.4 OVERRIDES**: the rule is no longer "`--positions-dir` is always explicit" but **"every `run_tiletie` path flag is always explicit"** — all six, three of them git-tracked in the spent run |

**Also carried, by reference, not rebuilt:** `STAGE1B_LADDER.json` (the `G-REPLICATE` reference)
· the merged W-code (W2/W3/W5/W6/W7/W8/W10) · the fixtures · the 4a/4b acceptance harness.
R4's W-delta is §8 and is small.

---

## R4-0. Pre-blind amendments — 2026-08-18 (rev R4.3, the last)

The W-code is otherwise complete at **`5c517cec`** (103 tests). Three items closed here; after
this the pair does not move again. **No gate conjunct's value changes** — R4-0.1 fixes an
ambiguity in how a conjunct is *counted*, R4-0.2 supplies the *mechanism* two rules needed in
order to both be true at once, and R4-0.3 is a disclosure.

### R4-0.1 RULING — seven comparisons, `base_vs_extension` carrying a `by_stratum` block. **RATIFIED AS BUILT.**

§2b(vi) said "three layers on `base_vs_extension` **per stratum**" while fixing the total at
**SEVEN** — and two strata make eight. The builder resolved it as **one** comparison keyed
`base_vs_extension` whose **top-level layers are summed counts** across strata, plus a
**`by_stratum`** block carrying each stratum's own three layers. **Ratified**, and the semantics
are written here so they are the rule's text and not a private convention of the code:

- **Summation is exact for the zero-tolerance layers.** Counts are non-negative, so
  `sum == 0 ⟺ every stratum == 0`. Conjunct §2b(i) — rid and root intersections must be zero on
  **every** comparison — therefore evaluates correctly on the summed top-level layer, with no
  weakening and no special case.
- **Nothing the digest conjuncts need is lost.** The bound is evaluated **per stratum** on
  `digest_exclusions.<stratum>.n_excluded`, which is a separate block; the comparison's digest
  layer is a *collision* count, and every collision is resolved individually by the total order
  regardless of which stratum it sat in.
- **Attribution on failure comes from `by_stratum`**, which is why the block is required rather
  than optional: a summed count that fails must still say which stratum failed.
- **The comparison count stays SEVEN** and READ_RULE §2b(vi)'s conjunct is unchanged in value.

*The alternative — eight keys `s1_base_vs_extension` / `s2_base_vs_extension` — is a ten-line
change but would require amending a gate conjunct's stated count at freeze time, for zero
informational gain. The cheaper and less invasive route is also the correct one here.*

### R4-0.2 RULING — the bound's evaluation mechanism. **BLESSED, and it is now the rule's text.**

⭐ **A real defect, caught late: R4-3 rules 5 and 7 as written were JOINTLY VACUOUS.** Rule 5
applies exclusions *before* the `POSITIONS_PLAN` freeze; rule 7 evaluates the bound *at* that
freeze. Together they guarantee the frozen corpus reports `n_excluded == 0` — **the bound could
never bind, on any corpus, however degenerate.** A bound that cannot fire is not a bound, and this
is the same class as the unsatisfiable-conjunct family this campaign has been killing since
`G-CAP` — only inverted: not fail-always, but **pass-always**.

**The blessed flow — the only one under which both rules hold:**

1. **Probe build** — positions built **without** exclusions (the two-pass, playout-free shape the
   S2 build already uses with `--allow-missing-champ-picks`; costs no scoring).
2. **Gate on the probe** — `G-DISJOINT` runs against it and measures the **true** collision count.
   **This is the count the bound is judged on**, against the denominator frozen in
   `RUN/FLOORS.json`.
3. **Apply exclusions**, then the **final build carries them forward** (`--carry-exclusions`), so
   no excluded rid ever reaches a leg — rule 5, satisfied on the artifact that is actually scored.
4. **The final `GATE_DISJOINT.json` reports both**: `carried` (the probe's exclusions) and
   `residual` (fresh collisions in the final build, **expected 0**).

**The bound is evaluated on `carried + residual`**, once, at the final gate — which keeps the
anti-gaming property intact (one evaluation, frozen denominator) while making the quantity
evaluated the *real* collision count rather than a post-exclusion zero. **A nonzero `residual` is
additionally a determinism defect** — the probe and the final build disagreed about the same
corpus — and must be reported as such, not quietly folded into the total.

### R4-0.3 DISCLOSURE — the accidental 138e9 generation burst, and why the top-up band is clean

During the builder's test round an accidental **~2-minute generation burst ran into the reserved
`138000000000` top-up band**. Cause, stated plainly because the mechanism matters: a guard-case
test that had been **out-of-range under R3 became LEGAL under R4's wider band arithmetic** and so
exec'd the **real** launcher at W48 instead of failing its guard. It was killed main-first with
workers reaped, and ~358 artifacts landed on the share. **The entire `gen_topup/` directory was
then verified and DELETED: the `138e9` band is clean, no registry row was ever claimed, and no
repo state was touched.** The deletion is load-bearing, not hygiene — **had those artifacts
survived, a later *licensed* top-up would have silently resumed into them via `--shared-claim`**,
inheriting games generated by a test harness under no prereg into a range the prereg licenses,
with the supply count quietly wrong and nothing in any gate able to see it. Because no artifact
survives, the band's seeds are unspent and the top-up clause is exactly as clean as it reads.
Guard added: **`--dry-run` / `WIDENING_GEN_DRY_RUN`** (resolves everything, prints `argv`, creates
nothing), and **all tests now use it** — a test that can exec a production launcher is a
launcher with a missing mode, not a test with a bad argument.

⭐ **The same fixture round caught and fixed a real EXCLUSION-ORDER INVERSION**: on a
spent-corpus collision the **banked** side would have been excluded rather than the R4 side —
which would have mutated a spent corpus's membership *and* left the duplicate position in the
fresh corpus, **the exact event class that killed R3.3**. It is now pinned by a deliberate fixture
collision, so the total order of R4-3 rule 1 is tested rather than merely asserted.

### R4-0.4 AMENDMENT (rev R4.4) — §0.O widens: **EVERY `run_tiletie` path flag is ALWAYS explicit**

⚠️ **This OVERRIDES the carried §0.O**, which named only `--positions-dir` and is now known to be
too narrow by five flags.

**The near-miss, on the record.** The executor's first smoke launch was killed mid-preflight
because `run_tiletie`'s preflight **silently writes `GATE_BACKEND_RECHECK.json` into
`measurement/tiletie_pricing_20260812/`** — a **git-tracked** file in the **SPENT** run's
directory. **No damage: killed pre-write, the file's mtime is still Aug 12, `git status` clean,
and the spent directory was verified pristine before and after.** The executor had set **four of
six** path flags from §0.O's wording and was still caught — which is the whole argument for this
amendment: a rule that names one flag reads as a rule about that flag.

**Six of `run_tiletie`'s path defaults resolve into the spent run** (verified this session against
`run_tiletie.py:103-108, 950-955`):

| flag | default | tracked? |
|---|---|---|
| `--positions-dir` | `measurement/tiletie_pricing_20260812/positions` | — (the §0.O case) |
| `--logs-dir` | `…/tiletie_pricing_20260812/logs` | — |
| **`--gate-out`** | `…/tiletie_pricing_20260812/GATE_BACKEND_RECHECK.json` | ⚠️ **TRACKED** |
| **`--manifest-out`** | `…/tiletie_pricing_20260812/RUN_MANIFEST.json` | ⚠️ **TRACKED** |
| **`--smoke-manifest`** | `…/tiletie_pricing_20260812/SMOKE_MANIFEST.json` | ⚠️ **TRACKED** |
| `--out-root` | `/mnt/c/carc-shared/tiletie_pricing_20260812` | — (share side) |

**The rule, widened:** **every one of those six flags is passed explicitly, in full, in every
invocation** — runbook, script, or hand-typed — for smokes and scoring alike. The three
**git-tracked** defaults (`--gate-out`, `--manifest-out`, `--smoke-manifest`) are called out
because they do not merely read the wrong corpus, they **mutate a closed run's tracked artifacts**.
And `--gate-out` is the sharpest of the three: **it fires from the PREFLIGHT, before any leg
runs**, so it needs no mention in your command and no scoring to do damage — the failure mode this
campaign has now met three times (`verify_tier1_rust`'s hard-coded `OUT_PATH`, R4-0.3's launcher
burst, and this) is **a default that writes somewhere a closed run lives.**

**Durable fix, spec'd for a FUTURE quiet window — NOT now (this amendment is the binding fix for
this run):** ⇒ **W11** — `run_tiletie` (and its siblings) **refuse to default-write into a
directory containing a manifest whose run-id is not the current run's**, failing loud with the
offending path rather than writing. A guard, not a convention: conventions are what these three
incidents each defeated.

---

## R4-1. What changes, in one table

| # | change | why |
|---|---|---|
| **A** | **§3 yield math re-derived from REALIZED rates**, full supply chain shown, **floors left as an owner parameter** | R3's §3 read raw census rows as final supply and set an S2 target its own capped-fraction constant refuted (`PREREG_FAILURE` §2) |
| **B** | **`G-DISJOINT` digest layer gains a pre-committed EXCLUSION rule with a hard bound** | a genuine cross-band board transposition is not a corpus leak, and "void the run" is the wrong price for one — but only while it is a trickle |
| **C** | **the two-box scoring layer (D1) is FIRST-CLASS**, not a deviation; **D2 is CLOSED AS UNNECESSARY** | the IF leg has dispatched to rust on `walled` since 2026-08-02; there was never a swap to make |
| **D** | **band arithmetic: base + extension (+ optional top-up), `G-BAND` generalised to N files** | 135e9 is retained as input; extension needs a fresh range; R3's two-file form does not stretch to three |
| **E** | **cost basis re-based on MEASUREMENT** (generation `c`; both IF `c` figures carried) | carrying a 3.3× stale commitment forward would re-manufacture the cost-model-miss disclosure |

Everything else — every estimand, bar, branch condition, rider and gate conjunct not named
above — is **identical to R3.3**.

---

## R4-2. (A) Supply chain and sizing — from realized rates

**The R3 error, in one line:** raw census rows are not positions. Two reductions apply, and the
second is mandated by the design's own §6 dedupe.

### R4-2.1 The measured chain (band 135e9, pre-scoring counts only)

**Measured integers first; factors are back-derived and marked `≈`.** (R4.1/A1: R3's chain printed
factors that did not multiply to its own terminus — `1,400 × 0.54 × 0.735 = 555.7 ≠ 551`. The
integers are what was counted; the split between qualification and dedupe is an approximate
decomposition of the one composite that was actually measured.)

```
S1  (--max-per-game 4, 350 games)
    raw census rows                  1,400   MEASURED
    realized qualifying-deduped        551   MEASURED
    composite survival              0.3936   MEASURED = 551 / 1,400
      of which  qualification        ~0.54   ~ approximate decomposition; the two
                afterstate dedupe   ~0.729   ~ factors are pinned to the composite,
                                             ~ not independently counted
    =>  r_S1 = 551 / 350 = 1.574 / game      SIZING CONSTANT

S2  (--max-per-game 3, 500 games)
    raw census rows                  1,500   MEASURED
    qualifying-deduped tied plies      613   MEASURED  (composite 0.4087)
    capped                             103   MEASURED  (fraction 103/613 = 0.168)
    =>  r_S2cap = 103 / 500 = 0.206 / game   SIZING CONSTANT
```

⭐ **Ceiling-independence cross-check (R4.1, corroboration).** S1 realizes **39.4%** of its mining
ceiling (551/1,400 at `--max-per-game 4`); S2 realizes **40.9%** (613/1,500 at 3). Agreement to
**1.5 pp across different ceilings** is direct evidence that the qualification × dedupe reduction
is **ceiling-independent** — which is what licenses quoting `r_S1` and `r_S2cap` as rates per game
rather than as artifacts of one mining depth.

**The capped fraction reconciles:** realized **0.168** against the pre-registered constant
**0.1807** is **z ≈ 0.84σ** on n=613 — agreement, not a revision. It was R3's *target* that
contradicted the constant (by ~10×), not the world.

**These two rates — `r_S1 = 1.574` and `r_S2cap = 0.206` qualifying-deduped per game — are the
sizing constants of record for R4.** They are measured, on this exact configuration, at
`--max-per-game` 4 and 3 respectively. Changing either mining ceiling invalidates the
corresponding rate and requires a re-measure, not a re-scale.

### R4-2.2 Games needed — **the floor is an owner parameter**

Banked and reusable: **S1 551**, **S2 103**. Additional games
`= ⌈(n₁−551)/1.574⌉ + ⌈(n₂−103)/0.206⌉`. Cost basis §R4-5.

| option | n₁ | n₂ | **+games** (S1 / S2) | gen wh | scoring wh | **TOTAL wh**¹ | at smoke `c_IF` | wall h | false-VOID² S1 leg / S2 leg / **EITHER** |
|---|---|---|---|---|---|---|---|---|---|
| FULL targets | 1,350 | 1,100 | **5,348** (508 / 4,840) | 552.6 | 929.0 | **1,493** | 1,082 | ≈32 | 0.38 / 0.45 / **0.82%** |
| all-floors³ | 1,283 | 1,045 | **5,039** (466 / 4,573) | 520.7 | 882.8 | **1,414** | 1,024 | ≈30 | 0.28 / 0.34 / **0.62%** |
| **S2 at 700** (PLAN_J's own floor) | 1,350 | 700 | **3,407** (508 / 2,899) | 352.1 | 819.0 | **1,181** | 819 | ≈26 | 0.38 / 0.97 / **1.35%** |
| S2 at 500 | 1,350 | 500 | **2,436** (508 / 1,928) | 251.7 | 764.0 | **1,025** | 687 | ≈23 | 0.38 / 1.38 / **1.75%** |
| S2 at 400 | 1,350 | 400 | **1,950** (508 / 1,442) | 201.5 | 736.5 | **947** | 621 | ≈21 | 0.38 / 3.74 / **4.10%** |
| **S1 ONLY** (rung 3 dropped) | 1,350 | — | **508** (508 / —) | 52.5 | 626.5 | **684** | 407 | ≈16 | 0.38 / — / **0.38%** |

¹ **TOTAL is not gen + scoring**: it also carries champ picks (`(n₁+n₂) × 13.755` worker-s) and,
where rung 3 runs, `D-DRAW`'s 2.0 wh. Both are small; both are in the total.
² ⭐ **REQUIRED reading before choosing (R4.1/C2, R4.2/C7).** The R4-3 exclusion bound is
`⌈0.005 × n⌉`, so it **shrinks with the floor while the collision rate does not**: at S2 = 400 the
bound is **2** and, at the observed 0.181%/position density (λ = 0.73), the chance of a **spurious
VOID** — that stratum voided by ordinary transposition luck rather than by any defect — is
**3.74%**. **`EITHER` is the number that matters for the decision**: the probability that *some*
stratum voids, `1 − (1−p_S1)(1−p_S2)` — **4.10% at S2 = 400 versus 0.82% at FULL, a 5× spread.**
(Presenting only the S2 leg would understate every row, since S1 can void independently.)
**The cheapest floor buys both the least power and the highest spurious-VOID risk.** Poisson,
`P(X > ⌈0.005n⌉)` per leg, at the observed density.
³ Row renamed from "committed FLOORS" (R4.1/C4): these are **targets**, and a target of
1,283/1,045 implies `G-COMPLETE` **gate** floors of `⌈0.95·n⌉` = **1,219 / 993**. The FULL row's
targets imply gate floors 1,283/1,045 — which is why the two rows look confusingly alike and why
the label was changed.

⭐ **The decision-relevant fact: rung 2 is nearly free and rung 3 is the entire cost.** The
B-ladder needs **508** more games; every game beyond that buys capped plies for the J rider,
which arrive at **0.206/game — 7.6× slower than S1's supply.** An owner choosing between these
rows is choosing how much to pay for rung 3, not for the run.

### R4-2.3 What each floor buys, in power — the honest ladder

`se(Δ_ora) = sd_Δ/√N`, `sd_Δ ∈ [0.9, 1.4]` (§6 CARRIED). A prediction resolves at 2σ iff
`sd_Δ ≤ d·√N/2`:

| N (capped) | resolves corrected **+0.0842** iff | resolves legacy **+0.1382** iff |
|---|---|---|
| 1,100 | `sd_Δ ≤ 1.396` — **99.3%** of the bracket; the bar is `1.4` (R3's known blind spot) | `≤ 2.292` ✅ whole bracket |
| 1,045 | `≤ 1.361` — 92.2% | `≤ 2.234` ✅ |
| 700 | `≤ 1.114` — **only the optimistic ≈43%** of the bracket | `≤ 1.828` ✅ |
| 500 | `≤ 0.941` — **8.3%**: essentially the bracket floor only | `≤ 1.545` ✅ |
| 400 | `≤ 0.842` — **below the bracket: 0%, unresolvable at any `sd_Δ`** | `≤ 1.382` — **fails at the bracket top** |

*(Bracket fractions are `(threshold − 0.9)/0.5` over `sd_Δ ∈ [0.9, 1.4]`. R4.1/C5 quoted N=700 as
the "30.6th percentile"; this session computes **42.8%** and could not reproduce 30.6% — the
substantive point, that N=700 is **not** "the optimistic half", stands either way and the text now
says ≈43%.)*

**No option separates 1.400 from 1.244** (CARRIED §6). Below `N ≈ 700` the rung stops being a
test of the *corrected* multiplier and becomes a test of the *legacy* one only; at `N = 400` it
tests neither reliably. **A floor below 700 should be chosen only as a decision to answer a
narrower question, and the read-out must say which question was bought.**

---

## R4-3. (B) The `G-DISJOINT` digest layer — exclusion rule, pre-committed

**What happened is not a corpus leak.** One `c_position_digest` collision, **zero** root overlap,
**zero** rid overlap: two independently generated games from different bands reached the **same
board** — a transposition. **The three-layer gate did its job by catching it**, and the layered
design is vindicated: rid/root disjointness is guaranteed by construction, digest disjointness is
an empirical property that must be *measured*, and it was.

**The rule, fixed here, before any R4 number exists:**

1. **A TOTAL ORDER decides every collision, so no pair is unruled (R4.1/B1).** Order the corpora
   **spent Stage-1b/tiletie ≺ 135e9 (base) ≺ 137e9 (extension) ≺ 138e9 (top-up)**; on a collision,
   **the higher-ordered (later) position is excluded** and the earlier is never touched. This
   subsumes R3's "exclude the newer rid" and additionally rules the case R4's own band structure
   created and R3 could not have: **base ↔ extension collisions *within one stratum*.** R3's
   contiguous band made intra-stratum cross-band collisions impossible; R4's base+extension
   structure makes them **expected** — at the observed 0.181%/position density the base↔extension
   count at FULL is **order-1**, so leaving them unruled would have meant an unruled event on a
   healthy run.
2. **Intra-run cross-stratum collisions.** An S1↔S2 digest collision excludes the **S2** rid (S1 is
   the B-ladder's primary; S2 is the rider), regardless of band. Two strata sharing a board would
   contaminate the independent-replication rider that compares them.
   ⚠️ **This rule is measured by the SEVENTH comparison, `s1_vs_s2` (R4.1/B4).** Without it the
   rule governed a case **no comparison could see** — and it is the **largest** unmeasured case,
   not a corner: calibrating a per-pair collision probability from the single observed event gives
   **≈1–2 expected S1×S2 events at FULL** (1,350 × 1,100 pairs), **≈3.4× the base↔extension
   count** — the reviewer's independent estimate was 1.29 events and 2.7×; the spread is the
   assumed size of the spent reference corpus, and every version of the model agrees the case is
   order-1 and the biggest one left unwatched.
3. **Same-rank pairs (135e9×135e9, 137e9×137e9, S1×S1, S2×S2) are OUT OF SCOPE BY CONSTRUCTION,
   and that is stated rather than left implicit (R4.1/R4).** No comparison compares a stratum-band
   to itself, so no within-stratum duplicate board can be detected and **no exclusion can fire on
   one**. Should such a comparison ever be added, the total order is completed by a deterministic
   tiebreak — **the lexicographically-later `rid` is excluded** — so the rule is total in advance
   rather than after the first surprise. **Named residual:** within-stratum transposition
   duplicates are **unmeasured**; two positions in one stratum sharing a board would be treated as
   independent observations by a bootstrap that clusters on `root_id`. A within-stratum digest
   uniqueness check is cheap and is **recommended for a future prereg** — it is deliberately *not*
   added here, because adding a conjunct at freeze time is exactly the move this discipline
   forbids.
4. **The exclusion is OUTCOME-INDEPENDENT by construction and that is why it is legitimate.** The
   digest is a function of the board alone, computed at corpus-build time, before any value
   exists. It is the opposite of the 2026-08-14 open-city void, whose exclusion was rejected
   precisely because it was *not* outcome-independent.
5. **It happens before the positions are frozen.** Excluded rids never enter the **final**
   `POSITIONS_PLAN`, never reach a scoring leg, and **the completion floors are evaluated on the
   post-exclusion count** — so an exclusion can never be used to explain away a shortfall after
   the fact. ⚠️ **Read this together with rule 7's probe flow (R4-0.2):** applied naively — to the
   only build there is — this rule makes rule 7's bound vacuous, because the frozen corpus would
   then always report `n_excluded == 0`. The probe build is what lets both rules be true.
6. **The hard bound — ONE spelling, in both documents (R4.1/B3):**
   **`n_excluded ≤ ⌈0.005 × qualifying_deduped(stratum)⌉`**, per stratum. Above it, the stratum is
   **VOID** — not excluded, not disclosed-and-continued. *(R3 carried "≤0.5% AND ≤15 absolute" here
   and the `⌈·⌉` form in the READ_RULE — 6 vs 7 at n₁ = 1,350. The `⌈·⌉` form wins, being the
   binding document's. The "≤15 absolute" conjunct is **deleted as inert**: it can only bind when
   `0.005n > 15`, i.e. `n > 3,000`, which no option in R4-2.2 reaches.)*
7. **The bound is evaluated ONCE, on the PROBE's collision count, against the frozen denominator
   (R4.1/R1 + R4-0.2's mechanism).** The evaluated quantity is
   **`carried + residual`** — the exclusions measured on the **probe** build (which carries none)
   plus any fresh collisions in the **final** build (expected `0`) — judged against the
   denominator recorded in `RUN/FLOORS.json`, **not** against the realized corpus size. Otherwise
   the bound would grow with the corpus and R4-7's threat 1 ("generate more games if supply is
   short") would double as a way to buy headroom for exclusions after seeing them. **A nonzero
   `residual` is separately a determinism defect** — probe and final disagreed about one corpus —
   and is reported as such, never quietly folded in. **A VOID stratum stays void; the answer is a
   new prereg, never a bigger corpus.**
8. **Why 0.5%.** The realized rate is **1 / 551 = 0.181%**, so the bar carries ≈2.8× headroom: it
   passes the observed world comfortably and still fails a world in which transposition
   degeneracy is a *property of the generator* rather than an accident. That second world is a
   different finding — it would mean champion self-play revisits boards at a rate that makes
   "fresh corpus" the wrong description — and it must surface as a VOID, not be absorbed silently.
   ⚠️ **The bound's tightness is floor-dependent and the cheapest floor is the most fragile:** see
   R4-2.2's false-VOID column (0.45% at FULL vs **3.74%** at S2 = 400, S2 leg).
9. **Always reported**, on every branch: the count, the rate, the excluded rids, the bound they
   were measured against, and **`denominator_source`** — whether or not any exclusion occurred.

---

## R4-4. (C) Two-box scoring is first-class; the rust-IF question is closed

**The two-box scoring layer (chunk / allocation / merge) is an instrument choice of R4, not a
deviation.** Its six-clause gate-neutrality analysis is at [`../DEVIATIONS.md`](../DEVIATIONS.md)
§D1 and is **incorporated here by reference**.

**DELIVERED** at commit **`1670f030`** (builder worktree `agent-acb67fb738d22b57f`; 36 tests):
`stage_chunks.py` · `ALLOCATION.conf` · `run_scoring.sh` · `merge_legs.py` / `merge_scoring.sh`.
The neutrality argument, as delivered, in five points — **each mapped to the clause it discharges**:

1. **Seeds name only `(tag, rid, j, salt)`.** `world_seed`/`playout_seed` live in
   `oracle_score_pilot.py` and are **imported** by `tier1_rust_leg.py`, not re-implemented; the
   salt is a module constant passed to both drivers; prefix-stability is asserted **fatally at
   launch**. Not the chunk, not the box, not `M`, not the row index. ⇒ **C1** (already signed;
   this is its delivered confirmation).
2. **Chunks are whole-rid sets**; a rid never splits across boxes within a leg; and the merged
   tree is **byte-identical per rid** to a single-box run, tested end-to-end. ⇒ **C3 SIGNED**, and
   with (3) it is also the empirical discharge of **C4**.
3. **`run_tiletie` supports no subsetting**, so the chunk layer **materialises exact rid-subset
   positions dirs** rather than filtering inside a leg; `verify_leg_records` forces per-chunk
   out-roots plus a merge; `cap_j`/`salt` are asserted **per chunk at the exact addresses
   `G-UNCAPPED`/`G-SALT` read**. ⇒ **C4 SIGNED**: a chunk is an ordinary run over fewer rids, so
   per-record `Game` construction is structurally unchanged from single-box — which is what makes
   (2)'s byte-identity general rather than a property of the tested set.
4. **The merge never opens a record.** Bytes are copied; rids come from filenames; each per-leg
   `summary.json` is copied verbatim per chunk and never parsed. **No computed statistic exists
   anywhere in this layer** — which is why the merge cannot move a value even in principle. ⇒ **C2**
   (already signed) and **C6**.
5. **Allocation is STATIC**, not work-stealing: 8 chunks/stratum, local share 0.651 against a
   0.645 capacity ideal, strata sequential per CARRIED §9 item 10, two-box wall ≈ **20.2 h**.
   ⇒ **C5 SIGNED** — static allocation **removes the `--shared-claim` hazard class outright**
   (no claims ⇒ no stranded `.claim` files, and no clock-drift path by which a fast box silently
   steals another's work); resume is per-chunk against per-chunk out-roots.

**⇒ All six clauses are now signed.** Provenance is explicit: C3/C4/C5 are signed on the delivered
code and its forwarded neutrality report (`1670f030`), and the **acceptance check that confirms it
on the real corpus is `stage_chunks verify`'s re-derivation, run post-corpus** with the 4b address
audit. **If that re-derivation fails, R4 scores single-box** — wall-clock is the cheaper failure;
an allocation-dependent value is not.

⚠️ **`ALLOCATION.conf` is sized on the committed `c`.** If the 4b-pre remeasure moves the IF:ARB
ratio materially, the allocation is revisited **pre-launch**. It is a wall-clock knob and **cannot
move a value** — it selects which box scores which rid, and (1)–(4) make that choice invisible to
every output.

**D2 (rust IF judge) is CLOSED AS UNNECESSARY.** The `clair-puct` IF leg has dispatched to rust on
`walled` since 2026-08-02 (`run_tiletie.py:117` `JUDGE_BACKEND`, `:154` `RUST_OK_PROFILES`; gate
`measurement/rustport_p6/GATE_ORACLE_PILOT_BACKEND.json` PASS, 20 positions / 940 field checks /
0 mismatches). There was never a swap to make: the estimand was never at risk, and the 9.4× is
that already-taken swap's own captured speedup. Recorded in `../DEVIATIONS.md` §D2.

⚠️ **Standing constraint, promoted to a threat-model line (it was previously implicit).** The rust
clairvoyant path **requires `walled`**: `RustCarryClairvoyantAgent` mirrors no rules config, and
`fixed_v1` / `app_aug2` **fail loud** rather than grade under the wrong rules. R4's corpus is
`walled`-only, so this is safe **today** — and it is stated here so that **no future stratum,
top-up or extension silently mixes rules profiles.** A profile change is not a knob change; it
changes which engine may price the leg.

---

## R4-5. (E) Cost basis — re-based on measurement

**Generation.** R3 committed **990** worker-s/game, inherited. The fresh same-config GEN smoke
measured **297.6**. R4 commits **372.0 = 297.6 × 1.25** — the measurement plus a margin, in the
direction that cannot under-commit. The one-sided HALT (CARRIED §7) therefore trips above
**465.0** worker-s/game, i.e. ≈1.56× the measured rate: a real trigger, not a formality. *Carrying
990 forward would have re-manufactured exactly the cost-model-miss disclosure this campaign has
already written twice.*

**IF (`clair-puct`) — both figures carried, deliberately.**

| figure | value | provenance |
|---|---|---|
| **committed** | **2.35** worker-s/playout | banked `elapsed_secs`; **plausibly the W30-CONTENDED rust price** |
| smoke-indicated | **1.2313** | `SMOKE_RUST_MANIFEST.json`, idle box, `M=32`, sims=100 |

The **1.91× gap is not resolved here and is not guessed at**: the pre-run `c`-remeasure (CARRIED
§7, at production knobs, on an idle box) settles it. **§R4-2.2's ETA is sized off the committed
2.35** — conservative, so the envelope cannot be undershot — and the **`at smoke c_IF` column
states the realized-likely total** so the owner's envelope math is honest in both directions.
`c_ARB` is unchanged at 0.178232.

**One consequence worth stating:** at the smoke-indicated price the FULL-targets option (1,082 wh)
lands **inside** the already-funded 1,174 wh envelope, while at the committed price it is
**+27%**. The floor decision and the `c`-remeasure outcome are therefore coupled, and the honest
order is: **remeasure first, then choose** — or choose at the committed price and bank the
surprise as headroom.

---

## R4-6. (D) Band arithmetic

| band | range | status |
|---|---|---|
| `135000000000` | +0…+849 (850 games) | **RETAINED as valid input** (`PREREG_FAILURE` §3), minus rids excluded by R4-3 |
| `136000000000` | — | **RELEASED UNUSED.** R3's top-up reservation; released rather than repurposed so "which prereg consumed which band" stays unambiguous |
| **`137000000000`** | **split into two committed sub-ranges, S1 then S2** (below) | **EXTENSION generation** — claimed at run time, `decision_influenced=no`, notes marking it **OFFLINE CORPUS SUBSTRATE** |
| `138000000000` | +0…+499 | **RESERVED** for the blind top-up clause, not licensed |

⚠️ **The extension band is SPLIT BY STRATUM, and the split is committed (R4.1/B2).** `+games` is a
**sum of two disjoint requirements**, and `strata_root_overlap == 0` is a gate conjunct — so
mining both strata from one undivided range (the natural reading of R3's parameterisation) would
**fail `G-DISJOINT` §2b(iv) on a perfectly healthy corpus**. R3 split band 135e9 at +349/+350
implicitly; R4 dropped the split when it made the size a parameter. `RUN/FLOORS.json` therefore
carries **`games_extension_s1` and `games_extension_s2`** and the two explicit sub-ranges:

| option | S1 sub-range | S2 sub-range |
|---|---|---|
| FULL | `137e9 +0…+507` | `+508…+5347` |
| all-floors | `+0…+465` | `+466…+5038` |
| **S2 at 700** | `+0…+507` | `+508…+3406` |
| S2 at 500 | `+0…+507` | `+508…+2435` |
| S2 at 400 | `+0…+507` | `+508…+1949` |
| S1 ONLY | `+0…+507` | *(none — `games_extension_s2 = 0`)* |

A game seed mined into the wrong stratum is a `G-DISJOINT` failure, not a bookkeeping slip.

**`G-BAND` generalises from two files to N.** Each generated range emits its **own**
`verify-champgames` file and is checked **against its own range** — `band_ok`, `seed_band`,
`n_out_of_band == 0`, `n_duplicate_seeds == 0` — and **the per-file game floors are a committed
table, not one blanket number** (R3's B1 lesson generalised: the base carried the floor and the
top-up carried the increment; with three possible files that rule must be tabular). Never one
invocation over a widened band. Exact conjunct: `READ_RULE.md` §2.

---

## R4-7. Threat model — what could still make this unreadable

1. **The rates are measured on ONE band.** `r_S1`/`r_S2cap` come from 850 games of band 135e9.
   If the extension band's supply differs materially, the floors move. **Mitigation, and it is a
   real one:** supply is knowable **before scoring** — the corpus build counts it — so a shortfall
   surfaces at the corpus stage, where the only cost is generation, not pricing.
2. **The `c_IF` gap (1.91×) is unresolved until the remeasure.** Sized conservatively; the HALT is
   one-sided and fires before the expensive legs.
3. **Transposition degeneracy may be a generator property**, not an accident — R4-3's bound is
   the detector, and its answer is VOID, not absorption.
4. **`walled`-only is load-bearing** for the rust IF path (R4-4).
5. **The merge layer is a GATE-SUPPORT SURFACE, and it is fail-closed by design.** `G-SALT`,
   `G-M`, `G-BACKEND` and `G-LEAF` all read `RUN_MANIFEST_*` fields — which, under chunking, must
   be *merged* from N per-chunk manifests. A naive merge would silently adopt one chunk's value
   and the gates would read a field no longer true of the whole run. `merge_legs.py` instead
   **raises** when any gate-addressed field differs across chunks (a **mixed-rev detector** — a
   chunk scored at a different rev, salt or backend cannot be merged into a manifest that claims
   uniformity); counters are summed; `workers` is nulled (box-specific, meaningless merged);
   `resolved_backend_by_leg` is unioned; and **an unclassified differing key raises** rather than
   defaulting. That last rule is the important one: it fails closed on fields nobody anticipated.
6. **`stage_chunks verify` is the acceptance check for the whole layer**, re-deriving the chunking
   post-corpus; a failure sends the run single-box rather than into a diagnosis.
7. **D1's clauses are all signed (R4-4), but on delivered code, not on a run.** Point 6 is what
   converts that into evidence about *this* corpus.

## R4-8. W-code delta (small; everything else carries)

| item | change |
|---|---|
| **W5** | `GATE_DISJOINT.json` gains: (0) the **probe → gate → apply → carry-forward** flow of R4-0.2 (`--carry-exclusions`), with the final report carrying **`carried`** and **`residual`** per stratum — the quantity the bound is judged on is `carried + residual`; (i) the R4-3 **exclusion** semantics — per-comparison collision lists, the excluded-rid set, the rate, the bound, **`denominator_source`** (R4.1/R5 — it is an address `G-DISJOINT` reads, and **ABSENT IS FAIL**, so a builder working from this table must emit it), and `void` vs `excluded` as distinct outcomes; (ii) a **SIXTH** comparison **`base_vs_extension`** — one key, summed top-level layers plus the required `by_stratum` block (R4-0.1) — the intra-stratum cross-band case R3's contiguous band made impossible and R4's band structure makes expected; and (iii) a **SEVENTH** comparison **`s1_vs_s2`**, all three layers (R4.1/B4) — the *largest* previously-unmeasured case (≈1–2 expected events at FULL, ≈3.4× base↔extension), and the one R4-3 rule 2 already claimed to govern. Rid and root layers cost nothing extra there, being zero-tolerance already. The total order of R4-3 rule 1 decides which side is excluded |
| **two-box layer** | **DELIVERED `1670f030`** — `stage_chunks.py`, `ALLOCATION.conf`, `run_scoring.sh`, `merge_legs.py`/`merge_scoring.sh`, 36 tests (R4-4). No further W-work; its acceptance check is `stage_chunks verify`, post-corpus |
| **W6** | (i) **run ALL gates and aggregate — never `set -e`-abort on the first failure** (that is why `GATE_DRAW.json` never emitted); (ii) build the **probe**, gate it, then carry R4-0.2's exclusions into the **final** `POSITIONS_PLAN`; (iii) size from the R4-2 rates |
| **W10** | (i) extension-band generation: base + extension (+ optional top-up) as **separate invocations into separate directories**, each with its own `verify-champgames` file (the §0.L pattern, now three-way); (ii) **`--dry-run` / `WIDENING_GEN_DRY_RUN`** — resolves everything, prints `argv`, **creates nothing** — and **all tests use it** (R4-0.3: a test that can exec a production launcher is a launcher missing a mode) |
| **W3** | `G-BAND`'s N-file form and the exclusion counters surfaced in the verdict block |
| carried unchanged | W2 · W7 · W8 + fixtures · W9 (`D-DRAW`) · `STAGE1B_LADDER.json` · the 4a/4b harness |

## R4-8b. The order of operations, written down (R4.1/R2)

The floor is an owner parameter, so the order in which it is chosen and frozen is what makes it
**ungameable**. This sequence is binding:

1. **`c_IF` remeasure** (the 4b-pre judge smokes, idle box) — settles the 1.91× gap **before**
   anyone chooses a floor, so the choice is made against a real price.
2. **Owner picks a floor** from R4-2.2, seeing R4-2.3's power ladder and the false-VOID column.
3. **`RUN/FLOORS.json` is written** — `{n1, n2, option_label, r_s1, r_s2cap, games_extension_s1,
   games_extension_s2, sub_ranges}`.
4. **The blind commit**: the R4 pair **and `FLOORS.json`, in ONE commit.**
5. **Only then is the extension band claimed**, and generation starts.
6. **Corpus build** (census → positions → champ picks → gates).
7. **`stage_chunks verify` — the two-box acceptance check — runs HERE (R4.1/R6): after the corpus
   build, beside the 4b address audit, BEFORE the first scoring leg.** It re-derives the chunking
   against the real corpus and is the step that converts R4-4's signatures (given on delivered
   code) into evidence about *this* corpus. **A failure sends R4 single-box** — a decision that is
   free at this point and expensive one leg later.
8. **Then** 4b-pre's smokes have already priced the legs, and scoring runs: S1, then S2.

⚠️ **`FLOORS.json` must exist before the extension band is claimed and before one game is
generated.** A floor chosen — or adjusted — after supply is known is a floor fitted to the data,
which is the failure `G-COMPLETE` exists to prevent. It is also the denominator R4-3 rule 7's
exclusion bound is evaluated against, so it must predate the corpus for that reason too.
*(Note the ordering interacts with R4-4: `ALLOCATION.conf` is sized on the committed `c`, so step 1
may also revise the allocation — a wall-clock knob, never a value.)*

## R4-9. Owner decisions

1. ⭐ **The floor** — pick a row of R4-2.2. R4-2.3 says what each buys. **Recommendation: `S2 at
   700`** — PLAN_J's own floor, 3,407 games, ≈1,181 wh committed / ≈819 wh at the smoke price,
   and it keeps the corrected multiplier resolvable across the optimistic half of the `sd_Δ`
   bracket. `S1 ONLY` is the honest fallback if rung 3's price is not worth its question.
2. **Remeasure `c_IF` before choosing, or choose at the committed price?** The 1.91× gap moves the
   FULL option in and out of the funded envelope.
3. **Ratify the R4-3 exclusion rule and its 0.5% / 15 bound.**
4. Carried from R3.3 and still open: the `I6` amendment pre-approval; the offline-corpus band
   registry question; the `B=64` game-cell trigger.
