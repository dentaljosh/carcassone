#!/usr/bin/env bash
# =============================================================================
# run_cells.sh -- D2-R4 RUNG-COMPRESSION CELL LAUNCHER (ATTEMPT 4).
#
# THE PRE-REGISTERED RESPIN of measurement/track_d2r3_prep, which adjudicated
# U-UNREADABLE on ONE gate -- G-TIMING -- at its BURN-IN, 80 games into 800,
# realized ratio 1.5491 against a frozen ceiling of 1.20. Attempt 2 had missed
# the same interval's FLOOR at 0.8382. Both voids are cost-calibration voids and
# neither is an instrument defect: attempt 3's gate fired exactly as designed and
# cost ~3.7 core-h instead of ~44.
#
# ⭐ ATTEMPT 4 CHANGES EXACTLY TWO THINGS: THE PROBE BUDGET AND THE BAND.
# Attempt 3's budget was derived against attempt 2's cell-realized costs, and
# those costs were CO-TENANT-INFLATED (~1.8x on the python rung) by a silent
# reconcile-exact-solver job that held the box through d2r2's whole cell window.
# Attempt 3's own G-TENANCY-enforced window was CLEAN, and is the first
# tenancy-enforced saturated calibration this program has ever had. Banner (C).
#
# CELL R800 (--rung-sims 800) and CELL R1600 (--rung-sims 1600), deck-paired on
# ONE band and THE SAME 200 decks, against a frozen fair-PIMC probe (k4x1024,
# tie-arbiter OFF), vs the frozen HeuristicMCTS(h800 / h1600, c=3.0) rung.
#
#   run_cells.sh local [--smoke] [--dry-run] [--band <SEED_START>]
#
# ⭐ THE TWO REAL CELLS DIFFER IN EXACTLY ONE EXPERIMENTAL ARGUMENT --
# `--rung-sims`. Both cells' argv are built from ONE shared COMMON array below,
# so G-SINGLEVAR is STRUCTURAL, not clerical. (They also differ in
# `--out-subdir` and `--claim-host`, which are BOOKKEEPING: two cells cannot
# share one output directory or one `--shared-claim` tag without corrupting
# each other.)
#
# =============================================================================
# CARRIED VERBATIM IN BEHAVIOUR FROM THE D2-R2 LAUNCHER -- FIXES 1-4
# =============================================================================
# These four are PROVEN (attempt 2 passed every gate they close). They are
# reproduced here unchanged except where the run id appears. Do not "improve"
# them; the only edits below are renames.
#
# FIX 1 (G-RULES).  R9 CANNOT live in the rules profile: `base_deck` derives the
#   farm data at IMPORT time and the Rust registry latches a `OnceLock`, so it
#   must be in the ENVIRONMENT before the process starts
#   (src/carcassonne_ai/rules_profile.py, R9_ENV_VAR). This launcher EXPORTS
#   CARCASSONNE_FIX_R9=1 at file scope -- before any leg, including --smoke and
#   --dry-run -- and `assert_r9_env` REFUSES to run if it is unset or not truthy.
#
# FIX 2 (G-LEAF).  For `--info fair --opponent h800` the harness does NOT
#   auto-inject curve125, so a naive cell plays the RUNG-DEFAULT v2.9 leaf on
#   both sides. The champion leaf reaches the CANDIDATE the way production play
#   does: the in-process `--cand-leaf-json` mechanism
#   (champion_leaf_curve125.json), NEVER by exporting CARCASSONNE_V29_MEEPLE_CURVE
#   -- the harness's _CANON_ENV uses setdefault, so a pre-set curve env would
#   MOVE THE RUNG to curve125 too and silently invalidate the CL-022 ruler.
#   `preflight_leaf` builds one champion through the harness's own module and
#   asserts BOTH sides before game 1: candidate == a36d2e15a3b3d71d AND
#   rung == 42af12fce22e1a0f.
#
# FIX 3 (G-TOOL a).  Attempt 1's two cells ran at DIFFERENT repo revs. This
#   launcher SNAPSHOTS `git rev-parse HEAD` + the code-path dirty fingerprint at
#   start, RE-CHECKS before EACH cell, and REFUSES to start a subsequent cell if
#   either moved -- loud, with both revs named.
#
# FIX 4 (G-TOOL b).  The pair's "BLIND_COMMIT in both manifests" sub-clause was
#   UNSATISFIABLE until a `--stamp-key KEY=VALUE` passthrough was added to the
#   harness's manifest writer (additive, inert unless passed, tested); this
#   launcher routes the BLIND_COMMIT file's content through it. The stamp lands
#   at BOTH searched addresses: `manifest["BLIND_COMMIT"]` and
#   `manifest["config"]["stamps"]["BLIND_COMMIT"]`.
#
# ALSO (G-TOOL, the dirty-tree half).  `require_clean_code` REFUSES a real cell
#   when any CODE path is dirty, overridable ONLY by `LAUNCH_DIRTY=1` with a
#   mandatory `LAUNCH_DIRTY_REASON`. The refusal is scoped to CODE paths ON
#   PURPOSE: this repo's working tree carries churning measurement artifacts at
#   all times, and this launcher itself must drop `RUN_LIVE.json` inside
#   `measurement/` for the freeze-latch hook to see it -- so a whole-tree dirty
#   refusal would fail on EVERY healthy run. Non-code dirt is RECORDED and is
#   not fatal.
#
# =============================================================================
# WHAT IS NEW IN ATTEMPT 4 -- AND IT IS ONLY (B) AND (C)
# =============================================================================
# ⭐ (D) THROUGH (I) BELOW ARE ATTEMPT 3's MACHINERY, CARRIED VERBATIM. Attempt 3
# did not die of an instrument defect; it died of a mis-derived constant, and its
# instrument is what made that cheap to discover. Do not "improve" any of them.
#
# (A) IDENTITY.  Run id `track_d2r4_prep`; out-subdirs d2r4_rung800 /
#     d2r4_rung1600; claim hosts d2r4-<NAME>-<HOST>.
#
# (B) BAND.  PINNED_BAND=150000000000; the smoke leg burns a DISJOINT throwaway
#     range at 150999999000 that is discarded and never pooled. Band
#     149000000000 is SPENT AND RETIRED -- attempt 3 put ~40 decks of real
#     records on it before the burn-in gate fired.
#
# (C) PROBE BUDGET k4x1024 (4096 total sims), DOWN from attempt 3's k4x1600
#     (6400 total sims). THIS IS THE ONLY EXPERIMENTAL CONSTANT THAT MOVES.
#
#     ⚠️ WHY ATTEMPT 3's NUMBER WAS WRONG, AND IT IS NOT WHAT IT LOOKS LIKE.
#     Attempt 3 priced 6400 against attempt 2's CELL-REALIZED saturated costs
#     (rung 1103.1 ms/move, probe 924.7 ms/move at 5504) -- which was the right
#     METHOD applied to CONTAMINATED INPUTS. The reconcile exact-solver suite ran
#     a silent ~100%-CPU job through d2r2's ENTIRE cell window, invisible to that
#     era's census (silent job + comm-truncated ps). The python rung, which is
#     DRAM-latency-bound, inflated ~1.8x; the rust probe only ~1.13x. The
#     asymmetry is what flagged the diagnosis. Zero code changes to src/engine/
#     rust/harness between the two revs; env/config byte-identical per manifests.
#     Record: results.csv row
#     `d2r3_rung_compression_U_UNREADABLE_burnin_abort_n80_b149e9`;
#     DECISIONS.md "2026-08-26 (midday)".
#
#     ⭐ THE CLEAN BASIS. Attempt 3's own burn-in window was measured under
#     G-TENANCY and came back CLEAN -- 40 decks x 2 seatings = 80 games, W=22,
#     exclusive box, n_malformed=0, n_missing=0. It is the FIRST tenancy-enforced
#     saturated calibration any attempt has had:
#         /mnt/c/carc-shared/track_d2r3_prep/BURNIN_R800.json
#         rung  (HeuristicMCTS h800, c=3.0, python, R9) =  601.19 ms/move
#         probe (rust fair PIMC, k4x1600 = 6400 total)  =  931.30 ms/move
#         => 931.30 / 6400 = 0.14552 ms per total-sim   [LINEAR, through origin]
#
#     TWO COST MODELS, both anchored on that ONE clean point:
#       * (M1) LINEAR through origin:
#              4096 x 0.14552 = 596.03 ms/move  =>  ratio 596.03 / 601.19
#              = 0.9914.
#       * (M2) FIXED-OVERHEAD-BOUNDED. Write the probe as F + c x sims and fit
#              through the same one point (F + 6400c = 931.30), so
#                  probe(4096) = 0.64 x 931.30 + 0.36 x F = 596.03 + 0.36 F
#              -- INCREASING in F, and equal to M1 exactly at F = 0. So M1 is the
#              FLOOR of this family and the CEILING is the only rail a fixed
#              overhead can push us through. It is reached only at
#                  596.03 + 0.36 F >= 1.20 x 601.19 = 721.43  =>  F >= 348.3
#              i.e. 37% of the probe's whole cost at 6400 as pure per-move fixed
#              overhead. That is implausible for a rust PIMC search, AND it does
#              not have to be argued: the burn-in gate (G) bounds the loss at
#              ~2.2 core-h whichever model is right.
#
#     ⚠️ NOTE WHAT IS *NOT* CLAIMED. Unlike attempt 3, this pair does NOT fit a
#     superlinear exponent. That exponent (1.261) was fitted from two co-tenant-
#     era points and is not trustworthy; there is exactly ONE clean scaling point
#     in existence. A model fitted to one point is a line through the origin, and
#     saying so is more honest than reusing a contaminated slope. Everything else
#     in COMMON is unchanged from attempt 3.
#
#     MARGINS TO THE RAILS at the projected 0.9914, stated before game 1: the
#     rung would have to run >=17.4% FASTER than the clean 601.19 (<=496.7
#     ms/move) to breach 1.20, or >=16.6% SLOWER (>=701.2 ms/move) to breach
#     0.85. Attempts 2 and 3 each had margin under only ONE of their two models.
#
#     ✅ AND ONE THING GOES AWAY. Attempt 3 carried a DELIBERATE NUMERICAL
#     COLLISION -- its candidate `--sims 1600` was the same integer as CELL
#     R1600's `--rung-sims 1600` -- and had to gate it so a reader could check
#     it. At k4x1024 THE COLLISION DOES NOT EXIST: `--sims 1024` (the CANDIDATE's
#     per-determinization PIMC budget; manifest `config.sims` and
#     `config.champion.sims_per_det`) can no longer be confused with
#     `--rung-sims 800/1600` (the OPPONENT HeuristicMCTS rung's budget; manifest
#     `config.rung.sims`). ⛔ `G-PROBE` IS RETAINED UNCHANGED ANYWAY. It was
#     never really a collision gate: no pair before attempt 3 gated the probe's
#     OWN budget at all, and that is the gap it closes. It now stands on that
#     merit alone.
#
# (D) SINGLE BOX, SINGLE W -- THE LAPTOP ROLE IS GONE. Only ROLE=local is valid,
#     W=22, SHARE=/mnt/c/carc-shared. See `resolve_role` for the refusal text:
#     the equal-time budget in (C) is calibrated against W=22 SATURATED figures
#     on THIS box; a different W is a different load regime and therefore a
#     different ratio, and `--shared-claim` across two boxes would mix two
#     regimes into one aggregate that means nothing. The `nproc >= W` check is
#     carried from the h2h_22016_prep precedent (an under-provisioned box
#     thrashes silently and would fail G-TIMING for a reason that is not the
#     experiment).
#
# (E) `--pilot` IS GONE; `--smoke` REPLACES IT AND HAS NO TIMING AUTHORITY.
#     This is the heart of the rebuild. Attempt 2 died because the quantity a
#     PILOT measured (an equal-time ratio at n=16, W unsaturated) was not the
#     quantity the CELL realized (the same ratio at n=400, W=22 saturated). The
#     smoke leg is a PLUMBING check only: it proves the config runs, that
#     n_failed == 0, and that the pair's own adjudicator can read what the
#     harness emits. It PRINTS a ratio under an explicit not-a-gate banner and
#     ADJUDICATES NOTHING. The equal-time gate now lives INSIDE the real cell --
#     see (G).
#     The smoke leg ends by running the pair's OWN adjudicator against the smoke
#     archive, per the h2h AMENDMENTS.md standing rule:
#         "the launcher's smoke step must end by running the cell's own
#          adjudicator against the smoke archive, and must require it to fail
#          only on band/N gates"
#     which is the fix for selftests that validate against SYNTHESIZED rather
#     than EMITTED manifests. A nonzero exit from the adjudicator is FATAL.
#     The smoke stays EXEMPT from the blind / band / dirty-code preconditions
#     (it spends neither blindness nor the band) but is NOT exempt from FIX 1
#     (R9) or FIX 2 (leaf pre-flight) -- a smoke run under the wrong rules or
#     the wrong leaf is not a smoke for THIS cell.
#
# (F) EXCLUSIVE TENANCY IS A PRECONDITION, NOT A COURTESY
#     (`feedback_no_agent_compute_beside_eval`: nice + thread-caps are NOT
#     coexistence on this DRAM-bound box). TWO mechanisms, both required:
#       1. `require_exclusive_box` -- a preflight census (d2r4_lib.py census)
#          before any real cell. Nonzero exit is FATAL and names the offending
#          processes / foreign RUN_LIVE.json sentinels. Override:
#          ALLOW_COTENANT=1 with a MANDATORY ALLOW_COTENANT_REASON, logged and
#          recorded into the PRELAUNCH record (same shape as LAUNCH_DIRTY).
#       2. A background SAMPLER for the whole of each cell.
#     ⚠️ WHY THE PREFLIGHT ALONE IS NOT ENOUGH: attempt 2's disclosed co-tenant
#     (an Android cross-compile + gradle build) STARTED AFTER the cell did, and
#     occupied the box during CELL R800's final ~10 minutes. A preflight census
#     cannot see a process that does not exist yet. Only a sampler running for
#     the cell's whole life could have caught it, which is what mechanism 2 is.
#
# (G) THE BURN-IN GATE -- ATTEMPT 3's CONTRIBUTION, AND IT PAID FOR ITSELF ON ITS
#     FIRST RUN. For CELL R800 ONLY (the
#     R1600 ratio is LOW BY CONSTRUCTION -- a 2x rung against the same probe --
#     and is not gated). The cell starts, and a watcher starts with it:
#         d2r4_lib.py watch --cell-dir <cell> --out BURNIN_R800.json
#     It blocks until all 80 burn-in games (decks BAND+0..BAND+39, both seats)
#     have records, then exits 0 (PASS: ratio inside the frozen bar) / 1 (FAIL)
#     / 2 (timeout => FAIL-CLOSED).
#       * on PASS: log the realized ratio and let the cell run to completion.
#         ⭐ THE BURN-IN GAMES COUNT. They are the cell's own first 40 decks,
#         same invocation, same config, same claim tag; NOTHING IS DISCARDED.
#         The live gate and the post-hoc gate are literally the same code
#         (d2r4_lib.timing_ratio) reading the same records, which is what makes
#         a live gate legitimate instead of a second, differently-measured pilot.
#       * on FAIL / TIMEOUT: KILL THE CELL AND STOP THE WHOLE RUN. A cost
#         calibration void then costs ~8% of a pair instead of 100%. ⭐ THIS IS NO
#         LONGER A PROJECTION: on attempt 3 this path FIRED FOR REAL at 80 of 800
#         games -- ~3.7 core-h against the ~44 a full void would have cost. At
#         attempt 4's cheaper probe the same abort costs ~2.2 core-h / ~6 min.
#     The same abort path fires if the tenancy sampler drops
#     ABORT_TENANCY_<NAME>.json at any point during EITHER cell.
#
#     ⚠️ PROCESS-GROUP HANDLING (`feedback_set_m_not_setsid_for_cell_groups`).
#     The cell is started under `set -m`, so its PGID == its PID BY
#     CONSTRUCTION. NEVER derive a PGID with `ps -o pgid= -p $!` after setsid:
#     it can return the DRIVER's group, in which case the driver kills itself,
#     the cell survives orphaned, and the sampler goes on writing zeros that
#     read like data. `start_cell` explicitly GUARDS that the observed cell
#     PGID equals the cell PID and DIFFERS from the driver's PGID before any
#     group-wide signal is ever permitted.
#     ⚠️ KILL ORDER (`feedback_isolate_destructive_tool_calls`): MAIN pid first,
#     settle, THEN survivors of the group by EXACT pid. A LIVE multiprocessing
#     Pool REPLACES workers you kill under it.
#
# (H) CELL ORDER IS FIXED: R800 runs FIRST, always -- it carries the gate and it
#     is the shorter cell. R1600 starts only after R800 completes AND
#     BURNIN_R800.json reads "pass": true.
#
# (I) The PRELAUNCH record carries the probe budget, the burn-in window size and
#     bar, the census verdict path, and the co-tenant override fields.
#
# =============================================================================
# NO BAR LIVES IN THIS SHELL.
# =============================================================================
# Every threshold and every piece of cost arithmetic lives in `d2r4_lib.py` and
# NOWHERE ELSE -- the equal-time bar, the whole-cell drift envelope, the burn-in
# window size, the tenancy CPU thresholds, the confirm-sample count, and the
# transcription of `eval_fair_puct._summary()`. This script SHELLS OUT for all
# of it. tests/test_d2r4_instrument.py asserts at grep level that no second copy
# of any bar has crept in here. The one numeric literal this file legitimately
# owns is PINNED_BAND, which is the launcher's own pin and is asserted equal to
# d2r4_lib.BAND by the same test.
#
# PRECONDITIONS, IN ORDER, ENFORCED BY THIS SCRIPT:
#   0. BLIND_COMMIT (a file in this directory, 40 hex chars) exists and is not a
#      placeholder.
#   1. BAND_CLAIMED (a file in this directory) exists -- the EXECUTOR drops it
#      after appending the band-claim row to governance/BAND_REGISTRY.csv. This
#      script NEVER claims or invents a band.
#   2. --band, if given, must equal PINNED_BAND -- it may only CONFIRM the
#      pinned value, never shadow it. A disagreeing --band is FATAL.
#   3. nproc >= W.
#   4. The box is an EXCLUSIVE TENANT (F).
#   5. --dry-run and --smoke are EXEMPT from 0-1 and from the dirty-code
#      refusal; --dry-run is additionally exempt from 3-4 because it starts
#      nothing at all. NEITHER is exempt from FIX 1 or FIX 2.
#
# ⚠️ DETACH IT. Mac-sleep SIGHUP and WSL VM teardown both kill tty-attached
# jobs -- launch as:
#   setsid nohup ./run_cells.sh local </dev/null >/dev/null 2>&1 & disown
# =============================================================================
set -euo pipefail

