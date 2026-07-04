#!/usr/bin/env python3
"""Phone-budget bench — clean SINGLE-THREAD ms/move for HeuristicMCTS on the
v2.9 Bmild_cap8 leaf (Cython flat-leaf path) at sims = 800/1600/3200/6400.

Question this settles: what search depth could a phone afford? Phones are
~2-4x slower than a desktop core, so we bench desktop single-thread ms/move
and derive the phone columns (2x / 4x) in the write-up.

Design:
  - Single process, single OS thread (OMP/MKL=1, CUDA masked). Pure CPU
    classical search — no net, no orchestrator, no multiprocessing.
  - Leaf = v2.9 Bmild_cap8: the canonical env set from
    scripts/canonical_az/solver_score.py (cap 8 / opp-cap 8 / drop3open 0 /
    meeple_k 2.0 / V29 curve -8,-4,-1,0,2,3,4,5), routed through
    flat_leaf -> flat_leaf_cy (CARCASSONNE_USE_FLAT_LEAF=1, USE_CY_LEAF=1).
  - HeuristicMCTS(heur_leaf="v2_7") vs itself, c=3.0 (the production UCT c),
    fresh tree per move (mcts.clear(), same as eval_heur_vs_heur.py).
    NOTE: with the canonical env above, "v2_7" selects DEFAULT_CONFIG which
    IS the v2.9 Bmild_cap8 leaf — the heur_leaf flag names the code path,
    the env names the config.
  - EVERY move is timed (time only best_action, i.e. the search); medians
    over full games so late-game cost variation is in the sample.
  - Cython provenance is HARD-ASSERTED before playing (a silent python-leaf
    fallback would inflate everything ~30x): after one leaf call,
    flat_leaf._CY_FLAT_V2 must be bound and — because our config sets a v29
    curve — flat_leaf._CY_SUPPORTS_CURVE must be True (a stale .so without
    curve support silently falls back to pure python). Per-game we also
    assert mcts.counters ran v2_7-only (the R1 guard pattern).
  - ETA guards: per-game wallclock budget (--game-budget-s, default 2400s)
    truncates a game that runs past it (truncated games still contribute
    per-move samples, flagged); per-level budget (--level-budget-s) stops
    starting NEW games at a level once exceeded (>=1 game always played).
  - Results JSON is rewritten atomically after every game -> harvestable live.

Usage (laptop, detached, pinned to one P-core):
  taskset -c 4 .venv/bin/python -u scripts/bench_phone_budget.py \
      --out /mnt/carc-shared/phone_budget/raw_laptop.json

MEASUREMENT ONLY — no champion/PRODUCTION change.
"""
from __future__ import annotations

import os

# v2.9 Bmild_cap8 leaf env — MUST precede the carcassonne_ai imports
# (DEFAULT_CONFIG reads these at import). Matches scripts/canonical_az/
# solver_score.py, plus the Cython flags (CY_LEAF default-on since 2026-06-17;
# set explicitly so the provenance block records intent).
_CANON_ENV = {
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
}
for _k, _v in _CANON_ENV.items():
    os.environ.setdefault(_k, _v)

import argparse
import dataclasses
import json
import platform
import random
import socket
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.mcts import HeuristicMCTS  # noqa: E402

DEFAULT_SIMS_LEVELS = "800,1600,3200,6400"
DEFAULT_GAMES = "4,4,3,3"
DEFAULT_C_PUCT = 3.0


# ---------------------------------------------------------------------------
# Provenance — assert the Cython flat leaf is ACTUALLY the leaf that runs.
# ---------------------------------------------------------------------------

def verify_cython_active() -> dict:
    """Fire one leaf call through the production dispatch, then assert the
    Cython path bound. Exits nonzero if the python fallback would run."""
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2

    g = Game()
    random.seed(0)
    board = g.get_init_board()
    _ = virtual_score_v2(board.state, 0, None)  # fires the lazy cy bind

    curve = DEFAULT_CONFIG.v29_meeple_curve
    cy_bound = bool(flat_leaf._CY_FLAT_V2)
    supports_curve = bool(flat_leaf._CY_SUPPORTS_CURVE)
    active = (
        flat_leaf.USE_FLAT_LEAF
        and flat_leaf.USE_CY_LEAF
        and cy_bound
        and (curve is None or supports_curve)
    )
    info = {
        "use_flat_leaf": bool(flat_leaf.USE_FLAT_LEAF),
        "use_cy_leaf": bool(flat_leaf.USE_CY_LEAF),
        "cy_module_bound": cy_bound,
        "cy_supports_v29_curve": supports_curve,
        "v29_curve": list(curve) if curve is not None else None,
        "cython_leaf_active": bool(active),
        "leaf_config": dataclasses.asdict(DEFAULT_CONFIG),
    }
    if not active:
        print(json.dumps(info, indent=2, default=str))
        raise SystemExit(
            "FATAL: Cython flat-leaf NOT active (python fallback would run, "
            "~30x slower — numbers would be garbage). Check the .so build / "
            "SUPPORTS_V29_CURVE."
        )
    return info


