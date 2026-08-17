"""THE TIE ARBITER, reachable from the JCloisterZone match driver.

Until this wiring the arbiter existed only behind ``eval_fair_puct``'s
``--cand-tiearb-*`` flags, which build their own ``HeuristicPriorConfig``. Every
out-of-lineage harness reaches the champion through
``champion_factory.make_production_champion`` instead, so the two-cell design
(CELL A = plain champion vs JCZ, CELL B = champion+arbiter vs JCZ) was simply
unreachable. These tests guard the three things that make that cell readable:

* **CELL A is untouched.** An unarmed champion's config, its manifest, and the
  match driver's per-game record are byte-identical to the pre-kwarg ones. A
  control that moved is not a control, and ``search.config_hash`` is computed
  from the config, so a stray default would silently re-key every existing
  manifest.
* **CELL B cannot be a silent null.** The arbiter is rust-only and fair-only, so
  an unsatisfiable request RAISES instead of dropping the surface. A silently
  arbiter-free "candidate" plays champion-vs-champion and grades a perfect null
  wearing the shape of a real cell — the J13 failure mode this surface exists to
  refuse. The same rule governs the per-game telemetry read.
* **The wiring gate is stamped.** The arbiter deliberately moves NO leaf hash, so
  the only config-side witness is the resolved ``cand_tiearb`` dict on the
  manifest, in the key and shape READ_RULE `G-J4` already reads.

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
MATCH_DIR = REPO / "scripts" / "jcz_match"
for _p in (str(REPO / "src"), str(MATCH_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from carcassonne_ai import champion_factory as CF  # noqa: E402

#: The committed knob set (DESIGN §2): B=16, J=4, exact f64 equality, the salt of
#: record. READ_RULE `G-J4` voids a run at any other B/J.
ARMED = {"enabled": True, "B": 16, "J": 4, "mode": "argmax",
         "salt": "tiearb2-deploy-v1", "eps": 0.0}
DISARMED = dict(ARMED, enabled=False)


# --------------------------------------------------------------------------- #
# 1-2. production_prior_cfg                                                    #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("tiearb", [None, DISARMED], ids=["none", "enabled-false"])
def test_unarmed_prior_cfg_is_the_champion_byte_for_byte(tiearb):
    """`None` and an `enabled=False` dict must both pass NO keyword to the config.

    Compared through ``as_manifest()`` and ``_config_hash`` rather than field-by-field
    on purpose: the hash is what lands in every manifest, so THAT is the thing whose
    stability is being claimed.
    """
    base = CF.production_prior_cfg()
    got = CF.production_prior_cfg(tiearb=tiearb)

    assert base.tiearb_enabled is False
    assert got.tiearb_enabled is False
    assert got == base
    assert got.as_manifest() == base.as_manifest()
    assert CF._config_hash(got.as_manifest()) == CF._config_hash(base.as_manifest())


def test_armed_prior_cfg_sets_all_six_fields():
    cfg = CF.production_prior_cfg(tiearb=ARMED)

    assert cfg.tiearb_enabled is True
    assert cfg.tiearb_b == 16
    assert cfg.tiearb_j == 4
    assert cfg.tiearb_mode == "argmax"
    assert cfg.tiearb_salt == "tiearb2-deploy-v1"
    assert cfg.tiearb_eps == 0.0
    # …and the arming is VISIBLE in the resolved config, i.e. the hash moves. The leaf
    # hash deliberately does not, so this is the only config-side difference there is.
    assert (CF._config_hash(cfg.as_manifest())
            != CF._config_hash(CF.production_prior_cfg().as_manifest()))


def test_armed_prior_cfg_validates_its_knobs():
    """__post_init__ owns the validation; the factory just has to not swallow it."""
    with pytest.raises(ValueError, match="tiearb_mode"):
        CF.production_prior_cfg(tiearb=dict(ARMED, mode="coinflip"))
    with pytest.raises(ValueError, match="tiearb_j"):
        CF.production_prior_cfg(tiearb=dict(ARMED, J=0))


# --------------------------------------------------------------------------- #
# 3-4. make_production_champion                                                #
# --------------------------------------------------------------------------- #
def test_armed_champion_refuses_the_python_backend():
    """RUST-ONLY, and it RAISES — the python search path has no arbiter at all, so a
    silently arbiter-free champion would grade a null wearing the shape of a cell."""
    with pytest.raises(ValueError, match="RUST-ONLY"):
        CF.make_production_champion("fair", verify=False, backend="python",
                                    tiearb=ARMED)


def test_armed_champion_refuses_clairvoyant_mode():
    """FAIR-ONLY (the arbiter binds at the PIMC root), reported as a MODE error — the
    documented kwarg-before-backend order, so a mode fault is never blamed on rust."""
    with pytest.raises(ValueError, match="FAIR-mode"):
        CF.make_production_champion("clairvoyant", verify=False, backend="python",
                                    tiearb=ARMED)


@pytest.mark.parametrize("tiearb", [None, DISARMED], ids=["none", "enabled-false"])
def test_unarmed_champion_manifest_has_no_cand_tiearb_key(tiearb):
    """No key, no hash drift, no re-review — CELL A's manifest is the pre-kwarg one."""
    from carcassonne_ai.game_wrapper import Game

    def _man(**kw):
        agent = CF.make_production_champion(
            "fair", game=Game(enable_legal_moves_cache=True), sims=1, k_dets=1,
            verify=False, backend="python", **kw)
        return agent.manifest

    man = _man(tiearb=tiearb)
    assert "cand_tiearb" not in man
    assert man == _man()          # byte-identical to never naming the kwarg at all


