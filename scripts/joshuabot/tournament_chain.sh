#!/bin/bash
# JOSHUA-BOT VARIANT TOURNAMENT — sequential per-cell chain launcher (SCREEN only).
#
# Prereg of record: measurement/joshuabot_20260812/TOURNAMENT_PREREG.md
#   - 6 cells x 150 decks x 2 seats = 300 games/cell, 1800 games, ONE shared band (1.25e11)
#   - candidate = the scripted JoshuaBot at that cell's variant
#   - opponent  = the UNMODIFIED production champion (PRODUCTION.yaml fair_deploy, rust)
#   - rules profile fixed_v1 (implies CARCASSONNE_FIX_R9=1; NOT comparable to walled elo)
#
# THIS SCRIPT PROMOTES NOTHING. It plays games, gates the wiring, and writes extracts.
# It never edits governance/PRODUCTION.yaml, never adjudicates, and never runs the CONFIRM
# (prereg section 5 rule 4 — that is a separate, authorized launch on the fresh band 1.26e11).
#
# ─────────────────────────────────────────────────────────────────────────────────────────
# FLAG SURFACE — VERIFIED 2026-08-12 against the bot worktree's COMMITTED driver
# (agent-a90ec26964a84fdd3, commit 2283178), NOT assumed:
# ─────────────────────────────────────────────────────────────────────────────────────────
#     --preset {current,early}
#     --j7-weight FLOAT              (default 1.0)
#     --j8-break-reserve-floor       (argparse action="store_true"  -> BARE flag, no value)
#     --j9-avoid-cloisters           (argparse action="store_true"  -> BARE flag, no value)
#     --override KEY=VALUE           (repeatable, typed — DELIBERATELY UNUSED by every cell:
#                                     sweeping an unnamed knob is a new prereg, not a cell)
#     --decks --seed-base --profile --workers --rust-threads --sims --k-dets --out
#     --resume --limit
#
# ⚠️ EVERY CELL GETS ITS OWN --out. The driver hard-refuses to append a second variant_id to
# an existing file (it would blend two players into one paired margin), and it writes
# <out>.manifest.json with the FULL resolved variant BEFORE game 1 — so this chain adds no
# manifest handling of its own, it only reads that manifest for the axis gate.
#
# GATE 1 below re-verifies the surface against the MERGED driver's --help before any game:
# a missing flag, or a bool flag that turns out to take a value, is a hard FAILED_TOURNAMENT.
# GATE 3 then proves per cell, from the driver's own manifest, that the flag actually landed
# on the bot's resolved params — a silently-ignored --j7-weight would make J7ZERO identical
# to BASE and buy a guaranteed, meaningless null (the band-1.23e11 W9 lesson).
#
# ⚠️ READ THE PREREG'S J8 REFRAME BEFORE INTERPRETING THE J8EX CELL: with the J3 reserve
# floor intact, j8_overcommit fires on ZERO chosen moves per current-preset game; with
# --j8-break-reserve-floor it fires 8-28x/game. BASE therefore plays with J8 effectively OFF,
# and the J8EX arm is "J8 present vs J8 absent", not a marginal exemption.
# ─────────────────────────────────────────────────────────────────────────────────────────
#
# WORKER GRANT (owner, 2026-08-12): "both boxes are yours. laptop for like 48hrs.
# local w30 until 11am, then w14". Encoded as: W=30 while the overnight window is open AND
# the cell is PROJECTED to finish before the window closes at 11:00 local; otherwise W=14.
# A W30 cell must never straddle 11:00.
#
# USAGE (the orchestrator launches this AFTER merging the bot into the main tree):
#   setsid nohup nice -n 19 bash /home/doctor/projects/carcassone/scripts/joshuabot/tournament_chain.sh \
#       >> /home/doctor/projects/carcassone/measurement/joshuabot_20260812/logs/chain.log 2>&1 & disown
#
# ENV OVERRIDES (all optional):
#   JB_BAND=125000000000     deck band (seed base) for the screen cells
#   JB_DECKS=150             decks per cell (games = 2x this)
#   JB_CELLS="BASE J7ZERO"   run only these cells, in this order (e.g. the DEFERRED set)
#   JB_W_HI=30 JB_W_LO=14    the two worker counts
#   JB_CONTENTION_W30=1.6    PLANNING CONSTANT, not a measurement: per-worker slowdown at W_HI
#   JB_CONTENTION_W14=1.15   ditto at W_LO
#   JB_BENCH_LIMIT=1         games in the bench (set to =W for an honest contended wave)
#   JB_MAX_SGAME=600         s/game above which the bench is treated as a broken wiring signal
#   JB_TAG=""                suffix for marker/log names when running a second box in parallel
#   JB_SKIP_BENCH=0          =1 reuses a prior bench s/game from BENCH.json (resume path)
#
# RESUME: safe to re-run. Cells with a DONE_<CELL> marker are skipped; a partially-written
# cell resumes via the driver's own --resume (per-game fsync checkpointing).

