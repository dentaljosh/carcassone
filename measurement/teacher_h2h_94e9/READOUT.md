# TEACHER H2H — READ-OUT (band 94e9, n=400 deck-paired, COMPLETE 2026-07-30 09:56 EDT)

> **STATUS: RESULT — the pre-registered BRACKET-NARROWING branch fired. NOT a verdict.**
> Prereg [TEACHER_H2H_PREREG.md](../../scripts/distill_flywheel/TEACHER_H2H_PREREG.md) (`f2e11ca`,
> committed before the first game). Nothing promoted; `governance/PRODUCTION.yaml` untouched.
> ⚠️ **A `results.csv` row is OWED and deliberately not written by this agent** (out of its
> authority) — see Close-out below.

## The measurement

**Candidate** = CL-067 `iter_03` net POLICY priors + FROZEN curve125 leaf (value severed),
**k4×688 = 2752**. **Opponent** = the production champion at its promoted `fair_deploy` budget
**k8×1376 = 11008** — i.e. **the net against its own corpus teacher's tier**, the pair that had
never been measured in either direction.

| statistic | value | z |
|---|---|---|
| W–D–L | **184–8–208** | |
| winrate | 0.4700 | **−1.20** |
| **elo** | **−20.9 ± 17.4** (1σ) | **−1.20** |
| **deck-paired margin** | **−2.0025 pts/deck** | **−1.90** |
| sign agreement | **YES** (both negative) | |
| cost/move | candidate 16.10 s · opponent 14.05 s | ratio **1.15×** |

Integrity verified before reading: `n=400`, `n_paired=200`, 400 records on disk (see the
fails-open incident below — this check was not a formality).

## Pre-registered branch: BRACKET-NARROWING → the n→800 extension FIRES

`|elo| = 20.9` lands inside the pre-committed `[5, 25]` interval and `|z| < 2`, so by the rule
fixed before the first game this is **explicitly not a verdict**, and the pre-registered response
is: **extend the SAME cell to n=800 on fresh decks of band 94e9, then verdict.** That extension is
scientifically pre-committed but is a **~7 h two-box spend** and has **not** been launched —
compute spend is Joshua's call (cost-discipline rule).

## What it already tells us, stated at the strength the evidence supports

**The direction is negative and both statistics agree** — the candidate is *below* the tier that
taught it, and the margin statistic (the one that is harder to move) sits at **z −1.90**, just
under 2σ. Read carefully:

- **This discriminates between the two derivations that motivated the cell.** They disagreed in
  sign: ≈**+8** via CL-060's budget-only route, ≈**−14** via CL-067's `counterevidence` equal-cost
  route. The measured **−20.9 ± 17.4** is consistent with the −14 route and sits ~1.7σ from the
  +8 route. So the "operator produces data above its own corpus tier" reading is the one the data
  disfavours — which is exactly the question the cell was funded to settle.
- **It does NOT contradict CL-067.** That claim is `+35.7 ± 12.3` at **equal sims** (2752 vs 2752)
  and is untouched. The two together say something sharper than either alone: *the net beats
  same-budget classical play, and still does not reach the tier that generated its training
  corpus when that tier is given its 4× budget.*
- **The cost picture makes it worse, not better.** The candidate spent **1.15× the opponent's
  wall-clock per move** while scoring ~21 elo below it. At equal wall-clock the gap would widen —
  consistent with CL-067's separately-resolved deployability REFUTED.
- **Do not over-read a 1.2σ elo.** House practice in this family is to inflate σ 1.5–2× on
  cross-band comparisons; this is a *within-band deck-paired* contrast, which is the robust class,
  but n=400 still only resolves effects ≳35 elo at 2σ. The extension exists precisely because
  −20.9 is in the zone where this program has been fooled before.

## Consequence for rodv3 turn 1 (pre-registered, not improvised)

If the extension confirms PREMISE WEAK, the prereg's own consequence applies: the awakening premise
narrows to *"above same-budget classical only"*, **gen at the corpus-teacher budget (k8×1376 =
11008, ~29 h local-only) becomes the ONLY clean test of lever 6**, and **a DEAD turn-1 gate becomes
expected rather than informative** — which is the outcome that *saves* funding that 29 h on a hunch.
This is the F1 amendment's surviving discriminator, and this cell was run first precisely to price
it. Turn-1 gen stays parked at **65/300**; its gate remains **NOT funded**.

## ⚠️ Incident: the fails-open guard fired — and my first diagnosis of it was wrong

At 09:52 a `summary.json` appeared with **`n=399, n_paired=199`** — a completely plausible-looking
summary for a cell that was asked for 400. This is the documented **eval-path fails-OPEN** hazard
(self-play fails closed and loud; eval writes a clean short summary). The integrity check caught it.

**But my remediation was premature, and the honest record matters more than a tidy one.** I found
one claim without a record — `seed094000000199_a1`, whose claim file said **`laptop:107288:…`** —
checked for live clients **on local only**, saw none, and concluded the claim was stranded. It was
not: the laptop was still playing that game. I parked the short summary, cleared a **live** claim,
and relaunched, which started a **duplicate** worker on a seed another box already owned.

What actually happened: the **local** client exhausted its share first and wrote a summary counting
the 399 records then on disk; the **laptop** finished the last game at 09:56:08 and rewrote
`summary.json` at the correct `n=400`. **The system self-corrected and my intervention was
unnecessary.** I killed the duplicate client (main + 21 spawn children by exact pid, then its orch
and SHM) **before it could finish and overwrite a completed record** — verified: the final record's
mtime is still 09:56:08, records 400, claims 400, summary `n=400 / n_paired=200`.

**Lesson, worth more than the incident:** a `.claim` file *names the host that owns it*. Before
declaring a claim stranded, check **that host** — not the box you happen to be typing on. The
information needed to avoid this was in the file I had already printed. The short summary is
retained as `summary_n399_PARTIAL.json` for the audit trail.

## Close-out obligations still owed (outside this agent's authority)

- **`experiments/results.csv` row** — a real strength measurement with both statistics; owed.
- **CLAIM_REGISTRY**: this answers CL-067's neighbouring open question; a new claim id or an
  amendment is owed.
- **`eval_fair_puct.py` `PROD_KNOBS`** is stale at the pre-promotion `k_dets=4, sims=688`, making
  its "NOT the shipped production champion" banner **inverted** since CL-071. Quiet-window fix; the
  harness's own `opponent_label` ("FAIR PRODUCTION CHAMPION … k8x1376") is the correct one.
