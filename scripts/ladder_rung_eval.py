"""Level-2 ladder: general paired head-to-head between any two FIXED rungs.

Plays N paired, seat-balanced games of (rung A vs rung B) and reports W/D/L,
elo, paired z, deck hashes + a full provenance manifest. Pure CPU (random /
RuleBasedPlayer / HeuristicMCTS) → no GPU / orchestrator; CPU-bound, keep
workers <= threads. Per-game JSON checkpoint (resumable), --shared-claim
work-stealing across the cluster. Mirrors eval_heur_vs_heur.py.

Rung spec tokens (--rung-a / --rung-b):
    random           uniform random over legal actions (seeded)
    greedy           RuleBasedPlayer — 1-ply virtual_score argmax + rules
    heur_v1@<sims>   HeuristicMCTS(heur_leaf="v1",  simulations=<sims>)
    heur_v2_7@<sims> HeuristicMCTS(heur_leaf="v2_7", simulations=<sims>)

Heuristic rungs honour the production v2.7 leaf env — set
    CARCASSONNE_V25_CAP=12 CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_USE_FLAT_LEAF=1
to match the established ruler exactly (recorded in the manifest).

Usage (one adjacent comparison):
  CARCASSONNE_V25_CAP=12 CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_USE_FLAT_LEAF=1 \
  python -u scripts/ladder_rung_eval.py --rung-a heur_v2_7@800 --rung-b heur_v2_7@200 \
      --n 200 --paired --seed-start 3030000000 --workers 14 \
      --out-root /mnt/c/carc-shared/level2_ladder --shared-claim

  # runtime leaf-provenance proof (1 game), then exit:
  ... --provenance-smoke
"""
from __future__ import annotations

import argparse
import json
import math
import os
import socket
import sys
import time
from dataclasses import asdict, dataclass
from multiprocessing import get_context
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from carcassonne_ai.claim import try_claim as _try_claim
from carcassonne_ai.eval_provenance import deck_hash
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import HeuristicMCTS
from carcassonne_ai.rule_based_player import RuleBasedPlayer
from carcassonne_ai.run_manifest import game_tag, write_manifest

REPO = Path(__file__).resolve().parent.parent
EVAL_ROOT = REPO / "data" / "level2_ladder"

_worker_shared_claim = False
_worker_claim_host = ""
_worker_claim_stale_secs = 5400


# --------------------------------------------------------------------------- #
# Rung agents — uniform interface: .move(game, board, mask) -> int            #
# --------------------------------------------------------------------------- #
class _RandomAgent:
    leaf_name = "none"

    def __init__(self, seed: int):
        import random
        self._rng = random.Random(seed)
        self.counters = {"v1_calls": 0, "v2_7_calls": 0}

    def move(self, game, board, mask) -> int:
        legal = np.flatnonzero(mask)
        return int(self._rng.choice(legal.tolist()))


class _GreedyAgent:
    leaf_name = "v1_1ply"

    def __init__(self, seed: int):
        self._p = RuleBasedPlayer(seed=seed)
        self.counters = {"v1_calls": 0, "v2_7_calls": 0}

    def move(self, game, board, mask) -> int:
        return int(self._p.choose_action(game, board, mask))


class _HeurAgent:
    def __init__(self, game, heur_leaf: str, sims: int, seed: int):
        self._m = HeuristicMCTS(game=game, simulations=sims, seed=seed, heur_leaf=heur_leaf)
        self.leaf_name = heur_leaf

    @property
    def counters(self):
        return self._m.counters

    def move(self, game, board, mask) -> int:
        self._m.clear()
        return int(self._m.best_action(board))


def parse_rung(spec: str):
    """-> (kind, leaf, sims) ; validates the spec token."""
    spec = spec.strip()
    if spec == "random":
        return ("random", "none", 0)
    if spec == "greedy":
        return ("greedy", "v1_1ply", 0)
    for leaf in ("v1", "v2_7"):
        prefix = f"heur_{leaf}@"
        if spec.startswith(prefix):
            sims = int(spec[len(prefix):])
            if sims <= 0:
                raise ValueError(f"bad sims in {spec!r}")
            return ("heur", leaf, sims)
    raise ValueError(
        f"unknown rung spec {spec!r}; expected random|greedy|heur_v1@N|heur_v2_7@N")


def make_agent(spec: str, *, game, seed: int):
    kind, leaf, sims = parse_rung(spec)
    if kind == "random":
        return _RandomAgent(seed)
    if kind == "greedy":
        return _GreedyAgent(seed)
    return _HeurAgent(game, leaf, sims, seed)


