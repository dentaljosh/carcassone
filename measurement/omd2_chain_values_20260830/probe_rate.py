#!/usr/bin/env python3
"""OM-D2 — the census defect rate, BOTH directions, on the 9 witness games.

The `G-FIRE` join can only see one direction (rust fires / census says untied).
This re-runs the banked tile-gap census on the witness games twice — memo ON
(the banked setting) and memo OFF (honest masks) — and counts every row whose
`tie_exact` or `gap` moves, in either direction.

Read-only; ~9 games, single process, nice -19.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from probe_witnesses import WITNESSES, load_corpus, prepare_env  # noqa: E402


def census_game(actions, deck_seed: int, *, cache: bool, leaf):
    import random

    import numpy as np
    from wingedsheep.carcassonne.objects.game_phase import GamePhase

    import chain_census as CC
    from carcassonne_ai.game_wrapper import Game

    random.seed(deck_seed)
    game = Game(enable_legal_moves_cache=cache, include_farm_scalars=True)
    board = game.get_init_board()
    rows = {}
    for ply, played in enumerate(actions):
        st = board.state
        seat = int(st.current_player)
        if st.phase != GamePhase.MEEPLES:
            n_legal = int(np.count_nonzero(game.get_valid_moves(board)))
            if n_legal >= 2:
                vals = CC.chain_values(game, board, seat, lambda s: leaf(s, seat))
                rep = CC.tie_report(vals)
                rows[ply] = {"tie_exact": rep["tie_exact"],
                             "tie_size_exact": rep["tie_size_exact"],
                             "gap": rep["gap"], "top1": rep["top1"]}
        board, _ = game.get_next_state(board, int(played))
    return rows


def main() -> int:
    prepare_env()
    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai import flat_leaf

    cfg = CF.production_leaf_cfg()
    CF.verify_leaf(cfg)
    bag_close = bool(getattr(cfg, "bag_close", False))

    def leaf(state, seat):
        return float(flat_leaf.flat_virtual_score_v2_float(state, int(seat), cfg, bag_close))

    corpus = load_corpus()
    seeds = sorted({s for s, _ in WITNESSES})
    tot = {"rows": 0, "tie_exact_moved": 0, "false_untied": 0, "false_tied": 0,
           "top1_moved": 0, "gap_moved": 0}
    per_game = []
    for s in seeds:
        t0 = time.time()
        a = corpus[s]
        on = census_game(a, s, cache=True, leaf=leaf)
        off = census_game(a, s, cache=False, leaf=leaf)
        d = {"deck_seed": s, "n_rows": len(on), "moved": []}
        for ply in sorted(on):
            o, f = on[ply], off[ply]
            if o != f:
                d["moved"].append({"ply": ply, "memo_on": o, "honest": f})
                tot["tie_exact_moved"] += int(o["tie_exact"] != f["tie_exact"])
                tot["false_untied"] += int(not o["tie_exact"] and f["tie_exact"])
                tot["false_tied"] += int(o["tie_exact"] and not f["tie_exact"])
                tot["top1_moved"] += int(o["top1"] != f["top1"])
                tot["gap_moved"] += int(o["gap"] != f["gap"])
        tot["rows"] += len(on)
        d["secs"] = round(time.time() - t0, 1)
        per_game.append(d)
        print(json.dumps({k: d[k] for k in ("deck_seed", "n_rows", "secs")}
                         | {"n_moved": len(d["moved"])}), flush=True)
    tot["n_games"] = len(seeds)
    tot["rate_rows_moved"] = sum(len(g["moved"]) for g in per_game) / tot["rows"]
    print(json.dumps(tot, indent=1))
    (HERE / "DEFECT_RATE.json").write_text(json.dumps(
        {"totals": tot, "per_game": per_game}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
