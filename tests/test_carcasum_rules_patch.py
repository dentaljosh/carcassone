"""Carcasum rules patch R1 — verified by OBSERVING a constructed game, not by diffing.

`vendor/carcasum/CARCASUM_PATCHES.md` R1 removes upstream's original-2000 tiny-city
exception (`if (score > 2) score *= 2;` in `Game::cityClosed`/`cityUnclosed`), so that a
completed **plain two-tile city scores 4**, matching our `fixed_v1` profile, instead of
upstream's 2.

That patch is the one rules divergence the external inventory predicted
(`docs/research/EXTERNAL_INVENTORY_R2_2026-08-23.md` §3.1 item 4), and
`measurement/carcasum_match_prep/AUDIT_PLAN.md` check 6 requires it to be **positively
observed** in a real game rather than trusted from a source diff — because a patch that
compiles is not a patch that is live in the binary the match will actually run.

The case is *constructed*, not fished for. Farm/city configurations that happen to
appear in a random corpus prove nothing on a schedule; a deck we choose does.

Also pins two things the match harness depends on and that would otherwise only be
checked implicitly:

* the `dump_tiles` table agrees with `tests/data/carcasum/TILE_MAPPING.tsv` — the TSV is
  derived from their **XML**, the dump from their **loader**, so agreement is a genuine
  two-source check (PROTOCOL.md §4);
* **no City edge carries field half-edges** anywhere in their tile set, which is the R9
  convention our engine matches under `CARCASSONNE_FIX_R9=1`.

Skipped (not failed) when the driver binary has not been built — the toolchain is
rootless and lives outside the repo, so a fresh checkout legitimately lacks it. Build
with `scripts/carcasum_match/bootstrap_toolchain.sh`.
"""
from __future__ import annotations

import csv
import json
import subprocess
from collections import defaultdict
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DRIVER = REPO / "vendor" / "carcasum" / "build-driver" / "carcasum_driver"
MAPPING = REPO / "tests" / "data" / "carcasum" / "TILE_MAPPING.tsv"

# Carcasum tileTypes, from the committed mapping. Named here so the test reads.
T_RCR = 2    # the start tile; city on N, roads W/E, field S
T_C = 17     # "C" / CFFF; city on N only, field elsewhere

pytestmark = pytest.mark.skipif(
    not DRIVER.exists(),
    reason=f"carcasum_driver not built at {DRIVER} "
           "(rootless toolchain: run scripts/carcasum_match/bootstrap_toolchain.sh)",
)


def _mapping_rows():
    with MAPPING.open() as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _full_pool() -> list[int]:
    """The 72-tile pack as Carcasum tileTypes, from the committed mapping."""
    pool: list[int] = []
    for r in _mapping_rows():
        pool += [int(r["carcasum_tile_type"])] * int(r["deck_count"])
    assert len(pool) == 72, len(pool)
    return pool


def _dump_tiles() -> dict:
    out = subprocess.run([str(DRIVER), "--dump-tiles"], capture_output=True,
                         text=True, timeout=120)
    assert out.returncode == 0, out.stderr[:2000]
    return json.loads(out.stdout)


