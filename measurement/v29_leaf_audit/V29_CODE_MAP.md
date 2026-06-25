# V29_CODE_MAP — leaf evaluator: where v2.8 lives, where v2.9 plugs in

**Stage 0 deliverable** (v2.9 evaluator/search audit, 2026-06-25). Read-only map of
the production leaf + insertion points. No behavior changed by this document.

Branch: `strategic-behavior-ladder` (v2.9 work continues here for now).
Constraint reminder: **v2.7 frozen + bit-identical, v2.8 opt-in, no PRODUCTION.yaml
edits, no checkpoint promotion, no RoD2 training.** This is a classical
evaluator/search audit only.

---

## 1. The production leaf formula (exact)

`virtual_score_v2(state, player, cfg) -> int` ([src/carcassonne_ai/virtual_score_v2.py:491](../../src/carcassonne_ai/virtual_score_v2.py#L491)):

```
score = base                                    # v1 end-of-game score differential
      + cap(closure_anticipation(player),  12)  # bonus_self
      - cap(closure_anticipation(opp),     12)  # bonus_opp
      + meeple_k * (free_meeples_self - free_meeples_opp)   # v2.8: meeple_k=2.0 ; v2.7: 0
return int(round(score))
```

- **base** = `virtual_score(state, player)` ([virtual_score.py](../../src/carcassonne_ai/virtual_score.py)) — runs the engine's
  final scoring on the *current* board and returns `score[player] - score[opp]`.
  Cities 2/tile+2/shield (complete) or 1/tile+1/shield (incomplete); roads 1/tile;
  cloisters 1+surrounding; farms 3 per finished adjacent city to the majority farmer.
- **closure_anticipation** ([virtual_score_v2.py:332](../../src/carcassonne_ai/virtual_score_v2.py#L332)) =
  `Σ P(close) × score-delta` over the player's meeples on INCOMPLETE features
  (cities, cloisters, farm-growth cities), deduped by canonical content.
  `P(close)` schedule (production, `DROP_THREE_OPEN=1`): `{1-open: 0.5, 2-open: 0.2}`, else 0.
  Per-player capped at `bonus_cap = opp_bonus_cap = 12` (`CARCASSONNE_V25_CAP=12`).
- **meeple term** ([virtual_score_v2.py:574](../../src/carcassonne_ai/virtual_score_v2.py#L574)) — flat, added AFTER caps. `meeple_k=2.0` is the **entire** v2.8−v2.7 delta.

### Production config (v2.8)
`CARCASSONNE_V25_CAP=12, DROP_THREE_OPEN=1, USE_FLAT_LEAF=1, VALUE_BLEND=0,
RESIDUAL_SCALE=0.25 (neural only), meeple_k=2.0`. `DEFAULT_CONFIG` is built from
these env vars at import ([virtual_score_v2.py:118](../../src/carcassonne_ai/virtual_score_v2.py#L118)).

---

## 2. How the leaf scalar reaches MCTS (both consumers)

The leaf returns an **integer point differential**; the consumer squashes it.

| Consumer | call site | transform |
|---|---|---|
| **HeuristicMCTS** (h200…h6400) | [mcts.py:346](../../src/carcassonne_ai/mcts.py#L346) | `tanh(diff / 15.0)` (`HEURISTIC_VALUE_NORM=15`) |
| **NeuralMCTS** (RoD agents) via `make_v25_value_wrapper` | [evaluators.py:239](../../src/carcassonne_ai/evaluators.py#L239) | `clip(tanh(diff/15) + 0.25·v_nn, ±1)` (residual) |

**Key consequence for Candidate A (win-shaped utility):** the pipeline is *already*
`tanh(diff/15)` — a mild win-shaping at T=15. "Win-shaping" = changing that
effective temperature. Implemented per the spec as `T·tanh(diff/T)` inside the leaf
(point-scale preserved), composed with the consumer's `tanh(/15)`:
final HeuristicMCTS value = `tanh( T·tanh(diff/T) / 15 )`. T→∞ recovers baseline;
smaller T compresses large leads (anti-padding) at the cost of margin resolution.

**Opt-in hook already exists:** `HeuristicMCTS(..., heur_leaf="v2_7", leaf_cfg=<LeafConfig>)`
([mcts.py:314](../../src/carcassonne_ai/mcts.py#L314), added 2026-06-22 for v2.8). v2.9 reuses it — no new MCTS plumbing.

---

## 3. The flat-leaf fast path and the object-path fallback

`USE_FLAT_LEAF=1` (production) redirects to `flat_leaf.flat_virtual_score_v2`
(de-objectified union-find, ~2.26× faster, bit-exact) — **UNLESS** the cfg needs
the object path ([virtual_score_v2.py:523](../../src/carcassonne_ai/virtual_score_v2.py#L523)):

```python
if flat_leaf.USE_FLAT_LEAF and not (
    cfg.tile_counting_closure or cfg.closure_continuous_slack > 0.0 or _v28_active(cfg)
):
    return flat_leaf.flat_virtual_score_v2(state, player, cfg)
```

`flat_leaf` implements base + closure + **flat meeple_k** ([flat_leaf.py:696](../../src/carcassonne_ai/flat_leaf.py#L696)),
so production v2.8 (legacy `meeple_k`) stays on the fast path. The deck-aware knobs
and the `v28_*` experimental fields force the slow object path (flat doesn't
implement them). **v2.9 follows the same pattern: `_v29_active(cfg)` forces the
object path**, leaving `flat_leaf` untouched and bit-exact.

---

## 4. Existing deck-aware completion code (Candidate C) — and why it's OFF

Already built, already killed:
- **Hard gate** `tile_counting_closure` ([virtual_score_v2.py:362](../../src/carcassonne_ai/virtual_score_v2.py#L362)): P→0 when the deck
  literally cannot finish a feature (`_deck_city_supply`).
- **Continuous ramp** `closure_continuous_slack` ([virtual_score_v2.py:239](../../src/carcassonne_ai/virtual_score_v2.py#L239) `_supply_factor`): scales
  P(close) smoothly by deck supply.

**Verdict (DECISIONS 2026-05-17):** hard gate 45% wr, continuous ramp 50%/−1.4 avg,
pooled **95/200 = 47.5% = a tight null.** "Closure-probability accuracy is not the
lever. MCTS does not need a calibrated P(closure); the rough fixed schedule is
already sufficient." **Re-confirmed dead in the 2026-06-22 v2.8 program** (deck-aware
closure: exact-K2 top-1 0.763→0.826 but full-game +3.5 elo z=1.09, endgame-local
washout). ⇒ **Candidate C is pre-killed; the knob stays available but no compute is
to be spent re-running it.**

---

## 5. Other pre-killed directions (2026-06-22 v2.8 program — DECISIONS:2640)

The v2.8 program tested 4 patches from a 678-case failure taxonomy. **One survivor:**
- ❌ **farm-majority-gate** (`v28_farm_majority`) — broad degradation, cap-masked.
- ❌ **deck-aware-closure** — see §4.
- ❌ **opp-denial** — no movement.
- ✅ **meeple-economy** (`meeple_k`) — +179.5 elo z=9.9 @ heur200, holds @ heur800;
  v28@200 beats v27@800. → **shipped as production v2.8.**

⇒ Candidate E (farm access / denial) overlaps two killed patches; treat as
low-prior, defer behind A/B. Candidate B (nonlinear meeple) **refines the one term
that worked** → highest prior. Candidate D (sparse tactical punish) is the only
genuinely-new direction with positive evidence (the 2026-06-25 strategic-ladder
high-precision finding: h6400 takes MUST_PUNISH_WEAK 92% vs RoD1 84%), but as a
*leaf-state* term it largely duplicates the base (completing a feature already banks
points) — the real lever there is search/policy, not the leaf. Stub + revisit.

---

## 6. v2.9 insertion points (what the build touches)

1. **`LeafConfig`** ([virtual_score_v2.py:58](../../src/carcassonne_ai/virtual_score_v2.py#L58)) — add v2.9 fields, all default
   neutral (bit-exact v2.8 when off): `v29_util_tanh_t`, `v29_meeple_curve`,
   `v29_punish_k`, `v29_farm_access_k`.
2. **`_v29_active(cfg)`** — new helper mirroring `_v28_active`; forces object path.
3. **Flat-redirect guard** ([virtual_score_v2.py:523](../../src/carcassonne_ai/virtual_score_v2.py#L523)) — add `or _v29_active(cfg)`.
4. **`virtual_score_v2` tail** — guard the flat-meeple line with `and cfg.v29_meeple_curve is None`
   (no-op when off), then `if _v29_active(cfg): score = leaf_v29.apply_v29(...)`.
5. **NEW `src/carcassonne_ai/leaf_v29.py`** — all v2.9 term logic + `apply_v29` +
   `decompose_v29(state, player, cfg) -> dict` (every component separately, for
   "which term moved the decision").
6. **NEW `scripts/v29/eval_v29_vs_v28.py`** — fork of `eval_heur_vs_heur.py`,
   parametrizing `leaf_cfg` on BOTH sides (A=v2.9 candidate, B=v2.8 baseline),
   adding pre-move close/even/padding/phase splits.

Frozen guarantee: when no `v29_*` field is set, `_v29_active` is False, the flat
redirect fires unchanged, and `decompose`/`apply_v29` are never called ⇒ v2.7 and
v2.8 outputs are byte-identical (asserted by test).
