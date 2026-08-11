"""Sanity-check the motif detectors on real greedy games (Part F.6).

Replays N greedy (RuleBasedPlayer) games, labels EVERY decision position, counts
motif firings by phase/move-type, and prints a handful of human-readable examples
per motif so a human can eyeball whether the detector is credible.

Run:  .venv/bin/python scripts/strategic_ladder/validate_motifs.py --games 6
"""
import argparse
import os
import random
import sys

# production leaf env (labeling is env-independent, but keep parity)
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")

import numpy as np

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.rule_based_player import RuleBasedPlayer
from wingedsheep.carcassonne.objects.game_phase import GamePhase

sys.path.insert(0, os.path.dirname(__file__))
import motifs as M

GEN_PLAYER_SEED = 70123


def walk_game(seed):
    """Yield (game, board, legal_actions, chosen_action) for each decision."""
    random.seed(seed)
    np.random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    player = RuleBasedPlayer(seed=GEN_PLAYER_SEED + seed)
    guard = 0
    while not game.get_game_ended(board, 0) and guard < 400:
        guard += 1
        mask = game.get_valid_moves(board)
        legal = [int(i) for i in np.flatnonzero(mask)]
        a = int(player.choose_action(game, board, mask))
        yield game, board, legal, a
        board, _ = game.get_next_state(board, a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=6)
    ap.add_argument("--examples", type=int, default=3)
    args = ap.parse_args()

    fire = {m: {"opp": 0, "took": 0} for m in M.MOTIFS}
    by_phase = {m: {} for m in M.MOTIFS}
    examples = {m: [] for m in M.MOTIFS}
    n_pos = n_tiles = n_meeple = 0

    for g in range(args.games):
        seed = 1930_000 + g
        for game, board, legal, chosen in walk_game(seed):
            n_pos += 1
            st = board.state
            if st.phase == GamePhase.TILES:
                n_tiles += 1
            else:
                n_meeple += 1
            snap = M.position_snapshot(game, board)
            labels = M.label_position(game, board, legal)
            takes = M.score_take(labels, chosen)
            for m, lab in labels.items():
                if not lab.opportunity:
                    continue
                fire[m]["opp"] += 1
                by_phase[m][snap["phase"]] = by_phase[m].get(snap["phase"], 0) + 1
                if takes[m] == "took":
                    fire[m]["took"] += 1
                if len(examples[m]) < args.examples:
                    examples[m].append({
                        "seed": seed, "phase": snap["phase"], "k": snap["k_remaining"],
                        "tile_phase": snap["phase_tile"], "to_move": snap["to_move"],
                        "scores": snap["scores"], "meeples_free": snap["meeples_free"],
                        "legal_n": len(legal), "sat_n": len(lab.satisfying),
                        "magnitude": round(lab.best_magnitude, 2),
                        "greedy_took": takes[m] == "took",
                        "detail": lab.detail,
                    })

    print(f"\n=== {args.games} greedy games | {n_pos} decisions "
          f"({n_tiles} TILES, {n_meeple} MEEPLES) ===\n")
    print(f"{'motif':14} {'opp':>6} {'took':>6} {'take%':>7}   by-phase")
    for m in M.MOTIFS:
        o, t = fire[m]["opp"], fire[m]["took"]
        rate = f"{100*t/o:.0f}%" if o else "--"
        ph = " ".join(f"{k}:{v}" for k, v in sorted(by_phase[m].items()))
        print(f"{m:14} {o:>6} {t:>6} {rate:>7}   {ph}")

    print("\n=== human-readable examples ===")
    for m in M.MOTIFS:
        if not examples[m]:
            continue
        print(f"\n--- {m} ---")
        for e in examples[m]:
            print(f"  seed={e['seed']} {e['tile_phase']} {e['phase']} k={e['k']} "
                  f"to_move=P{e['to_move']} scores={e['scores']} "
                  f"free_meeples={e['meeples_free']} | "
                  f"{e['sat_n']}/{e['legal_n']} legal satisfy, mag={e['magnitude']}, "
                  f"greedy_took={e['greedy_took']}")
            if e["detail"]:
                print(f"      detail={e['detail']}")


if __name__ == "__main__":
    main()
