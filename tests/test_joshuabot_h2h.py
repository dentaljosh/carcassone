"""``scripts/joshuabot/h2h.py`` — the pure parts of the deck-paired H2H driver.

The champion-budget game loop is not exercised here (that is fleet compute); what
is exercised is everything that decides WHAT gets played and HOW it is summarised:
cell construction (deck pairing), the resume contract, the paired statistic, and —
crucially — that ``JoshuaBot`` really does drive ``play_harness.play_game`` with no
harness change, which is the integration claim the whole instrument rests on.
"""
from __future__ import annotations

import importlib
import json
import os
import random
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HUMAN_ANCHOR = REPO / "scripts" / "human_anchor"
JOSHUABOT = REPO / "scripts" / "joshuabot"


def _load_h2h():
    """Import the driver as the top-level module ``h2h``.

    ⚠️ NOT ``spec_from_file_location`` under a synthetic name: the resilience
    test below runs the REAL spawn pool, and ``multiprocessing`` pickles
    ``_play_cell`` by ``__module__`` + ``__qualname__``. A synthetic module name
    is unimportable in the child, so the driver must be reachable by a name that
    is on ``sys.path`` (which spawn transfers to the child)."""
    for p in (str(REPO / "scripts"), str(JOSHUABOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    return importlib.import_module("h2h")


H2H = _load_h2h()


class TestCells:
    def test_every_deck_gets_both_seatings_adjacently(self):
        cells = H2H.build_cells([10, 11], set())
        assert cells == [(10, 0), (10, 1), (11, 0), (11, 1)]

    def test_resume_skips_finished_cells(self):
        cells = H2H.build_cells([10, 11], {(10, 0), (11, 1)})
        assert cells == [(10, 1), (11, 0)]

    def test_champion_seed_is_a_pure_function_of_the_cell(self):
        assert H2H.champion_seed(7, 0) == H2H.champion_seed(7, 0)
        assert H2H.champion_seed(7, 0) != H2H.champion_seed(7, 1)
        assert H2H.champion_seed(7, 0) != H2H.champion_seed(8, 0)

    def test_load_done_survives_a_torn_last_line(self, tmp_path):
        p = tmp_path / "out.jsonl"
        p.write_text(json.dumps({"deck_seed": 1, "joshua_seat": 0}) + "\n"
                     + '{"deck_seed": 2, "joshua_se')      # dirty-crash tail
        assert H2H.load_done(p) == {(1, 0)}


class _Args:
    """A stand-in for the parsed argparse namespace."""

    def __init__(self, **kw):
        self.j7_weight = 1.0
        self.j8_break_reserve_floor = False
        self.j9_avoid_cloisters = False
        self.override = None
        self.__dict__.update(kw)


class TestTournamentAxes:
    def test_defaults_resolve_to_the_documented_arm(self):
        assert H2H.build_overrides(_Args()) == {
            "j7_weight": 1.0, "j8_break_reserve_floor": False,
            "j9_avoid_cloisters": False}

    def test_named_flags_land_in_the_overrides(self):
        ov = H2H.build_overrides(_Args(j7_weight=0.0,
                                       j8_break_reserve_floor=True,
                                       j9_avoid_cloisters=True))
        assert ov == {"j7_weight": 0.0, "j8_break_reserve_floor": True,
                      "j9_avoid_cloisters": True}

    def test_override_escape_hatch_is_typed_and_wins(self):
        ov = H2H.build_overrides(_Args(
            override=["j9_min_surrounding=5", "j2_reach_threshold=0.25",
                      "j9_avoid_cloisters=true"]))
        assert ov["j9_min_surrounding"] == 5 and isinstance(ov["j9_min_surrounding"], int)
        assert ov["j2_reach_threshold"] == pytest.approx(0.25)
        assert ov["j9_avoid_cloisters"] is True        # beat the named flag's False

    def test_malformed_override_is_rejected(self):
        with pytest.raises(Exception):
            H2H.build_overrides(_Args(override=["j7_weight"]))

    def test_the_overrides_actually_build_that_bot(self):
        from carcassonne_ai.game_wrapper import Game
        from carcassonne_ai.joshua_bot import JoshuaBot

        ov = H2H.build_overrides(_Args(j7_weight=0.0, j9_avoid_cloisters=True))
        bot = JoshuaBot(Game(enable_legal_moves_cache=True), overrides=ov)
        assert bot.params.j7_weight == 0.0 and bot.params.j9_avoid_cloisters is True
        assert "j9avoid" in bot.variant_id


def _rec(seed, seat, margin, variant="current+j7w1"):
    return {"deck_seed": seed, "joshua_seat": seat,
            "margin_joshua_minus_champ": margin,
            "joshua_variant_id": variant,
            "winner": ("joshua" if margin > 0 else
                       "champion" if margin < 0 else "draw"),
            "joshua_rule_fires": {"j1_majority_steal": 1}}


class TestVariantGuard:
    def test_variants_in_reads_the_file(self, tmp_path):
        p = tmp_path / "out.jsonl"
        p.write_text("\n".join(json.dumps(_rec(1, s, 0)) for s in (0, 1)))
        assert H2H.variants_in(p) == {"current+j7w1"}

    def test_variants_in_is_empty_for_a_missing_file(self, tmp_path):
        assert H2H.variants_in(tmp_path / "nope.jsonl") == set()

    def test_a_mixed_file_is_visible_to_the_guard(self, tmp_path):
        p = tmp_path / "out.jsonl"
        p.write_text(json.dumps(_rec(1, 0, 0)) + "\n"
                     + json.dumps(_rec(1, 1, 0, variant="current+j7w0")) + "\n")
        assert len(H2H.variants_in(p)) == 2

    def test_summary_reports_which_variants_it_pooled(self):
        s = H2H.summarize([_rec(1, 0, +2), _rec(1, 1, -2)])
        assert s["variant_ids"] == ["current+j7w1"]


class TestSummarize:
    def test_pairs_are_averaged_over_the_two_seatings(self):
        s = H2H.summarize([_rec(1, 0, +10), _rec(1, 1, -4)])
        assert s["n_paired_decks"] == 1
        assert s["paired_margin_mean"] == pytest.approx(3.0)

    def test_an_unpaired_deck_is_scored_but_not_paired(self):
        s = H2H.summarize([_rec(1, 0, +10)])
        assert s["n_scored"] == 1 and s["n_paired_decks"] == 0
        assert s["paired_margin_mean"] is None

    def test_win_rate_counts_draws_as_a_half(self):
        s = H2H.summarize([_rec(1, 0, +1), _rec(1, 1, 0)])
        assert s["win_rate"] == pytest.approx(0.75)

    def test_rule_fires_are_totalled_for_the_audit(self):
        s = H2H.summarize([_rec(1, 0, +1), _rec(1, 1, -1)])
        assert s["rule_fires_total"]["j1_majority_steal"] == 2

    def test_sign_convention_is_joshua_minus_champion(self):
        assert H2H.summarize([_rec(1, 0, -6), _rec(1, 1, -6)])[
            "paired_margin_mean"] == pytest.approx(-6.0)


# --------------------------------------------------------------------------- #
# resilience: ONE pathological deck must cost ONE deck, not the run             #
# --------------------------------------------------------------------------- #
# 2026-08-13: the J7ZERO confirm died at 269/800 when the champion's rust search
# raised `NoLegalActionsAtInterior` on deck 126000000135 seat 0 — one cell killed
# the whole pool. The house lesson (capoff, DECISIONS 2026-07-31) is that a game
# which dies deterministically and leaves ZERO records is the dangerous pattern,
# because the loss is invisible AND can be candidate-correlated. These tests pin
# the catch path: the raise becomes a record, the pool finishes, the summary
# counts the exclusion.

#: the cell the stub worker below blows up on (module-level so the SPAWN child,
#: which re-imports this module, sees the same choice).
_STUB_FAIL_CELL = (10_001, 1)

#: the driver refuses to append a different variant to an existing file, so the
#: stub must stamp the SAME ``variant_id`` the real probe resolves. The parent
#: puts it here; spawn children inherit the environment.
_STUB_VARIANT_ENV = "H2H_STUB_VARIANT"

#: when set, the stub's pathological cell plays through — "the code fix" that a
#: ``--retry-failed`` pass claims happened. Spawn children inherit the environment.
_STUB_HEALED_ENV = "H2H_STUB_HEALED"


def _stub_ok_record(cell) -> dict:
    deck_seed, seat = int(cell[0]), int(cell[1])
    scores = [40, 30] if seat == 0 else [30, 40]
    return {"schema": H2H.SCHEMA, "deck_seed": deck_seed, "joshua_seat": seat,
            "champ_seat": 1 - seat, "scores": scores,
            "margin_joshua_minus_champ": scores[seat] - scores[1 - seat],
            "winner": "joshua",
            "joshua_variant_id": os.environ[_STUB_VARIANT_ENV],
            "joshua_rule_fires": {"j1_majority_steal": 1},
            "ms_per_move_joshua": 1.0, "ms_per_move_champ": 2.0,
            "n_moves": 3, "cell_secs": 0.01, "finished_at": time.time()}


def _stub_worker_init(profile, rust_threads, sims, k_dets, preset, overrides):
    """A stand-in for :func:`h2h._worker_init` with the SAME signature (it is
    handed the driver's real ``initargs``). Runs INSIDE the spawn child: it fills
    ``_W`` with what ``failed_record`` reads and swaps the game for a stub that
    explodes on exactly one cell. No engine, no champion, no game loop."""
    import h2h as _h

    _h._W.update(profile=profile, preset=preset, overrides=dict(overrides or {}),
                 variant_id=os.environ[_STUB_VARIANT_ENV])

    def _inner(cell):
        if ((int(cell[0]), int(cell[1])) == _STUB_FAIL_CELL
                and not os.environ.get(_STUB_HEALED_ENV)):
            raise RuntimeError("stub: PUCT reached a node with no valid actions")
        return _stub_ok_record(cell)

    _h._play_cell_inner = _inner


class TestFailedCellGuard:
    """The in-process half: ``_play_cell`` never lets a game's raise escape."""

    @pytest.fixture(autouse=True)
    def _worker_state(self, monkeypatch):
        monkeypatch.setitem(H2H._W, "preset", "current")
        monkeypatch.setitem(H2H._W, "profile", "fixed_v1")
        monkeypatch.setitem(H2H._W, "variant_id", "current+j7w0")
        monkeypatch.setitem(H2H._W, "overrides", {"j7_weight": 0.0})

    def test_a_raise_becomes_a_failed_record(self, monkeypatch):
        def boom(cell):
            raise RuntimeError("PUCT reached a node with no valid actions")

        monkeypatch.setattr(H2H, "_play_cell_inner", boom)
        rec = H2H._play_cell((126_000_000_135, 0))
        assert rec["failed"] is True
        assert rec["schema"].endswith("/failed")
        assert (rec["deck_seed"], rec["joshua_seat"]) == (126_000_000_135, 0)
        assert rec["champ_seat"] == 1
        assert rec["exc_type"] == "RuntimeError"
        assert "no valid actions" in rec["exc"]
        assert "boom" in rec["traceback"]            # the raise site is preserved
        assert rec["champion_seed"] == H2H.champion_seed(126_000_000_135, 0)
        # the fields every statistic keys on are ABSENT/None, so nothing can
        # silently read a failed cell as a 0-margin draw
        assert rec["winner"] is None
        assert "margin_joshua_minus_champ" not in rec
        assert rec["joshua_variant_id"] == "current+j7w0"   # the guard names it
        json.dumps(rec)                                     # JSONL-serialisable

    def test_the_record_survives_a_non_Exception_failure(self, monkeypatch):
        """pyo3 panics arrive as BaseException subclasses, not Exception."""
        class Panic(BaseException):
            pass

        def boom(cell):
            raise Panic("rust panicked")

        monkeypatch.setattr(H2H, "_play_cell_inner", boom)
        assert H2H._play_cell((5, 1))["exc_type"] == "Panic"

    @pytest.mark.parametrize("exc", [KeyboardInterrupt, SystemExit])
    def test_an_operator_interrupt_still_propagates(self, monkeypatch, exc):
        def boom(cell):
            raise exc()

        monkeypatch.setattr(H2H, "_play_cell_inner", boom)
        with pytest.raises(exc):
            H2H._play_cell((5, 1))


def _failed(seed, seat, variant="current+j7w1"):
    return {"schema": H2H.SCHEMA + "/failed", "failed": True, "deck_seed": seed,
            "joshua_seat": seat, "winner": None, "joshua_variant_id": variant,
            "exc_type": "RuntimeError", "exc": "no valid actions"}


class TestFailuresAreCounted:
    def test_summary_states_the_exclusion(self):
        s = H2H.summarize([_rec(1, 0, +2), _rec(1, 1, -2), _failed(2, 0)])
        assert s["n_records"] == 3 and s["n_scored"] == 2
        assert s["n_failed"] == 1
        assert s["failure_rate"] == pytest.approx(1 / 3)
        assert s["failed_cells"] == [{"deck_seed": 2, "joshua_seat": 0,
                                      "exc_type": "RuntimeError",
                                      "exc": "no valid actions"}]
        assert s["failed_by_seat"] == {"0": 1, "1": 0}

    def test_a_failed_cell_is_in_no_statistic(self):
        s = H2H.summarize([_rec(1, 0, +2), _rec(1, 1, -2), _failed(2, 0)])
        assert s["wins"] + s["draws"] + s["losses"] == 2
        assert s["n_paired_decks"] == 1                    # only deck 1 is paired
        assert s["paired_margin_mean"] == pytest.approx(0.0)

    def test_a_half_dead_deck_never_enters_the_paired_margin(self):
        """The seat that DID finish must not leak in as an unpaired half-deck."""
        s = H2H.summarize([_rec(9, 0, +30), _failed(9, 1)])
        assert s["n_paired_decks"] == 0 and s["paired_margin_mean"] is None

    def test_no_failures_reports_a_zero_rate_not_a_missing_key(self):
        s = H2H.summarize([_rec(1, 0, +2), _rec(1, 1, -2)])
        assert s["n_failed"] == 0 and s["failure_rate"] == 0.0

    def test_the_variant_guard_still_sees_a_failed_cell(self, tmp_path):
        p = tmp_path / "out.jsonl"
        p.write_text(json.dumps(_failed(2, 0, variant="current+j7w0")) + "\n")
        assert H2H.variants_in(p) == {"current+j7w0"}


class TestFailedResumeContract:
    def test_a_failed_cell_counts_as_done(self, tmp_path):
        p = tmp_path / "out.jsonl"
        p.write_text(json.dumps(_rec(1, 0, +1)) + "\n"
                     + json.dumps(_failed(1, 1)) + "\n")
        assert H2H.load_done(p) == {(1, 0), (1, 1)}
        assert H2H.load_failed(p) == {(1, 1)}

    def test_retry_failed_reopens_exactly_the_failed_cells(self, tmp_path):
        p = tmp_path / "out.jsonl"
        p.write_text(json.dumps(_rec(1, 0, +1)) + "\n"
                     + json.dumps(_failed(1, 1)) + "\n")
        done = H2H.load_done(p) - H2H.load_failed(p)
        assert H2H.build_cells([1], done) == [(1, 1)]

    def test_read_records_skips_a_torn_tail(self, tmp_path):
        p = tmp_path / "out.jsonl"
        p.write_text(json.dumps(_rec(1, 0, +1)) + "\n" + '{"deck_seed": 2, "josh')
        assert len(H2H.read_records(p)) == 1


class TestResolvedFailures:
    """A failure that a later ``--retry-failed`` pass PLAYED THROUGH is not a
    failure. After a successful retry the JSONL holds BOTH the failed record and
    the success record for the same cell — the SUCCESS RECORD IS THE ARBITER
    (mirrors ``eval_fair_puct``'s resolved-failure fix, commit 2f5d0929, where the
    arbiter is the result file). ``failure_rate`` gates the pre-registered
    validity trigger (>0.5% ⇒ stop and investigate), so it must mean what it
    says: an overstated rate can void a cleanly-completed cell."""

    def test_fail_retry_succeed_zeroes_the_failure_count(self):
        s = H2H.summarize([_rec(1, 0, +2), _failed(1, 1), _rec(1, 1, -2)])
        assert s["n_failed"] == 0
        assert s["failure_rate"] == 0.0
        assert s["failed_cells"] == []
        assert s["failed_by_seat"] == {"0": 0, "1": 0}

    def test_the_forensic_record_is_still_discoverable(self):
        s = H2H.summarize([_rec(1, 0, +2), _failed(1, 1), _rec(1, 1, -2)])
        assert s["n_resolved_failures"] == 1
        assert s["resolved_failed_cells"] == [{"deck_seed": 1, "joshua_seat": 1,
                                               "exc_type": "RuntimeError",
                                               "exc": "no valid actions"}]

    def test_an_unresolved_failure_still_counts(self):
        s = H2H.summarize([_rec(1, 0, +2), _failed(1, 1), _rec(1, 1, -2),
                           _failed(2, 0)])
        assert s["n_failed"] == 1
        assert s["failed_cells"][0]["deck_seed"] == 2
        # the resolved record is in NEITHER side of the rate: 1 failure over
        # 2 scored + 1 failed
        assert s["failure_rate"] == pytest.approx(1 / 3)
        assert s["n_resolved_failures"] == 1

    def test_resolution_restores_the_paired_deck(self):
        """The success record is a full game: the deck pairs up again and the
        margin statistics are exactly those of a never-failed run."""
        s = H2H.summarize([_rec(1, 0, +10), _failed(1, 1), _rec(1, 1, -4)])
        assert s["n_paired_decks"] == 1
        assert s["paired_margin_mean"] == pytest.approx(3.0)

    def test_zero_failure_output_unchanged_apart_from_resolved_keys(self):
        """house convention (test_no_failures_reports_a_zero_rate_not_a_missing_key):
        the resolved counts are ALWAYS emitted — a zero is stated. Everything
        else is byte-identical to the pre-fix summary, pinned in full."""
        s = H2H.summarize([_rec(1, 0, +2), _rec(1, 1, -2)])
        assert s.pop("n_resolved_failures") == 0
        assert s.pop("resolved_failed_cells") == []
        assert s == {
            "variant_ids": ["current+j7w1"],
            "n_records": 2, "n_scored": 2,
            "n_failed": 0, "failure_rate": 0.0,
            "failed_cells": [], "failed_by_seat": {"0": 0, "1": 0},
            "wins": 1, "draws": 0, "losses": 1,
            "win_rate": 0.5,
            "n_paired_decks": 1,
            "paired_margin_mean": 0.0,
            "paired_margin_sem": None,
            "paired_margin_z": None,
            "mean_margin_unpaired": 0.0,
            "rule_fires_total": {"j1_majority_steal": 2},
        }

    def test_load_failed_excludes_resolved_by_default(self, tmp_path):
        p = tmp_path / "out.jsonl"
        p.write_text(json.dumps(_failed(1, 1)) + "\n"
                     + json.dumps(_rec(1, 1, -2)) + "\n"
                     + json.dumps(_failed(2, 0)) + "\n")
        assert H2H.load_failed(p) == {(2, 0)}
        assert H2H.load_failed(p, include_resolved=True) == {(1, 1), (2, 0)}

    def test_retry_failed_does_not_reopen_a_resolved_cell(self, tmp_path):
        """the driver-level consequence: ``done -= load_failed(...)`` must not
        re-open (and duplicate) a cell whose retry already succeeded."""
        p = tmp_path / "out.jsonl"
        p.write_text(json.dumps(_rec(1, 0, +2)) + "\n"
                     + json.dumps(_failed(1, 1)) + "\n"
                     + json.dumps(_rec(1, 1, -2)) + "\n"
                     + json.dumps(_rec(2, 1, +1)) + "\n"
                     + json.dumps(_failed(2, 0)) + "\n")
        done = H2H.load_done(p) - H2H.load_failed(p)
        assert H2H.build_cells([1, 2], done) == [(2, 0)]


class TestPoolSurvivesAFailedCell:
    """The end-to-end claim, through the REAL spawn pool and the REAL driver."""

    @pytest.fixture(autouse=True)
    def _stub_pool(self, monkeypatch):
        from carcassonne_ai.joshua_bot import JoshuaBot

        variant = JoshuaBot(None, preset="current",
                            overrides=H2H.build_overrides(_Args())).variant_id
        monkeypatch.setenv(_STUB_VARIANT_ENV, variant)
        monkeypatch.setattr(H2H, "_worker_init", _stub_worker_init)
        monkeypatch.setattr(H2H, "export_profile_env", lambda profile: {"stub": True})

    def test_the_run_completes_and_the_summary_counts_the_failure(
            self, tmp_path, monkeypatch):
        out = tmp_path / "stub.jsonl"
        rc = H2H.main(["--decks", "3", "--seed-base", "10000",
                       "--workers", "2", "--out", str(out)])
        assert rc == 0                                    # the pool did NOT die

        recs = H2H.read_records(out)
        assert len(recs) == 6                             # 3 decks x 2 seats, all present
        bad = [r for r in recs if r.get("failed")]
        assert len(bad) == 1
        assert (bad[0]["deck_seed"], bad[0]["joshua_seat"]) == _STUB_FAIL_CELL
        assert "no valid actions" in bad[0]["exc"]

        man = json.loads((tmp_path / "stub.jsonl.manifest.json").read_text())
        assert man["summary"]["n_failed"] == 1            # a reader cannot miss it
        assert man["summary"]["n_scored"] == 5
        assert man["summary"]["failure_rate"] == pytest.approx(1 / 6)
        assert man["n_failed_this_leg"] == 1
        # the broken pair is dropped from the paired statistic, the others survive
        assert man["summary"]["n_paired_decks"] == 2

    def test_a_resume_skips_the_failed_cell_and_still_reports_it(
            self, tmp_path, monkeypatch):
        out = tmp_path / "stub.jsonl"
        argv = ["--decks", "3", "--seed-base", "10000", "--workers", "2",
                "--out", str(out)]
        assert H2H.main(argv) == 0
        assert H2H.main(argv + ["--resume"]) == 0         # nothing left to do
        assert len(H2H.read_records(out)) == 6            # no cell replayed
        man = json.loads((tmp_path / "stub.jsonl.manifest.json").read_text())
        assert man["summary"]["n_failed"] == 1            # still stated after resume

    def test_a_successful_retry_resolves_the_failure_end_to_end(
            self, tmp_path, monkeypatch):
        """fail -> --retry-failed -> SUCCEED, through the real spawn pool and the
        real driver: the cell completes, the failure count zeroes, the forensic
        record survives, and a THIRD --retry-failed pass re-opens nothing."""
        out = tmp_path / "stub.jsonl"
        argv = ["--decks", "3", "--seed-base", "10000", "--workers", "2",
                "--out", str(out)]
        assert H2H.main(argv) == 0                        # leg 1: one cell fails
        monkeypatch.setenv(_STUB_HEALED_ENV, "1")         # "the code fix"
        assert H2H.main(argv + ["--resume", "--retry-failed"]) == 0
        recs = H2H.read_records(out)
        assert len(recs) == 7                 # 6 games + the KEPT failure record
        man = json.loads((tmp_path / "stub.jsonl.manifest.json").read_text())
        assert man["summary"]["n_scored"] == 6
        assert man["summary"]["n_failed"] == 0            # a resolved failure is
        assert man["summary"]["failure_rate"] == 0.0      # NOT a failure
        assert man["summary"]["n_resolved_failures"] == 1
        assert (man["summary"]["resolved_failed_cells"][0]["deck_seed"]
                == _STUB_FAIL_CELL[0])
        assert man["summary"]["n_paired_decks"] == 3      # the healed pair is back
        # a third --retry-failed pass must NOT re-open the resolved cell
        assert H2H.main(argv + ["--resume", "--retry-failed"]) == 0
        assert len(H2H.read_records(out)) == 7            # no duplicate appended


class TestPlayHarnessIntegration:
    """The load-bearing claim: JoshuaBot slots into the E4 game loop unmodified."""

    def test_joshua_bot_drives_play_harness_play_game(self):
        if str(HUMAN_ANCHOR) not in sys.path:
            sys.path.insert(0, str(HUMAN_ANCHOR))
        import play_harness as PH                       # imports env_preamble itself

        from carcassonne_ai.game_wrapper import Game
        from carcassonne_ai.joshua_bot import JoshuaBot

        game = Game(enable_legal_moves_cache=True)
        seed = 606_101
        agents = {0: JoshuaBot(game, preset="current"),
                  1: JoshuaBot(game, preset="early")}
        rec = PH.play_game(game, seed, agents, {0: "joshua_current", 1: "joshua_early"},
                           {"experiment": "joshuabot_integration_smoke"})
        assert rec["result"]["n_moves"] > 100
        assert sum(rec["result"]["scores"]) > 0
        # the harness recorded the bot's own manifest for BOTH seats
        cm = rec["manifest"]["champion_manifests"]
        assert cm["0"]["preset"] == "current" and cm["1"]["preset"] == "early"
        assert all(m["agent"] == "joshua_bot" for m in cm.values())
        # ...and every move carries the harness's per-move telemetry envelope
        assert all({"path", "latch_k", "ms", "desc"} <= set(mv) for mv in rec["moves"])

    def test_paired_rematch_reproduces_the_deck(self):
        """Deck pairing is the driver's whole statistic; prove the harness really
        re-deals the identical deck when the seats swap."""
        if str(HUMAN_ANCHOR) not in sys.path:
            sys.path.insert(0, str(HUMAN_ANCHOR))
        import play_harness as PH

        from carcassonne_ai.game_wrapper import Game
        from carcassonne_ai.joshua_bot import JoshuaBot

        game = Game(enable_legal_moves_cache=True)
        random.seed(1)
        recs = PH.play_paired(
            game, 606_202,
            lambda: JoshuaBot(game, preset="current"),
            lambda: JoshuaBot(game, preset="early"),
            "joshua_current", "joshua_early",
            {"experiment": "joshuabot_pairing_smoke"})
        assert recs[0]["manifest"]["deck_hash"] == recs[1]["manifest"]["deck_hash"]
        assert all(r["result"]["n_moves"] > 100 for r in recs)
