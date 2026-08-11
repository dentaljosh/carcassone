# Phase 3 — Full-Game Pilot Results

> **Measurement only.** Champion unchanged. The only NEW full-game pilot warranted by the audit was
> the **residual isolation**; the hybrid matchups (#4, #5 of the brief) and the iter8-vs-heur facts
> are **reused** from prior verdicts (not re-run). Dynamic-hybrid pilots were **skipped** (Phase-4
> gate not cleared). Manifest: [FULLGAME_PILOT_MANIFEST.json](FULLGAME_PILOT_MANIFEST.json). Numbers:
> [FULLGAME_PILOT_RESULTS.csv](FULLGAME_PILOT_RESULTS.csv).

## New pilot — residual isolation (FACT)
`iter8@resid0.25` vs `iter8@resid0.0`, paired, both seats, fresh band **b360** (seed-start 3.6e9 —
NOT the spent sealed panel), n=200, identical net forward (only `residual_scale` differs), via
carc-orch on **local (W=28) + laptop (W=24)** work-stealing. Wall ≈ 25 min combined.

| split | n | W/D/L | winrate | avg diff (A−B) | elo | paired margin | paired z |
|---|---|---|---|---|---|---|---|
| **OVERALL** | 200 | 110/0/90 | 0.550 | +1.945 | **+34.9** | **+1.945** | **+1.518** |
| resid0.25 as seat 0 | 100 | 51/0/49 | 0.510 | +0.34 | +6.9 | — | — |
| resid0.25 as seat 1 | 100 | 59/0/41 | 0.590 | +3.55 | +63.2 | — | — |

Pilot ladder (cost discipline trail): n=20 preliminary was **−1.45 / z=−0.39** (10 decks,
noise-dominated) → **n=200 reverses it to +1.945 / z=+1.518**. This is exactly why n=20 is a screen,
not a verdict.

**Verdict (INTERPRETATION):** the residual head is a **small POSITIVE full-game lever (+35 elo)** at
the production depth — directionally consistent with its "validated lever" status — but **z=1.518 is
below the 2σ bar** (project rule: a ~35-elo effect needs n=400 to be a verdict). **Suggestive, not
conclusive.** Strong seat asymmetry (seat0 +6.9 vs seat1 +63.2 elo) is absorbed by the seat-balanced
paired statistic. **Non-transitive with the root metric:** residual *hurts* per-move deep-teacher
imitation (ROOT_ACTION_AUDIT §2) yet *wins games*. ⇒ keep residual_scale=0.25; do not drop it; a
n=400 top-up (resumable) is the recommended optional firm-up. See
[RESIDUAL_ROLE_AUDIT.md](RESIDUAL_ROLE_AUDIT.md).

## Reused full-game facts (NOT re-run — cited)
| matchup | n | elo | paired margin | paired z | source |
|---|---|---|---|---|---|
| HYBRID_K8 vs ITER8_PROD | 400 | +20.9 | +1.31 | +5.79 | [LEVEL2_HYBRID_VERDICT.md](../level2/LEVEL2_HYBRID_VERDICT.md) |
| HYBRID_K8 vs HEUR_3200 | 200 | −19.1 | −0.76 | −0.51 | LEVEL2_HYBRID_VERDICT.md |
| HYBRID_K5 vs ITER8_PROD | 200/400 | +10.4 | +0.80/+0.90 | +3.45/+6.23 | LEVEL2_HYBRID_VERDICT.md |
| HYBRID_K5 vs HEUR_3200 | 200 | −13.9 | −0.43 | −0.30 | LEVEL2_HYBRID_VERDICT.md |
| ITER8_PROD vs HEUR_800 | 400 | **+58.7** | — | — | PRODUCTION.yaml (champion validation) |
| ITER8_PROD vs HEUR_3200 | 200 | −28.7 | — | −0.70 | LEVEL2_HYBRID_VERDICT.md |

**Reading (INTERPRETATION):** the reused full-game ladder is the **non-transitivity anchor** for the
whole audit — iter8 *beats* heur@800 (+58.7) while *losing* to it on root imitation, and the fixed-K
hybrid is gap-closing (beats iter8, loses to heur@3200). The new residual pilot adds: the value head
is a small positive on top of this, not the source of iter8's strength.

## Skipped (gate not cleared)
**HYBRID_PHASE_DYNAMIC / HYBRID_SHARPNESS_DYNAMIC** — Phase-4 routing analysis found no cheap signal
beats always-heur@800 at the root (0.659 vs 0.658); a dynamic rule collapses to "more heuristic" =
the fixed-K sweep. No full-game spend justified ([ROUTING_RULE_ANALYSIS.md](ROUTING_RULE_ANALYSIS.md)).
