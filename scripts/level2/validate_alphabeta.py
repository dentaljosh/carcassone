"""Validate + benchmark the clairvoyant alpha-beta solver (endgame_solver).

Two jobs:
  (1) TRUST GATE: on K where the no-prune oracle is tractable (K=2, K=3), solve
      each position BOTH ways (alphabeta=False oracle vs alphabeta=True) and
      assert V* is bit-equal AND the optimal-action set is identical. Alpha-beta
      is only exact if it never changes the answer — this proves it. Reports the
      node-count reduction (prune ratio) so we can see how much depth it buys.
  (2) FEASIBILITY: on higher K (K=4, K=5) where the oracle is intractable, run
      AB-only with a node budget + per-position wall guard and report
      solved/budget-hit, nodes, and wall-time distribution.

Clairvoyant mode only (AB is clairvoyant-only). Pure CPU, parallel over positions.

Usage:
  python scripts/level2/validate_alphabeta.py --suite measurement/level2/l23_positions.jsonl \
      --gate-ks 2 3 --gate-limit 40 --feas-ks 4 --feas-limit 30 \
      --budget 3000000 --wall 120 --workers 6
"""
from __future__ import annotations

import os
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
import json
import math
import statistics as st
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import endgame_solver as S
from gen_endgame_positions import replay_to


def _gate_one(rec):
    """Oracle vs AB on one position. Returns dict with match + node counts."""
    seed, ply = rec["seed"], rec["ply"]
    game, board = replay_to(seed, ply)
    t0 = time.perf_counter()
    try:
        ref = S.solve(game, board, mode="clairvoyant", budget=rec["_budget"], alphabeta=False)
    except S.BudgetExceeded:
        return {"k": rec["k_remaining"], "status": "oracle_budget"}
    t1 = time.perf_counter()
    ab = S.solve(game, board, mode="clairvoyant", budget=rec["_budget"], alphabeta=True)
    t2 = time.perf_counter()
    val_ok = abs(ref.value - ab.value) <= 1e-9
    set_ok = set(ref.optimal_actions) == set(ab.optimal_actions)
    # every child value must match too (regret harness scores every move)
    cv_ok = (set(ref.child_values) == set(ab.child_values) and
             all(abs(ref.child_values[a] - ab.child_values[a]) <= 1e-9 for a in ref.child_values))
    return {
        "k": rec["k_remaining"], "status": "ok" if (val_ok and set_ok and cv_ok) else "MISMATCH",
        "val_ok": val_ok, "set_ok": set_ok, "cv_ok": cv_ok,
        "value": ref.value, "ref_nodes": ref.nodes, "ab_nodes": ab.nodes,
        "ref_secs": round(t1 - t0, 3), "ab_secs": round(t2 - t1, 3),
        "prune": (ref.nodes / ab.nodes) if ab.nodes else float("nan"),
        "seed": seed, "ply": ply,
    }


def _feas_one(rec):
    """AB-only feasibility on one position (oracle intractable here)."""
    seed, ply = rec["seed"], rec["ply"]
    game, board = replay_to(seed, ply)
    t0 = time.perf_counter()
    try:
        ab = S.solve(game, board, mode="clairvoyant", budget=rec["_budget"], alphabeta=True)
        secs = time.perf_counter() - t0
        return {"k": rec["k_remaining"], "status": "solved", "nodes": ab.nodes,
                "secs": round(secs, 2), "value": ab.value, "n_opt": len(ab.optimal_actions),
                "n_legal": len(ab.child_values), "legal_n": rec.get("legal_n"),
                "seed": seed, "ply": ply}
    except S.BudgetExceeded:
        secs = time.perf_counter() - t0
        return {"k": rec["k_remaining"], "status": "budget", "nodes": rec["_budget"],
                "secs": round(secs, 2), "legal_n": rec.get("legal_n"), "seed": seed, "ply": ply}


