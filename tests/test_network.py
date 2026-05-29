"""Tests for the warm-start network architecture."""
from __future__ import annotations

import numpy as np
import pytest
import torch

from carcassonne_ai.action_space import action_size
from carcassonne_ai.board_repr import N_CHANNELS
from carcassonne_ai.features import N_SCALAR_FEATURES
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.network import CarcassonneNet


@pytest.fixture
def net() -> CarcassonneNet:
    torch.manual_seed(0)
    return CarcassonneNet()


def test_forward_shapes(net: CarcassonneNet) -> None:
    B = 4
    W = 25
    board = torch.randn(B, N_CHANNELS, W, W)
    scalars = torch.randn(B, N_SCALAR_FEATURES)
    policy, value = net(board, scalars)
    assert policy.shape == (B, action_size(W))
    assert value.shape == (B,)


def test_value_in_tanh_range(net: CarcassonneNet) -> None:
    B = 16
    board = torch.randn(B, N_CHANNELS, 25, 25)
    scalars = torch.randn(B, N_SCALAR_FEATURES)
    _, value = net(board, scalars)
    assert (value > -1).all() and (value < 1).all()


def test_param_count_sanity(net: CarcassonneNet) -> None:
    """6 by 96 should land around 7-8M (the 2511-output dense layer alone is
    ~6M params from policy_flat_dim 2510 -> 2511, regardless of trunk)."""
    n = net.param_count()
    assert 6_000_000 < n < 9_000_000, f"unexpected param count {n}"


def test_masked_softmax_zeros_invalid(net: CarcassonneNet) -> None:
    """Masked softmax must put 0 on invalid actions and sum to 1 on valid."""
    B = 2
    A = action_size(25)
    logits = torch.randn(B, A)
    valid = torch.zeros(B, A, dtype=torch.bool)
    valid[0, [0, 5, 100]] = True
    valid[1, [42, 1234, 2510]] = True
    probs = net.policy_softmax_with_mask(logits, valid)
    assert probs[~valid].abs().max().item() == 0
    sums = probs.sum(dim=-1)
    assert torch.allclose(sums, torch.ones_like(sums), atol=1e-6)


def test_autograd_flows(net: CarcassonneNet) -> None:
    """A backward pass through the TRAINING forward (policy+value+ownership)
    should populate gradients on every parameter, including the aux head.

    (`forward` is the inference path and deliberately skips the ownership head,
    so it would leave ownership_head.* without gradients — the trainers use
    forward_train.)"""
    B = 2
    board = torch.randn(B, N_CHANNELS, 25, 25, requires_grad=False)
    scalars = torch.randn(B, N_SCALAR_FEATURES, requires_grad=False)
    policy, value, ownership = net.forward_train(board, scalars)
    loss = policy.sum() + value.sum() + ownership.sum()
    loss.backward()
    for name, p in net.named_parameters():
        assert p.grad is not None, f"{name} has no gradient"


def test_consumes_real_observation_from_game(net: CarcassonneNet) -> None:
    """End-to-end: take a real observation from the Game wrapper, feed it
    through the network, get sane outputs."""
    g = Game()
    board = g.get_init_board()
    obs, scalars = g.get_canonical_form(board, 0)
    obs_t = torch.from_numpy(obs).unsqueeze(0).float()
    scalars_t = torch.from_numpy(scalars).unsqueeze(0).float()
    net.train(False)  # inference mode (avoids triggering eval()-name hooks)
    with torch.no_grad():
        policy, value = net(obs_t, scalars_t)
    assert policy.shape == (1, g.get_action_size())
    assert value.shape == (1,)


def test_alternate_capacity_works() -> None:
    """A 4 by 64 net (the smaller fallback) builds and runs."""
    torch.manual_seed(0)
    smaller = CarcassonneNet(n_filters=64, n_blocks=4)
    n = smaller.param_count()
    # output dense dominates: ~6M; trunk adds <1M for this size
    assert 6_000_000 < n < 8_000_000, f"4 by 64 param count out of expected range: {n}"
    board = torch.randn(2, N_CHANNELS, 25, 25)
    scalars = torch.randn(2, N_SCALAR_FEATURES)
    policy, value = smaller(board, scalars)
    assert policy.shape == (2, action_size(25))
    assert value.shape == (2,)
