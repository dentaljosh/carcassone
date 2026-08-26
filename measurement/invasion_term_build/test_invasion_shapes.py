"""INVASION-RISK TERM FAMILY — python fixtures driving the RUST leaf.

Spec: `SHAPES.md` next to this file. Implementation:
`rust/carc/carc-core/src/leaf/invasion.rs` (+ the config plumbing listed in
SHAPES.md §"Knob schema"). This family is RUST-ONLY by decision, so every fixture
here goes through `carc_rs.MirrorState`; the Python leaves are exercised only to
prove they FAIL CLOSED.

## Run

    CARCASSONNE_FIX_R9=1 \\
    PYTHONPATH=<shadow-dir>:<worktree>/src:<worktree>/engine \\
    .venv/bin/python -m pytest measurement/invasion_term_build/ -q

`<shadow-dir>` is an unpacked `carc_rs` wheel built from this tree
(`maturin build --release -m rust/carc/carc-py/Cargo.toml -o …`, then unzip) —
the phase-seam pattern, so the shared venv's site-packages is never overwritten
while other runs may be live. `CARCASSONNE_FIX_R9=1` must be in the ENVIRONMENT
before the process starts: the E4 `fixed_v1` archives were played under R9 and
the rust tile registry latches a `OnceLock`.

## Contracts

  1. GATE 1 — WEIGHT-0 IDENTITY. With every invasion weight 0.0 (and the two
     INERT shape-B knobs deliberately moved off their defaults), the rust leaf is
     BIT-identical to the champion leaf, on a random-playout corpus AND on real E4
     positions — and the rust champion leaf is itself bit-identical to the
     production Python flat leaf, so "the champion" is not a rust-side fiction.
  2. GATE 2 — DIRECTION ON REAL INVASION POSITIONS. Fixtures are the Stage A/B
     census's KNOWN INVASION PLIES (`stage_b_plies.jsonl`, the 51 rows with
     `notes.mech == "merge"`), replayed into the rust mirror at the recorded
     contest-onset ply. Each shape must move the leaf in its documented direction,
     and shape C must penalize the UNDEFENDED-MONSTER side specifically.
  3. GATE 3 — LEAF HASH. A nonzero weight produces a different leaf hash; an
     explicit 0.0 hashes AS the champion (documented and safe: it IS the champion
     leaf, bit-for-bit).
  4. FAIL-CLOSED. Both Python leaves raise on a nonzero weight (there is no
     flat_leaf and no cy mirror), and `rust_agent.leaf_config_rs` forwards the
     knobs as CONDITIONAL kwargs so a stale carc_rs serves default-off configs
     unchanged but raises TypeError on a nonzero weight.
"""
from __future__ import annotations

import dataclasses as dc
import random
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for _p in (REPO / "src", REPO / "engine", str(HERE)):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

carc_rs = pytest.importorskip("carc_rs", reason="build the wheel from this tree")

import e4_positions as e4  # noqa: E402

if not hasattr(carc_rs.MirrorState, "invasion_terms"):
    pytest.skip("carc_rs build predates the invasion-risk family (rebuild the wheel)",
                allow_module_level=True)

import numpy as np  # noqa: E402

from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.rust_agent import leaf_config_rs  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402

CURVE125 = (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25)
#: The champion leaf of record's flat-relevant knobs (governance/PRODUCTION.yaml).
CHAMP = dc.replace(DEFAULT_CONFIG, meeple_k=2.0, bonus_cap=8.0, opp_bonus_cap=8.0,
                   closure_p={1: 0.5, 2: 0.2, 3: 0.05}, v29_meeple_curve=CURVE125)
#: GATE 1's candidate: every WEIGHT 0.0, both INERT shape-B knobs moved.
OFF_BUT_MOVED = dc.replace(CHAMP, invasion_beta=0.0, invasion_alpha=0.0,
                           invasion_gamma=0.0, invasion_delta_farm=0.0,
                           invasion_alpha_cap=3.0, invasion_stub_max_tiles=5)
