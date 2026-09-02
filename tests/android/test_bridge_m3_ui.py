"""Desktop tests for the M3 UI build's bridge additions (2026-09-02).

Three additive, read-only surfaces, none of which is on the move-decision path:

* ``tile_type_key`` — the tile-bag view's grouping key, canonicalised over the
  engine's own four rotations. THIS file is where the engine-side property lives,
  because the engine is importable here and is not on the JVM; the phone-side
  collapse is pinned by ``BagGroupingTest``.
* ``peek_next_tile`` — the "you draw next" panel, plus the ``preview_next_tile``
  archive stamp that lets the E4 ledger condition on it.
* ``remote_display_name`` — the remote opponent named from the SERVER's own
  ``/health`` self-description rather than from our copy of its launch flags.

    .venv/bin/python -m pytest tests/android/test_bridge_m3_ui.py -q
"""
from __future__ import annotations

import json

import pytest

import android_bridge as B


def j(s: str) -> dict:
    assert isinstance(s, str), f"bridge must return a JSON string, got {type(s)}"
    return json.loads(s)


def ok(s: str) -> dict:
    d = j(s)
    assert d.get("ok") is True, f"bridge call failed: {d}"
    return d


def new(**cfg) -> dict:
    base = {"seed": 5, "human_player": 0, "opponent": "tier1",
            "sims": 8, "k_dets": 1, "verify": False}
    base.update(cfg)
    return ok(B.new_game(json.dumps(base)))


@pytest.fixture(autouse=True)
def _clean_session():
    yield
    B.reset()


# --------------------------------------------------------------------------- #
# 1. the tile-bag grouping key                                                  #
# --------------------------------------------------------------------------- #
def _base_deck():
    from wingedsheep.carcassonne.tile_sets.base_deck import base_tile_counts, base_tiles
    return base_tile_counts, base_tiles


def test_the_72_tile_deck_collapses_to_the_24_base_game_types():
    """The retail base game has 24 distinct tiles (the lettered faces A..X).

    The engine carries 32 DESCRIPTIONS for them, because eight of the faces have a
    second "garden" drawing. A garden carries no rule at all under the locked
    2p Base+Farmers scope (no Abbots — CLAUDE.md), so those eight are art variants
    and the bag must show 24 rows, not 32.
    """
    counts, tiles = _base_deck()
    groups: dict[str, list[str]] = {}
    for desc in counts:
        groups.setdefault(B.tile_type_key(tiles[desc]), []).append(desc)

    assert len(counts) == 32, "the engine's base deck should carry 32 descriptions"
    assert len(groups) == 24, (
        f"expected the 24 base-game tile types, got {len(groups)}: "
        f"{sorted((k, sorted(v)) for k, v in groups.items())}")
    # Every collapsed pair is a plain face and its own garden variant, never two
    # genuinely different tiles.
    for members in groups.values():
        if len(members) > 1:
            assert len(members) == 2, members
            assert sum(1 for m in members if tiles[m].flowers) == 1, members


def test_the_grouped_counts_still_sum_to_the_whole_deck():
    counts, tiles = _base_deck()
    per_group: dict[str, int] = {}
    for desc, n in counts.items():
        key = B.tile_type_key(tiles[desc])
        per_group[key] = per_group.get(key, 0) + int(n)
    assert sum(counts.values()) == 72
    assert sum(per_group.values()) == 72


def test_pennanted_faces_never_merge_with_their_plain_twin():
    """⛔ A pennant is +1 point per tile in that city.

    Merging a shielded face into its unshielded twin would tell the player there
    are N of a tile when N-k of them score differently. `shield` is in the key for
    exactly this reason, and this is the test that says so.
    """
    counts, tiles = _base_deck()
    shielded = {B.tile_type_key(tiles[d]) for d in counts if tiles[d].shield}
    plain = {B.tile_type_key(tiles[d]) for d in counts if not tiles[d].shield}
    assert shielded, "the base deck has shielded faces"
    assert not (shielded & plain), "a pennanted face shares a group with a plain one"


def test_the_key_is_rotation_invariant_and_only_that():
    """Four rotations of one tile are one type; two different tiles are two."""
    _counts, tiles = _base_deck()
    straight = tiles["straight_road"]
    keys = {B.tile_type_key(straight.turn(n)) for n in range(4)}
    assert len(keys) == 1, "rotating a tile must not change its type"
    assert B.tile_type_key(tiles["bent_road"]) != B.tile_type_key(straight)


def test_get_bag_stamps_a_type_key_on_every_face():
    new()
    bag = ok(B.get_bag())
    assert bag["faces"], "the bag reports faces"
    for face in bag["faces"]:
        assert face["type_key"], f"no type_key on {face['description']}"
    # The additive field must not have disturbed the invariant the bag already
    # had: `total_remaining == len(deck)` (the in-hand tile is subtracted on the
    # counting side, so it is not added back here — see `get_bag`'s docstring).
    assert bag["total_remaining"] == bag["deck_remaining"]


