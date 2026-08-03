#!/usr/bin/env python3
"""JCloisterZone differential-oracle spike: TILE-DATA diff (no JCZ runtime needed).

Compares our hand-authored `engine/.../tile_sets/base_deck.py` against
JCloisterZone's `basic.xml` tile-definition data file (tile-set `basic:2`, which is
the C3 base game with the 8 garden/"flowers" variants substituted in place -- the
exact edition our deck models).

Both sides describe a tile as:
  * four edges, each city / road / field,
  * a set of FIELD (farm) regions, each region being a set of the 8 half-edges it
    touches plus the set of cities it is adjacent to.

Half-edge indexing (clockwise from the NW corner) is the shared canonical form:

    idx  0   1   2   3   4   5   6   7
    JCZ  NL  NR  EL  ER  SL  SR  WL  WR
    ours TLT TRT TRR BRR BRB BLB BLL TLL

Edge index e = idx // 2 : 0=N/TOP 1=E/RIGHT 2=S/BOTTOM 3=W/LEFT.
Rotating a tile 90 deg clockwise k times maps idx -> (idx + 2k) % 8, e -> (e+k) % 4.

Usage:  .venv/bin/python measurement/jcz_spike_20260803/jcz_tile_diff.py
"""
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
JCZ_XML = os.path.join(HERE, "jcz_basic_5x.xml")
JCZ_SET = "basic:2"

JCZ_HALF = ["NL", "NR", "EL", "ER", "SL", "SR", "WL", "WR"]
JCZ_HALF_IDX = {s: i for i, s in enumerate(JCZ_HALF)}
JCZ_EDGE_IDX = {"N": 0, "E": 1, "S": 2, "W": 3}

OUR_HALF_IDX = {"tlt": 0, "trt": 1, "trr": 2, "brr": 3,
                "brb": 4, "blb": 5, "bll": 6, "tll": 7}
OUR_EDGE_IDX = {"top": 0, "right": 1, "bottom": 2, "left": 3}


# ---------------------------------------------------------------- shared model
class TileModel:
    """Rotation-aware canonical tile description."""

    def __init__(self, name, cities, roads, fields, monastery, pennant, garden):
        # cities: list of frozenset(edge idx)   (one entry per distinct city feature)
        # roads:  list of frozenset(edge idx)   (one entry per distinct road feature)
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
        rh = lambda s: frozenset((i + 2 * k) % 8 for i in s)
        re_ = lambda s: frozenset((e + k) % 4 for e in s)
        return TileModel(
            self.name,
            [re_(c) for c in self.cities],
            [re_(r) for r in self.roads],
            [(rh(h), frozenset(re_(c) for c in cs)) for h, cs in self.fields],
            self.monastery, self.pennant, self.garden,
        )

    def skeleton(self):
        """Everything EXCEPT the field data -- used to align/rotate-match tiles."""
        return (frozenset(self.cities), frozenset(self.roads),
                self.monastery, self.pennant, self.garden)

    def field_sig(self):
        return frozenset(self.fields)

    # --- pretty printing -------------------------------------------------
    def edge_types(self):
        t = ["F"] * 4
        for c in self.cities:
            for e in c:
                t[e] = "C"
        for r in self.roads:
            for e in r:
                t[e] = "R"
        return "".join(t)  # N E S W

    def fields_str(self):
        out = []
        for h, cs in sorted(self.fields, key=lambda x: sorted(x[0])):
            hs = " ".join(JCZ_HALF[i] for i in sorted(h))
            if cs:
                cstr = " + city{" + "; ".join(
                    "".join("NESW"[e] for e in sorted(c)) for c in sorted(cs, key=sorted)
                ) + "}"
            else:
                cstr = ""
            out.append("[" + hs + "]" + cstr)
        return " ".join(out) if out else "(none)"


# ------------------------------------------------------------------ JCZ parser
def parse_jcz(path, set_id):
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
        roads = []
        for rel in tel.findall("road"):
            roads.append({JCZ_EDGE_IDX[s] for s in rel.text.split()})
        # map an edge label -> the city feature (frozenset of edges) containing it
        edge_to_city = {}
        for c in cities:
            for e in c:
                edge_to_city[e] = frozenset(c)
        fields = []
        for fel in tel.findall("field"):
            halves = {JCZ_HALF_IDX[s] for s in (fel.text or "").split()}
            adj = set()
            if fel.get("city"):
                for lab in fel.get("city").split():
                    adj.add(edge_to_city[JCZ_EDGE_IDX[lab]])
            fields.append((halves, adj))
        models[tid] = TileModel(tid, cities, roads, fields,
                                monastery=tel.find("monastery") is not None,
                                pennant=pennant,
                                garden=tel.find("garden") is not None)
    return models, counts


# ------------------------------------------------------------------ our parser
def parse_ours():
    from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles, base_tile_counts
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
        edge_to_city = {}
        for c in cities:
            for e in c:
                edge_to_city[e] = frozenset(c)
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