SELF="$(readlink -f "${BASH_SOURCE[0]}")"
DIR="$(dirname "$SELF")"
# Resolve the repo from THIS FILE's location, so the launcher is correct in the
# main tree and inside a git worktree alike (and so a dry-run/smoke can be
# exercised from a build worktree without pointing at the live tree by accident).
REPO="$(git -C "$DIR" rev-parse --show-toplevel)"
# The interpreter is the repo venv. CARC_PY overrides it for ONE purpose only:
# exercising --dry-run / the pre-flights from a build worktree, which carries the
# CODE under test but no `.venv` of its own. A real cell on a real box never sets
# it, and the resolved value is logged either way.
PY="${CARC_PY:-$REPO/.venv/bin/python}"
[ -x "$PY" ] || { echo "FATAL: no python at '$PY' (set CARC_PY to override)" >&2; exit 2; }
HARNESS="$REPO/scripts/classical_search/eval_fair_puct.py"
[ -f "$HARNESS" ] || { echo "FATAL: harness missing at '$HARNESS'" >&2; exit 2; }
# THE ONE IMPLEMENTATION of every bar and every cost figure (see the banner).
LIB="$DIR/d2r4_lib.py"
[ -f "$LIB" ] || { echo "FATAL: d2r4_lib.py missing at '$LIB'" >&2; exit 2; }
# The pair's own adjudicator. Only the --smoke leg invokes it.
ADJ="$DIR/analyze_d2r4.py"

