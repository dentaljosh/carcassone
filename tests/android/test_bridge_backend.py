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
    # SELECT the pre-flip archives, don't assume every archive is one. Post-flip
    # games (2026-08-02 build onward) legitimately carry `start_rule`/`grid_rule`
    # and the k8x1376 budget; asserting 'engine' + (4, 688) over them tests the
    # opposite of this test's contract. Added 2026-08-05, when the first post-flip
    # archive (the 98-78 win) landed and turned this glob red.
    pre_flip = [p for p in archives
                if not json.loads(p.read_text()).get("start_rule")]
    if not pre_flip:
        pytest.skip("no PRE-flip E4 archives in this checkout")
    for path in pre_flip:
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


def test_the_msun_flavour_actually_reaches_the_rust_search(monkeypatch):
    """The claim that matters, asserted behaviourally (ROUND2 F-12).

    `test_runtime_info_reports_rust` compares `runtime_info()`'s output to the module
    constant that `runtime_info()` interpolates, so it cannot fail whatever the Rust
    core is configured with — the same label-not-function shape the flip fixed for the
    leaf config. What G7 leg 1 measured is that ANDROID needs the **msun** tanh/expm1
    flavour (it differs from this desktop's glibc_fma), and the only thing that makes
    that true at runtime is the argument reaching `carc_rs.SearchConfigRs`."""
    seen: dict = {}
    real = carc_rs.SearchConfigRs

    def spy(*args, **kw):
        seen["args"] = args
        return real(*args, **kw)

    monkeypatch.setattr(carc_rs, "SearchConfigRs", spy)
    st = _j(B.new_game(json.dumps({"seed": 5, "opponent": "tier1",
                                   "backend": "rust"})))
    assert st["backend"] == "rust", st["backend_note"]
    args = seen["args"]
    assert B.ANDROID_TANH_FLAVOR == "msun", "G7 leg 1 measured msun on every ABI"
    assert args[11] == B.ANDROID_TANH_FLAVOR, \
        "the libm flavour the Rust search runs is not the one G7 measured on Android"
    assert args[10] == B.ANDROID_EXP_FMA


def test_the_manifest_says_carc_rs_played(monkeypatch):
    """ROUND2 F-8. `get_manifest()` is documented as "the manifest of the agent that is
    ACTUALLY playing", but it comes from the bridge's PYTHON anchor (built with
    `backend=python` on purpose), and champion_factory stamps its backend block only
    when the backend is NOT the python default — so under the rust flip the phone
    carried a byte-identical pure-Python manifest while carc_rs picked every move."""
    st = _j(B.new_game(json.dumps({"seed": 5, "opponent": "champion",
                                   "backend": "rust", "sims": 8, "k_dets": 1,
                                   "verify": False})))
    if st["backend"] != "rust":
        pytest.skip(f"no rust backend here: {st['backend_note']}")
    man = _j(B.get_manifest())["manifest"]
    assert man["backend"]["name"] == "rust"
    assert man["backend"]["role"] == "move_chooser"
    assert man["backend"]["anchor"] == "python"
    # The anchor is untouched: it is still the Python agent that owns the manifest.
    assert man["agent_class"] == "FairHeuristicPriorAgent"

    # Against tier1 the mirror is state-only, and the manifest must not overclaim.
    _j(B.new_game(json.dumps({"seed": 5, "opponent": "tier1", "backend": "rust"})))
    assert _j(B.get_manifest())["manifest"] is None       # tier1 has no manifest

    # A python game keeps a manifest with no backend block (champion_factory's rule).
    _j(B.new_game(json.dumps({"seed": 5, "opponent": "champion",
                              "backend": "python", "sims": 8, "k_dets": 1,
                              "verify": False})))
    assert "backend" not in _j(B.get_manifest())["manifest"]


def _no_carc_rs(monkeypatch):
    """Simulate a device whose ABI has no wheel."""
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) \
        else __builtins__.__import__

    def no_carc_rs(name, *a, **kw):
        if name == "carc_rs":
            raise ImportError("simulated: no wheel for this ABI")
        return real_import(name, *a, **kw)

    monkeypatch.setattr("builtins.__import__", no_carc_rs)


