"""Flywheel step 2: global-pooling value head (CarcassonneNet value_global_pool)."""
from __future__ import annotations

import pytest
import torch

from carcassonne_ai.board_repr import N_CHANNELS
from carcassonne_ai.network import CarcassonneNet


def _net(global_pool):
    # tiny net for speed
    return CarcassonneNet(n_filters=16, n_blocks=1, value_global_pool=global_pool)


def _inputs(net, b=2):
    board = torch.randn(b, N_CHANNELS, net.window_size, net.window_size)
    scalars = torch.randn(b, 10)
    return board, scalars


def test_global_pool_forward_shapes():
    net = _net(True)
    board, scalars = _inputs(net)
    pol, val = net(board, scalars)
    assert pol.shape == (2, net.action_size)
    assert val.shape == (2,)
    assert torch.all(val.abs() <= 1.0)  # tanh-bounded
    pol2, val2, own = net.forward_train(board, scalars)
    assert val2.shape == (2,) and own.shape[0] == 2


def test_global_pool_adds_params():
    plain = _net(False)
    pooled = _net(True)
    # value_fc1 input grows by 2*n_filters (32) → more params
    assert pooled.param_count() > plain.param_count()
    extra = pooled.param_count() - plain.param_count()
    assert extra == 2 * 16 * 64  # 2*n_filters * value_hidden weights


def test_value_responds_to_distant_board_change():
    """Global pooling means the value sees board-WIDE content: changing a far
    corner shifts the pooled mean/max → the value should move. (A tiny-receptive-
    field non-pool head can miss this.)"""
    torch.manual_seed(0)
    net = _net(True).eval()
    board, scalars = _inputs(net, b=1)
    with torch.no_grad():
        v0 = net(board, scalars)[1].item()
        b2 = board.clone()
        b2[:, :, 0, 0] += 5.0  # spike a far corner cell across all channels
        v1 = net(b2, scalars)[1].item()
    assert v0 != pytest.approx(v1)  # global pool propagated the change


def test_checkpoint_roundtrip_and_incompat_caught(tmp_path):
    pooled = _net(True)
    sd = pooled.state_dict()
    # reconstruct WITH the flag → loads clean
    rebuilt = _net(True)
    rebuilt.load_state_dict(sd)
    # reconstruct WITHOUT the flag → value_fc1 shape mismatch must fail loudly
    plain = _net(False)
    with pytest.raises(RuntimeError):
        plain.load_state_dict(sd)
