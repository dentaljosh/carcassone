"""``scripts/joshuabot/h2h.py`` — the pure parts of the deck-paired H2H driver.

The champion-budget game loop is not exercised here (that is fleet compute); what
is exercised is everything that decides WHAT gets played and HOW it is summarised:
cell construction (deck pairing), the resume contract, the paired statistic, and —
crucially — that ``JoshuaBot`` really does drive ``play_harness.play_game`` with no
harness change, which is the integration claim the whole instrument rests on.
"""
from __future__ import annotations

import importlib.util
import json
import random
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HUMAN_ANCHOR = REPO / "scripts" / "human_anchor"


def _load_h2h():
    """Import the driver by path — ``scripts/joshuabot`` is not a package."""
    if str(REPO / "scripts") not in sys.path:
        sys.path.insert(0, str(REPO / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "joshuabot_h2h", REPO / "scripts" / "joshuabot" / "h2h.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
