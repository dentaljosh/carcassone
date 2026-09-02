"""The production leaf environment is defined ONCE — and its VALUES have not moved.

Consolidation of 2026-09-02: eight hand-copied `CARCASSONNE_*` blocks collapsed onto
`carcassonne_ai.prod_env`. This suite is what keeps them collapsed.

Three jobs, in order of how loudly they should fail:

1. THE GOLDEN PIN (`test_play_profile_is_the_champion_leaf` and friends). The literal
   expected key/value pairs, spelled out. Consolidation must not move the champion's
   identity, so if anyone edits `prod_env.py` and changes a cap, a curve or a dispatch
   knob, THIS is the test that says so — independently of whether every site still
   agrees with every other site.
2. NO DRIFT (`test_*_matches_canonical`). Every former copy resolves to the canonical
   profile. Sites that CAN import it are checked by identity; the two that physically
   cannot (a standalone bench rsync'd to a box with no repo, and a test module that
   must set the env before its own imports) are parsed out of the source with `ast` and
   compared, which is the same guard the Android bridge used to get.
3. THE DELIBERATE DIVERGENCES ARE PINNED (`test_champ_env_sh_divergence_is_intentional`).
   `champ_env.sh` really does differ, on purpose, in a way that changes a RECORDED hash
   dialect. Pinning it means the divergence cannot silently grow.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from carcassonne_ai import prod_env  # noqa: E402


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #
def _load_by_path(name: str, path: Path):
    """Import a module by FILE PATH.

    Necessary because `env_preamble` is an ambiguous top-level name: there are two of
    them (human_anchor / f3_public_state_oracle) and whichever script dir reaches
    sys.path first shadows the other.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dict_literal_from_source(path: Path, var: str) -> dict[str, str]:
    """The value of a module-level `var = {...}` literal, WITHOUT importing the module.

    For sites that cannot be imported here (they apply env at import time, or they are
    standalone copies). `ast.literal_eval` so a source file can never execute code.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign) else [])
        for t in targets:
            if isinstance(t, ast.Name) and t.id == var:
                return ast.literal_eval(node.value)
    raise AssertionError(f"no module-level `{var} = {{...}}` literal in {path}")


def _first_dict_literal_in_for(path: Path) -> dict[str, str]:
    """The `{...}` of the first `for k, v in {...}.items():` at module level.

    `tests/test_alphabeta_agent.py` inlines its env block that way — it has to run
    before its own `carcassonne_ai` imports, so it cannot be a named import.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if (isinstance(node, ast.For) and isinstance(node.iter, ast.Call)
                and isinstance(node.iter.func, ast.Attribute)
                and node.iter.func.attr == "items"
                and isinstance(node.iter.func.value, ast.Dict)):
            return ast.literal_eval(node.iter.func.value)
    raise AssertionError(f"no module-level `for k, v in {{...}}.items():` in {path}")


def _sh_exports(path: Path) -> dict[str, str]:
    """CARCASSONNE_*/thread-pin `export K=V` pairs from a shell file (last wins)."""
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("export "):
            continue
        for tok in line[len("export "):].split():
            if "=" not in tok:
                continue
            k, v = tok.split("=", 1)
            if k.startswith(("CARCASSONNE_", "OMP_", "MKL_", "OPENBLAS_", "NUMEXPR_",
                             "VECLIB_", "CUDA_")):
                out[k] = v.strip('"').strip("'")
    return out


# --------------------------------------------------------------------------- #
# 1. THE GOLDEN PIN — the champion's identity, spelled out.                    #
# --------------------------------------------------------------------------- #
# Captured from the pre-consolidation tree (2026-09-02). Changing anything here is
# changing the deployed champion's leaf or its dispatch, which is an owner decision
# with a governance/PRODUCTION.yaml update and a leaf-fingerprint re-verify attached.
GOLDEN_PLAY = {
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-10,-5,-1.25,0,2.5,3.75,5,6.25",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
}
GOLDEN_RULER = {
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}


