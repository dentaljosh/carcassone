#!/usr/bin/env python3
"""`RUN/FLOORS.json` — the owner's floor choice, frozen, and the ONE reader of it.

DESIGN R4-2.2 makes the completion floor an **owner parameter**. R4-8b makes the
ORDER in which it is chosen the thing that keeps it ungameable:

    1. `c_IF` remeasure (4b-pre judge smokes, idle box)
    2. owner picks a row of R4-2.2, seeing the power ladder AND the false-VOID column
    3. `RUN/FLOORS.json` is written
    4. the blind commit — the R4 pair AND `FLOORS.json`, in ONE commit
    5. only THEN is the extension band claimed, and generation starts

⚠️ `FLOORS.json` must exist **before the extension band is claimed and before one
game is generated**. A floor chosen — or adjusted — after supply is known is a
floor fitted to the data, which is the failure `G-COMPLETE` exists to prevent.
It is also the **frozen denominator** for the R4-3 exclusion bound, so it must
predate the corpus for that reason too: otherwise the bound would grow with the
corpus and "generate more games" would double as a way to buy headroom for
exclusions after seeing them.

Four components read this file and must agree exactly on it — `gate_disjoint.py`
(the bound's denominator), `build_widening_corpus.sh` (stratum sizing),
`run_gen.sh` (the extension sub-ranges) and `analyze_widening.py` (the
`G-COMPLETE` floors). This module is that single reader.

Schema (READ_RULE §2a):
    {n1, n2, option_label, r_s1, r_s2cap,
     games_extension_s1, games_extension_s2, sub_ranges: {s1: [lo,hi]|null,
                                                          s2: [lo,hi]|null}}
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

# --- the SIZING CONSTANTS of record (DESIGN R4-2.1, measured on band 135e9) --- #
R_S1 = 1.574          # qualifying-deduped S1 positions per game (551 / 350)
R_S2CAP = 0.206       # capped S2 plies per game (103 / 500)
BANKED_S1 = 551       # already in hand from band 135e9, minus R4-3 exclusions
BANKED_S2CAP = 103

#: mining ceilings the rates were measured at. Changing either INVALIDATES the
#: corresponding rate and requires a re-measure, never a re-scale (R4-2.1).
MAX_PER_GAME_S1 = 4
MAX_PER_GAME_S2 = 3

EXTENSION_BAND = 137000000000
GATE_FLOOR_FRACTION = 0.95            # G-COMPLETE reads ⌈0.95 × n⌉
EXCLUSION_BOUND_FRACTION = 0.005      # R4-3 rule 6, the ⌈·⌉ form

#: DESIGN R4-2.2's menu. The owner picks a ROW; nothing here invents one.
OPTIONS = {
    "FULL":       {"n1": 1350, "n2": 1100},
    "all-floors": {"n1": 1283, "n2": 1045},
    "S2 at 700":  {"n1": 1350, "n2": 700},    # PLAN_J's own floor (R4-9 rec.)
    "S2 at 500":  {"n1": 1350, "n2": 500},
    "S2 at 400":  {"n1": 1350, "n2": 400},
    "S1 ONLY":    {"n1": 1350, "n2": 0},      # rung 3 NOT BOUGHT
}

REQUIRED_KEYS = ("n1", "n2", "option_label", "r_s1", "r_s2cap",
                 "games_extension_s1", "games_extension_s2", "sub_ranges")


class FloorsError(RuntimeError):
    """`FLOORS.json` is missing, malformed or internally inconsistent. Never
    repaired in place: the floor is a committed parameter, so a bad one is a
    STOP, not a default."""


# --------------------------------------------------------------------------- #
def games_needed(n1: int, n2: int, *, banked_s1=BANKED_S1, banked_s2=BANKED_S2CAP,
                 r_s1=R_S1, r_s2cap=R_S2CAP) -> tuple:
    """R4-2.2: `⌈(n₁−551)/1.574⌉ + ⌈(n₂−103)/0.206⌉`, as two DISJOINT
    requirements — never one sum mined from one range (that is what fails
    `strata_root_overlap == 0` on a healthy corpus)."""
    g1 = max(0, math.ceil((n1 - banked_s1) / r_s1)) if n1 else 0
    g2 = max(0, math.ceil((n2 - banked_s2) / r_s2cap)) if n2 else 0
    return g1, g2


def sub_ranges(g1: int, g2: int, *, band=EXTENSION_BAND) -> dict:
    """The two COMMITTED extension sub-ranges: S1 first, then S2, contiguous.

    ⚠️ The split is a CONJUNCT, not documentation (R4.1/B2). Every extension seed
    must lie in the sub-range of the stratum that mined it; mining both strata
    from one undivided range fails `G-DISJOINT` §2b(v) on a healthy corpus."""
    s1 = [band, band + g1 - 1] if g1 else None
    s2 = [band + g1, band + g1 + g2 - 1] if g2 else None
    return {"s1": s1, "s2": s2}


def build(option_label: str, **overrides) -> dict:
    """The FLOORS.json body for one row of R4-2.2."""
    if option_label not in OPTIONS:
        raise FloorsError(f"unknown option {option_label!r}; the owner must pick "
                          f"a row of DESIGN R4-2.2: {sorted(OPTIONS)}")
    n1 = int(overrides.get("n1", OPTIONS[option_label]["n1"]))
    n2 = int(overrides.get("n2", OPTIONS[option_label]["n2"]))
    g1, g2 = games_needed(n1, n2)
    return {
        "option_label": option_label,
        "n1": n1, "n2": n2,
        "r_s1": R_S1, "r_s2cap": R_S2CAP,
        "banked_s1": BANKED_S1, "banked_s2cap": BANKED_S2CAP,
        "games_extension_s1": g1, "games_extension_s2": g2,
        "sub_ranges": sub_ranges(g1, g2),
        "extension_band": EXTENSION_BAND,
        "gate_floor_s1": math.ceil(GATE_FLOOR_FRACTION * n1),
        "gate_floor_s2": math.ceil(GATE_FLOOR_FRACTION * n2),
        "exclusion_bound_s1": math.ceil(EXCLUSION_BOUND_FRACTION * n1),
        "exclusion_bound_s2": math.ceil(EXCLUSION_BOUND_FRACTION * n2),
        "max_per_game_s1": MAX_PER_GAME_S1,
        "max_per_game_s2": MAX_PER_GAME_S2,
        "rung3_bought": bool(n2),
        "note": "DESIGN R4-2.2. Written BEFORE the extension band is claimed and "
                "before one game is generated (R4-8b). Also the FROZEN "
                "denominator for the R4-3 exclusion bound: a VOID is not curable "
                "by generating more games.",
    }


def load(path) -> dict:
    """Read + VALIDATE. Every consumer goes through here, so a malformed floor
    file fails once, loudly, in one place."""
    p = Path(path)
    if not p.is_file():
        raise FloorsError(
            f"FLOORS.json not found: {p}. R4-8b: it is written BEFORE the "
            f"extension band is claimed and committed WITH the blind pair. "
            f"Nothing may proceed without it — the floors, the extension "
            f"sub-ranges and the exclusion denominator all live here.")
    try:
        d = json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        raise FloorsError(f"{p}: not JSON ({exc})") from exc
    missing = [k for k in REQUIRED_KEYS if k not in d]
    if missing:
        raise FloorsError(f"{p}: missing required key(s) {missing}")

    n1, n2 = int(d["n1"]), int(d["n2"])
    g1, g2 = int(d["games_extension_s1"]), int(d["games_extension_s2"])
    want1, want2 = games_needed(n1, n2, r_s1=float(d["r_s1"]),
                                r_s2cap=float(d["r_s2cap"]))
    if (g1, g2) != (want1, want2):
        raise FloorsError(
            f"{p}: games_extension_s1/s2 = ({g1}, {g2}) but the committed rates "
            f"and floors imply ({want1}, {want2}). The extension size is DERIVED "
            f"from the floor, never chosen separately.")
    sr = d["sub_ranges"] or {}
    want_sr = sub_ranges(g1, g2, band=int(d.get("extension_band", EXTENSION_BAND)))
    for tag in ("s1", "s2"):
        got, exp = sr.get(tag), want_sr[tag]
        if (got or None) != (exp or None):
            raise FloorsError(
                f"{p}: sub_ranges.{tag} = {got} but the committed split implies "
                f"{exp}. Every extension seed must lie in the sub-range of the "
                f"stratum that mined it — the split is a G-DISJOINT conjunct.")
    if n2 == 0 and sr.get("s2"):
        raise FloorsError(f"{p}: n2 == 0 (S1 ONLY) but an S2 sub-range is "
                          f"committed; none may be generated.")
    d.setdefault("gate_floor_s1", math.ceil(GATE_FLOOR_FRACTION * n1))
    d.setdefault("gate_floor_s2", math.ceil(GATE_FLOOR_FRACTION * n2))
    d.setdefault("rung3_bought", bool(n2))
    return d


def denominator(floors: dict, stratum: str) -> tuple:
    """`(value, source)` — the FROZEN denominator of the R4-3 exclusion bound.

    `source` is emitted as `denominator_source`, which `G-DISJOINT` READS:
    **ABSENT IS FAIL**, so it is returned here rather than left to each caller
    to spell."""
    key = "n1" if str(stratum).upper() == "S1" else "n2"
    return int(floors[key]), f"RUN/FLOORS.json::{key}"


def exclusion_bound(floors: dict, stratum: str) -> tuple:
    """`(bound_n, denominator, denominator_source)` — the ⌈0.005 × n⌉ form, the
    ONE spelling (R4-3 rule 6; the '≤15 absolute' conjunct is DELETED as inert:
    it can only bind above n = 3,000, which no R4-2.2 option reaches)."""
    den, src = denominator(floors, stratum)
    return math.ceil(EXCLUSION_BOUND_FRACTION * den), den, src


def gate_floor(floors: dict, stratum: str) -> int:
    """`G-COMPLETE`'s ⌈0.95 × n⌉, evaluated AFTER the §2b exclusions."""
    key = "n1" if str(stratum).upper() == "S1" else "n2"
    return math.ceil(GATE_FLOOR_FRACTION * int(floors[key]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write", help="emit FLOORS.json for one R4-2.2 row")
    w.add_argument("--option", required=True, choices=sorted(OPTIONS))
    w.add_argument("--out", required=True)
    v = sub.add_parser("verify", help="validate an existing FLOORS.json")
    v.add_argument("--path", required=True)
    r = sub.add_parser("range", help="one end of one committed sub-range "
                                     "(empty when the stratum has none)")
    r.add_argument("--path", required=True)
    r.add_argument("--stratum", required=True, choices=("s1", "s2"))
    r.add_argument("--end", required=True, choices=("lo", "hi"))
    a = ap.parse_args(argv)

    if a.cmd == "range":
        # the shell asks for ONE number; an absent sub-range prints nothing, so
        # the caller's `[ -n "$X" ]` guard is the whole error path
        rng = (load(a.path).get("sub_ranges") or {}).get(a.stratum)
        print("" if not rng else rng[0 if a.end == "lo" else 1])
        return 0

    if a.cmd == "write":
        body = build(a.option)
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(body, indent=2, sort_keys=True))
        print(json.dumps(body, indent=2, sort_keys=True))
        print(f"[floors] -> {a.out}")
        return 0
    print(json.dumps(load(a.path), indent=2, sort_keys=True))
    print(f"[floors] {a.path} VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
