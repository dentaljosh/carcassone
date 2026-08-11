"""Asymmetric-compute v2.7 ladder — an out-of-lineage, non-saturating ODOMETER.

The flywheel needs a gauge that DOESN'T lie while strength climbs (DECISIONS
2026-06-04 regroup; the "+39 that was a dead tie on the independent ladder"
proved a same-lineage gauge can magnetize). This is the first odometer rung:

  Hold the NET at a fixed sim budget (e.g. 200) and sweep the HeuristicMCTS
  opponent's budget over {50, 200, 800, 3200, ...}. The win-rate falls as the
  heuristic searches deeper; the heur-sim budget where it crosses 50% is the
  net's **heuristic-equivalent search depth** — an absolute-ish strength unit
  that (a) lives OUTSIDE the training lineage (can't be overfit to), and
  (b) never saturates (you can always crank heuristic sims).

This wraps scripts/eval_net_vs_heuristic.py (which already does net@sims vs
HeuristicMCTS@heur-sims, paired, resumable, --shared-claim) once per rung and
interpolates the crossover in log2(heur_sims) space. Per-rung games are
checkpointed under <out-root>/<out-subdir>/h<heur_sims>/ so the ladder resumes.

Example:
  python -u scripts/ladder_asymmetric.py \
    --checkpoint /mnt/c/carc-shared/stage_b/ckpt/iter_01.pt \
    --net-sims 200 --heur-rungs 50,200,800,3200 --n 100 --paired \
    --out-root /mnt/c/carc-shared/ladder --out-subdir iter_01_s200
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

_WR_RE = re.compile(r"winrate\s+([0-9.]+)")
_ELO_RE = re.compile(r"ELO \(net vs heuristic\):\s*([+-][0-9.]+)\s*\(\+/-\s*([0-9.nan]+)")
_WDL_RE = re.compile(r"net:\s+(\d+)W\s*/\s*(\d+)D\s*/\s*(\d+)L")


def crossover_heur_sims(rungs: list[tuple[int, float]]) -> tuple[float, str]:
    """Given [(heur_sims, net_winrate)] return (crossover_heur_sims, note).

    Win-rate is expected to DECREASE as heur_sims grows (stronger opponent).
    Interpolate the heur_sims where wr=0.5 in log2 space (compute is geometric).
    """
    rs = sorted(rungs)
    if not rs:
        return (float("nan"), "no rungs")
    if all(wr > 0.5 for _, wr in rs):
        return (float("inf"), f"net beats heuristic at ALL rungs (>= top {rs[-1][0]})")
    if all(wr < 0.5 for _, wr in rs):
        return (0.0, f"net loses to heuristic at ALL rungs (<= bottom {rs[0][0]})")
    for (h0, w0), (h1, w1) in zip(rs, rs[1:]):
        if (w0 - 0.5) * (w1 - 0.5) <= 0 and w0 != w1:
            t = (0.5 - w0) / (w1 - w0)
            log_h = math.log2(h0) + t * (math.log2(h1) - math.log2(h0))
            return (2.0 ** log_h, f"crossover between {h0} and {h1}")
    return (float("nan"), "non-monotone win-rates — no clean crossover")


def run_rung(args, heur_sims: int) -> dict:
    """Run one eval_net_vs_heuristic rung as a subprocess; parse the summary."""
    # Fold the heur leaf into the dir so a v2_7 rung can never cache-hit stale v1 JSONs
    # at the same ckpt/sims/c/seed (the explicit --out-subdir bypasses eval's _hl_tag guard).
    sub = f"{args.out_subdir}/{args.heur_leaf}/h{heur_sims}"
    cmd = [
        PY, "-u", "scripts/eval_net_vs_heuristic.py",
        "--checkpoint", str(args.checkpoint),
        "--n", str(args.n),
        "--sims", str(args.net_sims),
        "--heur-sims", str(heur_sims),
        "--c-puct", str(args.c_puct),
        "--workers", str(args.workers),
        "--out-root", str(args.out_root),
        "--out-subdir", sub,
        "--seed-start", str(args.seed_start),
        "--heur-leaf", args.heur_leaf,   # R1-redux fix: match the agent's v2.7 leaf (was silently v1, the -29 artifact)
    ]
    if args.paired:
        cmd.append("--paired")
    if args.shared_claim:
        cmd += ["--shared-claim", "--claim-host", args.claim_host]
    env = dict(os.environ)
    # Production v2.7 leaf knobs (same as the gate / ladder rungs).
    env.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
    env.setdefault("CARCASSONNE_V25_CAP", "12")
    print(f"\n########## RUNG heur_sims={heur_sims} ##########", flush=True)
    proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    out = proc.stdout + "\n" + proc.stderr
    if proc.returncode != 0:
        sys.stderr.write(out)
        raise RuntimeError(f"rung heur_sims={heur_sims} failed (rc={proc.returncode})")
    wr_m = _WR_RE.search(out)
    elo_m = _ELO_RE.search(out)
    wdl_m = _WDL_RE.search(out)
    if not wr_m:
        sys.stderr.write(out)
        raise RuntimeError(f"could not parse winrate for heur_sims={heur_sims}")
    rec = {
        "heur_sims": heur_sims,
        "winrate": float(wr_m.group(1)),
        "elo": float(elo_m.group(1)) if elo_m else None,
        "elo_sigma": (float(elo_m.group(2)) if elo_m and elo_m.group(2) != "nan" else None),
        "W": int(wdl_m.group(1)) if wdl_m else None,
        "D": int(wdl_m.group(2)) if wdl_m else None,
        "L": int(wdl_m.group(3)) if wdl_m else None,
    }
    print(f"  -> wr={rec['winrate']:.3f}  elo={rec['elo']}", flush=True)
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ladder_asymmetric")
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--net-sims", type=int, default=200,
                    help="Fixed NeuralMCTS sims for the net side (the agent under test).")
    ap.add_argument("--heur-rungs", type=str, default="50,200,800,3200",
                    help="Comma-separated HeuristicMCTS sim budgets to sweep.")
    ap.add_argument("--n", type=int, default=100, help="Games per rung (paired → even).")
    ap.add_argument("--c-puct", type=float, default=3.0)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--paired", action="store_true",
                    help="Deck-pairing (each deck both colors) — ~halves variance.")
    ap.add_argument("--seed-start", type=int, default=1_000_000_000,
                    help="Deck seed base. Default 1e9 keeps decks above the self-play "
                         "namespace (iter*10_000+game) — old 800k floor collided with "
                         "trained-on decks at iter>=80 (outside-review A9). Sub-floor "
                         "needs --allow-selfplay-seeds.")
    ap.add_argument("--allow-selfplay-seeds", action="store_true",
                    help="bypass the clean-eval seed-floor guard (taints train/test).")
    ap.add_argument("--out-root", type=str, required=True)
    ap.add_argument("--out-subdir", type=str, required=True)
    ap.add_argument("--shared-claim", action="store_true",
                    help="3-box work-stealing (launch this on each box, same out-root).")
    ap.add_argument("--claim-host", type=str, default="local")
    ap.add_argument("--heur-leaf", choices=["v1", "v2_7"], default="v2_7",
                    help="HeuristicMCTS leaf. DEFAULT v2_7 = MATCH the agent's leaf (R1-redux fix). "
                         "Before 2026-06-08 this gauge passed no --heur-leaf, so it silently ran the "
                         "v1 leaf — the source of the bogus -29 heur@800 number (vs the matched +52.5). "
                         "Use v1 only for an explicit legacy-leaf comparison.")
    args = ap.parse_args(argv)

    if not args.allow_selfplay_seeds:
        from carcassonne_ai import eval_provenance as ep
        ep.assert_clean_eval_seed_range(args.seed_start, args.n)

    rungs = [int(x) for x in args.heur_rungs.split(",") if x.strip()]
    results = [run_rung(args, h) for h in rungs]

    pairs = [(r["heur_sims"], r["winrate"]) for r in results]
    cross, note = crossover_heur_sims(pairs)

    print("\n=== ASYMMETRIC v2.7 LADDER ===")
    print(f"net: {args.checkpoint.name} @ sims={args.net_sims}, n={args.n}"
          f"{' paired' if args.paired else ''}")
    print(f"{'heur_sims':>10}  {'winrate':>8}  {'elo':>8}")
    for r in results:
        elo_s = f"{r['elo']:+.1f}" if r["elo"] is not None else "   n/a"
        print(f"{r['heur_sims']:>10}  {r['winrate']:>8.3f}  {elo_s:>8}")
    if math.isinf(cross):
        print(f"\nHEURISTIC-EQUIVALENT DEPTH: > {rungs[-1]} heur-sims ({note})")
    elif cross == 0.0:
        print(f"\nHEURISTIC-EQUIVALENT DEPTH: < {rungs[0]} heur-sims ({note})")
    elif math.isnan(cross):
        print(f"\nHEURISTIC-EQUIVALENT DEPTH: undetermined ({note})")
    else:
        print(f"\nHEURISTIC-EQUIVALENT DEPTH: ~{cross:.0f} heur-sims "
              f"(net@{args.net_sims} ≈ HeuristicMCTS@{cross:.0f}) — {note}")

    # Persist a self-describing summary next to the rung dirs.
    summ_dir = Path(args.out_root) / args.out_subdir
    summ_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "checkpoint": str(args.checkpoint),
        "net_sims": args.net_sims,
        "n": args.n,
        "paired": args.paired,
        "c_puct": args.c_puct,
        "rungs": results,
        "crossover_heur_sims": (None if (math.isinf(cross) or math.isnan(cross)) else cross),
        "crossover_note": note,
    }
    (summ_dir / "ladder.json").write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {summ_dir / 'ladder.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
