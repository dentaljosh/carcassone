"""Exact-K endgame conversion slice (Part A motif #8, separate labeled dataset).

For true-endgame positions we solve EXACTLY and measure each agent's conversion
REGRET = how far its move is from the exact-optimal value. One solve per position
yields every panel agent's regret via the harvest's recorded choices (no agent
re-run). Information model is labeled per depth:
  k=2 : marginalized (HONEST info -- opponent doesn't see future draws), ~5s
  k=3 : clairvoyant + alpha-beta (perfect-hindsight UPPER BOUND, feasible), labeled

This measures endgame EXECUTION, the closest exactly-solvable proxy for the spec's
"pre-endgame conversion" (true pre-endgame at k>=6 is not exactly solvable). RAM-bound
(solver TT) -> low W, LOCAL ONLY.

Run: .venv/bin/python scripts/strategic_ladder/exact_slice.py \
   --bank /mnt/c/carc-shared/strategic_ladder/bank \
   --harvest 'measurement/strategic_behavior_ladder/harvest/*.jsonl' \
   --workers 8 --cap 60 --out measurement/strategic_behavior_ladder
"""
import argparse
import glob
import json
import os
import pickle
import sys
import time
from collections import defaultdict

os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")

from multiprocessing import get_context

from carcassonne_ai.game_wrapper import Game

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "level2"))
from roster import PANEL
from endgame_solver import solve, BudgetExceeded

KS_MODE = {2: ("marginalized", False), 3: ("clairvoyant", True)}
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


def _solve_one(arg):
    idx, board_pkl, k, choices, chosen = arg
    mode, ab = KS_MODE[k]
    board = pickle.loads(board_pkl)
    try:
        res = solve(_G, board, mode=mode, budget=4_000_000, alphabeta=ab)
    except BudgetExceeded:
        return {"idx": idx, "k": k, "completed": False}
    if not res.completed or not res.child_values:
        return {"idx": idx, "k": k, "completed": False}
    vstar = res.value
    to_move = res.to_move
    opt = set(res.optimal_actions)

    def regret(a):
        if a not in res.child_values:
            return None
        v = res.child_values[a]
        return (vstar - v) if to_move == 0 else (v - vstar)

    per_agent = {}
    for ag in PANEL + ["ACTUAL"]:
        a = chosen if ag == "ACTUAL" else choices.get(ag, -1)
        r = regret(a)
        per_agent[ag] = {"regret": r, "match": (a in opt)}
    return {"idx": idx, "k": k, "mode": mode, "completed": True,
            "vstar": vstar, "n_opt": len(opt), "per_agent": per_agent}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", required=True)
    ap.add_argument("--harvest", nargs="+", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--cap", type=int, default=60, help="cap positions per k")
    ap.add_argument("--out", default="measurement/strategic_behavior_ladder")
    args = ap.parse_args()

    bank = load_bank(args.bank)
    hpaths = []
    for g in args.harvest:
        hpaths.extend(sorted(glob.glob(g)))
    hmap = {}
    for p in hpaths:
        with open(p) as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    hmap[r["idx"]] = r

    jobs = []
    per_k = defaultdict(int)
    for idx, s in enumerate(bank):
        k = s["k_remaining"]
        if k not in KS_MODE or s["tile_phase"] != "TILES":
            continue
        if per_k[k] >= args.cap or idx not in hmap:
            continue
        per_k[k] += 1
        h = hmap[idx]
        jobs.append((idx, s["board_pkl"], k, h.get("choices", {}), h.get("chosen", -1)))

    print(f"exact slice: {len(jobs)} positions ({dict(per_k)}); workers={args.workers}", flush=True)
    results = []
    t0 = time.perf_counter()
    ctx = get_context("fork")
    done = 0
    with ctx.Pool(args.workers, initializer=_init) as pool:
        for r in pool.imap_unordered(_solve_one, jobs, chunksize=1):
            results.append(r)
            done += 1
            if done % 10 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)}  {time.perf_counter()-t0:.0f}s", flush=True)

    # aggregate per agent
    agg = {ag: {"regret_sum": 0.0, "n": 0, "match": 0} for ag in PANEL + ["ACTUAL"]}
    n_done = 0
    for r in results:
        if not r.get("completed"):
            continue
        n_done += 1
        for ag, d in r["per_agent"].items():
            if d["regret"] is not None:
                agg[ag]["regret_sum"] += d["regret"]
                agg[ag]["n"] += 1
                agg[ag]["match"] += int(d["match"])

    L = ["# Exact-K endgame conversion slice\n",
         f"Solved {n_done}/{len(jobs)} positions. Info model: k=2 marginalized (honest), "
         "k=3 clairvoyant+ab (hindsight upper bound).\n",
         "| agent | mean exact regret (pts) | match-optimal % | n |",
         "|---|---|---|---|"]
    for ag in PANEL + ["ACTUAL"]:
        a = agg[ag]
        if a["n"]:
            L.append(f"| {ag} | {a['regret_sum']/a['n']:.3f} | "
                     f"{100*a['match']/a['n']:.0f}% | {a['n']} |")
        else:
            L.append(f"| {ag} | -- | -- | 0 |")
    out_md = os.path.join(args.out, "EXACT_SLICE.md")
    with open(out_md, "w") as f:
        f.write("\n".join(L) + "\n")
    with open(os.path.join(args.out, "exact_slice_raw.json"), "w") as f:
        json.dump([r for r in results if r.get("completed")], f)
    print("\n".join(L))
    print(f"\nwrote {out_md} ({time.perf_counter()-t0:.0f}s)")


if __name__ == "__main__":
    main()
