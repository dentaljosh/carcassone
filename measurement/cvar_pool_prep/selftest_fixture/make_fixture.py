#!/usr/bin/env python3
"""Build this round's selftest fixture FROM THE REAL EMITTER's output.

⛔⛔ THE FIXTURE TRAP, AND WHY THIS SCRIPT EXISTS. A hand-written manifest
fixture tests the gates against a document shape the author IMAGINED. This
program has realized that failure three times, most recently in the τ_p leg
(`DEVIATIONS.md` D-1), where **three of four obvious gate addresses were wrong
on the real emitter** — `config.champion.sims` does not exist (it is
`sims_per_det`), `config.exact_k` does not exist (it is `config.endgame.exact_k`),
`config.backend` is a DICT, and `rules_profile` is TOP-LEVEL. A gate at a wrong
address returns `MISSING` and, in a lib that failed OPEN, would pass vacuously.

⭐ **AND IT PAID FOR ITSELF AGAIN HERE.** The build-time dry cell (`REALCELL_DRY/`)
showed `config.opponent.champ_cfg.pool_mode` **ABSENT**: `champ_cfg` is the
FIVE-KNOB SHARED dict, not a resolved `as_manifest()`, so `G-POOL`'s opponent
address did not exist until `eval_fair_puct` was changed to state the opponent's
pooling rule POSITIVELY there — exactly the move `fpu_reduction: None` made in
that dict for `G-FPU`. That correction is `DEVIATIONS.md` D-2 and it was found by
running a real cell, not by reading the emitter's source.

So: `REALCELL_DRY/` holds the byte-untouched manifest + summary of a genuine
2-game k2×32 cell played on the laptop on THROWAWAY seeds, and every synthetic
case below is a MUTATION of that document — never a fresh dict. `SPECS.json`
records exactly which values were promoted and why.

    python make_fixture.py            # rebuild every synthetic case from REALCELL_DRY
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REAL = HERE / "REALCELL_DRY"

#: ⭐ THE SIX BUDGET NUMBERS PROMOTED from the dry cell's k2×32 to the round's
#: k16×1376. A fixture that genuinely ran the production budget would cost ~6 h;
#: these six values (and NOTHING else) are edited so `G-BUDGET` can pass on
#: `SMOKE_PASS`. Every key path, every other value and the whole document shape
#: are the emitter's own.
BUDGET_PROMOTIONS = {
    "config.champion.k_dets": 16,
    "config.champion.sims_per_det": 1376,
    "config.champion.total_sims": 22016,
    "config.opponent.k_dets": 16,
    "config.opponent.sims_per_det": 1376,
    "config.opponent.total_sims": 22016,
}


def _set(doc, dotted, value):
    cur = doc
    parts = dotted.split(".")
    for p in parts[:-1]:
        cur = cur[p]
    cur[parts[-1]] = value


def _del(doc, dotted):
    cur = doc
    parts = dotted.split(".")
    for p in parts[:-1]:
        cur = cur[p]
    cur.pop(parts[-1], None)


def _write(name, manifest=None, summary=None, records=1):
    d = HERE / name
    d.mkdir(parents=True, exist_ok=True)
    for stale in d.glob("*.json"):
        stale.unlink()
    if manifest is not None:
        (d / "manifest.json").write_text(json.dumps(manifest, indent=2,
                                                    ensure_ascii=False))
    if summary is not None:
        (d / "summary.json").write_text(json.dumps(summary, indent=2,
                                                   ensure_ascii=False))
    for i in range(records):
        (d / f"seed175999999{i:03d}_a0.json").write_text('{"stub": true}')
    return d


def main() -> int:
    base_m = json.loads((REAL / "manifest.json").read_text())
    base_s = json.loads((REAL / "summary.json").read_text())

    # --- the PASS case: the real document + the six budget promotions --------
    ok_m = copy.deepcopy(base_m)
    for addr, v in BUDGET_PROMOTIONS.items():
        _set(ok_m, addr, v)
    ok_s = copy.deepcopy(base_s)
    _write("SMOKE_PASS", ok_m, ok_s, records=8)

    # --- structural failures ------------------------------------------------
    _write("SMOKE_EMPTY_CELL", ok_m, ok_s, records=0)
    _write("SMOKE_NO_MANIFEST", None, ok_s, records=8)
    _write("SMOKE_NO_SUMMARY", ok_m, None, records=8)

    # --- G-POOL failures -----------------------------------------------------
    m = copy.deepcopy(ok_m); _del(m, "config.cand_search.pool_mode")
    _write("SMOKE_FAIL_pool_mode_absent", m, ok_s, 8)
    m = copy.deepcopy(ok_m); _set(m, "config.cand_search.pool_mode", "mean")
    _set(m, "config.cand_search.pool_alpha", None)
    _write("SMOKE_FAIL_pool_mode_mean", m, ok_s, 8)
    m = copy.deepcopy(ok_m); _set(m, "config.cand_search.pool_alpha", 0.5)
    _write("SMOKE_FAIL_pool_wrong_dose", m, ok_s, 8)
    m = copy.deepcopy(ok_m); _set(m, "config.champion.pool_mode", "mean")
    _write("SMOKE_FAIL_pool_candidate_unmoved", m, ok_s, 8)
    # ⭐⭐ THE LEAK — the proposition there is no shared flag for.
    m = copy.deepcopy(ok_m)
    _set(m, "config.opponent.champ_cfg.pool_mode", "cvar")
    _set(m, "config.opponent.champ_cfg.pool_alpha", 0.25)
    _write("SMOKE_FAIL_pool_leaked_to_opponent", m, ok_s, 8)
    m = copy.deepcopy(ok_m); _del(m, "config.opponent.champ_cfg.pool_mode")
    _write("SMOKE_FAIL_pool_opponent_absent", m, ok_s, 8)

    # --- G-SINGLEVAR failures -----------------------------------------------
    m = copy.deepcopy(ok_m); _set(m, "config.cand_search.fpu_reduction", 0.2)
    _write("SMOKE_FAIL_singlevar_fpu_live", m, ok_s, 8)
    m = copy.deepcopy(ok_m); _set(m, "config.cand_search.c_puct", 1.0)
    _write("SMOKE_FAIL_singlevar_cpuct_live", m, ok_s, 8)
    m = copy.deepcopy(ok_m); _del(m, "config.cand_search.tau_p")
    _write("SMOKE_FAIL_singlevar_taup_absent", m, ok_s, 8)

    # --- G-BUDGET / G-ARB failures ------------------------------------------
    m = copy.deepcopy(ok_m); _set(m, "config.champion.k_dets", 8)
    _write("SMOKE_FAIL_budget_stale", m, ok_s, 8)
    m = copy.deepcopy(ok_m); _set(m, "rules_profile", {"name": "walled"})
    _write("SMOKE_FAIL_rules_walled", m, ok_s, 8)
    m = copy.deepcopy(ok_m); _del(m, "config.opp_tiearb")
    _write("SMOKE_FAIL_arb_opponent_absent", m, ok_s, 8)
    m = copy.deepcopy(ok_m); _set(m, "config.cand_tiearb.B", 16)
    _write("SMOKE_FAIL_arb_wrong_B", m, ok_s, 8)
    m = copy.deepcopy(ok_m); _set(m, "config.cand_tiearb.enabled", False)
    _write("SMOKE_FAIL_arb_candidate_disabled", m, ok_s, 8)
    m = copy.deepcopy(ok_m); _set(m, "config.paired", False)
    _write("SMOKE_FAIL_unpaired", m, ok_s, 8)

    # --- ⭐⭐ G-REACH failures — the gates this round has and its three -------
    #     predecessors did not. Every one of these documents has a PERFECT
    #     config and would pass every manifest gate above.
    s = copy.deepcopy(ok_s); _set(s, "pool.candidate.pickchanges", 0)
    _set(s, "pool.candidate.reach_in_play", 0.0)
    _write("SMOKE_FAIL_reach_zero_pickchanges", ok_m, s, 8)
    s = copy.deepcopy(ok_s); _set(s, "pool.candidate.cvar_plies", 0)
    _set(s, "pool.candidate.pickchanges", 0)
    _set(s, "pool.candidate.reach_in_play", 0.0)
    _write("SMOKE_FAIL_reach_rule_never_ran", ok_m, s, 8)
    s = copy.deepcopy(ok_s); _set(s, "pool.opponent.cvar_plies", 91)
    _set(s, "pool.opponent.mode", "cvar")
    _write("SMOKE_FAIL_reach_opponent_leak", ok_m, s, 8)
    s = copy.deepcopy(ok_s); _set(s, "pool.candidate.modes_disagree", True)
    _set(s, "pool.candidate.mode", "MIXED")
    _set(s, "pool.candidate.modes_observed", ["cvar", "mean"])
    _write("SMOKE_FAIL_reach_mixed_rev", ok_m, s, 8)
    s = copy.deepcopy(ok_s); _del(s, "pool")
    _write("SMOKE_FAIL_reach_block_absent", ok_m, s, 8)
    s = copy.deepcopy(ok_s)
    _set(s, "pool.candidate.pickchanges", 1)
    _set(s, "pool.candidate.reach_in_play", 1.0 / 128.0)
    _write("SMOKE_FAIL_reach_below_floor", ok_m, s, 8)

    specs = {
        "built_from": "REALCELL_DRY/ — a genuine 2-game k2x32 cell played on the "
                      "laptop on THROWAWAY seeds 175999999000..1 "
                      "(DEVIATIONS.md D-1). Byte-untouched.",
        "budget_promotions": BUDGET_PROMOTIONS,
        "why_promoted": "A fixture that genuinely ran k16x1376 would cost ~6 h. "
                        "These six values and NOTHING ELSE are edited so "
                        "G-BUDGET can pass on SMOKE_PASS; every key path, every "
                        "other value and the whole document shape are the "
                        "emitter's own.",
        "d2_correction": "The dry cell showed config.opponent.champ_cfg.pool_mode "
                         "ABSENT — champ_cfg is the FIVE-KNOB SHARED dict, not a "
                         "resolved as_manifest(). eval_fair_puct now states the "
                         "opponent's pooling rule POSITIVELY there (the same move "
                         "fpu_reduction: None made for G-FPU), and REALCELL_DRY "
                         "is the RE-RUN that carries the correction.",
        "cases": sorted(p.name for p in HERE.iterdir()
                        if p.is_dir() and p.name != "__pycache__"),
    }
    (HERE / "SPECS.json").write_text(json.dumps(specs, indent=2,
                                                ensure_ascii=False))
    print(f"wrote {len(specs['cases'])} fixture dirs + SPECS.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
