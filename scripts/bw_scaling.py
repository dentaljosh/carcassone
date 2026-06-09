#!/usr/bin/env python3
"""Direct test: is this box memory-bandwidth-bound at ~16 threads?

Runs two microbenchmarks across thread counts 1..32:
  MEM  : each worker streams a >L3 array (256MB) in-place (read+write) -> saturates RAM bandwidth.
  CPU  : each worker runs a tight integer-ALU loop (L1-resident, ~no memory) -> pure core/SMT.

If MEM aggregate GB/s plateaus around N=16 (physical cores) while CPU aggregate keeps climbing
toward N=32, the box is memory-bandwidth-bound past 16 threads -- which is exactly the self-play
shape (peak at W=16, flat/down after). If BOTH plateau at 16, it's a core/SMT/scheduler limit,
not bandwidth. This distinguishes the two hypotheses directly.

No HW counters needed (WSL2 doesn't expose IMC/uncore PMU); we measure achieved throughput.
"""
import time, sys, multiprocessing as mp
import numpy as np

NS = [1, 2, 4, 8, 12, 16, 20, 24, 28, 32]
DUR = 4.0
ARR_MB = 256  # >> 64MB L3 so every pass goes to DRAM


def mem_worker(start, dur, mb, q):
    a = np.ones((mb * 1024 * 1024) // 8, dtype=np.float64)
    a += 1.0  # fault/warm the pages
    while time.time() < start:
        pass
    deadline = start + dur
    passes = 0
    while time.time() < deadline:
        a += 1.0  # read+write the whole array
        passes += 1
    q.put(passes * a.nbytes * 2)  # bytes moved (read + write)


def cpu_worker(start, dur, q):
    while time.time() < start:
        pass
    deadline = start + dur
    x = 123456789
    iters = 0
    CHUNK = 200000
    while time.time() < deadline:
        for _ in range(CHUNK):
            x = (x * 1103515245 + 12345) & 0x7fffffff
        iters += CHUNK
    q.put((iters, x & 1))  # x&1 keeps the optimizer honest


def run(mode, n, dur):
    q = mp.Queue()
    start = time.time() + 0.4
    procs = []
    for _ in range(n):
        if mode == "mem":
            p = mp.Process(target=mem_worker, args=(start, dur, ARR_MB, q))
        else:
            p = mp.Process(target=cpu_worker, args=(start, dur, q))
        p.start()
        procs.append(p)
    tot = 0
    for _ in range(n):
        r = q.get()
        tot += r if mode == "mem" else r[0]
    for p in procs:
        p.join()
    return tot / dur  # bytes/s (mem) or iters/s (cpu)


def main():
    print(f"# {ARR_MB}MB arrays, {DUR}s/point, L3=64MB, 16 cores / 32 threads\n")
    rows = []
    for mode in ("mem", "cpu"):
        base = None
        print(f"=== {mode.upper()} scaling ===")
        unit = "GB/s" if mode == "mem" else "Giter/s"
        print(f"{'N':>3} {'aggregate':>12} {'per-thread':>12} {'scaling_vs_N1':>14}")
        for n in NS:
            r = run(mode, n, DUR)
            val = r / 1e9
            if base is None:
                base = val / n  # per-thread at... actually set from N=1
            per = val / n
            if n == 1:
                base = val
            scal = val / (base * n) if base else 0
            rows.append((mode, n, val, per, scal))
            print(f"{n:>3} {val:>9.1f} {unit} {per:>9.3f} {unit.replace('/s','/s/t'):>0} {scal*100:>11.0f}%")
        print()
    # verdict
    mem = {n: v for (m, n, v, _, _) in rows if m == "mem"}
    cpu = {n: v for (m, n, v, _, _) in rows if m == "cpu"}
    mem_peakN = max(mem, key=mem.get)
    print("--- VERDICT ---")
    print(f"MEM peak {mem[mem_peakN]:.1f} GB/s at N={mem_peakN}; "
          f"MEM @16={mem.get(16,0):.1f} -> @32={mem.get(32,0):.1f} GB/s "
          f"({100*(mem.get(32,0)/mem.get(16,1)-1):+.0f}% from 16->32)")
    print(f"CPU @16={cpu.get(16,0):.2f} -> @32={cpu.get(32,0):.2f} Giter/s "
          f"({100*(cpu.get(32,0)/cpu.get(16,1)-1):+.0f}% from 16->32)")
    if mem.get(32, 0) < mem.get(16, 1) * 1.10 and cpu.get(32, 0) > cpu.get(16, 1) * 1.20:
        print("=> MEMORY-BANDWIDTH-BOUND past ~16 threads (mem flat, cpu still climbing).")
    elif cpu.get(32, 0) < cpu.get(16, 1) * 1.10:
        print("=> CPU/SMT/scheduler-bound (even pure-compute doesn't scale past 16).")
    else:
        print("=> mixed; inspect the curves.")


if __name__ == "__main__":
    main()
