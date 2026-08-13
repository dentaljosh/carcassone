# AMENDMENT 1 to DEPLOY_PREREG.md — N4 is pointed at the wrong branch

**Status: RECORDED WHILE BLIND.** Written 2026-08-13 mid-run, after reading the interim
**cost** statistic only. **No strength number (margin, z, elo, W/D/L) has been read by anyone
at the time of writing**, and none is readable: the cell's `summary.json` is written at
completion, and the interim block summary carries no strength fields (verified: 0 occurrences
of `paired_mean_margin` / `paired_z`).

This amendment does **not** change any threshold, any branch condition, or the primary
statistic. It records a **mechanism error in N4's stated consequence**, so that the error is on
record before unblinding rather than discovered while writing up a result.

## 1. The measured cost (interim, n=128 of 800)

| framing | ratio |
|---|---|
| **house metric** — `champ_prefix` vs `rung` per-move, i.e. what `menu_block_summary` reports and what CL-080's 1.0110 is | **1.2148** |
| like-for-like, prefix vs prefix | 1.1942 |
| total vs total (candidate incl. solver) | 1.1952 |

Per-game mean 1.2347, 95% CI [1.202, 1.267]. **N4 as written FIRES** (house metric > 1.20).

⚠️ Interim and shared-tenancy: ratio only, never an absolute ms/move. To be reconfirmed at
close-out from the completed `summary.json` — this amendment is about N4's *logic*, and stands
regardless of where the final ratio lands.

## 2. The error

N4 says: if `ms_ratio` > 1.20 then **N1 (the loss branch) downgrades** from REFUTED to
"loss, confounded by budget", because *"time-vs-strategy is not separable at that point."*

**That reasoning does not hold for this design, and the direction is backwards.**

Both arms run **identical search**: `k_dets 8 × sims 1376 = 11008` on the candidate **and** the
opponent (manifest: `opp_sims 1376`, `opp_k_dets 8`; verified). The candidate is slower per move
because its **leaf is more expensive to evaluate** — it is **not** given less search. At fixed
sims, wall-clock is **not a strength variable**: an arm that takes 21% longer to compute the
same 11008 simulations plays exactly as well as it would if it were instant.

So a **loss at equal sims is a clean loss**, attributable to the term, not to time.

Where the cost genuinely bites is the **deployment** question this cell is named for. At equal
*wall-clock*, the 21% could have been spent on ~21% more simulations instead of on the term.
Therefore:

- **A LOSS (N1) is not confounded by cost — if anything the cost makes the refutation
  STRONGER.** At equal time the candidate would have had *fewer* sims than the champion, so it
  would lose by *more*. Cost cannot rescue a loss.
- **A WIN (N2) is where cost must be discounted.** A win at equal sims is only a *deployable*
  win if it exceeds what ~21% more simulations would have bought the champion. N2, not N1, is
  the branch that needs the caveat.

## 3. What is recorded (and what is NOT changed)

Nothing is silently overwritten. `DEPLOY_PREREG.md` §6 stands as committed. At close-out
**both readings are to be reported**, and the owner decides which governs:

- **N4-as-written:** house `ms_ratio` > 1.20 ⇒ N1 downgrades to "loss, confounded by budget";
  no CL-081 at Refuted.
- **N4-as-amended (this document):** N1 is **not** downgraded by cost, because equal-sims makes
  wall-clock strength-neutral; instead **N2 acquires a mandatory discount** — any positive must
  be compared against the ~21% -more-sims counterfactual before the word "deployable" is used.

**Default if the owner does not rule: the prereg as written governs (N4-as-written).** A
prereg's authority does not depend on its author later liking it, and the conservative reading
costs us a claim we might have been entitled to rather than granting one we were not.

## 4. Provenance — why this is not post-hoc rationalisation

- Written **before any strength number existed on disk**, and verifiably so (§ header).
- Motivated by a **mechanism** — identical `sims` on both arms, read off the manifest — not by
  a result.
- The amendment **cannot** help the pre-stated prior. §4 of the prereg pre-states a **loss**.
  N4-as-amended makes a loss count *more* against the term (a clean REFUTED instead of a
  hedged "confounded"). **This amendment argues against the hypothesis its author is testing**,
  which is the opposite of the direction post-hoc bias runs.
- The error is **mine**, introduced in the brief that generated the prereg, not the drafting
  agent's.

## 5. Consequence for the run

**None. The cell continues unchanged.** No threshold moved, no branch condition moved, the
primary statistic is untouched, and the sample is not being stopped early or extended. The
only thing that changes is what gets written down at close-out.