# --------------------------------------------------------------------------- #
# 2. the next-tile peek                                                         #
# --------------------------------------------------------------------------- #
def test_the_peek_is_refused_on_the_humans_own_turn():
    """The gate is the CONTRACT, not a UI convention.

    On the human's turn the tile is already in hand, so a peek would hand over the
    draw AFTER the one being played — a much larger information change than the
    feature asks for, and one made while the player has a live decision.
    """
    st = new(human_player=0)
    assert st["is_human_turn"] is True
    d = j(B.peek_next_tile())
    assert d["ok"] is False
    assert d["error"]["code"] == "not_opponent_turn"


def test_the_peek_names_the_front_of_the_deck_and_does_not_draw_it():
    """It is a PEEK: the deck is the same length before and after, and the tile
    reported is the one `StateUpdater.draw_tile` would pop (`deck.pop(0)`)."""
    # Seat the human second so the very first state is the opponent's turn.
    new(human_player=1)
    session = B._require_session()
    before = list(session.board.state.deck)
    d = ok(B.peek_next_tile())
    after = list(session.board.state.deck)

    assert [t.description for t in before] == [t.description for t in after], \
        "peeking must not consume a tile"
    assert d["tile"]["description"] == before[0].description
    assert d["deck_remaining"] == len(before)


def test_the_peek_is_flagged_provisional_under_the_retail_redraw_rule():
    """Under `fixed_v1` an unplaceable draw is set aside and the player redraws, so
    the opponent's move can still change which tile arrives. The panel says so."""
    new(human_player=1, draw_rule=B.DRAW_RULE_REDRAW)
    assert ok(B.peek_next_tile())["provisional"] is True
    B.reset()
    new(human_player=1, draw_rule=B.DRAW_RULE_ENGINE)
    assert ok(B.peek_next_tile())["provisional"] is False


def test_a_game_with_no_peek_stamps_preview_next_tile_false():
    new(human_player=1)
    ok(B.debug_fast_forward("yes-destroy-this-game"))
    rec = ok(B.archive_record())
    assert rec["preview_next_tile"] is False
    assert rec["preview_next_tile_peeks"] == 0


def test_a_peeked_game_stamps_preview_next_tile_true_and_counts_them():
    """The stamp is a COUNT of peeks actually served, not a copy of a setting.

    A setting could be flipped off before it was ever used, or on after the game
    ended; what the E4 ledger needs to condition on is whether the human was shown
    the upcoming tile in THIS game.
    """
    new(human_player=1)
    ok(B.peek_next_tile())
    ok(B.peek_next_tile())
    ok(B.debug_fast_forward("yes-destroy-this-game"))
    rec = ok(B.archive_record())
    assert rec["preview_next_tile"] is True
    assert rec["preview_next_tile_peeks"] == 2


def test_the_peek_count_survives_a_save_restore_round_trip():
    """A Resume must not launder the first half's peeks out of the record."""
    new(human_player=1)
    ok(B.peek_next_tile())
    save = ok(B.save_game())
    assert save["preview_next_tile_peeks"] == 1

    B.reset()
    ok(B.restore_game(json.dumps(save)))
    assert B._require_session().peek_count == 1
    assert ok(B.save_game())["preview_next_tile_peeks"] == 1


def test_an_old_save_with_no_peek_field_restores_as_zero():
    """Absent == 0, which is literally true of every game played before this build."""
    new(human_player=1)
    ok(B.peek_next_tile())
    save = ok(B.save_game())
    del save["preview_next_tile_peeks"]

    B.reset()
    ok(B.restore_game(json.dumps(save)))
    assert B._require_session().peek_count == 0


# --------------------------------------------------------------------------- #
# 3. naming the remote opponent from the server, not from our config            #
# --------------------------------------------------------------------------- #
def test_a_fixed_playout_server_is_named_by_its_playouts_not_by_our_budget_ms():
    """The regression this fixes: `server.py --playouts` nulls `budget_ms` on the
    server side while the phone still carries its 5000 ms default, so the old
    `f"Carcasum {budget_ms // 1000}s"` printed "Carcasum 5s" over an opponent that
    was not on a time budget at all."""
    health = {"opponent_label": "carcasum_remote_p103500",
              "opponent": {"kind": "mcts", "playouts": 103500, "budget_ms": None}}
    assert B.remote_display_name(health, 5000) == "Carcasum(103.5k playouts)"


def test_a_time_budgeted_server_is_still_named_in_seconds():
    health = {"opponent_label": "carcasum_remote_5000ms",
              "opponent": {"kind": "mcts", "budget_ms": 5000, "cp": 0.5}}
    assert B.remote_display_name(health, 5000) == "Carcasum(5s/turn)"


def test_a_silent_server_falls_back_to_the_configured_budget():
    assert B.remote_display_name(None, 5000) == "Carcasum(5s/turn)"
    assert B.remote_display_name({}, None) == "Carcasum"


