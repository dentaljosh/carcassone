#!/usr/bin/env python3
"""OPTIONAL: batch-1 net-forward latency of the CL-067 distilled net, CPU vs ANE.

BEST-EFFORT / SEPARATE-DEPS. ``bench_champion.py`` is the must-work deliverable; this
one is a probe and is allowed to fail. Every heavy import is guarded and every failure
prints the exact ``pip install`` that would fix it.

WHY IT MATTERS — CL-067 (``governance/CLAIM_REGISTRY.csv``) confirmed the distilled
POLICY priors beat the deploy champion at EQUAL SIMS (+35.7 elo pooled, n=800
deck-paired) but REFUTED deployability on COST: an unloaded W=2 probe measured the
net-prior agent at 4.24x the champion's per-move wall clock, and the claim's own
close-out says the open problem is cost — "the net must get ~4x cheaper per move".
A batch-1 forward is the atom of that cost (the deployed evaluator is
``make_remote_single_evaluator``: k=1 per request, worker BLOCKS, so there is no
batching to hide behind). This script asks whether Apple's Neural Engine moves that
atom. It measures LATENCY ONLY — it is not a strength or deployability verdict, and
it does not touch the champion, PRODUCTION.yaml, or any claim.

    python bench_ane_forward.py                       # auto-find the bundled .pt
    python bench_ane_forward.py --iters 200 --checkpoint path/to/x.pt

Requires (macOS, Apple silicon):
    pip install torch coremltools
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_BUNDLE = HERE / "bundle"


def _need(pkg: str, why: str, extra: str = "") -> str:
    return (f"MISSING DEPENDENCY: {pkg}\n"
            f"  needed for: {why}\n"
            f"  install   : pip install {pkg}\n"
            + (f"  note      : {extra}\n" if extra else ""))


def find_checkpoint(bundle: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        if not explicit.is_file():
            raise SystemExit(f"bench_ane_forward: no such checkpoint: {explicit}")
        return explicit
    net_dir = bundle / "net"
    cands = sorted(net_dir.glob("*.pt")) if net_dir.is_dir() else []
    if not cands:
        raise SystemExit(
            f"bench_ane_forward: no .pt under {net_dir}.\n"
            "  The bundle was built with --no-ckpt, or the copy failed. Re-run\n"
            "  scripts/m5_bench/build_bundle.py on the repo box, or pass --checkpoint.")
    return cands[0]


def _stats(xs: list[float]) -> dict:
    s = sorted(xs)
    n = len(s)

    def q(p: float) -> float:
        return s[min(n - 1, max(0, int(round(p * n)) - 1))]

    return {"n": n, "mean_ms": sum(s) / n, "min_ms": s[0],
            "p50_ms": q(0.50), "p90_ms": q(0.90), "max_ms": s[-1]}


# --------------------------------------------------------------------------- #
# torch side                                                                    #
# --------------------------------------------------------------------------- #
def build_net(bundle: Path, ckpt_path: Path):
    """Load the checkpoint into a CarcassonneNet, arch read FROM the checkpoint.

    ``carcassonne_ai.network`` is the one torch-dependent module the bundle carries
    (build_bundle re-adds it AFTER sync_python's import gate, which excludes the torch
    cluster because the Android APK has no torch). Nothing the champion runs imports
    it, so its presence cannot affect ``bench_champion.py``."""
    sys.path.insert(0, str(bundle))
    try:
        import torch
    except ImportError:
        raise SystemExit(_need("torch", "loading the checkpoint and tracing the model",
                               "on Apple silicon the default wheel is arm64 and CPU/MPS "
                               "capable; no CUDA build exists or is needed here"))

    try:
        from carcassonne_ai.network import CarcassonneNet
    except ImportError as exc:
        raise SystemExit(
            f"bench_ane_forward: cannot import carcassonne_ai.network from {bundle}\n"
            f"  {type(exc).__name__}: {exc}\n"
            "  The bundle was built without the torch module; rebuild with "
            "scripts/m5_bench/build_bundle.py.")

    torch.set_num_threads(1)          # single-stream: the regime we care about
    ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    arch = {
        "n_filters": int(ck["n_filters"]),
        "n_blocks": int(ck["n_blocks"]),
        "n_input_channels": int(ck.get("n_input_channels", 78)),
        "n_scalar_features": int(ck.get("n_scalar_features", 10)),
        "value_global_pool": bool(ck.get("value_global_pool", False)),
    }
    net = CarcassonneNet(**arch).eval()
    net.load_state_dict(ck["model_state"])
    n_params = sum(p.numel() for p in net.parameters())
    return torch, net, arch, n_params


def bench_torch(torch, net, arch, iters: int, warmup: int) -> dict:
    W = net.window_size
    board = torch.randn(1, arch["n_input_channels"], W, W)
    scalars = torch.randn(1, arch["n_scalar_features"])
    times = []
    with torch.no_grad():
        for _ in range(warmup):
            net(board, scalars)
        for _ in range(iters):
            t0 = time.perf_counter()
            net(board, scalars)
            times.append((time.perf_counter() - t0) * 1e3)
    return _stats(times)


# --------------------------------------------------------------------------- #
# CoreML side                                                                   #
# --------------------------------------------------------------------------- #
def convert_and_bench(torch, net, arch, *, iters: int, warmup: int,
                      out_dir: Path, precision: str) -> dict:
    try:
        import coremltools as ct
    except ImportError:
        raise SystemExit(_need(
            "coremltools", "torch -> CoreML conversion and ANE dispatch",
            "coremltools>=7 is required for the mlprogram format the ANE needs; "
            "prediction only works on macOS"))
    import numpy as np

    W = board_w = net.window_size
    ex_board = torch.randn(1, arch["n_input_channels"], board_w, board_w)
    ex_scalars = torch.randn(1, arch["n_scalar_features"])

    class _Wrap(torch.nn.Module):
        """Trace-friendly wrapper: fixed positional args, tensor outputs only."""

        def __init__(self, inner):
            super().__init__()
            self.inner = inner

        def forward(self, board, scalars):
            out = self.inner(board, scalars)
            # (policy_logits, value[, ownership]) — keep the first two, which is
            # everything the deployed prior-only evaluator reads.
            return out[0], out[1]

    wrapped = _Wrap(net).eval()
    with torch.no_grad():
        traced = torch.jit.trace(wrapped, (ex_board, ex_scalars))

    ct_precision = {
        "fp16": ct.precision.FLOAT16,
        "fp32": ct.precision.FLOAT32,
    }[precision]

    inputs = [
        ct.TensorType(name="board", shape=ex_board.shape),
        ct.TensorType(name="scalars", shape=ex_scalars.shape),
    ]

    results: dict = {"precision": precision, "window": W, "units": {}}
    out_dir.mkdir(parents=True, exist_ok=True)

    # The ANE only ever runs ML Program models; the older neuralnetwork format is
    # CPU/GPU. compute_units is set at CONVERT time (it is baked into the loaded
    # model), so each unit gets its own conversion — comparing one model reloaded
    # with different units is not a thing coremltools supports.
    unit_specs = [
        ("CPU_ONLY", ct.ComputeUnit.CPU_ONLY),
        ("CPU_AND_NE", ct.ComputeUnit.CPU_AND_NE),
        ("ALL", ct.ComputeUnit.ALL),
    ]

    can_predict = platform.system() == "Darwin"
    if not can_predict:
        results["predict_skipped"] = (
            f"CoreML prediction requires macOS; this is {platform.system()}. "
            "Conversion still runs so the model can be validated off-box.")

    for label, unit in unit_specs:
        entry: dict = {}
        t0 = time.perf_counter()
        try:
            mlmodel = ct.convert(
                traced, inputs=inputs, convert_to="mlprogram",
                compute_units=unit, compute_precision=ct_precision)
        except Exception as exc:                   # noqa: BLE001
            entry["convert_error"] = f"{type(exc).__name__}: {exc}"
            results["units"][label] = entry
            continue
        entry["convert_s"] = time.perf_counter() - t0

        path = out_dir / f"cl067_{precision}_{label}.mlpackage"
        try:
            mlmodel.save(str(path))
            entry["saved"] = str(path)
        except Exception as exc:                   # noqa: BLE001
            entry["save_error"] = f"{type(exc).__name__}: {exc}"

        if not can_predict:
            results["units"][label] = entry
            continue

        feed = {"board": ex_board.numpy().astype(np.float32),
                "scalars": ex_scalars.numpy().astype(np.float32)}
        try:
            for _ in range(warmup):
                mlmodel.predict(feed)
            times = []
            for _ in range(iters):
                t1 = time.perf_counter()
                mlmodel.predict(feed)
                times.append((time.perf_counter() - t1) * 1e3)
            entry["latency"] = _stats(times)
        except Exception as exc:                   # noqa: BLE001
            entry["predict_error"] = f"{type(exc).__name__}: {exc}"
        results["units"][label] = entry

    return results


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    p.add_argument("--checkpoint", type=Path, default=None)
    p.add_argument("--iters", type=int, default=100)
    p.add_argument("--warmup", type=int, default=10)
    p.add_argument("--precision", choices=("fp16", "fp32"), default="fp16",
                   help="fp16 is what the ANE actually runs; fp32 is the honest "
                        "apples-to-apples against the torch CPU baseline")
    p.add_argument("--skip-coreml", action="store_true",
                   help="torch CPU baseline only")
    p.add_argument("--out", type=Path, default=None)
    a = p.parse_args(argv)

    bundle = a.bundle.resolve()
    ckpt = find_checkpoint(bundle, a.checkpoint)
    torch, net, arch, n_params = build_net(bundle, ckpt)

    stamp = time.strftime("%Y%m%dT%H%M%S")
    host = platform.node().split(".")[0] or "unknown"
    out_path = a.out or (HERE / "results" / f"bench_ane_{host}_{stamp}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    result = {
        "schema": "carcassonne-m5-bench/v1",
        "kind": "net_forward_latency_batch1",
        "claim": "CL-067",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "machine": {"platform": platform.platform(), "machine": platform.machine(),
                    "python": sys.version.split()[0], "node": platform.node()},
        "checkpoint": {"path": str(ckpt), "arch": arch, "n_params": int(n_params)},
        "torch_version": torch.__version__,
        "iters": a.iters,
    }

    print(f"bench_ane_forward: {ckpt.name}  {n_params / 1e6:.2f} M params  "
          f"{arch['n_filters']}x{arch['n_blocks']}  torch {torch.__version__}")
    print("-- torch CPU batch-1 (1 thread)")
    result["torch_cpu"] = bench_torch(torch, net, arch, a.iters, a.warmup)
    t = result["torch_cpu"]
    print(f"   mean {t['mean_ms']:.3f} ms   p50 {t['p50_ms']:.3f}   p90 {t['p90_ms']:.3f}")

    if not a.skip_coreml:
        print(f"-- CoreML convert + predict ({a.precision})")
        try:
            result["coreml"] = convert_and_bench(
                torch, net, arch, iters=a.iters, warmup=a.warmup,
                out_dir=HERE / "results" / "coreml", precision=a.precision)
            for label, entry in result["coreml"]["units"].items():
                lat = entry.get("latency")
                if lat:
                    print(f"   {label:<11} mean {lat['mean_ms']:.3f} ms   "
                          f"p50 {lat['p50_ms']:.3f}   p90 {lat['p90_ms']:.3f}")
                else:
                    why = (entry.get("predict_error") or entry.get("convert_error")
                           or result["coreml"].get("predict_skipped") or "no latency")
                    print(f"   {label:<11} -- {why}")
        except SystemExit as exc:
            # A missing optional dep must not lose the torch baseline we already have.
            result["coreml_error"] = str(exc)
            print(str(exc), file=sys.stderr)

    out_path.write_text(json.dumps(result, indent=2, default=str))
    print(f"\nbench_ane_forward: wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
