"""The FPU-RESURRECTION instrument's own invariants
(`measurement/fpu_resurrection_prep/`).

⛔ These test the INSTRUMENT, not a round: 0 games exist. They exist because the
launcher-side checks run once per round and are therefore never exercised by the
smoke, and because a gate nobody has seen FAIL is a gate nobody has tested.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PREP = REPO / "measurement" / "fpu_resurrection_prep"

pytestmark = pytest.mark.skipif(not PREP.is_dir(), reason="prep dir absent")


# --------------------------------------------------------------------------- #
# ⛔⛔ R2 — THE IMPORT COLLISION (pre-launch merge review, 2026-08-30)          #
# --------------------------------------------------------------------------- #
# `measurement/phasegate_prep/` and `measurement/fpu_resurrection_prep/` BOTH
# ship a module named `screen_lib` (the FPU one is a deliberate FORK). This file
# used to do `sys.path.insert(0, PREP)` and a bare `import screen_lib` inside a
# fixture. `tests/test_phasegate_instrument.py` does the same insert-and-import
# at MODULE scope — so in any run that collects both, phasegate's module was
# imported FIRST and cached in `sys.modules['screen_lib']`, and this file's
# deferred bare import then bound THE WRONG LIBRARY: 21 failures, of which the
# dangerous ones were the ~2 that PASSED against phasegate's constants.
#
# ⭐ THE FIX, and it must stay: load by EXPLICIT PATH under a UNIQUE module name.
# ⛔ No bare `import screen_lib`, no `sys.path` insert, no reliance on collection
# order — a name that cannot collide cannot be shadowed.
def _load_by_path(mod_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_FPU_L = _load_by_path("fpu_screen_lib", PREP / "screen_lib.py")


@pytest.fixture(scope="module")
def L():
    return _FPU_L


def test_the_fpu_screen_lib_is_not_phasegates(L):
    """⛔⛔ R2's own regression pin. If this ever fails, the suite is testing
    phasegate's fork under this file's name and ~2 of its assertions are passing
    VACUOUSLY against the wrong constants."""
    assert Path(L.__file__).parent == PREP
    assert L.__name__ == "fpu_screen_lib"
    # the discriminators: phasegate is ONE band and FOUR cells; this round is
    # THREE bands, THREE cells, and owns a knob table phasegate does not have.
    assert hasattr(L, "BANDS") and len(L.BANDS) == 3
    assert not hasattr(L, "BAND"), "this is phasegate's screen_lib, not the fork"
    assert {c.name for c in L.CELLS} == {"CELL_FPU02", "CELL_FPU04",
                                         "CELL_CPUCT10"}


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


def test_launcher_passes_a_smoke_cell_spec_to_the_adjudicator():
    """⭐⭐ R1(b) — the launcher must PASS the smoke's own spec. `--root` is the
    PARENT dir and the round's cell table names only the three ROUND cells, so
    without this flag a smoke read has nothing to adjudicate the archive
    against."""
    code = _launcher_code()
    assert "--smoke-cell" in code
    assert "--smoke-mode" in code
    # the four fields the adjudicator needs, plus the box role for G-HOST
    assert re.search(r'--smoke-cell "\$\{SMOKE_NAME\}=\$\{SMOKE_KNOB\}:'
                     r'\$\{SMOKE_VAL\}:\$\{SMOKE_SEED\}:\$\{SMOKE_GAMES\}:'
                     r'\$\{ROLE\}"', code), \
        "the launcher does not pass the smoke's knob/value/seed/n/role"


# --------------------------------------------------------------------------- #
# ⭐⭐ R1 — `--smoke-mode` MUST ADJUDICATE THE SMOKE (merge review 2026-08-30)  #
# --------------------------------------------------------------------------- #
# ⛔⛔ THE DEFECT, REPRODUCED. The cell scan dropped every `SMOKE_*` dir AND
# `adjudicate()` iterated only `screen_lib.CELLS`, so a smoke read produced
# `"cells": {}` / `"resolved_knobs": {}` and STILL EXITED 0 — which made
# `run_cells.sh`'s `|| DIE "the smoke adjudication FAILED"` unreachable. The
# smoke's whole job (read the RESOLVED KNOB back off the EMITTED manifest.json)
# silently did nothing, and a launcher defect would have reached the round.
#
# ⚠️ The identical defect is REALIZED in phasegate's banked `SMOKE_local.json`
# (`"cells": {}`) — see `measurement/phasegate_prep/AMENDMENTS.md`, PG-A2
# candidate note.

FIXTURE = PREP / "selftest_fixture"


def _smoke_root(tmp_path, dirs: dict) -> Path:
    """Build a tmp `--root` from the shipped fixture: `{dest: fixture_src}`."""
    root = tmp_path / "fpu_resurrection"
    root.mkdir()
    for dest, src in dirs.items():
        shutil.copytree(FIXTURE / src, root / dest)
    return root


def _run_smoke(root: Path, *smoke_cells: str, extra=()):
    return subprocess.run(
        [sys.executable, str(PREP / "analyze_fpu.py"), "--root", str(root),
         "--smoke-mode",
         *[a for s in smoke_cells for a in ("--smoke-cell", s)], *extra],
        capture_output=True, text=True, timeout=300)


#: the shipped fixture's FPU cell replayed under a SMOKE name: fpu 0.2, band
#: 157999999000 (the throwaway block), 12 decks == 24 games, local box.
SMOKE_FPU_SPEC = "SMOKE_FPU=fpu_reduction:0.2:157999999000:24:local"
#: and its c_puct cell: override 1.0, band 157999999200, 10 decks == 20 games.
SMOKE_CPUCT_SPEC = "SMOKE_CPUCT=c_puct:1.0:157999999200:20:laptop"


def test_smoke_mode_adjudicates_a_SMOKE_dir_and_returns_the_resolved_knob(tmp_path):
    """⭐⭐ R1(a)+(c) — THE REGRESSION PIN. On the OLD code this archive produced
    `"cells": {}`, `"resolved_knobs": {}` and exit 0."""
    root = _smoke_root(tmp_path, {"SMOKE_FPU": "CELL_FPU02"})
    r = _run_smoke(root, SMOKE_FPU_SPEC)
    v = json.loads(r.stdout)

    assert v["cells"], "⛔ R1: the smoke adjudicated ZERO cells"
    assert "SMOKE_FPU" in v["cells"]
    # ⭐ the knob comes back FROM THE EMITTED manifest.json, not from the CLI
    k = v["resolved_knobs"]["SMOKE_FPU"]
    assert k["requested_fpu_reduction"] == 0.2
    assert k["frozen"]["fpu_reduction"] == 0.2
    # ⭐ and it landed on the CANDIDATE SIDE ONLY
    assert k["resolved_two_sided"]["fpu_reduction"] == {"candidate": 0.2,
                                                        "opponent": None}
    by = {g["gate"]: g["ok"] for g in v["cells"]["SMOKE_FPU"]["gates"]}
    assert by["G-FPU"] and by["G-TWOSIDED"]
    assert v["smoke_ok"] is True and v["smoke_problems"] == []
    assert r.returncode == 0


def test_smoke_mode_exits_NONZERO_when_it_adjudicates_nothing(tmp_path):
    """⛔⛔ R1(c) — THE HEART OF IT. Zero adjudicated cells must be a FAILURE, so
    that `run_cells.sh`'s `|| DIE "the smoke adjudication FAILED"` is REACHABLE.
    On the OLD code this exact call exited 0."""
    root = _smoke_root(tmp_path, {"SMOKE_FPU": "CELL_FPU02"})
    # a spec naming a directory that is not there — nothing to adjudicate
    r = _run_smoke(root, "SMOKE_ABSENT=fpu_reduction:0.2:157999999000:24:local")
    assert r.returncode != 0, "⛔ R1: a zero-cell smoke still exited 0"
    v = json.loads(r.stdout)
    assert v["cells"] == {} and v["resolved_knobs"] == {}
    assert v["smoke_ok"] is False
    assert any("ZERO CELLS" in p for p in v["smoke_problems"])


def test_smoke_mode_NEVER_adjudicates_a_real_round_cell(tmp_path):
    """⛔ R1(a) — a re-smoke at a root that ALREADY HOLDS the round's real cells
    must not adjudicate them, and must never report their stale knobs as a smoke
    PASS."""
    root = _smoke_root(tmp_path, {"SMOKE_FPU": "CELL_FPU02",
                                  "CELL_FPU04": "CELL_FPU04",
                                  "CELL_CPUCT10": "CELL_CPUCT10"})
    r = _run_smoke(root, SMOKE_FPU_SPEC)
    v = json.loads(r.stdout)
    assert set(v["cells"]) == {"SMOKE_FPU"}
    assert set(v["resolved_knobs"]) == {"SMOKE_FPU"}
    assert r.returncode == 0


def test_smoke_mode_catches_the_both_sides_c_puct_trap(tmp_path):
    """⛔⛔ R1(c) — the knob must land on the CANDIDATE SIDE ONLY. `--c-puct` is
    the SHARED flag and builds the opponent too (run_cells.sh:288-291); a round
    launched over it is champion-vs-champion and EVERY other gate passes it."""
    root = _smoke_root(tmp_path, {"SMOKE_CPUCT": "CELL_CPUCT10"})
    man = root / "SMOKE_CPUCT" / "manifest.json"
    m = json.loads(man.read_text())
    m["config"]["opponent"]["champ_cfg"]["c_puct"] = 1.0   # the opponent MOVED
    man.write_text(json.dumps(m))

    r = _run_smoke(root, SMOKE_CPUCT_SPEC)
    assert r.returncode != 0
    v = json.loads(r.stdout)
    assert v["smoke_ok"] is False
    assert any("G-TWOSIDED" in p for p in v["smoke_problems"])


def test_smoke_mode_catches_a_knob_that_never_reached_the_wire(tmp_path):
    """⛔ The harness-predates-the-round / hard-coded-None disguise: `cand_search`
    absent means the candidate was fpu-BLIND by construction."""
    root = _smoke_root(tmp_path, {"SMOKE_FPU": "CELL_FPU02"})
    man = root / "SMOKE_FPU" / "manifest.json"
    m = json.loads(man.read_text())
    del m["config"]["cand_search"]
    man.write_text(json.dumps(m))

    r = _run_smoke(root, SMOKE_FPU_SPEC)
    assert r.returncode != 0
    v = json.loads(r.stdout)
    assert any("G-FPU" in p or "did not put the knob on the wire" in p
               for p in v["smoke_problems"])


def test_smoke_mode_refuses_to_run_without_a_smoke_cell(tmp_path):
    """⛔ Without a spec there is nothing to adjudicate AGAINST, and the read
    would vacuously exit 0 — which is the R1 defect itself."""
    root = _smoke_root(tmp_path, {"SMOKE_FPU": "CELL_FPU02"})
    r = _run_smoke(root)
    assert r.returncode != 0
    assert "--smoke-cell" in r.stderr


def test_smoke_cell_is_rejected_outside_smoke_mode(tmp_path):
    root = _smoke_root(tmp_path, {"CELL_FPU02": "CELL_FPU02"})
    r = subprocess.run(
        [sys.executable, str(PREP / "analyze_fpu.py"), "--root", str(root),
         "--smoke-cell", SMOKE_FPU_SPEC],
        capture_output=True, text=True, timeout=300)
    assert r.returncode != 0
    assert "only legal with --smoke-mode" in r.stderr


def test_a_smoke_cell_may_never_name_a_round_cell(tmp_path):
    """⛔ The name must start with `SMOKE_`; otherwise a round cell could be
    adjudicated under smoke rules, which skip the round's own bars."""
    root = _smoke_root(tmp_path, {"CELL_FPU02": "CELL_FPU02"})
    r = _run_smoke(root, "CELL_FPU02=fpu_reduction:0.2:157999999000:24:local")
    assert r.returncode != 0
    assert "SMOKE_" in r.stderr


