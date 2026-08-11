#!/bin/bash
# PHASE-SEAM GATE (d) — CHUNKED + RESUMABLE rebuild.
#
# ============================ WHAT THIS MEASURES ============================
# Does commit 549c0d1 (worktree agent-a195cbd889c3187bf, branch
# worktree-agent-a195cbd889c3187bf — a DEFAULT-OFF leaf phase multiplier)
# introduce any NOVEL test failure?
#
#   GREEN iff every failing test ID on the SEAM tree also fails on the MAIN tree
#          (i.e. every seam-side failure is pre-existing).
#   RED    if any failing ID is novel to the seam.
#
# The contract is identical to the serial phase_seam_gate.sh it replaces. Only the
# EXECUTION shape changed.
#
# ======================= WHY CHUNKS, NOT ONE BIG RUN ========================
# The serial gate ran the whole suite in ONE pytest process and failed THREE times
# for "infrastructure" reasons without ever producing a verdict:
#   * local box 2026-08-09 06:51 and 09:49 — dirty reboots
#   * laptop    2026-08-09 ~11:30        — WSL2 VM force-exit (0x80370107)
# Those are almost certainly not bad luck. An UNSEGMENTED `pytest tests/` run is a
# DOCUMENTED VM-killer on these boxes: the exact-solver modules accumulate
# transposition tables across the whole session and one python reached 34.6 GB RSS
# on 2026-07-29, starving the Windows host until the utility VM was torn down. A
# ~3 h single process is therefore both the thing most likely to die AND the thing
# that loses everything when it does.
#
# Chunking fixes all three failure classes at once:
#   1. MEMORY. Each chunk is a FRESH process, so per-chunk RSS is bounded and the
#      exact-solver files are isolated into a chunk of their own. Each chunk also
#      runs inside a `systemd-run --user --scope` memory cap when one is available.
#   2. CRASH LOSS. A dirty reboot or a VM teardown costs exactly ONE chunk. Rerun
#      the script and it picks up where it stopped.
#   3. HERMETICITY — and this is a genuine improvement to the measurement, not just
#      an ops convenience. The known pre-existing failures in this suite ARE
#      cross-file import-order contamination (virtual_score_v2.DEFAULT_CONFIG is
#      env-latched at import; prod_leaf_env hard-raises if imported after
#      carcassonne_ai). A fresh process per chunk is MORE hermetic than one giant
#      process, not less.
#
# CHUNK MEMBERSHIP IS A COMMITTED LITERAL (the CHUNKS array below). It is NOT
# derived at runtime from a glob. That is load-bearing: the seam leg and the main
# leg must see the SAME files in the SAME order inside the SAME process, or the
# import-order contamination differs between legs and the diff is inadmissible.
# If you add a test file to the repo you must add it to a chunk here by hand;
# the PREFLIGHT below fails loudly if the union of the chunks does not equal the
# set of files pytest actually collects.
#
# ============================ INVOCATION RULES ==============================
#   * SERIAL, never xdist, within a chunk — same env-latching reason as before.
#     Chunks are also run one at a time: two concurrent chunks would reintroduce
#     the memory pressure this design exists to remove.
#   * tests/rustport is its OWN chunk (chunk 17). prod_leaf_env hard-raises at
#     collection if imported after carcassonne_ai; the house runs it separately.
#   * The seam's Rust half lives in a scratch wheel PREPENDED to PYTHONPATH, so the
#     shared site-packages carc_rs is never touched and the main leg is stock.
#
# ============================= RESUME SEMANTICS =============================
#   Artifact per (tree, chunk):  PHASE_SEAM_GATE/chunks/<tree>/<chunk>.json
#   A chunk whose .json exists is SKIPPED on rerun. Artifacts are written
#   atomically (tmp + mv), so a crash mid-write cannot leave a half-truth.
#
#   A chunk only earns an artifact if pytest printed a real summary line. A
#   process that was OOM-killed / SIGKILLed / reboot-eaten prints no summary; that
#   is recorded as a CRASH, retried up to MAX_ATTEMPTS, and if it still will not
#   complete the gate exits INCONCLUSIVE rather than silently counting a dead
#   chunk as "zero failures". Never let a crash manufacture a GREEN.
#
#   A verdict is written ONLY when all 2*len(CHUNKS) artifacts exist. A partial
#   run is INCOMPLETE, never GREEN.
#
# Usage:  bash phase_seam_gate_chunked.sh            # run/resume to a verdict
#         bash phase_seam_gate_chunked.sh --plan     # print the chunk plan, exit
set -u

REPO=${GATE_REPO:-/home/doctor/projects/carcassone}
WT=$REPO/.claude/worktrees/agent-a195cbd889c3187bf
PY=${GATE_PY:-$REPO/.venv/bin/python}
OUT=${GATE_OUT:-$REPO/measurement/curve_shape_scope_20260809/PHASE_SEAM_GATE}
WHEEL_DIR=$OUT/wheels
WHEEL=$WHEEL_DIR/carc_rs-0.1.0-cp312-abi3-manylinux_2_34_x86_64.whl
SHADOW=$WHEEL_DIR/carc_rs_shadow
CHUNKDIR=$OUT/chunks
MAX_ATTEMPTS=${GATE_MAX_ATTEMPTS:-3}
CHUNK_TIMEOUT=${GATE_CHUNK_TIMEOUT:-3600}
MEM_HIGH=${GATE_MEM_HIGH:-7G}   # just under MEM_MAX on purpose -- see chunk_limits
MEM_MAX=${GATE_MEM_MAX:-8G}