set -uo pipefail

REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
H2H=$REPO/scripts/joshuabot/h2h.py
DIR=$REPO/measurement/joshuabot_20260812
LOGS=$DIR/logs
CELLDIR=$DIR/cells
PROBEDIR=$DIR/probe
BENCHDIR=$DIR/bench
SUMDIR=$DIR/summaries

TAG=${JB_TAG:-}
BAND=${JB_BAND:-125000000000}
DECKS=${JB_DECKS:-150}
W_HI=${JB_W_HI:-30}
W_LO=${JB_W_LO:-14}
C30=${JB_CONTENTION_W30:-1.6}
C14=${JB_CONTENTION_W14:-1.15}
BENCH_LIMIT=${JB_BENCH_LIMIT:-1}
MAX_SGAME=${JB_MAX_SGAME:-600}
SKIP_BENCH=${JB_SKIP_BENCH:-0}
PROFILE=${JB_PROFILE:-fixed_v1}

# Bench + the axis-wiring probes draw from band_start + 900e6: inside the band's registered
# label, DISJOINT from the cells' deck seeds (the 1.06e11 / 1.18e11 smoke precedent).
PROBE_BASE=$((BAND + 900000000))

PRIORITY="BASE J7ZERO EARLY J8EX J9ON ALLTOG"     # degradation order (prereg section 8)
CELLS=${JB_CELLS:-$PRIORITY}

DONE_MARK=$DIR/DONE_TOURNAMENT$TAG
FAIL_MARK=$DIR/FAILED_TOURNAMENT$TAG
BAND_MARK=$DIR/BAND_TOURNAMENT$TAG
DEFER_MARK=$DIR/DEFERRED_CELLS$TAG
PLAN_MARK=$DIR/PLAN$TAG.txt
BENCH_JSON=$DIR/BENCH$TAG.json

mkdir -p "$LOGS" "$CELLDIR" "$PROBEDIR" "$BENCHDIR" "$SUMDIR"

ts() { date +%F_%T; }
log() { echo "[jbchain $(ts)] $*"; }

fail() {
  { echo "FAILED $(ts)"; echo "reason: $*"; } > "$FAIL_MARK"
  log "FATAL: $*"
  log "wrote $FAIL_MARK — no further cells will run."
  exit 1
}

on_exit() {
  rc=$?
  if [ ! -f "$DONE_MARK" ] && [ ! -f "$FAIL_MARK" ]; then
    { echo "FAILED $(ts)"; echo "reason: unexpected exit rc=$rc (killed, crashed, or box reboot)"; } \
      > "$FAIL_MARK"
    log "unexpected exit rc=$rc — wrote $FAIL_MARK"
  fi
}
trap on_exit EXIT

# ── cell definitions ─────────────────────────────────────────────────────────────────────
cell_flags() {   # driver flags for a cell (on top of --decks/--profile/--workers/--out)
  case "$1" in
    BASE)   echo "--preset current" ;;
    J7ZERO) echo "--preset current --j7-weight 0.0" ;;
    J8EX)   echo "--preset current --j8-break-reserve-floor" ;;
    J9ON)   echo "--preset current --j9-avoid-cloisters" ;;
    EARLY)  echo "--preset early" ;;
    ALLTOG) echo "--preset current --j7-weight 0.0 --j8-break-reserve-floor --j9-avoid-cloisters" ;;
    *)      echo "" ;;
  esac
}

