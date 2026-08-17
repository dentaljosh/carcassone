#!/usr/bin/env bash
# =============================================================================
# jcz_tiearb_20260817 — MERGE THE PER-BOX SHARDS AND VERIFY COVERAGE EXACTLY.
#
#   merge_cells.sh                 merge both cells (the normal call)
#   merge_cells.sh <cell> [<cell>] merge only the named cell(s)
#   merge_cells.sh --check         verify only; write nothing
#
# ⭐ WHY THIS SCRIPT EXISTS. The owner ruling (DESIGN §0.1) put the run on TWO
# boxes, and `scripts/jcz_match/match.py` has no `--shared-claim`, so each box
# plays a DISJOINT, CONTIGUOUS deck sub-range into its own shard
# `<cell>.<host>.jsonl`. Nothing downstream can read a half-cell. This script
# concatenates the shards into `<cell>.jsonl` and PROVES the union is exactly the
# planned cell — no gap, no duplicate, no out-of-band deck (READ_RULE `G-COVER`).
#
# ⚠️ IT IS NOT THE GATE. `adjudicate.py` gates `G-COVER` and `G-SPLIT`
# independently from the records; this is the pre-adjudication convenience check
# that fails LOUDLY at merge time instead of silently producing a short cell that
# only voids hours later. A disagreement between this script and the adjudicator
# is itself a defect worth reporting.
#
# ADJUDICATES NOTHING. It reads no margin, no score and no strength number: it
# reads `deck_seed` and `champ_seat` and nothing else out of the records.
#
# OUTPUTS
#   $RUN_DIR/<cell>.jsonl            the merged cell (also copied to the share)
#   $RUN_DIR/<cell>.hostmap.json     deck_seed -> host, merged from the sidecars
#                                    AND cross-checked against shard membership
#   $RUN_DIR/COVER_<cell>.json       the per-cell `G-COVER` report
#   $RUN_DIR/SPLIT_CHECK.json        `G-SPLIT`: CELL A's map vs CELL B's map
#
# ABORTS (loudly, listing the offending seeds) on:
#   * a missing shard for a host that has a hostmap sidecar
#   * a deck outside [BAND, BAND+DECKS-1]
#   * a (deck_seed, champ_seat) pair recorded more than once
#   * a deck missing either seating
#   * a shard whose records do not match the host its sidecar claims
#   * (reported, not fatal) CELL A and CELL B deck→host maps that differ
# =============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/WORKERS.conf"
. "$HERE/_boxenv.sh"

PY="$REPO_LOCAL/.venv/bin/python"
CHECK_ONLY=0
CELLS=()

for a in "$@"; do
  case "$a" in
    --check)   CHECK_ONLY=1 ;;
    -h|--help) sed -n '2,45p' "$0"; exit 0 ;;
    "$CELL_A"|"$CELL_B") CELLS+=("$a") ;;
    *) echo "FATAL: unknown argument '$a' (expected --check, $CELL_A or $CELL_B)" >&2; exit 2 ;;
  esac
done
if [ "${#CELLS[@]}" -eq 0 ]; then CELLS=("$CELL_A" "$CELL_B"); fi

# ⚠️ log/die write to STDERR, not stdout. `stage_shards` returns its shard list on
# STDOUT through a command substitution, so a progress line on stdout would be
# captured as if it were a shard path.
ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[merge $(ts)] $*" >&2; }
die() { log "FATAL: $*"; exit "${2:-1}"; }

[ -x "$PY" ] || die "no venv python at $PY"

# ---- the band. Merging without it cannot check "out of band" at all. --------
[ -f "$BAND_SENTINEL" ] || die "band sentinel $BAND_SENTINEL is ABSENT — nothing to merge against (G-BAND)" 23
BAND="$(grep -m1 -E '^[0-9]+$' "$BAND_SENTINEL" || true)"
case "$BAND" in ''|*[!0-9]*) die "band sentinel $BAND_SENTINEL holds no numeric band" 23 ;; esac
log "band=$BAND decks=$DECKS  expected per cell: $DECKS decks x 2 seatings = $N_GAMES games"
log "cells: ${CELLS[*]}"

