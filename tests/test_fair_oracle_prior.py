"""Track-F Gate A FAIR-mode oracle-prior confirm harness contract (F2, 2026-07-19).

Covers the fair analog of tests/test_oracle_prior.py — the CONFIRM stage
(scripts/classical_search/eval_fair_puct.py + the per-world oracle path in
src/carcassonne_ai/fair_agent.py::FairHeuristicPriorAgent):

  1. EXTRACTION REUSE — the fair path and the clairvoyant screen share the SAME
     alias-fold / eps-floor helpers (carcassonne_ai.oracle_prior), so a copy-paste
     divergence is structurally impossible (identity assert).
  2. PER-WORLD INJECTION — the KEY correctness property: inside the fair PIMC root
     loop each determinization world runs ITS OWN pre-search and gets ITS OWN
     ROOT-prior override (not a shared one), and the override reaches the fair
     reshuffled root.
  3. OFF is byte-identical — the OFF agent never touches the oracle attributes, and
     the harness _save omits every oracle_* field (schema-identical) OFF, records
     them losslessly ON.
  4. HARNESS wiring — the tag carries -oracle<mult> on the CANDIDATE segment only,
     and the CLI exclusivity/validation gates fire.

Leaf env is pinned to the production v2.9 Bmild_cap8 substrate BEFORE importing
carcassonne_ai (mirrors tests/test_fair_puct_agent.py)."""
from __future__ import annotations

import os

for _k, _v in {
    "CARCASSONNE_V25_CAP": "8", "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0", "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1", "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1", "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
}.items():
    os.environ.setdefault(_k, _v)

import importlib.util
import json
import random
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

from carcassonne_ai import oracle_prior as OP  # noqa: E402
from carcassonne_ai import fair_agent as FA  # noqa: E402
from carcassonne_ai.fair_agent import FairHeuristicMCTSAgent, FairHeuristicPriorAgent  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import (  # noqa: E402
    HeuristicPriorConfig,
    make_heuristic_prior_evaluator,
)
from carcassonne_ai.mcts import NeuralMCTS  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402


def _load_by_path(name, rel):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# The clairvoyant screen (re-exports the shared helpers) + the fair harness (by path,
# same idiom as tests/test_oracle_prior.py importing eval_puct_priors).
epp = _load_by_path("eval_puct_priors", "scripts/classical_search/eval_puct_priors.py")
efp = _load_by_path("eval_fair_puct", "scripts/classical_search/eval_fair_puct.py")


def _cfg():
    return HeuristicPriorConfig(
        c_puct=1.5, tau_p=5.0, leaf_quantize="float", final_select="visits",
        value_norm=15.0, leaf_cfg=DEFAULT_CONFIG, reuse_tree=False, root_select="puct",
    )


def _midgame(seed: int, plies: int):
    """Deterministic mid-game Board after `plies` random moves (big unseen deck, so
    two reshuffled determinizations genuinely differ)."""
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    b = game.get_init_board()
    rng = random.Random(seed ^ 0xA5A5)
    for _ in range(plies):
        legal = np.flatnonzero(game.get_valid_moves(b))
        b, _ = game.get_next_state(b, int(rng.choice(legal)))
    assert game.get_game_ended(b, 0) == 0.0
    return game, b


# --------------------------------------------------------------------------- #
# 1. EXTRACTION REUSE — no copy-paste divergence.                              #
# --------------------------------------------------------------------------- #
def test_extraction_reuse_no_divergence():
    """The fair confirm and the clairvoyant screen must use the SAME extraction
    functions (single source: carcassonne_ai.oracle_prior). Identity, not equality —
    a copy-paste would break the `is`."""
    # clairvoyant screen re-exports the library helpers under its private names.
    assert epp._oracle_prior_from_visits is OP.oracle_prior_from_visits
    assert epp._root_action_groups is OP.root_action_groups
    assert epp._LeafCounter is OP.LeafCounter
    # the fair agent imports the SAME library helpers (module-level names).
    assert FA.oracle_prior_from_visits is OP.oracle_prior_from_visits
    assert FA.root_action_groups is OP.root_action_groups
    assert FA.LeafCounter is OP.LeafCounter


