#!/usr/bin/env python3
"""Exact-endgame-hybrid PRE-FLIGHT bench: how expensive is one exact solve at each K?

Decides which handoff K are tractable for FULL-GAME play (Part C) vs micro-validation
only. Loads real positions from the L2-3 suite, reconstructs each board, and times a
single clairvoyant alpha-beta solve (the agent's per-decision cost at that K). Also
asserts the solver's chosen move (min optimal_actions) is LEGAL — the exact-tail
correctness gate, with no full game needed.

Clairvoyant + alpha-beta only (the like-for-like, fast mode the exact:K:clair agent uses).
Pure CPU, single process. Reuses scripts/level2/endgame_solver + gen_endgame_positions.

  python scripts/exact_hybrid/bench_solver_by_k.py --ks 2 3 --per-k 10 --budget 2000000
"""
from __future__ import annotations
import os
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse, json, statistics as st, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

import numpy as np
import endgame_solver as S
from gen_endgame_positions import replay_to
from gen_endgame_multisource import replay_actions

SUITE = REPO / "measurement" / "level2" / "l23_positions.jsonl"


def _reconstruct(rec):
    if rec.get("actions") is not None:
        return replay_actions(rec["seed"], rec["actions"])
    return replay_to(rec["seed"], rec["ply"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default=str(SUITE))
    ap.add_argument("--ks", type=int, nargs="+", default=[2, 3])
    ap.add_argument("--per-k", type=int, default=10)
    ap.add_argument("--budget", type=int, default=2_000_000)
    ap.add_argument("--cap-secs", type=float, default=180.0,
                    help="advisory: print a warning if any single solve exceeds this")
    args = ap.parse_args(argv)

    recs = [json.loads(l) for l in open(args.suite)]
    by_k: dict[int, list] = {}
    for r in recs:
        by_k.setdefault(r["k_remaining"], []).append(r)

    print(f"# exact-solver pre-flight bench (clairvoyant + alpha-beta), budget={args.budget:,}")
    print(f"{'K':>2} {'n':>3} {'solved':>7} {'sec_med':>8} {'sec_max':>8} {'node_med':>9} "
          f"{'node_max':>9} {'legal_med':>9} {'verdict'}")
    summary = {}
    for k in args.ks:
        pool = by_k.get(k, [])[: args.per_k]
        secs, nodes, legals, solved, illegal = [], [], [], 0, 0
        for rec in pool:
            game, board = _reconstruct(rec)
            legal_n = int(np.flatnonzero(game.get_valid_moves(board)).size)
            t0 = time.perf_counter()
            try:
                res = S.solve(game, board, mode="clairvoyant", budget=args.budget, alphabeta=True)
                dt = time.perf_counter() - t0
                # exact-tail correctness: chosen move legal + in the optimal set
                choice = int(min(res.optimal_actions))
                if not game.get_valid_moves(board)[choice]:
                    illegal += 1
                solved += 1
                secs.append(dt); nodes.append(res.nodes); legals.append(legal_n)
                if dt > args.cap_secs:
                    print(f"   [warn] K={k} seed={rec['seed']} ply={rec.get('ply')} "
                          f"solve took {dt:.0f}s ({res.nodes:,} nodes, legal_n={legal_n})")
            except S.BudgetExceeded:
                dt = time.perf_counter() - t0
                secs.append(dt); legals.append(legal_n)
                print(f"   [budget] K={k} seed={rec['seed']} ply={rec.get('ply')} "
                      f"hit {args.budget:,} nodes in {dt:.0f}s (legal_n={legal_n})")
        n = len(pool)
        if solved:
            smed, smax = st.median([s for s in secs]), max(secs)
            nmed = st.median(nodes) if nodes else 0
            nmax = max(nodes) if nodes else 0
            lmed = st.median(legals) if legals else 0
            # full-game feasibility heuristic: a game tail re-solves at K, K-1, ... 2, ~2x the
            # K-solve total; flag tractable if the median single solve is well under a second.
            verdict = ("FULLGAME-OK" if smed < 1.0 else
                       "FULLGAME-MARGINAL" if smed < 10.0 else "MICRO-ONLY")
            print(f"{k:>2} {n:>3} {solved:>4}/{n:<2} {smed:>8.2f} {smax:>8.2f} {nmed:>9.0f} "
                  f"{nmax:>9.0f} {lmed:>9.0f} {verdict}{'  ILLEGAL!' if illegal else ''}")
            summary[k] = dict(n=n, solved=solved, sec_med=smed, sec_max=smax,
                              node_med=nmed, node_max=nmax, legal_med=lmed,
                              illegal=illegal, verdict=verdict)
        else:
            print(f"{k:>2} {n:>3}     0/{n:<2}  (all budget-exceeded) -> MICRO-ONLY at this budget")
            summary[k] = dict(n=n, solved=0, verdict="MICRO-ONLY")
    outp = REPO / "measurement" / "exact_endgame_hybrid"
    outp.mkdir(parents=True, exist_ok=True)
    json.dump(summary, open(outp / "solver_bench_by_k.json", "w"), indent=2)
    print(f"\n[written] {outp / 'solver_bench_by_k.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
