"""F9 A0 — the resolved `rules_profile` and its fail-loud boundaries.

The spec's whole argument for this plumbing is that a rules flag which is
*unstamped* or *partially applied* is worse than no flag at all: F9 exists because
a silent rule divergence survived every self-consistency gate the project owns. So
these tests are about the boundaries, not the happy path:

  * `walled` (the default) must add NOTHING to any `Game(...)` — that is Gate A0's
    identity, and it is checked as a property of the constructed object;
  * a profile whose fields the code cannot yet honour must RAISE, never be
    silently downgraded to what is built;
  * the profile must reach every worker (env-backed, so spawn inherits it);
  * a non-`walled` run must be refused an `experiments/results.csv` row unless the
    row's `exp_id` says which rules it was played under.
"""
from __future__ import annotations

import json
import os

import pytest

from carcassonne_ai import rules_profile as rp
from carcassonne_ai.game_wrapper import (
    ENGINE_BOARD_COLS,
    ENGINE_BOARD_ROWS,
    ENGINE_START_COL,
    ENGINE_START_ROW,
    Game,
)


@pytest.fixture(autouse=True)
def _clean_profile():
    """Every test starts and ends with no profile activated."""
    rp.reset()
    yield
    rp.reset()


# --------------------------------------------------------------------------- #
# The default IS the engine of record                                          #
# --------------------------------------------------------------------------- #
def test_default_is_walled_and_matches_the_engine_constants():
    prof = rp.active()
    assert prof.name == "walled"
    assert prof.is_walled
    # Duplicated constants in rules_profile.py are pinned equal to game_wrapper's,
    # so the "import-cycle free" convenience can never drift into a second truth.
    assert (prof.start_row, prof.start_col) == (ENGINE_START_ROW, ENGINE_START_COL)
    assert (prof.board_rows, prof.board_cols) == (ENGINE_BOARD_ROWS, ENGINE_BOARD_COLS)


def test_walled_adds_nothing_to_any_game_call():
    """GATE A0's identity, held structurally: the profile's kwargs are EMPTY, so a
    pre-F9 `Game()` call is the same call it always was."""
    assert rp.resolve("walled").game_kwargs() == {}
    rp.activate("walled")
    g = Game()
    assert g.recentred is False
    assert g.fixed_start_tile is False
    assert (g.start_row, g.start_col) == (ENGINE_START_ROW, ENGINE_START_COL)


def test_activating_a_profile_moves_the_default_game_geometry():
    rp.activate("centered18")
    g = Game()
    assert g.recentred is True
    assert (g.start_row, g.start_col) == (18, ENGINE_START_COL)
    # ... and the retail profile moves the start TILE, not the grid
    rp.activate("retail")
    g2 = Game()
    assert g2.fixed_start_tile is True
    assert g2.recentred is False


# --------------------------------------------------------------------------- #
# fixed_v1 — the Phase-B bundle (spec J3)                                       #
# --------------------------------------------------------------------------- #
def test_fixed_v1_carries_all_four_levers_into_the_game_call():
    """The bundle's whole point: ONE name resolves to all four rules levers, so a
    Phase-B leg cannot be half-applied. The kwarg NAMES are the ones
    `game_wrapper.Game` actually landed (`cloister_scan_fix`, `draw_rule`), not
    this module's vocabulary (`cloister_scan`, `unplaceable_tile`) — a mismatch
    there would be a TypeError at construction, which is why the Game is really
    built below rather than the dict merely inspected."""
    prof = rp.resolve("fixed_v1")
    assert prof.game_kwargs() == {
        "start_row": 18, "start_col": ENGINE_START_COL,   # W2 / A1
        "fixed_start_tile": True,                          # A4
        "cloister_scan_fix": True,                         # A2
        "draw_rule": "redraw",                             # A3
    }
    assert prof.is_walled is False

    rp.activate("fixed_v1")
    g = Game()
    assert g.recentred is True and (g.start_row, g.start_col) == (18, ENGINE_START_COL)
    assert g.fixed_start_tile is True
    assert g.cloister_scan_fix is True
    assert g.draw_rule == "redraw" and g.redraw_unplaceable is True


