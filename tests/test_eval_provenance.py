"""Tests for the runtime-verified evaluator-provenance layer (eval_provenance).

Covers the two reviewer assertions (R1 leaf-identity, R7 residual-fired), the
seed-namespace guard, deck-hash determinism, the `_V25Wrapped` counters, and the
spec extractors. The NEGATIVE tests are the load-bearing ones: a manifest that
CLAIMS one leaf while another ran must raise ProvenanceError.
"""
from __future__ import annotations

import numpy as np
import pytest

from carcassonne_ai import eval_provenance as ep
from carcassonne_ai.game_wrapper import Game


# --- file / git / deck helpers --------------------------------------------

def test_sha256_file_missing_returns_none(tmp_path):
    assert ep.sha256_file(tmp_path / "nope.bin") is None
    assert ep.sha256_file(None) is None


def test_sha256_file_matches_hashlib(tmp_path):
    import hashlib
    p = tmp_path / "x.bin"
    p.write_bytes(b"carcassonne")
    assert ep.sha256_file(p) == hashlib.sha256(b"carcassonne").hexdigest()


def test_git_commit_and_dirty_shape():
    sha, dirty = ep.git_commit_and_dirty()
    assert isinstance(sha, str) and isinstance(dirty, bool)
    # in this repo git is present, so it is a 40-hex sha or the 'unknown' sentinel
    assert sha == "unknown" or (len(sha) == 40 and all(c in "0123456789abcdef" for c in sha))


def test_deck_hash_deterministic_and_seed_sensitive():
    import random
    random.seed(ep.EVAL_SEED_FLOOR)
    h1 = ep.deck_hash(Game(enable_legal_moves_cache=True).get_init_board())
    random.seed(ep.EVAL_SEED_FLOOR)
    h2 = ep.deck_hash(Game(enable_legal_moves_cache=True).get_init_board())
    random.seed(ep.EVAL_SEED_FLOOR + 1)
    h3 = ep.deck_hash(Game(enable_legal_moves_cache=True).get_init_board())
    assert h1 == h2, "same seed must give same deck hash"
    assert h1 != h3, "different seed should (almost surely) give a different deck"
    assert len(h1) == 16


def test_deck_hash_covers_first_drawn_tile():
    """Regression (hygiene 4c): the engine draws the FIRST tile into next_tile at
    init, so two decks differing only in that first tile must NOT collide. The
    pre-fix hash (state.deck only) omitted next_tile and would collide here."""
    import random
    random.seed(ep.EVAL_SEED_FLOOR)
    board = Game(enable_legal_moves_cache=True).get_init_board()
    h0 = ep.deck_hash(board)
    orig = board.state.next_tile
    # Swap in a deck tile whose description differs from next_tile (deck unchanged
    # in content is irrelevant — only next_tile changes), so the FULL initial deck
    # differs solely in the first drawn tile.
    alt = next((t for t in board.state.deck if t.description != orig.description), None)
    assert alt is not None, "expected a base deck with >1 tile description"
    board.state.next_tile = alt
    assert ep.deck_hash(board) != h0, (
        "changing only the first drawn tile (next_tile) must change deck_hash")


# --- seed namespace guard --------------------------------------------------

def test_seed_guard_rejects_selfplay_namespace():
    with pytest.raises(ep.ProvenanceError):
        ep.assert_clean_eval_seed_range(600_000, 400)
    with pytest.raises(ep.ProvenanceError):
        ep.assert_clean_eval_seed_range(ep.EVAL_SEED_FLOOR - 1, 1)


def test_seed_guard_accepts_clean_floor():
    ep.assert_clean_eval_seed_range(ep.EVAL_SEED_FLOOR, 400)        # no raise
    ep.assert_clean_eval_seed_range(ep.EVAL_SEED_FLOOR + 50_000, 1000)


# --- R1 leaf-identity assertion (heuristic side) ---------------------------

