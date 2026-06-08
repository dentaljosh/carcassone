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
# G-T1/T2 training knobs (default = current behavior; Stage B overrides via env).
LR_SCHEDULE="${LR_SCHEDULE:-none}"          # none | cosine (G-T1)
VALUE_LOSS_WEIGHT="${VALUE_LOSS_WEIGHT:-1.0}"  # value-loss multiplier (G-T2; Stage B ~3)
STAGE_B_BLEND="${STAGE_B_BLEND:-0}"          # 1 → enable the value-blend ramp (G-S1)
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
# G-S3 (2026-06-03, Joshua-approved): the keep/gate reference is HeuristicMCTS
# (OUT-OF-LINEAGE), NOT the warm net. iter_11 is the self-play ANCHOR (in-lineage), so
# gating vs it rewards overfitting — the 2026-06-01 iter_4 "+39 vs iter_11" that TIED on
# the independent ladder. Gating vs HeuristicMCTS uses the SAME tool + reference as the
# +56.7-elo ladder rung, so the per-iter gate and the campaign verdict share one currency
# (elo vs heuristic). The gate runs at value_blend=0 (net priors + v2.7 leaf, exactly
# comparable to the ladder rung — isolates POLICY improvement; the value-head contribution
# is tested at the n=400 campaign verdict). warm_from = best gated checkpoint (reject a
# regressing iter and re-branch from the best). NOTE: per-iter gate cost ≈ n=GATE_GAMES
# eval on top of self-play+train — observe it on iter 0; drop GATE_GAMES if too slow.
GATE_GAMES="${GATE_GAMES:-200}"             # per-iter gate n (paired) vs HeuristicMCTS
GATE_CPUCT="${GATE_CPUCT:-3.0}"             # match production/ladder c=3.0
KEEP_MARGIN_ELO="${KEEP_MARGIN_ELO:-10}"    # adopt iter as new best iff elo >= best_elo + this
SEED_ELO="${SEED_ELO:-25.2}"                # iter_11 elo vs heuristic @ sims=200 (re-baseline n=400)
GATE_SEED="${GATE_SEED:-500000}"            # gate seed-start (per-iter dirs avoid file collision)
read -r -a HOSTS <<< "${HOSTS:-5800x xeon laptop}"
PY=.venv/bin/python
# CARC_RUN tags every worker (incl mp-spawn + orphans) with this run's name — read back
# by scripts/cluster_census.py via /proc/<pid>/environ for deterministic provenance, and
# `cluster_census.py --kill-tag $RUN` to cleanly kill the whole run incl orphaned workers.
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARC_RUN=$RUN"
mkdir -p "$OUT_LOCAL" "$CKPT_LOCAL" "$CODE_SYNC"
cd "$REPO" || { echo "FATAL: no repo at $REPO"; exit 1; }

workers_for() { case $1 in 5800x) echo 14;; xeon) echo 18;; laptop) echo 24;; *) echo 8;; esac; }
# Self-play per-box mode. RE-BENCHED 2026-06-03 on CURRENT (post-Phase-0) code via
# scripts/sweep_selfplay.sh at blend=0.5 (the stale 2026-06-01 +87% bench was river-era).
# VERDICT: orch-off wins on ALL 3 boxes by ~2× — the single GIL-bound orchestrator
# dispatch thread is pure overhead for the CPU v2.7 leaf, even on the weak Quadro (xeon
# off 5.87 > sh3 5.14 > orch 4.5 pos/s). At blend>0 the value-head GPU forward makes
# self-play GPU-bound past ~W14 everywhere (W20-22 DROP), so W=14 is the flat-peak edge
# on every box (per Joshua's lower-W-on-a-tie rule). Echoes "W <orch-flags>".
#   5800x off W14=11.22 (≈W16 11.07; W20 9.51) | laptop off W14=15.69 (W18 16.27 nominal,
#   +3.7% = within n=24 noise; W22 14.41) | xeon off W14=5.87 (W10 5.67; all orch/sh worse).
selfplay_mode() { case $1 in
  5800x)  echo "14 ";;   # orch-off W14 (fine sweep wsweep2: W14=11.99 jump vs W12 10.91; 16T)
  laptop) echo "20 ";;   # orch-off W20 (fine sweep peak 19.29, +12% vs W14; 24T box wants high W)
  xeon)   echo "10 ";;   # orch-off W10 (12T box, conservative no-oversubscribe; sweep cut early, lowest-impact)
  *)      echo "8 ";;
