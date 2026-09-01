#!/usr/bin/env bash
# =========================================================================== #
# τ_p AUDIT LEG — THE LAUNCHER.  measurement/taup_audit_leg_20260901/          #
#                                                                             #
# Two cells, one box (the LAPTOP), 800 deck-paired games each at the deployed  #
# champion config on BOTH seats. The single variable is `--cand-tau-p`, the    #
# flag this leg builds; see PREREG.md.                                        #
#                                                                             #
# ⚠️⚠️ IT RUNS **ON** THE LAPTOP, via the house pipe pattern:                  #
#        ssh laptop-wsl 'bash -s' < run_cells.sh -- --cell CELL_TAU3          #
#      NEVER the inline `ssh host 'cd .. && ..'` form — the cd gets STRIPPED   #
#      IN TRANSIT (feedback_remote_ssh_pipe_script_mandatory).                #
#                                                                             #
# ⚠️ LAUNCH DETACHED. Mac-sleep SIGHUP and WSL VM-teardown both kill           #
#    tty-attached jobs. This script SELF-DETACHES with setsid unless           #
#    --no-detach is passed, and drops a RUN_LIVE sentinel while it runs.       #
#                                                                             #
# USAGE                                                                       #
#   ./run_cells.sh --cell CELL_TAU3|CELL_TAU8 [--smoke] [--dry-run] [--plan]  #
#                  [--no-detach]                                              #
#                                                                             #
#   --plan     what is DONE / partial; spends nothing                         #
#   --dry-run  print the exact argv and exit; spends nothing                  #
#   --smoke    the per-cell pre-launch smoke at PRODUCTION knobs on the        #
#              throwaway sub-range, then ADJUDICATE IT from its own manifest   #
#              (nonzero exit on empty — the R1 defect class)                   #
#                                                                             #
# ⛔ REFUSALS (all fail CLOSED, before a deck is spent):                       #
#   * BLIND_COMMIT still PENDING            -> real cells refused              #
#   * sibling file BAND_CLAIMED absent      -> real cells refused              #
#   * TAUP_BITEXACT.json missing / not PASS / not the FULL frozen seed set     #
#                                          -> real cells AND smokes refused    #
#   * this box cannot express --cand-tau-p  -> everything refused              #
#   * PRODUCTION.yaml disagrees with the frozen budget/arbiter (G-PROD)        #
#                                          -> everything refused               #
# =========================================================================== #
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
. "$HERE/WORKERS.conf"

CELL=""; DRY=0; SMOKE=0; PLAN=0; DETACH=1
while [ $# -gt 0 ]; do
  case "$1" in
    --cell) CELL="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    --smoke) SMOKE=1; shift ;;
    --plan) PLAN=1; shift ;;
    --no-detach) DETACH=0; shift ;;
    --) shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$CELL" ] || { echo "--cell CELL_TAU3|CELL_TAU8 is required" >&2; exit 2; }

case "$CELL" in
  CELL_TAU3) TAU="$TAU_DOSE_LOW";  BAND="$BAND_TAU3"; SMOKE_OFF=0   ;;
  CELL_TAU8) TAU="$TAU_DOSE_HIGH"; BAND="$BAND_TAU8"; SMOKE_OFF=100 ;;
  *) echo "unknown cell: $CELL (CELL_TAU3 | CELL_TAU8)" >&2; exit 2 ;;
esac

# ⚠️ The venv is editable-installed against the MAIN tree, so a copy of this
# script running from a git WORKTREE has no `.venv` beside it. Fall back to the
# canonical one rather than dying — the worktree case is a BUILD/dry-run case.
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY="/home/doctor/projects/carcassone/.venv/bin/python"

OUT_ROOT="$SHARE_LAPTOP/$OUT_TAG"
LOG_DIR="$HERE/logs"
SENTINEL="$HERE/RUN_LIVE.json"

STAMP() { echo "[$(date -u +%H:%M:%SZ)] $*"; }
DIE()   { echo "⛔⛔ $*" >&2; rm -f "$SENTINEL"; exit 1; }