def _heur_spec(leaf_name):
    return ep.EvaluatorSpec(
        side="B", agent_class="HeuristicMCTS", search_impl="HeuristicMCTS",
        leaf_name=leaf_name, leaf_version=None, policy_source="none", sims=200)


def test_claims_v2_7_but_ran_v1_raises():
    """The exact R1 defect: manifest says v2_7, runtime ran v1."""
    spec = _heur_spec("v2_7")
    with pytest.raises(ep.ProvenanceError, match="claims leaf v2_7"):
        ep.assert_provenance_consistent([spec], {"B": {"v1_calls": 5, "v2_7_calls": 0}})


def test_claims_v1_but_ran_v2_7_raises():
    spec = _heur_spec("v1")
    with pytest.raises(ep.ProvenanceError, match="claims leaf v1"):
        ep.assert_provenance_consistent([spec], {"B": {"v1_calls": 0, "v2_7_calls": 9}})


def test_matched_v2_7_passes():
    spec = _heur_spec("v2_7")
    r = ep.assert_provenance_consistent([spec], {"B": {"v1_calls": 0, "v2_7_calls": 9}})
    assert r["ok"] is True and r["checked"][0]["leaf"] == "v2_7"


# --- R7 residual-fired assertion (neural side) -----------------------------

def _neural_spec(residual_scale=0.0, value_blend=0.0, leaf_name="v2_7"):
    return ep.EvaluatorSpec(
        side="A", agent_class="NeuralMCTS", search_impl="NeuralMCTS",
        leaf_name=leaf_name, leaf_version="2.7", policy_source="network", sims=200,
        residual_scale=residual_scale, value_blend=value_blend)


def test_residual_set_but_never_fired_raises():
    """The R7 silent fallback: residual_scale>0 but the resid path never executed."""
    spec = _neural_spec(residual_scale=0.25)
    with pytest.raises(ep.ProvenanceError, match="residual"):
        ep.assert_provenance_consistent([spec], {"A": {"v25_calls": 10, "resid_path": 0, "blend_path": 0}})


def test_residual_fired_passes():
    spec = _neural_spec(residual_scale=0.25)
    r = ep.assert_provenance_consistent([spec], {"A": {"v25_calls": 10, "resid_path": 10, "blend_path": 0}})
    assert r["ok"] and r["checked"][0]["resid_path"] == 10


def test_pure_v2_7_with_value_leak_raises():
    """residual==0 and blend==0 must mean NO net-value path ran (no silent leak)."""
    spec = _neural_spec(residual_scale=0.0, value_blend=0.0)
    with pytest.raises(ep.ProvenanceError, match="leaked"):
        ep.assert_provenance_consistent([spec], {"A": {"v25_calls": 10, "resid_path": 3, "blend_path": 0}})


def test_pure_v2_7_clean_passes():
    spec = _neural_spec()
    r = ep.assert_provenance_consistent([spec], {"A": {"v25_calls": 10, "resid_path": 0, "blend_path": 0}})
    assert r["ok"]


def test_blend_set_but_never_blended_raises():
    spec = _neural_spec(value_blend=0.5)
    with pytest.raises(ep.ProvenanceError, match="blend"):
        ep.assert_provenance_consistent([spec], {"A": {"v25_calls": 10, "resid_path": 0, "blend_path": 0}})


def test_v2_7_neural_but_leaf_never_ran_raises():
    spec = _neural_spec()
    with pytest.raises(ep.ProvenanceError, match="never executed"):
        ep.assert_provenance_consistent([spec], {"A": {"v25_calls": 0, "resid_path": 0, "blend_path": 0}})


def test_missing_counters_for_side_is_not_a_contradiction():
    # No counters captured for a side → skipped, not an error.
    spec = _heur_spec("v2_7")
    r = ep.assert_provenance_consistent([spec], {})
    assert r["ok"] and r["checked"] == []


