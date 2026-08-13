"""Virtual-score v2 — adds closure-proximity bonus + farm-growth potential
on top of the base `virtual_score`.

Diagnosed failure modes of v1 (DECISIONS.md 2026-05-14):
  1. **Closure-event blindness.** v1 gives partial credit for incomplete cities
     (1pt/tile, 1pt/shield) but the same tiles score double when the city
     closes (2pt/tile, 2pt/shield). v1 doesn't anticipate the partial→full
     credit swing → confidently mis-prices positions when a closure is
     imminent. Same for cloisters (1+N → 9 at close).
  2. **Farm composition opacity.** v1's farm scoring counts only cities with
     `city.finished == True`. Incomplete cities adjacent to a farmed area
     contribute 0 to v1, but those cities tend to complete by game-end,
     producing +3pts each. v1 systematically *underestimates* mature farms.

v2 adds an anticipation bonus for each placed meeple, weighted by P(closure)
based on how many adjacent board positions need to be filled. Mirror for the
opponent: their anticipated closures subtract from our v2 value.

Closure-probability heuristic (open_positions → P):
  1 → 1.0   (next tile placed nearby almost certainly closes)
  2 → 0.5
  3 → 0.25
  4+ → 0.0  (too far out; tile supply runs out before closure)

These thresholds are initial guesses. If v2 improves winrate, tune via a
small grid search; if v2 doesn't improve, the failure mode is elsewhere
(probably denial/meeple economy) and we redesign instead of tuning.

API mirrors `virtual_score`:
    diff = virtual_score_v2(state, player=0)
"""
from __future__ import annotations

import copy
import math
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.objects.terrain_type import TerrainType
from wingedsheep.carcassonne.utils.city_util import CityUtil
from wingedsheep.carcassonne.utils.farm_util import FarmUtil
from wingedsheep.carcassonne.utils.points_collector import PointsCollector

from . import compact_leaf
from . import flat_leaf
from . import virtual_score as _vs
from .virtual_score import virtual_score

if TYPE_CHECKING:
    from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
    from wingedsheep.carcassonne.objects.city import City


