"""Phase 3 tests for the v2.8 experimental leaf variants (measurement/heuristic_v28/).

Two contracts:
  (A) PARITY — with every v2.8 knob OFF, virtual_score_v2 is BIT-IDENTICAL to v2.7,
      on BOTH the object path and the flat fast path, and DEFAULT_CONFIG (production)
      carries no v2.8 effect. This is the "v2.7 stays frozen" guarantee.
  (B) EFFECT — each v2.8 toggle CAN change the evaluation (and, for HeuristicMCTS,
      the chosen action) on at least one real position, and respects its invariant
      (farm-majority only reduces the growth bonus; meeple-recovery scales down).

Variants under test:
  v28_farm       -> LeafConfig(v28_farm_majority=True)
  v28_meeple     -> LeafConfig(v28_meeple_k=k, v28_meeple_recovery_t0=t0)
  v28_completion -> LeafConfig(closure_continuous_slack=s)   (reused existing knob)
  v28_denial     -> LeafConfig(opp_bonus_cap > bonus_cap)    (reused existing knob)
"""
from __future__ import annotations

import dataclasses as dc
import random

import numpy as np
import pytest

from carcassonne_ai import flat_leaf
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import HeuristicMCTS
from carcassonne_ai.virtual_score_v2 import (
    DEFAULT_CONFIG,
    LeafConfig,
    _closure_anticipation_bonus,
    virtual_score_v2,
)


@pytest.fixture(autouse=True)
def _deterministic_global_rng():
    random.seed(20260622)
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
    """Yield (state,) snapshots from random self-play across several seeds/plies.

    Seeds the GLOBAL rng first: the engine's deck shuffle in get_init_board() draws
    from the global `random` module, so without this the corpus depends on whatever
    consumed the rng earlier (test order) — which flips the decks and was masking the
    v28_farm gate. Pinning it makes the corpus deterministic and order-independent."""
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
# (A) PARITY — v2.8 OFF is bit-identical v2.7
# ---------------------------------------------------------------------------

def test_default_config_has_no_v28_effect():
    """Production DEFAULT_CONFIG must carry every v2.8 field at its OFF default."""
    assert DEFAULT_CONFIG.v28_farm_majority is False
    assert DEFAULT_CONFIG.v28_meeple_k == 0.0
    assert DEFAULT_CONFIG.v28_meeple_recovery_t0 == 0


@pytest.mark.parametrize("use_flat", [False, True])
def test_v28_off_is_bit_identical_to_v27(use_flat):
    """A LeafConfig with v2.8 fields explicitly OFF == DEFAULT_CONFIG, byte-for-byte,
    on both the object path and the flat fast path."""
    off = dc.replace(DEFAULT_CONFIG, v28_farm_majority=False, v28_meeple_k=0.0,
                     v28_meeple_recovery_t0=0)
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
# (B) EFFECT — each toggle changes evaluation + respects its invariant
# ---------------------------------------------------------------------------

def test_v28_farm_only_reduces_growth_bonus():
    """The majority gate can only SUPPRESS growth credit -> the per-player closure
    bonus under v28_farm is always <= the v2.7 bonus."""
    farm = dc.replace(DEFAULT_CONFIG, v28_farm_majority=True)
    for st in _midgame_states():
        for p in (0, 1):
            b_v28 = _closure_anticipation_bonus(st, p, farm)
            b_v27 = _closure_anticipation_bonus(st, p, DEFAULT_CONFIG)
            assert b_v28 <= b_v27 + 1e-9


def test_v28_farm_changes_at_least_one_position():
    """v28_farm must change the (uncapped) closure bonus on >=1 contested-field
    position — proving the majority gate fires. NOTE: at the capped virtual_score_v2
    int level the change is often masked (bonus_cap=12 saturates mid-late game), an
    interaction carried into Phase 4/5 — so the contract is tested on the bonus."""
    farm = dc.replace(DEFAULT_CONFIG, v28_farm_majority=True)
    states = _midgame_states(n_seeds=40, plies=80, every=4)
    bonus_changed = sum(
        1 for st in states for p in (0, 1)
        if _closure_anticipation_bonus(st, p, farm) != _closure_anticipation_bonus(st, p, DEFAULT_CONFIG)
    )
    assert bonus_changed > 0, "v28_farm never altered any closure bonus — majority gate inert"


def test_v28_meeple_off_is_v27():
    meeple_off = dc.replace(DEFAULT_CONFIG, v28_meeple_k=0.0)
    for st in _midgame_states():
        for p in (0, 1):
            assert virtual_score_v2(st, p, meeple_off) == virtual_score_v2(st, p, DEFAULT_CONFIG)


