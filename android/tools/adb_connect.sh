#!/usr/bin/env bash
# One-command `adb` connect to Joshua's Pixel for E4 game-archive pulls.
#
# The wireless-debugging CONNECT PORT drifts every time wireless debugging is
# toggled on the device, so this script finds it instead of making you hunt.
# Order of attempts:  cached last-known port  ->  mDNS  ->  TCP port scan.
#
# ---------------------------------------------------------------------------
# TWO INDEPENDENT PROBLEMS -- do not conflate them:
#   DISCOVERY = "which port is the device listening on today?"  (this script)
#   PAIRING   = "does the device trust this host's client cert?" (needs Joshua
#               at the phone, one time per host).  A connect can reach the
#               device, get a well-formed STLS, and still be rejected at the
#               TLS handshake.  This script DETECTS that and prints the exact
#               on-device remedy rather than looping.  See exit code 4.
# ---------------------------------------------------------------------------
#
# Exit codes:
#   0  connected (device online in `adb devices`)
#   2  usage error
#   3  no open wireless-debug port found (phone asleep? wireless debugging off?)
#   4  reached the device but the TLS cert was REJECTED -> needs `adb pair`
#   5  some other adb failure (message is printed verbatim)
#
# Companion doc: ../README.md ("Wireless adb" section).

set -uo pipefail   # deliberately NOT -e: adb connect exits 0 on failure and we
                   # branch on its TEXT, so we handle return codes explicitly.

# --------------------------------------------------------------------------
# defaults
# --------------------------------------------------------------------------
DEFAULT_IP="100.64.4.100"          # Pixel over tailscale
DEFAULT_RANGE="30000-50000"        # observed wireless-debug ephemeral range
DEFAULT_TIMEOUT="0.5"              # per-port TCP connect timeout, seconds
# Bounded parallelism. Be polite to the phone: this is a burst of SYNs at it.
#
# MEASURED 2026-08-12: 20,001 ports (30000-50000) at JOBS=200, TIMEOUT=0.5 took
# 53.0s. That matches scan_time ~= (range_size / JOBS) * TIMEOUT almost exactly
# (predicted 50s), which tells you the important thing: closed ports on the
# tailnet DROP the SYN rather than sending an RST, so every miss costs the full
# timeout. Scan cost is therefore linear in the range and inversely linear in
# JOBS -- raise CARC_ADB_SCAN_JOBS if you want it faster and don't mind the
# bigger burst. In practice the port cache means you rarely scan at all.
SCAN_JOBS="${CARC_ADB_SCAN_JOBS:-200}"

ADB="${ADB:-${ANDROID_HOME:-$HOME/Android/Sdk}/platform-tools/adb}"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/carc"

IP="$DEFAULT_IP"
RANGE="$DEFAULT_RANGE"
TIMEOUT="$DEFAULT_TIMEOUT"
QUIET=0

# --------------------------------------------------------------------------
# tiny logging helpers
# --------------------------------------------------------------------------
say()  { [ "$QUIET" -eq 1 ] || printf '%s\n' "$*"; }
warn() { printf '%s\n' "$*" >&2; }