def test_production_budget_never_advertises_a_budget_this_device_cannot_pay(monkeypatch):
    """ROUND2 F-6. `production_budget()` is the ONLY budget the Home and Settings
    screens print, and it called `mobile_budget()` directly — whose own docstring warns
    that ignoring the backend "reintroduces exactly the hang the carve-out existed to
    prevent". On a device without carc_rs it advertised 11008 sims/move while every
    game actually started at the k4x688 floor."""
    B.reset()
    full = _j(B.production_budget())
    assert full["backend"] == "rust" and full["floored"] is False

    _no_carc_rs(monkeypatch)
    floored = _j(B.production_budget())
    assert floored["backend"] == "python"
    assert floored["floored"] is True
    assert (floored["k_dets"], floored["sims_per_det"]) == (
        B.ANDROID_FALLBACK_BUDGET["k_dets"],
        B.ANDROID_FALLBACK_BUDGET["sims_per_det"])
    assert floored["total_sims"] < floored["champion_of_record_total_sims"]
    # The YAML profile is still reported, just not as the headline.
    assert floored["profile_sims_per_det"] == full["sims_per_det"]


def test_an_explicit_python_request_does_not_claim_the_device_lacks_rust():
    """ROUND2 F-7. `budget_for_backend` sets `floored` whenever the session is python
    and the profile is rust — it cannot tell a MISSING WHEEL from a caller that asked
    for python. Keying the note on it alone asserted a hardware fact that was false,
    and `archive_record` persists that sentence into the permanent E4 record."""
    st = _j(B.new_game(json.dumps({"seed": 5, "opponent": "champion",
                                   "backend": "python", "verify": False})))
    note = st["budget_note"] or ""
    assert "REDUCED" in note, note
    assert "no Rust core on this device" not in note, note
    assert "by request" in note
    assert st["backend_note"] is None


def test_the_mobile_profile_note_names_the_direction_it_actually_went():
    """2026-08-25. The `MOBILE PROFILE` note hardcoded the word BELOW, because for its
    whole life the phone could only ever be the WEAKER side (the k4x688 carve-out, then
    parity at the 2026-08-01 unpin). The owner's k16x1376 = 22016 fold inverted that.

    This matters beyond wording: the string is rendered in the app AND persisted verbatim
    into the permanent E4 archive by `archive_record`, so a hardcoded BELOW would write
    "smaller search" onto every game played at TWICE the champion budget."""
    from carcassonne_ai import champion_factory as cf

    spec = cf.load_production_spec()
    mob = B.mobile_budget(spec)
    full = spec.k_dets * spec.sims_per_det
    if mob["total_sims"] == full:
        pytest.skip("mobile profile is at parity with the champion; no note to check")

    st = _j(B.new_game(json.dumps({"seed": 7, "opponent": "champion",
                                   "human_player": 0, "backend": "rust",
                                   "verify": False})))
    if st["backend"] != "rust":
        pytest.skip(f"no rust backend here: {st['backend_note']}")
    note = st["budget_note"] or ""
    assert "MOBILE PROFILE" in note, note
    if mob["total_sims"] > full:
        assert "ABOVE the champion" in note and "larger search" in note, note
        assert "BELOW" not in note and "smaller search" not in note, note
    else:
        assert "BELOW the champion" in note and "smaller search" in note, note
    # Whichever direction, both budgets are named in full so the record is self-describing.
    assert f"{mob['total_sims']}" in note and f"{full}" in note, note


def test_a_missing_wheel_still_says_so():
    """The other half of F-7 — the true statement must survive the fix."""
    monkey = pytest.MonkeyPatch()
    _no_carc_rs(monkey)
    try:
        st = _j(B.new_game(json.dumps({"seed": 5, "opponent": "champion",
                                       "backend": "rust", "verify": False})))
        assert "no Rust core on this device" in (st["budget_note"] or "")
    finally:
        monkey.undo()


