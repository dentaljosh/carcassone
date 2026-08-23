# L2 Hybrid-Handoff Verdict — can iter8 early/mid + deep heuristic endgame combine?

**Status: COMPLETE (Phase 1 + Phase 2, 2026-06-19). VERDICT: iter8's endgame weakness is locally
PATCHABLE (hybrid beats iter8, reproduced n=400 z≈+6) but the patched hybrid is GAP-CLOSING, NOT a
new champion — neither hybrid:5 nor hybrid:8 beats heur@3200 (both lose at |z|<1). Deep heuristic
remains strongest.** Measurement only — no training, no promotion. Champion of record unchanged
(iter8, [governance/PRODUCTION.yaml](../../governance/PRODUCTION.yaml)).

**ANNOTATED → SUPERSEDED (2026-08-23, D1, TRACK_D_PREP_2026-08-23 §3.2, CL-026):**
"deep heuristic remains strongest" is falsified as a top-of-ecosystem claim by
CL-043 (the PUCT-priors flip, 2026-07-07); the hybrid's subject (iter8) is
retired lineage two evidence-epochs back. Not re-run — no live consumer.

## Question
Joshua's hybrid-handoff experiment: does iter8's early/midgame policy strength combine with deep
heuristic endgame precision? Motivated by L2-3 (iter8 plays the endgame *worst*, top-1 0.667 @ K=2)
and #8 (iter8 −28.7 Elo vs heur@3200; heur@3200 = the strongest directly-tested practical
full-game ruler — best at K=4, but NOT universally best across K=2/K=3/K=4 exact top-1; see
[measurement/pre_tool_audit/EVIDENCE_HYGIENE_NOTES.md](../pre_tool_audit/EVIDENCE_HYGIENE_NOTES.md)).

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

## Phase 2 — hybrid:K vs heur@3200 (COMPLETE, n=200 paired, b340). The champion question.
Auto-gated (auto_phase2): K=8 and K=5 cleared (paired_z≥1.5 vs iter8, top-2). Plus n=400 top-ups of the
vs-iter8 bands (reproduce Phase 1).

| Hybrid vs heur@3200 | W/D/L | winrate | Elo | paired margin | paired z |
|---|---|---|---|---|---|
| K≤5 → heur@3200 | 94/4/102 | 0.480 | −13.9 | −0.43 | −0.30 |
| K≤8 → heur@3200 | 92/5/103 | 0.472 | −19.1 | −0.76 | −0.51 |

- **VERDICT: gap-closing, NOT a new champion.** Both hybrids *lose* to heur@3200, but at |z|<1 — a
  statistical tie-to-slight-loss. They are **modestly closer to heur@3200 than plain iter8 is** (iter8 vs
  heur@3200 = −28.7 Elo, z=−0.70 — itself a tie-to-slight-loss, so all three are |z|<1 vs the deep
  heuristic): the early/mid iter8 policy + deep-heuristic endgame closes most of iter8's gap to the deep
  heuristic, but does not surpass it. The deep heuristic remains the strongest practical agent.
- **Interpretation-table row hit:** "Hybrid ties/loses heur@3200 → deep heuristic remains strongest."
  Promotion rule (beat iter8 same-band paired AND beat heur@3200) NOT met → **nothing promoted** (as specified).
- **Phase 1 reproduced at n=400** (vs iter8): K≤5 margin +0.90 **z=+6.23**, K≤8 margin +1.32 **z=+5.79**
  — the PATCHABLE finding is robust. Note the small raw-Elo (+6) vs large paired-z: the hybrid reliably
  wins a *small per-game margin* (decisive on the paired statistic) that doesn't swing the winrate much.

## Reproduce / inspect (run is complete)
```
python scripts/level2/report_hybrid.py --root /mnt/c/carc-shared/level2_hybrid          # full table (authoritative)
```
All bands at final n (vs-iter8 topups n=400, vs-heur3200 n=200). Numbers above + in results.csv `l2hyb_*`.

## Cluster note (2026-06-19)
Phase 2 runs **local solo** (RTX 5060 Ti, orch W=48). The laptop (mobile 4070, W=26) was pulled after two
transient GPU compute stalls (carc-orch `cmp` spiked 2.4ms→3316ms → 60s worker timeout → BrokenServerError;
`set -e` aborted its launcher). Per-game JSONs are cached/resumable; relaunching the laptop later would
work-steal via `--shared-claim`. iter8 forwards batch on the SHM server; the v2.7 leaf + heur@3200 search
run on worker CPU (in orch mode workers block on the GPU-forward queue → high W is well-utilized; the
deep-heur bands are more CPU-bound so per-game wall is ~20–35s amortized vs ~8s for the neural bands).
