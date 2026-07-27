"""MEEPLE-DEDUP contracts — the flag-gated intra-tile meeple-action equivalence.

  (A) GROUPING       — meeple_equiv is the single source of truth; it reproduces the
                       android_bridge behaviour it was moved from, on every base tile.
  (B) MASKING        — dedup_legal keeps exactly one member of each group, never merges
                       across meeple types, and is inert outside the meeple phase.
  (C) CROSS-CHECK    — the search-side grouping agrees action-for-action with the census
                       implementation on REAL replayed positions.
  (D) BIT-EXACT OFF  — with the flag off (the default), a scripted game + fixed-seed
                       searches reproduce tests/golden/meeple_dedup_off.json, which was
                       recorded on the PRE-CHANGE tree. This is the production guard.
  (E) ON CORRECTNESS — one member per group expanded, root visits conserved, and the
                       move chosen comes from the group the OFF search chose from.
  (F) PLUMBING       — env flag vs per-agent kwarg, and two agents disagreeing in one
                       process (what a candidate-vs-champion screen needs).

Regenerate the golden with scripts/measurement_infra/gen_meeple_dedup_fixture.py — but
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
os.environ["CARCASSONNE_MEEPLE_DEDUP"] = "0"

import json  # noqa: E402
import random  # noqa: E402
import sys  # noqa: E402
from collections import Counter, defaultdict  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
for _p in ("scripts/measurement_infra", "android/app/src/main/python"):
    _abs = str(REPO / _p)
    if _abs not in sys.path:
        sys.path.insert(0, _abs)

from carcassonne_ai import meeple_equiv as ME  # noqa: E402
from carcassonne_ai.action_space import (  # noqa: E402
    FARMER_SIDES,
    NORMAL_SIDES,
    meeple_normal_base,
    meeple_pass_index,
)
from carcassonne_ai.fair_agent import FairHeuristicPriorAgent  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import (  # noqa: E402
    HeuristicPriorConfig,
    make_heuristic_prior_evaluator,
)
from carcassonne_ai.mcts import NeuralMCTS  # noqa: E402
from snapshot import frozen_v29_cfg  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402
from wingedsheep.carcassonne.objects.side import Side  # noqa: E402
from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles  # noqa: E402

GOLDEN = REPO / "tests" / "golden" / "meeple_dedup_off.json"
WINDOW = 25                       # the default action-space window size
NBASE = meeple_normal_base(WINDOW)
PASS_IDX = meeple_pass_index(WINDOW)
ON_SIMS = 200                     # section (E): stable enough that the pick is settled


def scenario_config() -> HeuristicPriorConfig:
    """Must stay in lockstep with gen_meeple_dedup_fixture.scenario_config."""
    return HeuristicPriorConfig(final_select="visits", leaf_cfg=frozen_v29_cfg())


@pytest.fixture(scope="module")
def golden() -> dict:
    return json.loads(GOLDEN.read_text())


# =========================================================================== #
# (A) GROUPING — the single source of truth                                    #
# =========================================================================== #

def test_android_bridge_reexports_the_same_object():
    """The bridge must not keep its own copy — one definition, or they drift."""
    import android_bridge

    assert android_bridge.feature_groups is ME.feature_groups


def test_census_imports_the_same_object():
    import meeple_dedup_census as MDC

    assert MDC.feature_groups is ME.feature_groups


def _independent_partition(tile) -> list[set]:
    """Re-derive the equivalence partition straight from the tile model.

    Deliberately NOT a call into meeple_equiv: this is the regression oracle for the
    move out of android_bridge, so it has to be written from the rules the docstring
    states (city side-groups / road Connections with CENTER excluded / chapel CENTER /
    farmer_positions) rather than from the code under test.
    """
    parts: list[set] = []
    for grp in getattr(tile, "city", ()) or ():
        s = {side.value for side in grp}
        if s:
            parts.append(s)
    for conn in getattr(tile, "road", ()) or ():
        s = {side.value for side in (conn.a, conn.b)
             if side is not None and side != Side.CENTER}
        if s:
            parts.append(s)
    if getattr(tile, "chapel", False) or getattr(tile, "flowers", False):
        parts.append({Side.CENTER.value})
    for farm in getattr(tile, "farms", ()) or ():
        s = {side.value for side in (getattr(farm, "farmer_positions", ()) or ())}
        if s:
            parts.append(s)
    return parts


@pytest.mark.parametrize("name", sorted(base_tiles))
@pytest.mark.parametrize("rot", (0, 1, 2, 3))
def test_feature_groups_matches_independent_rederivation(name, rot):
    """All 32 base tiles x 4 rotations: same partition as the model says."""
    tile = base_tiles[name].turn(rot)
    got = ME.feature_groups(tile)
    want = _independent_partition(tile)

    # Same set of described sides.
    assert set(got) == {v for part in want for v in part}
    # Same partition: two sides share an id iff the oracle puts them in one part.
    by_id: dict[int, set] = defaultdict(set)
    for side, gid in got.items():
        by_id[gid].add(side)
    assert sorted(map(sorted, by_id.values())) == sorted(map(sorted, want))


@pytest.mark.parametrize("name", sorted(base_tiles))
@pytest.mark.parametrize("rot", (0, 1, 2, 3))
def test_slot_group_ids_agrees_with_feature_groups(name, rot):
    tile = base_tiles[name].turn(rot)
    raw = ME.feature_groups(tile)
    ids = ME.slot_group_ids(tile)
    assert len(ids) == ME.N_SLOTS == 9
    for i, side in enumerate(ME.SLOT_SIDES):
        if side.value in raw:
            assert ids[i] != ME.NO_GROUP
        else:
            assert ids[i] == ME.NO_GROUP, f"{name} rot{rot}: {side} should be ungrouped"
    # Two slots share an id iff they share a raw group.
    for i in range(ME.N_SLOTS):
        for j in range(i + 1, ME.N_SLOTS):
            if ids[i] == ME.NO_GROUP or ids[j] == ME.NO_GROUP:
                continue
            same_raw = raw[ME.SLOT_SIDES[i].value] == raw[ME.SLOT_SIDES[j].value]
            assert (ids[i] == ids[j]) is same_raw


@pytest.mark.parametrize("name", sorted(base_tiles))
def test_knight_and_farmer_slots_are_never_merged(name):
    """A type-different action must never be collapsed into a same-feature group."""
    for rot in range(4):
        ids = ME.slot_group_ids(base_tiles[name].turn(rot))
        knight = {g for g in ids[:len(NORMAL_SIDES)] if g != ME.NO_GROUP}
        farmer = {g for g in ids[len(NORMAL_SIDES):] if g != ME.NO_GROUP}
        assert not (knight & farmer)
        assert len(ids) == len(NORMAL_SIDES) + len(FARMER_SIDES)


def test_slot_group_ids_memo_is_stable_and_bounded():
    ME._SLOT_CACHE.clear()
    first = {(n, r): ME.slot_group_ids(base_tiles[n].turn(r))
             for n in base_tiles for r in range(4)}
    n_entries = len(ME._SLOT_CACHE)
    second = {(n, r): ME.slot_group_ids(base_tiles[n].turn(r))
              for n in base_tiles for r in range(4)}
    assert first == second
    assert len(ME._SLOT_CACHE) == n_entries      # the second pass added nothing
    assert n_entries <= len(base_tiles) * 4      # 32 tiles x 4 rotations bounds it


def test_none_tile_is_all_private():
    assert ME.slot_group_ids(None) == (ME.NO_GROUP,) * ME.N_SLOTS
    assert ME.feature_groups(None) == {}


# =========================================================================== #
# (B) MASKING — dedup_legal on synthetic decisions (the census' tile cases)     #
# =========================================================================== #

def _stub_board(tile, *, phase=GamePhase.MEEPLES, has_last=True):
    """The smallest board dedup_legal reads: phase, last tile action, tile, window."""
    grid = defaultdict(lambda: defaultdict(lambda: None))
    grid[0][0] = tile
    last = SimpleNamespace(coordinate=SimpleNamespace(row=0, column=0)) if has_last else None
    return SimpleNamespace(
        state=SimpleNamespace(phase=phase, last_tile_action=last, board=grid),
        offset=SimpleNamespace(size=WINDOW),
    )


def _actions_for(sides) -> np.ndarray:
    """Flat action ids for the given Side.value strings, ascending (as a mask would be)."""
    out = []
    for v in sides:
        side = next(s for s in ME.SLOT_SIDES if s.value == v)
        out.append(NBASE + ME.SLOT_SIDES.index(side))
    return np.array(sorted(out), dtype=np.int64)


def _kept_actions(tile, sides, *, with_pass=True):
    legal = _actions_for(sides)
    if with_pass:
        legal = np.append(legal, PASS_IDX)
    dd = ME.dedup_legal(_stub_board(tile), legal)
    if dd is None:
        return [int(a) for a in legal], []
    keep, folds = dd
    return [int(legal[i]) for i in keep], [(int(legal[d]), int(legal[s]))
                                           for d, s in folds]


def test_two_opening_city_collapses_to_one():
    """`city_diagonal_top_right` is city=[[top, right]] — ONE city, two openings."""
    kept, folds = _kept_actions(base_tiles["city_diagonal_top_right"], ["top", "right"])
    assert kept == [NBASE + 0, PASS_IDX]            # TOP survives (lowest id), pass kept
    assert folds == [(NBASE + 0, NBASE + 1)]        # RIGHT's prior mass folds into TOP


def test_two_separate_cities_are_untouched():
    """`city_left_right` is city=[[left], [right]] — two cities that must stay distinct."""
    kept, folds = _kept_actions(base_tiles["city_left_right"], ["left", "right"])
    assert kept == [NBASE + 1, NBASE + 3, PASS_IDX]
    assert folds == []


def test_crossroads_stubs_stay_four_features():
    kept, folds = _kept_actions(base_tiles["crossroads"],
                                ["top", "right", "bottom", "left"])
    assert len(kept) == 5 and folds == []           # 4 roads + pass, nothing merged


def test_full_city_collapses_four_to_one():
    kept, folds = _kept_actions(base_tiles["full_city_with_shield"],
                                ["top", "right", "bottom", "left"])
    assert kept == [NBASE + 0, PASS_IDX]
    assert len(folds) == 3 and all(dst == NBASE + 0 for dst, _ in folds)


def test_two_farm_fields_collapse_to_two():
    """`city_narrow` farms are [[top_left, top_right], [bottom_left, bottom_right]]."""
    kept, folds = _kept_actions(
        base_tiles["city_narrow"],
        ["top_left", "top_right", "bottom_left", "bottom_right"])
    assert len(kept) == 3 and len(folds) == 2       # 2 fields + pass


def test_undescribed_side_is_never_merged():
    kept, _ = _kept_actions(base_tiles["full_city_with_shield"],
                            ["top", "right", "top_left", "bottom_left"], with_pass=False)
    # top+right are one city -> 1; the two farm sides are undescribed -> private each.
    assert len(kept) == 3


def test_inert_outside_the_meeple_phase():
    tile = base_tiles["full_city_with_shield"]
    legal = _actions_for(["top", "right", "bottom", "left"])
    assert ME.dedup_legal(_stub_board(tile, phase=GamePhase.TILES), legal) is None
    assert ME.dedup_legal(_stub_board(tile, has_last=False), legal) is None
    assert ME.dedup_legal(_stub_board(None), legal) is None


def test_pass_only_decision_is_inert():
    board = _stub_board(base_tiles["full_city_with_shield"])
    assert ME.dedup_legal(board, np.array([PASS_IDX], dtype=np.int64)) is None


# =========================================================================== #
# (C) CROSS-CHECK — search-side grouping == census grouping, on real positions  #
# =========================================================================== #

def _replay(actions):
    """Yield (ply, game, board) at every meeple-phase board of the recorded game."""
    game = Game(enable_legal_moves_cache=True)
    random.seed(json.loads(GOLDEN.read_text())["deck_seed"])
    board = game.get_init_board()
    for ply, a in enumerate(actions):
        if board.state.phase == GamePhase.MEEPLES:
            yield ply, game, board
        board, _ = game.get_next_state(board, int(a))


def test_dedup_matches_the_census_grouping_on_real_positions(golden):
    """The search's masking must remove exactly what the census counts as redundant."""
    import meeple_dedup_census as MDC
    from carcassonne_ai.action_space import decode

    checked = 0
    for _ply, game, board in _replay(golden["actions"]):
        legal = np.flatnonzero(game.get_valid_moves(board))
        nonpass = [int(a) for a in legal if int(a) != PASS_IDX]
        if not nonpass:
            continue
        coord = board.state.last_tile_action.coordinate
        tile = board.state.board[coord.row][coord.column]
        sides = [decode(a, off=board.offset, phase="meeples",
                        last_tile_coord=coord).coordinate_with_side.side.value
                 for a in nonpass]
        census_groups = MDC.dense_groups(tile, sides)
        want_redundant = len(census_groups) - len(set(census_groups))

        dd = ME.dedup_legal(board, legal)
        got_redundant = 0 if dd is None else len(dd[1])
        assert got_redundant == want_redundant

        # ... and the same PARTITION, not merely the same count.
        got_groups = ME.equivalent_meeple_action_groups(game, board)
        assert set(got_groups) == set(nonpass)
        as_parts = defaultdict(set)
        for a, g in got_groups.items():
            as_parts[g].add(a)
        census_parts = defaultdict(set)
        for a, g in zip(nonpass, census_groups):
            census_parts[g].add(a)
        assert (sorted(map(sorted, as_parts.values()))
                == sorted(map(sorted, census_parts.values())))
        checked += 1
    assert checked >= 10, f"only {checked} real meeple decisions exercised"


