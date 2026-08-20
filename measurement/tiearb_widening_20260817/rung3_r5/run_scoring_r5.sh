#!/usr/bin/env bash
# =============================================================================
# rung3_r5 — TWO-BOX SCORING LAUNCHER. Parameterized sibling of the parent
# campaign's `run_scoring.sh` — same shape, same pre-launch-abort discipline,
# same per-chunk invocation pattern — but the campaign root is rung3_r5/
# EXPLICITLY, never derived from `$RUN_ID`. The parent script composes
# `CAMPAIGN="$REPO/measurement/$RUN_ID"`, which can only ever resolve to
# `measurement/tiearb_widening_20260817/` — it cannot reach
# `rung3_r5/chunks/s2/`, because `rung3_r5` is a SUCCESSOR PREREG (its own
# blind commit, its own corpus, its own staged layer -- ALLOCATION_R5.conf's
# header), not a stratum of the R4.5 pair the parent script points at.
#
#   run_scoring_r5.sh <box> [judge] [chunk ...] [--dry-run]
#     box      : local | laptop-side
#     judge    : clair-puct | tier1-greedy
#                              (omitted => $JUDGE_ORDER from ALLOCATION_R5.conf)
#     chunk    : 1..N           (omitted => the list ALLOCATION_R5.conf gives
#                                 this (box, judge))
#     --dry-run: print the exact command for every allocated chunk and stop --
#                no subprocess is launched, no DONE stamp is written, no share
#                output dir is created.
#
# ⚠️ NO STRATUM ARGUMENT. rung3_r5 has one population (R5's own; there is no
# R5 analog of the parent's S1/S2 split — S1 is scored, unaffected, under the
# PARENT pair; ADJUDICATION_R4_GATES.md RULING 1). Its chunks happen to live
# under a directory named `s2` only because `stage_chunks.py` is REUSED
# verbatim and its stratum-keyed M table hard-codes `s2 -> M=32`, which is
# exactly R5's committed M (ALLOCATION_R5.conf's header explains this). This
# launcher hard-codes that one internal name; it is not a second stratum to
# choose between.
#
# ⚠️ THIS SCRIPT CANNOT MOVE A VALUE, same as the parent (`run_scoring.sh`'s
# own header): chunk MEMBERSHIP comes from `POSITION_ORDER.json` (the seeded
# permutation `stage_chunks.py` cut) and is IDENTICAL for both judges; world
# and playout seeds are `sha256(tag|rid|j|salt)` — no chunk, no box, no worker
# count and no M enters the derivation. Who runs which chunk is throughput
# only, exactly as the parent's header argues; the same argument holds here
# unchanged because it is the same seed derivation, the same `run_tiletie`.
#
# ⚠️ ONE `run_tiletie.py` INVOCATION SCORES EVERY LEG A CHUNK'S
# `POSITIONS_PLAN.json` NAMES. `launch_legs()` (run_tiletie.py) iterates the
# plan's `files` block itself — one subprocess per (judge, profile, leg r) —
# so this launcher passes `--positions-dir` ONCE per (box, judge, chunk) and
# never enumerates legs itself. A chunk's `files` block does NOT necessarily
# carry all 12 legs: `stage_chunks.py` OMITS a leg key entirely for a chunk
# that has zero surviving rids on that leg (`write_chunk_dir`, `if not sel:
# continue`) — legs 9-12 are thin enough (171/110/66/9 total rids) that most
# chunks will carry only a handful of the 12 keys. That is expected, not a
# defect; nothing here assumes a fixed leg count per chunk.
#
# ⚠️ `--positions-dir` IS ALWAYS PASSED IN FULL (DESIGN §0.O, carried).
# ⚠️ `--cap-j` IS NOT A `run_tiletie` FLAG (carried from the parent's header —
#    see its comment for the full reasoning; unchanged here).
# ⚠️ THE SALT IS NOT A FLAG EITHER (carried; asserted below, same as parent).
#
# DETACH IT (Mac->Windows->WSL SIGHUP + WSL VM teardown both kill tty jobs):
#   setsid nohup measurement/tiearb_widening_20260817/rung3_r5/run_scoring_r5.sh \
#     local > measurement/tiearb_widening_20260817/rung3_r5/logs/scoring_local.out \
#     2>&1 < /dev/null & disown
# =============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAMPAIGN_PARENT="$(cd "$HERE/.." && pwd)"

