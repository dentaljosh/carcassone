"""C3-INTRA contracts — the flag-gated within-turn (tile -> meeple) tree carry.

  (A) FLAG           — env default OFF, per-agent kwarg override, two agents disagreeing
                       inside ONE process (what a candidate-vs-champion screen needs).
  (B) CONTINUATION   — intra_reuse.match accepts exactly the genuine same-turn
                       continuation and rejects every other shape, by DERIVING each
                       retained world's post-placement position rather than predicting it.
  (C) RE-ROOT        — NeuralMCTS.reroot_to carries a subtree's statistics and refuses
                       anything a fresh expansion would disagree with.
  (D) BIT-EXACT OFF  — with the flag off (the default) a scripted game reproduces
                       tests/golden/intra_reuse_off.json, recorded on the PRE-CHANGE
                       tree. This is the production guard.
  (E) ON CORRECTNESS — the carry fires on real turns, the meeple decision inherits the
                       TILE decision's determinizations (not fresh draws), and the budget
                       accounting is carried + sims.
  (F) FALLBACK       — the safety matrix: opponent moved, a different action was played,
                       a restore re-seated _move_idx, a forced move, the exact-endgame
                       latch, a new game. Every one discards cleanly and plays on.
  (G) LEGALITY       — full scripted games ON at tiny budgets: zero illegal actions,
                       terminates, never mutates the caller's board.
  (H) PLUMBING       — factory kwarg + manifest stamp, mutual exclusion with the oracle
                       probe, and the MEEPLE-DEDUP interaction (a deduped node carries a
                       SUBSET of the legal mask, which a naive re-root guard would reject).

Regenerate the golden with scripts/measurement_infra/gen_intra_reuse_fixture.py — but
only on a tree where the OFF path is known good: a diff there is a production
regression, not a stale fixture.
"""
from __future__ import annotations

import os

# Frozen v2.9 leaf env — set BEFORE importing engine/package modules.
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
# This module asserts the OFF default; never let an inherited env decide that for us.
os.environ["CARCASSONNE_INTRA_TURN_REUSE"] = "0"

import json  # noqa: E402
import random  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))

from carcassonne_ai import champion_factory as cf  # noqa: E402
from carcassonne_ai import intra_reuse as ir  # noqa: E402
from carcassonne_ai.fair_agent import FairHeuristicPriorAgent  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import (  # noqa: E402
    HeuristicPriorConfig,
    make_heuristic_prior_evaluator,
)
from carcassonne_ai.mcts import NeuralMCTS  # noqa: E402
from snapshot import frozen_v29_cfg  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402

GOLDEN = REPO / "tests" / "golden" / "intra_reuse_off.json"


def scenario_config() -> HeuristicPriorConfig:
    """The exact config the golden generator builds (keep in lockstep with
    scripts/measurement_infra/gen_intra_reuse_fixture.py::scenario_config)."""
    return HeuristicPriorConfig(final_select="visits", leaf_cfg=frozen_v29_cfg())


@pytest.fixture(scope="module")
def golden() -> dict:
    return json.loads(GOLDEN.read_text())


@pytest.fixture(scope="module")
def cfg() -> HeuristicPriorConfig:
    return scenario_config()


def make_agent(cfg, *, intra=True, sims=16, k_dets=2, seed=11, game=None, **kw):
    return FairHeuristicPriorAgent(
        game if game is not None else Game(enable_legal_moves_cache=True),
        cfg=cfg, sims=sims, k_dets=k_dets, seed=seed,
        exact_endgame=kw.pop("exact_endgame", False), intra_reuse=intra, **kw)


def tiles_board(deck_seed=7, plies=2):
    """A deterministic NON-FORCED TILES-phase board, `plies` scripted legal moves in.

    Non-forced matters: the opening board has exactly ONE legal tile placement, and a
    forced decision runs no search at all (so there is nothing to retain).
    """
    game = Game(enable_legal_moves_cache=True)
    random.seed(deck_seed)
    board = game.get_init_board()
    rng = random.Random(deck_seed ^ 0x5151)
    while (plies > 0 or board.state.phase != GamePhase.TILES
           or int(game.get_valid_moves(board).sum()) < 2):
        legal = np.flatnonzero(game.get_valid_moves(board))
        board, _ = game.get_next_state(board, int(rng.choice(list(legal))))
        plies -= 1
        if game.get_game_ended(board, 0) != 0.0:
            raise RuntimeError("scripted prefix ended the game")
    return game, board


