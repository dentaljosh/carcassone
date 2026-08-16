# VOID — do not cite

This session is **void on two independent grounds** (2026-08-16):

1. **Wrong machine measured.** The shell-started foreground service ran in the
   `/background` cpuset (little cores 0-3 only) on this Android 17 preview
   build — verified via `/proc/<pid>/cpuset` — not the top-app cpuset (all 8
   cores) that real in-app play uses. That is why `s/move` read 2.00 vs the
   in-app 1.551 baseline, and why measured power sat below the (inflated,
   post-install dex2oat era) idle baseline.
2. **1 of 9 runs.** The driver's plan loop was truncated after the first run by
   an adb-shell-eats-stdin bug (`adb shell` inside `... | while read` consumed
   the piped plan). The identity gate then "passed" over a single run.

Both defects are fixed in `android/tools/battery_bench.sh` (stdin guard on the
`ashell`/`runas` wrappers; run-count gate; BenchActivity top-app pinning with
screen on at min brightness). The replacement session is the
`measurement/battery_bench_*` dir with a later timestamp.

Kept for the diagnosis trail: the sampler data here is what exposed the cpuset
problem (workload window reading *below* idle).
