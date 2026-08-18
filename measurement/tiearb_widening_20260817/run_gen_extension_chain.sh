#!/usr/bin/env bash
# run_gen_extension_chain.sh — run the TWO committed extension sub-ranges in
# sequence on one box, S1 then S2.
#
# Why a chain rather than two concurrent launches: the sub-ranges are separate
# `--out` directories and separate seed ranges, so running both at once on one
# box would split its workers between them for no gain. Sequential keeps each
# invocation at the full GEN worker count (local 48 / laptop 24) and keeps the
# per-stratum completion signal unambiguous.
#
# Both boxes run this same chain against the SAME two `--out` dirs on the share
# with `--shared-claim` O_EXCL work-stealing, so a slower box simply claims
# fewer games and neither can double-generate a seed.
#
# S1 (508 games) finishes long before S2 (4,840), so the boxes converge onto S2.
#
#   usage:  run_gen_extension_chain.sh {local|laptop-side}
#
# DETACH IT (house rule; Mac-sleep SIGHUP and WSL VM teardown both kill
# tty-attached jobs):
#   setsid nohup .../run_gen_extension_chain.sh local \
#     > /mnt/c/carc-shared/tiearb_widening_20260817/gen_ext.local.log 2>&1 \
#     < /dev/null & disown
set -uo pipefail

REPO=/home/doctor/projects/carcassone
GEN="$REPO/measurement/tiearb_widening_20260817/run_gen.sh"
# ⚠️ do NOT put braces in the :? message — an unescaped `}` closes the parameter
# expansion early and leaves a literal `}` glued to the value (BOX became
# "local}" on the first launch, which run_gen.sh correctly refused).
BOX="${1:?usage: run_gen_extension_chain.sh local|laptop-side}"
case "$BOX" in
  local|laptop-side) ;;
  *) echo "[chain] FATAL: box must be 'local' or 'laptop-side', got '$BOX'" >&2; exit 2 ;;
esac

for S in s1 s2; do
  echo "=== [$(date -Is)] chain: $BOX --extension $S ==="
  bash "$GEN" "$BOX" --extension "$S"
  rc=$?
  echo "=== [$(date -Is)] chain: $BOX $S exited rc=$rc ==="
  [ "$rc" -eq 0 ] || { echo "[chain] ABORTING: $S failed rc=$rc" >&2; exit "$rc"; }
done
echo "=== [$(date -Is)] chain: $BOX BOTH SUB-RANGES DONE ==="
