"""PROBE A — enriched per-node speed re-measurement (spec §3, task 4).

Gate-zero measured the 12-dim starter at ~1.28x (PATH-CY). This re-measures with
the FROZEN enriched 24-dim contract (component_features.py), whose per-player
meeple extraction + farm-growth schedule cost more than the starter. We report
the ratio to the production Cython leaf and the PASS/MARGINAL/FAIL vs the 3x bar.

Measured cells (all per-NODE, median ns, on realistic mid/late boards):

  BASELINE      flat_leaf_cy.flat_virtual_score_v2_cy      (the bar)
  EMIT          flat_leaf_cy.component_features_cy         (feature matrix from the
                                                            SAME C decompose — this
                                                            is the whole enemy)
  HEAD          numpy tiny-MLP (24 -> H -> 1) sum over rows (feats precomputed)
  PATH-CY       EMIT + HEAD  (the structured v_leaf marginal cost when the C
                             decompose is the emit's own — a self-contained
                             structured leaf that does NOT also compute the scalar)
  ADDITIVE-ARM  BASELINE + EMIT + HEAD  (the offline pre-gate's additive mode
                             needs BOTH the heuristic scalar h AND the structured
                             value at the same node — the honest cost for §4)

Run:  nice -n 19 CARCASSONNE_USE_CY_LEAF=1 .venv/bin/python scripts/probe_a/enriched_speed.py
"""
from __future__ import annotations

import math
import os
import random
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "engine"))
sys.path.insert(0, str(REPO / "scripts" / "probe_a"))

os.environ.setdefault("CARCASSONNE_USE_CY_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")

import numpy as np

from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
from wingedsheep.carcassonne.tile_sets.tile_sets import TileSet
from wingedsheep.carcassonne.tile_sets.supplementary_rules import SupplementaryRule
from wingedsheep.carcassonne.utils.action_util import ActionUtil
from wingedsheep.carcassonne.utils.state_updater import StateUpdater

from carcassonne_ai import flat_leaf
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
import carcassonne_ai.flat_leaf_cy as cy
import component_features as cf

FEAT_DIM = cf.FEAT_DIM
CLOSURE_P = DEFAULT_CONFIG.closure_p


def _count_tiles(st) -> int:
    return sum(1 for row in st.board for t in row if t is not None)


def rollout_to_tiles(seed: int, target_tiles: int):
    rng = random.Random(seed * 7919 + 13)
    st = CarcassonneGameState(
        players=2, tile_sets=[TileSet.BASE],
        supplementary_rules=[SupplementaryRule.FARMERS],
    )
    rng.shuffle(st.deck)
    placed = 1
    while not st.is_terminated() and placed < target_tiles:
        acts = ActionUtil.get_possible_actions(st)
        if not acts:
            break
        StateUpdater.apply_action_inplace(game_state=st, action=rng.choice(acts))
        placed = _count_tiles(st)
    return st


