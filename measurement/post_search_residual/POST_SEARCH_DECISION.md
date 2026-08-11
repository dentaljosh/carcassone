# Post-Search Residual / Adaptive Compute Pilot — DECISION

**Verdict: Decision C — the escalation signal is predictable, but a single trivial heuristic captures
it; learned ML adds no robust value, and the absolute magnitude is too small to expect game
conversion.**
**Concluded 2026-06-28 · branch `rod_v2_flywheel` · no games run, no cluster used, no production change.**

The reframe was correct and the opportunity is real, but "learning where shallow search is
insufficient" collapses to a one-line rule (`escalate when h200's top-2 moves are nearly tied in Q`),
and even a perfect oracle removes only a tiny absolute amount of regret.

## The 10 spec questions

1. **How often is h200 materially wrong vs h6400?** Rarely. On the real MCTS-play distribution:
   **positive_strong 2.8%** (q_gap≥0.02 ∧ regret≥0.02), positive_medium 5.2%, h200 agrees with h6400's
   top move **71%** of the time. Median regret(h200) = **0**; mean **0.0031** (tanh-Q); long-tailed
   (p99 ≈ 0.06). Phase-concentrated in the **opening**.
2. **Is the residual concentrated enough to predict?** **YES, extremely** — the worst **5%** of roots
   hold **67%** of all h200 regret; the worst 20% hold **99%**.
3. **Does an oracle adaptive strategy beat uniform compute?** **YES, decisively.** At matched
   avg-compute C=400 the oracle reaches **0.00017** (multi-depth) / 0.00073 (pairwise) vs uniform
   **0.00235** — **+92.5%**. The ceiling is high. (Stage-2 gate PASS on both greedy and MCTS roots.)
4. **Can a learned model predict useful escalations?** **YES, partially.** Best model = MLP over
   h200 diagnostics + Tier-B structural features: **AUROC(positive_strong) = 0.78**, and it beats
   uniform at matched compute **robustly** (bootstrap P=1.00 at C=400).
5. **Does learned adaptive beat simple heuristics like entropy?** **NO (not robustly).** The single
   best heuristic — **`low_top2gap`** (escalate when h200's top-2 backed-up Q are nearly tied) —
   already gets AUROC **0.73** and the MLP does **not** robustly beat it: bootstrap P(MLP beats
   heuristic) = **0.92 at C=400** (Δ +0.00023, **95% CI [−0.00009, +0.00059] crosses 0**) and **0.54
   at C=800**. Tier-A (no structural features) was even clearer — the heuristic *beat* every learned
   model. **ML adds no robust value over the one-line rule.**
6. **Does learned adaptive beat uniform at matched compute offline?** **YES robustly** (P=1.00 @C=400)
   — but so does the heuristic; this is the "predictable" half, not an ML win.
7. **Does implemented adaptive search match offline behavior?** **N/A — Stage 5 not run.** Gated out by
   Decision C (no ML scheduler worth implementing).
8. **Does adaptive search improve games at matched compute?** **N/A — not run** (Stage-6 spend gate;
   recommended against, see below).
9. **Is adaptive compute a viable *learned* contribution?** **No.** The opportunity is real but needs
   no learning (a single h200 statistic captures the predictable part), and the magnitude is tiny.
10. **Is any flywheel-like loop justified?** **No.** No ML flywheel (Decision C).

## Why C and not F — the two facts that kill the learned story

1. **A one-line heuristic captures the predictable signal.** `low_top2gap` (AUROC 0.73) ≈ the MLP
   with 21 structural features (AUROC 0.78); the MLP's matched-compute edge over it is within
   bootstrap noise (P=0.92 < 0.95, CI crosses 0; a tie at C=800). The roots where h200 is wrong are
   simply the roots where **h200 itself reports its top two moves are nearly tied in value** — no
   board understanding required. (Structural features nudge AUROC +0.05 but don't convert to a robust
   matched-compute win — echoes the feature-graph pilot: representation helps *ranking* but the gain
   is marginal and doesn't survive a strength-relevant test.)
2. **The absolute magnitude is tiny.** Mean h200 regret is **0.0031** tanh-Q; the *entire* oracle
   ceiling removes only ~0.0016 of it at C=400, and the achievable (heuristic/learned) slice is
   ~0.0003–0.0006. This is far below what a game screen can resolve, and it is exactly the
   **`b99c9ed` "root metrics don't convert"** pattern that has now recurred **four** times in this
   project (sims-washout, value/search autopsy, feature-graph, here).

## The conclusion to preserve (do not overstate)

This is **not** "adaptive compute resurrects a flywheel." The durable findings:

1. **The reframe is right and the opportunity is real but small.** Targeting `h6400 − h200` (the
   residual that survives shallow search) is the correct object, and an oracle that routes deep
   search to the worst ~5% of roots beats uniform compute by a large *relative* margin. Adaptive
   compute is a genuine *efficiency* axis.
2. **…but it needs no learning, and it is a compute-efficiency lever, not a strength lever.** The
   predictable part is one h200 statistic (top-2 Q proximity); ML/structural features add nothing
   robust. And the absolute regret removed is tiny — there is no reason to expect it to move games,
   and every prior "root metric improved" result in this project has failed to convert. A learned
   scheduler is not justified.

## Recommendation

**Stop. Decision C. Do not train an ML scheduler, do not run a flywheel.** v2.9 / `PRODUCTION.yaml` /
champion unchanged.

The one genuinely open question is narrow and is a **spend** gate: does even the *heuristic*
scheduler (`escalate h200→h800 when top-2 Q gap < τ`) beat uniform h400 in **actual games** at matched
average compute? My recommendation is **no, not worth it** — the offline matched-compute edge
(~0.0003 mean Q-regret) is below game-resolution and the `b99c9ed` prior is strong. Logged as a
**compute-efficiency** idea in BACKLOG (reach the same strength at fewer average sims), **not** a
strength play. If pursued anyway, it is a heuristic — not ML — scheduler, and needs a large-n paired
game screen to detect such a small effect.

## Artifacts

`POST_SEARCH_{PLAN,DATASET,BASELINES,BASELINES_mcts,TRAINING,OFFLINE_RESULTS}.md` ·
`{baselines,baselines_mcts,offline_adaptive}.json` ·
`data/{games_mcts,roots_mcts,roots_adaptive,features_mcts}.jsonl` (gitignored) ·
`scripts/post_search_residual/{gen_mcts_selfplay,build_adaptive_dataset,extract_root_features,
psr_lib,run_baselines,run_adaptive_gate}.py`.
Method note: lossless MCTS-game roots via recorded (deck-seed, action-sequence) replay; one
HeuristicMCTS(6400) search per root snapshotted at {200,400,800,1600,3200,6400} (bit-exact to
standalone h_L). Frozen v2.9 leaf (config_hash `7fc930b82801cb43`) throughout.
