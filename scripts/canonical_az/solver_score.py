#!/usr/bin/env python3
"""Solver-scoring harness — the NON-CIRCULAR ranker scorer (POST_REVIEW_PLAN §4 / M2 Part A).

The h6400_v2.9 oracle correlates 0.995 with the v2.9 leaf (autopsy F4), so every
offline gate scored against it is circular. The exact K<=4 endgame solver
(scripts/level2/endgame_solver.py) uses the REAL final score-diff (flat_base_score)
as its leaf value -> uncorrelated with the v2.9 leaf -> breaks the circularity.

This harness scores ANY per-child ranker's REGRET AGAINST THE SOLVER (not oracle_q):

  1. Reuse the existing h6400_v2.9 sibling sets (the 10,067 roots CL-033/§3A used;
     qprobe_A/probe.jsonl JOIN pool_A.jsonl on (seed,ply), NO new gen). Reconstruct
     each root via replay_to(seed,ply); compute k_remaining post-replay; filter K<=4.
  2. solve() each K<=4 root -> child_values (exact per-child value). Mode per root:
     marginalized (bag-expectation, the PREFERRED ground truth) at K<=2 where it is
     tractable (== clairvoyant there); clairvoyant+alpha-beta at K=3..4 (marginalized
     intractable there). Flagged per root.
  3. Score the ranker's per-child scores vs the solver child_values using
     step1_train.group_metrics (argmax-regret / top-1 / kendall-tau), oriented to the
     MOVER's perspective so argmax == best move (matches endgame_regret._eval_one /
     regret_of). Regret is in RAW POINTS, >= 0.
  4. Report per-root + aggregate solver-regret / top-1 / tau, split by K and by mode.

Default ranker = the static v2.9 leaf itself (the sanity baseline: its solver-regret
is the reference number). Swap in any callable(child_board, root_player, game) -> float
to score a learned value/feature ranker on the SAME positions the h6400 labels cover.

MEASUREMENT ONLY. Pure CPU, no net (v2.9-leaf ranker). No champion/PRODUCTION change.
"""
from __future__ import annotations

import os
# v2.9 leaf env — MUST precede the carcassonne_ai imports (DEFAULT_CONFIG reads these
# at import). EXACTLY matches dump_dataset.py (the dump that produced the h6400_v2.9
# sibling labels), so the v2.9-leaf ranker here is bit-identical to that leaf_q.
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
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(REPO / "scripts" / "feature_planes_gate"))

import endgame_solver as S                                # noqa: E402
from gen_endgame_positions import replay_to, k_remaining  # noqa: E402
from step1_train import group_metrics                     # noqa: E402 (argmax-regret/top1/tau core)
from carcassonne_ai.virtual_score_v2 import virtual_score_v2  # noqa: E402
import eval_hybrid_handoff as EH                           # noqa: E402 (_heur_leaf_cfg)

HG = REPO / "measurement" / "high_gap_distillation" / "scaled"
DEFAULT_QPROBE = str(HG / "qprobe_A" / "probe.jsonl")
DEFAULT_POOL = str(HG / "pool_A.jsonl")

# Mode policy by root K (M2_PLAN Part A): marginalized is the preferred ground truth
# but tractable only at K<=2 (== clairvoyant there); K>=3 marginalized is intractable
# -> clairvoyant+alpha-beta labels.
#
# NOTE on the qprobe_A reuse set: its 10,067 roots are sampled at DISCRETE k_remaining
# strata {2,4,6,10,14,22,32,44,56} (per-root k_remaining field; verified post-replay).
# So there are NO K=3 (or any odd-K) roots here: K<=2 = 1,119 roots (all K=2, all
# MARGINALIZED); K<=4 = 2,238 (adds 1,119 K=4 roots, all CLAIRVOYANT+AB). K=4 solves are
# the expensive tail (~21min median per M2_PLAN) -> the full K<=4 read-out is gated/cluster,
# NOT this smoke. (The M2_PLAN's "24.2%/15.0%" figures are a DIFFERENT 120-root fresh-greedy
# replay at all K=2..6; the actual qprobe_A reuse is 22.2%/11.1%.)
MARG_MAX_K = 2


# --------------------------------------------------------------------------- #
# Rankers: callable(child_board, root_player, game) -> float (higher = better  #
# for root_player, i.e. the mover). group_metrics's argmax then = the pick.    #
# --------------------------------------------------------------------------- #
def make_v29_leaf_ranker():
    """The static v2.9 leaf itself (the sanity baseline). Bit-identical to
    dump_dataset.py's leaf_q: tanh(virtual_score_v2(child, root_player, cfg)/15),
    terminal children clamped to [-1,1]."""
    cfg = EH._heur_leaf_cfg(2.0)

    def rank(child, root_player, game):
        ended = game.get_game_ended(child, root_player)
        if ended != 0:
            return max(-1.0, min(1.0, float(ended)))
        return math.tanh(virtual_score_v2(child.state, root_player, cfg) / 15.0)

    return rank