# ---------------------------------------------------------------------------
# FIX 1 -- R9. Exported BEFORE anything can import carcassonne_ai. `fixed_v1`
# EXPECTS this (rules_profile.r9_env_expected=True) and CANNOT apply it itself:
# import-time farm derivation + a Rust OnceLock. Without it every manifest reads
# rules_profile.r9_env_ok == False and the cell is U-UNREADABLE on G-RULES.
# ---------------------------------------------------------------------------
export CARCASSONNE_FIX_R9=1

# ⚠️ DELIBERATELY NOT EXPORTED: CARCASSONNE_V29_MEEPLE_CURVE. The champion leaf
# is injected IN-PROCESS on the candidate side only (FIX 2). Exporting the curve
# would move the harness's DEFAULT_CONFIG and therefore MOVE THE RUNG -- see the
# CURVE125 block in eval_fair_puct.py and `_assert_rung_is_ruler`.

# The band pinned by the pair -- --band may only CONFIRM this, never shadow it.
# This is the ONE numeric literal this shell owns; the test asserts it equals
# d2r4_lib.BAND.
PINNED_BAND=150000000000
# DISJOINT throwaway range for the smoke leg; never pooled, never claimed, never
# adjudicated. Deliberately far above the band so no arithmetic slip can reach it.
SMOKE_SEED_START=150999999000

# The two leaf hashes this cell's identity rests on (READ_RULE §3).
CHAMP_LEAF_HASH=a36d2e15a3b3d71d      # candidate: the curve125 production champion
RUNG_RULER_LEAF_HASH=42af12fce22e1a0f # rung: env DEFAULT_CONFIG, the CL-022 ruler
CAND_LEAF_JSON="$DIR/champion_leaf_curve125.json"

# The probe budget -- see banner (C). k-dets x sims = total sims.
PROBE_K_DETS=4
PROBE_SIMS=1024
PROBE_TOTAL_SIMS=4096

# CODE paths: dirt here makes `code_rev` a lie about what played the games.
CODE_PATHS=(src engine scripts rust tests pyproject.toml setup.py)

ROLE="${1:?usage: run_cells.sh local [--smoke] [--dry-run] [--band SEED_START]}"
shift || true
SMOKE=0; DRY=0; BAND=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --smoke)   SMOKE=1 ;;
    --dry-run) DRY=1 ;;
    --band)    BAND="${2:?--band needs a seed start}"; shift ;;
    *) echo "FATAL: unknown argument '$1'" >&2; exit 2 ;;
  esac
  shift
done

if [ -n "$BAND" ] && [ "$SMOKE" -eq 0 ] && [ "$BAND" != "$PINNED_BAND" ]; then
  echo "FATAL: --band $BAND disagrees with the pair's PINNED_BAND=$PINNED_BAND." >&2
  echo "FATAL: this launcher never accepts a different band for a real cell --" >&2
  echo "FATAL: if the band must change, the PAIR changes (DESIGN §5 + the band claim)." >&2
  exit 2
fi
BAND="${BAND:-$PINNED_BAND}"

# --------------------------------------------------------------------------- #
# (D) ONE ROLE, ONE BOX, ONE W. The laptop role of the d2r2 launcher is GONE.  #
# --------------------------------------------------------------------------- #
case "$ROLE" in
  local) SHARE=/mnt/c/carc-shared; W=22 ;;
  *)
    echo "FATAL: bad role '$ROLE' -- the ONLY valid role for D2-R4 is 'local'." >&2
    echo "FATAL:" >&2
    echo "FATAL:   1. The equal-time budget (k4x1024) is calibrated against the" >&2
    echo "FATAL:      d2r3 TENANCY-ENFORCED CLEAN burn-in figures on THIS box" >&2
    echo "FATAL:      at W=22 (rung 601.19 / probe 931.30 ms/move at 6400)." >&2
    echo "FATAL:      A different W is a different load regime and therefore a" >&2
    echo "FATAL:      DIFFERENT RATIO -- the budget does not transfer, and the" >&2
    echo "FATAL:      burn-in gate would be adjudicating a quantity nobody costed." >&2
    echo "FATAL:   2. --shared-claim across two boxes would interleave games from" >&2
    echo "FATAL:      two load regimes into ONE cell directory, and the cell's" >&2
    echo "FATAL:      single aggregate ms/move would then describe neither box." >&2
    echo "FATAL:      G-TIMING over such an aggregate is meaningless by" >&2
    echo "FATAL:      construction, which no post-hoc analysis can repair." >&2
    echo "FATAL:   3. Exclusive tenancy (banner F) is enforced per-box; a second" >&2
    echo "FATAL:      box is a second tenancy story this pair does not carry." >&2
    echo "FATAL: If D2-R4 must ever run on another box, that is a PAIR-level" >&2
    echo "FATAL: decision with a fresh cost calibration -- not a role flag." >&2
    exit 2 ;;
esac
HOST="$(hostname)"
OUT="$SHARE/track_d2r4_prep"
# Logs, sentinels and the pre-launch record live on the SHARE, not in the repo:
# a launcher that writes into its own working tree dirties the very tree whose
# cleanliness it is asserting.
LOGS="$OUT/logs"

# Filled in by start_cell / start_sampler; declared here so the abort paths can
# reference them unconditionally under `set -u`.
CELL_PID=""; CELL_PGID=""; GROUP_KILL_SAFE=0
SAMPLER_PID=""; SAMPLER_STOP=""; SAMPLER_OUT=""; ABORT_TENANCY=""
WATCH_PID=""; BURNIN_OUT=""; BURNIN_RC=""
CENSUS_OUT="$OUT/CENSUS_PRELAUNCH.json"

ts()  { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[d2r4 $(ts) $HOST/$ROLE] $*"; }

# --------------------------------------------------------------------------- #
# FIX 1 assertion. Refuses if the export above was somehow undone (a wrapper    #
# that scrubs the env, a `env -i` invocation, an edited copy of this file).     #
# Runs for EVERY leg including --smoke and --dry-run.                          #
# --------------------------------------------------------------------------- #
assert_r9_env() {
  local v="${CARCASSONNE_FIX_R9:-}"
  case "$(printf '%s' "$v" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) log "[G-RULES] CARCASSONNE_FIX_R9=$v (fixed_v1 expects it; import-latched)" ;;
    *)
      log "!!! FATAL: CARCASSONNE_FIX_R9 is unset or not truthy (got '${v}')."
      log "!!! fixed_v1 declares r9_env_expected=True and CANNOT apply R9 itself"
      log "!!! (import-time farm derivation + a Rust OnceLock), so every manifest"
      log "!!! would read rules_profile.r9_env_ok=False -> G-RULES VOID."
      exit 3 ;;
  esac
}

