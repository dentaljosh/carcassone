# G2 transformer control — read-out (2026-08-03)

> **STATUS: ✅ CLOSED 2026-08-03 — pre-registered verdict = `C_GRAY`.** The headline
> arm `g2_tf_match_best` reads solver regret **1.9830 vs the champion leaf's 0.9508**,
> paired sign-z **−19.30**, τ **0.0082 ± 0.0051** vs the leaf's **0.6153 ± 0.0121** —
> i.e. the same ~2× regret / ~30× τ gap every ResNet arm shows. **But it does NOT fire
> Branch A**, because all three arms failed the pre-registered *did-it-fit* gate
> (§4.2): trained from random init for 16 corpus passes, no architecture reached even
> **r = 0.55** held-out value↔outcome correlation (best-ever epochs: 0.4227 / 0.4370 /
> 0.4169). A failed-fit arm's poor ruler score is not evidence that the dissociation
> generalises — the pre-registration says so, and it was written before any of this
> was known.
>
> **The pre-registration ([PREREG.md](PREREG.md)) was committed in `ffd9319`, before
> the first training step**; the artifacts commit follows it. Design rationale:
> [DESIGN_MEMO.md](DESIGN_MEMO.md). Ops: [RUNBOOK.md](RUNBOOK.md).

**Scope, stated up front and binding on every number here.** This is an **offline**
architecture control for paper P1's gap G2. It trains three nets from random init on
one corpus at one budget with one seed each, and scores their **bare value heads** as
per-child rankers against an exact endgame solver on 1,119 K=2 roots. **No online
experiment, no blend, no search experiment, no game eval, no `governance/PRODUCTION.yaml`
touch, no `experiments/results.csv` row.** Offline sibling regret is not online search
value. Nothing here promotes anything.

---

## 1. What was asked

Every learner in P1's closure ladder is a conv-ResNet, MLP, GBDT or ridge regression.
CL-064 shows capacity is not the binding constraint *within* ResNets; nothing in the
kill set tests architecture *class*. The pre-registered question: **does the
prediction/discrimination dissociation hold for a transformer trunk at matched
parameters and matched corpus passes?**

Two-sided by construction — Branch A (it holds) closes the gap; **Branch B (the
transformer discriminates) would make the whole learned-value kill set
architecture-scoped and reopen structural blocker #2.**

## 2. What ran

Three arms, random init, the frozen `value_unlock_v1` recipe (corpus
`distill_strong_20260723` iter_00..03, fingerprint `6b362781945b33f3`; by-game split
2,280/120 files = 328,077/17,256 rows; AdamW lr 3e-4 cosine, wd 1e-4, effective batch
256, `pol_CE + 5.0·value_MSE + 0·ownership`, seed 0), **16 corpus passes** = the
baseline's cumulative lineage budget (4 iters × 3 epochs + 4 refine):

| arm | trunk | params | ×baseline | GPU-s | min/epoch |
|---|---|---|---|---|---|
| `resnet_scratch` | 6 ResBlocks × 96 | 7,509,167 | 1.000 | 2,391 | 2.5 |
| `tf_match` | 6 pre-LN blocks, d128, 8 heads, FF×4 | 7,731,599 | 1.030 | 5,457 | 5.7 |
| `tf_large` | 12 pre-LN blocks, d384, 8 heads, FF×4 | 28,062,863 | 3.738 | 31,528 | 32.8 |

≈ 10.9 GPU-hours total. Ruler: `solver_score.py --max-k 2`, **scored = 1119, skipped =
0, errors = 0**, ten rankers on the same solves, each G2 arm at **both** its
best-held-out-value-MSE epoch and its final epoch (both scored in one pass, so no
checkpoint was chosen after seeing the ruler).

**Instrument-integrity gate (§4.3): PASSED.** `v29_leaf` and `curve125` both reproduce
regret **0.9508** / top-1 **0.6095** / τ **0.6153** to four decimals — the fourth
independent reproduction (2026-07-03, 07-23, 07-30, 08-03). Continuity double-check:
`iter_03` vs `value_unlock_v1` picked-child agreement reads **0.277**, matching the
published 27.7% exactly. The instrument is the same instrument.

