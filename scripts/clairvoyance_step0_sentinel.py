"""Step 0 — prove the PRODUCTION search is deck-order CLAIRVOYANT.

The measurement-first spec (docs/MEASUREMENT_FIRST_SPEC_2026-06-18.md §8 gate 1)
requires confirming, before building any non-clairvoyant agent, that the current
search actually plans along the true future draw order. If draws were already
sampled, sub-problem (A) would be moot.

THE SENTINEL (Joshua's guardrail #1): construct a real mid-game decision node,
then make several copies whose PUBLIC STATE and REMAINING MULTISET are IDENTICAL
but whose future draw ORDER differs (shuffle `state.deck`, keep `next_tile`).
Run the production clairvoyant NeuralMCTS (fair_chance=False) on each copy with
the SAME mcts seed, so the ONLY differing input is the unseen deck order. Record
whether the root action / root value change.

  - root action/value CHANGE across permutations  → search USES the future order
    → CLAIRVOYANT confirmed (proceed to the gap experiment).
  - root action/value INVARIANT                    → search already determinized
    → (A) is moot; jump to the ladder.

Determinism anchor: perm 0 keeps the original deck order and is run TWICE; those
two must be byte-identical (fixed seed ⇒ deterministic), proving any variation in
the shuffled perms is caused by deck ORDER, not RNG.

Single process, cheap (~a handful of positions x ~6 searches x 200 sims).

Usage (production iter8 config):

  CARCASSONNE_V25_CAP=12 CARCASSONNE_V25_DROP_THREE_OPEN=1 \
  CARCASSONNE_V25_VALUE_BLEND=0 CARCASSONNE_USE_FLAT_LEAF=1 \
  python -u scripts/clairvoyance_step0_sentinel.py \
      --checkpoint /mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt \
      --residual-scale 0.25 --sims 200 --c-puct 3.0 \
      --positions 8 --perms 6 --out measurement/clairvoyance/step0_sentinel.json
"""
from __future__ import annotations

import argparse
import copy
import dataclasses
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import torch

from carcassonne_ai.evaluators import make_single_evaluator, make_v25_value_wrapper
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import NeuralMCTS
from carcassonne_ai.network import CarcassonneNet
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG


def _multiset(board) -> tuple:
    """Sorted tuple of remaining-deck tile descriptions = the PUBLIC bag contents
    (order-independent). Two boards with the same multiset differ only in order."""
    return tuple(sorted(t.description for t in board.state.deck))


def _make_clair_mcts(net, device, sims, c_puct, seed, include_farm, residual_scale):
    """A fresh PRODUCTION clairvoyant agent (fair_chance=False) + its own Game."""
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=include_farm)
    base = make_single_evaluator(net, device, game)
    if residual_scale is None:
        leaf = make_v25_value_wrapper(base)
    else:
        cfg = dataclasses.replace(DEFAULT_CONFIG, residual_scale=float(residual_scale))
        leaf = make_v25_value_wrapper(base, cfg)
    mcts = NeuralMCTS(game=game, evaluator=leaf, simulations=sims, c_puct=c_puct,
                      seed=seed, fair_chance=False)
    return game, mcts


def _root_action_value(net, device, board, *, sims, c_puct, seed, include_farm,
                       residual_scale):
    """Run ONE clairvoyant search on `board` and return (best_action_by_visits,
    root_value, visit_dict). A fresh agent each call so no tree carries over; the
    seed is identical across calls so RNG is held fixed."""
    game, mcts = _make_clair_mcts(net, device, sims, c_puct, seed, include_farm,
                                  residual_scale)
    # Re-key the board onto this agent's Game (string key only depends on public
    # state; deck ORDER is intentionally NOT in the key — the very property under test).
    b = copy.deepcopy(board)
    b._str_repr_cache = None
    visits = mcts.search(b)
    val = mcts.root_value(b)
    best = max(visits, key=lambda a: (visits[a], -a)) if visits else -1
    return int(best), float(val), {int(a): int(n) for a, n in visits.items()}


