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

## Follow-on

The chain is being **extended to iter_30** (latest-chain continuation from iter_10, `DO_SMOKE=0`, gen W28/8, no deadline) — the bet that more iterations eventually push past parity. All iter_11…iter_30 checkpoints will be retained for the same keep-best + ruler eval. Given the first 9 iters peaked at parity (iter_08), this is exploratory, not promotion-grade.

**Artifacts:** `evals/iter{04,07,08,10}_vs_iter01_n100/`, `evals/iter{08,10}_vs_iter01_n400/`, `evals/iter08_vs_heur3200_v28/`. Harnesses: `scripts/rod_v28/run_overnight_evals.sh` (net-vs-net 2-box), `scripts/rod_v28/run_heur_eval.sh` (ruler 2-box).