# =========================================================================== #
# (D) BIT-EXACT OFF — the production guard                                     #
# =========================================================================== #

def test_flag_defaults_off():
    assert ME.MEEPLE_DEDUP is False
    assert ME.resolve(None) is False
    assert NeuralMCTS(game=Game(), evaluator=lambda b: (None, 0.0)).meeple_dedup is False


def test_bit_exact_off_matches_pre_change_fixture(golden):
    """Replay the recorded scenario with the flag OFF: identical actions AND identical
    root visit counts to the pre-MEEPLE_DEDUP tree. Any diff is a production regression."""
    cfg = scenario_config()
    game = Game(enable_legal_moves_cache=True)
    random.seed(golden["deck_seed"])
    board = game.get_init_board()
    agent = FairHeuristicPriorAgent(game, cfg=cfg, sims=golden["sims"],
                                    k_dets=golden["k_dets"], seed=golden["agent_seed"],
                                    exact_endgame=False)
    evaluator = make_heuristic_prior_evaluator(game, cfg)

    actions: list[int] = []
    probes: list[dict] = []
    for _ply in range(golden["plies"]):
        if game.get_game_ended(board, board.state.current_player) != 0.0:
            break
        if board.state.phase == GamePhase.MEEPLES and len(probes) < len(golden["probes"]):
            m = NeuralMCTS(game=game, evaluator=evaluator,
                           simulations=golden["probe_sims"], c_puct=cfg.c_puct,
                           seed=golden["probe_seed"])
            counts = m.search(board)
            visits, pactions = m.root_visit_distribution(board)
            probes.append({
                "ply": len(actions),
                "visits_by_action": {str(int(a)): int(n) for a, n in counts.items()},
                "deduped_actions": [int(a) for a in pactions],
                "deduped_visits": [int(v) for v in visits],
                "best_action": int(m.best_action(board)),
            })
        a = int(agent.choose_action(board))
        actions.append(a)
        board, _ = game.get_next_state(board, a)

    assert actions == golden["actions"]
    assert probes == golden["probes"]
    assert game.string_representation(board) == golden["final_key"]