ts() { date +%F_%T; }
log() { echo "[gate $(ts)] $*"; }

# --------------------------------------------------------------------------
# THE CHUNK PLAN. name -> space-separated pytest paths, relative to a tree root.
# Nine chunks isolate the files that are heavy in RAM or wall-clock (the exact
# solver, MCTS, self-play, the 311-case meeple equivalence sweep, the 194-case
# golden set, the android bridge); the remaining ~104 light files are split
# alphabetically into eight roughly equal-sized groups; rustport is last and
# alone. Sizes in the comments are COLLECTED TEST COUNTS (2345 total).
# --------------------------------------------------------------------------
CHUNKS=(
"01_release_a|tests/release/test_bag_invariants.py tests/release/test_crop_boundary.py tests/release/test_deck_canonicalization.py tests/release/test_factory_manifest.py tests/release/test_farm_scoring.py tests/release/test_key_collision.py tests/release/test_rotation_alias.py tests/release/test_sign_semantics.py tests/test_action_space.py tests/test_adaptive_k_census.py tests/test_analyze_oracle_price.py tests/test_analyzer.py tests/test_analyzer_evloss.py"
"02_light_b|tests/test_aux_targets.py tests/test_bare_net_opponent.py tests/test_board_repr.py tests/test_board_repr_internal.py tests/test_board_repr_meeples.py tests/test_c5_fair_leaf_ab.py tests/test_c5_leaf_ab.py tests/test_c7_leaf_terms.py tests/test_c_cheap_scaffold.py tests/test_clairvoyance_wrapper.py tests/test_clairvoyant_mirror_rules.py tests/test_clock_skew_guard.py tests/test_cloister_scan_fix.py"
"03_light_c|tests/test_compact_leaf.py tests/test_coreml_evaluator.py tests/test_e4_deck_baseline.py tests/test_elo.py tests/test_engine_adjacency.py tests/test_entropy_guard.py tests/test_eval_iter_head_to_head_flags.py tests/test_eval_provenance.py tests/test_eval_server.py tests/test_eval_server_pool.py tests/test_evaluators.py tests/test_f3_caller_backends.py tests/test_f3_public_state_oracle.py"
"04_light_d|tests/test_f6_soft_cap.py tests/test_f7b_farm_knockout.py tests/test_farm_dedup_c1.py tests/test_farm_index.py tests/test_farm_multifield_city_p1l5.py tests/test_farm_scalars.py tests/test_farmwar_discriminator.py tests/test_features.py tests/test_fixed_start_tile.py tests/test_flat_leaf_edge_cases.py tests/test_flat_repr_cy.py tests/test_flywheel_loss_masking.py tests/test_frozen_substrates.py"
"05_light_e|tests/test_game_wrapper.py tests/test_gate_b_backend.py tests/test_gate_b_fair_pimc.py tests/test_gatec_c0.py tests/test_global_pool.py tests/test_hybrid_handoff_trigger.py tests/test_invalid_visit_clip.py tests/test_invariants.py tests/test_ladder_asymmetric.py tests/test_leaf_residual_mining.py tests/test_legal_moves_cache.py tests/test_measurement_infra.py tests/test_midgame_disagreement.py"
"06_light_f|tests/test_network.py tests/test_oracle_prior.py tests/test_oracle_score_pilot.py tests/test_pareto_curve_tally.py tests/test_policy_only.py tests/test_probe_5a_tempo_align.py tests/test_probe_a_feature_emit.py tests/test_r9_field_on_city_edge.py tests/test_remote_eval_bridge.py tests/test_render_marg_frontier.py tests/test_retune_parser.py tests/test_river_rotation.py tests/test_rr_roundrobin_harness.py"
"07_light_g|tests/test_rule_based_player.py tests/test_rules_fixed_descriptives.py tests/test_rules_profile.py tests/test_run_manifest.py tests/test_run_watchdog.py tests/test_semantic_eval_contracts.py tests/test_shell_harness_hygiene.py tests/test_shm_eval_handles.py tests/test_sighted_planes.py tests/test_stage_local.py tests/test_start_tile_grid_bound.py tests/test_state_deepcopy.py tests/test_string_representation.py"
"08_light_h|tests/test_symmetry_aug.py tests/test_t3_optuna.py tests/test_teacher_heuristic_prior.py tests/test_train_provenance.py tests/test_unplaceable_redraw.py tests/test_v210_bag_close.py tests/test_v28_variants.py tests/test_v29_flat_curve.py tests/test_v29_phase_multiplier.py tests/test_v29_variants.py tests/test_value_in_loop_fb1.py tests/test_value_norm.py tests/test_virtual_score.py tests/test_virtual_score_v2.py tests/test_wall_sentinel.py tests/test_warmstart.py tests/test_warmstart_streaming.py tests/test_window_overflow.py"
"09_android|tests/android/test_bridge.py tests/android/test_bridge_backend.py tests/android/test_wheel_build_tools.py"
"10_golden|tests/golden/test_golden.py"
"11_meeple_equiv|tests/test_meeple_equiv.py"
"12_exact_solver|tests/test_analyze_f13_ladder.py tests/test_endgame_solver.py tests/test_f13_exact_ladder.py tests/test_rustport_endgame_solver.py tests/test_solver_score_agent.py tests/test_solver_score_variants.py tests/test_wsweep_exact_solver.py"
"13_mcts|tests/test_ameneyro_mcts.py tests/test_heuristic_prior_mcts.py tests/test_mcts.py tests/test_mcts_transposition_c2.py tests/test_neural_mcts.py tests/test_neural_mcts_selfplay_extensions.py tests/test_neural_mcts_virtual_loss.py"
"14_selfplay|tests/test_anchor_fraction_selfplay.py tests/test_gen_fair_distill.py tests/test_run_phase4_smoke.py tests/test_selfplay.py tests/test_selfplay_claim.py"
"15a_fair_agent|tests/test_fair_agent.py"
"15b_fair_cand_curve_drift|tests/test_fair_cand_curve_drift.py"
"15c_fair_info_gate_zero|tests/test_fair_info_gate_zero.py"
"15d_fair_oracle_prior|tests/test_fair_oracle_prior.py"
"15e01_puct_deterministic_given_seed|tests/test_fair_puct_agent.py::test_puct_deterministic_given_seed"
"15e02_puct_seed_derivation_is_move_indexed|tests/test_fair_puct_agent.py::test_puct_seed_derivation_is_move_indexed"
"15e03_puct_choose_action_never_mutates_caller_boar|tests/test_fair_puct_agent.py::test_puct_choose_action_never_mutates_caller_board"
"15e04_puct_plays_full_legal_determinized_game|tests/test_fair_puct_agent.py::test_puct_plays_full_legal_determinized_game"
"15e05_puct_marginalized_handoff_fires_at_k2_and_la|tests/test_fair_puct_agent.py::test_puct_marginalized_handoff_fires_at_k2_and_latches"
"15e06_puct_no_solver_above_exact_max_k|tests/test_fair_puct_agent.py::test_puct_no_solver_above_exact_max_k"
"15e07_puct_exact_max_k_configurable_latches_at_k4|tests/test_fair_puct_agent.py::test_puct_exact_max_k_configurable_latches_at_k4"
"15e08_puct_exact_endgame_flag_gates_the_handoff|tests/test_fair_puct_agent.py::test_puct_exact_endgame_flag_gates_the_handoff"
"15e09_puct_k_dets_validation|tests/test_fair_puct_agent.py::test_puct_k_dets_validation"
"15e10_puct_batch_size_validation|tests/test_fair_puct_agent.py::test_puct_batch_size_validation"
"15e11_default_agent_constructs_neuralmcts_with_ser|tests/test_fair_puct_agent.py::test_default_agent_constructs_neuralmcts_with_serial_defaults"
"15e12_default_agent_never_enters_the_virtual_loss_|tests/test_fair_puct_agent.py::test_default_agent_never_enters_the_virtual_loss_path"
"15e13_default_agent_pick_matches_prebatch_golden|tests/test_fair_puct_agent.py::test_default_agent_pick_matches_prebatch_golden"
"15f_fair_puct_opponent|tests/test_fair_puct_opponent.py"
"15g_puct_priors_opponent_backend|tests/test_puct_priors_opponent_backend.py"
"15h_puct_priors_watchdog|tests/test_puct_priors_watchdog.py"
"16a_alphabeta_agent|tests/test_alphabeta_agent.py"
"16b_intra_reuse|tests/test_intra_reuse.py"
"16c_jcz_match|tests/test_jcz_match.py"
"16d_jcz_replay_oracle|tests/test_jcz_replay_oracle.py"
"16e_jcz_tile_oracle|tests/test_jcz_tile_oracle.py"
"16f_kparallel|tests/test_kparallel.py"
"16g_luck_floor_pairs|tests/test_luck_floor_pairs.py"
"16h_jcz_mining_analyze|tests/test_jcz_mining_analyze.py"
"16i_jcz_mining_extract|tests/test_jcz_mining_extract.py"
"17_rustport|tests/rustport"
)

