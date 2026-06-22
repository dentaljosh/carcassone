# Phase 4 — Routing-Rule Analysis

> **Measurement only.** Offline analysis on the 1000-position root-audit join; no game playing.
> Artifact: [ROUTING_RULE_ANALYSIS.csv](ROUTING_RULE_ANALYSIS.csv), built by
> `scripts/search_policy_mixing/routing_analysis.py`. **FACT** vs **INTERPRETATION** kept separate.
> **The metric here is root teacher-imitation (agreement with heur@3200), which is non-transitive
> with full-game strength** — see ROOT_ACTION_AUDIT.md ⚠️ box. This phase decides whether a *dynamic*
> handoff has root-level headroom over the *fixed-K* rule; the full-game verdict is the hybrid one.

## Key question
> Is fixed K≤8 already close to optimal, or is there evidence for a better dynamic handoff?

## (1) Do cheap signals SEPARATE iter8's root-error? — FACT: yes, several do
P[iter8 ≠ teacher] across signal quartiles (baseline P[iter8 err] = 0.513):
| signal | Q1(low) | Q2 | Q3 | Q4(high) | spread |
|---|---|---|---|---|---|
| **noresid visit-concentration** | 0.695 | 0.591 | 0.463 | 0.287 | **0.408** |
| **policy_top1_prob** | 0.649 | 0.540 | 0.476 | 0.386 | 0.264 |
| policy_entropy | 0.438 | 0.412 | 0.568 | 0.635 | 0.223 |
| k_remaining | 0.580 | 0.515 | 0.500 | 0.390 | 0.190 |
| n_legal | 0.404 | 0.515 | 0.558 | 0.591 | 0.187 |
| v27_gap | 0.621 | — | 0.310 | 0.091 | (monotone) |
| abs_score_diff | 0.449 | 0.480 | 0.539 | 0.596 | 0.146 |

**FACT:** iter8's own search/policy uncertainty (**visit-concentration**, then **policy top-1
prob**) predicts its root-error better than k_remaining does. When iter8 is decisive (high visit
concentration) it errs 29% of the time; when unsure, 70%. **INTERPRETATION:** the model "knows when
it's unsure," and that signal is sharper than the positional `k_remaining` the fixed-K rule uses.
This is the *only* encouraging routing result — but see (2).

## (2) Does any router BEAT "always heur@800" at the root? — FACT: no (no headroom)
Threshold router (use heur@800 when the signal crosses its best threshold, else iter8):
| router signal | best agree | heur coverage |
|---|---|---|
| always-iter8 (baseline) | 0.487 | 0.000 |
| always-heur@800 (baseline) | **0.658** | 1.000 |
| policy_top1_prob | 0.659 | 0.987 |
| noresid visit-concentration | 0.659 | 0.990 |
| v27_gap | 0.658 | 0.994 |
| k_remaining / n_legal / entropy / score-diff | 0.658 | ~1.000 |
| **oracle** (per-pos best of iter8/heur800) | **0.727** | — |

**FACT:** every signal's *optimal* router routes **~99–100% to heur@800** and lands at **0.658–0.659
≈ always-heur@800**. The best real router beats always-heur by **+0.001**. The fixed-K sweep is
monotone in heur coverage (K≤10 → 0.536 @ 20% cov; K≤40 → 0.629 @ 80% cov), i.e. **more heuristic =
better imitation, all the way up**. Even a *perfect* iter8/heur@800 router caps at **0.727** (≈
heur@1600 0.715) and no cheap signal approaches it (best 0.659).

**INTERPRETATION:** at the per-move imitation level there is **no headroom for a dynamic router** —
because heur@800 ≥ iter8 in **every** stratum (ROOT_ACTION_AUDIT §5), the cost-optimal per-move
policy is "use the deeper search," and the dynamic signals only tell you *how often iter8 will be
wrong*, not *a pocket where iter8 is right and heuristic is wrong*. The 0.408-spread visit-concentration
signal sorts iter8's errors but never finds iter8 > heur, so it cannot improve a router.

## Answer to the key question (INTERPRETATION)
> **Fixed K≤8 is not "optimal" — but no dynamic root-level rule beats it for the reason that matters:
> the hybrid's whole premise (hand the endgame to deep search) is already the dominant per-move
> policy, and pushing *more* of the game to deep search monotonically improves per-move imitation.**
> The fixed-K rule is a *coarse* version of "use deep search late"; a sharpness-dynamic rule would,
> on this evidence, simply route *more* to the heuristic (converging to "mostly heuristic"), which is
> exactly the fixed-K sweep with larger K. That is **not a new hybrid** — it is the existing finding
> that **deep heuristic dominates** (LEVEL2_HYBRID_VERDICT: fixed-K is gap-closing, not champion;
> "a cheap heur@800 endgame captures most of the gain").

## Why this does NOT kill iter8 (the non-transitivity, restated — INTERPRETATION)
The router analysis optimizes **teacher-imitation**, on which heur dominates. But **full-game**, iter8
(resid 0.25) beats heur@800 (+58.7 elo) and heur@1600. So "route everything to heur@800" would be a
*worse full-game agent* than iter8 despite better per-move imitation — the metric is non-transitive.
**Conclusion:** the routing evidence says a *dynamic hybrid optimized on cheap root signals* has no
justification to build (no offline headroom, no full-game pilot signal beyond the fixed-K verdict);
it does **not** say iter8 should be replaced by the heuristic. The two live roles for iter8 remain
**standalone full-game agent** and **early-leg of the fixed-K hybrid** — neither needs a dynamic router.

## Decision (gates from the brief)
- **HYBRID_PHASE_DYNAMIC / HYBRID_SHARPNESS_DYNAMIC:** ❌ **do not pilot.** Offline gate not cleared —
  no signal beats always-heur@800 at the root (+0.001), the rule collapses to "more heuristic" = the
  fixed-K sweep, and the fixed-K full-game verdict is already gap-closing-not-champion. Building a
  dynamic router would duplicate an already-stronger baseline (the brief's explicit *stop* condition).
- **Fixed K≤8 stands** as the best-characterized hybrid; no dynamic variant is justified by this data.
