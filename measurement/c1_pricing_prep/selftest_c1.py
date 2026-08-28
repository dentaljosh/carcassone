#!/usr/bin/env python3
"""C1 OUTCOME PRICING — the selftest. Pure python; no engine, no rust, no box.

Run before the freeze commit and again on every box after the bundle sync:

    .venv/bin/python -m pytest measurement/c1_pricing_prep/selftest_c1.py -q

§1 THE ARGPARSE CONTRACT — the PG-D7..D9 lesson (2026-08-28: three launcher
   bugs that a static check would have caught). `run_c1.sh` invokes a runner it
   does not own. Every flag it passes is extracted from the shell script and
   checked against the flags `continue_plies.py`'s parser actually declares,
   read by AST so nothing is imported and nothing is run.
§2 THE ARM-SLOT REMAP — the single most misreadable thing in this instrument.
§3 THE WORLD SPLIT — the cross-fit that de-biases the microgates' argmax.
§4 THE SIGN CONVENTION — hand fixtures at both seats.
§5 THE BRANCH TABLE + Holm.
§6 OUTCOME-BLINDNESS of the selector, asserted at code level.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CONT = REPO / "measurement" / "e4_continuation_20260828"
RUNNER = CONT / "continue_plies.py"
MICROGATES = REPO / "measurement" / "microgates_20260828" / "MICROGATES.json"
TARGETS = HERE / "targets_c1.jsonl"

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(CONT))


# --------------------------------------------------------------------------- #
# §1  the argparse contract                                                     #
# --------------------------------------------------------------------------- #
def _declared_flags(py: Path) -> set[str]:
    """Every `--flag` the file's argparse declares, by AST. No import, no exec."""
    tree = ast.parse(py.read_text())
    flags = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"):
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str) \
                        and a.value.startswith("--"):
                    flags.add(a.value)
    return flags


def _flags_passed_by(sh: Path, marker: str) -> set[str]:
    """The `--flags` the shell script passes in the invocation containing `marker`."""
    text = sh.read_text()
    i = text.index(marker)
    # the invocation runs until the first line that is not a backslash-continuation
    tail, out = text[i:], set()
    for line in tail.splitlines():
        out |= set(re.findall(r"(--[a-z0-9][a-z0-9-]*)", line))
        if not line.rstrip().endswith("\\"):
            break
    return out


def test_run_script_only_passes_flags_the_runner_declares():
    declared = _declared_flags(RUNNER)
    assert "--targets" in declared and "--units" in declared  # sanity on the AST
    passed = _flags_passed_by(HERE / "run_c1.sh", '"$RUNNER" \\')
    unknown = passed - declared
    assert not unknown, (f"run_c1.sh passes flags continue_plies.py does not "
                         f"declare: {sorted(unknown)}")


def test_run_script_passes_every_required_runner_flag():
    tree = ast.parse(RUNNER.read_text())
    required = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"
                and any(isinstance(k.value, ast.Constant) and k.value.value is True
                        for k in node.keywords if k.arg == "required")):
            for a in node.args:
                if isinstance(a, ast.Constant) and str(a.value).startswith("--"):
                    required.add(a.value)
    passed = _flags_passed_by(HERE / "run_c1.sh", '"$RUNNER" \\')
    assert required <= passed, f"run_c1.sh omits required flags: {sorted(required - passed)}"


@pytest.mark.parametrize("script,tool", [
    ("run_c1.sh", "continue_plies.py"),
])
def test_run_script_points_at_the_unmodified_runner(script, tool):
    assert RUNNER.exists()
    txt = (HERE / script).read_text()
    assert "e4_continuation_20260828/continue_plies.py" in txt
    # It must be reused, never copied: there is no local fork of the runner.
    assert not (HERE / tool).exists(), \
        "a local copy of the runner defeats the whole 'reuse, don't rebuild' point"


def test_our_own_entrypoints_parse_and_declare_what_the_docs_say():
    for f in ("build_c1_targets.py", "plan_c1.py", "preflight_c1.py",
              "adjudicate_c1.py", "exact_leg_c1.py"):
        ast.parse((HERE / f).read_text())          # syntactically valid
    assert {"--targets", "--out-dir", "--block", "--capacity", "--exclude"} \
        <= _declared_flags(HERE / "plan_c1.py")
    assert {"--units", "--targets", "--out"} <= _declared_flags(HERE / "adjudicate_c1.py")


def test_plan_and_run_agree_on_the_unit_file_name():
    """`plan_c1.py` writes units_<box>_<block>_<profile>.txt; run_c1.sh globs it."""
    plan = (HERE / "plan_c1.py").read_text()
    run = (HERE / "run_c1.sh").read_text()
    assert 'f"units_{b}_{args.block}_{prof}.txt"' in plan
    assert 'units_${BOX}_${BLOCK}${SUFFIX}_*.txt' in run