usage() {
  cat <<'EOF'
adb_connect.sh -- find the Pixel's drifting wireless-debug port and connect.

Usage:
  adb_connect.sh [--ip ADDR] [--port-range LO-HI] [--timeout SEC] [--quiet]

  --ip ADDR          device address        (default 100.64.4.100, tailnet)
  --port-range LO-HI wireless-debug range  (default 30000-50000; "PORT" alone
                     probes exactly one port)
  --timeout SEC      per-port TCP connect timeout (default 0.5)
  --quiet            only print the final device line or the error
  --help             this text

mDNS caveat (please don't re-litigate this):
  `adb mdns services` is tried first and is FREE, but it returns an empty list
  from this box and always will -- mDNS is link-local multicast (224.0.0.251)
  which neither traverses tailscale nor reaches the WSL2 VM behind Windows NAT.
  It is kept only because it WOULD work if this ever ran on the phone's own L2.

Exit codes: 0 connected | 2 usage | 3 no port found | 4 needs pairing | 5 other
EOF
}

# ==========================================================================
# PURE FUNCTIONS  (unit-tested via --selftest-fn; see tests/test_adb_connect.py)
# ==========================================================================

# parse_port_range SPEC -> prints "LO HI" on stdout, rc 0
# Accepts "30000-50000" or a bare "44749". rc 1 (with a message on stderr) if
# malformed, non-numeric, out of 1..65535, or reversed.
parse_port_range() {
  local spec="${1-}" lo hi
  case "$spec" in
    '')
      warn "port-range: empty"; return 1 ;;
    *-*)
      lo="${spec%%-*}"; hi="${spec#*-}" ;;
    *)
      lo="$spec"; hi="$spec" ;;
  esac
  # Reject anything that is not a plain non-empty run of digits. Check lo and hi
  # SEPARATELY: concatenating them first lets a half-open "30000-" or "-50000"
  # through (one side is empty, the join still looks all-digit) and the empty
  # side then blows up in the numeric comparisons below.
  case "$lo" in ''|*[!0-9]*) warn "port-range: not numeric: '$spec'"; return 1 ;; esac
  case "$hi" in ''|*[!0-9]*) warn "port-range: not numeric: '$spec'"; return 1 ;; esac
  if [ "$lo" -lt 1 ] || [ "$hi" -gt 65535 ]; then
    warn "port-range: out of 1..65535: '$spec'"; return 1
  fi
  if [ "$lo" -gt "$hi" ]; then
    warn "port-range: reversed (lo > hi): '$spec'"; return 1
  fi
  printf '%s %s\n' "$lo" "$hi"
}

# parse_mdns_services  -- reads `adb mdns services` output on stdin, prints one
# "HOST:PORT" per line for every _adb-tls-connect._tcp entry.
#
# Deliberately whitespace/column-order tolerant: it keys off the service-type
# token and then takes the last HOST:PORT-shaped token on the line. adb 37's
# mdns list is emitted by the Rust mdns bridge and its exact column layout is
# not recoverable from the binary, so we do not hard-code a column index.
# Pairing endpoints (_adb-tls-pairing._tcp) are IGNORED -- you cannot `connect`
# to those, and treating one as a connect port is a classic time-waster.
parse_mdns_services() {
  local line tok found
  while IFS= read -r line; do
    case "$line" in
      *_adb-tls-connect._tcp*) ;;
      *) continue ;;
    esac
    found=""
    for tok in $line; do
      # HOST:PORT where PORT is all digits and HOST is non-empty
      case "$tok" in
        *:*)
          local h="${tok%:*}" p="${tok##*:}"
          case "$p" in ''|*[!0-9]*) continue ;; esac
          [ -n "$h" ] || continue
          case "$h" in *_adb-tls*) continue ;; esac   # not the service type
          found="$tok" ;;
      esac
    done
    [ -n "$found" ] && printf '%s\n' "$found"
  done
  return 0
}

# classify_connect_output  -- reads combined stdout+stderr of `adb connect` on
# stdin, prints exactly one of: connected | no-port | cert-rejected | other
#
# WHY TEXT AND NOT EXIT CODE: `adb connect` exits 0 even when it fails
# (verified 2026-08-12, adb 37.0.0). The return code carries no information.
#
# The discriminator between "nothing there" and "there but untrusted" is the
# SHAPE of the failure line, which comes from two different adb format strings:
#   "failed to connect to '%s:%d': %s"  <- socket-level: QUOTED host, has reason
#   "failed to connect to %s"           <- post-TCP: UNQUOTED host, no reason
# The unquoted form means the TCP connect SUCCEEDED and we died later, in the
# TLS handshake -- i.e. the device is right there and refused our client cert.
classify_connect_output() {
  local out
  out="$(cat)"
  case "$out" in
    *"connected to "*)
      # covers both "connected to H:P" and "already connected to H:P"
      case "$out" in
        *"failed to connect"*) ;;      # fall through to the failure cases
        *) printf 'connected\n'; return 0 ;;
      esac ;;
  esac
  case "$out" in
    # QUOTED host + reason => never got a TCP session => wrong/closed port.
    *"failed to connect to '"*) printf 'no-port\n'; return 0 ;;
    # explicit auth failure
    *"failed to authenticate to "*) printf 'cert-rejected\n'; return 0 ;;
    # UNQUOTED host, no reason => TCP fine, handshake failed => cert rejected.
    *"failed to connect to "*) printf 'cert-rejected\n'; return 0 ;;
  esac
  printf 'other\n'
}

# ==========================================================================
# impure helpers
# ==========================================================================

