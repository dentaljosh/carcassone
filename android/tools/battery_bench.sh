#!/usr/bin/env bash
# battery_bench.sh -- on-device energy-per-move A/B bench across rust_threads arms.
#
# Runs the debug-only BenchService (see app/src/debug/) through an interleaved
# ABAB(C)xREPS schedule, samples battery current/voltage at ~1 Hz over adb,
# integrates joules per run, and writes a per-arm J/move table -- but ONLY if
# every run reports the identical move_hash (the play-identity witness; a
# mismatch ABORTS with no energy numbers printed).
#
# Runbook with the exact Sunday commands: BATTERY_BENCH.md (same directory).
#
# Requirements on the phone: the DEBUG apk installed, wireless debugging on,
# UNPLUGGED (the script refuses to measure a charging phone), no game running.
#
# Usage:
#   battery_bench.sh [--arms "4 2 1"] [--reps 3] [--moves 24] [--seed 424242]
#                    [--cooldown 60] [--baseline 60] [--timeout 900]
#                    [--out DIR] [--perfetto] [--dry-run]
#
#   --arms      space/comma list of rust_threads arms   (default "4 2 1")
#   --reps      interleaved cycles over the arm list    (default 3)
#   --moves     champion moves per run                  (default 24)
#   --seed      deck+agent seed (same for EVERY run --
#               that is what makes the arms comparable) (default 424242)
#   --cooldown  seconds between runs                    (default 60)
#   --baseline  idle-baseline seconds before arm 1      (default 60; 0 = skip)
#   --timeout   per-run completion timeout, seconds     (default 900)
#   --out       results dir (default measurement/battery_bench_<UTCstamp>/
#               under the repo root)
#   --perfetto  also record a perfetto trace per run IF the device advertises
#               the android.power data source (power rails / ODPM); saved as
#               an artifact, not parsed here. Degrades to a warning if absent.
#   --dry-run   validate adb/device/app/sensor state and print the plan; run nothing.
#
# Exit codes: 0 ok | 2 usage | 3 device/precondition failure | 4 run failure/timeout
#           | 5 identity-gate ABORT (hashes differ; no energy numbers printed)
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
ADB="${ADB:-${ANDROID_HOME:-$HOME/Android/Sdk}/platform-tools/adb}"
PY="${PY:-python3}"
PKG="com.jishal.carcassonne"
SVC="$PKG/.BenchService"
BATT_SYS="/sys/class/power_supply/battery"

ARMS="4 2 1"; REPS=3; MOVES=24; SEED=424242; COOLDOWN=60; BASELINE=60
TIMEOUT=900; OUT=""; PERFETTO=0; DRYRUN=0

say()  { printf '%s\n' "$*"; }
warn() { printf 'battery_bench: %s\n' "$*" >&2; }
die()  { warn "$2"; exit "$1"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --arms)     ARMS="${2//,/ }"; shift 2 ;;
    --reps)     REPS="$2"; shift 2 ;;
    --moves)    MOVES="$2"; shift 2 ;;
    --seed)     SEED="$2"; shift 2 ;;
    --cooldown) COOLDOWN="$2"; shift 2 ;;
    --baseline) BASELINE="$2"; shift 2 ;;
    --timeout)  TIMEOUT="$2"; shift 2 ;;
    --out)      OUT="$2"; shift 2 ;;
    --perfetto) PERFETTO=1; shift ;;
    --dry-run)  DRYRUN=1; shift ;;
    --help|-h)  sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die 2 "unknown argument: $1 (--help for usage)" ;;
  esac
done

[ -x "$ADB" ] || ADB="$(command -v adb || true)"
[ -n "$ADB" ] && [ -x "$ADB" ] || die 3 "no adb binary found (set \$ADB)"

# ---------------------------------------------------------------------------
# 0. connect (drifting wireless-debug port -> adb_connect.sh owns discovery)
# ---------------------------------------------------------------------------
"$HERE/adb_connect.sh" --quiet || die 3 "adb_connect.sh failed (see its exit-code contract; is wireless debugging on?)"

ashell() { "$ADB" shell "$@"; }
runas()  { "$ADB" shell run-as "$PKG" "$@"; }
dev_now_ms() { ashell 'date +%s%3N' | tr -d '\r'; }

# ---------------------------------------------------------------------------
# 1. preconditions (all of these also run under --dry-run)
# ---------------------------------------------------------------------------
say "== preconditions =="

# The app, as a DEBUG build (run-as only works on debuggable packages).
runas id >/dev/null 2>&1 || die 3 "run-as $PKG failed -- is the DEBUG apk installed?"
ashell dumpsys package "$PKG" 2>/dev/null | grep -q "BenchService" \
  || die 3 "BenchService not in the installed manifest -- installed apk predates the bench? (adb install -r app/build/outputs/apk/debug/app-debug.apk)"
say "app: debug build with BenchService present"

