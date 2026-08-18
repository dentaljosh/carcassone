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
#   base       135000000000 .. 135000000849  (850 games) RETAINED AS VALID INPUT
#   released   136000000000                  RELEASED UNUSED — never generated
#   EXTENSION  137000000000 ..               SPLIT BY STRATUM (FLOORS.json)
#   top-up     138000000000 .. 138000000499  RESERVED, not licensed
#
# ─────────────────────────────────────────────────────────────────────────────
# R4 BAND ARITHMETIC — three ways, and only two of them generate (DESIGN R4-6)
# ─────────────────────────────────────────────────────────────────────────────
#   * **135e9 is RETAINED as INPUT and this script REFUSES to generate into it.**
#     Its 850 games are reusable (`PREREG_FAILURE` §3): the R3.3 run stopped
#     PRE-SCORING, so no `arb`, `ora`, `Δ`, CI or per-position value was ever
#     computed for them. Re-generating there would duplicate seeds and fail
#     `G-BAND`'s `n_duplicate_seeds == 0` on a healthy run.
#   * **137e9 is the EXTENSION, and it is SPLIT BY STRATUM.** `+games` is a SUM
#     OF TWO DISJOINT REQUIREMENTS, and `strata_root_overlap == 0` is a gate
#     conjunct — so mining both strata from one undivided range would FAIL
#     `G-DISJOINT` §2b(v) ON A PERFECTLY HEALTHY CORPUS. The two sub-ranges are
#     committed in `RUN/FLOORS.json` and read from there; this script never
#     invents one. Two invocations, two `--out` directories.
#   * **138e9 is the top-up**, its own invocation, its own directory, its own
#     `verify-champgames` file.
#
# A game seed mined into the wrong stratum is a `G-DISJOINT` FAILURE, not a
# bookkeeping slip.
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
#   ./run_gen.sh {local|laptop-side} --extension s1   # 137e9, the S1 sub-range
#   ./run_gen.sh {local|laptop-side} --extension s2   # 137e9, the S2 sub-range
#   ./run_gen.sh {local|laptop-side} --smoke          # the §7.2 timed GEN smoke
#   ./run_gen.sh {local|laptop-side} --topup N        # 138e9, N <= 500
#
# (there is no base-band mode: 135e9 is RETAINED INPUT, never re-generated)
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

USAGE="usage: $0 {local|laptop-side} {--extension s1|--extension s2|--smoke|--topup N} [--dry-run]"
BOX="${1:-}"
MODE=""
TOPUP_GAMES=0
EXT_STRATUM=""
#: `--dry-run` resolves EVERYTHING — conf, floors, band, sub-range, worker count,
#: the full argv — prints it, and EXITS WITHOUT GENERATING. Every automated
#: caller (tests, lint, the acceptance harness) uses it. It exists because this
#: script's whole job is to start an expensive irreversible job, and a test that
#: reaches the `exec` starts 850 real games: on 2026-08-18 a unit test that
#: passed `--topup 201` did exactly that, at W48, into the reserved band.
DRY_RUN="${WIDENING_GEN_DRY_RUN:-0}"
shift || true
while [ $# -gt 0 ]; do
  case "$1" in
    --smoke)     MODE="smoke" ;;
    --extension) MODE="extension"; EXT_STRATUM="${2:-}"; shift ;;
    --topup)     MODE="topup"; TOPUP_GAMES="${2:-0}"; shift ;;
    --dry-run)   DRY_RUN=1 ;;
    --base|--full)
      echo "[gen] REFUSING: band 135e9 is RETAINED AS VALID INPUT (850 games," \
           "PREREG_FAILURE §3) and is NEVER re-generated. Generating there" \
           "would duplicate seeds and fail G-BAND's n_duplicate_seeds == 0 on" \
           "a healthy run. Use --extension s1|s2." >&2; exit 2 ;;
    *) echo "$USAGE" >&2; exit 2 ;;
  esac
  shift
done
[ -n "$MODE" ] || { echo "$USAGE" >&2; exit 2; }

case "$BOX" in
  local)       W="$W_GEN_LOCAL";  REPO="$REPO_LOCAL";  SHARE="$SHARE_LOCAL" ;;
  laptop-side) W="$W_GEN_LAPTOP"; REPO="$REPO_REMOTE"; SHARE="$SHARE_REMOTE" ;;
  *) echo "usage: $0 {local|laptop-side} [--smoke | --topup N]" >&2; exit 2 ;;
esac

# --- the bands, and the knobs matched VERBATIM to CORPUS_MANIFEST.json -------- #
BASE_SEED_START=135000000000       # RETAINED INPUT — never generated here
EXTENSION_SEED_START=137000000000  # split by stratum; sub-ranges from FLOORS.json
TOPUP_SEED_START=138000000000
TOPUP_MAX=500
SMOKE_GAMES=10
COMMITTED_WORKER_SECS_PER_GAME=372.0     # R4-5: 297.6 measured x 1.25 margin
                                         # (R3 carried 990 inherited; the fresh
                                         # same-config GEN smoke measured 297.6,
                                         # so the one-sided HALT now trips above
                                         # 465.0 = a REAL trigger, not a formality)
HALT_RATIO=1.25                          # §7.3 — ONE-SIDED (costlier only)

# `--backend rust`: DESIGN §3 names it in the config of record, and W10.1's own
# `W_GEN_LOCAL` comment justifies W48 as "gen_fair_distill --backend rust". The
# abbreviated W10.2 exec block omits the flag; running python-backed at W48
# would be neither the committed config nor the benched count, so the flag is
# carried here EXPLICITLY and this line is the audit trail for that reading.
BACKEND=rust

