"""Aggregate the Phase-3 clean-eval reruns into CLEAN_RESULTS.csv.

Reads each rerun dir's per-game JSON checkpoints (+ its manifest.json evaluator
block), computes deck-PAIRED winrate / elo / σ (the pairing halves variance vs an
unpaired count), and emits one self-describing row per rerun with full provenance
(leaf per side, checkpoint SHA, residual scale, runtime_verified, deck-hash count,
seed range). Also reports the residual value-head MARGINAL (scale-0.25 minus
scale-0) as a deck-paired difference, with a power note when |effect| is small.

Usage:
  python scripts/summarize_clean_eval.py --root /mnt/c/carc-shared/clean_eval_runs \
      --out clean_eval/CLEAN_RESULTS.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

EVAL_ROOT_DEFAULT = "/mnt/c/carc-shared/clean_eval_runs"


def _load_games(d: Path) -> list[dict]:
    games = []
    for p in sorted(d.glob("*.json")):
        if p.name == "manifest.json":
            continue
        try:
            g = json.load(open(p))
        except Exception:
            continue
        # normalize to side-A perspective: a_score in {1=win, 0.5=draw, 0=loss}
        if "won_by_a" in g:           # heur-vs-heur
            seat = g.get("a_player")
        elif "won_by_net" in g:       # net-vs-heur (A = net)
            seat = g.get("net_player")
            g["won_by_a"] = g["won_by_net"]
        else:
            continue
        g["_seat"] = seat
        if g.get("drew"):
            g["_a"] = 0.5
        else:
            g["_a"] = 1.0 if g.get("won_by_a") else 0.0
        games.append(g)
    return games


def _paired_stats(games: list[dict]) -> dict:
    """Deck-paired winrate/elo/σ from side-A perspective. Pairs the two seat
    orientations of each deck (seed); falls back to per-game if unpaired."""
    by_seed: dict[int, list[dict]] = {}
    for g in games:
        by_seed.setdefault(g["seed"], []).append(g)
    paired_scores = []          # one value per deck (or per game if unpaired)
    for seed, gs in by_seed.items():
        a_vals = [g["_a"] for g in gs]
        paired_scores.append(sum(a_vals) / len(a_vals))
    n = len(games)
    n_decks = len(paired_scores)
    w = sum(1 for g in games if g["_a"] == 1.0)
    d = sum(1 for g in games if g["_a"] == 0.5)
    losses = n - w - d
    avg_diff = sum(g.get("diff", 0) for g in games) / n if n else 0.0
    wr = sum(paired_scores) / n_decks if n_decks else 0.0
    # SE of the mean over paired-deck scores → properly credits pairing
    if n_decks > 1:
        var = sum((x - wr) ** 2 for x in paired_scores) / (n_decks - 1)
        se = math.sqrt(var / n_decks)
    else:
        se = float("nan")
    if 0.0 < wr < 1.0:
        elo = 400.0 * math.log10(wr / (1 - wr))
        elo_sig = (400.0 / math.log(10)) * se / (wr * (1 - wr)) if se == se else float("nan")
    else:
        elo = math.copysign(800.0, wr - 0.5)
        elo_sig = float("nan")
    decks = {g.get("deck_hash", "") for g in games}
    return {"n": n, "n_decks": n_decks, "W": w, "L": losses, "D": d,
            "wr": wr, "elo": elo, "elo_sigma": elo_sig, "avg_diff": avg_diff,
            "n_unique_decks": len(decks - {""})}


def _manifest_summary(d: Path) -> dict:
    m = d / "manifest.json"
    if not m.is_file():
        return {}
    try:
        ev = json.load(open(m)).get("evaluator", {})
    except Exception:
        return {}
    sides = ev.get("sides", [])
    a = sides[0] if sides else {}
    b = sides[1] if len(sides) > 1 else {}
    rv = ev.get("runtime_verified")
    return {
        "code_commit": (ev.get("code_commit") or "")[:10],
        "dirty": ev.get("dirty"),
        "a_side": a.get("side"), "a_leaf": a.get("leaf_name"),
        "a_agent": a.get("agent_class"),
        "a_ckpt_sha": (a.get("checkpoint_sha256") or "")[:12],
        "a_residual_scale": a.get("residual_scale"),
        "a_cap": a.get("cap"), "a_c_puct": a.get("c_puct"),
        "b_side": b.get("side"), "b_leaf": b.get("leaf_name"),
        "b_agent": b.get("agent_class"),
        "sims": a.get("sims"), "paired": a.get("paired"),
        "seed_range": a.get("seed_range"),
        "runtime_verified": (rv or {}).get("ok") if isinstance(rv, dict) else None,
    }


def _residual_marginal(root: Path):
    """Deck-paired (scale0.25 − scale0) A-winrate, using the SAME decks."""
    d0 = next(iter(root.glob("*residual_rs0_*")), None)
    d25 = next(iter(root.glob("*residual_rs025_*")), None)
    if not d0 or not d25:
        return None
    g0 = {(g["seed"], g["_seat"]): g["_a"] for g in _load_games(d0)}
    g25 = {(g["seed"], g["_seat"]): g["_a"] for g in _load_games(d25)}
    common = sorted(set(g0) & set(g25))
    if not common:
        return None
    diffs = [g25[k] - g0[k] for k in common]
    n = len(diffs)
    mean = sum(diffs) / n
    var = sum((x - mean) ** 2 for x in diffs) / (n - 1) if n > 1 else float("nan")
    se = math.sqrt(var / n) if var == var else float("nan")
    return {"n_paired": n, "mean_winrate_delta": mean, "se": se,
            "z": (mean / se) if se and se == se and se > 0 else float("nan")}


COLUMNS = ["rerun", "n", "n_decks", "n_unique_decks", "W", "L", "D", "wr", "elo",
           "elo_sigma", "avg_diff", "sims", "paired", "a_side", "a_agent", "a_leaf",
           "a_ckpt_sha", "a_residual_scale", "a_cap", "a_c_puct", "b_side", "b_agent",
           "b_leaf", "code_commit", "dirty", "runtime_verified", "seed_range"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="summarize_clean_eval")
    ap.add_argument("--root", type=Path, default=Path(EVAL_ROOT_DEFAULT))
    ap.add_argument("--out", type=Path, default=Path("clean_eval/CLEAN_RESULTS.csv"))
    args = ap.parse_args(argv)
    if not args.root.is_dir():
        print(f"no rerun root at {args.root}")
        return 1

    rows = []
    for d in sorted(p for p in args.root.iterdir() if p.is_dir()):
        games = _load_games(d)
        if not games:
            print(f"  {d.name}: (no games yet)")
            continue
        stats = _paired_stats(games)
        man = _manifest_summary(d)
        row = {"rerun": d.name, **stats, **man}
        rows.append(row)
        sig = row.get("elo_sigma")
        sig_s = f"±{sig:.0f}" if isinstance(sig, float) and sig == sig else "±?"
        print(f"  {d.name}: n={stats['n']} ({stats['n_decks']} decks) "
              f"{stats['W']}W/{stats['L']}L/{stats['D']}D  wr={stats['wr']:.3f}  "
              f"elo={stats['elo']:+.1f} {sig_s}  avg_diff={stats['avg_diff']:+.1f}  "
              f"rt_verified={man.get('runtime_verified')}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        wtr.writeheader()
        for r in rows:
            wtr.writerow(r)
    print(f"\nwrote {args.out} ({len(rows)} reruns)")

    marg = _residual_marginal(args.root)
    if marg:
        print(f"\nResidual value-head MARGINAL (scale0.25 − scale0, deck-paired, "
              f"n={marg['n_paired']}): Δwr={marg['mean_winrate_delta']:+.4f} "
              f"(SE {marg['se']:.4f}, z={marg['z']:.2f})")
        if abs(marg["z"]) < 2:
            print("  POWER NOTE: |z|<2 → the value-head marginal is not resolved at this n; "
                  "report as inconclusive and propose a top-up.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
