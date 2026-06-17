#!/usr/bin/env bash
# Residual value FLYWHEEL — ATTEMPT #2 (built 2026-06-08, per Joshua's recipe).
# Rebuilt after attempt #1 ended CL-011 = NULL. The headline lesson of attempt #1 was
# that the in-lineage heur@200 gate is a DISCORDANT proxy: it crowned iter1 (+40 out-of-
# lineage) and DISCARDED the stronger iter3 (+66.8). So attempt #2 changes WHO decides:
#
#   • EXTERNAL keep-best — the warm-from is chosen by a DECK-PAIRED heur@800 (out-of-
#     lineage) head-to-head of new-vs-current-best on the SAME rotating decks. The
#     in-lineage heur@200 gate is kept as TELEMETRY ONLY (logged; NO authority to crown
#     or terminate the lineage).
#   • FIXED 3-iter run — NO plateau-stop. Cheap-gate wobble cannot end the lineage.
#   • Distinct self-play decks each iter (SEED_START rotates) + rotating SELECTION decks
#     each iter (no overfit to one selection set) + a SEALED held-out confirmation band
#     evaluated on the final champion vs iter0 at the end.
#   • ALL per-iter checkpoints retained ($OUT/ckpt/iter*.pt; best.pt is a copy).
#   • No exit path skips the external odometer: selection runs inline every iter, and the
#     sealed confirmation runs after the loop unconditionally (even on a DEADLINE break).
#
# FROZEN CHOICES (pre-flight, 2026-06-08 — both empirically settled, see DECISIONS):
#   • Leaf = v2.7 (--heur-leaf v2_7 everywhere; v1 was nominally +24 elo but only 1.5σ
#     and switching forces a full re-tune → kept the tuned v2.7 ecosystem).
#   • Residual = raw Δ + tanh head, SCALE=0.25 (S-R3-1 tanh-cap is DEAD: |Δ|>1 in 0.00%
#     of 2.6M positions, 0.013% of the MSE budget; scale0.25 marginal confirmed +37.6).
#
# Workers: 5800x=14, laptop=20, xeon=10, all nice -n 19 (Joshua, 2026-06-08).
# Cluster: 3-box shared-claim (work-stealing) like attempt #1; same orphan-stall self-heal.
#
# Launch (ONLY when told): nohup nice -n 19 bash scripts/run_residual_flywheel_v2.sh > /tmp/flywheel2.log 2>&1 & disown
set -uo pipefail

SHARE_LOCAL=/mnt/c/carc-shared
SHARE_REMOTE=/mnt/carc-shared
REPO_LOCAL=/home/doctor/projects/carcassone
REPO_XEON=/home/doctor/projects/carcassone
REPO_LAPTOP=/home/doctor/projects/carcassone   # rebuilt laptop 2026-06-15: Win11+WSL, was /home/pop (pop-os)
LAPTOP_SSH=${LAPTOP_SSH:-laptop-wsl}            # rebuilt laptop: direct WSL bash (ssh laptop = Windows cmd.exe)
USE_XEON=${USE_XEON:-1}                         # 0 = exclude xeon from gen+eval (e.g. while benching it)
FLYWHEEL_TAG=${FLYWHEEL_TAG:-flywheel_residual_attempt2}   # fresh dir → no resume of attempt #1
OUT=$SHARE_LOCAL/$FLYWHEEL_TAG
OUTR=$SHARE_REMOTE/$FLYWHEEL_TAG
PY=$REPO_LOCAL/.venv/bin/python
ENVV="CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARCASSONNE_USE_FLAT_LEAF=1"   # = the v2.7 leaf config + flat-leaf rewrite (deployed 2026-06-09 @ iter5 boundary; bit-exact, ~+8% cluster)
WARMSTART_ROOT=$REPO_LOCAL/data/warmstart/heuristic_tau05

