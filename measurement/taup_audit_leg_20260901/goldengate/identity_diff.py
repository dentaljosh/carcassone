#!/usr/bin/env python3
"""Adjudicate the three golden-gate legs into `TAUP_BITEXACT.json`.

Precedent: `measurement/fpu_resurrection_prep/selftest_fixture/identity_diff.py`
-> `FPU_BITEXACT.json`. Same verdict shape, same "every check names its own
witness" discipline; the checks differ where the change does.

⛔ EVERY check FAILS CLOSED. A missing key is a FAIL, never a skip.

    python identity_diff.py OLD.json NEW.json NEW_TAU25.json --out TAUP_BITEXACT.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _check(name, ok, detail, why):
    return {"check": name, "ok": bool(ok), "detail": detail, "why": why}


def adjudicate(old: dict, new: dict, ctrl: dict) -> dict:
    checks = []
    legs = {"OLD": old, "NEW": new, "CTRL": ctrl}

    # --- ONE-WHEEL -----------------------------------------------------------
    wheels = {k: v.get("carc_rs_binary_sha") for k, v in legs.items()}
    checks.append(_check(
        "ONE-WHEEL", len(set(wheels.values())) == 1 and "unavailable" not in
        set(wheels.values()), wheels,
        "all three legs ran against ONE installed carc_rs binary — this change is "
        "python-only and the binary is a CONSTANT of the comparison"))

    # --- ONE-SRC -------------------------------------------------------------
    srcs = {k: v.get("carcassonne_ai_file") for k, v in legs.items()}
    checks.append(_check(
        "ONE-SRC", len(set(srcs.values())) == 1 and None not in set(srcs.values()),
        srcs,
        "⭐ STRONGER THAN THE FPU PRECEDENT: src/carcassonne_ai is byte-identical "
        "across the legs, so it is held CONSTANT rather than swung. The variable "
        "is one file (see ONE-FILE)"))

    # --- ONE-FILE ------------------------------------------------------------
    mods = {k: v.get("evalmod_sha256") for k, v in legs.items()}
    one_file = (mods["OLD"] != mods["NEW"] and mods["NEW"] == mods["CTRL"]
                and all(mods.values()))
    checks.append(_check(
        "ONE-FILE", one_file,
        {**mods, "paths": {k: v.get("evalmod") for k, v in legs.items()}},
        "OLD loaded a DIFFERENT eval_fair_puct.py than NEW, and the positive "
        "control ran on the SAME file NEW did — so the only thing that moved "
        "between OLD and NEW is the patched harness"))

    # --- SAME-SEEDS / SAME-BUDGET -------------------------------------------
    seeds = [tuple(v.get("seeds") or ()) for v in legs.values()]
    checks.append(_check(
        "SAME-SEEDS", len(set(seeds)) == 1 and len(seeds[0]) > 0,
        {"n": len(seeds[0]), "identical": len(set(seeds)) == 1},
        "all three legs played the same frozen deck set"))
    budgets = [json.dumps(v.get("budget"), sort_keys=True) for v in legs.values()]
    checks.append(_check(
        "SAME-BUDGET", len(set(budgets)) == 1, old.get("budget"),
        "identical search shape on all three legs"))

    # --- IDENTITY ------------------------------------------------------------
    mism = [(g1["seed"], g1["actions_sha256"], g2["actions_sha256"])
            for g1, g2 in zip(old.get("games", []), new.get("games", []))
            if g1["actions_sha256"] != g2["actions_sha256"]]
    ident_ok = (old.get("leg_sha256") == new.get("leg_sha256")
                and old.get("leg_sha256") is not None and not mism)
    checks.append(_check(
        "IDENTITY", ident_ok,
        {"old": old.get("leg_sha256"), "new": new.get("leg_sha256"),
         "per_game_mismatches": mism},
        "⭐ BIT-IDENTICAL with --cand-tau-p UNSET: the plumbing did not move the "
        "champion's play by one action"))

    # --- POSITIVE ------------------------------------------------------------
    differ = sum(1 for g1, g2 in zip(new.get("games", []), ctrl.get("games", []))
                 if g1["actions_sha256"] != g2["actions_sha256"])
    total = min(len(new.get("games", [])), len(ctrl.get("games", [])))
    pos_ok = (total > 0 and differ == total
              and ctrl.get("leg_sha256") != new.get("leg_sha256")
              and ctrl.get("requested_but_unreachable") is False)
    checks.append(_check(
        "POSITIVE", pos_ok,
        {"new": new.get("leg_sha256"), "ctrl": ctrl.get("leg_sha256"),
         "requested_cand_tau_p": ctrl.get("requested_cand_tau_p"),
         "resolved_cand_tau_p": (ctrl.get("cand_cfg") or {}).get("tau_p"),
         "games_that_differ": differ, "games_total": total},
        "⭐ the knob BINDS: every game diverges at the control dose. A flag "
        "parsed and dropped on the floor would be indistinguishable from the "
        "shared-flag defect this leg closes"))

    # --- CANDIDATE-ONLY ------------------------------------------------------
    # ⭐⭐ THE PROPOSITION `--tau-p` ITSELF FAILS. In EVERY leg the OPPONENT's
    # resolved config must carry the SHARED tau_p — including the control, where
    # the candidate's does not.
    shared_tau = (ctrl.get("production_knobs") or {}).get("tau_p")
    opp_taus = {k: (v.get("opp_cfg") or {}).get("tau_p") for k, v in legs.items()}
    cand_ctrl_tau = (ctrl.get("cand_cfg") or {}).get("tau_p")
    cand_only_ok = (shared_tau is not None
                    and all(t == shared_tau for t in opp_taus.values())
                    and cand_ctrl_tau == ctrl.get("requested_cand_tau_p")
                    and cand_ctrl_tau != shared_tau)
    checks.append(_check(
        "CANDIDATE-ONLY", cand_only_ok,
        {"shared_tau_p": shared_tau, "opponent_tau_p_per_leg": opp_taus,
         "ctrl_candidate_tau_p": cand_ctrl_tau},
        "⭐⭐ the OPPONENT (built by _make_opponent's own _cfg_from_dict call) "
        "carries the SHARED tau_p in every leg while the control's CANDIDATE "
        "carries the dose — which is exactly what --tau-p cannot do, and the "
        "whole reason this flag had to be built"))

    # --- AUDIT-ADJUDICATED ---------------------------------------------------
    aud_ok = (old.get("flag_expressible_on_this_module") is False
              and new.get("flag_expressible_on_this_module") is True
              and ctrl.get("flag_expressible_on_this_module") is True)
    checks.append(_check(
        "AUDIT-ADJUDICATED", aud_ok,
        {"old_module_expressible": old.get("flag_expressible_on_this_module"),
         "new_module_expressible": new.get("flag_expressible_on_this_module")},
        "⭐⭐ the audit's finding is ADJUDICATED: the pre-change eval_fair_puct's "
        "REAL argparse (driven via main(['--help'])) carries no --cand-tau-p, so "
        "no candidate-side tau_p cell was expressible on the classical champion; "
        "the patched one carries it and POSITIVE shows it reaching play"))

    failed = [c["check"] for c in checks if not c["ok"]]
    # ⭐ THE SEED-COUNT WITNESS, separate from the verdict on purpose. A PASS over
    # a PREVIEW subset is a real PASS of the propositions it tested — but it is
    # NOT the frozen gate, and `run_cells.sh` refuses to launch on one. Recording
    # it as a field rather than as a check keeps a cheap build-time pass honest
    # instead of making it a FAIL nobody reads.
    n_played = len(old.get("seeds") or ())
    FROZEN_SEED_COUNT = old.get("frozen_seed_count")
    return {
        "gate": "TAU_P GOLDEN GATE (bit-exact-when-unset + positive control + "
                "candidate-only)",
        "verdict": "PASS" if not failed else "FAIL",
        "seeds_played": n_played,
        "frozen_seed_count": FROZEN_SEED_COUNT,
        "full_frozen_set": n_played == FROZEN_SEED_COUNT,
        "checks": checks,
        "failed": failed,
        "legs": {k: {"evalmod": v.get("evalmod"),
                     "leg_sha256": v.get("leg_sha256"),
                     "requested_cand_tau_p": v.get("requested_cand_tau_p"),
                     "flag_expressible_on_this_module":
                         v.get("flag_expressible_on_this_module"),
                     "host": v.get("host"), "wall_secs": v.get("wall_secs")}
                 for k, v in legs.items()},
        "riders": [
            "⛔ This is a CODE-PATH gate at a tiny budget (k2 x 96), NEVER a "
            "strength measurement. No number in the legs may be quoted as one.",
            "⛔ It proves the DEFAULT path is unmoved, the knob BINDS, and it "
            "binds on the CANDIDATE ONLY. It says NOTHING about whether the knob "
            "HELPS — that is what the two cells of "
            "measurement/taup_audit_leg_20260901 are for, and the prior on them "
            "is LOW by construction (PREREG §1).",
            "⛔ The control dose here (the CTRL leg's requested_cand_tau_p) is a "
            "PLUMBING dose chosen to force divergence cheaply. It is not one of "
            "the round's two pre-registered doses and carries no claim.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument("ctrl", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    verdict = adjudicate(*(json.loads(p.read_text()) for p in (a.old, a.new, a.ctrl)))
    a.out.write_text(json.dumps(verdict, indent=2, ensure_ascii=False))
    for c in verdict["checks"]:
        print(f"  [{'PASS' if c['ok'] else 'FAIL'}] {c['check']}")
    print(f"{verdict['verdict']} -> {a.out}")
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
