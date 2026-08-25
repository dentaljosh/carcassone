"""The mobile tie-arbiter (owner ruling 2026-08-2x: default B32 on phone, a
Settings screen to pick lower options, a progress indicator on long thinks).

Three layers, tested separately:

1. ``mobile_tiearb(level, spec)`` — pure config resolution off a
   ``ProductionSpec``, no session, no rust. Every fail-closed branch (unknown
   level, "off", no YAML block, a B this build does not offer) is exercised
   against synthetic specs so the real bundled YAML is not the only thing
   protecting the app from a malformed profile.
2. ``_Session``/``new_game`` — the resolved ``self.tiearb`` dict, the
   conditional kwargs actually reaching ``carc_rs.SearchConfigRs`` (the same
   monkeypatch-spy idiom ``test_bridge_backend.py`` uses for the libm flavour),
   and every fail-closed gate that depends on runtime state (backend degraded
   to python, tier1 opponent, an unknown level refused not defaulted).
3. The E4 archive manifest stamp — ``tiearb_enabled``/``tiearb_b``/
   ``tiearb_threads``/``tiearb_salt`` recorded AS RESOLVED, backward-compatible
   (absent == pre-arbiter build) on both a fresh save and a restore of one.

This module lives beside ``test_bridge_backend.py`` for the same reason that one
does: importing ``android_bridge`` here (not from ``tests/rustport``) keeps the
leaf-dispatch env knobs this process happens to be running under out of any
other suite's way (see that module's docstring)."""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "android" / "app" / "src" / "main" / "python"))

import android_bridge as B  # noqa: E402
from carcassonne_ai import champion_factory  # noqa: E402

carc_rs = pytest.importorskip("carc_rs", reason="the desktop dev wheel is not built")

TINY = {"sims": 8, "k_dets": 1, "verify": False}


def _j(s: str) -> dict:
    d = json.loads(s)
    assert d.get("ok"), d
    return d


@pytest.fixture(autouse=True)
def _reset():
    yield
    B.reset()


def _spec_with_mobile_tiearb(tiearb: dict | None, *, b_options=(32, 16, 8)) -> object:
    """A real ``ProductionSpec`` (from the bundled YAML) with its
    ``deploy_profiles.mobile.tiearb`` block replaced — everything ELSE (budget,
    backend, leaf) stays the real champion, so a test only exercises the ONE
    axis it names."""
    spec = champion_factory.load_production_spec()
    mobile = dict((spec.deploy_profiles or {}).get("mobile") or {})
    if tiearb is None:
        mobile.pop("tiearb", None)
    else:
        mobile = {**mobile, "tiearb": {**tiearb, "B_options": list(b_options)}}
    # ProductionSpec is a frozen dataclass — `dataclasses.replace`, not assignment.
    return dataclasses.replace(
        spec, deploy_profiles={**(spec.deploy_profiles or {}), "mobile": mobile})


# --------------------------------------------------------------------------- #
# 1. mobile_tiearb() — pure config resolution, no session                     #
# --------------------------------------------------------------------------- #
def test_default_level_is_b32():
    assert B.TIEARB_LEVEL_DEFAULT == B.TIEARB_LEVEL_B32


def test_b32_resolves_armed_from_the_bundled_yaml():
    r = B.mobile_tiearb(B.TIEARB_LEVEL_B32)
    assert r["enabled"] is True
    assert r["B"] == 32
    assert r["J"] == 4
    assert r["mode"] == "argmax"
    assert r["salt"] == "tiearb2-deploy-v1"
    assert r["eps"] == 0.0
    assert r["threads"] == 2
    assert r["from_yaml"] is True
    assert r["reason"] is None


@pytest.mark.parametrize("level,b", [(B.TIEARB_LEVEL_B16, 16), (B.TIEARB_LEVEL_B8, 8)])
def test_lower_levels_resolve_their_own_b_only(level, b):
    """Only B moves between levels; J/mode/salt/eps/threads are the same mobile
    profile fields regardless of which B the Settings screen picked."""
    b32 = B.mobile_tiearb(B.TIEARB_LEVEL_B32)
    r = B.mobile_tiearb(level)
    assert r["enabled"] is True
    assert r["B"] == b
    for k in ("J", "mode", "salt", "eps", "threads"):
        assert r[k] == b32[k], f"{k} must not vary with the level"


def test_off_is_disabled_and_never_touches_the_yaml():
    r = B.mobile_tiearb(B.TIEARB_LEVEL_OFF)
    assert r == {"enabled": False, "B": 0, "J": 0, "mode": "", "salt": "",
                "eps": 0.0, "threads": 0, "level": "off", "from_yaml": True,
                "reason": None}


def test_unknown_level_fails_closed_with_a_reason():
    r = B.mobile_tiearb("b64")
    assert r["enabled"] is False
    assert "b64" in r["reason"]
    assert r["from_yaml"] is False


def test_missing_mobile_tiearb_block_fails_closed():
    spec = _spec_with_mobile_tiearb(None)
    r = B.mobile_tiearb(B.TIEARB_LEVEL_B32, spec)
    assert r["enabled"] is False
    assert "no mobile tiearb profile" in r["reason"]


