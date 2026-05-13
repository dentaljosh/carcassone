#!/bin/bash
# Bootstrap a vast.ai cloud box for Carcassonne self-play / eval runs.
#
# Usage (on the cloud box, after SSH-ing in):
#   git clone --depth 1 --branch <branch> https://github.com/dentaljosh/carcassone.git /workspace/carcassone
#   bash /workspace/carcassone/scripts/bootstrap_cloud.sh [release_tag]
#
# Default release_tag is `bootstrap-v1` (warmstart_canonical.pt + iter_06.pt).
# Override with a newer tag once we ship one with more checkpoints.
#
# This script is designed to be IDEMPOTENT — safe to re-run if a step fails.
# It uses long pip timeouts and explicit verification at each step.
#
# Lessons baked in from prior bootstrap pain (2026-05-12):
# - Pip's default 30 s read-timeout fails on torch's ~1 GB cu128 wheels; use 600 s.
# - PYTHONPATH may be unset; use ${VAR:-} defaults to survive `set -u`.
# - Box's docker image (pytorch:2.4.0) has Python 3.11; our pyproject.toml requires
#   >=3.12, so `pip install -e .` fails. We use PYTHONPATH for the repo's own code
#   and `pip install -e ./engine` for the vendored engine (engine has no python pin).
# - SSH host can shift between vast.ai proxies (ssh8 vs ssh6) under us; do not cache.
#   This is procedural, not a script fix — re-read `vastai show instance --raw` ssh_host
#   right before each connection from the local side.

set -eo pipefail

REPO_ROOT="${REPO_ROOT:-/workspace/carcassone}"
RELEASE_TAG="${1:-bootstrap-v1}"
GH_REPO="${GH_REPO:-dentaljosh/carcassone}"

echo "=== Cloud bootstrap starting ==="
echo "repo: $GH_REPO"
echo "release: $RELEASE_TAG"
echo "REPO_ROOT: $REPO_ROOT"
echo

if [ ! -d "$REPO_ROOT" ]; then
    echo "ERROR: $REPO_ROOT does not exist. Run this AFTER cloning the repo there." >&2
    echo "  git clone --depth 1 --branch <branch> https://github.com/$GH_REPO.git $REPO_ROOT" >&2
    exit 1
fi

cd "$REPO_ROOT"

# Step 1: Upgrade torch to Blackwell-compatible (sm_120) cu128 wheels.
# Skip if torch is already >= 2.7 — happens on re-runs.
need_torch_upgrade=$(python -c "
import sys
try:
    import torch
    v = torch.__version__.split('+')[0]
    major, minor = int(v.split('.')[0]), int(v.split('.')[1])
    sys.exit(0 if (major, minor) < (2, 7) else 1)
except ImportError:
    sys.exit(0)
" && echo "yes" || echo "no")

if [ "$need_torch_upgrade" = "yes" ]; then
    echo "=== Step 1/4: Upgrade torch to cu128 (sm_120 wheels) ==="
    pip install --upgrade --timeout 600 \
        --index-url https://download.pytorch.org/whl/cu128 \
        torch torchvision torchaudio 2>&1 | tail -8
else
    echo "=== Step 1/4: torch already >= 2.7 — skipping upgrade ==="
fi

python -c "
import torch
v = torch.__version__
cuda_ok = torch.cuda.is_available()
dev = torch.cuda.get_device_name(0) if cuda_ok else None
print(f'  torch={v} cuda={cuda_ok} dev={dev}')
assert cuda_ok, 'CUDA not available — wrong wheel or driver issue'
torch.zeros(1).cuda()
print('  GPU tensor alloc OK')
"

# Step 2: Install vendored engine (wingedsheep) as an editable package.
echo "=== Step 2/4: Install vendored engine (wingedsheep) ==="
pip install -e ./engine 2>&1 | tail -3
python -c "from wingedsheep.carcassonne.objects.meeple_type import MeepleType; print('  engine import OK')"

# Step 3: Install non-torch requirements. Skip the torch line (already handled).
echo "=== Step 3/4: Install non-torch requirements ==="
grep -v "^torch" requirements.txt | pip install --timeout 300 -r /dev/stdin 2>&1 | tail -3

# Step 4: Pull bootstrap checkpoints from the GH release. Direct HTTP to github.com,
# NOT via vast.ai SSH proxy — full bandwidth.
echo "=== Step 4/5: Pull checkpoints from GH release $RELEASE_TAG ==="
mkdir -p checkpoints
cd checkpoints
for asset in warmstart_canonical.pt iter_06.pt; do
    if [ ! -f "$asset" ]; then
        echo "  downloading $asset…"
        curl -sSL --retry 3 --retry-delay 5 -o "$asset" \
            "https://github.com/$GH_REPO/releases/download/$RELEASE_TAG/$asset"
    else
        echo "  $asset already present — skipping download"
    fi
done
ls -la *.pt
cd "$REPO_ROOT"

# Step 5: Pull the heuristic warmstart training dataset. Required at iter 0 of
# any phase-4 recipe with --warmstart-mix-fraction > 0 (which is every recipe
# we've shipped). Without this, train_iter.py crashes with "no training files
# found (buffer empty + no warmstart mix)" — discovered the hard way on the v6
# launch 2026-05-13 after 16 min of wasted self-play.
echo "=== Step 5/5: Pull warmstart training dataset from GH release ==="
mkdir -p data/warmstart
cd data/warmstart
if [ -d heuristic_tau05 ] && [ "$(ls heuristic_tau05 2>/dev/null | wc -l)" -ge 10000 ]; then
    echo "  heuristic_tau05/ already present ($(ls heuristic_tau05 | wc -l) files) — skipping"
else
    echo "  downloading heuristic_tau05.tar (~92 MB)…"
    curl -sSL --retry 3 --retry-delay 5 -o heuristic_tau05.tar \
        "https://github.com/$GH_REPO/releases/download/$RELEASE_TAG/heuristic_tau05.tar"
    echo "  extracting…"
    tar -xf heuristic_tau05.tar
    rm heuristic_tau05.tar
    echo "  done: $(ls heuristic_tau05 | wc -l) files"
fi
cd "$REPO_ROOT"

# Final sanity: load a checkpoint via the project code path.
echo "=== Sanity: load a checkpoint via project code ==="
PYTHONPATH="$REPO_ROOT/src:${PYTHONPATH:-}" python -c "
import torch
ckpt = torch.load('checkpoints/warmstart_canonical.pt', map_location='cpu', weights_only=False)
from carcassonne_ai.network import CarcassonneNet
net = CarcassonneNet(n_filters=ckpt['n_filters'], n_blocks=ckpt['n_blocks'])
net.load_state_dict(ckpt['model_state'])
print(f'  CarcassonneNet({ckpt[\"n_filters\"]}x{ckpt[\"n_blocks\"]}) loaded OK')
"

# Add PYTHONPATH to root's bashrc so future SSH sessions inherit it.
# Idempotent: only add if not already present.
if ! grep -q "PYTHONPATH=$REPO_ROOT/src" /root/.bashrc 2>/dev/null; then
    echo "export PYTHONPATH=$REPO_ROOT/src:\${PYTHONPATH:-}" >> /root/.bashrc
    echo "  added PYTHONPATH to /root/.bashrc"
fi

echo
echo "=== BOOTSTRAP DONE ==="
echo "Next: launch your run with PYTHONPATH set:"
echo "  cd $REPO_ROOT && PYTHONPATH=$REPO_ROOT/src python -u scripts/<your_script>.py [args]"
echo "Or just source /root/.bashrc (new SSH sessions inherit it automatically)."
