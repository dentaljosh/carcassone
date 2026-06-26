#!/usr/bin/env bash
# v29.1 retune — launch one wave across all 3 boxes (shared-claim, CPU-vs-CPU).
#   retune_launch.sh "Bmild_cap8 Bmild_cap12 Bmild_cap16"   [BASELINE] [N] [SIMS]
# Defaults: BASELINE=Bmild, N=200, SIMS=200, seed-start=1e9 (decks reused across waves).
# Workers: local 30 / laptop 22 / xeon 10 (Joshua's per-box spec). Each box runs the
# SAME candidate list; the shared claim files (on the CIFS share) coordinate work-stealing.
# Set DRYRUN=1 to print the per-box commands without launching.
set -uo pipefail
CANDS="${1:?usage: retune_launch.sh \"CAND...\" [BASELINE] [N] [SIMS]}"
BASE="${2:-Bmild}"; N="${3:-200}"; SIMS="${4:-200}"; SEED=1000000000
REPO=/home/doctor/projects/carcassone
GEN=/tmp/retune_gen   # generated inner scripts (local box); remote ones piped via ssh stdin
mkdir -p "$GEN"

# emit an inner runner: $1=tag $2=workers $3=out-root
inner() {
  local tag="$1" w="$2" out="$3"
  cat <<INNER
cd $REPO || exit 1
for C in $CANDS; do
  echo "--- ${tag} [\$C vs $BASE] \$(date '+%H:%M') ---"
  nice -n 19 .venv/bin/python -u scripts/v29/eval_v29_vs_v28.py --candidate "\$C" --baseline $BASE \\
    --n $N --sims $SIMS --paired --workers $w --seed-start $SEED \\
    --out-root $out --shared-claim --claim-stale-secs 1200
done
echo "=== ${tag} leg DONE \$(date '+%F %H:%M') ==="
INNER
}

LOG=/mnt/c/carc-shared/v29_eval
inner LOCAL  30 /mnt/c/carc-shared/v29_eval > "$GEN/local.sh"
# remote legs self-background (setsid + </dev/null) so the ssh channel closes and returns
{ echo "cd $REPO || exit 1"; echo "cat > /tmp/retune_inner.sh <<'EOS'";
  inner LAPTOP 22 /mnt/carc-shared/v29_eval; echo "EOS";
  echo "setsid nohup bash /tmp/retune_inner.sh </dev/null >/mnt/carc-shared/v29_eval/retune_laptop.log 2>&1 &";
  echo 'sleep 1; echo "laptop launched pid $!"'; } > "$GEN/laptop.sh"
{ echo "cd $REPO || exit 1"; echo "cat > /tmp/retune_inner.sh <<'EOS'";
  inner XEON   10 /mnt/carc-shared/v29_eval; echo "EOS";
  echo "setsid nohup bash /tmp/retune_inner.sh </dev/null >/mnt/carc-shared/v29_eval/retune_xeon.log 2>&1 &";
  echo 'sleep 1; echo "xeon launched pid $!"'; } > "$GEN/xeon.sh"

if [ "${DRYRUN:-0}" = "1" ]; then
  echo "### DRYRUN — would launch: $CANDS  (base=$BASE n=$N sims=$SIMS)"
  echo "--- LOCAL inner ---"; cat "$GEN/local.sh"
  echo "--- LAPTOP pipe ---"; cat "$GEN/laptop.sh"
  echo "--- XEON pipe ---";  cat "$GEN/xeon.sh"
  exit 0
fi

echo "=== RETUNE WAVE LAUNCH $(date '+%F %H:%M') | $CANDS | base=$BASE n=$N sims=$SIMS ==="
setsid nohup bash "$GEN/local.sh" </dev/null >"$LOG/retune_local.log" 2>&1 &
echo "local launched pid $!"
ssh laptop 'wsl -d Ubuntu -u doctor -- bash -s' < "$GEN/laptop.sh" 2>&1
ssh xeon-wsl 'bash -s' < "$GEN/xeon.sh" 2>&1
echo "=== all 3 legs launched ==="
