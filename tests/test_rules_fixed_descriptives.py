"""Tests for the F9 Phase C decision-density instrument (scripts/rules_fixed/).

The pins are REAL games from the walled 449-game champion corpus
(`measurement/champ_action_logs/champ_games.jsonl`), replayed under the `walled`
profile. They are here to make format drift LOUD: if the action encoding, the
phase alternation, the tile-pass path or the meeple-slot blocks ever move, these
counts change and the suite fails rather than the descriptive quietly reporting
a different game.

Game 28000000002 is deliberately in the fixture — it contains a TILE-PASS ply
(the engine's unplaceable-tile path, A3's subject matter), which is exactly the
event a naive ply-parity assumption would mis-handle.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "rules_fixed"))

import descriptives as dd  # noqa: E402

CORPUS = REPO / "measurement/champ_action_logs/champ_games.jsonl"

# game_id -> the pinned counts (walled replay, R9 off)
PINS = {
    28000000000: dict(n_plies=144, n_tile_plies=72, n_meeple_plies=72,
                      n_tiles_placed=72, tile_pass_plies=0, decisions=144,
                      searched=137, forced_total=7, tile_forced=1, meeple_forced=6,
                      meeples_committed=37, farmers_committed=8, meeples_free_end=1,
                      final_scores=[90, 108]),
    28000000001: dict(n_plies=144, n_tile_plies=72, n_meeple_plies=72,
                      n_tiles_placed=72, tile_pass_plies=0, decisions=144,
                      searched=139, forced_total=5, tile_forced=1, meeple_forced=4,
                      meeples_committed=34, farmers_committed=5, meeples_free_end=3,
                      final_scores=[110, 101]),
    # the tile-pass game
    28000000002: dict(n_plies=143, n_tile_plies=72, n_meeple_plies=71,
                      n_tiles_placed=71, tile_pass_plies=1, decisions=143,
                      searched=125, forced_total=18, tile_forced=2, meeple_forced=16,
                      meeples_committed=27, farmers_committed=5, meeples_free_end=0,
                      final_scores=[85, 106]),
}

BRANCHING_PINS = {  # game_id -> (tile mean, meeple mean), 6 dp
    28000000000: (29.194444, 3.680556),
    28000000001: (24.263889, 3.597222),
    28000000002: (31.805556, 3.267606),
}


@pytest.fixture(scope="module")
def walled_env():
    """Replay the walled corpus with the walled profile / R9 off, then restore."""
    saved = {k: os.environ.get(k)
             for k in ("CARCASSONNE_RULES_PROFILE", "CARCASSONNE_FIX_R9")}
    dd.publish_environment("walled", False)
    dd._use_repo_tree()
    dd.verify_environment("walled", False)
    yield
    from carcassonne_ai import rules_profile as rp
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    rp.reset()


@pytest.fixture(scope="module")
def fixture_games():
    if not CORPUS.exists():
        pytest.skip(f"corpus not present: {CORPUS}")
    corpus = dd.load_corpus(CORPUS, limit=3)
    return {g["game_id"]: g for g in corpus["games"]}


# --------------------------------------------------------------------------- #
# the replayed pins                                                             #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("gid", sorted(PINS))
def test_per_game_counts_pinned(gid, fixture_games, walled_env):
    g = fixture_games[gid]
    rec = dd.game_decision_stats(g["deck_seed"], g["actions"],
                                 recorded_scores=[g["score_p0"], g["score_p1"]],
                                 game_id=gid)
    for key, want in PINS[gid].items():
        assert rec[key] == want, f"{gid}.{key}: {rec[key]} != {want}"
    assert rec["replay_scores_match"] is True
    # structural invariants, independent of the pins
    assert rec["n_plies"] == rec["n_tile_plies"] + rec["n_meeple_plies"]
    assert rec["decisions"] == rec["searched"] + rec["forced_total"]
    assert rec["n_tiles_placed"] == rec["n_tile_plies"] - rec["tile_pass_plies"]


@pytest.mark.parametrize("gid", sorted(BRANCHING_PINS))
def test_branching_means_pinned(gid, fixture_games, walled_env):
    g = fixture_games[gid]
    rec = dd.game_decision_stats(g["deck_seed"], g["actions"], game_id=gid)
    want_tile, want_meeple = BRANCHING_PINS[gid]
    assert rec["tile_branching_mean"] == pytest.approx(want_tile, abs=1e-6)
    assert rec["meeple_branching_mean"] == pytest.approx(want_meeple, abs=1e-6)
    # a meeple ply offers at most the 9 slots + pass; a tile ply is bounded by the
    # 25x25x4 window. Cheap guards against a phase mix-up.
    assert 1 <= rec["meeple_branching_mean"] <= 10
    assert rec["tile_branching_mean"] > 10


def test_meeple_commit_split_matches_totals(fixture_games, walled_env):
    g = fixture_games[28000000000]
    rec = dd.game_decision_stats(g["deck_seed"], g["actions"], game_id=28000000000)
    placed = sum(rec["commits"][t][m] for t in dd.TERCILES
                 for m in ("normal", "monk", "farmer"))
    passes = sum(rec["commits"][t]["pass"] for t in dd.TERCILES)
    assert placed == rec["meeples_committed"]
    assert placed + passes == rec["n_meeple_plies"]
    # 2 seats x 7 meeples, minus what is still in hand at the terminal state,
    # equals what is on the board — placements can exceed that only by recycling.
    assert placed >= 14 - rec["meeples_free_end"]


def test_aggregate_and_markdown(fixture_games, walled_env):
    cat = dd.run(CORPUS, label="pin3", rules_profile="walled", workers=1, limit=3)
    assert cat["schema"] == dd.SCHEMA
    assert cat["corpus"]["n_games"] == 3
    assert cat["rules_profile"]["name"] == "walled"
    assert cat["rules_profile"]["r9_env"] is False
    assert cat["integrity"]["replay_scores_match"] == 3
    assert cat["integrity"]["replay_scores_mismatch"] == 0
    # pooled ply counts must equal the sum of the per-game ply counts
    n_tile = sum(PINS[g]["n_tile_plies"] for g in PINS)
    n_meeple = sum(PINS[g]["n_meeple_plies"] for g in PINS)
    assert cat["branching"]["tile"]["all"]["n"] == n_tile
    assert cat["branching"]["meeple"]["all"]["n"] == n_meeple
    assert (cat["branching"]["tile"]["all"]["forced_plies"]
            == sum(PINS[g]["tile_forced"] for g in PINS))
    md = dd.to_markdown(cat)
    assert "Decision density" in md and "walled" in md
    # every table row must have a consistent pipe count within its block
    assert md.count("| ply kind | phase |") == 1
    assert json.dumps(cat)  # JSON-serialisable end to end


# --------------------------------------------------------------------------- #
# corpus/profile plumbing — the fail-loud paths                                 #
# --------------------------------------------------------------------------- #
def _mini_dir(tmp_path, games, profile_block) -> Path:
    d = tmp_path / "corpus"
    (d / "actions").mkdir(parents=True)
    for g in games:
        (d / "actions" / f"seed_{g['deck_seed']}.json").write_text(json.dumps(g))
    (d / "manifest.json").write_text(json.dumps(
        {"kind": "gen_fair_distill", "rules_profile": profile_block}))
    return d


def test_dir_corpus_reads_profile_from_manifest(tmp_path, fixture_games):
    d = _mini_dir(tmp_path, list(fixture_games.values()),
                  {"name": "walled", "r9_env_expected": False,
                   "r9_env_observed": False, "r9_env_ok": True})
    corpus = dd.load_corpus(d)
    assert corpus["kind"] == "gen_fair_distill_dir"
    assert len(corpus["games"]) == 3
    prof = dd.resolve_corpus_profile(corpus, None)
    assert prof["name"] == "walled"
    assert prof["source"].startswith("corpus manifest")
    assert dd.r9_env_value(prof) is False


def test_fixed_v1_manifest_demands_r9(tmp_path, fixture_games):
    d = _mini_dir(tmp_path, list(fixture_games.values()),
                  {"name": "fixed_v1", "r9_env_expected": True,
                   "r9_env_observed": True, "r9_env_ok": True})
    prof = dd.resolve_corpus_profile(dd.load_corpus(d), None)
    assert prof["name"] == "fixed_v1"
    assert dd.r9_env_value(prof) is True


def test_cli_profile_disagreeing_with_manifest_raises(tmp_path, fixture_games):
    d = _mini_dir(tmp_path, list(fixture_games.values()), {"name": "centered18"})
    with pytest.raises(dd.CorpusFormatError, match="disagrees"):
        dd.resolve_corpus_profile(dd.load_corpus(d), "walled")


def test_r9_env_ok_false_is_refused(tmp_path, fixture_games):
    d = _mini_dir(tmp_path, list(fixture_games.values()),
                  {"name": "fixed_v1", "r9_env_expected": True,
                   "r9_env_observed": False, "r9_env_ok": False})
    with pytest.raises(dd.CorpusFormatError, match="r9_env_ok"):
        dd.resolve_corpus_profile(dd.load_corpus(d), None)


def test_unstamped_corpus_without_cli_profile_raises(tmp_path, fixture_games):
    d = _mini_dir(tmp_path, list(fixture_games.values()), {})
    with pytest.raises(dd.CorpusFormatError, match="no rules_profile"):
        dd.resolve_corpus_profile(dd.load_corpus(d), None)


def test_bad_corpus_shapes_raise(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(dd.CorpusFormatError, match="actions/"):
        dd.load_corpus(tmp_path / "empty")
    with pytest.raises(dd.CorpusFormatError, match="no such corpus"):
        dd.load_corpus(tmp_path / "nope")
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({"game_id": 1, "n_plies": 2}) + "\n")
    with pytest.raises(dd.CorpusFormatError, match="without actions"):
        dd.load_corpus(bad)


def test_r9_latch_mismatch_is_fatal(walled_env):
    """The R9 latch cannot be changed after import — the check must say so."""
    with pytest.raises(dd.CorpusFormatError, match="CARCASSONNE_FIX_R9"):
        dd.verify_environment("walled", True)


# --------------------------------------------------------------------------- #
# pure helpers                                                                  #
# --------------------------------------------------------------------------- #
def test_tercile_boundaries():
    assert dd.tercile_of(0, 72) == "early"
    assert dd.tercile_of(23, 72) == "early"
    assert dd.tercile_of(24, 72) == "mid"
    assert dd.tercile_of(47, 72) == "mid"
    assert dd.tercile_of(48, 72) == "late"
    assert dd.tercile_of(71, 72) == "late"
    assert dd.tercile_of(0, 0) == "early"       # degenerate game, no crash


def test_dist_shape():
    d = dd._dist([1, 2, 3, 4, 5])
    assert d["n"] == 5 and d["median"] == 3 and d["min"] == 1 and d["max"] == 5
    assert dd._dist([])["n"] == 0
    assert dd._dist([None, 2])["n"] == 1


def test_phase_c_runner_imports():
    """The runner must import without pulling the engine in (env is set later)."""
    sys.path.insert(0, str(REPO / "scripts" / "human_anchor"))
    mod = importlib.import_module("run_phase_c")
    assert hasattr(mod, "luck_slice") and hasattr(mod, "build_document")
    assert mod.TARGET_WRS


def test_luck_slice_math(fixture_games):
    sys.path.insert(0, str(REPO / "scripts" / "human_anchor"))
    mod = importlib.import_module("run_phase_c")
    corpus = {"games": list(fixture_games.values())}
    sl = mod.luck_slice(corpus, "pin3")
    assert sl["n_games"] == 3
    margins = [g["score_p0"] - g["score_p1"] for g in fixture_games.values()]
    assert sl["mean_seat0_margin"] == pytest.approx(sum(margins) / 3)
    assert sl["sigma_game"] > 0
    # the paired half must be advertised as missing, never silently filled in
    assert sl["not_derivable"]["luck_share_icc"]
    for k in sl["sizing_unpaired"]:
        assert sl["sizing_unpaired"][k]["n_games_paired_test"] is None
