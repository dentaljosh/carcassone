#!/usr/bin/env bash
# =============================================================================
# wsl_vs_native_ab.sh — project "eff_linus": price the WSL2 virtualisation tax
# =============================================================================
# MEASUREMENT INFRASTRUCTURE (not a strength lever). Roadmap G3 (per-move cost
# reduction), stage "Eff Jensen", sub-effort **eff_linus**. No games are played,
# no elo is produced, nothing here can change a champion or a claim.
#
# ## The question (Joshua, 2026-07-28)
#
# Every hot number this project owns was measured INSIDE WSL2. Two taxes are
# hypothesised, and this script prices both on the 5900XT box:
#
#   1. **CPU/DRAM tax.** WSL2 is a Hyper-V guest, so every guest page walk is a
#      nested (EPT / two-dimensional) walk. Our search is pointer-chasing over
#      dict/set union-find structures — i.e. TLB-miss-heavy, the exact workload
#      a 2-D page walk punishes. Hypothesis: 5-20% on `s/move`.
#   2. **GPU batch-1 tax.** WSL2 reaches the GPU through paravirtualisation
#      (/dev/dxg -> dxgkrnl), which adds per-submission latency. Batch-1 forwards
#      are pure launch latency, so this is where it would show. Every batch-1
#      figure we hold (G3, carc-orch) came through that path.
#
# The A/B lever needs no reboot and no dual-boot: from WSL you can exec a Windows
# binary directly, and it runs FULLY NATIVE (own NT process, no guest kernel).
# So one bash script can drive both arms back-to-back under identical conditions.
#
# ## Design — what makes this an A/B and not two benchmarks
#
#   * **Same source, byte-for-byte.** `stage()` rsyncs the repo's
#     `src/carcassonne_ai` + `engine/wingedsheep` and a copy of
#     `net_transport_bench.py` onto C:, and BOTH arms import from that one copy
#     (WSL sees /mnt/c/..., Windows sees C:\...). The champion arm likewise runs
#     the one standalone M5 bundle. Neither arm can drift from the other.
#   * **Same CPython minor.** WSL arm = 3.13 venv built for this bench, NOT the
#     repo venv (which is 3.12). A 3.12-vs-3.13 comparison would be a CPython
#     release test wearing a virtualisation costume.
#   * **Same torch build.** Both arms pin torch 2.11.0+cu128.
#   * **PURE-PYTHON leaf on both arms** (`CARCASSONNE_USE_CY_LEAF=0`). The bundle
#     ships Linux `.so`s and there is no Windows `.pyd`, so leaving Cython on
#     would compare a compiled leaf against an interpreted one and call the
#     4.5x difference "virtualisation". The driver ASSERTS `leaf_active == false`
#     on both arms and fails the run if either binds Cython. (Cython parity is
#     the round-2 question — see ROUND 2 below.)
#   * **Alternating A/B/B/A.** Cells run `wsl,win` on odd reps and `win,wsl` on
#     even reps, so a monotone load drift cannot masquerade as an arm effect.
#   * **Quiet-window guard.** Refuses at 1m loadavg > 4 without --force. The
#     guard is read WSL-side for BOTH arms: Windows has no loadavg, and the two
#     arms share one physical box anyway.
#
# ## Cells (ROUND 1)
#
#   champ_k1x32   champion single-stream s/move,  32 sims/move  (pure-python leaf)
#   champ_k4x172  champion single-stream s/move, 688 sims/move  (pure-python leaf)
#   net_cuda_b1   batch-1 policy forward on CUDA  (the /dev/dxg hypothesis)
#   net_cpu_1t    batch-1 policy forward on CPU, 1 thread (the control: no GPU
#                 path at all, so a delta here is pure CPU/DRAM tax)
#
# The two net cells reuse the committed measurement core of
# `net_transport_bench.py` rather than re-implementing it — including its real
# consumption pattern (`forward_policy_only` + on-device masked softmax + a full
# 2511-float device->host copy; there is NO `.item()` on the netprior path).
#
# =============================================================================
# RUNBOOK
# =============================================================================
#
# ---- tonight / any contended moment: plumbing proof only --------------------
#
#     scripts/measurement_infra/wsl_vs_native_ab.sh --smoke
#
#   ~2-4 min. Tiny scale (3 positions / 100 calls). Proves both interpreters run
#   the code and emit valid JSON. Its output is stamped
#   `smoke_is_not_a_measurement: true` — the numbers are contended garbage.
#
# ---- tomorrow's QUIET WINDOW: the real run ----------------------------------
#
#   Pre-flight (do not skip):
#     cat /proc/loadavg                       # want 1m < 1
#     ps -o pid,etime,%cpu,comm -C python --sort=-etime | head
#     nvidia-smi --query-gpu=power.draw,utilization.gpu,memory.used --format=csv
#     # the equal-wall-clock gate and carc-orch must both be STOPPED: the GPU
#     # cell cannot share the device, and the CPU cell cannot share the box.
#
#   Then:
#     nohup nice -n 19 scripts/measurement_infra/wsl_vs_native_ab.sh \
#         > /home/doctor/projects/carcassone/measurement/eff_linus/ab_run.log 2>&1 &
#     disown
#
#   EXPECTED WALL-CLOCK: ~20 min total (3 reps x 2 arms x 4 cells), derived from
#   the 2026-07-29 smoke on a LOADED box (so a quiet box should beat it):
#
#     champ_k1x32   0.15 s/move  x 12 decisions  ->  ~4 s  per arm-rep   ~0.5 min
#     champ_k4x172  2.27 s/move  x 12 decisions  ->  ~30 s per arm-rep   ~3.5 min
#     net_cpu_1t    16.1 ms/fwd  x 2000 x2 timings -> ~95 s per arm-rep  ~10  min
#     net_cuda_b1    3.1 ms/fwd  x 2000 x2 timings -> ~40 s per arm-rep  ~4   min
#
#   (`run_row` times BOTH `full` and `forward` per row, hence the x2.) The smoke
#   also PRINTS its own EST block, but that one scales total wallclock including
#   fixed setup, so it reads high — treat it as an upper bound.
#
#   Result -> measurement/eff_linus/wsl_vs_native_ab_<stamp>.json  (one merged
#   JSON + manifest; per-cell child JSONs kept alongside under cells/).
#
# =============================================================================
# WINDOWS-SIDE ARTEFACTS — NOT IN GIT (they live on the Windows user profile)
# =============================================================================
#
#   C:\Users\Doctor\AppData\Local\Programs\Python\Python313\python.exe
#       CPython 3.13.14, installed 2026-07-28 by
#       `winget install --id Python.Python.3.13 --scope user` (USER SCOPE, no
#       elevation, no PATH change).
#   C:\Users\Doctor\carc-win-bench\.venv
#       The Windows bench venv: numpy, pyyaml, torch==2.11.0+cu128
#       (pip --no-cache-dir; C: had ~19 GB free and the wheel is 2.75 GB).
#   /home/doctor/carc-wsl-bench/.venv
#       The matching WSL arm: CPython 3.13 (miniforge base), same three deps.
#   C:\carc-shared\eff_linus_20260728\
#       Staging dir this script writes (pysrc copy + generated .bat wrappers).
#       Regenerated on every run; safe to delete.
#
# Rebuild recipes for all four live in the git history of this commit's message
# and in the scratchpad scripts `setup_win_venv.ps1` / `setup_wsl_venv.sh`.
#
# =============================================================================
# ROUND 2 (documented, deliberately NOT done tonight)
# =============================================================================
#
#   1. **Cython parity — needs a decision from Joshua.** Round 1 is pure-Python
#      on both arms because there is no Windows `.pyd`. Building one needs
#      **MSVC Build Tools** (multi-GB, and the standard installer wants
#      elevation). Until that exists, this bench CANNOT price the production
#      leaf on native Windows — only the interpreted one. Two consequences:
#        - a round-1 win does NOT transfer 1:1 to production (the Cython leaf
#          moves the bottleneck from bytecode dispatch toward memory, which is
#          exactly where the nested-paging tax should be LARGER, not smaller);
#        - the round-2 A/B is the one that decides anything operationally.
#      QUESTION FOR JOSHUA: install VS Build Tools (C++ workload, ~7 GB, admin)?
#   2. **THP / large pages inside WSL, as a third arm.** If the tax is really
#      2-D page walks, then huge pages inside the guest should recover much of
#      it without leaving WSL — `/sys/kernel/mm/transparent_hugepage/enabled`
#      (madvise -> always) and the .wslconfig `pageReporting` knob. Cheap, and
#      it tests the MECHANISM rather than just the endpoint. Documented only.
#   3. If round 1 shows a real GPU-side delta, re-price carc-orch itself
#      (a Windows-native orchestrator is a much bigger lift than a venv).
#
# =============================================================================
set -euo pipefail

