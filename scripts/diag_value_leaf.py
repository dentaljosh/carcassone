"""Step-9 NO-GO diagnostic: is the NN value head a wiring bug or a real
search-exploitation failure?

Step 9 found the pure NN-value leaf loses 396/400 to the pure v2.7 heuristic
leaf (same policy net both sides). But the screening reported held-out
value<->outcome corr +0.81. Those can only both be true if either
  (A) the value is a GOOD predictor but a BAD search leaf (off-distribution
      exploitation — a real scientific NO-GO), or
  (B) the inference/leaf path is broken (sign/POV/feature) in a way that is
      self-consistent with train_iter's own corr readout but wrong when used
      as the MCTS leaf — a WIRING bug.

This distinguishes them on FRESH states through the SAME inference path the
leaf uses (get_canonical_form -> net -> value), comparing:
  nn_v  = NN value head            (current-player POV, tanh[-1,1])
  h_v   = tanh(virtual_score_v2/15) (current-player POV, the v2.7 leaf — known good)
  out   = actual game outcome from that POV, finishing both sides with the
          1-ply heuristic policy (a strong, cheap proxy for "who's winning")

Key reads:
  - corr(nn_v, h_v) and SIGN-AGREEMENT: if strongly POSITIVE/high -> the NN
    value agrees with the heuristic on these states -> inference path is fine ->
    NO-GO is real (search exploitation). If NEGATIVE/near-zero/sign-flipped ->
    WIRING bug.
  - corr(nn_v, out) vs corr(h_v, out): replicates the screening corr on fresh
    states through the inference path. If nn_v's corr collapses here but was
    0.81 in training -> train/inference mismatch (bug).

Usage: python scripts/diag_value_leaf.py --ckpt <path> --n 60
"""
from __future__ import annotations

import argparse
import math
import os
import random
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from carcassonne_ai.evaluators import make_single_evaluator  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.network import CarcassonneNet  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2  # noqa: E402


def heuristic_action(game: Game, board) -> int:
    """1-ply greedy virtual_score (Tier-1 policy) — cheap strong-ish play."""
    import copy
    from carcassonne_ai.virtual_score import virtual_score_inplace
    from carcassonne_ai.action_space import decode
    from wingedsheep.carcassonne.utils.state_updater import StateUpdater

    mask = game.get_valid_moves(board)
    legal = np.flatnonzero(mask)
    if legal.size == 1:
        return int(legal[0])
    player = board.state.current_player
    best_a, best_s = int(legal[0]), -1e9
    for a in legal:
        st = copy.deepcopy(board.state)
        act = decode(int(a), off=board.offset, phase=st.phase.value,
                     next_tile=st.next_tile,
                     last_tile_coord=(st.last_tile_action.coordinate
                                      if st.last_tile_action is not None else None))
        StateUpdater.apply_action_inplace(game_state=st, action=act)
        s = virtual_score_inplace(st, player)
        if s > best_s:
            best_s, best_a = s, int(a)
    return best_a


def finish_outcome(game: Game, board, pov_player: int, max_plies: int = 400) -> float:
    """Play to terminal with the 1-ply heuristic for BOTH sides; return outcome
    from pov_player's POV in {+1 win, 0 draw, -1 loss}."""
    import copy
    b = type(board)(state=copy.deepcopy(board.state), total_tiles=board.total_tiles,
                    offset=board.offset)
    plies = 0
    while game.get_game_ended(b, pov_player) == 0.0 and plies < max_plies:
        a = heuristic_action(game, b)
        b, _ = game.get_next_state(b, a)
        plies += 1
    v = game.get_game_ended(b, pov_player)
    return float(v)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="/mnt/c/carc-shared/pathb_loop/ckpt/iter_11.pt")
    ap.add_argument("--n", type=int, default=60, help="states to sample")
    ap.add_argument("--skip", type=int, default=40, help="min plies before sampling")
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--no-finish", action="store_true",
                    help="skip the outcome rollout (faster; only nn vs heuristic agreement)")
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(args.ckpt, map_location=device, weights_only=False)
    n_scalar = int(ck.get("n_scalar_features", 10))
    net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                         n_scalar_features=n_scalar).to(device)
    net.load_state_dict(ck["model_state"])
    net.train(False)
    include_farm = n_scalar > 10
    game = Game(include_farm_scalars=include_farm)
    nn_eval = make_single_evaluator(net, device, game)
    print(f"ckpt={args.ckpt}  n_scalar={n_scalar} (farm={include_farm})  device={device.type}")

    rng = random.Random(args.seed)
    nn_vals, h_vals, outs = [], [], []
    sampled = 0
    g = 0
    while sampled < args.n:
        random.seed(args.seed + g)
        g += 1
        board = game.get_init_board()
        plies = 0
        # play a heuristic-ish game (random opening, heuristic mid) and snapshot
        while game.get_game_ended(board, 0) == 0.0 and plies < 300:
            if plies < args.skip:
                mask = game.get_valid_moves(board)
                legal = np.flatnonzero(mask)
                a = int(rng.choice(legal.tolist()))
            else:
                a = heuristic_action(game, board)
            board, _ = game.get_next_state(board, a)
            plies += 1
            if plies == args.skip + rng.randint(0, 30) and game.get_game_ended(board, 0) == 0.0:
                pov = board.state.current_player
                _, nn_v = nn_eval(board)
                h_v = math.tanh(virtual_score_v2(board.state, pov, DEFAULT_CONFIG) / 15.0)
                nn_vals.append(nn_v)
                h_vals.append(h_v)
                if not args.no_finish:
                    outs.append(finish_outcome(game, board, pov))
                sampled += 1
                break
        if sampled >= args.n:
            break

    nn_a = np.array(nn_vals)
    h_a = np.array(h_vals)
    def corr(x, y):
        if len(x) < 2 or np.std(x) == 0 or np.std(y) == 0:
            return float("nan")
        return float(np.corrcoef(x, y)[0, 1])

    sign_agree = float(np.mean(np.sign(nn_a) == np.sign(h_a)))
    print(f"\nstates: {len(nn_a)}")
    print(f"NN value:   mean {nn_a.mean():+.3f}  std {nn_a.std():.3f}  range [{nn_a.min():+.3f},{nn_a.max():+.3f}]")
    print(f"v2.7 value: mean {h_a.mean():+.3f}  std {h_a.std():.3f}  range [{h_a.min():+.3f},{h_a.max():+.3f}]")
    print(f"corr(NN, v2.7):       {corr(nn_a, h_a):+.3f}")
    print(f"SIGN AGREEMENT NN/v2.7: {sign_agree:.1%}   (low/inverted => WIRING bug)")
    if outs:
        o = np.array(outs)
        print(f"\noutcomes (heuristic-finished): mean {o.mean():+.2f}")
        print(f"corr(NN value,   outcome): {corr(nn_a, o):+.3f}   (screening claimed ~0.81 held-out)")
        print(f"corr(v2.7 value, outcome): {corr(h_a, o):+.3f}   (heuristic baseline ~0.61)")
        print(f"NN sign matches outcome:   {np.mean(np.sign(nn_a)==np.sign(o)):.1%}")
        print(f"v2.7 sign matches outcome: {np.mean(np.sign(h_a)==np.sign(o)):.1%}")
    print("\nREAD:")
    print("  - high corr(NN,v2.7) + high sign-agree -> inference path FINE -> NO-GO is real (search exploitation)")
    print("  - negative/near-zero corr or sign-flip -> WIRING bug (value broken as a leaf, despite training corr)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
