# PHASE 0.3 — Self-play invalid-visit clip: ROOT CAUSE + FIX

**Date:** 2026-07-06 · **Status:** ROOT-CAUSED, FIXED, REGRESSION-TESTED · net-free deterministic repro.

## Symptom (the silent clip)
`src/carcassonne_ai/selfplay.py` built the policy target from MCTS visit counts and **silently dropped** ("clipped") any visit that landed on an action absent from the snapshot legality mask, with the comment *"most likely a stale legal-moves-cache entry from a prior search; not yet root-caused."* This bug class (legality/cache/transposition accounting) had twice corrupted training data before.

## Root cause: a legal-moves-CACHE collision between rotation-instances
The legal-moves cache (`Game._legal_cache`, `enable_legal_moves_cache=True`) is keyed by `string_representation(board)`. That key is **invariant to symmetric tile rotations** (it renders the physical board, which is identical for a rotationally-symmetric tile placed in two 180°-equivalent rotations). But `get_valid_moves` is a function of the **board instance**, not of the key: the engine stores the just-placed tile's `.farms` in a **rotated order**, so `ActionUtil.possible_meeple_actions` picks a different representative farmer corner (`farmer_positions[0]`) → **the same physical farm encodes to a different meeple action index**.

So two board instances that are the *same physical position* (same cache key) can have **different legal masks** (rotation-aliased farmer indices). When a prior ply's search left such a position in the cache under key K, the next ply's snapshot `get_valid_moves` for a *different rotation-instance* of the same position (same key K) is served the **stale, wrong-rotation** mask. The self-play loop then took the snapshot mask as the training mask, ran a fresh search (whose root recomputed the *other* rotation's indices), and `root_visit_distribution` returned visits on indices the stale snapshot omitted → the clip.

### Deterministic net-free repro (verified, `scripts/invalid_visit_clip/repro.py`)
- **seed 0, ply 8**, `next_tile = straight_road`, two legal TILES actions **1044** and **1046** (same (row,col), rotations 180° apart).
- Applying each yields children with the **SAME** `string_representation` (`same_key=True`) but **different** fresh masks: `{2506, 2507, 2510}` vs `{2508, 2509, 2510}` (`A_fresh != B_fresh = True`). The differing indices `{2506,2507}` vs `{2508,2509}` are the rotation-aliased farmer placements on the same physical farms; `2510` (shared) is the no-meeple action.
- With caching enabled, writing A then reading B serves **A's stale mask for B** (`B_served == A = True`, `B_served == freshB = False`) — the literal corruption path.

This is NOT a lossy transposition key in the harmful sense: the two instances are genuinely the same physical position (merging them as one MCTS node is *correct*). The only defect is at the **snapshot↔search boundary**, where a stale cache entry made the snapshot mask disagree with the search root's mask.

## Fix (`src/carcassonne_ai/selfplay.py`)
Move `mcts.clear()` (which calls `game.clear_caches()` → empties `_legal_cache`) to run **BEFORE** the snapshot mask is taken. Then the snapshot and the search root both recompute from **this** board instance with an empty cache → identical masks → no clip is possible. The former silent drop is now a **hard assert with full-repro telemetry** (`clip_trace.capture_clip_repro`, dumped under `CARCASSONNE_CLIP_TRACE_DIR`): if a masked-off visit ever appears again, a real invariant broke (e.g. cross-ply cache reuse reintroduced) and the run fails loudly rather than silently corrupting the policy/mask targets. Ordering change only — no extra `get_valid_moves`/`clear` calls, so no perf regression (in fact one fewer recompute than before).

## Why the fix is complete (and the latent unsoundness is bounded)
Within a single search, MCTS keys nodes by the same `string_representation`, so rotation-instances map to ONE transposition node whose `untried_actions` come from the first instance seen — internally consistent (all visits use that node's indices). The only externally-visible inconsistency was the snapshot↔root mask disagreement, which the clear-before-snapshot ordering removes. The runtime hard assert now guards the integration path during real gen.

**Recommended follow-up (not required, flag for BACKLOG):** the legal cache is *latently unsound* for any caller that shares a `Game`'s cache across rotation-instances without clearing between them. A principled fix would make `get_valid_moves` a pure function of the cache key (canonicalize the farmer-index representative independent of `.farms` order) or include the instance-distinguishing state in the key. Out of scope for Phase 0.3 (measurement/correctness of the self-play path); the hard assert catches any recurrence.

## Regression coverage (`tests/test_invalid_visit_clip.py`, net-free)
1. seed-0-ply-8 collision is reproducible (pinned actions 1044/1046, `straight_road`).
2. the two rotation-instances share a key but have different fresh masks (the soundness fact).
3. stale-cache serving reproduced (B served A's mask, wrong for B).
4. clear-before-snapshot makes the snapshot equal the search-root/fresh mask (the fix invariant).
5. `clear_caches()` empties the legal cache (the fix's premise).

## Measured clip frequency
Collisions of this kind are common early (straight_road is frequent), but the clip only *fired* at the snapshot↔search boundary and only when a stale cross-ply entry of a rotation-instance was present — rare per game. Post-fix the frequency is **structurally zero** (guaranteed by clear-before-snapshot, enforced by the hard assert). The pre-fix clip silently distorted the policy target by moving mass from a rotation-aliased farmer index to nothing; magnitude was small per event but unbounded in principle across a long run — hence the promotion to a hard assert rather than leaving a silent drop.