# --------------------------------------------------------------------------- #
# 5. the resolution is sticky per game (ROUND2 F-2)                            #
# --------------------------------------------------------------------------- #
def _tiny_rust_save() -> dict:
    st = _j(B.new_game(json.dumps({"seed": 31, "opponent": "champion",
                                   "human_player": 0, "backend": "rust",
                                   "sims": 8, "k_dets": 2, "verify": False})))
    if st["backend"] != "rust":
        pytest.skip(f"no rust backend here: {st['backend_note']}")
    for _ in range(6):
        if st["is_terminated"]:
            break
        st = _j(B.apply_action(st["legal"]["action_ids"][0])
                if st["is_human_turn"] else B.ai_move())
    return _j(B.save_game())


def test_a_save_records_what_it_was_played_on():
    save = _tiny_rust_save()
    assert save["backend"] == "rust"
    assert (save["k_dets_effective"], save["sims_effective"]) == (2, 8)


def test_a_resume_reproduces_the_played_budget_instead_of_re_resolving():
    """THE F-2 GUARD. Before the 2026-08-01 unpin the mobile profile was pinned
    unconditionally, so a restore reproduced the played budget by construction. Once
    the budget became conditional on the backend resolving, the same saved game could
    silently continue at a different sims/move — and `archive_record` stamped only the
    post-restore half."""
    save = _tiny_rust_save()
    # A CHAMPION save carries no explicit request (both null on the real phone path);
    # the effective pair is the only record of what it played at.
    save["sims"] = save["k_dets"] = None
    save["sims_effective"], save["k_dets_effective"] = 8, 2

    _j(B.restore_game(json.dumps(save)))
    s = B._S
    assert (s.eff_k_dets, s.eff_sims) == (2, 8), \
        "the resumed game was re-budgeted against today's device profile"
    assert s.played_backend == "rust" and s.backend == "rust"
    assert s.resume_note is None
    assert "RESUMED AT THE BUDGET THIS GAME WAS PLAYED AT" in (s.budget_note or "")


def test_a_save_with_no_backend_stamp_keeps_the_old_behaviour():
    """Every shipped E4 archive is in this class: an ABSENT stamp is not evidence
    about what the game ran, and inventing one would be worse than re-resolving."""
    save = _tiny_rust_save()
    save.pop("backend")
    save["sims"] = save["k_dets"] = None
    _j(B.restore_game(json.dumps(save)))
    s = B._S
    assert s.played_backend is None
    assert (s.eff_k_dets, s.eff_sims) == (B.mobile_budget()["k_dets"],
                                          B.mobile_budget()["sims_per_det"])


def test_a_resume_that_cannot_get_the_played_engine_says_so():
    """The pin is DROPPED when the backend resolves differently — carrying a
    rust-priced budget onto the Python engine is the ~25 s/move hang, not fidelity —
    and the game says which halves were played against what."""
    save = _tiny_rust_save()
    save["sims"] = save["k_dets"] = None
    save["sims_effective"], save["k_dets_effective"] = 1376, 8

    monkey = pytest.MonkeyPatch()
    _no_carc_rs(monkey)
    try:
        out = _j(B.restore_game(json.dumps(save)))
    finally:
        monkey.undo()
    s = B._S
    assert s.backend == "python" and s.played_backend == "rust"
    assert (s.eff_k_dets, s.eff_sims) == (
        B.ANDROID_FALLBACK_BUDGET["k_dets"],
        B.ANDROID_FALLBACK_BUDGET["sims_per_det"])
    assert "RESUMED ON A DIFFERENT ENGINE" in (s.resume_note or "")
    assert out["resume_note"] == s.resume_note


def test_the_archive_stamps_both_sides_of_a_resume():
    """`measurement/e4_games/README.md` grades E4 games off exactly these fields, so
    "played at 11008, resumed at 2752" must be visible in the record rather than
    collapsed into the post-restore answer."""
    save = _tiny_rust_save()
    save["sims"] = save["k_dets"] = None
    save["sims_effective"], save["k_dets_effective"] = 1376, 8
    monkey = pytest.MonkeyPatch()
    _no_carc_rs(monkey)
    try:
        _j(B.restore_game(json.dumps(save)))
        B._S.board.state.is_terminated = lambda: True     # archive wants a result
        rec = _j(B.archive_record())
    finally:
        monkey.undo()
    assert rec["backend"] == "python"
    assert (rec["k_dets_effective"], rec["sims_effective"]) == (
        B.ANDROID_FALLBACK_BUDGET["k_dets"],
        B.ANDROID_FALLBACK_BUDGET["sims_per_det"])
    assert rec["played_backend"] == "rust"
    assert (rec["played_k_dets_effective"], rec["played_sims_effective"]) == (8, 1376)
    assert "RESUMED ON A DIFFERENT ENGINE" in (rec["resume_note"] or "")


