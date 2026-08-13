"""Joshua-bot (``carcassonne_ai.joshua_bot``) — one test class per J-rule.

The contract this file defends is stated in
``measurement/joshuabot_20260812/SPEC.md``: every rule of the 2026-08-12 anchor
interview has a named symbol, and each symbol fires exactly where the interview
says it should and NOT where it does not. Most rule tests run against a synthetic
:class:`~carcassonne_ai.joshua_bot.Position` — a hand-built decomposition — so the
rule is isolated from the search, the leaf and the engine. The last two classes
close the loop on real games (fair-information invariance, determinism, legality).
"""
from __future__ import annotations

import random

import pytest

from carcassonne_ai.flat_leaf import Decomp
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.joshua_bot import (
    PRESETS,
    Clock,
    JoshuaBot,
    JoshuaParams,
    Position,
    _Cand,
    bag_farm_fraction,
    farm_total_value,
    j1_majority_steal,
    j2_farm_attack,
    j2_reach,
    j4_urgency,
    j5_dump,
    j6_anchor_and_roads,
    j7_close_vs_farm,
    j8_overcommit,
    remaining_tiles,
    surrounding_count,
    with_overrides,
)
from carcassonne_ai.rule_based_player import RuleBasedPlayer

ME, OPP = 0, 1
P = PRESETS["current"]


# --------------------------------------------------------------------------- #
# synthetic-position builders                                                  #
# --------------------------------------------------------------------------- #
class _FakeTile:
    """Just enough tile for the board-shaped helpers (no cloister)."""
    farms = ()

    def get_type(self, side):            # noqa: ARG002 — never a cloister
        return None


class _FakeState:
    """A board grid + the fields the board-shaped helpers read. Nothing else of a
    CarcassonneGameState is touched by the rule functions under test."""

    def __init__(self, filled=(), size=6, players=2):
        self.board = [[None] * size for _ in range(size)]
        self.placed_coords = set()
        for (r, c) in filled:
            self.board[r][c] = _FakeTile()
        self.players = players


def _decomp(**kw) -> Decomp:
    """A Decomp with every field defaulted to empty; pass only what matters."""
    base = dict(
        city_side_root={}, city_root_positions={}, city_root_coords={},
        city_root_finished={}, city_root_open_n={}, city_root_delta={},
        road_side_root={}, road_root_positions={}, road_root_coords={},
        road_root_finished={}, road_root_open_n={},
        farm_pos0_root={}, farm_anypos_root={}, farm_root_keys={},
        farm_root_adj_city_roots={}, farm_root_finished_cities={},
    )
    base.update(kw)
    return Decomp(**base)


def _pos(decomp: Decomp, *, city=None, road=None, farm=None, cloister=None,
         state=None) -> Position:
    return Position(state=state if state is not None else _FakeState(),
                    decomp=decomp, city_counts=city or {}, road_counts=road or {},
                    farm_counts=farm or {}, cloister_owner=cloister or {})


def _clock(k=40, k0=72, bag=0.9, mine=4, his=4, margin=0.0) -> Clock:
    return Clock(k=k, k0=k0, bag_farm_frac=bag, my_reserve=mine, opp_reserve=his,
                 margin=margin)


def _city(root, tiles, open_n, finished=False, delta=None):
    """One city component: `tiles` distinct coords, `open_n` empty adjacent cells."""
    coords = {(0, i) for i in range(tiles)}
    return dict(
        city_root_coords={root: coords},
        city_root_finished={root: finished},
        city_root_open_n={root: open_n},
        city_root_delta={root: tiles if delta is None else delta},
    )


# --------------------------------------------------------------------------- #
# J1 — late majority-steal join into his large open cities                     #
# --------------------------------------------------------------------------- #
class TestJ1MajoritySteal:
    def _fire(self, counts, tiles=6, open_n=3, finished=False, clock=None,
              params=P):
        pos = _pos(_decomp(**_city(1, tiles, open_n, finished)), city={1: counts})
        clk = clock or _clock()
        return j1_majority_steal(pos, ME, clk, params, j4_urgency(clk, params))

    def test_fires_on_a_tie_in_his_big_open_city(self):
        assert self._fire([1, 1]) > 0.0

    def test_fires_on_a_majority_too(self):
        assert self._fire([2, 1]) > 0.0

    def test_silent_when_the_city_is_too_small(self):
        assert self._fire([1, 1], tiles=P.j1_min_city_tiles - 1) == 0.0

    def test_silent_when_the_city_is_nearly_closed(self):
        assert self._fire([1, 1], open_n=P.j1_min_open_edges - 1) == 0.0

    def test_silent_on_a_finished_city(self):
        assert self._fire([1, 1], finished=True) == 0.0

    def test_silent_when_it_is_not_HIS_city(self):
        """A solo claim of a big open city is not a STEAL — J1 is about joining
        an investment he already made."""
        assert self._fire([1, 0]) == 0.0

    def test_silent_when_i_am_still_behind_on_the_feature(self):
        assert self._fire([1, 2]) == 0.0

    def test_grows_as_the_game_gets_late(self):
        early = self._fire([1, 1], clock=_clock(k=60, k0=72))
        late = self._fire([1, 1], clock=_clock(k=6, k0=72))
        assert late > early > 0.0

    def test_relaxes_when_he_has_no_meeples_left(self):
        """J4 conditioning: the same join is worth less when he cannot answer."""
        full = self._fire([1, 1], clock=_clock(his=4))
        empty = self._fire([1, 1], clock=_clock(his=0))
        assert 0.0 < empty < full


