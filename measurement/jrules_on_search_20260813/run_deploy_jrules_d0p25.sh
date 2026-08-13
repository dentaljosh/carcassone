#!/usr/bin/env bash
# J-RULES ON SEARCH — DEPLOY-BUDGET CELL, TWO-BOX WORK-STEALING LAUNCH CHAIN.
#
# Pre-registration of record: measurement/jrules_on_search_20260813/DEPLOY_PREREG.md (f5b962f)
# Design of record:           measurement/jrules_on_search_20260813/DESIGN.md §8/§9/§11
# Band row:                   governance/BAND_REGISTRY.csv, band_seed_start 128000000000
#
# ONE cell, ONE dose, split across TWO boxes by `--shared-claim` work-stealing:
#
#   cell      jrules_d0p25_deploy11008
#   candidate production champion leaf + the jrules bundle, jrules_dose 0.25,
#             jrules_mask DEFAULT 31 (JR_ALL = J1|J2|J5|J6|J8, NOT written in the cell JSON)
#             cand_leaf_hash 15948beccf3472d3
#   opponent  the UNMODIFIED production champion, opp_leaf_hash a36d2e15a3b3d71d
#   budget    k8 x 1376 = 11008 on BOTH arms
#   backend   rust, both sides · rules fixed_v1 + CARCASSONNE_FIX_R9=1 · exact-K 2
#   n         800 deck-paired = 400 decks x 2 seats, CRN
#   band      1.28e11, seeds 128000000000 .. 128000000399
#   boxes     local (5900XT) W14  +  laptop-wsl W16, ONE shared output dir on the share,
#             so the two boxes split the 800 games with no coordination and either box
#             finishing alone still completes the cell.
#
# ⚠️ THIS SCRIPT ADJUDICATES NOTHING. It runs games and writes records. It does NOT run
#    menu_block_summary.py, does not compute elo or a margin, does not touch
#    governance/PRODUCTION.yaml, governance/BAND_REGISTRY.csv, experiments/results.csv or
#    any claim row, and prints no verdict. DEPLOY_PREREG §5 rule 1 requires the N0 wiring
#    gates to be read from the manifest BEFORE any strength number is opened, so this
#    driver emits GATES_<cell>.json — pass/fail ONLY, with no strength statistic anywhere
#    in it — and leaves the summary to a separate reading session. That ordering is the
#    point, and it is why the summary step is deliberately absent.
#
# ⚠️ THE BAND IS HARDCODED AND TAKES NO ARGUMENT. DEPLOY_PREREG §3 pins band 1.28e11 and
#    seeds 128000000000..128000000399 by content; a band flag is exactly how a cell ends up
#    on a decision-influenced band. Changing it means writing a new pre-registration.
#
# ── HOW TO LAUNCH (from the LOCAL box; the laptop leg is dispatched from here) ───────────
#
#   setsid nohup nice -n 19 bash \
#     /home/doctor/projects/carcassone/measurement/jrules_on_search_20260813/run_deploy_jrules_d0p25.sh \
#     >> /home/doctor/projects/carcassone/measurement/jrules_on_search_20260813/logs/chain.log 2>&1 < /dev/null &
#   disown
#
#   `setsid` + `nohup` + `disown` are all three required: the harness's own background flag
#   is NOT enough — Mac-sleep SIGHUP and WSL VM teardown both kill tty-attached jobs.
#
# ── OPTIONS (env or flags) ──────────────────────────────────────────────────────────────
#   --dry-run        run every gate, print the resolved commands, launch NOTHING
#   --no-laptop      local box only (the laptop's G3 wheel gate is owed per box)
#   --laptop-only    dispatch the laptop leg and exit — use to JOIN the laptop to a chain
#                    that is already running local-only (e.g. after its wheel is rebuilt)
#   JR_W_LOCAL=14  JR_W_LAPTOP=16  JR_LAPTOP_SSH=laptop-wsl  JR_LAPTOP_MEMMAX=8G
#
# RESUMABLE AND RESTART-SAFE. menu_fair_cell.sh counts seed*.json in the SHARED dir and
# loops until 800 exist, so a relaunched chain resumes rather than restarting, and a claim
# left by a killed box is swept by menu_fair_cell's own claims-without-records sweeper.
# That is what makes the watchdog (jrules_d0p25_watchdog.sh) safe to arm.
set -u

REPO=/home/doctor/projects/carcassone
PY=$REPO/.venv/bin/python
DIR=$REPO/measurement/jrules_on_search_20260813
LOGS=$DIR/logs
VERDICTS=$DIR/verdicts

# ── pre-registered constants. Changing ANY of these voids DEPLOY_PREREG.md. ─────────────
BAND=128000000000
N=800
SUB=jrules_d0p25_deploy11008
OUT_NAME=jrules_deploy_20260813
CELLJSON=$DIR/cells/jrules_d0p25_deploy_fixed_v1_vs_fairchamp11008.json
EXPECT_CAND_HASH=15948beccf3472d3
CHAMP_HASH=a36d2e15a3b3d71d
EXPECT_DOSE=0.25
EXPECT_MASK=31
KDETS=8; SIMS=1376; EXACTK=2
# The moved-hash trap, recorded here so the gate below cannot be "simplified" away:
# {jrules_dose 0.0, jrules_mask 27} hashes to 92ac0da996e1b37b — NOT the champion — because
# _LEAF_HASH_EXCLUDE_IF_DEFAULT drops a field only while it holds its DEFAULT value. Such a
# cell would sail through any "the candidate hash moved" check while running
# champion-vs-champion and reading as a beautiful, meaningless null. The gate that proves
# the dose is LIVE is the RESOLVED jrules_dose VALUE, never the hash alone.
TRAP_HASH=92ac0da996e1b37b

