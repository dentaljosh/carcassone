"""J-RULES AS POLICY PRIORS (surface B) — contract tests.

Design of record: measurement/jrules_priors_20260814/DESIGN.md.
Production path: carc_core::search under SearchConfig.jrules_prior_dose != 0
(RUST-ONLY; the python search path fail-louds). Reference mirror:
carcassonne_ai.jrules_priors — what the parity tests here compare bit-for-bit
against carc_rs.MirrorState.jrules_prior_probe.

⚠️ PER-BOX REBUILD FOOTGUN, STATED LOUDLY: the rust-gated tests below SKIP —
they do not fail — when the installed `carc_rs` wheel predates surface B
(no `jrules_prior_probe` / no `jrules_prior_dose` kwarg). A skip on a box that
is about to run a cell means THE CELL WOULD SILENTLY RUN CHAMPION-VS-CHAMPION
IF THE PLUMBING WERE NOT FAIL-CLOSED — rebuild the wheel on that box
(`maturin build --release` in rust/carc/carc-py + reinstall) before launching
anything. The fail-closed guard itself (stale wheel + nonzero dose ⇒
TypeError) is tested WITHOUT the new wheel.
"""

from __future__ import annotations

import math
import random
import struct
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO / "src", REPO / "engine"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai import jrules_priors as jp  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import (  # noqa: E402
    HeuristicPriorConfig,
    make_heuristic_prior_evaluator,
)
from carcassonne_ai.joshua_bot import PRESETS  # noqa: E402

# The static bundle's fixture builder is deliberately REUSED (same states, same
# Decomp shape) so the two surfaces' behavioural tests stay comparable.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_jrules_term as tjt  # noqa: E402

_mk = tjt._mk
N = tjt.N
FARMER = tjt.FARMER


