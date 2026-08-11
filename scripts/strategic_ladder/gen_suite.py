"""Generate the full strategic-ladder position bank as ONE flat, work-stealing
game pool (so cheap games free workers for the h6400 long-poles instead of
blocking behind a per-regime barrier). Sharded across boxes by job index.

Regimes:
  D1 sources (panel-harvested, agent-unbiased once harvested):
    greedy:greedy, rod1:rod1, h800:h800, rod1:random, greedy:random, h800:random
  D2 regime contrast (mover's ACTUAL move scored; strong-vs-weak / strong-vs-strong):
    rod1:random, h6400:random, h3200:random, h200:random, rod1:h6400, h3200:h6400,
    random:random (baseline)

Thresholds were tuned on greedy DEV games (seed band 1930xxx) and FROZEN; this whole
suite (1940xxx+) is the HELD-OUT test set (Part F.1 dev/test split).

Run (local):  .venv/bin/python scripts/strategic_ladder/gen_suite.py \
   --workers 14 --shard 0/2 --out /mnt/c/carc-shared/strategic_ladder/bank
Run (laptop): ... --shard 1/2 --out /mnt/carc-shared/strategic_ladder/bank
"""
import argparse
import os
import pickle
import sys
import time

os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")

sys.path.insert(0, os.path.dirname(__file__))
import gen_positions as G
import motifs as M

# (regime, games, seed_base)
SUITE = [
    ("greedy:greedy", 14, 1940000),
    ("rod1:rod1",     14, 1941000),
    ("h800:h800",     10, 1942000),
    ("rod1:random",   14, 1943000),
    ("greedy:random", 10, 1944000),
    ("h800:random",   10, 1945000),
    ("h6400:random",   8, 1961000),
    ("h3200:random",   8, 1962000),
    ("h200:random",    8, 1963000),
    ("rod1:h6400",     8, 1964000),
    ("h3200:h6400",    8, 1965000),
    ("random:random",  8, 1966000),
]
MAX_PER_GAME = 40
BAND = "test"


def build_jobs():
    jobs = []
    for regime, games, seed_base in SUITE:
        a, b = regime.split(":")
        for i in range(games):
            jobs.append((a, b, seed_base + i, i, MAX_PER_GAME, regime, BAND))
    return jobs


def _est_cost(job):
    """rough core-seconds, to put expensive games first (better pool packing)."""
    a, b = job[0], job[1]
    w = {"h6400": 900, "h3200": 450, "h800": 120, "h200": 40,
         "rod1": 90, "iter08": 90, "greedy": 5, "random": 1}
    return w.get(a, 30) + w.get(b, 30)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--out", default="measurement/strategic_behavior_ladder/bank")
    args = ap.parse_args()

    k, n = (int(x) for x in args.shard.split("/"))
    jobs = build_jobs()
    jobs.sort(key=_est_cost, reverse=True)            # heavy first
    shard = [j for i, j in enumerate(jobs) if i % n == k]
    os.makedirs(args.out, exist_ok=True)
    out_pkl = os.path.join(args.out, f"suite_shard{k}of{n}.pkl")

    print(f"suite: {len(jobs)} games total; shard {k}/{n} -> {len(shard)} games; "
          f"workers={args.workers}", flush=True)

    from multiprocessing import get_context
    ctx = get_context("fork")
    all_snaps = []
    done = 0
    t0 = time.perf_counter()
    with ctx.Pool(args.workers, initializer=G._worker_init) as pool:
        for snaps in pool.imap_unordered(G._play_one, shard):
            all_snaps.extend(snaps)
            done += 1
            dt = time.perf_counter() - t0
            print(f"  {done}/{len(shard)} games  snaps={len(all_snaps)}  {dt:.0f}s", flush=True)
            # checkpoint periodically (crash safety on long h6400 runs)
            if done % 10 == 0:
                with open(out_pkl, "wb") as f:
                    pickle.dump(all_snaps, f, protocol=pickle.HIGHEST_PROTOCOL)

    with open(out_pkl, "wb") as f:
        pickle.dump(all_snaps, f, protocol=pickle.HIGHEST_PROTOCOL)
    n_opp = {m: sum(1 for s in all_snaps if m in s["labels"]) for m in M.MOTIFS}
    by_regime = {}
    for s in all_snaps:
        by_regime[s["regime"]] = by_regime.get(s["regime"], 0) + 1
    print(f"\nDONE shard {k}/{n}: {len(all_snaps)} snaps in {time.perf_counter()-t0:.0f}s")
    print(f"  opp counts: {n_opp}")
    print(f"  by regime: {by_regime}")
    print(f"  wrote {out_pkl}")


if __name__ == "__main__":
    main()