@dataclass
class LeafConfig:
    """Tunable knobs for the virtual_score_v2 leaf evaluator.

    Passing an explicit LeafConfig to `virtual_score_v2` lets two leaf
    variants coexist in one process — required for a clean same-checkpoint
    leaf-vs-leaf A/B head-to-head (the env-var globals below cannot do this,
    since they are read once at import). When no config is passed,
    `DEFAULT_CONFIG` (built from the CARCASSONNE_V25_* env vars) is used.

    Fields:
      closure_p: {open_positions: P(closure)} schedule for `_close_prob`.
      bonus_cap / opp_bonus_cap: per-player clamp on the anticipation bonus.
      meeple_k: weight on the (meeples_self - meeples_opp) economy term.
      tile_counting_closure: if True, `_close_prob` consults the remaining
        deck — P=0 for features the deck can no longer complete (Step 2 of
        the 2026-05-17 Option-1 plan). Default False = v2.7 behavior.
      closure_continuous_slack: if > 0, the hard tile-counting gate is
        replaced by a continuous deck-aware ramp — P(closure) is scaled by
        `_supply_factor(supply, need, slack)` instead of cliffed to 0 (Step 5
        of the Option-1 plan). Overrides `tile_counting_closure` when set.
        Default 0.0 = off.
      value_blend: if > 0, the leaf wrapper blends the network value head
        into the leaf value — `leaf = (1-λ)·tanh(vs2/15) + λ·v_nn` (Option 2,
        2026-05-17). 0.0 = pure heuristic leaf (v2.7 production). Read by
        `evaluators.make_v25_value_wrapper`, not by `virtual_score_v2` itself.
      residual_scale: if > 0, the leaf wrapper treats the network value head as a
        RESIDUAL on top of v2.7 — `leaf = clip(tanh(vs2/15) + scale·v_nn, ±1)`
        (Lever 1, 2026-06-05). The head is trained (value_target="residual") to
        predict Δ = search-Q − tanh(vs2/15); the leaf inherits v2.7's local
        sibling-ranking BY CONSTRUCTION and corrects it where Δ has signal. Takes
        precedence over value_blend when both > 0. Read by the leaf wrapper, not
        by `virtual_score_v2` itself.
    """
    closure_p: dict[int, float]
    bonus_cap: float
    opp_bonus_cap: float
    meeple_k: float = 0.0
    tile_counting_closure: bool = False
    closure_continuous_slack: float = 0.0
    value_blend: float = 0.0
    residual_scale: float = 0.0
    # --- v2.8 experimental leaf patches (Phase 3, measurement/heuristic_v28/) ---
    # All default OFF == bit-identical v2.7. All force the engine (object) path —
    # flat_leaf.py does NOT implement them (same opt-in pattern as the deck-aware
    # closure knobs above). NEVER set in production env knobs; constructed only
    # inside v28 eval/audit scripts.
    #   v28_farm_majority: gate the farm-growth bonus by current field farmer-
    #     majority — credit +3×P only on fields `player` would actually score
    #     (counts[opp] <= counts[player]). Fixes contested-field overvaluation.
    #   v28_meeple_k: coefficient on a recovery-scaled meeple-economy term, added
    #     AFTER caps, INDEPENDENT of the legacy `meeple_k`.
    #   v28_meeple_recovery_t0: tiles-remaining normalizer — the term is scaled by
    #     min(1, len(deck)/t0) so free meeples decay toward ~0 value in the endgame
    #     (no tiles left to redeploy). 0 == flat (no scaling), == legacy meeple_k shape.
    v28_farm_majority: bool = False
    v28_meeple_k: float = 0.0
    v28_meeple_recovery_t0: int = 0
    # --- v2.9 experimental leaf candidates (opt-in, measurement/v29_leaf_audit/) ---
    # All default neutral == bit-identical v2.8. All force the engine (object) path
    # (flat_leaf.py does NOT implement them — same pattern as the v28_* knobs above).
    # Constructed explicitly in v29 eval/audit scripts (NOT env-built), so a stray
    # env var can never activate them in production. Logic lives in leaf_v29.py.
    #   v29_util_tanh_t: Candidate A. If >0, the FINAL total is win-shaped to
    #     T*tanh(total/T) (point-scale preserved). 0.0 == off (linear, == v2.8).
    #   v29_meeple_curve: Candidate B. A value-by-free-meeple-count table (tuple,
    #     index = count 0..7). When set, REPLACES the flat meeple_k term with the
    #     symmetric curve differential. None == off.
    #   v29_punish_k / v29_farm_access_k: Candidates D / E (stubs in leaf_v29.py).
    v29_util_tanh_t: float = 0.0
    v29_meeple_curve: tuple | None = None
    v29_punish_k: float = 0.0
    v29_farm_access_k: float = 0.0
    # --- v2.9 C7 second wave (opt-in, measurement/classical_search/C7_LEAF_TERMS_DESIGN.md) ---
    # TWO new leaf terms, both default OFF == bit-identical champion (curve125). Unlike the
    # A/D/E stubs above, these are FLAT-implementable (curve/return/flip stay on the fast cy
    # float path); only util_tanh/punish/farm_access still force the object path. Added as
    # two SEPARATE gated adds (float add is non-associative) in a fixed order R-then-F.
    #   v29_meeple_return_k: Term R. Meeple-return liquidity — credits each committed,
    #     RETURNABLE meeple with P(feature closes) × marginal-curve-value-of-one-free-meeple
    #     (the dcurve step). REQUIRES a curve (raises ValueError if set with curve None).
    #   v29_farm_flip_k: Term F. Farm majority-flip anticipation — smooths base's hard
    #     sign(margin)·V step on CONTESTED fields by margin + free-meeple liquidity.
    # ⚠️ Adding these fields changes dataclasses.asdict(cfg); the frozen-cfg recipe
    # (snapshot._frozen_config_hash + its 8 mirrors) EXCLUDES the default-off set
    # {bag_close:False, v29_meeple_return_k:0.0, v29_farm_flip_k:0.0} so 7fc930b8 / 158f17ff
    # recompute UNCHANGED. Full-asdict manifest/golden hashes DO shift (expected).
    v29_meeple_return_k: float = 0.0
    v29_farm_flip_k: float = 0.0
    # --- v2.10 bag-aware closure (Track B, 2026-07-04) --------------------------
    # bag_close: when True, the FLAT closure-anticipation bonus consults the
    # REMAINING-TILE MULTISET (docs/V210_LEAF_SPEC_2026-07-04.md) — a feature the
    # bag can no longer complete gets P(closure)=0 EXACTLY. Flat-path ONLY
    # (flat_leaf implements it via _bag_stats; the object/engine path fails loud).
    # Default False == bit-identical v2.9. Promotes the CARCASSONNE_V210_BAG_CLOSE
    # module/env flag to a per-side LeafConfig knob so the game-gate harness can
    # toggle it asymmetrically; the module/env flag still applies when cfg is None
    # (back-compat) and DEFAULT_CONFIG mirrors it (see _config_from_env).
    # ⚠️ Adding this field CHANGES dataclasses.asdict(cfg) -> the frozen v2.9
    # config_hash (7fc930b82801cb43, governance/LEAF_SUBSTRATES.yaml) shifts; the
    # step2_pens/feature_graph provenance asserts pin that hash and must be
    # re-frozen if bag_close is ever folded into a frozen substrate.
    bag_close: bool = False
    # --- F6 SOFT CAP on the closure-anticipation bonus (candidate-only, CL-063) ----
    # The hard cap `_capped(bonus, cap) = min(bonus, cap)` TRUNCATES the surviving
    # `bonus_overflow_self` residual (CL-063 leaf-residual mining). F6 replaces the
    # clamp with a SOFT cap: linear credit `slope` for the bonus ABOVE the cap.
    #   soft(x, c, s) = x               if x <= c
    #                   c + s*(x - c)   if x >  c
    # s=0.0 == the current hard cap (BIT-EXACT: the s==0 branch routes through the
    # UNCHANGED `_capped`/min path — default traffic never touches the new arithmetic);
    # s=1.0 == uncapped (identity). PRIMARY target is the SELF bonus; the OPP slope is
    # kept independently controllable (mirrors bonus_cap / opp_bonus_cap).
    # Default OFF (0.0) == bit-identical to the champion. Flat-implementable — stays on
    # the fast cy float path (one extra branch); does NOT force the object path.
    # ⚠️ Adding these fields CHANGES dataclasses.asdict(cfg). BOTH the frozen-cfg recipe
    # (snapshot._frozen_config_hash + its 8 mirrors) AND the harness _leaf_hash
    # (c5_leaf_override._leaf_dict, the a36d2e15 dialect) EXCLUDE them WHILE 0.0, so the
    # champion's 6dfffd57 / 158f17ff / 7fc930b8 / a36d2e15 all recompute UNCHANGED. A
    # candidate that SETS a slope shifts the hash (it is a different leaf — as intended).
    soft_cap_slope: float = 0.0
    opp_soft_cap_slope: float = 0.0
    # --- F7b FARM-TERM KNOCKOUTS (measurement-only ablation, roadmap F7b) ----------
    # The farm contribution enters the leaf in TWO structurally separate places, and
    # neither had a knob before this (which is exactly why the F7 ablation deferred
    # the farm cells). These two default-OFF fields sever them independently:
    #   farm_base_off:   drop farm scoring from the BASE term — `_final_scores` stops
    #     awarding `3 x #finished-adjacent-cities` to the field majority. The leaf's
    #     base becomes "cities + roads + cloisters" only.
    #   farm_growth_off: drop the FARM-GROWTH block of the closure-anticipation bonus
    #     — the leaf stops crediting `P(closure) x 3` for incomplete cities adjacent
    #     to the player's fields. City-closure and cloister anticipation are untouched.
    # ⚠️ SCOPE: these knock the term out of the LEAF only. `flat_base_score` called
    # WITHOUT the flag (its default) is unchanged, so the exact endgame solver's
    # terminal evaluation — the TRUE final score, `endgame_solver` line "Leaf value =
    # the REAL final score differential" — keeps full farm scoring on both sides of an
    # ablation cell. That is deliberate: F7b ablates the heuristic, not the rules.
    # ⚠️ FLAT PATH ONLY. `flat_leaf.py` and the Rust leaf implement them; the object
    # (engine) path does NOT and fails loud rather than silently dropping the knockout,
    # and `flat_leaf_cy.pyx` deliberately does NOT implement them (F7b decision: the
    # cells run `--backend rust`, where no Python leaf is computed at all), so a SET
    # knob routes OFF the cy fast path to the bit-exact pure-Python flat leaf.
    # ⚠️ Adding these fields CHANGES dataclasses.asdict(cfg). BOTH the frozen-cfg recipe
    # (snapshot._frozen_config_hash + its mirrors) AND the harness _leaf_hash
    # (c5_leaf_override._leaf_dict, the a36d2e15 dialect) EXCLUDE them WHILE False, so
    # the champion's 6dfffd57 / 158f17ff / 7fc930b8 / a36d2e15 all recompute UNCHANGED.
    # A candidate that SETS one shifts the hash (it is a different leaf — as intended).
    farm_base_off: bool = False
    farm_growth_off: bool = False
    # --- Part C PHASE MULTIPLIER on the v2.9 meeple curve (prereg
    # measurement/curve_shape_scope_20260809/PREREG_DRAFT.md §4) -------------------
    # Multiply the meeple-economy differential `curve[m_self] - curve[m_opp]` by a
    # mean-1-renormalized linear function of tiles-remaining, so meeple value can
    # depend on game PHASE without changing the term's mean MAGNITUDE:
    #     f(k; beta) = clip(1 + beta*(k - 35)/35, 0.0, 2.0) / v29_phase_norm
    # with k = `fair_agent.k_remaining(state)` = len(deck) + (next_tile is not None).
    # `v29_phase_norm` is a RUN-LEVEL SCALAR (E[f] over the empirical k-distribution
    # of a game, `scripts/classical_search/compute_phase_norm.py`) supplied by the
    # caller — deliberately NOT computed inside the leaf, which must stay a pure
    # deterministic function of (state, cfg) for hashing and py/cy/rust reconciliation.
    # The renormalization is the methodological point: without it beta moves the term's
    # SCALE, which is the confound that invalidated the 2026-06-22
    # `v28_meeple_recovery_t0` kill. (Do NOT confuse the two — v28 is a different,
    # confounded, object-path-only lever.)
    # ⚠️ beta == 0.0 takes an EARLY BRANCH through the unmodified expression (not a
    # multiply by 1.0), so default traffic is byte-identical, not merely equal.
    # ⚠️ Adding these fields CHANGES dataclasses.asdict(cfg). BOTH the frozen-cfg recipe
    # (snapshot._frozen_config_hash + its mirrors) AND the harness _leaf_hash
    # (c5_leaf_override._leaf_dict, the a36d2e15 dialect) EXCLUDE them WHILE at their
    # defaults, so 6dfffd57 / 158f17ff / 7fc930b8 / a36d2e15 all recompute UNCHANGED.
    v29_phase_beta: float = 0.0
    v29_phase_norm: float = 1.0
    # --- TARGETED DENIAL on near-complete large opponent cities (candidate-only,
    # BACKLOG 2026-05-16 item 3 / LEVER_INDEX "targeted denial", building 2026-08-11) ---
    # Hypothesis: the leaf under-fears the CONJUNCTION of large AND near-complete
    # opponent cities — the capped opponent-anticipation term (`opp_bonus_cap`) can
    # never express more than `opp_bonus_cap` points of fear, so the champion won't
    # spend a tile to block where a strong human would. For each OPPONENT-STRICT-
    # MAJORITY incomplete city with (anticipated completed value `city_root_delta`
    # >= denial_size_min) AND (near-complete: 0 < open edges <= denial_open_max),
    # the leaf subtracts `denial_dose * (delta - denial_size_min + 1)` ON TOP of the
    # existing anticipation, EXPLICITLY NOT subject to `opp_bonus_cap` — escaping
    # the cap for near-complete features is the entire point of the term (see
    # flat_leaf.flat_denial_term). Tied cities never fire (both majority-score);
    # own cities never fire from the evaluating player's POV.
    #   denial_dose:     float, 0.0 (default) == term fully off == today's leaf,
    #                    via an early branch (never an add of 0.0).
    #   denial_size_min: anticipated-completed-value threshold, points.
    #   denial_open_max: max distinct open (empty-adjacent) cells to count as
    #                    "near-complete" (same open_n the closure schedule keys on).
    # ⚠️ FLAT PATH ONLY. `flat_leaf.py` and the Rust leaf implement it; the object
    # (engine) path FAILS LOUD below, and `flat_leaf_cy.pyx` deliberately does NOT
    # implement it (the F7b pattern: candidate cells run `--backend rust`, where no
    # Python leaf is computed), so a SET dose routes off the cy fast path to the
    # bit-exact pure-Python flat leaf.
    # ⚠️ Adding these fields CHANGES dataclasses.asdict(cfg). BOTH the frozen-cfg
    # recipe (snapshot._frozen_config_hash + its mirrors) AND the harness _leaf_hash
    # (c5_leaf_override._leaf_dict, the a36d2e15 dialect) EXCLUDE them WHILE at their
    # defaults, so 6dfffd57 / 158f17ff / 7fc930b8 / a36d2e15 all recompute UNCHANGED.
    # A candidate that SETS a dose shifts the hash (it is a different leaf — intended).
    denial_dose: float = 0.0
    denial_size_min: float = 8.0
    denial_open_max: int = 2
    # --- OPEN-CITY DISCIPLINE — penalize the ACTING PLAYER'S OWN large open cities
    # (candidate-only; BACKLOG 2026-05-16 / LEVER_INDEX "penalize large open cities" —
    # the flagged NEVER-TRIED leaf term, externally endorsed 2026-08-12 by four
    # independent strategy guides, docs/research/PRO_STRATEGY_SCAN_2026-08-12.md §F1;
    # spec measurement/opencity_term_20260812/TERM_SPEC.md, building 2026-08-12) -------
    # Mechanism (F1): city scoring gives NO per-tile size bonus (2/tile + 2/shield
    # whether the city is 2 tiles or 12) while completion probability FALLS and
    # steal/merge exposure RISES with every open edge. The champion's leaf prices a
    # city's anticipated value (`closure_p[open_n] * city_root_delta`) but never its
    # RISK, so a big wide-open city reads as an asset when a strong human reads it as
    # a liability. For each city where the side holds a STRICT weighted-meeple
    # majority, is INCOMPLETE, has `0 < open_n` open cells with `open_n >=
    # opencity_edge_min`, and spans `tiles >= opencity_size_min` DISTINCT TILES, the
    # penalty is
    #     (tiles - opencity_size_min + 1) * (open_n - opencity_edge_min + 1)
    # (linear escalation on BOTH axes; exactly 1 at the joint threshold corner). The
    # leaf subtracts `opencity_dose * T`, where T is the SIGNED differential
    # `pen(self) - pen(opp)` (symmetric, the default) or `pen(self)` alone
    # (asymmetric). ⚠️ The penalty ADJUSTS the existing city terms, it never replaces
    # them: the closure-anticipation credit for the same city is untouched.
    #   opencity_dose:      float, 0.0 (default) == term fully off == today's leaf,
    #                       via an early branch (never a subtract of 0.0).
    #   opencity_size_min:  city SIZE threshold in DISTINCT TILES. ⚠️ NOT the same
    #                       units as `denial_size_min`, which is in POINTS
    #                       (`city_root_delta`). Tiles is the F1 axis: the marginal
    #                       tile of a big city earns the same 2 points as the
    #                       marginal tile of a small one while adding all the risk,
    #                       so the mechanism is about the OBJECT's extent, not its
    #                       value.
    #   opencity_edge_min:  minimum distinct open (empty-adjacent) cells for the
    #                       penalty to fire — the same `open_n` the closure schedule
    #                       keys on. Default 2 encodes the guides' converged rule
    #                       ("prefer one open edge, tolerate two, avoid three"):
    #                       1-open never fires, 2-open weighs 1, 3-open weighs 2.
    #   opencity_symmetric: True (default) -> T = pen(self) - pen(opp), which keeps
    #                       the leaf ANTISYMMETRIC (`V(s,p) == -V(s,1-p)`) the way
    #                       every other structural term is. False -> T = pen(self)
    #                       only, an own-side-only penalty that breaks antisymmetry
    #                       (the way `denial_dose` already does) — kept as an
    #                       explicit ablation, not a default.
    # ⚠️ FLAT PATH ONLY. `flat_leaf.py` and the Rust leaf implement it; the object
    # (engine) path FAILS LOUD below, and `flat_leaf_cy.pyx` deliberately does NOT
    # implement it (the F7b/denial pattern: candidate cells run `--backend rust`,
    # where no Python leaf is computed), so a SET dose routes off the cy fast path to
    # the bit-exact pure-Python flat leaf.
    # ⚠️ Adding these fields CHANGES dataclasses.asdict(cfg). BOTH the frozen-cfg
    # recipe (snapshot._frozen_config_hash + its mirrors) AND the harness _leaf_hash
    # (c5_leaf_override._leaf_dict, the a36d2e15 dialect) EXCLUDE them WHILE at their
    # defaults, so 6dfffd57 / 158f17ff / 7fc930b8 / a36d2e15 all recompute UNCHANGED.
    # A candidate that SETS a dose shifts the hash (it is a different leaf — intended).
    opencity_dose: float = 0.0
    opencity_size_min: float = 4.0
    opencity_edge_min: int = 2
    opencity_symmetric: bool = True


