# Clairvoyance-gap experiment — VERDICT (2026-06-18)

> Measurement gate (no promote/retrain/redesign). Protocol + pre-registration:
> [CLAIRVOYANCE_GAP_PROTOCOL.md](CLAIRVOYANCE_GAP_PROTOCOL.md). Step 0 confirmed the
> production search is deck-order clairvoyant (value moved 8/8 positions). This run
> measures how much that future-sight is worth in elo vs a fixed heuristic ruler.

## Bottom line
_(filled from `GAP_RESULTS.json` after both arms complete)_

**Clairvoyance gap = clair_elo − nonclair_elo = ⟨TBD⟩ elo** → gate ⟨≥100 / 30–100 / ≤30⟩.

## Arms (vs HeuristicMCTS @ heur_sims=800, v2.7 leaf; n=200 paired, band 2.7e9)
| arm | search | W/D/L | winrate | elo vs heur (±1σ) | avg pts diff |
|---|---|---|---|---|---|
| CLAIR (K=1) | clairvoyant (true deck order) | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ |
| NONCLAIR (K=12) | root-determinization vote | ⟨⟩ | ⟨⟩ | ⟨⟩ | ⟨⟩ |

## Paired contrast (same deck + seat + heur seed; differs only in clairvoyance)
- mean d (nonclair − clair score over 200 cells) = ⟨⟩, se = ⟨⟩, **z = ⟨⟩**
- mean raw-margin diff (pts vs heur) = ⟨⟩
- **V1 monotonicity** (nonclair ≤ clair): ⟨⟩

## Cross-checks
- Visit-argmax clair-iter8 vs heur@800 ≈ published best_action **+72.2** (band 2.5e9)?
  ⟨compare — large divergence ⇒ separate the aggregation-rule effect⟩.
- Step 0 determinism anchor held; V2/V3/K-distinct wrapper tests pass.

## Interpretation (pre-registered gates — guardrail #4)
_(one of:)_
- **≥100 elo** — strength is heavily clairvoyance-inflated; re-ground the narrative on
  non-clairvoyant play; Level-2 ladder centers the non-clairvoyant agent.
- **≤30 elo** — hidden draw-order info is minor; clairvoyant numbers ~transfer;
  proceed to the saturated-ruler ladder (skip expensive non-clairvoyant search).
- **30–100 elo** — ambiguous; top up n before committing to Level 2/3.

## What this does and does NOT establish
- IS: the deployable-vs-reported strength discount for iter8 at sims=200, K=12,
  on an out-of-lineage heuristic ruler, with the action-aggregation rule held fixed.
- IS NOT: a human-anchored or saturated-ruler number (still the Level-2/3 work); a
  statement about other sims depths; a license to change production (gate only).

## Provenance
Raw per-game JSON + manifest under
`/mnt/c/carc-shared/clairvoyance_gap/iter8_{clair_K1,nonclair_K12}_s200_h800_c30/`;
deck hashes per game; seed band 2.7e9 (fresh, > 1e9 floor). Code @ ⟨commit⟩.
