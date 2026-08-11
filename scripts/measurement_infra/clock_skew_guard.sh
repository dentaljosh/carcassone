#!/usr/bin/env bash
# ============================================================================
# clock_skew_guard.sh — shared CLOCK-SKEW GUARD for every --shared-claim run.
#
# WHY THIS EXISTS (the live incident, 2026-07-30 23:26).
#   `carcassonne_ai/claim.py:is_stale()` compares a claim file's mtime — which,
#   on the CIFS share, is the SERVER's clock (the Windows host that exports
#   /mnt/c) — against the CLIENT's own `time.time()`. A client whose clock runs
#   FAST by more than `--claim-stale-secs` therefore sees EVERY claim on the
#   share as stale, INCLUDING claims a sibling box is actively working, and
#   steals them all instead of picking up unclaimed work.
#
#   Observed shape: the laptop's WSL2 clock had drifted +11697 s (3 h 15 m)
#   after a host sleep; within 3 minutes ALL 16 of the local box's fresh claims
#   had been re-owned by the laptop, so both boxes were computing the SAME
#   seeds and two-box work-stealing was silently worth ~1 box.
#
#   Nothing crashes and nothing warns: duplicate work is "harmless" by
#   claim.py's own contract, so the only symptom is missing throughput. Hence
#   this guard REFUSES TO START rather than run at half speed for a night.
#
# HOW IT MEASURES.
#   Write a zero-byte probe file into the run's output directory (on the share),
#   read the mtime the SERVER stamped on it, subtract from this box's `date`.
#   A positive skew means THIS BOX IS AHEAD of the share — the dangerous
#   direction, the one that steals claims. Negative (this box behind) is also
#   refused: it means this box's own claims look stale to it instantly.
#
# HOW TO WIRE IT INTO A LAUNCHER (the stanza; keep it near the top):
#
#   # ---- clock-skew guard (shared) — scripts/measurement_infra/clock_skew_guard.sh
#   _CSG="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   while [ ! -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] && [ "$_CSG" != / ]; do _CSG=$(dirname "$_CSG"); done
#   . "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" || { echo "FATAL: clock_skew_guard.sh not found"; exit 3; }
#   carc_clock_skew_guard
#
#   `carc_clock_skew_guard` takes an OPTIONAL directory to probe. With no
#   argument it probes `$OUT_ROOT` if the caller has already set one, else the
#   auto-detected share mount (`/mnt/c/carc-shared` locally, `/mnt/carc-shared`
#   inside an ssh to a remote box). Probing the share root is the CONSERVATIVE
#   default: it checks the clock relationship that actually governs claims even
#   when the launcher has not resolved its own output path yet.
#
# ENVIRONMENT.
#   CARC_CLOCK_SKEW_MAX      abort above this many seconds of |skew| (default 60)
#   CARC_CLOCK_TAG           prefix for the log lines (default: the caller's $0)
#   CARC_CLOCK_SKEW_DISABLE  set to 1 to skip the guard — prints a loud WARNING.
#                            Exists so nobody deletes the guard line outright;
#                            do not set it for a multi-box run.
#
# API (all safe under `set -euo pipefail`):
#   carc_clock_skew_seconds [dir]  echo the signed skew in seconds; rc 2 = unmeasurable
#   carc_clock_skew_check   [dir]  log + rc 0 (ok/unchecked) or rc 3 (skewed)
#   carc_clock_skew_guard   [dir]  carc_clock_skew_check, then `exit 3` on failure
#
# NOT a strength lever — this is measurement/cluster plumbing. Tests:
# tests/test_clock_skew_guard.py.
# ============================================================================

# The two donors that pioneered this guard keep their own inline copies on
# purpose (scripts/classical_search/leaf_ablation_launcher.sh and
# capscurve_resweep_launcher.sh) — they were live when this lib was hoisted.
# The semantics here are theirs; a later cleanup can dedupe them.

carc_clock_skew_default_dir() {
    # Echo the directory to probe. Empty output = nothing sensible to probe.
    if [ -n "${1:-}" ]; then printf '%s\n' "$1"; return 0; fi
    if [ -n "${OUT_ROOT:-}" ]; then printf '%s\n' "$OUT_ROOT"; return 0; fi
    local d
    for d in /mnt/c/carc-shared /mnt/carc-shared; do
        if [ -d "$d" ]; then printf '%s\n' "$d"; return 0; fi
    done
    printf '\n'
}

