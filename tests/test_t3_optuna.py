"""T3 joint Optuna knob-sweep tests (design: measurement/classical_search/
OPTUNA_KNOB_SWEEP_DESIGN.md).

This file covers the two T3 Stage-0 code artifacts that carry pytest-checkable
contracts:

  * ``--opp-pin-champion`` in eval_puct_priors.py (design §3/§5a) — the shared-axis
    leak fix. Unit tests prove the pinned opponent PUCT sibling takes the champion
    CONSTANTS (not the candidate's c_puct/tau_p/leaf_quantize), a leak-demo test proves
    the DEFAULT (unpinned) path copies the candidate knobs (the bug the flag fixes),
    and a bit-exact MIRROR integration test proves the flag is byte-identical to today
    when the candidate is at the champion knobs (S0a-as-pytest).

  * ``optuna_knob_sweep.py`` emission exactness (design §2/§5c) — scale==1.0 emits the
    champion leaf VERBATIM so trial-0's leaf hash == the champion hash, scale!=1 differs,
    closure_p keys survive the str->int round-trip, and every knob rounds/clamps to §2.

The harness sets the production leaf env at import via setdefault; but §5(e) requires the
CURVE125 champion leaf (the _CANON_ENV setdefault is the STALE curve100), so this file
exports the curve125 env BEFORE importing the harness — matching the launcher.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# §5(e): the champion side is curve125 — export it BEFORE importing the harness so
# DEFAULT_CONFIG resolves to the curve125 champion leaf (hash a36d2e15a3b3d71d), NOT the
# harness's stale curve100 _CANON_ENV setdefault. Mirrors c7_s1_launcher.sh lines 80-83.
os.environ.setdefault("CARCASSONNE_V25_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_OPP_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "0")
os.environ.setdefault("CARCASSONNE_V29_MEEPLE_CURVE", "-10,-5,-1.25,0,2.5,3.75,5,6.25")
os.environ.setdefault("CARCASSONNE_V25_MEEPLE_K", "2.0")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_CY_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_CY_REPR", "1")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

SCRIPT = REPO / "scripts" / "classical_search" / "eval_puct_priors.py"
_spec = importlib.util.spec_from_file_location("eval_puct_priors", SCRIPT)
epp = importlib.util.module_from_spec(_spec)
sys.modules["eval_puct_priors"] = epp  # fork-Pool workers unpickle _play_one by module name
_spec.loader.exec_module(epp)

# the T3 driver (emission exactness §5c, anchors, ranges/rounding §2)
_dspec = importlib.util.spec_from_file_location(
    "optuna_knob_sweep", REPO / "scripts" / "classical_search" / "optuna_knob_sweep.py")
oks = importlib.util.module_from_spec(_dspec)
sys.modules["optuna_knob_sweep"] = oks
_dspec.loader.exec_module(oks)

DEF = epp.DEFAULT_CONFIG

# curve125 champion leaf hash on current code (verified 2026-07-14 against the real
# C7 curve125 manifests). NOTE: the design §5(e) literal "96d2c075f85e9583" is STALE —
# the current-code _leaf_hash of the curve125 DEFAULT_CONFIG is this value; the gate's
# INTENT (champion side is curve125, distinct from curve100 42af12fce22e1a0f) is preserved.
CURVE125_LEAF_HASH = "a36d2e15a3b3d71d"


# --------------------------------------------------------------------------- #
# §5(e): the launcher env resolves the curve125 champion leaf (a36d2e15...),    #
# distinct from the harness's stale curve100 _CANON_ENV setdefault (42af12...). #
# Resolved in a CLEAN SUBPROCESS: DEFAULT_CONFIG is captured at virtual_score_v2 #
# import, so an in-process check is contaminated by whichever env was set before #
# the FIRST harness import in the pytest session — exactly the §5(e) trap, and   #
# exactly why the real launcher exports the curve125 env before python starts.   #
# --------------------------------------------------------------------------- #
def _leaf_hash_under_curve_env(curve: str) -> str:
    env = dict(os.environ)
    env.update({
        "CARCASSONNE_V25_CAP": "8", "CARCASSONNE_V25_OPP_CAP": "8",
        "CARCASSONNE_V25_DROP_THREE_OPEN": "0", "CARCASSONNE_V25_MEEPLE_K": "2.0",
        "CARCASSONNE_V25_VALUE_BLEND": "0", "CARCASSONNE_USE_FLAT_LEAF": "1",
        "CARCASSONNE_USE_CY_LEAF": "1", "CARCASSONNE_USE_CY_REPR": "1",
        "CUDA_VISIBLE_DEVICES": "", "CARCASSONNE_V29_MEEPLE_CURVE": curve,
    })
    # replicate _leaf_hash / _leaf_dict verbatim (c5_leaf_override) with no import-path
    # deps — INCLUDING the F6 soft-cap and F7b farm-knockout default-off exclusions
    # so a36d2e15 stays stable.
    code = (
        "import hashlib,json;from dataclasses import asdict;"
        "from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG as c;"
        "_ex={'soft_cap_slope':0.0,'opp_soft_cap_slope':0.0,"
        "'farm_base_off':False,'farm_growth_off':False,"
        "'v29_phase_beta':0.0,'v29_phase_norm':1.0};"
        "d={k:(list(v) if isinstance(v,tuple) else v) for k,v in asdict(c).items() "
        "if not (k in _ex and v==_ex[k])};"
        "print(hashlib.sha256(json.dumps(d,sort_keys=True,default=str).encode()).hexdigest()[:16])"
    )
    out = subprocess.check_output([sys.executable, "-c", code], env=env, cwd=str(REPO))
    return out.decode().strip()


def test_champion_leaf_is_curve125_under_launcher_env():
    assert _leaf_hash_under_curve_env("-10,-5,-1.25,0,2.5,3.75,5,6.25") == CURVE125_LEAF_HASH
    # the stale curve100 default resolves to a DIFFERENT hash (the §5e wrong-champion trap)
    assert _leaf_hash_under_curve_env("-8,-4,-1,0,2,3,4,5") == "42af12fce22e1a0f"
    assert _leaf_hash_under_curve_env("-8,-4,-1,0,2,3,4,5") != CURVE125_LEAF_HASH


# --------------------------------------------------------------------------- #
# --opp-pin-champion: pinned opponent == champion constants (§3/§5a)           #
# --------------------------------------------------------------------------- #
def test_pin_champion_uses_constants_when_candidate_differs():
    # candidate off every shared axis -> pinned opponent still reads champion constants
    shared = {"c_puct": 2.0, "tau_p": 3.5, "leaf_quantize": "int"}
    pinned = epp._champ_puct_cfg(shared, pin_champion=True)
    assert pinned.c_puct == epp.CHAMP_PUCT_C_PUCT == 1.5
    assert pinned.tau_p == epp.CHAMP_PUCT_TAU_P == 5.0
    assert pinned.leaf_quantize == epp.CHAMP_PUCT_LEAF_QUANTIZE == "float"
    # the always-pinned champion knobs are unchanged by the new flag
    assert pinned.final_select == epp.CHAMP_PUCT_FINAL_SELECT
    assert pinned.value_norm == epp.CHAMP_PUCT_VALUE_NORM
    assert pinned.c_lcb == epp.CHAMP_PUCT_C_LCB
    assert pinned.reuse_tree is False
    # champion side leaf is ALWAYS env DEFAULT_CONFIG (never the candidate override)
    assert pinned.leaf_cfg == DEF


def test_leak_demo_unpinned_takes_candidate_knobs():
    # THE LEAK, demonstrated once for the record (design §3): the DEFAULT (unpinned) path
    # copies the candidate's c_puct/tau_p/leaf_quantize onto the champion sibling, so a
    # sweep of --c-puct would move BOTH sides and the A/B measures nothing.
    shared = {"c_puct": 2.0, "tau_p": 3.5, "leaf_quantize": "int"}
    leaked = epp._champ_puct_cfg(shared, pin_champion=False)
    assert leaked.c_puct == 2.0 and leaked.tau_p == 3.5 and leaked.leaf_quantize == "int"


def test_pin_and_leak_diverge_offbaseline_agree_at_champion():
    off = {"c_puct": 2.0, "tau_p": 3.5, "leaf_quantize": "float"}
    assert epp._champ_puct_cfg(off, pin_champion=True).c_puct != \
        epp._champ_puct_cfg(off, pin_champion=False).c_puct
    # candidate already AT champion knobs -> pin and leak are indistinguishable (mirror)
    champ = {"c_puct": 1.5, "tau_p": 5.0, "leaf_quantize": "float"}
    a = epp._champ_puct_cfg(champ, pin_champion=True)
    b = epp._champ_puct_cfg(champ, pin_champion=False)
    assert (a.c_puct, a.tau_p, a.leaf_quantize) == (b.c_puct, b.tau_p, b.leaf_quantize)


def test_pin_requires_opponent_puct():
    # --opp-pin-champion without --opponent puct is an argparse error (SystemExit)
    with pytest.raises(SystemExit):
        epp.main(["--candidate", "puct", "--cand-sims", "16", "--opp-pin-champion",
                  "--n", "2", "--paired", "--summary-only"])


def test_variant_sig_tags_pinned_c_and_tau_only_when_diverged():
    import types
    base = dict(root_select="puct", final_select="visits", c_lcb=1.0, reuse_tree=False,
                value_norm=15.0, gumbel_m=16, gumbel_retain_g=True, gumbel_c_visit=50.0,
                gumbel_c_scale=1.0, c_puct=1.5, tau_p=5.0)
    # pinning OFF -> c/τ never tagged (legacy shared-axis behavior, byte-identical)
    a = types.SimpleNamespace(**{**base, "c_puct": 2.0, "opp_pin_champion": False})
    assert epp._variant_sig(a) == ""
    # pinning ON, candidate at champion c/τ -> still no tag
    b = types.SimpleNamespace(**{**base, "opp_pin_champion": True})
    assert epp._variant_sig(b) == ""
    # pinning ON, candidate off-baseline -> both tags appended
    c = types.SimpleNamespace(**{**base, "c_puct": 2.0, "tau_p": 3.5, "opp_pin_champion": True})
    assert epp._variant_sig(c) == "-c2-tp3.5"


# --------------------------------------------------------------------------- #
# Bit-exact MIRROR + leak integration (S0a as pytest)                          #
# --------------------------------------------------------------------------- #
def _run_cell(tmp: Path, sub: str, extra: list[str], cpuct: str = "1.5"):
    prev = sys.modules.get("eval_puct_priors")
    sys.modules["eval_puct_priors"] = epp
    try:
        rc = epp.main([
            "--candidate", "puct", "--opponent", "puct",
            "--cand-sims", "16", "--c-puct", cpuct, "--tau-p", "5",
            "--leaf-quantize", "float", "--final-select", "visits", "--value-norm", "15",
            "--exact-k", "2", "--n", "4", "--paired", "--workers", "2",
            "--seed-start", "20090000000",   # S0 smoke band 2.009e10 (design §4)
            "--out-root", str(tmp), "--out-subdir", sub, "--no-results-csv"] + extra)
    finally:
        if prev is not None:
            sys.modules["eval_puct_priors"] = prev
    assert rc == 0
    out = tmp / sub
    recs = {p.name: json.load(open(p)) for p in out.glob("seed*.json")}
    summ = json.load(open(out / "summary.json"))
    man = json.load(open(out / "manifest.json"))["config"]
    return recs, summ, man


def test_pin_mirror_bit_exact_at_champion_knobs(tmp_path):
    # candidate at champion knobs + champion leaf VERBATIM + --opp-pin-champion must
    # reproduce the no-flag/no-JSON run move-for-move (the S0a leak-fix proof).
    mirror = json.dumps({
        "bonus_cap": DEF.bonus_cap, "opp_bonus_cap": DEF.opp_bonus_cap,
        "closure_p": {str(k): v for k, v in DEF.closure_p.items()},
        "v29_meeple_curve": list(DEF.v29_meeple_curve),
    })
    base_recs, base_summ, base_man = _run_cell(tmp_path, "noflag", [])
    pin_recs, pin_summ, pin_man = _run_cell(
        tmp_path, "pinmirror", ["--cand-leaf-json", mirror, "--opp-pin-champion"])

    assert base_recs and set(base_recs) == set(pin_recs)
    for name in base_recs:
        b, o = base_recs[name], pin_recs[name]
        for k in ("diff", "score_p0", "score_p1", "moves", "deck_hash",
                  "cand_prefix_moves", "cand_exact_moves", "won_by_cand", "drew"):
            assert b[k] == o[k], f"{name}: {k} differs (noflag {b[k]} vs pinmirror {o[k]})"
    for k in ("W", "L", "D", "paired_mean_margin", "avg_diff"):
        assert base_summ[k] == pin_summ[k], f"summary {k} differs"
    # both sides resolve the SAME champion leaf (self-consistent; the absolute curve125
    # hash gate is the subprocess test above — in-process DEF is import-order dependent).
    assert base_man["champ_leaf_hash"] == pin_man["champ_leaf_hash"]
    assert pin_man["cand_leaf_hash"] == pin_man["champ_leaf_hash"]  # mirror -> cand==champ
    # manifest opponent block records the pin
    assert pin_man["opponent"]["pinned_champion_knobs"] is True
    assert pin_man["opponent"]["pinned_c_puct"] == 1.5
    assert pin_man["opponent"]["c_puct"] == 1.5


def test_pin_vs_leak_manifest_opponent_c_puct(tmp_path):
    # candidate at c_puct 2.0. Pinned -> opponent sees champion 1.5; unpinned (the leak)
    # -> opponent inherits the candidate's 2.0 (demonstrated once for the record).
    _, _, pin_man = _run_cell(tmp_path, "pin_c2", ["--opp-pin-champion"], cpuct="2.0")
    _, _, leak_man = _run_cell(tmp_path, "leak_c2", [], cpuct="2.0")
    assert pin_man["candidate"]["c_puct"] == 2.0
    assert pin_man["opponent"]["c_puct"] == 1.5          # pinned to champion
    assert pin_man["opponent"]["pinned_champion_knobs"] is True
    assert leak_man["candidate"]["c_puct"] == 2.0
    assert leak_man["opponent"]["c_puct"] == 2.0         # THE LEAK
    assert leak_man["opponent"]["pinned_champion_knobs"] is False


# --------------------------------------------------------------------------- #
# Driver EMISSION EXACTNESS (S0c, design §2/§5c) — self-consistent vs whatever  #
# DEFAULT_CONFIG resolved to (the absolute curve125 hash is the subprocess test).#
# --------------------------------------------------------------------------- #
def test_emission_champion_verbatim_hashes_equal():
    # scale==1.0 / caps==champion emits the champion leaf VERBATIM -> cand hash == champ
    assert oks.cand_leaf_hash(oks.CHAMP) == epp._leaf_hash(DEF)


def test_emission_scale_and_caps_change_the_hash():
    for override in ({"curve_scale": 1.2}, {"pclose_scale": 1.1},
                     {"bonus_cap": 7.0}, {"opp_bonus_cap": 9.0}):
        p = {**oks.CHAMP, **override}
        assert oks.cand_leaf_hash(p) != epp._leaf_hash(DEF), override


def test_emission_curve_scale_multiplies_each_entry():
    lj = oks.leaf_json({**oks.CHAMP, "curve_scale": 1.2})
    for got, base in zip(lj["v29_meeple_curve"], oks.CHAMP_CURVE):
        assert got == pytest.approx(base * 1.2)


def test_emission_pclose_scale_multiplies_each_value():
    lj = oks.leaf_json({**oks.CHAMP, "pclose_scale": 1.1})
    assert lj["closure_p"] == {k: pytest.approx(oks.CHAMP_CLOSURE_P[int(k)] * 1.1)
                               for k in ("1", "2", "3")}


def test_emission_closure_keys_survive_str_to_int_roundtrip():
    lj = oks.leaf_json({**oks.CHAMP, "pclose_scale": 1.1})
    assert set(lj["closure_p"]) == {"1", "2", "3"}          # emitted as str keys
    cfg = epp._load_cand_leaf_cfg(json.dumps(lj))
    assert set(cfg.closure_p) == {1, 2, 3}                  # coerced back to int
    assert all(isinstance(k, int) for k in cfg.closure_p)


def test_emission_leaf_stays_on_cy_float_path():
    # every emitted candidate leaf must clear the cy-float guard (else ~30x object path)
    for override in ({}, {"curve_scale": 0.8}, {"curve_scale": 1.45},
                     {"pclose_scale": 1.3}, {"bonus_cap": 12.0}, {"opp_bonus_cap": 6.5}):
        cfg = epp._load_cand_leaf_cfg(json.dumps(oks.leaf_json({**oks.CHAMP, **override})))
        epp._assert_cy_float_path(cfg)   # must not raise


# --------------------------------------------------------------------------- #
# Driver SPACE / rounding (§2) + enqueued anchors (§1(5))                      #
# --------------------------------------------------------------------------- #
def test_space_ranges_and_rounding():
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = oks.build_study(None, 20260714, in_memory=True)
    dp = {k: oks.SPACE[k][3] for k in oks.KNOB_ORDER}
    for _ in range(60):
        t = study.ask()
        p = oks.suggest_params(t)
        for knob in oks.KNOB_ORDER:
            lo, hi, _log, ndp = oks.SPACE[knob]
            assert lo <= p[knob] <= hi, f"{knob}={p[knob]} out of [{lo},{hi}]"
            assert round(p[knob], ndp) == p[knob], f"{knob} not rounded to {ndp}dp"
        study.tell(t, 0.0)


def test_enqueued_anchors_are_champion_and_curve14():
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = oks.build_study(None, 20260714, in_memory=True)
    oks.enqueue_anchors_if_fresh(study)
    t0 = study.ask(); p0 = oks.suggest_params(t0)
    assert p0 == {k: oks.CHAMP[k] for k in oks.KNOB_ORDER}      # trial 0 = champion
    assert oks.cand_leaf_hash(p0) == epp._leaf_hash(DEF)        # -> champion leaf hash
    study.tell(t0, 0.0)
    t1 = study.ask(); p1 = oks.suggest_params(t1)
    assert p1["curve_scale"] == 1.4                             # trial 1 = curve1.4rel
    assert all(p1[k] == oks.CHAMP[k] for k in oks.KNOB_ORDER if k != "curve_scale")


def test_env_guard_raises_on_wrong_champion(monkeypatch):
    # verify_champion_env must FAIL LOUD if DEFAULT_CONFIG isn't the curve125 champion
    monkeypatch.setattr(oks, "EXPECTED_CHAMP_LEAF_HASH", "deadbeefdeadbeef")
    with pytest.raises(SystemExit):
        oks.verify_champion_env()
