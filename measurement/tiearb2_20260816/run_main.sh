#!/usr/bin/env bash
# =============================================================================
# tiearb2_20260816 — MAIN SCORING RUN.
#
#   run_main.sh <box> <judge> [chunk ...]
#     box   : local | laptop-side
#     judge : clair-puct | tier1-greedy
#     chunk : 1..4; omitted => the chunk list ALLOCATION.conf gives this (box,judge)
#
# Chunk MEMBERSHIP comes from POSITION_ORDER.json (one committed seeded
# permutation, seed 20260816, cut into 4 sequential chunks) and is IDENTICAL for
# both judges — the cross-judge CRN join (G-CRN) and the analyser's per-position
# pairing both depend on that. Who runs which chunk is throughput only and
# cannot move a value.
#
# Records land per chunk (run_tiletie.verify_leg_records demands a records dir
# hold exactly its own chunk's rids), then are MERGED BY FILE COPY into
# merged/<judge>/ with a duplicate guard, so the analyser gets one root per judge.
#
# DETACH IT (Mac->Windows->WSL SIGHUP + WSL VM teardown both kill tty jobs):
#   setsid nohup measurement/tiearb2_20260816/run_main.sh local clair-puct \
#     > measurement/tiearb2_20260816/logs/main_local_clair.out 2>&1 < /dev/null &
#   disown
# =============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/WORKERS.conf"
. "$HERE/ALLOCATION.conf"

BOX="${1:?usage: run_main.sh <local|laptop-side> <clair-puct|tier1-greedy> [chunk ...]}"
JUDGE="${2:?usage: run_main.sh <local|laptop-side> <clair-puct|tier1-greedy> [chunk ...]}"
shift 2

case "$BOX" in
  local)       W="$W_LOCAL";  REPO="$REPO_LOCAL";  SHARE_RUN="$SHARE_RUN_LOCAL" ;;
  laptop-side) W="$W_LAPTOP"; REPO="$REPO_REMOTE"; SHARE_RUN="$SHARE_RUN_REMOTE" ;;
  *) echo "bad box '$BOX'" >&2; exit 2 ;;
esac
case "$JUDGE" in clair-puct|tier1-greedy) ;; *) echo "bad judge '$JUDGE'" >&2; exit 2 ;; esac

# allocation lookup: ALLOC_<box>_<judge> with - and . mapped to _
if [ "$#" -gt 0 ]; then
  CHUNKS="$*"
else
  key="ALLOC_$(echo "${BOX}_${JUDGE}" | tr '.-' '__')"
  CHUNKS="${!key:-}"
fi
[ -n "${CHUNKS// /}" ] || { echo "[main] no chunks allocated to ($BOX,$JUDGE) — nothing to do"; exit 0; }

PY="$REPO/.venv/bin/python"

# ⚠️ MUST run from the REPO ROOT. `POSITIONS_PLAN.json` stores its leg paths
# REPO-RELATIVE (e.g. "measurement/tiearb2_20260816/positions_chunk2/positions_walled_leg1.jsonl"),
# and run_tiletie's preflight resolves them against the CURRENT WORKING DIRECTORY.
# Without this cd, every chunk dies at `[preflight] positions: FAIL — missing
# positions file`, which is exactly what killed the 20:29 launch on BOTH boxes.
# (run_pilot.sh has always had this cd, which is why the pilot ran clean.)
cd "$REPO" || { echo "[main] FATAL: cannot cd to repo root '$REPO'" >&2; exit 1; }

LOGS="$HERE/logs"
mkdir -p "$LOGS"
export CARC_SRC_ROOT="$REPO/src"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$LOGS/main_${BOX}_${JUDGE}_$STAMP.log"
exec > >(tee -a "$LOG") 2>&1

echo "[main] $(date -Is) box=$BOX judge=$JUDGE W=$W chunks='$CHUNKS'"
echo "[main] share-run=$SHARE_RUN  log=$LOG"

# ---- share guard: the two boxes mount the share at DIFFERENT paths ----------
[ -d "$SHARE_RUN" ] || { echo "[main] FATAL: '$SHARE_RUN' absent — wrong share for box '$BOX'." >&2; exit 1; }

# ---- PRE-LAUNCH ABORTS (DESIGN §9) -----------------------------------------
# These three are the reason a launcher exists rather than a bare command line.
# Each one is a gate the DESIGN calls a PRE-LAUNCH ABORT: if it fails, the fresh
# corpus is NOT scored and the read-out is a harness report.