# --------------------------------------------------------------------------- #
# J2 — deck-counted farm tie/steal planned 2-4 tiles ahead                     #
# --------------------------------------------------------------------------- #
def _farm_setup(*, adj_cities=2, finished_cities=0, open_n=1, field=((2, 2),)):
    """One field (root 10) touching `adj_cities` cities, `finished_cities` of them
    already closed; the rest closable (open_n <= j2_city_close_open_max)."""
    city_coords, city_fin, city_open, city_delta = {}, {}, {}, {}
    roots = []
    for i in range(adj_cities):
        r = 100 + i
        roots.append(r)
        city_coords[r] = {(9, i)}
        city_fin[r] = i < finished_cities
        city_open[r] = open_n
        city_delta[r] = 4
    d = _decomp(
        city_root_coords=city_coords, city_root_finished=city_fin,
        city_root_open_n=city_open, city_root_delta=city_delta,
        farm_root_keys={10: frozenset((r, c, 0) for (r, c) in field)},
        farm_root_adj_city_roots={10: frozenset(roots)},
        farm_root_finished_cities={10: finished_cities},
    )
    return d


class TestJ2FarmAttack:
    #: the "current" preset only counts unclosed-city potential once the bag is
    #: down to j2_city_count_from_k, so the default clock here is a LATE one.
    LATE = P.j2_city_count_from_k - 10

    def _fire(self, counts, params=P, clock=None, d=None, state=None):
        pos = _pos(d if d is not None else _farm_setup(), farm={10: counts},
                   state=state or _FakeState(filled=[(2, 2)]))
        clk = clock or _clock(k=self.LATE)
        return j2_farm_attack(pos, ME, clk, params, j4_urgency(clk, params))

    def test_tie_on_his_valuable_field_pays(self):
        assert self._fire([1, 1]) > 0.0

    def test_steal_pays(self):
        assert self._fire([2, 1]) > 0.0

    def test_silent_when_i_am_behind_on_the_field(self):
        assert self._fire([1, 2]) <= 0.0

    def test_current_preset_counts_city_potential_only_late(self):
        """J10 — 'i started to count the cities, especially late in game'.

        Early, the same field reads as worth nothing (its cities are not closed
        yet and 'current' does not count them yet), so the tie pays nothing and
        the SURRENDER bar even charges for the farmer sitting there. Late, the
        identical field pays."""
        early_clock = _clock(k=P.j2_city_count_from_k + 10)
        late_clock = _clock(k=P.j2_city_count_from_k - 10)
        assert self._fire([1, 1], clock=early_clock) <= 0.0
        assert self._fire([1, 1], clock=late_clock) > self._fire([1, 1],
                                                                 clock=early_clock)

    def test_early_preset_counts_city_potential_at_any_point(self):
        e = PRESETS["early"]
        assert self._fire([1, 1], params=e,
                          clock=_clock(k=P.j2_city_count_from_k + 10)) > 0.0

    def test_current_preset_surrenders_a_worthless_field(self):
        """A field touching nothing closable is worth 0 -> 'current' charges the
        farmer sitting on it; 'early' (no surrender bar) does not."""
        barren = _farm_setup(adj_cities=1, open_n=99)     # nothing closable
        assert self._fire([1, 0], d=barren) < 0.0
        assert self._fire([1, 0], d=barren, params=PRESETS["early"]) == 0.0

    def test_approach_bonus_rewards_a_field_i_can_still_get_into(self):
        """His valuable field, mine empty, way in still open -> a positive pull
        (this is the '2-4 tiles in advance' steering)."""
        late = _clock(k=P.j2_city_count_from_k - 10)
        assert self._fire([0, 1], clock=late) > 0.0

    def test_no_approach_bonus_once_there_is_no_way_in(self):
        """Field fully surrounded: reach == 0, so the plan is off."""
        walled = _FakeState(filled=[(2, 2), (1, 2), (3, 2), (2, 1), (2, 3)])
        late = _clock(k=P.j2_city_count_from_k - 10)
        assert self._fire([0, 1], clock=late, state=walled) == 0.0


