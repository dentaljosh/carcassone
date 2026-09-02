#!/usr/bin/env bash
# =========================================================================== #
# GT-M1 RISK-ASYMMETRIC WORLD POOLING — THE LAUNCHER.                          #
# measurement/cvar_pool_prep/                                                  #
#                                                                             #
# Two cells, one box (the LAPTOP), 800 deck-paired games each at the deployed  #
# champion config on BOTH seats. The single variable is --cand-pool-mode /     #
# --cand-pool-alpha, the flags this round builds; see PREREG.md.               #
#                                                                             #
# ⚠️⚠️⚠️ IT RUNS **ON** THE LAPTOP, INVOKED **BY ABSOLUTE PATH**:              #
#                                                                             #
#     ssh laptop-wsl '/home/doctor/projects/carcassone/measurement/\           #
#         cvar_pool_prep/run_cells.sh --cell CELL_CVAR25'                      #
#                                                                             #
#   ⛔ **NOT** the pipe form `ssh host 'bash -s' < run_cells.sh -- --cell X`.   #
#      Under `bash -s` the script comes in on STDIN, so ${BASH_SOURCE[0]} is   #
#      NOT A PATH — `HERE` resolves to the remote $HOME and the `.` of         #
#      WORKERS.conf either dies or, far worse, silently sources nothing and    #
#      every constant below becomes an unbound-variable abort mid-ladder. The  #
#      tau_p launcher documents the pipe form in its own header while using    #
#      BASH_SOURCE, which is a latent version of exactly this bug.             #
#   ⭐ The absolute-path form is ALSO what the repo's "never rely on `cd` in   #
#      an SSH command" rule asks for: it depends on no starting directory.     #
#                                                                             #
# ⚠️ LAUNCH DETACHED. Mac-sleep SIGHUP and WSL VM-teardown both kill           #
#    tty-attached jobs. This script SELF-DETACHES with setsid unless           #
#    --no-detach is passed, and drops a RUN_LIVE sentinel while it runs.       #
#                                                                             #
# USAGE                                                                       #
#   ./run_cells.sh --cell CELL_CVAR25|CELL_CVAR50 [--smoke] [--dry-run]        #
#                  [--plan] [--no-detach]                                      #
#                                                                             #
#   --plan     what is DONE / partial; spends nothing                         #
#   --dry-run  print the exact argv and exit; spends nothing                  #
#   --smoke    the per-cell pre-launch smoke at PRODUCTION knobs on the        #
#              throwaway sub-range, then ADJUDICATE IT from its own manifest   #
#              AND summary (nonzero exit on empty, or on a rule that did not   #
#              REACH — the R1 defect class plus this round's own G-REACH)      #
#                                                                             #
# ⛔ REFUSALS (all fail CLOSED, before a deck is spent):                       #
#   * BLIND_COMMIT still PENDING            -> real cells refused              #
#   * sibling file BAND_CLAIMED absent      -> real cells refused              #
#   * CVAR_BITEXACT.json missing / not PASS / not the FULL frozen seed set     #
#                                          -> real cells AND smokes refused    #
#   * this box's WHEEL cannot express the rule -> everything refused           #
#   * this box's SOURCE cannot express the rule -> everything refused          #
#   * PRODUCTION.yaml disagrees with the frozen budget/arbiter (G-PROD)        #
#                                          -> everything refused               #
# =========================================================================== #
set -uo pipefail

# ⛔ FAIL LOUD IF THIS SCRIPT WAS PIPED. `${BASH_SOURCE[0]}` is the file when run
# by path and is `main`/`bash`/empty when the body arrived on stdin. Detecting it
# here turns a silent wrong-directory disaster into a one-line refusal.
if [ -z "${BASH_SOURCE[0]:-}" ] || [ ! -f "${BASH_SOURCE[0]:-/nonexistent}" ]; then
  echo "⛔⛔ run_cells.sh was PIPED (BASH_SOURCE='${BASH_SOURCE[0]:-}'), not run" >&2
  echo "   by path. It resolves WORKERS.conf from its own location, so a piped" >&2
  echo "   invocation would source NOTHING and every constant would be unbound." >&2
  echo "   Use:  ssh laptop-wsl '/home/doctor/projects/carcassone/measurement/cvar_pool_prep/run_cells.sh --cell CELL_CVAR25'" >&2
  exit 2
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
[ -f "$HERE/WORKERS.conf" ] || { echo "⛔ no WORKERS.conf beside $0" >&2; exit 2; }
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
[ -n "$CELL" ] || { echo "--cell CELL_CVAR25|CELL_CVAR50 is required" >&2; exit 2; }

