"""Tests for the v2.9 experimental leaf candidates (measurement/v29_leaf_audit/).

Three contracts:
  (A) PARITY — with every v2.9 field neutral, virtual_score_v2 is BIT-IDENTICAL to
      v2.8/v2.7 on BOTH paths, and DEFAULT_CONFIG carries no v2.9 effect.
  (B) EFFECT — each active toggle changes the evaluation and respects its invariant
      (util transform shrinks magnitude; meeple curve replaces the flat term).
  (C) DECOMPOSE — leaf_v29.decompose_v29 components sum to total_int, and total_int
      equals virtual_score_v2 on the object path for every cfg (incl. v2.8).

Reuses the corpus helpers from test_v28_variants (random self-play snapshots).
"""
from __future__ import annotations

import dataclasses as dc
import math
import random

import numpy as np
import pytest

from carcassonne_ai import flat_leaf, leaf_v29
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import HeuristicMCTS
from carcassonne_ai.virtual_score_v2 import (
    DEFAULT_CONFIG,
    _v29_active,
    virtual_score_v2,
)

# Production v2.8 baseline = DEFAULT_CONFIG + flat meeple_k=2.0 (the eval baseline).
V28 = dc.replace(DEFAULT_CONFIG, meeple_k=2.0)
MILD_CURVE = (-8.0, -4.0, -1.0, 0.0, 2.0, 3.0, 4.0, 5.0)  # value by free-meeple count 0..7


@pytest.fixture(autouse=True)
def _deterministic_global_rng():
    random.seed(20260625)
    yield


def _walk_random(g: Game, b, n_moves: int, seed: int):
    rng = random.Random(seed)
    for _ in range(n_moves):
        if g.get_game_ended(b, 0) != 0.0:
            break
        legal = np.flatnonzero(g.get_valid_moves(b))
        b, _ = g.get_next_state(b, int(rng.choice(legal.tolist())))
    return b


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


# ---------------------------------------------------------------------------
# (A) PARITY
# ---------------------------------------------------------------------------
def test_default_config_has_no_v29_effect():
    assert DEFAULT_CONFIG.v29_util_tanh_t == 0.0
    assert DEFAULT_CONFIG.v29_meeple_curve is None
    assert DEFAULT_CONFIG.v29_punish_k == 0.0
    assert DEFAULT_CONFIG.v29_farm_access_k == 0.0
    assert _v29_active(DEFAULT_CONFIG) is False
    assert _v29_active(V28) is False


@pytest.mark.parametrize("use_flat", [False, True])
def test_v29_off_is_bit_identical(use_flat):
    """v2.9 fields explicitly neutral == DEFAULT_CONFIG, byte-for-byte, both paths."""
    off = dc.replace(DEFAULT_CONFIG, v29_util_tanh_t=0.0, v29_meeple_curve=None,
                     v29_punish_k=0.0, v29_farm_access_k=0.0)
    saved = flat_leaf.USE_FLAT_LEAF
    flat_leaf.USE_FLAT_LEAF = use_flat
    try:
        states = _midgame_states()
        assert states
        for st in states:
            for p in (0, 1):
                assert virtual_score_v2(st, p, off) == virtual_score_v2(st, p, DEFAULT_CONFIG)
                assert virtual_score_v2(st, p, None) == virtual_score_v2(st, p, DEFAULT_CONFIG)
    finally:
        flat_leaf.USE_FLAT_LEAF = saved


# ---------------------------------------------------------------------------
# (B) EFFECT
# ---------------------------------------------------------------------------
def test_util_transform_math():
    """T*tanh(x/T): identity-ish near 0, sign-preserving, |out| < T and |out| <= |x|."""
    for t in (8.0, 16.0, 32.0):
        assert leaf_v29._util_transform(0.0, t) == 0.0
        for x in (-40, -8, -2, -1, 1, 2, 8, 40):
            y = leaf_v29._util_transform(float(x), t)
            assert math.copysign(1, y) == math.copysign(1, x)  # sign preserved
            assert abs(y) < t + 1e-9                            # bounded by T
            assert abs(y) <= abs(x) + 1e-9                      # never amplifies
        # small-x near-identity
        assert abs(leaf_v29._util_transform(1.0, t) - 1.0) < 0.05


