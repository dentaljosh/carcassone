"""THE OPPONENT-SIDE TIE ARBITER (`--opp-tiearb-*`, 2026-08-31 owner-funded
plumbing) — flags, construction, telemetry, manifest shape, and the new two-sided
gate vocabulary.

WHY THE PLUMBING EXISTS. `eval_fair_puct.py` could arm THE TIE ARBITER on the
CANDIDATE ONLY: `_make_opponent` took no `tiearb` parameter and `_cfg_from_dict`
reads five keys by name, so the opponent seat was STRUCTURALLY disarmed. Three
designs were bent around that hole rather than around the science — phasegate's
B16 contortion, S1 G3's arb-off constraint, and the 2026-08-30 H2H prereg whose
"ARB-ON both sides" leg was INEXPRESSIBLE (it would have shipped as a confounded
arb+fpu cell claiming one variable).

THE TWO PROPERTIES THIS FILE PINS, in order of how badly they would hurt:

  1. ADDITIVITY. An unarmed opponent changes NOTHING. No `opp_tiearb` key in the
     manifest (phasegate's `G-TIEARB-ARM` requires "opponent: no tiearb
     container"), no `opp_tiearb_*` key in summary.json, and the candidate's own
     `cand_tiearb` / `tiearb_*` blocks byte-identical to today's. Banked
     adjudicators read those spellings; a rename or an extra container would void
     live evidence.
  2. LIVENESS. An ARMED opponent must be witnessed BY PLAY, not by a config echo:
     per-game `opp_tiearb` telemetry off ITS OWN `FairAgentRs.stats()`, and a
     RAISE (never a silent None) when the seat is armed but has no rust agent —
     the J13 failure mode transposed to the other seat.

Rust legs are marked `slow` and skip LOUDLY when the installed `carc_rs` wheel
predates the arbiter; a skip on a box that just rebuilt is a failure of the
BUILD, not of this test.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import types
from dataclasses import fields
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "src", ROOT / "engine", ROOT / "scripts" / "classical_search",
           ROOT / "scripts", ROOT / "scripts" / "human_anchor"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import env_preamble  # noqa: E402,F401  MUST precede any carcassonne_ai import

import eval_fair_puct as E  # noqa: E402
import tiearb_gates as G  # noqa: E402

CFG_DICT = {"c_puct": 1.5, "tau_p": 5.0, "leaf_quantize": "float",
            "final_select": "visits", "value_norm": 15.0}

SPEC = {"enabled": True, "B": 4, "J": 2, "mode": "argmax",
        "salt": "tiearb2-deploy-v1", "eps": 0.0, "phase_gate": "all"}

#: The seven knobs a resolved arbiter dict carries, in both seats' spelling.
KNOBS = ("enabled", "b", "j", "mode", "salt", "eps", "phase_gate")


# --------------------------------------------------------------------------- #
# 1. THE FLAGS — the opponent set mirrors the candidate set EXACTLY.            #
# --------------------------------------------------------------------------- #
def _capture_parser(monkeypatch) -> argparse.ArgumentParser:
    """main()'s own ArgumentParser, captured by letting an unknown flag die.

    ⚠️ A SHIM MODULE, not an ArgumentParser subclass: argparse's own
    `super(ArgumentParser, self)` resolves the name from the argparse module
    globals at call time, so patching the class there recurses forever."""
    holder = {}

    def _factory(*a, **k):
        ap = argparse.ArgumentParser(*a, **k)
        holder.setdefault("ap", ap)
        return ap

    shim = types.SimpleNamespace(**{k: getattr(argparse, k)
                                    for k in dir(argparse) if not k.startswith("__")})
    shim.ArgumentParser = _factory
    monkeypatch.setattr(E, "argparse", shim)
    with pytest.raises(SystemExit):
        E.main(["--this-flag-does-not-exist"])
    return holder["ap"]


def test_every_cand_tiearb_flag_has_an_opp_twin_with_the_same_default(monkeypatch):
    ap = _capture_parser(monkeypatch)
    for knob in KNOBS:
        cand = ap.get_default(f"cand_tiearb_{knob}")
        opp = ap.get_default(f"opp_tiearb_{knob}")
        assert opp == cand, (
            f"--opp-tiearb-{knob} defaults to {opp!r} but --cand-tiearb-{knob} "
            f"defaults to {cand!r}; the two sets must mirror EXACTLY or a "
            "'both sides at the same spec' cell silently is not one")
    # the enabled flags are both store_true (absence == unarmed, never a default arm)
    assert ap.get_default("opp_tiearb_enabled") is False


def test_opp_tiearb_mode_and_phase_gate_accept_the_same_choices(monkeypatch):
    ap = _capture_parser(monkeypatch)
    acts = {a.dest: a for a in ap._actions}
    assert acts["opp_tiearb_mode"].choices == acts["cand_tiearb_mode"].choices
    assert (acts["opp_tiearb_phase_gate"].choices
            == acts["cand_tiearb_phase_gate"].choices)


@pytest.mark.parametrize("argv,needle", [
    # gated-but-disabled — the mis-typed-launcher shape, refused on BOTH seats.
    (["--opp-tiearb-phase-gate", "early"], "WITHOUT --opp-tiearb-enabled"),
    (["--cand-tiearb-phase-gate", "early"], "WITHOUT --cand-tiearb-enabled"),
    # rust-only, on both seats
    (["--opp-tiearb-enabled", "--backend", "python", "--opponent", "fair-champion"],
     "RUST-ONLY"),
    (["--cand-tiearb-enabled", "--backend", "python"], "RUST-ONLY"),
])
def test_the_refusals_mirror(argv, needle, capsys):
    with pytest.raises(SystemExit):
        E.main(argv)
    assert needle in capsys.readouterr().err


def _cli_error(argv) -> str:
    """Drive the CLI in a FRESH PROCESS and return its stderr.

    ⚠️ Why not in-process: `main()` injects the curve125 leaf into the process
    environment, so a SECOND in-process call that touches the h800/greedy RUNG
    dies on the harness's own (unrelated) "the ruler moved" guard before it can
    reach the refusal under test. Pre-existing harness behaviour, not this knob's
    — and a fresh process is the honest way to test a CLI refusal anyway."""
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts/classical_search/eval_fair_puct.py"),
         *argv], capture_output=True, text=True, timeout=600,
        env={k: v for k, v in os.environ.items()
             if k != "CARCASSONNE_V29_MEEPLE_CURVE"})
    assert r.returncode != 0, "expected the CLI to REFUSE:\n" + r.stdout[-2000:]
    return r.stderr


@pytest.mark.parametrize("opponent", ["h800", "greedy"])
def test_opp_tiearb_is_refused_for_a_leafless_rung(opponent):
    """A FROZEN RULER cannot host the arbiter (it stays python whatever --backend
    says), so arming it would grade an unarmed seat under an armed cell's name."""
    err = _cli_error(["--opp-tiearb-enabled", "--backend", "rust",
                      "--opponent", opponent])
    assert "fair-champion" in err and "--opp-tiearb-enabled" in err