PROJECT="eff_linus"
REPO=/home/doctor/projects/carcassone
STAGE_WSL=/mnt/c/carc-shared/eff_linus_20260728
STAGE_WIN='C:\carc-shared\eff_linus_20260728'
M5_WSL=/mnt/c/carc-shared/m5_bench_20260728
M5_WIN='C:\carc-shared\m5_bench_20260728'
CKPT_WSL=/mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt
CKPT_WIN='C:\carc-shared\distill_strong_20260723\ckpt\iter_03.pt'
WSL_PY=/home/doctor/carc-wsl-bench/.venv/bin/python
WIN_PY_WIN='C:\Users\Doctor\carc-win-bench\.venv\Scripts\python.exe'
WIN_PY_WSL=/mnt/c/Users/Doctor/carc-win-bench/.venv/Scripts/python.exe
LOADAVG_LIMIT=4.0

SMOKE=0
FORCE=0
REPS=3
CELLS="champ_k1x32,champ_k4x172,net_cuda_b1,net_cpu_1t"
OUTDIR=""
CHAMP_LIMIT=12          # positions per champion cell (of the 60 bundled)
NET_CALLS=2000
NET_WARMUP=200

usage() { sed -n '2,140p' "$0"; exit 0; }

while [ $# -gt 0 ]; do
  case "$1" in
    --smoke)  SMOKE=1; shift ;;
    --force)  FORCE=1; shift ;;
    --reps)   REPS="$2"; shift 2 ;;
    --cells)  CELLS="$2"; shift 2 ;;
    --out)    OUTDIR="$2"; shift 2 ;;
    --champ-limit) CHAMP_LIMIT="$2"; shift 2 ;;
    --calls)  NET_CALLS="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "wsl_vs_native_ab: unknown argument $1" >&2; exit 2 ;;
  esac