def test_a_disabled_yaml_block_fails_closed_even_for_a_named_level():
    spec = _spec_with_mobile_tiearb({"enabled": False, "J": 4, "mode": "argmax",
                                     "salt": "s", "eps": 0.0, "threads": 2})
    r = B.mobile_tiearb(B.TIEARB_LEVEL_B32, spec)
    assert r["enabled"] is False


def test_a_level_this_builds_b_options_does_not_offer_fails_closed():
    """The app requests b32 but a stale bundled YAML only ever measured b16/b8 —
    never invent a B nobody signed off on."""
    spec = _spec_with_mobile_tiearb(
        {"enabled": True, "J": 4, "mode": "argmax", "salt": "s", "eps": 0.0,
         "threads": 2}, b_options=(16, 8))
    r = B.mobile_tiearb(B.TIEARB_LEVEL_B32, spec)
    assert r["enabled"] is False
    assert "B_options" in r["reason"]
    # b16 is still fine against the SAME spec.
    assert B.mobile_tiearb(B.TIEARB_LEVEL_B16, spec)["enabled"] is True


def test_mobile_tiearb_never_raises():
    for level in (None, "", 32, "b32 ", "OFF"):
        r = B.mobile_tiearb(level)  # type: ignore[arg-type]
        assert r["enabled"] is False


# --------------------------------------------------------------------------- #
# 2. _Session / new_game — resolution against a live (or degraded) backend    #
# --------------------------------------------------------------------------- #
def test_new_game_defaults_to_b32_armed_on_rust():
    st = _j(B.new_game(json.dumps({"seed": 5, "opponent": "champion",
                                   "backend": "rust", **TINY})))
    assert st["backend"] == "rust", st["backend_note"]
    s = B._S
    assert s.tiearb_level == "b32"
    assert s.tiearb["enabled"] is True
    assert s.tiearb["B"] == 32
    assert s.tiearb["threads"] == 2
    assert s.tiearb["salt"] == "tiearb2-deploy-v1"
    # "cannot silently no-op": the live rust telemetry must agree.
    live = s.rs.stats()
    assert live["tiearb_enabled"] is True
    assert live["tiearb_b"] == 32
    assert live["tiearb_threads"] == 2


@pytest.mark.parametrize("level,b", [("b32", 32), ("b16", 16), ("b8", 8)])
def test_each_settings_value_resolves_and_goes_live(level, b):
    st = _j(B.new_game(json.dumps({
        "seed": 5, "opponent": "champion", "backend": "rust",
        "tiearb_level": level, **TINY})))
    s = B._S
    assert s.tiearb["enabled"] is True
    assert s.tiearb["B"] == b
    assert s.rs.stats()["tiearb_b"] == b


def test_off_disables_the_arbiter_end_to_end():
    st = _j(B.new_game(json.dumps({
        "seed": 5, "opponent": "champion", "backend": "rust",
        "tiearb_level": "off", **TINY})))
    s = B._S
    assert s.tiearb["enabled"] is False
    assert s.rs.stats()["tiearb_enabled"] is False


def test_unknown_tiearb_level_is_refused_not_defaulted():
    d = json.loads(B.new_game(json.dumps({"seed": 5, "tiearb_level": "b64"})))
    assert d["ok"] is False
    assert "tiearb_level" in d["error"]["message"]


def test_tier1_opponent_never_arms_the_arbiter():
    """Tier-1 has no search at all; a Settings level of b32 must not somehow
    reach it — `_build_opponent`'s tier1 branch returns before tiearb is
    resolved, and the __init__ safe-default (disabled) must still hold."""
    st = _j(B.new_game(json.dumps({
        "seed": 5, "opponent": "tier1", "backend": "rust", "tiearb_level": "b32"})))
    assert B._S.tiearb["enabled"] is False


def test_explicit_python_backend_fails_the_arbiter_closed_not_loud():
    st = _j(B.new_game(json.dumps({
        "seed": 5, "opponent": "champion", "backend": "python",
        "tiearb_level": "b32", **TINY})))
    s = B._S
    assert s.backend == "python"
    assert s.tiearb["enabled"] is False
    assert "rust-only" in (s.tiearb["reason"] or "")


def test_rust_unavailable_also_fails_the_arbiter_closed(monkeypatch):
    """The same 'lose the speedup, never the game' contract the backend degrade
    already has — a missing wheel must not crash a b32-armed game, it must play
    it, unarbitrated, on Python."""
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) \
        else __builtins__.__import__

    def no_carc_rs(name, *a, **kw):
        if name == "carc_rs":
            raise ImportError("simulated: no wheel for this ABI")
        return real_import(name, *a, **kw)

    monkeypatch.setattr("builtins.__import__", no_carc_rs)
    st = _j(B.new_game(json.dumps({
        "seed": 7, "opponent": "champion", "backend": "rust",
        "tiearb_level": "b32", **TINY})))
    assert st["backend"] == "python"
    assert B._S.tiearb["enabled"] is False


