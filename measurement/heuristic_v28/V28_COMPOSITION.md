# v2.8 candidate composition (Phase 6)

> Compose the candidate v2.8 leaf from **ablation-survivors only**. v2.7 stays frozen; the candidate
> is opt-in. Config: [V28_CANDIDATE_CONFIG.json](V28_CANDIDATE_CONFIG.json).

## What goes in — and what does not

| patch | root audit (P4) | search pilot (P5) | mechanism (autopsy) | in candidate? |
|---|---|---|---|---|
| **meeple-economy (flat `meeple_k`)** | net +6 midgame (weak static) | **+179.5 elo @200 (z=9.9), +95 @800** | economy term real; recovery-scaling falsified | **YES** |
| completion (deck-aware closure) | endgame K2 exact +0.063 | **+3.5 elo (null full-game)** | supported but immaterial | **NO** (null full-game) |
| farm (majority gate) | broad degradation | not advanced | falsified (cap-masked) | NO |
| denial (asym opp cap) | no movement | not advanced | falsified (search phenomenon) | NO |

**Decision: the candidate v2.8 = v2.7 + the FLAT meeple-economy term** (`meeple_k`, recovery scaling OFF
— `v28_meeple_recovery_t0=0`). The recovery scaling I originally proposed is **excluded**: it detracted
~75 elo (+179 flat vs +105 scaled) and its mechanism was falsified by the autopsy counterfactual. This
is the single-patch outcome the taxonomy's "prefer small ablations" discipline points to — no blob.

`v28_completion` is **explicitly excluded** despite a clean exact-label endgame mechanism: it is null at
full-game equal budget (the gate). It remains documented as a real-but-immaterial endgame leaf fix that
could matter inside a hybrid-handoff or endgame-specialized search — not in the general leaf.

## The candidate leaf — definition

```
v2.8_candidate(state, player) = virtual_score_v2(state, player)            # v2.7, UNCHANGED
                              + k * (meeples[player] - meeples[opp])        # flat economy term, post-cap
```
**Equivalence (verified 560/560):** this is **bit-identical to v2.7 with the EXISTING legacy `meeple_k`
knob** (`_MEEPLE_K`, env `CARCASSONNE_V25_MEEPLE_K`) set to 2.0 — a knob committed since v3 but left at
0.0. `meeple_k` is already implemented in the object, flat, AND Cython leaf paths, so the candidate
needs **no new code and runs at full production speed**. The whole positive v2.8 finding therefore
reduces to: *the `meeple_k` knob, declared null at n=20 and OFF since v3, is +179 elo at n=200.* (The
`v28_meeple_k`/`recovery_t0` fields added this branch were only for the recovery-scaling experiment,
which hurt and is excluded.)

with `k` a small versioned constant. **`k` is NOT yet optimized** — k=2 tested strongest of {1,2}
(+179 vs +38), but the upper bracket (k=3,4) was not run and `HEURISTIC_VALUE_NORM=15` means k=2 is a
large leaf reweighting, so the optimum may differ. The candidate ships **k=2 as the working value**
with k-optimization flagged as a required step before any larger eval.

## Honest status of the candidate (gates the recommendation)

- **Established (FACT):** beats v2.7 at equal budget in paired full-game HeuristicMCTS (+179 @200,
  +95 @800) — robust, reproducible, overturns the n=20 null. This satisfies the FIRST promotion gate
  ("beats v2.7 at equal budget in paired full-game eval").
- **NOT yet established:** the SECOND gate ("improves or preserves iter8/hybrid when used as the leaf").
  The neural leaf-swap is the generalization test; net-on-CPU is infeasibly slow, so it is **deferred
  to the SHM orchestrator** (harness [scripts/heuristic_v28/v28_iter8_leaf_eval.py](../../scripts/heuristic_v28/v28_iter8_leaf_eval.py)
  ready). The cross-depth anchor (heur@200_v28 vs heur@800_v27) is the cheap within-family proxy —
  see [V28_CANDIDATE_EVAL_RESULTS.md](V28_CANDIDATE_EVAL_RESULTS.md).
- **Load-bearing caveat:** the gain is measured vs the v2.7 ruler and directly counters v2.7's known
  over-committed-meeples weakness; beating v2.7 is not proven absolute strength.

→ Per the decision gate this composes a **candidate worthy of EXPERIMENTAL-reference status pending the
neural/out-of-lineage generalization test** — NOT a production change, NOT a v2.7 replacement. See
[HEURISTIC_V28_REPORT.md](HEURISTIC_V28_REPORT.md) for the final recommendation.
