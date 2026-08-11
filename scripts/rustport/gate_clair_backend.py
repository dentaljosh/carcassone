#!/usr/bin/env python3
"""GATE (d) — IDENTITY GATE for `eval_fair_puct --info clair --backend rust`.

WHY.  `--info clair` is the CLAIRVOYANCE-TAX arm: `elo(clair) - elo(fair)` is the
number the whole blind-vs-sighted framing rests on (~156 elo at champion config,
CL-022 lineage).  It is a REFERENCE INSTRUMENT, so the argument that gated the
champion as a PLAYER (G4/G6) does not transfer — a converted ruler grades nothing
until it is shown to be the SAME ruler, ply for ply.

WHAT IS COMPARED.  A FULL GAME, both seats, driven twice through the harness's own
`_make_champion(info="clair", ...)` construction — once `backend="python"`, once
`backend="rust"` — with, at every ply:

    the CHOSEN ACTION                                     (the ruler's decision)
    which arm answered: search prefix or marginalized solver  (the endgame latch)
    root_n, root_w  as RAW f64 BITS, and every root child (action, N, W-bits)
                                                          (the ruler's REASONS)

Comparing only the action would pass a ruler that got the right answer for the
wrong reasons; comparing the whole root table makes the two trees prove they are
the same tree.  The endgame plies (solver-owned) carry no root table and are
compared on action + `latch_k` + solver node count, which is the right surface
there — the solver is SHARED code (`_MarginalizedHandoff`), not part of the port.

WHY BOTH SEATS.  `_MarginalizedHandoff` latches on the POSITION, not on a seat, so
one handoff can play a whole game; doing that exercises every ply — including the
tile/meeple phase pairs and the endgame handoff — instead of half of them.

⚠️ BUDGET.  The default `--sims` is far below the clairvoyant champion's own
(k_dets x sims_per_det).  That is deliberate and it is not a weakening: this gate
proves ENGINE IDENTITY, which the sim budget does not interact with, and G3
(`reconcile_search.py`) already carries the production-budget raw-float leg.  A
full game at the champion budget would be hours per leg.

    .venv/bin/python scripts/rustport/gate_clair_backend.py --games 3 --sims 100
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "scripts" / "classical_search", REPO / "scripts" / "level2",
           REPO / "scripts" / "measurement_infra"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# MUST precede any carcassonne_ai import: this module installs the production leaf
# env at import time and `virtual_score_v2.DEFAULT_CONFIG` is import-frozen from it.
import eval_fair_puct as E  # noqa: E402

from carcassonne_ai import champion_factory as CF  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402

OUT = REPO / "measurement" / "rustport_p6" / "GATE_CLAIR_BACKEND.json"


def ubits(x: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


def _py_root(agent, game, board):
    """The python clair prefix's root table for `board` (None if the solver moved)."""
    m = getattr(agent._prefix, "mcts", None)
    if m is None:
        return None
    root = m._nodes.get(game.string_representation(board))
    if root is None:
        return None
    return {"root_n": int(root.N), "root_w_bits": ubits(root.W),
            "root_children": [[int(a), int(c.N), ubits(c.W)]
                              for a, c in sorted(root.children.items())]}


def _rs_root(agent):
    res = getattr(agent._prefix, "_last", None)
    if res is None:
        return None
    return {"root_n": int(res["root_n"]), "root_w_bits": int(res["root_w_bits"]),
            "root_children": [[int(a), int(n), int(w)]
                              for a, n, w in res["root_children"]]}


def _counters(agent) -> dict:
    return {"prefix_moves": int(agent.prefix_moves), "exact_moves": int(agent.exact_moves),
            "latch_k": agent.latch_k, "solver_nodes": int(agent.solver_nodes),
            "n_timeouts": int(agent.n_timeouts)}


