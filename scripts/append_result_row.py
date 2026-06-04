#!/usr/bin/env python3
"""Append ONE provenance-stamped row to experiments/results.csv from a run dir.

Reads <dir>/manifest.json (game, code_rev, resolved config — written by the eval
harness via carcassonne_ai.run_manifest) and pools <dir>/*.json game results, so the
row's `game`/`code_rev`/sims/ckpt come FROM the run, not hand-typed -> a row can never
drift from the era/code that produced it (the +181.7-River vs +25.2-base trap).

Currently supports the eval_net_vs_heuristic GameResult schema (won_by_net/drew).

Usage:
  python scripts/append_result_row.py --dir <run_dir> --exp-id <id> \
      [--confidence high|medium|low] [--note "..."] [--date YYYY-MM-DD] [--dry-run] [--force]
"""
import argparse
import csv
import json
import math
from pathlib import Path

CSV = Path(__file__).resolve().parent.parent / "experiments" / "results.csv"


def pool(d: Path):
    n = w = dr = 0
    diffs = []
    for jf in d.glob("*.json"):
        if jf.name == "manifest.json":
            continue
        try:
            r = json.loads(jf.read_text())
        except Exception:
            continue
        if "won_by_net" not in r:
            continue  # not an eval_net result
        n += 1
        if r.get("drew"):
            dr += 1
        elif r.get("won_by_net"):
            w += 1
        if "diff" in r:
            diffs.append(r["diff"])
    losses = n - w - dr
    return n, w, losses, dr, (sum(diffs) / len(diffs) if diffs else None)


def elo_sigma(w, l, d, n):
    wr = (w + 0.5 * d) / n
    if 0 < wr < 1:
        elo = 400.0 * math.log10(wr / (1 - wr))
        wr_sig = math.sqrt(wr * (1 - wr) / n)
        sig = (400.0 / math.log(10)) * wr_sig / (wr * (1 - wr))
    else:
        elo, sig = math.copysign(800.0, wr - 0.5), float("nan")
    return round(elo, 1), round(sig, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--exp-id", required=True)
    ap.add_argument("--confidence", default="medium")
    ap.add_argument("--note", default="")
    ap.add_argument("--date", default=None, help="default = manifest utc date")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="append even if exp_id exists")
    args = ap.parse_args()

    man = json.loads((args.dir / "manifest.json").read_text())
    cfg = man["config"]
    leaf = man.get("leaf_env", {})
    n, w, l, d, avg = pool(args.dir)
    if n == 0:
        raise SystemExit(f"no eval_net game json in {args.dir}")
    elo, sig = elo_sigma(w, l, d, n)
    cap = leaf.get("CARCASSONNE_V25_CAP", "12")
    vb = float(leaf.get("CARCASSONNE_V25_VALUE_BLEND", "0") or "0")
    new_var = cfg.get("new_var", "v2_7") + (f"+vb{vb}" if vb > 0 else "")
    date = args.date or man.get("utc", "")[:10]

    row = {
        "exp_id": args.exp_id, "date": date, "game": man["game"],
        "code_rev": man["code_rev"], "n": n,
        "new_ckpt": cfg.get("checkpoint", ""), "new_c": cfg.get("c_puct", ""),
        "new_cap": cap, "new_var": new_var, "new_sims": cfg.get("sims", ""),
        "old_ckpt": cfg.get("opponent", "HeuristicMCTS"), "old_c": cfg.get("c_puct", ""),
        "old_cap": cap, "old_var": "v2_7", "old_sims": cfg.get("heur_sims", ""),
        "W": w, "L": l, "D": d, "elo": elo, "sigma": sig,
        "avg_diff": round(avg, 1) if avg is not None else "",
        "src_dir": str(args.dir), "confidence": args.confidence, "note": args.note,
    }

    fields = list(csv.DictReader(open(CSV)).fieldnames)
    existing = {r["exp_id"] for r in csv.DictReader(open(CSV))}
    if args.exp_id in existing and not args.force:
        raise SystemExit(f"exp_id '{args.exp_id}' already in results.csv (use --force)")

    print("ROW:", {k: row[k] for k in ("exp_id", "date", "game", "code_rev", "n",
                                       "new_sims", "old_sims", "W", "L", "D", "elo", "sigma")})
    if args.dry_run:
        print("(dry-run; not written)")
        return
    with open(CSV, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=fields).writerow(row)
    print(f"appended '{args.exp_id}' to {CSV}")


if __name__ == "__main__":
    main()
