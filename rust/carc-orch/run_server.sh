#!/usr/bin/env bash
# Launch the carc-orch Rust GPU orchestrator against the venv's libtorch.
# Self-contained (no /tmp deps) so it survives reboots and works on any box
# with the same venv layout. LD_PRELOAD of libtorch_cuda.so is REQUIRED: the
# --as-needed linker drops it, so CUDA stays unregistered without it.
set -euo pipefail
DIR=$(dirname "$(readlink -f "$0")")
# §3.1 portability: derive the venv from the repo layout (this script lives at
# <repo>/rust/carc-orch/) and glob python3.* — so it works on the 5800x/xeon
# (/home/doctor/.../.venv, py3.12) AND the laptop (/home/pop/carcassone/.venv,
# py3.11). Override with CARC_VENV. Fail LOUD if torch libs aren't found
# (else LD_PRELOAD points at a nonexistent .so → silent CPU fallback).
VENV="${CARC_VENV:-$(cd "$DIR/../.." && pwd)/.venv}"
TORCHLIB=$(echo "$VENV"/lib/python3.*/site-packages/torch/lib)
if [ ! -d "$TORCHLIB" ]; then
  echo "run_server.sh: torch lib not found under $VENV (set CARC_VENV)" >&2
  exit 1
fi
NVLIBS=$(echo "$VENV"/lib/python3.*/site-packages/nvidia/*/lib | tr ' ' ':')
export LD_LIBRARY_PATH="$TORCHLIB:$NVLIBS:${LD_LIBRARY_PATH:-}"
export LD_PRELOAD="$TORCHLIB/libtorch_cuda.so${LD_PRELOAD:+:$LD_PRELOAD}"
exec "$DIR/target/release/carc-orch" "$@"
