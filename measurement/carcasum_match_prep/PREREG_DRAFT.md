# Carcasum external-reference match — PREREG **DRAFT**

> **STATUS: DRAFT — NOT BLIND-COMMITTED, NOT AUTHORISED, NOT LAUNCHED.**
> Nothing in this file is frozen. It exists so that the *design* is on record before any
> Carcasum strength number exists, and so the blind commit — when and if it happens — is a
> review of a written plan rather than a fresh act of authorship. The band row below is
> **planned, not claimed**: `governance/BAND_REGISTRY.csv` has NOT been appended to.
>
> **Gate:** this prereg may not be blind-committed until the divergence audit
> ([`AUDIT_PLAN.md`](AUDIT_PLAN.md), gate 5 of the build) passes N/N with zero REAL
> divergences. A strength number measured across a rules disagreement is a rules result.

---

## 0. Why this cell exists

Structural blocker #1: **no strong non-saturated reference exists.** The one out-of-lineage
ruler the program owns — JCZ `LegacyAiPlayer` — is sliding toward saturation (champion wr
**0.6406 / +100.4 elo** unmodified, **0.6981 / +145.6 elo** with the tie-arbiter lever;
[`measurement/jcz_tiearb_20260817/READOUT_b134.md`](../jcz_tiearb_20260817/READOUT_b134.md)),
and JCZ has **no knobs** — no depth, no budget, no difficulty — so there is no stronger JCZ to
dial up.

Carcasum ([`docs/research/EXTERNAL_INVENTORY_R2_2026-08-23.md`](../../docs/research/EXTERNAL_INVENTORY_R2_2026-08-23.md) §2)
is the only candidate found in two rounds of sweeping that clears every gate at once: exactly
our rules scope, AGPL, harnessable, and — uniquely — **it has a budget knob** (seconds or
playouts per move). That knob is the property a non-saturating ruler needs and the property
JCZ lacks.

### 0.1 The caveat that travels with this cell, always

The inventory's headline arithmetic — Carcasum MCTS at 84.0 % vs its own JCZ port ⇒ ≈ +288 elo
over "a JCZ AI" ⇒ ≈ **+188 elo above our champion** — is **a hypothesis, not a prediction, and
must never be quoted as one.** It chains two win rates through two *different builds of a third
program*, and this program has already been burned by exactly that class of inference (the leaf
effect is documented non-transitive in `clean_eval/CLEAN_EVAL_AUDIT.md`; CL-070 showed a
same-family anchor mis-ordering a +50 elo contrast *including the sign*). Two concrete reasons
it can be wrong are already known:

1. **Their "JCZ Player" is not our JCZ.** It is a 2014 adaptation of the JCZ **1.x/2.x**-era AI;
   ours is the **4.x** class. The thesis itself says the port "does not play exactly like the
   original", omits a JCZ undo bug, and is "much too slow".
2. **Their own ladder contradicts the transitive story.** Their `JCZPlayer` beats their
   hand-written greedy `SimplePlayer v3` by only **51.28 %** — statistically level with a simple
   greedy heuristic. If our JCZ reference is meaningfully stronger than a simple greedy, their
   JCZ port is weaker than ours and the 84 % overstates Carcasum's standing against us.

**Therefore this cell is registered as a measurement with no predicted sign.** Any readout that
opens by comparing the result to "+188" has misread this section.

---

## 1. Primary question and estimator

**Primary:** the champion's strength against `MCTSPlayer` at **one named budget**, measured as
the **deck-paired margin in points**, with win-rate/elo reported alongside.

- **Estimator of record:** deck-paired margin, `mean(margin_seat0 + margin_seat1)/2` over decks,
  with its paired SE and z. This is the within-band deck-paired class — the robust one, the one
  unaffected by the cross-band over-dispersion amendment (CL-068).
- **Secondary:** win rate → elo, `1σ ≈ 695·√(0.25/n)` within-band ⇒ n=400 ⇒ **±17.4 elo**.
- Both are reported. The paired one is load-bearing, exactly as in the JCZ confirm
  ([`measurement/jcz_match_20260809/CONFIRM_READOUT.md`](../jcz_match_20260809/CONFIRM_READOUT.md) §1).

