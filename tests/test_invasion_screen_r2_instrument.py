"""INSTRUMENT TESTS — invasion-risk term family, ROUND-2 bracket at 2752.

Pair under test: `measurement/invasion_screen_r2_prep/` (`DESIGN.md` + `READ_RULE.md`),
its bar library `screen_lib.py`, its adjudicator `analyze_screen.py`, and its
launcher `run_cells.sh`.

Adapted from `tests/test_invasion_screen_instrument.py` (round 1), which is itself
adapted from `tests/test_d2r4_instrument.py`. Round 1's three load-bearing
properties are carried verbatim:

1. **BARS LIVE IN ONE IMPLEMENTATION POINT.** Every threshold is `screen_lib`'s,
   and the launcher pins only the BAND as a numeric literal.
2. **NO SELF-INVALIDATING TESTS.** A test that re-asserts a constant against
   itself proves nothing. So the tests below check RELATIONSHIPS and BEHAVIOUR.
3. **THE ADJUDICATOR IS VALIDATED AGAINST A REAL EMITTED MANIFEST**, never a
   synthesized one — `analyze_screen.py --selftest` must exit 0.

⭐ AND ROUND 2 ADDS TWO MORE, because round 2 added the machinery that needs them:

4. **THE TWO-SIDED GATES ARE DRIVEN ON A C CELL, IN BOTH DIRECTIONS.** Three of
   the seven cells play a SHAPE-B AGENT rather than the champion, so `G-LEAF`,
   `G-INVASION`, `G-CAPFWD` and `G-SINGLEVAR` all became per-cell and two-sided.
   Every one of them is driven with the opponent pin RIGHT and WRONG, and with the
   opponent's invasion block PRESENT and ABSENT — because on a C cell "the
   opponent leaf drifted" is EXPECTED, so a gate that only checked for drift would
   be decorative exactly where it matters most.

5. ⭐ **THE FROZEN TWO-BOX ASSIGNMENT IS TESTED AS A PROPERTY, NOT AS A TABLE.**
   The owner directed round 2 onto both boxes, so the cell→box assignment is
   frozen in the prereg and `G-HOST` enforces it. The tests below check the
   PROPERTY that makes the assignment safe — **every shape sits wholly on one
   box**, so no pre-registered statistic is ever computed across the two machines
   — plus the launcher's refusal of a foreign cell, the per-box provenance
   resolution, and the one-`code_rev`-across-both-boxes conjunct.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
import random
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PREP = REPO / "measurement" / "invasion_screen_r2_prep"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


L = _load("screen_lib_r2_under_test", PREP / "screen_lib.py")
A = _load("analyze_screen_r2_under_test", PREP / "analyze_screen.py")

_FIXTURE_DIR = PREP / "selftest_fixture"


# ═══════════════════════════════════════════════════════════════════════════ #
# 1. THE SPEC IS INTERNALLY CONSISTENT                                        #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_sanity_check_is_clean():
    """`screen_lib.sanity_check()` is the spec's own consistency proof, and round
    2's version proves more than round 1's: n_games == 2*n_decks, no seed claimed
    twice, ranges contiguous, the smoke range disjoint, every knob off its
    default, the frozen leaf-diff key set equal to the ACTUAL two-sided
    difference of the two sides' invasion blocks, the opponent pin agreeing with
    the env regime, and ⭐ the cost model reproducing round 1's realized
    worker-seconds per game to 3%."""
    assert L.sanity_check() == []


def test_cell_ranges_are_disjoint_and_contiguous():
    ordered = sorted(L.CELLS, key=lambda c: c.seed_start)
    for a, b in zip(ordered, ordered[1:]):
        assert a.seed_end < b.seed_start, f"{a.name} overlaps {b.name}"
        assert b.seed_start == a.seed_end + 1, f"gap between {a.name} and {b.name}"
    assert ordered[0].seed_start == L.BAND
    total = sum(c.n_decks for c in L.CELLS)
    assert total == 2800
    assert sum(c.n_games for c in L.CELLS) == 2 * total


def test_seven_cells_three_shapes_and_every_one_is_an_arm():
    """⭐ ROUND 2 HAS NO PRECONDITION CELL. Round 1's IDENT is inherited (§3.1),
    so every cell here is an arm and every one is eligible for a branch."""
    assert len(L.CELLS) == 7
    assert L.ARM_CELLS == L.CELLS
    assert {c.shape for c in L.CELLS} == {"A", "B", "C"}
    assert len(L.cells_of_shape("A")) == 2
    assert len(L.cells_of_shape("B")) == 2
    assert len(L.cells_of_shape("C")) == 3


def test_every_shape_has_exactly_one_low_and_one_high_rung():
    """§4.5's contrast needs both ends of every shape's ladder."""
    for sh in L.SHAPES:
        rungs = [c.rung for c in L.cells_of_shape(sh)]
        assert rungs.count("low") == 1 and rungs.count("high") == 1, (sh, rungs)


def test_only_shape_c_has_an_interior_rung():
    """DESIGN §3.4 — A and B measure only x1/3 and x3 within round 2; their
    interior mid is round 1's, on ANOTHER BAND. C is the only bracketed shape."""
    interior = {c.shape for c in L.CELLS if c.rung == "mid"}
    assert interior == {"C"}


def test_the_weights_are_exactly_one_third_and_three_times_round_1s_mids():
    """⭐ THE WEIGHTS ARE NOT RE-PICKED (DESIGN §3.2). Round 1 NAMED all six
    points in its own §3.4 bracket table BEFORE it had an answer. Checked as a
    RELATIONSHIP against the ladder's own mid, not by re-asserting six literals."""
    for sh in ("A", "B"):
        lad = L.LADDER[sh]
        lo = next(c for c in L.cells_of_shape(sh) if c.rung == "low")
        hi = next(c for c in L.cells_of_shape(sh) if c.rung == "high")
        assert lo.weight == pytest.approx(lad["mid"] / 3.0, abs=1e-9), sh
        assert hi.weight == pytest.approx(lad["mid"] * 3.0, abs=1e-9), sh
    lad = L.LADDER["C"]
    weights = {c.rung: c.weight for c in L.cells_of_shape("C")}
    assert weights == {"low": lad["low"], "mid": lad["mid"], "high": lad["high"]}
    assert lad["low"] == pytest.approx(lad["mid"] / 3.0, abs=0.0035)
    assert lad["high"] == pytest.approx(lad["mid"] * 3.0, abs=0.0035)


def test_shape_d_is_not_run():
    assert "D" not in {c.shape for c in L.CELLS}
    assert "NOT RUN" in L.LADDER["D"]["note"]
    assert "not run" in L.D_NOT_RUN.lower()


def test_smoke_range_cannot_reach_any_cell():
    smoke = set(range(L.SMOKE_SEED_START, L.SMOKE_SEED_START + L.SMOKE_DECKS))
    for c in L.CELLS:
        assert not (smoke & set(c.seeds)), f"SMOKE range touches {c.name}"


def test_the_load_bearing_smoke_cell_is_a_C_cell():
    """DESIGN §9 — round 2's most-plumbing config is a C cell (the env regime, a
    non-champion opponent, the explicit-zero neutralisation, a 3-key diff,
    two-sided pins). C_MID rather than C_LOW/C_HIGH because the INTERIOR rung is
    the one §4.7's noise-signature rule reads."""
    smoke = L.cell_by_name(L.SMOKE_CELL)
    assert smoke.shape == "C"
    assert smoke.rung == "mid"
    assert smoke.shape_b_env is True
    assert smoke.box == "laptop"


# ═══════════════════════════════════════════════════════════════════════════ #
# 1b. ⭐ THE FROZEN TWO-BOX ASSIGNMENT (DESIGN §6.5)                           #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_every_shape_sits_wholly_on_one_box():
    """⭐⭐ THE LOAD-BEARING PROPERTY OF THE TWO-BOX SPLIT. If a shape were split,
    §4.5's low-vs-high contrast would become a CROSS-BOX statistic and the round
    would be resting on float identity between two machines — which this program
    HAS been bitten by (the Xeon was re-retired 2026-08-02 because AVX-512 makes
    the G0 determinism check FAIL by default). Shipping one wheel file makes such
    a comparison plausible; assigning shapes whole means nothing has to rely on
    it."""
    for sh in L.SHAPES:
        boxes = {c.box for c in L.cells_of_shape(sh)}
        assert len(boxes) == 1, f"shape {sh} is SPLIT across {sorted(boxes)}"


def test_both_boxes_are_used_and_the_assignment_partitions_the_cells():
    """The owner directed BOTH boxes. And every cell must belong to exactly one."""
    assert set(L.BOX_ROLES) == {"local", "laptop"}
    seen = []
    for role in L.BOX_ROLES:
        got = L.cells_of_box(role)
        assert got, f"box {role} has no cells"
        seen += [c.name for c in got]
    assert sorted(seen) == sorted(L.CELL_NAMES)
    assert len(seen) == len(set(seen)), "a cell is assigned to two boxes"
    assert [c.name for c in L.cells_of_box("local")] == \
        ["A_LOW", "A_HIGH", "B_LOW", "B_HIGH"]
    assert [c.name for c in L.cells_of_box("laptop")] == ["C_LOW", "C_MID", "C_HIGH"]


def test_each_box_smokes_a_config_it_will_actually_run():
    """⛔ A box that smoked another box's cell would prove nothing about its own
    plumbing — which is the entire purpose of the leg."""
    for role, sm in L.SMOKE_BY_BOX.items():
        assert L.cell_by_name(sm["cell"]).box == role, role


def test_the_two_smoke_ranges_are_disjoint_from_each_other_and_every_cell():
    seen = {}
    for role, sm in L.SMOKE_BY_BOX.items():
        for s in range(sm["seed_start"], sm["seed_start"] + L.SMOKE_DECKS):
            assert s not in seen, f"smoke seed {s} claimed by {seen.get(s)} and {role}"
            seen[s] = role
            for c in L.CELLS:
                assert not c.in_range(s), f"smoke seed {s} ({role}) overlaps {c.name}"


def test_the_share_mount_spelling_differs_by_box():
    """⚠️ CLAUDE.md: local commands use /mnt/c/carc-shared; anything INSIDE the
    laptop uses the other spelling. A launcher with the wrong one would write
    outside the share and the local adjudicator would never see the archive."""
    local = L.BOXES["local"]["share_mount"]
    laptop = L.BOXES["laptop"]["share_mount"]
    assert local != laptop
    assert local.startswith("/mnt/c/")
    assert not laptop.startswith("/mnt/c/")


def test_the_laptop_ratio_is_declared_assumed_and_bracketed():
    """⛔ It is one of exactly two unmeasured inputs, and the pair must say so
    rather than present it as a measurement."""
    assert L.BOXES["local"]["ratio_is_measured"] is True
    assert L.BOXES["local"]["per_game_ratio"] == 1.0
    assert L.BOXES["laptop"]["ratio_is_measured"] is False
    lo, hi = L.LAPTOP_RATIO_ENVELOPE
    assert lo < L.LAPTOP_RATIO_ASSUMED < hi
    assert L.BOXES["laptop"]["per_game_ratio"] == L.LAPTOP_RATIO_ASSUMED
    assert "ASSUMED, NOT MEASURED" in L.LAPTOP_RATIO_NOTE
    assert "moves no bar" in L.LAPTOP_RATIO_NOTE


def test_the_chosen_split_is_the_wall_clock_optimum_among_shape_clean_splits():
    """⭐ DESIGN §6.5(iii)'s table, RECOMPUTED rather than re-asserted. Every
    shape-clean assignment is enumerated and the frozen one must be the argmin of
    the round wall (the MAX over the two boxes, since they run concurrently)."""
    import itertools

    def wall_for(laptop_shapes) -> float:
        per_box = {"local": 0.0, "laptop": 0.0}
        for c in L.CELLS:
            role = "laptop" if c.shape in laptop_shapes else "local"
            le = L.project_cell_cost(c)["core_hours_local_equiv"]
            ratio = L.LAPTOP_RATIO_ASSUMED if role == "laptop" else 1.0
            per_box[role] += le * ratio
        return max(per_box[r] / L.BOXES[r]["W"] for r in per_box)

    frozen = frozenset({c.shape for c in L.cells_of_box("laptop")})
    options = {}
    for n in range(1, len(L.SHAPES)):
        for combo in itertools.combinations(L.SHAPES, n):
            options[frozenset(combo)] = wall_for(frozenset(combo))
    best = min(options, key=options.get)
    assert frozen == best, (
        f"the frozen split (laptop={sorted(frozen)}) is not the wall-clock optimum "
        f"({sorted(best)}); walls={ {tuple(sorted(k)): round(v, 2) for k, v in options.items()} }")
    # and it must beat a single-box local run, else the split buys nothing
    single = sum(L.project_cell_cost(c)["core_hours_local_equiv"] for c in L.CELLS) \
        / L.BOXES["local"]["W"]
    assert options[best] < single


# ═══════════════════════════════════════════════════════════════════════════ #
# 2. THE TWO OPPONENTS — the structural change round 2 is built around        #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_the_ab_cells_face_the_champion_and_the_c_cells_do_not():
    for c in L.CELLS:
        if c.shape in ("A", "B"):
            assert c.opponent == "champion"
            assert c.opp_leaf_hash == L.PROD_LEAF_HASH
            assert c.shape_b_env is False
            assert c.opp_invasion == {}
        else:
            assert c.opponent == "shape_b"
            assert c.opp_leaf_hash == L.SHAPE_B_LEAF_HASH
            assert c.shape_b_env is True
            assert c.opp_invasion == {"invasion_alpha": 0.09, "invasion_alpha_cap": 11.0}


def test_the_shape_b_agent_is_round_1s_B_MID_candidate_bit_for_bit():
    """⭐ NOT A NEW LEAF. SHAPES.md §3 requires C to be screened against something
    that invades; round 2 uses the leaf round 1 already built, screened and
    published — so nothing about C's opponent was chosen after seeing a result."""
    assert L.SHAPE_B_LEAF_HASH == L.R1_MIDS["B"]["cand_leaf_hash"]
    assert L.R1_MIDS["B"]["weight"] == 0.09
    assert L.SHAPE_B_ENV["CARCASSONNE_INVASION_ALPHA"] == "0.09"
    assert L.SHAPE_B_ENV["CARCASSONNE_INVASION_ALPHA_CAP"] == "11.0"


def test_every_c_candidate_json_carries_the_explicit_zeros():
    """⛔ LOAD-BEARING. `_load_cand_leaf_cfg` replaces named fields on the ENV
    DEFAULT_CONFIG, which in the C regime already carries alpha 0.09 / cap 11.0.
    Without the explicit zeros the candidate would INHERIT them and the cell would
    be 'B AND C vs B', not 'C vs B' — a cell that is not single-variable and that
    no gate downstream could unpick from the numbers."""
    for c in L.cells_of_shape("C"):
        body = L.LEAF_JSON_BODIES[c.leaf_json]
        assert body["invasion_alpha"] == 0.0, c.name
        assert body["invasion_alpha_cap"] == 0.0, c.name
        assert body["invasion_gamma"] == c.weight, c.name


def test_the_c_cells_leaf_diff_has_three_keys_and_the_others_do_not():
    """⭐ ROUND 2's STATEMENT OF THE SINGLE-VARIABLE PROPERTY: 'the two sides
    differ in EXACTLY the pre-registered term knobs'. On a C cell that is THREE
    keys, because the OPPONENT carries alpha + cap."""
    got = {c.name: sorted(c.leaf_diff_keys) for c in L.CELLS}
    assert got["A_LOW"] == got["A_HIGH"] == ["invasion_beta"]
    assert got["B_LOW"] == got["B_HIGH"] == ["invasion_alpha", "invasion_alpha_cap"]
    for c in L.cells_of_shape("C"):
        assert got[c.name] == ["invasion_alpha", "invasion_alpha_cap", "invasion_gamma"]


def test_no_cell_pins_the_same_leaf_on_both_sides():
    """A cell whose two sides are the same leaf measures nothing."""
    for c in L.CELLS:
        assert c.cand_leaf_hash != c.opp_leaf_hash, c.name


def test_every_candidate_hash_is_off_the_champion_pin():
    """Every round-2 cell carries a nonzero weight, so every candidate MUST move
    the hash — which is also why every cell needs --allow-leaf-hash-drift."""
    for c in L.CELLS:
        assert c.cand_leaf_hash != L.PROD_LEAF_HASH, c.name
        assert c.allow_leaf_hash_drift is True, c.name


