"""GATE (a) for the P6 persistent / re-rootable tree — `carc_rs.PersistentSearcher`
and `rust_agent.RustCarryClairvoyantAgent` against the Python `HeuristicPriorAgent`.

⚠️ WHY A CARRIED SEARCH NEEDS ITS OWN GATE.  Every prior rustport gate (G3
reconcile_search, GATE_CLAIRVOYANT, GATE_KWIDTH_BACKEND) compares a search that
starts from an EMPTY tree.  A carried search differs from a fresh one in ways
those gates structurally cannot see:

  * the root arrives with accumulated `(N, W)`, so `sqrt(parent_N)` in the PUCT
    term is different from simulation 1;
  * an already-EXPANDED root is not re-expanded, so it keeps the raw-f64
    `leaf_value` it got as an INTERIOR node and never takes the root-only
    `float32` round-trip `_eval_boards` applies (`Searcher::expand(via_f32)`);
  * the tree keeps nodes from earlier plies, so a later descent can transpose
    into a subtree that a fresh search would have had to build.

The comparison surface is therefore the whole root table, as RAW f64 BITS, at
EVERY ply of an advancing game — chosen action, `root.N`, `root.W`, every
`(action, N, W)` child edge, the PRE-search root visit count, and the node count
of the whole transposition table.

THE THREE TRANSITIONS, all gated here:
    best_action          -> the tree carries (Python clears NOTHING, at any reuse_tree)
    move(reuse=False)    -> clear() first; must equal `search_single` bit-for-bit
    move(reuse=True)     -> `_reroot_or_clear`, incl. its hit/fresh/collide outcomes

⚠️ `fair_common` MUST be imported before `carcassonne_ai` (import-frozen leaf env),
so it precedes every other project import in this file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "src", REPO / "engine", REPO / "scripts" / "measurement_infra",
           REPO / "scripts" / "rustport"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

carc_rs = pytest.importorskip("carc_rs", reason="build with `maturin develop --release`")

try:                                    # noqa: E402
    import fair_common as F             # applies the leaf env preamble
except RuntimeError as _e:              # pragma: no cover - import-order guard
    pytest.skip(f"production leaf env was not frozen into carcassonne_ai: {_e}",
                allow_module_level=True)

import trace_search as T  # noqa: E402
from carcassonne_ai import champion_factory as CF  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorAgent  # noqa: E402
from carcassonne_ai.rust_agent import RustCarryClairvoyantAgent  # noqa: E402
from root_replay import replay_actions  # noqa: E402

CHAMP_GAMES = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"

# Cheap but structurally complete: at sims=64 from ply 40 the carried root
# already pre-exists on every ply after the first (verified by the test itself),
# which is the condition the whole gate is about.
SIMS = 64
START_PLY = 40


def _root_table(agent, game, board) -> dict:
    """The Python root's comparable surface, floats as raw f64 bits."""
    root = agent.mcts._nodes[game.string_representation(board)]
    return {
        "root_n": int(root.N),
        "root_w_bits": F.ubits(root.W),
        "root_children": [[int(a), int(c.N), F.ubits(c.W)]
                          for a, c in sorted(root.children.items())],
        "tree_len": len(agent.mcts._nodes),
    }


def _rs_table(res: dict) -> dict:
    return {
        "root_n": int(res["root_n"]),
        "root_w_bits": int(res["root_w_bits"]),
        "root_children": [[int(a), int(n), int(w)] for a, n, w in res["root_children"]],
        "tree_len": int(res["tree_len"]),
    }


@pytest.fixture(scope="module")
def root():
    if not CHAMP_GAMES.exists():          # pragma: no cover - artifact-dependent
        pytest.skip(f"no recorded champion games at {CHAMP_GAMES}")
    rec = json.loads(next(ln for ln in CHAMP_GAMES.open() if ln.strip()))
    acts = [int(a) for a in rec["actions"]]
    deck_seed = int(rec["deck_seed"])
    game, board = replay_actions(deck_seed, acts, START_PLY)
    return game, board, deck_seed, acts


def _agents(root, *, reuse_tree=False, auto_advance=False, sims=SIMS):
    game, board, deck_seed, acts = root
    cfg = CF.production_prior_cfg()
    py = HeuristicPriorAgent(game, cfg, simulations=sims, seed=7,
                             reuse_tree=reuse_tree)
    rs = RustCarryClairvoyantAgent(game, cfg, simulations=sims, seed=7,
                                   reuse_tree=reuse_tree,
                                   auto_advance=auto_advance)
    rs.seat(deck_seed, acts[:START_PLY], board=board)
    return py, rs