# WORKERS.conf is the CAMPAIGN's (worker counts, share paths, repo roots are
# not rung3_r5-specific -- the parent's ONE definition, reused, never copied).
CONF="$CAMPAIGN_PARENT/WORKERS.conf"
[ -f "$CONF" ] || { echo "[scoring-r5] FATAL: WORKERS.conf not found at $CONF" >&2; exit 2; }
# shellcheck disable=SC1090
. "$CONF"
ALLOC="$HERE/ALLOCATION_R5.conf"
[ -f "$ALLOC" ] || { echo "[scoring-r5] FATAL: $ALLOC missing" >&2; exit 2; }
# shellcheck disable=SC1090
. "$ALLOC"

for v in W_EVAL_LOCAL W_EVAL_LAPTOP NICE SHARE_RUN_LOCAL SHARE_RUN_REMOTE \
         REPO_LOCAL REPO_REMOTE JUDGE_ORDER STRATUM_ORDER; do
  [ -n "${!v:-}" ] || { echo "[scoring-r5] FATAL: $CONF/$ALLOC does not set $v" >&2; exit 2; }
done
[ "$STRATUM_ORDER" = "s2" ] || {
  echo "[scoring-r5] FATAL: ALLOCATION_R5.conf sets STRATUM_ORDER='$STRATUM_ORDER', \
expected 's2' (the one directory name rung3_r5's chunks were staged under -- \
see the file header). This launcher hard-codes that name; a different value \
here means the two have drifted." >&2
  exit 2; }

BOX="${1:?usage: run_scoring_r5.sh <local|laptop-side> [judge] [chunk ...] [--dry-run]}"
shift
case "$BOX" in
  local)       W="$W_EVAL_LOCAL";  REPO="$REPO_LOCAL";  SHARE_RUN="$SHARE_RUN_LOCAL" ;;
  laptop-side) W="$W_EVAL_LAPTOP"; REPO="$REPO_REMOTE"; SHARE_RUN="$SHARE_RUN_REMOTE" ;;
  *) echo "[scoring-r5] FATAL: bad box '$BOX' (local | laptop-side)" >&2; exit 2 ;;
esac

# ---- pull --dry-run out of the remaining args wherever it appears ----------
DRY_RUN=0
REST=()
for a in "$@"; do
  if [ "$a" = "--dry-run" ]; then DRY_RUN=1; else REST+=("$a"); fi
done
set -- "${REST[@]}"

S="s2"                    # the ONE stratum name -- see the header + the guard above
JUDGES="$JUDGE_ORDER"
CHUNKS_OVERRIDE=""
if [ "$#" -gt 0 ]; then
  case "$1" in clair-puct|tier1-greedy) JUDGES="$1"; shift ;; esac
fi
[ "$#" -gt 0 ] && CHUNKS_OVERRIDE="$*"

PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || { echo "[scoring-r5] FATAL: no venv python at $PY" >&2; exit 2; }

# ⚠️ MUST run from the REPO ROOT -- same reasoning as the parent (run_tiletie's
# preflight resolves relative paths against the CWD; chunk plans carry
# ABSOLUTE leg paths, so this is belt-and-braces, kept for parity).
cd "$REPO" || { echo "[scoring-r5] FATAL: cannot cd to repo root '$REPO'" >&2; exit 1; }