def _bits(x: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


def _clock(**kw) -> jp.JrPriorClock:
    """A hand-built decision-node clock for the synthetic behavioural tests
    (the real constructor is exercised by the replay parity test)."""
    base = dict(k=40, late_frac=0.0, bag_farm_frac=1.0, urg=1.0, opp_reserve=4,
                parent_base=0.0, abs_margin=0.0, parent_unclaimed=0.0)
    base.update(kw)
    return jp.JrPriorClock(**base)


def _T(st, d, mask=31, clock=None, player=0, child_base=0.0):
    return jp.jrules_prior_term(st, player, d, mask,
                                clock if clock is not None else _clock(),
                                child_base)


# --------------------------------------------------------------------------- #
# 1. constants are the bot's, not new tunables                                 #
# --------------------------------------------------------------------------- #
def test_constants_match_joshua_bot():
    p = PRESETS["current"]
    assert jp.JP_J2_APPROACH_W == p.j2_approach_w
    assert jp.JP_J2_PLAN_HORIZON == p.j2_plan_horizon
    assert jp.JP_J2_REACH_THRESHOLD == p.j2_reach_threshold
    assert jp.JP_J2_ENTRY_CELLS_CAP == p.j2_entry_cells_cap
    assert jp.JP_J5_THROWAWAY_GAIN == p.j5_throwaway_gain
    assert jp.JP_J5_WEIGHT == p.j5_weight
    # The shared _JR_* block is pinned exhaustively by test_jrules_term; spot-pin
    # the ones this surface reads so a drift can't hide behind that suite.
    assert flat_leaf._JR_J1_JOIN_BONUS == p.j1_join_bonus
    assert flat_leaf._JR_J2_MIN_FARM_VALUE == p.j2_min_farm_value
    assert flat_leaf._JR_J6_ROAD_JOIN_MIN_LEN == p.j6_road_join_min_len
    assert flat_leaf._JR_J8_PIVOTAL_SWING == p.j8_pivotal_swing


# --------------------------------------------------------------------------- #
# 2. the RESTORED predicates — what surface A could not express                #
# --------------------------------------------------------------------------- #
def test_j1_requires_his_presence_now():
    """The static surface credits HOLDING a share (it had to). The prior
    surface restores the bot's join predicate: my solo meeple on my own big
    open city pays NOTHING; the 1-1 join into HIS city pays the bonus."""
    solo, d1 = _mk(cities={7: (False, 3, 8)}, meeples=[(0, "city", 7, N)])
    assert _T(solo, d1, mask=flat_leaf.JR_J1) == 0.0
    join, d2 = _mk(cities={7: (False, 3, 8)},
                   meeples=[(0, "city", 7, N), (1, "city", 7, N)])
    assert _T(join, d2, mask=flat_leaf.JR_J1) == flat_leaf._JR_J1_JOIN_BONUS


def test_j2_realized_steal_requires_his_presence_now():
    solo, d1 = _mk(farms={3: (2, (11,))}, meeples=[(0, "farm", 3, FARMER)])
    assert _T(solo, d1, mask=flat_leaf.JR_J2) == 0.0
    tie, d2 = _mk(farms={3: (2, (11,))}, cities={11: (False, 1, 4)},
                  meeples=[(0, "farm", 3, FARMER), (1, "farm", 3, FARMER)])
    # value = 3*2 finished + pot(1 closable unfinished adj city) = 6 + 3 >= bar
    # (k must be <= _JR_J2_CITY_COUNT_FROM_K for the potential to count — the
    # J10-"current" late-game city count)
    got = _T(tie, d2, mask=flat_leaf.JR_J2, clock=_clock(k=30))
    assert got == flat_leaf._JR_J2_STEAL_W * 3.0


def test_j6_road_join_requires_his_presence_now():
    solo, d1 = _mk(roads={5: (False, 6)}, meeples=[(0, "road", 5, N)])
    # solo long road: anchor bonus only, no join
    assert _T(solo, d1, mask=flat_leaf.JR_J6) == flat_leaf._JR_J6_ANCHOR_BONUS
    join, d2 = _mk(roads={5: (False, 6)},
                   meeples=[(0, "road", 5, N), (1, "road", 5, N)])
    # 1-1 tie on his long road: join bonus, no anchor (tie is not a lead)
    assert _T(join, d2, mask=flat_leaf.JR_J6) == flat_leaf._JR_J6_ROAD_JOIN_BONUS


# --------------------------------------------------------------------------- #
# 3. J2a — the planning clause, newly expressible                              #
# --------------------------------------------------------------------------- #
def _approach_state():
    """His valuable field (I am not on it), with one enterable cell."""
    st, d = _mk(farms={3: (2, ())}, meeples=[(1, "farm", 3, FARMER)])
    # the field cell (row 0, col 0) with empty neighbours -> entry cells exist
    d.farm_root_keys[3] = {(0, 0, 0)}
    return st, d


def test_j2a_approach_fires_with_reach():
    st, d = _approach_state()
    got = _T(st, d, mask=flat_leaf.JR_J2, clock=_clock(k=40, bag_farm_frac=1.0))
    # reach: entry cells (0,1),(1,0) -> 2; per_turn = 1.0*min(2,3)/3 = 2/3;
    # 1-(1/3)^3; value = 6.0; approach_w * value * reach
    reach = 1.0 - (1.0 - 2.0 / 3.0) ** 3
    assert got == pytest.approx(jp.JP_J2_APPROACH_W * 6.0 * reach)
    assert got > 0.0


def test_j2a_approach_needs_turns_reach_and_entries():
    st, d = _approach_state()
    # bag empty of farm tiles -> reach 0 -> below threshold -> no term
    assert _T(st, d, mask=flat_leaf.JR_J2, clock=_clock(bag_farm_frac=0.0)) == 0.0
    # no tiles left for me -> my_turns < 1 -> no term
    assert _T(st, d, mask=flat_leaf.JR_J2, clock=_clock(k=1)) == 0.0
    # no way in -> no term
    d.farm_root_keys[3] = set()
    assert _T(st, d, mask=flat_leaf.JR_J2, clock=_clock()) == 0.0


# --------------------------------------------------------------------------- #
# 4. J5 — the bot's before/after dump, newly expressible                       #
# --------------------------------------------------------------------------- #
def test_j5_dump_charges_only_throwaways_that_feed():
    # child board carries an unclaimed 9-tile city (value 9 > floor 4)
    st, d = _mk(cities={7: (False, 2, 9)})
    fed_clock = _clock(parent_unclaimed=0.0, parent_base=0.0, opp_reserve=3)
    fed = 9.0 - flat_leaf._JR_J5_VALUE_FLOOR
    # throwaway (child_base == parent_base) that feeds 5 points of unclaimed
    assert _T(st, d, mask=flat_leaf.JR_J5, clock=fed_clock, child_base=0.0) \
        == -jp.JP_J5_WEIGHT * fed
    # the same move gaining > j5_throwaway_gain is NOT a throwaway
    assert _T(st, d, mask=flat_leaf.JR_J5, clock=fed_clock, child_base=2.0) == 0.0
    # he has no meeple to grab it with -> no charge
    assert _T(st, d, mask=flat_leaf.JR_J5,
              clock=_clock(opp_reserve=0), child_base=0.0) == 0.0
    # feeding NEGATIVE (claiming reduces unclaimed) is never credited
    assert _T(st, d, mask=flat_leaf.JR_J5,
              clock=_clock(parent_unclaimed=99.0), child_base=0.0) == 0.0


# --------------------------------------------------------------------------- #
# 5. J8 — margin at the decision node                                          #
# --------------------------------------------------------------------------- #
def test_j8_reads_the_margin_from_the_clock():
    st, d = _mk(cities={7: (False, 1, 8)},
                meeples=[(0, "city", 7, N), (0, "city", 7, N)])
    live = _T(st, d, mask=flat_leaf.JR_J8, clock=_clock(abs_margin=0.0))
    assert live == flat_leaf._JR_J8_OVERCOMMIT_BONUS * \
        min(1.0, 8.0 / flat_leaf._JR_J8_VALUE_NORM)
    # a swing smaller than the decision-node margin is not pivotal
    dead = _T(st, d, mask=flat_leaf.JR_J8, clock=_clock(abs_margin=50.0))
    assert dead == 0.0


# --------------------------------------------------------------------------- #
# 6. mask ablation localizes                                                   #
# --------------------------------------------------------------------------- #
def test_mask_bits_isolate_rules():
    st, d = _mk(cities={7: (False, 3, 8)},
                roads={5: (False, 6)},
                meeples=[(0, "city", 7, N), (1, "city", 7, N),
                         (0, "road", 5, N)])
    full = _T(st, d, mask=31)
    parts = [
        _T(st, d, mask=flat_leaf.JR_J1),
        _T(st, d, mask=flat_leaf.JR_J2),
        _T(st, d, mask=flat_leaf.JR_J5),
        _T(st, d, mask=flat_leaf.JR_J6),
        _T(st, d, mask=flat_leaf.JR_J8),
    ]
    assert full == pytest.approx(math.fsum(parts))
    assert parts[0] > 0.0 and parts[3] > 0.0


# --------------------------------------------------------------------------- #
# 7. plumbing: fail-loud python path, validation, conditional forwarding       #
# --------------------------------------------------------------------------- #
def test_python_search_path_fails_loud_on_a_set_dose():
    cfg = HeuristicPriorConfig(jrules_prior_dose=0.25)
    with pytest.raises(NotImplementedError, match="rust-only"):
        # the guard fires before `game` is ever touched — passing None proves it
        make_heuristic_prior_evaluator(None, cfg)


def test_config_validation_rejects_typos():
    with pytest.raises(ValueError):
        HeuristicPriorConfig(jrules_prior_scope="both")
    with pytest.raises(ValueError):
        HeuristicPriorConfig(jrules_prior_mask=0)
    with pytest.raises(ValueError):
        HeuristicPriorConfig(jrules_prior_mask=64)
    # dose 0 with a moved mask/scope is legal (it is still the champion)
    HeuristicPriorConfig(jrules_prior_mask=27, jrules_prior_scope="own")


def test_manifest_carries_the_resolved_dose():
    m = HeuristicPriorConfig(jrules_prior_dose=0.25,
                             jrules_prior_mask=27,
                             jrules_prior_scope="own").as_manifest()
    assert m["jrules_prior_dose"] == 0.25
    assert m["jrules_prior_mask"] == 27
    assert m["jrules_prior_scope"] == "own"
    # and the default manifest says so too (the wiring gate reads THIS field)
    m0 = HeuristicPriorConfig().as_manifest()
    assert m0["jrules_prior_dose"] == 0.0


def test_default_config_forwards_no_jr_kwargs(monkeypatch):
    """A default-off config must not mention the kwargs at all, so a stale
    carc_rs keeps serving every champion config (the F7b dropped-kwarg rule)."""
    captured = {}

    class _FakeCfg:
        def __init__(self, *a, **kw):
            captured.update(kw)

    fake = SimpleNamespace(SearchConfigRs=_FakeCfg,
                           LeafConfigRs=lambda *a, **kw: None)
    monkeypatch.setitem(sys.modules, "carc_rs", fake)
    from carcassonne_ai import rust_agent
    rust_agent.search_config_rs(HeuristicPriorConfig(), sims=8)
    assert not any(k.startswith("jrules_prior") for k in captured)
    captured.clear()
    rust_agent.search_config_rs(
        HeuristicPriorConfig(jrules_prior_dose=0.25, jrules_prior_scope="own"),
        sims=8)
    assert captured["jrules_prior_dose"] == 0.25
    assert captured["jrules_prior_mask"] == 31
    assert captured["jrules_prior_scope"] == "own"


# --------------------------------------------------------------------------- #
# 8. rust-gated: parity + search contracts                                     #
# --------------------------------------------------------------------------- #
def _carc_rs_with_surface_b():
    carc_rs = pytest.importorskip("carc_rs")
    if not hasattr(carc_rs.MirrorState, "jrules_prior_probe"):
        pytest.skip(
            "carc_rs wheel PREDATES J-rules priors surface B — the per-box "
            "rebuild footgun. Rebuild before any cell on this box: "
            "`maturin build --release` in rust/carc/carc-py + reinstall. "
            "(The stale-wheel path itself is FAIL-CLOSED: a nonzero "
            "jrules_prior_dose raises TypeError in search_config_rs.)")
    return carc_rs


def _lockstep(seed: int, carc_rs, probe_plies):
    """Replay one seeded game in BOTH engines; yield (b, game, mirror) at the
    probe plies. Deck contract == MirrorState.from_seed (`random.seed`)."""
    random.seed(seed)
    g = Game(enable_legal_moves_cache=True)
    b = g.get_init_board()
    m = carc_rs.MirrorState.from_seed(str(seed))
    rng = random.Random(9_000_000 + seed)
    import numpy as np
    for ply in range(max(probe_plies) + 1):
        legal_py = np.flatnonzero(g.get_valid_moves(b)).tolist()
        legal_rs = sorted(m.legal_actions())
        assert legal_py == legal_rs, f"legal-mask divergence at ply {ply}"
        if ply in probe_plies and len(legal_py) >= 2:
            yield ply, b, g, m
        a = int(rng.choice(legal_py))
        b, _ = g.get_next_state(b, a)
        m.advance(a)


@pytest.mark.parametrize("seed", [28000000001, 28000000007])
@pytest.mark.parametrize("mask", [31, 1, 27])
def test_rust_python_term_parity_on_replayed_games(seed, mask):
    """The parity gate for surface B: rust probe vs the python reference
    mirror, BIT-FOR-BIT, on real replayed positions — clock fields and every
    per-child term."""
    carc_rs = _carc_rs_with_surface_b()
    probe_plies = {20, 30, 40, 50, 60}
    compared = 0
    for _ply, b, g, m in _lockstep(seed, carc_rs, probe_plies):
        probe = m.jrules_prior_probe(mask=mask)
        mover = probe["mover"]
        assert mover == b.state.current_player
        d_parent = flat_leaf.decompose(b.state)
        clock = jp.jr_prior_clock(b.state, mover, d_parent)
        assert _bits(clock.late_frac) == probe["late_frac_bits"]
        assert _bits(clock.bag_farm_frac) == probe["bag_farm_frac_bits"]
        assert _bits(clock.urg) == probe["urg_bits"]
        assert _bits(clock.parent_unclaimed) == probe["parent_unclaimed_bits"]
        assert clock.k == probe["k"]
        assert clock.opp_reserve == probe["opp_reserve"]
        assert _bits(clock.parent_base) == _bits(probe["parent_base"])
        for (a, _t, t_bits, base_rs) in probe["children"]:
            nb, _ = g.get_next_state(b, int(a))
            d_child = flat_leaf.decompose(nb.state)
            base_py = float(flat_leaf.flat_base_score(nb.state, mover, d_child))
            assert _bits(base_py) == _bits(base_rs), (seed, _ply, a)
            t_py = jp.jrules_prior_term(nb.state, mover, d_child, mask, clock,
                                        base_py)
            assert _bits(t_py) == t_bits, (
                f"term parity broke: seed {seed} ply {_ply} action {a} "
                f"py {t_py!r} rs_bits {t_bits}")
            compared += 1
    assert compared >= 40, f"parity corpus too thin ({compared} values)"


def _rs_cfg(carc_rs, sims=64, **jr):
    """A champion-shaped SearchConfigRs through the CANONICAL leaf mapping
    (`rust_agent.leaf_config_rs`), with the jr kwargs passed DIRECTLY so the
    dose-0-with-moved-mask control is constructible (the production
    `search_config_rs` deliberately drops the kwargs at dose 0)."""
    from carcassonne_ai import rust_agent
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
    leaf = rust_agent.leaf_config_rs(DEFAULT_CONFIG)
    return carc_rs.SearchConfigRs(leaf, sims, 1.5, 5.0, 15.0, 15.0,
                                  "float", "visits", None, 1.0, True,
                                  "glibc_fma", **jr)


def _wide_root(carc_rs, seed="28000000000"):
    m = carc_rs.MirrorState.from_seed(seed)
    for _ in range(30):
        la = m.legal_actions()
        m.advance(la[len(la) // 2])
    assert len(m.legal_actions()) >= 6
    return m


def test_rust_search_dose0_with_moved_mask_is_bit_identical():
    carc_rs = _carc_rs_with_surface_b()
    m = _wide_root(carc_rs)
    a = m.search_single(_rs_cfg(carc_rs))
    b = m.search_single(_rs_cfg(carc_rs, jrules_prior_dose=0.0,
                                jrules_prior_mask=27,
                                jrules_prior_scope="own"))
    assert a == b


def test_rust_search_dose_moves_priors_not_the_root_value():
    carc_rs = _carc_rs_with_surface_b()
    m = _wide_root(carc_rs)
    off = m.search_single(_rs_cfg(carc_rs))
    on = m.search_single(_rs_cfg(carc_rs, jrules_prior_dose=1.0))
    assert on["root_leaf_value_bits"] == off["root_leaf_value_bits"]
    assert on["root_priors"] != off["root_priors"]


def test_search_config_rs_resolves_and_reports_the_knobs():
    carc_rs = _carc_rs_with_surface_b()
    cfg = _rs_cfg(carc_rs, jrules_prior_dose=0.25, jrules_prior_scope="own")
    assert cfg.jrules_prior == (0.25, 31, "own")
    assert "jrules_prior_dose=0.25" in repr(cfg)
    # default-off repr is byte-identical to the pre-B string (no mention)
    assert "jrules_prior" not in repr(_rs_cfg(carc_rs))
    with pytest.raises(ValueError):
        _rs_cfg(carc_rs, jrules_prior_dose=0.25, jrules_prior_scope="both")
    with pytest.raises(ValueError):
        _rs_cfg(carc_rs, jrules_prior_dose=0.25, jrules_prior_mask=0)
