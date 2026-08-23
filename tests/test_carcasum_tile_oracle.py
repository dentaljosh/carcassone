"""D0b — the **Carcasum** differential tile oracle, as a permanent test.

A second, independent differential tile oracle, mirroring
`tests/test_jcz_tile_oracle.py` / `tests/data/jcz/` but against a wholly
separate open-source Carcassonne implementation:

    engine/wingedsheep/carcassonne/tile_sets/base_deck.py     (ours)
    tests/data/carcasum/carcasum_basic_2014.xml                (Carcasum, 2014)

Upstream: `TripleWhy/Carcasum` commit `5f5e3654d31ce8cef0eebeb80a7fb989ef7c2550`
(2014-07-24), AGPL-3.0. See `tests/data/carcasum/PROVENANCE.md`.

Sub-second, pure Python — Carcasum ships its tile definitions as a
declarative XML file (`jcz/resources/tile-definitions/basic.xml`) using the
same shared half-edge convention as the JCZ oracle, so this is a parser and a
set comparison, no C++/Qt build required.

## The one structural difference from the JCZ oracle: many-to-one

Carcasum's 2014 pack has only **24 tile kinds** (no separate ids for the 8
"garden"/flowers graphic variants — those counts fold into their non-garden
sibling). Our deck (and the JCZ 5.x reference) have **32**. So the pairing
here is OUR kind -> Carcasum id, a **total, many-to-one function**, not the
JCZ oracle's 1:1 pairing. `tests/data/carcasum/TILE_MAPPING.tsv` has 32 rows
(one per our-kind); several rows share a `carcasum_id`.

## The one allowance

Exactly one kind disagrees, and it is the **same, already-named** allowance
as the JCZ oracle — not a new, independent finding:

    R9 — `city_top_straight_road` (Carcasum `RCr`, x4) declares half-edges
         EL + WR (our TRR + TLL) only in its north field region. Our engine
         (flag off) additionally claims TLT + TRT (Carcasum NL + NR), the two
         halves of its own north CITY edge.

The text Carcasum uses for this tile's `<farm city="N">EL WR</farm>` is
byte-identical to JCZ 5.x's equivalent declaration — this is the SAME
divergence recurring verbatim against an unrelated, decade-older codebase, a
stronger corroboration of R9 than either oracle alone.

The allowance is keyed to `CARCASSONNE_FIX_R9` exactly as in the JCZ oracle:
flag off -> the divergence must be present and exactly `{NL, NR}`; flag on ->
withdrawn, exact agreement on all 32 rows.

Run standalone (either state) with:

    CARCASSONNE_FIX_R9=0 .venv/bin/python tests/test_carcasum_tile_oracle.py
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO / "engine", REPO / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

DATA = REPO / "tests" / "data" / "carcasum"
CARCASUM_XML = DATA / "carcasum_basic_2014.xml"
MAPPING_TSV = DATA / "TILE_MAPPING.tsv"

# Pinned upstream bytes — see tests/data/carcasum/PROVENANCE.md.
CARCASUM_XML_SHA256 = "ebae213af137b3467ce217c56d41d6ee9ae571bab7976f10fe055d9d217819d1"
CARCASUM_UPSTREAM_COMMIT = "5f5e3654d31ce8cef0eebeb80a7fb989ef7c2550"

# --- the half-edge convention (clockwise from the NW corner; both engines) ---
#     idx  0   1   2   3   4   5   6   7
#     both NL  NR  EL  ER  SL  SR  WL  WR
#     ours TLT TRT TRR BRR BRB BLB BLL TLL
JCZ_HALF = ["NL", "NR", "EL", "ER", "SL", "SR", "WL", "WR"]
JCZ_HALF_IDX = {s: i for i, s in enumerate(JCZ_HALF)}
JCZ_EDGE_IDX = {"N": 0, "E": 1, "S": 2, "W": 3}
OUR_HALF_IDX = {"tlt": 0, "trt": 1, "trr": 2, "brr": 3,
                "brb": 4, "blb": 5, "bll": 6, "tll": 7}
OUR_EDGE_IDX = {"top": 0, "right": 1, "bottom": 2, "left": 3}

# --- the ONE known divergence, named (same R9 as the JCZ oracle) -----------
R9_KIND = "city_top_straight_road"
R9_CARCASUM_ID = "RCr"
R9_CARCASUM_TILE_TYPE = 2
R9_SURPLUS = frozenset({"NL", "NR"})              # == our {TLT, TRT}

# --- the start tile, confirmed from tilefactory.cpp / game.cpp -------------
START_TILE_OUR_KIND = "city_top_straight_road"
START_TILE_CARCASUM_ID = "RCr"
START_TILE_TYPE = 2


# =========================================================================
# shared model (same shape as tests/test_jcz_tile_oracle.py's TileModel)
# =========================================================================
class TileModel:
    """Rotation-aware canonical tile description."""

    def __init__(self, name, cities, roads, fields, monastery, pennant, garden):
        self.name = name
        self.cities = [frozenset(c) for c in cities]
        self.roads = [frozenset(r) for r in roads]
        self.fields = [(frozenset(h), frozenset(frozenset(c) for c in cs))
                       for h, cs in fields]
        self.monastery = bool(monastery)
        self.pennant = bool(pennant)
        self.garden = bool(garden)

    def rotate(self, k):
        def rh(s):
            return frozenset((i + 2 * k) % 8 for i in s)

        def re_(s):
            return frozenset((e + k) % 4 for e in s)

        return TileModel(
            self.name,
            [re_(c) for c in self.cities],
            [re_(r) for r in self.roads],
            [(rh(h), frozenset(re_(c) for c in cs)) for h, cs in self.fields],
            self.monastery, self.pennant, self.garden,
        )

    def skeleton(self):
        """Rotation-alignment key INCLUDING garden — used only where both
        sides can carry a garden flag (never here; Carcasum has none)."""
        return (frozenset(self.cities), frozenset(self.roads),
                self.monastery, self.pennant, self.garden)

    def skeleton_no_garden(self):
        """Skeleton WITHOUT garden — Carcasum ids are never garden-flagged,
        so a garden/non-garden pair of our kinds must both be allowed to
        match the same Carcasum id (the many-to-one collapse)."""
        return (frozenset(self.cities), frozenset(self.roads),
                self.monastery, self.pennant)

    def field_sig(self):
        return frozenset(self.fields)

    def edge_types(self):
        t = ["F"] * 4
        for c in self.cities:
            for e in c:
                t[e] = "C"
        for r in self.roads:
            for e in r:
                t[e] = "R"
        return "".join(t)

    def fields_str(self):
        out = []
        for h, cs in sorted(self.fields, key=lambda x: sorted(x[0])):
            hs = " ".join(JCZ_HALF[i] for i in sorted(h))
            cstr = ""
            if cs:
                cstr = " + city{" + "; ".join(
                    "".join("NESW"[e] for e in sorted(c)) for c in sorted(cs, key=sorted)
                ) + "}"
            out.append("[" + hs + "]" + cstr)
        return " ".join(out) if out else "(none)"

    def half_edges_on_city_edges(self):
        et = self.edge_types()
        return frozenset(JCZ_HALF[i] for h, _ in self.fields for i in h
                         if et[i // 2] == "C")


# =========================================================================
# parsers
# =========================================================================
def parse_carcasum(path=CARCASUM_XML):
    """Returns (models: {id: TileModel}, counts: {id: int}, tile_type: {id: int}).

    `tile_type` is the 0-based XML declaration-order index — Carcasum's
    engine-internal `Tile::tileType` (see PROVENANCE.md "tileType numbering",
    confirmed against `jcz::TileFactory::readXMLTile` in tilefactory.cpp).
    """
    root = ET.parse(path).getroot()
    models, counts, tile_type = {}, {}, {}
    for idx, tel in enumerate(root.findall("tile")):
        tid = tel.get("id")
        counts[tid] = int(tel.get("count"))
        tile_type[tid] = idx

        cities, pennant = [], False
        for cel in tel.findall("city"):
            cities.append({JCZ_EDGE_IDX[s] for s in cel.text.split()})
            if cel.get("pennant") == "yes":
                pennant = True
        roads = [{JCZ_EDGE_IDX[s] for s in rel.text.split()} for rel in tel.findall("road")]
        edge_to_city = {e: frozenset(c) for c in cities for e in c}
        fields = []
        for fel in tel.findall("farm"):
            halves = {JCZ_HALF_IDX[s] for s in (fel.text or "").split()}
            adj = {edge_to_city[JCZ_EDGE_IDX[lab]] for lab in (fel.get("city") or "").split()}
            fields.append((halves, adj))
        models[tid] = TileModel(tid, cities, roads, fields,
                                monastery=tel.find("cloister") is not None,
                                pennant=pennant,
                                garden=False)
    return models, counts, tile_type


def parse_ours():
    from wingedsheep.carcassonne.tile_sets.base_deck import base_tile_counts, base_tiles

    models = {}
    for name, t in base_tiles.items():
        cities = [{OUR_EDGE_IDX[str(s)] for s in comp if str(s) in OUR_EDGE_IDX}
                  for comp in (t.city or [])]
        roads = []
        for conn in (t.road or []):
            ends = set()
            for attr in ("a", "b"):
                v = getattr(conn, attr, None)
                if v is not None and str(v) in OUR_EDGE_IDX:
                    ends.add(OUR_EDGE_IDX[str(v)])
            roads.append(ends)
        edge_to_city = {e: frozenset(c) for c in cities for e in c}
        fields = []
        for fc in (t.farms or []):
            halves = {OUR_HALF_IDX[str(s)] for s in fc.tile_connections}
            adj = set()
            for s in (getattr(fc, "city_sides", None) or []):
                e = OUR_EDGE_IDX.get(str(s))
                if e is not None and e in edge_to_city:
                    adj.add(edge_to_city[e])
            fields.append((halves, adj))
        models[name] = TileModel(name, cities, roads, fields,
                                 monastery=getattr(t, "chapel", False),
                                 pennant=getattr(t, "shield", False),
                                 garden=getattr(t, "flowers", False))
    return models, dict(base_tile_counts)


# =========================================================================
# the 32-row (many-to-one) pairing
# =========================================================================
def match_collapsing(ours, carc):
    """Pair each of OUR 32 kinds to exactly one Carcasum id. Several our-kinds
    landing on the same Carcasum id is EXPECTED (the garden collapse), not an
    error. Ties within one our-kind (same skeleton at >1 candidate id) are
    broken by field signature, mirroring the JCZ oracle's second pass."""
    pairs, unresolved, ambiguous = [], [], []
    for name, om in ours.items():
        cands = []
        for cid, cm in carc.items():
            for k in range(4):
                if om.rotate(k).skeleton_no_garden() == cm.skeleton_no_garden():
                    cands.append((cid, k))
                    break
        if len(cands) == 1:
            pairs.append((name, cands[0][0], cands[0][1]))
        elif len(cands) > 1:
            best = None
            for cid, k in cands:
                if om.rotate(k).field_sig() == carc[cid].field_sig():
                    best = (cid, k)
                    break
            if best is None:
                ambiguous.append((name, cands))
                continue
            pairs.append((name, best[0], best[1]))
        else:
            unresolved.append(name)
    return pairs, unresolved, ambiguous