# =============================================================================
# COLLECT THE SHARDS. A shard may live on the share (published by run_cell.sh at
# the end of each leg) or only in this box's own run dir. The share is preferred
# for the REMOTE box (it is the only copy this box can see) and the local run dir
# is preferred for the LOCAL box (it is the authoritative, per-game-fsync'd copy).
# ⚠️ SHARE_RUN is resolved BY HOSTNAME in _boxenv.sh, never by path existence —
# `/mnt/c/carc-shared` exists on BOTH boxes and points at different disks.
# =============================================================================
stage_shards() {
  local cell="$1" staged=0
  # every host that left a sidecar for this cell, from either location
  local maps
  maps="$( { ls "$RUN_DIR/${cell}".*.hostmap.json "$SHARE_RUN/${cell}".*.hostmap.json 2>/dev/null || true; } \
           | xargs -r -n1 basename | sort -u )"
  [ -n "$maps" ] || die "no hostmap sidecars for $cell in $RUN_DIR or $SHARE_RUN — did any box run?" 30
  for m in $maps; do
    local host shard local_shard share_shard
    host="${m#"${cell}".}"; host="${host%.hostmap.json}"
    shard="${cell}.${host}.jsonl"
    local_shard="$RUN_DIR/$shard"
    share_shard="$SHARE_RUN/$shard"
    if [ -s "$local_shard" ]; then
      echo "$local_shard"
    elif [ -s "$share_shard" ]; then
      echo "$share_shard"
    else
      die "host '$host' has a hostmap sidecar for $cell but NO shard at $local_shard or $share_shard" 31
    fi
    staged=$((staged + 1))
  done
  [ "$staged" -gt 0 ] || die "no shards staged for $cell" 30
}

for cell in "${CELLS[@]}"; do
  log "--- $cell ---"
  SHARDS="$(stage_shards "$cell")"
  echo "$SHARDS" | sed 's/^/    shard: /'

  MERGED="$RUN_DIR/${cell}.jsonl"
  COVER="$RUN_DIR/COVER_${cell}.json"
  MAPOUT="$RUN_DIR/${cell}.hostmap.json"

  if [ "$CHECK_ONLY" -eq 0 ]; then
    # `cat` in a stable, sorted-by-name order so the merged file is reproducible.
    # shellcheck disable=SC2086
    cat $(echo "$SHARDS" | sort) > "$MERGED".tmp
    mv -f "$MERGED".tmp "$MERGED"
    log "merged $(wc -l < "$MERGED" | tr -d ' ') records -> $MERGED"
  else
    log "--check: not writing $MERGED"
    # shellcheck disable=SC2086
    cat $(echo "$SHARDS" | sort) > "$MERGED".check.tmp
    MERGED="$MERGED.check.tmp"
  fi

  # ==========================================================================
  # G-COVER — EXACT coverage, computed from the records themselves.
  # Also rebuilds the deck→host map FROM SHARD MEMBERSHIP and cross-checks it
  # against the declared sidecars: the sidecar is a claim, the shard is evidence,
  # and `G-SPLIT` deserves both.
  # ==========================================================================
  MG_CELL="$cell" MG_BAND="$BAND" MG_DECKS="$DECKS" MG_MERGED="$MERGED" \
  MG_SHARDS="$SHARDS" MG_RUNDIR="$RUN_DIR" MG_SHARE="$SHARE_RUN" \
  MG_MAPOUT="$MAPOUT" MG_COVER="$COVER" MG_CHECKONLY="$CHECK_ONLY" \
    "$PY" - <<'PYEOF' || die "G-COVER FAILED for $cell — see the listing above" 32
import json, os, sys, collections, datetime, glob

