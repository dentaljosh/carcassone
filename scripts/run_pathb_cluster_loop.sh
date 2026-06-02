#!/usr/bin/env bash
# ⚠️ TRACKED SNAPSHOT (committed 2026-06-02). The COPY THAT ACTUALLY RUNS lives at
# /home/doctor/run_pathb_cluster_loop.sh (mirrored to the CIFS share's code_sync/
# for the remotes) — it can't live only in the repo because the launcher
# self-mounts the share (chicken-egg). Keep this snapshot in sync when editing the
# operational copy; this is the version-controlled, reviewable source. The C7
# conditional-gate change (warm-from best-so-far + adopt-on-confirmed) is PENDING
# here — see docs/PHASE1_BUILD_SPEC_2026-06-02.md Stage A5.
#
# PATH B Step 8 — 3-box work-stealing self-play LOOP. Adapts the proven
# maximalist_sequencer infra (held-ssh foreground python keeps the Xeon WSL VM
# alive per iter; stage_launcher.sh mounts+copies the launcher LOCAL on Xeon to
# dodge the share-unmounted chicken-egg). Per iter:
#   3-box shared-claim self-play -> train_iter (5800x) -> anchor-gate.
# Output + checkpoints live on the CIFS share so every box reads warm-from and
# writes seeds into the same folder. train_iter carries the entropy-floor
# collapse guard (exit 2 -> loop halts) + prints value-outcome corr each iter.
#
# Boxes: 5800x (local), xeon (Windows->WSL via stage_launcher), laptop (native
# Linux, /home/pop, share already mounted). Knobs: sims=200, v2.7 leaf, mix 0.
#
# Env: START(0) ITERS(12) GAMES(600) SIMS(200) HOSTS("5800x xeon laptop") POLL(60) WARM_SRC.
#   START>0 RESUMES in the same RUN dir from iter START (warm_from=iter_{START-1}.pt),
#   keeping train_iter's --window data buffer continuous. Anchor-gate stays vs the
#   original warm (cumulative climb). Requires ckpt/iter_{START-1}.pt + warm.pt present.
# Launch: nohup nice -n 19 bash /home/doctor/run_pathb_cluster_loop.sh > /tmp/pathb_cluster.log 2>&1 & disown
set -uo pipefail

REPO=/home/doctor/projects/carcassone
SHARE_LOCAL=/mnt/c/carc-shared
SHARE_REMOTE=/mnt/carc-shared          # both xeon AND laptop mount here
CODE_SYNC=$SHARE_LOCAL/code_sync
LAPTOP_REPO=/home/pop/carcassone
# Default RUN is a FRESH dir (pathb_anchor) so a START=0 anchor run can't clobber
# the pathb_loop screening checkpoints (iter_00..iter_11). Override RUN=pathb_loop
# START=12 only to resume the old extended loop.
RUN="${RUN:-pathb_anchor}"
OUT_LOCAL=$SHARE_LOCAL/$RUN
CKPT_LOCAL=$SHARE_LOCAL/$RUN/ckpt
# Strength push (DECISIONS 2026-05-31 ladder): warm-from + anchor + gate-ref all =
# iter_11 (the confirmed-strongest checkpoint), gating cumulative climb vs a FIXED ref.
WARM_SRC="${WARM_SRC:-$SHARE_LOCAL/pathb_loop/ckpt/iter_11.pt}"
WARM=$SHARE_LOCAL/$RUN/warm.pt
ITERS="${ITERS:-12}"; GAMES="${GAMES:-600}"; SIMS="${SIMS:-200}"
START="${START:-0}"
ANCHOR_GAMES="${ANCHOR_GAMES:-40}"; POLL="${POLL:-60}"
# Anchor-fraction self-play: a fraction of games are learner-vs-anchor (fixed iter_11),
# injecting a strong stationary opponent so the learner can't drift into self-play
# collusion. Flags are review-hardened (REVIEW_LOG iters 5-8). Anchor = WARM = iter_11.
ANCHOR_FRACTION="${ANCHOR_FRACTION:-0.3}"
# Plateau guard: after MAX_FLAT consecutive n=ANCHOR_GAMES gate win-rates fail to beat
# the running best, we SUSPECT a plateau. But n=ANCHOR_GAMES is noisy (1σ≈±8% at 40),
# so a flat streak can be noise, not a real stall. CONFIRM-BEFORE-KILL: rather than
# hard-stop on screen-grade evidence (asymmetric vs the verdict-grade bar we'd demand
# for a positive), we run ONE n=CONFIRM_GAMES head-to-head of the latest iter vs the
# current best. CONTINUE (plateau was noise) iff latest beats best at wr≥CONFIRM_THRESH;
# else STOP for real. This makes the kill decision symmetric with the keep decision and
# is immune to the running-best ratchet bias (it compares latest-vs-best directly, not
# vs the fixed iter_11 ref). CONFIRM_GAMES=400 ≈ our "verdict" n (1σ≈±2.5%).
MAX_FLAT="${MAX_FLAT:-2}"
CONFIRM_GAMES="${CONFIRM_GAMES:-400}"
CONFIRM_THRESH="${CONFIRM_THRESH:-0.54}"
read -r -a HOSTS <<< "${HOSTS:-5800x xeon laptop}"
PY=.venv/bin/python
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12"
mkdir -p "$OUT_LOCAL" "$CKPT_LOCAL" "$CODE_SYNC"
cd "$REPO" || { echo "FATAL: no repo at $REPO"; exit 1; }