W_LOCAL="${JR_W_LOCAL:-14}"
W_LAPTOP="${JR_W_LAPTOP:-16}"
LAPTOP_SSH="${JR_LAPTOP_SSH:-laptop-wsl}"
LAPTOP_MEMMAX="${JR_LAPTOP_MEMMAX:-8G}"

DRYRUN=0; DO_LOCAL=1; DO_LAPTOP=1
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)     DRYRUN=1; shift ;;
    --no-laptop)   DO_LAPTOP=0; shift ;;
    --laptop-only) DO_LOCAL=0; shift ;;
    *) echo "unknown arg '$1' (this chain takes NO band argument — the band is pinned by DEPLOY_PREREG §3)"; exit 2 ;;
  esac
done

mkdir -p "$LOGS" "$VERDICTS" || exit 9
ts() { date '+%F %T'; }
log() { echo "[jrules-d0p25 $(ts)] $*"; }

log "=== START chain (band $BAND, n=$N, cell $SUB) ==="
log "host=$(hostname) repo_head=$(git -C "$REPO" rev-parse --short HEAD) branch=$(git -C "$REPO" rev-parse --abbrev-ref HEAD)"
log "local W=$W_LOCAL  laptop W=$W_LAPTOP  do_local=$DO_LOCAL do_laptop=$DO_LAPTOP dry_run=$DRYRUN"

if [ -f "$DIR/DONE_$SUB" ]; then
  log "DONE_$SUB marker already present — cell complete, nothing to do."
  exit 0
fi

# ─────────────────────────────────────────────────────────────────────────────────────────
# Share mount — resolve BY CONTENT, never by directory existence, never by a default.
#
# ⚠️ /mnt/c/carc-shared AND /mnt/carc-shared BOTH EXIST ON THE LAPTOP and are different
# filesystems: /mnt/c/carc-shared there is drvfs of the LAPTOP'S OWN C:\ (measured: 1 entry,
# no data), while /mnt/carc-shared is the cifs mount of //192.168.0.195/carc-shared (369
# entries, the real share). `[ -d ]` therefore CANNOT tell them apart — only content can.
# Pattern copied from measurement/window_truncation_20260813/RUN_CMD.sh, whose first version
# died rc=13 on exactly this. Sentinel verified 2026-08-13 to be present on the cifs share
# and ABSENT from the laptop's drvfs C: mount.
# ─────────────────────────────────────────────────────────────────────────────────────────
SHARE_CANDIDATES="${JR_SHARE_CANDIDATES:-/mnt/c/carc-shared /mnt/carc-shared}"   # allow-path
SHARE_SENTINEL="${JR_SHARE_SENTINEL:-BAND_CLAIMS.txt}"
# ⚠️ SETS THE GLOBAL `SHARE`; it does NOT print the answer. An earlier version returned the
# path on stdout and was called as `SHARE=$(resolve_share)` — which captured the probe's own
# log lines into $SHARE and produced an --out-root with newlines and timestamps embedded in
# it. Caught by --dry-run before any game. Keep the assignment, not a command substitution.
SHARE=""
resolve_share() {
  local cand
  for cand in $SHARE_CANDIDATES; do
    if [ ! -d "$cand" ]; then
      log "  share candidate $cand: REJECTED (not a directory)"
    elif [ ! -f "$cand/$SHARE_SENTINEL" ]; then
      log "  share candidate $cand: REJECTED (exists, but no sentinel '$SHARE_SENTINEL' — $(ls -A "$cand" 2>/dev/null | wc -l | tr -d ' ') entries; wrong mount for this box)"
    elif [ -z "$SHARE" ]; then
      SHARE="$cand"; log "  share candidate $cand: ACCEPTED (sentinel present)"
    else
      log "  share candidate $cand: also has the sentinel; keeping $SHARE (first match wins)"
    fi
  done
  [ -n "$SHARE" ]
}
resolve_share || {
  log "FATAL: no share mount carries the sentinel '$SHARE_SENTINEL'. Candidates: $SHARE_CANDIDATES"
  log "       Refusing to guess a default — a hardcoded default is exactly how a job ends up"
  log "       writing records into an empty directory on the wrong box."
  exit 10
}
case "$SHARE" in *[!A-Za-z0-9/_.-]*) log "FATAL: resolved share '$SHARE' contains unexpected characters"; exit 10 ;; esac
OUT_ROOT="$SHARE/$OUT_NAME"
OUT_DIR="$OUT_ROOT/$SUB"
log "share resolved: $SHARE   out=$OUT_DIR"

# ─────────────────────────────────────────────────────────────────────────────────────────
# The launcher ENV CANON — byte-identical to scripts/classical_search/menu_fair_cell.sh.
# It must be exported HERE too, because the O0 hash gate below is only meaningful if it is
# computed under the same env the harness will run under: the point of O0 is that the
# champion resolves to a36d2e15a3b3d71d IN THE SAME PROCESS that resolves the candidate to
# 15948beccf3472d3, which is what proves the env was not mangled.
# ─────────────────────────────────────────────────────────────────────────────────────────
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export CARCASSONNE_FIX_R9=1