class TestJ2Reach:
    """The deck-counted planning test itself."""

    def _pos(self, filled=((2, 2),)):
        return _pos(_farm_setup(), farm={10: [0, 1]},
                    state=_FakeState(filled=list(filled)))

    def test_zero_when_no_turns_remain(self):
        assert j2_reach(self._pos(), 10, _clock(k=1), P) == 0.0

    def test_zero_when_the_field_is_sealed_in(self):
        sealed = self._pos(filled=[(2, 2), (1, 2), (3, 2), (2, 1), (2, 3)])
        assert j2_reach(sealed, 10, _clock(k=40), P) == 0.0

    def test_zero_when_the_bag_holds_no_field_tiles(self):
        assert j2_reach(self._pos(), 10, _clock(k=40, bag=0.0), P) == 0.0

    def test_rises_with_the_planning_horizon(self):
        short = with_overrides("current", j2_plan_horizon=1)
        long_ = with_overrides("current", j2_plan_horizon=4)
        clk = _clock(k=40, bag=0.5)
        assert j2_reach(self._pos(), 10, clk, long_) > j2_reach(self._pos(), 10, clk, short)


# --------------------------------------------------------------------------- #
# J3 / F-END — the reserve floor and the endgame release                       #
# --------------------------------------------------------------------------- #
def _cand(action, score=0.0, place=False, farmer=False, closes=False, swing=False,
          cloister=False, cloister_strong=False, pivotal=False):
    return _Cand(action=action, score=score, terms={}, after=_pos(_decomp()),
                 is_meeple_place=place, is_farmer=farmer, closes_own=closes,
                 swings_majority=swing, is_cloister=cloister,
                 cloister_strong=cloister_strong, is_pivotal_overcommit=pivotal)


class TestJ3ReserveFloor:
    def _bot(self, params=P):
        bot = JoshuaBot.__new__(JoshuaBot)          # no Game needed for the filter
        bot.params = params
        bot.rule_fires = {}
        return bot

    def test_last_meeple_is_held_back(self):
        """'i try to keep at least 1 meeple in my hand.'"""
        bot = self._bot()
        cands = [_cand(0), _cand(1, place=True)]
        kept = bot._apply_filters(cands, _clock(k=40, mine=1))
        assert [c.action for c in kept] == [0]
        assert bot.rule_fires["f_j3_reserve_floor"] == 1

    def test_but_spent_on_a_closure_that_returns_it(self):
        bot = self._bot()
        cands = [_cand(0), _cand(1, place=True, closes=True)]
        assert {c.action for c in bot._apply_filters(cands, _clock(k=40, mine=1))} == {0, 1}

    def test_and_spent_on_a_majority_swing(self):
        bot = self._bot()
        cands = [_cand(0), _cand(1, place=True, swing=True)]
        assert {c.action for c in bot._apply_filters(cands, _clock(k=40, mine=1))} == {0, 1}

    def test_not_applied_when_the_reserve_is_healthy(self):
        bot = self._bot()
        cands = [_cand(0), _cand(1, place=True)]
        assert len(bot._apply_filters(cands, _clock(k=40, mine=4))) == 2

    def test_released_near_the_end_of_the_bag(self):
        bot = self._bot()
        cands = [_cand(0), _cand(1, place=True)]
        kept = bot._apply_filters(cands, _clock(k=P.j3_endgame_release_k, mine=1))
        assert len(kept) == 2

    def test_f_end_drops_the_pass_when_meeples_would_be_wasted(self):
        """k_remaining <= my reserve: every unplaced meeple is lost points, and
        F-END overrides J3."""
        bot = self._bot()
        cands = [_cand(0), _cand(1, place=True)]
        kept = bot._apply_filters(cands, _clock(k=2, mine=3))
        assert [c.action for c in kept] == [1]
        assert bot.rule_fires["f_end_deploy"] == 1

    def test_a_filter_that_would_empty_the_set_is_skipped(self):
        bot = self._bot()
        cands = [_cand(0, place=True)]              # only a placement is legal
        assert len(bot._apply_filters(cands, _clock(k=40, mine=1))) == 1


class TestJ10EarlyFarmerBlock:
    def _bot(self, preset):
        bot = JoshuaBot.__new__(JoshuaBot)
        bot.params = PRESETS[preset]
        bot.rule_fires = {}
        return bot

    def test_current_blocks_farmers_in_the_first_half(self):
        bot = self._bot("current")
        cands = [_cand(0), _cand(1, place=True, farmer=True)]
        kept = bot._apply_filters(cands, _clock(k=70, k0=72, mine=4))
        assert [c.action for c in kept] == [0]
        assert bot.rule_fires["f_j10_early_farm_block"] == 1

    def test_current_allows_farmers_later(self):
        bot = self._bot("current")
        cands = [_cand(0), _cand(1, place=True, farmer=True)]
        assert len(bot._apply_filters(cands, _clock(k=20, k0=72, mine=4))) == 2

    def test_early_preset_never_blocks(self):
        """'sometimes i lay down a farm early... i might challenge it right away.'"""
        bot = self._bot("early")
        cands = [_cand(0), _cand(1, place=True, farmer=True)]
        assert len(bot._apply_filters(cands, _clock(k=70, k0=72, mine=4))) == 2