# --------------------------------------------------------------------- matcher
def match(ours, our_counts, jcz, jcz_counts):
    """Pair our kinds to JCZ ids by (deck count, rotation-invariant skeleton)."""
    pairs, unmatched_ours, used = [], [], set()
    for name, om in ours.items():
        cands = []
        for jid, jm in jcz.items():
            if jid in used or jcz_counts[jid] != our_counts[name]:
                continue
            for k in range(4):
                if om.rotate(k).skeleton() == jm.skeleton():
                    cands.append((jid, k))
                    break
        if len(cands) == 1:
            pairs.append((name, cands[0][0], cands[0][1]))
            used.add(cands[0][0])
        else:
            unmatched_ours.append((name, [c[0] for c in cands]))
    # second pass: resolve ties (same count + same skeleton, e.g. mirror pairs)
    for name, cands in list(unmatched_ours):
        free = [c for c in cands if c not in used]
        if not free:
            continue
        om = ours[name]
        best = None
        for jid in free:
            for k in range(4):
                r = om.rotate(k)
                if r.skeleton() == jcz[jid].skeleton() and r.field_sig() == jcz[jid].field_sig():
                    best = (jid, k)
                    break
            if best:
                break
        if best is None:  # arbitrary but deterministic
            jid = sorted(free)[0]
            k = next(k for k in range(4)
                     if om.rotate(k).skeleton() == jcz[jid].skeleton())
            best = (jid, k)
        pairs.append((name, best[0], best[1]))
        used.add(best[0])
        unmatched_ours.remove((name, cands))
    return pairs, unmatched_ours, [j for j in jcz if j not in used]


def main():
    jcz, jcz_counts = parse_jcz(JCZ_XML, JCZ_SET)
    ours, our_counts = parse_ours()
    print(f"JCZ  {JCZ_SET}: {len(jcz)} kinds, {sum(jcz_counts.values())} tiles")
    print(f"ours base_deck: {len(ours)} kinds, {sum(our_counts.values())} tiles")
    print(f"count multiset identical: {sorted(jcz_counts.values()) == sorted(our_counts.values())}\n")

    pairs, unmatched_ours, unmatched_jcz = match(ours, our_counts, jcz, jcz_counts)
    if unmatched_ours or unmatched_jcz:
        print("!! UNMATCHED ours:", unmatched_ours)
        print("!! UNMATCHED jcz :", unmatched_jcz, "\n")

    print("=" * 100)
    print("MAPPING TABLE  (rot = # of 90-deg CW rotations applied to OUR base orientation)")
    print("=" * 100)
    print(f"{'our kind':<42}{'JCZ id':<14}{'n':>3} {'rot':>4}  {'edges(NESW)':<12} verdict")
    diffs = []
    for name, jid, k in sorted(pairs, key=lambda p: p[1]):
        om = ours[name].rotate(k)
        jm = jcz[jid]
        ok = om.field_sig() == jm.field_sig()
        if not ok:
            diffs.append((name, jid, k, om, jm))
        print(f"{name:<42}{jid:<14}{our_counts[name]:>3} {k:>4}  {jm.edge_types():<12}"
              f"{'MATCH' if ok else '*** FIELD DIFF ***'}")

    print()
    print("=" * 100)
    print(f"FIELD-DATA DIFFS: {len(diffs)} of {len(pairs)} tile kinds")
    print("=" * 100)
    for name, jid, k, om, jm in diffs:
        n = our_counts[name]
        print(f"\n--- {name}  <->  {jid}   (x{n} in deck, our tile rotated {k}x90CW)")
        print(f"    edges (N E S W)  : {jm.edge_types()}")
        print(f"    JCZ  fields      : {jm.fields_str()}")
        print(f"    ours fields      : {om.fields_str()}")
        ours_only = om.field_sig() - jm.field_sig()
        jcz_only = jm.field_sig() - om.field_sig()
        for h, cs in sorted(ours_only, key=lambda x: sorted(x[0])):
            print(f"    ours-only region : [{' '.join(JCZ_HALF[i] for i in sorted(h))}]")
        for h, cs in sorted(jcz_only, key=lambda x: sorted(x[0])):
            print(f"    JCZ-only  region : [{' '.join(JCZ_HALF[i] for i in sorted(h))}]")
        # Classify: half-edges we claim that sit on a CITY edge. (A ROAD edge still
        # carries field on both halves -- the road is a line, not a band -- so only
        # city edges are illegitimate.)
        et = jm.edge_types()
        for h, cs in om.fields:
            bad = [JCZ_HALF[i] for i in sorted(h) if et[i // 2] == "C"]
            if bad:
                print(f"    >>> ours claims half-edges lying ON A CITY EDGE: {' '.join(bad)}"
                      f"  (edge types N E S W = {et})")

    # Global sweep: which kinds (matching or not) claim a half-edge on a city edge?
    print()
    print("=" * 100)
    print("GLOBAL SWEEP: field regions claiming a half-edge that lies on a CITY edge")
    print("(such a claim lets a farm cross a city border -- geometrically impossible)")
    print("=" * 100)
    for src, models in (("ours", ours), ("JCZ ", jcz)):
        hits = []
        for name, m in models.items():
            et = m.edge_types()
            bad = sorted({JCZ_HALF[i] for h, _ in m.fields for i in h if et[i // 2] == "C"})
            if bad:
                hits.append((name, " ".join(bad)))
        print(f"  {src}: {len(hits)} kind(s)" + ("" if hits else "  -- clean"))
        for name, bad in hits:
            print(f"        {name:<40} {bad}")
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