done

STAMP="$(date +%Y%m%d_%H%M%S)"
if [ -z "$OUTDIR" ]; then
  if [ "$SMOKE" -eq 1 ]; then
    OUTDIR="$REPO/measurement/eff_linus/smoke_$STAMP"
  else
    OUTDIR="$REPO/measurement/eff_linus/run_$STAMP"
  fi
fi
CELLDIR="$OUTDIR/cells"
mkdir -p "$CELLDIR"
NDJSON="$OUTDIR/runs.ndjson"
: > "$NDJSON"

if [ "$SMOKE" -eq 1 ]; then
  REPS=1; CHAMP_LIMIT=3; NET_CALLS=100; NET_WARMUP=10
fi

# --------------------------------------------------------------------------- #
# 0. pre-flight                                                                #
# --------------------------------------------------------------------------- #
echo "== eff_linus WSL-vs-native A/B =="
echo "   stamp   : $STAMP"
echo "   out     : $OUTDIR"
echo "   cells   : $CELLS   reps=$REPS   smoke=$SMOKE"

LA1="$(cut -d' ' -f1 /proc/loadavg)"
echo "   loadavg : $(cat /proc/loadavg)"
if [ "$SMOKE" -eq 0 ] && [ "$FORCE" -eq 0 ]; then
  if awk -v l="$LA1" -v lim="$LOADAVG_LIMIT" 'BEGIN{exit !(l>lim)}'; then
    echo "REFUSING: 1m loadavg $LA1 > $LOADAVG_LIMIT. This is a LATENCY A/B; on a" >&2
    echo "  contended box it measures the contention, not the hypervisor. Run it in" >&2
    echo "  the quiet window (gate + carc-orch stopped), or pass --force." >&2
    exit 2
  fi
