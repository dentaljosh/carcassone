#!/usr/bin/env python3
"""Adjudicate the GOLDEN GATE from three `identity_fixture.py` legs.

    python identity_diff.py OLD.json NEW.json NEW_FPU02.json [--out FPU_BITEXACT.json]

THE THREE PROPOSITIONS, and why all three are needed:

  ⭐ `IDENTITY`      `OLD.leg_sha256 == NEW.leg_sha256` — the plumbing did not
                     move the DEFAULT path. The round's opponent is the
                     unmodified champion; a moved default would mean every cell
                     grades a moved baseline.
  ⭐ `POSITIVE`      `NEW_FPU02.leg_sha256 != NEW.leg_sha256` — the knob BINDS.
                     ⛔ Without this, `IDENTITY` is worth nothing: the
                     hard-coded `None` this round removes would have passed
                     `IDENTITY` perfectly, every time.
  ⭐⭐ `AUDIT`        the audited false-negative, reproduced as a NUMBER rather
                     than asserted: a leg run on the PRE-change tree with
                     `--fpu 0.2` reports `requested_but_unreachable: true` (the
                     field does not exist there), and — the substantive half —
                     `NEW_FPU02` differs from `NEW` on a tree where it does.
                     Together: the knob was unreachable and is now reachable.

⛔ **THE WHEEL MUST BE ONE WHEEL.** All three legs must carry the same
`carc_rs_binary_sha`. The change is python-only, so a moved binary would mean
the comparison is not the comparison this gate claims to make — and the whole
"no `IDENT` preflight cell is needed" argument (`DESIGN.md` §9) rests on the
binary being a CONSTANT here.

⛔ **AND THE TREES MUST BE TWO TREES.** `OLD.src_tree != NEW.src_tree`, or the
"old code" leg is just the new code run twice — an identity that proves nothing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(p: Path) -> dict:
    return json.loads(Path(p).read_text())


def adjudicate(old: dict, new: dict, ctrl: dict) -> dict:
    checks = []

    def chk(cid, ok, detail, why):
        checks.append({"check": cid, "ok": bool(ok), "detail": detail, "why": why})

    shas = {"OLD": old.get("carc_rs_binary_sha"), "NEW": new.get("carc_rs_binary_sha"),
            "CTRL": ctrl.get("carc_rs_binary_sha")}
    one_wheel = len({v for v in shas.values() if v}) == 1 and all(shas.values())
    chk("ONE-WHEEL", one_wheel, shas,
        "all three legs ran against ONE installed carc_rs binary — the change is "
        "python-only and the binary is a CONSTANT of this comparison"
        if one_wheel else
        "⛔ the legs did not share a carc_rs binary. This gate compares CODE, not "
        "builds; a moved binary voids it and also voids DESIGN §9's argument that "
        "no IDENT preflight cell is needed.")

    trees = {"OLD": old.get("src_tree"), "NEW": new.get("src_tree"),
             "CTRL": ctrl.get("src_tree")}
    two_trees = (bool(trees["OLD"]) and bool(trees["NEW"])
                 and trees["OLD"] != trees["NEW"] and trees["NEW"] == trees["CTRL"])
    chk("TWO-TREES", two_trees, trees,
        "OLD and NEW resolved DIFFERENT source trees, and the positive control "
        "ran on the NEW one" if two_trees else
        "⛔ the OLD leg is not a different tree from the NEW leg (or the control "
        "did not run on NEW) — 'old code vs new code' was not actually tested")

    seeds_ok = (old.get("seeds") == new.get("seeds") == ctrl.get("seeds")
                and bool(new.get("seeds")))
    chk("SAME-SEEDS", seeds_ok,
        {"n": len(new.get("seeds") or []), "identical": seeds_ok},
        "all three legs played the same frozen deck set" if seeds_ok else
        "⛔ the legs played different decks — nothing here is a comparison")

    budget_ok = old.get("budget") == new.get("budget") == ctrl.get("budget")
    chk("SAME-BUDGET", budget_ok, new.get("budget"),
        "identical search shape on all three legs" if budget_ok else
        "⛔ the legs ran different budgets")

    ident = (old.get("leg_sha256") == new.get("leg_sha256")
             and bool(new.get("leg_sha256")))
    chk("IDENTITY", ident,
        {"old": old.get("leg_sha256"), "new": new.get("leg_sha256"),
         "per_game_mismatches": [
             {"seed": a.get("seed"), "old": a.get("actions_sha256"),
              "new": b.get("actions_sha256")}
             for a, b in zip(old.get("games") or [], new.get("games") or [])
             if a.get("actions_sha256") != b.get("actions_sha256")][:10]},
        "⭐ BIT-IDENTICAL at fpu_reduction=None: the plumbing did not move the "
        "champion's play by one action" if ident else
        "⛔ THE DEFAULT PATH MOVED. The round cannot launch over this: its "
        "opponent IS the unmodified champion.")

    pos = (ctrl.get("leg_sha256") != new.get("leg_sha256")
           and bool(ctrl.get("leg_sha256")))
    n_diff = sum(1 for a, b in zip(new.get("games") or [], ctrl.get("games") or [])
                 if a.get("actions_sha256") != b.get("actions_sha256"))
    chk("POSITIVE", pos,
        {"new": new.get("leg_sha256"), "ctrl": ctrl.get("leg_sha256"),
         "requested_fpu": ctrl.get("requested_fpu"),
         "resolved_fpu_leg0": ((ctrl.get("games") or [{}])[0]).get("resolved_fpu"),
         "games_that_differ": n_diff,
         "games_total": len(ctrl.get("games") or [])},
        f"⭐ the knob BINDS: {n_diff}/{len(ctrl.get('games') or [])} games diverge "
        "at fpu=0.2. A knob that changed nothing would be indistinguishable from "
        "the hard-coded None this round removes." if pos else
        "⛔ fpu=0.2 played IDENTICALLY to the champion — the knob did NOT bind. "
        "This is the audited defect, still present.")

    reach = (new.get("knob_expressible_on_this_tree") is True
             and old.get("knob_expressible_on_this_tree") is False)
    chk("AUDIT-ADJUDICATED", reach,
        {"old_tree_expressible": old.get("knob_expressible_on_this_tree"),
         "new_tree_expressible": new.get("knob_expressible_on_this_tree")},
        "⭐⭐ the audit's finding is ADJUDICATED: HeuristicPriorConfig had no "
        "fpu_reduction field on the OLD tree (so no caller could express the "
        "knob, and rust_agent.search_config_rs passed a hard-coded None into the "
        "SearchConfigRs slot regardless), and has one on the NEW tree where "
        "POSITIVE shows it reaching play." if reach else
        "⚠️ the reachability half could not be read from these legs (both trees "
        "report the same expressibility). The SUBSTANTIVE adjudication is "
        "POSITIVE; this check only records the field-level before/after.")

    ok = all(c["ok"] for c in checks)
    return {
        "gate": "FPU GOLDEN GATE (bit-exact-when-None + positive control)",
        "verdict": "PASS" if ok else "FAIL",
        "checks": checks,
        "failed": [c["check"] for c in checks if not c["ok"]],
        "legs": {"OLD": {k: old.get(k) for k in
                         ("src_tree", "leg_sha256", "requested_fpu",
                          "knob_expressible_on_this_tree", "host")},
                 "NEW": {k: new.get(k) for k in
                         ("src_tree", "leg_sha256", "requested_fpu",
                          "knob_expressible_on_this_tree", "host")},
                 "CTRL": {k: ctrl.get(k) for k in
                          ("src_tree", "leg_sha256", "requested_fpu",
                           "knob_expressible_on_this_tree", "host")}},
        "riders": [
            "⛔ This is a CODE-PATH gate at a tiny budget (k2 x 96), NEVER a "
            "strength measurement. No number in the legs may be quoted as one.",
            "⛔ It proves the DEFAULT path is unmoved and the knob BINDS. It says "
            "NOTHING about whether the knob HELPS — that is what the three cells "
            "of measurement/fpu_resurrection_prep are for.",
            "⭐ It is also why this round carries no IDENT preflight CELL: the "
            "phasegate precedent needed one because ITS wheel moved (a stale "
            "wheel would have served a gate-blind arbiter). No rust change was "
            "made here, ONE-WHEEL asserts the binary is a constant, and this "
            "gate covers the only thing that did move.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument("ctrl", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    v = adjudicate(_load(args.old), _load(args.new), _load(args.ctrl))
    txt = json.dumps(v, indent=2)
    if args.out:
        args.out.write_text(txt)
        print(f"[identity_diff] wrote {args.out}")
    print(txt)
    print(f"\nGOLDEN GATE: {v['verdict']}"
          + ("" if v["verdict"] == "PASS" else f" — failed {v['failed']}"))
    return 0 if v["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
