"""Generate a fresh position bank labeled with the STRICT detectors at EVERY decision
(not gated on the broad motifs), to top up the rare high-precision motifs (esp.
MUST_BLOCK_CITY) and get a clean strong-vs-weak + competitive sample.

Snapshots strict-opportunity positions (board pkl + provenance + strict labels +
mover's actual choice), capped per-game-per-motif to limit repeated-threat inflation;
backfills the game's eventual outcome. A separate harvest_panel pass then records every
panel agent's choice on these boards.
"""
import argparse
import os
import pickle
import sys
import time
from collections import defaultdict

import numpy as np

os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.flat_leaf import flat_base_score
from wingedsheep.carcassonne.objects.game_phase import GamePhase

sys.path.insert(0, os.path.dirname(__file__))
import strict_motifs as S
import roster as R

CAP_PER_MOTIF_PER_GAME = 2

SUITE = [
    ("rod1:random", 18, 1980000),
    ("greedy:random", 14, 1981000),
    ("h6400:random", 10, 1982000),
    ("h3200:random", 12, 1983000),
    ("random:random", 10, 1984000),
    ("rod1:rod1", 14, 1985000),
    ("h800:h800", 12, 1986000),
    ("greedy:greedy", 12, 1987000),
    ("rod1:h6400", 10, 1988000),
]


def play_game(a_spec, b_spec, seed, g, regime):
    import numpy as _np
    import random as _random
    _random.seed(seed)
    _np.random.seed(seed & 0x7FFFFFFF)
    p0_spec, p1_spec = (a_spec, b_spec) if g % 2 == 0 else (b_spec, a_spec)
    p0 = R.make_player(p0_spec, seed=seed * 1009 + 1)
    p1 = R.make_player(p1_spec, seed=seed * 1009 + 2)
    players, specs = (p0, p1), (p0_spec, p1_spec)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    snaps, ply, guard = [], 0, 0
    per_motif = defaultdict(int)
    while not game.get_game_ended(board, 0) and guard < 400:
        guard += 1
        st = board.state
        mover = st.current_player
        mask = game.get_valid_moves(board)
        legal = [int(i) for i in np.flatnonzero(mask)]
        chosen = int(players[mover].choose(game, board))
        labels = S.label_strict(game, board, legal)
        fired = {m: lab for m, lab in labels.items()
                 if lab.opportunity and per_motif[m] < CAP_PER_MOTIF_PER_GAME}
        if fired:
            margin = int(st.scores[mover]) - int(st.scores[1 - mover])
            k = len(st.deck) + (1 if st.next_tile is not None else 0)
            lsum = {m: {"sat": sorted(int(x) for x in lab.satisfying), "mag": lab.magnitude,
                        "threat": lab.threat, "detail": lab.detail} for m, lab in fired.items()}
            for m in fired:
                per_motif[m] += 1
            snaps.append({
                "regime": regime, "seed": seed, "g": g, "ply": ply, "mover": mover,
                "mover_spec": specs[mover], "opp_spec": specs[1 - mover],
                "tile_phase": "TILES" if st.phase == GamePhase.TILES else "MEEPLES",
                "k_remaining": k, "scores": list(st.scores), "margin_before": margin,
                "meeples_free": list(st.meeples), "legal_n": len(legal), "chosen": chosen,
                "strict_labels": lsum,
                "board_pkl": pickle.dumps(board, protocol=pickle.HIGHEST_PROTOCOL),
            })
        board, _ = game.get_next_state(board, chosen)
        ply += 1
    term = board.state
    for s in snaps:
        mar = flat_base_score(term, s["mover"])
        s["final_margin_mover"] = int(mar)
        s["result_mover"] = "W" if mar > 0 else ("D" if mar == 0 else "L")
    return snaps


def _job(arg):
    a, b, seed, g, regime = arg
    return play_game(a, b, seed, g, regime)


def _init():
    import torch
    torch.set_num_threads(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--out", default="/mnt/c/carc-shared/strategic_ladder/strict_bank")
    args = ap.parse_args()
    k, n = (int(x) for x in args.shard.split("/"))

    jobs = []
    for regime, games, sb in SUITE:
        a, b = regime.split(":")
        for i in range(games):
            jobs.append((a, b, sb + i, i, regime))
    # heavy-first
    cost = {"h6400": 900, "h3200": 450, "rod1": 90, "h800": 120, "greedy": 5, "random": 1}
    jobs.sort(key=lambda j: -(cost.get(j[0], 30) + cost.get(j[1], 30)))
    shard = [j for i, j in enumerate(jobs) if i % n == k]
    os.makedirs(args.out, exist_ok=True)
    out_pkl = os.path.join(args.out, f"strict_shard{k}of{n}.pkl")

    from multiprocessing import get_context
    ctx = get_context("fork")
    alls, done, t0 = [], 0, time.perf_counter()
    print(f"strict-gen: {len(shard)} games (shard {k}/{n}), W={args.workers}", flush=True)
    with ctx.Pool(args.workers, initializer=_init) as pool:
        for snaps in pool.imap_unordered(_job, shard):
            alls.extend(snaps)
            done += 1
            if done % 8 == 0 or done == len(shard):
                with open(out_pkl, "wb") as f:
                    pickle.dump(alls, f, protocol=pickle.HIGHEST_PROTOCOL)
                print(f"  {done}/{len(shard)} games  snaps={len(alls)}  {time.perf_counter()-t0:.0f}s", flush=True)
    with open(out_pkl, "wb") as f:
        pickle.dump(alls, f, protocol=pickle.HIGHEST_PROTOCOL)
    cnt = defaultdict(int)
    for s in alls:
        for m in s["strict_labels"]:
            cnt[m] += 1
    print(f"DONE: {len(alls)} snaps; per-motif {dict(cnt)} -> {out_pkl}")


if __name__ == "__main__":
    main()
