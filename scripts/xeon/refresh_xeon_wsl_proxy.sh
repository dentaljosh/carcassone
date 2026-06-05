#!/usr/bin/env bash
# Run from the 5800x after a Xeon WSL restart/reboot: the WSL NAT IP changes, so
# the Windows portproxy (192.168.0.110:2222 -> WSL_IP:2222) that makes
# `ssh xeon-wsl` work goes stale. This re-points it at the current WSL IP.
# (Permanent alternative: networkingMode=mirrored in .wslconfig — no IP churn,
# but needs a wsl --shutdown. See docs/XEON_DIRECT_SSH_2026-06-04.md.)
set -u
WSLIP=$(ssh -o ConnectTimeout=15 xeon "wsl -d Ubuntu-24.04 -- hostname -I" 2>/dev/null | awk '{print $1}')
[ -n "$WSLIP" ] || { echo "FATAL: could not read Xeon WSL IP (is WSL up?)"; exit 1; }
ssh -o ConnectTimeout=15 xeon "netsh interface portproxy delete v4tov4 listenport=2222 listenaddress=0.0.0.0" 2>/dev/null
ssh -o ConnectTimeout=15 xeon "netsh interface portproxy add v4tov4 listenport=2222 listenaddress=0.0.0.0 connectport=2222 connectaddress=$WSLIP"
echo "portproxy refreshed: 192.168.0.110:2222 -> $WSLIP:2222"
ssh -o ConnectTimeout=15 xeon-wsl "echo verify-ok && hostname" 2>&1 | head -2
