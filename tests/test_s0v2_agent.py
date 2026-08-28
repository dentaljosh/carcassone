"""Tests for the S0v2 scripted exploiter (measurement/s0v2_scripted_prep/).

⛔ S0v2 is a measurement instrument, never a production candidate — see
``measurement/s0v2_scripted_prep/DESIGN.md`` §0.

Three layers:
  * UNIT — the census-event detector and the plan state machine, on constructed
    fixtures (stub structures; no engine needed);
  * CONTRACT — the structural view and the move legality/no-mutation guarantees
    on a real mid-game board;
  * DETERMINISM — the same (seed, config) reproduces the same game byte for byte.
"""
from __future__ import annotations

import os
import random
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
PREP = REPO / "measurement" / "s0v2_scripted_prep"
sys.path.insert(0, str(PREP))

os.environ.setdefault("CARCASSONNE_FIX_R9", "1")

from s0v2_agent import (  # noqa: E402
    CLS_CITY, CLS_FARM, PlanConfig, PlanLedger, ScriptedExploiter, Structure,
    invasion_events, majority_events, merge_plausible, parse_overrides,
)


# --------------------------------------------------------------------------- #
# UNIT — the detector, on constructed fixtures                                  #
# --------------------------------------------------------------------------- #
class FakeStruct:
    """The slice of ``Structure`` that ``invasion_events`` reads.

    ``tiles`` maps component key -> tile count; ``counts`` key -> [w0, w1];
    ``members`` key -> meeple keys; ``of_meeple`` is derived."""

    def __init__(self, tiles, counts, members, pts=None, done=()):
        self.tiles = dict(tiles)
        self.counts = {k: list(v) for k, v in counts.items()}
        self.members = {k: list(v) for k, v in members.items()}
        self.pts = dict(pts or {})
        self.done = set(done)
        self.of_meeple = {m: k for k, ms in self.members.items() for m in ms}

    def n_tiles(self, key):
        return self.tiles[key]

    def potential_pts(self, key):
        return self.pts.get(key, 10)

    def finished(self, key):
        return key in self.done


# Meeple positional keys have the SEAT at index 0, exactly as Structure builds
# them: (player, row, col, side_name, meeple_type_name).
M_ME = (0, 0, 0, "TOP", "NORMAL")           # seat 0
M_ME3 = (0, 8, 8, "TOP", "NORMAL")          # seat 0, a second one
M_OP = (1, 1, 1, "TOP", "NORMAL")           # seat 1
M_OP2 = (1, 2, 2, "TOP", "NORMAL")          # seat 1, a second one


def _merge_fixture(my_tiles, opp_tiles):
    """Seat 0 holds a `my_tiles`-tile part, seat 1 an `opp_tiles`-tile part;
    the post ply has them in ONE component."""
    A, B = (CLS_CITY, 1), (CLS_CITY, 2)
    pre = FakeStruct(
        tiles={A: my_tiles, B: opp_tiles},
        counts={A: [1, 0], B: [0, 1]},
        members={A: [M_ME], B: [M_OP]},
    )
    P = (CLS_CITY, 9)
    post = FakeStruct(
        tiles={P: my_tiles + opp_tiles + 1},
        counts={P: [1, 1]},
        members={P: [M_ME, M_OP]},
        pts={P: 14},
    )
    return pre, post


def test_detector_finds_the_merge_and_names_the_smaller_side_invader():
    pre, post = _merge_fixture(my_tiles=2, opp_tiles=8)
    (ev,) = invasion_events(pre, post)
    assert ev["invader"] == 0 and ev["incumbent"] == 1
    assert ev["invader_tiles"] == 2 and ev["incumbent_tiles"] == 8
    assert ev["victim_pts"] == 14
    assert ev["stub_meeples"] == [M_ME]


def test_detector_names_the_opponent_invader_when_i_am_the_big_side():
    pre, post = _merge_fixture(my_tiles=9, opp_tiles=3)
    (ev,) = invasion_events(pre, post)
    assert ev["invader"] == 1 and ev["incumbent"] == 0


def test_detector_skips_merge_equal():
    """stage_a_census sets invader=None on a tile-count tie (`merge_equal`), so
    s0_signature never counts it — the detector must agree."""
    pre, post = _merge_fixture(my_tiles=5, opp_tiles=5)
    assert invasion_events(pre, post) == []


