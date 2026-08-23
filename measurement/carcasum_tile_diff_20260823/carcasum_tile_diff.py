#!/usr/bin/env python3
"""Carcasum differential-oracle generator: TILE-DATA diff (no Carcasum build needed).

Compares our hand-authored `engine/.../tile_sets/base_deck.py` against
Carcasum's vendored 2014-vintage `basic.xml` tile-definition file
(upstream `TripleWhy/Carcasum`, commit 5f5e3654d31ce8cef0eebeb80a7fb989ef7c2550).

Carcasum's 2014 pack has only **24 tile kinds** (no separate "garden"/flowers
graphic-variant ids -- those 8 variants are folded back into their non-garden
counterpart's `count`), where our deck and the JCZ 5.x reference both carry
**32 kinds** (24 base + 8 garden variants as distinct ids). So this is a
**many-to-one** pairing: OUR kind -> Carcasum id, not a 1:1 pairing like the
JCZ oracle. See tests/data/carcasum/PROVENANCE.md.

ADAPTATION NOTE (per the task brief -- "adapt, don't silently fork"): this
script imports `TileModel`, the shared half-edge/edge index tables, and
`parse_ours()` UNCHANGED from
`measurement/jcz_spike_20260803/jcz_tile_diff.py` (same shared canonical tile
model, same JCZ half-edge convention -- Carcasum's XML happens to use the
identical `NL/NR/EL/ER/SL/SR/WL/WR` + `N/E/S/W` text convention as JCZ 5.x, so
no new convention is introduced). What's NEW here, because Carcasum's schema
and the many-to-one collapse are genuinely different from the JCZ spike:

  * `parse_carcasum()` -- a new XML reader for Carcasum's schema, which
    differs from JCZ 5.x's in wire format even though the field/city/road
    text convention is shared:
      - `count` is an attribute directly on `<tile>` (JCZ 5.x keeps counts in
        a separate `<sets><tile-set><ref>` block).
      - pennant is `<city pennant="yes">` (singular; JCZ 5.x: `pennants`).
      - cloister is `<cloister/>` (JCZ 5.x: `<monastery/>`).
      - no `<garden>` tag exists at all -- Carcasum has no graphic variants.
      - tile declaration order in the XML IS the engine's `tileType` (see
        PROVENANCE.md / tilefactory.cpp `TileTypeType type =
        (TileTypeType)tileTemplates[set].size()`), so this parser also
        returns that 0-based index per id.
  * `match_collapsing()` -- JCZ's `match()` requires exact deck-count
    equality between one JCZ id and one our-kind (correct for a 1:1 pairing).
    That can't work here: e.g. Carcasum's `Ccc` (count 3) must match BOTH our
    `city_bottom_grass` (count 2) AND `city_bottom_grass_flowers` (count 1).
    `match_collapsing()` instead pairs by rotation-invariant skeleton alone
    (cities/roads/monastery/pennant -- deliberately NOT `garden`, since
    Carcasum tiles are never garden-flagged) and allows more than one of our
    kinds to land on the same Carcasum id, then verifies the per-id count
    sums agree afterward.

Usage:  .venv/bin/python measurement/carcasum_tile_diff_20260823/carcasum_tile_diff.py
"""
import os
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
JCZ_SPIKE_DIR = os.path.join(REPO, "measurement", "jcz_spike_20260803")
sys.path.insert(0, JCZ_SPIKE_DIR)

from jcz_tile_diff import (  # noqa: E402  (import must follow sys.path insert)
    TileModel, JCZ_HALF, JCZ_HALF_IDX, JCZ_EDGE_IDX, parse_ours,
)

CARCASUM_XML = os.path.join(REPO, "tests", "data", "carcasum", "carcasum_basic_2014.xml")


# ------------------------------------------------------------------ Carcasum parser
def parse_carcasum(path):
    """Returns (models: {id: TileModel}, counts: {id: int}, tile_type: {id: int})."""
    root = ET.parse(path).getroot()
    models, counts, tile_type = {}, {}, {}
    for idx, tel in enumerate(root.findall("tile")):
        tid = tel.get("id")
        counts[tid] = int(tel.get("count"))
        tile_type[tid] = idx  # XML declaration order == engine tileType (verified against tilefactory.cpp)

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
                                garden=False)  # Carcasum 2014 has no garden variants at all
    return models, counts, tile_type


