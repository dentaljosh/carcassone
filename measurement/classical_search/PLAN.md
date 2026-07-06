# PHASE 1.1 — PUCT-with-heuristic-priors on HeuristicMCTS — PRE-REGISTRATION

**Status:** PRE-REGISTERED (thresholds committed before any number exists). Written 2026-07-05.
**Program:** Post-review implementation, Phase 1 (classical search as a lever, MT-1) — the highest-EV item in the merged review.
**Discipline:** MEASUREMENT ONLY. No change to `governance/PRODUCTION.yaml`, the champion pointer, or the v2.7/v2.9 leaf. New behavior ships behind a flag defaulting OFF, bit-exact when off. Single read-out at the pre-registered n; no peeking, no threshold-moving.

## Hypothesis (H1.1)
Production `HeuristicMCTS` uses random-expansion UCT with `C=3.0` (inherited from a random-rollout paper), **no priors, no move ordering, one-random-child-per-sim expansion, and an int-quantized leaf**. This is well below the classical frontier at equal compute. Adding heuristic-leaf PUCT priors + expand-all-children + (optionally) a non-quantized leaf and a Q-based final selection should raise strength at matched wall-clock.

## Build (behind a flag on HeuristicMCTS or a sibling class; default OFF ⇒ bit-exact to today)
1. **PUCT selection with priors computed at node expansion.** At expansion, evaluate the leaf on each legal child (afterstate); prior `P(a) = softmax(Δleaf(a) / τ_p)` where `Δleaf(a) = leaf(child_a) − leaf(parent)` from the **mover's POV**. Selection = `Q(a) + c · P(a) · sqrt(ΣN) / (1 + N(a))` (standard PUCT). Batch the child leaf evals per expansion (flat/Cy leaf is cheap).
2. **Expand-all-children-at-once** replaces one-random-child-per-sim (this is the point of the priors).
3. **Config knobs exposed** (all swept or fixed, recorded in manifest):
   - `c_puct` (exploration),
   - `τ_p` (prior temperature),
   - `leaf_quantize ∈ {int, float}` — float = skip `int(round(...))`,
   - `final_select ∈ {visits, Q}` — the clairvoyance-gap doc showed the selector alone is worth ~100 elo, so it is a **swept parameter, not an assumption**.

## Equal-time normalization (MANDATORY — the comparison is at matched wall-clock, not matched sims)
Bench single-thread `ms/move` for the candidate vs the production champion `h6400` on an identical set of positions (same leaf env, same box, `nice -n 19`, net-free CPU). Set the candidate's `sims` so its wall-clock/move matches `h6400` within **±10%**. **Record BOTH sims counts and the measured ms/move in every manifest.** (Because expand-all + per-child leaf priors raise per-sim cost, the candidate will run fewer sims than 6400 — that is the fair comparison.)

## Opponent / mode
Opponent = the **production champion**: `HeuristicMCTS` on the v2.9 `Bmild_cap8` leaf @ `h6400` + exact-K≤4 endgame handoff. This is an **internal algorithm A/B**, so it runs **matched-mode = clairvoyant-vs-clairvoyant** (both descend the true deck) — permitted per the program's eval conventions for A/Bs. Deck-paired (same shuffled deck both seats, seats swapped).

## Sweep (pre-registered grid)
Screen every cell at **n=100** (deck-paired) vs the champion:
- `c ∈ {0.5, 1.0, 1.5, 2.5}` × `τ_p ∈ {2, 5}` = 8 cells.
- `final_select` and `leaf_quantize`: default `final_select=Q`, `leaf_quantize=float` for the primary grid; run the alternate settings (`visits`, `int`) as 2 extra reference cells at the best `(c, τ_p)` to size the selector/quantization effect separately.
Confirm the **single best cell** at **n=400** on a FRESH band.

## Bands (fresh, disjoint from all prior results.csv rows; max prior band ≈ 8.8e9)
- Screen (n=100 × cells): base seed band **9.00e9** (cells offset by disjoint sub-ranges, e.g. cell i uses `9.00e9 + i·1e6`).
- n=400 confirm: base seed band **9.40e9** (disjoint from every screen sub-range and from all prior bands).

## Pre-registered decision thresholds (n=400 confirm; σ_elo ≈ ±17.5 at n=400 paired)
- **FIRE:** best cell ≥ **+35 elo (2σ)** vs champion at n=400 → Phase 1.1 succeeds. Propose (do NOT execute) the champion flip + a ruler-ladder re-anchoring plan, and list which historical "parity with deep search" verdicts must be re-read against the new rung.
- **KILL:** if **every** screened cell ≤ **+17 elo (1σ)** → Phase 1.1 fails; heuristic-prior PUCT is not a lever at equal time.
- **AMBIGUOUS:** best cell in **(+17, +35)** at n=400 → proceed to Phase 1.2 (ID-alpha-beta), which is gated on this outcome. Surface the go/no-go + cost to Joshua before launching 1.2.

## Reporting
`measurement/classical_search/PUCT_PRIORS_RESULTS.md` (screen table + confirm), a `results.csv` row per game-eval (with manifest: full resolved config, leaf hash, code rev, seeds, both sims counts, ms/move), and the go/no-go paragraph. If any finding contradicts a `governance/CLAIM_REGISTRY.csv` claim, a proposed (not applied) registry amendment.

## Cost (to be surfaced before launch)
Equal-time bench (~15 min) + 8 screen cells × n=100 paired + 1 confirm × n=400 paired at h6400-equivalent wall-clock. h6400 is ~2.85 s/move single-thread (phone-budget bench). Estimate box-hours after the equal-time bench sets the candidate sims; **surface the total to Joshua before launching the screen** (this is a go between phases + likely >3 box-hours).
