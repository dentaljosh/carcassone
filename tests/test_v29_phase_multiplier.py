"""Part C PHASE MULTIPLIER on the v2.9 meeple curve
(`LeafConfig.v29_phase_beta` / `v29_phase_norm`).

Prereg: `measurement/curve_shape_scope_20260809/PREREG_DRAFT.md` §4, `SCOPE.md` §1.3.

    f(k; beta) = clip(1 + beta*(k - 35)/35, 0.0, 2.0)      K0 = 35
    f_eff      = f(k; beta) / v29_phase_norm

multiplies the meeple-economy differential `curve[m_self] - curve[m_opp]`.
`v29_phase_norm` is a RUN-LEVEL scalar (E[f] over a game's empirical k-distribution,
`scripts/classical_search/compute_phase_norm.py`) supplied by the caller — the leaf
stays a pure deterministic function of `(state, cfg)` so hashing and py/cy/rust
reconciliation hold. The renormalization is the methodological point: without it beta
moves the term's mean MAGNITUDE and the cell measures scale, not phase (the confound
that invalidated the 2026-06-22 `v28_meeple_recovery_t0` kill — a DIFFERENT, and
deliberately untouched, lever).

Contracts:
  1. DEFAULT OFF IS INERT — and inert by CONSTRUCTION, not by luck: `beta == 0.0`
     takes an EARLY BRANCH through the unmodified expression on every substrate
     (proved by monkeypatching `_phase_mult` to raise), the champion's leaf hashes
     recompute unchanged, and leaf values are bit-identical.
  2. beta == 0.0 is inert EVEN AT A NON-1.0 norm (the branch keys on beta alone), so
     a stray norm can never perturb the champion.
  3. THE KNOB BITES, in the right DIRECTION: beta > 0 magnifies the term early
     (k > 35) and shrinks it late (k < 35); beta < 0 does the reverse; the norm
     divides.
  4. THE CLIP BOUNDS FIRE at extreme beta (0.0 and 2.0 at the two deck ends).
  5. PY == CY == RUST bit-exactly WITH the knob on (the full-corpus version is
     `scripts/rustport/reconcile_leaf.py --configs phase`).
  6. `k_remaining` IS `fair_agent.k_remaining` — `len(deck) + (next_tile is not None)`
     — on EVERY ply including the MEEPLES phase, where `_bag_stats` deliberately
     disagrees (there `next_tile` is a stale ref to the just-placed tile). A silent
     substitution of `_bag_stats`' count would shift the phase clock by one tile per
     meeple ply.
  7. A STALE `.so` CANNOT SILENTLY DROP THE KNOB — the dispatcher refuses the cy fast
     path unless the build advertises `SUPPORTS_V29_PHASE` (a dropped multiplier reads
     as "phase does nothing", i.e. a FALSE NULL, which is worse than a slowdown).
"""
from __future__ import annotations

import dataclasses as dc
import random

import numpy as np
import pytest

from carcassonne_ai import flat_leaf
from carcassonne_ai.fair_agent import k_remaining as fair_k_remaining
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

CURVE125 = (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25)
CHAMP = dc.replace(DEFAULT_CONFIG, meeple_k=2.0, bonus_cap=8.0, opp_bonus_cap=8.0,
                   closure_p={1: 0.5, 2: 0.2, 3: 0.05}, v29_meeple_curve=CURVE125)
B_POS = dc.replace(CHAMP, v29_phase_beta=0.6, v29_phase_norm=1.0)
B_NEG = dc.replace(CHAMP, v29_phase_beta=-0.6, v29_phase_norm=1.0)
B_NORM = dc.replace(CHAMP, v29_phase_beta=0.6, v29_phase_norm=1.0723)
B_CLIP = dc.replace(CHAMP, v29_phase_beta=3.0, v29_phase_norm=1.0)

cy = pytest.importorskip("carcassonne_ai.flat_leaf_cy")


def _states(n_seeds=5, max_plies=150, start=4, every=4, seed_base=8090):
    """Real mid-game states across the whole deck sweep, so k ranges over both sides
    of K0=35 and both game phases are represented."""
    out = []
    for s in range(n_seeds):
        g = Game(enable_legal_moves_cache=True)
        b = g.get_init_board()
        rng = random.Random(seed_base + s)
        ply = 0
        while g.get_game_ended(b, 0) == 0.0 and ply < max_plies:
            if ply >= start and ply % every == 0:
                out.append(b.state)
            legal = np.flatnonzero(g.get_valid_moves(b))
            b, _ = g.get_next_state(b, int(rng.choice(legal.tolist())))
            ply += 1
    assert out, "no states generated"
    return out


STATES = _states()


