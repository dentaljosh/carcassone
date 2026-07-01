"""GATE ZERO of Probe B (docs/PROBE_B_FAIR_INFO_SPEC.md §3) — the reframed
fair-information gate.

NOT "add deck order to the transposition key" (that is the anti-pattern §3, and
the key already excludes deck order — verified). Instead this file:

  3a. V5 no-leak unit test — LOCK the existing property: two board states that
      differ ONLY in unrevealed deck ORDER must hash-identical under
      `string_representation`; a state that differs in something that SHOULD
      change the key (placed a tile / different next_tile) must hash-differently.

  3b. Flywheel-regime leak test — the REAL gate. CL-022's clairvoyance harness is
      sound because it `clear()`s the tree between each of its K determinizations.
      The flywheel-gen path is DIFFERENT: a PERSISTENT tree, K=1 `fair_chance`
      search per move, NO `clear()` between moves. Under a sparse (deck-order-free)
      transposition key, an interior node created under move-t's reshuffled future
      survives in `_nodes` and is REUSED at move t+1 after a fresh reshuffle —
      backing up values conditioned on move-t's now-counterfactual future. This
      test instruments that reuse directly and quantifies the divergence vs a
      clear()-per-move control.

Mechanism test, not a strength test — sims are deliberately low. A deterministic
stub evaluator drives the search (the leak is purely structural — transposition
reuse of interior nodes across determinizations — and is net-independent). A
real-checkpoint variant is included but skipped when the checkpoint is absent.
"""
from __future__ import annotations

import copy
import random as _random
from pathlib import Path

import numpy as np
import pytest

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import NeuralMCTS

REPO = Path(__file__).resolve().parents[1]
CKPT = REPO / "checkpoints" / "warmstart_canonical.pt"


@pytest.fixture(autouse=True)
def _preserve_global_random():
    """get_init_board() shuffles the deck via the engine's GLOBAL `random`.
    Save/restore so this module has zero net effect on global random (keeps the
    suite order-independent)."""
    st = _random.getstate()
    try:
        yield
    finally:
        _random.setstate(st)


# --------------------------------------------------------------------------- #
# A deterministic, non-uniform stub evaluator.
#
# It must be non-uniform so PUCT actually PREFERS some children and descends into
# interior nodes (creating the transpositions whose reuse is the leak). It is a
# pure function of the board's public state key, so it is reproducible and has NO
# knowledge of the deck order — exactly like the learned net. Value depends only
# on the current player's score margin (deck-order-blind), so any cross-move node
# reuse we detect is structural, not a stub artifact.
# --------------------------------------------------------------------------- #
_STUB_GAME = Game(enable_legal_moves_cache=True)


def _stub_evaluator(board):
    n = int(_STUB_GAME.get_action_size())
    mask = _STUB_GAME.get_valid_moves(board)
    legal = np.flatnonzero(mask)
    priors = np.zeros(n, dtype=np.float32)
    if len(legal) == 0:
        return priors, 0.0
    # Deterministic non-uniform priors keyed on action index (stable hash).
    raw = np.array([((int(a) * 2654435761) % 1000) + 1 for a in legal], dtype=np.float64)
    raw /= raw.sum()
    priors[legal] = raw.astype(np.float32)
    # Value: current player's score margin, squashed. Deck-order-blind.
    s = board.state
    margin = float(s.scores[s.current_player] - s.scores[1 - s.current_player])
    value = float(np.tanh(margin / 20.0))
    return priors, value


def _fresh_game():
    return Game(enable_legal_moves_cache=True)


def _mid_game_board(seed: int, plies: int):
    """Play `plies` greedy-ish (first-legal) moves from a seeded init board to get
    a real mid-game board with a non-trivial unseen deck."""
    _random.seed(seed)
    g = _fresh_game()
    board = g.get_init_board()
    for _ in range(plies):
        if g.get_game_ended(board, board.state.current_player) != 0.0:
            break
        mask = g.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if len(legal) == 0:
            break
        # deterministic pick, not first-index (avoid a degenerate corridor)
        a = int(legal[(seed + len(board.state.placed_coords)) % len(legal)])
        board, _ = g.get_next_state(board, a)
    return g, board