# adb_server_log_path -- where the adb SERVER writes its trace log. The
# SSLV3_ALERT_CERTIFICATE_UNKNOWN line lands there, never on the client's
# stderr, so this is our positive confirmation of a cert rejection.
adb_server_log_path() { printf '%s/adb.%s.log\n' "${TMPDIR:-/tmp}" "$(id -u)"; }

# adb_log_size -- byte size of the server log right now (0 if absent). Taken
# BEFORE a connect attempt so confirm_cert_rejection can read only the bytes
# that attempt produced. Without this, a TLS alert left over from an EARLIER
# attempt makes every later failure read as "confirmed" -- caught in testing
# 2026-08-12 when a connect to a non-adbd port was falsely confirmed.
adb_log_size() {
  local log; log="$(adb_server_log_path)"
  [ -r "$log" ] && stat -c %s "$log" 2>/dev/null || printf '0\n'
}

# confirm_cert_rejection OFFSET -- looks only at log bytes written after
# OFFSET. Prints "confirmed" (a TLS alert for this very attempt) or
# "inferred" (failure SHAPE says post-TCP, but no log evidence).
confirm_cert_rejection() {
  local off="${1:-0}" log; log="$(adb_server_log_path)"
  if [ -r "$log" ] && tail -c "+$((off + 1))" "$log" 2>/dev/null \
       | grep -qE 'SSLV3_ALERT_CERTIFICATE_UNKNOWN|Handshake failed'; then
    printf 'confirmed\n'
  else
    printf 'inferred\n'
  fi
}

# online_device -- prints the "HOST:PORT device ..." line if any device is in
# state `device`, rc 1 otherwise.
online_device() {
  local line
  while IFS= read -r line; do
    case "$line" in
      'List of devices attached'*|'') continue ;;
      *[[:space:]]device|*[[:space:]]device[[:space:]]*) printf '%s\n' "$line"; return 0 ;;
    esac
  done < <("$ADB" devices -l 2>/dev/null)
  return 1
}

# probe_port IP PORT TIMEOUT -- rc 0 if the TCP port accepts a connection.
probe_port() {
  local ip="$1" port="$2" tmo="$3"
  if [ "$HAVE_DEVTCP" -eq 1 ]; then
    timeout "$tmo" bash -c 'exec 3<>/dev/tcp/"$1"/"$2"' _ "$ip" "$port" 2>/dev/null
  else
    nc -z -w 1 "$ip" "$port" >/dev/null 2>&1
  fi
}

# scan_range IP LO HI TIMEOUT -- prints the first open port found, rc 1 if none.
# Bounded parallelism via xargs -P; `head -n1` SIGPIPEs the fan-out so we stop
# as soon as we have a hit instead of grinding through the whole range.
scan_range() {
  local ip="$1" lo="$2" hi="$3" tmo="$4" hit
  if [ "$HAVE_DEVTCP" -eq 1 ]; then
    hit="$(seq "$lo" "$hi" | xargs -P "$SCAN_JOBS" -n1 -I{} \
             timeout "$tmo" bash -c \
             'exec 3<>/dev/tcp/"$1"/"$2" && echo "$2"' _ "$ip" {} \
           2>/dev/null | head -n1)"
  else
    hit="$(seq "$lo" "$hi" | xargs -P "$SCAN_JOBS" -n1 -I{} \
             bash -c 'nc -z -w 1 "$1" "$2" >/dev/null 2>&1 && echo "$2"' _ "$ip" {} \
           2>/dev/null | head -n1)"
  fi
  [ -n "$hit" ] || return 1
  printf '%s\n' "$hit"
}

cache_file() { printf '%s/adb_connect_port_%s\n' "$CACHE_DIR" "$IP"; }
cache_read()  { local f; f="$(cache_file)"; [ -r "$f" ] && cat "$f" 2>/dev/null; }
cache_write() { local f; f="$(cache_file)"; mkdir -p "$CACHE_DIR" 2>/dev/null && printf '%s\n' "$1" >"$f" 2>/dev/null || true; }

# try_connect IP:PORT -- runs adb connect, echoes the classification.
try_connect() {
  "$ADB" connect "$1" 2>&1 | classify_connect_output
}

