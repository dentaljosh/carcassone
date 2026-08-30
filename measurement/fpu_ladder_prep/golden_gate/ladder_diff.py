#!/usr/bin/env python3
"""Adjudicate the FPU DOSE-LADDER's GOLDEN GATE from six `identity_leg.py` legs.

    python ladder_diff.py OLD.json NEW.json CTRL_005.json CTRL_010.json \
        CTRL_015.json CTRL_030.json --out ../FPU_BITEXACT_LADDER.json

THE PROPOSITIONS, and why each is needed:

  ⭐ `IDENTITY`       `OLD.leg_sha256 == NEW.leg_sha256` — the fpu plumbing did
                      not move the DEFAULT path, ON THE WHEEL THIS ROUND WILL
                      PLAY. The round's opponent is the unmodified champion; a
                      moved default would mean every rung grades a moved
                      baseline.
  ⭐⭐ `POSITIVE-*`    one per rung: `CTRL_<dose>.leg_sha256 != NEW.leg_sha256`.
                      ⛔ Without these `IDENTITY` is worth nothing — the
                      hard-coded `None` this family removed would have passed
                      `IDENTITY` perfectly. ⭐ `POSITIVE-0.05` is the
                      load-bearing one: it is the dose a dose-blind build would
                      be hardest to distinguish from the champion.
  ⭐⭐ `DOSE-DISTINCT` the four dosed legs differ FROM EACH OTHER. **NEW IN THIS
                      ROUND, and it is the check a LADDER specifically needs:** a
                      build that clamped, rounded or bucketed the dose on the
                      way to the `SearchConfigRs` slot would pass every
                      `POSITIVE-*` and still flatten the ladder into one
                      measurement repeated four times — with four healthy-looking
                      manifests, four healthy winrates and four distinct bands.
  ⭐⭐ `ONE-WHEEL`     all six legs on ONE `carc_rs_binary_sha`, which is then
                      STAMPED into the artefact. `run_cells.sh` refuses unless
                      that sha equals the launching box's own installed binary.
                      ⚠️⚠️ THIS IS WHY THE PARENT ROUND'S `FPU_BITEXACT.json` IS
                      NOT INHERITED: it was adjudicated on `f6316d42838574de`,
                      and the S1 `R7`/`R6` merge (commit `316df67d`) has since
                      changed `carc_core::search` and `fair::search_worlds` — the
                      modules that implement the FPU rule and the PIMC descent.
                      The counters are ARGUED play-neutral; "argued play-neutral"
                      is exactly what the hard-coded `None` also was.
  ⭐ `TWO-TREES`      `OLD.src_tree != NEW.src_tree`, and every CTRL ran on NEW.
                      Otherwise the "old code" leg is the new code run twice.
  `SAME-SEEDS` / `SAME-BUDGET` — the legs are actually comparable.
  ⭐⭐ `AUDIT-ADJUDICATED` — the audited false-negative reproduced as a NUMBER:
                      `HeuristicPriorConfig` has no `fpu_reduction` field on the
                      OLD tree and has one on the NEW tree, where `POSITIVE-*`
                      shows it reaching play.

⛔ NO NUMBER HERE IS A STRENGTH MEASUREMENT. The budget is `k2 x 96`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

#: ⛔ The four rungs, restated here ONLY so this script can run standalone. The
#: runner passes the legs in this order and `sanity` re-derives the set from the
#: legs' own `requested_fpu`, so a mismatch is caught rather than assumed.
RUNG_DOSES = (0.05, 0.10, 0.15, 0.30)


def _load(p: Path) -> dict:
    return json.loads(Path(p).read_text())


def adjudicate(old: dict, new: dict, ctrls: list[dict]) -> dict:
    checks = []

    def chk(cid, ok, detail, why):
        checks.append({"check": cid, "ok": bool(ok), "detail": detail, "why": why})

    legs = {"OLD": old, "NEW": new}
    for c in ctrls:
        legs[f"CTRL_{c.get('requested_fpu')}"] = c

    # --- ONE-WHEEL --------------------------------------------------------
    shas = {k: v.get("carc_rs_binary_sha") for k, v in legs.items()}
    distinct = {v for v in shas.values() if v}
    one_wheel = len(distinct) == 1 and all(shas.values())
    wheel = sorted(distinct)[0] if len(distinct) == 1 else None
    chk("ONE-WHEEL", one_wheel, shas,
        f"all six legs ran against ONE installed carc_rs binary ({wheel}) — the "
        "fpu change is python-only and the binary is a CONSTANT of this "
        "comparison. ⭐ It is STAMPED into this artefact and run_cells.sh "
        "refuses unless it equals the launching box's own installed binary."
        if one_wheel else
        "⛔ the legs did not share a carc_rs binary. This gate compares CODE, "
        "not builds; a moved binary voids it.")

    # --- TWO-TREES --------------------------------------------------------
    trees = {k: v.get("src_tree") for k, v in legs.items()}
    ctrl_on_new = all(c.get("src_tree") == new.get("src_tree") for c in ctrls)
    two_trees = (bool(trees["OLD"]) and bool(trees["NEW"])
                 and trees["OLD"] != trees["NEW"] and ctrl_on_new)
    chk("TWO-TREES", two_trees, trees,
        "OLD and NEW resolved DIFFERENT source trees, and every dosed control "
        "ran on the NEW one" if two_trees else
        "⛔ the OLD leg is not a different tree from the NEW leg (or a control "
        "did not run on NEW) — 'old code vs new code' was not actually tested")

    # --- SAME-SEEDS / SAME-BUDGET ----------------------------------------
    seed_sets = [tuple(v.get("seeds") or ()) for v in legs.values()]
    seeds_ok = bool(seed_sets[0]) and all(s == seed_sets[0] for s in seed_sets)
    chk("SAME-SEEDS", seeds_ok, {"n": len(seed_sets[0]), "identical": seeds_ok},
        "all six legs played the same frozen deck set" if seeds_ok else
        "⛔ the legs played different decks — nothing here is a comparison")

    budgets = [v.get("budget") for v in legs.values()]
    budget_ok = all(b == budgets[0] for b in budgets)
    chk("SAME-BUDGET", budget_ok, budgets[0],
        "identical search shape on all six legs" if budget_ok else
        "⛔ the legs ran different budgets")

    # --- IDENTITY ---------------------------------------------------------
    ident = (old.get("leg_sha256") == new.get("leg_sha256")
             and bool(new.get("leg_sha256")))
    chk("IDENTITY", ident,
        {"old": old.get("leg_sha256"), "new": new.get("leg_sha256"),
         "per_game_mismatches": [
             {"seed": a.get("seed"), "old": a.get("actions_sha256"),
              "new": b.get("actions_sha256")}
             for a, b in zip(old.get("games") or [], new.get("games") or [])
             if a.get("actions_sha256") != b.get("actions_sha256")][:10]},
        "⭐ BIT-IDENTICAL at fpu_reduction=None ON THIS WHEEL: the plumbing did "
        "not move the champion's play by one action" if ident else
        "⛔ THE DEFAULT PATH MOVED. The round cannot launch over this: its "
        "opponent IS the unmodified champion.")

    # --- POSITIVE, PER RUNG ----------------------------------------------
    for c in ctrls:
        dose = c.get("requested_fpu")
        n_diff = sum(1 for a, b in zip(new.get("games") or [],
                                       c.get("games") or [])
                     if a.get("actions_sha256") != b.get("actions_sha256"))
        total = len(c.get("games") or [])
        pos = (c.get("leg_sha256") != new.get("leg_sha256")
               and bool(c.get("leg_sha256")))
        chk(f"POSITIVE-{dose}", pos,
            {"new": new.get("leg_sha256"), "ctrl": c.get("leg_sha256"),
             "requested_fpu": dose,
             "resolved_fpu_leg0": ((c.get("games") or [{}])[0]).get("resolved_fpu"),
             "games_that_differ": n_diff, "games_total": total},
            f"⭐ the dose BINDS: {n_diff}/{total} games diverge at fpu={dose}."
            + ("  ⭐⭐ THIS IS THE LOAD-BEARING ONE: 0.05 is the smallest dose "
               "the round runs, and a build that ignored or clamped small doses "
               "would flatten the bottom of the ladder while every manifest "
               "looked healthy." if dose == 0.05 else "")
            if pos else
            f"⛔ fpu={dose} played IDENTICALLY to the champion — the dose did "
            "NOT bind. A rung over this is champion-vs-champion.")

    # --- DOSE-DISTINCT ----------------------------------------------------
    ctrl_hashes = {c.get("requested_fpu"): c.get("leg_sha256") for c in ctrls}
    distinct_ctrl = len({h for h in ctrl_hashes.values() if h}) == len(ctrl_hashes)
    collisions = {}
    seen: dict = {}
    for d, h in ctrl_hashes.items():
        if h in seen:
            collisions.setdefault(h, [seen[h]]).append(d)
        else:
            seen[h] = d
    chk("DOSE-DISTINCT", distinct_ctrl and bool(ctrl_hashes),
        {"leg_sha256_by_dose": ctrl_hashes, "collisions": collisions},
        "⭐⭐ the four rung doses produce FOUR DIFFERENT action sequences — the "
        "ladder measures four different agents, not one agent four times"
        if distinct_ctrl else
        "⛔⛔ TWO OR MORE DOSES PLAYED IDENTICALLY: " + json.dumps(collisions)
        + ". The dose is being clamped, rounded or bucketed on the way to the "
          "SearchConfigRs slot. Every POSITIVE-* check can still pass over this "
          "and the ladder would be one measurement repeated, with four healthy "
          "manifests, four healthy winrates and four distinct claimed bands.")

    # --- the rung set actually tested -------------------------------------
    tested = tuple(sorted(float(d) for d in ctrl_hashes if d is not None))
    set_ok = tested == tuple(sorted(RUNG_DOSES))
    chk("RUNG-SET", set_ok, {"tested": list(tested), "frozen": list(RUNG_DOSES)},
        "every frozen rung dose has a control leg" if set_ok else
        "⛔ the control legs do not cover the frozen ladder — a rung whose dose "
        "was never shown to bind may not be played")

    # --- AUDIT-ADJUDICATED -------------------------------------------------
    reach = (new.get("knob_expressible_on_this_tree") is True
             and old.get("knob_expressible_on_this_tree") is False)
    chk("AUDIT-ADJUDICATED", reach,
        {"old_tree_expressible": old.get("knob_expressible_on_this_tree"),
         "new_tree_expressible": new.get("knob_expressible_on_this_tree")},
        "⭐⭐ the audit's finding is ADJUDICATED: HeuristicPriorConfig had no "
        "fpu_reduction field on the OLD tree (so no caller could express the "
        "knob, and rust_agent.search_config_rs passed a hard-coded None into the "
        "SearchConfigRs slot regardless), and has one on the NEW tree where "
        "POSITIVE-* shows it reaching play." if reach else
        "⚠️ the reachability half could not be read from these legs (both trees "
        "report the same expressibility). The SUBSTANTIVE adjudication is "
        "POSITIVE-* and DOSE-DISTINCT; this check records the field-level "
        "before/after.")

    ok = all(c["ok"] for c in checks)
    return {
        "gate": "FPU DOSE-LADDER GOLDEN GATE (bit-exact-when-None + per-rung "
                "positive controls + dose-distinctness, ON THE LAUNCH WHEEL)",
        "verdict": "PASS" if ok else "FAIL",
        "wheel": {"binary_sha": wheel,
                  "build": new.get("carc_rs_build"),
                  "host": new.get("host"),
                  "note": "⚠️ carc_rs_binary_sha is BOX-LOCAL: two boxes "
                          "compiling identical source produce different bytes. "
                          "EACH BOX therefore runs its OWN golden gate before "
                          "its own rungs, and run_cells.sh compares this sha to "
                          "that box's installed binary."},
        "checks": checks,
        "failed": [c["check"] for c in checks if not c["ok"]],
        "legs": {k: {f: v.get(f) for f in
                     ("src_tree", "leg_sha256", "requested_fpu",
                      "knob_expressible_on_this_tree", "carc_rs_binary_sha",
                      "host")}
                 for k, v in legs.items()},
        "riders": [
            "⛔ This is a CODE-PATH gate at a tiny budget (k2 x 96), NEVER a "
            "strength measurement. No number in the legs may be quoted as one.",
            "⛔ It proves the DEFAULT path is unmoved on THIS WHEEL, that every "
            "rung's dose BINDS, and that the four doses are DISTINGUISHABLE. It "
            "says NOTHING about whether any dose HELPS — that is what the four "
            "cells of measurement/fpu_ladder_prep are for.",
            "⚠️⚠️ IT DOES NOT PROVE THE WHEEL MOVE WAS PLAY-NEUTRAL. Comparing "
            "this round's champion play to the parent round's would need the OLD "
            "BINARY rebuilt, and this gate deliberately does not attempt it. "
            "What it does instead is make the wheel a CONSTANT OF THIS ROUND: "
            "every rung and its own opponent play the same binary, and the "
            "adjudicator's G-WHEEL-SAME asserts it per box. ⛔ Cross-ROUND "
            "comparisons against the parent's 0.2 / 0.4 numbers were already "
            "forbidden by CL-068 (cross-band); the wheel move is one more reason.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument("ctrls", type=Path, nargs="+",
                    help="one CTRL leg per frozen rung dose")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    v = adjudicate(_load(args.old), _load(args.new),
                   [_load(p) for p in args.ctrls])
    txt = json.dumps(v, indent=2)
    if args.out:
        args.out.write_text(txt)
        print(f"[ladder_diff] wrote {args.out}")
    print(txt)
    print(f"\nGOLDEN GATE: {v['verdict']}"
          + ("" if v["verdict"] == "PASS" else f" — failed {v['failed']}"))
    return 0 if v["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
