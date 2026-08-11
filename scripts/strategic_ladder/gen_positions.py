"""Generate a labeled position bank for one REGIME (agent_a vs agent_b).

Plays seeded, deterministic games; at every decision labels motifs; snapshots
positions where >=1 motif opportunity fires (pickling the board for the
counterfactual panel harvest); records the MOVER's actual chosen action; and
backfills each snapshot with the game's eventual outcome (mover-perspective final
margin + W/D/L) for outcome-sanity (Part F.3).

Seats are balanced: game g uses (a as P0, b as P1) for even g, swapped for odd.
Each snapshot is tagged mover_spec / opp_spec / regime / band.

Run (example):
  .venv/bin/python scripts/strategic_ladder/gen_positions.py \
      --regime h6400:random --games 16 --seed-base 1940000 --band test \
      --max-per-game 40 --out measurement/strategic_behavior_ladder/bank
"""
import argparse
import os
import pickle
import sys
import time

import numpy as np

os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.flat_leaf import flat_base_score
from wingedsheep.carcassonne.objects.game_phase import GamePhase

sys.path.insert(0, os.path.dirname(__file__))
import motifs as M
import roster as R


def _labels_summary(labels):
    out = {}
    for m, lab in labels.items():
        if lab.opportunity:
            out[m] = {"sat": sorted(int(x) for x in lab.satisfying),
                      "mag": round(float(lab.best_magnitude), 3),
                      "detail": lab.detail}
    return out


def play_game(a_spec, b_spec, seed, g, max_per_game, regime, band):
    p0_spec, p1_spec = (a_spec, b_spec) if g % 2 == 0 else (b_spec, a_spec)
    p0 = R.make_player(p0_spec, seed=seed * 1009 + 1)
    p1 = R.make_player(p1_spec, seed=seed * 1009 + 2)
    players = (p0, p1)
    specs = (p0_spec, p1_spec)

    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    snaps = []
    ply = 0
    guard = 0
    while not game.get_game_ended(board, 0) and guard < 400:
        guard += 1
        st = board.state
        mover = st.current_player
        mask = game.get_valid_moves(board)
        legal = [int(i) for i in np.flatnonzero(mask)]
        chosen = int(players[mover].choose(game, board))

        if len(snaps) < max_per_game:
            labels = M.label_position(game, board, legal)
            lsum = _labels_summary(labels)
            if lsum:
                snap = M.position_snapshot(game, board)
                snaps.append({
                    "regime": regime, "band": band, "seed": seed, "g": g, "ply": ply,
                    "mover": mover, "mover_spec": specs[mover], "opp_spec": specs[1 - mover],
                    "tile_phase": snap["phase_tile"], "phase": snap["phase"],
                    "k_remaining": snap["k_remaining"], "scores": snap["scores"],
                    "meeples_free": snap["meeples_free"],
                    "meeples_placed": snap["meeples_placed"], "legal_n": len(legal),
                    "chosen": chosen, "labels": lsum,
                    "board_pkl": pickle.dumps(board, protocol=pickle.HIGHEST_PROTOCOL),
                })
        board, _ = game.get_next_state(board, chosen)
        ply += 1

    # eventual outcome (true end-of-game differential incl. farm scoring)
    term = board.state
    for s in snaps:
        mv = s["mover"]
        margin = flat_base_score(term, mv)
        s["final_margin_mover"] = int(margin)
        s["result_mover"] = "W" if margin > 0 else ("D" if margin == 0 else "L")
        s["game_len"] = ply
    return snaps


def _worker_init():
    import torch
    torch.set_num_threads(1)


def _play_one(arg):
    a_spec, b_spec, seed, g, max_per_game, regime, band = arg
    return play_game(a_spec, b_spec, seed, g, max_per_game, regime, band)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regime", required=True, help="agent_a:agent_b, e.g. h6400:random")
    ap.add_argument("--games", type=int, default=16)
    ap.add_argument("--seed-base", type=int, default=1940000)
    ap.add_argument("--band", choices=["dev", "test"], default="test")
    ap.add_argument("--max-per-game", type=int, default=40)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--g-start", type=int, default=0, help="first game index (for cross-box seed-range split)")
    ap.add_argument("--tag-suffix", default="", help="appended to output filename (e.g. box id)")
    ap.add_argument("--out", default="measurement/strategic_behavior_ladder/bank")
    args = ap.parse_args()

    a_spec, b_spec = args.regime.split(":")
    os.makedirs(args.out, exist_ok=True)
    tag = f"{args.band}_{a_spec}__vs__{b_spec}{args.tag_suffix}"
    out_pkl = os.path.join(args.out, f"{tag}.pkl")

    jobs = [(a_spec, b_spec, args.seed_base + args.g_start + i, args.g_start + i,
             args.max_per_game, args.regime, args.band) for i in range(args.games)]

    all_snaps = []
    t0 = time.perf_counter()
    if args.workers <= 1:
        for j in jobs:
            snaps = _play_one(j)
            all_snaps.extend(snaps)
            print(f"[{tag}] game seed={j[2]} snaps={len(snaps)} total={len(all_snaps)} "
                  f"elapsed={time.perf_counter()-t0:.0f}s", flush=True)
    else:
        from multiprocessing import get_context
        ctx = get_context("fork")
        done = 0
        with ctx.Pool(args.workers, initializer=_worker_init) as pool:
            for snaps in pool.imap_unordered(_play_one, jobs):
                all_snaps.extend(snaps)
                done += 1
                print(f"[{tag}] {done}/{len(jobs)} games done, total snaps={len(all_snaps)} "
                      f"elapsed={time.perf_counter()-t0:.0f}s", flush=True)

    with open(out_pkl, "wb") as f:
        pickle.dump(all_snaps, f, protocol=pickle.HIGHEST_PROTOCOL)
    n_opp = {m: sum(1 for s in all_snaps if m in s["labels"]) for m in M.MOTIFS}
    print(f"\nDONE {tag}: {len(all_snaps)} snapshots in {time.perf_counter()-t0:.0f}s, opp counts={n_opp}")
    print(f"wrote {out_pkl}")


if __name__ == "__main__":
    main()