class _Driver:
    """Minimal PROTOCOL.md client — deliberately independent of scripts/carcasum_match.

    This test exists to check the BINARY. Driving it through the production harness
    would make a harness bug able to mask a rules bug, so it speaks the protocol itself.
    """

    def __init__(self, deck, external_seat=0, budget_ms=20):
        self.p = subprocess.Popen(
            [str(DRIVER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.send({"t": "new_game", "deck": deck, "external_seat": external_seat,
                   "opponent": {"kind": "mcts", "budget_ms": budget_ms, "cp": 0.5},
                   "seed": 1})
        self.ready = self.recv()
        assert self.ready["t"] == "ready", self.ready

    def send(self, obj):
        self.p.stdin.write(json.dumps(obj) + "\n")
        self.p.stdin.flush()

    def recv(self):
        line = self.p.stdout.readline()
        assert line, "driver closed stdout unexpectedly"
        return json.loads(line)

    def close(self):
        try:
            self.send({"t": "quit"})
            self.p.wait(timeout=10)
        except Exception:
            self.p.kill()


def test_handshake_publishes_a_self_consistent_coordinate_frame():
    """The frame must come from the driver, never from a constant in Python.

    An earlier PROTOCOL.md revision asserted a 72x72 board with offset 36; the board is
    really 145x145 with offset 72 (`Board::Board` does `size(s * 2 + 1)`). A wrong
    offset does not fail loudly -- it yields a legal-looking move at the wrong square,
    which would surface as ~100% divergences and be misread as a RULES disagreement.
    These are the assertions that turn that into an immediate, obvious failure.
    """
    d = _Driver(deck=_deck_starting_with(T_C))
    try:
        r = d.ready
        bs, sxy = r["board_size"], list(r["start_xy"])
        assert bs % 2 == 1, f"board_size {bs} must be odd"
        assert sxy == [bs // 2, bs // 2], f"start {sxy} is not the centre of {bs}"
        assert r["start_tile_type"] == T_RCR, r["start_tile_type"]
        assert r["deck_len"] == 71, r["deck_len"]
    finally:
        d.close()


def _deck_starting_with(first: int) -> list[int]:
    pool = _full_pool()
    pool.remove(T_RCR)          # consumed by setStartTile before any ply
    pool.remove(first)
    deck = [first] + pool
    assert len(deck) == 71, len(deck)
    return deck


def test_plain_two_tile_city_scores_four_not_two():
    """AUDIT_PLAN check 6 -- patch R1 observed live in the binary.

    The start tile (RCr) has a city on its N edge; tile type 17 ("C") has a city on its
    N edge in base orientation. Placing a "C" directly NORTH of start, rotated so its
    city faces SOUTH, joins two single-edge cities into a closed 2-tile city with no
    pennant. Orientation is 2 because absolute side s reads base index (s - o) % 4, so
    mapping down(3) onto base N(1) needs o == 2.

    Upstream scores that 2. Patched, it scores 4.
    """
    d = _Driver(deck=_deck_starting_with(T_C))
    try:
        ox, oy = d.ready["start_xy"]
        target = [ox, oy - 1, 2]          # north of start, city facing south

        m = d.recv()
        assert m["t"] == "req_tile", m
        assert m["tile_type"] == T_C, m["tile_type"]
        assert target in [list(z) for z in m["placements"]], (
            f"construction invalid: {target} not among {m['placements']}")
        d.send({"t": "tile", "x": target[0], "y": target[1], "o": target[2]})

        m = d.recv()
        assert m["t"] == "req_meeple", m
        city = [n for n in m["nodes"] if n["terrain"] == "city"]
        assert len(city) == 1, m["nodes"]
        # The driver rotates node labels to BOARD-ABSOLUTE: base ['N'] at o=2 -> ['S'].
        assert city[0]["labels"] == ["S"], city[0]
        d.send({"t": "meeple", "i": city[0]["i"]})

        m = d.recv()
        assert m["t"] == "ev_move", m
        assert max(m["score_detail"]["city"]) == 4, (
            "plain 2-tile city scored "
            f"{max(m['score_detail']['city'])} -- expected 4 (modern). A 2 means "
            "upstream's original-2000 tiny-city exception is still live in this "
            "binary: patch R1 did not make it in, or the binary is stale.")
        assert max(m["scores"]) == 4, m["scores"]
    finally:
        d.close()


def test_dump_tiles_agrees_with_the_committed_mapping():
    """Two-source check: the TSV comes from their XML, this dump from their loader."""
    d = _dump_tiles()
    assert d["count"] == 24, d["count"]

    dump = {t["tile_type"]: (t["id"], t["deck_count"]) for t in d["tiles"]}
    tsv: dict[int, list] = defaultdict(lambda: [None, 0])
    for r in _mapping_rows():
        tt = int(r["carcasum_tile_type"])
        tsv[tt][0] = r["carcasum_id"]
        tsv[tt][1] += int(r["deck_count"])

    assert set(dump) == set(tsv), (sorted(set(dump) ^ set(tsv)))
    for tt in sorted(dump):
        assert dump[tt] == tuple(tsv[tt]), (tt, dump[tt], tsv[tt])
    assert sum(c for _, c in dump.values()) == 72


def test_no_city_edge_carries_field_half_edges():
    """The R9 convention, read out of THEIR loader rather than assumed from their XML.

    `TileFactory::readXMLTile` fills slot 1 only for a City edge (slots 0/2 -- the field
    half-edges -- are filled only for a Road edge). Our engine matches this under
    CARCASSONNE_FIX_R9=1, which is why every Carcasum match runs fixed_v1 + R9 and is
    not comparable to `walled` production elo.
    """
    violations = []
    for t in _dump_tiles()["tiles"]:
        field_labels = set()
        for n in t["nodes"]:
            if n["terrain"] == "field":
                field_labels |= set(n["labels"])
        for idx, side in enumerate(["W", "N", "E", "S"]):   # edges = [left, up, right, down]
            if t["edges"][idx] == "C":
                for half in (side + "L", side + "R"):
                    if half in field_labels:
                        violations.append((t["id"], half))
    assert violations == [], violations
