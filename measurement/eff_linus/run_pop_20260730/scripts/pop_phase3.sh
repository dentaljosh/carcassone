#!/usr/bin/env bash
set -uo pipefail
B=/home/pop/carc-pop-bench
export PATH="/home/pop/.local/bin:$PATH"
echo "############ mechanism reads (for the memo)"
echo "THP enabled : $(cat /sys/kernel/mm/transparent_hugepage/enabled)"
echo "THP defrag  : $(cat /sys/kernel/mm/transparent_hugepage/defrag)"
echo "khugepaged max_ptes_none: $(cat /sys/kernel/mm/transparent_hugepage/khugepaged/max_ptes_none 2>/dev/null)"
echo "kernel: $(uname -r)"
for f in /sys/devices/system/cpu/vulnerabilities/*; do echo "  vuln $(basename $f): $(cat $f)"; done
echo "############ torch (CPU-only wheel; cu128 skipped on the disk guard)"
echo "df before: $(df -h / | tail -1)"
uv pip install --python $B/.venv/bin/python --index-url https://download.pytorch.org/whl/cpu torch==2.11.0 2>&1 | tail -8
echo "df after : $(df -h / | tail -1)"
du -sh $B/.venv
$B/.venv/bin/python -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available(),'threads',torch.get_num_threads())"
echo "############ 4. TRUE un-niced control (perf gov, P-pinned)"
rm -rf $B/out/ctrl_unniced2
/home/pop/pop_ab.sh $B/out/ctrl_unniced2 champ_k4x172 pin 3 ""
echo "############ 5. net_cpu_1t (pin + free, 3 reps)"
rm -rf $B/out/net_perf
/home/pop/pop_ab.sh $B/out/net_perf net_cpu_1t pin,free 3
echo "df final : $(df -h / | tail -1)"
touch $B/out/.phase3_done
echo "PHASE3_DONE $(date -u +%FT%TZ)"
