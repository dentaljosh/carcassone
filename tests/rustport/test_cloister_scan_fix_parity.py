"""F9-A2 / the cloister-completion scan fix, Python reference vs `carc_rs`.

Companion to `tests/test_cloister_scan_fix.py` (the Python engine's own
control/trigger reproducer) and to the Rust `engine::cloister_scan_fix_tests`
module — this is the leg that drives BOTH engines from the same action indices
and compares them per ply.

**Default semantics are the gate that matters.** The flag is OPT-IN and DEFAULT
OFF, so `MirrorState.from_seed(seed)` with nothing passed must still be the
drifting scan every recorded game, checkpoint and gate was produced under;
`test_default_is_the_drifting_scan_of_record` pins that.

**Coverage, not volume, is what makes the flags-on leg mean something.** Under
uniform play the fixed scan runs thousands of times while its OUTCOME never
differs — random play completes ~0.1 cloisters/game and almost never has a monk
on one (audit RF-D-1's frequency caveat; measured here as 0.002 accelerated
completions/game over 1,000 uniform+wall games vs 0.2/game under the fuzz's
cloister-seeking `monk` policy). So the flags-on subset below runs `monk` seeds
that are KNOWN to carry the event.

The heavy legs are scripts, not tests:
  * `scripts/rustport/lockstep_fuzz.py --cloister-scan-fix --games 1000`
  * `scripts/rustport/lockstep_fuzz.py --cloister-scan-fix --monk-frac 1 --games 1000`
  * `scripts/rustport/probe_cloister_mutations.py`
This module runs the always-on subset.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "src", REPO / "engine", REPO / "scripts" / "measurement_infra",
           REPO / "scripts" / "rustport"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

carc_rs = pytest.importorskip("carc_rs", reason="build with `maturin develop --release`")

import os  # noqa: E402

os.environ["CARCASSONNE_WINDOW_AUDIT"] = "1"   # must precede game_wrapper import

import lockstep_fuzz as lf  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402

if not hasattr(carc_rs.MirrorState, "cloister_scan_fix"):
    pytest.skip("carc_rs predates F9-A2; rebuild the wheel",
                allow_module_level=True)

SEEDS = [0, 1, 2, 11]
# Seed indices measured to carry at least one accelerated completion under the
# `monk` policy (`scripts/rustport/probe_cloister_mutations.py`).
EVENT_SEEDS = [5, 14, 18, 23, 30, 48]


def _job(i: int, *, fix: bool, mode: str = "uniform", **kw) -> dict:
    job = {"deck_seed": lf.FUZZ_SEED_BASE + i, "policy_seed": 5_000_000 + i,
           "mode": mode, "max_plies": 400, "start_rule": "engine",
           "start_row": 6, "start_col": 15, "cloister_scan_fix": fix}
    job.update(kw)
    return job


def _ok(r: dict) -> None:
    assert r["mismatch"] is None, r["mismatch"]
    assert r["status"] in ("ok", "window_overflow", "engine_error"), r["status"]


# --- default semantics -----------------------------------------------------

class TestDefaultIsOff:
    def test_default_is_the_drifting_scan_of_record(self):
        """THE regression bar: passing nothing, passing False, and passing the
        other flags must all be the same game the port has always played."""
        for seed in SEEDS:
            a = carc_rs.MirrorState.from_seed(str(lf.FUZZ_SEED_BASE + seed))
            assert a.cloister_scan_fix() is False
            for kw in ({}, {"cloister_scan_fix": False},
                       {"cloister_scan_fix": None, "start_rule": "engine"}):
                b = carc_rs.MirrorState.from_seed(str(lf.FUZZ_SEED_BASE + seed), **kw)
                assert a.string_repr() == b.string_repr()
                assert a.state_digest() == b.state_digest()
                assert b.cloister_accel() == 0

    def test_the_python_wrapper_default_is_off(self):
        assert Game().cloister_scan_fix is False
        assert Game().get_init_board().state.cloister_scan_fix is False

    def test_the_resolved_config_reports_the_flag(self):
        assert carc_rs.resolve_game_config()["cloister_scan_fix"] is False
        assert carc_rs.resolve_game_config(
            cloister_scan_fix=True)["cloister_scan_fix"] is True

    def test_the_flag_is_independent_of_the_p5_flags(self):
        """A2 composes with P5: setting one must not move the other."""
        c = carc_rs.resolve_game_config(start_rule="retail", start_row=8,
                                        cloister_scan_fix=True)
        assert (c["start_rule"], c["start_row"], c["cloister_scan_fix"]) == (
            "retail", 8, True)
        assert carc_rs.resolve_game_config(start_rule="retail")[
            "cloister_scan_fix"] is False


# --- lockstep, both conventions -------------------------------------------

class TestLockstep:
    @pytest.mark.parametrize("fix", [False, True])
    @pytest.mark.parametrize("mode", ["uniform", "wall"])
    def test_lockstep_subset(self, fix, mode):
        for i in SEEDS[:3]:
            r = lf.fuzz_game(_job(i, fix=fix, mode=mode))
            _ok(r)
            if not fix:
                assert r["cloister_accel"] == 0

    @pytest.mark.parametrize("i", EVENT_SEEDS)
    def test_the_event_bearing_seeds_stay_in_lockstep(self, i):
        """The games where the fix actually CHANGES the outcome — a monk goes
        back to supply mid-game, so the meeple supply and therefore the node key
        diverge from the flags-off line.  Both engines must diverge identically."""
        r = lf.fuzz_game(_job(i, fix=True, mode="monk"))
        _ok(r)
        assert r["cloister_accel"] >= 1, "seed no longer carries the event"

    @pytest.mark.parametrize("i", EVENT_SEEDS[:3])
    def test_the_same_seed_flags_off_sees_no_event(self, i):
        r = lf.fuzz_game(_job(i, fix=False, mode="monk"))
        _ok(r)
        assert r["cloister_accel"] == 0


# --- composition with the P5 flags ----------------------------------------

class TestComposesWithP5:
    @pytest.mark.parametrize("rule", ["engine", "retail"])
    def test_composes_with_the_start_rule(self, rule):
        r = lf.fuzz_game(_job(1, fix=True, mode="monk", start_rule=rule))
        _ok(r)

    def test_composes_with_an_even_recentring(self):
        r = lf.fuzz_game(_job(1, fix=True, mode="monk", start_row=8, start_col=17))
        _ok(r)

    def test_composes_with_both_at_once(self):
        r = lf.fuzz_game(_job(2, fix=True, mode="monk", start_rule="retail",
                              start_row=8, start_col=17))
        _ok(r)