def deck_of(board) -> list[str]:
    return [t.description for t in board.state.deck]


# =========================================================================== #
# (A) THE FLAG                                                                 #
# =========================================================================== #

def test_the_package_under_test_is_the_one_next_to_this_file():
    """Guard against testing a DIFFERENT checkout than the one being edited.

    The venv is editable-installed against one tree, so running this suite from a git
    worktree without PYTHONPATH pointed at that worktree silently imports the OTHER
    tree's carcassonne_ai — every assertion below would then be about code nobody
    changed, and a green run would mean nothing. Comparing against this file's own
    location is checkout-agnostic, so it holds wherever the suite is run from."""
    import carcassonne_ai
    import wingedsheep
    expected = REPO.resolve()
    for mod in (carcassonne_ai, wingedsheep):
        got = Path(mod.__file__).resolve()
        assert expected in got.parents, (
            f"{mod.__name__} imported from {got}, but this test file lives under "
            f"{expected}. Run with PYTHONPATH={expected}/src:{expected}/engine")


def test_env_default_is_off():
    assert ir.INTRA_TURN_REUSE is False
    assert ir.enabled() is False
    assert ir.ENV_VAR == "CARCASSONNE_INTRA_TURN_REUSE"


def test_resolve_none_inherits_true_false_override():
    assert ir.resolve(None) is ir.INTRA_TURN_REUSE
    assert ir.resolve(True) is True
    assert ir.resolve(False) is False


def test_set_enabled_flips_the_process_default_and_exports(monkeypatch):
    monkeypatch.setattr(ir, "INTRA_TURN_REUSE", False, raising=True)
    monkeypatch.setenv(ir.ENV_VAR, "0")
    ir.set_enabled(True)
    try:
        assert ir.enabled() is True
        assert os.environ[ir.ENV_VAR] == "1"
        assert ir.resolve(None) is True
    finally:
        ir.set_enabled(False)


def test_two_agents_disagree_in_one_process(cfg):
    """A carry-ON candidate must be able to face a carry-OFF champion in ONE worker."""
    on = make_agent(cfg, intra=True)
    off = make_agent(cfg, intra=False)
    assert on._intra_reuse is True and off._intra_reuse is False
    assert on.intra_reuse is True and off.intra_reuse is False


def test_default_kwarg_inherits_the_env_flag(cfg):
    inherit = make_agent(cfg, intra=None)
    assert inherit._intra_reuse is False      # env is OFF in this module
    assert inherit.intra_reuse is None        # the raw kwarg, for the manifest read-off


# =========================================================================== #
# (B) THE CONTINUATION CHECK                                                   #
# =========================================================================== #

def _retained_from_tile_decision(cfg, deck_seed=7):
    """Run one TILE decision with the carry ON and return everything about it."""
    game, board = tiles_board(deck_seed)
    agent = make_agent(cfg, game=game)
    action = agent.choose_action(board)
    assert agent._intra is not None, "a tile decision must retain its forest"
    return game, board, agent, action


def test_match_accepts_the_genuine_continuation(cfg):
    game, board, agent, action = _retained_from_tile_decision(cfg)
    nxt, _ = game.get_next_state(board, action)
    worlds, reason = ir.match(game, agent._intra, nxt, agent._move_idx,
                              game.string_representation(nxt))
    assert reason == "hit"
    assert len(worlds) == agent._k_dets
    # Every derived world lands on exactly the position we were handed...
    for w in worlds:
        assert game.string_representation(w) == game.string_representation(nxt)
    # ...and carries ITS OWN deck, not the real one (these are still determinizations).
    assert len({tuple(deck_of(w)) for w in worlds}) == len(worlds) or agent._k_dets == 1