class TestJ9CloisterCaution:
    """J9 — 'he is good at blocking my cloister completions. i'm more cautious
    about grabbing them now.' OPT-IN tournament axis, default OFF."""

    ON = with_overrides("current", j9_avoid_cloisters=True)

    def _bot(self, params):
        bot = JoshuaBot.__new__(JoshuaBot)
        bot.params = params
        bot.rule_fires = {}
        return bot

    def _cands(self, strong=False):
        return [_cand(0), _cand(1, place=True, cloister=True,
                                cloister_strong=strong)]

    def test_off_by_default(self):
        """The rule must not change the bot unless it is switched on."""
        bot = self._bot(P)
        assert len(bot._apply_filters(self._cands(), _clock(k=70, k0=72, mine=4))) == 2

    def test_on_blocks_an_early_speculative_cloister(self):
        bot = self._bot(self.ON)
        kept = bot._apply_filters(self._cands(), _clock(k=70, k0=72, mine=4))
        assert [c.action for c in kept] == [0]
        assert bot.rule_fires["f_j9_cloister_caution"] == 1

    def test_on_still_takes_a_cloister_with_strong_prospects(self):
        """'more cautious', not 'never' — a 3x3 that is already filling is fine."""
        bot = self._bot(self.ON)
        kept = bot._apply_filters(self._cands(strong=True),
                                  _clock(k=70, k0=72, mine=4))
        assert len(kept) == 2

    def test_on_stops_blocking_later_in_the_bag(self):
        bot = self._bot(self.ON)
        kept = bot._apply_filters(self._cands(), _clock(k=20, k0=72, mine=4))
        assert len(kept) == 2

    def test_threshold_knob_moves_the_cutoff(self):
        late_blocker = with_overrides("current", j9_avoid_cloisters=True,
                                      j9_cloister_block_frac=0.10)
        bot = self._bot(late_blocker)
        kept = bot._apply_filters(self._cands(), _clock(k=20, k0=72, mine=4))
        assert [c.action for c in kept] == [0]

    def test_a_cloister_only_set_is_never_emptied(self):
        bot = self._bot(self.ON)
        cands = [_cand(0, place=True, cloister=True)]
        assert len(bot._apply_filters(cands, _clock(k=70, k0=72, mine=4))) == 1

    def test_strength_is_read_off_the_3x3(self):
        """`surrounding_count` == flat_leaf's cloister points: placed tiles in the
        3x3 INCLUDING the centre."""
        st = _FakeState(filled=[(2, 2), (1, 1), (1, 2), (3, 3)], size=6)
        assert surrounding_count(st.board, 2, 2) == 4
        assert surrounding_count(_FakeState(filled=[(2, 2)]).board, 2, 2) == 1


class TestJ8BreakReserveFloor:
    """The J3-vs-J8 conflict axis: which rule wins at a thin reserve."""

    ON = with_overrides("current", j8_break_reserve_floor=True)

    def _bot(self, params):
        bot = JoshuaBot.__new__(JoshuaBot)
        bot.params = params
        bot.rule_fires = {}
        return bot

    def test_off_j3_refuses_the_overcommit(self):
        bot = self._bot(P)
        cands = [_cand(0), _cand(1, place=True, pivotal=True)]
        assert [c.action for c in bot._apply_filters(cands, _clock(k=40, mine=1))] == [0]

    def test_on_j8_takes_the_chance(self):
        bot = self._bot(self.ON)
        cands = [_cand(0), _cand(1, place=True, pivotal=True)]
        assert len(bot._apply_filters(cands, _clock(k=40, mine=1))) == 2

    def test_on_does_not_open_the_floor_to_ordinary_placements(self):
        """The exemption is for PIVOTAL overcommits only — everything else still
        respects the reserve floor."""
        bot = self._bot(self.ON)
        cands = [_cand(0), _cand(1, place=True)]
        assert [c.action for c in bot._apply_filters(cands, _clock(k=40, mine=1))] == [0]


# --------------------------------------------------------------------------- #
# J4 — opponent-reserve conditioning                                           #
# --------------------------------------------------------------------------- #
class TestJ4Urgency:
    def test_minimum_when_he_is_out_of_meeples(self):
        assert j4_urgency(_clock(his=0), P) == pytest.approx(P.j4_min_urgency)

    def test_full_when_his_reserve_is_deep(self):
        assert j4_urgency(_clock(his=P.j4_full_reserve + 3), P) == pytest.approx(1.0)

    def test_monotone_in_his_reserve(self):
        vals = [j4_urgency(_clock(his=r), P) for r in range(0, 8)]
        assert all(b >= a for a, b in zip(vals, vals[1:]))