def test_play_profile_is_the_champion_leaf():
    """PLAY has not moved. Deployed play reads the leaf from the ENV, so this dict IS
    the champion's leaf shape (curve125, CL-051)."""
    assert prod_env.PLAY == GOLDEN_PLAY


def test_ruler_profile_has_not_moved():
    """RULER has not moved — and in particular still carries curve100, so fixed
    rulers/anchors stay on the frozen v2.9 substrate."""
    assert prod_env.RULER == GOLDEN_RULER


def test_the_two_profiles_differ_in_exactly_the_curve_and_the_thread_pins():
    """The PLAY/RULER split is deliberate and narrow. If a future edit makes them
    differ in a LEAF-SHAPE knob (a cap, meeple_k, value_blend), that is a real bug —
    the champion's leaf and the ruler's base must agree everywhere except the curve."""
    shared = set(prod_env.PLAY) & set(prod_env.RULER)
    differing = {k for k in shared if prod_env.PLAY[k] != prod_env.RULER[k]}
    assert differing == {"CARCASSONNE_V29_MEEPLE_CURVE"}
    # The key-set difference is only the (inert-by-default) CY_LEAF knob and thread pins.
    assert set(prod_env.RULER) - set(prod_env.PLAY) == {
        "CARCASSONNE_USE_CY_LEAF", "OPENBLAS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"}
    assert not set(prod_env.PLAY) - set(prod_env.RULER)


def test_curve125_is_exactly_curve100_times_1_25():
    """C5 curve125 = prior x1.25 exactly (governance/PRODUCTION.yaml leaf_config)."""
    c100 = [float(x) for x in prod_env.CURVE100.split(",")]
    c125 = [float(x) for x in prod_env.CURVE125.split(",")]
    assert len(c100) == len(c125) == 8
    assert c125 == pytest.approx([v * 1.25 for v in c100])


def test_profiles_agree_with_production_yaml():
    """The dispatch knobs match governance/PRODUCTION.yaml champion.env_knobs, and the
    PLAY curve/caps match champion.leaf_config."""
    yaml = pytest.importorskip("yaml")
    doc = yaml.safe_load((REPO / "governance" / "PRODUCTION.yaml").read_text("utf-8"))
    champ = doc["champion"]

    for k, v in champ["env_knobs"].items():
        assert prod_env.RULER[k] == v, f"{k} disagrees with PRODUCTION.yaml env_knobs"

    leaf = champ["leaf_config"]
    assert [float(x) for x in prod_env.PLAY["CARCASSONNE_V29_MEEPLE_CURVE"].split(",")] \
        == [float(x) for x in leaf["v29_meeple_curve"]]
    assert float(prod_env.PLAY["CARCASSONNE_V25_CAP"]) == float(leaf["bonus_cap"])
    assert float(prod_env.PLAY["CARCASSONNE_V25_OPP_CAP"]) == float(leaf["opp_bonus_cap"])


def test_shape_keys_are_exactly_what_default_config_reads():
    """PLAY_SHAPE is the subset that freezes virtual_score_v2.DEFAULT_CONFIG. If a knob
    is added to the leaf builder it must be added here too, or rustport's shape guard
    silently stops guarding it."""
    assert set(prod_env.SHAPE_KEYS) == set(prod_env.PLAY_SHAPE)
    assert set(prod_env.PLAY_SHAPE) <= set(prod_env.PLAY)
    # Every shape key must be one virtual_score_v2 actually reads.
    src = (REPO / "src" / "carcassonne_ai" / "virtual_score_v2.py").read_text("utf-8")
    for k in prod_env.SHAPE_KEYS:
        assert k in src, f"{k} is in PLAY_SHAPE but virtual_score_v2 never reads it"
    # ...and no dispatch/threading knob leaked into the shape subset.
    for k in prod_env.SHAPE_KEYS:
        assert not k.startswith(("CARCASSONNE_USE_", "OMP_", "MKL_", "CUDA_"))


