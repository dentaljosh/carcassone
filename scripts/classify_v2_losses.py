"""Split Phase 3 v2 T2 losses into realized vs endgame scoring.

For each lost game (NeuralMCTS s=50 vs vanilla MCTS s=100), measure:

  - realized: state.scores at the moment the last tile is placed (pre-endgame)
  - endgame:  delta between final scores (after count_final_scores) and
              realized scores. Captures farmers + incomplete cities/roads
              + cloisters with incomplete surroundings.

Per game we report:
  realized_gap = vanilla.realized - neural.realized
  endgame_gap  = vanilla.endgame  - neural.endgame
  total_gap    = realized_gap + endgame_gap   (sanity-checked vs replayed diff)

Aggregates across the losses:
  - mean realized gap, mean endgame gap, ratio
  - count of games where |endgame_gap| > |realized_gap|

Output: data/phase3_diagnostic/v2_loss_split.md

Approach: monkey-patch PointsCollector.count_final_scores to a no-op during
play. When the game ends, snapshot state.scores → realized. Restore
count_final_scores and call it once on a deepcopy → final scores.
endgame = final - realized.

Usage:
  python scripts/classify_v2_losses.py
"""
from __future__ import annotations

import copy
import json
import os
import random
import sys
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import torch

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.mcts import MCTS, NeuralMCTS

REPO_ROOT = Path(__file__).resolve().parent.parent
T2_DIR = REPO_ROOT / "data" / "tournament" / "eval_phase3"
OUT_DIR = REPO_ROOT / "data" / "phase3_diagnostic"
CKPT_PATH = REPO_ROOT / "checkpoints" / "warmstart_heuristic_tau05_prod.best.pt"
CACHE_DIR = OUT_DIR / "v2_loss_split_cache"


def _replay_split(
    seed: int, neural_player: int, neural_sims: int, vanilla_sims: int,
    net: CarcassonneNet, device: torch.device, c_puct: float = 1.5,
) -> tuple[list[int], list[int]]:
    """Replay one T2 game. Returns (realized_per_player, endgame_per_player)."""
    from wingedsheep.carcassonne.utils.points_collector import PointsCollector

    orig_final = PointsCollector.count_final_scores
    PointsCollector.count_final_scores = classmethod(lambda cls, game_state: None)

    try:
        random.seed(seed)
        game = Game(enable_legal_moves_cache=True)
        board = game.get_init_board()

        def evaluator(b):
            obs, scalars = game.get_canonical_form(b, b.state.current_player)
            obs_t = torch.from_numpy(obs).unsqueeze(0).float().to(device)
            scalars_t = torch.from_numpy(scalars).unsqueeze(0).float().to(device)
            with torch.no_grad():
                logits, value = net(obs_t, scalars_t)
                mask = game.get_valid_moves(b)
                mask_t = torch.from_numpy(mask.copy()).unsqueeze(0).bool().to(device)
                probs = net.policy_softmax_with_mask(logits, mask_t)
            return probs[0].cpu().numpy(), float(value.item())

        neural = NeuralMCTS(
            game=game, evaluator=evaluator, simulations=neural_sims,
            seed=seed, c_puct=c_puct,
        )
        vanilla_game = Game(enable_legal_moves_cache=True)
        vanilla = MCTS(game=vanilla_game, simulations=vanilla_sims, seed=seed + 1)

        while game.get_game_ended(board, 0) == 0.0:
            cur = board.state.current_player
            if cur == neural_player:
                neural.clear()
                action = neural.best_action(board)
            else:
                vanilla.clear()
                action = vanilla.best_action(board)
            board, _ = game.get_next_state(board, action)

        # count_final_scores was stubbed during play, so state.scores reflects
        # only realized-during-play points.
        realized = list(board.state.scores)

        # Restore the original final-scoring fn and run it on a deepcopy to
        # avoid mutating the captured terminal state mid-iteration.
        PointsCollector.count_final_scores = orig_final
        final_state = copy.deepcopy(board.state)
        PointsCollector.count_final_scores(final_state)
        final = list(final_state.scores)

        endgame = [final[i] - realized[i] for i in range(len(final))]
        return realized, endgame
    finally:
        PointsCollector.count_final_scores = orig_final


