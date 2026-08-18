# PLAN — rung (3) `J > 4` at capped plies

> **STATUS: PLAN ONLY, 2026-08-17. Not pre-registered, not funded to launch, nothing run.**
> Rung (3) of the tie-arbiter widening campaign
> ([roadmap](../../docs/PROGRAM_ROADMAP_2026-07-07.md), funded 2026-08-17). Queues behind
> the JCZ cells. A DESIGN + mechanical READ_RULE must be committed **before** any number is
> read — this is the pre-DESIGN scoping note, not the prereg.

## 1. Provenance of the "18%" and the "×1.40" — and what the extrapolation assumes

**The 18%** — `measurement/tiearb2_20260816/READOUT.md` §12, cut `capped_only`, **n = 244**
of 1,350 = **18.07%**; recomputed here from `positions_chunk*/ARMS.json` (`capped == true`):
**244 / 1350 = 0.1807**. Recurs family-wide — 18.1% / 18.7% / 19.4% / 20.1% across the
`tiletie_pricing_20260812` and `tiletie_oof_20260814` readouts.

**The ×1.40 is NOT from the tiearb runs.** Inherited verbatim, four documents deep, from
`measurement/tiletie_pricing_20260812/DESIGN.md` **§4.6**, quoted exactly:

> under the tied set's own estimated spread, `E[max of n draws] − mean = sigma_arm × a_n`
> with `a_2 = 0.56, a_4 = 1.03, a_8.55 ≈ 1.44`, so the **full-set ceiling is ≈ 1.40× the
> J=4 measured headroom**. The read-out reports both: `headroom_J4` (measured) and
> `headroom_fullset ≈ 1.40 × headroom_J4` (**an extrapolation through the S1a spread
> estimate, labelled as such — never quoted as a measurement**).

Pre-registered status: **yes, and honestly flagged.** §4.6 pre-registers it, applies §4.4's
branch thresholds to the *extrapolated* figure "so the cap cannot manufacture a closure",
and carries interpretation-rider **`I6-fullset-extrapolation-scope`** in every VERDICT since.
It is arithmetic `1.44 / 1.0294 = 1.399`.

### 1.1 Its assumptions — three stated, one NOT stated, and one that is materially wrong

| # | assumption | stated in §4.6? |
|---|---|---|
| A1 | arm values within a tied set are ~Gaussian with a common `sigma_arm` (so `a_n` applies) | implied by "the tied set's own estimated spread"; the S1a estimator is built for it |
| A2 | the scored arms are a **uniform seeded draw** from the tied set, so `sigma_arm` is unbiased at any `J ≥ 2` | **stated explicitly** (the S1a cap-invariance argument) |
| A3 | it is a **ceiling**, not a point estimate, and never a measurement | **stated, repeatedly** |
| A4 | the un-priced arms are **exchangeable** with the priced ones | **NOT stated as such** — it is entailed by A2 (uniform draw ⇒ exchangeable) but never named. It is the load-bearing assumption for this rung. |
| A5 | full-set size = **8.55** and priced size = **4**, *for every position* | stated as the inputs; **this is the wrong population — see below** |

⚠️ **The measured flaw (new, from this scoping pass — read-only recount of the spent corpus's
arm files: a COST statistic, no outcome value used).** `a_8.55` comes from the census's **raw**
tied-set sizes (`CENSUS.md` §2: mean 8.55, median 4, 17% are 13+). But the arbiter never prices
raw tie sets — `build_tie_arms` **dedupes by successor board first**, and the deduped
population is far smaller:

