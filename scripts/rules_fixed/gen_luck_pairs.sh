#!/usr/bin/env bash
# F9 Phase C §1 residue — the SEAT-SWAP PAIRED LUCK ARCHIVE under `fixed_v1`.
#
#   measurement/f9_phase_c/PHASE_C_DESCRIPTIVES.md §1 prices sigma_game and the
#   seat-0 advantage from the champion self-play corpora, and reports the paired
#   half — **luck_share_icc**, **sigma_pair**, **n_games_paired_test** — as NOT
#   DERIVABLE, because a self-play corpus has ONE seating per deck. Its own
#   closing line names the fix: "generate a seat-swap paired eval archive under
#   this rules profile (the seedNNN_a0.json / _a1.json shape
#   luck_floor.load_pairs reads) and add its directory to luck_floor.NEAR_EQUAL,
#   then re-run scripts/human_anchor/luck_floor.py." This script generates it.
#
# ⚠️ THIS IS DESCRIPTIVE. Throwaway seeds, NO band claim, NO elo verdict, NO
#    experiments/results.csv row (--no-results-csv), NO governance/BAND_REGISTRY
#    row, governance/PRODUCTION.yaml untouched. It measures how much of the
#    score margin the DECK fixes; nothing here is a strength contrast, and the
#    two sides are the SAME agent by construction so there is nothing to win.
#
# WHY BOTH SIDES ARE THE CHAMPION.
#   luck_floor's ICC estimator wants a NEAR-EQUAL pair: a strong-vs-weak archive
#   inflates the within-pair (skill) variance and *understates* the deck-luck
#   share (luck_floor.py "Method + caveats"). Champion-vs-champion is the
#   near-equal limit, and it is also the agent whose luck floor the E4/human
#   program actually needs. The two seatings are NOT degenerate: the harness
#   seeds the opponent side at `seed + 1`, so the two sides never share a
#   determinization stream and the a0/a1 games of one deck are two genuinely
#   independent seatings of that deck.
#
# THE HARNESS IS REUSED, NOT REWRITTEN.
#   scripts/classical_search/eval_fair_puct.py --opponent fair-champion is the
#   modern deck-paired head-to-head (the caps/curve re-sweep's sibling harness).
#   It already emits exactly `seed{seed:012d}_a{a_seat}.json` with
#   seed/a_seat/score_p0/score_p1/diff/drew — the shape luck_floor.load_pairs
#   reads — and it already auto-injects the frozen curve125 champion leaf on
#   BOTH sides of a symmetric head-to-head. The ONLY adapter needed downstream
#   is luck_floor's `won_by_a` spelling fallback (this harness writes
#   `won_by_champ`), which is in scripts/human_anchor/luck_floor.py:_won_by_a.
#
# RULES PROFILE. Both sides run `fixed_v1` + CARCASSONNE_FIX_R9=1. R9 is a DATA
#   flag latched at IMPORT (base_deck derives it; the Rust registry is a
#   OnceLock), so it MUST be exported here, before python starts —
#   `--rules-profile` cannot apply it, it can only stamp whether we did. Every
#   manifest carries rules_profile.name == fixed_v1 AND r9_env_ok == true; an
#   archive whose manifest says otherwise is void, whatever this script printed.
#
# COST. Champion play at the production budget k8x1376 = 11008 with the exact
#   K<=2 marginalized tail on BOTH sides. See the ETA printed at launch; the
#   authoritative figure is the measured mean over COMPLETED per-game jsons, not
#   the first few (memory `feedback_eta_before_launch`, order-statistic trap).
#
# ⚠️ CENSUS FIRST, AND DO NOT RUN THIS BESIDE A LIVE EVAL (memory
#    `feedback_no_agent_compute_beside_eval`).
#
# Usage:
#   scripts/rules_fixed/gen_luck_pairs.sh [--decks 200] [--workers 24]
#          [--seed-start 109500000000] [--out DIR] [--backend rust]
#          [--foreground] [--smoke]
# Then (local view of the share):
#   scripts/human_anchor/luck_floor.py --only-extra \
#       --extra-near-equal /mnt/c/carc-shared/f9_luck_pairs_fixed_v1 \
#       -o measurement/f9_phase_c/LUCK_FLOOR_fixed_v1.md
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"

# The interpreter. A git WORKTREE has no `.venv` of its own (the venv is editable-
# installed against the main tree), so a worktree build sets CARC_PYTHON + PYTHONPATH
# rather than pretending one exists — memory `feedback-worktree-isolation-live-tree`.
PY="${CARC_PYTHON:-$REPO/.venv/bin/python}"
if [[ ! -x "$PY" ]]; then
  echo "no interpreter at $PY — set CARC_PYTHON (and PYTHONPATH, in a worktree)" >&2
  exit 2