def _harvest_positions(game, n_positions, min_deck, seed0):
    """Play random-ish games forward to collect mid-game decision boards with at
    least `min_deck` tiles left in the bag (so a reshuffle is meaningful)."""
    boards = []
    g = seed0
    while len(boards) < n_positions:
        rng = np.random.default_rng(g)
        board = game.get_init_board()
        # advance a random number of plies into the midgame
        target_ply = int(rng.integers(8, 24))
        ply = 0
        ok = True
        while ply < target_ply:
            if game.get_game_ended(board, 0) != 0.0:
                ok = False
                break
            mask = game.get_valid_moves(board)
            legal = np.flatnonzero(mask)
            if legal.size == 0:
                ok = False
                break
            a = int(rng.choice(legal))
            board, _ = game.get_next_state(board, a)
            ply += 1
        g += 1
        if not ok:
            continue
        if game.get_game_ended(board, 0) != 0.0:
            continue
        if len(board.state.deck) < min_deck:
            continue
        if board.state.next_tile is None:
            continue
        boards.append((g - 1, ply, board))
    return boards


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="clairvoyance_step0_sentinel")
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--residual-scale", type=float, default=None)
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--c-puct", type=float, default=3.0)
    ap.add_argument("--positions", type=int, default=8)
    ap.add_argument("--perms", type=int, default=6, help="deck-order permutations per position (perm 0 = original, run twice)")
    ap.add_argument("--min-deck", type=int, default=20, help="min remaining tiles for a position to qualify")
    ap.add_argument("--mcts-seed", type=int, default=1234, help="FIXED across all perms so only deck order varies")
    ap.add_argument("--harvest-seed", type=int, default=900000000)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(str(args.checkpoint), map_location=device, weights_only=False)
    ns = int(ck.get("n_scalar_features", 10))
    include_farm = ns > 10
    net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                         n_scalar_features=ns,
                         value_global_pool=bool(ck.get("value_global_pool", False))
                         ).to(device)
    net.load_state_dict(ck["model_state"])
    net.train(False)

    print(f"[step0] device={device} ckpt={args.checkpoint.name} ns={ns} "
          f"include_farm={include_farm} residual_scale={args.residual_scale} "
          f"sims={args.sims} c={args.c_puct}", flush=True)

    hgame = Game(enable_legal_moves_cache=True, include_farm_scalars=include_farm)
    positions = _harvest_positions(hgame, args.positions, args.min_deck, args.harvest_seed)
    print(f"[step0] harvested {len(positions)} midgame positions", flush=True)

    records = []
    n_action_changes = 0
    n_value_changes = 0
    determinism_ok = True
    for idx, (gseed, ply, board) in enumerate(positions):
        mset = _multiset(board)
        next_desc = board.state.next_tile.description
        perm_results = []
        # perm 0: original order (run TWICE as the determinism anchor)
        a0, v0, vd0 = _root_action_value(net, device, board, sims=args.sims,
                                         c_puct=args.c_puct, seed=args.mcts_seed,
                                         include_farm=include_farm,
                                         residual_scale=args.residual_scale)
        a0b, v0b, _ = _root_action_value(net, device, board, sims=args.sims,
                                         c_puct=args.c_puct, seed=args.mcts_seed,
                                         include_farm=include_farm,
                                         residual_scale=args.residual_scale)
        det = (a0 == a0b) and (abs(v0 - v0b) < 1e-9)
        determinism_ok = determinism_ok and det
        perm_results.append({"perm": 0, "shuffled": False, "action": a0, "value": v0})
        # perms 1..P-1: reshuffled deck (same multiset, fixed next_tile, fixed mcts seed)
        for pi in range(1, args.perms):
            b = copy.deepcopy(board)
            rng = np.random.default_rng(10_000 + 31 * idx + pi)
            order = list(range(len(b.state.deck)))
            rng.shuffle(order)
            b.state.deck = [b.state.deck[i] for i in order]
            b._str_repr_cache = None
            # invariants: multiset preserved, revealed tile untouched
            assert _multiset(b) == mset, "reshuffle changed the multiset!"
            assert b.state.next_tile.description == next_desc, "reshuffle touched next_tile!"
            a, v, _ = _root_action_value(net, device, b, sims=args.sims,
                                         c_puct=args.c_puct, seed=args.mcts_seed,
                                         include_farm=include_farm,
                                         residual_scale=args.residual_scale)
            perm_results.append({"perm": pi, "shuffled": True, "action": a, "value": v})

        actions = [r["action"] for r in perm_results]
        values = [r["value"] for r in perm_results]
        n_distinct_actions = len(set(actions))
        vspread = max(values) - min(values)
        action_changed = n_distinct_actions > 1
        value_changed = vspread > 1e-6
        n_action_changes += int(action_changed)
        n_value_changes += int(value_changed)
        rec = {
            "idx": idx, "harvest_seed": gseed, "ply": ply,
            "deck_remaining": len(board.state.deck), "next_tile": next_desc,
            "n_legal": len(vd0),
            "determinism_ok": det,
            "n_distinct_actions": n_distinct_actions,
            "value_spread": round(vspread, 6),
            "action_changed": action_changed, "value_changed": value_changed,
            "perms": perm_results,
        }
        records.append(rec)
        print(f"  pos {idx}: deck={len(board.state.deck)} legal={len(vd0)} "
              f"det={det} distinct_actions={n_distinct_actions} "
              f"value_spread={vspread:.4f} "
              f"{'CLAIRVOYANT' if (action_changed or value_changed) else 'invariant'}",
              flush=True)

    np_ = len(positions)
    clairvoyant = (n_value_changes > 0 or n_action_changes > 0)
    summary = {
        "n_positions": np_,
        "determinism_ok_all": determinism_ok,
        "n_positions_action_changed": n_action_changes,
        "n_positions_value_changed": n_value_changes,
        "frac_value_changed": (n_value_changes / np_) if np_ else 0.0,
        "frac_action_changed": (n_action_changes / np_) if np_ else 0.0,
        "verdict": "CLAIRVOYANT" if clairvoyant else "INVARIANT/determinized",
        "config": {"checkpoint": str(args.checkpoint), "residual_scale": args.residual_scale,
                   "sims": args.sims, "c_puct": args.c_puct, "perms": args.perms,
                   "mcts_seed": args.mcts_seed, "min_deck": args.min_deck},
    }
    out = {"summary": summary, "positions": records}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)

    print("\n=== STEP 0 SENTINEL — VERDICT ===")
    print(f"positions: {np_}   determinism_ok(all): {determinism_ok}")
    print(f"positions where root VALUE changed with deck order:  {n_value_changes}/{np_}")
    print(f"positions where root ACTION changed with deck order: {n_action_changes}/{np_}")
    if not determinism_ok:
        print("⚠ DETERMINISM BROKEN — same deck order gave different output; "
              "results are confounded by RNG, not deck order. Investigate before trusting.")
    if clairvoyant:
        print("VERDICT: production search IS deck-order CLAIRVOYANT — the root action/value "
              "depend on the unseen future draw order. Proceed to the clairvoyance-gap experiment.")
    else:
        print("VERDICT: search is INVARIANT to deck order — already determinized; "
              "sub-problem (A) is moot, go straight to the ladder.")
    print(f"wrote {args.out}")
    return 0 if determinism_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
