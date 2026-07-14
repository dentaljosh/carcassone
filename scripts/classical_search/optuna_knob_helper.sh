#!/bin/bash
# T3 Optuna knob-sweep LAPTOP HELPER loop (pre-reg: measurement/classical_search/
# OPTUNA_KNOB_SWEEP_DESIGN.md §4). The LOCAL 5900XT runs the driver (optuna_knob_sweep.py,
# primary: owns the TPE study + TSV + aggregation); THIS script runs on the laptop and
# adds game throughput to whatever cell the driver is currently on. It polls the driver's
# atomic CURRENT_CELL.json pointer and joins that cell via eval_puct_priors.py
# --shared-claim (the C5/C7/kdets two-box work-stealing pattern; c7_s1_launcher.sh is the
# model — iterate-until-count + clean_stale_claims + census). The laptop NEVER imports
# optuna (design §4/§5f); it only plays games into the shared out-dir.
#
# ============================ PRE-FLIGHT (read before launch) ============================
# 1. Process census FIRST (built in below). Net-free classical harness (NO carc-orch; CUDA masked).
# 2. Laptop must be code-synced (git bundle) BEFORE this runs — a stale eval_puct_priors.py
#    without --opp-pin-champion would silently run the LEAKED champion (both sides move).
#    No .so rebuild needed (no LeafConfig schema change; the T3 leaf knobs are all cy-float).
# 3. The champion env below is curve125 (the ADOPTED champion), NOT the harness's stale
#    curve100 _CANON_ENV setdefault — else the laptop plays the WRONG champion side.
# 4. Detached, nice -n 19 (built in). Net-free CPU worker rule: W~22 laptop (design §4).
# =========================================================================================
#
# Usage (laptop):
#   nice -n 19 bash scripts/classical_search/optuna_knob_helper.sh
# Optional:
#   --share PATH        SHARE mount (default /mnt/carc-shared — the laptop mount)
#   --workers N         helper worker count (default 22)
#   --subdir-prefix P   pointer/cell subdir under <share>/classical_search (default t3_optuna)
#   --poll SECS         poll interval when idle/stale (default 15)
#   --stale-secs SECS   treat the pointer as stale if its ts is older than this (default 600)
#   --dry-run           print the reconstructed join argv for the CURRENT pointer and exit
set -u

REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
HARNESS=$REPO/scripts/classical_search/eval_puct_priors.py

SHARE=/mnt/carc-shared         # laptop mount (LOCAL primary uses /mnt/c/carc-shared)
WORKERS=22
SUBDIR_PREFIX=t3_optuna
POLL=15
STALE_SECS=600
DRYRUN=0
CLAIM_STALE=300
while [ $# -gt 0 ]; do
  case "$1" in
    --share)         SHARE="${2:?}"; shift 2 ;;
    --workers)       WORKERS="${2:?}"; shift 2 ;;
    --subdir-prefix) SUBDIR_PREFIX="${2:?}"; shift 2 ;;
    --poll)          POLL="${2:?}"; shift 2 ;;
    --stale-secs)    STALE_SECS="${2:?}"; shift 2 ;;
    --dry-run)       DRYRUN=1; shift ;;
    *) echo "unknown arg '$1'"; exit 1 ;;
  esac
done

OUT_ROOT="$SHARE/classical_search"
CUR="$OUT_ROOT/$SUBDIR_PREFIX/CURRENT_CELL.json"
HOST=$(hostname)
CLAIM_HOST="t3-laptop-$HOST"
ARGVFILE="/tmp/t3_helper_argv_$$.nul"
ts() { date +%F_%T; }

# production leaf env for the CHAMPION side — curve125 (the ADOPTED champion), NOT curve100.
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

count_results() { ls "$1"/seed*_a*.json 2>/dev/null | grep -vc summary; }
clean_stale_claims() {   # drop .claim files with no result; arg2=min-age-minutes (empty=all)
  local d="$1" age="${2:-}"; local args=(-name "seed*.claim")
  [ -n "$age" ] && args+=(-mmin "+$age")
  find "$d" "${args[@]}" 2>/dev/null | while read -r c; do
    [ -f "${c%.claim}.json" ] || rm -f "$c"
  done
}