# --------------------------------------------------------------------------- #
@dataclass
class GameResult:
    seed: int
    a_seat: int            # seat rung-A plays this game (0 or 1)
    rung_a: str
    rung_b: str
    score_p0: int
    score_p1: int
    diff: int              # A - B  (from A's perspective)
    won_by_a: bool
    drew: bool
    elapsed_s: float
    moves: int
    deck_hash: str = ""


def _result_path(out: Path, seed: int, a_seat: int) -> Path:
    return out / f"seed{seed:010d}_a{a_seat}.json"


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


def _play_one(args) -> GameResult | None:
    out_str, seed, a_seat, rung_a, rung_b = args
    out = Path(out_str)
    p = _result_path(out, seed, a_seat)
    cached = _try_load(p)
    if cached is not None:
        return cached
    if _worker_shared_claim:
        claim_path = p.with_suffix(".claim")
        if not _try_claim(claim_path, _worker_claim_host, _worker_claim_stale_secs):
            return None

    import random
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    # Separate Games per side so legal-move caches never cross.
    game_a = Game(enable_legal_moves_cache=True)
    game_b = Game(enable_legal_moves_cache=True)
    agent_a = make_agent(rung_a, game=game_a, seed=seed)
    agent_b = make_agent(rung_b, game=game_b, seed=seed + 1)
    board = game.get_init_board()
    dh = deck_hash(board)

    t0 = time.perf_counter()
    moves = 0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        mask = game.get_valid_moves(board)
        agent = agent_a if cur == a_seat else agent_b
        action = agent.move(game, board, mask)
        if not mask[action]:
            raise RuntimeError(f"rung returned illegal action {action}")
        board, _ = game.get_next_state(board, action)
        moves += 1
    elapsed = time.perf_counter() - t0
    s0, s1 = board.state.scores
    diff = (s0 - s1) if a_seat == 0 else (s1 - s0)
    r = GameResult(seed=seed, a_seat=a_seat, rung_a=rung_a, rung_b=rung_b,
                   score_p0=int(s0), score_p1=int(s1), diff=int(diff),
                   won_by_a=(diff > 0), drew=(diff == 0), elapsed_s=elapsed,
                   moves=moves, deck_hash=dh)
    _save(p, r)
    return r


def _paired_z(results, rung_a, rung_b):
    """Paired z on per-deck score difference. Pairs games (seed,a_seat=0) with
    (seed,a_seat=1): both A-perspective diffs, so d = diff0 + diff1 averaged is
    A's net seat-balanced margin per deck. z = mean_d / se_d."""
    by_seed = {}
    for r in results:
        by_seed.setdefault(r.seed, {})[r.a_seat] = r.diff
    ds = [(v[0] + v[1]) / 2.0 for v in by_seed.values() if 0 in v and 1 in v]
    if len(ds) < 2:
        return None, None, 0
    mean = sum(ds) / len(ds)
    var = sum((d - mean) ** 2 for d in ds) / (len(ds) - 1)
    se = math.sqrt(var / len(ds))
    z = mean / se if se > 0 else float("nan")
    return mean, z, len(ds)


def _summary(results, rung_a, rung_b):
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
    mean_d, z, npair = _paired_z(results, rung_a, rung_b)
    print()
    print(f"=== LADDER: {rung_a}  vs  {rung_b} ===")
    print(f"games:  {n}   {rung_a}: {w}W / {d}D / {losses}L   winrate {wr:.3f}")
    print(f"avg score diff (A - B): {avg:+.2f}")
    print(f"ELO (A vs B): {elo:+.1f}  (+/- {elo_sig:.1f} 1sigma)")
    if mean_d is not None:
        print(f"PAIRED: {npair} decks   mean seat-balanced margin {mean_d:+.2f}   z = {z:+.2f}")
    return {
        "rung_a": rung_a, "rung_b": rung_b, "n": n, "W": w, "D": d, "L": losses,
        "winrate": wr, "elo": elo, "elo_sig_1sigma": elo_sig,
        "avg_diff": avg, "paired_mean_margin": mean_d, "paired_z": z,
        "n_paired": npair, "n_deck_hashes": len({r.deck_hash for r in results}),
    }


