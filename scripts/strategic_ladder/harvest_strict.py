"""Harvest the agent panel's chosen action on each STRICT-opportunity position
(fresh strict_bank). Few positions -> cheap even with h6400. Sharded by idx.
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

PANEL = ["random", "greedy", "h200", "h800", "h3200", "h6400", "rod1"]
_G = None
_META = ("regime", "seed", "g", "ply", "mover", "mover_spec", "opp_spec", "tile_phase",
         "k_remaining", "scores", "margin_before", "meeples_free", "legal_n", "chosen",
         "final_margin_mover", "result_mover")


def _init():
    import torch
    torch.set_num_threads(1)
    global _G
    _G = Game(enable_legal_moves_cache=True)


def load_bank(d):
    snaps = []
    for p in sorted(glob.glob(os.path.join(d, "*.pkl"))):
        with open(p, "rb") as f:
            snaps.extend(pickle.load(f))
    return snaps


def _one(arg):
    idx, s = arg
    board = pickle.loads(s["board_pkl"])
    base = (s["seed"] * 10007 + s["ply"] * 13 + s["g"]) & 0x7FFFFFFF
    rec = {k: s.get(k) for k in _META}
    rec["idx"] = idx
    rec["strict_labels"] = s["strict_labels"]
    choices = {}
    for ai, spec in enumerate(PANEL):
        try:
            choices[spec] = int(R.make_player(spec, seed=base + ai * 131 + 1).choose(_G, board))
        except Exception:
            choices[spec] = -1
    rec["choices"] = choices
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", default="/mnt/c/carc-shared/strategic_ladder/strict_bank")
    ap.add_argument("--out", default="measurement/strategic_behavior_ladder/strict_harvest.jsonl")
    ap.add_argument("--workers", type=int, default=14)
    args = ap.parse_args()
    snaps = load_bank(args.bank)
    jobs = list(enumerate(snaps))
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    print(f"strict harvest: {len(jobs)} positions, panel={PANEL}, W={args.workers}", flush=True)
    t0, done = time.perf_counter(), 0
    ctx = get_context("fork")
    with open(args.out, "w") as f, ctx.Pool(args.workers, initializer=_init) as pool:
        for rec in pool.imap_unordered(_one, jobs, chunksize=1):
            f.write(json.dumps(rec) + "\n")
            f.flush()
            done += 1
            if done % 25 == 0 or done == len(jobs):
                dt = time.perf_counter() - t0
                print(f"  {done}/{len(jobs)} {dt:.0f}s eta {(len(jobs)-done)/(done/dt):.0f}s", flush=True)
    print(f"DONE {done} -> {args.out}")


if __name__ == "__main__":
    main()