def test_every_frozen_knob_is_off_its_default():
    """A knob frozen AT its default would be dropped by `_leaf_dict` and could
    never be observed in a manifest."""
    for c in L.CELLS:
        for k, v in c.cand_invasion.items():
            assert v != L.INVASION_DEFAULTS[k], f"{c.name}.{k} is at its default"


def test_the_leaf_json_files_on_disk_match_the_frozen_bodies():
    """The library's `LEAF_JSON_BODIES` is the frozen text; the files are what the
    launcher actually passes. Drift between them would arm the wrong leaf against
    the right hash assertion."""
    for name, body in L.LEAF_JSON_BODIES.items():
        on_disk = json.loads((PREP / name).read_text())
        assert on_disk == body, name
    assert {c.leaf_json for c in L.CELLS} == set(L.LEAF_JSON_BODIES)


# ═══════════════════════════════════════════════════════════════════════════ #
# 3. BARS LIVE IN ONE PLACE — the launcher pins only the band                 #
# ═══════════════════════════════════════════════════════════════════════════ #
def _workers_conf() -> dict[str, str]:
    out = {}
    for line in (PREP / "WORKERS.conf").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.split("#")[0].strip()
    return out


def test_workers_conf_band_matches_screen_lib():
    assert int(_workers_conf()["BAND"]) == L.BAND


def test_launcher_does_not_hardcode_any_bar():
    """⛔ The launcher must not carry a copy of any THRESHOLD. It may carry the
    band, the budget and operational constants; the bars belong to `screen_lib`
    alone, which is why the per-cell pre-check imports it."""
    sh = (PREP / "run_cells.sh").read_text()
    for forbidden in ("PROMOTE_Z", "BRACKET_Z", "REVERSED_Z", "SIGMA_D_MODEL",
                      "ELO_PER_PT_BRACKET", "N_COMMON_FRAC", "SAT_WR", "CONTRAST_Z"):
        assert f"{forbidden}=" not in sh, f"launcher hard-codes the bar {forbidden}"
    assert "screen_lib.py" in sh
    assert "leaf_gate" in sh
    assert "wheel_is_r1s" in sh


def test_launcher_cell_table_agrees_with_screen_lib():
    sh = (PREP / "run_cells.sh").read_text()
    for c in L.CELLS:
        assert f"[{c.name}]={c.seed_start}" in sh, f"{c.name} seed_start"
        assert f"[{c.name}]={c.n_decks}" in sh, f"{c.name} n_decks"
        assert f"[{c.name}]={c.n_games}" in sh, f"{c.name} n_games"
        assert f"[{c.name}]={c.leaf_json}" in sh, f"{c.name} leaf_json"
        assert f"[{c.name}]={1 if c.allow_leaf_hash_drift else 0}" in sh, f"{c.name} drift"


def test_workers_conf_carries_both_pinned_hashes_for_every_cell():
    """⭐ ROUND 2 PINS BOTH SIDES. `WORKERS.conf` is a SECOND copy of them, so it
    must be proven equal to the library's — drift here would arm the wrong
    `--cand-leaf-json` against the right hash assertion, or check the wrong
    opponent."""
    conf = _workers_conf()
    assert conf["PROD_LEAF_HASH"] == L.PROD_LEAF_HASH
    assert conf["SHAPE_B_LEAF_HASH"] == L.SHAPE_B_LEAF_HASH
    assert conf["R1_WHEEL_BINARY_SHA"] == L.R1_WHEEL_BINARY_SHA
    for c in L.CELLS:
        assert conf[f"CAND_LEAF_HASH_{c.name}"] == c.cand_leaf_hash, c.name
        assert conf[f"OPP_LEAF_HASH_{c.name}"] == c.opp_leaf_hash, c.name
    assert conf["SHAPE_B_ALPHA"] == L.SHAPE_B_ENV["CARCASSONNE_INVASION_ALPHA"]
    assert conf["SHAPE_B_ALPHA_CAP"] == L.SHAPE_B_ENV["CARCASSONNE_INVASION_ALPHA_CAP"]
    assert (int(conf["K_DETS"]), int(conf["SIMS_PER_DET"]), int(conf["TOTAL_SIMS"])) \
        == (4, 688, 2752)
    assert int(conf["K_DETS"]) * int(conf["SIMS_PER_DET"]) == int(conf["TOTAL_SIMS"])
    assert int(conf["SMOKE_GAMES"]) == L.SMOKE_GAMES
    # ⭐ per-box W, and the wheel that is SHIPPED rather than rebuilt
    for role in L.BOX_ROLES:
        assert int(conf[f"W_{role.upper()}"]) == L.BOXES[role]["W"], role
    assert conf["WHEEL_FILE"].endswith(".whl")
    # ⛔ the per-box smoke cells/seeds live in screen_lib, NOT in WORKERS.conf --
    # a second copy of them would be a second thing to drift.
    assert "SMOKE_CELL=" not in (PREP / "WORKERS.conf").read_text()
    assert "SMOKE_SEED_START=" not in (PREP / "WORKERS.conf").read_text()


def _argv_builders() -> str:
    """The body of `build_argv()`. Scanning THIS (rather than the whole file) is
    the honest test: the pair's prose deliberately NAMES the forbidden flags in
    order to forbid them."""
    text = (PREP / "run_cells.sh").read_text()
    return text.split("build_argv() {")[1].split("\n}\n")[0]


def test_launcher_never_arms_the_tie_arbiter():
    argv = _argv_builders()
    assert argv.strip(), "could not locate the argv builder in run_cells.sh"
    assert "tiearb" not in argv.lower()


def test_launcher_argv_is_symmetric_in_the_budget():
    """The single-variable property, at the source: `--k-dets`/`--sims` and
    `--opp-k-dets`/`--opp-sims` must be driven by the SAME two shell variables."""
    argv = _argv_builders()
    assert '--k-dets "$K_DETS"' in argv and '--opp-k-dets "$K_DETS"' in argv
    assert '--sims     "$SIMS_PER_DET"' in argv or '--sims "$SIMS_PER_DET"' in argv
    assert '--opp-sims "$SIMS_PER_DET"' in argv


def test_the_invasion_env_is_emitted_into_the_argv_never_exported():
    """⭐ LOAD-BEARING (DESIGN §2.5 item 3). A process-wide export would give the
    A/B cells a shape-B opponent too — the single most damaging thing this
    launcher could do. And the env is emitted on EVERY cell, pinned to 0.0/0.0 on
    the A/B cells, so a stray export in the orchestrator's shell cannot reach
    one."""
    argv = _argv_builders()
    assert 'env "CARCASSONNE_INVASION_ALPHA=$a"' in argv
    assert '"CARCASSONNE_INVASION_ALPHA_CAP=$cap"' in argv
    assert 'local a="0.0" cap="0.0"' in argv
    assert 'if [ "${CELL_BENV[$c]}" = "1" ]' in argv
    src = (PREP / "run_cells.sh").read_text()
    assert "export CARCASSONNE_INVASION" not in src, (
        "the invasion env must NEVER be exported process-wide")


def _run_launcher(*args):
    return subprocess.run(
        ["bash", str(PREP / "run_cells.sh"), *args], capture_output=True, text=True,
        env={**os.environ, "CARC_PY": sys.executable})


def test_launcher_refuses_to_run_without_a_host():
    """⛔ THERE IS NO DEFAULT, and that is the whole two-box hazard in one line: a
    launcher that silently assumed 'local' ON the laptop would run the WRONG
    CELLS at the WRONG SHARE MOUNT, and G-HOST would void them only AFTER the
    compute was spent."""
    r = _run_launcher("--dry-run")
    assert r.returncode != 0
    out = r.stdout + r.stderr
    assert "--host is REQUIRED" in out
    assert "no default" in out.lower()


def test_launcher_refuses_an_unknown_host():
    r = _run_launcher("--host", "xeon", "--dry-run")
    assert r.returncode != 0
    assert "not a known box role" in (r.stdout + r.stderr)


@pytest.mark.parametrize("role", ["local", "laptop"])
def test_launcher_dry_run_emits_only_its_own_cells(role):
    """⭐ EXECUTED, not read. Each box's dry-run must print an argv for exactly its
    own cells and REFUSE the others by name."""
    r = _run_launcher("--host", role, "--dry-run")
    assert r.returncode == 0, r.stdout + r.stderr
    mine = {c.name for c in L.cells_of_box(role)}
    theirs = {c.name for c in L.CELLS} - mine
    for name in mine:
        assert f"[dry-run] CELL {name:<6s}:" in r.stdout or \
            f"[dry-run] CELL {name}:" in r.stdout, name
    for name in theirs:
        assert f"CELL {name}: ⛔ NOT THIS BOX'S" in r.stdout, name
    # and the right share mount, with the right spelling
    assert L.BOXES[role]["share_mount"] in r.stdout


@pytest.mark.parametrize("role", ["local", "laptop"])
def test_launcher_dry_run_uses_each_boxs_own_smoke_and_W(role):
    r = _run_launcher("--host", role, "--dry-run")
    sm = L.SMOKE_BY_BOX[role]
    assert f"SMOKE ({sm['cell']} cfg, box {role})" in r.stdout
    assert f"--seed-start {sm['seed_start']}" in r.stdout
    assert f"W={L.BOXES[role]['W']}" in r.stdout


def test_launcher_dry_run_prints_the_two_box_cost_split():
    """§6.5's ETA has to be visible where the executor will look for it."""
    r = _run_launcher("--host", "local", "--dry-run")
    assert "PER BOX" in r.stdout
    assert "THEY RUN CONCURRENTLY" in r.stdout
    assert "the MAX, not the sum" in r.stdout
    assert "ASSUMED" in r.stdout          # the laptop ratio is flagged as such


def test_launcher_refuses_an_only_cell_belonging_to_the_other_box():
    """⛔ The up-front half of G-HOST: a foreign cell is refused BEFORE a game
    starts, not voided after ~30 core-h."""
    src = (PREP / "run_cells.sh").read_text()
    assert "require_cell_is_mine" in src
    main = src.split("main() {")[1]
    assert 'require_cell_is_mine "$ONLY"' in main
    assert 'require_cell_is_mine "$c"' in main


def test_launcher_is_not_executable():
    """The house pattern: tracked at mode 644. `chmod +x` is the ORCHESTRATOR's
    own launch act, never the build's."""
    mode = subprocess.run(["git", "-C", str(REPO), "ls-files", "-s",
                           "measurement/invasion_screen_r2_prep/run_cells.sh"],
                          capture_output=True, text=True).stdout
    if mode.strip():
        assert mode.split()[0] == "100644", f"run_cells.sh is tracked as {mode.split()[0]}"


def _launcher_code_paths() -> list[str]:
    src = (PREP / "run_cells.sh").read_text()
    m = re.search(r"^CODE_PATHS=\(([^)]*)\)", src, re.M)
    assert m, "CODE_PATHS not found in run_cells.sh"
    return m.group(1).split()


def test_launcher_code_paths_are_the_house_set():
    assert _launcher_code_paths() == ["src", "engine", "scripts", "rust", "tests",
                                      "pyproject.toml", "setup.py"]
    assert "measurement" not in _launcher_code_paths()


# ═══════════════════════════════════════════════════════════════════════════ #
# 4. THE LAUNCHER'S EMBEDDED HEREDOCS ACTUALLY RUN                            #
#                                                                             #
# ⭐ EXECUTE them, don't just read them. Round 1's suite found                 #
# `c.allow_hash_drift` (the field is `allow_leaf_hash_drift`) this way, in a   #
# preflight that would have aborted the round on its first real invocation.    #
# ═══════════════════════════════════════════════════════════════════════════ #
def _heredoc(tag: str) -> str:
    src = (PREP / "run_cells.sh").read_text()
    m = re.search(rf"<<'{tag}'.*?\n(.*?)\n{tag}", src, re.S)
    assert m, f"could not find the {tag} heredoc"
    return m.group(1)


#: which shell-table fields are parsed as ints (so a corruption must stay numeric,
#: else the preflight dies on ValueError instead of reporting the drifted field)
_INT_FIELDS = {1, 2, 3, 5, 8}


def _shell_table_rows(corrupt_field: int | None = None) -> str:
    rows = []
    for i, c in enumerate(L.CELLS):
        vals = [c.name, str(c.seed_start), str(c.n_decks), str(c.n_games),
                c.out_subdir, str(int(c.allow_leaf_hash_drift)), c.cand_leaf_hash,
                c.opp_leaf_hash, str(int(c.shape_b_env)), c.box]
        if corrupt_field is not None and i == 0:
            f = corrupt_field
            vals[f] = str(int(vals[f]) + 1) if f in _INT_FIELDS else vals[f] + "X"
        rows.append("|".join(vals))
    return "\n".join(rows)


def _table_env(role="local", **over):
    e = {**os.environ,
         "CARC_LIB": str(PREP / "screen_lib.py"),
         "CARC_BAND": str(L.BAND),
         "CARC_TABLE": _shell_table_rows(),
         "CARC_ROLE": role,
         "CARC_W": str(L.BOXES[role]["W"]),
         "CARC_SHARE": L.BOXES[role]["share_mount"],
         "CARC_SMOKE": f"{L.SMOKE_BY_BOX[role]['cell']}|{L.SMOKE_BY_BOX[role]['seed_start']}"}
    e.update({k: str(v) for k, v in over.items()})
    return e


@pytest.mark.parametrize("role", ["local", "laptop"])
def test_launcher_table_preflight_actually_runs(role):
    r = subprocess.run([sys.executable, "-c", _heredoc("TEOF")],
                       capture_output=True, text=True, env=_table_env(role))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "cell ranges disjoint" in r.stdout
    assert "sanity_check(): 0 problem(s)" in r.stdout
    assert "every shape sits wholly on one box" in r.stdout
    assert f"box {role}:" in r.stdout


@pytest.mark.parametrize("field,label", [(1, "seed_start"), (6, "cand_hash"),
                                         (7, "opp_hash"), (8, "shape_b_env"),
                                         (9, "box")])
def test_launcher_table_preflight_rejects_a_drifted_table(field, label):
    """⭐ INCLUDING THE THREE FIELDS ROUND 2 ADDED. A shell table that drifted on
    `opp_hash` or `shape_b_env` would run a C cell against the plain champion —
    the one cell SHAPES.md §3 forbids. One that drifted on `box` would run a cell
    on the wrong machine and make its shape's contrast cross-box. Both would look
    perfectly healthy in the numbers."""
    env = _table_env()
    env["CARC_TABLE"] = _shell_table_rows(field)
    r = subprocess.run([sys.executable, "-c", _heredoc("TEOF")],
                       capture_output=True, text=True, env=env)
    assert r.returncode != 0, f"a drifted {label} was tolerated"
    assert label in r.stdout


def test_launcher_table_preflight_rejects_a_drifted_band():
    r = subprocess.run([sys.executable, "-c", _heredoc("TEOF")],
                       capture_output=True, text=True,
                       env=_table_env(CARC_BAND=L.BAND + 1))
    assert r.returncode != 0
    assert "BAND" in r.stdout


@pytest.mark.parametrize("bad,marker", [
    ({"CARC_W": 99}, "W 99"),
    ({"CARC_SHARE": "/tmp/not-the-share"}, "share mount"),
    ({"CARC_SMOKE": "A_LOW|152999999900"}, "smoke"),
    ({"CARC_ROLE": "nosuchbox"}, "not a known box role"),
])
def test_launcher_table_preflight_rejects_a_drifted_box_config(bad, marker):
    """⭐ THE THREE PER-BOX CONSTANTS ROUND 2 ADDED, each fail-closed. A wrong
    share mount is the nastiest: the archive would land outside the share and the
    local adjudicator would simply never see that box's cells."""
    r = subprocess.run([sys.executable, "-c", _heredoc("TEOF")],
                       capture_output=True, text=True, env=_table_env(**bad))
    assert r.returncode != 0
    assert marker in r.stdout


