#!/usr/bin/env bash
# run_gen.sh — W10. PHASE 0: fresh champion self-play games (CORPUS SUBSTRATE ONLY).
#
# The W6 driver CONSUMES `$SHARE_RUN/gen`; this is what PRODUCES it. A
# parameterised copy of `measurement/tiearb2_20260816/run_gen.sh`: same
# generator, same production knobs, ONLY THE DECK-SEED BAND DIFFERS — which is
# what makes the widening corpus root-disjoint from every banked corpus BY
# CONSTRUCTION (DESIGN §3), rather than by assertion.
#
#   spent 2026-08-12 corpus : 28000000000 ..                 (consumed)
#   tiearb2_20260816        : 28100000000 .. 28100000849     (consumed)
#   THIS RUN  (base)        : 135000000000 .. 135000000849   (850 games)
#   THIS RUN  (top-up)      : 136000000000 .. 136000000199   (<=200, RESERVED)
#
# ─────────────────────────────────────────────────────────────────────────────
# W10.4 — WHAT THIS SCRIPT MUST NOT DO (verbatim from DESIGN §8)
# ─────────────────────────────────────────────────────────────────────────────
#   * NO SELF-LAUNCH. It never starts itself; the operator pastes a command.
#   * NO STRENGTH CLAIM. These are 0 strength games. This is not an evaluation.
#   * NO `experiments/results.csv` ROW. Not now, not later, on any outcome.
#   * NO BAND PROMOTION. The games are CORPUS SUBSTRATE, nothing more.
#   * It does not build positions, does not run a census, and does not touch
#     `shared_run/`.
#
#   ⚠️ ONE SANCTIONED EXCEPTION to the last clause, named rather than smuggled:
#   `--smoke` writes exactly ONE file under `shared_run/` —
#   `shared_run/corpus/GEN_SMOKE.json` — because W10.3 and §7.2 mandate that
#   exact address and §10 lists it among the manifests the run MUST write. It
#   writes nothing else there, ever. (A copy also lands beside the games on the
#   share so a laptop-side smoke is retrievable from the local box.)
#
# ─────────────────────────────────────────────────────────────────────────────
# USAGE — this script NEVER self-launches; paste one of these.
# ─────────────────────────────────────────────────────────────────────────────
#   ./run_gen.sh {local|laptop-side}            # the 850-game base band
#   ./run_gen.sh {local|laptop-side} --smoke    # the §7.2 timed 10-game GEN smoke
#   ./run_gen.sh {local|laptop-side} --topup N  # the reserved 136e9 range, N<=200
#
# BOTH BOXES run the SAME command against the SAME `--out` on the share with
# `--shared-claim` O_EXCL work-stealing, so a slow box simply claims fewer games.
#
# DETACH (house rule: anything > ~1 min; Mac-sleep SIGHUP and WSL VM teardown
# both kill tty-attached jobs, and the harness's own backgrounding is NOT
# enough — the python child must be explicitly detached):
#
#   setsid nohup measurement/tiearb_widening_20260817/run_gen.sh local \
#     > /mnt/c/carc-shared/tiearb_widening_20260817/gen.local.log 2>&1 \
#     < /dev/null & disown
#
# ⚠️ THE rc=124 TRAP. A detached launch issued over ssh under `timeout` returns
# rc=124 AFTER the job has already started, so:
#
#         rc=124 MEANS LAUNCHED. NEVER RETRY IT.
#
# A retry stacks a SECOND Pool on the same box; both then contend for the same
# claims and the box runs at half speed with twice the memory. Verify with
# `pgrep -fa gen_fair_distill` on that box, never by re-issuing the command.
#
# ⚠️ SMOKE BEFORE THE FULL RUN, ON AN IDLE BOX. A timing bench is an EXCLUSIVE
# TENANT (`feedback_no_agent_compute_beside_eval`): a smoke sharing the box with
# anything else measures contention, not cost.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

# W10.1: the launcher DIES without WORKERS.conf rather than inventing a count.
CONF="$HERE/WORKERS.conf"
[ -f "$CONF" ] || { echo "[gen] FATAL: $CONF missing — W10.1 defines it and no" \
                         "launcher may hard-code a worker count." >&2; exit 2; }
# shellcheck disable=SC1090
. "$CONF"
for v in W_GEN_LOCAL W_GEN_LAPTOP NICE SHARE_LOCAL SHARE_REMOTE \
         REPO_LOCAL REPO_REMOTE RUN_ID; do
  [ -n "${!v:-}" ] || { echo "[gen] FATAL: $CONF does not set $v" >&2; exit 2; }
done

