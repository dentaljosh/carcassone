# BURIED CAVEATS AUDIT — 2026-07-30

**Status:** FINDINGS FOR TRIAGE · **Auditor:** Opus (read-only pass) · **Commission:** Joshua,
2026-07-29 night — *"the failure mode we caught tonight. if missing the note about sims being
underpowered. I wonder how much else is buried in this project. ask an opus auditor to look over
the history of this project and see what else it funds."*

> **This memo changes nothing.** No `docs/LEVER_INDEX.md` row, no roadmap line, no
> `governance/CLAIM_REGISTRY.csv` edit was made — findings go to Joshua for triage first, per the
> commission. Every quote below was read from the named file/line (or the named on-disk artifact)
> during this pass.

## The search template

The seed case: [measurement/distill_flywheel_20260715/HANDOFF.md](../../measurement/distill_flywheel_20260715/HANDOFF.md#L57)
warned **before launch** that the flywheel's generation budget was too cheap for a null to mean
anything — and the *conclusion* ("growth REFUTED, learned track closed") propagated while the
*caveat* survived only in a memory file and one HANDOFF line, until Joshua re-derived it from
scratch two weeks later. It is now roadmap G8 / `rodv3`.

So this audit hunted six signatures: (1) nulls with an unresolved recorded scope-limit;
(2) advisor warnings overridden at launch whose consequence came true; (3) pre-registered
branch tables whose AMBIGUOUS branch fired with no follow-up; (4) claim falsifiers since met;
(5) scope-limited verdicts cited beyond scope; (6) "cheapest discriminator named, never run".

**The headline result is uncomfortable: the single clearest instance is not historical.** It is in
a run that was pre-registered last night, and the mechanism is the *same* mechanism, carried
forward in a weakened form.

### Ranking at a glance (most decision-value first; section order in this file is by ID, not rank)

| rank | id | one line | cost to resolve |
|---|---|---|---|
| 1 | **F1** | `rodv3` turn 1 reproduces the ¼-budget confound it was funded to resolve, and pre-commits a DEAD branch that would close lever 6 on it | free (prereg amendment) · or 2–4× gen compute for the decisive version |
| 2 | **F9** | five live surfaces — incl. `STATUS.md` twice and CL-068 — still say search budget is a closed lever, one day after it was promoted | free |
| 3 | **F6** | blocker #2 (leaf ceiling): CL-010 is `Provisional` since 2026-06-08, its falsifier **ran** 2026-06-19 and was never adjudicated, and two top-level docs cite it as established | free |
| 4 | **F10** | CL-059's own re-open condition (a) FIRED via CL-067 and the claim is still `Closed`; both index surfaces still assert a channel-level kill | free |
| 5 | **F13** | S-R3-1 (residual target ±2 into a ±1 head) was deferred as "Lever for attempt #2", attempt #2 ran without it, and Arm B is pre-committed to the same shape | minutes (histogram on existing data) |
| 6 | **F2** | the RoD-v2 anchor is measured to mis-order a +50 elo contrast by ~70 elo; that ceiling lives only in a CSV counterevidence column, not where the anchor is still used | free |
| 7 | **F14** | tonight's overnight watchdog hardcodes `.json`, so its orphan-claim guard is inert (and inverted) on the `.npz` gen cells it is armed on | one line |
| 8 | **F12** | the σ×1.8–2.2 cross-band over-dispersion correction lives only in a claim row + an ephemeral STATUS block, not in the canonical power guidance | one sentence |
| 9 | **F11** | three aggregating one-liners are factually wrong about their own evidence ("no open cell", "always negative", "inert under BOTH regimes") | free |
| 10 | **F7** | the 2026-05-20 false-negative audit measured a ~50% kill error rate and named 5 reservoirs; 3 were never swept and none is indexed | free (paper triage) |
| 11 | **F15** | adopted sealed-band governance never got its registry; the prescribed check is documented to fail silently open | ~1–2 h |
| 12 | **F8** | v1 leaf read *nominally stronger* than v2.7 on the clean ruler (−24.4 ± 16.5); fork declined for re-tune cost, never opened, never indexed | free (arithmetic) → 1 slow-path cell if ambiguous |
| 13 | **F3** | CL-071's own counterevidence asks for a clock-cost reconciliation with no owner | ~15 min |
| 14 | **F16** | the fair width sweep fixing the deployed allocation predates the determinization-leak fix (deflated: the record says those cells stay valid) | one sentence |
| 15 | **F4** | `LEVER_INDEX` contradicts itself on whether the oracle-pilot discriminator ran (the dedup index's one job) | one line |
| 16 | **F5** | a fixed bug still recorded as "queued for a fix" in CL-069 | one line |

**Thirteen of sixteen cost nothing but a text edit**, and only F1 could consume real compute. That
distribution is itself the finding about this project (see the systemic read).

---

## F1 — `rodv3` turn 1 reproduces the very confound it was funded to resolve (⚠️ LIVE, gen launching)

**Rank: highest. Actionable before the gate is funded, and the fix is free.**

### The buried clause, verbatim

The recorded confound is **relative**, not absolute —
[measurement/distill_flywheel_20260715/HANDOFF.md:57-60](../../measurement/distill_flywheel_20260715/HANDOFF.md):

> ⚠️ **sims200 = ¼ budget, BELOW the advisor's ½-budget "safe" floor.** A NULL result is AMBIGUOUS
> (real, OR gen search too weak to beat **the net's own 2752-distilled priors** → no gradient).
> **Protocol:** a POSITIVE signal is self-validating (viable, cheaply); a NULL → bump to sims
> **344** (k4×344=1376=½ budget) to disambiguate BEFORE concluding "doesn't work." … (Advisor
> wanted 344; Joshua chose 200 with this escalation protocol.)

Two things in that clause did not survive into the re-derivation:

1. **The mechanism is "gen search too weak to beat the net's own distilled priors"** — a ratio
   against *whatever budget produced the net's priors*, not a fixed 2752.
2. **The escalation protocol** (`NULL → bump to 344 → only then conclude`) **was never executed.**
   The null arrived 2026-07-19 and the arm closed; no sims-344 run exists.

Both were compressed into an absolute paraphrase in
[docs/LEVER_INDEX.md:210](../LEVER_INDEX.md) ("sims200 < the advisor's ½-budget floor") and in
roadmap [G8](../PROGRAM_ROADMAP_2026-07-07.md#L115).

### Why turn 1 lands in the same place — three independent confirmations

`scripts/distill_flywheel/RODV3_TURN1_PREREG.md:17-19` states the premise:

> The recorded ¼-budget confound (HANDOFF ½-budget floor; recipe lever 6) is the thing under test;
> CL-067's equal-sims +35.7 ± 12.3 supplies the missing premise **(operator > teacher at 2752)**.

**(a) The premise contradicts CL-067's own counterevidence field.** CL-067 measured the distilled
net's priors against the **deploy champion** at equal sims — never against the teacher.
`governance/CLAIM_REGISTRY.csv` CL-067, counterevidence:

> ASSUMPTION-FREE RESTATEMENT THAT DOES NOT USE THE EXCHANGE RATE AT ALL: per-move cost 11.7 s
> (distilled net at 2752 sims) vs 11.2 s (the 4x TEACHER k8x1376 at 11008 sims …) — at the SAME
> per-move cost the raw teacher scores +49.85 and the distillation +35.7, **so THE TEACHER IS
> +14.1 ELO BETTER THAN ITS OWN DISTILLATION.**

So "operator > teacher at 2752" is exactly backwards on the record: the operator is ~14 elo
*below* the teacher, and CL-067 is being cited one comparison wider than it was measured.

**(b) The gen budget is ¼ of the budget that produced the parent net's priors** — the HANDOFF's
own criterion, at 4× scale. Verified from the corpus artifact, not from prose:
`/mnt/c/carc-shared/distill_strong_20260723/iter_00/manifest.json` →
`config.teacher = {k_dets: 8, sims_per_det: 1376, total_budget_per_move: 11008}`. The prereg's own
mix table keeps those 2400 teacher games as 8/9ths of the training buffer and adds 300 new games
at **2752**.

| run | gen budget | budget that made the net's priors | ratio |
|---|---|---|---|
| refuted flywheel (CL-058) | 800 (k4×200) | 2752 (deploy champion) | **0.29** |
| `rodv3` turn 1 (funded) | 2752 (k4×688) | 11008 (k8×1376 teacher) | **0.25** |

The ratio the caveat was about is *unchanged* — marginally worse.

**(c) Under the absolute reading it also fails, because production moved the same day.**
`governance/PRODUCTION.yaml` `champion.fair_deploy` was promoted to `k_dets: 8` /
`sims_per_det: 1376` = **11008** on 2026-07-29 (CL-071, `budget_folded_in: "2026-07-29"`). The
prereg was written at ~23:50 that same night and still calls 2752 "full budget"
(`scripts/distill_flywheel/FULLBUDGET_GEN_SMOKE_RUNBOOK.md:17` likewise names
"`NET_SIMS=200` = 800 total, the ¼-budget confound"). Against the champion of record, **2752 is
now itself ¼ budget**, and the advisor's ½-budget floor re-derives to **5504**.

### Why this matters rather than being pedantry

The prereg pre-commits the DEAD branch (`RODV3_TURN1_PREREG.md:146-148`):

> **DEAD:** both statistics ≤ 0 or sign-split at |z|<1 → **lever 6 resolved NEGATIVE**; the
> ¼-budget confound was not the limiter; lever 1 (value sever) becomes the last suspect; STOP.

A near-zero derivative is the *expected* reading: only 300 of 2700 buffer games change, and the
new games are the weakest data in the buffer. If that reading is recorded as "lever 6 resolved
NEGATIVE", the audit's seed failure mode completes a second lap — this time with the pre-commitment
in writing.

**A fourth, smaller instance of the same drift sits in the gate's own authority.** CL-058's
still-open re-open trigger reads:

> (b) ANY variant (stage-3 value-unlock, lever ablation, longer window) holding >=2sigma at
> **PRODUCTION depth k4x688** -> promotable lever, the program's first learned-component win at
> depth (STILL OPEN).

`k4×688` was production depth when that was written. Since 2026-07-29 it is not. The rodv3 gate
inherits the phrase "AT DEPTH" from it, so "at depth" now silently means ¼ of production depth.
That is fine as a *derivative* test (candidate vs its own parent) — but the label should stop
implying production depth, or the next reader will over-read a pass.

### What it funds

1. **Free, before the gate is funded:** amend the DEAD branch so a null at gen 2752 is recorded as
   *still ambiguous under the confound's own criterion*, not as "lever 6 resolved NEGATIVE".
2. **Free:** fix the premise sentence in the prereg **and** roadmap G8 to what CL-067 measured
   (student > deploy champion at equal sims; teacher > student by +14.1 at equal cost).
3. **The decisive version of the experiment:** gen at **≥5504** (k4×1376 or k8×688) — the
   ½-budget floor re-derived against the current champion — or at 11008 for a true parity turn.
   Cost: the prereg's own ETA is ~10–15 h multi-box for 300 games at 2752, so ~20–30 h at 5504 and
   ~40–60 h at 11008. If the compute is not there, holding total gen compute fixed and halving the
   game count is cheaper but changes a second variable — say so in the prereg rather than absorb it.
4. **Cheap and never done:** the HANDOFF's own escalation step (a ½-budget re-run *of the refuted
   configuration*) is still the shortest path to a clean read on lever 6 in the old lineage.

---

## F2 — the RoD-v2 anchor is known to mis-order a +50 elo contrast by ~70 elo; that fact lives only in a CSV counterevidence field

**Rank: high — it is free to fix and it bears on every number ever graded through that anchor.**

`governance/CLAIM_REGISTRY.csv` CL-070, counterevidence:

> WHAT ACTUALLY IMPLICATES THE RULER IS CL-060, NOT THIS PROBE: the same pair measured two ways
> disagrees by ~70 elo. Direct head-to-head `cl060_h2h_k8x1376_vs_deploy_k4x688` (n=400 paired,
> 221W-164L-15D) = +49.85 +/-17.55; via RoD-v2 as ruler on ONE deck-matched band the same pair
> reads 11008 +105.6 vs 2752 +127.0 = **-21.4, WRONG SIGN and n.s.**

and its falsifier field records the decision that follows:

> DECISION THIS ALREADY DRIVES: **RoD-v2 cannot price budget above 2752** (the CL-060 contrast
> above), so **stop buying budget rungs graded against it.**

CL-071 repeats it as counterevidence (3) for the promoted champion. **But the caveat is not
attached to any of the places the anchor is still used:**

- `docs/LEVER_INDEX.md` — grep for `cannot price` returns nothing; the anchor appears only inside
  other levers' rows.
- The auto-memory note `reference_rodv2_iter2_eval_anchor.md` still reads, with no caveat: *"When
  an eval needs an h3200-class opponent/anchor, use RoDv2 iter_02 instead … Applies to the
  post-Gate-B probe pre-gates and any ladder/vs-anchor eval."*
- `scripts/distill_flywheel/RODV3_TURN1_PREREG.md:150` still uses it: *"Secondary (context, not
  gates): vs rod_v2 iter_02 anchor at k4×688"* — i.e. exactly at the 2752 boundary where the
  mis-pricing begins.
- CL-058 — the flywheel growth refutation that this whole audit descends from — lists as an
  assumption: *"rodv2_iter02 is a valid fixed out-of-lineage-ish anchor (~h3200 tier …)"*.

Nothing here says the flywheel null is wrong: its evals sat at k2×200, far below 2752, where the
anchor is not known to mis-price. The point is narrower and cheap — **the project's only
out-of-lineage anchor has a measured validity ceiling that a reader must currently discover by
reading a claim's counterevidence column.**

**What it funds:** a ruler-validity row (LEVER_INDEX §8 is the natural home) + the same sentence
appended to the memory note and to the rodv3 prereg's secondary read; concretely, the rodv3
secondary read must not be allowed to rescue or condemn the turn. Cost: doc/memory edit, zero
compute. Value: it is the second time a ~70-elo ruler artifact has cost this program a wrong
reading (the first was CL-060's own underpowered closure).

---

## F3 — CL-071's own counterevidence asks for a reconciliation nobody owns

`governance/CLAIM_REGISTRY.csv` CL-071, counterevidence (4):

> The 14.3-vs-17.4% clock band is an unreconciled 3.5x (roadmap 26%/91% anchors) vs 4.262x
> (measured) sequential-cost pair; **conclusion-insensitive but somebody should reconcile it.**

"Somebody should" with no owner is how caveats decay. It matters more than the wording suggests:
tournament legality is the *binding* constraint on the promoted champion (91% of the clock
single-stream), and the promoted config's clock share is currently quoted two ways in the same
governance file. **What it funds:** ~15 minutes of arithmetic against
`measurement/kparallel_bench_20260729/rows.csv`, then one number in `PRODUCTION.yaml`. Zero compute.

---

## F4 — `docs/LEVER_INDEX.md` contradicts itself about the oracle-pilot discriminator (would fund a re-run of a completed run)

The §8 row (line 222) records the discriminator as **run**:

> ⚠️ same-family self-preference — **DISCRIMINATOR RUN 2026-07-28 (late): THE SIGN SURVIVES OUT OF
> FAMILY** ⇒ threat downgraded UNRESOLVED → TESTED-AND-NOT-SUPPORTED …

The standing-list entry for the same probe (line 262) records it as **not run**:

> ⚠️ Sole surviving threat = same-family self-preference; **the cheapest discriminator (Tier-1
> greedy continuation, sign check only) is named and NOT run.**

The dedup index is the one file the project relies on to prevent re-running dead work, so an
internal contradiction inside it is a direct hit on that function. **What it funds:** one-line
edit; prevents a future agent from re-running the Tier-1 greedy pass (~254 s at W16 — trivial in
compute, but it also mis-states the threat's status as "sole surviving" when the record downgraded
it). Zero compute.

---

## F5 — a discharged debt still recorded as open (CL-069)

`governance/CLAIM_REGISTRY.csv` CL-069 counterevidence still reads:

> *** THE HEADLINE IS NOT A CLEAN 'CONSERVATIVE LOWER BOUND' — corrected 2026-07-27; **the
> harness's own printed banner still overstates this and is queued for a fix.** ***

The fix has landed: `scripts/classical_search/eval_fair_puct.py` now emits
`"is_bound": False` with a corrected `interpretation` block (≈lines 2996-3005), and the module
docstring carries the four-axis correction (lines 108-120). Only the registry row still says
"queued". **What it funds:** a registry status edit; prevents a future reader re-verifying a fixed
bug. Zero compute. (Listed for completeness — it is the mirror image of the failure mode: a
resolved caveat left reading as unresolved wastes inspection instead of decisions.)

---

## F6 — structural blocker #2 rests on a claim the registry marks *Provisional* and *contradicted*

**Rank: high on decision value, zero on compute — this is the premise gating the program's goal.**

`CLAUDE.md` states the two walls that gate superhuman as settled context:

> Two structural blockers gate it: (1) **measurement** … and (2) the **hand-crafted leaf eval caps
> learned strength near strong-human by construction** (the leaf of record is in
> `governance/PRODUCTION.yaml`; it was v2.7 when this was written, and the argument has survived
> every leaf generation since) — superhuman requires the *learned* components to exceed the
> heuristic, which they don't yet.

`PROJECT_CHARTER.md:34` names the claim that backs it:

> **Leaf ceiling** — the v2.7 leaf caps learned strength near strong-human *by construction*
> (CL-010); the learned components do not yet exceed it.

and `PROJECT_CHARTER.md:151` asserts its status: *"**Leaf ceiling holds** — no learned component
beats heur@800 out-of-lineage (CL-010 stays *Supported*; CL-006)."*

**The registry says otherwise, and has since 2026-06-08.** CL-010 is `Provisional`,
`last_updated 2026-06-08`, and both of its own evidence fields undercut it:

> **best_evidence:** DOWNGRADED 2026-06-08: the heur@800 -29 / heur@3200 -38 evidence was measured
> vs a v1-LEAF opponent (`ladder_asymmetric.py` never passed `--heur-leaf` -> silent v1 default,
> the R1-redux). It does NOT measure the v2.7 ceiling.
>
> **counterevidence:** MATCHED v2.7 odometer (flywheel iter0, clean seed 1.5e9, n=200) = net BEATS
> heur@800-v2.7 by +52.5 -> the net DOES exceed the v2.7 leaf at 4x search depth. **So the
> "v2.7-leaf ceiling" as evidenced is contradicted** …
>
> **falsifier:** a MATCHED-v2.7 heur@3200 measurement … **(needs Joshua's call on which leaf is
> the reference)**

**The named measurement DID run — eleven days later — and was never adjudicated into the claim.**
`experiments/results.csv:167`, `l22_iter8_vs_heur3200_b310_n400` (2026-06-19, n=400, candidate
`iter8` + residual @ sims 200, opponent `HeuristicMCTS` `old_var=v2_7` at `old_sims=3200`):
**180W / 213L / 7D, elo −28.7 ± 17.4, margin −0.85 pts/deck.** Read against CL-010's own
pre-stated rule (*"if the net also beats heur@3200-v2.7 the v2.7 ceiling is broken; if it loses the
ceiling holds at deeper search"*) the ceiling **held**. And the matched-v2.7 depth ladder, pulled
from results.csv this pass, is the real signal nobody wrote down:

| opponent depth (matched v2.7 leaf) | candidate elo | σ |
|---|---|---|
| heur@800 | **+40.1** | 17.5 |
| heur@1600 | **+34.9** | 17.5 |
| heur@3200 | **−28.7** | 17.4 |

The learned policy's edge over the *same* leaf decays as the heuristic is given depth and crosses
zero by h3200 — a ~69-elo swing between the last two rungs. That is a *stronger* statement of
blocker #2 than the registry carries, and it is exactly the "fit the trend across a ladder" method
the project's own memory note prescribes. The counterevidence that made the row `Provisional`
(*"net BEATS heur@800-v2.7 by +52.5"*) is the **shallowest rung of that ladder**.

So: the decisive measurement ran, its result supports the blocker, the registry never recorded it,
the row still reads `Provisional / last_updated 2026-06-08`, and the blocker on adjudication is a
one-line human decision (*"needs Joshua's call on which leaf is the reference"*) that has sat 52
days. Meanwhile two top-level docs cite it as established — one of them (`PROJECT_CHARTER.md`) has not
been touched since 2026-06-08 (`git log` → `7c5ca3d`), is still linked from
`governance/README.md` as the DECISIONS layer of the governance spine, and additionally declares
*"Track B … ← PRIMARY (2026-06-08)"* with *"superhuman vs humans is DEFERRED/aspirational"* —
the opposite of `CLAUDE.md`'s standing goal — while quoting `iter_11 +89.7` / residual `+83.2` as
"where the current validated gains live", two evidence epochs and one champion ago.

**Nothing here argues the blocker is false — the opposite.** The later record supports the
*stronger* version of it (CL-062 search converges to the leaf's own ordering; CL-065 closes the
learned leaf representation-independently; CL-066's tabula-rasa flatline), and so does the h3200
rung above. The finding is that **the program's most load-bearing premise is simultaneously
over-cited and under-recorded**: asserted as fact in two top-level docs, carried as `Provisional`
with stale contradicting evidence in the registry, and supported by a decisive cell that no
document links. Its secondary defect is falsifiability — the falsifier on file presumes a neural
champion that no longer exists, so as written nothing could now falsify it.

**What it funds** (all zero-compute, all a re-read rather than a re-measurement):
1. **Adjudicate CL-010 on evidence that already exists** — cite `l22_iter8_vs_heur3200_b310_n400`
   plus the three-rung ladder, and flip the status. The project's own trend method turns three
   individually-thin cells into a decisive read; right now the strongest available support for
   blocker #2 is sitting unlinked in results.csv.
2. Then re-specify the falsifier for the classical era: the ladder version is net-vs-heur, and the
   net is no longer the champion. In the current regime the instruments that could bear on an
   *absolute* ceiling are the human anchor (E4, parked) and exact-solver-graded regret.
3. Status-stamp `PROJECT_CHARTER.md` (house style: PATH_B.md's banner) or mark it superseded. A
   fresh thread that follows `governance/README.md` into it today adopts the wrong primary track
   and a stale champion.

---

## F7 — the 2026-05-20 false-negative audit named five "reservoirs"; three were never swept, and the index has no entry for any of them

**Rank: high value per unit cost — the deliverable is a paper triage, zero compute.**

`DECISIONS.md:855` records the measured base rate that makes this uncomfortable:

> **Headline:** Of the 4 hypothesized false-negative-suspect calls, the math from the prior entry
> (P(at least one recovered) ≈ 40-50%) actually delivered **2 recoveries**. The biggest is
> iter_B1: the project's claimed "plain v2.7 plateau at iter_01" was wrong …

i.e. when this project re-tested its own underpowered kills, **half of them were wrong, and one
recovery moved the global-best checkpoint.** The same entry then lists five reservoirs to sweep
(`DECISIONS.md:864-873`). Two were actioned (chain Option-B forward; the coarse-sweep item, later,
via C5-S5's c_puct wings and F6-S1's cap=∞). Three were not, verbatim:

> - **Smoke-test rejections (n=20-50).** Even more underpowered than n=100. Any past variant
>   rejection where the smoke landed within ±50 elo of zero was effectively "unknown" — re-run
>   candidates that had borderline smokes.
> - **Pre-bug-fix benchmarks.** The v2.5 farm/city dedup fix (2026-05-15) shifted optima. Any
>   variant rejected *before* that fix was tested against inflated bonus magnitudes — verdicts may
>   not hold.
> - **Other plane mismatches.** … cap value at train vs play, leaf-eval variant at train vs play,
>   orchestrator on/off — **not systematically audited.**

**Dedup:** `docs/LEVER_INDEX.md` has **zero hits** for `reservoir`, `false.negative`, `pre-bug`,
`retroactive`, `inflated`; so do the roadmap and STATUS. The file whose stated purpose is that "a
grep can't miss a dead lever" has no entry for the audit that measured this project's own kill
error rate.

**Honest deflation, so the triage isn't oversold:** most pre-2026-05-15 rejections are *neural-era*
recipe variants, and that whole track is now closed by later, independent, well-powered kills
(CL-065 representation-independent leaf closure; CL-066 tabula-rasa flatline). Re-opening those buys
nothing. The part that still bears on the **live classical champion** is the small subset of
*leaf and search* knobs whose only measurement predates the dedup fix — and several of those
(cap, closure_p, c_puct, value_norm) were re-swept inside C5/C7/F6 afterwards.

**What it funds:** one paper pass over `experiments/results.csv` + `DECISIONS.md` rows dated before
2026-05-15, tagging each kill as (i) superseded anyway, (ii) re-tested since, or (iii) **still-live
kill whose only evidence is a pre-fix benchmark or a ±50-elo smoke**, restricted to knobs the
classical champion actually reads. Bucket (iii) is a ranked re-open queue produced for zero box
time; by the entry's own measured base rate it is not expected to be empty. Cost: one subagent
pass. Any bucket-(iii) re-measurement then prices individually at ~one n=400 deck-paired cell.

---

## F8 — the v1 leaf measured *nominally stronger* than v2.7 on the clean ruler; the fork was declined for re-tune cost and never opened

**Rank: medium — but the cheapest resolution is arithmetic, not compute, so it is nearly free to close.**

`DECISIONS.md:81` (2026-06-08 pm-3), verbatim:

> **(2) Leaf comparison (CL-010) was already measured on the clean ruler (2026-06-07, n=400
> paired):** pure leaf gap heur-v2.7-vs-v1 = **−24.4 ± 16.5 (1.5σ = INCONCLUSIVE)** — v1 nominally
> the stronger standalone leaf but unresolved at n=400 … v2.7 is the fully-tuned ecosystem (CAP=12,
> DROP_THREE_OPEN, residual lineage, +86.9 Stage-B); switching to v1 forces a full re-tune →
> **Joshua: KEEP v2.7** (v1-leaf = a separate future fork, not a pre-flight).

`DECISIONS.md:87` states the same number as one of the clean ruler's "three narrative shifts":
*"the **leaf-gap 'universal +45% discount' is WRONG** — the pure v2.7 leaf is *weaker* than v1 in
standalone search"*.

The decision was sound (a re-tune is expensive, and the *combined* net beat both leaves). But the
fork was never opened, and every leaf generation since — v2.8 → v2.9 → v2.9.1 `Bmild_cap8` →
`curve125` — is a descendant of the branch the ruler leaned *against*, as is every leaf-axis kill
measured inside it (C5, C7/CL-055, F6/CL-063's *"the leaf-accuracy channel is confirmed closed"*).
Those closures are branch-scoped statements about adding terms to the v2.7 line, not axis-scoped
statements about the leaf.

**Dedup:** not in `docs/LEVER_INDEX.md` — the §6 row `v1 → v2 → v2.5 leaf lineage` records the
*forward* story ("v2 FAILED the bench; v2.5 then passed") and not the later clean-ruler reading
that put v1 nominally ahead of fully-tuned v2.7. No hits in STATUS or the roadmap.

**What it funds — cheapest first:**
1. **Arithmetic, free:** chain the *measured within-branch* gains since v2.7 (v2.9.1 `Bmild_cap8`
   vs real prod v2.8 = **+64.3 elo / z 3.77 / n=399**, plus CL-051's curve125 adoption) and ask
   whether they exceed 24.4 elo with margin. They very likely do — in which case the honest action
   is one indexed line closing the fork on arithmetic, and nothing else.
2. Only if (1) is ambiguous: one n=400 deck-paired standalone-leaf cell v1 vs `curve125` on the
   per-side leaf A/B harness (`--cand-leaf-json`, per-side `leaf_hash`). ⚠️ cost caveat: v1 is the
   **object** leaf (`virtual_score.py`, the path `RuleBasedPlayer` uses); it has no `flat_leaf` /
   Cython form, so the cell runs on the slow path and is more expensive than a normal rung.

---

## F9 — five live surfaces still tell a fresh thread that search budget is a closed lever, one day after it was promoted

**Rank: joint-highest with F1. Free. This is the audit's largest *live* citation defect.**

`CL-071` (2026-07-29, `PROMOTED`) diagnoses the defect in the closure it replaced:

> CL-068 closed the budget lever in BOTH directions FOR CLOCKED PLAY -- **that closure rested on an
> unstated SINGLE-STREAM assumption** and is what G6 reopens

The k-parallel split (`parallel_workers=8`, measured 6.370×, action-identical 30/30) makes the
strongest measured configuration cost ~14–17% of the 900 s clock instead of 91%, so it was promoted.
**But the closed version is still asserted, verbatim, in five places** — every one of them checked
against the file during this pass:

1. `STATUS.md:103` — *"Within everything comfortably clock-legal (≤~50% of clock) **budget buys
   nothing measurable** … not merely that 4× is unspendable, but that **everything spendable is
   already spent.** Search budget is a closed lever for clocked play **in both directions**"*
2. `STATUS.md:163` — *"Compute is an **unclocked-play knob only**; any future citation of it as
   progress toward the superhuman goal must carry this constraint. The **deploy champion is the only
   comfortably legal config we have**"* — in the same file whose top block (line 13) announces the
   promotion. **STATUS.md self-contradicts.**
3. `docs/LEVER_INDEX.md:165` — *"**⛔ buying elo with raw compute AT TOURNAMENT TIME CONTROL** …
   Compute is an **unclocked-play knob only**."*
4. `docs/PROGRAM_ROADMAP_2026-07-07.md:107` (G2) — *"the search-budget lever is **CLOSED IN BOTH
   DIRECTIONS** for clocked play"* — two lines above G6, which promotes exactly this; the two lines
   do not cross-reference.
5. `governance/CLAIM_REGISTRY.csv` CL-068 — still `Supported`, `last_updated 2026-07-29` (the day of
   the promotion) — *"The remaining clock levers are pondering (roadmap G1) and per-move cost (G3),
   **NOT sims**."* Verified by string count: the row contains `CL-071` once (only to say a different
   finding "DOES NOT TOUCH CL-060/CL-071") and contains **`k-parallel` 0 times, `single-stream` 0
   times, `parallel_workers` 0 times.**

Related: `docs/LEVER_INDEX.md:141` and `:219` both carry *"do not fund a throughput program"* /
*"don't fund it"*. A search-core change worth +49.85 deployable elo for roughly a day of engineering
is the counterexample; the recommendation needs an explicit k-parallel carve-out or it will next be
read as advice against the thing that just worked.

**What it funds:** nothing to measure — stamp the single-stream premise on all five surfaces and
cross-link G2 → G6. Zero compute. Value: this is the exact shape of the seed failure (a conclusion
outliving its premise), except it is one day old and sitting in the two files a fresh thread reads
first.

---

## F10 — CL-059's pre-registered re-open condition has FIRED and the claim was never flipped

**Rank: high. Free. This is the uncaught member of the class Joshua named** (the `r ≤ 1.5` eqtime
reopen was the caught one).

CL-059 (`Closed`, `last_updated 2026-07-21`) wrote its own reopen rule:

> Re-open ONLY if **(a) a DIFFERENT policy-capture mechanism (not root-prior reweighting) shows
> fair-depth headroom**, or (b) the strategic scope changes …

**Condition (a) fired three days later.** CL-067 captured headroom *in the policy-prior channel,
under fair play, at the identical k4×688 budget*: a distilled net supplying priors at every expanded
node — a different policy-capture mechanism from root-only oracle reweighting — pooled
**+35.7 ± 12.3 elo, winrate z +2.90, margin paired z +2.12** over n=800 deck-paired games on two
disjoint fresh bands. CL-067 is `Supported/high`. CL-059 is still `Closed`, and the channel-level
kill is still asserted in both index surfaces:

- `docs/LEVER_INDEX.md:93` — *"FAIR confirm is a dead tie ⇒ **the policy-prior channel has no
  capturable fair headroom**"*
- `docs/PROGRAM_ROADMAP_2026-07-07.md:78` — *"the policy-prior channel has **no capturable headroom
  at fair production depth**."*

The defensible claim is narrower than either sentence: *oracle **root-prior reweighting** buys
nothing at fair depth (one cell, one band, budget 2752, cost 4.63×)*. The channel itself has ~+36
elo of measured strength headroom whose live constraint is **per-move cost**, not strength — and per
the 2026-07-29 ANE cell (`r = 0.3512`) the forward tax is genuinely deletable, leaving +19.13 ± 17.40
= a wash rather than a refutation.

**Second, stale supporting leg:** CL-059 rests part of its case on *"Coherent with F3 fusion cost …
+ F5 ladder bend (raw sims dead past ~2x) + Gate-B depth-decay"*. The F5 leg was refuted the next day
(CL-060 `Reopened` 2026-07-22: 4× = +49.85, z 3.48) and CL-059 was never amended. Note this does
**not** flip the null's direction — CL-062's depth-decay means a deeper deploy makes a *root-prior*
null more null, not less. It is the coherence argument that decayed, not the result.

**What it funds:** a status/citation repair at zero cost. Nothing new to measure: the strength
question is already answered positively by CL-067, whose own open problem is cost. Explicitly do
**not** fund new prior-channel strength cells on this.

---

## F11 — four aggregating statements are wrong or over-strong about their own evidence

**Rank: medium-high, free, and both are in the files used for dedup.**

**(a) "the last formally-open strength cell."** `governance/CLAIM_REGISTRY.csv` CL-064 (`Closed`,
2026-07-22) claim field: *"This was the LAST formally-open strength cell."*, and its falsifier field:
*"combined with CL-039/CL-042 (value), CL-059 (prior), CL-060 (throughput …), CL-061 … and CL-063 …,
the learned-component program **has no open cell**."* CL-067 (2026-07-24 → 29) is a learned
component that exceeded the champion at equal sims, and says so about itself: *"this claim does not
depend on and is not contradicted by the learned-VALUE kills (CL-039/042/064/065/066)."* The
sentence was never amended. It matters because "no open cell" is the sentence that would justify
declining any future learned-component proposal.

**(b) "always negative."** `docs/LEVER_INDEX.md:26` (the LTR row): *"Re-fired offline 3× since,
**always negative**"*, citing CL-021, CL-033, CL-064. Two of the offline re-fires were **positive**,
verified in the registry this pass: **CL-037** — the sighted-rep `V4_listwise` moved best-alpha off 0
with regret 0.0263 → 0.0209 (**+20.5%**, clearing its pre-registered ≥15% bar); **CL-034** —
`listwise_mlp` over 50 action/delta scalars **beat the v2.9 leaf outright** on the same 10,067
sibling sets (regret 0.0289 → 0.0171, top-1 0.464 → 0.535). **CL-034 is not even in the row's
reference column**, and the partial correction at `:253` omits it too.

What is genuinely dead is narrower and worth stating precisely: **no LTR result has ever converted
through search** (CL-034 Stage 5 tried four integrations at sims=200; all lost to plain
`search_leaf`), and LTR-as-value-blend-leaf in a clairvoyant neural MCTS at sims=200 on the v2.7 leaf
is a retired regime. A secondary scope gap sits under it: the online α ladder was {0.5, 1, 3} with
the best marginal at the **endpoint α=3.0**, never extended — which the project's own bracketing rule
("a peak at a ladder ENDPOINT is not bracketed") forbids relying on, and `DECISIONS.md` 2026-06-05
pm-5 concedes *"Only-complete config a05t01(α=.5) = marginal −67 …; others partial+noisy."*

**(c) "all arms inert under BOTH regimes."** `docs/LEVER_INDEX.md:59` (Probe B §4A, clairvoyant vs
fair value targets): *"TRIED — **all arms inert under BOTH regimes** (the fourth nail)."* The
registry is more honest — CL-039 counterevidence: *"§4A is **DEPTH-SATURATED**: clair@800 is inert so
it cannot isolate the clairvoyance variable -- the clean H-4A-inert test is **AMBIGUOUS**, and an
h6400-depth §4A was NOT run. The close therefore rests on the cumulative value-inertness ledger +
the Gate-B offline→online mechanism, NOT on §4A alone."* So §4A did not test both regimes; it
saturated. The close is fine — it rests on other legs, as the registry says — but the index sentence
converts an ambiguous leg into a "nail", in the one file you grep before proposing a lever. (Partial
credit: `STATUS.md` does carry the caveat verbatim.)

**(d) registry hygiene, same family.** CL-007 (*"MSE cannot rank sibling actions"*) is still
`Provisional / 2026-06-07` although CL-038 (`CONCLUDED`, 2026-06-30) measured its falsifier in
passing: the value head *"ranks the game at Kendall-tau ~0.43 at EVERY search-tree depth, +43%
offline sibling-regret"*. The correct modern statement — "MSE *can* rank, it just cannot *drive* the
leaf" — is what CL-038 actually established, and Gate-C0's re-open bar descends from CL-007's older
framing.

**What it funds:** rewrite the sentences (free). The one cheap experiment they imply is already
indexed as standing-list item 6 (LTR over the Gate-C 84-feature read-out with exact-solver labels,
reuses existing labels, a few CPU-hours, $0) — this audit does **not** raise its priority; it only
corrects the record that currently over-states why it is unpromising.

---

## F12 — the band-level over-dispersion correction lives only in a claim row and an ephemeral STATUS block

`governance/CLAIM_REGISTRY.csv` CL-068 records an unresolved measurement anomaly *and* an interim
rule:

> WHY is this family over-dispersed ~1.8-2.2x across bands when the within-band harness is clean? …
> **UNTIL THAT IS ANSWERED: inflate sigma ~1.5-2x on any cross-band z in this family and prefer
> within-band deck-matched contrasts.**

The evidence is strong (the same `k4×344` config reads +0.9 / −53.4 / +20.9 on bands 60e9 / 76e9 /
88e9 — 2.20× on elo — with an identity control exonerating the harness; `STATUS.md:21`). But the
*rule* exists in exactly two places: a CSV cell, and a STATUS block that the file's own header
instructs future editors to overwrite in place. Meanwhile `CLAUDE.md`'s results-discipline block —
the canonical power guidance every new thread reads — still gives only the nominal figures
(*"n=400 → 1σ ≈ ±17 elo"*, *"n=400 paired ≈ ±12 elo"*) with no cross-band inflation factor, and
`governance/EVIDENCE_EPOCHS.md` has no hits for it.

**What it funds:** one sentence in the canonical power guidance (CLAUDE.md results-discipline or
EVIDENCE_EPOCHS), so cross-band cells stop being sized with a σ known to be 1.8–2.2× optimistic.
Zero compute, and it prevents a whole class of future false verdicts — the same class that produced
the −53.4 / +0.9 contradiction that cost a fresh-band confirm to untangle.

---

## F13 — S-R3-1: the residual target is ±2 into a ±1 head. Deferred as "Lever for attempt #2"; attempt #2 ran without it, and Arm B is pre-committed to reuse the same shape

**Rank: high among the free ones. It is a structural cap on the mechanism rodv3's Arm B would test.**

`REVIEW_LOG.md:549`, verbatim:

> **S-R3-1** … **Residual target Δ = root.Q − v2.7 leaf ∈ [−2,+2] but the value head is
> tanh-bounded to [−1,+1].** For the high-signal positions (`|Δ|>1`, where search and v2.7 strongly
> disagree) the head saturates → vanishing gradient → the **most informative residuals are
> systematically under-learned** … Self-consistent (does NOT bias any strength CLAIM) but a concrete
> structural CAP on what the residual can learn → a candidate mechanism for CL-004 being *modest*
> and a limit on CL-011 compounding … | **Lever for attempt #2** … clip the residual target to
> [−1,1] … OR a linear (unbounded) output … Surface to Joshua.

**Verified un-discharged at HEAD, this pass:**
`src/carcassonne_ai/network.py:148` — `return torch.tanh(self.value_fc2(v)).squeeze(-1)`,
unconditional. `src/carcassonne_ai/selfplay.py:471-473` — the interior residual row is
`float(nb_q) - _v27_leaf_value(nb.state, nb_player)`, no clip, no rescale (the trajectory rows at
`:440-446` are the same target). Both terms live in [−1,1], so the clipped `|Δ|>1` tail **is exactly
the "search strongly disagrees with the heuristic" set** — the positions the residual exists to
capture.

Attempt #2 then ran and plateaued (`docs/LEVER_INDEX.md:29` — *"Attempt-2 gave a bounded gain then
plateaued"*), and that plateau is now one of the pillars of the value-inertness ledger. The lever
named to be applied first was never applied.

**Why it is live rather than historical:** `RODV3_TURN1_PREREG.md:11,24-26` pre-commits **Arm B
(stage-3 value-unlock)** as the next arm after turn 1. If Arm B reuses the same target/head pairing,
it re-tests a mechanism through a representational cap that this review flagged before attempt #2.

**Dedup:** `docs/LEVER_INDEX.md` has rows for the *enclosing* levers (`:28` residual, `:29` residual
flywheel) and **neither mentions the range mismatch**; greps for `tanh-bounded`, `residual target`,
`S-R3-1` return nothing. This is precisely the conclusions-not-interventions gap the index exists to
close.

**What it funds — minutes, no new games:** histogram `|Δ|` over the residual-target `.npz` already
on the share. Either the `|Δ|>1` tail is negligible (the caveat retires *with evidence* and the
value closure gets stronger) or Arm B must clip/linearise before it spends a box-night. Do this
before Arm B is funded, not after.

---

## F14 — the overnight watchdog's orphan-claim guard is inert on the cells it is armed on tonight

**Rank: operational, live, one-line fix.**

`scripts/measurement_infra/run_watchdog.sh:58-67`:

> ```
> clear_orphan_claims() {
>   # a claim whose record exists is history; a claim with no record blocks resume forever
>   for c in "$CELL_DIR"/*.claim; do
>     j="${c%.claim}.json"
>     if [ ! -f "$j" ]; then rm -f "$c" && say "cleared orphan claim: $c"; fi
> ```

The record extension is hardcoded `.json` — correct for the eval harness it was built against on
2026-07-28. `RODV3_TURN1_PREREG.md:127` arms it on a **gen** cell:
`run_watchdog.sh '<out>/seed_*.npz' 300 …`. No `.json` ever exists beside `seed_*.npz`, so on a
gen cell **every** claim reads record-less and the guard deletes **all** of them, including the
claims of the 200-odd games already banked — the opposite of its documented contract. It fires only
on the stall path (`:74-83`: no workers alive AND short of N), so the blast radius is a relaunch
that may re-play completed seeds rather than a mid-run wipe; that is the same duplicated-work shape
already on record for the laptop joiner (`docs/LEVER_INDEX.md:217`, ~46 of 300 games duplicated).

**What it funds:** one line (`ext="${GLOB##*.}"`). It matters tonight because the prereg makes this
watchdog the *primary* unattended-run protection (`:125-128`), explicitly because "the session
heartbeat dies with the session".

**Adjacent, same family, verified:** `REVIEW_LOG.md:58` (D9) — *"a failed game leaves its `.claim`
file live for `--claim-stale-secs` … blocking that seed on both boxes"* — and `:488-490` (D22, the
missing `.failed` sidecar, *"it would re-attempt + re-fail forever, stalling at <GAMES. Not yet
hit"*). `REVIEW_LOG.md:210` says D9 should be fixed *"before the next multi-iteration run"*;
`docs/BACKLOG_REAUDIT_2026-07-13.md:50` re-parks it as a "**Flywheel-conditional infra bundle**".
The flywheel condition is met tonight. The cost of not fixing it has already been paid three times
in bespoke shell (`clean_stranded` re-implemented in `odo_oneshot.sh`,
`cluster_resume_after_fan.sh`, `auto_chain_h2h_flywheel.sh`) plus a whole new tool plus a manual
incantation carried as human ops discipline in the prereg (`:129-131`). ~15 LoC and a test.

---

## F15 — the adopted sealed-band governance never got its registry; the prescribed check is documented to fail silently open

`docs/reviews/REVIEW_ADOPTION_20260719.md:28`, verbatim:

> … A band that influenced a decision retires from confirmatory use. (Formalizes existing practice;
> **governance/ to carry the tier registry**.)

`governance/` has no band or tier file. The de-facto registry is
`/mnt/c/carc-shared/BAND_CLAIMS.txt` — plaintext on the share, **not git-tracked**, yet cited as
authority in the prereg (`:55`) and in the recent readouts. The programmatic alternative is recorded
as broken in two places: `DECISIONS.md` — *"the band-enumeration instruction … is BROKEN and
silently fails open"* — and `STATUS.md:33` — *"results.csv has no band column and the prescribed
check fails silently open."* CL-068's falsifier field says the same thing to the next reader:
*"results.csv has NO seed_start column and the old instruction to enumerate it fails SILENTLY OPEN."*

Band provenance is now maximally load-bearing: the 2026-07-29 promotion cites specific bands in
`governance/PRODUCTION.yaml`, and the rule whose violation produced the it16 winner's-curse crest
("a band that influenced a decision retires from confirmatory use") is currently enforceable only by
human recall — while F12 shows band identity is worth 1.8–2.2× in σ.

**What it funds:** a `band` column emitted into results.csv from the manifest each run already
writes, a tracked `governance/BAND_REGISTRY.csv`, and a `doc_lint` check. ~1–2 h, zero compute.
Do it before the next promotion or any external use of these numbers.

---

## F16 — the fair width sweep that fixes the deployed allocation predates the determinization-leak fix (low, with its own deflation)

`DECISIONS.md:2958`, verbatim:

> **⚠️ FAIR-BASELINE DISCONTINUITY CAVEAT.** Every past FAIR number in this repo — the k_dets CL-054
> +136 anchor, the curve125 fair confirm (CL-051), the D0 fair ladder (CL-046) — was measured on the
> *leaky* determinization. Those results are **NOT invalidated** (they remain valid PIMC
> measurements) but they are **NOT bit-reproducible** against the fixed agent.

Verified: every `kdets_*` cell in results.csv is dated **2026-07-13**; CL-056 (the leak fix) is
`Promoted 2026-07-14`. The leak was material — CL-056: *"19% of permutation trials flipped the
chosen move"* — and `governance/PRODUCTION.yaml:148` explains today's k8 vs CL-054's k4 purely as
budget-specificity, never mentioning that the k4 optimum was measured pre-fix. The mobile profile
still ships k4 at 2752 on that sweep.

**Deflation, stated up front:** the record already answers most of this — the pre-fix cells "remain
valid PIMC measurements" and CL-056 argues the fix is *"strength-neutral in expectation (same PIMC
distribution)"*. So this is not a reopen; the residual question is only whether the leak's magnitude
varied **with k** (which would tilt an allocation *ordering* rather than a level), and there is no
recorded reason to think it does. **What it funds:** one sentence of provenance on
`PRODUCTION.yaml:148` and on the CL-054 row. Re-running the 2752-tier bracket post-fix is a real
option (~4× cheaper than the parked 11008-tier width test) but this audit does **not** recommend
funding it on this evidence.

---

## Clean bills — kills and caveats checked this pass that are SOLID (do not re-audit)

| item | why it is clean |
|---|---|
| **F-B2b [MAJOR] — `fair_chance` reshuffle unsound vs the transposition table** (`docs/research/foundational_audit_2026-06-02.md:70`: *"deck order isn't in the state key, so determinized children with different futures merge. Fix before trusting any non-clairvoyant search"*) | **Structurally resolved, differently than proposed.** The production fair champion determinizes explicitly and gives each world its own tree (`src/carcassonne_ai/fair_agent.py:190+ search_one_world`, docstring *"fresh tree per determinization = fair_isolate discipline"*), so no cross-determinization merge is possible; the `fair_chance`-with-persistent-tree regime the caveat describes is guarded by `NeuralMCTS(fair_isolate=True)` with dedicated regression tests (`tests/test_fair_info_gate_zero.py::test_3b_*`) and is recorded as CL-056. Stage-1/strong distill gen uses `FairHeuristicPriorAgent`, not `fair_chance`. |
| **The deferred v2.9 h6400 arbiter as a precondition on the S1 production flip** (`docs/POST_REVIEW_PLAN.md:73-75`: *"the h6400 v2.9 arbiter was DEFERRED to promotion-time and never run"*) | **Ran before the flip:** +64.3 elo / z 3.77 / wr 0.591, n=399, fresh band 4.21e9 (`docs/POST_REVIEW_PLAN.md:59`, `STATUS.md:308`, `experiments/results.csv v291_THRONE_bmild_cap8_vs_v28prod_h6400_n399`, CL-041). The pre-commitment was honoured. |
| **Probe §5A's "live offline lead" along tempo** (an INCONCLUSIVE gate with a real residual) | **Indexed:** `docs/LEVER_INDEX.md:63` *"tempo / timing third axis · §5A · `tempo_only` arm — TRIED — INCONCLUSIVE on the rigorous bar; real but leaf-dominated"*, plus CL-040. Exactly the row this audit exists to check for. |
| **CL-068's "LOOSE END, unresolved: … the low end's ORDERING is unmeasured"** | **Discharged 2026-07-29:** the owed 688/1376/2752 deck-matched ladder ran on one shared band (88e9, 3×n=400 paired) and found the low end monotone; recorded in the same claim row. |
| **CL-069's overstating harness banner** | Fixed in code — see F5 (only the registry text lags). |
| **G7 / KWIDTH 22016 ("is 11008 at its knee?")** — a prereg whose KNEE branch was *unreachable* at the realized sd | **Cited correctly everywhere checked.** The prereg banner itself flags the power mis-specification, and STATUS.md:20 / roadmap G7 both carry *"INCONCLUSIVE per its own prereg … NO ROOM IS DETECTED above 11008"* rather than "there is nothing above". The "neither" branch pre-committed only *"Report the interval. Do not promote a direction."* — no skipped follow-up. |
| **The 2026-07-28 pre-gate closures** (adaptive-k census, meeple-dedup screen, C3-intra confirm) | Each row in `docs/LEVER_INDEX.md` §5 already carries its own re-open bar, its own refuted premises, and the caveat that the census measured the signal not the trade. These are the house style working as intended; nothing buried. |
| **KILL: "tabula rasa is dead" (CL-066)** | **The model the other kills should be written against.** 3,600 games over 12 iters, zero heuristic in the loop, all three pre-registered bars missed, mechanism independently measured (`PROBE_OFFDIST_20260724`: the value head memorises its ~1,200 GAME labels — held-out corr 0.530 vs a control's 0.717 on the same games). Status is `Disfavored`, not `Closed` — the correct register. Every citation surface checked is scoped, including `RESULTS.md:72`: *"show tabula rasa is impossible in Carcassonne; it shows it does not happen at our scale."* Its compute-bound and clairvoyant-regime limits are written into the row verbatim. Reopen = ≥10× scale ≈ 3–4 box-weeks; CL-066 itself says don't. |
| **KILL: "learned value can't beat the heuristic leaf"** | **Solid where it counts, and NOT a case of the seed confound.** Every value-as-leaf A/B ran both arms at matched *low* sims (100–200) — the regime that *favours* the leaf-value channel, so these nulls sit in the sensitive direction, and the documented policy-washout effect cuts the other way. Each primary claim carries its own scope verbatim (CL-039's at-this-scale guard; CL-064's K≤2 endgame weighting; CL-049's untested residual-blend). Only the *aggregating* sentence overreaches → F11(a). The one never-sampled regime (CL-049's residual-blend value inside the current fair champion) has a LOW prior by its own row; not recommended. |
| **KILL: "LTR is dead" — the strength half** | No LTR result has ever converted through search (CL-034 Stage 5 tried four integrations at sims=200; all lost to plain `search_leaf`), and production is now further from where a static comparator could help. That half stands. Only the *offline* summary is wrong → F11(b). |
| **D21 (self-play manifests) · D6 (warmstart-mix leakage)** | Both genuinely closed: manifests ship on both paths (`run_manifest.py`, `run_selfplay_iter.py:980-1015`, `gen_fair_distill.py:488-573`) — the "still TODO" note in REVIEW_LOG is itself stale; D6 is inert (`train_iter.py:297` default 0.0, not passed; `:237` short-circuits). |
| **`c5_s3_curve125_fair_vs_h800_k2`** ("POSITIVE-UNRESOLVED, pre-reg fair gate z≥2 NOT met") | **Not** a screen-cited-as-verdict: it was superseded by `c5_confirm_curve125_fair_vs_h800_k2` (n=902, +48.8 / z 3.13), and that confirm is what `PRODUCTION.yaml` actually cites. |
| **Rules-fidelity gaps (WC tie rule · fixed start tile)** | Both logged in `BACKLOG.md` on 2026-07-28 with explicit deferral reasoning and a stated bundling condition ("bundle with G1"), two days after being found. Working as intended — not buried. |
| **F6/CL-063 leaf-residual mining, and G7/KWIDTH** | Both pre-registered an AMBIGUOUS/"neither" branch and both honoured it (no S1 launched; "report the interval, do not promote a direction"). CL-063 was additionally amended by the soft-cap dose sweep. No skipped follow-up. |

---

## Systemic read

**The leak is not in experiment rigor, and it is not in the claim registry.** This project
pre-registers branch tables before results exist, keeps a verdict vocabulary, writes re-open bars
and scope guards into its own kill rows, and discharges most named debts within days — every clean
bill above was resolved *before* this audit looked, and in four of the five big kills the limiting
clause I would have flagged was already written verbatim in the claim's own counterevidence field.
The registry is doing its job.

**The leak is in the aggregating layer, and it is always the same operation: paraphrase across a
boundary of days.** A caveat is born precise and *relative* ("gen search too weak to beat **the
net's own 2752-distilled priors**") and is summarised once, for an index row, as an *absolute*
("sims200 < the ½-budget floor"). From then on the index — the very file designed to be the memory —
is what everyone greps. When the underlying scale moves (deploy budget 2752 → 11008 in a single
afternoon) the absolute paraphrase silently stops meaning what the original meant, and a run gets
funded to test a confound it reproduces (F1). Every other finding is a variant of the same
operation: a scope qualifier dropped from a one-liner (F9, F10, F11), a validity ceiling that only
ever lived in a CSV cell (F2, F12), a claim whose supporting-coherence citation went stale when a
sibling claim reopened with no back-link (F10's F5 leg, F9's CL-068 finding-3), a decisive cell that
exists in results.csv and is linked from nowhere (F6), a deferral whose stated trigger arrived while
the deferral text stayed frozen (F13, F14, F15). **Not one finding is a case of the project
measuring something badly.** Every one is a case of a true sentence outliving the conditions that
made it true.

**Would the new close-out rule — *every null's confound gets a `LEVER_INDEX` row the same day* —
have caught these? Only two of sixteen, and its limits are the useful part.** It catches the seed
case outright and F13. It would **not** have caught F1: the rodv3 row exists, was written the same
night, and it is the *lossy paraphrase inside the row* that failed. It cannot catch F9/F10/F11 at
all, because those are the inverse case — a *kill* that later *reopened*, where the rule points the
wrong way. And F2, F6, F12, F14, F15 are not nulls' confounds at all; they are a ruler ceiling, a
Provisional premise, a variance correction, a shell default, and a missing registry.

Three cheap amendments would cover the residual, in order of leverage:

1. **Quote the caveat verbatim in the index row, in the units it was written in.** Paraphrase is
   where the information dies. "¼ of the budget that produced the net's priors" survives a budget
   promotion; "below the ½-budget floor" does not.
2. **Make reopening a claim a fan-out operation, not a row edit.** F9 and F10 are both "claim X
   reopened; the four surfaces that cite X still say the old thing". The registry has the ids —
   `grep -rn CL-0NN` before closing out a reopen would have caught every instance in this memo. A
   `doc_lint` rule ("a claim whose status changed this week must be re-grepped across docs/") would
   automate it.
3. **When `PRODUCTION.yaml` changes a number, grep the tree for the old number.** F1 and F9 are
   both consequences of "2752" and "91% of the clock" being hard-coded into prose that was true the
   day before.

---

## Appendix — dedup discipline used

Every candidate was checked against `docs/LEVER_INDEX.md` (read in full: §1–§8 plus the
"Genuinely untried" standing list), `docs/PROGRAM_ROADMAP_2026-07-07.md`, and `STATUS.md`'s
current block before inclusion. Items **rejected as already-indexed** (i.e. found, verified live,
but disqualified because the index already holds them — listed so nobody re-reports them as
findings): the k4×2752-at-11008 width test named by CL-060/CL-070 as *"STILL UNRUN AND CHEAP"*
(standing-list item 5, though CL-071's promotion of k8 raises its priority); the
`--temp-threshold`/Dirichlet re-sweep (item 1); prior flattening as a game A/B (item 3); the
replay-window A/B (item 4); LTR on the Gate-C representation (item 6); sub-2752 budget points at
production width (item 11); batching the k determinizations into one eval request (item 12);
CL-054-vs-CL-060 width tension (§5 row, marked UNRESOLVED); and the *"re-read any older
equal-wall-clock ratio with suspicion"* warning attached to the batch-1 fix (§8 row). Also
disqualified as roadmap-open: A3/A4, D1–D3, E1–E4, B4 (incl. the "2-epoch batch-256" remainder),
G1; and the stage-3 value-unlock pre-gate + the n=1600 classical bundle, both carried as open
conditionals at roadmap `:84` — the first is worth a one-line cross-reference when rodv3's Arm B is
funded, since the prereg does not mention its pre-gate.

Method note: four parallel read-only sweeps (DECISIONS hedge-markers · the `measurement/` and
`governance/` trees · REVIEW_LOG D-numbers + BACKLOG + results.csv notes · an inverse check on five
load-bearing kills) plus this auditor's own pass over `docs/`, `PROJECT_CHARTER.md`, the claim
spine, and the live rodv3 artefacts. **Every quote in this memo was re-read from its named file
by the auditor before inclusion**, and two candidate findings were corrected in the process: the
CL-010 falsifier turned out to have *run* (F6, which strengthened the finding) and the h1600 rung
is +34.9, not the +24.4 first reported. Six further candidates died on the dedup check and are
listed above.
