"""The FPU PRODUCTION-H2H instrument's own invariants
(`measurement/fpu_h2h_prep/`).

⛔ These test the INSTRUMENT, not a round: 0 games exist. They exist because the
launcher-side checks run once per round and are therefore never exercised by the
smoke, and because a gate nobody has seen FAIL is a gate nobody has tested.

⚠️ SECONDS-SCALE BY CONSTRUCTION. Nothing here plays a game, imports
`carcassonne_ai`, or touches the share. The one subprocess is
`analyze_h2h.py --selftest` (~0.1 s).
"""
from __future__ import annotations

import csv
import importlib.util
import io
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PREP = REPO / "measurement" / "fpu_h2h_prep"

pytestmark = pytest.mark.skipif(not PREP.is_dir(), reason="prep dir absent")


# --------------------------------------------------------------------------- #
# ⛔⛔ R2 — THE IMPORT COLLISION (carried from the fpu_resurrection review)     #
# --------------------------------------------------------------------------- #
# `measurement/phasegate_prep/`, `measurement/fpu_resurrection_prep/`,
# `measurement/fpu_ladder_prep/` and now `measurement/fpu_h2h_prep/` ALL ship a
# module named `screen_lib` (each a deliberate FORK of the last). A bare
# `import screen_lib` after a `sys.path` insert binds whichever fork was cached
# FIRST — 21 failures in the ladder's build, of which the DANGEROUS ones were the
# ~2 that PASSED against another round's constants.
#
# ⭐ THE FIX, AND IT MUST STAY: load by EXPLICIT PATH under a UNIQUE module name.
# ⛔ No bare `import screen_lib`, no `sys.path` insert, no reliance on collection
# order — a name that cannot collide cannot be shadowed.
def _load_by_path(mod_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_H2H_L = _load_by_path("fpu_h2h_screen_lib", PREP / "screen_lib.py")


@pytest.fixture(scope="module")
def L():
    return _H2H_L


def test_the_h2h_screen_lib_is_not_a_siblings(L):
    """⛔⛔ R2's own regression pin. If this fails, the suite is testing another
    round's fork under this file's name and some assertions pass VACUOUSLY."""
    assert Path(L.__file__).parent == PREP
    assert L.__name__ == "fpu_h2h_screen_lib"
    assert L.ROUND_ID == "fpu_h2h"
    # the discriminators: phasegate is FOUR cells on ONE band and has no BANDS;
    # fpu_resurrection owns BAR_M + TAU_PAIR_SPEC; the ladder is FOUR bands with
    # BAR_EFFECT 1.5 and an arb-OFF gate; this round is ONE band, ONE cell,
    # BAR_EFFECT 1.0, and owns the two-sided arbiter vocabulary.
    assert hasattr(L, "BANDS") and len(L.BANDS) == 1
    assert not hasattr(L, "BAND_") and not hasattr(L, "TAU_PAIR_SPEC")
    assert not hasattr(L, "BAR_M"), "this is fpu_resurrection's fork"
    assert L.BAR_EFFECT == 1.0
    assert {c.name for c in L.CELLS} == {"CELL_H2H_FPU02"}
    assert hasattr(L, "DEPLOYED_TIEARB") and hasattr(L, "tiearb_sides_gate")


def test_the_arb_off_gate_is_gone_and_the_two_sided_one_replaced_it(L):
    """⛔⛔ THE INVERSION. The ladder's `G-ARB-OFF` FAILED on any armed arbiter.
    Carrying it here would void this round's healthy cell on its own premise."""
    assert not hasattr(L, "arb_off_gate"), (
        "the ladder's arb_off_gate survived the fork — it FAILS on an armed "
        "arbiter, which is exactly what this round arms on BOTH seats")
    assert hasattr(L, "tiearb_sides_gate") and hasattr(L, "tiearb_fire_gate")


def test_the_vocabulary_is_the_new_one_loaded_by_explicit_path(L):
    """⭐ `tiearb_gates` is the module merged 2026-08-31 with the opponent-side
    plumbing, and `screen_lib` loads it BY PATH under a round-unique name for the
    same R2 reason this test file does."""
    assert L.TG.__name__ == "fpu_h2h_tiearb_gates"
    assert (Path(L.TG.__file__)
            == REPO / "scripts" / "classical_search" / "tiearb_gates.py")
    assert hasattr(L.TG, "assert_tiearb_sides")
    assert hasattr(L.TG, "tiearb_sides_summary")
    # the spec is CITED, never retyped
    assert L.DEPLOYED_TIEARB == L.TG.DEPLOYED_TIEARB_B64
    assert set(L.DEPLOYED_TIEARB) == set(L.TG.TIEARB_SPEC_KEYS)
    assert "phase_gate" in L.DEPLOYED_TIEARB, (
        "a spec that omits phase_gate is UNDER-SPECIFIED — a silently-defaulted "
        "'all' on a gated cell makes it BE the ungated cell")


# --------------------------------------------------------------------------- #
# THE LIBRARY IS THE LAW                                                       #
# --------------------------------------------------------------------------- #

def test_sanity_check_is_clean(L):
    assert L.sanity_check() == []


def test_selftest_passes():
    """⭐ Includes the named DEFECT variants (24 of them, five of which only
    exist because the opponent seat can now be armed), BOTH directions of the
    FPU-A1 failure bar at the frozen 400-deck scale, and the IDENT
    propositions."""
    r = subprocess.run([sys.executable, str(PREP / "analyze_h2h.py"),
                        "--selftest"],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-8000:]
    v = json.loads(r.stdout.split("\nSELFTEST")[0])
    assert v["problems"] == []
    skip = {"healthy", "synthetic_clean_round",
            "fpu_a1_sub_bar_failure_is_REPORTED_not_void",
            "fpu_a1_at_or_above_bar_VOIDS", "ident_healthy",
            "ident_nonreproducing_detected", "ident_dose_did_not_bind_detected"}
    for label, d in v["fixture"].items():
        if label in skip:
            continue
        assert d["voided"], f"defect {label} voided no cell"
        assert d["verdict"] == "H-VOID-INSTRUMENT", label
    # ⭐ the five that could not have been written before 2026-08-31
    for label in ("opponent_seat_never_armed_the_confounded_cell",
                  "opponent_seat_present_but_disabled",
                  "the_two_seats_ran_different_B",
                  "phase_gate_key_missing_stale_wheel",
                  "opponent_seat_armed_but_never_arbitrated"):
        assert label in v["fixture"], f"{label} is not in the defect table"
    assert v["fixture"]["ident_nonreproducing_detected"] is True
    assert v["fixture"]["ident_dose_did_not_bind_detected"] is True


# --------------------------------------------------------------------------- #
# ⭐⭐ THE BAR — AN EFFECT SIZE, AND THE **CONFIRMATION** ONE                   #
# --------------------------------------------------------------------------- #

def test_the_bar_is_not_two_sigma_hat(L):
    """⛔ The house rule (owner 2026-08-30) forbids a bar set at 2*se_model."""
    assert abs(L.BAR_EFFECT - 2 * L.se_model(400)) > 0.05


def test_the_bar_is_the_confirmation_bar_not_the_ladders_screen_bar(L):
    assert L.BAR_EFFECT < L.LADDER_SCREEN_BAR == 1.5
    k16 = L.PRODUCTION_FOLD_PRECEDENTS[
        "k16x1376 budget promotion (2026-08-30, h2h_22016_20260824, b148e9)"]
    assert L.BAR_EFFECT <= k16["D_pts_per_deck"], (
        "the bar must be no harder than an effect this program has actually "
        "accepted as a production fold")


def test_the_incumbent_clears_the_bar_and_the_ladder_peak_does_not(L):
    """⭐ Both halves matter. The first says a repeat of the effect being
    confirmed is adoptable; the second says the lower bar is NOT quietly a bar
    the ladder already cleared."""
    inc = L.CONTEXT_ROWS[
        "fpu=0.2 — fpu_resurrection CELL_FPU02, band 155e9, ARB OFF"]
    assert L.branch_for_cell(inc["M"], inc["se"], inc["z"],
                             gates_ok=True) == "H-ADOPT"
    pk = L.CONTEXT_ROWS[
        "fpu=0.15 — fpu_ladder CELL_FPU015, band 166e9, ARB OFF"]
    assert L.branch_for_cell(pk["M"], pk["se"], pk["z"],
                             gates_ok=True) != "H-ADOPT"


def test_the_bar_is_on_the_interval_not_the_point_estimate(L):
    """M=+1.5 with se=0.69 is a point estimate ABOVE the bar whose LB95 (+0.12)
    is below it. That is the whole difference from a point-estimate bar."""
    assert L.branch_for_cell(1.5, 0.69, 1.5 / 0.69,
                             gates_ok=True) == "H-UNRESOLVED"


def test_elo_is_never_a_branch_input(L):
    assert "elo" not in L.branch_for_cell.__code__.co_varnames


def test_the_read_distribution_matches_the_read_rule_table(L):
    """⛔ DOC vs CODE. READ_RULE §8 prints these percentages; if the arithmetic
    moves and the prose does not, the round is advertising odds it does not have.
    """
    se0 = L.se_model(400)
    txt = (PREP / "READ_RULE.md").read_text()
    for delta, key, printed in ((0.0, "H-UNRESOLVED", "70.9 %"),
                                (0.0, "H-BOUNDED", "26.8 %"),
                                (2.95125, "H-ADOPT", "79.6 %"),
                                (1.835, "H-ADOPT", "21.5 %")):
        got = L.read_distribution(delta, se0)[key] * 100.0
        assert printed in txt, f"READ_RULE §8 no longer prints {printed}"
        assert abs(got - float(printed.split()[0])) < 0.1, (
            f"read_distribution({delta})[{key}] = {got:.2f}% but READ_RULE §8 "
            f"prints {printed}")
    assert L.n_decks_for_adopt_power(2.95125, 0.80) == 405
    assert 1400 <= L.n_decks_for_bounded_power(0.80) <= 1700


# --------------------------------------------------------------------------- #
# WORKERS.conf RESTATES THE LAW — A RESTATEMENT THAT DRIFTS IS A DEFECT        #
# --------------------------------------------------------------------------- #

def _conf(key: str) -> str:
    txt = (PREP / "WORKERS.conf").read_text()
    m = re.search(rf"^{key}=(\S+)$", txt, re.M)
    assert m, f"{key} missing from WORKERS.conf"
    return m.group(1)


def test_workers_conf_agrees_with_the_law(L):
    assert int(_conf("K_DETS")) == L.K_DETS
    assert int(_conf("SIMS_PER_DET")) == L.SIMS_PER_DET
    assert int(_conf("TOTAL_SIMS")) == L.TOTAL_SIMS
    assert int(_conf("EXACT_K")) == L.EXACT_K
    assert _conf("EXACT_MODE") == L.EXACT_MODE
    assert _conf("BACKEND") == L.BACKEND
    assert _conf("RULES_PROFILE") == L.RULES_PROFILE
    assert int(_conf("BAND_H2H")) == L.BAND == L.CELLS[0].seed_start
    assert int(_conf("THROWAWAY_BASE")) == L.THROWAWAY_BASE
    assert float(_conf("FPU_DOSE")) == L.CELLS[0].value == 0.2


def test_workers_conf_restates_the_deployed_arbiter(L):
    assert int(_conf("TIEARB_B")) == L.DEPLOYED_TIEARB["B"]
    assert int(_conf("TIEARB_J")) == L.DEPLOYED_TIEARB["J"]
    assert _conf("TIEARB_MODE") == L.DEPLOYED_TIEARB["mode"]
    assert _conf("TIEARB_SALT") == L.DEPLOYED_TIEARB["salt"]
    assert float(_conf("TIEARB_EPS")) == L.DEPLOYED_TIEARB["eps"]
    assert _conf("TIEARB_PHASE_GATE") == L.DEPLOYED_TIEARB["phase_gate"]


def test_the_provenance_ladder_is_still_unstamped():
    """⛔ The round is UNLAUNCHED at this commit: BLIND_COMMIT is PENDING, the
    band is not claimed, and W has not been stamped."""
    assert _conf("BLIND_COMMIT") == "PENDING"
    assert _conf("W_LAPTOP") == "TBD_FROM_SWEEP"
    assert not (PREP / "BAND_CLAIMED").exists()
    assert not (PREP / "PINNED_SRC_REV").exists()


def test_only_the_laptop_share_path_is_defined():
    """⚠️ THE SHARE MOUNT PATH DIFFERS BY BOX. This round is laptop-only, so a
    local path in WORKERS.conf would be the exact class of mistake the PreToolUse
    lint hook blocks."""
    txt = (PREP / "WORKERS.conf").read_text()
    assert re.search(r"^SHARE_LAPTOP=/mnt/carc-shared$", txt, re.M)
    assert not re.search(r"^SHARE_LOCAL=", txt, re.M)


# --------------------------------------------------------------------------- #
# THE LAUNCHER                                                                 #
# --------------------------------------------------------------------------- #

def test_run_cells_is_syntactically_valid():
    r = subprocess.run(["bash", "-n", str(PREP / "run_cells.sh")],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr


def test_run_cells_refuses_an_unstamped_W():
    """⛔ NOTHING is exempt — not even --dry-run. A smoke at a W the round will
    not run is a smoke of a different tenancy."""
    r = subprocess.run([str(PREP / "run_cells.sh"), "--role", "laptop",
                        "--dry-run"], capture_output=True, text=True,
                       timeout=120)
    assert r.returncode != 0
    assert "W_LAPTOP" in r.stdout + r.stderr


def test_run_cells_refuses_the_local_box():
    """⛔ The owner holds the local box, and G-HOST would void the archive after
    ~7 h of compute. The refusal is at launch instead."""
    r = subprocess.run([str(PREP / "run_cells.sh"), "--role", "local",
                        "--dry-run"], capture_output=True, text=True,
                       timeout=120)
    assert r.returncode != 0
    assert "LAPTOP ONLY" in r.stdout + r.stderr


def _launcher_code() -> str:
    """`run_cells.sh` with COMMENTS STRIPPED.

    ⚠️ Every flag-shaped invariant below must read the CODE, not the prose: the
    launcher's own comments NAME the forbidden flags (`--cand-c-puct`,
    `--c-puct`, `--tau-p`) in order to explain why they are absent, and a naive
    substring test on the whole file fires on its own documentation."""
    out = []
    for line in (PREP / "run_cells.sh").read_text().splitlines():
        out.append(re.sub(r"(^|\s)#.*$", "", line))
    return "\n".join(out)


def test_the_launcher_arms_BOTH_seats_and_carries_no_shared_knob_flag():
    """⛔⛔ THE SINGLE-VARIABLE INVARIANT, READ OFF THE LAUNCHER'S OWN CODE.

    Without `--opp-tiearb-*` the cell is candidate=champ+arb+fpu vs
    opponent=plain champ — a CONFOUNDED arb+fpu cell claiming one variable, and
    the shape this leg was INEXPRESSIBLE as before 2026-08-31.
    `--c-puct` / `--tau-p` are the SHARED flags and move BOTH sides."""
    code = _launcher_code()
    for flag in ("--cand-tiearb-enabled", "--opp-tiearb-enabled",
                 "--cand-fpu-reduction", "--paired", "--rules-profile",
                 "--out-root", "--out-subdir"):
        assert flag in code, f"{flag} is missing from the launcher"
    for forbidden in ("--cand-c-puct", "--tau-p"):
        assert forbidden not in code, (
            f"{forbidden} appears in the launcher — it would make the cell "
            "two-variable or move BOTH sides")
    # `--c-puct` must not appear as its own flag (the `--cand-...` and
    # `--opp-...` spellings are different flags and are absent anyway).
    assert not re.search(r"(?<![-\w])--c-puct(?![\w-])", code)
    # ⚠️ `--out` IS a legal flag — of `analyze_h2h.py`. What PG-D7 forbids is
    # passing it to `eval_fair_puct`, whose out dir is `--out-root`/`--out-subdir`
    # and whose argparse REFUSES the ambiguous prefix. So the check is scoped to
    # the harness invocation's own argument array, not to the whole file.
    m = re.search(r"local args=\(([\s\S]*?)\n  \)", code)
    assert m, "could not find the harness argument array in run_cells.sh"
    args_block = m.group(1)
    assert "eval_fair_puct.py" in args_block
    assert not re.search(r"(?<![-\w])--out(?![\w-])", args_block), (
        "`--out` is AMBIGUOUS in eval_fair_puct (PG-D7) — use "
        "--out-root/--out-subdir")
    for flag in ("--cand-tiearb-enabled", "--opp-tiearb-enabled", "--paired"):
        assert flag in args_block, f"{flag} is not on the harness invocation"


#: Flags the launcher passes to tools that are NOT the harness (`git`, `ps`).
_NON_HARNESS_FLAGS = {"--porcelain", "--sort"}
#: The launcher's own flags, and the adjudicator's.
_OUR_FLAGS = {"--role", "--dry-run", "--smoke", "--selftest", "--root",
              "--smoke-mode", "--smoke-cell", "--ident-mode", "--ident-a",
              "--ident-a2", "--ident-b", "--out", "--pin-laptop", "--pin-local"}


def test_every_flag_the_launcher_emits_exists_in_the_harness():
    """⭐⭐ THE WIRING TEST, WITHOUT IMPORTING THE HARNESS. A flag that
    `eval_fair_puct` does not define kills the run at argparse — after the
    precondition ladder has passed, and for the real cell that is after the
    census, the probes and the rev pin. The check is a TEXT scan of the harness's
    own `add_argument` calls, so it costs milliseconds and needs no
    `carcassonne_ai` import.

    ⚠️ `--rules-profile` is NOT declared in `eval_fair_puct.py`: it is added by
    `rules_profile.add_argument(ap)` (`src/carcassonne_ai/rules_profile.py`), so
    that file is scanned too. A scan of the harness alone would report a false
    missing flag — and the indirection is exactly the kind of thing a
    from-the-design test gets wrong."""
    known = set()
    for p in (REPO / "scripts" / "classical_search" / "eval_fair_puct.py",
              REPO / "src" / "carcassonne_ai" / "rules_profile.py"):
        known |= set(re.findall(r'add_argument\(\s*[\s\S]{0,80}?"(--[a-z0-9-]+)"',
                                p.read_text()))
    assert "--opp-tiearb-enabled" in known, (
        "this tree predates the 2026-08-31 opponent-side plumbing — the round "
        "is not expressible on it")
    assert "--rules-profile" in known
    emitted = set(re.findall(r"(?<![\w-])(--[a-z][a-z0-9-]*[a-z0-9])(?![\w-])",
                             _launcher_code()))
    missing = sorted(f for f in emitted - _OUR_FLAGS - _NON_HARNESS_FLAGS
                     if f not in known)
    assert not missing, (
        f"the launcher emits flags eval_fair_puct does not define: {missing}")


def test_the_launcher_probes_both_python_only_plumbings():
    """⛔⛔ THE PRIMARY PROVENANCE RISK HAS TWO HEADS. Both the fpu plumbing
    (2026-08-29) and the opponent-side arbiter plumbing (2026-08-31) are
    PYTHON-ONLY, so a stale box produces a healthy wheel, a healthy leaf hash and
    a silently wrong cell."""
    txt = (PREP / "run_cells.sh").read_text()
    assert "search_config_rs" in txt and "fpu=Some(" in txt
    assert "_make_opponent" in txt and "_opp_tiearb_telemetry" in txt
    assert "assert_tiearb_sides" in txt


def test_the_ident_legs_share_one_seed_and_drop_the_dose_on_exactly_one():
    """⭐ A / A2 identical; B same seeds, dose dropped. If the three legs did not
    share a seed the IDENT propositions would be about different games."""
    txt = (PREP / "run_cells.sh").read_text()
    assert txt.count("IDENT_SEED") >= 4          # one assignment + three uses
    assert 'run_cell "SMOKE_IDENT_A"' in txt
    assert 'run_cell "SMOKE_IDENT_A2"' in txt
    assert 'run_cell "SMOKE_IDENT_B"' in txt
    # leg B passes the EMPTY dose — the positive control
    assert re.search(r'run_cell "SMOKE_IDENT_B"\s+"\$IDENT_SEED"\s+'
                     r'"\$IDENT_GAMES"\s+""', txt)


def test_the_smoke_requires_the_two_new_gates(L):
    """⛔ A smoke that did not read the arbiter on BOTH seats would pass a
    launcher that armed only the candidate — and ship the confounded cell."""
    A = _load_by_path("fpu_h2h_analyze", PREP / "analyze_h2h.py")
    assert set(A.SMOKE_REQUIRED_GATES) >= {"G-FPU", "G-TWOSIDED",
                                           "G-TIEARB-SIDES", "G-TIEARB-FIRE"}


# --------------------------------------------------------------------------- #
# THE GOLDEN GATE IS INHERITED — AND THE INHERITANCE IS CHECKED, NOT ASSUMED   #
# --------------------------------------------------------------------------- #

def test_no_golden_gate_is_shipped_here_and_the_ladders_is_named():
    """⭐ This round does NOT rebuild the gate. It inherits the ladder's and
    re-asserts the wheel at launch; DESIGN §9 states the argument and names the
    two gaps the IDENT legs pay."""
    assert not (PREP / "golden_gate").exists()
    txt = (PREP / "run_cells.sh").read_text()
    assert "fpu_ladder_prep/FPU_BITEXACT_LADDER.json" in txt
    assert "carc_rs_binary_sha" in txt
    design = (PREP / "DESIGN.md").read_text()
    assert "a9bb2311ab9a635d" in design
    assert "GATE_NEST.json" in design
    for gap in ("TOGETHER", "0.2` is not one of"):
        assert gap in design, "DESIGN §9.2 no longer names both gaps"


# --------------------------------------------------------------------------- #
# THE BAND CLAIM                                                               #
# --------------------------------------------------------------------------- #

def test_band_claim_row_matches_the_registry_schema(L):
    d = json.loads((PREP / "BAND_CLAIM.json").read_text())
    assert d["_order_of_operations"], "the claim order is the 146e9 trap's fix"
    rows = d["_csv_rows"]
    assert len(rows) == 1
    parsed = next(csv.reader(io.StringIO(rows[0])))
    header = next(csv.reader(io.StringIO(
        (REPO / "governance" / "BAND_REGISTRY.csv").read_text()
        .splitlines()[0])))
    assert len(parsed) == len(header), (
        f"the CSV row has {len(parsed)} fields, the registry has {len(header)}")
    assert int(parsed[0]) == L.BAND
    assert parsed[header.index("tier")] == "claim"
    assert parsed[header.index("decision_influenced")] == "yes"
    assert parsed[header.index("evidence_or_claim")] \
        == "measurement/fpu_h2h_prep/READ_RULE.md"


def test_the_band_is_not_already_in_the_registry(L):
    """⚠️ The registry is NECESSARY AND NOT SUFFICIENT — the tree sweep is the
    binding check, re-run immediately before the append — but a band already in
    it is decisively taken."""
    txt = (REPO / "governance" / "BAND_REGISTRY.csv").read_text()
    ids = {line.split(",", 1)[0] for line in txt.splitlines()[1:] if line}
    assert str(L.BAND) not in ids
    for spent in ("164000000000", "165000000000", "166000000000",
                  "167000000000"):
        assert spent in ids, "the ladder's bands should be registered"


def test_the_throwaway_range_never_touches_the_cells_decks(L):
    c = L.CELLS[0]
    lo, hi = L.THROWAWAY_BASE, L.THROWAWAY_BASE + L.THROWAWAY_SPAN - 1
    assert c.seed_end < lo or c.seed_start > hi
    # and it lives inside this band's own 1e9 space, the house convention
    assert L.BAND <= lo <= L.BAND + 999_999_999


# --------------------------------------------------------------------------- #
# THE FIXTURE AND THE GITIGNORE                                                #
# --------------------------------------------------------------------------- #

def test_the_fixture_differs_from_the_round_in_scale_only(L):
    specs = json.loads((PREP / "selftest_fixture" / "SPECS.json").read_text())
    assert len(specs) == 1
    s, f = specs[0], L.CELLS[0]
    assert (s["name"], s["role"], s["knob"], s["value"]) == (
        f.name, f.role, f.knob, f.value)
    assert s["n_decks"] != f.n_decks and s["seed_start"] != f.seed_start


def test_the_fixture_manifest_carries_the_opponent_seat_arbiter(L):
    """⭐⭐ PG-A1: the fixture's shape is copied from a REAL emitted archive, and
    the opponent-seat addresses are the ones the gate resolves. A fixture missing
    them would teach the gate a shape no healthy cell has."""
    man = json.loads((PREP / "selftest_fixture" / L.CELLS[0].name
                      / "manifest.json").read_text())
    for addr in (("opp_tiearb",), ("config", "opp_tiearb"),
                 ("config", "opponent", "tiearb")):
        cur = man
        for part in addr:
            assert part in cur, f"the fixture has no {'.'.join(addr)}"
            cur = cur[part]
        assert cur["enabled"] is True and cur["B"] == 64
    # and the realized close-out counts, so the gate is proven to read the SPEC
    # keys only (a manifest gates identically before and after close-out)
    assert "fired_plies" in man["opp_tiearb"]
    assert "fired_plies" not in man["config"]["opp_tiearb"]
    ok, findings = L.TG.check_tiearb_sides(man, L.DEPLOYED_TIEARB,
                                           L.DEPLOYED_TIEARB)
    assert ok, findings


def test_gitignore_patterns_are_all_anchored():
    """⚠️⚠️ An unanchored `PINNED_SRC_REV` matches at ANY DEPTH and swallows
    `selftest_fixture/PINNED_SRC_REV`, which is a COMMITTED FIXTURE FILE. Without
    it the selftest raises on a fresh clone."""
    for line in (PREP / ".gitignore").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        assert line.startswith("/"), f"unanchored .gitignore pattern: {line!r}"
    assert (PREP / "selftest_fixture" / "PINNED_SRC_REV").is_file()


def test_the_read_out_is_not_gitignored():
    """⛔ The verdict is the round's deliverable and is COMMITTED, exactly as
    fpu_ladder_prep/LADDER_VERDICT.json is."""
    assert "/H2H_VERDICT.json" not in (PREP / ".gitignore").read_text()


# --------------------------------------------------------------------------- #
# THE PAIR                                                                     #
# --------------------------------------------------------------------------- #

def test_the_pair_is_frozen_and_says_zero_games_exist():
    for name in ("DESIGN.md", "READ_RULE.md"):
        txt = (PREP / name).read_text()
        assert "STATUS: FROZEN" in txt
        assert "0 games have been played at this commit" in txt


def test_the_pair_states_the_adopt_consequence_is_a_proposal(L):
    """⛔ H-ADOPT licenses PROPOSING the PRODUCTION.yaml flip and step 3 — never
    an automatic adoption. If that word softens, the round has changed."""
    assert "PROPOSING" in L.ADOPT_CONSEQUENCE
    assert "NOT AN ADOPTION" in L.ADOPT_CONSEQUENCE
    for name in ("DESIGN.md", "READ_RULE.md"):
        txt = (PREP / name).read_text()
        assert "governance/PRODUCTION.yaml" in txt
        assert ("UNTOUCHED" in txt or "does not touch" in txt), (
            f"{name} no longer says PRODUCTION.yaml is untouched on every branch")
        assert "PROPOS" in txt.upper()


def test_the_pair_names_the_owner_funding_rather_than_a_fired_trigger():
    """⚠️ The ladder read LADDER-UNRESOLVED, whose own READ_RULE §8.3 says it
    does NOT discharge the confirmation leg. This round must not claim a trigger
    fired."""
    design = (PREP / "DESIGN.md").read_text()
    assert "LADDER-UNRESOLVED" in design
    assert "OWNER-FUNDED" in design or "owner-funded" in design
    assert "feedback_execute_prereg_triggers" in design
