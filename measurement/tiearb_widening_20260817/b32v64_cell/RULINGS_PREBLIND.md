# `b32v64_cell` — PRE-BLIND DRAFTING RULINGS

> **Dated pre-blind text amendments on a drafted-but-not-yet-blind pair.** House pattern
> carried from [`b64_cell/RULINGS_PREBLIND.md`](../b64_cell/RULINGS_PREBLIND.md).
>
> ⚠️ **PRE-BLIND MEANS: before the blind commit, before the smoke, before game 1, and before
> ANY statistic of this run exists.** `WORKERS.conf::BLIND_COMMIT` still reads `PENDING`, no
> `summary.json` or `manifest.json` exists for either cell, and `run_cells.sh` mechanically
> refuses a real-cell launch. **Every ruling below is therefore a DESIGN AMENDMENT, not a
> post-hoc reinterpretation**, and the ordering is provable from git.

---

## RULING 1 — 2026-08-21 — `L-SATURATED` becomes ONE-SIDED NON-INFERIORITY at the same tolerance. **OWNER RULING.**

**Status: PRE-BLIND. OWNER-SELECTED. ADOPTED.**

### What the owner was shown, and what he chose

The orchestrator put an option card to the owner. The owner selected, **verbatim option
label**:

> **"One-sided ±15 (Recommended)"**

with the **verbatim description shown to the owner**:

> *"Fire the swap license when the one-sided 95% upper bound on the cost is under 15 elo…
> Matches the actual question — we only care if 32 COSTS elo, and the L-REVERSED branch
> already catches '32 is better'."*

### The amendment, in one line

```
WAS (drafted):   EQUIV  ==  ( |D| + 1.645*se_D  <=  0.93 )      # two-sided equivalence (TOST-style)
IS  (ruled):     EQUIV  ==  (  D  + 1.645*se_D  <=  0.93 )      # ONE-SIDED NON-INFERIORITY
```

**The tolerance does not move.** It is the same ±0.93 pts/game (±15 elo at the committed
16.1247 elo/pt gloss) the owner set when he funded `n1500`. **Only the SHAPE of the test
changes** — from "the whole 90% CI sits inside a two-sided band" to "the **one-sided 95%
upper bound on the cost** sits below the tolerance".

⚠️ **The `1.645` is unchanged and it is the SAME NUMBER doing a DIFFERENT JOB.** As drafted it
was the 90%-two-sided critical value; as ruled it is the **95%-ONE-SIDED** critical value.
`z_{0.95} = 1.645 = z_{0.95, two-sided-90%}` — the arithmetic is identical, the interpretation
is not, and the read-out must state it as **"one-sided 95% upper bound"**, never as "90% CI".

### Why it is the right shape — the owner's own reason, restated mechanically

**The question this cell exists to answer is asymmetric.** The deployed shape is `B` = 64; the
swap-down to `B` = 32 is licensed only if `B` = 32 **does not cost** more than the owner's
tolerance. **"`B` = 32 is BETTER than `B` = 64" is not a reason to refuse the swap — it is a
stronger reason to take it.** A two-sided band refused the licence in exactly that case, which
was a defect of shape, not of tolerance.

**And the large-negative arm is already owned by a different branch.** `L-REVERSED`
(`z_D ≤ −2.0`) is evaluated **second**, before `L-SATURATED`, and pre-empts it by
first-match-wins. So the one-sided form does **not** hand `L-SATURATED` the whole negative half
line in practice:

- **large-negative `D`** (`z_D ≤ −2.0`) ⇒ **`L-REVERSED` fires first.** `L-SATURATED` is never
  evaluated there. The reading "narrowing makes it *better* at 2σ" is a stronger and more
  specific finding than "narrowing does not cost 15 elo", and it gets its own branch and its
  own mandatory riders.
- **mildly-negative `D`** (`−2.0 < z_D < 0`) ⇒ **`L-SATURATED` fires, and that is CORRECT AND
  DESIRABLE.** The claim it licenses — *"`B` = 32 does not cost 15 elo"* — is **true** there,
  and more comfortably true than at `D` = 0.

⇒ **the effective `L-SATURATED` region is `(−2·se_D , 0.93 − 1.645·se_D]`**, which is bounded
on both sides *by the branch order*, not by the predicate. **That is stated in
[`READ_RULE.md`](READ_RULE.md) §4.4 rather than left to be inferred.**

### What it buys — computed, not asserted

At the committed `se(D)` = 0.5044 (realized-dispersion projection 0.4570 in brackets), the fire
window becomes `D̂ ≤ 0.93 − 1.645·se_D` = **0.1003** (**0.1782**) — **numerically the same upper
edge as the drafted two-sided window**; what changes is that it is no longer bounded below.

| true `D` | drafted (two-sided) | **ruled (one-sided), EFFECTIVE after `L-REVERSED` pre-emption** |
|---|---|---|
| `0` (the rungs are equal) | 0.158 (0.304) | **0.556 (0.629)** |
| `+0.0399` (offline bracket FLOOR) | — | **0.529 (0.601)** |
| `+0.1555` (offline bracket TOP) | 0.150 (0.287) | **0.446 (0.510)** |

⇒ **the ruling roughly TRIPLES the probability that a genuinely non-inferior `B` = 32 can be
SAID to be non-inferior, at n = 1,500 and with no extra spend.** ⛔ **It does NOT loosen the
tolerance and it does NOT make the verdict easier to over-read** — the mandatory scope sentence
on the branch is tightened, not relaxed, to say *upper bound* and *one-sided*.

