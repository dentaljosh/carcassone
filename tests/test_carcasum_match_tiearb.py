"""THE TIE ARBITER, reachable from the Carcasum out-of-lineage match driver.

Ported from `tests/test_jcz_match_tiearb.py` — the sibling out-of-lineage-match
harness that already had this plumbing (`scripts/jcz_match/match.py`).
`scripts/carcasum_match/match.py` had NO way to arm the tie-arbiter before the
`measurement/carcasum_arb_challenge_prep/` build ported the same
`_resolve_tiearb`/`_champ_tiearb_telemetry` pattern in, field-for-field, with the same
`--champ-tiearb-*` flag names.

Same three properties this test file guards, same reasons as the jcz_match precedent:

* **ARM-OFF is untouched.** An unarmed champion's config, manifest, and per-game
  record are byte-identical to before this plumbing existed — `carcasum_match_r1`'s
  and rung-2's own archives must remain readable against an unmodified schema.
* **ARM-ON cannot be a silent null.** The arbiter is rust-only and fair-only; an
  unsatisfiable request RAISES instead of dropping the surface — the J13 failure mode
  (`champion_factory.py`'s own docstring), and the exact reason
  `READ_RULE.md`'s `G-CHAMP-ON` gate exists on the analyzer side.
* **The wiring gate is stamped.** The arbiter moves NO leaf hash, so the only
  config-side witness is the resolved `cand_tiearb` dict on the manifest.

Cheap by construction: nothing here plays a game or runs a search.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]
MATCH_DIR = REPO / "scripts" / "carcasum_match"
for _p in (str(REPO / "src"), str(MATCH_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from carcassonne_ai import champion_factory as CF  # noqa: E402

#: The production knob set (governance/PRODUCTION.yaml fair_deploy.tiearb): B=64,
#: J=4, argmax, salt tiearb2-deploy-v1, eps 0.0. This is ARM-ON's own config, not
#: the CLI flags' defaults (which stay B=16 — explicit arming required, same
#: discipline `play_harness.py`'s own comment states).
#:
#: ⭐ `phase_gate` joined the shape with measurement/phasegate_prep: the rust
#: `search_config.tiearb` getter emits it unconditionally, so `_resolve_tiearb`,
#: the factory's `cand_tiearb` stamp and `_worker_init`'s exact-dict probe all
#: carry it. `"all"` is the ungated arbiter == every pre-gate armed cell.
ARMED = {"enabled": True, "B": 64, "J": 4, "mode": "argmax",
         "phase_gate": "all", "salt": "tiearb2-deploy-v1", "eps": 0.0}
DISARMED = dict(ARMED, enabled=False)


# --------------------------------------------------------------------------- #
# 1-2. production_prior_cfg (shared factory layer, already tested by            #
#      test_jcz_match_tiearb.py — re-asserted here only for the B=64 shape      #
#      this cell actually uses, since jcz_match's own fixture uses B=16)        #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("tiearb", [None, DISARMED], ids=["none", "enabled-false"])
def test_unarmed_prior_cfg_is_the_champion_byte_for_byte(tiearb):
    base = CF.production_prior_cfg()
    got = CF.production_prior_cfg(tiearb=tiearb)

    assert base.tiearb_enabled is False
    assert got.tiearb_enabled is False
    assert got == base
    assert got.as_manifest() == base.as_manifest()
    assert CF._config_hash(got.as_manifest()) == CF._config_hash(base.as_manifest())


def test_armed_prior_cfg_at_b64_sets_all_six_fields():
    cfg = CF.production_prior_cfg(tiearb=ARMED)

    assert cfg.tiearb_enabled is True
    assert cfg.tiearb_b == 64
    assert cfg.tiearb_j == 4
    assert cfg.tiearb_mode == "argmax"
    assert cfg.tiearb_salt == "tiearb2-deploy-v1"
    assert cfg.tiearb_eps == 0.0
    assert (CF._config_hash(cfg.as_manifest())
            != CF._config_hash(CF.production_prior_cfg().as_manifest()))


# --------------------------------------------------------------------------- #
# 3-4. make_production_champion (leaf hash does NOT move; ARM-OFF's manifest    #
#      gains no key)                                                           #
# --------------------------------------------------------------------------- #
def test_armed_champion_refuses_the_python_backend():
    with pytest.raises(ValueError, match="RUST-ONLY"):
        CF.make_production_champion("fair", verify=False, backend="python",
                                    tiearb=ARMED)


def test_armed_champion_refuses_clairvoyant_mode():
    with pytest.raises(ValueError, match="FAIR-mode"):
        CF.make_production_champion("clairvoyant", verify=False, backend="python",
                                    tiearb=ARMED)


@pytest.mark.parametrize("tiearb", [None, DISARMED], ids=["none", "enabled-false"])
def test_unarmed_champion_manifest_has_no_cand_tiearb_key(tiearb):
    """CELL/ARM-OFF's manifest is the pre-kwarg one — the schema r1 and rung-2 already
    committed to must not move under a build that never touches their archives."""
    from carcassonne_ai.game_wrapper import Game

    def _man(**kw):
        agent = CF.make_production_champion(
            "fair", game=Game(enable_legal_moves_cache=True), sims=1, k_dets=1,
            verify=False, backend="python", **kw)
        return agent.manifest

    man = _man(tiearb=tiearb)
    assert "cand_tiearb" not in man
    assert man == _man()          # byte-identical to never naming the kwarg at all


def test_armed_champion_stamps_cand_tiearb_at_the_deployed_shape():
    """The wiring gate `READ_RULE.md`'s `G-CHAMP-ON` reads: the resolved dict must be
    the exact deployed shape, not merely present."""
    pytest.importorskip("carc_rs")
    from carcassonne_ai.game_wrapper import Game

    agent = CF.make_production_champion(
        "fair", game=Game(enable_legal_moves_cache=True), sims=1, k_dets=1,
        verify=False, backend="rust", tiearb=ARMED)

    assert agent.manifest["cand_tiearb"] == ARMED
    # the leaf hash does NOT move (a search knob, not a leaf field)
    unarmed = CF.make_production_champion(
        "fair", game=Game(enable_legal_moves_cache=True), sims=1, k_dets=1,
        verify=False, backend="rust")
    assert (agent.manifest.get("leaf_hashes") == unarmed.manifest.get("leaf_hashes"))
    # …and the agent that will PLAY carries it too, not just the paperwork
    assert bool(agent._rs.stats()["tiearb_enabled"]) is True


# --------------------------------------------------------------------------- #
# 5. carcasum_match/match.py's own resolution + telemetry                      #
# --------------------------------------------------------------------------- #
def _args(**kw):
    """The argparse defaults, overridable — mirrors carcasum_match/match.py's
    `main()` parser exactly (§8 of DESIGN.md)."""
    d = dict(champ_tiearb_enabled=False, champ_tiearb_b=16, champ_tiearb_j=4,
             champ_tiearb_mode="argmax", champ_tiearb_salt="tiearb2-deploy-v1",
             champ_tiearb_eps=0.0)
    d.update(kw)
    return SimpleNamespace(**d)


def test_resolve_tiearb_unarmed_is_None_not_a_disabled_dict():
    """None, so nothing reaches the factory and the record gains no key — ARM-OFF's
    archive stays byte-identical to r1's/rung-2's own schema."""
    import match as M

    assert M._resolve_tiearb(_args()) is None


def test_resolve_tiearb_armed_carries_every_knob_including_the_deployed_b64():
    import match as M

    assert M._resolve_tiearb(_args(champ_tiearb_enabled=True, champ_tiearb_b=64)) \
        == ARMED
    assert M._resolve_tiearb(_args(champ_tiearb_enabled=True, champ_tiearb_b=8,
                                   champ_tiearb_j=2, champ_tiearb_mode="random",
                                   champ_tiearb_salt="probe", champ_tiearb_eps=1e-9)) \
        == {"enabled": True, "B": 8, "J": 2, "mode": "random",
            "phase_gate": "all", "salt": "probe", "eps": 1e-9}


def test_telemetry_is_None_when_unarmed_and_FAILS_LOUD_when_armed():
    """The J13 rule, in code: an armed game whose champion is not a rust-backed agent,
    or whose agent reports the knob off, RAISES rather than stamping a quiet None."""
    import match as M

    class _NoRs:
        pass

    class _Rs:
        def __init__(self, on):
            self._on = on

        def stats(self):
            return {"tiearb_enabled": self._on, "tiearb_tile_plies": 40,
                    "tiearb_fired_plies": 23, "tiearb_pickchanges": 5,
                    "tiearb_arms_total": 60, "tiearb_playouts_total": 960,
                    "tiearb_secs": 1.5, "tiearb_errors": 0,
                    "tiearb_first_error": None, "tiearb_partial_argmax": 0,
                    "tiearb_max_plies": 0, "tiearb_mode": "argmax",
                    "tiearb_b": 64, "tiearb_j": 4}

    class _Agent:
        def __init__(self, rs):
            self._rs = rs

    assert M._champ_tiearb_telemetry(_NoRs(), None) is None
    assert M._champ_tiearb_telemetry(_NoRs(), DISARMED) is None
    with pytest.raises(RuntimeError, match="no FairAgentRs"):
        M._champ_tiearb_telemetry(_NoRs(), ARMED)
    with pytest.raises(RuntimeError, match="tiearb_enabled=False"):
        M._champ_tiearb_telemetry(_Agent(_Rs(False)), ARMED)

    t = M._champ_tiearb_telemetry(_Agent(_Rs(True)), ARMED)
    assert t["fires"] == t["fired_plies"] == 23
    assert t["tile_plies"] == 40 and t["pickchanges"] == 5
    assert t["mode"] == "argmax" and t["B"] == 64 and t["J"] == 4
    assert set(t) == {"tile_plies", "fires", "fired_plies", "pickchanges",
                      "arms_total", "playouts_total", "secs", "errors",
                      "first_error", "partial_argmax", "max_plies", "mode", "B", "J"}


def test_the_cli_exposes_the_champ_tiearb_flags():
    """The flags exist on the real parser (--help exits before any engine import)."""
    out = subprocess.run([sys.executable, str(MATCH_DIR / "match.py"), "--help"],
                         capture_output=True, text=True, timeout=120,
                         cwd=str(REPO), env=dict(os.environ))
    assert out.returncode == 0, out.stderr
    for flag in ("--champ-tiearb-enabled", "--champ-tiearb-b", "--champ-tiearb-j",
                 "--champ-tiearb-mode", "--champ-tiearb-salt", "--champ-tiearb-eps"):
        assert flag in out.stdout, f"{flag} missing from --help"
