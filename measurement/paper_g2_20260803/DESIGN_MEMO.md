# G2 — the TRANSFORMER CONTROL for "Outcome Prediction Is Not Move Discrimination"

> **STATUS: ✅ CLOSED 2026-08-03 — verdict `C_GRAY`.** All three arms trained
> (≈10.9 GPU-h), the ruler pass ran clean (`scored=1119 skipped=0 errors=0`,
> integrity gate PASS), and every arm returned `C_GRAY`: the transformer lands
> indistinguishably from the ResNet (paired sign-z −0.94) and ~2× worse than the
> champion leaf, **but no from-scratch arm cleared the pre-registered
> outcome-prediction fit gate**, so this does not establish Branch A. Verdict and
> the warm-start finding: **[READOUT.md](READOUT.md)**; adjudication: PREREG §7.
> The design below is unchanged and is what ran.
>
> *(original banner, retained)* **🔵 DESIGN + PRE-REGISTERED, TRAINING PENDING
> (2026-08-03).** Funded by Joshua 2026-08-03. This memo is the *design rationale*;
> the binding bars live in [PREREG.md](PREREG.md), which is committed **before the
> first training step**.
> Measurement only — no `governance/PRODUCTION.yaml` touch, no `experiments/results.csv`
> row (offline instrument; the paper ledger + this directory carry it), no champion change.

## 1. What this is and why it exists

Paper P1 ([docs/papers/p1_prediction_vs_discrimination/OUTLINE.md](../../docs/papers/p1_prediction_vs_discrimination/OUTLINE.md))
claims a dissociation: a learned value head can *improve* at outcome prediction
(held-out value↔outcome r 0.6795, above its parent's 0.6564 and above the ≈0.61
hand-crafted-leaf reference) while losing **sibling move discrimination** to that
same leaf by 2.10× in solver regret, 9× at top-1 and 32× at Kendall τ (paired
sign-z −17.43 over 1,119 exact-solver roots). Every learner in the closure ladder
is a conv-ResNet, an MLP, a GBDT or a ridge regression. §9.3 of the outline
therefore scopes the claim by *architecture family*, and CLAIMS_LEDGER row **G2**
records the open decision: run a bounded modern-architecture control, or scope
the claim.

This directory runs the control.