### ⚠️ What this ruling does NOT do

- **It does not move the tolerance.** ±0.93 pts/game (±15 elo) stands, unchanged, as the owner
  set it.
- **It does not move `n`.** `n` = 1,500 decks/cell stands. ⛔ [DESIGN](DESIGN.md) §6.1's rule —
  *the smoke may HALT, it may never RESIZE* — is untouched.
- **It does not touch `L-REVERSED`, `L-RISING`, `L-AMBIGUOUS` or `U-UNREADABLE`.** Their
  conditions are byte-identical to the drafted ones. `L-AMBIGUOUS` remains the complement, so
  **totality is preserved by construction**.
- **It does not touch any gate.** All 13 §3 rows are unchanged.
- **It does not touch the cost analysis, the band, the cells, the knobs, or the launchers.**
- ⭐ **It does not change the KNIFE-EDGE.** For a **positive** point estimate the two shapes are
  arithmetically identical (`|D| = D`), so the `n` at which the offline bracket TOP would fire
  is **unchanged at 1,722 decks (committed law) / 1,413 decks (realized law)**. What changes is
  the *probability of landing in the window*, not the window's upper edge.

### Where it lands

| document | section |
|---|---|
| [`DESIGN.md`](DESIGN.md) | §6.3 (the `n` table's window/power columns), **§6.4** (the reachable-branch set + the power statement + the knife-edge), §5.2 closing, §10 threat 1, §13.1 (the unreachable-branch disease row) |
| [`READ_RULE.md`](READ_RULE.md) | §2.1 (`EQUIV_SHAPE`), **§4** (the `EQUIV` definition), **§4.0** (reachability + power), §4.1 branch 4, **§4.4** (the disjointness note) |
| `WORKERS.conf` | `TOLERANCE_PTS` / `EQUIV_SHAPE` — ⚠️ **owned by the ADJUDICATOR BUILDER**, not by this drafter; the builder is parameterizing `scripts/tiletie/analyze_b32v64_cell.py` on them and has been told to set `EQUIV_SHAPE=one_sided` |
| ⭐ `scripts/tiletie/analyze_b32v64_cell.py` | **`BRANCH_TEXT["L-SATURATED"]`** (headline, licence (i), the MANDATORY SCOPE SENTENCE, the power rider, **and the THIRD rider that did not exist before this ruling**) · **`BRANCH_TEXT["L-AMBIGUOUS"]`** (headline, scope sentence, rider (i)'s statistic list, **and the ⭐ high-side-only note the one-sided shape CREATES**) · **`POWER_AT_COMMITTED` / `POWER_AT_REALIZED_PROJ`** → 0.5560 / 0.6290 · **`N_FOR_80PCT_EQUIV_COMMITTED` / `_REALIZED`** → 2,728 / 2,240 decks/cell · the **`power_statement`** and **`reachable_branches`** strings → the ~56% / ~63% figures · **`modal_pre_run_expectation`** → `L-SATURATED` (0.556 > 0.444) · **`EQUIV_SHAPE_TEXT` / `CI_Z`'s comment** → *"one-sided 95% upper bound"*, never *"90% CI"* · **`d_block` / `render` / `main` / `gate_stat`** → **`UB95(D)` is the PRIMARY and is emitted BY NAME**, `CI90(D)` demoted to context |
| ⭐ `tests/test_tiearb_b32v64.py` | the sweep must assert the branch **TEXT**, not only the branch **LABEL** — at minimum that no `BRANCH_TEXT` entry contains the string `"90% CI"`, that `L-SATURATED`'s third rider is present, and that the power constants equal the pair's — plus the constants themselves (the suite previously asserted `== 0.158`, i.e. it **enforced** the superseded value) |

⛔ **`scripts/tiletie/` and `tests/` are the BUILDER's ground and were not touched by this
amendment — but they are LISTED here, because naming a landing site and touching it are
different acts, and only the first is the ruling's job.**

⚠️⚠️ **THE LAST TWO ROWS WERE MISSING FROM THIS TABLE UNTIL REVIEW R1 (item R9), AND THAT
OMISSION WAS THE SINGLE ROOT CAUSE OF THE REVIEW'S B1–B4.** The adjudicator was built **after**
this ruling and inherited the **pre-ruling** branch text and power constants; a suite of 130
green tests did not catch it because the sweep tested the branch *label* and never the branch
*text*. A read-out generated in that state would have announced a **two-sided equivalence at
"90% confidence"** on a rule that mandates a one-sided 95% upper bound and explicitly forbids
the phrase — i.e. the run would have been **mis-adjudicated in its own read-out**.

⭐ **THE LESSON, RECORDED AS A STANDING RULE RATHER THAN AS AN APOLOGY:** a ruling's landing
table must enumerate **every surface that RESTATES the ruled quantity**, not only the surfaces
the ruling's author owns. **Ownership decides who edits; RESTATEMENT decides who is listed.** A
surface that is not listed is orphaned by construction — and an amendment that moves a
predicate while leaving its restatements behind is more dangerous than no amendment, because
the two now disagree and both look authoritative. *(This is the sibling of
[`DEVIATIONS.md`](../DEVIATIONS.md) D6.2 — "a pair may not name a pass without naming its tool"
— applied to amendments rather than to passes.)*

---

*No gate, no bar's magnitude, no `n`, no band and no knob moves. One branch's PREDICATE SHAPE
moves, on a pre-blind owner ruling, with the owner's own words on the record.*
