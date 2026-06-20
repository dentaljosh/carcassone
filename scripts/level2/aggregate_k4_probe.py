"""Aggregate the K=4 (multi-source) endgame-regret probe — with the two checks
the L2-3 aggregator doesn't do, both demanded by the probe's critical caveat:

  (1) SELECTION BIAS. A higher-K suite is useless if the solver only cracks the
      easy boards. For each (mode, K) we compare the observable difficulty of
      SOLVED vs UNSOLVED (budget-hit) positions — median/mean legal_n and
      bag_size — and flag when solved positions are systematically easier
      (lower legal_n). We also report solved-rate BY SOURCE so a source whose
      positions are disproportionately unsolved is visible.

  (2) BY-SOURCE ROBUSTNESS. Agent regret metrics (top-1, mean/median regret,
      blunder rates) split by the generating source, so we can see whether the
      agent ranking is an artifact of one generator's position distribution.

PERFECT-INFORMATION (clairvoyant) vs BAG-EXPECTATION (marginalized) labels are
kept separate (reported per mode), per the protocol.

Pure reader. Usage:
  python scripts/level2/aggregate_k4_probe.py <RESULTS_DIR> [--out .../K4_PROBE.json]
"""
from __future__ import annotations

import argparse
import json
import statistics as st
from collections import defaultdict
from pathlib import Path


def _load(results_dir: Path):
    out = []
    for fp in results_dir.glob("*.json"):
        if fp.name.endswith("_RESULTS.json") or "PROBE" in fp.name:
            continue
        try:
            out.append(json.load(open(fp)))
        except Exception:
            pass
    return out


def _med(xs):
    return round(st.median(xs), 1) if xs else None


