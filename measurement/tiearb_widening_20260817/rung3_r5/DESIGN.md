# RUNG 3 (`J > 4`) — SUCCESSOR PREREG, rev R5 (DESIGN DRAFT)

> **STATUS: DRAFT, NOT A PREREGISTRATION YET. NOT LAUNCHED. NOTHING RUN.** The mechanical
> `READ_RULE.md` is **deliberately not written yet** — see §R5-8: three of its bars are numbers
> that **do not exist until the counts-only calibration sweep runs**, and writing a bar before
> its calibration is exactly what killed R4's S2 stratum.
>
> **Naming, deliberately not `shared_run_r5/`:** this run is **rung 3 only**. Rung 2 is being
> answered by the R4 pair under the owner's Reading-A ruling, so calling the successor "shared"
> would misdescribe it. Cross-referenced from
> [`ADJUDICATION_R4_GATES.md`](../ADJUDICATION_R4_GATES.md) and
> [`PREREG_FAILURE_S2.md`](../PREREG_FAILURE_S2.md) so it is findable.
>
> **Parent chain, by reference:** R3.3 (`../shared_run/` @ `604edc83`) → R4.5 (`../shared_run_r4/`)
> → this. Every rung-3 estimand, branch condition, rider and power figure is **CARRIED**; §R5-7
> lists what changes. **Priority: launches after S1 scoring completes, earliest.**
>
> `governance/PRODUCTION.yaml` untouched. No claim minted. No strength row.

## R5-0. What this exists to fix

R4's S2 stratum voided on `G-DISJOINT`'s digest bound: **29 exclusions against a bound of 6**
([`PREREG_FAILURE_S2.md`](../PREREG_FAILURE_S2.md)). The corpus was **not short and not leaky** —
supply passed, every rid/root layer was zero. It was **degenerate in one measurable way**, and the
bound was **the wrong shape** to see it coming. This successor fixes the shape, the mining
predicate, the loop, and the drafting gap that made the void's scope arguable.

## R5-1. ⭐ (a) The scale-aware bound — and the honest limit of what two points support

**The finding to design against:** collision density is **not a constant of the generator**; it
grows with games mined.

| corpus | games `G` | density `d` |
|---|---|---|
| base calibration | 858 | 0.181% |
| S2 (governed scale) | 5,340 | 2.636% |

`G` grew **6.22×**; `d` grew **14.56×**. Pair-counting (collisions ∝ `G²`, positions ∝ `G`, so
`d ∝ G`) predicts **6.22×** — **the observed growth is 2.34× steeper than even the quadratic
model.** Fitting the two points gives `d ∝ G^1.46` (collisions `∝ G^2.46`).

⚠️ **That exponent is an illustration, NOT a fit.** Two points determine a line through two
points; they cannot distinguish `G^1.46` from a curve that bends. **The whole failure being fixed
here was a bound calibrated at one scale and applied at another — the fix must not repeat it with
one extra point.** So:

**R5-1.1 — REQUIRED PRE-RUN: a counts-only density sweep, ≥4 scales.** Re-mine the **already
generated** 5,340 games at `G ∈ {500, 1500, 3000, 5340}` and count collisions at each. No
generation, no scoring, no champ picks — **counts only**, the class
[`PREREG_FAILURE.md`](../PREREG_FAILURE.md) §3.3 established as non-leaking. Emits
`RUN/DENSITY_SWEEP.json`: per `G`, the positions mined, collisions found, density, and the
**collision-depth histogram** (§R5-2 needs it).

**R5-1.2 — the bound's FORM, fixed now; its VALUE, set from the sweep.** The bound is on the
**density at the governed scale**, not on a fraction of `n`:

```
bound(G_governed)  =  d_model(G_governed) x M
```

where `d_model` is fitted from the sweep and `M` is a **pre-committed multiple** of the modelled
density. `M` is the one number chosen before the sweep runs, and it is **committed in this DESIGN
before any `d` is fitted**: **`M = 3`.** *(Rationale: R4's bound sat at 2.8× the calibration
density and was defeated by a 14.6× scale shift, not by a 2.8× fluctuation. A multiple of the
**modelled** density absorbs ordinary Poisson noise — at the observed counts, 3× is ≈4–5σ — while
still failing a corpus whose degeneracy departs from the model, which is the event worth voiding
on.)*

**R5-1.3 — the saturation guard, which is the real bar.** A model-relative bound cannot catch a
corpus that is *uniformly* degenerate — if `d_model` itself is large, `3 × d_model` is a licence
to proceed on a corpus that is mostly transpositions. So, independently:

> **If `d_model(G_governed) > 5%`, the corpus design is VOID before it is built** — no bound
> applies, and the answer is a ply-floor (§R5-2) or fewer games, never a bigger bound.

