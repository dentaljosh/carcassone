"""Measurement ladder (#1): the learned net vs a STRONG non-saturated reference.

The project's measurement wall: Tier-1 (1-ply heuristic) is saturated, and
self-anchored elo (iter_N vs warm/prev) can climb while absolute strength
regresses. We need an opponent that is (a) strong, (b) NOT saturated, (c) gives
an absolute-ish read. **HeuristicMCTS** = the v2.7 leaf + UCT search (mcts.py) —
the same leaf our bot uses, but with NO learned policy. So:

    NeuralMCTS(net priors + v2.7 leaf value)  vs  HeuristicMCTS(v2.7 leaf)
    at MATCHED sims.

This isolates exactly ONE thing: does the LEARNED POLICY add strength over pure
heuristic search at equal compute? If yes, the net is doing real work raw search
can't. This is the yardstick we'll trust going forward (and the first rung of the
'beat loser runs -> beat Joshua -> beat pros' ladder).

IMPORTANT: the neural side uses the PRODUCTION play config — net priors + v2.7
leaf value (make_v25_value_wrapper) — NOT the raw net value head (which Step 9
showed is a bad search leaf). We are measuring the policy, with the leaf both
sides share.

Per-game JSON checkpoint (resumable), multiprocessing pool. Mirror
play_mcts_vs_random / eval_neural_mcts_vs_vanilla conventions.

Usage:
  python -u scripts/eval_net_vs_heuristic.py --checkpoint <ckpt> \
      --n 100 --sims 200 --c-puct 3.0 --workers 14
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from dataclasses import asdict, dataclass
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import torch

from carcassonne_ai.claim import try_claim as _try_claim
from carcassonne_ai.evaluators import make_single_evaluator, make_v25_value_wrapper
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import HeuristicMCTS, NeuralMCTS
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.run_manifest import game_tag, write_manifest
from carcassonne_ai.selfplay import _bench_tick  # gated moves/s instrumentation (CARC_BENCH_TP)

REPO = Path(__file__).resolve().parent.parent
EVAL_ROOT = REPO / "data" / "ladder"

_worker_net = None
_worker_device = None
_worker_include_farm = False
# Work-stealing claim (only used with --shared-claim). Mirrors eval_iter_head_to_head.
_worker_shared_claim: bool = False
_worker_claim_host: str = ""
_worker_claim_stale_secs: int = 5400


@dataclass
class GameResult:
    seed: int
    net_player: int
    sims: int
    heur_sims: int
    c_puct: float
    score_p0: int
    score_p1: int
    diff: int          # net - heuristic
    won_by_net: bool
    drew: bool
    elapsed_s: float
    moves: int


def _result_path(out: Path, sims: int, heur_sims: int, c_puct: float,
                 seed: int, net_player: int) -> Path:
    ct = str(c_puct).replace(".", "")
    return out / f"n{sims:04d}_h{heur_sims:04d}_c{ct}_seed{seed:06d}_p{net_player}.json"


def _try_load(p: Path):
    if p.exists():
        try:
            return GameResult(**json.load(open(p)))
        except Exception:
            p.unlink(missing_ok=True)
    return None


def _save(p: Path, r: GameResult):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.stem + ".partial.json")
    json.dump(asdict(r), open(tmp, "w"))
    tmp.replace(p)


def _worker_init(checkpoint: str, shared_claim: bool = False,
                 claim_host: str = "", claim_stale_secs: int = 5400):
    global _worker_net, _worker_device, _worker_include_farm
    global _worker_shared_claim, _worker_claim_host, _worker_claim_stale_secs
    _worker_shared_claim = shared_claim
    _worker_claim_host = claim_host
    _worker_claim_stale_secs = claim_stale_secs
    _worker_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(checkpoint, map_location=_worker_device, weights_only=False)
    ns = int(ck.get("n_scalar_features", 10))
    _worker_include_farm = ns > 10
    net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                         n_scalar_features=ns).to(_worker_device)
    net.load_state_dict(ck["model_state"])
    net.train(False)
    _worker_net = net


def _play_one(args) -> GameResult:
    out_str, seed, net_player, sims, heur_sims, c_puct = args
    out = Path(out_str)
    p = _result_path(out, sims, heur_sims, c_puct, seed, net_player)
    cached = _try_load(p)
    if cached is not None:
        return cached

    # Work-stealing: atomically claim this (seed, net_player) before the
    # expensive game. If another box owns it, skip (return None). The .claim
    # sits next to the eventual .json; the exists-check above is the permanent
    # done-marker. Mirrors eval_iter_head_to_head.
    if _worker_shared_claim:
        claim_path = p.with_suffix(".claim")
        if not _try_claim(claim_path, _worker_claim_host, _worker_claim_stale_secs):
            return None

    import random
    random.seed(seed)

    game = Game(enable_legal_moves_cache=True, include_farm_scalars=_worker_include_farm)
    board = game.get_init_board()

    # Neural side = PRODUCTION play config: net priors + v2.7 leaf value.
    base = make_single_evaluator(_worker_net, _worker_device, game)
    leaf_eval = make_v25_value_wrapper(base)  # priors from net, value from v2.7
    net_mcts = NeuralMCTS(game=game, evaluator=leaf_eval, simulations=sims,
                          seed=seed, c_puct=c_puct)

    # Heuristic side = v2.7 leaf + UCT, NO learned policy. Its own game so its
    # legal-cache doesn't poison the neural side.
    heur_game = Game(enable_legal_moves_cache=True)
    heur_mcts = HeuristicMCTS(game=heur_game, simulations=heur_sims, seed=seed + 1)

    t0 = time.perf_counter()
    moves = 0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        if cur == net_player:
            net_mcts.clear()
            action = net_mcts.best_action(board)
        else:
            heur_mcts.clear()
            action = heur_mcts.best_action(board)
        board, _ = game.get_next_state(board, action)
        moves += 1
        _bench_tick()  # no-op unless CARC_BENCH_TP set

    elapsed = time.perf_counter() - t0
    s0, s1 = board.state.scores
    diff = (s0 - s1) if net_player == 0 else (s1 - s0)
    r = GameResult(
        seed=seed, net_player=net_player, sims=sims, heur_sims=heur_sims,
        c_puct=c_puct, score_p0=int(s0), score_p1=int(s1), diff=int(diff),
        won_by_net=(diff > 0), drew=(diff == 0), elapsed_s=elapsed, moves=moves,
    )
    _save(p, r)
    return r


def _summary(results, sims, heur_sims):
    import math
    n = len(results)
    w = sum(1 for r in results if r.won_by_net)
    d = sum(1 for r in results if r.drew)
    losses = n - w - d
    avg_diff = sum(r.diff for r in results) / n
    wr = (w + 0.5 * d) / n
    # elo + binomial sigma
    score = wr
    if 0 < score < 1:
        elo = 400.0 * math.log10(score / (1 - score))
        wr_sig = math.sqrt(score * (1 - score) / n)
        elo_sig = (400.0 / math.log(10)) * wr_sig / (score * (1 - score))
    else:
        elo = math.copysign(800.0, score - 0.5)
        elo_sig = float("nan")
    print()
    print(f"=== LADDER: NeuralMCTS(net, s={sims}) vs HeuristicMCTS(s={heur_sims}) ===")
    print(f"games:   {n}")
    print(f"net:     {w}W / {d}D / {losses}L   winrate {wr:.3f}")
    print(f"avg score diff (net - heuristic): {avg_diff:+.1f}")
    print(f"ELO (net vs heuristic): {elo:+.1f}  (+/- {elo_sig:.1f} 1sigma)")
    print()
    if wr > 0.55:
        print("READ: net's LEARNED POLICY beats pure heuristic search at matched compute"
              " -> real signal raw search can't replicate.")
    elif wr < 0.45:
        print("READ: net LOSES to pure heuristic search at matched compute"
              " -> the policy is not adding strength over the leaf+search.")
    else:
        print("READ: net ~ heuristic search (within noise) -> policy adds little at this sims/scale.")


def _build_work(seed_start: int, n: int, paired: bool):
    """Yield (seed, net_player) pairs.

    Legacy (unpaired): alternate net_player across n consecutive seeds.
    Paired (G-M2 deck-pairing): play each DECK both colors — same seed with the
    net as p0 AND as p1 — so first-player advantage AND deck-draw variance both
    cancel (~halves variance vs unpaired). n must be even; n/2 distinct decks.
    """
    if not paired:
        return [(seed_start + i, i % 2) for i in range(n)]
    work = []
    for i in range(n // 2):
        seed = seed_start + i
        work.append((seed, 0))
        work.append((seed, 1))
    return work


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="eval_net_vs_heuristic")
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--sims", type=int, default=200, help="NeuralMCTS sims")
    ap.add_argument("--heur-sims", type=int, default=None,
                    help="HeuristicMCTS sims (default = --sims, i.e. matched compute)")
    ap.add_argument("--c-puct", type=float, default=3.0)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--seed-start", type=int, default=600000)
    ap.add_argument("--out-subdir", type=str, default=None,
                    help="subdir under the out-root (default: derived from ckpt name)")
    ap.add_argument("--out-root", type=str, default=None,
                    help="root dir for results (default: REPO/data/ladder). Point at the "
                         "CIFS share + use --shared-claim to work-steal across boxes "
                         "(all boxes pass the SAME --seed-start/--n).")
    ap.add_argument("--paired", action="store_true",
                    help="deck-pairing (G-M2): play each deck both colors so first-player "
                         "advantage + deck variance cancel (~halves variance). n must be even.")
    ap.add_argument("--shared-claim", action="store_true",
                    help="work-stealing across boxes: atomically claim each (seed,player) via "
                         "an O_CREAT|O_EXCL .claim sidecar so idle boxes pull the tail instead "
                         "of sitting idle. All boxes use the SAME --seed-start/--n/--out-root.")
    ap.add_argument("--claim-stale-secs", type=int, default=5400,
                    help="a .claim older than this is re-claimable (default 90 min).")
    ap.add_argument("--claim-host", type=str, default=socket.gethostname(),
                    help="identity written into the claim body (host:pid:ts).")
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args(argv)
    if args.paired and args.n % 2 != 0:
        ap.error("--paired requires an even --n (n/2 decks x 2 colors)")

    heur_sims = args.heur_sims if args.heur_sims is not None else args.sims
    sub = args.out_subdir or f"{args.checkpoint.stem}_s{args.sims}_h{heur_sims}_c{str(args.c_puct).replace('.', '')}"
    root = Path(args.out_root) if args.out_root else EVAL_ROOT
    out = root / sub
    out.mkdir(parents=True, exist_ok=True)

    # self-describing run manifest (provenance: game/code_rev/leaf-env) — D21.
    if not args.summary_only:
        write_manifest(out, kind="eval_net_vs_heuristic", game=game_tag(Game()),
                       config={"checkpoint": str(args.checkpoint), "n": args.n,
                               "sims": args.sims, "heur_sims": heur_sims,
                               "c_puct": args.c_puct, "paired": args.paired,
                               "seed_start": args.seed_start, "opponent": "HeuristicMCTS",
                               "new_var": "v2_7"})

    # color balance via _build_work (paired = each deck both colors)
    tasks = [(str(out), seed, net_player, args.sims, heur_sims, args.c_puct)
             for seed, net_player in _build_work(args.seed_start, args.n, args.paired)]

    if args.summary_only:
        results = [r for t in tasks if (r := _try_load(_result_path(out, args.sims, heur_sims, args.c_puct, t[1], t[2]))) is not None]
        if results:
            _summary(results, args.sims, heur_sims)
        else:
            print("no cached results yet")
        return 0

    todo = [t for t in tasks if not _result_path(out, args.sims, heur_sims, args.c_puct, t[1], t[2]).exists()]
    workers = args.workers or min(os.cpu_count() or 1, len(todo) or 1)
    print(f"net-vs-heuristic: ckpt={args.checkpoint.name} n={args.n} sims={args.sims} "
          f"heur_sims={heur_sims} c={args.c_puct} | {len(tasks)-len(todo)} cached, "
          f"{len(todo)} to play, {workers} workers, out={out}")
    sys.stdout.flush()

    results = []
    if todo:
        t0 = time.perf_counter()
        with Pool(processes=workers, initializer=_worker_init,
                  initargs=(str(args.checkpoint), args.shared_claim,
                            args.claim_host, args.claim_stale_secs)) as pool:
            done = 0
            for r in pool.imap_unordered(_play_one, todo, chunksize=1):
                if r is None:
                    # work-steal skip: another box owns this (seed,player).
                    continue
                results.append(r)
                done += 1
                if done % 10 == 0 or done == len(todo):
                    el = time.perf_counter() - t0
                    print(f"  {done}/{len(todo)} played ({el/done:.1f}s/game, "
                          f"~{(len(todo)-done)*el/done/60:.0f} min left)")
                    sys.stdout.flush()
    # add cached
    for t in tasks:
        p = _result_path(out, args.sims, heur_sims, args.c_puct, t[1], t[2])
        if p.exists() and not any(r.seed == t[1] and r.net_player == t[2] for r in results):
            c = _try_load(p)
            if c:
                results.append(c)

    _summary(results, args.sims, heur_sims)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
