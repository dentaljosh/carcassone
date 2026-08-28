#!/usr/bin/env python3
"""E4 CONTINUATION PRICING — the pre-registered readout.

The estimator, stated before any outcome exists:

  * a PLY's price is the mean of its CRN worlds' `delta_pts_mover` (each world
    is one paired game-outcome difference, in TRUE final-score points);
  * a STRATUM's price is the unweighted mean over its plies, with a
    CLUSTER-ROBUST standard error clustered on GAME — 91 plies live in 38
    games, so treating plies as independent draws would understate the SE;
  * the PRIMARY pre-registered contrast is `invasion - control`. Both arms are
    DIVERGENT plies, so the contrast asks the only interesting question: is a
    champion-divergence at an invasion ply worth more than a
    champion-divergence at an ordinary ply? Games contribute plies to BOTH
    arms, so the contrast's SE is computed from per-cluster influence
    contributions of the DIFFERENCE, which de-correlates a shared game instead
    of pretending independence;
  * `defense` and `farm_capture` are read SEPARATELY, never pooled into the
    primary contrast. `defense` plies are the champion's own moves (`actor ==
    1`), so their price is the cost of the champion's non-defense.

No judged quantity appears anywhere: every number here is a difference of
REALIZED final scores.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
from pathlib import Path


def collapse_worlds(rows):
    """(game, ply) -> one priced ply, the mean over its landed CRN worlds."""
    by = collections.OrderedDict()
    for r in rows:
        by.setdefault((r["game"], r["ply"]), []).append(r)
    out = []
    for (game, ply), rs in by.items():
        ok = [x for x in rs if (x.get("pair") or {}).get("status") == "OK"]
        void = [x for x in rs if (x.get("pair") or {}).get("status") != "OK"]
        h = rs[0]
        rec = {"game": game, "ply": ply, "stratum": h["stratum"],
               "actor": int(h["actor"]), "k": h.get("k"),
               "ply_frac": h.get("ply_frac"),
               "m_worlds_ok": len(ok), "m_worlds_void": len(void),
               "void_reasons": sorted({(x.get("pair") or {}).get("reason")
                                       for x in void} - {None}),
               "price": (statistics.fmean(x["pair"]["delta_pts_mover"] for x in ok)
                         if ok else None),
               "world_deltas": [x["pair"]["delta_pts_mover"] for x in ok]}
        out.append(rec)
    return out


def _influence(plies, sign=1.0):
    """Per-game influence contributions of the mean (the delta-method pieces)."""
    n = len(plies)
    if n == 0:
        return {}, 0.0
    mu = statistics.fmean(p["price"] for p in plies)
    contrib = collections.defaultdict(float)
    for p in plies:
        contrib[p["game"]] += sign * (p["price"] - mu) / n
    return dict(contrib), mu


def cluster_stats(plies):
    """Mean + SE clustered on GAME. `plies` need only `game` and `price`."""
    plies = [p for p in plies if p.get("price") is not None]
    n = len(plies)
    if n == 0:
        return {"n": 0, "n_clusters": 0, "mean": None, "se": None, "z": None}
    contrib, mu = _influence(plies)
    g = len(contrib)
    var = sum(v * v for v in contrib.values())
    if g > 1:
        var *= g / (g - 1.0)                 # finite-cluster correction
    se = math.sqrt(var)
    return {"n": n, "n_clusters": g, "mean": mu, "se": se,
            "z": (mu / se if se > 0 else None),
            "total": mu * n,
            "sd_plies": (statistics.stdev([p["price"] for p in plies])
                         if n > 1 else None)}


def contrast(a, b):
    """`mean(a) - mean(b)` with a cluster-robust SE that shares game clusters.

    Each game's influence on the DIFFERENCE is its influence on mean(a) minus
    its influence on mean(b). A game contributing to both arms therefore has
    its two contributions cancel to the extent they agree — which is the point:
    a shared game is a paired, not an independent, observation.
    """
    a = [p for p in a if p.get("price") is not None]
    b = [p for p in b if p.get("price") is not None]
    if not a or not b:
        return {"n_a": len(a), "n_b": len(b), "diff": None, "se": None, "z": None}
    ca, ma = _influence(a, 1.0)
    cb, mb = _influence(b, -1.0)
    keys = set(ca) | set(cb)
    var = sum((ca.get(k, 0.0) + cb.get(k, 0.0)) ** 2 for k in keys)
    g = len(keys)
    if g > 1:
        var *= g / (g - 1.0)
    se = math.sqrt(var)
    return {"n_a": len(a), "n_b": len(b), "mean_a": ma, "mean_b": mb,
            "diff": ma - mb, "se": se, "z": (ma - mb) / se if se > 0 else None,
            "n_clusters": g, "n_shared_clusters": len(set(ca) & set(cb))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--units", nargs="+", required=True,
                    help="directories of unit_*.json (one per box)")
    ap.add_argument("--targets", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows, files = [], []
    for d in args.units:
        for f in sorted(Path(d).glob("unit_*.json")):
            files.append(str(f))
            rows.append(json.loads(f.read_text()))
    targets = [json.loads(l) for l in Path(args.targets).open()]
    want = {(t["game"], int(t["ply"])) for t in targets}
    stray = {(r["game"], r["ply"]) for r in rows} - want
    if stray:
        raise SystemExit(f"units outside the frozen target set: {sorted(stray)[:5]}")

    plies = collapse_worlds(rows)
    priced = [p for p in plies if p["price"] is not None]
    by_s = collections.defaultdict(list)
    for p in priced:
        by_s[p["stratum"]].append(p)

    out = {
        "n_unit_files": len(files),
        "n_units": len(rows),
        "n_target_plies": len(want),
        "n_plies_with_units": len(plies),
        "n_plies_priced": len(priced),
        "n_plies_missing": sorted(want - {(p["game"], p["ply"]) for p in plies}),
        "worlds": {
            "requested_per_ply": max((p["m_worlds_ok"] + p["m_worlds_void"]
                                      for p in plies), default=0),
            "ok": sum(p["m_worlds_ok"] for p in plies),
            "void": sum(p["m_worlds_void"] for p in plies),
            "void_reasons": dict(collections.Counter(
                r for p in plies for r in p["void_reasons"])),
        },
        "arm_status": dict(collections.Counter(
            a.get("status") for r in rows for a in (r.get("arms") or {}).values())),
        "by_stratum": {s: {**cluster_stats(v),
                           "mean_m_worlds_ok": round(
                               statistics.fmean(p["m_worlds_ok"] for p in v), 2)}
                       for s, v in sorted(by_s.items())},
        "PRIMARY_invasion_minus_control": contrast(by_s.get("invasion", []),
                                                   by_s.get("control", [])),
        "secondary": {
            "farm_capture_minus_control": contrast(by_s.get("farm_capture", []),
                                                   by_s.get("control", [])),
            "defense_read_separately": cluster_stats(by_s.get("defense", [])),
        },
        "descriptive": {
            "followup_agrees_with_archive_rate": (
                round(statistics.fmean(
                    [1.0 if r.get("followup_agrees_with_archive") else 0.0
                     for r in rows
                     if r.get("followup_agrees_with_archive") is not None]), 4)
                if any(r.get("followup_agrees_with_archive") is not None
                       for r in rows) else None),
            "mean_s_per_decision": round(statistics.fmean(
                [a["s_per_decision"] for r in rows
                 for a in (r.get("arms") or {}).values()
                 if a.get("s_per_decision")]), 4) if rows else None,
            "mean_arm_s": round(statistics.fmean(
                [a["arm_s"] for r in rows for a in (r.get("arms") or {}).values()
                 if a.get("arm_s")]), 2) if rows else None,
            "budget_notes": dict(collections.Counter(
                str(r.get("budget_note")) for r in rows)),
            "profiles": dict(collections.Counter(r["profile"] for r in rows)),
        },
        "plies": sorted(priced, key=lambda p: (p["stratum"], p["game"], p["ply"])),
        "caveat": "Every price is a difference of REALIZED final scores over "
                  "CRN-paired continuations under production-champion play. No "
                  "judge, no evaluation function, no search score. It prices the "
                  "TARGET PLY ONLY: every later move, including the meeple "
                  "follow-up, is the champion's.",
    }
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "plies"}, indent=1))


if __name__ == "__main__":
    main()
