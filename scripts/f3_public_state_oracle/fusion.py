"""F3 — strategy-fusion detector (§3.3). A NEW instrument.

Strategy fusion = a root action ``a`` ranks well under pooled-Q **because different
determinized worlds reward incompatible downstream continuations** that a single
observable-state policy cannot jointly realise. The exact public-state optimum uses
ONE contingent policy (conditioning only on revealed draws), so ``regret(pooled-Q
pick vs exact)`` already captures the *aggregate* fusion cost; the fusion premium
``Φ(a)`` **localises** which picks are inflated by fusion vs by coverage/selection
bias vs by plain sampling noise.

Mechanism (§3.3):
  * ``Q_fused(a)``  = each world scores ``a`` with ITS OWN clairvoyant continuation
                     (mean over worlds) — what pooled-Q effectively fuses.
  * ``Q_single(a)`` = the best value achievable by ONE continuation policy fixed
                     across all k worlds = ``max_j agg_w( replay π_j in world w )``.
  * ``Φ(a) = Q_fused(a) − Q_single(a) ≥ 0``.

The core ``fusion_premium`` is a pure function over a value matrix, so the toy
fixtures (test G) hand-specify the two-world incompatible-continuation scenario and
assert Φ exactly. ``engine_fusion_premium`` wires it to a real ``PimcCapture`` by
cross-world continuation replay to terminal (engine-exact ``flat_base_score``).
"""
from __future__ import annotations

import math

import numpy as np

from carcassonne_ai.flat_leaf import flat_base_score

DEFAULT_FUSION_THRESHOLD = 0.5


# --------------------------------------------------------------------------- #
# Pure core — a value matrix in, Φ out. Hand-verifiable (test G).              #
# --------------------------------------------------------------------------- #
def fusion_premium(fused_values, single_values: dict, aggregator: str = "mean") -> dict:
    """Φ from a per-world value picture (all values ROOT-player POV, points).

    fused_values  : list over the k worlds — world w's value for ``a`` under
                    world w's OWN continuation (the fused, per-world-clairvoyant
                    picture). ``Q_fused = mean(fused_values)``.
    single_values : {policy_id: [value in world 0, value in world 1, ...]} — the
                    value of replaying ONE fixed policy across all k worlds.
                    ``Q_single = max_j aggregator(single_values[j])``.
    aggregator    : 'mean' (default) or 'min' over worlds for the single-policy
                    score (the spec allows either; both are reported).

    Returns {phi, q_fused, q_single, best_single_policy}. Φ is clamped at 0
    (fusion can only INFLATE the fused estimate above the best single policy;
    a tiny negative from float noise is snapped to 0)."""
    if aggregator not in ("mean", "min"):
        raise ValueError(f"aggregator must be 'mean'|'min'; got {aggregator!r}")
    fv = [float(x) for x in fused_values]
    if not fv:
        raise ValueError("fusion_premium: empty fused_values")
    q_fused = float(np.mean(fv))
    agg = (lambda xs: float(np.mean(xs))) if aggregator == "mean" else (lambda xs: float(min(xs)))
    best_pol, q_single = None, -math.inf
    for pid, vals in single_values.items():
        s = agg([float(x) for x in vals])
        if s > q_single:
            q_single, best_pol = s, pid
    if q_single == -math.inf:
        raise ValueError("fusion_premium: empty single_values")
    phi = q_fused - q_single
    if -1e-9 < phi < 0:
        phi = 0.0
    return {"phi": phi, "q_fused": q_fused, "q_single": q_single,
            "best_single_policy": best_pol}


def flag_fusion(phi: float, pick: int, pooled_q_pick: int, optimal_actions,
                threshold: float = DEFAULT_FUSION_THRESHOLD) -> bool:
    """Flag ``pick`` as fusion-inflated iff Φ ≥ threshold AND it is the pooled-Q
    pick AND it is NOT in the exact optimal set (§3.3 step 3)."""
    return bool(phi >= threshold and pick == pooled_q_pick
                and pick not in set(optimal_actions))


# --------------------------------------------------------------------------- #
# Engine-backed continuation replay                                            #
# --------------------------------------------------------------------------- #
def _terminal(board) -> bool:
    return board.state.next_tile is None


def _root_pov(board, root_player: int) -> float:
    v = float(flat_base_score(board.state, 0))     # P0 - P1
    return v if root_player == 0 else -v


def replay_policy_to_terminal(game, board, primary_pol: dict, fallback_pol: dict,
                              root_player: int, ply_cap: int = 400) -> float:
    """Play ``board`` to terminal following ``primary_pol`` (keyed by observable
    ``string_representation``); where it has no legal entry for the current state,
    fall back to ``fallback_pol``; where neither applies, take the lowest legal
    action (a deterministic tie-break). Draws come from THIS board's own deck, so
    replaying policy π_j on world w's board = "policy j executed in world w".
    Returns the terminal score-diff in the ROOT player's perspective."""
    cur = board
    for _ in range(ply_cap):
        if _terminal(cur):
            return _root_pov(cur, root_player)
        legal = np.flatnonzero(game.get_valid_moves(cur)).astype(int)
        legal_set = set(int(x) for x in legal)
        key = game.string_representation(cur)
        a = primary_pol.get(key)
        if a is None or a not in legal_set:
            a = fallback_pol.get(key)
        if a is None or a not in legal_set:
            a = int(min(legal_set))
        cur, _ = game.get_next_state(cur, int(a))
    return _root_pov(cur, root_player)


def engine_fusion_premium(cap, action: int, game, *, aggregator: str = "mean",
                          ply_cap: int = 400) -> dict:
    """Φ(action) for a real PimcCapture via cross-world continuation replay.

    For each world w: play ``action`` from w.det_board (its own deck), then
      * fused_w   = replay world w's OWN policy π_w to terminal;
      * single[j][w] = replay policy π_j (source world j) with π_w fallback.
    Then Φ = Q_fused − max_j agg_w single[j][w]  (fusion_premium)."""
    root_player = cap.root_player
    # child board per world after playing `action` (in that world's deck)
    childs = []
    for w in cap.worlds:
        cb, _ = game.get_next_state(w.det_board, int(action))
        childs.append(cb)
    fused = []
    for w, cb in zip(cap.worlds, childs):
        fused.append(replay_policy_to_terminal(game, cb, w.policy_map, w.policy_map,
                                                root_player, ply_cap))
    single: dict = {}
    for j, wj in enumerate(cap.worlds):
        row = []
        for w, cb in zip(cap.worlds, childs):
            row.append(replay_policy_to_terminal(game, cb, wj.policy_map,
                                                  w.policy_map, root_player, ply_cap))
        single[j] = row
    return fusion_premium(fused, single, aggregator=aggregator)