# --------------------------------------------------------------------------- #
# 2. CONSTRUCTION — the knob reaches the OPPONENT's resolved config.            #
# --------------------------------------------------------------------------- #
def _capture_opponent_cfg(monkeypatch, **kw):
    """Build the head-to-head opponent with `_make_champion` stubbed out, and
    return the HeuristicPriorConfig it was handed."""
    seen = {}

    def _fake(info, cfg, *a, **k):
        seen["info"], seen["cfg"] = info, cfg
        return object()

    monkeypatch.setattr(E, "_make_champion", _fake)
    E._make_opponent("fair-champion", CFG_DICT, sims=8, k_dets=1, K=0,
                     rung_sims=800, seed=1, opp_leaf_cfg=None, **kw)
    return seen["cfg"]


def test_opponent_config_carries_the_arbiter_when_armed(monkeypatch):
    cfg = _capture_opponent_cfg(monkeypatch, tiearb=SPEC)
    assert cfg.tiearb_enabled is True
    assert (cfg.tiearb_b, cfg.tiearb_j) == (SPEC["B"], SPEC["J"])
    assert cfg.tiearb_mode == SPEC["mode"] and cfg.tiearb_salt == SPEC["salt"]
    assert cfg.tiearb_eps == SPEC["eps"]
    assert cfg.tiearb_phase_gate == SPEC["phase_gate"]


def test_opponent_config_is_untouched_when_unarmed(monkeypatch):
    """ADDITIVITY: `tiearb=None` (every historical caller) must build the config
    the pre-plumbing code built, field for field."""
    before = _capture_opponent_cfg(monkeypatch)                     # no tiearb kw
    after = _capture_opponent_cfg(monkeypatch, tiearb=None)         # explicit None
    off = _capture_opponent_cfg(monkeypatch,
                                tiearb={**SPEC, "enabled": False})  # armed=False
    for cfg in (before, after, off):
        assert bool(getattr(cfg, "tiearb_enabled", False)) is False
    assert {f.name: getattr(before, f.name) for f in fields(before)} == \
           {f.name: getattr(after, f.name) for f in fields(after)}