# =========================================================================== #
# (E) ON CORRECTNESS                                                           #
# =========================================================================== #

@pytest.fixture(scope="module")
def duplicate_positions(golden):
    """Every ply of the recorded game whose meeple decision has a real duplicate."""
    out = []
    for ply, game, board in _replay(golden["actions"]):
        groups = ME.equivalent_meeple_action_groups(game, board)
        if groups and max(Counter(groups.values()).values()) >= 2 and len(groups) >= 2:
            out.append(ply)
    assert len(out) >= 5, f"fixture game only offers {len(out)} duplicate decisions"
    return out


def _search_at(game, evaluator, board, cfg, dedup):
    m = NeuralMCTS(game=game, evaluator=evaluator, simulations=ON_SIMS,
                   c_puct=cfg.c_puct, seed=golden_seed(), meeple_dedup=dedup)
    m.search(board)
    return m, m._nodes[game.string_representation(board)]


def golden_seed() -> int:
    return 5


def test_on_expands_one_member_per_group_and_conserves_visits(golden,
                                                              duplicate_positions):
    cfg = scenario_config()
    evaluator = None
    seen = 0
    for ply, game, board in _replay(golden["actions"]):
        if ply not in duplicate_positions:
            continue
        if evaluator is None:
            evaluator = make_heuristic_prior_evaluator(game, cfg)
        groups = ME.equivalent_meeple_action_groups(game, board)
        _m_off, root_off = _search_at(game, evaluator, board, cfg, False)
        m_on, root_on = _search_at(game, evaluator, board, cfg, True)

        # 1. one member per group survives into the action space...
        by_group = Counter(groups[a] for a in root_on.valid_actions if a in groups)
        assert by_group and max(by_group.values()) == 1
        # ... and it is the LOWEST action id of its group (deterministic representative).
        for a in root_on.valid_actions:
            if a in groups:
                members = [x for x, g in groups.items() if g == groups[a]]
                assert a == min(members)
        # 2. no duplicate child was ever created.
        assert set(root_on.children) <= set(root_on.valid_actions)
        # 3. the dedup actually bit at this position.
        assert len(root_on.valid_actions) < len(root_off.valid_actions)
        # 4. visits conserved: every simulation still lands on exactly one root child.
        assert sum(c.N for c in root_on.children.values()) == ON_SIMS
        assert sum(c.N for c in root_off.children.values()) == ON_SIMS
        # 5. priors still normalize over the surviving actions.
        assert root_on.priors.keys() == set(root_on.valid_actions)
        assert sum(root_on.priors.values()) == pytest.approx(1.0, abs=1e-6)
        seen += 1
    assert seen == len(duplicate_positions)


