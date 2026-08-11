#!/usr/bin/env python3
"""G3 / step 3 (SUPPLEMENTARY) — does the between/within split hold outside the
K=2 endgame?

The exact-solver bank is endgame-only (READOUT §3.2 / CLAIMS_LEDGER E5).  The only
sibling-structured per-child values on disk that span the whole game are the
h6400_v2.9 deep-search Q values in

  measurement/high_gap_distillation/scaled/qprobe_A/probe.jsonl

— one record per root with `action_q: {action: q}` over ALL legal children, mover
oriented (`q_best` == max(action_q), `teacher_best` == argmax), sampled at discrete
`k_remaining` strata {2,4,6,10,14,22,32,44,56}.  These are the same 10,067 roots the
exact-solver bank is drawn from (its 1,119 roots are the k_remaining==2 stratum).

CAVEAT, binding on every number here: h6400 Q is a SEARCH ESTIMATE, not ground
truth, and it correlates 0.995 with the v2.9 leaf (autopsy F4) — which is exactly
why the paper's primary ruler is the exact solver instead.  This panel is used for
the SHAPE of the between/within split across game phase, never as a verdict.

Pure arithmetic: no engine, no search, no net forward, no GPU.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
PROBE = REPO / "measurement" / "high_gap_distillation" / "scaled" / "qprobe_A" / "probe.jsonl"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def split(vals_by_root: list[np.ndarray]) -> dict:
    all_v = np.concatenate(vals_by_root)
    n = all_v.size
    grand = all_v.mean()
    ss_total = float(((all_v - grand) ** 2).sum())
    ss_between = 0.0
    ss_within = 0.0
    for v in vals_by_root:
        m = v.mean()
        ss_between += v.size * (m - grand) ** 2
        ss_within += float(((v - m) ** 2).sum())
    return {
        "n_roots": len(vals_by_root),
        "n_children": int(n),
        "children_per_root_mean": n / len(vals_by_root),
        "sd_total": float(np.sqrt(ss_total / n)),
        "sd_between_root": float(np.sqrt(ss_between / n)),
        "sd_within_root": float(np.sqrt(ss_within / n)),
        "frac_between_root": ss_between / ss_total,
        "frac_within_root": ss_within / ss_total,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", default=str(PROBE))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    t0 = time.time()
    by_k: dict[int, list[np.ndarray]] = defaultdict(list)
    by_phase: dict[str, list[np.ndarray]] = defaultdict(list)
    all_roots: list[np.ndarray] = []
    n_rec = 0
    with open(args.probe) as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            aq = r.get("action_q")
            if not aq:
                continue
            v = np.fromiter((float(x) for x in aq.values()), dtype=np.float64)
            if v.size < 2:
                continue
            n_rec += 1
            by_k[int(r["k_remaining"])].append(v)
            by_phase[str(r["phase"])].append(v)
            all_roots.append(v)

    out = {
        "kind": "g3_phase_curve_h6400_oracle",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "code_rev": subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True).stdout.strip(),
        "inputs": {
            "probe": args.probe,
            "probe_sha256": sha256(Path(args.probe)),
            "value": "action_q — h6400_v2.9 deep-search per-child Q, mover-oriented, tanh units",
            "caveat": "SEARCH ESTIMATE, not ground truth; correlates 0.995 with the v2.9 leaf "
                      "(autopsy F4). Shape only — never a verdict.",
            "n_roots_with_action_q": n_rec,
        },
        "overall": split(all_roots),
        "by_k_remaining": {str(k): split(by_k[k]) for k in sorted(by_k)},
        "by_phase": {p: split(by_phase[p]) for p in sorted(by_phase)},
        "wall_secs": time.time() - t0,
    }
    js = json.dumps(out, indent=2)
    if args.out:
        Path(args.out).write_text(js + "\n")
    print(js)


if __name__ == "__main__":
    main()
