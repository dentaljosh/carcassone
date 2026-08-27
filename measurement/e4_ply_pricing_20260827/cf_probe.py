#!/usr/bin/env python3
"""Time the CHAMPION COUNTERFACTUAL move at production knobs. Computes NO prices.

The counterfactual is `n` production-champion decisions plus one full archive
replay per game, and at 290 target plies over 50 games it — not the 21 exact
solves — is what sets the run's wall clock. This measures both halves:

  * `construct_s`  — `make_production_champion(verify=True)` per game,
  * `replay_s`     — walking the whole archive (python `get_next_state` + mirror
                     `advance`) to reach the target plies,
  * `cf_s`         — ONE champion decision at the production budget.

ETA discipline: the run rate is the MEAN over completed decisions, never the
first few (the order-statistic trap).
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
ARCHIVES = REPO / "measurement" / "e4_games"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="fixed_v1")
    ap.add_argument("--targets", required=True)
    ap.add_argument("--games", type=int, default=2)
    ap.add_argument("--plies-per-game", type=int, default=5)
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    from analyzer.ev_loss import prepare_env
    env = prepare_env(args.profile)
    from carcassonne_ai import rules_profile
    from carcassonne_ai.champion_factory import make_production_champion
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.mirror_protocol import advance, resolve_execution, seat

    rows = [json.loads(l) for l in Path(args.targets).open()]
    rows = [r for r in rows if r["profile"] == args.profile]
    by_game = {}
    for r in rows:
        by_game.setdefault(r["game"], []).append(r)
    stems = sorted(by_game)[: args.games]

    prof = rules_profile.activate(args.profile)
    ex = resolve_execution("inherit", profile="desktop", rust_threads=args.threads)
    out = {"profile": args.profile, "env": env, "execution": dict(ex),
           "threads": args.threads, "games": [], "cf_secs": []}

    for stem in stems:
        arc = json.loads((ARCHIVES / stem).read_text())
        seed = int(arc["deck_seed"])
        actions = [int(x) for x in arc["actions"]]
        want = sorted(r["ply"] for r in by_game[stem])[: args.plies_per_game]
        random.seed(seed)
        t0 = time.time()
        game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
        board = game.get_init_board()
        champ = make_production_champion("fair", game=game, seed=0, verify=True,
                                         **ex.factory_kwargs())
        seat(champ, board)
        construct_s = time.time() - t0
        t0 = time.time()
        cfs = []
        for i, a in enumerate(actions):
            if i in want:
                t1 = time.time()
                champ._move_idx = i
                champ.choose_action(board)
                cfs.append(time.time() - t1)
            board, _ = game.get_next_state(board, a)
            advance(champ, a)
        walk_s = time.time() - t0
        out["games"].append({
            "game": stem, "n_plies": len(actions), "construct_s": round(construct_s, 3),
            "walk_s_incl_decisions": round(walk_s, 3),
            "replay_only_s": round(walk_s - sum(cfs), 3),
            "n_decisions": len(cfs),
            "cf_secs": [round(x, 3) for x in cfs]})
        out["cf_secs"].extend(cfs)
        print(json.dumps(out["games"][-1]), flush=True)

    cf = out["cf_secs"]
    out["summary"] = {
        "n_decisions": len(cf),
        "mean_cf_s": round(statistics.fmean(cf), 3) if cf else None,
        "median_cf_s": round(statistics.median(cf), 3) if cf else None,
        "max_cf_s": round(max(cf), 3) if cf else None,
        "mean_construct_s": round(statistics.fmean(
            [g["construct_s"] for g in out["games"]]), 3),
        "mean_replay_only_s": round(statistics.fmean(
            [g["replay_only_s"] for g in out["games"]]), 3),
        "eta_note": "rate = MEAN over completed decisions, never the first few "
                    "(order-statistic trap).",
    }
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(json.dumps(out["summary"], indent=1))


if __name__ == "__main__":
    main()
