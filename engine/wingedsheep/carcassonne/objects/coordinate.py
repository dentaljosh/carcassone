class Coordinate:

    def __init__(self, row: int, column: int):
        self.row = row
        self.column = column
        # Patch: immutable value object — cache the hash (built billions of
        # times in the v2.5 leaf's set-based graph traversal).
        self._hash = hash((row, column))

    def __eq__(self, other):
        return self.row == other.row and self.column == other.column

    def __hash__(self):
        return self._hash