# --------------------------------------------------------------------------- #
# FIX 2 assertion. Build the champion leaf THROUGH THE HARNESS'S OWN MODULE     #
# (importing eval_fair_puct applies its _CANON_ENV exactly as a real cell does) #
# and assert BOTH sides before game 1:                                          #
#   candidate (--cand-leaf-json) == a36d2e15a3b3d71d   -> G-LEAF                #
#   rung      (env DEFAULT_CONFIG) == 42af12fce22e1a0f -> G-RUNG / the ruler    #
# The second half is not decoration: it is what catches someone sourcing        #
# champ_env.sh (or exporting the curve) and silently moving the ruler.          #
# --------------------------------------------------------------------------- #
preflight_leaf() {
  [ -f "$CAND_LEAF_JSON" ] || { log "!!! FATAL: missing $CAND_LEAF_JSON"; exit 4; }
  CARC_PREFLIGHT_LEAF_JSON="$CAND_LEAF_JSON" \
  CARC_PREFLIGHT_CHAMP_HASH="$CHAMP_LEAF_HASH" \
  CARC_PREFLIGHT_RUNG_HASH="$RUNG_RULER_LEAF_HASH" \
  CARC_PREFLIGHT_REPO="$REPO" \
  "$PY" - <<'PFEOF' || { log "!!! FATAL: champion-leaf pre-flight FAILED -- see above. No game runs."; exit 4; }
import os, sys
repo = os.environ["CARC_PREFLIGHT_REPO"]
sys.path.insert(0, os.path.join(repo, "scripts", "classical_search"))
# Importing the harness module applies its _CANON_ENV (setdefault) exactly as a
# real cell does, and is side-effect-free otherwise (it is __main__-guarded).
import eval_fair_puct as H

want_cand = os.environ["CARC_PREFLIGHT_CHAMP_HASH"]
want_rung = os.environ["CARC_PREFLIGHT_RUNG_HASH"]
cand = H._load_cand_leaf_cfg(os.environ["CARC_PREFLIGHT_LEAF_JSON"])
H._assert_cy_float_path(cand)
got_cand = H._leaf_hash(cand)
got_rung = H._leaf_hash(H.DEFAULT_CONFIG)
ok = True
print(f"[preflight-leaf] candidate leaf_hash = {got_cand}  (want {want_cand})")
print(f"[preflight-leaf] rung      leaf_hash = {got_rung}  (want {want_rung})")
print(f"[preflight-leaf] candidate curve     = {cand.v29_meeple_curve}")
print(f"[preflight-leaf] rung      curve     = {H.DEFAULT_CONFIG.v29_meeple_curve}")
print(f"[preflight-leaf] r9 env observed     = {os.environ.get('CARCASSONNE_FIX_R9')!r}")
if got_cand != want_cand:
    print("[preflight-leaf] !!! G-LEAF WOULD VOID: the candidate is not the champion leaf.")
    ok = False
if got_rung != want_rung:
    print("[preflight-leaf] !!! G-RUNG WOULD VOID: the rung is not the CL-022 curve100 ruler.")
    print("[preflight-leaf] !!! Did something export CARCASSONNE_V29_MEEPLE_CURVE / source "
          "champ_env.sh? _CANON_ENV uses setdefault, so a pre-set curve MOVES THE RULER.")
    ok = False
if got_cand == got_rung:
    print("[preflight-leaf] !!! candidate and rung resolve the SAME leaf -- the probe is "
          "not the champion. VOID.")
    ok = False
sys.exit(0 if ok else 1)
PFEOF
  log "[G-LEAF/G-RUNG] champion-leaf pre-flight PASS (cand $CHAMP_LEAF_HASH / rung $RUNG_RULER_LEAF_HASH)"
}

# --------------------------------------------------------------------------- #
# (D) nproc >= W -- carried from measurement/h2h_22016_prep/run_cells.sh.       #
# An under-provisioned box thrashes SILENTLY, and the thing it would corrupt    #
# first is exactly the quantity this pair gates on.                             #
# --------------------------------------------------------------------------- #
require_nproc() {
  local np; np="$(nproc)"
  if [ "$np" -lt "$W" ]; then
    log "!!! FATAL: nproc=$np < W=$W. An under-provisioned box thrashes silently,"
    log "!!! and the first casualty is the per-move cost this pair gates on."
    exit 2
  fi
  log "[preflight] nproc=$np >= W=$W"
}

# --------------------------------------------------------------------------- #
# FIX 3 -- rev pinning. Snapshot at start; re-check before EACH cell.          #
# --------------------------------------------------------------------------- #
code_dirty_list() {
  git -C "$REPO" status --porcelain -- "${CODE_PATHS[@]}" 2>/dev/null || true
}
tree_dirty_count() {
  git -C "$REPO" status --porcelain 2>/dev/null | wc -l | tr -d ' '
}
snapshot_rev() {
  SNAP_REV="$(git -C "$REPO" rev-parse HEAD)"
  SNAP_CODE_DIRTY="$(code_dirty_list | sort | md5sum | awk '{print $1}')"
  SNAP_CODE_DIRTY_N="$(code_dirty_list | grep -c . || true)"
  log "[G-TOOL] rev snapshot: HEAD=$SNAP_REV code-dirty-files=$SNAP_CODE_DIRTY_N fp=$SNAP_CODE_DIRTY"
  log "[G-TOOL] whole-tree dirty entries (informational, NOT fatal): $(tree_dirty_count)"
}
assert_rev_unmoved() {
  local who="$1"
  local now_rev now_fp now_n
  now_rev="$(git -C "$REPO" rev-parse HEAD)"
  now_fp="$(code_dirty_list | sort | md5sum | awk '{print $1}')"
  now_n="$(code_dirty_list | grep -c . || true)"
  if [ "$now_rev" != "$SNAP_REV" ]; then
    log "!!! FATAL (G-TOOL): the repo rev MOVED between cells."
    log "!!!   at launch : $SNAP_REV"
    log "!!!   now ($who): $now_rev"
    log "!!! The first D2 attempt died exactly here: a commit landed on main between"
    log "!!! the two legs, so the two cells were not the same instrument. REFUSING to"
    log "!!! start $who. Re-run the whole pair at ONE rev; do not salvage half a pair."
    exit 5
  fi
  if [ "$now_fp" != "$SNAP_CODE_DIRTY" ]; then
    log "!!! FATAL (G-TOOL): the CODE dirty-state CHANGED between cells."
    log "!!!   at launch : $SNAP_CODE_DIRTY_N file(s), fp=$SNAP_CODE_DIRTY"
    log "!!!   now ($who): $now_n file(s), fp=$now_fp"
    log "!!! Same rev, different working code -> the two cells are not the same"
    log "!!! instrument even though code_rev would read the same sha. REFUSING."
    code_dirty_list | sed 's/^/!!!   /' | while read -r l; do log "$l"; done
    exit 5
  fi
  log "[G-TOOL] rev re-check OK before $who: HEAD=$now_rev, code dirt unchanged ($now_n)"
}

# --------------------------------------------------------------------------- #
# ALSO -- dirty-CODE refusal (real cells only; smoke/dry-run exempt).          #
# --------------------------------------------------------------------------- #
require_clean_code() {
  local dirt n
  dirt="$(code_dirty_list)"
  n="$(printf '%s' "$dirt" | grep -c . || true)"
  if [ "$n" -eq 0 ]; then
    log "[G-TOOL] code paths clean (${CODE_PATHS[*]})"
    return 0
  fi
  log "!!! CODE PATHS ARE DIRTY ($n entr(ies)) -- code_rev would be a lie about what ran:"
  printf '%s\n' "$dirt" | sed 's/^/!!!   /'
  if [ "${LAUNCH_DIRTY:-0}" = "1" ]; then
    if [ -z "${LAUNCH_DIRTY_REASON:-}" ]; then
      log "!!! FATAL: LAUNCH_DIRTY=1 requires LAUNCH_DIRTY_REASON=<why>. No reason, no override."
      exit 6
    fi
    log "!!! OVERRIDE ACCEPTED: LAUNCH_DIRTY=1"
    log "!!! REASON: $LAUNCH_DIRTY_REASON"
    log "!!! This is recorded in the PRELAUNCH record and in this log. The manifests"
    log "!!! will still read <sha>-dirty; the adjudicator reads this line to know why."
    return 0
  fi
  log "!!! FATAL: refusing to start a real cell on dirty CODE."
  log "!!! Commit or stash the code paths, or re-run with"
  log "!!!   LAUNCH_DIRTY=1 LAUNCH_DIRTY_REASON='<why>' $SELF $ROLE"
  exit 6
}

