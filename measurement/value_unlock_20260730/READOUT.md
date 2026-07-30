# Stage-3 value-unlock — OFFLINE chain read-out (2026-07-30)

> **STATUS: IN PROGRESS — pre-registration section §3 was written and committed BEFORE
> the ruler was run. Results sections are filled in below it.**

**Scope, stated up front and binding on every number here.** This is the three-step
*offline* chain Joshua funded ("ok, have a subagent try it"): (1) verify audit finding
**F13**, (2) train a value head on the strong corpus, (3) score it against the frozen
champion leaf on the offline ruler. **No online experiment, no blend, no search
experiment, no game eval, no `governance/PRODUCTION.yaml` touch.** Offline sibling
regret is **not** online search value; a win here funds the blend test and nothing more.

---

## 1. F13 verification — "residual target ±2 into a ±1 tanh head"

### 1.1 The code claim: **CONFIRMED, verbatim, at HEAD**

The audit's three cited lines are all present and un-discharged (verified this pass, all
line numbers re-read off disk today):

| what | file:line | text |
|---|---|---|
| the head | `src/carcassonne_ai/network.py:148` | `return torch.tanh(self.value_fc2(v)).squeeze(-1)` — unconditional, no linear-output branch |
| trajectory residual row | `src/carcassonne_ai/selfplay.py:446-449` | `search_values_arr.append(float(mcts.root_value(board)) - _v27_leaf_value(board.state, cur_player))` — no clip, no rescale |
| interior residual row | `src/carcassonne_ai/selfplay.py:471-473` | `interior_values_arr.append(float(nb_q) - _v27_leaf_value(nb.state, nb_player))` — no clip, no rescale |
| the leaf term's range | `src/carcassonne_ai/selfplay.py:39-46` | `_v27_leaf_value` returns `tanh(virtual_score_v2(...)/15)` ∈ [−1,1] |
| the MSE that consumes it | `scripts/train_iter.py:569` | `val_loss = F.mse_loss(value_pred, value_b)` |

So the **arithmetic** claim is exactly right: `root.Q ∈ [−1,1]` minus a leaf value in
`[−1,1]` is a target with support `[−2,+2]`, fed to a head whose codomain is `(−1,+1)`.
`REVIEW_LOG.md:549` is accurate about the code, and nothing has discharged it.

### 1.2 The *effect* claim: **REFUTED empirically — the tail the finding is about is empty**

The attempt-2 residual `.npz` corpora were deleted in a disk sweep (`iter{1..10}_data/`
under `/mnt/c/carc-shared/flywheel_residual_attempt2/` now hold only `.claim` files; a
whole-share `find -name '*.npz'` over every `*residual*` directory returns **0 files**).
So the histogram was taken from a **regeneration through the same emitter at attempt-2's
own knobs** — `scripts/gen_flywheel.sh`'s `SP_COMMON` verbatim (`--leaf-eval v2_5
--value-blend 0 --residual-scale 0.25 --value-target residual --sims 200 --batch-size 8`,
env `CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12
CARCASSONNE_USE_FLAT_LEAF=1`), warm-from the surviving attempt-2 `warm.pt`. Driver:
[`f13_gen.sh`](f13_gen.sh); 24 games, **52,971 rows**, seed band 700000 (fresh, disjoint
from attempt-2's 400–799).

**Measured distribution of the residual target Δ (n = 52,971 rows):**

```
min -0.739897   max +0.821970   mean +0.013673   sd 0.077952

  [-1.00,-0.75)        0   0.000%
  [-0.75,-0.50)       45   0.085%
  [-0.50,-0.25)      242   0.457%
  [-0.25,+0.00)    22663  42.784%
  [+0.00,+0.25)    29431  55.561%
  [+0.25,+0.50)      544   1.027%
  [+0.50,+0.75)       44   0.083%
  [+0.75,+1.00)        2   0.004%
  [+1.00,+2.00)        0   0.000%

  frac |Δ| > 0.5  : 0.001718  (n=91)
  frac |Δ| > 0.75 : 0.000038  (n=2)
  frac |Δ| > 1.0  : 0.000000  (n=0)   <-- the saturating region
  frac |Δ| >= 0.9 : 0.000000  (n=0)   <-- the tanh-gradient<=0.19 region
