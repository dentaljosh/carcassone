# RoD v2.8 Continuation Probe — Parent Matchups (Phase 4)

**The binding result.** `RoD_iter_01 + v2.8` vs frozen `ITER8_V28_PARENT` (= iter8 net + v2.8 leaf), net-vs-net, both NeuralMCTS@200, c_puct=3.0, residual_scale=0.25, **same v2.8 leaf both sides**, deck-paired both seats, fresh band 1922000000. Harness: `scripts/heuristic_v28/v28_net_vs_net_orch.{py,sh}` (two carc-orch SHM servers, one per checkpoint). Data: [`PARENT_MATCHUPS.csv`](PARENT_MATCHUPS.csv).

| n | W/D/L | winrate | Elo (A−B) | ±1σ | paired mean diff | paired z | by-seat (A@0 / A@1) |
|---|---|---|---|---|---|---|---|
| 200 (pilot) | 118/4/78 | 0.600 | **+70.4** | 25.1 | +4.33 | **+2.91** | 0.570 / 0.630 |
| **400 (confirm)** | 227/7/166 | 0.576 | **+53.4** | 17.6 | +3.68 | **+3.51** | 0.562 / 0.590 |

## Verdict: **RoD POSITIVE** (binding question)

`RoD_iter_01` beats the frozen `ITER8_V28_PARENT` by **+53.4 Elo (paired z = 3.51, n=400)** at equal (v2.8) leaf — well above the project's 2σ bar, consistent across both seats. The point estimate regressed from +70 (n=200, on the high side) to +53 (n=400) as expected; the effect is confidently positive (z=3.5 ⇒ >99.9%).

**This is the result the v2.7 substrate could not produce.** Every prior continuation on the v2.7 leaf — deeper-teacher (powered null vs iter8: +14.6/z0.65 @s200), the residual flywheel plateau (saturated iter5) — failed to beat its parent. One continuation iteration under the **v2.8 leaf** clears it decisively.

## Mechanism (hypothesis, to be tested by the ruler eval)

iter8's policy was distilled from **v2.7**-guided MCTS; its priors encode "good moves per v2.7." `RoD_iter_01` re-distilled 1000 fresh games of **v2.8**-guided MCTS, so its priors are aligned to the leaf they are now scored by at eval. The +53 is most simply read as **policy re-alignment to the stronger leaf** — not (yet) evidence that the learned components exceed the heuristic.

**Critical caveat — non-transitivity.** Rough Elo transitivity (parent was −38.4 vs `heur@3200_v28`; RoD is +53.4 vs parent) would put RoD ≈ **+15 vs heur@3200_v28** — i.e. matching/beating deep heuristic search at equal leaf. But the project has flagged the leaf/search effect as **non-transitive** (CLEAN_EVAL_AUDIT), so the +53-over-parent does NOT license that claim. The Phase-5 ruler eval (`RoD_iter_01 vs heur@3200_v28`, running) measures it directly:
- If RoD ≈ 0 or positive vs heur@3200_v28 → it genuinely closed the equal-leaf gap (strong result).
- If RoD still ≈ −38 vs heur@3200_v28 → the +53 is a non-transitive "tuned to beat iter8 specifically" artifact (weaker result).

## Decision-rule outcome

Per `PROBE_PLAN.md`: "Promising (pilot ≥ +12) → top up to n=400; z≥2 with point ≥ ~+24 = credible margin → RoD positive." Pilot +70/z2.9 → topped up → **+53.4 / z3.51 = credible margin ⇒ RoD POSITIVE.** Proceed to Phase 5 (ruler, running) and weigh iter2 (does it compound?).

**Provenance:** RoD_iter_01 sha `a8b824df…`; iter8 parent sha `0d355002…` (verified unchanged). Manifests under `v28_rod_probe/nvn_iter_01_mk20_vs_iter8_mk20_s200_rs025/`. MEASUREMENT ONLY — no promotion, PRODUCTION.yaml unchanged.