RANKERS = {"v29_leaf": make_v29_leaf_ranker}


# --------------------------------------------------------------------------- #
def load_sibling_roots(qprobe: str, pool: str):
    """The h6400_v2.9 sibling sets: qprobe_A (has action_q / k_remaining / phase)
    JOINed with pool_A (has checksum) on (seed, ply). Mirrors dump_dataset.py."""
    checks = {}
    for line in open(pool):
        r = json.loads(line)
        checks[(r["seed"], r["ply"])] = r["checksum"]
    recs = []
    for line in open(qprobe):
        r = json.loads(line)
        key = (r["seed"], r["ply"])
        if key in checks:
            r["checksum"] = checks[key]
            recs.append(r)
    return recs


def score_root(rec, ranker, budget, max_k):
    """Reconstruct one root, solve it, score the ranker's per-child regret vs the
    solver. Returns a per-root dict (or {'_error': ...} / {'_skip': ...})."""
    seed, ply = int(rec["seed"]), int(rec["ply"])
    try:
        game, board = replay_to(seed, ply)
    except Exception as e:  # noqa
        return {"_error": f"{seed}:{ply} recon {type(e).__name__}: {e}"}
    if game.string_representation(board) != rec["checksum"]:
        return {"_error": f"{seed}:{ply} checksum_mismatch"}

    k = k_remaining(board)                     # k computed POST-replay (authoritative)
    if k > max_k:
        return {"_skip": "k>max_k", "k": k}

    # mode policy: marginalized at K<=2 (preferred, == clairvoyant), else clairvoyant+AB
    if k <= MARG_MAX_K:
        mode, ab = "marginalized", False
    else:
        mode, ab = "clairvoyant", True

    root_player = board.state.current_player
    legal = np.flatnonzero(game.get_valid_moves(board)).astype(int)
    if legal.size < 2:
        return {"_skip": "<2 legal", "k": k}

    t0 = time.perf_counter()
    try:
        res = S.solve(game, board, mode=mode, budget=budget, alphabeta=ab)
    except S.BudgetExceeded:
        return {"_skip": "budget", "k": k, "mode": mode,
                "secs": round(time.perf_counter() - t0, 2)}
    solve_secs = time.perf_counter() - t0
    cv = res.child_values                      # {action: P0-perspective value}
    tm = res.to_move

    # Orient BOTH ranker score and solver value to the mover's perspective so that
    # group_metrics' argmax(target)=best and argmax(score)=pick are consistent, and
    # its regret == points lost vs optimal (== endgame_regret / regret_of). Solver
    # child_values are P0-perspective -> flip sign when the mover is P1.
    actions = list(cv.keys())
    solver_mover = np.array([(cv[a] if tm == 0 else -cv[a]) for a in actions], dtype=np.float64)
    score = np.empty(len(actions), dtype=np.float64)
    for i, a in enumerate(actions):
        child, _ = game.get_next_state(board, int(a))
        score[i] = float(ranker(child, root_player, game))

    regret, top1, tau = group_metrics(score, solver_mover)

    # position-difficulty context (mover-perspective spectrum), mirrors _eval_one
    sm_sorted = np.sort(solver_mover)[::-1]
    gap = float(sm_sorted[0] - sm_sorted[1]) if len(sm_sorted) >= 2 else None
    return {
        "seed": seed, "ply": ply, "phase": rec.get("phase", "?"),
        "k": k, "mode": mode, "n_legal": len(actions), "to_move": tm,
        "nodes": res.nodes, "solve_secs": round(solve_secs, 2),
        "solver_regret": round(float(regret), 4),
        "top1": int(top1), "tau": float(tau),
        "best_vs_second_gap": round(gap, 4) if gap is not None else None,
        "value_spread": round(float(solver_mover.max() - solver_mover.min()), 4),
    }


