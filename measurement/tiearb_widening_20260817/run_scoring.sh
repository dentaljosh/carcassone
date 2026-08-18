#!/usr/bin/env bash
# =============================================================================
# tiearb_widening_20260817 — TWO-BOX SCORING LAUNCHER.
#
#   run_scoring.sh <box> [stratum] [judge] [chunk ...]
#     box     : local | laptop-side
#     stratum : s1 | s2        (omitted => $STRATUM_ORDER from ALLOCATION.conf)
#     judge   : clair-puct | tier1-greedy
#                              (omitted => $JUDGE_ORDER from ALLOCATION.conf)
#     chunk   : 1..N           (omitted => the list ALLOCATION.conf gives this
#                               (stratum, box, judge))
#
# ⚠️ THIS SCRIPT CANNOT MOVE A VALUE. Chunk MEMBERSHIP comes from
# POSITION_ORDER.json (ONE committed seeded permutation per stratum, cut into
# sequential chunks) and is IDENTICAL for both judges. Who runs which chunk is
# throughput only: world/playout seeds are `sha256(tag|rid|j|salt)` — no chunk,
# no box, no worker count and no M enters the derivation
# (`oracle_score_pilot.world_seed`/`playout_seed`, imported by
# `tier1_rust_leg`). The frozen READ_RULE's `G-CRN` cross-judge join and the
# analyzer's per-position pairing on `rid` are therefore indifferent to the
# split, PROVIDED a rid is never split across boxes within a leg — which
# `stage_chunks.py` enforces structurally (whole-rid chunks) and this script
# re-verifies before it launches anything.
#
# ⚠️ `run_tiletie.py` HAS NO `--rids-file`. The only handle on "which positions"
# is `--positions-dir`, so restriction is MATERIALIZED: per-chunk positions dirs
# staged by `stage_chunks.py`. `run_tiletie.verify_leg_records` also demands a
# leg's records dir hold exactly its own input's rids, so per-chunk out-roots
# plus `merge_scoring.sh` are forced, not chosen.
#
# ⚠️ `--cap-j` IS NOT A `run_tiletie` FLAG. It is a `build_positions` knob
# (DESIGN §4's graded-knob table), already spent when the corpus was built. The
# uncapped property lives in `POSITIONS_PLAN.json::{uncapped,cap_j}` — the
# address `G-UNCAPPED` reads — and every chunk plan carries it VERBATIM. This
# script ASSERTS it per chunk instead of passing a flag that does not exist.
#
# ⚠️ THE SALT IS NOT A FLAG EITHER. `run_tiletie.WORLD_SEED_SALT` is a MODULE
# CONSTANT ("tiletie-v1", DESIGN §4's salt table) that `run_tiletie` passes to
# BOTH leg drivers as `--world-seed-salt`. This script asserts its value before
# launching, which is the only way to make it explicit.
#
# ⚠️ `--positions-dir` IS ALWAYS PASSED IN FULL (DESIGN §0.O). Its default is
# `measurement/tiletie_pricing_20260812/positions` — the SPENT corpus §3
# requires disjointness FROM.
#
# DETACH IT (Mac->Windows->WSL SIGHUP + WSL VM teardown both kill tty jobs):
#   setsid nohup measurement/tiearb_widening_20260817/run_scoring.sh local \
#     > measurement/tiearb_widening_20260817/logs/scoring_local.out 2>&1 \
#     < /dev/null & disown
# =============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CONF="$HERE/WORKERS.conf"
[ -f "$CONF" ] || CONF="$HERE/../WORKERS.conf"
[ -f "$CONF" ] || { echo "[scoring] FATAL: WORKERS.conf not found (W10.1 defines it)" >&2; exit 2; }
# shellcheck disable=SC1090
. "$CONF"
ALLOC="$HERE/ALLOCATION.conf"
[ -f "$ALLOC" ] || { echo "[scoring] FATAL: $ALLOC missing" >&2; exit 2; }
# shellcheck disable=SC1090
. "$ALLOC"

for v in W_EVAL_LOCAL W_EVAL_LAPTOP NICE SHARE_RUN_LOCAL SHARE_RUN_REMOTE \
         REPO_LOCAL REPO_REMOTE RUN_ID STRATUM_ORDER JUDGE_ORDER; do
  [ -n "${!v:-}" ] || { echo "[scoring] FATAL: $CONF/$ALLOC does not set $v" >&2; exit 2; }
