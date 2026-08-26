# DEVIATIONS — evloss autopsy R2 (taxonomy)

**Scope.** Deviations of the R2 taxonomy read from its binding prereg
(`scratchpad/evloss_autopsy/run/PLAN.md` §5/§7 + `SCOPE.md` §4/§6/§8). The R0/R1
deviation record (`run/DEVIATIONS.md`, D-L0 / D-L1) is an R1 artifact and is **not
modified** — hence the separate D-R2 series here (D-R2-0).

**Blind-order discipline.** Every entry below was written and committed **before any
per-category outcome number was computed**; the commit hash of that commit is the blind
stamp recorded in `R2_READOUT.json`. Nothing here is a statistic.

**PLAN.md is untouched.** The bars (`+0.5` pts/ply, 2σ cluster-robust, Holm, the
permutation control, the four funding conditions, the reach ceiling, the no-bucket-gated-
deployment fence) are unchanged by everything on this page.

---

## D-R2-0 — R2 deviations live in their own file

The task constraint is *never modify R0/R1 artifacts*. `run/DEVIATIONS.md` is the R0/R1
execution record and is left byte-identical. R2's series continues the same house format
and numbering convention (`D-<leg>-<n>`) in this file.

## D-R2-1 — the K count: PLAN's headline "24" vs its own axis table

PLAN.md §5 says *"K = 24 buckets over 7 axes"*; SCOPE.md §6 says *"K = 24 … across 6
axes"*. **Neither headline reconciles with the literal enumeration of its own table**, and
the two tables differ from each other (SCOPE lists contest shape as 3 buckets, PLAN's
⚠️ note corrects them to the 6 real `*_{best,played}` field names; SCOPE has no F7 row,
PLAN adds it as the 7th axis at 2 buckets).

**Resolution:** the axis table is binding, the headline integer is not. The classifier
enumerates the table literally with PLAN's ⚠️-corrected real field names, giving **26**
pre-registered buckets, and the readout reports the realized count. Holm runs across the
**estimable family** (D-R2-6), whose size is reported, not across a nominal 24.

Nothing about the bars or the read rule depends on the integer.

## D-R2-2 — the label-permutation null is permuted by GAME BLOCK, not within game

SCOPE §6 control 3 pre-registers *"permute bucket labels within game, 10,000×"*. At the
pre-registered **cap of 2 scored positions per game** (PLAN §2), the realized design is
498 games / 800 positions — so roughly 200 games contribute a single position and a
within-game permutation **cannot move its label at all**. The literal null is therefore
near-degenerate by construction of the sampling design, not by choice.

**Resolution:** the primary null permutes whole **game label-blocks** among games of equal
block size — a label permutation that preserves the cluster structure exactly (blocks stay
intact, sizes match) while actually breaking the label↔outcome link. The **literal
within-game variant is computed and reported beside it**, so the reader can see both.

The permuted statistic is the **bucket-vs-complement contrast z** (`contrast_cluster`),
because that is the quantity a label permutation prices: under the null the bucket mean is
drawn from the same population as its complement. `max_b z_b` against the `+0.5` bar is
reported under the same null as a secondary, since it is the literal reading of
"max_b |z_b|".

## D-R2-3 — H2/H4 enter as pre-registered CONJUNCTIONS, not as ported Stage-B predicates

The owner's H2/H4 are pre-registered in
`measurement/e4_owner_exploit_hypotheses_20260825.md` and were read out on the **E4**
corpus by `e4_exploit_grading_20260825/` (Stage A: H2 and H4 both CONFIRMED; H2+H4 shown
to be one mechanism via farm invasions).

Their **Stage-B ply predicates cannot be ported** to this corpus: `select_h2` needs a
whole-game **contest-onset census** (invader/incumbent roles, `n_tiles_at_contest`, merge
mechanism) and `select_h4` needs **farm-majority-switch windows** — both produced by
`stage_a_census.py`, which consumes **E4 archive JSON**, not the self-play corpus + subject
rows this autopsy banked. Rebuilding that census over 600 walled self-play games is a
separate instrument, not an analysis of the banked corpus, and would add compute to a leg
that is funded as an analysis.