A_ON = dc.replace(CHAMP, invasion_beta=0.5)
B_ON = dc.replace(CHAMP, invasion_alpha=0.5)
C_ON = dc.replace(CHAMP, invasion_gamma=0.5)
D_ON = dc.replace(CHAMP, invasion_delta_farm=0.5)

RC_CHAMP = leaf_config_rs(CHAMP)
RC_OFF = leaf_config_rs(OFF_BUT_MOVED)
RC = {"A": leaf_config_rs(A_ON), "B": leaf_config_rs(B_ON),
      "C": leaf_config_rs(C_ON), "D": leaf_config_rs(D_ON)}


# =========================================================================
# corpora
# =========================================================================

def _random_corpus(seeds=("4242", "77", "31337"), max_plies=130, start=16, every=5):
    """Lockstep python `Game` + rust `MirrorState` random playouts, yielding
    `(label, board, mirror)` at sampled plies. The python board rides along so
    GATE 1 can also assert rust-champion == python-champion."""
    out = []
    for s in seeds:
        import random as _r
        g = Game(enable_legal_moves_cache=True)
        _r.seed(int(s))
        b = g.get_init_board()
        ms = carc_rs.MirrorState.from_seed(s)
        rng = random.Random(int(s) + 1)
        for ply in range(max_plies):
            if g.get_game_ended(b, 0) != 0.0:
                break
            if ply >= start and ply % every == 0:
                out.append((f"seed{s}/ply{ply}", b.state, ms.string_repr()))
                yield f"seed{s}/ply{ply}", b.state, ms
            a = int(rng.choice(np.flatnonzero(g.get_valid_moves(b)).tolist()))
            b, _ = g.get_next_state(b, a)
            ms.advance(a)


def _invasion_plies():
    """`(game, [plies])` for the census's KNOWN INVASION rows — the recorded
    contest-onset ply plus the graded ply itself."""
    by_game: dict[str, set[int]] = {}
    for r in e4.stage_b_rows("merge"):
        n = r["notes"] or {}
        plies = {int(r["ply"])}
        if n.get("contest_onset_ply") is not None:
            plies.add(int(n["contest_onset_ply"]))
        by_game.setdefault(r["game"], set()).update(plies)
    return sorted(by_game.items())


def _e4_corpus():
    """`(label, MirrorState)` at every known-invasion ply we can replay.

    An archive with no `rules_profile` stamp is a pre-`fixed_v1` build and is
    SKIPPED, not guessed at (the rules-epoch rule)."""
    if not e4.r9_ok():
        pytest.skip("CARCASSONNE_FIX_R9=1 must be exported before the process starts")
    n = 0
    for game, plies in _invasion_plies():
        try:
            arch = e4.archive(game)
        except FileNotFoundError:
            continue
        if not arch.get("rules_profile"):
            continue
        for ply, ms in e4.states_along(arch, plies):
            n += 1
            yield f"{game}@{ply}", ms
    if n == 0:
        pytest.skip("no replayable E4 invasion positions found")


# =========================================================================
# GATE 1 — weight-0 identity
# =========================================================================

def test_gate1_weight_zero_is_bit_identical_random_corpus():
    """Every invasion weight 0.0 (inert knobs MOVED) == the champion leaf, bit for
    bit — and the rust champion == the production python flat champion, so the
    baseline this gate pins is the real one."""
    n = 0
    for label, pystate, ms in _random_corpus():
        for p in (0, 1):
            champ = ms.leaf_value_float(p, RC_CHAMP)
            off = ms.leaf_value_float(p, RC_OFF)
            assert champ.hex() == off.hex(), f"{label} pov{p}: {champ} != {off}"
            assert ms.leaf_value(p, RC_CHAMP) == ms.leaf_value(p, RC_OFF)
            py = flat_leaf.flat_virtual_score_v2_float(pystate, p, CHAMP)
            assert py.hex() == champ.hex(), f"{label} pov{p}: rust != python champion"
            n += 1
    assert n >= 100, f"only {n} fixtures"


