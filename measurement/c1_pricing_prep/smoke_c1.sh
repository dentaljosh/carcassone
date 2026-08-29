#!/usr/bin/env bash
# C1 OUTCOME PRICING — the MANDATORY pre-launch smoke.  DESIGN.md §7.2.
#
#   BOX=local W=30 SHARE=/mnt/c/carc-shared ./smoke_c1.sh
#
# ⚠️ The 2026-08-28 PG-D7..D9 lesson: three launcher bugs shipped in one night
# because the driver was never exercised against the real entrypoint.  This runs
# FOUR REAL UNITS THROUGH `run_c1.sh` ITSELF — same script, same flags, same
# production knobs, only the unit list differs — and then ADJUDICATES FROM THE
# EMITTED FILES.  An exit code is not evidence: a launcher's exit-0 != a run that
# did anything (auto-memory: feedback_verify_numbers_before_reporting).
#
# The four units are, deterministically:
#   * the MOST EXPENSIVE `invasion` ply (max remaining plies — the worst case),
#   * the MEDIAN `farm_capture` ply (the primary stratum),
#   x the TOP TWO world indices of each ply's own base block.
# Taking them from the top of the real world range means the smoke units ARE run
# units: the resumable base pass finds them on disk and skips them, so the smoke
# costs nothing twice and its outcomes are part of the frozen design (they are
# also the last two worlds of a pre-registered index range, not a special draw).
set -u

REPO="${REPO:-/home/doctor/projects/carcassone}"
DIR="$REPO/measurement/c1_pricing_prep"
BOX="${BOX:?set BOX}"
W="${W:?set W}"
SHARE="${SHARE:?set SHARE}"
PY="${PY:-$REPO/.venv/bin/python}"
# ⚠️ BLOCK=smoke, not BLOCK=base with a suffix: run_c1.sh globs
# `units_${BOX}_${BLOCK}${SUFFIX}_*.txt`, and `units_local_base_*` would happily
# swallow a `units_local_base_smoke_*` file into the real base pass's chunk list.
# A distinct block label keeps the two globs disjoint. The WORLD indices the
# smoke uses are still the base block's own top two (see below), so the smoke
# units ARE base-pass units and the resumable run skips them.
BLOCK=smoke
SUFFIX=""
MAX_PROJECTED_H="${MAX_PROJECTED_H:-8}"

export PYTHONPATH="$REPO/src:$REPO/engine:$REPO/scripts"

echo "=== [0/4] static: the argparse contract against the real entrypoint"
"$PY" -m pytest "$DIR/selftest_c1.py" -q || { echo "SMOKE FAIL: selftest"; exit 1; }

echo "=== [1/4] pick the four smoke units (deterministic)"
"$PY" - "$DIR" <<'PYEOF'
import json, sys
from pathlib import Path
D = Path(sys.argv[1])
rows = [json.loads(l) for l in (D / "targets_c1.jsonl").open()]
drops = set()
p = D / "preflight_drops.txt"
if p.exists():
    for line in p.open():
        line = line.strip()
        if line and not line.startswith("#"):
            g, ply = line.split()[:2]
            drops.add((g, int(ply)))
rows = [r for r in rows if (r["game"], r["ply"]) not in drops]
inv = sorted((r for r in rows if r["stratum"] == "invasion"),
             key=lambda r: (-r["n_remaining_plies"], r["game"], r["ply"]))[0]
fc = sorted((r for r in rows if r["stratum"] == "farm_capture"),
            key=lambda r: (r["n_remaining_plies"], r["game"], r["ply"]))
fc = fc[len(fc) // 2]
lines = []
for r in (inv, fc):
    for w in (r["world_hi_base"] - 2, r["world_hi_base"] - 1):
        lines.append(f"{r['game']} {r['ply']} {w}")
prof = {r["profile"] for r in (inv, fc)}
assert len(prof) == 1, prof
(D / f"units_SMOKEPICK_{prof.pop()}.txt").write_text("\n".join(lines) + "\n")
(D / "SMOKE_UNITS.json").write_text(json.dumps(
    {"invasion": {k: inv[k] for k in ("game", "ply", "stratum", "k",
                                      "n_remaining_plies", "c1_action",
                                      "champ_action")},
     "farm_capture": {k: fc[k] for k in ("game", "ply", "stratum", "k",
                                         "n_remaining_plies", "c1_action",
                                         "champ_action")},
     "units": lines}, indent=1))
print("\n".join(lines))
PYEOF
# run_c1.sh globs units_${BOX}_${BLOCK}${SUFFIX}_*.txt — rename the picker's
# box-agnostic file into that shape for whichever box is smoking.
for F in "$DIR"/units_SMOKEPICK_*.txt; do
  [ -e "$F" ] || continue
  mv "$F" "${F/units_SMOKEPICK_/units_${BOX}_${BLOCK}${SUFFIX}_}"
done

echo "=== [2/4] run them through run_c1.sh at PRODUCTION knobs"
T0=$(date +%s)
BOX="$BOX" W="$W" SHARE="$SHARE" BLOCK="$BLOCK" SUFFIX="$SUFFIX" SMOKE=1 \
  "$DIR/run_c1.sh" || { echo "SMOKE FAIL: run_c1.sh returned non-zero"; exit 1; }
T1=$(date +%s)

echo "=== [3/4] adjudicate FROM THE EMITTED FILES"
"$PY" - "$DIR" "$DIR/out_$BOX" "$((T1 - T0))" "$MAX_PROJECTED_H" "$W" <<'PYEOF'
import json, sys, glob
from pathlib import Path
D, out, elapsed, max_h = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4])
# ⚠️ C1-D2. The smoke's 4 units are ONE chunk (CHUNK=4, `split -l 4` on a 4-line
# file), so `run_c1.sh` starts exactly ONE `continue_plies.py` — its own driver
# log prints `units=4 chunks=1`. The rate measured here is therefore a
# SINGLE-PROCESS rate, while the base pass runs W chunks CONCURRENTLY. Dividing
# the whole base block by a 1-process rate answers "how long on ONE CORE", not
# "on THIS BOX", and overstates the wall by ~W. Scale by W, de-rated by the
# repo's own measured fleet efficiency.
W = int(sys.argv[5])
#: Measured, not invented: phasegate DESIGN §6.4's realized two-box figure —
#: 36 nominal workers delivered 23.66 worker-s per wall-second = 66%. Held on
#: this box in A1/A2 (W30 per-worker cost ran ~17% above the laptop's W22).
PARALLEL_EFFICIENCY = 0.66
want = [tuple(l.split()) for l in
        json.loads((D / "SMOKE_UNITS.json").read_text())["units"]]
