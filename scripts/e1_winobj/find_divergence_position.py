#!/usr/bin/env python3
"""E1 — find and pin a K=3 POSITIVE-CONTROL position where the win objective
and the margin objective provably disagree (measurement/e1_winobj_20260814/
DESIGN.md §3).

By the DESIGN §2 proposition no K<=2 control can exist (singleton chance bags
=> the objectives coincide), so the control lives at the smallest K with a real
chance mix: a TILES decision with k_remaining == 3. The finder rolls seeded
games forward with deterministic scripted policies, solves every reached K=3
TILES decision under BOTH objectives on the RUST production solver, and
reports positions where min(optimal_actions) differs — plus the certificate
(the win-pick's E[outcome] strictly beats the margin-pick's, and the
margin-pick's E[margin] is at least the win-pick's, both mover-POV).

⚠️ K=3 here is the CONTROL'S construction depth only — it exists to prove the
flag is live (surface-B inverted-liveness convention). Nothing about it
proposes playing at K=3; depth is closed (CL-076/F13).

Usage:
  find_divergence_position.py --wheel-dir DIR [--seeds 200] [--start 1]
                              [--workers 8] [--max-hits 5] [--budget 4000000]

Prints pinned constants (seed, policy, ply, picks) for the test suite and
writes measurement/e1_winobj_20260814/raw/divergence_controls.json.
Pure CPU. 0 games played.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "engine"))

_WHEEL_DIR = None


def _init_worker(wheel_dir):
    global _WHEEL_DIR
    _WHEEL_DIR = wheel_dir
    if wheel_dir:
        sys.path.insert(0, wheel_dir)


def _bits(b):
    return struct.unpack("<d", struct.pack("<Q", b))[0]


def _roll_policy(name):
    if name == "mid":
        return lambda legal: legal[len(legal) // 2]
    if name == "lo":
        return lambda legal: legal[0]
    if name == "hi":
        return lambda legal: legal[-1]
    raise ValueError(name)


def scan_bank_game(task):
    """--from-bank mode: replay ONE banked self-play game (deck_seed +
    archived actions — a REAL, close, champion-played game) to its first
    TILES ply with k_remaining == 3 and solve both objectives there.  The
    archived action sequence is followed exactly (lossless replay), so the
    position is a genuine champion-game position, not a scripted-roll one."""
    import random

    import numpy as np

    rec, budget = task

    import carc_rs
    if _WHEEL_DIR:
        assert carc_rs.__file__.startswith(_WHEEL_DIR), carc_rs.__file__
    from carcassonne_ai import fair_agent
    from carcassonne_ai.champion_factory import production_prior_cfg
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.rust_agent import _draw_order_for_mirror, search_config_rs
    from wingedsheep.carcassonne.objects.game_phase import GamePhase

    deck_seed = int(rec["deck_seed"])
    random.seed(deck_seed)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    board = game.get_init_board()

    rs = carc_rs.FairAgentRs(search_config_rs(production_prior_cfg(), 1),
                             k_dets=1, seed=0, exact_max_k=2)
    rs.start_game_from_deck(_draw_order_for_mirror(board.state, False))

    from carcassonne_ai.flat_leaf import flat_base_score

    hits = []
    for ply, a in enumerate(int(x) for x in rec["actions"]):
        st = board.state
        k = int(fair_agent.k_remaining(st))
        if st.phase == GamePhase.TILES and k == 3:
            # closeness prefilter: a margin/win divergence needs the win
            # boundary within reach of the last three tiles; a game already
            # decided by >12 exact points cannot flip, and skipping it saves a
            # minutes-long K=3 marginalized double-solve.
            if abs(int(flat_base_score(st, 0))) > 12:
                return hits
            rm = rs.solve_marginalized(budget=budget, objective="margin")
            rw = rs.solve_marginalized(budget=budget, objective="win")
            if rm is None or rw is None:
                return hits
            pick_m, pick_w = min(rm["optimal_actions"]), min(rw["optimal_actions"])
            banked = int(st.scores[0]) - int(st.scores[1])
            if pick_m != pick_w:
                cw = {a2: _bits(b) for a2, b in rw["child_win_values"]}
                cm = {a2: _bits(b) for a2, b in rm["child_values"]}
                dw = cw[pick_w] - cw[pick_m]
                dm = cm[pick_m] - cm[pick_w]
                if st.current_player == 1:
                    dw, dm = -dw, -dm
                hits.append({
                    "source": "selfplay_bank", "deck_seed": deck_seed,
                    "ply": ply, "k_remaining": k,
                    "to_move": int(st.current_player), "banked_diff": banked,
                    "pick_margin": int(pick_m), "pick_win": int(pick_w),
                    "delta_win_prob": float(dw), "delta_margin": float(dm),
                    "margin_optimal": [int(x) for x in rm["optimal_actions"]],
                    "win_optimal": [int(x) for x in rw["optimal_actions"]],
                    "margin_child_values": {int(x): _bits(b)
                                            for x, b in rm["child_values"]},
                    "win_child_w": {int(x): v for x, v in cw.items()},
                })
            return hits          # one K=3 TILES ply per game — done
        board, _ = game.get_next_state(board, a)
        rs.advance(a)
    return hits


def scan_seed(task):
    import random

    import numpy as np

    seed, policy_name, budget = task

    import carc_rs
    if _WHEEL_DIR:
        assert carc_rs.__file__.startswith(_WHEEL_DIR), carc_rs.__file__
    from carcassonne_ai import fair_agent
    from carcassonne_ai.champion_factory import production_prior_cfg
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.rust_agent import _draw_order_for_mirror, search_config_rs
    from wingedsheep.carcassonne.objects.game_phase import GamePhase

    pol = _roll_policy(policy_name)
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    board = game.get_init_board()
    init_state = board.state

    rs = carc_rs.FairAgentRs(search_config_rs(production_prior_cfg(), 1),
                             k_dets=1, seed=0, exact_max_k=2)
    rs.start_game_from_deck(_draw_order_for_mirror(init_state, False))

    hits = []
    actions = []
    ply = 0
    while board.state.next_tile is not None:
        st = board.state
        k = int(fair_agent.k_remaining(st))
        if st.phase == GamePhase.TILES and k == 3:
            rm = rs.solve_marginalized(budget=budget, objective="margin")
            rw = rs.solve_marginalized(budget=budget, objective="win")
            if rm is None or rw is None:
                break
            pick_m, pick_w = min(rm["optimal_actions"]), min(rw["optimal_actions"])
            if pick_m != pick_w:
                cw = {a: _bits(b) for a, b in rw["child_win_values"]}
                cm = {a: _bits(b) for a, b in rm["child_values"]}
                dw = cw[pick_w] - cw[pick_m]
                dm = cm[pick_m] - cm[pick_w]
                if st.current_player == 1:
                    dw, dm = -dw, -dm
                hits.append({
                    "seed": seed, "policy": policy_name, "ply": ply,
                    "actions_prefix": list(actions),
                    "k_remaining": k, "to_move": int(st.current_player),
                    "pick_margin": int(pick_m), "pick_win": int(pick_w),
                    "delta_win_prob": float(dw), "delta_margin": float(dm),
                    "margin_optimal": [int(a) for a in rm["optimal_actions"]],
                    "win_optimal": [int(a) for a in rw["optimal_actions"]],
                    "margin_child_values": {int(a): _bits(b)
                                            for a, b in rm["child_values"]},
                    "win_child_w": {int(a): v for a, v in cw.items()},
                })
        try:
            legal = [int(x) for x in np.flatnonzero(game.get_valid_moves(board))]
        except IndexError:
            # scripted-policy artifact: an extreme policy (lo/hi) can walk the
            # board to the window edge, which the engine's farm scan does not
            # survive.  Not a solver question — abandon this roll.
            break
        if not legal:
            break
        a = pol(legal)
        actions.append(a)
        board, _ = game.get_next_state(board, a)
        rs.advance(a)
        ply += 1
    return hits


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--wheel-dir", default=None)
    ap.add_argument("--from-bank", action="store_true",
                    help="scan the 449 banked self-play games' K=3 TILES plies "
                         "(real, close champion positions) instead of scripted rolls")
    ap.add_argument("--seeds", type=int, default=200)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--limit-games", type=int, default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-hits", type=int, default=5)
    ap.add_argument("--budget", type=int, default=4_000_000)
    ap.add_argument("--out", default=str(REPO / "measurement" / "e1_winobj_20260814"
                                         / "raw" / "divergence_controls.json"))
    args = ap.parse_args(argv)

    if args.from_bank:
        bank = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
        recs = []
        with open(bank) as fh:
            for line in fh:
                if line.strip():
                    recs.append(json.loads(line))
        recs.sort(key=lambda r: int(r["deck_seed"]))
        if args.limit_games:
            recs = recs[:args.limit_games]
        tasks = [(r, args.budget) for r in recs]
        worker = scan_bank_game
    else:
        tasks = [(s, p, args.budget)
                 for s in range(args.start, args.start + args.seeds)
                 for p in ("mid", "lo", "hi")]
        worker = scan_seed
    hits, scanned = [], 0
    with mp.Pool(args.workers, initializer=_init_worker,
                 initargs=(args.wheel_dir,)) as pool:
        for out in pool.imap_unordered(worker, tasks, chunksize=2):
            scanned += 1
            for h in out:
                hits.append(h)
                src = (f"deck_seed={h['deck_seed']}" if "deck_seed" in h
                       else f"seed={h['seed']} policy={h['policy']}")
                print(f"[HIT {len(hits)}] {src} "
                      f"ply={h['ply']} to_move={h['to_move']} "
                      f"pick_m={h['pick_margin']} pick_w={h['pick_win']} "
                      f"dP(win)={h['delta_win_prob']:+.4f} "
                      f"dE[m]={h['delta_margin']:+.4f}", flush=True)
            if len(hits) >= args.max_hits:
                pool.terminate()
                break
            if scanned % 50 == 0:
                print(f"  scanned {scanned}/{len(tasks)} rolls, {len(hits)} hits",
                      flush=True)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump({"scanned_rolls": scanned, "hits": hits}, fh, indent=1)
    print(f"done: {scanned} rolls scanned, {len(hits)} divergences -> {args.out}")
    return 0 if hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
