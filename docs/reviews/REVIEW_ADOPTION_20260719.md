# Review adoption & disposition — 2026-07-19

**Status: ADOPTED (Joshua "go for it", 2026-07-19 evening).** This is the project's response to [INTEGRATED_REVIEW_20260719.md](INTEGRATED_REVIEW_20260719.md). It maps the review's recommendations to our state, records what we adopt/defer/decline, and defines the near-term work queue. The roadmap ([../PROGRAM_ROADMAP_2026-07-07.md](../PROGRAM_ROADMAP_2026-07-07.md)) carries the live queue; this doc is the reasoning of record.

**Standing constraint: human play is not an option yet (Joshua).** The review's Priority 2 (human benchmark) and Stop-Rule B are ACCEPTED IN PRINCIPLE and PARKED; their protocol amendments (cross-player/Latin-square deck pairing — same-human deck replay leaks hidden order via memory; first-contact + adaptation blocks; sealed one-use claim bands) are adopted now so no infrastructure gets built the wrong way.

## Already answered or in flight when the review arrived (same evening)

| Review item | Our state |
|---|---|
| "Equal simulations ≠ equal compute" caveat on the stage-1 tie (F9, Phase-3 table) | **#3 equal-wall-clock eval RUNNING** (net k4×395 vs champ k4×688, n=200 paired band 22.0e9). Calibration found all prior cost ratios were harvest-queue artifacts; unloaded deployment ratio = 1.74× (CHECKLOG 2026-07-19 18:15). |
| F3 fair ladder is the flagship lever — but its rows are pre-CL-056 (leaky agent), which the review itself flags in F2 | **Fair-ruler re-baseline + extension RUNNING** on laptop: fixed champion vs h800 @ 2752/5504/**11008**, n=400 paired each, one fresh band 24.0e9, deck-matched across rungs (`fair_ruler_rebase_*`). |
| M5 flywheel causal test (depth transfer, fresh bands, out-of-lineage anchor) | Substantially done pre-review: PROD_DEPTH washout + EXT132 fresh-band refutation + rodv2_iter02 anchor (CL-058). Batching-mode control (P1-S7) not yet run — folded into the probe queue below. |
| it16 retraction wording | Adopt the review's narrower wording: "did not replicate, did not survive production depth; any remaining shallow effect too unstable/small to matter" — NOT "proved pure noise". CL-058 stands otherwise. |

## Adopted queue (in order; cheap-first; no new training arcs)

1. **P1-L5 farm multi-field-city fixture** (subagent, launched 2026-07-19 eve): does the leaf's `counted_growth_cities` wrongly dedup one city across a player's DISTINCT farms? Engine ground truth first, then flat leaf. If confirmed → fix → re-sweep caps (house rule: bug fix shifts optima).
2. **Utility calibration audit** (subagent, launched 2026-07-19 eve): empirical P(win | margin, tiles-remaining) from existing shards vs the fixed tanh(m/15). GO = material, robust stage interaction → then (and only then) the one-knob online test at n=800.
3. **P0-lite release integrity** (engineering, delegable): executable champion factory (manifest that *instantiates* the agent + emits resolved hashes), semantic/property suite (dual-farm/same-city, crop boundary, key equivalence, rotation aliases, deck canonicalization, sign semantics), adversarial state replay. Fix the stale human harness path as part of this even though human play is parked. Gate: zero divergences before the next headline claim.
4. **Gate A — oracle-prior production-depth headroom**: champion pre-search at 2–4× budget → its root distribution as priors at production budget. Decides whether ANY policy-learning spend is rational. Kill: <+15 elo tight → prior channel capped at depth; the review's stop-rule #1.
5. **Candidate 1 — exact small-bag public-state oracle**: 150–250 late roots with 2–4 genuinely hidden draws (our old fairness probe had deck_len==1 — tested nothing), DP over the remaining multiset with explicit chance nodes; compare pooled-Q/pooled-N/coverage-corrected vs the exact public-state optimum. Decides whether PIMC strategy fusion is a real, recoverable cost. Go: ≥0.5 pts/root or ≥25% regret reduction paired.
6. **Gate B — fixed-root depth-transfer replay** k4×{200,344,688}: `scripts/measurement_infra` multi-depth snapshot search is purpose-built for this. Cheap; also separates the washout mechanism (early discovery vs Q convergence vs selector).
7. **Throughput program go/no-go (review P3 "buy fair simulations")**: gated on the ladder re-baseline landing — if the fixed-agent curve still rises at 5504/11008, search-core throughput (profile → port measured bottlenecks only) is the highest-confidence lever we own. Elo gain measured at equal wall-clock, never assumed.

## Adopted policies (effective immediately)

- **Sealed-band governance (review P6)**: three deck tiers — reusable dev bands / sealed one-use promotion bands (assigned after hashes freeze) / final claim band. A band that influenced a decision retires from confirmatory use. (Formalizes existing practice; governance/ to carry the tier registry.)
- **Depth-provisional rule** (already ours, now explicit): shallow gains are provisional until production-depth + equal-wall-clock survival.
- **Stage-3 value-unlock is RESHAPED**: not an unfreeze/blend/leaf-replacement. If it runs, it runs as the review's Candidate 4 — residual/uncertainty model, local public-state sibling-regret gate (≥25% better than the leaf, two seeds, no bad tails) BEFORE any games. Gated behind items 4–5.
- **k4×344 distillation fork**: allowed ONLY if Gates A+B fire; 2–3 iterations per arm, keep-best promotion, fresh bands. Not before.
- **Stop rules (review Part VII-A)** adopted as the closure standard for "self-learning dead at this scale" — six conditions, all must hold.

## Deferred / declined (with reasons)

- **n=1600 classical bundle (Candidate 5)**: adopted in principle, deferred until boxes are idle (~4 box-days); runs after the probes, not before.
- **Human benchmark + Stop-Rule B**: parked (Joshua constraint). Note the honest ceiling meanwhile: internal results are "plausibly strong", never "superhuman".
- **Full architecture rebuild (Part I §3.4 component-GNN + dynamic action head)**: not funded now; becomes relevant only if Gate C (target alignment) is reached.
- **Full-board no-crop representation rework (P1-R1..R4)**: the window audit (2026-07 Phase 0.2) measured 0/299k dropped legal actions on the production distribution, so the crop is not currently believed to bite; M1-style adversarial replay folds into P0-lite item 3 rather than a standalone campaign. The review's stronger claim (fail-loud on ANY dropped action) is adopted as an assertion in the factory.
- **Tie-epsilon asymmetry (P1-G1 tail), scalar redundancy (P1-R6), rotation-alias label fragmentation (P1-A3)**: logged to BACKLOG; below the current cost line.

## Corrections to the review's factual base (minor; do not change its conclusions)

- The fair ladder numbers it cites as F3 are pre-CL-056 (it acknowledges this in F2 but still headlines them); the re-baseline in flight replaces them.
- "Tree reuse +39.3" is clairvoyant-regime-scoped (the review notes this correctly).
- The review's "+120.8 vs h800" curve125 fair confirm row is also pre-fix-era; treat via the re-baseline, same as F3.