# =========================================================================
# the oracle
# =========================================================================
def run_oracle():
    carc, carc_counts, carc_type = parse_carcasum()
    ours, our_counts = parse_ours()
    pairs, unresolved, ambiguous = match_collapsing(ours, carc)

    diffs = {}
    table = []
    for name, cid, k in sorted(pairs, key=lambda p: (carc_type[p[1]], p[0])):
        om, cm = ours[name].rotate(k), carc[cid]
        ok = om.field_sig() == cm.field_sig()
        table.append({"our_kind": name, "carcasum_id": cid,
                      "carcasum_tile_type": carc_type[cid],
                      "n": our_counts[name], "rot": k,
                      "edges": cm.edge_types(), "match": ok})
        if not ok:
            ours_halves = {i for h, _ in om.fields for i in h}
            carc_halves = {i for h, _ in cm.fields for i in h}
            diffs[name] = {
                "carcasum_id": cid, "carcasum_tile_type": carc_type[cid],
                "rot": k, "n": our_counts[name], "edges": cm.edge_types(),
                "ours_fields": om.fields_str(), "carcasum_fields": cm.fields_str(),
                "surplus_ours": sorted(JCZ_HALF[i] for i in ours_halves - carc_halves),
                "missing_ours": sorted(JCZ_HALF[i] for i in carc_halves - ours_halves),
                "on_city_edge": sorted(om.half_edges_on_city_edges()),
            }

    agg = defaultdict(int)
    for name, cid, k in pairs:
        agg[cid] += our_counts[name]
    count_mismatches = {cid: (agg.get(cid, 0), carc_counts[cid])
                        for cid in carc if agg.get(cid, 0) != carc_counts[cid]}

    return {
        "n_kinds_ours": len(ours), "n_tiles_ours": sum(our_counts.values()),
        "n_kinds_carcasum": len(carc), "n_tiles_carcasum": sum(carc_counts.values()),
        "unresolved": unresolved, "ambiguous": [a[0] for a in ambiguous],
        "table": table, "diffs": diffs,
        "count_mismatches": count_mismatches,
        "city_edge_sweep_ours": {n: sorted(m.half_edges_on_city_edges())
                                 for n, m in ours.items()
                                 if m.half_edges_on_city_edges()},
        "city_edge_sweep_carcasum": {n: sorted(m.half_edges_on_city_edges())
                                     for n, m in carc.items()
                                     if m.half_edges_on_city_edges()},
        "r9_flag": r9_flag_state(),
    }


