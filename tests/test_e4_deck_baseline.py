"""Tests for the E4 deck-baseline driver + estimator.

Two contracts, both load-bearing for the readout:

1. **DECK RECONSTRUCTION.** The driver's deal (`random.seed(deck_seed)` ->
   `Game(**profile.game_kwargs())` under `fixed_v1` + R9) must reproduce the SAME
   deck Joshua played. Proven the only way that proves anything: replay the real
   archive's action sequence on the reconstructed board and assert the engine's
   recomputed final scores equal the phone's recorded scores. A wrong deck cannot
   survive a 140-action replay.

2. **THE ESTIMATOR.** `control_variate` on synthetic data with a KNOWN deck effect:
   beta_hat must recover the planted slope, the centred adjustment must leave the
   point estimate untouched, and the se must shrink when the deck effect is real
   and NOT shrink when it is absent.

⚠️ Test 1 needs `CARCASSONNE_FIX_R9=1` latched at `carcassonne_ai.base_deck` import
time, so it is exported at module import and the test SKIPS (never silently grades
the wrong farms) if another test module already latched it off.
"""
from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "human_anchor"))

# R9 must be in the env BEFORE carcassonne_ai.base_deck imports (Rust OnceLock).
os.environ.setdefault("CARCASSONNE_FIX_R9", "1")

import e4_deck_baseline as DB  # noqa: E402
from e4_deck_baseline_analyze import control_variate, deck_summaries, corr  # noqa: E402


# --------------------------------------------------------------------------- #
# archive selection                                                            #
# --------------------------------------------------------------------------- #
def test_selects_only_fixed_v1_archives():
    picked = DB.select_archives()
    assert len(picked) >= 12, "expected the 12 fixed_v1 E4 archives"
    assert all(a["rules_profile"] == "fixed_v1" for a in picked)
    # the pre-fixed_v1 archives (2 walled + 1 app_aug2) must NOT be selected, and the
    # discriminator is the stamp's ABSENCE — never (start_rule, grid_rule).
    all_files = {p.name for p in DB.DEFAULT_ARCHIVES.glob("*.json")}
    excluded = all_files - {a["file"] for a in picked}
    for name in excluded:
        a = json.loads((DB.DEFAULT_ARCHIVES / name).read_text())
        assert a.get("rules_profile") != "fixed_v1"
    assert all(a["human_player"] == 0 for a in picked), "sign convention assumes seat 0"


def test_replicate_seeds_distinct_and_deterministic():
    seen = set()
    for r in range(8):
        s0, s1 = DB.replicate_seeds(r)
        assert s0 != s1
        assert (s0, s1) == DB.replicate_seeds(r)      # deterministic
        seen |= {s0, s1}
    assert len(seen) == 16                            # all distinct across replicates


def test_build_cells_skips_done_and_is_replicate_major():
    archives = [{"deck_seed": 1}, {"deck_seed": 2}]
    cells = DB.build_cells(archives, k=3, done={(1, 0)})
    assert (1, 0) not in {(c[0], c[1]) for c in cells}
    assert len(cells) == 3 * 2 - 1
    # replicate-major: every deck's replicate 0 comes before any replicate 1
    reps = [c[1] for c in cells]
    assert reps == sorted(reps)


def test_load_done_survives_a_torn_line(tmp_path):
    p = tmp_path / "sp.jsonl"
    p.write_text(json.dumps({"deck_seed": 5, "replicate": 0}) + "\n"
                 + '{"deck_seed": 5, "repl')      # dirty-crash tail
    assert DB.load_done(p) == {(5, 0)}