def test_the_wheel_preflight_runs_in_both_regimes_and_probes_both_sides():
    """⭐ THE PRECONDITION UNIQUE TO ROUND 2. `DEFAULT_CONFIG` is resolved from the
    ENVIRONMENT at `virtual_score_v2` import time and never re-read, so no single
    process can observe both opponents — the probe MUST run twice. And it must
    forward the OPPONENT leaf, which nothing in this program had ever done.

    ⚠️ Skipped if `carc_rs` is not importable; the assertion below is about the
    launcher's logic, not about this box's wheel."""
    pytest.importorskip("carc_rs", reason="carc_rs not installed")
    code = _heredoc("WEOF")
    probe_path = PREP / L.WHEEL_PROBE_FILENAME
    existed = probe_path.exists()
    backup = probe_path.read_bytes() if existed else None
    try:
        probe_path.unlink(missing_ok=True)
        seen_opp = {}
        for regime in ("plain", "bshape"):
            env = {**os.environ, "CARC_REPO": str(REPO), "CARC_DIR": str(PREP),
                   "CARC_LIB": str(PREP / "screen_lib.py"), "CARC_REGIME": regime,
                   "CARC_ALPHA": "0.09", "CARC_CAP": "11.0",
                   "CARCASSONNE_FIX_R9": "1"}
            r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                               text=True, env=env)
            assert r.returncode == 0, f"{regime}: {r.stdout}\n{r.stderr[-2000:]}"
            assert "G-WHEEL-SAME PASS" in r.stdout, regime
            m = re.search(r"OPPONENT leaf hash = (\w+)", r.stdout)
            assert m, regime
            seen_opp[regime] = m.group(1)
        # ⭐ THE WHOLE MECHANISM, OBSERVED: the SAME harness call resolves to two
        # DIFFERENT opponent leaves under the two regimes.
        assert seen_opp["plain"] == L.PROD_LEAF_HASH
        assert seen_opp["bshape"] == L.SHAPE_B_LEAF_HASH
        probe = json.loads(probe_path.read_text())
        assert set(probe["cells"]) == {c.name for c in L.CELLS}, (
            "the merged probe is missing cells — one regime did not run")
        ok, why = L.wheel_probe_ok(probe)
        assert ok, why
        assert probe["opp_side_forward_ok"] is True
        assert probe["wheel_is_round_1s"] is True
    finally:
        probe_path.unlink(missing_ok=True)
        if backup is not None:
            probe_path.write_bytes(backup)


def test_the_merged_wheel_probe_check_rejects_a_half_probed_round(tmp_path):
    """⛔ A round probed in only one regime would leave three cells unverified.
    The merged-contract heredoc must refuse it."""
    code = _heredoc("PEOF")
    half = {"cells": {c.name: {} for c in L.CELLS if not c.shape_b_env},
            "carc_rs_build": "carc_rs-0.1.0+deadbeefcafe+rustcunpinned"}
    for k in L.WHEEL_PROBE_REQUIRED_TRUE:
        half[k] = True
    (tmp_path / L.WHEEL_PROBE_FILENAME).write_text(json.dumps(half))
    env = {**os.environ, "CARC_LIB": str(PREP / "screen_lib.py"),
           "CARC_DIR": str(tmp_path)}
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, env=env)
    assert r.returncode != 0
    assert "missing cells" in r.stdout


# ═══════════════════════════════════════════════════════════════════════════ #
# 5. BRANCH BEHAVIOUR — driven AT each bar, not re-asserted                   #
# ═══════════════════════════════════════════════════════════════════════════ #
@pytest.mark.parametrize("z,expected", [
    (5.00, "PROMOTE"),
    (2.01, "PROMOTE"),
    (2.00, "PROMOTE"),     # READ_RULE §4 writes `z >= +2.0` — the endpoint PROMOTES
    (1.99, "BRACKET"),
    (1.00, "BRACKET"),     # `+1.0 <= z` — the endpoint BRACKETS
    (0.99, "NULL"),
    (0.00, "NULL"),
    (-1.99, "NULL"),
    (-2.00, "REVERSED"),   # `z <= -2.0` — the endpoint REVERSES
    (-2.01, "REVERSED"),
    (-9.00, "REVERSED"),
])
def test_branch_endpoints(z, expected):
    assert L.branch_for_cell(z, gates_ok=True) == expected


def test_the_bars_are_round_1s_verbatim():
    """⛔ NOT ONE BAR MOVED. Checked against round 1's own library rather than
    against a literal, so an edit to either side is caught."""
    r1 = _load("screen_lib_r1_for_comparison",
               REPO / "measurement" / "invasion_screen_prep" / "screen_lib.py")
    assert L.PROMOTE_Z == r1.PROMOTE_Z == 2.0
    assert L.BRACKET_Z == r1.BRACKET_Z == 1.0
    assert L.REVERSED_Z == r1.REVERSED_Z == -2.0
    assert L.SAT_WR == r1.SAT_WR
    assert L.N_COMMON_FRAC == r1.N_COMMON_FRAC
    assert L.FAILURE_RATE_VOID == r1.FAILURE_RATE_VOID
    assert L.SIGMA_D_MODEL == r1.SIGMA_D_MODEL
    assert L.SE_ANOMALY_BAND == r1.SE_ANOMALY_BAND
    assert L.ELO_PER_PT_BRACKET == r1.ELO_PER_PT_BRACKET
    assert (L.RECON_RTOL, L.RECON_ATOL) == (r1.RECON_RTOL, r1.RECON_ATOL)


def test_a_failed_gate_beats_every_branch():
    for z in (5.0, 2.0, 1.0, 0.0, -2.0, -9.0):
        assert L.branch_for_cell(z, gates_ok=False) == "U-UNREADABLE"


def test_absent_z_is_unreadable_not_null():
    """A cell with no statistic is UNREADABLE. Reading it as NULL would convert a
    broken cell into evidence of no effect."""
    assert L.branch_for_cell(None, gates_ok=True) == "U-UNREADABLE"
    assert L.branch_for_cell(float("nan"), gates_ok=True) == "U-UNREADABLE"


def _all(branch: str) -> dict:
    return {c.name: branch for c in L.CELLS}


def test_round_branch_family_parks_requires_every_cell_null():
    assert L.round_branch(_all("NULL")) == "FAMILY-PARKS"


def test_round_branch_promote_fires_only_on_an_A_or_B_cell():
    """⛔ A C PROMOTE IS NOT A PROMOTION INTO THE ADOPTION CHAIN (§4.6). The
    round-level table re-labels it DEFENDS-C."""
    b = _all("NULL"); b["B_HIGH"] = "PROMOTE"
    assert L.round_branch(b) == "PROMOTE-B"
    b = _all("NULL"); b["A_LOW"] = "PROMOTE"
    assert L.round_branch(b) == "PROMOTE-A"
    b = _all("NULL"); b["C_MID"] = "PROMOTE"
    assert L.round_branch(b) == "DEFENDS-C"


def test_an_A_or_B_promote_outranks_a_C_promote():
    b = _all("NULL"); b["C_MID"] = "PROMOTE"; b["A_HIGH"] = "PROMOTE"
    assert L.round_branch(b) == "PROMOTE-A"


def test_two_shapes_promoting_are_listed_in_cell_order_without_duplicates():
    b = _all("NULL")
    b["A_LOW"] = b["A_HIGH"] = b["B_HIGH"] = "PROMOTE"
    assert L.round_branch(b) == "PROMOTE-A,B"


def test_bracket_continue_outranks_reversed_and_family_parks():
    b = _all("NULL"); b["A_LOW"] = "BRACKET"; b["A_HIGH"] = "REVERSED"
    assert L.round_branch(b) == "BRACKET-CONTINUE"


def test_reversed_fires_only_when_nothing_reached_one_sigma():
    b = _all("NULL"); b["A_HIGH"] = "REVERSED"
    assert L.round_branch(b) == "REVERSED-A"
    b = _all("NULL"); b["A_HIGH"] = "REVERSED"; b["C_LOW"] = "REVERSED"
    assert L.round_branch(b) == "REVERSED-A,C"


def test_family_parks_requires_no_reversal():
    b = _all("NULL"); b["C_HIGH"] = "REVERSED"
    assert L.round_branch(b) != "FAMILY-PARKS"


def test_one_unreadable_cell_voids_the_round_branch():
    b = _all("NULL"); b["C_LOW"] = "U-UNREADABLE"
    assert L.round_branch(b) == "U-UNREADABLE"


def test_a_missing_cell_voids_the_round_branch():
    """ABSENT is FAIL at the round level too: a cell that never ran cannot be
    silently dropped from the table."""
    b = _all("NULL"); del b["C_HIGH"]
    assert L.round_branch(b) == "U-UNREADABLE"


# ═══════════════════════════════════════════════════════════════════════════ #
# 6. G-WHEEL-SAME — round 1's IDENT, inherited                                #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_wheel_is_r1s_keys_on_the_binary_sha_alone():
    """⭐ DESIGN §3.1a. `carc_rs_build` embeds the REPO REV AT CALL TIME, not a
    compiled-in value: round 1's own smoke and cell archives carry DIFFERENT build
    strings and the SAME binary sha. A gate that compared the build string failed
    --selftest against round 1's own emitted archive."""
    ok, _ = L.wheel_is_r1s(L.R1_WHEEL_BINARY_SHA, "carc_rs-0.1.0+ffffffffffff+rustcx")
    assert ok, "the build string must NOT be compared"
    ok, _ = L.wheel_is_r1s(L.R1_WHEEL_BINARY_SHA)
    assert ok, "the build string must be OPTIONAL"


@pytest.mark.parametrize("sha", [None, "", "deadbeefcafe1234", "A9AC686BCA1417F9"])
def test_wheel_is_r1s_fails_closed_on_anything_else(sha):
    """ABSENT is FAIL, and so is a different wheel — including a case-flipped one,
    because the sha is compared exactly."""
    ok, why = L.wheel_is_r1s(sha)
    assert ok is False
    assert "IDENT" in why


def test_a_changed_wheel_message_names_the_remedy():
    """⛔ The remedy is never to relax the gate. It is an IDENT cell, or the
    original wheel."""
    _, why = L.wheel_is_r1s("deadbeefcafe1234")
    assert "RE-OWES AN IDENT CELL" in why
    assert "DIFFERENT BOX" in why


def test_the_inherited_ident_numbers_are_round_1s_actual_reading():
    """The inheritance has to point at something checkable. These are round 1's
    adjudicated IDENT numbers, and its bar."""
    assert L.R1_IDENT["z"] == pytest.approx(0.9623827653349533)
    assert abs(L.R1_IDENT["z"]) <= L.R1_IDENT["bar"]
    assert L.R1_IDENT["n_failed"] == 0
    assert L.R1_IDENT["cand_leaf_hash"] == L.R1_IDENT["opp_leaf_hash"] == L.PROD_LEAF_HASH
    assert L.R1_IDENT["band"] == L.R1_BAND != L.BAND


# ═══════════════════════════════════════════════════════════════════════════ #
# 7. G-LEAF — the two-sided gate, driven in BOTH directions on a C cell       #
# ═══════════════════════════════════════════════════════════════════════════ #
def _good_args(c):
    return (c, c.cand_leaf_hash, c.opp_leaf_hash, list(L.CURVE125))


@pytest.mark.parametrize("cell", [c.name for c in L.CELLS])
def test_leaf_gate_passes_on_the_frozen_pins(cell):
    c = L.cell_by_name(cell)
    assert L.leaf_gate(*_good_args(c))["ok"], cell


@pytest.mark.parametrize("cell", [c.name for c in L.CELLS])
def test_leaf_gate_fails_on_a_wrong_candidate_hash(cell):
    c = L.cell_by_name(cell)
    g = L.leaf_gate(c, "0" * 16, c.opp_leaf_hash, list(L.CURVE125))
    assert not g["ok"]
    assert g["conjuncts"]["cand_hash_is_pinned"] is False


@pytest.mark.parametrize("cell", [c.name for c in L.CELLS])
def test_leaf_gate_fails_on_a_wrong_opponent_hash(cell):
    """⛔ THE CONJUNCT THAT ONLY EXISTS BECAUSE `--allow-leaf-hash-drift` RELAXES
    BOTH SIDES. Round 2 passes that flag on all seven cells, so the harness's own
    opponent-side assertion enforces nothing anywhere."""
    c = L.cell_by_name(cell)
    g = L.leaf_gate(c, c.cand_leaf_hash, "1" * 16, list(L.CURVE125))
    assert not g["ok"]
    assert g["conjuncts"]["opp_hash_is_pinned"] is False


def test_leaf_gate_catches_a_C_cell_that_played_the_PLAIN_CHAMPION():
    """⭐⭐ THE SINGLE MOST IMPORTANT TEST IN THIS FILE.

    If the env regime does not reach the harness, a C cell plays the PLAIN
    CHAMPION — which is exactly the cell SHAPES.md §3 forbids ('an H2H-vs-champion
    NULL for C is EXPECTED and is NOT disconfirming'). The archive would look
    perfectly healthy: right candidate, right curve, right budget, a champion
    opponent hash that every OTHER cell in the round legitimately carries, and a
    plausible null. Only the per-cell opponent PIN distinguishes it."""
    for c in L.cells_of_shape("C"):
        g = L.leaf_gate(c, c.cand_leaf_hash, L.PROD_LEAF_HASH, list(L.CURVE125))
        assert not g["ok"], f"{c.name} accepted the plain champion as its opponent"
        assert g["conjuncts"]["opp_hash_is_pinned"] is False


def test_leaf_gate_catches_an_AB_cell_that_got_the_SHAPE_B_OPPONENT():
    """The mirror image: a stray env export leaking into an A/B cell."""
    for c in L.CELLS:
        if c.shape == "C":
            continue
        g = L.leaf_gate(c, c.cand_leaf_hash, L.SHAPE_B_LEAF_HASH, list(L.CURVE125))
        assert not g["ok"], f"{c.name} accepted a shape-B opponent"


def test_leaf_gate_requires_the_two_sides_to_be_DIFFERENT_leaves():
    """⭐ CONJUNCT (d), and it exists because of the C cells. On an A/B cell 'the
    candidate is not the champion' implies the sides differ. On a C cell BOTH pins
    are nonzero-invasion leaves, so that implication is gone and the property has
    to be stated directly."""
    c = L.cell_by_name("C_MID")
    g = L.leaf_gate(c, L.SHAPE_B_LEAF_HASH, L.SHAPE_B_LEAF_HASH, list(L.CURVE125))
    assert g["conjuncts"]["sides_are_different_leaves"] is False
    assert not g["ok"]


@pytest.mark.parametrize("curve", [None, [], [1.0] * 8, list(L.CURVE125)[:-1],
                                   [-8.0, -4.0, -1.0, 0.0, 2.0, 3.0, 4.0, 5.0]])
def test_leaf_gate_requires_curve125(curve):
    """The last one is CURVE100 — the env default `_load_cand_leaf_cfg` replaces
    fields on. A candidate that lost its explicit curve would silently be a
    curve100 agent."""
    c = L.cell_by_name("A_LOW")
    g = L.leaf_gate(c, c.cand_leaf_hash, c.opp_leaf_hash, curve)
    assert not g["ok"]
    assert g["conjuncts"]["cand_curve_is_curve125"] is False


@pytest.mark.parametrize("bad", [None, 42, ["not", "a", "hash"]])
def test_leaf_gate_absent_is_fail_not_a_vacuous_pass(bad):
    """⛔ ROUND 1's IS-D1 IN ONE ASSERTION. Its precheck got `{}` for the config,
    so `cand_hash` was None — and a sibling conjunct passed VACUOUSLY on
    `{} == {}`. `leaf_gate` requires present STRINGS, so an empty config fails
    loudly instead of passing half of it quietly."""
    c = L.cell_by_name("C_LOW")
    assert not L.leaf_gate(c, bad, c.opp_leaf_hash, list(L.CURVE125))["ok"]
    assert not L.leaf_gate(c, c.cand_leaf_hash, bad, list(L.CURVE125))["ok"]


# ═══════════════════════════════════════════════════════════════════════════ #
# 7b. G-HOST — the frozen assignment, checked                                 #
# ═══════════════════════════════════════════════════════════════════════════ #
@pytest.mark.parametrize("host", ["Doctor", "5800x", "DESKTOP-ABC", "localhost"])
def test_host_gate_accepts_a_local_hostname_for_a_local_cell(host):
    assert L.host_matches_box(host, "local")[0] is True
    assert L.host_matches_box(host, "laptop")[0] is False


@pytest.mark.parametrize("host", ["laptop", "laptop-wsl", "LAPTOP", "pop-os",
                                  "doctor-laptop"])
def test_host_gate_accepts_every_laptop_spelling_this_program_uses(host):
    """⚠️ The SAME physical box reports `laptop`, `laptop-wsl` and `laptop-pop`
    under Windows / WSL / Pop!_OS (`reference_laptop_popos_access`). Pinning one
    spelling would void a healthy cell for a dual-boot reason that has nothing to
    do with the measurement — so the test is a normalised substring."""
    assert L.host_matches_box(host, "laptop")[0] is True
    assert L.host_matches_box(host, "local")[0] is False


@pytest.mark.parametrize("bad", [None, "", 42])
def test_host_gate_absent_is_fail(bad):
    for role in L.BOX_ROLES:
        ok, why = L.host_matches_box(bad, role)
        assert ok is False
        assert "ABSENT is FAIL" in why


