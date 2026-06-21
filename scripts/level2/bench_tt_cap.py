"""Bench the TT entry-cap: correctness (capped value == uncapped) + the
memory->nodes inflation curve. Decides whether plan A (cap + multi-box re-run)
actually helps the hard iter8 tail, or whether capping just explodes node counts.

Run single-threaded; safe alongside a running W=2 probe (medium position ~2GB).
"""
import json, os, sys, time, resource

os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from gen_endgame_multisource import replay_actions
from gen_endgame_positions import replay_to
import importlib


def _reconstruct(rec):
    if rec.get("actions") is not None:
        return replay_actions(rec["seed"], rec["actions"])
    return replay_to(rec["seed"], rec["ply"])


def _rss_gb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024**2)  # KB->GB on linux


def solve_with_cap(rec, cap, budget):
    os.environ["CARCASSONNE_TT_CAP"] = str(cap)
    import endgame_solver
    importlib.reload(endgame_solver)            # re-read env cap
    S = endgame_solver
    game, board = _reconstruct(rec)
    t0 = time.perf_counter()
    try:
        res = S.solve(game, board, mode="clairvoyant", budget=budget, alphabeta=True)
        secs = time.perf_counter() - t0
        return {"solved": True, "value": res.value, "opt": sorted(res.optimal_actions),
                "nodes": res.nodes, "secs": secs, "rss_gb": _rss_gb()}
    except S.BudgetExceeded:
        return {"solved": False, "nodes": budget, "secs": time.perf_counter() - t0,
                "rss_gb": _rss_gb()}


def main():
    suite = sys.argv[1] if len(sys.argv) > 1 else "/mnt/c/carc-shared/l23_k4_expand.jsonl"
    fast_gen = "greedy_s3500000000"             # tiny, instant -> correctness check
    med_gen = sys.argv[2] if len(sys.argv) > 2 else "iter8_s3501000016"  # ~38k nodes, iter8-source
    recs = {json.loads(l)["gen_id"]: json.loads(l) for l in open(suite)}

    # 1) CORRECTNESS: a fast position, uncapped vs aggressively capped -> same value/opt.
    fr = recs.get(fast_gen)
    if fr:
        base = solve_with_cap(fr, 0, 2_000_000)
        capped = solve_with_cap(fr, 500, 2_000_000)   # cap=500 entries: forces freeze
        ok = base["solved"] and capped["solved"] and base["value"] == capped["value"] and base["opt"] == capped["opt"]
        print(f"[correctness] {fast_gen}: uncapped V*={base['value']} nodes={base['nodes']} | "
              f"cap500 V*={capped['value']} nodes={capped['nodes']} | "
              f"MATCH={ok} (node inflation {capped['nodes']/max(base['nodes'],1):.1f}x)")
        if not ok:
            print("  !! CORRECTNESS FAIL — cap changes the answer; abort plan A"); return 1

    # 2) INFLATION CURVE: medium position, uncapped then shrinking caps.
    mr = recs.get(med_gen)
    if not mr:
        print(f"med position {med_gen} not in suite"); return 1
    print(f"\n[inflation] {med_gen} (legal_n={mr.get('legal_n')}):")
    base = solve_with_cap(mr, 0, 4_000_000)
    if not base["solved"]:
        print("  uncapped didn't solve at 4M budget"); return 1
    full_entries = base["nodes"]               # rough upper bound on TT entries
    print(f"  uncapped: V*={base['value']} nodes={base['nodes']} secs={base['secs']:.0f} rss={base['rss_gb']:.2f}GB")
    print(f"  (rss/nodes ~= {base['rss_gb']*1024/max(base['nodes'],1):.2f} MB-per-1k-nodes proxy)")
    for frac in (0.5, 0.25, 0.1):
        cap = max(int(full_entries * frac), 500)
        r = solve_with_cap(mr, cap, 600_000)   # fail-fast: >16x inflation aborts as BUDGET-HIT
        infl = r["nodes"] / base["nodes"]
        val_ok = r.get("value") == base["value"]
        status = "SOLVED" if r["solved"] else "BUDGET-HIT"
        print(f"  cap={cap:>8} ({frac:>4.0%} of nodes): {status} nodes={r['nodes']:>9} "
              f"infl={infl:>5.1f}x rss={r['rss_gb']:.2f}GB val_ok={val_ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
