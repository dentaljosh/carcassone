"""Fast always-on guards for the rustport P3 single-world PUCT search.

The full G3 gate is `scripts/rustport/reconcile_search.py --corpus all` (golden
/ midgame / champ / distill / e4 / det / games at sims 344 and 1376).  These are
the cheap subset plus the unit-level contracts a corpus sweep would only catch
indirectly:

* **the tracer is inert** — a traced search and an untraced `HeuristicPriorAgent`
  produce bit-identical trees.  Without this, the Python leg of the gate could
  drift from `src/carcassonne_ai/` and the gate would grade Rust against a
  private re-implementation;
* **the traces are byte-identical**, not merely "equivalent";
* the two ROOT asymmetries the port has to get right (the `float32` value
  round-trip at the root, the repr-keyed legal-move cache);
* `trace_diff.py` actually *fails* on a mutated trace (a gate that cannot go red
  is not a gate).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "src", REPO / "engine", REPO / "scripts" / "measurement_infra",
           REPO / "scripts" / "rustport"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

carc_rs = pytest.importorskip("carc_rs", reason="build with `maturin develop --release`")

import trace_search as T  # noqa: E402

from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorAgent  # noqa: E402

CHAMP = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
GOLDEN = REPO / "tests" / "golden" / "golden_fixture.json"


@pytest.fixture(scope="module")
def knobs() -> dict:
    return T.production_knobs()


@pytest.fixture(scope="module")
def champ_game() -> dict:
    with open(CHAMP) as fh:
        return json.loads(fh.readline())


def _positions(champ_game, plies):
    for ply in plies:
        yield ply, [int(a) for a in champ_game["actions"]]


# --------------------------------------------------------------------------- #
# Provenance                                                                   #
# --------------------------------------------------------------------------- #
def test_knobs_are_the_champion_of_record(knobs):
    """The gate must grade against PRODUCTION.yaml, not a remembered config."""
    assert knobs["leaf"]["leaf_hash"] == "a36d2e15a3b3d71d"
    assert knobs["c_puct"] == 1.5
    assert knobs["tau_p"] == 5.0
    assert knobs["final_select"] == "visits"
    assert knobs["leaf_quantize"] == "float"
    assert knobs["value_norm"] == 15.0
    assert knobs["score_norm_scale"] == 15.0
    # PRODUCTION.yaml says reuse_tree: true, but it is a documented NO-OP in
    # fair deploy (fresh tree per determinization) — P3 gates the single-world
    # search P4's PIMC drives, so the effective value is False.
    assert knobs["reuse_tree_yaml"] is True
    assert knobs["reuse_tree"] is False


def test_python_leg_uses_the_production_leaf_without_leaking_the_flag(knobs):
    """P3 searches must dispatch to the PRODUCTION leaf, but the flip must be
    SCOPED — `reconcile_leaf`/`test_p2_leaf` require `USE_CY_LEAF is False`
    outside it, and which module imported first must not decide the answer."""
    from carcassonne_ai import flat_leaf

    assert T._PROD_USE_CY_LEAF is True, "the Cython leaf is not the production path here"
    before = flat_leaf.USE_CY_LEAF
    with T.production_leaf_dispatch():
        assert flat_leaf.USE_CY_LEAF is True
    assert flat_leaf.USE_CY_LEAF is before, "trace_search leaked the dispatch flag"


# --------------------------------------------------------------------------- #
# The tracer is inert                                                          #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("ply", [0, 30, 70])
def test_tracer_does_not_change_the_search(knobs, champ_game, ply):
    """A traced search == the untouched `HeuristicPriorAgent`, bit for bit."""
    cfg = T.py_config(knobs)
    actions = [int(a) for a in champ_game["actions"]]
    seed = int(champ_game["deck_seed"])

    game, board = T.py_state(seed, actions, ply)
    plain = HeuristicPriorAgent(game=game, cfg=cfg, simulations=96, seed=None)
    chosen_plain = int(plain.move(board))
    root_plain = plain.mcts._nodes[game.string_representation(board)]
    want = sorted((int(a), int(c.N), T.ubits(c.W)) for a, c in root_plain.children.items())

    game2, board2 = T.py_state(seed, actions, ply)
    got = T.py_search_single(game2, board2, cfg, 96)

    assert got["chosen_action"] == chosen_plain
    assert [tuple(x) for x in got["root_children"]] == want
    assert got["root_n"] == int(root_plain.N)
    assert got["root_w_bits"] == T.ubits(root_plain.W)
    assert got["node_count"] == len(plain.mcts._nodes)


# --------------------------------------------------------------------------- #
# Rust == Python                                                               #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("ply,sims", [(0, 32), (24, 128), (60, 128), (100, 64)])
def test_rust_matches_python_on_champ_positions(knobs, champ_game, ply, sims):
    cfg = T.py_config(knobs)
    actions = [int(a) for a in champ_game["actions"]]
    seed = int(champ_game["deck_seed"])
    game, board = T.py_state(seed, actions, ply)
    ms = T.rs_state(seed, actions, ply)
    assert game.string_representation(board) == ms.string_repr()

    py = T.py_search_single(game, board, cfg, sims)
    rs = ms.search_single(T.rs_config(sims, knobs))
    assert py["chosen_action"] == rs["chosen_action"]
    assert [tuple(x) for x in py["root_children"]] == [tuple(x) for x in rs["root_children"]]
    assert [tuple(x) for x in py["deduped"]] == [tuple(x) for x in rs["deduped"]]
    assert [tuple(x) for x in py["root_priors"]] == [tuple(x) for x in rs["root_priors"]]
    assert py["root_n"] == rs["root_n"]
    assert py["root_w_bits"] == rs["root_w_bits"]
    assert py["root_leaf_value_bits"] == rs["root_leaf_value_bits"]
    assert py["node_count"] == rs["node_count"]


def test_root_leaf_value_takes_the_float32_round_trip(knobs, champ_game):
    """`search()` expands the root through `_eval_boards`, which packs the value
    into a `float32` array; `_expand` (interior) does not.  If the port ever
    "fixes" that asymmetry this test goes red — the root value would stop being
    representable as a float32."""
    import struct

    cfg = T.py_config(knobs)
    actions = [int(a) for a in champ_game["actions"]]
    seed = int(champ_game["deck_seed"])
    checked = 0
    for ply in (10, 40, 80):
        game, board = T.py_state(seed, actions, ply)
        py = T.py_search_single(game, board, cfg, 8)
        v = struct.unpack("<d", struct.pack("<Q", py["root_leaf_value_bits"]))[0]
        assert v == struct.unpack("<f", struct.pack("<f", v))[0], (
            f"root leaf_value {v!r} is not float32-representable at ply {ply}")
        checked += 1
    assert checked == 3


def test_deck_determinization_agrees_on_both_legs(knobs, champ_game):
    """The P4 surface: swap the UNSEEN deck for one permutation on both legs."""
    import random

    cfg = T.py_config(knobs)
    actions = [int(a) for a in champ_game["actions"]]
    seed = int(champ_game["deck_seed"])
    game, board = T.py_state(seed, actions, 50)
    ms = T.rs_state(seed, actions, 50)

    src = list(board.state.deck)
    descs = [t.description for t in src]
    assert descs == list(ms.unseen_deck())
    perm = list(range(len(src)))
    random.Random(7).shuffle(perm)
    board.state.deck[:] = [src[i] for i in perm]
    board._str_repr_cache = None
    ms.set_unseen_deck([descs[i] for i in perm])

    py = T.py_search_single(game, board, cfg, 128)
    rs = ms.search_single(T.rs_config(128, knobs))
    assert py["chosen_action"] == rs["chosen_action"]
    assert [tuple(x) for x in py["root_children"]] == [tuple(x) for x in rs["root_children"]]


def test_wrong_deck_length_is_refused(knobs, champ_game):
    ms = T.rs_state(int(champ_game["deck_seed"]),
                    [int(a) for a in champ_game["actions"]], 50)
    with pytest.raises(ValueError):
        ms.set_unseen_deck(list(ms.unseen_deck())[:-1])


# --------------------------------------------------------------------------- #
# The trace harness                                                            #
# --------------------------------------------------------------------------- #
def test_traces_are_byte_identical(knobs, champ_game, tmp_path):
    cfg = T.py_config(knobs)
    actions = [int(a) for a in champ_game["actions"]]
    seed = int(champ_game["deck_seed"])
    game, board = T.py_state(seed, actions, 44)
    ms = T.rs_state(seed, actions, 44)

    py_t, rs_t = tmp_path / "py.jsonl", tmp_path / "rs.jsonl"
    T.py_search_single(game, board, cfg, 150, trace_path=py_t)
    ms.search_single(T.rs_config(150, knobs), str(rs_t), True)

    a, b = py_t.read_bytes(), rs_t.read_bytes()
    assert a == b, "traces diverge; run scripts/rustport/trace_diff.py to bisect"
    lines = a.decode().strip().split("\n")
    assert sum(1 for line in lines if '"t":"sim"' in line) == 150
    assert any('"t":"exp"' in line for line in lines)


def test_trace_diff_reports_identical_and_catches_a_mutation(knobs, champ_game, tmp_path):
    """A gate that cannot go red is not a gate."""
    cfg = T.py_config(knobs)
    actions = [int(a) for a in champ_game["actions"]]
    seed = int(champ_game["deck_seed"])
    game, board = T.py_state(seed, actions, 20)
    ms = T.rs_state(seed, actions, 20)
    py_t, rs_t = tmp_path / "py.jsonl", tmp_path / "rs.jsonl"
    T.py_search_single(game, board, cfg, 64, trace_path=py_t)
    ms.search_single(T.rs_config(64, knobs), str(rs_t), True)

    tool = [sys.executable, str(REPO / "scripts" / "rustport" / "trace_diff.py")]
    ok = subprocess.run(tool + [str(py_t), str(rs_t)], capture_output=True, text=True)
    assert ok.returncode == 0 and "IDENTICAL" in ok.stdout

    # Flip ONE bit of ONE prior in the Rust trace.
    lines = rs_t.read_text().split("\n")
    for i, line in enumerate(lines):
        if '"t":"exp"' in line and '"pr":["' in line:
            head, _, tail = line.partition('"pr":["')
            lines[i] = head + '"pr":["' + ("f" + tail[1:] if tail[0] != "f" else "0" + tail[1:])
            break
    else:  # pragma: no cover
        pytest.fail("no expansion record with priors in the trace")
    rs_t.write_text("\n".join(lines))

    bad = subprocess.run(tool + [str(py_t), str(rs_t)], capture_output=True, text=True)
    assert bad.returncode == 1
    assert "DIVERGED" in bad.stdout
    assert "LIKELY CULPRIT" in bad.stdout


# --------------------------------------------------------------------------- #
# Non-production branches of the port (the gate legs all run production knobs)  #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("final_select", ["visits", "Q", "lcb"])
def test_every_final_select_branch_agrees(knobs, champ_game, final_select):
    cfg = T.py_config(knobs, final_select=final_select)
    actions = [int(a) for a in champ_game["actions"]]
    seed = int(champ_game["deck_seed"])
    for ply in (12, 48, 90):
        game, board = T.py_state(seed, actions, ply)
        ms = T.rs_state(seed, actions, ply)
        py = T.py_search_single(game, board, cfg, 96)
        rs = ms.search_single(T.rs_config(96, knobs, final_select=final_select))
        assert py["chosen_action"] == rs["chosen_action"], f"{final_select}@{ply}"
        assert [tuple(x) for x in py["root_children"]] == \
               [tuple(x) for x in rs["root_children"]]


def test_int_leaf_quantize_branch_agrees(knobs, champ_game):
    """`leaf_quantize='int'` is not the champion, but it is a live code path."""
    cfg = T.py_config(knobs, leaf_quantize="int")
    actions = [int(a) for a in champ_game["actions"]]
    seed = int(champ_game["deck_seed"])
    for ply in (20, 70):
        game, board = T.py_state(seed, actions, ply)
        ms = T.rs_state(seed, actions, ply)
        py = T.py_search_single(game, board, cfg, 96)
        rs = ms.search_single(T.rs_config(96, knobs, leaf_quantize="int"))
        assert py["chosen_action"] == rs["chosen_action"], f"int@{ply}"
        assert [tuple(x) for x in py["root_children"]] == \
               [tuple(x) for x in rs["root_children"]]


def test_terminal_endgame_positions_agree(knobs, champ_game):
    """The last plies exercise `get_game_ended` (tanh(diff/15)) and the terminal
    backup — where a terminal child's value, not the leaf, is what propagates."""
    cfg = T.py_config(knobs)
    actions = [int(a) for a in champ_game["actions"]]
    seed = int(champ_game["deck_seed"])
    n = 0
    for ply in range(max(0, len(actions) - 10), len(actions)):
        game, board = T.py_state(seed, actions, ply)
        if board.state.is_terminated():
            continue
        ms = T.rs_state(seed, actions, ply)
        py = T.py_search_single(game, board, cfg, 64)
        rs = ms.search_single(T.rs_config(64, knobs))
        assert py["chosen_action"] == rs["chosen_action"], f"end@{ply}"
        assert [tuple(x) for x in py["root_children"]] == \
               [tuple(x) for x in rs["root_children"]], f"end@{ply}"
        n += 1
    assert n >= 5


def test_golden_fixture_positions_agree(knobs):
    """A handful of golden-fixture positions, both legs, small budget."""
    fx = json.loads(GOLDEN.read_text())
    cfg = T.py_config(knobs)
    n = 0
    for seed_s, g in sorted(fx["games"].items(), key=lambda kv: int(kv[0]))[:4]:
        seed = int(g.get("deck_seed", seed_s))
        actions = [int(a) for a in g["actions"]]
        for ply in (0, len(actions) // 2, max(0, len(actions) - 4)):
            game, board = T.py_state(seed, actions, ply)
            if board.state.is_terminated():
                continue
            ms = T.rs_state(seed, actions, ply)
            py = T.py_search_single(game, board, cfg, 48)
            rs = ms.search_single(T.rs_config(48, knobs))
            assert py["chosen_action"] == rs["chosen_action"], f"{seed}@{ply}"
            assert [tuple(x) for x in py["root_children"]] == \
                   [tuple(x) for x in rs["root_children"]], f"{seed}@{ply}"
            n += 1
    assert n >= 8