def test_detector_skips_a_feature_that_was_already_contested():
    """Components only grow, so a feature contested earlier still has both seats
    in ONE pre-part — which is the census's `contested_seen` skip."""
    A = (CLS_CITY, 1)
    pre = FakeStruct(tiles={A: 6}, counts={A: [1, 1]}, members={A: [M_ME, M_OP]})
    P = (CLS_CITY, 9)
    post = FakeStruct(tiles={P: 7}, counts={P: [1, 1]}, members={P: [M_ME, M_OP]})
    assert invasion_events(pre, post) == []


def test_detector_needs_two_occupied_pre_parts():
    A = (CLS_CITY, 1)
    pre = FakeStruct(tiles={A: 4}, counts={A: [1, 0]}, members={A: [M_ME]})
    P = (CLS_CITY, 9)
    # the opponent's meeple has no pre-component (e.g. a cloister) -> one part
    post = FakeStruct(tiles={P: 5}, counts={P: [1, 1]}, members={P: [M_ME, M_OP]})
    assert invasion_events(pre, post) == []


def test_detector_sums_tiles_across_several_parts_per_side():
    A, B, C = (CLS_FARM, 1), (CLS_FARM, 2), (CLS_FARM, 3)
    pre = FakeStruct(
        tiles={A: 2, B: 2, C: 9},
        counts={A: [1, 0], B: [1, 0], C: [0, 1]},
        members={A: [M_ME], B: [(0, 5, 5, "TOP_LEFT", "FARMER")], C: [M_OP]},
    )
    P = (CLS_FARM, 9)
    post = FakeStruct(
        tiles={P: 14},
        counts={P: [2, 1]},
        members={P: [M_ME, (0, 5, 5, "TOP_LEFT", "FARMER"), M_OP]},
        pts={P: 12},
    )
    (ev,) = invasion_events(pre, post)
    assert ev["invader"] == 0
    assert ev["invader_tiles"] == 4 and ev["incumbent_tiles"] == 9
    assert sorted(ev["stub_meeples"]) == sorted([M_ME, (0, 5, 5, "TOP_LEFT", "FARMER")])


def test_detector_ignores_two_parts_of_the_same_seat():
    A, B = (CLS_CITY, 1), (CLS_CITY, 2)
    pre = FakeStruct(tiles={A: 2, B: 7}, counts={A: [1, 0], B: [1, 0]},
                     members={A: [M_ME], B: [M_ME3]})
    P = (CLS_CITY, 9)
    post = FakeStruct(tiles={P: 10}, counts={P: [2, 0]}, members={P: [M_ME, M_ME3]})
    assert invasion_events(pre, post) == []


# --------------------------------------------------------------------------- #
# UNIT — the MAJORITY detector (amendment 2026-08-28)                           #
# --------------------------------------------------------------------------- #
M_ME2 = (0, 7, 7, "TOP_LEFT", "FARMER")     # seat 0, a farmer


def test_majority_converts_a_tie_into_a_strict_majority():
    """The conversion the amendment exists for: a 1-v-1 `shared_tie` component
    plus a second owned part merges to 2-v-1."""
    T, S = (CLS_FARM, 1), (CLS_FARM, 2)          # tied component, my spare stub
    pre = FakeStruct(tiles={T: 9, S: 2},
                     counts={T: [1, 1], S: [1, 0]},
                     members={T: [M_ME, M_OP], S: [M_ME2]})
    P = (CLS_FARM, 9)
    post = FakeStruct(tiles={P: 12}, counts={P: [2, 1]},
                      members={P: [M_ME, M_OP, M_ME2]}, pts={P: 12})
    (ev,) = majority_events(pre, post, me=0)
    assert ev["from_tie"] is True
    assert ev["me_after"] == 2 and ev["opp_after"] == 1
    assert ev["victim_pts"] == 12
    assert sorted(ev["my_meeples"]) == sorted([M_ME, M_ME2])
    # ...and nothing for the opponent, who is now in the minority
    assert majority_events(pre, post, me=1) == []


def test_majority_also_fires_on_a_fresh_two_versus_one_landing():
    """Two of my parts and one of theirs join in the same ply: 2-v-1 with no
    contested pre-part.  Counted, and flagged from_tie=False because the census
    ALSO counts it as a deliberate invasion (the two counters overlap)."""
    A, B, C = (CLS_CITY, 1), (CLS_CITY, 2), (CLS_CITY, 3)
    pre = FakeStruct(tiles={A: 1, B: 1, C: 8},
                     counts={A: [1, 0], B: [1, 0], C: [0, 1]},
                     members={A: [M_ME], B: [M_ME2], C: [M_OP]})
    P = (CLS_CITY, 9)
    post = FakeStruct(tiles={P: 11}, counts={P: [2, 1]},
                      members={P: [M_ME, M_ME2, M_OP]}, pts={P: 16})
    (ev,) = majority_events(pre, post, me=0)
    assert ev["from_tie"] is False and ev["me_after"] == 2


