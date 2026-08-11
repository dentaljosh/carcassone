"""F-3 — the desktop `make_production_champion` callers speak the Rust mirror protocol.

The heavyweight evidence is the gate script (`scripts/rustport/gate_f3_callers.py` ->
`measurement/rustport_p6/F3_CALLER_GATES_20260802.json`: 444 action checks, 5/5 legs
byte-identical, guard fires on all three injections). This module is the CHEAP standing
version of the same three questions, so a future edit to one of those files cannot
quietly un-wire it:

  1. the WIRING exists — `start_game` once and `advance` for every applied action of
     BOTH seats — asserted with a RECORDING STUB, so it costs no search at all and is
     backend-independent (it would catch the regression even with carc_rs absent);
  2. the two backends play IDENTICALLY through the real harness (one tiny full game);
  3. the guard still FIRES when an advance is skipped — the half that proves (1) is
     load-bearing rather than decorative.

`resolve_execution`'s own contract (rust and parallel_workers are mutually exclusive)
is unit-tested here too: that pair is what makes `kparallel_latency_bench` RAISE today
if the factory default ever flips, so it is not a detail.
"""
import random
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
for _p in ("src", "scripts", "scripts/human_anchor", "scripts/m5_bench",
           "scripts/measurement_infra"):
    if str(_REPO / _p) not in sys.path:
        sys.path.insert(0, str(_REPO / _p))

import env_preamble  # noqa: E402,F401  production leaf env BEFORE carcassonne_ai

from carcassonne_ai import mirror_protocol as MP  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402

SIMS, K = 8, 1          # wiring, not strength
SEED = 777_000_001

carc_rs = pytest.importorskip("carc_rs", reason="rust backend not built here")


# --------------------------------------------------------------------------- #
# stubs                                                                        #
# --------------------------------------------------------------------------- #
class RecordingAgent:
    """Presents the mirror surface and records every protocol call. Plays the first
    legal action, so it is deterministic and free."""

    neural_moves = heur_moves = exact_moves = n_timeouts = 0
    solver_secs = solver_nodes = 0
    latch_k = None

    def __init__(self, game):
        self._game = game
        self.seated = 0
        self.advanced = []

    def start_game(self, board):
        self.seated += 1

    def advance(self, action, board_after=None):
        self.advanced.append(int(action))

    def choose_action(self, board):
        import numpy as np

        return int(np.flatnonzero(self._game.get_valid_moves(board))[0])


class PlainAgent:
    """No mirror at all (the Python champion / HumanCLIAgent shape)."""

    neural_moves = heur_moves = exact_moves = n_timeouts = 0
    solver_secs = solver_nodes = 0
    latch_k = None

    def __init__(self, game):
        self._game = game

    def choose_action(self, board):
        import numpy as np

        return int(np.flatnonzero(self._game.get_valid_moves(board))[0])


# --------------------------------------------------------------------------- #
# 1. mirror_protocol itself                                                    #
# --------------------------------------------------------------------------- #
def test_seat_and_advance_are_duck_typed():
    g = Game(enable_legal_moves_cache=True)
    mirrored, plain = RecordingAgent(g), PlainAgent(g)
    assert MP.is_mirrored(mirrored) and not MP.is_mirrored(plain)
    assert MP.seat({0: mirrored, 1: plain}, g.get_init_board()) == 1
    assert MP.advance([mirrored, plain], 17) == 1
    assert mirrored.advanced == [17]


def test_resolve_execution_never_pairs_rust_with_parallel_workers():
    rust = MP.resolve_execution("rust", profile="desktop")
    assert rust.is_rust and rust["parallel_workers"] is None
    assert "parallel_workers" not in rust.factory_kwargs()
    py = MP.resolve_execution("python", profile="desktop")
    assert not py.is_rust and "rust_threads" not in py.factory_kwargs()
    # the desktop profile's spawn split is still honoured on python
    assert py["parallel_workers"] == 8
    assert MP.resolve_execution("python", profile="desktop",
                                no_parallel=True)["parallel_workers"] is None


def test_inherit_is_the_caller_default_and_tracks_the_factory():
    """The whole point of `inherit`: it is what the factory would do unasked, so a flip
    of the factory default reaches all four harnesses without editing one of them.
    ⚠️ THAT FLIP LANDED 2026-08-03 — the factory default is `"auto"`, so `inherit` now
    resolves to the yaml engine (today `rust`), not to `python`. This assertion was
    written to survive it and did; it is the reason no harness needed an edit."""
    import inspect

    from carcassonne_ai.champion_factory import make_production_champion

    sig_default = inspect.signature(make_production_champion).parameters["backend"].default
    assert MP.factory_default_backend() == (
        sig_default if sig_default != "auto" else MP.resolve_execution("auto")["backend"])
    assert MP.resolve_execution("inherit")["backend"] == MP.factory_default_backend()

    # every converted caller defaults to it
    import bench_champion as BC
    import kparallel_latency_bench as KP
    import play_harness as PH
    import play_vs_tier1_gui as GUI

    assert (inspect.signature(GUI.build_opponent).parameters["backend"].default
            == "inherit")
    assert (inspect.signature(PH.resolve_execution).parameters["backend"].default
            == "inherit")
    assert (inspect.signature(BC.run_budget).parameters["backend"].default
            == "python")     # run_budget is called with an already-resolved literal
    assert (inspect.signature(KP.time_row).parameters["backend"].default == "python")


