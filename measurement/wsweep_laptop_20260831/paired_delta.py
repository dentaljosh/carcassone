#!/usr/bin/env python3
"""Paired per-game delta between two W points.

Every point plays the SAME games, so throughput can be contrasted game-by-game:
for game g,  rate_W(g) = W / elapsed_W(g)  [games/sec at saturation].
The paired ratio r(g) = rate_A(g)/rate_B(g) removes the deck entirely.
Reported as a log-ratio mean with a paired t (log is the right scale for a ratio).
"""
import json, glob, os, statistics, math, sys, itertools

OUTROOT = '/mnt/c/carc-shared/fpu_ladder'
LOGDIR = '/mnt/c/carc-shared/wsweep_laptop_20260831'


def collect(W):
    recs = {}
    order = []
    for f in glob.glob(f'{OUTROOT}/SMOKE_WSWEEP_W{W}/seed*.json'):
        r = json.load(open(f))
        recs[(r['seed'], r['a_seat'])] = (os.path.getmtime(f), r['elapsed_s'])
        order.append((os.path.getmtime(f), (r['seed'], r['a_seat'])))
    order.sort()
    steady = {k for _, k in order[0:len(order) - W]}   # drop the drain
    return recs, steady


def main():
    Ws = sorted(int(d.rsplit('W', 1)[1]) for d in glob.glob(f'{OUTROOT}/SMOKE_WSWEEP_W*'))
    data = {W: collect(W) for W in Ws}
    print('W points:', Ws)
    for A, B in itertools.combinations(Ws, 2):
        ra, sa = data[A]
        rb, sb = data[B]
        keys = (sa & sb) & set(ra) & set(rb)
        logs = [math.log((A / ra[k][1]) / (B / rb[k][1])) for k in keys]
        if len(logs) < 3:
            print(f'W{A} vs W{B}: too few paired games ({len(logs)})')
            continue
        m = statistics.mean(logs)
        se = statistics.stdev(logs) / len(logs) ** .5
        pct = (math.exp(m) - 1) * 100
        lo = (math.exp(m - 1.96 * se) - 1) * 100
        hi = (math.exp(m + 1.96 * se) - 1) * 100
        print(f'W{A} vs W{B}: n_paired={len(keys):3d}  '
              f'throughput W{A}/W{B} = {pct:+6.2f}%  '
              f'[95% CI {lo:+.2f}%, {hi:+.2f}%]  z={m / se:+5.2f}')


if __name__ == '__main__':
    main()
