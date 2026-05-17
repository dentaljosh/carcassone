"""Phase 4 head-to-head: iter_N vs iter_(N-1) with NeuralMCTS each side.

Both checkpoints run NeuralMCTS at the same simulation budget (eval-only,
no Dirichlet noise). Alternates which side plays first; per-game JSON
checkpointing so reruns skip cached games.

Output: writes a single ELO-log entry to `<output-root>/elo_log.json`
(appends if the file already exists). Per-game results live under
`<output-root>/eval/iter_<NN>_vs_<MM>/`.

Usage:
  python -u scripts/eval_iter_head_to_head.py \\
      --new-checkpoint checkpoints/selfplay/iter_01.pt \\
      --old-checkpoint checkpoints/selfplay/iter_00.pt \\
      --output-root data/selfplay/calibration \\
      --iter 1 --vs-iter 0 --games 10 --sims 50 --workers 4
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch

from carcassonne_ai.elo import update_pair
from carcassonne_ai.eval_server import (
    ServerHandles,
    shutdown_server,
    start_server,
)
from carcassonne_ai.eval_server_pool import (
    shutdown_server_pool,
    start_server_pool,
)
from carcassonne_ai.evaluators import (
    make_batch_evaluator,
    make_batch_evaluator_policy_only,
    make_single_evaluator,
    make_single_evaluator_policy_only,
    make_v25_batch_value_wrapper,
    make_v25_value_wrapper,
)
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import NeuralMCTS
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.remote_evaluators import (
    make_remote_batch_evaluator,
    make_remote_single_evaluator,
)


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class GameResult:
    seed: int
    new_player: int
    sims: int
    score_p0: int
    score_p1: int
    diff: int  # new - old
    won_by_new: bool
    drew: bool
    elapsed_s: float
    moves: int


# Per-worker globals — both checkpoints loaded once per process in the
# default (no-orchestrator) path. In orchestrator mode `_worker_new` and
# `_worker_old` stay None and the corresponding `_worker_*_handles` point
# at the two server processes (one per net).
_worker_new: CarcassonneNet | None = None
_worker_old: CarcassonneNet | None = None
_worker_device: torch.device | None = None
_worker_sims: int = 0
_worker_c_puct: float = 1.5
_worker_eval_dir: str = ""
_worker_batch_size: int = 1
_worker_virtual_loss: float = 1.0
_worker_use_fp16: bool = False
_worker_leaf_eval: str = "nn"  # "nn" or "v2_5" — see DECISIONS.md 2026-05-14
# Per-side LeafConfig (used only when leaf_eval == "v2_5"). None → the
# env-built DEFAULT_CONFIG (v2.7). Distinct new/old configs let a single
# head-to-head A/B two leaf variants — e.g. tile-counting vs v2.7.
_worker_new_leaf_cfg = None
_worker_old_leaf_cfg = None
_worker_new_handles: ServerHandles | None = None
_worker_old_handles: ServerHandles | None = None


def _result_path(eval_dir: str, sims: int, seed: int, new_player: int) -> Path:
    return Path(eval_dir) / f"s{sims:04d}_seed{seed:06d}_p{new_player}.json"


def _try_load(path: Path) -> GameResult | None:
    if not path.exists():
        return None
    try:
        with path.open() as fh:
            return GameResult(**json.load(fh))
    except Exception:
        return None


def _save(eval_dir: str, result: GameResult) -> None:
    path = _result_path(eval_dir, result.sims, result.seed, result.new_player)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + ".partial.json")
    with tmp.open("w") as fh:
        json.dump(asdict(result), fh)
    tmp.replace(path)


def _load_net(path: str, device: torch.device) -> CarcassonneNet:
    ckpt = torch.load(path, map_location=device, weights_only=False)
    net = CarcassonneNet(
        n_filters=ckpt["n_filters"], n_blocks=ckpt["n_blocks"]
    ).to(device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)
    return net


def _leaf_config_for(variant: str):
    """Map a --{new,old}-leaf-variant name to a LeafConfig (or None).

    'v2_7' → None (the worker falls back to the env-built DEFAULT_CONFIG).
    'tile_counting' → DEFAULT_CONFIG with the hard deck-aware closure gate on.
    'tile_counting_cont' → DEFAULT_CONFIG with the continuous deck-aware
        closure ramp on (slack=3.0).
    """
    if variant == "v2_7":
        return None
    from dataclasses import replace
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
    if variant == "tile_counting":
        return replace(DEFAULT_CONFIG, tile_counting_closure=True)
    if variant == "tile_counting_cont":
        return replace(DEFAULT_CONFIG, closure_continuous_slack=3.0)
    raise ValueError(f"unknown leaf variant: {variant}")


def _worker_init(
    new_path: str, old_path: str, sims: int, c_puct: float, eval_dir: str,
    batch_size: int, virtual_loss: float, use_fp16: bool = False,
    orch_cfg: dict | None = None, leaf_eval: str = "nn",
    new_leaf_cfg=None, old_leaf_cfg=None,
) -> None:
    """Pool initializer.

    Default (no-orchestrator) mode: load both checkpoints into per-worker
    VRAM and store on globals.

    Orchestrator mode (orch_cfg is not None): skip both checkpoint loads;
    pop a worker_id from the shared id_q and build two ServerHandles
    (one per server process) pointing at the per-worker response queues.

    `new_leaf_cfg` / `old_leaf_cfg` are optional `virtual_score_v2.LeafConfig`
    objects (used only under leaf_eval="v2_5"); None → DEFAULT_CONFIG.
    """
    global _worker_new, _worker_old, _worker_device, _worker_sims, _worker_c_puct, _worker_eval_dir
    global _worker_batch_size, _worker_virtual_loss, _worker_use_fp16, _worker_leaf_eval
    global _worker_new_leaf_cfg, _worker_old_leaf_cfg
    global _worker_new_handles, _worker_old_handles

    _worker_sims = sims
    _worker_c_puct = c_puct
    _worker_eval_dir = eval_dir
    _worker_batch_size = batch_size
    _worker_virtual_loss = virtual_loss
    _worker_use_fp16 = use_fp16
    _worker_leaf_eval = leaf_eval
    _worker_new_leaf_cfg = new_leaf_cfg
    _worker_old_leaf_cfg = old_leaf_cfg

    if orch_cfg is not None:
        _worker_device = torch.device("cpu")
        _worker_new = None
        _worker_old = None
        # Pull global worker_id, then look up the per-pool routing bundle.
        # Pool layer (eval_server_pool.start_server_pool) has already done
        # the worker_id % n_shards math; we just dereference.
        worker_id = orch_cfg["id_q"].get()
        _worker_new_handles = orch_cfg["new_handles_by_worker"][worker_id]
        _worker_old_handles = orch_cfg["old_handles_by_worker"][worker_id]
        return

    _worker_device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )
    _worker_new = _load_net(new_path, _worker_device)
    _worker_old = _load_net(old_path, _worker_device)


def _play_one(args: tuple[int, int]) -> GameResult:
    seed, new_player = args
    cached = _try_load(_result_path(_worker_eval_dir, _worker_sims, seed, new_player))
    if cached is not None:
        return cached

    import random
    random.seed(seed)

    game_new = Game(enable_legal_moves_cache=True)
    game_old = Game(enable_legal_moves_cache=True)
    if _worker_new_handles is not None:
        # Orchestrator mode: two remote evaluators talking to two servers.
        assert _worker_old_handles is not None
        new_eval = make_remote_single_evaluator(_worker_new_handles, game_new)
        old_eval = make_remote_single_evaluator(_worker_old_handles, game_old)
        new_batch_eval = None
        old_batch_eval = None
        if _worker_batch_size > 1:
            new_batch_eval = make_remote_batch_evaluator(
                _worker_new_handles, game_new
            )
            old_batch_eval = make_remote_batch_evaluator(
                _worker_old_handles, game_old
            )
    else:
        assert _worker_new is not None and _worker_old is not None
        use_policy_only = _worker_leaf_eval != "nn"
        single_factory = (
            make_single_evaluator_policy_only if use_policy_only
            else make_single_evaluator
        )
        new_eval = single_factory(
            _worker_new, _worker_device, game_new, use_fp16=_worker_use_fp16
        )
        old_eval = single_factory(
            _worker_old, _worker_device, game_old, use_fp16=_worker_use_fp16
        )
        new_batch_eval = None
        old_batch_eval = None
        if _worker_batch_size > 1:
            batch_factory = (
                make_batch_evaluator_policy_only if use_policy_only
                else make_batch_evaluator
            )
            new_batch_eval = batch_factory(
                _worker_new, _worker_device, game_new, use_fp16=_worker_use_fp16
            )
            old_batch_eval = batch_factory(
                _worker_old, _worker_device, game_old, use_fp16=_worker_use_fp16
            )

    # v2.5 leaf-eval swap: replace each side's NN value with virtual_score_v2.
    # Each side carries its own LeafConfig — normally identical (apples-to-
    # apples), but a leaf A/B run gives them different configs. See
    # DECISIONS.md 2026-05-14 + the 2026-05-17 Option-1 plan.
    if _worker_leaf_eval == "v2_5":
        new_eval = make_v25_value_wrapper(new_eval, _worker_new_leaf_cfg)
        old_eval = make_v25_value_wrapper(old_eval, _worker_old_leaf_cfg)
        if new_batch_eval is not None:
            new_batch_eval = make_v25_batch_value_wrapper(new_batch_eval, _worker_new_leaf_cfg)
        if old_batch_eval is not None:
            old_batch_eval = make_v25_batch_value_wrapper(old_batch_eval, _worker_old_leaf_cfg)

    new_mcts = NeuralMCTS(
        game=game_new, evaluator=new_eval, simulations=_worker_sims,
        seed=seed, c_puct=_worker_c_puct,
        batch_size=_worker_batch_size, batch_evaluator=new_batch_eval,
        virtual_loss=_worker_virtual_loss,
    )
    old_mcts = NeuralMCTS(
        game=game_old, evaluator=old_eval, simulations=_worker_sims,
        seed=seed + 1, c_puct=_worker_c_puct,
        batch_size=_worker_batch_size, batch_evaluator=old_batch_eval,
        virtual_loss=_worker_virtual_loss,
    )

    board = game_new.get_init_board()
    moves = 0
    t0 = time.perf_counter()
    while game_new.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        if cur == new_player:
            new_mcts.clear()
            action = new_mcts.best_action(board)
        else:
            old_mcts.clear()
            action = old_mcts.best_action(board)
        board, _ = game_new.get_next_state(board, action)
        moves += 1

    s0, s1 = board.state.scores
    diff = (s0 - s1) if new_player == 0 else (s1 - s0)
    result = GameResult(
        seed=seed, new_player=new_player, sims=_worker_sims,
        score_p0=s0, score_p1=s1, diff=diff,
        won_by_new=(diff > 0), drew=(diff == 0),
        elapsed_s=time.perf_counter() - t0, moves=moves,
    )
    _save(_worker_eval_dir, result)
    return result


def _append_elo_log(
    output_root: Path, iter_n: int, iter_prev: int,
    wins: int, losses: int, draws: int,
) -> dict:
    log_path = output_root / "elo_log.json"
    entries: list[dict]
    if log_path.exists():
        with log_path.open() as fh:
            entries = json.load(fh)
    else:
        entries = []

    # Anchor: previous iter's ELO is whatever the latest log entry recorded
    # for it. iter_-1 baseline is 0.
    prev_elo = 0.0
    for e in entries:
        if e["iter"] == iter_prev:
            prev_elo = float(e["elo_estimate"])
    new_elo, delta = update_pair(
        iter_n_elo_estimate=0.0,
        iter_prev_elo=prev_elo,
        wins=wins, losses=losses, draws=draws,
    )
    entry = {
        "iter": iter_n,
        "vs_iter": iter_prev,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "elo_delta": round(delta, 1),
        "elo_estimate": round(new_elo, 1),
    }
    entries.append(entry)
    with log_path.open("w") as fh:
        json.dump(entries, fh, indent=2)
    return entry


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="eval_iter_head_to_head")
    p.add_argument("--new-checkpoint", type=Path, required=True)
    p.add_argument("--old-checkpoint", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    p.add_argument("--iter", type=int, required=True, dest="iter_idx")
    p.add_argument("--vs-iter", type=int, required=True)
    p.add_argument("--games", type=int, default=10)
    p.add_argument("--sims", type=int, default=50)
    p.add_argument("--c-puct", type=float, default=1.5)
    p.add_argument("--workers", type=int, default=8,
                   help="Pool workers. Default 8 leaves SMT headroom for "
                        "other workloads on a 5800X. For dedicated runs, "
                        "W=16 is the empirical local optimum (measured "
                        "2026-05-09 on RTX 5060 Ti).")
    p.add_argument("--seed-start", type=int, default=900_000,
                   help="Eval seed base (kept high so it doesn't collide with "
                        "self-play seeds, which use iter * 10_000 + game_idx).")
    p.add_argument(
        "--batch-size", type=int, default=1,
        help="NeuralMCTS batch size for virtual-loss / batched-eval mode "
             "during head-to-head. 1 (default) = serial.",
    )
    p.add_argument(
        "--virtual-loss", type=float, default=1.0,
        help="W-penalty for in-flight nodes; only matters when --batch-size > 1.",
    )
    p.add_argument(
        "--fp16", action="store_true",
        help="Run network forward passes under torch.amp.autocast(fp16) on "
             "CUDA. Default off.",
    )
    p.add_argument(
        "--no-elo-log", action="store_true",
        help="Skip writing to elo_log.json. Use for ad-hoc anchor evals "
             "(e.g. iter_29 vs warmstart_canonical) that shouldn't pollute "
             "the chained ELO record.",
    )
    p.add_argument(
        "--orchestrator", action="store_true",
        help="GPU inference-server mode (2 servers, one per net). Workers "
             "are CPU-only and send requests over IPC. Default off; "
             "numerically identical to per-worker path within float32 noise.",
    )
    p.add_argument(
        "--leaf-eval", choices=["nn", "v2_5"], default="nn",
        help="Source of the leaf VALUE during MCTS (applied to BOTH sides "
             "for apples-to-apples comparison). 'nn' (default) uses each "
             "net's value head. 'v2_5' uses tanh(virtual_score_v2/15) for "
             "both sides, matching local production (DECISIONS.md 2026-05-14). "
             "Priors always come from the network — only the leaf value "
             "source changes.",
    )
    p.add_argument(
        "--new-leaf-variant",
        choices=["v2_7", "tile_counting", "tile_counting_cont"], default="v2_7",
        help="LeafConfig variant for the NEW side (only under --leaf-eval v2_5). "
             "'v2_7' = the env-built default. 'tile_counting' = v2.7 + the hard "
             "deck-aware closure gate. 'tile_counting_cont' = v2.7 + the "
             "continuous deck-aware closure ramp (Option-1 plan, 2026-05-17). "
             "Set this different from --old-leaf-variant to A/B two leaves "
             "in one run.",
    )
    p.add_argument(
        "--old-leaf-variant",
        choices=["v2_7", "tile_counting", "tile_counting_cont"], default="v2_7",
        help="LeafConfig variant for the OLD side. See --new-leaf-variant.",
    )
    p.add_argument("--orch-max-batch", type=int, default=256)
    p.add_argument("--orch-batch-timeout-ms", type=float, default=2.0)
    p.add_argument(
        "--orch-shards", type=int, default=1,
        help="Number of parallel eval-server processes per net (new+old "
             "each get their own pool of N shards). Default 1 = single "
             "server per net (back-compat). VRAM cost ~2 GB × N × 2 nets; "
             "watch the VRAM budget at high shard counts.",
    )
    args = p.parse_args(argv)

    eval_dir = (
        args.output_root / "eval" /
        f"iter_{args.iter_idx:02d}_vs_{args.vs_iter:02d}"
    )
    eval_dir.mkdir(parents=True, exist_ok=True)

    # Auto-cap removed 2026-05-09 (see run_selfplay_iter.py for rationale).
    # Note: head-to-head loads TWO networks per worker (2× GPU memory vs
    # self-play). Should still be fine on 16GB cards at W=16 (~200MB ×
    # 16 × 2 = 6.4GB), but watch nvidia-smi if you scale up.
    n_workers = min(args.workers, args.games)

    pool_args = [
        (args.seed_start + i, i % 2) for i in range(args.games)
    ]
    print(
        f"head-to-head: iter_{args.iter_idx:02d} vs iter_{args.vs_iter:02d}, "
        f"{args.games} games at sims={args.sims}, c_puct={args.c_puct}, "
        f"{n_workers} workers, eval_dir={eval_dir}, "
        f"orchestrator={args.orchestrator}, leaf_eval={args.leaf_eval}"
    )
    sys.stdout.flush()

    t0 = time.perf_counter()
    ctx = mp.get_context("spawn")
    results: list[GameResult] = []

    # Orchestrator: two server pools (one per net). Each pool can be sharded
    # for GIL bypass; routing is by worker_id % n_shards within each pool.
    new_pool = None
    old_pool = None
    orch_cfg: dict | None = None
    if args.orchestrator:
        print(
            f"  starting eval-server pools "
            f"(shards={args.orch_shards}, "
            f"max_batch={args.orch_max_batch}, "
            f"timeout={args.orch_batch_timeout_ms}ms, fp16={args.fp16})…"
        )
        sys.stdout.flush()
        policy_only = (args.leaf_eval != "nn")
        new_pool = start_server_pool(
            checkpoint_path=str(args.new_checkpoint),
            n_workers=n_workers,
            n_shards=args.orch_shards,
            max_batch=args.orch_max_batch,
            batch_timeout_ms=args.orch_batch_timeout_ms,
            use_fp16=args.fp16,
            policy_only=policy_only,
        )
        old_pool = start_server_pool(
            checkpoint_path=str(args.old_checkpoint),
            n_workers=n_workers,
            n_shards=args.orch_shards,
            max_batch=args.orch_max_batch,
            batch_timeout_ms=args.orch_batch_timeout_ms,
            use_fp16=args.fp16,
            policy_only=policy_only,
        )
        id_q = ctx.Queue()
        for w in range(n_workers):
            id_q.put(w)
        orch_cfg = {
            "new_handles_by_worker": new_pool.handles_by_worker,
            "old_handles_by_worker": old_pool.handles_by_worker,
            "id_q": id_q,
        }
        new_pids = [p.pid for p in new_pool.procs if p is not None]
        old_pids = [p.pid for p in old_pool.procs if p is not None]
        print(
            f"  eval-server pools ready "
            f"(new pids={new_pids}, old pids={old_pids})"
        )
        sys.stdout.flush()

    new_leaf_cfg = _leaf_config_for(args.new_leaf_variant)
    old_leaf_cfg = _leaf_config_for(args.old_leaf_variant)
    try:
        with ctx.Pool(
            processes=n_workers,
            initializer=_worker_init,
            initargs=(
                str(args.new_checkpoint), str(args.old_checkpoint),
                args.sims, args.c_puct, str(eval_dir),
                args.batch_size, args.virtual_loss, args.fp16,
                orch_cfg, args.leaf_eval,
                new_leaf_cfg, old_leaf_cfg,
            ),
        ) as pool:
            for done, r in enumerate(
                pool.imap_unordered(_play_one, pool_args, chunksize=1), 1
            ):
                results.append(r)
                wins_so_far = sum(1 for x in results if x.won_by_new)
                if done % max(1, args.games // 5) == 0 or done == args.games:
                    print(f"  ... {done}/{args.games}, new wins {wins_so_far}/{done}")
                    sys.stdout.flush()
    finally:
        if new_pool is not None:
            shutdown_server_pool(new_pool)
        if old_pool is not None:
            shutdown_server_pool(old_pool)
    elapsed = time.perf_counter() - t0

    wins = sum(1 for r in results if r.won_by_new)
    draws = sum(1 for r in results if r.drew)
    losses = args.games - wins - draws
    avg_diff = sum(r.diff for r in results) / args.games

    if args.no_elo_log:
        # Compute the standalone delta (anchor at 0) for reporting only;
        # don't touch the chain log.
        from carcassonne_ai.elo import update_pair
        _new_elo, delta = update_pair(
            iter_n_elo_estimate=0.0, iter_prev_elo=0.0,
            wins=wins, losses=losses, draws=draws,
        )
        print(
            f"\nANCHOR EVAL ({args.new_checkpoint.name} vs {args.old_checkpoint.name}): "
            f"{wins}W/{draws}D/{losses}L, avg diff {avg_diff:+.1f}, "
            f"elo_delta {delta:+.1f} (no log entry written), "
            f"wallclock {elapsed:.1f}s"
        )
    else:
        entry = _append_elo_log(
            args.output_root, args.iter_idx, args.vs_iter, wins, losses, draws
        )
        print(
            f"\niter_{args.iter_idx:02d} vs iter_{args.vs_iter:02d}: "
            f"{wins}W/{draws}D/{losses}L, avg diff {avg_diff:+.1f}, "
            f"elo_delta {entry['elo_delta']:+.1f} → elo_estimate {entry['elo_estimate']:+.1f}, "
            f"wallclock {elapsed:.1f}s"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