def test_util_transform_shrinks_large_leads():
    """Candidate A (T=8) must not increase |score|, and must strictly shrink at least
    one large-lead position (anti-padding)."""
    a8 = dc.replace(V28, v29_util_tanh_t=8.0)
    saw_shrink = False
    for st in _midgame_states():
        for p in (0, 1):
            base = abs(virtual_score_v2(st, p, V28))
            shaped = abs(virtual_score_v2(st, p, a8))
            assert shaped <= base, f"util transform amplified: {shaped} > {base}"
            if base >= 12 and shaped < base:
                saw_shrink = True
    assert saw_shrink, "T=8 win-shape never compressed a large lead"


def test_meeple_curve_replaces_flat_term():
    """With a curve set, the meeple contribution is the curve differential (NOT the
    flat meeple_k term); decompose exposes both."""
    curve_cfg = dc.replace(V28, v29_meeple_curve=MILD_CURVE)
    saw_imbalance = False
    for st in _midgame_states():
        for p in (0, 1):
            m_self, m_opp = st.meeples[p], st.meeples[1 - p]
            d = leaf_v29.decompose_v29(st, p, curve_cfg)
            flat_ref = 2.0 * (m_self - m_opp)
            curve_term = leaf_v29._curve_lookup(MILD_CURVE, m_self) - leaf_v29._curve_lookup(MILD_CURVE, m_opp)
            assert d["meeple_flat"] == pytest.approx(flat_ref)
            assert d["meeple_curve_delta"] == pytest.approx(curve_term - flat_ref)
            if m_self != m_opp:
                saw_imbalance = True
    assert saw_imbalance


def test_heuristic_mcts_v29_can_change_action():
    """A v2.9 cfg (aggressive win-shape) must change >=1 HeuristicMCTS action vs v2.8."""
    def act(seed, cfg, sims=24):
        random.seed(50_000 + seed)
        g = Game(enable_legal_moves_cache=True)
        b = _walk_random(g, g.get_init_board(), 24, seed)
        if g.get_game_ended(b, 0) != 0.0:
            return None
        m = HeuristicMCTS(game=g, simulations=sims, seed=seed, heur_leaf="v2_7", leaf_cfg=cfg)
        return int(m.best_action(b))

    a6 = dc.replace(V28, v29_util_tanh_t=6.0)
    diffs = 0
    for seed in range(14):
        x, y = act(seed, V28), act(seed, a6)
        if x is not None and y is not None and x != y:
            diffs += 1
    assert diffs > 0, "v2.9 win-shape never changed a HeuristicMCTS action"


# ---------------------------------------------------------------------------
# (C) DECOMPOSE
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cfg_name", ["v28", "A12", "Bcurve", "A12+Bcurve"])
def test_decompose_sums_to_leaf(cfg_name):
    """decompose_v29 total_int == virtual_score_v2 (object path), and the additive
    components + utility_transform_delta == pretransform/total. Force the object path
    so flat-vs-object ±1 rounding can't make this flaky; v2.9-active cfgs force it
    anyway."""
    cfg = {
        "v28": V28,
        "A12": dc.replace(V28, v29_util_tanh_t=12.0),
        "Bcurve": dc.replace(V28, v29_meeple_curve=MILD_CURVE),
        "A12+Bcurve": dc.replace(V28, v29_util_tanh_t=12.0, v29_meeple_curve=MILD_CURVE),
    }[cfg_name]
    saved = flat_leaf.USE_FLAT_LEAF
    flat_leaf.USE_FLAT_LEAF = False
    try:
        for st in _midgame_states():
            for p in (0, 1):
                d = leaf_v29.decompose_v29(st, p, cfg)
                # additive components reconstruct pretransform_total
                recon = (d["base"] + d["closure_self"] - d["closure_opp"]
                         + d["meeple_flat"] + d["meeple_curve_delta"] + d["v28_meeple"]
                         + d["deck_completion_delta"] + d["tactical_punish_delta"]
                         + d["threat_block_delta"] + d["farm_access_delta"]
                         + d["phase_scaling_delta"])
                assert recon == pytest.approx(d["pretransform_total"])
                assert (d["pretransform_total"] + d["utility_transform_delta"]
                        == pytest.approx(d["total"]))
                # the decomposition's int total == the production leaf
                assert d["total_int"] == virtual_score_v2(st, p, cfg)
    finally:
        flat_leaf.USE_FLAT_LEAF = saved