# (1) G-DISJOINT — the fresh corpus must share NO game, NO position and NO board
#     with the spent 2026-08-12 corpus (DESIGN §4.4).
DJ="$HERE/DISJOINTNESS.json"
[ -f "$DJ" ] || { echo "[main] FATAL: G-DISJOINT has not been evaluated ($DJ absent). DESIGN §9 makes it a PRE-LAUNCH ABORT — run scripts/tiletie/gate_disjoint.py first." >&2; exit 1; }
if [ "$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1])).get("passed"))' "$DJ")" != "True" ]; then
  "$PY" -c 'import json,sys;print(json.dumps(json.load(open(sys.argv[1])).get("layers"),indent=1))' "$DJ" >&2
  echo "[main] FATAL: G-DISJOINT FAILED (see $DJ). DESIGN §9: the fresh corpus is NOT scored. Resolve the overlap (drop the colliding positions from the corpus, or stage with stage_plans.py main --exclude-rids <file>), re-run gate_disjoint.py to a PASS, then re-run this script." >&2
  exit 1
fi
echo "[main] G-DISJOINT: passed"

# (2) PILOT.json — B* must already be FROZEN from cost alone (DESIGN §7.2/§10),
#     before one position of the fresh corpus is scored.
PJ="$HERE/PILOT.json"
[ -f "$PJ" ] || { echo "[main] FATAL: $PJ absent. DESIGN §10: the cost pilot runs FIRST and freezes B*. Run run_pilot.sh." >&2; exit 1; }
"$PY" - "$PJ" "$C_TIER1_ASSUMED" "$C_TIER1_REVISIT_TOLERANCE" <<'PYEOF' || exit 1
import json, sys
d = json.load(open(sys.argv[1]))
if (d.get("abort") or {}).get("triggered"):
    sys.exit("[main] FATAL: PILOT.json records an ABORT: %s"
             % ((d.get("abort") or {}).get("reasons")))
if d.get("B_star") is None:
    sys.exit("[main] FATAL: PILOT.json carries no top-level B_star — "
             "analyze_tiearb2.read_pilot would not find it either.")
c = d.get("c_tier1_worker_s_per_playout")
print("[main] PILOT.json: B* = %s, rho_wall(B*) = %s, c_tier1 = %s"
      % (d["B_star"], d.get("rho_wall_bstar"), c))
assumed, tol = float(sys.argv[2]), float(sys.argv[3])
if c and abs(c - assumed) / assumed > tol:
    print("[main] ⚠️  ADVISORY: the pilot's c_tier1 (%.4f) is more than %.0f%% off the "
          "ALLOCATION.conf assumption (%.2f) the chunk split was sized against — "
          "revisit ALLOCATION.conf before launching. THROUGHPUT ONLY: it cannot move "
          "a value, and chunk membership is fixed by POSITION_ORDER.json."
          % (c, tol * 100, assumed))
PYEOF

# (3) POSITION_ORDER.json — re-derived and compared BYTE FOR BYTE, so the two
#     boxes cannot drift apart on chunk membership. Both judges must score the
#     identical rid set per chunk or the cross-judge CRN join (G-CRN) breaks.
#     ⚠️ This check is SELF-CONTAINED on purpose. The obvious implementation —
#     `stage_plans.py main --verify` — re-derives the permutation from the SOURCE
#     corpus, which (a) lives only on the local box (`corpus/positions` is 65 MB and
#     is deliberately not synced) and (b) resolves its defaults RELATIVE to the repo
#     cwd, so it failed on BOTH boxes for two different reasons. What actually has
#     to hold before launch is narrower and is checkable from synced artefacts
#     alone: each chunk dir I am about to score must contain exactly the rids
#     POSITION_ORDER.json assigns to it. That is the property the cross-judge CRN
#     join depends on. (The full byte-identity re-derivation is still run on the
#     local box by run_analysis.sh, where the source corpus exists.)
"$PY" - "$HERE" "$CHUNKS" <<'PYEOF' || { echo "[main] FATAL: POSITION_ORDER.json / chunk verification failed — DO NOT LAUNCH." >&2; exit 1; }
import hashlib, json, sys
from pathlib import Path
here, chunks = Path(sys.argv[1]), [int(x) for x in sys.argv[2].split()]
doc = json.loads((here / "POSITION_ORDER.json").read_text())
order, sizes = doc["order"], doc["chunk_sizes"]
if len(order) != doc["n"] or sum(sizes) != doc["n"]:
    sys.exit(f"[main] POSITION_ORDER.json inconsistent: n={doc['n']} order={len(order)} sizes={sum(sizes)}")

# stage_plans.py writes the order file as one rid per line WITH a trailing
# newline, and hashes exactly those bytes. Reproduce that, trailing "\n" included.
digest = hashlib.sha256(("\n".join(order) + "\n").encode()).hexdigest()
if doc.get("sha256_order") and digest != doc["sha256_order"]:
    sys.exit(f"[main] POSITION_ORDER.json order digest MISMATCH — the committed permutation changed")
bounds, off = [], 0
for s in sizes:
    bounds.append((off, off + s)); off += s