def make_boards(n=60, lo=40, hi=80):
    return [rollout_to_tiles(1000 + i, lo + (hi - lo) * i // max(1, n - 1)) for i in range(n)]


class NumpyMLP:
    def __init__(self, in_dim=FEAT_DIM, hidden=32, seed=0):
        rng = np.random.default_rng(seed)
        self.W1 = rng.standard_normal((in_dim, hidden)).astype(np.float32) * 0.3
        self.b1 = np.zeros(hidden, dtype=np.float32)
        self.W2 = rng.standard_normal((hidden, 1)).astype(np.float32) * 0.3
        self.b2 = np.zeros(1, dtype=np.float32)

    def forward_sum(self, X):
        if X.shape[0] == 0:
            return 0.0
        h = np.tanh(X @ self.W1 + self.b1)
        return float((h @ self.W2 + self.b2).sum())


def timed_median_ns(fn, iters, warmup):
    for i in range(warmup):
        fn(i)
    s = []
    for i in range(iters):
        t0 = time.perf_counter_ns()
        fn(i)
        s.append(time.perf_counter_ns() - t0)
    return statistics.median(s)


def main():
    print("=" * 74)
    print("PROBE A — ENRICHED per-node speed (24-dim frozen contract)")
    print("=" * 74)
    _ = flat_leaf.flat_virtual_score_v2(rollout_to_tiles(0, 5), 0, DEFAULT_CONFIG)
    if flat_leaf._CY_FLAT_V2 in (None, False):
        print("!! Cython leaf NOT bound — wrong baseline. Abort.")
        sys.exit(2)

    N = 60
    boards = make_boards(N)
    NB = len(boards)
    tiles = [_count_tiles(b) for b in boards]
    comps = [cy.component_features_cy(b, 0, CLOSURE_P).shape[0] for b in boards]
    print(f"\nboards: {NB}  tiles min/med/max {min(tiles)}/{int(statistics.median(tiles))}/{max(tiles)}"
          f"   comps/board min/med/max {min(comps)}/{int(statistics.median(comps))}/{max(comps)}")
    print(f"FEAT_DIM = {FEAT_DIM}")

    feats = [cy.component_features_cy(b, 0, CLOSURE_P) for b in boards]
    npm = NumpyMLP(hidden=32, seed=0)
    ITERS, WARMUP = 20000, 2000

    def _baseline(i):
        return cy.flat_virtual_score_v2_cy(boards[i % NB], 0, DEFAULT_CONFIG)
    base = timed_median_ns(_baseline, ITERS, WARMUP)

    def _emit(i):
        return cy.component_features_cy(boards[i % NB], 0, CLOSURE_P)
    emit = timed_median_ns(_emit, ITERS, WARMUP)

    def _head(i):
        return npm.forward_sum(feats[i % NB])
    head = timed_median_ns(_head, ITERS, WARMUP)

    def _pathcy(i):
        X = cy.component_features_cy(boards[i % NB], 0, CLOSURE_P)
        return npm.forward_sum(X)
    pathcy = timed_median_ns(_pathcy, ITERS, WARMUP)

    def _additive(i):
        b = boards[i % NB]
        h = cy.flat_virtual_score_v2_cy(b, 0, DEFAULT_CONFIG)
        X = cy.component_features_cy(b, 0, CLOSURE_P)
        return h, npm.forward_sum(X)
    additive = timed_median_ns(_additive, ITERS, WARMUP)

    def R(x):
        return x / base

    print("\n" + "=" * 74)
    print("SUMMARY  (budget: v_leaf <= 3.00x the Cython leaf per node)")
    print("=" * 74)
    rows = [
        ("BASELINE  cython scalar leaf", base, 1.00, "the bar"),
        ("EMIT      component_features_cy", emit, R(emit), "C decompose + feat fill"),
        ("HEAD      numpy 24->32->1 sum", head, R(head), "feats precomputed"),
        ("PATH-CY   emit + head (structured only)", pathcy, R(pathcy), "structured v_leaf"),
        ("ADDITIVE  baseline + emit + head", additive, R(additive), "pre-gate additive arm"),
    ]
    print(f"  {'cell':<42} {'ns/node':>10} {'xbase':>7}  note")
    print("  " + "-" * 72)
    for name, ns, ratio, note in rows:
        flag = ""
        if name.startswith(("PATH", "ADDITIVE")):
            flag = "  PASS" if ratio <= 3.0 else ("  MARGINAL" if ratio <= 3.3 else "  FAIL")
        print(f"  {name:<42} {ns:>10,.0f} {ratio:>6.2f}x  {note}{flag}")

    print("\nVERDICT")
    print(f"  structured-only PATH-CY  = {R(pathcy):.2f}x  "
          f"({'PASS' if R(pathcy) <= 3.0 else 'MARGINAL' if R(pathcy) <= 3.3 else 'FAIL'})")
    print(f"  additive-arm (h + v)     = {R(additive):.2f}x  "
          f"({'PASS' if R(additive) <= 3.0 else 'MARGINAL' if R(additive) <= 3.3 else 'FAIL'})")
    print(f"  emit-alone marginal      = {R(emit):.2f}x  "
          f"(this is the cost the enrichment added over the scalar decompose)")


if __name__ == "__main__":
    main()
