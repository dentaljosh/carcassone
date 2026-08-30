# CL-083 RED-TEAM SYNTHESIS — verdict, dedup, and the experiment menu

**Bottom line: CL-083 needs a SCOPE amendment, not a BREAK.** Two of its clauses are stated wider than the evidence supports — the *independence* of the four instruments, and the *"plus cross-game adaptation"* conjunct. The negative core ("the edge is not a per-move gap that any measured leaf/rollout family closes") survives all four attacks, and survives one attack's own mechanism test, which I ran on banked data (below). Nothing here changes a funding decision that has already been taken; it changes how S1's G3 result will be read.

---

## 1. Dedup: the four attacks are three cracks, one of which I refuted

| # | Crack | Raised by | Severity after verification |
|---|---|---|---|
| A | **Policy-family conditionality + non-independence.** 3 of 4 instruments price futures under production-champion continuations; 3 of 4 draw from one 50-game corpus via one Stage-A census. "Four independent instruments" overstates the evidence. | shared-assumptions (primary), instrument-gap (variant), statistical (implicitly) | **SCOPE — amend** |
| B | **The "plus cross-game adaptation" conjunct has no supporting instrument, and the registered falsifier cannot falsify the conjunction.** | adaptation-confound | **SCOPE — amend (split the row's positive half)** |
| C | **farm_capture stratum reads persistently positive and was never powered.** | statistical | **WATCH — already in the counterevidence column; my leverage read says do not upgrade it** |
| D | **Consummation hole:** the instrument forced the owner's tile but let the champion choose the same-turn meeple, so the null prices "owner tile + champion plan." | instrument-gap | **COSMETIC — mechanism REFUTED on banked data (see §2.1); keep one caveat line** |

---

## 2. New evidence I generated (read-only, no repo writes)

All 728 continuation unit files are still on disk at
`/home/doctor/projects/carcassone/.claude/worktrees/agent-a93ae8ea54b24c9b6/measurement/e4_continuation_20260828/out_local|out_laptop/`
(mirror on the laptop at `/home/doctor/carc-e4cont/...`). That made three of the four proposed "free" precursors runnable now. Script: `/tmp/claude-1000/-home-doctor-projects-carcassone/d538aba0-bcf8-4b08-a01a-684a1ae3c7eb/scratchpad/split.py`.

### 2.1 The consummation attack's own Step 0 — runs, and cuts against it

`followup_agrees_with_archive` semantics (verified at `measurement/e4_continuation_20260828/continue_plies.py:421`): did the champion's *next* action in `arm_owner` equal the archive's ply+1 action.

Stratum phase composition (verified): invasion / defense / control targets are **100% tiles-phase**; **farm_capture targets are 100% meeple-phase (12/12)**.

| stratum | agreement rate (worlds) | reading |
|---|---|---|
| invasion | **0.810** (136/168) | true consummation rate |
| control | 0.800 | true consummation rate |
| defense | 0.893 | true consummation rate |
| farm_capture | **0.240** | **not a consummation statistic** — those plies *are* the meeple; "follow-up" = the opponent's next tile |

So the quoted pooled `0.7569` is a mixture of two different quantities, and the real consummation-divergence rate on the invasion stratum is **19%, concentrated in 4 of 21 plies (all-or-nothing per ply, not scattered)**.

Price split (attack's own predicted signature was: negatives concentrate in the divergent subset):

- invasion, **champion consummated** (17 plies): **−1.88** (se 2.30)
- invasion, **champion declined the owner's meeple** (4 plies): **+0.66** (se 2.61)
- as-treated primary, consummated-only: **invasion − control = −2.30 ± 2.84, z −0.81** (vs the registered −1.87 ± 1.88)

The negative sits in the fully-consummated subset; excluding the non-consummated plies makes the primary *more* negative. **The attenuation mechanism is contradicted in sign.** (n=4 is powerless to prove the converse — hence one caveat line, not an amendment.) Side note worth banking: defense plies where the champion declined the follow-up price **−5.12 (n=3, z −1.79)** — a curiosity, not a finding.

### 2.2 The farm_capture thread — real at ply level, but one-ply-leveraged and *not* two independent reads

- The 12 continuation farm plies are a **strict subset** of C1's 14 (12/12 overlap). Corpus overlap overall: 72 of C1's 188 plies are continuation plies; 45 vs 38 games from the same 50-game archive.
- Ply-level correlation between the two arms (different contrasts, disjoint world indices — continuation w0–7, C1 w16+): **Pearson r = 0.775**. That is genuine position-level replication (not measurement noise) — but it means the two reads do **not** halve the between-ply variance that caps the stratum mean. They are one signal measured twice.
- **Leverage:** one ply (`1787277974_331305.json` p97: +16.52 C1 / +16.12 continuation) carries it. Drop it and continuation farm goes **+2.53 (z 1.68) → +1.30 (z 1.37)**; C1 goes **+2.41 (z 1.42) → +1.33 (z 0.94)**. Leave-one-game-out worst case z 1.19.
- The statistical attack's arithmetic checks out where it matters: retention against CL-084's 50% falsifier bar is control −16.0%, defense −19.3%, invasion +12.6%, **farm_capture +40.2%** (2.414/6.000); and C1's achieved 2σ MDE (3.68) does exceed the point estimate — the confirmatory test was underpowered against its own prior.
- Its structural point also checks out: **more worlds cannot help** — farm sd across plies is 5.22 at M=8 and 6.36 at M≤64. Between-ply variance dominates; only new plies move the se.

**Net: leave CL-083's counterevidence column as the home of this thread. Do not promote it to an amendment of the per-move clause on current data.**

### 2.3 The adaptation Tier-0 re-cut — ran it, three statistics, all flat

Corpus ordered by `finished_at`, conditioned on budget epoch (53 games at `sims_effective=1376`, 2 stragglers at 688, 1 at the 22k mobile note):

| statistic | first half | second half / last-15 | contrast |
|---|---|---|---|
| owner margin (11k epoch, n=53) | +11.1 | +16.2 | **+5.1, se 6.9, z +0.75** |
| owner invasion plies/game (priced-ply proxy) | 1.76 | 1.68 | **−0.08, se 0.30, z −0.27** |
| agreement gradient (invasion − control) | +0.394 (z 4.05) | +0.416 (z 4.37); last-15 +0.360 (z 2.78) | flat |

**No within-corpus adaptation ramp is visible in any of the three cheapest banked statistics** — the owner expressed the exploit at full rate from the start of E4, and the gradient is time-stable. This is *underpowered* to exclude a ramp (the corpus resolves ~±14 pts on the half-difference at 2σ) and says nothing about pre-corpus adaptation, but it means the "plus cross-game adaptation" conjunct currently has **no positive instrument on either side** — which is a slightly different (and more honest) problem than the attack framed. It also sits in mild tension with `measurement/e4_exploit_grading_20260825/COMPOSITION.md` §"the learning curve is on the CHAMPION's side" (champion city-share −8.1pp): the composition signature moved, the margin did not resolve.

---

## 3. Does CL-083 need amendment as written? Yes — three edits, all scope/wording

The claim's *evidence* is not impeached. Its *quantifiers* are.

**Minimal honest amendment (proposed text — owner edits the registry, not me):**

1. **Headline clause.** Replace
   *"NOT per-move superiority — and no per-ply intervention of any measured family touches it"*
   with
   *"NOT per-move superiority **as priced under production-champion continuations and priors** — and no per-ply intervention of any measured family touches it **when graded that way**. Per-ply value that materialises only under an exploit-expressing (non-champion) continuation is UNPRICED, not excluded."*
   Rationale: the assumptions column already concedes exactly this for defense/steering; the concession belongs in the claim, and it extends to the attacking strata, whose payoff also lives on futures the champion's own search rarely visits (`measurement/s1_asymmetry_prep/DESIGN.md` §0).

2. **Independence clause.** Replace *"Four independent judge-free instruments converge"* with
   *"Four judge-free instruments converge, **sharing two axes**: (2) and (4) share the champion-continuation engine and 72 plies of one corpus; (1) and (2)/(4) share the corpus and the Stage-A selector; (3) is corpus-independent but was screened at k4×688=2752 inside a champion-family search whose internal opponent does not invade. **Independent evidence axes ≈ two (the agreement gradient; the S0v2 scripted exploiter), not four.**"*
   Note that the *convergence* is still real — three different estimands land on the same conclusion — but co-convergence of correlated instruments should not be quoted as four-fold.

3. **Positive half.** Split the row (or add a confidence qualifier in place):
   - **CL-083a — the edge is upstream of single-ply move choice.** confidence **high**, unchanged.
   - **CL-083b — the upstream edge is transferable position-steering plus cross-game adaptation, shares unknown.** confidence **medium/conjecture**, with the live alternative named: *mining of a stationary leak in a frozen opponent*. Add the Tier-0 result above as the first (null, underpowered) evidence for the adaptation share, and note that the registered falsifier — "edge collapsing vs an unfamiliar opponent" — **falsifies 083b only**, never the conjunction, which is why the split is needed for the falsifier to bite.

4. **Counterevidence column, one clause added:** *"farm_capture's two reads are correlated r=0.78 on 12 shared plies (not independent replications) and halve to ~+1.3 when the single highest-leverage ply is dropped; the 40% out-of-sample retention vs CL-084's 50% bar is the one place argmax-noise does not fully explain the gap."*

5. **Assumptions column, one clause added:** *"the target ply's same-turn meeple consummation is the champion's choice, not the owner's (19% divergence on the invasion stratum); the banked split shows the negative price sits in the consummated subset, so this is a scope note, not an attenuation."*

Confidence on the row overall: keep `high` for 083a; the `high` on the bundled row as currently written is not defensible once 083b is stated as a share-unknown conjunction.

---

## 4. Proposed experiments, ranked, with costs

Costed off the banked per-ply remaining-ply counts (Σ remaining: invasion 1,986 · defense 2,192 · control 2,996 · farm 360) at the run's own measured **1.16 s/continuation-ply**, on local W30 + laptop W22.

| # | Experiment | What it settles | Cost |
|---|---|---|---|
| **E-1** | **Out-of-family / exploit-expressing continuation arm.** Re-run `e4_continuation_20260828` verbatim on the same 91 plies with the continuation policy swapped. Two candidate families: (a) tier1-greedy — CL-085's validated out-of-family read, cheap, but *weak*; (b) an **exploit-expressing** continuation (S0v2 scripted invader, or the C-term γ≈0.07 agent) — the family whose blindness is the hypothesis. **(b) is the one that answers the question; (a) only shows family-sensitivity.** | Crack A. Null again ⇒ the per-ply null earns the independence CL-083 currently asserts. Positive ⇒ clause 1 above becomes mandatory, and a per-ply route reopens. | **~1.1 two-box hours per continuation family at champion cost** (invasion 0.20 h, control 0.30 h, defense 0.22 h, farm 0.04 h); far less with tier1-greedy. ⚠️ the B-invader was retired 2026-08-30 and S0v2 is parked, so the *expressing* opponent is an S1 deliverable — fold E-1 in as S1 by-catch rather than funding a standalone opponent build. |
| **E-2** | **`arm_owner_turn`** — force the archived tile *and* its archived meeple at the 21 invasion plies + a control analog, same CRN worlds. | Crack D, formally. Priority dropped from the attack's "at minimum AMEND today" to **optional**: §2.1 already shows the negative lives in the consummated subset. Worth one arm if E-1 runs anyway (shared launcher). | **~0.25 two-box hours** (invasion 0.10 + control 0.15, 1 extra arm each). |
| **E-3** | **New-plies farm test.** Pre-register now: when the growing archive holds ≥30 *new* divergent farm_capture plies, price them alone at M=16, same CRN discipline. Out-of-sample by construction, immune to multiplicity, and the only lever that moves the se (worlds provably cannot). | Crack C. z≥2 ⇒ amend the per-move clause and fund the farm leaf term; z<1 ⇒ the thread dies with power. | Pricing: **<0.1 two-box hours**. Champion-counterfactual input: ~50 min two-box for a 290-ply pass. **Real cost is owner game-time: ~50–70 more E4 games.** Pre-registering costs nothing today. |
| **E-4** | **Tier-0 temporal re-cut.** | Crack B. **DONE — results in §2.3.** Worth a `READ_RULE.md` + a repo home if the owner wants it cited. | **spent (this session).** |
| **E-5** | **Carcasum-unfamiliar owner session, ARM-ON.** Read the *signature* (deliberate invasions per `merge_plausible` opportunity, using the S0v2 census tooling) rather than the margin: per-game sd 0.53–0.71 resolves expression in a handful of games; margin collapse +13 → 0 resolves at ~2.5σ by n≈16. **Mandatory control: condition on opportunity supply** — Carcasum may simply not build invadable structures. | Crack B, decisively. **The only instrument in the program that separates steering from mining-a-stationary-leak.** | **16–20 owner games + a small census script; zero cluster compute.** |

**Sequencing recommendation:** E-4 is spent. E-3 is a pre-registration to write today at zero compute. E-1(b) should ride S1 rather than pre-empt it — S1's armed opponent *is* the missing continuation family, and re-pricing the 91 banked plies under it is ~1 box-hour of by-catch that converts CL-083's largest scope hole into a measurement. E-5 is the highest information-per-cost item on the whole list and needs only the owner's evenings.

**Artifacts of record:** `/home/doctor/projects/carcassone/governance/CLAIM_REGISTRY.csv` (CL-083/084/085) · `/mnt/c/carc-shared/e4_continuation_20260828/CONTINUATION.json` · `/home/doctor/projects/carcassone/measurement/c1_pricing_prep/C1_PRICING.json` · `/mnt/c/carc-shared/e4_ply_pricing_20260827/` (PRICED.json + rows_*.jsonl) · `/home/doctor/projects/carcassone/measurement/e4_continuation_20260828/{PREREG.md,continue_plies.py}` · `/home/doctor/projects/carcassone/measurement/e4_games/` (56 archives) · `/home/doctor/projects/carcassone/measurement/e4_exploit_grading_20260825/COMPOSITION.md` · `/home/doctor/projects/carcassone/measurement/s1_asymmetry_prep/DESIGN.md`.