def test_smoke_mode_still_emits_NO_OUTCOME_KEY(tmp_path):
    """⛔⛔ The Stage-2 `G-SMOKE` ruling, unchanged by R1: no outcome key at ANY
    depth. The added keys are all CONFIG or verdict-structural."""
    root = _smoke_root(tmp_path, {"SMOKE_FPU": "CELL_FPU02"})
    v = json.loads(_run_smoke(root, SMOKE_FPU_SPEC).stdout)
    forbidden = {"paired_mean_margin", "paired_z", "n_paired", "winrate", "elo",
                 "M", "z", "se", "UB95", "LB95", "diff", "avg_diff", "branch",
                 "branches", "W", "D", "L", "stats", "secondary_elo",
                 "_per_deck", "se_anomaly"}

    def walk(node, path=""):
        if isinstance(node, dict):
            for k, val in node.items():
                assert k not in forbidden, f"outcome key {k!r} at {path}"
                walk(val, f"{path}.{k}")
        elif isinstance(node, list):
            for i, val in enumerate(node):
                walk(val, f"{path}[{i}]")

    walk(v)


def test_real_mode_still_skips_smoke_and_void_dirs(tmp_path):
    """⭐ R1(d) — REAL-MODE BEHAVIOUR IS UNCHANGED. A round read must never
    adjudicate a smoke archive (it runs at the PRE-LAUNCH commit by design) or a
    `_VOID_` quarantine dir."""
    root = _smoke_root(tmp_path, {"SMOKE_FPU": "CELL_FPU02",
                                  "_VOID_OLD": "CELL_FPU04",
                                  "CELL_FPU02": "CELL_FPU02"})
    r = subprocess.run(
        [sys.executable, str(PREP / "analyze_fpu.py"), "--root", str(root)],
        capture_output=True, text=True, timeout=300)
    assert r.returncode == 0
    v = json.loads(r.stdout)
    assert set(v["cells"]) == {"CELL_FPU02"}
    assert v["smoke_mode"] is False
    assert "smoke_problems" not in v and "smoke_ok" not in v


