"""Summarize the 4-lever value-loss sequencer (scripts/lever_sequencer.sh).

Two lever families produce a knob-curve vs HeuristicMCTS@200, each judged by the
MARGINAL (knob>0 elo − knob=0 elo) — the only confound-free measure of whether
the value head is an ASSET (knob=0 = pure v2.7 leaf with that net's priors; the
policy baseline cancels out). Levers:

  Lever 1 (residual):  eval_residual_s{00,025,05}   knob = CARCASSONNE_V25_RESIDUAL_SCALE
  Lever 2 (centered):  eval_centered_b{0,05,10}     knob = CARCASSONNE_V25_VALUE_BLEND

Reports each curve, the marginal with its sigma + z (so a low-n spike can't be
mistaken for a win — the STEP B.1 a30t03 lesson), the gate verdict, and writes
$OUT/VERDICT.txt (WINNER=<l1|l2|none>) for the sequencer to branch on.

Usage:
  python scripts/lever_summary.py --out /mnt/c/carc-shared/lever_seq
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path


def _elo(w: int, d: int, n: int) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    wr = (w + 0.5 * d) / n
    if 0 < wr < 1:
        elo = 400.0 * math.log10(wr / (1 - wr))
        sig = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
    else:
        elo, sig = math.copysign(800.0, wr - 0.5), float("nan")
    return elo, sig


def _dir_record(d: Path) -> tuple[int, int, int]:
    w = dd = n = 0
    for jf in d.glob("*seed*.json"):
        try:
            r = json.loads(jf.read_text())
        except Exception:
            continue
        n += 1
        if r.get("won_by_net"):
            w += 1
        elif r.get("drew"):
            dd += 1
    return w, dd, n


# lever -> (subdir prefix, [(knob_tag, label, is_baseline)])
LEVERS = {
    "l1": ("eval_residual_", [("s0", "scale0", True), ("s025", "scale0.25", False),
                              ("s05", "scale0.5", False)]),
    "l2": ("eval_centered_", [("b0", "λ0", True), ("b05", "λ0.5", False),
                              ("b10", "λ1.0", False)]),
}
LEVER_NAME = {"l1": "Lever 1 (residual)", "l2": "Lever 2 (centered)"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--min-n-baseline", type=int, default=150,
                    help="Require the knob=0 baseline eval to reach this n before "
                         "trusting the marginal (else mark it low-confidence).")
    args = ap.parse_args()

    print(f"\n=== 4-lever value-loss sequencer: {args.out} ===")
    print("MARGINAL = (knob>0 elo) − (knob=0 elo). knob=0 = pure v2.7 leaf with")
    print("that net's priors, so the policy baseline cancels. The value head is an")
    print("ASSET only if MARGINAL ≥ 0 with z = marginal/σ comfortably positive")
    print("(a low-n point estimate ≥0 is NOT a win — the B.1 a30t03 lesson).\n")

    winners = []
    for lever, (prefix, knobs) in LEVERS.items():
        present = []
        for tag, label, is_base in knobs:
            d = args.out / f"{prefix}{tag}"
            if d.is_dir():
                w, dd, n = _dir_record(d)
                if n:
                    elo, sig = _elo(w, dd, n)
                    present.append((tag, label, is_base, elo, sig, n))
        if not present:
            continue
        print(f"--- {LEVER_NAME[lever]} ---")
        base = None
        for tag, label, is_base, elo, sig, n in present:
            flag = "  [baseline]" if is_base else ""
            print(f"  {label:<10} {elo:>+8.1f} ± {sig:>4.0f}  (n={n}){flag}")
            if is_base:
                base = (elo, sig, n)
        # marginal = best non-baseline knob − baseline
        nonbase = [(elo, sig, n, label) for tag, label, is_base, elo, sig, n
                   in present if not is_base]
        if base is None or not nonbase:
            print("  (incomplete — need baseline + ≥1 knob>0 eval)\n")
            continue
        b_elo, b_sig, b_n = base
        best_elo, best_sig, best_n, best_label = max(nonbase, key=lambda x: x[0])
        marg = best_elo - b_elo
        marg_sig = math.hypot(best_sig, b_sig) if (math.isfinite(best_sig)
                                                   and math.isfinite(b_sig)) else float("nan")
        z = marg / marg_sig if (math.isfinite(marg_sig) and marg_sig > 0) else float("nan")
        lowconf = b_n < args.min_n_baseline or best_n < args.min_n_baseline
        clears = marg >= 0
        confident = clears and math.isfinite(z) and z >= 1.0 and not lowconf
        verdict = ("✅ ASSET (marginal≥0, z≥1)" if confident
                   else "～ marginal≥0 but low-confidence (z<1 or low n)" if clears
                   else "✗ value HURTS (marginal<0)")
        print(f"  MARGINAL ({best_label}−baseline) = {marg:+.1f} ± {marg_sig:.0f}"
              f"  z={z:+.2f}  -> {verdict}\n")
        if confident:
            winners.append((lever, marg, z))

    # Overall verdict + machine-readable flag for the sequencer.
    winner = max(winners, key=lambda x: x[1])[0] if winners else "none"
    if winner != "none":
        m = next(x for x in winners if x[0] == winner)
        print(f"  >>> WINNER: {LEVER_NAME[winner]} marginal {m[1]:+.1f} (z={m[2]:+.2f})")
        print("      → hand to Lever 3 (flywheel): use this net as a λ-leaf in new")
        print("        self-play and iterate (run_pathb_cluster_loop STAGE_B_BLEND).")
    else:
        print("  >>> NO lever cleared the gate confidently.")
        print("      → Lever 4 decision branch: the v2.7-leaf ceiling holds —")
        print("        build the non-saturated odometer, try a different leaf, or")
        print("        accept ~strong-human and revisit the goal.")
    (args.out).mkdir(parents=True, exist_ok=True)
    (args.out / "VERDICT.txt").write_text(f"WINNER={winner}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