case "$CELL" in
  CELL_CVAR25) ALPHA="$ALPHA_LOW";  BAND="$BAND_CVAR25"; SMOKE_OFF=0   ;;
  CELL_CVAR50) ALPHA="$ALPHA_HIGH"; BAND="$BAND_CVAR50"; SMOKE_OFF=100 ;;
  *) echo "unknown cell: $CELL (CELL_CVAR25 | CELL_CVAR50)" >&2; exit 2 ;;
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
if [ "$DETACH" -eq 1 ] && [ "$DRY" -eq 0 ] && [ "$PLAN" -eq 0 ] \
   && [ "${CVAR_DETACHED:-0}" != "1" ]; then
  mkdir -p "$LOG_DIR"
  LOG="$LOG_DIR/${CELL}$([ "$SMOKE" -eq 1 ] && echo _smoke).log"
  STAMP "detaching -> $LOG"
  CVAR_DETACHED=1 setsid nohup nice -n 19 "${BASH_SOURCE[0]}" --cell "$CELL" \
      --no-detach $([ "$SMOKE" -eq 1 ] && echo --smoke) >> "$LOG" 2>&1 &
  disown || true
  STAMP "detached pid $! (tail -f $LOG)"
  exit 0
fi

# --------------------------------------------------------------------------- #
# 1. PLAN — spends nothing                                                     #
# --------------------------------------------------------------------------- #
if [ "$PLAN" -eq 1 ]; then
  D="$OUT_ROOT/$CELL"
  echo "cell        : $CELL   pool=$POOL_MODE alpha=$ALPHA (opponent stays 'mean')"
  echo "band        : $BAND   seeds $BAND .. $((BAND + N_DECKS - 1))"
  echo "tail width  : ceil($ALPHA * $K_DETS) worlds of $K_DETS"
  echo "shape       : k${K_DETS}x${SIMS_PER_DET}=$TOTAL_SIMS both seats, "\
"exact_k $EXACT_K $EXACT_MODE, $BACKEND, $RULES_PROFILE + R9, arbiter ARMED both seats"
  echo "out         : $D"
  if [ -d "$D" ]; then
    echo "played      : $(find "$D" -name 'seed*_a*.json' 2>/dev/null | wc -l) / $N_GAMES game records"
    echo "summary     : $([ -f "$D/summary.json" ] && echo present || echo ABSENT)"
  else
    echo "played      : 0 / $N_GAMES (out-dir does not exist)"
  fi
  echo "ETA         : $(awk -v n=$N_GAMES -v r=$G_PER_H_LAPTOP \
        'BEGIN{printf "%.2f h at W='"$W_LAPTOP"' (measured %.0f g/h)", n/r, r}')"
  exit 0
fi

# --------------------------------------------------------------------------- #
# 2. THE REFUSALS — all fail CLOSED, before a deck is spent                     #
# --------------------------------------------------------------------------- #
# --- 2a. the golden gate --------------------------------------------------- #
# ⛔ Applies to the SMOKE too: a smoke run over unproven plumbing is a smoke of
# a champion-vs-champion cell wearing this cell's name.
GATE="$HERE/CVAR_BITEXACT.json"
[ -f "$GATE" ] || DIE "$GATE is missing — the GT-M1 golden gate has not been \
run. goldengate/run_gate.sh, then relaunch."
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
print(f"[gate] CVAR_BITEXACT PASS{note}")
PYGATE

