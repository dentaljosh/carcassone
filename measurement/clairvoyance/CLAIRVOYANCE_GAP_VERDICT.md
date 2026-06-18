# Clairvoyance-gap experiment — VERDICT (2026-06-18)

> Measurement gate — no promote/retrain/redesign. Protocol + pre-registration:
> [CLAIRVOYANCE_GAP_PROTOCOL.md](CLAIRVOYANCE_GAP_PROTOCOL.md). Step 0 confirmed the
> production search is deck-order clairvoyant (root value moved 8/8 positions). This
> run measures how much that future-sight is worth in elo vs a fixed heuristic ruler.

## Bottom line
**Clairvoyance gap = clair_elo − nonclair_elo = +26.6 elo** (point estimate) → the
pre-registered **≤30 "minor contributor"** gate, but near its boundary (call it
**small-to-moderate, ~25–30 elo**, not negligible). The paired difference is **not
statistically distinguishable from zero** (z = −0.9). The decisive belief-change
scenario — a **≥100 elo "heavily inflated" gap — is excluded** (P(gap≥100) ≈ 2%, ~2σ).

**Read:** iter8's strength is **not** clairvoyance-inflated in any decision-changing
way. Knowing the true future deck order is worth only ~25 elo; the fair
(non-clairvoyant) agent keeps essentially all of iter8's strength (+40 vs heur@800).
Our published clairvoyant numbers **~transfer to honest, deployable play.** ⇒ proceed
to the saturated-ruler ladder (§5 of the measurement spec); a non-clairvoyant agent
is **not mandatory** for Level 2.

## Arms (vs HeuristicMCTS @ heur_sims=800, v2.7 leaf; paired, fresh band 2.7e9)
| arm | search | n | W/D/L | winrate | elo vs heur (±1σ) | avg pts diff |
|---|---|---|---|---|---|---|
| CLAIR (K=1) | clairvoyant (true deck order) | 200 | 119/0/81 | 0.595 | **+66.8** (±25.0) | +5.41 |
| NONCLAIR (K=12) | root-determinization, best_action pooled | 182 | 100/3/79 | 0.558 | **+40.3** (±25.9) | +2.79 |

_(stopped at nonclair n=182/200 — Joshua's call; the gap was stable across n=41→182.)_

## Paired contrast (same deck + seat + heur seed; differs only in clairvoyance)
- 182 paired cells; mean d (nonclair − clair score) = **−0.0467**, se = 0.0506, **z = −0.9**.
- mean raw-margin diff (pts vs heur) = −3.12.
- **V1 monotonicity** (nonclair ≤ clair, perfect info can't hurt): **holds** ✓.
- Gap stability across reads: **+16.2** (n=41) → **+21.4** (n=100) → **+26.6** (n=182).
  Crept up with n, so "small-to-moderate," not "negligible"; bounded well under 100.

## Cross-checks / validation
- **CLAIR arm reproduces the published clairvoyant number:** +66.8 (this run, n=200,
  band 2.7e9) vs **+72.2** published (`p2_iter8_vs_heur800_v27_s200_n400`, band 2.5e9)
  — within CI. The corrected `best_action` harness is sound.
- **Aggregation bug caught + fixed mid-run** (the interim read earned its keep): the
  first harness used visit-argmax, which scored clair at −34.9 (≈105 elo below
  `best_action` at sims=200/c=3.0). A same-config reproduction (`eval_net_vs_heuristic`,
  best_action, n=40, band 2.7e9) = +70.4 isolated the cause to the selector, not
  orchestrator/net-source. Fixed to production `best_action` (clair) + best_action
  pooled over the K determinizations (nonclair). See PROTOCOL §Isolation.
- Step 0 determinism anchor held; wrapper unit tests (V2 degenerate, V3
  permutation+non-mutation, K-distinct) pass.

## What this does and does NOT establish
- **IS:** the deployable-vs-reported strength discount for iter8 at sims=200, K=12, on
  the out-of-lineage v2.7 heuristic ruler, with the production action-selection rule
  in both arms (so the paired Δ is pure clairvoyance). The discount is small (~25 elo).
- **IS NOT:** a human-anchored or supra-heuristic number (still Level-2/3 work); a
  statement at other sims depths (policy/value effects move with sims —
  `feedback_sims_washout_net_eval`); a license to change production (gate only).

## Next
Per the measurement spec §8 gates: the clairvoyance fork is settled (minor), so go
**straight to the Level-2 saturated-ruler ladder** — skip the expensive
non-clairvoyant search; the clairvoyant agent is an acceptable baseline.

## Provenance
Raw per-game JSON + manifests under
`/mnt/c/carc-shared/clairvoyance_gap_v2/iter8_{clair_K1,nonclair_K12}_s200_h800_c30/`
(the earlier `clairvoyance_gap/` dir is the discarded visit-argmax diagnostic record);
deck hashes per game; fresh seed band 2.7e9 (> 1e9 clean-eval floor). Summary:
`GAP_RESULTS.json`. Harness @ commit `f7ebec3` (best_action fix) + `ad9ad03` (orch).
