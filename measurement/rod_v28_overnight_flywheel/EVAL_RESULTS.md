# RoD v2.8 Overnight Flywheel — EVAL RESULTS (iters 02–10)

**Date:** 2026-06-23 · **Branch:** rod_v28_overnight_flywheel · MEASUREMENT ONLY — no promotion, PRODUCTION.yaml unchanged, champion unchanged, v2.7 frozen.

## What was evaluated

The overnight flywheel ran **9 latest-chain iterations (RoD_iter_02 → RoD_iter_10)** warm-from RoD_iter_01, v2.8 leaf, batch 256, 3 epochs, 400 games/iter — all HEALTHY, no collapse. All checkpoints retained for after-the-fact keep-best. Candidates picked by cheap diagnostics: **iter_04** (early), **iter_07** (middle), **iter_08** (best per-iter smoke), **iter_10** (endpoint).

## 1. Candidate vs RoD_iter_01 (net-vs-net, v2.8 leaf, paired, NeuralMCTS@200)

elo sign: candidate − RoD_iter_01 (>0 ⇒ candidate stronger).

| candidate | n=100 screen | **n=400 (binding)** | read |
|---|---|---|---|
| iter_04 (early) | −17.4 / z−0.90 | — | ~tied/slightly below |
| iter_07 (middle) | −24.4 / z−0.29 | — | ~tied/slightly below |
| **iter_08** (best) | +49.0 / z1.05 | **+33.1 / paired_z +2.00** (217W/4D/179L) | **modest, ~2σ-credible gain** |
| iter_10 (endpoint) | +77.7 / z2.28 | **+21.7 / paired_z +0.69** (211W/3D/186L) | **~tied** (screen was noise) |

**Findings:**
- The n=100 screens **overstated** the effects (regression to the mean — the +77.7 endpoint screen collapsed to +21.7/z0.69 at n=400).
- The chain produced a **modest, real** internal gain: **iter_08 is the best checkpoint, +33.1 elo / paired_z +2.00** over RoD_iter_01 — small but credible (right at the 2σ bar).
- The gain is **not monotonic to the end**: iter_04/07 ≈ tied, iter_08 peaks, iter_10 (endpoint) regresses back to ~tied. Keep-**best** ⇒ iter_08, not the latest.

## 2. Best candidate vs the ruler — iter_08 vs heur@3200_v2.8 (n=800, VERDICT)

| matchup | winrate elo | paired margin | verdict |
|---|---|---|---|
| iter_08 vs heur@3200_v2.8 (**n=800**) | +6.5 (z+0.53) | **−0.38 (z−0.48)** | **TIE** (402W/11D/387L) |
| _n=200 screen (deflated)_ | +15.6 (z+0.64) | −1.46 (z−0.83) | tie |
| _ref: RoD_iter_01 vs same ruler (n=800)_ | +16.5 (z1.34) | −0.36 (z−0.47) | TIE |

**iter_08 reaches PARITY with deep-heuristic search but does NOT exceed it — virtually identical to RoD_iter_01** (paired margins −0.38 vs −0.36). Confirmed at **verdict power (n=800)**: both stats |z|<1, the n=200 screen's marginal +15.6 deflated to +6.5. The continuation's "decisive open test" (does a later iter push *above* heur@3200_v28?) is answered a clean **no** for the first 9 iters.

## Verdict

- **The chain compounded a modest internal gain** (best = iter_08, +33 elo / z2.0 over RoD_iter_01) — but **non-transitively**: that gain **washed out against the external ruler**, leaving iter_08 at the *same parity* with heur@3200_v2.8 that RoD_iter_01 already had.
- **Structural blocker #2 stands:** the learned agent reaches deep-heuristic level at equal leaf but has **not crossed above** it. Not superhuman (hand-crafted ruler, no human anchor).
- **Nothing promoted.** iter_08 is the keep-best checkpoint of this batch but is not a champion (parity ≠ exceed). Champion stays `flywheel2_champion_iter8`.

## W lessons applied (per-workload, all RAM-monitored)