def test_on_picks_from_the_group_the_off_search_chose(golden, duplicate_positions):
    """The move must stay in the same equivalence class — dedup reallocates the budget,
    it does not redirect the decision to a different feature."""
    cfg = scenario_config()
    evaluator = None
    for ply, game, board in _replay(golden["actions"]):
        if ply not in duplicate_positions:
            continue
        if evaluator is None:
            evaluator = make_heuristic_prior_evaluator(game, cfg)
        groups = ME.equivalent_meeple_action_groups(game, board)
        m_off, _ = _search_at(game, evaluator, board, cfg, False)
        m_on, _ = _search_at(game, evaluator, board, cfg, True)
        v_off, a_off = m_off.root_visit_distribution(board)
        v_on, a_on = m_on.root_visit_distribution(board)
        pick_off = int(a_off[int(np.argmax(v_off))])
        pick_on = int(a_on[int(np.argmax(v_on))])

        mask = game.get_valid_moves(board)
        assert mask[pick_on], f"ply {ply}: dedup search returned an illegal action"
        # `groups` covers placements only; a pass on either side must be a pass on both.
        assert (pick_on in groups) == (pick_off in groups)
        if pick_on in groups:
            assert groups[pick_on] == groups[pick_off], (
                f"ply {ply}: ON chose feature {groups[pick_on]}, OFF chose "
                f"{groups[pick_off]}")


