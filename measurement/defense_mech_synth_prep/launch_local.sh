#!/bin/bash
# Fail-closed launcher for the synthetic mechanism-corroboration round.
#
# ⛔ It REFUSES to launch unless, in this order:
#      1. `BAND_CLAIMED` exists beside it and names a machine-readable band
#      2. `BLIND_COMMIT.json` no longer says PENDING, and HEAD equals it
#      3. pytest + the adjudicator selftest pass
#      4. the manifest emits (which RUNS G-NEGCTRL and raises on failure)
#      5. the SMOKE cell runs and its own adjudicator exits zero
#      6. the harvest reaches the G-N floor
#      7. the projected wall clock is under ETA_CAP_H
#
# Every stage is resumable; re-running skips what already landed.
#
# Usage:  REPO=<worktree> [W=32] [ETA_CAP_H=14] ./launch_local.sh [--stage STAGE]
set -uo pipefail

D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(cd "$D/../.." && pwd)}"
PY="${PY:-$REPO/.venv/bin/python}"
[ -x "$PY" ] || PY="/home/doctor/projects/carcassone/.venv/bin/python"
export PYTHONPATH="$REPO/src:$REPO/engine:$REPO/scripts"
export OMP_NUM_THREADS=1
W="${W:-32}"
ETA_CAP_H="${ETA_CAP_H:-14}"
HARVEST_BLOCK="${HARVEST_BLOCK:-200}"
HARVEST_CAP="${HARVEST_CAP:-2000}"
OUT="$D/out_local"
STAGE="${2:-all}"

die() { echo "⛔ REFUSING TO LAUNCH: $*" >&2; exit 1; }
say() { echo "[launch $(date +%H:%M:%S)] $*"; }

# --------------------------------------------------------------- 1. the band
BC="$D/BAND_CLAIMED"
[ -f "$BC" ] || die "no BAND_CLAIMED beside this script. This round SPENDS a deck
band (unlike E-1a/E-1b) — see BAND_CLAIMED.placeholder. The orchestrator claims
it, appends governance/BAND_REGISTRY.csv, and drops the file. This agent did not."
BAND_START="$(grep -oP '^BAND_START=\K[0-9]+' "$BC" | head -1)"
BAND_N="$(grep -oP '^BAND_N=\K[0-9]+' "$BC" | head -1)"
[ -n "$BAND_START" ] || die "BAND_CLAIMED carries no machine-readable 'BAND_START=<int>' line."
[ -n "$BAND_N" ] || die "BAND_CLAIMED carries no machine-readable 'BAND_N=<int>' line."
[ "$BAND_N" -ge "$HARVEST_CAP" ] || die "BAND_N=$BAND_N is smaller than the frozen
harvest cap ($HARVEST_CAP). Claim a wider band or lower HARVEST_CAP deliberately."
say "band $BAND_START .. $((BAND_START + BAND_N - 1)) (n=$BAND_N)"

# ------------------------------------------------- 2. the blind commit + HEAD
BLIND="$($PY -c "import json;print(json.load(open('$D/BLIND_COMMIT.json'))['blind_commit'])")"
[ "$BLIND" != "PENDING" ] || die "BLIND_COMMIT.json still says PENDING. The freeze
commit lands the design; a SECOND commit stamps its own 40-hex sha here."
HEAD="$(git -C "$REPO" rev-parse HEAD)"
[ "$HEAD" = "$BLIND" ] || die "HEAD ($HEAD) != BLIND_COMMIT ($BLIND). A pinned round
whose source moved is a cross-cell rev split; re-pinning is NOT a fix."
[ -z "$(git -C "$REPO" status --porcelain -- "$D")" ] || die "the round's own directory
is DIRTY at launch. Commit or stash before launching."

if [ "$STAGE" = "all" ] || [ "$STAGE" = "tests" ]; then
# ------------------------------------------------------------- 3. the tests
say "pytest + adjudicator selftest"
"$PY" -m pytest "$D/test_synth.py" -q -p no:cacheprovider || die "test_synth.py FAILED"
"$PY" "$D/adjudicate_synth.py" --selftest || die "adjudicator selftest FAILED"
fi

mkdir -p "$OUT"