def _worker(args: tuple[int, int, int, int, float, int]) -> dict[str, Any]:
    """Pool worker: replay one game on CPU. Cached by seed."""
    seed, neural_player, n_sims, v_sims, c_puct, recorded_diff = args
    cache_path = CACHE_DIR / f"seed_{seed:06d}_p{neural_player}.json"
    if cache_path.exists():
        with cache_path.open() as fh:
            return json.load(fh)

    device = torch.device("cpu")
    ckpt = torch.load(CKPT_PATH, map_location=device, weights_only=False)
    net = CarcassonneNet(n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"]).to(device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)

    realized, endgame = _replay_split(
        seed=seed, neural_player=neural_player,
        neural_sims=n_sims, vanilla_sims=v_sims,
        net=net, device=device, c_puct=c_puct,
    )
    opp = 1 - neural_player
    realized_gap = realized[opp] - realized[neural_player]
    endgame_gap = endgame[opp] - endgame[neural_player]
    total_gap = realized_gap + endgame_gap
    replayed_diff = (realized[neural_player] + endgame[neural_player]) - (
        realized[opp] + endgame[opp]
    )
    sanity_ok = (total_gap == -replayed_diff)
    rec = {
        "seed": seed,
        "neural_player": neural_player,
        "recorded_diff": recorded_diff,
        "replayed_diff": replayed_diff,
        "neural_realized": realized[neural_player],
        "vanilla_realized": realized[opp],
        "neural_endgame": endgame[neural_player],
        "vanilla_endgame": endgame[opp],
        "realized_gap": realized_gap,
        "endgame_gap": endgame_gap,
        "total_gap": total_gap,
        "sanity_ok": sanity_ok,
    }
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w") as fh:
        json.dump(rec, fh)
    return rec


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="classify_v2_losses")
    p.add_argument("--max-games", type=int, default=None,
                   help="Cap the number of losses replayed (smoke testing).")
    p.add_argument("--override-sims", type=int, default=None,
                   help="Force both neural and vanilla sim counts to this value "
                        "(for cheap smoke runs; production uses recorded sims).")
    p.add_argument("--workers", type=int, default=None,
                   help="Pool workers (default: min(games, cpu_count)).")
    p.add_argument("--serial", action="store_true",
                   help="Run serially (debug; default is Pool).")
    args = p.parse_args(argv)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    losses = []
    for f in sorted(T2_DIR.glob("n0050_v0100_*.json")):
        if "_cp" in f.name:  # skip c_puct sweep games
            continue
        with f.open() as fh:
            r = json.load(fh)
        if not r.get("won_by_neural") and not r.get("drew"):
            losses.append(r)
    if not losses:
        print("No v2 T2 losses found.", file=sys.stderr)
        return 1
    if args.max_games is not None:
        losses = losses[: args.max_games]
    print(f"Splitting {len(losses)} v2 T2 losses into realized vs endgame ...")

    pool_args = []
    for r in losses:
        n_sims = args.override_sims if args.override_sims is not None else r["neural_sims"]
        v_sims = args.override_sims if args.override_sims is not None else r["vanilla_sims"]
        pool_args.append((
            r["seed"], r["neural_player"], n_sims, v_sims,
            r.get("c_puct", 1.5), r["diff"],
        ))

    if args.serial:
        per_game = [_worker(a) for a in pool_args]
    else:
        n_workers = args.workers or min(len(pool_args), os.cpu_count() or 1)
        print(f"  Pool: {n_workers} workers (CPU inference)")
        sys.stdout.flush()
        with Pool(processes=n_workers) as pool:
            per_game = []
            for rec in pool.imap_unordered(_worker, pool_args, chunksize=1):
                per_game.append(rec)
                print(f"  [{len(per_game)}/{len(pool_args)}] seed={rec['seed']} "
                      f"replayed_diff={rec['replayed_diff']:+d} "
                      f"realized_gap={rec['realized_gap']:+d} "
                      f"endgame_gap={rec['endgame_gap']:+d}")
                sys.stdout.flush()
        per_game.sort(key=lambda g: g["seed"])

    n = len(per_game)
    mean_realized = sum(g["realized_gap"] for g in per_game) / n
    mean_endgame = sum(g["endgame_gap"] for g in per_game) / n
    endgame_dominated = sum(
        1 for g in per_game if abs(g["endgame_gap"]) > abs(g["realized_gap"])
    )
    sanity_failures = sum(1 for g in per_game if not g["sanity_ok"])

    if abs(mean_realized) < 1e-9:
        ratio_str = "n/a (zero realized gap)"
    else:
        ratio_str = f"{mean_endgame / mean_realized:+.2f}"

    out = OUT_DIR / "v2_loss_split.md"
    with out.open("w") as fh:
        fh.write("# v2 T2 Loss Split: Realized vs Endgame\n\n")
        fh.write(
            f"Replayed {n} losses from `data/tournament/eval_phase3/n0050_v0100_*.json`. "
            "Each game's score split into realized (in-play) and endgame "
            "(farmers + incomplete features). Gap = vanilla - neural "
            "(positive = neural lost the category).\n\n"
        )

        fh.write("## Aggregate\n\n")
        fh.write("| Metric | Value |\n")
        fh.write("|---|---|\n")
        fh.write(f"| Games | {n} |\n")
        fh.write(f"| Mean realized gap (vanilla - neural) | {mean_realized:+.1f} |\n")
        fh.write(f"| Mean endgame gap (vanilla - neural) | {mean_endgame:+.1f} |\n")
        fh.write(f"| Endgame / realized ratio | {ratio_str} |\n")
        fh.write(f"| Games where \\|endgame gap\\| > \\|realized gap\\| | {endgame_dominated} / {n} |\n")
        fh.write(f"| Sanity check failures (total_gap != -replayed_diff) | {sanity_failures} / {n} |\n\n")

        fh.write("## Per-game detail\n\n")
        fh.write("| Seed | Net plays | Recorded diff | Replayed diff | Net realized | Van realized | Net endgame | Van endgame | Realized gap | Endgame gap | Total gap | Sanity |\n")
        fh.write("|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        for g in per_game:
            fh.write(
                f"| {g['seed']} | P{g['neural_player']} | {g['recorded_diff']:+d} | {g['replayed_diff']:+d} | "
                f"{g['neural_realized']} | {g['vanilla_realized']} | "
                f"{g['neural_endgame']} | {g['vanilla_endgame']} | "
                f"{g['realized_gap']:+d} | {g['endgame_gap']:+d} | {g['total_gap']:+d} | "
                f"{'OK' if g['sanity_ok'] else 'FAIL'} |\n"
            )
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
