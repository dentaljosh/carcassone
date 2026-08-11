"""C2 regression guard: MCTS transposition visit double-count fix.

Ported from scripts/verify_mcts_transposition_fix.py into pytest. Rotationally
symmetric tiles emit >=2 rotations that yield the IDENTICAL board, so the
transposition table hands both action slots the SAME child node. Summing
children[a].N per action then counts that node's visits once per slot (the bug).

Asserts the FIXED views are collision-free:
  - root_visit_distribution returns no two actions sharing a child object,
  - its mass == sum over UNIQUE child objects (not raw per-action sum),
  - raw>dedup exactly when a VISITED collision exists (mass really was inflated),
  - the selection-side alias structure holds (1 canonical + n-1 aliases per group).

Teeth check: requires that collisions are actually observed in the sample.
"""
from __future__ import annotations

import random

import numpy as np

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import NeuralMCTS

N_NODES = 30
SIMS = 64


def _uniform_evaluator(game):
    def _ev(board):
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        p = np.zeros_like(mask, dtype=np.float32)
        if legal.size:
            p[legal] = 1.0 / legal.size
        return p, 0.0
    return _ev


def test_mcts_transposition_visit_dedup():
    game = Game()
    ev = _uniform_evaluator(game)

    nodes_probed = 0
    nodes_with_collision = 0
    nodes_with_visited_collision = 0
    raw_gt_dedup_with_collision = 0
    sel_groups = 0
    seed = 0

    while nodes_probed < N_NODES and seed < N_NODES * 50:
        seed += 1
        random.seed(seed)
        mcts = NeuralMCTS(game, ev, simulations=SIMS, c_puct=3.0, seed=seed)
        board = game.get_init_board()
        for _ in range(seed % 20):  # sample openings + midgame
            if board.state.is_terminated():
                break
            legal = np.flatnonzero(game.get_valid_moves(board))
            if legal.size == 0:
                break
            board, _ = game.get_next_state(board, int(random.choice(legal)))
        if board.state.is_terminated():
            continue

        mcts.clear()
        mcts.search(board)
        root = mcts._nodes[game.string_representation(board)]
        if not root.children:
            continue
        nodes_probed += 1

        raw_sum = sum(c.N for c in root.children.values())
        by_id = {}
        for a, c in root.children.items():
            by_id.setdefault(id(c), []).append(a)
        colliding = {cid: acts for cid, acts in by_id.items() if len(acts) > 1}

        if colliding:
            nodes_with_collision += 1
            if any(root.children[acts[0]].N > 0 for acts in colliding.values()):
                nodes_with_visited_collision += 1
            for cid, acts in colliding.items():
                sel_groups += 1
                canon = root.child_canon.get(cid)
                n_alias = sum(1 for a in acts if a in root.child_aliases)
                # FIXED: each group = 1 canonical (not itself an alias) + n-1 aliases
                assert canon is not None, "collision group missing a canonical child"
                assert canon not in root.child_aliases
                assert n_alias == len(acts) - 1, (
                    f"alias structure broken: {n_alias} aliases for group of {len(acts)}"
                )

        counts, actions = mcts.root_visit_distribution(board)
        dedup_sum = float(counts.sum())

        # FIXED vector must share no child object across returned actions
        ret_ids = [id(root.children[a]) for a in actions]
        assert len(ret_ids) == len(set(ret_ids)), "C2 REGRESSION: dedup vector has collision"

        # dedup mass == sum over UNIQUE child objects
        unique_sum = sum(root.children[acts[0]].N for acts in by_id.values())
        assert abs(dedup_sum - unique_sum) < 1e-9, (
            f"C2 REGRESSION: dedup mass {dedup_sum} != unique-child sum {unique_sum}"
        )
        if colliding and dedup_sum < raw_sum - 1e-9:
            raw_gt_dedup_with_collision += 1

    assert nodes_probed > 0, "no decision nodes probed — test has no teeth"
    assert nodes_with_collision > 0, (
        "no transposition collisions observed — test isn't exercising the bug path"
    )
    # raw was inflated above dedup exactly on the visited-collision nodes
    assert raw_gt_dedup_with_collision == nodes_with_visited_collision