# --------------------------------------------------------------------------- #
# 2. NO DRIFT — every former copy resolves to the canonical profile.           #
# --------------------------------------------------------------------------- #
def test_human_anchor_env_preamble_matches_canonical():
    mod = _load_by_path("_ha_env_preamble",
                        REPO / "scripts" / "human_anchor" / "env_preamble.py")
    assert mod.PROD_ENV == prod_env.PLAY
    assert mod.PROD_ENV is prod_env.PLAY, "must re-export, not re-declare"


def test_f3_env_preamble_matches_canonical():
    mod = _load_by_path("_f3_env_preamble",
                        REPO / "scripts" / "f3_public_state_oracle" / "env_preamble.py")
    assert mod.CANON_ENV == prod_env.RULER
    assert mod.CANON_ENV is prod_env.RULER, "must re-export, not re-declare"


def test_f3_apply_is_bound_to_ruler_not_the_play_default():
    """Regression guard for the consolidation itself: `prod_env.apply()` defaults to
    PLAY, so the F3 adapter must bind RULER explicitly. A bare re-export would have
    silently switched the F3 oracle's base curve to curve125."""
    mod = _load_by_path("_f3_env_preamble_apply",
                        REPO / "scripts" / "f3_public_state_oracle" / "env_preamble.py")
    assert mod.apply() == mod.resolved()
    assert set(mod.apply()) == set(prod_env.RULER)


def test_eval_fair_puct_canon_env_matches_canonical():
    """Parsed from source, not imported: importing eval_fair_puct applies the env and
    drags in the whole harness."""
    path = REPO / "scripts" / "classical_search" / "eval_fair_puct.py"
    src = path.read_text(encoding="utf-8")
    assert "from carcassonne_ai.prod_env import RULER as _CANON_ENV" in src, (
        "eval_fair_puct must import the canonical RULER profile, not re-declare a dict")
    assert "prod_env.apply(_CANON_ENV)" in src


def test_android_bridge_matches_canonical():
    """The bridge no longer carries a literal copy — it imports the canonical module,
    which ships in the on-device bundle (sync_python.py copies src/carcassonne_ai)."""
    path = REPO / "android" / "app" / "src" / "main" / "python" / "android_bridge.py"
    src = path.read_text(encoding="utf-8")
    assert "from carcassonne_ai.prod_env import PLAY as PROD_ENV" in src
    # The env import must precede the first engine/leaf import, or R9 and DEFAULT_CONFIG
    # latch against a bare environment.
    i_env = src.index("from carcassonne_ai.prod_env import PLAY as PROD_ENV")
    for later in ("import wingedsheep", "from wingedsheep",
                  "from carcassonne_ai.champion_factory", "import champion_factory"):
        j = src.find(later)
        if j != -1:
            assert i_env < j, f"prod_env import must precede `{later}`"


def test_release_conftest_uses_canonical():
    src = (REPO / "tests" / "release" / "conftest.py").read_text(encoding="utf-8")
    assert "prod_env.apply(prod_env.RULER)" in src
    assert "CARCASSONNE_V25_CAP" not in src, "no hand-copied knob values may remain"


def test_rustport_prod_leaf_env_shape_matches_canonical():
    """Checked in a FRESH interpreter, not by re-executing the module here.

    `prod_leaf_env` guards its own import order and refuses to load once
    `carcassonne_ai.virtual_score_v2` is in sys.modules — which it is, in any session
    that has already touched the leaf. Re-executing it in-process would trip that guard
    and test nothing useful; a subprocess exercises the real thing."""
    out = subprocess.run(
        [sys.executable, "-c",
         "import prod_leaf_env as m, json; "
         "print(json.dumps({'keys': list(m.SHAPE_KEYS), 'shape': m.PLAY_SHAPE, "
         "'resolved': m.RESOLVED}))"],
        capture_output=True, text=True, check=True,
        cwd=str(REPO / "scripts" / "rustport"),
        env={"PYTHONPATH": f"{REPO / 'src'}:{REPO / 'engine'}", "PATH": "/usr/bin:/bin"},
    ).stdout
    got = json.loads(out)
    assert tuple(got["keys"]) == tuple(prod_env.SHAPE_KEYS)
    assert got["shape"] == prod_env.PLAY_SHAPE
    # Importing it must actually PUT the shape in the environment (curve125 included).
    assert got["resolved"] == prod_env.PLAY_SHAPE
    # It applies the SHAPE only — never the dispatch knobs (see its docstring).
    assert "CARCASSONNE_USE_FLAT_LEAF" not in got["shape"]