cell   = os.environ["MG_CELL"]
band   = int(os.environ["MG_BAND"])
decks  = int(os.environ["MG_DECKS"])
merged = os.environ["MG_MERGED"]
shards = [s for s in os.environ["MG_SHARDS"].split("\n") if s.strip()]
rundir = os.environ["MG_RUNDIR"]
share  = os.environ["MG_SHARE"]
lo, hi = band, band + decks - 1

# ---- deck -> host, from SHARD MEMBERSHIP (evidence) ----------------------
derived = {}
seen = collections.Counter()          # (deck, seat) -> n
torn = 0
per_shard = []
for path in sorted(shards):
    host = os.path.basename(path).split(".")[-2]
    n = 0
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                torn += 1                       # a torn last line: reported, not silent
                continue
            if "deck_seed" not in d or "champ_seat" not in d:
                torn += 1
                continue
            ds, cs = int(d["deck_seed"]), int(d["champ_seat"])
            seen[(ds, cs)] += 1
            n += 1
            prev = derived.get(ds)
            if prev is not None and prev != host:
                derived[ds] = "CONFLICT:%s|%s" % (prev, host)
            elif prev is None:
                derived[ds] = host
    per_shard.append({"shard": path, "host": host, "records": n})

# ---- deck -> host, from the SIDECARS (declaration) -----------------------
declared = {}
sidecar_files = []
for base in (rundir, share):
    sidecar_files += sorted(glob.glob(os.path.join(base, "%s.*.hostmap.json" % cell)))
sidecar_meta = []
for p in sidecar_files:
    try:
        doc = json.load(open(p))
    except Exception as e:                                   # noqa: BLE001
        print("  !! unreadable sidecar %s: %s" % (p, e))
        continue
    sidecar_meta.append({k: doc.get(k) for k in
                         ("host", "seed_base", "n_decks", "state",
                          "records_observed", "git_head", "utc")})
    for k, v in (doc.get("hostmap") or doc.get("deck_host") or {}).items():
        k = int(k)
        if k in declared and declared[k] != v:
            declared[k] = "CONFLICT:%s|%s" % (declared[k], v)
        else:
            declared[k] = v

# ---- the four G-COVER failure modes -------------------------------------
expected = {(d, s) for d in range(lo, hi + 1) for s in (0, 1)}
observed = set(seen)
out_of_band = sorted({d for (d, _s) in observed if d < lo or d > hi})
duplicates  = sorted([(d, s, n) for (d, s), n in seen.items() if n > 1])
missing     = sorted(expected - observed)
extra       = sorted(observed - expected)

# ---- sidecar vs shard cross-check ---------------------------------------
map_conflicts = sorted([d for d, h in derived.items() if str(h).startswith("CONFLICT")])
mismatched = sorted([d for d in derived
                     if d in declared and declared[d] != derived[d]])
undeclared = sorted([d for d in derived if d not in declared])

ok = not (out_of_band or duplicates or missing or extra or map_conflicts or mismatched)

def head(xs, n=25):
    xs = list(xs)
    return xs[:n] + (["... %d more" % (len(xs) - n)] if len(xs) > n else [])

print("  cell            %s" % cell)
print("  band            [%d, %d]  (%d decks x 2 seatings = %d games)"
      % (lo, hi, decks, decks * 2))
print("  shards          %s" % json.dumps(per_shard))
print("  records         %d  (unique cells %d, torn/unparseable %d)"
      % (sum(seen.values()), len(seen), torn))
print("  out_of_band     %d  %s" % (len(out_of_band), head(out_of_band)))
print("  duplicates      %d  %s" % (len(duplicates), head(duplicates)))
print("  missing         %d  %s" % (len(missing), head(missing)))
print("  extra           %d  %s" % (len(extra), head(extra)))
print("  hostmap conflicts (a deck in two shards) %d  %s"
      % (len(map_conflicts), head(map_conflicts)))
print("  sidecar/shard host mismatches           %d  %s"
      % (len(mismatched), head(mismatched)))
