"""Which v2.9 term moved the decision? — 1-ply leaf-argmax attribution.

For a candidate LeafConfig, walk a corpus of positions; at each decision compute the
1-ply leaf-argmax afterstate under v2.8 and under the candidate. Where they DIFFER,
decompose both chosen afterstates (mover POV) and attribute the swing to the v2.9 term
with the largest delta between them. This is the leaf's LOCAL preference — the actual
game uses MCTS on top, so treat it as "how the term reshapes afterstate ranking", not a
full move explanation.

Usage:
  python scripts/v29/why_decompose.py --candidate A16 --positions 200 --show 15
"""
from __future__ import annotations

import argparse
import dataclasses as dc
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai import leaf_v29 as L
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2

V28 = dc.replace(DEFAULT_CONFIG, meeple_k=2.0)
MILD_CURVE = (-8.0, -4.0, -1.0, 0.0, 2.0, 3.0, 4.0, 5.0)
AGGR_CURVE = (-14.0, -7.0, -3.0, 0.0, 2.0, 3.0, 3.5, 4.0)
# ONLY the v2.9-specific terms can explain why the candidate ranks differently than
# v2.8 — the v2.8 terms (base/closure/meeple_flat) are identical functions in both cfgs,
# so their afterstate-delta reflects the raw action difference, NOT the candidate's
# re-ranking. Attribute the swing among these; print the v2.8 terms only for context.
V29_TERMS = ("utility_transform_delta", "meeple_curve_delta",
             "tactical_punish_delta", "farm_access_delta")
CTX_TERMS = ("base", "closure_self", "closure_opp", "meeple_flat")


def candidate_cfg(name):
    if name.startswith("A") and name[1:].isdigit():
        return dc.replace(V28, v29_util_tanh_t=float(name[1:]))
    if name == "Bmild":
        return dc.replace(V28, v29_meeple_curve=MILD_CURVE)
    if name == "Baggr":
        return dc.replace(V28, v29_meeple_curve=AGGR_CURVE)
    if name in ("D1", "D2", "D3"):
        return dc.replace(V28, v29_punish_k={"D1": 0.3, "D2": 0.6, "D3": 1.0}[name])
    if name in ("E1", "E2"):
        return dc.replace(V28, v29_farm_access_k={"E1": 0.2, "E2": 0.4}[name])
    raise ValueError(name)


def _argmax_afterstate(g, b, cfg):
    """1-ply leaf-argmax: best legal action by mover-POV leaf on the afterstate."""
    mover = b.state.current_player
    best_a, best_v, best_after = None, None, None
    for a in np.flatnonzero(g.get_valid_moves(b)).tolist():
        nb, _ = g.get_next_state(b, int(a))
        v = virtual_score_v2(nb.state, mover, cfg)
        if best_v is None or v > best_v:
            best_a, best_v, best_after = int(a), v, nb
    return best_a, best_after, mover


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--positions", type=int, default=200)
    ap.add_argument("--show", type=int, default=15)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    cfg = candidate_cfg(args.candidate)

    random.seed(args.seed)
    # sample decision positions from random self-play
    positions = []
    s = 0
    while len(positions) < args.positions:
        g = Game(enable_legal_moves_cache=True)
        b = g.get_init_board()
        rng = random.Random(1000 + s); s += 1
        for ply in range(120):
            if g.get_game_ended(b, 0) != 0.0:
                break
            if ply >= 6 and ply % 3 == 0 and int(g.get_valid_moves(b).sum()) > 1:
                positions.append((g, b))
                if len(positions) >= args.positions:
                    break
            legal = np.flatnonzero(g.get_valid_moves(b))
            b, _ = g.get_next_state(b, int(rng.choice(legal.tolist())))

    diverged = 0
    attribution = {t: 0 for t in (*V29_TERMS, "none")}
    shown = 0
    for g, b in positions:
        a28, after28, mover = _argmax_afterstate(g, b, V28)
        a29, after29, _ = _argmax_afterstate(g, b, cfg)
        if a29 == a28:
            continue
        diverged += 1
        d28 = L.decompose_v29(after28.state, mover, cfg)   # v2.8's pick, scored by candidate
        d29 = L.decompose_v29(after29.state, mover, cfg)   # candidate's pick, scored by candidate
        # Attribute the re-ranking to the v2.9 term whose afterstate-delta is largest.
        v29d = {t: d29.get(t, 0.0) - d28.get(t, 0.0) for t in V29_TERMS}
        top = max(v29d, key=lambda t: abs(v29d[t]))
        attribution[top if abs(v29d[top]) > 1e-9 else "none"] += 1
        if shown < args.show:
            shown += 1
            ctx = {t: d29.get(t, 0.0) - d28.get(t, 0.0) for t in CTX_TERMS}
            print(f"\n[{shown}] mover=P{mover} deck={len(b.state.deck)} scores={tuple(b.state.scores)} "
                  f"legal={int(g.get_valid_moves(b).sum())}")
            print(f"    v2.8 pick total={d28['total_int']:+d} | cand pick total={d29['total_int']:+d} "
                  f"(cand prefers its pick by {d29['total']-d28['total']:+.2f})")
            print(f"    v2.9 term that flipped it: {top} Δ={v29d[top]:+.2f}")
            print(f"    context (action diff in v2.8 terms): "
                  + " ".join(f"{t.split('_')[0]}:{ctx[t]:+.1f}" for t in CTX_TERMS if abs(ctx[t]) > 0.05))

    print(f"\n=== {args.candidate}: {diverged}/{len(positions)} positions diverged from v2.8 (1-ply leaf) ===")
    print("attribution — which v2.9 term re-ranked the afterstate:")
    for t in sorted(attribution, key=lambda x: -attribution[x]):
        if attribution[t]:
            print(f"  {t:24} {attribution[t]:4}  ({100*attribution[t]/max(diverged,1):.0f}%)")


if __name__ == "__main__":
    main()