# Read the pointer, check status + staleness, and (if active) reconstruct the FULL join
# argv into $ARGVFILE (NUL-separated so the inline leaf JSON survives verbatim). Prints one
# line to stdout: "<STATUS> <OUT_SUBDIR> <N>". STATUS in {active,idle,stale,done,missing}.
read_pointer() {   # $1=cur $2=out_root $3=workers $4=claim_host $5=claim_stale $6=stale_secs $7=argvfile
  "$PY" - "$@" <<'PYEOF'
import json, sys, time
cur, out_root, workers, claim_host, claim_stale, stale_secs, argvfile = sys.argv[1:8]
try:
    d = json.load(open(cur))
except (OSError, json.JSONDecodeError):
    print("missing - -"); sys.exit(0)
status = d.get("status")
if status == "done":
    print("done - -"); sys.exit(0)
if status != "active":
    print("idle - -"); sys.exit(0)
if (time.time() - float(d.get("ts", 0))) > float(stale_secs):
    print(f"stale {d.get('out_subdir','-')} {d.get('n','-')}"); sys.exit(0)
sub = d["out_subdir"]; n = int(d["n"])
argv = ["--candidate", "puct", "--opponent", "puct", "--opp-pin-champion",
        "--leaf-quantize", "float", "--final-select", "visits",
        "--cand-sims", str(d["sims"]), "--exact-k", str(d["exact_k"]),
        "--n", str(n), "--paired",
        "--seed-start", str(d["seed_start"]),
        "--out-root", out_root, "--out-subdir", sub,
        "--exp-id", d["exp_id"], "--no-results-csv"] + list(d["knob_args"]) + [
        "--workers", str(workers), "--shared-claim",
        "--claim-host", claim_host, "--claim-stale-secs", str(claim_stale)]
with open(argvfile, "wb") as fh:
    fh.write(b"\0".join(a.encode() for a in argv))
print(f"active {sub} {n}")
PYEOF
}

pointer_sub() { "$PY" -c 'import json,sys
try: print(json.load(open(sys.argv[1])).get("out_subdir",""))
except Exception: print("")' "$1" 2>/dev/null; }

if [ "$DRYRUN" = 1 ]; then
  echo "[t3-helper DRY-RUN $HOST $(ts)] pointer=$CUR share=$SHARE W=$WORKERS"
  line=$(read_pointer "$CUR" "$OUT_ROOT" "$WORKERS" "$CLAIM_HOST" "$CLAIM_STALE" "$STALE_SECS" "$ARGVFILE")
  st=${line%% *}
  echo "[t3-helper DRY-RUN] status=$st"
  if [ "$st" = active ] && [ -f "$ARGVFILE" ]; then
    echo -n "  nice -n 19 $PY $HARNESS"; while IFS= read -r -d '' a; do printf ' %q' "$a"; done < "$ARGVFILE"; echo
  fi
  rm -f "$ARGVFILE"
  exit 0
fi

# census (net-free classical workers; a killed mp main orphans workers — inspect by age)
echo "[t3-helper $HOST $(ts)] start: share=$SHARE W=$WORKERS pointer=$CUR"
ps -o pid,etime,pcpu,comm -C python --sort=-etime 2>/dev/null | head -8 || true

idle=0
while true; do
  line=$(read_pointer "$CUR" "$OUT_ROOT" "$WORKERS" "$CLAIM_HOST" "$CLAIM_STALE" "$STALE_SECS" "$ARGVFILE")
  st=${line%% *}; rest=${line#* }; sub=${rest%% *}; n=${rest##* }
  case "$st" in
    done)
      echo "[t3-helper $(ts)] pointer status=done -> exit"; break ;;
    missing|idle|stale)
      idle=$((idle+1))
      [ $((idle % 20)) -eq 1 ] && echo "[t3-helper $(ts)] pointer $st -> idle (poll ${POLL}s)"
      sleep "$POLL"; continue ;;
    active)
      idle=0
      dir="$OUT_ROOT/$sub"
      mkdir -p "$dir"
      if [ "$(count_results "$dir")" -ge "$n" ]; then
        echo "[t3-helper $(ts)] cell $sub already at $(count_results "$dir")/$n -> idle for next"
        sleep "$POLL"; continue
      fi
      echo "[t3-helper $(ts)] JOIN cell $sub ($(count_results "$dir")/$n) W=$WORKERS"
      iter=0
      while [ "$(count_results "$dir")" -lt "$n" ] && [ $iter -lt 60 ]; do
        readarray -d '' ARGV < "$ARGVFILE"
        nice -n 19 "$PY" "$HARNESS" "${ARGV[@]}" > "/tmp/t3helper_${sub//\//_}.log" 2>&1
        clean_stale_claims "$dir" 4
        iter=$((iter+1))
        # bail early if the driver moved the pointer to a different cell
        nowsub=$(pointer_sub "$CUR")
        [ "$nowsub" != "$sub" ] && { echo "[t3-helper $(ts)] pointer moved $sub -> $nowsub, re-poll"; break; }
        [ "$(count_results "$dir")" -lt "$n" ] && sleep 3
      done
      [ "$(count_results "$dir")" -ge "$n" ] && \
        echo "[t3-helper $(ts)] cell $sub reached $n (primary aggregates) -> re-poll"
      ;;
  esac
done
rm -f "$ARGVFILE"
echo "[t3-helper $HOST $(ts)] DONE"
exit 0