The illustrative curve puts `d` at **6.6% by 10,000 games** and **18% by 20,000** — i.e. **the
5% guard binds not far above the scale R4 already reached.** Rung 3 cannot be bought by scaling
the corpus, and this clause says so before anyone tries.

## R5-2. ⭐ (b) The mining ply-floor — a new knob, and a first-class estimand change

**All 30 collisions, both strata, were at ply 2.** A `--min-ply k` predicate removes exactly the
region where boards are scarce and revisits are near-certain.

**R5-2.1 — the knob does not exist; the data for it does.** Verified: `run_census.py` has
`--max-per-game` and **no ply predicate**; `build_positions.py` carries `ply` on every row
(alongside `phase_bucket`, `tercile`) and **filters on none of them**. **W-item R5-W1:
`--min-ply` on `run_census.py` and `build_positions.py`**, recorded in `POSITIONS_PLAN.json` and
asserted by a gate. A new knob, not a new instrument.

**R5-2.2 — `k` is chosen FROM THE DATA, from a committed rule.** The prior from current evidence
is `k = 3` (it removes 100% of the 30 observed collisions). But `k = 3` is fitted to collisions at
**one** scale, and deeper plies will begin colliding as `G` grows — so the committed rule is:

> **`k` = the smallest ply floor such that `d_model(G_governed | ply ≥ k) ≤ 5%` AND the retained
> capped-ply supply still meets the floor in `FLOORS.json`** — both read off `DENSITY_SWEEP.json`'s
> depth histogram. If no `k` satisfies both, **rung 3 is not affordable by re-mining** and the
> successor stops rather than widening the bound.

**R5-2.3 — ⚠️ THE ESTIMAND CHANGES, and this is disclosed first-class, not in a footnote.**
With a ply-floor the measured population is **tied capped plies at ply ≥ `k`**, not *tied capped
plies*. The arbiter fires at ply 2 in real play; excluding those plies **excludes a real part of
its firing distribution**. Therefore, on **every** branch of the successor's read rule:

- the statistic is named **`Δ_ora(ply ≥ k)`**, never bare `Δ_ora`;
- **no result may be generalised to all tied plies**, and the pre-registered multipliers
  (1.400 legacy, 1.244 corrected) were derived on the **unfloored** population — so a comparison
  against them carries an explicit population-mismatch rider;
- the read-out reports **what fraction of capped plies the floor removed**, so the reader can see
  the size of the exclusion.

**R5-2.4 — the supply risk is real and must be measured, not assumed.** It is tempting to assume
ply-2 plies are rare among *capped* plies. The evidence points the other way: **29 of S2's
exclusions were capped ply-2 positions**, so ply 2 evidently produces capped plies in quantity —
plausibly because a near-empty board offers many symmetric placements of equal value, which is
exactly what makes a large tie set. **A ply-floor may therefore cost a large fraction of rung 3's
supply.** `DENSITY_SWEEP.json`'s histogram settles it before anything is priced.

## R5-3. (c) probe → carry, iterated to a fixed point

R4-0.2's loop ran **once** and pre-registered `residual = 0`, which
[`ADJUDICATION_R4_GATES.md`](../ADJUDICATION_R4_GATES.md) ruling 3 showed is **unreachable by
construction**: excluding rids admits positions the probe never saw, so a single pass leaves a
residual on a perfectly healthy corpus (it did, on both strata).

**The loop:** probe → gate → apply exclusions → re-probe → … until **`residual == 0`**, with
**`max_iterations = 5`**. Non-convergence at the cap is **fail-closed**: the stratum is **VOID**,
not "carried at iteration 5". The gate records `n_iterations` and the per-iteration exclusion
counts, and the bound of §R5-1.2 is evaluated on the **fixed point's cumulative total**.

## R5-4. (d) The 5,340 S2 games are RETAINED INPUT

**The same counts-only argument that let R4 retain band 135e9** ([`PREREG_FAILURE.md`](../PREREG_FAILURE.md)
§3): the S2 games were **never scored** — no `arb`, `ora`, `Δ` or CI exists for any position built
from them — and only structure counts were read. The **void attached to the R4 stratum and its
read rule, not to the games.**

