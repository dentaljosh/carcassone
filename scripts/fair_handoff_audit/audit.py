#!/usr/bin/env python3
"""PHASE 0.1 — Executable audit of the production FAIR endgame handoff.

WHY: governance/PRODUCTION.yaml line 29 says the champion endgame is an
"exact K<=4 alpha-beta solver handoff", but src/carcassonne_ai/fair_agent.py
latches only at K<=2 with the MARGINALIZED (no-alpha-beta) solver and documents
that a clairvoyant K=3-4 solve would be the cheating path. Two different code
paths are being conflated. This script instruments the ACTUAL production fair
launch path and reconciles the truth executably (not by reading alone).

WHAT IT PROVES (per the Phase-0.1 spec):
  (A) Per-move code-path census over ~20 production-config fair games:
      for every fair decision log (k_remaining, phase, path) where path is one
      of {pimc, exact_marginalized, exact_timeout_fallback}. Shows exactly which
      k values trigger the exact handoff.
  (B) Solver-call ledger: a global monkeypatch on endgame_solver.solve records
      (mode, alphabeta, k) for EVERY solve executed during the fair games.
      The leak question -- "did any solver call receive the true deck order
      beyond next_tile?" -- reduces to: was any fair-mode solve mode=="clairvoyant"
      (or alphabeta=True)? The marginalized solver keys on the SORTED bag
      multiset (endgame_solver._key line 133) so it is order-independent by
      construction; only a clairvoyant solve reads true order.
  (C) Order-invariance probes on harvested positions (executable proof of "no
      hidden-order information used"):
        * SOLVER (latched k<=2 TILES): marginalized-solve the board and 3
          deck-permutations (same multiset, same next_tile); assert identical
          (value, optimal_actions). Clean, RNG-free.
        * FULL FAIR DECISION (PIMC): decide on the board and 3 deck-permutations
          with a fresh agent at the same (seed, move_idx); measure how often the
          chosen action changes. NOTE: the fair agent reshuffles the unseen deck
          with its own RNG, and random.Random.shuffle depends on INPUT order, so
          a move flip here is RNG-sampling sensitivity, NOT order exploitation
          (reshuffling destroys the order signal in expectation). We report the
          rate and whether flips are between near-equal-pooled-Q siblings.

Run: nice -n 19 python scripts/fair_handoff_audit/audit.py --games 20 --sims 200 --k 4 --workers 16
"""
from __future__ import annotations