| statistic (Stage-1b corpus, n=1350) | value |
|---|---|
| `n_distinct_afterstates`, ALL positions | **mean 3.348**, median 3, max 12 |
| same, at **capped** plies (n=244) | **mean 6.99**, median 6, p90 10, max 12 |
| full-set arms at capped plies (`+ champ` when outside) | **mean 7.12**, median 6, max 13 |
| arms actually **priced** at capped plies | **mean 4.34** |
| `Ā` priced, all plies (matches Stage-2's 3.0022) / full-set at capped | **3.0022** / **3.5044** |

Re-running §4.6's **own** order-statistic machinery on the **deduped** sizes, per position,
same `a_n` convention (`a_4 = 1.0294`, `a_8 = 1.4236`):

- mean `a_priced` at capped plies = **1.0754**; mean `a_full` = **1.3374**
- ⇒ full-set ratio **at capped plies ≈ 1.244×**, not 1.40×
- ⇒ applied globally (capped plies are 18.07% of plies but carry 35.8% of the value, since
  `capped_only` arb_H +0.2851 vs pooled +0.1441) the global multiplier is **≈ 1.087×**, not 1.40×.

**So the owner's ~1.4× prior is very likely an over-statement, by construction, for two
compounding reasons: it uses raw rather than deduped set sizes, and it is applied globally
rather than only where the cap bit.** That does not make the rung uninteresting — it makes
it a *sharp* test of a pre-registered number, which is exactly what this rung is for. The
mechanistic correction (1.244 at capped plies) is computable a priori and must be
**pre-registered alongside 1.40** so the run can separate them.

## 2. The arm-selection rule when capped — a **seeded uniform draw**, not truncation

Both implementations agree and both assert it in tests. Python
`scripts/tiletie/build_positions.py::build_tie_arms` — dedupe by successor board → reference
arm = lowest-index survivor → remaining survivors capped by `rng.sample` → champion's own pick
appended if it reaches a distinct board. Rust `rust/carc/carc-core/src/tiearb.rs::build_arms`
(~L296-312) — identical, seeded `MT19937` shuffle-prefix over `candidates`; the doc comment
says it outright: *"The cap is a SEEDED DRAW over the deduped candidates — never index
truncation."* Unit test `the_cap_is_a_seeded_draw_and_is_deterministic` asserts across seeds
that the kept set **is not** the index prefix.

✅ **The arm-0 / selection-order side channel the Pixel bench refused is NOT present here.**
The draw is uniform-without-replacement over the deduped candidates — precisely what makes
A2/A4 hold and what makes the J=4 comparator a *free, exactly paired* sub-read of a full-set
run (§3). The corpus-time and runtime draws are deliberately **not** stream-identical across
languages (`tiearb.rs`, DESIGN §2.1); irrelevant here, since we compare a full set against its
**own** seeded subset within one run.

**Where `J ≤ 4` is enforced.** `tiearb.rs::build_arms`, the single block
`if candidates.len() > cap - 1 { … capped = true }`. `j` is already a threaded parameter, so
**un-capping is a call-site value change (`j = usize::MAX`), not a structural one** — the block
just never fires. LoC scope: **zero** lines inside `carc-core` for the offline study; the
offline instrument sets `--cap-j` (python, default 4). A *deploy* would additionally want a
`j`-by-condition policy at the call site. ⚠️ `rust/` is commit-frozen — **no edits made**.

⚠️ **`tiearb_partial_argmax_total` is NOT the cap counter.** Stage-2 READ_RULE §0.F/`G-PLY`:
it counts argmaxes taken over an **incomplete set of CRN worlds** (a broken pairing across
arms). Its 0-across-28,350-plies is a *pairing-integrity* pass and says nothing about `J`.
The cap witness is the per-ply `capped` boolean on `ArmSet`. **Any DESIGN for this rung must
emit a `tiearb_capped_total` counter — it does not exist today.**

## 3. Offline design — price the FULL tied set at capped plies

**Fresh corpus, fresh read-rule** (Stage-1b's is SPENT/BURNED; the recount in §1.1 uses only
arm-set *sizes*, never an outcome, and is declared here so the new prereg inherits no value).

1. Generate fresh champion self-play games on a **fresh band** (§7). Mine **all** exact-tie
   (`eps 0.0`) tile plies, not 4 probes/game — the enrichment lever (§4).
2. Build arms with **`--cap-j ∞`**, salt **`tiearb2-deploy-v1`**, recording per ply: the full
   deduped arm list, `n_distinct_afterstates`, `capped_at_4`, and the **exact J=4 seeded-draw
   subset** the deployed arbiter would have used.
3. Price every arm with **B = 16 CRN-paired tier1-greedy playouts to terminal**, rust,
   cross-fit argmax over world-mean — the deployed Stage-2 shape, unchanged.
4. ⭐ **The J=4 comparator is a FREE, EXACTLY-PAIRED SUB-READ.** The cap is a seeded draw
   computed *before* any playout, so restricting the argmax to that recorded subset over **the
   same CRN worlds** reproduces the deployed arbiter bit-for-bit. No second run, no second
   corpus, no cross-corpus contrast — within-position and CRN-shared, the lowest-variance
   class this programme has.

**Primary statistic.** §4.6's 1.40 is a claim about **`headroom` (`ora`)**, not `arb`. Both are
read; `ora` adjudicates.

- `R_ora = ora_full / ora_J4` at capped plies — **the pre-registered quantity**;
  `R_arb = arb_full / arb_J4` — the *deployable* quantity
- `Δ_ora`, `Δ_arb` — the paired per-ply differences (the powered statistics; ratios reported
  with CIs, but the bar is set on Δ)
- Both bracketed by two predictions frozen in the DESIGN before launch: **1.400** (legacy
  §4.6) and **1.244** (§1.1 correction on deduped sizes).

⚠️ **A downside risk to pre-register, not just an upside.** Widening the arm set widens the
**selection noise**: at fixed B = 16 the argmax over 7 noisy means is more winner's-cursed than
over 4. `Δ_arb < 0` with `Δ_ora > 0` is coherent — it would say *the value is there but B = 16
cannot reach it*, handing the finding to rung (2).

## 4. Power and corpus size

Stage-1b yields, recomputed from the corpus: **1,350 tied positions / 724 roots from 850
games** = 1.588 tied/game and **0.287 capped/game** — but that reflects a **4-probe-per-game**
subsample, not the supply. The true supply is Stage-2's realized firing rate
**`phi` = 17.57 tied tile plies/game**, so at full mining the yield is
**0.1807 × 17.57 ≈ 3.17 capped plies/game** — a **~11× enrichment** at zero extra generation.

Predicted paired increments (from Stage-1b's `capped_only` levels, `ora` +0.3455 / `arb` +0.2851):

| prediction | `Δ_ora` pts/capped ply | `Δ_arb` |
|---|---|---|
| legacy ×1.400 | **+0.1382** | +0.1140 |
| corrected ×1.244 | **+0.0842** | +0.0695 |
| cap-was-free ×1.00 | 0 | 0 |

`sd` of the **paired** difference is not measured anywhere and must be bracketed: it is
bounded above by the per-position level sd (**1.7197**, Stage-1b §11) and reduced by the
~61% of capped plies where the full-set argmax already lies inside the J=4 subset
(`1 − 2.779/7.123`), giving exact zeros. Bracket **sd_Δ ∈ [0.9, 1.4]**.

`N_capped` for a 2σ resolution of `Δ_ora`, `n = (2·sd/Δ)²`:

| | sd_Δ = 0.9 | sd_Δ = 1.4 |
|---|---|---|
| resolve the **legacy** +0.1382 | 170 | 410 |
| resolve the **corrected** +0.0842 | 457 | **1,106** |
| separate 1.40 **from** 1.244 (Δ = 0.054) | 1,111 | 2,690 ❌ |

⇒ **Target `N_capped` = 1,100** (floor 700). At 3.17 capped/game that is **≈ 350 games**;
with a per-root cap of **≤ 3 capped plies/game** to hold within-root clustering near
Stage-1b's (1.10 capped/root) and root-bootstrap SEs, budget **450–500 games**.

⚠️ **Honest power statement for the DESIGN:** this run **can** separate *cap-was-free* from
*either* prediction, and **can** confirm-or-refute 1.40 as a point; it **cannot** separate
1.40 from 1.244 at 2σ at any affordable size. The read-rule must say so up front, or a
result landing between them will be read as whichever the reader prefers.

## 5. Cost

Extra playouts = `capped plies × (full-set size − 4) × B × c_tier1_rust`; measured from the
corpus, **2.779 extra arms per capped ply** (678 over 244). `c_tier1_rust = 0.178232`
worker-s/playout — measured **at W30**, so already a *contended per-worker* figure.

| item | worker-h | W30 | W52 (local 30 + laptop 22) |
|---|---|---|---|
| generation, 450 games @ 586 worker-s/game | 73.3 | 41 min | **24 min** |
| `champ_picks` @ 1.409 worker-s/pos (~7,900 pos) | 3.1 | 6 min | 4 min |
| **extra** full-set playouts only, N=1,100, B=16 | **1.5** | 3 min | 2 min |
| full-set pricing at capped plies, N=1,100, B=16 | 6.2 | 12 min | 7 min |
| **J>4 rung, standalone total** | **≈ 83** | **≈ 2.8 h** | **≈ 1.6 h** |

**Two currencies, per Stage-2 §0.G — never conflate them.** *Sequential* `rho_wall`: widening
multiplies the per-fired-ply arbiter cost by `Ā_full / Ā_J4 = 3.5044 / 3.0022 = 1.167×`, so
`rho_wall(16)` 0.6224 → **≈ 0.727**. *Realized contended*: Stage-2 measured the deployed
`ms_ratio` at **2.42 / 2.33**, ~2× the predicted 1.1985, because the model divided by a
sequential `t_champ` and the cell divides by a contended ~1.7 s/move. Every "×
champion-per-move-wall" figure in this plan is in the **contended** currency (§7); the offline
pricing above is unaffected (worker-h, `c` measured contended).

## 6. Gates and branches (skeleton for the mechanical READ_RULE)

Pre-launch aborts, inherited: `G-DISJOINT` (root/rid/digest vs **both** spent tiearb corpora),
`G-LEAF` (`a36d2e15a3b3d71d`), `G-REPRO`, `G-GEN`, `G-BAND` (fresh, §7).
New, this rung: **`G-CAP`** — the recorded J=4 subset must reproduce the deployed seeded draw
for every ply (assert against `build_arms` at `j=4`, same salt/digest/ply), else the
comparator is not the deployed arbiter and the cell is void. **`G-ARMS`** — every full-set arm
scored on all B worlds (the `partial_argmax` analogue, per-arm not per-ply).

| branch | condition on `Δ_ora` (capped plies, root-bootstrap CI) | reading |
|---|---|---|
| **`X-CONFIRMED`** | `Δ_ora > 0` at 2σ **and** 1.400 inside the 95% CI of `R_ora` | the pre-registered full-set extrapolation **holds**; the cap left ~1.4× on the table at capped plies. Licenses a DESIGN for a `J`-widened deploy shape — nothing more. |
| **`X-PARTIAL`** | `Δ_ora > 0` at 2σ, 1.400 **outside** CI, 1.244 inside or below it | value exists but **below** the legacy prediction — the §1.1 dedupe correction is vindicated. Report the corrected multiplier as the number of record and **amend `I6` programme-wide**, since every VERDICT since 2026-08-12 carries the 1.40 rider. |
| **`X-FREE`** | `Δ_ora` CI contains 0 **and** excludes +0.0842 | **the cap was free.** J=4 is not a compromise; retire the rung and strike the ×1.40 extrapolation from the bound chain (it cancels out of `F`, so no prior verdict moves). |
| **`X-INCONCLUSIVE`** | neither | underpowered; report, do not adjudicate, do not top up without a fresh read-rule. |
| **`X-NOISE`** (rider, non-adjudicating) | `Δ_arb < 0` while `Δ_ora > 0` | value is reachable only at higher B ⇒ **hand to rung (2)**; a `J`-widened deploy at B=16 would *lose*. |

Nothing here touches `PRODUCTION.yaml`, a claim id, a band promotion, or the pending
production-flip decision on the measured B=16 / J≤4 shape.

## 7. Deploy note — what a confirmed rung would cost in play

Production shape would become **`J = full` at capped plies only** (`J = 4` elsewhere; the cap
never bites on the other 82%). `phi_capped = 0.1807 × phi = 0.1807 × 17.57 ≈ **3.18 capped
plies/game**.

Per-fired-ply arbiter cost `Ā × B × c` rises `3.0022 → 3.5044` arms = **+16.7%** (8.561 →
9.993 worker-s predicted; scaling Stage-2's realized +11.8% numerator error, 9.57 → **11.17**).
Through §0.G's own reconciliation `1 + (9.57 × phi / 72) / 1.7`, the contended in-cell
`ms_ratio` moves **2.37 → 2.60** predicted, i.e. realized **≈ 2.42 → ≈ 2.66×** the champion's
per-move wall — **+9.7% on total per-move wall**. Affordable under the owner's cost ruling, but
it must be **stated at the flip decision in the contended currency** — the lesson of §0.G.

**Fresh band:** ~~`133000000000`~~ **ORCHESTRATOR CORRECTION 2026-08-18: `133000000000`
was claimed by the JCZ out-of-lineage cells minutes before this plan landed** (registry read
raced the claim commit `a8b6cf87`). Reserve **`134000000000`** for this rung — or, if §8 is
adopted, for the **shared** widening instrument run, with the top-up range reserved up front
(the D1 row's close-out lesson). Re-read `BAND_REGISTRY.csv` at claim time regardless.

## 8. ⭐ Interaction with rung (2) `B > 16` — ONE paid run, two disjoint pre-regs

**Answer: yes, and it is close to free — this rung should ride rung (2)'s instrument run.**
Rung (2) needs a fresh **M = 64** run because the banked CRN records stop at 16 worlds. Built
with **`--cap-j ∞`** and recording the seeded J=4 subset per ply, one paid corpus serves both
pre-regs on **disjoint statistics**:

| | reads | over |
|---|---|---|
| rung (2) `B>16` | `arb` at B ∈ {16, 32, 64} on the **J=4 seeded subset** | **all** tied plies |
| rung (3) `J>4` | `arb`/`ora`, **full-set vs J=4 subset**, at **B = 16** | **capped** plies only |

They share the corpus and the CRN worlds but not a statistic and not a bar. The extra cost of
carrying rung (3) is only the un-capped arms: at 7,900 tied plies, `Ā` 3.0022 → 3.5044 is
**+16.7% of pricing**, i.e. **≈ +13 worker-h** on a shared run of ≈ 88 worker-h pricing
(7,900 plies × 3.5044 arms × 64 worlds × 0.178232 ≈ 88 worker-h; ≈ **2.9 h at W30**,
**≈ 1.7 h at W52**). Whole shared run incl. generation ≈ **165 worker-h ≈ 3.2 h wall at W52**.

**Requirements on the shared instrument — hand these to the rung-(2) planner:** (1) `--cap-j ∞`
at build, **recording the full deduped arm list** per ply; (2) record `salt`, `state_digest`,
`ply` **and** the materialised J=4 subset, so either planner can reconstruct the deployed arm
set exactly (`G-CAP`); (3) record `n_distinct_afterstates`, `capped_at_4`,
`champ_outside_tieset`; (4) emit **`tiearb_capped_total`** (does not exist today, §2);
(5) ⭐ CRN worlds **shared across all full-set arms**, not just the J=4 subset — otherwise the
paired contrast breaks and rung (3) gets nothing from the run; (6) both pre-regs committed
**before** the run, neither reading the other's statistic. The 2-D cell (full-set × B=64) is a
**rider on both, adjudicating for neither** — it answers the §3 selection-noise risk, the most
interesting thing the joint run can produce.

⚠️ If rung (2) declines requirement (5), this rung needs its own run (§5: ≈ 83 worker-h) and
the campaign pays roughly twice.

## 9. Open questions for the owner

1. **The ×1.40 looks wrong before we spend anything (§1.1) — do you still want the rung?** The
   correction on *deduped* arm sets says ≈ 1.24× at capped plies, ≈ 1.09× globally. Still worth
   running (it converts a 4-document-deep inherited extrapolation into a measurement, and `I6`
   rides on every VERDICT since 2026-08-12), but the honest prize is **~+0.08 pts/capped ply**,
   not ~1.4× of anything.
2. **Share the run with rung (2)?** ~13 worker-h vs ~83, plus the interaction cell free; costs
   strict prereg discipline across two planners on one corpus. Recommend **share**.
3. **`ora` or `arb` as the adjudicating statistic?** Recommend `ora` (faithful to §4.6's
   prediction), with `arb` as the deploy rider.
4. **Per-root mining depth** — full mining is ~11× enrichment but ~3× the within-root
   clustering. Recommend ≤3 capped plies/game with root-bootstrap SEs.
5. **Band `134000000000`** (corrected — 133e9 is the JCZ cells') for the (shared?) run,
   top-up range reserved up front — confirm.
6. If `X-PARTIAL` fires, **`I6` must be amended programme-wide** (touches historical VERDICTs;
   the multiplier cancels out of `F`, so no verdict *moves*) — approve in advance?