# --------------------------------------------------------------------------- #
# J5 — value-starving throwaway placement                                      #
# --------------------------------------------------------------------------- #
class _StubPos(Position):
    """A Position whose base() is pinned, so J5's throwaway test is exercised
    without dragging a real leaf into the unit test."""

    def __init__(self, base_value, **kw):
        super().__init__(**kw)
        self._base = float(base_value)

    def base(self, player):              # noqa: ARG002
        return self._base


def _unclaimed_pos(base, city_tiles):
    d = _decomp(**_city(1, city_tiles, 2))
    return _StubPos(base, state=_FakeState(), decomp=d, city_counts={},
                    road_counts={}, farm_counts={}, cloister_owner={}, memo={})


class TestJ5ValueStarvingDump:
    def test_a_throwaway_that_feeds_a_juicy_unclaimed_city_is_charged(self):
        before = _unclaimed_pos(0.0, 6)
        after = _unclaimed_pos(0.0, 9)               # grew an UNCLAIMED 9-tile city
        assert j5_dump(before, after, ME, _clock(), P, 1.0) < 0.0

    def test_not_charged_when_the_placement_actually_scores(self):
        """'a throwaway tile' — a placement that pays is not a throwaway."""
        before = _unclaimed_pos(0.0, 6)
        after = _unclaimed_pos(P.j5_throwaway_gain + 5, 9)
        assert j5_dump(before, after, ME, _clock(), P, 1.0) == 0.0

    def test_not_charged_when_he_has_no_meeple_to_take_it_with(self):
        """'if he has meeple and i have a throwaway tile...' — J4 conditioning."""
        before = _unclaimed_pos(0.0, 6)
        after = _unclaimed_pos(0.0, 9)
        assert j5_dump(before, after, ME, _clock(his=0), P, 1.0) == 0.0

    def test_not_charged_below_the_few_points_floor(self):
        """'worth more than a few points' — small unclaimed features are free."""
        floor = int(P.j5_value_floor)
        before = _unclaimed_pos(0.0, 1)
        after = _unclaimed_pos(0.0, floor)          # still at/below the floor
        assert j5_dump(before, after, ME, _clock(), P, 1.0) == 0.0

    def test_a_dump_that_feeds_nothing_is_free(self):
        before = _unclaimed_pos(0.0, 9)
        after = _unclaimed_pos(0.0, 9)
        assert j5_dump(before, after, ME, _clock(), P, 1.0) == 0.0


# --------------------------------------------------------------------------- #
# J6 — anchor structure + road policy                                          #
# --------------------------------------------------------------------------- #
def _roads(**by_root):
    """by_root: root -> (length, finished)."""
    return _decomp(
        road_root_coords={r: {(0, i) for i in range(v[0])} for r, v in by_root.items()},
        road_root_finished={r: v[1] for r, v in by_root.items()},
        road_root_open_n={r: 1 for r in by_root},
    )


class TestJ6AnchorAndRoads:
    def test_holding_a_big_city_and_a_road_pays_the_anchor_bonus(self):
        d = _decomp(**_city(1, P.j6_anchor_city_min, 2))
        d.road_root_coords[2] = {(5, 0), (5, 1)}
        d.road_root_finished[2] = False
        pos = _pos(d, city={1: [1, 0]}, road={2: [1, 0]})
        assert j6_anchor_and_roads(pos, ME, _clock(), P, 1.0) == pytest.approx(
            2 * P.j6_anchor_bonus)

    def test_the_anchor_bonus_does_not_scale_with_more_of_the_same(self):
        """'ONE big city and ONE road' — a second city anchor pays nothing extra."""
        d = _decomp(city_root_coords={1: {(0, i) for i in range(4)},
                                      2: {(1, i) for i in range(4)}},
                    city_root_finished={1: False, 2: False},
                    city_root_open_n={1: 2, 2: 2},
                    city_root_delta={1: 4, 2: 4})
        pos = _pos(d, city={1: [1, 0], 2: [1, 0]})
        assert j6_anchor_and_roads(pos, ME, _clock(), P, 1.0) == pytest.approx(
            P.j6_anchor_bonus)

    def test_tying_his_long_road_pays(self):
        d = _roads(**{"7": (P.j6_road_join_min_len, False)})
        pos = _pos(d, road={"7": [1, 1]})
        got = j6_anchor_and_roads(pos, ME, _clock(), P, 1.0)
        assert got > 0.0

    def test_tying_a_short_road_does_not(self):
        d = _roads(**{"7": (P.j6_road_join_min_len - 1, False)})
        tie = j6_anchor_and_roads(_pos(d, road={"7": [1, 1]}), ME, _clock(), P, 1.0)
        assert tie == pytest.approx(0.0)

    def test_extra_short_solo_road_claims_are_charged(self):
        """'i'm generally less bullish on roads than him' — the anchor road is
        free, every further short solo road claim is not."""
        one = _roads(**{"1": (2, False)})
        two = _roads(**{"1": (2, False), "2": (2, False)})
        v1 = j6_anchor_and_roads(_pos(one, road={"1": [1, 0]}), ME, _clock(), P, 1.0)
        v2 = j6_anchor_and_roads(_pos(two, road={"1": [1, 0], "2": [1, 0]}),
                                 ME, _clock(), P, 1.0)
        assert v2 == pytest.approx(v1 - P.j6_road_claim_penalty)


