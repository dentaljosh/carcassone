"""SIMS-SPLIT (``sims_tile`` / ``sims_meeple``) — the byte-identity + correctness gate.

The play-time knob for the phase-asymmetric sims-split lever (docs/LEVER_INDEX.md §5):
a single fair agent searches its TILES decisions at one per-world budget and its
MEEPLES decisions at another. The whole adoption argument rests on four properties,
each proven here on BOTH backends (python ``FairHeuristicPriorAgent`` and rust
``RustFairAgent`` / ``carc_rs.FairAgentRs``):

  (a) KNOBS-UNSET BYTE-IDENTITY — a full game (exact-K<=2 latch included) reproduces
      ``tests/golden/simsplit_off.json``, which was recorded on the PRE-change tree
      (generator: ``scripts/measurement_infra/gen_simsplit_off_fixture.py``): same
      action at every move, float/bit-equal pooled (N, W) at every searched move,
      same latch trajectory. Setting BOTH knobs equal to ``sims`` must also
      reproduce it (the override path at an equal budget IS the default path).
  (b) KNOBS-SET SANITY — the split agent is move-for-move THE TILE-BUDGET AGENT on
      TILES decisions and THE MEEPLE-BUDGET AGENT on MEEPLES decisions (action AND
      pooled (N, W) equality against two uniform-budget control agents), the two
      controls genuinely differ (so the equality is not vacuous), and the rust
      ``last_move()["sims_used"]`` reads the per-phase budget — including at the
      PRODUCTION shape k8 x (1376 tile / 344 meeple).
  (c) PYTHON<->RUST PARITY WITH KNOBS SET — full games stepped side by side:
      identical chosen action and pooled visits at every move (the G6 pattern, at
      test sims).
  (d) LATCH INTERACTION — the exact-K<=2 marginalized latch still fires on a TILES
      decision, turn-atomically, at the same ply with the same latch_k, knobs set
      or not (solver decisions consume no sims, so the split cannot touch them).

Plus loud rejection of the combinations the knob cannot honour (parallel_workers /
intra_reuse / oracle_prior_mult / non-positive budgets) and factory threading.
"""
import json
import os
import random
import sys
from pathlib import Path

import numpy as np  # noqa: F401  (import parity with sibling suites)
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "level2"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts",
                                "measurement_infra"))

from carcassonne_ai import fair_agent as FA  # noqa: E402
from carcassonne_ai.champion_factory import build_fair_champion  # noqa: E402
from carcassonne_ai.fair_agent import FairHeuristicPriorAgent  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig  # noqa: E402
from snapshot import frozen_v29_cfg  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402

# The compact-leaf test toggle is a conftest module global that would move the leaf
# under the fixture (same guard as test_kparallel).
pytestmark = pytest.mark.skipif(
    os.environ.get("CARC_TEST_COMPACT_LEAF") == "1",
    reason="compact-leaf toggle changes the leaf under the frozen fixture",
)

REPO = Path(__file__).resolve().parents[1]
GOLDEN = REPO / "tests" / "golden" / "simsplit_off.json"


@pytest.fixture(scope="module")
def golden() -> dict:
    return json.loads(GOLDEN.read_text())


def scenario_config() -> HeuristicPriorConfig:
    """EXACTLY the generator's config (keep in lockstep) — leaf pinned to the
    hash-asserted frozen v2.9 config, never the import-order-dependent
    DEFAULT_CONFIG."""
    return HeuristicPriorConfig(final_select="visits", leaf_cfg=frozen_v29_cfg())


