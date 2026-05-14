"""Diagnostic: why does hybrid_warmstart lose 23% of games to Tier-1?

Replays hybrid_warmstart (sims=400) vs Tier-1 with full per-move logging:
  - action chosen (decoded to human-readable form)
  - actual game scores after the move
  - virtual_score(hybrid's side) after the move — the heuristic's view of "if
    game ended now, my net score"

After each game we identify which games hybrid LOST and print a per-move
trajectory table. The pattern of interest:
  - hybrid's virtual_score climbs through the early game (it thinks it's
    winning), then collapses near the end as predicted points fail to
    materialize (farms growing slower than expected, cities never closing,
    opponent denials)

Goal: catalog the specific failure modes virtual_score is blind to, ranked
by frequency, to inform virtual_score_v2 design.
"""
from __future__ import annotations

import argparse
import math
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from carcassonne_ai.action_space import (
    decode,
    meeple_farmer_base,
    meeple_normal_base,
    meeple_pass_index,
    tile_action_count,
    tile_pass_index,
)
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import NeuralMCTS
from carcassonne_ai.rule_based_player import RuleBasedPlayer
from carcassonne_ai.virtual_score import virtual_score


_worker_net = None
_worker_device = None


def _worker_init(checkpoint_path: str) -> None:
    global _worker_net, _worker_device
    import torch
    from carcassonne_ai.network import CarcassonneNet

    _worker_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(checkpoint_path, map_location=_worker_device, weights_only=False)
    net = CarcassonneNet(n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"]).to(_worker_device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)
    _worker_net = net


def _hybrid_evaluator(game: Game):
    import torch

    def evaluator(board):
        obs, scalars = game.get_canonical_form(board, board.state.current_player)
        obs_t = torch.from_numpy(obs).unsqueeze(0).float().to(_worker_device)
        scalars_t = torch.from_numpy(scalars).unsqueeze(0).float().to(_worker_device)
        with torch.no_grad():
            logits, _ = _worker_net(obs_t, scalars_t)
            mask = game.get_valid_moves(board)
            mask_t = torch.from_numpy(mask.copy()).unsqueeze(0).bool().to(_worker_device)
            probs = _worker_net.policy_softmax_with_mask(logits, mask_t)
        diff = virtual_score(board.state, board.state.current_player)
        v = math.tanh(diff / 15.0)
        return probs[0].cpu().numpy(), v

    return evaluator


def _describe_action(game: Game, board, action_idx: int) -> str:
    """One-line human-readable description of an action."""
    W = game.window_size
    if action_idx == tile_pass_index(W):
        return "TILE_PASS"
    if action_idx == meeple_pass_index(W):
        return "MEEPLE_PASS"
    a_tile = tile_action_count(W)
    if action_idx < a_tile:
        cell, rot = divmod(action_idx, 4)
        wr, wc = divmod(cell, W)
        coord = board.offset.to_engine(wr, wc)
        return f"TILE({coord.row},{coord.column}) rot={rot}"
    norm_base = meeple_normal_base(W)
    farm_base = meeple_farmer_base(W)
    if norm_base <= action_idx < farm_base:
        slot = action_idx - norm_base
        sides = ["TOP", "RIGHT", "BOTTOM", "LEFT", "CENTER"]
        return f"MEEPLE_NORMAL {sides[slot]}"
    if farm_base <= action_idx < meeple_pass_index(W):
        slot = action_idx - farm_base
        corners = ["TL", "TR", "BL", "BR"]
        return f"MEEPLE_FARMER {corners[slot]}"
    return f"action_idx={action_idx}"


def play_one(args: tuple) -> dict:
    seed, hybrid_idx, sims = args
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    rule = RuleBasedPlayer(seed=seed)
    evaluator = _hybrid_evaluator(game)
    opp = NeuralMCTS(
        game=game,
        evaluator=evaluator,
        simulations=sims,
        seed=seed + 1,
    )

    moves: list[dict] = []
    t0 = time.perf_counter()
    move_idx = 0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        mask = game.get_valid_moves(board)
        if cur == hybrid_idx:
            opp.clear()
            action = opp.best_action(board)
            actor = "hybrid"
        else:
            action = rule.choose_action(game, board, mask)
            actor = "tier1"
        if not mask[action]:
            raise RuntimeError(f"player {cur} returned illegal action {action}")
        action_desc = _describe_action(game, board, action)
        board, _ = game.get_next_state(board, action)
        s0, s1 = board.state.scores
        vs_hybrid = virtual_score(board.state, hybrid_idx)
        moves.append(
            {
                "move": move_idx,
                "actor": actor,
                "action_idx": int(action),
                "action": action_desc,
                "score_p0": int(s0),
                "score_p1": int(s1),
                "vs_hybrid": int(vs_hybrid),  # final-scores-if-ended-now from hybrid's side
            }
        )
        move_idx += 1

    elapsed = time.perf_counter() - t0
    s0, s1 = board.state.scores
    hybrid_score = s0 if hybrid_idx == 0 else s1
    tier1_score = s1 if hybrid_idx == 0 else s0
    return {
        "seed": seed,
        "hybrid_idx": hybrid_idx,
        "hybrid_score": int(hybrid_score),
        "tier1_score": int(tier1_score),
        "hybrid_won": hybrid_score > tier1_score,
        "moves": moves,
        "elapsed_s": elapsed,
    }


def print_lost_game(r: dict) -> None:
    """Print a per-move table for a game where hybrid lost."""
    print()
    print(f"=== LOST GAME seed={r['seed']} hybrid={'p0' if r['hybrid_idx']==0 else 'p1'} "
          f"final {r['hybrid_score']}-{r['tier1_score']} ({r['elapsed_s']:.1f}s, "
          f"{len(r['moves'])} moves) ===")
    # Print every 5th move + the last 10 moves (where the lead typically flips).
    last_n = 10
    cutoff = max(0, len(r["moves"]) - last_n)
    print(f"  {'move':>4} {'actor':<7} {'action':<28} {'p0':>3} {'p1':>3} {'vs_hyb':>7}")
    prev_vs = 0
    for m in r["moves"]:
        # Print every 5th move OR within last_n OR when vs_hybrid changed by >=5.
        delta = m["vs_hybrid"] - prev_vs
        is_sample = (m["move"] % 5 == 0) or (m["move"] >= cutoff) or (abs(delta) >= 5)
        if is_sample:
            sign = "+" if m["vs_hybrid"] >= 0 else ""
            print(f"  {m['move']:>4} {m['actor']:<7} {m['action']:<28} "
                  f"{m['score_p0']:>3} {m['score_p1']:>3} {sign}{m['vs_hybrid']:>5}"
                  f"{'  *' if abs(delta) >= 5 else ''}")
        prev_vs = m["vs_hybrid"]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=10)
    p.add_argument("--sims", type=int, default=400)
    p.add_argument(
        "--checkpoint",
        type=Path,
        default=REPO_ROOT / "checkpoints" / "warmstart_canonical.pt",
    )
    p.add_argument("--seed-start", type=int, default=0)
    p.add_argument("--workers", type=int, default=None)
    args = p.parse_args()

    if args.workers is not None:
        n_workers = args.workers
    else:
        import torch
        n_workers = min(2 if torch.cuda.is_available() else 4, args.n)

    pool_args = [(args.seed_start + i, i % 2, args.sims) for i in range(args.n)]
    print(f"=== diagnose_virtual_score: hybrid vs Tier-1 at sims={args.sims}, "
          f"n={args.n}, workers={n_workers} ===")
    t0 = time.perf_counter()
    ctx = mp.get_context("spawn")
    with ctx.Pool(
        processes=n_workers,
        initializer=_worker_init,
        initargs=(str(args.checkpoint.resolve()),),
    ) as pool:
        results = []
        for r in pool.imap_unordered(play_one, pool_args, chunksize=1):
            results.append(r)
            wins = sum(1 for x in results if x["hybrid_won"])
            losses = len(results) - wins
            print(f"  ... {len(results)}/{args.n}  hybrid W={wins} L={losses}  "
                  f"(seed {r['seed']}: {r['hybrid_score']}-{r['tier1_score']} "
                  f"{'W' if r['hybrid_won'] else 'L'})")
            sys.stdout.flush()

    elapsed = time.perf_counter() - t0
    losses = [r for r in results if not r["hybrid_won"]]
    print()
    print(f"=== summary: hybrid won {len(results)-len(losses)} / {len(results)} "
          f"({(len(results)-len(losses))/len(results)*100:.0f}%) in {elapsed:.1f}s ===")
    print(f"=== {len(losses)} LOST GAMES (analyzed below) ===")
    for r in sorted(losses, key=lambda x: x["seed"]):
        print_lost_game(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