def test_match_rejects_a_non_adjacent_move_index(cfg):
    game, board, agent, action = _retained_from_tile_decision(cfg)
    nxt, _ = game.get_next_state(board, action)
    key = game.string_representation(nxt)
    for bad in (agent._move_idx + 1, agent._move_idx + 5, 0):
        worlds, reason = ir.match(game, agent._intra, nxt, bad, key)
        assert worlds is None and reason == ir.R_NOT_PRIOR


def test_match_rejects_a_tiles_phase_position(cfg):
    """The next decision must be THIS turn's meeple decision, not a fresh turn."""
    game, board, agent, _action = _retained_from_tile_decision(cfg)
    worlds, reason = ir.match(game, agent._intra, board, agent._move_idx,
                              game.string_representation(board))
    assert worlds is None and reason == ir.R_PHASE


def test_match_rejects_a_different_player_to_move(cfg):
    game, board, agent, action = _retained_from_tile_decision(cfg)
    nxt, _ = game.get_next_state(board, action)
    stale = ir.RetainedTurn(
        move_idx=agent._intra.move_idx, action=agent._intra.action,
        player=1 - agent._intra.player, root_key=agent._intra.root_key,
        trees=agent._intra.trees, boards=agent._intra.boards)
    worlds, reason = ir.match(game, stale, nxt, agent._move_idx,
                              game.string_representation(nxt))
    assert worlds is None and reason == ir.R_PLAYER


def test_match_rejects_a_position_that_is_not_our_action_applied(cfg):
    """The load-bearing check: a DIFFERENT legal tile action was played instead."""
    game, board, agent, action = _retained_from_tile_decision(cfg)
    others = [int(a) for a in np.flatnonzero(game.get_valid_moves(board)) if int(a) != action]
    assert others, "need an alternative tile action for this test"
    other, _ = game.get_next_state(board, others[0])
    worlds, reason = ir.match(game, agent._intra, other, agent._move_idx,
                              game.string_representation(other))
    assert worlds is None and reason == ir.R_KEY


def test_match_rejects_none(cfg):
    game, _board = tiles_board(7)
    worlds, reason = ir.match(game, None, _board, 1, "k")
    assert worlds is None and reason == ir.R_NONE


def test_the_placement_does_not_consume_the_determinized_deck(cfg):
    """THE information-legality invariant, asserted against the engine.

    A tile placement moves TILES -> MEEPLES without drawing, so a world's unseen deck is
    bit-identical before and after. That is what makes the tile decision's
    determinizations valid samples of the info state at the meeple decision."""
    game, board, agent, action = _retained_from_tile_decision(cfg)
    nxt, _ = game.get_next_state(board, action)
    assert nxt.state.phase == GamePhase.MEEPLES
    assert deck_of(nxt) == deck_of(board)
    for w in agent._intra.boards:
        after, _ = game.get_next_state(w, action)
        assert deck_of(after) == deck_of(w)


# =========================================================================== #
# (C) THE RE-ROOT                                                              #
# =========================================================================== #

def test_reroot_to_carries_visits_and_prunes(cfg):
    game, board = tiles_board(7)
    m = NeuralMCTS(game=game, evaluator=make_heuristic_prior_evaluator(game, cfg),
                   simulations=48, c_puct=cfg.c_puct, seed=3)
    m.search(board)
    n_before = len(m._nodes)
    # pick the most-visited root child = the position a played action leads to
    root = m._nodes[game.string_representation(board)]
    best = max(root.children.items(), key=lambda kv: kv[1].N)
    child_board, _ = game.get_next_state(board, best[0])
    carried = m.reroot_to(child_board)
    assert carried == best[1].N > 0
    assert len(m._nodes) <= n_before
    assert game.string_representation(child_board) in m._nodes
    assert game.string_representation(board) not in m._nodes  # old root dropped


def test_reroot_to_returns_zero_and_wipes_on_an_unknown_position(cfg):
    game, board = tiles_board(7)
    other_game, other_board = tiles_board(9)
    m = NeuralMCTS(game=game, evaluator=make_heuristic_prior_evaluator(game, cfg),
                   simulations=16, c_puct=cfg.c_puct, seed=3)
    m.search(board)
    assert m._nodes
    assert m.reroot_to(other_board) == 0
    assert not m._nodes          # wiped -> the caller's next search is clean anyway


