"""Bit-exactness guard for the window-overflow audit instrumentation.

Plays a fixed set of deterministic games (first-legal-action policy) and prints
a SHA256 over the concatenation of every get_valid_moves mask, plus the number
of audit records drained. Run once with CARCASSONNE_WINDOW_AUDIT unset and once
with =1; the mask hash MUST be identical (proving the audit block does not touch
the returned mask), while the record count is 0 when off and >0 when on.
"""
import hashlib
import os
import random
import sys

import numpy as np

from carcassonne_ai.game_wrapper import (
    Game,
    drain_window_audit,
    window_audit_enabled,
)


def play_and_hash(n_games: int, window_size: int = 25) -> tuple[str, int]:
    h = hashlib.sha256()
    game = Game(window_size=window_size, enable_legal_moves_cache=False)
    for gi in range(n_games):
        random.seed(1000 + gi)  # fix the deck shuffle so both runs replay the same games
        board = game.get_init_board()
        ply = 0
        while game.get_game_ended(board, board.state.current_player) == 0.0:
            mask = game.get_valid_moves(board)
            h.update(mask.tobytes())
            legal = np.flatnonzero(mask)
            if len(legal) == 0:
                break
            # Deterministic policy: rotate the choice a little by ply so games
            # differ, but stay fully reproducible across runs.
            a = int(legal[(gi * 7 + ply * 3) % len(legal)])
            board, _ = game.get_next_state(board, a)
            ply += 1
    return h.hexdigest(), len(drain_window_audit())


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    digest, n_records = play_and_hash(n)
    print(f"audit_enabled={window_audit_enabled()} "
          f"mask_sha256={digest} audit_records={n_records}")
