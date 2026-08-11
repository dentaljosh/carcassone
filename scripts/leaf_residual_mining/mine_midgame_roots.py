#!/usr/bin/env python3
"""Mine MIDGAME roots (TILES phase) from a replayable (deck_seed, actions) games jsonl.

Emits the root schema consumed by ``scripts/measurement_infra/gate_b_fair_pimc.py`` and by
``residual_emit.py``: ``{deck_seed, actions, ply, checksum, ...}``. Roots are reconstructed
losslessly via ``root_replay.replay_actions`` (see that module's contract), and the emitted
``checksum`` is the engine's ``string_representation`` so every downstream consumer verifies
the reconstruction rather than assuming it.

MIDGAME is defined by TILES-PHASE ply, not by wall position: only plies where the mover is
choosing a TILE PLACEMENT are eligible (meeple-phase plies branch 1-8 ways and carry almost no
sibling-ordering signal). The ply window is a CLI argument so the pre-registration owns it.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))

from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402

import root_replay as RR  # noqa: E402


def mine(games_path: Path, ply_lo: int, ply_hi: int, per_game: int, seed: int,
         max_games: int = 0):
    games = RR.load_games(games_path)
    if max_games:
        games = games[:max_games]
    rng = random.Random(int(seed))
    out = []
    for g in games:
        n = len(g.actions)
        hi = min(ply_hi, n - 1)
        cand = [p for p in range(ply_lo, hi + 1)]
        if not cand:
            continue
        picks = sorted(rng.sample(cand, min(per_game, len(cand))))
        # one replay per game, stepped forward -- avoids re-replaying from ply 0 per root
        game, board = RR.replay_actions(g.deck_seed, g.actions, 0)
        cur = 0
        want = set(picks)
        emitted_this_game = []
        for p in range(0, hi + 1):
            if p in want:
                st = board.state
                if st.phase == GamePhase.TILES:
                    mask = game.get_valid_moves(board)
                    n_legal = int(mask.sum())
                    if n_legal >= 2:
                        emitted_this_game.append({
                            "source_agent": g.meta.get("agent", "unknown"),
                            "game_id": int(g.game_id),
                            "deck_seed": int(g.deck_seed),
                            "ply": int(p),
                            "actions": [int(a) for a in g.actions],
                            "n_legal": n_legal,
                            "to_move": int(st.current_player),
                            "scores": [int(x) for x in st.scores],
                            "tiles_remaining": int(len(st.deck)),
                            "checksum": game.string_representation(board),
                        })
            if p >= hi:
                break
            board, _ = game.get_next_state(board, int(g.actions[p]))
            cur = p + 1
        out.extend(emitted_this_game)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Mine midgame TILES-phase roots from a games jsonl")
    ap.add_argument("--games", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ply-lo", type=int, default=40)
    ap.add_argument("--ply-hi", type=int, default=110)
    ap.add_argument("--per-game", type=int, default=2)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--max-games", type=int, default=0)
    args = ap.parse_args(argv)

    roots = mine(Path(args.games), args.ply_lo, args.ply_hi, args.per_game,
                 args.seed, args.max_games)
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with outp.open("w") as fh:
        for r in roots:
            fh.write(json.dumps(r) + "\n")
    plies = [r["ply"] for r in roots]
    legals = [r["n_legal"] for r in roots]
    print(f"[mine] {len(roots)} roots -> {outp}")
    if roots:
        print(f"[mine] ply  min/med/max = {min(plies)}/{sorted(plies)[len(plies)//2]}/{max(plies)}")
        print(f"[mine] legal min/med/max = {min(legals)}/{sorted(legals)[len(legals)//2]}/{max(legals)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