tg = {(r["game"], int(r["ply"])): r
      for r in (json.loads(l) for l in (D / "targets_c1.jsonl").open())}
rows = []
for g, p, w in want:
    f = out / f"unit_{g.replace('.json','')}_p{int(p):03d}_w{int(w)}.json"
    if not f.exists():
        print(f"SMOKE FAIL: no unit file emitted for {g} {p} {w}")
        sys.exit(1)
    rows.append(json.loads(f.read_text()))

fails = []
if len(rows) != 4:
    fails.append(f"emitted {len(rows)}/4 unit files")
for r in rows:
    t = tg[(r["game"], r["ply"])]
    if r["pair"]["status"] != "OK":
        fails.append(f"{r['game']} p{r['ply']} w{r['world']}: pair "
                     f"{r['pair']['status']} {r['pair'].get('reason')}")
    if int(r["played_action"]) != int(t["c1_action"]):
        fails.append(f"{r['game']} p{r['ply']}: arm_owner != c1_action")
    if int(r["counterfactual_action"]) != int(t["champ_action"]):
        fails.append(f"{r['game']} p{r['ply']}: arm_cf != champ_action")
    if int(r["world"]) < 16:
        fails.append(f"{r['game']} p{r['ply']}: world {r['world']} < 16")
    for a, v in (r.get("arms") or {}).items():
        if v.get("status") != "OK":
            fails.append(f"{r['game']} p{r['ply']} {a}: {v.get('status')}")
    if r["profile"] != "fixed_v1":
        fails.append(f"{r['game']}: profile {r['profile']}")

# Project the base-block ETA from the MEASURED continuation-ply rate of these
# units (never from unit count: the four units are deliberately atypical).
cp = sum(a["n_continuation_decisions"] for r in rows
         for a in (r.get("arms") or {}).values()
         if a.get("status") == "OK")
rate1 = cp / elapsed if elapsed else 0.0           # continuation-plies / s, ONE process
rate_box = rate1 * W * PARALLEL_EFFICIENCY         # ... and this box at its own W
base_cp = 323360
proj_h = (base_cp / rate_box / 3600) if rate_box else float("inf")
# ⛔ A RESUMED smoke is a VACUOUS pass: the units are already on disk, the runner
# skips them, `elapsed` collapses to a few seconds while `cp` still sums the
# emitted files, and the rate goes to infinity. Refuse to certify that.
vacuous = elapsed < 60
summary = {
    "n_units": len(rows), "elapsed_s": elapsed,
    "continuation_plies_executed": cp,
    "measured_rate_cont_plies_per_s_ONE_PROCESS": round(rate1, 3),
    "W_this_box": W, "parallel_efficiency_assumed": PARALLEL_EFFICIENCY,
    "measured_rate_cont_plies_per_s_this_box": round(rate_box, 2),
    "projected_base_block_hours_THIS_BOX_ALONE": round(proj_h, 2),
    "design_fleet_estimate_hours_BOTH_BOXES": 4.40,
    "max_projected_h_gate": max_h,
    "resumed_vacuous_rate": vacuous,
    "deltas_seen": [r["pair"].get("delta_pts_mover") for r in rows],
    "arm_s": [a.get("arm_s") for r in rows
              for a in (r.get("arms") or {}).values()],
    "fails": fails,
}
(D / "SMOKE_RESULT.json").write_text(json.dumps(summary, indent=1))
print(json.dumps(summary, indent=1))
if fails:
    print("SMOKE FAIL"); sys.exit(1)
if vacuous:
    print(f"SMOKE FAIL: elapsed {elapsed}s — the units were already on disk and "
          "were skipped, so the rate is vacuous. Move out_*/ aside and re-smoke "
          "if a fresh timing is wanted."); sys.exit(1)
if proj_h > max_h:
    print(f"SMOKE FAIL: projected {proj_h:.1f} h on this box alone exceeds the "
          f"{max_h} h gate — do not launch"); sys.exit(1)
print("SMOKE PASS")
PYEOF
RC=$?
echo "=== [4/4] smoke rc=$RC (artifacts: $DIR/SMOKE_UNITS.json $DIR/SMOKE_RESULT.json)"
exit $RC
