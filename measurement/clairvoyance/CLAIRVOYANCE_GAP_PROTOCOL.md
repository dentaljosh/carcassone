# Clairvoyance-gap experiment — PROTOCOL (pre-registered 2026-06-18)

> **Measurement gate only.** No promote / retrain / redesign follows from this run
> (Joshua's guardrail #5). It quantifies how much of iter8's reported strength
> comes from the search SEEING the true future deck order. Executes the first
> belief-changing experiment in `docs/MEASUREMENT_FIRST_SPEC_2026-06-18.md` §7.

## Estimand
Paired **Δelo(non-clairvoyant − clairvoyant)** for a FIXED agent (iter8, sims=200),
both arms anchored against the SAME fixed reference **HeuristicMCTS @ heur_sims=800,
v2.7 leaf**. The clairvoyance **gap** = `elo(clair vs heur) − elo(nonclair vs heur)`.

## Step 0 (gate 1) — RESULT: search IS deck-order clairvoyant ✅
`scripts/clairvoyance_step0_sentinel.py`, iter8 production config (residual 0.25,
sims 200, c 3.0). Held the mcts seed FIXED and varied ONLY the unseen deck order
(same public state + same remaining multiset, `next_tile` preserved):

- determinism anchor held — identical deck order ⇒ byte-identical root output (8/8);
- root **value** changed with deck order in **8/8** positions (spread 0.06–0.21 on [-1,1]);
- root **action** flipped in **2/8** positions.

⇒ the production search plans along the true future order. Sub-problem (A) is real;
the non-clairvoyant arm is meaningful. Raw: `measurement/clairvoyance/step0_sentinel.json`.

## Agents
- **CLAIR (K=1):** production iter8 — `NeuralMCTS(fair_chance=False)`, net priors +
  v2.7 leaf value with `residual_scale=0.25`, sims=200, c_puct=3.0. Descends the
  TRUE deck order (clairvoyant).
- **NONCLAIR (K=12):** same net/leaf/sims, `NeuralMCTS(fair_chance=True)`. At each
  move it runs K=12 independent searches, each on a fresh **root determinization**
  (deep-copy the root, shuffle ONLY the unseen `state.deck`, keep `next_tile`); it
  **pools the child stats across the 12 trees** — summed visits N_a and summed
  signed value W_a (root-player POV) — and picks by (pooled Q = W_a/N_a, N_a), i.e.
  the production `best_action` rule generalized to the determinization ensemble
  (standard PIMC statistic-pooling).
- **Opponent (both arms):** `HeuristicMCTS(heur_leaf=v2_7)` @ heur_sims=800.

### Isolation & honesty notes
- **Aggregation = production `best_action` for BOTH arms** (Q + visit tiebreak), so
  the clair arm reproduces the published clairvoyant number and the paired Δ isolates
  clairvoyance (true vs sampled futures), NOT an aggregation-rule difference.
- **⚠ Aggregation-bug caught at the interim read (2026-06-18):** the first harness
  used **visit-argmax** (raw τ→0 visit-max) for both arms. At sims=200 + c_puct=3.0
  that selector is ~105 elo WEAKER than `best_action`: visit-argmax clair-iter8 vs
  heur@800 scored **−34.9** (n=100, band 2.7e9) while the published best_action
  number is **+72.2** (i8_s200, n=400, band 2.5e9). Confirmed by a same-config
  reproduction: `eval_net_vs_heuristic` (best_action, per-worker net, band 2.7e9,
  n=40) = **+70.4** — matches the published +72, and isolates the cause to the
  selector (NOT orchestrator/net-source). Harness switched to `best_action` (commit
  below); the visit-argmax run is discarded (kept as the diagnostic record under
  `clairvoyance_gap/`, the corrected run writes to `clairvoyance_gap_v2/`).
- **Compute asymmetry is intended, not a confound:** the non-clairvoyant agent
  spends K× the search because not knowing the future is the COST of fair play; the
  question is the best a cheap fair agent does vs the clairvoyant production agent.
- **Non-peek contract (guardrail #2):** the agent only ever shuffles a deep-copy's
  unseen deck; the master `Game` advances the real board on the TRUE held-out order.
  The wrapper never reads the future order. Unit-pinned in
  `tests/test_clairvoyance_wrapper.py` (V3 + non-mutation).

## Design
- Fresh paired band: `--seed-start 2_700_000_000` (above the 1e9 clean-eval floor;
  not used by any prior eval — verified vs results.csv). n=200, `--paired` ⇒ 100
  decks × 2 colors. BOTH arms play the SAME 100 decks/seats ⇒ each paired cell
  differs only in clairvoyance (same deck, same seat, same heur seed=seed+1).
- sims=200, heur_sims=800, c_puct=3.0, K=12. Leaf env: CAP=12, DROP_THREE_OPEN=1,
  VALUE_BLEND=0, USE_FLAT_LEAF=1 (production). Deck hash per game; manifest per arm.

## Validation tests (status)
- **V2** degenerate last-tile no-op + search-level equivalence — PASS.
- **V3** determinization is a permutation of the multiset, keeps `next_tile`, never
  mutates the caller's board — PASS.
- **K-distinctness** — 12 determinizations are distinct worlds (rng advances) — PASS.
- **V1** monotonicity (nonclair winrate ≤ clair winrate) — checked POST-run in the
  analysis; a violation ⇒ determinizer bug (perfect info can't hurt, modulo noise).

## Decision gates (guardrail #4 — pre-registered)
Read on `gap = clair_elo − nonclair_elo`:
- **≥ 100 elo** → strength narrative is HEAVILY clairvoyance-inflated; re-ground on
  non-clairvoyant play; Level-2 ladder must center the non-clairvoyant agent.
- **≤ 30 elo** → hidden draw-order info is a MINOR contributor; clairvoyant numbers
  ~transfer; proceed to the saturated-ruler/ladder work, skip expensive non-clairv search.
- **30–100 elo** → ambiguous; top up n before committing to Level 2/3.

Significance: the paired per-cell score difference `d = nonclair − clair` with
`z = mean_d / se_d`. n=200 paired ⇒ ~±24 elo at 2σ (the spec's stated threshold).

## Deliverables
`CLAIRVOYANCE_GAP_PROTOCOL.md` (this) · `GAP_RESULTS.json` (per-arm + paired) ·
`CLAIRVOYANCE_GAP_VERDICT.md` · raw per-game JSON + manifests under the arm dirs ·
a `results.csv` row per arm · a CLAIM_REGISTRY entry for the gap.
