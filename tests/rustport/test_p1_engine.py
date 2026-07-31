"""Fast guards for the rustport P1 engine slice.

The full G1 gate is `scripts/rustport/reconcile_engine.py --corpus all`
(463 games / ~67k positions, ~10 s at 8 workers).  These are the cheap
always-on subset plus the unit-level contracts that the corpus replay would
only catch indirectly.
"""

from __future__ import annotations

import hashlib
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

import numpy as np  # noqa: E402

from carcassonne_ai.action_space import action_size, decode, encode  # noqa: E402
from carcassonne_ai.flat_leaf import flat_base_score  # noqa: E402
from root_replay import replay_actions  # noqa: E402

import reconcile_engine as rec  # noqa: E402


def _lockstep(deck_seed: int, actions: list[int]) -> None:
    game, board = replay_actions(deck_seed, actions, 0)
    ms = carc_rs.MirrorState.from_seed(str(deck_seed))
    for i, a in enumerate(list(actions) + [None]):
        assert game.string_representation(board) == ms.string_repr(), f"repr @ply {i}"
        if not board.state.is_terminated():
            mask = np.asarray(game.get_valid_moves(board), dtype=bool)
            assert hashlib.sha256(mask.tobytes()).hexdigest() == ms.legal_mask_sha256(), (
                f"mask @ply {i}"
            )
        assert [int(x) for x in board.state.scores] == list(ms.scores()), f"scores @ply {i}"
        for p in (0, 1):
            assert int(flat_base_score(board.state, p)) == int(ms.flat_base_score(p)), (
                f"flat_base_score[p{p}] @ply {i}"
            )
        if a is not None:
            board, _ = game.get_next_state(board, int(a))
            ms.advance(int(a))


def test_action_space_layout_matches_python():
    assert action_size(25) == 2511
    ms = carc_rs.MirrorState.from_seed("1")
    assert len(ms.legal_mask_bytes()) == action_size(25)


def test_first_move_is_the_forced_starting_placement():
    ms = carc_rs.MirrorState.from_seed("1")
    game, board = replay_actions(1, [], 0)
    mask = np.asarray(game.get_valid_moves(board), dtype=bool)
    assert ms.legal_actions() == np.flatnonzero(mask).tolist()
    assert len(ms.legal_actions()) == 1


def test_e4_phone_archives_replay_bit_identically():
    """Both archives, per-ply, plus the phone's own recorded final scores."""
    paths = sorted((REPO / "measurement" / "e4_games").glob("*.json"))
    assert len(paths) == 2
    for path in paths:
        d = json.loads(path.read_text())
        assert d["schema"] == "carcassonne-android-archive/v1"
        _lockstep(int(d["deck_seed"]), [int(a) for a in d["actions"]])
        ms = carc_rs.MirrorState.from_seed(str(d["deck_seed"]))
        for a in d["actions"]:
            ms.advance(int(a))
        assert list(ms.scores()) == [int(x) for x in d["result"]["scores"]]
        assert ms.is_terminal()


def test_golden_frozen_positions_reproduce():
    jobs = [j for j in rec.load_jobs("golden", None)]
    checked = 0
    for job in jobs:
        r = rec.check_game(job)
        assert r["mismatches"] == [], r["mismatches"][:1]
        checked += r["frozen_checked"]
    assert checked == 56, f"expected the fixture's 56 positions, saw {checked}"


def test_champ_sample_replays_bit_identically():
    jobs = rec.load_jobs("champ", None)
    assert len(jobs) == 449
    rng = random.Random(20260731)
    for job in rng.sample(jobs, 6):
        r = rec.check_game(job)
        assert r["mismatches"] == [], r["mismatches"][:1]


def test_from_deck_matches_from_seed():
    """The phone path (`start_game_from_deck`) must reach the same states as the
    seeded path — it is the entry point with no RNG dependence at all."""
    d = json.loads(sorted((REPO / "measurement" / "e4_games").glob("*.json"))[0].read_text())
    seed, actions = int(d["deck_seed"]), [int(a) for a in d["actions"]]
    deck = carc_rs.deck_descriptions_from_seed(str(seed))
    a = carc_rs.MirrorState.from_seed(str(seed))
    b = carc_rs.MirrorState.from_deck(deck)
    for i, act in enumerate(actions):
        assert a.string_repr() == b.string_repr(), f"@ply {i}"
        a.advance(act)
        b.advance(act)
    assert a.string_repr() == b.string_repr()
    assert a.scores() == b.scores() == tuple(d["result"]["scores"])


def test_decode_agrees_with_python_on_every_legal_action():
    """Every legal index decodes to the same engine action on both sides — the
    mask alone would not catch a decode that lands on a different rotation."""
    from carcassonne_ai.action_space import WindowOffset
    from wingedsheep.carcassonne.objects.actions.meeple_action import MeepleAction
    from wingedsheep.carcassonne.objects.actions.pass_action import PassAction
    from wingedsheep.carcassonne.objects.actions.tile_action import TileAction

    d = json.loads(sorted((REPO / "measurement" / "e4_games").glob("*.json"))[0].read_text())
    actions = [int(a) for a in d["actions"]]
    game, board = replay_actions(int(d["deck_seed"]), actions, 0)
    ms = carc_rs.MirrorState.from_seed(str(d["deck_seed"]))

    for i, a in enumerate(actions):
        off = board.offset
        assert (off.origin_row, off.origin_col, off.size) == ms.window_offset(), f"offset @{i}"
        mask = np.asarray(game.get_valid_moves(board), dtype=bool)
        for idx in np.flatnonzero(mask).tolist():
            act = decode(
                int(idx), off=off, phase=board.state.phase.value,
                next_tile=board.state.next_tile,
                last_tile_coord=(board.state.last_tile_action.coordinate
                                 if board.state.last_tile_action else None),
            )
            # round-trip: encode(decode(idx)) == idx
            assert encode(act, off, board.state.phase.value) == idx
            if isinstance(act, TileAction):
                assert 0 <= act.tile_rotations < 4
            else:
                assert isinstance(act, (MeepleAction, PassAction))
        board, _ = game.get_next_state(board, a)
        ms.advance(a)


def test_count_final_scores_is_order_invariant_smoke():
    """The P1 escalation trigger, in miniature.  The broad run is
    `scripts/rustport/property_count_final_scores_order.py`."""
    import property_count_final_scores_order as prop

    rc = prop.main(["--games", "3", "--plies-per-game", "3", "--perms", "3"])
    assert rc == 0, "count_final_scores became order-sensitive -> ESCALATE"
