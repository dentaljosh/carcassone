"""Exact-K endgame conversion slice (Part A motif #8, separate labeled dataset).

SELF-CONTAINED: generates dedicated endgame positions (k in {2,3} TILES decisions
from agent-unbiased greedy replay -- the opportunity-gated main bank has almost none),
harvests every panel agent's choice, solves EXACTLY, and reports each agent's
conversion REGRET = distance of its move from the exact-optimal value.

Information model is labeled per depth:
  k=2 : marginalized  (HONEST -- opponent doesn't see future draws), ~5s
  k=3 : clairvoyant+ab (perfect-hindsight UPPER BOUND, feasible), labeled

This measures endgame EXECUTION -- the closest exactly-solvable proxy for the spec's
"pre-endgame conversion" (true pre-endgame k>=6 is not exactly solvable). RAM-bound
(solver TT) -> low W, LOCAL ONLY.

Run: .venv/bin/python scripts/strategic_ladder/exact_slice.py --games 60 --workers 8 \
   --out measurement/strategic_behavior_ladder
"""
import argparse
import json
import os
import pickle
import random
import sys
import time
from collections import defaultdict

os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")

from multiprocessing import get_context

import numpy as np

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.rule_based_player import RuleBasedPlayer
from wingedsheep.carcassonne.objects.game_phase import GamePhase

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "level2"))
from roster import PANEL, make_player
from endgame_solver import solve, BudgetExceeded

KS_MODE = {2: ("marginalized", False), 3: ("clairvoyant", True)}
_G = None


def _init():
    import torch
    torch.set_num_threads(1)
    global _G
    _G = Game(enable_legal_moves_cache=True)


def gen_endgame_positions(n_games, ks, max_per_game, seed_base):
    """Agent-unbiased greedy replay; snapshot k-in-ks TILES decisions."""
    out = []
    for g in range(n_games):
        seed = seed_base + g
        random.seed(seed)
        np.random.seed(seed & 0x7FFFFFFF)
        game = Game(enable_legal_moves_cache=True)
        board = game.get_init_board()
        player = RuleBasedPlayer(seed=seed)
        ply = 0
        per_k = defaultdict(int)
        while not game.get_game_ended(board, 0):
            st = board.state
            k = len(st.deck) + (1 if st.next_tile is not None else 0)
            if st.phase == GamePhase.TILES and k in ks and per_k[k] < max_per_game:
                per_k[k] += 1
                out.append({"seed": seed, "ply": ply, "k": k,
                            "board_pkl": pickle.dumps(board, protocol=pickle.HIGHEST_PROTOCOL)})
            mask = game.get_valid_moves(board)
            a = int(player.choose_action(game, board, mask))
            board, _ = game.get_next_state(board, a)
            ply += 1
    return out


def _process(arg):
    pos = arg
    k = pos["k"]
    mode, ab = KS_MODE[k]
    board = pickle.loads(pos["board_pkl"])
    base = (pos["seed"] * 10007 + pos["ply"] * 13) & 0x7FFFFFFF
    # harvest panel choices at this endgame position
    choices = {}
    for ai, spec in enumerate(PANEL):
        try:
            choices[spec] = int(make_player(spec, seed=base + ai * 131 + 1).choose(_G, board))
        except Exception:
            choices[spec] = -1
    try:
        res = solve(_G, board, mode=mode, budget=4_000_000, alphabeta=ab)
    except BudgetExceeded:
        return {"k": k, "completed": False}
    if not res.completed or not res.child_values:
        return {"k": k, "completed": False}
    vstar, to_move, opt = res.value, res.to_move, set(res.optimal_actions)

    def regret(a):
        if a not in res.child_values:
            return None
        v = res.child_values[a]
        return (vstar - v) if to_move == 0 else (v - vstar)

    per_agent = {}
    for ag in PANEL:
        a = choices.get(ag, -1)
        per_agent[ag] = {"regret": regret(a), "match": a in opt, "choice": a}
    return {"k": k, "mode": mode, "completed": True, "vstar": vstar,
            "n_opt": len(opt), "n_legal": len(res.child_values), "per_agent": per_agent}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=60)
    ap.add_argument("--max-per-game", type=int, default=2)
    ap.add_argument("--seed-base", type=int, default=1970000)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--cap", type=int, default=80, help="cap positions per k")
    ap.add_argument("--out", default="measurement/strategic_behavior_ladder")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    ks = tuple(KS_MODE)
    print(f"generating endgame positions from {args.games} greedy games (k in {ks})...", flush=True)
    pos = gen_endgame_positions(args.games, ks, args.max_per_game, args.seed_base)
    # cap per k
    capped, per_k = [], defaultdict(int)
    for p in pos:
        if per_k[p["k"]] < args.cap:
            per_k[p["k"]] += 1
            capped.append(p)
    print(f"{len(capped)} positions ({dict(per_k)}); solving with W={args.workers}", flush=True)

    results, done, t0 = [], 0, time.perf_counter()
    ctx = get_context("fork")
    with ctx.Pool(args.workers, initializer=_init) as pool:
        for r in pool.imap_unordered(_process, capped, chunksize=1):
            results.append(r)
            done += 1
            if done % 10 == 0 or done == len(capped):
                print(f"  {done}/{len(capped)}  {time.perf_counter()-t0:.0f}s", flush=True)

    agg = {ag: {"rs": 0.0, "n": 0, "match": 0} for ag in PANEL}
    by_k = defaultdict(lambda: {ag: {"rs": 0.0, "n": 0, "match": 0} for ag in PANEL})
    n_done = 0
    for r in results:
        if not r.get("completed"):
            continue
        n_done += 1
        for ag, d in r["per_agent"].items():
            if d["regret"] is not None:
                for tgt in (agg[ag], by_k[r["k"]][ag]):
                    tgt["rs"] += d["regret"]
                    tgt["n"] += 1
                    tgt["match"] += int(d["match"])

    L = ["# Exact-K endgame conversion slice\n",
         f"Solved {n_done}/{len(capped)} positions. Info model: k=2 marginalized (honest), "
         "k=3 clairvoyant+ab (hindsight upper bound). Lower regret = better conversion.\n",
         "| agent | mean exact regret (pts) | match-optimal % | n | regret k=2 | regret k=3 |",
         "|---|---|---|---|---|---|"]
    for ag in PANEL:
        a = agg[ag]
        if not a["n"]:
            L.append(f"| {ag} | -- | -- | 0 | | |")
            continue
        k2 = by_k[2][ag]; k3 = by_k[3][ag]
        r2 = f"{k2['rs']/k2['n']:.2f}" if k2["n"] else "--"
        r3 = f"{k3['rs']/k3['n']:.2f}" if k3["n"] else "--"
        L.append(f"| {ag} | {a['rs']/a['n']:.3f} | {100*a['match']/a['n']:.0f}% | {a['n']} | {r2} | {r3} |")
    out_md = os.path.join(args.out, "EXACT_SLICE.md")
    with open(out_md, "w") as f:
        f.write("\n".join(L) + "\n")
    with open(os.path.join(args.out, "exact_slice_raw.json"), "w") as f:
        json.dump([r for r in results if r.get("completed")], f)
    print("\n".join(L))
    print(f"\nwrote {out_md} ({time.perf_counter()-t0:.0f}s)")


if __name__ == "__main__":
    main()