# --------------------------------------------------------------------------- #
# ⭐ R4 — THE ELO FOOTING (merge review 2026-08-30)                             #
# --------------------------------------------------------------------------- #

def test_BAR_ELO_is_on_the_DECK_PAIRED_footing(L):
    """⛔⛔ R4 — `BAR_ELO` is the DECK-PAIRED 2σ (800 games = 400 decks × 2
    seatings). `winrate_elo` used to emit the UNPAIRED binomial sigma beside it
    (±24.6 at 2σ), so the bar and its CI sat on two different rulers."""
    assert abs(L.PAIRING_FACTOR - 0.7071067811865476) < 1e-12
    paired = 2 * L.elo_sigma_paired(0.5, 800)
    unpaired = 2 * L.elo_sigma_unpaired(0.5, 800)
    assert abs(L.BAR_ELO - paired) < 0.05, "BAR_ELO is not the paired 2σ"
    assert abs(unpaired - 24.57) < 0.05, "the unpaired figure moved"
    assert abs(paired - unpaired * L.PAIRING_FACTOR) < 1e-9
    # ⛔ the provenance assert must be IN sanity_check, not only here
    assert L.sanity_check() == []


def test_winrate_elo_labels_its_footing(L):
    recs = [{"diff": 1.0, "won_by_champ": True}] * 420 + \
           [{"diff": -1.0, "won_by_champ": False}] * 380
    we = L.winrate_elo(recs)
    assert we["elo_footing"] == "deck-paired"
    assert we["elo_sig_1sigma_paired"] < we["elo_sig_1sigma_unpaired"]
    assert abs(we["elo_sig_1sigma_paired"]
               - we["elo_sig_1sigma_unpaired"] * L.PAIRING_FACTOR) < 1e-12
    # ⛔ the OLD, unlabelled key is gone on purpose
    assert "elo_sig_1sigma" not in we