def _require_rust_simsplit():
    """The installed carc_rs must carry the per-call override. An actionable
    failure beats a TypeError from deep inside a game loop: the fix is to
    rebuild + reinstall the dev wheel (maturin build -m rust/carc/carc-py/...)."""
    carc_rs = pytest.importorskip("carc_rs")
    import inspect

    try:
        sig = str(inspect.signature(carc_rs.FairAgentRs.choose_action))
    except (TypeError, ValueError):   # builtins may not expose a signature
        return
    if "sims_override" not in sig:
        pytest.fail(
            f"the installed carc_rs wheel ({carc_rs.__file__}) predates the "
            "sims_override API — rebuild/reinstall the dev wheel from "
            "rust/carc/carc-py before running the sims-split gate")


class _PoolSpy:
    """Capture every (agg_n, agg_w) handed to the pooled-Q pick, in call order."""

    def __init__(self):
        self.calls = []
        self._real = FA.pooled_q_argmax

    def __call__(self, agg_n, agg_w, min_visits=FA.DEFAULT_MIN_POOLED_VISITS):
        self.calls.append((dict(agg_n), dict(agg_w)))
        return self._real(agg_n, agg_w, min_visits)


def _replay_python(golden, **agent_kw):
    """Drive the fixture scenario with a python agent built with ``agent_kw`` on
    top of the fixture budget. Returns (decisions, agent, final_key)."""
    cfg = scenario_config()
    game = Game(enable_legal_moves_cache=True)
    random.seed(golden["deck_seed"])
    board = game.get_init_board()
    agent = FairHeuristicPriorAgent(game, cfg=cfg, sims=golden["sims"],
                                    k_dets=golden["k_dets"],
                                    seed=golden["agent_seed"], **agent_kw)
    spy = _PoolSpy()
    FA.pooled_q_argmax = spy
    decisions = []
    try:
        while game.get_game_ended(board, 0) == 0.0:
            before = len(spy.calls)
            a = int(agent.choose_action(board))
            if len(spy.calls) > before:
                agg_n, agg_w = spy.calls[-1]
                pooled = [[int(k), float(agg_n[k]).hex(), float(agg_w[k]).hex()]
                          for k in agg_n]
                kind = "search"
            else:
                pooled = []
                kind = ("exact" if agent.last_pooled_visits == {} and agent._latched
                        else "forced")
            decisions.append({"kind": kind, "action": a, "pooled": pooled})
            board, _ = game.get_next_state(board, a)
    finally:
        FA.pooled_q_argmax = spy._real
    return decisions, agent, game.string_representation(board)


def _replay_rust(golden, collect_sims_used=False, **agent_kw):
    from carcassonne_ai.rust_agent import RustFairAgent

    cfg = scenario_config()
    game = Game(enable_legal_moves_cache=True)
    random.seed(golden["deck_seed"])
    board = game.get_init_board()
    agent = RustFairAgent(game, cfg, sims=golden["sims"], k_dets=golden["k_dets"],
                          seed=golden["agent_seed"], **agent_kw)
    agent.start_game(board)
    decisions = []
    while game.get_game_ended(board, 0) == 0.0:
        phase = board.state.phase
        a = int(agent.choose_action(board))
        m = agent.last_move()
        kind = ("exact" if m["exact"] else "forced" if m["forced"] else "search")
        d = {"kind": kind, "action": a,
             "pooled_bits": [[int(x), int(n), int(w)] for x, n, w in m["pooled"]]}
        if collect_sims_used:
            d["sims_used"] = int(m["sims_used"])
            d["phase"] = phase.value
        decisions.append(d)
        board, _ = game.get_next_state(board, a)
        agent.advance(a)
    return decisions, agent, agent.string_repr()


def _assert_matches_python_golden(decisions, agent, final_key, golden):
    py = golden["python"]
    assert [d["action"] for d in decisions] == py["actions"]
    for i, (got, want) in enumerate(zip(decisions, py["decisions"])):
        assert got["kind"] == want["kind"], f"ply {i}: decision kind differs"
        assert got["pooled"] == want["pooled"], f"ply {i}: pooled (N,W) differs"
    assert final_key == py["final_key"]
    assert agent.heur_moves == py["heur_moves"]
    assert agent.exact_moves == py["exact_moves"]
    assert agent.n_timeouts == py["n_timeouts"]
    assert agent.latch_k == py["latch_k"]


