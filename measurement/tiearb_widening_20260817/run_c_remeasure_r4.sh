#!/usr/bin/env bash
# run_c_remeasure_r4.sh — the R4-8b step-1 `c_IF` remeasure (the 4b-pre judge smokes).
#
# R4-8b makes this the FIRST step: it settles the 1.91x c_IF gap (committed 2.35
# vs the idle-box smoke-indicated 1.2313) BEFORE the owner picks a floor, so the
# floor is chosen against a real price rather than a guessed one.
#
# FOUR invocations, per the CARRIED §7.1: {S1 --m 128, S2 --m 32} x {clair-puct,
# tier1-greedy}, --smoke-n 20, --arb-backend rust, --only-profiles walled, each
# writing its OWN --smoke-manifest (one shared path would have the second smoke
# overwrite the first).
#
# ⚠️ RUN SEQUENTIALLY, ON AN IDLE BOX. A timing bench is an EXCLUSIVE TENANT
# (feedback_no_agent_compute_beside_eval) — four smokes in parallel would measure
# contention, not cost.
#
# ⚠️ §0.O UNDER-SCOPES ITS OWN RULE — found the hard way on the first launch,
# which was killed mid-preflight. §0.O names `--positions-dir` as the flag that
# must always be explicit. In fact SIX of run_tiletie's path defaults resolve
# into the SPENT `measurement/tiletie_pricing_20260812/` run:
#
#   --positions-dir  PRICING_ROOT/positions            (the §0.O trap)
#   --logs-dir       PRICING_ROOT/logs
#   --gate-out       PRICING_ROOT/GATE_BACKEND_RECHECK.json   <-- GIT-TRACKED
#   --manifest-out   PRICING_ROOT/RUN_MANIFEST.json           <-- GIT-TRACKED
#   --smoke-manifest PRICING_ROOT/SMOKE_MANIFEST.json         <-- GIT-TRACKED
#   --out-root       /mnt/c/carc-shared/tiletie_pricing_20260812  (share side)
#
# `--gate-out` is the dangerous one: run_tiletie's PREFLIGHT runs
# gate_oracle_pilot_backend and writes that file unprompted, so merely INVOKING
# the smoke mutates a closed run's tracked artifact — the exact thing REVIEW_R1
# §2/§20 forbids ("nothing this campaign runs may write into ... any other closed
# run's directory"). ALL SIX ARE SET EXPLICITLY BELOW.
#
# These price the EXISTING base-corpus (band 135e9) positions, which is the only
# corpus that exists at this point in the binding order. c is a per-playout cost;
# no outcome statistic is computed, read or stored here.
#
# READ: ...::c_worker_secs_per_playout  (the Sigma elapsed_secs/playout figure of
# record) — NOT worker_secs_per_playout, which is the wall x W figure inflated
# ~1.9x that the emitter's own banner says not to cost from.
set -uo pipefail

REPO=/home/doctor/projects/carcassone
CAMPAIGN="$REPO/measurement/tiearb_widening_20260817"
. "$CAMPAIGN/WORKERS.conf"

PY="$REPO/.venv/bin/python"
OUT="$CAMPAIGN/c_remeasure_r4"          # NOT shared_run/ — the R3 pair is frozen,
                                        # and shared_run_r4/ is not committed yet.
LOGS="$OUT/logs"
SHARE=/mnt/c/carc-shared/tiearb_widening_20260817/c_remeasure_r4   # allow-path (local box only)
W="$W_EVAL_LOCAL"
mkdir -p "$OUT" "$LOGS" "$SHARE"

run_one() {
  local stratum="$1" m="$2" judge="$3"
  local pdir="$REPO/measurement/tiearb_widening_20260817/shared_run/corpus/positions_${stratum,,}"
  local man="$OUT/SMOKE_MANIFEST_${stratum}_${judge}.json"
  echo "=== [$(date -Is)] SMOKE $stratum m=$m judge=$judge W=$W ==="
  nice -n "$NICE" "$PY" -u "$REPO/scripts/tiletie/run_tiletie.py" \
    --smoke --smoke-n 20 \
    --smoke-judge "$judge" \
    --m "$m" \
    --arb-backend rust --arb-legal-mask-cache \
    --only-profiles walled --smoke-profile walled \
    --positions-dir "$pdir" \
    --out-root "$SHARE" \
    --logs-dir "$LOGS" \
    --smoke-manifest "$man" \
    --gate-out "$OUT/GATE_BACKEND_RECHECK_${stratum}_${judge}.json" \
    --manifest-out "$OUT/RUN_MANIFEST_UNUSED_${stratum}_${judge}.json" \
    --workers "$W" \
    2>&1 | tail -25
  echo "--- rc=${PIPESTATUS[0]} manifest=$man"
}

# ARB legs first: they are ~13x cheaper, so a config error surfaces in a minute
# rather than after a 16-minute IF leg.
run_one S1 128 tier1-greedy
run_one S2  32 tier1-greedy
run_one S1 128 clair-puct
run_one S2  32 clair-puct

echo "=== [$(date -Is)] ALL FOUR SMOKES DONE ==="
touch "$OUT/DONE_C_REMEASURE"