workers_for() { case $1 in 5800x) echo 14;; xeon) echo 18;; laptop) echo 24;; *) echo 8;; esac; }
# Self-play per-box mode (DECISIONS 2026-06-01 bench: mixed-mode = +87% cluster).
# Echoes "W <orch-flags>". The CPU v2.7 leaf makes the single-thread orchestrator
# the limiter, so bypass it (orch-off) where the net×W fits VRAM (5800x/laptop);
# the 8GB Turing box uses orch_shards=2. Strength-neutral: orch-off uses the same
# inline evaluator the orchestrator wraps (tests/test_eval_server.py: identical <1e-5).
selfplay_mode() { case $1 in
  5800x)  echo "16 ";;                                # orch-off W=16  -> 14.70 mv/s (+99%)
  laptop) echo "10 ";;                                # orch-off W=10  -> 19.26 mv/s (+110%)
  xeon)   echo "18 --orchestrator --orch-shards 2";;  # shards=2       -> 6.99 mv/s (+30%)
  *)      echo "8 --orchestrator";;
esac; }
# Anchor-gate eval workers per box (net-vs-net loads 2 nets/worker -> 2x VRAM, so
# conservative on the 8GB boxes; UNBENCHED for this script — eval_wsweep measured
# eval_net_vs_heuristic, not head-to-head). Gate fans across boxes via --shared-claim.
gate_workers() { case $1 in 5800x) echo 12;; xeon) echo 8;; laptop) echo 10;; *) echo 6;; esac; }
remote_path() { echo "$1" | sed "s|^$SHARE_LOCAL|$SHARE_REMOTE|"; }