def test_reroot_to_rejects_an_action_this_world_never_explored(cfg):
    """THE realistic in-game rejection: pooled-Q can pick an action that some
    determinization never descended into, so that world has no subtree to carry.
    (A created child always has N>=1 — creation happens on selection, which is followed
    by a backup — so "no statistics to carry" shows up as an ABSENT node, not a
    zero-visit one.)"""
    game, board = tiles_board(7)
    m = NeuralMCTS(game=game, evaluator=make_heuristic_prior_evaluator(game, cfg),
                   simulations=2, c_puct=cfg.c_puct, seed=3)
    m.search(board)
    root = m._nodes[game.string_representation(board)]
    unexplored = [int(a) for a in np.flatnonzero(game.get_valid_moves(board))
                  if int(a) not in root.children]
    assert unexplored, "need an unexplored root action at simulations=2"
    child_board, _ = game.get_next_state(board, unexplored[0])
    assert m.reroot_to(child_board) == 0
    assert not m._nodes          # wiped -> the caller searches fresh, safely


def test_expected_valid_actions_is_the_legal_mask_when_dedup_is_off(cfg):
    game, board = tiles_board(7)
    m = NeuralMCTS(game=game, evaluator=make_heuristic_prior_evaluator(game, cfg),
                   simulations=1, c_puct=cfg.c_puct, seed=3, meeple_dedup=False)
    assert m.expected_valid_actions(board) == {
        int(a) for a in np.flatnonzero(game.get_valid_moves(board))}


# =========================================================================== #
# (D) BIT-EXACT OFF — the production guard                                     #
# =========================================================================== #

def test_bit_exact_off_matches_pre_change_fixture(golden, cfg):
    """Replay the recorded scenario with the flag OFF: identical actions, identical
    pooled visit distributions, identical final position. Any diff is a production
    regression, not a stale fixture."""
    game = Game(enable_legal_moves_cache=True)
    random.seed(golden["deck_seed"])
    board = game.get_init_board()
    agent = FairHeuristicPriorAgent(game, cfg=cfg, sims=golden["sims"],
                                    k_dets=golden["k_dets"], seed=golden["agent_seed"],
                                    exact_endgame=False)
    actions: list[int] = []
    per_ply: list[dict] = []
    for _ply in range(golden["plies_requested"]):
        if game.get_game_ended(board, board.state.current_player) != 0.0:
            break
        phase = board.state.phase.name
        a = int(agent.choose_action(board))
        pooled = agent.last_pooled_visits or {}
        per_ply.append({
            "ply": len(actions), "phase": phase, "action": a,
            "pooled_visits": {str(int(k)): float(v) for k, v in sorted(pooled.items())},
        })
        actions.append(a)
        board, _ = game.get_next_state(board, a)

    assert actions == golden["actions"]
    assert per_ply == golden["per_ply"]
    assert game.string_representation(board) == golden["final_key"]
    assert agent.heur_moves == golden["heur_moves"]


def test_off_telemetry_is_completely_inert(golden, cfg):
    game, board = tiles_board(7)
    agent = make_agent(cfg, intra=False, game=game)
    agent.choose_action(board)
    assert agent._intra is None
    assert agent.intra_reuse_hits == 0
    assert agent.intra_turns_retained == 0
    assert agent.intra_carried_visits_total == 0
    assert agent.intra_reuse_discards == {}
    assert agent.last_intra_carried_visits is None
    assert agent.last_intra_root_visits is None
    assert agent.last_det_boards is None


# =========================================================================== #
# (E) ON CORRECTNESS                                                           #
# =========================================================================== #

def test_reuse_fires_on_a_real_turn_with_carried_visits(cfg):
    game, board, agent, action = _retained_from_tile_decision(cfg)
    assert agent.intra_turns_retained == 1
    assert agent.last_intra_carried_visits is None      # the TILE decision carried nothing
    nxt, _ = game.get_next_state(board, action)
    assert nxt.state.phase == GamePhase.MEEPLES
    move = agent.choose_action(nxt)

    assert agent.intra_reuse_hits == 1
    assert agent.intra_reuse_discards == {}
    carried = agent.last_intra_carried_visits
    assert carried is not None and len(carried) == agent._k_dets
    assert all(c > 0 for c in carried), f"every world must carry visits, got {carried}"
    assert agent.intra_carried_visits_total == sum(carried)
    assert game.get_valid_moves(nxt)[move]
    assert agent._intra is None          # consumed; a meeple decision retains nothing