def test_gate1_weight_zero_is_bit_identical_on_e4_positions():
    """Same gate on the REAL invasion positions (a different rules epoch, a
    different board distribution, the same identity)."""
    n = 0
    for label, ms in _e4_corpus():
        for p in (0, 1):
            champ = ms.leaf_value_float(p, RC_CHAMP)
            off = ms.leaf_value_float(p, RC_OFF)
            assert champ.hex() == off.hex(), f"{label} pov{p}"
            assert ms.leaf_value(p, RC_CHAMP) == ms.leaf_value(p, RC_OFF)
            n += 1
    assert n >= 20, f"only {n} E4 fixtures"


# =========================================================================
# GATE 2 — direction, on the census's known invasion positions
# =========================================================================

def _expected_transfer(scan, reserve, player, kinds):
    """Recompute the shape-A/D differential in PYTHON from the rust scan dump —
    an independent reading of the same mechanism, so the assertion is not the
    implementation asserting itself."""
    opp = 1 - player
    tot = 0.0
    for c in scan:
        if c["kind"] not in kinds or c["holder"] < 0 or c["open_n"] < 1:
            continue
        if c["holder"] == opp and reserve[player] >= 1:
            tot += c["value"]
        elif c["holder"] == player and reserve[opp] >= 1:
            tot -= c["value"]
    return tot


def test_gate2_shape_a_transfers_contested_value_on_e4_invasions():
    """Shape A: the potential INVADER is credited the contestable value the
    holder is charged for. Antisymmetric, and equal to an independent python
    recomputation from the component scan."""
    fired = 0
    n = 0
    for label, ms in _e4_corpus():
        scan = ms.invasion_scan()
        reserve = ms.meeples()
        t0 = ms.invasion_terms(0, RC_CHAMP)["T_A"]
        t1 = ms.invasion_terms(1, RC_CHAMP)["T_A"]
        assert t0 == -t1, f"{label}: shape A is not antisymmetric"
        for p in (0, 1):
            want = _expected_transfer(scan, reserve, p, {"city", "road", "farm"})
            got = ms.invasion_terms(p, RC_CHAMP)["T_A"]
            assert got == pytest.approx(want), f"{label} pov{p}"
        if t0 != 0.0:
            fired += 1
        n += 1
    assert fired >= 8, f"shape A fired on only {fired}/{n} known invasion positions"


def test_gate2_shape_d_prices_the_contested_farm_as_a_swing():
    """Shape D on the measured mechanism (late decisive farm captures): the farm
    HOLDER is charged, the potential invader credited, farms only."""
    fired = 0
    holder_charged = 0
    for label, ms in _e4_corpus():
        scan = ms.invasion_scan()
        reserve = ms.meeples()
        for p in (0, 1):
            want = _expected_transfer(scan, reserve, p, {"farm"})
            got = ms.invasion_terms(p, RC_CHAMP)["T_D"]
            assert got == pytest.approx(want), f"{label} pov{p}"
        t0 = ms.invasion_terms(0, RC_CHAMP)["T_D"]
        assert t0 == -ms.invasion_terms(1, RC_CHAMP)["T_D"]
        if t0 != 0.0:
            fired += 1
        # the DIRECTIONAL claim: every contestable farm charges its holder and
        # credits the other side, so the sign follows the net holder of value
        for c in scan:
            if c["kind"] != "farm" or c["holder"] < 0 or c["open_n"] < 1 or c["value"] <= 0:
                continue
            h = c["holder"]
            if reserve[1 - h] >= 1:
                holder_charged += 1
    assert fired >= 5, f"shape D fired on only {fired} known invasion positions"
    assert holder_charged >= 5, "no contestable, VALUED farm in the invasion corpus"


