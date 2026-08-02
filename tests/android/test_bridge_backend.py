"""The android_bridge backend flag (P7).

Two things are under test and they matter for different reasons:

1. **The default did not move.** The phone keeps playing the Python k4x688 path
   until Joshua flips it. A regression here would silently change what the
   shipped app plays, which is the one thing this phase must not do.
2. **The mirror tracks the engine.** When the rust backend IS selected, the
   `carc_rs` game advanced at the bridge's single choke point must render the
   same `string_representation` as the Python engine, ply for ply. That is the
   same byte-equality claim G1 gates, evaluated through the bridge's own plumbing
   (deck harvest, start_rule translation, `apply()`), which is the part G1 never
   saw.

NOT under test here: move identity. The bridge builds the mirror with the
ANDROID libm flavour (`msun`, measured at G7 leg 1); on this x86-64 desktop the
platform flavour is `glibc_fma`, so a move-identity assertion would be testing
the wrong platform's arithmetic. P3 §3 (the search is nearly libm-blind) is why
that does not disturb the mirror check, and `scripts/rustport/reconcile_fair.py`
is where move identity actually belongs.

WHY IT LIVES IN tests/android AND NOT tests/rustport
----------------------------------------------------
Importing `android_bridge` runs its PROD_ENV block, which `setdefault`s the leaf
DISPATCH knobs (`CARCASSONNE_USE_FLAT_LEAF`, `CARCASSONNE_USE_CY_REPR`) — and
those decide which IMPLEMENTATION every later test in the same process measures.
`scripts/rustport/prod_leaf_env` deliberately sets the leaf SHAPE only, for
exactly that reason ("G1-G5 were gated with the dispatch knobs as the scripts
found them"). Collected alongside the rustport gate tests, this module's import
alone flipped eight of them red. tests/android already lives in that environment,
so it is the only place this file is free.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "android" / "app" / "src" / "main" / "python"))

import android_bridge as B  # noqa: E402

carc_rs = pytest.importorskip("carc_rs", reason="the desktop dev wheel is not built")


def _j(s: str) -> dict:
    d = json.loads(s)
    assert d.get("ok"), d
    return d


@pytest.fixture(autouse=True)
def _reset():
    yield
    B.reset()


# --------------------------------------------------------------------------- #
# 1. the default                                                               #
# --------------------------------------------------------------------------- #
def test_default_backend_is_rust():
    """⚠️ FLIPPED 2026-08-01 (Joshua: "2 yes"). The phone plays the Rust champion by
    default; this is what pays for the mobile budget unpin (11008 sims = 1.551 s/move
    on carc_rs, ~25 s/move on Python). A regression here silently changes what the
    shipped app plays AND what budget it can afford."""
    assert B.BACKEND_DEFAULT == B.BACKEND_RUST
    st = _j(B.new_game(json.dumps({"seed": 5, "opponent": "tier1"})))
    assert st["backend"] == "rust", st["backend_note"]
    assert B._S.rs is not None, "the rust backend must build a mirror"


def test_python_is_still_selectable_and_builds_no_mirror():
    st = _j(B.new_game(json.dumps({"seed": 5, "opponent": "tier1",
                                   "backend": "python"})))
    assert st["backend"] == "python"
    assert st["backend_note"] is None
    assert B._S.rs is None, "the Python backend must not build a Rust mirror"


def test_unknown_backend_is_refused_not_defaulted():
    # Silently defaulting would let a typo run a different agent than asked for.
    d = json.loads(B.new_game(json.dumps({"seed": 5, "backend": "rustt"})))
    assert not d["ok"]
    assert "backend" in d["error"]["message"]


# --------------------------------------------------------------------------- #
# 2. the mirror                                                                #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("start_rule", ["retail", "engine"])
def test_rust_mirror_tracks_the_engine_ply_for_ply(start_rule, monkeypatch):
    """Both start rules, because the deck harvest differs between them: retail
    pulls the D tile out of the shuffled pool, engine does not."""
    monkeypatch.setenv("CARC_RS_RECONCILE", "1")
    monkeypatch.setattr(B, "_RS_RECONCILE", True)

    st = _j(B.new_game(json.dumps({
        "seed": 11, "opponent": "tier1", "backend": "rust",
        "start_rule": start_rule,
    })))
    assert st["backend"] == "rust", st["backend_note"]
    s = B._S
    assert s.rs is not None
    # The mirror's own view of the start rule must be the session's.
    assert s.rs.start_rule() == start_rule

    # 40 plies of legal play. `_assert_mirror` runs inside `apply()` under
    # CARC_RS_RECONCILE, so an ImportError-free run IS the assertion.
    import random

    rng = random.Random(4242)
    for _ in range(40):
        if st["is_terminated"]:
            break
        ids = st["legal"]["action_ids"]
        if not ids:
            break
        st = _j(B.apply_action(rng.choice(ids)))
    assert s.game.string_representation(s.board) == s.rs.string_repr()
    assert list(s.rs.scores()) == list(st["scores"])


def test_mirror_survives_undo(monkeypatch):
    """`undo_last_tile` rebuilds the session by replaying the log. The mirror has
    no undo of its own — it is rebuilt with it — so this checks the choke-point
    design rather than any undo-specific code."""
    monkeypatch.setattr(B, "_RS_RECONCILE", True)
    st = _j(B.new_game(json.dumps({
        "seed": 3, "opponent": "tier1", "backend": "rust", "human_player": 0,
    })))
    # Play into the human's meeple sub-phase, which is where undo is legal.
    steps = 0
    while st["phase"] != "meeples" and not st["is_terminated"] and steps < 20:
        st = _j(B.apply_action(st["legal"]["action_ids"][0]))
        steps += 1
    if st["phase"] != "meeples" or not st["is_human_turn"]:
        pytest.skip("did not reach a human meeple decision in 20 plies")
    st = _j(B.undo_last_tile())
    s = B._S
    assert s.rs is not None, s.rs_note
    assert s.game.string_representation(s.board) == s.rs.string_repr()


def test_rust_unavailable_degrades_to_python(monkeypatch):
    """A missing wheel must lose the speedup, not the game."""
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) \
        else __builtins__.__import__

    def no_carc_rs(name, *a, **kw):
        if name == "carc_rs":
            raise ImportError("simulated: no wheel for this ABI")
        return real_import(name, *a, **kw)

    monkeypatch.setattr("builtins.__import__", no_carc_rs)
    st = _j(B.new_game(json.dumps({"seed": 7, "opponent": "tier1", "backend": "rust"})))
    assert st["backend"] == "python"
    assert "carc_rs unavailable" in (st["backend_note"] or "")


def test_rust_unavailable_also_drops_the_budget_not_just_the_engine(monkeypatch):
    """THE COUPLING GUARD (2026-08-01 unpin). The mobile profile's k8x1376 is priced
    for the Rust core. Degrading the ENGINE while keeping the BUDGET would hand the
    phone a ~25 s/move champion — the exact UX the carve-out existed to prevent. So a
    session that cannot get carc_rs must land on the k4x688 floor as well."""
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) \
        else __builtins__.__import__

    def no_carc_rs(name, *a, **kw):
        if name == "carc_rs":
            raise ImportError("simulated: no wheel for this ABI")
        return real_import(name, *a, **kw)

    monkeypatch.setattr("builtins.__import__", no_carc_rs)
    st = _j(B.new_game(json.dumps({"seed": 7, "opponent": "champion",
                                   "backend": "rust", "verify": False})))
    s = B._S
    assert st["backend"] == "python" and s.rs is None
    assert (s.eff_k_dets, s.eff_sims) == (
        B.ANDROID_FALLBACK_BUDGET["k_dets"], B.ANDROID_FALLBACK_BUDGET["sims_per_det"])
    assert "REDUCED" in (st["budget_note"] or ""), st["budget_note"]


def test_restore_reseats_the_rust_mirror():
    """A resumed game must play the SAME champion the saved one did.

    The replay reaches the position with `advance()` only, which runs neither the
    search nor the endgame-latch trigger — so the mirror's own move counter and latch
    are still at zero unless `restore_game` seats them (`FairAgentRs.set_latched`'s
    docstring names exactly this case). Unseated, the resumed champion derives
    different per-move search seeds and can play a different move from the same
    position. Asserted behaviourally, which is the property that actually matters."""
    cfg = {"seed": 31, "opponent": "champion", "human_player": 0,
           "backend": "rust", "sims": 8, "k_dets": 2, "verify": False}
    st = _j(B.new_game(json.dumps(cfg)))
    if st["backend"] != "rust":
        pytest.skip(f"no rust backend here: {st['backend_note']}")
    for _ in range(10):
        if st["is_terminated"]:
            break
        st = _j(B.apply_action(st["legal"]["action_ids"][0])
                if st["is_human_turn"] else B.ai_move())
    live_stats = B._S.rs.stats()
    assert live_stats["move_idx"] > 0, "the live mirror never searched"
    save = _j(B.save_game())

    # STRUCTURAL, not behavioural: at a tiny test budget two different seeds usually
    # pick the same move anyway, so a move-equality assertion here passes even with
    # the re-seating deleted (verified). The timeline itself is the contract.
    r = _j(B.restore_game(json.dumps(save)))
    assert B._S.rs is not None, B._S.rs_note
    got = B._S.rs.stats()
    assert got["move_idx"] == live_stats["move_idx"] == r["restored"]["ai_decisions"], (
        "the restored mirror's move counter was not re-seated — the resumed champion "
        "would derive different per-move search seeds than the saved one")
    assert got["latched"] == live_stats["latched"]


def test_pre_flip_e4_archives_still_restore_under_the_new_default():
    """BACKWARD COMPAT for the 2026-08-01 flip, at the BRIDGE level.

    The real E4 archives were written by the PRE-flip app: no `start_rule` key (so
    they mean the legacy "engine" rule) and `sims`/`k_dets` null (so a restore
    resolves whatever the CURRENT profile says — which the unpin just moved from
    2752 to 11008). Both of those are exactly the kind of thing a budget/rule flip
    breaks, and these two files are the only human-vs-champion games that exist, so
    a regression here is unrecoverable data.

    tests/rustport/test_p1_engine.py replays them at the ENGINE level; this asserts
    the BRIDGE path — the one the app's Past-games list actually calls.
    """
    archives = sorted((REPO / "measurement" / "e4_games").glob("*.json"))
    if not archives:
        pytest.skip("no E4 archives in this checkout")
    for path in archives:
        blob = json.loads(path.read_text())
        r = _j(B.restore_game(json.dumps(blob)))
        assert B._S.start_rule == B.START_RULE_ENGINE, \
            f"{path.name}: an archive with no start_rule must replay as 'engine'"
        assert r["restored"]["actions"] == len(blob["actions"])
        assert r["scores"] == blob["scores"], f"{path.name}: replay diverged"
        # The archive keeps its OWN budget, so E4 grading of old games is untouched
        # by the unpin — the new champion budget must not be retro-applied to them.
        assert (blob["k_dets_effective"], blob["sims_effective"]) == (4, 688)


def test_runtime_info_reports_rust():
    info = _j(B.runtime_info())
    assert "rust" in info
    assert info["rust"]["default_backend"] == "rust"
    assert info["rust"]["available"] is True
    # available != active: `active` is about a LIVE session, and there is none here.
    assert info["rust"]["active"] is False
    assert info["rust"]["tanh_flavor"] == B.ANDROID_TANH_FLAVOR


# --------------------------------------------------------------------------- #
# 3. the mirror on the RECENTRED grid (2026-08-02)                              #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("grid_rule", ["centered18", "engine6"])
def test_the_mirror_plays_the_same_grid_as_the_engine(grid_rule):
    """The champion must search the grid that is on screen.

    The recentring changes the legal-move set from ply one, so a mirror left on
    the engine's (6, 15) would be picking moves for a different game — and
    because the mirror is a STATE mirror first, that shows up as a repr
    divergence rather than as a quietly weaker opponent. `_assert_mirror` runs
    inside `apply()` under CARC_RS_RECONCILE, so a full clean game IS the
    assertion (`MirrorDesync` would raise loudly at the first bad ply).
    """
    import random

    monkey = pytest.MonkeyPatch()
    monkey.setattr(B, "_RS_RECONCILE", True)
    try:
        st = _j(B.new_game(json.dumps({
            "seed": 17, "opponent": "tier1", "backend": "rust",
            "grid_rule": grid_rule,
        })))
        assert st["backend"] == "rust", st["backend_note"]
        s = B._S
        assert s.rs is not None, s.rs_note
        want_row = 18 if grid_rule == "centered18" else 6
        assert s.grid_row == want_row
        assert (st["board"][0]["row"], st["board"][0]["col"]) == (want_row, 15)
        # `string_representation` emits ABSOLUTE engine coordinates (it walks
        # `placed_coords`, not the window), so repr equality IS a grid check —
        # a mirror seated on (6, 15) against an engine on (18, 15) diverges on
        # the very first tile. `_start_rust_mirror` already ran `_assert_mirror`
        # at game start, which is why `s.rs is not None` above is meaningful.
        assert s.game.string_representation(s.board) == s.rs.string_repr()
        assert f"{want_row}, 15," in s.rs.string_repr(), \
            "the mirror is not showing the start tile at the recentred row"

        # A FULL game, both seats, every ply digest-checked.
        rng = random.Random(99)
        plies = 0
        while not st["is_terminated"]:
            plies += 1
            assert plies <= 400, "game did not terminate"
            ids = st["legal"]["action_ids"]
            st = _j(B.apply_action(rng.choice(ids)))
        assert plies > 100, f"probe degenerate: only {plies} plies"
        assert s.game.string_representation(s.board) == s.rs.string_repr()
        assert list(s.rs.scores()) == list(st["scores"])
    finally:
        monkey.undo()


def test_an_odd_grid_row_cannot_reach_the_mirror():
    """The EVEN-shift refusal is enforced on BOTH sides, and the bridge never
    gets to construct a half-configured mirror: `_Session` rejects the unknown
    rule name before any engine is built."""
    d = json.loads(B.new_game(json.dumps({"seed": 5, "backend": "rust",
                                          "grid_rule": "centered17"})))
    assert not d["ok"] and d["error"]["code"] == "ValueError"
    assert B._S is None or B._S.grid_rule in B.GRID_RULE_START
