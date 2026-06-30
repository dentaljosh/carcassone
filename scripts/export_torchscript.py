"""Export a CarcassonneNet checkpoint to a TorchScript module the Rust
orchestrator (rust/carc-orch) loads via tch::CModule::load.

The scripted module bakes in the masked softmax so the Rust side never
reimplements `policy_softmax_with_mask` (and so the wire contract stays
exactly (obs, scalars, mask) -> (priors, values), matching eval_server's
_process_batch). Signature:

    forward(obs (B,C,H,W) f32, scalars (B,S) f32, mask (B,A) bool)
        -> (priors (B,A) f32, value (B,) f32)

After export it runs a fp-parity check against the *Python* eval path
(net.forward + policy_softmax_with_mask) on random inputs across several
batch sizes — the scripted graph must match the eager path to fp tolerance
or the export is rejected. This is the model-half proof that gates the Rust
build; if this fails, nothing downstream can be trusted.

Usage:
    python scripts/export_torchscript.py --checkpoint <ckpt.pt> [--out <ts.pt>]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch

from carcassonne_ai.board_repr import N_CHANNELS
from carcassonne_ai.features import N_SCALAR_FEATURES
from carcassonne_ai.network import CarcassonneNet


class _ScriptedEvaluator(torch.nn.Module):
    """Wraps the net so the scripted forward returns exactly what the
    orchestrator wire protocol carries: masked-softmax priors + value.

    Kept deliberately tiny and control-flow-free so torch.jit.script
    compiles it (and net.forward) without surprises."""

    def __init__(self, net: CarcassonneNet):
        super().__init__()
        self.net = net

    def forward(
        self, obs: torch.Tensor, scalars: torch.Tensor, mask: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        logits, value = self.net(obs, scalars)
        # Identical to network.policy_softmax_with_mask.
        masked = logits.masked_fill(~mask.bool(), float("-inf"))
        priors = torch.softmax(masked, dim=-1)
        return priors, value


def _load_net(checkpoint_path: str, device: torch.device) -> tuple[CarcassonneNet, int]:
    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    n_scalar = int(ckpt.get("n_scalar_features", N_SCALAR_FEATURES))
    net = CarcassonneNet(
        n_filters=ckpt["n_filters"],
        n_blocks=ckpt["n_blocks"],
        n_scalar_features=n_scalar,
    ).to(device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)
    return net, n_scalar


def _export(module: torch.nn.Module, n_scalar: int):
    """TorchScript the inference wrapper.

    `torch.jit.script` fails on CarcassonneNet (its overridden load_state_dict
    uses super()/sets, which TorchScript can't compile). Trace is correct here
    regardless: the inference forward is pure straight-line conv/linear/cat/
    masked_fill/softmax with NO data-dependent control flow, so the traced
    graph generalizes over the batch dim. We verify that with the multi-k
    parity check afterwards (the real safety net)."""
    dev = next(module.parameters()).device
    # Trace at batch>1 so no dim is mistaken for a constant.
    ex_obs = torch.zeros(4, N_CHANNELS, 25, 25, device=dev)
    ex_scl = torch.zeros(4, n_scalar, device=dev)
    with torch.no_grad():
        logits, _ = module.net(ex_obs, ex_scl)
    a_size = logits.shape[1]
    ex_mask = torch.ones(4, a_size, dtype=torch.bool, device=dev)
    try:
        return torch.jit.script(module)
    except Exception as e:  # noqa: BLE001 - log why, then trace
        sys.stderr.write(f"[export] torch.jit.script unavailable ({type(e).__name__}); tracing instead\n")
        return torch.jit.trace(module, (ex_obs, ex_scl, ex_mask), check_trace=False)


# Tolerances are fp32 batch-stacking noise, NOT a fudge: the eval_server
# docstring itself only claims equality "modulo batch-stacking order (which
# can shift fp32 reduction order)", and trace can select a different cudnn
# algorithm than eager. A genuine logic error shows O(0.1+) diffs, ~1000x
# above these bars. The value is additionally scaled by residual_scale (0.25)
# on the worker before it touches the leaf, so 1e-3 on value is <<noise.
_TOL_PRIORS = 5e-4   # was 1e-4 — too strict: a TRAINED policy's BatchNorm running-stats +
                     # cudnn's nondeterministic reduction order pushed k=37 to 1.36e-4 and
                     # FATAL-halted a frozen-tiebreak run (2026-06-30). A genuine logic error
                     # shows O(0.1) — still ~200x above this bar, still caught. (review BUG-8)
_TOL_VALUE = 1e-3


def _parity(net: CarcassonneNet, scripted, device: torch.device, n_scalar: int) -> bool:
    """Compare scripted (priors, value) vs the eager Python eval path on
    random inputs over several batch sizes. Returns True iff all match
    within fp32 batch-stacking tolerance."""
    rng = np.random.default_rng(0)
    with torch.no_grad():
        a_size = net(torch.zeros(1, N_CHANNELS, 25, 25, device=device),
                     torch.zeros(1, n_scalar, device=device))[0].shape[1]
    ok = True
    for k in (1, 3, 8, 37):
        obs = torch.from_numpy(rng.standard_normal((k, N_CHANNELS, 25, 25), dtype=np.float32)).to(device)
        scl = torch.from_numpy(rng.standard_normal((k, n_scalar), dtype=np.float32)).to(device)
        mnp = rng.random((k, a_size)) > 0.5
        # guarantee >=1 legal action per row so softmax isn't all -inf
        mnp[:, 0] = True
        mask = torch.from_numpy(mnp).to(device)
        with torch.no_grad():
            logits, val_ref = net(obs, scl)
            priors_ref = net.policy_softmax_with_mask(logits, mask)
            priors_s, val_s = scripted(obs, scl, mask)
        dp = (priors_ref - priors_s).abs().max().item()
        dv = (val_ref - val_s).abs().max().item()
        good = dp < _TOL_PRIORS and dv < _TOL_VALUE
        ok = ok and good
        print(f"  k={k:3d}: max|dpriors|={dp:.2e}  max|dvalue|={dv:.2e}  {'OK' if good else 'FAIL'}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--out", default=None,
                    help="output .pt (default: <checkpoint stem>.ts.pt next to it)")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()

    device = torch.device(args.device)
    out = Path(args.out) if args.out else Path(args.checkpoint).with_suffix(".ts.pt")

    print(f"[export] loading {args.checkpoint} on {device}")
    net, n_scalar = _load_net(args.checkpoint, device)
    wrapper = _ScriptedEvaluator(net).to(device).eval()

    print("[export] tracing...")
    scripted = _export(wrapper, n_scalar)

    print("[export] fp-parity vs eager Python eval path:")
    if not _parity(net, scripted, device, n_scalar):
        sys.stderr.write("[export] PARITY FAILED — refusing to write. Investigate before trusting Rust.\n")
        return 1

    scripted.save(str(out))
    print(f"[export] OK -> {out}  (n_scalar={n_scalar}, C={N_CHANNELS}, device={device})")
    print("[export] Note: load this on the SAME device family in Rust (cuda).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