def test_the_meeple_decision_keeps_the_tile_decisions_determinizations(cfg):
    """The carry is of the WORLDS as much as the trees: no redraw, same decks."""
    game, board, agent, action = _retained_from_tile_decision(cfg)
    tile_decks = [deck_of(b) for b in agent.last_det_boards]
    assert len(tile_decks) == agent._k_dets
    nxt, _ = game.get_next_state(board, action)
    agent.choose_action(nxt)
    meeple_decks = [deck_of(b) for b in agent.last_det_boards]
    assert meeple_decks == tile_decks, "the meeple call redrew its determinizations"

    # ...and this is a real constraint: a carry-OFF agent at the same position draws
    # DIFFERENT decks (its per-move seed moved on), which is what we are avoiding.
    off = make_agent(cfg, intra=False, game=game)
    off._move_idx = agent._move_idx - 1
    off._intra_reuse = True          # telemetry only; nothing is retained to reuse
    off.choose_action(nxt)
    assert [deck_of(b) for b in off.last_det_boards] != tile_decks


def test_budget_accounting_is_carried_plus_sims(cfg):
    """ON, the meeple decision runs a FULL `sims` per world ON TOP of the carry — the
    strength-at-equal-nominal-budget framing the screen's read-out depends on."""
    game, board, agent, action = _retained_from_tile_decision(cfg)
    nxt, _ = game.get_next_state(board, action)
    agent.choose_action(nxt)
    carried = agent.last_intra_carried_visits
    after = agent.last_intra_root_visits
    assert after is not None and len(after) == len(carried) == agent._k_dets
    for c, a in zip(carried, after):
        assert a == c + agent._sims, f"expected {c}+{agent._sims} root visits, got {a}"


def test_carry_never_changes_the_move_index_bookkeeping(cfg):
    """Restore compatibility: _move_idx must advance exactly as it does OFF."""
    game, board = tiles_board(7)
    on, off = make_agent(cfg, intra=True, game=game), make_agent(cfg, intra=False)
    for agent in (on, off):
        assert agent._move_idx == 0
    a_on = on.choose_action(board)
    off.choose_action(board)
    assert on._move_idx == off._move_idx == 1
    nxt, _ = game.get_next_state(board, a_on)
    on.choose_action(nxt)
    off.choose_action(nxt)
    assert on._move_idx == off._move_idx == 2
    assert on.det_seed_base(5) == off.det_seed_base(5)


# =========================================================================== #
# (F) THE FALLBACK MATRIX — never a wrong reuse, always a safe fresh search     #
# =========================================================================== #

def test_fallback_a_different_action_was_played(cfg):
    game, board, agent, action = _retained_from_tile_decision(cfg)
    others = [int(a) for a in np.flatnonzero(game.get_valid_moves(board)) if int(a) != action]
    assert others
    other, _ = game.get_next_state(board, others[0])
    move = agent.choose_action(other)
    assert agent.intra_reuse_hits == 0
    assert agent.intra_reuse_discards == {ir.R_KEY: 1}
    assert agent.last_intra_carried_visits is None
    assert game.get_valid_moves(other)[move]


def test_fallback_opponent_moved_between(cfg):
    """Tile decision -> the turn is completed by someone else -> the opponent plays ->
    the agent is asked again. Its next decision is a fresh TILES one: no carry."""
    game, board, agent, action = _retained_from_tile_decision(cfg)
    rng = random.Random(99)
    b, _ = game.get_next_state(board, action)
    # finish the turn + let the opponent play, without asking the agent
    for _ in range(6):
        if b.state.phase == GamePhase.TILES and b.state.current_player == board.state.current_player:
            break
        legal = np.flatnonzero(game.get_valid_moves(b))
        b, _ = game.get_next_state(b, int(rng.choice(list(legal))))
    move = agent.choose_action(b)
    assert agent.intra_reuse_hits == 0
    assert sum(agent.intra_reuse_discards.values()) == 1
    assert set(agent.intra_reuse_discards) <= {ir.R_PHASE, ir.R_NOT_PRIOR, ir.R_KEY}
    assert game.get_valid_moves(b)[move]


