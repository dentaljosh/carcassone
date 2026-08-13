#!/usr/bin/env bash
# work_queue.sh -- the measurement work-queue chain.
#
# WHAT IT IS: a long-lived, detached poller that watches the two boxes (local
# 5900XT + laptop-wsl), and the moment a box frees, launches the highest-priority
# DISPATCHABLE item from scripts/scheduler/queue.json on it -- detached, niced,
# with its own DONE/FAILED markers and its own log. Then it keeps going.
#
# WHY A CHAIN AND NOT A HUMAN: the queue items are built by sibling agents that
# land at unpredictable times, and the boxes free at unpredictable times. Anything
# that needs a human in the loop wastes box-hours (~8 idle box-hours were burned
# on 2026-08-12 exactly this way).
#
# EVERY DECISION LIVES IN scripts/scheduler/queue_lib.py (pytest-covered). This
# shell does only the three things a shell must: process census, detached launch,
# ssh. Read scripts/scheduler/README.md for the queue format.
#
# HARD SAFETY RULES (enforced in queue_lib.py, restated here because they are the
# point of the whole design):
#   * NEVER edits governance/PRODUCTION.yaml, never adjudicates, never claims a band.
#   * NEVER launches anything that plays games unless a pre-registered prereg file
#     AND a band already claimed in governance/BAND_REGISTRY.csv are both on disk.
#     Otherwise: "BLOCKED: prereg/band missing", and it moves on.
#   * NEVER runs two jobs on one box; NEVER touches the laptop before its occupant's
#     DONE marker exists; NEVER dispatches to a box whose process census is dirty
#     (a marker can lie if a watchdog relaunched something).
#   * An item whose code is still in an unmerged worktree is NEEDS_MERGE -- notice
#     only, never an auto-merge, never an auto-run.
#
# RUN IT (detached; this is how it is armed):
#   setsid nohup nice -n 19 bash /home/doctor/projects/carcassone/scripts/scheduler/work_queue.sh \
#     >> /home/doctor/projects/carcassone/measurement/scheduler_20260813/logs/chain.log 2>&1 &
#
# STOP THE WHOLE QUEUE (graceful, and the watchdog will not restart it):
#   touch /home/doctor/projects/carcassone/measurement/scheduler_20260813/STOP
#
# ENV OVERRIDES: SCHED_QUEUE, SCHED_POLL_SECS (default 300), SCHED_MAX_HOURS
# (default 72), SCHED_PY (default python3), SCHED_ONCE=1 (single tick, for tests).
set -u

REPO=/home/doctor/projects/carcassone
SDIR="$REPO/scripts/scheduler"
RUN="$REPO/measurement/scheduler_20260813"
LOGS="$RUN/logs"
LOG="$LOGS/scheduler.log"
STATE="$RUN/state.json"
STOP="$RUN/STOP"
LOCK="$LOGS/scheduler.lock"

QUEUE="${SCHED_QUEUE:-$SDIR/queue.json}"
PY="${SCHED_PY:-python3}"
POLL="${SCHED_POLL_SECS:-300}"
MAX_HOURS="${SCHED_MAX_HOURS:-72}"
ONCE="${SCHED_ONCE:-0}"

mkdir -p "$LOGS" "$RUN/dispatch" "$RUN/markers"

say() { echo "$(date '+%F %T') $*" >>"$LOG"; }

# ---- single instance ---------------------------------------------------------
exec 9>"$LOCK"
if ! flock -n 9; then
  say "startup SKIPPED - another work_queue.sh holds the lock"
  exit 0
fi

say "=== work_queue.sh START pid=$$ queue=$QUEUE poll=${POLL}s max=${MAX_HOURS}h ==="
if ! "$PY" "$SDIR/queue_lib.py" validate --queue "$QUEUE" >>"$LOG" 2>&1; then
  say "FATAL: queue file failed validation - refusing to run. Fix $QUEUE and relaunch."
  exit 2
fi

# ---- census helpers ----------------------------------------------------------
# A marker can lie (a watchdog may have relaunched something), so every dispatch
# is gated on a live process census of the target box, not on markers alone.
census_patterns() {  # $1 = box name -> one regex per line
  "$PY" - "$QUEUE" "$1" <<'PYEOF'
import json, sys
q = json.load(open(sys.argv[1]))
pats = q["boxes"][sys.argv[2]].get("census_patterns")
if not pats:
    p = q["boxes"][sys.argv[2]].get("census_pattern")
    pats = [p] if p else []
print("\n".join(pats))
PYEOF
}