# ⚠️ CAMPAIGN ROOT = rung3_r5/, EXPLICITLY. Never `$REPO/measurement/$RUN_ID`
# (that is the defect this script exists to fix -- see the file header).
CAMPAIGN="$REPO/measurement/tiearb_widening_20260817/rung3_r5"
[ -d "$CAMPAIGN" ] || { echo "[scoring-r5] FATAL: campaign root '$CAMPAIGN' absent" >&2; exit 1; }
LOGS="$CAMPAIGN/logs"
MANIFESTS="$CAMPAIGN/chunks/manifests"
STAMPS="$CAMPAIGN/chunks/stamps"
ORDER="$CAMPAIGN/POSITION_ORDER.json"
mkdir -p "$LOGS" "$MANIFESTS" "$STAMPS"

# ---- W-FREEZE-LATCH sentinel (DEVIATIONS D5 (b)) -----------------------------
# ⭐ Dropped at leg start, cleared at close-out AND on any exit (trap), so an
# abort can never leave the tree latched. The PreToolUse latch
# (scripts/hooks/pretooluse_lint.py) refuses a MAIN-TREE commit while it exists.
# It is a FILE, not a convention: it is visible to WHOEVER commits, which is the
# point — the freeze discipline has failed twice and both times at the
# orchestrator's hands, not a builder's or an executor's.
run_live_path() { echo "$CAMPAIGN/RUN_LIVE.json"; }
run_live_drop() {
  "$PY" - "$(run_live_path)" "$1" <<'RLEOF' || true
import json, os, socket, sys, time
p, what = sys.argv[1], sys.argv[2]
json.dump({"what": what, "host": socket.gethostname(), "pid": os.getppid(),
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "why": ("W-FREEZE-LATCH sentinel (DEVIATIONS D5 (b)): a MAIN-TREE "
                   "commit while this leg is live can put two revisions into "
                   "one run — spawn respawns and each new --shared-claim cell "
                   "RE-IMPORT FROM DISK. Cleared at close-out and on any exit."),
           "cleared_by": "the launcher's EXIT trap"},
          open(p, "w"), indent=2, sort_keys=True)
RLEOF
  echo "[freeze] RUN_LIVE dropped -> $(run_live_path)"
}
run_live_clear() { rm -f "$(run_live_path)" 2>/dev/null || true; }

if [ "${DRY_RUN:-0}" -eq 0 ]; then
  trap 'run_live_clear' EXIT INT TERM
  run_live_drop "rung3_r5 scoring leg (box=${BOX:-?})"
fi


# Share output is namespaced under rung3_r5/ too, so a real launch can never
# collide with the parent's (now-refused) top-level `chunks/s2/` share path.
SHARE_RUN_R5="$SHARE_RUN/rung3_r5"

export CARC_SRC_ROOT="$REPO/src"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$LOGS/scoring_${BOX}_$STAMP.log"
exec > >(tee -a "$LOG") 2>&1

echo "[scoring-r5] $(date -Is) box=$BOX W=$W judges='$JUDGES' dry_run=$DRY_RUN"
echo "[scoring-r5] campaign=$CAMPAIGN  share-run=$SHARE_RUN_R5  repo=$REPO  log=$LOG"
echo "[scoring-r5] sizing assumption: local W$W_EVAL_LOCAL vs laptop W$W_EVAL_LAPTOP"
echo "[scoring-r5]   x LAPTOP_RATE=${LAPTOP_RATE:-?} -> effective $W_EVAL_LOCAL : "\
"$($PY -c "print(round($W_EVAL_LAPTOP*${LAPTOP_RATE:-1},1))")"

# ---- share guard: the two boxes mount the share at DIFFERENT paths ----------
[ -d "$SHARE_RUN" ] || {
  echo "[scoring-r5] FATAL: '$SHARE_RUN' absent — wrong share path for box '$BOX'." >&2
  echo "[scoring-r5]   local uses /mnt/c/carc-shared, laptop uses /mnt/carc-shared." >&2
  exit 1; }