**Resolution — explicitly pre-authorized, not invented:** SCOPE §6 states *"Named-but-not-
in-the-list hypotheses (farm timing, feature abandonment, opponent-blocking) are
expressible as **conjunctions of the above** and are declared as such in `PREREG.json`
*before* the run."* H2 **is** opponent-blocking and H4 **is** farm timing. They are declared
in `R2_PREREG.md` §4 as conjunctions of the same tested `autopsy_extract` covariates the
rest of the taxonomy uses, anchored on the two majority flags whose docstrings already
name the mechanism: **F2 `tie_force_join`** (*"NEWLY CONNECTS into a structure where the
opponent holds SOLE majority — the late majority-steal move class"*) and **F9
`reinforce_losing_contest`**.

**Named limitation** (also stated in the prereg, before the run): the two flags are
scalars, not per-feature-kind, so `H2xH4_FARM_STEAL` conjoins a scalar steal flag with a
per-kind contested set and is **indicative, not a clean intersection**. And this corpus is
**champion-vs-champion self-play** — it can show whether the *class of position* carries
oracle headroom; it cannot reproduce the owner's realized exploit, which is an
opponent-conditional behaviour.

## D-R2-4 — funding condition F4 (the `tier1-greedy` sign check) is NOT computable here

SCOPE §8 requires four conjunctive conditions to fund a term attempt; the fourth is
out-of-family **`tier1-greedy` sign agreement**. PLAN.md §6 already records that
`tier1-greedy` *"is python-only by construction, and is **R2's** sign check"* — but **no
such judge leg exists in the banked corpus**: R1 ran five legs (leaf / sib2 / sib3 / sib4 /
rnd), all `clair-puct`.

**Resolution:** F4 is reported as **NOT COMPUTABLE** rather than silently dropped or
silently passed, and the verdict vocabulary carries the debt explicitly: the best available
verdict is **`FUNNEL-OPEN-PENDING-SIGN`**, whose stated consequence names the owed
measurement (one python-only clair-marginalized `tier1-greedy` leg over the same rids).
**No term dollar is licensed by an F4-pending verdict.** The leaf-computable-predicate half
of F4 is satisfied by every pre-registered bucket by construction — all are functions of
the leaf's own inputs at the ply, never of the future or of the oracle's answer.

## D-R2-5 — the primary per-category z is against the +0.5 bar, not against 0

SCOPE §8 condition 1 reads *"`R̄_champ` significantly > 0"*. R1's pooled read is **z ≈ 20.8
against 0**, so a per-category z against 0 separates nothing: the taxonomy's job is to say
where the headroom is *reachable*, and the reachability bar this program already wrote down
is `+0.5` pts/ply (PLAN §7 `B-CEILING`; `everyply`'s re-open bar).

**Resolution:** `z_vs_bar = (R̄_champ − 0.5)/se` is the primary and carries the Holm
correction; `z_vs_0` is reported beside it and still gates F1's star cell (which needs
`z_vs_0 ≥ 2` **and** `z_G < 2`). This tightens the read; it does not loosen it.

## D-R2-6 — buckets with `n_games < 2` are excluded from the multiplicity family

`cluster_sandwich` returns `NaN` at fewer than 2 clusters — such a bucket has no
cluster-robust SE and therefore no z, no p, and nothing for Holm or the permutation null to
price. Excluding it is mechanical, **outcome-blind** (`n` and `n_games` are covariate-only
quantities, fixed by the classifier before any judged value is touched), and the excluded
set is reported with counts and reasons rather than dropped silently. Every such bucket
still appears in the per-category table with its `n`.

## D-R2-7 — two axes are not partitions, and the readout says so

- **`move_kind`** — the real fields are `move_kind_{best,played}`; the axis is read on
  `move_kind_played` and its five buckets partition the **meeple subset only** (tile plies
  carry `move_kind_played == "tile"`, outside the axis). The recombination check for this
  axis is run against the meeple-subset mean, not the pooled mean.
- **`commit_direction`** — PLAN names two buckets (`spend`, `hold`) but the field realizes
  four values (`n/a` on tile plies, plus `swap` and `both_pass` on meeple plies), so
  `spend ∪ hold` covers only part of the corpus. It is reported as a non-partition axis
  and is excluded from the recombination check. `commit_direction = spend` remains
  **PRE-DECLARED WEAK** and cannot fund a term at any z (PLAN §5, SCOPE §6); the funnel
  gate excludes it by construction.