fi

for p in "$WSL_PY" "$WIN_PY_WSL"; do
  [ -x "$p" ] || { echo "FATAL: missing interpreter $p (see the venv recipes in this header)" >&2; exit 2; }
done
[ -f "$CKPT_WSL" ] || { echo "FATAL: missing checkpoint $CKPT_WSL" >&2; exit 2; }
[ -d "$M5_WSL/bundle" ] || { echo "FATAL: missing M5 bundle $M5_WSL/bundle" >&2; exit 2; }

echo "-- pre-flight census"
ps -o pid,etime,%cpu,comm -C python --sort=-etime 2>/dev/null | head -8 || true
nvidia-smi --query-gpu=name,power.draw,utilization.gpu,memory.used --format=csv,noheader 2>/dev/null || true

# --------------------------------------------------------------------------- #
# 1. stage — ONE source copy on C:, both arms import from it                   #
# --------------------------------------------------------------------------- #
echo "-- staging source to $STAGE_WSL"
mkdir -p "$STAGE_WSL/pysrc" "$STAGE_WSL/bat"
# --delete so a stale module can never survive a run; the *.so exclude is load
# bearing: a Linux .so in the staged tree would let the WSL arm bind Cython
# while the Windows arm could not, which is the one asymmetry that would
# invalidate the whole comparison.
rsync -a --delete --exclude '__pycache__/' --exclude '*.so' --exclude '*.pyd' \
      --exclude '*.c' --exclude '*.pyc' \
      "$REPO/src/carcassonne_ai/" "$STAGE_WSL/pysrc/carcassonne_ai/"
rsync -a --delete --exclude '__pycache__/' --exclude '*.so' --exclude '*.pyd' \
      --exclude '*.c' --exclude '*.pyc' \
      "$REPO/engine/wingedsheep/" "$STAGE_WSL/pysrc/wingedsheep/"
cp "$REPO/scripts/measurement_infra/net_transport_bench.py" "$STAGE_WSL/net_transport_bench.py"
GIT_REV="$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "   git_rev : $GIT_REV"

# --------------------------------------------------------------------------- #
# 2. the shared environment, expressed twice                                   #
#                                                                              #
# ⚠️ WSL->Windows exec does NOT inherit the bash environment (verified: a var    #
# exported in bash reads back as the literal %VAR% under cmd.exe). Nor can the  #
# Windows process keep the WSL cwd — it arrives as \\wsl.localhost\... and      #
# cmd.exe answers "UNC paths are not supported. Defaulting to Windows           #
# directory." So every Windows cell goes through a GENERATED .bat that sets its #
# own env and cd's to a real C:\ path. Do not "simplify" this to an inline      #
# `VAR=x python.exe ...`; it silently runs with the wrong env.                  #
# --------------------------------------------------------------------------- #
# PYTHONHASHSEED: pinned so str/enum hash randomisation cannot add between-run
# variance to the union-find dict/set bookkeeping the leaf spends ~22% in.
# PYTHONDONTWRITEBYTECODE: pinned on BOTH arms so neither arm gets a warm .pyc
# the other lacks (and so the staged tree stays clean). Import is untimed.
# PYTHONUTF8=1: REQUIRED on the Windows arm and harmless on the WSL arm (Linux is
# already UTF-8). Without it, native Windows CPython defaults its text codec to
# the ANSI codepage (cp1252 here) and `champion_factory.load_production_spec()`
# dies with UnicodeDecodeError on the UTF-8 PRODUCTION.yaml — `Path.read_text()`
# in the library passes no explicit encoding. That is a REAL latent portability
# bug in src/carcassonne_ai/champion_factory.py, not a bench artefact; it is
# fixed here by environment rather than by source because the tree was live when
# this was written (CLAUDE.md worktree-isolation rule). ROUND 2 should carry the
# one-word `encoding="utf-8"` fix into the library at a quiet window.
COMMON_ENV=(
  "PYTHONUTF8=1"
  "PYTHONHASHSEED=0"
  "PYTHONDONTWRITEBYTECODE=1"
  "CARCASSONNE_USE_FLAT_LEAF=1"
  "CARCASSONNE_USE_CY_LEAF=0"
  "CARCASSONNE_USE_CY_REPR=0"
)