def test_armed_champion_stamps_cand_tiearb_in_the_G_J4_shape():
    """The wiring gate. The KEY and the SHAPE are eval_fair_puct's, deliberately: a
    gate that has to learn a second spelling eventually reads the wrong cell."""
    pytest.importorskip("carc_rs")
    from carcassonne_ai.game_wrapper import Game

    agent = CF.make_production_champion(
        "fair", game=Game(enable_legal_moves_cache=True), sims=1, k_dets=1,
        verify=False, backend="rust", tiearb=ARMED)

    assert agent.manifest["cand_tiearb"] == ARMED
    # the agent that will PLAY carries it too (not just the paperwork)
    assert bool(agent._rs.stats()["tiearb_enabled"]) is True


# --------------------------------------------------------------------------- #
# 5. the match driver's own resolution + telemetry                             #
# --------------------------------------------------------------------------- #
def _args(**kw):
    """The argparse defaults, overridable — mirrors `main()`'s parser exactly."""
    d = dict(champ_tiearb_enabled=False, champ_tiearb_b=16, champ_tiearb_j=4,
             champ_tiearb_mode="argmax", champ_tiearb_salt="tiearb2-deploy-v1",
             champ_tiearb_eps=0.0)
    d.update(kw)
    return SimpleNamespace(**d)


def test_resolve_tiearb_unarmed_is_None_not_a_disabled_dict():
    """None, so nothing reaches the factory and the record gains no key. An
    `enabled=False` dict here would still be falsy downstream, but it would also be a
    silent invitation to stamp `champ_tiearb: null` and change the frozen schema."""
    import match as M

    assert M._resolve_tiearb(_args()) is None


def test_resolve_tiearb_armed_carries_every_knob():
    import match as M

    assert M._resolve_tiearb(_args(champ_tiearb_enabled=True)) == ARMED
    assert M._resolve_tiearb(_args(champ_tiearb_enabled=True, champ_tiearb_b=8,
                                   champ_tiearb_j=2, champ_tiearb_mode="random",
                                   champ_tiearb_salt="probe", champ_tiearb_eps=1e-9)) \
        == {"enabled": True, "B": 8, "J": 2, "mode": "random", "salt": "probe",
            "eps": 1e-9}


def test_telemetry_is_None_when_unarmed_and_FAILS_LOUD_when_armed():
    """The J13 rule, in code: an armed game whose champion is not a RustFairAgent, or
    whose agent reports the knob off, RAISES rather than stamping a quiet None."""
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
                    "tiearb_b": 16, "tiearb_j": 4}

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
    # `fires` and `fired_plies` are the SAME number under two names on purpose: the
    # adjudicator reads one fail-closed, the summary blocks aggregate the other.
    assert t["fires"] == t["fired_plies"] == 23
    assert t["tile_plies"] == 40 and t["pickchanges"] == 5
    assert t["mode"] == "argmax" and t["B"] == 16 and t["J"] == 4
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


# --------------------------------------------------------------------------- #
# 6. the analyzer's firing ledger                                              #
# --------------------------------------------------------------------------- #
def test_analyze_emits_nothing_for_a_legacy_archive():
    import analyze as AZ

    legacy = [{"void": None, "winner": "champ", "deck_seed": 1, "champ_seat": 0,
               "margin_champ_minus_jcz": 4}]
    assert AZ.tiearb_block(legacy) is None
    assert "tiearb" not in AZ.analyze(legacy)


def test_analyze_tiearb_block_counts_voids_and_discounts_errors():
    """phi counts EVERY game the arbiter ran in, voids included (the surface ran
    there too, and dropping those flatters phi); phi_effective discounts the
    fail-soft plies that fell back to the champion's own pick."""
    import analyze as AZ

    def _g(fired, tile, errs=0, void=None):
        return {"void": void, "winner": "champ", "deck_seed": 1, "champ_seat": 0,
                "margin_champ_minus_jcz": 1,
                "champ_tiearb": {"tile_plies": tile, "fires": fired,
                                 "fired_plies": fired, "pickchanges": 3,
                                 "arms_total": 2 * fired, "playouts_total": 32 * fired,
                                 "secs": 2.0, "errors": errs, "first_error": None,
                                 "partial_argmax": 0, "max_plies": 0,
                                 "mode": "argmax", "B": 16, "J": 4}}

    b = AZ.tiearb_block([_g(20, 40), _g(10, 40, errs=6, void="VOID_ERROR")])
    assert b["tiearb_games"] == 2                     # the voided game counts
    assert b["tiearb_fired_plies_total"] == 30
    assert b["tiearb_tile_plies_total"] == 80
    assert b["phi"] == 15.0
    assert b["error_rate_on_fired"] == pytest.approx(6 / 36)
    assert b["phi_effective"] == pytest.approx(15.0 * (1 - 6 / 36))
    assert b["G_FIRE_fired"] is False
    assert b["modes"] == ["argmax"] and b["B"] == [16] and b["J"] == [4]

    # …and an INERT surface is called out, not read as a null.
    dead = AZ.tiearb_block([_g(0, 40), _g(0, 40)])
    assert dead["phi"] == 0.0 and dead["G_FIRE_fired"] is True
