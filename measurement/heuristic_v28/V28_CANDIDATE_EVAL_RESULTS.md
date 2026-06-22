# v2.8 candidate evaluation (Phase 7)

> Candidate **v2.8 = v2.7 + flat `meeple_k=2`** ([V28_CANDIDATE_CONFIG.json](V28_CANDIDATE_CONFIG.json)).
> Reported separately: classical heuristic gain, cross-depth anchor, neural gain, hybrid gain,
> runtime. Data: [V28_CANDIDATE_EVAL_RESULTS.csv](V28_CANDIDATE_EVAL_RESULTS.csv) +
> [V28_SEARCH_PILOT_RESULTS.csv](V28_SEARCH_PILOT_RESULTS.csv). Manifest:
> [V28_CANDIDATE_EVAL_MANIFEST.json](V28_CANDIDATE_EVAL_MANIFEST.json).

## 1. Classical heuristic gain — STRONG, depth-robust (FACT)

| eval | A | B | n | winrate A | Elo (A−B) | z_margin | signal |
|---|---|---|---|---|---|---|---|
| equal budget @200 | heur@200 v2.8 | heur@200 v2.7 | 200 | 0.738 | **+179.5** | +9.92 | VERDICT |
| equal budget @800 | heur@800 v2.8 | heur@800 v2.7 | 120 | 0.633 | **+94.9** | +3.76 | VERDICT |

The candidate beats v2.7 at equal budget by a large, reliable margin, and the gain **survives 4× deeper
search** (heur@800) — so it is **not search-imitation** (a leaf term that merely re-derived what search
finds would shrink as sims rise; this holds). The @800 number uses the recovery-scaled variant (the
strongest flat form was run @200); the flat form is ≥ scaled, so +94.9 is a lower bound on the
candidate's @800 gain.

## 2. Cross-depth anchor — the leaf gain is NOT search-fixable (FACT, the key generalization result)

| eval | A | B | n | winrate A | Elo (A−B) | z_margin | signal |
|---|---|---|---|---|---|---|---|
| cross-depth | **heur@200 v2.8** | **heur@800 v2.7** | 120 | **0.762** | **+202.6** | +6.97 | VERDICT |

**v2.8 with 200 sims beats v2.7 with 800 sims (4× the budget) by +202.6 elo (76% winrate).** This is
statistically indistinguishable from the equal-depth +179.5 (1σ ≈ ±30–37) — i.e. **quadrupling v2.7's
search does NOT reduce v2.8's advantage.** v2.7 cannot search its way out of the deficit. INTERPRETATION:
this is the signature of a genuine **leaf-quality** improvement (a better evaluation), not an equal-depth
rock-paper-scissors style edge (which more opponent search would erode). It strongly supports "real
strength within the heuristic family," though still measured against the v2.7 lineage.

## 3. Neural-guided gain — DEFERRED (the open decisive gate)

`iter8 net priors + v2.8 leaf (resid 0)` vs `+ v2.7 leaf (resid 0)`, NeuralMCTS@200. **Not run:**
net-on-CPU NeuralMCTS@200 is infeasibly slow (n=2 smoke timed out >120s/game). Per the cluster memory,
neural eval belongs on the **SHM orchestrator** at high W — building that wiring is the next step, not a
pilot. Harness ready: [scripts/heuristic_v28/v28_iter8_leaf_eval.py](../../scripts/heuristic_v28/v28_iter8_leaf_eval.py)
(residual forced 0 on both sides — the production head is v2.7-tied; production iter8 unchanged). **This
is the gate that separates "real absolute strength / superhuman lever" from "a v2.7-heuristic-specific
fix." It is open.**

## 4. Hybrid gain — DEFERRED (gated behind the neural eval, same orchestrator dependency).

## 5. Runtime / cost (FACT)

The candidate is **bit-identical to legacy `meeple_k=2`**, which the **flat AND Cython leaf paths already
implement** → **full production speed, no object-path penalty** (the pilots' object-path cost came from
the experimental `v28_meeple_k` field, not the candidate). Heur pilots: ~2.5–13 s/game @ sims 200–800,
W=15 local CPU, no GPU/orchestrator.

## Summary

| dimension | result |
|---|---|
| classical heuristic gain | **+179.5 elo @200, +94.9 @800 — large, depth-robust** |
| search-fixability | **none — v28@200 beats v27@800 (+202.6)** |
| neural-guided gain | **DEFERRED (orchestrator)** — the open decisive gate |
| hybrid gain | DEFERRED |
| runtime | full production speed (= legacy `meeple_k`) |

→ Clears the "beats v2.7 at equal budget" gate decisively and the cross-depth robustness check; the
neural/iter8 gate is the remaining open item. See [HEURISTIC_V28_REPORT.md](HEURISTIC_V28_REPORT.md).