# --- build block + schema validation ---------------------------------------

def test_build_eval_provenance_structure():
    specs = [_neural_spec(), _heur_spec("v2_7")]
    block = ep.build_eval_provenance(specs, kind="unit", argv=["--x"])
    assert block["schema"] == ep.SCHEMA_ID
    assert block["kind"] == "unit"
    assert len(block["sides"]) == 2
    assert {s["side"] for s in block["sides"]} == {"A", "B"}
    assert "checkpoint_sha256" in block["sides"][0]


def test_validate_evaluator_block_never_raises_on_missing_dep():
    # jsonschema is not installed on the cluster → must be a no-op returning True.
    block = ep.build_eval_provenance([_heur_spec("v1")], kind="unit", argv=[])
    assert ep.validate_evaluator_block(block) is True


# --- spec extractors read the live object ----------------------------------

def test_spec_from_heuristic_mcts_reads_leaf():
    from carcassonne_ai.mcts import HeuristicMCTS
    g = Game(enable_legal_moves_cache=True)
    m = HeuristicMCTS(game=g, simulations=4, seed=1, heur_leaf="v2_7")
    spec = ep.spec_from_heuristic_mcts(m, side="B", sims=4)
    assert spec.leaf_name == "v2_7" and spec.leaf_version == "2.7"
    assert spec.agent_class == "HeuristicMCTS" and spec.policy_source == "none"


def test_spec_from_neural_mcts_reads_leaf_cfg():
    import dataclasses
    from carcassonne_ai.mcts import NeuralMCTS
    from carcassonne_ai.evaluators import make_v25_value_wrapper
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

    g = Game(enable_legal_moves_cache=True)
    a_space = g.action_space_size if hasattr(g, "action_space_size") else 1
    base = lambda board: (np.zeros(a_space, dtype=np.float32), 0.5)
    cfg = dataclasses.replace(DEFAULT_CONFIG, residual_scale=0.25, bonus_cap=12.0, opp_bonus_cap=12.0)
    leaf_eval = make_v25_value_wrapper(base, cfg)
    m = NeuralMCTS(game=g, evaluator=leaf_eval, simulations=16, c_puct=3.0)
    spec = ep.spec_from_neural_mcts(m, side="A", checkpoint_path=None, sims=16)
    assert spec.leaf_name == "v2_7"
    assert spec.residual_scale == 0.25
    assert spec.cap == 12.0 and spec.opp_cap == 12.0
    assert spec.c_puct == 3.0


# --- the _V25Wrapped counters actually increment ---------------------------

def test_v25_wrapped_counters_increment_on_call():
    from carcassonne_ai.evaluators import make_v25_value_wrapper
    g = Game(enable_legal_moves_cache=True)
    board = g.get_init_board()
    a_space = g.get_valid_moves(board).shape[0]
    base = lambda b: (np.zeros(a_space, dtype=np.float32), 0.5)
    wrapped = make_v25_value_wrapper(base)            # default cfg: resid=0, blend=0
    assert wrapped.counters.v25_calls == 0
    _priors, _val = wrapped(board)
    assert wrapped.counters.v25_calls == 1
    assert wrapped.counters.plain_path == 1
    assert wrapped.counters.net_value_path == 0       # pure v2.7, no value leak


def test_v25_wrapped_residual_counter_increments():
    import dataclasses
    from carcassonne_ai.evaluators import make_v25_value_wrapper
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
    g = Game(enable_legal_moves_cache=True)
    board = g.get_init_board()
    a_space = g.get_valid_moves(board).shape[0]
    base = lambda b: (np.zeros(a_space, dtype=np.float32), 0.5)
    cfg = dataclasses.replace(DEFAULT_CONFIG, residual_scale=0.25)
    wrapped = make_v25_value_wrapper(base, cfg)
    wrapped(board)
    assert wrapped.counters.resid_path == 1
    assert wrapped.counters.net_value_path == 1
