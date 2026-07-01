#!/usr/bin/env python3
"""PROBE A — MILESTONE 2: re-confirm additive-arm leaf speed with the TRAINED
numpy head (structured_leaf.GThetaStub.from_trained_npz).

Same cells + boards as enriched_speed.py, but HEAD is the exported trained head
(24->32->1) loaded from the npz, and v_leaf uses the running-offset aggregation
(tanh((running+sum)/15)). The head SHAPE is identical to the milestone-1 stub so
the speed must hold ~2.56x; this proves it on the real weights, not a random stub.

  nice -n 19 CARCASSONNE_USE_CY_LEAF=1 .venv/bin/python -u \
      scripts/probe_a/trained_speed.py --npz checkpoints/probe_a/gtheta_numpy.npz
"""
from __future__ import annotations
import argparse, os, statistics, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "engine"))
sys.path.insert(0, str(REPO / "scripts" / "probe_a"))
os.environ.setdefault("CARCASSONNE_USE_CY_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")

import numpy as np  # noqa: E402
from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402
import carcassonne_ai.flat_leaf_cy as cy  # noqa: E402
import component_features as cf  # noqa: E402
import structured_leaf as SL  # noqa: E402
from enriched_speed import make_boards, _count_tiles, timed_median_ns  # noqa: E402

CLOSURE_P = DEFAULT_CONFIG.closure_p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", default=str(REPO / "checkpoints" / "probe_a" / "gtheta_numpy.npz"))
    args = ap.parse_args()

    g = SL.GThetaStub.from_trained_npz(args.npz)
    print("=" * 74)
    print("PROBE A — TRAINED-WEIGHTS additive-arm speed (numpy head, 24->32->1)")
    print("=" * 74)
    _ = flat_leaf.flat_virtual_score_v2(make_boards(1)[0], 0, DEFAULT_CONFIG)
    if flat_leaf._CY_FLAT_V2 in (None, False):
        print("!! Cython leaf NOT bound — wrong baseline. Abort."); sys.exit(2)

    boards = make_boards(60)
    NB = len(boards)
    tiles = [_count_tiles(b) for b in boards]
    feats = [cy.component_features_cy(b, 0, CLOSURE_P) for b in boards]
    runs = [float(int(b.scores[0]) - int(b.scores[1])) for b in boards]
    comps = [f.shape[0] for f in feats]
    print(f"boards {NB}  tiles med {int(statistics.median(tiles))}  "
          f"comps/board med {int(statistics.median(comps))}  FEAT_DIM={cf.FEAT_DIM}")
    ITERS, WARMUP = 20000, 2000

    def _baseline(i):
        return cy.flat_virtual_score_v2_cy(boards[i % NB], 0, DEFAULT_CONFIG)
    base = timed_median_ns(_baseline, ITERS, WARMUP)

    def _pathcy(i):
        X = cy.component_features_cy(boards[i % NB], 0, CLOSURE_P)
        return g.aggregate_with_offset(X, runs[i % NB])
    pathcy = timed_median_ns(_pathcy, ITERS, WARMUP)

    def _additive(i):
        b = boards[i % NB]
        h = cy.flat_virtual_score_v2_cy(b, 0, DEFAULT_CONFIG)
        X = cy.component_features_cy(b, 0, CLOSURE_P)
        return h, g.aggregate_with_offset(X, runs[i % NB])
    additive = timed_median_ns(_additive, ITERS, WARMUP)

    def R(x):
        return x / base

    print("\nSUMMARY (budget: v_leaf <= 3.00x the Cython leaf per node)")
    for name, ns, r in (("BASELINE cython leaf", base, 1.0),
                        ("PATH-CY  emit+trained head", pathcy, R(pathcy)),
                        ("ADDITIVE baseline+emit+head", additive, R(additive))):
        flag = ""
        if name.startswith(("PATH", "ADDITIVE")):
            flag = "  PASS" if r <= 3.0 else ("  MARGINAL" if r <= 3.3 else "  FAIL")
        print(f"  {name:<32} {ns:>9,.0f} ns  {r:>5.2f}x{flag}")
    print(f"\nVERDICT structured-only={R(pathcy):.2f}x  additive-arm={R(additive):.2f}x")


if __name__ == "__main__":
    main()