print_pairing_remedy() {
  local host="$1" port="$2" confirm="$3"
  cat >&2 <<EOF

=========================================================================
 PAIRING REQUIRED -- discovery worked, trust did not.  ($confirm)
=========================================================================
EOF
  if [ "$confirm" = confirmed ]; then
    cat >&2 <<EOF
The device is alive and listening on ${host}:${port}: it completed the TCP
connect and sent a well-formed STLS, then rejected THIS HOST's client
certificate (SSLV3_ALERT_CERTIFICATE_UNKNOWN, read from the adb server log
for this very attempt). No amount of reconnecting or port-scanning will fix
that -- only the on-device pairing flow will, and it needs someone at the phone.
EOF
  else
    cat >&2 <<EOF
Something on ${host}:${port} accepted the TCP connect and then failed the adb
handshake. That failure SHAPE is the cert-rejection signature, but the adb
server log showed no TLS alert for this attempt, so it is INFERRED -- it could
also be some non-adbd service occupying that port. If the remedy below does not
apply, re-run with a narrower --port-range.
EOF
  fi
  cat >&2 <<EOF

ON THE PHONE:
  Settings -> System -> Developer options -> Wireless debugging
          -> "Pair device with pairing code"

That dialog shows a DIFFERENT port (the PAIRING port, not ${port}) and a
6-digit code. With those, on this box:

  ${ADB} pair ${host}:<PAIRING_PORT> <6_DIGIT_CODE>

Then re-run this script -- pairing is one-time per host, and the connect
port is allowed to keep drifting afterwards:

  $0

=========================================================================
EOF
}

# ==========================================================================
# --selftest-fn dispatcher
#
# The pure functions above are the contract worth testing, and they are
# written in bash -- so the tests call THEM, through this dispatcher, rather
# than a Python re-implementation that could silently drift from the shell
# that actually ships. Stdin is passed through unchanged.
# ==========================================================================
if [ "${1-}" = "--selftest-fn" ]; then
  fn="${2-}"
  case "$fn" in
    parse_port_range|parse_mdns_services|classify_connect_output) ;;
    *) warn "--selftest-fn: not an exported pure function: '$fn'"; exit 2 ;;
  esac
  shift 2
  "$fn" "$@"
  exit $?
fi

# ==========================================================================
# argument parsing
# ==========================================================================
while [ $# -gt 0 ]; do
  case "$1" in
    --ip)          IP="${2-}";      [ -n "$IP" ] || { warn "--ip needs a value"; exit 2; }; shift 2 ;;
    --port-range)  RANGE="${2-}";   [ -n "$RANGE" ] || { warn "--port-range needs a value"; exit 2; }; shift 2 ;;
    --timeout)     TIMEOUT="${2-}"; [ -n "$TIMEOUT" ] || { warn "--timeout needs a value"; exit 2; }; shift 2 ;;
    --quiet|-q)    QUIET=1; shift ;;
    --help|-h)     usage; exit 0 ;;
    *)             warn "unknown argument: '$1'"; usage >&2; exit 2 ;;
  esac
done

read -r LO HI < <(parse_port_range "$RANGE") || exit 2
[ -n "${LO:-}" ] || { warn "port-range: could not parse '$RANGE'"; exit 2; }

[ -x "$ADB" ] || { warn "adb not found or not executable at: $ADB (set ADB= or ANDROID_HOME=)"; exit 2; }

# does this bash have /dev/tcp? (Ubuntu's does; a --enable-net-redirections-less
# build would not, and then we fall back to nc)
if (exec 3<>/dev/tcp/127.0.0.1/1) 2>/dev/null; then HAVE_DEVTCP=1
elif timeout 1 bash -c 'exec 3<>/dev/tcp/127.0.0.1/1' 2>&1 | grep -q 'Connection refused'; then HAVE_DEVTCP=1
elif command -v nc >/dev/null 2>&1; then HAVE_DEVTCP=0
else HAVE_DEVTCP=1; fi

# ==========================================================================
# 1. already connected? -- idempotent fast path
# ==========================================================================
if dev="$(online_device)"; then
  say "already connected:"
  printf '%s\n' "$dev"
  exit 0
fi

FOUND_PORT=""
SOURCE=""

