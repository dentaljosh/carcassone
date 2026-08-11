"""Paper P1 gap G2 — the TRANSFORMER CONTROL architecture.

A drop-in replacement for `carcassonne_ai.network.CarcassonneNet` in which ONLY
the trunk changes: the 6x96 conv-ResNet trunk becomes a pre-LN transformer
encoder over per-cell tokens. Every head below the trunk is copied verbatim from
`CarcassonneNet` (same modules, same attribute names, same shapes, same forward
arithmetic), so a parameter-count or ruler comparison between the two nets is a
comparison of TRUNK ARCHITECTURE CLASS and nothing else.

Why per-cell tokens and not patches
-----------------------------------
The board tensor is (81, 25, 25): 81 planes over a 25x25 window of the 35x35
engine grid, one cell per Carcassonne tile slot. Tokenising at patch=1 (one
token per cell, 625 tokens, + one global token carrying the 42 scalars) is the
only tokenisation that is INFORMATION-PRESERVING and RESOLUTION-MATCHED to the
ResNet: the transformer sees exactly the tensor the ResNet sees, reshaped, plus
learned absolute 2-D position embeddings. Any patch>1 would pool several tile
slots into one token and hand the transformer a strictly coarser view than the
convnet has -- a handicap that would make a negative result uninterpretable.

The one asymmetry, stated up front because it favours the TRANSFORMER: global
self-attention gives every cell a board-wide receptive field at layer 1, while
the ResNet's 6 residual blocks + stem reach only 15x15 of the 25x25 window. The
ResNet partially compensates through `value_global_pool` (a board-wide mean+max
summary injected into the value head), which this module reproduces exactly. So
the architecture control is run in the direction that is CONSERVATIVE for the
paper's claim: if the transformer still fails to discriminate, it did not fail
for want of global context.

MEASUREMENT ONLY. Nothing here touches production, PRODUCTION.yaml, or any
shared trainer default.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


# Head-shape constants mirrored from carcassonne_ai.network (kept local so this
# module imports cleanly from either the repo tree or a worktree).
DEFAULT_POLICY_PROJECT_CHANNELS = 4
DEFAULT_VALUE_PROJECT_CHANNELS = 1
DEFAULT_VALUE_HIDDEN = 64
DEFAULT_OWNERSHIP_PLANES = 3


class EncoderBlock(nn.Module):
    """Standard pre-LN transformer encoder block (attn -> MLP, both residual).

    Pre-LN (not post-LN) because it trains stably from random init without a
    warmup schedule, and the matched-compute constraint forbids spending budget
    on an architecture-specific warmup the ResNet arm does not get.
    """

    def __init__(self, d_model: int, n_heads: int, ff_mult: int = 4,
                 dropout: float = 0.0):
        super().__init__()
        self.norm1 = nn.LayerNorm(d_model)
        self.attn = nn.MultiheadAttention(
            d_model, n_heads, dropout=dropout, batch_first=True
        )
        self.norm2 = nn.LayerNorm(d_model)
        self.mlp = nn.Sequential(
            nn.Linear(d_model, ff_mult * d_model),
            nn.GELU(),
            nn.Linear(ff_mult * d_model, d_model),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.norm1(x)
        a, _ = self.attn(h, h, h, need_weights=False)
        x = x + a
        x = x + self.mlp(self.norm2(x))
        return x


class CarcassonneTransformer(nn.Module):
    """Transformer trunk + the EXACT CarcassonneNet policy/value/ownership heads.

    Interface is deliberately identical to `CarcassonneNet` -- `forward`,
    `forward_train`, `forward_policy_only`, `policy_softmax_with_mask`,
    `param_count`, and the same introspectable `n_input_channels` /
    `n_scalar_features` ints -- so it is a drop-in for
    `carcassonne_ai.evaluators.make_single_evaluator` and for the solver ruler's
    net-ranker path without changing one line of either.
    """

    def __init__(
        self,
        window_size: int = 25,
        n_input_channels: int = 81,
        n_scalar_features: int = 42,
        action_size: int = 2511,
        d_model: int = 128,
        depth: int = 6,
        n_heads: int = 8,
        ff_mult: int = 4,
        policy_project_channels: int = DEFAULT_POLICY_PROJECT_CHANNELS,
        value_project_channels: int = DEFAULT_VALUE_PROJECT_CHANNELS,
        value_hidden: int = DEFAULT_VALUE_HIDDEN,
        n_ownership_planes: int = DEFAULT_OWNERSHIP_PLANES,
        value_global_pool: bool = True,
    ):
        super().__init__()
        self.window_size = window_size
        self.action_size = action_size
        self.n_ownership_planes = n_ownership_planes
        self.n_input_channels = int(n_input_channels)
        self.n_scalar_features = int(n_scalar_features)
        self.value_global_pool = bool(value_global_pool)
        self.d_model = int(d_model)
        self.depth = int(depth)
        self.n_heads = int(n_heads)
        self.ff_mult = int(ff_mult)

        n_cells = window_size * window_size

        # --- trunk: per-cell tokenisation + learned 2-D position + global token ---
        self.cell_embed = nn.Linear(n_input_channels, d_model)
        self.pos_embed = nn.Parameter(torch.zeros(1, n_cells, d_model))
        nn.init.trunc_normal_(self.pos_embed, std=0.02)
        # The 42 board-level scalars enter as ONE extra token (the ResNet instead
        # concatenates them into both head MLPs; we do BOTH -- token here, and the
        # unchanged head concat below -- so the transformer never sees less).
        self.scalar_token = nn.Linear(n_scalar_features, d_model)
        self.blocks = nn.ModuleList([
            EncoderBlock(d_model, n_heads, ff_mult) for _ in range(depth)
        ])
        self.trunk_norm = nn.LayerNorm(d_model)

        # --- heads: verbatim CarcassonneNet, with n_filters -> d_model ---
        self.policy_project = nn.Sequential(
            nn.Conv2d(d_model, policy_project_channels, kernel_size=1, bias=False),
            nn.BatchNorm2d(policy_project_channels),
            nn.ReLU(inplace=True),
        )
        policy_flat_dim = policy_project_channels * window_size * window_size
        self.policy_fc = nn.Linear(policy_flat_dim + n_scalar_features, action_size)

        self.value_project = nn.Sequential(
            nn.Conv2d(d_model, value_project_channels, kernel_size=1, bias=False),
            nn.BatchNorm2d(value_project_channels),
            nn.ReLU(inplace=True),
        )
        value_flat_dim = value_project_channels * window_size * window_size
        value_in = value_flat_dim + n_scalar_features
        if self.value_global_pool:
            value_in += 2 * d_model
        self.value_fc1 = nn.Linear(value_in, value_hidden)
        self.value_fc2 = nn.Linear(value_hidden, 1)

        self.ownership_head = nn.Conv2d(d_model, n_ownership_planes, kernel_size=1)

    # ------------------------------------------------------------------ trunk
    def _trunk(self, board: torch.Tensor, scalars: torch.Tensor) -> torch.Tensor:
        """(B, C, W, W) + (B, S) -> (B, d_model, W, W), same shape contract as
        CarcassonneNet's `self.trunk(self.stem(board))`."""
        b, _c, h, w = board.shape
        x = board.flatten(2).transpose(1, 2)              # (B, HW, C)
        x = self.cell_embed(x) + self.pos_embed           # (B, HW, d)
        g = self.scalar_token(scalars).unsqueeze(1)       # (B, 1, d)
        x = torch.cat([g, x], dim=1)                      # (B, 1+HW, d)
        for blk in self.blocks:
            x = blk(x)
        x = self.trunk_norm(x)
        cells = x[:, 1:, :].transpose(1, 2).reshape(b, self.d_model, h, w)
        return cells

    # ------------------------------------------------- heads (verbatim copies)
    def _value_from_trunk(self, x: torch.Tensor, scalars: torch.Tensor) -> torch.Tensor:
        v = self.value_project(x).flatten(start_dim=1)
        if self.value_global_pool:
            g = torch.cat([x.mean(dim=(2, 3)), x.amax(dim=(2, 3))], dim=1)
            v = torch.cat([v, scalars, g], dim=1)
        else:
            v = torch.cat([v, scalars], dim=1)
        v = F.relu(self.value_fc1(v))
        return torch.tanh(self.value_fc2(v)).squeeze(-1)

    def forward(self, board: torch.Tensor, scalars: torch.Tensor):
        x = self._trunk(board, scalars)
        p = self.policy_project(x).flatten(start_dim=1)
        p = torch.cat([p, scalars], dim=1)
        policy_logits = self.policy_fc(p)
        value = self._value_from_trunk(x, scalars)
        return policy_logits, value

    def forward_train(self, board: torch.Tensor, scalars: torch.Tensor):
        x = self._trunk(board, scalars)
        p = self.policy_project(x).flatten(start_dim=1)
        p = torch.cat([p, scalars], dim=1)
        policy_logits = self.policy_fc(p)
        value = self._value_from_trunk(x, scalars)
        ownership = torch.tanh(self.ownership_head(x))
        return policy_logits, value, ownership

    def forward_policy_only(self, board: torch.Tensor, scalars: torch.Tensor):
        x = self._trunk(board, scalars)
        p = self.policy_project(x).flatten(start_dim=1)
        p = torch.cat([p, scalars], dim=1)
        return self.policy_fc(p)

    def policy_softmax_with_mask(self, policy_logits, valid_mask):
        masked_logits = policy_logits.masked_fill(~valid_mask.bool(), float("-inf"))
        return F.softmax(masked_logits, dim=-1)

    def param_count(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def trunk_param_count(self) -> int:
        head_names = ("policy_project", "policy_fc", "value_project",
                      "value_fc1", "value_fc2", "ownership_head")
        return sum(
            p.numel() for n, p in self.named_parameters()
            if p.requires_grad and not n.startswith(head_names)
        )

    def arch_dict(self) -> dict:
        return {
            "arch": "transformer",
            "window_size": self.window_size,
            "n_input_channels": self.n_input_channels,
            "n_scalar_features": self.n_scalar_features,
            "action_size": self.action_size,
            "d_model": self.d_model,
            "depth": self.depth,
            "n_heads": self.n_heads,
            "ff_mult": self.ff_mult,
            "value_global_pool": self.value_global_pool,
            "n_ownership_planes": self.n_ownership_planes,
        }


# The two pre-registered configurations (see measurement/paper_g2_20260803/PREREG.md).
CONFIGS = {
    # matched: total params within +3% of the ResNet baseline's 7,511,688
    "tf_match": dict(d_model=128, depth=6, n_heads=8, ff_mult=4),
    # capacity leg: ~3.7x the baseline's total params (mirrors CL-064's ~4x/step)
    "tf_large": dict(d_model=384, depth=12, n_heads=8, ff_mult=4),
}


def build(config: str, **overrides) -> CarcassonneTransformer:
    if config not in CONFIGS:
        raise KeyError(f"unknown g2 config {config!r}; have {sorted(CONFIGS)}")
    kw = dict(CONFIGS[config])
    kw.update(overrides)
    return CarcassonneTransformer(**kw)