def test_G_HOST_catches_a_cell_run_on_the_wrong_box(tmp_path):
    """⭐ THE MISTAKE THE FROZEN ASSIGNMENT EXISTS TO PREVENT: a C cell run on the
    local box (or an A/B cell on the laptop) would make its shape's §4.5 contrast
    a CROSS-BOX statistic, and the numbers would look perfectly healthy."""
    spec = L.cell_by_name("C_MID")            # frozen to the laptop
    d = _build_full_cell(tmp_path, spec, z_target=0.0)
    man = json.loads((d / "manifest.json").read_text())
    man["host"] = "Doctor"                    # ...but it ran locally
    (d / "manifest.json").write_text(json.dumps(man))
    gates, _ = _gates_on_disk(d, spec)
    assert gates.results["G-HOST"]["ok"] is False
    assert "FROZEN" in gates.results["G-HOST"]["note"]

    local = L.cell_by_name("B_LOW")           # frozen to local
    d2 = _build_full_cell(tmp_path, local, z_target=0.0)
    man2 = json.loads((d2 / "manifest.json").read_text())
    man2["host"] = "laptop-wsl"               # ...but it ran on the laptop
    (d2 / "manifest.json").write_text(json.dumps(man2))
    gates2, _ = _gates_on_disk(d2, local)
    assert gates2.results["G-HOST"]["ok"] is False


# ═══════════════════════════════════════════════════════════════════════════ #
# 8. THE STATISTIC (carried verbatim from round 1)                            #
# ═══════════════════════════════════════════════════════════════════════════ #
def _rec(seed, a_seat, diff, won=False, drew=False):
    return {"seed": seed, "a_seat": a_seat, "diff": diff,
            "won_by_champ": won, "drew": drew}


def test_paired_margin_matches_a_hand_computation():
    recs = [_rec(1, 0, 4.0), _rec(1, 1, 2.0), _rec(2, 0, -1.0), _rec(2, 1, -3.0)]
    mean, z, n, se, per = L.paired_margin(recs)
    assert per == [3.0, -2.0]
    assert n == 2
    assert mean == pytest.approx(0.5)
    sd = math.sqrt(((3.0 - 0.5) ** 2 + (-2.0 - 0.5) ** 2) / 1)
    assert se == pytest.approx(sd / math.sqrt(2))
    assert z == pytest.approx(0.5 / se)


def test_half_paired_decks_are_dropped_never_defaulted():
    recs = [_rec(1, 0, 4.0), _rec(1, 1, 2.0), _rec(2, 0, 99.0)]
    _, _, n, _, per = L.paired_margin(recs)
    assert n == 1 and per == [3.0]


def test_fewer_than_two_decks_yields_no_z_at_all():
    recs = [_rec(1, 0, 4.0), _rec(1, 1, 2.0)]
    mean, z, n, se, _ = L.paired_margin(recs)
    assert (mean, z, n, se) == (None, None, 1, None)


def test_winrate_elo_uses_the_record_flags_not_the_sign_of_diff():
    recs = [_rec(1, 0, -5.0, won=True), _rec(1, 1, 5.0, won=False),
            _rec(2, 0, 0.0, drew=True), _rec(2, 1, 1.0, won=True)]
    r = L.winrate_elo(recs)
    assert (r["W"], r["D"], r["L"]) == (2, 1, 1)
    assert r["winrate"] == pytest.approx((2 + 0.5) / 4)


def test_recon_none_closes_only_to_none():
    assert L.recon_close(None, None)
    assert not L.recon_close(None, 0.0)
    assert not L.recon_close(0.0, None)
    assert L.recon_close(1.0, 1.0 + 1e-12)
    assert not L.recon_close(1.0, 1.0001)


def test_the_witness_reproduces_the_real_archives_own_summary():
    """⭐ TRANSCRIPTION FIDELITY, ON REAL DATA. `screen_lib`'s witness is a
    deliberately INDEPENDENT re-implementation, so the only thing that makes it a
    WITNESS rather than a second opinion is that it reproduces the harness's own
    numbers off a real archive."""
    recs = [json.loads(p.read_text())
            for p in sorted(_FIXTURE_DIR.glob("seed*_a*.json"))]
    summary = json.loads((_FIXTURE_DIR / "summary.json").read_text())
    mean, z, n, _se, _ = L.paired_margin(recs)
    we = L.winrate_elo(recs)
    for stat, got in (("paired_mean_margin", mean), ("paired_z", z),
                      ("n_paired", n), ("winrate", we["winrate"]),
                      ("elo", we["elo"])):
        assert L.recon_close(summary[stat], got), (
            f"{stat}: harness {summary[stat]!r} vs witness {got!r}")


# ═══════════════════════════════════════════════════════════════════════════ #
# 9. §4.5 THE WITHIN-ROUND CONTRAST                                           #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_contrast_is_the_unmatched_difference_with_a_root_sum_square_se():
    lo = {"D": 0.20, "se": 0.60}
    hi = {"D": 1.60, "se": 0.80}
    out = L.shape_contrast(lo, hi)
    assert out["delta"] == pytest.approx(1.40)
    assert out["se"] == pytest.approx(math.sqrt(0.60 ** 2 + 0.80 ** 2))
    assert out["z"] == pytest.approx(1.40 / out["se"])


@pytest.mark.parametrize("delta,resolved", [(2.0, True), (1.9999, False),
                                            (-2.0, True), (-1.9999, False)])
def test_contrast_verdict_switches_at_exactly_two_sigma(delta, resolved):
    """The bar is CLOSED at its endpoint, like every other bar in this pair.
    SE(Delta) is forced to 1.0 so `z == delta`."""
    se = math.sqrt(0.5)
    out = L.shape_contrast({"D": 0.0, "se": se}, {"D": delta, "se": se})
    assert out["se"] == pytest.approx(1.0)
    assert (out["verdict"] == "SCALING RESOLVED") is resolved


def test_contrast_reports_direction_only_when_resolved():
    se = math.sqrt(0.5)
    up = L.shape_contrast({"D": 0.0, "se": se}, {"D": 3.0, "se": se})
    assert "increases" in up["direction"]
    down = L.shape_contrast({"D": 0.0, "se": se}, {"D": -3.0, "se": se})
    assert "DECREASES" in down["direction"]
    flat = L.shape_contrast({"D": 0.0, "se": se}, {"D": 0.1, "se": se})
    assert "not resolved" in flat["direction"]


@pytest.mark.parametrize("lo,hi", [(None, {"D": 1.0, "se": 0.6}),
                                   ({"D": 1.0, "se": 0.6}, None),
                                   ({"D": None, "se": 0.6}, {"D": 1.0, "se": 0.6}),
                                   ({"D": 1.0, "se": None}, {"D": 1.0, "se": 0.6})])
def test_contrast_absent_is_unreadable_never_zero(lo, hi):
    out = L.shape_contrast(lo, hi)
    assert out["readable"] is False
    assert out["verdict"] == "UNREADABLE"
    assert out["delta"] is None


def test_the_contrast_power_figures_are_root_two_times_the_cell_se():
    """§4.5's published SE(Delta) figures must BE sqrt(2) x the per-cell SE, not a
    typed table. Checked as the RELATIONSHIP the rounding cannot hide."""
    rows = {r["sigma_model"]: r for r in L.CONTRAST_POWER}
    model = rows["frozen 14.67"]
    assert model["se_delta"] == pytest.approx(math.sqrt(2) * L.se_model(400), abs=1e-4)
    assert model["mde_2sigma_pts"] == pytest.approx(2 * model["se_delta"], abs=1e-4)
    realized = rows["round-1 REALIZED ~11.97"]
    assert realized["se_delta"] == pytest.approx(
        math.sqrt(2) * L.R1_MIDS["B"]["SE"], abs=1e-3)


def test_the_contrast_is_never_described_as_a_promotion_input():
    out = L.shape_contrast({"D": 0.5, "se": 0.6}, {"D": 1.5, "se": 0.6})
    assert "NEVER a promotion input" in out["why"]
    assert "UNMATCHED" in out["why"]


# ═══════════════════════════════════════════════════════════════════════════ #
# 10. §4.7 THE NOISE SIGNATURE, on C's interior rung                          #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_noise_signature_fires_only_when_the_mid_beats_BOTH_neighbours_by_over_1sigma():
    fired = L.noise_signature({"z": 2.5}, {"z": 1.0}, {"z": 1.0})
    assert fired["applicable"] and fired["fired"]
    assert "RE-MEASURE" in fired["why"]
    # beats only ONE neighbour by >1 sigma
    assert not L.noise_signature({"z": 2.5}, {"z": 1.0}, {"z": 2.0})["fired"]
    assert not L.noise_signature({"z": 2.5}, {"z": 2.0}, {"z": 1.0})["fired"]
    # exactly 1 sigma on both is NOT a signature (strict >)
    assert not L.noise_signature({"z": 2.0}, {"z": 1.0}, {"z": 1.0})["fired"]


def test_noise_signature_is_not_applicable_without_all_three_rungs():
    assert L.noise_signature(None, {"z": 1.0}, {"z": 1.0})["applicable"] is False
    assert L.noise_signature({"z": 1.0}, {"z": None}, {"z": 1.0})["applicable"] is False
    out = L.noise_signature({"z": float("nan")}, {"z": 1.0}, {"z": 1.0})
    assert out["applicable"] is False and out["fired"] is False


def test_noise_signature_never_moves_a_branch():
    """⛔ It attaches a RE-MEASURE obligation to a branch; it does not change it."""
    assert L.branch_for_cell(2.5, True) == "PROMOTE"
    assert L.noise_signature({"z": 2.5}, {"z": 1.0}, {"z": 1.0})["fired"] is True
    assert L.branch_for_cell(2.5, True) == "PROMOTE"


# ═══════════════════════════════════════════════════════════════════════════ #
# 11. THE GUARDED ELO CONVERSION (carried verbatim)                           #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_elo_limb_switches_at_the_bar():
    assert L.elo_display(2.0, 3.0, 55.0, 0.7)["limb"] == "own-ratio"
    assert L.elo_display(1.99, 3.0, 55.0, 0.7)["limb"] == "pinned-bracket"
    assert L.elo_display(-2.0, -3.0, -55.0, 0.7)["limb"] == "own-ratio"


def test_null_limb_refuses_to_print_a_measured_scale():
    d = L.elo_display(0.3, 0.02, 1.0, 0.73)
    assert d["elo_per_point"] is None
    assert d["two_sigma_elo_lo"] is not None and d["two_sigma_elo_hi"] is not None
    assert "NOT A MEASURED SCALE" in d["label"].upper()


def test_own_ratio_limb_flags_a_reading_outside_the_in_family_bracket():
    inside = L.elo_display(3.0, 3.0, 3.0 * 18.0, 0.7)
    assert inside["elo_per_point_outside_bracket"] is False
    outside = L.elo_display(3.0, 3.0, 3.0 * 900.0, 0.7)
    assert outside["elo_per_point_outside_bracket"] is True
    assert "NEVER a branch input" in outside["anomaly_note"]


def test_zero_margin_cannot_reach_the_division():
    assert L.elo_display(9.0, 0.0, 12.0, 0.7)["limb"] == "pinned-bracket"


# ═══════════════════════════════════════════════════════════════════════════ #
# 12. THE SE MODEL AND ITS FLAG                                               #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_the_se_model_is_sigma_over_root_n_not_a_typed_table():
    assert L.se_model(400) == pytest.approx(0.7335, abs=1e-4)
    assert L.se_model(200) / L.se_model(400) == pytest.approx(math.sqrt(2), abs=1e-12)


@pytest.mark.parametrize("ratio,flagged", [(0.70, False), (1.43, False),
                                           (0.6999, True), (1.4301, True)])
def test_the_dispersion_anomaly_band_is_closed_at_its_endpoints(ratio, flagged):
    out = L.se_anomaly(L.se_model(400) * ratio, 400)
    assert out["flagged"] is flagged
    assert out["ratio"] == pytest.approx(ratio)
    assert L.se_anomaly(None, 400)["flagged"] is True, "an ABSENT SE is flagged too"


def test_a_low_flag_is_labelled_as_TIGHTER_and_a_high_one_as_CONCERNING():
    """⚠️ Round 1 realized 0.714-0.834 against this model, hugging its FLOOR, so a
    low-end flag is EXPECTED and means 'tighter than modelled'. The band does not
    move for that, but the readout must not present the two directions alike."""
    low = L.se_anomaly(L.se_model(400) * 0.5, 400)
    assert low["flagged"] and "TIGHTER" in low["direction"]
    high = L.se_anomaly(L.se_model(400) * 2.0, 400)
    assert high["flagged"] and "CONCERNING" in high["direction"]


def test_round_1s_realized_ratios_would_all_sit_inside_the_band():
    """Sanity on the expectation itself: if round 2 realizes what round 1 did, no
    cell flags. A_MID's 0.714 is the closest to the floor."""
    for cell, sigma in L.R1_REALIZED_SIGMA_D.items():
        n = 200 if cell == "IDENT" else 400
        out = L.se_anomaly(sigma / math.sqrt(n), n)
        assert out["flagged"] is False, (cell, out["ratio"])


# ═══════════════════════════════════════════════════════════════════════════ #
# 13. THE COST MODEL — built on round 1's REALIZED numbers                    #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_the_cost_model_reproduces_round_1s_realized_arms():
    """⭐ THE CALIBRATION PROOF, and the reason round 2 retired round 1's two-point
    fit. Checked here as well as in `sanity_check()` because it is the whole basis
    of the funding number."""
    for cell, realized in L.R1_REALIZED_S_PER_GAME.items():
        shape_ms = {"A_MID": L.MS_SHAPE_A_SIDE, "B_MID": L.MS_SHAPE_B_SIDE,
                    "D_MID": L.MS_SHAPE_D_SIDE}[cell]
        modelled = L.MOVES_PER_SIDE * (shape_ms + L.MS_CHAMPION_SIDE) / 1000.0 * L.OVERHEAD
        assert modelled == pytest.approx(realized, rel=0.03), cell


def test_the_c_cells_are_the_expensive_ones_because_BOTH_sides_pay():
    """Round 1 could charge the invasion margin to the candidate half only — its
    opponents were all weight-0. A C cell's OPPONENT carries invasion_alpha."""
    a = L.project_cell_cost(L.cell_by_name("A_LOW"))
    c = L.project_cell_cost(L.cell_by_name("C_LOW"))
    assert c["ms_opp"] > a["ms_opp"]
    # compare on the LOCAL-EQUIVALENT scale, else the box ratio confounds it
    assert c["s_per_game_local_equiv"] > a["s_per_game_local_equiv"]
    assert c["c_side_is_assumed"] is True
    assert a["c_side_is_assumed"] is False


def test_the_box_ratio_is_applied_to_the_laptop_cells_only():
    """⭐ TWO SCALES, AND THEY ARE NOT THE SAME NUMBER. The local-equivalent scale
    is the one the seven cells are comparable on; the on-its-box scale is the one
    the funding line is in."""
    for c in L.CELLS:
        p = L.project_cell_cost(c)
        if c.box == "local":
            assert p["s_per_game"] == pytest.approx(p["s_per_game_local_equiv"])
            assert p["box_ratio"] == 1.0
        else:
            assert p["box_ratio"] == L.LAPTOP_RATIO_ASSUMED
            assert p["s_per_game"] == pytest.approx(
                p["s_per_game_local_equiv"] * L.LAPTOP_RATIO_ASSUMED)


def test_the_round_wall_is_the_MAX_over_boxes_not_the_sum():
    """⭐ THE TWO BOXES RUN CONCURRENTLY. Reading the round's wall as a sum would
    make the split look worthless; reading it as the max is what it is."""
    r = L.project_round_cost()
    walls = [b["wall_hours"] for b in r["per_box"].values()]
    assert r["wall_hours"] == pytest.approx(max(walls))
    assert r["wall_hours"] < sum(walls)
    # and the split must actually beat a single-box local run
    assert r["wall_hours"] < r["wall_hours_single_box_local"]
    # core-hours DO sum, and exceed the local-equivalent because the laptop is slower
    assert r["core_hours"] == pytest.approx(sum(b["core_hours"] for b in r["per_box"].values()))
    assert r["core_hours"] > r["core_hours_local_equiv"]