# --- 1/2. default-off inertness --------------------------------------------- #
def test_champion_leaf_hash_unchanged():
    """The a36d2e15 dialect and the frozen-substrate recipe both EXCLUDE the two new
    fields while at their defaults, so the champion's fingerprints are byte-stable
    across this additive field pair."""
    import sys
    sys.path.insert(0, "scripts/classical_search")
    sys.path.insert(0, "scripts/measurement_infra")
    from c5_leaf_override import _leaf_hash as c5_hash
    from carcassonne_ai.alphabeta_agent import _leaf_hash as ab_hash
    from snapshot import _frozen_config_hash, FROZEN_V29_HASH

    assert c5_hash(CHAMP) == ab_hash(CHAMP) == "a36d2e15a3b3d71d"
    frozen = dc.replace(CHAMP, v29_meeple_curve=(-8.0, -4.0, -1.0, 0.0, 2.0, 3.0, 4.0, 5.0))
    assert _frozen_config_hash(frozen) == FROZEN_V29_HASH
    # a SET beta IS a different leaf and MUST move the hash
    assert ab_hash(B_POS) != ab_hash(CHAMP)


def test_default_off_never_enters_the_phase_branch(monkeypatch):
    """Inert BY CONSTRUCTION: with beta == 0.0 the multiplier function is never
    called, on the pure-Python flat path OR through the wrapper. (A `* 1.0` would be
    numerically exact but would still re-associate the expression; the early branch
    is what makes the default BYTE-identical rather than merely equal.)"""
    def boom(*a, **k):
        raise AssertionError("_phase_mult called with the knob at its default")

    monkeypatch.setattr(flat_leaf, "USE_CY_LEAF", False)   # else cy serves it and the
    monkeypatch.setattr(flat_leaf, "_phase_mult", boom)    # assertion is vacuous
    for st in STATES[:12]:
        flat_leaf.flat_virtual_score_v2(st, 0, CHAMP)
        flat_leaf.flat_virtual_score_v2_float(st, 1, CHAMP)


def test_default_off_values_identical_on_every_substrate():
    for st in STATES:
        for p in (0, 1):
            base = flat_leaf.flat_virtual_score_v2(st, p, CHAMP)
            explicit = flat_leaf.flat_virtual_score_v2(
                st, p, dc.replace(CHAMP, v29_phase_beta=0.0, v29_phase_norm=1.0))
            assert base == explicit
            assert int(cy.flat_virtual_score_v2_cy(st, p, CHAMP, False)) == base


def test_beta_zero_is_inert_even_at_a_non_unit_norm():
    """The branch keys on beta ALONE, so a stray/garbage norm cannot perturb the
    champion. (Belt-and-braces: `compute_phase_norm.py` returns norm=1.0 at beta=0,
    but nothing in the leaf depends on the caller getting that right.)"""
    stray = dc.replace(CHAMP, v29_phase_beta=0.0, v29_phase_norm=7.3)
    for st in STATES[:20]:
        for p in (0, 1):
            assert (flat_leaf.flat_virtual_score_v2_float(st, p, stray)
                    == flat_leaf.flat_virtual_score_v2_float(st, p, CHAMP))
            assert (float(cy.flat_virtual_score_v2_cy_float(st, p, stray, False))
                    == float(cy.flat_virtual_score_v2_cy_float(st, p, CHAMP, False)))


# --- 3. the knob bites, in the right direction ------------------------------ #
def test_phase_mult_formula_and_direction():
    """`clip(1 + beta*(k-35)/35, 0, 2)/norm`, checked against the literal spec."""
    class S:                                   # a minimal duck for _phase_mult
        def __init__(self, k, in_hand=True):
            self.deck = [None] * (k - 1 if in_hand else k)
            self.next_tile = object() if in_hand else None

    assert flat_leaf._PHASE_K0 == 35.0
    assert flat_leaf._phase_mult(S(35), 0.6, 1.0) == 1.0        # at K0: no tilt
    assert flat_leaf._phase_mult(S(35), -0.6, 1.0) == 1.0
    assert flat_leaf._phase_mult(S(70), 0.6, 1.0) == pytest.approx(1.6)   # early: up
    assert flat_leaf._phase_mult(S(0, in_hand=False), 0.6, 1.0) == pytest.approx(0.4)
    assert flat_leaf._phase_mult(S(70), -0.6, 1.0) == pytest.approx(0.4)  # mirrored
    assert flat_leaf._phase_mult(S(0, in_hand=False), -0.6, 1.0) == pytest.approx(1.6)
    # the norm DIVIDES
    assert (flat_leaf._phase_mult(S(70), 0.6, 2.0)
            == pytest.approx(flat_leaf._phase_mult(S(70), 0.6, 1.0) / 2.0))
    # and it is the fair_agent k, not len(deck): the in-hand tile counts
    assert flat_leaf._phase_mult(S(36, in_hand=True), 0.6, 1.0) != \
        flat_leaf._phase_mult(S(35, in_hand=False), 0.6, 1.0)