def test_undo_keeps_the_session_resolution():
    """`undo_last_tile` rebuilds through `restore_game`, so the sticky fields must
    round-trip rather than re-resolving mid-game."""
    st = _j(B.new_game(json.dumps({"seed": 3, "opponent": "champion",
                                   "human_player": 0, "backend": "rust",
                                   "sims": 8, "k_dets": 2, "verify": False})))
    if st["backend"] != "rust":
        pytest.skip(f"no rust backend here: {st['backend_note']}")
    steps = 0
    while st["phase"] != "meeples" and not st["is_terminated"] and steps < 20:
        st = _j(B.apply_action(st["legal"]["action_ids"][0])
                if st["is_human_turn"] else B.ai_move())
        steps += 1
    if st["phase"] != "meeples" or not st["is_human_turn"]:
        pytest.skip("did not reach a human meeple decision in 20 plies")
    _j(B.undo_last_tile())
    s = B._S
    assert s.backend == "rust" and s.rs is not None
    assert (s.eff_k_dets, s.eff_sims) == (2, 8)
    assert s.resume_note is None


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


# --------------------------------------------------------------------------- #
# 3b. the mirror under the rest of the fixed_v1 bundle (2026-08-03)             #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("cloister_rule", ["fixed", "drifting"])
@pytest.mark.parametrize("draw_rule", ["redraw", "engine"])
def test_the_mirror_plays_the_same_a2_and_a3_rules(cloister_rule, draw_rule):
    """A2 and A3 have no signature on ply one, which is what makes them worth a
    full-game check rather than a constructor assertion.

    A mirror left on the OTHER cloister scan scores a cloister on a different ply
    and hands its meeple back on a different ply; one left on the other draw rule
    diverges the first time a tile cannot be placed, because a different player
    owes the next decision and a different tile is drawn. Both show up as a repr
    divergence, and `_assert_mirror` runs inside `apply()` under
    CARC_RS_RECONCILE — so a full clean game IS the assertion.
    """
    import random

    monkey = pytest.MonkeyPatch()
    monkey.setattr(B, "_RS_RECONCILE", True)
    try:
        st = _j(B.new_game(json.dumps({
            "seed": 17, "opponent": "tier1", "backend": "rust",
            "cloister_rule": cloister_rule, "draw_rule": draw_rule,
        })))
        assert st["backend"] == "rust", st["backend_note"]
        s = B._S
        assert s.rs is not None, s.rs_note
        assert s.game.cloister_scan_fix is (cloister_rule == "fixed")
        assert s.game.redraw_unplaceable is (draw_rule == "redraw")
        assert s.game.string_representation(s.board) == s.rs.string_repr()

        rng = random.Random(99)
        plies = 0
        while not st["is_terminated"]:
            plies += 1
            assert plies <= 400, "game did not terminate"
            st = _j(B.apply_action(rng.choice(st["legal"]["action_ids"])))
        assert plies > 100, f"probe degenerate: only {plies} plies"
        assert s.game.string_representation(s.board) == s.rs.string_repr()
        assert list(s.rs.scores()) == list(st["scores"])
    finally:
        monkey.undo()


def test_the_mirror_is_on_the_same_farm_data_as_the_python_engine():
    """The fifth lever, which no `Game` and no `FairAgentRs` argument can carry.

    Both engines read `CARCASSONNE_FIX_R9` — the Python one when `base_deck` was
    imported, the Rust one into a `OnceLock` the first time its registry is asked
    for — so agreement is an ORDERING property, not a wiring one. `carc_rs` is the
    only place the Rust half of it can be read back."""
    from wingedsheep.carcassonne.tile_sets import base_deck

    py = B.FARM_RULE_R9 if base_deck.R9_FIELD_ON_CITY_EDGE_FIX else B.FARM_RULE_ENGINE
    rs = B.FARM_RULE_R9 if carc_rs.r9_enabled() else B.FARM_RULE_ENGINE
    assert py == rs == B.FARM_RULE_LATCHED, (
        f"python={py} rust={rs} bridge={B.FARM_RULE_LATCHED} — the two engines "
        "would decompose farms differently")


