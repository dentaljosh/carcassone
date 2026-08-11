"""P5 / G5 — the rules-fix FLAGS, Python reference vs `carc_rs`.

Every flag test merged into the main tree on 2026-07-31 (merge `5c35106`;
worktree `b7d61ab`/`6d8385d`/`8d877fc`/`e2ecdb3`) is reproduced here against the
Rust port, driving BOTH engines and comparing byte-exact `string_representation`
/ legal-mask bytes / scores per ply:

  tests/test_fixed_start_tile.py          -> `TestFixedStartTile`
  tests/android/test_bridge.py (start_rule) -> `TestStartRule`
  tests/test_start_tile_grid_bound.py     -> `TestEvenShift`

**Default semantics are the gate that matters.** Nothing here is enabled by
default anywhere: `MirrorState.from_seed(seed)` with no flags must be the
byte-compatible walled engine (`start_rule` missing ⇒ "engine", start (6, 15),
no pre-placed tile), and `test_default_is_bit_identical_to_the_pre_p5_port`
pins that.

**Comparison core.**  The per-ply comparison is `lockstep_fuzz.fuzz_game`, not a
new one — and not `reconcile_engine.check_game`, which is bound to the record
corpus (a `(deck_seed, actions, frozen_positions)` job) and has no flag hook.
The fuzz core is a strict SUPERSET of it: byte-equal mask instead of the
sha256, plus `(n_total, n_overflow)`, the window offset, BOTH Rust leaf routes,
and error parity.  `lockstep_fuzz` was extended with the flags rather than
forked, so the 1,000-game leg and these tests cannot drift apart.

The heavy legs are scripts, not tests:
  * `scripts/rustport/lockstep_fuzz.py --start-rule retail --games 1000`
  * `scripts/rustport/even_shift_property.py --games N --d-row 12`
This module runs the always-on subset of both.
"""

from __future__ import annotations

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

import os  # noqa: E402

os.environ["CARCASSONNE_WINDOW_AUDIT"] = "1"   # must precede game_wrapper import

import numpy as np  # noqa: E402

import even_shift_property as esp  # noqa: E402
import lockstep_fuzz as lf  # noqa: E402
from carcassonne_ai.game_wrapper import RETAIL_START_TILE, Game  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402
from wingedsheep.carcassonne.objects.side import Side  # noqa: E402
from wingedsheep.carcassonne.tile_sets.base_deck import base_tile_counts  # noqa: E402
from wingedsheep.carcassonne.utils.action_util import ActionUtil  # noqa: E402

SEED = 20260730          # the seed the merged Python tests use
FUZZ_SEEDS = [lf.FUZZ_SEED_BASE + i for i in range(4)]


def _pair(seed: int, rule: str = "engine", row: int = 6, col: int = 15):
    """`(Game, Board, MirrorState)` under the P5 flags — the driver's own helper,
    so the tests and the 1,000-game fuzz cannot drift apart."""
    return lf.init_pair(seed, rule, row, col)


# ===========================================================================
class TestStartRule:
    """`android_bridge._Session` semantics: "retail"/"engine"/missing ⇒ engine/
    unknown ⇒ raise.  The bridge rejects rather than defaulting because silently
    picking a rule decodes a DIFFERENT game from the same (deck_seed, actions)."""

    def test_missing_start_rule_means_engine(self):
        cfg = carc_rs.resolve_game_config()
        assert cfg["start_rule"] == "engine"
        assert cfg["fixed_start_tile"] is False
        assert (cfg["start_row"], cfg["start_col"]) == (6, 15)
        assert carc_rs.MirrorState.from_seed(str(SEED)).start_rule() == "engine"

    @pytest.mark.parametrize("rule,fixed", [("engine", False), ("retail", True)])
    def test_both_rules_resolve(self, rule, fixed):
        cfg = carc_rs.resolve_game_config(start_rule=rule)
        assert cfg["start_rule"] == rule and cfg["fixed_start_tile"] is fixed
        ms = carc_rs.MirrorState.from_seed(str(SEED), start_rule=rule)
        assert ms.start_rule() == rule
        assert (ms.tile_count() == 1) is fixed

    @pytest.mark.parametrize("bad", ["RETAIL", "Engine", "", "tournament", "none"])
    def test_unknown_start_rule_raises(self, bad):
        with pytest.raises(ValueError, match="unknown start_rule"):
            carc_rs.resolve_game_config(start_rule=bad)
        with pytest.raises(ValueError, match="unknown start_rule"):
            carc_rs.MirrorState.from_seed(str(SEED), start_rule=bad)
        with pytest.raises(ValueError, match="unknown start_rule"):
            lf.check_flags(bad, 6, 15)

    def test_the_fair_agent_carries_the_rule_too(self):
        """The flag has to reach the agent, not just the mirror — a game the
        agent starts must be under the same convention."""
        import trace_search as ts

        scfg = ts.rs_config(8)
        for rule in ("engine", "retail"):
            ag = carc_rs.FairAgentRs(scfg, 1, 0, start_rule=rule)
            assert ag.start_rule() == rule
            ag.start_game_from_seed(str(SEED))
            _g, board, ms = _pair(SEED, rule)
            assert ag.string_repr() == ms.string_repr()
            assert ag.string_repr() == _g.string_representation(board)
        with pytest.raises(ValueError, match="unknown start_rule"):
            carc_rs.FairAgentRs(scfg, 1, 0, start_rule="nope")
        with pytest.raises(ValueError, match="EVEN"):
            carc_rs.FairAgentRs(scfg, 1, 0, start_row=17)