def test_elo_is_never_a_branch_input(L):
    """⛔ Branches key off M / z / UB95 vs BAR_M. Moving BAR_ELO — or the elo
    itself — may not move a single branch."""
    assert "elo" not in L.branch_for_cell.__code__.co_varnames
    before = [L.branch_for_cell(m, se, m / se, gates_ok=True)
              for m in (-3.0, -0.5, 0.0, 1.0, 1.5, 3.0) for se in (0.4, 0.69, 1.4)]
    old = L.BAR_ELO
    try:
        L.BAR_ELO = 9999.0
        after = [L.branch_for_cell(m, se, m / se, gates_ok=True)
                 for m in (-3.0, -0.5, 0.0, 1.0, 1.5, 3.0)
                 for se in (0.4, 0.69, 1.4)]
    finally:
        L.BAR_ELO = old
    assert before == after


def test_the_readout_ci_is_built_on_the_paired_sigma(tmp_path):
    """⭐ R4 end-to-end: the emitted `secondary_elo` names its footing and its
    CI is the PAIRED one."""
    root = _smoke_root(tmp_path, {"CELL_FPU02": "CELL_FPU02"})
    r = subprocess.run(
        [sys.executable, str(PREP / "analyze_fpu.py"), "--root", str(root)],
        capture_output=True, text=True, timeout=300)
    se = json.loads(r.stdout)["cells"]["CELL_FPU02"]["secondary_elo"]
    assert se["footing"] == "deck-paired"
    assert "ci95_elo_paired" in se and "sigma_1_unpaired" in se
    lo, hi = se["ci95_elo_paired"]
    assert abs((hi - lo) / 4 - se["sigma_1_paired"]) < 1e-9


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