# =============================================================================
# PRE-LAUNCH ABORTS. Same properties as the parent's, same reasoning; adapted
# to R5's single stratum (M=32 only -- there is no M=128 leg in this design).
# =============================================================================

# (1) THE SALT + the M ceiling this launcher will ever request (32, not 128 --
#     R5 has no S1-shaped leg).
"$PY" - <<PYEOF || { echo "[scoring-r5] FATAL: salt assertion failed — DO NOT LAUNCH." >&2; exit 1; }
import sys, pathlib
sys.path.insert(0, str(pathlib.Path("scripts/tiletie").resolve()))
import run_tiletie as RT
want = "tiletie-v1"
if RT.WORLD_SEED_SALT != want:
    sys.exit(f"[scoring-r5] run_tiletie.WORLD_SEED_SALT = {RT.WORLD_SEED_SALT!r}, "
             f"expected {want!r}")
if RT.M_MAX < 32:
    sys.exit(f"[scoring-r5] run_tiletie.M_MAX = {RT.M_MAX} < 32; R5 needs --m 32")
print(f"[scoring-r5] salt: run_tiletie.WORLD_SEED_SALT = {RT.WORLD_SEED_SALT!r} "
      f"(module constant, passed to BOTH leg drivers as --world-seed-salt)")
PYEOF

# (2) POSITION_ORDER.json + chunk membership, re-derived from SYNCED ARTEFACTS
#     ONLY -- same narrower-than-full-rebuild property the parent checks
#     (its header, item 2): each chunk dir about to be scored holds exactly
#     the rids POSITION_ORDER.json assigns it, and carries the corpus
#     properties G-UNCAPPED / G-SALT / afterstate_dedupe address. Adapted for
#     R5: the per-chunk `files` block is walked GENERICALLY (no fixed leg
#     count assumed -- see the file header) instead of expecting one leg file.
[ -f "$ORDER" ] || { echo "[scoring-r5] FATAL: $ORDER absent — run stage_r5_corpus.py (stage) first." >&2; exit 1; }
"$PY" - "$CAMPAIGN" "$S" <<'PYEOF' || { echo "[scoring-r5] FATAL: POSITION_ORDER / chunk verification failed — DO NOT LAUNCH." >&2; exit 1; }
import hashlib, json, sys
from pathlib import Path
campaign, s = Path(sys.argv[1]), sys.argv[2]
doc = json.loads((campaign / "POSITION_ORDER.json").read_text())
M_EXPECT = 32
st = doc["strata"].get(s)
if st is None:
    sys.exit(f"[scoring-r5] POSITION_ORDER.json has no stratum {s!r}")
m_stamp = int(st.get("m", -1))
if m_stamp != M_EXPECT:
    sys.exit(f"[scoring-r5] POSITION_ORDER.json stamps m={m_stamp} but this "
             f"launcher commits m={M_EXPECT} — the stamp is what --m is "
             f"derived from, so a disagreement here IS a defect")
order, sizes = st["order"], st["chunk_sizes"]
if len(order) != st["n"] or sum(sizes) != st["n"]:
    sys.exit(f"[scoring-r5] POSITION_ORDER inconsistent n={st['n']} "
             f"order={len(order)} sizes={sum(sizes)}")
digest = hashlib.sha256(("\n".join(order) + "\n").encode()).hexdigest()
if digest != st["sha256_order"]:
    sys.exit("[scoring-r5] order digest MISMATCH — the committed permutation changed")
lo, bounds = 0, []
for n in sizes:
    bounds.append((lo, lo + n)); lo += n
