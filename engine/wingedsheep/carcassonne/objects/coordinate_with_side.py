from wingedsheep.carcassonne.objects.coordinate import Coordinate
from wingedsheep.carcassonne.objects.side import Side


class CoordinateWithSide:

    def __init__(self, coordinate: Coordinate, side: Side):
        self.coordinate = coordinate
        self.side = side
        # Patch: immutable value object — cache the hash (see coordinate.py).
        self._hash = hash((coordinate, side))

    def __eq__(self, other):
        return self.coordinate == other.coordinate and self.side == other.side

    def __hash__(self):
        return self._hash