def _config_from_env() -> LeafConfig:
    """Build the default LeafConfig from the CARCASSONNE_V25_* env vars.

    Schedule history: v2.5 halved v2's {1:1.0, 2:0.5, 3:0.25} (the v2
    diagnostic showed the bonus was 4-7x the v1 base, saturating tanh).
    v2.6 (ONE_OPEN_ONLY) restricts to 1-open features. v2.7 (DROP_THREE_OPEN,
    the production default) keeps {1, 2} — the 3-open lottery tickets were
    noise. `CARCASSONNE_V25_CAP` default 5.0 is the pre-v2.7 value; the v2.7
    production runs set CAP=12 explicitly.
    """
    if os.environ.get("CARCASSONNE_V25_ONE_OPEN_ONLY") == "1":
        closure_p: dict[int, float] = {1: 1.0}
    elif os.environ.get("CARCASSONNE_V25_DROP_THREE_OPEN") == "1":
        closure_p = {1: 0.5, 2: 0.2}
    else:
        closure_p = {1: 0.5, 2: 0.2, 3: 0.05}
    bonus_cap = float(os.environ.get("CARCASSONNE_V25_CAP", "5.0"))
    # v2.9 meeple liquidity curve (Candidate B). Comma-separated value-by-free-count
    # table (8 entries, free-meeple count 0..7); when set it REPLACES the flat
    # meeple_k term (see leaf_v29._meeple_curve_term / flat_leaf curve branch). Unset
    # == None == off (production v2.8 unchanged). The frozen v2.9 substrate sets
    # CARCASSONNE_V29_MEEPLE_CURVE="-8,-4,-1,0,2,3,4,5" (governance/LEAF_SUBSTRATES.yaml).
    _v29_curve_env = os.environ.get("CARCASSONNE_V29_MEEPLE_CURVE")
    v29_meeple_curve = (
        tuple(float(x) for x in _v29_curve_env.split(",")) if _v29_curve_env else None
    )
    return LeafConfig(
        closure_p=closure_p,
        bonus_cap=bonus_cap,
        opp_bonus_cap=float(os.environ.get("CARCASSONNE_V25_OPP_CAP", str(bonus_cap))),
        meeple_k=float(os.environ.get("CARCASSONNE_V25_MEEPLE_K", "0.0")),
        v29_meeple_curve=v29_meeple_curve,
        value_blend=float(os.environ.get("CARCASSONNE_V25_VALUE_BLEND", "0.0")),
        residual_scale=float(os.environ.get("CARCASSONNE_V25_RESIDUAL_SCALE", "0.0")),
        tile_counting_closure=(os.environ.get("CARCASSONNE_V25_TILE_COUNTING") == "1"),
        closure_continuous_slack=float(os.environ.get("CARCASSONNE_V25_CLOSURE_SLACK", "0.0")),
        # v2.8 experimental knobs — default OFF so production DEFAULT_CONFIG is unchanged.
        v28_farm_majority=(os.environ.get("CARCASSONNE_V28_FARM_MAJORITY") == "1"),
        v28_meeple_k=float(os.environ.get("CARCASSONNE_V28_MEEPLE_K", "0.0")),
        v28_meeple_recovery_t0=int(os.environ.get("CARCASSONNE_V28_MEEPLE_RECOVERY_T0", "0")),
        # v2.10 Track B: env-global bag-aware closure (back-compat with the module
        # flag). Default off == unchanged production DEFAULT_CONFIG. Mirroring the
        # env flag here keeps the env-global gate working through virtual_score_v2,
        # which always forwards a (non-None) cfg to flat_virtual_score_v2.
        bag_close=(os.environ.get("CARCASSONNE_V210_BAG_CLOSE") == "1"),
        # Part C phase multiplier — default 0.0/1.0 == no phase dependence == the
        # unmodified champion expression (early branch, not a multiply by 1.0).
        v29_phase_beta=float(os.environ.get("CARCASSONNE_V29_PHASE_BETA", "0.0")),
        v29_phase_norm=float(os.environ.get("CARCASSONNE_V29_PHASE_NORM", "1.0")),
        # Targeted denial — default 0.0 == term fully off == unchanged production
        # DEFAULT_CONFIG (the phase-beta pattern: env-buildable candidate knob).
        denial_dose=float(os.environ.get("CARCASSONNE_DENIAL_DOSE", "0.0")),
        denial_size_min=float(os.environ.get("CARCASSONNE_DENIAL_SIZE_MIN", "8.0")),
        denial_open_max=int(os.environ.get("CARCASSONNE_DENIAL_OPEN_MAX", "2")),
        # Open-city discipline — default 0.0 == term fully off == unchanged production
        # DEFAULT_CONFIG (the phase-beta / denial pattern: env-buildable candidate knob).
        opencity_dose=float(os.environ.get("CARCASSONNE_OPENCITY_DOSE", "0.0")),
        opencity_size_min=float(os.environ.get("CARCASSONNE_OPENCITY_SIZE_MIN", "4.0")),
        opencity_edge_min=int(os.environ.get("CARCASSONNE_OPENCITY_EDGE_MIN", "2")),
        opencity_symmetric=(os.environ.get("CARCASSONNE_OPENCITY_SYMMETRIC", "1") == "1"),
    )


