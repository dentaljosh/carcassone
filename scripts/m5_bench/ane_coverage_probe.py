#!/usr/bin/env python3
"""Supplement to bench_ane_forward.py — the two things it does NOT report.

bench_ane_forward.py times CPU_ONLY / CPU_AND_NE / ALL but records neither
(a) how the graph was PARTITIONED across compute devices, nor
(b) whether the CoreML outputs AGREE with torch.

Both are needed before any ANE latency number means anything: a model that
silently fell back to CPU is not an ANE measurement, and a model that runs fast
because fp16 mangled it is not a usable evaluator.

Reads the .mlpackage files bench_ane_forward.py already saved. Writes JSON.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def coverage(pkg: Path) -> dict:
    """Per-operation compute-device assignment via MLComputePlan (coremltools >= 8)."""
    import coremltools as ct

    out: dict = {"package": str(pkg)}
    try:
        from coremltools.models.compute_plan import MLComputePlan
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"MLComputePlan unavailable: {type(exc).__name__}: {exc}"
        return out

    # MLComputePlan wants a COMPILED model (.mlmodelc); handed an .mlpackage the
    # underlying C++ throws an uncaught ios_base::failure and ABORTS the process,
    # so compile first and never pass the package path.
    try:
        from coremltools.models.utils import compile_model
        compiled = compile_model(str(pkg))
        out["compiled"] = str(compiled)
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"compile_model: {type(exc).__name__}: {exc}"
        return out

    try:
        plan = MLComputePlan.load_from_path(
            path=str(compiled),
            compute_units=ct.ComputeUnit.CPU_AND_NE,
        )
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"load_from_path: {type(exc).__name__}: {exc}"
        return out

    try:
        prog = plan.model_structure.program
        fn = prog.functions["main"]
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"program walk: {type(exc).__name__}: {exc}"
        return out

    devices: Counter = Counter()
    per_op_type: dict[str, Counter] = {}
    non_ane: list[dict] = []
    for op in fn.block.operations:
        try:
            usage = plan.get_compute_device_usage_for_mlprogram_operation(op)
        except Exception:  # noqa: BLE001
            usage = None
        if usage is None:
            dev = "unknown"
        else:
            dev = type(usage.preferred_compute_device).__name__
        devices[dev] += 1
        per_op_type.setdefault(op.operator_name, Counter())[dev] += 1
        if "Neural" not in dev and op.operator_name not in ("const",):
            non_ane.append({"op": op.operator_name, "device": dev})

    total = sum(devices.values())
    ane = sum(v for k, v in devices.items() if "Neural" in k)
    out["ops_total"] = total
    out["ops_by_device"] = dict(devices)
    out["ane_op_fraction"] = (ane / total) if total else None
    out["fully_on_ane"] = bool(total) and ane == total
    out["by_op_type"] = {k: dict(v) for k, v in per_op_type.items()}
    out["non_ane_ops"] = non_ane[:60]
    out["non_ane_op_count"] = len(non_ane)
    return out


def agreement(bundle: Path, ckpt: Path, pkgs: dict[str, Path], seed: int) -> dict:
    import numpy as np
    import torch

    sys.path.insert(0, str(bundle))
    from carcassonne_ai.network import CarcassonneNet

    torch.set_num_threads(1)
    ck = torch.load(ckpt, map_location="cpu", weights_only=False)
    arch = {
        "n_filters": int(ck["n_filters"]),
        "n_blocks": int(ck["n_blocks"]),
        "n_input_channels": int(ck.get("n_input_channels", 78)),
        "n_scalar_features": int(ck.get("n_scalar_features", 10)),
        "value_global_pool": bool(ck.get("value_global_pool", False)),
    }
    net = CarcassonneNet(**arch).eval()
    net.load_state_dict(ck["model_state"])
    W = net.window_size

    g = torch.Generator().manual_seed(seed)
    board = torch.randn(1, arch["n_input_channels"], W, W, generator=g)
    scalars = torch.randn(1, arch["n_scalar_features"], generator=g)
    with torch.no_grad():
        out = net(board, scalars)
    ref_policy = out[0].numpy().astype(np.float64)
    ref_value = out[1].numpy().astype(np.float64)

    import coremltools as ct  # noqa: F401

    feed = {"board": board.numpy().astype(np.float32),
            "scalars": scalars.numpy().astype(np.float32)}

    res: dict = {"seed": seed, "arch": arch,
                 "ref": {"policy_absmax": float(np.abs(ref_policy).max()),
                         "value": ref_value.reshape(-1).tolist()[:4]},
                 "units": {}}
    for label, pkg in pkgs.items():
        entry: dict = {}
        try:
            m = ct.models.MLModel(str(pkg))
            got = m.predict(feed)
            keys = list(got.keys())
            entry["output_keys"] = keys
            # policy = the larger tensor, value = the smaller
            arrs = sorted(((k, np.asarray(v, dtype=np.float64)) for k, v in got.items()),
                          key=lambda kv: -kv[1].size)
            pol = arrs[0][1].reshape(ref_policy.shape)
            val = arrs[1][1].reshape(ref_value.shape)
            dp = np.abs(pol - ref_policy)
            dv = np.abs(val - ref_value)
            denom = max(float(np.abs(ref_policy).max()), 1e-9)
            entry["policy_max_abs_diff"] = float(dp.max())
            entry["policy_mean_abs_diff"] = float(dp.mean())
            entry["policy_max_rel_to_range"] = float(dp.max() / denom)
            entry["value_max_abs_diff"] = float(dv.max())
            entry["policy_argmax_torch"] = int(ref_policy.argmax())
            entry["policy_argmax_coreml"] = int(pol.argmax())
            entry["policy_argmax_agrees"] = bool(ref_policy.argmax() == pol.argmax())
            k = min(10, ref_policy.size)
            top_t = set(np.argsort(-ref_policy.reshape(-1))[:k].tolist())
            top_c = set(np.argsort(-pol.reshape(-1))[:k].tolist())
            entry["top10_overlap"] = len(top_t & top_c)
        except Exception as exc:  # noqa: BLE001
            entry["error"] = f"{type(exc).__name__}: {exc}"
        res["units"][label] = entry
    return res


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--results", type=Path, default=HERE / "results")
    p.add_argument("--bundle", type=Path, default=HERE / "bundle")
    p.add_argument("--precision", default="fp16")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=Path, default=None)
    a = p.parse_args()

    coreml_dir = a.results / "coreml"
    pkgs = {}
    for label in ("CPU_ONLY", "CPU_AND_NE", "ALL"):
        pkg = coreml_dir / f"cl067_{a.precision}_{label}.mlpackage"
        if pkg.exists():
            pkgs[label] = pkg
    if not pkgs:
        raise SystemExit(f"no .mlpackage under {coreml_dir}; run bench_ane_forward.py first")

    ckpts = sorted((a.bundle / "net").glob("*.pt"))
    out = {
        "schema": "carcassonne-m5-bench-supplement/v1",
        "kind": "ane_coverage_and_agreement",
        "precision": a.precision,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "machine": {"platform": platform.platform(), "node": platform.node()},
        "packages": {k: str(v) for k, v in pkgs.items()},
    }
    try:
        import coremltools as ct
        out["coremltools_version"] = ct.__version__
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"coremltools missing: {exc}")

    print("-- output agreement vs torch fp32 CPU")
    out["agreement"] = agreement(a.bundle, ckpts[0], pkgs, a.seed)
    for label, e in out["agreement"]["units"].items():
        if "error" in e:
            print(f"   {label:<11} -- {e['error']}")
        else:
            print(f"   {label:<11} policy maxabs {e['policy_max_abs_diff']:.4g}  "
                  f"value maxabs {e['value_max_abs_diff']:.4g}  "
                  f"argmax_agrees={e['policy_argmax_agrees']}  "
                  f"top10_overlap={e['top10_overlap']}/10")

    dest = a.out or (a.results / f"ane_coverage_{platform.node().split('.')[0]}_"
                     f"{time.strftime('%Y%m%dT%H%M%S')}.json")
    # Persist the agreement result BEFORE touching MLComputePlan: a bad input makes
    # the CoreML C++ layer abort the whole process, which would lose it.
    dest.write_text(json.dumps(out, indent=2, default=str))

    out["coverage"] = {}
    for label, pkg in pkgs.items():
        print(f"-- coverage {label}")
        out["coverage"][label] = coverage(pkg)
        c = out["coverage"][label]
        print(f"   {c.get('ops_by_device', c.get('error'))}")
        dest.write_text(json.dumps(out, indent=2, default=str))

    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