# Writes the launched PID to $5 (pidout). MUST be called directly (not via $())
# so backgrounding the worker doesn't make command-substitution wait on the
# worker's orchestrator children holding the pipe fd (the hang bug).
launch_on_host() {  # host name cmdline log pidout
  local host=$1 name=$2 cmdline=$3 log=$4 pidout=$5
  if [ "$host" = "5800x" ]; then
    nohup bash -c "$cmdline" > "$log" 2>&1 < /dev/null &
    echo $! > "$pidout"; disown
  elif [ "$host" = "xeon" ]; then
    # 1) write the per-job launcher to the share; 2) stage it LOCAL on Xeon
    # (mounts share + copies) so it's readable even if the share later drops;
    # 3) held ssh runs the LOCAL launcher foreground (keeps the WSL VM alive).
    local launcher=$CODE_SYNC/launch_xeon_${name}.sh
    cat > "$launcher" <<EOF
#!/usr/bin/env bash
set -uo pipefail
SHARE=$SHARE_REMOTE
mountpoint -q "\$SHARE" || sudo mount -t cifs //192.168.0.195/carc-shared "\$SHARE" -o credentials=/home/doctor/.carc-smb.creds,uid=1000,gid=1000,forceuid,forcegid,file_mode=0644,dir_mode=0755,vers=3.1.1,nobrl,actimeo=1,noserverino
mountpoint -q "\$SHARE" || { echo "FATAL: \$SHARE not mounted" >&2; exit 1; }
cd /home/doctor/projects/carcassone || exit 1
$cmdline
EOF
    chmod +x "$launcher"
    ssh -o ConnectTimeout=15 xeon "wsl -d Ubuntu-24.04 -- bash -lc '/home/doctor/stage_launcher.sh ${name}'" > /dev/null 2>&1
    nohup ssh -o ServerAliveInterval=60 -o ServerAliveCountMax=10 -o ConnectTimeout=15 xeon \
      "wsl -d Ubuntu-24.04 -- bash -lc '/home/doctor/launch_xeon_${name}.sh'" > "$log" 2>&1 < /dev/null &
    echo $! > "$pidout"; disown
  elif [ "$host" = "laptop" ]; then
    # native Linux: held ssh runs the worker foreground (no WSL). The CIFS share
    # is in fstab (_netdev,nofail) + the laptop has passwordless sudo, so re-mount
    # it if a reboot dropped it BEFORE relying on it — else writes hit an empty
    # root-owned mountpoint and the run dies on the first NoSuchFile/perm error
    # (the 2026-05-31 failure mode). Fatal out if it still won't mount.
    nohup ssh -o ServerAliveInterval=60 -o ServerAliveCountMax=10 -o ConnectTimeout=15 laptop \
      "mountpoint -q $SHARE_REMOTE || sudo mount $SHARE_REMOTE 2>/dev/null; mountpoint -q $SHARE_REMOTE || { echo 'FATAL: $SHARE_REMOTE not mounted on laptop' >&2; exit 1; }; cd $LAPTOP_REPO && $cmdline" > "$log" 2>&1 < /dev/null &
    echo $! > "$pidout"; disown
  fi
}

wait_for_count() {  # dir glob target "pids..." name
  local dir=$1 glob=$2 target=$3 pids=$4 name=$5 cnt
  while true; do
    cnt=$(find "$dir" -maxdepth 1 -name "$glob" 2>/dev/null | wc -l)
    if [ "$cnt" -ge "$target" ]; then echo "[$(date +%H:%M)] $name COMPLETE $cnt/$target"; return 0; fi
    local alive=0; for p in $pids; do kill -0 "$p" 2>/dev/null && alive=1; done
    if [ "$alive" -eq 0 ]; then echo "[$(date +%H:%M)] $name ALL_DEAD at $cnt/$target"; return 1; fi
    echo "[$(date +%H:%M)] $name $cnt/$target"; sleep "$POLL"
  done
}

cleanup_sp() {
  for host in "${HOSTS[@]}"; do
    case $host in
      5800x) pkill -TERM -f run_selfplay_iter 2>/dev/null || true ;;
      xeon)  ssh -o ConnectTimeout=10 xeon "wsl -d Ubuntu-24.04 -- pkill -TERM -f run_selfplay_iter" 2>/dev/null || true ;;
      laptop) ssh -o ConnectTimeout=10 laptop "pkill -TERM -f run_selfplay_iter" 2>/dev/null || true ;;
    esac
  done; sleep 8
}