DEFAULT_CONFIG: LeafConfig = _config_from_env()

# Order-independent bonus summation (2026-06-09, leaf-rewrite branch). The
# closure-anticipation bonus sums non-associative floats (0.2-multiples) in the
# iteration order of a SET (farm.farmer_connections_with_coordinate) — which is
# arbitrary (it depends on which meeple populated the shared farm/city cache
# first). Different valid orders differ by ~1 ULP, which flips int(round(score))
# at exact-.5 rounding boundaries in ~7e-5 of leaf evals. This is a latent
# order-sensitivity in the v2.7 leaf itself (same CLASS as the 2026-05-29
# find_farm start-dependence fix). When True, the bonus is accumulated with
# math.fsum (the correctly-rounded sum, order-independent), making the leaf a
# well-defined function of the contribution multiset and the compact-leaf path a
# TRUE bit-exact drop-in. Default OFF: turning it on CHANGES production's exact
# output (by those same ~1e-4 ±1 flips) vs the running flywheel, so it must be
# adopted as a deliberate, gated decision (Phase 4 / the compact-merge), not
# silently. Read as a module attribute so a runtime flip (the gate) is seen.
CANONICAL_BONUS_SUM = False

# Back-compat module constants — some tests + diagnose_v2.py import these
# directly. They mirror DEFAULT_CONFIG; new code should pass a LeafConfig.
_CLOSURE_P: dict[int, float] = DEFAULT_CONFIG.closure_p
_BONUS_CAP: float = DEFAULT_CONFIG.bonus_cap
_OPP_BONUS_CAP: float = DEFAULT_CONFIG.opp_bonus_cap
_MEEPLE_K: float = DEFAULT_CONFIG.meeple_k


