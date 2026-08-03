#!/bin/bash
# Point `ort-sys` at a CUDA-12 onnxruntime and put CUDA-12 runtime libs on the
# loader path. `source` this before any `cargo build` / `cargo run` in carc-net.
#
# ═══ WHY THIS FILE EXISTS ═══════════════════════════════════════════════════
#
# 1. THE LINK ERROR. `carc-net`'s `ort` dependency deliberately does NOT enable
#    the `download-binaries` feature, so `ort-sys` has no ONNX Runtime to link
#    against and the crate fails with
#
#        rust-lld: error: undefined symbol: OrtGetApiBase
#
#    ...for every binary in the crate. This is not a code fault and no source
#    change fixes it: it is a missing `ORT_LIB_LOCATION`. The fix is entirely in
#    the environment, which is exactly why it belongs in a checked-in script
#    instead of a session's shell history.
#
# 2. WHY NOT JUST ENABLE `download-binaries`. Because it is the trap the design
#    memo (`docs/RUST_NET_EVAL_DESIGN_20260802.md` §4b) was written around:
#    `ort` 2.0.0-rc.13's bundled onnxruntime is built against CUDA **13**
#    (libcudart.so.13, libcublas.so.13). This box has CUDA **12** only, via
#    torch's `nvidia-*` pip packages. The version gap does NOT raise — ORT logs
#    a provider-load failure and SILENTLY FALLS BACK TO CPU, so a row labelled
#    "cuda" measures the CPU. That fail-open produced the memo's bogus first
#    reading (cuda == cuda+graph == roughly cpu(8)). Pinning the library is the
#    load-bearing half of tier T3; `.error_on_failure()` in `lib.rs` is the
#    other half.
#
# 3. WHY `ORT_PREFER_DYNAMIC_LINK`. `ort-sys` defaults to STATIC linking against
#    `ORT_LIB_LOCATION`; the onnxruntime-gpu wheel ships shared objects only, so
#    dynamic linking has to be requested explicitly or the build script fails
#    with "could not link to the ONNX Runtime build in ...".
#
# ═══ PROVISIONING ═══════════════════════════════════════════════════════════
#
# `$ORT_DIST` is just the `onnxruntime/capi/` directory of an onnxruntime-gpu
# 1.22.0 wheel (CUDA-12 build), with the usual soname symlinks:
#
#     python3 -m venv /tmp/onnxvenv
#     /tmp/onnxvenv/bin/pip install onnxruntime-gpu==1.22.0
#     mkdir -p "$ORT_DIST"
#     cp /tmp/onnxvenv/lib/python3.*/site-packages/onnxruntime/capi/libonnxruntime*.so* "$ORT_DIST"/
#     ln -sf libonnxruntime.so.1.22.0 "$ORT_DIST/libonnxruntime.so"
#     ln -sf libonnxruntime.so.1.22.0 "$ORT_DIST/libonnxruntime.so.1"
#
# ⚠️ An `ort` upgrade and an onnxruntime upgrade are ONE change, not two: rc.13
# expects the 1.22 ABI, and mixing them produces silent option rejections (the
# `graph_optimization_level is not valid` failure noted in `lib.rs`).

: "${ORT_DIST:?set ORT_DIST to a directory holding a CUDA-12 libonnxruntime.so (see header)}"
CARC_VENV="${CARC_VENV:-/home/doctor/projects/carcassone/.venv}"
NV="$CARC_VENV/lib/python3.12/site-packages/nvidia"

export ORT_LIB_LOCATION="$ORT_DIST"
export ORT_PREFER_DYNAMIC_LINK=1
export LD_LIBRARY_PATH="$ORT_DIST:$NV/cublas/lib:$NV/cuda_runtime/lib:$NV/curand/lib:$NV/cufft/lib:$NV/cudnn/lib:$NV/cuda_nvrtc/lib:${LD_LIBRARY_PATH:-}"
