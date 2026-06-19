# L2 Hybrid-Handoff Verdict — can iter8 early/mid + deep heuristic endgame combine?

**Status: Phase 1 COMPLETE (verdict in). Phase 2 RUNNING (local solo, ~2h ETA as of 2026-06-19 ~22:4x UTC).**
Measurement only — no training, no promotion. Champion of record is unchanged (iter8, [governance/PRODUCTION.yaml](../../governance/PRODUCTION.yaml)).

## Question
Joshua's hybrid-handoff experiment: does iter8's early/midgame policy strength combine with deep
heuristic endgame precision? Motivated by L2-3 (iter8 plays the endgame *worst*, top-1 0.667 @ K=2)
and #8 (iter8 −28.7 Elo vs heur@3200; heur@3200 most endgame-precise).

## Harness (committed, d654082)
- [scripts/level2/eval_hybrid_handoff.py](../../scripts/level2/eval_hybrid_handoff.py) — paired-band
  head-to-head between `iter8` / `heur@N` / `hybrid:K:N`. Reuses ladder_rung_eval's paired-z/elo stats
  and endgame_regret's iter8 construction (residual_scale=0.25 in code, v2.7 env). carc-orch SHM support
  (`--shm-eval-server`).
- **Handoff semantics (latched, turn-atomic):** the hybrid plays iter8's policy until its FIRST own
  TILES-phase decision with `k_remaining <= K`, then switches to HeuristicMCTS@N for that tile AND every
  decision after. `k_remaining = len(deck) + (1 if next_tile else 0)` — IDENTICAL to
  gen_endgame_positions.k_remaining, so "K≤2" here == the L2-3 K=2 band. Verified: heur-moves/game == K
  exactly, latched in 200/200 games every band.
- Launchers: [run_hybrid_bands_orch.sh](../../scripts/level2/run_hybrid_bands_orch.sh) (orch, PH=1 vs iter8 /
  PH=2 vs heur@3200 + topup), [auto_phase2.sh](../../scripts/level2/auto_phase2.sh) (autonomous gate),
  aggregator [report_hybrid.py](../../scripts/level2/report_hybrid.py). Unit tests:
  tests/test_hybrid_handoff_trigger.py.
- Band: fresh **b340** (seed-start 3,400,000,000), n=200 paired, shared decks across all agents.
  Results dir: `/mnt/c/carc-shared/level2_hybrid/` (per-band `summary.json` = machine-readable authority).

## Phase 1 — hybrid:K vs iter8 (n=200 paired, b340). VERDICT: PATCHABLE.
| Hybrid (vs iter8) | W/D/L | winrate | Elo | paired margin (pts/game) | paired z |
|---|---|---|---|---|---|
| K≤2 → heur@3200 | 97/8/95 | 0.505 | +3.5 | +0.36 | +2.65 |
| K≤3 → heur@3200 | 96/8/96 | 0.500 | +0.0 | +0.25 | +1.18 |
| K≤5 → heur@3200 | 100/6/94 | 0.515 | +10.4 | +0.80 | +3.45 |
| K≤8 → heur@3200 | 103/6/91 | 0.530 | +20.9 | +1.36 | +4.68 |
| K≤5 → heur@**800** (sanity) | 101/5/94 | 0.517 | +12.2 | +0.60 | +2.89 |

- **Every hybrid beats iter8 on paired margin, monotone in K** (+0.36 → +0.80 → +1.36). iter8's endgame
  weakness IS locally patchable; the more endgame handed to the deep heuristic, the bigger the edge.
- **Reproduced at n=400:** K≤8 vs iter8 top-up → +1.31 pts/game, **paired z=+5.61** (vs +1.36/z=4.68 @ n=200).
- Effect is real but **modest in absolute terms** (best +1.36 pts/game, winrate 0.530).
- Compute sanity: heur@**800** endgame captures most of the gain (K5 +0.60 vs +0.80 for @3200) — a cheap
  heuristic endgame is most of the win; depth adds a little.

## Phase 2 — hybrid:K vs heur@3200 (RUNNING, local solo). The champion question.
Auto-gated (auto_phase2): K=8 and K=5 cleared (paired_z≥1.5 vs iter8, top-2). Running:
- `hybridK8h3200__vs__heur3200_b340_n200`, `hybridK5h3200__vs__heur3200_b340_n200` (n=200) +
  n=400 top-ups of the vs-iter8 bands (done for K8; K5 pending).
- **The disambiguation:** iter8 is −28.7 Elo vs heur@3200. If hybrid:8 ≈ heur@3200 (tie), iter8's early/mid
  adds nothing the deep heuristic lacks (gain was just "use more heur"). If hybrid:8 > heur@3200, the
  combination is genuinely better → new practical champion (would need a 2nd-band reproduction before any
  promotion). Expected (rough transitivity −28.7 + ~21): hybrid:8 still *loses* to heur@3200 but closes
  most of the gap.

## To resume / get the final verdict
```
python scripts/level2/report_hybrid.py --root /mnt/c/carc-shared/level2_hybrid          # full table
tail -f /mnt/c/carc-shared/level2_hybrid/local_phase2.log                                # progress
```
Phase 2 complete when `hybridK{8,5}h3200__vs__heur3200_b340_n200` each have 200 seed-files and
`hybridK5h3200__vs__iter8_b340_n200` has 400. Then read the heur@3200 bands' paired_z for the champion verdict.

## Cluster note (2026-06-19)
Phase 2 runs **local solo** (RTX 5060 Ti, orch W=48). The laptop (mobile 4070, W=26) was pulled after two
transient GPU compute stalls (carc-orch `cmp` spiked 2.4ms→3316ms → 60s worker timeout → BrokenServerError;
`set -e` aborted its launcher). Per-game JSONs are cached/resumable; relaunching the laptop later would
work-steal via `--shared-claim`. iter8 forwards batch on the SHM server; the v2.7 leaf + heur@3200 search
run on worker CPU (in orch mode workers block on the GPU-forward queue → high W is well-utilized; the
deep-heur bands are more CPU-bound so per-game wall is ~20–35s amortized vs ~8s for the neural bands).