def test_a_rust_registry_on_the_other_farm_rule_degrades_instead_of_diverging():
    """The safety net for the one process where the ordering CAN fail (an
    instrumented-test process, where another test class may build a Rust game
    before this module is imported). Simulated by lying about the latch."""
    monkey = pytest.MonkeyPatch()
    other = (B.FARM_RULE_ENGINE if B.FARM_RULE_LATCHED == B.FARM_RULE_R9
             else B.FARM_RULE_R9)
    monkey.setattr(carc_rs, "r9_enabled", lambda: other == B.FARM_RULE_R9)
    try:
        st = _j(B.new_game(json.dumps({
            "seed": 3, "opponent": "tier1", "backend": "rust",
        })))
        assert st["ok"] is True, st
        assert st["backend"] == "python", "a farm-rule split must not stay on rust"
        assert B._S.rs is None
        note = st["backend_note"] or B._S.rs_note or ""
        assert "farm_rule" in note and B.R9_ENV_VAR in note, note
    finally:
        monkey.undo()


# --------------------------------------------------------------------------- #
# 4. the two safety nets (REVIEW.md C-a / C-i, CONFIRMED 2026-08-02)            #
# --------------------------------------------------------------------------- #
def _panic_type() -> type:
    """The real ``pyo3_runtime.PanicException`` class, obtained by causing one.

    Imported by provocation rather than by name: `pyo3_runtime` is created by the
    extension, so it is not importable until a panic has been raised through it."""
    try:
        carc_rs.MirrorState.from_seed("abc")
    except BaseException as exc:                  # noqa: BLE001 — that IS the point
        return type(exc)
    raise AssertionError("carc_rs no longer panics on a non-decimal seed")


def test_a_rust_panic_is_not_an_exception():
    """The premise of C-a, asserted rather than assumed: `except Exception` cannot
    see a Rust panic, so every JNI entry point had to move to `BaseException`."""
    panic = _panic_type()
    assert issubclass(panic, BaseException)
    assert not issubclass(panic, Exception)


def test_a_panic_at_a_jni_entry_point_returns_json_not_a_crash(monkeypatch):
    """A panic must come back as the ordinary error envelope. Before the fix it
    crossed into Kotlin as an unhandled Python exception."""
    panic = _panic_type()
    _j(B.new_game(json.dumps({"seed": 5, "opponent": "tier1", "backend": "python"})))

    def boom(_s):
        raise panic("simulated rust panic")

    monkeypatch.setattr(B, "_state_dict", boom)
    d = json.loads(B.get_state())
    assert d["ok"] is False
    assert d["error"]["code"] == panic.__name__
    assert "simulated rust panic" in d["error"]["message"]


def test_interpreter_control_flow_is_still_allowed_through():
    """`BaseException` must not mean "swallow everything": a KeyboardInterrupt is not
    a bridge result, and eating it would make a test run uninterruptible."""
    for exc in (KeyboardInterrupt(), SystemExit(1)):
        with pytest.raises(type(exc)):
            B._jni_err(exc)


