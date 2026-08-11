"""F3 — instrumented root-determinization PIMC capture (the comparison harness core).

Re-runs the production fair champion's ``_pimc_move`` loop (byte-identical seeds,
determinizations, and per-world ``NeuralMCTS`` search) but KEEPS the per-world
trees so the harness can read the full per-world action-value matrix
``M[world w][action a] = (N_{w,a}, Q_{w,a})`` (§3.1) that the production agent
discards. From one capture it derives the four §3.1 selectors on COMMON RANDOM
NUMBERS (all read the same trees):

  (a) production pooled-Q     — ``pooled_q_argmax`` (the thing on trial)
  (b) pooled-N               — visit-count argmax
  (c) coverage-corrected E[Q] — unweighted world-mean with an imputed value for
                                worlds that never visited the action (neutral =
                                that world's root value; pessimistic = its
                                min-child Q). Review M4 arm 3.
  (d) exact optimum          — from endgame_solver (computed by the caller).

Root-action space is IDENTICAL across the k determinizations: the reshuffle only
permutes the UNSEEN deck; ``next_tile`` (the revealed in-hand tile) and the board
are untouched, so every world shares the same root legal actions — which is what
makes the cross-world matrix, coverage, and the four picks comparable at all.

All values are ROOT-PLAYER perspective (higher = better for the mover), the same
sign convention as ``pool_root_stats`` / ``pooled_q_argmax`` (which sign child W
into the root player's POV). So every selector is a plain argmax — no per-player
branch. Pure CPU, net-free.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

import numpy as np

from carcassonne_ai.fair_agent import (
    FairHeuristicMCTSAgent,
    pool_root_stats,
    pooled_q_argmax,
    DEFAULT_MIN_POOLED_VISITS,
)
from carcassonne_ai.heuristic_prior_mcts import make_heuristic_prior_evaluator
from carcassonne_ai.mcts import NeuralMCTS


# --------------------------------------------------------------------------- #
# Champion construction (single point; routes through champion_factory so the   #
# leaf is runtime-verified curve125 — the R1/R7-class guard).                   #
# --------------------------------------------------------------------------- #
def build_champion_eval(game, *, verify: bool = True):
    """Return (cfg, evaluator, manifest) for the production fair champion.

    The cfg is the curve125 HeuristicPriorConfig (c1.5/tau5/float/visits/vn15);
    the evaluator is the stateless heuristic-prior evaluator the fair champion
    wires internally (net=None). verify=True proves the leaf on real boards.
    Requires the production leaf env (``import env_preamble`` first)."""
    from carcassonne_ai import champion_factory as CF

    spec = CF.load_production_spec()
    leaf_cfg = CF.production_leaf_cfg(spec)
    cfg = CF.production_prior_cfg(spec, leaf_cfg)
    manifest = CF.resolved_manifest("fair", spec, leaf_cfg, cfg, verify=verify)
    evaluator = make_heuristic_prior_evaluator(game, cfg)
    return cfg, evaluator, manifest


# --------------------------------------------------------------------------- #
# Per-world tree read-out                                                       #
# --------------------------------------------------------------------------- #
def _deduped_children(root):
    """[(action, child)] with rotation-alias transposition collisions removed
    (lowest action kept) — the pool_root_stats / MCTS.best_action convention."""
    out = []
    seen: set[int] = set()
    for a in sorted(root.children):
        child = root.children[a]
        if id(child) in seen:
            continue
        seen.add(id(child))
        out.append((int(a), child))
    return out


def world_matrix(root) -> dict:
    """{action: (N, Q_rootPOV)} for one search tree's VISITED, deduped root
    children. Q is signed into the ROOT player's perspective (exactly the
    pool_root_stats sign rule) so higher = better for the mover."""
    m: dict[int, tuple] = {}
    for a, ch in _deduped_children(root):
        if ch.N <= 0:
            continue
        sw = ch.W if ch.player_to_move == root.player_to_move else -ch.W
        m[a] = (int(ch.N), float(sw) / float(ch.N))
    return m


def _greedy_policy_map(mcts) -> dict:
    """{observable state_key: mover-greedy action} over EVERY visited node in the
    tree — the world's continuation policy π_w (conditions only on the observable
    state, since string_representation excludes the hidden deck). At each node the
    mover picks argmax (Q in the node-mover POV, N) over its visited deduped
    children — the best_action rule."""
    pol: dict[str, int] = {}
    for key, node in mcts._nodes.items():
        best_a, best_score = None, None
        for a, ch in _deduped_children(node):
            if ch.N <= 0:
                continue
            q = ch.Q if ch.player_to_move == node.player_to_move else -ch.Q
            score = (q, ch.N)
            if best_score is None or score > best_score:
                best_score, best_a = score, a
        if best_a is not None:
            pol[key] = best_a
    return pol


@dataclass
class WorldTree:
    det_board: object                 # concrete reshuffled determinization Board
    root_value: float                 # root-POV backed-up root value (root.Q)
    matrix: dict = field(default_factory=dict)     # {action: (N, Q_rootPOV)}
    policy_map: dict = field(default_factory=dict)  # {state_key: action} (π_w)
    min_q: float = 0.0                # min root-POV child Q (pessimistic impute)


@dataclass
class PimcCapture:
    root_player: int
    legal: list
    root_key: str
    worlds: list                      # list[WorldTree]
    agg_n: dict                       # pooled visit counts (== last_pooled_visits)
    agg_w: dict                       # pooled root-POV W
    coverage: dict                    # {action: c(a)} = #worlds visiting a
    k_dets: int
    sims: int
    min_visits: int = DEFAULT_MIN_POOLED_VISITS


def capture_pimc(game, board, cfg, evaluator, *, k_dets: int, sims: int,
                 seed: int, move_idx: int = 0,
                 min_visits: int = DEFAULT_MIN_POOLED_VISITS,
                 keep_policy: bool = True) -> PimcCapture:
    """Replay the champion's PIMC at (seed, move_idx) and capture every world.

    Seeds are byte-identical to ``FairHeuristicPriorAgent._pimc_move``:
    ``base = (seed*1_000_003 + move_idx*8191) & 0x7FFFFFFF``; the deck-reshuffle
    RNG is ``Random(base+1)``; determinization i's tree seed is ``base+100+i``.
    So the pooled (agg_n, agg_w) here equal the production agent's exactly."""
    legal = np.flatnonzero(game.get_valid_moves(board)).astype(int).tolist()
    if len(legal) < 2:
        raise ValueError(f"capture_pimc needs >=2 legal actions, got {len(legal)}")
    root_player = int(board.state.current_player)
    root_key = game.string_representation(board)

    base = (seed * 1_000_003 + move_idx * 8191) & 0x7FFFFFFF
    det_rng = random.Random(base + 1)
    agg_n: dict = {}
    agg_w: dict = {}
    from collections import defaultdict
    agg_n = defaultdict(float)
    agg_w = defaultdict(float)
    coverage: dict = defaultdict(int)
    worlds: list = []

    for i in range(k_dets):
        b = FairHeuristicMCTSAgent.reshuffled_determinization(board, det_rng)
        m = NeuralMCTS(game=game, evaluator=evaluator, simulations=sims,
                       c_puct=float(cfg.c_puct), seed=base + 100 + i)
        m.search(b)
        root = m._nodes.get(root_key) or m._nodes[game.string_representation(b)]
        # pooled stats — verbatim the production harvester (parity contract).
        pool_root_stats(root, agg_n, agg_w)
        mat = world_matrix(root)
        for a in mat:
            coverage[a] += 1
        rv = float(root.W) / float(root.N) if root.N > 0 else 0.0
        min_q = min((q for (_n, q) in mat.values()), default=0.0)
        pol = _greedy_policy_map(m) if keep_policy else {}
        worlds.append(WorldTree(det_board=b, root_value=rv, matrix=mat,
                                policy_map=pol, min_q=min_q))
        m.clear()

    return PimcCapture(root_player=root_player, legal=legal, root_key=root_key,
                       worlds=worlds, agg_n=dict(agg_n), agg_w=dict(agg_w),
                       coverage=dict(coverage), k_dets=k_dets, sims=sims,
                       min_visits=min_visits)