fi

DECKS=200
WORKERS=24            # laptop gen W* (CLUSTER_OPS). Override per box.
# THROWAWAY seeds from the F9 reserve (docs/F9_BUILD_SPEC_20260802.md §5.3,
# 1.00e11-1.10e11), deliberately CLEAR of the 1.09e11+0..399 Phase-B/C corpus
# seeds. No BAND_REGISTRY row: a descriptive archive claims no band (spec §3,
# Gate C).
SEED_START=109500000000
OUT=""
BACKEND=rust
KDETS=8
SIMS=1376
EXACT_K=2
FOREGROUND=0
SMOKE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --decks)       DECKS="$2"; shift 2 ;;
    --workers)     WORKERS="$2"; shift 2 ;;
    --seed-start)  SEED_START="$2"; shift 2 ;;
    --out)         OUT="$2"; shift 2 ;;
    --backend)     BACKEND="$2"; shift 2 ;;
    --foreground)  FOREGROUND=1; shift ;;
    --smoke)       SMOKE=1; FOREGROUND=1; DECKS=4; WORKERS=4; shift ;;
    -h|--help)     sed -n '2,70p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[[ -z "$OUT" ]] && OUT="/mnt/c/carc-shared/f9_luck_pairs_fixed_v1"
if [[ "$SMOKE" == "1" && "$OUT" == "/mnt/c/carc-shared/f9_luck_pairs_fixed_v1" ]]; then
  OUT="/tmp/f9_luck_pairs_smoke"
fi
GAMES=$((DECKS * 2))          # --paired: decks x 2 seatings

# The curve125 champion leaf env — the archive must be played by the CHAMPION's
# leaf, not the scripts' curve100 default. (The head-to-head path also injects
# curve125 in-process on both sides and hard-fails on a mismatch; this export is
# the belt to that braces, and pins the flat/Cython leaf engine + BLAS threads.)
# shellcheck disable=SC1091
source "$REPO/scripts/distill_flywheel/champ_env.sh"

# ⚠️ R9 must be in the environment BEFORE the interpreter starts (import-latched).
export CARCASSONNE_FIX_R9=1

echo "F9 Phase C §1 — seat-swap paired LUCK archive under fixed_v1"
echo "  agents      : PRODUCTION CHAMPION both sides (--opponent fair-champion, curve125 both)"
echo "  budget      : k${KDETS}x${SIMS} = $((KDETS*SIMS))  exact-K<=${EXACT_K}  backend=${BACKEND}"
echo "  rules       : fixed_v1 + CARCASSONNE_FIX_R9=${CARCASSONNE_FIX_R9}  (manifest must stamp r9_env_ok)"
echo "  pairs       : ${DECKS} decks x 2 seatings = ${GAMES} games"
echo "  seeds       : ${SEED_START}..$((SEED_START+DECKS-1))   workers=${WORKERS}"
echo "  out         : $OUT"
echo "  descriptive : no results.csv row, no band, no PRODUCTION.yaml"
if [[ "$SMOKE" == "1" ]]; then echo "  *** SMOKE ***"; fi
echo

CMD=( nice -n 19 "$PY" -u
      "$REPO/scripts/classical_search/eval_fair_puct.py"
      --info fair --opponent fair-champion --backend "$BACKEND"
      --k-dets "$KDETS" --sims "$SIMS" --exact-k "$EXACT_K"
      --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits
      --n "$GAMES" --paired --seed-start "$SEED_START"
      --workers "$WORKERS"
      --rules-profile fixed_v1
      --out-root "$(dirname "$OUT")" --out-subdir "$(basename "$OUT")"
      --shared-claim --no-results-csv )

if [[ "$FOREGROUND" == "1" ]]; then
  mkdir -p "$OUT"
  "${CMD[@]}" 2>&1 | tee "$OUT/gen_luck_pairs.log"
else
  # ⚠️ DETACHED (CLAUDE.md): Mac-sleep SIGHUP and WSL VM teardown both kill
  # tty-attached jobs, and run_in_background alone is not enough.
  mkdir -p "$OUT"
  nohup setsid "${CMD[@]}" > "$OUT/gen_luck_pairs.log" 2>&1 < /dev/null &
  disown || true
  echo "launched detached; log: $OUT/gen_luck_pairs.log"
  echo "when it finishes (LOCAL share view /mnt/c/carc-shared):"
  echo "  scripts/human_anchor/luck_floor.py --only-extra \\"
  echo "      --extra-near-equal /mnt/c/carc-shared/$(basename "$OUT") \\"
  echo "      -o measurement/f9_phase_c/LUCK_FLOOR_fixed_v1.md"
fi