def test_the_chooser_hard_asserts_the_mirror_every_decision():
    """C-i, half one. The phone's chooser used to be
    `lambda board: int(self.rs.choose_action())` — it discarded its board argument,
    so a stale mirror went on answering with moves computed for a position the game
    had left. Desyncing the mirror by one ply must now be REFUSED, not played."""
    cfg = {"seed": 31, "opponent": "champion", "human_player": 1,
           "backend": "rust", "sims": 8, "k_dets": 1, "verify": False}
    st = _j(B.new_game(json.dumps(cfg)))
    if st["backend"] != "rust":
        pytest.skip(f"no rust backend here: {st['backend_note']}")
    assert not st["is_human_turn"], "seat 0 must be the AI for this probe"
    # Control: the guard does not fire on a healthy mirror.
    st = _j(B.ai_move())

    # Push the mirror one ply ahead of the engine, exactly as a missed `advance`
    # (or a failed one) would leave it.
    B._S.rs.advance(int(st["legal"]["action_ids"][0]))
    d = json.loads(B.ai_move() if not st["is_human_turn"]
                   else B.apply_action(st["legal"]["action_ids"][0]))
    if d.get("ok"):
        # It was the human's turn, so the desync is caught on the next AI decision.
        d = json.loads(B.ai_move())
    assert d["ok"] is False, "a desynced mirror was allowed to pick a move"
    assert "diverged" in d["error"]["message"]


class _BoomMirror:
    """A mirror whose `advance` fails the way a Rust panic would."""

    def __init__(self, real, exc_type):
        self._real, self._exc = real, exc_type

    def advance(self, _a):
        raise self._exc("simulated mirror failure")

    def __getattr__(self, name):
        return getattr(self._real, name)


def test_apply_is_failure_atomic_and_degrades_rather_than_going_stale():
    """C-i, half two. `apply()` used to mutate board/action_log/turn and THEN call
    `rs.advance`, so an FFI failure left Python one ply ahead of a mirror that stayed
    seated as the chooser — permanently stale, and undetected because the per-ply
    reconcile is off on the phone."""
    st = _j(B.new_game(json.dumps({"seed": 9, "opponent": "champion",
                                   "human_player": 0, "backend": "rust",
                                   "sims": 8, "k_dets": 1, "verify": False})))
    if st["backend"] != "rust":
        pytest.skip(f"no rust backend here: {st['backend_note']}")
    s = B._S
    before_actions = list(s.action_log)
    before_turn = s.turn
    s.rs = _BoomMirror(s.rs, _panic_type())

    action = int(st["legal"]["action_ids"][0])
    out = _j(B.apply_action(action))

    # The action landed EXACTLY ONCE on the Python side...
    assert s.action_log == before_actions + [action]
    assert s.turn == before_turn + 1
    assert out["n_actions"] == len(s.action_log)
    # ...the mirror is gone rather than stale, and says why...
    assert s.rs is None
    assert s.backend == B.BACKEND_PYTHON
    assert "rust mirror failed" in (s.rs_note or "")
    # ...and the budget came down with the engine, or the phone inherits a
    # ~25 s/move champion on the slow path.
    assert (s.eff_k_dets, s.eff_sims) == (1, 8), "an explicit request stays honoured"
    assert B._agent_ref is s.agent, "get_progress would read a dead agent"
    # The game is still playable.
    assert _j(B.get_state())["n_actions"] == len(s.action_log)


def test_a_mid_game_degrade_drops_to_the_floor_budget():
    """Same path, with no explicit sims request: the budget must land on the floor
    rather than keep a rust-priced 11008 on the Python engine."""
    st = _j(B.new_game(json.dumps({"seed": 9, "opponent": "champion",
                                   "human_player": 0, "backend": "rust",
                                   "verify": False})))
    if st["backend"] != "rust":
        pytest.skip(f"no rust backend here: {st['backend_note']}")
    s = B._S
    s.rs = _BoomMirror(s.rs, RuntimeError)
    _j(B.apply_action(int(st["legal"]["action_ids"][0])))
    assert s.rs is None and s.backend == B.BACKEND_PYTHON
    assert (s.eff_k_dets, s.eff_sims) == (
        B.ANDROID_FALLBACK_BUDGET["k_dets"], B.ANDROID_FALLBACK_BUDGET["sims_per_det"])


def test_an_odd_grid_row_cannot_reach_the_mirror():
    """The EVEN-shift refusal is enforced on BOTH sides, and the bridge never
    gets to construct a half-configured mirror: `_Session` rejects the unknown
    rule name before any engine is built."""
    d = json.loads(B.new_game(json.dumps({"seed": 5, "backend": "rust",
                                          "grid_rule": "centered17"})))
    assert not d["ok"] and d["error"]["code"] == "ValueError"
    assert B._S is None or B._S.grid_rule in B.GRID_RULE_START
