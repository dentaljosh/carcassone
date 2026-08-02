"""Contract tests for the Rust net-arm seam probe (`rust_agent.net_arm_backend_status`).

The probe's whole job is to make "net arms are Python" an ASSERTED fact rather than
an implicit one, so the things worth pinning are: it never raises, it never claims
support it cannot back, and it carries the gate's bar unmodified.

See `docs/RUST_NET_EVAL_DESIGN_20260802.md`.
"""
from __future__ import annotations

import carcassonne_ai.rust_agent as rust_agent


def test_probe_returns_a_complete_dict_and_never_raises():
    st = rust_agent.net_arm_backend_status()
    assert isinstance(st, dict)
    for key in ("supported", "reason", "carc_rs_present", "carc_rs_version",
                "reopen_r_bar", "r_is_an_upper_bound", "design_doc"):
        assert key in st, f"probe is missing {key!r}"


def test_unsupported_states_always_carry_a_reason():
    """A bare `supported: False` in a manifest is unactionable a month later."""
    st = rust_agent.net_arm_backend_status()
    if not st["supported"]:
        assert st["reason"], "an unsupported probe must say why"
    else:
        assert st["reason"] is None


def test_support_is_never_claimed_without_the_pyo3_surface():
    """The failure this guards is a probe that reports green because carc_rs
    imported, while the evaluator type it needs does not exist — which would route
    a net arm onto a backend that cannot run it."""
    import carc_rs

    st = rust_agent.net_arm_backend_status()
    if st["supported"]:
        assert hasattr(carc_rs, "PolicyEvaluatorRs")


def test_reopen_bar_matches_the_gate_of_record():
    """`NETPRIOR_EQTIME_GATE_20260728.md` §6 fixed r <= ~1.5 BEFORE anything was
    built. If this constant ever drifts, the drift must be a decision, not a typo."""
    assert rust_agent.NET_ARM_REOPEN_R_BAR == 1.5
    assert rust_agent.net_arm_backend_status()["reopen_r_bar"] == 1.5


def test_r_is_documented_as_an_upper_bound_for_the_rust_port():
    """Net priors REPLACE the classical child-leaf sweep, so the additive `r` model
    overstates the port's true cost ratio. Pinned because reading `r` as exact is
    the single easiest way to mis-decide this lever."""
    assert rust_agent.net_arm_backend_status()["r_is_an_upper_bound"] is True
