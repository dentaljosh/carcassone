"""Non-transitivity verdict from the clean-eval cells.

Builds the 2x2 (net x opponent-leaf) on the REPAIRED ruler and tests whether the
opponent-leaf change (v1 -> v2.7) moves different nets in OPPOSITE directions —
the claim that there is no universal "discount vs-HeuristicMCTS by ~X%".

For each net it pairs by (seed, seat) across its vs-v1 and vs-v2.7 cells (both use
the SAME 1e9 seed namespace, so the decks line up) and reports the WITHIN-NET
deck-paired leaf effect Delta = wr(vs v2.7) - wr(vs v1), with SE and z. A positive
Delta means v2.7 is the EASIER opponent for that net.

Cells (under --root):
  iter_11 : r2_iter11_vs_heurv2_7_s200 (v2.7)  vs  t1_iter11_vs_heurv1_s200 (v1)
  Stage-B : r3_stageb_iter01_vs_heurv2_7_s200   vs  t2_stageb_iter01_vs_heurv1_s200

Usage:
  python scripts/analyze_nontransitivity.py --root /mnt/c/carc-shared/clean_eval_runs
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from summarize_clean_eval import _load_games, _paired_stats

EVAL_ROOT_DEFAULT = "/mnt/c/carc-shared/clean_eval_runs"

NETS = [
    ("iter_11", "r2_iter11_vs_heurv2_7_s200", "t1_iter11_vs_heurv1_s200",
     {"v1_old": 25.2, "v2_7_old": 89.7}),
    ("Stage-B iter_01", "r3_stageb_iter01_vs_heurv2_7_s200", "t2_stageb_iter01_vs_heurv1_s200",
     {"v1_old": 86.9, "v2_7_old": 34.9}),
]


def _wr_to_elo(wr: float) -> float:
    if 0.0 < wr < 1.0:
        return 400.0 * math.log10(wr / (1 - wr))
    return math.copysign(800.0, wr - 0.5)


def _paired_leaf_effect(root: Path, v27_dir: str, v1_dir: str):
    """Deck-paired Delta = a(vs v2.7) - a(vs v1) keyed on (seed, seat)."""
    g27 = {(g["seed"], g["_seat"]): g["_a"] for g in _load_games(root / v27_dir)}
    g1 = {(g["seed"], g["_seat"]): g["_a"] for g in _load_games(root / v1_dir)}
    common = sorted(set(g27) & set(g1))
    if not common:
        return None
    diffs = [g27[k] - g1[k] for k in common]
    n = len(diffs)
    mean = sum(diffs) / n
    var = sum((x - mean) ** 2 for x in diffs) / (n - 1) if n > 1 else float("nan")
    se = math.sqrt(var / n) if var == var else float("nan")
    z = (mean / se) if se and se == se and se > 0 else float("nan")
    return {"n_paired": n, "mean_delta_wr": mean, "se": se, "z": z}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="analyze_nontransitivity")
    ap.add_argument("--root", type=Path, default=Path(EVAL_ROOT_DEFAULT))
    args = ap.parse_args(argv)

    print(f"\nNON-TRANSITIVITY 2x2 (clean ruler, root={args.root})\n")
    header = f"{'net':<18} {'vs heur-v1':>16} {'vs heur-v2.7':>16} {'Δ(v2.7−v1) wr':>22}"
    print(header)
    print("-" * len(header))

    signs = []
    rows = []
    for name, v27_dir, v1_dir, old in NETS:
        s27 = _paired_stats(_load_games(args.root / v27_dir)) if (args.root / v27_dir).is_dir() else None
        s1 = _paired_stats(_load_games(args.root / v1_dir)) if (args.root / v1_dir).is_dir() else None
        eff = _paired_leaf_effect(args.root, v27_dir, v1_dir)
        v1_s = f"{_wr_to_elo(s1['wr']):+.1f}±{s1['elo_sigma']:.0f}(n{s1['n']})" if s1 else "—"
        v27_s = f"{_wr_to_elo(s27['wr']):+.1f}±{s27['elo_sigma']:.0f}(n{s27['n']})" if s27 else "—"
        if eff:
            d_s = f"{eff['mean_delta_wr']:+.4f} z={eff['z']:.2f} (n{eff['n_paired']})"
            signs.append((name, eff["mean_delta_wr"], eff["z"]))
        else:
            d_s = "— (v1 cell not ready)"
        print(f"{name:<18} {v1_s:>16} {v27_s:>16} {d_s:>22}")
        rows.append((name, s1, s27, eff, old))

    print("\n(positive Δ ⇒ v2.7 is the EASIER opponent for that net)\n")
    print("Old contaminated v1 numbers for reference: iter_11 +25.2, Stage-B +86.9")

    if len(signs) == 2:
        (n1, d1, z1), (n2, d2, z2) = signs
        opp = (d1 > 0) != (d2 > 0)
        both_sig = abs(z1) >= 2 and abs(z2) >= 2
        print("\nVERDICT:")
        if opp and both_sig:
            print(f"  NON-TRANSITIVE CONFIRMED (clean): {n1} Δ={d1:+.4f} (z={z1:.2f}) and "
                  f"{n2} Δ={d2:+.4f} (z={z2:.2f}) have OPPOSITE signs, both ≥2σ.")
            print("  → No universal leaf discount; the opponent-leaf effect is agent-specific and sign-varying.")
        elif opp:
            print(f"  Opposite-sign (non-transitive) DIRECTION holds, but not both ≥2σ "
                  f"({n1} z={z1:.2f}, {n2} z={z2:.2f}). Report direction + σ; size up the weaker cell.")
        else:
            print(f"  SAME sign for both nets ({n1} Δ={d1:+.4f}, {n2} Δ={d2:+.4f}) — "
                  f"non-transitivity NOT supported on the clean ruler; revisit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
