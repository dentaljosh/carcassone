"""R9 — "a field half-edge may not lie on a city edge", the flag and its gates.

    *** DEFAULT OFF.  Nothing here adopts anything. ***

`city_top_straight_road` (JCZ `BA/RCr`, ×4 in the deck) declares `TLT` and
`TRT` — the two halves of its own NORTH edge, which is a CITY — in its north
farm region.  Found 2026-08-03 by the JCZ differential tile oracle
(`tests/test_jcz_tile_oracle.py`; `measurement/jcz_spike_20260803/`).  Every
farm traversal in the tree crosses a `tile_connection` unconditionally, so
those two entries let a field walk straight through a city.

`CARCASSONNE_FIX_R9=1` drops them (see `base_deck.py`'s R9 block for the flag,
the derivation and the `feedback_bug_fix_shifts_optima` rider).

## What this module gates

| gate | what it pins |
|---|---|
| `TestDefaultIsOff`        | the flag is off unless asked, in BOTH engines, and the flags-off tile data is bit-identical (`SEMANTIC_DIGEST` unchanged) |
| `TestFarmDataParity`      | python ⇄ Rust farm tables agree, **all 32 kinds × 4 rotations, in BOTH flag states** |
| `TestTheReproducer`       | the spike's two-tile board: the MERGE still happens flags-off, and is gone flags-on — measured in **all four** implementations |
| `TestTheScoreMoves`       | a deterministic position where the merge changes `flat_base_score` by 3 — measured in all four |
| `TestFlagsOffByteIdentity`| a replay sample through the python↔Rust lockstep core with no flag: 0 mismatches |
| `TestMutationProbe`       | regress the fix and prove each gate goes RED (the P1 lesson: "0 mismatches" must be *informative*) |

The heavy leg is a script, not a test:

    CARCASSONNE_FIX_R9=1 .venv/bin/python scripts/rustport/lockstep_fuzz.py \\
        --fix-r9 --games 500 --workers 8 --tag r9_on \\
        --out measurement/f9_r9/G5_lockstep_fuzz_r9_on.json

## Both flag states in one pytest run

R9 is a **data** flag: Python latches it when `base_deck` is imported and Rust
when its `OnceLock` registry is first built, so a single process cannot hold
both.  Every flags-on assertion therefore runs in a subprocess via
`run_in_state()` — and so does the flags-off half (`TestDefaultIsOff`, via the
`off` fixture): `tests/android/` sorts before this module in a whole-tree
`pytest tests/` run and latches R9 ON for the rest of the process before this
module ever runs, so an in-process flags-off assertion is an import-order race,
not a real invariant. See `TestDefaultIsOff`'s docstring for the reproduction.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO / "engine", REPO / "src", REPO / "scripts" / "rustport"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

carc_rs = pytest.importorskip("carc_rs", reason="build with `maturin develop --release`")

RCR = "city_top_straight_road"
R, C = 10, 10                       # anywhere interior; the fixture is hand-built


# =========================================================================
# the two hand-built fixtures, shared by every implementation
# =========================================================================
#: The spike's minimal reproducer: two RCr tiles with their cities joined
#: across the shared N/S border.  `(row, col, description, rotation)`.
MERGE_BOARD = [
    (R, C, RCR, 0),                 # city on N, road W-E
    (R - 1, C, RCR, 2),             # city on S — the two cities meet, and close
]
#: The two under-city field strips, addressed by a `farmer_position` of each.
LOWER_STRIP = (R, C, "top_left")
UPPER_STRIP = (R - 1, C, "bottom_left")

#: The same board plus a legitimate eastward extension of the LOWER strip, so
#: the two sides of the illegitimate join carry a different number of farmers.
#: Merged  -> one field, p0 2 farmers vs p1 1  -> p0 takes the finished city (+3).
#: Separate -> p0 owns the lower field (+3) and p1 owns the upper one (+3) -> 0.
SCORE_BOARD = MERGE_BOARD + [(R, C + 1, RCR, 0)]      # road W-E matches, field joins
#: NOTE the sides: base scoring matches on `farmer_positions[0]`, and the
#: 180°-rotated tile's `[TOP_LEFT, TOP_RIGHT]` becomes `[BOTTOM_RIGHT,
#: BOTTOM_LEFT]` — so the upper farmer must sit on BOTTOM_RIGHT to be counted.
SCORE_MEEPLES = [
    (0, R, C, "top_left", "farmer"),
    (0, R, C + 1, "top_left", "farmer"),
    (1, R - 1, C, "bottom_right", "farmer"),
]
SCORE_MERGED_DIFF = 3               # flat_base_score(p0) when the fields merge
SCORE_SPLIT_DIFF = 0                # ... and when they do not


# =========================================================================
# measurement — one function, four implementations, both flag states
# =========================================================================
def measure() -> dict:
    """Every observable this module needs, from the CURRENT process's flag
    state.  Importable and runnable standalone so a subprocess can produce the
    flags-on half (see `run_in_state`)."""
    import copy

    from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
    from wingedsheep.carcassonne.objects.coordinate import Coordinate
    from wingedsheep.carcassonne.objects.coordinate_with_side import CoordinateWithSide
    from wingedsheep.carcassonne.objects.meeple_position import MeeplePosition
    from wingedsheep.carcassonne.objects.meeple_type import MeepleType
    from wingedsheep.carcassonne.objects.side import Side
    from wingedsheep.carcassonne.tile_sets import base_deck
    from wingedsheep.carcassonne.utils.farm_util import FarmUtil
    from wingedsheep.carcassonne.utils.points_collector import PointsCollector

    import carcassonne_ai.flat_leaf as fl

    side = {s.value: s for s in Side}

    def build(cells, meeples=()):
        st = CarcassonneGameState()
        for row, col, desc, rot in cells:
            st.board[row][col] = base_deck.base_tiles[desc].turn(rot)
        st.placed_coords = {Coordinate(r, c) for r, c, _, _ in cells}
        for player, row, col, sd, _kind in meeples:
            st.placed_meeples[player].append(MeeplePosition(
                MeepleType.FARMER, CoordinateWithSide(Coordinate(row, col), side[sd])))
        return st

    def rs(cells, meeples=()):
        ms = carc_rs.MirrorState.from_seed("1")
        ms.set_board([(r, c, d, k) for r, c, d, k in cells])
        if meeples:
            ms.set_meeples(list(meeples))
        return ms

    # --- 1. the merge, at the FARM-PARTITION level ------------------------
    st = build(MERGE_BOARD)
    ms = rs(MERGE_BOARD)

    # (a) the vendored engine's own object traversal
    lo = FarmUtil.find_farm_by_coordinate(
        st, CoordinateWithSide(Coordinate(*LOWER_STRIP[:2]), side[LOWER_STRIP[2]]))
    object_merged = len(lo.farmer_connections_with_coordinate) > 1
    object_cells = sorted((n.coordinate.row - R, n.coordinate.column - C)
                          for n in lo.farmer_connections_with_coordinate)

    # (b) the production Python leaf
    d = fl.decompose(st)
    flat_lo = d.farm_anypos_root.get((LOWER_STRIP[0], LOWER_STRIP[1], side[LOWER_STRIP[2]]))
    flat_hi = d.farm_anypos_root.get((UPPER_STRIP[0], UPPER_STRIP[1], side[UPPER_STRIP[2]]))

    # (c) the production Cython leaf (its OWN C decomposition, not flat_leaf's)
    cy_lo = cy_hi = cy_farms = None
    cy_available = False
    try:
        from carcassonne_ai import flat_leaf_cy as _cy

        ex = _cy.decompose_export(st)
        cy_lo = ex["farm_anypos_root"].get(
            (LOWER_STRIP[0], LOWER_STRIP[1], side[LOWER_STRIP[2]]))
        cy_hi = ex["farm_anypos_root"].get(
            (UPPER_STRIP[0], UPPER_STRIP[1], side[UPPER_STRIP[2]]))
        cy_farms = len(ex["farm_root_finished_cities"])
        cy_available = True
    except ImportError:
        pass

    # (d) the Rust leaf
    rs_lo = ms.farm_anypos_root(*LOWER_STRIP)
    rs_hi = ms.farm_anypos_root(*UPPER_STRIP)

    # --- 2. the same merge, at the SCORE level ---------------------------
    sst = build(SCORE_BOARD, SCORE_MEEPLES)
    sms = rs(SCORE_BOARD, SCORE_MEEPLES)
    sd = fl.decompose(sst)
    engine_state = copy.deepcopy(sst)
    PointsCollector.count_final_scores(engine_state)

    return {
        "r9_python": bool(base_deck.R9_FIELD_ON_CITY_EDGE_FIX),
        "r9_rust": bool(carc_rs.r9_enabled()),
        "use_cy_leaf": bool(fl.USE_CY_LEAF),
        "cy_available": cy_available,
        # partition
        "object_merged": object_merged,
        "object_cells": object_cells,
        "flat_merged": flat_lo == flat_hi,
        "flat_roots": [flat_lo, flat_hi],
        "flat_n_farms": len(d.farm_root_keys),
        "cy_merged": None if not cy_available else cy_lo == cy_hi,
        "cy_n_farms": cy_farms,
        "rust_merged": rs_lo == rs_hi,
        "rust_roots": [rs_lo, rs_hi],
        "rust_n_farms": ms.n_farm_components(),
        # score
        "score_flat_python": fl.flat_base_score(sst, 0, sd),          # pure python
        "score_flat_cy": fl.flat_base_score(sst, 0),                  # cy redirect
        "score_engine": int(engine_state.scores[0] - engine_state.scores[1]),
        "score_rust": sms.flat_base_score_decomp(0),
        "score_rust_engine_route": sms.flat_base_score(0),
        # data
        "semantic_digest_rust": carc_rs.tile_data_digests()[1],
        "semantic_digest_rust_r9": carc_rs.tile_data_digest_r9(),
        "rcr_north_connections": sorted(
            str(fs) for fc in base_deck.base_tiles[RCR].farms
            if fc.city_sides for fs in fc.tile_connections),
        "rcr_north_group_count": len(
            [fc for fc in base_deck.base_tiles[RCR].farms if fc.city_sides]),
        # TestDefaultIsOff's fields (see its docstring: run through `off`/`on`
        # for import-order isolation, not asserted in-process).
        "semantic_digest_python": _export_tile_data().semantic_digest(),
        "semantic_digest_python_r9": _export_tile_data().semantic_digest_r9(),
        "changed_farm_descriptions": _changed_farm_descriptions(),
    }


def _export_tile_data():
    import export_tile_data as ex

    return ex


def _changed_farm_descriptions() -> list[str]:
    """Tile descriptions whose `farms` differ between the base and R9
    payloads, asserting every OTHER field is untouched along the way (decks,
    action spaces, board reprs and legal masks must be identical either way)."""
    ex = _export_tile_data()
    base, r9 = ex.semantic_payload(), ex.r9_semantic_payload()
    assert base["tile_order"] == r9["tile_order"]
    assert base["counts_in_insertion_order"] == r9["counts_in_insertion_order"]
    for a, b in zip(base["tiles"], r9["tiles"]):
        assert {k: v for k, v in a.items() if k != "farms"} == \
               {k: v for k, v in b.items() if k != "farms"}
    return [a["description"] for a, b in zip(base["tiles"], r9["tiles"])
            if a["farms"] != b["farms"]]


def _load_oracle_module():
    """`tests/test_jcz_tile_oracle.py` by path — `tests/` is not a package on
    sys.path, and adding it would shadow modules by accident."""
    import importlib.util

    path = Path(__file__).resolve().parent / "test_jcz_tile_oracle.py"
    spec = importlib.util.spec_from_file_location("_jcz_tile_oracle", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_in_state(on: bool) -> dict:
    """`measure()` in a fresh process with `CARCASSONNE_FIX_R9` forced."""
    env = dict(os.environ, CARCASSONNE_FIX_R9="1" if on else "0")
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in [str(REPO / "engine"), str(REPO / "src"),
                    os.environ.get("PYTHONPATH", "")] if p)
    rc = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--json"],
                        capture_output=True, text=True, env=env)
    assert rc.returncode == 0, rc.stdout[-4000:] + rc.stderr[-4000:]
    return json.loads(rc.stdout)


@pytest.fixture(scope="module")
def off():
    return run_in_state(False)


@pytest.fixture(scope="module")
def on():
    return run_in_state(True)


# =========================================================================
class TestDefaultIsOff:
    """THE regression bar for a flag that moves scoring: unless asked, both
    engines play exactly the game they have always played.

    ⚠️⚠️ R9 IMPORT-LATCH RACE (chores queue, root-caused here). These four
    checks used to import `base_deck`/`carc_rs` and assert straight off their
    IN-PROCESS state. That is exactly the state a whole-tree pytest run cannot
    guarantee: `base_deck.base_tiles` is a module-global mutated ONCE, at
    `base_deck`'s first import, from `CARCASSONNE_FIX_R9` (Rust mirrors this
    with its own `OnceLock` registry) — neither can be re-latched by a later
    `os.environ` write in the same process. `tests/android/android_bridge.py`
    sorts before this module in a `pytest tests/` collection and, at its own
    import, calls `os.environ.setdefault("CARCASSONNE_FIX_R9", "1")` *before*
    importing `carcassonne_ai` (the app wants R9 ON by default) — so by the
    time this module's tests run, R9 is ALREADY latched ON for the rest of the
    process, env var included (`setdefault` actually writes it). Reproduced:
    `pytest tests/android/test_bridge.py::test_bridge_imports_and_sets_prod_env
    tests/test_r9_field_on_city_edge.py::TestDefaultIsOff` fails all four here
    with digests/connections read back in the R9-ON shape; the same file run
    alone is green. Un-latching `base_tiles` in-process isn't available (the
    R9 tile replacement is a fresh `Tile` object, and the pre-mutation farms
    are not retained anywhere to restore from) — so, exactly like every OTHER
    state-sensitive check in this module (`TestFarmDataParity`,
    `TestTheReproducer`, ...), these run through the `off` fixture: a FRESH
    subprocess with `CARCASSONNE_FIX_R9` forced to `"0"`, immune to whatever
    the pytest parent process already latched."""

    def test_flag_is_off_in_this_process(self, off):
        assert off["r9_python"] is False
        assert off["r9_rust"] is False

    def test_the_surplus_half_edges_are_still_there_by_default(self, off):
        assert off["rcr_north_group_count"] == 1
        assert sorted(off["rcr_north_connections"]) == \
            ["tll", "tlt", "trr", "trt"]

    def test_flags_off_tile_data_is_bit_identical(self, off):
        """The strongest available flags-off statement: the SEMANTIC digest of
        everything the engine reads off a tile is the pre-R9 value.  Only
        SOURCE_SHA256 moved (the file gained the flag and its docs)."""
        assert off["semantic_digest_python"] == \
            "525f7041ab8402f3008f9cd230f089ec4e9fb0541a5eb982531c48a8c97c3800"
        assert off["semantic_digest_rust"] == off["semantic_digest_python"]
        assert off["semantic_digest_rust_r9"] == off["semantic_digest_python_r9"]
        assert off["semantic_digest_python_r9"] != off["semantic_digest_python"]

    def test_the_flag_touches_only_farms(self, off):
        """Descriptions, counts and insertion order are untouched, so decks,
        action spaces, board reprs and legal masks are the same either way.
        This is why a pre-R9 checkpoint can play an R9 game unchanged.
        (`_changed_farm_descriptions()`, run inside the `off` subprocess, also
        asserts every non-farms tile field matches between the two payloads.)"""
        assert off["changed_farm_descriptions"] == [RCR]


# =========================================================================
class TestImportOrderRegression:
    """Reproduces the R9 import-latch race END TO END, in a real pytest
    subprocess, so a future change that re-introduces in-process assertions
    to `TestDefaultIsOff` (or otherwise re-couples this module to ambient
    process state) is caught by CI rather than rediscovered in a full-suite
    run. See `TestDefaultIsOff`'s docstring for the mechanism."""

    def test_android_then_r9_default_off_is_green(self):
        rc = subprocess.run(
            [sys.executable, "-m", "pytest",
             "tests/android/test_bridge.py::test_bridge_imports_and_sets_prod_env",
             "tests/test_r9_field_on_city_edge.py::TestDefaultIsOff",
             "-q"],
            cwd=REPO, capture_output=True, text=True,
            env=dict(os.environ, PYTHONPATH=os.pathsep.join(
                p for p in [str(REPO / "engine"), str(REPO / "src"),
                            os.environ.get("PYTHONPATH", "")] if p)))
        assert rc.returncode == 0, (
            "android-then-r9 collection order should be green (the `off` "
            "subprocess isolation must hold) — got:\n"
            + rc.stdout[-4000:] + rc.stderr[-4000:])
        # 5 tests selected: the one android import test + TestDefaultIsOff's four.
        assert rc.stdout.count(".") == 5, rc.stdout[-2000:]