def _v28_active(cfg: "LeafConfig") -> bool:
    """True iff any v2.8 experimental patch is enabled on `cfg`. Used to force the
    engine (object) path — flat_leaf.py does not implement these. Off by default,
    so production cfgs return False (flat fast path stays bit-exact v2.7)."""
    return cfg.v28_farm_majority or cfg.v28_meeple_k != 0.0


def _v29_active(cfg: "LeafConfig") -> bool:
    """True iff any v2.9 candidate is enabled on `cfg`. Forces the engine (object)
    path — leaf_v29.py builds on the object helpers; flat_leaf does not implement it.
    Off by default, so production/v2.8 cfgs return False (flat fast path unchanged)."""
    return (cfg.v29_util_tanh_t > 0.0 or cfg.v29_meeple_curve is not None
            or cfg.v29_punish_k != 0.0 or cfg.v29_farm_access_k != 0.0
            or cfg.v29_meeple_return_k != 0.0 or cfg.v29_farm_flip_k != 0.0)


def _v29_curve_only(cfg: "LeafConfig") -> bool:
    """True iff the ONLY active v2.9 term is the meeple curve (Candidate B). The
    curve is a pure `state.meeples` table lookup — flat_leaf.py implements it
    directly (and the curve-aware pure-Python flat path is bit-exact to the object
    path), so a curve-only cfg can STAY on the fast flat path. The other v2.9 terms
    (A util_tanh / D punish / E farm) need the engine/object helpers, so they still
    force the object path."""
    return (cfg.v29_meeple_curve is not None
            and cfg.v29_util_tanh_t <= 0.0
            and cfg.v29_punish_k == 0.0
            and cfg.v29_farm_access_k == 0.0
            and cfg.v29_meeple_return_k == 0.0
            and cfg.v29_farm_flip_k == 0.0)


def _v29_flat_eligible(cfg: "LeafConfig") -> bool:
    """True iff every ACTIVE v2.9 term is one the flat/cy path implements (the
    curve, C7 Term R meeple-return, C7 Term F farm-flip). The object-only terms
    (A util_tanh / D punish / E farm_access) still force the engine path. Used by
    the flat-redirect condition (generalizes `_v29_curve_only`, which stays for the
    tests that import it). Not gated by `_v29_active` itself — callers AND it with
    `_v29_active` so a wholly-inactive cfg still routes flat by the outer USE_FLAT_LEAF."""
    return (cfg.v29_util_tanh_t <= 0.0
            and cfg.v29_punish_k == 0.0
            and cfg.v29_farm_access_k == 0.0)


def _field_owner_counts(state) -> dict:
    """v2.8 (v28_farm) helper. One pass over BOTH players' placed farmers → map
    each field (keyed by `frozenset(farm.farmer_connections_with_coordinate)`, the
    SAME key the closure bonus dedupes on) to `[count_p0, count_p1]` (big farmer =
    2). Lets the farm-growth bonus be gated to the field's majority owner — the
    player who would actually score the field's cities at game end. Uses the
    shared `_farm_cache` if attached (find_farm_by_coordinate reads it). Engine
    path only; not in the production hot path."""
    counts: dict = {}
    for p in (0, 1):
        for mp in state.placed_meeples[p]:
            if mp.meeple_type not in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                continue
            farm = FarmUtil.find_farm_by_coordinate(
                game_state=state, position=mp.coordinate_with_side
            )
            key = frozenset(farm.farmer_connections_with_coordinate)
            c = counts.get(key)
            if c is None:
                c = [0, 0]
                counts[key] = c
            c[p] += 2 if mp.meeple_type == MeepleType.BIG_FARMER else 1
    return counts


def _close_prob(open_positions: int, closure_p: dict[int, float] | None = None) -> float:
    """Probability that an incomplete feature closes by game-end given how
    many adjacent positions still need tiles. `closure_p` defaults to the
    env-built DEFAULT_CONFIG schedule."""
    if open_positions <= 0:
        return 1.0  # already closed (defensive — shouldn't be called)
    if closure_p is None:
        closure_p = DEFAULT_CONFIG.closure_p
    return closure_p.get(open_positions, 0.0)


_CARDINAL_SIDES = (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT)


def _deck_city_supply(state) -> int:
    """Number of tiles still in the deck that carry at least one city edge.

    A tile is rotated freely on placement, so any cardinal city edge means
    the tile *could* be used to extend a city — a deliberately permissive
    (over-counting) proxy for true placeability (true placeability needs an
    adjacency search, too expensive for the leaf eval hot path). Used by the
    Option-1 tile-counting closure gate: a city needing N more tiles cannot
    close if fewer than N city-bearing tiles remain in the deck."""
    n = 0
    for tile in state.deck:
        if any(tile.get_type(s) == TerrainType.CITY for s in _CARDINAL_SIDES):
            n += 1
    return n


def _supply_factor(supply: int, need: int, slack: float) -> float:
    """Continuous deck-aware closure discount (Option-1 step 5, 2026-05-17).

    Where the tile-counting gate is a hard cliff (P→0 only when the deck
    *literally cannot* finish a feature), this scales P(closure) smoothly by
    how plentiful the usable deck supply is. factor=1.0 once supply reaches
    `need * slack` (closure unconstrained by the deck), ramping linearly to
    0.0 as supply→0. `slack` > 1 reflects that not every usable drawn tile
    lands on this feature, so supply must exceed bare `need` severalfold
    before closure is treated as supply-unconstrained."""
    if need <= 0 or slack <= 0.0:
        return 1.0
    f = supply / (need * slack)
    if f >= 1.0:
        return 1.0
    return f if f > 0.0 else 0.0


