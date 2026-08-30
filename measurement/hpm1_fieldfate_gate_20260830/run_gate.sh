#!/usr/bin/env bash
# HP-M1 field-fate KILL GATE — the whole run, per PREREG.md (frozen 2026-08-30).
# Runs on the LAPTOP. Scripts are shipped to $HPM1 (NOT the repo — the repo is
# pinned at its round commit and must not be synced).
set -uo pipefail
cd /home/doctor/projects/carcassone

HPM1=/home/doctor/hpm1_run
OUT=$HPM1/out
PY=/home/doctor/projects/carcassone/.venv/bin/python
W=${W:-16}
mkdir -p "$OUT"

echo "=== [1] E4 census — one process per rules profile (R9 is import-latched) ==="
for p in fixed_v1 walled app_aug2; do
  nice -n 19 "$PY" "$HPM1/fieldfate_census.py" --corpus E4 --profile "$p" \
      --out-dir "$OUT" --workers "$W" || echo "  !! E4/$p FAILED"
done

echo "=== [2] SP449 profile selection — PREREG 1.1, first with >=99% reconciled ==="
SEL=""
for p in walled retail centered18 app_aug2 fixed_v1; do
  d="$HPM1/sp_probe_$p"
  nice -n 19 "$PY" "$HPM1/fieldfate_census.py" --corpus SP449 --profile "$p" \
      --out-dir "$d" --workers "$W" || { echo "  !! SP449/$p FAILED"; continue; }
  rate=$("$PY" - "$d/rows_SP449_${p}_games.json" <<'PY'
import json, sys
g = json.load(open(sys.argv[1]))
print(f"{sum(1 for x in g if x['recon_ok'])/max(len(g),1):.4f}")
PY
)
  echo "  profile=$p reconcile_rate=$rate"
  ok=$("$PY" -c "print(1 if float('$rate')>=0.99 else 0)")
  if [ "$ok" = "1" ]; then
    SEL="$p"
    cp "$d/rows_SP449_${p}.jsonl"        "$OUT/"
    cp "$d/rows_SP449_${p}_games.json"   "$OUT/"
    cp "$d/rows_SP449_${p}_manifest.json" "$OUT/"
    break
  fi
done
if [ -z "$SEL" ]; then
  echo "  SP449 DROPPED — no profile reached 99% (PREREG 1.1 fallback path)"
else
  echo "  SP449 profile adopted: $SEL"
fi
echo "{\"sp449_profile\": \"${SEL}\"}" > "$OUT/SP449_PROFILE.json"

echo "=== [3] adjudicate the bars ==="
nice -n 19 "$PY" "$HPM1/fieldfate_gate.py" --dir "$OUT" --primary-profile fixed_v1
echo "=== DONE ==="
date -u +%FT%TZ > "$OUT/DONE"
