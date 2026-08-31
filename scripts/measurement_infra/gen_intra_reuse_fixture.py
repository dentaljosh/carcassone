"""Record the PRE-CHANGE (flag-OFF) fair-agent behaviour that C3-INTRA must not disturb.

Run on a checkout WITHOUT the intra-turn-reuse change to produce the golden file, then
keep it frozen: ``tests/test_intra_reuse.py::test_bit_exact_off_matches_pre_change_fixture``
replays exactly this scenario with the flag OFF (the default) and demands the same action
sequence, the same per-decision POOLED VISIT distributions, and the same final board key.
That is the guard that the champion's fair search is byte-for-byte unchanged when
``CARCASSONNE_INTRA_TURN_REUSE`` is not set.

    CARCASSONNE_FIX_LEGAL_CACHE_KEY=0 \
      .venv/bin/python scripts/measurement_infra/gen_intra_reuse_fixture.py

⚠️ The banked golden predates the 2026-08-30 `CARCASSONNE_FIX_LEGAL_CACHE_KEY`
default flip, and `string_representation` is the MCTS transposition key, so the
replaying test is pinned to the legacy key (`legacy_cache_key` fixture). Regenerate
with `CARCASSONNE_FIX_LEGAL_CACHE_KEY=0` to stay comparable, or re-pin the test to the
new key and regenerate WITHOUT it — but do not mix the two.

The pooled visit distribution is the RIGHT fingerprint for this feature: intra-turn carry
changes nothing about which determinizations are drawn or how the tile decision searches,
and everything about the visit counts the MEEPLE decision pools. If the OFF path ever
drifts, the meeple-ply rows here move first.

Deliberately tiny (sims=24, k_dets=2, 40 plies) so the test costs seconds; bit-exactness is
budget-independent. The leaf env below is the frozen-v2.9 preamble
tests/test_measurement_infra.py uses, so the fixture does not depend on the caller's env.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# Frozen v2.9 leaf env — MUST precede the carcassonne_ai import (DEFAULT_CONFIG reads it).
for _k, _v in {
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
}.items():
    os.environ.setdefault(_k, _v)
# The fixture records the OFF behaviour: never let an inherited env turn the feature on.
os.environ["CARCASSONNE_INTRA_TURN_REUSE"] = "0"
os.environ["CARCASSONNE_MEEPLE_DEDUP"] = "0"

import random  # noqa: E402
import sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

sys.path.insert(0, str(_Path(__file__).resolve().parent))

from carcassonne_ai.fair_agent import FairHeuristicPriorAgent  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig  # noqa: E402
from snapshot import frozen_v29_cfg  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "tests" / "golden" / "intra_reuse_off.json"

DECK_SEED = 20260727
AGENT_SEED = 11
SIMS = 24
K_DETS = 2
PLIES = 40


def scenario_config() -> HeuristicPriorConfig:
    """The exact config both the generator and the test build (keep in lockstep).

    The leaf is pinned to the hash-asserted frozen v2.9 config rather than left to
    ``DEFAULT_CONFIG``: that global is built once at first import from the env, so in a
    full-suite run whichever sibling module wins the import race would decide it and the
    replay would diverge for reasons that have nothing to do with this feature.
    """
    return HeuristicPriorConfig(final_select="visits", leaf_cfg=frozen_v29_cfg())


def record() -> dict:
    cfg = scenario_config()
    game = Game(enable_legal_moves_cache=True)
    random.seed(DECK_SEED)
    board = game.get_init_board()
    agent = FairHeuristicPriorAgent(game, cfg=cfg, sims=SIMS, k_dets=K_DETS,
                                    seed=AGENT_SEED, exact_endgame=False)

    actions: list[int] = []
    plies: list[dict] = []
    for _ply in range(PLIES):
        if game.get_game_ended(board, board.state.current_player) != 0.0:
            break
        phase = board.state.phase.name
        a = int(agent.choose_action(board))
        pooled = agent.last_pooled_visits or {}
        plies.append({
            "ply": len(actions),
            "phase": phase,
            "action": a,
            # The pooled root-visit distribution across the k_dets worlds — the exact
            # quantity intra-turn carry perturbs on MEEPLES plies when it is ON.
            "pooled_visits": {str(int(k)): float(v) for k, v in sorted(pooled.items())},
        })
        actions.append(a)
        board, _ = game.get_next_state(board, a)

    return {
        "kind": "intra_turn_reuse_off_behaviour_fixture",
        "note": ("Recorded on the pre-C3-INTRA tree. Any diff means the flag-OFF fair "
                 "search path changed — that is a production regression, not a test bug."),
        "deck_seed": DECK_SEED,
        "agent_seed": AGENT_SEED,
        "sims": SIMS,
        "k_dets": K_DETS,
        "plies_requested": PLIES,
        "actions": actions,
        "final_key": game.string_representation(board),
        "per_ply": plies,
        "heur_moves": int(agent.heur_moves),
    }


if __name__ == "__main__":
    os.nice(19)
    rec = record()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=2))
    n_meeple = sum(1 for p in rec["per_ply"] if p["phase"] == "MEEPLES")
    print(f"{len(rec['actions'])} actions ({n_meeple} meeple plies) -> {OUT}")