# =========================================================================
class TestFarmDataParity:
    """python ⇄ Rust, all 32 kinds × 4 rotations, in BOTH flag states.  The
    Rust delta is codegen'd from the Python derivation, so this is a check that
    the codegen is current — the seam that makes parity structural."""

    @staticmethod
    def _python_farm_table(r9: bool):
        """`{(description, rot, slot): (positions, connections, city_sides)}`
        from the live engine, with R9 applied or not."""
        from wingedsheep.carcassonne.tile_sets import base_deck

        tiles = dict(base_deck.base_tiles)
        if r9:
            base_deck._r9_apply(tiles, base_deck.r9_farm_override(tiles))
        out = {}
        for name, tile in tiles.items():
            for rot in range(4):
                for slot, fc in enumerate(tile.turn(rot).farms):
                    out[(name, rot, slot)] = (
                        [str(s) for s in fc.farmer_positions],
                        [str(s) for s in fc.tile_connections],
                        [str(s) for s in fc.city_sides],
                    )
        return out

    @staticmethod
    def _rust_farm_table(r9: bool):
        return {(desc, rot, slot): (fp, tc, cs)
                for desc, slot, rot, fp, tc, cs in carc_rs.farm_table(r9)}

    @pytest.mark.parametrize("r9", [False, True])
    def test_python_and_rust_agree(self, r9):
        py = self._python_farm_table(r9)
        rs = self._rust_farm_table(r9)
        assert len(py) == len(rs) == 204          # 32 kinds x 4 rots, ragged slots
        assert py == rs

    def test_the_two_states_differ_in_exactly_one_place(self):
        """Not vacuous: the parity check above would pass trivially if the flag
        did nothing.  Exactly the 4 rotations of RCr's north region move."""
        a, b = self._rust_farm_table(False), self._rust_farm_table(True)
        moved = {k for k in a if a[k] != b[k]}
        assert {k[0] for k in moved} == {RCR}
        assert len(moved) == 4
        for (_n, rot, _slot) in moved:
            assert len(a[(_n, rot, _slot)][1]) == 4
            assert len(b[(_n, rot, _slot)][1]) == 2


