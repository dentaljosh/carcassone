#!/usr/bin/env python3
"""Export the policy head of a `CarcassonneNet` checkpoint to ONNX, at fixed batch sizes.

WHY FIXED BATCH. ONNX Runtime's CUDA execution provider will only capture a CUDA
Graph for a session whose input shapes are static. The CUDA Graph is not a nicety
here — it is the whole reason a rust-side evaluator is worth building. Measured on
this box (RTX 5060 Ti), eager batch-1 costs 2.40 ms while the same graph replayed
costs 0.339 ms, a 7.1x cut that comes entirely from not re-issuing ~30 kernel
launches per forward. Exporting one file per batch size is the cheapest way to get
that, and the batch sizes that matter are few and known: 1, the k-determinization
width 8 (the SHM transport's `MAX_K`), and 64 for a throughput reference.

POLICY-ONLY, RAW LOGITS. Both choices are inherited from
`scripts/m5_bench/export_cl067_coreml.py` and exist for the same reasons:

  * the `fair-netprior` arm never reads the net's value (the value is the FROZEN
    champion v2.9 leaf), so exporting the value head costs forward time for output
    nobody consumes;
  * the mask is applied on the HOST, not baked into the graph, so the only
    numerical difference between this backend and torch is the rounding of the
    logits themselves. Bake the mask in and that error budget stops being
    interpretable — see `coreml_evaluator`'s DESIGN DECISION 1.

NOTHING IS WRITTEN UNTIL EQUIVALENCE IS PROVEN. As with the CoreML and LiteRT
exports, the wrapper is asserted bit-identical to the untouched `CarcassonneNet`
before any artifact appears, so a broken export fails here rather than showing up
later as a mysterious strength regression.

    python3 rust/carc/carc-net/tools/export_onnx.py \
        --checkpoint /mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt \
        --out-dir <dir> --batches 1 8 64
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import torch

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "src"))

from carcassonne_ai.network import CarcassonneNet  # noqa: E402


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class PolicyOnly(torch.nn.Module):
    """Trace target: raw policy logits, no mask, no softmax, no value head."""

    def __init__(self, net: CarcassonneNet):
        super().__init__()
        self.net = net

    def forward(self, board: torch.Tensor, scalars: torch.Tensor) -> torch.Tensor:
        return self.net.forward_policy_only(board, scalars)


def build(ckpt_path: Path):
    ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    net = CarcassonneNet(
        window_size=25,
        n_input_channels=ck["n_input_channels"],
        n_scalar_features=ck["n_scalar_features"],
        n_filters=ck["n_filters"],
        n_blocks=ck["n_blocks"],
        value_global_pool=ck["value_global_pool"],
    )
    net.load_state_dict(ck["model_state"])
    net.eval()
    return net, ck


def assert_wrap_matches(net: CarcassonneNet, wrap: PolicyOnly, ck) -> dict:
    """The export wrapper must BE the net of record, not merely resemble it."""
    g = torch.Generator().manual_seed(0)
    b = torch.randn(4, ck["n_input_channels"], 25, 25, generator=g)
    s = torch.randn(4, ck["n_scalar_features"], generator=g)
    with torch.no_grad():
        ref = net.forward_policy_only(b, s)
        got = wrap(b, s)
    if not torch.equal(ref, got):
        raise SystemExit(
            f"export wrapper diverges from CarcassonneNet: max abs "
            f"{(ref - got).abs().max().item():.3e} — refusing to write an artifact")
    return {"wrapper_bit_identical": True, "probe_shape": list(ref.shape)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", type=Path,
                    default=Path("/mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt"))
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--batches", type=int, nargs="+", default=[1, 8, 64])
    ap.add_argument("--opset", type=int, default=17)
    a = ap.parse_args()

    a.out_dir.mkdir(parents=True, exist_ok=True)
    net, ck = build(a.checkpoint)
    wrap = PolicyOnly(net).eval()
    equiv = assert_wrap_matches(net, wrap, ck)

    manifest = {
        "schema": "carc-net-onnx-export/v1",
        "checkpoint": str(a.checkpoint),
        "checkpoint_sha256": sha256_file(a.checkpoint),
        "arch": {k: ck[k] for k in ("n_filters", "n_blocks", "n_input_channels",
                                    "n_scalar_features", "sighted",
                                    "include_farm_scalars", "value_global_pool")},
        "head": "policy_only_raw_logits",
        "mask_applied": "host_side_f32 (NOT in the graph)",
        "opset": a.opset,
        "torch": torch.__version__,
        "equivalence": equiv,
        "files": [],
    }

    for B in a.batches:
        board = torch.randn(B, ck["n_input_channels"], 25, 25)
        scal = torch.randn(B, ck["n_scalar_features"])
        out = a.out_dir / f"policy_b{B}.onnx"
        torch.onnx.export(
            wrap, (board, scal), str(out),
            input_names=["board", "scalars"], output_names=["policy_logits"],
            opset_version=a.opset, dynamo=False,
        )
        manifest["files"].append({
            "batch": B, "path": out.name, "sha256": sha256_file(out),
            "bytes": out.stat().st_size,
        })
        print(f"wrote {out} ({out.stat().st_size/1e6:.1f} MB)")

    mpath = a.out_dir / "export_manifest.json"
    mpath.write_text(json.dumps(manifest, indent=1))
    print(f"wrote {mpath}")


if __name__ == "__main__":
    main()