**n = 400** = 200 decks × 2 seatings (seat-swapped CRN). Rationale: the JCZ match used the same
size and resolved a +111 elo effect at z 7.55; n=400 is a verdict only for effects ≥ ~35 elo
(2σ) and cannot resolve +20 elo. If the true gap is small, the pre-registered outcome is
**"inconclusive at n=400"**, not a top-up improvised after seeing the number — see §5.

### 1.1 What is NOT being asked here

**The budget ladder is deferred to rung 2.** This cell prices the champion against Carcasum at
*one* budget. It does **not** attempt to locate the budget at which Carcasum equals the
champion, and it does not fit a slope across budgets. Reason: Carcasum's own doubling ladder
(thesis Table 5.5) prices the knob at roughly **+44 elo per doubling and shrinking** at the top
of its measured range (16384 vs 8192 playouts → 56.33 %), so a ladder is several cells of work
and only worth buying **after** rung 1 establishes that the opponent is in a useful range at
all. Locking the ladder question out of rung 1 is what stops this cell from quietly becoming a
budget-shopping exercise with a post-hoc rung.

---

## 2. Configuration (to be frozen at blind commit)

| | |
|---|---|
| **Ours** | the champion of record in `governance/PRODUCTION.yaml` at its deploy budget, rust backend, `verify=True`. Leaf hash stamped in every record's manifest. **No tie-arbiter lever** unless a separate cell says otherwise — the arbiter is a live, separately-governed contrast and mixing it in here would confound the reference reading. |
| **Theirs** | `MCTSPlayer<Utilities::PortionUtility, Playouts::RandomPlayout>`, `Cp = 0.5`, `reuseTree = false`, no node priors / progressive widening / progressive bias. **This is the exact configuration the thesis's 84 % was measured at** — and, per the thesis's own conclusions, *not their best* (they conclude a normalised Heyden evaluation + ε-greedy playouts is stronger). Deliberate: matching the published cell is worth more than maximising the opponent, and "their best" is a rung-2 question. |
| **Their budget** | **`budget_ms = 5000`** — the thesis's 5 s/move. ⚠️ Their timer is `boost::chrono::thread_clock`, i.e. **thread CPU time, not wall clock**; under `nice -n 19` on a loaded box the wall cost can exceed 5 s while the search still gets its 5 CPU-seconds. Whatever the smoke measures is what the readout reports; the *pre-registered* budget is the 5000 ms setting, not a realized wall figure. |
| **Rules** | `fixed_v1` + `CARCASSONNE_FIX_R9=1`, both sides. **Not a knob.** Carcasum's `basic.xml` declares `RCr` as `<farm city="N">EL WR</farm>` — the same half-edge convention that produced R9 — so R9-off would reintroduce genuine farm-partition divergences. Games from this cell are therefore **not comparable to `walled` (R9-off) production elo**, the same caveat the JCZ match carries. |
| **Their patches** | the modern tiny-city rule, and whatever else the audit forces — the exact list lives in `vendor/carcasum/CARCASUM_PATCHES.md` and is echoed by the driver's `ready` line into every manifest. A game whose manifest patch-list differs from the frozen one is not part of this cell. |
| **Hardware** | one box, exclusive tenancy. **A timing bench is an exclusive tenant** — no agent compute, no other run, on the box for the duration. Which box: to be named at blind commit, after the smoke's projected wall (§4) is known. |

---

## 3. Band plan — **planned, not claimed**

Next free band is **1.41e11** (`governance/BAND_REGISTRY.csv` currently tops out at 1.40e11,
retired). The row below is written out so the blind commit is a copy-paste, and is **not to be
appended until the cell is authorised.**

```
band_seed_start : 141000000000
label           : CARCASUM EXTERNAL-REFERENCE MATCH, RUNG 1 — champion vs Carcasum
                  MCTSPlayer<PortionUtility,RandomPlayout> @ Cp=0.5, budget 5000 ms/move,
                  fixed_v1 + CARCASSONNE_FIX_R9=1, deck-paired seat-swapped CRN.
tier            : claim
status          : (open at commit)
claimed_date    : (date of blind commit)
decision_influenced : (blank until close-out)
evidence_or_claim   : measurement/carcasum_match_prep/PREREG_DRAFT.md -> the committed prereg
notes           : Seeds 141000000000..141000000199 = 200 decks x 2 seats = n=400.
                  ** TOP-UP RANGE RESERVED UP FRONT: 141000000200..141000000299 **, consumed
                  ONLY if the §5 top-up branch fires. (Reserving up front is the lesson the
                  1.21e11 row had to record at close-out and the 1.19e11 row got right.)
```