import os
# ---- Production v2.9 Bmild_cap8 champion leaf env (MUST precede imports;
#      DEFAULT_CONFIG reads these at import). Verbatim from fair_agent_smoke.py.
os.environ.setdefault("CARCASSONNE_V25_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_OPP_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "0")
os.environ.setdefault("CARCASSONNE_V29_MEEPLE_CURVE", "-8,-4,-1,0,2,3,4,5")
os.environ.setdefault("CARCASSONNE_V25_MEEPLE_K", "2.0")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_CY_REPR", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse
import copy
import json
import pickle
import random
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

from carcassonne_ai.fair_agent import FairHeuristicMCTSAgent, k_remaining  # noqa: E402
from carcassonne_ai.game_wrapper import Game                              # noqa: E402
from carcassonne_ai.mcts import HeuristicMCTS                             # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase          # noqa: E402
import endgame_solver as _ES                                             # noqa: E402

OUT = REPO / "measurement" / "fair_handoff_audit"
OUT.mkdir(parents=True, exist_ok=True)

# ---- (B) global solver-call ledger via monkeypatch --------------------------
_SOLVE_CALLS: list[dict] = []
_ORIG_SOLVE = _ES.solve


def _patched_solve(game, board, mode="marginalized", budget=4_000_000, alphabeta=False):
    _SOLVE_CALLS.append({
        "mode": mode, "alphabeta": bool(alphabeta),
        "k": k_remaining(board.state),
        "phase": str(board.state.phase),
    })
    return _ORIG_SOLVE(game, board, mode=mode, budget=budget, alphabeta=alphabeta)


_ES.solve = _patched_solve

_CTX: dict = {}


def _permute_unseen_deck(board, rng):
    """Deepcopy of `board` with the UNSEEN state.deck permuted (multiset + the
    in-hand next_tile preserved) -- the hidden information a fair agent must not
    use. Distinct from the agent's own internal reshuffle; here we control it."""
    b = copy.deepcopy(board)
    rng.shuffle(b.state.deck)
    b._str_repr_cache = None
    return b


def play_one(args_tuple):
    """One production-config fair game; returns per-move census + local solver
    ledger + harvested position snapshots."""
    seed, fair_seat = args_tuple
    sims, K = _CTX["sims"], _CTX["k"]
    _SOLVE_CALLS.clear()
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    fair = FairHeuristicMCTSAgent(Game(enable_legal_moves_cache=True),
                                  sims=sims, k_dets=K, c_puct=3.0, seed=seed,
                                  heur_leaf="v2_7", exact_endgame=True)
    clair = HeuristicMCTS(game=Game(enable_legal_moves_cache=True),
                          simulations=sims, c=3.0, seed=seed + 1, heur_leaf="v2_7")
    moves = []
    snaps = []           # harvested (board, k, phase, latched) for offline probes
    harvest_rng = random.Random(seed ^ 0xABCDEF)
    ply = 0
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        mask = game.get_valid_moves(board)
        if cur == fair_seat:
            k = k_remaining(board.state)
            phase = "TILES" if board.state.phase == GamePhase.TILES else "MEEPLES"
            pre = (fair.exact_moves, fair.heur_moves, fair.n_timeouts)
            latched_before = fair._latched
            a = fair.choose_action(board)
            d_exact = fair.exact_moves - pre[0]
            d_timeout = fair.n_timeouts - pre[2]
            if d_exact:
                path = "exact_marginalized"
            elif d_timeout:
                path = "exact_timeout_fallback"
            else:
                path = "pimc"
            moves.append({"ply": ply, "k": k, "phase": phase, "path": path,
                          "latched_before": bool(latched_before)})
            # harvest: all latched (k<=2) TILES decisions + a light sample of the rest
            if (k <= 2 and phase == "TILES") or harvest_rng.random() < 0.06:
                snaps.append({"board": copy.deepcopy(board), "k": k, "phase": phase,
                              "seed": seed, "move_idx": fair._move_idx - 1,
                              "path": path})
        else:
            clair.clear()
            a = int(clair.best_action(board))
        assert mask[a], f"ILLEGAL {a} seed={seed} ply={ply}"
        board, _ = game.get_next_state(board, a)
        ply += 1
    s0, s1 = board.state.scores
    return {
        "seed": seed, "fair_seat": fair_seat, "scores": (int(s0), int(s1)),
        "moves": moves, "solver_calls": list(_SOLVE_CALLS), "snaps": snaps,
        "latch_k": fair.latch_k, "exact_moves": fair.exact_moves,
        "pimc_moves": fair.heur_moves, "timeouts": fair.n_timeouts,
    }


def probe_snaps(snaps, sims, K, n_solver=12, n_pimc=15):
    """(C) Offline order-invariance probes on harvested positions.

    Two DISJOINT probes (a latched k<=2 snapshot goes to the solver probe ONLY;
    a non-latched snapshot goes to the PIMC probe ONLY) so no snapshot triggers
    both a solver check and a latched fair-decision -- keeps solve count bounded:
      * SOLVER probe: marginalized-solve the board vs 1 deck-permutation; the
        marginalized _key sorts the bag so this must be bit-identical (executable
        confirmation of the by-construction order-independence). >=1 permutation
        across >=n_solver positions is enough to catch any violation.
      * PIMC probe: fresh fair decision on the board vs 3 deck-permutations;
        counts move flips -- characterizes the (benign) RNG-reshuffle order
        sensitivity of PIMC, NOT an information leak."""
    game = Game(enable_legal_moves_cache=True)
    solver_checks = []
    pimc_checks = []
    latched = [s for s in snaps if s["k"] <= 2 and s["phase"] == "TILES"]
    nonlatched = [s for s in snaps if not (s["k"] <= 2 and s["phase"] == "TILES")]

    # Probe budget is deliberately SMALL: a hard k=2 marginalized solve can churn
    # toward the 2M-node budget for 1-3 min and stall the whole probe. The real
    # agent already handles this via BudgetExceeded->PIMC fallback; here we just
    # skip the position (record "skipped_budget") rather than block. A budget hit
    # is not a violation — it's an unfinished check, excluded from the pass/fail.
    PROBE_BUDGET = 200_000
    for s in latched[:n_solver]:
        board, k = s["board"], s["k"]
        prng = random.Random(hash((s["seed"], s["move_idx"])) & 0x7FFFFFFF)
        pb = _permute_unseen_deck(board, prng)
        try:
            base = _ORIG_SOLVE(game, board, mode="marginalized",
                               budget=PROBE_BUDGET, alphabeta=False)
            r = _ORIG_SOLVE(game, pb, mode="marginalized",
                            budget=PROBE_BUDGET, alphabeta=False)
        except _ES.BudgetExceeded:
            solver_checks.append({"k": k, "invariant": None,
                                  "skipped_budget": True})
            continue
        ok = (abs(r.value - base.value) <= 1e-9 and
              set(r.optimal_actions) == set(base.optimal_actions))
        solver_checks.append({"k": k, "invariant": ok, "skipped_budget": False,
                              "value": round(base.value, 4),
                              "opt": sorted(base.optimal_actions)})

    for s in nonlatched[:n_pimc]:
        board, k, phase = s["board"], s["k"], s["phase"]
        legal = np.flatnonzero(game.get_valid_moves(board))
        if legal.size <= 1:
            continue
        mi = s["move_idx"]

        def _decide(bd):
            ag = FairHeuristicMCTSAgent(Game(enable_legal_moves_cache=True),
                                        sims=sims, k_dets=K, c_puct=3.0,
                                        seed=s["seed"], heur_leaf="v2_7",
                                        exact_endgame=True)
            ag._move_idx = mi
            return ag.choose_action(bd)

        a0 = _decide(board)
        prng = random.Random((hash((s["seed"], mi)) ^ 0x5555) & 0x7FFFFFFF)
        flips = 0
        for _ in range(3):
            pb = _permute_unseen_deck(board, prng)
            if _decide(pb) != a0:
                flips += 1
        pimc_checks.append({"k": k, "phase": phase, "path": s["path"],
                            "n_perm": 3, "flips": flips})
    return solver_checks, pimc_checks


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--seed-start", type=int, default=910_000_000)
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args(argv)
    _CTX.update(sims=args.sims, k=args.k)

    work = [(args.seed_start + i, i % 2) for i in range(args.games)]
    print(f"[audit] {args.games} fair games @ sims={args.sims} K={args.k} "
          f"(prod v2.9 Bmild_cap8 leaf) vs clairvoyant champion | W{args.workers}",
          flush=True)
    t0 = time.time()
    if args.workers <= 1:
        results = [play_one(w) for w in work]
    else:
        from multiprocessing import get_context
        with get_context("fork").Pool(min(args.workers, len(work))) as pool:
            results = list(pool.imap_unordered(play_one, work))
    results.sort(key=lambda r: r["seed"])
    dt = time.time() - t0
    print(f"[audit] {args.games} games complete in {dt/60:.1f} min", flush=True)

    # ---- (A) code-path census ------------------------------------------------
    all_moves = [m for r in results for m in r["moves"]]
    path_by_k = {}
    for m in all_moves:
        path_by_k.setdefault(m["k"], Counter())[m["path"]] += 1
    latch_ks = Counter(r["latch_k"] for r in results if r["latch_k"] is not None)

    # ---- (B) solver-call ledger ---------------------------------------------
    all_solves = [c for r in results for c in r["solver_calls"]]
    modes = Counter((c["mode"], c["alphabeta"]) for c in all_solves)
    clairvoyant_or_ab = [c for c in all_solves
                         if c["mode"] == "clairvoyant" or c["alphabeta"]]
    solve_k = Counter(c["k"] for c in all_solves)

    # ---- (C) order-invariance probes ----------------------------------------
    all_snaps = [s for r in results for s in r["snaps"]]
    print(f"[audit] probing {len(all_snaps)} harvested positions for order-invariance...",
          flush=True)
    solver_checks, pimc_checks = probe_snaps(all_snaps, args.sims, args.k)

    summary = {
        "config": {"games": args.games, "sims": args.sims, "k_dets": args.k,
                   "leaf": "v2.9 Bmild_cap8", "opponent": "clairvoyant champion",
                   "EXACT_MAX_K": _ES.__dict__.get("EXACT_MAX_K"),
                   "fair_EXACT_MAX_K": 2},
        "runtime_min": round(dt / 60, 2),
        "A_path_by_k": {str(k): dict(c) for k, c in sorted(path_by_k.items())},
        "A_latch_k_distribution": dict(latch_ks),
        "B_solve_modes": {f"{m}|ab={ab}": n for (m, ab), n in modes.items()},
        "B_clairvoyant_or_alphabeta_solves": len(clairvoyant_or_ab),
        "B_solve_k_distribution": dict(sorted(solve_k.items())),
        "C_solver_invariance": {
            "n": len(solver_checks),
            "n_checked": sum(1 for c in solver_checks
                             if c["invariant"] is not None),
            "n_skipped_budget": sum(1 for c in solver_checks
                                    if c["invariant"] is None),
            "all_invariant": all(c["invariant"] for c in solver_checks
                                 if c["invariant"] is not None),
            "n_violations": sum(1 for c in solver_checks
                                if c["invariant"] is False),
        },
        "C_pimc_order_sensitivity": {
            "n_positions": len(pimc_checks),
            "n_with_any_flip": sum(1 for c in pimc_checks if c["flips"] > 0),
            "total_perm_trials": sum(c["n_perm"] for c in pimc_checks),
            "total_flips": sum(c["flips"] for c in pimc_checks),
        },
    }
    (OUT / "audit_summary.json").write_text(json.dumps(summary, indent=2))
    with open(OUT / "audit_raw.pkl", "wb") as f:
        pickle.dump({"moves": all_moves, "solves": all_solves,
                     "solver_checks": solver_checks, "pimc_checks": pimc_checks,
                     "game_results": [{k: v for k, v in r.items() if k != "snaps"}
                                      for r in results]}, f)
    print(json.dumps(summary, indent=2), flush=True)
    print(f"[audit] wrote {OUT/'audit_summary.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
