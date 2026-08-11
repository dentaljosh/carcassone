# High-precision strategic-trap MOTIF definitions (frozen)

Narrow, precision-first successors to the broad ladder's motifs. Detector:
[`scripts/strategic_ladder/strict_motifs.py`](../../scripts/strategic_ladder/strict_motifs.py).
**Diagnostic only — no training on these labels, no promotion, v2.7 frozen, v2.8 opt-in.**

Design change from the broad ladder: the broad `block`/`avoid_feeding` used strict arg-min of
opponent city-equity, which mostly meant "play *somewhere else*" — not a human block. These
strict versions require the qualifying action to **physically interfere** with a concrete,
high-value opponent plan, and fire only on human-recognizable tactical situations. All detection
is structural (flat decomposition); **no outcome/score/agent/exact leakage** into the labels.

Shared: `mover = current_player`, `opp = 1-mover`, `margin_before = scores[mover]-scores[opp]`.
A city's **open completion cells** = the empty board cells outward-adjacent to its open city-edges
(reconstructed from `city_root_positions` + cardinal steps). Farm projected value = `3 × (#adjacent
city components)`; a farm's **live** adjacent cities = those finished or open_n ≤ 2 ("finishable").

## 1. `MUST_BLOCK_CITY` — TILES
- **opportunity:** opp holds ≥ tie on an OPEN city worth **≥ 8** points that is **1 tile from completion**
  (open_n == 1), the mover is not its sole owner, AND ∃ a legal tile placement **into that city's open
  completion cell** that leaves it **unfinished and strictly harder to close** (post open_n > pre open_n)
  — a genuine spoil, not a completion-gift and not "play elsewhere".
- **action qualifies:** the spoiling placement(s).
- magnitude = the threatened city value; `threat` names the cell and the open_n change.
- **excluded:** placements that complete the city for the opp; 1→1 swaps (no added difficulty); roads.

## 2. `MUST_NOT_FEED` — TILES  *(built, but FAILS to discriminate — see report)*
- **opportunity:** a legal placement hands the opp an immediate **≥ 8**-pt completable city (opp-owned,
  post open_n ≤ 1), AND ≥ 1 other legal placement avoids it.
- **action qualifies:** the safe (non-feeding) placements; the feeding placements are recorded separately.
- magnitude = the fed city value.
- **Honest caveat:** on the hard cases (few safe moves) even h6400 feeds ≈ as often as random — the lone
  "safe" move is usually forced/costly, so feeding is often correct. The detector cannot isolate a
  *tempting* trap; reported as inconclusive, not as "agents lack the concept."

## 3. `MUST_PUNISH_WEAK` — TILES or MEEPLES (competitive states only, margin_before ≤ +20)
- **opportunity:** the mover can immediately bank **≥ 8** points the opponent left exposed —
  either **complete its own ≥ 8-pt city this turn**, or **sole-claim a ≥ 8-pt live farm** (≥ 1 finishable
  adjacent city) the opp failed to contest.
- **action qualifies:** the completing/claiming action(s).
- magnitude = the banked value. Reported primarily in strong-vs-weak games.
- **excluded:** already-won states (margin_before > +20) — banking points in a won game is not "punishing".

## 4. `HIGH_VALUE_FARM_CLAIM_REFINED` — MEEPLES (competitive states only)
- **opportunity:** a legal FARMER placement makes the mover **sole** owner of a farm with **projected
  value ≥ 9** (≥ 3 cities) AND **≥ 2 LIVE (finishable) adjacent cities**, that the mover didn't already own,
  with `margin_before ≤ +20`.
- **action qualifies:** those farmer placements.
- magnitude = projected value; `detail` stores `live_adj`, `margin_before`.
- **excluded:** projected < 9; live < 2 (live=1 fields are *declined by every strong agent* — a bad-claim
  class, dropped on inspection); already-won states.

## Provenance recorded per position
position idx, regime, deck seed, seat (mover), move number (ply), phase/K, scores + margin_before,
free meeples, legal action count, qualifying actions, magnitude, threat description, every panel agent's
chosen action + took/missed, mover's actual choice, eventual mover-perspective final margin + result.