# ===========================================================================
class TestFixedStartTile:
    """tests/test_fixed_start_tile.py, reproduced against carc_rs."""

    def test_default_is_bit_identical_to_the_pre_p5_port(self):
        """THE regression bar: default OFF is byte-for-byte the game the port
        has always played.  Guards every G1-G4 verdict."""
        for seed in FUZZ_SEEDS + [SEED]:
            a = carc_rs.MirrorState.from_seed(str(seed))
            for kw in ({}, {"start_rule": "engine"},
                       {"start_rule": None, "start_row": 6, "start_col": 15}):
                b = carc_rs.MirrorState.from_seed(str(seed), **kw)
                assert a.string_repr() == b.string_repr()
                assert a.legal_mask_bytes() == b.legal_mask_bytes()
                assert a.state_digest() == b.state_digest()
                assert a.total_tiles() == b.total_tiles() == 72
                assert a.tile_count() == b.tile_count() == 0
                assert a.window_offset() == b.window_offset()
            # ... and identical to the Python default Game()
            game, board, ms = _pair(seed)
            assert game.string_representation(board) == a.string_repr()
            assert board.total_tiles == a.total_tiles() == 72
            assert board.state.placed_coords == set()
            assert board.state.current_player == a.current_player() == 0
            assert board.state.phase == GamePhase.TILES
            # the historical first-move contract: exactly one forced placement
            acts = ActionUtil.get_possible_actions(board.state)
            assert len(acts) == 1 == len(a.legal_actions())
            assert acts[0].coordinate == board.state.starting_position
            assert acts[0].tile_rotations == 0

    def test_retail_start_places_the_D_tile(self):
        game, board, ms = _pair(SEED, "retail")
        st = board.state
        coord = st.starting_position
        tile = st.board[coord.row][coord.column]

        assert tile is not None and tile.description == RETAIL_START_TILE
        assert tile.get_type(Side.TOP).name.lower() == "city"
        assert tile.get_type(Side.LEFT).name.lower() == "road"
        assert tile.get_type(Side.RIGHT).name.lower() == "road"
        assert tile.get_type(Side.BOTTOM).name.lower() == "grass"

        # the port sees the same tile, unrotated, at the same place
        assert ms.placed_tiles() == [(coord.row, coord.column, RETAIL_START_TILE, 0)]
        assert carc_rs.RETAIL_START_TILE == RETAIL_START_TILE
        assert ms.starting_position() == (coord.row, coord.column) == (6, 15)

        # nobody played it: player 0 to move, TILES phase, no meeple phase
        # pending, no meeples spent, `last_tile_action` None (the repr's last
        # element, which is what makes that observable byte-exactly).
        assert st.current_player == ms.current_player() == 0
        assert st.phase == GamePhase.TILES and ms.phase() == "tiles"
        assert st.last_tile_action is None
        assert st.placed_meeples == [[], []]
        assert st.meeples == [7, 7] and ms.meeples() == (7, 7)
        assert game.string_representation(board) == ms.string_repr()
        assert ms.string_repr().endswith(", None)")

        # bookkeeping the fast paths rely on
        assert st.placed_coords == {coord}
        assert coord not in st.open_positions and len(st.open_positions) == 4
        assert board.tile_count == ms.tile_count() == 1

    def test_retail_deck_is_the_remaining_71(self):
        game, board, ms = _pair(SEED, "retail")
        st = board.state
        assert len(st.deck) + 1 == 71 == ms.deck_len() + 1
        assert board.total_tiles == ms.total_tiles() == 72

        pool = [ms.next_tile()] + list(ms.unseen_deck())
        assert pool == [st.next_tile.description] + [t.description for t in st.deck]
        assert pool.count(RETAIL_START_TILE) == base_tile_counts[RETAIL_START_TILE] - 1 == 3

        all_tiles = pool + [RETAIL_START_TILE]
        assert len(all_tiles) == 72
        for name, count in base_tile_counts.items():
            assert all_tiles.count(name) == count, f"{name} miscounted"

    def test_retail_draws_the_D_out_of_the_shuffled_pool_in_place(self):
        """WHICH copy leaves the bag and WHERE in the draw order: the FIRST D in
        `[next_tile] + deck`, and nothing else moves."""
        for seed in FUZZ_SEEDS:
            eng = carc_rs.MirrorState.from_seed(str(seed))
            ret = carc_rs.MirrorState.from_seed(str(seed), start_rule="retail")
            pool = [eng.next_tile()] + list(eng.unseen_deck())
            assert len(pool) == 72
            expect = list(pool)
            expect.pop(expect.index(RETAIL_START_TILE))       # first match wins
            assert [ret.next_tile()] + list(ret.unseen_deck()) == expect

    def test_retail_first_move_is_a_real_choice(self):
        eg, eb, ems = _pair(SEED)
        rg, rb, rms = _pair(SEED, "retail")
        assert len(ActionUtil.get_possible_actions(eb.state)) == 1 == len(ems.legal_actions())
        assert len(ActionUtil.get_possible_actions(rb.state)) > 1
        assert len(rms.legal_actions()) == len(np.flatnonzero(rg.get_valid_moves(rb)))

    @pytest.mark.parametrize("rule", ["engine", "retail"])
    def test_window_offset_starts_on_the_start_tile(self, rule):
        game, board, ms = _pair(SEED, rule)
        sp = board.state.starting_position
        half = board.offset.size // 2
        assert board.offset.origin_row == sp.row - half
        assert board.offset.origin_col == sp.column - half
        assert ms.window_offset() == (board.offset.origin_row, board.offset.origin_col,
                                      board.offset.size)

    @pytest.mark.parametrize("rule", ["engine", "retail"])
    def test_plays_to_a_legal_finish_in_lockstep(self, rule):
        """End-to-end: 72 tiles placed, a scored terminal, and the port agrees
        byte-for-byte at every ply (`fuzz_game` is the same code the 1,000-game
        leg runs, with the flags threaded through)."""
        r = lf.fuzz_game({"deck_seed": lf.FUZZ_SEED_BASE + 11,
                          "policy_seed": 5_000_011, "mode": "uniform",
                          "max_plies": 400, "start_rule": rule,
                          "start_row": 6, "start_col": 15})
        assert r["mismatch"] is None, r["mismatch"]
        assert r["status"] in ("ok", "window_overflow", "engine_error"), r["status"]
        assert r["plies"] > 50 and r["compared"] == r["plies"] + 1

    @pytest.mark.parametrize("mode", ["uniform", "wall"])
    def test_retail_lockstep_fuzz_subset(self, mode):
        for i in range(3):
            r = lf.fuzz_game({"deck_seed": lf.FUZZ_SEED_BASE + i,
                              "policy_seed": 5_000_000 + i, "mode": mode,
                              "max_plies": 400, "start_rule": "retail",
                              "start_row": 6, "start_col": 15})
            assert r["mismatch"] is None, r["mismatch"]
            assert r["status"] in ("ok", "window_overflow", "engine_error")

    def test_the_action_space_is_untouched_by_the_rule(self):
        """The flag touches game SETUP only — the window, the action space and
        the encoding are unchanged, which is why a random-start checkpoint plays
        a fixed-start game with no shape or semantic change."""
        assert Game().get_action_size() == Game(fixed_start_tile=True).get_action_size()
        e = carc_rs.MirrorState.from_seed(str(SEED))
        r = carc_rs.MirrorState.from_seed(str(SEED), start_rule="retail")
        assert len(e.legal_mask_bytes()) == len(r.legal_mask_bytes())
        assert e.window_offset() == r.window_offset()