# --------------------------------------------------------------------------- #
# 2. PER-WORLD INJECTION — the KEY correctness property.                        #
# --------------------------------------------------------------------------- #
def test_per_world_injection_each_world_its_own_distribution():
    """A seeded 2-world oracle move: EACH determinization must run its OWN pre-search
    and receive its OWN ROOT-prior override — not a single shared distribution."""
    game, board = _midgame(5, 20)
    agent = FairHeuristicPriorAgent(
        Game(enable_legal_moves_cache=True), _cfg(), sims=24, k_dets=2, seed=7,
        exact_endgame=False, oracle_prior_mult=2)
    mv = agent.choose_action(board)
    assert game.get_valid_moves(board)[mv], "oracle fair agent returned an illegal action"
    # one oracle move, k_dets pre-searches (world count x moves).
    assert agent.oracle_moves == 1
    assert agent.oracle_presearch_worlds == agent.oracle_moves * 2
    # per-world overrides captured, and the two worlds' distributions DIFFER (each is
    # built from its OWN reshuffled deck's pre-search — a shared distribution is refuted).
    assert agent.last_world_oracle_priors is not None
    assert len(agent.last_world_oracle_priors) == 2
    o0, o1 = agent.last_world_oracle_priors
    assert o0 != o1, "both worlds got the SAME override — the pre-search is not per-world"
    # each override is a valid prior over the SAME legal set (structural, not per-deck).
    for ov in (o0, o1):
        assert abs(sum(ov.values()) - 1.0) < 1e-9
        assert all(p >= 0.0 for p in ov.values())
    # the override reached every world's root, and the pre-search did ~mult x the leaf work.
    assert agent.last_reached_root
    assert agent.oracle_presearch_leaf_calls > agent.oracle_mainsearch_leaf_calls
    ratio = agent.oracle_presearch_leaf_calls / max(1, agent.oracle_mainsearch_leaf_calls)
    assert 1.5 < ratio < 2.5, f"pre/main leaf ratio {ratio:.2f} not ~mult=2"


def test_injection_reaches_fair_reshuffled_root_whitebox():
    """White-box: the one-shot override lands on the root of a search over a FAIR
    reshuffled determinization (the exact per-world main-search construction)."""
    game, board = _midgame(11, 18)
    evaluator = make_heuristic_prior_evaluator(game, _cfg())
    # the per-world reshuffled deck (the fair PIMC determinization).
    b = FairHeuristicMCTSAgent.reshuffled_determinization(board, random.Random(3))

    # a pre-search distribution on THIS world -> an override (via the shared helpers).
    pre = NeuralMCTS(game=game, evaluator=evaluator, simulations=48, c_puct=1.5, seed=1)
    pre.search(b)
    counts, actions = pre.root_visit_distribution(b)
    groups = OP.root_action_groups(game, b)
    override = OP.oracle_prior_from_visits(
        groups, {int(a): float(c) for a, c in zip(actions, counts)}, 1e-3)
    assert override, "pre-search produced no override"

    # main search with the override injected: the root priors must equal the override.
    m = NeuralMCTS(game=game, evaluator=evaluator, simulations=16, c_puct=1.5, seed=1)
    m.set_root_prior_override(override)
    m.search(b)
    root = m._nodes[game.string_representation(b)]
    for a in root.valid_actions:
        assert root.priors[a] == pytest.approx(override.get(int(a), 0.0), abs=1e-9)
    # one-shot: consumed after the single search.
    assert m._root_prior_override is None


# --------------------------------------------------------------------------- #
# 3. OFF is byte-identical (agent + harness schema).                            #
# --------------------------------------------------------------------------- #
def test_off_agent_never_touches_oracle_state():
    """An OFF fair agent (default) leaves every oracle attribute inert and plays the
    SAME move as one that was handed oracle_prior_mult=None explicitly."""
    _game, board = _midgame(2, 16)
    a_plain = FairHeuristicPriorAgent(Game(enable_legal_moves_cache=True), _cfg(),
                                      sims=24, k_dets=2, seed=4, exact_endgame=False)
    a_none = FairHeuristicPriorAgent(Game(enable_legal_moves_cache=True), _cfg(),
                                     sims=24, k_dets=2, seed=4, exact_endgame=False,
                                     oracle_prior_mult=None)
    assert a_plain.choose_action(board) == a_none.choose_action(board)
    assert a_plain.oracle_prior_mult is None
    assert a_plain.oracle_moves == 0 and a_plain.oracle_presearch_worlds == 0
    assert a_plain.last_world_oracle_priors is None
    assert a_plain.last_reached_root is False


def _mk_result(**kw):
    base = dict(seed=1, a_seat=0, info="fair", exact_k=2, k_dets=2, sims=24,
                rung_sims=800, score_p0=10, score_p1=8, diff=2, won_by_champ=True,
                drew=False, elapsed_s=1.0, moves=10, champ_prefix_moves=5)
    base.update(kw)
    return efp.GameResult(**base)