```

**Verdict: F13 is CONFIRMED as a code fact and REFUTED as a mechanism.** The finding's
load-bearing sentence is *"the clipped `|Δ|>1` tail is exactly the 'search strongly
disagrees with the heuristic' set — the positions the residual exists to capture."* That
set is **empty**: **0 of 52,971 rows** exceed |Δ|=1, the single largest residual in the
sample is **0.822**, and 98.3% of rows sit inside |Δ|≤0.25. The head is never asked to
represent a target it cannot express, and never enters the vanishing-gradient regime.
Structurally this is what one should expect — |Δ|>1 needs the search Q and the leaf near
*opposite* extremes, and positions where the leaf is near ±1 are already decided, so the
search agrees there.

**What the data does show instead, and it is a different defect:** the residual target's
**sd is 0.078** while the policy cross-entropy it is summed against is O(1.5) at
`--value-loss-weight 1.0` (attempt-2's setting, read off
`/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter1.metrics.json`:
`train_pol_loss 1.5746` vs `train_val_loss 0.0038`, i.e. **~414×**). That is a
*signal-magnitude / loss-weighting* problem (the G-T2 axis), not the *representational
cap* F13 asserts. Anyone re-opening the residual lever should carry this correction: the
named fix (clip to [−1,1], or a linear output head) would have changed **nothing**.

**Honest scope on this refutation:** one 24-game regeneration, one seed band, at
sims=200 with the attempt-2 warm net. It is not the original attempt-2 corpus (that is
gone). The margin is large enough (largest observed |Δ| = 0.822 vs the 1.0 threshold,
with a 0.078 sd) that a band effect flipping it is implausible, but it is a
reconstruction and is labelled as one.

### 1.3 Consequence for THIS run's target shape

The corpus trained on in §2 uses **outcome** values, not residuals:
`values = tanh((p0−p1)/15)` mover-POV (`scripts/distill_flywheel/gen_fair_distill.py:319-320`).
Measured over all **345,333 rows** of `iter_00..03`: `min −0.999988, max +0.999988,
mean +0.000086, sd 0.711358` — **already inside the tanh head's range, 0 rows clipped**.
So the F13 fix (rescale/clamp) is a **no-op here and is deliberately not applied**, and
**no shared trainer default was changed** for any other pipeline.

One in-range analogue *is* worth recording, since it is the same physics one step milder:
**27.16% of rows have |v| ≥ 0.9** and **4.67% have |v| ≥ 0.99**, where tanh's derivative is
≤0.19 and ≤0.02 respectively. Changing the head to a linear output would address it — but
it would also invalidate warm-starting from CL-067 `iter_03`'s existing value head and
so confound the one comparison this chain exists to make. **Choice made and recorded:
keep the tanh head, keep the targets unscaled, raise the value loss weight instead
(§2).**

## 2. Training

*(filled in below — see §2 results)*

## 3. PRE-REGISTRATION — the offline verdict metric and bar

**Written before the ruler was run. Commit for this section precedes the result commit.**

### 3.1 Instrument

`scripts/canonical_az/solver_score.py` — the project's **non-circular** offline ranker
scorer. It reuses the **same 10,067 h6400_v2.9 sibling roots**
(`measurement/high_gap_distillation/scaled/qprobe_A/probe.jsonl` JOIN `pool_A.jsonl` on
`(seed, ply)`) that every prior sibling-regret verdict used, but it scores each ranker's
per-child ordering against the **exact endgame solver's** `child_values`, not against
h6400's `action_q`.

**Why not h6400's `action_q` directly** (i.e. `scripts/rod_v2/value_resurrection/leaf_audit.py`,
the harness whose colloquial name is "the sibling-regret ruler"): its own docstring and
`solver_score.py:4-7` record that **the h6400 oracle correlates 0.995 with the v2.9 leaf**
(autopsy F4), so "does the learned head beat the leaf on h6400-regret?" is *circular in
the leaf's favour by construction*. `leaf_audit.py` also has **no checkpoint hook at
all** — it is hardcoded to the v2.9 leaf — so it cannot score a learned value head even
if we wanted the circular number. The solver ruler is the instrument that (a) admits
arbitrary rankers (`--checkpoint`, `--leaf-variant`) and (b) has ground truth
uncorrelated with the leaf. **This is a deliberate deviation from the task's literal
wording, made before seeing any result, and it is the harder test for the learned head,
not the easier one.**

### 3.2 Root set

`--max-k 2` → the **1,119 exact K≤2 roots, all K=2, all `marginalized` mode** (the
qprobe_A strata are discrete `k_remaining ∈ {2,4,6,10,14,22,32,44,56}`, so there are no
odd-K roots; K≤4 would add 1,119 K=4 roots whose clairvoyant+αβ solves run ~21 min each
= not fundable here). This is the **identical root set** the M2 read-out used
(`measurement/canonical_az/solver_score_derisk_it00_03.json`, `n_scored: 1119`), so the
learned head's number is directly comparable to the M2 nets' numbers.

**Scope limit, stated in advance:** these 1,119 roots are all **endgame** (`k_remaining=2`).
The verdict is therefore an *endgame* sibling-ranking verdict, not a whole-game one.

### 3.3 Arms (all scored on the SAME solves, one pass)

| arm | what |
|---|---|
| `v29_leaf` (baseline) | the harness's built-in v2.9 leaf at cap 8 / **curve100** |
| `curve125` (`--leaf-variant`) | the **champion's actual leaf** — same cfg, `V29_MEEPLE_CURVE=-8,-4,-1,0,2.5,3.75,5,6.25` (the `run_v210_trackA_screen.sh` C125 string) |
| `iter_03` (`--checkpoint`) | CL-067 `distill_strong_20260723/ckpt/iter_03.pt` value head — **the un-refined warm parent, as the control** |
| `value_unlock_v1` (`--checkpoint`) | this run's trained value head |

### 3.4 The metric and the bar

**Primary statistic:** `solver_regret_mean` — the harness's canonical
`step1_train.group_metrics` argmax-regret, **in RAW POINTS**, mover-POV, ≥ 0, lower is
better (`solver_score.py:19-21`, `group_metrics` at `scripts/feature_planes_gate/step1_train.py:70-72`).

**Significance treatment:** the project's standing convention for this ruler — the
**paired sign-z on per-root regret** against the comparison arm on the *same* solved
roots, `z = (n_better − n_worse) / sqrt(n_better + n_worse)`, implemented at
`scripts/canonical_az/analyze_v210_screen.py:33` and reused verbatim at
`scripts/canonical_az/solver_score_agent.py:390-397`. The pre-registered gate trigger in
`docs/V210_LEAF_SPEC_2026-07-04.md` is **paired sign-z ≥ 2**.

**THE BAR (pre-committed):**

> **YES — "learned value beats the champion leaf offline"** iff `value_unlock_v1` has a
> **strictly lower** `solver_regret_mean` than the **`curve125`** arm **AND** the paired
> sign-z of (curve125 regret − value_unlock_v1 regret) over the 1,119 roots is **≥ +2.0**.
>
> **NO** iff `value_unlock_v1`'s `solver_regret_mean` is **higher** than curve125's **and**
> the paired sign-z is **≤ −2.0**.
>
> **AMBIGUOUS** in every other case (|sign-z| < 2, or the two statistics disagree in sign).

**Secondary, reported but not gating:** `top1_rate` (exact argmax agreement with the
solver) and `tau_mean` (Kendall tau-b), each with a **bootstrap over roots** (B = 10,000,
the `solver_score_agent.bootstrap_block` convention) for the tau sigma; and the
`iter_03` control arm, which tells us whether the value refine moved anything at all
(a `value_unlock_v1` ≈ `iter_03` reading means the recipe was inert, which is a
different failure than "learned value can't rank").

**Reference numbers already on disk** (`measurement/canonical_az/solver_score_derisk_it00_03.json`,
same 1,119 roots, read off the `aggregate` block): `v29_leaf` regret **0.9508** / top1
**0.6095** / tau **0.6153**; the four M2 sighted nets' value heads regret **1.8177–1.9651**
/ top1 **0.074–0.084** / tau **0.018–0.023**. **Prior expectation is therefore strongly
NO**; the bar above is what would have to happen to overturn it.

### 3.5 L2-3 endgame regret

`scripts/level2/endgame_regret.py` scores **whole agents playing moves**
(`ALL_AGENTS` hardcoded at `:71`; the only pluggable slot is `--ckpt` feeding the
`iter8` **NeuralMCTS** agent, i.e. a full policy+value search agent, not a bare value
ranker). It **cannot** score a bare value head as an evaluator, so running it would
measure a *search agent*, which is exactly the online question this chain is barred from.
**Declared out of scope before the fact**, with that reason.

---

## 4. Results

*(filled in below)*
