#!/usr/bin/env bash
# Vast.ai runbook for renting a CPU-heavy box and running Phase 4 self-play.
#
# Don't run this top-to-bottom. Each step is meant to be executed manually
# after verifying the previous step's output. Re-search at launch time —
# offers churn hourly.
#
# Pre-req: `vastai set api-key ...` already configured (we have it).

set -euo pipefail

# ────────────────────────────────────────────────────────────────────────
# STEP 1 — Verify CLI + balance
# ────────────────────────────────────────────────────────────────────────
# vastai show user --raw | jq '{credit, username}'
# Expect: credit > $0.83 for a 30-iter sanity run (~12hr at $0.069/hr).
# Expect: credit > $20  for a 200-iter prod run  (~30hr at $0.482/hr).

# ────────────────────────────────────────────────────────────────────────
# STEP 2 — Search offers. Filter on EFFECTIVE cores, not total cores —
#         multi-tenant boxes will list 64+ cores but only give us a slice.
# ────────────────────────────────────────────────────────────────────────
# For 30-iter sanity (cheap):
#   vastai search offers \
#     'cpu_cores_effective>=16 dph_total<0.10 reliability>0.97 verified=True \
#      rentable=True inet_down>=100 cuda_max_good>=12.0' \
#     --order 'dph_total asc' --raw
#
# For 200-iter prod (max throughput):
#   vastai search offers \
#     'cpu_cores_effective>=32 dph_total<0.50 reliability>0.97 verified=True \
#      rentable=True inet_down>=100 cuda_max_good>=12.0' \
#     --order 'dph_total asc' --raw
#
# Pipe through this to print a readable table:
#   ... --raw | python3 -c "
#     import json, sys
#     for o in json.loads(sys.stdin.read())[:15]:
#         print(f\"  \${o['dph_total']:.3f}/hr  {o['cpu_cores_effective']:>5.1f}eff/{o['cpu_cores']}tot  \"
#               f\"{o['cpu_name'][:30]:30}  {o['gpu_name'][:22]:22}  {o['cpu_ram']/1024:>3.0f}GB  id={o['id']}\")"

# Decision criteria when picking from the list:
#   - per-core speed (newer CPU > older): EPYC Rome/Milan/Genoa > Xeon Skylake/Cascade > Xeon Broadwell
#   - effective cores high (≥16 = beats local 5800X)
#   - GPU just needs ≥4GB VRAM and CUDA 12 — RTX 3060/3070/4060 all fine; old P4000 also works
#   - reliability ≥0.97 to avoid flaky hosts
#   - inet_down ≥100 Mbps so SCP is bearable

# ────────────────────────────────────────────────────────────────────────
# STEP 3 — Create instance (replace OFFER_ID with the chosen id)
# ────────────────────────────────────────────────────────────────────────
# OFFER_ID=35441078     # example: EPYC 7502 + RTX 3070 @ $0.069/hr
# vastai create instance "$OFFER_ID" \
#   --image pytorch/pytorch:2.4.0-cuda12.1-cudnn9-runtime \
#   --disk 100 \
#   --ssh \
#   --label phase4-selfplay
#
# Returns: {"new_contract": <INSTANCE_ID>}
# Save the INSTANCE_ID — you'll use it for everything below.
# INSTANCE_ID=<from above>

# ────────────────────────────────────────────────────────────────────────
# STEP 4 — Wait for instance to come up (status=running, ssh ready)
# ────────────────────────────────────────────────────────────────────────
# vastai show instance "$INSTANCE_ID" --raw | jq '{actual_status, ssh_host, ssh_port}'
# Repeat until actual_status=="running" and ssh_host is non-null (~30-90s).

# ────────────────────────────────────────────────────────────────────────
# STEP 5 — SSH in and bootstrap
# ────────────────────────────────────────────────────────────────────────
# vastai ssh-url "$INSTANCE_ID"  # prints ssh://root@HOST:PORT
# Use that with: ssh -p PORT root@HOST
#
# Once in:
#   apt-get install -y git rsync       # usually already there
#   nvidia-smi                          # confirm CUDA is up
#   python -c "import torch; print(torch.cuda.is_available())"  # expect True

# ────────────────────────────────────────────────────────────────────────
# STEP 6 — Sync repo + warmstart checkpoint from local box
# ────────────────────────────────────────────────────────────────────────
# (run on LOCAL box, not the rented one)
# REMOTE_HOST=ssh-host
# REMOTE_PORT=ssh-port
# rsync -avz -e "ssh -p $REMOTE_PORT" \
#   --exclude='data/' --exclude='.venv/' --exclude='__pycache__/' \
#   --exclude='*.pyc' --exclude='.git/' \
#   /home/doctor/projects/carcassone/ root@$REMOTE_HOST:/workspace/carcassone/
# rsync -avz -e "ssh -p $REMOTE_PORT" \
#   /home/doctor/projects/carcassone/checkpoints/warmstart_canonical.pt \
#   root@$REMOTE_HOST:/workspace/carcassone/checkpoints/

# ────────────────────────────────────────────────────────────────────────
# STEP 7 — Install deps on remote (~30s with uv) and run smoke tests
# ────────────────────────────────────────────────────────────────────────
# (run on REMOTE box)
# cd /workspace/carcassone
#
# # Bootstrap uv (much faster than pip — ~30s vs 3-5 min for our deps).
# # Skip if uv is already there (some pytorch images include it).
# command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
# export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
#
# # Install into the system Python (no venv needed in a single-purpose container).
# # uv defaults to using the active Python; the pytorch image's Python is fine.
# uv pip install --system -r requirements.txt
#
# # Sanity-check the runtime
# python -c "import torch; assert torch.cuda.is_available(); print('CUDA ok:', torch.cuda.get_device_name())"
# pytest tests/test_neural_mcts_virtual_loss.py tests/test_selfplay.py -q
# # If tests fail, STOP — likely CUDA/PyTorch version mismatch. Fix locally.