def _assert_matches_rust_golden(decisions, agent, final_repr, golden):
    rs = golden["rust"]
    assert [d["action"] for d in decisions] == rs["actions"]
    for i, (got, want) in enumerate(zip(decisions, rs["decisions"])):
        assert got["kind"] == want["kind"], f"ply {i}: decision kind differs"
        assert got["pooled_bits"] == want["pooled_bits"], \
            f"ply {i}: pooled raw bits differ"
    assert final_repr == rs["final_repr"]
    st = agent.stats()
    assert st["heur_moves"] == rs["heur_moves"]
    assert st["exact_moves"] == rs["exact_moves"]
    assert st["n_timeouts"] == rs["n_timeouts"]
    assert st["latch_k"] == rs["latch_k"]


# --------------------------------------------------------------------------- #
# (a) KNOBS-UNSET (and explicit-equal) BYTE-IDENTITY vs the pre-change fixture #
# --------------------------------------------------------------------------- #
@pytest.mark.slow      # a full game at sims=24 k2 (~1 min): the production guard
@pytest.mark.parametrize("agent_kw", [
    {},                                              # the default path itself
    {"sims_tile": 24, "sims_meeple": 24},            # override == budget: same path
], ids=["unset", "explicit-equal"])
def test_python_matches_pre_change_fixture(golden, agent_kw):
    decisions, agent, final_key = _replay_python(golden, **agent_kw)
    _assert_matches_python_golden(decisions, agent, final_key, golden)


@pytest.mark.parametrize("agent_kw", [
    {},
    {"sims_tile": 24, "sims_meeple": 24},
], ids=["unset", "explicit-equal"])
def test_rust_matches_pre_change_fixture(golden, agent_kw):
    _require_rust_simsplit()
    decisions, agent, final_repr = _replay_rust(golden, **agent_kw)
    _assert_matches_rust_golden(decisions, agent, final_repr, golden)


def test_fixture_covers_the_latch(golden):
    """The fixture itself must exercise (d): the latch fired on a TILES decision
    and handed the boundary turn to the solver turn-atomically."""
    py = golden["python"]
    assert py["exact_moves"] > 0 and py["latch_k"] is not None
    kinds = [d["kind"] for d in py["decisions"]]
    first = kinds.index("exact")
    assert py["decisions"][first]["phase"] == "tiles", "latch fired off-TILES"
    assert all(k == "exact" for k in kinds[first:]), \
        "a searched decision followed the latch (turn-atomicity broken)"


# --------------------------------------------------------------------------- #
# (b) KNOBS-SET: per-phase behaviour == the uniform-budget control agents       #
# --------------------------------------------------------------------------- #
TILE_SIMS, MEEPLE_SIMS = 24, 8