def test_gate2_shape_b_promotes_the_stub_claim_hand_built():
    """The mechanism in isolation, on a hand-built board: p1 holds a 2-tile road,
    p0 holds a 1-TILE STUB, and both have an edge into the SAME empty cell — the
    merge move the champion leaf demotes.

    Shape B credits the stub owner with the target's value; the champion leaf does
    not see it at all. Exact arithmetic, not a direction."""
    R, C = 10, 10
    cells = [(R, C - 2, "straight_road", 1), (R, C - 1, "straight_road", 1),
             (R, C + 1, "straight_road", 1)]                      # (R, C) left EMPTY
    meeples = [(1, R, C - 2, "left", "normal"), (0, R, C + 1, "right", "normal")]
    ms = carc_rs.MirrorState.from_seed("1")
    ms.set_board(cells)
    ms.set_meeples(meeples)

    scan = {(c["kind"], c["holder"]): c for c in ms.invasion_scan()}
    stub, target = scan[("road", 0)], scan[("road", 1)]
    assert (stub["tiles"], stub["value"]) == (1, 1.0)
    assert (target["tiles"], target["value"]) == (2, 2.0)

    # offense only: the stub owner is credited the TARGET's value; the target's
    # owner gets nothing (their feature is not a stub beside a bigger one).
    assert ms.invasion_terms(0, RC_CHAMP)["T_B"] == 2.0
    assert ms.invasion_terms(1, RC_CHAMP)["T_B"] == 0.0
    # ... and the leaf actually MOVES for the stub owner, by exactly alpha * T_B
    base0 = ms.leaf_value_float(0, RC_CHAMP)
    assert ms.leaf_value_float(0, RC["B"]) - base0 == pytest.approx(0.5 * 2.0)
    assert ms.leaf_value_float(1, RC["B"]) == ms.leaf_value_float(1, RC_CHAMP)

    # the cap is a cap: at 1.0 the pair contributes a count, not a value
    capped = leaf_config_rs(dc.replace(B_ON, invasion_alpha_cap=1.0))
    assert ms.invasion_terms(0, capped)["T_B"] == 1.0
    # a stub threshold BELOW the stub's size disqualifies it
    narrow = leaf_config_rs(dc.replace(B_ON, invasion_stub_max_tiles=1,
                                       invasion_alpha_cap=0.0))
    assert ms.invasion_terms(0, narrow)["T_B"] == 2.0     # 1 tile <= 1: still a stub
    # and shape A sees the same board as a net +1 for the stub owner
    assert ms.invasion_terms(0, RC_CHAMP)["T_A"] == 1.0


def test_gate2_shape_b_fires_on_the_census_invasion_positions():
    """The same shape on the REAL positions the census flagged as deliberate
    invasions: non-negative everywhere, strictly positive on most of them, and it
    can only RAISE the leaf (offense only)."""
    fired = 0
    n = 0
    for label, ms in _e4_corpus():
        n += 1
        hit = False
        for p in (0, 1):
            t = ms.invasion_terms(p, RC_CHAMP)["T_B"]
            assert t >= 0.0, f"{label} pov{p}: T_B {t} < 0"
            moved = ms.leaf_value_float(p, RC["B"]) - ms.leaf_value_float(p, RC_CHAMP)
            assert moved == pytest.approx(0.5 * t), f"{label} pov{p}"
            assert moved >= 0.0
            hit = hit or t > 0
        fired += bool(hit)
    assert fired >= n // 2, f"shape B fired on only {fired}/{n} invasion positions"


def _monster(scan, player, min_tiles=4, min_open=2):
    """The UNDEFENDED MONSTERS `player` holds — large, still-open claimed
    components. The champion's measured habit (Stage A: farm-zeroed 9/50)."""
    return [c for c in scan if c["holder"] == player and c["tiles"] >= min_tiles
            and c["open_n"] >= min_open]


def _c_contrib(c):
    """One component's charge under shape C — `frac * V`, the python reading of
    the rust formula."""
    return (c["open_n"] / c["edges"]) * c["value"] if c["edges"] else 0.0


def test_gate2_shape_c_charges_the_open_perimeter_and_only_lowers_the_leaf():
    """Shape C is DEFENSE ONLY on the real invasion positions: `T_C >= 0`, the leaf
    moves by EXACTLY `-gamma * T_C`, never up, and the charge is the sum of the
    side's own components' `frac * V`."""
    n = charged = 0
    for label, ms in _e4_corpus():
        n += 1
        scan = ms.invasion_scan()
        reserve = ms.meeples()
        for p in (0, 1):
            t = ms.invasion_terms(p, RC_CHAMP)["T_C"]
            assert t >= 0.0, f"{label} pov{p}: T_C {t} < 0"
            moved = ms.leaf_value_float(p, RC["C"]) - ms.leaf_value_float(p, RC_CHAMP)
            assert moved == pytest.approx(-0.5 * t), f"{label} pov{p}"
            assert moved <= 0.0, f"{label} pov{p}: shape C RAISED the leaf"
            # an independent python recomputation off the scan dump
            want = (sum(_c_contrib(c) for c in scan if c["holder"] == p)
                    if reserve[1 - p] >= 1 else 0.0)
            assert t == pytest.approx(want), f"{label} pov{p}"
            charged += t > 0.0
    assert charged >= n, f"shape C was silent too often ({charged} charges over {n} positions)"