if [ "${1:-}" = "--plan" ]; then
  for c in "${CHUNKS[@]}"; do
    n=${c%%|*}; f=${c#*|}
    echo "$n  ($(echo "$f" | wc -w) paths)"
  done
  exit 0
fi

mkdir -p "$OUT" "$CHUNKDIR/seam" "$CHUNKDIR/main"
log "chunked phase-seam gate starting; host=$(hostname) py=$PY"
"$PY" -V 2>&1 | sed "s/^/[gate] interpreter: /"

# ---------------------------- seam rust wheel -----------------------------
if [ ! -f "$WHEEL" ]; then
  log "seam wheel absent; rebuilding from the seam worktree (maturin build, release)"
  "$REPO/.venv/bin/maturin" build --release \
    -m "$WT/rust/carc/carc-py/Cargo.toml" -o "$WHEEL_DIR"
  rc=$?
  if [ "$rc" != 0 ]; then log "FATAL: wheel rebuild failed rc=$rc"; exit 2; fi
fi
if [ ! -d "$SHADOW" ] || [ -z "$(ls -A "$SHADOW" 2>/dev/null)" ]; then
  log "unpacking the seam's carc_rs wheel to a shadow dir (site-packages untouched)"
  rm -rf "$SHADOW"; mkdir -p "$SHADOW"
  "$PY" -c "import zipfile,sys;zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$WHEEL" "$SHADOW"
  rc=$?
  if [ "$rc" != 0 ]; then log "FATAL: could not unpack $WHEEL"; exit 2; fi
fi

# ------------------------------- preflight --------------------------------
# The chunk literal must cover exactly what pytest collects, on BOTH trees.
# A file present in the tree but absent from CHUNKS would be silently untested;
# a file in CHUNKS but absent from the tree makes a chunk error out. Fail loudly.
# NOTE ON THE TWO TREES NOT BEING FILE-IDENTICAL. 549c0d1 branched from an older
# main, so the sets differ in both directions: the seam ADDS
# tests/test_v29_phase_multiplier.py (the new feature's own tests), and main has
# two files the seam predates. The CHUNKS literal is therefore the UNION, and each
# leg runs the subset that exists in ITS tree. Dropping an absent file does not
# reorder the others, so import order for every SHARED file is still identical
# between the legs — which is the property the comparison actually needs.
# Consequences for the verdict, both in the safe direction:
#   * a seam-only test that fails is counted NOVEL. Correct: a failing test of the
#     new feature cannot be excused as pre-existing.
#   * if main FIXED something the seam still predates, that reads as novel too —
#     a possible false RED, never a false GREEN. RED is re-triaged by hand.
# What preflight enforces is the thing that would silently corrupt the gate: every
# test file present in a tree must appear in some chunk. Nothing untested.
preflight() {  # $1=label  $2=tree
  local label="$1" tree="$2" bad=0
  local listed actual unlisted
  # A chunk path may be a FILE or a pytest node id (file::test) -- 15e is split per
  # test because one of its tests alone wants ~6 GB. Compare on the file part only.
  listed=$(for c in "${CHUNKS[@]}"; do for p in ${c#*|}; do echo "${p%%::*}"; done; done | grep -v '^tests/rustport$' | sort -u)
  actual=$(cd "$tree" && find tests -name 'test_*.py' -not -path 'tests/rustport/*' | sort)
  unlisted=$(comm -13 <(echo "$listed") <(echo "$actual"))
  if [ -n "$unlisted" ]; then
    log "PREFLIGHT $label: test files present in the tree but in NO chunk (would go untested):"
    echo "$unlisted" | sed 's/^/[gate]   /'
    bad=1
  fi
  local only
  only=$(comm -23 <(echo "$listed") <(echo "$actual"))
  if [ -n "$only" ]; then
    log "PREFLIGHT $label: chunk paths absent from this tree (skipped on this leg, expected):"
    echo "$only" | sed 's/^/[gate]   /'
  fi
  return $bad
}
preflight seam "$WT"; pfs=$?
preflight main "$REPO"; pfm=$?
if [ "${1:-}" = "--preflight" ]; then
  log "preflight-only: seam=$pfs main=$pfm (0=ok)"; exit $((pfs + pfm))
fi
if [ "$pfs" != 0 ] || [ "$pfm" != 0 ]; then
  log "FATAL: preflight failed — chunk plan is stale. Fix CHUNKS, do not run a partial gate."
  echo "INCONCLUSIVE_STALE_CHUNK_PLAN" > "$OUT/VERDICT_BLOCKED"; exit 3
fi
log "preflight OK — chunk literal covers both trees exactly"

# ---------------------------- provenance stamp ----------------------------
prov() {  # $1=label $2=tree $3=pythonpath-prefix
  local pp="$2/src:$2/engine"
  [ -n "$3" ] && pp="$3:$pp"
  ( cd "$2" && PYTHONPATH="$pp" "$PY" -c "
import carcassonne_ai, sys
print('python:', sys.version.split()[0])
print('carcassonne_ai:', carcassonne_ai.__file__)
try:
    import carc_rs; print('carc_rs:', carc_rs.__file__)
except Exception as e: print('carc_rs import failed:', e)
" ) > "$OUT/${1}_provenance.txt" 2>&1
}
prov seam "$WT" "$SHADOW"
# main leg is STOCK: no PYTHONPATH at all, exactly as the serial gate ran it.
( cd "$REPO" && "$PY" -c "
import carcassonne_ai, sys
print('python:', sys.version.split()[0])
print('carcassonne_ai:', carcassonne_ai.__file__)
try:
    import carc_rs; print('carc_rs:', carc_rs.__file__)
except Exception as e: print('carc_rs import failed:', e)
" ) > "$OUT/main_provenance.txt" 2>&1

# ------------------------------- chunk runner -----------------------------
# Wrap in a cgroup memory scope when one is available. MemoryHigh throttles and
# forces reclaim well before MemoryMax kills, so the exact-solver chunk degrades
# to "slow" rather than "SIGKILL", which would read as a crash.
CAP_OK=0
if systemd-run --user --scope -p MemoryMax="$MEM_MAX" true >/dev/null 2>&1; then
  CAP_OK=1
  log "per-chunk memory scope ACTIVE (default High=$MEM_HIGH Max=$MEM_MAX Swap=0)"
else
  log "WARNING: systemd-run --user --scope unavailable; chunks run uncapped"
fi

# PER-CHUNK ALLOWANCES -- added 2026-08-09 after the seam/15_fair_puct incident.
#
# The default MemoryHigh=5G is a THROTTLE, not a kill: at the ceiling the cgroup
# forces reclaim and the process crawls instead of dying. The fair_puct tests
# legitimately build >5G of state, so the throttle turned a working chunk into a
# 63%-CPU crawl in uninterruptible reclaim (D state) that then blew the 3600 s
# budget and got SIGKILLed by `timeout`. Read from the outside that is
# indistinguishable from instability -- two attempts were lost that way, and NEITHER
# was a box problem. This is the ugliest failure shape a memory cap has: not a
# crash, but a silent slowdown that expires a deadline.
#
# Fix has two halves, because either alone is insufficient:
#   * the big-state families (fair_puct/puct_priors, and the alphabeta/jcz/kparallel
#     family that looks like its sibling) are split to ONE FILE PER CHUNK, so peak
#     RSS is bounded by the largest single module instead of their sum -- and if one
#     module is still too big, the artifact names say exactly which;
#   * those chunks get MemoryHigh=7G (headroom before throttling) with MemoryMax
#     held at 8G (the VM is 11G -- the hard cap is what stops a guest balloon from
#     killing the whole VM, and it stays), plus a 7200 s budget.
# A chunk that genuinely wants >8G now gets OOM-KILLED, which the time -v witness
# reports as a crash. That is the intended degradation: a loud, attributable death
# beats a silent stall.
# GATE_ONLY / GATE_DEFER / GATE_EXCLUDE are pipe-separated GLOB lists. They must be
# matched through this helper, never by interpolating the whole string into a `case`
# pattern: bash does NOT re-parse `|` as alternation when the pattern comes from a
# variable, so `case $n in ${VAR})` with VAR="a*|b*" silently matches NOTHING.
# Single-pattern knobs happened to work, which is exactly what kept the bug hidden.
# Failure direction was safe for EXCLUDE (cells just run) but NOT for DEFER -- a
# multi-pattern defer would have quietly attempted the cell it was meant to hold back.
matches_any() {  # $1=name  $2=pipe-separated glob list -> 0 if any matches
  local name="$1" pats="${2:-}" pat
  [ -z "$pats" ] && return 1
  local IFS='|'
  for pat in $pats; do
    case "$name" in $pat) return 0 ;; esac
  done
  return 1
}

chunk_limits() {  # $1=chunk name -> "MemoryHigh MemoryMax timeout_s"
  case "$1" in
    # 15e07 is the one genuinely large cell in the suite: test_puct_exact_max_k_
    # configurable_latches_at_k4 passed 6.5 GB RSS on its own and was still climbing
    # ~0.37 GB/min. It does NOT fit the 11.9 GB laptop VM under any cap that still
    # protects the VM, so this cell runs on the 41 GB local box for BOTH trees --
    # a documented box exception, kept internally valid by moving the seam and main
    # legs together. 16 GB is a deliberate ceiling, not a guess: if the cell needs
    # more than that, it is a finding to report, not a cap to keep raising.
    # MEASURED 2026-08-09: it passed 8.2 GB at 20 min and was still growing ~0.4
    # GB/min, so the ceiling was moved once, to 24 GB, on a 41 GB box. If a run
    # ever OOMs at 24 GB, STOP and report the cell as unbounded -- do not raise
    # again; the local VM dies around 34 GB (reference_wsl2_host_memory_teardown).
    15e07_*) echo "24G 24G 14400" ;;
    15*|16*) echo "7G 8G 7200" ;;
    *)                   echo "$MEM_HIGH $MEM_MAX $CHUNK_TIMEOUT" ;;
  esac
}

# /usr/bin/time -v is BOTH the peak-RSS instrument and the completion witness
# (see run_chunk). Without it the gate still works, on a weaker witness.
if [ -x /usr/bin/time ]; then
  TIMEV="/usr/bin/time -v"
else
  TIMEV=""
  log "WARNING: /usr/bin/time absent — no peak-RSS by-catch, weaker crash detection"
fi

run_chunk() {  # $1=tree-label  $2=tree-path  $3=pp-prefix  $4=chunk-name  $5=paths
  local label="$1" tree="$2" pre="$3" name="$4" paths="$5"
  local art="$CHUNKDIR/$label/$name.json"
  local txt="$CHUNKDIR/$label/$name.txt"
  if [ -f "$art" ]; then log "  [$label/$name] artifact exists — SKIP (resume)"; return 0; fi

  # Keep only the paths that exist in THIS tree (see the preflight note above).
  local kept="" p
  for p in $paths; do
    if [ -e "$tree/${p%%::*}" ]; then kept="$kept $p"; fi
  done
  if [ -z "$kept" ]; then
    log "  [$label/$name] no paths exist in this tree — recording empty artifact"
    echo "{\"chunk\":\"$name\",\"tree\":\"$label\",\"rc\":0,\"duration_s\":0,\"attempt\":0,\"n_failing\":0,\"failing_ids\":[],\"note\":\"no paths in this tree\"}" > "$art.tmp"
    mv -f "$art.tmp" "$art"; return 0
  fi
  paths="$kept"

  local c_high c_max c_to
  read -r c_high c_max c_to <<< "$(chunk_limits "$name")"
  local CAP=()
  if [ "$CAP_OK" = 1 ]; then
    CAP=(systemd-run --user --quiet --scope
         -p MemoryHigh="$c_high" -p MemoryMax="$c_max" -p MemorySwapMax=0)
  fi
  if [ "$c_to" != "$CHUNK_TIMEOUT" ]; then
    log "  [$label/$name] raised allowance: High=$c_high Max=$c_max timeout=${c_to}s"
  fi

  local attempt=1
  while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
    local t0 t1 rc dur
    t0=$(date +%s)
    log "  [$label/$name] running (attempt $attempt/$MAX_ATTEMPTS)"
    local pp=""
    if [ "$label" = seam ]; then pp="$pre:$tree/src:$tree/engine"; fi
    (
      cd "$tree" || exit 97
      if [ -n "$pp" ]; then export PYTHONPATH="$pp"; fi
      exec "${CAP[@]}" timeout -s KILL "$c_to" \
        $TIMEV nice -n 19 "$PY" -m pytest $paths -q -p no:randomly -p no:cacheprovider -rf --durations=10
    ) > "$txt" 2>&1
    rc=$?
    t1=$(date +%s); dur=$((t1 - t0))

    # DID THE CHUNK ACTUALLY FINISH? This has to be airtight in the direction that
    # matters: a chunk that DIED must never be read as a chunk with no failures.
    #
    # The obvious witness -- grepping pytest's terminal summary -- is WRONG, and
    # cost a poisoned chunk before it was caught on 2026-08-09: pytest 9.1 under
    # `-q` prints NO "N passed" line when nothing fails, so every clean chunk would
    # have been declared dead and the gate would have poisoned itself into
    # INCONCLUSIVE with a fully healthy suite.
    #
    # The reliable witness is /usr/bin/time -v, which prints its report only AFTER
    # wait4() reaps the child, and says explicitly how the child ended:
    #   "Exit status: N"                 -> normal termination (0 pass / 1 failures
    #                                       / 2 interrupted / 5 no tests -- all of
    #                                       these are COMPLETIONS we can read)
    #   "Command terminated by signal N" -> SIGKILL: OOM killer, the chunk timeout
    #   (neither line at all)            -> time itself never got to report: the
    #                                       whole process group went away, i.e. a
    #                                       VM teardown or a dirty reboot.
    # Only the first case earns an artifact.
    if [ -z "$TIMEV" ]; then
      # No /usr/bin/time on this box: fall back to the summary grep, which is
      # weaker (see above) but better than nothing.
      grep -qaE '[0-9]+ (passed|failed|error)|no tests ran|=+ (ERRORS|FAILURES) =+' "$txt"
      done_ok=$?
    elif grep -qa 'Command terminated by signal' "$txt"; then
      done_ok=1
    elif grep -qa 'Exit status:' "$txt"; then
      done_ok=0
    else
      done_ok=1
    fi
    if [ "$done_ok" = 0 ]; then
      local fails
      fails=$(grep -hE '^(FAILED|ERROR) ' "$txt" | awk '{print $2}' | sed 's/[[:space:]]*$//' | sort -u)
      local nf
      nf=$(printf '%s' "$fails" | grep -c . )
      # /usr/bin/time -v peak RSS, in kB. This is by-catch that either confirms or
      # refutes the "our own suite OOMed the host" hypothesis with numbers. A chunk
      # that walks up to MEM_MAX is a FINDING (which module, how big) -- record it,
      # never quietly raise the cap.
      local peak_kb
      peak_kb=$(grep -a 'Maximum resident set size' "$txt" | tail -1 | tr -dc '0-9')
      if [ -z "$peak_kb" ]; then peak_kb=0; fi
      if [ "$peak_kb" -gt 4194304 ]; then
        log "  [$label/$name] ⚠ PEAK RSS $((peak_kb / 1024)) MiB — within reach of MemoryMax=$MEM_MAX"
        echo "$(ts) $label/$name peak_rss_kb=$peak_kb" >> "$OUT/high_rss_chunks.txt"
      fi
      printf '%s\n' "$fails" | "$PY" -c '
import json, sys
path, name, tree, rc, dur, attempt = sys.argv[1:7]
ids = [l.strip() for l in sys.stdin.read().splitlines() if l.strip()]
json.dump({"chunk": name, "tree": tree, "rc": int(rc), "duration_s": int(dur),
           "attempt": int(attempt), "peak_rss_kb": int(sys.argv[7]),
           "n_failing": len(ids), "failing_ids": ids},
          open(path, "w"), indent=1)
' "$art.tmp" "$name" "$label" "$rc" "$dur" "$attempt" "$peak_kb"
      mv -f "$art.tmp" "$art"
      log "  [$label/$name] done rc=$rc ${dur}s failing=$nf peak_rss=$((peak_kb / 1024))MiB"
      return 0
    fi

    local how
    how=$(grep -a 'Command terminated by signal' "$txt" | tail -1)
    if [ -z "$how" ]; then how="no time-report at all (process group vanished)"; fi
    log "  [$label/$name] DIED (rc=$rc, ${dur}s): $how — retrying."
    echo "$(ts) attempt=$attempt rc=$rc dur=${dur}s died: $how" >> "$CHUNKDIR/$label/$name.crash"
    attempt=$((attempt + 1))
  done
  log "  [$label/$name] POISON — $MAX_ATTEMPTS attempts, never completed."
  return 1
}

run_tree() {  # $1=label $2=tree $3=pp-prefix
  local label="$1" poison=0
  log "=== $label tree: ${#CHUNKS[@]} chunks (serial, fresh process each) ==="
  for c in "${CHUNKS[@]}"; do
    # GATE_ONLY is a smoke-test hook (a regex over chunk names). Leave it UNSET for
    # a real gate: a filtered run reaches the verdict block with chunks missing and
    # would be withheld as INCONCLUSIVE, which is the intended safety behaviour.
    if [ -n "${GATE_ONLY:-}" ]; then
      matches_any "${c%%|*}" "${GATE_ONLY}" || continue
    fi
    # GATE_DEFER: skip a chunk WITHOUT attempting it. For a chunk under active
    # debugging, so the other 45 can make progress meanwhile instead of the whole
    # gate sitting behind one broken cell. A deferred chunk writes no artifact, so
    # the completeness guard keeps the verdict INCOMPLETE -- deferring can never
    # produce a verdict, only postpone one. Clear it before the final run.
    if [ -n "${GATE_DEFER:-}" ]; then
      if matches_any "${c%%|*}" "${GATE_DEFER}"; then
        log "  [$label/${c%%|*}] DEFERRED by GATE_DEFER"; continue
      fi
    fi
    # GATE_EXCLUDE: drop a cell from the gate ENTIRELY, on BOTH legs, and admit it
    # in the output. Unlike GATE_DEFER (which postpones and keeps the verdict
    # INCOMPLETE), this lets a verdict be reached with a hole in it -- so it is
    # only ever correct with the hole reported. Applied here, in the one loop that
    # runs both legs, so the exclusion cannot be asymmetric.
    if [ -n "${GATE_EXCLUDE:-}" ]; then
      if matches_any "${c%%|*}" "${GATE_EXCLUDE}"; then
        log "  [$label/${c%%|*}] EXCLUDED (coverage gap, both legs)"; continue
      fi
    fi
    run_chunk "$label" "$2" "$3" "${c%%|*}" "${c#*|}" || poison=1
  done
  return $poison
}

run_tree seam "$WT" "$SHADOW"; seam_poison=$?
run_tree main "$REPO" ""; main_poison=$?

NEXCL=0
EXCLUDED_NAMES=""
if [ -n "${GATE_EXCLUDE:-}" ]; then
  for c in "${CHUNKS[@]}"; do
    if matches_any "${c%%|*}" "${GATE_EXCLUDE}"; then
      NEXCL=$((NEXCL + 1)); EXCLUDED_NAMES="$EXCLUDED_NAMES ${c%%|*}"
    fi
  done
fi

# ------------------------------- the verdict -------------------------------
collect() {  # $1=label -> sorted unique failing ids
  "$PY" - "$CHUNKDIR/$1" <<'PYEOF'
import json, pathlib, sys
d = pathlib.Path(sys.argv[1])
ids = set()
for p in sorted(d.glob("*.json")):
    ids |= set(json.load(open(p))["failing_ids"])
print("\n".join(sorted(ids)))
PYEOF
}
collect seam > "$OUT/seam_failures.txt"
collect main > "$OUT/main_failures.txt"
comm -23 "$OUT/seam_failures.txt" "$OUT/main_failures.txt" > "$OUT/novel_failures.txt"

NS=$(grep -c . "$OUT/seam_failures.txt"); NM=$(grep -c . "$OUT/main_failures.txt")
NN=$(grep -c . "$OUT/novel_failures.txt")
{
  echo "phase-seam gate (chunked) — $(ts)"
  echo "host=$(hostname)  interpreter=$("$PY" -V 2>&1)"
  echo "seam tree : $WT  ($(git -C "$WT" rev-parse --short HEAD 2>/dev/null))"
  echo "main tree : $REPO ($(git -C "$REPO" rev-parse --short HEAD 2>/dev/null))"
  echo "chunks    : ${#CHUNKS[@]} per tree"
  if [ "$NEXCL" = 0 ]; then
    echo "BRANCH    : FULL -- every cell ran on both trees, no coverage gap"
  else
    echo "BRANCH    : PARTIAL -- $NEXCL cell(s) EXCLUDED from BOTH legs (coverage gap)"
    echo "excluded  :$EXCLUDED_NAMES"
    echo "  These cells were not run on either tree, so the gate makes NO claim"
    echo "  about them. The verdict below covers the remaining cells only."
  fi
  echo "failing on seam : $NS"
  echo "failing on main : $NM"
  echo "NOVEL to seam   : $NN"
} > "$OUT/gate_summary.txt"
cat "$OUT/gate_summary.txt" | sed 's/^/[gate] /'

# COMPLETENESS. A verdict is only admissible if EVERY chunk ran on BOTH trees.
# Without this, a GATE_ONLY-filtered smoke run (or any interrupted run whose caller
# jumped straight to the verdict block) would compute "0 novel" from a handful of
# chunks and write GREEN. Absence of evidence is not evidence of absence.
EXPECT=$(( (${#CHUNKS[@]} - NEXCL) * 2 ))
HAVE=$(ls "$CHUNKDIR"/seam/*.json "$CHUNKDIR"/main/*.json 2>/dev/null | wc -l)
if [ "$HAVE" != "$EXPECT" ]; then
  log "VERDICT WITHHELD: $HAVE/$EXPECT chunk artifacts present. Rerun to resume."
  echo "INCOMPLETE_${HAVE}_OF_${EXPECT}" > "$OUT/VERDICT_BLOCKED"
  exit 5
fi

if [ "$seam_poison" != 0 ] || [ "$main_poison" != 0 ]; then
  log "VERDICT WITHHELD: at least one chunk never completed. See $CHUNKDIR/*/*.crash"
  echo "INCONCLUSIVE" > "$OUT/VERDICT_BLOCKED"
  exit 4
fi

if [ "$NEXCL" != 0 ]; then
  {
    echo "COVERAGE GAP — this gate did NOT cover every cell."
    echo "VERDICT is GREEN_WITH_GAP: the merge is HELD for owner review, by design."
    echo "excluded from BOTH legs:$EXCLUDED_NAMES"
    echo
    echo "Why: the cell could not be run within a memory ceiling that is safe on"
    echo "any available box. The ceiling was not raised further because the cap"
    echo "lives inside the WSL VM that the work itself runs in, so cap creep risks"
    echo "the session, not just the cell."
    echo
    echo "Residual risk argument (why a verdict is still worth having): the seam"
    echo "under test is a DEFAULT-OFF leaf phase multiplier; the excluded cell is"
    echo "an exact_max_k latch test; and its test file is byte-identical across the"
    echo "two trees. So the excluded cell is unlikely to be where a seam-induced"
    echo "regression would show. That is an argument for accepting a KNOWN gap --"
    echo "it is not evidence the cell passes."
    echo
    echo "WHAT HAPPENS NEXT: night_chain refuses any verdict that is not exactly"
    echo "GREEN, so it stamps PHASE_ARM_BLOCKED and stops before the merge. In THIS"
    echo "case that marker means HELD-FOR-REVIEW, not seam-failed -- the diff over"
    echo "the cells that DID run was clean. Joshua decides whether to accept the gap"
    echo "and merge, or to close it first."
  } > "$OUT/COVERAGE_GAP.txt"
  log "COVERAGE GAP recorded:$EXCLUDED_NAMES"
fi

# The VERDICT file stays a SINGLE bare token -- night_chain.sh reads it as
# `V=$(cat VERDICT)` and branches on `[ "$V" != "GREEN" ]`, so any extra text would
# read as a failed gate. The partial branch exploits exactly that: GREEN_WITH_GAP
# is refused by the EXISTING check, so a known coverage gap can never ride an
# automatic merge through while the owner is away. No new trust in a new path.
if [ "$NN" = 0 ] && [ "$NEXCL" != 0 ]; then
  log "VERDICT: GREEN_WITH_GAP — no novel failures among the cells that ran, but"
  log "  $NEXCL cell(s) were excluded. Merge HELD for owner review."
  echo GREEN_WITH_GAP > "$OUT/VERDICT"
elif [ "$NN" = 0 ]; then
  log "VERDICT: GREEN — every seam-side failure also fails on main (pre-existing)."
  echo GREEN > "$OUT/VERDICT"
else
  log "VERDICT: RED — failures novel to the seam:"
  sed 's/^/[gate]   /' "$OUT/novel_failures.txt"
  echo RED > "$OUT/VERDICT"
fi
log "artifacts in $OUT"