def _agent_stats(rows, agent, mode, decision_only=False):
    regs, matches = [], []
    for d in rows:
        g = d["gt"].get(mode, {})
        if not g.get("solved"):
            continue
        if decision_only and g.get("n_optimal", 0) >= g.get("n_legal", 1):
            continue
        pa = g.get("per_agent", {}).get(agent)
        if not pa or pa.get("regret") is None:
            continue
        regs.append(pa["regret"])
        matches.append(1 if pa["match"] else 0)
    if not regs:
        return None
    n = len(regs)
    return {"n": n, "top1": round(sum(matches) / n, 3),
            "mean_regret": round(sum(regs) / n, 3), "median_regret": round(st.median(regs), 3),
            "blunder_gt2": round(sum(r > 2 for r in regs) / n, 3),
            "blunder_gt5": round(sum(r > 5 for r in regs) / n, 3),
            "blunder_gt10": round(sum(r > 10 for r in regs) / n, 3)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results_dir")
    ap.add_argument("--out", default="measurement/level2/K4_PROBE_RESULTS.json")
    args = ap.parse_args(argv)
    rows = _load(Path(args.results_dir))
    if not rows:
        print("no results found")
        return 1

    modes = sorted({m for d in rows for m in d.get("gt", {})})
    ks = sorted({d["k_remaining"] for d in rows})
    sources = sorted({d.get("source_agent") or "?" for d in rows})
    agents = sorted({a for d in rows for m in d["gt"].values()
                     if m.get("solved") for a in m.get("per_agent", {})})

    report = {"n_positions": len(rows), "modes": modes, "ks": ks, "sources": sources,
              "agents": agents, "selection_bias": {}, "solved_by_source": {},
              "solve_cost": {}, "metrics": {}}

    # ---- (1a) solved-rate by source x K x mode ---------------------------- #
    for mode in modes:
        report["solved_by_source"][mode] = {}
        for src in sources:
            sr = {}
            for k in ks:
                pos = [d for d in rows if (d.get("source_agent") or "?") == src and d["k_remaining"] == k]
                solved = sum(1 for d in pos if d["gt"].get(mode, {}).get("solved"))
                sr[k] = {"solved": solved, "total": len(pos)}
            report["solved_by_source"][mode][src] = sr

    # ---- (1b) SELECTION BIAS: solved vs unsolved difficulty --------------- #
    for mode in modes:
        report["selection_bias"][mode] = {}
        for k in ks:
            kr = [d for d in rows if d["k_remaining"] == k]
            solved = [d for d in kr if d["gt"].get(mode, {}).get("solved")]
            unsolved = [d for d in kr if mode in d["gt"] and not d["gt"][mode].get("solved")]
            s_legal = [d["legal_n"] for d in solved if d.get("legal_n") is not None]
            u_legal = [d["legal_n"] for d in unsolved if d.get("legal_n") is not None]
            s_bag = [d["bag_size"] for d in solved if d.get("bag_size") is not None]
            u_bag = [d["bag_size"] for d in unsolved if d.get("bag_size") is not None]
            gap = (_med(s_legal) - _med(u_legal)) if (s_legal and u_legal) else None
            report["selection_bias"][mode][k] = {
                "n_solved": len(solved), "n_unsolved": len(unsolved),
                "solved_rate": round(len(solved) / len(kr), 3) if kr else None,
                "legal_n_med_solved": _med(s_legal), "legal_n_med_unsolved": _med(u_legal),
                "legal_n_max_solved": max(s_legal) if s_legal else None,
                "legal_n_max_unsolved": max(u_legal) if u_legal else None,
                "bag_med_solved": _med(s_bag), "bag_med_unsolved": _med(u_bag),
                "easy_bias_legal_n_gap": gap,  # unsolved harder (higher legal_n) => negative gap
            }

    # ---- (1c) solve cost on solved positions ------------------------------ #
    for mode in modes:
        report["solve_cost"][mode] = {}
        for k in ks:
            nodes = [d["gt"][mode]["nodes"] for d in rows
                     if d["gt"].get(mode, {}).get("solved") and "nodes" in d["gt"][mode]]
            secs = [d["gt"][mode]["secs"] for d in rows
                    if d["gt"].get(mode, {}).get("solved") and "secs" in d["gt"][mode]]
            kn = [d["gt"][mode]["nodes"] for d in rows if d["k_remaining"] == k
                  and d["gt"].get(mode, {}).get("solved") and "nodes" in d["gt"][mode]]
            ksec = [d["gt"][mode]["secs"] for d in rows if d["k_remaining"] == k
                    and d["gt"].get(mode, {}).get("solved") and "secs" in d["gt"][mode]]
            report["solve_cost"][mode][k] = {
                "nodes_med": _med(kn), "nodes_max": max(kn) if kn else None,
                "secs_med": _med(ksec), "secs_max": max(ksec) if ksec else None}

    # ---- (2) agent metrics: overall + by source --------------------------- #
    for mode in modes:
        report["metrics"][mode] = {"overall": {a: _agent_stats(rows, a, mode) for a in agents},
                                   "decision": {a: _agent_stats(rows, a, mode, True) for a in agents},
                                   "by_source": {}}
        for src in sources:
            sr = [d for d in rows if (d.get("source_agent") or "?") == src]
            report["metrics"][mode]["by_source"][src] = {a: _agent_stats(sr, a, mode) for a in agents}

    json.dump(report, open(args.out, "w"), indent=2)

    # ---- human-readable ---------------------------------------------------- #
    print(f"\n{len(rows)} positions | sources={sources} | agents={agents}")
    for mode in modes:
        print(f"\n##### MODE: {mode}  ({'PERFECT-INFO' if mode=='clairvoyant' else 'BAG-EXPECTATION'}) #####")
        print(" SELECTION BIAS (solved vs unsolved difficulty):")
        print(f"  {'K':>3}{'solv%':>7}{'nSolv':>6}{'nUns':>5}{'legalN med S/U':>16}{'legalN max S/U':>16}{'easyGap':>8}")
        for k in ks:
            b = report["selection_bias"][mode][k]
            print(f"  {k:>3}{(b['solved_rate'] or 0)*100:>6.0f}%{b['n_solved']:>6}{b['n_unsolved']:>5}"
                  f"{str(b['legal_n_med_solved'])+'/'+str(b['legal_n_med_unsolved']):>16}"
                  f"{str(b['legal_n_max_solved'])+'/'+str(b['legal_n_max_unsolved']):>16}"
                  f"{str(b['easy_bias_legal_n_gap']):>8}")
        print(" SOLVED-RATE BY SOURCE:")
        for src in sources:
            cells = " ".join(f"K{k}:{report['solved_by_source'][mode][src][k]['solved']}/"
                             f"{report['solved_by_source'][mode][src][k]['total']}" for k in ks)
            print(f"  {src:<18} {cells}")
        print(" SOLVE COST (solved positions):")
        for k in ks:
            c = report["solve_cost"][mode][k]
            print(f"  K{k}: nodes med={c['nodes_med']} max={c['nodes_max']}  secs med={c['secs_med']} max={c['secs_max']}")
        print(f" AGENT METRICS (overall):")
        print(f"  {'agent':14}{'n':>5}{'top1':>7}{'meanReg':>9}{'medReg':>8}{'>2':>6}{'>5':>6}{'>10':>6}")
        for a in agents:
            s = report["metrics"][mode]["overall"][a]
            if s:
                print(f"  {a:14}{s['n']:>5}{s['top1']:>7.3f}{s['mean_regret']:>9.2f}{s['median_regret']:>8.2f}"
                      f"{s['blunder_gt2']:>6.2f}{s['blunder_gt5']:>6.2f}{s['blunder_gt10']:>6.2f}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