# ─────────────────────────────────────────────────────────────────────────────────────────
# O0 — the per-box leaf gate. NOT just "the hash moved" (see TRAP_HASH above).
# ─────────────────────────────────────────────────────────────────────────────────────────
# The gate body lives in o0_leaf_gate.py so BOTH boxes run byte-identical code — a
# reimplementation per box is how the two drift and one of them stops catching the trap.
o0_gate() {                # o0_gate <label> -> writes $VERDICTS/O0_<label>.json, rc 0/1
  local label="$1"
  CELLJSON="$CELLJSON" EXPECT_CAND_HASH="$EXPECT_CAND_HASH" CHAMP_HASH="$CHAMP_HASH" \
  EXPECT_DOSE="$EXPECT_DOSE" EXPECT_MASK="$EXPECT_MASK" TRAP_HASH="$TRAP_HASH" \
  "$PY" "$DIR/o0_leaf_gate.py" "$VERDICTS/O0_$label.json"
}

# ─────────────────────────────────────────────────────────────────────────────────────────
# LOCAL pre-flight
# ─────────────────────────────────────────────────────────────────────────────────────────
[ -x "$PY" ]        || { log "FATAL: venv python missing at $PY"; exit 11; }
[ -f "$CELLJSON" ]  || { log "FATAL: cell JSON missing at $CELLJSON"; exit 12; }
grep -q "^$BAND," "$REPO/governance/BAND_REGISTRY.csv" \
  || { log "FATAL: band $BAND is not claimed in governance/BAND_REGISTRY.csv. Refusing to burn an unregistered band."; exit 13; }
log "band $BAND present in governance/BAND_REGISTRY.csv (read-only check; this chain never writes it)"

if [ "$DO_LOCAL" = 1 ]; then
  log "--- LOCAL gate O0 (leaf hashes under the launcher env canon) ---"
  if ! o0_gate local; then
    log "!!! FATAL: LOCAL O0 gate FAILED — see $VERDICTS/O0_local.json. Nothing launched."
    exit 20
  fi
  log "LOCAL O0 PASS -> $VERDICTS/O0_local.json"

  log "--- LOCAL gate G4 (chain_capability_probe.py --require jrules --doses 0.25) ---"
  if ! "$PY" "$REPO/scripts/classical_search/chain_capability_probe.py" \
        --require jrules --doses 0.25 \
        --json-out "$VERDICTS/G4_probe_local.json" > "$LOGS/g4_probe_local.log" 2>&1; then
    log "!!! FATAL: LOCAL G4 capability probe FAILED (rc!=0) — see $VERDICTS/G4_probe_local.json"
    log "    A probe failure means the box would run champion-vs-champion or crash. Nothing launched."
    exit 21
  fi
  log "LOCAL G4 PASS -> $VERDICTS/G4_probe_local.json"
fi

# ─────────────────────────────────────────────────────────────────────────────────────────
# CHAIN MANIFEST — the self-describing record of the LAUNCH-side resolved config.
#
# ⚠️ This is NOT the manifest the prereg's N0 gate reads. eval_fair_puct writes the
# authoritative per-cell manifest.json into $OUT_DIR itself (cand_leaf_hash, opp_leaf_hash,
# cand_leaf_cfg, both arms' budgets, rules_profile, backend, band/pairing) and N0 is read
# from THAT file. This one records what the launch chain resolved — boxes, worker counts,
# share mounts, git revs, gate outcomes — which the cell manifest cannot know.
# ─────────────────────────────────────────────────────────────────────────────────────────
CHAIN_MANIFEST="$DIR/CHAIN_MANIFEST.json"
{
  cat <<JSON
{
  "schema": "carcassonne-jrules-deploy-chain/manifest/v1",
  "written": "$(date -Is)",
  "cell": "$SUB",
  "prereg": "measurement/jrules_on_search_20260813/DEPLOY_PREREG.md",
  "design": "measurement/jrules_on_search_20260813/DESIGN.md",
  "band_row": "governance/BAND_REGISTRY.csv:$BAND",
  "launch_host": "$(hostname)",
  "git": {"rev": "$(git -C "$REPO" rev-parse HEAD)",
          "short": "$(git -C "$REPO" rev-parse --short HEAD)",
          "branch": "$(git -C "$REPO" rev-parse --abbrev-ref HEAD)",
          "dirty": $( [ -n "$(git -C "$REPO" status --porcelain 2>/dev/null)" ] && echo true || echo false )},
  "candidate": {
    "cand_leaf_json": "$CELLJSON",
    "cand_leaf_json_sha256": "$(sha256sum "$CELLJSON" | cut -d' ' -f1)",
    "cand_leaf_json_content": $(cat "$CELLJSON"),
    "expected_cand_leaf_hash": "$EXPECT_CAND_HASH",
    "jrules_dose": $EXPECT_DOSE,
    "jrules_mask": $EXPECT_MASK,
    "jrules_mask_key_present_in_cell_json": false,
    "curve_drift_flag": "--allow-cand-curve-drift (curve125 verbatim; a no-op proved by O0)"
  },
  "opponent": {"leaf": "UNMODIFIED production champion", "expected_opp_leaf_hash": "$CHAMP_HASH"},
  "budget": {"k_dets": $KDETS, "sims_per_det": $SIMS, "total_sims": $((KDETS * SIMS)),
             "both_arms": true, "exact_k": $EXACTK, "exact_k_shared_by_both_arms": true},
  "search_knobs": {"c_puct": 1.5, "tau_p": 5, "leaf_quantize": "float", "final_select": "visits"},
  "rules": {"profile": "fixed_v1", "CARCASSONNE_FIX_R9": "1"},
  "backend": {"requested": "rust", "both_sides": true},
  "sampling": {"n": $N, "n_decks": $((N / 2)), "seatings_per_deck": 2, "paired": true,
               "crn": true, "band_seed_start": $BAND,
               "deck_seeds": "$BAND..$((BAND + N / 2 - 1))"},
  "harness": "scripts/classical_search/eval_fair_puct.py --info fair --opponent fair-champion, via scripts/classical_search/menu_fair_cell.sh",
  "work_split": {
    "mode": "--shared-claim work-stealing on ONE shared output dir (no coordination; either box alone still completes the cell)",
    "claim_stale_secs": 900,
    "boxes": [
      {"box": "local", "role": "primary", "workers": $W_LOCAL, "share": "$SHARE", "nice": 19, "enabled": $( [ "$DO_LOCAL" = 1 ] && echo true || echo false )},
      {"box": "laptop", "ssh": "$LAPTOP_SSH", "role": "helper", "workers": $W_LAPTOP, "share": "/mnt/carc-shared", "nice": 19, "mem_max": "$LAPTOP_MEMMAX", "enabled": $( [ "$DO_LAPTOP" = 1 ] && echo true || echo false )}
    ]
  },
  "out_dir_local_view": "$OUT_DIR",
  "gates": {"O0_local": "verdicts/O0_local.json", "G4_local": "verdicts/G4_probe_local.json",
            "O0_laptop": "verdicts/O0_laptop.json", "G3_laptop": "verdicts/G3_reconcile_laptop.json",
            "G4_laptop": "verdicts/G4_probe_laptop.json",
            "N0_wiring": "verdicts/GATES_$SUB.json"},
  "results_csv_row": false, "claim_row": false, "promotes": false,
  "touches_production_yaml": false, "adjudicates": false,
  "authoritative_cell_manifest": "$OUT_DIR/manifest.json",
  "note": "LAUNCH-SIDE manifest. The prereg N0 gate is read from the eval_fair_puct manifest at authoritative_cell_manifest, NOT from this file. This chain runs games and writes records; reading happens separately, after N0."
}
JSON
} > "$CHAIN_MANIFEST"
log "chain manifest -> $CHAIN_MANIFEST"

