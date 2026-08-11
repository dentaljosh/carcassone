"""Unit tests for the value-only-row loss masking (flywheel step 1).

masked_policy_ownership_loss must compute policy CE + ownership MSE over
full-trajectory rows ONLY (aux_mask=True) and subset OUT value-only interior
rows (aux_mask=False) whose dummy zero-policy / all-False-mask would otherwise
trip policy_cross_entropy's "rows sum to 1 / have a legal action" validators.
"""
from __future__ import annotations

import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from train_warmstart import (  # noqa: E402
    masked_policy_ownership_loss,
    ownership_loss,
    policy_cross_entropy,
)
from carcassonne_ai.board_repr import CH_TILE_PRESENT, N_CHANNELS  # noqa: E402

A = 6
P = 3
W = 4


def _full_row(seed: int):
    """A valid full-trajectory row: 2 legal actions, policy sums to 1 over them."""
    g = torch.Generator().manual_seed(seed)
    logits = torch.randn(1, A, generator=g)
    mask = torch.zeros(1, A, dtype=torch.bool)
    mask[0, :2] = True
    policy = torch.zeros(1, A)
    policy[0, 0], policy[0, 1] = 0.6, 0.4
    own_pred = torch.randn(1, P, W, W, generator=g)
    own_t = torch.zeros(1, P, W, W)
    board = torch.zeros(1, N_CHANNELS, W, W)
    board[0, CH_TILE_PRESENT] = 1.0
    return logits, policy, mask, own_pred, own_t, board


def _value_only_row():
    """A value-only interior row: dummy zero policy + all-False mask + zero
    ownership (would crash policy_cross_entropy if not subset out)."""
    logits = torch.randn(1, A)
    mask = torch.zeros(1, A, dtype=torch.bool)
    policy = torch.zeros(1, A)
    own_pred = torch.randn(1, P, W, W)
    own_t = torch.zeros(1, P, W, W)
    board = torch.zeros(1, N_CHANNELS, W, W)
    board[0, CH_TILE_PRESENT] = 1.0
    return logits, policy, mask, own_pred, own_t, board


def _cat(rows):
    cols = list(zip(*rows))
    return [torch.cat(c, dim=0) for c in cols]


def test_all_full_rows_matches_direct_losses() -> None:
    logits, policy, mask, own_pred, own_t, board = _cat([_full_row(0), _full_row(1)])
    aux = torch.ones(2, dtype=torch.bool)
    pol, own = masked_policy_ownership_loss(
        logits, policy, mask, own_pred, own_t, board, aux
    )
    assert torch.allclose(pol, policy_cross_entropy(logits, policy, mask))
    assert torch.allclose(own, ownership_loss(own_pred, own_t, board))


def test_all_value_only_rows_give_zero_policy_ownership() -> None:
    logits, policy, mask, own_pred, own_t, board = _cat([_value_only_row(), _value_only_row()])
    aux = torch.zeros(2, dtype=torch.bool)
    pol, own = masked_policy_ownership_loss(
        logits, policy, mask, own_pred, own_t, board, aux
    )
    assert float(pol) == 0.0 and float(own) == 0.0


def test_mixed_batch_subsets_to_full_rows_only() -> None:
    """A value-only row mixed with a full row must NOT crash, and the loss must
    equal the loss computed on the full row alone."""
    full = _full_row(7)
    vo = _value_only_row()
    logits, policy, mask, own_pred, own_t, board = _cat([full, vo])
    aux = torch.tensor([True, False])
    pol, own = masked_policy_ownership_loss(
        logits, policy, mask, own_pred, own_t, board, aux
    )
    # Expected: losses over the single full row only.
    f_logits, f_policy, f_mask, f_own_pred, f_own_t, f_board = full
    assert torch.allclose(pol, policy_cross_entropy(f_logits, f_policy, f_mask))
    assert torch.allclose(own, ownership_loss(f_own_pred, f_own_t, f_board))
    assert torch.isfinite(pol) and torch.isfinite(own)
