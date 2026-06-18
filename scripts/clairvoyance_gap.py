"""Clairvoyance-gap experiment (measurement gate, NOT a promotion run).

Measures how much of iter8's reported strength comes from SEEING the true future
deck order. Two arms, both anchored against the SAME fixed reference
HeuristicMCTS @ heur_sims (v2.7 leaf):

  - CLAIR  arm: production clairvoyant iter8 (fair_chance=False, K=1) vs heur.
  - NONCLAIR arm: root-determinization iter8 (fair_chance=True, K determinizations
    per move, vote by SUMMED root visit counts) vs the same heur.

Both arms play the SAME fresh deck band, seat-balanced (each deck both colors), so
the paired Δ(nonclair − clair) per (seed,color) cell isolates clairvoyance alone.

ISOLATION NOTE: both arms choose the root action by argmax of summed visit counts
(AlphaZero τ→0 rule). This deliberately holds the aggregation rule FIXED across
arms so Δ measures clairvoyance, not a best_action(Q+N)-vs-visit-vote difference.
The clair arm's absolute vs-heur elo should land near the published best_action
number (cross-check) since visit-argmax ≈ Q+N best_action at 200 sims.

NON-CLAIRVOYANCE CONTRACT (guardrail #2): the wrapper NEVER reads the true future
order. Each determinization deep-copies the root and shuffles ONLY the unseen
`state.deck` (multiset preserved, `next_tile` kept) — the real game board is
advanced by the master Game using the TRUE held-out deck, untouched by the agent.

Per-game JSON checkpoint (resumable), multiprocessing pool, optional --shared-claim
work-stealing across boxes. Deck hashes + manifest recorded.

Usage (one box; fan across boxes with the SAME --seed-start/--n + --shared-claim):

  CARCASSONNE_V25_CAP=12 CARCASSONNE_V25_DROP_THREE_OPEN=1 \
  CARCASSONNE_V25_VALUE_BLEND=0 CARCASSONNE_USE_FLAT_LEAF=1 \
  python -u scripts/clairvoyance_gap.py --mode nonclair --K 12 \
    --checkpoint /mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt \
    --residual-scale 0.25 --sims 200 --heur-sims 800 --heur-leaf v2_7 \
    --c-puct 3.0 --n 200 --seed-start 2700000000 --paired --workers 12 \
    --out-root /mnt/c/carc-shared/clairvoyance_gap --shared-claim
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import socket
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
import multiprocessing as mp
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import torch

from carcassonne_ai.claim import try_claim as _try_claim
from carcassonne_ai import eval_provenance as ep
from carcassonne_ai.eval_provenance import deck_hash
from carcassonne_ai.evaluators import make_single_evaluator, make_v25_value_wrapper
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import HeuristicMCTS, NeuralMCTS
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.run_manifest import game_tag, write_manifest
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

# ---- worker globals ----
_W = {}


@dataclass
class GameResult:
    seed: int
    net_player: int
    mode: str
    K: int
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
    deck_hash: str = ""


def _result_path(out: Path, seed: int, net_player: int) -> Path:
    return out / f"seed{seed:010d}_p{net_player}.json"


def _try_load(p: Path):
    if p.exists():
        try:
            return GameResult(**json.load(open(p)))
        except Exception:
            p.unlink(missing_ok=True)
    return None


def _save(p: Path, r: GameResult):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.stem}.{socket.gethostname()}.{os.getpid()}.partial.json")
    json.dump(asdict(r), open(tmp, "w"))
    tmp.replace(p)


def _worker_init(checkpoint, mode, K, residual_scale, heur_leaf,
                 shared_claim, claim_host, claim_stale_secs):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(checkpoint, map_location=device, weights_only=False)
    ns = int(ck.get("n_scalar_features", 10))
    net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                         n_scalar_features=ns,
                         value_global_pool=bool(ck.get("value_global_pool", False))
                         ).to(device)
    net.load_state_dict(ck["model_state"])
    net.train(False)
    _W.update(net=net, device=device, include_farm=ns > 10, mode=mode, K=int(K),
              residual_scale=residual_scale, heur_leaf=heur_leaf,
              shared_claim=shared_claim, claim_host=claim_host,
              claim_stale_secs=claim_stale_secs)


def _build_net_mcts(game, seed, sims, c_puct, fair_chance):
    base = make_single_evaluator(_W["net"], _W["device"], game)
    rs = _W["residual_scale"]
    if rs is None:
        leaf = make_v25_value_wrapper(base)
    else:
        cfg = dataclasses.replace(DEFAULT_CONFIG, residual_scale=float(rs))
        leaf = make_v25_value_wrapper(base, cfg)
    return NeuralMCTS(game=game, evaluator=leaf, simulations=sims, seed=seed,
                      c_puct=c_puct, fair_chance=fair_chance)


def _choose_action(net_mcts, board, mode, K):
    """PRODUCTION best_action selection for BOTH arms (Q + visit tiebreak), so the
    clair arm reproduces the published clairvoyant number (+72 at this config) and
    the paired Δ isolates clairvoyance, NOT an aggregation-rule change.

    clair (K=1, fair_chance=False): production best_action on the TRUE deck order.
    nonclair (K>=1, fair_chance=True): K independent searches, each on a fresh
    in-agent root determinization (clear() resets the tree but NOT the rng -> K
    distinct worlds, same public root_key since deck ORDER isn't in the key). Pool
    the child stats across the K trees -- summed visits N_a and summed signed value
    W_a (from the root player's POV) -- then pick by (pooled Q = W_a/N_a, N_a), the
    best_action rule generalized to the determinization ensemble (standard PIMC
    statistic-pooling)."""
    if mode == "clair":
        net_mcts.clear()
        return net_mcts.best_action(board)
    key = net_mcts.game.string_representation(board)
    aggN = defaultdict(float)
    aggW = defaultdict(float)
    for _ in range(K):
        net_mcts.clear()
        net_mcts.search(board)   # fair_chance=True reshuffles the root internally
        root = net_mcts._nodes[key]
        for a, child in net_mcts._deduped_children(root):
            if child.N <= 0:
                continue
            sw = child.W if child.player_to_move == root.player_to_move else -child.W
            aggN[a] += child.N
            aggW[a] += sw
    if not aggN:
        return int(np.flatnonzero(net_mcts.game.get_valid_moves(board))[0])
    return max(aggN, key=lambda a: (aggW[a] / aggN[a], aggN[a]))


def _play_one(args) -> GameResult | None:
    out_str, seed, net_player, sims, heur_sims, c_puct = args
    out = Path(out_str)
    p = _result_path(out, seed, net_player)
    cached = _try_load(p)
    if cached is not None:
        return cached
    if _W["shared_claim"]:
        if not _try_claim(p.with_suffix(".claim"), _W["claim_host"], _W["claim_stale_secs"]):
            return None

    import random
    random.seed(seed)
    mode, K = _W["mode"], _W["K"]
    fair = (mode == "nonclair")

    game = Game(enable_legal_moves_cache=True, include_farm_scalars=_W["include_farm"])
    board = game.get_init_board()
    dh = deck_hash(board)  # deck identity BEFORE any draw

    net_mcts = _build_net_mcts(game, seed, sims, c_puct, fair_chance=fair)
    heur_game = Game(enable_legal_moves_cache=True)
    heur_mcts = HeuristicMCTS(game=heur_game, simulations=heur_sims, seed=seed + 1,
                              heur_leaf=_W["heur_leaf"])

    t0 = time.perf_counter()
    moves = 0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        if cur == net_player:
            action = _choose_action(net_mcts, board, mode, K)
        else:
            heur_mcts.clear()
            action = heur_mcts.best_action(board)
        board, _ = game.get_next_state(board, int(action))
        moves += 1
    elapsed = time.perf_counter() - t0

    s0, s1 = int(board.state.scores[0]), int(board.state.scores[1])
    diff = (s0 - s1) if net_player == 0 else (s1 - s0)
    r = GameResult(seed=seed, net_player=net_player, mode=mode, K=K, sims=sims,
                   heur_sims=heur_sims, c_puct=c_puct, score_p0=s0, score_p1=s1,
                   diff=int(diff), won_by_net=(diff > 0), drew=(diff == 0),
                   elapsed_s=elapsed, moves=moves, deck_hash=dh)
    _save(p, r)
    return r


def _elo(wr):
    wr = min(max(wr, 1e-6), 1 - 1e-6)
    return 400.0 * math.log10(wr / (1 - wr))


def _summary(results, mode, K, heur_sims):
    n = len(results)
    if not n:
        print("no results")
        return
    w = sum(1 for r in results if r.won_by_net)
    d = sum(1 for r in results if r.drew)
    losses = n - w - d
    wr = (w + 0.5 * d) / n
    sig = math.sqrt(wr * (1 - wr) / n) if 0 < wr < 1 else float("nan")
    elo = _elo(wr)
    elo_sig = (400.0 / math.log(10)) * sig / (wr * (1 - wr)) if 0 < wr < 1 else float("nan")
    avg_diff = sum(r.diff for r in results) / n
    print(f"\n=== {mode.upper()} (K={K}) iter8 vs HeuristicMCTS(s={heur_sims}) ===")
    print(f"games: {n}   net {w}W / {d}D / {losses}L   winrate {wr:.4f}")
    print(f"avg score diff (net - heur): {avg_diff:+.2f}")
    print(f"ELO(net vs heur): {elo:+.1f}  (±{elo_sig:.1f} 1σ)")


def _build_work(seed_start, n, paired):
    if not paired:
        return [(seed_start + i, i % 2) for i in range(n)]
    work = []
    for i in range(n // 2):
        work.append((seed_start + i, 0))
        work.append((seed_start + i, 1))
    return work


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="clairvoyance_gap")
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--mode", choices=["clair", "nonclair"], required=True)
    ap.add_argument("--K", type=int, default=12, help="determinizations per move (nonclair)")
    ap.add_argument("--residual-scale", type=float, default=None)
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--heur-sims", type=int, default=800)
    ap.add_argument("--heur-leaf", choices=["v1", "v2_7"], default="v2_7")
    ap.add_argument("--c-puct", type=float, default=3.0)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed-start", type=int, default=2_700_000_000)
    ap.add_argument("--paired", action="store_true")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--out-root", type=str, required=True)
    ap.add_argument("--out-subdir", type=str, default=None)
    ap.add_argument("--shared-claim", action="store_true")
    ap.add_argument("--claim-stale-secs", type=int, default=7200)
    ap.add_argument("--claim-host", type=str, default=socket.gethostname())
    ap.add_argument("--allow-selfplay-seeds", action="store_true")
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args(argv)
    if args.paired and args.n % 2:
        ap.error("--paired requires even --n")
    if args.mode == "clair":
        args.K = 1

    if not args.summary_only and not args.allow_selfplay_seeds:
        ep.assert_clean_eval_seed_range(args.seed_start, args.n)

    sub = args.out_subdir or (f"{args.checkpoint.stem}_{args.mode}_K{args.K}"
                              f"_s{args.sims}_h{args.heur_sims}_c{str(args.c_puct).replace('.', '')}")
    out = Path(args.out_root) / sub
    out.mkdir(parents=True, exist_ok=True)

    tasks = [(str(out), s, pl, args.sims, args.heur_sims, args.c_puct)
             for s, pl in _build_work(args.seed_start, args.n, args.paired)]

    if args.summary_only:
        res = [r for t in tasks if (r := _try_load(_result_path(out, t[1], t[2]))) is not None]
        _summary(res, args.mode, args.K, args.heur_sims)
        return 0

    # manifest (provenance + wrapper config)
    seed_range = [args.seed_start, args.seed_start + (args.n // 2 if args.paired else args.n)]
    write_manifest(out, kind="clairvoyance_gap", game=game_tag(Game()),
                   config={"checkpoint": str(args.checkpoint), "mode": args.mode,
                           "K": args.K, "n": args.n, "sims": args.sims,
                           "heur_sims": args.heur_sims, "heur_leaf": args.heur_leaf,
                           "c_puct": args.c_puct, "residual_scale": args.residual_scale,
                           "paired": args.paired, "seed_start": args.seed_start,
                           "seed_range": seed_range, "opponent": "HeuristicMCTS",
                           "aggregation": "summed-visit-argmax (both arms)",
                           "wrapper": "root-determinization (fair_chance) per move; "
                                      "true deck never read by the agent"},
                   overwrite=True)

    todo = [t for t in tasks if not _result_path(out, t[1], t[2]).exists()]
    workers = args.workers or min(os.cpu_count() or 1, len(todo) or 1)
    print(f"clairvoyance_gap: mode={args.mode} K={args.K} ckpt={args.checkpoint.name} "
          f"n={args.n} sims={args.sims} heur_sims={args.heur_sims} | "
          f"{len(tasks)-len(todo)} cached, {len(todo)} to play, {workers} workers, out={out}",
          flush=True)

    results = []
    if todo:
        t0 = time.perf_counter()
        with Pool(processes=workers, initializer=_worker_init,
                  initargs=(str(args.checkpoint), args.mode, args.K, args.residual_scale,
                            args.heur_leaf, args.shared_claim, args.claim_host,
                            args.claim_stale_secs)) as pool:
            done = 0
            for r in pool.imap_unordered(_play_one, todo, chunksize=1):
                if r is None:
                    continue
                results.append(r)
                done += 1
                if done % 5 == 0 or done == len(todo):
                    el = time.perf_counter() - t0
                    print(f"  {done}/{len(todo)} played ({el/done:.1f}s/game, "
                          f"~{(len(todo)-done)*el/done/60:.0f} min left)", flush=True)
    for t in tasks:
        pth = _result_path(out, t[1], t[2])
        if pth.exists() and not any(r.seed == t[1] and r.net_player == t[2] for r in results):
            c = _try_load(pth)
            if c:
                results.append(c)
    _summary(results, args.mode, args.K, args.heur_sims)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
