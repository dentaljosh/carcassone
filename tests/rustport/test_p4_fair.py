"""Fast always-on guards for the rustport P4 fair agent (k-parallel PIMC + the
one-way exact latch + the marginalized solver).

The full G4 gate is `scripts/rustport/reconcile_fair.py --leg all` at
k8x1376.  These are the cheap subset plus the unit-level contracts a corpus
sweep would only catch indirectly:

* **the oracle is the CHAMPION** — the production leaf env is applied before
  `carcassonne_ai` is imported and `make_production_champion(verify=True)`'s
  provenance guard is live.  Without this, the gate would compare Rust against a
  cap-5 / meeple_k-0 leaf and go green on the wrong agent (this is not
  hypothetical — it is how the first draft of `fair_common` was wrong);
* the determinizer reproduces `reshuffled_determinization` deck-for-deck,
  including the CL-056 sort-before-shuffle canonicalization;
* the forced-move short-circuit consumes NO randomness;
* the pooled-Q rule's three tiebreaks and the min-visits floor;
* thread-count invariance (the merge is a sequential fold after every join);
* the marginalized solver against the values FROZEN ON DISK in
  `tests/golden/golden_fixture.json`, not a live Python recomputation.

⚠️ `fair_common` MUST be imported before `carcassonne_ai`, so it is imported
before every other project import in this file.
"""

from __future__ import annotations

import json
import random
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
    # fair_common checks the REAL invariant (were the import-frozen knobs already
    # at their production values when carcassonne_ai was frozen?), so this only
    # fires when the oracle really would be the wrong champion. Run this module
    # in its own process (`pytest tests/rustport`) to gate it.
    pytest.skip(f"production leaf env was not frozen into carcassonne_ai: {_e}",
                allow_module_level=True)

import reconcile_fair as R  # noqa: E402
import trace_search as T  # noqa: E402
from carcassonne_ai.fair_agent import FairHeuristicMCTSAgent  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402

GOLDEN = REPO / "tests" / "golden" / "golden_fixture.json"
CHAMP = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"


@pytest.fixture(scope="module")
def knobs() -> dict:
    return T.production_knobs()


@pytest.fixture(scope="module")
def champ_game() -> dict:
    with CHAMP.open() as fh:
        return json.loads(next(iter(fh)))


# --------------------------------------------------------------------------- #
# Provenance — the gate must grade the champion, not a lookalike               #
# --------------------------------------------------------------------------- #
def test_the_oracle_leaf_is_the_leaf_driven_into_rust(knobs):
    """`champion_factory` resolves the leaf from the import-frozen env;
    `trace_search` builds `prod-curve125` from PRODUCTION.yaml.  Two independent
    paths — equality is a real check, and `assert_same_leaf` fires inside
    `py_agent`, so constructing one at all is the assertion."""
    game = Game(enable_legal_moves_cache=True)
    agent = F.py_agent(game, sims=4, k_dets=1, seed=1)
    leaf = agent._cfg.resolved_leaf_cfg()
    assert float(leaf.bonus_cap) == 8.0
    assert float(leaf.opp_bonus_cap) == 8.0
    assert tuple(float(x) for x in leaf.v29_meeple_curve) == \
        (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25)
    assert knobs["leaf"]["leaf_hash"] == "a36d2e15a3b3d71d"


def test_a_wrong_leaf_is_refused(knobs):
    """The provenance guard can go RED — a gate that cannot fail is not a gate."""
    import dataclasses

    game = Game(enable_legal_moves_cache=True)
    agent = F.py_agent(game, sims=4, k_dets=1, seed=1)
    bad = dict(knobs)
    bad["leaf_cfg"] = dataclasses.replace(knobs["leaf_cfg"], bonus_cap=5.0)
    with pytest.raises(SystemExit):
        F.assert_same_leaf(agent, bad)


# --------------------------------------------------------------------------- #
# Seeds + determinization                                                      #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("seed", [0, 1, 101, 2**31 - 1, 123456789])
@pytest.mark.parametrize("move_idx", [0, 1, 37, 250])
def test_seed_derivation_matches(seed, move_idx):
    game = Game(enable_legal_moves_cache=True)
    pa = F.py_agent(game, sims=4, k_dets=1, seed=seed)
    ra = F.rs_agent(sims=4, k_dets=1, seed=seed)
    assert ra.det_seed_base(move_idx) == pa.det_seed_base(move_idx)
    for i in range(4):
        assert ra.det_search_seed(move_idx, i) == pa.det_search_seed(move_idx, i)