done

BOX="${1:?usage: run_scoring.sh <local|laptop-side> [stratum] [judge] [chunk ...]}"
shift
case "$BOX" in
  local)       W="$W_EVAL_LOCAL";  REPO="$REPO_LOCAL";  SHARE_RUN="$SHARE_RUN_LOCAL" ;;
  laptop-side) W="$W_EVAL_LAPTOP"; REPO="$REPO_REMOTE"; SHARE_RUN="$SHARE_RUN_REMOTE" ;;
  *) echo "[scoring] FATAL: bad box '$BOX' (local | laptop-side)" >&2; exit 2 ;;
esac

STRATA="$STRATUM_ORDER"
JUDGES="$JUDGE_ORDER"
CHUNKS_OVERRIDE=""
if [ "$#" -gt 0 ]; then
  case "$1" in s1|s2) STRATA="$1"; shift ;; esac
fi
if [ "$#" -gt 0 ]; then
  case "$1" in clair-puct|tier1-greedy) JUDGES="$1"; shift ;; esac
fi
[ "$#" -gt 0 ] && CHUNKS_OVERRIDE="$*"

PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || { echo "[scoring] FATAL: no venv python at $PY" >&2; exit 2; }

# ⚠️ MUST run from the REPO ROOT. run_tiletie's preflight resolves relative
# paths against the CURRENT WORKING DIRECTORY; the tiearb2_20260816 launch died
# on both boxes for exactly this. Chunk plans carry ABSOLUTE leg paths, so this
# is belt-and-braces — keep it.
cd "$REPO" || { echo "[scoring] FATAL: cannot cd to repo root '$REPO'" >&2; exit 1; }

CAMPAIGN="$REPO/measurement/$RUN_ID"
# rev R4.5 — the LIVE pair is `shared_run_r4/` (WORKERS.conf::PREREG_DIR_NAME);
# `shared_run/` is the SPENT R3.3 pair and is read-only forever.
[ -n "${PREREG_DIR_NAME:-}" ] || { echo "FATAL: WORKERS.conf does not set \
PREREG_DIR_NAME (rev R4.5). Composing an empty name would drop this run's \
artifacts into the campaign root instead of the LIVE prereg dir." >&2; exit 2; }
RUN_DIR="$CAMPAIGN/$PREREG_DIR_NAME"           # FROZEN prereg dir — read only
LOGS="$CAMPAIGN/logs"
MANIFESTS="$CAMPAIGN/chunks/manifests"
STAMPS="$CAMPAIGN/chunks/stamps"
ORDER="$CAMPAIGN/POSITION_ORDER.json"
mkdir -p "$LOGS" "$MANIFESTS" "$STAMPS"

export CARC_SRC_ROOT="$REPO/src"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$LOGS/scoring_${BOX}_$STAMP.log"
exec > >(tee -a "$LOG") 2>&1

echo "[scoring] $(date -Is) box=$BOX W=$W strata='$STRATA' judges='$JUDGES'"
echo "[scoring] share-run=$SHARE_RUN  repo=$REPO  log=$LOG"
echo "[scoring] sizing assumption: local W$W_EVAL_LOCAL vs laptop W$W_EVAL_LAPTOP"
echo "[scoring]   x LAPTOP_RATE=${LAPTOP_RATE:-?} -> effective $W_EVAL_LOCAL : "\
"$($PY -c "print(round($W_EVAL_LAPTOP*${LAPTOP_RATE:-1},1))")"

# ---- share guard: the two boxes mount the share at DIFFERENT paths ----------
[ -d "$SHARE_RUN" ] || {
  echo "[scoring] FATAL: '$SHARE_RUN' absent — wrong share path for box '$BOX'." >&2
  echo "[scoring]   local uses /mnt/c/carc-shared, laptop uses /mnt/carc-shared." >&2
  exit 1; }

# =============================================================================
# PRE-LAUNCH ABORTS. Each one is a property the frozen READ_RULE depends on.
# =============================================================================