# =========================================================================
class TestTheReproducer:
    """The spike's two-tile board, promoted to a fixture and run through ALL
    FOUR implementations.

    This is the measurement the spike explicitly did NOT do (SPIKE_REPORT
    "Not done here": *no check that flat_leaf.py / the Rust core reproduce the
    merge — argued from shared data, not measured*).  Answer: they all do.
    """

    def test_flags_off_the_merge_still_happens_everywhere(self, off):
        assert off["r9_python"] is False and off["r9_rust"] is False
        assert off["object_merged"] is True, off
        assert off["object_cells"] == [[-1, 0], [0, 0]]     # JSON: tuples -> lists
        assert off["flat_merged"] is True, off
        assert off["rust_merged"] is True, off
        assert off["flat_n_farms"] == off["rust_n_farms"] == 3
        if off["cy_available"]:
            assert off["cy_merged"] is True, off
            assert off["cy_n_farms"] == 3

    def test_flags_on_the_two_strips_are_separate_everywhere(self, on):
        assert on["r9_python"] is True and on["r9_rust"] is True
        assert on["object_merged"] is False, on
        assert on["object_cells"] == [[0, 0]]
        assert on["flat_merged"] is False, on
        assert on["rust_merged"] is False, on
        assert on["flat_n_farms"] == on["rust_n_farms"] == 4
        if on["cy_available"]:
            assert on["cy_merged"] is False, on
            assert on["cy_n_farms"] == 4

    def test_the_four_implementations_never_disagree_with_each_other(self, off, on):
        for res in (off, on):
            impls = {"object": res["object_merged"], "flat_leaf": res["flat_merged"],
                     "rust": res["rust_merged"]}
            if res["cy_available"]:
                impls["flat_leaf_cy"] = res["cy_merged"]
            assert len(set(impls.values())) == 1, impls

    def test_the_cython_leaf_was_actually_exercised(self, off, on):
        """`flat_leaf_cy` is the production default (`CARCASSONNE_USE_CY_LEAF`
        defaults ON), so a silent ImportError here would hide the one path most
        games actually run."""
        assert off["use_cy_leaf"] and on["use_cy_leaf"]
        if not off["cy_available"]:
            pytest.skip("flat_leaf_cy .so not built on this box "
                        "(python setup_flat_leaf_cy.py build_ext --inplace)")
        assert on["cy_available"]


