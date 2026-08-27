#!/usr/bin/env python3
"""Emit REAL E4 endgame positions (any ply, low K) for the rust-vs-python gate.

The target set alone is too thin at low K for the `walled` / `app_aug2` archives
(1-2 games each), and the differential test must cover EVERY profile the corpus
contains. This walks the archives of one profile and emits every TILES-phase ply
whose K is in `[--k-min, --k-max]`, which is the regime the exact solver runs in.
Computes no prices; reads no outcome field.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
ARCHIVES = REPO / "measurement" / "e4_games"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--k-min", type=int, default=2)
    ap.add_argument("--k-max", type=int, default=8)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    from analyzer.ev_loss import prepare_env, resolve_profile_name
    prepare_env(args.profile)
    from carcassonne_ai import rules_profile
    from carcassonne_ai.game_wrapper import Game

    prof = rules_profile.resolve(args.profile)
    rows = []
    for path in sorted(ARCHIVES.glob("*.json")):
        arc = json.loads(path.read_text())
        if not arc.get("ok") or "actions" not in arc:
            continue
        if resolve_profile_name(arc) != args.profile:
            continue
        seed = int(arc["deck_seed"])
        actions = [int(x) for x in arc["actions"]]
        random.seed(seed)
        game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
        board = game.get_init_board()
        for i, a in enumerate(actions):
            st = board.state
            k = len(st.deck) + (1 if st.next_tile is not None else 0)
            phase = str(getattr(st.phase, "name", st.phase)).lower()
            if phase == "tiles" and args.k_min <= k <= args.k_max:
                rows.append({"game": path.name, "profile": args.profile,
                             "ply": i, "k": int(k), "stratum": "diffgate"})
            board, _ = game.get_next_state(board, a)
    Path(args.out).write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"{args.profile}: {len(rows)} positions -> {args.out}")


if __name__ == "__main__":
    main()
