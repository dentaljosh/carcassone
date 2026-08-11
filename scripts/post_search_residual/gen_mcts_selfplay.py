#!/usr/bin/env python3
"""Post-Search Residual Pilot — Phase B: generate REAL MCTS-play games (not greedy).

The Stage-2 gate ran on greedy-self-play roots (replay_to = 1-ply greedy line). The spec requires
broadening to the real MCTS-play distribution before training. We self-play HeuristicMCTS(200, v2.9)
— the *base agent* of the adaptive system, so the positions it reaches are exactly the ones the
system would face — and record each game's **deck seed + full action sequence**. Reconstruction is
lossless and engine-exact: re-seed the deck, get_init_board, apply the recorded actions to any ply
(the engine consumes no global random during play; only the deck shuffle at init does — see
gen_endgame_positions.replay_to).

Net-free, pure CPU. Frozen v2.9 leaf (config_hash 7fc930b82801cb43). Output: games.jsonl, one line
per game {game_id, seed, actions:[...], n_plies, winner, check_ply, check_str}.
"""
from __future__ import annotations
import os
os.environ["CARCASSONNE_V25_CAP"] = "8"
os.environ["CARCASSONNE_V25_OPP_CAP"] = "8"
os.environ["CARCASSONNE_V25_DROP_THREE_OPEN"] = "0"
os.environ["CARCASSONNE_V29_MEEPLE_CURVE"] = "-8,-4,-1,0,2,3,4,5"
os.environ["CARCASSONNE_V25_MEEPLE_K"] = "2.0"
os.environ["CARCASSONNE_USE_FLAT_LEAF"] = "1"
os.environ["CARCASSONNE_USE_CY_REPR"] = "1"
os.environ["CARCASSONNE_V25_VALUE_BLEND"] = "0"
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse, json, random, sys, time
from pathlib import Path
from multiprocessing import get_context

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(REPO / "scripts" / "feature_graph"))

import eval_hybrid_handoff as EH                          # noqa: E402
from carcassonne_ai.game_wrapper import Game              # noqa: E402
from carcassonne_ai.mcts import HeuristicMCTS             # noqa: E402

OUT = REPO / "measurement" / "post_search_residual" / "data"
SIMS = 200
ROLLOUT_LIMIT = 400          # defensive cap on game length

_W: dict = {}


def replay_actions(seed: int, actions, ply: int):
    """Lossless reconstruction of an MCTS game at move index `ply`. Re-seed the deck
    (random.seed fixes get_init_board's shuffle), then apply the recorded actions[:ply].
    The engine consumes no global random during play -> exact Board. Returns (game, board)."""
    random.seed(int(seed))
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    board = game.get_init_board()
    for a in actions[:ply]:
        board, _ = game.get_next_state(board, int(a))
    return game, board


def _worker_init(cfg_norm):
    _W["agent"] = HeuristicMCTS(
        game=Game(enable_legal_moves_cache=True, include_farm_scalars=True),
        simulations=SIMS, heur_leaf="v2_7", leaf_cfg=EH._heur_leaf_cfg(cfg_norm), seed=0,
    )
    _W["mgame"] = Game(enable_legal_moves_cache=True, include_farm_scalars=True)


def _gen_game(seed):
    try:
        agent = _W["agent"]
        mgame = _W["mgame"]
        random.seed(int(seed))                 # deck shuffle
        board = mgame.get_init_board()
        agent.rng = random.Random((int(seed) ^ 0xA5A5A5) & 0x7fffffff)
        actions = []
        steps = 0
        CHECK_PLY = 60
        play_check_str = None
        while True:
            v = mgame.get_game_ended(board, board.state.current_player)
            if v != 0.0 or steps >= ROLLOUT_LIMIT:
                break
            agent.clear()
            a = int(agent.best_action(board))
            actions.append(a)
            board, _ = mgame.get_next_state(board, a)
            steps += 1
            if steps == CHECK_PLY:
                play_check_str = mgame.string_representation(board)   # IN-PLAY board
        n_plies = len(actions)
        # losslessness check: reconstruct the IN-PLAY board purely from (seed, actions)
        recon_ok = None
        if play_check_str is not None:
            _, cb = replay_actions(seed, actions, CHECK_PLY)
            recon_ok = (mgame.string_representation(cb) == play_check_str)
        winner = mgame.get_game_ended(board, 0)   # terminal value to player 0
        return {"game_id": int(seed), "seed": int(seed), "actions": actions,
                "n_plies": n_plies, "winner": float(winner),
                "recon_ok": recon_ok}
    except Exception as e:
        import traceback
        return {"_error": f"seed {seed}: {type(e).__name__}: {e}",
                "_tb": traceback.format_exc().splitlines()[-3:]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-games", type=int, default=400)
    ap.add_argument("--seed-base", type=int, default=2_900_000_000)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", type=str, default=str(OUT / "games_mcts.jsonl"))
    args = ap.parse_args()

    t0 = time.time()
    cfg = EH._heur_leaf_cfg(2.0)
    seeds = [args.seed_base + i for i in range(args.n_games)]
    print(f"[gen] {len(seeds)} HeuristicMCTS({SIMS},v2.9) self-play games, {args.workers} workers")

    ctx = get_context("fork")
    out_path = Path(args.out); out_path.parent.mkdir(parents=True, exist_ok=True)
    ok, errs, plies, recon_fail = 0, [], [], 0
    with out_path.open("w") as fh:
        with ctx.Pool(args.workers, initializer=_worker_init, initargs=(2.0,)) as pool:
            for i, g in enumerate(pool.imap_unordered(_gen_game, seeds, chunksize=2)):
                if "_error" in g:
                    errs.append(g["_error"])
                    if len(errs) <= 3:
                        print("  ERR", g["_error"], g.get("_tb"))
                else:
                    fh.write(json.dumps(g) + "\n")
                    ok += 1; plies.append(g["n_plies"])
                    if g.get("recon_ok") is False:
                        recon_fail += 1
                if (i + 1) % 50 == 0:
                    el = time.time() - t0
                    print(f"  {i+1}/{len(seeds)} ok={ok} err={len(errs)} reconfail={recon_fail} "
                          f"{el:.0f}s ({(i+1)/el:.2f} games/s)")
    dt = time.time() - t0
    import numpy as np
    pl = np.array(plies) if plies else np.array([0])
    print(f"[done] ok={ok} err={len(errs)} RECON_FAIL={recon_fail} in {dt:.0f}s | plies "
          f"min={pl.min()} max={pl.max()} mean={pl.mean():.0f} | {out_path} "
          f"({out_path.stat().st_size/1e6:.1f} MB)")
    if recon_fail:
        print("  *** WARNING: reconstruction mismatches — (seed,actions) replay is NOT lossless! ***")
    if errs[:3]:
        print("  sample errors:", errs[:3])


if __name__ == "__main__":
    main()