_carc_stat_mtime() {
    # GNU coreutils first, BSD/macOS second (the M5 bench box is in the cluster).
    stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null
}

_carc_mount_source() {
    # Best-effort: name the server that owns the mtime clock, for the message.
    command -v findmnt >/dev/null 2>&1 || return 0
    findmnt -no SOURCE --target "$1" 2>/dev/null || true
}

carc_clock_skew_seconds() {
    # echo signed skew (this box's clock MINUS the probed filesystem's clock).
    # rc 0 = measured, rc 2 = could not measure (caller should warn, not abort).
    local dir probe mtime now
    dir="$(carc_clock_skew_default_dir "${1:-}")"
    [ -n "$dir" ] || return 2
    mkdir -p "$dir" 2>/dev/null || return 2
    probe="$dir/.clock_probe_$$_${RANDOM:-0}"
    : > "$probe" 2>/dev/null || return 2
    mtime="$(_carc_stat_mtime "$probe")"
    now="$(date +%s)"
    rm -f "$probe" 2>/dev/null || true
    [ -n "$mtime" ] || return 2
    printf '%s\n' "$(( now - mtime ))"
}

carc_clock_skew_check() {
    # rc 0 = clock OK (or unmeasurable — warn and continue), rc 3 = skewed.
    local dir tag maxskew skew rc askew src host
    dir="$(carc_clock_skew_default_dir "${1:-}")"
    tag="${CARC_CLOCK_TAG:-$(basename "${0:-clock-skew}")}"
    maxskew="${CARC_CLOCK_SKEW_MAX:-60}"
    host="$(hostname 2>/dev/null || echo unknown-host)"

    if [ "${CARC_CLOCK_SKEW_DISABLE:-0}" = "1" ]; then
        echo "[$tag $host] WARNING: clock-skew guard DISABLED via CARC_CLOCK_SKEW_DISABLE=1."
        echo "  A fast clock on this box will steal every sibling box's live claims silently."
        return 0
    fi

    # `|| rc=$?` keeps this safe under `set -e` WITHOUT touching the caller's
    # shell options (toggling `set +e`/`set -e` here would silently ENABLE -e
    # for a launcher that deliberately runs without it).
    rc=0
    skew="$(carc_clock_skew_seconds "$dir")" || rc=$?

    if [ "$rc" -ne 0 ] || [ -z "$skew" ]; then
        echo "[$tag $host] WARNING: could not write a clock probe to '${dir:-<no share mount found>}' — skew UNCHECKED."
        return 0
    fi

    askew="${skew#-}"
    if [ "$askew" -gt "$maxskew" ]; then
        src="$(_carc_mount_source "$dir")"
        echo "[$tag $host] FATAL: clock skew vs the share's mtime clock = ${skew}s (limit ${maxskew}s)."
        echo "  probed dir : $dir${src:+   (mounted from $src)}"
        if [ "$skew" -gt 0 ]; then
            echo "  THIS BOX ($host) IS AHEAD of the share's clock by ${askew}s."
            echo "  It would treat every sibling box's LIVE claim as stale and steal it"
            echo "  (claim.py:is_stale compares SERVER mtime to CLIENT time.time()), so the"
            echo "  cluster would silently collapse to one box's worth of throughput."
        else
            echo "  THIS BOX ($host) IS BEHIND the share's clock by ${askew}s."
            echo "  Its own fresh claims would read as stale and be re-stolen immediately."
        fi
        echo "  Fix the clock on $host, then relaunch, e.g.:"
        echo "    sudo -n date -s @\$(ssh <box-that-exports-the-share> date +%s)"
        echo "  (WSL2 clocks drift after a host sleep and hwclock is absent there.)"
        return 3
    fi

    echo "[$tag $host] clock-skew guard OK (${skew}s vs $dir)"
    return 0
}

carc_clock_skew_guard() {
    # The one-call form for launchers: abort the run rather than degrade it.
    carc_clock_skew_check "${1:-}" || exit 3
}