def play(deck_seed: int, *, sims: int, k_dets: int, K: int, seed: int,
         max_plies: int) -> dict:
    """One full game, both seats, python and rust clair handoffs in LOCKSTEP.

    The game advances by the PYTHON action; a divergence is recorded (and the game
    stopped) rather than allowed to fork the two legs into incomparable positions.
    """
    cfg = CF.production_prior_cfg()
    game = Game(enable_legal_moves_cache=True)
    py_game = Game(enable_legal_moves_cache=True)
    rs_game = Game(enable_legal_moves_cache=True)
    py = E._make_champion("clair", cfg, sims, k_dets, K, seed, py_game,
                          backend="python")
    rs = E._make_champion("clair", cfg, sims, k_dets, K, seed, rs_game, backend="rust")

    import random

    random.seed(int(deck_seed))
    board = game.get_init_board()
    E._start_mirrors(board, py, rs)

    plies, diffs, root_checks, solver_plies = 0, [], 0, 0
    t_py = t_rs = 0.0
    while not board.state.is_terminated() and plies < max_plies:
        py_pre, rs_pre = py.prefix_moves, rs.prefix_moves
        t0 = time.perf_counter()
        a_py = int(py.move(board))
        t_py += time.perf_counter() - t0
        py_searched = py.prefix_moves > py_pre
        r_py = _py_root(py, py_game, board) if py_searched else None
        t1 = time.perf_counter()
        a_rs = int(rs.move(board))
        t_rs += time.perf_counter() - t1
        rs_searched = rs.prefix_moves > rs_pre
        r_rs = _rs_root(rs) if rs_searched else None
        bad = []
        if a_py != a_rs:
            bad.append({"field": "chosen_action", "python": a_py, "rust": a_rs})
        # Which ARM answered must agree: a python solver ply against a rust search
        # ply would be a latch divergence hiding behind an equal action.
        if _counters(py)["exact_moves"] != _counters(rs)["exact_moves"]:
            bad.append({"field": "exact_moves", "python": _counters(py)["exact_moves"],
                        "rust": _counters(rs)["exact_moves"]})
        if py_searched != rs_searched:
            bad.append({"field": "who_answered", "python": py_searched,
                        "rust": rs_searched})
        elif not py_searched:
            # SOLVER-OWNED PLY. Neither agent searched, so neither carries a root
            # table for THIS board — and reading one anyway is a trap: python's
            # `_nodes` lookup can still find a STALE node left by an earlier ply's
            # search while rust's `_last` is literally the previous search's
            # result, so the two "root tables" would be for different positions.
            # The comparable surface here is the action + the handoff counters,
            # and the solver itself is SHARED python code on both legs.
            solver_plies += 1
        else:
            root_checks += 1
            if r_py != r_rs:
                bad.append({"field": "root_table",
                            "python": str(r_py)[:300], "rust": str(r_rs)[:300]})
        if bad:
            diffs.append({"ply": plies, "issues": bad})
            break
        board, _ = game.get_next_state(board, a_py)
        E._advance_mirrors(a_py, py, rs)
        plies += 1

    return {"deck_seed": int(deck_seed), "plies": plies,
            "root_tables_compared": root_checks, "solver_plies": solver_plies,
            "terminal": bool(board.state.is_terminated()),
            "scores": [int(board.state.scores[0]), int(board.state.scores[1])],
            "python_counters": _counters(py), "rust_counters": _counters(rs),
            "counters_match": _counters(py) == _counters(rs),
            "diffs": diffs,
            "python_secs": round(t_py, 1), "rust_secs": round(t_rs, 1),
            "speedup": (round(t_py / t_rs, 2) if t_rs > 0 else None)}


