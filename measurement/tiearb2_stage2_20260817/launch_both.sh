#!/usr/bin/env bash
# =============================================================================
# tiearb2 STAGE 2 PHASE B — TWO-BOX LAUNCHER (bundle sync + wheel rebuild + the
# per-box detached driver).
#
#   launch_both.sh <BAND_SEED_START>
#
# ⚠️ THE BAND IS A PARAMETER AND THIS SCRIPT NEVER CLAIMS ONE. The orchestrator
# runs `scripts/classical_search/claim_next_band.py` immediately before game 1
# and passes the result in. `G-BAND` voids a run whose band was not claimed
# before game 1.
#
# What it does, in order, and why each step is here:
#   1. Census both boxes (a timing-sensitive cell is an EXCLUSIVE tenant).
#   2. FULL (not shallow) git bundle sync to the laptop. A shallow bundle gives a
#      parentless `code_rev`, which makes the manifest's provenance unreadable.
#   3. Rebuild the `carc_rs` wheel on EACH box at the SAME toolchain
#      (RUSTUP_TOOLCHAIN from WORKERS.conf) — READ_RULE `G-TOOL`. A new wheel is
#      exactly the situation the per-box positive control exists for.
#   4. Launch `run_cells.sh` DETACHED on each box (`setsid nohup ... & disown`).
#      The laptop leg is PIPED (`ssh laptop 'bash -s' < ...`), never an inline
#      `ssh laptop 'cd X && ...'` — Claude Code silently strips `cd` from inline
#      SSH commands, a documented failure mode.
#
# It does NOT wait, does NOT read a summary, and adjudicates NOTHING. The
# completion watch is the orchestrator's: `DONE_<cell>` / `FAILED_<cell>` markers
# in this directory, and `watch_cells.sh` for a rolling view.
# =============================================================================
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/WORKERS.conf"

BAND="${1:?usage: launch_both.sh <BAND_SEED_START>}"
case "$BAND" in ''|*[!0-9]*) echo "BAND must be numeric, got '$BAND'"; exit 2 ;; esac

REPO="$REPO_LOCAL"
cd "$REPO" || { echo "FATAL: cannot cd to '$REPO'" >&2; exit 1; }
LOGS="$HERE/logs"
mkdir -p "$LOGS"
ts() { date +%F_%T; }
log() { echo "[launch $(ts)] $*"; }

log "=== tiearb2 STAGE 2 PHASE B, band $BAND ==="
log "cells: $CELL_ARB (argmax) + $CELL_RND (random), n=$N_GAMES paired each, same decks"

# ---- 1. census -------------------------------------------------------------
log "--- census: local ---"
ps -o pid,etime,%cpu,comm -C python --sort=-etime 2>/dev/null | head -15
cat /proc/loadavg
log "--- census: laptop ---"
ssh laptop-wsl 'ps -o pid,etime,%cpu,comm -C python --sort=-etime | head -15; cat /proc/loadavg' || \
  { log "FATAL: laptop unreachable — fix the box before launching a 2-box cell"; exit 4; }

# ---- 2. FULL bundle sync ---------------------------------------------------
BUNDLE="$SHARE_LOCAL/bundles/tiearb2_stage2_$(git rev-parse --short HEAD).bundle"
mkdir -p "$SHARE_LOCAL/bundles"
log "--- full git bundle -> $BUNDLE ---"
git bundle create "$BUNDLE" --all || { log "FATAL: bundle create failed"; exit 5; }
log "bundle bytes: $(stat -c %s "$BUNDLE")"

REV="$(git rev-parse HEAD)"
cat > "$LOGS/_sync_laptop.sh" <<EOF
cd $REPO_REMOTE || exit 1
set -u
git fetch "$SHARE_REMOTE/bundles/$(basename "$BUNDLE")" '+refs/heads/*:refs/remotes/bundle/*' || exit 6
git reset --hard $REV || exit 7
# ⚠️ A NON-INTERACTIVE ssh shell does NOT get rustup on PATH (the profile that
# adds it is only sourced for login/interactive shells), so a bare
# \`maturin develop\` dies with "rustc ... is not installed or not in PATH" —
# observed on this exact box 2026-08-17. Source it explicitly.
[ -f "\$HOME/.cargo/env" ] && . "\$HOME/.cargo/env"
export PATH="\$HOME/.cargo/bin:\$PATH"
export RUSTUP_TOOLCHAIN=$RUST_TOOLCHAIN
rustc --version || exit 5
nice -n $NICE $REPO_REMOTE/.venv/bin/maturin develop --release -m rust/carc/carc-py/Cargo.toml || exit 8
git -C $REPO_REMOTE rev-parse --short HEAD
$REPO_REMOTE/.venv/bin/python -c 'import carc_rs;print("carc_rs", carc_rs.__version__, hasattr(carc_rs.MirrorState,"tiearb_probe"))'
EOF
log "--- laptop: sync + wheel rebuild (piped script; NEVER an inline ssh cd) ---"
ssh laptop-wsl 'bash -s' < "$LOGS/_sync_laptop.sh" || { log "FATAL: laptop sync/build failed"; exit 6; }

# ---- 3. local wheel rebuild ------------------------------------------------
log "--- local: wheel rebuild at RUSTUP_TOOLCHAIN=$RUST_TOOLCHAIN ---"
RUSTUP_TOOLCHAIN="$RUST_TOOLCHAIN" nice -n "$NICE" "$REPO/.venv/bin/maturin" \
  develop --release -m rust/carc/carc-py/Cargo.toml >> "$LOGS/build_local.log" 2>&1 || {
    log "FATAL: local wheel rebuild failed — see $LOGS/build_local.log"; exit 8; }

# ---- 4. detached launches --------------------------------------------------
log "--- launching DETACHED on local (W=$W_LOCAL) ---"
setsid nohup nice -n "$NICE" bash "$HERE/run_cells.sh" local "$BAND" "$W_LOCAL" \
  > "$LOGS/driver_local.log" 2>&1 < /dev/null &
disown
log "local driver pid $!"

cat > "$LOGS/_launch_laptop.sh" <<EOF
cd $REPO_REMOTE || exit 1
mkdir -p $REPO_REMOTE/measurement/$RUN_ID/logs
setsid nohup nice -n $NICE bash $REPO_REMOTE/measurement/$RUN_ID/run_cells.sh laptop $BAND $W_LAPTOP \
  > $REPO_REMOTE/measurement/$RUN_ID/logs/driver_laptop.log 2>&1 < /dev/null &
disown
echo "laptop driver launched"
EOF
log "--- launching DETACHED on laptop (W=$W_LAPTOP) ---"
# ⚠️ A synchronous `ssh host "job &"` can HANG and starve every box launched
# after it — background the LAUNCH CALL itself, and treat a `timeout` rc=124 as
# LAUNCHED (never retry: retries stack pools).
timeout 120 ssh laptop-wsl 'bash -s' < "$LOGS/_launch_laptop.sh"
lrc=$?
[ "$lrc" -eq 124 ] && log "laptop launch returned 124 from timeout — treat as LAUNCHED, do NOT retry"
log "laptop launch rc=$lrc"

log "=== LAUNCHED. Nothing adjudicated. Watch $HERE/DONE_* and $HERE/FAILED_*, or run watch_cells.sh ==="
