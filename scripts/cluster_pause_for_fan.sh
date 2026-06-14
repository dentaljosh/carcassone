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
# 2) remote worker pools BEFORE the share vanishes, so they exit clean (not crash on a dead mount)
ssh -o ConnectTimeout=15 laptop  'pkill -f eval_net_vs_heuristic; pkill -f run_selfplay_iter' </dev/null 2>/dev/null && echo "  laptop pools stopped" || echo "  laptop unreachable/none"
ssh -o ConnectTimeout=15 xeon-wsl 'pkill -f eval_net_vs_heuristic; pkill -f run_selfplay_iter' </dev/null 2>/dev/null && echo "  xeon pools stopped"   || echo "  xeon unreachable/none"
# 3) local 5800x pools (selection eval; gen9 already done)
pkill -f eval_net_vs_heuristic || true; pkill -f run_selfplay_iter || true; pkill -f gen_flywheel || true
echo "  5800x pools stopped"
echo "=== PAUSED. best.pt=iter8 + every completed game are safe on the share."
echo "    Power down the 5800x now. After boot + share re-serving: bash scripts/cluster_resume_after_fan.sh ==="
