"""C6 correctness gauntlet (BLOCKING before any strength cell) for the ID-alpha-beta
agent (src/carcassonne_ai/alphabeta_agent.py). Design:
measurement/classical_search/C6_ALPHABETA_DESIGN.md §8.

  1. SOLVER GAUNTLET — on near-terminal K2/K3 positions (built exactly as
     bench_ab_cost.py's --self-test does: fixed-seed replay to a TILES node with k
     tiles left), the agent at UNLIMITED budget + terminal-only horizon (max_depth
     >= 2K) must reproduce endgame_solver.solve(mode="clairvoyant", alphabeta=True)'s
     root VALUE exactly and return an OPTIMAL action. This exercises the P0-POV mover
     convention, mover handling, TT fail-soft flags, PVS and aspiration in one shot
     against trusted ground truth.
  2. VALUE-PRESERVATION — at fixed depth 4 on midgame positions, TT/PVS/killers/asp ON
     == all OFF (identical root value + move). LMR/futility EXCLUDED (move-changing).
  3. DETERMINISM — same board + budget twice -> identical move + node count.
  4. MEEPLE-EXTENSION — the horizon never lands on phase==MEEPLES (extension fires).

Leaf env = the production curve125 leaf (env_preamble / CL-051) set BEFORE importing
carcassonne_ai, so DEFAULT_CONFIG is the champion leaf. (The solver gauntlet's
terminal-only horizon never evaluates the heuristic leaf — only flat_base_score — so
the curve choice is irrelevant there; it matters only for the value-preservation
horizon leaves, where both arms share DEFAULT_CONFIG.)
"""
from __future__ import annotations

import os

# Production curve125 leaf env (== scripts/human_anchor/env_preamble.PROD_ENV) BEFORE
# any carcassonne_ai import so DEFAULT_CONFIG resolves to the champion leaf.
for _k, _v in {
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-10,-5,-1.25,0,2.5,3.75,5,6.25",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
}.items():
    os.environ.setdefault(_k, _v)

import math  # noqa: E402
import random  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))  # endgame_solver

from carcassonne_ai.alphabeta_agent import AlphaBetaAgent, AlphaBetaConfig  # noqa: E402
from carcassonne_ai.flat_leaf import flat_base_score  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402

import endgame_solver as S  # noqa: E402

try:
    from wingedsheep.carcassonne.objects.game_phase import GamePhase
    _TILES = GamePhase.TILES
    _MEEPLES = GamePhase.MEEPLES
except Exception:  # pragma: no cover
    _TILES = _MEEPLES = None

_BIG = 1_000_000_000  # effectively unlimited child-step budget


# --------------------------------------------------------------------------- #
# Position builders (mirror bench_ab_cost.py._near_terminal / _first_meeple_child)
# --------------------------------------------------------------------------- #
def _near_terminal(seed: int, k_target: int):
    """Deterministic random game; stop at the first TILES-phase, non-terminal node
    with k_target tiles remaining (in-hand + deck)."""
    random.seed(seed)
    g = Game(enable_legal_moves_cache=False)
    b = g.get_init_board()
    while b.state.next_tile is not None:
        if b.state.phase == _TILES and (1 + len(b.state.deck)) == k_target:
            return g, b
        legal = np.flatnonzero(g.get_valid_moves(b))
        b, _ = g.get_next_state(b, int(random.choice(legal)))
    return None, None


def _midgame(seed: int, ply_target: int):
    """Deterministic random game; stop at the first TILES node at ply >= ply_target."""
    random.seed(seed)
    g = Game(enable_legal_moves_cache=False)
    b = g.get_init_board()
    ply = 0
    while b.state.next_tile is not None:
        if b.state.phase == _TILES and ply >= ply_target:
            return g, b
        legal = np.flatnonzero(g.get_valid_moves(b))
        b, _ = g.get_next_state(b, int(random.choice(legal)))
        ply += 1
    return None, None


