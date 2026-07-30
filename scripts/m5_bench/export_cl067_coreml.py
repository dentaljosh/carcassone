#!/usr/bin/env python3
"""Export the CL-067 distilled net to a CoreML .mlpackage + a provenance sidecar.

THE ARTIFACT THE ANE CELL PLAYS WITH. The equal-wall-clock gate
(``measurement/classical_search/NETPRIOR_EQTIME_GATE_20260728.md`` §6) fixed a reopen
condition of ``r = forward_ms / search_ms_per_sim <= ~1.5``; the ANE is the only
measured path that clears it (0.42 ms batch-1 fp16, r ~ 0.73). This script produces the
model that ``carcassonne_ai.coreml_evaluator`` loads to make that real.

CONVERSION CORE is ``bench_ane_forward.py``'s (trace -> ``ct.convert(convert_to=
"mlprogram")`` -> save), with three deliberate differences, each of which exists
because that script is a LATENCY PROBE and this one produces a MEASUREMENT ARTIFACT:

  1. **POLICY-ONLY by default.** ``bench_ane_forward`` exports ``(policy_logits,
     value)``. The deployed fair-net-prior evaluator never reads the net value — the
     value is the FROZEN champion v2.9 leaf — so exporting the value head buys nothing
     and costs forward time (~5-10%, ``network.forward_policy_only``). ``--head both``
     restores the two-output graph for comparison work.
  2. **Raw LOGITS out, no softmax, no mask.** See ``coreml_evaluator``'s DESIGN
     DECISION 1. Keeping the graph a pure conv+FC stack is also what preserves the
     100%-on-NPU residency that ``ane_coverage_probe.py`` measured.
  3. **Nothing is written until equivalence is PROVEN.** ``assert_wrap_matches``
     compares the export wrapper against the untouched ``CarcassonneNet`` and raises
     rather than emit an artifact that is not the net of record — the same gate
     ``scripts/pixel_npu/convert_litert.py`` puts in front of its LiteRT export.

THE amax REWRITE. The checkpoint has ``value_global_pool=True``, so the VALUE head
computes ``x.amax(dim=(2, 3))``. The LiteRT sibling had to substitute
``F.max_pool2d(x, kernel_size=(H, W)).flatten(1)`` because litert-torch's NHWC pass has
no ``amax`` rewriter (see that file's ``Wrap`` docstring). Max is order-independent, so
the substitution is EXACT, and it is asserted bit-identical before export. Here it is
carried for two reasons even though the default export is policy-only (where the value
head, and therefore ``amax``, is not in the graph at all):

  * ``--head both`` needs it, and CoreML's own ANE placement for a reduce-max over
    spatial dims is not something to discover at measurement time;
  * the sidecar records the equivalence result either way, so the manifest answers
    "was the rewrite applied, and did it hold?" instead of leaving a reader to infer it.

USAGE (macOS with coremltools; conversion also runs on Linux — only ``predict`` is
Darwin-only, so the artifact can be built anywhere and shipped):

    python3 scripts/m5_bench/export_cl067_coreml.py \\
        --checkpoint /mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt \\
        --out-dir /mnt/c/carc-shared/m5_ane_cell/coreml

Writes ``cl067_iter03_policy_fp16.mlpackage`` and ``<name>.manifest.json``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

# The checkpoint of record for CL-067 (sha256 6e2679908d79a76c...), per the gate
# read-out's configuration table. Overridable, but the default is the net the
# +35.7-elo-at-equal-sims claim was measured on.
DEFAULT_CKPT = Path(
    "/mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_tree(path: Path) -> str:
    """Stable digest of a .mlpackage DIRECTORY (name + content, sorted).

    An .mlpackage is a bundle, not a file, so there is no single hash to quote. A
    strength claim has to name the exact artifact that produced it, hence this.
    """
    h = hashlib.sha256()
    for p in sorted(x for x in path.rglob("*") if x.is_file()):
        h.update(str(p.relative_to(path)).encode())
        h.update(sha256_file(p).encode())
    return h.hexdigest()


def _git_rev() -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(REPO), "describe", "--always", "--dirty"],
            capture_output=True, text=True, timeout=10).stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


# --------------------------------------------------------------------------- #
# 1. Load + the export wrapper (conversion core shared with bench_ane_forward)   #
# --------------------------------------------------------------------------- #
def build_net(ckpt_path: Path):
    """Load the checkpoint into a CarcassonneNet with the arch READ FROM the file."""
    sys.path.insert(0, str(REPO / "src"))
    import torch  # noqa: PLC0415

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
    return torch, net, arch, sum(p.numel() for p in net.parameters())


def make_wrapper(torch, net, head: str):
    """Trace-friendly wrapper. ``head="policy"`` -> logits only; ``"both"`` -> +value.

    Re-expresses ``CarcassonneNet.forward`` rather than calling it, for exactly one
    reason: the ``amax`` substitution documented in the module docstring. Everything
    else — same modules, same weights, same order — is the production forward.
    """
    import torch.nn.functional as F  # noqa: N812, PLC0415

    class Wrap(torch.nn.Module):
        def __init__(self, inner, head):
            super().__init__()
            self.inner = inner
            self.head = head

        def forward(self, board, scalars):
            m = self.inner
            x = m.stem(board)
            x = m.trunk(x)

            p = m.policy_project(x).flatten(start_dim=1)
            p = torch.cat([p, scalars], dim=1)
            policy_logits = m.policy_fc(p)
            if self.head == "policy":
                # EXACTLY network.forward_policy_only — the value head's conv,
                # flatten, 2x linear and tanh are not in the graph at all.
                return policy_logits

            v = m.value_project(x).flatten(start_dim=1)
            if m.value_global_pool:
                h, w = x.shape[2], x.shape[3]
                g_mean = x.mean(dim=(2, 3))
                # == x.amax(dim=(2,3)); max is order-independent so this is EXACT.
                g_max = F.max_pool2d(x, kernel_size=(h, w)).flatten(start_dim=1)
                v = torch.cat([v, scalars, g_mean, g_max], dim=1)
            else:
                v = torch.cat([v, scalars], dim=1)
            v = F.relu(m.value_fc1(v))
            return policy_logits, torch.tanh(m.value_fc2(v))

    return Wrap(net, head).eval()


def assert_wrap_matches(torch, net, arch, *, n: int = 8) -> dict:
    """Prove BOTH wrappers are the production forward, before anything is exported.

    Runs the full two-head check unconditionally — i.e. the ``amax`` -> ``max_pool2d``
    substitution is validated on every export, including a policy-only one where the op
    does not appear in the emitted graph. That is on purpose: the substitution is the
    single place this file could silently stop describing the net of record, and a
    check you only run sometimes is a check you cannot cite.
    """
    W = net.window_size
    torch.manual_seed(0)
    board = torch.randn(n, arch["n_input_channels"], W, W)
    scalars = torch.randn(n, arch["n_scalar_features"])

    both = make_wrapper(torch, net, "both")
    policy = make_wrapper(torch, net, "policy")
    with torch.no_grad():
        ref_policy, ref_value = net(board, scalars)
        ref_policy_only = net.forward_policy_only(board, scalars)
        got_policy, got_value = both(board, scalars)
        got_policy_only = policy(board, scalars)

    d_policy = float((ref_policy - got_policy).abs().max())
    d_value = float((ref_value.reshape(-1, 1) - got_value).abs().max())
    d_policy_only = float((ref_policy_only - got_policy_only).abs().max())

    result = {
        "n": n,
        "amax_rewrite_applied": bool(arch["value_global_pool"]),
        "amax_rewrite_reason": (
            "value_global_pool=True: the value head computes x.amax(dim=(2,3)); "
            "F.max_pool2d(kernel=HxW).flatten(1) is the same reduction and converts "
            "cleanly. Max is order-independent so the substitution is EXACT."
            if arch["value_global_pool"] else
            "value_global_pool=False: no amax in this checkpoint's value head; the "
            "rewrite is a no-op and the wrapper is a verbatim re-expression."),
        "policy_max_abs_diff_vs_forward": d_policy,
        "value_max_abs_diff_vs_forward": d_value,
        "policy_only_max_abs_diff_vs_forward_policy_only": d_policy_only,
        "tolerance": 1e-6,
    }
    worst = max(d_policy, d_value, d_policy_only)
    if worst > 1e-6:
        raise RuntimeError(
            "export_cl067_coreml: the export wrapper does NOT match CarcassonneNet "
            f"(policy {d_policy:.3e}, value {d_value:.3e}, policy_only "
            f"{d_policy_only:.3e}). Refusing to export a model that is not the net of "
            "record.")
    result["passed"] = True
    return result


# --------------------------------------------------------------------------- #
# 2. Conversion                                                                 #
# --------------------------------------------------------------------------- #
def convert(torch, wrapped, arch, *, head: str, precision: str, compute_units: str,
            out_path: Path) -> dict:
    try:
        import coremltools as ct  # noqa: PLC0415
    except ImportError:
        raise SystemExit(
            "MISSING DEPENDENCY: coremltools\n"
            "  needed for: torch -> CoreML (.mlpackage) conversion\n"
            "  install   : pip install 'coremltools>=7'\n"
            "  note      : CONVERSION runs anywhere; only predict() needs macOS. The\n"
            "              wrapper-equivalence check above already passed, so the net\n"
            "              is fine — this is purely a missing toolchain.") from None
    import numpy as np  # noqa: PLC0415

    from carcassonne_ai.coreml_evaluator import (  # noqa: PLC0415
        BOARD_INPUT, POLICY_OUTPUT, SCALARS_INPUT,
    )

    W = 25  # window_size; the action space is built for 25x25
    ex_board = torch.randn(1, arch["n_input_channels"], W, W)
    ex_scalars = torch.randn(1, arch["n_scalar_features"])
    with torch.no_grad():
        traced = torch.jit.trace(wrapped, (ex_board, ex_scalars))

    # Batch is FIXED at 1 — the shape the ANE residency and the 0.42 ms were measured
    # at, and the only shape the evaluator ever feeds (the fair-net-prior candidate
    # runs batch_size=1 by construction; see make_fair_net_prior_batch_evaluator).
    inputs = [
        ct.TensorType(name=BOARD_INPUT, shape=ex_board.shape),
        ct.TensorType(name=SCALARS_INPUT, shape=ex_scalars.shape),
    ]
    outputs = ([ct.TensorType(name=POLICY_OUTPUT)] if head == "policy"
               else [ct.TensorType(name=POLICY_OUTPUT), ct.TensorType(name="value")])

    kw = dict(
        inputs=inputs, convert_to="mlprogram",
        compute_units=getattr(ct.ComputeUnit, compute_units),
        compute_precision={"fp16": ct.precision.FLOAT16,
                           "fp32": ct.precision.FLOAT32}[precision])

    # Output NAMING is a convenience, not a contract. Older/newer coremltools differ on
    # whether `outputs=[TensorType(name=...)]` is accepted for a traced model, and this
    # tool cannot be exercised against a real coremltools on the Linux build box. So try
    # to name them, and fall back to whatever the converter picks — the evaluator
    # resolves a sole output positionally (`_resolve_output_name`) and the fallback is
    # RECORDED in the manifest, so nothing is silent either way. What must never happen
    # is the export failing on the Air for a cosmetic reason.
    t0 = time.perf_counter()
    named_outputs = True
    try:
        mlmodel = ct.convert(traced, outputs=outputs, **kw)
    except Exception as exc:  # noqa: BLE001
        named_outputs = f"{type(exc).__name__}: {exc}"
        mlmodel = ct.convert(traced, **kw)
    convert_s = time.perf_counter() - t0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        import shutil  # noqa: PLC0415
        shutil.rmtree(out_path)
    mlmodel.save(str(out_path))

    entry = {
        "path": str(out_path),
        "convert_s": convert_s,
        "precision": precision,
        # compute_units is baked in at CONVERT time as well as bound at LOAD time;
        # both are recorded because a mismatch between them is a silent way to
        # measure a different device than the one you meant.
        "compute_units_at_convert": compute_units,
        "head": head,
        "inputs": {BOARD_INPUT: list(ex_board.shape),
                   SCALARS_INPUT: list(ex_scalars.shape)},
        "outputs_requested": [o.name for o in outputs],
        "outputs_actual": [o.name for o in mlmodel.get_spec().description.output],
        # True, or the exception string explaining why the names did not take.
        "output_naming_ok": named_outputs,
        "coremltools_version": ct.__version__,
        "numpy_version": np.__version__,
    }

    # Round-trip the saved bundle on macOS: a model that converts but does not load or
    # predict is an artifact that will fail on the Air at the worst possible moment.
    if platform.system() == "Darwin":
        try:
            from carcassonne_ai.coreml_evaluator import load_coreml_model  # noqa: PLC0415

            m = load_coreml_model(out_path, compute_units=compute_units)
            feed = {BOARD_INPUT: ex_board.numpy().astype(np.float32),
                    SCALARS_INPUT: ex_scalars.numpy().astype(np.float32)}
            out = m.predict(feed)
            # Fall back to the spec's FIRST output if the rename did not take — the
            # traced wrapper emits policy_logits first in both head modes.
            oname = (POLICY_OUTPUT if POLICY_OUTPUT in out
                     else [o.name for o in m.get_spec().description.output][0])
            got = np.asarray(out[oname]).reshape(-1)
            with torch.no_grad():
                ref = wrapped(ex_board, ex_scalars)
                ref = (ref if head == "policy" else ref[0]).numpy().reshape(-1)
            entry["reload_check"] = {
                "ok": True,
                "outputs": sorted(out),
                "logits_max_abs_diff_vs_torch": float(np.abs(got - ref).max()),
                "argmax_agree": bool(int(got.argmax()) == int(ref.argmax())),
                "note": "ONE random-input sample; the real fidelity gate is "
                        "verify_coreml_evaluator.py on >=60 REAL encoded positions.",
            }
        except Exception as exc:  # noqa: BLE001
            entry["reload_check"] = {"ok": False,
                                     "error": f"{type(exc).__name__}: {exc}"}
    else:
        entry["reload_check"] = {
            "ok": None,
            "skipped": f"CoreML predict needs macOS; this is {platform.system()}. "
                       "The .mlpackage is still valid — run verify_coreml_evaluator.py "
                       "on the Air before citing it.",
        }
    return entry


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--checkpoint", type=Path, default=DEFAULT_CKPT)
    p.add_argument("--out-dir", type=Path, default=HERE / "results" / "coreml")
    p.add_argument("--name", type=str, default=None,
                   help="artifact basename (default cl067_iter03_<head>_<precision>)")
    p.add_argument("--head", choices=("policy", "both"), default="policy",
                   help="policy (default) = what the deployed evaluator reads; both "
                        "adds the value head for comparison work")
    p.add_argument("--precision", choices=("fp16", "fp32"), default="fp16",
                   help="fp16 is what the ANE runs and what r~0.73 was measured at")
    p.add_argument("--compute-units", default="CPU_AND_NE",
                   help="baked at convert time; CPU_AND_NE deliberately excludes the "
                        "GPU, which is a different device from the measured one")
    a = p.parse_args(argv)

    ckpt = a.checkpoint.resolve()
    if not ckpt.is_file():
        raise SystemExit(f"export_cl067_coreml: no such checkpoint: {ckpt}")

    torch, net, arch, n_params = build_net(ckpt)
    print(f"export_cl067_coreml: {ckpt.name}  {n_params / 1e6:.2f} M params  "
          f"{arch['n_filters']}x{arch['n_blocks']}  "
          f"{arch['n_input_channels']}ch/{arch['n_scalar_features']}sc  "
          f"value_global_pool={arch['value_global_pool']}")

    print("-- proving the export wrapper == CarcassonneNet.forward")
    equiv = assert_wrap_matches(torch, net, arch)
    print(f"   amax rewrite applied={equiv['amax_rewrite_applied']}  "
          f"policy {equiv['policy_max_abs_diff_vs_forward']:.3e}  "
          f"value {equiv['value_max_abs_diff_vs_forward']:.3e}  "
          f"policy_only {equiv['policy_only_max_abs_diff_vs_forward_policy_only']:.3e}"
          "  -> PASS")

    name = a.name or f"cl067_iter03_{a.head}_{a.precision}"
    out_path = a.out_dir.resolve() / f"{name}.mlpackage"
    print(f"-- converting ({a.head}, {a.precision}, {a.compute_units}) -> {out_path}")
    conv = convert(torch, make_wrapper(torch, net, a.head), arch, head=a.head,
                   precision=a.precision, compute_units=a.compute_units,
                   out_path=out_path)

    manifest = {
        "schema": "carcassonne-coreml-export/v1",
        "kind": "cl067_netprior_policy_forward",
        "claim": "CL-067",
        "purpose": "the forward path for the M5/ANE equal-wall-clock cell; the reopen "
                   "condition r = forward_ms / search_ms_per_sim <= ~1.5 from "
                   "measurement/classical_search/NETPRIOR_EQTIME_GATE_20260728.md §6",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "code_rev": _git_rev(),
        "machine": {"platform": platform.platform(), "machine": platform.machine(),
                    "python": sys.version.split()[0], "node": platform.node()},
        "source_checkpoint": {
            "path": str(ckpt),
            "sha256": sha256_file(ckpt),
            "arch": arch,
            "n_params": int(n_params),
        },
        "converter_versions": {
            "torch": torch.__version__,
            "coremltools": conv["coremltools_version"],
            "numpy": conv["numpy_version"],
            "python": sys.version.split()[0],
        },
        "export_wrapper_equivalence": equiv,
        "artifact": {**conv, "sha256_tree": sha256_tree(out_path)},
        "mask_and_softmax": (
            "NOT in the graph. The model emits raw policy logits; "
            "carcassonne_ai.coreml_evaluator.masked_softmax_np applies "
            "masked_fill(-inf)+softmax host-side in float32. See that module's DESIGN "
            "DECISION 1 for why (fp16 faithfulness, on-NPU residency, transport, "
            "attributable error budget)."),
        "acceptance": (
            "This manifest proves the artifact IS the checkpoint. It does NOT prove the "
            "ANE reproduces it — run scripts/m5_bench/verify_coreml_evaluator.py on the "
            "Air (>=60 real encoded positions) and cite THAT before the cell."),
    }
    man_path = out_path.with_suffix(".manifest.json")
    man_path.write_text(json.dumps(manifest, indent=2, default=str))
    print(f"   sha256(tree) {manifest['artifact']['sha256_tree'][:16]}...  "
          f"convert {conv['convert_s']:.1f}s")
    rc = conv.get("reload_check", {})
    if rc.get("ok"):
        print(f"   reload+predict OK  logits max|d| vs torch "
              f"{rc['logits_max_abs_diff_vs_torch']:.3e}  argmax_agree={rc['argmax_agree']}")
    elif rc.get("ok") is False:
        print(f"   reload+predict FAILED: {rc['error']}", file=sys.stderr)
    else:
        print(f"   reload+predict skipped ({platform.system()})")
    print(f"\nexport_cl067_coreml: wrote {out_path}\n"
          f"export_cl067_coreml: wrote {man_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
