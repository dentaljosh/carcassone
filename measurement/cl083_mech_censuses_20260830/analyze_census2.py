#!/usr/bin/env python3
"""CENSUS 2 read-out: owner vs champion setup-abandonment. PREREG read rule applied.

Reads the `C2_<profile>.jsonl` rows emitted by `census2_followthrough.py` and emits
`CENSUS2.json`. Uncertainty is a GAME-CLUSTER bootstrap (games resampled with
replacement), matching the PREREG's "cluster-robust by GAME" -- reported for context
only: the PREREG read rule is on the SIGN of D, not on a z.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

WINDOWS = (6, 12, 20)
PRIMARY_N = 12
BOOT_REPS = 2000
BOOT_SEED = 20260830


def load(paths):
    setups, games = [], []
    for p in paths:
        for line in Path(p).read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            (games if r["row"] == "game" else setups).append(r)
    return setups, games


def rates(rows, N):
    """(#eligible, #abandoned, rate) for one row set at window N."""
    el = [r for r in rows if r[f"w{N}"]["eligible"]]
    ab = [r for r in el if r[f"w{N}"]["abandoned"]]
    return len(el), len(ab), (len(ab) / len(el) if el else None)


def block(rows, N):
    n_el, n_ab, rate = rates(rows, N)
    el = [r for r in rows if r[f"w{N}"]["eligible"]]
    return {
        "n_setups": len(rows), "n_eligible": n_el, "n_censored": len(rows) - n_el,
        "n_abandoned": n_ab, "abandonment_rate": rate,
        "mean_own_growth": (sum(r[f"w{N}"]["own_growth"] for r in el) / len(el)
                            if el else None),
        "opp_growth_rate": (sum(bool(r[f"w{N}"]["opp_growth"]) for r in el) / len(el)
                            if el else None),
        "finished_in_window_rate": (sum(bool(r[f"w{N}"]["finished_in_window"])
                                        for r in el) / len(el) if el else None),
        "still_open_at_end_rate": (sum(bool(r[f"w{N}"]["still_open_at_end"])
                                       for r in el) / len(el) if el else None),
    }


def contrast(setups, N, key=lambda r: True):
    rows = [r for r in setups if key(r)]
    own = [r for r in rows if r["seat"] == "owner"]
    ch = [r for r in rows if r["seat"] == "champion"]
    b_own, b_ch = block(own, N), block(ch, N)
    d = (None if (b_own["abandonment_rate"] is None or b_ch["abandonment_rate"] is None)
         else b_ch["abandonment_rate"] - b_own["abandonment_rate"])

    # ---- GAME-cluster bootstrap on D (context only; the read rule is on sign) ----
    by_game = defaultdict(list)
    for r in rows:
        by_game[r["game"]].append(r)
    gids = sorted(by_game)
    rng = random.Random(BOOT_SEED)
    boots = []
    for _ in range(BOOT_REPS):
        draw = [by_game[gids[rng.randrange(len(gids))]] for _ in range(len(gids))]
        flat = [r for g in draw for r in g]
        o = [r for r in flat if r["seat"] == "owner" and r[f"w{N}"]["eligible"]]
        c = [r for r in flat if r["seat"] == "champion" and r[f"w{N}"]["eligible"]]
        if not o or not c:
            continue
        ro = sum(r[f"w{N}"]["abandoned"] for r in o) / len(o)
        rc = sum(r[f"w{N}"]["abandoned"] for r in c) / len(c)
        boots.append(rc - ro)
    boots.sort()
    ci = ([boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots))]]
          if boots else None)
    return {"owner": b_own, "champion": b_ch, "D_champ_minus_owner": d,
            "D_ci95_gamecluster": ci, "n_game_clusters": len(gids),
            "n_boot_ok": len(boots)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    setups, games = load(a.inputs)
    out = {
        "schema": "carcassonne-cl083-census2-readout/v1",
        "prereg": "measurement/cl083_mech_censuses_20260830/PREREG.md",
        "judge_free": True,
        "coverage": {
            "n_games": len(games),
            "n_recon_failures": sum(1 for g in games if not g["recon_ok"]),
            "n_setups": len(setups),
            "by_profile": dict(sorted(
                {p: sum(1 for g in games if g["profile"] == p)
                 for p in {g["profile"] for g in games}}.items())),
            "setups_by_seat": dict(sorted(
                {s: sum(1 for r in setups if r["seat"] == s)
                 for s in {r["seat"] for r in setups}}.items())),
        },
        "PRIMARY_N": PRIMARY_N,
        "primary": contrast(setups, PRIMARY_N),
        "robustness_windows": {f"N{N}": contrast(setups, N) for N in WINDOWS},
        "by_class": {c: contrast(setups, PRIMARY_N, lambda r, c=c: r["cls"] == c)
                     for c in ("city", "road")},
        "by_rules_profile": {
            p: contrast(setups, PRIMARY_N, lambda r, p=p: r["rules_profile"] == p)
            for p in sorted({r["rules_profile"] for r in setups})},
        "by_budget_epoch": {
            str(b): contrast(setups, PRIMARY_N,
                             lambda r, b=b: (r["sims_effective"],
                                             r["k_dets_effective"]) == b)
            for b in sorted({(r["sims_effective"], r["k_dets_effective"])
                             for r in setups}, key=str)},
    }

    d = out["primary"]["D_champ_minus_owner"]
    n_ch = out["primary"]["champion"]["n_eligible"]
    if d is None:
        verdict = "VOID (no eligible setups on one seat)"
    elif d <= 0:
        verdict = "CF-M1 KILLED (D <= 0: champion abandons no more than the owner)"
    elif n_ch < 20:
        verdict = "CF-M1 NOT KILLED (FRAGILE: <20 eligible champion setups)"
    else:
        verdict = "CF-M1 NOT KILLED (D > 0: the signature exists in the archive)"
    out["VERDICT"] = verdict
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({"D": d, "owner_rate": out["primary"]["owner"]["abandonment_rate"],
                      "champ_rate": out["primary"]["champion"]["abandonment_rate"],
                      "ci": out["primary"]["D_ci95_gamecluster"],
                      "VERDICT": verdict}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
