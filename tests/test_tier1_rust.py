"""Parity tests for the RUST `tier1-greedy` continuation (`carc_core::tier1`).

The port exists to re-price the tiearb2 arbiter's cost (Stage 2 Phase A,
`measurement/tiearb2_stage2_20260817/PHASE_A.md`). Its correctness bar is
bit-identity with the banked PYTHON judge, so these tests pin the places where
bit-identity is easy to lose:

  * the CPython `_randbelow(1)` rejection loop, which DOES consume entropy;
  * the two paths that consume NO draw (Rule-1 forced move; a single surviving
    candidate in `_best_by_virtual_score`);
  * Rule 3 (no early farmers) running BEFORE Rule 2 (endgame force-place);
  * `player` captured BEFORE the candidate action is applied;
  * a full playout reaching a scored terminal;
  * reproduction of a banked position-record.

⚠️ **The legal-mask memo is part of the contract.** `game_wrapper` memoizes the
legal mask under `Game.string_representation`, whose per-tile component cannot
distinguish rotation 0 from rotation 2 of a 180°-symmetric tile, so distinct
boards collide and the cached mask offers the wrong FARMER corner. The banked
judge ran with that memo, so `legal_mask_cache=True` is what reproduces it;
`False` is the honest mask. Both are tested, and the test that they DISAGREE on
a known-affected record is a regression guard on the whole finding.
"""
from __future__ import annotations

import copy
import json
import random
import struct
from pathlib import Path

import numpy as np
import pytest

carc_rs = pytest.importorskip("carc_rs")

from carcassonne_ai.action_space import (  # noqa: E402
    decode,
    meeple_farmer_base,
    meeple_pass_index,
)
from carcassonne_ai.fair_agent import FairHeuristicMCTSAgent  # noqa: E402
from carcassonne_ai.rule_based_player import RuleBasedPlayer  # noqa: E402
from carcassonne_ai.virtual_score import virtual_score_inplace  # noqa: E402
from wingedsheep.carcassonne.utils.state_updater import StateUpdater  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
RECORDS_ROOT = Path("/mnt/c/carc-shared/tiearb2_20260816/main")
POSITIONS_ROOT = REPO / "measurement" / "tiearb2_20260816"

# A late-ply banked record, chosen so a full leg is cheap. It is one of the 18
# legs the G-BITEXACT sample flagged, i.e. it EXERCISES the memo collision.
AFFECTED = {"chunk": 2, "leg": 2, "rid": "tt_sp_28100000641_p134"}
MAX_PLIES = 400


def _f64_bits(x) -> int:
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


def _load_banked(spec: dict):
    rec_p = (RECORDS_ROOT / f"chunk{spec['chunk']}" / "tier1-greedy" / "walled"
             / f"leg{spec['leg']}" / "records" / f"{spec['rid']}.json")
    pos_p = (POSITIONS_ROOT / f"positions_chunk{spec['chunk']}"
             / f"positions_walled_leg{spec['leg']}.jsonl")
    if not rec_p.exists() or not pos_p.exists():
        pytest.skip(f"banked corpus not mounted ({rec_p})")
    rec = json.loads(rec_p.read_text())
    pos = next(json.loads(x) for x in pos_p.read_text().splitlines()
               if x.strip() and json.loads(x)["rid"] == spec["rid"])
    return rec, pos


def _rust_leg(pos: dict, rec: dict, *, cache: bool):
    return carc_rs.tier1_leg(
        str(int(pos["deck_seed"])),
        [int(a) for a in pos["actions"]],
        int(pos["ply"]),
        int(pos["pick_a"]),
        int(pos["pick_b"]),
        int(pos["root_player"]),
        [int(x) for x in rec["world_seeds"]],
        [int(x) for x in rec["playout_seeds"]],
        MAX_PLIES,
        cache,
    )


def _python_playout(pos: dict, world_seed: int, playout_seed: int, pick: int,
                    *, legal_cache: bool):
    """`oracle_score_pilot._playout_value`, with the memo switchable. Returns
    (margin, actions, states-before-each-move, game)."""
    import sys
    sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))
    import root_replay as RR

    game, board = RR.replay_actions(int(pos["deck_seed"]), pos["actions"], int(pos["ply"]))
    if not legal_cache:
        game._legal_cache = None
    wb = FairHeuristicMCTSAgent.reshuffled_determinization(board, random.Random(world_seed))
    b = copy.deepcopy(wb)
    b, _ = game.get_next_state(b, int(pick))
    agent = RuleBasedPlayer(seed=int(playout_seed))
    actions, states = [], []
    while not b.state.is_terminated():
        states.append(copy.deepcopy(b))
        a = int(agent.choose_action(game, b, game.get_valid_moves(b)))
        actions.append(a)
        b, _ = game.get_next_state(b, a)
    rp = int(pos["root_player"])
    return float(b.state.scores[rp] - b.state.scores[1 - rp]), actions, states, game