def test_majority_does_not_fire_when_i_already_held_the_majority():
    T, S = (CLS_FARM, 1), (CLS_FARM, 2)
    pre = FakeStruct(tiles={T: 9, S: 2},
                     counts={T: [2, 1], S: [1, 0]},
                     members={T: [M_ME, M_OP, M_ME2], S: [M_ME3]})
    P = (CLS_FARM, 9)
    post = FakeStruct(tiles={P: 12}, counts={P: [3, 1]},
                      members={P: [M_ME, M_OP, M_ME2, M_ME3]})
    assert majority_events(pre, post, me=0) == []


def test_majority_needs_a_merge_not_just_a_lead():
    P = (CLS_FARM, 9)
    pre = FakeStruct(tiles={P: 12}, counts={P: [2, 1]}, members={P: [M_ME, M_ME2, M_OP]})
    post = FakeStruct(tiles={P: 13}, counts={P: [2, 1]}, members={P: [M_ME, M_ME2, M_OP]})
    assert majority_events(pre, post, me=0) == []


def test_majority_needs_the_opponent_still_present():
    """A component I hold alone is not a majority event — there is nobody to deny."""
    A, B = (CLS_CITY, 1), (CLS_CITY, 2)
    pre = FakeStruct(tiles={A: 2, B: 3}, counts={A: [1, 0], B: [1, 0]},
                     members={A: [M_ME], B: [M_ME2]})
    P = (CLS_CITY, 9)
    post = FakeStruct(tiles={P: 6}, counts={P: [2, 0]}, members={P: [M_ME, M_ME2]})
    assert majority_events(pre, post, me=0) == []


def test_a_merge_that_only_restores_a_tie_is_not_a_majority():
    """2-v-1 against me plus one of mine -> 2-v-2.  Better, but a tie still pays
    the incumbent in full, so it is not the event G-DAMAGE measures."""
    T, S = (CLS_FARM, 1), (CLS_FARM, 2)
    pre = FakeStruct(tiles={T: 9, S: 2}, counts={T: [1, 2], S: [1, 0]},
                     members={T: [M_ME, M_OP, M_OP2], S: [M_ME2]})
    P = (CLS_FARM, 9)
    post = FakeStruct(tiles={P: 12}, counts={P: [2, 2]},
                      members={P: [M_ME, M_OP, M_OP2, M_ME2]})
    assert majority_events(pre, post, me=0) == []


def test_majority_targets_are_contested_components_i_am_not_ahead_on():
    cfg = PlanConfig(majority_min_pts=4)
    keys = {"tied": (CLS_FARM, 1), "behind": (CLS_FARM, 2), "ahead": (CLS_FARM, 3),
            "mine": (CLS_FARM, 4), "theirs": (CLS_FARM, 5), "cheap": (CLS_FARM, 6),
            "done": (CLS_CITY, 7)}
    s = FakeStruct(
        tiles={k: 6 for k in keys.values()},
        counts={keys["tied"]: [1, 1], keys["behind"]: [1, 2], keys["ahead"]: [2, 1],
                keys["mine"]: [1, 0], keys["theirs"]: [0, 1], keys["cheap"]: [1, 1],
                keys["done"]: [1, 1]},
        members={k: [] for k in keys.values()},
        pts={k: 10 for k in keys.values()} | {keys["cheap"]: 2},
        done={keys["done"]})
    got = set(Structure.majority_targets(s, 0, cfg))
    assert got == {keys["tied"], keys["behind"]}


# --------------------------------------------------------------------------- #
# UNIT — the plan state machine                                                 #
# --------------------------------------------------------------------------- #
class FakeLedgerStruct:
    def __init__(self, of_meeple):
        self.of_meeple = dict(of_meeple)


def _ledger_with_one_plan():
    led = PlanLedger()
    p = led.start(ply=10, cls=CLS_FARM, stub_meeple=M_ME, victim_meeple=M_OP,
                  victim_tiles=9, victim_pts=12)
    return led, p