# Per-box worker counts: 5800x=14, laptop=12 (rebuilt 8GB/11GB box; orch sweep
# 2026-06-17 ~flat W12-16, W20 RAM-thrashes; was a stale 20 from the pop-os era), xeon=10.
W_5800X=${W_5800X:-14}; W_LAPTOP=${W_LAPTOP:-12}; W_XEON=${W_XEON:-10}
# Eval-W decoupled from gen-W (2026-06-16 xeon eval-W characterization: orch-off eval
# is CPU-thread-bound, peak at W=threads; xeon eval-W=12 > gen-W=10). Defaults to the
# per-box gen-W (behaviour unchanged) EXCEPT xeon=12. Used in _eval_launch only.
EVAL_W_5800X=${EVAL_W_5800X:-$W_5800X}; EVAL_W_LAPTOP=${EVAL_W_LAPTOP:-$W_LAPTOP}; EVAL_W_XEON=${EVAL_W_XEON:-12}

SCALE=${SCALE:-0.25}; GAMES=${GAMES:-400}; SIMS=${SIMS:-200}
# USE_ORCH=1 routes 5800x AND xeon gen through the carc-orch GPU orchestrator
# (per-forwarder CUDA streams, result-identical priors; verdict 2026-06-15). 5800x
# ~1.33x, xeon ~1.40x vs orch-off (A/B 2026-06-15; xeon fwd-rate scales W10->W18).
# Laptop stays orch-off (no Rust binary copied). Default 0 = ready but opt-in; the
# deployed resume recipe (STATUS) sets USE_ORCH=1. ORCH_WORKERS=28 is the 5800x peak;
# xeon defaults to W18 inside gen_flywheel.sh (NOT overridden here, so xeon picks 18).
USE_ORCH=${USE_ORCH:-0}; ORCH_WORKERS=${ORCH_WORKERS:-28}
ITERS=${ITERS:-3}; START=${START:-1}; KEEP_MARGIN=${KEEP_MARGIN:-0}   # external paired Δelo to promote; 0 = follow the external signal
TELEMETRY_GATE=${TELEMETRY_GATE:-1}                                   # 1 = also log the in-lineage heur@200 gate (no authority)

# --- seed bands (all eval seeds ≥ EVAL_SEED_FLOOR=1e9; self-play stays < 1e9) ---
#   self-play (gen): SEED_START = it*GAMES  → it1=400, it2=800, it3=1200 (rotating decks)
#   telemetry gate (heur@200, in-lineage):  GATE_SEED, fixed across iters (paired telemetry)
#   selection (heur@800, out-of-lineage, ROTATING): SEL_SEED_BASE + it*SEL_STRIDE
#   sealed confirmation (heur@800, HELD OUT): SEALED_SEED, used ONLY on the final champion
GATE_SEED=${GATE_SEED:-1000000000}; N_GATE=${N_GATE:-300}
SEL_SEED_BASE=${SEL_SEED_BASE:-1200000000}; SEL_STRIDE=${SEL_STRIDE:-1000}; ODO_N=${ODO_N:-200}
SEALED_SEED=${SEALED_SEED:-1700000000}; CONFIRM_N=${CONFIRM_N:-400}
ODO_HEUR_SIMS=${ODO_HEUR_SIMS:-800}

# Overnight wall-clock cap (0 = none). On a DEADLINE break the loop stops STARTING new
# iters but STILL runs the sealed confirmation on whatever champion exists.
DURATION_HOURS=${DURATION_HOURS:-0}
START_EPOCH=$(date +%s)
DEADLINE=0; [ "$DURATION_HOURS" != "0" ] && DEADLINE=$(awk -v s=$START_EPOCH -v h=$DURATION_HOURS 'BEGIN{printf "%d", s+h*3600}')

# iter0 = the confirmed residual net (Lever 1 winner; clean ruler +99.6 vs heur@200-v2.7).
# Overridable: the deeper-teacher experiment (docs/DEEPER_TEACHER_SPEC_2026-06-11.md) warm-starts
# from the new production champion via ITER0_CKPT=.../flywheel_residual_attempt2/ckpt/iter8.pt.
ITER0_CKPT=${ITER0_CKPT:-$SHARE_LOCAL/lever_seq/ckpt/residual.pt}