# UNPLUGGED, or the battery numbers measure the charger, not the workload.
BATT="$(ashell dumpsys battery | tr -d '\r')"
for src in "AC powered" "USB powered" "Wireless powered" "Dock powered"; do
  if printf '%s\n' "$BATT" | grep -q "$src: true"; then
    die 3 "phone is CHARGING ($src) -- unplug it; a charging phone measures nothing"
  fi
done
STATUS="$(printf '%s\n' "$BATT" | sed -n 's/^ *status: //p')"
[ "$STATUS" = "2" ] && die 3 "battery status=2 (charging) -- unplug the phone"
LEVEL="$(printf '%s\n' "$BATT" | sed -n 's/^ *level: //p')"
say "battery: unplugged, level ${LEVEL}%"
[ -n "$LEVEL" ] && [ "$LEVEL" -lt 30 ] && warn "battery below 30% -- voltage sag adds noise; consider charging first (then unplugging)"

# Millisecond device timestamps: the sampler and the bench windows share the
# device clock, which only works if toybox date supports %N here.
NOW_MS="$(dev_now_ms)"
case "$NOW_MS" in
  *[!0-9]*|'') die 3 "device 'date +%s%3N' returned '$NOW_MS' (no ms support?) -- the sampler cannot be aligned with the bench windows" ;;
esac
say "device clock: epoch_ms=$NOW_MS"

# The fuel-gauge sysfs nodes the sampler reads.
CUR="$(ashell cat $BATT_SYS/current_now 2>/dev/null | tr -d '\r')"
VOLT="$(ashell cat $BATT_SYS/voltage_now 2>/dev/null | tr -d '\r')"
case "$CUR" in ''|*[!0-9-]*) die 3 "cannot read $BATT_SYS/current_now (got '$CUR')" ;; esac
case "$VOLT" in ''|*[!0-9-]*) die 3 "cannot read $BATT_SYS/voltage_now (got '$VOLT')" ;; esac
say "fuel gauge: current_now=$CUR voltage_now=$VOLT (sign/units normalized in the report step)"

# Perfetto power data source (tier 2 -- optional; Pixels with ODPM rails
# advertise android.power). Detection is RUNTIME-ONLY by design.
POWER_DS=0
if ashell perfetto --query 2>/dev/null | grep -q "android.power"; then POWER_DS=1; fi
if [ "$PERFETTO" -eq 1 ] && [ "$POWER_DS" -eq 0 ]; then
  warn "perfetto android.power data source not advertised -- degrading to tier-1 (sysfs sampling only)"
  PERFETTO=0
fi
say "perfetto android.power: $([ "$POWER_DS" -eq 1 ] && echo available || echo absent)$([ "$PERFETTO" -eq 1 ] && echo ' (tracing ON)' || echo '')"

# No bench result files from a previous session to confuse the poller.
STALE="$(runas ls files/bench 2>/dev/null | tr -d '\r' | grep -c '\.json$' || true)"
[ "${STALE:-0}" -gt 0 ] && { warn "clearing $STALE stale result file(s) from files/bench/"; [ "$DRYRUN" -eq 1 ] || runas sh -c 'rm -f files/bench/*.json'; }

# The plan.
say ""
say "== plan =="
PLAN="$("$PY" "$HERE/battery_bench_lib.py" schedule --arms "$ARMS" --reps "$REPS")" \
  || die 2 "bad --arms/--reps"
N_RUNS="$(printf '%s\n' "$PLAN" | wc -l)"
printf '%s\n' "$PLAN" | while read -r rep arm tag; do
  say "  run $tag: rust_threads=$arm moves=$MOVES seed=$SEED (rep $rep)"
done
EST=$(( N_RUNS * (MOVES * 4 + COOLDOWN) + BASELINE ))
say "runs: $N_RUNS interleaved, cooldown ${COOLDOWN}s, baseline ${BASELINE}s -- rough ceiling ~$((EST / 60)) min"

if [ "$DRYRUN" -eq 1 ]; then
  say ""
  say "--dry-run: all preconditions PASS; nothing was launched."
  exit 0
fi

# ---------------------------------------------------------------------------
# 2. session setup
# ---------------------------------------------------------------------------
[ -n "$OUT" ] || OUT="$REPO/measurement/battery_bench_$(date -u +%Y%m%d_%H%M%S)"
mkdir -p "$OUT/runs" "$OUT/traces"
say ""
say "== session ($OUT) =="

# Screen off = the measurement condition (the workload is headless; the wakelock
# in BenchService keeps the CPU up).
if ashell dumpsys power | grep -qE 'mWakefulness=Awake'; then
  say "screen is on -- turning it off for the measurement"
  ashell input keyevent KEYCODE_SLEEP
fi

# batterystats cross-check: reset now, dump at the end. (Resets the device-wide
# battery-usage UI history -- acceptable on a dev phone; remove if not.)
ashell dumpsys batterystats --reset >/dev/null 2>&1 || warn "batterystats --reset failed (non-fatal)"