def _first_meeple_child(g: Game, board):
    """Step a TILES node once to a MEEPLES-phase child (to search from a meeple root)."""
    legal = np.flatnonzero(g.get_valid_moves(board))
    for a in legal:
        nb, _ = g.get_next_state(board, int(a))
        if nb.state.phase == _MEEPLES:
            return nb
    return None


# --------------------------------------------------------------------------- #
# 1. Solver gauntlet
# --------------------------------------------------------------------------- #
# (seed, k) — the two proven bench cases plus extra K2/K3 seeds for breadth.
_SOLVER_CASES = [
    (9_200_001, 2), (9_200_017, 3),
    (9_200_005, 2), (9_200_042, 3), (9_200_071, 2), (9_200_088, 3),
]


@pytest.mark.parametrize("seed,k", _SOLVER_CASES)
def test_solver_gauntlet_full_features(seed, k):
    """Unlimited budget + terminal-only horizon == solver root value + an optimal
    action, with ALL value-preserving features ON (TT + PVS + killers + aspiration)."""
    g, b = _near_terminal(seed, k)
    if b is None:
        pytest.skip(f"seed={seed} k={k}: could not build a near-terminal position")
    gt = S.solve(g, b, mode="clairvoyant", alphabeta=True)
    gt_opt = {int(a) for a in gt.optimal_actions}

    cfg = AlphaBetaConfig(step_budget=_BIG, max_depth=2 * k + 4,
                          asp=3.0, pvs=True, killers=2, use_tt=True)
    agent = AlphaBetaAgent(g, cfg)
    agent.clear()
    action = agent.move(b)
    assert agent.last_root_value == gt.value, (
        f"value mismatch seed={seed} k={k}: agent={agent.last_root_value} "
        f"solver={gt.value}")
    assert int(action) in gt_opt, (
        f"action {action} not in solver optimal set {sorted(gt_opt)} "
        f"(seed={seed} k={k})")
    # terminal-only horizon => the heuristic leaf is NEVER evaluated at a horizon.
    assert agent.horizon_meeple_hits == 0
    assert agent.depth_completed[-1] >= 2 * k, (
        f"did not search to terminal depth: completed={agent.depth_completed[-1]}")


@pytest.mark.parametrize("seed,k", _SOLVER_CASES)
def test_solver_gauntlet_no_tt_no_pvs(seed, k):
    """Same ground-truth match with TT + PVS + killers OFF (the plain-αβ floor) —
    isolates the mover convention / horizon from the TT/PVS machinery."""
    g, b = _near_terminal(seed, k)
    if b is None:
        pytest.skip(f"seed={seed} k={k}: could not build a near-terminal position")
    gt = S.solve(g, b, mode="clairvoyant", alphabeta=True)
    gt_opt = {int(a) for a in gt.optimal_actions}

    cfg = AlphaBetaConfig(step_budget=_BIG, max_depth=2 * k + 4,
                          asp=0.0, pvs=False, killers=0, use_tt=False)
    agent = AlphaBetaAgent(g, cfg)
    agent.clear()
    action = agent.move(b)
    assert agent.last_root_value == gt.value
    assert int(action) in gt_opt


# --------------------------------------------------------------------------- #
# 2. Value preservation (TT/PVS/killers/asp ON == all OFF), fixed depth 4
# --------------------------------------------------------------------------- #
_MIDGAME_SEEDS = list(range(4_300_000_001, 4_300_000_011))  # 10 positions


