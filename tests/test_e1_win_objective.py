"""E1 — win-probability endgame objective (measurement/e1_winobj_20260814/DESIGN.md).

Covers, on both implementations (python oracle + carc_rs where present):
  * the lattice primitives (outcome / lexicographic comparison, WIN_TIE);
  * default-off inertness: objective="margin" carries NO win payload and takes
    the untouched incumbent code path (the golden suite tests/golden/ is the
    frozen-fixture proof for the incumbent values themselves);
  * the DESIGN §2 K<=2 inertness proposition: at the deployed exact_max_k=2
    the two objectives coincide EXACTLY (singleton chance bags);
  * marginalized-only enforcement (clairvoyant + win is refused);
  * plumbing: FairHeuristicPriorAgent / RustFairAgent / champion_factory
    accept and resolve `exact_objective`; the old-wheel footgun fails LOUDLY;
  * rust<->python win-mode parity on replayed endgame positions;
  * the K=3 POSITIVE CONTROL: a pinned real-game position where the two
    objectives provably disagree, computed by BOTH modes, asserting they
    disagree (surface-B inverted-liveness convention — the leaf hash does not
    move on this knob, so liveness is proven by disagreement, not by hash).

Rust legs skip LOUDLY (with the per-box rebuild instruction) when the
installed carc_rs wheel predates the knob — a skip on a box that just
rebuilt is a failure of the build, not of the test.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "src", ROOT / "engine", ROOT / "scripts" / "level2"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import endgame_solver as S  # noqa: E402
from carcassonne_ai import fair_agent  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402

CONTROLS = ROOT / "measurement" / "e1_winobj_20260814" / "raw" / "divergence_controls.json"


# --------------------------------------------------------------------------- #
# helpers                                                                       #
# --------------------------------------------------------------------------- #
def _endgame(seed: int, k: int):
    """Roll a seeded game to the first TILES decision with k_remaining <= k
    (the fair solver tests' fixture shape)."""
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    board = game.get_init_board()
    actions = []
    while True:
        st = board.state
        if (st.phase == GamePhase.TILES
                and fair_agent.k_remaining(st) <= k):
            return game, board, actions
        legal = [int(x) for x in np.flatnonzero(game.get_valid_moves(board))]
        a = legal[len(legal) // 2]
        actions.append(a)
        board, _ = game.get_next_state(board, a)


def _rust_solver_agent(init_state, actions):
    """A carc_rs FairAgentRs seated on the replayed game, or a LOUD skip."""
    carc_rs = pytest.importorskip("carc_rs")
    from carcassonne_ai.champion_factory import production_prior_cfg
    from carcassonne_ai.rust_agent import _draw_order_for_mirror, search_config_rs

    try:
        rs = carc_rs.FairAgentRs(
            search_config_rs(production_prior_cfg(), 1), k_dets=1, seed=0,
            exact_max_k=2, exact_objective="margin")
    except TypeError:
        pytest.skip(
            "carc_rs wheel PREDATES the E1 exact_objective knob — the per-box "
            "rebuild footgun: rebuild the wheel on THIS box "
            "(maturin build --release -m rust/carc/carc-py/Cargo.toml) "
            "before trusting any exact_objective result here.")
    rs.start_game_from_deck(_draw_order_for_mirror(init_state, False))
    for a in actions:
        rs.advance(int(a))
    return rs


def _bits(b):
    import struct

    return struct.unpack("<d", struct.pack("<Q", b))[0]


# --------------------------------------------------------------------------- #
# lattice primitives                                                            #
# --------------------------------------------------------------------------- #
def test_outcome_lattice_win_draw_loss():
    assert S._outcome(3.0) == 1.0
    assert S._outcome(0.0) == 0.5          # ties are real: the E4 ledger has a 55-55
    assert S._outcome(-1.0) == 0.0


def test_lex_better_win_first_margin_tiebreak():
    # win dominates margin
    assert S._lex_better((0.9, -5.0), (0.5, +9.0), maximize=True)
    # within WIN_TIE, margin decides
    assert S._lex_better((0.5 + 1e-12, 3.0), (0.5, 2.0), maximize=True)
    assert not S._lex_better((0.5, 2.0), (0.5 + 1e-12, 3.0), maximize=True)
    # minimizer mirror-image
    assert S._lex_better((0.1, -2.0), (0.5, -9.0), maximize=False)
    assert S._lex_better((0.5, -3.0), (0.5, -2.0), maximize=False)
    # keep-first: equal pairs are NOT better
    assert not S._lex_better((0.5, 2.0), (0.5, 2.0), maximize=True)


# --------------------------------------------------------------------------- #
# python solver semantics                                                       #
# --------------------------------------------------------------------------- #
def test_margin_default_has_no_win_payload():
    game, board, _ = _endgame(11, 2)
    r = S.solve(game, board, mode="marginalized")
    assert r.objective == "margin"
    assert r.win_value is None and r.child_win_values is None


def test_win_is_marginalized_only():
    game, board, _ = _endgame(11, 2)
    with pytest.raises(AssertionError, match="marginalized-only"):
        S.solve(game, board, mode="clairvoyant", objective="win")
    with pytest.raises(AssertionError, match="margin|win"):
        S.solve(game, board, mode="marginalized", objective="wins")


@pytest.mark.parametrize("seed", [11, 12, 13])
def test_k2_inertness_proposition_python(seed):
    """DESIGN §2: at K<=2 every chance bag is a singleton => the solve is a
    deterministic minimax, outcome is a monotone transform of the margin, and
    the two objectives coincide EXACTLY — same optimal set, same margin, and
    win_value == outcome(margin)."""
    game, board, _ = _endgame(seed, 2)
    m = S.solve(game, board, mode="marginalized")
    w = S.solve(game, board, mode="marginalized", objective="win")
    assert m.optimal_actions == w.optimal_actions
    assert m.value == w.value
    assert w.win_value == S._outcome(m.value)
    assert m.child_values == w.child_values
    for a, mv in m.child_values.items():
        assert w.child_win_values[a] == S._outcome(mv)


def test_win_mode_budget_exceeded_still_raises():
    game, board, _ = _endgame(11, 2)
    with pytest.raises(S.BudgetExceeded):
        S.solve(game, board, mode="marginalized", budget=1, objective="win")


# --------------------------------------------------------------------------- #
# agent plumbing (python)                                                       #
# --------------------------------------------------------------------------- #
def test_fair_prior_agent_accepts_and_resolves_the_knob():
    g = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    a = fair_agent.FairHeuristicPriorAgent(g, sims=4, k_dets=1, seed=1,
                                           exact_objective="win")
    assert a.exact_objective == "win"
    b = fair_agent.FairHeuristicPriorAgent(g, sims=4, k_dets=1, seed=1)
    assert b.exact_objective == "margin"
    with pytest.raises(ValueError, match="exact_objective"):
        fair_agent.FairHeuristicPriorAgent(g, sims=4, k_dets=1, seed=1,
                                           exact_objective="wins")


def test_fair_prior_agent_passes_objective_to_the_solver(monkeypatch):
    """The agent's _exact_move forwards objective ONLY when non-default, so
    the incumbent's solver call is byte-for-byte the pre-knob one."""
    calls = []

    class _Res:
        optimal_actions = [7]
        nodes = 1

    def fake_solve(*args, **kw):
        calls.append(kw)
        return _Res()

    game, board, _ = _endgame(11, 2)
    monkeypatch.setattr(S, "solve", fake_solve)
    for obj, expect in (("margin", None), ("win", "win")):
        agent = fair_agent.FairHeuristicPriorAgent(
            game, sims=4, k_dets=1, seed=1, exact_objective=obj)
        assert agent._exact_move(board) == 7
        assert calls[-1].get("objective") == expect
    assert "objective" not in calls[0]      # margin: kwarg ABSENT, not "margin"


def test_champion_factory_forwards_exact_objective():
    from carcassonne_ai import champion_factory

    g = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    a = champion_factory.build_fair_champion(
        g, sims=4, k_dets=1, seed=1, exact_objective="win")
    assert a.exact_objective == "win"
    b = champion_factory.build_fair_champion(g, sims=4, k_dets=1, seed=1)
    assert b.exact_objective == "margin"


def test_rust_agent_old_wheel_fails_loudly(monkeypatch):
    """A 'win' request against a wheel without the kwarg must raise the
    rebuild-instruction RuntimeError, never silently play margin."""
    import carcassonne_ai.rust_agent as RA

    class _FakeRs:
        def __init__(self, *a, **kw):
            if "exact_objective" in kw:
                raise TypeError(
                    "FairAgentRs() got an unexpected keyword argument "
                    "'exact_objective'")

    fake_mod = type(sys)("carc_rs")
    fake_mod.FairAgentRs = _FakeRs
    monkeypatch.setitem(sys.modules, "carc_rs", fake_mod)
    monkeypatch.setattr(RA, "search_config_rs", lambda cfg, sims: None)

    g = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    with pytest.raises(RuntimeError, match="rebuild the wheel"):
        RA.RustFairAgent(g, None, sims=4, k_dets=1, exact_objective="win")
    # margin: the kwarg is never passed, so the old wheel keeps working
    RA.RustFairAgent(g, None, sims=4, k_dets=1)


# --------------------------------------------------------------------------- #
# rust parity + liveness (skip LOUDLY on a pre-E1 wheel)                        #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("seed", [11, 12])
def test_rust_k2_inertness_and_python_parity(seed):
    game, board, actions = _endgame(seed, 2)
    # the mirror must be seated on the INITIAL state's deck, then advanced
    random.seed(seed)
    g2 = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    b0 = g2.get_init_board()
    rs = _rust_solver_agent(b0.state, actions)

    rm = rs.solve_marginalized(objective="margin")
    rw = rs.solve_marginalized(objective="win")
    assert rm is not None and rw is not None
    # liveness discriminator: margin has NO win payload, win does
    assert rm["win_value"] is None and rm["child_win_values"] == []
    assert rw["win_value"] is not None
    assert rm["objective"] == "margin" and rw["objective"] == "win"
    # K<=2 inertness on the rust side
    assert rm["optimal_actions"] == rw["optimal_actions"]
    assert rm["value_bits"] == rw["value_bits"]
    # python parity in win mode
    pw = S.solve(game, board, mode="marginalized", objective="win")
    assert min(rw["optimal_actions"]) == min(pw.optimal_actions)
    assert abs(rw["win_value"] - pw.win_value) < 1e-12
    pw_w = pw.child_win_values
    for a, bits in rw["child_win_values"]:
        assert abs(pw_w[a] - _bits(bits)) < 1e-12


def test_rust_agent_stats_stamp_resolved_objective():
    carc_rs = pytest.importorskip("carc_rs")
    from carcassonne_ai.champion_factory import production_prior_cfg
    from carcassonne_ai.rust_agent import search_config_rs

    try:
        rs = carc_rs.FairAgentRs(
            search_config_rs(production_prior_cfg(), 1), k_dets=1, seed=0,
            exact_objective="win")
    except TypeError:
        pytest.skip(
            "carc_rs wheel PREDATES the E1 exact_objective knob — rebuild the "
            "wheel on THIS box before trusting any exact_objective result.")
    rs.start_game_from_seed("11")
    st = rs.stats()
    assert st["exact_objective"] == "win"
    with pytest.raises(ValueError):
        carc_rs.FairAgentRs(
            search_config_rs(production_prior_cfg(), 1), k_dets=1, seed=0,
            exact_objective="wins")


# --------------------------------------------------------------------------- #
# THE POSITIVE CONTROL — pinned K=3 real-game position, objectives disagree     #
# --------------------------------------------------------------------------- #
def test_positive_control_objectives_disagree():
    """Replays the pinned divergence position (a real banked self-play game's
    K=3 TILES ply) and asserts the two objectives PICK DIFFERENT MOVES — the
    inverted-liveness proof that the flag changes play. K=3 is the CONTROL'S
    construction depth only (no K<=2 control can exist, DESIGN §2); nothing
    here proposes playing at K=3 — depth is closed (CL-076/F13).

    ~1-2 min (a K=3 marginalized double-solve on the rust engine)."""
    if not CONTROLS.exists():
        pytest.skip(
            "no pinned control yet — run scripts/e1_winobj/"
            "find_divergence_position.py --from-bank (writes "
            f"{CONTROLS}); this skip is LOUD by design.")
    data = json.loads(CONTROLS.read_text())
    hits = data.get("hits") or []
    if not hits:
        pytest.fail(
            "divergence_controls.json exists but has NO hits — the finder "
            "completed without a control; the positive-control obligation is "
            "UNMET (fail, not skip: a committed empty control file means the "
            "liveness proof is missing, not pending).")
    # Prefer the strongest control (largest P(win) gap) so the disagreement
    # assert can never ride on a tolerance-scale value.
    h = max(hits, key=lambda x: x.get("delta_win_prob", 0.0))
    assert h["k_remaining"] == 3

    random.seed(int(h["deck_seed"]))
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    board = game.get_init_board()
    bank = ROOT / "measurement" / "champ_action_logs" / "champ_games.jsonl"
    rec = None
    with open(bank) as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                if int(r["deck_seed"]) == int(h["deck_seed"]):
                    rec = r
                    break
    assert rec is not None, f"deck_seed {h['deck_seed']} not in the bank"
    actions = [int(x) for x in rec["actions"]][: int(h["ply"])]
    for a in actions:
        board, _ = game.get_next_state(board, a)
    st = board.state
    assert st.phase == GamePhase.TILES
    assert fair_agent.k_remaining(st) == 3

    random.seed(int(h["deck_seed"]))
    g2 = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    b0 = g2.get_init_board()
    rs = _rust_solver_agent(b0.state, actions)
    rm = rs.solve_marginalized(budget=4_000_000, objective="margin")
    rw = rs.solve_marginalized(budget=4_000_000, objective="win")
    assert rm is not None and rw is not None
    pick_m, pick_w = min(rm["optimal_actions"]), min(rw["optimal_actions"])
    assert pick_m == int(h["pick_margin"]) and pick_w == int(h["pick_win"])
    assert pick_m != pick_w, "the pinned control no longer diverges"
    # the certificate, recomputed: the win pick buys strictly more E[outcome],
    # the margin pick strictly more E[margin] (mover POV)
    cw = {a: _bits(b) for a, b in rw["child_win_values"]}
    cm = {a: _bits(b) for a, b in rm["child_values"]}
    sgn = 1.0 if rm["to_move"] == 0 else -1.0
    assert sgn * (cw[pick_w] - cw[pick_m]) > S._WIN_TIE
    # margin leg within TIE (DESIGN amendment §4b: a margin-TIED,
    # win-differing control is the purest disagreement — exact-zero would
    # reject it on float dust)
    assert sgn * (cm[pick_m] - cm[pick_w]) >= -S._TIE
