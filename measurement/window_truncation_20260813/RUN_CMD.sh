#!/usr/bin/env bash
# Full WINDOW-TRUNCATION CENSUS — the two legs of DESIGN.md §8, as one dispatchable job.
#
#   bash measurement/window_truncation_20260813/RUN_CMD.sh [W]
#
# SCHEDULER CONTRACT (scripts/scheduler/work_queue.sh, queue item `window_truncation_census`):
#   * invoked as `bash <this> <W>` with SCHED_W / SCHED_BOX / SCHED_JOB_ID / SCHED_LOG exported,
#     from a wrapper that has already `cd`-ed to the repo root;
#   * SYNCHRONOUS / FOREGROUND on purpose — the scheduler has already detached us
#     (setsid+nohup locally, `systemd-run --user --scope -p MemoryMax=8G` remotely) and
#     writes its own DONE_/FAILED_<id> markers FROM OUR EXIT CODE. If this script
#     backgrounded its work and returned, the scheduler would mark it DONE immediately.
#     ⇒ never `&`, never `nohup`, here.
#   * bundle-sync, the `cd`-on-line-1 remote pipe and the memory-capped scope are all
#     done BY THE SCHEDULER for a remote box. This script therefore contains no ssh
#     and no box logic beyond resolving the share mount (which genuinely differs:
#     /mnt/c/carc-shared locally vs /mnt/carc-shared inside the laptop's WSL).
#
# WHAT IT RUNS — read-only over banked roots. No games are played, no band is consumed,
# nothing in governance/ or PRODUCTION.yaml is touched.
#
#   leg A  `walled`   — the 898-root CL-070 bank (band 28e9 champion self-play)
#   leg B  `fixed_v1` — every champion decision ply in the 23 E4 phone archives (~1,548)
#
# ⚠️ THE TWO LEGS MUST BE SEPARATE PROCESSES. `CARCASSONNE_FIX_R9` is latched at import
# (the Rust tile registry is a OnceLock and `base_deck` derives farm data at import), so
# one process cannot run both rules epochs. They are run sequentially, which gives that
# for free and keeps the box to one job.
#
# RESUME: each leg streams its rows to `rows.jsonl` and is launched with `--resume`, so a
# killed box restarts at ROOT granularity, not from zero. A leg whose DONE marker already
# exists is skipped entirely. Re-running this script is therefore always safe.
#
# ENV KNOBS (all optional):
#   WTC_SMOKE=1   2 roots per leg into ./_smoke, writes NO markers — launcher smoke test
#   WTC_N=<n>     cap roots per leg (0 = all, the default)
#   WTC_WORKERS   overrides W (which otherwise comes from $1, then SCHED_W, then 4)
set -uo pipefail

# --------------------------------------------------------------------------- #
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO" || { echo "cannot cd to repo root $REPO" >&2; exit 9; }

DIR="measurement/window_truncation_20260813"
LOGS="$DIR/logs"
PY="$REPO/.venv/bin/python"
CENSUS="scripts/measurement_infra/window_truncation_census.py"

W="${WTC_WORKERS:-${1:-${SCHED_W:-4}}}"
case "$W" in ''|*[!0-9]*) echo "worker count must be an integer, got '$W'" >&2; exit 2;; esac
[ "$W" -ge 1 ] || { echo "worker count must be >= 1, got $W" >&2; exit 2; }

SMOKE="${WTC_SMOKE:-0}"
NROOTS="${WTC_N:-0}"
BOX="${SCHED_BOX:-local}"
JOB="${SCHED_JOB_ID:-window_truncation_census}"

if [ "$SMOKE" = "1" ]; then
  OUT_A="$DIR/_smoke/census_walled"
  OUT_B="$DIR/_smoke/census_fixed_v1"
  NROOTS=2
  W=1
else
  OUT_A="$DIR/census_walled"
  OUT_B="$DIR/census_fixed_v1"
fi

mkdir -p "$LOGS" || exit 9

say() { echo "[$(date -Is)] $*"; }