def test_knob_on_moves_the_leaf_in_the_expected_direction():
    """The phase multiplier scales ONLY the meeple differential, so the signed change
    vs the champion is `(f-1) * (curve[m_self] - curve[m_opp])` exactly."""
    moved = 0
    for st in STATES:
        for p in (0, 1):
            opp = 1 - p
            term = (flat_leaf._flat_curve_lookup(CURVE125, st.meeples[p])
                    - flat_leaf._flat_curve_lookup(CURVE125, st.meeples[opp]))
            base = flat_leaf.flat_virtual_score_v2_float(st, p, CHAMP)
            for cfg in (B_POS, B_NEG, B_NORM):
                f = flat_leaf._phase_mult(st, cfg.v29_phase_beta, cfg.v29_phase_norm)
                got = flat_leaf.flat_virtual_score_v2_float(st, p, cfg)
                assert got == pytest.approx(base + (f - 1.0) * term, abs=1e-9)
                if abs(got - base) > 1e-9:
                    moved += 1
    assert moved > 0, "the knob never bit — an inert knob would produce a false null"


# --- 4. the clip bounds fire -------------------------------------------------- #
def test_clip_bounds_fire_at_extreme_beta():
    class S:
        def __init__(self, k):
            self.deck = [None] * (k - 1)
            self.next_tile = object()

    # beta=3: k=71 -> 1+3*36/35 = 4.09 -> clipped to 2.0 ; k=1 -> 1-2.91 -> clipped to 0
    assert flat_leaf._phase_mult(S(71), 3.0, 1.0) == 2.0
    assert flat_leaf._phase_mult(S(1), 3.0, 1.0) == 0.0
    assert flat_leaf._phase_mult(S(71), -3.0, 1.0) == 0.0
    assert flat_leaf._phase_mult(S(1), -3.0, 1.0) == 2.0
    # the clip is applied BEFORE the norm divide (so norm can push it outside [0,2])
    assert flat_leaf._phase_mult(S(71), 3.0, 4.0) == 0.5
    # and it fires on real states at both deck ends
    fs = [flat_leaf._phase_mult(st, 3.0, 1.0) for st in STATES]
    assert max(fs) == 2.0 and min(fs) == 0.0


# --- 5. py == cy == rust with the knob ON ------------------------------------ #
def test_python_equals_cython_with_the_knob_on():
    for st in STATES:
        for p in (0, 1):
            for cfg in (B_POS, B_NEG, B_NORM, B_CLIP):
                assert (float(cy.flat_virtual_score_v2_cy_float(st, p, cfg, False))
                        == flat_leaf.flat_virtual_score_v2_float(st, p, cfg))
                assert (int(cy.flat_virtual_score_v2_cy(st, p, cfg, False))
                        == flat_leaf.flat_virtual_score_v2(st, p, cfg))


def test_leaf_config_rs_forwards_both_fields():
    """A dropped POSITIONAL kwarg in the Python->Rust translation would silently run
    an UNMODIFIED leaf on the Rust side, i.e. a guaranteed false null."""
    pytest.importorskip("carc_rs")
    from carcassonne_ai.rust_agent import leaf_config_rs

    for cfg, (wb, wn) in ((CHAMP, (0.0, 1.0)), (B_POS, (0.6, 1.0)),
                          (B_NEG, (-0.6, 1.0)), (B_NORM, (0.6, 1.0723))):
        r = repr(leaf_config_rs(cfg))
        assert f"v29_phase_beta: {wb}" in r, r
        assert f"v29_phase_norm: {wn}" in r, r


def test_python_equals_rust_with_the_knob_on():
    """Bit-exact on a replayed game. The full-corpus version is
    `scripts/rustport/reconcile_leaf.py --configs phase`."""
    carc_rs = pytest.importorskip("carc_rs")
    from carcassonne_ai.rust_agent import leaf_config_rs

    rcfgs = {n: leaf_config_rs(c) for n, c in
             (("champ", CHAMP), ("pos", B_POS), ("neg", B_NEG),
              ("norm", B_NORM), ("clip", B_CLIP))}
    pycfgs = {"champ": CHAMP, "pos": B_POS, "neg": B_NEG, "norm": B_NORM, "clip": B_CLIP}

    seed = 8091
    random.seed(seed)
    g = Game(enable_legal_moves_cache=True)
    b = g.get_init_board()
    ms = carc_rs.MirrorState.from_seed(str(seed))
    rng = random.Random(seed)
    checked = 0
    while g.get_game_ended(b, 0) == 0.0:
        for name, rc in rcfgs.items():
            for p in (0, 1):
                assert int(ms.leaf_value(p, rc)) == \
                    flat_leaf.flat_virtual_score_v2(b.state, p, pycfgs[name]), \
                    f"{name} int mismatch at k={fair_k_remaining(b.state)}"
                assert float(ms.leaf_value_float(p, rc)) == \
                    flat_leaf.flat_virtual_score_v2_float(b.state, p, pycfgs[name]), \
                    f"{name} float mismatch at k={fair_k_remaining(b.state)}"
        checked += 1
        a = int(rng.choice(np.flatnonzero(g.get_valid_moves(b)).tolist()))
        b, _ = g.get_next_state(b, a)
        ms.advance(a)
    assert checked > 60