BOX="${1:-}"
MODE="full"
TOPUP_GAMES=0
shift || true
while [ $# -gt 0 ]; do
  case "$1" in
    --smoke) MODE="smoke" ;;
    --topup) MODE="topup"; TOPUP_GAMES="${2:-200}"; shift ;;
    *) echo "usage: $0 {local|laptop-side} [--smoke | --topup N]" >&2; exit 2 ;;
  esac
  shift
done

case "$BOX" in
  local)       W="$W_GEN_LOCAL";  REPO="$REPO_LOCAL";  SHARE="$SHARE_LOCAL" ;;
  laptop-side) W="$W_GEN_LAPTOP"; REPO="$REPO_REMOTE"; SHARE="$SHARE_REMOTE" ;;
  *) echo "usage: $0 {local|laptop-side} [--smoke | --topup N]" >&2; exit 2 ;;
esac

# --- the band, and the knobs matched VERBATIM to CORPUS_MANIFEST.json --------- #
SEED_START=135000000000
GAMES=850
TOPUP_SEED_START=136000000000
TOPUP_MAX=200
SMOKE_GAMES=10
COMMITTED_WORKER_SECS_PER_GAME=990.0     # DESIGN §7 currency A
HALT_RATIO=1.25                          # §7.3 — ONE-SIDED (costlier only)

# `--backend rust`: DESIGN §3 names it in the config of record, and W10.1's own
# `W_GEN_LOCAL` comment justifies W48 as "gen_fair_distill --backend rust". The
# abbreviated W10.2 exec block omits the flag; running python-backed at W48
# would be neither the committed config nor the benched count, so the flag is
# carried here EXPLICITLY and this line is the audit trail for that reading.
BACKEND=rust

OUT="$SHARE/$RUN_ID/gen"                 # exactly what W6 phase 1 collects from
OUT_TOPUP="$SHARE/$RUN_ID/gen_topup"     # SEPARATE dir — see the note below
RUN_DIR="$REPO/measurement/$RUN_ID/shared_run"

case "$MODE" in
  topup)
    # G-BAND's TWO-FILE FORM: the top-up is a SEPARATE INVOCATION into a
    # SEPARATE --out, so W6 phase 1 collects two champ-games files and verifies
    # each against ITS OWN committed range. One invocation over a widened band
    # is FORBIDDEN: it would report `n_out_of_band == 0` for a seed lying in
    # neither range, which is exactly the failure R3's defect B1 closed.
    [ "$TOPUP_GAMES" -ge 1 ] && [ "$TOPUP_GAMES" -le "$TOPUP_MAX" ] || {
      echo "[gen] FATAL: --topup N must be 1..$TOPUP_MAX (the §3 blind clause is" \
           "pre-licensed at <=200 games); got '$TOPUP_GAMES'" >&2; exit 2; }
    THIS_OUT="$OUT_TOPUP"; THIS_SEED="$TOPUP_SEED_START"; THIS_GAMES="$TOPUP_GAMES"
    ;;
  smoke)
    # SAME BAND, the band's FIRST TEN, RETAINED. No seed outside a committed
    # range is ever created, so G-BAND is untouched and the full run simply
    # resumes into the same --out under --shared-claim (the 10 are already done).
    THIS_OUT="$OUT"; THIS_SEED="$SEED_START"; THIS_GAMES="$SMOKE_GAMES"
    ;;
  *)
    THIS_OUT="$OUT"; THIS_SEED="$SEED_START"; THIS_GAMES="$GAMES"
    ;;
esac

mkdir -p "$THIS_OUT"
# shellcheck disable=SC1091
. "$REPO/scripts/distill_flywheel/champ_env.sh"

echo "[gen] mode=$MODE box=$BOX W=$W backend=$BACKEND out=$THIS_OUT" \
     "games=$THIS_GAMES seed_start=$THIS_SEED"
echo "[gen] CORPUS SUBSTRATE ONLY — 0 strength games, no results.csv row, no band promotion."

GEN_ARGS=(
  --games "$THIS_GAMES"
  --k-dets 4 --sims 688
  --exact-endgame --exact-max-k 2
  --rules-profile walled
  --backend "$BACKEND"
  --workers "$W"
  --seed-start "$THIS_SEED"
  --log-actions --actions-only
  --out "$THIS_OUT"
  --shared-claim
)

if [ "$MODE" != "smoke" ]; then
  # `exec`: the tiearb2 precedent — the python process REPLACES the shell, so a
  # `pkill -f gen_fair_distill` reaches the real worker parent.
  exec nice -n "$NICE" "$REPO/.venv/bin/python" -u \
    "$REPO/scripts/distill_flywheel/gen_fair_distill.py" "${GEN_ARGS[@]}"
