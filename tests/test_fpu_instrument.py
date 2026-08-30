"""The FPU-RESURRECTION instrument's own invariants
(`measurement/fpu_resurrection_prep/`).

⛔ These test the INSTRUMENT, not a round: 0 games exist. They exist because the
launcher-side checks run once per round and are therefore never exercised by the
smoke, and because a gate nobody has seen FAIL is a gate nobody has tested.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PREP = REPO / "measurement" / "fpu_resurrection_prep"
sys.path.insert(0, str(PREP))

pytestmark = pytest.mark.skipif(not PREP.is_dir(), reason="prep dir absent")


@pytest.fixture(scope="module")
def L():
    import screen_lib

    return screen_lib


# --------------------------------------------------------------------------- #
# THE LIBRARY IS THE LAW                                                       #
# --------------------------------------------------------------------------- #

def test_sanity_check_is_clean(L):
    assert L.sanity_check() == []


def test_selftest_passes():
    """⭐ Includes the 13 named DEFECT variants and the golden-gate artefact."""
    r = subprocess.run([sys.executable, str(PREP / "analyze_fpu.py"), "--selftest"],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-6000:]
    v = json.loads(r.stdout.split("\nSELFTEST")[0])
    assert v["problems"] == []
    assert v["golden_gate"]["verdict"] == "PASS"
    # every named defect must have voided at least one cell
    for label, d in v["fixture"].items():
        if label == "healthy":
            continue
        assert d["voided"], f"defect {label} voided no cell"


def test_workers_conf_agrees_with_the_law(L):
    """⛔ WORKERS.conf RESTATES screen_lib; a restatement that drifts is a
    launcher defect. `run_cells.sh` asserts this at launch and so does this."""
    txt = (PREP / "WORKERS.conf").read_text()

    def val(k):
        m = re.search(rf"^{k}=(\S+)$", txt, re.M)
        assert m, f"{k} missing from WORKERS.conf"
        return m.group(1)

    assert int(val("K_DETS")) == L.K_DETS
    assert int(val("SIMS_PER_DET")) == L.SIMS_PER_DET
    assert int(val("TOTAL_SIMS")) == L.TOTAL_SIMS
    assert int(val("THROWAWAY_BASE")) == L.THROWAWAY_BASE
    assert int(val("BAND_FPU02")) == L.BANDS["CELL_FPU02"]
    assert int(val("BAND_FPU04")) == L.BANDS["CELL_FPU04"]
    assert int(val("BAND_CPUCT10")) == L.BANDS["CELL_CPUCT10"]
    assert val("RULES_PROFILE") == L.RULES_PROFILE
    assert val("BACKEND") == L.BACKEND


def test_budget_is_the_promoted_champion(L):
    """⭐ 2026-08-30: desktop 11008 -> 22016. Both sides run the CURRENT
    champion, and `run_cells.sh`'s G-PROD re-asserts it against the YAML."""
    assert (L.K_DETS, L.SIMS_PER_DET, L.TOTAL_SIMS) == (16, 1376, 22016)
    assert L.K_DETS * L.SIMS_PER_DET == L.TOTAL_SIMS


def test_bands_are_disjoint_and_off_the_throwaway(L):
    rng = sorted((c.seed_start, c.seed_end, c.name) for c in L.CELLS)
    for a, b in zip(rng, rng[1:]):
        assert b[0] > a[1], f"{a} and {b} intersect"
    t_lo, t_hi = L.THROWAWAY_BASE, L.THROWAWAY_BASE + L.THROWAWAY_SPAN - 1
    for c in L.CELLS:
        assert c.seed_end < t_lo or c.seed_start > t_hi


def test_every_cell_owns_exactly_one_knob(L):
    for c in L.CELLS:
        assert (c.cand_fpu is None) != (c.cand_c_puct is None)


def test_bar_is_the_designs_own_resolution(L):
    """⛔ F-RESURRECT may never fire on an effect the design could not have
    resolved: BAR_M IS the 2-sigma resolution at n=400 decks."""
    assert abs(L.BAR_M - 2 * L.se_model(400)) < 2e-3
    assert 0.48 <= L.power_at(L.BAR_M, L.se_model(400)) <= 0.52


# --------------------------------------------------------------------------- #
# THE LADDER                                                                   #
# --------------------------------------------------------------------------- #

def test_ladder_is_exclusive_exhaustive_and_all_reachable(L):
    g = L.branch_grid(step=0.01)
    assert g["all_reachable"], g["reachable"]
    assert sum(g["histogram"].values()) == g["points"]


@pytest.mark.parametrize("M,se,want", [
    (5.0, 0.7, "F-RESURRECT"),
    (-3.0, 0.7, "F-NEGATIVE"),
    (0.0, 0.4, "F-REKILL"),
    (0.0, 1.5, "F-UNRESOLVED"),
    (1.30, 0.69, "F-UNRESOLVED"),        # below BAR_M, wide -> not RESURRECT
])
def test_named_ladder_points(L, M, se, want):
    assert L.branch_for_cell(M, se, M / se, gates_ok=True) == want


