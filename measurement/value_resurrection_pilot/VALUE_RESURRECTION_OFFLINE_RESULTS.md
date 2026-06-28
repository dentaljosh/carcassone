# Value Resurrection Pilot — OFFLINE RESULTS (Stage 5 = Gate 2)

> **STATUS: GATE FAILS → Decision B. STOP (no NMCTS, no games, no cluster).** 2026-06-28.
> **No learned value/ranking variant beats the v2.9 leaf on held-out sibling regret.** The offline
> α-sweep selects **α = 0** (zero weight on the learned term) for *every* variant; regret rises
> **monotonically** with α; the **endgame is no exception** (refutes Decision F). Reproduces CL-021
> against the *stronger* v2.9 leaf and the *deeper* h6400 teacher.

## The gate

Rank each held-out sibling set by the **combined ranker** `score(child) = leaf_q + α·learned(child)`
(learned output standardized; α=0 ≡ v2.9-leaf-alone). **Pass = some α makes regret drop ≥15–20% vs
α=0, top1 up, no ordinary catastrophe.** Test split = **637 groups** (172 held-out games), leakage-safe.

**v2.9-leaf-alone baseline (the bar to beat):** overall regret **0.0237** / top1 **0.474**;
endgame regret **0.0121** / top1 **0.465**.

## Result — every variant: best α = 0, beats_leaf = FALSE

| variant | net-alone τ vs h6400 | net-alone top1 | best α | combined regret (α=0 → α\*) | beats leaf? |
|---|---|---|---|---|---|
| **V4_listwise** (≈CL-021 arm B) | **+0.105** | 0.190 | **0.0** | 0.0237 → 0.0237 (**+0.0%**) | **No** |
| **V2_advantage** | **+0.083** | 0.165 | **0.0** | 0.0237 → 0.0237 | **No** |
| **V1_residual_mse** (predict the leaf's correction) | **+0.005** | 0.044 | **0.0** | 0.0237 → 0.0237 | **No** |

*(V1r_residual_list, V5_endgame not run — cut short; residual head independently inert, b99c9ed.)*

Context: the **v2.9 leaf ranks siblings at τ = 0.895**; the best learned head reaches **τ = 0.105**
(≈12% of the leaf, and barely above CL-021's arm-B **+0.029**). The **production net** (trained on
millions, b99c9ed) ranked at ~0.08 — same order. **Not probe-limited, not scale-limited.**

## The α-sweep is monotonically worse (V4, overall)

| α | 0.0 | 0.05 | 0.1 | 0.25 | 0.5 | 1.0 | 2.0 |
|---|---|---|---|---|---|---|---|
| regret | **0.0237** | 0.0296 | 0.0374 | 0.0484 | 0.0588 | 0.0637 | 0.0659 |
| top1 | **0.474** | 0.345 | 0.305 | 0.257 | 0.226 | 0.209 | 0.201 |

Adding *any* of the learned signal **degrades** the leaf ranking — the net's output is noise w.r.t. the
fine sibling structure, and mixing it in overrides the leaf's good ordering. V2 and V1 are identical in
shape (monotone up).

## Endgame slice — Decision F refuted

The endgame (the slice the pilot hoped might carry a learned value) behaves the same: leaf-alone is best
(regret 0.0121 / top1 0.465), and every α>0 makes it worse (V4: 0.0121 → 0.0167 → 0.0470). **net-alone
τ in the endgame is only +0.039** — the leaf is *strongest* in the endgame (Stage-3 audit), so there is
the least to add, and the net adds nothing. Consistent with exact-endgame being outcome-neutral and the
net playing the endgame worst (priors).

## Reading

This is **Decision B**: a real target exists (Stage 3: ~1,197 decisive leaf misses) but a learned
per-position value **scalar cannot beat the v2.9 leaf at sibling ranking** — three formulations
(listwise, advantage, residual-regression) all land at "give the net zero weight." The residual
variant — the natural "learn where the leaf is wrong" framing — is the **worst** (τ≈0): the leaf's
0.5%-of-signal residual is unlearnable by this architecture. → no Stage 6 (NMCTS), no Stage 7 (games).

Data: `stage4/<variant>/summary.json`, `stage4/stage5_offline_gate.json`.
Verdict + the 7 questions: [VALUE_RESURRECTION_DECISION.md](VALUE_RESURRECTION_DECISION.md).