## 3. The verdict — `C_GRAY`, and why the honest answer is not Branch A

### 3.1 Every arm reproduces the dissociation *pattern* — and none of them fit

| arm | regret ↓ | top-1 ↑ | τ ↑ | sign-z vs `curve125` | held-out r (final / best) |
|---|---|---|---|---|---|
| **`curve125`** (the champion's leaf — the baseline) | **0.9508** | **0.6095** | **0.6153 ± 0.0121** | — | ≈0.61 reference |
| `iter_03` (CL-067 warm parent) | 2.0000 | 0.0688 | 0.0177 | −18.08 | 0.6564 |
| `value_unlock_v1` (published CL-073 ResNet) | 1.9946 | 0.0670 | 0.0190 | −17.43 | 0.6795 |
| `g2_resnet_scratch_best` | 2.0054 | 0.0572 | 0.0111 | −18.55 | 0.2303 / 0.4227 |
| `g2_resnet_scratch_final` | 2.0357 | 0.0652 | 0.0117 | −18.19 | 0.2303 |
| **`g2_tf_match_best`** (**headline**) | **1.9830** | **0.0474** | **0.0082 ± 0.0051** | **−19.30** | 0.3698 / **0.4370** |
| `g2_tf_match_final` | 1.9750 | 0.0465 | 0.0038 | −18.64 | 0.3698 |
| `g2_tf_large_best` | 1.9955 | 0.0465 | 0.0047 | −19.08 | 0.3834 / 0.4169 |
| `g2_tf_large_final` | 1.9142 | 0.0590 | 0.0105 | −18.01 | 0.3834 |

Every G2 arm loses to the leaf by ~2× in regret, ~10× at top-1 and ~60–150× at τ, at
paired sign-z −18 to −19.3, and every one of them is **statistically indistinguishable
from the published warm-started nets** (paired vs `value_unlock_v1`: sign-z −1.86,
−1.88, −1.81, −0.25, −1.42, −1.33 — all |z| < 2). Δτ vs the leaf is −0.60 at
dτ-z −47 to −49 for all six.

**But the §4.2 did-it-fit gate failed for all three arms**, and it failed on the
outcome-prediction leg specifically:

| arm | train MSE halved? | held-out r ≥ 0.55? | entropy ≥ 0.8002? | **VALID CONTROL** |
|---|---|---|---|---|
| `resnet_scratch` | ✅ (0.4709 → 0.0279) | ❌ 0.2303 (best 0.4227) | ✅ 1.6047 | ❌ |
| `tf_match` | ❌ (0.4505 → 0.3406) | ❌ 0.3698 (best 0.4370) | ✅ 1.6349 | ❌ |
| `tf_large` | ❌ (0.4486 → 0.3560) | ❌ 0.3834 (best 0.4169) | ✅ 1.6865 | ❌ |

The r-gate fails **on either reading** — final-epoch r (0.23 / 0.37 / 0.38) or
best-ever-epoch r (0.4227 / 0.4370 / 0.4169) — so the outcome does not hinge on which
epoch's diagnostic is used. Convergence (§4.1) *passed* for all three: the final
quarter of training improved nothing on held-out value MSE (relative improvement
−0.261 / −0.073 / −0.032, i.e. it got *worse*) or on held-out policy CE. These are
plateaued runs, not truncated ones; the extension rule was therefore not triggered.

**So the pre-registered branch is `C_GRAY`, not Branch A.** Branch A requires held-out
r ≥ 0.61 *and* a valid control. Neither holds. Per PREREG §5 the outcome is: report
the point estimates and intervals, record that the control ran, **no promotion, no
claim change** beyond OUTLINE §9.3 naming the control and its inconclusive form. That
is what is being reported.

This is the pre-registration doing its job in the direction that costs us something.
The tempting write-up — "we ran a transformer, it also failed, the claim generalises" —
is exactly the sentence §4.2 was written to forbid, because a net that never learned
the task cannot testify about what a net that *has* learned the task would do at
ranking.

### 3.2 The pre-declared architecture contrast: indistinguishable

`g2_tf_match_best` vs `g2_resnet_scratch_best`, paired on the same 1,119 roots:
**173 better / 191 worse / 755 tie, sign-z −0.943, mean Δregret −0.0223.** The bar for
calling any architecture difference real was |z| ≥ 2. **Not met — at matched
parameters, matched corpus passes and matched heads, the transformer and the conv-ResNet
are indistinguishable on this ruler.** The 3.74× capacity leg is likewise flat
(`g2_tf_large_best` vs `g2_resnet_scratch_best`: sign-z −0.158).

## 4. The thing worth more than the verdict — **the warm start was load-bearing for outcome prediction itself**

The crisp new fact, and it was not what the experiment was designed to find:

> **Without the warm start, no architecture — 7.5M ResNet, 7.7M transformer, or 28M
> transformer — reaches even r = 0.55 outcome competence in 16 corpus passes, while the
> warm-started lineage nets on the identical corpus and split read r = 0.6564
> (`iter_03`) and 0.6795 (`value_unlock_v1`).**

The 16 passes are not the explanation: all three arms had *plateaued* (§4.1) and two of
them peaked at epoch 2 and epoch 6 and then decayed. What the arms did instead splits
by architecture, and the split is itself informative:

- **`resnet_scratch` memorised.** Train value MSE fell 0.4709 → **0.0279** (17×) while
  held-out MSE *rose* 0.4344 → 0.5405 — a 19× train/val gap, with held-out r decaying
  monotonically 0.4227 (epoch 2) → 0.2303 (epoch 16).
- **Both transformers barely fit at all.** Train MSE fell only 0.4505 → 0.3406 and
  0.4486 → 0.3560 (24% and 21%), with held-out MSE nearly flat. They did not overfit;
  they underfit, and more capacity (3.74×) did not change that.

Both failure modes land in the same place on held-out r, and this is the shape CL-066's
mechanism probe predicted: **the value head's effective sample size is *games*, not
positions.** 2,280 training files = 2,280 independent outcome labels supporting
328,077 rows. The ResNet spent its capacity memorising those ~2,280 labels; the
transformers, lacking the convnet's locality prior, could not even do that within
budget. Warm-starting from CL-067 `iter_03` supplied what 16 passes of outcome
regression on this corpus cannot.

⚠️ **This is a datum about learnability, NOT a rescue of the learned-value route.**
Discrimination stayed ~30× worse than the leaf in *every* arm regardless — including
the two warm-started nets that *do* clear r ≥ 0.61. Outcome competence and sibling
discrimination continue to move independently; this run adds that outcome competence
itself is warm-start-dependent at this data scale.

### 4.1 The heads still disagree with each other about the move

Picked-child agreement on the 1,119 roots (the READOUT §4.3(b) statistic):

- each G2 arm vs `curve125`: **6.3 – 7.9%**
- G2 arms vs each other (across architecture classes): **4.1 – 8.3%**
- `g2_tf_match_best` vs `g2_tf_match_final` (same net, 10 epochs apart): **20.5%**
- for reference, `iter_03` vs `value_unlock_v1`: 27.7%

Six value heads spanning two architecture classes and a 3.7× capacity range agree with
each other on the chosen move at near-chance rates while all scoring ~1.0 points/root
worse than the leaf. That is the READOUT §4.3(b) reading reproduced across architecture
class: not several imperfect orderings, but noise around a common position-level signal.

## 5. What this does and does not buy the paper

**Buys:** the referee objection "you only tested convnets" is answered **in the gray
form**, and the answer is honest. A transformer at matched parameters, matched corpus
passes and identical heads — with a strictly larger receptive field, which favours it —
lands on the ruler exactly where the ResNets land, indistinguishable from them at
sign-z −0.94, and a 3.74× capacity leg does not move it. **No tested architecture
escapes.**

**Does not buy:** a *generalisation* claim for the dissociation. The dissociation is
"improves at outcome prediction while losing discrimination"; these arms never got the
first half, so they cannot demonstrate the pair. That statement stays scoped to the
architectures that *did* achieve outcome competence — the conv-ResNet lineage.

**Consequence for OUTLINE §9.3 and CLAIMS_LEDGER G2:** G2 closes as `C_GRAY`. §9.3
should say the modern-architecture control was **run** and returned *no architecture
advantage on the ruler*, while stating plainly that no from-scratch arm cleared the
outcome-prediction gate, so architecture-generalisation of the *dissociation* remains
formally unresolved. **Branch B did not fire; no strength-program flag is raised.**

**The cheapest experiment that would resolve it**, recorded but *not* run and *not*
requested: warm-start a transformer from a net that already has outcome competence.
That is impossible across architecture classes by weight copying, so it needs either
(a) distillation of `iter_03`'s value head into the transformer as a pre-training
stage, or (b) many more corpus passes / a larger corpus so a from-scratch arm clears
r ≥ 0.55 on its own. Both are new funding decisions for Joshua, and neither is implied
by anything here.

## 6. Honest scope

1. **16 corpus passes, one budget.** Chosen before the fact as the baseline's cumulative
   lineage budget. All three arms plateaued within it (§4.1), so the failure is not a
   truncation artifact — but "plateaued at this budget on this corpus" is not "cannot
   be trained"; a larger corpus or a longer schedule is untested.
2. **One corpus.** `distill_strong_20260723` iter_00..03 — 2,400 games / 345,333 rows,
   with G3's finding attached: the outcome label is *exactly* constant within a game and
   the corpus contains no sibling sets at all. Both architectures faced that identically.
3. **One seed per arm.** CL-064's own caution applies with force — its seed spread
   exceeded its size effect. Nothing here rests on a small between-arm difference; the
   only differences claimed are (a) each arm vs the leaf, at |z| ≥ 18, and (b) the
   *absence* of an architecture difference, which is a null and is reported as one.
4. **All 1,119 roots are K=2 endgames.** Midgame discrimination is untested by this
   instrument (limitation E5, inherited unchanged).
5. **Offline regret ≠ online search value** (READOUT §4.4 of the CL-073 chain, inherited).
6. **bf16 autocast with fp32 master weights and fp32 validation**, applied uniformly to
   all three arms — a change from the published fp32 baseline, applied equally, logged
   per arm. `tf_large` used gradient accumulation (micro 64 × 4); its optimizer batch
   and step count are identical to the others', but its BatchNorm head statistics are
   computed over 64-row micro-batches rather than 256.
7. **The r-gate reading.** `analyze_g2.py` applies §4.2 using each arm's *final-epoch*
   correlation while the primary checkpoint is *best-val-MSE*. Recorded because it is a
   real seam — but the gate fails under both readings (best-ever r = 0.4227 / 0.4370 /
   0.4169, all below 0.55), so the verdict does not turn on it.

## 7. Files

| path | what |
|---|---|
| [PREREG.md](PREREG.md) | the bars, committed in `ffd9319` before the first training step |
| [DESIGN_MEMO.md](DESIGN_MEMO.md) | parity accounting, tokenisation rationale, the receptive-field asymmetry |
| [RUNBOOK.md](RUNBOOK.md) | ops / resumption |
| `solver_score_g2.json` | the ruler pass (1,119 roots × 10 rankers, checkpoint sha256s) |
| `VERDICT.json` | `analyze_g2.py` output — integrity gate, training gates, branch adjudication, secondaries |
| `scripts/paper_g2/` | architecture, trainer, bench, chain, ruler driver, adjudicator, watchdog |
| `/mnt/c/carc-shared/paper_g2_20260803/<arm>/` | per-epoch checkpoints, `history.json`, `manifest.json` |