def _build_work(seed_start, n, paired):
    if not paired:
        return [(seed_start + i, i % 2) for i in range(n)]
    work = []
    for i in range(n // 2):
        work.append((seed_start + i, 0))
        work.append((seed_start + i, 1))
    return work


def _provenance_smoke(rung_a, rung_b, seed_start) -> int:
    """Play 1 game in-process; assert each heuristic rung ran its claimed leaf."""
    import random
    random.seed(seed_start)
    game = Game(enable_legal_moves_cache=True)
    ga, gb = Game(enable_legal_moves_cache=True), Game(enable_legal_moves_cache=True)
    a = make_agent(rung_a, game=ga, seed=seed_start)
    b = make_agent(rung_b, game=gb, seed=seed_start + 1)
    board = game.get_init_board()
    t0 = time.perf_counter()
    moves = 0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        mask = game.get_valid_moves(board)
        agent = a if cur == 0 else b
        board, _ = game.get_next_state(board, agent.move(game, board, mask))
        moves += 1
    dt = time.perf_counter() - t0

    def _check(spec, agent, side):
        kind, leaf, sims = parse_rung(spec)
        c = agent.counters
        if kind == "heur" and leaf == "v2_7":
            assert c["v2_7_calls"] > 0 and c["v1_calls"] == 0, (side, spec, c)
        if kind == "heur" and leaf == "v1":
            assert c["v1_calls"] > 0 and c["v2_7_calls"] == 0, (side, spec, c)
        print(f"[provenance-smoke] {side} {spec}: leaf={agent.leaf_name} counters={c}")

    # side A occupies seat 0 in this smoke (cur==0 -> a); but agents alternate
    # by seat each move, so A only moved on its turns — counters still prove leaf.
    _check(rung_a, a, "A")
    _check(rung_b, b, "B")
    print(f"[provenance-smoke] OK — leaf provenance verified ({moves} moves, {dt:.1f}s, "
          f"~{dt/moves*1000:.0f} ms/move pair)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ladder_rung_eval")
    ap.add_argument("--rung-a", required=True, help="random|greedy|heur_v1@N|heur_v2_7@N")
    ap.add_argument("--rung-b", required=True)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--seed-start", type=int, default=3_000_000_000)
    ap.add_argument("--paired", action="store_true")
    ap.add_argument("--provenance-smoke", action="store_true")
    ap.add_argument("--out-root", type=str, default=None)
    ap.add_argument("--out-subdir", type=str, default=None)
    ap.add_argument("--shared-claim", action="store_true")
    ap.add_argument("--claim-stale-secs", type=int, default=5400)
    ap.add_argument("--claim-host", type=str, default=socket.gethostname())
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args(argv)
    parse_rung(args.rung_a); parse_rung(args.rung_b)  # validate early
    if args.paired and args.n % 2 != 0:
        ap.error("--paired requires an even --n")

    if args.provenance_smoke:
        return _provenance_smoke(args.rung_a, args.rung_b, args.seed_start)

    def _san(s):
        return s.replace("@", "").replace("_", "")
    sub = args.out_subdir or f"{_san(args.rung_a)}__vs__{_san(args.rung_b)}"
    root = Path(args.out_root) if args.out_root else EVAL_ROOT
    out = root / sub
    out.mkdir(parents=True, exist_ok=True)

    tasks = [(str(out), seed, a_seat, args.rung_a, args.rung_b)
             for seed, a_seat in _build_work(args.seed_start, args.n, args.paired)]

    if args.summary_only:
        results = [r for t in tasks if (r := _try_load(_result_path(out, t[1], t[2]))) is not None]
        if results:
            summ = _summary(results, args.rung_a, args.rung_b)
            json.dump(summ, open(out / "summary.json", "w"), indent=2)
        else:
            print("no cached results yet")
        return 0

    seed_range = [args.seed_start, args.seed_start + (args.n // 2 if args.paired else args.n)]
    write_manifest(out, kind="ladder_rung_eval", game=game_tag(Game()),
                   config={"rung_a": args.rung_a, "rung_b": args.rung_b, "n": args.n,
                           "paired": args.paired, "seed_start": args.seed_start,
                           "seed_range": seed_range,
                           "v25_env": {k: os.environ.get(k) for k in
                                       ("CARCASSONNE_V25_CAP", "CARCASSONNE_V25_DROP_THREE_OPEN",
                                        "CARCASSONNE_USE_FLAT_LEAF", "CARCASSONNE_V25_VALUE_BLEND")}})

    todo = [t for t in tasks if not _result_path(out, t[1], t[2]).exists()]
    workers = args.workers or min(os.cpu_count() or 1, len(todo) or 1)
    print(f"ladder {args.rung_a} vs {args.rung_b}: n={args.n} | {len(tasks)-len(todo)} cached, "
          f"{len(todo)} to play, {workers} workers, out={out}")
    sys.stdout.flush()

    results = []
    if todo:
        t0 = time.perf_counter()
        ctx = get_context("fork")
        with ctx.Pool(processes=workers, initializer=_worker_init,
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
        p = _result_path(out, t[1], t[2])
        if p.exists() and not any(r.seed == t[1] and r.a_seat == t[2] for r in results):
            c = _try_load(p)
            if c:
                results.append(c)

    if results:
        summ = _summary(results, args.rung_a, args.rung_b)
        json.dump(summ, open(out / "summary.json", "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