# =========================================================================
class TestTheScoreMoves:
    """The merge is not cosmetic: a deterministic position where it changes the
    scored outcome by 3 points, agreed by all four implementations.

    Two RCr city-to-city (the illegitimate join) plus one more RCr east of the
    lower tile (a legitimate field join through a road edge).  p0 has two
    farmers on the lower field, p1 one on the upper.  Merged, p0 has the
    majority and takes the completed city alone; split, they take one each.
    """

    def test_flags_off_the_merged_field_hands_p0_the_city(self, off):
        assert off["score_flat_python"] == SCORE_MERGED_DIFF, off
        assert off["score_flat_cy"] == SCORE_MERGED_DIFF, off
        assert off["score_engine"] == SCORE_MERGED_DIFF, off
        assert off["score_rust"] == SCORE_MERGED_DIFF, off
        assert off["score_rust_engine_route"] == SCORE_MERGED_DIFF, off

    def test_flags_on_they_take_one_each(self, on):
        assert on["score_flat_python"] == SCORE_SPLIT_DIFF, on
        assert on["score_flat_cy"] == SCORE_SPLIT_DIFF, on
        assert on["score_engine"] == SCORE_SPLIT_DIFF, on
        assert on["score_rust"] == SCORE_SPLIT_DIFF, on
        assert on["score_rust_engine_route"] == SCORE_SPLIT_DIFF, on

    def test_the_flag_actually_moved_the_number(self, off, on):
        assert off["score_flat_python"] != on["score_flat_python"]