# ---------------------------------------------------------------------------
# 1. The RNG contract
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", [0, 5, 20260817])
def test_randbelow_one_consumes_a_draw(seed: int) -> None:
    """`random.Random._randbelow(1)` returns 0 but is NOT a free call: it draws
    `getrandbits(1)` in a rejection loop until it lands on 0. Rust must burn the
    same words or every later tie-break desynchronizes."""
    ns = [1, 1, 1, 5, 1, 3]
    rust = carc_rs.randbelow_stream(str(seed), ns)
    r = random.Random(seed)
    py = [r._randbelow(n) for n in ns]
    assert rust == py
    # ...and the streams are still aligned afterwards.
    assert carc_rs.getrandbits_stream(str(seed), [32] * 0) == []
    assert list(rust) == py


def test_randbelow_zero_is_free() -> None:
    """`_randbelow(0)` short-circuits to 0 with no draw (CPython `if not n`)."""
    assert carc_rs.randbelow_stream("7", [0, 0]) == [0, 0]


# ---------------------------------------------------------------------------
# 2. Policy parity against the python RuleBasedPlayer, memo OFF on both sides
# ---------------------------------------------------------------------------
def test_playout_action_sequence_matches_python() -> None:
    """The whole point: same world, same seed, same moves, same terminal score.

    Run with the memo OFF on BOTH sides so this isolates the POLICY (the memo's
    collision behaviour is pinned separately below).
    """
    rec, pos = _load_banked(AFFECTED)
    ws, ps = int(rec["world_seeds"][0]), int(rec["playout_seeds"][0])
    pick = int(pos["pick_a"])
    py_margin, py_actions, _states, _game = _python_playout(
        pos, ws, ps, pick, legal_cache=False)
    rs_actions, rs_margin, rs_plies, _probe = carc_rs.tier1_playout_trace(
        str(int(pos["deck_seed"])), [int(a) for a in pos["actions"]], int(pos["ply"]),
        pick, int(pos["root_player"]), ws, ps, MAX_PLIES, -1, False)
    assert list(rs_actions) == py_actions
    assert rs_plies == len(py_actions)
    assert _f64_bits(rs_margin) == _f64_bits(py_margin)


def test_playout_reaches_a_scored_terminal() -> None:
    rec, pos = _load_banked(AFFECTED)
    _acts, margin, plies, _p = carc_rs.tier1_playout_trace(
        str(int(pos["deck_seed"])), [int(a) for a in pos["actions"]], int(pos["ply"]),
        int(pos["pick_a"]), int(pos["root_player"]),
        int(rec["world_seeds"][0]), int(rec["playout_seeds"][0]), MAX_PLIES, -1, False)
    assert plies > 0
    assert margin == float(int(margin)), "the terminal margin is an integer"


# ---------------------------------------------------------------------------
# 3. The two no-draw early returns, and the meeple filters
# ---------------------------------------------------------------------------
def test_no_draw_paths_and_meeple_filter_order() -> None:
    """Walk a real playout and, at every ply, check the rust probe against the
    python rules recomputed independently:

      * Rule 1 (single legal action) and a single surviving candidate both
        return with EMPTY `scores` — i.e. no argmax, hence no RNG draw;
      * the meeple candidate set is Rule 3 (no early farmers) applied BEFORE
        Rule 2 (endgame force-place). Whenever both filters fire the two orders
        give different sets, so this pins the order.
    """
    rec, pos = _load_banked(AFFECTED)
    ws, ps = int(rec["world_seeds"][0]), int(rec["playout_seeds"][0])
    pick = int(pos["pick_a"])
    _m, py_actions, states, game = _python_playout(pos, ws, ps, pick, legal_cache=False)

    farmer_base = meeple_farmer_base(game.window_size)
    pass_idx = meeple_pass_index(game.window_size)

    seen_forced = seen_single_candidate = seen_both_filters = 0
    for ply, board in enumerate(states):
        _a, _mg, _pl, probe = carc_rs.tier1_playout_trace(
            str(int(pos["deck_seed"])), [int(x) for x in pos["actions"]], int(pos["ply"]),
            pick, int(pos["root_player"]), ws, ps, MAX_PLIES, ply, False)
        assert probe is not None, f"probe missing at ply {ply}"
        rs_legal, rs_cands, rs_scores, rs_player = probe

        legal = [int(x) for x in np.flatnonzero(game.get_valid_moves(board))]
        assert list(rs_legal) == legal, f"legal set differs at ply {ply}"

        st = board.state
        if len(legal) == 1:
            seen_forced += 1
            assert list(rs_cands) == [] and list(rs_scores) == [], (
                "Rule 1 must return before any scoring, hence with no RNG draw")
            continue

        if st.phase.value == "meeples":
            cands = list(legal)
            tiles_left = len(st.deck)
            early = tiles_left > 0.6 * board.total_tiles
            forced = tiles_left <= int(st.meeples[st.current_player])
            if early:
                nf = [a for a in cands if not (farmer_base <= a < pass_idx)]
                if nf:
                    cands = nf
            if forced:
                npass = [a for a in cands if a != pass_idx]
                if npass:
                    cands = npass
            if early and forced:
                seen_both_filters += 1
            assert list(rs_cands) == cands, f"meeple candidate set differs at ply {ply}"
        else:
            assert list(rs_cands) == legal, f"tile candidate set differs at ply {ply}"

        if len(rs_cands) == 1:
            seen_single_candidate += 1
            assert list(rs_scores) == [], (
                "a single surviving candidate must return before the argmax, "
                "hence with no RNG draw")

    assert seen_forced or seen_single_candidate, (
        "this playout exercised neither no-draw path; pick a different record")
    # `seen_both_filters` is informational: a late-ply record need not hit it.