fi

# ─────────────────────────────────────────────────────────────────────────────
# W10.3 — the §7.2 timed GEN smoke. NOT exec'd: we must time it and emit.
# ─────────────────────────────────────────────────────────────────────────────
# `--actions-only` makes `actions/seed_<seed:012d>.json` the resume/claim key, so
# counting THOSE files over the smoke's own ten seeds is the realized-game count
# (`--shared-claim` may legitimately skip a seed another box already took).
count_done() {
  local n=0 s
  for ((s = 0; s < SMOKE_GAMES; s++)); do
    [ -f "$THIS_OUT/actions/$(printf 'seed_%012d.json' $((THIS_SEED + s)))" ] \
      && n=$((n + 1))
  done
  echo "$n"
}

BEFORE="$(count_done)"
T0=$(date +%s)
nice -n "$NICE" "$REPO/.venv/bin/python" -u \
  "$REPO/scripts/distill_flywheel/gen_fair_distill.py" "${GEN_ARGS[@]}"
T1=$(date +%s)
AFTER="$(count_done)"

WALL=$((T1 - T0))
NEW=$((AFTER - BEFORE))
echo "[gen-smoke] wall=${WALL}s games_new=$NEW games_present=$AFTER W=$W"

GEN_SMOKE="$RUN_DIR/corpus/GEN_SMOKE.json"
mkdir -p "$(dirname "$GEN_SMOKE")"
"$REPO/.venv/bin/python" - "$GEN_SMOKE" "$WALL" "$NEW" "$W" "$BOX" \
  "$COMMITTED_WORKER_SECS_PER_GAME" "$HALT_RATIO" "$THIS_OUT" <<'PYEOF'
import json, sys
out, wall, n, w, box, committed, halt_ratio, gen_dir = sys.argv[1:9]
wall, n, w = int(wall), int(n), int(w)
committed, halt_ratio = float(committed), float(halt_ratio)
# worker-s per GAME. ⚠️ UNITS: the judge legs are worker-s per PLAYOUT. The two
# are NEVER compared and never share a key name.
wspg = (wall * w / n) if n else None
ratio = (wspg / committed) if (wspg and committed) else None
rep = {
    "worker_secs_per_game": wspg,
    "n_games": n,
    "workers": w,
    "box": box,
    "wall_secs": wall,
    "committed": committed,
    "ratio": ratio,
    # ONE-SIDED: halt only when the realized cost is >25% COSTLIER. Cheaper is
    # recorded, never a halt (the 990 line is already ~2.25x conservative).
    "halt_fired": bool(ratio is not None and ratio > halt_ratio),
    "gen_dir": gen_dir,
    "units": "worker-seconds per GAME (the judge legs are per PLAYOUT — never "
             "compared, never the same key)",
    "note": "DESIGN §7.2 generation c-remeasure. The smoke's games are the "
            "band's first ten and are RETAINED, so no seed outside a committed "
            "range is ever created and G-BAND is untouched.",
}
if not n:
    rep["failed_smoke"] = True
    rep["reason"] = ("no game completed in this invocation — every one of the "
                     "band's first ten was already claimed/done. Clear them or "
                     "run the smoke on a fresh band prefix; a null cost is a "
                     "FAILED SMOKE, not a cheap leg and not a HALT.")
with open(out, "w") as fh:
    json.dump(rep, fh, indent=2, sort_keys=True)
print(f"[gen-smoke] worker_secs_per_game={wspg} ratio={ratio} "
      f"halt_fired={rep['halt_fired']} -> {out}")
if rep["halt_fired"]:
    print("\n" + "=" * 70 +
          "\n[gen-smoke] ***** HALT — RE-PRICE REQUIRED *****"
          "\n[gen-smoke] realized generation cost is >25% COSTLIER than the "
          "committed 990 worker-s/game."
          "\n[gen-smoke] A re-priced run above 1,500 worker-h requires FRESH "
          "OWNER AUTHORIZATION.\n" + "=" * 70, file=sys.stderr)
    raise SystemExit(1)
PYEOF
RC=$?

# a copy beside the games, so a laptop-side smoke is retrievable from the local
# box (the laptop's repo checkout is not synced back)
cp -f "$GEN_SMOKE" "$THIS_OUT/../GEN_SMOKE.$BOX.json" 2>/dev/null || true

echo "[gen-smoke] consumed by: scripts/tiletie/c_remeasure.py --gen-smoke $GEN_SMOKE"
exit "$RC"
