#!/usr/bin/env python3
"""Build this leg's selftest fixture FROM A REAL EMITTED CELL.

⚠️⚠️ **THE FIXTURE TRAP (three realized incidents).** A hand-encoded fixture
tests the fixture author's belief about the emitter, not the emitter. Every
document under `selftest_fixture/` therefore descends from ONE real
`manifest.json` written by `eval_fair_puct.py` itself — the build-time dry cell
(`DEVIATIONS.md` D-1), a genuine `--cand-tau-p 3.0` head-to-head at a tiny budget
on throwaway seeds. Nothing here was typed from the emitter's source.

WHAT EACH SUBDIR IS
    REAL_DRY/     the emitted manifest, BYTE-UNTOUCHED. `test_taup_leg.py` uses
                  it for the ADDRESS-VALIDITY claim: every address `leg_lib`'s
                  gates dig for must EXIST in output the emitter really wrote.
                  ⛔ It does NOT pass G-BUDGET (the dry cell ran k2x32, not the
                  frozen k16x1376) and it is asserted to fail exactly there.
    PASS/         REAL_DRY with the SIX budget numbers promoted to the frozen
                  production shape — the ONLY edit, listed in `PROMOTED` below
                  and recorded in SPECS.json. Nothing else is touched. A
                  fixture that really ran k16x1376 would cost ~6 hours to make.
    FAIL_*/       PASS with exactly ONE thing broken, each aimed at one gate.
                  ⛔ These are what prove the gates FIRE; a fixture with only a
                  passing case proves a gate that always returns [] is correct.
    EMPTY_CELL/   a manifest and ZERO per-game records (the R1 defect class).
    NO_MANIFEST/  a cell dir with no manifest at all.

USAGE
    python make_fixture.py --from <dir containing the real manifest.json>
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import leg_lib as L  # noqa: E402

#: The ONLY edit made to the real manifest, and why. Six numbers.
PROMOTED = {
    "config.champion.k_dets": L.K_DETS,
    "config.champion.sims_per_det": L.SIMS_PER_DET,
    "config.champion.total_sims": L.TOTAL_SIMS,
    "config.opponent.k_dets": L.K_DETS,
    "config.opponent.sims_per_det": L.SIMS_PER_DET,
    "config.opponent.total_sims": L.TOTAL_SIMS,
}

#: One mutation per gate branch. `None` as a value means DELETE the key — the
#: MISSING-is-not-None distinction every gate in `leg_lib` turns on.
_DELETE = object()
MUTATIONS = {
    "FAIL_taup_absent": {"config.cand_search.tau_p": _DELETE},
    "FAIL_taup_null": {"config.cand_search.tau_p": None},
    "FAIL_taup_wrong_dose": {"config.cand_search.tau_p": 4.0},
    "FAIL_taup_candidate_unmoved": {"config.champion.tau_p": 5.0},
    "FAIL_taup_leaked_to_opponent": {"config.opponent.champ_cfg.tau_p": 3.0},
    "FAIL_shared_taup_absent": {"config.cand_search.shared_tau_p": _DELETE},
    "FAIL_singlevar_fpu_live": {"config.cand_search.fpu_reduction": 0.2},
    "FAIL_singlevar_cpuct_live": {"config.cand_search.c_puct": 1.0},
    "FAIL_singlevar_cpuct_absent": {"config.cand_search.c_puct": _DELETE},
    "FAIL_arb_opponent_absent": {"config.opp_tiearb": _DELETE},
    "FAIL_arb_candidate_disabled": {"config.cand_tiearb.enabled": False},
    "FAIL_arb_wrong_B": {"config.cand_tiearb.B": 32},
    "FAIL_arb_gated": {"config.opp_tiearb.phase_gate": "late"},
    "FAIL_budget_stale": {"config.champion.sims_per_det": 688},
    "FAIL_rules_walled": {"rules_profile.name": "walled"},
    "FAIL_unpaired": {"config.paired": False},
}


def _set(doc, dotted, value):
    cur = doc
    parts = dotted.split(".")
    for p in parts[:-1]:
        cur = cur[p]
    if value is _DELETE:
        cur.pop(parts[-1], None)
    else:
        cur[parts[-1]] = value


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", type=Path, required=True,
                    help="a REAL emitted cell dir (must contain manifest.json "
                         "and at least one per-game record)")
    a = ap.parse_args()

    src_man = a.src / "manifest.json"
    real = json.loads(src_man.read_text())
    games = [p for p in a.src.glob("*.json")
             if p.name not in ("manifest.json", "summary.json")]
    if not games:
        raise SystemExit(f"⛔ {a.src} has no per-game records — it is not a real "
                         "emitted cell and must not seed a fixture")

    def write(name, man, with_games=True, prefix="SMOKE_"):
        # ⚠️ EVERY fixture cell is named SMOKE_* because `adjudicate_smoke.py`
        # REFUSES a cell whose name does not start with SMOKE_ — it reads
        # structural keys only and must never be pointed at a real cell. The one
        # deliberate exception (REALCELL_PASS) exists to test that refusal.
        d = HERE / (prefix + name)
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        (d / "manifest.json").write_text(json.dumps(man, indent=2))
        if with_games:
            for g in games:
                shutil.copy(g, d / g.name)
        return d

    write("REAL_DRY", real)

    passing = copy.deepcopy(real)
    for addr, val in PROMOTED.items():
        _set(passing, addr, val)
    write("PASS", passing)

    for name, muts in MUTATIONS.items():
        m = copy.deepcopy(passing)
        for addr, val in muts.items():
            _set(m, addr, val)
        write(name, m)

    write("EMPTY_CELL", passing, with_games=False)
    write("PASS", passing, prefix="REALCELL_")
    d = HERE / "SMOKE_NO_MANIFEST"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    for g in games:
        shutil.copy(g, d / g.name)

    (HERE / "SPECS.json").write_text(json.dumps({
        "provenance": "generated by make_fixture.py FROM A REAL EMITTED CELL — "
                      "never hand-encoded (the fixture trap, 3 realized incidents)",
        "source_cell": str(a.src),
        "source_manifest_host": real.get("host"),
        "source_manifest_code_rev": real.get("code_rev"),
        "source_cell_real_budget": {
            "k_dets": L.dig(real, "config.champion.k_dets"),
            "sims_per_det": L.dig(real, "config.champion.sims_per_det"),
            "note": "⛔ the dry cell is a TINY budget. It is a PLUMBING witness, "
                    "never a strength measurement, and its 2 games decide nothing.",
        },
        "promoted_in_PASS": {k: v for k, v in PROMOTED.items()},
        "promotion_rationale":
            "the ONLY edit between REAL_DRY and PASS. Six budget numbers are "
            "raised to the frozen k16x1376 shape so G-BUDGET has a passing case; "
            "a fixture that genuinely ran the frozen budget would cost ~6 h. "
            "Every KEY PATH, every other value and the whole document SHAPE come "
            "from the emitter untouched, and REAL_DRY keeps the unedited original "
            "so the address-validity claim is made against real output.",
        "mutations": {k: {a2: ("<DELETED>" if v is _DELETE else v)
                          for a2, v in m.items()}
                      for k, m in MUTATIONS.items()},
    }, indent=2, ensure_ascii=False))

    (HERE / "README.txt").write_text(
        "⛔⛔ SYNTHETIC SELFTEST FIXTURE — NOT A CELL, NOT A MEASUREMENT.\n"
        "Every subdir descends from ONE REAL manifest.json emitted by\n"
        "eval_fair_puct.py (the build-time dry cell: --cand-tau-p 3.0 at k2x32\n"
        "on throwaway seeds 171999999000+). REAL_DRY is that document\n"
        "byte-untouched; PASS promotes SIX budget numbers and nothing else\n"
        "(SPECS.json lists them); every FAIL_* breaks exactly ONE thing.\n"
        "\n"
        "⛔ NO NUMBER IN HERE IS A RESULT. The per-game records are copied from\n"
        "a 2-game plumbing run and exist so an adjudicator sees a non-empty\n"
        "cell; their outcomes are meaningless and may never be pooled or quoted.\n")
    print(f"fixture written under {HERE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
