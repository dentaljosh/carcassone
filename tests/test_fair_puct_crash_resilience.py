"""``scripts/classical_search/eval_fair_puct.py`` — crash resilience.

THE BUG (2026-08-14, cell ``oc2_C_d16p0_deploy11008``). One game raising
``carc_rs.WindowTruncationError`` out of ``pool.imap_unordered`` killed the ENTIRE
pass, and every game in flight lost its ``--shared-claim`` claim file — 14 of 800
records gone (1 poisoned game + 13 collateral), across 16 relaunches that each
re-crashed on the identical position.

THE CONTRACT these tests pin (mirroring ``tests/test_joshuabot_h2h.py``, whose
harness solved the same problem on 2026-08-13):
  * a game that raises is RECORDED, not fatal;
  * its claim does not strand (that is what stalls the next resume);
  * the record can never be mistaken for a game result by any downstream reader;
  * ``n_failed`` / ``failure_rate`` reach ``summary.json`` AND ``manifest.json``,
    and are present as a ZERO, never as a missing key;
  * retries are BOUNDED — a deterministic crash cannot loop forever;
  * a zero-failure run is unchanged.

No game is played here (that is fleet compute): the game body is stubbed, which is
exactly the point — the guard must be independent of what raised.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "classical_search" / "eval_fair_puct.py"

_spec = importlib.util.spec_from_file_location("eval_fair_puct", SCRIPT)
efp = importlib.util.module_from_spec(_spec)
sys.modules["eval_fair_puct"] = efp
_spec.loader.exec_module(efp)


def _result(seed=5, a_seat=0):
    return efp.GameResult(
        seed=seed, a_seat=a_seat, info="fair", exact_k=4, k_dets=8, sims=1376,
        rung_sims=800, score_p0=70, score_p1=60, diff=10, won_by_champ=True,
        drew=False, elapsed_s=1.0, moves=70)


@pytest.fixture
def worker(monkeypatch, tmp_path):
    """A minimal ``_W`` — the guard must work with nothing but the cell identity."""
    for k, v in dict(info="fair", opponent="h800", exact_k=4, k_dets=8, sims=1376,
                     rung_sims=800, shared_claim=False, claim_host="testbox",
                     claim_stale=7200).items():
        monkeypatch.setitem(efp._W, k, v)
    return tmp_path


def _boom(exc=RuntimeError("EMPTY_MASK_DIAG={\"cause\":\"window_truncation\"}")):
    def _raise(*a, **kw):
        raise exc
    return _raise


# --------------------------------------------------------------------------- #
class TestARaiseIsRecordedNotFatal:
    def test_a_raise_becomes_a_failure_not_an_exception(self, worker, monkeypatch):
        monkeypatch.setattr(efp, "_play_one_inner", _boom())
        r = efp._play_one((str(worker), 11, 1, 3))
        assert isinstance(r, efp.GameFailure)
        assert (r.seed, r.a_seat) == (11, 1)
        assert r.exc_type == "RuntimeError"

    def test_the_record_lands_on_disk_with_the_diagnosis(self, worker, monkeypatch):
        monkeypatch.setattr(efp, "_play_one_inner", _boom())
        efp._play_one((str(worker), 11, 1, 3))
        rec = json.loads(efp._failed_path(worker, 11, 1).read_text())
        assert rec["failed"] is True
        assert rec["seed"] == 11 and rec["a_seat"] == 1
        assert rec["deck_seed"] == 11          # h2h-side spelling of the same number
        assert "EMPTY_MASK_DIAG" in rec["exc"]
        assert rec["traceback"]
        assert rec["info"] == "fair" and rec["opponent"] == "h800"

    def test_a_non_Exception_failure_is_still_recorded(self, worker, monkeypatch):
        # pyo3 PanicException is a BaseException, not an Exception.
        monkeypatch.setattr(efp, "_play_one_inner", _boom(BaseException("panic")))
        r = efp._play_one((str(worker), 12, 0, 3))
        assert isinstance(r, efp.GameFailure) and r.exc_type == "BaseException"

    @pytest.mark.parametrize("exc", [KeyboardInterrupt(), SystemExit(1)])
    def test_an_operator_interrupt_still_propagates(self, worker, monkeypatch, exc):
        monkeypatch.setattr(efp, "_play_one_inner", _boom(exc))
        with pytest.raises(type(exc)):
            efp._play_one((str(worker), 13, 0, 3))

    def test_a_failed_write_is_not_fatal_either(self, worker, monkeypatch):
        monkeypatch.setattr(efp, "_play_one_inner", _boom())
        monkeypatch.setattr(efp, "_save_failure", _boom(OSError("disk full")))
        r = efp._play_one((str(worker), 14, 0, 3))
        assert isinstance(r, efp.GameFailure)


class TestTheClaimDoesNotStrand:
    """The collateral half of the incident: a claim with no record stalls every
    later resume until someone hand-cleans it."""

    def test_the_claim_is_released_on_failure(self, worker, monkeypatch):
        monkeypatch.setitem(efp._W, "shared_claim", True)
        monkeypatch.setattr(efp, "_play_one_inner", _boom())
        efp._play_one((str(worker), 21, 0, 3))
        claim = efp._result_path(worker, 21, 0).with_suffix(".claim")
        assert not claim.exists(), "a failed game must not strand its claim"
        assert efp._failed_path(worker, 21, 0).exists()

    def test_the_claim_is_taken_before_the_game(self, worker, monkeypatch):
        """Sanity: the claim really was created, so the release above is real."""
        seen = {}
        monkeypatch.setitem(efp._W, "shared_claim", True)

        def _inner(out, seed, a_seat, p):
            seen["claim"] = p.with_suffix(".claim").exists()
            raise RuntimeError("boom")
        monkeypatch.setattr(efp, "_play_one_inner", _inner)
        efp._play_one((str(worker), 22, 0, 3))
        assert seen["claim"] is True

    def test_a_lost_claim_is_still_just_a_skip(self, worker, monkeypatch):
        monkeypatch.setitem(efp._W, "shared_claim", True)
        monkeypatch.setattr(efp, "_try_claim", lambda *a, **kw: False)
        assert efp._play_one((str(worker), 23, 0, 3)) is None
        assert not efp._failed_path(worker, 23, 0).exists()


class TestAFailureCanNeverBeReadAsAGame:
    def test_it_is_not_in_the_cell_dir_that_readers_glob(self, worker, monkeypatch):
        monkeypatch.setattr(efp, "_play_one_inner", _boom())
        efp._play_one((str(worker), 31, 0, 3))
        # the three glob shapes downstream readers actually use, all non-recursive
        for pat in ("*.json", "seed*_a*.json", "*seed*.json"):
            assert list(worker.glob(pat)) == [], f"{pat} must not see a failure record"

    def test_try_load_never_returns_one(self, worker, monkeypatch):
        monkeypatch.setattr(efp, "_play_one_inner", _boom())
        efp._play_one((str(worker), 32, 0, 3))
        assert efp._try_load(efp._result_path(worker, 32, 0)) is None

    def test_it_carries_no_statistic_bearing_key(self, worker, monkeypatch):
        monkeypatch.setattr(efp, "_play_one_inner", _boom())
        efp._play_one((str(worker), 33, 1, 3))
        rec = json.loads(efp._failed_path(worker, 33, 1).read_text())
        for k in ("diff", "won_by_champ", "drew", "score_p0", "score_p1"):
            assert k not in rec, f"{k} would let a half-game leak into a statistic"

    def test_a_failure_is_never_appended_to_results(self, worker, monkeypatch):
        """The driver appends only GameResults, so `_summary` is safe by type."""
        monkeypatch.setattr(efp, "_play_one_inner", _boom())
        r = efp._play_one((str(worker), 34, 0, 3))
        assert not isinstance(r, efp.GameResult)


class TestRetriesAreBounded:
    def _fail(self, out, seed, a_seat, max_attempts, monkeypatch):
        monkeypatch.setattr(efp, "_play_one_inner", _boom())
        return efp._play_one((str(out), seed, a_seat, max_attempts))

    def test_attempts_accumulate_across_passes(self, worker, monkeypatch):
        a = self._fail(worker, 41, 0, 3, monkeypatch)
        b = self._fail(worker, 41, 0, 3, monkeypatch)
        assert (a.attempts, b.attempts) == (1, 2)
        assert (a.permanent, b.permanent) == (False, False)

    def test_the_budget_flips_the_record_permanent(self, worker, monkeypatch):
        for _ in range(2):
            self._fail(worker, 42, 0, 2, monkeypatch)
        rec = json.loads(efp._failed_path(worker, 42, 0).read_text())
        assert rec["attempts"] == 2 and rec["permanent"] is True

    def test_a_failed_game_is_done_by_default(self):
        todo = [("o", 51, 0, 3), ("o", 52, 0, 3)]
        keep, reopened, skipped, exhausted = efp._filter_failed_todo(
            todo, {(51, 0): {"attempts": 1}}, retry_failed=False, max_attempts=3)
        assert keep == [("o", 52, 0, 3)] and skipped == [("o", 51, 0, 3)]
        assert reopened == [] and exhausted == []

    def test_retry_failed_reopens_exactly_the_failed_games(self):
        todo = [("o", 51, 0, 3), ("o", 52, 0, 3)]
        keep, reopened, skipped, exhausted = efp._filter_failed_todo(
            todo, {(51, 0): {"attempts": 1}}, retry_failed=True, max_attempts=3)
        assert keep == todo and reopened == [("o", 51, 0, 3)]
        assert skipped == [] and exhausted == []

    def test_retry_failed_stops_at_the_budget(self):
        """⚠️ THE TERMINATION GUARANTEE: a wrapper looping --retry-failed on a
        deterministic crash converges instead of grinding forever."""
        todo = [("o", 51, 0, 3)]
        keep, reopened, skipped, exhausted = efp._filter_failed_todo(
            todo, {(51, 0): {"attempts": 3}}, retry_failed=True, max_attempts=3)
        assert keep == [] and exhausted == todo and reopened == []

    def test_a_pass_always_terminates(self, worker, monkeypatch):
        """Simulate the observed incident: the same deterministic crash, relaunched.
        Pass 1 records it; every later default pass has an EMPTY todo."""
        todo = [(str(worker), 61, 0, 3)]
        self._fail(worker, 61, 0, 3, monkeypatch)
        for _ in range(20):                       # 16 relaunches happened for real
            todo2, _, skipped, _ = efp._filter_failed_todo(
                todo, efp.load_failures(worker), False, 3)
            assert todo2 == [] and skipped == todo


class TestTheRateIsVisible:
    def test_a_clean_run_states_a_zero_not_a_missing_key(self):
        b = efp._failure_block([_result()], [])
        assert b["n_failed"] == 0 and b["failure_rate"] == 0.0
        assert b["validity_trigger_fired"] is False

    def test_the_rate_is_over_everything_attempted(self):
        b = efp._failure_block([_result(1), _result(2), _result(3)],
                               [{"seed": 4, "a_seat": 1, "exc_type": "RuntimeError"}])
        assert b["n_failed"] == 1 and b["failure_rate"] == pytest.approx(0.25)
        assert b["failed_by_seat"] == {"0": 0, "1": 1}
        assert b["failed_cells"][0]["seed"] == 4

    def test_the_prereg_validity_trigger_fires_above_half_a_percent(self):
        clean = efp._failure_block([_result(i) for i in range(999)],
                                   [{"seed": 1, "a_seat": 0}])
        assert clean["failure_rate"] <= efp.FAILURE_RATE_TRIGGER
        assert clean["validity_trigger_fired"] is False
        dirty = efp._failure_block([_result(i) for i in range(99)],
                                   [{"seed": 1, "a_seat": 0}])
        assert dirty["validity_trigger_fired"] is True

    def test_the_trigger_is_shouted_not_just_stamped(self, capsys):
        efp._shout_failures(efp._failure_block(
            [_result(i) for i in range(9)], [{"seed": 1, "a_seat": 0}]), 9)
        out = capsys.readouterr().out
        assert "FAILED GAME(S)" in out and "VALIDITY TRIGGER FIRED" in out

    def test_a_clean_run_shouts_nothing(self, capsys):
        efp._shout_failures(efp._failure_block([_result()], []), 1)
        assert capsys.readouterr().out == ""

    def test_the_summary_carries_the_exclusion_block(self):
        summ = efp._summary([_result(1), _result(2)], "fair", 4, 8, 1376, 800,
                            failures=[{"seed": 3, "a_seat": 0,
                                       "exc_type": "WindowTruncationError"}])
        assert summ["n_failed"] == 1
        assert summ["failure_rate"] == pytest.approx(1 / 3)
        assert summ["failed_cells"][0]["exc_type"] == "WindowTruncationError"

    def test_a_failure_moves_no_statistic(self):
        """The exclusion is an exclusion: n/W/elo are computed on the scored games
        only, and are identical whether or not a failure sits beside them."""
        keys = ("n", "W", "D", "L", "winrate", "elo", "avg_diff",
                "paired_mean_margin", "paired_z", "n_paired")
        base = efp._summary([_result(1, 0), _result(1, 1)], "fair", 4, 8, 1376, 800)
        with_fail = efp._summary([_result(1, 0), _result(1, 1)], "fair", 4, 8, 1376,
                                 800, failures=[{"seed": 9, "a_seat": 0}])
        assert {k: base[k] for k in keys} == {k: with_fail[k] for k in keys}


class TestFailedClasses:
    """`failed_classes` (ADDITIVE, 2026-08-23) — the per-failure diagnostic-class
    histogram commissioned by READOUT_B64.md's "SPEC-vs-BUILDABLE" clause 3 /
    RULING 3. Sibling to `failed_cells` in the same exclusion block; the
    adjudicator reads it at `summary.json::failed_classes`."""

    def test_n_failed_zero_gives_an_empty_dict_not_a_missing_key(self):
        b = efp._failure_block([_result()], [])
        assert b["n_failed"] == 0
        assert "failed_classes" in b
        assert b["failed_classes"] == {}

    def test_a_mix_of_classes_including_an_unrecognised_one(self):
        bad = [
            {"seed": 1, "a_seat": 0, "exc_type": "PanicException"},
            {"seed": 2, "a_seat": 1, "exc_type": "PanicException"},
            {"seed": 3, "a_seat": 0, "exc_type": "IndexError"},
        ]
        b = efp._failure_block([_result()], bad)
        assert b["failed_classes"] == {"PanicException": 2, "other:IndexError": 1}

    def test_window_truncation_takes_precedence_over_a_generic_exc_type(self):
        """A truncation failure can carry `exc_type == 'RuntimeError'` (see
        `carcassonne_ai.window_truncation.is_window_truncation` — it classifies by
        payload, not just class identity). The generic type name must not shadow
        the semantic class the `window_truncation` flag already knows."""
        bad = [{"seed": 1, "a_seat": 0, "exc_type": "RuntimeError",
               "window_truncation": True}]
        b = efp._failure_block([_result()], bad)
        assert b["failed_classes"] == {"WindowTruncationError": 1}
        assert "other:RuntimeError" not in b["failed_classes"]

    def test_the_histogram_sums_to_n_failed(self):
        bad = [
            {"seed": 1, "a_seat": 0, "exc_type": "PanicException"},
            {"seed": 2, "a_seat": 1, "exc_type": "RuntimeError",
             "window_truncation": True},
            {"seed": 3, "a_seat": 0, "exc_type": "IndexError"},
            {"seed": 4, "a_seat": 1, "exc_type": "ValueError"},
        ]
        b = efp._failure_block([_result()], bad)
        assert b["n_failed"] == len(bad) == 4
        assert sum(b["failed_classes"].values()) == b["n_failed"]

    def test_a_missing_exc_type_is_still_classified_not_dropped(self):
        b = efp._failure_block([_result()], [{"seed": 1, "a_seat": 0}])
        assert sum(b["failed_classes"].values()) == 1

    def test_failed_classes_reaches_the_manifest(self, tmp_path):
        (tmp_path / "manifest.json").write_text(json.dumps({"kind": "eval_fair_puct"}))
        block = efp._failure_block([_result()], [
            {"seed": 1, "a_seat": 0, "exc_type": "PanicException"},
            {"seed": 2, "a_seat": 1, "exc_type": "IndexError"},
        ])
        efp._patch_failure_manifest(tmp_path, block, n_failed_this_leg=2)
        man = json.loads((tmp_path / "manifest.json").read_text())
        assert man["failed_classes"] == {"PanicException": 1, "other:IndexError": 1}

    def test_a_clean_manifest_stamps_an_empty_dict(self, tmp_path):
        (tmp_path / "manifest.json").write_text(json.dumps({"kind": "eval_fair_puct"}))
        efp._patch_failure_manifest(tmp_path, efp._failure_block([_result()], []), 0)
        man = json.loads((tmp_path / "manifest.json").read_text())
        assert man["failed_classes"] == {}

    def test_the_summary_carries_failed_classes_too(self):
        summ = efp._summary([_result(1), _result(2)], "fair", 4, 8, 1376, 800,
                            failures=[{"seed": 3, "a_seat": 0,
                                       "exc_type": "WindowTruncationError"}])
        assert summ["failed_classes"] == {"WindowTruncationError": 1}

    def test_existing_keys_are_unchanged_by_the_addition(self):
        """ADDITIVE ONLY: no existing key's name/type/value moves."""
        bad = [{"seed": 4, "a_seat": 1, "exc_type": "RuntimeError"}]
        b = efp._failure_block([_result(1), _result(2), _result(3)], bad)
        assert b["n_failed"] == 1 and b["failure_rate"] == pytest.approx(0.25)
        assert b["failed_by_seat"] == {"0": 0, "1": 1}
        assert b["failed_cells"][0]["seed"] == 4
        assert set(b["failed_cells"][0].keys()) == {
            "seed", "a_seat", "attempts", "permanent", "exc_type", "exc",
            "window_truncation", "window_diag"}