def test_the_smoke_block_label_cannot_be_swallowed_by_a_real_block_glob():
    """`units_local_base_*` must NOT match the smoke's own unit file."""
    smoke = (HERE / "smoke_c1.sh").read_text()
    assert "\nBLOCK=smoke\n" in smoke and '\nSUFFIX=""\n' in smoke
    names = [f"units_local_{b}_fixed_v1.txt" for b in ("base", "E1", "E2", "E3")]
    smoke_name = "units_local_smoke_fixed_v1.txt"
    import fnmatch
    for b in ("base", "E1", "E2", "E3"):
        assert not fnmatch.fnmatch(smoke_name, f"units_local_{b}_*.txt")
    for n in names:
        assert not fnmatch.fnmatch(n, "units_local_smoke_*.txt")


# --------------------------------------------------------------------------- #
# §2  the arm-slot remap                                                        #
# --------------------------------------------------------------------------- #
def _targets():
    if not TARGETS.exists():
        pytest.skip("targets_c1.jsonl not built yet")
    return [json.loads(l) for l in TARGETS.open()]


def test_arm_slots_carry_the_c1_and_champion_picks():
    for r in _targets():
        assert r["played_action"] == r["c1_action"]
        assert r["counterfactual_action"] == r["champ_action"]
        assert r["arm_map"] == {"arm_owner": "c1_rollout_argmax",
                                "arm_cf": "production_champion_pick"}


def test_no_agreeing_ply_is_in_the_run():
    for r in _targets():
        assert r["c1_action"] != r["champ_action"], \
            "an agreeing ply prices exactly zero and must never cost compute"


def test_targets_reproduce_the_microgates_picks_exactly():
    mg = {(p["game"], p["ply"]): p
          for p in json.loads(MICROGATES.read_text())["G2"]["plies"]}
    for r in _targets():
        p = mg[(r["game"], r["ply"])]
        assert r["c1_action"] == p["rollout_argmax"]
        assert r["champ_action"] == p["counterfactual_action"]
        assert r["owner_action"] == p["played_action"]
        gap = p["arm_values"][str(p["rollout_argmax"])] \
            - p["arm_values"][str(p["counterfactual_action"])]
        assert abs(r["insample_gap_pts"] - gap) < 1e-6
        assert gap >= -1e-9, "the rollout argmax cannot be below its own arm"


def test_every_target_carries_the_runner_schema():
    need = {"game", "profile", "stratum", "ply", "k", "phase", "actor",
            "played_action", "counterfactual_action", "n_plies", "ply_frac"}
    for r in _targets():
        assert need <= set(r)
        assert r["profile"] == "fixed_v1"     # one R9 import-latch group


# --------------------------------------------------------------------------- #
# §3  the world split — the cross-fit                                           #
# --------------------------------------------------------------------------- #
MICROGATES_WORLDS = set(range(16))       # microgates M_WORLDS = 16, indices 0..15
CONTINUATION_WORLDS = set(range(8))      # e4_continuation M_WORLDS = 8, 0..7


def test_every_world_this_instrument_draws_is_new():
    for r in _targets():
        used = set(range(r["world_lo_base"], r["world_hi_base"]))
        for e in r["extension_blocks"]:
            used |= set(range(e["world_lo"], e["world_hi"]))
        assert not (used & MICROGATES_WORLDS), \
            "an in-sample world would re-import the winner's curse"
        assert not (used & CONTINUATION_WORLDS)
        assert min(used) >= 16


def test_extension_blocks_do_not_overlap_the_base_or_each_other():
    for r in _targets():
        seen = set(range(r["world_lo_base"], r["world_hi_base"]))
        for e in r["extension_blocks"]:
            blk = set(range(e["world_lo"], e["world_hi"]))
            assert not (seen & blk), f"block {e['block']} overlaps earlier worlds"
            seen |= blk


def _code_only(src: str) -> str:
    """The file's EXECUTABLE text: comments and docstrings stripped.

    Prose about outcomes is not a read of an outcome — these gates are about what
    the code touches, so they must not be satisfiable (or breakable) by a comment.
    """
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                node.body.pop(0)
                if not node.body:
                    node.body.append(ast.Pass())
    return ast.unparse(ast.fix_missing_locations(tree))


def test_world_generator_is_arm_independent_and_index_separated():
    import continue_plies as CP
    assert CP.WORLD_SEED == 20260828       # inherited UNCHANGED; the split is by index
    fn = next(n for n in ast.walk(ast.parse(Path(CP.__file__).read_text()))
              if isinstance(n, ast.FunctionDef) and n.name == "world_rng")
    body = _code_only(ast.unparse(ast.Module(body=[fn], type_ignores=[])))
    assert "arm" not in body, "an arm term in world_rng would destroy the CRN pairing"
    a = CP.world_rng(12345, 40, 16).random()
    b = CP.world_rng(12345, 40, 17).random()
    c = CP.world_rng(12345, 40, 16).random()
    assert a == c and a != b


