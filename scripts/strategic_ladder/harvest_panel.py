"""Counterfactual panel harvest: for every labeled position in the bank, record
each PANEL agent's chosen action. Joined with the stored motif labels downstream to
compute opportunity-normalized take rates.

Agent-unbiased: every agent faces the SAME positions, so take-rate differences are
pure agent differences (not position-distribution artifacts).

Sharding for cross-box work-split: --shard k/n processes positions where idx % n == k.
Each box writes its own jsonl; merge downstream. Per-position agent seeds are derived
from the position (stable across shards) -> fully reproducible regardless of split.

Run (local half):  .venv/bin/python scripts/strategic_ladder/harvest_panel.py \
   --bank measurement/strategic_behavior_ladder/bank \
   --out  measurement/strategic_behavior_ladder/harvest/local.jsonl \
   --workers 14 --shard 0/2
"""
import argparse
import glob
import json
import os
import pickle
import sys
import time

os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")

from multiprocessing import get_context

from carcassonne_ai.game_wrapper import Game

sys.path.insert(0, os.path.dirname(__file__))
import roster as R

_META = ("regime", "band", "seed", "g", "ply", "mover", "mover_spec", "opp_spec",
         "tile_phase", "phase", "k_remaining", "legal_n", "chosen",
         "final_margin_mover", "result_mover", "meeples_free")

_G = None


def _init():
    import torch
    torch.set_num_threads(1)
    global _G
    _G = Game(enable_legal_moves_cache=True)


def load_bank(bank_dir):
    snaps = []
    for p in sorted(glob.glob(os.path.join(bank_dir, "*.pkl"))):
        with open(p, "rb") as f:
            snaps.extend(pickle.load(f))
    return snaps


def _pos_seed(s):
    return (s["seed"] * 10007 + s["ply"] * 13 + s.get("g", 0)) & 0x7FFFFFFF


def _harvest_one(arg):
    idx, s = arg
    board = pickle.loads(s["board_pkl"])
    base = _pos_seed(s)
    rec = {k: s.get(k) for k in _META}
    rec["idx"] = idx
    rec["labels"] = s["labels"]
    choices = {}
    for ai, spec in enumerate(R.PANEL):
        try:
            player = R.make_player(spec, seed=base + ai * 131 + 1)
            choices[spec] = int(player.choose(_G, board))
        except Exception as e:  # never let one agent kill the position
            choices[spec] = -1
            rec.setdefault("errors", {})[spec] = repr(e)[:120]
    rec["choices"] = choices
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", default="measurement/strategic_behavior_ladder/bank")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--shard", default="0/1", help="k/n: process positions with idx%n==k")
    ap.add_argument("--limit", type=int, default=0, help="cap positions (smoke)")
    args = ap.parse_args()

    k, n = (int(x) for x in args.shard.split("/"))
    snaps = load_bank(args.bank)
    jobs = [(i, s) for i, s in enumerate(snaps) if i % n == k]
    if args.limit:
        jobs = jobs[:args.limit]
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    print(f"bank={len(snaps)} positions; shard {k}/{n} -> {len(jobs)} positions; "
          f"workers={args.workers}; panel={R.PANEL}", flush=True)

    t0 = time.perf_counter()
    done = 0
    ctx = get_context("fork")
    with open(args.out, "w") as fout, ctx.Pool(args.workers, initializer=_init) as pool:
        for rec in pool.imap_unordered(_harvest_one, jobs, chunksize=1):
            fout.write(json.dumps(rec) + "\n")
            fout.flush()
            done += 1
            if done % 25 == 0 or done == len(jobs):
                dt = time.perf_counter() - t0
                rate = done / dt if dt else 0
                eta = (len(jobs) - done) / rate if rate else 0
                print(f"  {done}/{len(jobs)} positions  {dt:.0f}s  "
                      f"{rate:.2f} pos/s  eta {eta:.0f}s", flush=True)
    print(f"DONE shard {k}/{n}: {done} positions in {time.perf_counter()-t0:.0f}s -> {args.out}")


if __name__ == "__main__":
    main()