mkdir -p $OUT/ckpt $OUT/done $OUT/gate $OUT/odo
cd $REPO_LOCAL || { echo "FATAL: cannot cd $REPO_LOCAL" >&2; exit 1; }
[ -f "$ITER0_CKPT" ] || { echo "FATAL: iter0 residual ckpt missing: $ITER0_CKPT" >&2; exit 1; }
echo "=== residual FLYWHEEL ATTEMPT #2 @ $(date): TAG=$FLYWHEEL_TAG ITERS=$START..$ITERS SCALE=$SCALE GAMES=$GAMES ==="
echo "    keep-best = EXTERNAL (heur@${ODO_HEUR_SIMS}-v2.7 paired, rotating decks); gate@${SIMS} = telemetry only; VLW=${VLW:-1.0} KEEP_MARGIN=$KEEP_MARGIN"

# Fresh bundle so remotes run current code (incl. the odo_paired_tally TALLY line + gen SEED_START).
git bundle create $SHARE_LOCAL/code_sync/carc_stage-b-wiring.bundle stage-b-wiring >/dev/null 2>&1
echo "  bundle tip: $(git rev-parse --short stage-b-wiring)"
echo "  syncing remotes to bundle…"
ssh -o ConnectTimeout=20 $LAPTOP_SSH "cd $REPO_LAPTOP && git fetch $SHARE_REMOTE/code_sync/carc_stage-b-wiring.bundle stage-b-wiring && git reset --hard FETCH_HEAD" >/dev/null 2>&1 && echo "  laptop synced" || echo "  laptop sync FAILED (gate/odo fan may run stale)"
[ "$USE_XEON" = 1 ] && { ssh -o ConnectTimeout=20 xeon-wsl "cd $REPO_XEON && git fetch $SHARE_REMOTE/code_sync/carc_stage-b-wiring.bundle stage-b-wiring && git reset --hard FETCH_HEAD" >/dev/null 2>&1 && echo "  xeon synced" || echo "  xeon sync FAILED (gate/odo fan may run stale)"; } || echo "  xeon EXCLUDED (USE_XEON=0)"