# --------------------------------------------------------------------------- #
# 0. SELF-DETACH                                                               #
# --------------------------------------------------------------------------- #
# ⚠️ The harness's own background flag is NOT enough — the python child must be
# explicitly detached. Re-exec under setsid, niced, with the log on disk.
if [ "$DETACH" -eq 1 ] && [ "$DRY" -eq 0 ] && [ "$PLAN" -eq 0 ] \
   && [ "${TAUP_DETACHED:-0}" != "1" ]; then
  mkdir -p "$LOG_DIR"
  LOG="$LOG_DIR/${CELL}$([ "$SMOKE" -eq 1 ] && echo _smoke).log"
  STAMP "detaching -> $LOG"
  TAUP_DETACHED=1 setsid nohup nice -n 19 "$0" --cell "$CELL" --no-detach \
      $([ "$SMOKE" -eq 1 ] && echo --smoke) >> "$LOG" 2>&1 &
  disown || true
  STAMP "detached pid $! (tail -f $LOG)"
  exit 0
fi

# --------------------------------------------------------------------------- #
# 1. PLAN — spends nothing                                                     #
# --------------------------------------------------------------------------- #
if [ "$PLAN" -eq 1 ]; then
  D="$OUT_ROOT/$CELL"
  echo "cell        : $CELL   tau_p=$TAU (shared stays $TAU_P_PRODUCTION)"
  echo "band        : $BAND   seeds $BAND .. $((BAND + N_DECKS - 1))"
  echo "shape       : k${K_DETS}x${SIMS_PER_DET}=$TOTAL_SIMS both seats, "\
"exact_k $EXACT_K $EXACT_MODE, $BACKEND, $RULES_PROFILE + R9, arbiter ARMED both seats"
  echo "out         : $D"
  if [ -d "$D" ]; then
    echo "played      : $(find "$D" -name 'seed*_a*.json' 2>/dev/null | wc -l) / $N_GAMES game records"
    echo "summary     : $([ -f "$D/summary.json" ] && echo present || echo ABSENT)"
  else
    echo "played      : 0 / $N_GAMES (out-dir does not exist)"
  fi
  # ETA is a BRACKET, not a point: no W=24 rate has been measured at this shape.
  echo "ETA         : $(awk -v n=$N_GAMES -v lo=$G_PER_H_LAPTOP_LO -v hi=$G_PER_H_LAPTOP_HI \
        'BEGIN{printf "%.2f-%.2f h at W='"$W_LAPTOP"'", n/hi, n/lo}')"
  exit 0
fi

# --------------------------------------------------------------------------- #
# 2. THE REFUSALS — all fail CLOSED, before a deck is spent                     #
# --------------------------------------------------------------------------- #
# --- 2a. the golden gate --------------------------------------------------- #
# ⛔ Applies to the SMOKE too: a smoke run over unproven plumbing is a smoke of
# a champion-vs-champion cell wearing this cell's name.
GATE="$HERE/TAUP_BITEXACT.json"
[ -f "$GATE" ] || DIE "$GATE is missing — the --cand-tau-p golden gate has not \
been run. goldengate/run_gate.sh, then relaunch."
# ⚠️ The VERDICT is required in every mode (a dry-run that printed an argv for
# unproven plumbing would be a launch checklist item nobody re-checks). The
# FULL-FROZEN-SEED-SET requirement binds only modes that spend compute: a
# build-time PREVIEW pass is a real pass of what it tested, and --dry-run/--plan
# spend nothing.
"$PY" - "$GATE" "$DRY" <<'PYGATE' || DIE "the golden gate does not authorise this"
import json, sys
g = json.load(open(sys.argv[1]))
dry = sys.argv[2] == "1"
bad = []
if g.get("verdict") != "PASS":
    bad.append(f"verdict={g.get('verdict')!r} (failed: {g.get('failed')})")
if not g.get("full_frozen_set") and not dry:
    bad.append(f"seeds_played={g.get('seeds_played')} != frozen "
               f"{g.get('frozen_seed_count')} — a PREVIEW pass is a real pass of "
               "what it tested, but it is NOT the frozen gate and may not "
               "authorise compute or a band")
if bad:
    print("⛔⛔ " + "; ".join(bad)); sys.exit(1)
note = ("" if g.get("full_frozen_set")
        else f"  ⚠️ PREVIEW ONLY ({g.get('seeds_played')}/"
             f"{g.get('frozen_seed_count')} seeds) — dry-run exempt, a real run "
             "is NOT")
print(f"[gate] TAUP_BITEXACT PASS{note}")
PYGATE