# (1) THE SALT. `run_tiletie.WORLD_SEED_SALT` is a module constant, not a flag —
#     asserting it here is the only way to make DESIGN §4's salt table explicit.
"$PY" - <<'PYEOF' || { echo "[scoring] FATAL: salt assertion failed — DO NOT LAUNCH." >&2; exit 1; }
import sys, pathlib
sys.path.insert(0, str(pathlib.Path("scripts/tiletie").resolve()))
import run_tiletie as RT
want = "tiletie-v1"
if RT.WORLD_SEED_SALT != want:
    sys.exit(f"[scoring] run_tiletie.WORLD_SEED_SALT = {RT.WORLD_SEED_SALT!r}, "
             f"DESIGN §4 fixes {want!r}")
if RT.M_MAX < 128:
    sys.exit(f"[scoring] run_tiletie.M_MAX = {RT.M_MAX} < 128; S1 needs --m 128")
print(f"[scoring] salt: run_tiletie.WORLD_SEED_SALT = {RT.WORLD_SEED_SALT!r} "
      f"(module constant, passed to BOTH leg drivers as --world-seed-salt)")
PYEOF

# (2) POSITION_ORDER.json + chunk membership, re-derived from SYNCED ARTEFACTS
#     ONLY. The obvious `stage_chunks.py verify` re-derives from the SOURCE
#     corpus, which lives only on the local box (the tiearb2 lesson). What has
#     to hold before launch is narrower and is checkable from the chunk dirs
#     alone: each chunk dir I am about to score holds exactly the rids
#     POSITION_ORDER.json assigns to it, and carries the corpus properties the
#     gates address. That is the property the cross-judge CRN join depends on.
[ -f "$ORDER" ] || { echo "[scoring] FATAL: $ORDER absent — run stage_chunks.py stage first." >&2; exit 1; }
"$PY" - "$CAMPAIGN" "$STRATA" <<'PYEOF' || { echo "[scoring] FATAL: POSITION_ORDER / chunk verification failed — DO NOT LAUNCH." >&2; exit 1; }
import hashlib, json, sys
from pathlib import Path
campaign, strata = Path(sys.argv[1]), sys.argv[2].split()
doc = json.loads((campaign / "POSITION_ORDER.json").read_text())
M_EXPECT = {"s1": 128, "s2": 32}
noted = set()          # one NOTE per (stratum, value), not one per chunk
for s in strata:
    st = doc["strata"].get(s)
    if st is None:
        sys.exit(f"[scoring] POSITION_ORDER.json has no stratum {s!r}")
    # ---- M: assert the STAMP, which is what --m is derived from ---------- #
    # POSITION_ORDER.json carries the COMMITTED M for the stratum (stamped by
    # stage_chunks from the pair). `m_for()` below independently states the same
    # constant to build `run_tiletie --m`. Cross-checking the two is the real
    # assertion: if they ever disagree, this launcher would score at a budget
    # the chunking was not sized for.
    m_stamp = int(st.get("m", -1))
    if m_stamp != M_EXPECT[s]:
        sys.exit(f"[scoring] {s}: POSITION_ORDER.json stamps m={m_stamp} but "
                 f"this launcher commits m={M_EXPECT[s]} — the stamp is what "
                 f"--m is derived from, so a disagreement here IS a defect")
    order, sizes = st["order"], st["chunk_sizes"]
    if len(order) != st["n"] or sum(sizes) != st["n"]:
        sys.exit(f"[scoring] {s}: POSITION_ORDER inconsistent n={st['n']} "
                 f"order={len(order)} sizes={sum(sizes)}")
    digest = hashlib.sha256(("\n".join(order) + "\n").encode()).hexdigest()
    if digest != st["sha256_order"]:
        sys.exit(f"[scoring] {s}: order digest MISMATCH — the committed permutation changed")
    lo, bounds = 0, []
    for n in sizes:
        bounds.append((lo, lo + n)); lo += n
    seen_all = set()
    for k, (a, b) in enumerate(bounds, 1):
        want = set(order[a:b])
        if seen_all & want:
            sys.exit(f"[scoring] {s}: chunk{k} overlaps an earlier chunk")
        seen_all |= want
        d = campaign / "chunks" / s / f"chunk{k}"
        arms_p, plan_p = d / "ARMS.json", d / "POSITIONS_PLAN.json"
        if not arms_p.is_file() or not plan_p.is_file():
            sys.exit(f"[scoring] {s}/chunk{k}: not staged ({d})")
        got = set(json.loads(arms_p.read_text()))
        if got != want:
            sys.exit(f"[scoring] {s}/chunk{k}: rid set != POSITION_ORDER slice "
                     f"(dir={len(got)} expected={len(want)} "
                     f"missing={len(want - got)} extra={len(got - want)})")
        plan = json.loads(plan_p.read_text())
        # the corpus properties the gates address must have survived the subset
        if plan.get("uncapped") is not True or plan.get("cap_j") is not None:
            sys.exit(f"[scoring] {s}/chunk{k}: uncapped={plan.get('uncapped')} "
                     f"cap_j={plan.get('cap_j')} — the widening corpus MUST be "
                     f"UNCAPPED (`--cap-j inf`); G-UNCAPPED reads these keys")
        if int(plan.get("deployed_cap_j", -1)) != 4:
            sys.exit(f"[scoring] {s}/chunk{k}: deployed_cap_j="
                     f"{plan.get('deployed_cap_j')} != 4 (G-SALT)")
        # ⚠️ NOT ASSERTED, and this is the SECOND copy of that decision (the
        # first was stage_chunks.py, fixed at b06ad1ff; ruling 038185ed
        # adjudicated the class). `build_positions` has NO `--m` flag: a chunk
        # plan's `m_worlds` is INHERITED from the corpus plan, whose value comes
        # from a module constant used only for cost arithmetic. It never enters
        # a seed, a position, an arm or a digest — seeds are
        # sha256(tag|rid|j|salt), with no M term. So it is 32 on EVERY corpus
        # this pipeline builds, and asserting it against S1's committed 128
        # refused the S1 launch outright while S2 passed on the coincidence that
        # 32 equals its committed M. The M of record is G-M's, read from
        # RUN_MANIFEST via `run_tiletie --m`.
        m_plan = int(plan.get("m_worlds", -1))
        if m_plan != M_EXPECT[s] and (s, m_plan) not in noted:
            noted.add((s, m_plan))
            print(f"[scoring] NOTE {s}: chunk plan m_worlds={m_plan} vs "
                  f"committed m={M_EXPECT[s]}. NOT a defect and NOT asserted: "
                  f"build_positions has no --m flag and its m_worlds is "
                  f"cost-arithmetic metadata only. The M of record is G-M's, "
                  f"from RUN_MANIFEST via run_tiletie --m.")
        if plan.get("world_seed_salt") not in (None, "tiletie-v1"):
            sys.exit(f"[scoring] {s}/chunk{k}: world_seed_salt="
                     f"{plan.get('world_seed_salt')!r} != 'tiletie-v1'")
        if (plan.get("afterstate_dedupe") or {}).get("applied") is not True:
            sys.exit(f"[scoring] {s}/chunk{k}: afterstate_dedupe.applied is not "
                     f"True — run_tiletie's preflight would refuse it")
        for key, info in (plan.get("files") or {}).items():
            p = Path(info["path"])
            if not p.is_file():
                sys.exit(f"[scoring] {s}/chunk{k}: missing leg file {p}")
            n = sum(1 for ln in p.read_text().splitlines() if ln.strip())
            if n != int(info["n"]):
                sys.exit(f"[scoring] {s}/chunk{k}: {p} has {n} lines, plan says {info['n']}")
    if seen_all != set(order):
        sys.exit(f"[scoring] {s}: the chunk dirs do not partition the committed order")
    print(f"[scoring] {s}: POSITION_ORDER verified (seed {doc['seed']}, n={st['n']}, "
          f"sizes={sizes}) — whole-rid chunks, disjoint, exhaustive")