# --------------------------------------------------------------------------- #
# J7 — closing a city he farms                                                 #
# --------------------------------------------------------------------------- #
def _close_setup(finished=True, farm_counts=(0, 1)):
    d = _decomp(**_city(1, 4, 0, finished=finished))
    d.farm_root_adj_city_roots[10] = frozenset({1})
    d.farm_root_finished_cities[10] = 1 if finished else 0
    d.farm_root_keys[10] = frozenset({(2, 2, 0)})
    return _pos(d, city={}, farm={10: list(farm_counts)})


class TestJ7CloseVersusFarm:
    def test_closing_a_city_he_farms_is_discounted(self):
        """'i hesistate if I've already surrendered the farm to him because he
        gets an easy 3 points there.'"""
        assert j7_close_vs_farm(_close_setup(), ME, P) == pytest.approx(
            -P.j7_weight * P.j7_points_per_field)

    def test_no_discount_while_the_city_is_still_open(self):
        assert j7_close_vs_farm(_close_setup(finished=False), ME, P) == 0.0

    def test_no_discount_when_the_field_is_not_his(self):
        assert j7_close_vs_farm(_close_setup(farm_counts=(1, 0)), ME, P) == 0.0
        assert j7_close_vs_farm(_close_setup(farm_counts=(1, 1)), ME, P) == 0.0

    def test_no_discount_on_a_city_i_own(self):
        pos = _close_setup()
        pos.city_counts[1] = [1, 0]
        assert j7_close_vs_farm(pos, ME, P) == 0.0

    def test_weight_zero_recovers_the_naive_count(self):
        naive = with_overrides("current", j7_weight=0.0)
        assert j7_close_vs_farm(_close_setup(), ME, naive) == 0.0


