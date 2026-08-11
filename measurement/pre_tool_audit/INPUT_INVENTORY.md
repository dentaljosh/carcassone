# Phase 1 — Input Inventory: what iter8 already receives vs must infer

> **Purpose.** Before proposing any "tool" feature, document exactly what the production
> champion's network already gets as input. A tool is only worth building if it supplies
> information the net does **not** already have (explicitly or easily-inferably).
>
> **Champion.** `flywheel2_champion_iter8` — 96×6 ResNet, `n_scalar_features=12`,
> `value_global_pool=False`, obs `(78, 25, 25)`, v2.7 (`virtual_score_v2`) leaf,
> `RESIDUAL_SCALE=0.25`, `FLAT_LEAF=1` ([governance/PRODUCTION.yaml](../../governance/PRODUCTION.yaml)).
> All citations are `path:line` at commit `1924261`.
>
> **FACTS** = read off the encoding code. **INTERPRETATION** = my classification of tool-relevance.

---

## 1. Board tensor — 78 channels × 25 × 25 (FACT)

Layout from [src/carcassonne_ai/board_repr.py:94-107](../../src/carcassonne_ai/board_repr.py),
encoded in `encode_board` ([board_repr.py:315](../../src/carcassonne_ai/board_repr.py)),
player-relative (channels are remapped so "mine"/"opp" are from the side-to-move's view).

| channels | count | name | encodes |
|---|---|---|---|
| 0–15 | 16 | `CH_EDGES` | 4 sides × 4 edge categories (city / road / field / none), one-hot per side |
| 16 | 1 | `CH_TILE_PRESENT` | a tile occupies this cell |
| 17 | 1 | `CH_SHIELD` | tile has a city shield |
| 18 | 1 | `CH_CHAPEL` | tile is a chapel |
| 19–24 | 6 | `CH_INTERNAL_ROAD` | internal road connectivity (the 6 side-pairs) |
| 25–30 | 6 | `CH_INTERNAL_CITY` | internal city connectivity (the 6 side-pairs) |
| 31–35 | 5 | `CH_NORMAL_MEEPLE_MINE` | my normal meeple on {T,R,B,L,CENTER} |
| 36–40 | 5 | `CH_NORMAL_MEEPLE_OPP` | opponent normal meeple on {T,R,B,L,CENTER} |
| 41–44 | 4 | `CH_FARMER_MEEPLE_MINE` | my farmer on {TL,TR,BL,BR} |
| 45–48 | 4 | `CH_FARMER_MEEPLE_OPP` | opponent farmer on {TL,TR,BL,BR} |
| 49–64 | 16 | `CH_REF_TILE_EDGES` | the **in-hand tile** edges, broadcast to all cells |
| 65–76 | 12 | `CH_REF_TILE_INTERNAL` | in-hand tile internal topology (6 road + 6 city pairs), broadcast |
| 77 | 1 | `CH_LAST_TILE_POS` | one-hot of the last-placed tile position |
| **total** | **78** | | |

**Key structural facts:**
- The board is the **current (pre-action) placement**. The net is NOT shown any candidate
  afterstate — it must imagine each action's effect.
- The **in-hand tile** is fully described (its edges + internal topology, channels 49–76) but
  is broadcast as a constant plane, not placed. Rotation is handled by the policy action index,
  not by encoding 4 rotated tiles ([board_repr.py:392](../../src/carcassonne_ai/board_repr.py)).
- Meeple **ownership and slot** are explicit (channels 31–48); **feature membership** (which
  tiles form one city/road/farm) is implicit in the edge + connectivity channels and must be
  reasoned out by the conv's receptive field.

## 2. The 12 scalar features (FACT)

From `encode_scalars` ([src/carcassonne_ai/features.py:114-147](../../src/carcassonne_ai/features.py)),
current-player-relative, normalized. Champion has `include_farm=True` → 10 base + 2 farm = 12.

| idx | feature | norm | source line |
|---|---|---|---|
| 0 | meeples remaining (mine) | /7 | features.py:131 |
| 1 | meeples remaining (opp) | /7 | features.py:132 |
| 2 | score (mine) | /100 | features.py:133 |
| 3 | score (opp) | /100 | features.py:134 |
| 4 | score differential (mine − opp) | /50 | features.py:135 |
| 5 | **tiles remaining in deck** (a single global count) | /72 | features.py:128,136 |
| 6 | current-player flag | 0/1 | features.py:137 |
| 7 | phase == TILES | 0/1 | features.py:138 |
| 8 | phase == MEEPLES | 0/1 | features.py:139 |
| 9 | game progress (0→1 as tiles exhaust) | [0,1] | features.py:129,140 |
| 10 | farm contested-field count | /4 | features.py:144-145 |
| 11 | farm control balance | /4 | features.py:144-146 |

The farm scalars (10–11) are **raw structural counts** — # fields where both players have a
farmer, and (my-majority fields − opp-majority fields). They are **deliberately NOT
value-weighted by adjacent cities** to avoid re-encoding the v2.7 heuristic into the net input
([features.py:64-67](../../src/carcassonne_ai/features.py)).

## 3. Policy head — 2511 actions (FACT)

From [src/carcassonne_ai/action_space.py:14-24](../../src/carcassonne_ai/action_space.py):
- `0 .. 2499` — TileAction, index `(row*25 + col)*4 + rotation` (25×25 window × 4 rotations)
- `2500` — tile-phase Pass
- `2501 .. 2505` — MeepleAction NORMAL on {TOP,RIGHT,BOTTOM,LEFT,CENTER} of the just-placed tile
- `2506 .. 2509` — MeepleAction FARMER on {TL,TR,BL,BR}
- `2510` — meeple-phase Pass

Total `25*25*4 + 11 = 2511` (`network.py:11,62`). **The policy is a learned map from the single
current-state encoding to a logit per action** — it never sees a per-action afterstate or any
per-action computed quantity.

## 4. Value head + residual leaf (FACT)

- The MCTS **leaf value** is `tanh(virtual_score_v2/15) + RESIDUAL_SCALE × v_nn`, with
  `RESIDUAL_SCALE = 0.25` ([governance/PRODUCTION.yaml:30](../../governance/PRODUCTION.yaml);
  blend in `evaluators.make_v25_value_wrapper`, leaf norm 15 in
  [mcts.py:~346](../../src/carcassonne_ai/mcts.py)). So the **v2.7 heuristic supplies ~75–80% of
  the leaf value; the net's value head supplies a 25%-scaled residual correction.**
- `CARCASSONNE_V25_VALUE_BLEND=0` ([PRODUCTION.yaml:32](../../governance/PRODUCTION.yaml)) →
  the v2.7 score is **NOT blended into the net's own input**; the net is value-trained on a
  delta target relative to the heuristic.

**Critical separation (INTERPRETATION):** v2.7 is the *leaf evaluator inside MCTS*, computed by
scoring afterstates. It is **never an input feature to the policy/value heads**. So the per-action
consequence information that v2.7 computes (score, completion, farm projection) reaches the agent
**only through MCTS 1-ply lookahead at the leaf**, not through the net. A "tool" that feeds those
per-action quantities directly to the net (or to an action-ranker) would be a genuinely new
information path — its value depends on whether MCTS search already extracts that signal.

---

## 5. Tool-candidate classification (INTERPRETATION)

For each proposed tool quantity: does the **current net input** already contain it?
Legend: **EXPLICIT** (a literal channel/scalar) · **IMPLICIT** (derivable from channels by the
conv, not given) · **ABSENT** (not present and not locally derivable) · **DERIVED-leaky**
(a coarse/partial summary is given) · **MCTS-only** (not a net input, but search sees it at the leaf).

| # | tool quantity | net-input status | justification + cite |
|---|---|---|---|
| 1 | immediate score delta of an action | **ABSENT (per-action)** | net has current scores (scalars 2–4) but no per-action afterstate; the score *after* each candidate placement is not encoded. MCTS sees it via the leaf. |
| 2 | meeple placed/recovered/net delta | **IMPLICIT / ABSENT** | current meeple counts (scalars 0–1) + positions (ch 31–48) are explicit; whether a *specific action* places/recovers is rule-derivable but not given per action. |
| 3 | completion yes/no of an action | **IMPLICIT** | inferable from edge (ch 0–15) + connectivity (ch 19–30) + in-hand tile (ch 49–76), but requires multi-tile spatial reasoning the conv must learn; not given. |
| 4 | open-edge delta | **IMPLICIT** | open edges are locally derivable (tile-present + edge-type + empty neighbor); the *delta from an action* is not encoded. |
| 5 | affected feature ownership | **IMPLICIT / UNCLEAR** | meeple ownership is explicit (ch 31–48); mapping a placement to the owner(s) of the (possibly large) feature it joins needs connectivity reasoning that may exceed the receptive field. |
| 6 | remaining tile counts / **bag-aware completion** | **DERIVED-leaky → mostly ABSENT** | scalar 5 gives **one global** "tiles remaining" count; the **bag composition** (which tile types remain) is NOT encoded, so "P(a closing tile is still available)" is ABSENT. |
| 7 | farm / final-scoring estimates | **DERIVED-leaky → ABSENT (full)** | 2 *structural* farm scalars (10–11) are explicit but deliberately un-valued; the full final-score projection (city/road/farm points) is the v2.7 leaf's job, **not a net input**. |
| 8 | opponent denial / blocking | **ABSENT (explicit)** | no channel; net must learn it from board + opp meeple positions. |
| 9 | **v2.7 action score (per-action)** | **MCTS-only (ABSENT from net input)** | v2.7 is the leaf value, blended 0.25 with net value; it is NOT fed to the policy/value heads ([features.py:64-67](../../src/carcassonne_ai/features.py), `VALUE_BLEND=0`). The per-action v2.7 score is the single most informative existing quantity *not* given to the net directly. |
| 10 | exact solver regret labels | **ABSENT** | computed only in the offline measurement suites; never in production. |

### Headline for the tool question (INTERPRETATION)
The policy head is a **pure-learned function of the current board** with **no explicit per-action
consequence features**. Every "consequence-of-this-action" quantity (#1–#5, #7–#9) is at best
something the conv must *infer*, and the one quantity that demonstrably ranks endgame actions well —
the **v2.7 per-action score** — reaches the agent only via MCTS leaf lookahead, never as a direct
ranking signal. The two cleanly-ABSENT quantities are **bag composition / bag-aware completion (#6)**
and **explicit per-action v2.7 score / score-delta (#1, #9)**. These are the natural first tool
candidates *if* the audit (Phases 3–4) shows iter8's misses correlate with them. Conversely, farm
structure (#7) and meeple counts (#2) are already partly given, so tools there are lower-value.