# --- 2b. blindness + band (REAL CELLS ONLY; the smoke spends neither) ------ #
if [ "$SMOKE" -eq 0 ] && [ "$DRY" -eq 0 ]; then
  [ "$BLIND_COMMIT" != "PENDING" ] || DIE "BLIND_COMMIT is still PENDING in \
WORKERS.conf. The freeze commit lands the pair with PENDING; a SECOND, stamping \
commit writes its 40-hex sha. REFUSING to spend a band blind-unstamped."
  [ -f "$HERE/BAND_CLAIMED" ] || DIE "$HERE/BAND_CLAIMED does not exist. This \
agent PROPOSED bands $BAND_CVAR25 / $BAND_CVAR50 and CLAIMED NOTHING — see \
BAND_CLAIMED.placeholder. The orchestrator re-runs the tree sweep, appends TWO \
rows to governance/BAND_REGISTRY.csv and drops that file. REFUSING."
fi

# --- 2c. can THIS box express the cell? ------------------------------------ #
# ⛔⛔ THE PROBE, IN THREE LAYERS. Every other gate would pass a box whose
# SOURCE or whose WHEEL predates this round, and the cell it produced would be
# champion-vs-champion with a healthy leaf hash and a perfectly plausible
# dirname. ⚠️ THE WHEEL LAYER IS NEW TO THIS ROUND: fpu / c_puct / tau_p were
# python-only plumbing, so a bundle sync was enough. GT-M1 changes carc_core,
# so a box with a fresh bundle and a STALE WHEEL is a live failure mode and the
# most likely one at fleet roll-out.
"$PY" - "$REPO" "$POOL_MODE" "$ALPHA" "$K_DETS" <<'PYPROBE' \
  || DIE "a plumbing probe FAILED on this box — REFUSING."
import contextlib, io, math, sys
repo, mode, alpha, k_dets = sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4])
sys.path.insert(0, repo + "/scripts/human_anchor")
import env_preamble  # noqa: F401
sys.path.insert(0, repo + "/scripts/classical_search")
import eval_fair_puct as E
bad = []

# (1) THE FLAGS EXIST IN THE REAL ARGPARSE (not merely in the source text).
buf = io.StringIO()
try:
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        E.main(["--help"])
except SystemExit:
    pass
helptext = buf.getvalue()
for flag in ("--cand-pool-mode", "--cand-pool-alpha"):
    if flag not in helptext:
        bad.append(f"eval_fair_puct's argparse has NO {flag}")

# (2) THEY REACH THE CANDIDATE CONFIG — and NOT the opponent's.
cs = {"fpu_reduction": None, "c_puct": None, "tau_p": None,
      "shared_c_puct": 1.5, "shared_tau_p": 5.0,
      "pool_mode": mode, "pool_alpha": alpha}
cand = E._build_champ_cfg(1.5, 5.0, "float", "visits", 15.0, None, cand_search=cs)
opp = E._cfg_from_dict({"c_puct": 1.5, "tau_p": 5.0, "leaf_quantize": "float",
                        "final_select": "visits", "value_norm": 15.0,
                        "fpu_reduction": None}, None)
if getattr(cand, "pool_mode", None) != mode or getattr(cand, "pool_alpha", None) != alpha:
    bad.append(f"the candidate config resolved pooling "
               f"({getattr(cand, 'pool_mode', None)!r}, "
               f"{getattr(cand, 'pool_alpha', None)!r}), not ({mode!r}, {alpha!r})")
if getattr(opp, "pool_mode", "mean") != "mean" or getattr(opp, "pool_alpha", None) is not None:
    bad.append(f"⛔⛔ the OPPONENT config resolved pooling "
               f"({getattr(opp, 'pool_mode', None)!r}, "
               f"{getattr(opp, 'pool_alpha', None)!r}) — the RULE LEAKED onto "
               "the opponent. There is no shared --pool-mode, so this is a pure "
               "wiring defect.")