# --------------------------------------------------------------------------- #
# 1. deck reconstruction — the archive replays to its recorded scores           #
# --------------------------------------------------------------------------- #
@pytest.mark.slow
def test_deck_reconstruction_replays_archive_to_recorded_scores():
    """The driver's deal is the same deck the phone dealt — proven by replay."""
    import env_preamble  # noqa: F401  production leaf env, before carcassonne_ai
    from carcassonne_ai import rules_profile

    if not rules_profile.r9_env_on():
        pytest.skip("CARCASSONNE_FIX_R9 latched off by another module; run this file alone")

    from carcassonne_ai.game_wrapper import Game

    prof = rules_profile.activate("fixed_v1")
    picked = DB.select_archives()
    assert picked, "no fixed_v1 archives"

    # two archives is enough to catch a wrong deal and keeps the test quick
    for meta in picked[:2]:
        arch = json.loads(Path(meta["path"]).read_text())
        # EXACTLY the driver's deal (play_harness.play_game seeds immediately before
        # get_init_board, which is what the root_replay contract fixes).
        random.seed(int(arch["deck_seed"]))
        game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
        board = game.get_init_board()
        for ply, a in enumerate(arch["actions"]):
            valid = game.get_valid_moves(board)
            assert valid[int(a)] == 1, (
                f"{meta['file']}: archived action {a} illegal at ply {ply} — "
                "the reconstructed deck is NOT the deck that was played")
            board, _ = game.get_next_state(board, int(a))
        assert game.get_game_ended(board, 0) != 0.0, f"{meta['file']}: replay did not end"
        assert list(board.state.scores) == meta["scores"], (
            f"{meta['file']}: replayed scores {list(board.state.scores)} != recorded "
            f"{meta['scores']}")


# --------------------------------------------------------------------------- #
# 2. the estimator                                                             #
# --------------------------------------------------------------------------- #
def _synthetic(n, beta, deck_sd, noise_sd, seed=11):
    """m_i = alpha + beta*d_i + eps_i with a PLANTED deck effect d_i."""
    rng = random.Random(seed)
    d = [rng.gauss(0.0, deck_sd) for _ in range(n)]
    m = [3.0 + beta * di + rng.gauss(0.0, noise_sd) for di in d]
    return m, d


def test_beta_hat_recovers_a_planted_slope():
    m, d = _synthetic(4000, beta=0.8, deck_sd=10.0, noise_sd=5.0)
    est = control_variate(m, d)
    assert abs(est["beta_hat"]["beta"] - 0.8) < 0.05
    assert abs(est["corr_m_d"] - corr(m, d)) < 1e-12


def test_centred_adjustment_never_moves_the_point_estimate():
    m, d = _synthetic(60, beta=0.7, deck_sd=12.0, noise_sd=15.0, seed=3)
    est = control_variate(m, d)
    raw = est["unadjusted"]["estimate"]
    assert abs(est["beta1"]["estimate"] - raw) < 1e-9
    assert abs(est["beta_hat"]["estimate"] - raw) < 1e-9


def test_real_deck_effect_shrinks_the_se_and_headline_follows():
    m, d = _synthetic(400, beta=1.0, deck_sd=12.0, noise_sd=8.0, seed=5)
    est = control_variate(m, d)
    assert est["var_ratio_beta_hat"] < 0.6, "a strong deck effect must reduce variance"
    assert est["adjustment_helped"] is True
    assert est["headline"] == "beta_hat"


def test_absent_deck_effect_does_not_let_beta1_win_the_headline():
    """beta=1 subtraction with NO real deck effect ADDs variance — the trap the spec
    pre-registers. beta_hat shrinks toward 0 and stays ~harmless; and beta=1 is never
    allowed to be the headline whatever it does."""
    m, d = _synthetic(400, beta=0.0, deck_sd=12.0, noise_sd=15.0, seed=7)
    est = control_variate(m, d)
    assert est["var_ratio_beta1"] > 1.0, "naive subtraction should ADD variance here"
    assert abs(est["beta_hat"]["beta"]) < 0.25
    assert est["headline"] in ("unadjusted", "beta_hat")
    assert est["headline"] != "beta1"


def test_deck_summaries_and_uncentred_supplement():
    recs = [{"deck_seed": 1, "margin_seat0_minus_seat1": x} for x in (10, 20)]
    recs += [{"deck_seed": 2, "margin_seat0_minus_seat1": x} for x in (-4, 4)]
    s = deck_summaries(recs)
    assert s[1]["mean"] == 15.0 and s[1]["n"] == 2
    assert s[2]["mean"] == 0.0
    est = control_variate([1.0, 2.0, 3.0], [10.0, 0.0, -10.0])
    assert abs(est["mean_deck_value"] - 0.0) < 1e-12
    assert abs(est["uncentred_beta1_estimate"] - 2.0) < 1e-12
