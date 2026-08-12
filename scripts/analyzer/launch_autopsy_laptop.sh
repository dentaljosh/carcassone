#!/usr/bin/env bash
# Launch the E4 autopsy SCORING run (measurement/e4_autopsy_20260812/DESIGN.md §10) on the
# LAPTOP at W22, detached + watchdogged. OWNER-GATED: run only after Joshua picks box+scope.
#
#   launch_autopsy_laptop.sh [fixed_v1|all] [both|primary]     (defaults: fixed_v1 both)
#
# What it does, in order:
#   1. cuts a git bundle of android-app onto the share (remotes can't reach github;
#      running stale code on the laptop = contamination),
#   2. pipes a remote script to the laptop (cd on line 1 — inline `ssh host 'cd ..'`
#      gets the cd stripped in transit, so never that form) which:
#      - guards against WSL clock drift (>300 s vs the just-written bundle aborts),
#      - fetches the bundle + hard-resets the repo to it,
#      - CLEARS ok=false oracle records under the out-root (the local smoke left 4
#        wall-capped ok=false records in the exact records/ dir resume reads; resume
#        SKIPS failed records silently — DESIGN §7 — so they must go before launch;
#        ok=true smoke records are valid completions and are kept),
#      - builds the fixed_v1-only sample if that scope was chosen,
#      - writes RUN_CMD.sh (the exact scoring command + DONE/FAILED markers),
#      - launches it detached under `systemd-run --user --scope -p MemoryMax=8G`
#        (laptop VM has 11 GB; an uncapped guest ballooning vmmem is the documented
#        teardown mechanism; user linger is enabled so the scope survives ssh exit),
#      - arms the cron watchdog (scripts/analyzer/autopsy_watchdog.sh, 10-min ticks).
#   3. AFTER this script exits, the caller must verify parallelism from a fresh ssh
#      (house rule): ssh laptop-wsl 'pgrep -fc oracle_score_pilot || echo NOT-RUNNING'
set -euo pipefail

SCOPE="${1:-fixed_v1}"     # fixed_v1 | all
JUDGES_SEL="${2:-both}"    # both | primary
case "$SCOPE" in fixed_v1|all) ;; *) echo "bad scope: $SCOPE" >&2; exit 2;; esac
case "$JUDGES_SEL" in
  both)    JUDGES_ARGS="clair-puct tier1-greedy" ;;
  primary) JUDGES_ARGS="clair-puct" ;;
  *) echo "bad judges: $JUDGES_SEL" >&2; exit 2 ;;
esac

REPO=/home/doctor/projects/carcassone
SHARE_LOCAL=/mnt/c/carc-shared
SHARE_REMOTE=/mnt/carc-shared   # laptop view of the same share  # allow-path
STAMP="$(date +%Y%m%d_%H%M%S)"
BUNDLE_NAME="autopsy_${STAMP}.bundle"

cd "$REPO"
mkdir -p "$SHARE_LOCAL/bundles"
git bundle create "$SHARE_LOCAL/bundles/$BUNDLE_NAME" android-app
echo "bundle: $BUNDLE_NAME ($(git rev-parse --short android-app))"

REMOTE_SCRIPT="$(mktemp)"
cat > "$REMOTE_SCRIPT" <<REMOTE
set -euo pipefail
cd /home/doctor/projects/carcassone
BUNDLE="$SHARE_REMOTE/bundles/$BUNDLE_NAME"
AUT=measurement/e4_autopsy_20260812
OUT="$SHARE_REMOTE/analyzer_e4_autopsy_20260812"

# clock-drift guard (WSL clocks jump after host sleep; a drifted box mis-times everything)
drift=\$(( \$(date +%s) - \$(stat -c %Y "\$BUNDLE") )); drift=\${drift#-}
if [ "\$drift" -gt 300 ]; then
  echo "CLOCK DRIFT \${drift}s vs bundle mtime — fix with date -s before launching" >&2; exit 3
fi

git fetch "\$BUNDLE" android-app
git reset --hard FETCH_HEAD
.venv/bin/python -c "import carcassonne_ai" || { echo "venv import failed" >&2; exit 4; }

# clear failed (ok=false) records so resume cannot silently skip those positions
cleared=0
while IFS= read -r f; do rm -f "\$f"; cleared=\$((cleared+1)); done < <(
  grep -l '"ok": false' "\$OUT"/*/*/records/*.json 2>/dev/null || true)
echo "cleared \$cleared ok=false record(s) under \$OUT"

SAMPLE="\$AUT/SAMPLE.json"
if [ "$SCOPE" = "fixed_v1" ]; then
  .venv/bin/python - <<'PY'
import json
p = "measurement/e4_autopsy_20260812/SAMPLE.json"
s = json.load(open(p))
# the driver iterates positions_files only (run_autopsy.py main); the top-level
# "positions" rid list is informational and deliberately left untouched
s["positions_files"] = {k: v for k, v in s["positions_files"].items() if k == "fixed_v1"}
assert s["positions_files"], "fixed_v1 missing from positions_files"
s["scope_note"] = "fixed_v1-only scope (launch_autopsy_laptop.sh); n_selected/per_stratum still describe the full 371-position sample"
out = "measurement/e4_autopsy_20260812/SAMPLE_fixedv1.json"
json.dump(s, open(out, "w"), indent=1)
n = sum(1 for _ in open(s["positions_files"]["fixed_v1"]))
print(f"fixed_v1-only sample written: {out} ({n} positions in epoch file)")
PY
  SAMPLE="\$AUT/SAMPLE_fixedv1.json"
fi

mkdir -p "\$AUT/logs"
rm -f "\$AUT/DONE_AUTOPSY" "\$AUT/FAILED_AUTOPSY" "\$AUT/logs/relaunch_count"
cat > "\$AUT/RUN_CMD.sh" <<RUNCMD
#!/usr/bin/env bash
cd /home/doctor/projects/carcassone
mkdir -p \$AUT/logs
nice -n 19 .venv/bin/python -u scripts/analyzer/run_autopsy.py \\
  --sample \$SAMPLE --judges $JUDGES_ARGS \\
  --workers 22 --backend python --skip-gate \\
  --out-root \$OUT \\
  >> \$AUT/logs/run_laptop.log 2>&1
rc=\\\$?
if [ "\\\$rc" -eq 0 ]; then touch \$AUT/DONE_AUTOPSY
else echo "rc=\\\$rc \\\$(date -Is)" >> \$AUT/FAILED_AUTOPSY; fi
RUNCMD
chmod +x "\$AUT/RUN_CMD.sh"

nohup systemd-run --user --scope -p MemoryMax=8G bash "\$AUT/RUN_CMD.sh" \
  > "\$AUT/logs/scope.log" 2>&1 < /dev/null &
disown
echo "launched detached (scope MemoryMax=8G); log: \$AUT/logs/run_laptop.log"

( crontab -l 2>/dev/null | grep -v autopsy_watchdog || true
  echo "*/10 * * * * /home/doctor/projects/carcassone/scripts/analyzer/autopsy_watchdog.sh"
) | crontab -
echo "watchdog armed (10-min cron)"
REMOTE

ssh laptop-wsl 'bash -s' < "$REMOTE_SCRIPT"
rm -f "$REMOTE_SCRIPT"
echo "REMINDER: verify parallelism now:  ssh laptop-wsl 'pgrep -fc oracle_score_pilot'"
