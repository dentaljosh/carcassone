"""Per-game wall watchdog + OpenBLAS-pin regression guards for eval_puct_priors.

Root cause of the 2026-07-06 curve175 n=400 hang: the harness pins OMP/MKL threads
but the installed numpy is scipy-OpenBLAS, so every net-free CPU worker spawned a
box-sized (32) busy-waiting BLAS pool → 54 workers oversubscribed the boxes and made
no progress for hours. Fix 1: pin OPENBLAS_NUM_THREADS=1 in the canon env (result-
neutral). Fix 2 (safety net, tested here): a per-game wall watchdog that ABANDONS a
game exceeding CARCASSONNE_GAME_WALL_SECS and records it as a `game_timeout`, so one
pathological deck can never wedge a Pool worker — and the eval always completes.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "classical_search" / "eval_puct_priors.py"

_spec = importlib.util.spec_from_file_location("eval_puct_priors", SCRIPT)
epp = importlib.util.module_from_spec(_spec)
sys.modules["eval_puct_priors"] = epp  # fork-Pool workers unpickle _play_one by module name
_spec.loader.exec_module(epp)


def _mk_result(seed, a_seat, diff, game_timeout=False):
    """A minimal GameResult (only the fields _summary reads)."""
    return epp.GameResult(
        seed=seed, a_seat=a_seat, cand_sims=48, champ_sims=48,
        score_p0=10, score_p1=10 - diff, diff=diff,
        won_by_cand=(diff > 0), drew=(diff == 0), elapsed_s=1.0, moves=10,
        cand_prefix_moves=5, champ_prefix_moves=5, game_timeout=game_timeout)


# --------------------------------------------------------------------------- #
# Root-cause fix: the OpenBLAS pin must be in the canon env.                    #
# --------------------------------------------------------------------------- #
def test_openblas_threads_pinned_in_canon_env():
    # The actual BLAS backend is OpenBLAS; without this pin each worker spawns a
    # 32-thread busy-wait pool → the oversubscription hang. Guard it.
    assert epp._CANON_ENV.get("OPENBLAS_NUM_THREADS") == "1"
    # and it actually took effect for this process (setdefault at import, pre-numpy)
    import os
    assert os.environ.get("OPENBLAS_NUM_THREADS") == "1"


# --------------------------------------------------------------------------- #
# Watchdog accounting: _summary excludes game_timeout games from every stat.    #
# --------------------------------------------------------------------------- #
def test_summary_excludes_game_timeouts():
    results = [
        _mk_result(1, 0, +4), _mk_result(1, 1, -2),   # a completed pair
        _mk_result(2, 0, +6), _mk_result(2, 1, +2),   # another completed pair
        _mk_result(3, 0, 0, game_timeout=True),        # abandoned — must be excluded
        _mk_result(3, 1, 0, game_timeout=True),
    ]
    summ = epp._summary(results, 48, 48)
    assert summ["n"] == 4                 # only the 4 completed games
    assert summ["W"] + summ["D"] + summ["L"] == 4
    assert summ["game_timeouts"] == 2
    assert summ["n_paired"] == 2          # the 2 fully-completed decks only


def test_summary_all_timeouts_is_graceful():
    results = [_mk_result(1, 0, 0, game_timeout=True),
               _mk_result(1, 1, 0, game_timeout=True)]
    summ = epp._summary(results, 48, 48)      # must not ZeroDivisionError
    assert summ["n"] == 0 and summ["game_timeouts"] == 2


# --------------------------------------------------------------------------- #
# Watchdog fires end-to-end: a ~0s budget abandons every game, the eval still   #
# completes, records game_timeout=True per seed, and reports the count.         #
# --------------------------------------------------------------------------- #
def test_watchdog_fires_end_to_end(tmp_path, monkeypatch):
    # Use whichever module object is registered in sys.modules (another test file may
    # have re-registered "eval_puct_priors"): the fork-Pool pickles _play_one by that
    # name, so main()'s module must BE the registered one, and the monkeypatch must
    # land on it (forked workers inherit its GAME_WALL_SECS global).
    m = sys.modules["eval_puct_priors"]
    monkeypatch.setattr(m, "GAME_WALL_SECS", 1e-9)
    rc = m.main([
        "--candidate", "h48", "--opponent", "h48", "--exact-k", "2",
        "--n", "2", "--paired", "--workers", "2",
        "--seed-start", "9990010000",
        "--out-root", str(tmp_path), "--no-results-csv"])
    assert rc == 0
    out = tmp_path / "rr_h48_vs_h48_k2"
    recs = [json.load(open(p)) for p in out.glob("seed*.json")]
    assert len(recs) == 2
    assert all(r["game_timeout"] is True for r in recs)    # every game abandoned
    summ = json.load(open(out / "summary.json"))
    assert summ["n"] == 0 and summ["game_timeouts"] == 2


def test_watchdog_off_completes_normally(tmp_path, monkeypatch):
    # Default-safe: with a generous budget (nothing hangs) the games complete and
    # NONE are flagged game_timeout — byte-identical to pre-watchdog behavior.
    m = sys.modules["eval_puct_priors"]
    monkeypatch.setattr(m, "GAME_WALL_SECS", 3600.0)
    rc = m.main([
        "--candidate", "h48", "--opponent", "h48", "--exact-k", "2",
        "--n", "2", "--paired", "--workers", "2",
        "--seed-start", "9990020000",
        "--out-root", str(tmp_path), "--no-results-csv"])
    assert rc == 0
    out = tmp_path / "rr_h48_vs_h48_k2"
    recs = [json.load(open(p)) for p in out.glob("seed*.json")]
    assert len(recs) == 2 and all(r["game_timeout"] is False for r in recs)
    summ = json.load(open(out / "summary.json"))
    assert summ["n"] == 2 and summ["game_timeouts"] == 0
