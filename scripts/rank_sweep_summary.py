"""Summarize the STEP B.1 ranking-loss sweep (Shabbos run).

Scans an OUT dir for eval_<tag>_b<lt> game-result dirs (written by
eval_net_vs_heuristic), computes elo per (config tag, lambda), and prints the
lambda-curve per config so the verdict is readable at a glance:

  SUCCESS = any config's lambda=0.5 elo >= 0 (the value head is finally an asset
  in the blend). Compare to the failures so far: searchval -24, GP -38,
  mimic-v2.7 -38 (all < 0). lambda=0 ~ the policy baseline; lambda=1.0 = pure NN
  leaf (craters for every head so far).

Usage:
  python scripts/rank_sweep_summary.py --out /mnt/c/carc-shared/rank_sweep
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


def _dir_record(d: Path) -> tuple[int, int, int, float]:
    w = dd = n = 0
    diff_sum = 0.0
    for jf in d.glob("*seed*.json"):
        try:
            r = json.loads(jf.read_text())
        except Exception:
            continue
        n += 1
        diff_sum += r.get("diff", 0)
        if r.get("won_by_net"):
            w += 1
        elif r.get("drew"):
            dd += 1
    return w, dd, n, (diff_sum / n if n else 0.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--baseline-l0", type=float, default=74.0,
                    help="Fallback policy-only λ0 elo for the marginal when a "
                         "config's own λ0 eval is incomplete (rank_data α=0 gate = +74).")
    args = ap.parse_args()

    pat = re.compile(r"^eval_(.+)_b(\d+)$")
    # tag -> {lam_tag: (w,d,n,avgdiff)}
    configs: dict[str, dict[str, tuple]] = {}
    for d in sorted(args.out.glob("eval_*_b*")):
        if not d.is_dir():
            continue
        m = pat.match(d.name)
        if not m:
            continue
        tag, lt = m.group(1), m.group(2)
        configs.setdefault(tag, {})[lt] = _dir_record(d)

    if not configs:
        print(f"no eval dirs under {args.out}")
        return 1

    lam_order = [("0", "λ0"), ("05", "λ0.5"), ("10", "λ1.0")]
    print(f"\n=== ranking-loss sweep: {args.out} ===")
    print("READ THE *MARGINAL* (λ0.5 − λ0), NOT absolute λ0.5: absolute λ0.5 is")
    print("confounded by the policy baseline λ0 (~+70 here). The value head is an")
    print(f"ASSET only if MARGINAL >= ~0. Fallback baseline λ0 = +{args.baseline_l0:.0f}")
    print("(use a config's own λ0 when its eval is complete, n>=150).")
    print("Prior MSE heads' marginal: searchval −80, GP −94 (all big-negative).\n")
    print(f"  {'config':<12} " + "  ".join(f"{lbl:>15}" for _, lbl in lam_order)
          + f"  {'MARGINAL(λ.5−λ0)':>17}  {'done':>4}")
    print(f"  {'-'*12} " + "  ".join("-" * 15 for _ in lam_order) + f"  {'-'*17}  ----")
    best = None
    for tag in sorted(configs):
        cells = []
        elos = {}
        for lt, _lbl in lam_order:
            rec = configs[tag].get(lt)
            if rec is None:
                cells.append(f"{'-':>15}")
                continue
            w, dd, n, _ = rec
            elo, sig = _elo(w, dd, n)
            cells.append(f"{elo:>+7.1f}±{sig:>3.0f}/{n:<3}" if n else f"{'-':>15}")
            if n:
                elos[lt] = (elo, n)
        # marginal = λ0.5 − (own λ0 if complete else baseline)
        marg = mtxt = None
        if "05" in elos:
            l05 = elos["05"][0]
            l0n = elos.get("0")
            base = l0n[0] if (l0n and l0n[1] >= 150) else args.baseline_l0
            src = "own" if (l0n and l0n[1] >= 150) else "base"
            marg = l05 - base
            mtxt = f"{marg:>+8.1f} ({src})"
        done = (args.out / "done" / tag).exists()
        print(f"  {tag:<12} " + "  ".join(cells)
              + f"  {(mtxt or '-'):>17}  {'yes' if done else 'no':>4}")
        if marg is not None and (best is None or marg > best[1]):
            best = (tag, marg)

    print()
    if best is not None:
        verdict = ("✅ value is an ASSET (marginal >= 0)" if best[1] >= 0
                   else "✗ value still HURTS (marginal < 0) — gate unmet")
        print(f"  best MARGINAL: {best[0]} = {best[1]:+.1f}  -> {verdict}")
        print("  (also note λ1.0 vs prior −576/−604: smaller crater = ranking loss")
        print("   improved leaf quality even if marginal still < 0.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