def test_the_shared_cfg_dict_cannot_express_the_arbiter(monkeypatch):
    """⛔ THE REASON THE PARAMETER HAD TO EXIST. `_cfg_from_dict` reads FIVE keys
    by name, so a `tiearb` smuggled into the SHARED dict is silently inert — and
    the shared dict builds BOTH sides anyway, so it could never be one-sided."""
    cfg = _capture_opponent_cfg(monkeypatch)
    smuggled = E._cfg_from_dict({**CFG_DICT, "tiearb": SPEC}, None)
    assert bool(getattr(smuggled, "tiearb_enabled", False)) is False
    assert bool(getattr(cfg, "tiearb_enabled", False)) is False


def test_arming_a_non_fair_champion_opponent_raises():
    for opponent in ("h800", "greedy", "bare-net"):
        with pytest.raises(ValueError, match="fair-champion"):
            E._make_opponent(opponent, CFG_DICT, sims=8, k_dets=1, K=0,
                             rung_sims=800, seed=1, tiearb=SPEC)


# --------------------------------------------------------------------------- #
# 3. TELEMETRY — stubbed `FairAgentRs.stats()`, both seats.                     #
# --------------------------------------------------------------------------- #
def _stats(**over):
    s = {
        "tiearb_enabled": True, "tiearb_tile_plies": 40, "tiearb_fired_plies": 17,
        "tiearb_pickchanges": 6, "tiearb_arms_total": 39,
        "tiearb_playouts_total": 156, "tiearb_secs": 1.25, "tiearb_errors": 0,
        "tiearb_first_error": None, "tiearb_partial_argmax": 0,
        "tiearb_max_plies": 400, "tiearb_mode": "argmax", "tiearb_b": 4,
        "tiearb_j": 2, "tiearb_phase_gate": "all", "tiearb_fired_early": 7,
        "tiearb_fired_mid": 6, "tiearb_fired_late": 4,
        "tiearb_pickchanges_early": 3, "tiearb_pickchanges_mid": 2,
        "tiearb_pickchanges_late": 1,
    }
    s.update(over)
    return s


class _Rs:
    def __init__(self, stats):
        self._stats = stats

    def stats(self):
        return self._stats


class _BareAgent:
    """The CANDIDATE shape: the rust agent itself (`._rs`)."""
    def __init__(self, stats):
        self._rs = _Rs(stats)


class _Handoff:
    """The OPPONENT shape: `_MarginalizedHandoff`, rust agent at `._prefix`."""
    def __init__(self, stats):
        self._prefix = _BareAgent(stats)


@pytest.fixture(autouse=True)
def _clean_worker_state():
    saved = dict(E._W)
    E._W.clear()
    yield
    E._W.clear()
    E._W.update(saved)


def test_unarmed_opponent_stamps_none():
    assert E._opp_tiearb_telemetry(_Handoff(_stats())) is None
    E._W["opp_tiearb"] = {**SPEC, "enabled": False}
    assert E._opp_tiearb_telemetry(_Handoff(_stats())) is None


def test_armed_opponent_block_is_schema_identical_to_the_candidates():
    E._W["opp_tiearb"] = dict(SPEC)
    E._W["cand_tiearb"] = dict(SPEC)
    opp = E._opp_tiearb_telemetry(_Handoff(_stats()))
    cand = E._cand_tiearb_telemetry(_BareAgent(_stats()))
    assert opp == cand, "the two seats must never drift into two schemas"
    assert opp["fires"] == opp["fired_plies"] == 17
    assert opp["phase_gate"] == "all"
    assert opp["fired_early"] + opp["fired_mid"] + opp["fired_late"] == 17


def test_armed_opponent_reaches_through_the_marginalized_handoff():
    """The opponent is wrapped; reading `rung._rs` (the candidate's lookup) would
    find nothing and — before the raise below — stamp a silent None."""
    E._W["opp_tiearb"] = dict(SPEC)
    h = _Handoff(_stats())
    assert getattr(h, "_rs", None) is None
    assert E._fair_rs(h) is h._prefix._rs
    assert E._opp_tiearb_telemetry(h)["tile_plies"] == 40


