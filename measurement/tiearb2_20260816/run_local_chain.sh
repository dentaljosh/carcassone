#!/usr/bin/env bash
# run_local_chain.sh — the LOCAL box's whole main-scoring shift, one detached process.
#
# ALLOCATION.conf gives local: clair-puct chunks 1-4, then tier1-greedy chunk 4.
# Chained with ';' not '&&' on purpose: a partial failure in the clair-puct leg
# must not silently cancel the tier1 chunk-4 leg — both legs stamp their own
# DONE markers and the analyser reads whatever completed (every chunk is a
# uniform random subsample of the committed permutation, so a partial run is
# still unbiased at its realized n).
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[chain] $(date -Is) START local shift"
"$HERE/run_main.sh" local clair-puct
rc_clair=$?
echo "[chain] $(date -Is) clair-puct leg rc=$rc_clair"

"$HERE/run_main.sh" local tier1-greedy 4
rc_t1=$?
echo "[chain] $(date -Is) tier1-greedy chunk4 leg rc=$rc_t1"

touch "$HERE/DONE_LOCAL_SHIFT"
echo "[chain] $(date -Is) DONE local shift (clair rc=$rc_clair, tier1 rc=$rc_t1)"
exit $(( rc_clair | rc_t1 ))