# --------------------------------------------------------------------------- #
# THE GATE: a multi-ply CARRIED search, node for node                           #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("plies", [6])
def test_carried_search_matches_python_root_table_every_ply(root, plies):
    game, board, _seed, _acts = root
    py, rs = _agents(root)
    b = board
    carried_plies = 0
    for ply in range(plies):
        key = game.string_representation(b)
        pre = py.mcts._nodes.get(key)
        pre_n = int(pre.N) if pre is not None else 0
        with T.production_leaf_dispatch():
            a_py = int(py.best_action(b))
        a_rs = int(rs.best_action(b))
        res = rs.last_search()
        assert a_py == a_rs, f"ply {ply}: action {a_py} != {a_rs}"
        assert pre_n == int(res["root_n_before"]), (
            f"ply {ply}: pre-search root N {pre_n} != {res['root_n_before']} — the "
            "two trees do not agree on what was CARRIED IN")
        assert _root_table(py, game, b) == _rs_table(res), f"ply {ply}: root table"
        if pre_n > 0:
            carried_plies += 1
            # The carry is what makes this gate non-redundant with G3.
            assert int(res["root_n"]) == pre_n + SIMS
        b, _ = game.get_next_state(b, a_py)
        rs.advance(a_py)
    assert carried_plies >= plies - 1, (
        "the root must pre-exist on every ply after the first, or this gate is "
        f"testing a fresh-tree search in disguise (carried on {carried_plies})")


def test_first_carried_ply_is_the_fresh_search(root):
    """Ply 0 of a carried run == `search_single` == `move(reuse_tree=False)`."""
    game, board, deck_seed, acts = root
    _py, rs_carry = _agents(root)
    _py2, rs_fresh = _agents(root)
    a_carry = rs_carry.best_action(board)
    a_fresh = rs_fresh.move(board)
    assert a_carry == a_fresh
    assert _rs_table(rs_carry.last_search()) == _rs_table(rs_fresh.last_search())
    # ...and both equal the un-sessioned `MirrorState.search_single`.
    ms = carc_rs.MirrorState.from_seed(str(deck_seed))
    for a in acts[:START_PLY]:
        ms.advance(int(a))
    single = ms.search_single(rs_carry._scfg)
    assert int(single["chosen_action"]) == a_carry
    assert int(single["root_n"]) == int(rs_carry.last_search()["root_n"])
    assert int(single["root_w_bits"]) == int(rs_carry.last_search()["root_w_bits"])
    assert ([[int(a), int(n), int(w)] for a, n, w in single["root_children"]]
            == _rs_table(rs_carry.last_search())["root_children"])


# --------------------------------------------------------------------------- #
# move() — the OTHER transition: clear (reuse_tree=False)                       #
# --------------------------------------------------------------------------- #
def test_move_without_reuse_clears_and_matches_python(root):
    game, board, _seed, _acts = root
    py, rs = _agents(root, reuse_tree=False)
    b = board
    for ply in range(3):
        with T.production_leaf_dispatch():
            a_py = int(py.move(b))
        a_rs = int(rs.move(b))
        res = rs.last_search()
        assert a_py == a_rs, f"ply {ply}"
        assert int(res["root_n_before"]) == 0, "move(reuse=False) must CLEAR"
        assert int(res["root_n"]) == SIMS
        assert _root_table(py, game, b) == _rs_table(res), f"ply {ply}: root table"
        b, _ = game.get_next_state(b, a_py)
        rs.advance(a_py)


# --------------------------------------------------------------------------- #
# move() with reuse_tree=True — the re-root                                     #
# --------------------------------------------------------------------------- #
def test_move_with_reuse_tree_reroots_like_python(root):
    game, board, _seed, _acts = root
    py, rs = _agents(root, reuse_tree=True)
    b = board
    for ply in range(4):
        with T.production_leaf_dispatch():
            a_py = int(py.move(b))
        a_rs = int(rs.move(b))
        res = rs.last_search()
        assert a_py == a_rs, f"ply {ply}"
        assert _root_table(py, game, b) == _rs_table(res), f"ply {ply}: root table"
        b, _ = game.get_next_state(b, a_py)
        rs.advance(a_py)
    # the three `_reroot_or_clear` counters, ported name for name
    assert (py.reuse_hits, py.reuse_fresh, py.reuse_collide) == \
           (rs.reuse_hits, rs.reuse_fresh, rs.reuse_collide)
    assert rs.reuse_hits > 0, "a same-game continuation must re-root at least once"


