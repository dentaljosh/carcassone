#!/usr/bin/env python3
"""C-cheap v2 — CRN-paired Δ verdict: the fair-net arm vs the CACHED fair baseline.

WHY: eval_fair_puct.py's `fair` (baseline) and `fair-net` (C-cheap) arms play the
SAME fixed rung on the SAME decks (same seed → same pre-shuffled deck → common
random numbers). So we only ever need to RUN the fair-net arm — this script joins
its per-game JSONs against the already-cached `fair` baseline JSONs and computes the
CRN-paired Δ, cancelling the (large) deck-to-deck variance instead of re-running the
baseline.

It reads the eval_fair_puct GameResult JSONs (``seed<seed:012d>_a<a_seat>.json``,
fields: seed, a_seat, diff = champion − rung, won_by_champ, drew) from both arms and
reports:
  * per-arm winrate / elo vs the rung, over the COMMON game set (apples-to-apples);
  * the CRN-paired Δ on the per-DECK seat-balanced margin
    (deck margin = mean over a_seat of diff; Δ = fair-net − fair), with a paired z;
  * fair-net elo − fair elo.

Baseline default: /mnt/c/carc-shared/fair_ladder_s2752_vs_h800_k2 (n=200, band 15e9).

Usage:
  .venv/bin/python scripts/classical_search/crn_delta_fairnet.py \
      --fairnet-dir /mnt/c/carc-shared/classical_search/<fair-net out dir> \
      [--baseline-dir /mnt/c/carc-shared/fair_ladder_s2752_vs_h800_k2] \
      [--out <summary.json>]
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

DEFAULT_BASELINE = "/mnt/c/carc-shared/fair_ladder_s2752_vs_h800_k2"


def _load_games(d: Path) -> dict[tuple[int, int], dict]:
    """Map (seed, a_seat) -> the game record for every seed*_a*.json in `d`."""
    out: dict[tuple[int, int], dict] = {}
    for p in sorted(d.glob("seed*_a*.json")):
        try:
            r = json.load(open(p))
        except Exception:
            continue
        if "seed" not in r or "a_seat" not in r:
            continue
        out[(int(r["seed"]), int(r["a_seat"]))] = r
    return out


def _wr_elo(records) -> tuple[int, int, int, int, float, float]:
    """(n, W, D, L, winrate, elo) for a champion-vs-rung set (elo clamped at ±800)."""
    n = len(records)
    w = sum(1 for r in records if r.get("won_by_champ"))
    d = sum(1 for r in records if r.get("drew"))
    losses = n - w - d
    wr = (w + 0.5 * d) / n if n else float("nan")
    if n and 0.0 < wr < 1.0:
        elo = 400.0 * math.log10(wr / (1.0 - wr))
    else:
        elo = math.copysign(800.0, wr - 0.5) if n else float("nan")
    return n, w, d, losses, wr, elo


def _deck_margins(games: dict[tuple[int, int], dict]) -> dict[int, float]:
    """seed -> seat-balanced margin = mean over a_seat of diff (needs BOTH seats)."""
    by_seed: dict[int, dict[int, float]] = {}
    for (seed, a_seat), r in games.items():
        by_seed.setdefault(seed, {})[a_seat] = float(r["diff"])
    return {s: (v[0] + v[1]) / 2.0 for s, v in by_seed.items() if 0 in v and 1 in v}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="crn_delta_fairnet")
    ap.add_argument("--fairnet-dir", type=Path, required=True,
                    help="dir of fair-net arm seed*_a*.json (eval_fair_puct --info fair-net)")
    ap.add_argument("--baseline-dir", type=Path, default=Path(DEFAULT_BASELINE),
                    help=f"cached `fair` baseline JSONs (default {DEFAULT_BASELINE})")
    ap.add_argument("--out", type=Path, default=None, help="optional summary.json path")
    args = ap.parse_args(argv)

    fn = _load_games(args.fairnet_dir)
    base = _load_games(args.baseline_dir)
    if not fn:
        raise SystemExit(f"no fair-net games under {args.fairnet_dir}")
    if not base:
        raise SystemExit(f"no baseline games under {args.baseline_dir}")

    # COMMON game set (both arms played this exact (seed, a_seat)).
    common = sorted(set(fn) & set(base))
    if not common:
        raise SystemExit("no (seed, a_seat) overlap between the fair-net and baseline dirs")
    fn_common = [fn[k] for k in common]
    base_common = [base[k] for k in common]

    n_fn, w_fn, d_fn, l_fn, wr_fn, elo_fn = _wr_elo(fn_common)
    n_b, w_b, d_b, l_b, wr_b, elo_b = _wr_elo(base_common)

    # CRN-paired Δ on the per-deck seat-balanced margin (deck variance cancels).
    fn_dm = _deck_margins({k: fn[k] for k in common})
    base_dm = _deck_margins({k: base[k] for k in common})
    decks = sorted(set(fn_dm) & set(base_dm))
    deltas = [fn_dm[s] - base_dm[s] for s in decks]

    mean_d = z = None
    if len(deltas) >= 2:
        mean_d = sum(deltas) / len(deltas)
        var = sum((x - mean_d) ** 2 for x in deltas) / (len(deltas) - 1)
        se = math.sqrt(var / len(deltas))
        z = (mean_d / se) if se > 0 else float("nan")

    print("=== CRN-Δ: fair-net vs cached fair baseline ===")
    print(f"fairnet-dir : {args.fairnet_dir}")
    print(f"baseline-dir: {args.baseline_dir}")
    print(f"common games (seed,a_seat): {len(common)}  |  paired decks (both seats): {len(decks)}")
    print(f"fair-net : {n_fn} games  {w_fn}W/{d_fn}D/{l_fn}L  wr={wr_fn:.3f}  elo={elo_fn:+.1f}")
    print(f"fair     : {n_b} games  {w_b}W/{d_b}D/{l_b}L  wr={wr_b:.3f}  elo={elo_b:+.1f}")
    print(f"elo(fair-net) - elo(fair) = {elo_fn - elo_b:+.1f}")
    if mean_d is not None:
        print(f"CRN paired Δ (seat-balanced deck margin, fair-net - fair): "
              f"{mean_d:+.3f} pts/deck   z = {z:+.2f}   (n_decks={len(decks)})")
        print("  gate (C_CHEAP_SPEC §4): promote iff the fair-net elo lead is >= +35 "
              "AND the paired Δ z is clearly > 0.")
    else:
        print("  (need >= 2 paired decks for a paired z)")

    if args.out:
        summ = {
            "fairnet_dir": str(args.fairnet_dir), "baseline_dir": str(args.baseline_dir),
            "n_common_games": len(common), "n_paired_decks": len(decks),
            "fairnet": {"n": n_fn, "W": w_fn, "D": d_fn, "L": l_fn, "wr": wr_fn, "elo": elo_fn},
            "fair": {"n": n_b, "W": w_b, "D": d_b, "L": l_b, "wr": wr_b, "elo": elo_b},
            "elo_diff_fairnet_minus_fair": elo_fn - elo_b,
            "crn_paired_delta_pts_per_deck": mean_d, "crn_paired_z": z,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        json.dump(summ, open(args.out, "w"), indent=2)
        print(f"[out] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