# --------------------------------------------------------------------------- #
# share mount — THE one genuine box difference (CLUSTER_OPS invariant)         #
# --------------------------------------------------------------------------- #
SHARE=""
for cand in /mnt/c/carc-shared /mnt/carc-shared; do   # allow-path
  [ -d "$cand" ] && { SHARE="$cand"; break; }
done
[ -n "$SHARE" ] || { say "FATAL: no share mount found (/mnt/c/carc-shared or /mnt/carc-shared)"; exit 10; }  # allow-path
BANK="$SHARE/classical_search/move_agreement_k4_b28e9/roots.jsonl"

# --------------------------------------------------------------------------- #
# pre-flight — fail loudly and distinctly, before any compute                  #
# --------------------------------------------------------------------------- #
say "window-truncation census: box=$BOX job=$JOB W=$W smoke=$SMOKE share=$SHARE"
[ -x "$PY" ]        || { say "FATAL: venv python missing at $PY"; exit 11; }
[ -f "$CENSUS" ]    || { say "FATAL: instrument missing at $CENSUS"; exit 12; }
[ -f "$BANK" ]      || { say "FATAL: CL-070 root bank missing at $BANK"; exit 13; }
[ -d measurement/e4_games ] || { say "FATAL: measurement/e4_games absent (leg B roots)"; exit 14; }
"$PY" -c "import carc_rs, carcassonne_ai" >/dev/null 2>&1 \
  || { say "FATAL: venv cannot import carc_rs / carcassonne_ai"; exit 15; }

GITREV="$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo unknown)"
NROOTS_A=$(wc -l < "$BANK" | tr -d ' ')
say "preflight ok — git $GITREV, leg-A bank $NROOTS_A roots, $(ls measurement/e4_games/*.json 2>/dev/null | wc -l | tr -d ' ') e4 archives"

if [ "$SMOKE" != "1" ]; then
  rm -f "$DIR/FAILED_CENSUS"
  cat > "$DIR/RUN_MANIFEST.json" <<JSON
{
  "schema": "carcassonne-window-truncation-census/run-manifest/v1",
  "job_id": "$JOB",
  "box": "$BOX",
  "workers": $W,
  "started": "$(date -Is)",
  "git_rev": "$GITREV",
  "share": "$SHARE",
  "roots_leg_walled": "$BANK",
  "roots_leg_fixed_v1": "measurement/e4_games",
  "n_roots_cap": $NROOTS,
  "design": "$DIR/DESIGN.md",
  "instrument": "$CENSUS",
  "read_only": true,
  "plays_games": false,
  "band": null,
  "note": "Two rules epochs, SEPARATE PROCESSES (CARCASSONNE_FIX_R9 is import-latched). Resume-able at root granularity. Epochs are reported separately and MUST NOT be pooled."
}
JSON
fi

# --------------------------------------------------------------------------- #
# one leg                                                                      #
# --------------------------------------------------------------------------- #
run_leg() {           # run_leg <name> <out_dir> <log> <r9:0|1> <extra args...>
  local name="$1" out="$2" log="$3" r9="$4"; shift 4
  local marker="$DIR/DONE_LEG_${name}"

  if [ "$SMOKE" != "1" ] && [ -f "$marker" ]; then
    say "leg $name: DONE marker present ($marker) — skipping"
    return 0
  fi
  say "leg $name: starting (W=$W, R9=$r9, out=$out, log=$log)"
  mkdir -p "$out"

  # `--resume` is unconditional: rows stream to disk, so a fresh dir resumes from
  # nothing and a half-finished one picks up where the box died.
  if [ "$r9" = "1" ]; then export CARCASSONNE_FIX_R9=1; else unset CARCASSONNE_FIX_R9; fi
  "$PY" -u "$CENSUS" \
      --out-dir "$out" --workers "$W" --n "$NROOTS" --resume \
      --tag "${JOB}_${name}_W${W}_${BOX}" "$@" 2>&1 | tee -a "$log"
  local rc="${PIPESTATUS[0]}"
  unset CARCASSONNE_FIX_R9

  if [ "$rc" -ne 0 ]; then
    say "leg $name: FAILED rc=$rc (log: $log)"
    return "$rc"
  fi
  [ "$SMOKE" = "1" ] || echo "ok $(date -Is) W=$W box=$BOX git=$GITREV" > "$marker"
  say "leg $name: done"
  return 0
}

