# HEURISTIC v2.8 — final report

> **Branch:** build & test a stronger heuristic leaf (v2.8) via controlled ablations, classical-engine
> progress first. **v2.7 frozen forever; v2.8 opt-in; production champion + defaults UNCHANGED; no
> training, no flywheel, no promotion to production.** FACT vs INTERPRETATION marked. Numbers cite
> artifact rows. Commits: `cf28e41` (P0-3), `3343a27` (P4+autopsy), `5ef216f` (P5), + this.

## TL;DR

The v2.8 branch found **one real, large, reproducible heuristic-leaf improvement**: a **flat
meeple-economy term** (`meeple_k`) — **+179.5 elo (z=9.9) at heur@200**, **holding at heur@800
(+94.9, z=3.8)** in paired full-game HeuristicMCTS vs v2.7. It is **bit-identical to the legacy
`meeple_k` knob that has been OFF since v3 and was wrongly declared "null" at n=20** (DECISIONS
2026-05-14); at proper power it is a major gain, and it runs at full production speed (flat/Cython
already implement it). Three other candidate patches were **killed** (farm, denial, completion).

**BUT** this is measured **against the v2.7 ruler in heuristic search**, and the term directly counters
v2.7's known *over-committed-meeples* weakness — so beating v2.7 is **not yet proven absolute strength**.
The generalization gate (does it help the neural production policy / an out-of-lineage reference) is
**not yet run** (net-on-CPU infeasible → deferred to the SHM orchestrator). **Recommendation:
EXPERIMENTAL reference, pending the neural leaf-swap + k-optimization. Do NOT promote to production or
replace v2.7.**

---

## The 11 questions

**1. v2.7's most credible failure modes?**
From the Phase-1 taxonomy ([V27_FAILURE_TAXONOMY.md](V27_FAILURE_TAXONOMY.md), 678 mined cases): ~67%
of v2.7's disagreements with stronger references are **structural/positional / search-horizon — NOT
leaf-addressable**. The credible *leaf-addressable* failures are: **(a) over-committed meeples** (no
meeple-economy term — confirmed the big one), **(b) endgame phantom-closure credit** (fixed schedule
ignores deck supply — real but immaterial full-game), (c) contested-field farm overvaluation (real but
cap-masked). v2.7-static ≈ iter8 at root selection (both ~0.48 vs the teacher); deeper *search* on the
same leaf is what closes the gap.

**2. Which candidate patches were tested?** Four: `v28_farm` (majority-gated farm-growth), `v28_completion`
(deck-aware closure), `v28_meeple` (recovery-scaled meeple economy), `v28_denial` (asymmetric opp cap).
(M5 scarcity / M6 phase held — taxonomy weak/speculative.)

**3. Which survived the root-action audit?** ([V28_ROOT_AUDIT.md](V28_ROOT_AUDIT.md)) `v28_completion`
(endgame K=2 exact top-1 0.763→0.826) and `v28_meeple` (weak, net +6/1000). **Killed:** `v28_farm`
(broad degradation, cap-masked) and `v28_denial` (no movement — pre-committed kill).

**4. Which survived low-budget search?** ([V28_SEARCH_PILOT_RESULTS.md](V28_SEARCH_PILOT_RESULTS.md))
**Only `v28_meeple`.** `v28_completion` is **null full-game** (+3.5 elo, z=1.09) despite its exact
endgame mechanism — the endgame-local gain washes out (hybrid-handoff lesson). `v28_meeple` is **+105.6
@200 and +94.9 @800** (survives depth = not search-imitation). Disentangle: the **FLAT** term
(+179.5) ≫ recovery-scaled (+105.6) — recovery scaling detracts.

**5. Was a v2.8 candidate composed?** Yes ([V28_COMPOSITION.md](V28_COMPOSITION.md)): **v2.8_candidate =
v2.7 + flat `meeple_k=2`** (single patch; = the existing legacy knob). `v28_completion` excluded (null);
farm/denial killed.

**6. Does v2.8 beat v2.7 at equal search budget?** **YES, decisively** — +179.5 elo (z=9.9) @200,
+94.9 (z=3.8) @800, paired n=200/120 ([V28_SEARCH_PILOT_RESULTS.csv](V28_SEARCH_PILOT_RESULTS.csv)).
Cross-depth anchor: **v28@200 beats v27@800 (4× budget) by +202.6 elo, z=7.0, 76% wr** — quadrupling
v2.7's search does NOT close the gap, the signature of a genuine leaf-quality gain (see
[V28_CANDIDATE_EVAL_RESULTS.md](V28_CANDIDATE_EVAL_RESULTS.md)).

