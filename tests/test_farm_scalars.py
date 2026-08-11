"""Tests for the Path B Step E farm-control input scalars (2026-05-29).

Contracts:
  1. encode_scalars(include_farm=False) is byte-identical to the legacy 10-vector;
     include_farm=True appends exactly 2 values after that prefix.
  2. farm_control_scalars agrees with an INDEPENDENT recompute (find_farm +
     find_meeples per field, no index) — validates the fast index-based tally.
  3. contested is symmetric across players; balance is antisymmetric.
  4. Game(include_farm_scalars=...) flips the scalar size 10<->12 and feeds the
     right width through get_canonical_form.
  5. CarcassonneNet accepts a 12-scalar input (forward + forward_train).
"""
from __future__ import annotations

import random

import numpy as np
import pytest
import torch

from carcassonne_ai.features import (
    FARM_SCALAR_NORM,
    N_FARM_SCALARS,
    N_SCALAR_FEATURES,
    encode_scalars,
    farm_control_scalars,
)
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.network import CarcassonneNet
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.utils.farm_util import FarmUtil


def _play(seed: int, plies: int = 130):
    # Base-only games terminate at ~141-144 plies; cap below that so we return a
    # deep but NON-terminal board (callers run get_valid_moves on it, which fails
    # on a terminal state). River's old 83-tile deck ran to ~166 plies.
    game = Game()
    random.seed(seed)
    board = game.get_init_board()
    n = 0
    while game.get_game_ended(board, 0) == 0.0 and n < plies:
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break
        board, _ = game.get_next_state(board, int(random.choice(legal.tolist())))
        n += 1
    return board


def _independent_farm_control(state, player):
    """Recompute (contested, balance) the slow, obvious way: for each farmer,
    find its field via find_farm (no index/cache), dedup fields by their node-key
    set, count meeples with find_meeples. Cross-checks farm_control_scalars."""
    opp = 1 - player
    seen = set()
    contested = 0
    balance = 0
    for pl in range(state.players):
        for mp in state.placed_meeples[pl]:
            if mp.meeple_type not in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                continue
            farm = FarmUtil.find_farm_by_coordinate(state, mp.coordinate_with_side)
            if farm is None:
                continue
            key = frozenset(
                FarmUtil._farm_node_key(f) for f in farm.farmer_connections_with_coordinate
            )
            if key in seen:
                continue
            seen.add(key)
            meeples = FarmUtil.find_meeples(state, farm)
            mine, theirs = len(meeples[player]), len(meeples[opp])
            if mine > 0 and theirs > 0:
                contested += 1
            if mine > theirs:
                balance += 1
            elif theirs > mine:
                balance -= 1
    return contested, balance


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 5, 7, 11, 13])
def test_encode_scalars_length_and_prefix(seed):
    board = _play(seed)
    base = encode_scalars(board.state, 0, board.total_tiles, include_farm=False)
    full = encode_scalars(board.state, 0, board.total_tiles, include_farm=True)
    assert len(base) == N_SCALAR_FEATURES == 10
    assert len(full) == N_SCALAR_FEATURES + N_FARM_SCALARS == 12
    assert np.array_equal(base, full[:N_SCALAR_FEATURES])  # legacy prefix unchanged


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 5, 7, 11, 13, 17, 21])
def test_farm_control_matches_independent(seed):
    state = _play(seed).state
    for p in range(state.players):
        fast = farm_control_scalars(state, p)
        slow = _independent_farm_control(state, p)
        assert fast == slow, f"seed {seed} player {p}: fast {fast} != independent {slow}"


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 5, 7, 11, 13])
def test_contested_symmetric_balance_antisymmetric(seed):
    state = _play(seed).state
    c0, b0 = farm_control_scalars(state, 0)
    c1, b1 = farm_control_scalars(state, 1)
    assert c0 == c1          # "both players farm this field" is player-agnostic
    assert b0 == -b1         # "I lead minus opp leads" flips sign


def test_game_flag_controls_scalar_size():
    g10, g12 = Game(), Game(include_farm_scalars=True)
    assert g10.get_scalar_feature_size() == 10
    assert g12.get_scalar_feature_size() == 12
    board = _play(2)
    _, s10 = g10.get_canonical_form(board, 0)
    _, s12 = g12.get_canonical_form(board, 0)
    assert len(s10) == 10 and len(s12) == 12
    assert np.array_equal(s10, s12[:10])


def test_normalization_in_range():
    """Farm scalars stay roughly in [-1, 1] across many states (saturation rare)."""
    sat = 0
    total = 0
    for seed in range(20):
        state = _play(seed).state
        for p in range(state.players):
            c, b = farm_control_scalars(state, p)
            total += 2
            if abs(c / FARM_SCALAR_NORM) > 1.0:
                sat += 1
            if abs(b / FARM_SCALAR_NORM) > 1.0:
                sat += 1
    assert sat / max(total, 1) < 0.10, f"farm scalars saturate too often: {sat}/{total}"


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 7])
def test_v25_wrapper_value_matches_standalone_leaf(seed):
    """make_v25_value_wrapper shares one farm/city cache across the policy-encode
    and the leaf value. Its value must equal the standalone leaf value (sharing
    must not corrupt the result), with farm scalars ON (12-scalar Game)."""
    from carcassonne_ai.evaluators import make_v25_value_wrapper
    from carcassonne_ai.virtual_score_v2 import virtual_score_v2

    game = Game(include_farm_scalars=True)
    board = _play(seed)
    st = board.state

    def base_eval(b):
        # exercises get_canonical_form (the encode, incl. farm_control_scalars)
        _, _ = game.get_canonical_form(b, b.state.current_player)
        mask = game.get_valid_moves(b)
        legal = np.flatnonzero(mask)
        priors = np.zeros(mask.shape, dtype=np.float32)
        if legal.size:
            priors[legal] = 1.0 / legal.size
        return priors, 0.0

    wrapped = make_v25_value_wrapper(base_eval)
    _, wrapped_value = wrapped(board)
    import math
    standalone = math.tanh(virtual_score_v2(st, st.current_player) / 15.0)
    assert wrapped_value == pytest.approx(standalone, abs=1e-6)
    # the shared cache must be detached after the call (no leak on the tree state)
    assert not hasattr(st, "_farm_cache")
    assert not hasattr(st, "_city_cache")


def test_network_accepts_12_scalars():
    net = CarcassonneNet(n_filters=32, n_blocks=2, n_scalar_features=12)
    game = Game(include_farm_scalars=True)
    board = game.get_init_board()
    obs, scalars = game.get_canonical_form(board, 0)
    obs_t = torch.from_numpy(obs).unsqueeze(0).float()
    sc_t = torch.from_numpy(scalars).unsqueeze(0).float()
    logits, value = net(obs_t, sc_t)
    assert logits.shape[0] == 1 and value.shape == (1,)
    logits2, value2, ownership = net.forward_train(obs_t, sc_t)
    assert logits2.shape == logits.shape
