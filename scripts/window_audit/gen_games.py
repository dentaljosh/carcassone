"""Generate champion-leaf self-play games for the window audit (top-up to >=2000).

Uses HeuristicMCTS with heur_leaf='v2_7' (== the champion leaf, built from the
CARCASSONNE_V25_*/V29_* env block) as BOTH players. Net-on-CPU generation of
thousands of games with the actual net champion is hours-infeasible; the board
GEOMETRY that drives window overflow is set by placement-policy quality, which
the v2.7 leaf + MCTS captures (it is the reference-ladder / RoDv2-tier opponent).

Records (deck_seed, action_sequence) as GameRecord jsonl — losslessly replayable
by root_replay. Parallel over deck seeds with a bounded Pool.
"""
import argparse
import os
import random
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts" / "measurement_infra"))

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import HeuristicMCTS
from root_replay import GameRecord, save_games


def gen_one(deck_seed: int, sims: int) -> GameRecord:
    random.seed(int(deck_seed))
    game = Game(window_size=25, enable_legal_moves_cache=True)
    board = game.get_init_board()
    mcts = HeuristicMCTS(game, simulations=sims, heur_leaf="v2_7", seed=deck_seed)
    actions = []
    while game.get_game_ended(board, board.state.current_player) == 0.0:
        mcts.clear()
        a = int(mcts.best_action(board))
        actions.append(a)
        board, _ = game.get_next_state(board, a)
    return GameRecord(game_id=int(deck_seed), deck_seed=int(deck_seed),
                      actions=actions, n_plies=len(actions),
                      meta={"gen": "heur_v2_7", "sims": sims})


def _worker(args):
    seed, sims = args
    return gen_one(seed, sims)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1400)
    ap.add_argument("--seed-base", type=int, default=7_000_000)
    ap.add_argument("--sims", type=int, default=100)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", default="measurement/window_audit/gen_games.jsonl")
    args = ap.parse_args()

    seeds = [(args.seed_base + i, args.sims) for i in range(args.n)]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    if args.workers <= 1:
        games = [_worker(s) for s in seeds]
    else:
        from multiprocessing import Pool
        with Pool(args.workers) as pool:
            games = []
            for i, g in enumerate(pool.imap_unordered(_worker, seeds, chunksize=4)):
                games.append(g)
                if (i + 1) % 100 == 0:
                    print(f"generated {i+1}/{args.n}", flush=True)
    save_games(args.out, games)
    print(f"wrote {len(games)} games to {args.out}")


if __name__ == "__main__":
    main()
