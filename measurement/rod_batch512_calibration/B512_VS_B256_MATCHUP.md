# rod_batch512_calibration — Phase 5: B512 vs B256 (THE key calibration matchup)

**Question:** is the batch-512 net as strong as the validated batch-256 reference, head-to-head? `ROD_ITER1_B512_TEST + v2.8` vs `ROD_ITER1_B256_REFERENCE + v2.8`, net-vs-net, both NeuralMCTS@200, c_puct=3.0, residual_scale=0.25, **same v2.8 leaf both sides**, deck-paired both seats, **fresh band 1923000000**. Harness: `scripts/heuristic_v28/v28_net_vs_net_orch.{py,sh}` (Rust carc-orch SHM, work-stealing local W48 + laptop W16). Sign: diff = A−B, so **elo<0 ⇒ B512 weaker**. Data: [`B512_VS_B256_MATCHUP.csv`](B512_VS_B256_MATCHUP.csv).

| n | W/D/L | winrate | Elo (B512−B256) | ±1σ | paired mean | paired z | by-seat (A@0 / A@1) | signal |
|---|---|---|---|---|---|---|---|---|
| 200 (screen) | 95/6/99 | 0.490 | −6.9 | 24.6 | −0.99 | −0.64 | 0.510 / 0.470 | inconclusive |
| **400 (confirm)** | 194/10/196 | 0.497 | **−1.7** | 17.4 | −0.44 | **−0.41** | 0.542 / 0.453 | **tie** |

## Verdict: B512 ≈ B256 in direct play — a statistical TIE

Head-to-head, the batch-512 net is **indistinguishable from the batch-256 reference: −1.7 Elo (paired z = −0.41, n=400)**, the point estimate converging on zero (−6.9 → −1.7 as n doubled). The two siblings play at equal strength against each other. **So the policy under-fit visible in training (val_pol 0.435 vs 0.270, Phase 3) did NOT translate into a head-to-head strength loss** — MCTS@200 search laundered the less-converged priors, consistent with the project's standing "per-move policy precision ≠ whole-game strength."

Power: n=400 paired resolves to ≈ ±12 Elo (1σ), so we can rule out B512 being worse than B256 by more than ~24 Elo (2σ). The true direct gap is small.

## The catch — non-transitivity (this is the scientifically important part)

The head-to-head tie **contradicts the parent-relative margins**:

| | vs frozen parent (n=400) | direct head-to-head |
|---|---|---|
| B256 | **+53.4** (z3.51, decisive) | — |
| B512 | **+10.4** (z1.65, inconclusive) | — |
| B512 − B256 | predicted by transitivity: **−43** | **measured: −1.7 (tie)** |

A ~41-Elo non-transitivity gap, now well outside noise (the direct measure is ±17 at n=400; −43 is >2σ away). **B512 ties the validated B256 head-to-head, yet lost B256's decisive edge over the parent (iter8).** Reading: B256's policy, distilled to a sharper optimum, acquired a *specific exploitative edge against iter8* that the under-converged B512 policy lacks — but that edge does not generalize, so head-to-head the two are even. This corroborates the project's repeated finding that **parent-relative Elo is a non-transitive, unreliable proxy for sibling strength.**

## Bearing on the decision (full reasoning in the Phase 7 report)

- **"B512 similar to B256 within noise"** — ✅ satisfied (tie).
- **"…AND beats frozen parent"** — ❌ NOT satisfied (B512 vs parent inconclusive at z1.65).
- The decision-rule branch "if B512 fails to (credibly) beat parent → reject 512 for RoD" fires — but is now in tension with the direct tie. The honest resolution (Phase 7): B512 is **strength-neutral head-to-head but not validated against the fixed references** (fails the parent gate; under-trains the policy; untested vs the heuristic ruler where B256 reached parity). Net call: **keep batch 256 for the clean RoD lineage.**

**Provenance:** B512 sha `9cca3edf…`; B256 sha `a8b824df…`. MEASUREMENT ONLY — no promotion, PRODUCTION.yaml unchanged, v2.7 frozen.