count_local_census() {
  local pids="" p
  while IFS= read -r p; do
    [ -z "$p" ] && continue
    pids="$pids $(pgrep -f "$p" 2>/dev/null || true)"
  done < <(census_patterns local)
  # drop our own pid/ppid defensively (pgrep -f can match a wrapper argv)
  echo "$pids" | tr ' ' '\n' | sed '/^$/d' \
    | grep -vx -e "$$" -e "$PPID" 2>/dev/null | sort -u | wc -l
}

count_laptop_census() {
  local host out probe="$RUN/dispatch/_census_laptop.sh"
  host=$(jqbox laptop host)
  # House rule: pipe a real script to ssh; the inline `ssh h "cd x && y"` form gets
  # the cd stripped in transit. No cd is needed here, but the piped form is the rule.
  { echo 'pids=""'
    echo 'while IFS= read -r p; do'
    echo '  [ -z "$p" ] && continue'
    echo '  pids="$pids $(pgrep -f "$p" 2>/dev/null || true)"'
    echo 'done <<PATS'
    census_patterns laptop
    echo 'PATS'
    echo 'echo "$pids" | tr " " "\n" | sed "/^$/d" | sort -u | wc -l'
  } >"$probe"
  out=$(timeout 90 ssh -o BatchMode=yes -o ConnectTimeout=15 "$host" 'bash -s' <"$probe" 2>/dev/null | tr -d '\r' | tail -1)
  case "$out" in
    ''|*[!0-9]*) echo "-1" ;;   # unreachable / garbage -> fail closed, box stays busy
    *)           echo "$out" ;;
  esac
}

# ---- dispatch: local ---------------------------------------------------------
dispatch_local() {
  local id="$1" cmd="$2" w="$3" joblog="$4" mdir="$5"
  local wrap="$RUN/dispatch/${id}_local.sh"
  mkdir -p "$(dirname "$joblog")" "$mdir"
  rm -f "$mdir/DONE_$id" "$mdir/FAILED_$id"
  cat >"$wrap" <<EOF
#!/usr/bin/env bash
# GENERATED by work_queue.sh on $(date -Is) for queue item '$id'. Safe to re-read,
# pointless to edit -- it is rewritten on every dispatch.
cd $REPO || exit 9
export SCHED_W=$w SCHED_BOX=local SCHED_JOB_ID=$id SCHED_LOG=$joblog
echo "=== scheduler dispatch $id W=$w \$(date -Is) ===" >>"$joblog"
bash "$cmd" "$w" >>"$joblog" 2>&1
rc=\$?
if [ "\$rc" -eq 0 ]; then
  echo "ok \$(date -Is)" >"$mdir/DONE_$id"
else
  echo "rc=\$rc \$(date -Is)" >>"$mdir/FAILED_$id"
fi
echo "=== scheduler dispatch $id EXIT rc=\$rc \$(date -Is) ===" >>"$joblog"
EOF
  chmod +x "$wrap"
  setsid nohup nice -n 19 bash "$wrap" >>"$LOGS/${id}_wrapper.log" 2>&1 </dev/null &
  echo $!
}

