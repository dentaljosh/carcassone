#!/usr/bin/env python3
"""Clean compute-bound (SIMD-in-cache) scaling test, to remove the CPython-footprint confound
from bw_scaling.py's CPU mode. Each worker hammers np.sin on a 128KB (L2-resident) array -> high
arithmetic intensity, ~no DRAM traffic. If aggregate FLOP-rate scales toward N=32, the cores CAN
use SMT for compute (so self-play's W=16 cap is the MEMORY side). If it plateaus at ~16, SMT is
simply not useful on this silicon for any heavy work.
"""
import time, multiprocessing as mp
import numpy as np

NS = [1, 2, 4, 8, 12, 16, 20, 24, 28, 32]
DUR = 3.0
N_EL = 16384  # 128 KB float64 -> stays in per-core L2 (512KB), no DRAM streaming


def fpu_worker(start, dur, q):
    a = np.random.rand(N_EL)
    while time.time() < start:
        pass
    deadline = start + dur
    ops = 0
    while time.time() < deadline:
        np.sin(a, out=a)      # heavy SIMD transcendental, in-cache
        a *= 0.9999
        a += 0.5
        ops += 1
    q.put(ops * N_EL)


def run(n, dur):
    q = mp.Queue()
    start = time.time() + 0.4
    procs = [mp.Process(target=fpu_worker, args=(start, dur, q)) for _ in range(n)]
    for p in procs:
        p.start()
    tot = sum(q.get() for _ in range(n))
    for p in procs:
        p.join()
    return tot / dur


def main():
    print(f"# clean SIMD (np.sin on {N_EL*8//1024}KB L2-resident array), {DUR}s/point\n")
    print(f"{'N':>3} {'aggregate_Msin/s':>18} {'scaling_vs_N1':>14}")
    base = None
    vals = {}
    for n in NS:
        v = run(n, DUR) / 1e6
        if n == 1:
            base = v
        vals[n] = v
        print(f"{n:>3} {v:>15.0f}    {100*v/(base*n):>11.0f}%")
    print("\n--- VERDICT ---")
    g = 100 * (vals[32] / vals[16] - 1)
    print(f"compute @16={vals[16]:.0f} -> @32={vals[32]:.0f} Msin/s ({g:+.0f}% from 16->32)")
    if g > 20:
        print("=> cores CAN scale with SMT for pure compute -> self-play's W=16 cap is the MEMORY side.")
    else:
        print("=> even clean in-cache compute plateaus at ~16 -> SMT adds ~nothing on this silicon.")


if __name__ == "__main__":
    main()
