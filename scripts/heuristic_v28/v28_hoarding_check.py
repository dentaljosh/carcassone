"""Terminal-hoarding / late meeple-in-hand pathology check for the v2.8 flat meeple term.

The flat meeple-economy term rewards free meeples with NO endgame decay (unlike the rejected
recovery-scaled variant). Concern: does it cause the agent to HOARD meeples past their value —
ending the game with unplaced meeples that score 0? This plays paired HeuristicMCTS games
(A = v2.8 meeple_k, B = v2.7) and measures, per side:
  - terminal UNPLACED meeple count (state.meeples[side]) — the hoarding signature if v2.8 > v2.7
  - unplaced meeples over the last K plies (does it hold then dump, or strand them?)
  - the win/score so we can see if hoarding co-occurs with winning (flexibility) or losing.

Pure CPU (HeuristicMCTS, no net). Measurement only.

Out: measurement/heuristic_v28/V28_HOARDING_CHECK.json
"""
from __future__ import annotations
import os, sys, json, random, dataclasses as dc
from multiprocessing import get_context

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "scripts", "heuristic_v28"))
import v28_configs; v28_configs.set_prod_env()
import numpy as np
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import HeuristicMCTS
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
OUT = os.path.join(REPO, "measurement", "heuristic_v28", "V28_HOARDING_CHECK.json")
MEEPLE_K = float(os.environ.get("V28_HOARD_K", "2.0"))
SIMS = int(os.environ.get("V28_HOARD_SIMS", "200"))


def _play(args):
    seed, a_seat = args
    cfg_a = dc.replace(DEFAULT_CONFIG, meeple_k=MEEPLE_K)  # v2.8
    random.seed(seed)
    ga = Game(enable_legal_moves_cache=True); gb = Game(enable_legal_moves_cache=True)
    a = HeuristicMCTS(game=ga, simulations=SIMS, seed=seed, heur_leaf="v2_7", leaf_cfg=cfg_a)
    b = HeuristicMCTS(game=gb, simulations=SIMS, seed=seed + 1, heur_leaf="v2_7", leaf_cfg=None)
    board = ga.get_init_board()
    # track unplaced meeples (state.meeples) by seat over plies
    a_hist, b_hist = [], []
    while ga.get_game_ended(board, 0) == 0.0:
        st = board.state
        a_hist.append(int(st.meeples[a_seat])); b_hist.append(int(st.meeples[1 - a_seat]))
        cur = st.current_player
        mcts = a if cur == a_seat else b
        mcts.clear()
        board, _ = ga.get_next_state(board, mcts.best_action(board))
    st = board.state
    # terminal UNPLACED meeple count per side (the hoarding metric)
    a_term = int(st.meeples[a_seat]); b_term = int(st.meeples[1 - a_seat])
    s0, s1 = st.scores
    diff = (s0 - s1) if a_seat == 0 else (s1 - s0)
    # mean unplaced over last 5 plies
    a_last5 = sum(a_hist[-5:]) / max(1, len(a_hist[-5:]))
    b_last5 = sum(b_hist[-5:]) / max(1, len(b_hist[-5:]))
    return {"seed": seed, "a_seat": a_seat, "a_term_unplaced": a_term, "b_term_unplaced": b_term,
            "a_last5_unplaced": round(a_last5, 2), "b_last5_unplaced": round(b_last5, 2),
            "diff": int(diff), "won_by_a": diff > 0}


def main():
    n = int(os.environ.get("V28_HOARD_N", "60"))
    seed0 = int(os.environ.get("V28_HOARD_SEED", "1908220000"))
    work = []
    for i in range(n // 2):
        work.append((seed0 + i, 0)); work.append((seed0 + i, 1))
    ctx = get_context("fork")
    with ctx.Pool(int(os.environ.get("V28_HOARD_W", "14"))) as pool:
        res = list(pool.imap_unordered(_play, work))
    n = len(res)
    a_term = sum(r["a_term_unplaced"] for r in res) / n
    b_term = sum(r["b_term_unplaced"] for r in res) / n
    a_l5 = sum(r["a_last5_unplaced"] for r in res) / n
    b_l5 = sum(r["b_last5_unplaced"] for r in res) / n
    wins = sum(r["won_by_a"] for r in res)
    # hoarding co-occurrence: of games A won, did A end with MORE unplaced than B?
    won = [r for r in res if r["won_by_a"]]
    won_more_unplaced = sum(1 for r in won if r["a_term_unplaced"] > r["b_term_unplaced"])
    out = {"n": n, "meeple_k": MEEPLE_K, "sims": SIMS,
           "a_v28_mean_terminal_unplaced": round(a_term, 3),
           "b_v27_mean_terminal_unplaced": round(b_term, 3),
           "delta_terminal_unplaced_v28_minus_v27": round(a_term - b_term, 3),
           "a_v28_mean_last5_unplaced": round(a_l5, 3),
           "b_v27_mean_last5_unplaced": round(b_l5, 3),
           "a_v28_winrate": round(wins / n, 3),
           "a_wins_n": len(won),
           "a_wins_with_more_terminal_unplaced_than_b": won_more_unplaced,
           "samples": res[:20]}
    json.dump(out, open(OUT, "w"), indent=2)
    print(json.dumps({k: v for k, v in out.items() if k != "samples"}, indent=2))
    print(f"\nINTERPRETATION: delta_terminal_unplaced > ~0.5 with high winrate => v2.8 holds more "
          f"meeples at game end (potential hoarding, but winning); ~0 => no hoarding pathology.")
    print(f"wrote -> {OUT}")


if __name__ == "__main__":
    main()