def test_fixed_v1_declares_the_r9_env_and_a_leg_without_it_is_detectable():
    """R9 is env-latched at import (base_deck derives the farm data, the Rust
    registry latches a OnceLock), so the profile CANNOT apply it — it can only
    declare the debt and stamp whether the process paid it. Without the env, a
    fixed_v1 manifest must say so: otherwise a leg that forgot `CARCASSONNE_FIX_R9`
    produces an artifact indistinguishable from one that did not."""
    prof = rp.resolve("fixed_v1")
    assert prof.r9_env_expected is True

    os.environ.pop(rp.R9_ENV_VAR, None)
    m = prof.as_manifest()
    assert m["r9_env_expected"] is True
    assert m["r9_env_observed"] is False
    assert m["r9_env_ok"] is False, "a fixed_v1 leg with no env must be detectable"

    os.environ[rp.R9_ENV_VAR] = "1"
    try:
        m2 = prof.as_manifest()
        assert m2["r9_env_observed"] is True and m2["r9_env_ok"] is True
    finally:
        os.environ.pop(rp.R9_ENV_VAR, None)

    # ...and walled, which expects no env, is flagged when the env IS set —
    # a walled number measured under R9 is not a walled number.
    os.environ[rp.R9_ENV_VAR] = "1"
    try:
        assert rp.resolve("walled").as_manifest()["r9_env_ok"] is False
    finally:
        os.environ.pop(rp.R9_ENV_VAR, None)


def test_rules_profile_r9_truthiness_matches_both_engines():
    """The spellings are duplicated here to keep this module import-cycle free
    (same convenience as the geometry constants); pin them equal to the two real
    implementations so the convenience cannot drift into a third truth."""
    import carc_rs
    from wingedsheep.carcassonne.tile_sets.base_deck import _r9_env_on

    assert rp.R9_ENV_VAR == "CARCASSONNE_FIX_R9"
    for raw in ("1", "true", "TRUE", "yes", "on", " on ", "0", "", "no", "off", "2"):
        assert rp.r9_env_on({rp.R9_ENV_VAR: raw}) == _r9_env_on({rp.R9_ENV_VAR: raw}), raw
    # the Rust side is a OnceLock resolved once per process, so it can only be
    # compared against the env this process actually started with
    assert carc_rs.r9_enabled() == rp.r9_env_on()


def test_an_explicit_kwarg_always_beats_the_profile():
    """The profile fills in what the caller left unsaid; it never overrides an
    explicit argument (otherwise a probe or a test could not pin its own grid)."""
    rp.activate("centered18")
    g = Game(start_row=ENGINE_START_ROW, start_col=ENGINE_START_COL)
    assert g.recentred is False


def test_every_shipped_profile_uses_an_even_shift():
    """`board_repr.offset_from_centroid_sums` is equivariant under EVEN translations
    only (banker's rounding). An odd-shift profile would silently slip the window on
    ~half of all positions — `Game` refuses it, and no shipped profile may rely on
    that refusal firing."""
    for name in rp.known():
        prof = rp.resolve(name)
        assert (prof.start_row - ENGINE_START_ROW) % 2 == 0, name
        assert (prof.start_col - ENGINE_START_COL) % 2 == 0, name


# --------------------------------------------------------------------------- #
# Fail-loud                                                                     #
# --------------------------------------------------------------------------- #
def test_an_unknown_profile_raises_rather_than_defaulting():
    with pytest.raises(rp.RulesProfileError) as e:
        rp.resolve("canonical")
    assert "unknown rules_profile" in str(e.value)


@pytest.mark.parametrize("field,value,needle", [
    ("board_rows", 143, "W3"),
])
def test_a_profile_the_code_cannot_honour_is_refused_not_ignored(field, value, needle):
    """A HALF-applied profile is the failure mode F9 exists to detect, so anything
    not yet built raises at resolve time. These assertions lift as A1-b/A2/A3 land —
    when they start failing, that is the signal to move them, not to delete them.

    MOVED 2026-08-03 (the F9 compose merge): `cloister_scan="fixed"` (A2) and
    `unplaceable_tile="redraw"` (A3) used to live in this list. They are now
    BUILT, so their "not built" refusals were retired exactly as the paragraph
    above instructs — and replaced by the two tests directly below, which assert
    the stronger property (the values are HONOURED, and an unknown value in
    either vocabulary still raises). Only W3 remains unbuilt."""
    from dataclasses import replace

    bad = replace(rp.PROFILES["walled"], name="not_built", **{field: value})
    rp.PROFILES["not_built"] = bad
    try:
        with pytest.raises(rp.RulesProfileError) as e:
            rp.resolve("not_built")
        assert needle in str(e.value)
    finally:
        del rp.PROFILES["not_built"]