# =========================================================================== #
# (F) PLUMBING                                                                 #
# =========================================================================== #

def _dummy_mcts(**kw):
    return NeuralMCTS(game=Game(), evaluator=lambda b: (None, 0.0), **kw)


def test_kwarg_overrides_the_env_flag(monkeypatch):
    monkeypatch.setattr(ME, "MEEPLE_DEDUP", False)
    assert _dummy_mcts().meeple_dedup is False
    assert _dummy_mcts(meeple_dedup=True).meeple_dedup is True
    monkeypatch.setattr(ME, "MEEPLE_DEDUP", True)
    assert _dummy_mcts().meeple_dedup is True
    assert _dummy_mcts(meeple_dedup=False).meeple_dedup is False


def test_set_enabled_exports_env_for_spawned_workers(monkeypatch):
    monkeypatch.setattr(ME, "MEEPLE_DEDUP", False)
    monkeypatch.setenv(ME.ENV_VAR, "0")
    ME.set_enabled(True)
    try:
        assert ME.MEEPLE_DEDUP is True
        assert os.environ[ME.ENV_VAR] == "1"       # a spawn child re-reads this
        assert ME._env_flag() is True
    finally:
        ME.set_enabled(False)
    assert ME.MEEPLE_DEDUP is False


def test_env_flag_parsing(monkeypatch):
    for val, want in (("1", True), ("true", True), ("ON", True), ("yes", True),
                      ("0", False), ("", False), ("no", False)):
        monkeypatch.setenv(ME.ENV_VAR, val)
        assert ME._env_flag() is want