# ────────────────────────────────────────────────────────────────────────
# STEP 8 — Run a 1-iter calibration on remote (10-15 min)
# ────────────────────────────────────────────────────────────────────────
# Bench the actual rented hardware before committing to the long run.
# WORKERS = effective_cores you're paying for (e.g., 16 for the EPYC 7502 box).
# nohup python -u scripts/run_selfplay_iter.py \
#   --checkpoint checkpoints/warmstart_canonical.pt \
#   --output-root data/selfplay/vastai_calibration \
#   --iter 0 --games 16 --sims 100 \
#   --batch-size 8 --workers 16 --no-cuda-cap \
#   > /tmp/calib.log 2>&1 & disown
#
# Watch:
#   tail -f /tmp/calib.log  (cancel with Ctrl-C; doesn't kill the run)
# Wait for "Done iter=0" line. Note the wallclock — extrapolate to full run.

# ────────────────────────────────────────────────────────────────────────
# STEP 8b — Worker sweep on the rented box (~30-45 min, ~$0.05)
# ────────────────────────────────────────────────────────────────────────
# Per-core perf, L3-cache dynamics, GPU-context contention all differ from
# our local 5800X. Re-discover the optimal W on the rented hardware before
# committing to the long run.
#
# Pick W values that span the rented box's effective cores. Examples:
#   16-core box:  W={4, 8, 12, 16, 20}      # we already know local optimum at 5800X
#   32-core box:  W={8, 16, 24, 32, 48}     # 48 tests over-subscription
#   64-core box:  W={16, 32, 48, 64, 96}
#
# (run on REMOTE box)
# RESULTS=/tmp/vastai_bench_workers.txt
# echo "W,games,sims,batch,wallclock_s" > $RESULTS
# for W in 8 16 24 32 48; do      # adjust to rented box
#   rm -rf "data/selfplay/bench_w${W}"
#   start=$(date +%s.%N)
#   python -u scripts/run_selfplay_iter.py \
#     --checkpoint checkpoints/warmstart_canonical.pt \
#     --output-root "data/selfplay/bench_w${W}" \
#     --iter 0 --games 16 --sims 100 \
#     --batch-size 8 --workers "$W" --no-cuda-cap \
#     > "/tmp/bench_w${W}.log" 2>&1
#   elapsed=$(python3 -c "print(f'{$(date +%s.%N) - $start:.1f}')")
#   echo "$W,16,100,8,$elapsed" >> $RESULTS
#   echo "W=$W: ${elapsed}s"
# done
# cat $RESULTS
#
# Then maybe a fine-grained sweep around the winner (e.g., if W=24 won,
# try {20, 22, 24, 26, 28}).
#
# Pick the W that minimizes wallclock. Use that for STEP 9.

# ────────────────────────────────────────────────────────────────────────
# STEP 9 — Launch the actual 30-iter run (or 200-iter)
# ────────────────────────────────────────────────────────────────────────
# 30-iter sanity:
# nohup python -u scripts/run_phase4_smoke.py \
#   --iters 30 --games 50 --sims 100 \
#   --eval-sims 100 --eval-games 20 \
#   --workers 16 --eval-workers 16 \
#   --batch-size 8 --virtual-loss 1.0 --no-cuda-cap \
#   --output-root data/selfplay/sanity_30iter \
#   > /tmp/phase4_30iter.log 2>&1 & disown
#
# 200-iter prod (only if 30-iter passes):
#   --iters 200 --games 100 --sims 200 --eval-sims 200 --eval-games 30
#   (and bump --workers to whatever the rented box has)

# ────────────────────────────────────────────────────────────────────────
# STEP 10 — Monitor (you'll be on local box; SSH back periodically)
# ────────────────────────────────────────────────────────────────────────
# From local:
#   ssh -p $REMOTE_PORT root@$REMOTE_HOST 'tail -50 /tmp/phase4_30iter.log'
#   ssh -p $REMOTE_PORT root@$REMOTE_HOST 'cat /workspace/carcassone/data/selfplay/sanity_30iter/elo_log.json'
# Both safe to disconnect from — the remote nohup keeps running.

# ────────────────────────────────────────────────────────────────────────
# STEP 11 — Pull results back to local
# ────────────────────────────────────────────────────────────────────────
# (run on LOCAL box once the remote run finishes)
# rsync -avz -e "ssh -p $REMOTE_PORT" \
#   root@$REMOTE_HOST:/workspace/carcassone/data/selfplay/sanity_30iter/ \
#   /home/doctor/projects/carcassone/data/selfplay/sanity_30iter/
# rsync -avz -e "ssh -p $REMOTE_PORT" \
#   root@$REMOTE_HOST:/workspace/carcassone/checkpoints/selfplay/ \
#   /home/doctor/projects/carcassone/checkpoints/selfplay/

# ────────────────────────────────────────────────────────────────────────
# STEP 12 — Destroy instance to stop the meter
# ────────────────────────────────────────────────────────────────────────
# vastai destroy instance "$INSTANCE_ID"
# CONFIRM with: vastai show instances --raw | jq '.[] | .id'  (your id should be gone)
#
# Common gotcha: stopped (not destroyed) instances still bill for storage.
# Destroy to fully stop charges.