# --------------------------------------------------------------------------- #
# The four selectors (§3.1) — free functions so tests can exercise them on a    #
# synthetic capture / matrix without running any search.                        #
# --------------------------------------------------------------------------- #
def pooled_q_pick(cap: PimcCapture) -> int:
    """(a) production pooled-Q — byte-for-byte fair_agent.pooled_q_argmax."""
    return int(pooled_q_argmax(cap.agg_n, cap.agg_w, cap.min_visits))


def pooled_n_pick(cap: PimcCapture) -> int:
    """(b) pooled visit-count argmax (N primary, lowest action tiebreak)."""
    if not cap.agg_n:
        raise ValueError("pooled_n_pick: no visited actions")
    return int(max(cap.agg_n, key=lambda a: (cap.agg_n[a], -a)))


def covq_values(cap: PimcCapture, impute: str = "neutral") -> dict:
    """(c) coverage-corrected expected-Q per action: unweighted mean over ALL k
    worlds of the root-POV Q, imputing worlds that never visited the action.

    impute='neutral'     -> that world's root value (root.Q).
    impute='pessimistic' -> that world's min-child Q (counts adverse missing
                            worlds against the action)."""
    if impute not in ("neutral", "pessimistic"):
        raise ValueError(f"impute must be 'neutral'|'pessimistic'; got {impute!r}")
    cand = sorted(cap.agg_n)                    # actions visited in >=1 world
    out: dict[int, float] = {}
    for a in cand:
        qs = []
        for w in cap.worlds:
            if a in w.matrix:
                qs.append(w.matrix[a][1])
            elif impute == "neutral":
                qs.append(w.root_value)
            else:
                qs.append(w.min_q)
        out[a] = float(np.mean(qs)) if qs else float("-inf")
    return out


def covq_pick(cap: PimcCapture, impute: str = "neutral") -> int:
    """argmax of covq_values (root-POV, so higher = better; lowest-action tiebreak)."""
    vals = covq_values(cap, impute)
    if not vals:
        raise ValueError("covq_pick: no candidate actions")
    return int(max(vals, key=lambda a: (vals[a], -a)))


def all_picks(cap: PimcCapture) -> dict:
    """The four PIMC selectors (d/exact is computed elsewhere from the solver)."""
    return {
        "pooled_q": pooled_q_pick(cap),
        "pooled_n": pooled_n_pick(cap),
        "covq_neutral": covq_pick(cap, "neutral"),
        "covq_pessimistic": covq_pick(cap, "pessimistic"),
    }
