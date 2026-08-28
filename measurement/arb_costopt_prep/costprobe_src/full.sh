cd /home/doctor/costprobe
mkdir -p out
PL=6,14,22,30,40,50,60,72,86,100
{
  echo "=== CENSUS BEFORE ==="; uptime; ps -eo pid,etime,%cpu,args --sort=-%cpu | head -6
  echo "=== RUN none ==="
  ./target/release/tier1_costprobe 6 $PL 4 none > out/probe_none.json 2>out/probe_none.err
  echo "rc=$?"; tail -2 out/probe_none.err
  echo "=== RUN cache ==="
  ./target/release/tier1_costprobe 6 $PL 4 cache > out/probe_cache.json 2>out/probe_cache.err
  echo "rc=$?"; tail -2 out/probe_cache.err
  echo "=== RUN allocount (none) ==="
  ./target-ac/release/tier1_costprobe 3 $PL 2 none > out/probe_alloc.json 2>out/probe_alloc.err
  echo "rc=$?"; tail -2 out/probe_alloc.err
  echo "=== CENSUS AFTER ==="; uptime; ps -eo pid,etime,%cpu,args --sort=-%cpu | head -6
  echo "=== DONE ==="
} > out/full.log 2>&1
touch out/DONE