PYEOF

echo "[scoring] ---- process census ----"
ps -o pid,etime,%cpu,comm -C python --sort=-etime 2>/dev/null | head -6 || echo "[scoring] no python"
cat /proc/loadavg

# =============================================================================
# THE LEGS
# =============================================================================
alloc_for() {   # $1=stratum $2=judge -> chunk list
  local key
  key="ALLOC_$(echo "$1_${BOX}_$2" | tr '.-' '__')"
  echo "${!key:-}"
}

m_for() { case "$1" in s1) echo 128 ;; s2) echo 32 ;; *) echo "" ;; esac; }

rc_all=0
for S in $STRATA; do
  M="$(m_for "$S")"
  [ -n "$M" ] || { echo "[scoring] FATAL: bad stratum '$S'" >&2; exit 2; }
  POSDIR_CORPUS="$RUN_DIR/corpus/positions_$S"
  for J in $JUDGES; do
    if [ -n "$CHUNKS_OVERRIDE" ]; then CH="$CHUNKS_OVERRIDE"; else CH="$(alloc_for "$S" "$J")"; fi
    if [ -z "${CH// /}" ]; then
      echo "[scoring] ($S,$BOX,$J): no chunks allocated — skip"
      continue
    fi
    echo "[scoring] ===== stratum=$S judge=$J chunks='$CH' m=$M"
    for k in $CH; do
      PLAN="$CAMPAIGN/chunks/$S/chunk${k}"
      OUT="$SHARE_RUN/chunks/$S/chunk${k}"
      DONE="$STAMPS/DONE_${S}_${J}_chunk${k}"
      if [ -f "$DONE" ]; then echo "[scoring] $S/$J/chunk$k already done — skip"; continue; fi
      [ -d "$PLAN" ] || { echo "[scoring] FATAL: plan dir $PLAN missing" >&2; exit 1; }
      mkdir -p "$OUT"

      # ⚠️ --positions-dir NAMED IN FULL (DESIGN §0.O) — the default is the SPENT
      #    measurement/tiletie_pricing_20260812/positions corpus.
      # ⚠️ --gate-out / --manifest-out go OUTSIDE the prereg dir: the frozen dir's
      #    RUN_MANIFEST_{S1,S2}.json is ONE file per stratum, assembled by
      #    merge_scoring.sh from these per-chunk manifests.
      CMD=(nice -n "$NICE" "$PY" "$REPO/scripts/tiletie/run_tiletie.py"
           --positions-dir "$PLAN"
           --judges "$J"
           --m "$M"
           --oracle-sims 100
           --arb-backend rust
           --arb-legal-mask-cache
           --only-profiles walled
           --workers "$W"
           --out-root "$OUT"
           --logs-dir "$LOGS"
           --gate-out "$CAMPAIGN/chunks/GATE_BACKEND_RECHECK_${S}_${J}_chunk${k}.json"
           --manifest-out "$MANIFESTS/RUN_MANIFEST_$(echo "$S" | tr '[:lower:]' '[:upper:]')_${J}_chunk${k}.json"
           --resume --yes)
      printf '[scoring] EXACT:'; printf ' %q' "${CMD[@]}"; echo
      "${CMD[@]}"
      rc=$?
      echo "[scoring] $S/$J/chunk$k rc=$rc $(date -Is)"
      if [ "$rc" -ne 0 ]; then
        rc_all=$rc
        echo "[scoring] $S/$J/chunk$k FAILED — continuing to the next chunk"
        continue
      fi
      touch "$DONE"
    done
    # per-(stratum, judge, box) completion stamp
    all=1
    nkey="N_CHUNKS_$S"; N="${!nkey:-0}"
    for k in $(seq 1 "$N"); do [ -f "$STAMPS/DONE_${S}_${J}_chunk${k}" ] || all=0; done
    [ "$all" -eq 1 ] && { touch "$STAMPS/DONE_${S}_${J}"; \
      echo "[scoring] ALL $N chunks DONE for $S/$J (both boxes)"; }
  done
done

# ---- readiness banner -------------------------------------------------------
ready=1
for S in $STRATA; do
  for J in tier1-greedy clair-puct; do
    [ -f "$STAMPS/DONE_${S}_${J}" ] || ready=0
  done
done
if [ "$ready" -eq 1 ]; then
  echo "=============================================================================="
  echo "  ✅ every allocated chunk of '$STRATA' has scored on BOTH judges."
  echo "  Next (LOCAL BOX, after the laptop's chunks have landed on the share):"
  echo "      measurement/$RUN_ID/merge_scoring.sh <stratum>"
  echo "=============================================================================="
fi

echo "[scoring] DONE box=$BOX rc_all=$rc_all $(date -Is)"
exit "$rc_all"