def test_fallback_restore_reseated_move_idx(cfg):
    """android_bridge.restore_game() re-seats _move_idx (and _latched) on the agent."""
    game, board, agent, action = _retained_from_tile_decision(cfg)
    nxt, _ = game.get_next_state(board, action)
    agent._move_idx = 0                       # what restore_game does
    move = agent.choose_action(nxt)
    assert agent.intra_reuse_hits == 0
    assert agent.intra_reuse_discards == {ir.R_NOT_PRIOR: 1}
    assert game.get_valid_moves(nxt)[move]


def test_discard_intra_carry_is_an_explicit_public_hook(cfg):
    game, board, agent, action = _retained_from_tile_decision(cfg)
    assert agent._intra is not None
    agent.discard_intra_carry()
    assert agent._intra is None
    nxt, _ = game.get_next_state(board, action)
    move = agent.choose_action(nxt)
    assert agent.intra_reuse_hits == 0
    assert game.get_valid_moves(nxt)[move]


def test_fallback_new_game(cfg):
    game, board, agent, _action = _retained_from_tile_decision(cfg)
    fresh_game, fresh_board = tiles_board(21)
    agent._game = fresh_game                  # a seat reused across games
    move = agent.choose_action(fresh_board)
    assert agent.intra_reuse_hits == 0
    assert agent.intra_reuse_discards == {ir.R_PHASE: 1}
    assert fresh_game.get_valid_moves(fresh_board)[move]


def test_fallback_forced_move(cfg, monkeypatch):
    """A decision with ONE legal action runs no search, so nothing can be carried into
    it. (Forced tile-phase passes and single-option meeple phases both land here; the
    mask is forced directly so the test does not depend on finding such a seed.)"""
    game, board, agent, action = _retained_from_tile_decision(cfg)
    nxt, _ = game.get_next_state(board, action)
    only = int(np.flatnonzero(game.get_valid_moves(nxt))[0])
    forced = np.zeros_like(game.get_valid_moves(nxt))
    forced[only] = True
    monkeypatch.setattr(game, "get_valid_moves", lambda b: forced)
    move = agent.choose_action(nxt)
    assert move == only
    assert agent.intra_reuse_hits == 0
    assert agent.intra_reuse_discards == {ir.R_FORCED: 1}
    assert agent.last_pooled_visits == {only: 1.0}


def test_fallback_exact_endgame_latch(cfg):
    """When the solver owns a decision no search runs, so a retained forest is dropped.

    Reachable in production only via a BudgetExceeded PIMC fallback on the tile half
    followed by a successful solve on the meeple half; asserted here by latching
    directly, which is the same state the agent would be in."""
    game, board, agent, action = _retained_from_tile_decision(cfg)
    nxt, _ = game.get_next_state(board, action)
    agent._exact_endgame = True
    agent._latched = True
    solved = {"n": 0}

    def fake_exact(_board):
        solved["n"] += 1
        return int(np.flatnonzero(game.get_valid_moves(_board))[0])

    agent._exact_move = fake_exact
    move = agent.choose_action(nxt)
    assert solved["n"] == 1
    assert agent._intra is None
    assert agent.intra_reuse_hits == 0
    assert agent.intra_reuse_discards == {ir.R_LATCHED: 1}
    assert game.get_valid_moves(nxt)[move]


def test_a_rejected_reroot_falls_back_all_or_nothing(cfg, monkeypatch):
    """If ANY world's retained node fails the search-side guard the WHOLE forest is
    dropped — a partially-carried pool would mix worlds searched to different depths
    into one pooled-Q."""
    game, board, agent, action = _retained_from_tile_decision(cfg)
    nxt, _ = game.get_next_state(board, action)
    victim = agent._intra.trees[-1]
    real = NeuralMCTS.reroot_to
    monkeypatch.setattr(NeuralMCTS, "reroot_to",
                        lambda self, b: 0 if self is victim else real(self, b))
    move = agent.choose_action(nxt)
    assert agent.intra_reuse_hits == 0
    assert agent.intra_reuse_discards == {ir.R_REROOT: 1}
    assert agent.last_intra_carried_visits is None
    assert game.get_valid_moves(nxt)[move]