# --------------------------------------------------------------------------- #
# BLIND_COMMIT + BAND_CLAIMED -- both real files.                               #
# --------------------------------------------------------------------------- #
require_blind_and_band() {
  local bc="$DIR/BLIND_COMMIT" bcl="$DIR/BAND_CLAIMED"
  if [ ! -f "$bc" ] || ! grep -qE '^[0-9a-f]{40}$' "$bc"; then
    log "!!! FATAL: $bc is missing or does not hold a 40-hex-char sha."
    log "!!! It currently reads: '$(tr -d '[:space:]' < "$bc" 2>/dev/null || echo '<absent>')'"
    log "!!! The EXECUTOR writes the real sha AFTER DESIGN.md + READ_RULE.md land on main."
    log "!!! (--dry-run and --smoke are exempt -- neither spends blindness.)"
    exit 2
  fi
  if [ ! -f "$bcl" ]; then
    log "!!! FATAL: $bcl is missing."
    log "!!! The EXECUTOR drops it AFTER appending the band-claim row to"
    log "!!! governance/BAND_REGISTRY.csv. This script never claims a band."
    exit 2
  fi
}

blind_commit_value() { tr -d '[:space:]' < "$DIR/BLIND_COMMIT"; }

# --------------------------------------------------------------------------- #
# (F) 1 -- EXCLUSIVE-TENANCY PREFLIGHT CENSUS. All logic (instantaneous per-pid #
# CPU%, the aggregate bar, the confirm-sample count, the foreign-sentinel scan) #
# lives in d2r4_lib.py. This shell only decides what to do with the exit code.  #
# --------------------------------------------------------------------------- #
require_exclusive_box() {
  local rc=0
  mkdir -p "$OUT"
  log "[G-TENANCY] preflight census (d2r4_lib census) -> $CENSUS_OUT"
  "$PY" "$LIB" census --repo "$REPO" --own-dir "$DIR" --own-pgid $$ \
      --out "$CENSUS_OUT" || rc=$?
  if [ "$rc" -eq 0 ]; then
    log "[G-TENANCY] preflight census CLEAN -- no foreign RUN_LIVE.json, no foreign compute"
    return 0
  fi
  log "!!! G-TENANCY PREFLIGHT FAILED (census rc=$rc). The offending processes and/or"
  log "!!! foreign RUN_LIVE.json sentinels are named in the JSON printed just above"
  log "!!! and saved at $CENSUS_OUT."
  log "!!! feedback_no_agent_compute_beside_eval: nice + thread-caps are NOT coexistence"
  log "!!! on this DRAM-bound box. Attempt 2 disclosed an Android cross-compile + gradle"
  log "!!! build sharing the box during CELL R800's final ~10 minutes; this pair gates on"
  log "!!! per-move COST, so a co-tenant is not noise, it is the measurement moving."
  if [ "${ALLOW_COTENANT:-0}" = "1" ]; then
    if [ -z "${ALLOW_COTENANT_REASON:-}" ]; then
      log "!!! FATAL: ALLOW_COTENANT=1 requires ALLOW_COTENANT_REASON=<why>. No reason, no override."
      exit 7
    fi
    log "!!! OVERRIDE ACCEPTED: ALLOW_COTENANT=1"
    log "!!! REASON: $ALLOW_COTENANT_REASON"
    log "!!! Recorded in the PRELAUNCH record and in this log. The mid-run SAMPLER is"
    log "!!! NOT disabled by this override -- it still aborts on a confirmed breach."
    return 0
  fi
  log "!!! FATAL: refusing to start a real cell without exclusive tenancy."
  log "!!! Wait for the box, or re-run with"
  log "!!!   ALLOW_COTENANT=1 ALLOW_COTENANT_REASON='<why>' $SELF $ROLE"
  exit 7
}

# --------------------------------------------------------------------------- #
# ONE shared COMMON array -- both real cells' argv extend it (G-SINGLEVAR is    #
# STRUCTURAL). FIX 2 and FIX 4 live here, so neither cell can be built without  #
# them.                                                                        #
# --------------------------------------------------------------------------- #
build_common() {
  # ⚠️ --n 400: the harness's --n counts GAMES; --paired gives 2 seatings per
  # deck, so --n 400 = 200 DECKS (the costed and gated deck count).
  # DO NOT "fix" this to 200.
  # ⚠️ --sims $PROBE_SIMS (1024): the CANDIDATE probe axis, NOT the rung axis.
  # See banner (C) for the derivation against the d2r3 TENANCY-ENFORCED CLEAN
  # burn-in costs. (Attempt 3's numerical collision with CELL R1600's
  # --rung-sims is GONE at this budget; G-PROBE is retained regardless.)
  COMMON=(--info fair --opponent h800 --backend rust
          --k-dets "$PROBE_K_DETS" --sims "$PROBE_SIMS" --exact-k 2
          --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits
          --n 400 --paired --seed-start "$BAND"
          --rules-profile fixed_v1 --workers "$W"
          --cand-leaf-json "$CAND_LEAF_JSON"
          --out-root "$OUT"
          --shared-claim --claim-stale-secs 1800
          --no-results-csv)
  if [ "$1" = "with-stamp" ]; then
    COMMON+=(--stamp-key "BLIND_COMMIT=$(blind_commit_value)")
  fi
}

# $1 = cell name (R800|R1600), $2 = rung-sims, $3 = out-subdir, $4 = with-stamp|no-stamp
cell_argv() {
  local NAME="$1" RS="$2" SUB="$3" STAMP="${4:-with-stamp}"
  build_common "$STAMP"
  ARGV=(nice -n 19 "$PY" -u "$HARNESS" "${COMMON[@]}"
        --rung-sims "$RS"
        --out-subdir "$SUB"
        --claim-host "d2r4-$NAME-$HOST")
}

# --------------------------------------------------------------------------- #
# RUN_LIVE.json freeze-latch sentinel. MUST live under measurement/ for the     #
# repo's PreToolUse hook to see it, so this one file necessarily dirties the    #
# working tree -- which is why the dirty refusal above is scoped to CODE paths. #
# --------------------------------------------------------------------------- #
run_live_path() { echo "$DIR/RUN_LIVE.json"; }
run_live_drop() {
  "$PY" - "$(run_live_path)" "$1" <<'RLEOF' || true
import json, os, socket, sys, time
p, what = sys.argv[1], sys.argv[2]
json.dump({"what": what, "host": socket.gethostname(), "pid": os.getppid(),
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "why": ("D2-R4 rung-compression cell freeze-latch sentinel: a MAIN-TREE "
                   "commit while this leg is live is what produced the first "
                   "attempt's two-revision pair. Cleared on the launcher's EXIT trap."),
           "cleared_by": "the launcher's EXIT trap"},
          open(p, "w"), indent=2, sort_keys=True)
RLEOF
  log "[freeze] RUN_LIVE dropped -> $(run_live_path)"
}
run_live_clear() { rm -f "$(run_live_path)" 2>/dev/null || true; }

write_prelaunch() {
  mkdir -p "$OUT"
  CARC_PL_OUT="$OUT/PRELAUNCH_${HOST}.json" \
  CARC_PL_REV="$SNAP_REV" CARC_PL_FP="$SNAP_CODE_DIRTY" \
  CARC_PL_N="$SNAP_CODE_DIRTY_N" CARC_PL_TREE_N="$(tree_dirty_count)" \
  CARC_PL_BAND="$BAND" CARC_PL_ROLE="$ROLE" CARC_PL_W="$W" \
  CARC_PL_BLIND="$(blind_commit_value)" \
  CARC_PL_CAND="$CHAMP_LEAF_HASH" CARC_PL_RUNG="$RUNG_RULER_LEAF_HASH" \
  CARC_PL_DIRTY_OVERRIDE="${LAUNCH_DIRTY:-0}" \
  CARC_PL_DIRTY_REASON="${LAUNCH_DIRTY_REASON:-}" \
  CARC_PL_COTENANT_OVERRIDE="${ALLOW_COTENANT:-0}" \
  CARC_PL_COTENANT_REASON="${ALLOW_COTENANT_REASON:-}" \
  CARC_PL_CENSUS="$CENSUS_OUT" \
  CARC_PL_KDETS="$PROBE_K_DETS" CARC_PL_PSIMS="$PROBE_SIMS" \
  CARC_PL_PTOTAL="$PROBE_TOTAL_SIMS" \
  CARC_PL_LIBDIR="$DIR" \
  "$PY" - <<'PLEOF' || true
import json, os, socket, sys, time
sys.path.insert(0, os.environ["CARC_PL_LIBDIR"])
# No __pycache__ in measurement/: a launcher that asserts tree cleanliness must
# not create untracked churn in the tree it is asserting about.
sys.dont_write_bytecode = True
# The burn-in window size and its bar are READ FROM THE LIBRARY, never retyped.
import d2r4_lib as L
d = {
    "run_id": "track_d2r4_prep",
    "host": socket.gethostname(), "role": os.environ["CARC_PL_ROLE"],
    "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "band_seed_start": int(os.environ["CARC_PL_BAND"]),
    "workers": int(os.environ["CARC_PL_W"]),
    "blind_commit": os.environ["CARC_PL_BLIND"],
    "code_rev_head": os.environ["CARC_PL_REV"],
    "code_dirty_fingerprint": os.environ["CARC_PL_FP"],
    "code_dirty_files": int(os.environ["CARC_PL_N"]),
    "tree_dirty_entries": int(os.environ["CARC_PL_TREE_N"]),
    "dirty_override": os.environ["CARC_PL_DIRTY_OVERRIDE"] == "1",
    "dirty_override_reason": os.environ["CARC_PL_DIRTY_REASON"] or None,
    "cotenant_override": os.environ["CARC_PL_COTENANT_OVERRIDE"] == "1",
    "cotenant_override_reason": os.environ["CARC_PL_COTENANT_REASON"] or None,
    "census_verdict_path": os.environ["CARC_PL_CENSUS"],
    "r9_env": os.environ.get("CARCASSONNE_FIX_R9"),
    "expected_cand_leaf_hash": os.environ["CARC_PL_CAND"],
    "expected_rung_leaf_hash": os.environ["CARC_PL_RUNG"],
    "probe_k_dets": int(os.environ["CARC_PL_KDETS"]),
    "probe_sims_per_det": int(os.environ["CARC_PL_PSIMS"]),
    "probe_total_sims": int(os.environ["CARC_PL_PTOTAL"]),
    "burnin_decks": L.N_BURNIN_DECKS,
    "burnin_bar": [L.TIMING_LO, L.TIMING_HI],
    "note": ("Per-box pre-launch record for the D2-R4 cost-calibration-fix "
             "successor. Adjudicates nothing; it is the witness that FIX 1-4, the "
             "tenancy precondition and the burn-in gate were in force on THIS box "
             "before game 1. burnin_* are READ FROM d2r4_lib, not retyped."),
}
json.dump(d, open(os.environ["CARC_PL_OUT"], "w"), indent=2, sort_keys=True)
print("[prelaunch] wrote", os.environ["CARC_PL_OUT"])
PLEOF
}