# ===========================================================================
class TestEvenShift:
    """tests/test_start_tile_grid_bound.py, reproduced against carc_rs.

    Row 6 of a 35-row grid leaves 6 rows of headroom above and 28 below; 6 -> 18
    restores it.  The shift must be EVEN because `offset_from_centroid_sums`
    centres the window with banker's-rounded `round(sum/count)`.
    """

    def test_start_tile_is_not_centred_and_the_port_agrees(self):
        ms = carc_rs.MirrorState.from_seed(str(SEED))
        row, col = ms.starting_position()
        assert (row, col) == (carc_rs.DEFAULT_START_ROW, carc_rs.DEFAULT_START_COL)
        above, below = row, 35 - 1 - row
        left, right = col, 35 - 1 - col
        # The same documented, measured asymmetry the Python test pins.  If a
        # future recentring lands, BOTH assertions fire together.
        assert (above, below) == (6, 28)
        assert (left, right) == (15, 19)
        assert above < 17, "observed placed-tile spans reach 17 rows"

    @pytest.mark.parametrize("row", [0, 2, 4, 6, 8, 18, 34])
    def test_even_shifts_are_accepted(self, row):
        cfg = carc_rs.resolve_game_config(start_row=row)
        assert cfg["start_row"] == row
        assert carc_rs.MirrorState.from_seed(str(SEED), start_row=row).starting_position() \
            == (row, 15)

    @pytest.mark.parametrize("row", [5, 7, 17, 19, 1, 33])
    def test_odd_shifts_are_refused(self, row):
        """The NEGATIVE test: an odd shift silently slips the window by one cell
        on ~half of all positions (`round(6.5) == 6` vs `round(17.5) == 18`), so
        it must be refused at construction, not measured later."""
        assert (row - 6) % 2 == 1
        with pytest.raises(ValueError, match="EVEN"):
            carc_rs.resolve_game_config(start_row=row)
        with pytest.raises(ValueError, match="EVEN"):
            carc_rs.MirrorState.from_seed(str(SEED), start_row=row)
        with pytest.raises(ValueError, match="EVEN"):
            lf.check_flags("engine", row, 15)

    @pytest.mark.parametrize("col", [14, 16, 100])
    def test_odd_or_offboard_columns_are_refused(self, col):
        with pytest.raises(ValueError):
            carc_rs.resolve_game_config(start_col=col)

    @pytest.mark.parametrize("row", [-2, 36])
    def test_offboard_even_rows_are_refused(self, row):
        with pytest.raises(ValueError, match="outside"):
            carc_rs.resolve_game_config(start_row=row)

    def test_odd_shift_desynchronises_the_window_but_even_does_not(self):
        """The mechanism, straight out of the Python module docstring, measured
        on the port: a centroid landing exactly on `.5`."""
        from carcassonne_ai.board_repr import offset_from_centroid_sums

        _g, board, _ms = _pair(SEED)
        st = board.state
        sum_row, sum_col, count = 13, 30, 2           # row centroid 6.5 — the tie
        base = offset_from_centroid_sums(st, sum_row, sum_col, count)
        odd = offset_from_centroid_sums(st, sum_row + 11 * count, sum_col, count)
        even = offset_from_centroid_sums(st, sum_row + 12 * count, sum_col, count)
        assert even.origin_row == base.origin_row + 12
        assert odd.origin_row != base.origin_row + 11

    @pytest.mark.parametrize("rule", ["engine", "retail"])
    def test_even_shift_property_holds_on_replayed_games(self, rule):
        """The full four-engine property (see `even_shift_property.__doc__`):
        Python<->Rust byte identity at BOTH rows, the exact row transform, the
        window translating exactly, and a bit-identical encoded tensor."""
        compared = 0
        for i in range(3):
            r = esp.run_game({"deck_seed": lf.FUZZ_SEED_BASE + i,
                              "policy_seed": 6_000_000 + i,
                              "mode": "uniform", "d_row": 12, "d_col": 0,
                              "start_rule": rule, "max_plies": 400})
            assert r["mismatch"] is None, r["mismatch"]
            assert r["status"] == "ok", r["status"]
            compared += r["compared"]
            assert r["compared"] > 30, f"probe degenerate: {r}"
        assert compared > 90

    def test_the_shift_is_what_makes_the_wall_stop_biting(self):
        """Evidence the probe is not vacuous: on at least one replayed game the
        two grids DO part company, and always because the base board's 6 rows of
        headroom denied something (`stopped_by == mask_divergence`), never
        because a checked invariant broke."""
        stops, denied = [], 0
        for i in range(8):
            r = esp.run_game({"deck_seed": lf.FUZZ_SEED_BASE + i,
                              "policy_seed": 6_000_000 + i,
                              "mode": "wall" if i % 5 == 4 else "uniform",
                              "d_row": 12, "d_col": 0,
                              "start_rule": "engine", "max_plies": 400})
            assert r["mismatch"] is None, r["mismatch"]
            stops.append(r["stopped_by"])
            denied += r["wall_denied_plies"]
        assert set(stops) <= {"terminal", "mask_divergence", "engine_refusal"}
        assert "mask_divergence" in stops, stops
        assert denied > 0, "no off-grid open position was ever denied — probe weak"
