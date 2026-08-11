"""Clairvoyance diagnostic — how much strength is our MCTS getting from SEEING
the future deck?

Our NeuralMCTS does NOT model chance: the engine's deck is pre-shuffled in its
true future order, and every simulation descends along the actual upcoming tiles
(single-determinization / perfect-information search). A fair Carcassonne player
knows the bag CONTENTS but not the ORDER. `NeuralMCTS(fair_chance=True)` re-shuffles
the unseen deck per move (one plausible future, the info a real player has).

This pits the SAME net against itself, one side clairvoyant (fair_chance=False,
the status quo), one side fair (fair_chance=True), at matched sims/c_puct. Colors
alternate by seed parity to cancel first-move advantage. Greedy play (argmax-visit,
no Dirichlet) on both sides.

  - clairvoyant ≫ fair  → future-sight is load-bearing; our strength numbers are
    inflated vs fair play, and the chance model is the real lever.
  - clairvoyant ≈ fair  → future-sight isn't the story; single-determinization is
    fine for strength, and the missing draw-EXPECTATION (for value learning) is the
    angle → motivates exact chance nodes for a different reason.

Usage (fan across boxes with disjoint --seed-start ranges sharing one --out-root):

  CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 \
  python -u scripts/diag_clairvoyance.py \
      --checkpoint /mnt/c/carc-shared/pathb_loop/ckpt/iter_11.pt \
      --n 100 --seed-start 0 --sims 200 --c-puct 3.0 --workers 10 \
      --out-root /mnt/c/carc-shared/clairvoyance

Summary:

  python scripts/diag_clairvoyance.py --checkpoint .../iter_11.pt \
      --sims 200 --c-puct 3.0 --out-root /mnt/c/carc-shared/clairvoyance --summary-only
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import signal
import sys
import time
from pathlib import Path

import numpy as np
import torch

from carcassonne_ai.evaluators import make_single_evaluator, make_v25_value_wrapper
from carcassonne_ai.features import N_SCALAR_FEATURES
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import NeuralMCTS
from carcassonne_ai.network import CarcassonneNet


_worker_net: CarcassonneNet | None = None
_worker_device: torch.device | None = None
_worker_cfg: dict | None = None


def _worker_init(checkpoint_path: str, cfg: dict) -> None:
    global _worker_net, _worker_device, _worker_cfg
    _worker_cfg = cfg
    _worker_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(checkpoint_path, map_location=_worker_device, weights_only=False)
    net = CarcassonneNet(
        n_filters=ckpt["n_filters"],
        n_blocks=ckpt["n_blocks"],
        n_scalar_features=int(ckpt.get("n_scalar_features", N_SCALAR_FEATURES)),
    ).to(_worker_device)
    net.load_state_dict(ckpt["model_state"])
    net.train(False)
    _worker_net = net


def _result_path(out_dir: Path, seed: int) -> Path:
    return out_dir / f"seed_{seed:06d}.json"


def _subdir_name(checkpoint: Path, sims: int, c_puct: float) -> str:
    return f"{checkpoint.stem}_s{sims}_c{str(c_puct).replace('.', '')}"


def _make_agent(cfg: dict, fair: bool, seed: int) -> tuple[Game, NeuralMCTS]:
    """One (Game, NeuralMCTS) pair. Separate Game per agent so their legal-move
    caches don't cross-contaminate; same shared net via the module global."""
    game = Game(
        enable_legal_moves_cache=True,
        include_farm_scalars=cfg.get("include_farm_scalars", False),
    )
    ev = make_v25_value_wrapper(make_single_evaluator(_worker_net, _worker_device, game))
    mcts = NeuralMCTS(
        game=game,
        evaluator=ev,
        simulations=cfg["sims"],
        c_puct=cfg["c_puct"],
        seed=seed,
        dirichlet_alpha=0.0,
        dirichlet_eps=0.0,
        batch_size=1,
        fair_chance=fair,
    )
    return game, mcts


