"""Record the PRE-CHANGE (flag-OFF) search behaviour that MEEPLE-DEDUP must not disturb.

Run on a checkout WITHOUT the dedup change to produce the golden file, then keep it
frozen: ``tests/test_meeple_equiv.py::test_bit_exact_off_matches_pre_change_fixture``
replays exactly this scenario with the flag OFF (the default) and demands the same
action sequence and the same root visit counts. That is the guard that the champion's
search is byte-for-byte unchanged when ``CARCASSONNE_MEEPLE_DEDUP`` is not set.

    .venv/bin/python scripts/measurement_infra/gen_meeple_dedup_fixture.py

Deliberately tiny (sims=24, k_dets=2, 40 plies) so the test costs seconds; bit-exactness
is budget-independent. The leaf env below is the frozen-v2.9 preamble
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
# The fixture records the OFF behaviour: never let an inherited env turn dedup on.
os.environ["CARCASSONNE_MEEPLE_DEDUP"] = "0"

import random  # noqa: E402
import sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

sys.path.insert(0, str(_Path(__file__).resolve().parent))

from carcassonne_ai.fair_agent import FairHeuristicPriorAgent  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import (  # noqa: E402
    HeuristicPriorConfig,
    make_heuristic_prior_evaluator,
)
from carcassonne_ai.mcts import NeuralMCTS  # noqa: E402
from snapshot import frozen_v29_cfg  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "tests" / "golden" / "meeple_dedup_off.json"

DECK_SEED = 20260727
AGENT_SEED = 11
SIMS = 24
K_DETS = 2
PLIES = 40
PROBE_SIMS = 40      # the standalone-NeuralMCTS probes at meeple-phase roots
PROBE_SEED = 5
MAX_PROBES = 6


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
    evaluator = make_heuristic_prior_evaluator(game, cfg)

    actions: list[int] = []
    probes: list[dict] = []
    for _ply in range(PLIES):
        if game.get_game_ended(board, board.state.current_player) != 0.0:
            break
        # A standalone single-tree probe at every meeple-phase root (the nodes the
        # dedup acts on): its visit counts are the finest-grained OFF invariant.
        if board.state.phase == GamePhase.MEEPLES and len(probes) < MAX_PROBES:
            m = NeuralMCTS(game=game, evaluator=evaluator, simulations=PROBE_SIMS,
                           c_puct=cfg.c_puct, seed=PROBE_SEED)
            counts = m.search(board)
            visits, pactions = m.root_visit_distribution(board)
            probes.append({
                "ply": len(actions),
                "visits_by_action": {str(int(a)): int(n) for a, n in counts.items()},
                "deduped_actions": [int(a) for a in pactions],
                "deduped_visits": [int(v) for v in visits],
                "best_action": int(m.best_action(board)),
            })
        a = int(agent.choose_action(board))
        actions.append(a)
        board, _ = game.get_next_state(board, a)

    return {
        "kind": "meeple_dedup_off_behaviour_fixture",
        "note": ("Recorded on the pre-MEEPLE_DEDUP tree. Any diff means the flag-OFF "
                 "search path changed — that is a production regression, not a test bug."),
        "deck_seed": DECK_SEED,
        "agent_seed": AGENT_SEED,
        "sims": SIMS,
        "k_dets": K_DETS,
        "plies": PLIES,
        "probe_sims": PROBE_SIMS,
        "probe_seed": PROBE_SEED,
        "actions": actions,
        "final_key": game.string_representation(board),
        "probes": probes,
    }


if __name__ == "__main__":
    os.nice(19)
    rec = record()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=2))
    print(f"{len(rec['actions'])} actions, {len(rec['probes'])} probes -> {OUT}")