# --- 2b. blindness + band (REAL CELLS ONLY; the smoke spends neither) ------ #
if [ "$SMOKE" -eq 0 ] && [ "$DRY" -eq 0 ]; then
  [ "$BLIND_COMMIT" != "PENDING" ] || DIE "BLIND_COMMIT is still PENDING in \
WORKERS.conf. The freeze commit lands the pair with PENDING; a SECOND, stamping \
commit writes its 40-hex sha. REFUSING to spend a band blind-unstamped."
  [ -f "$HERE/BAND_CLAIMED" ] || DIE "$HERE/BAND_CLAIMED does not exist. This \
agent PROPOSED bands $BAND_TAU3 / $BAND_TAU8 and CLAIMED NOTHING — see \
BAND_CLAIMED.placeholder. The orchestrator re-runs the tree sweep, appends TWO \
rows to governance/BAND_REGISTRY.csv and drops that file. REFUSING."
fi

# --- 2c. can THIS box express the cell? ------------------------------------ #
# ⛔⛔ THE PROBE. Every other gate would pass a box whose bundle predates the
# --cand-tau-p plumbing, and the cell it produced would be champion-vs-champion
# with a healthy wheel, a healthy leaf hash and a perfectly plausible dirname.
"$PY" - "$REPO" "$TAU" "$TAU_P_PRODUCTION" <<'PYPROBE' \
  || DIE "a plumbing probe FAILED on this box — REFUSING."
import contextlib, io, sys
repo, tau, shared = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
sys.path.insert(0, repo + "/scripts/human_anchor")
import env_preamble  # noqa: F401
sys.path.insert(0, repo + "/scripts/classical_search")
import eval_fair_puct as E
bad = []

# (1) THE FLAG EXISTS IN THE REAL ARGPARSE (not merely in the source text).
buf = io.StringIO()
try:
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        E.main(["--help"])
except SystemExit:
    pass
if "--cand-tau-p" not in buf.getvalue():
    bad.append("eval_fair_puct's argparse has NO --cand-tau-p")

# (2) IT REACHES THE CANDIDATE CONFIG — and NOT the opponent's.
cs = {"fpu_reduction": None, "c_puct": None, "tau_p": tau,
      "shared_c_puct": 1.5, "shared_tau_p": shared}
cand = E._build_champ_cfg(1.5, shared, "float", "visits", 15.0, None,
                          cand_search=cs)
opp = E._cfg_from_dict({"c_puct": 1.5, "tau_p": shared, "leaf_quantize": "float",
                        "final_select": "visits", "value_norm": 15.0,
                        "fpu_reduction": None}, None)
if cand.tau_p != tau:
    bad.append(f"the candidate config resolved tau_p={cand.tau_p!r}, not {tau!r}")
if opp.tau_p != shared:
    bad.append(f"⛔⛔ the OPPONENT config resolved tau_p={opp.tau_p!r}, not the "
               f"shared {shared!r} — the dose LEAKED onto the opponent")

# (3) IT REACHES THE RUST BACKEND THAT ACTUALLY PLAYS.
from carcassonne_ai.rust_agent import search_config_rs
import re
r = repr(search_config_rs(cand, 8))
m = re.search(r"tau_p=([-0-9.eE+]+)", r)
if m is None or float(m.group(1)) != tau:
    bad.append(f"SearchConfigRs did not bind tau_p={tau!r}: {r}")

# (4) the paired work-builder still yields the contiguous range this leg's band
#     arithmetic depends on.
w = E._build_work(1000, 6, True)
if w != [(1000,0),(1000,1),(1001,0),(1001,1),(1002,0),(1002,1)]:
    bad.append("_build_work(seed_start, n, paired=True) changed shape: " + repr(w))

if bad:
    print("⛔⛔ THIS BOX CANNOT EXPRESS THE CELL: " + "; ".join(bad))
    print("The source here predates measurement/taup_audit_leg_20260901's "
          "eval_fair_puct patch. A cell run from this box would be "
          "champion-vs-champion. Sync the bundle.")
    sys.exit(1)
print(f"[probe] this box binds cand tau_p={tau} on the candidate ONLY (opponent "
      f"stays {shared}), all the way into SearchConfigRs")
PYPROBE

# --- 2d. G-PROD: the frozen shape still IS production ---------------------- #
"$PY" - "$REPO/governance/PRODUCTION.yaml" "$K_DETS" "$SIMS_PER_DET" \
        "$TIEARB_B" "$TIEARB_J" "$TIEARB_MODE" "$TIEARB_SALT" "$TIEARB_EPS" \
        "$TAU_P_PRODUCTION" \
  <<'PYPROD' || DIE "G-PROD FAILED — the frozen shape has drifted from production."