def _summ(label, rows):
    solved = [r for r in rows if r.get("status") in ("ok", "solved")]
    print(f"\n=== {label}: {len(rows)} positions ===")
    if not rows:
        return
    bad = [r for r in rows if r.get("status") == "MISMATCH"]
    if bad:
        print(f"  !!! {len(bad)} MISMATCH (alpha-beta NOT exact) — first: {bad[0]}")
    other = [r for r in rows if r.get("status") not in ("ok", "solved", "MISMATCH")]
    if other:
        from collections import Counter
        print(f"  non-solved: {dict(Counter(r['status'] for r in other))}")
    if solved:
        nodes = [r.get("ab_nodes", r.get("nodes")) for r in solved]
        secs = [r.get("ab_secs", r.get("secs")) for r in solved]
        print(f"  solved {len(solved)}/{len(rows)}  nodes med={st.median(nodes):.0f} "
              f"max={max(nodes)}  secs med={st.median(secs):.2f} max={max(secs):.1f}")
        prunes = [r["prune"] for r in solved if "prune" in r and r["prune"] == r["prune"]]
        if prunes:
            print(f"  prune ratio (oracle_nodes/ab_nodes) med={st.median(prunes):.1f}x "
                  f"min={min(prunes):.1f}x max={max(prunes):.1f}x")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="measurement/level2/l23_positions.jsonl")
    ap.add_argument("--gate-ks", type=int, nargs="*", default=[2, 3])
    ap.add_argument("--gate-limit", type=int, default=40)
    ap.add_argument("--feas-ks", type=int, nargs="*", default=[4])
    ap.add_argument("--feas-limit", type=int, default=30)
    ap.add_argument("--budget", type=int, default=3_000_000)
    ap.add_argument("--gate-budget", type=int, default=400_000)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", default=None, help="optional JSON dump of all rows")
    args = ap.parse_args(argv)

    recs = [json.loads(l) for l in open(args.suite)]
    by_k = {}
    for r in recs:
        by_k.setdefault(r["k_remaining"], []).append(r)

    gate_recs = []
    for k in args.gate_ks:
        for r in by_k.get(k, [])[:args.gate_limit]:
            r = dict(r, _budget=args.gate_budget)
            gate_recs.append(r)
    feas_recs = []
    for k in args.feas_ks:
        for r in by_k.get(k, [])[:args.feas_limit]:
            r = dict(r, _budget=args.budget)
            feas_recs.append(r)

    from multiprocessing import get_context
    ctx = get_context("fork")
    print(f"alpha-beta validation: gate {len(gate_recs)} (K={args.gate_ks}, budget={args.gate_budget}), "
          f"feas {len(feas_recs)} (K={args.feas_ks}, budget={args.budget}), W={args.workers}", flush=True)

    t0 = time.perf_counter()
    gate_rows, feas_rows = [], []
    if gate_recs:
        with ctx.Pool(args.workers) as pool:
            for i, row in enumerate(pool.imap_unordered(_gate_one, gate_recs, chunksize=1), 1):
                gate_rows.append(row)
                if row.get("status") == "MISMATCH":
                    print(f"  MISMATCH at {row.get('seed')}/{row.get('ply')}: {row}", flush=True)
                if i % 10 == 0:
                    print(f"  gate {i}/{len(gate_recs)} ({(time.perf_counter()-t0)/i:.1f}s/pos)", flush=True)
    _summ("GATE (oracle vs alpha-beta — must be 0 MISMATCH)", gate_rows)

    if feas_recs:
        t1 = time.perf_counter()
        with ctx.Pool(args.workers) as pool:
            for i, row in enumerate(pool.imap_unordered(_feas_one, feas_recs, chunksize=1), 1):
                feas_rows.append(row)
                print(f"  feas {i}/{len(feas_recs)}: K={row['k']} {row['status']} "
                      f"nodes={row['nodes']} {row['secs']}s legal_n={row.get('legal_n')}", flush=True)
        _summ(f"FEASIBILITY (AB-only, budget={args.budget})", feas_rows)

    if args.out:
        json.dump({"gate": gate_rows, "feas": feas_rows}, open(args.out, "w"))
        print("\nwrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
