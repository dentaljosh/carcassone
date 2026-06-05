"""Tests for the Path B policy-entropy collapse guard.

Validates train_iter._mean_policy_entropy (the measurement the Step-8 loop uses
to detect a collapsed policy head) and the collapse condition the gate checks.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from train_iter import _mean_policy_entropy, _value_outcome_corr  # noqa: E402


class _StubNet:
    """Returns fixed logits regardless of input; mimics CarcassonneNet.forward_train."""

    def __init__(self, logits: torch.Tensor):
        self._logits = logits

    def train(self, mode: bool = True):
        return self

    def forward_train(self, board, scalar):
        return self._logits[: board.shape[0]], None, None


def _entropy(logits: torch.Tensor, mask: torch.Tensor) -> float:
    b, a = logits.shape
    board = torch.zeros(b, 1, 1, 1)
    scalar = torch.zeros(b, 10)
    policy = torch.zeros(b, a)
    value = torch.zeros(b)
    own = torch.zeros(b, 1, 1, 1)
    aux = torch.ones(b, dtype=torch.bool)  # all full rows
    loader = [(board, scalar, policy, value, mask, own, aux)]
    return _mean_policy_entropy(_StubNet(logits), loader, torch.device("cpu"))


def test_uniform_policy_entropy_is_log_n():
    a = 4
    ent = _entropy(torch.zeros(2, a), torch.ones(2, a))
    assert abs(ent - math.log(a)) < 1e-4


def test_sharp_policy_entropy_near_zero():
    ent = _entropy(torch.tensor([[50.0, 0.0, 0.0, 0.0]]), torch.ones(1, 4))
    assert ent < 1e-3


def test_entropy_respects_mask():
    # uniform logits, only 2 of 4 actions legal -> entropy = log(2), not log(4).
    ent = _entropy(torch.zeros(1, 4), torch.tensor([[1.0, 1.0, 0.0, 0.0]]))
    assert abs(ent - math.log(2)) < 1e-4


def test_collapse_trips_floor():
    # A near-deterministic policy sits well below 0.5x a uniform baseline ->
    # the gate (trained < 0.5 * baseline) would fire.
    baseline = _entropy(torch.zeros(1, 8), torch.ones(1, 8))  # log(8) ~= 2.08
    collapsed = _entropy(torch.tensor([[50.0] + [0.0] * 7]), torch.ones(1, 8))
    assert collapsed < 0.5 * baseline


def test_healthy_policy_passes_floor():
    # A mildly-peaked but still-spread policy stays above the 0.5x floor.
    baseline = _entropy(torch.zeros(1, 8), torch.ones(1, 8))
    healthy = _entropy(torch.tensor([[1.5, 1.0, 0.8, 0.5, 0.3, 0.2, 0.1, 0.0]]), torch.ones(1, 8))
    assert healthy > 0.5 * baseline


def test_entropy_skips_value_only_rows():
    # Flywheel step 1: a value-only interior row (aux=False, all-False mask)
    # must be SKIPPED, not crash (its masked softmax is degenerate). Entropy
    # then equals that of the single surviving full row (uniform → log a).
    a = 4
    logits = torch.zeros(2, a)
    board = torch.zeros(2, 1, 1, 1)
    scalar = torch.zeros(2, 10)
    policy = torch.zeros(2, a)
    value = torch.zeros(2)
    own = torch.zeros(2, 1, 1, 1)
    mask = torch.tensor([[1.0, 1.0, 1.0, 1.0], [0.0, 0.0, 0.0, 0.0]])
    aux = torch.tensor([True, False])
    loader = [(board, scalar, policy, value, mask, own, aux)]
    ent = _mean_policy_entropy(_StubNet(logits), loader, torch.device("cpu"))
    assert abs(ent - math.log(a)) < 1e-4


class _ValueStub:
    """Returns a fixed value prediction; mimics CarcassonneNet.forward_train's
    (policy, value, ownership) tuple for the value-corr readout."""

    def __init__(self, pred: torch.Tensor):
        self._pred = pred

    def train(self, mode: bool = True):
        return self

    def forward_train(self, board, scalar):
        b = board.shape[0]
        return torch.zeros(b, 4), self._pred[:b], None


def _corr(pred: torch.Tensor, target: torch.Tensor):
    b = pred.shape[0]
    board = torch.zeros(b, 1, 1, 1)
    scalar = torch.zeros(b, 10)
    policy = torch.zeros(b, 4)
    mask = torch.ones(b, 4)
    own = torch.zeros(b, 1, 1, 1)
    aux = torch.ones(b, dtype=torch.bool)
    loader = [(board, scalar, policy, target, mask, own, aux)]
    return _value_outcome_corr(_ValueStub(pred), loader, torch.device("cpu"))


def test_value_corr_perfect_positive():
    t = torch.tensor([0.1, 0.2, 0.3, 0.4, 0.5])
    assert abs(_corr(2.0 * t + 0.05, t) - 1.0) < 1e-4


def test_value_corr_perfect_negative():
    t = torch.tensor([0.1, 0.2, 0.3, 0.4, 0.5])
    assert abs(_corr(-t, t) + 1.0) < 1e-4


def test_value_corr_degenerate_returns_none():
    # constant prediction -> zero variance -> None (not a crash).
    t = torch.tensor([0.1, 0.2, 0.3, 0.4, 0.5])
    assert _corr(torch.full((5,), 0.3), t) is None