@pytest.mark.parametrize("n,want", [
    (103500, "103.5k"), (2000, "2k"), (1500, "1.5k"), (900, "900"), (1000, "1k"),
])
def test_playout_counts_read_as_numbers_a_person_would_say(n, want):
    assert B.humanise_playouts(n) == want


# --------------------------------------------------------------------------- #
# 3b. the ARCHIVE's opponent stamp, derived from the server (ruling 2026-09-02)  #
# --------------------------------------------------------------------------- #
def test_the_archive_label_comes_from_the_server_in_playout_mode():
    """OWNER RULING 2026-09-02, "fix the labels". The stamp used to be built from
    OUR copy of the launch config and always read `carcasum_remote_5000ms`, which
    is false whenever the daemon runs `--playouts` (budget_ms is None on its side).
    The archive is graded months later, so it must say what actually played."""
    health = {"opponent_label": "carcasum_remote_p103500",
              "opponent": {"kind": "mcts", "playouts": 103500, "budget_ms": None}}
    assert B.resolve_remote_opponent_kind(health, 5000) == "carcasum_remote_p103500"


def test_the_archive_label_is_still_the_budget_form_in_budget_mode():
    health = {"opponent_label": "carcasum_remote_5000ms",
              "opponent": {"kind": "mcts", "budget_ms": 5000}}
    assert B.resolve_remote_opponent_kind(health, 5000) == "carcasum_remote_5000ms"
    # And an unusual-but-honest budget is carried through, not rounded to 5000.
    assert B.resolve_remote_opponent_kind(
        {"opponent_label": "carcasum_remote_2000ms"}, 2000) == "carcasum_remote_2000ms"


@pytest.mark.parametrize("label", [
    "champion",                 # ⛔ the one that would poison the E4 anchor
    "tier1",
    "",
    None,
    "something_else_entirely",
    "not_carcasum_remote",      # contains the prefix, but not as a prefix
])
def test_a_server_that_does_not_name_itself_carcasum_is_never_believed(label):
    """⛔ THE SAFETY PROPERTY. This value goes into the archive's `opponent` field,
    and that field is the ONE gate keeping foreign games out of the owner-vs-champion
    E4 anchor (`scripts/e4_archives.py`: eligible iff `opponent == "champion"`).

    A server reporting `"champion"` — mistyped, misconfigured, or simply a different
    program on that port — would silently pool its games into the anchor and move the
    single number the whole owner session is chained through. So the server's label
    is accepted ONLY as a `carcasum_remote…` spelling; anything else falls back to
    the budget-derived form, which is conservative in the direction that matters.
    """
    kind = B.resolve_remote_opponent_kind({"opponent_label": label}, 5000)
    assert kind == "carcasum_remote_5000ms"
    assert kind != "champion"


def test_every_derivable_label_is_still_recognised_as_remote():
    """Whatever the server says, `is_remote_opponent` must match it — that predicate
    is what `_save_payload` uses to decide a game carries a `remote_url`, and what
    `restore_game` uses to route a save back to the remote branch."""
    for health in (
        {"opponent_label": "carcasum_remote_p103500"},
        {"opponent_label": "carcasum_remote_5000ms"},
        {"opponent_label": "champion"},          # refused, falls back — still remote
        None,
    ):
        kind = B.resolve_remote_opponent_kind(health, 5000)
        assert kind.startswith(B.REMOTE_OPPONENT_PREFIX)
        assert B.is_remote_opponent(kind)


def test_the_derived_label_is_excluded_by_the_real_e4_gate():
    """END TO END, across the module boundary that actually matters.

    The two halves of this ruling are written in different files — the bridge
    derives the label, `scripts/e4_archives.py` decides what the anchor counts —
    and each is individually correct for reasons the other cannot see. This drives
    the REAL gate with the REAL derived labels, so a future change to either side
    that breaks the pair fails here rather than in a month's arithmetic.
    """
    import importlib.util
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "_e4_archives_for_bridge_test", repo / "scripts" / "e4_archives.py")
    ea = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ea)

    for health in (
        {"opponent_label": "carcasum_remote_p103500"},
        {"opponent_label": "carcasum_remote_5000ms"},
        {"opponent_label": "champion"},          # the poisoning attempt
        {},
        None,
    ):
        kind = B.resolve_remote_opponent_kind(health, 5000)
        blob = {"opponent": kind, "scores": [90, 70]}
        assert not ea.is_anchor_eligible(blob), (
            f"a remote game stamped {kind!r} reached the champion anchor")
        assert kind in ea.rejection_reason(blob)


def test_the_short_opponent_name_stays_short_enough_for_the_hud_chip():
    """`MoveText.shortOpponent` cuts at the parenthesis and the HUD chip takes 14
    characters, so the identity has to survive both."""
    for health in (
        {"opponent": {"playouts": 103500}},
        {"opponent": {"budget_ms": 5000}},
        None,
    ):
        name = B.remote_display_name(health, 5000)
        assert name.split("(")[0] == "Carcasum"
        assert len(name.split("(")[0]) <= 14