write_bat() {   # write_bat <path> <cwd_win> <extra_env_kv...> -- <exe> <args...>
  local bat="$1"; shift
  local cwd="$1"; shift
  {
    echo "@echo off"
    echo "setlocal"
    for kv in "${COMMON_ENV[@]}"; do echo "set \"$kv\""; done
    while [ "$1" != "--" ]; do echo "set \"$1\""; shift; done
    shift
    echo "cd /d $cwd"
    printf '"%s" -u' "$WIN_PY_WIN"
    for a in "$@"; do printf ' %s' "\"$a\""; done
    printf '\n'
    echo "exit /b %ERRORLEVEL%"
  } > "$bat"
  unix2dos -q "$bat" 2>/dev/null || sed -i 's/$/\r/' "$bat"
}

snap() {  # one-line machine state
  local la; la="$(cat /proc/loadavg)"
  local gpu; gpu="$(nvidia-smi --query-gpu=power.draw,utilization.gpu,memory.used,clocks.sm \
                    --format=csv,noheader,nounits 2>/dev/null | head -1 || true)"
  printf '{"loadavg":"%s","nvidia_smi":"%s"}' "$la" "$gpu"
}

# --------------------------------------------------------------------------- #
# 3. one cell, one arm                                                         #
# --------------------------------------------------------------------------- #
run_cell() {  # run_cell <cell> <arm> <rep>
  local cell="$1" arm="$2" rep="$3"
  local tag="${cell}__${arm}__rep${rep}"
  local cj="$CELLDIR/$tag.json"
  local log="$CELLDIR/$tag.log"
  local before after rc t0 t1
  before="$(snap)"
  t0="$(date +%s.%N)"
  set +e
  case "$cell:$arm" in
    champ_*:wsl)
      local budget="${cell#champ_}"
      env "${COMMON_ENV[@]}" "$WSL_PY" -u "$M5_WSL/bench_champion.py" \
          --bundle "$M5_WSL/bundle" --budgets "$budget" --limit "$CHAMP_LIMIT" \
          --warmup 1 --tag "$PROJECT:$tag" --out "$cj" > "$log" 2>&1
      rc=$? ;;
    champ_*:win)
      local budget="${cell#champ_}"
      local bat="$STAGE_WSL/bat/$tag.bat"
      write_bat "$bat" "$M5_WIN" -- \
          "$M5_WIN\\bench_champion.py" --bundle "$M5_WIN\\bundle" \
          --budgets "$budget" --limit "$CHAMP_LIMIT" --warmup 1 \
          --tag "$PROJECT:$tag" --out "$STAGE_WIN\\out_$tag.json"
      cmd.exe /c "$STAGE_WIN\\bat\\$tag.bat" > "$log" 2>&1
      rc=$?
      [ -f "$STAGE_WSL/out_$tag.json" ] && mv "$STAGE_WSL/out_$tag.json" "$cj"
      ;;
    net_*:wsl)
      local row="${cell#net_}"
      env "${COMMON_ENV[@]}" "PYTHONPATH=$STAGE_WSL/pysrc" \
          "$WSL_PY" -u "$STAGE_WSL/net_transport_bench.py" \
          --ckpt "$CKPT_WSL" --rows "$row" --calls "$NET_CALLS" \
          --warmup "$NET_WARMUP" --out "$cj" $( [ "$SMOKE" -eq 1 ] && echo --smoke ) \
          > "$log" 2>&1
      rc=$? ;;
    net_*:win)
      local row="${cell#net_}"
      local bat="$STAGE_WSL/bat/$tag.bat"
      local extra=""
      [ "$SMOKE" -eq 1 ] && extra="--smoke"
      write_bat "$bat" "$STAGE_WIN" "PYTHONPATH=$STAGE_WIN\\pysrc" -- \
          "$STAGE_WIN\\net_transport_bench.py" --ckpt "$CKPT_WIN" --rows "$row" \
          --calls "$NET_CALLS" --warmup "$NET_WARMUP" \
          --out "$STAGE_WIN\\out_$tag.json" $extra
      cmd.exe /c "$STAGE_WIN\\bat\\$tag.bat" > "$log" 2>&1
      rc=$?
      [ -f "$STAGE_WSL/out_$tag.json" ] && mv "$STAGE_WSL/out_$tag.json" "$cj"
      ;;
    *) echo "unknown cell:arm $cell:$arm" >&2; return 2 ;;
  esac
  set -e
  t1="$(date +%s.%N)"
  after="$(snap)"
  printf '{"cell":"%s","arm":"%s","rep":%s,"rc":%s,"wallclock_s":%s,"child_json":"%s","log":"%s","state_before":%s,"state_after":%s}\n' \
    "$cell" "$arm" "$rep" "$rc" "$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.3f", b-a}')" \
    "$cj" "$log" "$before" "$after" >> "$NDJSON"
  printf '   %-28s rc=%s  %ss\n' "$tag" "$rc" \
    "$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.1f", b-a}')"
}

