# G2 TRANSFORMER CONTROL — PRE-REGISTRATION

> **STATUS: 🔒 PRE-REGISTERED 2026-08-03, BEFORE THE FIRST TRAINING STEP.**
> This file is committed before any G2 arm is trained and before the ruler is
> run. Nothing below may be edited after training starts except to record
> outcomes in §7; any change to §§1–6 after that point must be a new dated
> section with the reason, not an overwrite.
>
> Design rationale: [DESIGN_MEMO.md](DESIGN_MEMO.md). Measurement only — no
> `governance/PRODUCTION.yaml`, no `experiments/results.csv` row, no champion
> change, no shared trainer default changed.

## 1. The question

Every learner in the P1 closure ladder is a conv-ResNet, MLP, GBDT or ridge
regression. **Does the prediction/discrimination dissociation reported in CL-073
hold for a transformer trunk at matched parameters and matched corpus passes?**

Two-sided by construction:

- If it holds, P1's claim generalises across architecture class and
  CLAIMS_LEDGER row **G2** closes.
- If a transformer *discriminates*, the learned-value kill set (CL-039 / CL-042 /
  CL-064 / CL-065 / CL-066 / CL-073) is **architecture-scoped**, the paper claim
  rescopes, and a strength-program flag is raised for Joshua.

## 2. Arms (all trained from RANDOM INIT; no warm start)

| arm id | trunk | trainable params | ×baseline |
|---|---|---|---|
| `g2_resnet_scratch` | 6 ResBlocks × 96 filters (the baseline arch) | 7,509,167 | 1.000 |
| `g2_tf_match` | 6 pre-LN encoder blocks, d_model 128, 8 heads, FF×4 | 7,731,599 | 1.030 |
| `g2_tf_large` | 12 pre-LN encoder blocks, d_model 384, 8 heads, FF×4 | 28,062,863 | 3.738 |

Heads (`policy_project`, `policy_fc`, `value_project`, `value_fc1`, `value_fc2`,
`ownership_head`, `value_global_pool=True`) are identical code and identical
shapes across all three; only the trunk differs.

Reference arms on the ruler, not trained here: `curve125` (the champion leaf —
**the baseline the bar is written against**), `v29_leaf` (provenance self-check),
`value_unlock_v1` (the published CL-073 ResNet), `iter_03` (its warm parent).

## 3. The frozen task and recipe (identical for all three arms)

