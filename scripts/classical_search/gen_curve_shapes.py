#!/usr/bin/env python3
"""Generate the Part-A curvature-probe candidate curves from the frozen parametrization.

Source of truth: measurement/curve_shape_scope_20260809/SCOPE.md §1.1 +
PREREG_DRAFT.md §4, reproduced VERBATIM:

    curve[3-j] = -d * (j/3)**gamma            j = 1,2,3
    curve[3]   = 0                            (PINNED -- identifiability)
    curve[3+i] = sum_{u<=i} g_u ,  g_1 = s0 ,  g_i = s1 * rho**(i-2)   i = 1..4

    "After generation the table is rescaled so its L1 norm equals production's."

Production = (d=10, gamma=2, s0=2.5, s1=1.25, rho=1.0).

⚠️ C0_identity uses the LITERAL production table, NOT its parametric approximation
(SCOPE §1.1: "the sweep should enqueue the *literal* production table as trial 0
rather than its parametric approximation, and treat the (d,gamma) fit as a
reparametrization only"). The parametric low side is -10/-4.444/-1.111 vs the
literal -10/-5/-1.25, so C1/C2/C3 -- which ARE generated from the family --
carry a small low-side offset relative to C0 that is NOT part of the intended
contrast. That is a property of the pre-registered design, recorded here so the
read-out can state it rather than discover it.
"""
import json

CURVE125 = (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25)
PROD_L1 = sum(abs(x) for x in CURVE125)  # 33.75

CELLS = {
    # id            d     gamma  s0    s1    rho
    "C0_identity": None,  # literal production table, see docstring
    "C1_flattop": (10.0, 2.0, 2.5, 1.25, 0.4),
    "C2_broadlow": (16.0, 0.8, 2.5, 1.25, 1.0),
    "C3_hoard": (10.0, 2.0, 2.5, 1.25, 1.2),
}


def generate(d, gamma, s0, s1, rho, *, rescale=True):
    curve = [0.0] * 8
    for j in (1, 2, 3):
        curve[3 - j] = -d * (j / 3.0) ** gamma
    curve[3] = 0.0
    gs = [s0] + [s1 * rho ** (i - 2) for i in (2, 3, 4)]
    acc = 0.0
    for i, g in enumerate(gs, start=1):
        acc += g
        curve[3 + i] = acc
    if rescale:
        l1 = sum(abs(x) for x in curve)
        if l1 > 0:
            k = PROD_L1 / l1
            curve = [x * k for x in curve]
    return [round(x, 6) for x in curve]


def main() -> int:
    out = {}
    for cid, params in CELLS.items():
        if params is None:
            curve, note = list(CURVE125), "literal production curve125 (identity cell)"
        else:
            curve = generate(*params)
            note = "generated from (d,gamma,s0,s1,rho), L1-rescaled to production's 33.75"
        out[cid] = {
            "v29_meeple_curve": curve,
            "params": (dict(zip(("d", "gamma", "s0", "s1", "rho"), params))
                       if params else None),
            "l1": round(sum(abs(x) for x in curve), 6),
            "note": note,
        }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
