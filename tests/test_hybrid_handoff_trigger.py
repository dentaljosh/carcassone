"""Unit test for the hybrid-handoff trigger semantics (scripts/level2/eval_hybrid_handoff.py).

The trigger must latch to the heuristic ONLY on a TILES-phase decision with
k_remaining <= K, where k_remaining = len(deck) + (1 if next_tile else 0) — the
exact definition gen_endgame_positions uses, so "K<=2" here == the L2-3 K=2 band.
Latching only on TILES keeps turns atomic (boundary tile + its meeple stay with
one sub-agent).
"""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

from wingedsheep.carcassonne.objects.game_phase import GamePhase

# load the script as a module (it lives under scripts/, not the package)
_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "level2" / "eval_hybrid_handoff.py"
_spec = importlib.util.spec_from_file_location("eval_hybrid_handoff", _SCRIPT)
hh = importlib.util.module_from_spec(_spec)
sys.modules["eval_hybrid_handoff"] = hh
_spec.loader.exec_module(hh)


def _state(deck_len, has_next_tile, phase):
    return SimpleNamespace(deck=[0] * deck_len, next_tile=(object() if has_next_tile else None),
                           phase=phase)


def test_k_remaining_counts_in_hand_tile():
    assert hh.k_remaining(_state(3, True, GamePhase.TILES)) == 4
    assert hh.k_remaining(_state(3, False, GamePhase.MEEPLES)) == 3
    assert hh.k_remaining(_state(0, False, GamePhase.MEEPLES)) == 0


def test_latches_at_tiles_boundary():
    # K=2: a TILES position with k_remaining==2 latches; k_remaining==3 does not.
    latch, k = hh.hybrid_should_latch(_state(1, True, GamePhase.TILES), K=2)  # k=2
    assert latch and k == 2
    latch, k = hh.hybrid_should_latch(_state(2, True, GamePhase.TILES), K=2)  # k=3
    assert not latch and k == 3


def test_never_latches_in_meeple_phase():
    # Even with k_remaining<=K, a MEEPLES-phase decision must NOT trigger the latch
    # (turn-atomicity: the meeple goes with whoever placed the tile).
    latch, k = hh.hybrid_should_latch(_state(1, False, GamePhase.MEEPLES), K=2)  # k=1
    assert not latch and k == 1


def test_k_zero_band_only_last_tile():
    # K=0 should never latch (no TILES position has k_remaining<=0 while a tile is in hand).
    latch, _ = hh.hybrid_should_latch(_state(0, True, GamePhase.TILES), K=0)  # k=1
    assert not latch


def test_agent_spec_parsing():
    assert hh.parse_agent("iter8") == ("iter8", None, hh.ITER8_SIMS)
    assert hh.parse_agent("heur@3200") == ("heur", None, 3200)
    assert hh.parse_agent("hybrid:5:800") == ("hybrid", 5, 800)
    assert hh._needs_net("heur@3200") is False
    assert hh._needs_net("hybrid:2:3200") is True
    for bad in ("hybrid:5", "heur@0", "heur@-1", "wat", "hybrid:5:0"):
        try:
            hh.parse_agent(bad)
            assert False, f"expected ValueError for {bad!r}"
        except ValueError:
            pass
