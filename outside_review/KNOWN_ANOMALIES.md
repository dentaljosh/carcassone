# KNOWN_ANOMALIES — things that do not fit our current explanation

These are observations a reviewer should weigh independently. Each is stated as a
FACT first, then our current (tentative) explanation, then what is still unexplained.
Ordered roughly by how load-bearing they are.

---

## A1. The same checkpoint swung +181.7 → +25.2 elo from a "non-strength" change
- **Fact:** iter_11 vs HeuristicMCTS, matched c=3.0/sims=200: **+181.7 elo / 9.2σ** on the River+buggy game (`ladder_iter11_vs_heuristic_n400`, 2026-05-31) vs **+25.2 elo / 1.45σ** on the base-only bug-fixed game (`ladder_iter11_vs_heuristic_baseonly_n400`, 2026-06-02). Same net, same harness.
- **Current explanation:** River ruleset + farm-scoring bug + iter_11 being on-distribution for the game it trained on, together inflated the old number ~7×.
- **Still unexplained / unsettling:** a 9.2σ "trustworthy absolute signal" (its own results.csv note) evaporated to insignificance from changes that were not supposed to touch strength. This is a direct demonstration that **a high-σ result against our own reference can be almost entirely artifact.** It should lower confidence in *every* current vs-HeuristicMCTS number, including the +86.9 and the residual +46.5.

## A2. Rising value-head correlation never once translated into search usefulness
- **Fact:** the value head was driven 0.18 → 0.464 → 0.81 → 0.84 (outcome/Q correlation) across multiple rebuilds (Path B, search_value, search_value_tree, +global-pool). At **every** level the value-as-leaf result was a liability: blend λ=0.5 ≈ −24 to −38, λ=1.0 ≈ −552 to −604. Kendall-τ on sibling ranking stayed ≈ 0.08 (chance) even for a head with corr 0.86 that was explicitly trained to mimic the v2.7 leaf.
- **Current explanation:** outcome-correlation is the wrong gauge; what a leaf needs is *local sibling ranking*, and MSE regression cannot produce it regardless of target.
- **Still unexplained:** why MSE-on-the-optimal-target (mimic v2.7, which itself ranks at τ=0.58) collapses to τ=0.08. If the target ranks well and the head fits the target at corr 0.86, the head "should" inherit some ranking. The loss-form explanation is plausible but not mechanistically proven — and the value-loss is also ~5–10× under-weighted in the gradient (G-T2), a confound never removed before declaring "MSE can't rank."

## A3. Search beyond a point stops helping vs a fixed reference — but we cannot tell artifact from saturation
- **Fact:** Curve A (iter_01 @ sims {50,100,200,400,800} vs fixed heur@200): −74, +49, +35*, +85, +70. The top is flat. (*the s200 +35 is a known noise-low draw; confirmed +87.)
- **Current explanation:** flat top is a *weak-fixed-reference artifact* — you can't widen a margin against a shallow opponent — NOT saturation. (Initially mis-called as saturation, then corrected.)
- **Still unexplained:** iter_01's own *matched-depth* scaling is unmeasured. The only matched-depth evidence (iter_11 ladder: +25@200 → +57@800) is a different checkpoint and only ~1.5σ at the low end. So "more search should help" is asserted, not demonstrated, for the current best net.

## A4. Old checkpoint ties / beats newer ones; the chain is non-monotonic
- **Fact:** (a) Option-B chain: B2/B3/B4 each "+" over predecessor, but B4 vs iter_01 = −19.1. (b) Anchor-fraction: iter_4 "+39 over iter_11" but iter_4 ≈ iter_11 on the independent ladder (−16.6, tied) and iter_0 ≈ iter_5 (−24.4). (c) policy_scale: 7 iterations warm-from-latest *eroded* +87 → pooled +38.
- **Current explanation:** self-anchored / lineage-relative elo magnetizes (RPS-style self-specialization, anchor-overfit); without a keep-best ratchet the chain random-walks downward.
- **Still unexplained:** the *mechanism* by which iterating clean-data policy training on its own sims=200 visit targets makes the policy weaker (the "distill-down" hypothesis is unconfirmed). A reviewer should note the system has **never demonstrated a multi-iteration climb in absolute strength** — every climb is either single-step or self-anchored.

## A5. The flywheel regressed on iter 1, then "recovered" on iter 2 — but only back to iter 0
- **Fact:** residual flywheel gate (seed 900k, n=300): iter0 +116.5 → iter1 +66.8 (−50, "co-adaptation destabilized the policy: scale0 +75→+35") → iter2 +125.7 (+9.2 over iter0 = tied within ±21).
- **Current explanation:** co-adaptation training is unstable; the residual is a static asset that doesn't compound.
- **Still unexplained:** why iter1 craters the *policy* (scale0 dropped +75→+35) when the only change was putting the residual leaf into self-play. A 50-elo policy regression from one iteration of co-adaptation is large and not understood; "destabilized" is a label, not a diagnosis.