# Verdict-grade confirm gate: n=$3 head-to-head of iter $1 (new) vs iter $2 (old/best),
# fanned across all boxes (net-vs-net, same path as the anchor-gate). Sets global
# confirm_wr = WR(new vs old). Used by the plateau confirm-before-kill so we never stop
# the run on a noisy n=ANCHOR_GAMES streak alone.
confirm_gate() {
  local newi=$1 oldi=$2 games=$3 nn on cdir cpids=""
  nn=$(printf "%02d" "$newi"); on=$(printf "%02d" "$oldi")
  cdir=$OUT_LOCAL/eval/iter_${nn}_vs_${on}   # script zero-pads vs-iter (:02d) → must match
  for host in "${HOSTS[@]}"; do
    local cw goutp gnew gold ccmd cpidf cp
    cw=$(gate_workers "$host"); goutp=$OUT_LOCAL
    gnew=$CKPT_LOCAL/iter_$nn.pt; gold=$CKPT_LOCAL/iter_$on.pt
    [ "$host" != "5800x" ] && { goutp=$(remote_path "$OUT_LOCAL"); gnew=$(remote_path "$gnew"); gold=$(remote_path "$gold"); }
    ccmd="nice -n 19 env $ENVV $PY -u scripts/eval_iter_head_to_head.py --new-checkpoint $gnew --old-checkpoint $gold --output-root $goutp --iter $newi --vs-iter $oldi --games $games --sims $SIMS --c-puct 1.5 --leaf-eval v2_5 --workers $cw --orchestrator --no-elo-log --seed-start 900000 --shared-claim --claim-host $host"
    cpidf="/tmp/pathb_confirmpid_${host}"; rm -f "$cpidf"
    launch_on_host "$host" "confirm_${RUN}" "$ccmd" "/tmp/pathb_confirm_${host}.log" "$cpidf"
    sleep 1; cp=$(cat "$cpidf" 2>/dev/null); cpids="$cpids $cp"; echo "  launched confirm on $host (W=$cw) PID=$cp"
  done
  confirm_wr=""
  if wait_for_count "$cdir" "s*.json" "$games" "$cpids" "confirm"; then
    local cout
    cout=$("$PY" - "$cdir" <<'PYC'
import json, sys, glob, os
d = sys.argv[1]; w = l = dr = 0
for f in glob.glob(os.path.join(d, "s*.json")):
    try: r = json.load(open(f))
    except Exception: continue
    if r.get("drew"): dr += 1
    elif r.get("won_by_new"): w += 1
    else: l += 1
tot = w + l + dr
wr = (w + 0.5 * dr) / tot if tot else 0.0
print(f"  CONFIRM-GATE: {w}W/{dr}D/{l}L of {tot} (wr={wr:.1%})  WR={wr:.4f}")
PYC
)
    echo "$cout"
    confirm_wr=$(printf '%s\n' "$cout" | sed -n 's/.*WR=\([0-9.]*\).*/\1/p' | tail -1)
  fi
  for host in "${HOSTS[@]}"; do
    case $host in
      5800x) pkill -TERM -f eval_iter_head_to_head 2>/dev/null || true ;;
      xeon)  ssh -o ConnectTimeout=10 xeon "wsl -d Ubuntu-24.04 -- pkill -TERM -f eval_iter_head_to_head" 2>/dev/null || true ;;
      laptop) ssh -o ConnectTimeout=10 laptop "pkill -TERM -f eval_iter_head_to_head" 2>/dev/null || true ;;
    esac
  done; sleep 5
}