def _neighbor_coord(coord: Coordinate, side: Side) -> Coordinate | None:
    """Coordinate of the tile adjacent to `coord` across `side`. Returns
    None for non-cardinal sides (e.g. farmer corners), which are handled
    differently in scoring."""
    if side == Side.TOP:
        return Coordinate(coord.row - 1, coord.column)
    if side == Side.BOTTOM:
        return Coordinate(coord.row + 1, coord.column)
    if side == Side.LEFT:
        return Coordinate(coord.row, coord.column - 1)
    if side == Side.RIGHT:
        return Coordinate(coord.row, coord.column + 1)
    return None


def _open_city_positions(state, city: "City") -> int:
    """Number of unique adjacent board positions that need a tile (with a
    matching city side) to close this city. Coarse — counts empty neighbors
    of city-side positions, deduplicated."""
    seen: set[tuple[int, int]] = set()
    for pos in city.city_positions:
        neighbor = _neighbor_coord(pos.coordinate, pos.side)
        if neighbor is None:
            continue
        if 0 <= neighbor.row < len(state.board) and 0 <= neighbor.column < len(state.board[0]):
            if state.board[neighbor.row][neighbor.column] is None:
                seen.add((neighbor.row, neighbor.column))
    return len(seen)


def _open_road_positions(state, road) -> int:
    """Number of unique adjacent empty board cells across the road component's
    edges — the road analog of `_open_city_positions` (over `road.road_positions`).
    Used by the C7 Term R (meeple-return liquidity) object path + reconcile
    reference. Deduplicated distinct empty neighbours."""
    seen: set[tuple[int, int]] = set()
    for pos in road.road_positions:
        neighbor = _neighbor_coord(pos.coordinate, pos.side)
        if neighbor is None:
            continue
        if 0 <= neighbor.row < len(state.board) and 0 <= neighbor.column < len(state.board[0]):
            if state.board[neighbor.row][neighbor.column] is None:
                seen.add((neighbor.row, neighbor.column))
    return len(seen)


def _city_closure_delta(state, city: "City") -> int:
    """Score delta if this incomplete city closed: full credit minus partial
    credit. For a city with T tiles and S shields, partial = T+S, full =
    2T+2S, so delta = T+S. Cathedrals (inns flag) are scored at 3pts/tile
    when finished, 0 when unfinished — different math, handled separately."""
    if city.finished:
        return 0
    has_cathedral = False
    coords: set[tuple[int, int]] = set()
    for pos in city.city_positions:
        c = pos.coordinate
        tile = state.board[c.row][c.column]
        if tile is None:
            continue
        if tile.inn:  # engine reuses .inn as the cathedral flag on city tiles
            has_cathedral = True
        coords.add((c.row, c.column))
    delta = 0
    for r, col in coords:
        tile = state.board[r][col]
        if has_cathedral:
            # incomplete cathedral city = 0pts, complete = 3pts/tile (or 6 with shield).
            # Risk of closure with cathedral is high reward, but our coarse
            # heuristic doesn't distinguish; treat as plain city for delta.
            delta += 6 if tile.shield else 3
        else:
            delta += 2 if tile.shield else 1
    return delta


def _surrounding_count(state, coord: Coordinate) -> int:
    """Number of placed tiles among the 8 cells surrounding `coord`. Same
    metric the engine uses to score a cloister/chapel/flowers."""
    n = 0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            r, c = coord.row + dr, coord.column + dc
            if 0 <= r < len(state.board) and 0 <= c < len(state.board[0]):
                if state.board[r][c] is not None:
                    n += 1
    return n


