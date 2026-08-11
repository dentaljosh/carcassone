"""Clean-eval rerun #1: the PURE leaf gap — HeuristicMCTS-v2.7 vs HeuristicMCTS-v1.

R1 (outside-review 2026-06-07) showed the strength yardstick ran the v1 leaf while
the agent ran v2.7; matching the leaf cost ~39 elo on the headline cell. This
harness measures that leaf gap DIRECTLY, with no learned net involved: two pure
HeuristicMCTS players at MATCHED sims, one with the v2.7 leaf (cap/drop-three-open)
and one with the legacy v1 `virtual_score` leaf. The elo of v2.7 over v1 IS the
leaf gap that contaminated every vs-HeuristicMCTS absolute.

Both sides are pure CPU (no GPU / no orchestrator) → CPU-bound, so keep workers
<= threads. Per-game JSON checkpoint (resumable), deck-paired, balanced seats,
clean seed namespace, full provenance manifest. Mirrors eval_net_vs_heuristic.

Usage:
  python -u scripts/eval_heur_vs_heur.py --n 400 --sims 200 --paired \
      --seed-start 1000000000 --workers 12 --out-root /mnt/c/carc-shared/clean_eval
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

from carcassonne_ai.claim import try_claim as _try_claim
from carcassonne_ai import eval_provenance as ep
from carcassonne_ai.eval_provenance import deck_hash
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import HeuristicMCTS
from carcassonne_ai.run_manifest import game_tag, write_manifest

REPO = Path(__file__).resolve().parent.parent
EVAL_ROOT = REPO / "data" / "heur_vs_heur"

# side A = the v2.7 leaf (the agent's leaf); side B = the legacy v1 leaf.
A_LEAF, B_LEAF = "v2_7", "v1"

_worker_shared_claim = False
_worker_claim_host = ""
_worker_claim_stale_secs = 5400


@dataclass
class GameResult:
    seed: int
    a_player: int          # seat the v2.7 side plays (0 or 1)
    sims: int
    score_p0: int
    score_p1: int
    diff: int              # v2.7 - v1
    won_by_a: bool
    drew: bool
    elapsed_s: float
    moves: int
    deck_hash: str = ""


def _result_path(out: Path, sims: int, seed: int, a_player: int) -> Path:
    return out / f"s{sims:04d}_seed{seed:06d}_a{a_player}.json"


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


def _worker_init(shared_claim=False, claim_host="", claim_stale_secs=5400):
    global _worker_shared_claim, _worker_claim_host, _worker_claim_stale_secs
    _worker_shared_claim = shared_claim
    _worker_claim_host = claim_host
    _worker_claim_stale_secs = claim_stale_secs


def _make_sides(seed, sims):
    """Two pure HeuristicMCTS players, separate Games so legal caches don't mix.
    Side A = v2.7 leaf, side B = v1 leaf."""
    game_a = Game(enable_legal_moves_cache=True)
    game_b = Game(enable_legal_moves_cache=True)
    a = HeuristicMCTS(game=game_a, simulations=sims, seed=seed, heur_leaf=A_LEAF)
    b = HeuristicMCTS(game=game_b, simulations=sims, seed=seed + 1, heur_leaf=B_LEAF)
    return game_a, a, b


def _play_one(args) -> GameResult | None:
    out_str, seed, a_player, sims = args
    out = Path(out_str)
    p = _result_path(out, sims, seed, a_player)
    cached = _try_load(p)
    if cached is not None:
        return cached
    if _worker_shared_claim:
        claim_path = p.with_suffix(".claim")
        if not _try_claim(claim_path, _worker_claim_host, _worker_claim_stale_secs):
            return None

    import random
    random.seed(seed)
    game, a_mcts, b_mcts = _make_sides(seed, sims)
    board = game.get_init_board()
    dh = deck_hash(board)

    t0 = time.perf_counter()
    moves = 0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        mcts = a_mcts if cur == a_player else b_mcts
        mcts.clear()
        action = mcts.best_action(board)
        board, _ = game.get_next_state(board, action)
        moves += 1
    elapsed = time.perf_counter() - t0
    s0, s1 = board.state.scores
    diff = (s0 - s1) if a_player == 0 else (s1 - s0)
    r = GameResult(seed=seed, a_player=a_player, sims=sims, score_p0=int(s0), score_p1=int(s1),
                   diff=int(diff), won_by_a=(diff > 0), drew=(diff == 0),
                   elapsed_s=elapsed, moves=moves, deck_hash=dh)
    _save(p, r)
    return r


def _summary(results, sims):
    import math
    n = len(results)
    w = sum(1 for r in results if r.won_by_a)
    d = sum(1 for r in results if r.drew)
    losses = n - w - d
    avg = sum(r.diff for r in results) / n
    wr = (w + 0.5 * d) / n
    if 0 < wr < 1:
        elo = 400.0 * math.log10(wr / (1 - wr))
        elo_sig = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
    else:
        elo, elo_sig = math.copysign(800.0, wr - 0.5), float("nan")
    print()
    print(f"=== LEAF GAP: HeuristicMCTS(v2_7) vs HeuristicMCTS(v1) @ sims={sims} ===")
    print(f"games:  {n}   v2_7: {w}W / {d}D / {losses}L   winrate {wr:.3f}")
    print(f"avg score diff (v2_7 - v1): {avg:+.1f}")
    print(f"ELO (v2_7 vs v1): {elo:+.1f}  (+/- {elo_sig:.1f} 1sigma)")
    if abs(elo) <= 35 and not math.isnan(elo_sig):
        print(f"POWER NOTE: |elo|<=35 at n={n} (1σ≈±{elo_sig:.0f}); deck-paired ±12 needs ~n=700-1500 for a verdict.")


def _build_work(seed_start, n, paired):
    if not paired:
        return [(seed_start + i, i % 2) for i in range(n)]
    work = []
    for i in range(n // 2):
        work.append((seed_start + i, 0))
        work.append((seed_start + i, 1))
    return work


def _provenance_smoke(out, sims, seed_start) -> int:
    """Single-process runtime proof: side A ran v2.7-only, side B ran v1-only."""
    game, a_mcts, b_mcts = _make_sides(seed_start, sims)
    import random
    for a_player in (0, 1):
        random.seed(seed_start)
        board = game.get_init_board()
        while game.get_game_ended(board, 0) == 0.0:
            cur = board.state.current_player
            mcts = a_mcts if cur == a_player else b_mcts
            mcts.clear(); board, _ = game.get_next_state(board, mcts.best_action(board))
    counters = {"A_v2_7": a_mcts.counters, "B_v1": b_mcts.counters}
    aspec = ep.spec_from_heuristic_mcts(a_mcts, side="A_v2_7", sims=sims, paired=True,
                                        seed_range=[seed_start, seed_start + 1],
                                        eval_script="eval_heur_vs_heur.py")
    bspec = ep.spec_from_heuristic_mcts(b_mcts, side="B_v1", sims=sims, paired=True,
                                        seed_range=[seed_start, seed_start + 1],
                                        eval_script="eval_heur_vs_heur.py")
    verdict = ep.assert_provenance_consistent([aspec, bspec], counters)
    print("[provenance-smoke] counters:", json.dumps(counters))
    print("[provenance-smoke] OK — v2_7-only / v1-only verified at runtime")
    block = ep.build_eval_provenance([aspec, bspec], kind="eval_heur_vs_heur",
                                     argv=sys.argv[1:], runtime_verified=verdict)
    mpath = write_manifest(out, kind="eval_heur_vs_heur", game=game_tag(Game()),
                           config={"sims": sims, "seed_start": seed_start,
                                   "a_leaf": A_LEAF, "b_leaf": B_LEAF, "provenance_smoke": True},
                           evaluator=block, overwrite=True)
    print(f"[provenance-smoke] manifest -> {mpath}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="eval_heur_vs_heur")
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--seed-start", type=int, default=ep.EVAL_SEED_FLOOR)
    ap.add_argument("--allow-selfplay-seeds", action="store_true")
    ap.add_argument("--paired", action="store_true")
    ap.add_argument("--provenance-smoke", action="store_true")
    ap.add_argument("--out-root", type=str, default=None)
    ap.add_argument("--out-subdir", type=str, default=None)
    ap.add_argument("--shared-claim", action="store_true")
    ap.add_argument("--claim-stale-secs", type=int, default=5400)
    ap.add_argument("--claim-host", type=str, default=socket.gethostname())
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args(argv)
    if args.paired and args.n % 2 != 0:
        ap.error("--paired requires an even --n")

    seed_range = [args.seed_start, args.seed_start + (args.n // 2 if args.paired else args.n)]
    if not args.summary_only and not args.allow_selfplay_seeds:
        ep.assert_clean_eval_seed_range(args.seed_start, args.n)

    sub = args.out_subdir or f"heur_v2_7_vs_v1_s{args.sims}"
    root = Path(args.out_root) if args.out_root else EVAL_ROOT
    out = root / sub
    out.mkdir(parents=True, exist_ok=True)

    if args.provenance_smoke:
        return _provenance_smoke(out, args.sims, args.seed_start)

    tasks = [(str(out), seed, a_player, args.sims)
             for seed, a_player in _build_work(args.seed_start, args.n, args.paired)]

    if args.summary_only:
        results = [r for t in tasks if (r := _try_load(_result_path(out, args.sims, t[1], t[2]))) is not None]
        if results:
            _summary(results, args.sims)
        else:
            print("no cached results yet")
        return 0

    if not args.summary_only:
        aspec = ep.spec_from_heuristic_mcts(
            HeuristicMCTS(game=Game(enable_legal_moves_cache=True), simulations=args.sims, heur_leaf=A_LEAF),
            side="A_v2_7", sims=args.sims, paired=args.paired, seed_range=seed_range,
            eval_script="eval_heur_vs_heur.py", argv=sys.argv[1:])
        bspec = ep.spec_from_heuristic_mcts(
            HeuristicMCTS(game=Game(enable_legal_moves_cache=True), simulations=args.sims, heur_leaf=B_LEAF),
            side="B_v1", sims=args.sims, paired=args.paired, seed_range=seed_range,
            eval_script="eval_heur_vs_heur.py", argv=sys.argv[1:])
        block = ep.build_eval_provenance([aspec, bspec], kind="eval_heur_vs_heur",
                                         argv=sys.argv[1:], runtime_verified=None)
        write_manifest(out, kind="eval_heur_vs_heur", game=game_tag(Game()),
                       config={"n": args.n, "sims": args.sims, "paired": args.paired,
                               "seed_start": args.seed_start, "a_leaf": A_LEAF, "b_leaf": B_LEAF},
                       evaluator=block)

    todo = [t for t in tasks if not _result_path(out, args.sims, t[1], t[2]).exists()]
    workers = args.workers or min(os.cpu_count() or 1, len(todo) or 1)
    print(f"heur-vs-heur(leaf gap): n={args.n} sims={args.sims} | {len(tasks)-len(todo)} cached, "
          f"{len(todo)} to play, {workers} workers, out={out}")
    sys.stdout.flush()

    results = []
    if todo:
        t0 = time.perf_counter()
        with Pool(processes=workers, initializer=_worker_init,
                  initargs=(args.shared_claim, args.claim_host, args.claim_stale_secs)) as pool:
            done = 0
            for r in pool.imap_unordered(_play_one, todo, chunksize=1):
                if r is None:
                    continue
                results.append(r)
                done += 1
                if done % 10 == 0 or done == len(todo):
                    el = time.perf_counter() - t0
                    print(f"  {done}/{len(todo)} played ({el/done:.1f}s/game, "
                          f"~{(len(todo)-done)*el/done/60:.0f} min left)")
                    sys.stdout.flush()
    for t in tasks:
        p = _result_path(out, args.sims, t[1], t[2])
        if p.exists() and not any(r.seed == t[1] and r.a_player == t[2] for r in results):
            c = _try_load(p)
            if c:
                results.append(c)

    if results:
        _summary(results, args.sims)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
