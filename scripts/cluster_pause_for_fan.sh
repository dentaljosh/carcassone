#!/usr/bin/env bash
# cluster_pause_for_fan.sh — cleanly quiesce the deepteacher cluster before taking
# the 5800x offline for the VRM fan install (2026-06-14).
#
# WHY THIS IS LOAD-BEARING: the 5800x is the linchpin THREE ways — it (1) HOSTS the
# CIFS share that xeon + laptop mount, (2) runs the orchestrator, and (3) runs the
# Claude session. Powering it down drops the share → xeon + laptop crash too → the
# WHOLE cluster pauses. Per-game checkpoints (.npz/.json on the share) make this
# near-lossless; only in-flight games are dropped (their .claim files are pre-cleaned
# on resume). Resume after boot with: scripts/cluster_resume_after_fan.sh
set -uo pipefail
echo "=== pause deepteacher cluster @ $(date) ==="
# 1) orchestrator FIRST (stops new gen/eval launches + heal relaunches)
pkill -f run_residual_flywheel_v2.sh && echo "  orchestrator stopped" || echo "  orchestrator not running"
sleep 2
# 2) remote worker pools BEFORE the share vanishes, so they exit clean (not crash on a dead mount).
#    BRACKET patterns ([e]val…) so pkill can't self-match its own ssh shell (the old exit-255 trap),
#    and report REACHABILITY (ssh rc) separately from killed-count — the old "&& stopped || unreachable"
#    lied because the trailing pkill returns 1 on no-match, masking a successful eval kill.
for h in laptop xeon-wsl; do
  out=$(ssh -o ConnectTimeout=15 -o BatchMode=yes "$h" 'b=$(pgrep -fc "[e]val_net_vs_heuristic" 2>/dev/null); pkill -f "[e]val_net_vs_heuristic" 2>/dev/null; pkill -f "[r]un_selfplay_iter" 2>/dev/null; echo "killed ${b:-0} eval pool(s)"' </dev/null 2>/dev/null) \
    && echo "  $h: ${out:-done}" \
    || echo "  $h: UNREACHABLE (left as-is; crash-cleans when share drops, claims pre-cleaned on resume)"
done
# 3) local 5800x pools (selection eval; gen9 already done) — bracket patterns + count, for symmetry
lb=$(pgrep -fc "[e]val_net_vs_heuristic" 2>/dev/null)
pkill -f "[e]val_net_vs_heuristic" 2>/dev/null; pkill -f "[r]un_selfplay_iter" 2>/dev/null; pkill -f "[g]en_flywheel" 2>/dev/null
echo "  5800x: killed ${lb:-0} eval pool(s)"
echo "=== PAUSED. best.pt=iter8 + every completed game are safe on the share."
echo "    Power down the 5800x now. After boot + share re-serving: bash scripts/cluster_resume_after_fan.sh ==="
