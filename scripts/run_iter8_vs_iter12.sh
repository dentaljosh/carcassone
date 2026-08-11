#!/usr/bin/env bash
# Phase 2 — clean iter8 vs iter12 at agent sims 200 AND 800, vs heur@800-v2.7, paired,
# FRESH band 2.5e9. Pre-registered: deepteacher_audit/ITER8_VS_ITER12_PROTOCOL.md.
# 5800x+laptop cluster, orch+cython eval (production eval path; result-identical priors).
# Eval helpers copied verbatim from run_residual_flywheel_v2.sh (battle-tested heal logic).
#
# Launch (detached): nohup nice -n 19 bash scripts/run_iter8_vs_iter12.sh > /tmp/i8v12.log 2>&1 & disown
set -uo pipefail

# ---- CLOCK-SKEW GUARD (shared) — scripts/measurement_infra/clock_skew_guard.sh ----------
# A box whose clock is fast sees every sibling's LIVE --shared-claim claim as stale and steals
# it (claim.py:is_stale compares SERVER mtime to CLIENT time.time()), silently collapsing the
# cluster to one box's throughput. Refuse to start rather than run at half speed all night.
_CSG="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || pwd)"
while [ ! -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] && [ "$_CSG" != / ]; do _CSG=$(dirname "$_CSG"); done
[ -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] || _CSG="${REPO:-/home/doctor/projects/carcassone}"
. "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" || { echo "FATAL: clock_skew_guard.sh not found from $0"; exit 3; }
carc_clock_skew_guard
# ----------------------------------------------------------------------------------------

SHARE_LOCAL=/mnt/c/carc-shared
SHARE_REMOTE=/mnt/carc-shared
REPO_LOCAL=/home/doctor/projects/carcassone
REPO_LAPTOP=/home/doctor/projects/carcassone
LAPTOP_SSH=${LAPTOP_SSH:-laptop-wsl}
PY=$REPO_LOCAL/.venv/bin/python

OUT=$SHARE_LOCAL/iter8_vs_iter12
OUTR=$SHARE_REMOTE/iter8_vs_iter12
N=${N:-400}; BAND=${BAND:-2500000000}; HSIMS=${HSIMS:-800}; SCALE=${SCALE:-0.25}
EVAL_W_5800X=${EVAL_W_5800X:-48}; EVAL_W_LAPTOP=${EVAL_W_LAPTOP:-26}
ITER8=$SHARE_LOCAL/flywheel_residual_attempt2/ckpt/iter8.pt
ITER12=$SHARE_LOCAL/deepteacher/ckpt/iter12.pt
HEAL_CAP=${HEAL_CAP:-8}; STALL_ODO=${STALL_ODO:-60}

mkdir -p "$OUT"
cd "$REPO_LOCAL" || { echo "FATAL: cannot cd $REPO_LOCAL" >&2; exit 1; }
for f in "$ITER8" "$ITER12"; do [ -f "$f" ] || { echo "FATAL: missing $f" >&2; exit 1; }; done
echo "=== Phase 2 iter8-vs-iter12 @ $(date): band=$BAND n=$N heur@$HSIMS scale=$SCALE ==="
echo "    iter8  = $ITER8  (sha $(sha256sum "$ITER8"|cut -c1-12))"
echo "    iter12 = $ITER12 (sha $(sha256sum "$ITER12"|cut -c1-12))"

git bundle create $SHARE_LOCAL/code_sync/carc_stage-b-wiring.bundle stage-b-wiring >/dev/null 2>&1
echo "  bundle tip: $(git rev-parse --short stage-b-wiring)"
ssh -o ConnectTimeout=20 $LAPTOP_SSH "cd $REPO_LAPTOP && git fetch $SHARE_REMOTE/code_sync/carc_stage-b-wiring.bundle stage-b-wiring && git reset --hard FETCH_HEAD" >/dev/null 2>&1 && echo "  laptop synced" || echo "  laptop sync FAILED (cluster may run 1 box)"

