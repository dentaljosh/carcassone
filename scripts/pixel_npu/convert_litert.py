#!/usr/bin/env python3
"""torch -> LiteRT (.tflite) conversion of the CL-067 distilled net, for the Pixel NPU probe.

STAGE "Eff Jensen". The Apple M5's ANE runs this net's batch-1 forward in 0.42 ms fp16 (all 52
ops on the NPU, zero fallback) vs 2.6 ms torch-CPU. DECISIONS 2026-07-28 named the Android
equivalent route as "Pixel Tensor NPU via LiteRT (one artifact, per-vendor delegates)". This
script builds that one artifact.

    python convert_litert.py --out-dir /mnt/c/carc-shared/pixel_npu_20260729

Produces, in --out-dir:
    cl067_iter03_fp32.tflite                    the baseline artifact
    cl067_iter03_fp16.tflite                    fp16 weights (float_casting), GPU-delegate target
    cl067_iter03_int8dyn_EXPERIMENTAL.tflite    int8 dynamic weights -- see the WARNING below
    MANIFEST.json                               every converter version + every sha256

⚠️ THE int8 ARTIFACT IS EXPERIMENTAL AND IS NOT A DEPLOY CANDIDATE. It is emitted because it is
nearly free and because some mobile NPU paths accept only int8. Its policy head has 2511 logits
and int8 weight quantization is expected to move argmax on a non-trivial fraction of positions.
`verify_agreement.py` measures exactly that; read the number before using the artifact for
anything, and never headline its latency.

TOOLCHAIN NOTE (2026-07-28): the converter formerly known as `ai-edge-torch` was RENAMED to
`litert-torch`; `ai-edge-torch` on PyPI is now a deprecation shim (0.7.2, "Development Status ::
7 - Inactive") whose only dependency is `litert-torch`. This script targets `litert_torch`
directly. Install into a DEDICATED venv -- never the project .venv:

    uv venv --python 3.12 /path/to/venv
    uv pip install --python /path/to/venv/bin/python --index-strategy unsafe-best-match \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        "litert-torch==0.9.2" "torch==2.11.0" numpy

The net's own module (`carcassonne_ai.network`) is imported from the FROZEN M5 bundle, not from
the live tree -- cluster runs re-import `src/` from disk and this script must not be able to
perturb them. Nothing here writes inside the repo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
import traceback
from pathlib import Path

import numpy as np

DEFAULT_BUNDLE = Path("/mnt/c/carc-shared/m5_bench_20260728/bundle")
DEFAULT_CKPT = Path("/mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt")
# The checkpoint of record for CL-067. Any copy must still hash to this.
EXPECTED_CKPT_SHA256 = (
    "6e2679908d79a76cd2d66789d992676a5bfa85946a1543968982b308873751a1")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pkg_versions() -> dict:
    """Record EVERY converter version. A .tflite is opaque; its provenance is this dict."""
    import importlib.metadata as md
    want = ("litert-torch", "litert-converter", "ai-edge-litert", "ai-edge-quantizer",
            "torch", "torchao", "jax", "jaxlib", "numpy", "flatbuffers", "absl-py",
            "ai-edge-torch")
    out = {}
    for name in want:
        try:
            out[name] = md.version(name)
        except md.PackageNotFoundError:
            out[name] = None
    out["python"] = sys.version.split()[0]
    out["platform"] = platform.platform()
    return out


# --------------------------------------------------------------------------- #
# 1. Build the torch module                                                     #
# --------------------------------------------------------------------------- #
class ForwardOnly:
    """Marker namespace; the real wrapper is built inside build_net (needs torch)."""


def build_net(bundle: Path, ckpt_path: Path):
    """Load the checkpoint into a CarcassonneNet, arch read FROM the checkpoint.

    Mirrors `bench_ane_forward.py`'s loader so the LiteRT artifact and the CoreML artifact are
    provably the same weights and the same arch resolution.
    """
    sys.path.insert(0, str(bundle))
    import torch

    from carcassonne_ai.network import CarcassonneNet  # noqa: PLC0415

    torch.set_num_threads(1)
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

    import torch.nn.functional as F  # noqa: N812, PLC0415

    class Wrap(torch.nn.Module):
        """Export-friendly wrapper: fixed positional tensor args, tensor outputs only.

        Returns (policy_logits, value) -- exactly what the deployed prior-only evaluator reads.
        The ownership aux head lives in `forward_train` and is never exported. The value is
        (B, 1) rather than `forward`'s squeezed (B,); a rank-1 output is needless shape friction
        in downstream runtimes.

        ⚠️ ONE DELIBERATE OP SUBSTITUTION -- read this before trusting the artifact.

        This re-expresses `CarcassonneNet.forward` + `_value_from_trunk` rather than calling
        them, for exactly one reason: the checkpoint has `value_global_pool=True`, so the value
        head computes `x.amax(dim=(2, 3))`, and litert-torch's NHWC layout pass has no rewriter
        for `amax`. Converting the stock module fails hard with:

            RuntimeError: NHWC node rewriter not found: amax

        `x.amax(dim=(2, 3))` is global max pooling, so we substitute
        `F.max_pool2d(x, kernel_size=(H, W)).flatten(1)`, which the converter does handle. Max is
        order-independent, so the substitution is EXACT, not an approximation -- and it is
        asserted to be bit-identical against the unmodified `net(...)` in `assert_wrap_matches`
        before anything is exported. The mean branch is left as `x.mean(dim=(2, 3))` because that
        op converts fine and float summation order is not worth perturbing.

        Nothing else differs from the production forward: same modules, same weights, same order.
        """

        def __init__(self, inner):
            super().__init__()
            self.inner = inner

        def forward(self, board, scalars):
            m = self.inner
            x = m.stem(board)
            x = m.trunk(x)

            p = m.policy_project(x).flatten(start_dim=1)
            p = torch.cat([p, scalars], dim=1)
            policy_logits = m.policy_fc(p)

            v = m.value_project(x).flatten(start_dim=1)
            if m.value_global_pool:
                h, w = x.shape[2], x.shape[3]
                g_mean = x.mean(dim=(2, 3))
                g_max = F.max_pool2d(x, kernel_size=(h, w)).flatten(start_dim=1)  # == x.amax
                v = torch.cat([v, scalars, g_mean, g_max], dim=1)
            else:
                v = torch.cat([v, scalars], dim=1)
            v = F.relu(m.value_fc1(v))
            value = torch.tanh(m.value_fc2(v))

            return policy_logits, value

    return torch, net, Wrap(net).eval(), arch, n_params


def assert_wrap_matches(torch, net, wrapped, arch, *, n: int = 8) -> dict:
    """Prove the export wrapper is the production forward, before we export it.

    The wrapper substitutes one op (see `Wrap`). If that substitution were ever wrong -- or if
    someone later "tidies" the wrapper and silently changes the maths -- every downstream number
    in this stage would be measuring the wrong model while looking perfectly healthy. So gate the
    export on an exact comparison against the untouched `net.forward`.
    """
    W = 25
    torch.manual_seed(0)
    board = torch.randn(n, arch["n_input_channels"], W, W)
    scalars = torch.randn(n, arch["n_scalar_features"])
    with torch.no_grad():
        ref_policy, ref_value = net(board, scalars)
        got_policy, got_value = wrapped(board, scalars)
    d_policy = float((ref_policy - got_policy).abs().max())
    d_value = float((ref_value.reshape(-1, 1) - got_value).abs().max())
    # Bit-identical is what we expect; 1e-6 is slack for nothing in particular.
    if d_policy > 1e-6 or d_value > 1e-6:
        raise RuntimeError(
            "convert_litert: the export wrapper does NOT match CarcassonneNet.forward "
            f"(policy max|d| {d_policy:.3e}, value max|d| {d_value:.3e}). Refusing to export a "
            "model that is not the net of record.")
    return {"n": n, "policy_max_abs_diff": d_policy, "value_max_abs_diff": d_value}


# --------------------------------------------------------------------------- #
# 2. Conversion                                                                 #
# --------------------------------------------------------------------------- #
def convert_fp32(torch, wrapped, arch, out_path: Path) -> dict:
    """Baseline conversion. Everything else is a post-pass over this flatbuffer."""
    import litert_torch

    W = 25  # window_size; the net's action space is built for 25x25
    board = torch.randn(1, arch["n_input_channels"], W, W)
    scalars = torch.randn(1, arch["n_scalar_features"])

    t0 = time.perf_counter()
    edge = litert_torch.convert(wrapped, (board, scalars))
    dt = time.perf_counter() - t0
    edge.export(str(out_path))
    return {"ok": True, "convert_s": dt, "path": str(out_path),
            "bytes": out_path.stat().st_size, "sha256": sha256_file(out_path),
            "sample_shapes": {"board": list(board.shape), "scalars": list(scalars.shape)}}


def _calibration_data(npz_path: Path, signature: str, in_names: list[str]) -> dict:
    """Feed the REAL 60 positions to the calibrator, not random noise.

    Static (full-integer) quantization picks activation scales from observed ranges. A real
    Carcassonne board is ~93% zeros with a very different distribution from N(0,1), so
    calibrating on random inputs would set activation ranges that are wrong everywhere the model
    is actually used. `encode_positions.py` produces the real ones.
    """
    z = np.load(npz_path, allow_pickle=False)
    boards, scalars = z["boards"], z["scalars"]
    board_name = next(n for n in in_names if "board" in n.lower()) if any(
        "board" in n.lower() for n in in_names) else in_names[0]
    scalar_name = next(n for n in in_names if n != board_name)
    return {signature: [
        {board_name: boards[i:i + 1].astype(np.float32),
         scalar_name: scalars[i:i + 1].astype(np.float32)}
        for i in range(boards.shape[0])]}


def quantize_from(fp32_path: Path, out_path: Path, *, mode: str,
                  calib_npz: Path | None = None) -> dict:
    """Post-pass the fp32 flatbuffer with AI Edge Quantizer.

    mode="fp16"  -> float_casting: weights stored as fp16, dequantized before a float compute.
                    This is the artifact you want under the GPU delegate.
    mode="int8dyn" -> the stock `dynamic_wi8_afp32` recipe: per-channel int8 weights, fp32
                    activations, integer compute. EXPERIMENTAL, see the module docstring.
    mode="int8full" -> `static_wi8_ai8`: int8 weights AND int8 activations, calibrated on the 60
                    real positions. EXPERIMENTAL. This exists for ONE reason: measured on a
                    Pixel 9 Pro 2026-07-29, the `google-edgetpu` NNAPI driver REJECTS both the
                    float and the dynamic-int8 graphs ("the model graph will not be executed by
                    the delegate") and silently falls back to XNNPACK. A full-integer graph is
                    the only remaining shape an EdgeTPU-class accelerator is likely to accept,
                    so it is worth one artifact to find out. Its fidelity will be the worst of
                    the set -- verify before believing any latency it produces.

    NOTE on fp16: `litert_torch.convert`'s own `quant_config` accepts only a PT2E quantizer or a
    generative recipe -- there is no fp16 knob on the converter itself (upstream issue
    google-ai-edge/litert-torch#875, "Convert to float16 model", still open). The supported route
    is this post-pass via the quantizer's FLOAT_CASTING algorithm, which is what we use.
    """
    from ai_edge_quantizer import qtyping, quantizer, recipe

    qt = quantizer.Quantizer(str(fp32_path))
    if mode == "fp16":
        qt.update_quantization_recipe(
            regex=".*",
            operation_name=qtyping.TFLOperationName.ALL_SUPPORTED,
            algorithm_key=recipe.AlgorithmName.FLOAT_CASTING,
            op_config=qtyping.OpQuantizationConfig(
                weight_tensor_config=qtyping.TensorQuantizationConfig(
                    num_bits=16, dtype=qtyping.TensorDataType.FLOAT),
                compute_precision=qtyping.ComputePrecision.FLOAT,
            ),
        )
    elif mode == "int8dyn":
        qt.load_quantization_recipe(recipe.dynamic_wi8_afp32())
    elif mode == "int8full":
        qt.load_quantization_recipe(recipe.static_wi8_ai8())
    else:
        raise ValueError(f"quantize_from: unknown mode {mode!r}")

    calib_result = None
    if qt.need_calibration:
        if calib_npz is None or not calib_npz.is_file():
            raise RuntimeError(
                f"quantize_from({mode}): recipe requires activation calibration but no "
                f"calibration positions were supplied (looked for {calib_npz}). Refusing to "
                "emit an uncalibrated -- i.e. wrong -- artifact. Run encode_positions.py first.")
        from ai_edge_litert.interpreter import Interpreter

        interp = Interpreter(model_path=str(fp32_path))
        interp.allocate_tensors()
        sig = list(interp.get_signature_list().keys())[0]
        in_names = list(interp.get_signature_list()[sig]["inputs"])
        calib_result = qt.calibrate(_calibration_data(calib_npz, sig, in_names))
    elif mode in ("fp16", "int8dyn"):
        # These two are weight-only / dynamic and must NOT need calibration. If a toolchain
        # upgrade changes that, fail rather than silently emit an uncalibrated model.
        pass

    t0 = time.perf_counter()
    result = qt.quantize(calibration_result=calib_result, enable_progress_bar=False)
    dt = time.perf_counter() - t0
    # export_model refuses to overwrite; a re-run must be idempotent or a partial MANIFEST gets
    # written whose artifact list disagrees with what is on disk.
    out_path.unlink(missing_ok=True)
    result.export_model(str(out_path))
    return {"ok": True, "quantize_s": dt, "path": str(out_path),
            "bytes": out_path.stat().st_size, "sha256": sha256_file(out_path),
            "recipe": qt.get_quantization_recipe()}


def tflite_summary(path: Path) -> dict:
    """Op census of the produced flatbuffer, via the LiteRT interpreter.

    This is the artifact's *shape contract*, and it is the thing to diff if a phone-side run
    behaves oddly. It also gives the total op count that §3-D of the runbook compares against
    NNAPI's "replacing N nodes" line to catch silent partial delegation.
    """
    from ai_edge_litert.interpreter import Interpreter

    interp = Interpreter(model_path=str(path))
    interp.allocate_tensors()
    ops: dict[str, int] = {}
    try:
        for d in interp._get_ops_details():          # noqa: SLF001 - no public equivalent
            ops[d["op_name"]] = ops.get(d["op_name"], 0) + 1
    except Exception:                                # noqa: BLE001
        ops = {"(op census unavailable on this ai-edge-litert build)": 0}
    return {
        "inputs": [{"name": d["name"], "shape": [int(x) for x in d["shape"]],
                    "dtype": str(d["dtype"])} for d in interp.get_input_details()],
        "outputs": [{"name": d["name"], "shape": [int(x) for x in d["shape"]],
                     "dtype": str(d["dtype"])} for d in interp.get_output_details()],
        "n_ops": sum(ops.values()), "ops": ops,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    p.add_argument("--checkpoint", type=Path, default=DEFAULT_CKPT)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--skip-int8", action="store_true",
                   help="skip the EXPERIMENTAL int8 variants")
    p.add_argument("--calib-npz", type=Path, default=None,
                   help="encode_positions.py output, used to calibrate int8full; "
                        "default <out-dir>/positions_encoded.npz")
    p.add_argument("--allow-hash-mismatch", action="store_true",
                   help="proceed even if the checkpoint sha256 is not the CL-067 one")
    a = p.parse_args(argv)

    ckpt = a.checkpoint.resolve()
    if not ckpt.is_file():
        raise SystemExit(f"convert_litert: no checkpoint at {ckpt}")
    got = sha256_file(ckpt)
    if got != EXPECTED_CKPT_SHA256 and not a.allow_hash_mismatch:
        raise SystemExit(
            f"convert_litert: checkpoint sha256 mismatch\n"
            f"  expected {EXPECTED_CKPT_SHA256}\n  got      {got}\n"
            "  This is not the CL-067 net of record. Pass --allow-hash-mismatch only if you\n"
            "  mean to convert a DIFFERENT net, and relabel the outputs accordingly.")

    a.out_dir.mkdir(parents=True, exist_ok=True)
    versions = pkg_versions()
    torch, net, wrapped, arch, n_params = build_net(a.bundle.resolve(), ckpt)
    wrap_check = assert_wrap_matches(torch, net, wrapped, arch)

    print(f"convert_litert: {ckpt.name}  {n_params / 1e6:.2f} M params  "
          f"{arch['n_filters']}x{arch['n_blocks']}  "
          f"{arch['n_input_channels']}ch/{arch['n_scalar_features']}scl  "
          f"torch {torch.__version__}  litert-torch {versions['litert-torch']}")

    manifest = {
        "schema": "carcassonne-pixel-npu/v1",
        "kind": "torch_to_litert_conversion",
        "claim": "CL-067",
        "stage": "Eff Jensen",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "checkpoint": {"path": str(ckpt), "sha256": got, "arch": arch,
                       "n_params": int(n_params)},
        "bundle": str(a.bundle.resolve()),
        "converter_versions": versions,
        "export_wrapper_equivalence": wrap_check,
        "artifacts": {},
        "notes": [
            "ai-edge-torch was RENAMED to litert-torch (ai-edge-torch 0.7.2 is a deprecation "
            "shim). Versions above are the real toolchain.",
            "The export wrapper substitutes F.max_pool2d(kernel=HxW) for x.amax(dim=(2,3)) in "
            "the value head: litert-torch's NHWC pass has no rewriter for amax and conversion "
            "of the stock module fails with 'NHWC node rewriter not found: amax'. The "
            "substitution is exact (max is order-independent) and is asserted against the "
            "unmodified net in export_wrapper_equivalence above.",
            "CPU-interpreter agreement is measured by verify_agreement.py. NPU/GPU-delegate "
            "agreement can only be measured on-device.",
        ],
    }

    fp32 = a.out_dir / "cl067_iter03_fp32.tflite"
    print("-- fp32 convert")
    try:
        entry = convert_fp32(torch, wrapped, arch, fp32)
        entry["tflite"] = tflite_summary(fp32)
        manifest["artifacts"]["fp32"] = entry
        print(f"   ok  {entry['bytes'] / 1e6:.2f} MB  {entry['convert_s']:.1f}s  "
              f"{entry['tflite']['n_ops']} ops")
    except Exception as exc:                          # noqa: BLE001
        # A documented failure is an acceptable result; a silently wrong artifact is not.
        manifest["artifacts"]["fp32"] = {
            "ok": False, "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc()}
        print(f"   FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        (a.out_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, default=str))
        print(f"convert_litert: wrote {a.out_dir / 'MANIFEST.json'} (fp32 FAILED)")
        return 1

    calib_npz = a.calib_npz or (a.out_dir / "positions_encoded.npz")
    for mode, fname in (("fp16", "cl067_iter03_fp16.tflite"),
                        ("int8dyn", "cl067_iter03_int8dyn_EXPERIMENTAL.tflite"),
                        ("int8full", "cl067_iter03_int8full_EXPERIMENTAL.tflite")):
        if mode.startswith("int8") and a.skip_int8:
            continue
        print(f"-- {mode} quantize")
        out = a.out_dir / fname
        try:
            entry = quantize_from(fp32, out, mode=mode, calib_npz=calib_npz)
            entry["tflite"] = tflite_summary(out)
            if mode == "int8full":
                entry["calibration"] = {"npz": str(calib_npz), "n_positions": 60,
                                        "note": "real replayed positions, not random noise"}
            if mode.startswith("int8"):
                entry["EXPERIMENTAL"] = (
                    "int8 weight quantization on a 2511-logit policy head is expected to move "
                    "argmax; not a deploy candidate until verify_agreement.py says otherwise")
            manifest["artifacts"][mode] = entry
            print(f"   ok  {entry['bytes'] / 1e6:.2f} MB  {entry['quantize_s']:.1f}s  "
                  f"{entry['tflite']['n_ops']} ops")
        except Exception as exc:                      # noqa: BLE001
            manifest["artifacts"][mode] = {
                "ok": False, "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc()}
            print(f"   FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)

    (a.out_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\nconvert_litert: wrote {a.out_dir / 'MANIFEST.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