def r9_flag_state() -> bool:
    from wingedsheep.carcassonne.tile_sets import base_deck

    return bool(getattr(base_deck, "R9_FIELD_ON_CITY_EDGE_FIX", False))


def expected_diverging_kinds(r9_on: bool) -> set:
    return set() if r9_on else {R9_KIND}


# =========================================================================
# fixtures
# =========================================================================
@pytest.fixture(scope="module")
def oracle():
    return run_oracle()


@pytest.fixture(scope="module")
def r9_on():
    return r9_flag_state()


# =========================================================================
# tests
# =========================================================================
def test_vendored_reference_is_the_pinned_bytes():
    """The oracle is only worth its provenance. Bytes are verbatim upstream
    (see tests/data/carcasum/PROVENANCE.md); an edit here fails loudly."""
    assert hashlib.sha256(CARCASUM_XML.read_bytes()).hexdigest() == CARCASUM_XML_SHA256


def test_pack_shape_and_deck_count_multiset(oracle):
    """Carcasum's 2014 pack: 24 kinds, 72 tiles. Ours: 32 kinds, 72 tiles
    (the garden-variant collapse — see PROVENANCE.md). Total tile count must
    still agree exactly, and every Carcasum id's count must equal the sum of
    the our-kinds mapped onto it."""
    assert oracle["n_kinds_carcasum"] == 24
    assert oracle["n_kinds_ours"] == 32
    assert oracle["n_tiles_ours"] == oracle["n_tiles_carcasum"] == 72
    assert oracle["count_mismatches"] == {}