# (3) IT REACHES THE RUST BACKEND THAT ACTUALLY PLAYS — read off the `pool`
#     GETTER, which returns numbers. ⛔ An AttributeError here is the STALE-WHEEL
#     signal: rust's Display prints 1.0 as "1", so a repr regex would be the
#     wrong instrument even if the getter did not exist.
from carcassonne_ai.rust_agent import search_config_rs, carc_rs_binary_sha
sc = search_config_rs(cand, 8)
got = getattr(sc, "pool", None)
if got is None:
    bad.append("⛔⛔ the installed carc_rs SearchConfigRs has NO `pool` getter — "
               "THIS BOX'S WHEEL PREDATES measurement/cvar_pool_prep. A bundle "
               "sync is NOT enough for this round: GT-M1 changes carc_core, so "
               "the wheel must be REBUILT (RUSTUP_TOOLCHAIN=1.96.0) and "
               "installed here.")
else:
    got = (str(dict(got).get("mode")),
           None if dict(got).get("alpha") is None else float(dict(got)["alpha"]))
    if got != (mode, alpha):
        bad.append(f"SearchConfigRs resolved pooling {got!r}, not "
                   f"{(mode, alpha)!r}")

# (4) ⭐⭐ THE RULE ACTUALLY RUNS AND COUNTS ITSELF. Two moves of a real CVaR
#     agent at a tiny budget: `pool_cvar_plies` must move. This is the layer
#     that catches a wheel whose getter exists but whose dispatch does not.
if not bad:
    import random
    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai.game_wrapper import Game
    random.seed(7)
    g = Game(enable_legal_moves_cache=True)
    b = g.get_init_board()
    ag = CF.build_fair_champion(g, cfg=cand, sims=24, k_dets=4, seed=7,
                                exact_max_k=2, backend="rust", rust_threads=1)
    if hasattr(ag, "start_game"):
        ag.start_game(b)
    for _ in range(3):
        a = int(ag.move(b))
        b, _ = g.get_next_state(b, a)
        if hasattr(ag, "advance"):
            ag.advance(a)
    st = getattr(ag, "_rs", None)
    st = st.stats() if st is not None else {}
    if int(st.get("pool_cvar_plies") or 0) <= 0:
        bad.append("⛔⛔ a live 3-ply CVaR agent reports pool_cvar_plies=0 — the "
                   "rule RESOLVED but the DISPATCH never ran. This box's wheel "
                   "is not the one this round was built against.")

# (5) the paired work-builder still yields the contiguous range this round's
#     band arithmetic depends on.
w = E._build_work(1000, 6, True)
if w != [(1000,0),(1000,1),(1001,0),(1001,1),(1002,0),(1002,1)]:
    bad.append("_build_work(seed_start, n, paired=True) changed shape: " + repr(w))

if bad:
    print("⛔⛔ THIS BOX CANNOT EXPRESS THE CELL: " + "; ".join(bad))
    sys.exit(1)
print(f"[probe] this box binds pool=({mode}, {alpha}) on the candidate ONLY "
      f"(opponent stays 'mean'), all the way into SearchConfigRs AND into a live "
      f"agent's own counters. At the cell's k_dets={k_dets} that is the worst "
      f"{max(1, math.ceil(alpha * k_dets))} of {k_dets} worlds.")
print(f"[probe] carc_rs binary sha (BOX-LOCAL, not cross-box comparable): "
      f"{carc_rs_binary_sha()}")
PYPROBE

# --- 2d. G-PROD: the frozen shape still IS production ---------------------- #
"$PY" - "$REPO/governance/PRODUCTION.yaml" "$K_DETS" "$SIMS_PER_DET" \
        "$TIEARB_B" "$TIEARB_J" "$TIEARB_MODE" "$TIEARB_SALT" "$TIEARB_EPS" \
  <<'PYPROD' || DIE "G-PROD FAILED — the frozen shape has drifted from production."
# ⚠️⚠️ PARSED AS YAML AT EXPLICIT ADDRESSES, NEVER GREPPED. PRODUCTION.yaml
# carries a `deploy_profiles.mobile` block with the SAME key names
# (k_dets/sims_per_det/tiearb) at DIFFERENT values, so a `^\s+k_dets:` regex
# matches whichever block comes first and would silently re-assert the frozen
# desktop shape against a mobile number.
import sys, yaml
p, kd, sims, b, j, mode, salt, eps = sys.argv[1:9]
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
        bad.append(f"PRODUCTION.yaml {addr}={got!r} but this round froze {want!r}")