class TestItReachesTheManifest:
    def _manifest(self, tmp_path):
        (tmp_path / "manifest.json").write_text(json.dumps({"kind": "eval_fair_puct"}))
        return tmp_path

    def test_n_failed_reaches_the_manifest(self, tmp_path):
        out = self._manifest(tmp_path)
        block = efp._failure_block([_result(i) for i in range(9)],
                                   [{"seed": 1, "a_seat": 0, "exc_type": "RuntimeError"}])
        efp._patch_failure_manifest(out, block, n_failed_this_leg=1)
        man = json.loads((out / "manifest.json").read_text())
        assert man["n_failed"] == 1
        assert man["n_failed_this_leg"] == 1
        assert man["validity_trigger_fired"] is True
        assert man["failed_by_seat"] == {"0": 1, "1": 0}
        assert man["failed_cells"][0]["seed"] == 1
        assert man["kind"] == "eval_fair_puct"      # provenance untouched

    def test_a_clean_cell_stamps_a_zero(self, tmp_path):
        out = self._manifest(tmp_path)
        efp._patch_failure_manifest(out, efp._failure_block([_result()], []), 0)
        man = json.loads((out / "manifest.json").read_text())
        assert man["n_failed"] == 0 and man["failure_rate"] == 0.0
        assert man["validity_trigger_fired"] is False