def test_gate2_shape_c_penalizes_the_undefended_monster():
    """GATE 2's defence half, stated the way the term is actually true.

    On the census's invasion positions, wherever a side holds an UNDEFENDED
    MONSTER (a claimed component of >= 4 tiles with >= 2 open board cells and real
    points on it) while the other side still has a meeple to invade with, that
    monster carries a STRICTLY POSITIVE charge inside its holder's `T_C`.

    ⚠️ WHAT IS **NOT** ASSERTED, AND MUST NOT BE (see SHAPES.md §"Shape C — the
    normalisation caveat"). `frac = open_n / total_edges` makes the charge a RATE
    times a value, and a big city has proportionally MORE edges, so shape C does
    NOT rank a large open city above a small fully-open feature: on this corpus the
    side-aggregate `T_C(monster holder) > T_C(other)` is FALSE in 8 of 23 one-sided
    cases. That is a property of the shape as specified, measured here so the
    screening prereg reads it correctly — not a bug, and not something to paper
    over with a stronger assertion."""
    checked = 0
    for label, ms in _e4_corpus():
        scan = ms.invasion_scan()
        reserve = ms.meeples()
        t = {p: ms.invasion_terms(p, RC_CHAMP)["T_C"] for p in (0, 1)}
        for p in (0, 1):
            if reserve[1 - p] < 1:
                # BY DESIGN: a perimeter nobody can walk through is not a
                # liability, so the term is silent for that side.
                assert t[p] == 0.0, label
                continue
            for c in _monster(scan, p):
                if c["value"] <= 0.0:
                    continue          # an unfinished-city-only field pays nothing yet
                own = _c_contrib(c)
                assert own > 0.0, f"{label}: monster {c} carries no charge"
                assert t[p] >= own - 1e-9, f"{label}: monster charge not inside T_C"
                checked += 1
    assert checked >= 5, f"only {checked} undefended monsters in the corpus"


def test_gate2_shape_c_perimeter_pin_hand_built():
    """The mechanism in isolation: two boards that differ ONLY in whether p0's own
    road still has a second open board cell. Closing that edge HALVES p0's charge
    and leaves p1's untouched — the "stop building undefended monsters" gradient,
    pinned arithmetically."""
    R, C = 10, 10
    base = [(R, C - 2, "straight_road", 1), (R, C - 1, "straight_road", 1),
            (R, C + 1, "straight_road", 1)]
    meeples = [(1, R, C - 2, "left", "normal"), (0, R, C + 1, "right", "normal")]

    def build(cells):
        ms = carc_rs.MirrorState.from_seed("1")
        ms.set_board(cells)
        ms.set_meeples(meeples)
        return ms

    wide = build(base)                                   # p0 road: 2 open cells / 2 edges
    capped = build(base + [(R, C + 2, "chapel", 0)])     # ... one of them filled in

    assert wide.invasion_terms(0, RC_CHAMP)["T_C"] == 1.0
    assert capped.invasion_terms(0, RC_CHAMP)["T_C"] == 0.5
    # the opponent's own exposure is untouched by p0 tidying up p0's perimeter
    assert wide.invasion_terms(1, RC_CHAMP)["T_C"] == capped.invasion_terms(1, RC_CHAMP)["T_C"]
    # and the leaf follows, by exactly -gamma * T_C
    for ms, want in ((wide, 1.0), (capped, 0.5)):
        moved = ms.leaf_value_float(0, RC["C"]) - ms.leaf_value_float(0, RC_CHAMP)
        assert moved == pytest.approx(-0.5 * want)


# =========================================================================
# GATE 3 — leaf hash
# =========================================================================