# ── One-shot VERIFY mode ───────────────────────────────────────────────────
# Run verdict-grade head-to-head gates on EXISTING checkpoints, then exit (skips
# the whole self-play loop). For the post-loop batch: absolute verdict + floor
# sanity-check, fanned across all 3 boxes via the same machinery as the gate.
#   VERIFY="new:old:games:label[,new:old:games:label...]"  (comma-separated)
#   new/old = "iterNN" (-> ckpt/iter_NN.pt) | "warm" (= iter_11 ref) | full path
# Each gate writes to a FRESH eval/verify_<label>/ dir (own vs-iter sentinel +
# seed-start) so it never collides with the loop's n=40 gates. Example:
#   VERIFY="iter04:warm:400:v_iter4_vs_iter11,iter00:iter05:100:floor_i0_vs_i5" \
#     bash /home/doctor/run_pathb_cluster_loop.sh
if [ -n "${VERIFY:-}" ]; then
  resolve_ckpt() { case "$1" in
    warm) echo "$WARM";;
    iter[0-9]*) echo "$CKPT_LOCAL/iter_$(printf "%02d" "$((10#$(echo "$1" | sed 's/[^0-9]//g')))").pt";;
    *) echo "$1";;
  esac; }
  echo "=== VERIFY MODE @ $(date) : $VERIFY ==="
  vsent=${VSENT0:-8800}  # vs-iter sentinel (override VSENT0 to avoid colliding w/ prior VERIFY dirs)
  vseed=700000
  IFS=',' read -r -a _pairs <<< "$VERIFY"
  for spec in "${_pairs[@]}"; do
    IFS=':' read -r vnew vold vgames vlabel <<< "$spec"
    np=$(resolve_ckpt "$vnew"); op=$(resolve_ckpt "$vold")
    if [ ! -f "$np" ]; then echo "SKIP $vlabel: missing new $np"; continue; fi
    if [ ! -f "$op" ]; then echo "SKIP $vlabel: missing old $op"; continue; fi
    # iter index for the script's dir naming = strip 'iter' prefix if present, else 0
    vidx=$(echo "$vnew" | sed 's/[^0-9]//g'); vidx=$((10#${vidx:-0}))
    vdir=$OUT_LOCAL/eval/iter_$(printf "%02d" "$vidx")_vs_${vsent}
    rm -rf "$vdir"; mkdir -p "$vdir"
    echo "--- VERIFY $vlabel: $vnew vs $vold (n=$vgames) -> $vdir @ $(date) ---"
    vpids=""
    for host in "${HOSTS[@]}"; do
      vw=$(gate_workers "$host"); goutp=$OUT_LOCAL; gnew=$np; gold=$op
      [ "$host" != "5800x" ] && { goutp=$(remote_path "$OUT_LOCAL"); gnew=$(remote_path "$np"); gold=$(remote_path "$op"); }
      vcmd="nice -n 19 env $ENVV $PY -u scripts/eval_iter_head_to_head.py --new-checkpoint $gnew --old-checkpoint $gold --output-root $goutp --iter $vidx --vs-iter $vsent --games $vgames --sims $SIMS --c-puct ${VCPUCT:-1.5} --leaf-eval v2_5 --workers $vw --orchestrator --no-elo-log --seed-start $vseed --shared-claim --claim-host $host"
      vpidf="/tmp/pathb_verifypid_${host}"; rm -f "$vpidf"
      launch_on_host "$host" "verify_${vlabel}" "$vcmd" "/tmp/pathb_verify_${host}_${vlabel}.log" "$vpidf"
      sleep 1; vp=$(cat "$vpidf" 2>/dev/null); vpids="$vpids $vp"; echo "  launched $vlabel on $host (W=$vw) PID=$vp"
    done
    if wait_for_count "$vdir" "s*.json" "$vgames" "$vpids" "verify-$vlabel"; then
      "$PY" - "$vdir" "$vlabel" "$vnew" "$vold" "$vgames" <<'PYV'
import json, sys, glob, os
d, label, vnew, vold, n = sys.argv[1:6]
w = l = dr = 0
for f in glob.glob(os.path.join(d, "s*.json")):
    try: r = json.load(open(f))
    except Exception: continue
    if r.get("drew"): dr += 1
    elif r.get("won_by_new"): w += 1
    else: l += 1
tot = w + l + dr
wr = (w + 0.5 * dr) / tot if tot else 0.0
# 1σ for a binomial proportion at this n (rough), in winrate points
sig = (0.25 / tot) ** 0.5 if tot else 0
print(f"  VERIFY-RESULT {label}: {vnew} vs {vold}  {w}W/{dr}D/{l}L of {tot}  wr={wr:.1%}  (1σ≈±{sig*100:.1f}%)")
PYV
    else
      echo "  VERIFY $vlabel INCOMPLETE (a box died) — partial in $vdir"
    fi
    for host in "${HOSTS[@]}"; do
      case $host in
        5800x) pkill -TERM -f eval_iter_head_to_head 2>/dev/null || true ;;
        xeon)  ssh -o ConnectTimeout=10 xeon "wsl -d Ubuntu-24.04 -- pkill -TERM -f eval_iter_head_to_head" 2>/dev/null || true ;;
        laptop) ssh -o ConnectTimeout=10 laptop "pkill -TERM -f eval_iter_head_to_head" 2>/dev/null || true ;;
      esac
    done; sleep 5
    vsent=$((vsent + 1)); vseed=$((vseed + 100000))
  done
  echo "=== VERIFY MODE DONE @ $(date) ==="
  exit 0
