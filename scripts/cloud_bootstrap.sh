#!/usr/bin/env bash
# Cloud-side bootstrap for vast.ai 5090 + 48-core EPYC boxes running the
# ghcr.io/dentaljosh/carcassone-cloud:latest image. Pulls the gpu-orchestrator
# branch, installs both packages (carcassonne-ai + vendored wingedsheep),
# verifies GPU + cores. Idempotent — safe to re-run on an existing checkout.
#
# Usage from local:
#   ssh -i ~/.ssh/vast -p <port> root@<host> 'bash -s' < scripts/cloud_bootstrap.sh
#
# AFTER this script:
#   scp -i ~/.ssh/vast -P <port> checkpoints/warmstart_canonical.pt \
#     root@<host>:/workspace/carcassone/checkpoints/
#   # Then launch the actual run (e.g. run_phase4_smoke.py) inside an
#   # nohup ... & disown wrapper per CLAUDE.md SSH-resilience rule.
set -euo pipefail

cd /workspace
if [ ! -d carcassone ]; then
  git clone --depth 1 --branch gpu-orchestrator \
    https://github.com/dentaljosh/carcassone /workspace/carcassone
else
  cd carcassone && git fetch && git checkout gpu-orchestrator && git pull && cd ..
fi
cd /workspace/carcassone

# Both packages must be installed editable. The cloud image has torch+cuda
# but neither carcassonne-ai (this project) nor wingedsheep (vendored engine
# under engine/) is preinstalled. Skipping either gives ModuleNotFoundError
# on the first script run.
pip install -e . 2>&1 | tail -3
pip install -e engine/ 2>&1 | tail -3

mkdir -p checkpoints

echo "=== bootstrap done — git HEAD: $(git rev-parse --short HEAD) ==="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true
echo "nproc=$(nproc)"
python -c "import carcassonne_ai, wingedsheep; print('imports OK')"
