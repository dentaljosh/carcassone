#!/usr/bin/env bash
# build_tiearb2_corpus.sh — tiearb2_20260816 CORPUS ASSEMBLY driver (mining only).
#
# Assembles a FRESH tied-tile-ply corpus from the 850 champion self-play games of
# deck-seed band 28100000000..28100000849, then PROVES it disjoint from the spent
# 2026-08-12 corpus. It computes NO strength / headroom / arbitration statistic —
# every phase here is corpus material, not a measurement.
#
# ⚠️ THIS SCRIPT NEVER SELF-LAUNCHES. Invoke it explicitly, and only after the
#    generation run has finished (phase 1 hard-fails on a short corpus).
#
# Resumable: each phase is skipped when its own output already exists. Delete
# that output to force the phase to re-run. Phase 6 (the gate) ALWAYS runs.
#
# Usage:
#   scripts/tiletie/build_tiearb2_corpus.sh              # all phases
#   scripts/tiletie/build_tiearb2_corpus.sh 2 3          # only phases 2 and 3
#   TIEARB2_MIN_GAMES=800 scripts/tiletie/build_tiearb2_corpus.sh
#
# Detach it (house rule: anything > ~1 min):
#   setsid nohup scripts/tiletie/build_tiearb2_corpus.sh \
#     > measurement/tiearb2_20260816/logs/driver.out 2>&1 < /dev/null & disown
#
# Full phase-by-phase rationale + the verified flag list:
#   measurement/tiearb2_20260816/CORPUS_PIPELINE.md
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_DIR="$REPO/measurement/tiearb2_20260816"

# shellcheck disable=SC1091
. "$RUN_DIR/WORKERS.conf"          # W_LOCAL / NICE / SHARE_LOCAL / RUN_ID — the
                                   # ONLY place worker counts live. Never hard-code.

PY="$REPO/.venv/bin/python"
LOGS="$RUN_DIR/logs"
CORPUS="$RUN_DIR/corpus"
CENSUS="$CORPUS/census"
POSITIONS="$CORPUS/positions"
PICKS="$CORPUS/champ_picks"
SHADOW="$CORPUS/_shadow_repo"

GEN_DIR="$SHARE_LOCAL/$RUN_ID/gen"
CHAMP_GAMES="$CORPUS/champ_games_tiearb2.jsonl"
EXCLUDE_RIDS="$CORPUS/EXCLUDE_RIDS_spent733.txt"
EXCLUDE_DIGEST="$CORPUS/EXCLUDE_RIDS_digest.txt"
EXCLUDE_ALL="$CORPUS/EXCLUDE_RIDS_all.txt"
DIGEST_REPORT="$RUN_DIR/DIGEST_EXCLUSIONS.json"
PROBE="$CORPUS/_probe_positions"
SPENT_POOLED="$REPO/measurement/tiletie_pricing_20260812/positions_pooled"
AFTERSTATE_MAP="$CENSUS/afterstate_map_walled.json"

# --- corpus constants (see CORPUS_PIPELINE.md) -------------------------------
SEED_LO=28100000000
SEED_HI=28100000849
EXPECT_GAMES=850
MIN_GAMES="${TIEARB2_MIN_GAMES:-$EXPECT_GAMES}"
MAX_PER_GAME=4
SAMPLE_SEED=20260816
CAP_J=4
TARGET_POSITIONS=1400
PROFILE=walled

# Empty stand-ins that switch OFF the e4 and CL-070-bank census strata: this
# corpus is 100% `walled` self-play. `run_census.py` has no --no-e4 / --no-bank
# flag, so the supported knobs are `--limit-e4-games 0` / `--limit-bank 0`
# (documented "smoke-test" knobs, exact at 0) pointed at empty inputs.
EMPTY_E4="$CORPUS/_empty_e4"
EMPTY_BANK="$CORPUS/_empty_bank.jsonl"