# --------------------------------------------------------------------------- #
# J8 — pivotal-feature overcommit                                              #
# --------------------------------------------------------------------------- #
class TestJ8Overcommit:
    def _fire(self, counts, tiles=8, open_n=2, params=P, clock=None):
        pos = _pos(_decomp(**_city(1, tiles, open_n)), city={1: counts})
        clk = clock or _clock()
        return j8_overcommit(pos, ME, clk, params, 1.0)

    def test_two_meeples_on_a_pivotal_open_city_pays(self):
        """'sometimes it takes 2 meeple to secure a city.'"""
        assert self._fire([2, 0]) > 0.0

    def test_a_single_meeple_is_not_an_overcommit(self):
        assert self._fire([1, 0]) == 0.0

    def test_nothing_for_a_feature_too_small_to_decide_the_game(self):
        small = int(P.j8_pivotal_swing // 2) - 1
        assert self._fire([2, 0], tiles=small) == 0.0

    def test_nothing_once_he_can_no_longer_get_in(self):
        assert self._fire([2, 0], open_n=0) == 0.0

    def test_nothing_past_the_meeple_cap(self):
        assert self._fire([P.j8_max_city_meeples + 1, 0]) == 0.0

    def test_nothing_when_the_game_is_not_close(self):
        """'the game will turn on a single large feature' — if the margin already
        dwarfs the feature, it decides nothing."""
        assert self._fire([2, 0], clock=_clock(margin=500.0)) == 0.0

    def test_a_field_gets_three(self):
        """'sometimes 3 for a single farm.'"""
        d = _farm_setup(adj_cities=4, finished_cities=4)
        pos = _pos(d, farm={10: [3, 0]}, state=_FakeState(filled=[(2, 2)]))
        assert j8_overcommit(pos, ME, _clock(), P, 1.0) > 0.0
        pos4 = _pos(d, farm={10: [P.j8_max_farm_meeples + 1, 0]},
                    state=_FakeState(filled=[(2, 2)]))
        assert j8_overcommit(pos4, ME, _clock(), P, 1.0) == 0.0


# --------------------------------------------------------------------------- #
# fair information — the hard contract                                         #
# --------------------------------------------------------------------------- #
class TestFairInformation:
    def test_remaining_tiles_is_a_multiset_sorted_by_description(self):
        random.seed(31)
        game = Game(enable_legal_moves_cache=True)
        board = game.get_init_board()
        a = remaining_tiles(board.state)
        descs = [d for d, _t, _n in a]
        assert descs == sorted(descs)                       # order destroyed
        assert sum(n for _d, _t, n in a) == len(board.state.deck)

    def test_remaining_tiles_ignores_draw_order(self):
        random.seed(31)
        game = Game(enable_legal_moves_cache=True)
        board = game.get_init_board()
        before = remaining_tiles(board.state)
        rng = random.Random(9)
        rng.shuffle(board.state.deck)
        assert remaining_tiles(board.state) == before
        assert bag_farm_fraction(board.state) == pytest.approx(
            bag_farm_fraction(board.state))

    def test_deck_permutation_invariance(self):
        """THE fair-information test: permuting the UNDRAWN deck must not move a
        single decision. Draw order is hidden information; the multiset is not."""
        random.seed(77)
        game = Game(enable_legal_moves_cache=True)
        board = game.get_init_board()
        bot = JoshuaBot(game, preset="current")
        rb = RuleBasedPlayer(seed=3)
        rng = random.Random(4242)
        checked = 0
        for _ in range(40):
            if game.get_game_ended(board, 0) != 0.0:
                break
            seat = board.state.current_player
            if seat == 0:
                a = bot.choose_action(board)
                shuffled = list(board.state.deck)
                rng.shuffle(shuffled)
                board.state.deck = shuffled
                assert JoshuaBot(game, preset="current").choose_action(board) == a
                checked += 1
            else:
                a = rb.choose_action(game, board, game.get_valid_moves(board))
            board, _ = game.get_next_state(board, int(a))
        assert checked >= 5


# --------------------------------------------------------------------------- #
# agent-level contract: determinism, harness fit, full games                   #
# --------------------------------------------------------------------------- #
class TestAgentContract:
    def test_play_harness_telemetry_surface(self):
        """It must drop into ``scripts/human_anchor/play_harness.play_game``
        untouched: the snapshot attributes exist and it is not mirror-seated."""
        from carcassonne_ai import mirror_protocol as MP

        game = Game(enable_legal_moves_cache=True)
        bot = JoshuaBot(game)
        for attr in ("latch_k", "heur_moves", "exact_moves", "n_timeouts",
                     "solver_secs", "solver_nodes", "neural_moves"):
            assert hasattr(bot, attr)
        assert not MP.is_mirrored(bot)
        assert bot.manifest["agent"] == "joshua_bot"
        assert bot.manifest["deterministic"] is True

    def test_unknown_preset_raises(self):
        with pytest.raises(ValueError):
            JoshuaBot(Game(enable_legal_moves_cache=True), preset="nope")

    def test_unknown_override_raises_rather_than_being_ignored(self):
        """A typo'd tournament axis would otherwise read as a null result."""
        with pytest.raises(TypeError):
            JoshuaBot(Game(enable_legal_moves_cache=True),
                      overrides={"j7_wieght": 0.0})

    def test_presets_differ_where_the_interview_says_they_do(self):
        early, cur = PRESETS["early"], PRESETS["current"]
        assert early.early_farm_block_frac < cur.early_farm_block_frac
        assert early.j2_steal_w > cur.j2_steal_w
        assert early.j2_min_farm_value < cur.j2_min_farm_value
        assert early.j2_city_count_from_k > cur.j2_city_count_from_k

    def test_manifest_records_the_variant(self):
        """House rule: a cell must be self-describing. The manifest carries the
        variant id, the three tournament axes, the explicit overrides, AND the
        full resolved params."""
        game = Game(enable_legal_moves_cache=True)
        bot = JoshuaBot(game, preset="current",
                        overrides={"j7_weight": 0.0,
                                   "j8_break_reserve_floor": True,
                                   "j9_avoid_cloisters": True})
        m = bot.manifest
        assert m["axes"] == {"j7_weight": 0.0, "j8_break_reserve_floor": True,
                             "j9_avoid_cloisters": True}
        assert m["overrides"]["j7_weight"] == 0.0
        assert m["params"]["j7_weight"] == 0.0          # resolved, not just declared
        assert m["params"]["j9_cloister_block_frac"] == P.j9_cloister_block_frac
        assert m["variant_id"] == bot.variant_id
        assert m["variant_id"].startswith("current+j7w0")
        assert "j8brk" in m["variant_id"] and "j9avoid" in m["variant_id"]

    def test_variant_id_is_stable_and_distinguishes_arms(self):
        game = Game(enable_legal_moves_cache=True)
        base = JoshuaBot(game).variant_id
        assert base == JoshuaBot(game).variant_id
        assert base != JoshuaBot(game, overrides={"j7_weight": 0.0}).variant_id
        assert base != JoshuaBot(
            game, overrides={"j8_break_reserve_floor": True}).variant_id
        assert base != JoshuaBot(
            game, overrides={"j9_avoid_cloisters": True}).variant_id
        assert base != JoshuaBot(game, preset="early").variant_id

    def test_each_variant_is_separately_deterministic(self):
        """Determinism is per VARIANT: the same arm always repeats itself, and a
        toggled axis is allowed to (but need not) differ."""
        random.seed(4242)
        game = Game(enable_legal_moves_cache=True)
        board = game.get_init_board()
        arms = [{}, {"j7_weight": 0.0}, {"j8_break_reserve_floor": True},
                {"j9_avoid_cloisters": True}]
        for _ in range(10):
            picks = []
            for ov in arms:
                a = JoshuaBot(game, overrides=ov).choose_action(board)
                assert JoshuaBot(game, overrides=ov).choose_action(board) == a
                picks.append(a)
            board, _ = game.get_next_state(board, int(picks[0]))

    def test_deterministic_same_position_same_move(self):
        random.seed(5150)
        game = Game(enable_legal_moves_cache=True)
        board = game.get_init_board()
        for _ in range(12):
            a = JoshuaBot(game).choose_action(board)
            assert JoshuaBot(game).choose_action(board) == a
            board, _ = game.get_next_state(board, int(a))

    @pytest.mark.parametrize("preset", ["current", "early"])
    def test_full_game_vs_rule_based_player(self, preset):
        """Smoke: the bot plays a legal, complete game from both seats."""
        game = Game(enable_legal_moves_cache=True)
        for joshua_seat in (0, 1):
            random.seed(9090)
            board = game.get_init_board()
            bot = JoshuaBot(game, preset=preset)
            rb = RuleBasedPlayer(seed=11)
            n = 0
            while game.get_game_ended(board, 0) == 0.0:
                valid = game.get_valid_moves(board)
                seat = board.state.current_player
                a = (bot.choose_action(board) if seat == joshua_seat
                     else rb.choose_action(game, board, valid))
                assert valid[a], f"illegal action {a} at move {n}"
                board, _ = game.get_next_state(board, int(a))
                n += 1
                assert n < 400, "runaway game"
            assert n > 100
            assert sum(board.state.scores) > 0

    def test_all_toggles_on_still_plays_a_legal_complete_game(self):
        """The maximal variant: J7 naive + J8 breaks the reserve floor + J9
        cloister caution. Three filters and a re-weighted term interacting is
        exactly where a candidate set could get emptied."""
        game = Game(enable_legal_moves_cache=True)
        ov = {"j7_weight": 0.0, "j8_break_reserve_floor": True,
              "j9_avoid_cloisters": True}
        for joshua_seat in (0, 1):
            random.seed(8181)
            board = game.get_init_board()
            bot = JoshuaBot(game, preset="current", overrides=ov)
            rb = RuleBasedPlayer(seed=13)
            n = 0
            while game.get_game_ended(board, 0) == 0.0:
                valid = game.get_valid_moves(board)
                seat = board.state.current_player
                a = (bot.choose_action(board) if seat == joshua_seat
                     else rb.choose_action(game, board, valid))
                assert valid[a], f"illegal action {a} at move {n}"
                board, _ = game.get_next_state(board, int(a))
                n += 1
                assert n < 400, "runaway game"
            assert n > 100

    def test_rules_actually_fire_over_a_real_game(self):
        """An encoding nobody's rules ever reach is not an encoding. Over one
        full game at least three distinct J-terms must have moved a decision."""
        random.seed(303)
        game = Game(enable_legal_moves_cache=True)
        board = game.get_init_board()
        bot = JoshuaBot(game, preset="current")
        rb = RuleBasedPlayer(seed=11)
        while game.get_game_ended(board, 0) == 0.0:
            seat = board.state.current_player
            a = (bot.choose_action(board) if seat == 1
                 else rb.choose_action(game, board, game.get_valid_moves(board)))
            board, _ = game.get_next_state(board, int(a))
        assert len([k for k in bot.rule_fires if k.startswith("j")]) >= 3


class TestFarmValuation:
    def test_finished_cities_are_left_to_the_base_score(self):
        """``flat_base_score`` already pays 3/finished adjacent city, so only the
        UNFINISHED ones may enter the J2 potential — otherwise J2 double-counts."""
        from carcassonne_ai.joshua_bot import farm_potential_value

        d = _farm_setup(adj_cities=2, finished_cities=2)
        pos = _pos(d, farm={10: [1, 1]}, state=_FakeState(filled=[(2, 2)]))
        late = _clock(k=10)
        assert farm_potential_value(pos, 10, late, P) == 0.0
        assert farm_total_value(pos, 10, late, P) == pytest.approx(6.0)

    def test_unclosable_cities_do_not_count(self):
        from carcassonne_ai.joshua_bot import farm_potential_value

        d = _farm_setup(adj_cities=2, open_n=99)
        pos = _pos(d, farm={10: [1, 1]}, state=_FakeState(filled=[(2, 2)]))
        assert farm_potential_value(pos, 10, _clock(k=10), P) == 0.0