if at(*CH, "fair_deploy", "tiearb", "phase_gate") is not None:
    bad.append("PRODUCTION.yaml has grown a fair_deploy.tiearb.phase_gate — this "
               "round froze the UNGATED arbiter ('all') on the strength of its "
               "absence; re-read the pair before launching")
# ⛔ AND: production must still pool by the MEAN. If PRODUCTION.yaml ever grows a
# pooling knob, this round's opponent is no longer the champion it claims.
if at(*CH, "fair_deploy", "pool_mode") is not None or \
   at(*CH, "agent_knobs", "pool_mode") is not None:
    bad.append("PRODUCTION.yaml has grown a pooling knob — the champion this "
               "round grades against is no longer the mean-pooled one it froze")
if bad:
    print("⛔⛔ " + "; ".join(bad)); sys.exit(1)
print("[G-PROD] the frozen budget/arbiter still match PRODUCTION.yaml at "
      "champion.fair_deploy, and production still pools by the MEAN")
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
    # ⛔⛔ WITHOUT --paired THE ROUND HAS NO PRIMARY (PG-D9) and it walks
    # 2*N_DECKS seeds — outside its own frozen band.
    --n "$n_games" --paired --seed-start "$seed_start"
    # ⚠️ `--out` is AMBIGUOUS in eval_fair_puct and argparse REFUSES it (PG-D7).
    --workers "$W_LAPTOP" --out-root "$OUT_ROOT" --out-subdir "$name"
    # ⚠️ WITHOUT THIS THE ROUND RUNS `walled` (PG-D8).
    --rules-profile "$RULES_PROFILE"
    # ⭐⭐ THE ARBITER, ON **BOTH** SEATS, AT THE FULL DEPLOYED SPEC.
    --cand-tiearb-enabled --cand-tiearb-b "$TIEARB_B" --cand-tiearb-j "$TIEARB_J"
    --cand-tiearb-mode "$TIEARB_MODE" --cand-tiearb-salt "$TIEARB_SALT"
    --cand-tiearb-eps "$TIEARB_EPS" --cand-tiearb-phase-gate "$TIEARB_PHASE_GATE"
    --opp-tiearb-enabled --opp-tiearb-b "$TIEARB_B" --opp-tiearb-j "$TIEARB_J"
    --opp-tiearb-mode "$TIEARB_MODE" --opp-tiearb-salt "$TIEARB_SALT"
    --opp-tiearb-eps "$TIEARB_EPS" --opp-tiearb-phase-gate "$TIEARB_PHASE_GATE"
    # ⛔⛔ THE SINGLE VARIABLE — and note there is NO --cand-c-puct, NO
    # --cand-tau-p, NO --cand-fpu-reduction and NO bare --c-puct / --tau-p
    # anywhere in this script, by construction.
    --cand-pool-mode "$POOL_MODE" --cand-pool-alpha "$ALPHA"
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
    STAMP "[dry-run] $name alpha=$ALPHA seeds=${seed_start}.. n=$n_games -> $out"
    printf '    %q ' "$PY" "${args[@]}"; echo
    return 0
  fi
  STAMP "$name pool=$POOL_MODE alpha=$ALPHA seeds=${seed_start}.. n=$n_games W=$W_LAPTOP -> $out"
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
    # ⛔⛔ ADJUDICATE THE SMOKE FROM ITS OWN EMITTED MANIFEST **AND SUMMARY**.
    # Nonzero exit on an empty or manifest-less cell (the R1 defect class) AND
    # on a rule that resolved but never REACHED (this round's own G-REACH). A
    # smoke that "ran" and produced nothing, or that produced a candidate
    # indistinguishable from the champion, must not read as a green light.
    "$PY" "$HERE/adjudicate_cvar_smoke.py" --root "$OUT_ROOT" --cell "$SMOKE_NAME" \
        --alpha "$ALPHA" --out "$HERE/SMOKE_${CELL}.json" \
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
{"cell": "$CELL", "kind": "real", "pool_mode": "$POOL_MODE", "pool_alpha": $ALPHA,
 "band": $BAND, "pid": $$, "host": "$(hostname)",
 "started_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
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