@pytest.mark.parametrize("field,value", [
    ("cloister_scan", "drifting_typo"),
    ("unplaceable_tile", "next-player"),
])
def test_an_unknown_rules_vocabulary_raises_rather_than_playing_the_engine_rule(
        field, value):
    """The replacement for the A2/A3 "not built" refusals above.

    `game_kwargs()` turns these fields into kwargs by EQUALITY (`== "fixed"`,
    `== "redraw"`), so a typo would fall through every branch and add no
    argument — i.e. quietly play the engine rule under a profile whose name and
    manifest both claim otherwise. That is the exact silent class F9 exists to
    kill, so the vocabulary is checked at resolve time."""
    from dataclasses import replace

    bad = replace(rp.PROFILES["walled"], name="typo", **{field: value})
    rp.PROFILES["typo"] = bad
    try:
        with pytest.raises(rp.RulesProfileError) as e:
            rp.resolve("typo")
        assert field in str(e.value)
    finally:
        del rp.PROFILES["typo"]


# --------------------------------------------------------------------------- #
# It must survive the process boundary (spawn workers re-import this module)    #
# --------------------------------------------------------------------------- #
def test_activation_travels_through_the_environment():
    rp.activate("centered18")
    assert os.environ[rp.ENV_VAR] == "centered18"
    # simulate a fresh interpreter that inherited the env but never called activate
    rp._cache = rp._cache_key = None
    assert rp.active().name == "centered18"


def test_a_bad_env_value_raises_in_the_worker_rather_than_silently_walling():
    os.environ[rp.ENV_VAR] = "typo18"
    rp._cache = rp._cache_key = None
    with pytest.raises(rp.RulesProfileError):
        rp.active()


# --------------------------------------------------------------------------- #
# The manifest stamp, and the results.csv guard it feeds                        #
# --------------------------------------------------------------------------- #
def test_every_manifest_carries_the_resolved_profile(tmp_path):
    from carcassonne_ai.run_manifest import write_manifest

    rp.activate("centered18")
    write_manifest(tmp_path, kind="unit", game="base", config={"x": 1})
    man = json.loads((tmp_path / "manifest.json").read_text())
    block = man["rules_profile"]
    assert block["name"] == "centered18"
    assert block["start_row"] == 18 and block["grid_rule"] == "centered18"
    assert block["recentred"] is True


def test_default_manifest_says_walled(tmp_path):
    from carcassonne_ai.run_manifest import write_manifest

    write_manifest(tmp_path, kind="unit", game="base", config={})
    man = json.loads((tmp_path / "manifest.json").read_text())
    assert man["rules_profile"]["name"] == "walled"


def test_patch_manifest_merges_one_key_without_touching_provenance(tmp_path):
    from carcassonne_ai.run_manifest import patch_manifest, write_manifest

    write_manifest(tmp_path, kind="unit", game="base", config={"deep": {"a": 1}})
    before = json.loads((tmp_path / "manifest.json").read_text())
    patch_manifest(tmp_path, "wall_sentinel", {"games": 4})
    after = json.loads((tmp_path / "manifest.json").read_text())
    assert after["wall_sentinel"] == {"games": 4}
    assert after["config"] == before["config"]
    assert after["code_rev"] == before["code_rev"]
    assert patch_manifest(tmp_path / "nope", "k", 1) is None


class TestResultsCsvGuard:
    """`experiments/results.csv` is the WALLED record. A fixed-rules number that
    enters it unlabelled is silently non-comparable — the exact class F9 exists to
    prevent — so the guard is on the one field every reader sees."""

    @staticmethod
    def _check(profile, exp_id):
        import importlib.util
        from pathlib import Path

        path = Path(__file__).resolve().parents[1] / "scripts" / "append_result_row.py"
        spec = importlib.util.spec_from_file_location("_arr", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        man = {} if profile is None else {"rules_profile": {"name": profile}}
        return mod.check_rules_profile(man, exp_id)

    def test_walled_rows_pass(self):
        assert self._check("walled", "cl060_h2h_k8x1376") == "walled"

    def test_a_legacy_manifest_with_no_block_is_walled_by_construction(self):
        assert self._check(None, "anything") == "walled"

    def test_a_fixed_rules_row_is_refused_unless_the_exp_id_says_so(self):
        with pytest.raises(SystemExit) as e:
            self._check("centered18", "f9_transfer_k8x1376")
        assert "REFUSED" in str(e.value)

    def test_a_fixed_rules_row_that_names_its_profile_passes(self):
        assert self._check("centered18", "f9_transfer_centered18_k8x1376") == "centered18"
