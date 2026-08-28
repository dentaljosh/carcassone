#!/usr/bin/env python3
"""IDENT-BITEXACT adjudicator — diff two `identity_fixture.py` legs.

⛔ A HARD ABORT (DESIGN §8 step 5): a non-identity here VOIDS THE BUILD, not the
round. Exit 0 == every asserted pair is byte-identical.

The claims, and why they need TWO wheels:

    NEW.all  == OLD.arb      the gate at "all" changed NO played action
    NEW.none == OLD.champ    the armed-but-inert gate IS the champion
    NEW.all  == NEW.arb      an explicitly-set default is the default
    NEW.none == NEW.champ    (within-wheel control for the line above)
    OLD.champ == NEW.champ   the wheel rebuild moved nothing OFF the surface

The pre-change wheel cannot accept `tiearb_phase_gate` at all, so the first two
are CROSS-WHEEL by construction and cannot be produced inside one process.

⚠️ Identity is asserted on the ACTION SEQUENCES — the only thing that is both
fully determined by the code under test and fully determines the game. Final
scores are compared too, as a cheap second surface; they are a FUNCTION of the
actions, so they can only agree, and a disagreement there would mean the ENGINE
moved, not the gate.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# (left_file, left_arm, right_file, right_arm, what it proves)
DEFAULT_PAIRS = [
    ("new", "all", "old", "arb",
     "gate=all is TODAY'S UNGATED ARBITER, bit for bit"),
    ("new", "none", "old", "champ",
     "gate=none is THE UNMODIFIED CHAMPION, bit for bit"),
    ("new", "all", "new", "arb",
     "an explicitly-set default is the default (within-wheel control)"),
    ("new", "none", "new", "champ",
     "armed-but-gated-off is the champion (within-wheel control)"),
    ("old", "champ", "new", "champ",
     "the rebuild moved nothing off the arbiter surface"),
]


def _leg(blob: dict, arm: str) -> dict:
    legs = blob.get("legs") or {}
    if arm not in legs:
        raise SystemExit(f"FAIL: arm {arm!r} absent from {sorted(legs)}")
    return legs[arm]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True, nargs="+",
                    help="PRE-change-wheel fixture json(s)")
    ap.add_argument("--new", required=True, nargs="+",
                    help="POST-change-wheel fixture json(s)")
    args = ap.parse_args()

    def _merge(paths):
        out = {"legs": {}, "config": None, "seeds": None, "carc_rs_file": []}
        for p in paths:
            b = json.loads(Path(p).read_text())
            out["legs"].update(b["legs"])
            if out["config"] is None:
                out["config"], out["seeds"] = b["config"], b["seeds"]
            elif (out["config"], out["seeds"]) != (b["config"], b["seeds"]):
                raise SystemExit(f"FAIL: {p} was produced at a different config")
            out["carc_rs_file"].append(b["carc_rs_file"])
        return out

    side = {"old": _merge(args.old), "new": _merge(args.new)}
    if side["old"]["config"] != side["new"]["config"]:
        raise SystemExit("FAIL: the two wheels' legs ran at different configs — "
                         "an identity claim across them would be meaningless")

    # The legs must actually come from DIFFERENT wheels, or the whole exercise
    # compares a wheel with itself and proves nothing.
    if set(side["old"]["carc_rs_file"]) & set(side["new"]["carc_rs_file"]):
        raise SystemExit("FAIL: old and new legs loaded the SAME carc_rs — "
                         "this diff would be vacuous")
    # ... and the new wheel must actually carry the gate.
    for arm in ("all", "none"):
        if arm in side["new"]["legs"]:
            g = next(iter(side["new"]["legs"][arm]["games"].values()))["phase_gate"]
            if g != arm:
                raise SystemExit(f"FAIL: new leg {arm!r} reports phase_gate={g!r} "
                                 "— the wheel did not carry the knob")
    for arm in ("champ", "arb"):
        if arm in side["old"]["legs"]:
            g = next(iter(side["old"]["legs"][arm]["games"].values()))["phase_gate"]
            if g is not None:
                raise SystemExit(f"FAIL: the OLD leg {arm!r} reports "
                                 f"phase_gate={g!r} — it is not the pre-change wheel")

    ok = True
    rows = []
    for lf, la, rf, ra, why in DEFAULT_PAIRS:
        if la not in side[lf]["legs"] or ra not in side[rf]["legs"]:
            rows.append(("SKIP", f"{lf}.{la} == {rf}.{ra}", "leg absent", why))
            continue
        L, R = _leg(side[lf], la), _leg(side[rf], ra)
        same_sha = L["action_sha256"] == R["action_sha256"]
        bad = [s for s in L["games"]
               if L["games"][s]["actions"] != R["games"][s]["actions"]
               or L["games"][s]["scores"] != R["games"][s]["scores"]]
        good = same_sha and not bad
        ok &= good
        rows.append(("PASS" if good else "FAIL",
                     f"{lf}.{la} == {rf}.{ra}",
                     f"{len(L['games'])} games, sha {L['action_sha256'][:12]} vs "
                     f"{R['action_sha256'][:12]}" + (f", {len(bad)} DIFFER" if bad else ""),
                     why))

    # A positive control: the gated legs MUST differ from the ungated one, or
    # the "identity" above is the trivial identity of a knob that does nothing.
    if "early" in side["new"]["legs"] and "all" in side["new"]["legs"]:
        E, A = side["new"]["legs"]["early"], side["new"]["legs"]["all"]
        moved = E["action_sha256"] != A["action_sha256"]
        fewer = E["fired_plies_total"] < A["fired_plies_total"]
        ok &= moved and fewer
        rows.append(("PASS" if (moved and fewer) else "FAIL",
                     "new.early != new.all",
                     f"fired {E['fired_plies_total']} < {A['fired_plies_total']}",
                     "POSITIVE CONTROL: the gate is not a no-op"))

    w = max(len(r[1]) for r in rows)
    for st, pair, detail, why in rows:
        print(f"[{st}] {pair:<{w}}  {detail}\n        {why}")
    print("\nIDENT-BITEXACT: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
