"""Rust-parity tests for the L2-3 exact endgame solver.

Sits alongside `tests/test_endgame_solver.py` — that file validates the PYTHON
solver against an independent brute force; this one validates
`carc_rs.MirrorState.solve_endgame` (the `carc_core::endgame` port) against the
Python solver on the same positions.

Everything is compared as raw f64 BITS, and the NODE COUNT is compared too: a
TT-key, move-ordering or chance-node difference changes the search shape even
when the values agree, and the node count is the only thing that sees it.

Positions are DETERMINISTIC: the deck is shuffled by the global `random` module
at `get_init_board`, so we `random.seed(S)` first and drive the Rust mirror in
LOCKSTEP with the same action ints.

Build the extension with:
    maturin develop --release --manifest-path rust/carc/carc-py/Cargo.toml
"""
import os
import random
import struct
import sys

import numpy as np
import pytest

REPO = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "scripts", "level2"))

from carcassonne_ai.game_wrapper import Game  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402
import endgame_solver as S  # noqa: E402

carc_rs = pytest.importorskip("carc_rs", reason="build with `maturin develop --release`")


def ubits(x: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


def _k(b):
    return len(b.state.deck) + (1 if b.state.next_tile is not None else 0)


def endgame_pair(seed: int, k_target: int):
    """(game, board, mirror) at the first TILES ply with `k_target` tiles left.

    Mirrors `test_endgame_solver.endgame_position` and drives the Rust mirror
    with the identical action sequence, so the two sides are the same position
    by construction — and `string_repr` equality is asserted, not assumed.
    """
    random.seed(seed)                       # seeds the engine deck shuffle
    game = Game(enable_legal_moves_cache=True)
    b = game.get_init_board()
    ms = carc_rs.MirrorState.from_seed(str(seed))
    mover_rng = random.Random(seed ^ 0x5151)
    while game.get_game_ended(b, 0) == 0.0:
        if b.state.phase == GamePhase.TILES and _k(b) == k_target:
            assert game.string_representation(b) == ms.string_repr()
            assert ms.k_remaining() == k_target
            return game, b, ms
        legal = np.flatnonzero(game.get_valid_moves(b))
        a = int(mover_rng.choice(legal))
        b, _ = game.get_next_state(b, a)
        ms.advance(a)
    raise RuntimeError(f"never reached k={k_target}")


def assert_same(py, rs, ctx=""):
    """Bit-for-bit equality of a Python `SolveResult` and the Rust dict."""
    assert ubits(py.value) == int(rs["value_bits"]), f"{ctx}: value"
    assert int(py.to_move) == int(rs["to_move"]), f"{ctx}: to_move"
    assert [int(a) for a in py.optimal_actions] == [int(a) for a in rs["optimal_actions"]], \
        f"{ctx}: optimal_actions"
    py_cv = sorted((int(a), ubits(v)) for a, v in py.child_values.items())
    rs_cv = sorted((int(a), int(v)) for a, v in rs["child_values"])
    assert py_cv == rs_cv, f"{ctx}: child_values"
    assert int(py.nodes) == int(rs["nodes"]), f"{ctx}: nodes"


@pytest.mark.parametrize("seed", [1, 7, 11])
@pytest.mark.parametrize("mode,alphabeta", [("clairvoyant", False),
                                            ("clairvoyant", True),
                                            ("marginalized", False)])
def test_rust_matches_python_at_k1(seed, mode, alphabeta):
    """K=1, every mode: identical value, optimal set, child values and nodes."""
    game, b, ms = endgame_pair(seed, 1)
    py = S.solve(game, b, mode, budget=5_000_000, alphabeta=alphabeta)
    rs = ms.solve_endgame(mode=mode, budget=5_000_000, alphabeta=alphabeta)
    assert rs is not None
    assert_same(py, rs, f"seed{seed} {mode} ab={alphabeta}")


@pytest.mark.slow
@pytest.mark.parametrize("seed", [1, 7])
@pytest.mark.parametrize("mode,alphabeta", [("clairvoyant", False),
                                            ("clairvoyant", True),
                                            ("marginalized", False)])
def test_rust_matches_python_at_k2(seed, mode, alphabeta):
    """K=2 — the first depth at which the TT actually collapses transpositions."""
    game, b, ms = endgame_pair(seed, 2)
    py = S.solve(game, b, mode, budget=5_000_000, alphabeta=alphabeta)
    rs = ms.solve_endgame(mode=mode, budget=5_000_000, alphabeta=alphabeta)
    assert rs is not None
    assert_same(py, rs, f"seed{seed} {mode} ab={alphabeta}")


@pytest.mark.parametrize("seed", [1, 7, 11])
def test_rust_v2_last_tile_clair_equals_marg(seed):
    """V2, on the RUST side: at K=1 there is no hidden future."""
    _, _, ms = endgame_pair(seed, 1)
    rc = ms.solve_endgame(mode="clairvoyant", budget=5_000_000)
    rm = ms.solve_endgame(mode="marginalized", budget=5_000_000)
    assert rc["value_bits"] == rm["value_bits"]
    assert rc["optimal_actions"] == rm["optimal_actions"]
    assert sorted(map(tuple, rc["child_values"])) == sorted(map(tuple, rm["child_values"]))


@pytest.mark.parametrize("seed", [1, 7, 11])
def test_rust_alphabeta_is_exact(seed):
    """V-brute, on the RUST side: alpha-beta == the no-prune path == the
    independent no-TT brute force, and pruning never costs nodes."""
    _, _, ms = endgame_pair(seed, 1)
    plain = ms.solve_endgame(mode="clairvoyant", budget=5_000_000, alphabeta=False)
    ab = ms.solve_endgame(mode="clairvoyant", budget=5_000_000, alphabeta=True)
    brute = ms.brute_solve_endgame(budget=5_000_000)
    assert brute is not None
    b_val, b_opt, b_cv = brute
    assert plain["value_bits"] == ab["value_bits"] == ubits(b_val)
    assert plain["optimal_actions"] == ab["optimal_actions"] == list(b_opt)
    assert sorted(map(tuple, plain["child_values"])) == sorted(map(tuple, b_cv))
    assert ab["nodes"] <= plain["nodes"]


def test_rust_budget_exceeded_returns_none():
    """A blown node budget is `None` on the wire (Python raises BudgetExceeded)."""
    _, _, ms = endgame_pair(1, 2)
    assert ms.solve_endgame(mode="clairvoyant", budget=1) is None
    assert ms.solve_endgame(mode="marginalized", budget=1) is None


def test_rust_tt_cap_is_correctness_neutral():
    """Freezing the TT can cost nodes; it must never change the answer."""
    _, _, ms = endgame_pair(1, 2)
    free = ms.solve_endgame(mode="clairvoyant", budget=5_000_000, tt_cap=0)
    capped = ms.solve_endgame(mode="clairvoyant", budget=5_000_000, tt_cap=16)
    assert free["value_bits"] == capped["value_bits"]
    assert free["optimal_actions"] == capped["optimal_actions"]
    assert capped["tt_entries"] <= 16
    assert capped["nodes"] >= free["nodes"]


def test_rust_refuses_alphabeta_for_marginalized():
    """Chance nodes have no minimax cutoff — the Python `assert`, as a ValueError."""
    _, _, ms = endgame_pair(1, 1)
    with pytest.raises(Exception):
        ms.solve_endgame(mode="marginalized", budget=5_000_000, alphabeta=True)


def test_rust_rejects_an_unknown_mode():
    _, _, ms = endgame_pair(1, 1)
    with pytest.raises(ValueError):
        ms.solve_endgame(mode="perfect", budget=1000)