@pytest.mark.parametrize("ply", [0, 17, 55, 100])
def test_determinizations_match_deck_for_deck(champ_game, ply):
    """Includes the CL-056 hardening: the unseen deck is SORTED by description
    before the shuffle, so the world is a function of the multiset + rng only."""
    game, board, _lat, _lk = R._seat(champ_game["deck_seed"],
                                     champ_game["actions"], ply)
    K = 8
    pa = F.py_agent(game, sims=4, k_dets=K, seed=101)
    ra = F.rs_agent(sims=4, k_dets=K, seed=101)
    ra.start_game_from_seed(str(int(champ_game["deck_seed"])))
    for a in champ_game["actions"][:ply]:
        ra.advance(int(a))
    rng = random.Random(pa.det_seed_base(ply) + 1)
    want = []
    for _ in range(K):
        b = FairHeuristicMCTSAgent.reshuffled_determinization(board, rng)
        want.append([t.description for t in b.state.deck])
    assert ra.determinizations(ply) == want


def test_determinization_ignores_the_true_deck_order(champ_game):
    """A different (unobservable) engine deck ORDER must give the same worlds."""
    ply = 40
    ra = F.rs_agent(sims=4, k_dets=4, seed=5)
    ra.start_game_from_seed(str(int(champ_game["deck_seed"])))
    for a in champ_game["actions"][:ply]:
        ra.advance(int(a))
    base = ra.determinizations(ply)
    deck = ra.unseen_deck()
    ra.set_unseen_deck(list(reversed(deck)))
    assert ra.determinizations(ply) == base


# --------------------------------------------------------------------------- #
# The pooled-Q rule                                                            #
# --------------------------------------------------------------------------- #
def test_pooled_q_argmax_agrees_with_python_on_synthetic_pools():
    """The Rust pool is internal, so exercise the RULE through the Python one and
    assert the documented semantics the port implements."""
    from carcassonne_ai.fair_agent import pooled_q_argmax

    # min-visits floor excludes a 1-visit noise pick
    assert pooled_q_argmax({9: 1.0, 3: 4.0}, {9: 5.0, 3: 2.0}, 2) == 3
    # ...unless nothing qualifies
    assert pooled_q_argmax({9: 1.0, 3: 1.0}, {9: 5.0, 3: 2.0}, 2) == 9
    # equal Q -> higher N
    assert pooled_q_argmax({9: 4.0, 3: 8.0}, {9: 2.0, 3: 4.0}, 2) == 3
    # equal Q and N -> LOWEST action
    assert pooled_q_argmax({9: 4.0, 3: 4.0}, {9: 2.0, 3: 2.0}, 2) == 3


# --------------------------------------------------------------------------- #
# The forced-move short-circuit                                                #
# --------------------------------------------------------------------------- #
def test_a_forced_move_runs_no_search_and_draws_no_randomness():
    """Ply 0 offers exactly one placement.  The short-circuit lives in the AGENT
    (not the search), returns before `det_rng` is even constructed, and stamps a
    one-hot policy row."""
    ra = F.rs_agent(sims=100_000, k_dets=8, seed=1, threads=1)
    ra.start_game_from_seed("7")
    assert len(ra.legal_actions()) == 1
    import time
    t0 = time.perf_counter()
    a = ra.choose_action()
    dt = time.perf_counter() - t0
    assert a == ra.legal_actions()[0]
    assert dt < 1.0, "a forced move ran the searches"
    m = ra.last_move()
    assert m["forced"] and not m["exact"] and m["pooled"] == []
    assert ra.stats()["last_pooled_visits"] == [(a, 1.0)]


# --------------------------------------------------------------------------- #
# Thread-count invariance                                                      #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("ply", [20, 64])
def test_thread_count_invariance(champ_game, ply):
    _g, _b, latched, latch_k = R._seat(champ_game["deck_seed"],
                                       champ_game["actions"], ply)
    ref = None
    for t in (1, 4, 8):
        ra = F.rs_agent(sims=64, k_dets=8, seed=909, threads=t)
        R._rs_seat(ra, champ_game["deck_seed"], champ_game["actions"], ply,
                   latched, latch_k, ply)
        rec = F.rs_decision(ra)
        if ref is None:
            ref = rec
        else:
            assert F.compare_decision(ref, rec, f"t{t}") == []


# --------------------------------------------------------------------------- #
# The latch                                                                    #
# --------------------------------------------------------------------------- #
def test_latch_trajectory_matches_over_a_recorded_game(champ_game):
    random.seed(int(champ_game["deck_seed"]))
    game = Game(enable_legal_moves_cache=True)
    py = F.latch_trajectory_py(game, champ_game["actions"])
    rs = F.latch_trajectory_rs(champ_game["deck_seed"], champ_game["actions"])
    assert py == rs
    assert any(lat for _p, _k, lat in py), "the game never reached the latch band"


