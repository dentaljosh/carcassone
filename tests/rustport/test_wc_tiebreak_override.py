"""WC tie-break — the FairAgentRs / SearchConfigRs resolution rule.

`PyFairAgent::new` takes a `wc_tiebreak` kwarg AND receives a separately
constructed `SearchConfigRs` that carries its own `wc_tiebreak`. The original
build let the kwarg clobber the SearchConfig unconditionally, which meant an
explicitly-armed SearchConfig could be silently DISARMED by the agent's default
— a wrong-rules-cell factory (the cell looks armed at the call site and plays
under the incumbent draw rule).

The resolution rule this file pins (`rust/carc/carc-py/src/lib.rs`):

  * kwarg omitted (`None`)                     => INHERIT the SearchConfig's value
  * kwarg `False` + SearchConfig armed          => REFUSED loudly (ValueError)
  * any other explicit kwarg                    => wins on BOTH legs
    (notably SearchConfig `False` + kwarg `True` = the normal arming path
     `rust_agent.py` uses, which must keep working)

Both legs' RESOLVED values are stamped by `stats()` (`wc_tiebreak` and
`wc_tiebreak_search`) so a future divergence is visible in the artifact rather
than assumed from the constructor's contract.

⚠️ Rust legs skip LOUDLY when the installed `carc_rs` wheel predates the knob —
carc_rs is a per-box BUILT artifact, so a skip on a box that just rebuilt is a
failure of the BUILD, not of this test.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "engine", ROOT / "scripts" / "rustport"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

carc_rs = pytest.importorskip("carc_rs", reason="build with `maturin develop --release`")

import trace_search as T  # noqa: E402

STALE = (
    "the installed carc_rs wheel predates the WC tie-break `wc_tiebreak` knob — "
    "rebuild the wheel on THIS box (per-box footgun: carc_rs is a built artifact; "
    "reinstall from rust/carc/target/wheels). A skip here on a box that just "
    "rebuilt is a BUILD failure, not a test failure."
)


def _search_cfg(wc_tiebreak: bool):
    """A production-knob `SearchConfigRs` with `wc_tiebreak` set explicitly."""
    k = T.production_knobs()
    leaf = T._rec_mod()._to_rs(k["leaf_cfg"])
    try:
        return carc_rs.SearchConfigRs(
            leaf, 8, k["c_puct"], k["tau_p"], k["value_norm"],
            k["score_norm_scale"], k["leaf_quantize"], k["final_select"],
            None, 1.0, True, "glibc_fma", wc_tiebreak=wc_tiebreak)
    except TypeError as e:                       # pragma: no cover - stale wheel
        if "wc_tiebreak" in str(e):
            pytest.skip(STALE)
        raise


def _agent(search_cfg, **kw):
    try:
        return carc_rs.FairAgentRs(search_cfg, k_dets=1, seed=0, threads=1, **kw)
    except TypeError as e:                       # pragma: no cover - stale wheel
        if "wc_tiebreak" in str(e):
            pytest.skip(STALE)
        raise


def _resolved(agent) -> tuple[bool, bool]:
    """(solver leg, search leg) as stamped by `stats()`."""
    s = agent.stats()
    if "wc_tiebreak" not in s:                   # pragma: no cover - stale wheel
        pytest.skip(STALE)
    return bool(s["wc_tiebreak"]), bool(s["wc_tiebreak_search"])


# --------------------------------------------------------------------------- #
# the resolution truth table                                                    #
# --------------------------------------------------------------------------- #
def test_default_is_off_on_both_legs():
    """Nothing said anywhere == the untouched incumbent."""
    assert _resolved(_agent(_search_cfg(False))) == (False, False)


def test_omitted_kwarg_inherits_an_armed_search_config():
    """The bug this file exists for: an armed SearchConfig must SURVIVE an
    agent that says nothing about the rule."""
    assert _resolved(_agent(_search_cfg(True))) == (True, True)


def test_omitted_kwarg_inherits_an_unarmed_search_config():
    assert _resolved(_agent(_search_cfg(False))) == (False, False)


def test_explicit_true_arms_both_legs_the_normal_arming_path():
    """`rust_agent.py` builds the SearchConfig WITHOUT the knob and passes
    `wc_tiebreak=True` to the agent only when armed — this combination must
    keep working and must reach BOTH legs."""
    assert _resolved(_agent(_search_cfg(False), wc_tiebreak=True)) == (True, True)


def test_explicit_true_agrees_with_an_armed_search_config():
    assert _resolved(_agent(_search_cfg(True), wc_tiebreak=True)) == (True, True)


def test_explicit_false_on_an_unarmed_search_config_is_fine():
    assert _resolved(_agent(_search_cfg(False), wc_tiebreak=False)) == (False, False)


def test_silently_disarming_an_armed_search_config_is_REFUSED():
    """The dangerous combination: armed SearchConfig + `wc_tiebreak=False`.
    Refused loudly rather than silently dropping a RULES flag."""
    cfg = _search_cfg(True)
    with pytest.raises(ValueError) as ei:
        _agent(cfg, wc_tiebreak=False)
    msg = str(ei.value)
    assert "wc_tiebreak" in msg
    # the message must name the fix, not just the fault
    assert "omit" in msg.lower() or "both" in msg.lower()


def test_both_legs_are_always_stamped_and_always_agree():
    """`stats()` emits the resolved value for each leg; they are reconciled at
    construction, so they must never disagree."""
    for cfg_armed, kw in ((False, {}), (True, {}), (False, {"wc_tiebreak": True}),
                          (True, {"wc_tiebreak": True})):
        solver, search = _resolved(_agent(_search_cfg(cfg_armed), **kw))
        assert solver == search, (cfg_armed, kw, solver, search)
