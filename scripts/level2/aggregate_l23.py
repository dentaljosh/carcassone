"""Aggregate the L2-3 endgame-regret per-position results into the verdict metrics.

Reads the per-position JSON files written by endgame_regret.py and reports, per
agent x GT-mode x K-bucket (Joshua #6):
  - top-1 agreement with the solver (fraction the agent's move is optimal)
  - mean / median regret (points lost vs optimal)
  - blunder rates: fraction with regret > 2, > 5, > 10 points
  - the above on ALL solved positions AND on DECISION positions (where the move
    matters, i.e. n_optimal < n_legal) for a sharper read
  - examples: the largest iter8 regret losses, and iter8's best "wins over the
    field" (iter8 optimal while the heuristics blunder)

Pure reader. Usage:
  python scripts/level2/aggregate_l23.py <RESULTS_DIR> [--out measurement/level2/L23_REGRET_RESULTS.json]
"""
from __future__ import annotations

import argparse
import json
import statistics as st
from pathlib import Path


def _load(results_dir: Path) -> list[dict]:
    out = []
    for fp in results_dir.glob("*.json"):
        if fp.name in ("L23_REGRET_RESULTS.json",):
            continue
        try:
            out.append(json.load(open(fp)))
        except Exception:
            pass
    return out


def _agent_stats(rows, agent, mode, decision_only):
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
    return {
        "n": n,
        "top1_agreement": round(sum(matches) / n, 4),
        "mean_regret": round(sum(regs) / n, 3),
        "median_regret": round(st.median(regs), 3),
        "blunder_gt2": round(sum(r > 2 for r in regs) / n, 4),
        "blunder_gt5": round(sum(r > 5 for r in regs) / n, 4),
        "blunder_gt10": round(sum(r > 10 for r in regs) / n, 4),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results_dir")
    ap.add_argument("--out", default="measurement/level2/L23_REGRET_RESULTS.json")
    args = ap.parse_args(argv)
    rows = _load(Path(args.results_dir))
    if not rows:
        print("no results found")
        return 1

    agents = sorted({a for d in rows for m in d["gt"].values()
                     if m.get("solved") for a in m.get("per_agent", {})})
    modes = sorted({m for d in rows for m in d["gt"]})
    ks = sorted({d["k_remaining"] for d in rows})

    # coverage: solved-rate per mode per K
    coverage = {}
    for mode in modes:
        coverage[mode] = {}
        for k in ks:
            kr = [d for d in rows if d["k_remaining"] == k]
            solved = sum(1 for d in kr if d["gt"].get(mode, {}).get("solved"))
            disc = sum(1 for d in kr if d["gt"].get(mode, {}).get("solved")
                       and d["gt"][mode].get("n_optimal", 0) < d["gt"][mode].get("n_legal", 1))
            coverage[mode][k] = {"positions": len(kr), "solved": solved, "decision": disc}

    out = {"n_positions": len(rows), "agents": agents, "modes": modes, "ks": ks,
           "coverage": coverage, "metrics": {}}
    for mode in modes:
        out["metrics"][mode] = {}
        for scope, decision_only in (("all", False), ("decision", True)):
            out["metrics"][mode][scope] = {}
            # overall
            out["metrics"][mode][scope]["overall"] = {
                a: _agent_stats(rows, a, mode, decision_only) for a in agents}
            # by K
            out["metrics"][mode][scope]["by_k"] = {}
            for k in ks:
                kr = [d for d in rows if d["k_remaining"] == k]
                out["metrics"][mode][scope]["by_k"][k] = {
                    a: _agent_stats(kr, a, mode, decision_only) for a in agents}

    # examples (clairvoyant decision positions): largest iter8 losses + wins-over-field
    def _i8(d, mode):
        g = d["gt"].get(mode, {})
        if not g.get("solved"):
            return None
        return g.get("per_agent", {}).get("iter8")
    emode = "clairvoyant" if "clairvoyant" in modes else modes[0]
    heur_keys = [a for a in agents if a.startswith("heur@")]
    losses, wins = [], []
    for d in rows:
        pa = _i8(d, emode)
        if not pa or pa.get("regret") is None:
            continue
        ident = {"seed": d["seed"], "ply": d["ply"], "k": d["k_remaining"],
                 "iter8_regret": pa["regret"], "iter8_move": pa["move"]}
        losses.append(ident)
        if pa["regret"] == 0:  # iter8 optimal — how badly did heuristics do here?
            g = d["gt"][emode]["per_agent"]
            heur_reg = [g[h]["regret"] for h in heur_keys if g.get(h) and g[h].get("regret") is not None]
            if heur_reg:
                wins.append({**ident, "max_heur_regret": max(heur_reg)})
    losses.sort(key=lambda x: -x["iter8_regret"])
    wins.sort(key=lambda x: -x["max_heur_regret"])
    out["examples"] = {"mode": emode, "largest_iter8_losses": losses[:8],
                       "iter8_wins_over_field": wins[:8]}

    json.dump(out, open(args.out, "w"), indent=2)

    # human-readable
    print(f"\n{len(rows)} positions | agents={agents}")
    for mode in modes:
        print(f"\n  coverage[{mode}] by K: " + " ".join(
            f"K{k}:{coverage[mode][k]['solved']}/{coverage[mode][k]['positions']}(dec {coverage[mode][k]['decision']})" for k in ks))
    for mode in modes:
        for scope in ("all", "decision"):
            print(f"\n=== {mode} / {scope} positions (overall) ===")
            print(f"  {'agent':14}{'n':>5}{'top1':>8}{'meanReg':>9}{'medReg':>8}{'>2':>7}{'>5':>7}{'>10':>7}")
            for a in agents:
                s = out["metrics"][mode][scope]["overall"][a]
                if s:
                    print(f"  {a:14}{s['n']:>5}{s['top1_agreement']:>8.3f}{s['mean_regret']:>9.2f}"
                          f"{s['median_regret']:>8.2f}{s['blunder_gt2']:>7.3f}{s['blunder_gt5']:>7.3f}{s['blunder_gt10']:>7.3f}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