for k in chunks:
    lo, hi = bounds[k - 1]
    expect = set(order[lo:hi])
    d = here / f"positions_chunk{k}"
    arms = d / "ARMS.json"
    if not arms.is_file():
        sys.exit(f"[main] chunk{k}: {arms} missing")
    got = set(json.loads(arms.read_text()))
    if got != expect:
        sys.exit(f"[main] chunk{k}: rid set != POSITION_ORDER slice "
                 f"(dir={len(got)} expected={len(expect)} "
                 f"missing={len(expect - got)} extra={len(got - expect)})")
    legs = sorted(d.glob("positions_*_leg*.jsonl"))
    if not legs:
        sys.exit(f"[main] chunk{k}: no leg files in {d}")
    print(f"[main] chunk{k}: {len(got)} rids match POSITION_ORDER, {len(legs)} leg file(s)")
print(f"[main] POSITION_ORDER.json verified (seed {doc['seed']}, n={doc['n']}, sizes={sizes})")
PYEOF

echo "[main] ---- process census ----"
ps -o pid,etime,%cpu,comm -C python --sort=-etime 2>/dev/null | head -5 || echo "[main] no python"
cat /proc/loadavg

rc_all=0
for k in $CHUNKS; do
  PLAN="$HERE/positions_chunk${k}"
  OUT="$SHARE_RUN/main/chunk${k}"
  DONE="$HERE/DONE_${JUDGE}_CHUNK${k}"
  if [ -f "$DONE" ]; then echo "[main] chunk$k ($JUDGE) already done — skip"; continue; fi
  [ -d "$PLAN" ] || { echo "[main] FATAL: plan dir $PLAN missing" >&2; exit 1; }
  mkdir -p "$OUT"
  echo "[main] ===== chunk $k -> $OUT"
  CMD=(nice -n "$NICE" "$PY" "$REPO/scripts/tiletie/run_tiletie.py"
       --positions-dir "$PLAN"
       --judges "$JUDGE"
       --m 32
       --oracle-sims 100
       --workers "$W"
       --out-root "$OUT"
       --logs-dir "$LOGS"
       --gate-out "$HERE/GATE_BACKEND_RECHECK_${JUDGE}_chunk${k}.json"
       --manifest-out "$HERE/RUN_MANIFEST_${JUDGE}_chunk${k}.json"
       --resume --yes)
  printf '[main] EXACT:'; printf ' %q' "${CMD[@]}"; echo
  "${CMD[@]}"
  rc=$?
  echo "[main] chunk$k rc=$rc $(date -Is)"
  if [ "$rc" -ne 0 ]; then rc_all=$rc; echo "[main] chunk$k FAILED — continuing to next chunk"; continue; fi
  touch "$DONE"
done

# ---- merge by file copy, with a duplicate guard ----------------------------
MERGED="$SHARE_RUN/main/merged/$JUDGE"
mkdir -p "$MERGED"
dups=0; copied=0
for k in $CHUNKS; do
  SRC="$SHARE_RUN/main/chunk${k}/$JUDGE"
  [ -d "$SRC" ] || continue
  while IFS= read -r f; do
    rel="${f#"$SRC"/}"
    dst="$MERGED/$rel"
    if [ -f "$dst" ]; then dups=$((dups+1)); echo "[main] DUPLICATE (not overwritten): $rel"; continue; fi
    mkdir -p "$(dirname "$dst")"; cp -p "$f" "$dst"; copied=$((copied+1))
  done < <(find "$SRC" -type f -name '*.json')
done
echo "[main] merge: copied=$copied duplicates=$dups -> $MERGED"
[ "$dups" -eq 0 ] || { echo "[main] FATAL: $dups duplicate record(s) — a chunk was merged twice." >&2; exit 1; }

echo "[main] records now under $MERGED: $(find "$MERGED" -path '*/records/*.json' | wc -l)"
touch "$HERE/DONE_${JUDGE}_${BOX}"

# ---- completion stamps -----------------------------------------------------
# DONE_MAIN_<judge> when that judge has all N_CHUNKS chunk stamps; DONE_MAIN when
# BOTH judges do. The per-(judge,chunk) stamps are authoritative for resume —
# these two are the "is the read ready for analysis" signal.
done_judge=1
for k in $(seq 1 "$N_CHUNKS"); do
  [ -f "$HERE/DONE_${JUDGE}_CHUNK${k}" ] || done_judge=0
done
if [ "$done_judge" -eq 1 ]; then
  touch "$HERE/DONE_MAIN_${JUDGE}"
  echo "[main] ALL $N_CHUNKS CHUNKS DONE for $JUDGE"
fi
if [ -f "$HERE/DONE_MAIN_clair-puct" ] && [ -f "$HERE/DONE_MAIN_tier1-greedy" ]; then
  touch "$HERE/DONE_MAIN"
  echo "=============================================================================="
  echo "  ✅ DONE_MAIN — both judges have scored all $N_CHUNKS chunks."
  echo "  Next: run_analysis.sh   (LOCAL BOX ONLY)"
  echo "=============================================================================="
fi

echo "[main] DONE box=$BOX judge=$JUDGE rc_all=$rc_all $(date -Is)"
exit "$rc_all"
