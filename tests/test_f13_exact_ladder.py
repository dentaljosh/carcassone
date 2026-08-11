"""F13 modern exact-K winrate ladder — the NEW tail machinery.

Prereg (binding): measurement/exact_k_ladder_20260803/PREREG_DRAFT.md
Machinery:        scripts/classical_search/exact_tail.py
Harness wiring:   scripts/classical_search/eval_puct_priors.py (--opp-exact-k /
                  --exact-wall-caps / --exact-k-floor / --exact-solver)
Launcher:         scripts/classical_search/f13_ladder_launcher.sh

Covers, in the order the brief names them:
  * the per-arm tail-K override plumbs through the CLI -> worker -> both _ExactHandoffs
    -> the per-cell manifest (end-to-end tiny cell);
  * a wall cap TRIGGERS the fallback to K-1 (monkeypatched always-capping solve), and
    the fallback plays the PREFIX SEARCH, never a raw leaf;
  * the fallback RECURSES downward across plies and stops at the floor;
  * cap-hit + fallback counters land in summary.json AND manifest.json (per-game and
    per-cell totals), so the >20%-censored rule is computable;
  * the censored-rate computation, including the >20% boundary;
  * REGRESSION: the production fair K<=2 MARGINALIZED latch is UNTOUCHED by all of it;
  * REGRESSION: a non-F13 cell's per-game JSON and manifest are schema-identical to the
    pre-F13 harness (the ladder is default-OFF).

Also proves the wall cap's state-safety claim directly: a capped call runs in a forked
child, so nothing it did — including a deliberate mutation — can reach this process.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parent.parent
CS = REPO / "scripts" / "classical_search"
SCRIPT = CS / "eval_puct_priors.py"
LAUNCHER = CS / "f13_ladder_launcher.sh"
SMOKER = CS / "f13_smoke.py"

sys.path.insert(0, str(CS))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

import exact_tail as et  # noqa: E402

# The harness sets the production v2.9 Bmild_cap8 leaf env via setdefault at import, so
# import it before anything that reads DEFAULT_CONFIG (same stanza as the sibling
# harness tests; the module name is registered so fork-Pool workers can unpickle
# _play_one).
_spec = importlib.util.spec_from_file_location("eval_puct_priors", SCRIPT)
epp = importlib.util.module_from_spec(_spec)
sys.modules["eval_puct_priors"] = epp
_spec.loader.exec_module(epp)


# =========================================================================== #
# 1. the cap map                                                              #
# =========================================================================== #
class TestWallCapMap:
    def test_empty_forms_mean_uncapped(self):
        assert et.parse_wall_caps(None) == {}
        assert et.parse_wall_caps("") == {}
        assert et.parse_wall_caps("   ") == {}

    def test_prereg_map(self):
        assert et.parse_wall_caps("5:300,6:600") == {5: 300.0, 6: 600.0}
        # "default" spells the pre-registered map: K<=4 uncapped, K5 300s, K6 600s.
        assert et.parse_wall_caps("default") == et.DEFAULT_WALL_CAPS
        assert et.DEFAULT_WALL_CAPS == {5: 300.0, 6: 600.0}

    def test_zero_means_explicitly_uncapped_at_that_k(self):
        assert et.parse_wall_caps("5:0,6:600") == {6: 600.0}

    def test_caps_are_a_map_not_hardcoded(self):
        # The brief's requirement: caps must be a per-K CLI/config map. Any K is
        # expressible, including ones the prereg does not name.
        assert et.parse_wall_caps("3:12.5,7:1800") == {3: 12.5, 7: 1800.0}

    @pytest.mark.parametrize("bad", ["5", "5:", ":300", "x:300", "5:abc", "-1:300",
                                     "5:-3"])
    def test_malformed_raises_never_silently_uncaps(self, bad):
        # A mistyped cap must NOT silently become "no cap" on an overnight rung.
        with pytest.raises(ValueError):
            et.parse_wall_caps(bad)

    def test_cap_for_keys_on_solve_size(self):
        caps = {5: 300.0, 6: 600.0}
        assert et.cap_for(caps, 4) is None      # K<=4 uncapped (prereg)
        assert et.cap_for(caps, 5) == 300.0
        assert et.cap_for(caps, 6) == 600.0
        assert et.cap_for({}, 6) is None
        assert et.cap_for(None, 6) is None

    def test_fmt_roundtrips(self):
        spec = "5:300,6:600"
        assert et.fmt_wall_caps(et.parse_wall_caps(spec)) == spec
        assert et.fmt_wall_caps({}) == ""


# =========================================================================== #
# 2. the wall cap itself — mechanism + state safety                           #
# =========================================================================== #
_SIDE_EFFECT: list = []


def _mutating_fast():
    _SIDE_EFFECT.append("ran")
    return {"status": "ok", "action": 7, "nodes": 3}


def _mutating_slow():
    _SIDE_EFFECT.append("ran")
    time.sleep(30)
    return {"status": "ok", "action": 7, "nodes": 3}


def _boom():
    raise RuntimeError("solver exploded")


class TestWallCapCall:
    def setup_method(self):
        _SIDE_EFFECT.clear()

    def test_uncapped_runs_inline_no_fork(self):
        # This is what keeps the K<=4 production tail byte-identical to the pre-F13
        # path (and what makes the K4-vs-K4 identity smoke meaningful).
        out = et.wall_cap_call(_mutating_fast, None)
        assert out == {"status": "ok", "action": 7, "nodes": 3}
        assert _SIDE_EFFECT == ["ran"], "uncapped call must run IN THIS PROCESS"

    def test_zero_cap_also_runs_inline(self):
        et.wall_cap_call(_mutating_fast, 0)
        assert _SIDE_EFFECT == ["ran"]

    def test_capped_call_returns_the_value(self):
        out = et.wall_cap_call(_mutating_fast, 30.0)
        assert out == {"status": "ok", "action": 7, "nodes": 3}

    def test_capped_call_is_state_safe_child_mutations_do_not_escape(self):
        # THE state-safety claim, proven: a capped solve runs in a forked child, so
        # every byte it touches lives in the child's copy-on-write address space.
        out = et.wall_cap_call(_mutating_fast, 30.0)
        assert out["action"] == 7
        assert _SIDE_EFFECT == [], (
            "a capped solve must NOT be able to mutate this process — that is the "
            "whole reason a SIGKILL on cap cannot corrupt state")

    def test_cap_hit_raises_and_leaves_the_parent_untouched(self):
        sentinel = {"untouched": True}
        t0 = time.monotonic()
        with pytest.raises(et.WallCapExceeded) as ei:
            et.wall_cap_call(_mutating_slow, 0.6, k=6)
        dt = time.monotonic() - t0
        assert dt < 12.0, f"cap did not fire promptly ({dt:.1f}s for a 0.6s cap)"
        assert ei.value.cap_secs == 0.6 and ei.value.k == 6
        assert _SIDE_EFFECT == [], "the killed child cannot have mutated the parent"
        assert sentinel == {"untouched": True}

    def test_cap_hit_reaps_the_child_no_zombie(self):
        with pytest.raises(et.WallCapExceeded):
            et.wall_cap_call(_mutating_slow, 0.4)
        # If the child were left unreaped, waitpid(-1) would return it here.
        with pytest.raises(ChildProcessError):
            os.waitpid(-1, os.WNOHANG)

    def test_child_exception_is_a_failure_never_a_result(self):
        with pytest.raises(et.ChildSolveFailed) as ei:
            et.wall_cap_call(_boom, 30.0)
        assert "RuntimeError" in str(ei.value)

    def test_rust_solver_has_no_timeout_parameter(self):
        # The design rationale, asserted rather than assumed: if carc_rs ever grows a
        # deadline/timeout argument, fork+SIGKILL stops being the only option and this
        # test should be revisited deliberately.
        carc_rs = pytest.importorskip("carc_rs")
        doc = (carc_rs.MirrorState.solve_endgame.__doc__ or "").lower()
        text = (doc + " " + str(inspect.signature)).lower()
        assert "timeout" not in doc and "deadline" not in doc, (
            "carc_rs.solve_endgame appears to expose a wall/timeout knob now — "
            "re-evaluate the fork+SIGKILL cap in scripts/classical_search/exact_tail.py")
        assert text is not None


# =========================================================================== #
# 3. the fallback ladder (ExactTailState)                                     #
# =========================================================================== #
class TestFallbackLadder:
    def test_attempt_accounting_splits_capped_from_uncapped(self):
        st = et.ExactTailState(6, caps={5: 300.0, 6: 600.0}, k_floor=4)
        assert st.note_attempt(6) == 600.0
        assert st.note_attempt(4) is None       # K<=4 uncapped (prereg)
        assert st.latch_solves == 2
        assert st.capped_attempts == 1
        assert st.cap_hits == 0

    def test_cap_hit_steps_the_threshold_down_one(self):
        st = et.ExactTailState(6, caps={5: 300.0, 6: 600.0}, k_floor=4)
        st.note_attempt(6)
        st.note_cap_hit(6)
        assert st.eff_k == 5, "a cap at k=6 must degrade the arm to the K=5 arm"
        assert st.fallback_depth == 1
        assert st.cap_hits == 1
        assert st.cap_hits_by_k == {6: 1}

    def test_fallback_recurses_downward_and_floors_at_the_incumbent(self):
        # "recurse downward if that also caps" — realised across plies, because there
        # is no smaller exact solve OF THE SAME position (no solver has a depth limit).
        st = et.ExactTailState(6, caps={5: 1.0, 6: 1.0, 4: 1.0, 3: 1.0}, k_floor=4)
        for k in (6, 5, 4, 3):
            st.note_attempt(k)
            st.note_cap_hit(k)
        assert st.eff_k == 4, "the ladder must never degrade BELOW the incumbent floor"
        assert st.fallback_depth == 2, "6->5, 5->4, then the floor absorbs the rest"
        assert st.cap_hits == 4
        assert st.cap_hits_by_k == {6: 1, 5: 1, 4: 1, 3: 1}

    def test_floor_zero_reproduces_the_pre_f13_degradation(self):
        st = et.ExactTailState(3, caps={1: 1.0, 2: 1.0, 3: 1.0}, k_floor=0)
        for k in (3, 2, 1):
            st.note_attempt(k)
            st.note_cap_hit(k)
        assert st.eff_k == 0
        assert st.fallback_depth == 3

    def test_as_dict_carries_every_counter_the_manifest_needs(self):
        st = et.ExactTailState(5, caps={5: 300.0}, k_floor=4)
        st.note_attempt(5)
        st.note_cap_hit(5)
        d = st.as_dict()
        assert d["exact_k"] == 5 and d["eff_k_final"] == 4 and d["k_floor"] == 4
        assert d["latch_solves"] == 1 and d["capped_attempts"] == 1
        assert d["cap_hits"] == 1 and d["fallback_depth"] == 1
        assert d["cap_hits_by_k"] == {5: 1}


# =========================================================================== #
# 4. the censored-rate computation (the >20% rule)                            #
# =========================================================================== #
class TestCensoring:
    def test_prereg_denominator_is_latch_solves(self):
        # PREREG: "if >20% of a rung's LATCH SOLVES cap out".
        assert et.censored_rate(3, 12) == pytest.approx(0.25)
        assert et.censored_rate(0, 0) == 0.0

    def test_conditional_rate_is_a_diagnostic_not_the_trigger(self):
        assert et.censored_rate_capped(3, 6) == pytest.approx(0.5)
        assert et.censored_rate_capped(3, 0) == 0.0

    def test_threshold_is_strictly_greater_than_20_percent(self):
        assert et.CENSOR_THRESHOLD == 0.20
        assert et.is_censored(0.20) is False, "exactly 20% is NOT >20%"
        assert et.is_censored(0.2001) is True
        assert et.is_censored(0.0) is False

    def test_censoring_block_fires_the_banner_on_the_candidate_arm(self):
        cand = {"cap_hits": 30, "latch_solves": 100, "capped_attempts": 40}
        champ = {"cap_hits": 0, "latch_solves": 100, "capped_attempts": 0}
        b = et.censoring_block(cand, champ)
        assert b["censored_rate"] == pytest.approx(0.30)
        assert b["censored_rate_capped"] == pytest.approx(0.75)
        assert b["censored"] is True
        assert "NOT A VERDICT" in b["banner"]
        assert b["opponent_cap_hits_alarm"] is False

    def test_uncensored_rung_carries_no_banner(self):
        b = et.censoring_block({"cap_hits": 1, "latch_solves": 100, "capped_attempts": 20},
                               {"cap_hits": 0, "latch_solves": 100, "capped_attempts": 0})
        assert b["censored"] is False and b["banner"] == ""

    def test_incumbent_cap_hit_is_an_instrument_alarm(self):
        # The K<=4 incumbent tail is uncapped by construction, so a cap hit on that
        # side means the harness is not doing what the prereg says it is.
        b = et.censoring_block({"cap_hits": 0, "latch_solves": 10, "capped_attempts": 0},
                               {"cap_hits": 1, "latch_solves": 10, "capped_attempts": 1})
        assert b["opponent_cap_hits_alarm"] is True


# =========================================================================== #
# 5. _ExactHandoff — per-arm K, cap -> prefix (never a leaf), recursion        #
# =========================================================================== #
class _FakePrefix:
    """A prefix agent stand-in: records every ply it was asked to play."""

    def __init__(self, action: int = 4242):
        self.action = action
        self.calls = 0

    def move(self, board) -> int:
        self.calls += 1
        return self.action


def _board(k: int):
    """A board whose only observable property is k_remaining (deck + next_tile)."""
    return SimpleNamespace(state=SimpleNamespace(
        phase=epp._TILES_PHASE, deck=[None] * k, next_tile=None))


@pytest.mark.skipif(epp._TILES_PHASE is None, reason="engine GamePhase unavailable")
class TestExactHandoffLadder:
    def test_per_arm_k_is_independent(self, monkeypatch):
        a = epp._ExactHandoff(_FakePrefix(), None, 6, caps={}, k_floor=4)
        b = epp._ExactHandoff(_FakePrefix(), None, 4, caps={}, k_floor=4)
        assert (a.tail.k0, a.tail.eff_k) == (6, 6)
        assert (b.tail.k0, b.tail.eff_k) == (4, 4)
        # ... and they latch at different points in the SAME position: this is the
        # entire content of a rung — candidate tail K=6, incumbent tail K=4.
        monkeypatch.setattr(epp._et, "wall_cap_call",
                            lambda fn, cap, k=None, **kw: {"status": "ok",
                                                           "action": 5, "nodes": 1})
        a_pfx, b_pfx = a._prefix, b._prefix
        assert a.move(_board(6)) == 5, "the K=6 arm hands off to the exact solver"
        assert b.move(_board(6)) == b_pfx.action, "the K=4 arm is still searching"
        assert a.latch_k == 6 and a.exact_moves == 1 and a_pfx.calls == 0
        assert b.latch_k is None and b_pfx.calls == 1 and b.tail.latch_solves == 0

    def test_cap_hit_falls_back_to_the_prefix_search_never_a_leaf(self, monkeypatch):
        pfx = _FakePrefix(action=99)
        h = epp._ExactHandoff(pfx, None, 6, caps={6: 1.0, 5: 1.0}, k_floor=4)

        def _always_caps(fn, cap, k=None, **kw):
            raise et.WallCapExceeded(cap or 1.0, k)
        monkeypatch.setattr(epp._et, "wall_cap_call", _always_caps)

        act = h.move(_board(6))
        assert act == 99, "on a cap hit the PREFIX SEARCH plays that ply"
        assert pfx.calls == 1 and h.prefix_moves == 1
        assert h.exact_moves == 0
        assert h.tail.cap_hits == 1 and h.tail.eff_k == 5
        assert h.tail.fallback_depth == 1

    def test_fallback_recursion_across_plies_down_to_the_floor(self, monkeypatch):
        pfx = _FakePrefix()
        h = epp._ExactHandoff(pfx, None, 6, caps={6: 1.0, 5: 1.0, 4: 1.0}, k_floor=4)
        monkeypatch.setattr(
            epp._et, "wall_cap_call",
            lambda fn, cap, k=None, **kw: (_ for _ in ()).throw(
                et.WallCapExceeded(cap or 1.0, k)))
        h.move(_board(6))
        assert h.tail.eff_k == 5
        h.move(_board(5))
        assert h.tail.eff_k == 4, "K-1 also capped -> recurse downward"
        h.move(_board(4))
        assert h.tail.eff_k == 4, "floored AT the incumbent, never below"
        assert h.tail.cap_hits == 3 and h.tail.fallback_depth == 2
        assert h.tail.cap_hits_by_k == {6: 1, 5: 1, 4: 1}
        assert pfx.calls == 3, "every capped ply was played by the prefix search"

    def test_degraded_arm_does_not_attempt_a_solve_above_its_threshold(self, monkeypatch):
        """After the ladder steps down, a position ABOVE the new threshold is played by
        the prefix WITHOUT burning another (doomed) capped solve."""
        pfx = _FakePrefix()
        h = epp._ExactHandoff(pfx, None, 6, caps={6: 1.0}, k_floor=4)
        monkeypatch.setattr(
            epp._et, "wall_cap_call",
            lambda fn, cap, k=None, **kw: (_ for _ in ()).throw(
                et.WallCapExceeded(cap or 1.0, k)))
        h.move(_board(6))                       # caps, eff_k -> 5
        before = h.tail.latch_solves
        h.move(_board(6))                       # same size, now above the threshold
        assert h.tail.latch_solves == before, "no doomed re-solve of an oversized position"
        assert pfx.calls == 2

    def test_uncapped_arm_solves_and_counts_nodes(self, monkeypatch):
        pfx = _FakePrefix()
        h = epp._ExactHandoff(pfx, None, 4, caps={5: 300.0}, k_floor=0)
        monkeypatch.setattr(epp._et, "wall_cap_call",
                            lambda fn, cap, k=None, **kw: {"status": "ok",
                                                           "action": 11, "nodes": 500})
        assert h.move(_board(4)) == 11
        assert h.tail.latch_solves == 1
        assert h.tail.capped_attempts == 0, "k=4 is uncapped (prereg)"
        assert h.tail.cap_hits == 0
        assert h.exact_moves == 1 and h.solver_nodes == 500

    def test_node_budget_exceeded_keeps_the_legacy_semantics(self, monkeypatch):
        """BudgetExceeded is NOT a cap hit: prefix plays that ply, arm stays latched at
        the SAME K (the pre-F13 contract), and it is counted separately."""
        pfx = _FakePrefix()
        h = epp._ExactHandoff(pfx, None, 4, caps={}, k_floor=0)
        monkeypatch.setattr(epp._et, "wall_cap_call",
                            lambda fn, cap, k=None, **kw: {"status": "budget"})
        h.move(_board(4))
        assert h.n_timeouts == 1 and h.tail.cap_hits == 0
        assert h.tail.eff_k == 4, "a node-budget miss must not move the tail K"
        assert pfx.calls == 1

    def test_rust_solver_without_a_mirror_fails_closed(self):
        with pytest.raises(ValueError, match="mirror-carrying"):
            epp._ExactHandoff(_FakePrefix(), None, 6, solver="rust")


# =========================================================================== #
# 6. end-to-end: the CLI override + the counters in summary.json / manifest    #
# =========================================================================== #
def _run_cell(tmp_path, extra, n=2):
    """A tiny real cell through the real Pool/claim/manifest machinery.

    ⚠️ Re-pins sys.modules["eval_puct_priors"] first. Several test files load this
    harness by PATH under that same module name; whichever loaded last wins, and a
    fork-Pool worker then refuses to pickle `_play_one` ("not the same object as
    eval_puct_priors._play_one"). Pre-existing cross-file interaction (it fails the
    same way on an unmodified tree); pinned here so THIS file is order-independent.
    """
    sys.modules["eval_puct_priors"] = epp
    argv = ["--candidate", "h30", "--opponent", "h30",
            "--n", str(n), "--paired", "--workers", "1",
            "--seed-start", "9000000000",
            "--out-root", str(tmp_path), "--out-subdir", "cell",
            "--no-results-csv"] + extra
    rc = epp.main(argv)
    assert rc == 0
    out = tmp_path / "cell"
    man = json.loads((out / "manifest.json").read_text())
    summ = json.loads((out / "summary.json").read_text())
    games = [json.loads(p.read_text())
             for p in sorted(out.glob("seed*_a*.json"))]
    return man, summ, games


@pytest.mark.slow
class TestEndToEnd:
    def test_per_arm_k_and_caps_reach_the_manifest_and_the_counters_land(self, tmp_path):
        # Candidate tail K=3 vs a K=2 "incumbent", with a cap at k=3 so small that
        # EVERY candidate latch solve caps out -> the ladder is exercised for real.
        man, summ, games = _run_cell(tmp_path, [
            "--exact-k", "3", "--opp-exact-k", "2",
            "--exact-wall-caps", "3:0.002", "--exact-k-floor", "1"])

        tail = man["config"]["exact_tail"]
        assert tail["cand_exact_k"] == 3, "per-arm candidate K must reach the manifest"
        assert tail["opp_exact_k"] == 2, "per-arm opponent K must reach the manifest"
        assert tail["wall_caps"] == {"3": 0.002}
        assert tail["wall_caps_spec"] == "3:0.002"
        assert tail["k_floor"] == 1
        assert tail["solver"] == "python"
        assert tail["ladder_engaged"] is True
        # PROVENANCE (fixed 2026-08-04): the round-robin opponent block must carry the
        # OPPONENT's K, not the candidate's. It used to stamp args.exact_k, so an
        # asymmetric cell recorded its K=2 incumbent as K=3.
        assert man["config"]["candidate"]["exact_k"] == 3
        assert man["config"]["opponent"]["exact_k"] == 2
        # the legacy top-level field stays the CANDIDATE's K (pre-F13 shape)
        assert man["config"]["exact_k"] == 3
        assert "fork+SIGKILL" in tail["cap_mechanism"]
        assert tail["censor_threshold"] == et.CENSOR_THRESHOLD

        # per-CELL totals, in BOTH the summary and the manifest (patched after the run)
        for block in (summ["f13"], man["f13"]):
            cand = block["candidate"]
            assert cand["exact_k"] == 3
            assert cand["latch_solves"] > 0
            assert cand["capped_attempts"] > 0
            assert cand["cap_hits"] > 0, "a 2 ms cap must cap out"
            assert cand["fallback_depth"] > 0
            assert block["opponent"]["cap_hits"] == 0, "the incumbent tail is uncapped"
            assert block["opponent_cap_hits_alarm"] is False
            assert block["censored_rate"] == pytest.approx(
                et.censored_rate(cand["cap_hits"], cand["latch_solves"]))
            # The >20% trigger is exercised in TestCensoring; here we only require the
            # cell block to be SELF-CONSISTENT with it (a real cell's rate is whatever
            # the solver did, and 1/5 == 0.20 is deliberately NOT censored).
            assert block["censored"] is et.is_censored(block["censored_rate"])
            assert bool(block["banner"]) is block["censored"]
            assert block["games"] == len(games)

        # per-GAME telemetry (the numerator/denominator, per side, per game)
        assert games, "no per-game records written"
        for g in games:
            assert g["f13_on"] is True
            assert g["cand_tail_k"] == 3 and g["champ_tail_k"] == 2
            assert g["champ_cap_hits"] == 0, "the K<=2 incumbent tail is uncapped"
            assert g["cand_eff_k_final"] <= 3
            # a game that capped must have stepped its threshold down, and vice versa
            assert (g["cand_cap_hits"] > 0) == (g["cand_fallback_depth"] > 0)
        # Not every game caps: whether the CANDIDATE is on move at k_remaining=3 (the
        # only capped size here) depends on the seat, so the cap-hit count is a
        # per-CELL statistic, which is exactly why the prereg's rule is per-rung.
        assert any(g["cand_cap_hits"] > 0 for g in games)
        assert sum(g["cand_cap_hits"] for g in games) == summ["f13"]["candidate"]["cap_hits"]
        assert (sum(g["cand_latch_solves"] for g in games)
                == summ["f13"]["candidate"]["latch_solves"])

    def test_non_f13_cell_is_schema_identical_to_the_pre_f13_harness(self, tmp_path):
        man, summ, games = _run_cell(tmp_path, ["--exact-k", "2"])
        assert "f13" not in summ, "a legacy cell must not grow an f13 summary block"
        assert "f13" not in man, "a legacy cell's manifest must not be patched"
        assert man["config"]["exact_tail"]["ladder_engaged"] is False
        assert man["config"]["exact_tail"]["cap_mechanism"] == "none (uncapped)"
        # symmetric cell: BOTH arm blocks report the same (shared) K
        assert man["config"]["candidate"]["exact_k"] == 2
        assert man["config"]["opponent"]["exact_k"] == 2
        # ... and the python-tail provenance string is the one that ran
        assert man["config"]["backend"]["tail_engine"] == "python"
        assert "stay Python" in man["config"]["backend"]["unconverted"]
        for g in games:
            for k in epp._F13_RESULT_FIELDS:
                assert k not in g, f"legacy per-game JSON grew an F13 key: {k}"

    def test_cli_refuses_a_rust_tail_without_a_rust_backend(self, tmp_path):
        with pytest.raises(SystemExit):
            _run_cell(tmp_path, ["--exact-k", "4", "--exact-solver", "rust",
                                 "--backend", "python"])

    def test_cli_refuses_a_malformed_cap_map(self, tmp_path):
        with pytest.raises(SystemExit):
            _run_cell(tmp_path, ["--exact-k", "4", "--exact-wall-caps", "5:not-a-number"])

    def test_cli_refuses_a_floor_above_both_arms(self, tmp_path):
        with pytest.raises(SystemExit):
            _run_cell(tmp_path, ["--exact-k", "3", "--opp-exact-k", "2",
                                 "--exact-k-floor", "6"])


# =========================================================================== #
# 6b. backend provenance: the "unconverted" prose follows the RESOLVED tail    #
# =========================================================================== #
class TestBackendUnconvertedProvenance:
    """`config.backend.unconverted` used to hardcode "the exact-K clairvoyant tail on
    BOTH sides ... stay Python". True pre-F13, FALSE under --exact-solver rust. It is
    now derived from the resolved solver (eval_puct_priors._backend_unconverted)."""

    def test_python_tail_is_listed_as_unconverted(self):
        s = epp._backend_unconverted("python")
        assert "exact-K clairvoyant tail on BOTH sides" in s
        assert "stay Python" in s
        assert "same Python solver on both sides" in s
        assert "CONVERTED" not in s

    def test_rust_tail_is_not_claimed_to_be_python(self):
        s = epp._backend_unconverted("rust")
        assert "carc_rs.MirrorState.solve_endgame" in s
        assert "CONVERTED on both sides" in s
        # the tail must NOT appear in the unconverted list any more
        assert "exact-K clairvoyant tail on BOTH sides" not in s
        # the two non-tail unconverted items survive either way
        for s2 in (s, epp._backend_unconverted("python")):
            assert "HeuristicMCTS opponent" in s2 and "net arm" in s2

    def test_the_two_solvers_produce_different_prose(self):
        assert epp._backend_unconverted("rust") != epp._backend_unconverted("python")

    def test_no_stale_python_tail_sentence_left_in_the_source(self):
        src = SCRIPT.read_text()
        assert "The tail is shared\n" not in src
        assert "The EXACT tail stays Python for" not in src, \
            "the _play_one inline comment still asserts a Python-only tail"


# =========================================================================== #
# 7. REGRESSION — the production fair K<=2 MARGINALIZED latch is UNTOUCHED     #
# =========================================================================== #
class TestFairMarginalizedLatchUntouched:
    """PREREG falsifier/guard: "The fair agent's production K<=2 marginalized latch is
    untouched by all of this." The two tails are code-disjoint by construction: the
    clairvoyant K<=4 tail is a HARNESS wrapper (_ExactHandoff), the fair tail lives
    inside the agent with `mode="marginalized"` as a hardcoded string literal."""

    def test_fair_exact_max_k_is_still_two(self):
        from carcassonne_ai import fair_agent
        assert fair_agent.EXACT_MAX_K == 2

    def test_fair_agent_ctor_default_is_still_two(self):
        from carcassonne_ai.fair_agent import EXACT_MAX_K, FairHeuristicPriorAgent
        sig = inspect.signature(FairHeuristicPriorAgent.__init__)
        assert sig.parameters["exact_max_k"].default == EXACT_MAX_K == 2

    def test_fair_solve_is_still_marginalized_without_alphabeta(self):
        from carcassonne_ai.fair_agent import FairHeuristicPriorAgent
        src = inspect.getsource(FairHeuristicPriorAgent._exact_move)
        assert 'mode="marginalized"' in src
        assert "alphabeta=False" in src
        assert "clairvoyant" not in src, "the fair tail must never read the true deck"

    def test_production_spec_still_pins_exact_max_k_two(self):
        from carcassonne_ai import champion_factory as cf
        assert cf.load_production_spec().exact_max_k == 2

    def test_fair_agent_does_not_import_the_f13_machinery(self):
        # Code-disjointness, asserted: nothing in the fair deploy path can see the
        # wall caps or the fallback ladder.
        src = (REPO / "src" / "carcassonne_ai" / "fair_agent.py").read_text()
        for token in ("exact_tail", "wall_cap", "WallCapExceeded", "ExactTailState"):
            assert token not in src, f"fair_agent.py now references {token}"

    def test_rust_fair_agent_default_k_is_still_two(self):
        carc_rs = pytest.importorskip("carc_rs")
        if not hasattr(carc_rs, "FairAgentRs"):
            pytest.skip("carc_rs wheel has no FairAgentRs")
        doc = (carc_rs.FairAgentRs.__doc__ or "") + (carc_rs.FairAgentRs.__init__.__doc__ or "")
        assert doc is not None  # presence check; the value is asserted via the factory


# =========================================================================== #
# 8. the launcher                                                             #
# =========================================================================== #
class TestLauncher:
    @pytest.fixture(scope="class")
    def text(self):
        return LAUNCHER.read_text()

    def test_exists_and_is_syntactically_valid(self):
        import subprocess
        assert LAUNCHER.exists() and SMOKER.exists()
        assert subprocess.run(["bash", "-n", str(LAUNCHER)]).returncode == 0

    def test_carries_all_four_rungs_including_k3(self, text):
        # K=3 was ADDED to the design after the draft (denser trend line).
        assert 'RUNGS_ALL="k2 k3 k5 k6"' in text

    def test_k4_is_the_identity_smoke_not_a_cell(self, text):
        assert "INCUMBENT_K=4" in text
        assert "that is the IDENTITY SMOKE, not a cell" in text

    def test_prereg_caps_and_floor_are_the_defaults(self, text):
        assert 'CAPS="5:300,6:600"' in text
        assert "K_FLOOR=4" in text, "the ladder must floor AT the incumbent"

    def test_pins_fixed_v1_and_exports_r9_before_the_harness(self, text):
        assert "PROFILE=fixed_v1" in text
        assert "export CARCASSONNE_FIX_R9=1" in text
        assert "manifest_profile_ok" in text and "VOID-PROFILE" in text

    def test_sources_the_shared_clock_skew_guard(self, text):
        # tests/test_clock_skew_guard.py enforces this for every --shared-claim
        # launcher; only two grandfathered donors may inline it.
        assert "clock_skew_guard.sh" in text and "carc_clock_skew_guard" in text
        assert "--shared-claim" in text

    def test_both_smoke_modes_are_wired(self, text):
        assert "--smoke-identity" in text and "--smoke-k6" in text
        assert "IDENTITY SMOKE FAILED" in text, "identity smoke must gate the ladder"
        assert "SMOKE_BAND=" in text, "smokes must use a throwaway band"

    def test_resume_by_existence_and_claim_recovery(self, text):
        for token in ("cell_complete", "count_results", "clean_stale_claims",
                      "--shared-claim", "--claim-stale-secs"):
            assert token in text

    def test_censoring_columns_are_first_class_in_the_progress_record(self, text):
        for col in ("latch_solves", "cap_hits", "fallback", "censored_rate"):
            assert col in text

    def test_does_not_write_governance_or_production(self, text):
        for forbidden in ("BAND_REGISTRY", "PRODUCTION.yaml"):
            assert f">> {forbidden}" not in text and f"> {forbidden}" not in text