## A6. A lone parameter spike that defined production for weeks turned out to be noise — twice
- **Fact:** (a) "c=3.0 = +47.2 elo / 2.8σ" (2026-05-26) was promoted as a free win; re-validated at n=1600 → **+18.5** (≈40% was regression-to-mean). (b) "c=2.0 = +18pp" unpaired screen *reversed* to −17.4 when paired. The project's own "noise signature" rule (a lone value beating its neighbors by >1σ) was written *because of* these.
- **Still unsettling:** these are the spikes that were *caught*. The same dynamic (single screens at z≈1.4–1.9 promoted to "findings") is visible in the current residual story — the lever-1 screen was +68.3, the confirm +35.5, pooled +46.5. The pooled z=2.29 is barely a verdict, and the σ doesn't credit pairing in either direction cleanly.

## A7. Clairvoyant search is "not a strength lever" yet the value targets are trained on clairvoyant outcomes
- **Fact:** clairvoyant-vs-fair screen (n=76) = 0.474, dead even → future-sight declared non-load-bearing for search strength. Yet the value head's training targets (final score, or root.Q from a clairvoyant tree) are produced *by* the clairvoyant search.
- **Current explanation:** future-sight bites value-*learning* (single-future high-variance labels), not search strength.
- **Still unexplained:** the n=76 screen is small (±0.5σ resolution is poor) and was on the River game; it has not been re-run on base. The conclusion "future-sight is not load-bearing" rests on one underpowered screen that gates a whole demoted workstream (chance nodes).

## A8. HeuristicMCTS — the yardstick — used a DIFFERENT leaf than the agent — ✅ CONFIRMED + QUANTIFIED 2026-06-07
- **Fact:** `HeuristicMCTS._rollout` (`mcts.py:298-304`) evaluated leaves with **v1** `virtual_score`; the neural agent's leaf is **v2.7** (`virtual_score_v2`, cap=12, drop-3-open, closure bonuses). The docstrings (`mcts.py:288`, `eval_net_vs_heuristic.py:6,9,156`) claimed both sides share the v2.7 leaf.
- **RESOLVED (measured):** re-ran the headline cell with the opponent given the matched v2.7 leaf — **iter_01 vs HeuristicMCTS, n=400 paired, seeds 700000+: +86.9 (v1 opp leaf) → +48.1 ± 17.5 (v2.7 opp leaf).** Matching the leaf cost **−38.8 elo (~45% of the headline)**. The learned policy edge is **real and positive (+48.1, 2.7σ)** but about half the headline. Fixed `d472d10` (`heur_leaf` option, default v1 for comparability; docstrings corrected). Row `results.csv: r1_iter01_vs_heuristic_v27leaf_baseonly_s200_n400`.
- **Why it mattered:** the "+25/+57/+87 vs HeuristicMCTS" numbers were intended to isolate the learned *policy* at a matched leaf; ~45% of each was the v2.7-vs-v1 leaf gap, not the policy. So every absolute vs-HeuristicMCTS number in the river/base ledger is inflated by roughly this factor and should be mentally discounted ~45% until re-run with `--heur-leaf v2_7`.
- **Process note:** the n=70 interim read was −55 elo (looked like a collapse-to-negative); it regressed to +48 by n=400. A textbook small-n noise spike — and a reminder that the same caution applies to *this* package's interim readings.

## A9. The eval seed floors overlap the self-play seed range
- **Fact:** self-play seed = `iter*10_000 + game_idx`; `eval_net_vs_heuristic` defaults `--seed-start 600000` and `ladder_asymmetric` 800000. Deck = f(seed) via global `random.shuffle`. So an eval at seed 600000 uses the *same deck* the net saw at iter 60, game 0.
- **Current explanation:** the head-to-head script was bumped to 1e9 (G-M6 fix); the ladder/odometer were not.
- **Still unexplained / open:** how many of the strength evals (which floors, which iters) actually overlapped trained-on decks. For runs that trained past iter ~60, the ladder number is potentially inflated by train/test contamination and nobody has quantified it.

## A10. Performance depends on box/mode/worker-count in ways that kept reversing
- **Fact:** the "optimal" self-play config flipped repeatedly: orchestrator W=48/96 (cloud) → orch-off W=14/16 (local) → "+87% mixed-mode" (later labeled river-era and superseded) → per-box W=14/10/20. fp16 was "dead" then "batch-conditionally faster on Blackwell/Ada."
- **Current explanation:** the bottleneck is the CPU v2.7 leaf, not the GPU, so orchestrator IPC is pure overhead locally; cloud (48-core) had a different profile.
- **Why a reviewer cares:** throughput configs are a moving target tuned by benches that themselves shifted with the game change. None of this affects *correctness*, but it means wall-clock/compute-budget figures across the project are not comparable.

---

## Cross-cutting note
Anomalies A1, A6, A8, A9 are all **measurement** anomalies; A2, A4, A5, A7 are **learning** anomalies. The project's own read is that measurement is the #1 blocker. A reviewer who trusts that framing should still note that the measurement anomalies (A8 especially) have not all been closed, so even the "we measured X" statements that drive strategy may rest on a contaminated ruler.
