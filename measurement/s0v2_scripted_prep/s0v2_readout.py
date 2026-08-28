#!/usr/bin/env python3
"""S0v2 TELEMETRY READ-OUT — the fire-rate ledger, and the census reconciliation.

⛔ SMOKE INSTRUMENT.  Companion to ``s0_signature.py`` (which is reused verbatim
and owns every counter the BARS are read against).  This script owns only the
things the census cannot see: what the plan module *tried*, what gated it, and
how the agent's own causal merge-fire count compares with the census's
global-union-find deliberate-invasion count (DESIGN.md §1.2).

Usage:
    s0v2_readout.py --games-dir <arm dir> --rows <rows.jsonl> [--label X]
                    [--out telemetry.json]
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


def _mean(xs):
    return (sum(xs) / len(xs)) if xs else float("nan")


def _sem(xs):
    if len(xs) < 2:
        return float("nan")
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1) / len(xs))


def load_games(games_dir: Path):
    out = []
    for p in sorted(games_dir.glob("seed*.json")):
        a = json.loads(p.read_text())
        a["_name"] = p.stem
        out.append(a)
    return out


def census_deliberate(rows_path: Path):
    """game id -> (deliberate invasions BY the candidate, contest onsets by it)."""
    by_game = defaultdict(list)
    for line in Path(rows_path).open():
        line = line.strip()
        if line:
            r = json.loads(line)
            by_game[r["game"]].append(r)
    out = {}
    for gid, grows in by_game.items():
        g = [r for r in grows if r["row"] == "game"][0]
        hp = int(g["human_player"])
        onsets = delib = 0
        for r in grows:
            if r["row"] != "contest" or r.get("invader") is None:
                continue
            if int(r["invader"]) != hp:
                continue
            onsets += 1
            if int(r.get("actor", -1)) == hp:
                delib += 1
        out[gid] = (delib, onsets)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games-dir", required=True)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    games = load_games(Path(args.games_dir))
    cen = census_deliberate(Path(args.rows))

    tel = Counter()
    per_game_merge, per_game_census, per_game_onsets = [], [], []
    fires = Counter()
    shares = defaultdict(list)
    costs = defaultdict(list)
    plan_reasons = Counter()
    elapsed, moves = [], []
    margins = []
    plan_started = plan_done = plan_aband = plan_open = 0

    for a in games:
        prov = a.get("s0v2") or {}
        t = prov.get("telemetry") or {}
        for k, v in t.items():
            if isinstance(v, (int,)) and not isinstance(v, bool):
                tel[k] += v
        per_game_merge.append(int(t.get("merge_fires", 0)))
        # stage_a_census keys its rows by the archive FILE NAME; be tolerant of
        # whether that carries the .json suffix.
        hit = cen.get(a["_name"])
        if hit is None:
            hit = cen.get(a["_name"] + ".json")
        if hit is None:
            raise SystemExit(f"no census rows for {a['_name']!r}; "
                             f"have e.g. {next(iter(cen), None)!r}")
        d, o = hit
        per_game_census.append(d)
        per_game_onsets.append(o)
        for f in prov.get("fires", []):
            fires[f["kind"]] += 1
            if "visit_share" in f:
                shares[f["kind"]].append(float(f["visit_share"]))
            if "leaf_cost" in f:
                costs[f["kind"]].append(float(f["leaf_cost"]))
        for pl in prov.get("plans", []):
            plan_started += 1
            if pl["status"] == "completed":
                plan_done += 1
            elif pl["status"] == "abandoned":
                plan_aband += 1
                plan_reasons[pl.get("reason") or "?"] += 1
            else:
                plan_open += 1
        elapsed.append(float(prov.get("elapsed_s", 0.0)))
        moves.append(int(prov.get("moves", 0)))
        margins.append(int(a["result"]["diff"]))

    n = len(games)
    out = {
        "label": args.label,
        "n_games": n,
        "margin_mean": _mean(margins), "margin_sem": _sem(margins),
        "census_deliberate_per_game": _mean(per_game_census),
        "census_deliberate_sem": _sem(per_game_census),
        "agent_merge_fires_per_game": _mean(per_game_merge),
        "agent_merge_fires_total": sum(per_game_merge),
        "census_deliberate_total": sum(per_game_census),
        "census_onsets_total": sum(per_game_onsets),
        "census_completion_rate": ((sum(per_game_census) / sum(per_game_onsets))
                                   if sum(per_game_onsets) else None),
        "reconciliation_agent_minus_census": sum(per_game_merge) - sum(per_game_census),
        "fires": dict(fires),
        "telemetry_totals": dict(tel),
        "plans_started": plan_started, "plans_completed": plan_done,
        "plans_abandoned": plan_aband, "plans_open_at_end": plan_open,
        "plan_completion_rate": (plan_done / plan_started) if plan_started else None,
        "plan_abandon_reasons": dict(plan_reasons),
        "visit_share": {k: {"n": len(v), "min": min(v), "median": sorted(v)[len(v) // 2],
                            "max": max(v)} for k, v in shares.items() if v},
        "leaf_cost": {k: {"n": len(v), "min": min(v), "median": sorted(v)[len(v) // 2],
                          "max": max(v)} for k, v in costs.items() if v},
        "worker_s_per_game": _mean(elapsed),
        "moves_per_game": _mean(moves),
        "note": ("worker_s_per_game is an UPPER BOUND: the box was shared. "
                 "agent merge fires use the CAUSAL detector; the census uses a "
                 "global union-find over the whole game (DESIGN.md §1.2)."),
    }

    print(f"=== S0v2 TELEMETRY {args.label} (n={n}) ===")
    print(f"margin                       {out['margin_mean']:+.2f} +- {out['margin_sem']:.2f}")
    print(f"census deliberate / game     {out['census_deliberate_per_game']:.3f} "
          f"+- {out['census_deliberate_sem']:.3f}")
    print(f"agent merge fires / game     {out['agent_merge_fires_per_game']:.3f} "
          f"(total {out['agent_merge_fires_total']} vs census "
          f"{out['census_deliberate_total']})")
    print(f"census onsets total          {out['census_onsets_total']} "
          f"-> deliberate/onset {out['census_completion_rate']}")
    print(f"fires                        {out['fires']}")
    print(f"plans started/completed      {plan_started}/{plan_done} "
          f"(rate {out['plan_completion_rate']}) abandoned {plan_aband} "
          f"{dict(plan_reasons)}")
    for k, v in out["visit_share"].items():
        print(f"  visit_share {k:9s} n={v['n']} min={v['min']:.3f} "
              f"med={v['median']:.3f} max={v['max']:.3f}")
    for k, v in out["leaf_cost"].items():
        print(f"  leaf_cost   {k:9s} n={v['n']} min={v['min']:.2f} "
              f"med={v['median']:.2f} max={v['max']:.2f}")
    print(f"telemetry totals             "
          f"{ {k: v for k, v in sorted(out['telemetry_totals'].items()) if v} }")
    print(f"worker-s/game (UPPER BOUND)  {out['worker_s_per_game']:.1f}  "
          f"moves/game {out['moves_per_game']:.1f}")

    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=2, sort_keys=True))
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
