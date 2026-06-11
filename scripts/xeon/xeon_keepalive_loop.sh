#!/usr/bin/env bash
# Durable xeon WSL keepalive for long cluster runs. Holds the distro VM alive (prevents
# the idle-teardown that drops the NAT proxy + CIFS mount together). On any drop: refresh
# the portproxy, re-mount the share, re-hold via the reliable legacy port-22 path.
REPO=/home/doctor/projects/carcassone
MNT="sudo mount -t cifs //192.168.0.195/carc-shared /mnt/carc-shared -o credentials=/home/doctor/.carc-smb.creds,uid=1000,gid=1000,forceuid,forcegid,file_mode=0644,dir_mode=0755,vers=3.1.1,nobrl,actimeo=1,noserverino"
while true; do
  bash "$REPO/scripts/xeon/refresh_xeon_wsl_proxy.sh" >/dev/null 2>&1
  ssh -o ConnectTimeout=20 xeon "wsl -d Ubuntu-24.04 -- $MNT" >/dev/null 2>&1
  ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=4 -o ConnectTimeout=25 xeon "wsl -d Ubuntu-24.04 -- sleep infinity" >/dev/null 2>&1
  sleep 8
done