def test_a_failed_gate_voids_first(L):
    assert L.branch_for_cell(9.9, 0.1, 99.0, gates_ok=False) == "U-VOID-INSTRUMENT"


# --------------------------------------------------------------------------- #
# ⭐⭐ THE FUNDED CONDITIONALITY                                                #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("z,triggered", [(2.5, True), (-2.5, True), (2.0, True),
                                         (1.99, False), (0.0, False),
                                         (-1.5, False)])
def test_tau_trigger_is_two_sided_and_at_2sigma(L, z, triggered):
    assert L.tau_trigger({"gates_ok": True,
                          "stats": {"z": z}})["triggered"] is triggered


def test_a_voided_cpuct_cell_neither_triggers_nor_rekills(L):
    t = L.tau_trigger({"gates_ok": False, "stats": {"z": 9.0}})
    assert t["triggered"] is False
    assert "not a null" in t["why"]


def test_tau_pair_is_specified_but_not_built(L):
    """⛔ READ_RULE §6: the shape and trigger are frozen; no cell exists and the
    launcher cannot launch one."""
    assert {c.name for c in L.CELLS} == {"CELL_FPU02", "CELL_FPU04",
                                         "CELL_CPUCT10"}
    spec = L.TAU_PAIR_SPEC
    assert set(spec["cells"]) == {"CELL_TAU8", "CELL_TAU12"}
    assert spec["cells"]["CELL_TAU8"]["value"] == 8.0
    assert spec["cells"]["CELL_TAU12"]["value"] == 12.0
    # ⭐ the plumbing note must survive: tau_p has the SAME defect c_puct does
    assert "--cand-tau-p" in spec["plumbing"]
    sh = (PREP / "run_cells.sh").read_text()
    assert "--cand-tau-p" not in sh


# --------------------------------------------------------------------------- #
# THE LAUNCHER                                                                 #
# --------------------------------------------------------------------------- #

def test_launcher_parses_and_refuses_without_a_role():
    assert subprocess.run(["bash", "-n", str(PREP / "run_cells.sh")]).returncode == 0
    r = subprocess.run(["bash", str(PREP / "run_cells.sh")],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode != 0


def _launcher_code() -> str:
    """`run_cells.sh` with FULL-LINE COMMENTS STRIPPED.

    ⚠️ Load-bearing: the launcher's comments deliberately NAME the flags it must
    never use ("NOT `--c-puct`: that is the SHARED flag…", "there is NO
    `--cand-tiearb-*` flag anywhere"). A prohibition test that scanned the raw
    text would fail on the very comment that documents the prohibition — and,
    worse, would pass if someone deleted the comment and added the flag."""
    return "\n".join(ln for ln in (PREP / "run_cells.sh").read_text().splitlines()
                     if not ln.lstrip().startswith("#"))


def test_launcher_never_arms_the_tie_arbiter():
    """⛔ G-ARB-OFF's structural half: there is no --cand-tiearb-* flag anywhere
    in the launcher's CODE, by construction."""
    assert "--cand-tiearb" not in _launcher_code()


def test_launcher_uses_cand_c_puct_never_the_shared_flag():
    """⭐ DEVIATIONS D1. `--c-puct` builds BOTH sides; a cell built on it is
    champion-vs-champion."""
    code = _launcher_code()
    assert "--cand-c-puct" in code
    assert "--cand-fpu-reduction" in code
    assert not re.search(r"(?<!-)--c-puct\b", code), \
        "the launcher uses the SHARED --c-puct, which moves BOTH sides"
    assert not re.search(r"(?<!-)--tau-p\b", code), \
        "the launcher uses the SHARED --tau-p, which moves BOTH sides"


def test_launcher_passes_paired_and_a_rules_profile():
    """The PG-D8/PG-D9 defects, pinned: without --paired n_paired is 0 on every
    cell; without --rules-profile the round silently runs `walled`."""
    code = _launcher_code()
    assert "--paired" in code
    assert "--rules-profile" in code


# --------------------------------------------------------------------------- #
# THE GOLDEN GATE ARTEFACT                                                      #
# --------------------------------------------------------------------------- #

def test_golden_gate_artifact_is_pass_and_complete():
    v = json.loads((PREP / "FPU_BITEXACT.json").read_text())
    assert v["verdict"] == "PASS"
    by = {c["check"]: c for c in v["checks"]}
    for k in ("ONE-WHEEL", "TWO-TREES", "SAME-SEEDS", "SAME-BUDGET",
              "IDENTITY", "POSITIVE", "AUDIT-ADJUDICATED"):
        assert by[k]["ok"], f"{k} is not PASS"
    # ⭐ the substantive half: the knob changed EVERY game
    d = by["POSITIVE"]["detail"]
    assert d["games_that_differ"] == d["games_total"] >= 20