# ⚠️⚠️ PARSED AS YAML AT EXPLICIT ADDRESSES, NEVER GREPPED. PRODUCTION.yaml
# carries a `deploy_profiles.mobile` block with the SAME key names
# (k_dets/sims_per_det/tiearb) at DIFFERENT values, so a `^\s+k_dets:` regex
# matches whichever block comes first and would silently re-assert the frozen
# desktop shape against a mobile number.
import sys, yaml
p, kd, sims, b, j, mode, salt, eps, tau = sys.argv[1:10]
d = yaml.safe_load(open(p))
def at(*path):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur
bad = []
CH = ("champion",)
for path, want, cast in (
        (CH + ("fair_deploy", "k_dets"), int(kd), int),
        (CH + ("fair_deploy", "sims_per_det"), int(sims), int),
        (CH + ("agent_knobs", "tau_p"), float(tau), float),
        (CH + ("fair_deploy", "tiearb", "enabled"), True, bool),
        (CH + ("fair_deploy", "tiearb", "B"), int(b), int),
        (CH + ("fair_deploy", "tiearb", "J"), int(j), int),
        (CH + ("fair_deploy", "tiearb", "mode"), mode, str),
        (CH + ("fair_deploy", "tiearb", "salt"), salt, str),
        (CH + ("fair_deploy", "tiearb", "eps"), float(eps), float)):
    got = at(*path)
    addr = ".".join(path)
    if got is None:
        bad.append(f"PRODUCTION.yaml has no `{addr}` — cannot re-assert it")
    elif cast(got) != want:
        bad.append(f"PRODUCTION.yaml {addr}={got!r} but this leg froze {want!r}")
# ⚠️ PRODUCTION.yaml carries NO phase_gate key, because the deployed arbiter is
# UNGATED — and "all" is exactly how the harness spells ungated. Assert the
# ABSENCE rather than letting an argparse default decide it.
if at(*CH, "fair_deploy", "tiearb", "phase_gate") is not None:
    bad.append("PRODUCTION.yaml has grown a fair_deploy.tiearb.phase_gate — this "
               "leg froze the UNGATED arbiter ('all') on the strength of its "
               "absence; re-read the pair before launching")
if bad:
    print("⛔⛔ " + "; ".join(bad)); sys.exit(1)
print("[G-PROD] the frozen budget/arbiter/tau_p still match PRODUCTION.yaml "
      "at champion.fair_deploy / champion.agent_knobs")
PYPROD

# --- 2e. census by FULL ARGS, never -C python ------------------------------ #
# ⚠️ A silent long job is invisible to `ps -C python`. No timing statistic is a
# branch input here, so tenancy is RESULT-safe — the census is still owed.
if [ "$DRY" -eq 0 ]; then
  STAMP "process census (FULL ARGS):"
  ps -eo pid,etime,pcpu,args --sort=-etime | grep -E "python|carc" | grep -v grep \
    | head -20 | sed 's/^/    /'
fi

export CARCASSONNE_FIX_R9="$CARCASSONNE_FIX_R9"   # ⚠️ env-latched at IMPORT
export PYTHONUNBUFFERED=1
# ⚠️ NOT in --dry-run: the share path is the LAPTOP's mount and does not exist
# on the build box, and a dry-run must touch no filesystem it is not going to use.
[ "$DRY" -eq 1 ] || mkdir -p "$OUT_ROOT" "$LOG_DIR"

