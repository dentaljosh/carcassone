#!/usr/bin/env python3
"""PROBE A — MILESTONE 2.5 additive-arm leaf speed with the ENRICHED head.

Re-confirms the ≤3× Cython-leaf budget (spec §3 / task-1 rider) AFTER adding the
two board-level side-inputs:
  * bag histogram extraction (step1_planes.bag_histogram) + a 32->16->1 bag_head,
  * the exact cloister board-level offset (structured_leaf.cloister_offset).

Both are BOARD-LEVEL (one per node), so the marginal cost over the milestone-2
head is: one bag_histogram pass (32-int census over the deck) + one tiny 32->16->1
forward + one cloister pass (single sweep over placed cloister meeples). Expect
~2.7-2.8× (spec estimate).

Cells (per NODE, median ns, on realistic mid/late boards; same board set as
enriched_speed.py):
  BASELINE   flat_leaf_cy.flat_virtual_score_v2_cy       (the bar)
  PATH-2.5   emit + head + bag_hist + bag_head + cloister (structured v_leaf only)
  ADDITIVE   BASELINE + PATH-2.5                          (the §4 additive arm)

The head is loaded from the ENRICHED trained npz (has bag_W1..); if absent, a
random-weight enriched stub is synthesized so the SPEED can be measured
independently of training completion (weights don't change wall-time).

  nice -n 19 CARCASSONNE_USE_CY_LEAF=1 .venv/bin/python -u \
      scripts/probe_a/enriched25_speed.py --npz checkpoints/probe_a/gtheta_bag_numpy.npz
"""
from __future__ import annotations
import argparse, os, statistics, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "engine"))
sys.path.insert(0, str(REPO / "scripts" / "probe_a"))
sys.path.insert(0, str(REPO / "scripts" / "feature_planes_gate"))
os.environ.setdefault("CARCASSONNE_USE_CY_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")

import numpy as np  # noqa: E402
from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402
import carcassonne_ai.flat_leaf_cy as cy  # noqa: E402
import component_features as cf  # noqa: E402
import structured_leaf as SL  # noqa: E402
from enriched_speed import make_boards, _count_tiles, timed_median_ns  # noqa: E402
from step1_planes import bag_histogram, N_BAG  # noqa: E402

CLOSURE_P = DEFAULT_CONFIG.closure_p


def _random_enriched_stub(hidden=32, bag_hidden=16, seed=0):
    rng = np.random.default_rng(seed)
    return SL.GThetaStub(
        W1=rng.standard_normal((cf.FEAT_DIM, hidden)) * 0.3, b1=np.zeros(hidden),
        W2=rng.standard_normal((hidden, 1)) * 0.3, b2=np.zeros(1),
        bag_W1=rng.standard_normal((N_BAG, bag_hidden)) * 0.3, bag_b1=np.zeros(bag_hidden),
        bag_W2=rng.standard_normal((bag_hidden, 1)) * 0.3, bag_b2=np.zeros(1),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", default=str(REPO / "checkpoints" / "probe_a" / "gtheta_bag_numpy.npz"))
    args = ap.parse_args()

    if Path(args.npz).exists():
        g = SL.GThetaStub.from_trained_npz(args.npz)
        g._is_stub = False
        src = f"trained {args.npz}"
    else:
        g = _random_enriched_stub()
        g._is_stub = False
        src = "random enriched stub (weights don't affect wall-time)"
    assert g.has_bag, "enriched head must carry a bag input"

    print("=" * 74)
    print("PROBE A — MILESTONE 2.5 ENRICHED additive-arm speed")
    print(f"head: {src}")
    print("=" * 74)
    _ = flat_leaf.flat_virtual_score_v2(make_boards(1)[0], 0, DEFAULT_CONFIG)
    if flat_leaf._CY_FLAT_V2 in (None, False):
        print("!! Cython leaf NOT bound — wrong baseline. Abort."); sys.exit(2)

    boards = make_boards(60)
    NB = len(boards)
    tiles = [_count_tiles(b) for b in boards]
    feats = [cy.component_features_cy(b, 0, CLOSURE_P) for b in boards]
    runs = [float(int(b.scores[0]) - int(b.scores[1])) for b in boards]
    print(f"boards {NB}  tiles med {int(statistics.median(tiles))}  "
          f"comps/board med {int(statistics.median([f.shape[0] for f in feats]))}  "
          f"FEAT_DIM={cf.FEAT_DIM}  N_BAG={N_BAG}")
    ITERS, WARMUP = 20000, 2000

    def _baseline(i):
        return cy.flat_virtual_score_v2_cy(boards[i % NB], 0, DEFAULT_CONFIG)
    base = timed_median_ns(_baseline, ITERS, WARMUP)

    # PATH-2.5: the full enriched structured leaf (emit + comp-head + bag_hist +
    # bag_head + cloister). This is exactly structured_value's trained path.
    def _path25(i):
        b = boards[i % NB]
        X = cy.component_features_cy(b, 0, CLOSURE_P)
        clo = SL.cloister_offset(b, 0, DEFAULT_CONFIG)
        bag = bag_histogram(b)
        return g.aggregate_with_offset(X, runs[i % NB], clo, bag)
    path25 = timed_median_ns(_path25, ITERS, WARMUP)

    def _additive(i):
        b = boards[i % NB]
        h = cy.flat_virtual_score_v2_cy(b, 0, DEFAULT_CONFIG)
        X = cy.component_features_cy(b, 0, CLOSURE_P)
        clo = SL.cloister_offset(b, 0, DEFAULT_CONFIG)
        bag = bag_histogram(b)
        return h, g.aggregate_with_offset(X, runs[i % NB], clo, bag)
    additive = timed_median_ns(_additive, ITERS, WARMUP)

    # marginal cost of the two new side-inputs alone (bag_hist + bag_head + cloister).
    def _sides(i):
        b = boards[i % NB]
        clo = SL.cloister_offset(b, 0, DEFAULT_CONFIG)
        bag = bag_histogram(b)
        return g.bag_scalar(bag) + clo
    sides = timed_median_ns(_sides, ITERS, WARMUP)

    def R(x):
        return x / base
    print("\nSUMMARY (budget: v_leaf <= 3.00x the Cython leaf per node)")
    for name, ns, r in (("BASELINE cython leaf", base, 1.0),
                        ("SIDES    bag_hist+bag_head+cloister", sides, R(sides)),
                        ("PATH-2.5 enriched structured leaf", path25, R(path25)),
                        ("ADDITIVE baseline+enriched", additive, R(additive))):
        flag = ""
        if name.startswith(("PATH", "ADDITIVE")):
            flag = "  PASS" if r <= 3.0 else ("  MARGINAL" if r <= 3.3 else "  FAIL")
        print(f"  {name:<38} {ns:>9,.0f} ns  {r:>5.2f}x{flag}")
    print(f"\nVERDICT structured-only={R(path25):.2f}x  additive-arm={R(additive):.2f}x  "
          f"({'PASS' if R(additive) <= 3.0 else 'MARGINAL' if R(additive) <= 3.3 else 'FAIL'})")


if __name__ == "__main__":
    main()