def test_reroot_to_an_unseen_position_clears(root):
    """`_reroot_or_clear` case (b): board absent from the retained tree."""
    game, board, deck_seed, acts = root
    _py, rs = _agents(root, reuse_tree=True)
    rs.move(board)
    assert rs.tree_len() > 1
    # Jump the mirror far past anything the tree explored.
    a = int(rs.last_search()["chosen_action"])
    b = board
    b, _ = game.get_next_state(b, a)
    rs.advance(a)
    for _ in range(6):
        legal = [int(x) for x in game.get_valid_moves(b).nonzero()[0]]
        mv = legal[-1]
        b, _ = game.get_next_state(b, mv)
        rs.advance(mv)
    before_fresh = rs.reuse_fresh
    rs.move(b)
    assert rs.reuse_fresh == before_fresh + 1
    assert int(rs.last_search()["root_n"]) == SIMS


# --------------------------------------------------------------------------- #
# The mirror contract                                                           #
# --------------------------------------------------------------------------- #
def test_auto_advance_walks_the_mirror_itself(root):
    """The playout-loop shape (`oracle_score_pilot._playout_value`): the caller
    never advances a mirror, so the agent must."""
    game, board, _seed, _acts = root
    py, rs = _agents(root, auto_advance=True)
    b = board
    for ply in range(4):
        with T.production_leaf_dispatch():
            a_py = int(py.best_action(b))
        a_rs = int(rs.best_action(b))          # NO rs.advance() here — that is the point
        assert a_py == a_rs, f"ply {ply}"
        assert _root_table(py, game, b) == _rs_table(rs.last_search())
        b, _ = game.get_next_state(b, a_py)


def test_a_stale_mirror_raises_rather_than_answering(root):
    from carcassonne_ai.rust_agent import MirrorDesync

    game, board, _seed, _acts = root
    _py, rs = _agents(root)
    a = rs.best_action(board)
    b, _ = game.get_next_state(board, int(a))
    # the caller "forgot" to advance
    with pytest.raises(MirrorDesync):
        rs.best_action(b)


def test_evaluator_injection_still_fails_closed(root):
    """Gap 3 is NOT closed by this feature and must keep refusing."""
    game, _board, _seed, _acts = root
    with pytest.raises(ValueError, match="evaluator injection"):
        RustCarryClairvoyantAgent(game, CF.production_prior_cfg(), simulations=8,
                                  evaluator=object())


def test_reuse_tree_defaults_from_the_config_like_python(root):
    """⚠️ The production clairvoyant cfg carries ``reuse_tree=True``.

    A Rust ruler that defaulted the flag to False would silently CLEAR where the
    Python champion RE-ROOTS — invisible to any single-move gate (a fresh agent
    has nothing to re-root into) and worth 24 carried visits per ply in a game.
    This pins the resolution rule itself.
    """
    game, board, deck_seed, acts = root
    cfg = CF.production_prior_cfg()
    py = HeuristicPriorAgent(game, cfg, simulations=SIMS, seed=7)
    rs = RustCarryClairvoyantAgent(game, cfg, simulations=SIMS, seed=7)
    assert py._reuse_tree == rs._reuse_tree == bool(cfg.reuse_tree)
    assert rs.stats()["reuse_tree"] == bool(cfg.reuse_tree)
    # ...and an explicit kwarg still wins, on both.
    assert not RustCarryClairvoyantAgent(game, cfg, simulations=SIMS,
                                         reuse_tree=False)._reuse_tree


def test_default_config_move_matches_python_over_a_game(root):
    """The `_MarginalizedHandoff` shape: `.move()` at the CONFIG's own reuse_tree."""
    game, board, deck_seed, acts = root
    cfg = CF.production_prior_cfg()
    py = HeuristicPriorAgent(game, cfg, simulations=SIMS, seed=7)
    rs = RustCarryClairvoyantAgent(game, cfg, simulations=SIMS, seed=7)
    rs.seat(deck_seed, acts[:START_PLY], board=board)
    b = board
    for ply in range(4):
        with T.production_leaf_dispatch():
            a_py = int(py.move(b))
        a_rs = int(rs.move(b))
        assert a_py == a_rs, f"ply {ply}"
        assert _root_table(py, game, b) == _rs_table(rs.last_search()), f"ply {ply}"
        b, _ = game.get_next_state(b, a_py)
        rs.advance(a_py)
    assert (py.reuse_hits, py.reuse_fresh, py.reuse_collide) == \
           (rs.reuse_hits, rs.reuse_fresh, rs.reuse_collide)


def test_stats_names_the_tree_policy(root):
    _py, rs = _agents(root)
    st = rs.stats()
    assert st["backend"] == "rust"
    assert st["agent_class"] == "RustCarryClairvoyantAgent"
    assert "persistent" in st["tree_policy"]
    assert set(st) >= {"reuse_hits", "reuse_fresh", "reuse_collide", "tree_nodes",
                       "simulations", "reuse_tree", "auto_advance"}