**Band hygiene.** A band that influenced a decision retires from confirmatory use. The audit
games (gate 5) and the smoke games (gate 6) **must not** use this band — they use dev-tier
seeds and are explicitly non-confirmatory, because they are run *before* the hashes freeze and
their whole purpose is to be looked at.

---

## 4. Prerequisites — all must be green before blind commit

1. **Build** — `vendor/carcasum` at upstream `5f5e3654d31ce8cef0eebeb80a7fb989ef7c2550`, the
   driver binary built, its sha256 pinned, `CARCASUM_PATCHES.md` complete and re-appliable.
2. **Tile mapping** — `tests/data/carcasum/TILE_MAPPING.tsv` verified against *their loader*
   (not merely their XML) by `tests/test_carcasum_tile_oracle.py`, and the deck-count multiset
   agreeing 72/72 under the garden-variant collapse.
3. **Divergence audit (THE gate)** — ~50 cheap games (their AI at a low budget vs our
   tier1-greedy or random; the point is rules coverage, not strength):
   - final-score agreement **N/N**, zero REAL divergences;
   - **per-terrain** agreement, not just totals — the `score_detail` diff is what licenses the
     word *farms* in any later sentence;
   - **farms actually exercised in > 80 % of audit games** (a farm-free corpus certifies
     nothing about farm scoring, and farms are where the R9-class bugs live);
   - unplaceable-tile redraw exercised at least once, and agreeing.
   Any irreconcilable divergence is reported loudly and **blocks this cell**.
4. **Smoke** — 4 games at production knobs, timed, with both sides' realized s/move reported and
   a projected wall for n=400 (§6 of the build report). A smoke is not evidence of strength;
   n=4 is noise, and this prereg pre-commits to **not** reading its win/loss.

---

## 5. Decision rules, fixed in advance

Let `d` = deck-paired margin in points, `z = d / SE(d)`, over 200 decks.

| branch | condition | pre-registered action |
|---|---|---|
| **A — usable reference** | `\|z\| ≥ 3` | Report the sign and size. Carcasum enters the ruler set at this budget. Queue rung 2 (the budget ladder) to find the budget where it equals the champion — *that*, not this cell, is the non-saturating-ruler deliverable. |
| **B — level** | `\|z\| < 3` and `\|d\| ≤ 2.0 pts` | Report **level at this budget**. A level opponent is the *most* useful ruler outcome, not a null: it means the knob is positioned where it can move in both directions. Queue rung 2 anyway. |
| **C — inconclusive** | `\|z\| < 3` and `\|d\| > 2.0 pts` | **Top-up once** to n=800 using the reserved range `141000000200..141000000299`, then re-read under the SAME rule. One top-up, pre-registered, no second. |
| **D — void-contaminated** | voids or REAL divergences > 1 % of games | **No strength number is published.** Diagnose, patch, re-audit, re-run. A win rate over a rules disagreement is a rules result. |

**Read-rule discipline:** these branches are fixed *before* any game is played, and the fired
branch **is** the authorisation to execute it — a fired trigger gets run and reported, not
re-litigated.

**Winner's-curse note.** Carcasum was selected *because* an external document reported a large
number for it. That is a selection effect on the candidate, and it is why §0.1 refuses to carry
the +188 forward and why branch B is written as a success rather than a disappointment.

---

## 6. Close-out obligations

The six-touch checklist applies in full: `experiments/results.csv` row → `DECISIONS.md` index
line → status banner on this doc → governance row flip (`BAND_REGISTRY.csv` status,
`CLAIM_REGISTRY`) → `STATUS.md` top block → roadmap line in
`docs/PROGRAM_ROADMAP_2026-07-07.md`. Then `python3 scripts/doc_lint.py`.

Additionally, and regardless of outcome: a **`docs/LEVER_INDEX.md`** row for *"Carcasum external
reference"*, plus DECLINED rows for *Carcassonne-SGE*, *SYNCS Bot Battle*, *Asmodee Conqueror*,
and *OpenSpiel / Ludii — game absent*, so the next reader's grep cannot miss that these were
looked at (`EXTERNAL_INVENTORY_R2` §6).