def test_rustport_prod_leaf_env_guard_is_narrowed_to_the_leaf():
    """Its guard must test `carcassonne_ai.virtual_score_v2`, not the package name —
    otherwise importing the canonical module (which latches nothing) would trip it."""
    src = (REPO / "scripts" / "rustport" / "prod_leaf_env.py").read_text("utf-8")
    assert '"carcassonne_ai.virtual_score_v2" in sys.modules' in src
    assert '"carcassonne_ai" in sys.modules' not in src


def test_m5_bench_literal_copy_has_not_drifted():
    """`scripts/m5_bench/bench_champion.py` is rsync'd to the M5 as a STANDALONE file
    with no repo alongside it, so it keeps a literal copy. This is the guard that the
    copy still equals the canonical PLAY profile."""
    got = _dict_literal_from_source(
        REPO / "scripts" / "m5_bench" / "bench_champion.py", "PROD_ENV")
    assert got == prod_env.PLAY


def test_alphabeta_test_inline_block_has_not_drifted():
    """`tests/test_alphabeta_agent.py` sets the env before its own imports, so it
    inlines the block. Its comment claims equality with the human-anchor preamble; it
    actually carries the RULER dispatch/thread keys with the PLAY curve. Pinned as the
    union so the claim can no longer quietly rot."""
    got = _first_dict_literal_in_for(REPO / "tests" / "test_alphabeta_agent.py")
    # Same leaf SHAPE as PLAY (this is what decides DEFAULT_CONFIG).
    assert {k: got[k] for k in prod_env.SHAPE_KEYS} == prod_env.PLAY_SHAPE
    # Extra keys are dispatch/threading only — never a leaf-shape knob.
    for k in set(got) - set(prod_env.PLAY):
        assert k.startswith(("CARCASSONNE_USE_", "OPENBLAS_", "NUMEXPR_", "VECLIB_"))


# --------------------------------------------------------------------------- #
# 3. DELIBERATE DIVERGENCES — pinned, so they cannot grow.                     #
# --------------------------------------------------------------------------- #
def test_champ_env_sh_divergence_is_intentional():
    """`scripts/distill_flywheel/champ_env.sh` was NOT converted.

    It deliberately omits CARCASSONNE_V25_MEEPLE_K, which selects the
    `frozen_config_hash_meeple_k0` = 6dfffd57051690f2 dialect that
    governance/PRODUCTION.yaml records against champ_env/distill (meeple_k is inert
    under a non-null curve, so the leaf VALUE is unchanged — but the recorded hash
    dialect is not). Converting it would move a number in the governance record for no
    gain. This test pins the divergence to exactly that.
    """
    got = _sh_exports(REPO / "scripts" / "distill_flywheel" / "champ_env.sh")
    missing = set(prod_env.PLAY) - set(got)
    assert missing == {"CARCASSONNE_V25_MEEPLE_K", "CARCASSONNE_V25_DROP_THREE_OPEN",
                       "CARCASSONNE_V25_VALUE_BLEND"}, (
        "champ_env.sh's divergence from the canonical PLAY profile changed — "
        f"unexpectedly missing/no-longer-missing: {missing}")
    # Everything it DOES set must agree with the canonical profile.
    for k, v in got.items():
        if k in prod_env.PLAY:
            assert got[k] == prod_env.PLAY[k], f"champ_env.sh {k} drifted"
    # The omitted three are all no-ops for the leaf VALUE, which is why this is safe:
    #   MEEPLE_K          inert under a non-null curve (flat_leaf takes the curve branch)
    #   DROP_THREE_OPEN   `_config_from_env` tests `== "1"`, so "0" and unset are equal
    #   VALUE_BLEND       library default is "0.0" == the profile's "0"
    assert prod_env.PLAY["CARCASSONNE_V25_DROP_THREE_OPEN"] == "0"
    assert float(prod_env.PLAY["CARCASSONNE_V25_VALUE_BLEND"]) == 0.0