def test_every_our_kind_pairs_uniquely(oracle):
    assert oracle["unresolved"] == []
    assert oracle["ambiguous"] == []
    assert len(oracle["table"]) == 32


def test_pairing_matches_the_pinned_mapping(oracle):
    """Re-derived pairing == the checked-in `TILE_MAPPING.tsv`. Without this,
    a silent re-pairing could make a real field divergence look like a MATCH."""
    rows = [ln.split("\t") for ln in
            MAPPING_TSV.read_text().strip().splitlines()[1:]]
    pinned = {r[0]: (r[1], int(r[2]), int(r[3]), int(r[4])) for r in rows}
    got = {e["our_kind"]: (e["carcasum_id"], e["carcasum_tile_type"], e["n"], e["rot"])
           for e in oracle["table"]}
    assert got == pinned


def test_start_tile_is_city_top_straight_road(oracle):
    """RCr is the only Carcasum tile with a `<position>` element;
    `TileFactory::createPack` prepends exactly its first clone, and
    `Game::newGame` takes it as the fixed start tile. See PROVENANCE.md."""
    root = ET.parse(CARCASUM_XML).getroot()
    with_position = [tel.get("id") for tel in root.findall("tile")
                     if tel.find("position") is not None]
    assert with_position == [START_TILE_CARCASUM_ID]

    row = next(e for e in oracle["table"] if e["our_kind"] == START_TILE_OUR_KIND)
    assert row["carcasum_id"] == START_TILE_CARCASUM_ID
    assert row["carcasum_tile_type"] == START_TILE_TYPE