def test_two_agents_in_one_process_can_disagree():
    """A dedup-ON candidate must be able to face a dedup-OFF champion in ONE worker."""
    game = Game(enable_legal_moves_cache=True)
    cfg = scenario_config()
    on = FairHeuristicPriorAgent(game, cfg=cfg, sims=8, k_dets=1, seed=1,
                                 exact_endgame=False, meeple_dedup=True)
    off = FairHeuristicPriorAgent(game, cfg=cfg, sims=8, k_dets=1, seed=1,
                                  exact_endgame=False, meeple_dedup=False)
    assert on.meeple_dedup is True and off.meeple_dedup is False
    default = FairHeuristicPriorAgent(game, cfg=cfg, sims=8, k_dets=1, seed=1,
                                      exact_endgame=False)
    assert default.meeple_dedup is None            # = inherit, and the flag is OFF


def test_prior_mode_fold_vs_drop(monkeypatch, golden):
    """Both prior modes are live code. FOLD gives the surviving representative the mass
    of its whole group (the `prior_bonus` convention); DROP discards the duplicates'
    mass and renormalizes, so equal-delta features get equal prior regardless of how
    many openings they happen to have. Either way the priors sum to 1 over survivors."""
    cfg = scenario_config()
    seen = 0
    for _ply, game, board in _replay(golden["actions"]):
        groups = ME.equivalent_meeple_action_groups(game, board)
        if not groups or max(Counter(groups.values()).values()) < 2:
            continue
        evaluator = make_heuristic_prior_evaluator(game, cfg)
        priors = {}
        for mode in ("fold", "drop"):
            monkeypatch.setattr(ME, "PRIOR_MODE", mode)
            m = NeuralMCTS(game=game, evaluator=evaluator, simulations=1,
                           c_puct=cfg.c_puct, seed=5, meeple_dedup=True)
            m.search(board)
            root = m._nodes[game.string_representation(board)]
            priors[mode] = dict(root.priors)
            assert sum(priors[mode].values()) == pytest.approx(1.0, abs=1e-6)
        # Same surviving action set, genuinely different mass allocation.
        assert priors["fold"].keys() == priors["drop"].keys()
        rep = min(a for a in groups
                  if sum(1 for x, g in groups.items() if g == groups[a]) >= 2)
        assert priors["fold"][rep] > priors["drop"][rep]
        seen += 1
        if seen >= 3:
            break
    assert seen >= 3


def test_agent_kwarg_reaches_the_search():
    game = Game(enable_legal_moves_cache=True)
    cfg = scenario_config()
    from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorAgent

    assert HeuristicPriorAgent(game, cfg, simulations=4).mcts.meeple_dedup is False
    assert HeuristicPriorAgent(game, cfg, simulations=4,
                               meeple_dedup=True).mcts.meeple_dedup is True
