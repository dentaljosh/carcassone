from enum import Enum

from wingedsheep.carcassonne.objects.side import Side


class FarmerSide(Enum):
    TLL = "tll"
    TLT = "tlt"
    TRT = "trt"
    TRR = "trr"
    BLL = "bll"
    BLB = "blb"
    BRB = "brb"
    BRR = "brr"

    def to_json(self):
        return self.value

    def __str__(self):
        return self.value

    def get_side(self) -> Side:
        # Patch: return a value precomputed at import (loop below). The original
        # walked self.value[2] through the enum .value descriptor up to 4× per
        # call — a top-3 self-time hog in the v2.5 leaf's farm traversal.
        return self._side


_FARMER_SIDE_OF = {"l": Side.LEFT, "r": Side.RIGHT, "b": Side.BOTTOM, "t": Side.TOP}
for _member in FarmerSide:
    _member._side = _FARMER_SIDE_OF[_member.value[2]]
del _member, _FARMER_SIDE_OF