| knob | value |
|---|---|
| corpus | `/mnt/c/carc-shared/distill_strong_20260723` iter_00..03 (`--iter 3 --window 4`), 2,400 files / 345,333 rows, fingerprint `6b362781945b33f3` |
| split | by GAME, `split_files_train_val(val_fraction=0.05, seed=0)` → 2,280 train files (328,077 rows) / 120 val files (17,256 rows) |
| input rep | sighted 81 planes × 25 × 25 + 42 scalars (the corpus arrays, unmodified) |
| value target | mover-POV outcome `tanh((p0−p1)/15)` (the corpus `values` array, unmodified) |
| loss | `masked_policy_CE + 5.0 · value_MSE + 0.0 · ownership` |
| optimizer | AdamW, lr 3e-4, weight decay 1e-4, cosine annealing over the full run |
| effective batch | 256 (grad accumulation for `g2_tf_large`: micro 64 × 4; optimizer steps unchanged) |
| seed | 0 |
| **corpus passes** | **16** (= `value_unlock_v1`'s cumulative lineage: 4 iters × 3 epochs + 4 refine epochs) |
| precision | bf16 autocast, fp32 master weights, **fp32 validation** — uniformly across all three arms |

Checkpoints are written every epoch; `best.pt` tracks the lowest held-out value
MSE; `final.pt` is the last epoch.

## 4. Training-validity gates (checked BEFORE any ruler number is looked at)

### 4.1 Convergence criterion

An arm is **CONVERGED** iff, comparing the best held-out value MSE over its final
4 epochs against the best over its first 12:

* relative improvement < 2%, **and**
* the same holds for held-out policy cross-entropy.

If an arm is NOT converged at 16 passes, it is **extended once by +16 passes**
(cosine re-annealed over the 32-pass horizon, resumed from `last.pt`), re-checked,
and both curves reported. If it is still not converged, the arm is reported as
**UNDERTRAINED** and **cannot support Branch A**.

### 4.2 Did-it-fit gate

An arm is a **VALID CONTROL** only if all three hold:

1. final-epoch **train** value MSE < 0.5 × epoch-1 train value MSE (the net is
   fitting the objective at all);
2. held-out **value↔outcome Pearson r ≥ 0.55** (the published nets read 0.6564 /
   0.6795; the hand-crafted-leaf reference is ≈0.61, `train_iter.py:706`);
3. held-out mean policy entropy ≥ **0.8002** nats (the project's own collapse
   floor = 0.50 × the 1.6004 baseline).

An arm failing 4.2 is reported as FAILED-TO-FIT. A failed arm's poor ruler score
is **not** evidence for Branch A.

### 4.3 Instrument-integrity gate (the ruler run is VOID if this fails)

In the same ruler pass, the `v29_leaf` and `curve125` arms must reproduce
`solver_regret_mean` **0.9508**, `top1_rate` **0.6095**, `tau_mean` **0.6153** to
four decimals (as they have on 2026-07-03, 2026-07-23, 2026-07-30). If they do
not, the pass is void and no G2 number is reported.

## 5. THE BARS (pre-committed)

**Instrument:** `scripts/canonical_az/solver_score.py --max-k 2`, the 1,119 exact
K=2 marginalized roots, one solve per root shared by all rankers.
**Primary statistic:** `solver_regret_mean` (raw points, mover-POV, lower better).
**Significance:** paired sign-z on per-root regret vs `curve125`,
`z = (n_better − n_worse)/sqrt(n_better + n_worse)`, oriented so **positive = the
arm beats the leaf**. This is the project's standing convention
(`analyze_v210_screen.py:33`), with the standing gate trigger |z| ≥ 2.
**Primary checkpoint per arm:** `best.pt` (lowest held-out value MSE). `final.pt`
is scored in the same pass and reported; it is not the primary.

Adjudicated **per arm**, with `g2_tf_match` as the headline:

### Branch A — the dissociation GENERALISES across architecture class
> The arm passes §4.2, its held-out value↔outcome r ≥ **0.61** (the heuristic
> reference), **and** its `solver_regret_mean` is **higher** than `curve125`'s
> **and** the paired sign-z is **≤ −2.0**.

⇒ P1's claim generalises. CLAIMS_LEDGER **G2 closes**; OUTLINE §9.3 rewrites from
"transformers not tested" to "conv / MLP / GBDT / ridge **and** transformer
families tested". No strength-program flag.

### Branch B — the kill set is ARCHITECTURE-SCOPED
> The arm's `solver_regret_mean` is **lower** than `curve125`'s **and** the paired
> sign-z is **≥ +2.0**.

⇒ **PAPER: rescope.** The dissociation is a property of the tested conv/tabular
family, not of outcome regression as such; §§5–6 and the abstract must be rewritten
and CL-039/064/065/073's scope fields amended.
⇒ **STRENGTH PROGRAM: flag raised.** The learned-value route reopens on a modern
architecture; CLAUDE.md structural blocker #2 requires restatement. **Report only —
next steps are Joshua's.** No promotion, no PRODUCTION change, no online run
initiated from this result.

### Branch B-partial — architecture moves the needle without closing the gap
> Neither A nor B fires, **and** the arm's `tau_mean` ≥ **0.30**.

(0.30 is **CL-064's own pre-registered LIVE threshold**, reused verbatim — not a
bar invented for this experiment. Context: the ResNet arms read τ 0.019 / 0.083 /
0.095 / 0.133; the leaf reads 0.6153.)

⇒ Report the interval. **No promotion, no claim rescope** beyond OUTLINE §9.3
recording "tested; partial". Strength-program flag at **ADVISORY** level only
(records that a modern architecture is the first learner to move τ off the floor).

### Branch C — gray zone
> Everything else: |sign-z| < 2, or the two primary statistics disagree in sign,
> and `tau_mean` < 0.30.

⇒ **AMBIGUOUS.** Report point estimates and bootstrap intervals; record that the
control ran; no promotion, no claim change. §9.3 gains a sentence naming the
control and its inconclusive outcome.

### Secondary statistics — reported, NOT gating
`top1_rate`; `tau_mean` ± bootstrap-over-roots σ (B = 10,000, seed 0, the
`solver_score_agent.bootstrap_block` convention); paired sign-z of each G2 arm vs
`value_unlock_v1` and vs `g2_resnet_scratch`; and the picked-child agreement rate
between arm pairs (the READOUT §4.3(b) statistic).

**The architecture contrast**, pre-declared: paired sign-z of
(`g2_resnet_scratch` regret − `g2_tf_match` regret) over the same 1,119 roots.
|z| ≥ 2 is required to call any difference between the two architectures real;
below that the two are reported as indistinguishable. This statistic is
**descriptive** — it never overrides §5's branches, which are all defined against
`curve125`.

**Multiplicity.** Three trained arms × 2 checkpoints = 6 adjudications against one
baseline. The headline arm is fixed in advance (`g2_tf_match`, `best.pt`); the
other five are reported as secondary and **cannot on their own trigger Branch B**
— a Branch-B firing on a non-headline arm alone is reported as B-partial pending a
confirmatory rerun, whose design would be Joshua's call.

## 6. Declared out of scope (before the fact)

- No online / game-play evaluation, no blend, no search integration. Offline
  sibling regret is not online search value (READOUT §4.4, inherited).
- No `scripts/level2/endgame_regret.py` run — it scores whole search agents, not
  bare value rankers (READOUT §3.5, inherited).
- K≤4 roots (≈21 min/solve) are not fundable here; all 1,119 roots are K=2
  endgames (limitation E5, inherited).
- One seed per arm. No recipe sweep. CL-064's "seed spread exceeded the size
  effect" caution applies: every verdict here rests on the **level** relative to
  the leaf, never on a small between-arm difference.
- No new metric is defined after this file is committed.

## 7. Outcomes (filled in AFTER the fact; this section only)

*(empty at pre-registration)*