def _trio_python(golden, max_plies):
    """split(tile=24, meeple=8) vs uniform-24 vs uniform-8, asked in lockstep on
    the SAME board stream (advanced by the split agent's action)."""
    cfg = scenario_config()
    random.seed(golden["deck_seed"])
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    # Separate Games so no agent can lean on another's legal-move memo.
    split = FairHeuristicPriorAgent(
        game, cfg=cfg, sims=golden["sims"], k_dets=golden["k_dets"],
        seed=golden["agent_seed"], sims_tile=TILE_SIMS, sims_meeple=MEEPLE_SIMS)
    uni_t = FairHeuristicPriorAgent(
        Game(enable_legal_moves_cache=True), cfg=cfg, sims=TILE_SIMS,
        k_dets=golden["k_dets"], seed=golden["agent_seed"])
    uni_m = FairHeuristicPriorAgent(
        Game(enable_legal_moves_cache=True), cfg=cfg, sims=MEEPLE_SIMS,
        k_dets=golden["k_dets"], seed=golden["agent_seed"])
    spy = _PoolSpy()
    FA.pooled_q_argmax = spy
    checked = {"tiles": 0, "meeples": 0}
    controls_differed = 0
    try:
        for _ply in range(max_plies):
            if game.get_game_ended(board, 0) != 0.0:
                break
            phase = board.state.phase
            n0 = len(spy.calls)
            a_split = int(split.choose_action(board))
            n1 = len(spy.calls)
            a_t = int(uni_t.choose_action(board))
            n2 = len(spy.calls)
            a_m = int(uni_m.choose_action(board))
            n3 = len(spy.calls)
            # All three took the same branch (searched, or all forced/exact).
            assert (n1 - n0) == (n2 - n1) == (n3 - n2)
            if n1 > n0:               # searched
                p_split, p_t, p_m = spy.calls[n0], spy.calls[n1], spy.calls[n2]
                if phase == GamePhase.TILES:
                    assert a_split == a_t, "split != uniform-24 on a TILES decision"
                    assert p_split == p_t, "split pooled != uniform-24 on TILES"
                    checked["tiles"] += 1
                else:
                    assert a_split == a_m, "split != uniform-8 on a MEEPLES decision"
                    assert p_split == p_m, "split pooled != uniform-8 on MEEPLES"
                    checked["meeples"] += 1
                if p_t != p_m:
                    controls_differed += 1
            board, _ = game.get_next_state(board, a_split)
    finally:
        FA.pooled_q_argmax = spy._real
    return checked, controls_differed


@pytest.mark.slow      # 3 agents over a 40-ply prefix (~1 min)
def test_python_split_equals_uniform_controls_per_phase(golden):
    checked, controls_differed = _trio_python(golden, max_plies=40)
    assert checked["tiles"] >= 5, f"only {checked['tiles']} tile decisions checked"
    assert checked["meeples"] >= 5, f"only {checked['meeples']} meeple decisions checked"
    # The equality above is only meaningful if the two budgets actually produce
    # different searches — otherwise a dropped override would pass silently.
    assert controls_differed >= 3, \
        "uniform-24 and uniform-8 searches barely differ; the budget knob is inert?"


def test_rust_split_equals_uniform_controls_per_phase(golden):
    """The rust trio, over the FULL game (rust is cheap): per-phase action +
    pooled-bit equality against the uniform controls, per-move sims_used
    evidence, and the latch (d) — all three latch identically and the boundary
    turn is solver-owned turn-atomically."""
    _require_rust_simsplit()
    from carcassonne_ai.rust_agent import RustFairAgent

    cfg = scenario_config()
    random.seed(golden["deck_seed"])
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()

    def mk(sims=None, **kw):
        g = Game(enable_legal_moves_cache=True)
        a = RustFairAgent(g, cfg, sims=(golden["sims"] if sims is None else sims),
                          k_dets=golden["k_dets"], seed=golden["agent_seed"], **kw)
        return a

    split = mk(sims_tile=TILE_SIMS, sims_meeple=MEEPLE_SIMS)
    uni_t = mk(sims=TILE_SIMS)
    uni_m = mk(sims=MEEPLE_SIMS)
    for a in (split, uni_t, uni_m):
        a.start_game(board)
    checked = {"tiles": 0, "meeples": 0}
    controls_differed = 0
    latch_plies = {}
    ply = 0
    while game.get_game_ended(board, 0) == 0.0:
        phase = board.state.phase
        a_split = int(split.choose_action(board))
        a_t = int(uni_t.choose_action(board))
        a_m = int(uni_m.choose_action(board))
        m_split, m_t, m_m = (x.last_move() for x in (split, uni_t, uni_m))
        assert (m_split["exact"], m_split["forced"]) == \
               (m_t["exact"], m_t["forced"]) == (m_m["exact"], m_m["forced"])
        if not (m_split["exact"] or m_split["forced"]):
            if phase == GamePhase.TILES:
                assert a_split == a_t and m_split["pooled"] == m_t["pooled"]
                assert m_split["sims_used"] == TILE_SIMS
                checked["tiles"] += 1
            else:
                assert a_split == a_m and m_split["pooled"] == m_m["pooled"]
                assert m_split["sims_used"] == MEEPLE_SIMS
                checked["meeples"] += 1
            if m_t["pooled"] != m_m["pooled"]:
                controls_differed += 1
        else:
            assert m_split["sims_used"] == 0    # no search ran
        for name, ag in (("split", split), ("uni_t", uni_t), ("uni_m", uni_m)):
            if ag.stats()["latched"] and name not in latch_plies:
                latch_plies[name] = (ply, ag.stats()["latch_k"], phase.value)
        board, _ = game.get_next_state(board, a_split)
        for ag in (split, uni_t, uni_m):
            ag.advance(a_split)
        ply += 1
    assert checked["tiles"] >= 5 and checked["meeples"] >= 5
    assert controls_differed >= 3
    # (d): all three latched at the same ply, same k, on a TILES decision.
    assert len(set(latch_plies.values())) == 1, f"latch diverged: {latch_plies}"
    assert latch_plies["split"][2] == "tiles"
    assert split.exact_moves == uni_t.exact_moves == uni_m.exact_moves > 0