# --------------------------------------------------------------------------- #
# 4. warm-up pass — Defender scans a fresh venv on first exec; that scan must   #
#    not land inside a timed cell. One throwaway import per arm.                #
# --------------------------------------------------------------------------- #
echo "-- warm-up (Defender first-touch of the venv; discarded)"
env "${COMMON_ENV[@]}" "$WSL_PY" -c "import numpy, yaml, torch; print('wsl warm', torch.__version__)" || true
write_bat "$STAGE_WSL/bat/warm.bat" "$STAGE_WIN" -- \
    -c "import numpy, yaml, torch; print('win warm', torch.__version__)"
cmd.exe /c "$STAGE_WIN\\bat\\warm.bat" 2>&1 | tr -d '\r' || true

# --------------------------------------------------------------------------- #
# 5. the alternating loop                                                      #
# --------------------------------------------------------------------------- #
IFS=',' read -r -a CELL_ARR <<< "$CELLS"
for cell in "${CELL_ARR[@]}"; do
  for rep in $(seq 1 "$REPS"); do
    # order flips per rep so a monotone drift cannot look like an arm effect
    if [ $((rep % 2)) -eq 1 ]; then order="wsl win"; else order="win wsl"; fi
    for arm in $order; do
      run_cell "$cell" "$arm" "$rep"
    done
  done
done

# --------------------------------------------------------------------------- #
# 6. merge + assert                                                            #
# --------------------------------------------------------------------------- #
MERGED="$OUTDIR/wsl_vs_native_ab_$STAMP.json"
PROJECT="$PROJECT" STAMP="$STAMP" GIT_REV="$GIT_REV" SMOKE="$SMOKE" FORCE="$FORCE" \
REPS="$REPS" CELLS="$CELLS" NDJSON="$NDJSON" MERGED="$MERGED" OUTDIR="$OUTDIR" \
CHAMP_LIMIT="$CHAMP_LIMIT" NET_CALLS="$NET_CALLS" NET_WARMUP="$NET_WARMUP" \
CHAMP_LIMIT_FULL=12 REPS_FULL=3 \
WSL_PY="$WSL_PY" WIN_PY="$WIN_PY_WIN" STAGE_WSL="$STAGE_WSL" CKPT="$CKPT_WSL" \
"$WSL_PY" "$REPO/scripts/measurement_infra/wsl_vs_native_merge.py"

echo
echo "== done =="
echo "   merged JSON : $MERGED"
[ "$SMOKE" -eq 1 ] && echo "   ⚠️  SMOKE — the box is contended and the scale is tiny. These numbers are"
[ "$SMOKE" -eq 1 ] && echo "      plumbing evidence, NOT measurements. Re-run in the quiet window."
exit 0