# ---------------------------------------------------------------------------
# Micro context benches — single leaf eval + 7M-net CPU forward (batch 1).
# ---------------------------------------------------------------------------

def _midgame_board(n_moves: int = 40):
    g = Game()
    random.seed(123)
    board = g.get_init_board()
    for _ in range(n_moves):
        if g.get_game_ended(board, 0) != 0.0:
            break
        legal = np.flatnonzero(g.get_valid_moves(board))
        board, _ = g.get_next_state(board, int(random.choice(legal)))
    return g, board


def bench_leaf(n: int = 20) -> dict:
    """Time n single leaf evals on a midgame state (after warmup)."""
    from carcassonne_ai.virtual_score_v2 import virtual_score_v2

    _, board = _midgame_board()
    for _ in range(50):  # warmup
        virtual_score_v2(board.state, 0, None)
    times_us = []
    for _ in range(n):
        t0 = time.perf_counter_ns()
        virtual_score_v2(board.state, 0, None)
        times_us.append((time.perf_counter_ns() - t0) / 1e3)
    times_us.sort()
    return {
        "n": n,
        "median_us": times_us[len(times_us) // 2],
        "min_us": times_us[0],
        "max_us": times_us[-1],
    }


def bench_net_forward() -> dict:
    """One 7M-net CPU forward (batch 1), torch single-thread. Skipped on error."""
    try:
        import torch

        torch.set_num_threads(1)
        from carcassonne_ai.board_repr import N_CHANNELS
        from carcassonne_ai.features import N_SCALAR_FEATURES
        from carcassonne_ai.network import CarcassonneNet

        net = CarcassonneNet().eval()
        n_params = sum(p.numel() for p in net.parameters())
        board = torch.randn(1, N_CHANNELS, 25, 25)
        scalars = torch.randn(1, N_SCALAR_FEATURES)
        times_ms = []
        with torch.no_grad():
            for _ in range(5):  # warmup
                net(board, scalars)
            for _ in range(20):
                t0 = time.perf_counter()
                net(board, scalars)
                times_ms.append((time.perf_counter() - t0) * 1e3)
        times_ms.sort()
        return {
            "n_params": int(n_params),
            "n": len(times_ms),
            "median_ms": times_ms[len(times_ms) // 2],
            "min_ms": times_ms[0],
            "max_ms": times_ms[-1],
            "torch_threads": 1,
        }
    except Exception as e:  # torch missing / arch mismatch -> context is optional
        return {"skipped": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------------------
# The game bench.
# ---------------------------------------------------------------------------

def play_timed_game(
    seed: int,
    sims: int,
    c: float,
    game_budget_s: float,
    move_cap: int | None,
) -> dict:
    """One HeuristicMCTS-vs-itself game (both sides the v2.9 leaf), timing
    every best_action() call. Fresh tree per move. Returns per-move ms."""
    random.seed(seed)
    game_a = Game(enable_legal_moves_cache=True)
    game_b = Game(enable_legal_moves_cache=True)
    a = HeuristicMCTS(game=game_a, simulations=sims, c=c, seed=seed, heur_leaf="v2_7")
    b = HeuristicMCTS(game=game_b, simulations=sims, c=c, seed=seed + 1, heur_leaf="v2_7")
    board = game_a.get_init_board()

    move_ms: list[float] = []
    truncated = False
    t_game0 = time.perf_counter()
    while game_a.get_game_ended(board, 0) == 0.0:
        mcts = a if board.state.current_player == 0 else b
        mcts.clear()
        t0 = time.perf_counter()
        action = mcts.best_action(board)
        move_ms.append((time.perf_counter() - t0) * 1e3)
        board, _ = game_a.get_next_state(board, action)
        elapsed = time.perf_counter() - t_game0
        if (move_cap and len(move_ms) >= move_cap) or elapsed > game_budget_s:
            if game_a.get_game_ended(board, 0) == 0.0:
                truncated = True
            break
    wall_s = time.perf_counter() - t_game0

    # R1-style provenance: both sides must have run the v2_7 code path only.
    for side, m in (("A", a), ("B", b)):
        cnt = m.counters
        if cnt["v1_calls"] != 0 or cnt["v2_7_calls"] <= 0:
            raise SystemExit(f"FATAL: side {side} leaf provenance bad: {cnt}")

    s0, s1 = board.state.scores
    return {
        "seed": seed,
        "sims": sims,
        "moves": len(move_ms),
        "truncated": truncated,
        "wall_s": wall_s,
        "score_p0": int(s0),
        "score_p1": int(s1),
        "leaf_calls": a.counters["v2_7_calls"] + b.counters["v2_7_calls"],
        "move_ms": [round(x, 3) for x in move_ms],
    }


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return float("nan")
    idx = q * (len(sorted_vals) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def summarize_level(games: list[dict]) -> dict:
    pooled = sorted(t for g in games for t in g["move_ms"])
    full = [g for g in games if not g["truncated"]]
    return {
        "n_games": len(games),
        "n_full_games": len(full),
        "n_moves": len(pooled),
        "median_ms": round(_percentile(pooled, 0.5), 1),
        "p90_ms": round(_percentile(pooled, 0.9), 1),
        "mean_ms": round(sum(pooled) / len(pooled), 1) if pooled else float("nan"),
        "max_ms": round(pooled[-1], 1) if pooled else float("nan"),
        "mean_full_game_wall_s": (
            round(sum(g["wall_s"] for g in full) / len(full), 1) if full else None
        ),
        "mean_moves_per_full_game": (
            round(sum(g["moves"] for g in full) / len(full), 1) if full else None
        ),
        "truncated_games": len(games) - len(full),
    }


def _atomic_dump(payload: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".partial.json")
    tmp.write_text(json.dumps(payload, indent=2, default=str))
    tmp.replace(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sims", default=DEFAULT_SIMS_LEVELS,
                    help="comma-separated sims levels")
    ap.add_argument("--games", default=DEFAULT_GAMES,
                    help="comma-separated games per level (matched to --sims)")
    ap.add_argument("--c", type=float, default=DEFAULT_C_PUCT)
    ap.add_argument("--seed-start", type=int, default=7_770_000)
    ap.add_argument("--game-budget-s", type=float, default=2400.0,
                    help="truncate a single game past this wallclock (ETA guard)")
    ap.add_argument("--level-budget-s", type=float, default=5400.0,
                    help="stop starting new games at a level past this (>=1 always)")
    ap.add_argument("--move-cap", type=int, default=0,
                    help="hard per-game move cap (0 = none)")
    ap.add_argument("--out", default=str(
        Path(__file__).resolve().parent.parent / "measurement" / "phone_budget" / "raw.json"))
    args = ap.parse_args()

    sims_levels = [int(x) for x in args.sims.split(",")]
    games_per = [int(x) for x in args.games.split(",")]
    if len(games_per) != len(sims_levels):
        raise SystemExit("--games must match --sims in length")
    out = Path(args.out)

    print(f"[phone-budget] host={socket.gethostname()} cpu={platform.processor() or platform.machine()}")
    prov = verify_cython_active()
    print(f"[phone-budget] cython leaf ACTIVE: {json.dumps({k: v for k, v in prov.items() if k != 'leaf_config'}, default=str)}")

    leaf_micro = bench_leaf()
    print(f"[phone-budget] leaf micro (20 evals, midgame): median {leaf_micro['median_us']:.1f} us")
    net_micro = bench_net_forward()
    print(f"[phone-budget] net fwd micro: {json.dumps(net_micro)}")

    payload: dict = {
        "kind": "phone_budget_bench",
        "host": socket.gethostname(),
        "cpu": platform.processor() or platform.machine(),
        "python": sys.version.split()[0],
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "argv": sys.argv[1:],
        "env": {k: os.environ.get(k) for k in _CANON_ENV},
        "c_puct": args.c,
        "opponent": "HeuristicMCTS(v2_7 code path, v2.9 Bmild_cap8 env config) self-mirror",
        "provenance": prov,
        "leaf_micro": leaf_micro,
        "net_forward_micro": net_micro,
        "levels": {},
        "games": [],
    }

    for sims, n_games in zip(sims_levels, games_per):
        level_t0 = time.perf_counter()
        level_games: list[dict] = []
        for i in range(n_games):
            if i > 0 and (time.perf_counter() - level_t0) > args.level_budget_s:
                print(f"[phone-budget] sims={sims}: level budget hit after {i} games — moving on")
                break
            g = play_timed_game(
                seed=args.seed_start + sims * 100 + i,
                sims=sims,
                c=args.c,
                game_budget_s=args.game_budget_s,
                move_cap=args.move_cap or None,
            )
            level_games.append(g)
            payload["games"].append(g)
            payload["levels"][str(sims)] = summarize_level(level_games)
            _atomic_dump(payload, out)
            ms = sorted(g["move_ms"])
            print(
                f"[phone-budget] sims={sims} game {i + 1}/{n_games}: "
                f"{g['moves']} moves, wall {g['wall_s']:.1f}s, "
                f"median {_percentile(ms, 0.5):.0f} ms/move, p90 {_percentile(ms, 0.9):.0f}"
                f"{' [TRUNCATED]' if g['truncated'] else ''}",
                flush=True,
            )

    payload["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _atomic_dump(payload, out)

    print("\nsims | median ms/move | p90 ms/move | mean full-game wall")
    for sims in sims_levels:
        s = payload["levels"].get(str(sims))
        if s:
            print(f"{sims:5d} | {s['median_ms']:>10.1f} | {s['p90_ms']:>10.1f} | "
                  f"{s['mean_full_game_wall_s']}s over {s['n_full_games']} full games")
    print(f"[phone-budget] DONE -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