if [ "$STAGE" = "all" ] || [ "$STAGE" = "manifest" ]; then
# ------------------------------------------- 4. the manifest RUNS G-NEGCTRL
say "manifest + G-NEGCTRL pre-flight (dose-0 all-zero, dose-d* boosted>0)"
"$PY" "$D/synth_mech.py" emit-manifest --manifest "$OUT/manifest.json" \
    --threads 1 || die "manifest/G-NEGCTRL FAILED"
fi

if [ "$STAGE" = "all" ] || [ "$STAGE" = "smoke" ]; then
# ------------------------------------------------------------- 5. the SMOKE
# ⛔ Throwaway seeds INSIDE the band's declared throwaway sub-range, never the claim.
SM="$D/out_SMOKE"
SMOKE_START=$((BAND_START + 999000))
say "SMOKE: 2 games at $SMOKE_START (throwaway sub-range), production knobs"
mkdir -p "$SM"
"$PY" "$D/synth_mech.py" gen --seed-start "$SMOKE_START" --n-games 2 \
    --outdir "$SM/games" --threads 1 || die "smoke generation FAILED"
"$PY" "$D/synth_mech.py" select --games "$SM/games" --outdir "$SM/select" \
    --threads 1 || die "smoke selection FAILED"
"$PY" "$D/synth_mech.py" freeze-targets --select "$SM/select" \
    --out "$SM/targets_synth.jsonl" --n-per-stratum 2 --n-identity 1 \
    || die "smoke freeze FAILED"
"$PY" "$D/synth_mech.py" emit-manifest --manifest "$SM/manifest.json" \
    --targets "$SM/targets_synth.jsonl" --threads 1 || die "smoke manifest FAILED"
"$PY" - "$SM" <<'PY' || die "smoke unit plan FAILED"
import json, pathlib, sys
SM = pathlib.Path(sys.argv[1])
rows = [json.loads(l) for l in (SM/"targets_synth.jsonl").read_text().splitlines() if l.strip()]
(SM/"units.txt").write_text("".join(f"{r['deck_seed']} {r['ply']} {w}\n"
                                    for r in rows for w in range(2)))
print(f"[smoke] {len(rows)} plies x 2 worlds")
PY
for i in $(seq 0 3); do
  nice -n 19 "$PY" "$D/synth_mech.py" price --targets "$SM/targets_synth.jsonl" \
    --games "$SM/games" --units "$SM/units.txt" --manifest "$SM/manifest.json" \
    --outdir "$SM/units" --threads 1 --shard "$i" --of 4 \
    > "$SM/price_$i.log" 2>&1 &
done
wait
# ⛔ The adjudicator writes SMOKE_VALIDATION.json ITSELF via --out. A shell `| tee`
#    would make the pipeline's exit status tee's and swallow the very refusal the
#    smoke exists to produce (E-1b's own §5.3 lesson).
"$PY" "$D/adjudicate_synth.py" --smoke --units "$SM/units" \
    --manifest "$SM/manifest.json" --targets "$SM/targets_synth.jsonl" \
    --selection "$SM/SELECTION.json" --out "$SM/SMOKE_VALIDATION.json" \
    || die "SMOKE ADJUDICATION FAILED — see $SM/SMOKE_VALIDATION.json"
say "smoke PASSED"
fi

if [ "$STAGE" = "all" ] || [ "$STAGE" = "harvest" ]; then
# ------------------------------------------------- 6. the ADAPTIVE HARVEST
# ⭐ Outcome-blind by construction: not one continuation is played here, so the
#    stopping rule is a function of covariates only (PREREG §5.4).
say "harvest: blocks of $HARVEST_BLOCK games, cap $HARVEST_CAP, stop at n_defense>=200"
played=0
while [ "$played" -lt "$HARVEST_CAP" ]; do
  start=$((BAND_START + played))
  say "  block: $HARVEST_BLOCK games from $start (played $played/$HARVEST_CAP)"
  for i in $(seq 0 $((W-1))); do
    nice -n 19 "$PY" "$D/synth_mech.py" gen --seed-start "$start" \
      --n-games "$HARVEST_BLOCK" --outdir "$OUT/games" --threads 1 \
      --shard "$i" --of "$W" >> "$OUT/gen.log" 2>&1 &
  done
  wait
  for i in $(seq 0 $((W-1))); do
    nice -n 19 "$PY" "$D/synth_mech.py" select --games "$OUT/games" \
      --outdir "$OUT/select" --threads 1 --shard "$i" --of "$W" \
      >> "$OUT/select.log" 2>&1 &
  done
  wait
  played=$((played + HARVEST_BLOCK))
  "$PY" "$D/synth_mech.py" freeze-targets --select "$OUT/select" \
      --out "$D/targets_synth.jsonl" || die "freeze-targets FAILED"
  nd="$($PY -c "import json;print(json.load(open('$D/SELECTION.json'))['n_defense'])")"
  say "  n_defense=$nd after $played games"
  [ "$nd" -ge 200 ] && break