def test_armed_opponent_without_a_rust_agent_raises():
    E._W["opp_tiearb"] = dict(SPEC)
    with pytest.raises(RuntimeError, match="no FairAgentRs"):
        E._opp_tiearb_telemetry(object())


def test_armed_opponent_whose_stats_say_disabled_raises():
    """The STALE-WHEEL footgun: the knob was requested, the rust side dropped it."""
    E._W["opp_tiearb"] = dict(SPEC)
    with pytest.raises(RuntimeError, match="tiearb_enabled=False"):
        E._opp_tiearb_telemetry(_Handoff(_stats(tiearb_enabled=False)))


def test_a_stale_wheel_missing_the_phase_gate_fails_loud():
    """⛔ ABSENT is never a default: an ungated arbiter on a gated cell IS the
    ungated cell wearing the gated cell's name."""
    E._W["opp_tiearb"] = dict(SPEC)
    s = _stats()
    del s["tiearb_phase_gate"]
    with pytest.raises(KeyError):
        E._opp_tiearb_telemetry(_Handoff(s))


# --------------------------------------------------------------------------- #
# 4. SUMMARY — `tiearb_*` unchanged, `opp_tiearb_*` additive.                   #
# --------------------------------------------------------------------------- #
def _result(seed, a_seat, *, cand=None, opp=None):
    return E.GameResult(
        seed=seed, a_seat=a_seat, info="fair", exact_k=0, k_dets=1, sims=8,
        rung_sims=800, score_p0=50, score_p1=40, diff=(10 if a_seat == 0 else -10),
        won_by_champ=(a_seat == 0), drew=False, elapsed_s=1.0, moves=70,
        deck_hash="d", opponent="fair-champion",
        cand_tiearb=cand, opp_tiearb=opp)


def _summary(results):
    return E._summary(results, "fair", 0, 1, 8, 800, opponent="fair-champion",
                      opp_label="champ")


def _block():
    E._W["cand_tiearb"] = dict(SPEC)
    return E._cand_tiearb_telemetry(_BareAgent(_stats()))


def test_a_candidate_only_cell_emits_no_opponent_keys():
    b = _block()
    s = _summary([_result(1, 0, cand=b), _result(1, 1, cand=b)])
    assert s["tiearb_games"] == 2 and s["tiearb_fired_plies_total"] == 34
    assert not [k for k in s if k.startswith("opp_tiearb_")], (
        "an unarmed opponent must add NO summary key — banked adjudicators read "
        "this document and phasegate's G-TIEARB-ARM treats an opponent container "
        "as a defect")


def test_an_arb_off_cell_emits_no_tiearb_keys_at_all():
    s = _summary([_result(1, 0), _result(1, 1)])
    assert not [k for k in s if "tiearb" in k and k != "wc_tiebreak"]


def test_the_opponent_block_is_additive_and_leaves_the_candidate_untouched():
    b = _block()
    cand_only = _summary([_result(1, 0, cand=b), _result(1, 1, cand=b)])
    both = _summary([_result(1, 0, cand=b, opp=b), _result(1, 1, cand=b, opp=b)])
    for k, v in cand_only.items():
        assert both[k] == v, f"the opponent seat moved the candidate key {k}"
    assert both["opp_tiearb_games"] == 2
    assert both["opp_tiearb_fired_plies_total"] == 34
    assert both["opp_tiearb_phi"] == 17.0
    assert both["opp_tiearb_phase_gates"] == ["all"]
    assert both["opp_tiearb_G_FIRE_fired"] is False


def test_the_two_seats_summary_key_sets_are_identical_modulo_the_prefix():
    """⛔ THE ANTI-DRIFT PIN. The candidate's summary keys are written LITERALLY
    (their spellings are asserted by source text in tests/test_tiearb_phase_gate.py
    and tests/test_tiearb2_stage2.py's `G-PLY`, so they must not become f-strings);
    the opponent's come from `_tiearb_side_summary`. Two code paths, ONE schema —
    pinned here, so a key added to one seat and not the other fails loudly."""
    b = _block()
    s = _summary([_result(1, 0, cand=b, opp=b), _result(1, 1, cand=b, opp=b)])
    cand = {k[len("tiearb_"):] for k in s if k.startswith("tiearb_")}
    opp = {k[len("opp_tiearb_"):] for k in s if k.startswith("opp_tiearb_")}
    assert cand == opp and cand
    for stem in sorted(cand):
        assert s[f"tiearb_{stem}"] == s[f"opp_tiearb_{stem}"], (
            f"same telemetry both seats must aggregate identically: {stem}")