def test_save_omits_oracle_fields_when_off(tmp_path):
    p = tmp_path / "seed1_a0.json"
    efp._save(p, _mk_result())
    d = json.load(open(p))
    assert not any(k.startswith("oracle_") for k in d), "OFF cell must be schema-identical"
    r2 = efp._try_load(p)                      # lossless: defaults refill the omitted keys
    assert r2.oracle_prior_moves == 0 and r2.oracle_presearch_worlds == 0


def test_save_includes_oracle_fields_when_on(tmp_path):
    p = tmp_path / "seed1_a0.json"
    efp._save(p, _mk_result(oracle_prior_moves=70, oracle_presearch_worlds=280,
                            oracle_presearch_secs=16.8, oracle_mainsearch_secs=7.6,
                            oracle_presearch_leaf_calls=8117,
                            oracle_mainsearch_leaf_calls=4061))
    d = json.load(open(p))
    assert d["oracle_prior_moves"] == 70 and d["oracle_presearch_worlds"] == 280
    assert d["oracle_presearch_leaf_calls"] == 8117
    r2 = efp._try_load(p)                      # lossless round-trip
    assert r2.oracle_mainsearch_leaf_calls == 4061


def test_oracle_telemetry_empty_for_non_oracle_agent():
    """_oracle_telemetry returns {} for a non-oracle candidate (so the GameResult keeps
    its default zeros and _save omits them)."""
    _game, _board = _midgame(1, 8)
    plain = FairHeuristicPriorAgent(Game(enable_legal_moves_cache=True), _cfg(),
                                    sims=8, k_dets=2, seed=1, exact_endgame=False)
    assert efp._oracle_telemetry(plain) == {}
    assert efp._oracle_telemetry(None) == {}


# --------------------------------------------------------------------------- #
# 4. HARNESS wiring — tag on the CANDIDATE only + CLI validation.               #
# --------------------------------------------------------------------------- #
def test_tag_carries_oracle_on_candidate_only(tmp_path):
    """--summary-only builds the out-dir tag without playing: -oracle<mult> must ride
    the CANDIDATE segment (before _vs_<opponent>), never leak onto the opponent."""
    rc = efp.main(["--info", "fair", "--opponent", "fair-champion",
                   "--oracle-prior-mult", "3", "--k-dets", "2", "--sims", "24",
                   "--exact-k", "2", "--n", "2", "--paired", "--summary-only",
                   "--out-root", str(tmp_path)])
    assert rc == 0
    subdirs = [p.name for p in tmp_path.iterdir() if p.is_dir()]
    assert len(subdirs) == 1, subdirs
    tag = subdirs[0]
    assert "-oracle3" in tag
    # the oracle suffix must sit on the CANDIDATE side of the `_vs_` opponent identity.
    cand_part, _, opp_part = tag.partition("_vs_")
    assert "-oracle3" in cand_part and "oracle" not in opp_part, tag


@pytest.mark.parametrize("argv,needle", [
    (["--info", "fair-netprior", "--net", "x.pt", "--oracle-prior-mult", "3"],
     "requires --info fair"),
    (["--info", "fair-net", "--net", "x.pt", "--oracle-prior-mult", "3"],
     "requires --info fair"),
    (["--info", "fair", "--net", "x.pt", "--oracle-prior-mult", "3"],
     "mutually exclusive with --net"),
    (["--info", "fair", "--oracle-prior-mult", "1"],
     "must be >= 2"),
])
def test_cli_validation_rejects_bad_oracle_combos(argv, needle, capsys):
    with pytest.raises(SystemExit):
        efp.main(argv + ["--n", "2", "--paired"])
    err = capsys.readouterr().err
    assert needle in err, f"expected {needle!r} in stderr, got: {err}"


def test_agent_rejects_oracle_with_batching():
    """Batching (virtual loss) perturbs PUCT selection, confounding the ROOT-prior
    probe — the agent hard-rejects the combo even though the CLI can't reach it."""
    with pytest.raises(ValueError, match="oracle_prior_mult requires batch_size=1"):
        FairHeuristicPriorAgent(Game(enable_legal_moves_cache=True), _cfg(),
                                sims=8, k_dets=2, seed=1, oracle_prior_mult=3,
                                batch_size=2)
    with pytest.raises(ValueError, match="must be >= 2"):
        FairHeuristicPriorAgent(Game(enable_legal_moves_cache=True), _cfg(),
                                sims=8, k_dets=2, seed=1, oracle_prior_mult=1)