class TestAResolvedFailureIsNotAFailure:
    """fail -> --retry-failed -> SUCCEED must leave a cell reporting n_failed == 0.

    The stale record would otherwise inflate `failure_rate`, which is the input to
    the PRE-REGISTERED VALIDITY TRIGGER (>0.5% ⇒ stop and investigate) — an
    overstated rate can void a cell that actually completed cleanly."""

    def _fail_then_succeed(self, out, monkeypatch, seed=101, a_seat=0):
        monkeypatch.setattr(efp, "_play_one_inner", _boom())
        efp._play_one((str(out), seed, a_seat, 3))          # pass 1: crash
        assert efp._failed_path(out, seed, a_seat).exists()

        def _ok(o, s, a, p):                                 # pass 2: retry works
            r = _result(s, a)
            efp._save(p, r)
            return r
        monkeypatch.setattr(efp, "_play_one_inner", _ok)
        return efp._play_one((str(out), seed, a_seat, 3))

    def test_the_retry_returns_a_real_result(self, worker, monkeypatch):
        r = self._fail_then_succeed(worker, monkeypatch)
        assert isinstance(r, efp.GameResult) and r.diff == 10

    def test_the_record_is_stamped_resolved_not_deleted(self, worker, monkeypatch):
        self._fail_then_succeed(worker, monkeypatch)
        p = efp._failed_path(worker, 101, 0)
        assert p.exists(), "the forensic trail must survive — never deleted"
        rec = json.loads(p.read_text())
        assert rec["resolved"] is True and "resolved_at" in rec
        # the diagnosis itself is intact
        assert rec["window_diag"] == {"cause": "window_truncation"}
        assert rec["exc_type"] == "RuntimeError" and rec["traceback"]

    def test_load_failures_excludes_it_by_default(self, worker, monkeypatch):
        self._fail_then_succeed(worker, monkeypatch)
        assert efp.load_failures(worker) == {}
        assert (101, 0) in efp.load_failures(worker, include_resolved=True)

    def test_the_summary_reports_zero_failures(self, worker, monkeypatch):
        self._fail_then_succeed(worker, monkeypatch)
        recs = list(efp.load_failures(worker, include_resolved=True).values())
        summ = efp._summary([_result(101, 0)], "fair", 4, 8, 1376, 800,
                            failures=[r for r in recs if not r.get("resolved")],
                            resolved=[r for r in recs if r.get("resolved")])
        assert summ["n_failed"] == 0
        assert summ["failure_rate"] == 0.0
        assert summ["failed_cells"] == []
        assert summ["validity_trigger_fired"] is False
        # …but the flaky game is still discoverable from the summary alone
        assert summ["n_resolved_failures"] == 1
        assert summ["resolved_failed_cells"][0]["seed"] == 101
        assert summ["resolved_failed_cells"][0]["window_truncation"] is True

    def test_the_manifest_reports_zero_failures(self, worker, monkeypatch):
        self._fail_then_succeed(worker, monkeypatch)
        (worker / "manifest.json").write_text(json.dumps({"kind": "eval_fair_puct"}))
        recs = list(efp.load_failures(worker, include_resolved=True).values())
        block = efp._failure_block([_result(101, 0)],
                                   [r for r in recs if not r.get("resolved")],
                                   [r for r in recs if r.get("resolved")])
        efp._patch_failure_manifest(worker, block, n_failed_this_leg=0)
        man = json.loads((worker / "manifest.json").read_text())
        assert man["n_failed"] == 0 and man["failure_rate"] == 0.0
        assert man["validity_trigger_fired"] is False
        assert man["n_resolved_failures"] == 1

    def test_a_resolved_failure_cannot_trip_the_validity_trigger(self, worker,
                                                                 monkeypatch):
        """The exact regression: one resolved failure in an 800-game cell must not
        read as 0.125% — it must read as 0.00%."""
        self._fail_then_succeed(worker, monkeypatch)
        recs = list(efp.load_failures(worker, include_resolved=True).values())
        block = efp._failure_block([_result(i) for i in range(800)],
                                   [r for r in recs if not r.get("resolved")],
                                   [r for r in recs if r.get("resolved")])
        assert block["n_failed"] == 0 and block["failure_rate"] == 0.0

    def test_an_unresolved_failure_still_counts(self, worker, monkeypatch):
        """Guard the guard: the exclusion must not swallow a REAL failure."""
        monkeypatch.setattr(efp, "_play_one_inner", _boom())
        efp._play_one((str(worker), 102, 1, 3))
        recs = list(efp.load_failures(worker).values())
        assert len(recs) == 1 and recs[0]["resolved"] is False
        assert efp._failure_block([_result()], recs)["n_failed"] == 1

    def test_the_resolved_note_is_printed_but_trips_nothing(self, worker,
                                                            monkeypatch, capsys):
        self._fail_then_succeed(worker, monkeypatch)
        recs = list(efp.load_failures(worker, include_resolved=True).values())
        block = efp._failure_block([_result(101, 0)], [], recs)
        efp._shout_failures(block, 1)
        out = capsys.readouterr().out
        assert "RESOLVED by a later successful retry" in out
        assert "VALIDITY TRIGGER FIRED" not in out
        assert "FAILED GAME(S)" not in out

    def test_a_peers_result_resolves_our_record(self, worker, monkeypatch):
        """--shared-claim: another box may have played the successful retry, so the
        RESULT FILE is the arbiter — no bookkeeping of ours is required."""
        monkeypatch.setattr(efp, "_play_one_inner", _boom())
        efp._play_one((str(worker), 103, 0, 3))
        assert list(efp.load_failures(worker)) == [(103, 0)]
        efp._save(efp._result_path(worker, 103, 0), _result(103, 0))   # the peer
        assert efp.load_failures(worker) == {}

    def test_marking_is_idempotent_and_cheap_when_clean(self, worker):
        efp._mark_failure_resolved(worker, 104, 0)          # no record: no-op
        assert not (worker / efp.FAILED_DIRNAME).exists()