print_dry_run() {
  local name="$1" rs="$2" sub="$3"
  cell_argv "$name" "$rs" "$sub" no-stamp
  printf '[dry-run] cell %s (rung-sims=%s):' "$name" "$rs"
  printf ' %q' "${ARGV[@]}"
  printf '\n'
  printf '[dry-run]   (a real cell also carries --stamp-key BLIND_COMMIT=<sha from %s>)\n' \
    "$DIR/BLIND_COMMIT"
}

# =========================================================================== #
# (E) THE SMOKE LEG -- PLUMBING ONLY, ZERO TIMING AUTHORITY.                   #
# =========================================================================== #
run_smoke() {
  local sub="smoke_r800"
  local SARGV=(nice -n 19 "$PY" -u "$HARNESS"
        --info fair --opponent h800 --backend rust
        --k-dets "$PROBE_K_DETS" --sims "$PROBE_SIMS" --exact-k 2
        --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits
        --n 16 --paired --seed-start "$SMOKE_SEED_START"
        --rules-profile fixed_v1 --workers "$W"
        --cand-leaf-json "$CAND_LEAF_JSON"
        --out-root "$OUT" --out-subdir "$sub"
        --shared-claim --claim-stale-secs 1800
        --claim-host "d2r4-smoke-$HOST"
        --no-results-csv
        --rung-sims 800)
  if [ "$DRY" -eq 1 ]; then
    printf '[dry-run] smoke argv:'
    printf ' %q' "${SARGV[@]}"
    printf '\n'
    return 0
  fi
  log "SMOKE -- CELL R800's config at n=16 (8 decks x 2 seatings), seed-start=$SMOKE_SEED_START"
  log "SMOKE band is DISJOINT, DISCARDED and never pooled with the real cell band."
  log "SMOKE checks PLUMBING ONLY: does the config run, is n_failed 0, can the pair's"
  log "SMOKE own adjudicator read what the harness emits."
  mkdir -p "$LOGS" "$OUT/$sub"

  # ADVISORY tenancy census. The smoke is exempt from the tenancy PRECONDITION
  # (it adjudicates nothing, so a co-tenant cannot corrupt a verdict) but the
  # reading is free and tells the operator whether the box will be usable when
  # the real cell wants it. Non-fatal by construction.
  log "[census] ADVISORY (smoke leg -- non-fatal):"
  if "$PY" "$LIB" census --repo "$REPO" --own-dir "$DIR" --own-pgid $$; then
    log "[census] ADVISORY: box is exclusive right now."
  else
    log "[census] ADVISORY: box is NOT exclusive right now. Harmless for a smoke"
    log "[census] ADVISORY: (it adjudicates nothing), but a REAL cell would REFUSE"
    log "[census] ADVISORY: here unless ALLOW_COTENANT=1 + ALLOW_COTENANT_REASON."
  fi

  "${SARGV[@]}" >> "$LOGS/smoke_r800.log" 2>&1 || \
    log "smoke rc=$? (the harness is resumable under --shared-claim)"

  log "SMOKE DONE -- asserting n_failed == 0 and printing the realized ratio"
  "$PY" - "$OUT/$sub" "$DIR" <<'SEOF' || { log "!!! FATAL: smoke leg did not produce a clean archive."; exit 10; }
import json, sys, pathlib
out = pathlib.Path(sys.argv[1])
sys.path.insert(0, sys.argv[2])
sys.dont_write_bytecode = True   # see write_prelaunch
# The ratio arithmetic is the LIBRARY's, so this print cannot drift from the gate.
import d2r4_lib as L

cands = sorted(out.glob("**/summary.json"))
if not cands:
    print("[smoke] !!! no summary.json found under", out)
    sys.exit(1)
s = json.load(open(cands[-1]))
nf = s.get("n_failed")
if nf is None:
    print("[smoke] !!! summary.json has no n_failed field")
    sys.exit(1)
if int(nf) != 0:
    print(f"[smoke] !!! n_failed = {nf} -- the config does not run clean. FATAL.")
    sys.exit(1)
print(f"[smoke] n_failed = 0 over n = {s.get('n')} games")

recs, mal = L.load_records(out)
r = L.timing_ratio(recs, malformed=mal)
print("")
print("*** NOT A GATE -- a 16-game leg does not saturate W=22; the equal-time gate is "
      "the BURN-IN WINDOW inside the real cell (READ_RULE §3 G-TIMING). This number is "
      "printed for information and adjudicates nothing. ***")
print("")
if r.ratio is None:
    print("[smoke] no timing reading available (no usable records) -- still NOT A GATE")
else:
    print(f"[smoke] champ_prefix_ms_per_move={r.champ_ms_per_move:.3f} "
          f"rung_ms_per_move={r.rung_ms_per_move:.3f} ratio={r.ratio:.4f} "
          f"over {r.n_games} games")
print("[smoke] ^ INFORMATION ONLY. Attempt 2 died because a pilot ratio measured at "
      "n=16 with W unsaturated was not the ratio the cell realized at n=400 with W=22 "
      "saturated. This launcher does not repeat that inference.")
sys.exit(0)
SEOF

  # --------------------------------------------------------------------- #
  # The h2h AMENDMENTS.md standing rule: the smoke step ENDS by running    #
  # the cell's OWN adjudicator against the smoke archive, and requires it  #
  # to fail only on the band/N/paired-cell gates a 16-game throwaway       #
  # archive cannot satisfy by construction. This is the fix for selftests  #
  # that validate against SYNTHESIZED rather than EMITTED manifests: the   #
  # only archive an adjudicator is ever proven against must be one the     #
  # harness actually wrote.                                                #
  # --------------------------------------------------------------------- #
  if [ ! -f "$ADJ" ]; then
    log "!!! FATAL: the pair's adjudicator is missing at $ADJ."
    log "!!! The smoke leg is not complete until analyze_d2r4.py --smoke-mode has"
    log "!!! read the archive the harness just emitted. Do not launch a real cell"
    log "!!! against an adjudicator that has never seen an emitted manifest."
    exit 11
  fi
  log "SMOKE -- running the pair's own adjudicator in --smoke-mode against $OUT/$sub"
  "$PY" "$ADJ" --smoke-mode --cell-r800 "$OUT/$sub" || {
    log "!!! FATAL: analyze_d2r4.py --smoke-mode returned nonzero on the smoke archive."
    log "!!! In --smoke-mode the adjudicator must PASS iff the ONLY failures are the"
    log "!!! band / N / paired-cell gates a 16-game throwaway archive cannot satisfy."
    log "!!! A nonzero exit therefore means a REAL gate is broken on emitted output --"
    log "!!! exactly what this step exists to catch before 800 games are spent."
    exit 11
  }
  log "SMOKE PASS -- plumbing clean, adjudicator reads emitted output. NO TIMING VERDICT WAS TAKEN."
}

# =========================================================================== #
# (F)(G) CELL SUPERVISION -- process groups, the sampler, the burn-in gate.    #
# =========================================================================== #