def test_gate3_leaf_hash_moves_only_for_a_nonzero_weight():
    """The a36d2e15 dialect drops a field WHILE IT HOLDS ITS DEFAULT, so:

      * the champion's hash recomputes UNCHANGED across the six additive fields;
      * an explicit `{"invasion_beta": 0.0}` hashes AS the champion — documented
        and SAFE, because it IS the champion leaf bit-for-bit (the hash names the
        leaf FUNCTION, not the JSON text);
      * any nonzero weight is a different leaf and shifts the hash;
      * ⚠️ a MOVED INERT knob (`invasion_alpha_cap` / `invasion_stub_max_tiles`)
        with all weights 0.0 ALSO shifts the hash while the leaf is unchanged —
        the same known, accepted asymmetry the open-city thresholds carry.
    """
    sys.path.insert(0, str(REPO / "scripts" / "classical_search"))
    import c5_leaf_override as ovr

    champ_hash = ovr._leaf_hash(DEFAULT_CONFIG)
    assert ovr._leaf_hash(ovr._load_cand_leaf_cfg('{"invasion_beta": 0.0}')) == champ_hash
    assert ovr._leaf_hash(ovr._load_cand_leaf_cfg(
        '{"invasion_beta": 0.0, "invasion_alpha": 0.0, "invasion_gamma": 0.0,'
        ' "invasion_delta_farm": 0.0}')) == champ_hash
    for spec in ('{"invasion_beta": 0.5}', '{"invasion_alpha": 0.5}',
                 '{"invasion_gamma": 0.5}', '{"invasion_delta_farm": 0.5}'):
        assert ovr._leaf_hash(ovr._load_cand_leaf_cfg(spec)) != champ_hash, spec
    # the documented inert-knob asymmetry, asserted so it cannot surprise anyone
    assert ovr._leaf_hash(ovr._load_cand_leaf_cfg(
        '{"invasion_alpha_cap": 3.0}')) != champ_hash


def test_cand_leaf_json_round_trips_and_guards(capsys):
    """`--cand-leaf-json` parses the flat knob schema, WARNS that the family is
    rust-only, and rejects a nonsense threshold."""
    sys.path.insert(0, str(REPO / "scripts" / "classical_search"))
    import c5_leaf_override as ovr

    cfg = ovr._load_cand_leaf_cfg(
        '{"invasion_beta": 0.25, "invasion_alpha": 0.5, "invasion_alpha_cap": 6.0,'
        ' "invasion_stub_max_tiles": 2, "invasion_gamma": 0.0,'
        ' "invasion_delta_farm": 0.0}')
    assert (cfg.invasion_beta, cfg.invasion_alpha, cfg.invasion_alpha_cap) == (0.25, 0.5, 6.0)
    ovr._assert_cy_float_path(cfg)
    err = capsys.readouterr().err
    assert "invasion-risk family set" in err and "RUST leaf ONLY" in err
    with pytest.raises(ValueError, match="invasion_alpha_cap"):
        ovr._assert_cy_float_path(ovr._load_cand_leaf_cfg(
            '{"invasion_beta": 0.5, "invasion_alpha_cap": -1.0}'))
    with pytest.raises(ValueError, match="invasion_stub_max_tiles"):
        ovr._assert_cy_float_path(ovr._load_cand_leaf_cfg(
            '{"invasion_alpha": 0.5, "invasion_stub_max_tiles": 0}'))
    with pytest.raises(ValueError, match="unknown LeafConfig field"):
        ovr._load_cand_leaf_cfg('{"invasion_bета": 0.5}')


# =========================================================================
# FAIL-CLOSED
# =========================================================================

