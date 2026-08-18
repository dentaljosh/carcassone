# PREREG FAILURE DISPOSITION — the shared rung-2+3 run, pair `604edc83`

> **The pair is SPENT-BY-GATE-FAILURE. The corpus is REUSABLE INPUT. Those are different
> objects and the distinction is the whole content of this file.**
>
> The blind-committed pair [`shared_run/DESIGN.md`](shared_run/DESIGN.md) +
> [`shared_run/READ_RULE.md`](shared_run/READ_RULE.md) (rev R3.3, blind commit `604edc83`) is
> **frozen history**. It is not amended, not revived, and not re-read. The successor is
> [`shared_run_r4/`](shared_run_r4/DESIGN.md).
>
> **`governance/PRODUCTION.yaml` untouched. No claim minted. No `experiments/results.csv` row.
> No strength statement of any kind is made or implied by this document.**

## 1. What happened — two §2 gates fired, pre-scoring, as designed

| gate | result | detail |
|---|---|---|
| `G-DISJOINT` | **FAIL** | Exactly **one** `c_position_digest` collision: S1 `tt_sp_135000000122_p2` ↔ banked `tt_sp_28100000609_p2`, digest `dceabd7b…`. **Zero** root overlap, **zero** rid overlap — a genuine cross-band **board transposition**, not a corpus leak. |
| `G-COMPLETE` | **UNSATISFIABLE AS WRITTEN** | Realized supply **S1 551** against a 1,283 floor; **S2 capped 103** against a 1,045 floor. Not a shortfall to be topped up — a **27× miss** on S2. |

**Both fired before one position was priced.** They are §2 preconditions, evaluated before any
branch statistic by construction, and no scoring leg ever started.

Two execution notes, recorded because they cost information:
- The corpus driver aborted under `set -e` at the first failing gate, so **`GATE_DRAW.json` was
  never emitted**. A gate suite that short-circuits tells you about one failure when it could
  have told you about all of them — `run_tiletie`'s own preflight already has the right
  behaviour ("all checks always run and are all printed, not short-circuited"). R4 requires the
  same of the corpus driver (a W-code change, R4 §8).
- The blind top-up clause (≤200 games ⇒ ≈ +41 capped plies) **cannot rescue a 27× miss.** It was
  sized against a supply model that was wrong by an order of magnitude; exercising it would have
  bought nothing and spent the one pre-licensed top-up.

## 2. Why `G-COMPLETE` was unsatisfiable — the sizing error, named

§3's yield table treated **raw census rows as final supply**: 350 games × `--max-per-game 4` =
1,400 rows, read as ≈1,400 usable positions. Two mandatory reductions were omitted, **one of
which §6 of the same document requires**:

```
raw census rows            1,400   (350 games x 4)
  x qualification  ~0.54     756   (tie must survive the qualifying predicate)
  x afterstate dedupe ~0.735 556   (the dedupe §6 ITSELF mandates: -26.5%)
realized                     551
```

The S2 target was worse than optimistic — it was **internally inconsistent**: §3 carried the
capped fraction **0.1807** as a constant *and* asked for 1,100 capped plies from 500 games, which
requires a capped rate of 2.2/game against its own constant's implied ≈0.22/game. The realized
capped fraction **103/613 = 0.168** is in line with the constant; it was the *target* that
contradicted it, not the world. **The design's own arithmetic refuted its own target, and no
review round caught it** — which is why R4's supply chain is written out in full, every stage
shown, and why supply arithmetic is explicitly in the reviewer's scope this time.

## 3. ⭐ The blindness argument — band 135e9's 850 games are REUSABLE INPUT

**This is the load-bearing claim of this document.** Stated in full because a successor's validity
rests on it.

**3.1 What was read.** Counting statistics only: raw census rows, the qualification and dedupe
survival rates, per-stratum supply (551, 613, 103), the per-game rates (1.574, 0.206), the
realized capped fraction (0.168), and one board-digest collision (two rids and a digest).

**3.2 What was NOT read — and, more strongly, what does not exist.** The run stopped **pre-scoring**.
No `arb`, no `ora`, no `Δ`, no CI, no per-position value exists **anywhere on disk** for these
positions. This is not "we did not look"; it is **"it was never computed."** That is a materially
stronger claim than the usual blindness assertion, and it is available here only because the
gates are preconditions that run before any statistic — which is exactly why they are written
that way.

**3.3 Why supply counts cannot leak an outcome.** A supply count is a function of the corpus's
**structure** — how many plies tie, how many survive dedupe, how many hit the `J = 4` cap. The
map from *"how many capped plies exist"* to *"what `Δ_ora` is"* is precisely the unknown the run
exists to measure. Nothing in a count constrains the sign or the magnitude of any branch
statistic. The house precedent is direct: the rung-1 kill-census read `phi`, arbitrable fractions
and duplicate shares off two corpora, declared itself *"a census that counts and never scores"*,
and adjudicated a rung without contaminating anything.

**3.4 What the counts DO constrain, declared rather than glossed.** They determine **sizing**. R4
chooses its `n` from realized rates measured **on these same games**, so **R4's `n` is not
statistically independent of the 135e9 corpus's structure.** That is legitimate and precedented —
it is a **nuisance-parameter read**, the class PLAN_J §1.1 already used when it recounted arm-set
sizes off a spent corpus and declared it *"a COST statistic, no outcome value used"* — and it
biases no estimand: `n` is fixed before any value exists and applies symmetrically to every arm,
stratum and branch. It is declared here so no reader has to discover it.

**3.5 The one thing that IS spent.** The **pair** — its single-use read rule — is spent by gate
failure. The **corpus** is not: nothing about these positions was adjudicated, priced or read as
an outcome. Hence the disposition in the banner: pair `SPENT`, corpus `REUSABLE INPUT`.

**3.6 A carried obligation.** The digest-colliding rid `tt_sp_135000000122_p2` collides with the
**banked Stage-1b** corpus regardless of which prereg reads it. It is excluded in R4 too, under
R4's pre-committed exclusion rule — not re-adjudicated.

## 4. Disposition

- **Pair `604edc83`: SPENT-BY-GATE-FAILURE.** Frozen; never amended, revived or re-read. Its
  `G-REPLICATE` reference (`STAGE1B_LADDER.json`), the W-code, the fixtures and the acceptance
  harness are unaffected and carry forward **by reference**.
- **Band `135000000000` +0…+849 (850 games): VALID INPUT, retained**, minus the one excluded rid.
- **Band `136000000000`: RELEASED UNUSED.** It was R3's top-up reservation; releasing it rather
  than repurposing it keeps "which prereg consumed which band" unambiguous.
- **Extension generation claims a fresh band** (R4 §3).
- **No band retires from confirmatory use on this event** — nothing was decision-influenced,
  because nothing was decided.

*Both gates did their job. A prereg whose preconditions fire before any money is spent on scoring
is a prereg working correctly; the failure worth recording is the sizing arithmetic in §2, and it
is fixed by measurement in R4, not by argument.*
