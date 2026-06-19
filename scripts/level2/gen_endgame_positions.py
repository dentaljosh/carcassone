"""L2-3 endgame position-suite generator (with provenance).

Plays DETERMINISTIC greedy (RuleBasedPlayer) self-play games on a fresh seed
band and snapshots the first TILES-phase position at each target K (tiles left).
Each record is fully reconstructable via `replay_to(seed, ply)` and carries the
provenance the protocol requires (scores, meeples, bag multiset, deck order).

Greedy is a neutral, fast generator → realistic endgame boards not biased toward
any agent under test. The suite is FIXED once generated (committed) so every
agent + re-run sees identical positions.

Determinism: `random.seed(deck_seed)` fixes the engine deck shuffle (done at
get_init_board); RuleBasedPlayer uses its own fixed-seed RNG for tiebreaks; the
engine consumes no global random during play. So (deck_seed, ply) -> exact Board.

Usage:
  python scripts/level2/gen_endgame_positions.py --band 3200000000 --n 120 \
      --ks 2 3 4 5 6 --out measurement/level2/l23_positions.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.rule_based_player import RuleBasedPlayer
from wingedsheep.carcassonne.objects.game_phase import GamePhase

GEN_PLAYER_SEED = 70123     # fixed tiebreak seed for the generator policy
SOURCE_AGENT = "greedy_selfplay"


def _new_game():
    return Game(enable_legal_moves_cache=True)


def k_remaining(board) -> int:
    return len(board.state.deck) + (1 if board.state.next_tile is not None else 0)


def replay_to(seed: int, ply: int):
    """Reconstruct (game, board) at move index `ply` of greedy game `seed`.
    The canonical reconstruction used by BOTH the generator and the harness."""
    random.seed(seed)                      # fixes the deck shuffle
    game = _new_game()
    board = game.get_init_board()
    player = RuleBasedPlayer(seed=GEN_PLAYER_SEED)
    for _ in range(ply):
        mask = game.get_valid_moves(board)
        a = player.choose_action(game, board, mask)
        board, _ = game.get_next_state(board, int(a))
    return game, board


def _provenance(game, board, ply: int, seed: int) -> dict:
    s = board.state
    deck_descs = [t.description for t in s.deck]
    bag = dict(sorted(Counter(deck_descs).items()))
    return {
        "gen_id": f"g{seed}",
        "source_agent": SOURCE_AGENT,
        "seed": seed,
        "ply": ply,
        "k_remaining": k_remaining(board),
        "to_move": int(s.current_player),
        "scores": [int(s.scores[0]), int(s.scores[1])],
        "meeples": {
            "free": [int(s.meeples[0]), int(s.meeples[1])],
            "placed": [len(s.placed_meeples[0]), len(s.placed_meeples[1])],
        },
        "in_hand_tile": s.next_tile.description if s.next_tile is not None else None,
        "bag_multiset": bag,                # the hidden bag (= deck) type-multiset
        "bag_size": len(deck_descs),
        "known_order": deck_descs,          # real future order (clairvoyant mode)
        "legal_n": int(mask_sum(game, board)),
        "checksum": game.string_representation(board),
    }


def mask_sum(game, board) -> int:
    return int(game.get_valid_moves(board).sum())


def generate_game(seed: int, want_ks: set[int]) -> list[dict]:
    random.seed(seed)
    game = _new_game()
    board = game.get_init_board()
    player = RuleBasedPlayer(seed=GEN_PLAYER_SEED)
    seen: dict[int, dict] = {}
    ply = 0
    while game.get_game_ended(board, 0) == 0.0:
        if board.state.phase == GamePhase.TILES:
            k = k_remaining(board)
            if k in want_ks and k not in seen:
                seen[k] = _provenance(game, board, ply, seed)
        mask = game.get_valid_moves(board)
        a = player.choose_action(game, board, mask)
        board, _ = game.get_next_state(board, int(a))
        ply += 1
    return [seen[k] for k in sorted(seen)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--band", type=int, default=3_200_000_000)
    ap.add_argument("--n", type=int, default=120, help="number of generator games")
    ap.add_argument("--ks", type=int, nargs="+", default=[2, 3, 4, 5, 6])
    ap.add_argument("--out", default="measurement/level2/l23_positions.jsonl")
    args = ap.parse_args(argv)
    want = set(args.ks)

    records = []
    for i in range(args.n):
        seed = args.band + i
        try:
            recs = generate_game(seed, want)
            records.extend(recs)
        except Exception as e:  # noqa - a generator game dying shouldn't kill the suite
            print(f"  seed {seed} skipped: {e}", file=sys.stderr)
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{args.n} games, {len(records)} positions", flush=True)

    with open(args.out, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    by_k = Counter(r["k_remaining"] for r in records)
    print(f"wrote {len(records)} positions to {args.out}")
    print("by K:", dict(sorted(by_k.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
