#!/usr/bin/env python3
"""⭐ RUST-MIRROR VERDICT — can `carc_core::endgame` mirror an E4 archive's rules profile?

The program record says the RUST CLAIRVOYANT **JUDGE** cannot mirror E4 rules
profiles. That finding is about the judge. This script asks the separate question
the ply-pricing instrument actually depends on: does the rust **exact solver**
reproduce the Python oracle (`scripts/level2/endgame_solver.py`) bit-for-bit on
REAL E4 endgame states, under each archive's own resolved rules profile?

Method (`scripts/rustport/reconcile_exact_solver.py`'s gate, restricted to E4):

  * seat the Python `Game`/board by lossless `(deck_seed, actions)` replay under
    the profile's `game_kwargs()`;
  * seat the Rust mirror with `MirrorState.from_seed(seed, **mirror_geometry_kwargs(game))`
    and drive it in LOCKSTEP with `.advance(a)`;
  * DESYNC GUARD: `game.string_representation(board) == ms.string_repr()`;
  * solve both sides in every requested mode and compare `value_bits`,
    `optimal_actions`, `child_values` (every action, bit-for-bit) and `nodes`
    (the search SHAPE, not just the answer).

Zero mismatches over zero checks never PASSes (the house exit discipline).
Timings for both sides are recorded — they are the cost model the K cut uses.
"""
from __future__ import annotations

import argparse
import json
import random
import struct
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

SOLVER_FIELDS = ("value_bits", "to_move", "optimal_actions", "child_values", "nodes")
ARCHIVES = REPO / "measurement" / "e4_games"