seen_all = set()
for k, (a, b) in enumerate(bounds, 1):
    want = set(order[a:b])
    if seen_all & want:
        sys.exit(f"[scoring-r5] chunk{k} overlaps an earlier chunk")
    seen_all |= want
    d = campaign / "chunks" / s / f"chunk{k}"
    arms_p, plan_p = d / "ARMS.json", d / "POSITIONS_PLAN.json"
    if not arms_p.is_file() or not plan_p.is_file():
        sys.exit(f"[scoring-r5] chunk{k}: not staged ({d})")
    got = set(json.loads(arms_p.read_text()))
    if got != want:
        sys.exit(f"[scoring-r5] chunk{k}: rid set != POSITION_ORDER slice "
                 f"(dir={len(got)} expected={len(want)} "
                 f"missing={len(want - got)} extra={len(got - want)})")
    plan = json.loads(plan_p.read_text())
    if plan.get("uncapped") is not True or plan.get("cap_j") is not None:
        sys.exit(f"[scoring-r5] chunk{k}: uncapped={plan.get('uncapped')} "
                 f"cap_j={plan.get('cap_j')} — the widening corpus MUST be "
                 f"UNCAPPED (`--cap-j inf`); G-UNCAPPED reads these keys")
    if int(plan.get("deployed_cap_j", -1)) != 4:
        sys.exit(f"[scoring-r5] chunk{k}: deployed_cap_j="
                 f"{plan.get('deployed_cap_j')} != 4 (G-SALT)")
    if plan.get("world_seed_salt") not in (None, "tiletie-v1"):
        sys.exit(f"[scoring-r5] chunk{k}: world_seed_salt="
                 f"{plan.get('world_seed_salt')!r} != 'tiletie-v1'")
    if (plan.get("afterstate_dedupe") or {}).get("applied") is not True:
        sys.exit(f"[scoring-r5] chunk{k}: afterstate_dedupe.applied is not "
                 f"True — run_tiletie's preflight would refuse it")
    files = plan.get("files") or {}
    if not files:
        sys.exit(f"[scoring-r5] chunk{k}: POSITIONS_PLAN.json names zero leg files")
    n_lines_total = 0
    for key, info in files.items():
        p = Path(info["path"])
        if not p.is_file():
            sys.exit(f"[scoring-r5] chunk{k}: missing leg file {p}")
        n = sum(1 for ln in p.read_text().splitlines() if ln.strip())
        if n != int(info["n"]):
            sys.exit(f"[scoring-r5] chunk{k}: {p} has {n} lines, plan says {info['n']}")
        n_lines_total += n
    print(f"[scoring-r5] chunk{k}: {len(want)} rid(s), {len(files)} leg file(s), "
          f"{n_lines_total} total leg line(s)")
if seen_all != set(order):
    sys.exit("[scoring-r5] the chunk dirs do not partition the committed order")
print(f"[scoring-r5] {s}: POSITION_ORDER verified (seed {doc['seed']}, n={st['n']}, "
      f"sizes={sizes}) — whole-rid chunks, disjoint, exhaustive")
PYEOF

echo "[scoring-r5] ---- process census ----"
ps -o pid,etime,%cpu,comm -C python --sort=-etime 2>/dev/null | head -6 || echo "[scoring-r5] no python"
cat /proc/loadavg

# =============================================================================
# THE LEGS -- one run_tiletie.py invocation per (box, judge, chunk); it fans
# out every leg the chunk's plan names, internally (see the file header).
# =============================================================================
alloc_for() {   # $1=judge -> chunk list
  local key
  key="ALLOC_$(echo "${S}_${BOX}_$1" | tr '.-' '__')"
  echo "${!key:-}"
}