# ---- dispatch: laptop --------------------------------------------------------
# Bundle-sync first (remotes cannot reach github; stale code = contaminated cell),
# then pipe a real script with `cd` on line 1, then run under a memory-capped
# systemd scope (the laptop VM is ~11 GB and an uncapped guest is the documented
# WSL teardown mechanism).
dispatch_laptop() {
  local id="$1" cmd="$2" w="$3" joblog="$4" mdir_local="$5" mdir_remote="$6"
  local host share_local share_remote memmax rel branch remote_head bundle bpath ahead
  host=$(       jqbox laptop host)
  share_local=$(jqbox laptop share_local)
  share_remote=$(jqbox laptop share_remote)
  memmax=$(     jqbox laptop mem_max)
  rel="${cmd#"$REPO"/}"
  branch=$(git -C "$REPO" rev-parse --abbrev-ref HEAD)

  mkdir -p "$mdir_local" "$share_local/bundles" "$share_local/scheduler_20260813/dispatch"
  rm -f "$mdir_local/DONE_$id" "$mdir_local/FAILED_$id"

  # --- bundle sync, incremental when the laptop already has our history --------
  remote_head=$(timeout 60 ssh -o BatchMode=yes -o ConnectTimeout=15 "$host" \
                  "git -C $REPO rev-parse HEAD" 2>/dev/null | tr -d '\r\n ')
  bundle=""
  if [ -n "$remote_head" ] && git -C "$REPO" cat-file -e "${remote_head}^{commit}" 2>/dev/null; then
    ahead=$(git -C "$REPO" rev-list --count "${remote_head}..${branch}" 2>/dev/null || echo 0)
    if [ "${ahead:-0}" -eq 0 ]; then
      say "  laptop already at $remote_head (0 commits behind $branch) - no bundle needed"
    else
      bundle="sched_${id}_$(date +%Y%m%d_%H%M%S).bundle"
      bpath="$share_local/bundles/$bundle"
      if ! git -C "$REPO" bundle create "$bpath" "^$remote_head" "$branch" >>"$LOG" 2>&1; then
        say "  incremental bundle failed - falling back to a full bundle"
        git -C "$REPO" bundle create "$bpath" "$branch" >>"$LOG" 2>&1 || {
          say "  BUNDLE FAILED - refusing to dispatch $id to the laptop with stale code"; return 1; }
      fi
      say "  bundle $bundle ($ahead commit(s) ahead of the laptop)"
    fi
  else
    bundle="sched_${id}_$(date +%Y%m%d_%H%M%S).bundle"
    bpath="$share_local/bundles/$bundle"
    git -C "$REPO" bundle create "$bpath" "$branch" >>"$LOG" 2>&1 || {
      say "  BUNDLE FAILED - refusing to dispatch $id to the laptop with stale code"; return 1; }
    say "  full bundle $bundle (laptop HEAD unknown or not in our history)"
  fi

  # --- inner wrapper, staged on the share (both boxes see it) -----------------
  local innerL="$share_local/scheduler_20260813/dispatch/${id}_run.sh"
  local innerR="$share_remote/scheduler_20260813/dispatch/${id}_run.sh"
  cat >"$innerL" <<EOF
#!/usr/bin/env bash
# GENERATED by work_queue.sh on $(date -Is) for queue item '$id' (laptop).
cd $REPO || exit 9
export SCHED_W=$w SCHED_BOX=laptop SCHED_JOB_ID=$id SCHED_LOG=$joblog
mkdir -p "\$(dirname "$joblog")" "$mdir_remote"
echo "=== scheduler dispatch $id W=$w \$(date -Is) ===" >>"$joblog"
nice -n 19 bash "$rel" "$w" >>"$joblog" 2>&1
rc=\$?
if [ "\$rc" -eq 0 ]; then
  echo "ok \$(date -Is)" >"$mdir_remote/DONE_$id"
else
  echo "rc=\$rc \$(date -Is)" >>"$mdir_remote/FAILED_$id"
fi
echo "=== scheduler dispatch $id EXIT rc=\$rc \$(date -Is) ===" >>"$joblog"
EOF
  chmod +x "$innerL"

  # --- remote script: cd on line 1, piped via `bash -s` (never inline `cd &&`) --
  local remote="$RUN/dispatch/${id}_remote.sh"
  {
    echo "cd $REPO || exit 9"
    echo 'set -uo pipefail'
    if [ -n "$bundle" ]; then
      cat <<EOF
BUNDLE="$share_remote/bundles/$bundle"
drift=\$(( \$(date +%s) - \$(stat -c %Y "\$BUNDLE") )); drift=\${drift#-}
if [ "\$drift" -gt 300 ]; then
  echo "CLOCK DRIFT \${drift}s vs bundle mtime - fix with date -s before launching" >&2; exit 3
fi
git fetch "\$BUNDLE" $branch || exit 5
git reset --hard FETCH_HEAD || exit 5
EOF
    fi
    cat <<EOF
.venv/bin/python -c "import carcassonne_ai" >/dev/null 2>&1 || { echo "venv import failed" >&2; exit 4; }
[ -f "$rel" ] || { echo "launch command $rel absent after sync" >&2; exit 6; }
mkdir -p "$mdir_remote"
nohup systemd-run --user --scope -p MemoryMax=$memmax bash "$innerR" \
  >"$share_remote/scheduler_20260813/dispatch/${id}_scope.log" 2>&1 </dev/null &
disown
echo "launched $id detached under a MemoryMax=$memmax scope"
EOF
  } >"$remote"

  if ! timeout 300 ssh -o BatchMode=yes -o ConnectTimeout=15 "$host" 'bash -s' <"$remote" >>"$LOG" 2>&1; then
    say "  REMOTE LAUNCH FAILED for $id (see $LOG) - not marking dispatched"
    return 1
  fi
  echo "remote"
}

jqbox() {  # $1 box, $2 key
  "$PY" - "$QUEUE" "$1" "$2" <<'PYEOF'
import json, sys
print(json.load(open(sys.argv[1]))["boxes"][sys.argv[2]].get(sys.argv[3], ""))
PYEOF
}

# ---- one tick ----------------------------------------------------------------
tick() {
  local cl clap decision n
  cl=$(count_local_census)
  clap=$(count_laptop_census)
  decision=$("$PY" "$SDIR/queue_lib.py" tick --queue "$QUEUE" --state "$STATE" \
               --census "local=$cl,laptop=$clap" 2>>"$LOG")
  if [ -z "$decision" ]; then
    say "TICK ERROR: queue_lib.py tick produced no output (see $LOG)"
    return 0
  fi

  # log every box + item line the decision core produced
  "$PY" - <<'PYEOF' "$decision" >>"$LOG"
import json, sys, time
d = json.loads(sys.argv[1])
ts = time.strftime('%F %T')
for line in d["log_lines"]:
    print(f"{ts}   {line}")
PYEOF

  local item box cmd w joblog mdirL mdirR pid
  item=$(dget "$decision" item)
  [ -z "$item" ] && { [ "$(dget "$decision" drained)" = "True" ] && \
      say "queue DRAINED - idling; add items to $QUEUE (no restart needed)"; return 0; }

  box=$(   dget "$decision" box)
  cmd=$(   dget "$decision" launch_cmd)
  w=$(     dget "$decision" workers)
  joblog=$(dget "$decision" log)
  mdirL=$( dget "$decision" marker_dir_local)
  mdirR=$( dget "$decision" marker_dir_remote)
  case "$joblog" in /*) ;; *) joblog="$REPO/$joblog" ;; esac

  say "DISPATCHING $item -> $box W=$w cmd=$cmd"
  if [ "$box" = "laptop" ]; then
    pid=$(dispatch_laptop "$item" "$cmd" "$w" "$joblog" "$mdirL" "$mdirR")
  else
    pid=$(dispatch_local "$item" "$cmd" "$w" "$joblog" "$mdirL")
  fi
  if [ -z "$pid" ]; then
    say "DISPATCH FAILED for $item on $box"
    "$PY" "$SDIR/queue_lib.py" record --queue "$QUEUE" --state "$STATE" \
      --item "$item" --event launch_failed --box "$box" --detail "launch returned no pid"
    return 0
  fi
  "$PY" "$SDIR/queue_lib.py" record --queue "$QUEUE" --state "$STATE" \
    --item "$item" --event dispatched --box "$box" --pid "$pid" \
    --detail "W=$w cmd=$cmd log=$joblog"
  say "DISPATCHED $item on $box (pid/handle $pid), log $joblog"
  # verify parallelism a moment later (house reflex) -- logged, not enforced
  ( sleep 60
    if [ "$box" = "local" ]; then
      say "  parallelism check $item: $(count_local_census) live process(es) on local"
    else
      say "  parallelism check $item: $(count_laptop_census) live process(es) on laptop"
    fi ) &
}

dget() {  # pull one key out of the decision JSON's dispatch object
  "$PY" - "$1" "$2" <<'PYEOF'
import json, sys
d = json.loads(sys.argv[1])
if sys.argv[2] == "drained":
    print(d.get("drained")); raise SystemExit
disp = d.get("dispatch") or {}
print(disp.get(sys.argv[2], "") if disp else "")
PYEOF
}

# ---- main loop ---------------------------------------------------------------
started=$(date +%s)
while true; do
  if [ -f "$STOP" ]; then
    say "STOP file present ($STOP) - exiting cleanly. rm it and relaunch (or wait for the cron watchdog) to resume."
    exit 0
  fi
  tick
  [ "$ONCE" = "1" ] && { say "SCHED_ONCE=1 - single tick done, exiting"; exit 0; }
  now=$(date +%s)
  if [ $(( now - started )) -gt $(( MAX_HOURS * 3600 )) ]; then
    say "max lifetime ${MAX_HOURS}h reached - exiting (the cron watchdog will start a fresh one)"
    exit 0
  fi
  sleep "$POLL"
done