def test_an_opponent_that_never_fired_trips_its_own_G_FIRE():
    """A both-sides cell whose opponent never arbitrated is a ONE-SIDED cell
    wearing a symmetric cell's name — the defect this plumbing ends."""
    E._W["cand_tiearb"] = dict(SPEC)
    live = E._cand_tiearb_telemetry(_BareAgent(_stats()))
    inert = E._cand_tiearb_telemetry(_BareAgent(_stats(
        tiearb_fired_plies=0, tiearb_fired_early=0, tiearb_fired_mid=0,
        tiearb_fired_late=0)))
    s = _summary([_result(1, 0, cand=live, opp=inert),
                  _result(1, 1, cand=live, opp=inert)])
    assert s["tiearb_G_FIRE_fired"] is False
    assert s["opp_tiearb_G_FIRE_fired"] is True


def test_game_result_defaults_the_opponent_slot_to_none():
    """A record banked before the field existed still loads (`GameResult(**d)`)."""
    r = E.GameResult(seed=1, a_seat=0, info="fair", exact_k=0, k_dets=1, sims=8,
                     rung_sims=800, score_p0=1, score_p1=0, diff=1,
                     won_by_champ=True, drew=False, elapsed_s=0.0, moves=1,
                     deck_hash="d")
    assert r.opp_tiearb is None


# --------------------------------------------------------------------------- #
# 5. THE GATE HELPER — the vocabulary a both-sides prereg cites.                #
# --------------------------------------------------------------------------- #
def _manifest(cand=None, opp=None):
    m = {"config": {}}
    if cand is not None:
        m["cand_tiearb"] = dict(cand)
        m["config"]["cand_tiearb"] = dict(cand)
    if opp is not None:
        m["opp_tiearb"] = dict(opp)
        m["config"]["opp_tiearb"] = dict(opp)
    return m


OFF = {**SPEC, "enabled": False}


def test_gate_accepts_the_three_states():
    G.assert_tiearb_sides(_manifest(SPEC, SPEC), SPEC, SPEC)          # both armed
    G.assert_tiearb_sides(_manifest(SPEC, None), SPEC, None)          # cand only
    G.assert_tiearb_sides(_manifest(OFF, None), None, None)           # arb off
    G.assert_tiearb_sides(_manifest(None, None), None, None)          # nothing


def test_gate_rejects_an_unexpectedly_armed_opponent():
    with pytest.raises(G.TiearbGateError, match="expected UNARMED"):
        G.assert_tiearb_sides(_manifest(SPEC, SPEC), SPEC, None)


def test_gate_rejects_a_missing_opponent_arm():
    """THE ONE THE OLD VOCABULARY COULD NOT SAY: a cell claiming both sides while
    the opponent played the plain champion."""
    with pytest.raises(G.TiearbGateError, match="ABSENT from the manifest"):
        G.assert_tiearb_sides(_manifest(SPEC, None), SPEC, SPEC)
    with pytest.raises(G.TiearbGateError, match="present-but-disabled"):
        G.assert_tiearb_sides(_manifest(SPEC, OFF), SPEC, SPEC)


def test_gate_rejects_a_mismatched_spec_and_a_missing_key():
    with pytest.raises(G.TiearbGateError, match="B=16"):
        G.assert_tiearb_sides(_manifest(SPEC, {**SPEC, "B": 16}), SPEC, SPEC)
    thin = {k: v for k, v in SPEC.items() if k != "phase_gate"}
    with pytest.raises(G.TiearbGateError, match="phase_gate MISSING"):
        G.assert_tiearb_sides(_manifest(SPEC, thin), SPEC, SPEC)


def test_gate_tolerates_the_realized_close_out_counts():
    """The top-level address is patched with fired_*/pickchanges_* at close-out;
    a gate must read the same before and after."""
    realized = {**SPEC, "fired_plies": 38, "pickchanges": 23}
    G.assert_tiearb_sides(_manifest(SPEC, realized), SPEC, SPEC)


def test_gate_reads_the_opponent_block_mirror():
    m = {"config": {"cand_tiearb": dict(SPEC),
                    "opponent": {"tiearb": dict(SPEC)}}}
    findings = G.assert_tiearb_sides(m, SPEC, SPEC)
    assert any("config.opponent.tiearb" in f for f in findings)