mkdir -p "$LOGS" "$CORPUS" "$CENSUS" "$POSITIONS" "$PICKS" "$EMPTY_E4"
[ -f "$EMPTY_BANK" ] || : > "$EMPTY_BANK"

PHASES=("$@")
want() {                                   # want <n> -> run phase n?
  [ ${#PHASES[@]} -eq 0 ] && return 0
  local p; for p in "${PHASES[@]}"; do [ "$p" = "$1" ] && return 0; done; return 1
}
say() { echo "[tiearb2][$(date '+%F %T')] $*"; }
skip() { say "PHASE $1 SKIP — $2 already exists (delete it to re-run)"; }

# --------------------------------------------------------------------------- #
# PHASE 1 — COLLECT: merge the per-game action logs into one jsonl, verify band #
# --------------------------------------------------------------------------- #
if want 1; then
  if [ -f "$CHAMP_GAMES" ]; then
    skip 1 "$CHAMP_GAMES"
  else
    say "PHASE 1 COLLECT: $GEN_DIR -> $CHAMP_GAMES"
    nice -n "$NICE" "$PY" -u "$REPO/scripts/distill_flywheel/collect_action_logs.py" \
      --in "$GEN_DIR" \
      --out "$CHAMP_GAMES" \
      --verify 10 2>&1 | tee "$LOGS/p1_collect.log"
  fi
  # The band/count assertion ALWAYS runs (it is the gate on phase 1's output,
  # not a by-product of the merge) and is what phases 2+ read the realized
  # game count from.
  say "PHASE 1 VERIFY: band [$SEED_LO, $SEED_HI], >= $MIN_GAMES games"
  nice -n "$NICE" "$PY" -u "$REPO/scripts/tiletie/tiearb2_corpus_lib.py" \
    verify-champgames --path "$CHAMP_GAMES" \
    --seed-lo "$SEED_LO" --seed-hi "$SEED_HI" \
    --expect-games "$EXPECT_GAMES" --min-games "$MIN_GAMES" \
    --out "$CORPUS/CHAMP_GAMES_VERIFY.json" 2>&1 | tee "$LOGS/p1_verify.log"
fi

# --------------------------------------------------------------------------- #
# PHASE 2 — CENSUS: leaf top-2 tie structure over the NEW champ games only      #
# --------------------------------------------------------------------------- #
if want 2; then
  if [ -f "$CENSUS/rows.jsonl" ]; then
    skip 2 "$CENSUS/rows.jsonl"
  else
    # Realized game count -> the census ply target (4 x games, so
    # --max-per-game 4 can take up to 4 plies from EVERY game rather than
    # exhausting the budget on a prefix of them). Re-derived here (not carried
    # from phase 1) so phase 2 is runnable on its own.
    N_GAMES="$(nice -n "$NICE" "$PY" "$REPO/scripts/tiletie/tiearb2_corpus_lib.py" \
      verify-champgames --path "$CHAMP_GAMES" --seed-lo "$SEED_LO" --seed-hi "$SEED_HI" \
      --expect-games "$EXPECT_GAMES" --min-games "$MIN_GAMES" --print-n)"
    N_CHAMPGAMES=$(( N_GAMES * MAX_PER_GAME ))
    say "PHASE 2 CENSUS: W=$W_LOCAL, realized games=$N_GAMES, --n-champgames $N_CHAMPGAMES -> $CENSUS"
    nice -n "$NICE" "$PY" -u "$REPO/scripts/tiletie/run_census.py" \
      --out-dir "$CENSUS" \
      --champgames-path "$CHAMP_GAMES" \
      --e4-dir "$EMPTY_E4" --limit-e4-games 0 \
      --bank-path "$EMPTY_BANK" --limit-bank 0 \
      --n-champgames "$N_CHAMPGAMES" \
      --max-per-game "$MAX_PER_GAME" \
      --sample-seed "$SAMPLE_SEED" \
      --workers "$W_LOCAL" \
      --contention-note "tiearb2 corpus assembly; 100% walled self-play (e4 and CL-070 bank strata switched off via --limit-e4-games 0 / --limit-bank 0)" \
      2>&1 | tee "$LOGS/p2_census.log"
  fi
fi

# --------------------------------------------------------------------------- #
# PHASE 3 — TRANSPOSITION MAP: afterstate_map_walled.json for build_positions   #
# --------------------------------------------------------------------------- #
if want 3; then
  if [ -f "$AFTERSTATE_MAP" ]; then
    skip 3 "$AFTERSTATE_MAP"
  else
    # transposition_census.py has NO --champ-games flag: it resolves self-play
    # actions from two hard-coded paths, neither of which knows the 281000000xx
    # band. The script must not be edited (live generation), so it is invoked
    # through a shadow repo root whose measurement/champ_action_logs/
    # champ_games.jsonl is OUR corpus. See tiearb2_corpus_lib.stage_shadow.
    say "PHASE 3a stage shadow repo root -> $SHADOW"
    ENTRY="$(nice -n "$NICE" "$PY" "$REPO/scripts/tiletie/tiearb2_corpus_lib.py" \
      stage-shadow --shadow-root "$SHADOW" --champ-games "$CHAMP_GAMES")"
    say "PHASE 3 TRANSPOSITION MAP via $ENTRY"
    nice -n "$NICE" "$PY" -u "$ENTRY" \
      --rows "$CENSUS/rows.jsonl" \
      --profile "$PROFILE" \
      --stratum selfplay \
      --out "$AFTERSTATE_MAP" 2>&1 | tee "$LOGS/p3_transposition.log"
  fi
fi

# --------------------------------------------------------------------------- #
# PHASE 4 — CHAMP PICKS: the k8x1376 champion's actual move at each tied ply    #
# --------------------------------------------------------------------------- #
if want 4; then
  if [ -f "$PICKS/champ_picks.jsonl.done" ]; then
    skip 4 "$PICKS/champ_picks.jsonl.done"
  else
    say "PHASE 4 CHAMP PICKS: W=$W_LOCAL (~1.409 worker-s/position) -> $PICKS"
    nice -n "$NICE" "$PY" -u "$REPO/scripts/tiletie/champ_picks.py" \
      --census-rows "$CENSUS/rows.jsonl" \
      --rules-profile "$PROFILE" \
      --champ-games "$CHAMP_GAMES" \
      --out "$PICKS/champ_picks.jsonl" \
      --workers "$W_LOCAL" \
      --nice "$NICE" \
      --resume 2>&1 | tee "$LOGS/p4_champ_picks.log"
    # champ_picks.py resumes into an existing jsonl, so that file existing does
    # NOT mean it is complete; a separate stamp marks the phase done.
    touch "$PICKS/champ_picks.jsonl.done"
  fi
fi

# --------------------------------------------------------------------------- #
# PHASE 5 — BUILD POSITIONS: the corpus plan, deduped and rid-excluded          #
# --------------------------------------------------------------------------- #
# build_positions <out-dir> <exclude-rids-file> — the ONE invocation shape, used
# by the phase-5b PROBE build and by the real phase-5 build alike, so the two can
# never drift apart in anything but the exclusion list.
#
# --afterstate-map is passed EXPLICITLY: its default globs the 2026-08-12 census
# dir, which would silently dedupe this corpus against the SPENT map.
build_positions_into() {
  nice -n "$NICE" "$PY" -u "$REPO/scripts/tiletie/build_positions.py" \
    --census-rows "$CENSUS/rows.jsonl" \
    --out-dir "$1" \
    --champ-picks "$PICKS/champ_picks.jsonl" \
    --cap-j "$CAP_J" \
    --n "$TARGET_POSITIONS" \
    --afterstate-map "$AFTERSTATE_MAP" \
    --exclude-rids "$2" \
    --sample-seed "$SAMPLE_SEED" \
    --e4-dir "$EMPTY_E4" \
    --champ-games "$CHAMP_GAMES"
}

if want 5; then
  if [ -f "$POSITIONS/POSITIONS_PLAN.json" ]; then
    skip 5 "$POSITIONS/POSITIONS_PLAN.json"
  else
    say "PHASE 5a emit spent-corpus rid exclusion list -> $EXCLUDE_RIDS"
    nice -n "$NICE" "$PY" "$REPO/scripts/tiletie/tiearb2_corpus_lib.py" \
      emit-exclude-rids --arms "$SPENT_POOLED/ARMS.json" --out "$EXCLUDE_RIDS" \
      2>&1 | tee "$LOGS/p5_exclude_rids.log"

    # ----------------------------------------------------------------------- #
    # PHASE 5b — the layer-(c) BOARD-DIGEST exclusion list                     #
    # ----------------------------------------------------------------------- #
    # Layers (a) root_id and (b) rid are guaranteed by the fresh deck-seed band.
    # Layer (c) — sha256(checksum), the BOARD — is NOT: Carcassonne boards
    # TRANSPOSE, so two different games can reach a bit-identical early board.
    # That is intrinsic, not band contamination, so the fix is EXCLUSION, not
    # regeneration (see CORPUS_PIPELINE.md phase 5b).
    #
    # The list can only be computed from a REALIZED board census, so it comes
    # from a throwaway PROBE build made with the SPENT-RID LIST ALONE. Deriving
    # it from the final corpus instead would be circular: that corpus already has
    # the exclusions applied, so the tool would find nothing, emit an empty list,
    # and a rebuild would restore the offending positions. The whole step is
    # keyed on EXCLUDE_ALL, so the pipeline is reproducible from scratch.
    if [ -f "$EXCLUDE_ALL" ]; then
      skip 5b "$EXCLUDE_ALL"
    else
      say "PHASE 5b PROBE BUILD (spent rids only, throwaway) -> $PROBE"
      rm -rf "$PROBE"; mkdir -p "$PROBE"
      build_positions_into "$PROBE" "$EXCLUDE_RIDS" 2>&1 \
        | tee "$LOGS/p5b_probe_build.log"

      say "PHASE 5b DIGEST EXCLUSIONS: $PROBE -> $EXCLUDE_DIGEST"
      nice -n "$NICE" "$PY" -u "$REPO/scripts/tiletie/emit_digest_exclusions.py" \
        --new-dir "$PROBE" \
        --spent-dir "$SPENT_POOLED" \
        --out "$EXCLUDE_DIGEST" \
        --report "$DIGEST_REPORT" 2>&1 | tee "$LOGS/p5b_digest_exclusions.log"

      say "PHASE 5b CONCAT: spent733 + digest -> $EXCLUDE_ALL"
      { printf '# tiearb2 COMBINED rid exclusion list = spent-corpus rids +\n'
        printf '# layer-(c) board-digest exclusions. Both source files carry\n'
        printf '# their own headers below; build_positions.py strips comments.\n'
        cat "$EXCLUDE_RIDS" "$EXCLUDE_DIGEST"
      } > "$EXCLUDE_ALL"
    fi

    say "PHASE 5 BUILD POSITIONS: cap-j $CAP_J, target $TARGET_POSITIONS -> $POSITIONS"
    build_positions_into "$POSITIONS" "$EXCLUDE_ALL" 2>&1 \
      | tee "$LOGS/p5_build_positions.log"

    # run_tiletie.py's preflight REFUSES a plan whose afterstate_dedupe.applied
    # is not true — fail here, loudly, rather than at launch time. The probe plan
    # and the digest report are cross-checked against the final plan so the
    # arithmetic (probe supply - digest exclusions == final supply) is proved,
    # not assumed.
    nice -n "$NICE" "$PY" - "$POSITIONS/POSITIONS_PLAN.json" \
      "$PROBE/POSITIONS_PLAN.json" "$DIGEST_REPORT" \
      <<'PYEOF' 2>&1 | tee "$LOGS/p5_plan_assert.log"
import json, os, sys
plan = json.loads(open(sys.argv[1]).read())
ded, exc = plan["afterstate_dedupe"], plan["exclude_rids"]
print(f"[plan] afterstate_dedupe.applied = {ded['applied']}")
print(f"[plan] n_dropped_all_transposition = {ded['n_dropped_all_transposition']}")
print(f"[plan] exclude_rids.n_requested = {exc['n_requested']}")
print(f"[plan] exclude_rids.n_removed_from_supply = {exc['n_removed_from_supply']}")
print(f"[plan] n_supply_after_exclusion = {exc['n_supply_after_exclusion']}")
print(f"[plan] n_positions = {plan['n_positions']}")
assert ded["applied"] is True, "afterstate_dedupe NOT applied — run_tiletie will refuse"

# Supply < --n, so stratified_sample takes ALL of it: n_positions must equal the
# post-exclusion supply exactly. Any gap means a seeded subsample crept in.
assert plan["n_positions"] == exc["n_supply_after_exclusion"], (
    f"n_positions {plan['n_positions']} != supply after exclusion "
    f"{exc['n_supply_after_exclusion']} — the sampler subsampled; the corpus is "
    f"not 'all remaining supply'")

if os.path.exists(sys.argv[2]) and os.path.exists(sys.argv[3]):
    probe = json.loads(open(sys.argv[2]).read())["exclude_rids"]
    dig = json.loads(open(sys.argv[3]).read())
    print(f"[probe] n_removed_from_supply = {probe['n_removed_from_supply']} "
          f"| supply = {probe['n_supply_after_exclusion']}")
    print(f"[digest] n_spent_overlap = {dig['n_spent_overlap']} | "
          f"n_internal_dupes = {dig['n_internal_dupes']} | "
          f"n_total_excluded = {dig['n_total_excluded']}")
    # The spent rid list alone must remove NOTHING: the two corpora are
    # root-disjoint by deck-seed band, and it is defence in depth.
    assert probe["n_removed_from_supply"] == 0, (
        f"{probe['n_removed_from_supply']} position(s) removed by the SPENT RID "
        f"list — the bands were supposed to be disjoint. STOP and investigate.")
    assert (exc["n_supply_after_exclusion"]
            == probe["n_supply_after_exclusion"] - dig["n_total_excluded"]), (
        "supply arithmetic does not close: probe supply "
        f"{probe['n_supply_after_exclusion']} - {dig['n_total_excluded']} digest "
        f"exclusions != {exc['n_supply_after_exclusion']}")
    print(f"[plan] OK: {probe['n_supply_after_exclusion']} probe supply "
          f"- {dig['n_total_excluded']} digest exclusion(s) "
          f"= {exc['n_supply_after_exclusion']} positions")
else:
    print("[plan] NOTE: probe plan / digest report absent (phase 5b was skipped "
          "on a pre-existing EXCLUDE_RIDS_all.txt) — cross-check not performed.",
          file=sys.stderr)
PYEOF
  fi
fi

# --------------------------------------------------------------------------- #
# PHASE 6 — G-DISJOINT: three-layer proof vs the spent 733-position corpus      #
# --------------------------------------------------------------------------- #
if want 6; then
  say "PHASE 6 G-DISJOINT gate"
  nice -n "$NICE" "$PY" -u "$REPO/scripts/tiletie/gate_disjoint.py" \
    --spent-dir "$SPENT_POOLED" \
    --new-dir "$POSITIONS" \
    --out "$RUN_DIR/DISJOINTNESS.json" 2>&1 | tee "$LOGS/p6_gate_disjoint.log"
fi

say "DONE"
