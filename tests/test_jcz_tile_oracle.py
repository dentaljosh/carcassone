"""D0 — the JCloisterZone **differential tile oracle**, as a permanent test.

Promoted from `measurement/jcz_spike_20260803/jcz_tile_diff.py` (spike verdict
GO, `SPIKE_REPORT.md`).  It parses **both** tile sets from scratch on every run
and fails on **any** field-data divergence between

    engine/wingedsheep/carcassonne/tile_sets/base_deck.py        (ours)
    tests/data/jcz/jcz_basic_5x.xml   tile-set `basic:2`         (JCZ 5.x)

Sub-second, pure Python, **no Java and no JCZ runtime** — JCZ ships its tile
definitions as a declarative XML file whose farm model is the same shape as
ours (8 named half-edges + the cities each field region touches), so the whole
priority-1 check is a parser and a set comparison.

## The one allowance

Exactly one kind disagrees, and it is a **named, keyed allowance**, not a
tolerance:

    R9 — `city_top_straight_road` (JCZ `BA/RCr`, ×4) declares half-edges
         TLT + TRT (JCZ `NL` + `NR`) in its north field region.  Those are the
         two halves of its NORTH edge, and its north edge is a CITY.  JCZ lists
         `EL WR` (our `TRR`, `TLL`) only.

`FarmUtil.find_farm` (and every leaf that reads the same data) crosses a
`tile_connection` unconditionally, so those two surplus entries let a field walk
straight through a city.  See `measurement/jcz_spike_20260803/rcr_merge_probe.py`
and `tests/test_r9_field_on_city_edge.py`.

The allowance is **keyed to the R9 flag state** (`CARCASSONNE_FIX_R9`, default
off, `base_deck.R9_FIELD_ON_CITY_EDGE_FIX`):

* flag **off** → the divergence is *required* to be present and to be
  *exactly* `{NL, NR}` on that one kind.  This is a strict-xfail sentinel: if
  somebody "fixes" the data unconditionally, this test goes red and forces the
  flag decision instead of letting a rules change land silently.
* flag **on**  → the allowance is withdrawn; **exact agreement is enforced**,
  all 32 kinds, zero divergences.

Run standalone (either state) with:

    CARCASSONNE_FIX_R9=0 .venv/bin/python tests/test_jcz_tile_oracle.py
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO / "engine", REPO / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

DATA = REPO / "tests" / "data" / "jcz"
JCZ_XML = DATA / "jcz_basic_5x.xml"
MAPPING_TSV = DATA / "TILE_MAPPING.tsv"
JCZ_SET = "basic:2"

# Pinned upstream bytes — see tests/data/jcz/PROVENANCE.md.
JCZ_XML_SHA256 = "587a079d76e1be495467f7d469ec60811eb14d2480377c165754967a15274f2a"

# --- the half-edge convention (clockwise from the NW corner; both engines) ---
#     idx  0   1   2   3   4   5   6   7
#     JCZ  NL  NR  EL  ER  SL  SR  WL  WR
#     ours TLT TRT TRR BRR BRB BLB BLL TLL
JCZ_HALF = ["NL", "NR", "EL", "ER", "SL", "SR", "WL", "WR"]
JCZ_HALF_IDX = {s: i for i, s in enumerate(JCZ_HALF)}
JCZ_EDGE_IDX = {"N": 0, "E": 1, "S": 2, "W": 3}
OUR_HALF_IDX = {"tlt": 0, "trt": 1, "trr": 2, "brr": 3,
                "brb": 4, "blb": 5, "bll": 6, "tll": 7}
OUR_EDGE_IDX = {"top": 0, "right": 1, "bottom": 2, "left": 3}
OUR_HALF_NAME = {v: k.upper() for k, v in OUR_HALF_IDX.items()}

# --- the ONE known divergence, named ---------------------------------------
R9_KIND = "city_top_straight_road"
R9_JCZ_ID = "BA/RCr"
R9_SURPLUS_JCZ = frozenset({"NL", "NR"})        # == our {TLT, TRT}
R9_SURPLUS_OURS = frozenset({"TLT", "TRT"})


# =========================================================================
# shared model
# =========================================================================
class TileModel:
    """Rotation-aware canonical tile description (the differ's shared form)."""

    def __init__(self, name, cities, roads, fields, monastery, pennant, garden):
        # cities/roads: list of frozenset(edge idx), one per distinct feature
        # fields: list of (frozenset(half idx), frozenset(city-feature edge-frozensets))
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
        """Everything EXCEPT the field data — used to align/rotate-match."""
        return (frozenset(self.cities), frozenset(self.roads),
                self.monastery, self.pennant, self.garden)

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
        return "".join(t)                       # N E S W

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
        """Field half-edges lying on a CITY edge — geometrically impossible.

        A *road* edge legitimately carries field on both halves (a road is a
        line, not a band), so only city edges are illegitimate.  This
        distinction is the bug detector.
        """
        et = self.edge_types()
        return frozenset(JCZ_HALF[i] for h, _ in self.fields for i in h
                         if et[i // 2] == "C")


# =========================================================================
# parsers
# =========================================================================
def parse_jcz(path=JCZ_XML, set_id=JCZ_SET):
    root = ET.parse(path).getroot()
    counts = Counter()
    for ts in root.find("sets").findall("tile-set"):
        if ts.get("id") == set_id:
            for ref in ts.findall("ref"):
                counts[ref.get("tile")] += int(ref.get("count"))
    models = {}
    for tel in root.find("tiles").findall("tile"):
        tid = tel.get("id")
        if tid not in counts:
            continue
        cities, pennant = [], False
        for cel in tel.findall("city"):
            cities.append({JCZ_EDGE_IDX[s] for s in cel.text.split()})
            if cel.get("pennants"):
                pennant = True
        roads = [{JCZ_EDGE_IDX[s] for s in rel.text.split()}
                 for rel in tel.findall("road")]
        # A1: JCZ names a city in `field city="…"` by ONE representative edge
        # label, not by all its edges.  Resolve the label to the city FEATURE.
        edge_to_city = {e: frozenset(c) for c in cities for e in c}
        fields = []
        for fel in tel.findall("field"):
            halves = {JCZ_HALF_IDX[s] for s in (fel.text or "").split()}
            adj = {edge_to_city[JCZ_EDGE_IDX[lab]]
                   for lab in (fel.get("city") or "").split()}
            fields.append((halves, adj))
        models[tid] = TileModel(tid, cities, roads, fields,
                                monastery=tel.find("monastery") is not None,
                                pennant=pennant,
                                garden=tel.find("garden") is not None)
    return models, dict(counts)


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
# the 32-kind pairing (deck count x rotation-invariant skeleton)
# =========================================================================
def match(ours, our_counts, jcz, jcz_counts):
    pairs, ambiguous, used = [], [], set()
    for name, om in ours.items():
        cands = []
        for jid, jm in jcz.items():
            if jid in used or jcz_counts.get(jid) != our_counts[name]:
                continue
            for k in range(4):
                if om.rotate(k).skeleton() == jm.skeleton():
                    cands.append((jid, k))
                    break
        if len(cands) == 1:
            pairs.append((name, cands[0][0], cands[0][1]))
            used.add(cands[0][0])
        else:
            ambiguous.append((name, [c[0] for c in cands]))
    # second pass: the two chiral pairs (same count + same skeleton) — break
    # the tie on the field signature, then deterministically.
    for name, cands in list(ambiguous):
        free = [c for c in cands if c not in used]
        if not free:
            continue
        om, best = ours[name], None
        for jid in free:
            for k in range(4):
                r = om.rotate(k)
                if r.skeleton() == jcz[jid].skeleton() and r.field_sig() == jcz[jid].field_sig():
                    best = (jid, k)
                    break
            if best:
                break
        if best is None:
            jid = sorted(free)[0]
            k = next(k for k in range(4)
                     if om.rotate(k).skeleton() == jcz[jid].skeleton())
            best = (jid, k)
        pairs.append((name, best[0], best[1]))
        used.add(best[0])
        ambiguous.remove((name, cands))
    return pairs, ambiguous, sorted(j for j in jcz if j not in used)


# =========================================================================
# the oracle
# =========================================================================
def run_oracle():
    """Parse both decks, pair them, diff the field data.  Pure data in/out so
    the same routine serves the tests and the `__main__` / subprocess path."""
    jcz, jcz_counts = parse_jcz()
    ours, our_counts = parse_ours()
    pairs, ambiguous, unmatched_jcz = match(ours, our_counts, jcz, jcz_counts)

    diffs = {}
    table = []
    for name, jid, k in sorted(pairs, key=lambda p: p[1]):
        om, jm = ours[name].rotate(k), jcz[jid]
        ok = om.field_sig() == jm.field_sig()
        table.append({"our_kind": name, "jcz_id": jid, "n": our_counts[name],
                      "rot": k, "edges": jm.edge_types(), "match": ok})
        if not ok:
            # the half-edges we claim that JCZ does not, expressed as the
            # union over regions (rotation-normalised into JCZ labels)
            ours_halves = {i for h, _ in om.fields for i in h}
            jcz_halves = {i for h, _ in jm.fields for i in h}
            diffs[name] = {
                "jcz_id": jid, "rot": k, "n": our_counts[name],
                "edges": jm.edge_types(),
                "ours_fields": om.fields_str(), "jcz_fields": jm.fields_str(),
                "surplus_ours": sorted(JCZ_HALF[i] for i in ours_halves - jcz_halves),
                "missing_ours": sorted(JCZ_HALF[i] for i in jcz_halves - ours_halves),
                "on_city_edge": sorted(om.half_edges_on_city_edges()),
            }

    return {
        "n_kinds_ours": len(ours), "n_tiles_ours": sum(our_counts.values()),
        "n_kinds_jcz": len(jcz), "n_tiles_jcz": sum(jcz_counts.values()),
        "counts_multiset_equal":
            sorted(jcz_counts.values()) == sorted(our_counts.values()),
        "ambiguous": ambiguous, "unmatched_jcz": unmatched_jcz,
        "table": table, "diffs": diffs,
        "city_edge_sweep_ours": {n: sorted(m.half_edges_on_city_edges())
                                 for n, m in ours.items()
                                 if m.half_edges_on_city_edges()},
        "city_edge_sweep_jcz": {n: sorted(m.half_edges_on_city_edges())
                                for n, m in jcz.items()
                                if m.half_edges_on_city_edges()},
        "r9_flag": r9_flag_state(),
    }


def r9_flag_state() -> bool:
    from wingedsheep.carcassonne.tile_sets import base_deck

    return bool(getattr(base_deck, "R9_FIELD_ON_CITY_EDGE_FIX", False))


def expected_diverging_kinds(r9_on: bool) -> set:
    """The NAMED allowance set, keyed to the flag.  Empty when R9 is on."""
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
    """The oracle is only worth its provenance.  Bytes are verbatim upstream
    (see tests/data/jcz/PROVENANCE.md); an edit here fails loudly."""
    assert hashlib.sha256(JCZ_XML.read_bytes()).hexdigest() == JCZ_XML_SHA256


def test_edition_matches_ours(oracle):
    """`basic:2` IS the edition we model: same 32 kinds, same 72 tiles, same
    count multiset.  (This is what retired the spec's garden-substitution
    workaround.)"""
    assert oracle["n_kinds_ours"] == oracle["n_kinds_jcz"] == 32
    assert oracle["n_tiles_ours"] == oracle["n_tiles_jcz"] == 72
    assert oracle["counts_multiset_equal"]


def test_every_kind_pairs_uniquely(oracle):
    assert oracle["ambiguous"] == []
    assert oracle["unmatched_jcz"] == []
    assert len(oracle["table"]) == 32


def test_pairing_matches_the_pinned_mapping(oracle):
    """Re-derived pairing == the checked-in `TILE_MAPPING.tsv`.  Without this,
    a silent re-pairing could make a real field divergence look like a MATCH."""
    rows = [ln.split("\t") for ln in
            MAPPING_TSV.read_text().strip().splitlines()[1:]]
    pinned = {r[0]: (r[1], int(r[2]), int(r[3])) for r in rows}
    got = {e["our_kind"]: (e["jcz_id"], e["n"], e["rot"]) for e in oracle["table"]}
    assert got == pinned


def test_no_field_data_divergence_beyond_the_named_allowance(oracle, r9_on):
    """**THE oracle assertion.**  Any divergence that is not the named R9
    allowance is a failure, in either flag state."""
    unexpected = set(oracle["diffs"]) - expected_diverging_kinds(r9_on)
    assert not unexpected, (
        "base_deck.py diverges from the JCZ reference on kind(s) not covered by "
        f"any named allowance: {json.dumps({k: oracle['diffs'][k] for k in unexpected}, indent=2)}"
    )


def test_r9_allowance_is_exactly_the_two_half_edges_we_named(oracle, r9_on):
    """Strict-xfail sentinel.  With the flag OFF the divergence must still be
    present AND still be exactly `{NL, NR}` on `city_top_straight_road` — so
    the allowance cannot silently widen, and an unconditional "fix" of the data
    turns this red instead of sliding a rules change past the flag."""
    if r9_on:
        assert R9_KIND not in oracle["diffs"], (
            "CARCASSONNE_FIX_R9 is ON but the R9 divergence is still present: "
            f"{oracle['diffs'].get(R9_KIND)}"
        )
        return
    assert R9_KIND in oracle["diffs"], (
        "the R9 divergence has vanished with CARCASSONNE_FIX_R9 OFF — the data "
        "was changed unconditionally.  R9 is a flagged rules change; adopt it "
        "through the flag, not by editing base_deck.py in place."
    )
    d = oracle["diffs"][R9_KIND]
    assert d["jcz_id"] == R9_JCZ_ID and d["n"] == 4
    assert set(d["surplus_ours"]) == set(R9_SURPLUS_JCZ)
    assert d["missing_ours"] == []
    assert set(d["on_city_edge"]) == set(R9_SURPLUS_JCZ)
    assert d["edges"] == "CRFR"          # city N, road E, field S, road W


def test_only_r9_ever_claims_a_field_half_edge_on_a_city_edge(oracle, r9_on):
    """The global sweep the spike ran: a field region claiming a half-edge that
    lies on a CITY edge lets a farm cross a city border.  JCZ's whole base set
    is clean; ours must be too, modulo the R9 allowance."""
    assert oracle["city_edge_sweep_jcz"] == {}
    if r9_on:
        assert oracle["city_edge_sweep_ours"] == {}
    else:
        assert set(oracle["city_edge_sweep_ours"]) == {R9_KIND}
        assert set(oracle["city_edge_sweep_ours"][R9_KIND]) == set(R9_SURPLUS_JCZ)


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
    """The allowance really is keyed to the flag: OFF ⇒ exactly one named
    divergence; ON ⇒ **zero** divergences, exact agreement on all 32 kinds."""
    res = _oracle_in_subprocess(flag)
    assert res["r9_flag"] is r9
    assert set(res["diffs"]) == expected_diverging_kinds(r9)
    assert res["city_edge_sweep_jcz"] == {}
    assert set(res["city_edge_sweep_ours"]) == expected_diverging_kinds(r9)


# =========================================================================
def _print_report(res) -> int:
    print(f"JCZ  {JCZ_SET}: {res['n_kinds_jcz']} kinds, {res['n_tiles_jcz']} tiles")
    print(f"ours base_deck: {res['n_kinds_ours']} kinds, {res['n_tiles_ours']} tiles")
    print(f"count multiset identical: {res['counts_multiset_equal']}")
    print(f"CARCASSONNE_FIX_R9 (R9 field-on-city-edge fix): "
          f"{'ON' if res['r9_flag'] else 'off'}\n")
    print(f"{'our kind':<42}{'JCZ id':<14}{'n':>3} {'rot':>4}  {'edges':<8} verdict")
    for e in res["table"]:
        print(f"{e['our_kind']:<42}{e['jcz_id']:<14}{e['n']:>3} {e['rot']:>4}  "
              f"{e['edges']:<8}{'MATCH' if e['match'] else '*** FIELD DIFF ***'}")
    print(f"\nFIELD-DATA DIFFS: {len(res['diffs'])} of {len(res['table'])} kinds")
    for name, d in res["diffs"].items():
        print(f"\n--- {name}  <->  {d['jcz_id']}  (x{d['n']}, rot {d['rot']}, "
              f"edges NESW={d['edges']})")
        print(f"    JCZ  fields : {d['jcz_fields']}")
        print(f"    ours fields : {d['ours_fields']}")
        print(f"    surplus ours: {' '.join(d['surplus_ours']) or '(none)'}")
        print(f"    ON CITY EDGE: {' '.join(d['on_city_edge']) or '(none)'}")
    print(f"\nglobal city-edge sweep  ours: {res['city_edge_sweep_ours'] or 'clean'}")
    print(f"global city-edge sweep  JCZ : {res['city_edge_sweep_jcz'] or 'clean'}")
    expected = expected_diverging_kinds(res["r9_flag"])
    return 0 if set(res["diffs"]) == expected else 1


if __name__ == "__main__":
    result = run_oracle()
    if "--json" in sys.argv:
        print(json.dumps(result))
        raise SystemExit(0 if set(result["diffs"]) ==
                         expected_diverging_kinds(result["r9_flag"]) else 1)
    raise SystemExit(_print_report(result))