# ---------------------------------------------------------------------------
# Shared helpers (carried verbatim from attempt #1's hardened launcher: D-S1..S4).
# ---------------------------------------------------------------------------
HEAL_CAP=${HEAL_CAP:-8}
# Eval heal stall-window (polls x 30s before declaring a stall). 60 = 30min, comfortably longer than
# one sims=800 net-vs-heur game (~10-30min). The old fixed 20 (10min) false-stalled on the tail/long
# games -> heal thrash that re-stacked workers, hung launch-ssh, and risked the heal-cap abort
# (2026-06-16). Gate evals (sims=200, ~2-4min games) keep their small window.
STALL_ODO=${STALL_ODO:-60}
# Gen heal stall-window (polls x 60s). 15 = 15min; the old 6 (6min) was shorter than a sims=800
# self-play game (same false-stall class as the eval bug above).
STALL_GEN=${STALL_GEN:-15}
_share_writable() { ( touch "$SHARE_LOCAL/.fw2_probe" 2>/dev/null && rm -f "$SHARE_LOCAL/.fw2_probe" 2>/dev/null ); }
_kill_pool() {   # reap the prior pool (cmdline pattern $1) on all 3 boxes: SIGKILL, scoped, hang-proof.
  # Bracket the 1st char so the regex matches real workers (incl. spawn/forkserver children, which
  # carry the full argv) but never the pkill shell itself (self-match guard). `timeout` caps each
  # remote kill so a drowning box can't hang the heal (the 2026-06-16 17-min wedge).
  local pat="[${1:0:1}]${1:1}"
  pkill -9 -f "$pat" 2>/dev/null || true
  timeout 20 ssh -o ConnectTimeout=10 $LAPTOP_SSH "pkill -9 -f '$pat'" </dev/null >/dev/null 2>&1 || true
  [ "$USE_XEON" = 1 ] && timeout 20 ssh -o ConnectTimeout=10 xeon-wsl "pkill -9 -f '$pat'" </dev/null >/dev/null 2>&1 || true
}
_ssh_bg() {   # launch a detached remote cmd. RETRY only on rc=255 (connect jitter).
  # `timeout 45` caps the launch ssh so a held-open channel can't wedge the heal. But a detached
  # launch (setsid+&) routinely holds the channel open on the WSL boxes, so the ssh hits the 45s
  # timeout (rc=124) AFTER the pool already started. Treat 124 as LAUNCHED and do NOT retry —
  # retrying stacks a 2nd/3rd pool (the 2026-06-16 retry-stacking bug: xeon hit 42 workers / 3 pools).
  local host="$1" cmd="$2" label="$3" try rc
  for try in 1 2 3; do
    timeout 45 ssh -o ConnectTimeout=20 "$host" "$cmd" </dev/null && return 0
    rc=$?
    [ "$rc" = "124" ] && { echo "  $label launched (detached; ssh channel held open, rc=124 — not retried)" >&2; return 0; }
    [ "$rc" = "255" ] || { echo "  $label launch rc=$rc" >&2; return "$rc"; }
    echo "  $label ssh rc=255 (try $try/3) — retry" >&2; sleep 3
  done
  echo "  $label ssh FAILED after 3 tries (box dropped this iter; heal re-adds)" >&2; return 255
}
_clean_stranded() {   # $1=dir $2=ext(json|npz) $3=only-if-older-than-min (0=all)
  local dir="$1" ext="$2" age="${3:-0}" c
  if [ "$age" = "0" ]; then
    for c in "$dir"/*.claim; do [ -e "$c" ] || continue; [ -e "${c%.claim}.$ext" ] || rm -f "$c"; done
  else
    while IFS= read -r c; do [ -e "${c%.claim}.$ext" ] || rm -f "$c"; done \
      < <(find "$dir" -name '*.claim' -mmin +"$age" 2>/dev/null)
  fi
}

# elo of the net-vs-heur win-rate in a dir (echoes "elo sigma n"); reads *seed*.json.
elo_of_dir() {
  $PY - "$1" <<'PY'
import json, glob, math, sys
d=sys.argv[1]; w=dd=n=0
for jf in glob.glob(f"{d}/*seed*.json"):
    if jf.endswith(".partial.json"): continue
    try: r=json.loads(open(jf).read())
    except: continue
    n+=1
    if r.get("won_by_net"): w+=1
    elif r.get("drew"): dd+=1
if n==0:
    print("-9999.0 0.0 0"); sys.exit()
wr=(w+0.5*dd)/n; eps=0.5/n; wr=min(1-eps, max(eps, wr))
elo=400*math.log10(wr/(1-wr)); sig=(400/math.log(10))*math.sqrt(wr*(1-wr)/n)/(wr*(1-wr))
print(f"{elo:.1f} {sig:.1f} {n}")
PY
}

# Launch ONE 3-box shared-claim net-vs-heur eval (generic over n / heur-sims / seed / root).
# All sides: residual SCALE, --heur-leaf v2_7 (the frozen matched leaf), --c-puct 3.0, --paired.
_eval_launch() {   # $1=sub $2=rckpt $3=ckpt $4=n $5=heur_sims $6=seed $7=root(local)
  local sub="$1" rckpt="$2" ckpt="$3" N="$4" hs="$5" seed="$6" root="$7" rroot
  rroot=${root/$SHARE_LOCAL/$SHARE_REMOTE}
  nice -n 19 env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE="$SCALE" $PY -u scripts/eval_net_vs_heuristic.py \
    --checkpoint "$ckpt" --n "$N" --sims "$SIMS" --heur-sims "$hs" --c-puct 3.0 --heur-leaf v2_7 \
    --workers "$EVAL_W_5800X" --out-root "$root" --out-subdir "$sub" \
    --seed-start "$seed" --paired --shared-claim --claim-host 5800x >/tmp/fw2_eval5800x.log 2>&1 &
  _ssh_bg $LAPTOP_SSH "cd $REPO_LAPTOP && env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE=$SCALE setsid nice -n 19 $REPO_LAPTOP/.venv/bin/python -u scripts/eval_net_vs_heuristic.py --checkpoint $rckpt --n $N --sims $SIMS --heur-sims $hs --c-puct 3.0 --heur-leaf v2_7 --workers $EVAL_W_LAPTOP --out-root $rroot --out-subdir $sub --seed-start $seed --paired --shared-claim --claim-host laptop > /tmp/fw2_evallaptop.log 2>&1 </dev/null &" "eval laptop $sub" &
  [ "$USE_XEON" = 1 ] && _ssh_bg xeon-wsl "cd $REPO_XEON && env $ENVV CARCASSONNE_V25_RESIDUAL_SCALE=$SCALE setsid nice -n 19 $REPO_XEON/.venv/bin/python -u scripts/eval_net_vs_heuristic.py --checkpoint $rckpt --n $N --sims $SIMS --heur-sims $hs --c-puct 3.0 --heur-leaf v2_7 --workers $EVAL_W_XEON --out-root $rroot --out-subdir $sub --seed-start $seed --paired --shared-claim --claim-host xeon > /tmp/fw2_evalxeon.log 2>&1 </dev/null &" "eval xeon $sub" &
}

# Block until a dir reaches N games, self-healing the orphan-stall. Returns 1 (loud) on
# heal-cap. NOT called in a $(...) subshell, so a caller `|| exit 1` actually aborts.
_run_eval() {   # $1=ckpt(local) $2=sub $3=n $4=heur_sims $5=seed $6=stall_polls $7=root(local)
  local ckpt="$1" sub="$2" N="$3" hs="$4" seed="$5" stallmax="$6" root="$7" rckpt dir last stall cur heals
  rckpt=${ckpt/$SHARE_LOCAL/$SHARE_REMOTE}
  dir="$root/$sub"; mkdir -p "$dir"
  if [ "$(ls "$dir"/*seed*.json 2>/dev/null | wc -l)" -ge "$N" ]; then return 0; fi
  _clean_stranded "$dir" json 0
  _eval_launch "$sub" "$rckpt" "$ckpt" "$N" "$hs" "$seed" "$root"
  last=-1; stall=0; heals=0
  while [ "$(ls "$dir"/*seed*.json 2>/dev/null | wc -l)" -lt "$N" ]; do
    sleep 30
    cur=$(ls "$dir"/*seed*.json 2>/dev/null | wc -l)
    if [ "$cur" -eq "$last" ]; then stall=$((stall+1)); else stall=0; last=$cur; fi
    if [ "$stall" -ge "$stallmax" ]; then
      heals=$((heals+1))
      [ "$heals" -gt "$HEAL_CAP" ] && { echo "  [$sub] FATAL: $heals heals, stuck at $cur/$N — aborting (D-S1)" >&2; return 1; }
      if ! _share_writable; then echo "  [$sub] share NOT writable — backing off (heal $heals)" >&2; continue; fi
      echo "  [$sub] STALLED at $cur/$N — heal $heals: kill pool + clean stale (30min) + relaunch" >&2
      _kill_pool "$sub"
      _clean_stranded "$dir" json 30; _eval_launch "$sub" "$rckpt" "$ckpt" "$N" "$hs" "$seed" "$root"; stall=0
    fi
  done
  return 0
}

# Launch the 3-box residual self-play gen for iter $1 with rotating seed-band $2.
_gen_launch() {   # $1=iter $2=seed_start
  local it="$1" sp_seed="$2"
  SHARE=$SHARE_LOCAL REPO=$REPO_LOCAL HOST=5800x WORKERS=$W_5800X USE_ORCH=$USE_ORCH ORCH_WORKERS=$ORCH_WORKERS WARM=$OUT/warm.pt OUT=$OUT/iter${it}_data SCALE=$SCALE GAMES=$GAMES SIMS=$SIMS SEED_START=$sp_seed \
    nohup nice -n 19 bash $SHARE_LOCAL/code_sync/gen_flywheel.sh > /tmp/fw2_gen5800x_$it.log 2>&1 & disown
  _ssh_bg $LAPTOP_SSH "SHARE=$SHARE_REMOTE REPO=$REPO_LAPTOP HOST=laptop USE_ORCH=$USE_ORCH WORKERS=$W_LAPTOP WARM=$OUTR/warm.pt OUT=$OUTR/iter${it}_data SCALE=$SCALE GAMES=$GAMES SIMS=$SIMS SEED_START=$sp_seed setsid nice -n 19 bash $SHARE_REMOTE/code_sync/gen_flywheel.sh > /tmp/fw2_genlaptop_$it.log 2>&1 </dev/null &" "[it$it] laptop gen" &   # laptop NOW orch (USE_ORCH=1 -> _OWD=12 + CY_REPR; A/B 2026-06-17 orch>off @s800)
  [ "$USE_XEON" = 1 ] && _ssh_bg xeon-wsl "SHARE=$SHARE_REMOTE REPO=$REPO_XEON HOST=xeon WORKERS=$W_XEON WARM=$OUTR/warm.pt OUT=$OUTR/iter${it}_data SCALE=$SCALE GAMES=$GAMES SIMS=$SIMS SEED_START=$sp_seed USE_ORCH=0 setsid nice -n 19 bash $SHARE_REMOTE/code_sync/gen_flywheel.sh > /tmp/fw2_genxeon_$it.log 2>&1 </dev/null &" "[it$it] xeon gen" &   # xeon=orch-OFF W10 (2026-06-16 bench: tie, GPU underfed; only 5800x earns orch)
}

# Parse the odo_paired_tally TALLY line: A=baseline(best/iter0), B=new(iter/champion).
# Echoes "delo z eloA eloB ndecks" (delo = eloB - eloA = new − baseline).
_paired() {   # $1=A_dir(baseline) $2=B_dir(new)
  $PY scripts/odo_paired_tally.py "$1" "$2" 2>&1 | awk '
    /^TALLY /{for(i=1;i<=NF;i++){split($i,kv,"=");v[kv[1]]=kv[2]}
              print v["delo"],v["z"],v["eloA"],v["eloB"],v["ndecks"]; found=1}
    END{if(!found) print "nan nan nan nan 0"}'
}

# ---------------------------------------------------------------------------
# Pre-loop: init best = iter0 (the confirmed residual net). Optional iter0 telemetry gate.
# ---------------------------------------------------------------------------
if [ -f "$OUT/best_id.txt" ] && [ -s "$OUT/best.pt" ]; then
  BEST_ID=$(cat "$OUT/best_id.txt"); echo "  resuming: best=$BEST_ID"
else
  cp "$ITER0_CKPT" "$OUT/best.pt"; BEST_ID="iter0"; echo "iter0" > "$OUT/best_id.txt"
  if [ "$TELEMETRY_GATE" = "1" ]; then
    echo "--- iter0 telemetry gate (in-lineage heur@${SIMS}-v2.7) @ $(date) ---"
    _run_eval "$OUT/best.pt" "gate_iter0" "$N_GATE" "$SIMS" "$GATE_SEED" 12 "$OUT/gate" || { echo "FATAL: iter0 gate heal-cap" >&2; exit 1; }
    echo "  [telemetry] iter0 gate = $(elo_of_dir "$OUT/gate/gate_iter0") (heur@${SIMS}, in-lineage — NO authority)"
  fi
fi

# ---------------------------------------------------------------------------
# Main loop — FIXED ITERS, no plateau-stop.
# ---------------------------------------------------------------------------
for it in $(seq $START $ITERS); do
  if [ "$DEADLINE" -gt 0 ] && [ "$(date +%s)" -ge "$DEADLINE" ]; then
    echo "=== DEADLINE reached ($DURATION_HOURS h) — not starting iter $it; going to sealed confirmation ==="; break
  fi
  echo ""; echo "########## ATTEMPT-2 ITER $it @ $(date) (warm from best=$BEST_ID) ##########"
  DATA=$OUT/iter${it}_data; CKPT=$OUT/ckpt/iter${it}.pt; SP_SEED=$(( it * GAMES ))
  [ -s "$OUT/best.pt" ] || { echo "[it$it] FATAL: best.pt missing/empty — refusing to warm from nothing" >&2; exit 1; }
  cp "$OUT/best.pt" "$OUT/warm.pt" || { echo "[it$it] FATAL: cannot stage warm.pt" >&2; exit 1; }

  # --- 3-box residual self-play on the iter's rotating deck band (SEED_START) ---
  if [ ! -f "$OUT/done/gen$it" ]; then
    echo "[it$it] launch 3-box residual gen (seed_start=$SP_SEED) @ $(date)"
    mkdir -p "$DATA/iter_00"; _clean_stranded "$DATA/iter_00" npz 0
    _gen_launch "$it" "$SP_SEED"
    glast=-1; gstall=0; gheals=0
    while [ "$(ls $DATA/iter_00/*.npz 2>/dev/null | wc -l)" -lt "$GAMES" ]; do
      sleep 60
      gcur=$(ls $DATA/iter_00/*.npz 2>/dev/null | wc -l)
      if [ "$gcur" -eq "$glast" ]; then gstall=$((gstall+1)); else gstall=0; glast=$gcur; fi
      if [ "$gstall" -ge "$STALL_GEN" ]; then
        gheals=$((gheals+1))
        [ "$gheals" -gt "$HEAL_CAP" ] && { echo "[it$it] FATAL: $gheals gen heals, stuck at $gcur/$GAMES — aborting (D-S1)" >&2; exit 1; }
        if ! _share_writable; then echo "[it$it] gen: share NOT writable — backing off (heal $gheals)" >&2; continue; fi
        echo "[it$it] gen STALLED at $gcur/$GAMES — heal $gheals: kill pool + clean stale (30min) + relaunch" >&2
        _kill_pool run_selfplay_iter
        _clean_stranded "$DATA/iter_00" npz 30; _gen_launch "$it" "$SP_SEED"; gstall=0
      fi
    done
    echo "[it$it] gen complete ($(ls $DATA/iter_00/*.npz 2>/dev/null | wc -l) npz) @ $(date)"
    date > "$OUT/done/gen$it"
  else
    echo "[it$it] gen — done, skip"
  fi

  # --- train the residual head on the co-adapted data ---
  if [ ! -f "$CKPT" ]; then
    echo "[it$it] train @ $(date)"
    nice -n 19 env $ENVV $PY -u scripts/train_iter.py \
      --output-root "$DATA" --warmstart-root "$WARMSTART_ROOT" \
      --iter 0 --window 10 --warmstart-mix-fraction 0.0 --value-loss-weight ${VLW:-1.0} \
      --stage-local "/tmp/fw2_stage_$it" --warm-from "$OUT/warm.pt" --output "$CKPT" --epochs 3 \
      --prov-value-target residual --prov-selfplay-leaf "v2_7+residual${SCALE}" \
      --prov-seed-range "${SP_SEED}-$((SP_SEED+GAMES-1))" --prov-run-tag "flywheel_attempt2_it${it}"
    rm -rf "/tmp/fw2_stage_$it" 2>/dev/null || true
    [ -f "$CKPT" ] || { echo "[it$it] TRAIN FAILED — halting" >&2; exit 1; }
  fi

  # --- EXTERNAL keep-best: deck-paired heur@800 head-to-head new-vs-best on a ROTATING band ---
  BAND=$(( SEL_SEED_BASE + it * SEL_STRIDE ))
  echo "[it$it] === selection: iter$it vs best=$BEST_ID, paired heur@${ODO_HEUR_SIMS}-v2.7, band $BAND, n=$ODO_N @ $(date) ==="
  _run_eval "$CKPT"        "sel_it${it}_new"  "$ODO_N" "$ODO_HEUR_SIMS" "$BAND" $STALL_ODO "$OUT/odo" || { echo "[it$it] FATAL: selection(new) heal-cap" >&2; exit 1; }
  _run_eval "$OUT/best.pt" "sel_it${it}_best" "$ODO_N" "$ODO_HEUR_SIMS" "$BAND" $STALL_ODO "$OUT/odo" || { echo "[it$it] FATAL: selection(best) heal-cap" >&2; exit 1; }
  read DELO ZTAL ELOBEST ELONEW NDECKS < <(_paired "$OUT/odo/sel_it${it}_best" "$OUT/odo/sel_it${it}_new")
  echo "[it$it] selection: iter$it=${ELONEW} elo  best($BEST_ID)=${ELOBEST} elo  | paired Δelo(new−best)=${DELO} z=${ZTAL} decks=${NDECKS}"
  PROMOTE=$(awk -v d="$DELO" -v m="$KEEP_MARGIN" 'BEGIN{dl=tolower(d); if(d==""||dl~/nan|inf/){print 0; exit} print (d+0 > m+0)?1:0}')
  if [ "$PROMOTE" = "1" ]; then
    cp "$CKPT" "$OUT/best.pt"; BEST_ID="iter$it"; echo "iter$it" > "$OUT/best_id.txt"
    echo "[it$it] ✅ NEW BEST = iter$it (external paired Δ=${DELO} > margin $KEEP_MARGIN)"
  else
    echo "[it$it] ✗ keep best=$BEST_ID (iter$it did not beat it out-of-lineage)"
  fi
  echo "${it},${ELONEW},${ELOBEST},${DELO},${ZTAL},${NDECKS},${PROMOTE},${BEST_ID}" >> "$OUT/selection.csv"

  # --- telemetry gate (in-lineage heur@200) — LOGGED ONLY, no authority ---
  if [ "$TELEMETRY_GATE" = "1" ]; then
    _run_eval "$CKPT" "gate_it${it}" "$N_GATE" "$SIMS" "$GATE_SEED" 12 "$OUT/gate" || { echo "[it$it] gate heal-cap (telemetry — continuing)" >&2; }
    G=$(elo_of_dir "$OUT/gate/gate_it${it}")
    echo "[it$it] [telemetry] in-lineage gate(heur@${SIMS}-v2.7) = $G  | external selection said Δ=${DELO} (watch for discordance — attempt #1's failure mode)"
    echo "${it},${G// /,},${ELONEW},${DELO}" >> "$OUT/telemetry_gate.csv"
  fi
done

# ---------------------------------------------------------------------------
# SEALED CONFIRMATION — champion vs iter0 on a HELD-OUT band never used in selection.
# Always runs (even after a DEADLINE break). This is THE attempt-#2 out-of-lineage verdict.
# ---------------------------------------------------------------------------
echo ""; echo "===== SEALED CONFIRMATION @ $(date): champion=$BEST_ID vs iter0 on held-out band $SEALED_SEED, n=$CONFIRM_N, heur@${ODO_HEUR_SIMS}-v2.7 ====="
_run_eval "$OUT/best.pt"  "sealed_champ" "$CONFIRM_N" "$ODO_HEUR_SIMS" "$SEALED_SEED" $STALL_ODO "$OUT/odo" || { echo "FATAL: sealed(champ) heal-cap" >&2; exit 1; }
_run_eval "$ITER0_CKPT"   "sealed_iter0" "$CONFIRM_N" "$ODO_HEUR_SIMS" "$SEALED_SEED" $STALL_ODO "$OUT/odo" || { echo "FATAL: sealed(iter0) heal-cap" >&2; exit 1; }
echo "--- sealed paired tally (A=iter0 baseline, B=champion $BEST_ID) ---"
$PY scripts/odo_paired_tally.py "$OUT/odo/sealed_iter0" "$OUT/odo/sealed_champ" | tee "$OUT/SEALED_VERDICT.txt"
read SDELO SZ SELOA SELOB SND < <(_paired "$OUT/odo/sealed_iter0" "$OUT/odo/sealed_champ")

echo ""
echo "=== FLYWHEEL ATTEMPT #2 DONE @ $(date) ==="
echo "    champion = $BEST_ID ($OUT/best.pt)   |  all ckpts retained: $OUT/ckpt/iter*.pt"
echo "    SEALED out-of-lineage verdict: champion vs iter0 (fresh decks, n=$CONFIRM_N paired heur@${ODO_HEUR_SIMS}-v2.7):"
echo "      champion abs = ${SELOB} elo   iter0 abs = ${SELOA} elo   Δelo(champ−iter0) = ${SDELO}  z=${SZ}  decks=${SND}"
echo "    charter bar to FLIP CL-011: ≥3 non-regressing iters with cumulative out-of-lineage ≥ +45 elo (+15/iter)."
echo "    selection log: $OUT/selection.csv  | telemetry: $OUT/telemetry_gate.csv  | sealed: $OUT/SEALED_VERDICT.txt"