def _play_one_pool(args: tuple[int, str]) -> tuple[int, str, int]:
    seed, out_dir_str = args
    out_dir = Path(out_dir_str)
    path = _result_path(out_dir, seed)
    if path.exists():
        return seed, "cached", 0

    cfg = _worker_cfg
    assert cfg is not None and _worker_net is not None and _worker_device is not None

    # Color assignment: even seed → clairvoyant is player 0; odd → player 1.
    clair_player = seed % 2
    # One game object drives state; each agent has its OWN game/cache/mcts but we
    # step a single shared board (the master). The agents only READ `board` to
    # search + choose; the master `game` applies the chosen action.
    master = Game(
        enable_legal_moves_cache=True,
        include_farm_scalars=cfg.get("include_farm_scalars", False),
    )
    _, clair_mcts = _make_agent(cfg, fair=False, seed=seed)
    _, fair_mcts = _make_agent(cfg, fair=True, seed=seed)
    agents = {clair_player: clair_mcts, 1 - clair_player: fair_mcts}

    max_plies = cfg.get("max_plies", 400)
    board = master.get_init_board()
    ply = 0
    while master.get_game_ended(board, 0) == 0.0 and ply < max_plies:
        cur = int(board.state.current_player)
        mask = master.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break
        mcts = agents[cur]
        mcts.clear()
        mcts.search(board)
        action = mcts.best_action(board)
        if not mask[int(action)]:
            action = int(legal[0])  # defensive
        board, _ = master.get_next_state(board, int(action))
        ply += 1

    if master.get_game_ended(board, 0) == 0.0:
        sys.stderr.write(f"[seed {seed}] no termination (ply={ply}); skipping\n")
        return seed, "failed", 0

    p0, p1 = int(board.state.scores[0]), int(board.state.scores[1])
    clair_score = p0 if clair_player == 0 else p1
    fair_score = p1 if clair_player == 0 else p0
    if clair_score > fair_score:
        clair_result = 1.0
    elif clair_score < fair_score:
        clair_result = 0.0
    else:
        clair_result = 0.5
    rec = {
        "seed": seed,
        "clair_player": clair_player,
        "p0_score": p0,
        "p1_score": p1,
        "clair_score": clair_score,
        "fair_score": fair_score,
        "clair_result": clair_result,         # 1 clairvoyant win, 0 loss, .5 draw
        "clair_margin": clair_score - fair_score,
        "plies": ply,
    }
    tmp = path.with_name(path.stem + ".partial.json")
    with open(tmp, "w") as f:
        json.dump(rec, f)
    tmp.rename(path)
    return seed, "fresh", 1


def _elo(wr: float) -> float:
    wr = min(max(wr, 1e-6), 1 - 1e-6)
    return -400.0 * math.log10(1.0 / wr - 1.0)


def _summarize(out_dir: Path) -> int:
    files = sorted(out_dir.glob("seed_*.json"))
    if not files:
        print(f"No data at {out_dir}")
        return 0
    res, margins = [], []
    n_games = 0
    for f in files:
        try:
            r = json.load(open(f))
        except Exception as e:
            print(f"  load failed: {f.name}: {e}")
            continue
        n_games += 1
        res.append(float(r["clair_result"]))
        margins.append(float(r["clair_margin"]))
    res = np.asarray(res)
    margins = np.asarray(margins)
    n = res.size
    if n == 0:
        print(f"{out_dir}: 0 games")
        return 0
    wins = int((res == 1.0).sum())
    losses = int((res == 0.0).sum())
    draws = int((res == 0.5).sum())
    score = float(res.mean())                      # clairvoyant's match score
    decisive = wins + losses
    wr_dec = wins / decisive if decisive else float("nan")
    # 1 sigma on the match score over n games (Bernoulli-ish, draws=0.5)
    sd = float(res.std(ddof=1)) / math.sqrt(n) if n > 1 else float("nan")

    print("=== clairvoyance diagnostic summary ===")
    print(f"dir: {out_dir}")
    print(f"games: {n}   (clairvoyant {wins}W / {draws}D / {losses}L)")
    print()
    print(f"  clairvoyant match score = {score:.4f}  (±{sd:.4f} 1σ)")
    print(f"  clairvoyant win-rate (decisive) = {wr_dec:.4f}  (n_dec={decisive})")
    print(f"  → elo(clair vs fair) = {_elo(score):+.1f}")
    print(f"  mean score margin (clair − fair) = {margins.mean():+.2f}  "
          f"(median {np.median(margins):+.1f})")
    print()
    # Verdict: is future-sight load-bearing? Use the match score vs 0.5.
    z = (score - 0.5) / sd if sd and not math.isnan(sd) else float("nan")
    print("--- VERDICT ---")
    print(f"  clairvoyant advantage = {score - 0.5:+.4f}  ({z:+.1f}σ from 50%)")
    if not math.isnan(z) and abs(z) < 2.0:
        print("  CLAIRVOYANCE: not significant (≈ even) — future-sight isn't "
              "driving strength; chance matters (if at all) via value-learning, "
              "not search strength.")
    elif score - 0.5 >= 0:
        print("  CLAIRVOYANCE: clairvoyant STRONGER — future-sight is load-bearing; "
              "fair-play strength is lower than our reported numbers. Chance model "
              "is a real lever → justifies exact chance nodes.")
    else:
        print("  CLAIRVOYANCE: fair STRONGER (!) — single-determinization on the "
              "true deck is HURTING (strategy fusion / committing to one line). "
              "Investigate before trusting current search.")
    return 0