print("  decks in a shard but in no sidecar      %d  %s"
      % (len(undeclared), head(undeclared)))
print("  G-COVER         %s" % ("PASS" if ok else "*** FAIL ***"))

doc = {
    "witness": "G-COVER (pre-adjudication convenience check; adjudicate.py gates it independently)",
    "cell": cell, "band": band, "decks": decks,
    "deck_range": [lo, hi], "games_expected": decks * 2,
    "utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "merged": merged, "shards": per_shard, "sidecars": sidecar_meta,
    "records_total": sum(seen.values()), "unique_cells": len(seen),
    "torn_or_unparseable": torn,
    "out_of_band": out_of_band, "duplicates": duplicates,
    "missing": missing, "extra": extra,
    "hostmap_conflicts": map_conflicts,
    "sidecar_shard_mismatches": mismatched,
    "decks_without_sidecar": undeclared,
    "pass": ok,
}
with open(os.environ["MG_COVER"], "w") as fh:
    json.dump(doc, fh, indent=1)

if os.environ["MG_CHECKONLY"] != "1":
    # the merged deck -> host map. DERIVED (evidence) is authoritative; the
    # declared sidecar value is carried alongside so a reader can see both.
    # ⚠️ THE KEY MUST BE `hostmap`, and no OTHER top-level key may be one of
    # adjudicate.py's wrappers ("host_map", "decks", "deck_hosts") — it takes the
    # FIRST wrapper it finds and an unrecognised shape VOIDS `G-SPLIT`.
    # `declared_by_launcher` is deliberately not a wrapper name.
    mapdoc = {
        "witness": "G-SPLIT input",
        "cell": cell, "band": band, "deck_range": [lo, hi],
        "utc": doc["utc"],
        "hostmap": {str(k): derived[k] for k in sorted(derived)},
        "declared_by_launcher": {str(k): declared[k] for k in sorted(declared)},
        "hosts": sorted({v for v in derived.values() if not str(v).startswith("CONFLICT")}),
        "n_decks_mapped": len(derived),
    }
    with open(os.environ["MG_MAPOUT"], "w") as fh:
        json.dump(mapdoc, fh, indent=1)

sys.exit(0 if ok else 1)
PYEOF

  if [ "$CHECK_ONLY" -eq 0 ]; then
    cp -f "$MERGED" "$SHARE_RUN/" 2>/dev/null || log "WARN: could not publish $MERGED to the share"
    cp -f "$MAPOUT" "$COVER" "$SHARE_RUN/" 2>/dev/null || true
    log "G-COVER PASS for $cell -> $COVER ; hostmap -> $MAPOUT"
  else
    rm -f "$MERGED"
    log "G-COVER PASS for $cell (--check: nothing written except $COVER)"
  fi
done

# =============================================================================
# G-SPLIT — CELL A's deck→host map vs CELL B's, asserted IDENTICAL.
#
# ⭐ WHY THIS MATTERS ARITHMETICALLY (DESIGN §0.1.2). `D = M_B − M_A` is
# DECK-PAIRED: deck d contributes margin_B(d) − margin_A(d). If deck d ran on the
# laptop in one cell and locally in the other, every per-box difference — the JVM
# packaging (17.0.19+10-1-24.04.2 locally vs +10-1-26.04.2 on the laptop), the
# different W and hence different contention, the different RAM headroom — lands
# INSIDE that paired difference and is arithmetically indistinguishable from the
# arbiter's effect. With the map identical, all of it is common to both terms and
# cancels EXACTLY. `launch.sh` guarantees it by computing the split ONCE and
# handing the same (seed_base, n_decks) pair to both cells on a box; this check
# proves it from the records afterwards.
#
# Emitted whenever BOTH cells were merged. It is a REPORT: `adjudicate.py` gates
# `G-SPLIT` independently and its verdict is the one that binds.
# =============================================================================
if [ "${#CELLS[@]}" -eq 2 ] && [ "$CHECK_ONLY" -eq 0 ]; then
  log "--- G-SPLIT: $CELL_A vs $CELL_B deck->host ---"
  # ⚠️ `set +e` around it: this block MUST be allowed to exit nonzero so the
  # explicit, explanatory failure below runs instead of `set -e` killing the
  # script with no message.
  set +e
  SP_A="$RUN_DIR/${CELL_A}.hostmap.json" \
  SP_B="$RUN_DIR/${CELL_B}.hostmap.json" \
  SP_OUT="$RUN_DIR/SPLIT_CHECK.json" \
  SP_CA="$CELL_A" SP_CB="$CELL_B" \
    "$PY" - <<'PYEOF'