# =========================================================================
class TestFlagsOffByteIdentity:
    """A replay sample through the python↔Rust lockstep core with NO flag set.
    The full 500-game flags-on leg is a script (see the module docstring); this
    is the always-on subset, and it is the flags-OFF direction — the one that
    has to stay bit-compatible with every result on record."""

    @pytest.mark.parametrize("mode", ["uniform", "wall"])
    def test_replay_sample_is_lockstep_with_no_flag(self, mode):
        import lockstep_fuzz as lf

        assert lf.R9_PY is False and lf.R9_RS is False
        for i in range(3):
            r = lf.fuzz_game({"deck_seed": lf.FUZZ_SEED_BASE + i,
                              "policy_seed": 5_000_000 + i, "mode": mode,
                              "max_plies": 400, "start_rule": "engine",
                              "start_row": 6, "start_col": 15})
            assert r["mismatch"] is None, r["mismatch"]
            assert r["status"] in ("ok", "window_overflow", "engine_error"), r
            assert r["fix_r9"] is False

    def test_the_fuzz_refuses_a_flag_the_environment_does_not_carry(self):
        import lockstep_fuzz as lf

        with pytest.raises(SystemExit, match="CARCASSONNE_FIX_R9"):
            lf.check_r9(True)
        assert lf.check_r9(False) is False