# --------------------------------------------------------------------------- #
# §4  the sign convention, by hand                                              #
# --------------------------------------------------------------------------- #
def _arm(margin, w=None):
    w = w or {k: 1 for k in ("root_repr_sha", "world_deck_sha", "world_deck_len",
                             "n_drawn_prefix", "n_legal_root",
                             "det_seed_base_at_root", "move_idx_at_root")}
    return {"status": "OK", "margin_p0_minus_p1": margin, "witness": w}


def test_positive_delta_means_the_c1_pick_scored_more_for_the_mover():
    import continue_plies as CP
    # seat 0: C1 arm ends +10, champion arm ends +4  ->  C1 better by 6
    assert CP.pair_price(_arm(10), _arm(4), 0)["delta_pts_mover"] == 6
    # seat 1: P0-P1 of -10 is BETTER for seat 1 than -4  ->  C1 better by 6
    assert CP.pair_price(_arm(-10), _arm(-4), 1)["delta_pts_mover"] == 6
    # and the losing direction
    assert CP.pair_price(_arm(4), _arm(10), 0)["delta_pts_mover"] == -6


def test_a_witness_mismatch_voids_and_never_prices():
    import continue_plies as CP
    bad = dict(_arm(4)["witness"])
    bad["world_deck_sha"] = 2
    out = CP.pair_price(_arm(10), _arm(4, bad), 0)
    assert out["status"] == "VOID" and "delta_pts_mover" not in out


# --------------------------------------------------------------------------- #
# §5  the branch table and Holm                                                 #
# --------------------------------------------------------------------------- #
def test_holm_is_holm():
    import adjudicate_c1 as A
    h = A.holm({"a": 0.001, "b": 0.04}, alpha=0.05)
    assert h["a"]["holm_threshold"] == pytest.approx(0.025)
    assert h["a"]["holm_reject"] is True
    assert h["b"]["holm_threshold"] == pytest.approx(0.05)
    assert h["b"]["holm_reject"] is True
    h2 = A.holm({"a": 0.03, "b": 0.04}, alpha=0.05)
    assert h2["a"]["holm_reject"] is False and h2["b"]["holm_reject"] is False


def test_two_sided_p_matches_the_familiar_z():
    import adjudicate_c1 as A
    assert A.two_sided_p(1.96) == pytest.approx(0.05, abs=2e-3)
    assert A.two_sided_p(0.0) == pytest.approx(1.0)


def test_prereg_bars_match_the_code():
    import adjudicate_c1 as A
    assert (A.ALPHA, A.SE_PRECISION_BAR_P2, A.VOID_WORLD_RATE) == (0.05, 1.2, 0.10)
    assert A.CO_PRIMARIES == ("P1_farm_capture", "P2_contested")
    design = (HERE / "DESIGN.md").read_text()
    for token in ("C1-PRICED-POSITIVE", "C1-NULL-BOUNDED", "C1-NEGATIVE",
                  "C1-UNRESOLVED", "C1-VOID"):
        assert token in design
        assert token in (HERE / "READ_RULE.md").read_text()


def test_build_constants_match_the_design():
    import build_c1_targets as B
    assert B.WORLD_BASE == 16
    assert B.M_BASE == {"farm_capture": 32, "invasion": 16,
                        "defense": 8, "control": 8}
    assert [e["block"] for e in B.EXTENSIONS] == ["E1", "E2", "E3"]
    design = (HERE / "DESIGN.md").read_text()
    assert "WORLD_BASE = 16" in design
    assert "farm_capture: 32" in design


# --------------------------------------------------------------------------- #
# §6  outcome-blindness of the selector                                         #
# --------------------------------------------------------------------------- #
BANNED = ("winner", "final_scores", "recorded_scores", "margin", "realized",
          "delta_pts_mover", "price_", "scores_at_ply", "regret",
          "margin_p0_minus_p1")


def test_selector_reads_no_outcome_field():
    body = _code_only((HERE / "build_c1_targets.py").read_text())
    hits = [w for w in BANNED if w in body]
    assert not hits, f"the selector touches outcome fields: {hits}"


def test_preflight_checks_the_runners_mask_not_the_microgates_mask():
    import preflight_c1 as P
    assert P.RUNNER_LEGAL_MASK_CACHE is True
    runner = RUNNER.read_text()
    assert "enable_legal_moves_cache=True" in runner
    mg = (REPO / "measurement" / "microgates_20260828" / "microgates.py").read_text()
    assert "LEGAL_MASK_CACHE = False" in mg


def test_doc_lint_is_clean_on_this_directory():
    out = subprocess.run([sys.executable, str(REPO / "scripts" / "doc_lint.py"),
                          "--errors-only"], capture_output=True, text=True,
                         timeout=180)
    assert out.returncode == 0, out.stdout + out.stderr
