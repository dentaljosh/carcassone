#!/usr/bin/env bash
# eff_linus round 3 — provision the Pop!_OS arm. Mirrors the round-2 WSL arm:
# CPython 3.13.14 exactly (uv / python-build-standalone), numpy 2.5.1, pyyaml 6.0.3.
set -euo pipefail
cd /home/pop

echo "=== DNS/net check ==="
getent hosts astral.sh || echo "DNS FAIL astral.sh"
curl -sS -o /dev/null -w 'astral.sh %{http_code}\n' https://astral.sh/uv/install.sh || echo "HTTPS FAIL"

echo "=== df before ==="
df -h / | tail -1

mkdir -p /home/pop/carc-pop-bench

if ! command -v uv >/dev/null 2>&1 && [ ! -x /home/pop/.local/bin/uv ]; then
  echo "=== installing uv ==="
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="/home/pop/.local/bin:$PATH"
uv --version

echo "=== uv python install 3.13.14 ==="
uv python install 3.13.14
uv python list --only-installed

echo "=== venv ==="
cd /home/pop/carc-pop-bench
uv venv --python 3.13.14 .venv
./.venv/bin/python -VV

echo "=== deps (exact round-2 versions) ==="
uv pip install --python /home/pop/carc-pop-bench/.venv/bin/python numpy==2.5.1 pyyaml==6.0.3

./.venv/bin/python -c "import sys,numpy,yaml,platform;print('py',sys.version);print('numpy',numpy.__version__);print('yaml',yaml.__version__);print('platform',platform.platform())"

echo "=== df after ==="
df -h / | tail -1
du -sh /home/pop/.local/share/uv 2>/dev/null || true
du -sh /home/pop/carc-pop-bench/.venv 2>/dev/null || true
echo "PROVISION_OK"