def _job(a):
    return play(a[0], sims=a[1], k_dets=a[2], K=a[3], seed=a[4], max_plies=a[5])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gate_clair_backend")
    ap.add_argument("--games", type=int, default=3)
    ap.add_argument("--seed-start", type=int, default=96900000000)
    ap.add_argument("--sims", type=int, default=100,
                    help="TOTAL clairvoyant sims per move (the arm's sims x k_dets). "
                         "Engine identity does not interact with the budget; G3 carries "
                         "the production-budget raw-float leg.")
    ap.add_argument("--k-dets", type=int, default=1,
                    help="the clair arm multiplies sims x k_dets into ONE search")
    ap.add_argument("--exact-k", type=int, default=2,
                    help="the marginalized endgame latch (shared by both legs)")
    ap.add_argument("--agent-seed", type=int, default=0)
    ap.add_argument("--max-plies", type=int, default=400)
    ap.add_argument("--workers", type=int, default=1, help="GAME-parallel fork pool")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)

    jobs = [(int(args.seed_start) + i, int(args.sims), int(args.k_dets),
             int(args.exact_k), int(args.agent_seed), int(args.max_plies))
            for i in range(int(args.games))]
    if int(args.workers) > 1:
        import multiprocessing as mp

        with mp.get_context("fork").Pool(min(args.workers, len(jobs))) as pool:
            rows = list(pool.imap_unordered(_job, jobs))
    else:
        rows = [_job(j) for j in jobs]

    for r in rows:
        print(f"  deck={r['deck_seed']} plies={r['plies']} "
              f"root_tables={r['root_tables_compared']} solver_plies={r['solver_plies']} "
              f"terminal={r['terminal']} scores={r['scores']} "
              f"{'IDENTICAL' if not r['diffs'] else 'MISMATCH'} "
              f"| py {r['python_secs']}s rs {r['rust_secs']}s x{r['speedup']}",
              flush=True)

    mism = [{"deck_seed": r["deck_seed"], "diffs": r["diffs"]} for r in rows if r["diffs"]]
    mism += [{"deck_seed": r["deck_seed"], "counters": [r["python_counters"],
                                                        r["rust_counters"]]}
             for r in rows if not r["counters_match"]]
    # A game that never reached terminal proved less than it looks like it did.
    not_terminal = [r["deck_seed"] for r in rows if not r["terminal"]]
    if not_terminal:
        mism.append({"error": "games did not reach terminal — the endgame handoff was "
                              "not exercised", "deck_seeds": not_terminal})
    ok = bool(rows) and not mism
    t_py = sum(r["python_secs"] for r in rows)
    t_rs = sum(r["rust_secs"] for r in rows)
    out = {
        "gate": "rustport P6 — eval_fair_puct --info clair, python vs rust",
        "why": "--info clair is the CLAIRVOYANCE-TAX arm (elo(clair) - elo(fair), ~156 "
               "elo at champion config). It is a REFERENCE INSTRUMENT: G4/G6 gated the "
               "champion as a PLAYER and does not transfer.",
        "seam": "_make_champion(info='clair', backend=...) -> "
                "champion_factory.build_clairvoyant_champion(backend='rust') -> "
                "rust_agent.RustCarryClairvoyantAgent, inside "
                "eval_fair_puct._MirrorMarginalizedHandoff. The marginalized endgame "
                "solver is the SAME python code on both legs.",
        "surface": "per ply: chosen action, which arm answered (search vs solver), and "
                   "the full root table (root_n, root_w and every child's (action, N, W)) "
                   "as RAW f64 BIT PATTERNS; per game: the handoff counters "
                   "(prefix_moves / exact_moves / latch_k / solver_nodes / n_timeouts)",
        "knobs": {"sims_total_per_move": int(args.sims) * int(args.k_dets),
                  "exact_k": int(args.exact_k), "agent_seed": int(args.agent_seed)},
        "games": len(rows),
        "plies": sum(r["plies"] for r in rows),
        "root_tables_compared": sum(r["root_tables_compared"] for r in rows),
        "solver_plies": sum(r["solver_plies"] for r in rows),
        "mismatches": mism,
        "python_secs": round(t_py, 1), "rust_secs": round(t_rs, 1),
        "speedup": (round(t_py / t_rs, 2) if t_rs > 0 else None),
        "verdict": "PASS" if ok else "FAIL",
        "scope": "the clairvoyant ruler at these knobs on this revision, net-free. Gap 3 "
                 "(evaluator injection) stays OPEN: --info fair-net / fair-netprior "
                 "still refuse the rust backend.",
        "rows": rows,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"\n{out['verdict']}: {len(rows)} games, {out['plies']} plies, "
          f"{out['root_tables_compared']} root tables, {len(mism)} mismatches, "
          f"{out['speedup']}x -> {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