# --- 6. the k_remaining definition of record --------------------------------- #
def test_k_remaining_matches_fair_agent_on_every_ply():
    """Including the MEEPLES phase, where `_bag_stats` deliberately DISAGREES (there
    `next_tile` is a stale ref to the just-placed tile). A silent substitution would
    shift the phase clock by one tile on every meeple ply."""
    from wingedsheep.carcassonne.objects.game_phase import GamePhase

    random.seed(8092)
    g = Game(enable_legal_moves_cache=True)
    b = g.get_init_board()
    rng = random.Random(8092)
    seen_meeple_phase = False
    disagreed_with_bag = 0
    while g.get_game_ended(b, 0) == 0.0:
        st = b.state
        assert flat_leaf._k_remaining(st) == fair_k_remaining(st)
        if st.phase == GamePhase.MEEPLES:
            seen_meeple_phase = True
            if st.next_tile is not None:
                # bag counts the deck only here; the phase clock counts the hand too
                disagreed_with_bag += 1
                assert flat_leaf._k_remaining(st) == len(st.deck) + 1
        a = int(rng.choice(np.flatnonzero(g.get_valid_moves(b)).tolist()))
        b, _ = g.get_next_state(b, a)
    assert seen_meeple_phase and disagreed_with_bag > 0


# --- 7. a stale .so cannot silently drop the knob ---------------------------- #
def test_cy_capability_flag_present_and_gates_dispatch(monkeypatch):
    assert cy.SUPPORTS_V29_PHASE is True
    # simulate a STALE build: the dispatcher must refuse the cy fast path, not
    # silently serve an unmodified leaf.
    monkeypatch.setattr(flat_leaf, "_CY_SUPPORTS_PHASE", False)
    monkeypatch.setattr(flat_leaf, "_CY_FLAT_V2", lambda *a, **k:
                        (_ for _ in ()).throw(AssertionError("stale cy leaf was used")))
    monkeypatch.setattr(flat_leaf, "_CY_FLAT_V2_FLOAT", lambda *a, **k:
                        (_ for _ in ()).throw(AssertionError("stale cy leaf was used")))
    for st in STATES[:8]:
        flat_leaf.flat_virtual_score_v2(st, 0, B_POS)
        flat_leaf.flat_virtual_score_v2_float(st, 0, B_POS)


def test_candidate_leaf_guard_rejects_a_phase_config_without_a_curve():
    import sys
    sys.path.insert(0, "scripts/classical_search")
    from c5_leaf_override import _assert_cy_float_path

    _assert_cy_float_path(B_POS)                      # the legal shape passes
    with pytest.raises(ValueError, match="requires v29_meeple_curve"):
        _assert_cy_float_path(dc.replace(B_POS, v29_meeple_curve=None))
    with pytest.raises(ValueError, match="non-zero"):
        _assert_cy_float_path(dc.replace(B_POS, v29_phase_norm=0.0))


# --- the object (engine) leaf path carries it too ---------------------------- #
def test_object_path_agrees_with_the_flat_path():
    """`leaf_v29._meeple_curve_term` is the object path's copy of the term; it must
    take the same early branch and the same multiplier."""
    from carcassonne_ai import leaf_v29

    for st in STATES[:20]:
        for p in (0, 1):
            opp = 1 - p
            plain = leaf_v29._meeple_curve_term(st, p, opp, CURVE125)
            assert plain == (flat_leaf._flat_curve_lookup(CURVE125, st.meeples[p])
                             - flat_leaf._flat_curve_lookup(CURVE125, st.meeples[opp]))
            for cfg in (B_POS, B_NEG, B_NORM):
                got = leaf_v29._meeple_curve_term(st, p, opp, CURVE125,
                                                  cfg.v29_phase_beta, cfg.v29_phase_norm)
                f = flat_leaf._phase_mult(st, cfg.v29_phase_beta, cfg.v29_phase_norm)
                assert got == f * plain