# --------------------------------------------------------------------------- #
# 4. The shell seam.                                                          #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("profile", ["play", "ruler"])
def test_export_cli_round_trips(profile):
    """`python -m carcassonne_ai.prod_env --export` is what launchers eval. Its output
    must be parseable POSIX and must reproduce the profile exactly."""
    out = subprocess.run(
        [sys.executable, "-m", "carcassonne_ai.prod_env", "--export", "--profile", profile],
        capture_output=True, text=True, check=True,
        env={"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin"},
    ).stdout
    got = {}
    for line in out.splitlines():
        assert line.startswith("export "), f"non-export line would break `eval`: {line!r}"
        k, v = line[len("export "):].split("=", 1)
        assert v.startswith("'") and v.endswith("'"), f"value not shell-quoted: {line!r}"
        got[k] = v[1:-1].replace("'\\''", "'")
    assert got == prod_env.PROFILES[profile]


@pytest.mark.parametrize("profile", ["play", "ruler"])
def test_json_cli_round_trips(profile):
    out = subprocess.run(
        [sys.executable, "-m", "carcassonne_ai.prod_env", "--json", "--profile", profile],
        capture_output=True, text=True, check=True,
        env={"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin"},
    ).stdout
    assert json.loads(out) == prod_env.PROFILES[profile]


def test_release_audit_sh_consumes_the_cli():
    """The one shell launcher converted in this pass no longer types the values."""
    src = (REPO / "scripts" / "release_audit.sh").read_text(encoding="utf-8")
    assert "carcassonne_ai.prod_env --export --profile ruler" in src
    assert "export CARCASSONNE_V25_CAP" not in src


# --------------------------------------------------------------------------- #
# 5. The module's own contract.                                               #
# --------------------------------------------------------------------------- #
def test_importing_prod_env_latches_nothing():
    """The whole design rests on this: importing the canonical module must NOT pull in
    the leaf, the engine, or the tile table — otherwise `apply()` would always run too
    late and every site's ordering contract would be a lie."""
    out = subprocess.run(
        [sys.executable, "-c",
         "import sys; import carcassonne_ai.prod_env as p; "
         "bad=[m for m in sys.modules if m.startswith(('wingedsheep',)) "
         "or m.startswith('carcassonne_ai.') and m != 'carcassonne_ai.prod_env']; "
         "print(repr(bad))"],
        capture_output=True, text=True, check=True,
        env={"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin"},
    ).stdout.strip()
    assert out == "[]", f"importing prod_env dragged in {out}"


def test_latching_modules_are_real_and_do_latch():
    """`LATCHING_MODULES` is what every import-order guard now tests. Each name must
    exist AND must actually read one of the knobs at module scope — otherwise a guard
    is either impossible to trip or silently stops protecting something."""
    reads = {
        "carcassonne_ai.virtual_score_v2": (REPO / "src/carcassonne_ai/virtual_score_v2.py",
                                            "CARCASSONNE_V25_CAP"),
        "carcassonne_ai.flat_leaf": (REPO / "src/carcassonne_ai/flat_leaf.py",
                                     "CARCASSONNE_USE_FLAT_LEAF"),
        "carcassonne_ai.board_repr": (REPO / "src/carcassonne_ai/board_repr.py",
                                      "CARCASSONNE_USE_CY_REPR"),
        "wingedsheep.carcassonne.tile_sets.base_deck": (
            REPO / "engine/wingedsheep/carcassonne/tile_sets/base_deck.py",
            "CARCASSONNE_FIX_R9"),
    }
    assert set(prod_env.LATCHING_MODULES) == set(reads)
    for mod, (path, knob) in reads.items():
        assert path.is_file(), f"{mod} -> {path} does not exist"
        assert knob in path.read_text("utf-8"), f"{path} no longer reads {knob}"