# ==========================================================================
# 2. cached last-known port -- one connect, no scan, covers the common case
# ==========================================================================
if cached="$(cache_read)" && [ -n "$cached" ]; then
  # Honour an explicit --port-range: a cached port outside the requested range
  # must not silently hijack the run.
  if [ "$cached" -ge "$LO" ] 2>/dev/null && [ "$cached" -le "$HI" ] 2>/dev/null; then
    say "trying cached port $cached ..."
    if probe_port "$IP" "$cached" "$TIMEOUT"; then
      FOUND_PORT="$cached"; SOURCE="cache"
    else
      say "  cached port $cached is closed (it drifted) -- rediscovering"
    fi
  else
    say "  ignoring cached port $cached (outside requested range $LO-$HI)"
  fi
fi

# ==========================================================================
# 3. mDNS -- free, and structurally empty from this box (see --help)
# ==========================================================================
if [ -z "$FOUND_PORT" ]; then
  say "trying mDNS ..."
  mdns_ep="$("$ADB" mdns services 2>/dev/null | parse_mdns_services | head -n1)"
  if [ -n "$mdns_ep" ]; then
    say "  mDNS advertised $mdns_ep"
    IP="${mdns_ep%:*}"; FOUND_PORT="${mdns_ep##*:}"; SOURCE="mdns"
  else
    say "  mDNS returned no _adb-tls-connect endpoint (expected here: multicast"
    say "  crosses neither tailscale nor the WSL2 NAT -- see --help)"
  fi
fi

# ==========================================================================
# 4. TCP scan of the wireless-debug range
# ==========================================================================
if [ -z "$FOUND_PORT" ]; then
  say "scanning $IP ports $LO-$HI (timeout ${TIMEOUT}s, ${SCAN_JOBS} parallel) ..."
  t0=$(date +%s.%N)
  hit="$(scan_range "$IP" "$LO" "$HI" "$TIMEOUT")"
  rc=$?
  t1=$(date +%s.%N)
  elapsed="$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.1f", b-a}')"
  if [ $rc -ne 0 ] || [ -z "$hit" ]; then
    say "  scan finished in ${elapsed}s -- no open port in $LO-$HI"
    warn ""
    warn "No wireless-debug port found on $IP."
    warn "Check on the phone: Settings -> System -> Developer options ->"
    warn "Wireless debugging is ON (it turns itself off on some reboots), and"
    warn "the phone is awake and on the tailnet."
    exit 3
  fi
  say "  found open port $hit in ${elapsed}s"
  FOUND_PORT="$hit"; SOURCE="scan"
fi

# ==========================================================================
# 5. connect + classify
#
# Two passes at most. The second exists for one specific real failure: the adb
# server can hold a STALE OFFLINE TRANSPORT for this endpoint (very easy to hit
# with a drifting port), and then `adb connect` cheerfully answers "already
# connected" while `adb devices` shows `offline` forever. `adb disconnect`
# clears it and the next connect is a real one.
# ==========================================================================
for attempt in 1 2; do
  say "adb connect $IP:$FOUND_PORT (via $SOURCE) ..."
  LOG_OFFSET="$(adb_log_size)"
  verdict="$(try_connect "$IP:$FOUND_PORT")"

  case "$verdict" in
    connected)
      cache_write "$FOUND_PORT"
      if dev="$(online_device)"; then
        say "connected:"
        printf '%s\n' "$dev"
        exit 0
      fi
      if [ "$attempt" -eq 1 ]; then
        say "  adb says connected but the transport is not online -- clearing a"
        say "  stale transport with 'adb disconnect' and retrying once"
        "$ADB" disconnect "$IP:$FOUND_PORT" >/dev/null 2>&1 || true
        continue
      fi
      # Persisted after a disconnect+retry: genuinely odd (e.g. `unauthorized`).
      warn "adb reported a connection but no device is online:"
      "$ADB" devices -l >&2
      exit 5
      ;;
    cert-rejected)
      cache_write "$FOUND_PORT"  # the PORT is right; it's the trust that's missing
      confirm="$(confirm_cert_rejection "$LOG_OFFSET")"
      print_pairing_remedy "$IP" "$FOUND_PORT" "$confirm"
      exit 4
      ;;
    no-port)
      warn "port $FOUND_PORT closed between the probe and the connect (it drifted mid-run)."
      warn "Re-run to rescan."
      exit 3
      ;;
    *)
      warn "adb connect failed in an unrecognised way. Raw adb output:"
      "$ADB" connect "$IP:$FOUND_PORT" 2>&1 >&2
      exit 5
      ;;
  esac
done

warn "exhausted connect attempts to $IP:$FOUND_PORT"
exit 5
