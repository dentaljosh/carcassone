"""Phase 3 warm-start network — ResNet trunk + policy + value heads.

Starting capacity: 6 ResBlocks × 96 filters (~4M params). See
DECISIONS.md "Phase 3 network starting capacity" for rationale. If
acceptance fails (network can't beat random ≥90%, or net+MCTS(s=50)
doesn't beat vanilla MCTS(s=100) >55%), bump to 10×128.

Input: (B, 40, 25, 25) board tensor + (B, 10) scalar features
Output:
    policy_logits: (B, 2511) — masked-softmax at inference
    value:         (B,)      — tanh-bounded, range [-1, +1]

The masked softmax is applied at INFERENCE only. Training loss applies
the mask before normalizing the policy target (cross-entropy expects
unnormalized logits, but the target distribution is on valid moves only).
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from .action_space import action_size as compute_action_size
from .board_repr import N_CHANNELS
from .features import N_SCALAR_FEATURES


DEFAULT_FILTERS = 96
DEFAULT_BLOCKS = 6
DEFAULT_POLICY_PROJECT_CHANNELS = 4   # 1×1 conv channel-reduction before flatten
DEFAULT_VALUE_PROJECT_CHANNELS = 1
DEFAULT_VALUE_HIDDEN = 64


class ResBlock(nn.Module):
    """Standard residual block: two 3×3 convs with BN+ReLU, skip connection."""

    def __init__(self, channels: int):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(channels)
        self.conv2 = nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out = out + residual
        return F.relu(out)


class CarcassonneNet(nn.Module):
    """Policy + value network for the Carcassonne wrapper.

    Standard AlphaZero-style head pattern: a 1×1 conv reduces trunk channels
    before flattening, so the dense output layer's input dimension stays
    manageable. With trunk channels=96 and policy-projection-channels=4, the
    flatten is 4×25×25=2500, leading to a 2511-output dense of ~6M params
    instead of ~150M from a naive flatten.
    """

    def __init__(
        self,
        window_size: int = 25,
        n_input_channels: int = N_CHANNELS,
        n_scalar_features: int = N_SCALAR_FEATURES,
        n_filters: int = DEFAULT_FILTERS,
        n_blocks: int = DEFAULT_BLOCKS,
        policy_project_channels: int = DEFAULT_POLICY_PROJECT_CHANNELS,
        value_project_channels: int = DEFAULT_VALUE_PROJECT_CHANNELS,
        value_hidden: int = DEFAULT_VALUE_HIDDEN,
    ):
        super().__init__()
        self.window_size = window_size
        self.action_size = compute_action_size(window_size)

        self.stem = nn.Sequential(
            nn.Conv2d(n_input_channels, n_filters, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(n_filters),
            nn.ReLU(inplace=True),
        )
        self.trunk = nn.Sequential(*[ResBlock(n_filters) for _ in range(n_blocks)])

        # Policy head: 1×1 conv → flatten → cat scalars → linear to action_size.
        self.policy_project = nn.Sequential(
            nn.Conv2d(n_filters, policy_project_channels, kernel_size=1, bias=False),
            nn.BatchNorm2d(policy_project_channels),
            nn.ReLU(inplace=True),
        )
        policy_flat_dim = policy_project_channels * window_size * window_size
        self.policy_fc = nn.Linear(policy_flat_dim + n_scalar_features, self.action_size)

        # Value head: 1×1 conv → flatten → cat scalars → linear → ReLU → linear → tanh.
        self.value_project = nn.Sequential(
            nn.Conv2d(n_filters, value_project_channels, kernel_size=1, bias=False),
            nn.BatchNorm2d(value_project_channels),
            nn.ReLU(inplace=True),
        )
        value_flat_dim = value_project_channels * window_size * window_size
        self.value_fc1 = nn.Linear(value_flat_dim + n_scalar_features, value_hidden)
        self.value_fc2 = nn.Linear(value_hidden, 1)

    def forward(
        self, board: torch.Tensor, scalars: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Compute policy logits and value.

        board: (B, n_input_channels, W, W) float
        scalars: (B, n_scalar_features) float
        returns: (policy_logits (B, action_size), value (B,))
        """
        x = self.stem(board)
        x = self.trunk(x)

        p = self.policy_project(x).flatten(start_dim=1)
        p = torch.cat([p, scalars], dim=1)
        policy_logits = self.policy_fc(p)

        v = self.value_project(x).flatten(start_dim=1)
        v = torch.cat([v, scalars], dim=1)
        v = F.relu(self.value_fc1(v))
        value = torch.tanh(self.value_fc2(v)).squeeze(-1)

        return policy_logits, value

    def policy_softmax_with_mask(
        self, policy_logits: torch.Tensor, valid_mask: torch.Tensor
    ) -> torch.Tensor:
        """Masked softmax for inference: only valid actions get nonzero prob.

        valid_mask: (B, action_size) bool/0-1.
        Sets logits of invalid actions to -inf before softmax.
        """
        masked_logits = policy_logits.masked_fill(~valid_mask.bool(), float("-inf"))
        return F.softmax(masked_logits, dim=-1)

    def param_count(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