def test_rust_production_shape_sims_used():
    """(b) at the PRODUCTION budget shape: k8 x (tile 1376 / meeple 344). One
    tile + one meeple decision, asserting the per-move sims_used and that the
    pooled visit mass scales with the phase budget (per-world root-child visits
    are within a few sims of the budget)."""
    _require_rust_simsplit()
    from carcassonne_ai.rust_agent import RustFairAgent

    cfg = scenario_config()
    random.seed(4)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    agent = RustFairAgent(game, cfg, sims=1376, k_dets=8, seed=3,
                          sims_tile=1376, sims_meeple=344)
    agent.start_game(board)
    seen = {"tiles": None, "meeples": None}
    while None in seen.values():
        phase = board.state.phase
        a = int(agent.choose_action(board))
        m = agent.last_move()
        if not (m["forced"] or m["exact"]) and seen[phase.value] is None:
            seen[phase.value] = m
        board, _ = game.get_next_state(board, a)
        agent.advance(a)
    k = 8
    tile, meeple = seen["tiles"], seen["meeples"]
    assert tile["sims_used"] == 1376
    assert meeple["sims_used"] == 344
    # pooled N is stored as raw f64 bits; recover the visit totals.
    import struct
    tot = lambda m: sum(struct.unpack("<d", struct.pack("<Q", n))[0]  # noqa: E731
                        for _a, n, _w in m["pooled"])
    assert k * (1376 - 4) <= tot(tile) <= k * 1376, tot(tile)
    assert k * (344 - 4) <= tot(meeple) <= k * 344, tot(meeple)