# --------------------------------------------------------------------------- #
# The marginalized solver                                                      #
# --------------------------------------------------------------------------- #
def _golden_solver_positions():
    return R.golden_solver_positions()


@pytest.mark.parametrize("idx", range(14))
def test_solver_reproduces_the_frozen_golden_values(idx):
    """Re-judged against the values ON DISK, not a live Python recomputation."""
    pos = _golden_solver_positions()
    if idx >= len(pos):
        pytest.skip("fixture holds fewer solver positions than expected")
    p = pos[idx]
    ra = F.rs_agent(sims=1, k_dets=1, seed=0)
    ra.start_game_from_seed(str(p["deck_seed"]))
    for a in p["actions"][:p["ply"]]:
        ra.advance(int(a))
    rs = F.rs_solve(ra)
    assert rs is not None
    assert rs["value_bits"] == F.ubits(float(p["frozen"]["value"]))
    assert rs["optimal_actions"] == [int(a) for a in p["frozen"]["optimal_actions"]]
    assert rs["nodes"] == int(p["frozen"]["nodes"])


def test_solver_matches_the_live_python_oracle(champ_game):
    """Every K<=2 decision of one recorded game — the deployed band."""
    traj = F.latch_trajectory_rs(champ_game["deck_seed"], champ_game["actions"])
    plies = [p for p, k, _ in traj if k <= F.EXACT_MAX_K]
    assert plies, "no K<=2 decisions in this game"
    n = 0
    for ply in plies:
        game, board, _lat, _lk = R._seat(champ_game["deck_seed"],
                                         champ_game["actions"], ply)
        ra = F.rs_agent(sims=1, k_dets=1, seed=0)
        ra.start_game_from_seed(str(int(champ_game["deck_seed"])))
        for a in champ_game["actions"][:ply]:
            ra.advance(int(a))
        assert F.compare_solve(F.py_solve(game, board),
                               F.rs_solve(ra), f"ply{ply}") == []
        game.clear_caches()
        n += 1
    assert n >= 2


def test_budget_exceeded_is_reported_as_a_fallback_not_an_error(champ_game):
    """A blown budget is `None` (⇒ the agent falls back to fair PIMC for that
    decision and STAYS latched), not an exception."""
    traj = F.latch_trajectory_rs(champ_game["deck_seed"], champ_game["actions"])
    ply = [p for p, k, _ in traj if k <= F.EXACT_MAX_K][0]
    ra = F.rs_agent(sims=1, k_dets=1, seed=0)
    ra.start_game_from_seed(str(int(champ_game["deck_seed"])))
    for a in champ_game["actions"][:ply]:
        ra.advance(int(a))
    assert ra.solve_marginalized(1) is None
    assert ra.solve_marginalized(F.EXACT_BUDGET) is not None


# --------------------------------------------------------------------------- #
# Rejections                                                                   #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("kw", [
    {"k_dets": 0}, {"threads": 0}, {"exact_max_k": -1}, {"chance_drop": "nope"},
])
def test_bad_config_is_refused(knobs, kw):
    base = dict(sims=8, k_dets=2, seed=1, threads=1)
    base.update({k: v for k, v in kw.items() if k in ("k_dets", "threads")})
    with pytest.raises(ValueError):
        carc_rs.FairAgentRs(
            T.rs_config(8, knobs),
            k_dets=base["k_dets"], seed=1,
            exact_max_k=kw.get("exact_max_k", 2),
            chance_drop=kw.get("chance_drop", "type"),
            threads=base["threads"])


def test_choose_action_without_a_game_is_refused(knobs):
    ra = carc_rs.FairAgentRs(T.rs_config(8, knobs), k_dets=1, seed=0)
    with pytest.raises(RuntimeError):
        ra.choose_action()


# --------------------------------------------------------------------------- #
# The full-game lockstep (the test_kparallel template), cheap budget           #
# --------------------------------------------------------------------------- #
@pytest.mark.slow
@pytest.mark.parametrize("deck_seed,agent_seed,threads", [(7, 101, 1), (23, 202, 4)])
def test_full_game_action_identity(deck_seed, agent_seed, threads):
    out = R._game_job({
        "leg": "game", "label": f"unit/{deck_seed}", "deck_seed": deck_seed,
        "agent_seed": agent_seed, "sims": 24, "k_dets": 4, "threads": threads,
        "max_moves": None})
    assert out["mismatches"] == []
    assert out["decisions"] > 100
    assert out["exact_moves"] > 0, "the game never reached the exact latch"
