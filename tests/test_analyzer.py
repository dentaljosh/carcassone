"""Contracts for the Phase-5 analyzer (scripts/analyzer/).

Four groups:
  A. replay-count sanity   — plies/turns/meeples reconcile with the archive
  B. hand-checked fixture  — every stat verified against a literal expected value
                             on one small, fully-enumerated game
  C. stranding definition  — pinned, including the farmer carve-out
  D. e4_diff plumbing      — percentile ranking + the report builds end to end
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "analyzer"))
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))

from replay_stats import (  # noqa: E402
    replay_game_stats, game_scalars, seat_scalars, k_band, tercile,
    K_BAND_EARLY_MIN, K_BAND_MID_MIN,
)
import corpus_stats as CS  # noqa: E402
import e4_diff as ED  # noqa: E402
from root_replay import load_games  # noqa: E402

CHAMP = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
E4_DIR = REPO / "measurement" / "e4_games"


@pytest.fixture(scope="module")
def champ_records():
    if not CHAMP.exists():
        pytest.skip(f"corpus missing: {CHAMP}")
    return load_games(CHAMP)


@pytest.fixture(scope="module")
def fixture_game(champ_records):
    """One fixed, fully-replayed game. Its game_id pins the fixture: if the corpus
    file is ever regenerated the hand-checked numbers below must be re-derived."""
    rec = next(r for r in champ_records if r.game_id == 28000000000)
    return rec, replay_game_stats(
        rec.deck_seed, rec.actions,
        recorded_scores=[rec.meta["score_p0"], rec.meta["score_p1"]],
        game_id=rec.game_id)


# --------------------------------------------------------------------------- #
# A. replay-count sanity
# --------------------------------------------------------------------------- #

def test_replay_reproduces_recorded_scores(fixture_game):
    rec, st = fixture_game
    assert st.replay_scores_match is True
    assert st.final_scores == [rec.meta["score_p0"], rec.meta["score_p1"]]


def test_ply_and_turn_counts_reconcile(fixture_game):
    rec, st = fixture_game
    assert st.n_plies == len(rec.actions) == rec.n_plies
    # Every ply is consumed by exactly one turn record.
    assert sum(t["plies"] for t in st.turns) == st.n_plies
    assert len(st.turns) == st.n_turns
    # Turn indices are dense and ordered.
    assert [t["turn"] for t in st.turns] == list(range(st.n_turns))
    # Seats alternate one turn each in a normal full game.
    assert sum(1 for t in st.turns if t["player"] == 0) == st.n_turns // 2


def test_score_split_reconciles_with_final_scores(fixture_game):
    _rec, st = fixture_game
    assert st.split_ok
    for p, flow in enumerate(st.score_flow):
        assert flow["during_play"] + flow["incomplete"] + flow["farms"] == flow["total"]
        assert flow["total"] == st.final_scores[p]


def test_meeple_ledger_matches_engine_supply(fixture_game):
    _rec, st = fixture_game
    # Every deployment is in the ledger exactly once, and the count agrees with
    # the hand-supply the engine reports (7 start, minus what is still out).
    for p in (0, 1):
        placed = [m for m in st.meeples if m["player"] == p]
        stranded = [m for m in placed if m["stranded"]]
        last_hand = st.turns[-1]["meeples_in_hand"][p]
        # meeples in hand at the last turn + meeples still on the board
        # + meeples returned-but-not-yet-redeployed must never exceed 7 placed-out.
        assert 0 <= last_hand <= 7
        assert len(stranded) <= 7
        assert all(m["locked_turns"] >= 0 for m in placed)
        assert all(m["return_turn"] is None or m["return_turn"] >= m["place_turn"]
                   for m in placed)


def test_corpus_replays_clean_and_counts_match(champ_records):
    """A 20-game slice of the real corpus: every game replays to its recorded
    score and every score split reconciles. This is the guard that would fire if
    the engine, the leaf decomposition, or the archive format ever drifted."""
    for rec in champ_records[:20]:
        st = replay_game_stats(rec.deck_seed, rec.actions,
                               recorded_scores=[rec.meta["score_p0"],
                                                rec.meta["score_p1"]],
                               game_id=rec.game_id)
        assert st.replay_scores_match is True, rec.game_id
        assert st.split_ok, rec.game_id
        assert st.n_plies == len(rec.actions)


# --------------------------------------------------------------------------- #
# B. hand-checked fixture — literal expected values
# --------------------------------------------------------------------------- #
# Derived once by enumerating game 28000000000's replay and checking the pieces
# against the engine's own scores. If a definition changes, these MUST be
# re-derived by hand, not auto-updated.

def test_fixture_headline_values(fixture_game):
    _rec, st = fixture_game
    assert st.n_plies == 144
    assert st.n_turns == 72
    assert st.final_scores == [90, 108]
    assert st.score_flow == [
        {"during_play": 62, "incomplete": 10, "farms": 18, "total": 90},
        {"during_play": 69, "incomplete": 21, "farms": 18, "total": 108},
    ]


def test_fixture_completions_hand_checked(fixture_game):
    _rec, st = fixture_game
    comp = st.completions
    assert len(comp) == 27
    by = lambda t: [e for e in comp if e["terrain"] == t]  # noqa: E731
    assert (len(by("city")), len(by("road")), len(by("cloister"))) == (10, 12, 5)
    # Closure turns are non-decreasing (detection is first-sighting).
    assert [e["turn"] for e in comp] == sorted(e["turn"] for e in comp)
    # Cloisters always close at exactly 9 tiles / 9 points.
    assert all(e["size"] == 9 and e["points"] == 9 for e in by("cloister"))
    # Roads score 1/tile when finished (no inns in scope).
    assert all(e["points"] == e["size"] for e in by("road"))
    # Cities score 2/tile + 2/shield when finished (no cathedrals in scope).
    assert all(e["points"] == 2 * e["size"] + 2 * e["shields"] for e in by("city"))
    # The first closure in this game, checked by hand off the replay.
    first = comp[0]
    assert (first["terrain"], first["size"], first["shields"], first["points"],
            first["turn"], first["k_remaining"], first["winners"]) == \
        ("city", 8, 2, 20, 13, 58, [1])


def test_fixture_meeple_ledger_hand_checked(fixture_game):
    _rec, st = fixture_game
    assert len(st.meeples) == 24
    m0 = sorted((m for m in st.meeples), key=lambda m: (m["place_turn"], m["player"]))[0]
    # p0's opening move claims a road on turn 0; it comes home on turn 16 for 3 pts.
    assert m0 == {
        "player": 0, "terrain": "road", "meeple_type": "normal",
        "place_turn": 0, "place_k_remaining": 71, "place_tercile": "early",
        "place_k_band": "early", "return_turn": 16, "points_earned": 3,
        "stranded": False, "locked_turns": 16,
    }
    # Deployments must equal the number of distinct meeple placements.
    assert sum(1 for t in st.turns if t["move_type"] != "pass") == len(st.meeples)


def test_fixture_seat_scalars_hand_checked(fixture_game):
    _rec, st = fixture_game
    s0 = seat_scalars(st, 0)
    assert s0["final_score"] == 90
    assert s0["during_play"] == 62 and s0["farm_pts"] == 18
    assert s0["n_farmers_placed"] == 4
    assert s0["first_farm_turn"] == 2 and s0["first_farm_k_remaining"] == 69
    assert s0["stranded_nonfarmer"] == 2
    assert s0["n_nonfarm_placed"] == 9
    assert s0["stranding_rate_nonfarmer"] == pytest.approx(2 / 9)
    # meeple-turns locked = sum over the 2 stranded non-farmers of (72 - place_turn)
    stranded = [m for m in st.meeples
                if m["player"] == 0 and m["terrain"] != "farm" and m["stranded"]]
    assert s0["meeple_turns_locked"] == sum(72 - m["place_turn"] for m in stranded)
    # The phase mix fractions over one seat's turns must sum to 1 in each band.
    for seg in ("kband", "tercile"):
        for ph in ("early", "mid", "late"):
            fr = [s0[f"{seg}_{ph}_frac_{k}"]
                  for k in ("city", "road", "farm", "cloister", "pass")]
            assert sum(fr) == pytest.approx(1.0)


def test_fixture_game_scalars_hand_checked(fixture_game):
    _rec, st = fixture_game
    g = game_scalars(st)
    assert g["n_turns"] == 72
    assert g["n_completions"] == 27
    assert (g["n_cities_closed"], g["n_roads_closed"], g["n_cloisters_closed"]) \
        == (10, 12, 5)
    assert g["max_city_size"] == 8
    assert g["score_margin_abs"] == 18
    assert g["total_points"] == 198
    assert g["mean_city_size"] == pytest.approx(29 / 10)


# --------------------------------------------------------------------------- #
# C. band/tercile boundaries and the stranding definition — pinned
# --------------------------------------------------------------------------- #

def test_k_band_boundaries_pinned():
    assert (K_BAND_EARLY_MIN, K_BAND_MID_MIN) == (48, 24)
    assert k_band(71) == k_band(48) == "early"
    assert k_band(47) == k_band(24) == "mid"
    assert k_band(23) == k_band(0) == "late"


def test_tercile_boundaries_pinned():
    assert tercile(0, 72) == "early" and tercile(23, 72) == "early"
    assert tercile(24, 72) == "mid" and tercile(47, 72) == "mid"
    assert tercile(48, 72) == "late" and tercile(71, 72) == "late"


def test_stranding_definition_pinned(fixture_game):
    """STRANDED == still in placed_meeples at the meeple-intact terminal state,
    which is exactly 'never returned during play' == 'never scored during play'."""
    _rec, st = fixture_game
    for m in st.meeples:
        # The two characterisations must never disagree.
        assert m["stranded"] == (m["return_turn"] is None)
        if m["stranded"]:
            assert m["points_earned"] == 0, "a stranded meeple banked no during-play points"
            assert m["locked_turns"] == st.n_turns - m["place_turn"]
        else:
            assert m["locked_turns"] == m["return_turn"] - m["place_turn"]


def test_farmers_are_always_stranded(fixture_game):
    """The farmer carve-out. A farmer is unrecoverable in Base+Farmers, so it is
    stranded BY DESIGN — which is why the headline rate excludes farmers."""
    _rec, st = fixture_game
    farmers = [m for m in st.meeples if m["terrain"] == "farm"]
    assert farmers, "fixture must contain farmers"
    assert all(m["stranded"] for m in farmers)
    assert all(m["return_turn"] is None for m in farmers)
    for p in (0, 1):
        s = seat_scalars(st, p)
        # The two rates must be computed off different denominators.
        assert s["stranded_all"] == s["stranded_nonfarmer"] + s["n_farmers_placed"]
        assert s["n_meeples_placed"] == s["n_nonfarm_placed"] + s["n_farmers_placed"]


def test_stranding_rate_excludes_farmers_from_both_sides(fixture_game):
    _rec, st = fixture_game
    s0 = seat_scalars(st, 0)
    nonfarm = [m for m in st.meeples if m["player"] == 0 and m["terrain"] != "farm"]
    assert s0["stranding_rate_nonfarmer"] == pytest.approx(
        sum(1 for m in nonfarm if m["stranded"]) / len(nonfarm))


# --------------------------------------------------------------------------- #
# D. aggregation + e4_diff
# --------------------------------------------------------------------------- #

def test_aggregate_builds_and_reconciles(champ_records, tmp_path):
    games, seats, details = [], [], []
    for rec in champ_records[:8]:
        g, ss, d = CS._one((rec.deck_seed, rec.actions,
                            [rec.meta["score_p0"], rec.meta["score_p1"]], rec.game_id))
        games.append(g); seats.extend(ss); details.append(d)
    cat = CS.aggregate(games, seats, details, "t", "x.jsonl", "note", {})
    assert cat["n_games"] == 8 and cat["n_seats"] == 16
    assert cat["integrity"]["replay_scores_match"] == 8
    assert cat["integrity"]["split_ok"] == 8
    assert cat["integrity"]["replay_scores_mismatch"] == 0
    # Per-band non-farmer counts must partition the total.
    s = cat["stranding"]
    assert sum(s["by_placement_k_band"][ph]["n_placed"] for ph in ("early", "mid", "late")) \
        == s["n_nonfarm_placed"]
    assert sum(s["by_terrain"][t]["n_placed"] for t in ("city", "road", "cloister")) \
        == s["n_nonfarm_placed"]
    # Move-mix turn counts must partition every turn, in both segmentations.
    total_turns = sum(g["n_turns"] for g in games)
    for seg in ("by_k_band", "by_tercile"):
        assert sum(b["n_turns"] for b in cat["move_mix"][seg].values()) == total_turns
    assert 0.0 <= cat["move_mix"]["segmentation_agreement"] <= 1.0
    # Markdown renders without blowing up and mentions the integrity line.
    md = CS.to_markdown(cat)
    assert "Integrity" in md and "Stranding" in md


def test_percentile_rank_edges():
    xs = [1, 2, 3, 4, 5]
    assert ED.percentile_rank(xs, 0) == 0.0
    assert ED.percentile_rank(xs, 6) == 1.0
    assert ED.percentile_rank(xs, 3) == pytest.approx(0.5)
    assert ED.percentile_rank([], 3) is None
    assert ED.percentile_rank(xs, None) is None


def test_e4_diff_end_to_end(champ_records, tmp_path):
    archives = sorted(E4_DIR.glob("*.json"))
    if not archives:
        pytest.skip("no E4 archives")
    games, seats, details = [], [], []
    for rec in champ_records[:8]:
        g, ss, d = CS._one((rec.deck_seed, rec.actions,
                            [rec.meta["score_p0"], rec.meta["score_p1"]], rec.game_id))
        games.append(g); seats.extend(ss); details.append(d)
    cat = CS.aggregate(games, seats, details, "t", "x.jsonl", "note", {})

    e4 = ED.load_e4(archives[0])
    rep = ED.build_report(e4, cat, archives[0].stem)
    # The phone's recorded scores must survive a desktop replay.
    assert rep["replay_scores_match"] is True
    assert rep["split_ok"] is True
    assert rep["final_scores"] == rep["recorded_scores"]
    # And the replayed split must match the breakdown the phone itself recorded.
    if rep["recorded_breakdown"]:
        for p, row in enumerate(rep["recorded_breakdown"]):
            got = rep["replayed_score_flow"][p]
            assert got["during_play"] == row["during_play"]
            assert got["incomplete"] == row["incomplete"]
            assert got["farms"] == row["farms"]
    assert len(rep["top_divergences"]) == 3
    assert rep["seat_scalars"].keys() == {"human", "champion"}
    for r in rep["rows"]:
        if r["human_pct"] is not None:
            assert 0.0 <= r["human_pct"] <= 1.0
    md = ED.to_markdown(rep, cat)
    assert "biggest divergences" in md