done
nd="$($PY -c "import json;print(json.load(open('$D/SELECTION.json'))['n_defense'])")"
nc="$($PY -c "import json;print(json.load(open('$D/SELECTION.json'))['n_control'])")"
if [ "$nd" -lt 160 ] || [ "$nc" -lt 160 ]; then
  die "SYNTH-HARVEST-SHORT: n_defense=$nd n_control=$nc after $played games (floor 160).
PREREG §7 — this branch licenses NOTHING. Report the achieved n and the realized
yield; a successor round needs fresh owner funding and a fresh band."
fi
fi

if [ "$STAGE" = "all" ] || [ "$STAGE" = "cell" ]; then
# ------------------------------------------ 7. the ETA gate, then the cell
"$PY" "$D/synth_mech.py" emit-manifest --manifest "$OUT/manifest.json" \
    --targets "$D/targets_synth.jsonl" --threads 1 || die "manifest FAILED"
"$PY" - "$D" "$OUT" "$W" "$ETA_CAP_H" <<'PY' || exit 1
import json, pathlib, sys
D, OUT, W, CAP = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4])
rows = [json.loads(l) for l in (D/"targets_synth.jsonl").read_text().splitlines() if l.strip()]
priced = [r for r in rows if r["stratum"] in ("defense", "control", "identity")]
rem = sum(r["n_plies"] - r["ply"] for r in priced)
dec = rem * 4 * 8                                     # 4 arms x 8 worlds
h = dec * 2.219 / 3600.0 / W                          # E-1b's realized local rate
print(f"[eta] {len(priced)} plies, {dec:,} continuation-decisions, "
      f"~{h:.1f} h wall at W={W} (E-1b's 2.219 s/decision model of record)")
(OUT/"units.txt").write_text("".join(f"{r['deck_seed']} {r['ply']} {w}\n"
                                     for r in priced for w in range(8)))
if h > CAP:
    raise SystemExit(f"⛔ projected wall {h:.1f} h exceeds ETA_CAP_H={CAP}. PREREG §5.2's "
                     f"gate: this round does not launch.")
PY

# ⛔ The freeze-latch sentinel: main-tree commits refuse while this exists.
cat > "$D/RUN_LIVE_synth.json" <<EOF
{"round":"defense_mech_synth","started":"$(date -Is)","box":"local","W":$W,
 "band_start":$BAND_START,"blind_commit":"$BLIND",
 "note":"pinned round — NO main-tree commits at all while this file exists"}
EOF
say "launching the cell DETACHED at W=$W"
for i in $(seq 0 $((W-1))); do
  setsid nohup nice -n 19 "$PY" "$D/synth_mech.py" price \
    --targets "$D/targets_synth.jsonl" --games "$OUT/games" \
    --units "$OUT/units.txt" --manifest "$OUT/manifest.json" \
    --outdir "$OUT/units" --threads 1 --shard "$i" --of "$W" \
    --done-sentinel "$OUT/DONE_$i.json" \
    > "$OUT/price_$i.log" 2>&1 < /dev/null &
  disown
done
say "launched $W shards. Readout when DONE_*.json == $W:"
say "  $PY $D/adjudicate_synth.py --units $OUT/units --manifest $OUT/manifest.json \\"
say "      --targets $D/targets_synth.jsonl --selection $D/SELECTION.json \\"
say "      --select-rows $OUT/select --out $D/SYNTH.json"
say "  then REMOVE $D/RUN_LIVE_synth.json"
fi