import json, os, sys, datetime

a = json.load(open(os.environ["SP_A"]))
b = json.load(open(os.environ["SP_B"]))
ma, mb = a["hostmap"], b["hostmap"]
only_a = sorted(set(ma) - set(mb), key=int)
only_b = sorted(set(mb) - set(ma), key=int)
differ = sorted([k for k in set(ma) & set(mb) if ma[k] != mb[k]], key=int)
identical = not (only_a or only_b or differ)

def head(xs, n=25):
    xs = list(xs)
    return xs[:n] + (["... %d more" % (len(xs) - n)] if len(xs) > n else [])

print("  decks in %s only : %d %s" % (os.environ["SP_CA"], len(only_a), head(only_a)))
print("  decks in %s only : %d %s" % (os.environ["SP_CB"], len(only_b), head(only_b)))
print("  decks whose HOST differs between cells: %d %s" % (len(differ), head(differ)))
for k in differ[:25]:
    print("      deck %s : %s=%s  %s=%s"
          % (k, os.environ["SP_CA"], ma[k], os.environ["SP_CB"], mb[k]))
print("  G-SPLIT (identical deck->host across cells): %s"
      % ("PASS" if identical else "*** FAIL ***"))

doc = {
    "witness": "G-SPLIT (pre-adjudication convenience check; adjudicate.py gates it independently)",
    "utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "cell_a": os.environ["SP_CA"], "cell_b": os.environ["SP_CB"],
    "n_decks_a": len(ma), "n_decks_b": len(mb),
    "hosts_a": a.get("hosts"), "hosts_b": b.get("hosts"),
    "decks_only_in_a": only_a, "decks_only_in_b": only_b,
    "decks_with_different_host": differ,
    "identical": identical,
    "rationale": (
        "DESIGN §0.1.2 / READ_RULE G-SPLIT: D is deck-paired, so a deck that ran "
        "on different boxes in the two cells puts every per-box difference (JVM "
        "packaging, W and contention, RAM) INSIDE the paired difference, where it "
        "is indistinguishable from the arbiter's effect. Identical map => it "
        "cancels exactly."),
}
json.dump(doc, open(os.environ["SP_OUT"], "w"), indent=1)
sys.exit(0 if identical else 1)
PYEOF
  spr=$?
  set -e
  cp -f "$RUN_DIR/SPLIT_CHECK.json" "$SHARE_RUN/" 2>/dev/null || true
  if [ "$spr" -ne 0 ]; then
    log "!!! G-SPLIT FAILED — the deck->host assignment DIFFERS between the two cells."
    log "!!! See $RUN_DIR/SPLIT_CHECK.json. READ_RULE §3 VOIDS the run on this (U-UNREADABLE)."
    log "!!! Do NOT 'fix' it by re-labelling: the games were physically played on the"
    log "!!! boxes the records say. The remedy is to REPLAY the mismatched decks so"
    log "!!! that both cells' decks sit on the same box, or to accept U-UNREADABLE."
    exit 33
  fi
  log "G-SPLIT PASS -> $RUN_DIR/SPLIT_CHECK.json"
fi

log "MERGE COMPLETE. NOTHING ADJUDICATED — read READ_RULE.md §3 before any number."
exit 0
