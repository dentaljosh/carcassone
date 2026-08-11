#!/usr/bin/env bash
# F9 / D1 — the five validation legs behind measurement/jcz_oracle_20260803/.
#
# Legs are chosen so each pair isolates ONE variable:
#   A vs B  — R9 off/on, everything else held (the R9 flip, on the real archive)
#   C vs D  — R9 off/on under fixed rules (the R9 flip, on the clean profile)
#   D vs E  — walled vs fixed_v1 at the SAME policy (the rules-profile effect)
#   A, F    — the actual recorded corpora (champion play; E4 human-vs-champion)
#
# ⚠️ `--policy record` is only sound for `walled`: a recorded (deck_seed, actions)
# pair decodes to a DIFFERENT game under fixed_v1 (retail start + redraw + the
# recentred grid all move the action space). The fixed legs therefore keep the
# DECK and generate their own legal trajectory (`--policy seeded`).
set -euo pipefail
cd "$(dirname "$0")/../.."

PY=${PY:-/home/doctor/projects/carcassone/.venv/bin/python}
OUT=measurement/jcz_oracle_20260803
CHAMP=measurement/champ_action_logs/champ_games.jsonl
E4=measurement/e4_games
N=${N:-20}
mkdir -p "$OUT"

run() {  # run <name> <profile> <policy> on|off <games...>
  local name=$1 profile=$2 policy=$3 r9=$4; shift 4
  local args=()
  for g in "$@"; do args+=(--games "$g"); done
  [ "$r9" = on ] && args+=(--r9)
  echo "=== leg $name : profile=$profile policy=$policy r9=$r9 ==="
  nice -n 19 "$PY" scripts/jcz_oracle/replay_diff.py "${args[@]}" \
      --limit "$N" --profile "$profile" --policy "$policy" \
      --out "$OUT/$name.json" 2>&1 | tail -25
}

run A_walled_record_r9off    walled   record off "$CHAMP"
run B_walled_record_r9on     walled   record on  "$CHAMP"
run C_fixed_seeded_r9off     fixed_v1 seeded off "$CHAMP"
run D_fixed_seeded_r9on      fixed_v1 seeded on  "$CHAMP"
run E_walled_seeded_r9on     walled   seeded on  "$CHAMP"
run F_e4_walled_record_r9on  walled   record on  "$E4"
run G_e4_walled_record_r9off walled   record off "$E4"
echo "ALL LEGS DONE"