# ─────────────────────────────────────────────────────────────────────────────────────────
# The harness invocation, identical on both boxes except <W> and the box tag.
# ─────────────────────────────────────────────────────────────────────────────────────────
cell_args() {              # cell_args <W> <local|laptop>
  printf '%s ' "$1" "$2" \
    --sub "$SUB" --n "$N" --band "$BAND" \
    --k-dets "$KDETS" --sims "$SIMS" --opp-k-dets "$KDETS" --opp-sims "$SIMS" \
    --exact-k "$EXACTK" \
    --cand-leaf-json "$CELLJSON" --drift
}

# ─────────────────────────────────────────────────────────────────────────────────────────
# LAPTOP leg — dispatched from here. Bundle-sync first (remotes cannot reach github; stale
# code is a contaminated cell), then a real script piped with `cd` on line 1.
#
# ⚠️ NEVER an inline `ssh host 'cd /path && ...'` — Claude Code strips the `cd` in transit
#    and the remote command then runs from $HOME. Always `ssh host 'bash -s' < file`.
# ⚠️ The laptop's G3 (wheel rebuilt + reconcile 0 mismatches) is owed PER BOX and was NOT
#    cleared there as of 2026-08-13 (its carc_rs predates the term: leaf_config_rs raises
#    TypeError, fail-closed). The gates below run ON THE LAPTOP and refuse to launch if it
#    is still stale. A laptop-gate failure is NOT fatal to the cell: the local leg simply
#    runs it alone, and `--laptop-only` joins the laptop later once the wheel lands.
# ─────────────────────────────────────────────────────────────────────────────────────────
dispatch_laptop() {
  local branch remote_head bundle bpath ahead remote rc
  branch=$(git -C "$REPO" rev-parse --abbrev-ref HEAD)
  mkdir -p "$SHARE/bundles" "$DIR/dispatch"

  remote_head=$(timeout 60 ssh -o BatchMode=yes -o ConnectTimeout=15 "$LAPTOP_SSH" \
                  "git -C $REPO rev-parse HEAD" 2>/dev/null | tr -d '\r\n ')
  bundle=""
  if [ "$DRYRUN" = 1 ]; then
    log "  [dry-run] skipping bundle creation (laptop HEAD reported: ${remote_head:-unreachable})"
  elif [ -n "$remote_head" ] && git -C "$REPO" cat-file -e "${remote_head}^{commit}" 2>/dev/null; then
    ahead=$(git -C "$REPO" rev-list --count "${remote_head}..${branch}" 2>/dev/null || echo 0)
    if [ "${ahead:-0}" -eq 0 ]; then
      log "  laptop already at $remote_head (0 commits behind $branch) — no bundle needed"
    else
      bundle="jrules_d0p25_$(date +%Y%m%d_%H%M%S).bundle"; bpath="$SHARE/bundles/$bundle"
      git -C "$REPO" bundle create "$bpath" "^$remote_head" "$branch" >>"$LOGS/dispatch_laptop.log" 2>&1 || {
        log "  incremental bundle failed — falling back to a full bundle"
        git -C "$REPO" bundle create "$bpath" "$branch" >>"$LOGS/dispatch_laptop.log" 2>&1 || {
          log "  !! BUNDLE FAILED — refusing to dispatch to the laptop with stale code"; return 1; }; }
      log "  bundle $bundle ($ahead commit(s) ahead of the laptop)"
    fi
  else
    bundle="jrules_d0p25_$(date +%Y%m%d_%H%M%S).bundle"; bpath="$SHARE/bundles/$bundle"
    git -C "$REPO" bundle create "$bpath" "$branch" >>"$LOGS/dispatch_laptop.log" 2>&1 || {
      log "  !! BUNDLE FAILED — refusing to dispatch to the laptop with stale code"; return 1; }
    log "  full bundle $bundle (laptop HEAD unknown or not in our history)"
  fi

  remote="$DIR/dispatch/laptop_leg.sh"
  {
    echo "cd $REPO || exit 9"          # ← cd on line 1, ALWAYS. Never inline over ssh.
    echo 'set -u'
    echo "REPO=$REPO"
    echo "DIR=$DIR"
    echo "PY=$PY"
    if [ -n "$bundle" ]; then
      cat <<EOF
BUNDLE="/mnt/carc-shared/bundles/$bundle"
[ -f "\$BUNDLE" ] || { echo "bundle \$BUNDLE not visible from the laptop" >&2; exit 3; }
drift=\$(( \$(date +%s) - \$(stat -c %Y "\$BUNDLE") )); drift=\${drift#-}
if [ "\$drift" -gt 300 ]; then
  echo "CLOCK DRIFT \${drift}s vs bundle mtime — a drifted client STEALS every sibling claim. Fix with date -s first." >&2
  exit 4
fi
# ⚠️ REFUSE TO reset --hard OVER UNCOMMITTED WORK. Another session may be mid-rebuild of
# the carc_rs wheel on this box (G3 is owed per box), and a blind reset would silently
# destroy its tracked edits. A dirty laptop tree is a HUMAN decision, not a sync failure:
# fail loudly and let the local leg run alone rather than clobber someone's work.
dirty=\$(git status --porcelain 2>/dev/null | head -20)
if [ -n "\$dirty" ]; then
  echo "LAPTOP SYNC REFUSED: the laptop repo has uncommitted changes and syncing would" >&2
  echo "  'git reset --hard' over them. Someone may be mid-rebuild here. Resolve by hand," >&2
  echo "  then re-join with: bash $DIR/run_deploy_jrules_d0p25.sh --laptop-only" >&2
  echo "\$dirty" >&2
  exit 6
fi
git fetch "\$BUNDLE" $branch || exit 5
git reset --hard FETCH_HEAD  || exit 5
echo "laptop synced to \$(git rev-parse --short HEAD)"
EOF
    fi
    cat <<'EOF'
# ---- the launcher env canon, byte-identical to menu_fair_cell.sh -----------------------
export CARCASSONNE_V25_CAP=8 CARCASSONNE_V25_OPP_CAP=8 CARCASSONNE_V25_DROP_THREE_OPEN=0
export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25 CARCASSONNE_V25_MEEPLE_K=2.0
export CARCASSONNE_USE_FLAT_LEAF=1 CARCASSONNE_USE_CY_REPR=1 CARCASSONNE_USE_CY_LEAF=1 CARCASSONNE_V25_VALUE_BLEND=0
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export CARCASSONNE_FIX_R9=1

mkdir -p "$DIR/verdicts" "$DIR/logs"

# ---- share resolution ON THE LAPTOP, by content. BOTH candidate paths exist here. ------
SHARE=""
for cand in /mnt/c/carc-shared /mnt/carc-shared; do   # allow-path
  [ -d "$cand" ] || { echo "  laptop share candidate $cand: REJECTED (not a directory)"; continue; }
  if [ ! -f "$cand/BAND_CLAIMS.txt" ]; then
    echo "  laptop share candidate $cand: REJECTED (no sentinel; $(ls -A "$cand" 2>/dev/null | wc -l) entries — this is the laptop's own C:, not the share)"
  elif [ -z "$SHARE" ]; then
    SHARE="$cand"; echo "  laptop share candidate $cand: ACCEPTED (sentinel present)"
  fi
done
[ -n "$SHARE" ] || { echo "FATAL: no laptop share mount carries BAND_CLAIMS.txt — refusing to guess" >&2; exit 10; }

# ---- G3 (per box): the wheel really carries the term, and Rust == Python on the corpus.
# This is the SOLE Rust-parity guard for jrules (test_rust_parity_spot_check skips
# STRUCTURALLY — carc_rs exposes no direct leaf entry point — so it will never become a
# pass on any rebuilt box). A stale wheel here is fail-closed, but a launcher that swallowed
# it would produce a champion-vs-champion cell reading as "the strategy is worth nothing"
# rather than "it never ran".
echo "--- laptop G3: reconcile_leaf.py --configs jrules --corpus golden ---"
if ! "$PY" "$REPO/scripts/rustport/reconcile_leaf.py" --configs jrules --corpus golden \
        --workers 8 --out "$DIR/verdicts/G3_reconcile_laptop.json" \
        > "$DIR/logs/g3_reconcile_laptop.log" 2>&1; then
  echo "LAPTOP GATE FAIL: G3 reconcile FAILED — the carc_rs wheel is stale or Rust/Python diverge." >&2
  echo "  see $DIR/logs/g3_reconcile_laptop.log" >&2
  exit 30
fi
echo "laptop G3 PASS"

echo "--- laptop G4: chain_capability_probe.py --require jrules --doses 0.25 ---"
if ! "$PY" "$REPO/scripts/classical_search/chain_capability_probe.py" \
        --require jrules --doses 0.25 \
        --json-out "$DIR/verdicts/G4_probe_laptop.json" \
        > "$DIR/logs/g4_probe_laptop.log" 2>&1; then
  echo "LAPTOP GATE FAIL: G4 capability probe FAILED — see $DIR/verdicts/G4_probe_laptop.json" >&2
  exit 31
fi
echo "laptop G4 PASS"
EOF
    # O0 on the laptop, same gate script the local box ran (dose-LIVE, not hash-moved).
    cat <<EOF
echo "--- laptop O0: leaf hashes under the launcher env canon ---"
CELLJSON=$CELLJSON EXPECT_CAND_HASH=$EXPECT_CAND_HASH CHAMP_HASH=$CHAMP_HASH \\
EXPECT_DOSE=$EXPECT_DOSE EXPECT_MASK=$EXPECT_MASK TRAP_HASH=$TRAP_HASH \\
"\$PY" "$DIR/o0_leaf_gate.py" "$DIR/verdicts/O0_laptop.json" || {
  echo "LAPTOP GATE FAIL: O0 leaf gate FAILED — see $DIR/verdicts/O0_laptop.json" >&2; exit 32; }
echo "laptop O0 PASS"

# ---- launch, DETACHED and memory-capped ------------------------------------------------
# setsid + nohup + disown: the laptop VM is torn down by Windows memory pressure and a
# systemd --user scope dies with the last ssh session, so the job must outlive this ssh.
mkdir -p "\$SHARE/$OUT_NAME/$SUB"
MENU_OUT_ROOT="\$SHARE/$OUT_NAME" setsid nohup systemd-run --user --scope -p MemoryMax=$LAPTOP_MEMMAX \\
  nice -n 19 bash "$REPO/scripts/classical_search/menu_fair_cell.sh" \\
    $(cell_args "$W_LAPTOP" laptop) \\
  >> "$DIR/logs/cell_laptop.log" 2>&1 < /dev/null &
disown
echo "laptop leg LAUNCHED detached (W=$W_LAPTOP, MemoryMax=$LAPTOP_MEMMAX) -> \$SHARE/$OUT_NAME/$SUB"
EOF
  } > "$remote"

  if [ "$DRYRUN" = 1 ]; then
    log "[dry-run] laptop leg script written to $remote (NOT dispatched). Contents:"
    sed 's/^/    | /' "$remote"
    return 0
  fi

  log "  dispatching: ssh $LAPTOP_SSH 'bash -s' < $remote"
  timeout 900 ssh -o BatchMode=yes -o ConnectTimeout=15 "$LAPTOP_SSH" 'bash -s' < "$remote" \
    >> "$LOGS/dispatch_laptop.log" 2>&1
  rc=$?
  log "  laptop dispatch rc=$rc (log: $LOGS/dispatch_laptop.log)"
  return $rc
}

if [ "$DO_LAPTOP" = 1 ]; then
  log "--- LAPTOP leg dispatch ---"
  if dispatch_laptop; then
    if [ "$DRYRUN" = 1 ]; then
      log "[dry-run] laptop leg script generated and NOT dispatched"
    else
      log "LAPTOP leg dispatched OK (W=$W_LAPTOP)"
      echo "$(ts) dispatched W=$W_LAPTOP" > "$DIR/LAPTOP_DISPATCHED"
    fi
  elif [ "$DRYRUN" = 1 ]; then
    log "[dry-run] laptop leg script generation failed"
  else
    log "!!! LAPTOP leg NOT started (gate failure, sync failure, or box unreachable)."
    log "    This is NOT fatal: the local leg completes the cell alone, just slower."
    log "    Re-join the laptop later (e.g. once its carc_rs wheel is rebuilt) with:"
    log "      bash $DIR/run_deploy_jrules_d0p25.sh --laptop-only"
    { echo "$(ts)"; echo "laptop leg refused or failed to launch"; echo "see $LOGS/dispatch_laptop.log"; } \
      > "$DIR/FAILED_LAPTOP_DISPATCH"
  fi
fi

if [ "$DO_LOCAL" != 1 ]; then
  log "=== --laptop-only: laptop dispatch attempted, local leg NOT started. Exiting. ==="
  exit 0
fi

# ─────────────────────────────────────────────────────────────────────────────────────────
# LOCAL leg — FOREGROUND on purpose.
#
# menu_fair_cell.sh loops until the SHARED dir holds 800 seed*.json, so this call blocks for
# the whole cell (however the 800 are split between the boxes) and the chain's pid therefore
# lives exactly as long as the run. That is what makes a "chain not running" watchdog check
# meaningful — if this backgrounded and returned, the watchdog would see a dead chain the
# instant it launched.
# ─────────────────────────────────────────────────────────────────────────────────────────
mkdir -p "$OUT_DIR"
if [ "$DRYRUN" = 1 ]; then
  log "[dry-run] local leg would be:"
  log "    MENU_OUT_ROOT=$OUT_ROOT nice -n 19 bash $REPO/scripts/classical_search/menu_fair_cell.sh $(cell_args "$W_LOCAL" local)"
  MENU_OUT_ROOT="$OUT_ROOT" bash "$REPO/scripts/classical_search/menu_fair_cell.sh" \
      $(cell_args "$W_LOCAL" local) --dry-run
  log "=== dry-run complete. NOTHING was launched. ==="
  exit 0
fi

# The watchdog's COLD-START GUARD. It refuses to launch anything until this file exists, so
# the cron tick can be armed BEFORE the owner launches without ever starting a run nobody
# asked for. Written here — at the moment the owner's local leg actually begins — and never
# by the watchdog itself.
{ echo "$(ts)"; echo "host=$(hostname) pid=$$ W_local=$W_LOCAL band=$BAND cell=$SUB"; } > "$DIR/CHAIN_STARTED"

log "--- LOCAL leg START (W=$W_LOCAL, foreground, blocks until $N records exist on the share) ---"
MENU_OUT_ROOT="$OUT_ROOT" nice -n 19 bash "$REPO/scripts/classical_search/menu_fair_cell.sh" \
    $(cell_args "$W_LOCAL" local) >> "$LOGS/cell_local.log" 2>&1
rc=$?
GOT=$(find "$OUT_DIR" -maxdepth 1 -name 'seed*.json' 2>/dev/null | wc -l)
log "LOCAL leg END rc=$rc records=$GOT/$N"

# ─────────────────────────────────────────────────────────────────────────────────────────
# N0 WIRING GATES — pass/fail ONLY. Deliberately contains no strength statistic.
# DEPLOY_PREREG §5 rule 1: the gates are read BEFORE the summary is opened, so this driver
# emits them and does NOT run menu_block_summary.py.
# ─────────────────────────────────────────────────────────────────────────────────────────
MANIFEST="$OUT_DIR/manifest.json" OUT_DIR="$OUT_DIR" \
EXPECT_CAND_HASH="$EXPECT_CAND_HASH" CHAMP_HASH="$CHAMP_HASH" EXPECT_DOSE="$EXPECT_DOSE" \
EXPECT_BAND="$BAND" EXPECT_N="$N" GOT_N="$GOT" SUB="$SUB" KDETS="$KDETS" SIMS="$SIMS" \
"$PY" - > "$VERDICTS/GATES_$SUB.json" 2>"$LOGS/gates_$SUB.log" <<'PYEOF'
import json, os, re, sys

CURVE125 = [-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25]
g, res = [], True
def chk(n, ok, got, why=""):
    global res
    res &= bool(ok)
    g.append({"gate": n, "ok": bool(ok), "observed": got, "why": why})

mp = os.environ["MANIFEST"]
try:
    m = json.load(open(mp))
except Exception as e:
    m = {}
    chk("N0_manifest_readable", False, f"{mp}: {e!r}", "no manifest => nothing is readable")

c  = m.get("config", {}) or {}
rp = m.get("rules_profile") or {}
le = m.get("leaf_env") or {}
cl = c.get("cand_leaf_cfg") or {}
ol = c.get("opp_leaf_cfg") or {}
ch = c.get("champion") or {}
op = c.get("opponent") or {}
eg = c.get("endgame") or {}
be = c.get("backend") or {}
cd = c.get("cand_curve_drift") or {}
K, S = int(os.environ["KDETS"]), int(os.environ["SIMS"])

chk("N0a_cand_leaf_hash", c.get("cand_leaf_hash") == os.environ["EXPECT_CAND_HASH"],
    c.get("cand_leaf_hash"))
chk("N0b_opp_leaf_hash_is_unmodified_champion",
    c.get("opp_leaf_hash") == os.environ["CHAMP_HASH"], c.get("opp_leaf_hash"))
# ⚠️ THE GATE THAT PROVES THE DOSE IS LIVE. A moved hash is NOT sufficient: a
# {dose 0.0, mask 27} leaf hashes to 92ac0da996e1b37b != the champion and would pass N0a-
# style "the hash moved" reasoning while running champion-vs-champion.
chk("N0c_cand_jrules_dose_LIVE",
    cl.get("jrules_dose") is not None
    and float(cl["jrules_dose"]) == float(os.environ["EXPECT_DOSE"]),
    cl.get("jrules_dose"),
    "the RESOLVED dose in the manifest, not the hash, is what proves the term is live")
chk("N0d_no_jrules_mask_key_in_cand_leaf_cfg", "jrules_mask" not in cl,
    [k for k in cl if k.startswith("jrules")],
    "absence => the default 31; a mask typo must not be able to silently ablate rules")
chk("N0e_opponent_leaf_has_no_jrules", not any(k.startswith("jrules") for k in ol),
    {k: v for k, v in ol.items() if k.startswith("jrules")})
chk("N0f_cand_budget_k8x1376_11008",
    (ch.get("k_dets"), ch.get("sims_per_det"), ch.get("total_sims")) == (K, S, K * S),
    [ch.get("k_dets"), ch.get("sims_per_det"), ch.get("total_sims")])
chk("N0g_opp_budget_k8x1376_11008",
    (op.get("k_dets"), op.get("sims_per_det"), op.get("total_sims")) == (K, S, K * S),
    [op.get("k_dets"), op.get("sims_per_det"), op.get("total_sims")])
chk("N0h_rules_fixed_v1_and_R9",
    rp.get("name") == "fixed_v1" and rp.get("r9_env_ok") is True
    and le.get("CARCASSONNE_FIX_R9") == "1",
    [rp.get("name"), rp.get("r9_env_ok"), le.get("CARCASSONNE_FIX_R9")])
chk("N0i_backend_rust_both_sides",
    be.get("requested") == "rust"
    and sorted(be.get("converted_sides") or []) == ["candidate", "opponent"],
    [be.get("requested"), be.get("converted_sides")],
    "N0 wants rust on BOTH sides; `requested` alone does not say which sides were actually "
    "converted, so converted_sides is the field that answers it.")
chk("N0j_exact_k2_shared_by_both_arms",
    eg.get("exact_k") == 2 and eg.get("shared_by_both_arms") is True,
    [eg.get("exact_k"), eg.get("shared_by_both_arms")])
chk("N0k_curve_drift_is_curve125_verbatim",
    c.get("cand_curve_drift_allowed") is True
    and list(cd.get("curve_values") or []) == CURVE125,
    [c.get("cand_curve_drift_allowed"), cd.get("curve_values")])
chk("N0l_band_and_pairing",
    (c.get("band_seed_start"), c.get("n_decks"), c.get("seatings_per_deck"), c.get("paired"))
    == (int(os.environ["EXPECT_BAND"]), int(os.environ["EXPECT_N"]) // 2, 2, True),
    [c.get("band_seed_start"), c.get("n_decks"), c.get("seatings_per_deck"), c.get("paired")])

# ---- record completeness: 800 records, 800 unique (deck_seed, seat), 0 missing, 0 extra.
d = os.environ["OUT_DIR"]
exp_band, exp_n = int(os.environ["EXPECT_BAND"]), int(os.environ["EXPECT_N"])
want = {(exp_band + i, s) for i in range(exp_n // 2) for s in (0, 1)}
seen, malformed = set(), []
for f in os.listdir(d) if os.path.isdir(d) else []:
    mm = re.fullmatch(r"seed(\d+)_a([01])\.json", f)
    if mm:
        seen.add((int(mm.group(1)), int(mm.group(2))))
    elif f.startswith("seed") and f.endswith(".json"):
        malformed.append(f)
missing, extra = sorted(want - seen), sorted(seen - want)
chk("N0m_800_records", int(os.environ["GOT_N"]) == exp_n, f"{os.environ['GOT_N']}/{exp_n}")
chk("N0n_800_unique_deckseed_seat_cells", len(seen) == exp_n, len(seen))
chk("N0o_zero_missing", not missing, missing[:12])
chk("N0p_zero_extra", not extra and not malformed, {"extra": extra[:12], "malformed": malformed[:12]})

# ---- ⚠️ N0's "a single variant_id" clause: eval_fair_puct EMITS NO variant_id ANYWHERE.
# `variant_id` is a scripts/joshuabot/h2h.py concept (the Joshua-bot tournament driver); the
# clause was carried over from that run's integrity line. It is reported here as
# UNVERIFIABLE-AS-WRITTEN with the closest available surrogate — one manifest, and every
# record agreeing on the cell-defining knobs — so the reading session sees the gap rather
# than a silently-dropped gate. This is flagged, NOT waived, and NOT counted in the pass/fail.
knobs, bad = set(), []
for (s, seat) in sorted(seen):
    try:
        r = json.load(open(os.path.join(d, f"seed{s}_a{seat}.json")))
    except Exception as e:
        bad.append([s, seat, repr(e)]); continue
    knobs.add((r.get("sims"), r.get("k_dets"), r.get("exact_k"),
               r.get("opponent"), r.get("info"), r.get("rung_sims")))
surrogate_ok = len(knobs) == 1 and not bad
g.append({"gate": "N0q_single_variant_id__UNVERIFIABLE_AS_WRITTEN",
          "ok": None, "counted_in_pass_fail": False,
          "observed": {"distinct_record_knob_tuples": len(knobs),
                       "tuple": sorted(knobs)[0] if len(knobs) == 1 else sorted(knobs)[:4],
                       "unreadable_records": bad[:6], "surrogate_ok": surrogate_ok},
          "why": "DEPLOY_PREREG N0 requires 'a single variant_id', but eval_fair_puct emits "
                 "no variant_id in its manifest or its records (it is a joshuabot/h2h.py "
                 "field). Surrogate reported: one manifest + all records agreeing on "
                 "(sims, k_dets, exact_k, opponent, info, rung_sims). RAISE THIS AT READ "
                 "TIME; do not treat the clause as satisfied merely because this line exists."})

json.dump({"cell": os.environ["SUB"], "all_gates_pass": res,
           "records": f"{os.environ['GOT_N']}/{exp_n}", "gates": g,
           "note": "WIRING ONLY — contains no strength statistic by design "
                   "(DEPLOY_PREREG.md section 5 rule 1: gates before numbers, always). "
                   "This driver deliberately does NOT run menu_block_summary.py."},
          sys.stdout, indent=2)
sys.stdout.write("\n")
PYEOF
grc=$?
GPASS=$("$PY" -c "import json;print(json.load(open('$VERDICTS/GATES_$SUB.json'))['all_gates_pass'])" 2>/dev/null || echo UNREADABLE)
log "N0 wiring gates: all_gates_pass=$GPASS (gate-script rc=$grc) -> $VERDICTS/GATES_$SUB.json"

MIN=$(( N * 9 / 10 ))
if [ "$GOT" -ge "$MIN" ]; then
  { echo "$(ts)"; echo "records $GOT/$N"; echo "band_seed_start $BAND";
    echo "cand_leaf_hash_expected $EXPECT_CAND_HASH"; echo "jrules_dose_expected $EXPECT_DOSE";
    echo "workers local=$W_LOCAL laptop=$W_LAPTOP (shared-claim work-stealing)";
    echo "n0_wiring_gates_all_pass $GPASS";
    echo "NOT ADJUDICATED — read DEPLOY_PREREG.md N0 from $OUT_DIR/manifest.json before any number.";
    echo "N4 cost confound: read ms_ratio_cand_over_opp off menu_block_summary.py (fair-PIMC";
    echo "  convention: cand = champ_prefix_ms_per_move, opp = rung_ms_per_move).";
  } > "$DIR/DONE_$SUB"
  log "cell $SUB DONE ($GOT/$N) -> $DIR/DONE_$SUB"
  [ "$GOT" -lt "$N" ] && log "cell $SUB INCOMPLETE but >=90% — the 90% VOID rule applies at READ time, not here"
else
  { echo "$(ts)"; echo "records $GOT/$N (<90%) — VOID by the standing rule";
    echo "local leg rc=$rc"; echo "see $LOGS/cell_local.log"; } > "$DIR/FAILED_$SUB"
  log "!!! cell $SUB FAILED ($GOT/$N < 90%) -> $DIR/FAILED_$SUB"
  exit 11
fi

log "=== CHAIN COMPLETE. Nothing adjudicated, nothing promoted, no results.csv row, no claim row. ==="
exit 0