def main(argv: list[str] | None = None) -> int:
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGHUP, lambda *_: sys.exit(0))

    p = argparse.ArgumentParser(prog="diag_clairvoyance")
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--n", type=int, default=0)
    p.add_argument("--seed-start", type=int, default=0)
    p.add_argument("--sims", type=int, default=200)
    p.add_argument("--c-puct", type=float, default=3.0)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--out-root", type=Path, required=True)
    p.add_argument("--summary-only", action="store_true")
    args = p.parse_args(argv)

    sub = _subdir_name(args.checkpoint, args.sims, args.c_puct)
    out_dir = args.out_root / sub

    if args.summary_only:
        return _summarize(out_dir)
    if args.n <= 0:
        p.error("--n must be > 0 in play mode (or pass --summary-only)")
    out_dir.mkdir(parents=True, exist_ok=True)

    _peek = torch.load(str(args.checkpoint), map_location="cpu", weights_only=False)
    learner_ns = int(_peek.get("n_scalar_features", N_SCALAR_FEATURES))
    include_farm_scalars = learner_ns > N_SCALAR_FEATURES
    del _peek

    seeds = list(range(args.seed_start, args.seed_start + args.n))
    pool_args = [(s, str(out_dir)) for s in seeds]
    already = sum(1 for s in seeds if _result_path(out_dir, s).exists())
    remaining = args.n - already
    n_workers = min(args.workers, remaining or 1)

    cfg = {
        "sims": args.sims,
        "c_puct": args.c_puct,
        "include_farm_scalars": include_farm_scalars,
    }
    print(f"diag_clairvoyance: {args.n} games (sims={args.sims}, c={args.c_puct}), "
          f"{n_workers} workers, {already} cached, {remaining} to play, out={out_dir}")
    sys.stdout.flush()
    if remaining == 0:
        print("All games cached; run --summary-only.")
        return 0

    t0 = time.perf_counter()
    fresh = cached = failed = 0
    first_fresh_t = None
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=n_workers, initializer=_worker_init,
                  initargs=(str(args.checkpoint), cfg)) as pool:
        for done, (seed, status, _) in enumerate(
            pool.imap_unordered(_play_one_pool, pool_args, chunksize=1), 1
        ):
            if status == "fresh":
                fresh += 1
                if first_fresh_t is None:
                    first_fresh_t = time.perf_counter()
                    el = first_fresh_t - t0
                    print(f"  [ETA] first game {el:.0f}s; ~{(remaining*el/n_workers)/60:.1f} "
                          f"min for {remaining} fresh")
                    sys.stdout.flush()
            elif status == "failed":
                failed += 1
            else:
                cached += 1
            if done % max(1, args.n // 10) == 0 or done == args.n:
                print(f"  ... {done}/{args.n} (fresh={fresh}, cached={cached}, failed={failed})")
                sys.stdout.flush()
    print(f"\nDone: {fresh} fresh + {cached} cached + {failed} failed, "
          f"{time.perf_counter()-t0:.1f}s. Run --summary-only to aggregate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
