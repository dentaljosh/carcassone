#!/usr/bin/env python3
"""Desktop verification: LiteRT CPU interpreter vs torch fp32, for the CL-067 .tflite artifacts.

    python verify_agreement.py --out-dir /mnt/c/carc-shared/pixel_npu_20260729

⚠️ READ THIS BEFORE QUOTING ANY NUMBER FROM THIS SCRIPT.

**This measures CPU-INTERPRETER agreement, and nothing else.** It answers "did the torch -> LiteRT
conversion preserve the function?" It does NOT answer "will the Pixel's GPU or NPU produce these
outputs". A delegate is free to reassociate float arithmetic, run fp16 accumulation, fuse ops
differently, or fall back to CPU for part of the graph -- so **delegate agreement can only be
measured on-device**, by re-running this comparison against outputs captured from the phone. A
clean bill of health here is a necessary condition for trusting the artifact, never a sufficient
one. The runbook (`phone_bench/RUNBOOK_PIXEL.md`) is where the on-device half lives.

WHAT IS COMPARED

  (a) random inputs -- N(0,1) boards and scalars. Wide dynamic range, exercises the arithmetic,
      but is off-distribution: a real board is ~93% zeros.
  (b) REAL encoded positions -- 60 of them, replayed by `encode_positions.py` from the frozen M5
      bundle's `positions.jsonl` and encoded through the same sighted (81ch/42-scalar) encoder the
      deployed evaluator uses. These carry their LEGAL-MOVE MASKS, which is the point: the policy
      head has 2511 logits but a real position has ~11 legal moves, so argmax over all 2511 is a
      much easier test than argmax over the legal set. **The legal-masked argmax is the headline
      metric** -- it is the move the agent would actually play.

Both are reported separately and neither is allowed to stand in for the other.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

DEFAULT_BUNDLE = Path("/mnt/c/carc-shared/m5_bench_20260728/bundle")
DEFAULT_CKPT = Path("/mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# Reference: torch fp32                                                         #
# --------------------------------------------------------------------------- #
def torch_reference(bundle: Path, ckpt: Path, boards: np.ndarray, scalars: np.ndarray):
    """Run the UNMODIFIED CarcassonneNet.forward -- amax and all.

    Deliberately NOT the export wrapper from convert_litert.py. The wrapper substitutes one op to
    get past a converter limitation; if that substitution were wrong, comparing the .tflite back
    against the wrapper would agree beautifully and still be measuring the wrong function. The
    reference here is the production forward.
    """
    sys.path.insert(0, str(bundle))
    import torch

    from carcassonne_ai.network import CarcassonneNet  # noqa: PLC0415

    torch.set_num_threads(1)
    ck = torch.load(ckpt, map_location="cpu", weights_only=False)
    arch = {
        "n_filters": int(ck["n_filters"]), "n_blocks": int(ck["n_blocks"]),
        "n_input_channels": int(ck.get("n_input_channels", 78)),
        "n_scalar_features": int(ck.get("n_scalar_features", 10)),
        "value_global_pool": bool(ck.get("value_global_pool", False)),
    }
    net = CarcassonneNet(**arch).eval()
    net.load_state_dict(ck["model_state"])

    pol, val = [], []
    with torch.no_grad():
        for i in range(boards.shape[0]):
            b = torch.from_numpy(boards[i:i + 1])
            s = torch.from_numpy(scalars[i:i + 1])
            p, v = net(b, s)
            pol.append(p.numpy().reshape(-1))
            val.append(float(v.reshape(-1)[0]))
    return np.stack(pol), np.array(val, dtype=np.float64), arch, torch.__version__


# --------------------------------------------------------------------------- #
# Candidate: LiteRT CPU interpreter                                             #
# --------------------------------------------------------------------------- #
def litert_run(tflite: Path, boards: np.ndarray, scalars: np.ndarray):
    from ai_edge_litert.interpreter import Interpreter

    interp = Interpreter(model_path=str(tflite), num_threads=1)
    interp.allocate_tensors()
    ins = interp.get_input_details()
    outs = interp.get_output_details()

    # Bind inputs by SHAPE, not by name or index: the converter names them after the traced
    # arg names, and the ordering is not contractual across toolchain versions. Binding by the
    # 4-D/2-D distinction is unambiguous for this model and cannot silently swap.
    board_in = next(d for d in ins if len(d["shape"]) == 4)
    scalar_in = next(d for d in ins if len(d["shape"]) == 2)
    if len(ins) != 2:
        raise SystemExit(f"verify_agreement: expected 2 inputs, got {len(ins)}")

    action_size = boards.shape[0] and None  # placeholder; resolved from the output shapes below
    policy_out = max(outs, key=lambda d: int(np.prod(d["shape"])))
    value_out = min(outs, key=lambda d: int(np.prod(d["shape"])))
    if policy_out["index"] == value_out["index"]:
        raise SystemExit("verify_agreement: could not tell the policy output from the value "
                         "output by size; inspect the model's output details by hand")
    del action_size

    def _quantize_in(detail, arr: np.ndarray) -> np.ndarray:
        """A full-integer graph takes int8/uint8 tensors, not floats.

        The affine params live in the tensor detail. Quantizing here (rather than refusing the
        model) is what an app would do at the boundary, so the agreement number we report
        includes the input-quantization error -- which is honest: that error is real and
        unavoidable for this artifact.
        """
        dt = detail["dtype"]
        if dt == np.float32:
            return arr.astype(np.float32)
        scale, zero = detail["quantization"]
        if scale == 0:
            raise SystemExit(f"verify_agreement: input {detail['name']} is {dt} but carries no "
                             "quantization scale; cannot feed it faithfully")
        info = np.iinfo(dt)
        q = np.round(arr / scale + zero)
        return np.clip(q, info.min, info.max).astype(dt)

    def _dequantize_out(detail, arr: np.ndarray) -> np.ndarray:
        if detail["dtype"] == np.float32:
            return arr.astype(np.float64)
        scale, zero = detail["quantization"]
        return (arr.astype(np.float64) - zero) * scale

    quantized_io = any(d["dtype"] != np.float32 for d in ins + outs)

    pol, val = [], []
    for i in range(boards.shape[0]):
        interp.set_tensor(board_in["index"], _quantize_in(board_in, boards[i:i + 1]))
        interp.set_tensor(scalar_in["index"], _quantize_in(scalar_in, scalars[i:i + 1]))
        interp.invoke()
        pol.append(_dequantize_out(
            policy_out, interp.get_tensor(policy_out["index"])).reshape(-1))
        val.append(float(_dequantize_out(
            value_out, interp.get_tensor(value_out["index"])).reshape(-1)[0]))
    return np.stack(pol), np.array(val, dtype=np.float64), {
        "inputs": [{"name": d["name"], "shape": [int(x) for x in d["shape"]],
                    "dtype": str(np.dtype(d["dtype"])), "quantization": list(d["quantization"])}
                   for d in ins],
        "outputs": [{"name": d["name"], "shape": [int(x) for x in d["shape"]],
                     "dtype": str(np.dtype(d["dtype"])), "quantization": list(d["quantization"])}
                    for d in outs],
        "quantized_io": bool(quantized_io),
    }


# --------------------------------------------------------------------------- #
# Comparison                                                                    #
# --------------------------------------------------------------------------- #
def _masked_softmax(logits: np.ndarray, mask: np.ndarray) -> np.ndarray:
    z = np.where(mask, logits, -np.inf)
    z = z - z.max()
    e = np.exp(z)
    return e / e.sum()


def compare(ref_p, ref_v, got_p, got_v, legal: np.ndarray | None, *, topk: int = 5) -> dict:
    n = ref_p.shape[0]
    out: dict = {
        "n": int(n),
        "value_max_abs_dev": float(np.abs(ref_v - got_v).max()),
        "value_mean_abs_dev": float(np.abs(ref_v - got_v).mean()),
        "policy_logit_max_abs_dev": float(np.abs(ref_p - got_p).max()),
        "policy_logit_mean_abs_dev": float(np.abs(ref_p - got_p).mean()),
        "argmax_agree_all_logits": float((ref_p.argmax(1) == got_p.argmax(1)).mean()),
    }
    if legal is None:
        out["legal_masked"] = None
        return out

    agree, top_overlap, prob_dev, disagreements = 0, [], [], []
    for i in range(n):
        m = legal[i]
        nl = int(m.sum())
        idx = np.flatnonzero(m)
        r_best = idx[ref_p[i][idx].argmax()]
        g_best = idx[got_p[i][idx].argmax()]
        if r_best == g_best:
            agree += 1
        else:
            disagreements.append({
                "i": int(i), "n_legal": nl,
                "ref_action": int(r_best), "got_action": int(g_best),
                # How much did we give up? If the two top moves were near-tied in the reference,
                # a flip is cheap; if they were far apart, it is a real behaviour change.
                "ref_logit_gap": float(ref_p[i][r_best] - ref_p[i][g_best]),
            })
        k = min(topk, nl)
        r_top = set(idx[np.argsort(-ref_p[i][idx])[:k]].tolist())
        g_top = set(idx[np.argsort(-got_p[i][idx])[:k]].tolist())
        top_overlap.append(len(r_top & g_top) / k)
        prob_dev.append(float(np.abs(_masked_softmax(ref_p[i], m)
                                     - _masked_softmax(got_p[i], m)).max()))
    out["legal_masked"] = {
        "argmax_agree": agree / n,
        "argmax_agree_count": f"{agree}/{n}",
        f"top{topk}_overlap_mean": float(np.mean(top_overlap)),
        f"top{topk}_overlap_min": float(np.min(top_overlap)),
        "masked_prob_max_abs_dev": float(np.max(prob_dev)),
        "masked_prob_mean_abs_dev": float(np.mean(prob_dev)),
        "disagreements": disagreements[:20],
    }
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out-dir", type=Path, required=True,
                   help="dir holding the .tflite artifacts; the report is written here too")
    p.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    p.add_argument("--checkpoint", type=Path, default=DEFAULT_CKPT)
    p.add_argument("--positions-npz", type=Path, default=None,
                   help="default: <out-dir>/positions_encoded.npz (from encode_positions.py)")
    p.add_argument("--n-random", type=int, default=32)
    p.add_argument("--topk", type=int, default=5)
    a = p.parse_args(argv)

    tflites = sorted(a.out_dir.glob("cl067_iter03_*.tflite"))
    if not tflites:
        raise SystemExit(f"verify_agreement: no cl067_iter03_*.tflite under {a.out_dir}; "
                         "run convert_litert.py first")

    npz_path = a.positions_npz or (a.out_dir / "positions_encoded.npz")
    if not npz_path.is_file():
        raise SystemExit(
            f"verify_agreement: no encoded positions at {npz_path}.\n"
            "  Produce them first (needs the frozen M5 bundle, NOT the live tree):\n"
            "    PYTHONPATH=/mnt/c/carc-shared/m5_bench_20260728/bundle \\\n"
            "      python3 scripts/pixel_npu/encode_positions.py --out <that path>")
    z = np.load(npz_path, allow_pickle=False)
    real_boards, real_scalars = z["boards"], z["scalars"]
    real_legal = z["legal"] if "legal" in z.files else None
    pos_prov = json.loads(str(z["provenance"]))

    rng = np.random.default_rng(0)
    rnd_boards = rng.standard_normal(
        (a.n_random, *real_boards.shape[1:])).astype(np.float32)
    rnd_scalars = rng.standard_normal((a.n_random, real_scalars.shape[1])).astype(np.float32)

    print(f"verify_agreement: {len(tflites)} artifact(s); "
          f"{a.n_random} random + {real_boards.shape[0]} real positions")

    all_boards = np.concatenate([rnd_boards, real_boards])
    all_scalars = np.concatenate([rnd_scalars, real_scalars])
    t0 = time.perf_counter()
    ref_p, ref_v, arch, torch_ver = torch_reference(
        a.bundle.resolve(), a.checkpoint.resolve(), all_boards, all_scalars)
    print(f"  torch fp32 reference: {all_boards.shape[0]} forwards in "
          f"{time.perf_counter() - t0:.1f}s")

    nr = a.n_random
    report = {
        "schema": "carcassonne-pixel-npu/v1",
        "kind": "litert_cpu_interpreter_agreement",
        "claim": "CL-067",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scope_warning": (
            "CPU-INTERPRETER agreement only. GPU/NNAPI/NPU delegates may reassociate float "
            "arithmetic or partially fall back to CPU; delegate agreement can ONLY be measured "
            "on-device."),
        "reference": {"impl": "torch fp32 CarcassonneNet.forward (unmodified, incl. amax)",
                      "torch": torch_ver, "arch": arch,
                      "checkpoint_sha256": sha256_file(a.checkpoint.resolve())},
        "positions_provenance": pos_prov,
        "machine": {"platform": platform.platform(), "python": sys.version.split()[0],
                    "numpy": np.__version__},
        "artifacts": {},
    }

    for tf in tflites:
        label = tf.stem.replace("cl067_iter03_", "")
        print(f"-- {label}")
        try:
            got_p, got_v, io = litert_run(tf, all_boards, all_scalars)
        except Exception as exc:                       # noqa: BLE001
            report["artifacts"][label] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            print(f"   FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        entry = {
            "ok": True, "path": str(tf), "sha256": sha256_file(tf),
            "bytes": tf.stat().st_size, "io": io,
            "random_inputs": compare(ref_p[:nr], ref_v[:nr], got_p[:nr], got_v[:nr],
                                     None, topk=a.topk),
            "real_positions": compare(ref_p[nr:], ref_v[nr:], got_p[nr:], got_v[nr:],
                                      real_legal, topk=a.topk),
        }
        report["artifacts"][label] = entry
        r, q = entry["random_inputs"], entry["real_positions"]
        lm = q["legal_masked"]
        print(f"   random : value max|d| {r['value_max_abs_dev']:.3e}   "
              f"policy max|d| {r['policy_logit_max_abs_dev']:.3e}   "
              f"argmax(all) {r['argmax_agree_all_logits'] * 100:.1f}%")
        print(f"   real   : value max|d| {q['value_max_abs_dev']:.3e}   "
              f"policy max|d| {q['policy_logit_max_abs_dev']:.3e}")
        if lm:
            print(f"   real   : LEGAL argmax {lm['argmax_agree_count']} "
                  f"({lm['argmax_agree'] * 100:.1f}%)   "
                  f"top{a.topk} overlap {lm[f'top{a.topk}_overlap_mean'] * 100:.1f}%   "
                  f"masked-prob max|d| {lm['masked_prob_max_abs_dev']:.3e}")

    stamp = time.strftime("%Y%m%dT%H%M%S")
    out = a.out_dir / f"verify_agreement_{stamp}.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nverify_agreement: wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