**7. Does v2.8 improve iter8 when used as the leaf?** **NOT YET TESTED.** The neural leaf-swap requires
the SHM orchestrator (net-on-CPU NeuralMCTS@200 timed out >120s/game). Harness built
([scripts/heuristic_v28/v28_iter8_leaf_eval.py](../../scripts/heuristic_v28/v28_iter8_leaf_eval.py));
**deferred** as the next step. This is the **decisive generalization gate** and is open.

**8. Does v2.8 improve hybrid?** Not tested (gated behind the neural eval — same orchestrator dependency).

**9. Is the gain robust enough for a larger evaluation?** **Yes for the heuristic-search claim** (z=9.9
@200, holds @800, reproducible, overturns the n=20 null). **No for an absolute-strength claim** until
the neural leaf-swap + an out-of-lineage anchor confirm it. k is not optimized (k=2 strongest of {1,2};
upper bracket unrun).

**10. Should v2.8 become a reference ruler, stay experimental, or be killed?** **EXPERIMENTAL
reference** — see the gate below. It clears the "beats v2.7 at equal budget" gate but NOT the
"improves/preserves iter8 as leaf" gate (untested). Promote to experimental, hold on production/ruler
status.

**11. Next branch?** Priority order: **(a) the orchestrator-based neural leaf-swap** (iter8 net + v2.8
leaf vs + v2.7 leaf — the gate for real strength); **(b) k-optimization** (sweep k∈{2,3,4,6}, with cap
interaction); **(c) an out-of-lineage anchor** (does heur@200_v28 beat heur@3200_v27 / approach the
neural champion?); then, if all hold, **(d) a larger powered eval** and **(e) neural distillation from
the v2.8 leaf** (retrain a value/policy on v2.8-leaf search — the path to a learned component exceeding
the heuristic). If the neural gate fails, the finding stands as "a v2.7-heuristic-specific fix, not a
superhuman lever."

---

## Decision gate (from the task)

**Promote to EXPERIMENTAL reference if:** beats v2.7 at equal budget paired full-game ✅ (+179/+95);
doesn't badly degrade exact/K diagnostics ✅ (meeple term: root audit minimal degradation, v27_correct
0.985; endgame exact unchanged); improves/preserves iter8/hybrid as leaf ⚠️ **UNTESTED**; understandable
& reproducible ✅ (one knob, = legacy `meeple_k=2`); v2.7 frozen ✅ (parity proven, 184 tests).
→ **Clears 4/5 gates; the iter8/hybrid gate is open. Verdict: EXPERIMENTAL, pending the neural test.**

**Do NOT promote (to production/ruler) because:** the gain is vs the v2.7 ruler only (not an independent
anchor); it may partly exploit v2.7's over-commitment style; neural generalization untested; k unoptimized.
**Explicitly NOT done:** no production change, no PRODUCTION.yaml edit, no v2.7 modification, no training.

## Mechanism honesty (the autopsy discipline)

The largest gain came from the patch whose *originally-hypothesized* mechanism (recovery scaling) was
**falsified** ([MECHANISTIC_AUTOPSIES.md](MECHANISTIC_AUTOPSIES.md)): the win is the **plain meeple-economy
term**, not the scaling. This is logged as mechanism-CORRECTED (economy term supported by the
over-commitment failure mode + depth-robustness), not "empirical gain, mechanism unclear" — the
disentangle pinned the mechanism. The one patch with a clean *exact-label* mechanism (`v28_completion`,
deck-aware closure) was **strategically immaterial** full-game. Two lessons reproduced: endgame-local
leaf gains don't move full-game Elo; and underpowered (n=20) screens hide real levers.

## Artifacts
P0 [REUSE_AND_SCOPE.md](REUSE_AND_SCOPE.md) · P1 [V27_FAILURE_TAXONOMY.md](V27_FAILURE_TAXONOMY.md) +
[V27_FAILURE_CASES.csv](V27_FAILURE_CASES.csv) · P2 [V28_PATCH_PROPOSALS.md](V28_PATCH_PROPOSALS.md) ·
P3 [V28_VARIANT_REGISTRY.md](V28_VARIANT_REGISTRY.md) + [V28_VARIANT_CONFIGS.json](V28_VARIANT_CONFIGS.json)
+ [tests/test_v28_variants.py](../../tests/test_v28_variants.py) · P4 [V28_ROOT_AUDIT.md](V28_ROOT_AUDIT.md)
+ [autopsy](MECHANISTIC_AUTOPSIES.md) · P5 [V28_SEARCH_PILOT_RESULTS.md](V28_SEARCH_PILOT_RESULTS.md) ·
P6 [V28_COMPOSITION.md](V28_COMPOSITION.md) + [V28_CANDIDATE_CONFIG.json](V28_CANDIDATE_CONFIG.json) ·
P7 [V28_CANDIDATE_EVAL_RESULTS.md](V28_CANDIDATE_EVAL_RESULTS.md).
