from wingedsheep.carcassonne.objects.coordinate_with_side import CoordinateWithSide


class City:
    def __init__(self, city_positions: [CoordinateWithSide], finished: bool):
        self.city_positions = city_positions
        self.finished = finished

    # Value equality by position set so a City can be deduped in a set/dict
    # regardless of which find_cities call produced it (defense-in-depth for
    # the farm-scoring double-count; see PointsCollector.count_farm_points).
    def _key(self):
        return frozenset(self.city_positions)

    def __eq__(self, other):
        return isinstance(other, City) and self._key() == other._key()

    def __hash__(self):
        return hash(self._key())
