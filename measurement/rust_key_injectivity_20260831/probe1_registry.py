#!/usr/bin/env python3
"""Probe 1 — is the RUST node key injective at the TILE level?

READ-ONLY. No production code touched. Pure registry read via `carc_rs`.

The rust node key (`carc_core::repr_key::string_representation`) writes, per
placed tile, `(row, col, description, rot_sig_repr)` where
`rot_sig_repr = ((4 outer edge types), shield, chapel, flowers)`.  The ROTATION
INDEX is NOT in the key.  So two rotations `r != r'` of the same base tile are
INDISTINGUISHABLE to the key iff `rot_sig_repr[r] == rot_sig_repr[r']`.

This probe:
  1. enumerates every (description, rot) in the rust registry and groups by
     (description, rot_sig_repr) -> the KEY-COLLIDING rotation classes;
  2. for each colliding class, reads the rust FARM TABLE for both rotations and
     asks whether the two rotations are PHYSICALLY the same tile:
       * `geom`  = multiset of (frozenset(tile_connections), frozenset(city_sides))
                   -- the farm regions as they connect to neighbours; and
       * `offer` = the SET of `farmer_positions[0]` (the ONLY corner the engine
                   ever offers per region: `__possible_farmer_position`).
     `geom` equal  => same physical board.
     `offer` differing => the LEGAL FARMER ACTION IDS differ, i.e. the key
     collision is OBSERVABLE in the action set.

Both R9 states are read (`farm_table(r9)`), because the deployed rules profile
`fixed_v1` turns R9 ON and the historic profile turns it OFF.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import carc_rs

HERE = Path(__file__).resolve().parent


def farm_by_rot(r9: bool):
    """(description, rot) -> list of (farmer_positions, tile_connections, city_sides)."""
    out = defaultdict(list)
    for desc, slot, rot, fpos, tconn, csides in carc_rs.farm_table(r9):
        out[(desc, int(rot))].append((slot, tuple(fpos), tuple(tconn), tuple(csides)))
    for k in out:
        out[k].sort()
    return out


def geom(slots):
    """Physical farm geometry: unordered regions keyed by how they touch the world."""
    return sorted(
        (tuple(sorted(set(tconn))), tuple(sorted(set(csides))), tuple(sorted(set(fpos))))
        for _slot, fpos, tconn, csides in slots
    )


def offer(slots):
    """The corner set the engine actually OFFERS (farmer_positions[0] per region)."""
    return sorted({fpos[0] for _slot, fpos, _tc, _cs in slots if fpos})


def main() -> int:
    rot_tab = carc_rs.rotated_tile_table()  # (description, rot, rot_sig_repr)
    classes = defaultdict(list)
    for desc, rot, sig in rot_tab:
        classes[(desc, sig)].append(int(rot))

    colliding = {k: sorted(v) for k, v in classes.items() if len(v) > 1}

    report = {
        "r9_enabled_in_process": carc_rs.r9_enabled(),
        "n_rotated_tiles": len(rot_tab),
        "n_distinct_descriptions": len({d for d, _, _ in rot_tab}),
        "n_key_classes": len(classes),
        "n_colliding_classes": len(colliding),
        "colliding": [],
    }

    for r9 in (False, True):
        ft = farm_by_rot(r9)
        for (desc, sig), rots in sorted(colliding.items()):
            slots = {r: ft.get((desc, r), []) for r in rots}
            geoms = {r: geom(slots[r]) for r in rots}
            offers = {r: offer(slots[r]) for r in rots}
            ref = rots[0]
            report["colliding"].append(
                {
                    "r9": r9,
                    "description": desc,
                    "rot_sig_repr": sig,
                    "rotations": rots,
                    "n_farm_slots": {str(r): len(slots[r]) for r in rots},
                    # PHYSICAL identity of the placed tile
                    "geometry_identical": all(geoms[r] == geoms[ref] for r in rots),
                    # OBSERVABLE consequence: does the offered farmer corner move?
                    "offered_corners": {str(r): offers[r] for r in rots},
                    "offered_corners_identical": all(
                        offers[r] == offers[ref] for r in rots
                    ),
                    "geometry": {str(r): geoms[r] for r in rots},
                }
            )

    n_geom_diff = sum(1 for c in report["colliding"] if not c["geometry_identical"])
    n_offer_diff = sum(
        1 for c in report["colliding"] if not c["offered_corners_identical"]
    )
    report["summary"] = {
        "classes_with_DIFFERENT_physical_geometry": n_geom_diff,
        "classes_with_DIFFERENT_offered_farmer_corners": n_offer_diff,
        "verdict_tile_level": (
            "KEY IS NON-INJECTIVE OVER ROTATIONS"
            if colliding
            else "key injective over rotations"
        ),
    }
    (HERE / "REGISTRY_COLLISIONS.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report["summary"], indent=1))
    print()
    for c in report["colliding"]:
        if c["r9"]:
            continue
        print(
            f"{c['description']:<28} rots={c['rotations']} "
            f"geom_same={c['geometry_identical']!s:<5} "
            f"offer_same={c['offered_corners_identical']!s:<5} "
            f"offers={c['offered_corners']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