def test_both_python_leaves_fail_closed_on_a_nonzero_weight():
    """There is no flat_leaf and no cy mirror. Serving an invasion-blind Python
    leaf would read as 'the term is worth nothing' instead of 'it never ran', so
    BOTH Python routes raise."""
    from carcassonne_ai.virtual_score_v2 import virtual_score_v2

    g = Game(enable_legal_moves_cache=True)
    b = g.get_init_board()
    rng = random.Random(5)
    for _ in range(30):
        b, _ = g.get_next_state(b, int(rng.choice(
            np.flatnonzero(g.get_valid_moves(b)).tolist())))
    # sanity: the OFF config is served normally by both routes
    assert isinstance(flat_leaf.flat_virtual_score_v2(b.state, 0, OFF_BUT_MOVED), int)
    for cfg in (A_ON, B_ON, C_ON, D_ON):
        with pytest.raises(NotImplementedError, match="RUST leaf"):
            flat_leaf.flat_virtual_score_v2(b.state, 0, cfg)
        with pytest.raises(NotImplementedError, match="RUST leaf"):
            flat_leaf.flat_virtual_score_v2_float(b.state, 0, cfg)
        with pytest.raises(NotImplementedError, match="RUST leaf"):
            virtual_score_v2(b.state, 0, cfg)


def test_leaf_config_rs_forwards_the_knobs_conditionally():
    """A carc_rs build predating the family must keep serving every default-off
    (champion) config unchanged, and must raise TypeError on a nonzero weight —
    fail-closed loud, never a silently invasion-blind leaf."""
    import inspect

    class _Spy:
        def __init__(self):
            self.kwargs = None

        def LeafConfigRs(self, *a, **kw):     # noqa: N802 — mirrors the pyo3 name
            self.kwargs = kw
            return object()

    import carcassonne_ai.rust_agent as ra

    src = inspect.getsource(ra.leaf_config_rs)
    assert "**invasion" in src

    spy = _Spy()
    saved = sys.modules.get("carc_rs")
    sys.modules["carc_rs"] = spy
    try:
        ra.leaf_config_rs(CHAMP)
        assert not any(k.startswith("invasion_") for k in spy.kwargs), spy.kwargs
        ra.leaf_config_rs(OFF_BUT_MOVED)
        assert not any(k.startswith("invasion_") for k in spy.kwargs), (
            "an all-zero-weight config must forward NOTHING, so a stale wheel still "
            "serves it")
        ra.leaf_config_rs(dc.replace(A_ON, invasion_delta_farm=0.25))
        assert spy.kwargs["invasion_beta"] == 0.5
        assert spy.kwargs["invasion_delta_farm"] == 0.25
        assert "invasion_alpha_cap" not in spy.kwargs      # inert, alpha == 0.0
        ra.leaf_config_rs(dc.replace(B_ON, invasion_alpha_cap=6.0,
                                     invasion_stub_max_tiles=3))
        assert spy.kwargs["invasion_alpha_cap"] == 6.0
        assert spy.kwargs["invasion_stub_max_tiles"] == 3
    finally:
        if saved is not None:
            sys.modules["carc_rs"] = saved
        else:
            del sys.modules["carc_rs"]


def test_rust_leaf_terms_exposes_the_four_shapes():
    """The per-term breakdown carries each raw T, and it is 0.0 while that shape's
    weight is off (the term is never even computed then)."""
    ms = carc_rs.MirrorState.from_seed("4242")
    g = Game(enable_legal_moves_cache=True)
    import random as _r
    _r.seed(4242)
    b = g.get_init_board()
    rng = random.Random(4243)
    for _ in range(60):
        a = int(rng.choice(np.flatnonzero(g.get_valid_moves(b)).tolist()))
        b, _ = g.get_next_state(b, a)
        ms.advance(a)
    off = ms.leaf_terms(0, RC_CHAMP)
    for k in ("invasion_a", "invasion_b", "invasion_c", "invasion_d"):
        assert off[k] == 0.0, k
    raw = ms.invasion_terms(0, RC_CHAMP)
    assert ms.leaf_terms(0, RC["A"])["invasion_a"] == raw["T_A"]
    assert ms.leaf_terms(0, RC["B"])["invasion_b"] == raw["T_B"]
    assert ms.leaf_terms(0, RC["C"])["invasion_c"] == raw["T_C"]
    assert ms.leaf_terms(0, RC["D"])["invasion_d"] == raw["T_D"]
    # a shape's weight moves ONLY its own term
    assert ms.leaf_terms(0, RC["A"])["invasion_b"] == 0.0
    assert ms.leaf_terms(0, RC["C"])["invasion_d"] == 0.0
