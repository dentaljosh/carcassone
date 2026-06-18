# Verdict — clean iter8 vs iter12 (2026-06-17)

Pre-registration: [ITER8_VS_ITER12_PROTOCOL.md](ITER8_VS_ITER12_PROTOCOL.md). Raw:
[ITER8_VS_ITER12_RESULTS.csv](ITER8_VS_ITER12_RESULTS.csv) + per-game JSON + manifests in
`/mnt/c/carc-shared/iter8_vs_iter12/{i8_s200,i12_s200,i8_s800,i12_s800}`. All four cells
provenance-verified at runtime (manifest checkpoint sha: iter8 `0d355002`, iter12 `059e394c`).

## Result (fresh band 2.5e9, n=400 paired, vs HeuristicMCTS@800-v2.7, residual 0.25)

| plane | iter8 | iter12 | **paired Δ(iter12−iter8)** | z | W/D/L (i12) |
|---|---|---|---|---|---|
| **s200** | +72.2 ± 17.7 | +86.9 ± 17.9 | **+14.6 elo** | **0.65** | 246/6/148 |
| **s800** | +142.1 ± 18.8 | +154.5 ± 19.1 | **+12.4 elo** | **0.51** | 280/7/113 |

Pre-registered thresholds: STRONGER = Δ≥+24 & z≥2.0; TIE = |Δ|<24 & |z|<2.0; top-up if
Δ∈[15,30] & z∈[1.3,2.3]. **Both planes fall in the TIE band; neither qualifies for top-up**
(z≪1.3). These are powered nulls for a ≥+24 elo effect.

## The 6 questions
1. **Is iter12 stronger than iter8 at sims 200?** **No.** +14.6 elo, z=0.65 — within noise.
   (Reproduces the spent-band 1.7e9 read +15.3/z0.68 on an independent band → robust.)
2. **Is iter12 stronger than iter8 at sims 800?** **No.** +12.4 elo, z=0.51 — within noise.
   *This is the cell the deepteacher never measured.* Cleanly a tie.
3. **Did deepteacher raise the low-budget (s200) policy ceiling over iter8?** **No** (tie).
4. **Did deepteacher raise the deep-play (s800) ceiling over iter8?** **No** (tie). The deeper
   teacher, iterated 12×, does not exceed its own warm-from iter8 at the deep plane.
5. **Does iter12 replace iter8 as production champion?** **No.** No significant gain at either
   plane; champion stays **iter8** (`PRODUCTION.yaml` unchanged).
6. **Which prior deepteacher claims must be revised?**
   - The sealed "Δ+8.1/z0.34 tie @s800" and washout "Δ+82.8/z3.48 @s200" are **iter12 vs
     residual.pt**, not vs iter8 (provenance audit) → relabel; they are not the experiment's
     question.
   - The mid-run confirm "iter2 +53.7/z2.14 over iter8 @s800" (band 1.3e9) and interim "iter9
     +35.6/z1.21 @s800" (band 1.6e9) did **not** carry to the final champion on a clean paired
     band (iter12 +12.4/z0.51). Consistent with deck-band-favorable noise + a noisy s800
     selection gate; **do not cite them as durable deep-plane gains.**
   - The STATUS framing "the washout proves policy iteration is a dead end for deep-search
     strength" reached the right end state (no deep-plane gain over iter8) but via the wrong
     baseline; it is now **directly supported** by this clean tie at s800.

## Conclusions permitted
- The deeper-teacher run produced a champion (iter12) **statistically tied with its warm-from
  iter8 at both s200 and s800** on a fresh paired band. The "stronger/deeper teacher breaks the
  plateau" hypothesis gets a **clean powered-null at the deep verdict plane** (the earlier
  defective analysis could not deliver this).
- Both point estimates are a small consistent positive (~+12–15 elo) but below the
  decision-relevant threshold; resolving a true +13 would need n≈1500 and is not worth the compute.
- Deep search lifts BOTH nets by ~+70 elo (s200→s800: iter8 +72→+142, iter12 +87→+155),
  i.e. the heuristic-scored deep search exploits both policies about equally — consistent with
  the washout mechanism (policy gains are recovered by search regardless of priors).

## Conclusions NOT permitted
- "Deeper teacher failed" as if it ran from a worse start — it ran from iter8 (confirmed); it
  simply tied iter8.
- "Deeper teacher worked" — it did not beat iter8 at any plane.
- Promoting iter12 on the +12–15 point estimate (z<0.7).
- Treating the iter2/iter9 band-favorable signals as the result.