# --------------------------------------------------------------------------- #
# (c) PYTHON <-> RUST PARITY WITH THE KNOBS SET                                 #
# --------------------------------------------------------------------------- #
@pytest.mark.slow      # two full deck-distinct games, python agent is the cost
@pytest.mark.parametrize("deck_seed,agent_seed", [(20260812, 5), (777, 12)])
def test_python_rust_parity_with_knobs_set(deck_seed, agent_seed):
    """Full games stepped side by side at (tile 24 / meeple 8): identical chosen
    action at every move, identical pooled visits, identical latch counters —
    the G6 identity pattern with the split ACTIVE on both backends."""
    _require_rust_simsplit()
    from carcassonne_ai.rust_agent import RustFairAgent

    cfg = scenario_config()
    random.seed(deck_seed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    py = FairHeuristicPriorAgent(game, cfg=cfg, sims=24, k_dets=2, seed=agent_seed,
                                 sims_tile=TILE_SIMS, sims_meeple=MEEPLE_SIMS)
    rs = RustFairAgent(Game(enable_legal_moves_cache=True), cfg, sims=24, k_dets=2,
                       seed=agent_seed, sims_tile=TILE_SIMS,
                       sims_meeple=MEEPLE_SIMS)
    rs.start_game(board)
    n = 0
    while game.get_game_ended(board, 0) == 0.0:
        a_py = int(py.choose_action(board))
        a_rs = int(rs.choose_action(board))
        assert a_py == a_rs, f"move {n}: python chose {a_py}, rust chose {a_rs}"
        assert {int(k): float(v) for k, v in py.last_pooled_visits.items()} \
            == rs.last_pooled_visits, f"move {n}: pooled visits differ"
        board, _ = game.get_next_state(board, a_py)
        rs.advance(a_py)
        n += 1
    assert n > 40, f"game ended suspiciously early ({n} moves)"
    assert py.exact_moves == rs.exact_moves > 0     # (d) under the split
    assert py.latch_k == rs.latch_k
    assert py.n_timeouts == rs.n_timeouts == 0
    assert py.heur_moves == rs.heur_moves    # both count forced PIMC moves too


# --------------------------------------------------------------------------- #
# rejections + factory threading + manifest read-off                           #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("kw,msg", [
    ({"sims_tile": 0}, "sims_tile must be >= 1"),
    ({"sims_meeple": -3}, "sims_meeple must be >= 1"),
    ({"sims_tile": 16, "parallel_workers": 2}, "mutually exclusive"),
    ({"sims_meeple": 16, "intra_reuse": True}, "mutually exclusive"),
    ({"sims_tile": 16, "oracle_prior_mult": 2}, "mutually exclusive"),
])
def test_python_rejected_combinations(kw, msg):
    game = Game(enable_legal_moves_cache=True)
    with pytest.raises(ValueError, match=msg):
        FairHeuristicPriorAgent(game, HeuristicPriorConfig(), sims=4, k_dets=2, **kw)


def test_rust_rejects_bad_budgets():
    _require_rust_simsplit()
    from carcassonne_ai.rust_agent import RustFairAgent

    game = Game(enable_legal_moves_cache=True)
    with pytest.raises(ValueError, match="sims_tile must be >= 1"):
        RustFairAgent(game, scenario_config(), sims=8, k_dets=2, sims_tile=0)
    # The pyo3 layer's own guard (reached only by a direct FFI caller).
    a = RustFairAgent(game, scenario_config(), sims=8, k_dets=2)
    random.seed(1)
    a.start_game(Game(enable_legal_moves_cache=True).get_init_board())
    with pytest.raises(ValueError, match="sims_override must be >= 1"):
        a._rs.choose_action(None, 0)


def test_factory_threads_the_knob_both_backends():
    a = build_fair_champion(Game(enable_legal_moves_cache=True),
                            cfg=scenario_config(), sims=8, k_dets=2, seed=0,
                            sims_tile=6, sims_meeple=3)
    assert (a.sims_tile, a.sims_meeple) == (6, 3)
    off = build_fair_champion(Game(enable_legal_moves_cache=True),
                              cfg=scenario_config(), sims=8, k_dets=2, seed=0)
    assert (off.sims_tile, off.sims_meeple) == (None, None)
    _require_rust_simsplit()
    r = build_fair_champion(Game(enable_legal_moves_cache=True),
                            cfg=scenario_config(), sims=8, k_dets=2, seed=0,
                            backend="rust", sims_tile=6, sims_meeple=3)
    assert (r.sims_tile, r.sims_meeple) == (6, 3)
    st = r.stats()
    assert (st["sims_tile"], st["sims_meeple"]) == (6, 3)
    r_off = build_fair_champion(Game(enable_legal_moves_cache=True),
                                cfg=scenario_config(), sims=8, k_dets=2, seed=0,
                                backend="rust")
    assert "sims_tile" not in r_off.stats()      # no drift when OFF
