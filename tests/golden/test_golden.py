"""STANDING GOLDEN CORRECTNESS GATE (Phase 0.4).

Asserts the current code reproduces the frozen fixture (tests/golden/golden_fixture.json)
AND a set of structural invariants. Any drift in the engine final score, the flat base
leaf, the v2.7/v2.8/v2.9 virtual_score_v2 leaves, the K<=2 exact solver, the legal-move
masks, the action-space encode/decode/rotation bijection, flat-vs-object bit-exactness,
MCTS visit accounting, replay reconstruction, or the fair-mode hidden-information contract
trips this gate. Regenerate deliberately with `tests/golden/gen_golden.py` when a change is
intended.

Invariants wired:
  1. per-position fixture reproduction (leaf/base/mask/solver/provenance)
  2. value antisymmetry get_game_ended(b,0) == -get_game_ended(b,1) incl. a draw case
  3. encode(decode(idx)) round-trip over legal tile- AND meeple-phase indices
  4. action_rotation_perm(W) is a bijection; rotate_action^4 == identity
  5. flat-vs-object leaf bit-exactness under CANONICAL_BONUS_SUM
  6. HeuristicMCTS visit accounting: root.N == deduped child-N sum == simulations
  7. replay_actions reproduces terminal scores bit-exactly
  8. fair-mode: ZERO clairvoyant solves; latched marginalized solve is deck-permute-invariant
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _golden_common as C  # noqa: E402  (sets frozen env + sys.path BEFORE carcassonne)

import copy  # noqa: E402
import json  # noqa: E402
import random  # noqa: E402

import pytest  # noqa: E402

from carcassonne_ai import action_space as A  # noqa: E402
from carcassonne_ai.fair_agent import FairHeuristicMCTSAgent  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.mcts import HeuristicMCTS  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402
import endgame_solver as S  # noqa: E402

np = C.np

FIX = json.loads(C.FIXTURE.read_text())
META = FIX["meta"]
POSITIONS = FIX["positions"]
GAMES = FIX["games"]
PERM = FIX["deck_perm_invariance"]

PID = [p["id"] for p in POSITIONS]
POS_BY_ID = {p["id"]: p for p in POSITIONS}


def _replay_pos(pos):
    return C.replay_actions(pos["seed"], GAMES[str(pos["seed"])]["actions"], pos["ply"])


# ---------------------------------------------------------------- fixture sanity
def test_fixture_present_and_configs_frozen():
    assert len(POSITIONS) >= 40, f"only {len(POSITIONS)} golden positions"
    assert len(GAMES) >= 8
    # config-hash drift gate: the three leaf configs must hash to the frozen values.
    for name, cfg in C.CFGS.items():
        assert C.cfg_hash(cfg) == META["cfg_hashes"][name], f"leaf cfg {name} drifted"
    # the v2.9 leaf equals the current runtime config used to freeze the fixture
    assert META["current_v29_hash"] == C.cfg_hash(C.CFG_V29)


def test_configs_are_discriminated_and_v29_is_production():
    """The suite must PIN each leaf config distinctly: without positions where all three
    disagree, a regression in the v2.8 meeple-liquidity term or the v2.9 meeple curve
    wouldn't change any frozen value (most random-play positions have symmetric meeple
    counts, so the liquidity DIFFERENTIAL cancels and v27==v28==v29)."""
    disc = [p for p in POSITIONS if p["kind"] == "discriminating"]
    assert len(disc) >= 3, f"only {len(disc)} discriminating positions — gate can't catch v2.8/v2.9 drift"
    for p in disc:
        v27, v28, v29 = p["vs"]["v27"], p["vs"]["v28"], p["vs"]["v29"]
        assert v27 != v28 and v28 != v29, f"pid={p['id']} labelled discriminating but configs coincide"
    # Recorded at generation time (env controlled): golden CFG_V29 == production DEFAULT_CONFIG.
    # NB: the governance FROZEN_V29_HASH (snapshot.py) is STALE post-v2.10-bag_close — see
    # META['governance_hash_note']; this check is the robust production-leaf identity gate.
    assert META.get("v29_equals_default_config") is True, \
        "golden CFG_V29 != production DEFAULT_CONFIG"


# ------------------------------------------------ (1) per-position reproduction
@pytest.mark.parametrize("pid", PID)
def test_position_reproduces(pid):
    pos = POS_BY_ID[pid]
    game, board = _replay_pos(pos)
    st = board.state
    assert st.phase.value == pos["phase"]
    assert int(st.current_player) == pos["current_player"]

    # flat base leaf (pure int) + antisymmetry
    fbs = [int(C.flat_base_score(st, 0)), int(C.flat_base_score(st, 1))]
    assert fbs == pos["flat_base_score"]
    assert fbs[0] == -fbs[1]

    # v2.7 / v2.8 / v2.9 leaves (object path, canonical)
    for name, cfg in C.CFGS.items():
        got = [C.leaf_canon(st, 0, cfg), C.leaf_canon(st, 1, cfg)]
        assert got == pos["vs"][name], f"{name} leaf drift at pid={pid}"

    # legal-move mask (hash + count + explicit sample + window/action size)
    mi = C.mask_info(game, board)
    for key in ("window_size", "action_size", "legal_count", "legal_mask_sha256", "legal_sample"):
        assert mi[key] == pos[key], f"{key} drift at pid={pid}"

    # K<=2 exact solver value + optimal set
    if pos["solver"] is not None:
        r = S.solve(game, board, mode="marginalized", budget=C.SOLVER_BUDGET, alphabeta=False)
        assert abs(float(r.value) - pos["solver"]["value"]) < 1e-9
        assert sorted(int(a) for a in r.optimal_actions) == pos["solver"]["optimal_actions"]


# --------------------------------------- (5) flat-vs-object leaf bit-exactness
@pytest.mark.parametrize("pid", PID)
def test_flat_equals_object_leaf(pid):
    pos = POS_BY_ID[pid]
    _game, board = _replay_pos(pos)
    st = board.state
    for name, cfg in C.CFGS.items():
        assert C.flat_eq_object(st, cfg), f"flat!=object for {name} at pid={pid}"


# --------------------------- (7) replay + (2)/terminal engine-final reproduction
@pytest.mark.parametrize("seed", sorted(GAMES, key=int))
def test_replay_terminal_reproduces(seed):
    g = GAMES[seed]
    _game, board = C.replay_actions(int(seed), g["actions"], g["n_plies"])
    st = board.state
    assert [int(st.scores[0]), int(st.scores[1])] == g["terminal_scores"]
    assert int(C.flat_base_score(st, 0)) == g["engine_final_diff_p0"]


# --------------------------------------------------- (2) value antisymmetry
def test_value_antisymmetry_incl_draw():
    checked_terminal = 0
    draw_checked = False
    for seed, g in GAMES.items():
        game, board = C.replay_actions(int(seed), g["actions"], g["n_plies"])
        assert board.state.is_terminated()
        v0 = game.get_game_ended(board, 0)
        v1 = game.get_game_ended(board, 1)
        assert abs(v0 + v1) < 1e-12, (seed, v0, v1)
        checked_terminal += 1
        # forced draw: equal scores must hit the +-1e-6 antisymmetric epsilon branch
        if not draw_checked:
            b2 = copy.deepcopy(board)
            b2.state.scores[0] = b2.state.scores[1] = 7
            assert game.get_game_ended(b2, 0) == 1e-6
            assert game.get_game_ended(b2, 1) == -1e-6
            assert game.get_game_ended(b2, 0) == -game.get_game_ended(b2, 1)
            draw_checked = True
    assert checked_terminal >= 8 and draw_checked


# ------------------------------ (3) encode/decode round-trip (tiles + meeples)
def _roundtrip_legal(game, board):
    st = board.state
    off = board.offset
    phase = st.phase.value
    last = st.last_tile_action.coordinate if st.last_tile_action is not None else None
    mask = np.asarray(game.get_valid_moves(board), dtype=bool)
    n = 0
    for idx in np.flatnonzero(mask).tolist():
        idx = int(idx)
        act = A.decode(idx, off=off, phase=phase, next_tile=st.next_tile, last_tile_coord=last)
        assert A.encode(act, off, phase) == idx, f"roundtrip fail idx={idx} phase={phase}"
        n += 1
    return n


@pytest.mark.parametrize("pid", PID)
def test_encode_decode_roundtrip(pid):
    pos = POS_BY_ID[pid]
    game, board = _replay_pos(pos)
    tiles_checked = _roundtrip_legal(game, board)   # golden positions are TILES phase
    assert tiles_checked > 0
    # step one legal tile action -> MEEPLES phase -> round-trip meeple indices too
    first_legal = int(np.flatnonzero(game.get_valid_moves(board))[0])
    nb, _ = game.get_next_state(board, first_legal)
    if nb.state.phase == GamePhase.MEEPLES:
        assert _roundtrip_legal(game, nb) > 0


# ------------------------------------- (4) rotation bijection + 4x identity
def test_action_rotation_bijection_and_involution():
    wsizes = sorted({p["window_size"] for p in POSITIONS})
    assert wsizes
    for w in wsizes:
        perm = np.asarray(A.action_rotation_perm(w))
        asz = A.action_size(w)
        assert perm.shape[0] == asz
        assert sorted(perm.tolist()) == list(range(asz)), f"perm not a bijection for W={w}"
    # rotate_action applied 4x is the identity, over the full action space of one W
    w = wsizes[0]
    for a in range(A.action_size(w)):
        r = a
        for _ in range(4):
            r = A.rotate_action(r, w)
        assert r == a, f"rotate^4 != id at a={a} W={w}"


# --------------------------- (6) HeuristicMCTS visit accounting (dedup identity)
@pytest.mark.parametrize("pid", [p["id"] for p in POSITIONS if p["k"] in (14, 26)][:3])
def test_mcts_visit_accounting(pid):
    pos = POS_BY_ID[pid]
    game, board = _replay_pos(pos)
    sims = 120
    m = HeuristicMCTS(game=game, simulations=sims, c=3.0, seed=1234,
                      heur_leaf="v2_7", leaf_cfg=C.CFG_V29)
    m.search(board)
    root = m._nodes[game.string_representation(board)]
    assert not root.is_terminal
    # root is on every simulation's backprop path -> its N equals the sim budget
    assert root.N == sims
    # Dedup transposition-aliased children by node id (symmetric-tile rotations point
    # to ONE child node): sum of deduped direct-child N == root.N EXACTLY. Depth-1
    # children can't be revisited deeper (monotone tile progress), so no over-count.
    seen: set[int] = set()
    deduped_sum = 0
    naive_sum = 0
    for a in sorted(root.children):
        ch = root.children[a]
        naive_sum += ch.N
        if id(ch) in seen:
            continue
        seen.add(id(ch))
        deduped_sum += ch.N
    assert deduped_sum == root.N, (deduped_sum, root.N)
    assert naive_sum >= deduped_sum   # aliasing (if any symmetric tiles) inflates the naive sum


# ------------------------- (8a) fair mode makes ZERO clairvoyant solves --------
def _play_fair_from(pos, sims=80, k_dets=3):
    """Two FairHeuristicMCTSAgents play the position out to terminal."""
    game, board = _replay_pos(pos)
    agents = {
        s: FairHeuristicMCTSAgent(Game(enable_legal_moves_cache=True, include_farm_scalars=True),
                                  sims=sims, k_dets=k_dets, c_puct=3.0, seed=100 + s,
                                  heur_leaf="v2_7", leaf_cfg=C.CFG_V29, exact_endgame=True,
                                  exact_budget=C.SOLVER_BUDGET)
        for s in (0, 1)
    }
    guard = 0
    while game.get_game_ended(board, 0) == 0.0:
        guard += 1
        assert guard < 200
        cur = int(board.state.current_player)
        a = agents[cur].choose_action(board)
        board, _ = game.get_next_state(board, int(a))
    return agents


def test_fair_zero_clairvoyant_solves():
    recorded: list[dict] = []
    orig = S.solve

    def _rec(game, board, mode="marginalized", budget=4_000_000, alphabeta=False):
        recorded.append({"mode": mode, "alphabeta": bool(alphabeta)})
        return orig(game, board, mode=mode, budget=budget, alphabeta=alphabeta)

    k6 = [p for p in POSITIONS if p["k"] == 6][:1]   # one short fair game (both seats fair)
    assert k6, "need a k=6 start position for the fair-game test"
    S.solve = _rec
    try:
        total_exact = 0
        for pos in k6:
            agents = _play_fair_from(pos)
            total_exact += agents[0].exact_moves + agents[1].exact_moves
    finally:
        S.solve = orig
    # (a) every fair-mode solve must be honest marginalized, never clairvoyant/alpha-beta
    assert recorded, "fair game never reached the solver (no latched k<=2 decision)"
    assert all(c["mode"] == "marginalized" for c in recorded), "clairvoyant solve leaked!"
    assert all(c["alphabeta"] is False for c in recorded), "alpha-beta pruning leaked!"
    assert total_exact >= 1


# ------- (8b) latched marginalized solve is invariant under deck permutation ---
@pytest.mark.parametrize("i", range(len(PERM)))
def test_fair_latched_solve_permute_reproduces(i):
    """K<=2 latch-band marginalized solve, re-solved on a deck-permuted copy, must match
    the frozen value + optimal set. (At k<=2 the unseen deck holds <=1 tile so the permute
    is a structural no-op; this is a solver-REPRODUCTION regression gate. The genuine
    multi-tile order-independence is test_marginalized_key_is_deck_order_invariant.)"""
    e = PERM[i]
    game, board = C.replay_actions(e["seed"], e["actions"], e["ply"])
    b2 = copy.deepcopy(board)
    random.Random(e["perm_seed"]).shuffle(b2.state.deck)   # multiset + next_tile preserved
    b2._str_repr_cache = None
    r = S.solve(game, b2, mode="marginalized", budget=C.SOLVER_BUDGET, alphabeta=False)
    assert abs(float(r.value) - e["value"]) < 1e-9, "marginalized value drift/leak under permute"
    assert sorted(int(a) for a in r.optimal_actions) == e["optimal_actions"], \
        "optimal set changed under deck permute (hidden-info leak?)"


def test_marginalized_key_is_deck_order_invariant():
    """Direct, INSTANT test of the hidden-info order-independence MECHANISM at a genuine
    multi-tile deck: endgame_solver._Solver._key sorts the bag multiset in marginalized
    mode (deck-order-independent) but preserves order in clairvoyant mode. A deep k>=3
    marginalized solve (the only way to get a >=2-tile *latched* deck) would churn for
    minutes, so we test the mechanism itself on a midgame golden position's full deck."""
    mid = next(p for p in POSITIONS if p["k"] >= 14)
    game, board = _replay_pos(mid)
    assert len(board.state.deck) >= 2
    b2 = copy.deepcopy(board)
    b2.state.deck = list(reversed(b2.state.deck))          # guaranteed reorder if >=2 distinct
    b2._str_repr_cache = None
    marg = S._Solver(game, "marginalized", 1)
    clair = S._Solver(game, "clairvoyant", 1)
    assert marg._key(board) == marg._key(b2), "marginalized _key changed under deck permute (leak!)"
    raw_changed = ([t.description for t in board.state.deck]
                   != [t.description for t in b2.state.deck])
    if raw_changed:
        assert clair._key(board) != clair._key(b2), \
            "clairvoyant _key must reflect deck order (else the marginalized sort is vacuous)"