def _closure_anticipation_bonus(state, player: int, cfg: "LeafConfig | None" = None) -> float:
    """Sum of P(closure) × score-delta over all of `player`'s placed meeples
    on incomplete features.

    `cfg` selects the closure-probability schedule (and, for Step 2, the
    tile-counting gate); defaults to DEFAULT_CONFIG.

    Dedupes features (cities and farms) across meeples — multiple meeples
    on the same farm/city contribute the bonus exactly once. This both
    fixes a real over-counting bug (the engine itself only scores each
    farm once per player regardless of how many of that player's farmers
    are on it) AND cuts CPU work by skipping repeated find_city /
    find_farm_by_coordinate calls on the same logical feature.
    Identification is by canonical content (frozenset of city positions /
    farmer connections) since the engine returns a fresh City/Farm
    object on each call (no __eq__/__hash__).
    """
    if cfg is None:
        cfg = DEFAULT_CONFIG
    closure_p = cfg.closure_p
    # v2.8 (v28_farm): precompute field farmer-majority once per call so the
    # farm-growth branch can suppress credit on fields the opponent will win.
    opp = 1 - player
    owner_counts = _field_owner_counts(state) if cfg.v28_farm_majority else None
    # Deck-aware closure (Option-1 steps 2 & 5): a feature whose open
    # positions outnumber what the remaining deck can supply is unlikely (or
    # unable) to close by game-end. `gate` = the step-2 hard cliff (P→0 when
    # the deck literally can't finish it); `continuous` = the step-5 smooth
    # ramp, which overrides the gate when on. When both are off (v2.7
    # default) the supply scan is skipped entirely — zero overhead.
    gate = cfg.tile_counting_closure
    slack = cfg.closure_continuous_slack
    continuous = slack > 0.0
    _need_supply = gate or continuous
    deck_size = len(state.deck) if _need_supply else 0
    city_supply = _deck_city_supply(state) if _need_supply else 0
    bonus = 0.0
    # Order-independent accumulation: when CANONICAL_BONUS_SUM is on, collect
    # contributions and math.fsum them at the end instead of summing in the
    # (arbitrary) set-iteration order. OFF -> _contribs stays None and only the
    # running `bonus += ...` path runs, byte-identical to prior production.
    _contribs = [] if CANONICAL_BONUS_SUM else None
    seen_cities: set[frozenset] = set()
    seen_farms: set[frozenset] = set()
    # Cities counted via farm-growth bonus stay deduped across all the
    # player's farms — same incomplete city adjacent to two farms shouldn't
    # be paid for twice.
    counted_growth_cities: set[frozenset] = set()

    for mp in state.placed_meeples[player]:
        coord_side = mp.coordinate_with_side
        coord = coord_side.coordinate
        tile = state.board[coord.row][coord.column]
        if tile is None:
            continue
        terrain = tile.get_type(coord_side.side)

        if terrain == TerrainType.CITY:
            city = CityUtil.find_city(game_state=state, city_position=coord_side)
            city_key = frozenset(city.city_positions)
            if city_key in seen_cities:
                continue
            seen_cities.add(city_key)
            if city.finished:
                continue
            open_n = _open_city_positions(state, city)
            if open_n <= 0:
                continue  # D16: board-edge city with 0 in-bounds open positions physically can't close — no anticipation bonus (don't fall into _close_prob's defensive 1.0)
            p = _close_prob(open_n, closure_p)
            if continuous:
                p *= _supply_factor(city_supply, open_n, slack)
            elif gate and (deck_size < open_n or city_supply < open_n):
                p = 0.0  # deck can no longer complete this city
            if p > 0:
                delta = _city_closure_delta(state, city)
                _c = p * delta
                bonus += _c
                if _contribs is not None:
                    _contribs.append(_c)

        elif terrain == TerrainType.CHAPEL or terrain == TerrainType.FLOWERS:
            n_surround = _surrounding_count(state, coord)
            needed = 8 - n_surround
            if needed > 0:
                p = _close_prob(needed, closure_p)
                if continuous:
                    p *= _supply_factor(deck_size, needed, slack)
                elif gate and deck_size < needed:
                    p = 0.0  # not enough tiles left to surround the cloister
                if p > 0:
                    # Cloister already scores 1 + n_surround in v1's partial.
                    # If closed, scores 9. Delta = 8 - n_surround.
                    _c = p * (8 - n_surround)
                    bonus += _c
                    if _contribs is not None:
                        _contribs.append(_c)

        elif mp.meeple_type in (MeepleType.FARMER, MeepleType.BIG_FARMER):
            # Farm growth: for each incomplete city adjacent to this farm,
            # add 3 × P(closes). Cities that ARE already complete are
            # already counted by v1 — don't double-count.
            farm = FarmUtil.find_farm_by_coordinate(game_state=state, position=coord_side)
            farm_key = frozenset(farm.farmer_connections_with_coordinate)
            if farm_key in seen_farms:
                continue
            seen_farms.add(farm_key)
            if owner_counts is not None:
                # v28_farm: suppress the entire field's growth credit when the
                # opponent holds a strict farmer majority — those cities score for
                # THEM at game end, so +3×P to `player` is spurious. Ties keep the
                # credit (canonical rule: tied farmers both score).
                oc = owner_counts.get(farm_key)
                if oc is not None and oc[opp] > oc[player]:
                    continue
            for fc in farm.farmer_connections_with_coordinate:
                cities = CityUtil.find_cities(
                    game_state=state,
                    coordinate=fc.coordinate,
                    sides=fc.farmer_connection.city_sides,
                )
                for city in cities:
                    city_key = frozenset(city.city_positions)
                    if city_key in counted_growth_cities:
                        continue
                    counted_growth_cities.add(city_key)
                    if city.finished:
                        continue  # already in v1 farm score
                    open_n = _open_city_positions(state, city)
                    if open_n <= 0:
                        continue  # D16: same — an unclosable board-edge city earns no farm-growth bonus
                    p = _close_prob(open_n, closure_p)
                    if continuous:
                        p *= _supply_factor(city_supply, open_n, slack)
                    elif gate and (deck_size < open_n or city_supply < open_n):
                        p = 0.0  # deck can no longer complete this city
                    if p > 0:
                        _c = p * 3
                        bonus += _c
                        if _contribs is not None:
                            _contribs.append(_c)
        # ROAD: no closure delta (complete and incomplete both score 1pt/tile
        # without inn modifier; with inn, finished=2/tile, unfinished=0).
        # Inn-roads ARE a closure-blind spot but rare in 2p River+Farmers.
        # Skip for v2; add in v3 if road denial shows up in failure modes.

    # uncapped — caller decides which cap to apply (self vs opp). When canonical,
    # return the order-independent fsum of contributions; else the running sum
    # (byte-identical to prior production).
    if _contribs is not None:
        return math.fsum(_contribs)
    return bonus


def _capped(bonus: float, cap: float) -> float:
    if bonus > cap:
        return cap
    return bonus


def _soft_capped(bonus: float, cap: float, slope: float) -> float:
    """F6 soft cap (CL-063): linear credit `slope` to the closure bonus ABOVE `cap`
    instead of a hard clamp. slope==0.0 reproduces `_capped` (hard clamp) BIT-EXACTLY
    by delegating to the UNCHANGED min path; slope==1.0 is uncapped (identity). For
    0<slope<1 the bonus above the cap keeps `cap + slope*(bonus-cap)`. == the
    flat_leaf._soft_capped / heuristic_prior_mcts inline / cy soft-cap branch."""
    if slope == 0.0:
        return _capped(bonus, cap)
    if bonus > cap:
        return cap + slope * (bonus - cap)
    return bonus