def test_tile_type_is_xml_declaration_order(oracle):
    """`Tile::tileType` == 0-based index of the `<tile>` element in XML
    declaration order (confirmed against tilefactory.cpp; see
    PROVENANCE.md). Spot-check the full 0..23 numbering."""
    root = ET.parse(CARCASUM_XML).getroot()
    ids_in_order = [tel.get("id") for tel in root.findall("tile")]
    assert len(ids_in_order) == 24
    expected = ["L", "LR", "RCr", "Cccc+", "CccR+", "CccR", "CFc+", "CFc.1",
                "Cc.1", "Cc+", "CcRr", "CcRr+", "Ccc", "Ccc+", "CRr", "CRRR",
                "RrC", "C", "CFC.2", "CC.2", "RRRR", "RRR", "Rr", "RFr"]
    assert ids_in_order == expected


def test_no_field_data_divergence_beyond_the_named_allowance(oracle, r9_on):
    """**THE oracle assertion.** Any divergence that is not the named R9
    allowance is a failure, in either flag state."""
    unexpected = set(oracle["diffs"]) - expected_diverging_kinds(r9_on)
    assert not unexpected, (
        "base_deck.py diverges from the Carcasum reference on kind(s) not "
        f"covered by any named allowance: "
        f"{json.dumps({k: oracle['diffs'][k] for k in unexpected}, indent=2)}"
    )


def test_r9_allowance_is_exactly_the_two_half_edges_we_named(oracle, r9_on):
    """Strict-xfail sentinel, mirroring the JCZ oracle: flag OFF -> the
    divergence must still be present and still be exactly `{NL, NR}` on
    `city_top_straight_road`."""
    if r9_on:
        assert R9_KIND not in oracle["diffs"], (
            "CARCASSONNE_FIX_R9 is ON but the R9 divergence is still present: "
            f"{oracle['diffs'].get(R9_KIND)}"
        )
        return
    assert R9_KIND in oracle["diffs"], (
        "the R9 divergence has vanished with CARCASSONNE_FIX_R9 OFF against "
        "the Carcasum reference too — the data was changed unconditionally."
    )
    d = oracle["diffs"][R9_KIND]
    assert d["carcasum_id"] == R9_CARCASUM_ID and d["carcasum_tile_type"] == R9_CARCASUM_TILE_TYPE
    assert d["n"] == 4
    assert set(d["surplus_ours"]) == set(R9_SURPLUS)
    assert d["missing_ours"] == []
    assert set(d["on_city_edge"]) == set(R9_SURPLUS)
    assert d["edges"] == "CRFR"


