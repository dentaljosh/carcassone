"""Record the PRE-CHANGE (knobs-unset) behaviour that the SIMS-SPLIT knob must not disturb.

Run on a checkout WITHOUT the ``sims_tile``/``sims_meeple`` change to produce the golden
file, then keep it frozen: ``tests/test_simsplit_knob.py`` replays exactly this scenario
with the knobs UNSET (the default) and demands the same action sequence, the same pooled
``(N, W)`` floats at every searched move, and the same exact-endgame latch trajectory —
on BOTH backends (python ``FairHeuristicPriorAgent`` and rust ``RustFairAgent``). That is
the guard that the champion's play is byte-for-byte unchanged when neither knob is set.

    PYTHONPATH=src:engine .venv/bin/python scripts/measurement_infra/gen_simsplit_off_fixture.py

FULL GAME (not a prefix) so the fixture pins the exact-K<=2 marginalized latch too — the
turn-atomic TILES-phase trigger is part of the byte-identity claim. Deliberately tiny
(sims=24, k_dets=2) so the replay costs tens of seconds; bit-exactness is
budget-independent. The leaf env below is the frozen-v2.9 preamble the meeple-dedup
fixture uses, and the config pins ``leaf_cfg`` explicitly so the fixture does not depend
on the caller's env or the suite's import order.

Float discipline: python pooled N/W are stored as ``float.hex()`` strings; rust pooled
N/W as raw u64 bit ints (``last_move()["pooled"]``'s own format). Both round-trip
exactly through JSON.
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
# The fixture records knobs-unset behaviour on the plain search path.
os.environ["CARCASSONNE_MEEPLE_DEDUP"] = "0"
os.environ["CARCASSONNE_INTRA_TURN_REUSE"] = "0"

import random  # noqa: E402
import sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

_REPO = _Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_Path(__file__).resolve().parent))       # snapshot
sys.path.insert(0, str(_REPO / "scripts" / "level2"))            # endgame_solver
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO / "engine"))

from carcassonne_ai import fair_agent as FA  # noqa: E402
from carcassonne_ai.fair_agent import FairHeuristicPriorAgent  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig  # noqa: E402
from snapshot import frozen_v29_cfg  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402

OUT = _REPO / "tests" / "golden" / "simsplit_off.json"

DECK_SEED = 20260811
AGENT_SEED = 7
SIMS = 24
K_DETS = 2


def scenario_config() -> HeuristicPriorConfig:
    """The exact config the generator and the test build (keep in lockstep). Leaf
    pinned to the hash-asserted frozen v2.9 config — never the import-order-dependent
    DEFAULT_CONFIG (the meeple-dedup fixture's rationale, verbatim)."""
    return HeuristicPriorConfig(final_select="visits", leaf_cfg=frozen_v29_cfg())


class _PoolSpy:
    """Capture every (agg_n, agg_w) handed to the pooled-Q pick, in call order."""

    def __init__(self):
        self.calls = []
        self._real = FA.pooled_q_argmax

    def __call__(self, agg_n, agg_w, min_visits=FA.DEFAULT_MIN_POOLED_VISITS):
        self.calls.append((dict(agg_n), dict(agg_w)))
        return self._real(agg_n, agg_w, min_visits)


def record_python() -> dict:
    cfg = scenario_config()
    game = Game(enable_legal_moves_cache=True)
    random.seed(DECK_SEED)
    board = game.get_init_board()
    agent = FairHeuristicPriorAgent(game, cfg=cfg, sims=SIMS, k_dets=K_DETS,
                                    seed=AGENT_SEED)      # exact_endgame default ON
    spy = _PoolSpy()
    FA.pooled_q_argmax = spy
    decisions = []
    actions = []
    try:
        while game.get_game_ended(board, 0) == 0.0:
            phase = board.state.phase.value
            before = len(spy.calls)
            a = int(agent.choose_action(board))
            searched = len(spy.calls) > before
            if searched:
                agg_n, agg_w = spy.calls[-1]
                pooled = [[int(k), float(agg_n[k]).hex(), float(agg_w[k]).hex()]
                          for k in agg_n]        # dict insertion order
                kind = "search"
            else:
                pooled = []
                kind = ("exact" if agent.last_pooled_visits == {} and agent._latched
                        else "forced")
            decisions.append({"ply": len(actions), "phase": phase, "kind": kind,
                              "action": a, "pooled": pooled})
            actions.append(a)
            board, _ = game.get_next_state(board, a)
    finally:
        FA.pooled_q_argmax = spy._real
    return {
        "actions": actions,
        "decisions": decisions,
        "final_key": game.string_representation(board),
        "heur_moves": int(agent.heur_moves),
        "exact_moves": int(agent.exact_moves),
        "n_timeouts": int(agent.n_timeouts),
        "latch_k": agent.latch_k,
        "final_scores": [int(s) for s in board.state.scores],
    }


def record_rust(py_actions: list[int]) -> dict:
    from carcassonne_ai.rust_agent import RustFairAgent

    cfg = scenario_config()
    game = Game(enable_legal_moves_cache=True)
    random.seed(DECK_SEED)
    board = game.get_init_board()
    agent = RustFairAgent(game, cfg, sims=SIMS, k_dets=K_DETS, seed=AGENT_SEED)
    agent.start_game(board)
    decisions = []
    actions = []
    while game.get_game_ended(board, 0) == 0.0:
        a = int(agent.choose_action(board))
        m = agent.last_move()
        kind = ("exact" if m["exact"] else "forced" if m["forced"] else "search")
        decisions.append({"ply": len(actions), "kind": kind, "action": a,
                          "pooled_bits": [[int(x), int(n), int(w)]
                                          for x, n, w in m["pooled"]]})
        actions.append(a)
        board, _ = game.get_next_state(board, a)
        agent.advance(a)
    # Sanity at generation time (the G4/G6 property, re-proven on this scenario):
    assert actions == py_actions, "rust leg diverged from python at generation time"
    st = agent.stats()
    return {
        "actions": actions,
        "decisions": decisions,
        "final_repr": agent.string_repr(),
        "heur_moves": int(st["heur_moves"]),
        "forced_moves": int(st["forced_moves"]),
        "exact_moves": int(st["exact_moves"]),
        "n_timeouts": int(st["n_timeouts"]),
        "latch_k": st["latch_k"],
    }


def main() -> None:
    py = record_python()
    assert py["exact_moves"] > 0, "fixture game never latched — pick another deck seed"
    rs = record_rust(py["actions"])
    assert rs["exact_moves"] == py["exact_moves"]
    assert rs["latch_k"] == py["latch_k"]
    out = {
        "kind": "simsplit_off_behaviour_fixture",
        "note": ("Recorded on the PRE-sims_tile/sims_meeple tree (python agent + "
                 "carc_rs wheel named below). Any diff means the knobs-UNSET search "
                 "path changed — that is a production regression, not a test bug."),
        "deck_seed": DECK_SEED,
        "agent_seed": AGENT_SEED,
        "sims": SIMS,
        "k_dets": K_DETS,
        "python": py,
        "rust": rs,
    }
    import carc_rs
    out["carc_rs_version_at_generation"] = str(carc_rs.__version__)
    OUT.write_text(json.dumps(out, indent=1))
    n_moves = len(py["actions"])
    print(f"wrote {OUT}: {n_moves} moves, heur={py['heur_moves']} "
          f"exact={py['exact_moves']} latch_k={py['latch_k']} "
          f"scores={py['final_scores']}")


if __name__ == "__main__":
    main()