# =========================================================================== #
# (G) LEGALITY — the whole point                                               #
# =========================================================================== #

@pytest.mark.parametrize("deck_seed", [3, 2024])
def test_full_game_on_is_legal_and_terminates(cfg, deck_seed):
    game = Game(enable_legal_moves_cache=True)
    random.seed(deck_seed)
    board = game.get_init_board()
    a0 = make_agent(cfg, intra=True, sims=8, k_dets=2, seed=1,
                    game=Game(enable_legal_moves_cache=True), exact_endgame=True)
    a1 = make_agent(cfg, intra=True, sims=8, k_dets=2, seed=2,
                    game=Game(enable_legal_moves_cache=True), exact_endgame=True)
    moves = 0
    while game.get_game_ended(board, 0) == 0.0:
        agent = a0 if board.state.current_player == 0 else a1
        act = agent.choose_action(board)
        assert game.get_valid_moves(board)[act], f"illegal action {act} at move {moves}"
        board, _ = game.get_next_state(board, act)
        moves += 1
        assert moves < 400, "game did not terminate"
    assert game.get_game_ended(board, 0) != 0.0
    assert (a0.intra_reuse_hits + a1.intra_reuse_hits) > 0, "the carry never fired"
    assert a0.n_timeouts == 0 and a1.n_timeouts == 0
    for agent in (a0, a1):
        # every retained forest is either used or explicitly discarded — none leak
        assert agent.intra_turns_retained == (
            agent.intra_reuse_hits + sum(agent.intra_reuse_discards.values())
            + (1 if agent._intra is not None else 0))


def test_choose_action_never_mutates_the_callers_board_when_on(cfg):
    import pickle
    game, board = tiles_board(7)
    agent = make_agent(cfg, game=game)
    before = pickle.dumps(board.state)
    a = agent.choose_action(board)
    assert pickle.dumps(board.state) == before
    nxt, _ = game.get_next_state(board, a)
    before_n = pickle.dumps(nxt.state)
    agent.choose_action(nxt)
    assert pickle.dumps(nxt.state) == before_n


# =========================================================================== #
# (H) PLUMBING                                                                 #
# =========================================================================== #

def test_oracle_prior_and_intra_reuse_are_mutually_exclusive(cfg):
    with pytest.raises(ValueError, match="mutually exclusive"):
        make_agent(cfg, intra=True, oracle_prior_mult=2)
    # ...and each alone is fine
    make_agent(cfg, intra=True)
    make_agent(cfg, intra=False, oracle_prior_mult=2)


def test_factory_forwards_the_kwarg_and_rejects_clairvoyant_mode():
    agent = cf.build_fair_champion(Game(enable_legal_moves_cache=True), intra_reuse=True)
    assert agent._intra_reuse is True
    with pytest.raises(ValueError, match="FAIR-mode"):
        cf.make_production_champion("clairvoyant", seed=1, sims=8, verify=False,
                                    intra_reuse=True)


def test_build_fair_champion_default_is_untouched():
    """_UNSET means the constructor is called with the pre-feature argument list."""
    agent = cf.build_fair_champion(Game(enable_legal_moves_cache=True))
    assert agent.intra_reuse is None
    assert agent._intra_reuse is False


@pytest.mark.parametrize("dedup", [False, True])
def test_reuse_still_fires_with_meeple_dedup(cfg, dedup):
    """A deduped node's valid_actions is a SUBSET of the legal mask — a re-root guard
    that compared against the raw mask would reject every carry when dedup is on."""
    game, board = tiles_board(7)
    agent = make_agent(cfg, game=game, meeple_dedup=dedup)
    action = agent.choose_action(board)
    nxt, _ = game.get_next_state(board, action)
    agent.choose_action(nxt)
    assert agent.intra_reuse_hits == 1, f"carry did not fire with meeple_dedup={dedup}"
    assert all(c > 0 for c in agent.last_intra_carried_visits)