def test_tiearb_kwargs_actually_reach_the_rust_search(monkeypatch):
    """Same spy idiom as test_bridge_backend.py's
    test_the_msun_flavour_actually_reaches_the_rust_search: a kwarg asserted
    only against `self.tiearb` could still be silently dropped before it
    reaches `carc_rs.SearchConfigRs`. Capture the real call."""
    captured = {}
    orig = carc_rs.SearchConfigRs

    def spy(*a, **kw):
        captured.update(kw)
        return orig(*a, **kw)

    monkeypatch.setattr(carc_rs, "SearchConfigRs", spy)
    _j(B.new_game(json.dumps({
        "seed": 5, "opponent": "champion", "backend": "rust",
        "tiearb_level": "b32", **TINY})))
    assert captured.get("tiearb_enabled") is True
    assert captured.get("tiearb_b") == 32
    assert captured.get("tiearb_j") == 4
    assert captured.get("tiearb_mode") == "argmax"
    assert captured.get("tiearb_salt") == "tiearb2-deploy-v1"
    assert captured.get("tiearb_eps") == 0.0
    assert captured.get("tiearb_threads") == 2


def test_off_never_passes_a_single_tiearb_kwarg():
    """Conditional-keyword, not conditional-value: an OLD carc_rs wheel that
    predates the arbiter kwarg surface entirely must still build this call when
    disarmed — the same discipline rust_agent.search_config_rs() follows."""
    captured = {}
    orig = carc_rs.SearchConfigRs

    def spy(*a, **kw):
        captured.update(kw)
        return orig(*a, **kw)

    import pytest as _pytest
    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(carc_rs, "SearchConfigRs", spy)
        _j(B.new_game(json.dumps({
            "seed": 5, "opponent": "champion", "backend": "rust",
            "tiearb_level": "off", **TINY})))
    assert not any(k.startswith("tiearb_") for k in captured)


# --------------------------------------------------------------------------- #
# 3. the E4 archive manifest stamp                                            #
# --------------------------------------------------------------------------- #
def _play_out(st: dict, max_plies: int = 400) -> dict:
    plies = 0
    while not st["is_terminated"]:
        plies += 1
        assert plies <= max_plies, "game did not terminate"
        if st["is_human_turn"]:
            st = _j(B.apply_action(st["legal"]["action_ids"][0]))
        else:
            st = _j(B.ai_move(st["generation"]))
    return st


def test_archive_stamps_tiearb_as_resolved_when_armed():
    st = _j(B.new_game(json.dumps({
        "seed": 9, "opponent": "champion", "backend": "rust",
        "tiearb_level": "b16", **TINY})))
    st = _play_out(st)
    rec = _j(B.archive_record())
    assert rec["tiearb_enabled"] is True
    assert rec["tiearb_b"] == 16
    assert rec["tiearb_threads"] == 2
    assert rec["tiearb_salt"] == "tiearb2-deploy-v1"
    # The Settings CHOICE also rides in the save core, one layer up.
    assert rec["tiearb_level"] == "b16"


def test_archive_stamps_tiearb_disabled_when_off():
    st = _j(B.new_game(json.dumps({
        "seed": 9, "opponent": "champion", "backend": "rust",
        "tiearb_level": "off", **TINY})))
    st = _play_out(st)
    rec = _j(B.archive_record())
    assert rec["tiearb_enabled"] is False
    assert rec["tiearb_b"] is None
    assert rec["tiearb_threads"] is None
    assert rec["tiearb_salt"] is None
    assert rec["tiearb_level"] == "off"


def test_a_save_with_no_tiearb_level_is_read_as_pre_arbiter_off():
    """Backward compatibility (mandatory, task requirement 4): a save/archive
    written before this feature shipped has no `tiearb_level` key at all, and
    that must resume as 'no arbiter', never a guess."""
    _j(B.new_game(json.dumps({"seed": 5, "opponent": "tier1"})))
    save = _j(B.save_game())
    assert "tiearb_level" in save        # every NEW save carries it
    save.pop("tiearb_level")             # simulate a pre-arbiter-build save
    _j(B.restore_game(json.dumps(save)))
    assert B._S.tiearb_level == B.TIEARB_LEVEL_OFF
    assert B._S.tiearb["enabled"] is False


def test_a_resumed_game_keeps_its_own_level_not_the_current_default():
    """Per-game invariant (like the five rule fields), not ambient Settings: a
    save written at b8 resumes at b8 even if the CURRENT default is b32."""
    st = _j(B.new_game(json.dumps({
        "seed": 5, "opponent": "champion", "backend": "rust",
        "tiearb_level": "b8", **TINY})))
    saved = _j(B.save_game())
    assert saved["tiearb_level"] == "b8"
    d = _j(B.restore_game(json.dumps(saved)))
    assert B._S.tiearb_level == "b8"
    assert B._S.tiearb["B"] == 8


def test_unknown_saved_tiearb_level_is_refused_not_guessed():
    _j(B.new_game(json.dumps({"seed": 5, "opponent": "tier1"})))
    save = _j(B.save_game())
    save["tiearb_level"] = "b64"
    d = json.loads(B.restore_game(json.dumps(save)))
    assert d["ok"] is False