⚠️ **This corrects a line in [`PREREG_FAILURE_S2.md`](../PREREG_FAILURE_S2.md) §5** ("the
extension band's S2 sub-range is spent; a successor claims fresh seeds"), which was over-strict
and is amended there. **What is spent is the R4 S2 *stratum* — the positions built under R4's
rule — not the substrate.** Re-mining the same games under a **ply-floor** produces a *different
position set* from the same games, which is the intended use and is not a re-read of anything.

**Conditions:** the retained games enter R5's gates **fresh and pre-cleared of nothing** — R4's
gate **failed**, so no position built from them ever passed anything; and `CORPUS_UNION.json`
(R4-0.5's shape) records origin commit, per-file sha256 and retained/fresh counts.

## R5-5. Cost — re-mining is census + positions only

| item | worker-h |
|---|---|
| density sweep + census over 5,340 games (counts only) | ≈2 |
| champ picks (`N` × 13.755 worker-s) | 2.7 – 4.2 |
| pricing, `M = 32`, per R4's per-capped-ply rate | 192.5 (`N`=700) – 302.5 (`N`=1,100) |
| **TOTAL** | **≈197 (`N`=700) – ≈309 (`N`=1,100)** |

**No generation.** R4 spent ≈**500 worker-h** generating those 5,340 games; retaining them is the
entire saving, and it is why the successor is cheap. ⚠️ **Contingency:** if §R5-2's ply-floor cuts
supply below the floor, generation returns to the bill at the R4-2.2 rates — and per §R5-2.2 the
correct response may be to stop rather than to buy more games, since §R5-1.3's guard tightens as
`G` grows.

## R5-6. ⭐ (e) The scope-marker taxonomy — so the per-stratum-void question cannot recur

R4's ambiguity existed because `G-DISJOINT` was **unmarked** and the binding taxonomy had no cell
for "one gate, per-stratum conjunct, one stratum void". Fixed prospectively and programme-wide:

> **Every gate row carries an explicit scope marker. An unmarked gate is a DRAFTING DEFECT that
> must be fixed before the blind commit — never adjudicated at read time.**

| marker | meaning | on a single-stratum failure |
|---|---|---|
| `[RUN]` | whole-run conjunct (cross-stratum quantities) | the **run** fails; no stratum is readable |
| `[S1]` / `[S2]` | evaluated on that stratum only | binds only the rungs whose cells live there |
| `[PER-STRATUM]` | evaluated separately per stratum | **that stratum** voids; the other **remains readable** — stated in the row, not inferred |

**A gate with conjuncts of mixed scope must be SPLIT into separately-named gates**, one per scope
— which is what `G-DISJOINT` should always have been: its cross-stratum conjuncts
(`strata_root_overlap`, `s1_vs_s2`) are `[RUN]`, its per-stratum bound is `[PER-STRATUM]`, and
mixing them in one row is what made the void's scope arguable. R5 has one stratum, so this costs
it nothing; it is written for the next multi-stratum prereg.

## R5-7. What is CARRIED unchanged

Rung 3's **estimand** (`Δ_ora`, `ora` adjudicates, `arb` rides) · the **branch table**
(`X-CONFIRMED` / `X-ABOVE` / `X-PARTIAL` / `X-BELOW` / `X-FREE` / `X-INCONCLUSIVE`, the `R_ora`
degenerate guard and its `Δ_ora`-only sub-table, `X-NOISE`) · the **power arithmetic**
(`sd_Δ ∈ [0.9, 1.4]`, the root bootstrap at 2,000 reps, significance on the percentile CI) ·
**all eight riders**, including **`I7-draw-scope`** · the `I6` amendment draft · `G-DRAW`,
`G-UNCAPPED`, `G-SALT`, `G-M`, `G-BACKEND`, `G-LEAF`, `G-CRN`, `G-PREFIX`, `G-BITEXACT@HEAD` ·
the `allow_null` closed list · fail-closed address discipline.

**`W9 (D-DRAW)` transfers here**, skipped in R4 as moot — so **`I7`'s dedupe-partition conditional
is still UNMEASURED and this successor inherits the obligation**, not a clean slate.

⚠️ Every carried statistic keeps its wording but acquires §R5-2.3's population qualifier: the
successor measures **ply ≥ `k`**.

## R5-8. Why the READ_RULE is not written yet

Three of its bars are numbers that do not exist: **`d_model` and the bound** (§R5-1.2, from the
sweep), **`k`** (§R5-2.2, from the depth histogram), and **`N_capped` / `FLOORS.json`** (from the
post-floor supply). **Writing them before the calibration is precisely the R4 failure.** Sequence:
`R5-W1` knob → density sweep (counts only) → fit → owner picks `N` → `FLOORS.json` →
**then** the mechanical READ_RULE → blind commit → run. The sweep is **counts-only and
outcome-free**, so it may run before the blind commit without spending blindness — the same
licence §R5-4 rests on.

## R5-9. Open for the owner

1. **Fund the successor at all?** ≈197–309 worker-h, no generation — but §R5-1.3's guard may
   VOID the design before it is built, and §R5-2.2 may find no affordable `k`. **Both outcomes are
   possible answers, and neither is a strength result.**
2. **Accept the estimand change** to *tied plies at ply ≥ k* (§R5-2.3), with the multipliers'
   population mismatch carried on every branch?
3. **Ratify `M = 3` and the 5% saturation guard** — committed here **before** any density is
   fitted, which is what makes them bars rather than accommodations.