fi

echo "=== PATH B 3-box cluster loop: HOSTS=${HOSTS[*]} START=$START ITERS=$ITERS GAMES=$GAMES SIMS=$SIMS @ $(date)"
if [ "$START" -eq 0 ]; then
  # clobber guard: refuse to overwrite an existing iter_00 ckpt (e.g. RUN=pathb_loop)
  if [ -f "$CKPT_LOCAL/iter_00.pt" ]; then
    echo "FATAL: $CKPT_LOCAL/iter_00.pt already exists — START=0 would clobber it. Use a fresh RUN= or resume with START=N." >&2
    exit 1
  fi
  cp "$WARM_SRC" "$WARM" || { echo "FATAL: no warm net at $WARM_SRC"; exit 1; }
  echo "WARM/anchor/gate-ref = $WARM_SRC ; anchor_fraction=$ANCHOR_FRACTION ; plateau stop after $MAX_FLAT flat gates"
else
  [ -f "$WARM" ] || { echo "FATAL: resume needs original $WARM (anchor-gate ref)"; exit 1; }
  [ -f "$CKPT_LOCAL/iter_$(printf "%02d" $((START-1))).pt" ] || { echo "FATAL: resume needs $CKPT_LOCAL/iter_$(printf "%02d" $((START-1))).pt"; exit 1; }
  echo "RESUME from iter $START (warm_from=iter_$(printf "%02d" $((START-1))).pt; anchor-gate vs original warm)"
fi

# Plateau tracking (stop-after-MAX_FLAT-flat, vs the fixed iter_11 gate ref).
best_wr="-1"; best_iter=-1; flat=0