esac; }
# G-S1 Stage-B value-blend ramp: λ for blending the NN value head INTO the search
# leaf ((1-λ)*v2.7 + λ*v_nn) — the fix for F-B1 (value head never in the loop).
# DEFAULT OFF (0.0 every iter = current production, value head NOT in loop) so this
# script is unchanged for non-Stage-B runs. Set STAGE_B_BLEND=1 to enable the ramp.
# ⚠️ The curve below is a PROPOSAL — Joshua tunes it before the real Stage-B run.
# Gates (gcmd/ccmd/vcmd) deliberately omit --value-blend → stay at 0.0 (comparable).
blend_for_iter() {
  [ "${STAGE_B_BLEND:-0}" = "1" ] || { echo "0.0"; return; }
  # STAGE_B_BLEND_CONST: fix λ at a constant for ALL iters (skip the ramp). Used by the
  # compounding overnight run (λ=1.0 from iter 0). Unset → the ramp curve below.
  if [ -n "${STAGE_B_BLEND_CONST:-}" ]; then echo "$STAGE_B_BLEND_CONST"; return; fi
  case $1 in
    0|1) echo "0.0";;    # warmup on the pure v2.7 leaf
    2)   echo "0.15";;
    3)   echo "0.30";;
    4)   echo "0.50";;
    5)   echo "0.70";;
    *)   echo "1.0";;
  esac
}
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

# G-S3: track best elo vs HeuristicMCTS; warm_from = iter_$best_iter (or WARM if none beat
# the seed yet). best_elo seeded with iter_11's re-baseline elo so an iter must EXCEED the
# seed to be adopted (we never warm from worse-than-iter_11).
best_elo="$SEED_ELO"; best_iter=-1; flat=0
# Persist/restore keep-best across relaunches. AUDITOR (High, 2026-06-03): every relaunch
# reset best_iter=-1, so a crash+resume would re-branch from WARM (iter_11) instead of the
# adopted best — silently corrupting the rest of the chain. Restore prior state if present
# (written after each gate below). On a crash with NO state file (old-code run), reconstruct
# it from the log: grep the last 'NEW BEST → warm_from=iter_NN' and its elo, write best_iter/
# best_elo into $STATE_FILE, then relaunch.
STATE_FILE="$OUT_LOCAL/loop_state.env"
if [ -f "$STATE_FILE" ]; then
  . "$STATE_FILE"
  echo "  restored keep-best: best_iter=$best_iter best_elo=$best_elo flat=$flat (from $STATE_FILE)"
fi