def test_the_round_cost_envelope_brackets_the_point_estimate():
    env = L.round_cost_envelope()
    assert env["low"]["core_hours"] < env["point"]["core_hours"] < env["high"]["core_hours"]
    # the C-side envelope moves ONLY the three C cells; the laptop-ratio envelope
    # moves them too — so the four A/B cells are fixed at both ends.
    for name in ("A_LOW", "A_HIGH", "B_LOW", "B_HIGH"):
        assert env["low"]["per_cell"][name]["core_hours"] == \
            env["high"]["per_cell"][name]["core_hours"]
    for name in ("C_LOW", "C_MID", "C_HIGH"):
        assert env["low"]["per_cell"][name]["core_hours"] < \
            env["high"]["per_cell"][name]["core_hours"]
    assert env["low"]["per_box"]["local"]["core_hours"] == \
        env["high"]["per_box"]["local"]["core_hours"]


def test_cost_scales_linearly_with_games():
    c = L.cell_by_name("A_LOW")
    p = L.project_cell_cost(c)
    assert p["core_hours"] == pytest.approx(p["s_per_game"] * c.n_games / 3600.0)


def test_the_funding_line_in_design_matches_the_library():
    """DESIGN §0(a)/§6.2's published range must be the one the library computes,
    ⭐ on the ACROSS-BOTH-BOXES scale that the funding line is stated in."""
    env = L.round_cost_envelope()
    design = (PREP / "DESIGN.md").read_text()
    assert 154 <= env["low"]["core_hours"] <= 156, env["low"]["core_hours"]
    assert 176 <= env["high"]["core_hours"] <= 178, env["high"]["core_hours"]
    assert "155" in design and "177" in design
    # and the local-equivalent figure must be published too, so the two scales
    # cannot be confused for each other
    assert "139.2" in design


# ═══════════════════════════════════════════════════════════════════════════ #
# 14. THE SMOKE ALLOWED SET                                                   #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_smoke_allowed_set_is_PARSED_from_read_rule_not_retyped():
    """⛔ THE SELF-INVALIDATING-TEST GUARD. Asserting the set against a literal
    copy of itself passes just as happily after someone edits both. This PARSES
    §3.5's fenced block out of `READ_RULE.md`, so the pair's prose is the
    authority and a silent WIDENING is caught."""
    md = (PREP / "READ_RULE.md").read_text()
    block = md.split("### §3.5")[1].split("---")[0].split("```")[1]
    named = set(block.split())
    assert named == set(L.SMOKE_ALLOWED_FAILURES), (
        f"READ_RULE §3.5 names {sorted(named)}; screen_lib pins "
        f"{sorted(L.SMOKE_ALLOWED_FAILURES)}")
    assert "RECON/n_paired" in named and "RECON" not in named


def test_round_2_narrowed_the_allowed_set_it_did_not_widen_it():
    """⭐ Round 1 also excused G-IDENT, a gate round 2 does not carry. Round 2's
    replacement, G-WHEEL-SAME, is NOT excused: each box's smoke runs the same
    wheel that box's cells will. G-HOST IS excused, but only mechanically — see
    the next test."""
    r1 = _load("screen_lib_r1_for_allowed_set",
               REPO / "measurement" / "invasion_screen_prep" / "screen_lib.py")
    assert "G-WHEEL-SAME" not in L.SMOKE_ALLOWED_FAILURES
    assert "G-IDENT" not in L.GATE_IDS
    # strictly smaller once G-IDENT (r1-only) and G-HOST (r2-only) are set aside
    assert (set(L.SMOKE_ALLOWED_FAILURES) - {"G-HOST"}) < set(r1.SMOKE_ALLOWED_FAILURES)


def test_G_HOST_is_excused_on_a_smoke_for_a_stated_mechanical_reason_only():
    """⚠️ `--smoke-mode` is handed a DIRECTORY, and each box smokes a DIFFERENT
    cell's config, so the smoke cell's frozen `box` is not necessarily the box
    that ran it. ⛔ THE PROPERTY IS NOT LEFT UNCHECKED: the launcher refuses a
    foreign cell before a game starts, and G-HOST is fully enforced on every REAL
    cell."""
    assert "G-HOST" in L.SMOKE_ALLOWED_FAILURES
    reason = L.SMOKE_ALLOWED_REASONS["G-HOST"]
    assert "NOT UNCHECKED" in reason.upper()
    assert "cells_of_box" in reason


def test_every_allowed_failure_carries_a_stated_reason():
    for gid in L.SMOKE_ALLOWED_FAILURES:
        assert L.SMOKE_ALLOWED_REASONS.get(gid), f"{gid} has no stated reason"
    assert set(L.SMOKE_ALLOWED_REASONS) == set(L.SMOKE_ALLOWED_FAILURES)


def test_the_structural_gates_are_NOT_excusable_on_a_smoke():
    must_pass = {"G-SINGLEVAR", "G-LEAF", "G-INVASION", "G-CAPFWD", "G-WHEEL",
                 "G-WHEEL-SAME", "G-RULES", "G-BACKEND", "G-BUDGET", "G-TIEARB",
                 "G-EXACT", "G-REV", "G-BLIND"}
    assert not (must_pass & set(L.SMOKE_ALLOWED_FAILURES))
    assert must_pass < set(L.GATE_IDS)


def test_gate_ids_are_exactly_nineteen_unique_names():
    """⭐ NINETEEN, not round 1's eighteen: G-IDENT retired with the IDENT cell,
    G-WHEEL-SAME took its slot, and G-HOST is NEW for the frozen two-box
    assignment."""
    assert len(L.GATE_IDS) == 19
    assert len(set(L.GATE_IDS)) == 19
    assert "G-HOST" in L.GATE_IDS
    assert "G-WHEEL-SAME" in L.GATE_IDS
    assert "G-IDENT" not in L.GATE_IDS


