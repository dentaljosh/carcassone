"""Drift guard for the checked-in tile codegen (rustport P1).

`rust/carc/carc-core/src/tiles/generated.rs` is generated from the vendored
`base_deck.py` and committed.  Nothing rebuilds it automatically (the spec
forbids a Python-invoking `build.rs`), so these tests are what stop the Rust
engine from silently scoring a stale deck:

* the compiled-in `SOURCE_SHA256` still matches `base_deck.py` byte-for-byte;
* the compiled-in `SEMANTIC_DIGEST` still matches a fresh digest of everything
  the engine reads off a tile — **including `base_tile_counts` dict insertion
  order**, which the deck build iterates before the one global shuffle;
* re-rendering the file produces exactly the checked-in bytes;
* every rotated tile's terrain signature agrees with the live engine's
  `Tile.turn(k).get_type(...)`, so the Rust rotation port is pinned to Python
  and not merely to itself.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "engine", REPO / "scripts" / "rustport"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

carc_rs = pytest.importorskip("carc_rs", reason="build with `maturin develop --release`")

import export_tile_data as ex  # noqa: E402


def test_source_sha256_matches_base_deck():
    compiled_source, _ = carc_rs.tile_data_digests()
    assert compiled_source == ex.source_sha256(), (
        "tiles/generated.rs was built from a different base_deck.py; "
        "re-run scripts/rustport/export_tile_data.py"
    )


def test_semantic_digest_matches_live_engine():
    _, compiled_semantic = carc_rs.tile_data_digests()
    assert compiled_semantic == ex.semantic_digest()


def test_counts_insertion_order_is_captured():
    from wingedsheep.carcassonne.tile_sets.base_deck import base_tile_counts

    payload = ex.semantic_payload()
    assert [k for k, _ in payload["counts_in_insertion_order"]] == list(base_tile_counts)
    assert sum(v for _, v in payload["counts_in_insertion_order"]) == 72


def test_generated_file_is_up_to_date():
    rc = subprocess.run(
        [sys.executable, str(REPO / "scripts/rustport/export_tile_data.py"), "--check"],
        capture_output=True, text=True,
    )
    assert rc.returncode == 0, rc.stdout + rc.stderr


def test_rotated_tiles_match_python_turn_and_get_type():
    """The Rust registry's `(description, rot, signature)` table vs the engine's
    own `Tile.turn(rot)` + `game_wrapper._tile_rotation_signature`."""
    sys.path.insert(0, str(REPO / "src"))
    from carcassonne_ai.game_wrapper import _tile_rotation_signature
    from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles

    want = {}
    for name, tile in base_tiles.items():
        for rot in range(4):
            want[(name, rot)] = repr(_tile_rotation_signature(tile.turn(rot)))

    got = {(d, rot): sig for d, rot, sig in carc_rs.rotated_tile_table()}
    assert len(got) == 32 * 4
    assert got == want


def test_deck_from_seed_matches_cpython_shuffle():
    import random

    from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
    from wingedsheep.carcassonne.tile_sets.supplementary_rules import SupplementaryRule
    from wingedsheep.carcassonne.tile_sets.tile_sets import TileSet

    for seed in (0, 1, 42, 867966, 161583, 28_000_000_000, 2**70 + 7):
        random.seed(seed)
        st = CarcassonneGameState(
            players=2, tile_sets=[TileSet.BASE],
            supplementary_rules=[SupplementaryRule.FARMERS],
        )
        py = [st.next_tile.description] + [t.description for t in st.deck]
        assert py == carc_rs.deck_descriptions_from_seed(str(seed)), seed
        assert len(py) == 72