def test_resolve_execution_auto_reads_the_yaml():
    auto = MP.resolve_execution("auto", profile="desktop")
    from carcassonne_ai.champion_factory import deploy_profile

    assert auto["backend"] == deploy_profile("desktop")["backend"]
    # and whatever it resolved to, the kwargs it hands the factory are legal
    from carcassonne_ai.champion_factory import make_production_champion

    make_production_champion("fair", seed=0, sims=4, k_dets=1, verify=False,
                             **auto.factory_kwargs())


def test_resolve_execution_is_fail_safe_but_never_downgrades_an_explicit_rust():
    boom = MP.resolve_execution("auto", profile="no-such-profile", warn=None)
    assert boom["backend"] in ("python", "rust")     # fail-safe, never an exception
    with pytest.raises(ValueError):
        MP.resolve_execution("torch")


# --------------------------------------------------------------------------- #
# 2. play_harness — the E4 human path                                          #
# --------------------------------------------------------------------------- #
def test_play_harness_drives_the_mirror_for_both_seats():
    import play_harness as PH

    g = Game(enable_legal_moves_cache=True)
    champ, human = RecordingAgent(g), PlainAgent(g)
    rec = PH.play_game(g, SEED, {0: human, 1: champ},
                       {0: "human", 1: "champ"}, {"t": 1})
    n = rec["result"]["n_moves"]
    assert champ.seated == 1, "start_game must be called exactly once, on the init board"
    assert champ.advanced == [m["action"] for m in rec["moves"]], (
        "the mirror must advance on EVERY applied action of BOTH seats, in order")
    assert len(champ.advanced) == n


def test_play_harness_python_and_rust_play_the_same_game():
    import play_harness as PH

    legs = {}
    for backend in ("python", "rust"):
        ex = MP.resolve_execution(backend, profile=None)
        g = Game(enable_legal_moves_cache=True)
        agents = {s: PH._make_fair_agent(g, SIMS, K, seed=100 + s, execution=ex)
                  for s in (0, 1)}
        rec = PH.play_game(g, SEED, agents, {0: "a", 1: "b"}, {"t": 1})
        legs[backend] = ([m["action"] for m in rec["moves"]], rec["result"]["scores"])
    assert legs["python"] == legs["rust"]


def test_play_harness_raises_when_the_advance_is_skipped(monkeypatch):
    """The pre-F-3 behaviour, injected. It must be LOUD, not silently wrong."""
    import play_harness as PH
    from carcassonne_ai.rust_agent import MirrorDesync

    ex = MP.resolve_execution("rust", profile=None)
    g = Game(enable_legal_moves_cache=True)
    agents = {s: PH._make_fair_agent(g, SIMS, K, seed=100 + s, execution=ex)
              for s in (0, 1)}
    monkeypatch.setattr(MP, "advance", lambda *a, **k: 0)
    with pytest.raises(MirrorDesync):
        PH.play_game(g, SEED, agents, {0: "a", 1: "b"}, {"t": 1})


# --------------------------------------------------------------------------- #
# 3. play_vs_tier1_gui — the interactive path                                  #
# --------------------------------------------------------------------------- #
class _FakeGUI:
    """Runs the SHIPPED `GameGUI` mirror methods with the Tk chrome stubbed."""

    def __init__(self, game, opponent, human_seat=0):
        import play_vs_tier1_gui as GUI

        self._GUI = GUI
        self.game, self.ai, self.human = game, opponent, human_seat
        self.board = game.get_init_board()
        self.selected_cell = None
        self.rotation_options, self.rotation_idx = [], 0
        GUI.GameGUI._seat_mirror(self)

    def _advance(self):
        pass

    def _advance_mirror(self, idx):
        self._GUI.GameGUI._advance_mirror(self, idx)

    def play(self, plies=None, skip_advance_at=None):
        import numpy as np

        acts = []
        while not self.board.state.is_terminated() and (plies is None
                                                        or len(acts) < plies):
            if self.board.state.current_player == self.human:
                idx = int(np.flatnonzero(self.game.get_valid_moves(self.board))[0])
            else:
                idx = int(self.ai.pick(self.board,
                                       self.game.get_valid_moves(self.board)))
            acts.append(idx)
            if skip_advance_at is not None and len(acts) - 1 == skip_advance_at:
                self.board, _ = self.game.get_next_state(self.board, idx)
                continue
            self._GUI.GameGUI._apply_action(self, idx)
        return acts