RUN_DIR="$REPO/measurement/$RUN_ID/shared_run"
FLOORS="$RUN_DIR/FLOORS.json"

# Each band/stratum generates into its OWN directory, so each gets its OWN
# `verify-champgames` file and G-BAND's N-file form holds end-to-end. Merging
# them into one --out would put seeds from two committed ranges in front of one
# verify — the widened-band failure R3's defect B1 closed, generalised.
OUT_EXT_S1="$SHARE/$RUN_ID/gen_ext_s1"
OUT_EXT_S2="$SHARE/$RUN_ID/gen_ext_s2"
OUT_TOPUP="$SHARE/$RUN_ID/gen_topup"

# `FLOORS.json` is the ONLY source of the extension sub-ranges. R4-8b makes it
# predate the band claim precisely so this script cannot invent one.
ext_field() {
  [ -f "$FLOORS" ] || { echo "[gen] FATAL: $FLOORS missing — R4-8b writes it" \
    "BEFORE the extension band is claimed and before one game is generated." \
    "The sub-ranges live there and are never invented here." >&2; exit 2; }
  "$REPO/.venv/bin/python" - "$FLOORS" "$1" <<'PYEOF'
import json, sys
d = json.loads(open(sys.argv[1]).read()); k = sys.argv[2]
sr = d.get("sub_ranges") or {}
if k in ("s1_lo", "s1_hi", "s2_lo", "s2_hi"):
    tag, which = k.split("_")
    rng = sr.get(tag)
    print("" if not rng else rng[0 if which == "lo" else 1])
else:
    print(d.get(k, ""))
PYEOF
}

case "$MODE" in
  extension)
    case "$EXT_STRATUM" in
      s1) THIS_OUT="$OUT_EXT_S1"; G="$(ext_field games_extension_s1)"
          THIS_SEED="$(ext_field s1_lo)" ;;
      s2) THIS_OUT="$OUT_EXT_S2"; G="$(ext_field games_extension_s2)"
          THIS_SEED="$(ext_field s2_lo)" ;;
      *) echo "$USAGE" >&2; exit 2 ;;
    esac
    if [ -z "$THIS_SEED" ] || [ -z "$G" ] || [ "$G" -eq 0 ] 2>/dev/null; then
      echo "[gen] REFUSING: FLOORS.json commits NO $EXT_STRATUM extension" \
           "sub-range (games_extension_$EXT_STRATUM = ${G:-0}). On the S1 ONLY" \
           "row there is no S2 sub-range and NONE MAY BE GENERATED." >&2
      exit 2
    fi
    THIS_GAMES="$G"
    ;;
  topup)
    # G-BAND's TWO-FILE FORM: the top-up is a SEPARATE INVOCATION into a
    # SEPARATE --out, so W6 phase 1 collects two champ-games files and verifies
    # each against ITS OWN committed range. One invocation over a widened band
    # is FORBIDDEN: it would report `n_out_of_band == 0` for a seed lying in
    # neither range, which is exactly the failure R3's defect B1 closed.
    [ "$TOPUP_GAMES" -ge 1 ] && [ "$TOPUP_GAMES" -le "$TOPUP_MAX" ] || {
      echo "[gen] FATAL: --topup N must be 1..$TOPUP_MAX (the §3 blind clause is" \
           "138e9 +0..+499); got '$TOPUP_GAMES'" >&2; exit 2; }
    THIS_OUT="$OUT_TOPUP"; THIS_SEED="$TOPUP_SEED_START"; THIS_GAMES="$TOPUP_GAMES"
    ;;
  smoke)
    # SAME BAND as the run it prices — the EXTENSION S1 sub-range's FIRST TEN,
    # RETAINED. No seed outside a committed range is ever created, so G-BAND is
    # untouched and the extension run simply resumes into the same --out under
    # --shared-claim (those ten are already done).
    THIS_OUT="$OUT_EXT_S1"; THIS_SEED="$(ext_field s1_lo)"
    THIS_GAMES="$SMOKE_GAMES"
    [ -n "$THIS_SEED" ] || { echo "[gen] FATAL: no S1 extension sub-range in" \
      "$FLOORS" >&2; exit 2; }
    ;;
  *) echo "$USAGE" >&2; exit 2 ;;
esac

echo "[gen] mode=$MODE box=$BOX W=$W backend=$BACKEND out=$THIS_OUT" \
     "games=$THIS_GAMES seed_start=$THIS_SEED"
echo "[gen] CORPUS SUBSTRATE ONLY — 0 strength games, no results.csv row, no band promotion."

GEN_ARGS_PREVIEW="--games $THIS_GAMES --k-dets 4 --sims 688 --exact-endgame \
--exact-max-k 2 --rules-profile walled --backend $BACKEND --workers $W \
--seed-start $THIS_SEED --log-actions --actions-only --out $THIS_OUT \
--shared-claim"
if [ "$DRY_RUN" != "0" ]; then
  # ⚠️ EXIT BEFORE ANYTHING IRREVERSIBLE. Nothing is created — not the output
  # directory, not a claim, not a game. Everything above this line is pure
  # resolution (conf, floors, band, sub-range, worker count) and is exactly what
  # a real run would use, so a dry run audits the resolution without buying it.
  echo "[gen] DRY RUN — resolved command (NOTHING GENERATED, no directory created):"
  echo "[gen]   nice -n $NICE $REPO/.venv/bin/python -u \\"
  echo "[gen]     $REPO/scripts/distill_flywheel/gen_fair_distill.py $GEN_ARGS_PREVIEW"
  exit 0
fi

mkdir -p "$THIS_OUT"
# shellcheck disable=SC1091
. "$REPO/scripts/distill_flywheel/champ_env.sh"

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