rc_all=0
POSDIR_CORPUS="$CAMPAIGN/corpus/positions_$S"
for J in $JUDGES; do
  if [ -n "$CHUNKS_OVERRIDE" ]; then CH="$CHUNKS_OVERRIDE"; else CH="$(alloc_for "$J")"; fi
  if [ -z "${CH// /}" ]; then
    echo "[scoring-r5] ($BOX,$J): no chunks allocated — skip"
    continue
  fi
  echo "[scoring-r5] ===== judge=$J chunks='$CH' m=32"
  for k in $CH; do
    PLAN="$CAMPAIGN/chunks/$S/chunk${k}"
    OUT="$SHARE_RUN_R5/chunks/$S/chunk${k}"
    DONE="$STAMPS/DONE_${J}_chunk${k}"
    if [ -f "$DONE" ]; then echo "[scoring-r5] $J/chunk$k already done — skip"; continue; fi
    [ -d "$PLAN" ] || { echo "[scoring-r5] FATAL: plan dir $PLAN missing" >&2; exit 1; }

    CMD=(nice -n "$NICE" "$PY" "$REPO/scripts/tiletie/run_tiletie.py"
         --positions-dir "$PLAN"
         --judges "$J"
         --m 32
         --oracle-sims 100
         --arb-backend rust
         --arb-legal-mask-cache
         --only-profiles walled
         --workers "$W"
         --out-root "$OUT"
         --logs-dir "$LOGS"
         --gate-out "$CAMPAIGN/chunks/GATE_BACKEND_RECHECK_${J}_chunk${k}.json"
         --manifest-out "$MANIFESTS/RUN_MANIFEST_R5_${J}_chunk${k}.json"
         --resume --yes)
    printf '[scoring-r5] EXACT:'; printf ' %q' "${CMD[@]}"; echo
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "[scoring-r5] DRY-RUN: not executing, no DONE stamp, no share dir created"
      continue
    fi
    mkdir -p "$OUT"
    "${CMD[@]}"
    rc=$?
    echo "[scoring-r5] $J/chunk$k rc=$rc $(date -Is)"
    if [ "$rc" -ne 0 ]; then
      rc_all=$rc
      echo "[scoring-r5] $J/chunk$k FAILED — continuing to the next chunk"
      continue
    fi
    touch "$DONE"
  done
  if [ "$DRY_RUN" -eq 0 ]; then
    all=1
    for k in $(seq 1 "$N_CHUNKS_s2"); do [ -f "$STAMPS/DONE_${J}_chunk${k}" ] || all=0; done
    [ "$all" -eq 1 ] && { touch "$STAMPS/DONE_${J}"; \
      echo "[scoring-r5] ALL $N_CHUNKS_s2 chunks DONE for $J (both boxes)"; }
  fi
done