for ((N=START; N<ITERS; N++)); do
  NN=$(printf "%02d" "$N")
  iter_dir=$OUT_LOCAL/iter_$NN
  mkdir -p "$iter_dir"
  if [ "$N" -eq 0 ]; then warm_from=$WARM; else warm_from=$CKPT_LOCAL/iter_$(printf "%02d" $((N-1))).pt; fi
  echo ""; echo "########## ITER $N: self-play @ $(date) (warm_from=$warm_from) ##########"
  pids=""
  for host in "${HOSTS[@]}"; do
    read -r w orchflags <<< "$(selfplay_mode "$host")"; outp=$OUT_LOCAL; warmp=$warm_from; anchorp=$WARM
    [ "$host" != "5800x" ] && { outp=$(remote_path "$OUT_LOCAL"); warmp=$(remote_path "$warm_from"); anchorp=$(remote_path "$WARM"); }
    cmd="nice -n 19 env $ENVV $PY -u scripts/run_selfplay_iter.py --iter $N --games $GAMES --sims $SIMS --leaf-eval v2_5 --value-target score_diff --workers $w $orchflags --batch-size 8 --checkpoint $warmp --anchor-fraction $ANCHOR_FRACTION --anchor-checkpoint $anchorp --output-root $outp --shared-claim --claim-host $host --seed-start 0"
    pidf="/tmp/pathb_pid_${host}_$NN"; rm -f "$pidf"
    launch_on_host "$host" "sp_${RUN}_$NN" "$cmd" "/tmp/pathb_sp_${host}_$NN.log" "$pidf"
    sleep 1; pid=$(cat "$pidf" 2>/dev/null)
    pids="$pids $pid"; echo "  launched self-play on $host (W=$w) PID=$pid"
  done
  # Fail loud if ALL self-play workers die before the iter completes (pre-launch
  # review B2, 2026-05-31): set -e is NOT on, so a bare call would swallow the
  # ALL_DEAD return -> train would run on PARTIAL data and --window 10 would
  # propagate the poisoned iter into the next 9. Halt like train-failure does.
  if ! wait_for_count "$iter_dir" "seed_*.npz" "$GAMES" "$pids" "iter$N-selfplay"; then
    echo "FATAL: self-play workers all died before iter $N reached $GAMES games ($iter_dir) — HALTING (refusing to train on partial data)" >&2
    cleanup_sp
    exit 1
  fi
  cleanup_sp

  echo "########## ITER $N: train @ $(date) ##########"
  nice -n 19 env $ENVV $PY -u scripts/train_iter.py \
    --output-root "$OUT_LOCAL" --warmstart-root "$REPO/data/warmstart/heuristic_tau05" \
    --iter "$N" --window 10 --warmstart-mix-fraction 0.0 \
    --warm-from "$warm_from" --output "$CKPT_LOCAL/iter_$NN.pt" --epochs 3
  trc=$?
  if [ $trc -ne 0 ]; then echo "TRAIN exited $trc (entropy collapse / NaN?) — HALTING loop at iter $N"; exit $trc; fi

  echo "########## ITER $N: anchor-gate vs warm (3-box, --shared-claim) @ $(date) ##########"
  # Fan the gate across all boxes (eval is fastest on the laptop; DECISIONS 2026-06-01).
  # Each box plays its claimed share into the shared eval_dir; we tally all JSONs after.
  # Advisory only — the loop continues regardless of the gate outcome.
  gate_dir=$OUT_LOCAL/eval/iter_${NN}_vs_9999
  gpids=""
  for host in "${HOSTS[@]}"; do
    gw=$(gate_workers "$host"); goutp=$OUT_LOCAL; gnew=$CKPT_LOCAL/iter_$NN.pt; gold=$WARM
    [ "$host" != "5800x" ] && { goutp=$(remote_path "$OUT_LOCAL"); gnew=$(remote_path "$gnew"); gold=$(remote_path "$WARM"); }
    gcmd="nice -n 19 env $ENVV $PY -u scripts/eval_iter_head_to_head.py --new-checkpoint $gnew --old-checkpoint $gold --output-root $goutp --iter $N --vs-iter 9999 --games $ANCHOR_GAMES --sims $SIMS --c-puct 1.5 --leaf-eval v2_5 --workers $gw --orchestrator --no-elo-log --seed-start 800000 --shared-claim --claim-host $host"
    gpidf="/tmp/pathb_gatepid_${host}_$NN"; rm -f "$gpidf"
    launch_on_host "$host" "gate_${RUN}_$NN" "$gcmd" "/tmp/pathb_gate_${host}_$NN.log" "$gpidf"
    sleep 1; gp=$(cat "$gpidf" 2>/dev/null); gpids="$gpids $gp"; echo "  launched gate on $host (W=$gw) PID=$gp"
  done
  gate_wr=""
  if wait_for_count "$gate_dir" "s*.json" "$ANCHOR_GAMES" "$gpids" "iter$N-gate"; then
    gate_out=$("$PY" - "$gate_dir" <<'PYTALLY'
import json, sys, glob, os
d = sys.argv[1]; w = l = dr = 0
for f in glob.glob(os.path.join(d, "s*.json")):
    try: r = json.load(open(f))
    except Exception: continue
    if r.get("drew"): dr += 1
    elif r.get("won_by_new"): w += 1
    else: l += 1
tot = w + l + dr
wr = (w + 0.5 * dr) / tot if tot else 0.0
print(f"  ANCHOR-GATE: {w}W/{dr}D/{l}L of {tot} (wr={wr:.1%}) vs warm  WR={wr:.4f}")
PYTALLY
)
    echo "$gate_out"
    gate_wr=$(printf '%s\n' "$gate_out" | sed -n 's/.*WR=\([0-9.]*\).*/\1/p' | tail -1)
  else
    echo "  (anchor-gate incomplete — some boxes died; continuing)"
  fi
  # reap gate stragglers on every box (mirrors cleanup_sp)
  for host in "${HOSTS[@]}"; do
    case $host in
      5800x) pkill -TERM -f eval_iter_head_to_head 2>/dev/null || true ;;
      xeon)  ssh -o ConnectTimeout=10 xeon "wsl -d Ubuntu-24.04 -- pkill -TERM -f eval_iter_head_to_head" 2>/dev/null || true ;;
      laptop) ssh -o ConnectTimeout=10 laptop "pkill -TERM -f eval_iter_head_to_head" 2>/dev/null || true ;;
    esac
  done; sleep 5

  # Plateau guard: gate wr is measured vs the FIXED iter_11 ref, so it should climb
  # as the learner improves. Stop after MAX_FLAT consecutive iters that fail to beat
  # the running best. (n=ANCHOR_GAMES is noisy → coarse; see header note.)
  if [ -n "$gate_wr" ]; then
    if awk "BEGIN{exit !($gate_wr > $best_wr)}"; then
      best_wr=$gate_wr; best_iter=$N; flat=0; echo "  gate wr=$gate_wr — new best vs iter_11 (iter $N; flat reset to 0)"
    else
      flat=$((flat + 1)); echo "  gate wr=$gate_wr did NOT beat best=$best_wr (iter $best_iter; flat $flat/$MAX_FLAT)"
    fi
    if [ "$flat" -ge "$MAX_FLAT" ]; then
      # CONFIRM BEFORE KILL: the flat streak is screen-grade (n=ANCHOR_GAMES, ±8%). Verify
      # at verdict grade (n=CONFIRM_GAMES) that iter $N really isn't still improving over the
      # best, before throwing away a possibly-working run. Symmetric with the bar we'd demand
      # for a positive; immune to the running-best ratchet (compares latest-vs-best directly).
      echo "########## PLATEAU SUSPECTED: $flat flat gates (n=$ANCHOR_GAMES, ±8%) — CONFIRMING iter $N vs best (iter $best_iter) at n=$CONFIRM_GAMES before killing @ $(date) ##########"
      confirm_gate "$N" "$best_iter" "$CONFIRM_GAMES"
      if [ -z "$confirm_wr" ]; then
        # Confirm gate produced no verdict (boxes died / share hiccup mid-confirm). Do NOT
        # kill the run on an infra failure — that's the false-kill we're trying to avoid.
        # Reset flat so we re-confirm at the next plateau rather than stopping on no data.
        echo "  CONFIRM INCONCLUSIVE: confirm gate produced no result (infra failure?) — NOT killing; resetting flat, will re-confirm at next plateau. @ $(date)"
        flat=0
      elif awk "BEGIN{exit !($confirm_wr >= $CONFIRM_THRESH)}"; then
        echo "  CONFIRM: iter $N beats best (iter $best_iter) at n=$CONFIRM_GAMES (wr=$confirm_wr ≥ $CONFIRM_THRESH) — the flat streak was n=$ANCHOR_GAMES NOISE. Adopting iter $N as best; flat reset; CONTINUING."
        best_iter=$N; best_wr=$gate_wr; flat=0
      else
        echo "########## PLATEAU CONFIRMED at n=$CONFIRM_GAMES: iter $N vs best (iter $best_iter) wr=${confirm_wr:-NA} < $CONFIRM_THRESH — real stall, STOPPING at iter $N. Best = iter $best_iter. @ $(date) ##########"
        echo "  (absolute verdict: gate best iter $best_iter vs iter_11 at n=400 to classify success-vs-null before pivoting to the leaf.)"
        echo "########## ITER $N COMPLETE @ $(date) ##########"
        break
      fi
    fi
  else
    echo "  (no gate wr captured this iter — skipping plateau check)"
  fi
  echo "########## ITER $N COMPLETE @ $(date) ##########"
done
echo "=== CLUSTER LOOP DONE @ $(date) ==="
