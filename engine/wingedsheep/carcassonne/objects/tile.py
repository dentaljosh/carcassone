import json
import sys
from typing import Set
import numpy as np

from wingedsheep.carcassonne.objects.connection import Connection
from wingedsheep.carcassonne.objects.farmer_connection import FarmerConnection
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.objects.terrain_type import TerrainType
from wingedsheep.carcassonne.utils.side_modification_util import SideModificationUtil

np.set_printoptions(suppress=True, linewidth=np.nan, threshold=sys.maxsize)


class Tile:
    def __init__(self,
                 description: str = "",
                 turns: int = 0,
                 road: [Connection] = (),
                 river: [Connection] = (),
                 city: [[Side]] = (),
                 grass: [Side] = (),
                 farms: [FarmerConnection] = (),
                 shield: bool = False,
                 chapel: bool = False,
                 flowers: bool = False,
                 inn: [Side] = (),
                 cathedral: bool = False,
                 unplayable_sides: [Side] = (),
                 image: str = "Empty.png"):
        self.description = description
        self.turns = turns
        self.road = road
        self.river = river
        self.city = city
        self.grass = grass
        self.farms: [FarmerConnection] = farms
        self.shield = shield
        self.chapel = chapel
        self.flowers = flowers
        self.inn = inn
        self.cathedral = cathedral
        self.unplayable_sides = unplayable_sides
        self.image = image
        # Patched (vendored fork, 2026-05-13): lazy-built per-side TerrainType
        # cache. The original get_type re-derives road/river/city sets from
        # scratch on every call (called ~5M times per self-play game from
        # TilePositionFinder + farmer-position lookups). After the deepcopy
        # patch, tile.get_type became the #1 self-time hotspot.
        self._type_cache: dict | None = None
        # Patched (vendored fork, 2026-05-13): cache the wrapper's rotation
        # signature (4-edge tuple + shield/chapel/flowers booleans) on the
        # Tile itself. Tiles are immutable and shared via canonical refs
        # (base_tiles dict + Tile.turn() returns a fresh Tile per rotation),
        # so the signature for any given Tile reference never changes.
        # string_representation calls this ~880K times per game; caching
        # turns that into ~80 cache misses (once per unique rotated tile).
        self._rot_sig_cache: tuple | None = None

    def get_road_ends(self) -> Set[Side]:
        sides: Set[Side] = set([])
        for road in self.road:
            sides.add(road.a)
            sides.add(road.b)
        return set(sides)

    def get_river_ends(self) -> Set[Side]:
        sides: Set[Side] = set([])
        for road in self.river:
            sides.add(road.a)
            sides.add(road.b)
        return set(sides)

    def get_city_sides(self) -> Set[Side]:
        sides: Set[Side] = set([])
        for side_list in self.city:
            for side in side_list:
                sides.add(side)
        return set(sides)

    def has_river(self) -> bool:
        return len(self.river) > 0

    def get_type(self, side: Side):
        cache = self._type_cache
        if cache is None:
            cache = self._build_type_cache()
            self._type_cache = cache
        return cache.get(side)

    def _build_type_cache(self) -> dict:
        """Precompute (side -> TerrainType) for all 9 sides once. Patched
        (vendored fork, 2026-05-13). Replaces ~5M repeated set-derivations
        per self-play game with one dict lookup per get_type call."""
        unplayable = set(self.unplayable_sides)
        river_ends = self.get_river_ends()
        road_ends = self.get_road_ends()
        city_sides = self.get_city_sides()
        grass_set = set(self.grass)
        cache: dict = {}
        for side in Side:
            if side in unplayable:
                cache[side] = TerrainType.UNPLAYABLE
                continue
            if side == Side.CENTER and self.chapel:
                cache[side] = TerrainType.CHAPEL
                continue
            if side == Side.CENTER and self.flowers:
                cache[side] = TerrainType.FLOWERS
                continue
            if side in river_ends:
                cache[side] = TerrainType.UNPLAYABLE
                continue
            if side in road_ends:
                cache[side] = TerrainType.ROAD
                continue
            if side in city_sides:
                cache[side] = TerrainType.CITY
                continue
            if side in grass_set:
                cache[side] = TerrainType.GRASS
                continue
            cache[side] = None  # falls through (matches original behavior)
        return cache

    def to_json(self):
        return {
            "description": self.description,
            "river": list(map(lambda x: x.to_json(), self.river)),
            "road": list(map(lambda x: x.to_json(), self.road)),
            "city": list(map(lambda x: x.to_json(), self.city)),
            "grass": list(map(lambda x: x.to_json(), self.grass)),
            "farms": list(map(lambda x: x.to_json(), self.farms)),
            "shield": self.shield,
            "chapel": self.chapel,
            "flowers": self.flowers,
            "inn": list(map(lambda x: x.to_json(), self.inn)),
            "unplayable_sides": list(map(lambda x: x.to_json(), self.unplayable_sides))
        }

    def __str__(self):
        return json.dumps(self.to_json(), indent=2)

    def turn(self, times: int):
        return Tile(
            description=self.description,
            turns=times,
            road=list(map(lambda x: SideModificationUtil.turn_connection(x, times), self.road)),
            river=list(map(lambda x: SideModificationUtil.turn_connection(x, times), self.river)),
            city=list(map(lambda x: SideModificationUtil.turn_sides(x, times), self.city)),
            grass=list(map(lambda x: SideModificationUtil.turn_side(x, times), self.grass)),
            farms=list(map(lambda x: SideModificationUtil.turn_farmer_connection(x, times), self.farms)),
            shield=self.shield,
            chapel=self.chapel,
            flowers=self.flowers,
            inn=list(map(lambda x: SideModificationUtil.turn_side(x, times), self.inn)),
            unplayable_sides=list(map(lambda x: SideModificationUtil.turn_side(x, times), self.unplayable_sides)),
            image=self.image
        )