def virtual_score_v2(
    state: "CarcassonneGameState", player: int, cfg: "LeafConfig | None" = None
) -> int:
    """v1 base + closure-anticipation bonus (self) - closure-anticipation
    bonus (opponent), with optional v3 meeple-economy term.

    `cfg` selects the leaf-eval knobs (closure schedule, caps, meeple_k,
    tile-counting). When None, DEFAULT_CONFIG (env-var-built) is used —
    back-compat. Pass an explicit LeafConfig to A/B two leaf variants in
    one process.

    Caps: self bonus capped at `cfg.bonus_cap`, opp bonus at
    `cfg.opp_bonus_cap` (defaults to same; raise opp cap to strengthen the
    denial signal in search).

    v3 meeple term (off when meeple_k=0.0): adds `cfg.meeple_k × (meeples_self
    - meeples_opp)` AFTER caps. `state.meeples[i]` is i's unplaced-meeple
    count (start 7, decrements on placement, returns on closure).
    """
    if state.players != 2:
        raise ValueError(
            f"virtual_score_v2 is implemented for 2-player only; got {state.players}"
        )
    if cfg is None:
        cfg = DEFAULT_CONFIG
    # Flat-leaf redirect (2026-06-09, leaf-rewrite): when USE_FLAT_LEAF is on,
    # compute the leaf via the de-objectified flat path (bit-exact under canonical
    # sum, ~2.26x faster per leaf). Covers BOTH leaf wrappers since they both call
    # virtual_score_v2 here. The flat path does NOT implement the deck-aware closure
    # configs, so fall through to the engine path for those (also the wiring-time
    # guard from the audit: flat must never silently mis-handle tile_counting/
    # continuous). Default OFF -> byte-identical to prior production.
    if flat_leaf.USE_FLAT_LEAF and not (
        cfg.tile_counting_closure or cfg.closure_continuous_slack > 0.0
        or _v28_active(cfg)
        or (_v29_active(cfg) and not _v29_flat_eligible(cfg))
    ):
        # Flat-eligible v2.9 configs (curve / C7 Term R return / Term F flip) stay
        # on the fast flat path — flat_virtual_score_v2 applies them bit-exactly.
        # Only the object-only v2.9 terms (util_tanh/punish/farm_access) fall through.
        return flat_leaf.flat_virtual_score_v2(state, player, cfg)
    if getattr(cfg, "farm_base_off", False) or getattr(cfg, "farm_growth_off", False):
        # F7b farm knockouts are flat-path ONLY (see LeafConfig) — fail loudly rather
        # than silently scoring an INTACT farm term here, which would read as "the
        # knockout is worth nothing" instead of "the knockout never ran".
        raise NotImplementedError(
            "LeafConfig.farm_base_off / farm_growth_off (F7b) require the flat leaf "
            "path (set CARCASSONNE_USE_FLAT_LEAF=1 and use a flat-eligible LeafConfig)"
        )
    if getattr(cfg, "denial_dose", 0.0) != 0.0:
        # Targeted denial is flat-path ONLY (see LeafConfig.denial_dose) — fail
        # loudly rather than silently scoring WITHOUT the denial term here, which
        # would read as "denial is worth nothing" instead of "denial never ran".
        raise NotImplementedError(
            "LeafConfig.denial_dose (targeted denial) requires the flat leaf path "
            "(set CARCASSONNE_USE_FLAT_LEAF=1 and use a flat-eligible LeafConfig)"
        )
    if getattr(cfg, "opencity_dose", 0.0) != 0.0:
        # Open-city discipline is flat-path ONLY (see LeafConfig.opencity_dose) —
        # fail loudly rather than silently scoring WITHOUT the penalty here, which
        # would read as "the term is worth nothing" instead of "the term never ran".
        raise NotImplementedError(
            "LeafConfig.opencity_dose (open-city discipline) requires the flat leaf "
            "path (set CARCASSONNE_USE_FLAT_LEAF=1 and use a flat-eligible LeafConfig)"
        )
    if flat_leaf.V210_BAG_CLOSE or getattr(cfg, "bag_close", False):
        # v2.10 bag-aware closure gate is flat-path ONLY (docs/V210_LEAF_SPEC
        # Track B) — fail loudly rather than silently dropping the gate on the
        # engine/object path (USE_FLAT_LEAF=0, or a deck-aware/v28/v29-non-curve
        # cfg forcing the fallthrough). Covers BOTH the env-global flag and an
        # explicit LeafConfig.bag_close=True.
        raise NotImplementedError(
            "bag-aware closure (CARCASSONNE_V210_BAG_CLOSE=1 or LeafConfig.bag_close=True) "
            "requires the flat leaf path (set CARCASSONNE_USE_FLAT_LEAF=1 and use a "
            "flat-eligible LeafConfig)"
        )
    opp = 1 - player
    # Leaf-pass flood-fill sharing (2026-05-29 speedup): share ONE lazy farm-region
    # memo (`_farm_cache`) and ONE lazy city-component memo (`_city_cache`) across
    # all three consumers in this leaf eval — virtual_score's count_final_scores
    # (on its snapshot) and both closure-bonus passes (on the live state). A
    # state's deepcopy shares Tile/FarmerConnection refs (and CoordinateWithSide
    # city keys are value-hashable), so a cache populated on the live state is
    # valid on virtual_score's snapshot too. find_farm_by_coordinate / find_city
    # read the caches transparently. Detached in finally so neither lingers on a
    # long-lived (e.g. MCTS-tree) state — get_next_state's deepcopy would strip
    # them anyway. USE_FARM_CACHE / USE_CITY_CACHE off -> legacy flood-fills (the
    # bench/gate A/B baselines).
    # REUSE a caller-attached cache if present (e.g. make_v25_value_wrapper shares
    # one cache across the policy-encode AND this leaf-value pass, so the farm
    # input scalars' floods are reused here for free). Only create+detach a cache
    # we own — never delete the caller's, or the encode<->leaf sharing breaks.
    # Compact leaf (2026-06-09): when USE_COMPACT_LEAF is on, pre-populate the
    # shared caches via flat union-find (compact_leaf) instead of leaving them
    # empty for lazy object-BFS fill. Same dicts, same keys/values -> the engine
    # resolves every find_farm/find_city as a hit; bit-exact-gated. The prebuilt
    # cache is shared into virtual_score's snapshot below (valid: the deepcopy
    # shares Tile/FarmerConnection refs, so id()-keyed and value-keyed entries
    # both carry over). Compact OFF -> byte-identical to the prior {} behavior.
    own_farm = (_vs.USE_FARM_CACHE or _vs.USE_COMPACT_LEAF) and not hasattr(state, "_farm_cache")
    own_city = (_vs.USE_CITY_CACHE or _vs.USE_COMPACT_LEAF) and not hasattr(state, "_city_cache")
    if own_farm:
        state._farm_cache = compact_leaf.build_farm_cache(state) if _vs.USE_COMPACT_LEAF else {}
    if own_city:
        state._city_cache = compact_leaf.build_city_cache(state) if _vs.USE_COMPACT_LEAF else {}
    farm_cache = getattr(state, "_farm_cache", None)
    city_cache = getattr(state, "_city_cache", None)
    try:
        base = virtual_score(state, player, farm_cache=farm_cache, city_cache=city_cache)
        # F6 soft cap: slope 0.0 (default/champion) delegates to the hard `_capped`,
        # so default traffic is bit-identical. Per-side slopes are independent.
        bonus_self = _soft_capped(
            _closure_anticipation_bonus(state, player, cfg),
            cfg.bonus_cap, getattr(cfg, "soft_cap_slope", 0.0))
        bonus_opp = _soft_capped(
            _closure_anticipation_bonus(state, opp, cfg),
            cfg.opp_bonus_cap, getattr(cfg, "opp_soft_cap_slope", 0.0))
    finally:
        if own_farm:
            try:
                del state._farm_cache
            except AttributeError:
                pass
        if own_city:
            try:
                del state._city_cache
            except AttributeError:
                pass
    score = base + bonus_self - bonus_opp
    # The flat meeple term is REPLACED by the v2.9 curve when one is set (the curve
    # term is added in apply_v29). Bit-exact when v29_meeple_curve is None.
    if cfg.meeple_k > 0.0 and cfg.v29_meeple_curve is None:
        score += cfg.meeple_k * (state.meeples[player] - state.meeples[opp])
    if cfg.v28_meeple_k != 0.0:
        # v28_meeple: recovery-scaled meeple economy. Free meeples are worth more
        # while tiles remain to redeploy them, ~nothing in the endgame. t0=0 -> flat
        # (== legacy meeple_k shape); t0>0 -> linear decay by remaining deck.
        rf = 1.0
        if cfg.v28_meeple_recovery_t0 > 0:
            rf = min(1.0, len(state.deck) / cfg.v28_meeple_recovery_t0)
        score += cfg.v28_meeple_k * (state.meeples[player] - state.meeples[opp]) * rf
    if _v29_active(cfg):
        # v2.9 candidate terms (B curve, D/E stubs) + win-shaping transform (A).
        # Object-path only (the flat redirect above falls through when v29 active).
        from . import leaf_v29
        score = leaf_v29.apply_v29(state, player, opp, cfg, score)
    return int(round(score))
