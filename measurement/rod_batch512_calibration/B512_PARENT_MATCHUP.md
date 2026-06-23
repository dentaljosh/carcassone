# rod_batch512_calibration — Phase 4: B512 vs Frozen Parent

**Question:** does the batch-512 sibling still produce a child that beats the frozen `ITER8_V28_PARENT`? `ROD_ITER1_B512_TEST + v2.8` vs `iter8 + v2.8`, net-vs-net, both NeuralMCTS@200, c_puct=3.0, residual_scale=0.25, **same v2.8 leaf both sides**, deck-paired both seats, **band 1922000000** (the SAME decks as the B256-vs-parent matchup → directly comparable). Harness: `scripts/heuristic_v28/v28_net_vs_net_orch.{py,sh}` (Rust carc-orch SHM, work-stealing local W48 + laptop W16). Data: [`B512_PARENT_MATCHUP.csv`](B512_PARENT_MATCHUP.csv).

| n | W/D/L | winrate | Elo (A−B) | ±1σ | paired mean | paired z | by-seat (A@0 / A@1) | signal |
|---|---|---|---|---|---|---|---|---|
| 200 (screen) | 104/2/94 | 0.525 | +17.4 | 24.6 | +3.27 | +2.06 | 0.470 / 0.580 | inconclusive |
| **400 (confirm)** | 203/6/191 | 0.515 | **+10.4** | 17.4 | +1.87 | **+1.65** | 0.487 / 0.542 | **inconclusive** |
| _ref: B256 vs parent (n=400, same decks)_ | 227/7/166 | 0.576 | **+53.4** | 17.6 | +3.68 | **+3.51** | 0.562 / 0.590 | positive |

## Verdict: B512 does NOT credibly beat the frozen parent (inconclusive at n=400)

`ROD_ITER1_B512_TEST` clears the frozen `ITER8_V28_PARENT` by only **+10.4 Elo (paired z=1.65, n=400)** — **below the 2σ bar, statistically inconclusive**: at n=400 we cannot even confirm B512 > parent. The point estimate decayed from +17.4 (n=200) to +10.4 (n=400), the expected regression of a small/near-zero effect at higher n.

**The comparison that matters is against B256 on the identical decks:** the batch-256 reference beat the same parent by **+53.4 / z=3.51** — a decisive, ~5× larger margin. So:

- **The policy under-fit (Phase 3: val_pol 0.44 vs 0.27) translated into a large loss of playing strength — it did NOT wash out under MCTS@200 search.** B512 retains only ~+10 of B256's ~+53 advantage over the parent (roughly a **−43 Elo** swing).
- This already satisfies the Phase-5 decision rule's reject branch ("if B512 fails to (credibly) beat parent → reject 512 for RoD"), but the direct B512-vs-B256 matchup (Phase 5) quantifies the gap and guards against any non-transitive artifact.

**Transitivity prediction for Phase 5:** B512−B256 ≈ (B512−parent) − (B256−parent) = +10.4 − 53.4 = **≈ −43 Elo** (B512 weaker). Phase 5 measures it directly.

**Provenance:** B512 sha `9cca3edf…`; iter8 parent sha `0d355002…` (frozen, unchanged); B256 ref sha `a8b824df…`. MEASUREMENT ONLY — no promotion, PRODUCTION.yaml unchanged, v2.7 frozen.