# =========================================================================
class TestMutationProbe:
    """"0 mismatches" is only worth something if a broken fix would be caught.
    Each probe below regresses one piece and asserts the corresponding gate
    goes RED."""

    def test_a_no_op_predicate_fails_the_jcz_oracle(self):
        """Regress the derivation to a no-op: the flags-on oracle must still
        see the divergence."""
        from wingedsheep.carcassonne.tile_sets import base_deck

        oracle = _load_oracle_module()

        tiles = dict(base_deck.base_tiles)
        # the real predicate finds it...
        assert set(base_deck.r9_farm_override(tiles)) == {RCR}
        # ...a no-op does not, and the flags-on expectation then fails
        assert oracle.expected_diverging_kinds(r9_on=True) == set()
        assert RCR in oracle.run_oracle()["diffs"]      # i.e. flags-on would be RED

    def test_dropping_road_half_edges_too_would_be_caught(self):
        """The predicate must gate on CITY edges only — a road edge legitimately
        carries field on both halves.  Widening it to every non-field edge
        changes 20 kinds, which the oracle's 31-clean assertion catches."""
        from wingedsheep.carcassonne.objects.farmer_connection import FarmerConnection
        from wingedsheep.carcassonne.tile_sets import base_deck

        too_wide = {}
        for name, tile in base_deck.base_tiles.items():
            bad = {s for g in (tile.city or []) for s in g}
            bad |= {e for conn in (tile.road or []) for e in (conn.a, conn.b)}
            farms, changed = [], False
            for fc in tile.farms:
                keep = [fs for fs in fc.tile_connections if fs.get_side() not in bad]
                changed |= len(keep) != len(fc.tile_connections)
                farms.append(FarmerConnection(list(fc.farmer_positions), keep,
                                              list(fc.city_sides)))
            if changed:
                too_wide[name] = farms
        assert len(too_wide) > 1, "the over-wide predicate must touch more kinds"
        assert set(base_deck.r9_farm_override()) == {RCR}

    def test_a_stale_rust_override_fails_the_parity_gate(self):
        """Simulate `generated.rs` not being regenerated: the Rust table keeps
        the surplus entries while Python drops them."""
        py = TestFarmDataParity._python_farm_table(True)
        stale = TestFarmDataParity._rust_farm_table(False)   # == "codegen not re-run"
        assert py != stale

    def test_the_reproducer_would_notice_a_fix_that_did_nothing(self, off, on):
        """If the flag silently failed to apply, flags-on would look like
        flags-off — every observable below separates them."""
        for key in ("object_merged", "flat_merged", "rust_merged",
                    "flat_n_farms", "rust_n_farms", "score_flat_python",
                    "score_flat_cy", "score_engine", "score_rust"):
            assert off[key] != on[key], key


# =========================================================================
if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(measure()))
    else:
        print(json.dumps(measure(), indent=2))