cell_axes() {    # expected "<preset> <j7_weight> <j8_break_reserve_floor> <j9_avoid_cloisters>"
  case "$1" in
    BASE)   echo "current 1.0 False False" ;;
    J7ZERO) echo "current 0.0 False False" ;;
    J8EX)   echo "current 1.0 True False" ;;
    J9ON)   echo "current 1.0 False True" ;;
    EARLY)  echo "early 1.0 False False" ;;
    ALLTOG) echo "current 0.0 True True" ;;
    *)      echo "" ;;
  esac
}

cell_index() {   # stable index -> distinct probe deck seed per cell
  case "$1" in
    BASE) echo 0 ;; J7ZERO) echo 1 ;; J8EX) echo 2 ;;
    J9ON) echo 3 ;; EARLY) echo 4 ;; ALLTOG) echo 5 ;; *) echo 9 ;;
  esac
}

# ── window / worker arithmetic ───────────────────────────────────────────────────────────
# The overnight W_HI window is open from 17:00 through 10:59 and closes at 11:00 local.
# A daytime launch (11:00-16:59) runs the whole chain at W_LO, per the grant's "then w14".
now_min()  { local h m; h=$(date +%H); m=$(date +%M); echo $((10#$h * 60 + 10#$m)); }
w_hi_open() { local h; h=$(date +%H); h=$((10#$h)); [ "$h" -ge 17 ] || [ "$h" -lt 11 ]; }
mins_to_close() {                      # minutes until the next 11:00; 0 if the window is shut
  if ! w_hi_open; then echo 0; return; fi
  local n d; n=$(now_min); d=$((660 - n)); [ "$d" -le 0 ] && d=$((d + 1440))
  echo "$d"
}
est_min() {                            # $1=games $2=W -> projected wall minutes at s/game $S_GAME
  awk -v g="$1" -v w="$2" -v s="$S_GAME" -v c30="$C30" -v c14="$C14" -v hi="$W_HI" \
      'BEGIN{c=(w>=hi?c30:c14); printf "%d", (g*s*c/w/60)+0.5}'
}

# ── the reusable per-run pieces ──────────────────────────────────────────────────────────
run_h2h() {                            # $1=out $2=seedbase $3=decks $4=workers $5=limit $6=log  $7..=flags
  local out=$1 sb=$2 dk=$3 wk=$4 lim=$5 lg=$6; shift 6
  nice -n 19 "$PY" "$H2H" \
      --decks "$dk" --seed-base "$sb" --profile "$PROFILE" \
      --workers "$wk" --limit "$lim" --out "$out" --resume "$@" \
      >> "$lg" 2>&1 </dev/null
}

check_axes() {                         # $1=manifest path  $2=cell
  local man=$1 cell=$2 exp
  exp=$(cell_axes "$cell")
  # shellcheck disable=SC2086
  set -- $exp
  "$PY" - "$man" "$1" "$2" "$3" "$4" <<'PYEOF'
import json, sys
m = json.load(open(sys.argv[1]))
jm = m["joshua_manifest"]; ax = jm["axes"]
got = {"preset": str(jm["preset"]),
       "j7_weight": float(ax["j7_weight"]),
       "j8_break_reserve_floor": bool(ax["j8_break_reserve_floor"]),
       "j9_avoid_cloisters": bool(ax["j9_avoid_cloisters"])}
want = {"preset": sys.argv[2], "j7_weight": float(sys.argv[3]),
        "j8_break_reserve_floor": sys.argv[4] == "True",
        "j9_avoid_cloisters": sys.argv[5] == "True"}
ok = (got["preset"] == want["preset"]
      and abs(got["j7_weight"] - want["j7_weight"]) < 1e-9
      and got["j8_break_reserve_floor"] == want["j8_break_reserve_floor"]
      and got["j9_avoid_cloisters"] == want["j9_avoid_cloisters"])
print(("AXES OK   " if ok else "AXES MISMATCH ") + json.dumps({"got": got, "want": want}))
sys.exit(0 if ok else 3)
PYEOF
}

n_records() { "$PY" - "$1" <<'PYEOF'
import json, sys, os
p = sys.argv[1]
n = 0
if os.path.exists(p):
    for line in open(p):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("winner"):
            n += 1
print(n)
PYEOF
}

write_summary() {                      # $1=cell jsonl  $2=out json — REUSES the driver's own
  JB_SCRIPTS=$REPO/scripts/joshuabot "$PY" - "$1" "$2" <<'PYEOF'
import json, os, sys
sys.path.insert(0, os.environ["JB_SCRIPTS"])
from h2h import summarize                      # the driver's statistic, never re-implemented
recs = []
for line in open(sys.argv[1]):
    line = line.strip()
    if line:
        try:
            recs.append(json.loads(line))
        except json.JSONDecodeError:
            pass
s = summarize(recs)
s["note"] = ("EXTRACT ONLY. No verdict, no adjudication, no promotion. Read against "
             "measurement/joshuabot_20260812/TOURNAMENT_PREREG.md sections 4-5.")
json.dump(s, open(sys.argv[2], "w"), indent=1)
print(json.dumps({k: s[k] for k in ("n_scored", "n_failed", "failure_rate",
                                    "win_rate", "n_paired_decks",
                                    "paired_margin_mean", "paired_margin_sem",
                                    "paired_margin_z") if k in s}))
PYEOF
}

# ═════════════════════════════════════════════════════════════════════════════════════════
log "START band=$BAND decks/cell=$DECKS profile=$PROFILE cells='$CELLS'"
log "repo HEAD=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo unknown)"
rm -f "$FAIL_MARK"
[ -f "$DONE_MARK" ] && log "NOTE: $DONE_MARK already exists — re-running only unfinished cells."

[ -x "$PY" ]   || fail "no venv python at $PY"
[ -f "$H2H" ]  || fail "driver missing at $H2H — has the bot worktree been merged into main?"

# ── GATE 1: flag surface (the ASSUMED-FLAGS block at the top of this file) ────────────────
HELP=$("$PY" "$H2H" --help 2>&1) || fail "h2h.py --help failed:
$HELP"
MISSING=""
for f in --decks --seed-base --preset --workers --out --resume --limit \
         --j7-weight --j8-break-reserve-floor --j9-avoid-cloisters; do
  printf '%s\n' "$HELP" | grep -q -- "$f" || MISSING="$MISSING $f"
done
[ -z "$MISSING" ] || fail "driver is missing flags:$MISSING — the ASSUMED FLAG SURFACE block at the top of this script is stale; verify against the merged h2h.py before relaunching."
# Flag FORM check. argparse prints a value-taking option as "--flag METAVAR" (metavar =
# uppercased dest) and a store_true as a bare "[--flag]". Testing for the METAVAR TOKEN is the
# reliable discriminator: matching "--flag +[A-Z]+" false-fires on help text that merely
# starts with an uppercase word ("--j9-avoid-cloisters  J9: his stated adaptation...").
metavar_of() { printf '%s' "${1#--}" | tr 'a-z-' 'A-Z_'; }
for f in --j8-break-reserve-floor --j9-avoid-cloisters; do
  if printf '%s\n' "$HELP" | grep -q -- "$(metavar_of "$f")"; then
    fail "$f appears to TAKE A VALUE in the merged driver (metavar $(metavar_of "$f") is in --help; expected argparse store_true). Update cell_flags() in this script — passing it bare would be a parse error or, worse, silently consume the next token."
  fi
done
printf '%s\n' "$HELP" | grep -q -- "$(metavar_of --j7-weight)" \
  || fail "--j7-weight no longer takes a value in the merged driver (metavar J7_WEIGHT absent from --help). cell_flags() passes '--j7-weight 0.0' and would break or mis-parse."
log "GATE 1 PASS — flag surface matches the assumed form."

# band marker (written before game 1, like night_chain's BAND_* files)
{
  echo "band_seed_start=$BAND"
  echo "cell_seed_range=${BAND}..$((BAND + DECKS - 1))  (${DECKS} decks x 2 seats per cell)"
  echo "bench_probe_seed_base=$PROBE_BASE   # disjoint from the cell decks, inside the band label"
  echo "confirm_band=126000000000           # RESERVED, separate authorized launch"
  echo "cells=$CELLS"
  echo "profile=$PROFILE"
  echo "prereg=measurement/joshuabot_20260812/TOURNAMENT_PREREG.md"
  echo "registry=governance/BAND_REGISTRY.csv (rows 1.25e11 screen / 1.26e11 confirm)"
  echo "started=$(ts)"
} > "$BAND_MARK"

# ── GATE 2 + the BENCH: one BASE game, alone, at production knobs ─────────────────────────
BENCH_OUT=$BENCHDIR/bench_base$TAG.jsonl
if [ "$SKIP_BENCH" = "1" ] && [ -f "$BENCH_JSON" ]; then
  S_GAME=$("$PY" -c "import json;print(json.load(open('$BENCH_JSON'))['s_per_game'])") \
    || fail "could not re-read s_per_game from $BENCH_JSON"
  log "BENCH skipped by JB_SKIP_BENCH=1 — reusing s/game=$S_GAME"
else
  log "BENCH: $BENCH_LIMIT game(s), BASE variant, seed_base=$PROBE_BASE (disjoint from cells)"
  BW=1; [ "$BENCH_LIMIT" -gt 1 ] && BW=$BENCH_LIMIT
  T0=$(date +%s)
  # shellcheck disable=SC2046
  run_h2h "$BENCH_OUT" "$PROBE_BASE" "$BENCH_LIMIT" "$BW" "$BENCH_LIMIT" \
          "$LOGS/bench$TAG.log" $(cell_flags BASE) \
    || fail "bench run failed — see $LOGS/bench$TAG.log"
  T1=$(date +%s)
  S_GAME=$("$PY" - "$BENCH_OUT" "$BENCH_LIMIT" <<'PYEOF'
import json, sys
recs = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
n = max(1, int(sys.argv[2]))
recs = recs[-n:]
# cell_secs is the worker's own wall time for the game; the mean over completions is the
# rate of record (never the first completion — the order-statistic trap).
print(round(sum(float(r["cell_secs"]) for r in recs) / len(recs), 2))
PYEOF
) || fail "could not read cell_secs from the bench record ($BENCH_OUT)"
  log "BENCH: s/game=$S_GAME (wave wall $((T1 - T0)) s, $BENCH_LIMIT game(s), W=$BW)"

  # GATE 2 — the bench record must prove the production path
  "$PY" - "$BENCH_OUT" <<'PYEOF' || fail "GATE 2 FAILED — the bench game did not run the production path (see the printed record fields)"
import json, sys
r = [json.loads(l) for l in open(sys.argv[1]) if l.strip()][-1]
ex = json.dumps(r.get("execution"))
bad = []
if r.get("rules_profile") != "fixed_v1":       bad.append(f"rules_profile={r.get('rules_profile')}")
if "rust" not in ex.lower():                   bad.append(f"execution={ex}")
if not r.get("champion_id"):                   bad.append("champion_id missing")
if not r.get("total_sims_of_record"):          bad.append("total_sims_of_record missing")
print("GATE2", "FAIL " + "; ".join(bad) if bad else "OK",
      json.dumps({k: r.get(k) for k in ("rules_profile", "champion_id",
                                        "total_sims_of_record", "k_dets_of_record",
                                        "leaf_hash", "ms_per_move_champ",
                                        "ms_per_move_joshua")}))
sys.exit(1 if bad else 0)
PYEOF
  log "GATE 2 PASS — fixed_v1 + rust + verified champion at the PRODUCTION.yaml budget."
  { echo "{\"s_per_game\": $S_GAME, \"bench_games\": $BENCH_LIMIT, \"utc\": \"$(ts)\"}"; } > "$BENCH_JSON"
fi

awk -v s="$S_GAME" -v m="$MAX_SGAME" 'BEGIN{exit !(s > 0 && s < m)}' \
  || fail "bench s/game=$S_GAME is outside (0, $MAX_SGAME) — the signature of a python-backend fallback or a mis-resolved champion. Not spending 1800 games on it."

# GATE 3 for BASE comes free from the bench manifest
check_axes "$BENCH_OUT.manifest.json" BASE \
  || fail "GATE 3 FAILED for BASE — the bench manifest's resolved axes are not the BASE variant."

# ── GATE 3: 1-game axis-wiring probes for the remaining cells, run concurrently ───────────
PROBE_PIDS=""; PROBE_CELLS=""
for cell in $CELLS; do
  [ "$cell" = "BASE" ] && continue
  [ -n "$(cell_flags "$cell")" ] || fail "unknown cell '$cell' in JB_CELLS"
  k=$(cell_index "$cell")
  # shellcheck disable=SC2046
  run_h2h "$PROBEDIR/probe_${cell}$TAG.jsonl" "$((PROBE_BASE + 10 + k))" 1 1 1 \
          "$LOGS/probe_${cell}$TAG.log" $(cell_flags "$cell") &
  PROBE_PIDS="$PROBE_PIDS $!"; PROBE_CELLS="$PROBE_CELLS $cell"
done
if [ -n "$PROBE_PIDS" ]; then
  log "GATE 3: 1-game axis probes running concurrently for$PROBE_CELLS"
  PRC=0
  for p in $PROBE_PIDS; do wait "$p" || PRC=1; done
  [ "$PRC" -eq 0 ] || fail "an axis probe crashed — see $LOGS/probe_*.log"
  for cell in $PROBE_CELLS; do
    check_axes "$PROBEDIR/probe_${cell}$TAG.jsonl.manifest.json" "$cell" \
      || fail "GATE 3 FAILED for $cell — the driver's resolved axes are not what the cell's flags asked for. A silently-ignored flag would make this cell a duplicate of another and buy a guaranteed null."
  done
fi
log "GATE 3 PASS — every cell's flags land on the bot's resolved params."

# fire-count observation — DESCRIPTIVE ONLY (prereg section 9.4): never gates, drops or re-tunes a cell
"$PY" - "$PROBEDIR" "$BENCH_OUT" "$PROBEDIR/PROBE_FIRES$TAG.json" <<'PYEOF' 2>/dev/null | while read -r ln; do log "PROBE-FIRES $ln"; done
import glob, json, os, sys
out = {}
paths = [(os.path.basename(p).split("probe_")[-1].split(".jsonl")[0], p)
         for p in sorted(glob.glob(os.path.join(sys.argv[1], "probe_*.jsonl")))]
paths.append(("BASE(bench)", sys.argv[2]))
for name, p in paths:
    try:
        recs = [json.loads(l) for l in open(p) if l.strip()]
    except OSError:
        continue
    if recs:
        out[name] = recs[-1].get("joshua_rule_fires") or {}
json.dump(out, open(sys.argv[3], "w"), indent=1)
for name, fires in out.items():
    live = {k: v for k, v in fires.items() if v}
    print(f"{name}: " + (json.dumps(live) if live else "NO RULE FIRED IN THE PROBE GAME (WARN: "
          "descriptive only — a cell whose rule never fires is destined to read null)"))
PYEOF

# ── plan: which cells fit the remaining W_HI window, by the degradation priority order ────
GAMES=$((DECKS * 2))
LEFT=$(mins_to_close)
PER_HI=$(est_min "$GAMES" "$W_HI")
PER_LO=$(est_min "$GAMES" "$W_LO")
log "PLAN: ${GAMES} games/cell; est ${PER_HI} min at W${W_HI}, ${PER_LO} min at W${W_LO}; W${W_HI} window has ${LEFT} min left"

KEEP=""; DEFER=""; ACC=0
if [ "$LEFT" -le 0 ]; then
  KEEP="$CELLS"
  log "PLAN: the W${W_HI} window is CLOSED (daytime launch) — the whole chain runs at W${W_LO} per the grant's 'then w14'. No cells deferred."
else
  for cell in $PRIORITY; do
    case " $CELLS " in *" $cell "*) ;; *) continue ;; esac
    if [ -f "$DIR/DONE_${cell}$TAG" ]; then KEEP="$KEEP $cell"; continue; fi
    if [ $((ACC + PER_HI)) -le "$LEFT" ]; then
      ACC=$((ACC + PER_HI)); KEEP="$KEEP $cell"
    else
      DEFER="$DEFER $cell"
    fi
  done
  if [ -z "$KEEP" ]; then
    KEEP="BASE"; DEFER=$(echo "$DEFER" | sed 's/ BASE//')
    log "PLAN: not even one cell fits the window — keeping BASE anyway (it is the reference every contrast needs) and letting it run at W${W_LO}."
  fi
fi
KEEP=$(echo "$KEEP" | tr -s ' ' | sed 's/^ //;s/ $//')
DEFER=$(echo "$DEFER" | tr -s ' ' | sed 's/^ //;s/ $//')
{
  echo "planned_at=$(ts)"
  echo "s_per_game_bench=$S_GAME  (contention constants: W${W_HI} x${C30}, W${W_LO} x${C14} — PLANNING CONSTANTS, not measurements)"
  echo "est_min_per_cell_W${W_HI}=$PER_HI   est_min_per_cell_W${W_LO}=$PER_LO"
  echo "window_min_left=$LEFT"
  echo "priority_order=$PRIORITY"
  echo "KEEP=$KEEP"
  echo "DEFER=$DEFER"
} > "$PLAN_MARK"
log "PLAN: KEEP='$KEEP'  DEFER='$DEFER'"
if [ -n "$DEFER" ]; then
  {
    echo "# Cells that did not fit the W${W_HI} window at the benched s/game=$S_GAME ($(ts))."
    echo "# NOT dropped — run them at W${W_LO} after 11:00, or on the laptop (48h grant):"
    for c in $DEFER; do
      echo "JB_CELLS=\"$c\" JB_SKIP_BENCH=1 bash $REPO/scripts/joshuabot/tournament_chain.sh"
    done
  } > "$DEFER_MARK"
  log "DEFERRED cells written to $DEFER_MARK"
else
  rm -f "$DEFER_MARK"
fi

# ── the cells, sequentially ──────────────────────────────────────────────────────────────
INCOMPLETE=""
for cell in $KEEP; do
  if [ -f "$DIR/DONE_${cell}$TAG" ]; then log "CELL $cell: already DONE — skipping."; continue; fi
  OUT=$CELLDIR/${cell}$TAG.jsonl
  # W is chosen at CELL START: W_HI only if the window is open AND this cell is projected to
  # finish before it closes — a W_HI cell must never straddle 11:00.
  LEFT=$(mins_to_close)
  if [ "$LEFT" -gt 0 ] && [ "$PER_HI" -le "$LEFT" ]; then W=$W_HI; else W=$W_LO; fi
  EST=$(est_min "$GAMES" "$W")
  log "CELL $cell: START W=$W est=${EST} min (window ${LEFT} min left) seeds ${BAND}..$((BAND + DECKS - 1)) out=$OUT"
  T0=$(date +%s)
  # shellcheck disable=SC2046
  run_h2h "$OUT" "$BAND" "$DECKS" "$W" 0 "$LOGS/cell_${cell}$TAG.log" $(cell_flags "$cell")
  RC=$?
  T1=$(date +%s)
  N=$(n_records "$OUT")
  log "CELL $cell: driver rc=$RC records=$N/$GAMES wall=$(( (T1 - T0) / 60 )) min"
  if [ "$RC" -ne 0 ]; then
    log "CELL $cell: NON-ZERO rc — leaving it un-DONE (re-running this chain resumes it) and continuing to the next cell."
    INCOMPLETE="$INCOMPLETE $cell"
    continue
  fi
  if [ "$N" -lt "$GAMES" ]; then
    : > "$DIR/INCOMPLETE_${cell}$TAG"
    log "CELL $cell: INCOMPLETE ($N < $GAMES) — marker written, NOT marked DONE."
    INCOMPLETE="$INCOMPLETE $cell"
    continue
  fi
  check_axes "$OUT.manifest.json" "$cell" \
    || fail "post-run axis check FAILED for $cell — the completed cell is not the variant it claims to be."
  log "CELL $cell extract: $(write_summary "$OUT" "$SUMDIR/${cell}$TAG.json")"
  : > "$DIR/DONE_${cell}$TAG"
  rm -f "$DIR/INCOMPLETE_${cell}$TAG"
  log "CELL $cell: DONE"
done

# ── close ────────────────────────────────────────────────────────────────────────────────
{
  echo "DONE $(ts)"
  echo "band=$BAND decks/cell=$DECKS games/cell=$GAMES profile=$PROFILE"
  echo "bench_s_per_game=$S_GAME"
  echo "cells_run=$KEEP"
  echo "cells_deferred=${DEFER:-none}"
  echo "cells_incomplete=${INCOMPLETE:-none}"
  echo "extracts=$SUMDIR   (EXTRACTS ONLY — no verdict, no promotion; read against the prereg)"
  echo "NEXT: the orchestrator adjudicates per TOURNAMENT_PREREG.md sections 5-6. The CONFIRM"
  echo "      (n=400 decks on the FRESH band 126000000000) is a SEPARATE authorized launch."
} > "$DONE_MARK"
log "TOURNAMENT CHAIN FINISHED — wrote $DONE_MARK"
[ -n "$INCOMPLETE" ] && log "NOTE: incomplete cells:$INCOMPLETE (re-run this chain to resume them)"
exit 0