**It is deliberately two-sided.** The advisor framing ("blunts the one predictable
referee objection") treats this as a paper chore. It is not only that. CL-064
established that capacity is not the binding constraint *within* ResNets; nothing
in the kill set tests architecture *class*. If a transformer discriminates, the
whole learned-value kill set (CL-039 / CL-042 / CL-064 / CL-065 / CL-066 / CL-073)
becomes architecture-scoped and structural blocker #2 in
[CLAUDE.md](../../CLAUDE.md) reopens on a modern-architecture route. Both branches
are first-class in [PREREG.md](PREREG.md) §5 and neither is favoured by the design.

## 2. The validity bar this control has to clear

An architecture control is worthless if the referee can answer it with "your
transformer was undertrained / smaller / fed a different task / graded on a
different ruler". The four constraints below are the design, and each is
mechanised rather than promised.

### 2.1 PARITY — matched parameters

| net | trunk | total trainable params | vs baseline |
|---|---|---|---|
| `value_unlock_v1` (published ResNet baseline) | 6 ResBlocks × 96 filters | **7,509,167** | — |
| `resnet_scratch` (in-experiment ResNet control) | identical | 7,509,167 | ×1.000 |
| `tf_match` | 6 pre-LN encoder blocks, d_model 128, 8 heads, FF×4 | **7,731,599** | **×1.030** |
| `tf_large` (capacity leg) | 12 blocks, d_model 384, 8 heads, FF×4 | **28,062,863** | ×3.738 |

(Counts are measured, not estimated — `scripts/paper_g2/bench_g2.py`. The
checkpoint file's 7,511,688 figure quoted in the READOUT includes BatchNorm
running-statistic buffers, which are not trainable parameters; 7,509,167 is the
`param_count()` figure and is what "±20%" is applied to. `tf_match` is +3.0%,
comfortably inside the ±20% band.)

**Why the totals are dominated by a head, and why that is fine.** Both nets share
the AlphaZero-style policy head `Linear(4·25·25 + 42 → 2511)` = 6,386,073 params,
i.e. **85% of the 7.5M budget is the policy output layer in both architectures**.
The architectural contrast therefore lives in the trunk: 1,065,312 params of
conv-ResNet versus 1,285,888 params of transformer encoder — a **1.21× trunk
budget in the transformer's favour**, on top of the matched total. `tf_large`
raises the trunk to 21,582,336 (20.3× the ResNet trunk). The design deliberately
never gives the transformer *less* on any axis.

**Why the heads are byte-identical code.** `scripts/paper_g2/g2_transformer.py`
copies `policy_project` / `policy_fc` / `value_project` / `value_fc1` /
`value_fc2` / `ownership_head` and `_value_from_trunk` verbatim from
`src/carcassonne_ai/network.py`, with `n_filters → d_model`. The value head keeps
`value_global_pool=True`, exactly as the baseline. So the comparison is a trunk
comparison and nothing else, and the transformer inherits the same value-head
inductive bias the baseline had.

### 2.2 PARITY — matched training compute

Same corpus passes, same effective batch, same optimizer, same schedule, same
loss weights, same seed:

| knob | value | source |
|---|---|---|
| corpus | `distill_strong_20260723` iter_00..03, 2,400 files / 345,333 rows | READOUT §2 |
| split | **by game**, `split_files_train_val(val_fraction=0.05, seed=0)` → 2,280 / 120 files | READOUT §2 |
| effective batch | 256 | READOUT §2 |
| optimizer | AdamW, lr 3e-4, weight decay 1e-4, cosine to 0 | READOUT §2 |
| loss | `pol_CE + 5.0·value_MSE + 0·ownership` | READOUT §2 |
| seed | 0 | READOUT §2 |
| **corpus passes** | **16** | see below |

**The 16.** `value_unlock_v1` is a 4-epoch refine warm-started from CL-067
`iter_03`, which is itself the end of a four-iteration lineage at 3 epochs each.
Its cumulative exposure to this corpus family is therefore 4×3 + 4 = **16 corpus
passes**. The G2 arms cannot warm-start (no ResNet weights fit a transformer), so
they are trained **from random init for the full cumulative budget**, and an
in-experiment `resnet_scratch` arm gets the identical 16-pass from-scratch
treatment. That removes the warm-start confound from the architecture contrast
entirely: `resnet_scratch` vs `tf_match` is a clean, single-variable A/B, and
`value_unlock_v1` remains on the ruler as the published external reference.

`tf_large` needs gradient accumulation (micro-batch 64 × 4) to fit 16 GiB; the
*optimizer* batch and step count are unchanged, which is what "matched optimizer
budget" means. All three arms train under bf16 autocast with fp32 master weights
and **fp32 validation**, uniformly — a change from the published fp32 baseline
that is applied to every arm equally and logged.

**Wall-clock and FLOPs are NOT matched and are not claimed to be** — the
transformer costs 3.2× (tf_match) and 20× (tf_large) the ResNet's step time on
this GPU. Matching wall-clock instead of corpus passes would starve the
transformer of data passes, which is the actual referee objection. Both figures
are logged per epoch.

**Undertraining is answered by measurement, not assertion.** PREREG §4 fixes a
convergence criterion and a "did it fit at all" validity gate *before* training,
with a pre-committed extension rule. An arm that fails the fit gate cannot be
used to support Branch A.

### 2.3 SAME TASK — the tokenisation choice

The input is unchanged: the 81-plane, 25×25 *sighted* board tensor plus 42 scalar
features, the exact arrays in the corpus `.npz` files.

**Choice: per-cell tokens (patch = 1).** 625 cell tokens, each the 81-channel
vector at that cell linearly projected to `d_model`, plus a learned absolute
position embedding per cell, plus **one extra global token** carrying the 42
scalars.

Why, and why it smuggles nothing:

- **Information-preserving.** Patch=1 is a reshape. Any patch > 1 would pool
  several Carcassonne tile slots into one token and hand the transformer a
  strictly coarser view of the board than the convnet gets — a handicap that
  would make a negative result uninterpretable ("your transformer couldn't see
  individual tiles").
- **Resolution-matched.** One token per tile slot is the natural granularity of
  the game; the ResNet's own spatial unit is the same cell.
- **The scalars are supplied twice, not once.** The 42 scalars enter as a global
  token *and* are concatenated into both head MLPs exactly as in the ResNet. The
  transformer therefore never sees less than the ResNet on any input path.

**The one asymmetry, and it favours the transformer.** Global self-attention gives
every cell a board-wide receptive field from layer 1. The ResNet's stem + 6
residual blocks reach only 15×15 of the 25×25 window; it compensates partially
through `value_global_pool` (a board-wide mean+max summary injected into the value
head), which `tf_match` also has. So the control is run in the direction that is
**conservative for the paper's claim**: if the transformer still fails to
discriminate siblings, it did not fail for want of global context — which is
worth saying explicitly, because "convnets can't integrate the whole board" is the
most natural mechanistic rescue for the ResNet nulls and this design closes it.

A second asymmetry worth naming: the corpus's `group_id` is −1 throughout (G3's
finding — the training corpus contains **no sibling sets at all** and the outcome
label is *exactly* constant within a game). Both architectures face that label
structure identically. G2 is therefore a test of whether a different architecture
extracts between-sibling contrasts from a label that carries none — the mechanism
§6 predicts it cannot, and Branch B would be a genuine surprise.

### 2.4 SAME RULER — no new instrument, no new metric

The evaluation is `scripts/canonical_az/solver_score.py --max-k 2` over the same
**1,119 exact K=2 marginalized roots**, the same `curve125` champion-leaf
baseline, the same primary statistic (`solver_regret_mean`, raw points), the same
paired sign-z convention, the same bootstrap-over-roots τ σ (B = 10,000), and the
same adjudicator arithmetic (`measurement/value_unlock_20260730/analyze_ruler.py`).

The only code change to the harness is a new `--g2-checkpoint` flag that
constructs a ranker for a transformer checkpoint. Its `rank()` body — terminal
short-circuit to `get_game_ended`, mover-POV orientation flip on the child's
`current_player` — is copied character-for-character from the existing
`make_net_ranker`. **The integrity guard is empirical, not a promise:** the
`v29_leaf` and `curve125` arms must reproduce regret **0.9508** / top-1 **0.6095**
/ τ **0.6153** to four decimals, as they have across three independent runs
(2026-07-03, 07-23, 07-30). If they do not, the run is void and nothing is
reported.

Held-out outcome-prediction (value↔outcome Pearson r) is computed by
`train_iter._value_outcome_corr` — the same function, on the same by-game
validation split, that produced the baseline's 0.6564 / 0.6795.

## 3. Arms

| arm | what | role |
|---|---|---|
| `curve125` | the champion's leaf (`V29_MEEPLE_CURVE=-8,-4,-1,0,2.5,3.75,5,6.25`) | **the pre-registered baseline** |
| `v29_leaf` | harness built-in leaf, curve100 | provenance self-check |
| `value_unlock_v1` | published ResNet baseline (CL-073) | external reference |
| `iter_03` | CL-067 warm parent | continuity with the READOUT |
| `g2_resnet_scratch` | ResNet 6×96, random init, 16 passes | **in-experiment matched-budget control** |
| `g2_tf_match` | transformer d128×L6, random init, 16 passes | **the headline control** |
| `g2_tf_large` | transformer d384×L12, random init, 16 passes | capacity leg (mirrors CL-064's design) |

Each G2 arm is scored at **both** its best-held-out-value-MSE epoch and its final
epoch, in one pass, so no checkpoint is selected after seeing the ruler.

## 4. Cost

Measured on the local RTX 5060 Ti (16 GiB), bf16, effective batch 256, 1,282
optimizer steps/epoch (`scripts/paper_g2/bench_g2.py`, 2026-08-03):

| arm | step time (eff. batch 256) | peak VRAM | min/epoch (compute) | 16 epochs |
|---|---|---|---|---|
| `resnet_scratch` | 66.8 ms | 1.07 GiB | 1.43 (≈3.1 observed, data-bound) | ≈ 0.8 h |
| `tf_match` | 214.7 ms | 4.83 GiB | 4.59 | ≈ 1.3 h |
| `tf_large` (micro 64 × 4) | 1331.6 ms | 7.10 GiB | 28.45 | ≈ 7.7 h |

**Total ≈ 9.8 GPU-hours**, run serially, cheapest-informative-first
(`resnet_scratch` → `tf_match` → `tf_large`), so the headline answer lands ~2 h
in. Plus one solver-ruler pass, ≈ 1–2 h on 16 CPU workers at `nice -n 19`
(the 4-ranker baseline pass was 1,210 s; this one carries 10 rankers, one of them
a 28M-param net on CPU). Within the funded ~1 GPU-day.

Runs are **detached** (`setsid` + `nohup`) with **per-epoch checkpoints** and a
`--resume` path, per the box's dirty-reboot history
(memory `reference_local_box_dirty_reboots`).

## 5. What this does not do

- No online/game evaluation, no blend, no search experiment. Offline sibling
  regret is not online search value — the same scope limit the CL-073 chain
  carried (READOUT §4.4).
- All 1,119 roots are K=2 endgames; midgame discrimination is untested by this
  instrument (limitation E5, inherited unchanged).
- One recipe, one seed per arm. CL-064's own finding — seed spread exceeded its
  size effect — applies here too, and PREREG §5 accordingly rests every verdict
  on the *level* relative to the leaf, never on a small between-arm difference.
- No `results.csv` row, no `PRODUCTION.yaml` change, no champion change, no
  shared trainer default changed.

## 6. Files

| path | what |
|---|---|
| `scripts/paper_g2/g2_transformer.py` | the architecture (trunk swap; heads verbatim) |
| `scripts/paper_g2/train_g2.py` | the trainer (task/pipeline imported from `train_iter.py`) |
| `scripts/paper_g2/bench_g2.py` | the pre-flight param/throughput bench |
| `scripts/paper_g2/run_g2_chain.sh` | detached serial training chain |
| `scripts/paper_g2/run_g2_ruler.sh` | the solver-ruler pass |
| `scripts/paper_g2/analyze_g2.py` | the pre-registered adjudicator |
| [PREREG.md](PREREG.md) | the binding bars — committed before the first training step |