def _fake_opponent(agent):
    import play_vs_tier1_gui as GUI

    return GUI.Opponent(name="stub", pick=lambda b, m: agent.choose_action(b),
                        agent=agent)


def test_gui_apply_action_is_the_single_choke_point():
    g = Game(enable_legal_moves_cache=True)
    stub = RecordingAgent(g)
    gui = _FakeGUI(g, _fake_opponent(stub), human_seat=0)
    acts = gui.play(plies=12)
    assert stub.seated == 1
    assert stub.advanced == acts, "every applied action, human's and AI's, must advance"


def test_gui_python_and_rust_play_the_same_game():
    import play_vs_tier1_gui as GUI

    legs = {}
    for backend in ("python", "rust"):
        random.seed(SEED)
        g = Game(enable_legal_moves_cache=True)
        opp = GUI.build_opponent("champion", seed=7, sims=SIMS, k_dets=K,
                                 verbose=False, backend=backend, profile=None)
        legs[backend] = _FakeGUI(g, opp).play()
    assert legs["python"] == legs["rust"]


def test_gui_raises_when_an_advance_is_skipped():
    import play_vs_tier1_gui as GUI
    from carcassonne_ai.rust_agent import MirrorDesync

    random.seed(SEED)
    g = Game(enable_legal_moves_cache=True)
    opp = GUI.build_opponent("champion", seed=7, sims=SIMS, k_dets=K, verbose=False,
                             backend="rust", profile=None)
    with pytest.raises(MirrorDesync):
        _FakeGUI(g, opp).play(skip_advance_at=1)


def test_gui_tier1_opponent_carries_no_agent_and_stays_python():
    import play_vs_tier1_gui as GUI

    opp = GUI.build_opponent("tier1", seed=1, sims=None, k_dets=None, verbose=False,
                             backend="rust")
    assert opp.agent is None                      # nothing to seat, nothing to advance
    assert MP.seat(opp.agent, None) == 0


# --------------------------------------------------------------------------- #
# 4. bench_champion / kparallel — mid-game entry by replay                     #
# --------------------------------------------------------------------------- #
def _rows(n=2, stride=29):
    import json

    src = _REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
    rows = []
    with open(src) as fh:
        for line in fh:
            if not line.strip():
                continue
            g = json.loads(line)
            for ply in range(int(len(g["actions"]) * 0.4),
                             int(len(g["actions"]) * 0.7), stride):
                rows.append({"pos_id": len(rows), "deck_seed": int(g["deck_seed"]),
                             "actions": [int(a) for a in g["actions"][:ply]],
                             "ply": ply})
                if len(rows) >= n:
                    return rows
    return rows


def test_bench_champion_reseat_matches_python_at_every_root():
    import bench_champion as BC
    from carcassonne_ai import champion_factory as CF

    rows = _rows(2)
    legs = {}
    for backend in ("python", "rust"):
        agent = CF.make_production_champion(
            "fair", game=Game(enable_legal_moves_cache=True), seed=101, sims=SIMS,
            k_dets=K, verify=False,
            # PINNED in BOTH directions (2026-08-03): the factory default is now
            # "auto", so an omitted kwarg would make the "python" leg a Rust one.
            backend=backend)
        acts = []
        for i, row in enumerate(rows):
            _g, board = BC.replay(Game, row)
            BC.reseat(agent, row, i)
            agent._latched = False
            acts.append(int(agent.choose_action(board)))
            assert agent._move_idx == i + 1
        legs[backend] = acts
    assert legs["python"] == legs["rust"]


def test_midgame_entry_without_the_prefix_replay_raises():
    """`reseat` is not optional bookkeeping — an unreplayed mirror must be caught."""
    import bench_champion as BC
    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai.rust_agent import MirrorDesync

    row = _rows(1)[0]
    agent = CF.make_production_champion(
        "fair", game=Game(enable_legal_moves_cache=True), seed=7, sims=SIMS, k_dets=K,
        verify=False, backend="rust")
    _g, board = BC.replay(Game, row)
    agent.start_game_from_seed(int(row["deck_seed"]))       # prefix NOT replayed
    with pytest.raises(MirrorDesync):
        agent.choose_action(board)


def test_kparallel_rust_rows_are_threads_and_agree_with_python():
    import kparallel_latency_bench as KP

    roots = KP.load_roots(KP.DEFAULT_GAMES, 2, 0.35, 0.70, 11)
    assert all("prefix" in m for _g, _b, m in roots)
    _s, py_actions, _t = KP.time_row(roots, K, SIMS, None, 90_000, backend="python")
    _s, rs_actions, _t = KP.time_row(roots, K, SIMS, None, 90_000, backend="rust")
    _s, rs2_actions, _t = KP.time_row(roots, K, SIMS, 2, 90_000, backend="rust")
    assert py_actions == rs_actions == rs2_actions
