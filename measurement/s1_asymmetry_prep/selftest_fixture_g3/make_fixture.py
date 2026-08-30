#!/usr/bin/env python3
"""Regenerate `selftest_fixture_g3/` — a SHAPED, HEALTHY three-arm round.

⛔⛔ **THE FIXTURE ENCODES THE EMITTER'S REAL OUTPUT SHAPE, NOT THE GATE'S
EXPECTATION.** That is `PG-A1` (measurement/phasegate_prep/AMENDMENTS.md): a
frozen adjudicator voided a healthy round because `G-LEAF` compared a stringified
curve against a label, and no healthy archive could ever have passed it. A
fixture written from the read-rule would have passed that gate too. So every key
below is traced to the line of `scripts/classical_search/eval_fair_puct.py` that
writes it:

  * `config.champion.*`            <- `HeuristicPriorConfig.as_manifest()` plus the
                                      budget block (4586-4592). ⚠️ It does NOT
                                      carry `fpu_reduction`.
  * `config.opponent.champ_cfg.*`  <- the FIVE-key `champ_cfg_dict` (2950-2961),
                                      which DOES carry `fpu_reduction: null`.
  * `config.opponent.{k_dets,sims_per_det,total_sims}` (4695-4700) — the
    opponent's budget is one level UP, not inside `champ_cfg`.
  * `config.cand_jrules_prior`     <- 4778, the resolved `{dose, mask, scope}`.
  * `config.cand_tiearb`           <- 4791, plus the top-level copy at 5113.
  * `config.{band_seed_start,n_decks,seatings_per_deck}` <- 4756-4758.
  * summary keys                   <- the REAL `summary.json` of
    `measurement/h2h_22016_20260824/h2h_k16x1376_vs_champ_k8x1376/`.
  * per-game records               <- the REAL `seed*_a*.json` of the same run
    (`seed`, `a_seat`, `diff`, `won_by_champ`, `drew`, ...).
  * ⭐ `jr_expansions`             <- the R7 witness build's FINAL contract
    (2026-08-30), at BOTH emitted addresses, with the UNARMED opponent reading
    ALL ZEROS — the counters live inside the `dose != 0` branch.

⚠️ The fixture differs from the round in SCALE ONLY (30/30/20 decks instead of
600/600/400). `analyze_g3.selftest` asserts that: role and scope must match the
frozen arms exactly.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
REV = "a" * 40
BLIND = "b" * 40
LEAF = "a36d2e15a3b3d71d"
BAND = 161_000_000_000

#: SHAPED so the healthy round reads `S1-FIRES` (P1 clears POSITIVE) and, with
#: the G2 census unavailable, `S1-MARGIN-ONLY`. ⛔ Fixture numbers are not
#: hypotheses about the real cell — they exist to make every branch and every
#: gate observable.
ARMS = [
    # name, role, scope, n_decks, true per-deck mean
    ("CELL_G3_OPP", "local", "opp", 30, +2.6),
    ("CELL_G3_OWN", "laptop", "own", 30, -1.4),
    ("CELL_G3_ALL", "local", "all", 20, +0.2),
]

CHAMP_CFG = {
    "c_puct": 1.5, "tau_p": 5.0, "leaf_quantize": "float",
    "final_select": "visits", "value_norm": "tanh",
}


def _expansions(scope: str, n_games: int) -> dict:
    """The R7 census, at the ARMED candidate's realistic proportions.

    `own_mover` is ~half of `total` (the two players alternate), and `boosted`
    is the in-scope subset minus the terminal / no-legal-child expansions that
    legitimately boost nothing — which is exactly why `G-WITNESS`'s coverage
    check is ADVISORY and its `boosted <= denominator` check is HARD."""
    total = 220_000 * n_games
    own = total // 2
    den = {"own": own, "opp": total - own, "all": total}[scope]
    return {"total": total, "own_mover": own, "boosted": int(den * 0.93)}


UNARMED = {"total": 0, "own_mover": 0, "boosted": 0}
"""⚠️ THE UNARMED SIDE READS ALL ZEROS — the R7 counters sit inside the
`dose != 0` branch. `{T, M, 0}` with `T > 0` is NOT what a healthy opponent
emits, and a gate asserting `opponent.total > 0` would fail every real cell."""


def manifest(name, role, scope, n_decks) -> dict:
    host = "laptop-wsl" if role == "laptop" else "Doctor"
    return {
        "kind": "eval_fair_puct", "game": "carcassonne-base-farmers",
        "host": host, "code_rev": REV,
        "rust_toolchain": "1.83.0-x86_64-unknown-linux-gnu",
        "carc_rs_build": "c0ffee1234567890", "carc_rs_binary_sha": "deadbeef01",
        "carc_rs_version": "0.1.0", "mixed_builds": False,
        "rules_profile": {"name": "fixed_v1", "r9_env_ok": True,
                          "r9_env_observed": True},
        "cand_tiearb": None,
        "stamps": {"BLIND_COMMIT": BLIND},
        "config": {
            "info": "fair",
            "champion": {
                "agent": "FairHeuristicPriorAgent", **CHAMP_CFG,
                "c_lcb": 0.0, "reuse_tree": False, "root_select": "puct",
                "jrules_prior_dose": 0.25, "jrules_prior_mask": 31,
                "jrules_prior_scope": scope,
                "jrules_filter_mask": 0, "jrules_filter_min_keep": 1,
                "k_dets": 16, "sims_per_det": 1376, "total_sims": 22016,
                "leaf": "FROZEN v2.9 curve125 production champion leaf",
            },
            "endgame": {"mode": "marginalized", "exact_k": 2,
                        "exact_budget": 200_000, "shared_by_both_arms": True},
            "opponent_mode": "fair-champion",
            "opponent": {
                "mode": "fair-champion", "agent": "FairHeuristicPriorAgent",
                "champ_cfg": {**CHAMP_CFG, "fpu_reduction": None},
                "k_dets": 16, "sims_per_det": 1376, "total_sims": 22016,
                "endgame": {"mode": "marginalized", "exact_k": 2},
                "leaf_hash": LEAF,
            },
            "backend": {"name": "rust", "requested": "rust",
                        "mixed_builds": False,
                        "converted_sides": ["candidate", "opponent"]},
            "band_seed_start": BAND, "n_decks": n_decks,
            "seatings_per_deck": 2,
            "cand_leaf_hash": LEAF, "opp_leaf_hash": LEAF,
            "cand_leaf_json": None,
            "cand_jrules_prior": {"dose": 0.25, "mask": 31, "scope": scope},
            "cand_jrules_filter": None,
            "cand_tiearb": None,
            "code_rev": REV,
            "stamps": {"BLIND_COMMIT": BLIND},
        },
    }


def build_arm(name, role, scope, n_decks, mean, rng) -> None:
    out = HERE / name
    out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("*.json"):
        p.unlink()
    (out / "manifest.json").write_text(
        json.dumps(manifest(name, role, scope, n_decks), indent=1))

    recs, diffs = [], []
    for i in range(n_decks):
        seed = BAND + i
        # per-deck effect + a seat-antisymmetric nuisance, so the seat average
        # recovers the effect exactly as the real deck-pairing does
        eff = mean + rng.gauss(0.0, 3.0)
        nuis = rng.gauss(0.0, 9.0)
        for a_seat in (0, 1):
            d = eff + (nuis if a_seat == 0 else -nuis)
            recs.append({
                "seed": seed, "a_seat": a_seat, "info": "fair", "exact_k": 2,
                "k_dets": 16, "sims": 1376,
                "score_p0": 100, "score_p1": 100, "diff": round(d, 4),
                "won_by_champ": bool(d > 0), "drew": bool(d == 0),
                "elapsed_s": 520.0, "moves": 142,
                "deck_hash": f"{seed:016x}",
                "champ_prefix_moves": 70, "champ_exact_moves": 2,
                "champ_prefix_secs": 268.0, "champ_solver_secs": 0.01,
                "champ_timeouts": 0,
                "rung_moves": 70, "rung_secs": 250.0,
                "opponent": "fair-champion",
                "opp_prefix_moves": 70, "opp_exact_moves": 2,
                "opp_prefix_secs": 248.0, "opp_solver_secs": 1.9,
                "opp_timeouts": 0,
                "cand_jf": None, "cand_tiearb": None,
                "cand_jr_expansions": _expansions(scope, 1),
                "opp_jr_expansions": dict(UNARMED),
                "wc_tiebreak": False, "wc_tie_resolved": False,
            })
        diffs.append(eff)
    for r in recs:
        (out / f"seed{r['seed']}_a{r['a_seat']}.json").write_text(
            json.dumps(r, indent=1))

    n_games = 2 * n_decks
    per_deck = [(recs[2 * i]["diff"] + recs[2 * i + 1]["diff"]) / 2.0
                for i in range(n_decks)]
    m = math.fsum(per_deck) / n_decks
    var = math.fsum((x - m) ** 2 for x in per_deck) / (n_decks - 1)
    se = math.sqrt(var / n_decks)
    w = sum(1 for r in recs if r["won_by_champ"])
    d0 = sum(1 for r in recs if r["drew"])
    wr = (w + 0.5 * d0) / n_games
    summ = {
        "info": "fair", "exact_k": 2, "k_dets": 16, "sims": 1376,
        "total_sims": 22016, "asymmetric_budgets": False,
        "candidate_k_dets": 16, "candidate_sims": 1376,
        "candidate_total_sims": 22016,
        "opp_k_dets": 16, "opp_sims": 1376, "opp_total_sims": 22016,
        "n_failed": 0, "failure_rate": 0.0, "failed_cells": [],
        "opponent": "fair-champion",
        "opponent_label": "FAIR PRODUCTION CHAMPION (k16x1376)",
        "n": n_games, "W": w, "D": d0, "L": n_games - w - d0,
        "winrate": wr,
        "elo": 400.0 * math.log10(wr / (1 - wr)),
        "avg_diff": math.fsum(r["diff"] for r in recs) / n_games,
        "paired_mean_margin": m, "paired_z": m / se, "n_paired": n_decks,
        # ⚠️ THE FIELD-NAME TRAP: the CANDIDATE side is `champ_prefix_ms_per_move`
        # and the OPPONENT side is `rung_ms_per_move` (memory:
        # feedback_verify_numbers_before_reporting). 1.079 is SIZING §3's
        # prediction for `opp`, comfortably under the 1.20 N4 trigger.
        "champ_prefix_ms_per_move": 3828.0,
        "rung_ms_per_move": 3547.0,
        "champ_latched_games": n_games, "solver_secs_per_game": 1.9,
        "champ_timeouts": 0, "wc_tiebreak": False, "wc_tie_resolved_games": 0,
        # ⭐ THE R7 WITNESS, AT BOTH EMITTED ADDRESSES.
        "jr_expansions": {"candidate": _expansions(scope, n_games),
                          "opponent": dict(UNARMED)},
        "cand_jr_expansions": _expansions(scope, n_games),
        "opp_jr_expansions": dict(UNARMED),
    }
    (out / "summary.json").write_text(json.dumps(summ, indent=1))


def main() -> None:
    rng = random.Random(20260830)
    specs = []
    for name, role, scope, n_decks, mean in ARMS:
        build_arm(name, role, scope, n_decks, mean, rng)
        specs.append({"name": name, "role": role, "scope": scope,
                      "seed_start": BAND, "n_decks": n_decks,
                      "purpose": "fixture arm — SCALE differs from the round, "
                                 "role and scope do NOT"})
    (HERE / "SPECS.json").write_text(json.dumps(specs, indent=1))
    (HERE / "PINNED_SRC_REV").write_text(REV + "\n")
    print(f"wrote {len(specs)} fixture arms under {HERE}")


if __name__ == "__main__":
    main()
