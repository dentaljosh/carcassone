# Phase 5 — Fair-Information vs Clairvoyant Labels

> **Constraint honored throughout the audit:** exact CLAIRVOYANT solver labels (perfect knowledge
> of the real future deck order) are kept verbally and structurally distinct from FAIR-INFORMATION
> / bag-expectation (marginalized) labels. This note states exactly which is which, which
> conclusions depend on clairvoyance, and the minimum future test before any "transfers to honest
> play" claim.

## What labels exist, and of which kind — FACT

| slice | n positions | clairvoyant | fair-information (marginalized) |
|---|---|---|---|
| K=2 | 150 | ✅ exact (alpha-beta) | ✅ exact (expectiminimax) |
| K=3 | 71 | ✅ exact | ❌ **0 solved** (intractable w/o make/unmake) |
| K=4 | 187 | ✅ exact (alpha-beta) | ❌ not attempted (needs make/unmake; PENDING in [K4 verdict](../level2/LEVEL2_K4_PROBE_VERDICT.md)) |

- **Clairvoyant** = minimax/alpha-beta over the *known real* future deck order. An UPPER BOUND on
  achievable play; an agent that doesn't see the deck cannot be expected to match it.
- **Marginalized (fair-information)** = expectiminimax over the *unknown remaining bag* (uniform
  over the remaining-tile multiset at each draw) — the honest game value. This is the **preferred**
  ground truth, but it admits no alpha-beta (chance nodes break minimax cutoffs), so it is far more
  expensive and is the part gated on the make/unmake solver.

## Tiny fair-information sanity slice (the "trivial" optional check) — FACT

At K=2 the bag holds exactly one (determined) tile, so the two label kinds must coincide. Verified
directly on the re-solved [k2_childvalues.jsonl](k2_childvalues.jsonl):

> **150 / 150 K=2 positions: marginalized == clairvoyant, BIT-IDENTICAL** — every game-theoretic
> value, every optimal-action set, and the FULL per-action value map match exactly.

So the only fair-information labels that exist are **degenerate** (they carry no information beyond
clairvoyant). The first K where the two genuinely diverge is **K=3**, which is unsolved in
marginalized mode.

## Which audit conclusions depend on clairvoyant labels — INTERPRETATION

- **K=2 conclusions** (the τ=0.55 v2.7-ranking result, the simple-selector collapse, the K=2
  disagreement split) are **fair-information-safe** — at K=2 the labels coincide.
- **K=3 and K=4 conclusions are CLAIRVOYANT-ONLY.** This includes the headline "iter8 plays the
  endgame worst" at K=3/K=4, the source disentangler (iter8 0.65 own / 0.44 greedy-gen), the
  sharpness split (iter8 sharp 0.39 / regret 3.34), and the K=4 portion of the disagreement audit.
  These are statements about **clairvoyant** optimal play; under honest (fair-information) play the
  *magnitudes* could shift (and an agent's clairvoyant "regret" partly reflects not seeing the deck).
- The separate **clairvoyance-gap** eval ([CL-022](../clairvoyance/CLAIRVOYANCE_GAP_VERDICT.md))
  bounds *deck-order* clairvoyance at **~+27 Elo (z≈−0.9)** in the **sims=200 / root-determinization
  full-game** setup — i.e. a large (≥100 Elo) inflation is NOT supported there. But that is a
  full-game-Elo bound, **not** a per-move endgame-regret transfer proof. Fair-information transfer of
  the endgame-regret ranking is **not fully proven** (carried from EVIDENCE_HYGIENE_NOTES.md item 4).

## Minimum future test before claiming transfer to honest play — INTERPRETATION

The smallest decisive test: **marginalized (fair-information) K=3 labels on a small balanced slice
(~30–50 positions), re-running the agent-regret comparison.** If "iter8 worst / heur@3200 strongest"
survives at K=3 under fair information (the first K where marg ≠ clair), the clairvoyant ranking
transfers; if it collapses, the clairvoyant endgame story is partly a not-seeing-the-deck artifact.

**Infrastructure needed (cost):** marginalized K≥3 is gated on a **make/unmake (no-deepcopy) solver**
— the engine's per-`get_next_state` deepcopy (~1.7 ms) is the binding constraint, and expectiminimax
has no alpha-beta to lean on. Estimated **~3–5 day engine project** (incremental apply/undo on the
trusted engine; helps the solver family only, NOT production MCTS — see
[BACKLOG.md](../../BACKLOG.md) / [STATUS.md](../../STATUS.md)). A K=3 marginalized solve at the
existing no-prune cost (K=3 clairvoyant median ~264 s/pos *with* alpha-beta) would be substantially
slower without pruning, so the make/unmake speedup is a prerequisite, not optional.

**Recommendation:** do NOT build a large marginalized solver for this audit. Treat all K=3/K=4
numbers as clairvoyant upper bounds; gate any "iter8 endgame deficit transfers to honest play" claim
on the small marginalized-K=3 slice above, after make/unmake exists.
