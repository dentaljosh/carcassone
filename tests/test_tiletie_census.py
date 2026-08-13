"""Contract tests for scripts/tiletie/ (chain_census.py + run_census.py).

Env MUST be set before any `carcassonne_ai` import — R9 (`CARCASSONNE_FIX_R9`) is
import-latched into a Rust `OnceLock`. The whole suite runs under the `walled`
profile (R9 off) because the CL-070 root bank used for the fidelity fixtures is
walled-profile; `chain_census.prepare_env` / the leaf construction it enables
are otherwise profile-agnostic.

Run: .venv/bin/python -m pytest tests/test_tiletie_census.py -x -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for _rel in ("scripts/tiletie", "scripts/jcz_mining", "scripts/jcz_match",
             "scripts/human_anchor", "scripts/measurement_infra", "scripts/analyzer"):
    _p = str(REPO / _rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import chain_census as CC                                  # noqa: E402

CC.prepare_env("walled")                                    # BEFORE any carcassonne_ai import

import root_replay as RR                                    # noqa: E402

BANK_PATH = Path("/mnt/c/carc-shared/classical_search/move_agreement_k4_b28e9/roots.jsonl")


def _load_bank_roots(n=3):
    rows = []
    if not BANK_PATH.exists():
        return rows
    with BANK_PATH.open() as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("phase") == "TILES":
                rows.append(rec)
            if len(rows) >= n:
                break
    return rows


@pytest.fixture(scope="module")
def leaf():
    leaf_fn, cfg, hashes, bag_close = CC.build_leaf()
    assert hashes.get("harness_leaf_hash") == CC.LEAF_HASH_OF_RECORD
    return leaf_fn


@pytest.fixture(scope="module")
def bank_roots():
    rows = _load_bank_roots(3)
    if len(rows) < 3:
        pytest.skip(f"bank at {BANK_PATH} unavailable or has <3 TILES roots — "
                     "cannot run the fidelity/determinism/schema fixtures")
    return rows


# --------------------------------------------------------------------------- #
# 1. FIDELITY — chain_census.chain_values must be bit-identical to
#    mine_disagreements.chain_values(..., ply_class="TILE") on real positions.
# --------------------------------------------------------------------------- #
def test_chain_values_bit_identical_to_mine_disagreements(bank_roots, leaf):
    """Imports `mine_disagreements` locally (heavy import-time side effects are
    fine inside a test; production code under scripts/tiletie/ never imports
    it — see chain_census.py's module docstring)."""
    import mine_disagreements as MD

    n_compared = 0
    for rec in bank_roots:
        game, board = RR.replay_actions(int(rec["deck_seed"]), rec["actions"], int(rec["ply"]))
        assert game.string_representation(board) == rec["checksum"], (
            "bank replay checksum mismatch — the root does not reconstruct against "
            "this src tree; the fidelity comparison would not be on a real position")
        seat = int(board.state.current_player)

        def bound_leaf(state, _seat=seat):
            return leaf(state, _seat)

        ours = CC.chain_values(game, board, seat, bound_leaf)
        theirs = MD.chain_values(game, board, seat, bound_leaf, "TILE")

        assert len(ours) >= 2, "bank TILES roots are sampled with n_legal>=2"
        assert len(ours) == len(theirs)
        assert [a for a, _v, _c in ours] == [a for a, _v, _c in theirs], (
            "action order (and so the ascending-action contract) diverged")
        for (a1, v1, c1), (a2, v2, c2) in zip(ours, theirs):
            assert a1 == a2
            # `==`, not `pytest.approx` — the brief requires bit-identical floats.
            assert v1 == v2, f"leaf VALUE diverged at action {a1}: {v1!r} != {v2!r}"
            assert c1 == c2, f"chain diverged at action {a1}: {c1!r} != {c2!r}"

        # argmax_chain, the downstream consumer of chain_values, must agree too.
        pick_a, val_a, chain_a, tie_a = CC.argmax_chain(ours)
        pick_b, val_b, chain_b, tie_b = MD.argmax_chain(theirs)
        assert (pick_a, val_a, chain_a, tie_a) == (pick_b, val_b, chain_b, tie_b)

        n_compared += 1
    assert n_compared == len(bank_roots)


def test_chain_values_does_not_mutate_board(bank_roots, leaf):
    """`game_wrapper.Game.get_next_state` is documented "Safe — input board is
    unmodified", and `chain_values` calls it once per legal action from the SAME
    root `board` — if that guarantee ever regressed, `census_ply` would be taking
    its `checksum` (computed before `chain_values` runs, precisely to make this
    class of bug visible rather than silently corrupting a later replay) against
    a board that already changed under it. Assert the checksum is byte-identical
    before and after, on a real position."""
    rec = bank_roots[0]
    game, board = RR.replay_actions(int(rec["deck_seed"]), rec["actions"], int(rec["ply"]))
    before = game.string_representation(board)
    seat = int(board.state.current_player)
    CC.chain_values(game, board, seat, lambda st, _s=seat: leaf(st, _s))
    after = game.string_representation(board)
    assert before == after


# --------------------------------------------------------------------------- #
# 2. tie_report — unit tests on synthetic value lists (no engine needed)         #
# --------------------------------------------------------------------------- #
def test_tie_report_exact_tie():
    values = [(10, 1.0, [10]), (20, 5.0, [20, 21]), (30, 5.0, [30]), (40, 2.0, [40])]
    rep = CC.tie_report(values)
    assert rep["n_cand"] == 4
    assert rep["top1"] == 5.0
    assert rep["top2"] == 2.0
    assert rep["gap"] == pytest.approx(3.0)
    assert rep["tie_exact"] is True
    assert rep["tie_size_exact"] == 2
    assert rep["tie_actions_exact"] == [20, 30]           # ascending
    assert rep["argmax_action"] == 20                     # lowest index of the tied set


def test_tie_report_no_ties():
    values = [(5, 3.0, [5]), (1, 9.0, [1]), (3, 6.0, [3])]
    rep = CC.tie_report(values)
    assert rep["top1"] == 9.0
    assert rep["top2"] == 6.0
    assert rep["gap"] == pytest.approx(3.0)
    assert rep["tie_exact"] is False
    assert rep["tie_size_exact"] == 1
    assert rep["tie_actions_exact"] == [1]
    assert rep["argmax_action"] == 1


def test_tie_report_all_equal():
    values = [(7, 2.0, [7]), (2, 2.0, [2]), (9, 2.0, [9])]
    rep = CC.tie_report(values)
    assert rep["top1"] == 2.0
    assert rep["top2"] is None
    assert rep["gap"] is None
    assert rep["tie_exact"] is True
    assert rep["tie_size_exact"] == 3
    assert rep["tie_actions_exact"] == [2, 7, 9]
    assert rep["argmax_action"] == 2


def test_tie_report_eps_membership_boundaries():
    # top1=10.0; runner-up gaps chosen EXACTLY binary-representable (powers of two
    # halves) so `top1 - value` is bit-exact and the boundary test is not itself
    # at the mercy of float rounding: 0.25, 0.5, 1.0, 4.0.
    values = [(1, 10.0, [1]), (2, 9.75, [2]), (3, 9.5, [3]), (4, 9.0, [4]), (5, 6.0, [5])]
    rep = CC.tie_report(values, eps_grid=(0.0, 0.25, 0.5, 1.0))
    assert rep["by_eps"]["0.0"] == {"tie": False, "size": 1, "actions": [1]}
    # 10.0 - 9.75 == 0.25 -> INCLUSIVE at eps=0.25
    assert rep["by_eps"]["0.25"] == {"tie": True, "size": 2, "actions": [1, 2]}
    # 10.0 - 9.5 == 0.5 -> INCLUSIVE at eps=0.5 (and 2 still qualifies)
    assert rep["by_eps"]["0.5"] == {"tie": True, "size": 3, "actions": [1, 2, 3]}
    # 10.0 - 9.0 == 1.0 -> INCLUSIVE at eps=1.0; 6.0 (gap 4.0) never qualifies
    assert rep["by_eps"]["1.0"] == {"tie": True, "size": 4, "actions": [1, 2, 3, 4]}
    # eps=0.0 reproduces the exact case bit-for-bit
    assert rep["by_eps"]["0.0"]["actions"] == rep["tie_actions_exact"]
    assert rep["by_eps"]["0.0"]["tie"] == rep["tie_exact"]
    assert rep["by_eps"]["0.0"]["size"] == rep["tie_size_exact"]


def test_tie_report_ascending_action_ordering_independent_of_input_order():
    # Fed in DESCENDING / scrambled action-id order on purpose.
    values = [(99, 4.0, [99]), (1, 4.0, [1]), (50, 4.0, [50]), (2, 1.0, [2])]
    rep = CC.tie_report(values)
    assert rep["tie_actions_exact"] == [1, 50, 99]
    assert rep["by_eps"]["0.0"]["actions"] == [1, 50, 99]
    assert rep["argmax_action"] == 1


def test_tie_report_empty_raises():
    with pytest.raises(ValueError):
        CC.tie_report([])


# --------------------------------------------------------------------------- #
# 3. determinism — censusing the same root twice gives identical rows            #
#    (excluding `secs`)                                                          #
# --------------------------------------------------------------------------- #
def test_census_ply_deterministic(bank_roots, leaf):
    rec = bank_roots[0]
    meta = {
        "stratum": "selfplay", "source": "bank", "rules_profile": "walled",
        "game_label": f"bank_{rec['deck_seed']}", "root_id": f"{rec['deck_seed']}_{rec['ply']}",
        "deck_seed": int(rec["deck_seed"]), "ply": int(rec["ply"]),
        "n_plies": len(rec["actions"]),
        "action_played": int(rec["actions"][rec["ply"]]) if rec["ply"] < len(rec["actions"]) else None,
        "h200_top2_q_gap": rec.get("h200_top2_q_gap"),
        "bank_phase_bucket": rec.get("phase_bucket"),
    }

    # `leaf` (the fixture) is the natural 2-arg `leaf(state, seat)` `build_leaf()`
    # returns — `census_ply` binds the seat itself, no wrapping needed here.
    game1, board1 = RR.replay_actions(int(rec["deck_seed"]), rec["actions"], int(rec["ply"]))
    seat1 = int(board1.state.current_player)
    row1 = CC.census_ply(game1, board1, seat1, leaf, meta=meta)

    game2, board2 = RR.replay_actions(int(rec["deck_seed"]), rec["actions"], int(rec["ply"]))
    seat2 = int(board2.state.current_player)
    row2 = CC.census_ply(game2, board2, seat2, leaf, meta=meta)

    row1 = dict(row1); row2 = dict(row2)
    row1.pop("secs"); row2.pop("secs")
    assert row1 == row2


# --------------------------------------------------------------------------- #
# 4. schema — every emitted row has the full documented key set and             #
#    JSON-serialises                                                             #
# --------------------------------------------------------------------------- #
def test_census_ply_schema(bank_roots, leaf):
    for rec in bank_roots:
        game, board = RR.replay_actions(int(rec["deck_seed"]), rec["actions"], int(rec["ply"]))
        seat = int(board.state.current_player)
        meta = {
            "stratum": "selfplay", "source": "bank", "rules_profile": "walled",
            "game_label": f"bank_{rec['deck_seed']}",
            "root_id": f"{rec['deck_seed']}_{rec['ply']}",
            "deck_seed": int(rec["deck_seed"]), "ply": int(rec["ply"]),
            "n_plies": len(rec["actions"]),
            "action_played": (int(rec["actions"][rec["ply"]])
                              if rec["ply"] < len(rec["actions"]) else None),
            "h200_top2_q_gap": rec.get("h200_top2_q_gap"),
            "bank_phase_bucket": rec.get("phase_bucket"),
        }
        row = CC.census_ply(game, board, seat, leaf, meta=meta)

        assert set(row.keys()) == set(CC.ROW_SCHEMA_KEYS)
        # round-trips through JSON with no loss of key set
        rt = json.loads(json.dumps(row))
        assert set(rt.keys()) == set(CC.ROW_SCHEMA_KEYS)
        assert rt["checksum"] == rec["checksum"]
        assert rt["by_eps"].keys() == {str(e) for e in CC.TIE_EPS_GRID}
        for eps_row in rt["by_eps"].values():
            assert set(eps_row.keys()) == {"tie", "size"}
        assert len(rt["tie_actions_exact"]) <= CC.TIE_ACTIONS_CAP
        assert rt["n_legal"] == rt["n_cand"]
        assert rt["phase_bucket"] in ("early", "mid", "late")
        assert rt["tercile"] in (0, 1, 2)


# --------------------------------------------------------------------------- #
# bonus — phase_bucket must be the SAME axis as
# scripts/measurement_infra/sample_agreement_roots.py's own PHASE_CUTS/function
# (GOAL spec: "MUST use the project cuts from sample_agreement_roots.py").
# --------------------------------------------------------------------------- #
def test_phase_bucket_matches_sample_agreement_roots():
    sar_path = REPO / "scripts" / "measurement_infra" / "sample_agreement_roots.py"
    src = sar_path.read_text()
    ns: dict = {}
    # PHASE_CUTS is a plain dict literal near the top of the file; import the whole
    # module would pull in torch/engine imports this test does not need.
    marker = "PHASE_CUTS = "
    start = src.index(marker)
    end = src.index("\n", start)
    exec(src[start:end], {}, ns)  # noqa: S102 (trusted repo file, literal dict only)
    assert ns["PHASE_CUTS"] == CC.PHASE_CUTS
    for k in (0, 1, 5, 10, 14, 20, 24, 25, 30, 40, 47, 48, 49, 60, 100):
        expect = "late"
        for name, (lo, hi) in ns["PHASE_CUTS"].items():
            if lo < k < hi:
                expect = name
                break
        assert CC.phase_bucket(k) == expect, f"k_remaining={k}"