# =========================================================================== #
# 3a. V5 NO-LEAK unit test — lock the property (positive) + negative control.
# =========================================================================== #
def test_3a_v5_deck_order_not_in_key_positive():
    """Two states identical except in unrevealed deck ORDER hash-identically."""
    g, board = _mid_game_board(seed=11, plies=14)
    assert len(board.state.deck) >= 5, "need a real bag to shuffle"

    b1 = copy.deepcopy(board)
    b2 = copy.deepcopy(board)
    b1._str_repr_cache = None
    b2._str_repr_cache = None

    # Shuffle ONLY the deck of b2, preserving the multiset, next_tile, everything.
    before_multiset = sorted(t.description for t in b2.state.deck)
    rng = _random.Random(999)
    rng.shuffle(b2.state.deck)
    b2._str_repr_cache = None
    after_multiset = sorted(t.description for t in b2.state.deck)

    assert before_multiset == after_multiset, "shuffle must preserve the multiset"
    assert (b1.state.next_tile.description == b2.state.next_tile.description)
    # The actual order must differ for the test to be meaningful (retry a couple
    # of seeds worth of shuffles if by fluke it landed identical).
    tries = 0
    while ([t.description for t in b1.state.deck] == [t.description for t in b2.state.deck]
           and tries < 10):
        rng.shuffle(b2.state.deck)
        b2._str_repr_cache = None
        tries += 1
    assert ([t.description for t in b1.state.deck]
            != [t.description for t in b2.state.deck]), "deck order never changed"

    k1 = g.string_representation(b1)
    k2 = g.string_representation(b2)
    assert k1 == k2, "deck ORDER leaked into the transposition key (V5 no-leak FAIL)"


def test_3a_v5_negative_control_placed_tile_changes_key():
    """A state with one MORE placed tile must hash DIFFERENTLY (guards against a
    degenerate key that ignores real state)."""
    g, board = _mid_game_board(seed=11, plies=14)
    k_before = g.string_representation(board)

    mask = g.get_valid_moves(board)
    legal = np.flatnonzero(mask)
    assert len(legal) > 0
    advanced, _ = g.get_next_state(board, int(legal[0]))
    k_after = g.string_representation(advanced)
    assert k_before != k_after, "placing a tile did not change the key"


def test_3a_v5_negative_control_next_tile_changes_key():
    """Two states differing only in the REVEALED next_tile must hash differently
    (next_tile IS in the key — it is public info, unlike deck order)."""
    g, board = _mid_game_board(seed=7, plies=12)
    b1 = copy.deepcopy(board)
    b2 = copy.deepcopy(board)
    # Find a deck tile whose description differs from the current next_tile and
    # swap it in as next_tile on b2 (keep len(deck) equal by swapping, not popping).
    cur = b1.state.next_tile.description
    swap_idx = next((i for i, t in enumerate(b2.state.deck)
                     if t.description != cur), None)
    if swap_idx is None:
        pytest.skip("no differing tile available to construct the next_tile control")
    b2.state.deck[swap_idx], b2.state.next_tile = b2.state.next_tile, b2.state.deck[swap_idx]
    b1._str_repr_cache = None
    b2._str_repr_cache = None
    assert b1.state.next_tile.description != b2.state.next_tile.description
    assert g.string_representation(b1) != g.string_representation(b2), (
        "different revealed next_tile did not change the key"
    )


# =========================================================================== #
# 3b. FLYWHEEL-REGIME leak test — persistent tree, K=1 fair_chance per move,
#     NO clear() between moves. Compare against a clear()-per-move control on the
#     SAME game/seed and quantify stale-future node reuse + root-Q divergence.
# =========================================================================== #
def _make_mcts(game, *, sims, seed, evaluator):
    return NeuralMCTS(
        game=game,
        evaluator=evaluator,
        simulations=sims,
        seed=seed,
        c_puct=3.0,
        fair_chance=True,
    )