# True iff `$1` is a live, non-zombie pid. A background child that has exited is
# a ZOMBIE until reaped, and `kill -0` SUCCEEDS on a zombie -- so a naive
# `kill -0` completion test spins forever.
proc_alive() {
  local p="$1" line st
  [ -n "$p" ] || return 1
  [ -r "/proc/$p/stat" ] || return 1
  read -r line < "/proc/$p/stat" 2>/dev/null || return 1
  st="${line##*) }"; st="${st%% *}"
  [ "$st" != "Z" ]
}

# `feedback_set_m_not_setsid_for_cell_groups`: with job control ON, a background
# job becomes its own process-group leader, so PGID == PID BY CONSTRUCTION. We
# still VERIFY it and refuse group-wide signalling if the verification fails.
start_cell() {
  local logfile="$1"
  set -m
  "${ARGV[@]}" >> "$logfile" 2>&1 &
  CELL_PID=$!
  set +m
  local observed driver
  observed="$(ps -o pgid= -p "$CELL_PID" 2>/dev/null | tr -d ' ' || true)"
  driver="$(ps -o pgid= -p $$ 2>/dev/null | tr -d ' ' || true)"
  if [ -n "$observed" ] && [ "$observed" = "$CELL_PID" ] && [ "$observed" != "$driver" ]; then
    CELL_PGID="$CELL_PID"; GROUP_KILL_SAFE=1
    log "[proc] cell pid=$CELL_PID pgid=$CELL_PGID (driver pgid=$driver) -- group kill ARMED"
  else
    CELL_PGID=""; GROUP_KILL_SAFE=0
    log "!!! [proc] WARNING: cell pgid ('$observed') is not its own pid ('$CELL_PID') or"
    log "!!! equals the driver's pgid ('$driver'). Group-wide signalling is DISARMED --"
    log "!!! signalling that group would kill THIS DRIVER and orphan the cell. An abort"
    log "!!! will kill the cell's MAIN pid only; check for orphaned workers by hand."
  fi
}

start_sampler() {
  local name="$1"
  SAMPLER_OUT="$OUT/TENANCY_${name}.jsonl"
  SAMPLER_STOP="$OUT/.sampler_stop_${name}"
  ABORT_TENANCY="$OUT/ABORT_TENANCY_${name}.json"
  rm -f "$SAMPLER_STOP" "$ABORT_TENANCY" 2>/dev/null || true
  # Detached so a driver hiccup cannot take the tenancy record with it.
  setsid nohup "$PY" "$LIB" sampler \
      --out "$SAMPLER_OUT" \
      --own-pgid "${CELL_PGID:-$CELL_PID}" \
      --stop-file "$SAMPLER_STOP" \
      --abort-file "$ABORT_TENANCY" \
      >> "$LOGS/tenancy_${name}.log" 2>&1 &
  SAMPLER_PID=$!
  log "[G-TENANCY] sampler pid=$SAMPLER_PID -> $SAMPLER_OUT (abort file: $ABORT_TENANCY)"
}

stop_sampler() {
  [ -n "$SAMPLER_STOP" ] && : > "$SAMPLER_STOP" 2>/dev/null || true
  [ -n "$SAMPLER_PID" ] && kill "$SAMPLER_PID" 2>/dev/null || true
  SAMPLER_PID=""
}

# `feedback_isolate_destructive_tool_calls`: kill the MAIN pid FIRST and let it
# settle -- a LIVE multiprocessing Pool REPLACES workers killed under it -- then
# take the survivors of the cell's own process group by EXACT pid.
kill_cell() {
  local why="$1" p
  if [ -z "$CELL_PID" ]; then
    log "[kill] $why -- no live cell pid recorded; nothing to signal."
    return 0
  fi
  log "[kill] $why -- killing cell MAIN pid $CELL_PID FIRST (a live Pool respawns"
  log "[kill] workers if you kill its children first), then group survivors by pid."
  kill -TERM "$CELL_PID" 2>/dev/null || true
  local i=0
  while [ "$i" -lt 5 ]; do
    proc_alive "$CELL_PID" || break
    sleep 1
    i=$((i + 1))
  done
  if proc_alive "$CELL_PID"; then
    log "[kill] main pid still alive after ~5s settle -- SIGKILL"
    kill -KILL "$CELL_PID" 2>/dev/null || true
  fi
  if [ "$GROUP_KILL_SAFE" = "1" ]; then
    local survivors
    survivors="$(pgrep -g "$CELL_PGID" 2>/dev/null || true)"
    if [ -n "$survivors" ]; then
      log "[kill] group $CELL_PGID survivors (killing by EXACT pid): $(echo "$survivors" | tr '\n' ' ')"
      for p in $survivors; do
        [ "$p" = "$$" ] && continue
        kill -KILL "$p" 2>/dev/null || true
      done
    else
      log "[kill] no survivors in group $CELL_PGID"
    fi
  else
    log "[kill] group kill DISARMED (see the [proc] warning) -- main pid only."
  fi
  CELL_PID=""
}

write_abort_json() {
  # $1 = destination, $2 = kind, $3 = human reason, $4 = evidence path ("" if none)
  CARC_AB_OUT="$1" CARC_AB_KIND="$2" CARC_AB_REASON="$3" CARC_AB_EVID="${4:-}" \
  CARC_AB_LIBDIR="$DIR" CARC_AB_CELL="${5:-}" \
  "$PY" - <<'ABEOF' || true
import json, os, socket, sys, time
sys.path.insert(0, os.environ["CARC_AB_LIBDIR"])
sys.dont_write_bytecode = True   # see write_prelaunch
# The bar is READ FROM THE LIBRARY. This shell never retypes one.
import d2r4_lib as L
evid_path = os.environ.get("CARC_AB_EVID") or None
evid = None
if evid_path and os.path.isfile(evid_path):
    try:
        evid = json.load(open(evid_path))
    except Exception as e:  # pragma: no cover - diagnostics only
        evid = {"unreadable": evid_path, "error": str(e)}
d = {
    "run_id": "track_d2r4_prep",
    "kind": os.environ["CARC_AB_KIND"],
    "reason": os.environ["CARC_AB_REASON"],
    "cell": os.environ.get("CARC_AB_CELL") or None,
    "host": socket.gethostname(),
    "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "bar_lo": L.TIMING_LO,
    "bar_hi": L.TIMING_HI,
    "burnin_decks": L.N_BURNIN_DECKS,
    "evidence_path": evid_path,
    "evidence": evid,
    "terminal": True,
    "note": ("The band is retired with roughly the burn-in window's worth of records "
             "on it. There is NO re-pick and NO resume under this pair: a fourth "
             "attempt needs a fresh pair, a fresh band and a fresh owner decision."),
}
json.dump(d, open(os.environ["CARC_AB_OUT"], "w"), indent=2, sort_keys=True)
print("[abort] wrote", os.environ["CARC_AB_OUT"])
ABEOF
}

abort_terminal() {
  # $1 = cell name, $2 = kind, $3 = reason, $4 = evidence path, $5 = exit code
  local name="$1" kind="$2" reason="$3" evid="$4" code="$5"
  log "!!!"
  log "!!! ================= TERMINAL ABORT ($kind) ================="
  log "!!! $reason"
  kill_cell "$kind on cell $name"
  stop_sampler
  write_abort_json "$OUT/ABORT_${kind}_${name}.json" "$kind" "$reason" "$evid" "$name"
  run_live_clear
  log "!!! CELL R1600 WILL NOT START. The run stops here."
  log "!!! The band $BAND is RETIRED with roughly the burn-in window's worth of"
  log "!!! records on it. There is NO re-pick and NO resume under this pair --"
  log "!!! attempt 4 has spent its calibration the same way attempts 1, 2 and 3"
  log "!!! spent theirs. A FIFTH attempt needs a FRESH PAIR, a FRESH BAND, and a"
  log "!!! FRESH OWNER DECISION. Do not restart this launcher."
  log "!!! Evidence: $evid"
  log "!!! ==========================================================="
  exit "$code"
}