fail() {              # fail <stage> <rc>
  say "CENSUS FAILED at $1 (rc=$2)"
  if [ "$SMOKE" != "1" ]; then
    echo "stage=$1 rc=$2 $(date -Is) box=$BOX W=$W" >> "$DIR/FAILED_CENSUS"
  fi
  exit "$2"
}

T0=$(date +%s)

# --- leg A: walled, the CL-070 bank ---------------------------------------- #
run_leg walled "$OUT_A" "$LOGS/census_walled.log" 0 \
    --roots "$BANK" --rules-profile walled
rc=$?; [ "$rc" -eq 0 ] || fail "leg_walled" "$rc"

# --- leg B: fixed_v1, the E4 champion decision plies ------------------------ #
# SEPARATE PROCESS, deliberately: CARCASSONNE_FIX_R9 cannot be flipped in-process.
run_leg fixed_v1 "$OUT_B" "$LOGS/census_fixed_v1.log" 1 \
    --roots-format e4 --roots measurement/e4_games --rules-profile fixed_v1
rc=$?; [ "$rc" -eq 0 ] || fail "leg_fixed_v1" "$rc"

# --------------------------------------------------------------------------- #
# mechanical result note (NOT an adjudication — READOUT.md stays human-owned)  #
# --------------------------------------------------------------------------- #
ELAPSED=$(( $(date +%s) - T0 ))
say "both legs complete in ${ELAPSED}s — writing CENSUS_RESULT.md"

if [ "$SMOKE" = "1" ]; then
  say "SMOKE ok — no markers, no CENSUS_RESULT.md written"
  exit 0
fi

"$PY" - "$OUT_A/summary.json" "$OUT_B/summary.json" "$DIR/CENSUS_RESULT.md" \
       "$ELAPSED" "$W" "$BOX" "$GITREV" <<'PYEOF'
import json, sys, datetime

a_p, b_p, out_p, elapsed, w, box, rev = sys.argv[1:8]
legs = [("walled (CL-070 bank)", json.load(open(a_p))),
        ("fixed_v1 (E4 archives)", json.load(open(b_p)))]

def rule_of_three(n):
    return 3.0 / n if n else None

NODES_PER_GAME = 72 * 11008          # 72 champion decisions x k8 x 1376

L = []
L.append("# Window-truncation census — MECHANICAL RESULT\n")
L.append("**Auto-generated by `RUN_CMD.sh`. This is the arithmetic, NOT the verdict —\n"
         "the adjudicated read belongs in `READOUT.md` and follows the pre-registered\n"
         "thresholds in [DESIGN.md](DESIGN.md) §6.**\n")
L.append(f"\n- run: box `{box}`, W={w}, git `{rev}`, {int(elapsed)//60} min "
         f"({datetime.datetime.now().isoformat(timespec='seconds')})")
L.append("- ⚠️ the two rules epochs are reported SEPARATELY and must not be pooled "
         "(different wall geometries)\n")