def test_plan_completes_when_its_foothold_meeple_takes_part_in_a_merge():
    led, p = _ledger_with_one_plan()
    hit = led.complete(ply=22, stub_meeples=[M_ME])
    assert [x.pid for x in hit] == [p.pid]
    assert p.status == "completed" and p.closed_ply == 22 and p.reason == "merged"
    assert led.summary() | {"plans_started": 1, "plans_completed": 1,
                            "plans_abandoned": 0, "plans_open_at_end": 0,
                            "plan_completion_rate": 1.0} == led.summary()


def test_a_merge_by_another_meeple_does_not_complete_the_plan():
    led, p = _ledger_with_one_plan()
    assert led.complete(ply=22, stub_meeples=[M_OP2]) == []
    assert p.status == "open"


def test_plan_is_abandoned_when_the_foothold_meeple_comes_back():
    led, p = _ledger_with_one_plan()
    led.refresh(ply=30, struct=FakeLedgerStruct({M_OP: (CLS_FARM, 3)}), me=0)
    assert p.status == "abandoned" and p.reason == "stub_gone" and p.closed_ply == 30


def test_plan_is_abandoned_when_the_victim_meeple_is_gone():
    led, p = _ledger_with_one_plan()
    led.refresh(ply=31, struct=FakeLedgerStruct({M_ME: (CLS_FARM, 1)}), me=0)
    assert p.status == "abandoned" and p.reason == "victim_gone"


def test_plan_is_abandoned_when_something_else_merged_the_two():
    led, p = _ledger_with_one_plan()
    led.refresh(ply=32, struct=FakeLedgerStruct({M_ME: (CLS_FARM, 7),
                                                 M_OP: (CLS_FARM, 7)}), me=0)
    assert p.status == "abandoned" and p.reason == "merged_not_by_plan"
    s = led.summary()
    assert s["plans_completed"] == 0 and s["plan_completion_rate"] == 0.0


def test_refresh_leaves_a_live_plan_open():
    led, p = _ledger_with_one_plan()
    led.refresh(ply=33, struct=FakeLedgerStruct({M_ME: (CLS_FARM, 1),
                                                 M_OP: (CLS_FARM, 3)}), me=0)
    assert p.status == "open"


def test_summary_of_an_empty_ledger_has_no_rate():
    s = PlanLedger().summary()
    assert s["plan_completion_rate"] is None
    assert s["reinforce_plan_completion_rate"] is None


def test_ledger_splits_invade_and_reinforce_plans():
    led = PlanLedger()
    a = led.start(1, CLS_FARM, M_ME, M_OP, 9, 12, kind="invade")
    b = led.start(2, CLS_FARM, M_ME2, M_OP, 9, 12, kind="reinforce")
    assert [p.pid for p in led.open_of_kind("reinforce")] == [b.pid]
    led.complete(ply=5, stub_meeples=[M_ME2])
    s = led.summary()
    assert s["invade_plans_started"] == 1 and s["invade_plans_completed"] == 0
    assert s["reinforce_plans_started"] == 1 and s["reinforce_plans_completed"] == 1
    assert s["reinforce_plan_completion_rate"] == 1.0
    assert a.status == "open" and b.status == "completed"
    assert led.open_of_kind("reinforce") == []


# --------------------------------------------------------------------------- #
# CONTRACT — on a real mid-game board                                           #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def midgame():
    """A deterministic ~70-ply random position, its Game and Board."""
    from carcassonne_ai import rules_profile as RP
    from carcassonne_ai.game_wrapper import Game

    RP.activate("fixed_v1")
    random.seed(20260828)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    for _ in range(70):
        if game.get_game_ended(board, 0) != 0.0:
            break
        idxs = np.flatnonzero(game.get_valid_moves(board))
        board, _ = game.get_next_state(board, int(random.choice(idxs)))
    return game, board


def test_structure_meeple_index_agrees_with_the_production_leaf(midgame):
    """Every placed non-cloister meeple must land on exactly one component, and
    the per-component weights must sum to the number of such meeples."""
    from carcassonne_ai import flat_leaf
    from wingedsheep.carcassonne.objects.terrain_type import TerrainType

    _, board = midgame
    st = board.state
    s = Structure(st)
    n_non_cloister = 0
    for p in range(st.players):
        for mp in st.placed_meeples[p]:
            cws = mp.coordinate_with_side
            tile = st.board[cws.coordinate.row][cws.coordinate.column]
            if tile.get_type(cws.side) not in (TerrainType.CHAPEL, TerrainType.FLOWERS):
                n_non_cloister += 1
    assert n_non_cloister > 0
    assert sum(sum(c) for c in s.counts.values()) == n_non_cloister
    # component identity is per-class: no key is shared between classes
    assert len({k for k in s.counts}) == len(s.counts)
    # every component with a meeple has at least one tile and a point value
    for k in s.counts:
        assert s.n_tiles(k) >= 1
        assert s.potential_pts(k) >= 0
    # the flat leaf agrees the position is scoreable (kernel is the same one)
    assert isinstance(flat_leaf.flat_virtual_score_v2_float(st, 0), float)


