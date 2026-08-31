#!/usr/bin/env python3
"""OM-D2 — name the colliding tile and the rotating farm slots (witness 1)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from probe_witnesses import load_corpus, prepare_env  # noqa: E402

SEED, PLY, A1, A2 = 28000000011, 24, 949, 951


def main() -> int:
    prepare_env()
    import random

    from carcassonne_ai.action_space import decode
    from carcassonne_ai.game_wrapper import Game

    actions = load_corpus()[SEED]
    random.seed(SEED)
    g = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    b = g.get_init_board()
    for a in actions[:PLY]:
        b, _ = g.get_next_state(b, int(a))
    t = b.state.next_tile
    ta1 = decode(A1, off=b.offset, phase=b.state.phase.value, next_tile=t)
    ta2 = decode(A2, off=b.offset, phase=b.state.phase.value, next_tile=t)

    def tinfo(x):
        return {
            "description": getattr(x, "description", None),
            "grass": getattr(x, "grass", None),
            "edges": [str(getattr(x, s, None)) for s in ("north", "east", "south", "west")],
            "shield": getattr(x, "shield", None),
            "chapel": getattr(x, "chapel", None),
            "flowers": getattr(x, "flowers", None),
            "farms": [
                [str(p) for p in (getattr(f, "farmer_positions", None) or [])]
                for f in (getattr(x, "farms", None) or [])
            ],
        }

    out = {
        "tile_description": getattr(t, "description", None),
        "A1": {"coord": str(ta1.coordinate), "tile": tinfo(ta1.tile)},
        "A2": {"coord": str(ta2.coordinate), "tile": tinfo(ta2.tile)},
    }
    print(json.dumps(out, indent=1, default=str))
    (HERE / "TILE_WITNESS.json").write_text(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
