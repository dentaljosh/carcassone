# M2 — Sample the never-run canonical-AZ cell, solver-scored (runbook)

**Status:** SCOPED — build after M1/M3 (biggest reopener). Plan:
[docs/POST_REVIEW_PLAN.md](../../docs/POST_REVIEW_PLAN.md) §4. Scoped 2026-07-01 (subagent read-only pass).

**Question.** The cell {sighted CNN × pooled value head × non-degenerate target × sound low-sim improvement} — the
closest thing to actually running AlphaZero here — has never been sampled (every lineage net used a saturated/
0.5%-variance target, `value_global_pool=False`, blind rep). M2 samples it and scores it **against the exact solver**
(not the 0.995-circular h6400), adjudicating §3A's "residual value is ~1-D" (itself h6400-scored → suspect).

## PART A — the solver-scoring harness (the non-circular through-line fix — build FIRST, reusable everywhere)
`scripts/level2/endgame_solver.py`: `solve(game, board, mode="marginalized"|"clairvoyant", budget=4M, alphabeta=False)
-> SolveResult`. **`SolveResult.child_values`** = exact value of EVERY legal root action (enables per-move regret);
`regret_of(res, action)` computes it. Leaf value = real final score-diff (`flat_base_score`) → does NOT correlate
with the v2.9 leaf → **breaks the circularity.**
- **Cost/solve (measured):** K=2 ~4.5s · K=3 ~80s · K=4 ~21min median (7.4hr max). **Marginalized (bag-expectation)
  tractable only at K≤2** (== clairvoyant there); K=3 marginalized ~71/150; K=4 marginalized intractable (needs
  make/unmake, BACKLOG). So K≥3 solver-scoring = clairvoyant labels.
- **K≤4 positions already exist — reuse the sibling sets, NO new gen:** a 120-root replay of the 10,067 h6400_v2.9
  sibling roots → **K≤4 = 24.2%, K≤2 = 15.0%** (~2,400 / ~1,500 roots re-scorable on the SAME positions the h6400
  labels cover = direct de-circularization). Roots reconstruct via `replay_to(seed,ply)`; compute k_remaining
  post-replay. (`l23_positions.jsonl` at K=2..6 is the purpose-built alternative.)
- **Harness = ~120–180 LOC glue:** reuse `solve`/`regret_of` + `step1_train.py::group_metrics` (argmax-regret/top-1/
  kendall-τ + α-sweep) + `endgame_regret.py::_eval_one`'s scoring pattern. Only new piece = swap the target from
  `oracle_q` to solver `child_values` + a K≤4 replay filter. **This is the standing methodological fix — build it
  once, use it for §5A-tempo re-scoring, §3A re-adjudication, and M2's read-out.**

## PART B — M2 training wiring
| Ingredient | Wired? | Flag / location | Build? |
|---|---|---|---|
| Sighted CNN (+3 farm planes, 32 bag hist) | helpers exist, **NOT wired** into net/gen/train | `step1_planes.py::farm_connectivity_planes` / `bag_histogram` | **YES — the plumbing (biggest item)** |
| `--global-pool` + warm-value-fresh | **YES** | `train_iter.py --global-pool --warm-value-fresh`; `CarcassonneNet(value_global_pool=True)` | flag-flip |
| `score_diff_wide` target | **YES** | gen `run_selfplay_iter.py --value-target score_diff_wide`; train `--value-loss-weight 1.5` | flag-flip |
| Gumbel @64–150 sims | **NO** (mcts.py = PUCT+Dirichlet only) | — | build ~150–300 LOC **or fall back to PUCT@200** |
| warmstart + short-loop launcher | **YES** | `scripts/rod_v2/run_rod_v2_flywheel.sh` (set START/ITERS, DO_SMOKE=0) | parameterize |

**Per-iter eval:** `scripts/eval_net_vs_heuristic.py --n 200 --sims 200 --heur-sims 3200`. ⚠️ **`--heur-leaf` offers
only v1/v2_7 — no `v2_9`** → "h3200_v2.9" isn't a flag today; use v2_7@3200, add a v2_9 choice (small), or use the
RoD-v2 iter_02 anchor. (Decision.)

**Biggest blocker:** the sighted input-shape change (78→81 ch, 10→42 scalars) breaks arch-compat with EVERY existing
checkpoint → M2 needs a **fresh warmstart** on a re-dumped sighted representation (no trunk warm-from). That's the
main reason this cell is "never-run." **Recommended MVP:** flip global-pool/score_diff_wide/launcher + PUCT@200 (skip
Gumbel), build the sighted plumbing + fresh warmstart, 3–5 iters, gate offline **against the solver on the K≤2
marginalized sibling subset** (cheap, non-circular).

## Read-out (solver-scored, not h6400)
- **Success:** rs-sweep {0,0.25,0.5} shows a monotone ≥2σ paired game effect at any point (first in project history),
  OR solver-τ>0.5 with value-outcome corr>0.6 on fresh-band games → autopsy §7 "M2 fires". 
- **Kill:** head inert (rs-sweep flat, solver-τ<0.3) with all ingredients fixed → inertness is architecture-
  independent at this scale → autopsy §7 "all-kill"; CL-039 gains real support. Expect a real chance of KILL (the
  leaf may capture most of the additive value). This adjudicates; it does not resurrect.