# ---- helpers (verbatim from run_residual_flywheel_v2.sh) ----
_share_writable() { ( touch "$SHARE_LOCAL/.i8v12_probe" 2>/dev/null && rm -f "$SHARE_LOCAL/.i8v12_probe" 2>/dev/null ); }
_kill_pool() { local pat="[${1:0:1}]${1:1}"; pkill -9 -f "$pat" 2>/dev/null || true; timeout 20 ssh -o ConnectTimeout=10 $LAPTOP_SSH "pkill -9 -f '$pat'" </dev/null >/dev/null 2>&1 || true; }
_ssh_bg() {
  local host="$1" cmd="$2" label="$3" try rc
  for try in 1 2 3; do
    timeout 45 ssh -o ConnectTimeout=20 "$host" "$cmd" </dev/null && return 0
    rc=$?
    [ "$rc" = "124" ] && { echo "  $label launched (detached; rc=124 not retried)" >&2; return 0; }
    [ "$rc" = "255" ] || { echo "  $label launch rc=$rc" >&2; return "$rc"; }
    echo "  $label ssh rc=255 (try $try/3)" >&2; sleep 3
  done
  echo "  $label ssh FAILED after 3 tries" >&2; return 255
}
_clean_stranded() { local dir="$1" ext="$2" age="${3:-0}" c
  if [ "$age" = "0" ]; then for c in "$dir"/*.claim; do [ -e "$c" ] || continue; [ -e "${c%.claim}.$ext" ] || rm -f "$c"; done
  else while IFS= read -r c; do [ -e "${c%.claim}.$ext" ] || rm -f "$c"; done < <(find "$dir" -name '*.claim' -mmin +"$age" 2>/dev/null); fi
}
elo_of_dir() { $PY - "$1" <<'PY'
import json, glob, math, sys
d=sys.argv[1]; w=dd=n=0
for jf in glob.glob(f"{d}/*seed*.json"):
    if jf.endswith(".partial.json"): continue
    try: r=json.loads(open(jf).read())
    except: continue
    n+=1
    if r.get("won_by_net"): w+=1
    elif r.get("drew"): dd+=1
if n==0: print("-9999.0 0.0 0"); sys.exit()
wr=(w+0.5*dd)/n; eps=0.5/n; wr=min(1-eps, max(eps, wr))
elo=400*math.log10(wr/(1-wr)); sig=(400/math.log(10))*math.sqrt(wr*(1-wr)/n)/(wr*(1-wr))
print(f"{elo:.1f} {sig:.1f} {n}")
PY
}
# launch ONE 3-box shared-claim eval cell (sims passed per-cell)
_eval_launch() { local sub="$1" ckpt="$2" sims="$3" rckpt
  rckpt=${ckpt/$SHARE_LOCAL/$SHARE_REMOTE}
  CKPT="$ckpt" OW="$EVAL_W_5800X" SIMS="$sims" HEUR_SIMS="$HSIMS" CARCASSONNE_V25_RESIDUAL_SCALE="$SCALE" \
    nice -n 19 bash scripts/eval_orch.sh --n "$N" --c-puct 3.0 --heur-leaf v2_7 --out-root "$OUT" --out-subdir "$sub" \
    --seed-start "$BAND" --paired --shared-claim --claim-host 5800x >/tmp/i8v12_5800x_$sub.log 2>&1 &
  _ssh_bg $LAPTOP_SSH "cd $REPO_LAPTOP && CKPT=$rckpt OW=$EVAL_W_LAPTOP SIMS=$sims HEUR_SIMS=$HSIMS CARCASSONNE_V25_RESIDUAL_SCALE=$SCALE setsid nice -n 19 bash scripts/eval_orch.sh --n $N --c-puct 3.0 --heur-leaf v2_7 --out-root $OUTR --out-subdir $sub --seed-start $BAND --paired --shared-claim --claim-host laptop > /tmp/i8v12_laptop_$sub.log 2>&1 </dev/null &" "laptop $sub" &
}
_run_eval() { local sub="$1" ckpt="$2" sims="$3" dir last stall cur heals
  dir="$OUT/$sub"; mkdir -p "$dir"
  if [ "$(ls "$dir"/*seed*.json 2>/dev/null | wc -l)" -ge "$N" ]; then echo "  [$sub] already complete, skip"; return 0; fi
  _clean_stranded "$dir" json 0
  echo "  [$sub] launch ckpt=$(basename "$ckpt") sims=$sims @ $(date)"
  _eval_launch "$sub" "$ckpt" "$sims"
  last=-1; stall=0; heals=0
  while [ "$(ls "$dir"/*seed*.json 2>/dev/null | wc -l)" -lt "$N" ]; do
    sleep 30; cur=$(ls "$dir"/*seed*.json 2>/dev/null | wc -l)
    if [ "$cur" -eq "$last" ]; then stall=$((stall+1)); else stall=0; last=$cur; fi
    if [ "$stall" -ge "$STALL_ODO" ]; then
      heals=$((heals+1)); [ "$heals" -gt "$HEAL_CAP" ] && { echo "  [$sub] FATAL: $heals heals, stuck $cur/$N" >&2; return 1; }
      _share_writable || { echo "  [$sub] share not writable, backoff" >&2; continue; }
      echo "  [$sub] STALLED $cur/$N — heal $heals" >&2
      _kill_pool "$sub"; _clean_stranded "$dir" json 30; _eval_launch "$sub" "$ckpt" "$sims"; stall=0
    fi
  done
  echo "  [$sub] complete ($(ls "$dir"/*seed*.json 2>/dev/null | wc -l)) @ $(date)"
}
_paired() { $PY scripts/odo_paired_tally.py "$1" "$2" 2>&1 | awk '
  /^TALLY /{for(i=1;i<=NF;i++){split($i,kv,"=");v[kv[1]]=kv[2]}; print v["delo"],v["z"],v["eloA"],v["eloB"],v["ndecks"]; f=1}
  END{if(!f) print "nan nan nan nan 0"}'; }

# ---- run the 4 cells (s200 first = cheaper, early read; then s800) ----
_run_eval i8_s200  "$ITER8"  200 || exit 1
_run_eval i12_s200 "$ITER12" 200 || exit 1
_run_eval i8_s800  "$ITER8"  800 || exit 1
_run_eval i12_s800 "$ITER12" 800 || exit 1

# ---- paired verdict + results ----
echo ""; echo "===== PHASE 2 RESULTS @ $(date) ====="
read D2 Z2 A2 B2 ND2 < <(_paired "$OUT/i8_s200" "$OUT/i12_s200")
read D8 Z8 A8 B8 ND8 < <(_paired "$OUT/i8_s800" "$OUT/i12_s800")
echo "  iter8  @s200 vs heur: $(elo_of_dir "$OUT/i8_s200")"
echo "  iter12 @s200 vs heur: $(elo_of_dir "$OUT/i12_s200")"
echo "  iter8  @s800 vs heur: $(elo_of_dir "$OUT/i8_s800")"
echo "  iter12 @s800 vs heur: $(elo_of_dir "$OUT/i12_s800")"
echo "  PAIRED s200 (iter12-iter8): delo=$D2 z=$Z2 eloA(i8)=$A2 eloB(i12)=$B2 decks=$ND2"
echo "  PAIRED s800 (iter12-iter8): delo=$D8 z=$Z8 eloA(i8)=$A8 eloB(i12)=$B8 decks=$ND8"
{
  echo "plane,iter8_elo,iter12_elo,paired_delo_i12_minus_i8,z,ndecks,band,n"
  echo "s200,$A2,$B2,$D2,$Z2,$ND2,$BAND,$N"
  echo "s800,$A8,$B8,$D8,$Z8,$ND8,$BAND,$N"
} > "$OUT/PHASE2_PAIRED.csv"
echo "  wrote $OUT/PHASE2_PAIRED.csv"
echo "=== PHASE 2 DONE @ $(date) ==="