def _root_q_by_action(mcts, root_key):
    """{action: signed child-Q from root player POV} for the just-searched root."""
    root = mcts._nodes[root_key]
    out = {}
    for a, child in mcts._deduped_children(root):
        if child.N == 0:
            continue
        q = child.Q if child.player_to_move == root.player_to_move else -child.Q
        out[a] = q
    return out


def _chosen_action(qmap):
    return max(qmap, key=lambda a: (qmap[a], -a)) if qmap else None


def _run_game(*, persistent: bool, sims: int, seed: int, max_moves: int, evaluator):
    """Advance a real game move-by-move. `persistent`=True → the flywheel-gen
    regime (never clear() the tree). `persistent`=False → the clear()-per-move
    control. Same master deck / same search seed both ways.

    Returns per-move records:
      qmaps      : list of {action: root-Q} dicts
      chosen     : list of chosen actions
      reuse      : list of counts of INTERIOR nodes that already existed in the
                   tree BEFORE this move's search (i.e. created under a PRIOR
                   move's determinization) and gained visits during THIS move's
                   search — the stale-future reuse count.
    """
    _random.seed(seed)
    g = _fresh_game()
    master = g.get_init_board()  # keeps its TRUE deck order — never reshuffled
    mcts = _make_mcts(g, sims=sims, seed=seed, evaluator=evaluator)

    qmaps, chosen, reuse = [], [], []
    for _mv in range(max_moves):
        if g.get_game_ended(master, master.state.current_player) != 0.0:
            break
        mask = g.get_valid_moves(master)
        if len(np.flatnonzero(mask)) == 0:
            break

        # Snapshot pre-move tree: state_key -> N (visits so far).
        pre = {k: node.N for k, node in mcts._nodes.items()}

        # The reshuffle happens INSIDE search() (fair_chance). The root KEY is
        # deck-order-blind, so the search's root node is found by the same key
        # regardless of the reshuffled future.
        mcts.search(master)
        root_key = g.string_representation(master)  # master unmutated → true key
        qmap = _root_q_by_action(mcts, root_key)
        qmaps.append(qmap)
        chosen.append(_chosen_action(qmap))

        # Count stale-future reuse: nodes present BEFORE this move's search whose
        # visit count GREW during it, excluding the root itself (the root legit
        # accumulates across moves only in the persistent case; interior reuse is
        # the leak). These interior nodes were created under a prior move's
        # reshuffled deck and are now re-scored under a fresh one.
        grew = 0
        for k, node in mcts._nodes.items():
            if k == root_key:
                continue
            if k in pre and node.N > pre[k]:
                grew += 1
        reuse.append(grew)

        # Play the master's chosen action on the TRUE deck (best_action on master).
        a = mcts.best_action(master)
        master, _ = g.get_next_state(master, a)

        if not persistent:
            mcts.clear()

    return {"qmaps": qmaps, "chosen": chosen, "reuse": reuse}


def _summarize_divergence(pers, ctrl):
    """Root-Q divergence between persistent and clear-per-move runs, per move."""
    n = min(len(pers["qmaps"]), len(ctrl["qmaps"]))
    max_abs = 0.0
    mean_abs_list = []
    chosen_diffs = 0
    for i in range(n):
        qp, qc = pers["qmaps"][i], ctrl["qmaps"][i]
        common = set(qp) & set(qc)
        if common:
            diffs = [abs(qp[a] - qc[a]) for a in common]
            max_abs = max(max_abs, max(diffs))
            mean_abs_list.append(float(np.mean(diffs)))
        if pers["chosen"][i] != ctrl["chosen"][i]:
            chosen_diffs += 1
    return {
        "n_moves": n,
        "max_abs_q_div": max_abs,
        "mean_abs_q_div": float(np.mean(mean_abs_list)) if mean_abs_list else 0.0,
        "chosen_action_diffs": chosen_diffs,
        "total_stale_reuse_persistent": int(sum(pers["reuse"])),
        "total_stale_reuse_control": int(sum(ctrl["reuse"])),
        "max_stale_reuse_move_persistent": int(max(pers["reuse"]) if pers["reuse"] else 0),
    }