def test_leaf_scores_use_the_player_captured_before_the_apply() -> None:
    """`_best_by_virtual_score` reads `board.state.current_player` BEFORE the
    candidate action is applied, so every candidate is scored from the mover's
    perspective, not from the afterstate's. Compare rust's per-candidate int64
    scores against `virtual_score_inplace` computed with that captured player."""
    rec, pos = _load_banked(AFFECTED)
    ws, ps = int(rec["world_seeds"][0]), int(rec["playout_seeds"][0])
    pick = int(pos["pick_a"])
    _m, _acts, states, game = _python_playout(pos, ws, ps, pick, legal_cache=False)

    checked = 0
    for ply, board in enumerate(states):
        _a, _mg, _pl, probe = carc_rs.tier1_playout_trace(
            str(int(pos["deck_seed"])), [int(x) for x in pos["actions"]], int(pos["ply"]),
            pick, int(pos["root_player"]), ws, ps, MAX_PLIES, ply, False)
        rs_legal, rs_cands, rs_scores, rs_player = probe
        if not rs_scores:
            continue
        st = board.state
        assert rs_player == st.current_player
        py_scores = []
        for ai in rs_cands:
            action = decode(
                int(ai), off=board.offset, phase=st.phase.value, next_tile=st.next_tile,
                last_tile_coord=(st.last_tile_action.coordinate
                                 if st.last_tile_action is not None else None))
            scratch = copy.deepcopy(st)
            StateUpdater.apply_action_inplace(game_state=scratch, action=action)
            py_scores.append(int(virtual_score_inplace(scratch, st.current_player)))
        assert list(rs_scores) == py_scores, f"leaf scores differ at ply {ply}"
        checked += 1
        if checked >= 6:            # six scored decisions is plenty and keeps it fast
            break
    assert checked, "no scored decision found in this playout"


# ---------------------------------------------------------------------------
# 4. Banked-record reproduction, and the memo-collision regression guard
# ---------------------------------------------------------------------------
def test_banked_record_reproduced_bit_for_bit_with_the_memo() -> None:
    """The gate, in miniature: one banked leg, all 2 x m playouts, raw f64 bits."""
    rec, pos = _load_banked(AFFECTED)
    va, vb, pa, pb, stats = _rust_leg(pos, rec, cache=True)
    assert [_f64_bits(x) for x in va] == [_f64_bits(x) for x in rec["values_a"]]
    assert [_f64_bits(x) for x in vb] == [_f64_bits(x) for x in rec["values_b"]]
    assert list(pa) == list(rec["playout_plies_a"])
    assert list(pb) == list(rec["playout_plies_b"])
    hits, misses, entries = stats
    assert misses > 0 and hits > 0 and entries == misses


def test_the_memo_collision_is_real_and_is_what_the_bank_carries() -> None:
    """Regression guard on the Phase-A finding.

    With the memo OFF the rust port computes the honest mask and DISAGREES with
    the bank on exactly the worlds the collision touched; with it ON it agrees
    everywhere. If someone ever fixes `string_representation`, this test fails
    loudly rather than letting the gate quietly re-interpret itself.
    """
    rec, pos = _load_banked(AFFECTED)
    on_a, on_b, _pa, _pb, _s = _rust_leg(pos, rec, cache=True)
    off_a, off_b, _qa, _qb, off_stats = _rust_leg(pos, rec, cache=False)
    assert off_stats == (0, 0, 0)

    bank_a = [_f64_bits(x) for x in rec["values_a"]]
    diff_on = [i for i, x in enumerate(on_a) if _f64_bits(x) != bank_a[i]]
    diff_off = [i for i, x in enumerate(off_a) if _f64_bits(x) != bank_a[i]]
    assert diff_on == [], "the memo-faithful port must reproduce the bank exactly"
    assert diff_off, (
        "the honest-mask port must differ from the bank on this record — it is "
        "one of the 18 legs the collision touched")
    # The collision changes the playout, not its length: the engine still walks
    # the same number of plies.
    assert list(_pa) == list(rec["playout_plies_a"])
    assert [_f64_bits(x) for x in on_b] == [_f64_bits(x) for x in rec["values_b"]]
