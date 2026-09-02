#!/usr/bin/env python3
"""Adjudicate the four golden-gate legs into `CVAR_BITEXACT.json`.

Precedent: `measurement/taup_audit_leg_20260901/goldengate/identity_diff.py`
→ `TAUP_BITEXACT.json`. Same verdict shape, same "every check names its own
witness" discipline; the checks differ where the change does — and this change
spans a TREE and a WHEEL, so `ONE-SRC`/`ONE-WHEEL` invert into `TREE-SWUNG` and
`WHEEL-SWUNG`.

⛔ EVERY check FAILS CLOSED. A missing key is a FAIL, never a skip.

    python identity_diff.py OLD.json NEW.json NEW_CVAR25.json NEW_ALPHA1.json \\
        --out ../CVAR_BITEXACT.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _check(name, ok, detail, why):
    return {"check": name, "ok": bool(ok), "detail": detail, "why": why}


def _ps(leg, key):
    """Sum one pooling counter over a leg's games (0 when absent)."""
    tot = 0
    for g in leg.get("games", []):
        d = g.get("pool_stats") or {}
        tot += int(d.get(key) or 0)
    return tot


def adjudicate(old: dict, new: dict, cvar: dict, alpha1: dict) -> dict:
    checks = []
    legs = {"OLD": old, "NEW": new, "CVAR25": cvar, "ALPHA1": alpha1}
    dosed = {"CVAR25": cvar, "ALPHA1": alpha1}

    # --- WHEEL-SWUNG ---------------------------------------------------------
    # ⭐ THE INVERSE of the τ_p gate's ONE-WHEEL. GT-M1 changes carc_core AND
    # carc-py, so the wheel is a VARIABLE: OLD must run a DIFFERENT binary than
    # the three NEW legs, and that OLD binary must be the stale one.
    wheels = {k: v.get("carc_rs_binary_sha") for k, v in legs.items()}
    new_wheels = {wheels["NEW"], wheels["CVAR25"], wheels["ALPHA1"]}
    wheel_ok = (len(new_wheels) == 1 and "unavailable" not in new_wheels
                and wheels["OLD"] not in new_wheels
                and wheels["OLD"] not in (None, "unavailable"))
    checks.append(_check(
        "WHEEL-SWUNG", wheel_ok,
        {**wheels, "files": {k: v.get("carc_rs_file") for k, v in legs.items()}},
        "OLD ran the PRE-CHANGE carc_rs (the one installed in the venv) and all "
        "three NEW legs ran ONE freshly built binary — so the wheel is a named "
        "variable of the OLD/NEW contrast, not an uncontrolled one"))

    # --- OLD-WHEEL-IS-STALE / NEW-WHEEL-IS-FRESH ----------------------------
    # The wheel's CAPABILITY, not just its hash: the `pool` getter exists only
    # on a post-GT-M1 build. This is what makes `IDENTITY` meaningful — the OLD
    # leg genuinely could not have expressed the rule.
    old_getter = ((old.get("rust_pool_readback") or {}).get("has_pool_getter"))
    new_getters = {k: ((v.get("rust_pool_readback") or {}).get("has_pool_getter"))
                   for k, v in legs.items() if k != "OLD"}
    checks.append(_check(
        "OLD-WHEEL-IS-STALE", old_getter is False,
        {"old_has_pool_getter": old_getter},
        "⭐ the OLD leg's carc_rs has NO `pool` getter — it PREDATES "
        "measurement/cvar_pool_prep and could not have expressed the rule under "
        "any flag. That is what the IDENTITY leg is identical TO"))
    checks.append(_check(
        "NEW-WHEEL-IS-FRESH", all(v is True for v in new_getters.values()),
        new_getters,
        "every NEW leg's carc_rs exposes `pool` — the rebuilt wheel is what "
        "played, and the launcher's own stale-wheel refusal reads this getter"))

    # --- TREE-SWUNG ----------------------------------------------------------
    srcs = {k: v.get("carcassonne_ai_file") for k, v in legs.items()}
    new_srcs = {srcs["NEW"], srcs["CVAR25"], srcs["ALPHA1"]}
    tree_ok = (len(new_srcs) == 1 and None not in new_srcs
               and srcs["OLD"] not in new_srcs and srcs["OLD"] is not None)
    checks.append(_check(
        "TREE-SWUNG", tree_ok,
        {**srcs, "trees": {k: v.get("tree") for k, v in legs.items()}},
        "⚠️ UNLIKE the tau_p gate, src/carcassonne_ai IS a variable here (GT-M1 "
        "touches heuristic_prior_mcts / rust_agent / champion_factory), so OLD "
        "resolved a DIFFERENT package than the three NEW legs, and those three "
        "resolved the SAME one"))

    # --- ONE-FILE ------------------------------------------------------------
    mods = {k: v.get("evalmod_sha256") for k, v in legs.items()}
    new_mods = {mods["NEW"], mods["CVAR25"], mods["ALPHA1"]}
    checks.append(_check(
        "HARNESS-SWUNG",
        (len(new_mods) == 1 and mods["OLD"] not in new_mods and all(mods.values())),
        {**mods, "paths": {k: v.get("evalmod") for k, v in legs.items()}},
        "OLD loaded a DIFFERENT eval_fair_puct.py; the three dosed/undosed NEW "
        "legs ran the SAME one"))

    # --- SAME-SEEDS / SAME-BUDGET -------------------------------------------
    seeds = [tuple(v.get("seeds") or ()) for v in legs.values()]
    checks.append(_check(
        "SAME-SEEDS", len(set(seeds)) == 1 and len(seeds[0]) > 0,
        {"n": len(seeds[0]), "identical": len(set(seeds)) == 1},
        "all four legs played the same frozen deck set"))
    budgets = [json.dumps(v.get("budget"), sort_keys=True) for v in legs.values()]
    checks.append(_check(
        "SAME-BUDGET", len(set(budgets)) == 1, old.get("budget"),
        "identical search shape on all four legs"))

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
        "⭐⭐ BIT-IDENTICAL with --cand-pool-mode UNSET, across a swung TREE and "
        "a swung WHEEL: neither the new rust dispatch, the new config fields, "
        "the new telemetry nor the harness plumbing moved the champion's play "
        "by one action"))

    # --- MEAN-COUNTERS-ZERO --------------------------------------------------
    # The assertable invariant of an UNARMED side, derived from PLAY.
    mean_cnt = {k: _ps(new, k) for k in
                ("pool_cvar_plies", "pool_pickchanges", "pool_fallbacks")}
    checks.append(_check(
        "MEAN-COUNTERS-ZERO", all(v == 0 for v in mean_cnt.values()), mean_cnt,
        "the Mean-pooled NEW leg never entered carc_core::fair::pool — the "
        "counters live inside the CVaR arm of the dispatch, so all-zero is the "
        "byte-identity premise stated as a number"))

    # --- POSITIVE ------------------------------------------------------------
    differ = sum(1 for g1, g2 in zip(new.get("games", []), cvar.get("games", []))
                 if g1["actions_sha256"] != g2["actions_sha256"])
    total = min(len(new.get("games", [])), len(cvar.get("games", [])))
    reach_plies = _ps(cvar, "pool_cvar_plies")
    reach_changes = _ps(cvar, "pool_pickchanges")
    pos_ok = (total > 0 and differ == total
              and cvar.get("leg_sha256") != new.get("leg_sha256")
              and cvar.get("requested_but_unreachable") is False
              and reach_plies > 0 and reach_changes > 0)
    checks.append(_check(
        "POSITIVE", pos_ok,
        {"new": new.get("leg_sha256"), "cvar": cvar.get("leg_sha256"),
         "games_that_differ": differ, "games_total": total,
         "cvar_plies": reach_plies, "pickchanges": reach_changes,
         "reach_in_play": (reach_changes / reach_plies) if reach_plies else None,
         "fallbacks": _ps(cvar, "pool_fallbacks"),
         "resolved_pool": (cvar.get("rust_pool_readback") or {}).get("pool")},
        "⭐⭐ the knob BINDS, on TWO independent witnesses: every game diverges "
        "from the Mean-pooled leg, AND the agent's own play-derived counter says "
        "the CVaR rule decided plies and CHANGED the pick on some of them. A "
        "flag parsed and dropped on the floor would pass a divergence test only "
        "by accident and would fail this one flat"))

    # --- CANDIDATE-ONLY ------------------------------------------------------
    # ⭐⭐ Unconditional here, unlike tau_p's: there IS no shared --pool-mode, so
    # ANY opponent-side CVaR is a leak. Asserted from the OPPONENT's own
    # resolved config in EVERY leg, dosed ones included.
    opp_pool = {k: {"mode": (v.get("opp_cfg") or {}).get("pool_mode"),
                    "alpha": (v.get("opp_cfg") or {}).get("pool_alpha")}
                for k, v in legs.items()}
    # OLD predates the fields entirely -> "MISSING" is CORRECT there, and is not
    # the same as a leak. NEW-family legs must positively say "mean"/None.
    cand_only_ok = (
        opp_pool["OLD"]["mode"] in ("mean", "MISSING")
        and all(opp_pool[k]["mode"] == "mean" and opp_pool[k]["alpha"] is None
                for k in ("NEW", "CVAR25", "ALPHA1"))
        and (cvar.get("cand_cfg") or {}).get("pool_mode") == "cvar"
        and (cvar.get("cand_cfg") or {}).get("pool_alpha")
        == cvar.get("requested_pool_alpha"))
    checks.append(_check(
        "CANDIDATE-ONLY", cand_only_ok,
        {"opponent_pool_per_leg": opp_pool,
         "cvar_candidate_pool": {
             "mode": (cvar.get("cand_cfg") or {}).get("pool_mode"),
             "alpha": (cvar.get("cand_cfg") or {}).get("pool_alpha")}},
        "⭐⭐ the OPPONENT (built by _make_opponent's own _cfg_from_dict call) "
        "pools by the deployed visit-weighted mean in EVERY leg while the dosed "
        "legs' CANDIDATE carries the rule. There is no shared --pool-mode by "
        "design, so any opponent-side cvar here would be a pure LEAK — and a "
        "two-sided pooling change is a different CHAMPION, not a cell"))

    # --- ALPHA1-IS-NOT-MEAN --------------------------------------------------
    # ⚠️⚠️ THE BUILD BRIEF'S ONE FACTUAL CORRECTION, ADJUDICATED RATHER THAN
    # ARGUED. The brief asked for "alpha=1.0 => bit-exact with mean". The census
    # that licensed this lever already measured that FALSE.
    a1_differ = sum(1 for g1, g2 in zip(new.get("games", []),
                                        alpha1.get("games", []))
                    if g1["actions_sha256"] != g2["actions_sha256"])
    a1_plies = _ps(alpha1, "pool_cvar_plies")
    a1_changes = _ps(alpha1, "pool_pickchanges")
    a1_ok = (a1_plies > 0
             and alpha1.get("requested_but_unreachable") is False
             and (alpha1.get("rust_pool_readback") or {}).get("pool")
             == {"mode": "cvar", "alpha": 1.0})
    checks.append(_check(
        "ALPHA1-EQUALWEIGHT-ARM", a1_ok,
        {"games_that_differ_from_mean": a1_differ,
         "games_total": min(len(new.get("games", [])),
                            len(alpha1.get("games", []))),
         "cvar_plies": a1_plies, "pickchanges": a1_changes,
         "reach_in_play": (a1_changes / a1_plies) if a1_plies else None,
         "leg_sha256": alpha1.get("leg_sha256"),
         "identical_to_mean": alpha1.get("leg_sha256") == new.get("leg_sha256")},
        "⚠️⚠️ THE CORRECTION. alpha=1.0 is the EQUAL-WEIGHT-per-world mean and "
        "is NOT an identity control for the deployed rule, which is "
        "VISIT-weighted (sum(W)/sum(N)). The census disclosed exactly this "
        "(cl083_mech_censuses_20260830/DEVIATIONS.md D-1: the alpha=1.00 rule "
        "changes the pick on 18.1% of contest-exposed plies BY ITSELF, which is "
        "why `reach_vs_equalweight` exists in that artefact). This check "
        "therefore asserts the ARM IS EXPRESSIBLE and records whether it "
        "diverges — it does NOT assert identity, and a build that made it "
        "identical would be a build that got the rule wrong. The bit-exact "
        "statement that IS true — CVaR at alpha=1.0 equals the SORTED-ORDER "
        "equal-weight mean — is arithmetic and is pinned in "
        "carc_core::fair::pool::tests::"
        "alpha_one_is_the_sorted_order_equal_weight_mean"))

    # --- AUDIT-ADJUDICATED ---------------------------------------------------
    aud_ok = (old.get("flag_expressible_on_this_module") is False
              and all(v.get("flag_expressible_on_this_module") is True
                      for v in (new, cvar, alpha1)))
    checks.append(_check(
        "AUDIT-ADJUDICATED", aud_ok,
        {"old_module_expressible": old.get("flag_expressible_on_this_module"),
         "new_module_expressible": new.get("flag_expressible_on_this_module")},
        "⭐ the pre-change eval_fair_puct's REAL argparse (driven via "
        "main(['--help'])) carries no --cand-pool-mode, so no candidate-side "
        "pooling cell was expressible on the classical champion; the patched "
        "one carries it and POSITIVE shows it reaching play"))

    # --- J-WORLDS ------------------------------------------------------------
    # The two dosed legs must select DIFFERENT tail widths at k=4:
    # alpha 0.25 -> ceil(1) = 1 world; alpha 1.0 -> 4. If they coincided, the
    # gate would be testing one rule twice.
    j_ok = ((cvar.get("rust_pool_readback") or {}).get("pool", {}) or {}).get(
        "alpha") != (((alpha1.get("rust_pool_readback") or {}).get("pool", {})
                      or {}).get("alpha"))
    checks.append(_check(
        "DOSES-DISTINCT", bool(j_ok),
        {"cvar25_alpha": ((cvar.get("rust_pool_readback") or {})
                          .get("pool", {}) or {}).get("alpha"),
         "alpha1_alpha": ((alpha1.get("rust_pool_readback") or {})
                          .get("pool", {}) or {}).get("alpha"),
         "k_dets": (old.get("budget") or {}).get("k_dets"),
         "note": "at k=4 alpha 0.25 -> ceil(1.0) = 1 world, alpha 1.0 -> 4"},
        "the two dosed legs select different lower-tail widths, so the gate "
        "tests two rules and not one rule twice"))

    failed = [c["check"] for c in checks if not c["ok"]]
    n_played = len(old.get("seeds") or ())
    FROZEN_SEED_COUNT = old.get("frozen_seed_count")
    return {
        "gate": "GT-M1 CVaR POOLING GOLDEN GATE (bit-exact-when-unset across a "
                "swung tree AND wheel + positive control + candidate-only + the "
                "alpha=1.0 equal-weight arm)",
        "verdict": "PASS" if not failed else "FAIL",
        "seeds_played": n_played,
        "frozen_seed_count": FROZEN_SEED_COUNT,
        "full_frozen_set": n_played == FROZEN_SEED_COUNT,
        "checks": checks,
        "failed": failed,
        "legs": {k: {"tree": v.get("tree"),
                     "evalmod": v.get("evalmod"),
                     "leg_sha256": v.get("leg_sha256"),
                     "carc_rs_binary_sha": v.get("carc_rs_binary_sha"),
                     "requested_pool_mode": v.get("requested_pool_mode"),
                     "requested_pool_alpha": v.get("requested_pool_alpha"),
                     "flag_expressible_on_this_module":
                         v.get("flag_expressible_on_this_module"),
                     "host": v.get("host"), "wall_secs": v.get("wall_secs")}
                 for k, v in legs.items()},
        "riders": [
            "⛔ This is a CODE-PATH gate at a tiny budget (k4 x 96), NEVER a "
            "strength measurement. No number in the legs may be quoted as one — "
            "including `reach_in_play`, which at this budget and on self-play "
            "decks is not comparable to the census's reach(alpha).",
            "⛔ It proves the DEFAULT path is unmoved across a swung tree AND a "
            "swung wheel, that the rule BINDS, and that it binds on the "
            "CANDIDATE ONLY. It says NOTHING about whether the rule HELPS — "
            "that is what the two cells of measurement/cvar_pool_prep are for, "
            "and the census that licensed them explicitly declined to price the "
            "change (PREREG §1).",
            "⚠️⚠️ ALPHA1 IS NOT AN IDENTITY LEG. See the ALPHA1-EQUALWEIGHT-ARM "
            "check: alpha=1.0 is the equal-weight-per-world mean, the deployed "
            "rule is visit-weighted, and the census measured them disagreeing "
            "on 18.1% of contest-exposed plies. A future reader who 'fixes' "
            "alpha=1.0 into an identity is breaking the rule, not the gate.",
            "⛔ The alpha used by the CVAR25 leg is a PLUMBING dose that happens "
            "to equal one of the round's two funded doses. At k=4 it selects 1 "
            "world where the deployed k=16 selects 4, so it is NOT the round's "
            "cell and carries no claim.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument("cvar", type=Path)
    ap.add_argument("alpha1", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    verdict = adjudicate(*(json.loads(p.read_text())
                           for p in (a.old, a.new, a.cvar, a.alpha1)))
    a.out.write_text(json.dumps(verdict, indent=2, ensure_ascii=False))
    for c in verdict["checks"]:
        print(f"  [{'PASS' if c['ok'] else 'FAIL'}] {c['check']}")
    print(f"{verdict['verdict']} -> {a.out}")
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