# ---- readiness banner -------------------------------------------------------
if [ "$DRY_RUN" -eq 0 ]; then
  ready=1
  for J in tier1-greedy clair-puct; do
    [ -f "$STAMPS/DONE_${J}" ] || ready=0
  done
  if [ "$ready" -eq 1 ]; then
    echo "=============================================================================="
    echo "  ✅ every allocated rung3_r5 chunk has scored on BOTH judges."
    echo ""
    echo "  NEXT — MERGE. ⭐ The direct merge_legs use is BLESSED (D5 (c), DESIGN"
    echo "  line 448): the classification, the licence and the carry-forward all"
    echo "  live IN merge_legs, so a thin driver would add a wrapper without"
    echo "  adding a check. Two conditions travel with the blessing: the EXACT"
    echo "  invocation below is RECORDED IN THE READ-OUT, and this step is named"
    echo "  here rather than left as a TODO — a TODO that reads as an unbuilt"
    echo "  step, next to a step in fact performed by hand, is how a runbook lies"
    echo "  to its next reader."
    echo ""
    echo "  1) the R5 instrument witness (BOTH boxes — one box leaves the other's"
    echo "     working tree unwitnessed):"
    echo ""
    echo "     $PY $REPO/measurement/tiearb_widening_20260817/instrument_identity.py \\"
    echo "       --licence R5 --repo $REPO \\"
    echo "       --box local --box laptop:laptop-wsl \\"
    echo "       --out $CAMPAIGN/INSTRUMENT_IDENTITY_R5.json"
    echo ""
    echo "  2) the merge itself (--dry-run FIRST; it writes nothing):"
    echo ""
    echo "     $PY -u $REPO/measurement/tiearb_widening_20260817/merge_legs.py \\"
    echo "       --stratum $S --licence R5 \\"
    echo "       --chunks-root $SHARE_RUN/chunks/$S \\"
    echo "       --out-dir $CAMPAIGN/legs/$S \\"
    echo "       --positions-dir $CAMPAIGN/corpus/positions_$S \\"
    echo "       --manifests-dir $MANIFESTS --manifest-tag R5 \\"
    echo "       --instrument-identity $CAMPAIGN/INSTRUMENT_IDENTITY_R5.json \\"
    echo "       --run-manifest-out $CAMPAIGN/RUN_MANIFEST_R5.json \\"
    echo "       --report $CAMPAIGN/MERGE_REPORT_$S.json"
    echo ""
    echo "  ⚠️ --manifest-tag R5 is REQUIRED and is a FILENAME, not an address."
    echo "     This launcher wrote RUN_MANIFEST_R5_<judge>_chunk<N>.json; the"
    echo "     merge's default glob is the STRATUM (RUN_MANIFEST_S2_*), which"
    echo "     matches none of them. An empty glob is not a satisfied domain: the"
    echo "     D4.12 evidence map would come back empty and the licence would"
    echo "     refuse a HEALTHY run while naming the wrong cause."
    echo ""
    echo "  ⚠️ --run-manifest-out is RUN_MANIFEST_R5.json — the address READ_RULE"
    echo "     §2 gives G-M, G-SALT and G-BACKEND. Writing RUN_MANIFEST_S2.json"
    echo "     would leave all three primaries UNRESOLVED at A3."
    echo ""
    echo "  ⚠️ --licence R5 selects R5's OWN enumerated rev pair"
    echo "     {9bc2ab772ee907cdf4278985cf717497b95b2af1,"
    echo "      a5aa4a5e8573754b25476d220bbfe5fda514cf60} AND its witness file."
    echo "     It is NOT a permission: a rev outside that pair still refuses, and"
    echo "     the merge RE-DERIVES the instrument diff and refuses if non-empty."
    echo ""
    echo "  ⚠️ --out-dir is \$CAMPAIGN/legs/$S, NOT the share. READ_RULE §2"
    echo "     addresses the merged legs at RUN/legs/$S/... and RUN is the"
    echo "     CAMPAIGN dir; under ABSENT IS FAIL a G-M / G-SALT / G-BACKEND"
    echo "     fallback that resolves nowhere is the fail-always shape this pair"
    echo "     keeps catching. ⚠️ R4 merged its legs to the SHARE instead — this"
    echo "     is a DELIBERATE divergence from that precedent, made to keep the"
    echo "     addresses live, and it is REPORTED rather than assumed. One flag"
    echo "     reverses it if the owner prefers the share (then A2/A3 and the"
    echo "     adjudicator must both be pointed there explicitly)."
    echo ""
    echo "  3) G-DRAW — a pure invocation bless, no code change, no new mode."
    echo ""
    echo "     $PY $REPO/scripts/tiletie/gate_draw.py \\"
    echo "       --arms $CAMPAIGN/ARMS_R5.json \\"
    echo "       --out  $CAMPAIGN/GATE_DRAW_R5.json"
    echo ""
    echo "  ⛔ Do NOT pass --cap-j. Take the default DEPLOYED_CAP_J == 4. R5 is"
    echo "     the rung-3 (J > 4) read and the temptation to 'match the rung' is"
    echo "     precisely wrong: G-DRAW asserts that the recorded J=4 subset"
    echo "     reproduces this repo's own seeded draw. Passing R5's J would"
    echo "     compare subset_j4 against a draw it was never made by —"
    echo "     FAIL-ALWAYS, the G-CAP shape again. Expect n_checked = 1,060;"
    echo "     ok requires n_checked > 0, so an empty or mis-pathed --arms FAILS"
    echo "     rather than passing on zero rows."
    echo ""
    echo "  4) W9 / D-DRAW — the dedupe-partition probe. LATE and disclosed"
    echo "     (D6.1 class: its inputs are the sha-pinned corpus artifacts, which"
    echo "     scoring READS and does not write). ~3 s for the whole population."
    echo ""
    echo "     $PY $REPO/scripts/tiletie/d_draw_probe.py \\"
    echo "       --arms $CAMPAIGN/ARMS_R5.json \\"
    echo "       --leg  $CAMPAIGN/corpus/positions_s2/positions_walled_leg1.jsonl \\"
    echo "       --out  $CAMPAIGN/D_DRAW.json"
    echo ""
    echo "  ⛔ D-DRAW ADJUDICATES NOTHING and may never correct, reweight or"
    echo "     re-scale Delta_ora. The DISCHARGE is the Tier-1 partition block;"
    echo "     the chartered agreement_rate is a coincidence statistic printed"
    echo "     beside its null model and labelled NOT-EVIDENCE."
    echo "  ⚠️ NO FILTER FLAG EXISTS, by design: ARMS_R5 carries \`capped\` (false"
    echo "     on all 1,060) beside \`capped_at_4\` (true on all 1,060), and"
    echo "     filtering on the field whose NAME matches the charter's word"
    echo "     empties the population and passes G-DDRAW vacuously."
    echo ""
    echo "  5) A2 — the [post-corpus] acceptance pass. ⛔ It is LATE (deviation"
    echo "     D6: the pair named the pass and named no tool, so the checkpoint"
    echo "     was skipped before the first scoring leg). Its inputs were frozen"
    echo "     before scoring, so the audit is LATE, NOT CONTAMINATED — but its"
    echo "     protective value is spent, and A2 VERIFIES the freeze rather than"
    echo "     assuming it. A sha drift RAISES to the owner (exit 3); it is never"
    echo "     repaired or re-pinned."
    echo ""
    echo "     $PY $REPO/scripts/tiletie/acceptance_r5.py \\"
    echo "       --pass A2 --run $CAMPAIGN \\"
    echo "       --json-out $CAMPAIGN/ACCEPTANCE_A2.json"
    echo ""
    echo "  6) ADJUDICATE — the read-out. --dry-run FIRST (it writes nothing)."
    echo ""
    echo "     $PY $REPO/scripts/tiletie/analyze_rung3_r5.py \\"
    echo "       --run $CAMPAIGN --legs-root $CAMPAIGN/legs/$S \\"
    echo "       --out-json $CAMPAIGN/READOUT_R5.json \\"
    echo "       --out-md   $CAMPAIGN/READOUT_R5.md"
    echo ""
    echo "  7) A3 — the [post-scoring] pass, LAST."
    echo ""
    echo "     $PY $REPO/scripts/tiletie/acceptance_r5.py \\"
    echo "       --pass A3 --run $CAMPAIGN \\"
    echo "       --json-out $CAMPAIGN/ACCEPTANCE_A3.json"
    echo ""
    echo "  ⚠️ THE ORDER IS THE POINT — merge -> gate_draw -> D-DRAW -> A2 ->"
    echo "     adjudicate -> A3 — and A3 comes AFTER the adjudicator, not before."
    echo "     A3 audits READOUT:: addresses and THE ADJUDICATOR IS WHAT WRITES"
    echo "     THEM; run first it can only ever report the artifact missing,"
    echo "     which is exactly what happened (D6.3). Each pass is pinned"
    echo "     RELATIVE TO THE PRODUCER OF ITS INPUTS — 'after X writes A', never"
    echo "     'at the end': the extended D6.2 rule, whose load-bearing half is"
    echo "     that naming the tool is necessary and NOT sufficient."
    echo ""
    echo "  ⛔ THE VERDICT STAYS SEALED UNTIL ALL 19 GATES PASS."
    echo "=============================================================================="
  fi
fi

run_live_clear
echo "[scoring-r5] DONE box=$BOX rc_all=$rc_all $(date -Is)"
exit "$rc_all"