def test_gate_summary_reader():
    sides = G.tiearb_sides_summary({"tiearb_games": 2, "tiearb_phi": 15.5,
                                    "tiearb_fired_plies_total": 31,
                                    "tiearb_pickchanges_total": 21,
                                    "tiearb_G_FIRE_fired": False})
    assert sides["candidate"]["phi"] == 15.5
    assert sides["opponent"] is None


# --------------------------------------------------------------------------- #
# 6. THE MANIFEST, FROM A REAL RUN — armed/absent x both sides.                 #
# --------------------------------------------------------------------------- #
def _carc_rs_has_tiearb() -> bool:
    try:
        from carcassonne_ai.rust_agent import search_config_rs
    except Exception:
        return False
    cfg = E._build_champ_cfg(1.5, 5.0, "float", "visits", 15.0, None, tiearb=SPEC)
    try:
        return dict(search_config_rs(cfg, 8).tiearb) == SPEC
    except Exception:
        return False


def _run(out: Path, extra: list[str]) -> dict:
    argv = [sys.executable, str(ROOT / "scripts/classical_search/eval_fair_puct.py"),
            "--backend", "rust", "--info", "fair", "--opponent", "fair-champion",
            "--k-dets", "1", "--sims", "4", "--exact-k", "0",
            "--n", "2", "--paired", "--seed-start", "167999999960",
            "--workers", "1", "--out-root", str(out.parent),
            "--out-subdir", out.name, "--rules-profile", "fixed_v1",
            "--no-results-csv"] + extra
    r = subprocess.run(argv, capture_output=True, text=True, timeout=900,
                       env={**__import__("os").environ, "CARCASSONNE_FIX_R9": "1"})
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-4000:]
    return {"manifest": json.loads((out / "manifest.json").read_text()),
            "summary": json.loads((out / "summary.json").read_text()),
            "stdout": r.stdout}


ARB4 = ["--cand-tiearb-b", "4", "--cand-tiearb-j", "2"]
OPP4 = ["--opp-tiearb-b", "4", "--opp-tiearb-j", "2"]
SPEC4 = {**SPEC, "B": 4, "J": 2}


@pytest.mark.slow
@pytest.mark.skipif(not _carc_rs_has_tiearb(),
                    reason="the installed carc_rs wheel predates the tie arbiter "
                           "— REBUILD THE WHEEL ON THIS BOX; a skip here on a "
                           "freshly-built box is a BUILD failure, not a test one")
@pytest.mark.parametrize("cand_on,opp_on", [(True, True), (True, False),
                                            (False, False)])
def test_real_run_manifest_shape(tmp_path, cand_on, opp_on):
    extra = []
    if cand_on:
        extra += ["--cand-tiearb-enabled"] + ARB4
    if opp_on:
        extra += ["--opp-tiearb-enabled"] + OPP4
    got = _run(tmp_path / "CELL", extra)
    man, summ = got["manifest"], got["summary"]

    # the CANDIDATE side never changes shape: always a full resolved dict, at both
    # addresses, whatever the opponent does.
    assert man["config"]["cand_tiearb"]["enabled"] is cand_on
    assert man["cand_tiearb"]["enabled"] is cand_on

    if opp_on:
        assert man["config"]["opp_tiearb"] == SPEC4
        assert man["config"]["opponent"]["tiearb"] == SPEC4
        # top level carries the resolved knobs PLUS the realized counts
        assert man["opp_tiearb"]["enabled"] is True
        assert man["opp_tiearb"]["fired_plies"] == summ["opp_tiearb_fired_plies_total"]
        assert summ["opp_tiearb_games"] == 2
        assert summ["opp_tiearb_fired_plies_total"] > 0, (
            "an armed opponent that never fired is an INERT seat, not a null")
        G.assert_tiearb_sides(man, SPEC4, SPEC4)
    else:
        # ⛔ ABSENT, at every address — phasegate's G-TIEARB-ARM depends on it.
        assert "opp_tiearb" not in man and "opp_tiearb" not in man["config"]
        assert "tiearb" not in man["config"]["opponent"]
        assert not [k for k in summ if k.startswith("opp_tiearb_")]
        G.assert_tiearb_sides(man, SPEC4 if cand_on else None, None)

    if cand_on:
        assert summ["tiearb_games"] == 2 and summ["tiearb_fired_plies_total"] > 0
