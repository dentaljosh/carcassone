#!/usr/bin/env bash
cd /home/pop
echo "=== HOST ==="
hostnamectl 2>/dev/null | head -8
echo "=== LSCPU ==="
lscpu | grep -E "Model name|Socket|Core|Thread|CPU\(s\)|MHz|Flags" | head -12
echo "=== LSCPU EXTENDED ==="
lscpu --extended
echo "=== CPUFREQ DRIVER/GOVERNOR ==="
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver 2>/dev/null || echo "no scaling_driver"
echo "governors avail: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors 2>/dev/null)"
for c in 0 8 16 20; do
  echo "cpu$c gov=$(cat /sys/devices/system/cpu/cpu$c/cpufreq/scaling_governor 2>/dev/null) max=$(cat /sys/devices/system/cpu/cpu$c/cpufreq/scaling_max_freq 2>/dev/null)"
done
echo "epp: $(cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference 2>/dev/null)"
echo "no_turbo: $(cat /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null)"
echo "=== PLATFORM PROFILE / POWER ==="
cat /sys/firmware/acpi/platform_profile 2>/dev/null || echo "no platform_profile"
cat /sys/class/power_supply/AC*/online 2>/dev/null | head -2
echo "=== LOAD / PROCS ==="
cat /proc/loadavg
uptime
ps -eo pid,etime,%cpu,comm --sort=-%cpu | head -10
echo "=== MEM/DISK ==="
free -m
df -h /
echo "=== TOOLS ==="
for t in gcc cc git uv python3 rsync curl nvidia-smi taskset chrt sensors; do
  printf "%-10s %s\n" "$t" "$(command -v $t || echo MISSING)"
done
python3 -V 2>&1
gcc --version 2>/dev/null | head -1
echo "=== GPU ==="
nvidia-smi --query-gpu=name,driver_version,power.draw,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>&1 | head -3
echo "=== THERMAL ==="
for z in /sys/class/thermal/thermal_zone*/temp; do echo "$z $(cat $z 2>/dev/null)"; done | head -8
echo "=== SUDO TEST ==="
echo pop | sudo -S -p '' true 2>&1 && echo "SUDO OK" || echo "SUDO FAIL"