# ═══════════════════════════════════════════════════════════════════════════ #
# 15. THE HASHES ROUND-TRIP THROUGH THE HARNESS, PER ENV REGIME               #
# ═══════════════════════════════════════════════════════════════════════════ #
def _derive_hashes(regime: str) -> dict:
    """Resolve every cell of one env regime through the HARNESS's own
    `_load_cand_leaf_cfg` + `_leaf_hash`, in a CHILD process.

    ⚠️ A CHILD, not this process: `DEFAULT_CONFIG` is resolved from the
    environment at `virtual_score_v2` import time and never re-read, so the two
    regimes cannot coexist in one interpreter. That is the same structural fact
    that makes the launcher's wheel probe run twice."""
    code = r"""
import json, os, sys
regime = sys.argv[1]
if regime == "bshape":
    os.environ["CARCASSONNE_INVASION_ALPHA"] = "0.09"
    os.environ["CARCASSONNE_INVASION_ALPHA_CAP"] = "11.0"
os.environ.setdefault("CARCASSONNE_FIX_R9", "1")
sys.path.insert(0, sys.argv[2])
sys.path.insert(0, sys.argv[3])
import eval_fair_puct as H
out = {"opp": H._leaf_hash(H._curve125_leaf_cfg()), "cells": {}}
for name, path in json.loads(sys.argv[4]).items():
    cfg = H._load_cand_leaf_cfg(path)
    d = H._leaf_dict(cfg)
    out["cells"][name] = {
        "hash": H._leaf_hash(cfg),
        "curve": list(cfg.v29_meeple_curve or ()),
        "invasion": {k: v for k, v in d.items() if k.startswith("invasion")},
    }
out["opp_invasion"] = {k: v for k, v in
                       H._leaf_dict(H._curve125_leaf_cfg()).items()
                       if k.startswith("invasion")}
print(json.dumps(out))
"""
    want = {c.name: str(PREP / c.leaf_json) for c in L.CELLS
            if bool(c.shape_b_env) == (regime == "bshape")}
    r = subprocess.run(
        [sys.executable, "-c", code, regime, str(REPO / "src"),
         str(REPO / "scripts" / "classical_search"), json.dumps(want)],
        capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip(f"harness not importable: {r.stderr[-500:]}")
    return json.loads(r.stdout)


@pytest.mark.parametrize("regime", ["plain", "bshape"])
def test_both_pinned_hashes_round_trip_through_the_harness(regime):
    """⭐ THE PINS ARE NOT DECORATION. `G-LEAF` gates on them, and on a C cell they
    are the ONLY thing distinguishing a correct opponent from a wrong one. Both
    sides, both regimes, through the harness's OWN code path."""
    got = _derive_hashes(regime)
    for c in L.CELLS:
        if bool(c.shape_b_env) != (regime == "bshape"):
            continue
        cell = got["cells"][c.name]
        assert cell["hash"] == c.cand_leaf_hash, f"{c.name} candidate hash drifted"
        assert tuple(cell["curve"]) == tuple(L.CURVE125), f"{c.name} is not curve125"
        assert cell["invasion"] == dict(c.cand_invasion), c.name
        assert got["opp"] == c.opp_leaf_hash, f"{c.name} opponent hash drifted"
        assert got["opp_invasion"] == dict(c.opp_invasion), c.name


def test_the_env_regime_is_what_moves_the_opponent_leaf():
    """⭐ THE MECHANISM ITSELF, OBSERVED END TO END (DESIGN §2.5). The SAME harness
    call — `_curve125_leaf_cfg()`, which is literally what eval_fair_puct.py:3774
    hands the head-to-head opponent — resolves to two DIFFERENT leaves under the
    two regimes, and nothing but the environment differs between them."""
    assert _derive_hashes("plain")["opp"] == L.PROD_LEAF_HASH
    assert _derive_hashes("bshape")["opp"] == L.SHAPE_B_LEAF_HASH


def test_the_explicit_zeros_fully_neutralise_the_env_on_the_candidate_side():
    """⛔ If they did not, a C cell would be 'B AND C vs B'. The proof: the C
    candidates resolve to the SAME hash whether or not the env is set."""
    with_env = _derive_hashes("bshape")["cells"]
    code = r"""
import json, os, sys
os.environ.setdefault("CARCASSONNE_FIX_R9", "1")
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
import eval_fair_puct as H
print(json.dumps({n: H._leaf_hash(H._load_cand_leaf_cfg(p))
                  for n, p in json.loads(sys.argv[3]).items()}))
"""
    want = {c.name: str(PREP / c.leaf_json) for c in L.cells_of_shape("C")}
    r = subprocess.run([sys.executable, "-c", code, str(REPO / "src"),
                        str(REPO / "scripts" / "classical_search"), json.dumps(want)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("harness not importable")
    without_env = json.loads(r.stdout)
    for name, h in without_env.items():
        assert with_env[name]["hash"] == h, (
            f"{name}: the env leaked into the candidate leaf — the cell would be "
            "'B AND C vs B', not 'C vs B'")


def test_round_1s_frozen_hashes_reproduce_through_the_same_machinery():
    """⭐ THE DERIVATION MACHINERY'S OWN CONTROL. Round 2's pins are only as
    trustworthy as the code path that produced them, so that path is required to
    reproduce round 1's three published hashes and the champion pin EXACTLY.
    ⚠️ Deriving WITHOUT the harness reproduces NONE of them — `eval_fair_puct`
    installs its own `_CANON_ENV` above every carcassonne_ai import."""
    code = r"""
import json, os, sys
os.environ.setdefault("CARCASSONNE_FIX_R9", "1")
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
import eval_fair_puct as H
c125 = [-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25]
out = {"champion": H._leaf_hash(H._curve125_leaf_cfg())}
for name, spec in {
        "A_MID": {"v29_meeple_curve": c125, "invasion_beta": 0.12},
        "B_MID": {"v29_meeple_curve": c125, "invasion_alpha": 0.09,
                  "invasion_alpha_cap": 11.0},
        "D_MID": {"v29_meeple_curve": c125, "invasion_delta_farm": 0.12}}.items():
    out[name] = H._leaf_hash(H._load_cand_leaf_cfg(json.dumps(spec)))
print(json.dumps(out))
"""
    r = subprocess.run([sys.executable, "-c", code, str(REPO / "src"),
                        str(REPO / "scripts" / "classical_search")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("harness not importable")
    got = json.loads(r.stdout)
    assert got["champion"] == L.PROD_LEAF_HASH
    assert got["A_MID"] == L.R1_MIDS["A"]["cand_leaf_hash"]
    assert got["B_MID"] == L.R1_MIDS["B"]["cand_leaf_hash"] == L.SHAPE_B_LEAF_HASH
    assert got["D_MID"] == L.R1_MIDS["D"]["cand_leaf_hash"]


# ═══════════════════════════════════════════════════════════════════════════ #
# 16. THE GATES, DRIVEN ON REAL AND RE-BADGED ARCHIVES                        #
#                                                                             #
# The archives below are re-badges of `selftest_fixture/manifest.json` — a     #
# REAL emitted manifest — onto each cell's frozen band, with per-deck margins  #
# constructed to hit an EXACT z. Nothing here plays a game or spends a deck.   #
# ═══════════════════════════════════════════════════════════════════════════ #
def _exact_z_margins(n: int, z_target: float, seed: int = 20260827) -> list[float]:
    """`n` per-deck margins whose deck-paired z is EXACTLY `z_target`. `se` is
    shift-invariant, so a pure shift moves the mean without touching dispersion."""
    rng = random.Random(seed)
    xs = [rng.gauss(0.0, 12.0) for _ in range(n)]
    mx = sum(xs) / n
    var = sum((x - mx) ** 2 for x in xs) / (n - 1)
    se = math.sqrt(var / n)
    return [x - mx + z_target * se for x in xs]


def _build_full_cell(root: Path, spec, *, z_target: float = 0.0,
                     blind: str = "b" * 40, pinned: str = "b" * 40,
                     n_decks: int | None = None) -> Path:
    """A structurally HEALTHY full-size archive for `spec`, re-badged from the real
    emitted manifest onto that cell's own frozen deck range and its own TWO
    pinned leaves."""
    man = json.loads((_FIXTURE_DIR / "manifest.json").read_text())
    cfg = man["config"]
    champ_leaf = copy.deepcopy(cfg["cand_leaf_cfg"])
    # strip the fixture's own invasion keys so the re-badge starts from a clean
    # curve125 leaf, whatever the fixture happened to carry
    for k in L.INVASION_FIELDS:
        champ_leaf.pop(k, None)
    n_decks = spec.n_decks if n_decks is None else n_decks

    cfg["band_seed_start"] = spec.seed_start
    cfg["seed_start"] = spec.seed_start
    cfg["n_decks"] = n_decks
    cfg["n"] = 2 * n_decks
    cfg["seatings_per_deck"] = 2
    # `_leaf_dict` DROPS a field at its default, so each side carries exactly its
    # own non-default invasion keys — which is what makes the leaf diff equal the
    # cell's frozen key set.
    cfg["cand_leaf_cfg"] = dict(champ_leaf, **dict(spec.cand_invasion))
    cfg["cand_leaf_hash"] = spec.cand_leaf_hash
    cfg["opp_leaf_cfg"] = dict(champ_leaf, **dict(spec.opp_invasion))
    cfg["opp_leaf_hash"] = spec.opp_leaf_hash
    # `config.champion.leaf_cfg` is the FULL asdict (nothing dropped) — where
    # G-INVASION and G-CAPFWD read the candidate's six invasion fields from.
    cfg["champion"]["leaf_cfg"].update(L.INVASION_DEFAULTS)
    cfg["champion"]["leaf_cfg"].update(dict(spec.cand_invasion))
    cfg["stamps"] = {"BLIND_COMMIT": blind}
    # ⚠️ the real manifest carries the stamp at the TOP LEVEL too, and that is the
    # address `G-BLIND` resolves FIRST — re-badging only `config.stamps` would
    # leave round 1's own blind sha in place and fail on "stamp mismatch".
    man["BLIND_COMMIT"] = blind
    man["SCREEN_CELL"] = spec.name
    cfg["code_rev"] = pinned[:8]
    man["code_rev"] = pinned[:8]
    man["carc_rs_binary_sha"] = L.R1_WHEEL_BINARY_SHA
    # ⭐ the host the FROZEN assignment says this cell runs on (G-HOST)
    man["host"] = "laptop-wsl" if spec.box == "laptop" else "Doctor"

    d = root / spec.out_subdir
    d.mkdir(parents=True, exist_ok=True)
    recs = []
    for i, m in enumerate(_exact_z_margins(n_decks, z_target)):
        s = spec.seed_start + i
        for a in (0, 1):
            recs.append({"seed": s, "a_seat": a,
                         "diff": (2.0 * m) if a == 0 else 0.0,
                         "won_by_champ": ((i + a) % 2 == 0), "drew": False,
                         "deck_hash": f"{s:016x}"})
    for r in recs:
        (d / f"seed{r['seed']:012d}_a{r['a_seat']}.json").write_text(json.dumps(r))

    mean, z, n_paired, _se, _ = L.paired_margin(recs)
    we = L.winrate_elo(recs)
    (d / "summary.json").write_text(json.dumps({
        "n": 2 * n_decks, "n_failed": 0, "failure_rate": 0.0,
        "winrate": we["winrate"], "elo": we["elo"],
        "elo_sig_1sigma": we["elo_sig_1sigma"],
        "paired_mean_margin": mean, "paired_z": z, "n_paired": n_paired,
        "avg_diff": we["avg_diff"],
        "champ_prefix_ms_per_move": 690.0, "rung_ms_per_move": 470.0,
    }, indent=1))
    (d / "manifest.json").write_text(json.dumps(man, indent=1))
    return d


def _healthy_probe() -> dict:
    p = {k: True for k in L.WHEEL_PROBE_REQUIRED_TRUE}
    p["carc_rs_build"] = "carc_rs-0.1.0+deadbeefcafe+rustcunpinned"
    return p


def _healthy_wheel_ancestry(rev: str = "deadbeefcafe") -> dict:
    return {"ok": True, "rev": rev, "invasion_source_present": True,
            "is_ancestor": True, "why": ""}


def _healthy_blind_proof(blind: str = "b" * 40) -> dict:
    return {"ok": True, "blind_commit": blind, "is_ancestor_of_head": True,
            "introduced_frozen_banner": True, "proof_ok": True, "why": ""}


def _healthy_src_clean(cells=None) -> dict:
    names = ["pre-flight"] + [f"{c.name}-after-seal" for c in (cells or L.CELLS)]
    return {"ok": True, "boundaries": names, "dirty_boundaries": [],
            "has_preflight": True, "missing_after": [], "why": ""}


def _gates_on_disk(cell_dir: Path, spec, *, blind="b" * 40, pinned="b" * 40, **over):
    kw = dict(pinned_src_rev=pinned, blind_commit=blind,
              wheel_probe=_healthy_probe(),
              wheel_ancestry=_healthy_wheel_ancestry(),
              blind_proof=_healthy_blind_proof(blind),
              src_clean=_healthy_src_clean())
    kw.update(over)
    return A.run_gates(A.Cell(spec, cell_dir), **kw)


@pytest.mark.parametrize("cell", [c.name for c in L.CELLS])
def test_a_healthy_full_size_archive_passes_every_gate(tmp_path, cell):
    """⭐ THE SATISFIABILITY CONTROL (READ_RULE §3.1 question 2), driven on EVERY
    cell — including the three whose opponent is not the champion. If a full-size
    re-badge of a REAL emitted manifest could not clear every per-cell gate, the
    §9 smoke leg would be a PERMANENT launch blocker and the ABSENT tests below
    would be proving nothing."""
    spec = L.cell_by_name(cell)
    d = _build_full_cell(tmp_path, spec, z_target=0.0)
    gates, _ = _gates_on_disk(d, spec)
    failed = gates.failed()
    assert failed == [], json.dumps({g: gates.results[g] for g in failed},
                                    default=str, indent=1)


def test_G_INVASION_catches_a_C_cell_whose_OPPONENT_BLOCK_IS_EMPTY(tmp_path):
    """⭐⭐ THE OTHER MOST IMPORTANT TEST. An empty opponent invasion block on a C
    cell means THE ENV REGIME DID NOT REACH THE HARNESS and the cell played the
    plain champion. Round 1's rule — 'the opponent carries no invasion key' —
    would have PASSED this archive, because on an A/B cell an empty opponent block
    is exactly right."""
    spec = L.cell_by_name("C_MID")
    d = _build_full_cell(tmp_path, spec, z_target=0.0)
    man = json.loads((d / "manifest.json").read_text())
    for k in L.INVASION_FIELDS:
        man["config"]["opp_leaf_cfg"].pop(k, None)
    (d / "manifest.json").write_text(json.dumps(man))
    gates, _ = _gates_on_disk(d, spec)
    assert gates.results["G-INVASION"]["ok"] is False
    assert gates.results["G-SINGLEVAR"]["ok"] is False, (
        "the leaf diff would drop to one key — G-SINGLEVAR must catch it too")


def test_G_INVASION_catches_an_AB_cell_that_GAINED_an_opponent_knob(tmp_path):
    """The mirror image: the env leaking into an A/B cell."""
    spec = L.cell_by_name("B_LOW")
    d = _build_full_cell(tmp_path, spec, z_target=0.0)
    man = json.loads((d / "manifest.json").read_text())
    man["config"]["opp_leaf_cfg"]["invasion_alpha"] = 0.09
    man["config"]["opp_leaf_cfg"]["invasion_alpha_cap"] = 11.0
    (d / "manifest.json").write_text(json.dumps(man))
    gates, _ = _gates_on_disk(d, spec)
    assert gates.results["G-INVASION"]["ok"] is False


def test_G_INVASION_catches_a_C_candidate_that_INHERITED_the_env(tmp_path):
    """⛔ The explicit-zero failure mode: a C candidate carrying alpha as well as
    gamma is 'B AND C', not 'C'."""
    spec = L.cell_by_name("C_HIGH")
    d = _build_full_cell(tmp_path, spec, z_target=0.0)
    man = json.loads((d / "manifest.json").read_text())
    man["config"]["cand_leaf_cfg"]["invasion_alpha"] = 0.09
    man["config"]["champion"]["leaf_cfg"]["invasion_alpha"] = 0.09
    (d / "manifest.json").write_text(json.dumps(man))
    gates, _ = _gates_on_disk(d, spec)
    assert gates.results["G-INVASION"]["ok"] is False


def test_G_CAPFWD_checks_the_OPPONENT_side_too(tmp_path):
    """⭐ ROUND 2's EXTENSION. The C cells' opponent is the only reference leaf in
    this program's history to carry a nonzero alpha — and it carries a cap with
    it. An opponent with a cap and no alpha runs a leaf the manifest does not
    describe (leaf_config_rs drops the cap silently)."""
    spec = L.cell_by_name("C_LOW")
    d = _build_full_cell(tmp_path, spec, z_target=0.0)
    man = json.loads((d / "manifest.json").read_text())
    man["config"]["opp_leaf_cfg"]["invasion_alpha"] = 0.0    # cap survives, alpha gone
    (d / "manifest.json").write_text(json.dumps(man))
    gates, _ = _gates_on_disk(d, spec)
    assert gates.results["G-CAPFWD"]["ok"] is False


def test_G_CAPFWD_still_checks_the_candidate_side(tmp_path):
    spec = L.cell_by_name("A_HIGH")
    d = _build_full_cell(tmp_path, spec, z_target=0.0)
    man = json.loads((d / "manifest.json").read_text())
    man["config"]["champion"]["leaf_cfg"]["invasion_alpha_cap"] = 11.0  # no alpha
    (d / "manifest.json").write_text(json.dumps(man))
    gates, _ = _gates_on_disk(d, spec)
    assert gates.results["G-CAPFWD"]["ok"] is False


def test_singlevar_fails_on_an_EXTRA_differing_key(tmp_path):
    spec = L.cell_by_name("A_LOW")
    d = _build_full_cell(tmp_path, spec, z_target=0.0)
    man = json.loads((d / "manifest.json").read_text())
    man["config"]["cand_leaf_cfg"]["invasion_gamma"] = 0.5
    (d / "manifest.json").write_text(json.dumps(man))
    gates, _ = _gates_on_disk(d, spec)
    assert gates.results["G-SINGLEVAR"]["ok"] is False


def test_singlevar_fails_when_the_EXPECTED_key_is_identical_on_both_sides(tmp_path):
    """⭐ THE OTHER DIRECTION, and the one a naive subset check would miss: the
    cell's own knob never reached the leaf, so the two sides are identical and the
    cell silently measures NOTHING."""
    spec = L.cell_by_name("A_LOW")
    d = _build_full_cell(tmp_path, spec, z_target=0.0)
    man = json.loads((d / "manifest.json").read_text())
    man["config"]["opp_leaf_cfg"]["invasion_beta"] = spec.weight
    (d / "manifest.json").write_text(json.dumps(man))
    gates, _ = _gates_on_disk(d, spec)
    assert gates.results["G-SINGLEVAR"]["ok"] is False


def test_singlevar_fails_when_a_search_knob_differs_across_the_sides(tmp_path):
    spec = L.cell_by_name("B_HIGH")
    d = _build_full_cell(tmp_path, spec, z_target=0.0)
    man = json.loads((d / "manifest.json").read_text())
    man["config"]["opponent"]["champ_cfg"]["c_puct"] = 9.9
    (d / "manifest.json").write_text(json.dumps(man))
    gates, _ = _gates_on_disk(d, spec)
    assert gates.results["G-SINGLEVAR"]["ok"] is False


def test_tiearb_passes_on_a_healthy_archive_and_catches_both_armed_shapes(tmp_path):
    """Round 1's freeze-time correction, carried: a healthy manifest emits a
    TERMINAL `config.champion.tiearb_enabled = false`, so (b) must scan CONTAINER
    segments only, and (a2) checks the newly-exempted terminals."""
    spec = L.cell_by_name("A_LOW")
    d = _build_full_cell(tmp_path, spec, z_target=0.0)
    man = json.loads((d / "manifest.json").read_text())
    assert man["config"]["champion"]["tiearb_enabled"] is False   # the real shape
    gates, _ = _gates_on_disk(d, spec)
    assert gates.results["G-TIEARB"]["ok"] is True

    man["config"]["champion"]["tiearb_enabled"] = True
    (d / "manifest.json").write_text(json.dumps(man))
    gates, _ = _gates_on_disk(d, spec)
    assert gates.results["G-TIEARB"]["ok"] is False

    man["config"]["champion"]["tiearb_enabled"] = False
    man["config"]["opp_tiearb"] = {"enabled": True, "B": 16}
    (d / "manifest.json").write_text(json.dumps(man))
    gates, _ = _gates_on_disk(d, spec)
    assert gates.results["G-TIEARB"]["ok"] is False


def test_G_WHEEL_SAME_fails_on_a_rebuilt_wheel(tmp_path):
    spec = L.cell_by_name("A_LOW")
    d = _build_full_cell(tmp_path, spec, z_target=0.0)
    man = json.loads((d / "manifest.json").read_text())
    man["carc_rs_binary_sha"] = "0123456789abcdef"
    (d / "manifest.json").write_text(json.dumps(man))
    gates, _ = _gates_on_disk(d, spec)
    assert gates.results["G-WHEEL-SAME"]["ok"] is False
    assert "RE-OWES AN IDENT CELL" in gates.results["G-WHEEL-SAME"]["note"]


def test_a_failed_subdirectory_record_is_never_counted_as_a_completion(tmp_path):
    """⚠️ The harness writes FAILURE records into `<cell>/failed/` using the SAME
    `seed*_a*.json` pattern. A recursive glob would count them as completions —
    inflating `n_common`, MOVING THE MARGIN, and turning a broken cell into a
    healthy-looking one."""
    spec = L.cell_by_name("C_MID")
    d = _build_full_cell(tmp_path, spec, z_target=0.0)
    before = A.Cell(spec, d)
    (d / "failed").mkdir()
    poison = spec.seed_end + 1
    for a in (0, 1):
        (d / "failed" / f"seed{poison:012d}_a{a}.json").write_text(json.dumps(
            {"seed": poison, "a_seat": a, "diff": 999.0,
             "won_by_champ": True, "drew": False}))
    after = A.Cell(spec, d)
    assert len(after.records) == len(before.records) == spec.n_games
    assert poison not in L.per_deck_margins(after.records)
    gates, _ = _gates_on_disk(d, spec)
    assert gates.failed() == [], gates.failed()


def test_recon_voids_but_never_moves_the_number(tmp_path):
    """READ_RULE §3 `RECON`: the recomputation is a WITNESS, never a branch input
    — it can only void, never move, the number."""
    spec = L.cell_by_name("B_LOW")
    d = _build_full_cell(tmp_path, spec, z_target=0.5)
    summ = json.loads((d / "summary.json").read_text())
    summ["paired_z"] += 0.01
    (d / "summary.json").write_text(json.dumps(summ))
    gates, stats = _gates_on_disk(d, spec)
    assert gates.results["RECON"]["ok"] is False
    assert stats["z"] == pytest.approx(summ["paired_z"]), "RECON MOVED the number"


def test_recon_absorbs_a_summation_order_difference_and_nothing_larger(tmp_path):
    spec = L.cell_by_name("B_LOW")
    d = _build_full_cell(tmp_path, spec, z_target=0.5)
    summ = json.loads((d / "summary.json").read_text())
    summ["paired_mean_margin"] *= (1 + 1e-9)
    (d / "summary.json").write_text(json.dumps(summ))
    gates, _ = _gates_on_disk(d, spec)
    assert gates.results["RECON"]["ok"] is True


# ═══════════════════════════════════════════════════════════════════════════ #
# 17. ABSENT IS FAIL — the sharp form                                         #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_absent_is_fail_for_every_gate_on_an_empty_archive():
    """READ_RULE §3.1 question 4. Not one gate may pass with no data. This caught
    three vacuous passes in round 1 (`G-INVASION`, `G-CAPFWD`, `G-TIEARB`), each a
    'nothing bad was found' predicate that is trivially true of nothing."""
    empty = A.Cell(L.cell_by_name("C_MID"), PREP / "__nonexistent__")
    g, _ = A.run_gates(empty, pinned_src_rev=None, blind_commit=None, wheel_probe=None)
    passed = [r["id"] for r in g.results.values() if r["ok"]]
    assert passed == [], f"gates passed with NO data: {passed}"


def test_every_gate_id_in_read_rule_is_implemented():
    empty = A.Cell(L.cell_by_name("A_LOW"), PREP / "__nonexistent__")
    g, _ = A.run_gates(empty, pinned_src_rev=None, blind_commit=None, wheel_probe=None)
    assert set(L.GATE_IDS) == set(g.results)


#: Each gate's OWN witness address(es) in the emitted manifest/summary.
_ABSENT_PROBES = {
    "G-BAND": ["config.band_seed_start", "config.seed_start"],
    "G-SINGLEVAR": ["config.opponent.champ_cfg.c_puct"],
    "G-LEAF": ["config.opp_leaf_hash", "config.opponent.leaf_hash"],
    "G-INVASION": ["config.champion.leaf_cfg"],
    "G-CAPFWD": ["config.champion.leaf_cfg"],
    "G-WHEEL": ["carc_rs_build", "config.backend.carc_rs_build"],
    "G-WHEEL-SAME": ["carc_rs_binary_sha", "config.backend.carc_rs_binary_sha"],
    "G-RULES": ["rules_profile.r9_env_ok", "config.rules_profile.r9_env_ok"],
    "G-BACKEND": ["config.backend.name"],
    "G-BUDGET": ["config.champion.k_dets"],
    "G-EXACT": ["config.endgame.exact_k"],
    "G-REV": ["config.code_rev", "code_rev"],
    "G-BLIND": ["BLIND_COMMIT", "config.stamps.BLIND_COMMIT"],
    "G-N": ["n"],
    "G-SAT": ["winrate"],
    "RECON": ["paired_mean_margin"],
}


def _drop_address(doc, dotted: str) -> None:
    cur = doc
    for part in dotted.split(".")[:-1]:
        if not isinstance(cur, dict) or part not in cur:
            return
        cur = cur[part]
    if isinstance(cur, dict):
        cur.pop(dotted.split(".")[-1], None)


@pytest.mark.parametrize("gid", sorted(_ABSENT_PROBES))
def test_absent_is_fail_against_an_otherwise_healthy_archive(tmp_path, gid):
    """READ_RULE §3.1 question 4, driven the SHARP way: start from an archive that
    passes EVERY gate, remove ONE gate's own witness, and require exactly that
    gate to fail. The empty-archive form cannot make this distinction — a gate that
    failed unconditionally would satisfy it just as well."""
    spec = L.cell_by_name("C_MID")
    d = _build_full_cell(tmp_path, spec, z_target=0.0)
    man = json.loads((d / "manifest.json").read_text())
    summ = json.loads((d / "summary.json").read_text())
    for addr in _ABSENT_PROBES[gid]:
        _drop_address(man, addr)
        _drop_address(man.get("config", {}), addr)
        _drop_address(summ, addr)
    (d / "manifest.json").write_text(json.dumps(man))
    (d / "summary.json").write_text(json.dumps(summ))
    gates, _ = _gates_on_disk(d, spec)
    assert gates.results[gid]["ok"] is False, (
        f"{gid} survived the removal of {_ABSENT_PROBES[gid]} — ABSENT became a "
        "skip or a permissive default")


# ═══════════════════════════════════════════════════════════════════════════ #
# 18. THE ADJUDICATOR END TO END                                              #
# ═══════════════════════════════════════════════════════════════════════════ #
def _stub_externals(monkeypatch, blind, pinned, probe):
    monkeypatch.setattr(A, "_read_text",
                        lambda p: pinned if p.name == "PINNED_SRC_REV" else blind)
    monkeypatch.setattr(A, "_read_json",
                        lambda p: probe if p.name == L.WHEEL_PROBE_FILENAME
                        else (json.loads(p.read_text()) if p.exists() else None))
    monkeypatch.setattr(A, "wheel_ancestry_facts",
                        lambda *a, **k: _healthy_wheel_ancestry())
    monkeypatch.setattr(A, "blind_facts", lambda *a, **k: _healthy_blind_proof(blind))
    monkeypatch.setattr(A, "src_clean_facts", lambda *a, **k: _healthy_src_clean())


def test_a_failed_G_WHEEL_SAME_voids_ALL_SEVEN_cells_end_to_end(tmp_path, monkeypatch):
    """⭐ READ_RULE §3.4, THROUGH THE ADJUDICATOR rather than through the branch
    arithmetic alone. Round 2 carries no IDENT cell; it INHERITS round 1's, and the
    inheritance is valid only while the wheel that proved it is the wheel that
    plays. A wheel move must void the ROUND, not one archive — and here it is
    broken on ONE cell only, to prove the round-wide propagation."""
    blind = pinned = "c" * 40
    _stub_externals(monkeypatch, blind, pinned, _healthy_probe())

    for spec in L.CELLS:
        _build_full_cell(tmp_path, spec, z_target=0.0, blind=blind, pinned=pinned)
    clean = A.adjudicate(tmp_path)
    assert clean["wheel_same"]["ok"] is True, (
        "the control arm must be clean, else the assertion below proves nothing")
    assert clean["round_branch"] == "FAMILY-PARKS"
    assert all(c["branch"] != "U-UNREADABLE" for c in clean["cells"].values())

    # …now break the wheel fingerprint on ONE cell only.
    victim = tmp_path / L.cell_by_name("B_HIGH").out_subdir / "manifest.json"
    man = json.loads(victim.read_text())
    man["carc_rs_binary_sha"] = "0123456789abcdef"
    victim.write_text(json.dumps(man))

    broken = A.adjudicate(tmp_path)
    assert broken["wheel_same"]["ok"] is False
    assert broken["round_branch"] == "U-UNREADABLE"
    for name, cell in broken["cells"].items():
        assert cell["gates"]["G-WHEEL-SAME"]["ok"] is False, name
        assert cell["branch"] == "U-UNREADABLE", (
            f"{name} was read past a wheel move (READ_RULE §3.4)")


def test_the_adjudicator_reads_each_cell_against_its_OWN_BOXS_provenance(tmp_path,
                                                                        monkeypatch):
    """⭐ §6.5(iv). Each box writes its own PINNED_SRC_REV / SRC_CLEAN /
    BLIND_PROOF into ITS OWN checkout, which the local adjudicator cannot see —
    so each publishes to <out-root>/_provenance/<role>/ and every cell is gated
    against its own box's copy. Here the LAPTOP's SRC_CLEAN is made dirty and ONLY
    the laptop's cells may void."""
    blind = pinned = "a" * 40
    monkeypatch.setattr(A, "wheel_ancestry_facts",
                        lambda *a, **k: _healthy_wheel_ancestry())
    monkeypatch.setattr(A, "blind_facts", lambda *a, **k: _healthy_blind_proof(blind))

    for spec in L.CELLS:
        _build_full_cell(tmp_path, spec, z_target=0.0, blind=blind, pinned=pinned)
    for role in L.BOX_ROLES:
        d = tmp_path / L.provenance_subdir(role)
        d.mkdir(parents=True, exist_ok=True)
        (d / "PINNED_SRC_REV").write_text(pinned)
        (d / "BLIND_COMMIT").write_text(blind)
        (d / L.WHEEL_PROBE_FILENAME).write_text(json.dumps(_healthy_probe()))
        rows = [{"boundary": "pre-flight", "src_clean": True}] + [
            {"boundary": f"{c.name}-after-seal", "src_clean": True}
            for c in L.cells_of_box(role)]
        _write_src_clean(d / "SRC_CLEAN.jsonl", rows)

    rep = A.adjudicate(tmp_path)
    assert all(rep["provenance"][r]["is_per_box"] for r in L.BOX_ROLES)
    assert rep["cross_box_rev_ok"] is True
    assert all(c["gates"]["G-REV"]["ok"] for c in rep["cells"].values()), "control not clean"

    # ...now dirty ONLY the laptop's SRC_CLEAN
    d = tmp_path / L.provenance_subdir("laptop")
    rows = [{"boundary": "pre-flight", "src_clean": True}] + [
        {"boundary": f"{c.name}-after-seal", "src_clean": False}
        for c in L.cells_of_box("laptop")]
    _write_src_clean(d / "SRC_CLEAN.jsonl", rows)
    rep2 = A.adjudicate(tmp_path)
    for name, c in rep2["cells"].items():
        want = (L.cell_by_name(name).box == "local")
        assert c["gates"]["G-REV"]["ok"] is want, (
            f"{name}: G-REV should be {want} — a box's dirt must void ITS OWN cells only")


def test_a_cross_box_rev_disagreement_voids_G_REV_everywhere(tmp_path, monkeypatch):
    """⭐ THE CONJUNCT THAT MAKES SEVEN CELLS ONE ROUND RATHER THAN TWO. The laptop
    cannot reach GitHub, so its tree is bundle-synced; this is the check that the
    sync actually happened. Without it the laptop could run stale code and the
    round would be mixed-rev ACROSS MACHINES — the track_d2_prep defect with an
    extra machine."""
    blind = "a" * 40
    monkeypatch.setattr(A, "wheel_ancestry_facts",
                        lambda *a, **k: _healthy_wheel_ancestry())
    monkeypatch.setattr(A, "blind_facts", lambda *a, **k: _healthy_blind_proof(blind))
    revs = {"local": "a" * 40, "laptop": "b" * 40}
    for spec in L.CELLS:
        _build_full_cell(tmp_path, spec, z_target=0.0, blind=blind,
                         pinned=revs[spec.box])
    for role in L.BOX_ROLES:
        d = tmp_path / L.provenance_subdir(role)
        d.mkdir(parents=True, exist_ok=True)
        (d / "PINNED_SRC_REV").write_text(revs[role])
        (d / "BLIND_COMMIT").write_text(blind)
        (d / L.WHEEL_PROBE_FILENAME).write_text(json.dumps(_healthy_probe()))
        _write_src_clean(d / "SRC_CLEAN.jsonl",
                         [{"boundary": "pre-flight", "src_clean": True}] +
                         [{"boundary": f"{c.name}-after-seal", "src_clean": True}
                          for c in L.cells_of_box(role)])
    rep = A.adjudicate(tmp_path)
    assert rep["cross_box_rev_ok"] is False
    for name, c in rep["cells"].items():
        assert c["gates"]["G-REV"]["ok"] is False, name
        assert "CROSS-BOX REV DISAGREEMENT" in c["gates"]["G-REV"]["note"]
        assert c["branch"] == "U-UNREADABLE", name


def test_the_adjudicator_computes_the_contrasts_and_the_noise_check(tmp_path, monkeypatch):
    """§4.5 and §4.7 are MANDATORY OUTPUT, so they must exist on the report even
    when nothing fires — and the contrast must reflect the cells' real numbers."""
    blind = pinned = "d" * 40
    _stub_externals(monkeypatch, blind, pinned, _healthy_probe())
    targets = {"A_LOW": 0.0, "A_HIGH": 1.5, "B_LOW": 0.0, "B_HIGH": 0.0,
               "C_LOW": 0.0, "C_MID": 0.0, "C_HIGH": 0.0}
    for spec in L.CELLS:
        _build_full_cell(tmp_path, spec, z_target=targets[spec.name],
                         blind=blind, pinned=pinned)
    rep = A.adjudicate(tmp_path)
    assert set(rep["contrasts"]) == set(L.SHAPES)
    a = rep["contrasts"]["A"]
    assert a["readable"] is True
    lo = rep["cells"]["A_LOW"]["stats"]
    hi = rep["cells"]["A_HIGH"]["stats"]
    assert a["delta"] == pytest.approx(hi["D"] - lo["D"])
    assert a["se"] == pytest.approx(math.sqrt(hi["se"] ** 2 + lo["se"] ** 2))
    assert rep["noise_signature"]["applicable"] is True
    assert rep["cells"]["A_HIGH"]["branch"] == "BRACKET"
    assert rep["round_branch"] == "BRACKET-CONTINUE"


def test_the_render_prints_every_mandatory_section(tmp_path, monkeypatch):
    """READ_RULE §4.3 lists eleven mandatory items. A readout that silently drops
    one is a readout that can narrate past a limit the pair stated before game 1."""
    blind = pinned = "e" * 40
    _stub_externals(monkeypatch, blind, pinned, _healthy_probe())
    for spec in L.CELLS:
        _build_full_cell(tmp_path, spec, z_target=0.0, blind=blind, pinned=pinned)
    out = A.render(A.adjudicate(tmp_path))
    for token in ("THE INHERITED IDENT", "§4.3(1) PER CELL",
                  "LOW-vs-HIGH CONTRAST", "DESCRIPTIVE OVERLAY ONLY",
                  "THE LADDER RULES", "noise-signature", "§4.3(4) POWER",
                  "COST MULTIPLIER", "THE FROZEN INPUTS", "THE LADDER AS RUN",
                  "SHAPE C'S OPPONENT", "WHAT NO BRANCH DOES", "THE STATED PRIOR",
                  # ⭐ §4.3 item 12 — the two-box block
                  "THE TWO-BOX SPLIT", "ONE CODE REV ACROSS BOTH BOXES",
                  "ASSUMED, NOT MEASURED"):
        assert token in out, f"the readout omits {token!r}"
    for role in L.BOX_ROLES:
        assert role in out
    for c in L.CELLS:
        assert f"box={c.box}" in out
    for c in L.CELLS:
        assert c.cand_leaf_hash in out and c.opp_leaf_hash in out, c.name
    for gid in L.GATE_IDS:
        assert gid in out, gid


def test_the_render_labels_the_C_cells_cost_ratio_as_gamma_vs_alpha(tmp_path, monkeypatch):
    """§4.3(6) — on a C cell BOTH sides pay invasion arithmetic, so the ratio is
    NOT term-vs-plain and must not be presented as if it were."""
    blind = pinned = "f" * 40
    _stub_externals(monkeypatch, blind, pinned, _healthy_probe())
    for spec in L.CELLS:
        _build_full_cell(tmp_path, spec, z_target=0.0, blind=blind, pinned=pinned)
    out = A.render(A.adjudicate(tmp_path))
    assert "gamma-vs-alpha" in out


def test_the_render_prints_the_defence_reading_on_every_C_cell(tmp_path, monkeypatch):
    blind = pinned = "0" * 40
    _stub_externals(monkeypatch, blind, pinned, _healthy_probe())
    for spec in L.CELLS:
        _build_full_cell(tmp_path, spec, z_target=0.0, blind=blind, pinned=pinned)
    out = A.render(A.adjudicate(tmp_path))
    assert out.count("§4.6 DEFENCE READING:") == 3


# ═══════════════════════════════════════════════════════════════════════════ #
# 19. §4.6 — C READS DEFENCE                                                  #
# ═══════════════════════════════════════════════════════════════════════════ #
@pytest.mark.parametrize("branch", ["PROMOTE", "BRACKET", "REVERSED", "NULL"])
def test_every_C_branch_carries_the_defence_caveat_or_its_own_mechanism(branch):
    txt = L.c_reading(branch, 2.5)
    assert txt and txt != "unrecognised branch"
    if branch in ("PROMOTE", "BRACKET"):
        assert "NEVER PROMOTES PAST ITS OWN FAMILY" in txt
        assert "production H2H" in txt
    if branch == "REVERSED":
        assert "NORMALISATION" in txt.upper()
        assert "UN-NORMALISED" in txt.upper()
    if branch == "NULL":
        assert "BOUND, not a zero" in txt
        assert "INFORMATIVE" in txt.upper()


def test_the_C_opponent_note_says_it_is_not_the_champion():
    assert "NOT THE CHAMPION OF RECORD" in L.C_OPPONENT_NOTE
    assert L.SHAPE_B_LEAF_HASH in L.C_OPPONENT_NOTE
    assert "DEFENCE PAYS AGAINST" in L.C_OPPONENT_NOTE


def test_C_never_licenses_the_adoption_chain():
    t = L.C_NEVER_PROMOTES_ALONE
    assert "does NOT enter the four-link adoption chain" in t
    assert "PRODUCTION.yaml" in t
    assert "C-vs-E4" in t


# ═══════════════════════════════════════════════════════════════════════════ #
# 20. THE PAIR ITSELF                                                         #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_pair_files_all_exist():
    for f in ("DESIGN.md", "READ_RULE.md", "run_cells.sh", "analyze_screen.py",
              "screen_lib.py", "BAND_CLAIM.json", "BLIND_COMMIT", "WORKERS.conf",
              "DEVIATIONS.md"):
        assert (PREP / f).is_file(), f"missing {f}"
    for c in L.CELLS:
        assert (PREP / c.leaf_json).is_file(), c.leaf_json


def test_band_claimed_sentinel_is_NOT_present_at_freeze():
    """⛔ THE INTERLOCK. `BAND_CLAIMED` is deliberately NOT created at freeze, and
    the launcher refuses every real cell without it."""
    assert not (PREP / "BAND_CLAIMED").exists()


def test_the_executor_owed_artifacts_are_NOT_present_at_freeze():
    """⛔ `PINNED_SRC_REV` must be written at LAUNCH HEAD by the executor, and a
    committed one would be a lie about what ran. `WHEEL_PROBE.json` /
    `BLIND_PROOF.json` / `SRC_CLEAN.jsonl` are likewise launch artifacts."""
    for f in ("PINNED_SRC_REV", "WHEEL_PROBE.json", "BLIND_PROOF.json",
              "SRC_CLEAN.jsonl", "RUN_LIVE.json"):
        assert not (PREP / f).exists(), f"{f} must be executor-owed, not frozen"


def test_band_claim_row_names_this_band_and_parses_as_eight_csv_fields():
    import csv
    import io
    claim = json.loads((PREP / "BAND_CLAIM.json").read_text())
    assert claim["band_seed_start"] == L.BAND
    row = next(csv.reader(io.StringIO(claim["_csv_row"])))
    assert len(row) == 8, f"row has {len(row)} fields"
    assert row[0] == str(L.BAND)
    assert row[2] == "claim" and row[3] == "claimed"


def test_the_band_claim_allocation_matches_the_library():
    claim = json.loads((PREP / "BAND_CLAIM.json").read_text())
    alloc = claim["cell_allocation"]
    assert set(alloc) == {c.name for c in L.CELLS}
    for c in L.CELLS:
        a = alloc[c.name]
        assert a["seeds"] == f"{c.seed_start}..{c.seed_end}"
        assert a["decks"] == c.n_decks and a["games"] == c.n_games
        assert a["cand_leaf"] == c.cand_leaf_hash
        assert a["opp_leaf"] == c.opp_leaf_hash


def test_design_and_read_rule_carry_the_frozen_numbers():
    design = (PREP / "DESIGN.md").read_text()
    for c in L.CELLS:
        assert str(c.weight) in design, f"{c.knob}={c.weight} is not stated in DESIGN.md"
        assert c.cand_leaf_hash in design, c.name
    assert str(L.FROZEN_DERIVATION["G_sibling_p90_minus_p10"]) in design
    assert str(L.BAND) in design
    assert L.R1_WHEEL_BINARY_SHA in design
    assert L.SHAPE_B_LEAF_HASH in design


def test_read_rule_names_every_gate_it_claims_to():
    rr = (PREP / "READ_RULE.md").read_text()
    for gid in L.GATE_IDS:
        assert gid in rr, f"{gid} is implemented but not named in READ_RULE.md"
    for c in L.CELLS:
        assert c.cand_leaf_hash in rr, f"{c.name}'s pinned candidate hash is not in READ_RULE"
    assert L.SHAPE_B_LEAF_HASH in rr


def test_the_pair_states_the_two_box_assignment_in_both_halves():
    """⭐ The assignment is a PREREG fact, so it has to be in the pair, not only in
    the launcher."""
    design = (PREP / "DESIGN.md").read_text()
    rr = (PREP / "READ_RULE.md").read_text()
    assert "6.5" in design and "TWO BOXES" in design
    assert "G-HOST" in rr
    for c in L.CELLS:
        # every cell's box appears in the DESIGN §3 table
        assert c.box in design
    for role in L.BOX_ROLES:
        assert L.BOXES[role]["share_mount"] in design, role
    assert "get round 2 on both local and laptop" in design
    # and both halves must state the within-box property
    assert "WITHIN ONE BOX" in design.upper()
    assert "WITHIN ONE BOX" in rr.upper()


def test_the_band_claim_records_the_two_box_execution():
    claim = json.loads((PREP / "BAND_CLAIM.json").read_text())
    assert "two_box_execution" in claim
    t = claim["two_box_execution"]
    assert "FROZEN IN THE PREREG" in t
    assert "SHAPES ARE ASSIGNED WHOLE" in t
    assert "SAME WHEEL FILE" in t
    for c in L.CELLS:
        assert claim["cell_allocation"][c.name]["box"] == c.box
    assert "TWO-BOX EXECUTION" in claim["_csv_row"]


def test_read_rule_names_every_round_branch_the_library_can_emit():
    rr = (PREP / "READ_RULE.md").read_text()
    for label in ("U-UNREADABLE", "PROMOTE-<shape>", "DEFENDS-C",
                  "BRACKET-CONTINUE", "REVERSED-<shape>", "FAMILY-PARKS"):
        assert label in rr, label


def test_the_pair_states_the_power_caveat_in_both_halves():
    """⭐ §2.2 is the round's most important sentence, and a readout that misses it
    can narrate a FAMILY-PARKS as a refutation of round 1."""
    for path in (PREP / "DESIGN.md", PREP / "READ_RULE.md"):
        txt = path.read_text()
        assert "POWERED TO DETECT SCALING" in txt.upper(), path.name
    rr = (PREP / "READ_RULE.md").read_text()
    assert "does not refute round 1" in rr.lower()
    # §5's list must carry the same fence, so a readout that only reads the list
    # still cannot narrate a FAMILY-PARKS as a refutation
    joined = " ".join(L.NO_BRANCH_DOES).lower()
    assert "family-parks" in joined and "refutation" in joined


def test_the_cross_band_fence_is_stated_in_the_library_and_the_pair():
    assert "NEVER pooled" in L.R1_OVERLAY_RULE
    assert "CL-068" in L.R1_OVERLAY_RULE
    rr = (PREP / "READ_RULE.md").read_text()
    assert "DESCRIPTIVE OVERLAY" in rr
    assert "CL-068" in rr


def test_the_endpoint_and_interior_rules_are_stated_before_any_number():
    assert "NOT BRACKETED" in L.AB_ENDPOINT_RULE
    assert "ENDPOINT" in L.AB_ENDPOINT_RULE
    assert "INTERIOR" in L.C_INTERIOR_RULE
    assert "NOISE SIGNATURE" in L.C_INTERIOR_RULE


def test_blind_commit_is_pending_or_a_real_sha():
    v = (PREP / "BLIND_COMMIT").read_text().strip()
    assert v == "PENDING" or L.is_hex40(v), f"BLIND_COMMIT is {v!r}"


def test_rev_matching_is_a_prefix_rule_not_string_equality():
    full = "2eca4a92fb0012345678901234567890abcdef12"
    assert L.rev_matches("2eca4a92", full)[0]
    assert L.rev_matches("2ECA4A92", full)[0]
    assert not L.rev_matches("deadbee", full)[0]
    assert not L.rev_matches("2eca", full)[0]
    assert not L.rev_matches(None, full)[0]
    assert not L.rev_matches("2eca4a92", None)[0]


@pytest.mark.parametrize("code_rev", ["dbf78ed8-dirty", "2eca4a92-dirty"])
def test_whole_tree_dirty_marker_does_not_fail_the_rev_match(code_rev):
    """Round 1's amendment round 2, carried: `run_manifest.code_rev()` computes
    dirtiness over the WHOLE TREE and the main tree is perpetually dirty with
    measurement artifacts. The FATAL, code-path-scoped verdict is SRC_CLEAN's."""
    full = code_rev.split("-")[0] + "0" * (40 - len(code_rev.split("-")[0]))
    ok, why = L.rev_matches(code_rev, full)
    assert ok is True, why
    assert "INFORMATIONAL" in why


def test_a_wrong_sha_still_fails_even_when_only_the_marker_differs():
    full = "dbf78ed8" + "0" * 32
    assert not L.rev_matches("deadbeef-dirty", full)[0]
    assert not L.rev_matches("dbf7-dirty", full)[0]
    assert not L.rev_matches("dbf78ed8-dirty", None)[0]


# ---- SRC_CLEAN / BLIND / WHEEL-ancestry: the conjuncts round 1 amended in ----
def _write_src_clean(p: Path, rows) -> Path:
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


def test_src_clean_facts_requires_clean_at_every_boundary_and_one_per_cell(tmp_path):
    names = ["pre-flight"] + [f"{c.name}-after-seal" for c in L.CELLS]
    cells = [c.name for c in L.CELLS]
    good = _write_src_clean(tmp_path / "a.jsonl",
                            [{"boundary": n, "src_clean": True} for n in names])
    assert A.src_clean_facts(good, cells)["ok"] is True
    rows = [{"boundary": n, "src_clean": (n != names[3])} for n in names]
    dirty = _write_src_clean(tmp_path / "b.jsonl", rows)
    out = A.src_clean_facts(dirty, cells)
    assert out["ok"] is False and out["dirty_boundaries"] == [names[3]]
    # a cell with no after-boundary
    rows2 = [{"boundary": "pre-flight", "src_clean": True}] + [
        {"boundary": f"{c}-after-seal", "src_clean": True} for c in cells[:-1]]
    p2 = _write_src_clean(tmp_path / "c.jsonl", rows2)
    out2 = A.src_clean_facts(p2, cells)
    assert out2["ok"] is False and out2["missing_after"] == [cells[-1]]


def test_src_clean_facts_absent_or_empty_is_fail(tmp_path):
    assert A.src_clean_facts(tmp_path / "nope.jsonl", ["A_LOW"])["ok"] is False
    empty = tmp_path / "e.jsonl"
    empty.write_text("")
    assert A.src_clean_facts(empty, ["A_LOW"])["ok"] is False
    bad = tmp_path / "f.jsonl"
    bad.write_text("{not json}\n")
    assert A.src_clean_facts(bad, ["A_LOW"])["ok"] is False


def test_src_clean_smoke_mode_relaxes_only_the_per_cell_requirement(tmp_path):
    """A smoke has ONE cell and no seal. ⛔ The CLEAN requirement does NOT relax."""
    rows = [{"boundary": "pre-flight", "src_clean": True},
            {"boundary": "smoke-after", "src_clean": True}]
    p = _write_src_clean(tmp_path / "g.jsonl", rows)
    assert A.src_clean_facts(p, [c.name for c in L.CELLS])["ok"] is False
    assert A.src_clean_facts(p, [L.SMOKE_CELL], smoke=True)["ok"] is True
    rows[1]["src_clean"] = False
    p2 = _write_src_clean(tmp_path / "h.jsonl", rows)
    assert A.src_clean_facts(p2, [L.SMOKE_CELL], smoke=True)["ok"] is False


@pytest.mark.parametrize("build,rev", [
    ("carc_rs-0.1.0+2eca4a92fb00+rustcunpinned", "2eca4a92fb00"),
    ("carc_rs-1.59963.20305+abcdef1234567890+rustc1.79", "abcdef1234567890"),
])
def test_wheel_ancestry_extracts_the_embedded_rev(build, rev, tmp_path):
    assert A.wheel_ancestry_facts(tmp_path, build)["rev"] == rev


@pytest.mark.parametrize("build", [None, "", "not-a-build-id", "carc_rs-0.1.0"])
def test_wheel_ancestry_fails_closed_without_an_embedded_rev(build, tmp_path):
    out = A.wheel_ancestry_facts(tmp_path, build)
    assert out["ok"] is False and out["rev"] is None


def test_blind_facts_rejects_a_pending_or_short_sha(tmp_path):
    for blind in (None, "", "PENDING", "abc123"):
        assert A.blind_facts(tmp_path, blind, None, tmp_path / "d.md",
                             tmp_path / "r.md")["ok"] is False


@pytest.mark.parametrize("drop", sorted(L.WHEEL_PROBE_REQUIRED_TRUE) + ["carc_rs_build"])
def test_the_wheel_probe_contract_fails_closed_on_every_field(drop):
    """⭐ A STALE WHEEL IS THE WORST FAILURE MODE THIS FAMILY HAS, and round 2 has
    NO weight-0 cell to trip on it. Every probe field is load-bearing — including
    the two round 2 added, `opp_side_forward_ok` and `wheel_is_round_1s`."""
    probe = _healthy_probe()
    assert L.wheel_probe_ok(probe)[0] is True
    probe.pop(drop)
    assert L.wheel_probe_ok(probe)[0] is False
    assert L.wheel_probe_ok(None)[0] is False
    assert L.wheel_probe_ok({})[0] is False


def test_the_probe_contract_gained_the_two_round_2_keys():
    r1 = _load("screen_lib_r1_for_probe",
               REPO / "measurement" / "invasion_screen_prep" / "screen_lib.py")
    assert set(r1.WHEEL_PROBE_REQUIRED_TRUE) < set(L.WHEEL_PROBE_REQUIRED_TRUE)
    assert "opp_side_forward_ok" in L.WHEEL_PROBE_REQUIRED_TRUE
    assert "wheel_is_round_1s" in L.WHEEL_PROBE_REQUIRED_TRUE


# ═══════════════════════════════════════════════════════════════════════════ #
# 21. THE LAUNCHER'S SMOKE LEG AND PER-CELL INTERLOCK                         #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_the_smoke_leg_writes_its_own_launch_artifacts():
    """⭐ Round 1's amendment-1 fix, carried. G-REV and G-BLIND are NOT in §3.5's
    allowed set, so both must PASS on the smoke — and the fix SUPPLIES THE WITNESS,
    it does not widen the allowed set."""
    src = (PREP / "run_cells.sh").read_text()
    smoke = src.split("run_smoke() {")[1].split("\n}\n")[0]
    assert 'rev-parse HEAD > "$DIR/$PINNED_SRC_REV_FILE"' in smoke
    assert "write_blind_proof" in smoke
    assert 'record_src_boundary "pre-flight"' in smoke
    assert "record_src_boundary" in smoke.split('record_src_boundary "pre-flight"')[1]


def test_the_smoke_leg_stamps_blind_commit_like_a_real_cell():
    """⭐ Round 1's amendment-2 fix, carried: the unstamped smoke failed G-BLIND on
    'stamp mismatch', and the fix is to make the SMOKE match the real cells."""
    src = (PREP / "run_cells.sh").read_text()
    smoke = src.split("run_smoke() {")[1].split("\n}\n")[0]
    m = re.search(r'build_argv "\$c" "\$SMOKE_GAMES".*?(\S+)\s*$', smoke, re.M)
    assert m, "could not find the smoke's build_argv call"
    assert m.group(1) == "with-stamp"


def test_build_argv_emits_the_blind_stamp_only_with_stamp():
    body = _argv_builders()
    assert '--stamp-key "BLIND_COMMIT=$(blind_commit_value)"' in body
    assert '--stamp-key "SCREEN_CELL=$c"' in body
    assert 'if [ "$stamp" = "with-stamp" ]' in body


def test_the_per_cell_interlock_runs_after_every_cell():
    """⭐ ROUND 2's SUCCESSOR TO ROUND 1's IDENT INTERLOCK (DESIGN §6.4). Round 1
    gated the whole round on ONE identity cell; round 2 has none and seven arms, so
    it re-checks the EMITTED leaves after EVERY cell. A wiring defect costs ONE
    cell (~20 core-h), not seven (~139)."""
    src = (PREP / "run_cells.sh").read_text()
    main = src.split("main() {")[1]
    assert "run_cell \"$c\"" in main
    assert "cell_precheck \"$c\"" in main
    # the pre-check must come AFTER the cell, in the same loop iteration
    assert main.index('run_cell "$c"') < main.index('cell_precheck "$c"')


def test_the_per_cell_interlock_is_statistics_blind():
    """⛔ It reads no bar and no branch. It cannot stop the round for a
    DISAPPOINTING result, only for a BROKEN one. (Round 1's IDENT pre-check DID
    read a statistic — an identity cell's whole content is that statistic. Round
    2's cells are arms, and a launcher that could halt an arm on its number would
    be peeking.)"""
    code = _heredoc("IEOF")
    for bar in ("PROMOTE_Z", "BRACKET_Z", "REVERSED_Z", "IDENT_ABS_Z_MAX",
                "branch_for_cell", "round_branch", "ident_z_ok"):
        assert bar not in code, f"the per-cell pre-check reads the bar {bar}"
    assert "leaf_gate" in code
    assert "wheel_is_r1s" in code
    assert "STATISTICS-BLIND" in code


def test_the_per_cell_interlock_reads_config_from_manifest_not_summary():
    """⛔ ROUND 1's DEVIATION IS-D1, IN ONE ASSERTION. Its precheck read the config
    block off summary.json — which carries none — got `{}`, and fail-closed voided
    a HEALTHY cell while a vacuous `{} == {}` hid the cause."""
    code = _heredoc("IEOF")
    assert 'json.load(open(mans[-1])).get("config"' in code
    assert 'json.load(open(sums[-1])).get("n_failed")' in code
    assert "IS-D1" in code


def test_the_per_cell_interlock_actually_runs_against_a_healthy_archive(tmp_path):
    """⭐ EXECUTE the heredoc, don't just read it — the round-1 precedent for this
    test found a real typo that would have aborted the round on first use."""
    spec = L.cell_by_name("C_MID")
    d = _build_full_cell(tmp_path, spec, z_target=0.0)
    code = _heredoc("IEOF")
    env = {**os.environ, "CARC_LIB": str(PREP / "screen_lib.py"),
           "CARC_CELL_OUT": str(d), "CARC_CELL": spec.name}
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS  leaf_gate" in r.stdout
    assert "PASS  wheel_is_round_1s" in r.stdout


def test_the_per_cell_interlock_stops_on_a_wrong_opponent(tmp_path):
    """The C-cell failure mode it exists to catch, executed."""
    spec = L.cell_by_name("C_LOW")
    d = _build_full_cell(tmp_path, spec, z_target=0.0)
    man = json.loads((d / "manifest.json").read_text())
    man["config"]["opp_leaf_hash"] = L.PROD_LEAF_HASH      # played the plain champion
    (d / "manifest.json").write_text(json.dumps(man))
    code = _heredoc("IEOF")
    env = {**os.environ, "CARC_LIB": str(PREP / "screen_lib.py"),
           "CARC_CELL_OUT": str(d), "CARC_CELL": spec.name}
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, env=env)
    assert r.returncode != 0
    assert "FAIL  leaf_gate" in r.stdout
    assert "STOPPING THE ROUND HERE" in r.stdout


# ═══════════════════════════════════════════════════════════════════════════ #
# 22. THE ADJUDICATOR'S CONTRACT                                              #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_selftest_exits_zero():
    """READ_RULE §7 — and it must be seeded from a REAL emitted manifest."""
    r = subprocess.run([sys.executable, str(PREP / "analyze_screen.py"), "--selftest"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "REAL emitted archive" in r.stdout
    assert "SELFTEST GREEN" in r.stdout


def test_selftest_fixture_is_a_real_emitted_archive_not_a_synthesis():
    """A synthesized fixture would let a gate be 'validated' against a manifest the
    DESIGN described rather than one the harness WROTE — the exact defect the
    h2h_22016_prep post-mortem raised, and the one that caught this round's own
    G-WHEEL-SAME (DESIGN §3.1a)."""
    man = json.loads((_FIXTURE_DIR / "manifest.json").read_text())
    assert man.get("config") and man.get("code_rev") and man.get("carc_rs_build")
    assert man["config"]["backend"]["name"] == "rust"
    assert man["rules_profile"]["name"] == "fixed_v1"
    assert len(list(_FIXTURE_DIR.glob("seed*_a*.json"))) >= 4
    # ⭐ and it is round 1's OWN wheel, which is why G-WHEEL-SAME is satisfiable on it
    assert man["carc_rs_binary_sha"] == L.R1_WHEEL_BINARY_SHA


def test_the_fixture_spec_is_not_a_round_2_cell():
    assert L.FIXTURE_SPEC.name not in L.CELL_NAMES
    assert L.FIXTURE_SPEC.seed_start < L.BAND


def test_adjudicator_never_writes_results_csv():
    """⛔ Close-out rows are a human act on the six-touch checklist."""
    src = (PREP / "analyze_screen.py").read_text()
    assert "results.csv" not in src.replace(
        "# ⛔ The adjudicator NEVER writes experiments/results.csv", "")