# ~1 Hz sampler: ONE persistent adb shell, device-clock timestamps (the same
# clock the bench result windows use, so no host/device skew enters the math).
SAMPLES="$OUT/samples.csv"
ashell "while true; do echo \"\$(date +%s%3N) \$(cat $BATT_SYS/current_now) \$(cat $BATT_SYS/voltage_now)\"; sleep 1; done" \
  > "$SAMPLES" &
SAMPLER_PID=$!
cleanup() { kill "$SAMPLER_PID" 2>/dev/null; wait "$SAMPLER_PID" 2>/dev/null; }
trap cleanup EXIT
sleep 3
[ -s "$SAMPLES" ] || die 3 "sampler produced no data"
say "sampler: pid $SAMPLER_PID -> $SAMPLES"

# Idle baseline window (screen off, app idle) -- reported and used for the
# net-J/move column.
BASE_ARG=""
if [ "$BASELINE" -gt 0 ]; then
  B0="$(dev_now_ms)"
  say "baseline: sampling ${BASELINE}s idle..."
  sleep "$BASELINE"
  B1="$(dev_now_ms)"
  BASE_ARG="--baseline $B0:$B1"
fi

# ---------------------------------------------------------------------------
# 3. the interleaved runs
# ---------------------------------------------------------------------------
run_one() { # $1=arm $2=tag
  local arm="$1" tag="$2" t_launch elapsed=0 trace_pid=""
  if [ "$PERFETTO" -eq 1 ]; then
    cat > "$OUT/traces/power.pbtxt" <<'EOF'
buffers { size_kb: 16384 fill_policy: RING_BUFFER }
data_sources { config { name: "android.power"
  android_power_config { battery_poll_ms: 250 collect_power_rails: true } } }
duration_ms: 1200000
EOF
    "$ADB" push "$OUT/traces/power.pbtxt" /data/local/tmp/carc_power.pbtxt >/dev/null
    ashell "perfetto --txt -c /data/local/tmp/carc_power.pbtxt -o /data/misc/perfetto-traces/carc_$tag.pftrace" &
    trace_pid=$!
  fi
  say "launching $tag (rust_threads=$arm)..."
  ashell am start-foreground-service -n "$SVC" \
    --ei n_moves "$MOVES" --ei rust_threads "$arm" --ei seed "$SEED" --es tag "$tag" \
    | tr -d '\r' | grep -qi error && { warn "am start failed for $tag"; return 1; }
  t_launch=$(date +%s)
  while :; do
    if runas ls "files/bench/$tag.json" >/dev/null 2>&1; then break; fi
    elapsed=$(( $(date +%s) - t_launch ))
    [ "$elapsed" -ge "$TIMEOUT" ] && { warn "TIMEOUT after ${TIMEOUT}s waiting for $tag"; return 1; }
    sleep 2
  done
  runas cat "files/bench/$tag.json" | tr -d '\r' > "$OUT/runs/$tag.json"
  if [ -n "$trace_pid" ]; then
    ashell "killall -INT perfetto" 2>/dev/null; wait "$trace_pid" 2>/dev/null
    "$ADB" pull "/data/misc/perfetto-traces/carc_$tag.pftrace" "$OUT/traces/" >/dev/null 2>&1 \
      || warn "perfetto trace pull failed for $tag (non-fatal)"
  fi
  grep -q '"ok": true' "$OUT/runs/$tag.json" \
    || { warn "$tag reported failure:"; sed -n '1,12p' "$OUT/runs/$tag.json" >&2; return 1; }
  say "  $tag done ($(grep -o '"s_per_move_mean": [0-9.]*' "$OUT/runs/$tag.json" || true))"
  return 0
}

FIRST=1
printf '%s\n' "$PLAN" | while read -r rep arm tag; do
  if [ "$FIRST" -eq 1 ]; then
    FIRST=0
  else
    say "cooldown ${COOLDOWN}s..."
    sleep "$COOLDOWN"
  fi
  run_one "$arm" "$tag" || echo "$tag" >> "$OUT/failed_runs"
done
if [ -s "$OUT/failed_runs" ]; then
  die 4 "run(s) failed/timed out: $(tr '\n' ' ' < "$OUT/failed_runs") -- see $OUT/runs/"
fi

# ---------------------------------------------------------------------------
# 4. wrap up: stop sampler, batterystats artifact, gate + report
# ---------------------------------------------------------------------------
cleanup; trap - EXIT
ashell dumpsys batterystats "$PKG" > "$OUT/batterystats.txt" 2>/dev/null \
  || warn "batterystats dump failed (non-fatal)"

say ""
say "== identity gate + energy report =="
# shellcheck disable=SC2086
if ! "$PY" "$HERE/battery_bench_lib.py" report \
      --runs-dir "$OUT/runs" --samples "$SAMPLES" $BASE_ARG --out-dir "$OUT"; then
  die 5 "identity gate ABORT or report failure -- see message above; artifacts kept in $OUT"
fi
say ""
say "artifacts: $OUT (results.md, results.json, samples.csv, runs/, batterystats.txt$( [ "$PERFETTO" -eq 1 ] && echo ', traces/' ))"
