# FGSR_OFFLINE_RESULTS.md — Stage 6 offline gate (TEST split)

_generated 2026-06-29 04:17 · net-free · frozen v2.9 leaf · TEST = 1672 roots · 2000-resample bootstrap · NO search, NO games_

Gate frames each head against the PASS criteria; the DECISION is the human's.

- **G3 robust win** = P(beats B3) ≥ 0.95, CI not crossing 0, at matched compute, on ≥1 robustness split, AND ≥10–20% tail-regret reduction vs B3.
- **G4 strength win** = decisive-tail regret reduction vs h200 with bootstrap CI>0 that survives the ordinary-subset no-regression check.

## G0

### G3 scheduler — AUROC(pos_strong) = **0.6602** → verdict **FAIL** (P_max=0.34, max matched-compute regret reduction vs B3 = -1.0%)

Matched-compute regret vs B3 (lower=better) + bootstrap P(model<B3):

| C | model | B3 | Δ (model−ref, +=better) | P(beats B3) | 95% CI |
|---|---|---|---|---|---|
| 300 | 0.00263 | 0.00227 | -0.000358 | 0.058 | [-0.00087, +0.00011] |
| 400 | 0.00215 | 0.00204 | -0.000132 | 0.2325 | [-0.00049, +0.00028] |
| 600 | 0.00179 | 0.00168 | -0.000071 | 0.1835 | [-0.00021, +0.00018] |
| 800 | 0.00169 | 0.00160 | -0.000080 | 0.3375 | [-0.00044, +0.00024] |
| 1200 | 0.00157 | 0.00130 | -0.000285 | 0.0375 | [-0.00061, +0.00003] |

vs B5 (flat MLP), matched-compute + bootstrap:

| C | model | B5 | P(beats B5) | 95% CI |
|---|---|---|---|---|
| 300 | 0.00263 | 0.00232 | 0.01 | [-0.00055, -0.00005] |
| 400 | 0.00215 | 0.00176 | 0.006 | [-0.00066, -0.00013] |
| 600 | 0.00179 | 0.00171 | 0.2365 | [-0.00016, +0.00021] |
| 800 | 0.00169 | 0.00161 | 0.3085 | [-0.00043, +0.00021] |
| 1200 | 0.00157 | 0.00110 | 0.0055 | [-0.00074, -0.00015] |

**Robustness — opening-only TEST slice** (n=387): AUROC model=0.6639784946236559, ref=0.6935483870967742; Δregret @C400=-0.00045831655982244085, @C800=-0.00020324434370854383.

Per-phase Δregret (ref−model, +=model better):

| phase | n | Δ@C400 | Δ@C800 |
|---|---|---|---|
| opening | 387 | -0.000458 | -0.000203 |
| midgame | 348 | -0.000235 | +0.000000 |
| late_mid | 340 | -0.000437 | -0.000218 |
| pre_endgame | 286 | +0.000352 | -0.000194 |
| endgame | 311 | +0.000159 | -0.000140 |

### G4 reranker (constant h200 compute) → verdict **TIE** (P(tail reduction>0)=0.94, ordinary no-regression=False)

Selected-move regret vs h6400 (lower=better):

| slice | n | h200 | model | model+abstain |
|---|---|---|---|---|
| decisive_tail | 46 | 0.04582 | 0.03703 | 0.04297 |
| full_pool | 1672 | 0.00286 | 0.00876 | 0.00527 |
| ordinary | 1626 | 0.00164 | 0.00796 | 0.00421 |

_37 of 46 decisive-tail roots are structurally blind (leaf_q gap≈0 between model and h200 pick) — abstain keeps h200's pick there._

- bootstrap **model** tail-regret reduction vs h200: P(>0)=0.94, Δ=+0.008888 CI[-0.002533, +0.018125].
- bootstrap **model_abstain** tail-regret reduction vs h200: P(>0)=0.78, Δ=+0.003033 CI[-0.006466, +0.010314].

## G1

### G3 scheduler — AUROC(pos_strong) = **0.5594** → verdict **FAIL** (P_max=0.34, max matched-compute regret reduction vs B3 = -1.0%)

Matched-compute regret vs B3 (lower=better) + bootstrap P(model<B3):

| C | model | B3 | Δ (model−ref, +=better) | P(beats B3) | 95% CI |
|---|---|---|---|---|---|
| 300 | 0.00256 | 0.00227 | -0.000291 | 0.072 | [-0.00066, +0.00010] |
| 400 | 0.00236 | 0.00204 | -0.000324 | 0.054 | [-0.00069, +0.00008] |
| 600 | 0.00184 | 0.00168 | -0.000148 | 0.1445 | [-0.00040, +0.00017] |
| 800 | 0.00169 | 0.00160 | -0.000080 | 0.3375 | [-0.00044, +0.00024] |
| 1200 | 0.00177 | 0.00130 | -0.000500 | 0.0005 | [-0.00082, -0.00017] |

vs B5 (flat MLP), matched-compute + bootstrap:

| C | model | B5 | P(beats B5) | 95% CI |
|---|---|---|---|---|
| 300 | 0.00256 | 0.00232 | 0.1335 | [-0.00060, +0.00020] |
| 400 | 0.00236 | 0.00176 | 0.0005 | [-0.00089, -0.00027] |
| 600 | 0.00184 | 0.00171 | 0.204 | [-0.00036, +0.00021] |
| 800 | 0.00169 | 0.00161 | 0.3085 | [-0.00043, +0.00021] |
| 1200 | 0.00177 | 0.00110 | 0.001 | [-0.00096, -0.00038] |

**Robustness — opening-only TEST slice** (n=387): AUROC model=0.46415770609318996, ref=0.6935483870967742; Δregret @C400=-0.00031296645577417667, @C800=-0.00020324434370854383.

Per-phase Δregret (ref−model, +=model better):

| phase | n | Δ@C400 | Δ@C800 |
|---|---|---|---|
| opening | 387 | -0.000313 | -0.000203 |
| midgame | 348 | -0.000659 | +0.000000 |
| late_mid | 340 | -0.000432 | -0.000218 |
| pre_endgame | 286 | +0.000517 | -0.000055 |
| endgame | 311 | -0.000108 | -0.000275 |

### G4 reranker (constant h200 compute) → verdict **TIE** (P(tail reduction>0)=0.92, ordinary no-regression=False)

Selected-move regret vs h6400 (lower=better):

| slice | n | h200 | model | model+abstain |
|---|---|---|---|---|
| decisive_tail | 46 | 0.04582 | 0.03602 | 0.04554 |
| full_pool | 1672 | 0.00286 | 0.00877 | 0.00590 |
| ordinary | 1626 | 0.00164 | 0.00800 | 0.00478 |

_33 of 46 decisive-tail roots are structurally blind (leaf_q gap≈0 between model and h200 pick) — abstain keeps h200's pick there._

- bootstrap **model** tail-regret reduction vs h200: P(>0)=0.92, Δ=+0.010122 CI[-0.004811, +0.022070].
- bootstrap **model_abstain** tail-regret reduction vs h200: P(>0)=0.57, Δ=+0.000624 CI[-0.012398, +0.011263].

## Deferred
- Source split (greedy-vs-MCTS robustness) needs roots_adaptive graphs (not built this run) — DEFERRED.