@pytest.mark.parametrize("seed", _MIDGAME_SEEDS)
def test_value_preservation_depth4(seed):
    g, b = _midgame(seed, ply_target=40)
    if b is None:
        pytest.skip(f"seed={seed}: could not build a midgame position")
    on = AlphaBetaConfig(step_budget=_BIG, max_depth=4,
                         asp=3.0, pvs=True, killers=2, use_tt=True,
                         lmr=False, futility=0.0)
    off = AlphaBetaConfig(step_budget=_BIG, max_depth=4,
                          asp=0.0, pvs=False, killers=0, use_tt=False,
                          lmr=False, futility=0.0)
    a_on = AlphaBetaAgent(g, on)
    a_on.clear()
    m_on = a_on.move(b)
    a_off = AlphaBetaAgent(g, off)
    a_off.clear()
    m_off = a_off.move(b)
    assert a_on.last_root_value == a_off.last_root_value, (
        f"value differs seed={seed}: ON={a_on.last_root_value} OFF={a_off.last_root_value}")
    assert m_on == m_off, f"move differs seed={seed}: ON={m_on} OFF={m_off}"


# --------------------------------------------------------------------------- #
# 3. Determinism (same board + budget twice -> identical move + node count)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("seed", _MIDGAME_SEEDS[:5])
def test_determinism(seed):
    g, b = _midgame(seed, ply_target=45)
    if b is None:
        pytest.skip(f"seed={seed}: could not build a midgame position")
    cfg = AlphaBetaConfig(step_budget=6000, max_depth=64,
                          asp=3.0, pvs=True, killers=2, use_tt=True)
    a1 = AlphaBetaAgent(g, cfg)
    a1.clear()
    m1 = a1.move(b)
    a2 = AlphaBetaAgent(g, cfg)
    a2.clear()
    m2 = a2.move(b)
    assert m1 == m2, f"move not deterministic seed={seed}: {m1} vs {m2}"
    assert a1.nodes == a2.nodes, f"node count not deterministic: {a1.nodes} vs {a2.nodes}"
    assert a1.steps_used == a2.steps_used
    assert a1.depth_completed == a2.depth_completed


# --------------------------------------------------------------------------- #
# 4. Meeple-extension (the horizon never lands on phase==MEEPLES)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("seed", [9_200_033, 9_200_051, 4_300_000_003])
def test_meeple_extension(seed):
    """Search from a MEEPLES-phase root (where even-depth ID horizons WOULD land on
    MEEPLES); the extension must push the horizon onto the following TILES node so no
    heuristic leaf is ever evaluated at MEEPLES."""
    g, b = _midgame(seed, ply_target=40)
    if b is None:
        g, b = _near_terminal(seed, 6)
    if b is None:
        pytest.skip(f"seed={seed}: could not build a position")
    mb = _first_meeple_child(g, b)
    if mb is None:
        pytest.skip(f"seed={seed}: no meeple-phase child available")
    assert mb.state.phase == _MEEPLES
    cfg = AlphaBetaConfig(step_budget=200_000, max_depth=6,
                          asp=3.0, pvs=True, killers=2, use_tt=True)
    agent = AlphaBetaAgent(g, cfg)
    agent.clear()
    agent.move(mb)
    assert agent.horizon_meeple_hits == 0, (
        f"horizon landed on a MEEPLES node {agent.horizon_meeple_hits}x (seed={seed})")
    assert agent.extensions > 0, "meeple-extension never fired from a MEEPLES root"
    assert agent.horizon_tiles > 0, "no TILES horizon leaf was ever evaluated"


# --------------------------------------------------------------------------- #
# 5. as_manifest / leaf_hash provenance (Trap-1 mitigation)
# --------------------------------------------------------------------------- #
def test_as_manifest_shape():
    cfg = AlphaBetaConfig(step_budget=28000)
    man = cfg.as_manifest()
    assert man["agent"] == "AlphaBetaAgent"
    assert man["step_budget"] == 28000
    assert isinstance(man["leaf_hash"], str) and len(man["leaf_hash"]) == 16
    assert "leaf_cfg" in man and isinstance(man["leaf_cfg"], dict)
    # leaf_hash matches the harness recipe (c5_leaf_override._leaf_hash) on the same cfg.
    sys.path.insert(0, str(REPO / "scripts" / "classical_search"))
    from c5_leaf_override import _leaf_hash as harness_leaf_hash
    assert man["leaf_hash"] == harness_leaf_hash(cfg.resolved_leaf_cfg())


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "-x"]))