def _agg(rows):
    if not rows:
        return None
    reg = np.array([r["solver_regret"] for r in rows], dtype=np.float64)
    t1 = np.array([r["top1"] for r in rows], dtype=np.float64)
    tau = np.array([r["tau"] for r in rows], dtype=np.float64)
    secs = np.array([r["solve_secs"] for r in rows], dtype=np.float64)
    return {
        "n": len(rows),
        "solver_regret_mean": round(float(reg.mean()), 4),
        "solver_regret_median": round(float(np.median(reg)), 4),
        "solver_regret_max": round(float(reg.max()), 4),
        "top1_rate": round(float(t1.mean()), 4),
        "tau_mean": round(float(np.nanmean(tau)), 4),
        "solve_secs_mean": round(float(secs.mean()), 2),
        "solve_secs_total": round(float(secs.sum()), 1),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--qprobe", default=DEFAULT_QPROBE,
                    help="sibling-set source with action_q/k_remaining (qprobe_A/probe.jsonl)")
    ap.add_argument("--pool", default=DEFAULT_POOL,
                    help="sibling-set source with checksum (pool_A.jsonl)")
    ap.add_argument("--max-k", type=int, default=4, help="K filter (root k_remaining <= this)")
    ap.add_argument("--ranker", default="v29_leaf", choices=list(RANKERS),
                    help="per-child ranker to score (default: the static v2.9 leaf baseline)")
    ap.add_argument("--n", type=int, default=0,
                    help="cap #K<=max_k roots to SCORE (0=all). Roots are pre-filtered by the "
                         "records' k_remaining then verified post-replay; --n counts SOLVED roots.")
    ap.add_argument("--budget", type=int, default=5_000_000, help="solver node budget/root")
    ap.add_argument("--workers", type=int, default=1,
                    help="parallel solve workers (fork). Keep low alongside running evals.")
    ap.add_argument("--out", default="", help="optional: write full JSON report here")
    ap.add_argument("--seed-shuffle", type=int, default=0,
                    help="shuffle roots with this seed before the --n cap (for a random subset)")
    args = ap.parse_args(argv)

    ranker = RANKERS[args.ranker]()
    recs = load_sibling_roots(args.qprobe, args.pool)
    print(f"[load] {len(recs)} sibling roots (qprobe ∩ pool)", flush=True)

    # cheap pre-filter on the record's k_remaining (verified post-replay in score_root).
    cand = [r for r in recs if int(r.get("k_remaining", 99)) <= args.max_k]
    if args.seed_shuffle:
        import random
        random.Random(args.seed_shuffle).shuffle(cand)
    else:
        cand.sort(key=lambda r: (int(r.get("k_remaining", 99)), int(r["seed"]), int(r["ply"])))
    kdist = Counter(int(r.get("k_remaining", 99)) for r in cand)
    print(f"[filter] {len(cand)} roots with record k_remaining<={args.max_k} "
          f"({100*len(cand)/max(len(recs),1):.1f}%); K-dist={dict(sorted(kdist.items()))}", flush=True)

    def _worker(rec):
        return score_root(rec, ranker, args.budget, args.max_k)

    scored, errs, skips = [], [], []
    t0 = time.perf_counter()

    def _handle(out):
        if out is None:
            return
        if "_error" in out:
            errs.append(out)
        elif "_skip" in out:
            skips.append(out)
        else:
            scored.append(out)

    # single-process by default (cheap, safe alongside the running evals); optional pool.
    if args.workers <= 1:
        for rec in cand:
            _handle(_worker(rec))
            if args.n and len(scored) >= args.n:
                break
            if len(scored) and len(scored) % 10 == 0 and (len(scored) + len(skips) + len(errs)) % 10 == 0:
                el = time.perf_counter() - t0
                print(f"  scored={len(scored)} skip={len(skips)} err={len(errs)} "
                      f"({el/max(len(scored),1):.1f}s/scored)", flush=True)
    else:
        from multiprocessing import get_context
        ctx = get_context("fork")
        # when capping with --n we can't stop a pool mid-stream cleanly; just submit the
        # (already small) candidate list and cut after. For the full run this is a no-op.
        sub = cand[: args.n * 3] if args.n else cand   # 3x headroom for skips
        with ctx.Pool(args.workers) as pool:
            for out in pool.imap_unordered(_worker, sub, chunksize=1):
                _handle(out)
                if args.n and len(scored) >= args.n:
                    break

    dt = time.perf_counter() - t0
    print(f"[done] scored={len(scored)} skipped={len(skips)} errors={len(errs)} in {dt:.1f}s", flush=True)
    if errs[:3]:
        print("  sample errors:", [e["_error"] for e in errs[:3]], flush=True)
    if skips:
        print("  skip reasons:", dict(Counter(s["_skip"] for s in skips)), flush=True)

    by_k = {k: _agg([r for r in scored if r["k"] == k]) for k in sorted({r["k"] for r in scored})}
    by_mode = {m: _agg([r for r in scored if r["mode"] == m]) for m in sorted({r["mode"] for r in scored})}
    report = {
        "ranker": args.ranker, "max_k": args.max_k, "budget": args.budget,
        "qprobe": args.qprobe, "pool": args.pool,
        "n_roots_total": len(recs), "n_candidates": len(cand),
        "n_scored": len(scored), "n_skipped": len(skips), "n_errors": len(errs),
        "aggregate": _agg(scored), "by_k": by_k, "by_mode": by_mode,
        "per_root": scored,
    }
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2))
        print(f"[out] wrote {args.out}", flush=True)

    print(f"\n==== SOLVER-SCORE ({args.ranker}) ====")
    a = report["aggregate"]
    if a:
        print(f"AGG  n={a['n']}  solver_regret mean={a['solver_regret_mean']} "
              f"median={a['solver_regret_median']} max={a['solver_regret_max']}  "
              f"top1={a['top1_rate']}  tau={a['tau_mean']}")
    for k, ag in by_k.items():
        if ag:
            print(f"  K={k} ({'marg' if k <= MARG_MAX_K else 'clair'})  n={ag['n']}  "
                  f"regret={ag['solver_regret_mean']}  top1={ag['top1_rate']}  "
                  f"tau={ag['tau_mean']}  {ag['solve_secs_mean']}s/solve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