def ubits(x: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


def py_result_dict(res) -> dict:
    return {
        "value_bits": ubits(res.value),
        "to_move": int(res.to_move),
        "optimal_actions": [int(a) for a in res.optimal_actions],
        "child_values": sorted((int(a), ubits(v)) for a, v in res.child_values.items()),
        "nodes": int(res.nodes),
    }


def rs_result_dict(d) -> dict:
    return {
        "value_bits": int(d["value_bits"]),
        "to_move": int(d["to_move"]),
        "optimal_actions": [int(a) for a in d["optimal_actions"]],
        "child_values": sorted((int(a), int(v)) for a, v in d["child_values"]),
        "nodes": int(d["nodes"]),
    }


def seat(profile_name, deck_seed, actions, ply):
    import carc_rs
    from carcassonne_ai import rules_profile
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.rust_agent import mirror_geometry_kwargs

    prof = rules_profile.resolve(profile_name)
    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    board = game.get_init_board()
    ms = carc_rs.MirrorState.from_seed(str(int(deck_seed)),
                                       **mirror_geometry_kwargs(game))
    for a in actions[:ply]:
        board, _ = game.get_next_state(board, int(a))
        ms.advance(int(a))
    return game, board, ms


class _PySolveTimeout(Exception):
    """The PYTHON oracle blew its wall cap — a SKIP, never a mismatch.

    Same discipline as `reconcile_exact_solver._PySolveTimeout`: the cap applies
    to the PYTHON side only, so a Rust solve that outran its budget while Python
    finished is still reported as a real divergence.
    """


def _timed_py_solve(S, game, board, mode, budget, ab, cap_s: int):
    if cap_s <= 0:
        return S.solve(game, board, mode, budget=budget, alphabeta=ab)
    import signal as _sig

    def _fire(*_):
        raise _PySolveTimeout()

    old = _sig.signal(_sig.SIGALRM, _fire)
    _sig.alarm(int(cap_s))
    try:
        return S.solve(game, board, mode, budget=budget, alphabeta=ab)
    finally:
        _sig.alarm(0)
        _sig.signal(_sig.SIGALRM, old)


def compare(py: dict, rs: dict) -> list[dict]:
    bad = []
    for f in SOLVER_FIELDS:
        if py[f] != rs[f]:
            if f == "child_values":
                pv, rv = dict(py[f]), dict(rs[f])
                diff = [(a, pv.get(a), rv.get(a)) for a in sorted(set(pv) | set(rv))
                        if pv.get(a) != rv.get(a)]
                bad.append({"field": f, "n_diff": len(diff), "first": diff[:5]})
            else:
                bad.append({"field": f, "py": py[f], "rs": rs[f]})
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--positions", required=True,
                    help="jsonl of {game, ply, k} rows")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--budget", type=int, default=4_000_000)
    ap.add_argument("--max-k-marg", type=int, default=3)
    ap.add_argument("--max-k-clair", type=int, default=8)
    ap.add_argument("--max-k-noab", type=int, default=3)
    ap.add_argument("--min-k", type=int, default=0)
    ap.add_argument("--py-timeout-s", type=int, default=300)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    from analyzer.ev_loss import prepare_env
    env = prepare_env(args.profile)

    import endgame_solver as S  # scripts/level2

    rows = [json.loads(line) for line in Path(args.positions).open()]
    rows = [r for r in rows if r.get("profile") == args.profile]
    rows.sort(key=lambda r: (r["k"], r["game"], r["ply"]))
    picked, seen_games = [], {}
    # spread across games so the test is not five plies of one archive
    for r in rows:
        if r["k"] > max(args.max_k_marg, args.max_k_clair) or r["k"] < args.min_k:
            continue
        if seen_games.get(r["game"], 0) >= 2:
            continue
        seen_games[r["game"]] = seen_games.get(r["game"], 0) + 1
        picked.append(r)
        if len(picked) >= args.n:
            break

    out = {"profile": args.profile, "env": env, "budget": args.budget,
           "n_positions": len(picked), "checks": 0, "skipped": 0,
           "mismatches": [], "positions": []}

    for r in picked:
        arc = json.loads((ARCHIVES / r["game"]).read_text())
        game, board, ms = seat(args.profile, arc["deck_seed"],
                               [int(x) for x in arc["actions"]], int(r["ply"]))
        prow = {"game": r["game"], "ply": r["ply"], "k": r["k"],
                "stratum": r.get("stratum"), "cells": {}}
        if game.string_representation(board) != ms.string_repr():
            out["mismatches"].append({"field": "replay_desync", **prow})
            out["positions"].append(prow)
            continue
        prow["desync"] = False

        modes = []
        if r["k"] <= args.max_k_clair:
            modes.append(("clairvoyant", True))
        # the NO-alpha-beta clairvoyant oracle is a full minimax over the known
        # deck and explodes past K=3 on the Python side; it is run only as the
        # low-K cross-check that +ab is exact.
        if r["k"] <= args.max_k_noab:
            modes.append(("clairvoyant", False))
        if r["k"] <= args.max_k_marg:
            modes.append(("marginalized", False))

        for mode, ab in modes:
            cell = f"{mode}{'+ab' if ab else ''}"
            t0 = time.time()
            try:
                py = _timed_py_solve(S, game, board, mode, args.budget, ab,
                                     args.py_timeout_s)
            except (S.BudgetExceeded, _PySolveTimeout):
                out["skipped"] += 1
                prow["cells"][cell] = {"status": "PY_SKIPPED"}
                continue
            py_s = time.time() - t0
            t0 = time.time()
            rs = ms.solve_endgame(mode=mode, budget=args.budget, alphabeta=ab)
            rs_s = time.time() - t0
            if rs is None:
                out["mismatches"].append(
                    {"field": "rust_budget_exceeded", "cell": cell, **prow})
                prow["cells"][cell] = {"status": "RS_BUDGET_EXCEEDED"}
                continue
            bad = compare(py_result_dict(py), rs_result_dict(rs))
            for b in bad:
                b.update({"cell": cell, "game": r["game"], "ply": r["ply"], "k": r["k"]})
            out["mismatches"].extend(bad)
            out["checks"] += 1
            prow["cells"][cell] = {
                "status": "OK" if not bad else "MISMATCH",
                "py_s": round(py_s, 4), "rs_s": round(rs_s, 4),
                "speedup": round(py_s / rs_s, 2) if rs_s > 0 else None,
                "nodes": int(py.nodes),
                "value": float(py.value),
                "n_root_actions": len(py.child_values),
            }
        out["positions"].append(prow)

    out["ok"] = (len(out["mismatches"]) == 0) and (out["checks"] > 0)
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "positions"}, indent=1))
    for p in out["positions"]:
        print(p["game"], "ply", p["ply"], "K", p["k"], json.dumps(p["cells"]))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