def test_only_r9_ever_claims_a_field_half_edge_on_a_city_edge(oracle, r9_on):
    assert oracle["city_edge_sweep_carcasum"] == {}
    if r9_on:
        assert oracle["city_edge_sweep_ours"] == {}
    else:
        assert set(oracle["city_edge_sweep_ours"]) == {R9_KIND}
        assert set(oracle["city_edge_sweep_ours"][R9_KIND]) == set(R9_SURPLUS)


def test_the_other_31_kinds_are_field_exact(oracle):
    clean = [e["our_kind"] for e in oracle["table"] if e["match"]]
    assert len(clean) >= 31
    assert set(oracle["diffs"]) <= {R9_KIND}


# --- both flag states in one pytest run, via a subprocess -------------------
def _oracle_in_subprocess(flag: str) -> dict:
    env = dict(os.environ, CARCASSONNE_FIX_R9=flag,
               PYTHONPATH=os.pathsep.join(
                   [str(REPO / "engine"), str(REPO / "src"),
                    os.environ.get("PYTHONPATH", "")]).rstrip(os.pathsep))
    rc = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--json"],
                        capture_output=True, text=True, env=env)
    assert rc.returncode in (0, 1), rc.stdout + rc.stderr
    return json.loads(rc.stdout)


@pytest.mark.parametrize("flag,r9", [("0", False), ("1", True)])
def test_oracle_in_both_flag_states(flag, r9):
    res = _oracle_in_subprocess(flag)
    assert res["r9_flag"] is r9
    assert set(res["diffs"]) == expected_diverging_kinds(r9)
    assert res["city_edge_sweep_carcasum"] == {}
    assert set(res["city_edge_sweep_ours"]) == expected_diverging_kinds(r9)
    assert res["count_mismatches"] == {}


# =========================================================================
def _print_report(res) -> int:
    print(f"Carcasum 2014: {res['n_kinds_carcasum']} kinds, {res['n_tiles_carcasum']} tiles")
    print(f"ours base_deck: {res['n_kinds_ours']} kinds, {res['n_tiles_ours']} tiles")
    print(f"CARCASSONNE_FIX_R9 (R9 field-on-city-edge fix): "
          f"{'ON' if res['r9_flag'] else 'off'}\n")
    print(f"{'our kind':<42}{'carcasum id':<14}{'type':>5}{'n':>3} {'rot':>4}  {'edges':<8} verdict")
    for e in res["table"]:
        print(f"{e['our_kind']:<42}{e['carcasum_id']:<14}{e['carcasum_tile_type']:>5}"
              f"{e['n']:>3} {e['rot']:>4}  {e['edges']:<8}"
              f"{'MATCH' if e['match'] else '*** FIELD DIFF ***'}")
    print(f"\nFIELD-DATA DIFFS: {len(res['diffs'])} of {len(res['table'])} kinds")
    for name, d in res["diffs"].items():
        print(f"\n--- {name}  <->  {d['carcasum_id']}  (x{d['n']}, rot {d['rot']}, "
              f"edges NESW={d['edges']})")
        print(f"    carcasum fields : {d['carcasum_fields']}")
        print(f"    ours     fields : {d['ours_fields']}")
        print(f"    surplus ours    : {' '.join(d['surplus_ours']) or '(none)'}")
        print(f"    ON CITY EDGE    : {' '.join(d['on_city_edge']) or '(none)'}")
    print(f"\nglobal city-edge sweep  ours    : {res['city_edge_sweep_ours'] or 'clean'}")
    print(f"global city-edge sweep  carcasum: {res['city_edge_sweep_carcasum'] or 'clean'}")
    expected = expected_diverging_kinds(res["r9_flag"])
    return 0 if set(res["diffs"]) == expected and not res["count_mismatches"] else 1


if __name__ == "__main__":
    result = run_oracle()
    if "--json" in sys.argv:
        print(json.dumps(result))
        ok = (set(result["diffs"]) == expected_diverging_kinds(result["r9_flag"])
              and not result["count_mismatches"])
        raise SystemExit(0 if ok else 1)
    raise SystemExit(_print_report(result))
