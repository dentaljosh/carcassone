"""Phase 3 acceptance Tournament 2: NeuralMCTS(s=50) vs vanilla MCTS(s=100).

Network MCTS uses the warm-start network as prior + leaf evaluator. Vanilla
MCTS uses random rollouts. The acceptance criterion is >55% wins for the
network side at half the simulation budget — proves the network adds value
over pure search at equal-or-better compute efficiency.

Per-game checkpointing under data/tournament/eval_phase3/.
Resumable. Pattern matches play_mcts_vs_random.py.

Usage:
  python -u scripts/eval_neural_mcts_vs_vanilla.py \\
    --checkpoint checkpoints/warmstart_<strategy>_smoke.best.pt \\
    --n 100 \\
    --neural-sims 50 --vanilla-sims 100
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from dataclasses import asdict, dataclass
import multiprocessing as mp
from pathlib import Path

import numpy as np
import torch

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import MCTS, NeuralMCTS
from carcassonne_ai.network import CarcassonneNet


REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = REPO_ROOT / "data" / "tournament" / "eval_phase3"


@dataclass
class GameResult:
    seed: int
    neural_player: int
    neural_sims: int
    vanilla_sims: int
    score_p0: int
    score_p1: int
    diff: int  # neural - vanilla
    won_by_neural: bool
    drew: bool
    elapsed_s: float
    moves: int
    c_puct: float = 1.5  # default for backwards-compat with files that lack the field


def _c_puct_tag(c_puct: float) -> str:
    """Filename-safe tag for c_puct (e.g. 1.5 -> 'cp1p5'). Included in
    per-game checkpoint filenames so a sweep over c_puct values doesn't
    cache-collide across runs."""
    s = f"{c_puct:.2f}".replace(".", "p").rstrip("0").rstrip("p")
    return f"cp{s}"


def _result_path(neural_sims: int, vanilla_sims: int, seed: int, neural_player: int, c_puct: float = 1.5) -> Path:
    tag = _c_puct_tag(c_puct)
    return EVAL_DIR / f"n{neural_sims:04d}_v{vanilla_sims:04d}_{tag}_seed{seed:06d}_p{neural_player}.json"


def _try_load(path: Path) -> GameResult | None:
    if not path.exists():
        return None
    try:
        with path.open() as fh:
            data = json.load(fh)
        return GameResult(**data)
    except Exception:
        return None


def _save(result: GameResult) -> None:
    path = _result_path(
        result.neural_sims, result.vanilla_sims, result.seed, result.neural_player, result.c_puct
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + ".partial.json")
    with tmp.open("w") as fh:
        json.dump(asdict(result), fh)
    tmp.replace(path)


# Worker-side state — initialized once per process.
_worker_net: CarcassonneNet | None = None
_worker_device: torch.device | None = None


def _worker_init(checkpoint_path: str) -> None:
    """Initialize the network in each worker process exactly once."""
    global _worker_net, _worker_device
    _worker_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(checkpoint_path, map_location=_worker_device, weights_only=False)
    net = CarcassonneNet(n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"]).to(_worker_device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)
    _worker_net = net


def _network_evaluator(game: Game):
    """Returns a Callable[[Board], (priors, value)] using the worker's net."""
    def evaluator(board):
        obs, scalars = game.get_canonical_form(board, board.state.current_player)
        obs_t = torch.from_numpy(obs).unsqueeze(0).float().to(_worker_device)
        scalars_t = torch.from_numpy(scalars).unsqueeze(0).float().to(_worker_device)
        with torch.no_grad():
            logits, value = _worker_net(obs_t, scalars_t)
            mask = game.get_valid_moves(board)
            mask_t = torch.from_numpy(mask.copy()).unsqueeze(0).bool().to(_worker_device)
            probs = _worker_net.policy_softmax_with_mask(logits, mask_t)
        return probs[0].cpu().numpy(), float(value.item())
    return evaluator


def _play_one(args: tuple[int, int, int, int, float]) -> GameResult:
    seed, neural_player, neural_sims, vanilla_sims, c_puct = args
    cached = _try_load(_result_path(neural_sims, vanilla_sims, seed, neural_player, c_puct))
    if cached is not None:
        return cached

    import random
    random.seed(seed)

    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    evaluator = _network_evaluator(game)
    neural = NeuralMCTS(game=game, evaluator=evaluator, simulations=neural_sims, seed=seed, c_puct=c_puct)
    # Vanilla MCTS uses its OWN game so its cache doesn't poison the neural side.
    vanilla_game = Game(enable_legal_moves_cache=True)
    vanilla = MCTS(game=vanilla_game, simulations=vanilla_sims, seed=seed + 1)

    t0 = time.perf_counter()
    moves = 0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        if cur == neural_player:
            neural.clear()
            action = neural.best_action(board)
        else:
            vanilla.clear()
            # vanilla operates on its own game's wrapper; pass the SAME state.
            # Both MCTSes share the underlying CarcassonneGameState (via Board)
            # but each maintains its own legal-moves cache.
            action = vanilla.best_action(board)
        board, _ = game.get_next_state(board, action)
        moves += 1

    elapsed = time.perf_counter() - t0
    s0, s1 = board.state.scores
    diff = (s0 - s1) if neural_player == 0 else (s1 - s0)
    result = GameResult(
        seed=seed,
        neural_player=neural_player,
        neural_sims=neural_sims,
        vanilla_sims=vanilla_sims,
        score_p0=s0,
        score_p1=s1,
        diff=diff,
        won_by_neural=(diff > 0),
        drew=(diff == 0),
        elapsed_s=elapsed,
        moves=moves,
        c_puct=c_puct,
    )
    _save(result)
    return result


