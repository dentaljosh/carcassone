#!/usr/bin/env python3
"""Phase 3 finalize — read the residual pilot per-game jsons, recompute the paired
verdict (+ by-seat split), write FULLGAME_PILOT_RESULTS.csv. Pure offline."""
from __future__ import annotations
import csv, glob, json, math, os

D = "/mnt/c/carc-shared/spm_residual/resid0.25__vs__resid0.0_b360_n200"
SPM = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "measurement", "search_policy_mixing")


def load(d):
    return [json.load(open(p)) for p in glob.glob(os.path.join(d, "seed*.json"))]


def paired_z(results):
    by_seed = {}
    for r in results:
        by_seed.setdefault(r["seed"], {})[r["a_seat"]] = r["diff"]
    ds = [(v[0] + v[1]) / 2.0 for v in by_seed.values() if 0 in v and 1 in v]
    if len(ds) < 2:
        return None, None, 0
    mean = sum(ds) / len(ds)
    var = sum((d - mean) ** 2 for d in ds) / (len(ds) - 1)
    se = math.sqrt(var / len(ds))
    return mean, (mean / se if se > 0 else float("nan")), len(ds)


def summ(results, tag):
    n = len(results)
    w = sum(1 for r in results if r["won_by_a"])
    d = sum(1 for r in results if r["drew"])
    L = n - w - d
    wr = (w + 0.5 * d) / n
    avg = sum(r["diff"] for r in results) / n
    elo = 400 * math.log10(wr / (1 - wr)) if 0 < wr < 1 else float("nan")
    mean_d, z, npair = paired_z(results)
    return {"tag": tag, "n": n, "W": w, "D": d, "L": L, "winrate": round(wr, 4),
            "avg_diff": round(avg, 3), "elo": round(elo, 1),
            "paired_margin": round(mean_d, 3) if mean_d is not None else None,
            "paired_z": round(z, 3) if z is not None else None, "n_paired": npair}


def main():
    res = load(D)
    print(f"loaded {len(res)} games from {D}")
    overall = summ(res, "iter8@resid0.25_vs_resid0_OVERALL")
    seat0 = summ([r for r in res if r["a_seat"] == 0], "resid0.25_as_seat0")
    seat1 = summ([r for r in res if r["a_seat"] == 1], "resid0.25_as_seat1")
    rows = [overall, seat0, seat1]
    for r in rows:
        print(json.dumps(r))

    # write CSV: residual pilot rows + reused full-game facts (for the consolidated table)
    reused = [
        {"tag": "REUSED:HYBRID_K8_vs_iter8", "n": 400, "elo": 20.9, "paired_margin": 1.31, "paired_z": 5.79, "winrate": "", "W": "", "D": "", "L": "", "avg_diff": "", "n_paired": ""},
        {"tag": "REUSED:HYBRID_K8_vs_heur3200", "n": 200, "elo": -19.1, "paired_margin": -0.76, "paired_z": -0.51, "winrate": "", "W": "", "D": "", "L": "", "avg_diff": "", "n_paired": ""},
        {"tag": "REUSED:iter8_vs_heur800", "n": 400, "elo": 58.7, "paired_margin": "", "paired_z": "", "winrate": "", "W": "", "D": "", "L": "", "avg_diff": "", "n_paired": ""},
        {"tag": "REUSED:iter8_vs_heur3200", "n": 200, "elo": -28.7, "paired_margin": "", "paired_z": -0.70, "winrate": "", "W": "", "D": "", "L": "", "avg_diff": "", "n_paired": ""},
    ]
    cols = ["tag", "n", "W", "D", "L", "winrate", "avg_diff", "elo", "paired_margin", "paired_z", "n_paired"]
    with open(os.path.join(SPM, "FULLGAME_PILOT_RESULTS.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows + reused:
            w.writerow({c: r.get(c, "") for c in cols})
    print(f"\nwrote FULLGAME_PILOT_RESULTS.csv ({len(rows)} pilot rows + {len(reused)} reused facts)")

    # verdict string for the docs
    z = overall["paired_z"]
    verdict = ("resid0.25 BEATS resid0" if (z and z > 1.5) else
               "resid0.25 LOSES to resid0" if (z and z < -1.5) else
               "TIE (|z|<1.5): residual full-game-neutral")
    print(f"\nVERDICT: {verdict}  (overall paired margin {overall['paired_margin']} pts/game, z={z}, elo {overall['elo']})")


if __name__ == "__main__":
    main()