# Thresholds: this is a MECHANISM detector, not a strength test. "Material leak"
# = the persistent path reuses stale-future interior nodes AND that changes the
# search's root Q / choice vs the clear-per-move control by a non-trivial amount.
_Q_DIV_MATERIAL = 0.02          # |ΔQ| in [-1,1] units; >2% is non-trivial
_REUSE_MATERIAL = 1             # ≥1 interior node re-scored across determinizations


def _leak_verdict(summ):
    leaks = (
        summ["total_stale_reuse_persistent"] >= _REUSE_MATERIAL
        and (
            summ["max_abs_q_div"] >= _Q_DIV_MATERIAL
            or summ["chosen_action_diffs"] > 0
        )
    )
    return "LEAK" if leaks else "NO MATERIAL LEAK"


def test_3b_flywheel_regime_leak_stub():
    """Instrument the flywheel-gen regime and report LEAK / NO MATERIAL LEAK with
    numbers. This test always PASSES (it is a detector that emits a verdict); the
    verdict is asserted for internal consistency and printed for the report."""
    sims, seed, max_moves = 60, 3, 18
    pers = _run_game(persistent=True, sims=sims, seed=seed,
                     max_moves=max_moves, evaluator=_stub_evaluator)
    ctrl = _run_game(persistent=False, sims=sims, seed=seed,
                     max_moves=max_moves, evaluator=_stub_evaluator)
    summ = _summarize_divergence(pers, ctrl)
    verdict = _leak_verdict(summ)

    print("\n=== 3b FLYWHEEL-REGIME LEAK TEST (stub evaluator) ===")
    for k, v in summ.items():
        print(f"  {k:36s}: {v}")
    print(f"  {'VERDICT':36s}: {verdict}")

    # The CONTROL (clear-per-move) must have ZERO cross-move interior reuse by
    # construction — the tree is wiped each move. This validates the instrument:
    # any reuse the persistent path shows is genuinely cross-determinization.
    assert summ["total_stale_reuse_control"] == 0, (
        "clear-per-move control showed cross-move node reuse — instrument is wrong"
    )
    # Internal-consistency assertion (does not fail the run; documents the verdict).
    assert verdict in ("LEAK", "NO MATERIAL LEAK")


@pytest.mark.skipif(not CKPT.exists(), reason="canonical checkpoint missing")
def test_3b_flywheel_regime_leak_real_net():
    """Same detector driven by the REAL warmstart_canonical net. Net QUALITY is
    irrelevant to a structural-leak test; this just confirms the stub finding
    reproduces on the production evaluator path."""
    import torch
    from carcassonne_ai.evaluators import make_single_evaluator
    from carcassonne_ai.network import CarcassonneNet

    device = torch.device("cpu")  # mechanism test — keep it CPU/cheap
    ck = torch.load(str(CKPT), map_location=device, weights_only=False)
    ns = int(ck.get("n_scalar_features", 10))
    net = CarcassonneNet(
        n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
        n_scalar_features=ns,
        value_global_pool=bool(ck.get("value_global_pool", False)),
    ).to(device)
    net.load_state_dict(ck["model_state"])
    net.train(False)
    g = Game(enable_legal_moves_cache=True, include_farm_scalars=ns > 10)
    evaluator = make_single_evaluator(net, device, g)

    sims, seed, max_moves = 40, 5, 12
    pers = _run_game(persistent=True, sims=sims, seed=seed,
                     max_moves=max_moves, evaluator=evaluator)
    ctrl = _run_game(persistent=False, sims=sims, seed=seed,
                     max_moves=max_moves, evaluator=evaluator)
    summ = _summarize_divergence(pers, ctrl)
    verdict = _leak_verdict(summ)

    print("\n=== 3b FLYWHEEL-REGIME LEAK TEST (real net) ===")
    for k, v in summ.items():
        print(f"  {k:36s}: {v}")
    print(f"  {'VERDICT':36s}: {verdict}")

    assert summ["total_stale_reuse_control"] == 0
    assert verdict in ("LEAK", "NO MATERIAL LEAK")
