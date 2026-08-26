"""Bit-exactness of the v2.9 meeple curve (Candidate B) on the PRODUCTION fast path.

RoD v2 runs self-play gen + train with the frozen v2.9 substrate (`Bmild_cap8`) as
the leaf. Production gen/train use `CARCASSONNE_USE_FLAT_LEAF=1` (+ the cy leaf,
default-ON). The curve was validated ONLY through the object path (leaf_v29.apply_v29);
these tests prove the flat path the production workers actually run is byte-identical
to that validated object path, and that the curve is NOT silently dropped by the
compiled cy leaf.

If any of these fail, the RoD v2 gen leaf is NOT the frozen v2.9 substrate — do not
launch (it would contaminate every iter with a different leaf than the throne test).
"""
from __future__ import annotations

import dataclasses as dc
import hashlib
import json
import os
import random

import numpy as np
import pytest

from carcassonne_ai import flat_leaf
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.virtual_score_v2 import (
    DEFAULT_CONFIG,
    LeafConfig,
    _config_from_env,
    _v29_active,
    _v29_curve_only,
    virtual_score_v2,
)

V28 = dc.replace(DEFAULT_CONFIG, meeple_k=2.0)
MILD_CURVE = (-8.0, -4.0, -1.0, 0.0, 2.0, 3.0, 4.0, 5.0)
# The frozen v2.9 classical substrate (governance/LEAF_SUBSTRATES.yaml: v2_9_bmild_cap8).
BMILD_CAP8 = dc.replace(V28, v29_meeple_curve=MILD_CURVE, bonus_cap=8.0, opp_bonus_cap=8.0)
FROZEN_CONFIG_HASH = "7fc930b82801cb43"


def _midgame_states(n_seeds=24, plies=70, every=6, seed_base=7):
    random.seed(seed_base)
    out = []
    for s in range(n_seeds):
        g = Game(enable_legal_moves_cache=True)
        b = g.get_init_board()
        rng = random.Random(1000 + s)
        for ply in range(plies):
            if g.get_game_ended(b, 0) != 0.0:
                break
            legal = np.flatnonzero(g.get_valid_moves(b))
            b, _ = g.get_next_state(b, int(rng.choice(legal.tolist())))
            if ply % every == 0:
                out.append(b.state)
    return out


# Default-off knobs excluded from the frozen-cfg recipe so 7fc930b8 / 158f17ff stay
# stable across additive default-off fields (bag_close; C7 Term R/F). Mirrors
# scripts/measurement_infra/snapshot.py::_FROZEN_HASH_DEFAULT_OFF.
_FROZEN_HASH_DEFAULT_OFF = {"bag_close": False, "v29_meeple_return_k": 0.0, "v29_farm_flip_k": 0.0, "soft_cap_slope": 0.0, "opp_soft_cap_slope": 0.0, "farm_base_off": False, "farm_growth_off": False, "v29_phase_beta": 0.0, "v29_phase_norm": 1.0, "denial_dose": 0.0, "denial_size_min": 8.0, "denial_open_max": 2, "opencity_dose": 0.0, "opencity_size_min": 4.0, "opencity_edge_min": 2, "opencity_symmetric": True, "opencity_cap": 0.0, "jrules_dose": 0.0, "jrules_mask": 31, "tiletie_dose": 0.0, "tiletie_w_city": 1.0, "tiletie_w_road": 1.0, "tiletie_w_perim": 0.0, "tiletie_w_lib": 0.0, "tiletie_norm": 8.0, "invasion_beta": 0.0, "invasion_alpha": 0.0, "invasion_alpha_cap": 0.0, "invasion_stub_max_tiles": 2, "invasion_gamma": 0.0, "invasion_delta_farm": 0.0}


