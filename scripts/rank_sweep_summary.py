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
    print("(SUCCESS = λ0.5 >= 0; prior failures: searchval -24, GP -38, mimic-v2.7 -38)\n")
    print(f"  {'config':<14} " + "  ".join(f"{lbl:>16}" for _, lbl in lam_order)
          + f"  {'done':>5}")
    print(f"  {'-'*14} " + "  ".join("-" * 16 for _ in lam_order) + "  -----")
    best = None
    for tag in sorted(configs):
        cells = []
        l05 = None
        for lt, _lbl in lam_order:
            rec = configs[tag].get(lt)
            if rec is None:
                cells.append(f"{'-':>16}")
                continue
            w, dd, n, _ = rec
            elo, sig = _elo(w, dd, n)
            cells.append(f"{elo:>+8.1f}±{sig:>4.0f}/{n:<3}" if n else f"{'-':>16}")
            if lt == "05" and n:
                l05 = elo
        done = (args.out / "done" / tag).exists()
        print(f"  {tag:<14} " + "  ".join(cells) + f"  {'yes' if done else 'no':>5}")
        if l05 is not None and (best is None or l05 > best[1]):
            best = (tag, l05)

    print()
    if best is not None:
        verdict = "✅ CLEARS the gate" if best[1] >= 0 else "✗ still < 0 (gate unmet)"
        print(f"  best λ0.5: {best[0]} = {best[1]:+.1f}  -> {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