# --------------------------------------------------------------------------- #
# 3. ONE CELL                                                                  #
# --------------------------------------------------------------------------- #
run_cell() {
  local name="$1" seed_start="$2" n_games="$3"
  local out="$OUT_ROOT/$name"
  [ "$DRY" -eq 1 ] || mkdir -p "$out"
  local args=(
    "$REPO/scripts/classical_search/eval_fair_puct.py"
    --backend "$BACKEND" --info fair
    --k-dets "$K_DETS" --sims "$SIMS_PER_DET"
    --opp-k-dets "$K_DETS" --opp-sims "$SIMS_PER_DET"
    --exact-k "$EXACT_K"
    --opponent fair-champion
    # ⛔⛔ WITHOUT --paired THE LEG HAS NO PRIMARY (PG-D9) and it walks 2*N_DECKS
    # seeds — outside its own frozen band.
    --n "$n_games" --paired --seed-start "$seed_start"
    # ⚠️ `--out` is AMBIGUOUS in eval_fair_puct and argparse REFUSES it (PG-D7).
    --workers "$W_LAPTOP" --out-root "$OUT_ROOT" --out-subdir "$name"
    # ⚠️ WITHOUT THIS THE LEG RUNS `walled` (PG-D8).
    --rules-profile "$RULES_PROFILE"
    # ⭐⭐ THE ARBITER, ON **BOTH** SEATS, AT THE FULL DEPLOYED SPEC.
    --cand-tiearb-enabled --cand-tiearb-b "$TIEARB_B" --cand-tiearb-j "$TIEARB_J"
    --cand-tiearb-mode "$TIEARB_MODE" --cand-tiearb-salt "$TIEARB_SALT"
    --cand-tiearb-eps "$TIEARB_EPS" --cand-tiearb-phase-gate "$TIEARB_PHASE_GATE"
    --opp-tiearb-enabled --opp-tiearb-b "$TIEARB_B" --opp-tiearb-j "$TIEARB_J"
    --opp-tiearb-mode "$TIEARB_MODE" --opp-tiearb-salt "$TIEARB_SALT"
    --opp-tiearb-eps "$TIEARB_EPS" --opp-tiearb-phase-gate "$TIEARB_PHASE_GATE"
    # ⛔⛔ THE SINGLE VARIABLE — and note there is NO bare --tau-p, no --c-puct,
    # no --cand-c-puct and no --cand-fpu-reduction anywhere in this script, by
    # construction.
    --cand-tau-p "$TAU"
  )
  # ⚠️ The SMOKE plays the throwaway sub-range, which is outside the clean-eval
  # seed range the harness asserts on. A REAL cell never passes this.
  if [ "${4:-}" = "throwaway" ]; then
    args+=(--allow-selfplay-seeds)
  fi
  if [ "$BLIND_COMMIT" != "PENDING" ]; then
    args+=(--stamp-key "BLIND_COMMIT=$BLIND_COMMIT")
  fi
  if [ "$DRY" -eq 1 ]; then
    STAMP "[dry-run] $name tau_p=$TAU seeds=${seed_start}.. n=$n_games -> $out"
    printf '    %q ' "$PY" "${args[@]}"; echo
    return 0
  fi
  STAMP "$name tau_p=$TAU seeds=${seed_start}.. n=$n_games W=$W_LAPTOP -> $out"
  nice -n 19 "$PY" "${args[@]}" || DIE "$name FAILED"
}

# --------------------------------------------------------------------------- #
# 4. THE SMOKE — production knobs, throwaway seeds, self-adjudicated           #
# --------------------------------------------------------------------------- #
if [ "$SMOKE" -eq 1 ]; then
  SMOKE_NAME="SMOKE_${CELL}_laptop"
  SMOKE_SEED=$((THROWAWAY_BASE + SMOKE_OFF))
  [ "$DRY" -eq 1 ] || cat > "$SENTINEL" <<EOF
{"cell": "$SMOKE_NAME", "kind": "smoke", "pid": $$, "host": "$(hostname)",
 "started_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "out": "$OUT_ROOT/$SMOKE_NAME",
 "spends_band": false}
EOF
  run_cell "$SMOKE_NAME" "$SMOKE_SEED" "$SMOKE_GAMES" throwaway
  if [ "$DRY" -eq 0 ]; then
    # ⛔⛔ ADJUDICATE THE SMOKE FROM ITS OWN EMITTED MANIFEST. Nonzero exit on an
    # empty or manifest-less cell — the R1 defect class. A smoke that "ran" and
    # produced nothing must not read as a green light.
    "$PY" "$HERE/adjudicate_smoke.py" --root "$OUT_ROOT" --cell "$SMOKE_NAME" \
        --dose "$TAU" --out "$HERE/SMOKE_${CELL}.json" \
      || DIE "the smoke adjudication FAILED — REFUSING to launch $CELL"
    STAMP "smoke adjudicated -> SMOKE_${CELL}.json (structural keys only)"
    rm -f "$SENTINEL"
  fi
  exit 0
fi

# --------------------------------------------------------------------------- #
# 5. THE REAL CELL                                                             #
# --------------------------------------------------------------------------- #
[ "$DRY" -eq 1 ] || cat > "$SENTINEL" <<EOF
{"cell": "$CELL", "kind": "real", "tau_p": $TAU, "band": $BAND, "pid": $$,
 "host": "$(hostname)", "started_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
 "out": "$OUT_ROOT/$CELL", "n_games": $N_GAMES, "spends_band": true,
 "note": "the freeze-latch hook refuses main-tree commits while this exists"}
EOF
run_cell "$CELL" "$BAND" "$N_GAMES"
if [ "$DRY" -eq 1 ]; then
  STAMP "[dry-run] nothing was played, no band was spent"
  exit 0
fi
rm -f "$SENTINEL"
STAMP "$CELL COMPLETE -> $OUT_ROOT/$CELL"