L.append("\n| statistic | " + " | ".join(n for n, _ in legs) + " |")
L.append("|---|" + "---|" * len(legs))
rows = [
    ("roots censused", "n_censused_roots"),
    ("expanded nodes censused", "nodes_censused"),
    ("**nodes with >=1 dropped LEGAL action**", "nodes_truncated"),
    ("node truncation rate (P2)", "node_truncation_rate"),
    ("visit-weighted rate", "visit_weighted_truncation_rate"),
    ("**empty-mask nodes (P3)**", "nodes_empty_mask"),
    ("world-search raises (P3)", "world_errors"),
    ("roots with any search truncation", "roots_with_any_search_truncation"),
    ("root (played-level) truncation", "roots_with_root_truncation"),
    ("**pick changed at W=71 (P1)**", "n_pick_changed"),
    ("pick comparisons", "n_pick_comparable"),
    ("**P1 pick_change_rate**", "pick_change_rate"),
    ("iso null control (n / violations)", None),
    ("digest gate failures", "digest_gate_fail"),
    ("encode collisions", "encode_collisions"),
    ("error rows", "n_error_rows"),
    ("skipped forced / solver-region", None),
]
for label, key in rows:
    cells = []
    for _, s in legs:
        if label.startswith("iso"):
            cells.append(f"{s.get('iso_control_n')} / {s.get('iso_control_violations')}")
        elif label.startswith("skipped"):
            cells.append(f"{s.get('n_skipped_forced')} / {s.get('n_skipped_solver_region')}")
        else:
            v = s.get(key)
            cells.append("n/a" if v is None else (f"{v:.3e}" if isinstance(v, float) and 0 < v < 1e-3
                                                 else f"{v:.4f}" if isinstance(v, float) else str(v)))
    L.append(f"| {label} | " + " | ".join(cells) + " |")

L.append("\n## Rule-of-three bounds on a null (95%)\n")
for name, s in legs:
    n = s.get("nodes_censused") or 0
    t = s.get("nodes_truncated") or 0
    if t == 0 and n:
        r3 = rule_of_three(n)
        L.append(f"- **{name}**: 0/{n:,} => <= {r3:.2e} per node "
                 f"=> **<= {r3 * NODES_PER_GAME:.2f} truncation events per champion-game**")
    else:
        L.append(f"- **{name}**: {t}/{n:,} = {(t / n if n else 0):.3e} per node "
                 f"=> ~{(t / n if n else 0) * NODES_PER_GAME:.2f} events per champion-game (NOT a null)")

L.append("\n## Pre-registered read (DESIGN.md §6), applied mechanically\n")
L.append("**P3 — ALREADY FIRED, independently of this census.** A real "
         "`NoLegalActionsAtInterior` raise happened in production on 2026-08-13 "
         "(J7ZERO confirm, deck 126000000135), and it is reproduced inside the "
         "instrument (`crash_cell/`). The fail-loud fix (DESIGN §7 F-c) is licensed "
         "regardless of anything below.\n")
for name, s in legs:
    p1 = s.get("pick_change_rate")
    if p1 is None:
        band = "no comparable roots — P1 unread"
    elif p1 >= 0.02:
        band = "**REAL DEFECT band (P1 >= 2%)** — price the changed roots, then fix (F-a)"
    elif p1 >= 0.005:
        band = "**GREY band (0.5% <= P1 < 2%)** — price with oracle_score_pilot before deciding"
    else:
        band = "CURIOSITY band (P1 < 0.5%) for strength; P3 still stands on its own"
    L.append(f"- **{name}** — P1 = {p1}: {band}")
    if (s.get("nodes_truncated") or 0) > 0 and p1 == 0:
        L.append("  - ⚠️ P2 > 0 with P1 = 0 => 'real but so far harmless', NOT 'dead' "
                 "(DESIGN §6-P2: P1 has far less power than P2).")
    if (s.get("iso_control_violations") or 0) > 0:
        L.append("  - 🚨 ISO CONTROL VIOLATED — narrow/wide diverged with zero truncation. "
                 "This is an INSTRUMENT BUG; do not read any number above until resolved.")

open(out_p, "w").write("\n".join(L) + "\n")
print("wrote", out_p)
PYEOF
rc=$?; [ "$rc" -eq 0 ] || fail "census_result" "$rc"

echo "ok $(date -Is) box=$BOX W=$W git=$GITREV elapsed=${ELAPSED}s" > "$DIR/DONE_CENSUS"
say "DONE — $DIR/DONE_CENSUS written; see $DIR/CENSUS_RESULT.md"
exit 0
