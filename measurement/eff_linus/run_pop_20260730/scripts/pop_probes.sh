#!/usr/bin/env bash
# eff_linus round 3 — confound probes on the Pop arm.
#   1. un-niced control (mirrors round-2 §3a)
#   2. governor bracket: re-run the champ cells under the AS-FOUND powersave
#      governor, so the memo can say what the `performance` setting bought.
#   3. E-core probe: pin to the 8 E-cores, mirroring round-2 §4's aff_ecore.
set -uo pipefail
B=/home/pop/carc-pop-bench

echo "############ 1. UN-NICED control (performance governor, P-core pinned)"
rm -rf $B/out/ctrl_unniced
/home/pop/pop_ab.sh $B/out/ctrl_unniced champ_k4x172 pin 3 ""

echo "############ 2. E-CORE probe (performance governor)"
rm -rf $B/out/probe_ecore
sed 's/^PMASK="0-15"$/PMASK="16-23"/' /home/pop/pop_ab.sh > /home/pop/pop_ab_ecore.sh
chmod +x /home/pop/pop_ab_ecore.sh
grep -n '^PMASK=' /home/pop/pop_ab_ecore.sh
/home/pop/pop_ab_ecore.sh $B/out/probe_ecore champ_k4x172 pin 3

echo "############ 3. GOVERNOR bracket -> powersave"
echo pop | sudo -S -p '' bash -c 'for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo powersave > $f; done'
sleep 2
echo "governor now: $(cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor | sort -u | tr '\n' ' ') epp: $(cat /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference | sort -u | tr '\n' ' ')"
rm -rf $B/out/gov_powersave
/home/pop/pop_ab.sh $B/out/gov_powersave champ_k1x32,champ_k4x172 pin,free 3

echo "############ restore performance for the net cell"
echo pop | sudo -S -p '' bash -c 'for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo performance > $f; done'
sleep 1
echo "governor now: $(cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor | sort -u | tr '\n' ' ')"
touch $B/out/.probes_done
echo "PROBES_DONE $(date -u +%FT%TZ)"
