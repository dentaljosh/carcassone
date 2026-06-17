# Pre-registration — clean iter8 vs iter12 comparison (2026-06-17)

**Status: PRE-REGISTERED — recorded BEFORE execution. Do not edit results into this file.**
Results → `ITER8_VS_ITER12_RESULTS.csv`; verdict → `ITER8_VS_ITER12_VERDICT.md`.

## Why this run exists
The deepteacher sealed/washout baseline was `residual.pt`, not the warm-from iter8 (see
[DEEPTEACHER_PROVENANCE_AUDIT.md](DEEPTEACHER_PROVENANCE_AUDIT.md)). So **iter12 vs iter8 has
never been measured at the deep (s800) plane**, and at s200 only on a spent band (+15.3/z0.68).
This run measures it cleanly.

## Candidates (hash-pinned)
| id | path | sha256 |
|---|---|---|
| iter8 (incumbent champion) | `/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt` | `0d355002…ee2c` |
| iter12 (deepteacher champion) | `/mnt/c/carc-shared/deepteacher/ckpt/iter12.pt` | `059e394c…d0c` |

Runtime provenance assertion: every eval manifest must record the candidate's
`checkpoint_sha256` matching the above, and `residual_scale=0.25` with the residual path fired.

## Fixed config (identical both sides, both planes)
- Opponent: **HeuristicMCTS, heur_sims=800, leaf v2_7** (matched leaf).
- `c_puct=3.0`, `residual_scale=0.25`, `CAP=12`, `DROP_THREE_OPEN=1`, `FLAT_LEAF=1`, `VALUE_BLEND=0`.
- Deck-**paired**, seat-balanced (each deck played both colors).
- **Fresh seed band `--seed-start 2500000000`** — never used for selection, gate, confirm,
  sealed, washout, interim, or symaug (used bands: 1.0/1.2/1.3/1.6/1.7/1.9/2.0 e9). No reuse.
- n=400 per cell (200 decks × 2 seats).
- Eval code revision recorded per manifest (`code_commit`).

## Design — 2×2 vs ruler + direct head-to-head
**A. vs-ruler (primary, comparable to all prior deepteacher numbers):** 4 cells, each net vs
HeuristicMCTS@800:

| | agent sims 200 | agent sims 800 |
|---|---|---|
| iter8 | cell A1 | cell A3 |
| iter12 | cell A2 | cell A4 |

Paired Δ(iter12−iter8) computed on **common decks** at each plane: s200 = tally(A2,A1),
s800 = tally(A4,A3) via `scripts/odo_paired_tally.py` (pairs by deck seed; NOT independent-elo
subtraction).

**B. direct head-to-head (confirmatory):** iter12 vs iter8 net-vs-net, paired, n=400, at s200 and
s800 (`scripts/eval_iter_head_to_head.py`). Removes the heuristic as intermediary. Run if cost
permits; A is the verdict, B corroborates.

## Hypotheses
- **H1 (primary, deep plane):** iter12 > iter8 at **s800** by ≥ +24 elo paired (the deepteacher
  premise: play at the deep plane). 
- **H2 (secondary, prod plane):** iter12 > iter8 at **s200**.
- **H0 (null):** |Δ| < 24 elo at a plane (tie).

## Decision thresholds (from CLAUDE.md n-rules: n=400 paired ≈ ±12 elo 1σ)
- **STRONGER at a plane:** Δ(iter12−iter8) ≥ **+24 elo (2σ) AND z ≥ 2.0**.
- **TIE (powered null):** |Δ| < 24 AND |z| < 2.0 (a |Δ|<15 result actively rules out ≥+24).
- **INCONCLUSIVE → top up to n=800 paired:** Δ ∈ [+15,+30] with z ∈ [1.3, 2.3].
- **NEW PRODUCTION CHAMPION (replaces iter8):** requires iter12 ≥ iter8 at the **production
  plane (s200, per PRODUCTION.yaml)** by ≥+24/z≥2 **AND** no regression (Δ ≥ −10) at s800. A
  deep-plane-only win does **not** flip the s200 production champion; it would instead motivate
  a separate decision to move the production plane to s800.
- **DEEP-PLANE WIN (separate verdict):** iter12 ≥ iter8 at s800 by ≥+24/z≥2 → "deeper teacher
  raised the deep-play ceiling over iter8" = supported.

## Conclusions NOT permitted
- Promoting iter12 on a positive point estimate without z ≥ 2.0.
- Calling the deeper-teacher hypothesis "worked" or "failed" from the residual-baselined
  sealed/washout numbers (wrong baseline).
- Generalizing a single-band result to "strength" — the fresh 2.5e9 band is the verdict; existing
  1.3/1.6e9 signals are cross-checks, not pooled in.
- Indirect elo subtraction across separate runs where a paired common-deck Δ is available.
- Reviving the tanh-cap explanation.

## The 6 questions the verdict must answer
1. Is iter12 stronger than iter8 at sims 200?
2. Is iter12 stronger than iter8 at sims 800?
3. Did deepteacher raise the low-budget (s200) policy ceiling over iter8?
4. Did deepteacher raise the deep-play (s800) ceiling over iter8?
5. Does iter12 replace iter8 as production champion?
6. Which prior deepteacher claims must be revised?

## Prior (for calibration, NOT pooled into the verdict)
Existing independent-band signals vs champion-iter8 @s800: iter2 +53.7/z2.14 (1.3e9),
iter9 +35.6/z1.21 (1.6e9, n=134). iter12 vs iter8 @s200 (spent 1.7e9): +15.3/z0.68.
Expectation: a positive deep-plane Δ for iter12 is plausible; s200 likely weak/null.