def _cfg_hash(cfg):
    d = {k: (list(v) if isinstance(v, tuple) else v) for k, v in dc.asdict(cfg).items()
         if not (k in _FROZEN_HASH_DEFAULT_OFF and v == _FROZEN_HASH_DEFAULT_OFF[k])}
    return hashlib.sha256(
        json.dumps(d, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]


def test_curve_only_gate():
    """Bmild_cap8 is curve-only → eligible for the fast flat path; v2.8 is not v29."""
    assert _v29_active(BMILD_CAP8) is True
    assert _v29_curve_only(BMILD_CAP8) is True
    assert _v29_active(V28) is False
    # adding any other v2.9 term must DISqualify the flat path
    assert _v29_curve_only(dc.replace(BMILD_CAP8, v29_util_tanh_t=8.0)) is False
    assert _v29_curve_only(dc.replace(BMILD_CAP8, v29_punish_k=1.0)) is False


def test_flat_curve_bit_exact_to_object_path():
    """The CURVE LOGIC on the production flat path is byte-identical to the validated
    object path (leaf_v29.apply_v29) under the SAME summation mode. We force canonical
    fsum on the object path (the flat path is always fsum) to isolate the curve logic
    from the pre-existing ±1 naive-vs-canonical reorder flip (DECISIONS 2026-06-09).
    Also catches the cy-silent-drop bug: if cy dropped the curve, flat would equal the
    no-curve score and DIFFER from the object path here."""
    import carcassonne_ai.virtual_score_v2 as vs

    states = _midgame_states()
    assert states
    saved_flat = flat_leaf.USE_FLAT_LEAF
    saved_canon = vs.CANONICAL_BONUS_SUM
    try:
        vs.CANONICAL_BONUS_SUM = True
        n_curve_differs = 0
        for st in states:
            for p in (0, 1):
                flat_leaf.USE_FLAT_LEAF = True
                flat_val = virtual_score_v2(st, p, BMILD_CAP8)
                flat_leaf.USE_FLAT_LEAF = False
                obj_val = virtual_score_v2(st, p, BMILD_CAP8)
                assert flat_val == obj_val, (
                    f"flat {flat_val} != object {obj_val} for Bmild_cap8 (canonical) — "
                    "the production flat curve leaf is NOT the validated v2.9 substrate"
                )
                # and the curve must actually bite vs the no-curve cap8 leaf
                no_curve = dc.replace(BMILD_CAP8, v29_meeple_curve=None)
                if virtual_score_v2(st, p, no_curve) != obj_val:
                    n_curve_differs += 1
        assert n_curve_differs > 0, "curve never changed the score — it is inert/dropped"
    finally:
        flat_leaf.USE_FLAT_LEAF = saved_flat
        vs.CANONICAL_BONUS_SUM = saved_canon


def test_flat_curve_matches_object_within_reorder_flip():
    """Production reality: the gen leaf is flat-canonical-curve; the throne test
    measured object-naive-curve. They agree except on the documented rare ±1
    reorder-flip positions (must be a tiny fraction, never a systematic gap)."""
    import carcassonne_ai.virtual_score_v2 as vs

    states = _midgame_states()
    saved_flat = flat_leaf.USE_FLAT_LEAF
    saved_canon = vs.CANONICAL_BONUS_SUM
    try:
        n, n_diff, max_abs = 0, 0, 0
        for st in states:
            for p in (0, 1):
                vs.CANONICAL_BONUS_SUM = True
                flat_leaf.USE_FLAT_LEAF = True
                gen_leaf = virtual_score_v2(st, p, BMILD_CAP8)        # production gen leaf
                vs.CANONICAL_BONUS_SUM = False
                flat_leaf.USE_FLAT_LEAF = False
                throne_leaf = virtual_score_v2(st, p, BMILD_CAP8)     # throne-test leaf
                n += 1
                d = abs(gen_leaf - throne_leaf)
                if d:
                    n_diff += 1
                    max_abs = max(max_abs, d)
        assert max_abs <= 1, f"systematic gap (max |Δ|={max_abs}), not a reorder flip"
        assert n_diff / n < 0.05, f"too many flips ({n_diff}/{n}) — not the rare ±1 case"
    finally:
        flat_leaf.USE_FLAT_LEAF = saved_flat
        vs.CANONICAL_BONUS_SUM = saved_canon


def test_env_builds_frozen_substrate():
    """Setting the production env vars (curve + cap8, 3-open default, flat meeple_k
    inert) yields a LeafConfig whose leaf-shape hashes to the frozen v2.9 substrate."""
    keys = [
        "CARCASSONNE_V29_MEEPLE_CURVE", "CARCASSONNE_V25_CAP", "CARCASSONNE_V25_OPP_CAP",
        "CARCASSONNE_V25_MEEPLE_K", "CARCASSONNE_V25_DROP_THREE_OPEN",
        "CARCASSONNE_V25_RESIDUAL_SCALE", "CARCASSONNE_V25_VALUE_BLEND",
    ]
    saved = {k: os.environ.get(k) for k in keys}
    try:
        os.environ["CARCASSONNE_V29_MEEPLE_CURVE"] = "-8,-4,-1,0,2,3,4,5"
        os.environ["CARCASSONNE_V25_CAP"] = "8"
        os.environ["CARCASSONNE_V25_OPP_CAP"] = "8"
        os.environ["CARCASSONNE_V25_MEEPLE_K"] = "2.0"
        os.environ.pop("CARCASSONNE_V25_DROP_THREE_OPEN", None)  # default → 3-open
        os.environ.pop("CARCASSONNE_V25_RESIDUAL_SCALE", None)
        os.environ.pop("CARCASSONNE_V25_VALUE_BLEND", None)
        cfg = _config_from_env()
        assert cfg.v29_meeple_curve == MILD_CURVE
        assert cfg.bonus_cap == 8.0 and cfg.opp_bonus_cap == 8.0
        assert cfg.closure_p == {1: 0.5, 2: 0.2, 3: 0.05}  # 3-open
        assert cfg.meeple_k == 2.0  # present but inert (curve replaces it)
        # leaf shape (residual_scale=0) must equal the frozen substrate hash
        leaf_shape = dc.replace(cfg, residual_scale=0.0, value_blend=0.0)
        assert _cfg_hash(leaf_shape) == FROZEN_CONFIG_HASH
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
