#!/usr/bin/env bash
# build_widening_corpus.sh — W6. TIE-ARBITER WIDENING corpus assembly driver
# (mining only; it computes NO strength / headroom / arbitration statistic).
#
# A PARAMETERISED COPY of the working `build_tiearb2_corpus.sh`, carrying all
# five of its phases — collect + band verify, census, the SHADOW-ROOT
# transposition/afterstate map, champ picks, build positions — plus the gates.
# DESIGN.md §4 deliberately has no runnable command block: the first draft's
# block, run literally, would have built the WRONG corpus and then crashed
# (REVIEW_R1 §15). THIS SCRIPT IS THE INVOCATION OF RECORD.
#
# What differs from the tiearb2 precedent, and why:
#   * TWO root-disjoint strata off ONE generation, carved by deck-seed sub-band
#     (S1 = band +0..+349, S2 = band +350..+849). That split IS the
#     disjointness mechanism; phase 7's W5 gate PROVES it.
#   * `--cap-j inf` — UNCAPPED. The `J > 4` rung reads the full deduped set
#     while the `B` rung reads the recorded seeded `J=4` subset off the SAME
#     CRN worlds (PLAN_J_gt_4 §3.2, §8).
#   * S2 is TWO-PASS: pass 1 `--allow-missing-champ-picks` (free, no playouts)
#     to learn `capped_at_4`, then <=3 capped rids per root are SELECTED
#     (outcome-blind: `capped_at_4` is knowable before any pricing), then pass 2
#     builds only those. `build_positions.py` has no `--include-rids`, so the
#     selection is expressed as the exclusion of its complement.
#   * The band verify is TWO INVOCATIONS when the blind top-up was exercised —
#     the base file against [135000000000,135000000849] carrying the >=850
#     floor, and CHAMP_GAMES_VERIFY_TOPUP.json against ITS OWN
#     [136000000000,136000000199] carrying only the increment. NEVER one
#     invocation over a widened band: that would report `n_out_of_band == 0`
#     for a seed lying in neither range (READ_RULE §2 `G-BAND`, R3 defect B1).
#   * Every output path is ABSOLUTE and under RUN/ (REVIEW_R1 §16).
#   * WORKERS.conf lives OUTSIDE the frozen prereg dir (DESIGN §9, item 9), so a
#     W retune is never a mid-run edit to a frozen file.
#
# ⚠️ THIS SCRIPT NEVER SELF-LAUNCHES. Invoke it explicitly, and only after the
#    generation run has finished (phase 1 hard-fails on a short corpus).
#
# Resumable: each phase is skipped when its own output already exists. Delete
# that output to force the phase to re-run. Phase 7 (the gates) ALWAYS runs.
#
# Usage:
#   scripts/tiletie/build_widening_corpus.sh            # all phases
#   scripts/tiletie/build_widening_corpus.sh 2 3        # only phases 2 and 3
#   WIDENING_MIN_GAMES=800 scripts/tiletie/build_widening_corpus.sh
#
# Detach it (house rule: anything > ~1 min):
#   setsid nohup scripts/tiletie/build_widening_corpus.sh \
#     > measurement/tiearb_widening_20260817/shared_run/logs/driver.out \
#     2>&1 < /dev/null & disown
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CAMPAIGN="$REPO/measurement/tiearb_widening_20260817"
RUN_DIR="$CAMPAIGN/shared_run"

# W10.1: the driver DIES without WORKERS.conf rather than inventing a count. It
# lives OUTSIDE the frozen shared_run/ (DESIGN §9 item 9), so a W retune is never
# an edit to a frozen file.
CONF="$CAMPAIGN/WORKERS.conf"
[ -f "$CONF" ] || { echo "[widening] FATAL: $CONF missing — W10.1 defines it." >&2
                    exit 2; }
# shellcheck disable=SC1091
. "$CONF"
for v in W_EVAL_LOCAL NICE SHARE_LOCAL RUN_ID SHARE_RUN_LOCAL; do
  [ -n "${!v:-}" ] || { echo "[widening] FATAL: $CONF does not set $v" >&2; exit 2; }
