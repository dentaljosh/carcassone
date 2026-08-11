#!/usr/bin/env python3
"""C2 verification: MCTS transposition visit double-count fix.

Rotationally-symmetric tiles emit >=2 rotations that yield the IDENTICAL board,
so the transposition table hands both action slots the SAME child node object.
Reading children[a].N per action then counts that node's visits once per slot.

This script runs a uniform-random evaluator NeuralMCTS (the collision is purely
structural — board symmetry — so no checkpoint is needed) on real game openings,
then for each decision node checks:

  COLLISIONS: how many root children share a child object with another action
              (proves the bug condition occurs).
  RAW SUM   : sum of children[a].N over ALL actions (the OLD inflated mass).
  DEDUP SUM : sum from root_visit_distribution (the FIXED, deduped vector).

Pass criteria:
  - some collisions are observed (the bug condition is real), AND
  - the FIXED root_visit_distribution has NO two actions sharing a child, AND
  - dedup-sum < raw-sum exactly when collisions exist (mass was inflated and is
    now corrected), AND dedup-sum == sum of UNIQUE child Ns.

Usage: python scripts/verify_mcts_transposition_fix.py --n 40 --sims 64
"""
import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "engine"))

import numpy as np

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import NeuralMCTS


def uniform_evaluator(game):
    def _ev(board):
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        p = np.zeros_like(mask, dtype=np.float32)
        if legal.size:
            p[legal] = 1.0 / legal.size
        return p, 0.0
    return _ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40, help="number of decision nodes to probe")
    ap.add_argument("--sims", type=int, default=64)
    ap.add_argument("--seed-start", type=int, default=0)
    args = ap.parse_args()

    game = Game()
    ev = uniform_evaluator(game)

    nodes_probed = 0
    nodes_with_collision = 0
    nodes_with_visited_collision = 0
    total_colliding_actions = 0
    raw_gt_dedup_with_collision = 0
    dedup_has_collision = 0        # FIX BROKEN if > 0
    dedup_ne_unique = 0           # FIX BROKEN if > 0
    sel_groups = 0                # collision groups checked (selection side)
    sel_alias_bad = 0            # FIX BROKEN if > 0: group not (n-1 aliases + 1 repr)
    seed = args.seed_start

    while nodes_probed < args.n:
        seed += 1
        random.seed(seed)
        mcts = NeuralMCTS(game, ev, simulations=args.sims, c_puct=3.0, seed=seed)
        board = game.get_init_board()
        # advance a random number of plies so we sample openings AND midgame
        # (where symmetric straight tiles create the most collisions)
        target_ply = (seed % 20)
        for _ in range(target_ply):
            if board.state.is_terminated():
                break
            mask = game.get_valid_moves(board)
            legal = np.flatnonzero(mask)
            if legal.size == 0:
                break
            board, _ = game.get_next_state(board, int(random.choice(legal)))
        if board.state.is_terminated():
            continue

        mcts.clear()
        mcts.search(board)
        root_key = game.string_representation(board)
        root = mcts._nodes[root_key]
        if not root.children:
            continue
        nodes_probed += 1

        # --- raw (pre-fix) view: per-action child.N over ALL actions ---
        raw_sum = sum(c.N for c in root.children.values())

        # --- collision count: actions sharing a child object ---
        by_id = {}
        for a, c in root.children.items():
            by_id.setdefault(id(c), []).append(a)
        colliding = {cid: acts for cid, acts in by_id.items() if len(acts) > 1}
        n_collide_actions = sum(len(acts) for acts in colliding.values())
        if colliding:
            nodes_with_collision += 1
            total_colliding_actions += n_collide_actions
            # A collision only INFLATES the raw sum if the shared child was
            # actually visited (N>0). Unvisited collisions contribute 0 to both
            # raw and dedup sums (0==0), so they can't satisfy raw>dedup — the
            # criterion below must only require inflation for VISITED collisions,
            # else a correct fix FALSE-FAILs whenever a colliding child has N=0.
            if any(root.children[acts[0]].N > 0 for acts in colliding.values()):
                nodes_with_visited_collision += 1
            # --- selection-side (PUCT) alias structure check ---
            # Each collision group must have exactly one representative in
            # child_canon and (n-1) members flagged as aliases (skipped in PUCT),
            # with the representative carrying the folded prior_bonus.
            for cid, acts in colliding.items():
                sel_groups += 1
                canon = root.child_canon.get(cid)
                n_alias = sum(1 for a in acts if a in root.child_aliases)
                if canon is None or n_alias != len(acts) - 1 or canon in root.child_aliases:
                    sel_alias_bad += 1

        # --- fixed view: root_visit_distribution (deduped) ---
        counts, actions = mcts.root_visit_distribution(board)
        dedup_sum = float(counts.sum())

        # no two returned actions may share a child object
        ret_ids = [id(root.children[a]) for a in actions]
        if len(ret_ids) != len(set(ret_ids)):
            dedup_has_collision += 1

        # dedup sum must equal the sum over UNIQUE child objects
        unique_sum = sum(root.children[acts[0]].N for acts in by_id.values())
        if abs(dedup_sum - unique_sum) > 1e-9:
            dedup_ne_unique += 1

        if colliding and dedup_sum < raw_sum - 1e-9:
            raw_gt_dedup_with_collision += 1

    print(f"\n=== C2 MCTS transposition verification "
          f"({nodes_probed} decision nodes, sims={args.sims}) ===")
    print(f"nodes WITH >=1 collision:        {nodes_with_collision} "
          f"({100*nodes_with_collision/max(1,nodes_probed):.1f}%)")
    print(f"  of which VISITED (N>0):        {nodes_with_visited_collision}")
    print(f"total colliding action slots:    {total_colliding_actions}")
    print(f"nodes where raw>dedup (inflated): {raw_gt_dedup_with_collision} "
          f"(must == {nodes_with_visited_collision})")
    print(f"FIXED vector still has collision: {dedup_has_collision}  (must be 0)")
    print(f"dedup-sum != unique-child-sum:    {dedup_ne_unique}  (must be 0)")
    print(f"selection alias groups checked:   {sel_groups}")
    print(f"selection alias structure BAD:    {sel_alias_bad}  (must be 0)")
    ok = (
        nodes_with_collision > 0
        and dedup_has_collision == 0
        and dedup_ne_unique == 0
        and raw_gt_dedup_with_collision == nodes_with_visited_collision
        and sel_groups > 0
        and sel_alias_bad == 0
    )
    print(f"VERDICT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
