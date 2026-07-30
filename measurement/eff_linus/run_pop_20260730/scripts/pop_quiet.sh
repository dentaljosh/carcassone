#!/usr/bin/env bash
cd /home/pop
echo "=== live top (2s sample) ==="
top -b -n 2 -d 2 | awk '/^%Cpu|^ *PID/{p=1} p' | tail -22
echo "=== loadavg ==="
cat /proc/loadavg
echo "=== GOVERNOR BEFORE ==="
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference
echo "=== set performance ==="
echo pop | sudo -S -p '' bash -c 'for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo performance > $f; done' 2>&1
sleep 1
echo "=== GOVERNOR AFTER ==="
for c in 0 8 16 23; do echo "cpu$c gov=$(cat /sys/devices/system/cpu/cpu$c/cpufreq/scaling_governor) epp=$(cat /sys/devices/system/cpu/cpu$c/cpufreq/energy_performance_preference)"; done
echo "distinct governors: $(cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor | sort -u | tr '\n' ' ')"
echo "distinct epp: $(cat /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference | sort -u | tr '\n' ' ')"
echo "no_turbo: $(cat /sys/devices/system/cpu/intel_pstate/no_turbo)"
echo "=== thermal ==="
cat /sys/class/thermal/thermal_zone0/temp
echo "=== AC power ==="
cat /sys/class/power_supply/AC*/online 2>/dev/null
echo "=== root fs medium ==="
lsblk -o NAME,SIZE,TYPE,TRAN,MODEL,MOUNTPOINT 2>/dev/null | head -15
findmnt -no SOURCE,FSTYPE,OPTIONS / 2>/dev/null
echo "=== tailscale/hostname ==="
hostname; ip -4 addr show | grep -E "inet " | head -5