def skeleton_no_garden(m):
    """Rotation-invariant skeleton WITHOUT the garden flag -- Carcasum ids never
    carry it, so a garden/non-garden pair of our kinds must both be allowed to
    match the same Carcasum id."""
    return (frozenset(m.cities), frozenset(m.roads), m.monastery, m.pennant)


# --------------------------------------------------------------------- matcher
def match_collapsing(ours, carc):
    """Pair each of OUR 32 kinds to exactly one Carcasum id (many our-kinds per
    Carcasum id is expected). Ties (same skeleton, different rotation/chirality)
    are broken by field_sig, mirroring the JCZ oracle's second pass."""
    pairs, unresolved = [], []
    for name, om in ours.items():
        cands = []
        for cid, cm in carc.items():
            for k in range(4):
                if skeleton_no_garden(om.rotate(k)) == skeleton_no_garden(cm):
                    cands.append((cid, k))
                    break
        if len(cands) == 1:
            pairs.append((name, cands[0][0], cands[0][1]))
        elif len(cands) > 1:
            # disambiguate by field signature (ignoring the one R9 case, which is
            # a KNOWN divergence, not an ambiguity -- it still uniquely skeleton-matches)
            best = None
            for cid, k in cands:
                if ours[name].rotate(k).field_sig() == carc[cid].field_sig():
                    best = (cid, k)
                    break
            if best is None:
                best = cands[0]
            pairs.append((name, best[0], best[1]))
        else:
            unresolved.append(name)
    return pairs, unresolved


def main():
    ours, our_counts = parse_ours()
    carc, carc_counts, carc_type = parse_carcasum(CARCASUM_XML)

    print(f"Carcasum 2014: {len(carc)} kinds, {sum(carc_counts.values())} tiles")
    print(f"ours base_deck: {len(ours)} kinds, {sum(our_counts.values())} tiles")

    pairs, unresolved = match_collapsing(ours, carc)
    if unresolved:
        print("!! UNRESOLVED ours (no skeleton match found):", unresolved)

    print(f"\npaired {len(pairs)} of {len(ours)} our-kinds")

    # aggregate our counts per carcasum id, verify against carc_counts
    agg = defaultdict(int)
    for name, cid, k in pairs:
        agg[cid] += our_counts[name]
    mismatches = {cid: (agg[cid], carc_counts[cid]) for cid in carc
                  if agg.get(cid, 0) != carc_counts[cid]}
    print(f"deck-count per-id agreement: {'ALL OK' if not mismatches else mismatches}")
    print(f"total tiles: ours={sum(our_counts.values())} carcasum={sum(carc_counts.values())}")

    print()
    print("=" * 110)
    hdr = f"{'our_kind':<42}{'carcasum_id':<14}{'type':>5}{'n':>3} {'rot':>4}  {'edges(NESW)':<12} verdict"
    print(hdr)
    diffs = []
    for name, cid, k in sorted(pairs, key=lambda p: (carc_type[p[1]], p[0])):
        om = ours[name].rotate(k)
        cm = carc[cid]
        ok = om.field_sig() == cm.field_sig()
        if not ok:
            diffs.append((name, cid, k, om, cm))
        print(f"{name:<42}{cid:<14}{carc_type[cid]:>5}{our_counts[name]:>3} {k:>4}  "
              f"{cm.edge_types():<12}{'MATCH' if ok else '*** FIELD DIFF ***'}")

    print()
    print("=" * 110)
    print(f"FIELD-DATA DIFFS: {len(diffs)} of {len(pairs)} our-kinds")
    print("=" * 110)
    for name, cid, k, om, cm in diffs:
        print(f"\n--- {name}  <->  {cid}  (type {carc_type[cid]}, our tile rotated {k}x90CW)")
        print(f"    edges (N E S W)  : {cm.edge_types()}")
        print(f"    carcasum fields  : {cm.fields_str()}")
        print(f"    ours     fields  : {om.fields_str()}")
        et = cm.edge_types()
        for h, cs in om.fields:
            bad = [JCZ_HALF[i] for i in sorted(h) if et[i // 2] == "C"]
            if bad:
                print(f"    >>> ours claims half-edges lying ON A CITY EDGE: {' '.join(bad)}")

    return 1 if (diffs or mismatches or unresolved) else 0


if __name__ == "__main__":
    sys.exit(main())