done
# ⚠️ TWO COUNT SETS. Every phase here is CPU-leaf mining (census, champ picks,
# build positions), i.e. the F7d EVAL row — NOT the GEN row. Borrowing
# W_GEN_LOCAL would over-subscribe the box; W10.1 exists so the two cannot be
# confused. Generation itself is W10's run_gen.sh, at W_GEN_*.
W="$W_EVAL_LOCAL"

PY="$REPO/.venv/bin/python"
LOGS="$RUN_DIR/logs"
CORPUS="$RUN_DIR/corpus"
SHADOW="$CORPUS/_shadow_repo"

GEN_DIR="$SHARE_RUN_LOCAL/gen"             # what W10's run_gen.sh produces
GEN_DIR_TOPUP="$SHARE_RUN_LOCAL/gen_topup" # the SEPARATE reserved-range invocation
CHAMP_GAMES="$CORPUS/champ_games_widening.jsonl"
CHAMP_GAMES_TOPUP="$CORPUS/champ_games_widening_topup.jsonl"

# --- corpus constants (DESIGN §3) -------------------------------------------- #
SEED_LO=135000000000
SEED_HI=135000000849
TOPUP_LO=136000000000
TOPUP_HI=136000000199
EXPECT_GAMES=850
MIN_GAMES="${WIDENING_MIN_GAMES:-$EXPECT_GAMES}"
SAMPLE_SEED=20260819
PROFILE=walled
CAP_J=inf                          # UNCAPPED — DESIGN §4's graded-knob table

S1_SEED_LO=$SEED_LO;               S1_SEED_HI=135000000349
S2_SEED_LO=135000000350;           S2_SEED_HI=$SEED_HI
S1_MAX_PER_GAME=4;                 S2_MAX_PER_GAME=3
S1_TARGET=1400                     # DESIGN §3: n1 = 1,350, supply at target 1,400
S2_MAX_CAPPED_PER_ROOT=3           # PLAN_J ask 4 — root-bootstrap SEs
S2_TARGET=0                        # 0 = take ALL remaining supply

BANKED_TILETIE="$REPO/measurement/tiletie_pricing_20260812/positions_pooled"
BANKED_TIEARB2="$REPO/measurement/tiearb2_20260816/corpus/positions"
BANKED_EXCLUDE="$REPO/measurement/tiearb2_20260816/corpus/EXCLUDE_RIDS_all.txt"

# Empty stand-ins that switch OFF the e4 and CL-070-bank census strata: this
# corpus is 100% `walled` self-play. `run_census.py` has no --no-e4 / --no-bank
# flag, so the supported knobs are `--limit-e4-games 0` / `--limit-bank 0`
# pointed at EMPTY inputs. (Real empty paths, not literal '': `Path('')` is the
# CWD, which would glob the repo root.)
EMPTY_E4="$CORPUS/_empty_e4"
EMPTY_BANK="$CORPUS/_empty_bank.jsonl"

mkdir -p "$LOGS" "$CORPUS" "$EMPTY_E4"
[ -f "$EMPTY_BANK" ] || : > "$EMPTY_BANK"

