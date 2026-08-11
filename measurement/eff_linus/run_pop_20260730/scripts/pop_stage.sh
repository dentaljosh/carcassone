#!/usr/bin/env bash
# Stage the Pop arm: M5 bundle (champ cells) + pysrc @ 17ba2ce (net cells).
set -euo pipefail
cd /home/pop

echo "=== extract M5 bundle ==="
mkdir -p /home/pop/carc-pop-bench
tar -C /home/pop/carc-pop-bench -xzf /home/pop/m5_bench.tgz
ls /home/pop/carc-pop-bench/m5_bench_20260728/
echo "positions md5: $(md5sum /home/pop/carc-pop-bench/m5_bench_20260728/bundle/positions.jsonl)"
echo "ckpt sha256:   $(sha256sum /home/pop/carc-pop-bench/m5_bench_20260728/bundle/net/distill_iter_03.pt)"
echo "any .so in bundle? $(find /home/pop/carc-pop-bench/m5_bench_20260728 -name '*.so' | wc -l) (want 0 => pure-python leaf guaranteed)"

echo "=== clone git bundle (no checkout) ==="
rm -rf /home/pop/carc-repo
git clone --no-checkout --quiet /home/pop/carc_head.bundle /home/pop/carc-repo
git -C /home/pop/carc-repo log --oneline -1 FETCH_HEAD 2>/dev/null || true
git -C /home/pop/carc-repo rev-parse HEAD

echo "=== extract pysrc @ 17ba2ce (the exact rev round-2's WSL arm staged) ==="
git -C /home/pop/carc-repo checkout 17ba2ce -- src/carcassonne_ai engine/wingedsheep scripts/measurement_infra
mkdir -p /home/pop/carc-pop-bench/stage/pysrc
rsync -a --delete --exclude '__pycache__/' --exclude '*.so' --exclude '*.pyd' \
      --exclude '*.c' --exclude '*.pyc' \
      /home/pop/carc-repo/src/carcassonne_ai/ /home/pop/carc-pop-bench/stage/pysrc/carcassonne_ai/
rsync -a --delete --exclude '__pycache__/' --exclude '*.so' --exclude '*.pyd' \
      --exclude '*.c' --exclude '*.pyc' \
      /home/pop/carc-repo/engine/wingedsheep/ /home/pop/carc-pop-bench/stage/pysrc/wingedsheep/
cp /home/pop/carc-repo/scripts/measurement_infra/net_transport_bench.py /home/pop/carc-pop-bench/stage/net_transport_bench.py
echo "staged files: $(find /home/pop/carc-pop-bench/stage/pysrc -type f | wc -l)"
echo "PYSRC_MANIFEST_SHA: $(find /home/pop/carc-pop-bench/stage/pysrc -type f -name '*.py' | sort | xargs sha256sum | sha256sum)"
echo "NET_BENCH_SHA: $(sha256sum /home/pop/carc-pop-bench/stage/net_transport_bench.py)"

echo "=== free the bundle file ==="
rm -f /home/pop/carc_head.bundle /home/pop/m5_bench.tgz
df -h / | tail -1
echo "STAGE_OK"
