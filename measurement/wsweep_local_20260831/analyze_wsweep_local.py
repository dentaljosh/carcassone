#!/usr/bin/env python3
"""Analyze the LOCAL W sweep (arb-on-both-sides cell shape, deck-paired).

Adapted from measurement/wsweep_laptop_20260831/analyze_wsweep.py — the merged laptop
analyzer, which is NOT edited. Adaptations: LOGDIR -> wsweep_local_20260831, cell name
prefix SMOKE_WSWEEP_W -> SMOKE_WSWEEPLOC_W (the laptop half already occupies
SMOKE_WSWEEP_W* on the SAME share). Estimators are byte-identical.

Every point plays the SAME n games from the SAME throwaway deck set, so the
ladder is a deck-PAIRED contrast; per-game wall time varies ~40% deck-to-deck
and unpaired points would swamp the 5%-of-peak settle threshold.

Ramp/drain: the pool is SATURATED from t=0 (n >> W, so all W slots fill
immediately). The only under-loaded phase is the DRAIN — the last W
completions. So the steady set = completions [0 .. n-W-1].

  A  steady games/h = 3600 * W / mean(elapsed_s over the steady set)
  P  PAIRED games/h = same, but over the INTERSECTION of every point's steady
     set — the fully deck-matched estimate. THIS IS THE PRIMARY.
  B  saturated wall-clock rate = (n-W) / (t[n-W-1] - T0)
  C  gross rate = n / point_wall_s (includes the drain; context only)
"""
import json, os, glob, statistics

SHARE = '/mnt/c/carc-shared'
LOGDIR = f'{SHARE}/wsweep_local_20260831'
OUTROOT = f'{SHARE}/fpu_ladder'
CELL = 'SMOKE_WSWEEPLOC_W'


def load_points():
    pts = {}
    p = f'{LOGDIR}/points.jsonl'
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if line:
                d = json.loads(line)
                pts[d['W']] = d          # last write wins (re-runs)
    return pts


def sampler(W):
    for f in glob.glob(f'{LOGDIR}/*_W{W}_samples.tsv'):
        las, avail, running = [], [], []
        for line in open(f):
            fl = line.rstrip('\n').split('\t')
            if len(fl) < 3:
                continue
            try:
                las.append(float(fl[1].split()[0]))
            except Exception:
                pass
            try:
                avail.append(int(fl[2].split('avail ')[-1]))
            except Exception:
                pass
            if len(fl) > 3:
                try:
                    running.append(int(fl[3]))
                except Exception:
                    pass
        las = las[3:] or las
        running = running[3:] or running
        return (round(statistics.median(las), 2) if las else None,
                min(avail) if avail else None,
                round(statistics.median(running), 1) if running else None)
    return None, None, None


def collect(W):
    d = f'{OUTROOT}/{CELL}{W}'
    recs = []
    for f in glob.glob(f'{d}/seed*.json'):
        try:
            r = json.load(open(f))
        except Exception:
            continue
        recs.append((os.path.getmtime(f), (r['seed'], r['a_seat']), r.get('elapsed_s')))
    recs.sort()
    return recs


def main():
    pts = load_points()
    data = {W: collect(W) for W in sorted(pts)}
    steady = {}
    for W, recs in data.items():
        n = len(recs)
        if n <= W:
            continue
        steady[W] = recs[0:n - W]                        # drop the drain

    common = None
    for W, s in steady.items():
        keys = {k for _, k, _ in s}
        common = keys if common is None else (common & keys)
    common = common or set()

    rows = []
    for W in sorted(steady):
        recs, s = data[W], steady[W]
        n = len(recs)
        el = [e for _, _, e in s if e]
        el_p = [e for _, k, e in s if e and k in common]
        t0 = pts[W]['t0']
        span = s[-1][0] - t0
        rows.append({
            'W': W, 'n': n, 'rc': pts[W]['rc'], 'wall_s': pts[W]['wall_s'],
            'steady_games': len(s), 'paired_games': len(el_p),
            'A_mean_el_s': round(statistics.mean(el), 1),
            'A_games_h': round(3600.0 * W / statistics.mean(el), 1),
            'P_mean_el_s': round(statistics.mean(el_p), 1) if el_p else None,
            'P_games_h': round(3600.0 * W / statistics.mean(el_p), 1) if el_p else None,
            'P_sem_pct': round(100 * statistics.stdev(el_p) / len(el_p) ** .5
                               / statistics.mean(el_p), 2) if len(el_p) > 2 else None,
            'B_games_h': round(len(s) / span * 3600.0, 1) if span > 0 else None,
            'C_gross_games_h': round(pts[W]['n'] / pts[W]['wall_s'] * 3600.0, 1),
        })
        la, av, run = sampler(W)
        rows[-1].update(loadavg_med=la, min_avail_MB=av, running_med=run)

    print(json.dumps(rows, indent=1))
    if not rows:
        return
    key = 'P_games_h' if all(r['P_games_h'] for r in rows) else 'A_games_h'
    peak = max(r[key] for r in rows)
    print(f'\nprimary estimator = {key}   (paired over {len(common)} common games)')
    print(f"{'W':>4} {'paired g/h':>11} {'sem%':>6} {'steady g/h':>11} {'satur g/h':>10} "
          f"{'gross g/h':>10} {'s/game':>7} {'%peak':>7} {'load':>6} {'run':>5} {'availMB':>8}")
    for r in rows:
        print(f"{r['W']:>4} {str(r['P_games_h']):>11} {str(r['P_sem_pct']):>6} "
              f"{r['A_games_h']:>11} {str(r['B_games_h']):>10} {r['C_gross_games_h']:>10} "
              f"{3600.0 / r[key]:>7.1f} {100.0 * r[key] / peak:>6.1f}% "
              f"{str(r['loadavg_med']):>6} {str(r['running_med']):>5} {str(r['min_avail_MB']):>8}")
    within = [r for r in rows if r[key] >= 0.95 * peak]
    if within:
        print(f"\nSMALLEST W within 5% of peak = {within[0]['W']} "
              f"({within[0][key]} games/h, {100.0 * within[0][key] / peak:.1f}% of peak)")
    print('argmax W =', max(rows, key=lambda x: x[key])['W'], '(NOT the settle rule)')


if __name__ == '__main__':
    main()