class TestLoadFailures:
    def test_it_reads_back_what_the_worker_wrote(self, worker, monkeypatch):
        monkeypatch.setattr(efp, "_play_one_inner", _boom())
        efp._play_one((str(worker), 71, 0, 3))
        efp._play_one((str(worker), 72, 1, 3))
        assert sorted(efp.load_failures(worker)) == [(71, 0), (72, 1)]

    def test_a_missing_dir_is_empty_not_an_error(self, tmp_path):
        assert efp.load_failures(tmp_path) == {}

    def test_a_torn_record_is_skipped_and_left_alone(self, worker):
        p = efp._failed_path(worker, 73, 0)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{"failed": true, "seed": 7')       # dirty-crash tail
        assert efp.load_failures(worker) == {}
        assert p.exists(), "a failure record is evidence — never unlinked"


class TestAZeroFailureRunIsUnchanged:
    def test_a_played_game_returns_untouched(self, worker, monkeypatch):
        r = _result(81, 0)
        monkeypatch.setattr(efp, "_play_one_inner", lambda *a, **kw: r)
        assert efp._play_one((str(worker), 81, 0, 3)) is r
        assert not (worker / efp.FAILED_DIRNAME).exists()

    def test_a_cached_game_short_circuits_as_before(self, worker):
        p = efp._result_path(worker, 82, 0)
        efp._save(p, _result(82, 0))
        got = efp._play_one((str(worker), 82, 0, 3))
        assert isinstance(got, efp.GameResult) and got.diff == 10

    def test_the_task_tuple_stays_backward_compatible(self, worker, monkeypatch):
        """A 3-tuple (the pre-change shape) still runs, with a budget of 1."""
        monkeypatch.setattr(efp, "_play_one_inner", _boom())
        r = efp._play_one((str(worker), 83, 0))
        assert isinstance(r, efp.GameFailure) and r.permanent is True

    def test_the_result_json_schema_did_not_move(self, worker):
        efp._save(efp._result_path(worker, 84, 0), _result(84, 0))
        keys = set(json.loads(efp._result_path(worker, 84, 0).read_text()))
        assert "failed" not in keys and "attempts" not in keys


class TestTheFlagsMirrorH2H:
    def test_retry_failed_is_off_by_default_and_spelled_as_in_h2h(self):
        # the parser is built inside main(), so assert against the source: same
        # flag spelling and same default-off as scripts/joshuabot/h2h.py.
        h2h_src = (REPO / "scripts" / "joshuabot" / "h2h.py").read_text()
        src = SCRIPT.read_text()
        assert '"--retry-failed", action="store_true"' in h2h_src
        assert '"--retry-failed", action="store_true"' in src
        assert '"--max-attempts", type=int, default=3' in src

    def test_the_field_names_match_the_h2h_record(self, worker, monkeypatch):
        """The `ms_ratio` lesson (commit 56c69022): two harnesses, ONE convention."""
        monkeypatch.setattr(efp, "_play_one_inner", _boom())
        efp._play_one((str(worker), 91, 0, 3))
        rec = json.loads(efp._failed_path(worker, 91, 0).read_text())
        for k in ("failed", "exc_type", "exc", "traceback",
                  "window_truncation", "window_diag"):
            assert k in rec, f"h2h.failed_record carries {k}; this must too"