def _summary(results: list[GameResult], neural_sims: int, vanilla_sims: int) -> int:
    wins = sum(1 for r in results if r.won_by_neural)
    draws = sum(1 for r in results if r.drew)
    losses = len(results) - wins - draws
    avg_diff = sum(r.diff for r in results) / len(results)
    avg_moves = sum(r.moves for r in results) / len(results)
    avg_elapsed = sum(r.elapsed_s for r in results) / len(results)
    pct = wins / len(results)

    print()
    print(f"Tournament 2: NeuralMCTS(s={neural_sims}) vs vanilla MCTS(s={vanilla_sims}), {len(results)} games")
    print(f"  Neural wins:   {wins}/{len(results)} ({pct:.1%})")
    print(f"  Draws:         {draws}/{len(results)}")
    print(f"  Neural losses: {losses}/{len(results)}")
    print(f"  avg score diff (neural - vanilla): {avg_diff:+.1f}")
    print(f"  avg moves/game: {avg_moves:.0f}")
    print(f"  avg wallclock per game: {avg_elapsed:.1f}s")

    if pct > 0.55:
        print("\n  PASS: Neural wins >55% (Phase 3 acceptance Tournament 2 met).")
        return 0
    print(f"\n  FAIL: Neural wins {pct:.1%}, target >55%.")
    return 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="eval_neural_mcts_vs_vanilla")
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--neural-sims", type=int, default=50)
    p.add_argument("--vanilla-sims", type=int, default=100)
    p.add_argument("--seed-start", type=int, default=20000)
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--neural-c-puct", type=float, default=1.5,
                   help="PUCT exploration constant for NeuralMCTS (default 1.5)")
    p.add_argument("--reset", action="store_true",
                   help="Wipe matching result files before starting")
    p.add_argument("--summary-only", action="store_true",
                   help="Read existing results and summarize")
    args = p.parse_args(argv)

    pool_args = [
        (args.seed_start + i, i % 2, args.neural_sims, args.vanilla_sims, args.neural_c_puct)
        for i in range(args.n)
    ]

    if args.reset:
        for a in pool_args:
            path = _result_path(a[2], a[3], a[0], a[1], a[4])
            path.unlink(missing_ok=True)
        print(f"Wiped result files for n={args.neural_sims}, v={args.vanilla_sims}, c_puct={args.neural_c_puct}")

    if args.summary_only:
        results = [r for r in (_try_load(_result_path(a[2], a[3], a[0], a[1], a[4])) for a in pool_args) if r is not None]
        if not results:
            print("No saved games for these parameters.")
            return 0
        return _summary(results, args.neural_sims, args.vanilla_sims)

    already = sum(1 for a in pool_args if _result_path(a[2], a[3], a[0], a[1], a[4]).exists())
    n_remaining = args.n - already

    # GPU-aware default: each worker holds its own CUDA context (~500MB
    # baseline overhead) and concurrent tiny inferences thrash. Cap at 2 by
    # default when CUDA is available — the network call is fast enough that
    # NeuralMCTS-side throughput isn't the bottleneck (vanilla MCTS rollout
    # cost is). If the user wants more parallelism, --workers overrides.
    if args.workers is not None:
        n_workers = args.workers
    elif torch.cuda.is_available():
        n_workers = min(2, max(n_remaining, 1))
        print(f"  CUDA detected — defaulting to {n_workers} workers to avoid GPU thrash. Use --workers N to override.")
    else:
        n_workers = min(os.cpu_count() or 1, max(n_remaining, 1))
    print(
        f"Tournament 2: NeuralMCTS(s={args.neural_sims}, c_puct={args.neural_c_puct}) "
        f"vs vanilla MCTS(s={args.vanilla_sims}), {args.n} games, {n_workers} workers"
    )
    if already:
        print(f"  Resuming: {already}/{args.n} cached, {n_remaining} to play")

    t0 = time.perf_counter()
    results: list[GameResult] = []
    first_done_t: float | None = None
    if n_remaining > 0:
        # CUDA can't be re-initialized in forked subprocesses (raises in
        # _worker_init when the worker tries to torch.load(map_location=cuda)).
        # Use 'spawn' so each worker starts a fresh interpreter without
        # inheriting the parent's CUDA context.
        ctx = mp.get_context("spawn")
        with ctx.Pool(
            processes=n_workers,
            initializer=_worker_init,
            initargs=(str(args.checkpoint.resolve()),),
        ) as pool:
            for r in pool.imap_unordered(_play_one, pool_args, chunksize=1):
                results.append(r)
                n = len(results)
                if first_done_t is None and n > already:
                    first_done_t = time.perf_counter()
                    first_s = first_done_t - t0
                    eta = (args.n - n) * first_s / n_workers
                    m, s = divmod(eta, 60)
                    print(f"  [ETA] first new game took {first_s:.0f}s; "
                          f"~{int(m)}m{int(s):02d}s for {args.n - n} more")
                    sys.stdout.flush()
                if n % 10 == 0 or n == args.n:
                    wins = sum(1 for x in results if x.won_by_neural)
                    print(f"  ... {n}/{args.n} done, neural {wins}/{n} so far")
                    sys.stdout.flush()
    else:
        results = [_try_load(_result_path(a[2], a[3], a[0], a[1], a[4])) for a in pool_args]
        results = [r for r in results if r is not None]

    return _summary(results, args.neural_sims, args.vanilla_sims)


if __name__ == "__main__":
    sys.exit(main())