for ((N=START; N<ITERS; N++)); do
  NN=$(printf "%02d" "$N")
  BLEND=$(blend_for_iter "$N")   # G-S1: value-blend λ for this iter (0.0 unless STAGE_B_BLEND=1)
  iter_dir=$OUT_LOCAL/iter_$NN
  mkdir -p "$iter_dir"
  # Self-heal stale claims (claim w/o npz) from a prior killed/jittered attempt so a
  # RESUME can complete those seeds. Safe HERE: runs BEFORE this iter's workers launch,
  # so it can never clear a live claim. Without it, a mid-iter worker death (manual kill,
  # or a laptop Tailscale drop killing a held-ssh) strands that worker's in-flight claims
  # and the resume permanently stalls at GAMES - n_workers_killed (the iter-1 556/600 bug).
  for c in "$iter_dir"/*.claim; do [ -e "$c" ] || break; n="${c%.claim}.npz"; [ -f "$n" ] || rm -f "$c"; done
  # G-S3: warm from the BEST gated checkpoint, not the latest — a regressing iter is
  # rejected and the next iter re-branches from the best (best_iter=-1 → the iter_11 seed).
  if [ "$N" -eq 0 ] || [ "$best_iter" -lt 0 ]; then warm_from=$WARM; else warm_from=$CKPT_LOCAL/iter_$(printf "%02d" "$best_iter").pt; fi
  echo ""; echo "########## ITER $N: self-play @ $(date) (warm_from=$warm_from value_blend=$BLEND) ##########"
  pids=""
  for host in "${HOSTS[@]}"; do
    read -r w orchflags <<< "$(selfplay_mode "$host")"; outp=$OUT_LOCAL; warmp=$warm_from; anchorp=$WARM
    [ "$host" != "5800x" ] && { outp=$(remote_path "$OUT_LOCAL"); warmp=$(remote_path "$warm_from"); anchorp=$(remote_path "$WARM"); }
    cmd="nice -n 19 env $ENVV $PY -u scripts/run_selfplay_iter.py --iter $N --games $GAMES --sims $SIMS --leaf-eval v2_5 --value-blend $BLEND --value-target ${VALUE_TARGET:-score_diff} --workers $w $orchflags --batch-size 8 --checkpoint $warmp --anchor-fraction $ANCHOR_FRACTION --anchor-checkpoint $anchorp --output-root $outp --shared-claim --claim-host $host --seed-start 0"
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

  echo "########## ITER $N: train @ $(date) (lr=$LR_SCHEDULE vlw=$VALUE_LOSS_WEIGHT) ##########"
  # G-T1/T2: LR schedule + value-loss weight. Defaults (none / 1.0) = current
  # behavior. For Stage B the value head is gradient-starved → set e.g.
  # VALUE_LOSS_WEIGHT=3 LR_SCHEDULE=cosine (Joshua tunes; sweep 1–5×).
  # --stage-local: copy the buffer onto local ext4 before streaming. $OUT_LOCAL is
  # on 9p/drvfs (the 5800x share) and a 9p stall wedged a train mid-epoch (GPU idle
  # ~50min, 2026-06-05). Staging keeps the read-path off 9p; cleaned after train.
  STAGE_DIR="/tmp/carc_stage_${RUN}_$NN"
  nice -n 19 env $ENVV $PY -u scripts/train_iter.py \
    --output-root "$OUT_LOCAL" --warmstart-root "$REPO/data/warmstart/heuristic_tau05" \
    --iter "$N" --window 10 --warmstart-mix-fraction 0.0 \
    --lr-schedule "${LR_SCHEDULE:-none}" --value-loss-weight "${VALUE_LOSS_WEIGHT:-1.0}" \
    --stage-local "$STAGE_DIR" \
    --warm-from "$warm_from" --output "$CKPT_LOCAL/iter_$NN.pt" --epochs 3 \
    --prov-value-target "${VALUE_TARGET:-score_diff}" \
    --prov-selfplay-leaf "v2_7+blend${BLEND}" \
    --prov-seed-range "0-$((GAMES-1))" \
    --prov-run-tag "$RUN"
  trc=$?
  rm -rf "$STAGE_DIR" 2>/dev/null || true
  if [ $trc -ne 0 ]; then echo "TRAIN exited $trc (entropy collapse / NaN?) — HALTING loop at iter $N"; exit $trc; fi

  echo "########## ITER $N: GATE vs HeuristicMCTS (G-S3 out-of-lineage, n=$GATE_GAMES paired, c=$GATE_CPUCT, 3-box --shared-claim) @ $(date) ##########"
  # Fan the gate across all boxes; each claims its share into the shared eval dir; tally
  # the full pool after via --summary-only. Reference = HeuristicMCTS (NOT the warm net):
  # same currency as the +56.7 ladder rung. Runs at value_blend=0 (priors + v2.7 leaf).
  gate_dir=$OUT_LOCAL/eval/iter_${NN}_vs_heur
  gpids=""
  for host in "${HOSTS[@]}"; do
    gw=$(gate_workers "$host"); goutp=$OUT_LOCAL; gnew=$CKPT_LOCAL/iter_$NN.pt
    [ "$host" != "5800x" ] && { goutp=$(remote_path "$OUT_LOCAL"); gnew=$(remote_path "$gnew"); }
    gcmd="nice -n 19 env $ENVV $PY -u scripts/eval_net_vs_heuristic.py --checkpoint $gnew --n $GATE_GAMES --sims $SIMS --heur-sims $SIMS --c-puct $GATE_CPUCT --workers $gw --out-root $goutp --out-subdir eval/iter_${NN}_vs_heur --seed-start $GATE_SEED --paired --shared-claim --claim-host $host"
    gpidf="/tmp/pathb_gatepid_${host}_$NN"; rm -f "$gpidf"
    launch_on_host "$host" "gate_${RUN}_$NN" "$gcmd" "/tmp/pathb_gate_${host}_$NN.log" "$gpidf"
    sleep 1; gp=$(cat "$gpidf" 2>/dev/null); gpids="$gpids $gp"; echo "  launched gate on $host (W=$gw) PID=$gp"
  done
  gate_elo=""
  if wait_for_count "$gate_dir" "n*.json" "$GATE_GAMES" "$gpids" "iter$N-gate"; then
    # Full-pool tally (reads every n*.json in the dir; prints "ELO (net vs heuristic): X").
    gate_out=$(nice -n 19 env $ENVV $PY -u scripts/eval_net_vs_heuristic.py --checkpoint $CKPT_LOCAL/iter_$NN.pt --n $GATE_GAMES --sims $SIMS --heur-sims $SIMS --c-puct $GATE_CPUCT --out-root $OUT_LOCAL --out-subdir eval/iter_${NN}_vs_heur --seed-start $GATE_SEED --paired --summary-only 2>&1)
    echo "$gate_out"
    gate_elo=$(printf '%s\n' "$gate_out" | sed -n 's/.*ELO (net vs heuristic): \([+-][0-9.]*\).*/\1/p' | tail -1)
  else
    echo "  (gate incomplete — some boxes died; continuing without an elo this iter)"
  fi
  # reap gate stragglers on every box (mirrors cleanup_sp)
  for host in "${HOSTS[@]}"; do
    case $host in
      5800x) pkill -TERM -f eval_net_vs_heuristic 2>/dev/null || true ;;
      xeon)  ssh -o ConnectTimeout=10 xeon "wsl -d Ubuntu-24.04 -- pkill -TERM -f eval_net_vs_heuristic" 2>/dev/null || true ;;
      laptop) ssh -o ConnectTimeout=10 laptop "pkill -TERM -f eval_net_vs_heuristic" 2>/dev/null || true ;;
    esac
  done; sleep 5

  # G-S3 keep/plateau: gate elo is measured vs HeuristicMCTS (out-of-lineage, fixed ref),
  # so it should climb as the learner improves. Adopt iter $N as the new best (→ next
  # warm_from) iff its elo beats the running best by ≥ KEEP_MARGIN_ELO. Stop after MAX_FLAT
  # consecutive iters that fail to set a new best. n=GATE_GAMES is much less noisy than the
  # old n=40 wr screen (n=200 paired ≈ ±12 elo), so a flat streak is trustworthy on its own;
  # the net-vs-net confirm_gate is superseded (in-lineage, the trap we moved away from).
  if [ -n "$gate_elo" ]; then
    thresh=$(awk "BEGIN{printf \"%.4f\", $best_elo + $KEEP_MARGIN_ELO}")
    if awk "BEGIN{exit !($gate_elo >= $thresh)}"; then
      best_elo=$gate_elo; best_iter=$N; flat=0
      echo "  GATE: iter $N = ${gate_elo} elo vs heuristic ≥ best+margin ($thresh) — NEW BEST → warm_from=iter_$NN; flat reset to 0"
    else
      flat=$((flat + 1))
      echo "  GATE: iter $N = ${gate_elo} elo vs heuristic < best+margin ($thresh; best=$best_elo iter $best_iter); flat $flat/$MAX_FLAT"
      if [ "$flat" -ge "$MAX_FLAT" ]; then
        echo "########## PLATEAU: $flat iters (n=$GATE_GAMES gate) without a new best — STOPPING at iter $N. Best = iter $best_iter ($best_elo elo vs heuristic). @ $(date) ##########"
        echo "  (campaign verdict: run iter $best_iter vs iter_11 at n=400 paired; success bar = +25 elo over iter_11.)"
        echo "########## ITER $N COMPLETE @ $(date) ##########"
        break
      fi
    fi
  else
    echo "  (no gate elo captured this iter — skipping keep/plateau check)"
  fi
  printf 'best_iter=%s\nbest_elo=%s\nflat=%s\n' "$best_iter" "$best_elo" "$flat" > "$STATE_FILE"
  echo "########## ITER $N COMPLETE @ $(date) ##########"
done
echo "=== CLUSTER LOOP DONE @ $(date) ==="
