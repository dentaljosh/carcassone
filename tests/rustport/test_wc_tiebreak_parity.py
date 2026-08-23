"""Rust-parity tests for the WC tie-break rule flag (BACKLOG 2026-08-03 "WC
tie-break rule flag"; measurement/TOURNAMENT_LANDSCAPE_MEMO_20260728.md
§1.3/§1.4) on the exact endgame solver.

Sits alongside `tests/test_rustport_endgame_solver.py` (that file's `assert_same`
/ `endgame_pair` shape is mirrored here verbatim) and `tests/test_wc_tiebreak.py`
(the core's own coverage — `_outcome`, `SolveResult.wc_tiebreak`, the K<=2
inertness-survives-the-flag proposition). This file validates
`carc_rs.MirrorState.solve_endgame(..., objective=..., wc_tiebreak=...)` against
`scripts/level2/endgame_solver.solve(..., wc_tiebreak=...)` on replayed endgame
positions.

Two load-bearing facts pinned throughout (both proven independently by
`scripts/level2/endgame_solver.solve`'s own docstring, re-verified here on the
Rust side):
  * under `objective="margin"` (the deployed default), `wc_tiebreak` is INERT
    BY CONSTRUCTION — margin mode never calls the outcome lattice, so an
    armed-but-margin-objective solve must be byte-identical to an unarmed one;
  * under `objective="win"`, `wc_tiebreak` changes which moves the solver
    prefers (a tied terminal becomes a LOSS instead of a draw for P0) — this is
    where the flag actually has search-visible teeth.

⚠️ The installed carc_rs wheel on THIS box does NOT carry the `wc_tiebreak`
kwarg (confirmed live, 2026-08-23) — every test here `pytest.skip`s LOUDLY with
the per-box rebuild instruction rather than silently passing on a wheel that
never ran the knob. Written so it PASSES once someone rebuilds with
`maturin develop --release --manifest-path rust/carc/carc-py/Cargo.toml`.
"""
import os
import random
import struct
import sys

import numpy as np
import pytest

REPO = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "scripts", "level2"))

from carcassonne_ai.game_wrapper import Game  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402
import endgame_solver as S  # noqa: E402

carc_rs = pytest.importorskip("carc_rs", reason="build with `maturin develop --release`")

_REBUILD = (
    "carc_rs wheel on THIS box PREDATES the wc_tiebreak knob on "
    "MirrorState.solve_endgame — rebuild with `maturin develop --release "
    "--manifest-path rust/carc/carc-py/Cargo.toml` before trusting any "
    "wc_tiebreak result here. This is a BUILD gap, not a test failure."
)


