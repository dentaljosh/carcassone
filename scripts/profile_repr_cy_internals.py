#!/usr/bin/env python3
"""Decompose where the ~14us/encode of flat_repr_cy.encode_board_cy goes.

Answers: is the cost the per-tile board WALK (which a shared flat_leaf
decomposition could remove) or fixed costs (np.zeros alloc + the ref-tile
broadcast fill, which it cannot)? Method: time np.zeros alone, then encode on
FEW-tile vs MANY-tile boards. If few ~= many, per-tile work is negligible and
sharing the leaf's decomposition saves ~nothing.
"""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "engine"))

import numpy as np  # noqa: E402

from carcassonne_ai import flat_repr_cy  # noqa: E402
from carcassonne_ai.board_repr import N_CHANNELS  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402


def collect(game, seed, max_plies=400):
    random.seed(seed)
    board = game.get_init_board()
    out = [board]
    plies = 0
    while game.get_game_ended(board, 0) == 0.0 and plies < max_plies:
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break
        board, _ = game.get_next_state(board, int(random.choice(legal.tolist())))
        plies += 1
        out.append(board)
    return out


def ntiles(b):
    return len(getattr(b.state, "placed_coords", []))


def main():
    game = Game()
    pool = []
    for gi in range(12):
        pool.extend(collect(game, 100 + gi))
    few = [b for b in pool if ntiles(b) <= 12]
    many = [b for b in pool if ntiles(b) >= 55]
    print(f"pool {len(pool)}  few(<=12 tiles)={len(few)}  many(>=55 tiles)={len(many)}")
    W = pool[-1].offset.size

    # warm caches
    for b in few + many:
        flat_repr_cy.encode_board_cy(b.state, 0, b.offset)

    def time_encode(boards, reps=400):
        work = [(b, p) for b in boards for p in (0, 1)]
        best = float("inf")
        for _ in range(reps):
            t0 = time.perf_counter()
            for b, p in work:
                flat_repr_cy.encode_board_cy(b.state, p, b.offset)
            best = min(best, (time.perf_counter() - t0) / len(work))
        return best * 1e6  # us/encode

    def time_alloc(reps=2000):
        best = float("inf")
        for _ in range(reps):
            t0 = time.perf_counter()
            for _ in range(50):
                np.zeros((N_CHANNELS, W, W), dtype=np.float32)
            best = min(best, (time.perf_counter() - t0) / 50)
        return best * 1e6

    t_alloc = time_alloc()
    t_few = time_encode(few)
    t_many = time_encode(many)
    nf = float(np.mean([ntiles(b) for b in few]))
    nm = float(np.mean([ntiles(b) for b in many]))
    per_tile = (t_many - t_few) / (nm - nf) if nm > nf else float("nan")

    print(f"\n  np.zeros(({N_CHANNELS},{W},{W})) alloc : {t_alloc:6.2f} us")
    print(f"  encode  few-tile (~{nf:.0f} tiles)     : {t_few:6.2f} us")
    print(f"  encode  many-tile (~{nm:.0f} tiles)    : {t_many:6.2f} us")
    print(f"  delta (many - few)                  : {t_many - t_few:6.2f} us  over {nm-nf:.0f} extra tiles")
    print(f"  => per-tile walk cost               : {per_tile:6.3f} us/tile")
    print(f"  => fixed cost (alloc + ref-fill + ovh) dominates: "
          f"{t_few:.1f}us at few-tile vs {t_alloc:.1f}us alloc alone")
    print(f"\n  INTERPRETATION: a shared flat_leaf decomposition could only remove the")
    print(f"  per-tile WALK (~{per_tile:.2f}us/tile x ~{nm:.0f} = ~{per_tile*nm:.1f}us of the {t_many:.1f}us many-tile encode);")
    print(f"  the rest is np.zeros + ref-broadcast fill, which it cannot touch.")


if __name__ == "__main__":
    main()