PHASES=("$@")
want() { [ ${#PHASES[@]} -eq 0 ] && return 0
         local p; for p in "${PHASES[@]}"; do [ "$p" = "$1" ] && return 0; done; return 1; }
say()  { echo "[widening][$(date '+%F %T')] $*"; }
skip() { say "PHASE $1 SKIP — $2 already exists (delete it to re-run)"; }

census_dir()    { echo "$CORPUS/census_$1"; }
positions_dir() { echo "$CORPUS/positions_$1"; }
picks_dir()     { echo "$CORPUS/champ_picks_$1"; }
map_path()      { echo "$(census_dir "$1")/afterstate_map_${PROFILE}.json"; }
games_path()    { echo "$CORPUS/champ_games_$1.jsonl"; }

# --------------------------------------------------------------------------- #
# PHASE 1 — COLLECT: merge the per-game action logs, verify the band, split     #
# --------------------------------------------------------------------------- #
if want 1; then
  if [ -f "$CHAMP_GAMES" ]; then
    skip 1 "$CHAMP_GAMES"
  else
    say "PHASE 1 COLLECT: $GEN_DIR -> $CHAMP_GAMES"
    nice -n "$NICE" "$PY" -u "$REPO/scripts/distill_flywheel/collect_action_logs.py" \
      --in "$GEN_DIR" --out "$CHAMP_GAMES" --verify 10 2>&1 | tee "$LOGS/p1_collect.log"
  fi

  # The band/count assertion ALWAYS runs — it is the gate on phase 1's output.
  # BASE file: its own range, and it alone carries the >= 850 floor.
  say "PHASE 1 VERIFY (BASE): band [$SEED_LO, $SEED_HI], >= $MIN_GAMES games"
  nice -n "$NICE" "$PY" -u "$REPO/scripts/tiletie/tiearb2_corpus_lib.py" \
    verify-champgames --path "$CHAMP_GAMES" \
    --seed-lo "$SEED_LO" --seed-hi "$SEED_HI" \
    --expect-games "$EXPECT_GAMES" --min-games "$MIN_GAMES" \
    --out "$CORPUS/CHAMP_GAMES_VERIFY.json" 2>&1 | tee "$LOGS/p1_verify.log"

  # TOP-UP: W10's `run_gen.sh --topup N` writes to a SEPARATE --out, so it is
  # collected into a SEPARATE champ-games file. That separation is what keeps
  # G-BAND's two-file form intact end-to-end: merging the reserved range into the
  # base file would put out-of-band seeds in front of the base verify and FAIL a
  # healthy run.
  if [ ! -f "$CHAMP_GAMES_TOPUP" ] \
     && [ -d "$GEN_DIR_TOPUP" ] \
     && [ -n "$(ls -A "$GEN_DIR_TOPUP" 2>/dev/null)" ]; then
    say "PHASE 1 COLLECT (TOP-UP): $GEN_DIR_TOPUP -> $CHAMP_GAMES_TOPUP"
    nice -n "$NICE" "$PY" -u "$REPO/scripts/distill_flywheel/collect_action_logs.py" \
      --in "$GEN_DIR_TOPUP" --out "$CHAMP_GAMES_TOPUP" --verify 10 2>&1 \
      | tee "$LOGS/p1_collect_topup.log"
  fi

  # TOP-UP file: a SECOND invocation against ITS OWN reserved range, carrying
  # only the increment. Holding it to the 850 floor would VOID every healthy run
  # that exercises the pre-licensed clause (<=200 games) — READ_RULE §2 G-BAND.
  if [ -f "$CHAMP_GAMES_TOPUP" ]; then
    say "PHASE 1 VERIFY (TOP-UP): band [$TOPUP_LO, $TOPUP_HI], increment only"
    nice -n "$NICE" "$PY" -u "$REPO/scripts/tiletie/tiearb2_corpus_lib.py" \
      verify-champgames --path "$CHAMP_GAMES_TOPUP" \
      --seed-lo "$TOPUP_LO" --seed-hi "$TOPUP_HI" \
      --min-games 1 \
      --out "$CORPUS/CHAMP_GAMES_VERIFY_TOPUP.json" 2>&1 \
      | tee "$LOGS/p1_verify_topup.log"
  else
    say "PHASE 1: no top-up file — the blind corpus top-up was NOT exercised"
  fi

  for S in s1 s2; do
    if [ "$S" = s1 ]; then LO=$S1_SEED_LO; HI=$S1_SEED_HI; else LO=$S2_SEED_LO; HI=$S2_SEED_HI; fi
    say "PHASE 1 SPLIT $S: deck-seed sub-band [$LO, $HI] -> $(games_path "$S")"
    nice -n "$NICE" "$PY" -u "$REPO/scripts/tiletie/tiearb2_corpus_lib.py" \
      split-champgames --path "$CHAMP_GAMES" --out "$(games_path "$S")" \
      --seed-lo "$LO" --seed-hi "$HI" 2>&1 | tee "$LOGS/p1_split_$S.log"
  done
fi

# --------------------------------------------------------------------------- #
# PHASE 2 — CENSUS: leaf top-2 tie structure, per stratum                       #
# --------------------------------------------------------------------------- #
if want 2; then
  for S in s1 s2; do
    CENSUS="$(census_dir "$S")"; GAMES="$(games_path "$S")"
    if [ "$S" = s1 ]; then MPG=$S1_MAX_PER_GAME; LO=$S1_SEED_LO; HI=$S1_SEED_HI
                     else MPG=$S2_MAX_PER_GAME; LO=$S2_SEED_LO; HI=$S2_SEED_HI; fi
    mkdir -p "$CENSUS"
    if [ -f "$CENSUS/rows.jsonl" ]; then skip "2($S)" "$CENSUS/rows.jsonl"; continue; fi
    # Realized game count -> the census ply target (MPG x games), so
    # --max-per-game can take up to MPG plies from EVERY game rather than
    # exhausting the budget on a prefix of them. Re-derived here (not carried
    # from phase 1) so phase 2 is runnable on its own.
    N_GAMES="$(nice -n "$NICE" "$PY" "$REPO/scripts/tiletie/tiearb2_corpus_lib.py" \
      verify-champgames --path "$GAMES" --seed-lo "$LO" --seed-hi "$HI" \
      --min-games 1 --print-n)"
    N_CHAMPGAMES=$(( N_GAMES * MPG ))
    say "PHASE 2 CENSUS $S: W=$W (eval row), games=$N_GAMES, --n-champgames $N_CHAMPGAMES"
    nice -n "$NICE" "$PY" -u "$REPO/scripts/tiletie/run_census.py" \
      --out-dir "$CENSUS" \
      --champgames-path "$GAMES" \
      --e4-dir "$EMPTY_E4" --limit-e4-games 0 \
      --bank-path "$EMPTY_BANK" --limit-bank 0 \
      --n-champgames "$N_CHAMPGAMES" \
      --max-per-game "$MPG" \
      --sample-seed "$SAMPLE_SEED" \
      --workers "$W" \
      --contention-note "tiearb widening corpus ($S); 100% walled self-play (e4 and CL-070 bank strata off via --limit-e4-games 0 / --limit-bank 0)" \
      2>&1 | tee "$LOGS/p2_census_$S.log"
  done
fi

# --------------------------------------------------------------------------- #
# PHASE 3 — TRANSPOSITION MAP via the SHADOW REPO ROOT                          #
# --------------------------------------------------------------------------- #
# transposition_census.py has NO --champ-games flag: it resolves self-play
# actions from two HARD-CODED paths, neither of which knows the 135e9 band. The
# script must not be edited, so it is invoked through a shadow repo root whose
# measurement/champ_action_logs/champ_games.jsonl is OUR corpus. WITHOUT THIS
# STEP build_positions silently globs the SPENT corpus's map (REVIEW_R1 §15).
if want 3; then
  say "PHASE 3a stage shadow repo root -> $SHADOW"
  ENTRY="$(nice -n "$NICE" "$PY" "$REPO/scripts/tiletie/tiearb2_corpus_lib.py" \
    stage-shadow --shadow-root "$SHADOW" --champ-games "$CHAMP_GAMES")"
  for S in s1 s2; do
    MAP="$(map_path "$S")"
    if [ -f "$MAP" ]; then skip "3($S)" "$MAP"; continue; fi
    say "PHASE 3 TRANSPOSITION MAP $S via $ENTRY"
    nice -n "$NICE" "$PY" -u "$ENTRY" \
      --rows "$(census_dir "$S")/rows.jsonl" \
      --profile "$PROFILE" --stratum selfplay \
      --out "$MAP" 2>&1 | tee "$LOGS/p3_transposition_$S.log"
  done
fi

# --------------------------------------------------------------------------- #
# PHASE 4 — CHAMP PICKS: the champion's actual move at each tied ply            #
# --------------------------------------------------------------------------- #
# WITHOUT --champ-picks the build raises KeyError on row 1 (REVIEW_R1 §15).
if want 4; then
  for S in s1 s2; do
    PICKS="$(picks_dir "$S")"; mkdir -p "$PICKS"
    if [ -f "$PICKS/champ_picks.jsonl.done" ]; then
      skip "4($S)" "$PICKS/champ_picks.jsonl.done"; continue; fi
    say "PHASE 4 CHAMP PICKS $S: W=$W (eval row) -> $PICKS"
    nice -n "$NICE" "$PY" -u "$REPO/scripts/tiletie/champ_picks.py" \
      --census-rows "$(census_dir "$S")/rows.jsonl" \
      --rules-profile "$PROFILE" \
      --champ-games "$(games_path "$S")" \
      --out "$PICKS/champ_picks.jsonl" \
      --workers "$W" --nice "$NICE" --resume 2>&1 \
      | tee "$LOGS/p4_champ_picks_$S.log"
    # champ_picks.py RESUMES into an existing jsonl, so that file existing does
    # NOT mean it is complete; a separate stamp marks the phase done.
    touch "$PICKS/champ_picks.jsonl.done"
  done
fi

# --------------------------------------------------------------------------- #
# PHASE 5 — BUILD POSITIONS                                                     #
# --------------------------------------------------------------------------- #
# ONE invocation shape, used by the S1 build, the S2 two-pass and the digest
# probe alike, so they can never drift apart in anything but their arguments.
# --afterstate-map is passed EXPLICITLY: its default globs the 2026-08-12 census
# dir, which would silently dedupe this corpus against the SPENT map.
# build_positions_into <out-dir> <stratum> <exclude-rids|-> <n> [extra flags...]
build_positions_into() {
  local out="$1" s="$2" excl="$3" n="$4"; shift 4
  local args=(--census-rows "$(census_dir "$s")/rows.jsonl"
              --out-dir "$out"
              --cap-j "$CAP_J"
              --n "$n"
              --afterstate-map "$(map_path "$s")"
              --sample-seed "$SAMPLE_SEED"
              --e4-dir "$EMPTY_E4"
              --champ-games "$(games_path "$s")")
  [ "$excl" != "-" ] && args+=(--exclude-rids "$excl")
  nice -n "$NICE" "$PY" -u "$REPO/scripts/tiletie/build_positions.py" \
    "${args[@]}" "$@"
}

if want 5; then
  # ---- 5a: the banked-corpus rid exclusion lists (defence in depth) -------- #
  EXCL_BANKED="$CORPUS/EXCLUDE_RIDS_banked.txt"
  if [ -f "$EXCL_BANKED" ]; then
    skip 5a "$EXCL_BANKED"
  else
    say "PHASE 5a banked rid exclusion lists -> $EXCL_BANKED"
    nice -n "$NICE" "$PY" "$REPO/scripts/tiletie/tiearb2_corpus_lib.py" \
      emit-exclude-rids --arms "$BANKED_TILETIE/ARMS.json" \
      --out "$CORPUS/_excl_tiletie0812.txt" 2>&1 | tee "$LOGS/p5a_excl_a.log"
    nice -n "$NICE" "$PY" "$REPO/scripts/tiletie/tiearb2_corpus_lib.py" \
      emit-exclude-rids --arms "$BANKED_TIEARB2/ARMS.json" \
      --out "$CORPUS/_excl_tiearb2_0816.txt" 2>&1 | tee "$LOGS/p5a_excl_b.log"
    { printf '# widening COMBINED banked rid exclusion list =\n'
      printf '#   tiletie_pricing_20260812 + tiearb2_20260816 +\n'
      printf '#   tiearb2_20260816/EXCLUDE_RIDS_all.txt\n'
      printf '# EXPECTED effect: n_removed_from_supply == 0 (the bands are\n'
      printf '# root-disjoint by construction; this is defence in depth).\n'
      cat "$CORPUS/_excl_tiletie0812.txt" "$CORPUS/_excl_tiearb2_0816.txt" \
          "$BANKED_EXCLUDE"
    } > "$EXCL_BANKED"
  fi

  # ---- 5b: S1, one pass, all remaining supply up to the target ------------- #
  P_S1="$(positions_dir s1)"
  if [ -f "$P_S1/POSITIONS_PLAN.json" ]; then
    skip "5b(s1)" "$P_S1/POSITIONS_PLAN.json"
  else
    mkdir -p "$P_S1"
    say "PHASE 5b BUILD POSITIONS s1: UNCAPPED, target $S1_TARGET -> $P_S1"
    build_positions_into "$P_S1" s1 "$EXCL_BANKED" "$S1_TARGET" \
      --champ-picks "$(picks_dir s1)/champ_picks.jsonl" 2>&1 \
      | tee "$LOGS/p5b_build_s1.log"
  fi

  # ---- 5c: S2, TWO-PASS ---------------------------------------------------- #
  # pass 1 is FREE (no playouts) and exists only to learn `capped_at_4`; the
  # <=3-per-root selection is therefore outcome-blind BY CONSTRUCTION.
  P_S2="$(positions_dir s2)"; P_S2_PASS1="$CORPUS/_positions_s2_pass1"
  EXCL_S2="$CORPUS/EXCLUDE_RIDS_s2_pass2.txt"
  if [ -f "$P_S2/POSITIONS_PLAN.json" ]; then
    skip "5c(s2)" "$P_S2/POSITIONS_PLAN.json"
  else
    if [ ! -f "$EXCL_S2" ]; then
      say "PHASE 5c PASS 1 (s2, --allow-missing-champ-picks, no playouts)"
      rm -rf "$P_S2_PASS1"; mkdir -p "$P_S2_PASS1"
      build_positions_into "$P_S2_PASS1" s2 "$EXCL_BANKED" 0 \
        --allow-missing-champ-picks 2>&1 | tee "$LOGS/p5c_s2_pass1.log"

      say "PHASE 5c SELECT <=$S2_MAX_CAPPED_PER_ROOT capped rids per root"
      nice -n "$NICE" "$PY" "$REPO/scripts/tiletie/tiearb2_corpus_lib.py" \
        select-capped --arms "$P_S2_PASS1/ARMS.json" \
        --max-per-root "$S2_MAX_CAPPED_PER_ROOT" --seed "$SAMPLE_SEED" \
        --out-exclude "$CORPUS/_excl_s2_selection.txt" \
        --out-report "$RUN_DIR/S2_SELECTION.json" 2>&1 \
        | tee "$LOGS/p5c_s2_select.log"
      { printf '# S2 pass-2 exclusion list = banked rids + every pass-1 rid NOT\n'
        printf '# selected as one of the <=%s capped plies of its root.\n' \
               "$S2_MAX_CAPPED_PER_ROOT"
        cat "$EXCL_BANKED" "$CORPUS/_excl_s2_selection.txt"
      } > "$EXCL_S2"
    fi
    mkdir -p "$P_S2"
    say "PHASE 5c PASS 2 (s2, selected rids only, with champ picks) -> $P_S2"
    build_positions_into "$P_S2" s2 "$EXCL_S2" "$S2_TARGET" \
      --champ-picks "$(picks_dir s2)/champ_picks.jsonl" 2>&1 \
      | tee "$LOGS/p5c_s2_pass2.log"
  fi

  # ---- 5d: the plan assertions -------------------------------------------- #
  # run_tiletie.py's preflight REFUSES a plan whose afterstate_dedupe.applied is
  # not true — fail here, loudly, rather than at launch time.
  for S in s1 s2; do
    nice -n "$NICE" "$PY" - "$(positions_dir "$S")/POSITIONS_PLAN.json" "$S" \
      <<'PYEOF' 2>&1 | tee "$LOGS/p5d_plan_assert_$S.log"
import json, sys
plan = json.loads(open(sys.argv[1]).read()); s = sys.argv[2]
ded, exc = plan["afterstate_dedupe"], plan["exclude_rids"]
print(f"[{s}] afterstate_dedupe.applied = {ded['applied']}")
print(f"[{s}] uncapped = {plan.get('uncapped')} | cap_j = {plan.get('cap_j')}")
print(f"[{s}] n_positions = {plan['n_positions']} | "
      f"n_positions_capped_at_4 = {plan.get('n_positions_capped_at_4')}")
print(f"[{s}] exclude_rids.n_removed_from_supply = {exc['n_removed_from_supply']}")
assert ded["applied"] is True, "afterstate_dedupe NOT applied — run_tiletie will refuse"
assert plan.get("uncapped") is True and plan.get("cap_j") is None, (
    "the widening corpus MUST be UNCAPPED (--cap-j inf): G-UNCAPPED reads "
    "POSITIONS_PLAN.json::{uncapped,cap_j} and the J>4 rung needs the full "
    "deduped set")
PYEOF
  done
fi

# --------------------------------------------------------------------------- #
# PHASE 6 — leg-manifest COPY-BACK from the share                               #
# --------------------------------------------------------------------------- #
# READ_RULE reads the per-leg addresses under RUN/, not the share (REVIEW_R1
# §16). Only the `tier1-greedy` legs are ADDRESSED by any gate — `resolved_config`
# and `preflight.seeds` exist only on tier1_rust_leg manifests — but both judges'
# manifests are copied so the record is complete (DESIGN §8 builder delta 4).
if want 6; then
  for S in s1 s2; do
    SRC="$SHARE_RUN_LOCAL/$S"
    [ -d "$SRC" ] || { say "PHASE 6 $S: no leg output at $SRC yet — skipping"; continue; }
    say "PHASE 6 COPY-BACK $S: $SRC -> $RUN_DIR/legs/$S"
    while IFS= read -r -d '' m; do
      rel="${m#"$SRC"/}"
      dst="$RUN_DIR/legs/$S/$rel"
      mkdir -p "$(dirname "$dst")"
      cp -f "$m" "$dst"
    done < <(find "$SRC" -name manifest.json -print0)
  done
fi

# --------------------------------------------------------------------------- #
# PHASE 7 — THE GATES (always run): W5's merged G-DISJOINT and G-DRAW            #
# --------------------------------------------------------------------------- #
if want 7; then
  say "PHASE 7 G-DISJOINT (merged, five comparisons + strata_root_overlap)"
  nice -n "$NICE" "$PY" -u "$REPO/scripts/tiletie/gate_disjoint.py" --merged \
    --s1-dir "$(positions_dir s1)" --s2-dir "$(positions_dir s2)" \
    --ref "tiletie0812=$BANKED_TILETIE" \
    --ref "tiearb2_0816=$BANKED_TIEARB2" \
    --exclude-rids "$BANKED_EXCLUDE" \
    --out "$RUN_DIR/GATE_DISJOINT.json" 2>&1 | tee "$LOGS/p7_gate_disjoint.log"

  say "PHASE 7 G-DRAW (the recorded J=4 subset reproduces this repo's own draw)"
  nice -n "$NICE" "$PY" -u "$REPO/scripts/tiletie/gate_draw.py" \
    --arms "$(positions_dir s1)/ARMS.json" \
    --arms "$(positions_dir s2)/ARMS.json" \
    --out "$RUN_DIR/GATE_DRAW.json" 2>&1 | tee "$LOGS/p7_gate_draw.log"
fi

say "DONE"
