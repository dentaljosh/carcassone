#!/bin/bash
# Measure real per-worker RAM for production self-play, cleanly (W small enough to never swap).
# Reports idle baseline, peak used during a W=8 run, the delta (=cost of 8 workers), per-worker
# incremental, and the summed Pss/Rss of the actual compute workers as a cross-check.
set -u
REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
WARM=/mnt/c/carc-shared/pathb_loop/ckpt/iter_11.pt
W=8
TMP=/tmp/memprobe_w8
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARC_RUN=memprobe"
cd "$REPO" || exit 1
rm -rf "$TMP"; mkdir -p "$TMP"

base=$(free -m | awk 'NR==2{print $3}')
echo "idle_baseline_used_MB=$base"

nohup nice -n 19 env $ENVV $PY -u scripts/run_selfplay_iter.py \
  --iter 0 --games 40 --sims 200 --leaf-eval v2_5 --value-blend 0.0 \
  --value-target score_diff --workers $W --batch-size 8 \
  --checkpoint "$WARM" --anchor-fraction 0.3 --anchor-checkpoint "$WARM" \
  --output-root "$TMP" --seed-start 2000000 > /tmp/memprobe_sp.log 2>&1 &
echo "selfplay launched"

# wait for the W workers to load (up to ~45s)
for i in $(seq 1 15); do
  mp=$(pgrep -f "memprobe_w8" | head -1)
  [ -n "$mp" ] && [ "$(pgrep -f 'memprobe_w8' | wc -l)" -ge "$((W+1))" ] && break
  sleep 3
done
echo "loaded: procs=$(pgrep -f 'memprobe_w8' | wc -l)"

# sample ~45s, track peak used RAM
peak=$base
for i in $(seq 1 15); do
  u=$(free -m | awk 'NR==2{print $3}')
  [ "$u" -gt "$peak" ] && peak=$u
  sleep 3
done
echo "peak_used_MB=$peak"

# Pss/Rss of every self-play proc (main + workers) as cross-check
tot_pss=0; tot_rss=0; n=0
for p in $(pgrep -f "memprobe_w8"); do
  pss=$(awk '/^Pss:/{print $2}' /proc/$p/smaps_rollup 2>/dev/null)
  rss=$(awk '/^Rss:/{print $2}' /proc/$p/smaps_rollup 2>/dev/null)
  [ -n "$pss" ] && { tot_pss=$((tot_pss+pss)); tot_rss=$((tot_rss+rss)); n=$((n+1)); }
done
echo "selfplay_procs_measured=$n"
echo "sum_Pss_MB=$((tot_pss/1024))"
echo "sum_Rss_MB=$((tot_rss/1024))"

# clean kill (workers carry --output-root /tmp/memprobe_w8 in cmdline -> pkill -f catches them all)
pkill -f "memprobe_w8" 2>/dev/null || true
sleep 3
pkill -9 -f "memprobe_w8" 2>/dev/null || true
rm -rf "$TMP"

delta=$((peak - base))
echo "---RESULT---"
echo "WSL_total_MB=$(free -m | awk 'NR==2{print $2}')"
echo "background_idle_MB=$base"
echo "peak_used_at_W${W}_MB=$peak"
echo "delta_for_${W}_workers_MB=$delta"
echo "per_worker_incremental_MB=$((delta / W))"
echo "sum_Pss_MB_over_${n}_procs=$((tot_pss/1024))"