| workload | W (local/laptop) | live RAM headroom | note |
|---|---|---|---|
| self-play GEN (orch) | 28 / 8 | ~17 / ~4 GB | W48 gen OOM'd (38GB RSS) — workers carry a position buffer |
| net-vs-net EVAL (2 contexts) | 48 / 16 | ~21 / ~4 GB | same W48 but ~24.8GB RSS — eval workers lighter |
| heur@3200 EVAL (mixed neural+CPU) | 24 / 8 | ~23 / ~3 GB | flat-leaf 3200-trees are light (~540MB/worker), NOT the old W=20-OOM profile |

Codified in `docs/CLUSTER_OPS.md` "Worker counts — GEN W ≠ EVAL W".

## Follow-on — TAIL EVAL (iters 11–17) + early-iter completeness (02/03), 2026-06-23

The chain was **extended iter_11→iter_17** then stopped (target had been 30). Those tail iters
were initially `DO_SMOKE=0` (unevaled); this section is the **after-the-fact tail eval** plus the
early iters 02/03 for completeness. All numbers in `experiments/results.csv` (`rod_ov_*_n100` /
`*_n384`); n=100 are SCREENS (±35 elo, coarse).

**vs RoD_iter_01 (n=100 screen; elo = candidate − RoD1):**

| iter | elo | paired_z | read |
|---|---|---|---|
| iter_02 | +20.9 | +0.17 | tied |
| iter_03 | −3.5 | +0.40 | tied |
| iter_11 | +96.2 | +1.18 | looks strong but **inflated** (see h2h below) |
| iter_13 | +17.4 | +0.83 | ~tied |
| iter_15 | +3.5 | −0.32 | tied |
| iter_17 | +41.9 | +0.69 | positive; best tail contender |

**vs the keep-best iter_08 (the decisive test — does the extension beat it?):**

| iter | n | elo | paired_z | verdict |
|---|---|---|---|---|
| iter_11 | 100 | **−56.1** | −1.80 | **LOSES** — its +96-vs-RoD1 was non-transitive noise |
| iter_13 | 100 | −13.9 | +0.56 | tie (wash) |
| iter_17 | 100 | +13.9 | −0.74 | tie (wash) — best contender |
| **iter_17** | **384** | **+6.3** | **−0.16** | **TIE at verdict power** (40-min timeout clipped from 400) |

**Verdict: the extended chain (11–17) does NOT beat iter_08.** The strongest-vs-RoD1 tail iter
(iter_11) *loses* head-to-head to iter_08; iter_13/iter_17 tie; the best contender (iter_17) ties
at n=384. Combined with the early/middle iters (02/03/04/07 all ~tied/below RoD1) and iter_10
(tied), **the whole chain hovers at RoD1/heuristic level; iter_08 remains the lone 2σ point and
the keep-best, sitting at heur@3200 parity without exceeding it.** Nothing promoted; champion +
PRODUCTION.yaml unchanged. All 16 continuation checkpoints retained.

**Note (2-box tally):** the early 2-box screens (iter_15/17) first reported clipped n (72/80) from a
premature-tally race in the shared-claim path (no completion barrier — diagnosed 2026-06-23, work-
stealing distributes fine, 32/68 split, but each box tallies on its own pass-completion). All were
re-tallied to full n after both boxes drained. Fix tracked separately (drain-to-completion barrier
+ shorter claim-stale-secs).

**Artifacts:** `evals/iter{02,03,04,07,08,10,11,13,15,17}_vs_iter01_n100/`, `evals/iter{08,10}_vs_iter01_n400/`,
`evals/iter{11,13,17}_vs_iter08_n100/`, `evals/iter17_vs_iter08_n400/`, `evals/iter08_vs_heur3200_v28/`.
Harnesses: `scripts/rod_v28/run_overnight_evals.sh` (vs-RoD1 2-box), `scripts/rod_v28/run_screens_vs_base.sh`
(vs-iter08, parameterized baseline), `scripts/rod_v28/run_heur_eval.sh` (ruler).
