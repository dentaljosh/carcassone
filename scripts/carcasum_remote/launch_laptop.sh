#!/usr/bin/env bash
# Launch the phone remote-opponent server on the LAPTOP, detached and surviving
# the ssh session that started it.
#
#   ssh laptop-wsl 'bash -s' < scripts/carcasum_remote/launch_laptop.sh
#
# (Pipe it — `ssh host 'cd X && ...'` has the `cd` stripped in transit; that is a
# documented Claude Code failure mode and the reason this is a script rather than
# an inline command. Auto-memory `feedback_remote_ssh_pipe_script_mandatory`.)
#
# WHY THE LAPTOP. It is the box the anchor was measured on, and Carcasum's budget
# is thread CPU-TIME, not wall time — so 5 CPU-seconds buys more playouts on a
# faster core, and a different box is literally a DIFFERENT-STRENGTH opponent.
# `measurement/carcasum_owner_session_prep/SETUP.md` §2 is the argument in full;
# the reference throughput to reproduce is a MEDIAN of ~46,332 playouts/turn.
#
# WHY systemd-run --user --scope. A plain `nohup ... &` inside an ssh session on
# this box dies when the last ssh session goes away, because the WSL user manager
# is torn down with it. Lingering is already ENABLED here (auto-memory
# `reference_laptop_cluster_access`), so a --user scope outlives the session.
# `nohup setsid` is the fallback if systemd-run is unavailable.
set -euo pipefail

REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
SERVER=$REPO/scripts/carcasum_remote/server.py
BINARY=$REPO/vendor/carcasum/build-driver/carcasum_driver
PORT=${CARCASUM_REMOTE_PORT:-8971}
LOG=${CARCASUM_REMOTE_LOG:-$REPO/measurement/carcasum_owner_session/server.log}
RECORDS=${CARCASUM_REMOTE_RECORDS:-$REPO/measurement/carcasum_owner_session/server_records}

cd "$REPO"

# The tailnet address of THIS box, taken live — never hardcoded. `tailscale` is
# not installed inside this WSL, but WSL mirrored networking puts the tailnet
# /32 on an interface here, so `hostname -I` carries it.
HOST=$(hostname -I | tr ' ' '\n' | grep -E '^100\.' | head -1)
if [ -z "$HOST" ]; then
  echo "FATAL: no 100.x tailnet address on this box — the phone cannot reach it." >&2
  exit 1
fi

if [ ! -x "$BINARY" ]; then
  echo "FATAL: no carcasum_driver at $BINARY" >&2
  exit 1
fi

mkdir -p "$(dirname "$LOG")" "$RECORDS"

# Already up? Say so and stop — a second daemon on the same port is a silent
# split-brain (half the game's moves would go to a different Carcasum process).
if curl -fsS --max-time 5 "http://$HOST:$PORT/health" >/dev/null 2>&1; then
  echo "ALREADY RUNNING on http://$HOST:$PORT"
  curl -fsS --max-time 5 "http://$HOST:$PORT/health"
  exit 0
fi

CMD=("$PY" "$SERVER" --host "$HOST" --port "$PORT" --binary "$BINARY"
     --budget-ms 5000 --records-dir "$RECORDS")

if command -v systemd-run >/dev/null 2>&1 && [ -n "${XDG_RUNTIME_DIR:-}" ]; then
  systemd-run --user --scope --unit "carcasum-remote-$PORT" \
      --property=MemoryMax=8G \
      nice -n 5 "${CMD[@]}" >>"$LOG" 2>&1 &
else
  nohup setsid nice -n 5 "${CMD[@]}" >>"$LOG" 2>&1 &
fi
disown || true

# The gates (binary sha256 + the live tiny-city scoring probe) run BEFORE the
# socket is bound, so "the port answers" is also "the gates passed".
for _ in $(seq 1 30); do
  sleep 1
  if curl -fsS --max-time 5 "http://$HOST:$PORT/health" 2>/dev/null; then
    echo
    echo "UP on http://$HOST:$PORT  (log: $LOG)"
    echo "Put that address in the phone's Settings -> Opponent -> Remote Carcasum."
    exit 0
  fi
done

echo "FAILED to come up within 30s — last 40 log lines:" >&2
tail -40 "$LOG" >&2
exit 1