MEASUREMENT ONLY — no champion/PRODUCTION.yaml/v2.7/v2.9 change. Contributes to CL-042 (autopsy; CL-041 = S1 promotion).

## Cost + go/no-go (updated post-M3, 2026-07-02) — the decision Joshua weighs before launch

**M3 sharpens M2's question.** M3 (n=400) showed the *weak* weaned value (τ≈0.43) craters MCTS (0.265) but recovers
to **parity** (0.496) with FPU=0.6 — FPU removes the value's *harm* but can't manufacture *help* from a value weaker
than the τ≈0.895 leaf. **So M2's real question is now precise: can a *better* value — sighted rep × pooled head ×
non-degenerate target (`score_diff_wide`) — with **FPU=0.6 installed**, EXCEED the leaf (>0.50), not just tie it?**
The FPU fix is now a *fixed ingredient* of the M2 loop, not a variable.

**Cost (the "separate, larger budget decision" the plan flagged):**
- **Build ≈ 1–2 days eng** — dominated by the sighted-plane plumbing (`encode_board`→`CarcassonneNet` 78→81ch /
  10→42 scalars → gen → train, ~200–400 LOC + tests) + a **fresh warmstart** (the input-shape change breaks
  arch-compat with every checkpoint → no warm-from; re-dump the sighted heuristic-labeled dataset + train warmstart).
- **Cluster ≈ 15–25 box-hours** — fresh warmstart (~a few hr) + a 3–5-iter loop (per iter: gen ~1–1.5 h, train
  ~30 m, per-iter eval n=200 vs h3200 ~30 m → ~2–3 h/iter) + the rs-sweep {0,0.25,0.5} game read-out. ~1 day on
  local+laptop work-stealing.
- **Total ≈ 2–3 days** (mostly the build).

**Honest prior on the outcome — a real chance of KILL:** §3A found the residual value space collapses to ~1
dimension across scalar AND structured heads (though h6400-scored → M2 re-checks it solver-scored); the leaf is a
strong decomposable τ≈0.895 ranker that **nothing in the program has beaten**; and M3's "recovery" was to parity via
FPU-*neutralization*, not value-*driving*. So M2 may well return "even the canonical cell can't exceed the leaf" →
CL-039 gains real, earned support (scoped closure). **M2 adjudicates the reopening; it does not presume it resurrects.**

**Why it's still worth it (the case for launch):** it is the **closest-to-real-AlphaZero cell never sampled** here,
and superhuman-via-learned-value is the project's primary goal — the one question the whole ledger left structurally
open (every prior net had a degenerate target / pooling-off / blind rep). A clean KILL *earns* the route closure the
autopsy currently can't write; a fire genuinely revives the flywheel. Either way it resolves §7. **Recommend: launch,
eyes open to a likely null — but decide as an explicit ~2–3-day budget commit, not a silent continuation.**


## Read-out protocol (PRE-REGISTERED 2026-07-03 — thresholds fixed before the numbers)

After the loop, evaluate checkpoints **iter_01 / iter_03 / iter_05** (a TRAJECTORY — shows compounding, not a lone final point; Joshua's call). The per-iter in-loop eval (vs RoD-v2 iter_02) is a *policy* health check, **NOT** the verdict. The verdict is two reads:

**(1) PRIMARY - solver-scored value ranking (non-circular).** `solver_score.py` (b0e7158) on each net's **value head**: sibling-ranking regret + Kendall-tau vs the exact K<=4 solver (ground truth, uncorrelated with the leaf). Read across 1->3->5 for improvement. Solve the ~1,119 K<=2 roots ONCE (~1-2 h, or reuse cache), then score 3 nets = minutes; add K=4 clairvoyant (~21 min/solve) only if K<=2 is ambiguous.

**(2) CONVERSION - residual-scale game sweep.** For each of 1/3/5, blend value into the leaf at **rs in {0, 0.25, 0.5}** with **FPU=0.6**, play n=200. Opponent = a **FIXED rung, never the moving parent**: sweep vs **RoD-v2 iter_02** (net -> orch-fast) for the trajectory; confirm the winning rs at the strongest iter vs **h_v2.9@3200** (the real deep-classical bar). 3 iters x 3 rs = 9 runs, orch across local+laptop ~= 2 h.

**Pre-registered verdict:**
- **FIRE (value exceeds the leaf):** solver-tau beats the leaf AND improves 1->3->5, AND a monotone **>=2sigma paired game gain** on the rs-sweep at some iter -> first in project history -> the flywheel revives; iter_5 seeds a real Section-10(b) run. Autopsy Section-7 = reopening confirmed.
- **KILL (ranks-but-doesn't-convert, or flat 1->3->5):** solver-tau <= leaf, or rs-sweep game effect <2sigma / non-monotone -> even the canonical AZ cell can't beat the tau~0.895 leaf -> CL-039 upgrades "premature" -> "earned, scoped closure".
- **Total cost ~= half a day**, mostly parallel. Single read-out at the pre-registered n; no peeking/cherry-picking.