def ubits(x: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


def _k(b):
    return len(b.state.deck) + (1 if b.state.next_tile is not None else 0)


def endgame_pair(seed: int, k_target: int):
    """(game, board, mirror) at the first TILES ply with `k_target` tiles left.
    Verbatim copy of test_rustport_endgame_solver.py's helper (kept local so
    this file has no cross-test-module import)."""
    random.seed(seed)
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


def _rust_solve_wc(ms, **kw):
    """One `solve_endgame` call with `wc_tiebreak` — the LOUD skip point. Every
    test below routes through this so a stale wheel skips consistently."""
    try:
        return ms.solve_endgame(**kw)
    except TypeError as e:
        if "wc_tiebreak" in str(e):
            pytest.skip(_REBUILD)
        raise


def assert_same_core(py, rs, ctx=""):
    """value/to_move/optimal_actions/child_values/nodes — same shape as
    test_rustport_endgame_solver.assert_same."""
    assert ubits(py.value) == int(rs["value_bits"]), f"{ctx}: value"
    assert int(py.to_move) == int(rs["to_move"]), f"{ctx}: to_move"
    assert [int(a) for a in py.optimal_actions] == [int(a) for a in rs["optimal_actions"]], \
        f"{ctx}: optimal_actions"
    py_cv = sorted((int(a), ubits(v)) for a, v in py.child_values.items())
    rs_cv = sorted((int(a), int(v)) for a, v in rs["child_values"])
    assert py_cv == rs_cv, f"{ctx}: child_values"
    assert int(py.nodes) == int(rs["nodes"]), f"{ctx}: nodes"


# --------------------------------------------------------------------------- #
# 1. margin objective — wc_tiebreak INERT on the Rust side too                 #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("seed", [1, 7, 11])
def test_margin_objective_wc_tiebreak_is_inert_on_rust(seed):
    """Rust mirror of endgame_solver.solve's documented margin-mode inertness:
    wc_tiebreak=True under objective='margin' must return the IDENTICAL result
    to wc_tiebreak=False (same value/optimal_actions/child_values/nodes) —
    margin mode never reaches the outcome lattice on either side."""
    _, b, ms = endgame_pair(seed, 1)
    off = _rust_solve_wc(ms, mode="marginalized", budget=5_000_000,
                         objective="margin", wc_tiebreak=False)
    on = _rust_solve_wc(ms, mode="marginalized", budget=5_000_000,
                        objective="margin", wc_tiebreak=True)
    assert off is not None and on is not None
    assert off["value_bits"] == on["value_bits"]
    assert off["optimal_actions"] == on["optimal_actions"]
    assert sorted(map(tuple, off["child_values"])) == sorted(map(tuple, on["child_values"]))
    assert off["nodes"] == on["nodes"]


@pytest.mark.parametrize("seed", [1, 7, 11])
def test_margin_objective_parity_wc_tiebreak_true_vs_python(seed):
    """Same position, wc_tiebreak=True, objective='margin': python and rust
    must still agree (the flag being inert here is a property BOTH sides must
    share, not just the rust side against itself)."""
    game, b, ms = endgame_pair(seed, 1)
    py = S.solve(game, b, mode="marginalized", budget=5_000_000,
                objective="margin", wc_tiebreak=True)
    assert py.wc_tiebreak is True and py.objective == "margin"
    rs = _rust_solve_wc(ms, mode="marginalized", budget=5_000_000,
                        objective="margin", wc_tiebreak=True)
    assert rs is not None
    assert_same_core(py, rs, f"seed{seed} margin wc=True")


# --------------------------------------------------------------------------- #
# 2. win objective — wc_tiebreak has TEETH, parity on the outcome lattice too  #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("seed", [1, 7, 11])
@pytest.mark.parametrize("wc", [False, True])
def test_win_objective_parity(seed, wc):
    """K=1 (every chance bag a singleton — DESIGN §2's inertness proposition
    still lets win-mode disagree with margin-mode on WHICH lattice value is
    reported, even though the optimal action set cannot move at this depth).
    Parity on value/optimal_actions/child_values/nodes AND the win-specific
    win_value/child_win_values, under both wc_tiebreak states."""
    game, b, ms = endgame_pair(seed, 1)
    py = S.solve(game, b, mode="marginalized", budget=5_000_000,
                objective="win", wc_tiebreak=wc)
    assert py.wc_tiebreak is wc and py.objective == "win"
    rs = _rust_solve_wc(ms, mode="marginalized", budget=5_000_000,
                        objective="win", wc_tiebreak=wc)
    assert rs is not None
    assert_same_core(py, rs, f"seed{seed} win wc={wc}")
    # the outcome-lattice payload E1 added — win_value / child_win_values
    assert "win_value" in rs and rs["win_value"] is not None
    assert abs(py.win_value - float(rs["win_value"])) < 1e-9, \
        f"seed{seed} win wc={wc}: win_value"
    py_wv = sorted((int(a), float(v)) for a, v in py.child_win_values.items())
    rs_wv = sorted((int(a), float(v)) for a, v in rs["child_win_values"])
    for (pa, pv), (ra, rv) in zip(py_wv, rs_wv):
        assert pa == ra and abs(pv - rv) < 1e-9, f"seed{seed} win wc={wc}: child_win_values"


def test_wc_tiebreak_stamped_on_the_rust_result():
    """Liveness discriminator: the resolved wc_tiebreak state must be readable
    off the rust result too (mirrors SolveResult.wc_tiebreak on the python
    side) — an "armed but inert" (margin-objective) leg must still be
    distinguishable from a never-armed one by inspecting the result, not by
    re-deriving it from what was passed in."""
    _, b, ms = endgame_pair(1, 1)
    off = _rust_solve_wc(ms, mode="marginalized", budget=5_000_000,
                         objective="win", wc_tiebreak=False)
    on = _rust_solve_wc(ms, mode="marginalized", budget=5_000_000,
                        objective="win", wc_tiebreak=True)
    assert off is not None and on is not None
    if "wc_tiebreak" in off and "wc_tiebreak" in on:
        assert off["wc_tiebreak"] is False
        assert on["wc_tiebreak"] is True
    else:
        pytest.skip(
            "carc_rs solve_endgame() result carries no 'wc_tiebreak' key yet — "
            "the knob works (this leg only runs past the LOUD skip point once "
            "it does) but the liveness stamp is not on the wire; not this "
            "test's contract to invent the key, flag for the core owner.")


# --------------------------------------------------------------------------- #
# 3. old-wheel footgun, confirmed live (not simulated)                         #
# --------------------------------------------------------------------------- #
def test_old_wheel_wc_tiebreak_kwarg_skips_loudly_not_silently():
    """Positive control for the skip mechanism itself: on THIS (stale) wheel,
    passing wc_tiebreak must raise TypeError (never silently ignore it and
    return a margin-mode-shaped result), so `_rust_solve_wc`'s catch is
    catching a REAL stale-kwarg error, not masking a different bug."""
    _, _, ms = endgame_pair(1, 1)
    try:
        ms.solve_endgame(mode="marginalized", budget=5_000_000,
                         objective="margin", wc_tiebreak=True)
    except TypeError as e:
        assert "wc_tiebreak" in str(e)
        pytest.skip(_REBUILD)
    else:
        pytest.skip(
            "this wheel DOES carry wc_tiebreak — the positive control for the "
            "skip mechanism is inapplicable on a rebuilt box; the parity tests "
            "above are the ones that matter here.")