def test_v28_meeple_flat_term_changes_eval():
    """t0=0 (flat) meeple term shifts the score by ~k*(m_self - m_opp) before rounding."""
    k = 3.0
    cfg = dc.replace(DEFAULT_CONFIG, v28_meeple_k=k, v28_meeple_recovery_t0=0)
    changed = 0
    for st in _midgame_states():
        for p in (0, 1):
            imbalance = st.meeples[p] - st.meeples[1 - p]
            if imbalance != 0:
                if virtual_score_v2(st, p, cfg) != virtual_score_v2(st, p, DEFAULT_CONFIG):
                    changed += 1
    assert changed > 0, "v28_meeple flat term never changed an imbalanced position"


def test_v28_meeple_recovery_scales_down_late():
    """With a large t0 (recovery scaling active, deck < t0), the meeple term is
    smaller in magnitude than the flat (t0=0) term on the same position."""
    k = 4.0
    flat_cfg = dc.replace(DEFAULT_CONFIG, v28_meeple_k=k, v28_meeple_recovery_t0=0)
    scaled = dc.replace(DEFAULT_CONFIG, v28_meeple_k=k, v28_meeple_recovery_t0=10_000)
    seen_scaledown = False
    for st in _midgame_states():
        for p in (0, 1):
            imbalance = st.meeples[p] - st.meeples[1 - p]
            if imbalance == 0:
                continue
            base = virtual_score_v2(st, p, DEFAULT_CONFIG)
            flat_term = virtual_score_v2(st, p, flat_cfg) - base
            scaled_term = virtual_score_v2(st, p, scaled) - base
            # rf = min(1, deck/10000) < 1 mid-game -> |scaled_term| <= |flat_term|
            assert abs(scaled_term) <= abs(flat_term) + 1e-9
            if abs(scaled_term) < abs(flat_term) - 1e-9:
                seen_scaledown = True
    assert seen_scaledown, "recovery scaling never reduced the meeple term"


def test_v28_denial_asymmetric_cap_changes_eval():
    """Raising opp_bonus_cap above bonus_cap (v28_denial) changes >=1 position."""
    denial = dc.replace(DEFAULT_CONFIG, opp_bonus_cap=DEFAULT_CONFIG.bonus_cap + 12.0)
    changed = sum(
        1 for st in _midgame_states(n_seeds=40, plies=80, every=4) for p in (0, 1)
        if virtual_score_v2(st, p, denial) != virtual_score_v2(st, p, DEFAULT_CONFIG)
    )
    assert changed > 0, "v28_denial (asymmetric opp cap) never changed a position"


def test_v28_completion_slack_only_reduces_bonus():
    """v28_completion (continuous deck-aware slack) can only reduce the closure
    bonus (a P(closure) discount), never increase it."""
    comp = dc.replace(DEFAULT_CONFIG, closure_continuous_slack=3.0)
    saved = flat_leaf.USE_FLAT_LEAF
    flat_leaf.USE_FLAT_LEAF = True  # slack forces engine path regardless
    try:
        for st in _midgame_states():
            for p in (0, 1):
                assert _closure_anticipation_bonus(st, p, comp) <= _closure_anticipation_bonus(
                    st, p, DEFAULT_CONFIG) + 1e-9
    finally:
        flat_leaf.USE_FLAT_LEAF = saved


# ---------------------------------------------------------------------------
# HeuristicMCTS leaf_cfg threading
# ---------------------------------------------------------------------------

def _heur_action(seed, leaf_cfg, sims=24):
    # Seed the GLOBAL rng so get_init_board()'s deck is identical across calls with
    # the same seed (else None vs DEFAULT_CONFIG land on different boards).
    random.seed(50_000 + seed)
    g = Game(enable_legal_moves_cache=True)
    b = _walk_random(g, g.get_init_board(), n_moves=24, seed=seed)
    if g.get_game_ended(b, 0) != 0.0:
        return None, None
    m = HeuristicMCTS(game=g, simulations=sims, seed=seed, heur_leaf="v2_7", leaf_cfg=leaf_cfg)
    return int(m.best_action(b)), b


def test_heuristic_mcts_leaf_cfg_none_matches_default():
    """leaf_cfg=None must reproduce DEFAULT_CONFIG behaviour exactly (same action)."""
    for seed in range(6):
        a_none, _ = _heur_action(seed, None)
        a_def, _ = _heur_action(seed, DEFAULT_CONFIG)
        assert a_none == a_def


def test_heuristic_mcts_v28_leaf_cfg_can_change_action():
    """A v2.8 leaf_cfg (here a strong meeple term) must change the chosen action on
    at least one of several positions — proving the cfg is actually threaded."""
    v28 = dc.replace(DEFAULT_CONFIG, v28_meeple_k=8.0, v28_meeple_recovery_t0=0,
                     v28_farm_majority=True)
    diffs = 0
    for seed in range(12):
        a_v27, _ = _heur_action(seed, DEFAULT_CONFIG)
        a_v28, _ = _heur_action(seed, v28)
        if a_v27 is not None and a_v28 is not None and a_v27 != a_v28:
            diffs += 1
    assert diffs > 0, "v2.8 leaf_cfg never changed a HeuristicMCTS action"