def test_adj_empty_and_merge_plausible_are_geometric(midgame):
    _, board = midgame
    st = board.state
    s = Structure(st)
    keys = list(s.counts)
    for k in keys:
        for (r, c) in s.adj_empty(k):
            assert st.board[r][c] is None
    # merge_plausible is symmetric and false across classes
    for a in keys:
        for b in keys:
            assert merge_plausible(s, a, b) == merge_plausible(s, b, a)
            if a[0] != b[0]:
                assert not merge_plausible(s, a, b)


def test_get_next_state_does_not_mutate_the_parent(midgame):
    """The plan module evaluates every candidate child off ONE parent board;
    if `get_next_state` aliased the parent's structures this would corrupt it."""
    game, board = midgame
    s_before = Structure(board.state)
    before = (sorted(map(sorted, s_before.decomp.city_root_coords.values())),
              sorted(map(sorted, s_before.decomp.road_root_coords.values())),
              len(s_before.decomp.farm_anypos_root))
    for a in np.flatnonzero(game.get_valid_moves(board)):
        game.get_next_state(board, int(a))
    s_after = Structure(board.state)
    after = (sorted(map(sorted, s_after.decomp.city_root_coords.values())),
             sorted(map(sorted, s_after.decomp.road_root_coords.values())),
             len(s_after.decomp.farm_anypos_root))
    assert before == after


def test_every_move_the_agent_returns_is_legal_and_it_finishes_a_game():
    from s0v2_devplay import RULES_PROFILE, GreedyLeafAgent
    from carcassonne_ai import rules_profile as RP
    from carcassonne_ai.game_wrapper import Game

    RP.activate(RULES_PROFILE)
    random.seed(31337)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    cfg = PlanConfig()
    ex = ScriptedExploiter(GreedyLeafAgent(game), game, cfg, label="test")
    opp = GreedyLeafAgent(game)
    n = 0
    while game.get_game_ended(board, 0) == 0.0:
        legal = set(int(i) for i in np.flatnonzero(game.get_valid_moves(board)))
        a = ex.move(board) if board.state.current_player == 0 else opp.move(board)
        assert a in legal, f"illegal action {a} at ply {n}"
        board, _ = game.get_next_state(board, a)
        ex.advance(a)
        n += 1
    assert n > 100
    tel = ex.telemetry()
    assert tel["plies_seen"] > 0
    assert (tel["base_moves"] + tel["merge_fires"] + tel["setup_fires"]
            + tel["foothold_fires"] + tel["majority_fires"]
            + tel["reinforce_foothold_fires"]) >= tel["plies_seen"]


# --------------------------------------------------------------------------- #
# DETERMINISM                                                                   #
# --------------------------------------------------------------------------- #
def _dev_game(seed, a_seat, cfg):
    from carcassonne_ai import rules_profile as RP
    import s0v2_devplay as D

    RP.activate(D.RULES_PROFILE)
    return D.play_one(seed, a_seat, cfg)


def test_the_same_seed_and_config_reproduce_the_game_exactly():
    cfg = PlanConfig()
    a = _dev_game(555001, 0, cfg)
    b = _dev_game(555001, 0, cfg)
    assert a["actions"] == b["actions"]
    assert a["scores"] == b["scores"]
    assert a["s0v2"]["telemetry"]["merge_fires"] == b["s0v2"]["telemetry"]["merge_fires"]
    assert [f["action"] for f in a["s0v2"]["fires"]] == \
           [f["action"] for f in b["s0v2"]["fires"]]
    assert [(p["pid"], p["status"]) for p in a["s0v2"]["plans"]] == \
           [(p["pid"], p["status"]) for p in b["s0v2"]["plans"]]