# $1 = name, $2 = rung-sims, $3 = out-subdir, $4 = gated|ungated
run_cell_supervised() {
  local NAME="$1" RS="$2" SUB="$3" GATED="$4"
  local logfile="$LOGS/cells_$NAME.log"
  cell_argv "$NAME" "$RS" "$SUB" with-stamp
  log "cell $NAME (rung-sims=$RS) -> $OUT/$SUB"
  mkdir -p "$OUT/$SUB"
  start_cell "$logfile"
  start_sampler "$NAME"

  WATCH_PID=""; BURNIN_RC=""
  local burnin_seen=0
  if [ "$GATED" = "gated" ]; then
    BURNIN_OUT="$OUT/BURNIN_${NAME}.json"
    rm -f "$BURNIN_OUT" 2>/dev/null || true
    log "[G-TIMING] burn-in watcher armed -> $BURNIN_OUT"
    log "[G-TIMING] it blocks until EVERY burn-in game (both seats of the window's"
    log "[G-TIMING] decks, defined by SEED not by arrival order) has a record, then"
    log "[G-TIMING] adjudicates with the SAME code the post-hoc gate uses."
    log "[G-TIMING] ⭐ THE BURN-IN GAMES COUNT -- same invocation, same config, same"
    log "[G-TIMING] claim tag. Nothing is discarded on PASS."
    "$PY" "$LIB" watch --cell-dir "$OUT/$SUB" --band "$BAND" \
        --out "$BURNIN_OUT" --poll-secs 20 --timeout-secs 5400 \
        >> "$LOGS/burnin_${NAME}.log" 2>&1 &
    WATCH_PID=$!
  else
    log "[G-TIMING] cell $NAME is NOT burn-in-gated: its ratio is LOW BY CONSTRUCTION"
    log "[G-TIMING] (a 2x rung against the same probe). The whole-cell drift envelope"
    log "[G-TIMING] still applies post-hoc, in analyze_d2r4.py."
  fi

  # ---- the supervisor loop ------------------------------------------------ #
  while :; do
    # (F) mid-run tenancy abort -- fires during EITHER cell.
    if [ -n "$ABORT_TENANCY" ] && [ -f "$ABORT_TENANCY" ]; then
      [ -n "$WATCH_PID" ] && kill "$WATCH_PID" 2>/dev/null || true
      abort_terminal "$NAME" "TENANCY" \
        "A foreign tenant was CONFIRMED on the box while cell $NAME was live. Attempt 2's co-tenant started AFTER its cell did, which is why a preflight census alone is not a control. This pair gates on per-move COST: a co-tenant is not noise, it is the measurement moving." \
        "$ABORT_TENANCY" 9
    fi
    # (G) burn-in verdict -- the watcher writes its JSON, then exits.
    if [ "$GATED" = "gated" ] && [ "$burnin_seen" -eq 0 ] && [ -f "$BURNIN_OUT" ]; then
      BURNIN_RC=0
      wait "$WATCH_PID" || BURNIN_RC=$?
      WATCH_PID=""
      burnin_seen=1
      if [ "$BURNIN_RC" -eq 0 ]; then
        log "[G-TIMING] BURN-IN PASS. Verdict written to $BURNIN_OUT:"
        sed 's/^/[G-TIMING]   /' "$BURNIN_OUT" || true
        log "[G-TIMING] cell $NAME continues to completion; the burn-in games COUNT."
      else
        local why
        if [ "$BURNIN_RC" -eq 2 ]; then
          why="The burn-in window did not COMPLETE inside the watcher's timeout. FAIL-CLOSED: an incomplete window is an unknown window, and gating on an unknown window is what a gate exists to prevent."
        else
          why="The realized burn-in equal-time ratio is OUTSIDE the frozen bar. This is the SAME reading, over the SAME records, with the SAME code the post-hoc gate would use -- so the cell is already U-UNREADABLE on G-TIMING and every further game is waste."
        fi
        abort_terminal "$NAME" "BURNIN" "$why (watcher rc=$BURNIN_RC)" "$BURNIN_OUT" 8
      fi
    fi
    proc_alive "$CELL_PID" || break
    sleep 5
  done

  local CELL_RC=0
  wait "$CELL_PID" || CELL_RC=$?
  CELL_PID=""
  [ "$CELL_RC" -eq 0 ] || log "cell $NAME rc=$CELL_RC (the harness is resumable under --shared-claim)"

  # The cell is gone; drain the watcher if it somehow outlived it.
  if [ -n "$WATCH_PID" ]; then
    BURNIN_RC=0
    wait "$WATCH_PID" || BURNIN_RC=$?
    WATCH_PID=""
    if [ "$GATED" = "gated" ] && [ "$BURNIN_RC" -ne 0 ]; then
      abort_terminal "$NAME" "BURNIN" \
        "The cell ended before the burn-in window was adjudicated PASS (watcher rc=$BURNIN_RC)." \
        "${BURNIN_OUT:-}" 8
    fi
  fi
  stop_sampler
  log "[G-TENANCY] tenancy record for $NAME: $SAMPLER_OUT"
}

# The gate's verdict, re-read from disk -- so a RESUME (cell R800 already DONE)
# is held to the same condition as a fresh run. The verdict field is read from
# the file the LIBRARY wrote; no bar is evaluated here.
require_burnin_pass() {
  local f="$1" rc=0
  "$PY" - "$f" <<'BPEOF' || rc=$?
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
if not p.is_file():
    print(f"[G-TIMING] !!! {p} is absent -- CELL R800's burn-in was never adjudicated.")
    sys.exit(1)
try:
    v = json.loads(p.read_text())
except Exception as e:
    print(f"[G-TIMING] !!! {p} is unreadable: {e}")
    sys.exit(1)
if not v.get("pass"):
    print(f"[G-TIMING] !!! {p} reads pass=False.")
    sys.exit(1)
print(f"[G-TIMING] {p} reads pass=True -- CELL R1600 is clear to start.")
sys.exit(0)
BPEOF
  if [ "$rc" -ne 0 ]; then
    log "!!! FATAL: CELL R1600 requires CELL R800's burn-in verdict to read pass=true."
    log "!!! Refusing to spend a second cell on a band whose cost calibration is not"
    log "!!! established. Nothing to resume: see the ABORT record in $OUT."
    exit 8
  fi
}

main() {
  assert_r9_env                      # FIX 1 -- every leg, no exemptions
  preflight_leaf                     # FIX 2 -- every leg, no exemptions

  if [ "$SMOKE" -eq 1 ]; then
    [ "$DRY" -eq 1 ] || require_nproc
    run_smoke
    return 0
  fi

  if [ "$DRY" -eq 1 ]; then
    snapshot_rev
    log "role=$ROLE W=$W band=$BAND (dry-run: no games start, no blind/band/tenancy guards enforced)"
    log "probe budget: k-dets=$PROBE_K_DETS sims=$PROBE_SIMS total=$PROBE_TOTAL_SIMS"
    print_dry_run R800  800  d2r4_rung800
    print_dry_run R1600 1600 d2r4_rung1600
    return 0
  fi

  require_nproc                      # (D) -- h2h precedent
  require_blind_and_band
  snapshot_rev                       # FIX 3 -- the baseline both cells are pinned to
  require_clean_code                 # ALSO -- dirty-CODE refusal (real cells only)
  require_exclusive_box              # (F) 1 -- preflight census

  log "role=$ROLE W=$W band=$BAND out=$OUT"
  log "BLIND_COMMIT=$(blind_commit_value) (stamped into BOTH manifests via --stamp-key)"
  log "probe budget: k-dets=$PROBE_K_DETS sims=$PROBE_SIMS total=$PROBE_TOTAL_SIMS"
  log "⚠️ --sims $PROBE_SIMS is the CANDIDATE probe axis, NOT --rung-sims (rung axis)."
  log "⭐ the two real cells differ in EXACTLY ONE EXPERIMENTAL argument: --rung-sims"
  log "⚠️ they also differ in --out-subdir and --claim-host, which are BOOKKEEPING."

  mkdir -p "$LOGS" "$OUT"
  write_prelaunch
  trap 'run_live_clear' EXIT INT TERM
  run_live_drop "d2r4 rung-compression cell (role=$ROLE)"

  # (H) CELL R800 FIRST, ALWAYS -- it carries the gate and it is the shorter cell.
  if [ -f "$OUT/DONE_cells_R800_${HOST}" ]; then
    log "cell R800 already DONE on $HOST -- skipping (its burn-in verdict still gates R1600)"
    BURNIN_OUT="$OUT/BURNIN_R800.json"
  else
    assert_rev_unmoved "cell R800"   # FIX 3 -- re-checked before EACH cell
    run_cell_supervised R800 800 d2r4_rung800 gated
    touch "$OUT/DONE_cells_R800_${HOST}"
  fi

  # (H) the gate stands between the two cells, on resume as on a fresh run.
  require_burnin_pass "$OUT/BURNIN_R800.json"

  if [ -f "$OUT/DONE_cells_R1600_${HOST}" ]; then
    log "cell R1600 already DONE on $HOST -- skipping"
  else
    assert_rev_unmoved "cell R1600"
    run_cell_supervised R1600 1600 d2r4_rung1600 ungated
    touch "$OUT/DONE_cells_R1600_${HOST}"
  fi

  if [ -f "$OUT/DONE_cells_R800_${HOST}" ] && [ -f "$OUT/DONE_cells_R1600_${HOST}" ]; then
    run_live_clear
    log "DONE -- both cells complete on $HOST, RUN_LIVE cleared"
  else
    log "one or more cells did not complete -- RUN_LIVE stays until both DONE sentinels exist"
  fi
}

# Testability seam. `CARC_D2R4_LIB_ONLY=1 source run_cells.sh local` defines every
# guard above and runs NOTHING — so tests/test_d2r4_instrument.py can call
# assert_r9_env / preflight_leaf / assert_rev_unmoved / require_clean_code /
# require_exclusive_box / proc_alive directly instead of asserting on log text.
# It changes no behaviour of a real launch: the variable is never set on a box,
# and an unset variable takes the `main` branch.
if [ "${CARC_D2R4_LIB_ONLY:-0}" != "1" ]; then
  main "$@"
fi
