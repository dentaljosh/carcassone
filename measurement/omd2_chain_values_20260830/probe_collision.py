#!/usr/bin/env python3
"""OM-D2 — the smoking gun: the two tied tile actions COLLIDE on one
`string_representation` key, so the memo serves the first one's legal mask to
the second.

Single witness `(28000000011, 24)`, single position, read-only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from probe_witnesses import load_corpus, prepare_env  # noqa: E402

SEED, PLY, A1, A2 = 28000000011, 24, 949, 951


def main() -> int:
    prepare_env()
    import random

    import numpy as np

    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai.action_space import decode
    from carcassonne_ai.game_wrapper import Game

    cfg = CF.production_leaf_cfg()
    CF.verify_leaf(cfg)

    actions = load_corpus()[SEED]
    random.seed(SEED)
    g = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    b = g.get_init_board()
    for a in actions[:PLY]:
        g.get_valid_moves(b)
        b, _ = g.get_next_state(b, int(a))

    s1, _ = g.get_next_state(b, A1)
    s2, _ = g.get_next_state(b, A2)
    k1 = g.string_representation(s1)
    k2 = g.string_representation(s2)
    m1 = g._compute_mask(s1)
    m2 = g._compute_mask(s2)
    def dec_tile(i):
        return repr(decode(int(i), off=b.offset, phase=b.state.phase.value,
                           next_tile=b.state.next_tile))

    def dec_meeple(i, s):
        return repr(decode(int(i), off=s.offset, phase=s.state.phase.value,
                           last_tile_coord=s.state.last_tile_action.coordinate
                           if getattr(s.state, "last_tile_action", None) else None))

    out = {
        "deck_seed": SEED, "ply": PLY, "tile_actions": [A1, A2],
        "decoded_tile_actions": {str(A1): dec_tile(A1), str(A2): dec_tile(A2)},
        "string_representation_equal": k1 == k2,
        "honest_masks_equal": bool(np.array_equal(m1, m2)),
        "honest_legal_meeples_after_A1": [int(x) for x in np.flatnonzero(m1)],
        "honest_legal_meeples_after_A2": [int(x) for x in np.flatnonzero(m2)],
        "decoded_meeples_after_A2": {
            str(int(x)): dec_meeple(x, s2) for x in np.flatnonzero(m2)
        },
    }
    print(json.dumps(out, indent=1))
    (HERE / "COLLISION_WITNESS.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