def test_majority_on_is_deterministic_and_legal():
    from s0v2_devplay import RULES_PROFILE, GreedyLeafAgent
    from carcassonne_ai import rules_profile as RP
    from carcassonne_ai.game_wrapper import Game

    cfg = PlanConfig(victim_min_pts=3, victim_min_tiles=4, stub_max_tiles=6,
                     majority_enabled=True, reinforce_enabled=True)
    a = _dev_game(555004, 0, cfg)
    b = _dev_game(555004, 0, cfg)
    assert a["actions"] == b["actions"]
    assert a["s0v2"]["telemetry"]["majority_fires"] == \
        b["s0v2"]["telemetry"]["majority_fires"]

    RP.activate(RULES_PROFILE)
    random.seed(4242)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    ex = ScriptedExploiter(GreedyLeafAgent(game), game, cfg, label="maj")
    opp = GreedyLeafAgent(game)
    while game.get_game_ended(board, 0) == 0.0:
        legal = set(int(i) for i in np.flatnonzero(game.get_valid_moves(board)))
        act = ex.move(board) if board.state.current_player == 0 else opp.move(board)
        assert act in legal
        board, _ = game.get_next_state(board, act)
        ex.advance(act)
    tel = ex.telemetry()
    assert tel["meeples_spent_on_reinforcement"] == tel["reinforce_foothold_fires"]
    assert tel["reinforce_plans_started"] == tel["reinforce_foothold_fires"]


def test_majority_off_is_the_previous_agent_exactly():
    """The amendment must be a pure ADDITION: with the new fire off, the agent
    reproduces the arm the 2026-08-28 smoke ran, move for move."""
    base = dict(victim_min_pts=3, victim_min_tiles=4, stub_max_tiles=6)
    off = _dev_game(555005, 0, PlanConfig(**base, majority_enabled=False,
                                          reinforce_enabled=False))
    assert off["s0v2"]["telemetry"]["majority_fires"] == 0
    assert off["s0v2"]["telemetry"]["reinforce_foothold_fires"] == 0
    assert off["s0v2"]["telemetry"]["meeples_spent_on_reinforcement"] == 0


def test_disabling_every_fire_reproduces_the_base_agent_exactly():
    """The plan module must be a pure OVERRIDE: with all four fires off, the
    wrapped agent plays the base agent's game move for move."""
    off = PlanConfig(merge_enabled=False, foothold_enabled=False,
                     setup_enabled=False, majority_enabled=False,
                     reinforce_enabled=False)
    a = _dev_game(555002, 0, off)
    assert a["s0v2"]["telemetry"]["merge_fires"] == 0
    assert a["s0v2"]["telemetry"]["setup_fires"] == 0
    assert a["s0v2"]["telemetry"]["foothold_fires"] == 0
    assert a["s0v2"]["telemetry"]["base_moves"] == a["s0v2"]["telemetry"]["plies_seen"]


def test_a_different_config_changes_the_game():
    """Sanity: the knobs are actually wired to behaviour."""
    on = _dev_game(555003, 0, PlanConfig())
    off = _dev_game(555003, 0, PlanConfig(merge_enabled=False,
                                          foothold_enabled=False,
                                          setup_enabled=False,
                                          majority_enabled=False,
                                          reinforce_enabled=False))
    assert on["s0v2"]["telemetry"]["plies_seen"] > 0
    fired = (on["s0v2"]["telemetry"]["merge_fires"]
             + on["s0v2"]["telemetry"]["setup_fires"]
             + on["s0v2"]["telemetry"]["foothold_fires"]
             + on["s0v2"]["telemetry"]["majority_fires"])
    if fired:
        assert on["actions"] != off["actions"]


# --------------------------------------------------------------------------- #
# config plumbing                                                               #
# --------------------------------------------------------------------------- #
def test_parse_overrides_types_and_rejects_typos():
    c = parse_overrides(["stub_max_tiles=7", "setup_enabled=false",
                         "min_visit_share=0.35"])
    assert c.stub_max_tiles == 7 and c.setup_enabled is False
    assert c.min_visit_share == pytest.approx(0.35)
    with pytest.raises(ValueError):
        parse_overrides(["stub_max_tilez=7"])
    with pytest.raises(ValueError):
        parse_overrides(["stub_max_tiles"])


def test_plan_config_is_frozen_and_serialises():
    c = PlanConfig()
    with pytest.raises(Exception):
        c.stub_max_tiles = 99          # type: ignore[misc]
    d = c.as_dict()
    assert d["stub_max_tiles"] == c.stub_max_tiles
    assert PlanConfig(**d) == c