def test_latched_modules_is_empty_before_the_leaf_is_imported():
    """The guard must be trippable-but-not-tripped in the state every preamble runs in:
    the package imported, the leaf not. This is the exact false-positive that the old
    `"carcassonne_ai" in sys.modules` proxy produced once the preambles started
    importing the canonical module."""
    out = subprocess.run(
        [sys.executable, "-c",
         "import carcassonne_ai.prod_env as p; print(p.latched_modules())"],
        capture_output=True, text=True, check=True,
        env={"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin"},
    ).stdout.strip()
    assert out == "()", f"importing prod_env already latched: {out}"


def test_latched_modules_fires_once_the_leaf_is_imported():
    out = subprocess.run(
        [sys.executable, "-c",
         "import carcassonne_ai.virtual_score_v2; "
         "import carcassonne_ai.prod_env as p; print(p.latched_modules())"],
        capture_output=True, text=True, check=True,
        env={"PYTHONPATH": f"{REPO / 'src'}:{REPO / 'engine'}", "PATH": "/usr/bin:/bin"},
    ).stdout.strip()
    assert "carcassonne_ai.virtual_score_v2" in out


@pytest.mark.parametrize("path,label", [
    ("scripts/rustport/fair_common.py", "fair_common"),
    ("scripts/tiletie/meeple_tie_census.py", "meeple_tie_census"),
])
def test_import_order_guards_do_not_use_the_package_proxy(path, label):
    """Regression guard for the consolidation. These two modules guard import order.
    Because the preambles now import `carcassonne_ai.prod_env`, a guard written as
    `if "carcassonne_ai" in sys.modules` would fire on EVERY import. They must test
    `prod_env.latched_modules()` instead."""
    src = (REPO / path).read_text(encoding="utf-8")
    assert '"carcassonne_ai" in sys.modules' not in src, (
        f"{label} still uses the package-name proxy — it will now always fire")
    assert "prod_env.latched_modules()" in src


def test_fair_common_imports_without_raising():
    """The end-to-end version of the test above: `fair_common` applies the preamble and
    then runs its own import-order guard. Before the guard was narrowed this raised."""
    r = subprocess.run(
        [sys.executable, "-c", "import fair_common; print('OK')"],
        capture_output=True, text=True, cwd=str(REPO / "scripts" / "rustport"),
        env={"PYTHONPATH": f"{REPO / 'src'}:{REPO / 'engine'}", "PATH": "/usr/bin:/bin"},
    )
    if r.returncode != 0 and "carc_rs" in r.stderr:
        pytest.skip("carc_rs extension not built in this tree")
    assert r.returncode == 0, r.stderr[-3000:]
    assert "OK" in r.stdout


def test_apply_is_setdefault_not_overwrite(monkeypatch):
    """A caller who already exported a knob WINS — orchestrators and --shared-claim
    cells depend on this."""
    monkeypatch.setenv("CARCASSONNE_V25_CAP", "99")
    got = prod_env.apply(prod_env.PLAY)
    assert got["CARCASSONNE_V25_CAP"] == "99"


def test_verify_raises_on_mismatch(monkeypatch):
    monkeypatch.setenv("CARCASSONNE_V25_CAP", "99")
    with pytest.raises(RuntimeError, match="production leaf environment mismatch"):
        prod_env.verify(prod_env.PLAY)


def test_verify_passes_after_apply(monkeypatch):
    for k in list(prod_env.RULER):
        monkeypatch.delenv(k, raising=False)
    prod_env.apply(prod_env.RULER)
    assert prod_env.verify(prod_env.RULER) == prod_env.RULER


def test_unknown_profile_name_raises():
    with pytest.raises(KeyError, match="unknown prod_env profile"):
        prod_env.apply("clairvoyant")
